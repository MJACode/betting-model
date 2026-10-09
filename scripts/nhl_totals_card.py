"""NHL total goals card: write `nhl_over_under` bets (models/nhl_totals_market.py).

Runs on every refresh pass right after the odds fetch, and in the 6am daily run
right after its odds step, so the fetch it reads is the one just stored. It
prices every NHL game that has not started, with no date or lead horizon:
Pinnacle's own listing sets the window (it first hangs a total about 24 hours
before puck drop), and the prior-day quotes carry most of the evidence.

LIVE, with no default-off write switch (mike, 2026-10-08: "This is live
model"). The MLB cards' switches flipped off on a redeploy and those models
went dark without a trace (config.py, MLB_*_PUBLISH).

INSERT ONCE (CLAUDE.md 1c). A game's first qualifying fetch is the bet of
record. A later better price, a moved number or the other side all write
nothing. The check-then-insert runs under the model's transaction-scoped
advisory lock, because the 6am run and a refresh pass can overlap and the
picks unique index includes the side, so it would not stop an over plus an
under.

BET ROWS ONLY. The scorer deletes every model's unsettled non-BET rows on each
pass, so a "declined" row would not survive. The per-pass diagnostic line in
the worker log is how an empty card is told apart from a broken one.

ROW SHAPE: the scorer's convention for a pick decided away from DraftKings
(scripts/nhl_props_card.py). dk_odds / dk_implied_prob / edge are DraftKings'
own price at this number in this fetch, else NULL / 0.0 / 0.0; decision_* is
the book taken, always set; line_book names that book only when DraftKings did
not hang the number; best_* is set only when the bet is not at DraftKings.

    python -m scripts.nhl_totals_card              # print the card, write nothing
    python -m scripts.nhl_totals_card --publish    # write new bets
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.nhl_totals_market as mk
from data.db import get_connection
from models.market_relative import implied
from models.scorer import (
    _build_pick_label,
    _get_current_bankroll,
    _insert_picks,
    quarter_kelly,
)
from tracking.pick_integrity import pick_problems

MODEL_ID = mk.MODEL_ID
SPORT = "NHL"
MARKET = "totals"
_ET = ZoneInfo("America/New_York")


def slate(conn, now: datetime) -> dict[str, dict]:
    """Every NHL game whose start is after `now`. No horizon.

    The game_date bound only lets the query use the date: a game that starts
    after `now` cannot carry an ET date earlier than yesterday's. The started
    check is done on the parsed start time, because commence_time is TEXT in
    mixed shapes.
    """
    from features.feature_engine import _parse_iso_ts
    since = (now.astimezone(_ET).date() - timedelta(days=1)).isoformat()
    rows = conn.execute("""
        SELECT game_id, home_team, away_team, commence_time, game_date
        FROM games
        WHERE sport = 'NHL'
          AND commence_time IS NOT NULL
          AND game_date >= %s
    """, (since,)).fetchall()
    out = {}
    for gid, home, away, commence, gd in rows:
        start = _parse_iso_ts(commence)
        if start is None or start <= now:
            continue
        out[gid] = {"home": home, "away": away,
                    "commence_time": commence, "game_date": str(gd)[:10]}
    return out


def pick_rows(bets, games: dict, bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure given its inputs, so it is testable."""
    from models.honest_ev import gate
    rows = []
    for b in bets:
        # The platform's EV gate on the model's own probability at the price
        # taken. With own-probability membership it agrees with find_bets.
        ev = gate(MODEL_ID, b.fair, b.price)
        if not ev.clears:
            logger.info(f"{MODEL_ID}: {ev.reason} - dropped {b.game_id} "
                        f"{b.side} @{b.book}")
            continue
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        line = float(b.line)
        label = _build_pick_label(b.side, home, away, MARKET, line)
        problems = pick_problems(label, b.side, line, MODEL_ID, home, away)
        if problems:
            logger.error(f"{MODEL_ID}: refusing {b.game_id}: {'; '.join(problems)}")
            continue
        price = float(b.price)
        dec_implied = implied(price)
        dk = b.dk_price
        dk_implied = implied(dk) if dk is not None else None
        at_dk = b.book == mk.REFERENCE_BOOK
        kelly_frac, rec_bet = quarter_kelly(b.fair, dec_implied, bankroll)
        decision_edge = round(b.fair - dec_implied, 4)
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": b.side, "pick_label": label,
            # Pinnacle's no-vig probability of the side, in the same fetch.
            "model_probability": round(b.fair, 4),
            # DraftKings' own price at this number in this fetch, else the
            # NOT NULL placeholders.
            "dk_odds": dk,
            "dk_implied_prob": round(dk_implied, 4) if dk is not None else 0.0,
            "edge": round(b.fair - dk_implied, 4) if dk is not None else 0.0,
            "dk_bet_link": b.dk_link if dk is not None else None,
            "line_book": None if dk is not None else b.book,
            "scored_line": line,
            "kelly_fraction": kelly_frac,
            "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
            "confidence_tier": "MED" if decision_edge < 0.03 else "HIGH",
            "injury_flag": None,
            "injury_detail": None,
            # The price the bet was taken at. Always set: the scorer deletes an
            # unstarted BET with dk_odds and decision_odds both NULL.
            "decision_book": b.book,
            "decision_odds": price,
            "decision_implied_prob": round(dec_implied, 4),
            "decision_edge": decision_edge,
            "best_book": None if at_dk else b.book,
            "best_odds": None if at_dk else price,
            "best_implied_prob": None if at_dk else round(dec_implied, 4),
            "best_edge": None if at_dk else decision_edge,
            "best_bet_link": None if at_dk else b.link,
        })
    return rows


def publish(conn, rows: list[dict]) -> int:
    """Insert once per game, under the model's lock, in one transaction."""
    if not rows:
        return 0
    from scripts.nfl_wind_publisher import _lock_model
    _lock_model(conn, MODEL_ID)
    written = 0
    for r in rows:
        # Any BET on the game counts: the other side, a VOIDed or settled one.
        got = conn.execute("""
            SELECT 1 FROM picks
            WHERE game_id = %s AND model_id = %s AND signal_type = 'BET'
            LIMIT 1
        """, (r["game_id"], MODEL_ID)).fetchone()
        if got:
            continue
        _insert_picks(conn, [r])
        written += 1
    conn.commit()
    return written


def render(bets, diag: dict) -> str:
    counts = " ".join(f"{k}={diag.get(k, 0)}" for k in mk.DIAG_KEYS)
    lines = [f"NHL totals card ({MODEL_ID}): {counts}"]
    for b in sorted(bets, key=lambda x: -x.ev):
        lines.append(
            f"  {b.game_id:28s} {b.side:5s} {b.line:4.1f} @{b.book} "
            f"{b.price:+.0f}  fair {b.fair:.4f}  EV {b.ev:+.4f}  "
            f"(PIN {b.sharp_over:+.0f}/{b.sharp_under:+.0f}, fetch {b.created_at})")
    return "\n".join(lines)


def run_card(do_publish: bool = False, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    conn = get_connection()
    try:
        games = slate(conn, now)
        if not games:
            logger.info("NHL totals card: no unstarted NHL games")
            return {"games": 0, "bets": 0, "published": 0}
        quotes = mk.load_fetch_quotes(conn, games)
        bets, diag = mk.find_bets(quotes)
        logger.info("\n" + render(bets, diag))
        published = 0
        if do_publish and bets:
            bankroll = _get_current_bankroll(conn)
            rows = pick_rows(bets, games, bankroll)
            published = publish(conn, rows)
            logger.info(f"NHL totals card: {published} new bet(s) written "
                        f"of {len(bets)} on the card")
        return {"games": len(games), "bets": len(bets), "published": published}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(do_publish=a.publish))


if __name__ == "__main__":
    main()
