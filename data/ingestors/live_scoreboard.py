"""Live scores for the app's Scoreboard: NFL, NBA and NHL, from ESPN.

Matt, 2026-10-29: the Scoreboard should show every game for a sport, live
games and their scores included. MLB (live_game_state) and NCAAF
(ncaaf_live_states) already store in-progress state. These three stored
nothing until the final score landed on `games`, so a game in progress
showed as upcoming.

One ESPN site scoreboard call per sport per tick. The call is made only while
that sport has a game that has started, has no final score on `games`, and
has no final row here yet. A tick with nothing live is one database read.

Reachability, measured 2026-10-29 from api_call_log: site.api.espn.com
answered the worker 200 on 3,164 scheduler calls in the 7 days before, the
NBA scoreboard among them. The older notes in this repo that call it 403 from
the worker are out of date. A non-200 is logged and the tick moves on.

The table holds one row per game, the latest state, upserted every tick
(the "state table the writer maintains" shape in
.claude/rules/data-integrity.md). Only in-progress and completed games are
written. A pre-game event writes nothing.

Shape read here (the NBA half is pinned by the saved ESPN payloads under
tests/fixtures/espn_nba_scoreboard_*.json; NFL and NHL use the same site
scoreboard document): events[].{id, date, status.{period, displayClock,
type.{state, name, completed, shortDetail}}, competitions[0].{competitors[].
{id, homeAway, score, team.{id, abbreviation, displayName}}, situation.
{possession, downDistanceText, shortDownDistanceText}}}.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from loguru import logger

SPORT_PATHS: dict[str, str] = {
    "NFL": "football/nfl",
    "NBA": "basketball/nba",
    "NHL": "hockey/nhl",
}
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"

# A game is polled from this long before its listed start, so the first
# in-progress tick is not missed when the start time is a few minutes early.
LEAD = timedelta(minutes=10)
# And for this long after it. No NFL, NBA or NHL game runs past it; a game
# still unsettled after it is a feed or settlement problem, not a live game.
TAIL = timedelta(hours=7)

_ET = ZoneInfo("America/New_York")

# ESPN abbreviations that are not ours. Names are tried first.
_NFL_ABBREV = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
_NHL_ABBREV = {"LA": "LAK", "TB": "TBL", "SJ": "SJS", "NJ": "NJD"}


def _dig(obj: Any, *path: Any) -> Any:
    cur = obj
    for key in path:
        if cur is None:
            return None
        try:
            cur = cur[key]
        except (KeyError, IndexError, TypeError):
            return None
    return cur


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return None


def team_code(sport: str, abbrev: str | None, name: str | None) -> str | None:
    """Our team id for an ESPN team, or None when it is not one of ours."""
    a = (abbrev or "").upper().strip()
    n = " ".join((name or "").split())
    if sport == "NBA":
        from data.ingestors.nba_espn_box import nba_team
        return nba_team(a, n)
    if sport == "NFL":
        from config import NFL_ODDS_API_MAP
        return NFL_ODDS_API_MAP.get(n) or _NFL_ABBREV.get(a) or (a or None)
    if sport == "NHL":
        from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP
        return NHL_ODDS_API_MAP.get(n) or _NHL_ABBREV.get(a) or (a or None)
    return None


def clock_label(sport: str, status: dict) -> str:
    """'Q3 7:42', 'Half', 'End P2', 'OT 3:10', 'Final'. ESPN's own short
    detail when the period is missing."""
    st = status.get("type") or {}
    name = str(st.get("name") or "").upper()
    period = _int(status.get("period"))
    clock = str(status.get("displayClock") or "").strip()
    short = str(st.get("shortDetail") or st.get("detail") or "").strip()
    if st.get("state") == "post":
        return short or "Final"
    if "HALFTIME" in name:
        return "Half"
    if period is None:
        return short
    regulation = 3 if sport == "NHL" else 4
    letter = "P" if sport == "NHL" else "Q"
    if period > regulation:
        n = period - regulation
        if sport == "NHL" and n >= 2 and "SHOOTOUT" in (name + short.upper()):
            tag = "SO"
        else:
            tag = "OT" if n == 1 else f"OT{n}"
    else:
        tag = f"{letter}{period}"
    if "END_PERIOD" in name or short.lower().startswith("end of"):
        return f"End {tag}"
    if "SHOOTOUT" in name:
        return "SO"
    return f"{tag} {clock}".strip() if clock else tag


def parse_scoreboard(sport: str, data: dict) -> list[dict]:
    """In-progress and completed games on one ESPN scoreboard, one dict each.

    A pre-game event, a postponed or cancelled one, and an event whose teams
    are not two of ours are dropped. Scores are None when ESPN leaves them
    out; nothing is filled in.
    """
    out: list[dict] = []
    for ev in (data or {}).get("events") or []:
        status = ev.get("status") or _dig(ev, "competitions", 0, "status") or {}
        st = status.get("type") or {}
        state = st.get("state")
        name = str(st.get("name") or "").upper()
        if state not in ("in", "post"):
            continue
        if state == "post" and (not st.get("completed")
                                or "POSTPONED" in name or "CANCEL" in name):
            continue
        comp = _dig(ev, "competitions", 0) or {}
        sides: dict[str, dict] = {}
        for c in comp.get("competitors") or []:
            side = c.get("homeAway")
            if side not in ("home", "away"):
                continue
            team = c.get("team") or {}
            sides[side] = {
                "code": team_code(sport, team.get("abbreviation"), team.get("displayName")),
                "ids": {str(x) for x in (c.get("id"), team.get("id")) if x is not None},
                "score": _int(c.get("score")),
            }
        home, away = sides.get("home"), sides.get("away")
        if not home or not away or not home["code"] or not away["code"]:
            continue
        situation = comp.get("situation") or {}
        poss_id = situation.get("possession")
        possession = None
        if state == "in" and poss_id is not None:
            if str(poss_id) in home["ids"]:
                possession = "home"
            elif str(poss_id) in away["ids"]:
                possession = "away"
        detail = None
        if sport == "NFL" and state == "in":
            detail = (situation.get("downDistanceText")
                      or situation.get("shortDownDistanceText") or None)
        out.append({
            "event_id": str(ev.get("id") or ""),
            "event_date": et_date(ev.get("date")),
            "home": home["code"],
            "away": away["code"],
            "home_score": home["score"],
            "away_score": away["score"],
            "state": state,
            "period": _int(status.get("period")),
            "clock_label": clock_label(sport, status),
            "situation": detail,
            "possession": possession,
        })
    return out


def et_date(iso_ts: Any) -> str | None:
    s = str(iso_ts or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ET).strftime("%Y-%m-%d")


def _parse_ts(v: Any) -> datetime | None:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    s = str(v or "").strip()
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def due_sports(games: Iterable[dict], finished: set[str], now: datetime) -> set[str]:
    """Sports with a game that could be in progress now.

    Started (inside LEAD), not past TAIL, no final score on `games`, and no
    completed row stored here yet.
    """
    out: set[str] = set()
    for g in games:
        sport = g.get("sport")
        if sport not in SPORT_PATHS or g.get("game_id") in finished:
            continue
        if g.get("home_score") is not None and g.get("away_score") is not None:
            continue
        start = _parse_ts(g.get("commence_time"))
        if start is None:
            continue
        if start - LEAD <= now <= start + TAIL:
            out.add(sport)
    return out


def match_games(sport: str, rows: list[dict], games: Iterable[dict]) -> list[dict]:
    """Attach our game_id to each parsed row. Unmatched rows are dropped and
    logged once per tick: an event we do not carry is not a game to show."""
    by_teams: dict[tuple[str, str], list[dict]] = {}
    for g in games:
        if g.get("sport") != sport:
            continue
        by_teams.setdefault((g.get("home_team"), g.get("away_team")), []).append(g)
    out, missed = [], []
    for row in rows:
        cands = by_teams.get((row["home"], row["away"])) or []
        pick = next((g for g in cands if g.get("game_date") == row.get("event_date")), None)
        if pick is None and len(cands) == 1:
            pick = cands[0]
        if pick is None:
            missed.append(f"{row['away']}@{row['home']}")
            continue
        out.append({**row, "game_id": pick["game_id"], "game_date": pick["game_date"],
                    "sport": sport})
    if missed:
        logger.info(f"live_scoreboard {sport}: no games row for {', '.join(missed)}")
    return out


def _default_fetch(sport: str, dates: list[str]) -> dict | None:
    import requests
    from data.ingestors.injury_ingestor import ESPN_HEADERS

    url = SCOREBOARD_URL.format(path=SPORT_PATHS[sport])
    # ESPN's date range is YYYYMMDD-YYYYMMDD. The slate is today, plus
    # yesterday in the early-morning window (config.live_slate_dates).
    days = sorted(d.replace("-", "") for d in dates)
    params = {"dates": days[0] if len(days) == 1 else f"{days[0]}-{days[-1]}"}
    try:
        r = requests.get(url, params=params, headers=ESPN_HEADERS, timeout=10)
    except Exception as exc:                                  # noqa: BLE001
        logger.warning(f"live_scoreboard {sport}: fetch failed: {exc}")
        return None
    if r.status_code != 200:
        logger.warning(f"live_scoreboard {sport}: HTTP {r.status_code}")
        return None
    try:
        return r.json()
    except ValueError:
        logger.warning(f"live_scoreboard {sport}: response was not JSON")
        return None


UPSERT_SQL = """
INSERT INTO public.live_scoreboard
    (game_id, sport, game_date, event_id, state, home_score, away_score,
     period, clock_label, situation, possession, snapshot_at, source)
VALUES
    (%(game_id)s, %(sport)s, %(game_date)s, %(event_id)s, %(state)s,
     %(home_score)s, %(away_score)s, %(period)s, %(clock_label)s,
     %(situation)s, %(possession)s, %(snapshot_at)s, 'espn_site')
ON CONFLICT (game_id) DO UPDATE SET
    state = EXCLUDED.state,
    home_score = EXCLUDED.home_score,
    away_score = EXCLUDED.away_score,
    period = EXCLUDED.period,
    clock_label = EXCLUDED.clock_label,
    situation = EXCLUDED.situation,
    possession = EXCLUDED.possession,
    snapshot_at = EXCLUDED.snapshot_at,
    event_id = EXCLUDED.event_id
"""


def run_once(conn=None, *, now: datetime | None = None,
             fetch: Callable[[str, list[str]], dict | None] | None = None) -> dict:
    """One tick. Returns {sport: rows written} for the sports it polled."""
    from config import live_slate_dates

    now = now or datetime.now(timezone.utc)
    fetch = fetch or _default_fetch
    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    try:
        if conn.execute(
            "SELECT to_regclass('public.live_scoreboard') IS NOT NULL"
        ).fetchone()[0] is not True:
            logger.info("live_scoreboard: table not created yet; nothing written")
            return {}
        dates = live_slate_dates(now.astimezone(_ET))
        cols = ("game_id", "sport", "game_date", "home_team", "away_team",
                "home_score", "away_score", "commence_time")
        games = [dict(zip(cols, r)) for r in conn.execute(
            "SELECT game_id, sport, game_date::text, home_team, away_team, "
            "home_score, away_score, commence_time::text FROM public.games "
            "WHERE sport = ANY(%(sports)s) AND game_date::text = ANY(%(dates)s)",
            {"sports": list(SPORT_PATHS), "dates": dates},
        ).fetchall()]
        if not games:
            return {}
        finished = {r[0] for r in conn.execute(
            "SELECT game_id FROM public.live_scoreboard "
            "WHERE game_date = ANY(%(dates)s) AND state = 'post'",
            {"dates": dates},
        ).fetchall()}
        written: dict[str, int] = {}
        for sport in sorted(due_sports(games, finished, now)):
            data = fetch(sport, dates)
            if data is None:
                continue
            rows = match_games(sport, parse_scoreboard(sport, data), games)
            stamp = now.isoformat()
            for row in rows:
                conn.execute(UPSERT_SQL, {**row, "snapshot_at": stamp})
            conn.commit()
            written[sport] = len(rows)
            time.sleep(0.1)
        if written:
            logger.info(f"live_scoreboard: {written}")
        return written
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(run_once())
