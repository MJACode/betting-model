"""NBL schedule, finals, quarter scores, box scores and play-by-play from ESPN.

THE SOURCE. ESPN's site API, free, no key, league 55 (`basketball/nbl`):
  * scoreboard?dates=<YYYY>&limit=1000 -- every NBL event of one CALENDAR year,
    played or scheduled, with its UTC start, both clubs, the score, each
    side's quarter and overtime line scores, the venue and ESPN's own season
    label and type (preseason, regular-season, post-season). A season spans
    two calendar years (September to March), so a season is two calls.
    Measured 2026-11-14: served from the 2022-23 season (nothing in 2021-22's
    calendar year); 2027's call already holds the rest of the 2026-27 regular
    season to 2027-02-14, so the schedule is stored months ahead from the
    first run. The ranged form `dates=YYYYMMDD-YYYYMMDD` answers HTTP 400 for
    this league.
  * summary?event=<id> -- one game: both teams' and every player's box score,
    the header, and 400-500 plays (period, game clock, running score, team,
    play type, shooter, shot location). No wall-clock time on any play
    (`wallclockAvailable` False), no referees, attendance 0 (read 2026-11-14 on
    event 401875310).

WHAT IS WRITTEN, one transaction per calendar year:
  * nbl_espn_raw: each event's scoreboard JSON as fetched, once per change of
    its content (source SOURCE), so a change in ESPN cannot rewrite what was
    read.
  * nbl_teams: each club code, its ESPN id, newest name and every name.
  * nbl_events: one row an event, every season type.
  * games: one row per regular-season or finals game between two NBL clubs
    that is not cancelled or postponed, sport NBL, the home club's code as
    home_team, the score filled once the game is final (a stored score is
    never overwritten), went_to_ot, regulation_tie, home_win.
  * nbl_period_scores: quarters 1-4 and each overtime as period 5, 6 ... for
    every final game, checked to sum to the final score.
And, per final game not yet held (--summaries):
  * nbl_espn_summaries: the box score, the header and the plays (each play's
    text dropped; every other field kept), once per change of content.

STALE EVENTS. A past event ESPN still lists as scheduled (a postponed game
replayed under another id) is kept in nbl_events with its status and never
reaches `games`: an event is a league game only once it is final, in play, or
still in the future (STALE_AFTER).

    python -m data.ingestors.nbl_espn --seasons 2023 2027            # dry run
    python -m data.ingestors.nbl_espn --seasons 2023 2027 --apply --summaries
    python -m data.ingestors.nbl_espn --current --apply --summaries  # the worker's step
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timedelta, timezone

import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.db import get_connection
from data.ingestors import nbl_teams as nt

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nbl"
SOURCE = "espn_nbl"
FIRST_SEASON = 2023            # 2022-23, the first season ESPN serves
HEADERS = {"User-Agent": "Mozilla/5.0 (Signalbase)", "Accept": "application/json"}
FINAL = "STATUS_FINAL"
DEAD = frozenset({"STATUS_CANCELED", "STATUS_POSTPONED", "STATUS_FORFEIT"})
STALE_AFTER = timedelta(hours=36)
SUMMARY_GAP_S = 0.5            # between summary calls
# Events ESPN labels regular-season that are not league games, each measured.
# 401707730: Cairns v Sydney on 2024-09-09, ten days before the 2024-25 season
# opened (2024-09-19); with it those two clubs show 30 regular-season games and
# every other club 29, the season's real count (read 2026-11-14).
NOT_LEAGUE_GAMES = {401707730: "a 2024-09-09 preseason game labelled regular-season"}

RAW = "nbl_espn_raw"
RAW_COLS = ("espn_id", "sha1", "payload", "fetched_at")
RAW_DDL = """
CREATE TABLE IF NOT EXISTS nbl_espn_raw (
    espn_id     BIGINT NOT NULL,
    sha1        TEXT NOT NULL,
    payload     JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (espn_id, sha1)
)
"""
PERIODS = "nbl_period_scores"
PERIOD_COLS = ("game_id", "period", "home_points", "away_points", "season", "source",
               "loaded_at")
PERIODS_DDL = """
CREATE TABLE IF NOT EXISTS nbl_period_scores (
    game_id      TEXT NOT NULL,
    period       INTEGER NOT NULL,
    home_points  INTEGER NOT NULL,
    away_points  INTEGER NOT NULL,
    season       INTEGER NOT NULL,
    source       TEXT NOT NULL,
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, period)
)
"""
SUMMARIES = "nbl_espn_summaries"
SUMMARY_COLS = ("game_id", "espn_id", "sha1", "payload", "fetched_at")
SUMMARIES_DDL = """
CREATE TABLE IF NOT EXISTS nbl_espn_summaries (
    game_id     TEXT NOT NULL,
    espn_id     BIGINT NOT NULL,
    sha1        TEXT NOT NULL,
    payload     JSONB NOT NULL,
    fetched_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (game_id, sha1)
)
"""

_RAW_INSERT = f"""
INSERT INTO {RAW} (espn_id, sha1, payload) VALUES (%s, %s, %s::jsonb)
ON CONFLICT (espn_id, sha1) DO NOTHING
"""
_TEAM_UPSERT = f"""
INSERT INTO {nt.TEAMS} (code, espn_id, name, names, first_season, last_season, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (code) DO UPDATE SET
    name = CASE WHEN EXCLUDED.last_season >= COALESCE({nt.TEAMS}.last_season, 0)
                THEN EXCLUDED.name ELSE {nt.TEAMS}.name END,
    names = ARRAY(SELECT DISTINCT unnest({nt.TEAMS}.names || EXCLUDED.names) ORDER BY 1),
    first_season = LEAST({nt.TEAMS}.first_season, EXCLUDED.first_season),
    last_season = GREATEST({nt.TEAMS}.last_season, EXCLUDED.last_season),
    updated_at = NOW()
"""
_EVENT_UPSERT = f"""
INSERT INTO {nt.EVENTS} (game_id, espn_id, season, season_type, game_date, commence_time,
                         home_code, away_code, home_espn_id, away_espn_id, neutral_site,
                         status, played, venue_name, venue_city, updated_at)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON CONFLICT (game_id) DO UPDATE SET
    season = EXCLUDED.season, season_type = EXCLUDED.season_type,
    game_date = EXCLUDED.game_date, commence_time = EXCLUDED.commence_time,
    home_code = EXCLUDED.home_code, away_code = EXCLUDED.away_code,
    home_espn_id = EXCLUDED.home_espn_id, away_espn_id = EXCLUDED.away_espn_id,
    neutral_site = EXCLUDED.neutral_site, status = EXCLUDED.status,
    played = EXCLUDED.played, venue_name = EXCLUDED.venue_name,
    venue_city = EXCLUDED.venue_city, updated_at = NOW()
"""
_GAME_UPSERT = """
INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time,
                   neutral_site, data_source, created_at, updated_at)
VALUES (%s, 'NBL', %s, %s, %s, %s, %s, %s, %s, NOW()::TEXT, NOW()::TEXT)
ON CONFLICT (game_id) DO UPDATE SET
    season = EXCLUDED.season, game_date = EXCLUDED.game_date,
    home_team = EXCLUDED.home_team, away_team = EXCLUDED.away_team,
    commence_time = EXCLUDED.commence_time, neutral_site = EXCLUDED.neutral_site,
    updated_at = NOW()::TEXT
WHERE games.sport = 'NBL'
"""
# A stored score is never overwritten: the WHERE refuses a row that has one.
_SCORE_FILL = """
UPDATE games SET home_score = %s, away_score = %s, home_win = %s, went_to_ot = %s,
                 regulation_tie = %s, updated_at = NOW()::TEXT
 WHERE game_id = %s AND sport = 'NBL'
   AND (home_score IS NULL OR away_score IS NULL)
"""
_PERIOD_INSERT = f"""
INSERT INTO {PERIODS} (game_id, period, home_points, away_points, season, source)
VALUES (%s, %s, %s, %s, %s, %s)
ON CONFLICT (game_id, period) DO NOTHING
"""
_SUMMARY_INSERT = f"""
INSERT INTO {SUMMARIES} (game_id, espn_id, sha1, payload) VALUES (%s, %s, %s, %s::jsonb)
ON CONFLICT (game_id, sha1) DO NOTHING
"""


def ensure_tables(conn) -> None:
    nt.ensure_tables(conn)
    changed = False
    for name, cols, ddl in ((RAW, RAW_COLS, RAW_DDL), (PERIODS, PERIOD_COLS, PERIODS_DDL),
                            (SUMMARIES, SUMMARY_COLS, SUMMARIES_DDL)):
        if not schema_is_current(conn, name, columns=cols, rls=True, revoked_from=API_ROLES):
            conn.execute(ddl)
            lock_down(conn, name)
            changed = True
    if changed:
        conn.commit()


# ── fetch and parse ──────────────────────────────────────────────────────────

def fetch_year(year: int, session=None) -> dict:
    s = session or requests
    r = s.get(f"{BASE}/scoreboard", params={"dates": str(year), "limit": 1000},
              headers=HEADERS, timeout=60)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, dict) or not isinstance(body.get("events"), list):
        raise RuntimeError(f"{year}: unexpected answer shape {type(body).__name__}")
    return body


def fetch_summary(espn_id, session=None) -> dict:
    s = session or requests
    r = s.get(f"{BASE}/summary", params={"event": str(espn_id)}, headers=HEADERS, timeout=60)
    r.raise_for_status()
    return r.json()


def _int(v) -> int | None:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _ts(v) -> datetime | None:
    if not v:
        return None
    t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def parse_event(e: dict, known_codes: dict[int, str] | None = None) -> dict:
    """One scoreboard event -> the row values. Pure.

    `known_codes` maps ESPN team id -> club code for clubs that carry no
    abbreviation on this event (none seen, kept for safety); a club with no
    abbreviation and no known code is outside the league and has code None."""
    comp = e["competitions"][0]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    if set(sides) != {"home", "away"}:
        raise ValueError(f"{e.get('id')}: competitors {sorted(sides)}")
    season = int(e["season"]["year"])
    season_type = e["season"].get("slug") or str(e["season"].get("type"))
    start = _ts(e.get("date"))
    # ESPN dates an NBL game in UTC; the local (Australian) day is the game's
    # date, and an evening tip in Perth is still the same UTC day, so the UTC
    # date plus 10 hours (AEST) is the calendar day the league printed.
    local = (start + timedelta(hours=10)).date().isoformat() if start else ""
    if local and nt.season_label_for_date(local) != season:
        raise ValueError(f"{e.get('id')}: ESPN season {season} for a game on {local}")
    status = ((e.get("status") or {}).get("type") or {}).get("name")
    known_codes = known_codes or {}

    def club(c):
        t = c["team"]
        tid = int(t["id"])
        return tid, (t.get("abbreviation") or known_codes.get(tid)), t.get("displayName")

    (hid, hcode, hname), (aid, acode, aname) = club(sides["home"]), club(sides["away"])
    venue = comp.get("venue") or {}
    row = {
        "espn_id": int(e["id"]), "game_id": nt.build_game_id(e["id"]), "season": season,
        "season_type": season_type, "game_date": local,
        "commence_time": start.isoformat() if start else None,
        "home_code": hcode, "away_code": acode, "home_espn_id": hid, "away_espn_id": aid,
        "home_name": hname, "away_name": aname,
        "neutral_site": bool(comp.get("neutralSite")), "status": status,
        "played": status == FINAL, "venue_name": venue.get("fullName"),
        "venue_city": (venue.get("address") or {}).get("city"),
        "home_score": None, "away_score": None, "periods": [],
    }
    if status == FINAL:
        hp = [_int(x.get("value")) for x in sides["home"].get("linescores") or []]
        ap = [_int(x.get("value")) for x in sides["away"].get("linescores") or []]
        hs, as_ = _int(sides["home"].get("score")), _int(sides["away"].get("score"))
        if (None in hp or None in ap or len(hp) != len(ap)
                or len(hp) < nt.REGULATION_PERIODS):
            raise ValueError(f"{e['id']}: incomplete line scores {hp} / {ap}")
        if sum(hp) != hs or sum(ap) != as_:
            raise ValueError(f"{e['id']}: periods {sum(hp)}-{sum(ap)} do not sum to {hs}-{as_}")
        row.update(home_score=hs, away_score=as_,
                   periods=[(i + 1, h, a) for i, (h, a) in enumerate(zip(hp, ap))])
    return row


def parse_events(events: list[dict]) -> tuple[list[dict], list[tuple[str, str]]]:
    """(the rows, [(ESPN id, why)] for events refused). An event ESPN shows
    final before its line scores are filled in, or with a label that does not
    match its date, is refused and left for the next pass, so one bad event
    never stops the season's other games from being stored."""
    rows, refused = [], []
    for e in events:
        try:
            rows.append(parse_event(e))
        except (ValueError, KeyError, TypeError) as exc:
            refused.append((str(e.get("id")), str(exc)))
    return rows, refused


def results(row: dict) -> tuple | None:
    """(home_win, went_to_ot, regulation_tie) for a final game, else None."""
    if row["home_score"] is None:
        return None
    reg_h = sum(h for p, h, _ in row["periods"] if p <= nt.REGULATION_PERIODS)
    reg_a = sum(a for p, _, a in row["periods"] if p <= nt.REGULATION_PERIODS)
    ot = int(len(row["periods"]) > nt.REGULATION_PERIODS)
    if ot != int(reg_h == reg_a):
        raise ValueError(f"{row['espn_id']}: overtime {ot} but regulation {reg_h}-{reg_a}")
    return int(row["home_score"] > row["away_score"]), ot, int(reg_h == reg_a)


def is_league_game(row: dict, now: datetime) -> bool:
    """A regular-season or finals game between two NBL clubs that is final,
    under way, or still to come; never a cancelled, postponed or stale one."""
    if row["season_type"] not in nt.LEAGUE_SEASON_TYPES:
        return False
    if row["espn_id"] in NOT_LEAGUE_GAMES:
        return False
    if not row["home_code"] or not row["away_code"]:
        return False
    if row["status"] in DEAD:
        return False
    if row["status"] == FINAL:
        return True
    start = _ts(row["commence_time"])
    return start is not None and start > now - STALE_AFTER


# ── store ────────────────────────────────────────────────────────────────────

def _digest(obj) -> tuple[str, str]:
    payload = json.dumps(obj, sort_keys=True)
    return payload, hashlib.sha1(payload.encode()).hexdigest()


def store_year(conn, body: dict, now: datetime | None = None) -> dict:
    """One calendar year's answer into the database, one transaction."""
    now = now or datetime.now(timezone.utc)
    events = body["events"]
    rows, refused = parse_events(events)
    for eid, why in refused:
        logger.warning(f"NBL ESPN event {eid} refused this pass: {why}")
    stats = {"events": len(rows), "league_games": 0, "final": 0, "period_rows": 0,
             "stale_or_dead": 0, "refused": len(refused)}
    if not rows:
        return stats
    clubs: dict[str, dict] = {}
    for r in rows:
        for code, tid, name in ((r["home_code"], r["home_espn_id"], r["home_name"]),
                                (r["away_code"], r["away_espn_id"], r["away_name"])):
            if not code:
                continue
            c = clubs.setdefault(code, {"espn_id": tid, "names": set(), "first": r["season"],
                                        "last": r["season"]})
            if c["espn_id"] != tid:
                raise ValueError(f"club {code}: two ESPN ids {c['espn_id']} and {tid}")
            if name:
                c["names"].add(name)
            c["first"] = min(c["first"], r["season"])
            c["last"] = max(c["last"], r["season"])
    for e in events:
        payload, digest = _digest(e)
        conn.execute(_RAW_INSERT, (int(e["id"]), digest, payload))
    conn.executemany(_TEAM_UPSERT, [(code, c["espn_id"], sorted(c["names"])[-1],
                                     sorted(c["names"]), c["first"], c["last"])
                                    for code, c in clubs.items() if c["names"]])
    conn.executemany(_EVENT_UPSERT, [(
        r["game_id"], r["espn_id"], r["season"], r["season_type"], r["game_date"],
        r["commence_time"], r["home_code"], r["away_code"], r["home_espn_id"],
        r["away_espn_id"], r["neutral_site"], r["status"], r["played"], r["venue_name"],
        r["venue_city"]) for r in rows])
    league = [r for r in rows if is_league_game(r, now)]
    stats["league_games"] = len(league)
    stats["stale_or_dead"] = sum(1 for r in rows
                                 if r["season_type"] in nt.LEAGUE_SEASON_TYPES
                                 and r["home_code"] and r["away_code"]
                                 and not is_league_game(r, now))
    conn.executemany(_GAME_UPSERT, [(r["game_id"], r["season"], r["game_date"], r["home_code"],
                                     r["away_code"], r["commence_time"],
                                     int(r["neutral_site"]), SOURCE) for r in league])
    fills, periods = [], []
    for r in league:
        res = results(r)
        if res is None:
            continue
        stats["final"] += 1
        fills.append((r["home_score"], r["away_score"], *res, r["game_id"]))
        periods += [(r["game_id"], p_, h, a, r["season"], SOURCE) for p_, h, a in r["periods"]]
    if fills:
        conn.executemany(_SCORE_FILL, fills)
    if periods:
        conn.executemany(_PERIOD_INSERT, periods)
    stats["period_rows"] = len(periods)
    conn.commit()
    return stats


def compact_summary(js: dict) -> dict:
    """What nbl_espn_summaries keeps of a summary: the box score, the header,
    and every play with its text dropped (the text is most of the bytes and
    repeats the play's type, shooter and points)."""
    plays = [{k: v for k, v in p.items() if k not in ("text", "shortDescription")}
             for p in js.get("plays") or []]
    return {"boxscore": js.get("boxscore"), "header": js.get("header"),
            "format": js.get("format"), "gameInfo": js.get("gameInfo"), "plays": plays}


def due_summaries(conn, seasons: list[int]) -> list[tuple[str, int]]:
    """(game_id, espn_id) of final league games in these seasons with no
    stored summary."""
    rows = conn.execute(
        f"SELECT e.game_id, e.espn_id FROM {nt.EVENTS} e "
        f"WHERE e.season = ANY(%s) AND e.status = %s AND e.season_type = ANY(%s) "
        f"AND e.home_code IS NOT NULL AND e.away_code IS NOT NULL "
        f"AND e.espn_id <> ALL(%s) "
        f"AND NOT EXISTS (SELECT 1 FROM {SUMMARIES} s WHERE s.game_id = e.game_id) "
        f"ORDER BY e.commence_time",
        (seasons, FINAL, sorted(nt.LEAGUE_SEASON_TYPES), sorted(NOT_LEAGUE_GAMES))).fetchall()
    return [(r[0], int(r[1])) for r in rows]


def store_summaries(conn, seasons: list[int], limit: int | None = None) -> dict:
    due = due_summaries(conn, seasons)
    if limit is not None:
        due = due[:limit]
    stats = {"due": len(due), "stored": 0, "failed": 0}
    with requests.Session() as s:
        for game_id, espn_id in due:
            try:
                js = fetch_summary(espn_id, s)
                if not (js.get("boxscore") or {}).get("players"):
                    raise RuntimeError("no player box")
                payload, digest = _digest(compact_summary(js))
                conn.execute(_SUMMARY_INSERT, (game_id, espn_id, digest, payload))
                conn.commit()
                stats["stored"] += 1
            except Exception as exc:                            # noqa: BLE001
                conn.rollback()
                stats["failed"] += 1
                logger.warning(f"NBL summary {game_id}: {exc}")
            time.sleep(SUMMARY_GAP_S)
    return stats


def current_season_label(now: datetime | None = None) -> int:
    """The season in progress by the calendar: from July the season that ends
    next year. Only picks which calendar years the step asks for."""
    now = now or datetime.now(timezone.utc)
    return now.year + 1 if now.month >= 7 else now.year


def years_for(seasons: list[int]) -> list[int]:
    """The calendar years a set of ending-year seasons spans."""
    return sorted({y for s in seasons for y in (s - 1, s)})


def club_counts(rows: list[dict], now: datetime | None = None) -> dict[int, dict[str, int]]:
    """Regular-season league games per club per season: every club plays the
    same number in an NBL season, so a club apart from the rest names an event
    to look at (it found NOT_LEAGUE_GAMES)."""
    now = now or datetime.now(timezone.utc)
    out: dict[int, dict[str, int]] = {}
    for r in rows:
        if r["season_type"] != "regular-season" or not is_league_game(r, now):
            continue
        d = out.setdefault(r["season"], {})
        for c in (r["home_code"], r["away_code"]):
            d[c] = d.get(c, 0) + 1
    return out


def run(seasons: list[int], apply: bool, summaries: bool = False) -> list[dict]:
    out = []
    with requests.Session() as s:
        bodies = [(y, fetch_year(y, s)) for y in years_for(seasons)]
    every = parse_events([e for _, b in bodies for e in b["events"]])[0]
    for season, d in sorted(club_counts([r for r in every if r["season"] in seasons]).items()):
        if len(set(d.values())) > 1:
            logger.warning(f"NBL {season}: clubs' regular-season counts differ {sorted(d.items())}")
    for year, body in bodies:
        rows = parse_events(body["events"])[0]
        rows = [r for r in rows if r["season"] in seasons]
        body = {**body, "events": [e for e in body["events"]
                                   if int(e["season"]["year"]) in seasons]}
        by = {}
        for r in rows:
            k = (r["season"], r["season_type"], r["status"])
            by[k] = by.get(k, 0) + 1
        print(f"NBL {year}: {len(rows)} events " + ", ".join(
            f"{s_}/{t}/{st}={n}" for (s_, t, st), n in sorted(by.items())))
        if not apply:
            continue
        with get_connection() as conn:
            ensure_tables(conn)
            st = store_year(conn, body)
        logger.info(f"NBL ESPN store {year}: {st}")
        out.append(st)
    if apply and summaries:
        with get_connection() as conn:
            ensure_tables(conn)
            st = store_summaries(conn, seasons)
        logger.info(f"NBL ESPN summaries: {st}")
        out.append(st)
    if not apply:
        print("dry run: nothing written (add --apply)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="NBL games, finals, quarter scores from ESPN")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                   help="ending-year labels, e.g. 2023 2027")
    g.add_argument("--current", action="store_true", help="the season in progress only")
    ap.add_argument("--apply", action="store_true", help="write to the database")
    ap.add_argument("--summaries", action="store_true",
                    help="also store the box score and plays of each final game not yet held")
    a = ap.parse_args(argv)
    seasons = ([current_season_label()] if a.current
               else list(range(max(a.seasons[0], FIRST_SEASON), a.seasons[1] + 1)))
    run(seasons, a.apply, a.summaries)
    return 0


if __name__ == "__main__":
    sys.exit(main())
