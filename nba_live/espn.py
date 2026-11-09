"""ESPN's NBA scoreboard and game summary (free), parsed for the in-play loop.

WHY site.api AND NOT core. The lab's play-by-play is the sportsdataverse ESPN
release (scripts/nba_ingame_data.py, through data/ingestors/nba_pbp.slim_plays),
and that release is ESPN's game-summary `plays` array, one row per play with
the same fields renamed: id, sequenceNumber, type.id / type.text, text,
awayScore / homeScore, period.number, clock.displayValue, scoringPlay,
scoreValue, team.id, participants[0..2].athlete.id, wallclock, shootingPlay,
coordinate.x / .y, pointsAttempted (records_from_summary below maps them back,
and scripts/nba_live_espn_check.py compares the two field by field). Reading the
same document live is what makes the live state the lab's state.

REACHABILITY, MEASURED. site.api.espn.com refused the Railway worker with 403
from 2026-08-05 (data/ingestors/wnba_results_ingestor.py). In api_call_log for
2026-10-10..17 it answered the WORKER service ('pipeline' source) 200 on 1,942
of 1,944 calls -- the WNBA summary and NBA teams endpoints among them, no 403.
No call from the POLLERS service is on record, so the loop runs on the worker
(scheduler._PIPELINE_JOBS). Every call goes through monitoring/probe.py, so a
403 shows in api_call_log under source 'nba-live-ingame' the first night.

    scoreboard  events[].{id, date, season.type (2 regular season),
                status.type.{state pre|in|post, completed}, status.period,
                competitions[0].competitors[].{homeAway, team.{id,
                abbreviation, location, displayName}}}
    summary     header.{season.{year, type}, competitions[0].{date, status,
                competitors[]}}, plays[], boxscore.players[].{team,
                statistics[0].athletes[].{athlete.{id, displayName}, starter}}
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

log = logging.getLogger(__name__)

SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
REGULAR_SEASON = 2


@dataclass(frozen=True)
class EspnEvent:
    event_id: int
    date: str | None          # ISO UTC tip as ESPN lists it
    season_type: int | None
    state: str                # 'pre' | 'in' | 'post'
    completed: bool
    period: int | None
    home_abbr: str | None
    away_abbr: str | None
    home_name: str | None
    away_name: str | None


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _sides(comp: dict) -> tuple[dict, dict]:
    home = away = {}
    for c in comp.get("competitors") or []:
        if c.get("homeAway") == "home":
            home = c
        elif c.get("homeAway") == "away":
            away = c
    return home, away


def parse_scoreboard(j: dict) -> list[EspnEvent]:
    out = []
    for e in (j or {}).get("events") or []:
        comp = (e.get("competitions") or [{}])[0]
        home, away = _sides(comp)
        st = (e.get("status") or comp.get("status") or {})
        typ = st.get("type") or {}
        out.append(EspnEvent(
            event_id=_int(e.get("id")), date=e.get("date"),
            season_type=_int((e.get("season") or {}).get("type")),
            state=str(typ.get("state") or ""), completed=bool(typ.get("completed")),
            period=_int(st.get("period")),
            home_abbr=(home.get("team") or {}).get("abbreviation"),
            away_abbr=(away.get("team") or {}).get("abbreviation"),
            home_name=(home.get("team") or {}).get("location"),
            away_name=(away.get("team") or {}).get("location")))
    return [e for e in out if e.event_id is not None]


def summary_status(j: dict) -> dict:
    """{'state', 'completed', 'period'} from a summary's header."""
    comp = (((j or {}).get("header") or {}).get("competitions") or [{}])[0]
    st = comp.get("status") or {}
    typ = st.get("type") or {}
    return {"state": str(typ.get("state") or ""), "completed": bool(typ.get("completed")),
            "period": _int(st.get("period"))}


def records_from_summary(j: dict) -> list[dict]:
    """The summary's plays as sportsdataverse ESPN rows (PBP_SOURCE_COLS of
    data/ingestors/nba_pbp.py), in the order ESPN lists them, so that
    nba_pbp.slim_plays and nba_ingame_data.plays_frame read them exactly as
    they read the release the lab was built from."""
    head = (j or {}).get("header") or {}
    comp = (head.get("competitions") or [{}])[0]
    home, away = _sides(comp)
    ht, at = home.get("team") or {}, away.get("team") or {}
    season = head.get("season") or {}
    base = {
        "home_team_id": _int(ht.get("id")), "away_team_id": _int(at.get("id")),
        "home_team_abbrev": ht.get("abbreviation"), "away_team_abbrev": at.get("abbreviation"),
        "home_team_name": ht.get("location"), "away_team_name": at.get("location"),
        "game_date": (comp.get("date") or "")[:10] or None,
        "season": _int(season.get("year")), "season_type": _int(season.get("type")),
        "game_id": _int(comp.get("id") or head.get("id")),
    }
    rows = []
    for p in (j or {}).get("plays") or []:
        parts = [((x or {}).get("athlete") or {}).get("id") for x in (p.get("participants") or [])]
        parts += [None] * (3 - len(parts))
        coord = p.get("coordinate") or {}
        typ = p.get("type") or {}
        per = p.get("period") or {}
        clk = p.get("clock") or {}
        rows.append({
            **base,
            "sequence_number": p.get("sequenceNumber"),
            "type_id": _int(typ.get("id")), "type_text": typ.get("text"),
            "text": p.get("text"),
            "away_score": _int(p.get("awayScore")), "home_score": _int(p.get("homeScore")),
            "period_number": _int(per.get("number")),
            "clock_display_value": clk.get("displayValue"),
            "clock_minutes": None, "clock_seconds": None,
            "scoring_play": bool(p.get("scoringPlay")),
            "score_value": _int(p.get("scoreValue")),
            "team_id": _int((p.get("team") or {}).get("id")),
            "athlete_id_1": _int(parts[0]), "athlete_id_2": _int(parts[1]),
            "athlete_id_3": _int(parts[2]),
            "wallclock": p.get("wallclock"),
            "shooting_play": bool(p.get("shootingPlay")),
            "coordinate_x_raw": coord.get("x"), "coordinate_y_raw": coord.get("y"),
            "points_attempted": _int(p.get("pointsAttempted")),
        })
    return rows


def starters_from_summary(j: dict) -> list[dict]:
    """Every athlete in the summary's box: {'team_abbr', 'athlete_id', 'name',
    'starter'}. Live, ESPN marks the five starters once the game is under way."""
    out = []
    for team in ((j or {}).get("boxscore") or {}).get("players") or []:
        abbr = (team.get("team") or {}).get("abbreviation")
        for stat in (team.get("statistics") or [])[:1]:
            for a in stat.get("athletes") or []:
                ath = a.get("athlete") or {}
                aid = _int(ath.get("id"))
                if aid is None:
                    continue
                out.append({"team_abbr": abbr, "athlete_id": aid,
                            "name": ath.get("displayName"), "starter": bool(a.get("starter"))})
    return out


class EspnClient:
    """Two GETs, both free. Each returns None on any failure (logged), never a
    stale copy: a pass decides on this pass's document or not at all."""

    def __init__(self, session=None, timeout: float = 15.0):
        self._session = session
        self.timeout = timeout
        self.calls = 0
        self.failures = 0

    def _get(self, url: str, params: dict) -> dict | None:
        import requests
        s = self._session or requests
        self.calls += 1
        try:
            r = s.get(url, params=params, timeout=self.timeout)
            if getattr(r, "status_code", 200) != 200:
                self.failures += 1
                log.warning("ESPN %s answered %s", url.rsplit("/", 1)[-1], r.status_code)
                return None
            return r.json()
        except Exception as exc:                      # noqa: BLE001
            self.failures += 1
            log.warning("ESPN %s failed: %s", url.rsplit("/", 1)[-1], exc)
            return None

    def scoreboard(self, yyyymmdd: str) -> list[EspnEvent] | None:
        j = self._get(SCOREBOARD_URL, {"dates": yyyymmdd})
        return None if j is None else parse_scoreboard(j)

    def summary(self, event_id: int) -> dict | None:
        return self._get(SUMMARY_URL, {"event": str(event_id)})
