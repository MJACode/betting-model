"""Paper MLB totals public-fade card: fade OVER tickets ≥ cut, bet UNDER.

Deployment of models/mlb_total_public_fade. Mirrors scripts/mlb_game_market_card
(slate, insert-once, INSERT gated by env default 0).

Deliberate and load-bearing:

  NOT mlb_over_under and NOT mlb_total_market. Those ids stay paused /
  Pin-vs-soft respectively. This lane fades a public OVER pile.

  TICKET CUT IS ENV. MLB_TOTAL_PUBLIC_FADE_TICKET_PCT default 70; 80 is
  supported. The finder applies it. ACTION_THRESHOLDS min_edge is 0 so the
  action filter does not invent a second cut.

  INSERT-ONCE (§1c). Re-pricing a locked under after the ticket pile
  moves would replace a bet that was taken with one that never existed.

  MLB_TOTAL_PUBLIC_FADE_PUBLISH default 0. A pass with --publish still
  logs; it writes picks only when the env is 1.

    python -m scripts.mlb_total_public_fade_card
    python -m scripts.mlb_total_public_fade_card --date 2026-09-16 --publish
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import models.mlb_game_market as mk
import models.mlb_total_public_fade as fade
from models.market_relative import implied
from models.scorer import (
    _build_pick_label,
    _get_current_bankroll,
    _insert_picks,
)
from scripts.mlb_game_market_card import _BOOK, slate
from tracking.pick_integrity import pick_problems

MODEL_ID = fade.MODEL_ID
SPORT = fade.SPORT
MARKET = fade.MARKET

# Flat 1 unit. The backtest is flat-bet units; ticket% is not a calibrated
# probability, so Kelly on (tickets − 50) would invent a stake.
FLAT_UNIT_DOLLARS = 100.0


def pick_rows(bets, games, quotes, bankroll: float) -> list[dict]:
    """Fade bets -> picks rows. Pure given its inputs, so it is testable."""
    floor = config.min_odds_for(MODEL_ID)
    rows = []
    for b in bets:
        if floor is not None and b.price < floor:
            logger.info(f"price floor {floor}: dropped {b.game_id} under "
                        f"@{b.book} {b.price:+.0f}")
            continue
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        label = _build_pick_label(fade.SIDE, home, away, MARKET, b.line)
        book_tag = _BOOK.get(b.book, b.book)
        if not label.endswith(f"({book_tag})"):
            label = f"{label} ({book_tag})"
        problems = pick_problems(label, fade.SIDE, b.line, MODEL_ID, home, away)
        if problems:
            logger.error(f"refusing {b.game_id}: {'; '.join(problems)}")
            continue
        under_imp = implied(b.price)
        if under_imp is None:
            logger.info(f"unimplied under {b.price}: dropped {b.game_id}")
            continue
        # Stored edge is public OVER share above 50pp, NOT model − implied.
        # Ticket 70 → 0.20. Documented in docs/mlb_total_public_fade.md.
        public_lean = round((b.over_ticket_pct - 50.0) / 100.0, 4)
        q = quotes.get((b.game_id, b.book), {})
        link = q.get("under_link")
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": fade.SIDE, "pick_label": label,
            "model_probability": round(under_imp, 4),
            "dk_implied_prob": round(under_imp, 4),
            "edge": public_lean,
            "dk_odds": b.price, "scored_line": b.line,
            "kelly_fraction": 0.0,
            "recommended_bet": FLAT_UNIT_DOLLARS,
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
            "confidence_tier": "HIGH" if b.over_ticket_pct >= 80 else "MED",
            "injury_flag": None,
            "injury_detail": None,
            "decision_book": b.book,
            "decision_odds": b.price,
            "decision_implied_prob": round(under_imp, 4),
            "decision_edge": public_lean,
            "best_book": b.book,
            "best_odds": b.price,
            "best_implied_prob": round(under_imp, 4),
            "best_edge": public_lean,
            "line_book": b.book,
            "dk_bet_link": link if b.book == "draftkings" else None,
            "best_bet_link": link,
            "public_bet_pct": round(100.0 - b.over_ticket_pct, 1),
            "public_money_pct": None,
        })
    return rows


def publish(conn, rows: list[dict]) -> int:
    """Insert-once per game. A later tick must not replace the locked bet."""
    keep = []
    for r in rows:
        got = conn.execute("""
            SELECT 1 FROM picks
            WHERE game_id = %s AND model_id = %s
        """, (r["game_id"], MODEL_ID)).fetchone()
        if got:
            continue
        keep.append(r)
    if not keep:
        return 0
    _insert_picks(conn, keep)
    conn.commit()
    return len(keep)


def render(bets, diag) -> str:
    lines = [f"MLB totals public-fade card — {len(bets)} flag(s)  "
             f"[cut {fade.ticket_threshold():.0f}tix · "
             f"below {diag.get('below_cut', 0)} · "
             f"no-DK {diag.get('no_dk', 0)} · "
             f"line-out {diag.get('line_out', 0)} · "
             f"no-price {diag.get('no_price', 0)}]"]
    for b in sorted(bets, key=lambda x: -x.over_ticket_pct):
        lines.append(
            f"  {b.game_id:28s} under {b.line:.1f}  "
            f"@{_BOOK.get(b.book, b.book):4s} {b.price:+.0f}  "
            f"over tix {b.over_ticket_pct:.1f}"
        )
    return "\n".join(lines)


def run_card(game_date: str | None = None, do_publish: bool = False) -> dict:
    from data.db import get_connection

    game_date = game_date or config.today_et().isoformat()
    conn = get_connection()
    try:
        games = slate(conn, game_date)
        if not games:
            logger.info(f"mlb total public fade: no MLB games on {game_date}")
            return {"flags": 0, "published": 0,
                    "publish_enabled": fade.publish_enabled()}
        gids = list(games)
        quotes = mk.load_latest_quotes(conn, SPORT, MARKET, gids)
        splits = fade.load_public_over_splits(conn, gids)
        bets, diag = fade.find_fade_bets(
            splits, quotes, min_over_tickets=fade.ticket_threshold())
        logger.info("\n" + render(bets, diag))
        published = 0
        will_insert = bool(do_publish) and fade.publish_enabled()
        if do_publish and not will_insert:
            logger.info(
                f"mlb total public fade: {len(bets)} flag(s) logged, INSERT "
                f"gated off (set MLB_TOTAL_PUBLIC_FADE_PUBLISH=1 to write picks)")
        if will_insert and bets:
            bankroll = _get_current_bankroll(conn)
            rows = pick_rows(bets, games, quotes, bankroll)
            published = publish(conn, rows)
            logger.info(f"published {published} new pick(s) of {len(bets)} flagged")
        return {"flags": len(bets), "published": published,
                "publish_enabled": fade.publish_enabled()}
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--date", default=None)
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    run_card(a.date, do_publish=a.publish)


if __name__ == "__main__":
    main()
