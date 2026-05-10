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

PROP_FEATURE_MAP: dict[str, list[str]] = {
    "mlb_prop_pitcher_k": PROP_PITCHER_K_FEATURES,
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

    conn = get_connection()
    bulk = _build_bulk_prop_lookups(conn, seasons)
    conn.close()

    if model_id == 'mlb_prop_pitcher_k':
        raw_rows = _all_pitcher_k_rows(bulk, seasons, training_mode=True)
    else:
        raise NotImplementedError(f"build_prop_training_dataset not yet implemented for {model_id}")

    if not raw_rows:
        logger.warning(f"No training rows generated for {model_id}")
        return pd.DataFrame()

    df = pd.DataFrame(raw_rows)

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
