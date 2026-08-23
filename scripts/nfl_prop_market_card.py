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
    python -m scripts.nfl_prop_market_card --publish       # write picks rows
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

# Not redefined here — the card must bet exactly the set the backtest graded.
SOFT_BOOKS = mk.SOFT_BOOKS

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


MODEL_ID = "nfl_prop_market"


def pick_rows(bets, games, names, bankroll: float) -> list[dict]:
    """Card bets -> picks rows. Pure, so the mapping is testable without a DB."""
    rows = []
    for b in bets:
        g = games.get(b.game_id, {})
        who = (names or {}).get(b.player, b.player)
        side = "Over" if b.side == "over" else "Under"
        mkt = _LABEL.get(b.market, b.market)
        # pick_label is a display string, NOT the settlement join — that is
        # player_key. It still leads with the player name so the old regex
        # fallback keeps working on these rows.
        label = (f"{who} {side} {b.line:g} {mkt}"
                 if b.market != "player_anytime_td" else f"{who} Anytime TD")
        rows.append({
            "game_id": b.game_id, "model_id": MODEL_ID, "sport": "NFL",
            "game_date": g.get("date"), "game_time": g.get("kickoff"),
            "pick_side": b.side, "pick_label": f"{label} ({_BOOK.get(b.book, b.book)})",
            "model_probability": b.fair,
            # The soft book's own de-vigged number, so edge on the row is the
            # same quantity the rule selected on: fair - book's de-vigged prob.
            "dk_implied_prob": b.fair - b.edge,
            "edge": b.edge,
            # dk_odds holds the SOFT BOOK's price, named in pick_label. This
            # model never scores against DraftKings, so the platform's DK-only
            # invariant does not apply — the §28 wind card set that precedent.
            "dk_odds": b.price, "scored_line": b.line,
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "prop_market": b.market, "player_key": b.player,
        })
    return rows


_INSERT = """
    INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                       pick_side, pick_label, model_probability, dk_implied_prob,
                       edge, dk_odds, scored_line, kelly_fraction,
                       recommended_bet, bankroll_at_pick, signal_type,
                       confidence_tier, prop_market, player_key)
    VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s, %(game_time)s,
            %(pick_side)s, %(pick_label)s, %(model_probability)s,
            %(dk_implied_prob)s, %(edge)s, %(dk_odds)s, %(scored_line)s,
            %(kelly_fraction)s, %(recommended_bet)s, %(bankroll_at_pick)s,
            %(signal_type)s, %(confidence_tier)s, %(prop_market)s, %(player_key)s)
"""


def publish(conn, rows: list[dict]) -> int:
    """
    Insert-once per proposition. The opener rule's lock, not the wind card's
    delete-and-replace: an edge here is a disagreement that gets corrected, so
    re-pricing a locked pick at a number the market has since fixed would
    replace a bet that was taken with one that never existed.
    """
    # picks.game_id is a FOREIGN KEY into games, and an NFL game only gets a
    # games row from the daily props-data step. The first production NFL prop
    # insert died on exactly this constraint (§29), so check up front and name
    # the games that are missing rather than either aborting the whole card or
    # skipping them silently.
    want = sorted({r["game_id"] for r in rows})
    known = {row[0] for row in conn.execute(
        "SELECT game_id FROM games WHERE game_id = ANY(%s)", (want,)).fetchall()}
    absent = [g for g in want if g not in known]
    if absent:
        logger.error("no games row for %d game(s) — skipping their picks; run "
                     "the nfl-props-data step: %s", len(absent), ", ".join(absent))
        rows = [r for r in rows if r["game_id"] in known]

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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=8)
    ap.add_argument("--date", help="anchor date (default today UTC)")
    ap.add_argument("--min-edge", type=float, default=MIN_EDGE)
    ap.add_argument("--fetch", action="store_true",
                    help="pull fresh prices before building the card (costs credits)")
    ap.add_argument("--publish", action="store_true",
                    help="write the card into picks (insert-once per proposition)")
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
        if a.publish and bets:
            from models.scorer import _get_current_bankroll
            n = publish(conn, pick_rows(bets, games, names,
                                        _get_current_bankroll(conn)))
            logger.info(f"published {n} new pick(s); {len(bets) - n} already locked")
    finally:
        conn.close()
    print(render(bets, diag, games, names))


if __name__ == "__main__":
    main()
