"""
public_betting_ingestor.py — Public betting splits via Action Network.

Fetches the % of bets (tickets) and % of money (handle) on each side of every
MLB game today and stores them in the `public_betting` staging table. The
scorer later joins the latest snapshot per (game_id, market, side) and copies
the two percentages onto each pick so the daily picks output can show public
backing alongside model probability and edge (Linear BAB-58).

Why it matters
--------------
Public betting % helps flag fade-the-public spots. A high-edge model pick with
low public backing can signal sharp money on our side; a pick the public is
piling onto despite our edge warns of line-movement risk.

Data source
-----------
Action Network's unofficial JSON scoreboard endpoint — the same data behind
actionnetwork.com/mlb/public-betting. No API key. This endpoint is undocumented
and may change shape or stop returning splits without notice, so every fetch is
best-effort: any failure is logged and returns 0 rows (the pipeline continues),
mirroring the resilient pattern used for the ESPN hidden API and F5 odds.

Endpoint:
    GET {ACTION_NETWORK_BASE}/mlb?bookIds={ids}&date=YYYYMMDD&periods=event

Each game carries a `markets` block keyed by book id; each book exposes
`moneyline`, `spread`, and `total` arrays whose entries have a `side` plus a
`bet_info` object with `tickets.percent` (% of bets) and `money.percent`
(% of money).

Usage:
    python -m data.ingestors.public_betting_ingestor              # today (ET)
    python -m data.ingestors.public_betting_ingestor --date 2026-05-30
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import ACTION_NETWORK_BASE, ACTION_NETWORK_BOOK_IDS
from data.db import get_connection, DBConnection
from data.ingestors.odds_ingestor import _normalize_team, _build_game_id

# ── Constants ─────────────────────────────────────────────────────────────────

_ET = ZoneInfo("America/New_York")
REQUEST_TIMEOUT = 20  # seconds

# Browser-like UA — the endpoint rejects the default python-requests agent.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.actionnetwork.com/mlb/public-betting",
}

# Action Network market name → our internal full-game market key.
_AN_MARKET_MAP = {
    "moneyline": "h2h",
    "spread":    "spreads",
    "total":     "totals",
}

# Sides we expect per market — used to validate parsed entries.
_VALID_SIDES = {"home", "away", "over", "under"}


# ── Parsing helpers (pure functions — unit-tested) ────────────────────────────

def _pct(info: dict, key: str):
    """
    Extract a 0-100 percentage from a bet_info sub-object.

    Handles both shapes Action Network has shipped:
        {"tickets": {"percent": 65, "value": 13000}}
        {"tickets": {"percent": 0.65}}            (fractional)
    Returns a float 0-100, or None if absent.
    """
    sub = (info or {}).get(key)
    if not isinstance(sub, dict):
        return None
    pct = sub.get("percent")
    if pct is None:
        return None
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        return None
    # Normalise fractional (0-1) values to a 0-100 scale.
    if 0 <= pct <= 1:
        pct *= 100.0
    return round(pct, 1)


def _select_book(markets: dict, book_ids: list[str]) -> dict | None:
    """
    From a game's `markets` block (keyed by book id), return the period block
    for the first book that actually carries split data. Falls back to any book
    present so we degrade gracefully if the configured id is missing.
    """
    if not isinstance(markets, dict) or not markets:
        return None

    # Preferred order: configured book ids first, then any remaining book.
    ordered = [b for b in book_ids if b in markets]
    ordered += [b for b in markets.keys() if b not in ordered]

    for bid in ordered:
        block = markets.get(bid)
        if not isinstance(block, dict):
            continue
        # Splits live under "event" (full game) when present; some payloads put
        # the market arrays at the top level of the book block.
        period = block.get("event") if isinstance(block.get("event"), dict) else block
        if any(an_key in period for an_key in _AN_MARKET_MAP):
            return period
    return None


def parse_public_betting(game: dict, book_ids: list[str],
                         snapshot_at: str) -> list[dict]:
    """
    Parse one Action Network game dict into public_betting rows.

    Returns a list of {game_id, game_date, market, side, book,
    public_bet_pct, public_money_pct, source, snapshot_at} dicts. Returns []
    when the game has no usable team or split data (silently skipped upstream).
    """
    teams = {t.get("id"): t for t in game.get("teams", []) if isinstance(t, dict)}
    home = teams.get(game.get("home_team_id"))
    away = teams.get(game.get("away_team_id"))
    if not home or not away:
        return []

    home_name = home.get("full_name") or home.get("display_name") or ""
    away_name = away.get("full_name") or away.get("display_name") or ""
    if not home_name or not away_name:
        return []

    home_abbr = _normalize_team(home_name, "MLB")
    away_abbr = _normalize_team(away_name, "MLB")

    # game_date in ET, matching how games are keyed elsewhere.
    start = game.get("start_time", "")
    try:
        game_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        game_date = game_dt.astimezone(_ET).strftime("%Y-%m-%d")
    except Exception:
        game_date = snapshot_at[:10]

    game_id = _build_game_id("MLB", game_date, away_abbr, home_abbr)

    period = _select_book(game.get("markets", {}), book_ids)
    if not period:
        return []

    rows: list[dict] = []
    for an_key, market in _AN_MARKET_MAP.items():
        entries = period.get(an_key)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            side = entry.get("side")
            if side not in _VALID_SIDES:
                continue
            bet_info = entry.get("bet_info") or {}
            bet_pct   = _pct(bet_info, "tickets")
            money_pct = _pct(bet_info, "money")
            if bet_pct is None and money_pct is None:
                continue
            rows.append({
                "game_id":          game_id,
                "game_date":        game_date,
                "market":           market,
                "side":             side,
                "book":             "consensus",
                "public_bet_pct":   bet_pct,
                "public_money_pct": money_pct,
                "source":           "action_network",
                "snapshot_at":      snapshot_at,
            })
    return rows


# ── HTTP ──────────────────────────────────────────────────────────────────────

def _fetch_scoreboard(date_str: str, book_ids: list[str]) -> list[dict]:
    """Fetch the MLB scoreboard for date_str (YYYY-MM-DD). Returns games list."""
    url = f"{ACTION_NETWORK_BASE}/mlb"
    params = {
        "bookIds": ",".join(book_ids),
        "date":    date_str.replace("-", ""),  # AN expects YYYYMMDD
        "periods": "event",
    }
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    # AN has used both "games" and "scores"/"public_betting" wrappers over time.
    games = data.get("games")
    if not isinstance(games, list):
        games = data.get("scores") if isinstance(data.get("scores"), list) else []
    return games


# ── DB writer ─────────────────────────────────────────────────────────────────

def _upsert_public_betting(conn: DBConnection, rows: list[dict]) -> int:
    """Upsert split rows. One row per (game_id, market, side, book)."""
    if not rows:
        return 0
    sql = """
        INSERT INTO public_betting (
            game_id, game_date, market, side, book,
            public_bet_pct, public_money_pct, source, snapshot_at
        ) VALUES (
            %(game_id)s, %(game_date)s, %(market)s, %(side)s, %(book)s,
            %(public_bet_pct)s, %(public_money_pct)s, %(source)s, %(snapshot_at)s
        )
        ON CONFLICT (game_id, market, side, book) DO UPDATE SET
            public_bet_pct   = EXCLUDED.public_bet_pct,
            public_money_pct = EXCLUDED.public_money_pct,
            game_date        = EXCLUDED.game_date,
            source           = EXCLUDED.source,
            snapshot_at      = EXCLUDED.snapshot_at
    """
    conn.executemany(sql, rows)
    return len(rows)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_public_betting_ingestor(target_date: str = None) -> dict:
    """
    Pull Action Network public betting splits for all MLB games on target_date
    and upsert them into public_betting.

    Best-effort: a fetch/parse failure is logged and yields 0 rows so the daily
    pipeline keeps going. Picks for games without splits simply leave the
    public_bet_pct / public_money_pct columns NULL.
    """
    if target_date is None:
        target_date = datetime.now(_ET).strftime("%Y-%m-%d")

    book_ids = [b.strip() for b in ACTION_NETWORK_BOOK_IDS.split(",") if b.strip()]
    snapshot_at = datetime.now(_ET).isoformat()
    start = datetime.now()

    logger.info(f"Public betting ingestor: {target_date} (books={book_ids})")

    try:
        games = _fetch_scoreboard(target_date, book_ids)
    except Exception as exc:
        logger.warning(f"Action Network fetch failed (non-fatal): {exc}")
        return {"target_date": target_date, "games": 0, "rows": 0, "error": str(exc)}

    if not games:
        logger.info(f"No MLB games returned by Action Network for {target_date}")
        return {"target_date": target_date, "games": 0, "rows": 0}

    conn = get_connection()
    total_rows = 0
    games_with_splits = 0
    try:
        for game in games:
            try:
                rows = parse_public_betting(game, book_ids, snapshot_at)
            except Exception as exc:
                logger.debug(f"  Skipping a game (parse error): {exc}")
                continue
            if rows:
                # Only persist rows whose game we actually track (FK to games).
                game_id = rows[0]["game_id"]
                exists = conn.execute(
                    "SELECT 1 FROM games WHERE game_id = %s", (game_id,)
                ).fetchone()
                if not exists:
                    logger.debug(f"  {game_id} not in games table — skipping")
                    continue
                total_rows += _upsert_public_betting(conn, rows)
                games_with_splits += 1
        conn.commit()
    except Exception as exc:
        conn.rollback()
        logger.warning(f"Public betting upsert failed (non-fatal): {exc}")
        return {"target_date": target_date, "games": len(games),
                "rows": total_rows, "error": str(exc)}
    finally:
        conn.close()

    duration = (datetime.now() - start).total_seconds()
    logger.success(
        f"Public betting: {games_with_splits}/{len(games)} games with splits, "
        f"{total_rows} rows — {duration:.1f}s"
    )
    return {
        "target_date": target_date,
        "games":       len(games),
        "with_splits": games_with_splits,
        "rows":        total_rows,
        "duration_s":  duration,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run public betting ingestor")
    parser.add_argument("--date", metavar="YYYY-MM-DD",
                        help="Target date (default: today ET)")
    args = parser.parse_args()
    result = run_public_betting_ingestor(target_date=args.date)
    logger.info(f"Done: {result}")
