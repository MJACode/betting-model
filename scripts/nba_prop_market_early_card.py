"""NBA prop card, 10 HOURS before tip: `nba_prop_market_early`, a PAPER test (mike, 2026-11-26).

WHAT IT IS. `nba_prop_market`'s rule, unchanged (models/nba_prop_market.py: Pinnacle's coherent
no-vig under, every bettable book at Pinnacle's exact line, EV > 0 at -200 or better, the best
book per player and market), decided 9.5 to 10.5 hours before tip instead of 45 to 57 minutes.

WHY. The 2023-24 to 2025-26 grade of that rule on a snapshot bought 10 hours before every tip
(docs/nba_data_sources_and_handle_2026_11.md, D5): 7,572 bets, +5.8% a bet (90% CI +3.8 to +7.7)
against +2.6% for the same rule about an hour before tip on the same games, ahead in every
season. mike, 2026-11-26: yes to a forward paper test.

PAPER. The id is in config.PAUSED_MODELS (Updated-By: mike), so every row it writes carries the
pause marker and no publisher, push or record reads it; it still settles and is graded like any
pick. Unpausing it is one line in config.py with mike's name on the commit.

ONLY THE THREE MARKETS GRADED AT 10 HOURS: points, rebounds, threes (the five bought early
included blocks and steals, which this rule does not price; assists and PRA were not bought, so
they were never graded this early).

ITS OWN DOOR, NOT THE NBA PROP DOOR. scripts/nba_props_card.py writes at most one NBA prop bet a
game and six a night across the two live prop models. A card deciding ten hours earlier would
take a game's one bet before either live model looks, so this card writes its own rows outside
that door, with no game or night cap: every qualifying proposition, as graded.

DECIDED ONCE, like the hourly-fed model it copies: the first look inside the window whose newest
fetch holds Pinnacle decides the game, bets or none, in `nba_prop_market_early_decisions`, in
the same transaction as its bets, under the model's advisory lock. The live feed showed
Pinnacle's points props up 10 hours before tip on 26 of 73 games (2026-11-15 to 11-24), so most
games will log `no_sharp` and not be decided; that is the rule, not a fault.

Runs on every refresh pass after the prop fetch (step nba-prop-market-early). Regular season only.

    python -m scripts.nba_prop_market_early_card              # print the card, write nothing
    python -m scripts.nba_prop_market_early_card --publish    # write decisions and paused bets
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_prop_market as mk  # noqa: E402
import scripts.nba_prop_market_card as rule_card  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402

MODEL_ID = "nba_prop_market_early"
WINDOW_MIN = (570, 630)          # 9.5 to 10.5 hours: the graded snapshot sat at 10 hours
MARKETS = ("player_points", "player_rebounds", "player_threes")
DECISIONS_TABLE = "nba_prop_market_early_decisions"
DECISIONS_COLS = rule_card.DECISIONS_COLS
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_prop_market_early_decisions (
    game_id     TEXT PRIMARY KEY,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at    TEXT NOT NULL,
    n_quotes    INTEGER NOT NULL,
    n_bets      INTEGER NOT NULL,
    detail      TEXT
)
"""
_INSERT_DECISION = rule_card._INSERT_DECISION.replace(rule_card.DECISIONS_TABLE, DECISIONS_TABLE)


def ensure_decisions_table(conn) -> None:
    """Created once, locked down, free after that (data/ddl_guard). Committed before any lock."""
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS, rls=True,
                         revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, DECISIONS_TABLE)
    conn.commit()


def decided_games(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        f"SELECT game_id FROM {DECISIONS_TABLE} WHERE game_id = ANY(%s)", (list(game_ids),)).fetchall()}


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM picks WHERE model_id = %s AND signal_type = 'BET' "
        "AND game_id = ANY(%s)", (MODEL_ID, list(game_ids))).fetchall()}


def look(conn, now: datetime) -> dict:
    """One look, no write -> {"games", "bets", "diag", "decisions"}."""
    skipped: list[str] = []
    games = rule_card.slate(conn, now, skipped, horizon_min=WINDOW_MIN[1])
    if not games:
        return {"games": {}, "bets": [], "diag": dict.fromkeys(mk.DIAG_KEYS, 0), "decisions": []}
    ensure_decisions_table(conn)
    taken = games_with_a_bet(conn, sorted(games))
    decided = decided_games(conn, sorted(games))
    quotes = mk.load_quotes(conn, games, now, window=WINDOW_MIN, markets=MARKETS)
    in_window = {g: v for g, v in games.items()
                 if g not in taken and g not in decided and mk.in_window(v["tip"], now, WINDOW_MIN)}
    roster = rule_card.load_roster(conn, in_window) if in_window else mk.Roster([])
    bets, diag, decisions = mk.find_bets(quotes, games, roster, now, taken=taken, decided=decided,
                                         window=WINDOW_MIN, model_id=MODEL_ID, markets=MARKETS)
    return {"games": games, "bets": bets, "diag": diag, "decisions": decisions}


def publish(conn, rows: list[dict], decisions: list) -> dict:
    """Under the model's lock: re-read the ledger and the bets, then each new decision and its
    bets in ONE transaction; a decision's n_bets is the inserts that returned a row."""
    from scripts.nfl_wind_publisher import _lock_model
    out = {"decided": 0, "written": 0}
    if not decisions:
        return out
    _lock_model(conn, MODEL_ID)
    gids = sorted({d.game_id for d in decisions})
    skip = decided_games(conn, gids) | games_with_a_bet(conn, gids)
    for d in sorted(decisions, key=lambda x: x.game_id):
        if d.game_id in skip:
            continue
        mine = [r for r in rows if r["game_id"] == d.game_id]
        got = conn.execute(_INSERT_DECISION, {"game_id": d.game_id, "fetch_at": d.fetch_at,
                                              "n_quotes": d.n_quotes, "n_bets": len(mine),
                                              "detail": d.detail}).fetchone()
        if not got:
            continue
        out["decided"] += 1
        n = sum(1 for r in mine
                if conn.execute(rule_card._INSERT, {c: r[c] for c in rule_card._COLS}).fetchone())
        out["written"] += n
        if n != len(mine):
            conn.execute(f"UPDATE {DECISIONS_TABLE} SET n_bets = %s WHERE game_id = %s",
                         (n, d.game_id))
    conn.commit()
    return out


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        got = look(conn, now)
        logger.info("\n" + rule_card.render(got["bets"], got["diag"]).replace(
            rule_card.MODEL_ID, MODEL_ID, 1))
        result = {"games": len(got["games"]), "decisions": len(got["decisions"]),
                  "bets": len(got["bets"]), "published": 0}
        if do_publish and got["decisions"]:
            rows = []
            if got["bets"]:
                from models.scorer import _get_current_bankroll
                rows = rule_card.pick_rows(got["bets"], _get_current_bankroll(conn), model_id=MODEL_ID)
            w = publish(conn, rows, got["decisions"])
            result.update(published=w["written"], decided=w["decided"])
        return result
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
