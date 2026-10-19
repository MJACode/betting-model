"""NBA scoreboard and box-score parsers for ESPN, for the worker.

`nba_api` reads stats.nba.com, which blocks the worker, so NBA finals and
player box scores on the worker come from ESPN's site API instead. This module
holds the PURE parsers (fixture-tested, no I/O); the writer that uses them is
`data/ingestors/nba_results_ingestor.py`, the `nba-results` pipeline step.

ESPN team codes differ from ours (GS, NO, NY, SA, UTAH, WSH); they are mapped
through nba_stats_ingestor's table. An event whose teams are not two NBA teams
(an international preseason opponent, an All-Star side) is dropped here.

Shape (measured 2026-10-15 against the 2026-04-10 slate; fixtures under
tests/fixtures/espn_nba_*.json):
  scoreboard  events[].{id, date (UTC), season.type (1 pre, 2 regular, 3 post,
              5 play-in), status.{period, type.completed},
              competitions[0].competitors[].{homeAway, score,
              team.{abbreviation, displayName}}}
  summary     boxscore.players[].{team.{abbreviation, displayName},
              statistics[0].{labels[], totals[], athletes[].{athlete.{id,
              displayName}, starter, didNotPlay, reason, stats[]}}}
  ESPN puts `reason: "COACH'S DECISION"` on EVERY athlete, including the ones
  who played. It means something only when didNotPlay is true, so that is the
  only place it is read. Players ruled out before the game (inactive) are not
  in the box at all.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data.ingestors.nba_stats_ingestor import (
    _NBA_ABBREV_MAP, _NBA_NAME_MAP, _build_game_id,
)
from data.ingestors.wnba_results_ingestor import (
    _min_to_float, _split_made_att, _to_int,
)

ESPN_NBA_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
)
ESPN_NBA_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
)

_ET = ZoneInfo("America/New_York")
_NBA_CODES = frozenset(_NBA_ABBREV_MAP.values())

# ESPN season.type values. Preseason is never ours to score.
SEASON_TYPE_PRESEASON = 1


def nba_team(abbrev: str | None, name: str | None = "") -> str | None:
    """Our 3-letter code for an ESPN team, or None when it is not an NBA team.

    Unlike nba_stats_ingestor._norm_nba this never passes an unknown code
    through: a preseason game against an overseas club must not become a game
    row with a made-up team.
    """
    a = (abbrev or "").upper().strip()
    code = _NBA_ABBREV_MAP.get(a) or _NBA_NAME_MAP.get(name or "")
    return code if code in _NBA_CODES else None


def et_date(iso_ts: str | None) -> str | None:
    """'2026-04-11T02:30Z' -> '2026-04-10' (the ET calendar date), or None."""
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


def parse_nba_scoreboard(data: dict, game_date: str) -> list[dict]:
    """Completed games between two NBA teams, one dict each.

    `game_date` is the ET date the scoreboard was asked for. The game's own
    date is the ET date of its tip (the event's UTC timestamp); when that is
    missing the requested date is used. `went_to_ot` is 1 when ESPN counts more
    than four periods, None when it does not say.
    """
    out = []
    for ev in (data or {}).get("events") or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        status = ev.get("status") or {}
        if not bool((status.get("type") or {}).get("completed")):
            continue
        home = away = None
        home_score = away_score = None
        for c in comp.get("competitors") or []:
            team = c.get("team") or {}
            code = nba_team(team.get("abbreviation"), team.get("displayName"))
            if c.get("homeAway") == "home":
                home, home_score = code, _to_int(c.get("score"))
            elif c.get("homeAway") == "away":
                away, away_score = code, _to_int(c.get("score"))
        if not home or not away:
            continue
        gdate = et_date(ev.get("date")) or game_date
        period = _to_int(status.get("period"))
        season_type = _to_int((ev.get("season") or {}).get("type"))
        out.append({
            "event_id": str(ev.get("id") or ""),
            "game_id": _build_game_id(gdate, away, home),
            "game_date": gdate,
            "home": home,
            "away": away,
            "home_score": home_score,
            "away_score": away_score,
            "period": period,
            "went_to_ot": (1 if period > 4 else 0) if period else None,
            "season_type": season_type,
            "commence_time": ev.get("date"),
        })
    return out


def _team_blocks(data: dict):
    """(our team code, labels index, athletes) per team in a summary's box."""
    for team_block in ((data or {}).get("boxscore") or {}).get("players") or []:
        team_info = team_block.get("team") or {}
        team = nba_team(team_info.get("abbreviation"), team_info.get("displayName"))
        if not team:
            continue
        blocks = team_block.get("statistics") or []
        if not blocks:
            continue
        block = blocks[0]
        labels = [str(x).upper() for x in (block.get("labels") or block.get("names") or [])]
        yield team, {lab: i for i, lab in enumerate(labels)}, block


_COUNTING = ("PTS", "REB", "AST", "STL", "BLK", "TO", "OREB", "DREB", "PF")


def _no_minutes(row: list, idx: dict) -> bool:
    """ESPN lists some benched players with MIN '--' and every count zero,
    without didNotPlay. stats.nba.com has no row for them (2 of 2 such rows,
    2026-04-01..12, e.g. DaQuan Jeffries in NBA_2026-04-05_LAC_SAC), and a prop
    on a player who never checked in is void, so they are treated as DNP."""
    def stat(label):
        i = idx.get(label)
        return row[i] if i is not None and i < len(row) else None

    if _min_to_float(stat("MIN")) is not None:
        return False
    for label in _COUNTING:
        v = _to_int(stat(label))
        if v:
            return False
    for label in ("FG", "3PT", "FT"):
        _m, a = _split_made_att(stat(label))
        if a:
            return False
    return True


def _played(ath: dict, idx: dict) -> bool:
    if ath.get("didNotPlay"):
        return False
    row = ath.get("stats") or []
    return bool(row) and not _no_minutes(row, idx)


def parse_nba_box(data: dict) -> list[dict]:
    """Every athlete who played, stats read BY LABEL. DNP, empty and
    no-minutes rows are omitted. `starter` stays a bool here; the row written
    to Postgres uses 0/1."""
    out = []
    for team, idx, block in _team_blocks(data):
        def stat(row, label, idx=idx):
            i = idx.get(label)
            return row[i] if i is not None and i < len(row) else None

        for ath in block.get("athletes") or []:
            if not _played(ath, idx):
                continue
            row = ath.get("stats") or []
            a = ath.get("athlete") or {}
            name = a.get("displayName") or ""
            if not name:
                continue
            fg_m, fg_a = _split_made_att(stat(row, "FG"))
            fg3_m, fg3_a = _split_made_att(stat(row, "3PT"))
            ft_m, ft_a = _split_made_att(stat(row, "FT"))
            out.append({
                "espn_id": str(a.get("id") or ""),
                "name": name,
                "team": team,
                "starter": bool(ath.get("starter")),
                "minutes": _min_to_float(stat(row, "MIN")),
                "points": _to_int(stat(row, "PTS")),
                "rebounds": _to_int(stat(row, "REB")),
                "offensive_reb": _to_int(stat(row, "OREB")),
                "defensive_reb": _to_int(stat(row, "DREB")),
                "assists": _to_int(stat(row, "AST")),
                "steals": _to_int(stat(row, "STL")),
                "blocks": _to_int(stat(row, "BLK")),
                "turnovers": _to_int(stat(row, "TO")),
                "fg_made": fg_m, "fg_att": fg_a,
                "fg3_made": fg3_m, "fg3_att": fg3_a,
                "ft_made": ft_m, "ft_att": ft_a,
            })
    return out


NO_MINUTES_REASON = "NO MINUTES"


def parse_nba_dnp(data: dict) -> list[dict]:
    """Athletes ESPN lists as did-not-play, with the reason it gives
    ("COACH'S DECISION", an injury note...), plus the no-minutes rows
    parse_nba_box leaves out (reason NO MINUTES). Inactive players are not
    listed by ESPN at all."""
    out = []
    for team, idx, block in _team_blocks(data):
        for ath in block.get("athletes") or []:
            if _played(ath, idx) or not (ath.get("didNotPlay") or ath.get("stats")):
                continue
            a = ath.get("athlete") or {}
            name = a.get("displayName") or ""
            if not name:
                continue
            if ath.get("didNotPlay"):
                reason = ath.get("reason")
                reason = str(reason).strip() if reason else None
            else:
                reason = NO_MINUTES_REASON
            out.append({
                "espn_id": str(a.get("id") or ""),
                "name": name,
                "team": team,
                "reason": reason,
            })
    return out


def box_team_totals(data: dict) -> dict[str, int]:
    """{team: points} from the box's own team totals row, for reconciliation."""
    out = {}
    for team, idx, block in _team_blocks(data):
        i = idx.get("PTS")
        totals = block.get("totals") or []
        if i is not None and i < len(totals):
            pts = _to_int(totals[i])
            if pts is not None:
                out[team] = pts
    return out


def fill_missing(dates_to_games: dict[str, dict[str, set[str]]], *, get_json=None,
                 connect=None) -> dict:
    """Log the box of every final on these dates that is not logged yet.

    Called by settlement (data/ingestors/prop_box_scores.py) with
    `{date: {game_id: {player_id, ...}}}` for games that have a score and an
    unsettled prop but no log. It used to write a game only when every needed
    player resolved by name, which meant a rookie's game was never logged. It
    now runs the same writer as the `nba-results` step, so there is one opinion
    about how an NBA box is logged: every player, with an `espn:<id>` id when
    no NBA.com id can be found (nba_results_ingestor's docstring).
    """
    if not dates_to_games:
        return {"games": 0, "skipped": 0, "errors": 0}
    from data.ingestors.nba_results_ingestor import ingest_nba_results

    totals = ingest_nba_results(dates=sorted(dates_to_games), get_json=get_json,
                                connect=connect, raise_on_error=False)
    return {"games": totals.get("box_games", 0),
            "skipped": totals.get("not_in_games", 0),
            "errors": totals.get("errors", 0)}
