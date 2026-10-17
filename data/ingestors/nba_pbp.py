"""Free NBA play-by-play into Supabase, and the lineup segments derived from it.

WHY. The NBA game-market search (docs/nba_models_2026.md section 6, family F1
and F4) needs player ratings that owe nothing to the betting market: adjusted
plus-minus from on-court segments, a garbage-time flag, and shot-level
three-point luck. None of that can be built from box scores.

SOURCE (free; nothing here touches a paid API). sportsdataverse's GitHub
releases of ESPN's feed, one parquet per season:
    espn_nba_pbp/play_by_play_<season>.parquet          every play
    espn_nba_player_boxscores/player_box_<season>.parquet  starters, minutes
The file year is OUR season label (the ending year): play_by_play_2019 runs
2018-10-16 -> 2019-06-13 with season=2019 on every row (measured 2026-10-16).
ESPN season_type 2 = regular season, 3 = postseason, 5 = play-in; preseason
and the All-Star games (teams GIA, USA, STARS, STRIPES) are dropped.

WHAT IT WRITES (every table created here, locked down beside its CREATE).
  nba_pbp_games      one row per ESPN game loaded: our game_id, how it was
                     matched to `games`, ESPN's final score, the derivation's
                     diagnostics. A game's row is written in the SAME commit as
                     its plays and segments, so it is the resume ledger.
  nba_pbp            one row per play, slimmed (see PBP_COLS).
  nba_pbp_box        ESPN's box score per game: who played, for which side,
                     who started, minutes. The derivation's other input, kept
                     so segments can be rebuilt from Supabase alone.
  nba_player_id_map  ESPN athlete id -> the NBA.com person id every other NBA
                     table uses, matched by name within team and game.
  nba_stints         one row per segment with the same ten players on the
                     floor (data/ingestors/nba_stints.py says how).

GAME MATCHING. ESPN's ET date and teams build our id (NBA_<date>_<away>_<home>,
the format of `games`, nba_player_game_log and nba_player_game_adv). Postseason
and play-in games get the same-format id but are not in `games`, which holds
the regular season only; `in_games` says which. A regular-season game whose
built id is not in `games` is tried with home and away swapped, then one day
either side, against ids no exact match has claimed; `match_method` records
which. When the swap is what matched, the sides are flipped so 'H' is always
the home team of our `games` row.

    python -m data.ingestors.nba_pbp --seasons 2019-2026 --build-map
    python -m data.ingestors.nba_pbp --seasons 2019-2026 --load
    python -m data.ingestors.nba_pbp --seasons 2019 --load --rederive-stints
    python -m data.ingestors.nba_pbp --seasons 2019 --dry-run   (no writes)
    python -m data.ingestors.nba_pbp --seasons 2019-2026 --fill-gaps

GAPS. The release lacks a few regular-season games (six late-February 2019-20
games, for one). --fill-gaps takes every `games` row no stored ESPN game
matched from ESPN's own free scoreboard and summary endpoints, which the
release is a flattening of, and writes it through the same path with
source 'espn_summary_api'.
"""
from __future__ import annotations

import argparse
import math
import tempfile
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from loguru import logger

from data.ingestors.nba_espn_box import nba_team
from data.ingestors.nba_stats_ingestor import _build_game_id
from data.ingestors import nba_stints as st
from data.name_match import normalize_player_name

SOURCE = "sportsdataverse_espn_pbp"
DERIVATION = "stints-v1"
RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"
PBP_URL = RELEASE + "/espn_nba_pbp/play_by_play_{season}.parquet"
BOX_URL = RELEASE + "/espn_nba_player_boxscores/player_box_{season}.parquet"
DOWNLOAD_ROOT = Path(tempfile.gettempdir()) / "nba_free_data" / "sportsdataverse_espn"
SEASON_TYPES = (2, 3, 5)
COORD_SENTINEL_BELOW = -1000.0   # ESPN writes -214748340 where there is no location
GAMES_PER_COMMIT = 6             # ~500 plays a game -> ~3,000 rows a commit

PBP_SOURCE_COLS = (
    "game_id", "sequence_number", "type_id", "type_text", "text", "away_score",
    "home_score", "period_number", "clock_display_value", "clock_minutes",
    "clock_seconds", "scoring_play", "score_value", "team_id", "athlete_id_1",
    "athlete_id_2", "athlete_id_3", "wallclock", "shooting_play",
    "coordinate_x_raw", "coordinate_y_raw", "season", "season_type",
    "home_team_id", "away_team_id", "home_team_abbrev", "away_team_abbrev",
    "home_team_name", "away_team_name", "game_date", "points_attempted",
)
BOX_SOURCE_COLS = (
    "game_id", "season", "season_type", "game_date", "athlete_id",
    "athlete_display_name", "team_id", "team_abbreviation", "team_display_name",
    "home_away", "minutes", "starter", "did_not_play", "points", "team_score",
    "opponent_team_score",
)

PBP_COLS = (
    "espn_game_id", "play_no", "sequence_number", "game_id", "season",
    "season_type", "period", "clock_s", "game_s", "wallclock", "type_id",
    "type_text", "scoring_play", "shooting_play", "shot_value", "points",
    "espn_score_value", "home_score", "away_score", "espn_home_score",
    "espn_away_score", "team_side", "espn_team_id", "athlete_id_1",
    "athlete_id_2", "athlete_id_3", "coord_x", "coord_y", "text",
)
BOX_COLS = ("espn_game_id", "espn_id", "game_id", "season", "side", "team",
            "name", "starter", "minutes", "did_not_play")
GAME_COLS = (
    "espn_game_id", "game_id", "season", "season_type", "game_date", "home_team",
    "away_team", "in_games", "match_method", "sides_swapped", "n_plays",
    "n_periods", "espn_home_final", "espn_away_final", "pbp_home_pts",
    "pbp_away_pts", "n_stints", "diagnostics", "source", "derivation",
)
STINT_COLS = (
    "espn_game_id", "stint_no", "game_id", "season", "season_type", "period",
    "start_s", "end_s", "duration_s", "home_team", "away_team",
    "home_espn_ids", "away_espn_ids", "home_player_ids", "away_player_ids",
    "n_home", "n_away", "home_pts", "away_pts", "home_poss", "away_poss",
    "home_fga", "home_fg3a", "home_fg3m", "home_fta", "home_ftm", "home_oreb",
    "home_tov", "away_fga", "away_fg3a", "away_fg3m", "away_fta", "away_ftm",
    "away_oreb", "away_tov", "home_score_start", "away_score_start",
    "garbage_time", "derivation",
)
MAP_COLS = ("espn_id", "player_id", "name", "our_name", "method", "games_seen",
            "games_matched", "games_conflict")

GAMES_DDL = """
CREATE TABLE IF NOT EXISTS nba_pbp_games (
    espn_game_id     BIGINT PRIMARY KEY,
    game_id          TEXT NOT NULL,
    season           INTEGER NOT NULL,
    season_type      SMALLINT NOT NULL,
    game_date        TEXT NOT NULL,
    home_team        TEXT NOT NULL,
    away_team        TEXT NOT NULL,
    in_games         BOOLEAN NOT NULL,
    match_method     TEXT NOT NULL,
    sides_swapped    BOOLEAN NOT NULL DEFAULT FALSE,
    n_plays          INTEGER NOT NULL,
    n_periods        SMALLINT NOT NULL,
    espn_home_final  INTEGER,
    espn_away_final  INTEGER,
    pbp_home_pts     INTEGER,
    pbp_away_pts     INTEGER,
    n_stints         INTEGER,
    diagnostics      JSONB,
    source           TEXT NOT NULL,
    derivation       TEXT,
    loaded_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
PBP_DDL = """
CREATE TABLE IF NOT EXISTS nba_pbp (
    espn_game_id     BIGINT NOT NULL,
    play_no          INTEGER NOT NULL,
    sequence_number  INTEGER,
    game_id          TEXT NOT NULL,
    season           INTEGER NOT NULL,
    season_type      SMALLINT NOT NULL,
    period           SMALLINT NOT NULL,
    clock_s          REAL NOT NULL,
    game_s           REAL NOT NULL,
    wallclock        TIMESTAMPTZ,
    type_id          INTEGER,
    type_text        TEXT,
    scoring_play     BOOLEAN,
    shooting_play    BOOLEAN,
    shot_value       SMALLINT,
    points           SMALLINT NOT NULL,
    espn_score_value SMALLINT,
    home_score       INTEGER NOT NULL,
    away_score       INTEGER NOT NULL,
    espn_home_score  INTEGER,
    espn_away_score  INTEGER,
    team_side        TEXT,
    espn_team_id     INTEGER,
    athlete_id_1     BIGINT,
    athlete_id_2     BIGINT,
    athlete_id_3     BIGINT,
    coord_x          REAL,
    coord_y          REAL,
    text             TEXT,
    PRIMARY KEY (espn_game_id, play_no)
)
"""
BOX_DDL = """
CREATE TABLE IF NOT EXISTS nba_pbp_box (
    espn_game_id  BIGINT NOT NULL,
    espn_id       BIGINT NOT NULL,
    game_id       TEXT NOT NULL,
    season        INTEGER NOT NULL,
    side          TEXT NOT NULL,
    team          TEXT NOT NULL,
    name          TEXT,
    starter       BOOLEAN NOT NULL,
    minutes       REAL,
    did_not_play  BOOLEAN,
    PRIMARY KEY (espn_game_id, espn_id)
)
"""
MAP_DDL = """
CREATE TABLE IF NOT EXISTS nba_player_id_map (
    espn_id         BIGINT PRIMARY KEY,
    player_id       TEXT,
    name            TEXT NOT NULL,
    our_name        TEXT,
    method          TEXT NOT NULL,
    games_seen      INTEGER NOT NULL,
    games_matched   INTEGER NOT NULL,
    games_conflict  INTEGER NOT NULL,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
"""
STINTS_DDL = """
CREATE TABLE IF NOT EXISTS nba_stints (
    espn_game_id      BIGINT NOT NULL,
    stint_no          INTEGER NOT NULL,
    game_id           TEXT NOT NULL,
    season            INTEGER NOT NULL,
    season_type       SMALLINT NOT NULL,
    period            SMALLINT NOT NULL,
    start_s           REAL NOT NULL,
    end_s             REAL NOT NULL,
    duration_s        REAL NOT NULL,
    home_team         TEXT NOT NULL,
    away_team         TEXT NOT NULL,
    home_espn_ids     BIGINT[] NOT NULL,
    away_espn_ids     BIGINT[] NOT NULL,
    home_player_ids   TEXT[] NOT NULL,
    away_player_ids   TEXT[] NOT NULL,
    n_home            SMALLINT NOT NULL,
    n_away            SMALLINT NOT NULL,
    home_pts          SMALLINT NOT NULL,
    away_pts          SMALLINT NOT NULL,
    home_poss         SMALLINT NOT NULL,
    away_poss         SMALLINT NOT NULL,
    home_fga          SMALLINT NOT NULL,
    home_fg3a         SMALLINT NOT NULL,
    home_fg3m         SMALLINT NOT NULL,
    home_fta          SMALLINT NOT NULL,
    home_ftm          SMALLINT NOT NULL,
    home_oreb         SMALLINT NOT NULL,
    home_tov          SMALLINT NOT NULL,
    away_fga          SMALLINT NOT NULL,
    away_fg3a         SMALLINT NOT NULL,
    away_fg3m         SMALLINT NOT NULL,
    away_fta          SMALLINT NOT NULL,
    away_ftm          SMALLINT NOT NULL,
    away_oreb         SMALLINT NOT NULL,
    away_tov          SMALLINT NOT NULL,
    home_score_start  INTEGER NOT NULL,
    away_score_start  INTEGER NOT NULL,
    garbage_time      BOOLEAN NOT NULL,
    derivation        TEXT NOT NULL,
    PRIMARY KEY (espn_game_id, stint_no)
)
"""
# nba_pbp carries only its primary key: ~5M rows, read per game through
# espn_game_id (nba_pbp_games maps our game_id to it), so a game_id index would
# cost a few hundred MB for a lookup the ledger already answers.
INDEXES = {
    "nba_pbp_games_game_id_idx": ("CREATE INDEX IF NOT EXISTS nba_pbp_games_game_id_idx "
                                  "ON nba_pbp_games (game_id)"),
    "nba_pbp_games_season_idx": ("CREATE INDEX IF NOT EXISTS nba_pbp_games_season_idx "
                                 "ON nba_pbp_games (season)"),
    "nba_pbp_box_game_id_idx": ("CREATE INDEX IF NOT EXISTS nba_pbp_box_game_id_idx "
                                "ON nba_pbp_box (game_id)"),
    "nba_pbp_box_season_idx": ("CREATE INDEX IF NOT EXISTS nba_pbp_box_season_idx "
                               "ON nba_pbp_box (season)"),
    "nba_player_id_map_player_idx": ("CREATE INDEX IF NOT EXISTS nba_player_id_map_player_idx "
                                     "ON nba_player_id_map (player_id)"),
    "nba_stints_game_id_idx": ("CREATE INDEX IF NOT EXISTS nba_stints_game_id_idx "
                               "ON nba_stints (game_id)"),
    "nba_stints_season_idx": ("CREATE INDEX IF NOT EXISTS nba_stints_season_idx "
                              "ON nba_stints (season)"),
}


# ── small converters ────────────────────────────────────────────────────────

def _missing(v) -> bool:
    if v is None:
        return True
    try:
        return isinstance(v, float) and math.isnan(v)
    except TypeError:
        return False


def _int(v):
    if _missing(v):
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _float(v):
    if _missing(v):
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _bool(v) -> bool:
    if _missing(v):
        return False
    if isinstance(v, str):
        return v.strip().lower() in ("true", "1", "t", "yes")
    return bool(v)


def _txt(v):
    if _missing(v):
        return None
    s = str(v)
    return s if s.strip() else None


def _date10(v) -> str | None:
    s = _txt(v)
    return s[:10] if s else None


def parse_seasons(spec: str) -> list[int]:
    """'2019-2026' or '2019,2021' -> [2019, ...]."""
    out: list[int] = []
    for part in str(spec).split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            out.extend(range(int(a), int(b) + 1))
        elif part:
            out.append(int(part))
    return sorted(set(out))


# ── game matching ───────────────────────────────────────────────────────────

def match_games(espn_games: list[dict], our_ids: set[str]) -> dict:
    """{espn_game_id: (game_id, in_games, method, swapped)}.

    `espn_games` carry espn_game_id, game_date (ET), home, away, season_type.
    Exact ids are claimed first, so a fallback can never take a game another
    ESPN game matches exactly (2020-21 scheduled the same two teams on
    consecutive days)."""
    out: dict = {}
    claimed: set[str] = set()
    pending = []
    for g in espn_games:
        gid = _build_game_id(g["game_date"], g["away"], g["home"])
        if gid in our_ids and gid not in claimed:
            out[g["espn_game_id"]] = (gid, True, "exact", False)
            claimed.add(gid)
        else:
            pending.append(g)
    for g in pending:
        gid = _build_game_id(g["game_date"], g["away"], g["home"])
        if g["season_type"] != 2:
            out[g["espn_game_id"]] = (gid, gid in our_ids, "not_regular_season", False)
            continue
        d0 = date.fromisoformat(g["game_date"])
        tries = [(d0, True, "swapped")]
        for dd in (-1, 1):
            d = (d0 + timedelta(days=dd)).isoformat()
            tries += [(date.fromisoformat(d), False, "date_shift"),
                      (date.fromisoformat(d), True, "date_shift_swapped")]
        hit = None
        for d, swap, method in tries:
            away, home = (g["home"], g["away"]) if swap else (g["away"], g["home"])
            cand = _build_game_id(d.isoformat(), away, home)
            if cand in our_ids and cand not in claimed:
                hit = (cand, True, method, swap)
                claimed.add(cand)
                break
        out[g["espn_game_id"]] = hit or (gid, False, "unmatched", False)
    return out


# ── plays ───────────────────────────────────────────────────────────────────

def _side(team_id, home_tid, away_tid, swapped: bool):
    if team_id is None:
        return None
    if team_id == home_tid:
        s = st.HOME
    elif team_id == away_tid:
        s = st.AWAY
    else:
        return None
    if swapped:
        s = st.AWAY if s == st.HOME else st.HOME
    return s


def slim_plays(records: list[dict], *, espn_game_id: int, game_id: str, season: int,
               season_type: int, swapped: bool = False) -> list[dict]:
    """One game's source rows -> nba_pbp rows, in play order.

    Order, points and the running score follow nba_stints' ORDER and POINTS
    rules. ESPN's own score columns are kept beside ours (espn_home_score...),
    as ESPN printed them; ours are the running totals of `points`.
    """
    if not records:
        return []
    home_tid = _int(records[0].get("home_team_id"))
    away_tid = _int(records[0].get("away_team_id"))
    rows = []
    for r in records:
        clock = st.parse_clock(r.get("clock_display_value"))
        if clock is None:
            m, s = _float(r.get("clock_minutes")), _float(r.get("clock_seconds"))
            clock = (m or 0.0) * 60 + (s or 0.0)
        period = _int(r.get("period_number")) or 0
        team_id = _int(r.get("team_id"))
        eh, ea = _int(r.get("home_score")), _int(r.get("away_score"))
        if swapped:
            eh, ea = ea, eh
        x, y = _float(r.get("coordinate_x_raw")), _float(r.get("coordinate_y_raw"))
        has_xy = (x is not None and y is not None and x > COORD_SENTINEL_BELOW
                  and y > COORD_SENTINEL_BELOW)
        rows.append({
            "espn_game_id": espn_game_id,
            "sequence_number": _int(r.get("sequence_number")),
            "game_id": game_id,
            "season": season,
            "season_type": season_type,
            "period": period,
            "clock_s": round(float(clock), 1),
            "wallclock": _txt(r.get("wallclock")),
            "type_id": _int(r.get("type_id")),
            "type_text": _txt(r.get("type_text")),
            "scoring_play": _bool(r.get("scoring_play")),
            "shooting_play": _bool(r.get("shooting_play")),
            "espn_score_value": _int(r.get("score_value")),
            "espn_points_attempted": _int(r.get("points_attempted")),
            "espn_home_score": eh,
            "espn_away_score": ea,
            "team_side": _side(team_id, home_tid, away_tid, swapped),
            "espn_team_id": team_id,
            "athlete_id_1": _int(r.get("athlete_id_1")),
            "athlete_id_2": _int(r.get("athlete_id_2")),
            "athlete_id_3": _int(r.get("athlete_id_3")),
            "coord_x": x if has_xy else None,
            "coord_y": y if has_xy else None,
            "text": _txt(r.get("text")),
            # the derivation reads `clock`; nba_pbp stores it as clock_s
            "clock": round(float(clock), 1),
        })
    rows = st.order_plays(rows)
    home = away = 0
    for n, p in enumerate(rows, start=1):
        p["play_no"] = n
        p["shot_value"] = st.shot_value(p)
        p["points"] = st.play_points(p)
        if p["points"] and p["team_side"] == st.HOME:
            home += p["points"]
        elif p["points"] and p["team_side"] == st.AWAY:
            away += p["points"]
        p["home_score"], p["away_score"] = home, away
        p["game_s"] = round(st.elapsed(p["period"], p["clock"]), 1)
    return rows


def box_context(box_records: list[dict], swapped: bool = False):
    """(roster {espn id: side}, starters {side: ids}, seconds {id: s},
    names {id: name}) from one game's ESPN box rows."""
    roster: dict[int, str] = {}
    starters = {st.HOME: set(), st.AWAY: set()}
    seconds: dict[int, float] = {}
    names: dict[int, str] = {}
    for r in box_records:
        aid = _int(r.get("athlete_id"))
        ha = (_txt(r.get("home_away")) or "").lower()
        if aid is None or ha not in ("home", "away"):
            continue
        side = st.HOME if ha == "home" else st.AWAY
        if swapped:
            side = st.AWAY if side == st.HOME else st.HOME
        roster[aid] = side
        names[aid] = _txt(r.get("athlete_display_name")) or ""
        if _bool(r.get("starter")):
            starters[side].add(aid)
        mins = _float(r.get("minutes"))
        if mins and mins > 0:
            seconds[aid] = mins * 60.0
    return roster, starters, seconds, names


def roster_from_plays(plays: list[dict], roster: dict[int, str]) -> int:
    """Add to `roster` every athlete the plays credit to a side that the box
    does not list (the whole roster, for the one 2018-19 game with no box).
    The side is the one most of his own plays (athlete_id_1, and both players
    of a substitution) are credited to. Returns how many were added."""
    votes: dict[int, Counter] = defaultdict(Counter)
    for p in plays:
        side = p.get("team_side")
        if side not in (st.HOME, st.AWAY):
            continue
        ids = [p.get("athlete_id_1")]
        if st.is_sub(p):
            ids.append(p.get("athlete_id_2"))
        elif not st.presence_eligible(p):
            continue
        for a in ids:
            if a is not None and a not in roster:
                votes[a][side] += 1
    for a, v in votes.items():
        roster[a] = v.most_common(1)[0][0]
    return len(votes)


def drop_duplicate_box_ids(roster: dict, starters: dict, seconds: dict, names: dict,
                           play_ids: set[int]) -> set[int]:
    """ESPN's box sometimes lists one player twice under two athlete ids
    (Isaiah Canaan as 4412182 and 2490589 in ESPN game 401070216; 18 of 2,626
    team-games in 2018-19 show six starters). Within a side, an id that shares
    its normalized name with another and never appears in the game's plays is
    dropped, when the other one does appear. Returns the ids dropped."""
    by = defaultdict(list)
    for a, side in roster.items():
        by[(side, normalize_player_name(names.get(a)))].append(a)
    drop: set[int] = set()
    for (_side, nm), ids in by.items():
        if nm and len(ids) > 1 and any(a in play_ids for a in ids):
            drop |= {a for a in ids if a not in play_ids}
    for a in drop:
        roster.pop(a, None)
        seconds.pop(a, None)
        names.pop(a, None)
        for s in starters.values():
            s.discard(a)
    return drop


# ── player id matching ──────────────────────────────────────────────────────

METHOD_RANK = {"name_in_game": 0, "initial_last_in_game": 1, "last_in_game": 2,
               "elimination_in_game": 3, "name_in_team_season": 4}


def _last(norm: str) -> str:
    return norm.split()[-1] if norm else ""


def match_names(espn: dict[int, str], ours: dict[str, str],
                espn_played: set[int] | None = None,
                ours_played: set[str] | None = None) -> dict[int, tuple[str, str]]:
    """{espn id: (our player id, method)} for one team in one game.

    Tried in order, each only among players still unmatched, and each refusing
    an ambiguous answer (two candidates is no match): the normalized full name
    (data/name_match.py); the same last name and first initial; the same last
    name; and finally, when exactly one ESPN player who played and one of ours
    who played are left, those two."""
    out: dict[int, tuple[str, str]] = {}
    e_left = {k: normalize_player_name(v) for k, v in espn.items()}
    o_left = {k: normalize_player_name(v) for k, v in ours.items()}

    def take(keyfn, method):
        e_keys = defaultdict(list)
        for k, v in e_left.items():
            if v:
                e_keys[keyfn(v)].append(k)
        o_keys = defaultdict(list)
        for k, v in o_left.items():
            if v:
                o_keys[keyfn(v)].append(k)
        for key, es in e_keys.items():
            os_ = o_keys.get(key, [])
            if key and len(es) == 1 and len(os_) == 1:
                out[es[0]] = (os_[0], method)
        for e, (o, _m) in out.items():
            e_left.pop(e, None)
            o_left.pop(o, None)

    take(lambda v: v, "name_in_game")
    take(lambda v: (v.split()[0][:1], _last(v)), "initial_last_in_game")
    take(_last, "last_in_game")
    e_p = [k for k in e_left if espn_played is None or k in espn_played]
    o_p = [k for k in o_left if ours_played is None or k in ours_played]
    if len(e_p) == 1 and len(o_p) == 1:
        out[e_p[0]] = (o_p[0], "elimination_in_game")
    return out


def season_fallback(votes: dict, names: dict[int, str], team_seasons: dict,
                    by_team_season: dict) -> int:
    """For an ESPN id no game matched, the one player of ours with the same
    normalized name on any team-season he appeared for. ESPN carries some
    players under a second id that its box lists beside the first (Isaiah
    Canaan as 4412182 and 2490589), so the in-game match sees two of him and
    refuses both. Adds votes in place; returns how many ids it resolved."""
    n = 0
    for a, ts in team_seasons.items():
        if votes.get(a):
            continue
        key = normalize_player_name(names.get(a))
        if not key:
            continue
        pids = set()
        for t in ts:
            pids |= by_team_season.get(t, {}).get(key, set())
        if len(pids) == 1:
            votes[a][pids.pop()].append("name_in_team_season")
            n += 1
    return n


def resolve_map(votes: dict, names: dict[int, str], our_names: dict[str, str],
                seen: Counter) -> list[dict]:
    """One nba_player_id_map row per ESPN id from its per-game votes
    ({espn id: {player id: [methods]}}): the player id with the most games,
    its strongest method, and how many games voted for something else."""
    rows = []
    for eid in sorted(set(seen) | set(votes)):
        v = votes.get(eid) or {}
        if v:
            pid, methods = max(v.items(), key=lambda kv: (len(kv[1]), -min(
                METHOD_RANK[m] for m in kv[1]), kv[0]))
            best = min(methods, key=lambda m: METHOD_RANK[m])
            conflict = sum(len(m) for p, m in v.items() if p != pid)
            rows.append({"espn_id": eid, "player_id": pid, "name": names.get(eid) or "",
                         "our_name": our_names.get(pid), "method": best,
                         "games_seen": seen.get(eid, 0), "games_matched": len(methods),
                         "games_conflict": conflict})
        else:
            rows.append({"espn_id": eid, "player_id": None, "name": names.get(eid) or "",
                         "our_name": None, "method": "unmatched",
                         "games_seen": seen.get(eid, 0), "games_matched": 0,
                         "games_conflict": 0})
    return rows


# ── stints -> rows ──────────────────────────────────────────────────────────

def our_ids(espn_ids, id_map: dict[int, str]) -> list[str]:
    """Our player ids for a lineup, sorted; 'espn:<id>' where the map has none
    (the convention nba_results_ingestor uses for a player NBA.com lacks)."""
    return sorted(id_map.get(int(e)) or f"espn:{int(e)}" for e in espn_ids)


def stint_rows(stints: list[dict], *, espn_game_id: int, game_id: str, season: int,
               season_type: int, home: str, away: str, id_map: dict[int, str]) -> list[dict]:
    out = []
    for s in stints:
        r = {k: s[k] for k in s if k not in ("home_ids", "away_ids")}
        r.update({
            "espn_game_id": espn_game_id, "game_id": game_id, "season": season,
            "season_type": season_type, "home_team": home, "away_team": away,
            "home_espn_ids": list(s["home_ids"]), "away_espn_ids": list(s["away_ids"]),
            "home_player_ids": our_ids(s["home_ids"], id_map),
            "away_player_ids": our_ids(s["away_ids"], id_map),
            "derivation": DERIVATION,
        })
        out.append(r)
    return out


# ── the season frames ───────────────────────────────────────────────────────

def download(url: str, dest_dir: Path) -> Path:
    """Fetch `url` into `dest_dir` (created empty for it); reuse a complete
    earlier download. The file is untrusted data: it is only ever read by
    pandas, from the repo root."""
    import requests

    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / url.rsplit("/", 1)[-1]
    if path.exists() and path.stat().st_size > 0:
        return path
    part = path.with_suffix(path.suffix + ".part")
    for attempt in range(4):
        try:
            with requests.get(url, timeout=180, stream=True) as resp:
                resp.raise_for_status()
                with open(part, "wb") as fh:
                    for chunk in resp.iter_content(1 << 20):
                        fh.write(chunk)
            part.replace(path)
            return path
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"{path.name}: {type(exc).__name__}: {exc}; retry {attempt + 1}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"could not download {url}")


def season_frames(season: int):
    """(pbp records grouped by ESPN game id, box records grouped likewise),
    regular season, postseason and play-in only."""
    import pandas as pd
    import pyarrow.parquet as pq

    pbp_path = download(PBP_URL.format(season=season), DOWNLOAD_ROOT / f"pbp_{season}")
    box_path = download(BOX_URL.format(season=season), DOWNLOAD_ROOT / f"box_{season}")
    have = set(pq.read_schema(pbp_path).names)
    pbp = pd.read_parquet(pbp_path, columns=[c for c in PBP_SOURCE_COLS if c in have])
    have = set(pq.read_schema(box_path).names)
    box = pd.read_parquet(box_path, columns=[c for c in BOX_SOURCE_COLS if c in have])
    pbp = pbp[pbp["season_type"].isin(SEASON_TYPES)]
    box = box[box["season_type"].isin(SEASON_TYPES)]
    pbp = pbp.astype(object).where(pbp.notna(), None)
    box = box.astype(object).where(box.notna(), None)
    games = defaultdict(list)
    for r in pbp.to_dict("records"):
        games[int(r["game_id"])].append(r)
    boxes = defaultdict(list)
    for r in box.to_dict("records"):
        boxes[int(r["game_id"])].append(r)
    return games, boxes


def espn_game_meta(espn_game_id: int, recs: list[dict]) -> dict | None:
    """Teams, ET date and season type of one ESPN game, or None when either
    side is not an NBA team (All-Star and exhibition games)."""
    r = recs[0]
    home = nba_team(_txt(r.get("home_team_abbrev")), _txt(r.get("home_team_name")))
    away = nba_team(_txt(r.get("away_team_abbrev")), _txt(r.get("away_team_name")))
    if not home or not away:
        return None
    return {"espn_game_id": espn_game_id, "home": home, "away": away,
            "game_date": _date10(r.get("game_date")),
            "season_type": _int(r.get("season_type")), "season": _int(r.get("season"))}


def box_finals(box_records: list[dict], swapped: bool = False):
    """ESPN's final score (home, away) from the box rows' team_score."""
    h = a = None
    for r in box_records:
        ha = (_txt(r.get("home_away")) or "").lower()
        if ha == "home" and h is None:
            h = _int(r.get("team_score"))
        elif ha == "away" and a is None:
            a = _int(r.get("team_score"))
    return (a, h) if swapped else (h, a)


def build_game(espn_game_id: int, recs: list[dict], box_recs: list[dict], meta: dict,
               match: tuple, id_map: dict[int, str], seconds_override: dict | None = None):
    """Everything one game writes: (game row, pbp rows, box rows, stint rows)."""
    game_id, in_games, method, swapped = match
    season, stype = meta["season"], meta["season_type"]
    home, away = (meta["away"], meta["home"]) if swapped else (meta["home"], meta["away"])
    plays = slim_plays(recs, espn_game_id=espn_game_id, game_id=game_id, season=season,
                       season_type=stype, swapped=swapped)
    roster, starters, seconds, names = box_context(box_recs, swapped)
    play_ids = {a for p in plays for a in (p["athlete_id_1"], p["athlete_id_2"],
                                           p["athlete_id_3"]) if a is not None}
    dropped = drop_duplicate_box_ids(roster, starters, seconds, names, play_ids)
    from_plays = roster_from_plays(plays, roster)
    if seconds_override:
        seconds = {**seconds, **seconds_override}
    stints, diag = st.derive_stints(plays, roster, starters, seconds, ordered=True)
    s_rows = stint_rows(stints, espn_game_id=espn_game_id, game_id=game_id, season=season,
                        season_type=stype, home=home, away=away, id_map=id_map)
    eh, ea = box_finals(box_recs, swapped)
    g = {
        "espn_game_id": espn_game_id, "game_id": game_id, "season": season,
        "season_type": stype, "game_date": meta["game_date"], "home_team": home,
        "away_team": away, "in_games": in_games, "match_method": method,
        "sides_swapped": swapped, "n_plays": len(plays),
        "n_periods": max((p["period"] for p in plays), default=0),
        "espn_home_final": eh, "espn_away_final": ea,
        "pbp_home_pts": plays[-1]["home_score"] if plays else 0,
        "pbp_away_pts": plays[-1]["away_score"] if plays else 0,
        "n_stints": len(s_rows),
        "diagnostics": {**diag.as_dict(), "box_duplicate_ids_dropped": len(dropped),
                        "roster_from_plays": from_plays, "box_rows": len(box_recs)},
        "source": SOURCE,
        "derivation": DERIVATION,
    }
    b_rows = []
    for r in box_recs:
        aid = _int(r.get("athlete_id"))
        if aid is None or aid not in roster:
            continue
        b_rows.append({
            "espn_game_id": espn_game_id, "espn_id": aid, "game_id": game_id,
            "season": season, "side": roster[aid],
            "team": home if roster[aid] == st.HOME else away,
            "name": names.get(aid), "starter": _bool(r.get("starter")),
            "minutes": _float(r.get("minutes")), "did_not_play": _bool(r.get("did_not_play")),
        })
    return g, plays, b_rows, s_rows


# ── database ────────────────────────────────────────────────────────────────

def ensure_tables(conn) -> None:
    """Each table created once and locked down beside its CREATE; nothing
    after that (data/ddl_guard.py: a no-op CREATE still reloads PostgREST)."""
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current

    def idx(table):
        return tuple(k for k, v in INDEXES.items() if f" ON {table} " in v)

    def make(table, ddl, cols):
        if schema_is_current(conn, table, columns=cols, indexes=idx(table), rls=True,
                             revoked_from=API_ROLES):
            return False
        conn.execute(ddl)
        for k in idx(table):
            conn.execute(INDEXES[k])
        return True

    if make("nba_pbp_games", GAMES_DDL, GAME_COLS):
        lock_down(conn, "nba_pbp_games")
    if make("nba_pbp", PBP_DDL, PBP_COLS):
        lock_down(conn, "nba_pbp")
    if make("nba_pbp_box", BOX_DDL, BOX_COLS):
        lock_down(conn, "nba_pbp_box")
    if make("nba_player_id_map", MAP_DDL, MAP_COLS):
        lock_down(conn, "nba_player_id_map")
    if make("nba_stints", STINTS_DDL, STINT_COLS):
        lock_down(conn, "nba_stints")
    conn.commit()


def _insert(conn, table: str, cols: tuple[str, ...], rows: list[dict],
            conflict: str = "DO NOTHING", casts: dict | None = None) -> None:
    if not rows:
        return
    casts = casts or {}
    vals = ", ".join(f"%({c})s{casts.get(c, '')}" for c in cols)
    conn.executemany(
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({vals}) ON CONFLICT {conflict}",
        [{c: r.get(c) for c in cols} for r in rows])


def _json_diag(g: dict) -> dict:
    import json
    return {**g, "diagnostics": json.dumps(g["diagnostics"])}


def write_games(conn, batch: list[tuple], rederive: bool) -> None:
    """One commit for a few games: ledger row, plays, box and segments."""
    games = [_json_diag(g) for g, _p, _b, _s in batch]
    ids = [g["espn_game_id"] for g in games]
    if rederive:
        conn.execute("DELETE FROM nba_stints WHERE espn_game_id = ANY(%s)", (ids,))
        conn.execute("DELETE FROM nba_pbp_games WHERE espn_game_id = ANY(%s)", (ids,))
    _insert(conn, "nba_pbp_games", GAME_COLS, games, casts={"diagnostics": "::jsonb"})
    if not rederive:
        _insert(conn, "nba_pbp", PBP_COLS, [p for _g, ps, _b, _s in batch for p in ps])
        _insert(conn, "nba_pbp_box", BOX_COLS, [b for _g, _p, bs, _s in batch for b in bs])
    _insert(conn, "nba_stints", STINT_COLS, [s for _g, _p, _b, ss in batch for s in ss])
    conn.commit()


def active_queries(conn) -> int:
    return conn.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'").fetchone()[0]


def _season_games(conn, season: int) -> dict[str, tuple]:
    rows = conn.execute(
        "SELECT game_id, home_score, away_score FROM games WHERE sport = 'NBA' AND season = %s",
        (season,)).fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def _season_adv(conn, season: int):
    return conn.execute(
        "SELECT game_id, team, player_id, player_name, played, seconds_played "
        "FROM nba_player_game_adv WHERE season = %s", (season,)).fetchall()


def _load_map(conn) -> dict[int, str]:
    if conn.execute("SELECT to_regclass('public.nba_player_id_map')").fetchone()[0] is None:
        return {}
    return {int(r[0]): r[1] for r in conn.execute(
        "SELECT espn_id, player_id FROM nba_player_id_map WHERE player_id IS NOT NULL").fetchall()}


def _matches_for(espn_meta: dict, our: set[str]) -> dict:
    return match_games(list(espn_meta.values()), our)


def build_map(conn, seasons: list[int]) -> dict:
    """nba_player_id_map from every season's box score against
    nba_player_game_adv, matched by name within team and game."""
    votes: dict = defaultdict(lambda: defaultdict(list))
    names: dict[int, str] = {}
    our_names: dict[str, str] = {}
    seen: Counter = Counter()
    stats = Counter()
    team_seasons: dict[int, set] = defaultdict(set)     # espn id -> {(season, team)}
    by_team_season: dict = defaultdict(lambda: defaultdict(set))  # (s, t) -> name -> pids
    for season in seasons:
        games, boxes = season_frames(season)
        our = _season_games(conn, season)
        adv = defaultdict(dict)
        adv_played = defaultdict(set)
        for gid, team, pid, pname, played, _secs in _season_adv(conn, season):
            adv[(gid, team)][pid] = pname
            our_names[pid] = pname
            by_team_season[(season, team)][normalize_player_name(pname)].add(pid)
            if played:
                adv_played[(gid, team)].add(pid)
        meta = {}
        for eid, recs in games.items():
            m = espn_game_meta(eid, recs)
            if m:
                meta[eid] = m
        matches = _matches_for(meta, set(our))
        for eid, m in meta.items():
            game_id, _in, _method, swapped = matches[eid]
            home, away = (m["away"], m["home"]) if swapped else (m["home"], m["away"])
            roster, _starters, secs, nm = box_context(boxes.get(eid, []), swapped)
            names.update(nm)
            for side, team in ((st.HOME, home), (st.AWAY, away)):
                espn_side = {a: nm[a] for a, s in roster.items() if s == side}
                ours = adv.get((game_id, team), {})
                if not ours:
                    stats["team_games_without_adv"] += 1
                    continue
                for a in espn_side:
                    seen[a] += 1
                    team_seasons[a].add((season, team))
                played_e = {a for a in espn_side if secs.get(a, 0) > 0}
                got = match_names(espn_side, ours, played_e, adv_played.get((game_id, team)))
                for a, (pid, method) in got.items():
                    votes[a][pid].append(method)
                    stats[method] += 1
                stats["espn_player_games"] += len(espn_side)
                stats["espn_played_games"] += len(played_e)
                stats["played_matched"] += sum(1 for a in played_e if a in got)
        logger.info(f"id map: season {season} read; running {dict(stats)}")
    stats["name_in_team_season"] = season_fallback(votes, names, team_seasons, by_team_season)
    rows = resolve_map(votes, names, our_names, seen)
    ensure_tables(conn)
    for i in range(0, len(rows), 2000):
        _insert(conn, "nba_player_id_map", MAP_COLS, rows[i:i + 2000], conflict=(
            "(espn_id) DO UPDATE SET player_id = EXCLUDED.player_id, name = EXCLUDED.name, "
            "our_name = EXCLUDED.our_name, method = EXCLUDED.method, "
            "games_seen = EXCLUDED.games_seen, games_matched = EXCLUDED.games_matched, "
            "games_conflict = EXCLUDED.games_conflict, updated_at = NOW()"))
        conn.commit()
    stats["map_rows"] = len(rows)
    stats["map_matched"] = sum(1 for r in rows if r["player_id"])
    return dict(stats)


def load_season(conn, season: int, *, rederive: bool = False, dry_run: bool = False,
                limit: int | None = None) -> dict:
    games, boxes = season_frames(season)
    our = _season_games(conn, season)
    id_map = _load_map(conn)
    rev = defaultdict(dict)   # (game_id, player_id) -> seconds (exact, NBA.com)
    for gid, _team, pid, _n, played, secs in _season_adv(conn, season):
        if played and secs:
            rev[gid][pid] = float(secs)
    meta = {}
    stats = Counter()
    for eid, recs in games.items():
        m = espn_game_meta(eid, recs)
        if m:
            meta[eid] = m
        else:
            stats["dropped_not_nba_teams"] += 1
    matches = _matches_for(meta, set(our))
    for v in matches.values():
        stats[f"match_{v[2]}"] += 1
    stored: set[int] = set()
    if not dry_run:
        ensure_tables(conn)
        stored = {r[0] for r in conn.execute(
            "SELECT espn_game_id FROM nba_pbp_games WHERE season = %s", (season,)).fetchall()}
        logger.info(f"season {season}: {len(stored)} games already stored; "
                    f"{active_queries(conn)} active queries")
    # A stored game is skipped (resume), or with --rederive-stints has its
    # segments and ledger row replaced while its plays and box stay as stored.
    todo = [(eid, eid in stored) for eid in sorted(meta) if rederive or eid not in stored]
    if limit:
        todo = todo[:limit]
    pending = {False: [], True: []}
    results = []
    for n, (eid, redo) in enumerate(todo, start=1):
        m = meta[eid]
        match = matches[eid]
        built = build_game(eid, games[eid], boxes.get(eid, []), m, match, id_map,
                           _exact_seconds(boxes.get(eid, []), rev.get(match[0], {}), id_map))
        stats["games"] += 1
        stats["plays"] += len(built[1])
        stats["stints"] += len(built[3])
        results.append(built[0])
        if dry_run:
            continue
        pending[redo].append(built)
        for kind in (False, True):
            if pending[kind] and (len(pending[kind]) >= GAMES_PER_COMMIT or n == len(todo)):
                write_games(conn, pending[kind], rederive=kind)
                pending[kind] = []
        if n % 200 == 0:
            logger.info(f"season {season}: {n}/{len(todo)} games; "
                        f"{active_queries(conn)} active queries")
    stats["season"] = season
    return {"stats": dict(stats), "games": results}


def _exact_seconds(box_recs: list[dict], adv_secs: dict[str, float],
                   id_map: dict[int, str]) -> dict[int, float]:
    """NBA.com's exact seconds played per ESPN athlete, where the id map knows
    him; the period fill then ranks by these instead of ESPN's whole minutes."""
    out = {}
    for r in box_recs:
        a = _int(r.get("athlete_id"))
        pid = id_map.get(a) if a is not None else None
        if pid and pid in adv_secs:
            out[a] = adv_secs[pid]
    return out


# ── gaps: games the release lacks, from ESPN's own summary endpoint ────────

GAP_SOURCE = "espn_summary_api"
MAX_GAPS = 100      # more than this unmatched means the season is not loaded yet


def summary_records(data: dict, espn_game_id: int, season: int, season_type: int,
                    game_date: str):
    """ESPN's summary JSON -> (play records, box records) in the release's
    column names, so the same build_game path reads both. The release is
    sportsdataverse's flattening of this same endpoint: participants[0..2] are
    athlete_id_1..3, coordinate.x/y are coordinate_x_raw/y_raw."""
    from data.ingestors.nba_espn_box import parse_nba_box

    comp = ((data.get("header") or {}).get("competitions") or [{}])[0]
    teams, scores = {}, {}
    for c in comp.get("competitors") or []:
        teams[c.get("homeAway")] = c.get("team") or {}
        scores[c.get("homeAway")] = _int(c.get("score"))
    home, away = teams.get("home") or {}, teams.get("away") or {}
    base = {
        "game_id": espn_game_id, "season": season, "season_type": season_type,
        "game_date": game_date, "home_team_id": _int(home.get("id")),
        "away_team_id": _int(away.get("id")), "home_team_abbrev": home.get("abbreviation"),
        "away_team_abbrev": away.get("abbreviation"),
        "home_team_name": home.get("displayName") or home.get("location"),
        "away_team_name": away.get("displayName") or away.get("location"),
    }
    plays = []
    for p in data.get("plays") or []:
        parts = [((x or {}).get("athlete") or {}).get("id") for x in p.get("participants") or []]
        parts += [None] * (3 - len(parts))
        coord = p.get("coordinate") or {}
        plays.append({
            **base,
            "sequence_number": p.get("sequenceNumber"),
            "type_id": (p.get("type") or {}).get("id"),
            "type_text": (p.get("type") or {}).get("text"),
            "text": p.get("text"),
            "away_score": p.get("awayScore"), "home_score": p.get("homeScore"),
            "period_number": (p.get("period") or {}).get("number"),
            "clock_display_value": (p.get("clock") or {}).get("displayValue"),
            "scoring_play": p.get("scoringPlay"), "score_value": p.get("scoreValue"),
            "team_id": (p.get("team") or {}).get("id"),
            "athlete_id_1": parts[0], "athlete_id_2": parts[1], "athlete_id_3": parts[2],
            "wallclock": p.get("wallclock"), "shooting_play": p.get("shootingPlay"),
            "coordinate_x_raw": coord.get("x"), "coordinate_y_raw": coord.get("y"),
            "points_attempted": p.get("pointsAttempted"),
        })
    home_code = nba_team(home.get("abbreviation"), home.get("displayName"))
    box = []
    for r in parse_nba_box(data):
        ha = "home" if r["team"] == home_code else "away"
        box.append({"athlete_id": r["espn_id"], "athlete_display_name": r["name"],
                    "home_away": ha, "starter": r["starter"], "minutes": r["minutes"],
                    "did_not_play": False, "team_score": scores.get(ha)})
    return plays, box


def find_event(game_id: str, game_date: str, boards: dict, get_board,
               taken: set[int] = frozenset()) -> tuple | None:
    """(scoreboard event, swapped) for one of our games, by its two teams on
    its ET date, then the day before and after: ESPN dates some games by a
    placeholder time (DET at POR, ours 2020-02-23, ESPN 2020-02-24T12:00Z).
    An ESPN event already stored is never taken, so the other game of a
    two-game series cannot stand in for this one."""
    _sport, _d, away, home = game_id.split("_", 3)
    d0 = date.fromisoformat(game_date)
    for dd in (0, -1, 1):
        d = (d0 + timedelta(days=dd)).isoformat()
        if d not in boards:
            boards[d] = get_board(d)
        for ev in boards[d]:
            if int(ev["event_id"]) in taken:
                continue
            if (ev["away"], ev["home"]) == (away, home):
                return ev, False
            if (ev["away"], ev["home"]) == (home, away):
                return ev, True
    return None


def fill_gaps(conn, season: int, *, get_json=None, dry_run: bool = False) -> dict:
    """Load every `games` row of the season that no stored ESPN game matched,
    from ESPN's free scoreboard and summary endpoints (the release is missing
    a few: six late-February 2019-20 games, for one)."""
    from data.ingestors.nba_espn_box import (ESPN_NBA_SCOREBOARD_URL, ESPN_NBA_SUMMARY_URL,
                                              parse_nba_scoreboard)
    if get_json is None:
        from data.ingestors.nba_results_ingestor import _http_get_json as get_json
    ensure_tables(conn)
    missing = conn.execute("""
        SELECT g.game_id, g.game_date FROM games g
         WHERE g.sport = 'NBA' AND g.season = %s AND g.home_score IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM nba_pbp_games p WHERE p.game_id = g.game_id)
         ORDER BY g.game_date""", (season,)).fetchall()
    stats = Counter(missing=len(missing))
    stats["season"] = season
    if not missing:
        return dict(stats)
    if len(missing) > MAX_GAPS:
        # The release has not been loaded for this season yet: filling now
        # would fetch the whole season one game at a time.
        logger.warning(f"season {season}: {len(missing)} games unmatched; run --load first")
        stats["refused"] = 1
        return dict(stats)
    id_map = _load_map(conn)
    adv = defaultdict(dict)
    for gid, _team, pid, _n, played, secs in _season_adv(conn, season):
        if played and secs:
            adv[gid][pid] = float(secs)
    boards: dict[str, list] = {}
    taken = {int(r[0]) for r in conn.execute(
        "SELECT espn_game_id FROM nba_pbp_games WHERE season = %s", (season,)).fetchall()}

    def board(d):
        return parse_nba_scoreboard(get_json(ESPN_NBA_SCOREBOARD_URL, {"dates": d.replace("-", "")}), d)

    built = []
    for game_id, gdate in missing:
        found = find_event(game_id, gdate, boards, board, taken)
        if not found:
            stats["no_espn_event"] += 1
            logger.warning(f"gap {game_id}: no ESPN event on the scoreboard")
            continue
        ev, swapped = found
        eid = int(ev["event_id"])
        data = get_json(ESPN_NBA_SUMMARY_URL, {"event": eid})
        recs, box = summary_records(data, eid, season, ev.get("season_type") or 2, ev["game_date"])
        if not recs:
            stats["no_plays"] += 1
            logger.warning(f"gap {game_id}: ESPN event {eid} has no plays")
            continue
        meta = espn_game_meta(eid, recs)
        if meta is None:
            stats["not_nba_teams"] += 1
            continue
        method = "gap_swapped" if swapped else "gap_exact"
        g = build_game(eid, recs, box, meta, (game_id, True, method, swapped), id_map,
                       _exact_seconds(box, adv.get(game_id, {}), id_map))
        g[0]["source"] = GAP_SOURCE
        stats["filled"] += 1
        built.append(g)
        time.sleep(0.3)
    if not dry_run:
        for i in range(0, len(built), GAMES_PER_COMMIT):
            write_games(conn, built[i:i + GAMES_PER_COMMIT], rederive=False)
    return dict(stats)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--seasons", required=True, help="e.g. 2019-2026")
    ap.add_argument("--build-map", action="store_true")
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--rederive-stints", action="store_true",
                    help="replace stored segments with this derivation's")
    ap.add_argument("--dry-run", action="store_true", help="derive, write nothing")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--fill-gaps", action="store_true",
                    help="games in `games` the release lacks, from ESPN's summary API")
    a = ap.parse_args()
    from data.db import get_connection

    conn = get_connection()
    try:
        seasons = parse_seasons(a.seasons)
        if a.build_map:
            print({"map": build_map(conn, seasons)})
        if a.load or (a.dry_run and not a.fill_gaps):
            for s in seasons:
                out = load_season(conn, s, rederive=a.rederive_stints, dry_run=a.dry_run,
                                  limit=a.limit)
                print(out["stats"])
        if a.fill_gaps:
            for s in seasons:
                print(fill_gaps(conn, s, dry_run=a.dry_run))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
