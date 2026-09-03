"""
The live WNBA player-prop market card: de-vig Pinnacle, bet the soft outlier.

Deployment of models/wnba_prop_market (the NFL rule ported 2026-08-31 — see
that module's docstring for the why and the measured Pinnacle coverage). This
script is plumbing: load the slate's pre-tip quotes, call the shared selection
functions, print the card, publish picks. The split mirrors
scripts/nfl_prop_market_card.py exactly.

Deliberate and load-bearing, inherited unchanged:

  THE THRESHOLD IS PRE-COMMITTED AT 5pp — the NFL derivation's number (6pp
  chosen greedily went negative blind). It is not to be chased per-week, and a
  WNBA-specific re-derivation would be exactly the greedy selection the NFL
  work proved doesn't survive.

  SELECTION GOES THROUGH best_per_prop. The same proposition at three books is
  one opinion; publishing all three would stake it three times.

  INSERT-ONCE PER PROPOSITION (the opener lock, not delete-and-replace): the
  edge here is a disagreement the market corrects — re-pricing a locked pick at
  the corrected number would replace a bet that was taken with one that never
  existed.

WNBA-specific:
  * The blanket -140 prop price floor (config.MODEL_MIN_ODDS) applies.
  * player_id is resolved from wnba_player_game_log by normalized name so the
    wnba_player settle branch can grade the pick; a flag whose player cannot be
    resolved is SKIPPED AND LOGGED rather than published unsettleable.
  * PAPER-FIRST. Kill: no positive blind month at >= 50 flags → close the rule.

    python -m scripts.wnba_prop_market_card                    # today's card
    python -m scripts.wnba_prop_market_card --date 2026-08-30  # replay a day
    python -m scripts.wnba_prop_market_card --publish          # write picks
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import models.wnba_prop_market as mk  # noqa: E402
from config import MODEL_MIN_ODDS  # noqa: E402
from data.db import get_connection  # noqa: E402

MODEL_ID = "wnba_prop_market"
MIN_EDGE = 0.05                                    # pre-committed; see docstring
PRICE_FLOOR = MODEL_MIN_ODDS.get(MODEL_ID, -140)

_LABEL = {"player_points": "Pts", "player_rebounds": "Reb", "player_assists": "Ast"}
_BOOK = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM",
         "williamhill_us": "CZR", "espnbet": "ESPN", "pinnacle": "PIN"}


def norm_name(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z ]", "", s)
    return " ".join(p for p in s.split() if p not in {"jr", "sr", "ii", "iii", "iv"})


def slate(conn, game_date: str) -> dict[str, dict]:
    rows = conn.execute("""
        SELECT game_id, home_team, away_team, commence_time
        FROM games WHERE sport = 'WNBA' AND game_date = %s
    """, (game_date,)).fetchall()
    return {r[0]: {"home": r[1], "away": r[2], "commence_time": r[3]} for r in rows}


def player_ids(conn, season: int) -> dict[str, str]:
    """normalized name -> player_id, from the game log (settlement's id space)."""
    rows = conn.execute("""
        SELECT DISTINCT player_id, player_name FROM wnba_player_game_log
        WHERE season = %s
    """, (season,)).fetchall()
    return {norm_name(n): str(p) for p, n in rows}


def apply_price_floor(bets):
    """The blanket WNBA-prop floor: drop sides juicier than -140."""
    kept = [b for b in bets if b.price >= PRICE_FLOOR]
    dropped = len(bets) - len(kept)
    if dropped:
        logger.info(f"price floor {PRICE_FLOOR}: dropped {dropped} side(s)")
    return kept


def pick_rows(bets, games, quotes, pid_by_name, game_date: str,
              bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure given its inputs, so it is testable."""
    rows = []
    for b in bets:
        pid = pid_by_name.get(norm_name(b.player))
        if pid is None:
            # No game-log identity -> the wnba_player settle branch could never
            # grade it. Publishing would create a permanently-NULL pick (the
            # session-51 class), so skip loudly instead.
            logger.warning(f"cannot resolve player_id for {b.player!r} — flag skipped")
            continue
        g = games.get(b.game_id, {})
        side = "Over" if b.side == "over" else "Under"
        q = quotes.get((b.game_id, b.player, b.market, b.book), {})
        link = q.get("over_link") if b.side == "over" else q.get("under_link")
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": "WNBA",
            "game_date": game_date, "game_time": g.get("commence_time"),
            "pick_side": b.side,
            "pick_label": (f"{b.player} {side} {b.line:g} "
                           f"{_LABEL.get(b.market, b.market)} ({_BOOK.get(b.book, b.book)})"),
            # model_probability IS Pinnacle's de-vigged number; edge is vs the
            # soft book's own de-vigged prob — the exact quantities the NFL
            # rule validated on. dk_odds holds the SOFT book's price with the
            # book named in pick_label (the §28 precedent for rules that don't
            # score against DK).
            "model_probability": b.fair,
            "dk_implied_prob": b.fair - b.edge,
            "edge": b.edge,
            "dk_odds": b.price, "scored_line": b.line,
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "prop_market": b.market, "player_key": b.player,
            "player_id": pid,
            "dk_bet_link": link if b.book == "draftkings" else None,
        })
    return rows


_INSERT = """
    INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                       pick_side, pick_label, model_probability, dk_implied_prob,
                       edge, dk_odds, scored_line, kelly_fraction,
                       recommended_bet, bankroll_at_pick, signal_type,
                       confidence_tier, prop_market, player_key, player_id,
                       dk_bet_link)
    VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s, %(game_time)s,
            %(pick_side)s, %(pick_label)s, %(model_probability)s,
            %(dk_implied_prob)s, %(edge)s, %(dk_odds)s, %(scored_line)s,
            %(kelly_fraction)s, %(recommended_bet)s, %(bankroll_at_pick)s,
            %(signal_type)s, %(confidence_tier)s, %(prop_market)s,
            %(player_key)s, %(player_id)s, %(dk_bet_link)s)
"""


def publish(conn, rows: list[dict]) -> int:
    """Insert-once per (game, player, market, side) — the opener lock."""
    written = 0
    for r in rows:
        got = conn.execute("""
            SELECT 1 FROM picks
            WHERE game_id = %s AND model_id = %s AND player_key = %s
              AND prop_market = %s AND pick_side = %s
        """, (r["game_id"], r["model_id"], r["player_key"],
              r["prop_market"], r["pick_side"])).fetchone()
        if got:
            continue
        conn.execute(_INSERT, r)
        written += 1
    if written:
        conn.commit()
    return written


def render(bets, diag) -> str:
    lines = [f"WNBA prop market card — {len(bets)} flag(s)  "
             f"[sharp {diag['sharp_quotes']} · compared {diag['compared']} · "
             f"line-mismatch {diag['line_mismatch']} · no-sharp {diag['no_sharp']}]"]
    for b in sorted(bets, key=lambda x: -x.edge):
        side = "Over" if b.side == "over" else "Under"
        lines.append(f"  {b.player:24s} {side:5s} {b.line:4g} "
                     f"{_LABEL.get(b.market, b.market):3s} "
                     f"@{_BOOK.get(b.book, b.book):4s} {b.price:+.0f}  "
                     f"fair {b.fair:.3f}  edge {b.edge * 100:+.1f}pp  "
                     f"(PIN {b.sharp_price:+.0f})")
    return "\n".join(lines)


def run_card(game_date: str | None = None, do_publish: bool = False) -> dict:
    """The pipeline entry point (run_pipeline step + refresh pass)."""
    game_date = game_date or date.today().isoformat()
    conn = get_connection()
    try:
        games = slate(conn, game_date)
        if not games:
            logger.info(f"wnba-prop-market: no WNBA games {game_date}")
            return {"flags": 0, "published": 0}

        quotes = mk.load_wnba_prop_quotes(conn, game_date)
        bets, diag = mk.find_bets(quotes, min_edge=MIN_EDGE, soft_books=mk.SOFT_BOOKS)
        bets = apply_price_floor(mk.best_per_prop(bets))
        logger.info("\n" + render(bets, diag))

        published = 0
        if do_publish and bets:
            from models.scorer import _get_current_bankroll
            bankroll = _get_current_bankroll(conn)
            pid_by_name = player_ids(conn, int(game_date[:4]))
            published = publish(conn, pick_rows(bets, games, quotes, pid_by_name,
                                                game_date, bankroll))
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
