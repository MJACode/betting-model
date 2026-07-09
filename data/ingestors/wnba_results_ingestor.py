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

Usage:
    python -m data.ingestors.wnba_results_ingestor                    # trailing window
    python -m data.ingestors.wnba_results_ingestor --date 2026-07-05  # one date
"""

import argparse
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

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

REQUEST_SLEEP = 0.4     # be polite between per-event summary calls
LOOKBACK_DAYS = 3       # always re-check the last N days' finals
HEAL_DAYS = 14          # also re-fetch any recent WNBA game still missing a score


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


# ── ESPN fetch helpers ────────────────────────────────────────────────────────

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
    date (one bad date logs and continues). Returns counts.
    """
    if run_date is None:
        run_date = datetime.now().strftime("%Y-%m-%d")

    conn = get_connection()
    totals = {"dates": 0, "finals": 0, "box_rows": 0,
              "unresolved_players": 0, "team_rows": 0}
    try:
        dates = [only_date] if only_date else _target_dates(
            conn, run_date, lookback_days, heal_days)
        name_map = _load_name_to_player_id(conn)
        unresolved: set = set()

        for game_date in dates:
            try:
                sb = _fetch_scoreboard(game_date)
            except requests.RequestException as exc:
                logger.warning(f"WNBA results: scoreboard fetch failed for {game_date}: {exc}")
                continue
            games = parse_scoreboard(sb, game_date)
            finals = [g for g in games if g["completed"]
                      and g["home_score"] is not None and g["away_score"] is not None]
            totals["dates"] += 1
            if not finals:
                logger.info(f"WNBA results {game_date}: no completed games "
                            f"({len(games)} on slate)")
                continue

            totals["finals"] += _upsert_games_espn(conn, finals)

            log_rows = []
            for g in finals:
                try:
                    summary = _fetch_summary(g["event_id"])
                except requests.RequestException as exc:
                    logger.warning(f"WNBA results: summary fetch failed for "
                                   f"{g['game_id']} (event {g['event_id']}): {exc}")
                    continue
                for p in parse_summary_boxscore(summary):
                    pid = name_map.get(norm_player_name(p["name"]))
                    if not pid:
                        unresolved.add(p["name"])
                        continue
                    log_rows.append({
                        "player_id":     pid,
                        "player_name":   p["name"],
                        "team":          p["team"],
                        "game_id":       g["game_id"],
                        "game_date":     game_date,
                        "season":        g["season"],
                        "minutes":       p["minutes"],
                        "is_starter":    p["starter"],
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
                    })
                time.sleep(REQUEST_SLEEP)

            totals["box_rows"] += _upsert_player_log(conn, log_rows)
            conn.commit()
            logger.info(f"WNBA results {game_date}: {len(finals)} finals, "
                        f"{len(log_rows)} box rows upserted")

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
