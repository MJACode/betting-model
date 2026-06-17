"""
nba_prop_feature_engine.py — Feature builder for NBA player prop models.

Nine models (one per market):
  Poisson counts — points / rebounds / assists / threes / pra (P+R+A) /
                   blocks / steals / turnovers
  Logistic (binary) — double_double (DD: ≥10 in ≥2 of pts/reb/ast/stl/blk)

Mirrors wnba_prop_feature_engine.py: per-player rolling form from
nba_player_game_log, season-to-date averages with prior-season fallback,
opponent team context from nba_team_stats, plus minutes (the basketball
opportunity driver). The double-double model adds a rolling DD-rate feature.

Public API (parallels the WNBA prop engine):
  • build_nba_prop_training_dataset(model_id, seasons) → DataFrame
  • build_nba_prop_scoring_rows(game_date, model_id)    → DataFrame
  • NBA_PROP_FEATURE_MAP                                 → {model_id: [cols]}

Look-ahead safety: all rolling/season stats are strictly before game_date;
opponent team stats are ASOF (as_of_date <= game_date) with prior-season fallback.
"""

import bisect
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection, DBConnection


# Stats with rolling/season/trend features and (for counts) a target column.
# 'fg3' = made threes, 'pra' = pts+reb+ast, 'dd' = double-double indicator (0/1).
_ROLL_STATS = ("points", "rebounds", "assists", "fg3", "pra",
               "blocks", "steals", "turnovers", "dd")


def _nba_season(game_date: str) -> int:
    """Internal season (ending year) for a date — Oct-Dec → year+1, else year."""
    year = int(game_date[:4])
    month = int(game_date[5:7])
    return year + 1 if month >= 10 else year


# ── Feature column definitions ─────────────────────────────────────────────────

def _stat_features(stat: str) -> list[str]:
    """Per-stat rolling/season feature names for a given box-score stat."""
    return [
        f"{stat}_last3_avg",
        f"{stat}_last5_avg",
        f"{stat}_last10_avg",
        f"season_{stat}_avg",
        f"{stat}_trend",           # last3 − season (hot/cold)
    ]

_BASE_FEATURES = [
    "min_last3_avg",        # minutes — the opportunity driver
    "min_last5_avg",
    "season_min_avg",
    "is_starter",           # 1 if started recent games (minutes proxy)
    "opp_def_rating",       # opponent defensive efficiency (ASOF)
    "opp_pace",             # opponent pace → more possessions = more counting stats
    "opp_points_allowed_pg",
    "is_home",
    "rest_days",
    "is_early_season",
]

PROP_PLAYER_POINTS_FEATURES    = _stat_features("points")    + ["fg3_last5_avg"] + _BASE_FEATURES
PROP_PLAYER_REBOUNDS_FEATURES  = _stat_features("rebounds")  + _BASE_FEATURES
PROP_PLAYER_ASSISTS_FEATURES   = _stat_features("assists")   + _BASE_FEATURES
PROP_PLAYER_THREES_FEATURES    = _stat_features("fg3")       + _BASE_FEATURES
PROP_PLAYER_BLOCKS_FEATURES    = _stat_features("blocks")    + _BASE_FEATURES
PROP_PLAYER_STEALS_FEATURES    = _stat_features("steals")    + _BASE_FEATURES
PROP_PLAYER_TURNOVERS_FEATURES = _stat_features("turnovers") + _BASE_FEATURES
PROP_PLAYER_PRA_FEATURES       = (
    _stat_features("pra")
    + ["points_last5_avg", "rebounds_last5_avg", "assists_last5_avg"]
    + _BASE_FEATURES
)
# Double-double: rolling DD rate (avg of the 0/1 indicator) + the component
# rolling averages most likely to clear 10 (pts/reb/ast).
PROP_PLAYER_DD_FEATURES = (
    _stat_features("dd")
    + ["points_last5_avg", "rebounds_last5_avg", "assists_last5_avg",
       "points_last10_avg", "rebounds_last10_avg", "assists_last10_avg"]
    + _BASE_FEATURES
)

NBA_PROP_FEATURE_MAP: dict[str, list[str]] = {
    "nba_prop_player_points":    PROP_PLAYER_POINTS_FEATURES,
    "nba_prop_player_rebounds":  PROP_PLAYER_REBOUNDS_FEATURES,
    "nba_prop_player_assists":   PROP_PLAYER_ASSISTS_FEATURES,
    "nba_prop_player_threes":    PROP_PLAYER_THREES_FEATURES,
    "nba_prop_player_pra":       PROP_PLAYER_PRA_FEATURES,
    "nba_prop_player_blocks":    PROP_PLAYER_BLOCKS_FEATURES,
    "nba_prop_player_steals":    PROP_PLAYER_STEALS_FEATURES,
    "nba_prop_player_turnovers": PROP_PLAYER_TURNOVERS_FEATURES,
    "nba_prop_player_dd":        PROP_PLAYER_DD_FEATURES,
}

# Stat key in the derived row each model targets.
_TARGET_STAT = {
    "nba_prop_player_points":    "points",
    "nba_prop_player_rebounds":  "rebounds",
    "nba_prop_player_assists":   "assists",
    "nba_prop_player_threes":    "fg3",
    "nba_prop_player_pra":       "pra",
    "nba_prop_player_blocks":    "blocks",
    "nba_prop_player_steals":    "steals",
    "nba_prop_player_turnovers": "turnovers",
    "nba_prop_player_dd":        "dd",
}


def _double_double(pts, reb, ast, stl, blk) -> int:
    """1 if the player reached double figures in ≥2 of the five categories."""
    cats = [pts, reb, ast, stl, blk]
    return int(sum(1 for c in cats if (c or 0) >= 10) >= 2)


# ── Bulk loaders ───────────────────────────────────────────────────────────────

def build_bulk_nba_prop_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """Bulk-load player game logs + team stats + games for NBA prop features."""
    all_seasons  = sorted(set(seasons))
    load_seasons = list(range(min(all_seasons) - 1, max(all_seasons) + 2))
    sp_load = ','.join(['%s'] * len(load_seasons))

    # ── Player game logs (load all so rolling windows reach into prior season) ──
    gl_cols = [
        'player_id', 'player_name', 'team', 'game_id', 'game_date', 'season',
        'minutes', 'is_starter', 'points', 'rebounds', 'assists',
        'steals', 'blocks', 'turnovers', 'fg3_made',
    ]
    gl_rows = conn.execute("""
        SELECT player_id, player_name, team, game_id, game_date, season,
               minutes, is_starter, points, rebounds, assists,
               steals, blocks, turnovers, fg3_made
        FROM nba_player_game_log
        WHERE points IS NOT NULL
        ORDER BY player_id, game_date
    """).fetchall()

    player_logs: dict = {}
    for r in gl_rows:
        d = dict(zip(gl_cols, r))
        # derived stats used as feature/target keys
        d['fg3'] = d.get('fg3_made')
        pts = d.get('points') or 0
        reb = d.get('rebounds') or 0
        ast = d.get('assists') or 0
        d['pra'] = pts + reb + ast
        d['dd']  = _double_double(d.get('points'), d.get('rebounds'),
                                  d.get('assists'), d.get('steals'), d.get('blocks'))
        pid = d['player_id']
        if pid not in player_logs:
            player_logs[pid] = ([], [])
        player_logs[pid][0].append(d['game_date'])
        player_logs[pid][1].append(d)

    # ── Team stats (opponent context, ASOF) ────────────────────────────────────
    ts_cols = ['team', 'season', 'as_of_date', 'def_rating', 'pace',
               'points_allowed_pg']
    ts_rows = conn.execute(f"""
        SELECT team, season, as_of_date, def_rating, pace, points_allowed_pg
        FROM nba_team_stats WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_stats:
            team_stats[k] = ([], [])
        team_stats[k][0].append(d['as_of_date'])
        team_stats[k][1].append(d)

    # ── Games (home/away for opponent + is_home + rest) ─────────────────────────
    g_rows = conn.execute("""
        SELECT game_id, home_team, away_team, game_date
        FROM games WHERE sport = 'NBA'
    """).fetchall()
    games: dict = {r[0]: {'home_team': r[1], 'away_team': r[2], 'game_date': r[3]}
                   for r in g_rows}

    logger.debug(
        f"NBA prop bulk loads: {len(gl_rows)} player games, "
        f"{len(ts_rows)} team-stat rows, {len(g_rows)} games"
    )
    return dict(player_logs=player_logs, team_stats=team_stats, games=games)


# ── Rolling helpers ────────────────────────────────────────────────────────────

def _rolling_avg(bulk: dict, player_id: str, game_date: str,
                 stat: str, n: int) -> float | None:
    if player_id not in bulk['player_logs']:
        return None
    dates, rows = bulk['player_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if len(prior) < n:
        return None
    window = prior[-n:]
    vals = [r.get(stat) for r in window if r.get(stat) is not None]
    return round(float(np.mean(vals)), 3) if vals else None


def _season_avg(bulk: dict, player_id: str, game_date: str,
                season: int, stat: str) -> float | None:
    if player_id not in bulk['player_logs']:
        return None
    dates, rows = bulk['player_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if not prior:
        return None
    for s in (season, season - 1):
        s_rows = [r for r in prior if r['season'] == s]
        if s_rows:
            vals = [r.get(stat) for r in s_rows if r.get(stat) is not None]
            return round(float(np.mean(vals)), 3) if vals else None
    return None


def _recent_starter(bulk: dict, player_id: str, game_date: str) -> int:
    """1 if the player started a majority of their last 5 games."""
    if player_id not in bulk['player_logs']:
        return 0
    dates, rows = bulk['player_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[max(0, cutoff - 5):cutoff]
    if not prior:
        return 0
    starts = sum(1 for r in prior if r.get('is_starter'))
    return int(starts >= max(1, len(prior) // 2 + 1))


def _opp_team_stat(bulk: dict, opp_team: str, season: int,
                   game_date: str, key: str) -> float | None:
    ts = bulk['team_stats']
    for s in (season, season - 1):
        k = (opp_team, s)
        if k in ts:
            dates, stats = ts[k]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                return stats[idx].get(key)
    return None


def _rest_days(bulk: dict, player_team: str, game_date: str) -> int | None:
    """Days since the player's team's previous game (scan games for the team)."""
    prior = None
    for g in bulk['games'].values():
        gd = g['game_date']
        if gd >= game_date:
            continue
        if g['home_team'] == player_team or g['away_team'] == player_team:
            if prior is None or gd > prior:
                prior = gd
    if prior is None:
        return None
    from datetime import datetime
    try:
        return (datetime.strptime(game_date, "%Y-%m-%d")
                - datetime.strptime(prior, "%Y-%m-%d")).days
    except (ValueError, TypeError):
        return None


# ── Row builder ────────────────────────────────────────────────────────────────

def _build_player_row(bulk: dict, player_id: str, player_name: str,
                      team: str, game_id: str, game_date: str, season: int,
                      log_row: dict | None) -> dict | None:
    """
    Build one NBA player feature row covering all nine prop targets.
    log_row (when training) carries the actual box score for target columns.
    Returns None if the game_id isn't in our games table.
    """
    game_info = bulk['games'].get(game_id)
    if not game_info:
        return None
    is_home  = 1 if team == game_info['home_team'] else 0
    opp_team = game_info['away_team'] if is_home else game_info['home_team']

    is_early = 0
    if player_id in bulk['player_logs']:
        dates, _ = bulk['player_logs'][player_id]
        is_early = int(bisect.bisect_left(dates, game_date) < 5)

    row = {
        "player_id":   player_id,
        "player_name": player_name,
        "team":        team,
        "opp_team":    opp_team,
        "game_id":     game_id,
        "game_date":   game_date,
        "season":      season,
        "is_home":     is_home,
        "is_starter":  _recent_starter(bulk, player_id, game_date),
        "is_early_season": is_early,
        "opp_def_rating":        _opp_team_stat(bulk, opp_team, season, game_date, 'def_rating'),
        "opp_pace":              _opp_team_stat(bulk, opp_team, season, game_date, 'pace'),
        "opp_points_allowed_pg": _opp_team_stat(bulk, opp_team, season, game_date, 'points_allowed_pg'),
        "rest_days":             _rest_days(bulk, team, game_date),
        # Minutes (opportunity)
        "min_last3_avg":  _rolling_avg(bulk, player_id, game_date, 'minutes', 3),
        "min_last5_avg":  _rolling_avg(bulk, player_id, game_date, 'minutes', 5),
        "season_min_avg": _season_avg(bulk, player_id, game_date, season, 'minutes'),
    }

    # Per-stat rolling/season/trend for each modelled stat
    for stat in _ROLL_STATS:
        l3  = _rolling_avg(bulk, player_id, game_date, stat, 3)
        l5  = _rolling_avg(bulk, player_id, game_date, stat, 5)
        l10 = _rolling_avg(bulk, player_id, game_date, stat, 10)
        s   = _season_avg(bulk, player_id, game_date, season, stat)
        row[f"{stat}_last3_avg"]  = l3
        row[f"{stat}_last5_avg"]  = l5
        row[f"{stat}_last10_avg"] = l10
        row[f"season_{stat}_avg"] = s
        row[f"{stat}_trend"]      = (round(l3 - s, 3) if (l3 is not None and s is not None) else None)

    # Targets (training only — actual box score in log_row)
    if log_row is not None:
        pts = log_row.get('points')
        reb = log_row.get('rebounds')
        ast = log_row.get('assists')
        row["target_points"]    = pts
        row["target_rebounds"]  = reb
        row["target_assists"]   = ast
        row["target_fg3"]       = log_row.get('fg3_made')
        row["target_pra"]       = ((pts or 0) + (reb or 0) + (ast or 0)
                                   if pts is not None else None)
        row["target_blocks"]    = log_row.get('blocks')
        row["target_steals"]    = log_row.get('steals')
        row["target_turnovers"] = log_row.get('turnovers')
        row["target_dd"]        = _double_double(pts, reb, ast,
                                                  log_row.get('steals'),
                                                  log_row.get('blocks')) if pts is not None else None

    return row


# ── Training dataset ───────────────────────────────────────────────────────────

def build_nba_prop_training_dataset(model_id: str, seasons: list[int]) -> pd.DataFrame:
    """Build the feature matrix + target for one NBA prop model."""
    if model_id not in NBA_PROP_FEATURE_MAP:
        raise NotImplementedError(f"No NBA prop feature map for {model_id}")
    feature_cols = NBA_PROP_FEATURE_MAP[model_id]
    stat = _TARGET_STAT[model_id]
    target_col = f"target_{stat}"

    conn = get_connection()
    try:
        bulk = build_bulk_nba_prop_lookups(conn, seasons)
    finally:
        conn.close()

    season_set = set(seasons)
    rows = []
    for player_id, (dates, log_rows) in bulk['player_logs'].items():
        for log in log_rows:
            if log['season'] not in season_set:
                continue
            # require the player actually played (minutes > 0) to be a real sample
            if (log.get('minutes') or 0) <= 0:
                continue
            r = _build_player_row(
                bulk, log['player_id'], log['player_name'], log['team'],
                log['game_id'], log['game_date'], log['season'], log_row=log,
            )
            if r is not None:
                rows.append(r)

    if not rows:
        logger.warning(f"No training rows generated for {model_id}")
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    if target_col != 'target' and target_col in df.columns:
        df = df.rename(columns={target_col: 'target'})

    meta_cols = ['player_id', 'player_name', 'team', 'opp_team',
                 'game_id', 'game_date', 'season']
    keep_cols = meta_cols + [c for c in feature_cols if c in df.columns] + ['target']
    df = df[[c for c in keep_cols if c in df.columns]]

    num_cols = [c for c in df.columns if c not in meta_cols + ['target']]
    before = len(df)
    df = df.dropna(subset=num_cols + ['target'])
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped}/{before} rows with null features/target "
                    f"({dropped/before:.1%})")
    if df.empty:
        logger.warning(f"{model_id}: 0 rows after null-drop")
        return df

    logger.success(
        f"{model_id}: {len(df)} training rows | target mean={df['target'].mean():.2f}, "
        f"std={df['target'].std():.2f}, range=[{df['target'].min():.0f}, {df['target'].max():.0f}]"
    )
    return df


# ── Scoring rows (daily pipeline) ──────────────────────────────────────────────

def build_nba_prop_scoring_rows(game_date: str, model_id: str) -> pd.DataFrame:
    """
    Build NBA player feature rows for today's games.

    Candidate players = everyone with a confirmed lineup slot for the date if
    available; otherwise everyone who has appeared for one of today's teams this
    season. NBA lineups aren't ingested into lineup_slots, so in practice the
    fallback (recent rotation players) is used — rotations are stable and the
    minutes-based features carry the opportunity signal.
    """
    if model_id not in NBA_PROP_FEATURE_MAP:
        raise NotImplementedError(f"No NBA prop feature map for {model_id}")
    feature_cols = NBA_PROP_FEATURE_MAP[model_id]
    season = _nba_season(game_date)

    conn = get_connection()
    try:
        # today's NBA games
        game_rows = conn.execute("""
            SELECT game_id, home_team, away_team
            FROM games WHERE sport = 'NBA' AND game_date = %s
        """, (game_date,)).fetchall()
        if not game_rows:
            logger.info(f"  No NBA games for {game_date} — skipping prop scoring")
            return pd.DataFrame()

        team_to_game = {}
        for gid, ht, at in game_rows:
            team_to_game[ht] = (gid, ht)
            team_to_game[at] = (gid, at)
        teams = tuple(team_to_game.keys())
        nba_game_ids = [gid for gid, _ht, _at in game_rows]

        # confirmed lineups (preferred) — MUST scope to today's NBA games.
        # lineup_slots is shared with MLB; without this scope the query returns
        # MLB players whose game_ids miss the NBA games lookup so every row drops.
        gph = ','.join(['%s'] * len(nba_game_ids))
        lineup_rows = conn.execute(f"""
            SELECT player_id, player_name, team, game_id
            FROM lineup_slots
            WHERE game_date = %s AND is_confirmed = TRUE
              AND game_id IN ({gph})
        """, [game_date] + nba_game_ids).fetchall()

        candidates = []  # (player_id, player_name, team, game_id)
        if lineup_rows:
            candidates = [(str(r[0]), r[1], r[2], r[3]) for r in lineup_rows]
        else:
            # fallback: recent players for today's teams this season
            ph = ','.join(['%s'] * len(teams))
            recent = conn.execute(f"""
                SELECT DISTINCT player_id, player_name, team
                FROM nba_player_game_log
                WHERE team IN ({ph})
                  AND season = %s
                  AND game_date < %s
            """, list(teams) + [season, game_date]).fetchall()
            for pid, name, team in recent:
                if team in team_to_game:
                    gid, _ = team_to_game[team]
                    candidates.append((str(pid), name, team, gid))

        bulk = build_bulk_nba_prop_lookups(conn, [season])
    finally:
        conn.close()

    rows = []
    for pid, name, team, game_id in candidates:
        r = _build_player_row(bulk, pid, name, team, game_id, game_date,
                              season, log_row=None)
        if r is not None:
            rows.append(r)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    meta_cols = ['player_id', 'player_name', 'team', 'opp_team',
                 'game_id', 'game_date', 'season']
    seen: set = set()
    keep_cols = []
    for c in meta_cols + [c for c in feature_cols if c in df.columns]:
        if c not in seen and c in df.columns:
            keep_cols.append(c)
            seen.add(c)
    return df[keep_cols]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Build NBA prop training dataset")
    parser.add_argument("model_id", help="e.g. nba_prop_player_points")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=[2019, 2020, 2021, 2022, 2023, 2024])
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = build_nba_prop_training_dataset(args.model_id, args.seasons)
    if not df.empty:
        if args.out:
            df.to_csv(args.out, index=False)
            logger.info(f"Saved to {args.out}")
        else:
            logger.info(f"Shape: {df.shape}")
            print(df.describe())
