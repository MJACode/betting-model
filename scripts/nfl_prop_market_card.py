"""
The live NFL player-prop card: de-vig Pinnacle, bet the soft outlier.

This is the deployment of the rule measured in docs/nfl_props_model.md §5c
(954 bets, +10.33% ROI at a 5pp threshold, positive in all three seasons, and
reproduced by no other reference book). The rule itself lives in
models/nfl_prop_market; this script is plumbing — fetch the board, call the
model, print the card — the same split as §28's wind and opener cards.

Two things are deliberate and load-bearing:

  THE THRESHOLD IS PRE-COMMITTED AT 5pp. Selecting it greedily on 2023-24 picks
  6pp, and 6pp applied blind to 2025 returns -0.46%. The tail overfits. 5pp
  replicated (+10.22% train, +10.76% blind), so it is the number and it is not
  to be chased from week to week.

  SELECTION GOES THROUGH models.nfl_prop_market.best_per_prop, the same call the
  backtest grades. The same prop offered at three books is one opinion; a card
  that listed all three would show a slate the measured ROI never described.

    python -m scripts.nfl_prop_market_card                 # upcoming slate
    python -m scripts.nfl_prop_market_card --fetch         # pull fresh prices first
    python -m scripts.nfl_prop_market_card --date 2025-09-07
"""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone

from loguru import logger

import models.nfl_prop_market as mk
from data.db import get_connection
from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_quotes
from models.nfl_prop_backtest import _as_dt

# The pre-committed threshold. See the module docstring before changing it.
MIN_EDGE = 0.05

SOFT_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet")

_LABEL = {
    "player_pass_yds": "Pass Yds", "player_pass_attempts": "Pass Att",
    "player_pass_completions": "Comp", "player_pass_tds": "Pass TD",
    "player_reception_yds": "Rec Yds", "player_receptions": "Rec",
    "player_rush_yds": "Rush Yds", "player_anytime_td": "Anytime TD",
}
_BOOK = {"draftkings": "DK", "fanduel": "FD", "betmgm": "MGM",
         "williamhill_us": "CZR", "espnbet": "ESPN", "pinnacle": "PIN"}


def slate(conn, start: str, end: str) -> dict[str, dict]:
    """{game_id: {kickoff, away, home}} for scheduled games in a window.

    From nfl_team_game_stats, not `games`: an NFL game only gets a `games` row
    when it carries a wind/opener pick, so `games` cannot see a normal slate.
    """
    rows = conn.execute("""
        SELECT game_id, commence_time, team, opponent, is_home, game_date
        FROM nfl_team_game_stats
        WHERE game_date BETWEEN %s AND %s AND commence_time IS NOT NULL
    """, (start, end)).fetchall()
    out: dict[str, dict] = {}
    for gid, ko, team, opp, is_home, gd in rows:
        ko = ko.isoformat() if hasattr(ko, "isoformat") else str(ko)
        d = out.setdefault(gid, {"kickoff": ko, "date": str(gd)})
        if is_home:
            d["home"], d["away"] = team, opp
        else:
            d["away"], d["home"] = team, opp
    return out


def card(conn, start: str, end: str,
         min_edge: float = MIN_EDGE) -> tuple[list, dict, dict]:
    games = slate(conn, start, end)
    if not games:
        return [], {"reason": "no scheduled games in window"}, {}

    now = datetime.now(timezone.utc)
    live = {g for g, d in games.items()
            if (_as_dt(d["kickoff"]) or now) <= now}
    open_games = [g for g in games if g not in live]
    if not open_games:
        return [], {"reason": "every game in window has kicked off"}, {}

    quotes = load_nfl_prop_quotes(conn, open_games, list(mk.SHARP_MARKETS))
    bets, diag = mk.find_bets(quotes, min_edge=min_edge, soft_books=SOFT_BOOKS)
    diag["games"] = len(open_games)
    diag["started_skipped"] = len(live)
    # Bets key on the NORMALISED name (that is the join to nflverse); the card
    # is read by a person, so carry the book's own spelling back for display.
    names = {k[1]: v.get("player_name") or k[1] for k, v in quotes.items()}
    return mk.best_per_prop(bets), diag, names


def render(bets, diag, games, names=None) -> str:
    lines = [
        f"NFL prop card — sharp {mk.SHARP_BOOK} | min edge {MIN_EDGE:.0%}",
        f"{diag.get('games', 0)} open games | {diag.get('sharp_quotes', 0)} sharp quotes | "
        f"{diag.get('compared', 0)} compared | {len(bets)} bets",
    ]
    if diag.get("line_mismatch"):
        # Not decoration: if most soft quotes sit on a different number than the
        # sharp book, a thin card is about coverage, not about a quiet market.
        lines.append(f"({diag['line_mismatch']} soft quotes dropped on line mismatch)")
    if not bets:
        lines.append(f"\nNo qualifying edges. {diag.get('reason', '')}".rstrip())
        return "\n".join(lines)

    lines.append("")
    lines.append(f"{'matchup':<12}{'player':<22}{'market':<11}{'bet':<16}"
                 f"{'book':<6}{'price':>7}{'fair':>7}{'edge':>7}")
    for b in bets:
        g = games.get(b.game_id, {})
        matchup = f"{g.get('away','?')}@{g.get('home','?')}"
        side = "Over" if b.side == "over" else "Under"
        mkt = _LABEL.get(b.market, b.market)
        bet = (f"{side} {b.line:g}" if b.market != "player_anytime_td" else "Yes")
        price = f"+{int(b.price)}" if b.price > 0 else f"{int(b.price)}"
        who = (names or {}).get(b.player, b.player)
        lines.append(f"{matchup:<12}{who[:21]:<22}{mkt:<11}{bet:<16}"
                     f"{_BOOK.get(b.book, b.book):<6}{price:>7}"
                     f"{b.fair:>6.1%}{b.edge:>7.1%}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--date", help="anchor date (default today UTC)")
    ap.add_argument("--min-edge", type=float, default=MIN_EDGE)
    ap.add_argument("--fetch", action="store_true",
                    help="pull fresh prices before building the card (costs credits)")
    a = ap.parse_args()

    if a.fetch:
        from data.ingestors.nfl_prop_odds_ingestor import run_nfl_prop_odds_ingestor
        logger.info(f"fetching: {run_nfl_prop_odds_ingestor(a.days)}")

    anchor = datetime.fromisoformat(a.date).date() if a.date else datetime.now(timezone.utc).date()
    start, end = anchor.isoformat(), (anchor + timedelta(days=a.days)).isoformat()

    conn = get_connection()
    try:
        games = slate(conn, start, end)
        bets, diag, names = card(conn, start, end, a.min_edge)
    finally:
        conn.close()
    print(render(bets, diag, games, names))


if __name__ == "__main__":
    main()
