"""The NBA prop door: ONE bet a game across both NBA prop models, four a night, the strongest first.

mike, 2026-10-20, after opening night wrote 36 NBA prop bets on one game:
"Void all nba props. Wild you sent like a million props. Only the strongest
picks need to be sent, like NHL." This replaces the 2026-10-16 rule for
nba_prop_market and nba_prop_projection ("no game or night cap, maximize units
won").

THE SHAPE IS NHL's (scripts/nhl_props_card.py): the prop models' candidates are
pooled, the strongest bet in each game is kept (none for a game either model
has already bet), then the strongest MAX_NBA_PROP_BETS_PER_NIGHT of the night
(one game_date), the bets already written that night counted. "Strongest" is
the bet's EV percentile within its OWN model (below). publish_across_models
is the only door an NBA prop pick goes through: neither card writes on its own.

ONE LOOK, ONE CHOICE. Both cards run in the same step (run_cards): the rule's
card first, then the projection card told which games the rule decides in this
look, so it decides them in the same look rather than a tick later. Every
candidate of both is pooled BEFORE anything is chosen, so the order the cards
run in cannot decide which model's bet a game gets.

WHAT STILL HOLDS FROM EACH CARD (CLAUDE.md 1c, and each card's own ledger):
  - a game a card has decided stays decided: its ledger row is written once,
    whether or not its bet survived the cap, and it is never looked at again;
  - a game that already holds an NBA prop bet from EITHER model gets no other,
    on any later look;
  - a written pick is never rewritten or deleted. The cap decides only what is
    WRITTEN; a dropped candidate leaves no picks row. Its game's ledger row
    says how many were dropped and why (detail: cap_game_already_bet,
    cap_one_a_game, cap_night_full) and n_bets is what was written.

WHAT COUNTS AGAINST THE NIGHT: every BET row either model wrote for that
game_date, except a VOID one. A VOIDed pick is a row that should never have
been produced (scripts/void_picks.py); it is not a bet of record, so it does
not use a night's slot. (2026-10-20: the 36 VOIDed opening-night bets would
otherwise fill that night nine times over.) A VOIDed game still counts as
BET for the one-a-game rule, as it always did for re-deciding a game.

THE RANKING: EACH MODEL'S OWN EV PERCENTILE (models/nba_prop_rank.py).
nba_prop_market's EV is Pinnacle's no-vig under times the price (median 0.020
over its graded bets); nba_prop_projection's is its calibrated probability
times the price (median 0.083), which its own notes call an upper bound
(models/nba_prop_projection.py). On raw EV the projection model held 99.7% of
the pooled top tenth and the market model got 0.2% to 1.3% of the one-a-game
bets: raw EV switches the market model off. So a bet ranks by where its EV
sits among its own model's graded EVs (2023-24..2025-26, fixed breakpoints);
a tie goes to the larger raw EV, then a stable key. Graded at one a game and
four a night in tip order: +153.8 units, +9.69%, the market model on about 30%
of the bets (raw EV: +134.0 units, +8.86%; the gap is inside the noise).

LIVE, a look writes what has cleared by then: a better bet in a game that tips
later does not replace an earlier one, and an early game can use a night's
slot a later game would have used. So the night fills in tip order, the order
the grade measured; inside one look the strongest goes first.

ONE MODEL'S LOOK FAILING DOES NOT STOP THE OTHER. Each look's error is logged
and that model has no candidates this look; the other model still decides and
writes; the result carries the error and the step reports failure (exit 1).

    python -m scripts.nba_props_card              # both cards and the choice, write nothing
    python -m scripts.nba_props_card --publish    # write the decisions and the chosen bets
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scripts.nba_prop_market_card as rule_card  # noqa: E402
import scripts.nba_prop_projection_card as projection_card  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.nba_prop_rank import ev_percentile  # noqa: E402

RULE_ID = rule_card.MODEL_ID                     # nba_prop_market
PROJECTION_ID = projection_card.MODEL_ID         # nba_prop_projection
# Every NBA prop model. One bet a game is shared among them. The rule's id
# first: it is the order the locks are taken in (the order the projection
# card always took them), so no two writers can deadlock.
PROP_MODEL_IDS = (RULE_ID, PROJECTION_ID)
MAX_NBA_PROP_BETS_PER_GAME = 1
# At most this many NBA prop bets a night (one game_date), strongest first, the
# bets already written that night included (VOID rows excepted). mike,
# 2026-10-20: "Only the strongest picks need to be sent, like NHL." The NBA
# grade (both models, one a game, 2023-24..2025-26, in tip order) set it: 3 to
# 6 a night all returned about 8 to 9%; 4 gave +153.6 units, +9.69%, about 4
# bets a night instead of about 187 uncapped (docs/thresholds.md).
MAX_NBA_PROP_BETS_PER_NIGHT = 4
# Each model's ledger, for correcting n_bets to what was actually written.
DECISIONS_TABLES = {RULE_ID: rule_card.DECISIONS_TABLE, PROJECTION_ID: projection_card.DECISIONS_TABLE}


# ── reads (inside the lock when publishing) ───────────────────────────────────

def games_with_a_prop_bet(conn, game_ids: list[str]) -> set[str]:
    """The games either NBA prop model has already written a BET for, whatever became of it."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM picks WHERE model_id = ANY(%s) AND signal_type = 'BET' "
        "AND game_id = ANY(%s)", (list(PROP_MODEL_IDS), list(game_ids))).fetchall()}


def prop_bets_by_night(conn, game_dates: list[str]) -> dict[str, int]:
    """How many NBA prop BETs are already written for each game_date, a VOIDed one not counted."""
    if not game_dates:
        return {}
    return {str(d)[:10]: int(n) for d, n in conn.execute(
        "SELECT game_date, count(*) FROM picks WHERE model_id = ANY(%s) AND signal_type = 'BET' "
        "AND game_date = ANY(%s) AND condition_status IS DISTINCT FROM 'VOID' GROUP BY game_date",
        (list(PROP_MODEL_IDS), list(game_dates))).fetchall()}


# ── the choice (pure) ─────────────────────────────────────────────────────────

def _rank(r: dict) -> tuple:
    """Highest EV percentile within its own model first, then the larger raw EV, then a stable
    key: a tie goes the same way whichever list a row came in."""
    ev = float(r["_ev"])
    return (-ev_percentile(r["model_id"], ev), -ev, r["model_id"], str(r["player_id"]),
            r["prop_market"], r["pick_side"], float(r["scored_line"]))


def one_per_game(rows: list[dict], taken: set[str] | None = None) -> list[dict]:
    """The strongest row in each game across both NBA prop models, none for a game already bet. Pure."""
    taken = taken or set()
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=_rank):
        if r["game_id"] in taken:
            continue
        n = left.setdefault(r["game_id"], MAX_NBA_PROP_BETS_PER_GAME)
        if n <= 0:
            continue
        left[r["game_id"]] = n - 1
        kept.append(r)
    return kept


def per_night(rows: list[dict], written: dict[str, int] | None = None) -> list[dict]:
    """At most MAX_NBA_PROP_BETS_PER_NIGHT a game_date, strongest first, written bets counted. Pure."""
    written = written or {}
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=_rank):
        d = str(r["game_date"])[:10]
        n = left.setdefault(d, MAX_NBA_PROP_BETS_PER_NIGHT - written.get(d, 0))
        if n <= 0:
            continue
        left[d] = n - 1
        kept.append(r)
    return kept


def choose(rows: list[dict], taken: set[str], written: dict[str, int]
           ) -> tuple[list[dict], dict[tuple[str, str], Counter]]:
    """-> (the rows to write, {(model_id, game_id): Counter of why each other row was dropped}). Pure."""
    by_game = one_per_game(rows, taken)
    chosen = per_night(by_game, written)
    kept_game, kept = {id(r) for r in by_game}, {id(r) for r in chosen}
    why: dict[tuple[str, str], Counter] = {}
    for r in rows:
        if id(r) in kept:
            continue
        reason = ("cap_game_already_bet" if r["game_id"] in taken
                  else "cap_one_a_game" if id(r) not in kept_game else "cap_night_full")
        why.setdefault((r["model_id"], r["game_id"]), Counter())[reason] += 1
    return chosen, why


def _detail(base: str | None, dropped: Counter | None) -> str:
    extra = " ".join(f"{k}={v}" for k, v in sorted((dropped or {}).items()))
    return " ".join(x for x in ((base or "").strip(), extra) if x)


# ── the door ──────────────────────────────────────────────────────────────────

def publish_across_models(conn, rows: list[dict], rule_decisions: list,
                          projection_decisions: list[dict]) -> dict:
    """Write each decided game once and the bets the cap allows. The only door an NBA prop pick
    goes through.

    Under both models' locks (nba_prop_market's first), each card's ledger, the games already
    bet and the night's count are re-read; the candidates of the games each card decides now are
    pooled; one a game, then MAX_NBA_PROP_BETS_PER_NIGHT a night, strongest first (_rank); then
    each new decision row and its chosen bets, in ONE transaction. A decision row's n_bets is the
    number of its picks inserts that returned a row.
    -> {"written", "decided": {model_id: n}, "pool", "chosen", "dropped": {reason: n}}.
    """
    out = {"written": 0, "decided": {m: 0 for m in PROP_MODEL_IDS}, "pool": 0, "chosen": 0,
           "dropped": {}}
    if not rule_decisions and not projection_decisions:
        return out
    from scripts.nfl_wind_publisher import _lock_model
    for m in PROP_MODEL_IDS:
        _lock_model(conn, m)
    rule_ids = sorted({d.game_id for d in rule_decisions})
    proj_ids = sorted({d["game_id"] for d in projection_decisions})
    # each card's own once-only rule, re-read inside the lock
    rule_skip = rule_card.decided_games(conn, rule_ids) | rule_card.games_with_a_bet(conn, rule_ids)
    proj_skip = projection_card.decided_games(conn, proj_ids)
    rule_new = sorted((d for d in rule_decisions if d.game_id not in rule_skip), key=lambda d: d.game_id)
    proj_new = sorted((d for d in projection_decisions if d["game_id"] not in proj_skip),
                      key=lambda d: d["game_id"])
    deciding = ({(RULE_ID, d.game_id) for d in rule_new}
                | {(PROJECTION_ID, d["game_id"]) for d in proj_new})
    pool = [r for r in rows if (r["model_id"], r["game_id"]) in deciding]
    taken = games_with_a_prop_bet(conn, sorted(set(rule_ids) | set(proj_ids)))
    written = prop_bets_by_night(conn, sorted({str(r["game_date"])[:10] for r in pool}))
    chosen, why = choose(pool, taken, written)

    def _write(model_id: str, gid: str, insert_decision: str, params: dict) -> None:
        mine = [r for r in chosen if r["model_id"] == model_id and r["game_id"] == gid]
        got = conn.execute(insert_decision, {**params, "n_bets": len(mine),
                                             "detail": _detail(params.get("detail"),
                                                               why.get((model_id, gid)))}).fetchone()
        if not got:
            return
        out["decided"][model_id] += 1
        n = 0
        for r in mine:
            if conn.execute(rule_card._INSERT, {c: r[c] for c in rule_card._COLS}).fetchone():
                n += 1
        out["written"] += n
        if n != len(mine):          # an insert hit ON CONFLICT DO NOTHING: count what was written
            conn.execute(f"UPDATE {DECISIONS_TABLES[model_id]} SET n_bets = %s WHERE game_id = %s",
                         (n, gid))

    for d in rule_new:
        _write(RULE_ID, d.game_id, rule_card._INSERT_DECISION,
               {"game_id": d.game_id, "fetch_at": d.fetch_at, "n_quotes": d.n_quotes, "detail": d.detail})
    for d in proj_new:
        _write(PROJECTION_ID, d["game_id"], projection_card._INSERT_DECISION, dict(d))
    conn.commit()
    dropped: Counter = Counter()
    for c in why.values():
        dropped.update(c)
    out.update(pool=len(pool), chosen=len(chosen), dropped=dict(dropped))
    logger.info(f"nba-props: {out['written']} bet(s) written of {len(pool)} that clear "
                f"(one a game across both NBA prop models, {MAX_NBA_PROP_BETS_PER_NIGHT} a night, "
                f"ranked by each model's own EV percentile; "
                f"dropped {dict(dropped)}; {len(taken)} game(s) already bet; already written by "
                f"night {written}); decided {out['decided']}")
    for r in sorted(chosen, key=_rank):
        logger.info(f"  {r['model_id']:20s} {r['game_id']:26s} {r['pick_label']} "
                    f"@{r['decision_book']} {r['decision_odds']:+.0f}  EV {float(r['_ev']):+.4f} "
                    f"(percentile {ev_percentile(r['model_id'], float(r['_ev'])):.2f})")
    return out


# ── the step ──────────────────────────────────────────────────────────────────

def run_cards(do_publish: bool = False, now: datetime | None = None, art: dict | None = None) -> dict:
    """Both NBA prop cards in one look, one choice, one write (run_pipeline step nba-props, and
    the old step names nba-prop-market / nba-prop-projection). `art`: the projection artifact,
    for a replay.

    One look raising does not stop the other model: its error is logged, that model has no
    candidates or decisions this look, the other decides and writes, and result["errors"]
    ({model_id: message}) is non-empty, so the step returns False and exits 1."""
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    errors: dict[str, str] = {}
    empty = {"games": {}, "bets": [], "diag": {}, "decisions": [], "names": {}}
    try:
        try:
            rule = rule_card.look(conn, now)
        except Exception as exc:  # noqa: BLE001 - logged, reported, the other model still bets
            logger.exception(f"nba-props: {RULE_ID} look failed; {PROJECTION_ID} continues: {exc}")
            errors[RULE_ID] = f"{type(exc).__name__}: {exc}"
            _rollback(conn)
            rule = dict(empty)
        try:
            proj = projection_card.look(conn, now, art,
                                        rule_deciding={d.game_id for d in rule["decisions"]})
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"nba-props: {PROJECTION_ID} look failed; {RULE_ID} continues: {exc}")
            errors[PROJECTION_ID] = f"{type(exc).__name__}: {exc}"
            _rollback(conn)
            proj = dict(empty)
        rows: list[dict] = []
        if rule["bets"] or proj["bets"]:
            from models.scorer import _get_current_bankroll
            bankroll = _get_current_bankroll(conn)
            rows = rule_card.pick_rows(rule["bets"], bankroll) + projection_card.pick_rows(proj["bets"], bankroll)
        logger.info("\n" + rule_card.render(rule["bets"], rule["diag"]))
        logger.info("\n" + projection_card.render(proj["bets"], proj["diag"]) + f" names={proj['names']}")
        result = {"games": len(rule["games"]), "bets": {RULE_ID: len(rule["bets"]),
                                                        PROJECTION_ID: len(proj["bets"])},
                  "published": 0, "decided": {m: 0 for m in PROP_MODEL_IDS}, "errors": errors}
        if do_publish:
            got = publish_across_models(conn, rows, rule["decisions"], proj["decisions"])
            result.update(published=got["written"], decided=got["decided"], dropped=got["dropped"])
        elif rows:
            # what the door would write now: read, not locked, nothing written
            gids = sorted({r["game_id"] for r in rows})
            chosen, _ = choose(rows, games_with_a_prop_bet(conn, gids),
                               prop_bets_by_night(conn, sorted({str(r["game_date"])[:10] for r in rows})))
            logger.info(f"nba-props (dry run): would write {len(chosen)} of {len(rows)}: "
                        + "; ".join(f"{r['model_id']} {r['pick_label']} EV {float(r['_ev']):+.4f} "
                                    f"(percentile {ev_percentile(r['model_id'], float(r['_ev'])):.2f})"
                                    for r in sorted(chosen, key=_rank)))
        return result
    finally:
        conn.close()


def _rollback(conn) -> None:
    """A failed read can leave the transaction aborted; clear it so the other model's look runs."""
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 - a connection with nothing to roll back
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    result = run_cards(do_publish=a.publish)
    print(result)
    if result.get("errors"):
        sys.exit(1)


if __name__ == "__main__":
    main()
