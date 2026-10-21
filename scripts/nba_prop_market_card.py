"""NBA prop card: write `nba_prop_market` bets (models/nba_prop_market.py).

Runs on every refresh pass right after the prop fetch (`par nba-prop-odds`),
in the 6am daily run right after its NBA prop step, and on the five-minute
window job right after that job's fetch of the games about to enter their
window (scheduler.run_nba_prop_window), so the fetch it reads is the one just
stored. It decides only games whose tip is 45-57 minutes away; every other
game is counted in the diagnostic line and left alone.

LIVE, with no default-off write switch: the MLB cards' switches flipped off on
a redeploy and those models went dark without a trace (config.py,
MLB_*_PUBLISH).

EACH GAME DECIDED ONCE (CLAUDE.md 1c, and fidelity to the backtest, which
looked at every game once). The first look inside the window whose newest
fetch holds Pinnacle for a game IS that game's decision, whether or not any
proposition qualified, and it is written to nba_prop_market_decisions in the
same transaction as the game's bets. A game with a decision row is never
looked at again, so a later better price, a moved line or another player
writes nothing. A game that already holds an nba_prop_market BET is never
decided again either (the insert-once guard this card shipped with). The
reads and the inserts run under the model's transaction-scoped advisory lock
(the one the NHL cards and the NFL rules take), because the 6am run, a refresh
pass and the window job can overlap; the ledger and the picks are re-read
INSIDE the lock so two writers cannot both decide one game.

ONE NBA PROP BET A GAME, ACROSS BOTH NBA PROP MODELS, AND A FEW A NIGHT
(mike, 2026-10-20, after opening night wrote 36 bets on one game: "Only the
strongest picks need to be sent, like NHL"). This card no longer writes
anything itself: it finds every qualifying proposition (look()), and
scripts/nba_props_card.publish_across_models -- the only door an NBA prop pick
goes through -- pools them with nba_prop_projection's, keeps the best EV in
each game and the best few of the night, and writes this card's decision rows
with them. The 2026-10-16 "no game or night cap" rule is replaced.

BET ROWS ONLY in picks. The scorer deletes every model's unsettled non-BET rows
on each pass, so a "declined" row would not survive there. A decision with no
bet lives in the ledger; the per-look diagnostic line in the worker log is how
an empty card is told apart from a broken one.

ROW SHAPE: the scorer's convention for a pick decided away from DraftKings
(scripts/nhl_props_card.py). dk_odds / dk_implied_prob / edge / dk_bet_link
are DraftKings' OWN under at this line in this fetch, else NULL / 0.0 / 0.0 /
NULL; decision_* is the book taken, always set (the scorer deletes an
unstarted BET with dk_odds and decision_odds both NULL); line_book names that
book only when DraftKings did not hang the number; best_* is set only when the
bet is not at DraftKings. pick_label and player_key carry the BET book's own
spelling of the player, because closing-line value reads that book's close by
that name (tracking/paper_tracker._capture_clv). kelly_fraction is the NHL
prop cards' flat 0.01.

    python -m scripts.nba_prop_market_card              # print the card, write no pick or decision
    python -m scripts.nba_prop_market_card --publish    # both NBA prop cards through the shared door
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_prop_market as mk  # noqa: E402
import scripts.nba_total_luck_card as tlcard  # noqa: E402
from data.anon_readable import API_ROLES, lock_down  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = mk.MODEL_ID
SPORT = mk.SPORT

# ── the decisions ledger ──────────────────────────────────────────────────────
# One row per game the card has decided (models/nba_prop_market, DECIDED ONCE).
# Worker-only (data/anon_readable.WORKER_ONLY_TABLES): the app never reads it.
DECISIONS_TABLE = "nba_prop_market_decisions"
DECISIONS_COLS = ("game_id", "decided_at", "fetch_at", "n_quotes", "n_bets", "detail")
DECISIONS_DDL = """
CREATE TABLE IF NOT EXISTS nba_prop_market_decisions (
    game_id     TEXT PRIMARY KEY,
    decided_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    fetch_at    TEXT NOT NULL,
    n_quotes    INTEGER NOT NULL,
    n_bets      INTEGER NOT NULL,
    detail      TEXT
)
"""
_INSERT_DECISION = (
    "INSERT INTO nba_prop_market_decisions (game_id, fetch_at, n_quotes, n_bets, detail) "
    "VALUES (%(game_id)s, %(fetch_at)s, %(n_quotes)s, %(n_bets)s, %(detail)s) "
    "ON CONFLICT (game_id) DO NOTHING RETURNING game_id")


def ensure_decisions_table(conn) -> None:
    """Create the ledger once, locked down, and cost nothing after that.

    Behind data/ddl_guard.schema_is_current: a CREATE TABLE IF NOT EXISTS
    still fires Supabase's pgrst_ddl_watch and reloads PostgREST's schema
    cache for the whole app, and this runs on every look (every refresh pass
    and every five-minute window tick). Committed on its own, BEFORE the
    publish lock is taken: the guard rolls back a failed catalog probe, which
    would release a transaction-scoped lock already held.
    """
    if schema_is_current(conn, DECISIONS_TABLE, columns=DECISIONS_COLS,
                         rls=True, revoked_from=API_ROLES):
        return
    conn.execute(DECISIONS_DDL)
    lock_down(conn, "nba_prop_market_decisions")
    conn.commit()


# ── reads ─────────────────────────────────────────────────────────────────────

def slate(conn, now: datetime, skipped: list | None = None,
          horizon_min: int | None = None) -> dict[str, dict]:
    """REGULAR-SEASON NBA games that have not tipped and tip within the
    decision window's far end (or `horizon_min`, for the window job's look
    ahead). Both NBA prop models read this slate (the projection card and the
    five-minute window job call it too).

    The totals card's slate, read with this window
    (scripts.nba_total_luck_card.slate): the tip is the earlier of
    nba_schedule's and games' start (models.nba_prop_market.tip_of), and a
    game counts as regular season by models.nba_total_luck.regular_season --
    the schedule types it 'regular', or the schedule does not list it and it
    falls on a regular-season day. The second half is the NBA Cup week: the
    2026-27 schedule was loaded on 2026-10-15, before the league set it, so
    24 regular-season games were not in it and the knockout games were only
    placeholders, while the odds feed writes each into `games` as soon as it
    quotes it. The daily schedule refresh lists them once ESPN does
    (data/ingestors/nba_schedule_refresh.py); this keeps them priced on a day
    that refresh has failed. They are in the graded population: the props
    bought for 2023-24..2025-26 cover 1,230 regular-season games a season,
    the Cup quarterfinals and semifinals included.

    NOT the play-in, the playoffs or the NBA Cup final, on purpose. Neither
    prop model has been graded on one: the stored prop history holds 0 of
    those 272 games of 2023-24..2025-26 (18 play-in, 251 playoff, 3 Cup
    finals) against 3,690 of 3,690 regular-season games (player_prop_odds
    joined to nba_schedule by game type, production, 2026-10-20). Grading them
    means buying those props first (data/ingestors/nba_odds_history.py
    --props over the postseason dates). Each is skipped and named in
    `skipped`, as is a game the schedule does not list on a day that is not
    a regular-season day.
    """
    return tlcard.slate(conn, now, skipped,
                        horizon_min=horizon_min if horizon_min is not None
                        else mk.DECISION_WINDOW_MIN[1])


def load_roster(conn, games: dict[str, dict]) -> mk.Roster:
    """Everyone logged for tonight's teams this season or last (read by team)."""
    teams = sorted({t for g in games.values() for t in (g["home"], g["away"])})
    seasons = sorted({s for g in games.values() if g.get("season")
                      for s in (g["season"], g["season"] - 1)})
    if not teams or not seasons:
        return mk.Roster([])
    rows = conn.execute("""
        SELECT DISTINCT player_id, player_name, team FROM nba_player_game_log
        WHERE team = ANY(%s) AND season = ANY(%s) AND player_id IS NOT NULL
    """, (teams, seasons)).fetchall()
    return mk.Roster(rows)


def games_with_a_bet(conn, game_ids: list[str]) -> set[str]:
    """Games that already carry an nba_prop_market BET, whatever became of it
    (settled, VOIDed, the other side): none of them is decided again."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute("""
        SELECT DISTINCT game_id FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s)
    """, (MODEL_ID, list(game_ids))).fetchall()}


def decided_games(conn, game_ids: list[str]) -> set[str]:
    """Games that already have a decision row: none is looked at again."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT game_id FROM nba_prop_market_decisions WHERE game_id = ANY(%s)",
        (list(game_ids),)).fetchall()}


# ── rows ──────────────────────────────────────────────────────────────────────

def pick_label(bet: mk.NbaPropBet) -> str:
    return f"{bet.player} Under {bet.line:g} {mk.MARKET_LABEL[bet.market]}"


def pick_rows(bets: list[mk.NbaPropBet], bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure given its inputs, so it is testable."""
    rows = []
    for b in bets:
        label = pick_label(b)
        problems = pick_problems(label, mk.SIDE, b.line, MODEL_ID,
                                 prop_market=b.market)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id} {label!r}: {'; '.join(problems)}")
            continue
        price = float(b.price)
        dec_implied = implied(price)
        decision_edge = round(b.fair - dec_implied, 4)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == mk.REFERENCE_BOOK
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": b.game_date, "game_time": b.tip,
            "pick_side": mk.SIDE, "pick_label": label,
            # Pinnacle's proportional no-vig under, same line, same fetch. It IS
            # the model's own probability (config.MODELS_ON_OWN_PROBABILITY).
            "model_probability": round(b.fair, 4),
            "model_probability_cal": round(b.fair, 4),
            # DraftKings' own under at this line in this fetch, else the NOT
            # NULL placeholders.
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.fair - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": b.line,
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "prop_market": b.market, "player_key": b.player,
            "player_id": str(b.player_id),
            "decision_book": b.book, "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4),
            "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
            "_ev": round(b.ev, 4), "_tip": b.tip,
        })
    return rows


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds",
         "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type",
         "confidence_tier", "prop_market", "player_key", "player_id", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link")
# Its own column list, NOT models.scorer._insert_picks: that one names neither
# prop_market nor player_key, so both would be dropped silently and the pick
# could neither settle (FROM_PROP_MARKET) nor be found by the CLV capture.
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)}) "
           f"ON CONFLICT DO NOTHING RETURNING pick_id")


# ── the pass ──────────────────────────────────────────────────────────────────

def render(bets, diag: dict, written: int | None = None,
           decisions_written: int | None = None) -> str:
    counts = " ".join(f"{k}={diag.get(k, 0)}" for k in mk.DIAG_KEYS)
    head = f"NBA prop card ({MODEL_ID}): {counts}"
    if decisions_written is not None:
        head += f" decisions_written={decisions_written}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in sorted(bets, key=lambda x: -x.ev):
        lines.append(
            f"  {b.game_id:26s} {b.player} Under {b.line:g} {mk.MARKET_LABEL[b.market]} "
            f"@{b.book} {b.price:+.0f}  fair {b.fair:.4f}  EV {b.ev:+.4f}  "
            f"(PIN {b.sharp_over:+.0f}/{b.sharp_under:+.0f}, fetch {b.fetch})")
    return "\n".join(lines)


def look(conn, now: datetime) -> dict:
    """One look, no write: the games in reach, every qualifying proposition and the games this
    look decides. -> {"games", "bets", "diag", "decisions"}."""
    skipped: list[str] = []
    games = slate(conn, now, skipped)
    if skipped:
        logger.info(f"nba-prop-market: not a regular-season game, not priced: {skipped}")
    if not games:
        return {"games": {}, "bets": [], "diag": dict.fromkeys(mk.DIAG_KEYS, 0), "decisions": []}
    ensure_decisions_table(conn)
    taken = games_with_a_bet(conn, sorted(games))
    decided = decided_games(conn, sorted(games))
    quotes = mk.load_quotes(conn, games, now)
    in_window = {g: v for g, v in games.items()
                 if g not in taken and g not in decided and mk.in_window(v["tip"], now)}
    roster = load_roster(conn, in_window) if in_window else mk.Roster([])
    bets, diag, decisions = mk.find_bets(quotes, games, roster, now, taken=taken,
                                         decided=decided)
    for gid, g in sorted(games.items()):
        lead = mk.minutes_to_tip(g["tip"], now)
        if gid in taken or gid in decided or lead >= mk.DECISION_WINDOW_MIN[0]:
            continue
        rows = [q for q in quotes if q["game_id"] == gid]
        if not mk.window_was_fetched(mk._pre_tip(rows, g["tip"], now), g["tip"]):
            # Widen nothing (the window is the evidence). Say it, so a
            # cadence that cannot reach a tip time is visible.
            logger.warning(
                f"nba-prop-market: {gid} tips at {g['tip'].isoformat()} ({lead:.0f} min) "
                f"and no prop fetch landed {mk.DECISION_WINDOW_MIN[0]}-"
                f"{mk.DECISION_WINDOW_MIN[1]} min before it: no pass could decide it")
    return {"games": games, "bets": bets, "diag": diag, "decisions": decisions}


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    """Print this model's card. Publishing runs BOTH NBA prop cards through the shared door
    (scripts/nba_props_card.run_cards): one model alone must never write, or the card that
    happened to run first would win the game's one bet."""
    now = now or datetime.now(timezone.utc)
    if do_publish:
        from scripts.nba_props_card import run_cards
        return run_cards(do_publish=True, now=now)
    conn = get_connection()
    try:
        got = look(conn, now)
        logger.info("\n" + render(got["bets"], got["diag"]))
        return {"games": len(got["games"]), "bets": len(got["bets"]), "published": 0,
                "decided": 0, "diag": got["diag"]}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
