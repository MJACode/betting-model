"""DailyFaceoff's starting-goalie archive: who started in goal and WHEN it was known.

WHY. No NHL bet may be made until both starting goalies are confirmed (mike,
2026-10-20; models/nhl_goalie_gate.py). Our own record of when a goalie was
confirmed (`nhl_goalie_designations`) starts 2026-10-24, so no earlier season
can say which games had both goalies confirmed by a given hour. A rule that
decides at noon ET (docs/nhl_sharp_vs_soft.md, "Fewer bets, bigger stakes")
cannot be graded against the goalie rule without it. mike, 2026-11-22: "yes to
all" to backfilling it.

WHAT. DailyFaceoff's date page (https://www.dailyfaceoff.com/starting-goalies/
YYYY-MM-DD, the page `nhl_goalie_designations` already reads for today) keeps
each past date's final card: per team, the goalie, his status, and the news
item behind it, with its time (`newsCreatedAt`) and source link. Measured
2026-11-21 on 38 dates: the archive starts 2021-11-18 (earlier dates show the
current week), game counts match our schedule, and the share of teams with a
news time is 53% (2021-22) rising to 88% (2025-26) and 100% (2026-27). When
the source link is an X post, its id carries the post's own time (the X id's
top bits are milliseconds since 2010-11-04), which is earlier than
DailyFaceoff's write-up.

What it is NOT: the time a starter first became known. The archive keeps the
final status only (a "Likely" before the "Confirmed" is gone), and ESPN
sometimes confirmed earlier (2026-11-19: 3 of 24 teams, by 1.5 to 6.7 hours).

WHERE. `nhl_goalie_archive`, one row per (game_id, team), source
`dailyfaceoff_archive`. Created on --apply (once a run, skipped when already
current), RLS on, anon and authenticated hold nothing. A re-run inserts only
pairs not already stored (ON CONFLICT DO NOTHING), so it never rewrites a row.
Runs on the worker (job type `nhl_goalie_archive`), which owns DATABASE_URL.

    python -m data.ingestors.nhl_goalie_archive                      # dry run: dates, nothing fetched
    python -m data.ingestors.nhl_goalie_archive --apply              # fetch and store every missing date
    python -m data.ingestors.nhl_goalie_archive --apply --start 2025-10-01 --end 2026-04-20
"""
from __future__ import annotations

import argparse
import re
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests
from loguru import logger

from data.ingestors.nhl_goalie_designations import (DAILYFACEOFF_HEADERS, DAILYFACEOFF_URL,
                                                     NO_STARTER, normalize_status,
                                                     parse_dailyfaceoff_page, team_from_name)

ET = ZoneInfo("America/New_York")
TABLE = "nhl_goalie_archive"
SOURCE = "dailyfaceoff_archive"
# The first date DailyFaceoff's page keeps (measured 2026-11-21: 2021-11-17 and
# earlier answer with the current week instead).
FIRST_DATE = "2021-11-18"
# One page every 1.5 s: DailyFaceoff sits behind Cloudflare.
PAUSE_S = 1.5
TIMEOUT_S = 20
# X ids: milliseconds since this epoch in the bits above 22.
_X_EPOCH_MS = 1288834974657
_X_STATUS = re.compile(r"(?:x|twitter)\.com/[^/?#]+/status(?:es)?/(\d+)", re.I)
_DF_STRENGTH = {2: "confirmed", 3: "likely"}

DDL = f"""
CREATE TABLE IF NOT EXISTS nhl_goalie_archive (
    game_id          TEXT NOT NULL,
    team             TEXT NOT NULL,
    side             TEXT NOT NULL,
    page_date        DATE NOT NULL,
    player_name      TEXT,
    source_player_id TEXT,
    status           TEXT NOT NULL,
    news_created_at  TIMESTAMPTZ,
    news_source_name TEXT,
    news_source_url  TEXT,
    post_at          TIMESTAMPTZ,
    source           TEXT NOT NULL DEFAULT '{SOURCE}',
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (game_id, team)
)
"""
_INSERT = f"""
    INSERT INTO nhl_goalie_archive (game_id, team, side, page_date, player_name, source_player_id, status,
                         news_created_at, news_source_name, news_source_url, post_at, source)
    VALUES (%(game_id)s, %(team)s, %(side)s, %(page_date)s, %(player_name)s,
            %(source_player_id)s, %(status)s, %(news_created_at)s, %(news_source_name)s,
            %(news_source_url)s, %(post_at)s, %(source)s)
    ON CONFLICT (game_id, team) DO NOTHING
"""


def x_post_time(url: str | None) -> datetime | None:
    """The time an X post was made, from its id; None for any other link."""
    m = _X_STATUS.search(url or "")
    if not m:
        return None
    ms = (int(m.group(1)) >> 22) + _X_EPOCH_MS
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _ts(raw) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None


def parse_archive(page_props: dict, page_date: str,
                  schedule: dict[tuple[str, str], str]) -> tuple[list[dict], int]:
    """One row per team on a date page whose game is on our schedule.

    `schedule` maps (home, away) to our game_id for that date; a game we do not
    hold is counted and skipped, never given an invented id. Returns (rows,
    games skipped)."""
    rows, skipped = [], 0
    for g in (page_props or {}).get("data") or []:
        home, away = team_from_name(g.get("homeTeamName")), team_from_name(g.get("awayTeamName"))
        game_id = schedule.get((home, away)) if home and away else None
        if not game_id:
            skipped += 1
            continue
        for side, team in (("home", home), ("away", away)):
            name = g.get(f"{side}GoalieName") or None
            raw = g.get(f"{side}NewsStrengthName")
            if raw is None:
                raw = _DF_STRENGTH.get(g.get(f"{side}NewsStrengthId"))
            pid = g.get(f"{side}GoalieId")
            url = g.get(f"{side}NewsSourceUrl") or None
            rows.append({
                "game_id": game_id, "team": team, "side": side, "page_date": page_date,
                "player_name": name,
                "source_player_id": str(pid) if pid not in (None, "") else None,
                "status": normalize_status(raw) if name else NO_STARTER,
                "news_created_at": _ts(g.get(f"{side}NewsCreatedAt")),
                "news_source_name": g.get(f"{side}NewsSourceName") or None,
                "news_source_url": url,
                "post_at": x_post_time(url),
                "source": SOURCE,
            })
    return rows, skipped


def schedule_for(conn, start: str, end: str) -> dict[str, dict[tuple[str, str], str]]:
    """Our NHL games by ET date: {date: {(home, away): game_id}}."""
    out: dict[str, dict] = {}
    for gid, gdate, home, away in conn.execute(
            "SELECT game_id, game_date::text, home_team, away_team FROM games "
            "WHERE sport = 'NHL' AND game_date::text BETWEEN %s AND %s", (start, end)).fetchall():
        out.setdefault(gdate, {})[(home, away)] = gid
    return out


def stored_dates(conn) -> set[str]:
    try:
        return {r[0] for r in conn.execute(f"SELECT DISTINCT page_date::text FROM {TABLE}").fetchall()}
    except Exception:  # noqa: BLE001 — the table is created on --apply, not before
        conn.rollback()
        return set()


def ensure_table(conn) -> None:
    from data.anon_readable import lock_down
    from data.ddl_guard import schema_is_current
    if schema_is_current(conn, TABLE, columns=("post_at", "news_created_at"), rls=True,
                         revoked_from=("anon", "authenticated")):
        return
    conn.execute(DDL)
    lock_down(conn, TABLE)
    conn.commit()


def fetch_page(page_date: str) -> dict:
    resp = requests.get(DAILYFACEOFF_URL.format(date=page_date), headers=DAILYFACEOFF_HEADERS,
                        timeout=TIMEOUT_S)
    resp.raise_for_status()
    return parse_dailyfaceoff_page(resp.text)


def run(start: str, end: str, apply: bool, conn=None, fetch=fetch_page,
        pause_s: float = PAUSE_S) -> dict:
    from data.db import get_connection
    own = conn is None
    conn = conn or get_connection()
    stats = {"dates": 0, "fetched": 0, "rows": 0, "inserted": 0, "games_skipped": 0,
             "failed": [], "with_news_time": 0, "with_post_time": 0}
    try:
        sched = schedule_for(conn, start, end)
        todo = sorted(d for d in sched if d not in stored_dates(conn))
        stats["dates"] = len(todo)
        print(f"{len(sched)} NHL dates {start}..{end}; {len(todo)} not stored yet")
        if not apply:
            print("dry run: nothing fetched. Re-run with --apply.")
            return stats
        ensure_table(conn)
        for d in todo:
            try:
                rows, skipped = parse_archive(fetch(d), d, sched[d])
            except Exception as exc:  # noqa: BLE001 — one bad date never stops the walk
                logger.warning(f"DailyFaceoff archive {d}: not read ({exc!r})")
                stats["failed"].append(d)
                time.sleep(pause_s)
                continue
            stats["fetched"] += 1
            stats["games_skipped"] += skipped
            stats["rows"] += len(rows)
            stats["with_news_time"] += sum(r["news_created_at"] is not None for r in rows)
            stats["with_post_time"] += sum(r["post_at"] is not None for r in rows)
            for r in rows:
                cur = conn.execute(_INSERT, r)
                stats["inserted"] += getattr(cur, "rowcount", 0) or 0
            conn.commit()
            time.sleep(pause_s)
        back = conn.execute(f"SELECT count(*), count(DISTINCT page_date) FROM {TABLE} "
                            "WHERE page_date BETWEEN %s AND %s", (start, end)).fetchone()
        stats["stored_rows"], stats["stored_dates"] = int(back[0]), int(back[1])
    finally:
        if own:
            conn.close()
    shown = stats if len(stats["failed"]) <= 20 else {**stats, "failed": stats["failed"][:20] + ["..."]}
    print(shown)
    return stats


def main(argv: list[str] | None = None) -> dict:
    yesterday = (datetime.now(ET).date() - timedelta(days=1)).isoformat()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--start", default=FIRST_DATE)
    ap.add_argument("--end", default=yesterday)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    for v in (a.start, a.end):
        date.fromisoformat(v)
    return run(max(a.start, FIRST_DATE), min(a.end, yesterday), a.apply)


if __name__ == "__main__":
    main()
