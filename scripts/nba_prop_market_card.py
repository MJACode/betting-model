"""NBA prop card: write `nba_prop_market` bets (models/nba_prop_market.py).

Runs on every refresh pass right after the prop fetch (`par nba-prop-odds`),
and in the 6am daily run right after its NBA prop step, so the fetch it reads
is the one just stored. It decides only games whose tip is 45-70 minutes away;
every other game is counted in the diagnostic line and left alone.

LIVE, with no default-off write switch: the MLB cards' switches flipped off on
a redeploy and those models went dark without a trace (config.py,
MLB_*_PUBLISH).

INSERT ONCE PER GAME (CLAUDE.md 1c). A game's first qualifying pass is the bet
of record. A later better price, a moved line or another player writes
nothing: a game that already holds an nba_prop_market BET is never decided
again. The check, the caps and the insert run under the model's
transaction-scoped advisory lock (the one the NHL cards and the NFL rules
take), because the 6am run and a refresh pass can overlap, and the caps are
counted INSIDE the lock so two writers cannot both see three and both write a
fourth.

ONE A GAME, FOUR A NIGHT (models/nba_prop_market.MAX_BETS_PER_GAME /
MAX_BETS_PER_NIGHT, with the measured basis). The night is the game's ET date
and the BETs already written that night count against it. Games reaching
their window in the same pass are taken in tip order, then by EV -- the order
the backtest graded (first four games of the night by tip), so the card bets
exactly the population that was measured.

BET ROWS ONLY. The scorer deletes every model's unsettled non-BET rows on each
pass, so a "declined" row would not survive. The per-pass diagnostic line in
the worker log is how an empty card is told apart from a broken one.

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

    python -m scripts.nba_prop_market_card              # print the card, write nothing
    python -m scripts.nba_prop_market_card --publish    # write new bets
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nba_prop_market as mk  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.market_relative import implied  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

MODEL_ID = mk.MODEL_ID
SPORT = mk.SPORT
_ET = ZoneInfo("America/New_York")


# ── reads ─────────────────────────────────────────────────────────────────────

def slate(conn, now: datetime, skipped: list | None = None) -> dict[str, dict]:
    """REGULAR-SEASON NBA games that have not tipped and tip within the
    decision window's far end.

    The tip is the earlier of nba_schedule's and games' start
    (models.nba_prop_market.tip_of). The game_date bound only lets the query
    use the date: a game tipping in the next 70 minutes cannot carry an ET
    date before yesterday or after tomorrow.

    Regular season only, because that is the population the rule was graded
    on (1,230 games a season, 2023-24..2025-26). A game nba_schedule does not
    list as 'regular' -- the NBA Cup final, play-in, playoffs, or a game the
    schedule does not know -- is skipped and named in `skipped`.
    """
    today = now.astimezone(_ET).date()
    dates = [(today + timedelta(days=d)).isoformat() for d in (-1, 0, 1)]
    rows = conn.execute("""
        SELECT g.game_id, g.home_team, g.away_team, g.game_date, g.season,
               g.commence_time, s.commence_time, s.game_type
        FROM games g
        LEFT JOIN nba_schedule s ON s.game_id = g.game_id
        WHERE g.sport = 'NBA' AND g.game_date = ANY(%s)
    """, (dates,)).fetchall()
    out = {}
    horizon = now + timedelta(minutes=mk.DECISION_WINDOW_MIN[1])
    for gid, home, away, gd, season, g_ct, s_ct, game_type in rows:
        tip = mk.tip_of(s_ct, g_ct)
        if tip is None or tip <= now or tip > horizon:
            continue
        if game_type != "regular":
            if skipped is not None:
                skipped.append(f"{gid} ({game_type or 'not in nba_schedule'})")
            continue
        out[gid] = {"home": home, "away": away, "game_date": str(gd)[:10],
                    "season": int(season) if season is not None else None, "tip": tip}
    return out


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


def bets_by_night(conn, game_dates: list[str]) -> dict[str, int]:
    """nba_prop_market BETs already written for each game_date (the ET night)."""
    if not game_dates:
        return {}
    return {str(d)[:10]: int(n) for d, n in conn.execute("""
        SELECT game_date, count(*) FROM picks
        WHERE model_id = %s AND signal_type = 'BET' AND game_date = ANY(%s)
        GROUP BY game_date
    """, (MODEL_ID, list(game_dates))).fetchall()}


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


def _rank(r: dict) -> tuple:
    """Inside one game: the best EV."""
    return (-r["_ev"], r["_tip"], r["game_id"], str(r["player_id"]))


def _night_rank(r: dict) -> tuple:
    """Across a night: tip order, then EV -- the backtest's order (first four
    games of the night by tip; 1,862 bets, +5.05%)."""
    return (r["_tip"], -r["_ev"], r["game_id"], str(r["player_id"]))


def one_per_game(rows: list[dict], taken: set[str] | None = None) -> list[dict]:
    """The best-EV row in each game, none for a game already bet. Pure."""
    taken = taken or set()
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=_rank):
        if r["game_id"] in taken:
            continue
        n = left.setdefault(r["game_id"], mk.MAX_BETS_PER_GAME)
        if n <= 0:
            continue
        left[r["game_id"]] = n - 1
        kept.append(r)
    return kept


def per_night(rows: list[dict], written: dict[str, int] | None = None) -> list[dict]:
    """At most MAX_BETS_PER_NIGHT a game_date, the BETs already written counted.

    Rows are taken in tip order, then EV. Called once per pass, so across passes
    it is first come: a later pass only fills what is left of the night.
    """
    written = written or {}
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=_night_rank):
        d = str(r["game_date"])[:10]
        n = left.setdefault(d, mk.MAX_BETS_PER_NIGHT - written.get(d, 0))
        if n <= 0:
            continue
        left[d] = n - 1
        kept.append(r)
    return kept


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


def publish(conn, rows: list[dict]) -> int:
    """Insert once per game, under the model's lock, caps counted inside it."""
    if not rows:
        return 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    taken = games_with_a_bet(conn, sorted({r["game_id"] for r in rows}))
    written = bets_by_night(conn, sorted({str(r["game_date"])[:10] for r in rows}))
    chosen = per_night(one_per_game(rows, taken), written)
    n = 0
    for r in chosen:
        got = conn.execute(_INSERT, {c: r[c] for c in _COLS}).fetchone()
        if got:
            n += 1
    conn.commit()
    logger.info(f"nba-prop-market: {n} bet(s) written of {len(rows)} on the card "
                f"(one a game, {mk.MAX_BETS_PER_NIGHT} a night; {len(taken)} game(s) "
                f"already bet; already written by night {written})")
    return n


# ── the pass ──────────────────────────────────────────────────────────────────

def render(bets, diag: dict, written: int | None = None) -> str:
    counts = " ".join(f"{k}={diag.get(k, 0)}" for k in mk.DIAG_KEYS)
    head = f"NBA prop card ({MODEL_ID}): {counts}"
    if written is not None:
        head += f" written={written}"
    lines = [head]
    for b in sorted(bets, key=lambda x: -x.ev):
        lines.append(
            f"  {b.game_id:26s} {b.player} Under {b.line:g} {mk.MARKET_LABEL[b.market]} "
            f"@{b.book} {b.price:+.0f}  fair {b.fair:.4f}  EV {b.ev:+.4f}  "
            f"(PIN {b.sharp_over:+.0f}/{b.sharp_under:+.0f}, fetch {b.fetch})")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        skipped: list[str] = []
        games = slate(conn, now, skipped)
        if skipped:
            logger.info(f"nba-prop-market: not a regular-season game, not priced: {skipped}")
        if not games:
            diag = dict.fromkeys(mk.DIAG_KEYS, 0)
            logger.info(render([], diag, 0 if do_publish else None)
                        + " (no NBA game tips in the next "
                        f"{mk.DECISION_WINDOW_MIN[1]} minutes)")
            return {"games": 0, "bets": 0, "published": 0, "diag": diag}
        taken = games_with_a_bet(conn, sorted(games))
        quotes = mk.load_quotes(conn, games, now)
        in_window = {g: v for g, v in games.items()
                     if g not in taken and mk.in_window(v["tip"], now)}
        roster = load_roster(conn, in_window) if in_window else mk.Roster([])
        bets, diag = mk.find_bets(quotes, games, roster, now, taken=taken)
        for gid, g in sorted(games.items()):
            lead = mk.minutes_to_tip(g["tip"], now)
            if gid in taken or lead >= mk.DECISION_WINDOW_MIN[0]:
                continue
            rows = [q for q in quotes if q["game_id"] == gid]
            if not mk.window_was_fetched(mk._pre_tip(rows, g["tip"], now), g["tip"]):
                # Widen nothing (the window is the evidence). Say it, so a
                # cadence that cannot reach a tip time is visible.
                logger.warning(
                    f"nba-prop-market: {gid} tips at {g['tip'].isoformat()} ({lead:.0f} min) "
                    f"and no prop fetch landed {mk.DECISION_WINDOW_MIN[0]}-"
                    f"{mk.DECISION_WINDOW_MIN[1]} min before it: no pass could decide it")
        published = 0
        if do_publish and bets:
            from models.scorer import _get_current_bankroll
            rows = pick_rows(bets, _get_current_bankroll(conn))
            published = publish(conn, rows)
        logger.info("\n" + render(bets, diag, published if do_publish else None))
        return {"games": len(games), "bets": len(bets), "published": published, "diag": diag}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
