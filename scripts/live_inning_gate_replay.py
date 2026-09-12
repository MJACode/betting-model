"""
What an inning gate on `mlb_live_total_runs` would ACTUALLY have done.

WHY THIS EXISTS RATHER THAN A QUERY
-----------------------------------
Split the settled record by the inning the bet was taken in and it reads:

    innings 1-3   26-31   -9.66u    claims ~73%, delivers ~46%
    innings 4+    27-10  +11.69u    claims ~74%, delivers ~73%

both halves of the current regime agreeing in both bands. It is tempting to
read the second row as "what a gate returns". It is not, and the reason is
`LOCK_LIVE_PICKS_AT_FIRST_SIGNAL`: one BET per (game, model), 94 BETs across 94
distinct games since 2026-08-24. So "innings 4+" is the record of games whose
FIRST qualifying signal happened to arrive late — a self-selected set. Under a
gate, a game that fired in the 2nd does not vanish; it locks at its first
qualifying signal from the gate inning on, at a different line and a different
price. Some of those re-qualify and some never do, and no query over `picks` can
say which, because the bets a gate would have made were never written.

So this replays the PRODUCTION decision over the states and prices we kept:

    live_game_state   108,284 rows / 171 games   since 2026-08-24
    odds (in_play, totals)  642,582 rows / 188 games

For each game, for each state snapshot in time order, it pairs the state with
the in-play DK price in force at that moment, rebuilds the model's own feature
row, and asks `classify_live_signal` — the real thresholds, the real EV floor,
the real edge cap. The first BET at or after the gate inning is the pick that
gate would have locked. Grading is the final score against that pick's own line.

Reusing the production functions is the point. A reimplementation of the
decision would answer a question about the reimplementation.

THE GRADING WAS VALIDATED BEFORE ANY OF IT WAS BELIEVED (CLAUDE.md 7: validate
the grading before moving a cut). `_grade`'s rule — final total against the
pick's own `scored_line`, over/under, whole numbers push — was recomputed
against production settlement for every settled `mlb_live_total_runs` BET since
2026-08-24 and agrees on **94 of 94**.

WHY THIS CANNOT CURRENTLY BE 0 (2026-09-08)
-------------------------------------------
The 2026-09-07 run reported **13 games production bet that the replay does not**
and its gate verdict was acted on anyway. Diagnosed here, and it is not a
pairing or coverage problem: the missed games have ~900 paired snapshots each.

The replay and production disagree about the MODEL PROBABILITY, because they
disagree about the pre-game feature row. Measured on
`MLB_2026-09-07_LAA_BOS` — same state, same DK line 7.5, same price -118,
holding everything fixed and varying only the stats snapshot:

    stats as of 2026-09-07   lam 7.853   p_over 0.5263   -> no bet
    stats as of 2026-09-05   lam 9.391   p_over 0.7199   -> BET
    production recorded                  p_over 0.7268   -> BET

Only six features move between those two rows — team ERA 3.60 vs 3.65, 4.21 vs
4.25, and runs_last_10 by 0.1-0.2. **That is enough to move expected remaining
runs by 1.5 and the over probability by 19 points**, which is a finding about
the model, not about the replay, and it is recorded in
`docs/mlb_volume_efficiency.md`.

Production's row cannot be reconstructed. `models.live_scorer._pregame_features`
memoises on `(game_date, game_id)` in process, so a running loop freezes one
feature row per game at whatever the stats tables held when it first saw the
game — a moment that is not recorded anywhere. The decision log
(`DECISION_LOG_DIR`) is NFL-only; no MLB live pick stores its feature vector or
its lambda.

So the replay cannot be made faithful by bounding its inputs on the pick's
timestamp: the newest snapshot available at 17:55 UTC (as of 09-07, created
10:05 UTC) gives 0.5263, and production got 0.7268. **The information needed is
not in the database.** Recording lambda and the feature row on every live pick
is the prerequisite, and until then the control fails and the tables are
refused.

A SECOND DEFECT, FOUND HERE AND SHARED WITH PRODUCTION. `_pregame_features`
passes `_get_dk_odds(conn, game_id, "h2h")` into `build_mlb_game_features`. For
this game that returns `snapshot_type='in_play'`, home -10000 / away +1380,
stamped 19:44 UTC — an in-play price from two hours AFTER the pick, read as a
pre-game one. It does not feed these 18 features, so it is not the bug above,
but it is CLAUDE.md 6's pre-game/in-play separation broken in the live path and
it will be the next wrong number.

WHAT IT DOES NOT MODEL
  * The 5s cadence and the staleness guards that make a pass happen at all. A
    price that existed in `odds` is assumed askable, which flatters every gate
    equally and so does not bias the COMPARISON between gates.
  * Any effect of the pick itself on the market.
  * Best-line shopping: DK only, which is the decision book (CLAUDE.md 6).

Usage
-----
    python -m scripts.live_inning_gate_replay --since 2026-08-24
    python -m scripts.live_inning_gate_replay --since 2026-08-24 --gates 1 3 4 5 6

Reports one row per gate: bets, W-L, units, and the realised-vs-claimed gap.
Gate 1 is the ungated replay and is the control — if it does not roughly
reproduce the 94 bets actually written, the replay is wrong and nothing else in
the table means anything. That check is printed, not assumed.
"""

from __future__ import annotations

import argparse
from collections import defaultdict

import numpy as np
from loguru import logger

import config
from data.db import get_connection
from features.live_game_features import build_live_state_row
from data.live_quote_guard import quote_predates_score
from models.live_scorer import (
    _count_over_prob,
    classify_live_signal,
    expected_value,
)
from models.trainer import load_model

MODEL_ID = "mlb_live_total_runs"
STATE_COLS = ["inning", "inning_half", "outs", "bases_state",
              "home_score", "away_score", "abstract_game_state", "snapshot_at"]

# How stale an in-play price may be relative to the state it is paired with.
MAX_PRICE_AGE_S = 120

# AND THE SAME STALE-QUOTE GUARD PRODUCTION APPLIES. Until 2026-09-12 the
# pairing here was by time ALONE, while `_get_live_dk_odds` had (since #458,
# 2026-09-03) also declined a quote the book stamped BEFORE the score it has
# not priced yet. The gap was not academic: on the 47-slate 2026 replay that
# set the 0.72 cut, 18 of the 38 qualifying bets were quotes production would
# have refused, and they went 16-2 -- they carried the entire result
# (docs/thresholds.md, "The forward check on fresh quotes"). A replay that
# counts bets production cannot take is not a replay of production.
LIVE_SCORE_LAG_TOLERANCE_SEC = getattr(config, "LIVE_SCORE_LAG_TOLERANCE_SEC", 0.0)


def _games(conn, since: str) -> list[dict]:
    rows = conn.execute("""
        SELECT game_id, game_date, season, home_team, away_team, commence_time,
               home_score, away_score
        FROM games
        WHERE sport = 'MLB' AND game_date >= %s
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY game_date, game_id
    """, (since,)).fetchall()
    cols = ["game_id", "game_date", "season", "home_team", "away_team",
            "commence_time", "home_score", "away_score"]
    return [dict(zip(cols, r)) for r in rows]


def _states(conn, game_id: str) -> list[dict]:
    rows = conn.execute(f"""
        SELECT {', '.join(STATE_COLS)}
        FROM live_game_state
        WHERE game_id = %s
        ORDER BY snapshot_at
    """, (game_id,)).fetchall()
    return [dict(zip(STATE_COLS, r)) for r in rows]


def _prices(conn, game_id: str) -> list[dict]:
    """DK in-play totals, oldest first. One row per snapshot we kept."""
    rows = conn.execute("""
        SELECT snapshot_at, total_line, over_price, under_price
        FROM odds
        WHERE game_id = %s AND snapshot_type = 'in_play'
          AND market = 'totals' AND bookmaker = 'draftkings'
          AND total_line IS NOT NULL
        ORDER BY snapshot_at
    """, (game_id,)).fetchall()
    return [dict(zip(["snapshot_at", "total_line", "over_price", "under_price"], r))
            for r in rows]


def _score_seen_at(states: list[dict]) -> list:
    """Per state, when we FIRST saw the score that state carries.

    The offline twin of live_scorer._score_changed_at, which asks the same
    question of live_game_state at one instant. None where the score has not
    changed since the first state we hold -- the same "first sight" rule, and
    the same meaning: nothing to be stale against.
    """
    out, first_seen, prev = [], None, None
    for st in states:
        score = (st.get("home_score"), st.get("away_score"))
        if prev is None:
            prev = score          # the opening state: no earlier, different score
        elif score != prev:
            first_seen = st["snapshot_at"]
            prev = score
        out.append(first_seen)
    return out


def _pair(states: list[dict], prices: list[dict]) -> list[tuple[dict, dict]]:
    """Each state with the newest price at or before it, within the age bound
    AND not predating the score that state shows — production's own two rules
    (`_get_live_dk_odds`), the second via production's own helper.

    A merge walk rather than a per-state scan: these are two sorted lists of a
    few thousand rows per game, and the quadratic version took longer than the
    query did.
    """
    from datetime import datetime

    def ts(v):
        s = str(v).replace("Z", "+00:00")
        try:
            return datetime.fromisoformat(s).timestamp()
        except ValueError:
            return None

    pt = [(ts(p["snapshot_at"]), p) for p in prices]
    pt = [(t, p) for t, p in pt if t is not None]
    seen = _score_seen_at(states)
    out, i = [], 0
    for st, score_seen_at in zip(states, seen):
        t = ts(st["snapshot_at"])
        if t is None:
            continue
        while i + 1 < len(pt) and pt[i + 1][0] <= t:
            i += 1
        if not pt or pt[i][0] > t or (t - pt[i][0]) > MAX_PRICE_AGE_S:
            continue
        if quote_predates_score(pt[i][1]["snapshot_at"], score_seen_at,
                                LIVE_SCORE_LAG_TOLERANCE_SEC):
            continue
        out.append((st, pt[i][1]))
    return out


def _signals(artifact, game: dict, pregame: dict,
             paired: list[tuple[dict, dict]]) -> list[dict]:
    """Every BET the model would have produced, in time order.

    Exactly the arithmetic of `_score_live_model`'s poisson branch, calling the
    same helpers. Both sides are offered to `classify_live_signal`; only BETs
    are returned, because a gate only ever changes which BET is first.
    """
    feat_cols = artifact["feature_cols"]
    clf = artifact["model"]
    out = []
    for state, price in paired:
        row = build_live_state_row(state, pregame, MODEL_ID)
        if row is None:
            continue
        x = np.array([[np.nan if row.get(c) is None else float(row[c])
                       for c in feat_cols]], dtype=float)
        try:
            lam = float(np.clip(clf.predict(x)[0], 1e-6, None))
        except Exception:
            continue
        rest_line = float(price["total_line"]) - row["total_runs"]
        if rest_line < 0:
            continue
        p_over = _count_over_prob(lam, rest_line, artifact.get("dispersion"))
        for side, prob, odds in (("over", p_over, price["over_price"]),
                                 ("under", 1.0 - p_over, price["under_price"])):
            if odds is None:
                continue
            implied = _implied(odds)
            if implied is None:
                continue
            if classify_live_signal(MODEL_ID, prob, prob - implied, odds) != "BET":
                continue
            out.append({"inning": state.get("inning"), "side": side,
                        "prob": prob, "odds": float(odds),
                        "line": float(price["total_line"]),
                        "snapshot_at": state["snapshot_at"],
                        "ev": expected_value(prob, odds)})
    return out


def _implied(american) -> float | None:
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return (abs(a) / (abs(a) + 100.0)) if a < 0 else (100.0 / (a + 100.0))


def _grade(sig: dict, game: dict) -> tuple[str, float]:
    """Result and units for one full-game total, against the final score."""
    total = float(game["home_score"]) + float(game["away_score"])
    if total == sig["line"]:
        return "PUSH", 0.0
    won = (total > sig["line"]) if sig["side"] == "over" else (total < sig["line"])
    if not won:
        return "LOSS", -1.0
    a = sig["odds"]
    return "WIN", (a / 100.0 if a > 0 else 100.0 / abs(a))


def replay(since: str, gates: list[int]) -> dict:
    conn = get_connection()
    artifact = load_model(MODEL_ID)
    if artifact is None:
        raise SystemExit(f"no active artifact for {MODEL_ID}")

    from features.feature_engine import build_mlb_game_features
    from models.scorer import _get_dk_odds

    per_gate = defaultdict(list)
    dropped: dict[str, str] = {}
    scanned = 0
    try:
        for game in _games(conn, since):
            gid = game["game_id"]
            states = _states(conn, gid)
            if not states:
                dropped[gid] = "no live_game_state rows"
                continue
            prices = _prices(conn, gid)
            if not prices:
                dropped[gid] = "no DK in_play totals rows"
                continue
            # Both markets, as production's _pregame_features does: h2h for
            # the moneyline context, totals for `pregame_total_line`. Passing
            # only h2h replays the post-2026-09-08 artifact with its anchor
            # NaN, which is the map/artifact mismatch the scorer's guard
            # refuses -- so the replay must not quietly do it either.
            pregame = build_mlb_game_features(
                conn, gid, game["game_date"], game["home_team"],
                game["away_team"], game["season"],
                odds_row=_get_dk_odds(conn, gid, "h2h"),
                totals_row=_get_dk_odds(conn, gid, "totals"))
            if not pregame:
                dropped[gid] = "pre-game features unavailable"
                continue
            scanned += 1
            paired = _pair(states, prices)
            if not paired:
                dropped[gid] = (f"no state paired with a price inside "
                                f"{MAX_PRICE_AGE_S}s ({len(states)} states, "
                                f"{len(prices)} prices)")
                continue
            sigs = _signals(artifact, game, pregame, paired)
            if not sigs:
                dropped[gid] = (f"{len(paired)} paired snapshots, no signal "
                                f"cleared the cut")
            for g in gates:
                first = next((s for s in sigs if (s["inning"] or 0) >= g), None)
                if first is not None:
                    per_gate[g].append({**first, "game_id": game["game_id"],
                                        "game_date": game["game_date"],
                                        **dict(zip(("result", "units"),
                                                   _grade(first, game)))})
            if scanned % 20 == 0:
                logger.info(f"  replayed {scanned} games")
    finally:
        conn.close()

    return {"scanned": scanned, "per_gate": dict(per_gate), "dropped": dropped}


def _bet_games(conn, since: str) -> set:
    """Games that actually produced a settled production BET."""
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND is_live AND signal_type = 'BET'
          AND game_date >= %s AND result IN ('WIN', 'LOSS', 'PUSH')
    """, (MODEL_ID, since)).fetchall()}


def _table(out: dict, keep, title: str) -> None:
    print()
    print(title)
    print(f"{'gate':>5}{'bets':>7}{'W-L-P':>10}{'units':>9}{'ROI':>8}"
          f"{'claims':>8}{'delivers':>10}")
    for gate in sorted(out["per_gate"]):
        rows = [r for r in out["per_gate"][gate]
                if keep is None or r["game_id"] in keep]
        w = sum(1 for r in rows if r["result"] == "WIN")
        l = sum(1 for r in rows if r["result"] == "LOSS")
        p = sum(1 for r in rows if r["result"] == "PUSH")
        u = sum(r["units"] for r in rows)
        claims = sum(r["prob"] for r in rows) / max(len(rows), 1)
        delivers = w / max(w + l, 1)
        print(f"{gate:>5}{len(rows):>7}{f'{w}-{l}-{p}':>10}{u:>+9.2f}"
              f"{u / max(len(rows), 1):>+8.1%}{claims:>8.1%}{delivers:>10.1%}")


def _refuse_tables(missed, force: bool) -> bool:
    """Whether the control has failed and the gate tables must not be printed.

    A separate function because it is the whole point of the control: on
    2026-09-07 the check printed BESIDE the tables, 13 games were missing, and
    the verdict was acted on anyway. `force` is for debugging the replay, never
    for a gate decision.
    """
    return bool(missed) and not force


def _report(out: dict, conn) -> None:
    print()
    print(f"Games replayed: {out['scanned']}")

    bet_games = _bet_games(conn, ARGS.since)
    gate1 = out["per_gate"].get(min(out["per_gate"], default=1), [])

    # THE CONTROL, and it is NOT "the two counts are close".
    #
    # LOCK_LIVE_PICKS_AT_FIRST_SIGNAL means production writes at most ONE bet
    # per game, and so does this replay. So the ungated replay's games should be
    # a SUPERSET of production's: the replay sees every snapshot we kept,
    # production saw only the passes it managed to run. Every extra game is one
    # production never bet; a game production bet and the replay does not is a
    # defect in here.
    replayed_games = {r["game_id"] for r in gate1}
    extra = replayed_games - bet_games
    missed = bet_games - replayed_games
    print(f"control: {len(replayed_games)} games bet by the ungated replay vs "
          f"{len(bet_games)} by production")
    print(f"         +{len(extra)} the replay bet and production did not; "
          f"{len(missed)} the other way")
    if missed:
        print("         a game production bet that the replay does not is a "
              "REPLAY DEFECT - read it before the tables.")
        why = defaultdict(list)
        for gid in sorted(missed):
            why[out["dropped"].get(gid, "reached _signals but no BET first "
                                        "at/after gate")].append(gid)
        for reason, gids in sorted(why.items(), key=lambda kv: -len(kv[1])):
            print(f"           {len(gids):>3}  {reason}")
            for gid in gids[:4]:
                print(f"                  {gid}")

    # THE CONTROL GATES THE TABLES. It used to print beside them, and the tables
    # were read anyway -- the 2026-09-07 run reported 13 missed games and its
    # gate verdict was acted on. A number that is allowed to be read while the
    # check under it is failing is not a check.
    if _refuse_tables(missed, ARGS.force):
        print()
        print("REFUSING TO PRINT THE GATE TABLES.")
        print(f"  {len(missed)} game(s) production bet that this replay does "
              f"not reproduce. Until that is 0, the ungated control is not the")
        print("  production record and no gate comparison drawn from it means "
              "anything. See the docstring, 'WHY THIS CANNOT CURRENTLY BE 0'.")
        print("  --force prints them anyway, for debugging only.")
        print()
        raise SystemExit(2)

    # BOTH TABLES, because they answer different questions and the second is the
    # one a gate decision should read. The unrestricted table includes games
    # production never bet, so an uplift there may be this replay's optimism
    # about how often a pass actually ran rather than anything about innings.
    _table(out, None, "ALL replayed games (a wider universe than production saw):")
    _table(out, bet_games,
           "RESTRICTED to games production actually bet - read this one:")
    print()



ARGS = None


def main() -> None:
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", default="2026-08-24",
                    help="first game_date to replay (default: the 08-30 cut's era)")
    ap.add_argument("--gates", type=int, nargs="+", default=[1, 3, 4, 5, 6],
                    help="inning gates to compare; 1 is the ungated control")
    ap.add_argument("--force", action="store_true",
                    help="print the gate tables even when the control fails. "
                         "For debugging the replay, never for a gate decision.")
    ARGS = ap.parse_args()
    out = replay(ARGS.since, ARGS.gates)
    conn = get_connection()
    try:
        _report(out, conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
