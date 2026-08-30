"""
mlb_pbp_ingestor.py — Phase 2a of the live (in-play) betting build.

Backfills historical play-by-play data into the `plays` table. One row per
play in a completed game; the state vector *before* the play becomes the
model input and the game's final outcome becomes the label.

Why MLB Stats API and not Retrosheet?
-------------------------------------
- The MLB Stats API live feed (`/api/v1.1/game/{gamePk}/feed/live`) is the
  EXACT same endpoint the Phase 1 live poller queries at game time. Training
  on it means the state vector at training time matches the state vector at
  inference time — no parser drift between train and serve.
- 2008+ coverage is plenty: 17+ seasons × ~2,400 games/season ≈ 41K games of
  play-by-play, more than enough to fit win-probability models.
- Trivial parser (JSON structured by MLB) versus Retrosheet's dense event
  notation (S8/G means single to center on a grounder, etc.).
- Free. No external binaries (cwgame/cwevent), no scraping risk.

Retrosheet remains the only viable source if we ever want pre-2008 PBP.
`retrosheet_ingestor.py` is kept as a documented Plan B.

Usage
-----
    # Backfill an entire season — idempotent (skips games already loaded)
    python -m data.ingestors.mlb_pbp_ingestor --backfill 2024 2024

    # Backfill a range of seasons (long-running — overnight job)
    python -m data.ingestors.mlb_pbp_ingestor --backfill 2019 2025

    # One specific game — useful for spot-checks
    python -m data.ingestors.mlb_pbp_ingestor --game-id MLB_2024-04-05_NYY_BOS

API budget
----------
~46K games × 1 feed-live call ≈ 46K MLB Stats API calls per full backfill.
At 200ms per call that is ~2.5 hours. MLB Stats API has no published rate
limit but we throttle to be polite (150ms sleep between calls).
"""

from __future__ import annotations

import argparse
import time
from datetime import date, datetime, timedelta
from typing import Optional

import requests
import statsapi
from loguru import logger

from data.db import get_connection, DBConnection
from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS

_MLB_API_V11 = "https://statsapi.mlb.com/api/v1.1"
_API_SLEEP_SEC = 0.15


# ── Pure parser (no I/O) ──────────────────────────────────────────────────────

def _bases_after_from_matchup(matchup: dict) -> str:
    """
    Encode runners after the play from matchup.postOnFirst/Second/Third.
    Empty matchup → '000'. Same convention as live_game_state.bases_state.
    """
    matchup = matchup or {}
    return "".join(
        "1" if matchup.get(f"postOn{base}") else "0"
        for base in ("First", "Second", "Third")
    )


def _split_event_type(result: dict) -> tuple[Optional[str], Optional[str]]:
    """
    Pull the canonical eventType (machine-readable) and description (free text).
    MLB Stats API event types: 'single', 'double', 'home_run', 'strikeout',
    'walk', 'hit_by_pitch', 'force_out', 'field_out', 'sac_fly', 'grounded_into_double_play',
    'wild_pitch' (rare — runner advance), 'pickoff_1b', etc.
    """
    result = result or {}
    return result.get("eventType"), result.get("description")


def parse_play(
    play: dict,
    *,
    state_before: dict,
    home_won: Optional[int],
    season: int,
    game_id: str,
    play_index: int,
) -> dict:
    """
    Convert one allPlays[] entry into a `plays`-row dict.

    state_before is the running state we maintain as we walk the play list.
    We rely on `about.isTopInning`, `count.outs`, and `result.{home,away}Score`
    plus matchup.postOn* to compute state after.
    """
    result   = play.get("result")  or {}
    about    = play.get("about")   or {}
    count    = play.get("count")   or {}
    matchup  = play.get("matchup") or {}

    half_inning = "top" if about.get("isTopInning") else "bottom"

    # Outs/score AFTER the play come straight from the API.
    outs_after        = count.get("outs")
    score_home_after  = result.get("homeScore")
    score_away_after  = result.get("awayScore")
    bases_after       = _bases_after_from_matchup(matchup)

    # Outs/score BEFORE the play = AFTER from previous state (or 0 if first play).
    outs_before       = state_before.get("outs_after", 0)
    score_home_before = state_before.get("score_home_after", 0)
    score_away_before = state_before.get("score_away_after", 0)
    bases_before      = state_before.get("bases_after", "000")

    # If a half-inning rolled over, outs reset to 0. We detect this by comparing
    # current half-inning to the previous play's half-inning.
    prev_half = state_before.get("half_inning")
    if prev_half and prev_half != half_inning:
        outs_before = 0
        bases_before = "000"

    event_type, description = _split_event_type(result)

    batter_id  = ((matchup.get("batter")  or {}).get("id"))
    pitcher_id = ((matchup.get("pitcher") or {}).get("id"))
    bat_side   = ((matchup.get("batSide")    or {}).get("code"))
    pitch_hand = ((matchup.get("pitchHand") or {}).get("code"))

    # Runs and outs added by this play — derived from before/after diff.
    runs_on_play = None
    if score_home_after is not None and score_away_after is not None:
        runs_on_play = (score_home_after + score_away_after) - (score_home_before + score_away_before)
    outs_added = None
    if outs_after is not None:
        outs_added = max(0, outs_after - outs_before)

    return {
        "game_id":           game_id,
        "season":            season,
        "play_index":        play_index,
        "inning":            about.get("inning"),
        "half_inning":       half_inning,
        "outs_before":       outs_before,
        "bases_before":      bases_before,
        "score_home_before": score_home_before,
        "score_away_before": score_away_before,
        "batter_id":         str(batter_id) if batter_id is not None else None,
        "pitcher_id":        str(pitcher_id) if pitcher_id is not None else None,
        "bat_side":          bat_side,
        "pitch_hand":        pitch_hand,
        "event_type":        event_type,
        "description":       description,
        "runs_on_play":      runs_on_play,
        "outs_added":        outs_added,
        "outs_after":        outs_after,
        "bases_after":       bases_after,
        "score_home_after":  score_home_after,
        "score_away_after":  score_away_after,
        "home_won":          home_won,
    }


def parse_game_plays(
    feed: dict,
    *,
    game_id: str,
    season: int,
    home_won: Optional[int],
) -> list[dict]:
    """Walk allPlays[] and emit `plays`-row dicts in order."""
    all_plays = (feed.get("liveData") or {}).get("plays", {}).get("allPlays") or []
    rows: list[dict] = []
    state = {
        "outs_after": 0,
        "score_home_after": 0,
        "score_away_after": 0,
        "bases_after": "000",
        "half_inning": None,
    }
    for i, play in enumerate(all_plays):
        row = parse_play(
            play,
            state_before=state,
            home_won=home_won,
            season=season,
            game_id=game_id,
            play_index=i,
        )
        rows.append(row)
        # Carry state forward.
        state = {
            "outs_after":       row["outs_after"]       if row["outs_after"]       is not None else state["outs_after"],
            "score_home_after": row["score_home_after"] if row["score_home_after"] is not None else state["score_home_after"],
            "score_away_after": row["score_away_after"] if row["score_away_after"] is not None else state["score_away_after"],
            "bases_after":      row["bases_after"],
            "half_inning":      row["half_inning"],
        }
    return rows


# ── Network I/O ───────────────────────────────────────────────────────────────

def _fetch_pbp(mlbam_game_pk: int) -> Optional[dict]:
    url = f"{_MLB_API_V11}/game/{mlbam_game_pk}/feed/live"
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.warning(f"  PBP fetch error for gamePk {mlbam_game_pk}: {exc}")
        return None


# ── DB helpers ────────────────────────────────────────────────────────────────

_INSERT_SQL = """
INSERT INTO plays (
    game_id, season, play_index, inning, half_inning,
    outs_before, bases_before, score_home_before, score_away_before,
    batter_id, pitcher_id, bat_side, pitch_hand,
    event_type, description, runs_on_play, outs_added,
    outs_after, bases_after, score_home_after, score_away_after,
    home_won
) VALUES (
    %(game_id)s, %(season)s, %(play_index)s, %(inning)s, %(half_inning)s,
    %(outs_before)s, %(bases_before)s, %(score_home_before)s, %(score_away_before)s,
    %(batter_id)s, %(pitcher_id)s, %(bat_side)s, %(pitch_hand)s,
    %(event_type)s, %(description)s, %(runs_on_play)s, %(outs_added)s,
    %(outs_after)s, %(bases_after)s, %(score_home_after)s, %(score_away_after)s,
    %(home_won)s
)
"""


def _already_loaded(conn: DBConnection, game_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM plays WHERE game_id = %s LIMIT 1", (game_id,)
    ).fetchone()
    return row is not None


def _lookup_home_won(conn: DBConnection, game_id: str) -> Optional[int]:
    row = conn.execute(
        "SELECT home_win, home_score FROM games WHERE game_id = %s", (game_id,)
    ).fetchone()
    if not row:
        return None
    home_win, home_score = row
    # If the game isn't actually complete (no score), we cannot label.
    if home_score is None:
        return None
    return int(home_win) if home_win is not None else None


# ── Per-game ingest ───────────────────────────────────────────────────────────

def ingest_pbp_for_game(
    game_id: str,
    mlbam_game_pk: int,
    season: int,
    conn: DBConnection,
    *,
    force: bool = False,
) -> int:
    """Fetch PBP for one game and insert. Returns number of plays written."""
    if not force and _already_loaded(conn, game_id):
        logger.debug(f"  {game_id} already loaded — skipping")
        return 0

    home_won = _lookup_home_won(conn, game_id)
    if home_won is None:
        logger.debug(f"  {game_id} has no home_win label yet — skipping")
        return 0

    feed = _fetch_pbp(mlbam_game_pk)
    if not feed:
        return 0

    rows = parse_game_plays(feed, game_id=game_id, season=season, home_won=home_won)
    if not rows:
        logger.debug(f"  {game_id} returned 0 plays — skipping")
        return 0

    conn.executemany(_INSERT_SQL, rows)
    conn.commit()
    return len(rows)


# ── Backfill driver ───────────────────────────────────────────────────────────

def _game_id_from_schedule(g: dict, target_date: str) -> Optional[str]:
    away = STATSAPI_TEAM_IDS.get(g["away_id"])
    home = STATSAPI_TEAM_IDS.get(g["home_id"])
    if not away or not home:
        return None
    return f"MLB_{target_date}_{away}_{home}"


def backfill_pbp(start_year: int, end_year: int, force: bool = False) -> dict:
    """
    Backfill PBP for every completed MLB game from start_year through end_year.

    Iterates day by day so the schedule endpoint is called once per date and
    we fan out to per-game PBP calls only for games that resolve to a row in
    our `games` table with a known final score.
    """
    conn = get_connection()
    totals = {"games_seen": 0, "games_loaded": 0, "plays_written": 0, "skipped": 0, "errors": 0}
    try:
        for season in range(start_year, end_year + 1):
            # MLB regular season is March/April → October. Playoff games extend
            # into November. We sweep Mar 1 → Nov 30 to be safe.
            d = date(season, 3, 1)
            end = date(season, 11, 30)
            while d <= end:
                target_date = d.isoformat()
                try:
                    games = statsapi.schedule(date=target_date, sportId=1)
                except Exception as exc:
                    logger.warning(f"  schedule failed for {target_date}: {exc}")
                    games = []

                for g in games:
                    totals["games_seen"] += 1
                    game_id = _game_id_from_schedule(g, target_date)
                    if not game_id:
                        totals["skipped"] += 1
                        continue
                    try:
                        n = ingest_pbp_for_game(game_id, g["game_id"], season, conn, force=force)
                    except Exception as exc:
                        # ROLL BACK, or the rest of the run is a silent no-op.
                        # Postgres poisons a connection after a failed statement
                        # ("current transaction is aborted, commands ignored
                        # until end of transaction block"), so without this ONE
                        # bad game turns every subsequent one into the same
                        # error -- and the run still ends with a SUCCESS line,
                        # because the summary only counts what it wrote and
                        # never mentions what it could not. Seen 2026-08-30: a
                        # unique-key conflict at ~600 games of 1,818 left the
                        # remaining 2,200 schedule entries "processed" and
                        # nothing written, reported as "complete: 0/2869 games".
                        try:
                            conn.rollback()
                        except Exception:
                            pass
                        totals["errors"] += 1
                        logger.warning(f"  {game_id} ingest error: {exc}")
                        n = 0
                    if n > 0:
                        totals["games_loaded"] += 1
                        totals["plays_written"] += n
                        logger.info(f"  {game_id}: {n} plays")
                    time.sleep(_API_SLEEP_SEC)

                d += timedelta(days=1)
            logger.success(
                f"Season {season} done: "
                f"{totals['games_loaded']} games, {totals['plays_written']} plays"
            )
    finally:
        conn.close()

    # A run that wrote nothing is not a success, whatever the exit code says.
    if totals["errors"] and not totals["games_loaded"]:
        logger.error(
            f"PBP backfill {start_year}-{end_year} WROTE NOTHING: "
            f"{totals['errors']} of {totals['games_seen']} games errored. "
            f"Re-run — the backfill is idempotent and skips what is loaded."
        )
    elif totals["errors"]:
        logger.warning(
            f"PBP backfill {start_year}-{end_year}: {totals['errors']} game(s) "
            f"errored and were skipped; re-run to pick them up."
        )
    logger.success(
        f"PBP backfill {start_year}-{end_year} complete: "
        f"{totals['games_loaded']}/{totals['games_seen']} games, "
        f"{totals['plays_written']} plays"
    )
    return totals


# ── Single-game CLI path ──────────────────────────────────────────────────────

def ingest_pbp_for_game_id(game_id: str, force: bool = False) -> int:
    """
    Resolve game_id → mlbam_game_pk via statsapi.schedule, then ingest.
    Used by `--game-id` CLI for spot-checks.
    """
    parts = game_id.split("_")
    if len(parts) < 4 or parts[0] != "MLB":
        raise ValueError(f"Unrecognized game_id: {game_id}")
    target_date = parts[1]
    away = parts[2]
    home = parts[3]
    season = int(target_date[:4])

    games = statsapi.schedule(date=target_date, sportId=1)
    mlbam_pk = None
    for g in games:
        away_ab = STATSAPI_TEAM_IDS.get(g["away_id"])
        home_ab = STATSAPI_TEAM_IDS.get(g["home_id"])
        if away_ab == away and home_ab == home:
            mlbam_pk = g["game_id"]
            break
    if mlbam_pk is None:
        raise ValueError(f"Could not resolve {game_id} → mlbam_game_pk")

    conn = get_connection()
    try:
        return ingest_pbp_for_game(game_id, mlbam_pk, season, conn, force=force)
    finally:
        conn.close()


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill MLB play-by-play data into `plays`")
    parser.add_argument("--backfill", nargs=2, type=int, metavar=("START_YEAR", "END_YEAR"),
                        help="Backfill seasons START_YEAR..END_YEAR (inclusive)")
    parser.add_argument("--game-id", default=None,
                        help="Ingest PBP for one game (e.g. MLB_2024-04-05_NYY_BOS)")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest games even if already loaded")
    args = parser.parse_args()

    if args.game_id:
        n = ingest_pbp_for_game_id(args.game_id, force=args.force)
        logger.success(f"{args.game_id}: {n} plays written")
    elif args.backfill:
        start, end = args.backfill
        backfill_pbp(start, end, force=args.force)
    else:
        parser.print_help()
