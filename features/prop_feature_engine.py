"""
prop_feature_engine.py — Feature builder for MLB player prop models.

Builds per-pitcher (and future per-batter) feature rows from:
  - player_game_log      rolling in-game stats per pitcher/batter
  - player_savant_stats  season-level Statcast metrics
  - mlb_team_stats       opponent team K% for batter context
  - game_weather         park context (dome, temp)
  - games                opponent team lookup

Umpire features (ump_k_per_game, ump_k_plus_minus) are defined but excluded from
PROP_PITCHER_K_FEATURES until the umpires table is populated. Add them and retrain.

Usage:
    from features.prop_feature_engine import build_prop_training_dataset
    df = build_prop_training_dataset("mlb_prop_pitcher_k", [2019, 2020, 2021, 2022, 2023])
"""

import bisect
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection, DBConnection


# ── Park HR Factors ────────────────────────────────────────────────────────────
# 5-year HR park factor (2019-2023 average) normalised to 1.0 = league average.
# Source: Baseball Reference multi-year park factors. Values above 1.0 favour HRs.
# Venues not listed fall back to 1.0 (neutral). Updated periodically — not a
# daily ingestor concern since park character changes slowly.

PARK_HR_FACTORS: dict[str, float] = {
    "Coors Field":              1.34,
    "Great American Ball Park": 1.19,
    "Citizens Bank Park":       1.14,
    "Yankee Stadium":           1.12,
    "Rogers Centre":            1.10,
    "American Family Field":    1.08,
    "Globe Life Field":         0.94,
    "Dodger Stadium":           0.95,
    "Fenway Park":              0.96,
    "Kauffman Stadium":         0.87,
    "T-Mobile Park":            0.88,
    "Petco Park":               0.88,
    "Oracle Park":              0.87,
    "Comerica Park":            0.90,
    "PNC Park":                 0.91,
    "loanDepot Park":           0.92,
    "Tropicana Field":          0.92,
    "Citi Field":               0.93,
    "Target Field":             0.96,
    "Busch Stadium":            0.97,
    "Angel Stadium":            0.97,
    "Camden Yards":             1.02,
    "Wrigley Field":            1.04,
    "Truist Park":              1.00,
    "Minute Maid Park":         1.01,
    "Guaranteed Rate Field":    1.05,
    "Progressive Field":        0.99,
    "Chase Field":              1.00,
    "Nationals Park":           0.98,
    "Oakland Coliseum":         0.82,
    "Sutter Health Park":       0.85,
}


# ── Feature Column Definitions ─────────────────────────────────────────────────

PROP_PITCHER_K_FEATURES = [
    # Rolling form — last N starts, strictly before game date
    "k_last3_avg",        # avg strikeouts over last 3 starts
    "k_last5_avg",        # avg strikeouts over last 5 starts
    "k_last10_avg",       # avg strikeouts over last 10 starts
    "k_rate_last3",       # Ks per true inning, last 3 starts (controls for IP)
    "k_rate_last5",       # Ks per true inning, last 5 starts
    "ip_last3_avg",       # avg innings (true decimal) last 3 starts — K ceiling signal
    "ip_last5_avg",       # avg innings (true decimal) last 5 starts
    "season_k_avg",       # season-to-date avg Ks per start
    "k_trend",            # k_last3_avg − season_k_avg  (positive = running hot)
    # Baseball Savant metrics — prior season to avoid data leakage in training
    # Note: savant_swstr_pct and savant_csw_pct are excluded — not populated
    # in our Savant pulls (Baseball Savant leaderboard CSV does not expose them
    # in the columns we download). Add if/when backfill is extended.
    "savant_k_pct",       # strikeout rate (K per PA)
    "savant_whiff_pct",   # whiff rate on swings (primary K predictor)
    "savant_bb_pct",      # walk rate
    "savant_xera",        # expected ERA
    "savant_avg_velocity",  # fastball velocity
    # Opponent offense
    "opp_team_k_pct",     # opponent team K% as hitters (strikeout tendency)
    # Ballpark / environment
    "is_dome_game",       # 1 = dome (neutralises wind/temp effects)
    "temp_f",             # game-time temperature (cold suppresses velocity/movement)
]

PROP_BATTER_HITS_FEATURES = [
    # Rolling form (last N games, strictly before game date)
    "hits_last5_avg",       # avg hits per game, last 5
    "hits_last10_avg",      # avg hits per game, last 10
    "hit_rate_last5",       # hits per AB, last 5 (quality vs volume)
    "hit_rate_last10",      # hits per AB, last 10
    "season_hit_avg",       # season-to-date avg hits/game (prior-season fallback)
    "hit_trend",            # hits_last5_avg − season_hit_avg (hot/cold signal)
    # Baseball Savant metrics (prior season to avoid data leakage in training)
    "savant_xba",           # expected batting average — ball-quality predictor
    "savant_woba",          # wOBA — correlates with overall contact production
    "savant_batter_k_pct",  # strikeout rate (higher K → fewer hits)
    "savant_exit_velocity", # hard contact quality
    # Context
    "batting_order",        # lineup slot 1-9 (determines AB opportunity)
    "opp_team_era",         # opposing pitching quality (team ERA as-of game date)
    "is_dome_game",
]

PROP_BATTER_TB_FEATURES = [
    # Rolling form
    "tb_last5_avg",         # avg total bases per game, last 5
    "tb_last10_avg",        # avg total bases per game, last 10
    "season_tb_avg",        # season-to-date avg TB/game (prior-season fallback)
    "tb_trend",             # tb_last5_avg − season_tb_avg
    "hr_last10_avg",        # recent HR rate (HR = 4 TB each — big driver)
    # Baseball Savant metrics (prior season)
    "savant_xslg",          # expected slugging — direct TB predictor
    "savant_barrel_pct",    # barrel rate — best power predictor
    "savant_hard_hit_pct",  # hard hit rate
    "savant_exit_velocity",
    "savant_launch_angle",  # 25-30° optimal for XBH
    # Context
    "batting_order",
    "opp_team_era",
    "is_dome_game",
    "temp_f",               # cold weather suppresses carry (fewer HR/XBH)
]

PROP_BATTER_HR_FEATURES = [
    # Rolling form (wider windows — HR is rare, need more samples)
    "hr_last10_avg",         # avg HR per game, last 10
    "hr_last20_avg",         # avg HR per game, last 20
    "season_hr_avg",         # season-to-date avg HR/game (prior-season fallback)
    # Baseball Savant batter metrics (prior season)
    "savant_barrel_pct",     # top HR predictor
    "savant_hard_hit_pct",
    "savant_xslg",
    "savant_exit_velocity",
    "savant_launch_angle",
    # Opposing starter — game-level signal (v2 additions)
    "opp_starter_hr9",       # opp starter season HR/9 as-of game (HR-prone pitcher)
    "opp_starter_hr9_last3", # opp starter HR/9 over last 3 starts (recent form)
    "opp_starter_gb_pct",    # opp starter groundball % (prior season) — GB pitcher → fewer HRs
    # Park and platoon (v2 additions)
    "park_hr_factor",        # ballpark HR index (1.0 = league avg; Coors ~1.34, Petco ~0.87)
    "platoon_advantage",     # 1 if batter faces opposite-hand pitcher, 0 if same, NaN if unknown
    # Context
    "batting_order",
    "is_dome_game",
    "temp_f",
]

PROP_FEATURE_MAP: dict[str, list[str]] = {
    "mlb_prop_pitcher_k":   PROP_PITCHER_K_FEATURES,
    "mlb_prop_batter_hits": PROP_BATTER_HITS_FEATURES,
    "mlb_prop_batter_tb":   PROP_BATTER_TB_FEATURES,
    "mlb_prop_batter_hr":   PROP_BATTER_HR_FEATURES,
}


# ── IP Conversion ──────────────────────────────────────────────────────────────

def _ip_to_decimal(ip: float | None) -> float | None:
    """
    Convert MLB innings-pitched notation to true decimal innings.
    MLB stores IP as whole.thirds:  2.1 = 2⅓,  6.2 = 6⅔,  6.0 = 6.0
    Formula: whole + (fractional digit) / 3
    """
    if ip is None:
        return None
    whole = int(ip)
    thirds = round((ip - whole) * 10)   # e.g. 2.1 → 1,  6.2 → 2
    if thirds > 2:                       # shouldn't happen, guard against float drift
        thirds = 2
    return round(whole + thirds / 3, 4)


# ── Bulk Data Loader ───────────────────────────────────────────────────────────

def _build_bulk_prop_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """
    Bulk-load all tables needed for prop feature building in ~5 queries.
    All data is loaded into memory; no per-row DB calls during feature assembly.
    """
    all_seasons    = sorted(set(seasons))
    # For Savant we need prior season (leakage avoidance) plus current
    savant_seasons = sorted(set(s + offset for s in all_seasons for offset in (-1, 0)))
    # For team stats we need the season before training start for early-season ASOF
    load_seasons   = sorted(set([min(all_seasons) - 1] + all_seasons))

    sp_sav  = ','.join(['%s'] * len(savant_seasons))
    sp_load = ','.join(['%s'] * len(load_seasons))
    sp_all  = ','.join(['%s'] * len(all_seasons))

    # ── Pitcher game logs ─────────────────────────────────────────────────────
    # Load ALL historical starts (not just requested seasons) so rolling windows
    # at the start of each season can reach back into prior-season starts.
    gl_cols = ['player_id', 'player_name', 'team', 'game_id', 'game_date', 'season',
               'p_strikeouts', 'innings_pitched', 'p_walks', 'p_hits_allowed']
    gl_rows = conn.execute("""
        SELECT player_id, player_name, team, game_id, game_date, season,
               p_strikeouts, innings_pitched, p_walks, p_hits_allowed
        FROM player_game_log
        WHERE player_type = 'pitcher'
          AND is_starter = TRUE
          AND p_strikeouts IS NOT NULL
        ORDER BY player_id, game_date
    """).fetchall()

    # player_id → (sorted_dates list, rows list)
    pitcher_logs: dict = {}
    for r in gl_rows:
        d = dict(zip(gl_cols, r))
        d['ip_dec'] = _ip_to_decimal(d['innings_pitched'])   # pre-convert once
        pid = d['player_id']
        if pid not in pitcher_logs:
            pitcher_logs[pid] = ([], [])
        pitcher_logs[pid][0].append(d['game_date'])
        pitcher_logs[pid][1].append(d)

    # ── Savant pitcher stats ──────────────────────────────────────────────────
    sv_cols = ['player_id', 'season', 'k_pct', 'bb_pct', 'whiff_pct',
               'swstr_pct', 'csw_pct', 'xera', 'avg_velocity']
    sv_rows = conn.execute(f"""
        SELECT player_id, season, k_pct, bb_pct, whiff_pct,
               swstr_pct, csw_pct, xera, avg_velocity
        FROM player_savant_stats
        WHERE player_type = 'pitcher'
          AND season IN ({sp_sav})
    """, savant_seasons).fetchall()
    # (player_id, season) → stats dict
    savant: dict = {(r[0], r[1]): dict(zip(sv_cols, r)) for r in sv_rows}

    # ── Team stats (opponent k_pct as hitters) ────────────────────────────────
    ts_cols = ['team', 'season', 'as_of_date', 'k_pct']
    ts_rows = conn.execute(f"""
        SELECT team, season, as_of_date, k_pct
        FROM mlb_team_stats
        WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()

    # (team, season) → (sorted_dates, k_pct_values)
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_stats:
            team_stats[k] = ([], [])
        team_stats[k][0].append(d['as_of_date'])
        team_stats[k][1].append(d['k_pct'])

    # ── Weather ───────────────────────────────────────────────────────────────
    w_rows = conn.execute("""
        SELECT game_id, temp_f, is_dome_game
        FROM game_weather
    """).fetchall()
    weather: dict = {r[0]: {'temp_f': r[1], 'is_dome_game': r[2]} for r in w_rows}

    # ── Games (home/away team lookup for opponent derivation) ─────────────────
    g_rows = conn.execute(f"""
        SELECT game_id, home_team, away_team
        FROM games
        WHERE sport = 'MLB'
          AND season IN ({sp_all})
    """, all_seasons).fetchall()
    games: dict = {r[0]: {'home_team': r[1], 'away_team': r[2]} for r in g_rows}

    logger.debug(
        f"Bulk loads: {len(gl_rows)} pitcher starts, {len(sv_rows)} savant rows, "
        f"{len(ts_rows)} team-stat rows, {len(w_rows)} weather rows, {len(g_rows)} games"
    )

    return dict(
        pitcher_logs=pitcher_logs,
        savant=savant,
        team_stats=team_stats,
        weather=weather,
        games=games,
    )


# ── Per-Row Feature Builders ───────────────────────────────────────────────────

def _pitcher_rolling(bulk: dict, player_id: str, game_date: str, season: int) -> dict:
    """
    Rolling pitcher K stats from prior starts strictly before game_date.
    Uses true decimal IP for rate calculations.
    Returns empty dict (all features None) if no prior starts exist.
    """
    if player_id not in bulk['pitcher_logs']:
        return {}

    dates, rows = bulk['pitcher_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior = rows[:cutoff]

    if not prior:
        return {}

    def _avg_ks(n: int) -> float | None:
        window = prior[-n:]
        if len(window) < n:
            return None
        ks = [r['p_strikeouts'] for r in window if r['p_strikeouts'] is not None]
        return round(float(np.mean(ks)), 3) if ks else None

    def _k_rate(n: int) -> float | None:
        window = prior[-n:]
        if len(window) < n:
            return None
        ks_total  = sum(r['p_strikeouts'] for r in window if r['p_strikeouts'] is not None)
        ip_total  = sum(r['ip_dec'] for r in window if r['ip_dec'] is not None)
        if not ip_total:
            return None
        return round(ks_total / ip_total, 3)

    def _avg_ip(n: int) -> float | None:
        window = prior[-n:]
        if len(window) < n:
            return None
        ips = [r['ip_dec'] for r in window if r['ip_dec'] is not None]
        return round(float(np.mean(ips)), 3) if ips else None

    # Season-to-date average (same season, before this game).
    # Falls back to prior season when no current-season starts exist yet
    # (e.g. first weeks of a new season, or when daily ingestion is behind).
    # Prior-season average is a known historical fact — not data leakage.
    season_k_avg: float | None = None
    for s in (season, season - 1):
        s_rows = [r for r in prior if r['season'] == s]
        if s_rows:
            ks = [r['p_strikeouts'] for r in s_rows if r['p_strikeouts'] is not None]
            season_k_avg = round(float(np.mean(ks)), 3) if ks else None
            break

    k_last3 = _avg_ks(3)
    k_trend: float | None = None
    if k_last3 is not None and season_k_avg is not None:
        k_trend = round(k_last3 - season_k_avg, 3)

    return {
        'k_last3_avg':  k_last3,
        'k_last5_avg':  _avg_ks(5),
        'k_last10_avg': _avg_ks(10),
        'k_rate_last3': _k_rate(3),
        'k_rate_last5': _k_rate(5),
        'ip_last3_avg': _avg_ip(3),
        'ip_last5_avg': _avg_ip(5),
        'season_k_avg': season_k_avg,
        'k_trend':      k_trend,
    }


def _pitcher_savant(bulk: dict, player_id: str, season: int,
                    training_mode: bool) -> dict:
    """
    Savant metrics for a pitcher.
    training_mode=True  → prior season (season-1). Avoids data leakage in training.
    training_mode=False → current season with prior-season fallback. For live scoring.
    """
    savant = bulk['savant']
    lookup = season - 1 if training_mode else season
    stats  = savant.get((player_id, lookup))
    if stats is None and not training_mode:
        stats = savant.get((player_id, season - 1))
    if stats is None:
        return {}
    return {
        'savant_k_pct':        stats.get('k_pct'),
        'savant_whiff_pct':    stats.get('whiff_pct'),
        'savant_swstr_pct':    stats.get('swstr_pct'),
        'savant_csw_pct':      stats.get('csw_pct'),
        'savant_bb_pct':       stats.get('bb_pct'),
        'savant_xera':         stats.get('xera'),
        'savant_avg_velocity': stats.get('avg_velocity'),
    }


def _opp_k_pct(bulk: dict, opp_team: str, season: int,
               game_date: str) -> float | None:
    """Opponent team K% as hitters, as-of game_date (ASOF bisect lookup)."""
    ts = bulk['team_stats']
    for s in (season, season - 1):
        key = (opp_team, s)
        if key in ts:
            dates, vals = ts[key]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0 and vals[idx] is not None:
                return vals[idx]
    return None


def _build_pitcher_k_row(bulk: dict,
                          player_id: str, player_name: str,
                          team: str, game_id: str, game_date: str,
                          season: int, target: int,
                          training_mode: bool = True) -> dict | None:
    """
    Build a single pitcher K feature row.
    Returns None if the game_id isn't in our games table (e.g. Tokyo Series).
    """
    game_info = bulk['games'].get(game_id)
    if not game_info:
        return None

    opp_team = (game_info['away_team']
                if team == game_info['home_team']
                else game_info['home_team'])

    rolling = _pitcher_rolling(bulk, player_id, game_date, season)
    savant  = _pitcher_savant(bulk, player_id, season, training_mode)
    weather = bulk['weather'].get(game_id, {})
    opp_kp  = _opp_k_pct(bulk, opp_team, season, game_date)

    return {
        # Metadata (excluded from model features)
        'player_id':   player_id,
        'player_name': player_name,
        'team':        team,
        'opp_team':    opp_team,
        'game_id':     game_id,
        'game_date':   game_date,
        'season':      season,
        'target':      target,
        # Rolling form
        **rolling,
        # Savant
        **savant,
        # Opponent
        'opp_team_k_pct':  opp_kp,
        # Context
        'is_dome_game': int(weather.get('is_dome_game') or 0),
        'temp_f':       weather.get('temp_f'),
    }


# ── Training Dataset Builder ───────────────────────────────────────────────────

def build_prop_training_dataset(model_id: str, seasons: list[int]) -> pd.DataFrame:
    """
    Build the full historical feature matrix for a prop model.

    Args:
        model_id: e.g. 'mlb_prop_pitcher_k'
        seasons:  training seasons to include

    Returns:
        DataFrame with feature columns + 'target' + metadata.
        Rows with any null feature values are dropped (no imputation).

    Target variable:
        pitcher K model → p_strikeouts (raw count, int). This feeds a Poisson
        regression in trainer.py, not a binary classifier.
    """
    from config import PROP_MODELS
    if model_id not in PROP_MODELS:
        raise ValueError(f"Unknown prop model_id: {model_id}. Check config.PROP_MODELS.")
    if model_id not in PROP_FEATURE_MAP:
        raise NotImplementedError(f"No feature map defined for {model_id}")

    feature_cols = PROP_FEATURE_MAP[model_id]

    _BATTER_MODELS = ('mlb_prop_batter_hits', 'mlb_prop_batter_tb', 'mlb_prop_batter_hr')
    _BATTER_TARGET = {
        'mlb_prop_batter_hits': 'target_hits',
        'mlb_prop_batter_tb':   'target_tb',
        'mlb_prop_batter_hr':   'target_hr',
    }

    if model_id == 'mlb_prop_pitcher_k':
        conn = get_connection()
        bulk = _build_bulk_prop_lookups(conn, seasons)
        conn.close()
        raw_rows = _all_pitcher_k_rows(bulk, seasons, training_mode=True)
        target_col = 'target'
    elif model_id in _BATTER_MODELS:
        conn = get_connection()
        bulk = _build_bulk_batter_lookups(conn, seasons)
        conn.close()
        raw_rows = _all_batter_rows(bulk, seasons)
        target_col = _BATTER_TARGET[model_id]
    else:
        raise NotImplementedError(f"build_prop_training_dataset not yet implemented for {model_id}")

    if not raw_rows:
        logger.warning(f"No training rows generated for {model_id}")
        return pd.DataFrame()

    df = pd.DataFrame(raw_rows)

    # Normalise target column to 'target' for trainer compatibility
    if target_col != 'target' and target_col in df.columns:
        df = df.rename(columns={target_col: 'target'})

    meta_cols = ['player_id', 'player_name', 'team', 'opp_team',
                 'game_id', 'game_date', 'season']
    keep_cols = meta_cols + [c for c in feature_cols if c in df.columns] + ['target']
    df = df[[c for c in keep_cols if c in df.columns]]

    num_cols = [c for c in df.columns if c not in meta_cols + ['target']]
    before = len(df)
    df = df.dropna(subset=num_cols)
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped}/{before} rows with null features "
                    f"({dropped/before:.1%})")

    if df.empty:
        logger.warning(f"{model_id}: 0 rows after null-drop")
        return df

    logger.success(
        f"{model_id}: {len(df)} training rows | "
        f"target mean={df['target'].mean():.2f}, "
        f"std={df['target'].std():.2f}, "
        f"range=[{df['target'].min():.0f}, {df['target'].max():.0f}]"
    )
    return df


def _all_pitcher_k_rows(bulk: dict, seasons: list[int],
                         training_mode: bool) -> list[dict]:
    """Iterate all pitcher starts in the requested seasons and build feature rows."""
    season_set = set(seasons)
    rows = []
    skipped_no_game = 0

    for player_id, (dates, log_rows) in bulk['pitcher_logs'].items():
        for log in log_rows:
            if log['season'] not in season_set:
                continue

            row = _build_pitcher_k_row(
                bulk,
                player_id=log['player_id'],
                player_name=log['player_name'],
                team=log['team'],
                game_id=log['game_id'],
                game_date=log['game_date'],
                season=log['season'],
                target=log['p_strikeouts'],
                training_mode=training_mode,
            )
            if row is None:
                skipped_no_game += 1
            else:
                rows.append(row)

    if skipped_no_game:
        logger.debug(f"  Skipped {skipped_no_game} starts: game_id not in games table")

    logger.info(f"Built {len(rows)} pitcher K candidate rows")
    return rows


# ── Scoring Row Builder (daily pipeline) ───────────────────────────────────────

def build_pitcher_k_scoring_rows(game_date: str,
                                  pitchers: list[dict]) -> pd.DataFrame:
    """
    Build pitcher K feature rows for today's probable starters.

    Args:
        game_date: YYYY-MM-DD scoring date
        pitchers:  list of dicts, each with keys:
                     player_id   (str) — MLB player ID from statsapi
                     player_name (str) — full name
                     team        (str) — 3-letter abbreviation
                     game_id     (str) — e.g. 'MLB_2026-05-09_NYY_BOS'

    player_game_log is NOT used for today's entries (those don't exist pre-game).
    Rolling stats are computed from historical game_log rows strictly before
    game_date using the bisect lookup in _pitcher_rolling().

    Returns DataFrame with feature columns. Missing features left as NaN —
    scorer skips pitchers without enough historical data rather than imputing.
    """
    if not pitchers:
        return pd.DataFrame()

    season = int(game_date[:4])
    conn = get_connection()
    bulk = _build_bulk_prop_lookups(conn, [season])
    conn.close()

    rows = []
    for p in pitchers:
        row = _build_pitcher_k_row(
            bulk,
            player_id=p['player_id'],
            player_name=p['player_name'],
            team=p['team'],
            game_id=p['game_id'],
            game_date=game_date,
            season=season,
            target=None,          # no target at scoring time
            training_mode=False,  # use current season savant with prior fallback
        )
        if row is not None:
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    feature_cols = PROP_PITCHER_K_FEATURES
    meta_cols = ['player_id', 'player_name', 'team', 'opp_team', 'game_id', 'game_date', 'season']
    keep_cols = meta_cols + [c for c in feature_cols if c in df.columns]
    return df[[c for c in keep_cols if c in df.columns]]


# ── Batter Bulk Data Loader ────────────────────────────────────────────────────

def _build_bulk_batter_lookups(conn: DBConnection, seasons: list[int]) -> dict:
    """
    Bulk-load all tables needed for batter prop feature building.
    Mirrors _build_bulk_prop_lookups but for batter models.
    """
    all_seasons    = sorted(set(seasons))
    savant_seasons = sorted(set(s + offset for s in all_seasons for offset in (-1, 0)))
    load_seasons   = sorted(set([min(all_seasons) - 1] + all_seasons))

    sp_sav  = ','.join(['%s'] * len(savant_seasons))
    sp_load = ','.join(['%s'] * len(load_seasons))
    sp_all  = ','.join(['%s'] * len(all_seasons))

    # ── Batter game logs ──────────────────────────────────────────────────────
    # Load ALL seasons so rolling windows at the start of each training season
    # can reach back into prior-season games.
    gl_cols = [
        'player_id', 'player_name', 'team', 'game_id', 'game_date', 'season',
        'at_bats', 'hits', 'total_bases', 'home_runs', 'rbi', 'runs',
        'walks', 'strikeouts', 'stolen_bases', 'batting_order',
    ]
    gl_rows = conn.execute("""
        SELECT player_id, player_name, team, game_id, game_date, season,
               at_bats, hits, total_bases, home_runs, rbi, runs,
               walks, strikeouts, stolen_bases, batting_order
        FROM player_game_log
        WHERE player_type = 'batter'
          AND at_bats >= 1
          AND hits IS NOT NULL
        ORDER BY player_id, game_date
    """).fetchall()

    batter_logs: dict = {}
    for r in gl_rows:
        d = dict(zip(gl_cols, r))
        pid = d['player_id']
        if pid not in batter_logs:
            batter_logs[pid] = ([], [])
        batter_logs[pid][0].append(d['game_date'])
        batter_logs[pid][1].append(d)

    # ── Savant batter stats ───────────────────────────────────────────────────
    sv_cols = [
        'player_id', 'season', 'batter_k_pct', 'batter_bb_pct',
        'batting_avg', 'slg_pct', 'obp', 'woba', 'xwoba',
        'xba', 'xslg', 'barrel_pct', 'hard_hit_pct',
        'launch_angle', 'exit_velocity', 'sprint_speed',
    ]
    sv_rows = conn.execute(f"""
        SELECT player_id, season, batter_k_pct, batter_bb_pct,
               batting_avg, slg_pct, obp, woba, xwoba,
               xba, xslg, barrel_pct, hard_hit_pct,
               launch_angle, exit_velocity, sprint_speed
        FROM player_savant_stats
        WHERE player_type = 'batter'
          AND season IN ({sp_sav})
    """, savant_seasons).fetchall()
    savant_batters: dict = {(r[0], r[1]): dict(zip(sv_cols, r)) for r in sv_rows}

    # ── Team pitching (opponent quality for batters) ───────────────────────────
    # Loads ERA and bullpen ERA for the opposing team.
    ts_cols = ['team', 'season', 'as_of_date', 'team_era', 'bullpen_era']
    ts_rows = conn.execute(f"""
        SELECT team, season, as_of_date, team_era, bullpen_era
        FROM mlb_team_stats
        WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()

    team_pitching: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_pitching:
            team_pitching[k] = ([], [], [])
        team_pitching[k][0].append(d['as_of_date'])
        team_pitching[k][1].append(d['team_era'])
        team_pitching[k][2].append(d['bullpen_era'])

    # ── Weather (include venue for park factor lookup) ─────────────────────────
    w_rows = conn.execute("""
        SELECT game_id, temp_f, is_dome_game, venue
        FROM game_weather
    """).fetchall()
    weather: dict = {r[0]: {'temp_f': r[1], 'is_dome_game': r[2], 'venue': r[3]}
                     for r in w_rows}

    # ── Games ─────────────────────────────────────────────────────────────────
    g_rows = conn.execute(f"""
        SELECT game_id, home_team, away_team
        FROM games
        WHERE sport = 'MLB'
          AND season IN ({sp_all})
    """, all_seasons).fetchall()
    games: dict = {r[0]: {'home_team': r[1], 'away_team': r[2]} for r in g_rows}

    # ── Pitcher game logs (for opposing-starter HR/9 rolling + starter ID) ────
    # Load all historical starts so rolling windows at season start can look back.
    p_gl_cols = ['player_id', 'game_id', 'game_date', 'team', 'season',
                 'p_home_runs', 'innings_pitched']
    p_gl_rows = conn.execute("""
        SELECT player_id, game_id, game_date, team, season,
               p_home_runs, innings_pitched
        FROM player_game_log
        WHERE player_type = 'pitcher'
          AND is_starter = TRUE
          AND p_home_runs IS NOT NULL
        ORDER BY player_id, game_date
    """).fetchall()

    pitcher_logs: dict = {}   # player_id → (sorted_dates, rows)
    game_starters: dict = {}  # game_id → {team: player_id}
    for r in p_gl_rows:
        d = dict(zip(p_gl_cols, r))
        d['ip_dec'] = _ip_to_decimal(d['innings_pitched'])
        pid = d['player_id']
        if pid not in pitcher_logs:
            pitcher_logs[pid] = ([], [])
        pitcher_logs[pid][0].append(d['game_date'])
        pitcher_logs[pid][1].append(d)
        gid = d['game_id']
        if gid not in game_starters:
            game_starters[gid] = {}
        game_starters[gid][d['team']] = pid

    # ── Pitcher Savant gb_pct (prior-season, leakage-safe) ────────────────────
    p_sv_rows = conn.execute(f"""
        SELECT player_id, season, gb_pct
        FROM player_savant_stats
        WHERE player_type = 'pitcher'
          AND season IN ({sp_sav})
    """, savant_seasons).fetchall()
    pitcher_savant: dict = {(r[0], r[1]): r[2] for r in p_sv_rows}

    # ── Player handedness ─────────────────────────────────────────────────────
    hand_rows = conn.execute("""
        SELECT player_id, bat_hand, throw_hand
        FROM player_handedness
    """).fetchall()
    player_hands: dict = {r[0]: {'bat_hand': r[1], 'throw_hand': r[2]}
                          for r in hand_rows}

    logger.debug(
        f"Batter bulk loads: {len(gl_rows)} batter games, {len(sv_rows)} savant rows, "
        f"{len(ts_rows)} team-pitching rows, {len(w_rows)} weather rows, "
        f"{len(g_rows)} games, {len(p_gl_rows)} pitcher starts, "
        f"{len(p_sv_rows)} pitcher savant rows, {len(hand_rows)} player hands"
    )

    return dict(
        batter_logs=batter_logs,
        savant_batters=savant_batters,
        team_pitching=team_pitching,
        weather=weather,
        games=games,
        pitcher_logs=pitcher_logs,
        game_starters=game_starters,
        pitcher_savant=pitcher_savant,
        player_hands=player_hands,
    )


# ── Batter Rolling Helpers ─────────────────────────────────────────────────────

def _batter_rolling_avg(bulk: dict, player_id: str, game_date: str,
                        stat_col: str, n: int) -> float | None:
    """Avg of stat_col over the last n games strictly before game_date."""
    if player_id not in bulk['batter_logs']:
        return None
    dates, rows = bulk['batter_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if len(prior) < n:
        return None
    window = prior[-n:]
    vals = [r[stat_col] for r in window if r[stat_col] is not None]
    return round(float(np.mean(vals)), 3) if vals else None


def _batter_rate(bulk: dict, player_id: str, game_date: str,
                 num_col: str, denom_col: str, n: int) -> float | None:
    """
    sum(num_col) / sum(denom_col) over the last n games.
    Used for hit rate (hits/AB) and similar rate stats.
    """
    if player_id not in bulk['batter_logs']:
        return None
    dates, rows = bulk['batter_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if len(prior) < n:
        return None
    window = prior[-n:]
    num   = sum(r[num_col]   for r in window if r[num_col]   is not None)
    denom = sum(r[denom_col] for r in window if r[denom_col] is not None)
    return round(num / denom, 3) if denom else None


def _batter_season_avg(bulk: dict, player_id: str, game_date: str,
                       season: int, stat_col: str) -> float | None:
    """
    Season-to-date avg of stat_col, strictly before game_date.
    Falls back to prior season if current season has no data yet
    (e.g. first weeks of a new season — prior season avg is valid historical fact).
    """
    if player_id not in bulk['batter_logs']:
        return None
    dates, rows = bulk['batter_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if not prior:
        return None
    for s in (season, season - 1):
        s_rows = [r for r in prior if r['season'] == s]
        if s_rows:
            vals = [r[stat_col] for r in s_rows if r[stat_col] is not None]
            return round(float(np.mean(vals)), 3) if vals else None
    return None


# ── Batter Savant and Context Helpers ──────────────────────────────────────────

def _batter_savant(bulk: dict, player_id: str, season: int,
                   training_mode: bool) -> dict:
    """
    Savant metrics for a batter.
    training_mode=True  → prior season (season-1). Avoids data leakage.
    training_mode=False → current season with prior-season fallback.
    """
    savant = bulk['savant_batters']
    lookup = season - 1 if training_mode else season
    stats  = savant.get((player_id, lookup))
    if stats is None and not training_mode:
        stats = savant.get((player_id, season - 1))
    if stats is None:
        return {}
    return {
        'savant_xba':           stats.get('xba'),
        'savant_woba':          stats.get('woba'),
        'savant_xwoba':         stats.get('xwoba'),
        'savant_xslg':          stats.get('xslg'),
        'savant_batter_k_pct':  stats.get('batter_k_pct'),
        'savant_batter_bb_pct': stats.get('batter_bb_pct'),
        'savant_barrel_pct':    stats.get('barrel_pct'),
        'savant_hard_hit_pct':  stats.get('hard_hit_pct'),
        'savant_exit_velocity': stats.get('exit_velocity'),
        'savant_launch_angle':  stats.get('launch_angle'),
        'savant_sprint_speed':  stats.get('sprint_speed'),
    }


def _opp_pitching(bulk: dict, opp_team: str, season: int,
                  game_date: str) -> dict:
    """
    Opponent team pitching quality as-of game_date (bisect ASOF lookup).
    Falls back to prior season if current season has no rows yet.
    """
    tp = bulk['team_pitching']
    for s in (season, season - 1):
        key = (opp_team, s)
        if key in tp:
            dates, eras, bp_eras = tp[key]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                return {
                    'opp_team_era':    eras[idx],
                    'opp_bullpen_era': bp_eras[idx],
                }
    return {}


# ── Opposing Starter HR/9 Helpers ─────────────────────────────────────────────

def _starter_hr9_rolling(bulk: dict, player_id: str, game_date: str,
                         n: int) -> float | None:
    """HR/9 for the opposing starter over the last n starts before game_date."""
    if player_id not in bulk['pitcher_logs']:
        return None
    dates, rows = bulk['pitcher_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    if len(prior) < n:
        return None
    window = prior[-n:]
    hrs = sum(r['p_home_runs'] for r in window if r['p_home_runs'] is not None)
    ips = sum(r['ip_dec']      for r in window if r['ip_dec']      is not None)
    if not ips:
        return None
    return round(hrs / ips * 9, 3)


def _starter_hr9_season(bulk: dict, player_id: str, game_date: str,
                        season: int) -> float | None:
    """Season-to-date HR/9 for the opposing starter, with prior-season fallback."""
    if player_id not in bulk['pitcher_logs']:
        return None
    dates, rows = bulk['pitcher_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior  = rows[:cutoff]
    for s in (season, season - 1):
        s_rows = [r for r in prior if r['season'] == s]
        if s_rows:
            hrs = sum(r['p_home_runs'] for r in s_rows if r['p_home_runs'] is not None)
            ips = sum(r['ip_dec']      for r in s_rows if r['ip_dec']      is not None)
            if ips > 0:
                return round(hrs / ips * 9, 3)
    return None


def _starter_gb_pct(bulk: dict, player_id: str, season: int,
                    training_mode: bool) -> float | None:
    """Pitcher groundball % from Savant. Prior season in training to avoid leakage."""
    lookup = season - 1 if training_mode else season
    gb = bulk['pitcher_savant'].get((player_id, lookup))
    if gb is None and not training_mode:
        gb = bulk['pitcher_savant'].get((player_id, season - 1))
    return gb


# ── Batter Row Builder ─────────────────────────────────────────────────────────

def _build_batter_row(bulk: dict,
                      player_id: str, player_name: str,
                      team: str, game_id: str, game_date: str,
                      season: int, log_row: dict | None,
                      training_mode: bool = True) -> dict | None:
    """
    Build a single batter feature row covering all three batter prop models
    (hits, TB, HR). The caller selects the right target column and feature
    subset via build_prop_training_dataset or build_batter_scoring_rows.

    log_row must contain at minimum: batting_order, hits, total_bases,
    home_runs, at_bats (all from player_game_log or lineup_slots at score time).
    Returns None if the game_id isn't in our games table.
    """
    game_info = bulk['games'].get(game_id)
    if not game_info:
        return None

    opp_team = (game_info['away_team']
                if team == game_info['home_team']
                else game_info['home_team'])

    weather  = bulk['weather'].get(game_id, {})
    sv       = _batter_savant(bulk, player_id, season, training_mode)
    pitching = _opp_pitching(bulk, opp_team, season, game_date)

    # ── Opposing starter features (HR model) ─────────────────────────────────
    opp_starter_id  = bulk['game_starters'].get(game_id, {}).get(opp_team)
    opp_hr9         = None
    opp_hr9_last3   = None
    opp_gb          = None
    platoon_adv     = None
    if opp_starter_id:
        opp_hr9       = _starter_hr9_season(bulk, opp_starter_id, game_date, season)
        opp_hr9_last3 = _starter_hr9_rolling(bulk, opp_starter_id, game_date, 3)
        opp_gb        = _starter_gb_pct(bulk, opp_starter_id, season, training_mode)
        # Platoon: 1 = batter faces opposite-hand pitcher (historically advantageous)
        batter_hand  = bulk['player_hands'].get(player_id, {}).get('bat_hand')
        pitcher_hand = bulk['player_hands'].get(opp_starter_id, {}).get('throw_hand')
        if batter_hand and pitcher_hand:
            # Switch hitters always face the "opposite" hand so platoon_adv = 1
            if batter_hand == 'S':
                platoon_adv = 1
            else:
                platoon_adv = 1 if batter_hand != pitcher_hand else 0

    # ── Park HR factor ─────────────────────────────────────────────────────────
    venue         = weather.get('venue')
    park_hr_factor = PARK_HR_FACTORS.get(venue, 1.0) if venue else 1.0

    # ── Rolling stats ─────────────────────────────────────────────────────────
    hits5    = _batter_rolling_avg(bulk, player_id, game_date, 'hits', 5)
    hits10   = _batter_rolling_avg(bulk, player_id, game_date, 'hits', 10)
    hit_r5   = _batter_rate(bulk, player_id, game_date, 'hits', 'at_bats', 5)
    hit_r10  = _batter_rate(bulk, player_id, game_date, 'hits', 'at_bats', 10)
    s_hit    = _batter_season_avg(bulk, player_id, game_date, season, 'hits')

    tb5      = _batter_rolling_avg(bulk, player_id, game_date, 'total_bases', 5)
    tb10     = _batter_rolling_avg(bulk, player_id, game_date, 'total_bases', 10)
    s_tb     = _batter_season_avg(bulk, player_id, game_date, season, 'total_bases')

    hr10     = _batter_rolling_avg(bulk, player_id, game_date, 'home_runs', 10)
    hr20     = _batter_rolling_avg(bulk, player_id, game_date, 'home_runs', 20)
    s_hr     = _batter_season_avg(bulk, player_id, game_date, season, 'home_runs')

    hit_trend = (round(hits5 - s_hit, 3)
                 if hits5 is not None and s_hit is not None else None)
    tb_trend  = (round(tb5 - s_tb, 3)
                 if tb5 is not None and s_tb is not None else None)

    return {
        # ── Metadata ──────────────────────────────────────────────────────────
        'player_id':    player_id,
        'player_name':  player_name,
        'team':         team,
        'opp_team':     opp_team,
        'game_id':      game_id,
        'game_date':    game_date,
        'season':       season,
        # ── Targets (None at score time) ──────────────────────────────────────
        'target_hits':  log_row.get('hits')        if log_row else None,
        'target_tb':    log_row.get('total_bases')  if log_row else None,
        'target_hr':    log_row.get('home_runs')    if log_row else None,
        # ── Hits features ─────────────────────────────────────────────────────
        'hits_last5_avg':  hits5,
        'hits_last10_avg': hits10,
        'hit_rate_last5':  hit_r5,
        'hit_rate_last10': hit_r10,
        'season_hit_avg':  s_hit,
        'hit_trend':       hit_trend,
        # ── TB features ───────────────────────────────────────────────────────
        'tb_last5_avg':    tb5,
        'tb_last10_avg':   tb10,
        'season_tb_avg':   s_tb,
        'tb_trend':        tb_trend,
        # ── HR features ───────────────────────────────────────────────────────
        'hr_last10_avg':   hr10,
        'hr_last20_avg':   hr20,
        'season_hr_avg':   s_hr,
        # ── Opposing starter (HR model v2) ────────────────────────────────────
        'opp_starter_hr9':       opp_hr9,
        'opp_starter_hr9_last3': opp_hr9_last3,
        'opp_starter_gb_pct':    opp_gb,
        # ── Park and platoon (HR model v2) ────────────────────────────────────
        'park_hr_factor':    park_hr_factor,
        'platoon_advantage': platoon_adv,
        # ── Savant (all models share the same pull) ────────────────────────────
        **sv,
        # ── Opponent pitching ─────────────────────────────────────────────────
        **pitching,
        # ── Context ───────────────────────────────────────────────────────────
        'batting_order': log_row.get('batting_order') if log_row else None,
        'is_dome_game':  int(weather.get('is_dome_game') or 0),
        'temp_f':        weather.get('temp_f'),
    }


# ── Training Iterator ──────────────────────────────────────────────────────────

def _all_batter_rows(bulk: dict, seasons: list[int],
                     min_ab: int = 1) -> list[dict]:
    """
    Iterate all batter game-log rows for the requested seasons and build
    feature rows. Each row covers all three batter prop targets at once
    (hits, TB, HR) so the bulk load only happens once regardless of which
    model is being trained.

    min_ab=1 filters true DNPs (player on lineup but never batted).
    """
    season_set = set(seasons)
    rows       = []
    skipped_no_game = 0

    for player_id, (dates, log_rows) in bulk['batter_logs'].items():
        for log in log_rows:
            if log['season'] not in season_set:
                continue
            if (log['at_bats'] or 0) < min_ab:
                continue

            row = _build_batter_row(
                bulk,
                player_id=log['player_id'],
                player_name=log['player_name'],
                team=log['team'],
                game_id=log['game_id'],
                game_date=log['game_date'],
                season=log['season'],
                log_row=log,
                training_mode=True,
            )
            if row is None:
                skipped_no_game += 1
            else:
                rows.append(row)

    if skipped_no_game:
        logger.debug(f"  Skipped {skipped_no_game} batter games: game_id not in games table")
    logger.info(f"Built {len(rows)} batter candidate rows")
    return rows


# ── Batter Scoring Row Builder (daily pipeline) ────────────────────────────────

def build_batter_scoring_rows(game_date: str, model_id: str) -> pd.DataFrame:
    """
    Build batter feature rows for today's confirmed lineups.

    Reads batting_order and team from lineup_slots (populated by lineup_ingestor).
    Historical rolling stats come from player_game_log (strictly before game_date).
    Returns DataFrame with feature columns ready for scorer prediction.

    Batters missing 5+ games of history (new players, early season) will have null
    rolling features and are dropped — scorer skips them rather than imputing.
    """
    if model_id not in PROP_FEATURE_MAP:
        raise NotImplementedError(f"No feature map for {model_id}")

    feature_cols = PROP_FEATURE_MAP[model_id]
    season       = int(game_date[:4])

    conn = get_connection()
    try:
        lineup_rows = conn.execute("""
            SELECT player_id, player_name, team, game_id, batting_order
            FROM lineup_slots
            WHERE game_date = %s
              AND is_confirmed = TRUE
            ORDER BY game_id, team, batting_order
        """, (game_date,)).fetchall()

        if not lineup_rows:
            logger.info(f"  No confirmed lineups for {game_date} — skipping batter scoring")
            return pd.DataFrame()

        bulk = _build_bulk_batter_lookups(conn, [season])
    finally:
        conn.close()

    rows = []
    for r in lineup_rows:
        pid, name, team, game_id, batting_order = str(r[0]), r[1], r[2], r[3], r[4]
        log_row = {'batting_order': batting_order}     # no target at score time
        row = _build_batter_row(
            bulk,
            player_id=pid,
            player_name=name,
            team=team,
            game_id=game_id,
            game_date=game_date,
            season=season,
            log_row=log_row,
            training_mode=False,
        )
        if row is not None:
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    meta_cols = ['player_id', 'player_name', 'team', 'opp_team',
                 'game_id', 'game_date', 'season', 'batting_order']
    # Deduplicate: batting_order appears in both meta and feature lists
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

    parser = argparse.ArgumentParser(description="Build prop training dataset")
    parser.add_argument("model_id", help="e.g. mlb_prop_pitcher_k")
    parser.add_argument("--seasons", nargs="+", type=int,
                        default=[2019, 2020, 2021, 2022, 2023])
    parser.add_argument("--out", default=None, help="Output CSV path")
    args = parser.parse_args()

    df = build_prop_training_dataset(args.model_id, args.seasons)
    if not df.empty:
        if args.out:
            df.to_csv(args.out, index=False)
            logger.info(f"Saved to {args.out}")
        else:
            logger.info(f"Shape: {df.shape}")
            print(df.describe())
            print("\nNull counts:")
            print(df.isnull().sum())
