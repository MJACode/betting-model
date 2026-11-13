"""Free women's college basketball play-by-play into Supabase: the game state
the halftime total model (models/ncaabw_live_ht.py) is fitted on and reads at
the break.

WHY. The model prices a halftime total from the score and the clock at the
quote's stamp, and is fitted on the score every 30 seconds of every priced
game. `games` holds finals and `ncaabw_period_scores` quarter scores; only a
play-by-play with wall-clock times says what the score was when a book stamped
its number. Until 2026-11-11 the women's play-by-play sat in a research cache
on one machine (CLAUDE.md section 1b: everything goes in Supabase).

TWO SOURCES, ONE PARSER (the men's module's `play_row`, with the women's clock).
  * History: sportsdataverse's GitHub release of ESPN's feed, one parquet per
    season (`espn_womens_college_basketball_pbp/play_by_play_<season>.parquet`,
    free; the file year is OUR season label, the ending year). Measured
    2026-11-11: 2024-25 holds 1,973,907 plays, 2025-26 2,824,090, 2026-27 to
    2026-11-09 244,282.
  * Live: ESPN's free summary endpoint (`summary_rows`), which the release is a
    flattening of.

THE WOMEN'S CLOCK. Four 10-minute quarters since 2015-16 (two halves before:
data.ingestors.ncaabw_teams.regulation_periods), then 5-minute overtimes.
`game_s` is seconds of the game gone on that clock, so halftime is 1,200 and
the end of regulation 2,400 in every season.

PLAY NUMBERS ARE NOT TIME ORDER. Measured on the 2026-27 file: in 83% of games
ESPN's play number does not rise with its wallclock (substitutions and
corrections are logged late). A reader that wants the state at an instant
sorts by wallclock, then play number (models/ncaabw_live_ht.states_from_rows).

WHAT IT WRITES (both created here, locked down beside their CREATE; the men's
columns exactly).
  ncaabw_pbp        one row per play.
  ncaabw_pbp_games  one row per ESPN game loaded, written in the SAME commit
                    as the game's plays: the resume ledger.

MATCHING. `ncaabw_events` maps ESPN's event id to our game_id. The release's
home team id is checked against the event's; when they are swapped the scores
are swapped back, and a game whose teams match neither way is skipped and
counted, never guessed.

    python -m data.ingestors.ncaabw_pbp --seasons 2025 2027
    python -m data.ingestors.ncaabw_pbp --seasons 2027 2027 --from-dir ~/ncaabw_research/cache
    python -m data.ingestors.ncaabw_pbp --seasons 2027 2027 --dry-run
"""
from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

import pandas as pd
import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current
from data.ingestors import ncaab_pbp as base
from data.ingestors.ncaabw_teams import regulation_periods

SOURCE = "sportsdataverse_espn_wbb_pbp"
LIVE_SOURCE = "espn_summary_api"
PBP_URL = base.RELEASE + "/espn_womens_college_basketball_pbp/play_by_play_{season}.parquet"
SUMMARY_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
               "womens-college-basketball/summary")
REG_S = 2400.0           # regulation: four 10-minute quarters (two halves before 2015-16)
OT_S = 300.0             # five-minute overtimes
GAMES_PER_COMMIT = 40

PBP_TABLE = "ncaabw_pbp"
GAMES_TABLE = "ncaabw_pbp_games"
PBP_COLS = base.PBP_COLS
GAME_COLS = base.GAME_COLS
# The men's two tables under the women's names, written out so the CREATE sits
# beside its lock_down (tests/test_anon_readable.py); tests/test_ncaabw_live_ht.py
# holds the columns to the men's.
PBP_DDL = """
CREATE TABLE IF NOT EXISTS ncaabw_pbp (
    espn_game_id      BIGINT   NOT NULL,
    play_no           INTEGER  NOT NULL,
    sequence_number   BIGINT,
    game_id           TEXT     NOT NULL,
    season            INTEGER  NOT NULL,
    season_type       SMALLINT,
    period            SMALLINT,
    clock_s           REAL,
    game_s            REAL,
    wallclock         TIMESTAMPTZ,
    type_id           INTEGER,
    type_text         TEXT,
    scoring_play      BOOLEAN,
    shooting_play     BOOLEAN,
    score_value       SMALLINT,
    points_attempted  SMALLINT,
    home_score        INTEGER,
    away_score        INTEGER,
    team_side         TEXT,
    espn_team_id      INTEGER,
    athlete_id_1      BIGINT,
    athlete_id_2      BIGINT,
    text              TEXT,
    source            TEXT     NOT NULL,
    PRIMARY KEY (espn_game_id, play_no)
)
"""
GAMES_DDL = """
CREATE TABLE IF NOT EXISTS ncaabw_pbp_games (
    espn_game_id      BIGINT PRIMARY KEY,
    game_id           TEXT NOT NULL,
    season            INTEGER NOT NULL,
    season_type       SMALLINT,
    game_date         TEXT,
    home_espn_id      INTEGER,
    away_espn_id      INTEGER,
    sides_swapped     BOOLEAN NOT NULL DEFAULT FALSE,
    n_plays           INTEGER,
    n_periods         INTEGER,
    wallclock_share   REAL,
    first_wallclock   TIMESTAMPTZ,
    last_wallclock    TIMESTAMPTZ,
    last_home_score   INTEGER,
    last_away_score   INTEGER,
    games_home_score  INTEGER,
    games_away_score  INTEGER,
    score_matches     BOOLEAN,
    source            TEXT NOT NULL,
    loaded_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
PBP_INDEXES = (
    ("idx_ncaabw_pbp_game", "CREATE INDEX IF NOT EXISTS idx_ncaabw_pbp_game "
                            "ON ncaabw_pbp (game_id, wallclock)"),
    ("idx_ncaabw_pbp_season", "CREATE INDEX IF NOT EXISTS idx_ncaabw_pbp_season "
                              "ON ncaabw_pbp (season)"),
)
GAMES_INDEXES = (
    ("idx_ncaabw_pbp_games_gid", "CREATE INDEX IF NOT EXISTS idx_ncaabw_pbp_games_gid "
                                 "ON ncaabw_pbp_games (game_id)"),
)


def ensure_tables(conn) -> None:
    """Create both tables once, locked down; a current schema costs one read each."""
    changed = False
    for table, cols, ddl, indexes in ((PBP_TABLE, PBP_COLS, PBP_DDL, PBP_INDEXES),
                                      (GAMES_TABLE, GAME_COLS, GAMES_DDL, GAMES_INDEXES)):
        if schema_is_current(conn, table, columns=cols, indexes=tuple(n for n, _ in indexes),
                             rls=True, revoked_from=API_ROLES):
            continue
        conn.execute(ddl)
        for _, idx in indexes:
            conn.execute(idx)
        lock_down(conn, table)
        changed = True
    if changed:
        conn.commit()


# ── one play, from either source ─────────────────────────────────────────────

def game_seconds(period: int | None, clock_s: float | None, season: int | None) -> float | None:
    """Seconds of the game gone at a play, on the women's clock. None when
    either input is missing."""
    if period is None or clock_s is None or period < 1:
        return None
    n = regulation_periods(season)
    length = REG_S / n
    if period <= n:
        return (period - 1) * length + (length - clock_s)
    return REG_S + (period - n - 1) * OT_S + (OT_S - clock_s)


def _womens(rows: list[dict], season: int, source: str) -> list[dict]:
    """The men's parsed rows put on the women's clock and under this module's source."""
    for r in rows:
        r["game_s"] = game_seconds(r["period"], r["clock_s"], season)
        r["source"] = source
    return rows


def summary_rows(summary: dict, *, espn_game_id: int, game_id: str, season: int,
                 home_espn_id: int | None, away_espn_id: int | None) -> list[dict]:
    """ESPN's women's summary JSON -> play rows, in OUR orientation."""
    rows = base.summary_rows(summary, espn_game_id=espn_game_id, game_id=game_id, season=season,
                             home_espn_id=home_espn_id, away_espn_id=away_espn_id)
    return _womens(rows, season, LIVE_SOURCE)


def release_rows(records, *, game_id: str, season: int, swapped: bool) -> list[dict]:
    """One game's release records -> play rows, in play order."""
    return _womens(base.release_rows(records, game_id=game_id, season=season, swapped=swapped),
                   season, SOURCE)


# ── writes ───────────────────────────────────────────────────────────────────

def write_games(conn, games: list[tuple[list[dict], dict]]) -> None:
    """Replace each game's plays and ledger row, all in one commit."""
    ids = [g["espn_game_id"] for _, g in games]
    conn.execute(f"DELETE FROM {PBP_TABLE} WHERE espn_game_id = ANY(%s)", (ids,))
    conn.execute(f"DELETE FROM {GAMES_TABLE} WHERE espn_game_id = ANY(%s)", (ids,))
    plays = [r for rows, _ in games for r in rows]
    if plays:
        base._copy(conn, PBP_TABLE, PBP_COLS, plays)
    base._copy(conn, GAMES_TABLE, GAME_COLS, [g for _, g in games])
    conn.commit()


def events_for(conn, season: int) -> dict[int, dict]:
    """ESPN event id -> our event and its final, for one season."""
    rows = conn.execute("""
        SELECT e.espn_event_id, e.game_id, e.game_date, e.home_espn_id, e.away_espn_id,
               g.home_score, g.away_score
          FROM ncaabw_events e LEFT JOIN games g ON g.game_id = e.game_id
         WHERE e.season = %s
    """, (season,)).fetchall()
    keys = ("espn_event_id", "game_id", "game_date", "home_espn_id", "away_espn_id",
            "home_score", "away_score")
    return {int(r[0]): dict(zip(keys, r)) for r in rows}


def loaded_ids(conn, season: int) -> set[int]:
    """ESPN ids already in the ledger; empty before the table exists."""
    if conn.execute(f"SELECT to_regclass('public.{GAMES_TABLE}')").fetchone()[0] is None:
        conn.commit()
        return set()
    return {int(r[0]) for r in conn.execute(
        f"SELECT espn_game_id FROM {GAMES_TABLE} WHERE season = %s", (season,)).fetchall()}


def release_frame(season: int, from_dir: str | None = None) -> pd.DataFrame | None:
    """The season's release file: a copy in `from_dir` (pbp_<season>.parquet or
    play_by_play_<season>.parquet) when one is there, else the download. None
    when the release has no file for the season."""
    import pyarrow.parquet as pq

    def read(src) -> pd.DataFrame:
        # a season's file holds only some of the columns (2024-25 has no points_attempted)
        have = set(pq.ParquetFile(src).schema_arrow.names)
        return pd.read_parquet(src, columns=[c for c in base.RELEASE_COLS if c in have])

    if from_dir:
        for name in (f"pbp_{season}.parquet", f"play_by_play_{season}.parquet"):
            f = Path(from_dir).expanduser() / name
            if f.exists():
                return read(f)
    r = requests.get(PBP_URL.format(season=season), timeout=300)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return read(io.BytesIO(r.content))


def parsed_games(frame: pd.DataFrame, events: dict[int, dict], season: int, stats: dict | None = None):
    """Yield (event, swapped, play rows) for every release game that is ours,
    through the one parser. `stats` counts what was left out and why."""
    stats = stats if stats is not None else {}
    for eid, g in base.release_games(frame):
        stats["games_in_file"] = stats.get("games_in_file", 0) + 1
        ev = events.get(eid)
        if ev is None:
            stats["no_event"] = stats.get("no_event", 0) + 1
            continue
        sw = base.orientation(g[0].get("home_team_id"), g[0].get("away_team_id"), ev)
        if sw is None:
            stats["team_mismatch"] = stats.get("team_mismatch", 0) + 1
            continue
        rows = release_rows(g, game_id=ev["game_id"], season=season, swapped=sw)
        if rows:
            yield ev, sw, rows


def load_season(conn, season: int, *, force: bool = False, dry_run: bool = False,
                frame: pd.DataFrame | None = None, from_dir: str | None = None) -> dict:
    stats = {"season": season, "games_in_file": 0, "loaded": 0, "already": 0, "no_event": 0,
             "team_mismatch": 0, "swapped": 0, "plays": 0, "score_mismatch": 0}
    if frame is None:
        frame = release_frame(season, from_dir)
        if frame is None:
            stats["missing_file"] = True
            return stats
    events = events_for(conn, season)
    have = set() if force else loaded_ids(conn, season)
    stored = frame["game_id"].astype("int64").isin(have)
    stats["already"] = int(frame.loc[stored, "game_id"].nunique())
    frame = frame[~stored]
    batch: list[tuple[list[dict], dict]] = []
    for ev, sw, rows in parsed_games(frame, events, season, stats):
        led = base.game_ledger(rows, event=ev, swapped=sw, source=SOURCE)
        stats["swapped"] += int(sw)
        stats["score_mismatch"] += int(led["score_matches"] is False)
        stats["plays"] += len(rows)
        stats["loaded"] += 1
        batch.append((rows, led))
        if len(batch) >= GAMES_PER_COMMIT:
            if not dry_run:
                write_games(conn, batch)
            batch = []
    if batch and not dry_run:
        write_games(conn, batch)
    stats["games_in_file"] += stats["already"]
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=(2025, 2027), help="ending-year seasons (2027 = 2026-27)")
    ap.add_argument("--from-dir", help="read pbp_<season>.parquet from here before downloading")
    ap.add_argument("--force", action="store_true", help="reload games already stored")
    ap.add_argument("--dry-run", action="store_true", help="parse and count; write nothing")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
        if not args.dry_run:
            ensure_tables(conn)
        for s in range(args.seasons[0], args.seasons[1] + 1):
            res = load_season(conn, s, force=args.force, dry_run=args.dry_run, from_dir=args.from_dir)
            print(res, flush=True)
            logger.info(f"ncaabw_pbp {res}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
