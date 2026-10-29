"""% of bets and % of money per side, for the app's Scoreboard only.

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

SPORTS: tuple[str, ...] = ("NFL", "NCAAF", "NBA", "NHL", "MLB")
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


def parse_game(sport: str, game: dict) -> dict | None:
    """One Action Network game -> {date, home_ids, away_ids, sides}, or None
    when it carries no usable split. `sides` is {(market, side): {tickets,
    money, value}} after the pair rules (0/0 is missing, a pair must sum to
    ~100)."""
    teams = {t.get("id"): t for t in game.get("teams") or [] if isinstance(t, dict)}
    home = team_candidates(sport, teams.get(game.get("home_team_id")))
    away = team_candidates(sport, teams.get(game.get("away_team_id")))
    if not home or not away:
        return None
    sides = validate_sides(parse_v2_sides(game, CONSENSUS_BOOK))
    sides = {k: v for k, v in sides.items()
             if v.get("tickets") is not None or v.get("money") is not None}
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
               counts: dict | None = None) -> list[dict]:
    """Rows to upsert from one scoreboard payload. Started games are left
    alone so the stored row stays the last pre-start split."""
    rows: list[dict] = []
    stamp = now.isoformat()
    for game in (payload or {}).get("games") or []:
        if not isinstance(game, dict):
            continue
        parsed = parse_game(sport, game)
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
        if counts is not None:
            counts["games"] = counts.get("games", 0) + 1
        for (market, side), v in sorted(parsed["sides"].items()):
            rows.append({
                "game_id": g["game_id"], "sport": sport,
                "game_date": g["game_date"], "market": market, "side": side,
                "bet_pct": v.get("tickets"), "money_pct": v.get("money"),
                "line_value": v.get("value"), "snapshot_at": stamp,
            })
    return rows


def _default_fetch(sport: str, day: str) -> dict | None:
    import requests

    url = V2_URL.format(slug=sport.lower())
    params = {"bookIds": CONSENSUS_BOOK, "date": day.replace("-", ""), "periods": "event"}
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


UPSERT_SQL = """
INSERT INTO public.scoreboard_splits
    (game_id, sport, game_date, market, side, bet_pct, money_pct,
     line_value, snapshot_at, source)
VALUES
    (%(game_id)s, %(sport)s, %(game_date)s, %(market)s, %(side)s,
     %(bet_pct)s, %(money_pct)s, %(line_value)s, %(snapshot_at)s,
     'action_network')
ON CONFLICT (game_id, market, side) DO UPDATE SET
    bet_pct = EXCLUDED.bet_pct,
    money_pct = EXCLUDED.money_pct,
    line_value = EXCLUDED.line_value,
    snapshot_at = EXCLUDED.snapshot_at
"""


def run(conn=None, *, now: datetime | None = None,
        fetch: Callable[[str, str], dict | None] | None = None) -> dict:
    """One pass: every sport with an unstarted game today or tomorrow (ET).
    Returns {sport: {games, rows, unmatched, started}}."""
    now = now or datetime.now(timezone.utc)
    fetch = fetch or _default_fetch
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
            if rows:
                conn.executemany(UPSERT_SQL, rows)
                conn.commit()
            counts["rows"] = len(rows)
            out[sport] = counts
        logger.info(f"scoreboard_splits: {out}")
        return out
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(run())
