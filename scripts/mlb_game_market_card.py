"""Live MLB run-line card: de-vig Pinnacle, bet the bettable soft outlier.

Deployment of models/mlb_game_market (the NFL prop-market rule pointed at
MLB spreads). This script is plumbing: load today's unstarted games, take
the latest pre-game quotes, call find_spread_bets, print the card, publish
insert-once picks under model_id `mlb_spread_market`.

Deliberate and load-bearing:

  THE THRESHOLD IS 1.8pp. Measured 2026-09-15 on the 2026 season against
  BEST_LINE_BOOKMAKERS (docs/mlb_runline_ou_edge_search.md). 2.0pp is a
  peak that fails the early half. Do not chase it.

  ONE BET PER GAME. The same game at three books is one opinion.

  INSERT-ONCE (§1c). The edge is a disagreement the market corrects —
  re-pricing a locked pick at the corrected number would replace a bet
  that was taken with one that never existed.

  TOTALS ARE NOT PUBLISHED. The same construction is negative at every
  threshold on 2026 MLB totals.

    python -m scripts.mlb_game_market_card
    python -m scripts.mlb_game_market_card --date 2026-09-15 --publish
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path
import sys

from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
import models.mlb_game_market as mk
from data.db import get_connection
from models.scorer import (
    _build_pick_label,
    _get_current_bankroll,
    _get_public_betting,
    _insert_picks,
    quarter_kelly,
)
from tracking.pick_integrity import pick_problems

MODEL_ID = "mlb_spread_market"
MIN_EDGE = mk.MIN_EDGE_SPREADS
SPORT = "MLB"
MARKET = "spreads"

_BOOK = {
    "draftkings": "DK", "fanduel": "FD", "betmgm": "MGM",
    "williamhill_us": "CZR", "betrivers": "BR", "hardrockbet": "HR",
    "fanatics": "FAN", "fliff": "FLIFF", "ballybet": "BAL",
    "betparx": "PARX", "rebet": "REBET",
}


def slate(conn, game_date: str) -> dict[str, dict]:
    """Unstarted MLB games on `game_date` (and the next calendar day, so a
    west-coast night slate still prices after midnight ET)."""
    nxt = (date.fromisoformat(game_date) + timedelta(days=1)).isoformat()
    rows = conn.execute("""
        SELECT game_id, home_team, away_team, commence_time, game_date
        FROM games
        WHERE sport = 'MLB'
          AND game_date IN (%s, %s)
          AND commence_time IS NOT NULL
    """, (game_date, nxt)).fetchall()
    out = {}
    for gid, home, away, commence, gd in rows:
        out[gid] = {
            "home": home, "away": away,
            "commence_time": commence, "game_date": str(gd)[:10],
        }
    return out


def pick_rows(bets, games, quotes, bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure given its inputs, so it is testable."""
    floor = config.min_odds_for(MODEL_ID)
    rows = []
    for b in bets:
        if floor is not None and b.price < floor:
            logger.info(f"price floor {floor}: dropped {b.game_id} {b.side} "
                        f"@{b.book} {b.price:+.0f}")
            continue
        g = games.get(b.game_id, {})
        home, away = g.get("home", ""), g.get("away", "")
        label = _build_pick_label(b.side, home, away, MARKET, b.line)
        book_tag = _BOOK.get(b.book, b.book)
        if not label.endswith(f"({book_tag})"):
            label = f"{label} ({book_tag})"
        problems = pick_problems(label, b.side, b.line, MODEL_ID, home, away)
        if problems:
            logger.error(f"refusing {b.game_id}: {'; '.join(problems)}")
            continue
        implied = b.fair - b.edge
        kelly_frac, rec_bet = quarter_kelly(b.fair, implied, bankroll)
        q = quotes.get((b.game_id, b.book), {})
        if b.side == "home":
            link = q.get("home_link")
        elif b.side == "away":
            link = q.get("away_link")
        elif b.side == "over":
            link = q.get("over_link")
        else:
            link = q.get("under_link")
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": SPORT,
            "game_date": g.get("game_date"),
            "game_time": g.get("commence_time"),
            "pick_side": b.side, "pick_label": label,
            # model_probability IS Pinnacle's de-vigged number; edge is vs
            # the soft book's own de-vigged prob — the quantities the cut
            # was measured on.
            "model_probability": round(b.fair, 4),
            "dk_implied_prob": round(implied, 4),
            "edge": round(b.edge, 4),
            "dk_odds": b.price, "scored_line": b.line,
            "kelly_fraction": kelly_frac,
            "recommended_bet": rec_bet,
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
            "confidence_tier": "MED" if b.edge < 0.03 else "HIGH",
            "injury_flag": None,
            "injury_detail": None,
            "decision_book": b.book,
            "decision_odds": b.price,
            "decision_implied_prob": round(implied, 4),
            "decision_edge": round(b.edge, 4),
            "best_book": b.book,
            "best_odds": b.price,
            "best_implied_prob": round(implied, 4),
            "best_edge": round(b.edge, 4),
            "line_book": b.book,
            "dk_bet_link": link if b.book == "draftkings" else None,
            "best_bet_link": link,
            "_quote_snapshot_at": b.snap,
        })
    return rows


def _stamp_public(conn, rows: list[dict]) -> None:
    for r in rows:
        try:
            r.update(_get_public_betting(conn, r["game_id"], MARKET,
                                         r["pick_side"]))
        except Exception:  # noqa: BLE001 — display-only
            pass


def _shadow_gate(conn, rows: list[dict], quotes: dict, games: dict) -> None:
    """Persist CLEAR vs PASS_* without changing signal_type.

    The 1.8pp Pinnacle-soft disagreement IS the measured edge. Applying
    PASS_STEAMED / PASS_PUBLIC_STEAM live here would veto a cut that has
    not been re-measured under that overlay. Shadow so the next assessment
    can split the record. Fail-open.
    """
    if not rows:
        return
    try:
        from models import game_market_gate as gmg
    except Exception:  # noqa: BLE001
        return
    for r in rows:
        q = quotes.get((r["game_id"], r.get("decision_book")))
        g = games.get(r["game_id"], {})
        as_of = r.get("_quote_snapshot_at")
        opening = gmg.load_opening_odds(
            conn, r["game_id"], MARKET, as_of,
            commence=g.get("commence_time"), book=r.get("decision_book") or "draftkings",
        )
        gmg.apply_to_picks(
            [r], market=MARKET, current_odds=q, opening_odds=opening,
            mode="shadow", min_no_vig_edge=None,
            enabled_models={MODEL_ID},
        )
    try:
        gmg.persist(conn, rows, mode="shadow")
    except Exception:  # noqa: BLE001 — table missing
        pass
    for r in rows:
        r.pop("_market_gate", None)
        r.pop("_market_as_of", None)
        r.pop("_quote_snapshot_at", None)


def publish(conn, rows: list[dict]) -> int:
    """Insert-once per game. A later tick must not replace the locked bet."""
    written = 0
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
    written = len(keep)
    return written


def render(bets, diag) -> str:
    lines = [f"MLB spread market card — {len(bets)} flag(s)  "
             f"[sharp compared {diag.get('compared', 0)} · "
             f"mismatch {diag.get('line_mismatch', 0)} · "
             f"no-sharp {diag.get('no_sharp', 0)} · "
             f"gap {diag.get('not_simultaneous', 0)}]"]
    for b in sorted(bets, key=lambda x: -x.edge):
        lines.append(
            f"  {b.game_id:28s} {b.side:4s} {b.line:+.1f}  "
            f"@{_BOOK.get(b.book, b.book):4s} {b.price:+.0f}  "
            f"fair {b.fair:.3f}  edge {b.edge * 100:+.1f}pp  "
            f"(PIN {b.sharp_price:+.0f})"
        )
    return "\n".join(lines)


def run_card(game_date: str | None = None, do_publish: bool = False) -> dict:
    game_date = game_date or config.today_et().isoformat()
    conn = get_connection()
    try:
        games = slate(conn, game_date)
        if not games:
            logger.info(f"mlb spread market: no MLB games on {game_date}")
            return {"flags": 0, "published": 0}
        quotes = mk.load_latest_quotes(conn, SPORT, MARKET, list(games))
        bets, diag = mk.find_spread_bets(quotes, min_edge=MIN_EDGE)
        logger.info("\n" + render(bets, diag))
        published = 0
        if do_publish and bets:
            bankroll = _get_current_bankroll(conn)
            rows = pick_rows(bets, games, quotes, bankroll)
            _stamp_public(conn, rows)
            _shadow_gate(conn, rows, quotes, games)
            published = publish(conn, rows)
            logger.info(f"published {published} new pick(s) of {len(bets)} flagged")
        return {"flags": len(bets), "published": published}
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
