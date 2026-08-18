"""
Publish the NFL wind-totals card into the platform's picks table.

The nfl/ package is standalone by design (CLAUDE.md Section 28) — its weekly
wind card prints to the Railway log and writes a CSV on the worker's ephemeral
disk. This publisher bridges that card into the app: after each scheduled LIVE
card run (scheduler.run_nfl_wind_card), it reads the day's card CSV and mirrors
the qualifying bets into `games` + `picks`, so they surface in the mobile app
like any other pick and settle through the standard game-level path.

Conventions (load-bearing):
- game_id = "NFL_" + the nflverse game id (e.g. NFL_2026_01_NE_SEA). The
  nflverse id is stable across flex-schedule date changes and is the join key
  the results ingestor uses — settlement can never miss on a date mismatch.
- model_id = "nfl_wind_totals"; picks are ALWAYS the under (the rule is
  under-only — it is not a spread or over play, see nfl/models/wind_totals.py).
- dk_odds stores the card's BEST-BOOK price. The wind card line-shops across
  books by design; the platform's DraftKings-only invariant applies to models
  that score against DK lines, which this standalone model never does. The
  book is named in pick_label so the price is never mistaken for a DK quote.
- Delete + replace for FUTURE kickoffs only: each card run re-prices whatever
  is still in its window (runbook: later is better — the edge is vs the close
  and forecast skill improves), so unstarted NFL wind picks that are NOT on
  the latest live card are cleared (wind dropped / line moved past the edge
  gate). Started games are never touched — the UFC/golf look-ahead precedent;
  NFL picks are future-dated and exempt from the first-run lock.
- NEVER run after a --dry-run card: a dry run has no prices and writes no CSV,
  and clearing picks off it would wipe a valid board. The scheduler only
  invokes this after a live run (THE_ODDS_API_KEY/ODDS_API_KEY present).

OPENER MODE (--opener): publishes the daily opener-spread card
(nfl/scripts/daily_opener_card.py) as model `nfl_opener_spread`. The locking
is the OPPOSITE of wind: an opener bet locks at the FIRST qualifying moment
(~T-6..T-2 days out) and is NEVER re-priced or removed — the edge IS the
staleness of the number taken; waiting or refreshing destroys it. So opener
publishing is insert-once per (game, model): a game that already has an
opener pick (settled or not) is skipped, and no-card days clear nothing.

Run (from repo root, after a LIVE card run only):
    python -m scripts.nfl_wind_publisher                    # today's wind card (UTC date)
    python -m scripts.nfl_wind_publisher --opener           # today's opener card
    python -m scripts.nfl_wind_publisher --date 2026-09-10
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

NFL_WIND_MODEL_ID = "nfl_wind_totals"
NFL_OPENER_MODEL_ID = "nfl_opener_spread"
CARDS_DIR = Path(__file__).resolve().parent.parent / "nfl" / "data" / "cards"

_ET = ZoneInfo("America/New_York")

# Short labels for the best-price book named in pick_label. Unknown keys fall
# back to the raw key so a new book can never crash the publisher.
BOOK_ABBREV = {
    "draftkings": "DK",
    "fanduel": "FD",
    "betmgm": "MGM",
    "williamhill_us": "CZR",   # Caesars on The Odds API
    "caesars": "CZR",
    "espnbet": "ESPN",
    "betrivers": "BR",
    "bovada": "BOV",
    "pinnacle": "PIN",
    "matchbook": "MB (exch.)",  # exchange — price gross of commission
}


def parse_matchup(matchup: str) -> tuple[str, str]:
    """'NYJ @ MIA' -> ('NYJ', 'MIA'). Raises on any other shape."""
    away, sep, home = matchup.partition(" @ ")
    if not sep or not away.strip() or not home.strip():
        raise ValueError(f"unparseable NFL matchup: {matchup!r}")
    return away.strip(), home.strip()


def kick_fields(kick_utc: str) -> tuple[str, str]:
    """
    The card's kick_utc ('2026-09-13 17:00:00+00:00') -> (game_date, game_time).

    game_date is the EASTERN date (platform convention — a Sunday-night 8:20pm
    ET kickoff is 00:20 UTC Monday and must not land on Monday's board).
    game_time is the ISO commence_time in UTC (T separator), matching
    games.commence_time everywhere else.
    """
    dt = datetime.fromisoformat(kick_utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.astimezone(_ET).date().isoformat(), dt.isoformat()


def _fmt_line(total_line: float) -> str:
    """44.0 -> '44', 43.5 -> '43.5'."""
    return f"{total_line:g}"


def build_rows(card_rows: list[dict], bankroll: float) -> tuple[list[dict], list[dict]]:
    """
    Pure transform: card CSV rows -> (games rows, picks rows).

    Card columns (nfl/models/wind_totals.Bet): game_id, matchup, kick_utc,
    stadium_id, lead_days, forecast_wind, exp_true_wind, total_line, book,
    price, model_prob, market_prob, edge, stake_pct, ev_pct (+ stake_units).
    Rows that fail to parse are skipped with a message rather than sinking the
    whole card.
    """
    games: list[dict] = []
    picks: list[dict] = []
    for r in card_rows:
        try:
            nflverse_id = r["game_id"].strip()
            season = int(nflverse_id.split("_")[0])
            away, home = parse_matchup(r["matchup"])
            game_date, commence_iso = kick_fields(r["kick_utc"])
            total_line = float(r["total_line"])
            price = float(r["price"])
            model_prob = float(r["model_prob"])
            market_prob = float(r["market_prob"])
            edge = float(r["edge"])
            stake_pct = float(r["stake_pct"])
            wind = float(r["forecast_wind"])
            book = (r.get("book") or "").strip()
        except (KeyError, ValueError, IndexError) as exc:
            print(f"skipping unparseable card row ({exc}): {r}", file=sys.stderr)
            continue

        game_id = f"NFL_{nflverse_id}"
        kelly_fraction = round(stake_pct / 100.0, 6)
        games.append({
            "game_id": game_id,
            "sport": "NFL",
            "season": season,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "commence_time": commence_iso,
        })
        picks.append({
            "game_id": game_id,
            "model_id": NFL_WIND_MODEL_ID,
            "sport": "NFL",
            "game_date": game_date,
            "game_time": commence_iso,
            "pick_side": "under",
            "pick_label": (
                f"{away} @ {home} Under {_fmt_line(total_line)} "
                f"(Wind {wind:.0f} mph, {BOOK_ABBREV.get(book, book or '?')})"
            ),
            "model_probability": model_prob,
            "dk_implied_prob": market_prob,   # de-vigged best-book prob
            "edge": edge,
            "dk_odds": price,                 # best-book price; book in label
            "scored_line": total_line,
            "kelly_fraction": kelly_fraction,
            "recommended_bet": round(kelly_fraction * bankroll, 2),
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
        })
    return games, picks


def build_opener_rows(card_rows: list[dict], bankroll: float) -> tuple[list[dict], list[dict]]:
    """
    Pure transform: opener card CSV rows -> (games rows, picks rows).

    Card columns (daily_opener_card.select_opener_bets): game_id, matchup,
    kick_utc, lead_days, side, bet_team, book, price, side_line,
    soft_home_line, pin_home_line, dev, model_prob, market_prob, edge.

    scored_line stores the SOFT book's HOME spread — the platform's spreads
    settle convention (covered = margin + spread_home; home wins >0, away <0),
    which grades both sides correctly from the one home-relative number.
    """
    games: list[dict] = []
    picks: list[dict] = []
    for r in card_rows:
        try:
            nflverse_id = r["game_id"].strip()
            season = int(nflverse_id.split("_")[0])
            away, home = parse_matchup(r["matchup"])
            game_date, commence_iso = kick_fields(r["kick_utc"])
            side = r["side"].strip()
            assert side in ("home", "away"), side
            bet_team = r["bet_team"].strip()
            side_line = float(r["side_line"])
            soft_home_line = float(r["soft_home_line"])
            price = float(r["price"])
            model_prob = float(r["model_prob"])
            market_prob = float(r["market_prob"])
            edge = float(r["edge"])
            dev = float(r["dev"])
            book = (r.get("book") or "").strip()
        except (KeyError, ValueError, IndexError, AssertionError) as exc:
            print(f"skipping unparseable opener row ({exc}): {r}", file=sys.stderr)
            continue

        game_id = f"NFL_{nflverse_id}"
        # The validated stake is 1u flat (the backtest is flat-staked; there is
        # no per-bet Kelly curve for a flat 58.18% rule) — mirror the wind
        # card's 1% flat cap for sizing consistency.
        kelly_fraction = 0.01
        games.append({
            "game_id": game_id,
            "sport": "NFL",
            "season": season,
            "game_date": game_date,
            "home_team": home,
            "away_team": away,
            "commence_time": commence_iso,
        })
        picks.append({
            "game_id": game_id,
            "model_id": NFL_OPENER_MODEL_ID,
            "sport": "NFL",
            "game_date": game_date,
            "game_time": commence_iso,
            "pick_side": side,
            "pick_label": (
                f"{away} @ {home} — {bet_team} {side_line:+g} "
                f"(Opener {dev:+g} vs Pinnacle, {BOOK_ABBREV.get(book, book or '?')})"
            ),
            "model_probability": model_prob,
            "dk_implied_prob": market_prob,
            "edge": edge,
            "dk_odds": price,                 # soft-book price; book in label
            "scored_line": soft_home_line,    # HOME spread — settle convention
            "kelly_fraction": kelly_fraction,
            "recommended_bet": round(kelly_fraction * bankroll, 2),
            "bankroll_at_pick": bankroll,
            "signal_type": "BET",
        })
    return games, picks


def read_card(path: Path) -> list[dict]:
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def publish(run_date: str | None = None) -> int:
    """
    Mirror the day's card into games + picks. Returns picks written.

    A missing card CSV after a LIVE run means zero qualifying bets — unstarted
    NFL wind picks are cleared either way, so a pick whose wind dropped below
    threshold (or whose edge evaporated) leaves the board honestly.
    """
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()

    card_path = CARDS_DIR / f"wind_card_{run_date}.csv"
    card_rows = read_card(card_path) if card_path.exists() else []
    game_rows, pick_rows = build_rows(card_rows, config.BANKROLL)

    now_iso = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        for g in game_rows:
            conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date,
                                   home_team, away_team, commence_time, data_source)
                VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s,
                        %(home_team)s, %(away_team)s, %(commence_time)s, 'nfl_wind_card')
                ON CONFLICT (game_id) DO UPDATE
                SET commence_time = EXCLUDED.commence_time,
                    game_date     = EXCLUDED.game_date
            """, g)

        # Clear unstarted, unsettled wind picks — the latest live card is the
        # board of record for every future kickoff in its window. Started
        # games are never touched (their pick stands and settles).
        conn.execute("""
            DELETE FROM picks
            WHERE model_id = %s
              AND result IS NULL
              AND game_id IN (
                  SELECT game_id FROM games
                  WHERE sport = 'NFL' AND commence_time > %s
              )
        """, (NFL_WIND_MODEL_ID, now_iso))

        for p in pick_rows:
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s)
            """, p)
        conn.commit()
    finally:
        conn.close()

    print(f"NFL wind publish {run_date}: {len(pick_rows)} pick(s) "
          f"from {card_path.name if card_path.exists() else 'no card (zero qualifying bets)'}")
    return len(pick_rows)


def publish_opener(run_date: str | None = None) -> int:
    """
    Mirror the day's opener card into games + picks. Returns picks written.

    INSERT-ONCE LOCK: a game with ANY existing nfl_opener_spread pick is
    skipped — the first qualifying card locks the bet forever (the edge is the
    stale number; re-pricing on a later card would trade it away). No-card
    days do nothing: opener picks are never cleared.
    """
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()

    card_path = CARDS_DIR / f"opener_card_{run_date}.csv"
    if not card_path.exists():
        print(f"NFL opener publish {run_date}: no card — nothing to do")
        return 0
    game_rows, pick_rows = build_opener_rows(read_card(card_path), config.BANKROLL)

    conn = get_connection()
    written = 0
    try:
        for g in game_rows:
            conn.execute("""
                INSERT INTO games (game_id, sport, season, game_date,
                                   home_team, away_team, commence_time, data_source)
                VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s,
                        %(home_team)s, %(away_team)s, %(commence_time)s, 'nfl_opener_card')
                ON CONFLICT (game_id) DO UPDATE
                SET commence_time = EXCLUDED.commence_time,
                    game_date     = EXCLUDED.game_date
            """, g)

        for p in pick_rows:
            existing = conn.execute("""
                SELECT 1 FROM picks WHERE game_id = %s AND model_id = %s LIMIT 1
            """, (p["game_id"], p["model_id"])).fetchone()
            if existing:
                continue  # locked at its first qualifying card
            conn.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, game_time,
                                   pick_side, pick_label, model_probability,
                                   dk_implied_prob, edge, dk_odds, scored_line,
                                   kelly_fraction, recommended_bet, bankroll_at_pick,
                                   signal_type)
                VALUES (%(game_id)s, %(model_id)s, %(sport)s, %(game_date)s,
                        %(game_time)s, %(pick_side)s, %(pick_label)s,
                        %(model_probability)s, %(dk_implied_prob)s, %(edge)s,
                        %(dk_odds)s, %(scored_line)s, %(kelly_fraction)s,
                        %(recommended_bet)s, %(bankroll_at_pick)s, %(signal_type)s)
            """, p)
            written += 1
        conn.commit()
    finally:
        conn.close()

    print(f"NFL opener publish {run_date}: {written} new pick(s) locked, "
          f"{len(pick_rows) - written} already locked")
    return written


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="card date (UTC, YYYY-MM-DD); default today")
    ap.add_argument("--opener", action="store_true",
                    help="publish the opener-spread card instead of the wind card")
    args = ap.parse_args()
    if args.opener:
        publish_opener(args.date)
    else:
        publish(args.date)
