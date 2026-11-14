"""Tennis results from ESPN's public scoreboard, stored in Supabase.

WHY. The match archive (data/ingestors/tennis_archive.py) ends with its June
2026 snapshot, and a pick placed tomorrow has to be graded tomorrow. ESPN's
scoreboard answers without a key and carries every singles match of the tour
events it lists (the 250 level and the WTA 125 level included; 2010 on, read
2026-11-13), with the round, the court, the start, both players' ESPN ids, the
games of every set and the tiebreak points, and a status that names a
retirement or a walkover:

    site.api.espn.com/apis/site/v2/sports/tennis/{atp|wta}/scoreboard?dates=YYYYMMDD

One call returns every tournament in play on that date, whole (the 2025 US Open
answered with all 239 men's singles matches, qualifying included). So a season
is read off its own calendar (leagues[0].calendar, the dates with play) at a
step short enough that no tournament falls between two calls.

WHAT IS STORED. tennis_espn_matches: one row per singles match, keyed on ESPN's
competition id, updated in place while a match moves from scheduled to final.
The status is ESPN's (STATUS_FINAL, STATUS_RETIRED, STATUS_WALKOVER, ...);
best-of is NOT read from ESPN's format field, which says 5 for best-of-3 events
(the women's US Open, Shanghai), but from the tour and the event.

THE SEASON is the year in ESPN's event id ("189-2025"), never a match date.

    python -m data.ingestors.tennis_espn --seasons 2025 2026 --store
    python -m data.ingestors.tennis_espn --days 3 --store       # the recent days
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import date, datetime, timedelta, timezone

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

URL = "https://site.api.espn.com/apis/site/v2/sports/tennis/{tour}/scoreboard"
TOURS = ("atp", "wta")
SINGLES = {"mens-singles": "ATP", "womens-singles": "WTA"}
# Every third date with play: the shortest tour event runs five days.
CALENDAR_STEP = 3
# Grand Slam men's singles is best of five; every other singles match here is
# best of three. ESPN marks the four by `major` on the event.
SLAM_NAMES = ("australian open", "french open", "roland garros", "wimbledon", "us open")

TABLE = "tennis_espn_matches"
COLS = ("comp_id", "tour", "season", "event_id", "event_name", "is_major", "round_name",
        "start_time", "court", "venue", "status", "completed", "best_of",
        "p1_id", "p1_name", "p1_country", "p1_winner", "p1_games", "p1_tiebreaks",
        "p2_id", "p2_name", "p2_country", "p2_winner", "p2_games", "p2_tiebreaks",
        "note", "was_suspended", "updated_at")
DDL = """
CREATE TABLE IF NOT EXISTS tennis_espn_matches (
    comp_id        TEXT PRIMARY KEY,
    tour           TEXT NOT NULL,
    season         INTEGER NOT NULL,
    event_id       TEXT NOT NULL,
    event_name     TEXT,
    is_major       BOOLEAN,
    round_name     TEXT,
    start_time     TIMESTAMPTZ,
    court          TEXT,
    venue          TEXT,
    status         TEXT,
    completed      BOOLEAN,
    best_of        INTEGER,
    p1_id          TEXT,
    p1_name        TEXT,
    p1_country     TEXT,
    p1_winner      BOOLEAN,
    p1_games       INTEGER[],
    p1_tiebreaks   INTEGER[],
    p2_id          TEXT,
    p2_name        TEXT,
    p2_country     TEXT,
    p2_winner      BOOLEAN,
    p2_games       INTEGER[],
    p2_tiebreaks   INTEGER[],
    note           TEXT,
    was_suspended  BOOLEAN,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
INDEX = "idx_tennis_espn_matches_start"
INDEX_DDL = f"CREATE INDEX IF NOT EXISTS {INDEX} ON {TABLE} (tour, start_time)"


def ensure_tables(conn) -> None:
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        conn.execute(INDEX_DDL)
        lock_down(conn, TABLE)
        conn.commit()


class FetchFailed(Exception):
    pass


def fetch(tour: str, day: date) -> dict:
    """One scoreboard answer. Raises FetchFailed after four tries, so a date
    that could not be read is retried, never silently skipped."""
    for attempt in range(4):
        try:
            r = requests.get(URL.format(tour=tour), params={"dates": day.strftime("%Y%m%d")},
                             timeout=90)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"ESPN {tour} {day}: HTTP {r.status_code}")
        except requests.RequestException as exc:
            logger.warning(f"ESPN {tour} {day}: {exc}")
        time.sleep(2 ** attempt)
    raise FetchFailed(f"{tour} {day}")


def _season(event_id: str) -> int | None:
    try:
        return int(str(event_id).rsplit("-", 1)[1])
    except (IndexError, ValueError):
        return None


def _player(c: dict) -> tuple:
    a = c.get("athlete") or {}
    flag = (a.get("flag") or {}).get("alt")
    games, tbs = [], []
    for ls in c.get("linescores") or []:
        v = ls.get("value")
        games.append(int(v) if v is not None else None)
        tbs.append(int(ls["tiebreak"]) if ls.get("tiebreak") is not None else None)
    return (str(c.get("id")), a.get("displayName"), flag, bool(c.get("winner")), games, tbs)


def parse(body: dict) -> list[tuple]:
    """Every singles match in one scoreboard answer, in COLS order (minus
    updated_at). Players keep ESPN's order (`order` 1 first)."""
    out = []
    for ev in body.get("events") or []:
        event_id = ev.get("id")
        season = _season(event_id)
        name = ev.get("name") or ""
        major = bool(ev.get("major")) or any(s in name.lower() for s in SLAM_NAMES)
        for g in ev.get("groupings") or []:
            tour = SINGLES.get((g.get("grouping") or {}).get("slug"))
            if not tour:
                continue
            for c in g.get("competitions") or []:
                comps = sorted(c.get("competitors") or [], key=lambda x: x.get("order", 9))
                if len(comps) != 2 or any(x.get("type") != "athlete" for x in comps):
                    continue
                st = (c.get("status") or {}).get("type") or {}
                p1, p2 = _player(comps[0]), _player(comps[1])
                note = ((c.get("notes") or [{}])[0] or {}).get("text")
                out.append((
                    str(c["id"]), tour, season, event_id, name, major,
                    (c.get("round") or {}).get("displayName"), c.get("date"),
                    (c.get("venue") or {}).get("court"), (c.get("venue") or {}).get("fullName"),
                    st.get("name"), bool(st.get("completed")),
                    5 if (major and tour == "ATP") else 3,
                    *p1, *p2, note, bool(c.get("wasSuspended")),
                ))
    return out


_UPSERT = (f"INSERT INTO {TABLE} ({', '.join(COLS[:-1])}) VALUES "
           f"({', '.join(['%s'] * (len(COLS) - 1))}) ON CONFLICT (comp_id) DO UPDATE SET "
           + ", ".join(f"{c} = EXCLUDED.{c}" for c in COLS[1:-1])
           + ", updated_at = NOW()")


def season_dates(tour: str, season: int) -> list[date]:
    """The dates with play in a season, from ESPN's own calendar."""
    try:
        body = fetch(tour, date(season, 6, 15))
    except FetchFailed:
        time.sleep(60)
        body = fetch(tour, date(season, 6, 15))
    cal = ((body.get("leagues") or [{}])[0]).get("calendar") or []
    days = sorted({datetime.fromisoformat(str(d).replace("Z", "+00:00")).date()
                   for d in cal if isinstance(d, str)})
    return [d for d in days if d.year == season or d.month == 12]


def collect(tour: str, days: list[date], rounds: int = 3) -> dict[str, tuple]:
    """Every match on `days`. A date that fails is retried, up to `rounds`
    passes with a minute between them; one still failing stops the run."""
    rows: dict[str, tuple] = {}
    todo = list(days)
    for attempt in range(rounds):
        failed = []
        for d in todo:
            try:
                body = fetch(tour, d)
            except FetchFailed:
                failed.append(d)
                continue
            for r in parse(body):
                rows[r[0]] = r
        if not failed:
            return rows
        logger.warning(f"ESPN {tour}: {len(failed)} dates failed, pass {attempt + 1}")
        todo = failed
        time.sleep(60)
    raise FetchFailed(f"ESPN {tour}: {len(todo)} dates still failing: {todo[:5]}")


def store(conn, rows: list[tuple]) -> int:
    ensure_tables(conn)
    for i in range(0, len(rows), 1000):
        conn.executemany(_UPSERT, rows[i:i + 1000])
        conn.commit()
    return len(rows)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ESPN tennis results -> Supabase")
    ap.add_argument("--seasons", nargs=2, type=int)
    ap.add_argument("--days", type=int, help="the last N days and the next 2")
    ap.add_argument("--store", action="store_true")
    a = ap.parse_args(argv)
    found: dict[str, tuple] = {}
    for tour in TOURS:
        if a.seasons:
            for s in range(a.seasons[0], a.seasons[1] + 1):
                days = season_dates(tour, s)[::CALENDAR_STEP]
                got = collect(tour, days)
                logger.info(f"ESPN {tour} {s}: {len(days)} calls, {len(got)} matches")
                found.update(got)
        if a.days:
            today = datetime.now(timezone.utc).date()
            days = [today + timedelta(days=k) for k in range(-a.days, 3)]
            found.update(collect(tour, days))
    rows = list(found.values())
    print(json.dumps({"matches": len(rows)}))
    if a.store and rows:
        from data.db import get_connection
        conn = get_connection()
        try:
            store(conn, rows)
        finally:
            conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
