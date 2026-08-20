"""
NFL per-player per-game stats (nflverse weekly player stats) → nfl_player_game_log.

Feeds the mobile Stats tab's NFL leaderboard (season totals, last-N windows,
and Hit Rate mode) via v_player_season_totals_nfl + the player_window_totals_nfl /
player_recent_games_nfl RPCs. Display/stats only — no model reads this table.

Source: nflverse-data GitHub release assets, tag `stats_player`, asset
`stats_player_week_{season}.csv` (config.NFLVERSE_PLAYER_STATS_URL_TMPL) — the
canonical weekly player-stats export, updated nightly in season. One row per
player per game with passing/rushing/receiving/defense splits. `game_date`
isn't in the weekly file, so each run also fetches the nflverse games.csv
schedule (config.NFLVERSE_GAMES_URL — the same file nfl_results_ingestor
already reads) and joins on the nflverse game id.

Conventions:
- game_id is stored platform-style as "NFL_{nflverse_id}" (e.g.
  NFL_2025_01_CIN_CLE) — same convention as the wind-card publisher — but has
  NO FK to games: only games with wind/opener picks ever get a games row,
  while this log covers the whole league.
- season = the nflverse season label (year the season STARTS: Jan/Feb games
  belong to the prior year's label).
- Rows where every tracked stat is zero (kickers, punters, pure tackle-only
  defenders — stats we don't store) are skipped to keep the leaderboard
  meaningful.
- REG and POST rows are both kept (season totals include playoffs — the MLB
  season-totals precedent).

Self-healing: run_nfl_player_stats_ingestor() ingests the current season plus
any of the last NFL_PLAYER_STATS_BACKFILL_SEASONS seasons that look missing
(< _SEASON_COMPLETE_ROWS rows), so the first run after deploy backfills
2023-2025 with no manual step. A season whose CSV isn't published yet (the
off-season) 404s and is treated as a clean no-op — that is the off-season gate.

Usage:
    python -m data.ingestors.nfl_player_stats_ingestor                # self-healing daily
    python -m data.ingestors.nfl_player_stats_ingestor --season 2025
    python -m data.ingestors.nfl_player_stats_ingestor --backfill 2023 2025
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from data.db import get_connection

try:
    from loguru import logger
except ImportError:  # pragma: no cover - loguru is always present in prod
    import logging
    logger = logging.getLogger(__name__)

# A real NFL season yields ~15-20K stat rows; a season with fewer than this is
# treated as not-yet-ingested by the self-heal (a verification sample or a
# partially-failed run gets re-ingested — the upsert makes that free).
_SEASON_COMPLETE_ROWS = 5000

# CSV column → table column for the integer stats.
_INT_STATS = {
    "completions": "completions",
    "attempts": "attempts",
    "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions",
    "carries": "carries",
    "rushing_tds": "rushing_tds",
    "receptions": "receptions",
    "targets": "targets",
    "receiving_tds": "receiving_tds",
    "def_interceptions": "def_interceptions",
}
# CSV column → table column for the fractional stats (yards can be negative,
# sacks come in halves).
_NUM_STATS = {
    "passing_yards": "passing_yards",
    "rushing_yards": "rushing_yards",
    "receiving_yards": "receiving_yards",
    "def_sacks": "def_sacks",
}


def _to_int(v: str | None) -> int:
    try:
        return int(float(v)) if v not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


def _to_num(v: str | None) -> float:
    try:
        return float(v) if v not in (None, "") else 0.0
    except (TypeError, ValueError):
        return 0.0


def current_nfl_season(today: date | None = None) -> int:
    """nflverse season label for 'now': the season starting this calendar year
    from March onward; Jan/Feb belong to the prior year's season (playoffs)."""
    d = today or datetime.now(timezone.utc).date()
    return d.year if d.month >= 3 else d.year - 1


def parse_player_week_csv(csv_text: str, game_dates: dict[str, str]) -> list[dict]:
    """
    Pure parse: nflverse stats_player_week CSV text -> upsert-ready row dicts.
    `game_dates` maps nflverse game_id -> gameday (YYYY-MM-DD) from games.csv.
    Rows whose game id isn't in the schedule are skipped (game_date is the
    ordering key for every window RPC — a dateless row would corrupt last-N).
    All-zero rows across the tracked stats are skipped (see module docstring).
    """
    rows: list[dict] = []
    skipped_no_date = 0
    for raw in csv.DictReader(io.StringIO(csv_text)):
        gid = (raw.get("game_id") or "").strip()
        pid = (raw.get("player_id") or "").strip()
        name = (raw.get("player_display_name") or raw.get("player_name") or "").strip()
        if not gid or not pid or not name:
            continue
        game_date = game_dates.get(gid)
        if not game_date:
            skipped_no_date += 1
            continue

        row = {
            "player_id": pid,
            "player_name": name,
            "pos": (raw.get("position") or "").strip() or None,
            "team": (raw.get("team") or "").strip(),
            "opponent": (raw.get("opponent_team") or "").strip() or None,
            "game_id": f"NFL_{gid}",
            "game_date": game_date,
            "season": _to_int(raw.get("season")),
            "week": _to_int(raw.get("week")),
            "season_type": (raw.get("season_type") or "").strip() or None,
        }
        for src, dst in _INT_STATS.items():
            row[dst] = _to_int(raw.get(src))
        for src, dst in _NUM_STATS.items():
            row[dst] = _to_num(raw.get(src))

        stat_cols = list(_INT_STATS.values()) + list(_NUM_STATS.values())
        if all(not row[c] for c in stat_cols):
            continue  # kicker/punter/tackle-only row — nothing we track
        rows.append(row)

    if skipped_no_date:
        logger.warning(f"NFL player stats: {skipped_no_date} row(s) skipped — "
                       "game id missing from the nflverse schedule")
    return rows


def _fetch_game_dates() -> dict[str, str]:
    """nflverse games.csv -> {nflverse game_id: gameday}."""
    resp = requests.get(config.NFLVERSE_GAMES_URL, timeout=60)
    resp.raise_for_status()
    out: dict[str, str] = {}
    for row in csv.DictReader(io.StringIO(resp.text)):
        gid = (row.get("game_id") or "").strip()
        day = (row.get("gameday") or "").strip()
        if gid and day:
            out[gid] = day
    return out


def _fetch_season_csv(season: int) -> str | None:
    """The season's weekly stats CSV text, or None when not published (404)."""
    url = config.NFLVERSE_PLAYER_STATS_URL_TMPL.format(season=season)
    resp = requests.get(url, timeout=120, allow_redirects=True)
    if resp.status_code == 404:
        logger.info(f"NFL player stats: season {season} CSV not published yet — skipping")
        return None
    resp.raise_for_status()
    return resp.text


_UPSERT_SQL = """
    INSERT INTO nfl_player_game_log (
        player_id, player_name, pos, team, opponent, game_id, game_date,
        season, week, season_type,
        completions, attempts, passing_yards, passing_tds, interceptions,
        carries, rushing_yards, rushing_tds,
        receptions, targets, receiving_yards, receiving_tds,
        def_sacks, def_interceptions
    ) VALUES (
        %(player_id)s, %(player_name)s, %(pos)s, %(team)s, %(opponent)s,
        %(game_id)s, %(game_date)s, %(season)s, %(week)s, %(season_type)s,
        %(completions)s, %(attempts)s, %(passing_yards)s, %(passing_tds)s,
        %(interceptions)s, %(carries)s, %(rushing_yards)s, %(rushing_tds)s,
        %(receptions)s, %(targets)s, %(receiving_yards)s, %(receiving_tds)s,
        %(def_sacks)s, %(def_interceptions)s
    )
    ON CONFLICT(player_id, game_id) DO UPDATE SET
        player_name     = EXCLUDED.player_name,
        pos             = EXCLUDED.pos,
        team            = EXCLUDED.team,
        opponent        = EXCLUDED.opponent,
        game_date       = EXCLUDED.game_date,
        season          = EXCLUDED.season,
        week            = EXCLUDED.week,
        season_type     = EXCLUDED.season_type,
        completions     = EXCLUDED.completions,
        attempts        = EXCLUDED.attempts,
        passing_yards   = EXCLUDED.passing_yards,
        passing_tds     = EXCLUDED.passing_tds,
        interceptions   = EXCLUDED.interceptions,
        carries         = EXCLUDED.carries,
        rushing_yards   = EXCLUDED.rushing_yards,
        rushing_tds     = EXCLUDED.rushing_tds,
        receptions      = EXCLUDED.receptions,
        targets         = EXCLUDED.targets,
        receiving_yards = EXCLUDED.receiving_yards,
        receiving_tds   = EXCLUDED.receiving_tds,
        def_sacks       = EXCLUDED.def_sacks,
        def_interceptions = EXCLUDED.def_interceptions
"""


def ingest_nfl_player_stats(season: int, conn=None,
                            game_dates: dict[str, str] | None = None) -> int:
    """Fetch + upsert one season's weekly player stats. Returns rows upserted."""
    csv_text = _fetch_season_csv(season)
    if csv_text is None:
        return 0
    if game_dates is None:
        game_dates = _fetch_game_dates()
    rows = parse_player_week_csv(csv_text, game_dates)
    if not rows:
        logger.info(f"NFL player stats {season}: 0 stat rows in the CSV")
        return 0

    own_conn = conn is None
    if own_conn:
        conn = get_connection()
    try:
        conn.executemany(_UPSERT_SQL, rows)
        conn.commit()
    finally:
        if own_conn:
            conn.close()
    logger.info(f"NFL player stats {season}: {len(rows)} row(s) upserted")
    return len(rows)


def run_nfl_player_stats_ingestor() -> int:
    """
    Self-healing daily ingest: refresh the current season, plus (re)ingest any
    of the last NFL_PLAYER_STATS_BACKFILL_SEASONS seasons that look missing.
    Off-season the current season's CSV 404s → clean no-op. Returns total rows.
    """
    season_now = current_nfl_season()
    conn = get_connection()
    try:
        counts = {
            int(r[0]): int(r[1]) for r in conn.execute(
                "SELECT season, COUNT(*) FROM nfl_player_game_log GROUP BY season"
            ).fetchall()
        }
        targets = [season_now]
        for s in range(season_now - config.NFL_PLAYER_STATS_BACKFILL_SEASONS, season_now):
            if counts.get(s, 0) < _SEASON_COMPLETE_ROWS:
                targets.append(s)
        targets = sorted(set(targets))

        game_dates: dict[str, str] | None = None
        total = 0
        for season in targets:
            if game_dates is None:
                game_dates = _fetch_game_dates()  # one schedule fetch per run
            total += ingest_nfl_player_stats(season, conn=conn, game_dates=game_dates)
        return total
    finally:
        conn.close()


def backfill_nfl_player_stats(start_year: int, end_year: int) -> int:
    """Explicit backfill over a season range (idempotent upserts)."""
    game_dates = _fetch_game_dates()
    conn = get_connection()
    total = 0
    try:
        for season in range(start_year, end_year + 1):
            total += ingest_nfl_player_stats(season, conn=conn, game_dates=game_dates)
    finally:
        conn.close()
    logger.info(f"NFL player stats backfill {start_year}-{end_year}: {total} row(s)")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="nflverse weekly player stats → nfl_player_game_log")
    ap.add_argument("--season", type=int, help="ingest one season")
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                    help="ingest a season range, e.g. --backfill 2023 2025")
    args = ap.parse_args()
    if args.backfill:
        backfill_nfl_player_stats(args.backfill[0], args.backfill[1])
    elif args.season:
        ingest_nfl_player_stats(args.season)
    else:
        run_nfl_player_stats_ingestor()
