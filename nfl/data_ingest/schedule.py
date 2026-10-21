"""
The NFL schedule the live cards run on: the `games` table, never a file.

Until 2026-10-20 the wind card, the opener card, their DraftKings line dump
and the scheduler's NFL clock all read `data/games.csv`, a copy of the nflverse
schedule committed once (4ffdada1, 2026-08-15) and never refreshed. Measured
against the database that day:

  * it held the 272 regular-season games and no playoff game, so once week 18
    ended (2027-01-10) every NFL pre-game job would have found nothing ahead
    and stood down for the whole postseason;
  * CHI @ GB still sat at 16:25 ET. The real kickoff was 13:00 ET, and wind
    BET 3365283 was written with the 20:25Z time, read 3h25m after the game
    had started;
  * all nine games abroad carried the home team's US stadium, so two London
    wind BETs were forecast at Jacksonville's coordinates.

The rows read here are written every day by the nflverse ingest
(data/ingestors/nfl_props_data_ingestor.py, Step 0h of the 6am pipeline, and
again from the settle pass's box-score gap fill), which carries playoff games
from the day nflverse lists them. `games.commence_time` is the kickoff of
record; the venue comes from the home team's `nfl_team_game_stats` row and is
resolved by `weather.resolve_venue`.

THERE IS NO FALLBACK TO THE FILE. A card that cannot reach the database prints
why and sees an empty slate, the same shape as a card with no key: no bet is
better than a bet on a frozen kickoff. `data/games.csv` stays in the repo as
history for the replays and backtests, which is what it is.
"""

from __future__ import annotations

import sys

import pandas as pd
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")

# The columns `fetch_rows` returns, in order.
ROW_COLUMNS = ["game_id", "season", "home_team", "away_team", "commence_time",
               "week", "season_type", "roof", "stadium_id", "stadium", "location"]

# Bounded on game_date (indexed) and filtered to the window in Python: about
# sixteen games a week, so the read is a few dozen rows. The venue columns are
# read through to_jsonb so a table the boot migration has not reached yet
# returns NULL for them instead of failing the opener card, which does not
# need them. A game with no home-team row keeps its kickoff (LEFT JOIN).
_SQL = """
    SELECT g.game_id, g.season, g.home_team, g.away_team, g.commence_time,
           s.week, s.season_type, s.roof,
           to_jsonb(s) ->> 'stadium_id' AS stadium_id,
           to_jsonb(s) ->> 'stadium'    AS stadium,
           to_jsonb(s) ->> 'location'   AS location
    FROM games g
    LEFT JOIN nfl_team_game_stats s
           ON s.game_id = g.game_id AND s.team = g.home_team
    WHERE g.sport = 'NFL'
      AND g.game_date >= %s AND g.game_date <= %s
      AND g.commence_time IS NOT NULL
"""


def fetch_rows(lo_date: str, hi_date: str) -> list[dict]:
    """NFL games whose Eastern game_date is in [lo_date, hi_date], as dicts."""
    from data.db import get_connection

    conn = get_connection()
    try:
        rows = conn.execute(_SQL, (lo_date, hi_date)).fetchall()
    finally:
        conn.close()
    return [dict(zip(ROW_COLUMNS, r)) for r in rows]


def _utc(now) -> pd.Timestamp:
    t = pd.Timestamp.now(tz="UTC") if now is None else pd.Timestamp(now)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=ROW_COLUMNS + ["kick_utc", "nflverse_stadium_id",
                                               "nflverse_roof", "venue_note",
                                               "matchup", "lead_days"])


def _text(v) -> str | None:
    """A roof value as a comparable string, None for blank, NaN or None."""
    return (v.strip() or None) if isinstance(v, str) else None


def load_schedule(lo_days: float = 0.0, hi_days: float = 10.0, now=None,
                  rows: list[dict] | None = None) -> pd.DataFrame:
    """
    Games kicking off in (now + lo_days, now + hi_days], soonest first.

    One row per game in the shape the cards have always consumed: `game_id`
    as the nflverse id (no "NFL_" prefix -- the publishers add it),
    `home_team`/`away_team` as nflverse abbreviations, `kick_utc` (tz-aware
    UTC), `lead_days`, `matchup`, `roof`, `week`, `season`.

    `stadium_id` is the RESOLVED venue (a `STADIUM_COORDS` key) or None when
    the venue cannot be established; `nflverse_stadium_id` is the raw id and
    `venue_note` says how the venue was decided or why it was not. `roof` is
    the venue's own roof for a game abroad (weather.venue_roof), the row's
    otherwise; `nflverse_roof` is the raw value either way.

    `rows` injects the database rows (tests). Otherwise the database is read;
    when it cannot be, the slate is empty and the reason goes to stderr.
    """
    from data_ingest.weather import resolve_venue, venue_roof

    now = _utc(now)
    if rows is None:
        # Eastern dates, a day of slack each side: a Sunday-night kickoff is
        # Monday in UTC but carries Sunday's game_date.
        lo_date = (now.tz_convert(_ET) + pd.Timedelta(days=lo_days - 1)).date().isoformat()
        hi_date = (now.tz_convert(_ET) + pd.Timedelta(days=hi_days + 1)).date().isoformat()
        try:
            rows = fetch_rows(lo_date, hi_date)
        except Exception as exc:                               # noqa: BLE001
            print(f"WARNING: NFL schedule unavailable from the games table "
                  f"({type(exc).__name__}: {exc}); no games this run", file=sys.stderr)
            return _empty()
    if not rows:
        return _empty()

    g = pd.DataFrame(rows, columns=ROW_COLUMNS)
    g["kick_utc"] = pd.to_datetime(g.commence_time, utc=True, format="ISO8601",
                                   errors="coerce")
    g = g[g.kick_utc.notna()]
    g = g[(g.kick_utc > now + pd.Timedelta(days=lo_days))
          & (g.kick_utc <= now + pd.Timedelta(days=hi_days))].copy()
    if g.empty:
        return _empty()

    g["game_id"] = g.game_id.astype(str).str.replace(r"^NFL_", "", regex=True)
    g["nflverse_stadium_id"] = g.stadium_id
    resolved = [resolve_venue(sid, name, loc)
                for sid, name, loc in zip(g.stadium_id, g.stadium, g.location)]
    g["stadium_id"] = [v for v, _ in resolved]
    g["venue_note"] = [n for _, n in resolved]
    # A game abroad is judged by its venue's roof, not the home team's that
    # nflverse copies onto the row (weather.VENUE_ROOF_ABROAD). The raw value
    # rides along, and the note says when the two differ.
    g["nflverse_roof"] = g.roof
    g["roof"] = [venue_roof(sid, roof) for sid, roof in zip(g.stadium_id, g.roof)]
    g["venue_note"] = [
        note if _text(roof) == _text(raw)
        else f"{note}; roof {_text(roof) or 'unknown'} (nflverse row: {_text(raw) or 'blank'})"
        for note, roof, raw in zip(g.venue_note, g.roof, g.nflverse_roof)]
    g["matchup"] = g.away_team + " @ " + g.home_team
    g["lead_days"] = (g.kick_utc - now).dt.total_seconds() / 86400
    return g.sort_values("kick_utc").reset_index(drop=True)
