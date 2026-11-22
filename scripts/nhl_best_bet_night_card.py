"""NHL best bet a night: write at most one bet a night (models/nhl_best_bet_night.py).

Runs on every refresh pass right after the NHL totals card, and on every NHL
goalie-window tick that decides games (scheduler.run_nhl_goalie_window), so a
night's bet lands on the first fetch after both goalies of some game are
confirmed and a bettable book beats Pinnacle's no-vig price there.

ONE BET A NIGHT, INSERT ONCE (CLAUDE.md 1c). The night is the game's ET date.
Once any of the four ids (nhl_night_puckline, nhl_night_total,
nhl_night_moneyline, nhl_night_regulation) holds a BET for a night, nothing
more is written for it; a later better price writes nothing. The check and the
insert run under the family's advisory lock.

NO SECOND BET ON A GAME. A game already holding an NHL BET from any model
(the totals card runs just before this one) is skipped, so the family never
doubles a bet another model already made, and never bets against one
(the side-conflict rule, CLAUDE.md "one game never carries two bets that
cannot both win").

BOTH STARTING GOALIES CONFIRMED FIRST (mike, 2026-10-20), and each market's
price fetched after it: models/nhl_goalie_gate.py, then
models/nhl_best_bet_night.after_confirmation (per market), then refuse_unknown
at the insert.

ROW SHAPE: the totals card's (scripts/nhl_totals_card.pick_rows), per market.
Flat stake (picks.stake_units NULL): a higher EV floor did not do better in
the evidence.

    python -m scripts.nhl_best_bet_night_card              # print, write nothing
    python -m scripts.nhl_best_bet_night_card --publish    # write the night's bet
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nhl_best_bet_night as nb  # noqa: E402
import models.nhl_goalie_gate as goalie_gate  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.market_relative import implied  # noqa: E402
from models.scorer import _build_pick_label, _get_current_bankroll, _insert_picks, quarter_kelly  # noqa: E402
from scripts.nhl_totals_card import slate  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

SPORT = "NHL"
# Does a player-prop BET on a game count as "an NHL bet" for the skip? Built as
# mike said it, yes. Measured 2026-11-22 on 2026-27's 372 started games: 234
# held a BET placed before the start, 108 of them player props only, so props
# can block up to 63% of games against 34% for side and total bets alone.
SKIP_GAMES_WITH_PROP_BETS = True


def label_for(c: nb.Candidate, home: str, away: str) -> str:
    if c.market == "h2h_3way":
        # The regulation model's own labels (models/scorer.py).
        return {"home": f"{home} (Regulation)", "away": f"{away} (Regulation)",
                "draw": f"{away} @ {home} Draw (Regulation)"}[c.side]
    return _build_pick_label(c.side, home, away, c.market, c.line)


def pick_rows(cands, games: dict, bankroll: float) -> list[dict]:
    """Candidates -> picks rows. Pure given its inputs."""
    from models.honest_ev import gate
    rows = []
    for c in cands:
        ev = gate(c.model_id, c.fair, c.price)
        if not ev.clears:
            logger.info(f"{c.model_id}: {ev.reason} - dropped {c.game_id} {c.side} @{c.book}")
            continue
        g = games.get(c.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        label = label_for(c, home, away)
        problems = pick_problems(label, c.side, c.line, c.model_id, home, away)
        if problems:
            logger.error(f"{c.model_id}: refusing {c.game_id}: {'; '.join(problems)}")
            continue
        price = float(c.price)
        dec_implied = implied(price)
        dk = c.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = c.book == nb.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(c.fair, dec_implied, bankroll)
        decision_edge = round(c.fair - dec_implied, 4)
        rows.append({
            "game_id": c.game_id, "model_id": c.model_id, "sport": SPORT,
            "game_date": g.get("game_date"), "game_time": g.get("commence_time"),
            "pick_side": c.side, "pick_label": label,
            "model_probability": round(c.fair, 4),
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(c.fair - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": c.dk_link if dk is not None else None,
            "line_book": None if dk is not None else c.book,
            "scored_line": c.line,
            "kelly_fraction": kelly_frac, "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll,
            "signal_type": "BET", "confidence_tier": "MED",
            "injury_flag": None, "injury_detail": None,
            "decision_book": c.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4), "decision_edge": decision_edge,
            "best_book": None if at_dk else c.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else c.link,
        })
    return rows


def nights_with_bet(conn, nights) -> set[str]:
    nights = sorted({n for n in nights if n})
    if not nights:
        return set()
    return {str(r[0])[:10] for r in conn.execute(
        "SELECT DISTINCT game_date FROM picks WHERE model_id = ANY(%s) AND signal_type = 'BET' "
        "AND game_date = ANY(%s)", (list(nb.MODEL_IDS), nights)).fetchall()}


def games_with_bet(conn, game_ids) -> set[str]:
    """The games already holding an NHL BET. A VOID row (never a pick) and one
    written while its model was paused (not a signal) hold nothing, as in the
    side-conflict check."""
    game_ids = list(game_ids)
    if not game_ids:
        return set()
    from config import PAUSED_NOTE
    props = "" if SKIP_GAMES_WITH_PROP_BETS else "AND prop_market IS NULL AND model_id NOT LIKE 'nhl_prop_%%' "
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM picks WHERE game_id = ANY(%s) AND sport = 'NHL' "
        "AND signal_type = 'BET' AND condition_status IS DISTINCT FROM 'VOID' "
        "AND downgrade_reason IS DISTINCT FROM %s " + props,
        (game_ids, PAUSED_NOTE)).fetchall()}


def publish(conn, rows: list[dict]) -> int:
    """At most one bet a night, under the family's lock, in one transaction."""
    if not rows:
        return 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, nb.FAMILY)
    rows = goalie_gate.refuse_unknown(conn, rows, mode="drop", label=nb.FAMILY)
    written = 0
    for r in rows:
        # Re-checked under the lock: another pass may have written since.
        if nights_with_bet(conn, [r["game_date"]]) or games_with_bet(conn, [r["game_id"]]):
            continue
        _insert_picks(conn, [r])
        written += 1
    conn.commit()
    return written


def render(picks: dict, cands: dict, diag: dict) -> str:
    counts = " ".join(f"{k}={diag.get(k, 0)}" for k in nb.DIAG_KEYS)
    lines = [f"NHL best bet a night ({nb.FAMILY}): {counts}"]
    for gid, c in sorted(cands.items(), key=lambda kv: -kv[1].ev):
        mark = " <- tonight's bet" if c in picks.values() else ""
        lines.append(f"  {gid:28s} {c.model_id:21s} {c.side:5s} {'' if c.line is None else c.line} "
                     f"@{c.book} {c.price:+.0f} fair {c.fair:.4f} EV {c.ev:+.4f}{mark}")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        games = slate(conn, now)
        if not games:
            logger.info("NHL best bet a night: no unstarted NHL games")
            return {"games": 0, "held": 0, "candidates": 0, "picks": 0, "published": 0}
        states = goalie_gate.matchup_states(conn, list(games), now=now)
        games, held = goalie_gate.split_known(games, {g: m.reason for g, m in states.items()})
        goalie_gate.log_held("NHL best bet a night", held)
        if not games:
            return {"games": len(held), "held": len(held), "candidates": 0, "picks": 0, "published": 0}
        known_at = {g: states[g].known_at for g in games}
        quotes, waiting = nb.after_confirmation(nb.load_quotes(conn, games), known_at)
        if waiting:
            logger.info(f"NHL best bet a night: {len(waiting)} market(s) wait for a Pinnacle fetch "
                        f"taken after both goalies were confirmed: "
                        + ", ".join(f"{g} {m}" for g, m in waiting))
        cands, diag = nb.game_candidates(quotes, now=now)
        picks = nb.pick_of_the_night(cands, games,
                                     nights_with_bet(conn, [g["game_date"] for g in games.values()]),
                                     games_with_bet(conn, list(games)))
        logger.info("\n" + render(picks, cands, diag))
        published = 0
        if do_publish and picks:
            rows = pick_rows(list(picks.values()), games, _get_current_bankroll(conn))
            published = publish(conn, rows)
            logger.info(f"NHL best bet a night: {published} bet(s) written")
        return {"games": len(games) + len(held), "held": len(held), "candidates": len(cands),
                "picks": len(picks), "published": published}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
