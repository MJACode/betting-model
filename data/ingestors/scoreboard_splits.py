"""% of bets and % of money per side from Action Network's consensus.

SINCE 2026-11-16 THIS IS HISTORY ONLY. The Scoreboard shows DraftKings' own
split (data/ingestors/dk_splits.py); this module appends Action Network's
consensus to scoreboard_splits_history and no longer writes
scoreboard_splits. What follows is the original 2026-10-29 note.

Matt, 2026-10-29: the Scoreboard shows Odds, % Bets and % Money for a chosen
market (spread, total, moneyline), the way Action Network's Matchups board
does. Source: Action Network's free v2 scoreboard
(``/web/v2/scoreboard/{sport}?bookIds=15&date=YYYYMMDD&periods=event``),
the same endpoint nba_public_splits_ingestor polls for NBA. No API key, no
Odds API credits.

WHY A TABLE OF ITS OWN. models/scorer.py copies `public_betting`'s
percentages onto every pick by game id with no sport filter, and
tracking/model_quality.py reads them back, so any NFL / NCAAF / NHL / NBA row
written there would change what live picks carry. `nba_public_splits` is a
research log with NBA-only columns. This table is display only: one row per
(game_id, market, side), the latest pre-start split, and nothing but the app
reads it.

WHAT IS AND IS NOT MEASURED. On 2026-10-29 the stored splits covered NBA
(nba_public_splits, 71 games since 10-20) and MLB (public_betting). Whether
the v2 endpoint serves splits for NFL, NCAAF and NHL was not checked: this
sandbox's network policy blocks api.actionnetwork.com. Each pass logs how
many games per sport had a split, so the first worker pass after deploy is
the measurement. A sport with no split writes nothing and its cards show a
dash.

Only games that have not reached their listed start are written, so the row
kept for a game is its last pre-start split (v2's in-progress entries read
0/0, which is missing, not 0%). The app shows that percent only when
line_value is the number in the odds cell, and not at all next to an
in-play DraftKings quote.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from loguru import logger

from data.ingestors.nba_public_splits_ingestor import (
    _ABBR_ALIASES as _NBA_ABBR_ALIASES,
    CONSENSUS_BOOK,
    et_game_date,
    parse_v2_sides,
    validate_sides,
)

# WNBA added 2026-11-26 (mike, "1) yes"): inert until its season has an unstarted game. Teams match on the
# full name through the odds feed's normaliser (WNBA_ODDS_API_MAP); scripts/splits_coverage_probe.py counts
# how many of its last played date's games the matcher finds.
SPORTS: tuple[str, ...] = ("NFL", "NCAAF", "NBA", "NHL", "MLB", "NCAAB", "WNBA")

# Period splits (Matt, 2026-11-26: "Yes on splits", hourly).
# CORRECTION (mike, 2026-11-26, later the same day): consensus serves NO period
# split. The list below was chosen from worker_jobs 1698627, which counted
# Action Network's 0/0 placeholder as a split. Counting only non-zero shares,
# worker_jobs 1717775 (15:15 UTC) found no period and no team-total split at
# consensus for NFL, NCAAF or NCAAB (NBA and NHL had no games that day), and
# the hourly passes at 15:19, 15:28 and 16:18 UTC stored 0 period rows in all
# five sports (worker log). The fetch is left in place so a period split shows
# up in the history the day consensus starts serving one; whether any single
# book splits periods is what scripts/splits_coverage_probe.py measures.
PERIODS_BY_SPORT: dict[str, tuple[str, ...]] = {
    "NBA": ("firsthalf", "secondhalf", "firstquarter", "secondquarter", "thirdquarter", "fourthquarter"),
    "NFL": ("firsthalf", "firstquarter", "secondquarter", "thirdquarter", "fourthquarter"),
    "NCAAF": ("firsthalf", "firstquarter", "secondquarter", "thirdquarter", "fourthquarter"),
    "NCAAB": ("firsthalf", "secondhalf"),
    "NHL": ("firstperiod",),
}
# The odds table's period suffix for each v2 period (h2h_q1, totals_h1, ...), so
# mcp_stats reads one naming for prices and splits.
PERIOD_SUFFIX = {"firsthalf": "h1", "secondhalf": "h2", "firstquarter": "q1", "secondquarter": "q2",
                 "thirdquarter": "q3", "fourthquarter": "q4", "firstperiod": "p1"}
# Hourly, not every pass: the hourly passes start at :17 (7am-5pm ET) and the
# evening passes every 10 minutes, so this window holds exactly one pass an hour.
PERIOD_MINUTES = range(15, 30)


def periods_due(now: datetime) -> bool:
    return now.astimezone(_ET).minute in PERIOD_MINUTES


def periods_storable(conn) -> bool:
    """scoreboard_splits_period_markets_2026_11_26.sql has run: the history's
    market check accepts a period suffix. Until it has, no period is fetched,
    so a refused row can never fail the full-game append beside it."""
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = "
        "'scoreboard_splits_history_market_period_check')").fetchone()
    return bool(row and row[0])
V2_URL = "https://api.actionnetwork.com/web/v2/scoreboard/{slug}"
REQUEST_TIMEOUT = 20
# Today and tomorrow (ET): the Scoreboard's forward days.
DAYS_AHEAD = 1

_ET = ZoneInfo("America/New_York")

# Action Network abbreviations that differ from ours, per sport. The full
# name goes through the odds feed's normaliser first; these are the fallback.
_ABBR_ALIASES: dict[str, dict[str, str]] = {
    "NBA": dict(_NBA_ABBR_ALIASES),
    "NFL": {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"},
    "NHL": {"LA": "LAK", "TB": "TBL", "SJ": "SJS", "NJ": "NJD", "UTAH": "UTA"},
    "MLB": {"WAS": "WSH", "CHW": "CWS", "AZ": "ARI"},
}


def _headers(sport: str) -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Referer": f"https://www.actionnetwork.com/{sport.lower()}/public-betting",
    }


def team_candidates(sport: str, team: dict | None) -> set[str]:
    """Every id this Action Network team could be in `games`. Matching keeps
    only a candidate that is actually on the slate, so nothing is invented."""
    if not isinstance(team, dict):
        return set()
    out: set[str] = set()
    from data.ingestors.odds_ingestor import _normalize_team
    for name in (team.get("full_name"), team.get("display_name")):
        if name:
            try:
                out.add(_normalize_team(str(name), sport))
            except Exception:                                 # noqa: BLE001
                pass
    if sport == "NCAAF":
        for name in (team.get("location"), team.get("short_name")):
            if name:
                out.add(str(name))
    abbr = str(team.get("abbr") or "").upper()
    if abbr:
        out.add(_ABBR_ALIASES.get(sport, {}).get(abbr, abbr))
    return {c for c in out if c}


def parse_game(sport: str, game: dict, period: str = "event") -> dict | None:
    """One Action Network game -> {date, home_ids, away_ids, sides}, or None
    when it carries no usable split. `sides` is {(market, side): {tickets,
    money, value}} after the pair rules (0/0 is missing, a pair must sum to
    ~100)."""
    teams = {t.get("id"): t for t in game.get("teams") or [] if isinstance(t, dict)}
    home = team_candidates(sport, teams.get(game.get("home_team_id")))
    away = team_candidates(sport, teams.get(game.get("away_team_id")))
    if not home or not away:
        return None
    sides = validate_sides(parse_v2_sides(game, CONSENSUS_BOOK, period))
    sides = {k: v for k, v in sides.items()
             if v.get("tickets") is not None or v.get("money") is not None}
    if period != "event":
        # Pair rules run on the base market; the stored name carries the period.
        sides = {(f"{m}_{PERIOD_SUFFIX[period]}", side): v for (m, side), v in sides.items()}
    if not sides:
        return None
    return {"date": et_game_date(game.get("start_time")), "home": home,
            "away": away, "sides": sides}


def match(parsed: dict, games: Iterable[dict]) -> dict | None:
    """The one `games` row whose teams are among the candidates, preferring
    the same ET date. Two matches on different dates with no date hit is
    ambiguous and returns None."""
    hits = [g for g in games
            if g.get("home_team") in parsed["home"] and g.get("away_team") in parsed["away"]]
    same_day = [g for g in hits if g.get("game_date") == parsed.get("date")]
    if len(same_day) == 1:
        return same_day[0]
    if not same_day and len(hits) == 1:
        return hits[0]
    return None


def _parse_ts(v: Any) -> datetime | None:
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def build_rows(sport: str, payload: dict, games: list[dict], now: datetime,
               counts: dict | None = None, period: str = "event") -> list[dict]:
    """Rows to upsert from one scoreboard payload. Started games are left
    alone so the stored row stays the last pre-start split."""
    rows: list[dict] = []
    stamp = now.isoformat()
    for game in (payload or {}).get("games") or []:
        if not isinstance(game, dict):
            continue
        parsed = parse_game(sport, game, period)
        if parsed is None:
            continue
        g = match(parsed, games)
        if g is None:
            if counts is not None:
                counts["unmatched"] = counts.get("unmatched", 0) + 1
            continue
        start = _parse_ts(g.get("commence_time"))
        if start is None or start <= now:
            if counts is not None:
                counts["started"] = counts.get("started", 0) + 1
            continue
        if counts is not None and period == "event":
            counts["games"] = counts.get("games", 0) + 1
        for (market, side), v in sorted(parsed["sides"].items()):
            rows.append({
                "game_id": g["game_id"], "sport": sport,
                "game_date": g["game_date"], "market": market, "side": side,
                "bet_pct": v.get("tickets"), "money_pct": v.get("money"),
                "line_value": v.get("value"), "snapshot_at": stamp,
            })
    return rows


def _default_fetch(sport: str, day: str, period: str = "event") -> dict | None:
    import requests

    url = V2_URL.format(slug=sport.lower())
    params = {"bookIds": CONSENSUS_BOOK, "date": day.replace("-", ""), "periods": period}
    try:
        r = requests.get(url, params=params, headers=_headers(sport), timeout=REQUEST_TIMEOUT)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"scoreboard_splits {sport} {day}: fetch failed: {exc}")
        return None
    if r.status_code != 200:
        logger.warning(f"scoreboard_splits {sport} {day}: HTTP {r.status_code}")
        return None
    try:
        return r.json()
    except ValueError:
        logger.warning(f"scoreboard_splits {sport} {day}: response was not JSON")
        return None


# Matt, 2026-11-16: the Scoreboard shows DraftKings' own split
# (data/ingestors/dk_splits.py), so Action Network's consensus no longer
# writes scoreboard_splits, where it would overwrite the DK row every pass.
# It is kept, append-only, in scoreboard_splits_history with its source.
HISTORY_SOURCE = "action_network"

HISTORY_LATEST_SQL = """
SELECT DISTINCT ON (game_id, market, side)
       game_id, market, side, bet_pct, money_pct, line_value
  FROM public.scoreboard_splits_history
 WHERE source = %(source)s AND game_id = ANY(%(ids)s)
 ORDER BY game_id, market, side, snapshot_at DESC
"""

HISTORY_INSERT_SQL = """
INSERT INTO public.scoreboard_splits_history
    (game_id, sport, game_date, market, side, bet_pct, money_pct,
     line_value, odds, source, snapshot_at)
VALUES
    (%(game_id)s, %(sport)s, %(game_date)s, %(market)s, %(side)s,
     %(bet_pct)s, %(money_pct)s, %(line_value)s, %(odds)s, %(source)s,
     %(snapshot_at)s)
ON CONFLICT (game_id, market, side, source, snapshot_at) DO NOTHING
"""


def _same(a: Any, b: Any) -> bool:
    if a is None or b is None:
        return a is None and b is None
    try:
        return abs(float(a) - float(b)) < 1e-6
    except (TypeError, ValueError):
        return False


def changed_rows(rows: list[dict], latest: dict) -> list[dict]:
    """The rows whose split or line differs from the last stored for the same
    (game_id, market, side). Pure. A row with no stored predecessor is new."""
    out = []
    for r in rows:
        prev = latest.get((r["game_id"], r["market"], r["side"]))
        if prev is not None and all(
            _same(r.get(k), prev.get(k)) for k in ("bet_pct", "money_pct", "line_value")
        ):
            continue
        out.append(r)
    return out


def append_history(conn, rows: list[dict], source: str) -> int:
    """Append each row that changed since the last one stored for `source`.
    Never updates or deletes. Returns the number appended; 0 when the history
    table does not exist yet (the migration runs on the next pipeline pass)."""
    if not rows:
        return 0
    if conn.execute(
        "SELECT to_regclass('public.scoreboard_splits_history') IS NOT NULL"
    ).fetchone()[0] is not True:
        logger.info("scoreboard_splits_history: table not created yet; nothing appended")
        return 0
    ids = sorted({r["game_id"] for r in rows})
    cols = ("game_id", "market", "side", "bet_pct", "money_pct", "line_value")
    latest = {}
    for rec in conn.execute(HISTORY_LATEST_SQL, {"source": source, "ids": ids}).fetchall():
        d = dict(zip(cols, rec))
        latest[(d["game_id"], d["market"], d["side"])] = d
    new = [{"odds": None, **r, "source": source} for r in changed_rows(rows, latest)]
    if new:
        conn.executemany(HISTORY_INSERT_SQL, new)
        conn.commit()
    return len(new)


def run(conn=None, *, now: datetime | None = None,
        fetch: Callable[[str, str], dict | None] | None = None,
        fetch_period: Callable[[str, str, str], dict | None] | None = None) -> dict:
    """One pass: every sport with an unstarted game today or tomorrow (ET).
    Returns {sport: {games, rows, unmatched, started}}. Period splits are
    fetched on the hourly window only (periods_due), through `fetch_period`;
    a caller that passes its own `fetch` and no `fetch_period` gets none."""
    now = now or datetime.now(timezone.utc)
    if fetch_period is None and fetch is None:
        fetch_period = _default_fetch
    fetch = fetch or _default_fetch
    with_periods = fetch_period is not None and periods_due(now)
    today = now.astimezone(_ET).date()
    days = [(today + timedelta(days=i)).isoformat() for i in range(DAYS_AHEAD + 1)]
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if conn.execute(
            "SELECT to_regclass('public.scoreboard_splits') IS NOT NULL"
        ).fetchone()[0] is not True:
            logger.info("scoreboard_splits: table not created yet; nothing written")
            return {}
        cols = ("game_id", "sport", "game_date", "home_team", "away_team", "commence_time")
        games = [dict(zip(cols, r)) for r in conn.execute(
            "SELECT game_id, sport, game_date::text, home_team, away_team, "
            "commence_time::text FROM public.games "
            "WHERE sport = ANY(%(sports)s) AND game_date::text = ANY(%(days)s)",
            {"sports": list(SPORTS), "days": days},
        ).fetchall()]
        with_periods = with_periods and periods_storable(conn)
        out: dict = {}
        for sport in SPORTS:
            slate = [g for g in games if g["sport"] == sport]
            if not any((_parse_ts(g["commence_time"]) or now) > now for g in slate):
                continue
            counts: dict = {}
            rows: list[dict] = []
            for day in days:
                if not any(g["game_date"] == day for g in slate):
                    continue
                payload = fetch(sport, day)
                if payload is None:
                    continue
                rows.extend(build_rows(sport, payload, slate, now, counts))
                time.sleep(0.5)
                for period in (PERIODS_BY_SPORT.get(sport, ()) if with_periods else ()):
                    pp = fetch_period(sport, day, period)
                    if pp is not None:
                        got = build_rows(sport, pp, slate, now, None, period)
                        counts[period] = counts.get(period, 0) + len(got)
                        rows.extend(got)
                    time.sleep(0.5)
            counts["rows"] = len(rows)
            counts["history"] = append_history(conn, rows, HISTORY_SOURCE)
            out[sport] = counts
        logger.info(f"scoreboard_splits: {out}")
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(run())
