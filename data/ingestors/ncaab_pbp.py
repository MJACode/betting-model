"""Free men's college basketball play-by-play into Supabase: the game state the
NCAAB in-play model reads, for the seasons it is graded on and the night it
bets.

WHY. The in-play model (models/ncaab_live_ig.py) prices a quote from the score
and clock at the quote's stamp. Neither `games` nor `ncaab_period_scores`
(half scores only) can say what the score was at 21:55:37; only a play-by-play
with wall-clock times can. Nothing NCAAB stored one before 2026-11-07.

TWO SOURCES, ONE PARSER.
  * History: sportsdataverse's GitHub release of ESPN's feed, one parquet per
    season (`espn_mens_college_basketball_pbp/play_by_play_<season>.parquet`,
    free; the file year is OUR season label, the ending year). Measured
    2026-11-07: 2021-22 holds 5,830 games, 99.2% of plays with a wallclock;
    2025-26 holds 6,275 games, 100.0%.
  * Live: ESPN's free summary endpoint (`fetch_summary_plays`), which the
    release is a flattening of. Both go through `play_row`, so the loop reads a
    play exactly as the grade read it (the NBA in-play lesson: one parsing path,
    docs/sports/nba.md "In play").

WHAT IT WRITES (both tables created here, locked down beside their CREATE).
  ncaab_pbp        one row per play: period, seconds left in it, seconds of the
                   game gone, ESPN's wallclock (when ESPN LOGGED the play), the
                   running score in OUR orientation, the play type and team.
  ncaab_pbp_games  one row per ESPN game loaded: our game_id, the orientation
                   check against `ncaab_events`, play counts, the wallclock
                   share, the last running score against `games`' final. Written
                   in the SAME commit as the game's plays, so it is the resume
                   ledger: a game in it is never loaded again without --force.

MATCHING. `ncaab_events` maps ESPN's event id to our game_id, and our games row
is in ESPN's orientation (data/ingestors/ncaab_espn_ingestor.py). The release's
home team id is checked against the event's; when they are swapped the scores
are swapped back (`sides_swapped`), and a game whose teams match neither way is
skipped and counted, never guessed. A game not in `ncaab_events` (a non-D-I
exhibition) is skipped and counted.

    python -m data.ingestors.ncaab_pbp --seasons 2021 2026
    python -m data.ingestors.ncaab_pbp --seasons 2026 2026 --dry-run
"""
from __future__ import annotations

import argparse
import csv
import io
import math
import sys
from datetime import datetime, timezone

import pandas as pd
import requests
from loguru import logger

from data.anon_readable import API_ROLES, lock_down
from data.ddl_guard import schema_is_current

SOURCE = "sportsdataverse_espn_mbb_pbp"
LIVE_SOURCE = "espn_summary_api"
RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
PBP_URL = RELEASE + "/espn_mens_college_basketball_pbp/play_by_play_{season}.parquet"
SUMMARY_URL = ("https://site.api.espn.com/apis/site/v2/sports/basketball/"
               "mens-college-basketball/summary")
HALF_S = 1200            # men's college basketball: two 20-minute halves
OT_S = 300               # five-minute overtimes
GAMES_PER_COMMIT = 40    # ~460 plays a game -> ~18,000 rows a commit

PBP_TABLE = "ncaab_pbp"
GAMES_TABLE = "ncaab_pbp_games"
PBP_COLS = (
    "espn_game_id", "play_no", "sequence_number", "game_id", "season", "season_type",
    "period", "clock_s", "game_s", "wallclock", "type_id", "type_text", "scoring_play",
    "shooting_play", "score_value", "points_attempted", "home_score", "away_score",
    "team_side", "espn_team_id", "athlete_id_1", "athlete_id_2", "text", "source",
)
GAME_COLS = (
    "espn_game_id", "game_id", "season", "season_type", "game_date", "home_espn_id",
    "away_espn_id", "sides_swapped", "n_plays", "n_periods", "wallclock_share",
    "first_wallclock", "last_wallclock", "last_home_score", "last_away_score",
    "games_home_score", "games_away_score", "score_matches", "source", "loaded_at",
)
PBP_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_pbp (
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
PBP_INDEXES = (
    ("idx_ncaab_pbp_game", "CREATE INDEX IF NOT EXISTS idx_ncaab_pbp_game "
                           "ON ncaab_pbp (game_id, wallclock)"),
    ("idx_ncaab_pbp_season", "CREATE INDEX IF NOT EXISTS idx_ncaab_pbp_season "
                             "ON ncaab_pbp (season)"),
)
GAMES_DDL = """
CREATE TABLE IF NOT EXISTS ncaab_pbp_games (
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
GAMES_INDEXES = (
    ("idx_ncaab_pbp_games_gid", "CREATE INDEX IF NOT EXISTS idx_ncaab_pbp_games_gid "
                                "ON ncaab_pbp_games (game_id)"),
)


def ensure_tables(conn) -> None:
    """Create both tables once, locked down; a current schema costs one read each."""
    changed = False
    if not schema_is_current(conn, PBP_TABLE, columns=PBP_COLS,
                             indexes=tuple(n for n, _ in PBP_INDEXES),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(PBP_DDL)
        for _, ddl in PBP_INDEXES:
            conn.execute(ddl)
        lock_down(conn, PBP_TABLE)
        changed = True
    if not schema_is_current(conn, GAMES_TABLE, columns=GAME_COLS,
                             indexes=tuple(n for n, _ in GAMES_INDEXES),
                             rls=True, revoked_from=API_ROLES):
        conn.execute(GAMES_DDL)
        for _, ddl in GAMES_INDEXES:
            conn.execute(ddl)
        lock_down(conn, GAMES_TABLE)
        changed = True
    if changed:
        conn.commit()


# ── one play, from either source ─────────────────────────────────────────────

def _int(v):
    try:
        if v is None or (isinstance(v, float) and math.isnan(v)) or str(v).strip() == "":
            return None
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _bool(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "t", "yes")
    return bool(v)


def _text(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    t = str(v).strip()
    return t or None


def clock_seconds(display: str | None) -> float | None:
    """'19:58' -> 1198.0, '0:07.4' -> 7.4; None when unreadable."""
    if not display:
        return None
    try:
        if ":" in str(display):
            m, s = str(display).split(":", 1)
            return int(m) * 60 + float(s)
        return float(display)
    except ValueError:
        return None


def game_seconds(period: int | None, clock_s: float | None) -> float | None:
    """Seconds of the game gone at a play: two 1,200-second halves, then
    300-second overtimes. None when either input is missing."""
    if period is None or clock_s is None or period < 1:
        return None
    if period <= 2:
        return (period - 1) * HALF_S + (HALF_S - clock_s)
    return 2 * HALF_S + (period - 3) * OT_S + (OT_S - clock_s)


def parse_wallclock(v) -> datetime | None:
    s = _text(v)
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def play_row(*, espn_game_id: int, play_no: int, sequence_number, game_id: str,
             season: int, season_type, period, clock_display, wallclock, type_id,
             type_text, scoring_play, shooting_play, score_value, points_attempted,
             home_score, away_score, team_id, home_espn_id, away_espn_id,
             athlete_id_1, athlete_id_2, text, swapped: bool, source: str) -> dict:
    """The one normalised play. `home_score` / `away_score` are ESPN's running
    score in ESPN's orientation; `swapped` turns them round so they are OUR
    home and away (ncaab_events / games)."""
    p = _int(period)
    c = clock_seconds(clock_display)
    h, a = _int(home_score), _int(away_score)
    if swapped:
        h, a = a, h
    team = _int(team_id)
    side = None
    if team is not None:
        home_id, away_id = (_int(away_espn_id), _int(home_espn_id)) if swapped else \
                           (_int(home_espn_id), _int(away_espn_id))
        side = "H" if team == home_id else ("A" if team == away_id else None)
    return {
        "espn_game_id": int(espn_game_id), "play_no": int(play_no),
        "sequence_number": _int(sequence_number), "game_id": game_id,
        "season": int(season), "season_type": _int(season_type), "period": p,
        "clock_s": c, "game_s": game_seconds(p, c), "wallclock": parse_wallclock(wallclock),
        "type_id": _int(type_id), "type_text": _text(type_text),
        "scoring_play": _bool(scoring_play), "shooting_play": _bool(shooting_play),
        "score_value": _int(score_value), "points_attempted": _int(points_attempted),
        "home_score": h, "away_score": a, "team_side": side, "espn_team_id": team,
        "athlete_id_1": _int(athlete_id_1), "athlete_id_2": _int(athlete_id_2),
        "text": _text(text), "source": source,
    }


def summary_rows(summary: dict, *, espn_game_id: int, game_id: str, season: int,
                 home_espn_id: int | None, away_espn_id: int | None) -> list[dict]:
    """ESPN summary JSON -> play rows, through `play_row`. The orientation is
    read off the summary's own competitors against the event's stored ids."""
    comp = ((summary.get("header") or {}).get("competitions") or [{}])[0]
    teams = {c.get("homeAway"): _int((c.get("team") or {}).get("id"))
             for c in comp.get("competitors") or []}
    swapped = (home_espn_id is not None and teams.get("away") == home_espn_id
               and teams.get("home") == away_espn_id)
    season_type = ((summary.get("header") or {}).get("season") or {}).get("type")
    out = []
    for i, pl in enumerate(summary.get("plays") or [], start=1):
        parts = pl.get("participants") or []
        aid = [_int(((x or {}).get("athlete") or {}).get("id")) for x in parts[:2]]
        out.append(play_row(
            espn_game_id=espn_game_id, play_no=i, sequence_number=pl.get("sequenceNumber"),
            game_id=game_id, season=season, season_type=season_type,
            period=(pl.get("period") or {}).get("number"),
            clock_display=(pl.get("clock") or {}).get("displayValue"),
            wallclock=pl.get("wallclock"), type_id=(pl.get("type") or {}).get("id"),
            type_text=(pl.get("type") or {}).get("text"), scoring_play=pl.get("scoringPlay"),
            shooting_play=pl.get("shootingPlay"), score_value=pl.get("scoreValue"),
            points_attempted=pl.get("pointsAttempted"), home_score=pl.get("homeScore"),
            away_score=pl.get("awayScore"), team_id=(pl.get("team") or {}).get("id"),
            home_espn_id=teams.get("home"), away_espn_id=teams.get("away"),
            athlete_id_1=aid[0] if aid else None, athlete_id_2=aid[1] if len(aid) > 1 else None,
            text=pl.get("text"), swapped=swapped, source=LIVE_SOURCE))
    return out


def fetch_summary_plays(espn_game_id: int, *, game_id: str, season: int,
                        home_espn_id: int | None, away_espn_id: int | None,
                        session: requests.Session | None = None,
                        timeout: float = 20.0) -> tuple[list[dict], dict]:
    """(play rows, the summary JSON) for one game from ESPN's free summary
    endpoint. Raises on an HTTP error: the caller fails closed."""
    s = session or requests
    r = s.get(SUMMARY_URL, params={"event": str(espn_game_id)}, timeout=timeout)
    r.raise_for_status()
    js = r.json()
    return summary_rows(js, espn_game_id=espn_game_id, game_id=game_id, season=season,
                        home_espn_id=home_espn_id, away_espn_id=away_espn_id), js


RELEASE_COLS = (
    "game_id", "game_play_number", "sequence_number", "season_type", "period_number",
    "clock_display_value", "wallclock", "type_id", "type_text", "scoring_play",
    "shooting_play", "score_value", "points_attempted", "home_score", "away_score",
    "team_id", "home_team_id", "away_team_id", "athlete_id_1", "athlete_id_2", "text",
)


def release_games(frame: pd.DataFrame):
    """Yield (espn game id, [record dict, ...]) per game, in play order. The
    needed columns are turned into Python lists once per season: a per-game
    DataFrame.to_dict over the release's 63 arrow-backed columns took 22 s per
    100 games (profiled 2026-11-07)."""
    cols = [c for c in RELEASE_COLS if c in frame.columns]
    df = frame[cols].sort_values(["game_id", "game_play_number"], kind="stable")
    lists = [df[c].tolist() for c in cols]
    recs = (dict(zip(cols, vals)) for vals in zip(*lists))
    cur, buf = None, []
    for rec in recs:
        gid = int(rec["game_id"])
        if gid != cur and buf:
            yield cur, buf
            buf = []
        cur = gid
        buf.append(rec)
    if buf:
        yield cur, buf


def release_rows(records, *, game_id: str, season: int, swapped: bool) -> list[dict]:
    """One game's release records (a DataFrame filtered to it, or the record
    dicts release_games yields) -> play rows, in play order."""
    if isinstance(records, pd.DataFrame):
        records = records.sort_values("game_play_number").to_dict("records")
    else:
        records = sorted(records, key=lambda r: int(r["game_play_number"]))
    out = []
    for rec in records:
        out.append(play_row(
            espn_game_id=int(rec["game_id"]), play_no=int(rec["game_play_number"]),
            sequence_number=rec.get("sequence_number"), game_id=game_id, season=season,
            season_type=rec.get("season_type"), period=rec.get("period_number"),
            clock_display=rec.get("clock_display_value"), wallclock=rec.get("wallclock"),
            type_id=rec.get("type_id"), type_text=rec.get("type_text"),
            scoring_play=rec.get("scoring_play"), shooting_play=rec.get("shooting_play"),
            score_value=rec.get("score_value"), points_attempted=rec.get("points_attempted"),
            home_score=rec.get("home_score"), away_score=rec.get("away_score"),
            team_id=rec.get("team_id"), home_espn_id=rec.get("home_team_id"),
            away_espn_id=rec.get("away_team_id"), athlete_id_1=rec.get("athlete_id_1"),
            athlete_id_2=rec.get("athlete_id_2"), text=rec.get("text"),
            swapped=swapped, source=SOURCE))
    return out


def game_ledger(rows: list[dict], *, event: dict, swapped: bool, source: str) -> dict:
    """The ncaab_pbp_games row for one game's plays."""
    wc = [r["wallclock"] for r in rows if r["wallclock"] is not None]
    last = next((r for r in reversed(rows) if r["home_score"] is not None), None)
    # games stores scores as NUMERIC (80.0); the ledger column is INTEGER
    gh, ga = _int(event.get("home_score")), _int(event.get("away_score"))
    lh = last["home_score"] if last else None
    la = last["away_score"] if last else None
    return {
        "espn_game_id": rows[0]["espn_game_id"], "game_id": event["game_id"],
        "season": rows[0]["season"], "season_type": rows[0]["season_type"],
        "game_date": event.get("game_date"), "home_espn_id": event.get("home_espn_id"),
        "away_espn_id": event.get("away_espn_id"), "sides_swapped": swapped,
        "n_plays": len(rows), "n_periods": max((r["period"] or 0) for r in rows),
        "wallclock_share": round(len(wc) / len(rows), 4) if rows else None,
        "first_wallclock": min(wc) if wc else None, "last_wallclock": max(wc) if wc else None,
        "last_home_score": lh, "last_away_score": la,
        "games_home_score": gh, "games_away_score": ga,
        "score_matches": (None if gh is None or lh is None
                          else bool(gh == lh and ga == la)),
        "source": source, "loaded_at": datetime.now(timezone.utc),
    }


# ── writes ───────────────────────────────────────────────────────────────────

def _copy(conn, table: str, cols: tuple[str, ...], rows: list[dict]) -> None:
    """COPY rows in (the per-row insert would take hours for 14M plays)."""
    buf = io.StringIO()
    w = csv.writer(buf)
    for r in rows:
        w.writerow(["\\N" if r.get(c) is None else
                    (r[c].isoformat() if isinstance(r[c], datetime) else r[c]) for c in cols])
    buf.seek(0)
    cur = conn._conn.cursor()
    cur.copy_expert(f"COPY {table} ({', '.join(cols)}) FROM STDIN "
                    "WITH (FORMAT csv, NULL '\\N')", buf)
    cur.close()


def write_games(conn, games: list[tuple[list[dict], dict]]) -> None:
    """Replace each game's plays and ledger row, all in one commit."""
    ids = [g["espn_game_id"] for _, g in games]
    conn.execute("DELETE FROM ncaab_pbp WHERE espn_game_id = ANY(%s)", (ids,))
    conn.execute("DELETE FROM ncaab_pbp_games WHERE espn_game_id = ANY(%s)", (ids,))
    plays = [r for rows, _ in games for r in rows]
    if plays:
        _copy(conn, PBP_TABLE, PBP_COLS, plays)
    _copy(conn, GAMES_TABLE, GAME_COLS, [g for _, g in games])
    conn.commit()


def events_for(conn, season: int) -> dict[int, dict]:
    """ESPN event id -> our event and its final, for one season."""
    rows = conn.execute("""
        SELECT e.espn_event_id, e.game_id, e.game_date, e.home_espn_id, e.away_espn_id,
               g.home_score, g.away_score
          FROM ncaab_events e LEFT JOIN games g ON g.game_id = e.game_id
         WHERE e.season = %s
    """, (season,)).fetchall()
    keys = ("espn_event_id", "game_id", "game_date", "home_espn_id", "away_espn_id",
            "home_score", "away_score")
    return {int(r[0]): dict(zip(keys, r)) for r in rows}


def loaded_ids(conn, season: int) -> set[int]:
    """ESPN ids already in the ledger; empty before the table exists (a dry run
    on a database this module has never reached)."""
    if conn.execute("SELECT to_regclass('public.ncaab_pbp_games')").fetchone()[0] is None:
        conn.commit()
        return set()
    return {int(r[0]) for r in conn.execute(
        "SELECT espn_game_id FROM ncaab_pbp_games WHERE season = %s", (season,)).fetchall()}


def orientation(release_home: int | None, release_away: int | None,
                event: dict) -> bool | None:
    """False = same orientation, True = swapped, None = different teams."""
    eh, ea = _int(event.get("home_espn_id")), _int(event.get("away_espn_id"))
    rh, ra = _int(release_home), _int(release_away)
    if (rh, ra) == (eh, ea):
        return False
    if (rh, ra) == (ea, eh):
        return True
    return None


def load_season(conn, season: int, *, force: bool = False, dry_run: bool = False,
                frame: pd.DataFrame | None = None) -> dict:
    stats = {"season": season, "games_in_file": 0, "loaded": 0, "already": 0,
             "no_event": 0, "team_mismatch": 0, "swapped": 0, "plays": 0,
             "score_mismatch": 0}
    if frame is None:
        r = requests.get(PBP_URL.format(season=season), timeout=300)
        if r.status_code == 404:
            stats["missing_file"] = True
            return stats
        r.raise_for_status()
        frame = pd.read_parquet(io.BytesIO(r.content))
    events = events_for(conn, season)
    have = set() if force else loaded_ids(conn, season)
    batch: list[tuple[list[dict], dict]] = []
    for eid, g in release_games(frame):
        stats["games_in_file"] += 1
        if eid in have:
            stats["already"] += 1
            continue
        ev = events.get(eid)
        if ev is None:
            stats["no_event"] += 1
            continue
        first = g[0]
        sw = orientation(first.get("home_team_id"), first.get("away_team_id"), ev)
        if sw is None:
            stats["team_mismatch"] += 1
            continue
        stats["swapped"] += int(sw)
        rows = release_rows(g, game_id=ev["game_id"], season=season, swapped=sw)
        if not rows:
            continue
        led = game_ledger(rows, event=ev, swapped=sw, source=SOURCE)
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
    return stats


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seasons", nargs=2, type=int, metavar=("FIRST", "LAST"),
                    default=(2021, 2026), help="ending-year seasons (2026 = 2025-26)")
    ap.add_argument("--force", action="store_true", help="reload games already stored")
    ap.add_argument("--dry-run", action="store_true", help="parse and count; write nothing")
    args = ap.parse_args(argv)

    from data.db import get_connection
    conn = get_connection()
    try:
        if not args.dry_run:
            ensure_tables(conn)
        for s in range(args.seasons[0], args.seasons[1] + 1):
            res = load_season(conn, s, force=args.force, dry_run=args.dry_run)
            print(res, flush=True)
            logger.info(f"ncaab_pbp {res}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
