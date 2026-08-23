"""
NFL player-prop MODELLING data from nflverse → Supabase.

Three writes, one per source, all idempotent upserts:

  1. `nfl_player_game_log` — the same weekly player rows the display ingestor
     writes (`nfl_player_stats_ingestor`), PLUS the modelling columns that
     ingestor parses past and discards: usage shares (target_share,
     air_yards_share, wopr, racr), air yards, YAC, EPA, the solo/assist tackle
     split, and the kicking splits. Both modules parse the SAME source CSV and
     upsert on the SAME key, so they converge on identical values and may run in
     either order. This module is the superset; the display one is untouched.

  2. `nfl_team_game_stats` — one row per team per game. Offensive volume is the
     denominator behind every usage share and the pace proxy; the pre-game
     market and environment context (spread, total, roof, surface, temp, wind,
     div game) comes from the same nflverse games.csv the results ingestor
     already reads. Opponent-defence-allowed features read this table from the
     defending team's side, so there is no separate defence table.

  3. `nfl_snap_counts` — snap share. nflverse keys snaps on `pfr_player_id` and
     a PFR-style display name, with no gsis id, so rows carry a normalised name
     and the feature engine joins on (norm_name, team, game_id). Measured
     coverage against the weekly stats: 98.1% of all rows, 98.8% of rows with a
     target, 99.3% with a carry, 100% with a pass attempt, 97.8% with a tackle —
     and zero duplicate keys.

Why snap share is worth the join: it is the availability signal, and it is the
main driver of the tackles+assists market — the market with the most
out-of-sample signal in the sport (see docs/nfl_props_model.md §2c).

Season label = the nflverse season (the year the season STARTS; Jan/Feb
playoff games belong to the prior year's label). REG and POST are both kept;
the feature engine filters to REG for training.

Usage:
    python -m data.ingestors.nfl_props_data_ingestor                 # self-healing daily
    python -m data.ingestors.nfl_props_data_ingestor --season 2025
    python -m data.ingestors.nfl_props_data_ingestor --backfill 2015 2025
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import unicodedata
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import config
from data.db import get_connection
from data.ingestors.nfl_player_stats_ingestor import (
    _fetch_season_csv, current_nfl_season, _to_int, _to_num,
)

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


# A full season yields ~17-19K player rows / ~550 team rows; below this the
# self-heal treats the season as not ingested (the upsert makes a redo free).
_SEASON_COMPLETE_PLAYER_ROWS = 5_000
_SEASON_COMPLETE_TEAM_ROWS = 300

_SUFFIX_RE = re.compile(r"\b(jr|sr|ii|iii|iv|v)\.?$")


def norm_player_name(name: str) -> str:
    """
    Accent-stripped, suffix-stripped, letters-only key.

    This is the ONLY bridge between the weekly stats (gsis ids, "Marvin
    Harrison Jr.") and snap counts (pfr ids, "Marvin Harrison"). Keep it in one
    place: the feature engine's join and the ingest must normalise identically
    or the join silently degrades to nulls rather than failing.
    """
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = _SUFFIX_RE.sub("", s.lower().strip())
    return re.sub(r"[^a-z]", "", s)


# ── nflverse schedule (games.csv) ─────────────────────────────────────────────

def fetch_schedule() -> dict[str, dict]:
    """nflverse games.csv → {game_id: row}. One fetch per run."""
    resp = requests.get(config.NFLVERSE_GAMES_URL, timeout=90)
    resp.raise_for_status()
    out: dict[str, dict] = {}
    for row in csv.DictReader(io.StringIO(resp.text)):
        gid = (row.get("game_id") or "").strip()
        if gid:
            out[gid] = row
    return out


def _fetch_snap_csv(season: int) -> str | None:
    """The season's snap-count CSV text, or None when not published (404)."""
    url = config.NFLVERSE_SNAP_COUNTS_URL_TMPL.format(season=season)
    resp = requests.get(url, timeout=120, allow_redirects=True)
    if resp.status_code == 404:
        logger.info(f"NFL snap counts: season {season} not published yet — skipping")
        return None
    resp.raise_for_status()
    return resp.text


# ── Pure parsers ──────────────────────────────────────────────────────────────

# CSV column → table column. Ints, then numerics (yards can be negative, sacks
# and shares are fractional).
_INT_COLS = {
    "completions": "completions", "attempts": "attempts", "passing_tds": "passing_tds",
    "passing_interceptions": "interceptions", "carries": "carries",
    "rushing_tds": "rushing_tds", "rushing_first_downs": "rushing_first_downs",
    "receptions": "receptions", "targets": "targets", "receiving_tds": "receiving_tds",
    "def_interceptions": "def_interceptions",
    "fg_made": "fg_made", "fg_att": "fg_att", "pat_made": "pat_made", "pat_att": "pat_att",
}
_NUM_COLS = {
    "passing_yards": "passing_yards", "rushing_yards": "rushing_yards",
    "receiving_yards": "receiving_yards", "def_sacks": "def_sacks",
    "sacks_suffered": "sacks_suffered", "passing_air_yards": "passing_air_yards",
    "passing_epa": "passing_epa", "receiving_air_yards": "receiving_air_yards",
    "receiving_yards_after_catch": "receiving_yac", "receiving_epa": "receiving_epa",
    "target_share": "target_share", "air_yards_share": "air_yards_share",
    "wopr": "wopr", "racr": "racr",
    "def_tackles_solo": "def_tackles_solo", "def_tackle_assists": "def_tackle_assists",
    "def_qb_hits": "def_qb_hits",
}
# Columns that decide whether a row carries anything we model. A row that is
# zero across all of them is a long-snapper / punter / pure-ST player.
_SIGNAL_COLS = ("attempts", "carries", "targets", "receptions", "def_tackles_solo",
                "def_tackle_assists", "def_sacks", "fg_att", "pat_att")

PLAYER_COLUMNS = (["player_id", "player_name", "norm_name", "pos", "team", "opponent",
                   "game_id", "game_date", "season", "week", "season_type"]
                  + list(_INT_COLS.values()) + list(_NUM_COLS.values()))


def parse_player_rows(csv_text: str, schedule: dict[str, dict]) -> list[dict]:
    """nflverse weekly stats CSV → nfl_player_game_log upsert rows (modelling superset)."""
    rows: list[dict] = []
    skipped_no_date = 0
    for raw in csv.DictReader(io.StringIO(csv_text)):
        gid = (raw.get("game_id") or "").strip()
        pid = (raw.get("player_id") or "").strip()
        name = (raw.get("player_display_name") or raw.get("player_name") or "").strip()
        if not gid or not pid or not name:
            continue
        game = schedule.get(gid)
        game_date = (game or {}).get("gameday", "").strip()
        if not game_date:
            # game_date is the ordering key for every rolling window — a dateless
            # row would silently corrupt last-N features, so it is dropped.
            skipped_no_date += 1
            continue

        row = {
            "player_id": pid,
            "player_name": name,
            "norm_name": norm_player_name(name),
            "pos": (raw.get("position") or "").strip() or None,
            "team": (raw.get("team") or "").strip(),
            "opponent": (raw.get("opponent_team") or "").strip() or None,
            "game_id": f"NFL_{gid}",
            "game_date": game_date,
            "season": _to_int(raw.get("season")),
            "week": _to_int(raw.get("week")),
            "season_type": (raw.get("season_type") or "").strip() or None,
        }
        for src, dst in _INT_COLS.items():
            row[dst] = _to_int(raw.get(src))
        for src, dst in _NUM_COLS.items():
            row[dst] = _to_num(raw.get(src))
        if not any(row.get(c) for c in _SIGNAL_COLS):
            continue
        rows.append(row)

    if skipped_no_date:
        logger.warning(f"NFL props data: {skipped_no_date} row(s) skipped — "
                       "game id missing from the nflverse schedule")
    return rows


TEAM_COLUMNS = ["game_id", "team", "opponent", "game_date", "season", "week", "season_type",
                "is_home", "pass_attempts", "carries", "plays", "pass_yards", "rush_yards",
                "completions", "targets", "spread_line", "total_line", "roof", "surface",
                "temp", "wind", "div_game", "commence_time", "points_for", "points_against"]


def _kickoff_utc(gameday: str, gametime: str | None) -> str | None:
    """
    nflverse gameday + gametime (Eastern, "HH:MM") → a UTC ISO timestamp.

    The scorer refuses to price a prop once the game has started, and NFL games
    have no row in `games` unless they carry a wind/opener pick — so kickoff has
    to be carried here. A missing gametime yields None rather than a guessed
    midnight, which would make every Sunday game look already-started.
    """
    if not gameday or not gametime:
        return None
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        naive = datetime.strptime(f"{gameday} {gametime.strip()}", "%Y-%m-%d %H:%M")
        return naive.replace(tzinfo=ZoneInfo("America/New_York")).astimezone(
            ZoneInfo("UTC")).isoformat()
    except (ValueError, TypeError):
        return None


def parse_team_rows(player_rows: list[dict], schedule: dict[str, dict]) -> list[dict]:
    """
    Aggregate parsed player rows to one row per (game, team) and attach the
    pre-game market + environment context from the schedule.

    Volume is summed from the player rows rather than taken from a team feed so
    the share denominators are exactly consistent with the numerators.
    """
    agg: dict[tuple[str, str], dict] = {}
    for r in player_rows:
        key = (r["game_id"], r["team"])
        a = agg.get(key)
        if a is None:
            a = agg[key] = {
                "game_id": r["game_id"], "team": r["team"], "opponent": r["opponent"],
                "game_date": r["game_date"], "season": r["season"], "week": r["week"],
                "season_type": r["season_type"],
                "pass_attempts": 0, "carries": 0, "pass_yards": 0.0, "rush_yards": 0.0,
                "completions": 0, "targets": 0,
            }
        a["pass_attempts"] += r.get("attempts") or 0
        a["carries"] += r.get("carries") or 0
        a["completions"] += r.get("completions") or 0
        a["targets"] += r.get("targets") or 0
        a["pass_yards"] += r.get("passing_yards") or 0.0
        a["rush_yards"] += r.get("rushing_yards") or 0.0

    out: list[dict] = []
    for (gid, team), a in agg.items():
        game = schedule.get(gid[4:], {})       # strip the "NFL_" prefix
        home = (game.get("home_team") or "").strip()
        away = (game.get("away_team") or "").strip()
        is_home = 1 if team == home else (0 if team == away else None)
        hs, as_ = _num_or_none(game.get("home_score")), _num_or_none(game.get("away_score"))
        a.update({
            "plays": a["pass_attempts"] + a["carries"],
            "is_home": is_home,
            "spread_line": _num_or_none(game.get("spread_line")),   # home-relative
            "total_line": _num_or_none(game.get("total_line")),
            "roof": (game.get("roof") or "").strip() or None,
            "surface": (game.get("surface") or "").strip() or None,
            "temp": _num_or_none(game.get("temp")),
            "wind": _num_or_none(game.get("wind")),
            "div_game": _int_or_none(game.get("div_game")),
            "commence_time": _kickoff_utc(a["game_date"], game.get("gametime")),
            "points_for": (hs if is_home == 1 else as_) if is_home is not None else None,
            "points_against": (as_ if is_home == 1 else hs) if is_home is not None else None,
        })
        out.append(a)
    return out


def parse_upcoming_team_rows(schedule: dict[str, dict], season: int,
                             played: set[tuple[str, str]]) -> list[dict]:
    """
    Context-only `nfl_team_game_stats` rows for SCHEDULED-but-unplayed games.

    This is what keeps the feature engine pure-DB. The scoring path needs the
    upcoming game's spread, total, roof and wind — pre-game context that only
    lives in the schedule — and without these rows it would have to fetch the
    nflverse CSV itself at score time. Volume and points stay NULL; the same
    (game_id, team) key is overwritten with the real numbers once the game is
    played, so a row is never stale for longer than one ingest.
    """
    rows: list[dict] = []
    for gid, game in schedule.items():
        if _int_or_none(game.get("season")) != season:
            continue
        home = (game.get("home_team") or "").strip()
        away = (game.get("away_team") or "").strip()
        gameday = (game.get("gameday") or "").strip()
        if not home or not away or not gameday:
            continue
        if _num_or_none(game.get("home_score")) is not None:
            continue                                   # played — the aggregate wins
        for team, opp, is_home in ((home, away, 1), (away, home, 0)):
            if (f"NFL_{gid}", team) in played:
                continue
            rows.append({
                "game_id": f"NFL_{gid}", "team": team, "opponent": opp,
                "game_date": gameday, "season": season,
                "week": _int_or_none(game.get("week")),
                "season_type": (game.get("game_type") or "").strip() or None,
                "is_home": is_home,
                "pass_attempts": None, "carries": None, "plays": None,
                "pass_yards": None, "rush_yards": None,
                "completions": None, "targets": None,
                "spread_line": _num_or_none(game.get("spread_line")),
                "total_line": _num_or_none(game.get("total_line")),
                "roof": (game.get("roof") or "").strip() or None,
                "surface": (game.get("surface") or "").strip() or None,
                "temp": _num_or_none(game.get("temp")),
                "wind": _num_or_none(game.get("wind")),
                "div_game": _int_or_none(game.get("div_game")),
                "commence_time": _kickoff_utc(gameday, game.get("gametime")),
                "points_for": None, "points_against": None,
            })
    return rows


SNAP_COLUMNS = ["game_id", "team", "player_name", "norm_name", "pfr_player_id", "pos",
                "season", "week", "offense_snaps", "offense_pct", "defense_snaps",
                "defense_pct", "st_snaps", "st_pct"]


def parse_snap_rows(csv_text: str) -> list[dict]:
    """
    nflverse snap_counts CSV → nfl_snap_counts upsert rows.

    Deduplicated on (game_id, team, norm_name): the table's unique key. Real
    duplicates do not occur in the source (measured: zero across 11 seasons),
    but two players on one roster normalising to the same key would otherwise
    fail the upsert mid-batch rather than losing one row.
    """
    seen: set[tuple[str, str, str]] = set()
    rows: list[dict] = []
    for raw in csv.DictReader(io.StringIO(csv_text)):
        gid = (raw.get("game_id") or "").strip()
        team = (raw.get("team") or "").strip()
        name = (raw.get("player") or "").strip()
        if not gid or not team or not name:
            continue
        nn = norm_player_name(name)
        key = (f"NFL_{gid}", team, nn)
        if not nn or key in seen:
            continue
        seen.add(key)
        rows.append({
            "game_id": key[0], "team": team, "player_name": name, "norm_name": nn,
            "pfr_player_id": (raw.get("pfr_player_id") or "").strip() or None,
            "pos": (raw.get("position") or "").strip() or None,
            "season": _to_int(raw.get("season")), "week": _to_int(raw.get("week")),
            "offense_snaps": _to_int(raw.get("offense_snaps")),
            "offense_pct": _to_num(raw.get("offense_pct")),
            "defense_snaps": _to_int(raw.get("defense_snaps")),
            "defense_pct": _to_num(raw.get("defense_pct")),
            "st_snaps": _to_int(raw.get("st_snaps")),
            "st_pct": _to_num(raw.get("st_pct")),
        })
    return rows


def _num_or_none(v) -> float | None:
    try:
        return float(v) if v not in (None, "", "NA") else None
    except (TypeError, ValueError):
        return None


def _int_or_none(v) -> int | None:
    f = _num_or_none(v)
    return int(f) if f is not None else None


# ── Upserts ───────────────────────────────────────────────────────────────────

def _upsert_sql(table: str, columns: list[str], conflict: list[str]) -> str:
    cols = ", ".join(columns)
    vals = ", ".join(f"%({c})s" for c in columns)
    sets = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in conflict)
    return (f"INSERT INTO {table} ({cols}) VALUES ({vals}) "
            f"ON CONFLICT ({', '.join(conflict)}) DO UPDATE SET {sets}")


_PLAYER_UPSERT = _upsert_sql("nfl_player_game_log", PLAYER_COLUMNS, ["player_id", "game_id"])
_TEAM_UPSERT = _upsert_sql("nfl_team_game_stats", TEAM_COLUMNS, ["game_id", "team"])
_SNAP_UPSERT = _upsert_sql("nfl_snap_counts", SNAP_COLUMNS, ["game_id", "team", "norm_name"])


# Supabase enforces a statement timeout (this repo has been bitten by it before —
# the player-handedness backfill had to be rewritten into committed chunks for
# exactly this reason). A season is ~17k player rows and ~26k snap rows; sending
# those as one batch over the pooler is the shape that times out. Chunked and
# committed as we go, so a timeout costs one chunk rather than the season, and a
# re-run skips what already landed (every write is an upsert).
_UPSERT_CHUNK = 500


def _upsert_chunked(conn, sql: str, rows: list[dict], chunk: int = _UPSERT_CHUNK) -> int:
    for i in range(0, len(rows), chunk):
        conn.executemany(sql, rows[i:i + chunk])
        conn.commit()
    return len(rows)


def ingest_season(season: int, conn=None, schedule: dict[str, dict] | None = None) -> dict:
    """Ingest one season's player rows, team-game rows and snap counts."""
    if schedule is None:
        schedule = fetch_schedule()

    # Order matters: the SCHEDULED-game context rows are written even when the
    # weekly stats CSV does not exist yet. Before week 1 that CSV 404s, and an
    # early return here would leave the scorer with no slate for the opening
    # week — the model would silently produce zero picks on the one week it has
    # the most history for.
    csv_text = _fetch_season_csv(season)
    player_rows = parse_player_rows(csv_text, schedule) if csv_text else []
    team_rows = parse_team_rows(player_rows, schedule) if player_rows else []
    played = {(r["game_id"], r["team"]) for r in team_rows}
    team_rows += parse_upcoming_team_rows(schedule, season, played)

    snap_text = _fetch_snap_csv(season) if csv_text else None
    snap_rows = parse_snap_rows(snap_text) if snap_text else []

    own = conn is None
    if own:
        conn = get_connection()
    try:
        _upsert_chunked(conn, _PLAYER_UPSERT, player_rows)
        _upsert_chunked(conn, _TEAM_UPSERT, team_rows)
        _upsert_chunked(conn, _SNAP_UPSERT, snap_rows)
    finally:
        if own:
            conn.close()

    logger.info(f"NFL props data {season}: {len(player_rows)} player, "
                f"{len(team_rows)} team, {len(snap_rows)} snap row(s)")
    return {"players": len(player_rows), "teams": len(team_rows), "snaps": len(snap_rows)}


def run_nfl_props_data_ingestor() -> dict:
    """
    Self-healing daily ingest: refresh the current season, plus (re)ingest any
    modelling season that looks incomplete in either the player log or the
    team-game table. Off-season the current season's CSV 404s → clean no-op.
    """
    season_now = current_nfl_season()
    conn = get_connection()
    try:
        players = {int(r[0]): int(r[1]) for r in conn.execute(
            "SELECT season, COUNT(*) FROM nfl_player_game_log GROUP BY season").fetchall()}
        teams = {int(r[0]): int(r[1]) for r in conn.execute(
            "SELECT season, COUNT(*) FROM nfl_team_game_stats GROUP BY season").fetchall()}

        targets = {season_now}
        for s in range(config.NFL_MODEL_FIRST_SEASON, season_now):
            if (players.get(s, 0) < _SEASON_COMPLETE_PLAYER_ROWS
                    or teams.get(s, 0) < _SEASON_COMPLETE_TEAM_ROWS):
                targets.add(s)

        schedule: dict[str, dict] | None = None
        total = {"players": 0, "teams": 0, "snaps": 0}
        for season in sorted(targets):
            if schedule is None:
                schedule = fetch_schedule()   # one schedule fetch per run
            got = ingest_season(season, conn=conn, schedule=schedule)
            for k in total:
                total[k] += got[k]
        return total
    finally:
        conn.close()


def backfill(start_year: int, end_year: int) -> dict:
    """Explicit backfill over a season range (idempotent upserts)."""
    schedule = fetch_schedule()
    conn = get_connection()
    total = {"players": 0, "teams": 0, "snaps": 0}
    try:
        for season in range(start_year, end_year + 1):
            got = ingest_season(season, conn=conn, schedule=schedule)
            for k in total:
                total[k] += got[k]
    finally:
        conn.close()
    logger.info(f"NFL props data backfill {start_year}-{end_year}: {total}")
    return total


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="nflverse → NFL prop modelling tables")
    ap.add_argument("--season", type=int, help="ingest one season")
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"),
                    help="ingest a season range, e.g. --backfill 2015 2025")
    args = ap.parse_args()
    if args.backfill:
        backfill(args.backfill[0], args.backfill[1])
    elif args.season:
        ingest_season(args.season)
    else:
        run_nfl_props_data_ingestor()
