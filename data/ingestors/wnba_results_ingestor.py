"""
wnba_results_ingestor.py — WNBA final scores + box scores via the ESPN hidden API.

Why this exists: nba_api (stats.nba.com) blocks GitHub Actions datacenter IPs, so
WNBA results only landed via the local "Basketball Daily Ingest" Task Scheduler
job — whenever that job lagged, WNBA games kept NULL scores and WNBA picks sat
unsettled for days (sessions 90/94c/96 and the 2026-07-07 red run). ESPN's hidden
API IS reachable from Actions (the daily WNBA injuries step already uses
site.api.espn.com there), so this module makes WNBA settlement fully cloud-native:

  • games                — final scores + home_win for a trailing window, plus a
                           self-heal pass over any recent WNBA game still missing
                           a score (covers days the pipeline itself missed)
  • wnba_player_game_log — per-player box scores (prop settlement + rolling
                           prop features)
  • wnba_team_stats      — season-to-date snapshot REBUILT FROM OUR OWN DB
                           (games + wnba_player_game_log), so the game scorer's
                           team features can't silently freeze if the local
                           nba_api job dies (the bullpen-freeze bug class)

player_id convention (load-bearing): wnba_player_game_log keys players by the
nba_api PLAYER_ID, and prop picks store that id at scoring time — settlement
matches on (player_id, game_id). ESPN uses its own athlete ids, so each ESPN box
row is mapped back to the nba_api id by NORMALIZED PLAYER NAME against existing
log history. Players with no history (true debuts) are skipped with a log line:
they cannot have prop picks anyway (scoring candidates come from the log), and
the local nba_api job backfills them whenever it next runs.

The local Basketball Daily Ingest job stays as the authoritative/redundant
source — every write here is an idempotent upsert, so the two coexist; whichever
runs later simply overwrites with (near-)identical numbers.

ESPN endpoint shape assumptions (documented for a one-line fix, DataGolf
precedent — verified against ESPN's long-stable site.api.espn.com v2 schema):
  scoreboard: events[].{id, date, status.type.completed,
              competitions[0].competitors[].{homeAway, score,
              team.{displayName, abbreviation}}}
  summary:    boxscore.players[].{team.{displayName, abbreviation},
              statistics[0].{labels[], athletes[].{athlete.{id, displayName},
              starter, didNotPlay, stats[]}}}
  stat labels: MIN, FG "m-a", 3PT "m-a", FT "m-a", OREB, DREB, REB, AST, STL,
               BLK, TO, PF, PTS (parsed BY LABEL, never by fixed index)

sports.core.api.espn.com FALLBACK (added 2026-08-11): on 2026-08-05 ESPN's
consumer host site.api.espn.com started answering the Railway worker with
HTTP 403 (IP block) and WNBA finals stopped landing, while the core host
sports.core.api.espn.com kept serving the worker (the daily WNBA injuries
step reads it). When the site.api fetch for a date fails FOR ANY REASON,
that date falls back to the core v2 API and produces the exact same record
shapes, so every downstream writer is untouched. Core shape assumptions
(the $ref-linked v2 schema; every ref is chased defensively and any
unexpected shape skips the row rather than failing the date):
  events list: /v2/sports/basketball/leagues/wnba/events?dates=A-B
               → items[].{$ref}  (queried as a 2-day range and filtered
               client-side by ET date, so ET-vs-UTC bucketing can't drop a
               late tip)
  event doc:   {id, date, competitions[0].{id, date, status{$ref→type.completed},
               competitors[].{id, homeAway, team{$ref→abbreviation,displayName},
               score{$ref→value}, roster{$ref}}}}
  roster doc:  entries[].{starter, didNotPlay, athlete{$ref→id,displayName},
               statistics{$ref}}
  stats doc:   splits.categories[].stats[].{name, abbreviation, value}
               (resolved BY NAME with abbreviation fallback, never by index)

Usage:
    python -m data.ingestors.wnba_results_ingestor                    # trailing window
    python -m data.ingestors.wnba_results_ingestor --date 2026-07-05  # one date
"""

import argparse
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from data.db import get_connection, DBConnection
from data.ingestors.injury_ingestor import ESPN_HEADERS
from data.ingestors.wnba_stats_ingestor import (
    _norm_wnba, _build_game_id, _safe, _upsert_player_log, _upsert_team_stats,
)

ESPN_WNBA_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
)
ESPN_WNBA_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/summary"
)
CORE_WNBA_EVENTS_URL = (
    "https://sports.core.api.espn.com/v2/sports/basketball/leagues/wnba/events"
)

REQUEST_SLEEP = 0.4      # be polite between per-event summary calls
CORE_REQUEST_SLEEP = 0.1  # per core-API call ($ref chasing makes many small calls)
LOOKBACK_DAYS = 3        # always re-check the last N days' finals
HEAL_DAYS = 14           # also re-fetch any recent WNBA game still missing a score

_ET = ZoneInfo("America/New_York")


# ── Pure parsers (fixture-testable, no I/O) ───────────────────────────────────

def _to_int(val):
    try:
        if val is None:
            return None
        return int(str(val).strip())
    except (TypeError, ValueError):
        return None


def _split_made_att(val) -> tuple:
    """ESPN shooting stats come as 'made-attempted' strings, e.g. '5-11'."""
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", str(val or ""))
    if not m:
        return None, None
    return int(m.group(1)), int(m.group(2))


def _min_to_float(val):
    """ESPN MIN is usually whole minutes ('32'); tolerate '32:30' and '--'."""
    s = str(val or "").strip()
    if not s or s in ("--", "-"):
        return None
    if ":" in s:
        try:
            mins, secs = s.split(":", 1)
            return round(int(mins) + int(secs) / 60.0, 1)
        except ValueError:
            return None
    try:
        return float(s)
    except ValueError:
        return None


def norm_player_name(name: str) -> str:
    """Normalize a player name for cross-source matching (ESPN ↔ nba_api):
    strip accents, punctuation, and common suffixes; lowercase; collapse space."""
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", " ").replace("'", "").replace("-", " ")
    s = re.sub(r"\b(jr|sr|ii|iii|iv)\b", " ", s)
    return " ".join(s.split())


def parse_scoreboard(data: dict, game_date: str) -> list:
    """
    Parse an ESPN scoreboard payload into per-game records.

    Returns [{event_id, game_id, home, away, home_score, away_score, home_win,
              completed, commence_time}] — only games where both teams resolve
    to our canonical abbrevs. game_id uses the REQUESTED date (the scoreboard
    is queried per ET date), matching odds_ingestor's WNBA_{date}_{away}_{home}.
    """
    out = []
    for ev in (data or {}).get("events", []) or []:
        comps = ev.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        completed = bool(((ev.get("status") or {}).get("type") or {}).get("completed"))
        home = away = None
        home_score = away_score = None
        for c in comp.get("competitors", []) or []:
            team = c.get("team") or {}
            abbrev = _norm_wnba(team.get("abbreviation", ""),
                                team.get("displayName", ""))
            score = _to_int(c.get("score"))
            if c.get("homeAway") == "home":
                home, home_score = abbrev, score
            elif c.get("homeAway") == "away":
                away, away_score = abbrev, score
        if not home or not away:
            continue
        home_win = None
        if completed and home_score is not None and away_score is not None:
            home_win = 1 if home_score > away_score else 0
        out.append({
            "event_id":      str(ev.get("id", "")),
            "game_id":       _build_game_id(game_date, away, home),
            "game_date":     game_date,
            "season":        int(game_date[:4]),
            "home":          home,
            "away":          away,
            "home_score":    home_score if completed else None,
            "away_score":    away_score if completed else None,
            "home_win":      home_win,
            "completed":     completed,
            "commence_time": ev.get("date"),
        })
    return out


def parse_summary_boxscore(data: dict) -> list:
    """
    Parse an ESPN game-summary payload's boxscore into per-player stat dicts.

    Returns [{espn_id, name, team, starter, minutes, points, rebounds,
              offensive_reb, defensive_reb, assists, steals, blocks, turnovers,
              fg_made, fg_att, fg3_made, fg3_att, ft_made, ft_att}].
    Players marked didNotPlay (or with an empty stats row) are skipped.
    Stats are resolved BY LABEL so a column reorder can't corrupt values.
    """
    out = []
    for team_block in ((data or {}).get("boxscore") or {}).get("players", []) or []:
        team_info = team_block.get("team") or {}
        team = _norm_wnba(team_info.get("abbreviation", ""),
                          team_info.get("displayName", ""))
        stats_blocks = team_block.get("statistics") or []
        if not stats_blocks:
            continue
        block = stats_blocks[0]
        labels = [str(x).upper() for x in (block.get("labels") or block.get("names") or [])]
        idx = {lab: i for i, lab in enumerate(labels)}

        def stat(row, label):
            i = idx.get(label)
            return row[i] if i is not None and i < len(row) else None

        for ath in block.get("athletes", []) or []:
            if ath.get("didNotPlay"):
                continue
            row = ath.get("stats") or []
            if not row:
                continue
            a = ath.get("athlete") or {}
            fg_m, fg_a = _split_made_att(stat(row, "FG"))
            fg3_m, fg3_a = _split_made_att(stat(row, "3PT"))
            ft_m, ft_a = _split_made_att(stat(row, "FT"))
            out.append({
                "espn_id":       str(a.get("id", "")),
                "name":          a.get("displayName", ""),
                "team":          team,
                "starter":       bool(ath.get("starter")),
                "minutes":       _min_to_float(stat(row, "MIN")),
                "points":        _to_int(stat(row, "PTS")),
                "rebounds":      _to_int(stat(row, "REB")),
                "offensive_reb": _to_int(stat(row, "OREB")),
                "defensive_reb": _to_int(stat(row, "DREB")),
                "assists":       _to_int(stat(row, "AST")),
                "steals":        _to_int(stat(row, "STL")),
                "blocks":        _to_int(stat(row, "BLK")),
                "turnovers":     _to_int(stat(row, "TO")),
                "fg_made":       fg_m, "fg_att": fg_a,
                "fg3_made":      fg3_m, "fg3_att": fg3_a,
                "ft_made":       ft_m, "ft_att": ft_a,
            })
    return out


# ── sports.core.api.espn.com fallback parsers ─────────────────────────────────
# Pure given an injected `fetch(url) -> dict` (a dict lookup in tests); the
# production fetch is _get_core_json. Any shape surprise skips the row/event.

def _et_date(iso_ts):
    """UTC event timestamp ('2026-08-11T00:00Z') → ET calendar date, or None."""
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


def _deref(obj, fetch, need: str) -> dict:
    """Resolve a core-API field that may be inline or a {'$ref': url} link.
    Fetches only when the needed key is absent; non-dicts resolve to {}."""
    if not isinstance(obj, dict):
        return {}
    if need in obj:
        return obj
    ref = obj.get("$ref")
    if ref:
        return fetch(ref) or {}
    return obj


def parse_core_event(ev: dict, game_date: str, fetch):
    """
    One core-API event doc → the same per-game record parse_scoreboard emits,
    plus 'core_rosters' ({our_abbrev: roster_ref}) for the box-score pass.
    Returns None for events outside the requested ET date (the 2-day range
    query can include neighbours) or with unresolvable teams. Score refs are
    only chased for completed games.
    """
    comps = (ev or {}).get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    et = _et_date(comp.get("date") or ev.get("date"))
    if et is not None and et != game_date:
        return None
    ev_id = str(ev.get("id", ""))
    comp_id = str(comp.get("id", "") or ev_id)
    status = _deref(comp.get("status") or ev.get("status") or {}, fetch, need="type")
    completed = bool(((status or {}).get("type") or {}).get("completed"))
    home = away = None
    home_score = away_score = None
    rosters = {}
    for c in comp.get("competitors", []) or []:
        team = _deref(c.get("team") or {}, fetch, need="abbreviation")
        abbrev = _norm_wnba(team.get("abbreviation", ""),
                            team.get("displayName", "") or team.get("name", ""))
        score = None
        if completed:
            sdoc = _deref(c.get("score") or {}, fetch, need="value")
            val = sdoc.get("value")
            score = (int(val) if isinstance(val, (int, float))
                     else _to_int(sdoc.get("displayValue")))
        side = c.get("homeAway")
        if side == "home":
            home, home_score = abbrev, score
        elif side == "away":
            away, away_score = abbrev, score
        if abbrev:
            # roster ref is usually inline on the competitor; constructed as a
            # fallback so a missing field can't kill the box-score pass
            rosters[abbrev] = ((c.get("roster") or {}).get("$ref")
                               or f"{CORE_WNBA_EVENTS_URL}/{ev_id}/competitions/"
                                  f"{comp_id}/competitors/{c.get('id', '')}/roster")
    if not home or not away:
        return None
    home_win = None
    if completed and home_score is not None and away_score is not None:
        home_win = 1 if home_score > away_score else 0
    return {
        "event_id":      ev_id,
        "game_id":       _build_game_id(game_date, away, home),
        "game_date":     game_date,
        "season":        int(game_date[:4]),
        "home":          home,
        "away":          away,
        "home_score":    home_score if completed else None,
        "away_score":    away_score if completed else None,
        "home_win":      home_win,
        "completed":     completed,
        "commence_time": comp.get("date") or ev.get("date"),
        "core_rosters":  rosters,
    }


# Core stat fields resolved BY NAME (with abbreviation fallback) — the core
# API's basketball athlete-statistics names, never positional indexes.
_CORE_STAT_KEYS = {
    "minutes":       ("minutes", "MIN"),
    "points":        ("points", "PTS"),
    "rebounds":      ("totalRebounds", "rebounds", "REB"),
    "offensive_reb": ("offensiveRebounds", "OREB", "OR"),
    "defensive_reb": ("defensiveRebounds", "DREB", "DR"),
    "assists":       ("assists", "AST"),
    "steals":        ("steals", "STL"),
    "blocks":        ("blocks", "BLK"),
    "turnovers":     ("turnovers", "TO"),
    "fg_made":       ("fieldGoalsMade", "FGM"),
    "fg_att":        ("fieldGoalsAttempted", "FGA"),
    "fg3_made":      ("threePointFieldGoalsMade", "3PM"),
    "fg3_att":       ("threePointFieldGoalsAttempted", "3PA"),
    "ft_made":       ("freeThrowsMade", "FTM"),
    "ft_att":        ("freeThrowsAttempted", "FTA"),
}


def parse_core_stat_values(doc: dict) -> dict:
    """Flatten a core-API athlete-statistics doc (splits.categories[].stats[])
    into our stat fields. Unknown/missing stats resolve to None."""
    flat = {}
    for cat in (((doc or {}).get("splits") or {}).get("categories") or []):
        for st in cat.get("stats", []) or []:
            val = st.get("value", st.get("displayValue"))
            for key in (st.get("name"), st.get("abbreviation")):
                if key and str(key) not in flat:
                    flat[str(key)] = val
    out = {}
    for field, keys in _CORE_STAT_KEYS.items():
        val = next((flat[k] for k in keys if k in flat), None)
        if field == "minutes":
            out[field] = (round(float(val), 1) if isinstance(val, (int, float))
                          else _min_to_float(val))
        else:
            out[field] = (int(val) if isinstance(val, (int, float))
                          else _to_int(val))
    return out


def _core_athlete(entry: dict, fetch, cache: dict):
    """(espn_id, displayName) for a roster entry. Athlete docs are cached per
    run — the same players repeat every game, so the backlog costs one fetch
    per unique player, not per box row."""
    ath = entry.get("athlete") if isinstance(entry.get("athlete"), dict) else {}
    name = ath.get("displayName") or ath.get("fullName")
    if name:
        return str(ath.get("id", "")), name
    ref = ath.get("$ref")
    if not ref:
        return "", None
    if ref not in cache:
        try:
            doc = fetch(ref) or {}
        except Exception as exc:
            logger.warning(f"WNBA results: core athlete fetch failed ({exc})")
            return "", None
        cache[ref] = (str(doc.get("id", "")),
                      doc.get("displayName") or doc.get("fullName"))
    return cache[ref]


def _fetch_core_box_players(game: dict, fetch=None, athlete_cache=None) -> list:
    """
    Per-player box rows for one core-sourced game — the same dict shape
    parse_summary_boxscore emits. Best-effort: a failed roster/stats fetch or
    an empty stat line skips that team/player with a warning instead of
    failing the date (finals are already committed by then).
    """
    fetch = fetch or _get_core_json
    if athlete_cache is None:
        athlete_cache = {}
    out = []
    for team_abbrev, roster_ref in (game.get("core_rosters") or {}).items():
        try:
            roster = fetch(roster_ref) or {}
        except Exception as exc:
            logger.warning(f"WNBA results: core roster fetch failed for "
                           f"{game['game_id']} {team_abbrev}: {exc}")
            continue
        for entry in roster.get("entries", []) or []:
            if entry.get("didNotPlay"):
                continue
            stats_ref = (entry.get("statistics") or {}).get("$ref")
            if not stats_ref:
                continue
            try:
                stats = parse_core_stat_values(fetch(stats_ref))
            except Exception:
                continue
            if stats.get("points") is None and stats.get("minutes") is None:
                continue    # empty stat line — inactive / no box data
            espn_id, name = _core_athlete(entry, fetch, athlete_cache)
            if not name:
                continue
            out.append({"espn_id": espn_id, "name": name, "team": team_abbrev,
                        "starter": bool(entry.get("starter")), **stats})
    return out


# ── ESPN fetch helpers ────────────────────────────────────────────────────────

def _get_core_json(url: str) -> dict:
    """GET a core-API URL. Core $refs are emitted as http:// — force https so
    the worker's egress never downgrades. A tiny sleep keeps ~40 small calls
    per game polite."""
    if url.startswith("http://"):
        url = "https://" + url[len("http://"):]
    resp = requests.get(url, headers=ESPN_HEADERS, timeout=15)
    resp.raise_for_status()
    time.sleep(CORE_REQUEST_SLEEP)
    return resp.json()


def _fetch_core_games(game_date: str, fetch=None) -> list:
    """List + resolve one ET date's WNBA events via sports.core.api.espn.com.
    Queries a 2-day range and filters by ET date inside parse_core_event, so
    it works whether ESPN buckets the dates filter by ET or UTC calendar day."""
    fetch = fetch or _get_core_json
    d = datetime.strptime(game_date, "%Y-%m-%d")
    lo = game_date.replace("-", "")
    hi = (d + timedelta(days=1)).strftime("%Y%m%d")
    listing = fetch(f"{CORE_WNBA_EVENTS_URL}?dates={lo}-{hi}&limit=100")
    out = []
    for item in (listing or {}).get("items", []) or []:
        ref = item.get("$ref") if isinstance(item, dict) else None
        if not ref:
            continue
        rec = parse_core_event(fetch(ref), game_date, fetch)
        if rec:
            out.append(rec)
    return out


def _fetch_scoreboard(game_date: str) -> dict:
    resp = requests.get(ESPN_WNBA_SCOREBOARD_URL,
                        params={"dates": game_date.replace("-", "")},
                        headers=ESPN_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


def _fetch_summary(event_id: str) -> dict:
    resp = requests.get(ESPN_WNBA_SUMMARY_URL, params={"event": event_id},
                        headers=ESPN_HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ── player_id resolution (ESPN name → nba_api id from our own log) ───────────

def _load_name_to_player_id(conn: DBConnection) -> dict:
    """{normalized player name: nba_api player_id} from wnba_player_game_log,
    most-recent row wins on a name collision."""
    rows = conn.execute("""
        SELECT player_id, player_name, MAX(game_date) AS last_seen
        FROM wnba_player_game_log
        GROUP BY player_id, player_name
        ORDER BY last_seen ASC
    """).fetchall()
    mapping = {}
    for player_id, player_name, _last in rows:
        key = norm_player_name(player_name)
        if key:
            mapping[key] = str(player_id)   # later (more recent) rows overwrite
    return mapping


def build_log_row(p: dict, player_id: str, game: dict, game_date: str) -> dict:
    """
    Shape one parsed box-score player dict into a wnba_player_game_log row.
    is_starter is cast bool → 1/0: the column is INTEGER (nba_api convention)
    and Postgres refuses an implicit boolean→integer cast — passing the raw
    parser bool aborted the whole ingest transaction (2026-07-11 outage).
    """
    return {
        "player_id":     player_id,
        "player_name":   p["name"],
        "team":          p["team"],
        "game_id":       game["game_id"],
        "game_date":     game_date,
        "season":        game["season"],
        "minutes":       p["minutes"],
        "is_starter":    1 if p["starter"] else 0,
        "points":        p["points"],
        "rebounds":      p["rebounds"],
        "offensive_reb": p["offensive_reb"],
        "defensive_reb": p["defensive_reb"],
        "assists":       p["assists"],
        "steals":        p["steals"],
        "blocks":        p["blocks"],
        "turnovers":     p["turnovers"],
        "fg_made":       p["fg_made"],  "fg_att":  p["fg_att"],
        "fg3_made":      p["fg3_made"], "fg3_att": p["fg3_att"],
        "ft_made":       p["ft_made"],  "ft_att":  p["ft_att"],
    }


# ── DB writers ────────────────────────────────────────────────────────────────

def _upsert_games_espn(conn: DBConnection, rows: list) -> int:
    """Upsert final scores into games. Odds-provided commence_time is preserved."""
    if not rows:
        return 0
    keys = ("game_id", "season", "game_date", "home", "away",
            "home_score", "away_score", "home_win", "commence_time")
    rows = [{k: r[k] for k in keys} for r in rows]
    sql = """
        INSERT INTO games (
            game_id, sport, season, game_date, home_team, away_team,
            home_score, away_score, home_win, data_source, commence_time
        ) VALUES (
            %(game_id)s, 'WNBA', %(season)s, %(game_date)s, %(home)s, %(away)s,
            %(home_score)s, %(away_score)s, %(home_win)s, 'espn', %(commence_time)s
        )
        ON CONFLICT(game_id) DO UPDATE SET
            home_score    = EXCLUDED.home_score,
            away_score    = EXCLUDED.away_score,
            home_win      = EXCLUDED.home_win,
            commence_time = COALESCE(games.commence_time, EXCLUDED.commence_time),
            updated_at    = NOW()::TEXT
    """
    conn.executemany(sql, rows)
    return len(rows)


# ── Team-stats rebuild from our own DB (no nba_api dependency) ────────────────

def rebuild_wnba_team_stats(conn: DBConnection, season: int, as_of_date: str) -> int:
    """
    Rebuild the season-to-date wnba_team_stats snapshot for as_of_date from the
    games table (scores/W-L) + wnba_player_game_log (shooting/possession sums
    aggregated per team-game). Mirrors wnba_stats_ingestor._build_team_stat_rows
    formulas so features are consistent regardless of which path wrote the row.

    Rate stats (pace/ratings/shooting) use only games with box coverage; volume
    stats (ppg, W-L, point diff) use all finals. In practice coverage is ~100%.
    """
    finals = conn.execute("""
        SELECT game_id, home_team, away_team, home_score, away_score
        FROM games
        WHERE sport = 'WNBA' AND season = %s AND game_date < %s
          AND home_score IS NOT NULL AND away_score IS NOT NULL
    """, (season, as_of_date)).fetchall()
    if not finals:
        return 0

    box = conn.execute("""
        SELECT game_id, team,
               SUM(points), SUM(fg_made), SUM(fg_att), SUM(fg3_made), SUM(fg3_att),
               SUM(ft_made), SUM(ft_att), SUM(offensive_reb), SUM(rebounds),
               SUM(assists), SUM(turnovers)
        FROM wnba_player_game_log
        WHERE season = %s AND game_date < %s
        GROUP BY game_id, team
    """, (season, as_of_date)).fetchall()
    box_by_key = {}
    for gid, team, pts, fgm, fga, fg3m, fg3a, ftm, fta, oreb, reb, ast, tov in box:
        box_by_key[(gid, team)] = {
            "pts": pts or 0, "fgm": fgm or 0, "fga": fga or 0,
            "fg3m": fg3m or 0, "fg3a": fg3a or 0, "ftm": ftm or 0, "fta": fta or 0,
            "oreb": oreb or 0, "reb": reb or 0, "ast": ast or 0, "tov": tov or 0,
        }

    acc: dict = {}

    def team_acc(team):
        return acc.setdefault(team, {
            "n": 0, "pts": 0, "opp": 0, "w": 0, "l": 0,
            "home_pts": [], "away_pts": [],
            "nb": 0, "b_pts": 0, "b_opp": 0,
            "fgm": 0, "fga": 0, "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0,
            "oreb": 0, "reb": 0, "ast": 0, "tov": 0,
        })

    for gid, home, away, hs, aws in finals:
        for team, opp_team, pts, opp, is_home in (
            (home, away, hs, aws, True), (away, home, aws, hs, False),
        ):
            a = team_acc(team)
            a["n"] += 1
            a["pts"] += pts
            a["opp"] += opp
            a["w" if pts > opp else "l"] += 1
            (a["home_pts"] if is_home else a["away_pts"]).append(pts)
            b = box_by_key.get((gid, team))
            if b:
                a["nb"] += 1
                a["b_pts"] += b["pts"]
                a["b_opp"] += opp
                for k in ("fgm", "fga", "fg3m", "fg3a", "ftm", "fta",
                          "oreb", "reb", "ast", "tov"):
                    a[k] += b[k]

    rows = []
    for team, a in acc.items():
        n = a["n"]
        if n == 0:
            continue
        poss = a["fga"] - a["oreb"] + a["tov"] + 0.44 * a["fta"]
        poss = poss if (a["nb"] > 0 and poss > 0) else None
        mean = lambda xs: round(sum(xs) / len(xs), 2) if xs else None
        rows.append({
            "team":              team,
            "season":            season,
            "as_of_date":        as_of_date,
            "games_played":      n,
            "points_per_game":   _safe(a["pts"] / n, 2),
            "points_allowed_pg": _safe(a["opp"] / n, 2),
            "pace":              _safe(poss / a["nb"], 2) if poss else None,
            "off_rating":        _safe(100 * a["b_pts"] / poss, 2) if poss else None,
            "def_rating":        _safe(100 * a["b_opp"] / poss, 2) if poss else None,
            "efg_pct":           _safe((a["fgm"] + 0.5 * a["fg3m"]) / a["fga"], 4) if a["fga"] else None,
            "fg_pct":            _safe(a["fgm"] / a["fga"], 4) if a["fga"] else None,
            "fg3_pct":           _safe(a["fg3m"] / a["fg3a"], 4) if a["fg3a"] else None,
            "ft_pct":            _safe(a["ftm"] / a["fta"], 4) if a["fta"] else None,
            "reb_per_game":      _safe(a["reb"] / a["nb"], 2) if a["nb"] else None,
            "ast_per_game":      _safe(a["ast"] / a["nb"], 2) if a["nb"] else None,
            "tov_pct":           _safe(100 * a["tov"] / poss, 2) if poss else None,
            "points_last_3":     None,   # rolling computed by feature engine from games
            "points_last_5":     None,
            "points_home":       mean(a["home_pts"]),
            "points_away":       mean(a["away_pts"]),
            "wins":              a["w"],
            "losses":            a["l"],
            "point_differential": _safe((a["pts"] - a["opp"]) / n, 2),
        })
    return _upsert_team_stats(conn, rows)


# ── Main entry point ──────────────────────────────────────────────────────────

def _target_dates(conn: DBConnection, run_date: str,
                  lookback_days: int, heal_days: int) -> list:
    """Dates to fetch: the trailing lookback window, plus any recent date that
    still has a WNBA game with no final score (self-heal for missed days)."""
    d = datetime.strptime(run_date, "%Y-%m-%d")
    yday = (d - timedelta(days=1)).strftime("%Y-%m-%d")
    dates = {(d - timedelta(days=i)).strftime("%Y-%m-%d")
             for i in range(1, lookback_days + 1)}
    heal_start = (d - timedelta(days=heal_days)).strftime("%Y-%m-%d")
    rows = conn.execute("""
        SELECT DISTINCT game_date FROM games
        WHERE sport = 'WNBA' AND home_score IS NULL
          AND game_date >= %s AND game_date <= %s
    """, (heal_start, yday)).fetchall()
    dates.update(str(r[0]) for r in rows)
    return sorted(dates)


def ingest_wnba_results(run_date: str = None, lookback_days: int = LOOKBACK_DAYS,
                        heal_days: int = HEAL_DAYS,
                        only_date: str = None) -> dict:
    """
    Fetch WNBA finals + box scores from ESPN for the trailing window (or one
    date) and upsert games / wnba_player_game_log, then rebuild the current
    season's wnba_team_stats snapshot from the DB. Idempotent; best-effort per
    date — one bad date rolls back and logs, the rest still commit — but the
    call still raises at the end if any date failed, so the pipeline step
    shows red instead of silently green. Returns counts.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    totals = {"dates": 0, "finals": 0, "box_rows": 0,
              "unresolved_players": 0, "team_rows": 0}
    failed_dates = []
    try:
        dates = [only_date] if only_date else _target_dates(
            conn, run_date, lookback_days, heal_days)
        name_map = _load_name_to_player_id(conn)
        unresolved: set = set()
        athlete_cache: dict = {}   # core-API athlete docs, shared across dates

        for game_date in dates:
            # site.api first (cheapest, may recover); ANY failure there —
            # network, 403 block, HTML-instead-of-JSON — falls back to the
            # core host, which kept serving the worker through the 2026-08-05
            # site.api IP block (injuries read it daily).
            source = "site"
            try:
                games = parse_scoreboard(_fetch_scoreboard(game_date), game_date)
            except Exception as exc:
                logger.warning(f"WNBA results: site.api scoreboard failed for "
                               f"{game_date} ({exc}); trying sports.core fallback")
                try:
                    games = _fetch_core_games(game_date)
                    source = "core"
                except Exception as exc2:
                    logger.warning(f"WNBA results: sports.core events fetch also "
                                   f"failed for {game_date}: {exc2}")
                    failed_dates.append(game_date)
                    continue
            try:
                finals = [g for g in games if g["completed"]
                          and g["home_score"] is not None and g["away_score"] is not None]
                totals["dates"] += 1
                if not finals:
                    logger.info(f"WNBA results {game_date} [{source}]: no completed "
                                f"games ({len(games)} on slate)")
                    continue

                date_finals = _upsert_games_espn(conn, finals)

                log_rows = []
                for g in finals:
                    if source == "core":
                        players = _fetch_core_box_players(g, athlete_cache=athlete_cache)
                    else:
                        try:
                            players = parse_summary_boxscore(_fetch_summary(g["event_id"]))
                        except requests.RequestException as exc:
                            logger.warning(f"WNBA results: summary fetch failed for "
                                           f"{g['game_id']} (event {g['event_id']}): {exc}")
                            continue
                    for p in players:
                        pid = name_map.get(norm_player_name(p["name"]))
                        if not pid:
                            unresolved.add(p["name"])
                            continue
                        log_rows.append(build_log_row(p, pid, g, game_date))
                    time.sleep(REQUEST_SLEEP)

                date_box = _upsert_player_log(conn, log_rows)
                conn.commit()
                totals["finals"] += date_finals
                totals["box_rows"] += date_box
                logger.info(f"WNBA results {game_date} [{source}]: {len(finals)} "
                            f"finals, {len(log_rows)} box rows upserted")
            except Exception as exc:
                # A bad payload or DB error for one date must not take down the
                # rest of the window (the 2026-07-11 is_starter type error rolled
                # back six days of backlog). Roll back this date and continue.
                conn.rollback()
                failed_dates.append(game_date)
                logger.error(f"WNBA results: {game_date} failed, rolled back: {exc}")

        if unresolved:
            totals["unresolved_players"] = len(unresolved)
            logger.warning(
                f"WNBA results: {len(unresolved)} ESPN player(s) with no nba_api id "
                f"in wnba_player_game_log (skipped; local job backfills them): "
                f"{sorted(unresolved)[:10]}")

        # Rebuild the current-season team snapshot so game-scorer features stay
        # fresh even if the local nba_api job is down. Cheap no-op preseason.
        season = int(run_date[:4])
        totals["team_rows"] = rebuild_wnba_team_stats(conn, season, run_date)
        conn.commit()
        if totals["team_rows"]:
            logger.info(f"WNBA team stats rebuilt from DB: {totals['team_rows']} "
                        f"rows as of {run_date}")
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    if failed_dates:
        # Good dates are already committed; surface the failures so the
        # pipeline step (and the red run) still flag a broken ingest.
        raise RuntimeError(
            f"WNBA results: {len(failed_dates)} date(s) failed "
            f"({', '.join(failed_dates)}); committed so far: {totals}")

    logger.success(f"WNBA results (ESPN): {totals}")
    return totals


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest WNBA finals + box scores from ESPN (Actions-reachable)")
    parser.add_argument("--date", help="Ingest one game date YYYY-MM-DD")
    parser.add_argument("--run-date", help="Anchor date for the trailing window "
                                           "(default: today)")
    args = parser.parse_args()
    result = ingest_wnba_results(run_date=args.run_date, only_date=args.date)
    logger.info(f"Done: {result}")
