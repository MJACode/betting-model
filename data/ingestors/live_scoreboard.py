"""Live scores for the app's Scoreboard: NFL, NBA, NHL, NCAAB and NCAABW,
from ESPN, and EuroLeague from EuroLeague's own live API.

EuroLeague (mike, 2026-11-25: "Why don't I see euroleague in the live feed"):
ESPN does not carry it, so its games went from Upcoming to Final on the
Scoreboard and no in-play line was ever read for them. Its state comes from
live.euroleague.net/api/PlayByPlay, the answer the halftime loop already
reads (data/ingestors/euroleague_live_feed.py): `Live`, the quarter arrays
with each play's running score (A is the home club) and the quarter's clock
counting down from 10:00, an 'EP' at a quarter's end and an 'EG' at the
game's (read off E2026 game 110, tests/fixtures/euroleague_live). One call per
game in progress, one at a time, never inside the halftime loop's read
window (EUROLEAGUE_QUIET_S), so this can never be what rate-limits a bet.

Matt, 2026-11-15: the Scoreboard covers every sport with games, and men's and
women's college basketball get live scores now. Their games are matched to
ours by ESPN's event id (ncaab_events / ncaabw_events, written with the games
rows by the ESPN schedule ingestors), never by team names: 300+ Division I
schools have no three-letter code. Measured 2026-11-15: all 149 NCAAB and 162
NCAABW games on 11-14..11-16 had an event row. Their scoreboards are asked
for Division I (groups=50) with limit=500, the parameters the in-play loops
(data/ingestors/ncaab_live_feed.py) already use from the worker.

Matt, 2026-10-29: the Scoreboard should show every game for a sport, live
games and their scores included. MLB (live_game_state) and NCAAF
(ncaaf_live_states) already store in-progress state. These three stored
nothing until the final score landed on `games`, so a game in progress
showed as upcoming.

One ESPN site scoreboard call per sport for each ET date on the slate, each
tick: today, plus yesterday until 6 am ET. ESPN answers HTTP 400 to a
YYYYMMDD-YYYYMMDD range (NBA, NHL and NFL, measured 2026-10-30), so the dates
are asked for one at a time. The calls are made only while that sport has a
game that has started, has no final score on `games`, and has no final row
here yet. A tick with nothing live is one database read.

Reachability, measured 2026-10-29 from api_call_log: site.api.espn.com
answered the worker 200 on 3,164 scheduler calls in the 7 days before, the
NBA scoreboard among them. The older notes in this repo that call it 403 from
the worker are out of date. A non-200 is logged and the tick moves on.

The table holds one row per game, the latest state, upserted every tick
(the "state table the writer maintains" shape in
.claude/rules/data-integrity.md). Only in-progress and completed games are
written. A pre-game event writes nothing.

Shape read here, pinned by saved ESPN payloads: NBA under
tests/fixtures/espn_nba_scoreboard_*.json, NFL under
espn_nfl_scoreboard_2026-10-18.json and 2026-10-19.json, NHL under
espn_nhl_scoreboard_2026-10-24.json and 2026-10-27.json.
events[].{id, date, status.{period, displayClock, type.{state, name,
completed, shortDetail}}, competitions[0].{competitors[].{id, homeAway,
score, team.{id, abbreviation, displayName}}, situation.{possession,
downDistanceText, shortDownDistanceText}}}.
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Iterable
from zoneinfo import ZoneInfo

from loguru import logger

SPORT_PATHS: dict[str, str] = {
    "NFL": "football/nfl",
    "NBA": "basketball/nba",
    "NHL": "hockey/nhl",
    "NCAAB": "basketball/mens-college-basketball",
    "NCAABW": "basketball/womens-college-basketball",
}
# Extra query parameters per sport. Without groups=50 the college scoreboard
# lists ESPN's featured games only, not every Division I game.
SPORT_PARAMS: dict[str, dict[str, Any]] = {
    "NCAAB": {"groups": 50, "limit": 500},
    "NCAABW": {"groups": 50, "limit": 500},
}
# Sports whose ESPN events map to our games by event id, through this table.
EVENT_TABLES: dict[str, str] = {
    "NCAAB": "ncaab_events",
    "NCAABW": "ncaabw_events",
}
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/{path}/scoreboard"

# A game is polled from this long before its listed start, so the first
# in-progress tick is not missed when the start time is a few minutes early.
LEAD = timedelta(minutes=10)
# And for this long after it. No game on this board runs past it; a game
# still unsettled after it is a feed or settlement problem, not a live game.
TAIL = timedelta(hours=7)

_ET = ZoneInfo("America/New_York")

# ESPN abbreviations that are not ours. Names are tried first.
# NHL scoreboards say UTA (measured 2026-10-24 and 2026-10-27). The teams
# list says UTAH (measured the same day). Both have to become UTA.
_NFL_ABBREV = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}
_NHL_ABBREV = {"LA": "LAK", "TB": "TBL", "SJ": "SJS", "NJ": "NJD", "UTAH": "UTA"}


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


def _known(code: str, ours: set[str]) -> str | None:
    """An ESPN abbreviation that is not one of our ids is not a team id.
    Passing LAR or UTAH through made match_games drop the game."""
    return code if code in ours else None


def team_code(sport: str, abbrev: str | None, name: str | None) -> str | None:
    """Our team id for an ESPN team, or None when it is not one of ours."""
    a = (abbrev or "").upper().strip()
    n = " ".join((name or "").split())
    if sport == "NBA":
        from data.ingestors.nba_espn_box import nba_team
        return nba_team(a, n)
    if sport == "NFL":
        from config import NFL_ODDS_API_MAP
        code = NFL_ODDS_API_MAP.get(n) or _NFL_ABBREV.get(a) or a
        return _known(code, set(NFL_ODDS_API_MAP.values()))
    if sport == "NHL":
        from data.ingestors.odds_ingestor import NHL_ODDS_API_MAP
        code = NHL_ODDS_API_MAP.get(n) or _NHL_ABBREV.get(a) or a
        return _known(code, set(NHL_ODDS_API_MAP.values()))
    return None


def _side_label(side: dict | None) -> str:
    if not side:
        return "?"
    return f"{side.get('abbrev') or '?'} ({side.get('name') or 'no name'})"


def clock_label(sport: str, status: dict) -> str:
    """'Q3 7:42', '2H 5:10', 'Half', 'End P2', 'OT 3:10', 'Final'. ESPN's
    own short detail when the period is missing. Men's college basketball
    plays two halves; women's plays four quarters, like the NBA."""
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
    regulation = {"NHL": 3, "NCAAB": 2}.get(sport, 4)
    if period > regulation:
        n = period - regulation
        if sport == "NHL" and n >= 2 and "SHOOTOUT" in (name + short.upper()):
            tag = "SO"
        else:
            tag = "OT" if n == 1 else f"OT{n}"
    elif sport == "NCAAB":
        tag = f"{period}H"
    else:
        tag = f"{'P' if sport == 'NHL' else 'Q'}{period}"
    if "END_PERIOD" in name or short.lower().startswith("end of"):
        return f"End {tag}"
    if "SHOOTOUT" in name:
        return "SO"
    return f"{tag} {clock}".strip() if clock else tag


def parse_scoreboard(sport: str, data: dict) -> list[dict]:
    """In-progress and completed games on one ESPN scoreboard, one dict each.

    A pre-game event, a postponed or cancelled one, and an event whose teams
    are not two of ours are dropped. Scores are None when ESPN leaves them
    out; nothing is filled in. A sport in EVENT_TABLES is not mapped by team
    here: match_games maps it by event id, so its codes are ESPN's own.
    """
    by_event = sport in EVENT_TABLES
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
                "code": (team.get("abbreviation") or team.get("displayName") or "?")
                if by_event else
                team_code(sport, team.get("abbreviation"), team.get("displayName")),
                "abbrev": team.get("abbreviation"),
                "name": team.get("displayName"),
                "ids": {str(x) for x in (c.get("id"), team.get("id")) if x is not None},
                "score": _int(c.get("score")),
            }
        home, away = sides.get("home"), sides.get("away")
        if not home or not away or not home["code"] or not away["code"]:
            logger.warning(
                f"live_scoreboard {sport}: unmapped ESPN team "
                f"{_side_label(away)} @ {_side_label(home)}"
            )
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


def match_games(sport: str, rows: list[dict], games: Iterable[dict],
                event_games: dict[str, str] | None = None) -> list[dict]:
    """Attach our game_id to each parsed row. Unmatched rows are dropped and
    logged once per tick: an event we do not carry is not a game to show.

    A sport in EVENT_TABLES matches on ESPN's event id only (`event_games`,
    event id -> our game_id). With no map it matches nothing."""
    by_teams: dict[tuple[str, str], list[dict]] = {}
    by_id: dict[str, dict] = {}
    for g in games:
        if g.get("sport") != sport:
            continue
        by_teams.setdefault((g.get("home_team"), g.get("away_team")), []).append(g)
        by_id[g.get("game_id")] = g
    out, missed = [], []
    for row in rows:
        if sport in EVENT_TABLES:
            pick = by_id.get((event_games or {}).get(str(row.get("event_id"))))
        else:
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
    # One call per ET date. The slate is today, plus yesterday in the
    # early-morning window (config.live_slate_dates), and the site scoreboard
    # answers HTTP 400 to a YYYYMMDD-YYYYMMDD range: every call from 00:00 ET
    # on 2026-10-30 was refused, and the late games stopped updating. A date
    # that fails does not cost the other its events.
    events: list = []
    answered = False
    for day in sorted(d.replace("-", "") for d in dates):
        try:
            r = requests.get(url, params={"dates": day, **SPORT_PARAMS.get(sport, {})},
                             headers=ESPN_HEADERS, timeout=10)
        except Exception as exc:                              # noqa: BLE001
            logger.warning(f"live_scoreboard {sport} {day}: fetch failed: {exc}")
            continue
        if r.status_code != 200:
            logger.warning(f"live_scoreboard {sport} {day}: HTTP {r.status_code}")
            continue
        try:
            data = r.json()
        except ValueError:
            logger.warning(f"live_scoreboard {sport} {day}: response was not JSON")
            continue
        answered = True
        events.extend((data or {}).get("events") or [])
    return {"events": events} if answered else None


UPSERT_SQL = """
INSERT INTO public.live_scoreboard
    (game_id, sport, game_date, event_id, state, home_score, away_score,
     period, clock_label, situation, possession, snapshot_at, source)
VALUES
    (%(game_id)s, %(sport)s, %(game_date)s, %(event_id)s, %(state)s,
     %(home_score)s, %(away_score)s, %(period)s, %(clock_label)s,
     %(situation)s, %(possession)s, %(snapshot_at)s, %(source)s)
ON CONFLICT (game_id) DO UPDATE SET
    source = EXCLUDED.source,
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


def _event_games(conn, sport: str, game_ids: list[str]) -> dict[str, str]:
    """ESPN event id -> our game_id for these games, from the sport's events
    table. The table name comes from EVENT_TABLES, never from input."""
    if not game_ids:
        return {}
    table = EVENT_TABLES[sport]
    rows = conn.execute(
        f"SELECT espn_event_id::text, game_id FROM public.{table} "
        "WHERE game_id = ANY(%(ids)s)",
        {"ids": game_ids},
    ).fetchall()
    return {str(r[0]): r[1] for r in rows}


# ── EuroLeague, from EuroLeague's own live API ───────────────────────────────

EUROLEAGUE = "EUROLEAGUE"
_EL_ID = re.compile(r"^EUROLEAGUE_(E\d{4})_(\d+)$")
_EL_QUARTERS = ("FirstQuarter", "SecondQuarter", "ThirdQuarter", "ForthQuarter", "ExtraTime")
# The halftime loop reads EuroLeague's API at each five-minute mark plus
# models.euroleague_live_ht.FETCH_AFTER_SEC (37 s), three calls a game and
# three more after the odds call, PAUSE_S apart; Cloudflare refused four
# calls at once (HTTP 429, 2026-11-13) and a refusal backs that loop off 30 s.
# So no Scoreboard call is made from 25 s to 110 s after a mark: with this job
# on the minute, one tick in five skips EuroLeague, and its row stays inside
# the app's 10-minute freshness window.
EUROLEAGUE_QUIET_S = (25, 110)


def euroleague_quiet(now: datetime) -> bool:
    """True inside the halftime loop's read window of the five-minute cycle."""
    into = (now.minute % 5) * 60 + now.second
    return EUROLEAGUE_QUIET_S[0] <= into < EUROLEAGUE_QUIET_S[1]


def euroleague_code(game_id: str) -> tuple[str, int] | None:
    m = _EL_ID.match(str(game_id or ""))
    return (m.group(1), int(m.group(2))) if m else None


def _el_plays(pbp: dict, quarter: str) -> list[dict]:
    return [p for p in ((pbp or {}).get(quarter) or []) if isinstance(p, dict)]


def _el_type(play: dict) -> str:
    return str(play.get("PLAYTYPE") or "").strip()


def parse_euroleague(game: dict, pbp: dict | None) -> dict | None:
    """One live_scoreboard row for a EuroLeague game from its PlayByPlay
    answer, or None when it holds no game in progress or finished. Pure.

    A quarter is under way once its 'BP' is logged (the break's substitutions
    are logged in the next quarter's array before it, so an array that is not
    empty is not a quarter begun). The score is the last play that carries
    one; before the first basket of a begun game it is 0-0. The clock is the
    quarter's last stamped MARKERTIME (time left). EuroLeague's A must be our
    home club, else the answer is not used: nothing here turns sides over."""
    if not pbp:
        return None
    home, away = str(pbp.get("CodeTeamA") or "").strip(), str(pbp.get("CodeTeamB") or "").strip()
    if home != game.get("home_team") or away != game.get("away_team"):
        logger.warning(f"live_scoreboard {EUROLEAGUE} {game.get('game_id')}: clubs {away}@{home} "
                       f"are not ours ({game.get('away_team')}@{game.get('home_team')}); not used")
        return None
    quarters = [_el_plays(pbp, q) for q in _EL_QUARTERS]
    plays = [p for q in quarters for p in q]
    ended = any(_el_type(p) == "EG" for p in plays)
    begun = [i for i, q in enumerate(quarters) if any(_el_type(p) == "BP" for p in q)]
    if not begun or (pbp.get("Live") is not True and not ended):
        return None
    cur = begun[-1]
    scored = [p for p in plays if p.get("POINTS_A") is not None and p.get("POINTS_B") is not None]
    home_score = _int(scored[-1]["POINTS_A"]) if scored else 0
    away_score = _int(scored[-1]["POINTS_B"]) if scored else 0
    tag = "OT" if cur == 4 else f"Q{cur + 1}"
    in_play = [p for p in quarters[cur] if _el_type(p) not in ("IN", "OUT")]
    clocks = [str(p.get("MARKERTIME") or "").strip() for p in in_play]
    clock = next((c for c in reversed(clocks) if c), "")
    if ended:
        label = "Final/OT" if quarters[4] else "Final"
    elif in_play and _el_type(in_play[-1]) == "EP":
        label = "Half" if cur == 1 else f"End {tag}"
    else:
        label = f"{tag} {clock}".strip()
    code = euroleague_code(game.get("game_id"))
    return {
        "event_id": str(code[1]) if code else "",
        "game_id": game["game_id"],
        "game_date": game.get("game_date"),
        "sport": EUROLEAGUE,
        "home": home,
        "away": away,
        "home_score": home_score,
        "away_score": away_score,
        "state": "post" if ended else "in",
        "period": cur + 1,
        "clock_label": label,
        "situation": None,
        "possession": None,
    }


def _euroleague_default_fetch() -> Callable[[str, int], dict | None]:
    from data.ingestors.euroleague_live_feed import EuroleagueApi
    api = EuroleagueApi()
    return lambda season, code: api._get("PlayByPlay", season, code)


def _euroleague_tick(conn, games: list[dict], finished: set[str], now: datetime,
                     fetch: Callable[[str, int], dict | None] | None) -> int | None:
    """Rows written for EuroLeague this tick, or None when nothing was due or
    the halftime loop's read window holds the tick off."""
    due = []
    for g in games:
        if g.get("sport") != EUROLEAGUE or g.get("game_id") in finished:
            continue
        if g.get("home_score") is not None and g.get("away_score") is not None:
            continue
        start = _parse_ts(g.get("commence_time"))
        if start is not None and start - LEAD <= now <= start + TAIL:
            due.append(g)
    if not due or euroleague_quiet(now):
        return None
    fetch = fetch or _euroleague_default_fetch()
    stamp = now.isoformat()
    n = 0
    for g in due:
        code = euroleague_code(g["game_id"])
        if code is None:
            continue
        row = parse_euroleague(g, fetch(*code))
        if row is None:
            continue
        conn.execute(UPSERT_SQL, {**row, "snapshot_at": stamp, "source": "euroleague_api"})
        n += 1
    conn.commit()
    return n


def run_once(conn=None, *, now: datetime | None = None,
             fetch: Callable[[str, list[str]], dict | None] | None = None,
             euroleague_fetch: Callable[[str, int], dict | None] | None = None) -> dict:
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
            {"sports": [*SPORT_PATHS, EUROLEAGUE], "dates": dates},
        ).fetchall()]
        if not games:
            return {}
        finished = {r[0] for r in conn.execute(
            "SELECT game_id FROM public.live_scoreboard "
            "WHERE game_date = ANY(%(dates)s) AND state = 'post'",
            {"dates": dates},
        ).fetchall()}
        written: dict[str, int] = {}
        failed: dict[str, str] = {}
        for sport in sorted(due_sports(games, finished, now)):
            # One sport's database error must not cost the sports after it
            # their tick (NBA, NCAAB, NCAABW, NFL, NHL run in that order).
            # Roll back so the connection is usable, write the rest, then
            # raise so the heartbeat still marks the tick failed.
            try:
                data = fetch(sport, dates)
                if data is None:
                    continue
                event_games = (_event_games(conn, sport, [g["game_id"] for g in games
                                                           if g["sport"] == sport])
                               if sport in EVENT_TABLES else None)
                rows = match_games(sport, parse_scoreboard(sport, data), games, event_games)
                stamp = now.isoformat()
                for row in rows:
                    conn.execute(UPSERT_SQL, {**row, "snapshot_at": stamp, "source": "espn_site"})
                conn.commit()
                written[sport] = len(rows)
            except Exception as exc:                          # noqa: BLE001
                conn.rollback()
                failed[sport] = f"{type(exc).__name__}: {exc}"
                logger.error(f"live_scoreboard {sport}: {failed[sport]}")
            time.sleep(0.1)
        try:
            n = _euroleague_tick(conn, games, finished, now, euroleague_fetch)
            if n is not None:
                written[EUROLEAGUE] = n
        except Exception as exc:                              # noqa: BLE001
            conn.rollback()
            failed[EUROLEAGUE] = f"{type(exc).__name__}: {exc}"
            logger.error(f"live_scoreboard {EUROLEAGUE}: {failed[EUROLEAGUE]}")
        if written:
            logger.info(f"live_scoreboard: {written}")
        if failed:
            raise RuntimeError(f"live_scoreboard: failed for {sorted(failed)}; wrote {written}")
        return written
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    print(run_once())
