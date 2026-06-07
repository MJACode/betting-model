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
    # Umpire
    "ump_k_plus_minus",   # HP umpire career avg starter Ks minus league avg (Ks/game delta)
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

PROP_BATTER_RBI_FEATURES = [
    # Rolling form — RBIs require runners on base, so team context matters
    "rbi_last5_avg",       # avg RBIs per game, last 5
    "rbi_last10_avg",      # avg RBIs per game, last 10
    "season_rbi_avg",      # season-to-date avg RBIs (prior-season fallback)
    "rbi_trend",           # rbi_last5_avg − season_rbi_avg
    # Contact quality — hard contact clears bases
    "savant_xba",          # expected batting average (ball quality)
    "savant_xslg",         # extra base hits are the primary RBI vehicle
    # Context — batting order determines RBI opportunity directly
    "batting_order",       # 3-5 hitters face more runners on base
    "opp_team_era",        # weaker pitching = more base-runners for RBI opportunities
    "is_dome_game",
]

PROP_BATTER_RUNS_FEATURES = [
    # Rolling form — runs require getting on base then being driven in
    "runs_last5_avg",      # avg runs scored per game, last 5
    "runs_last10_avg",     # avg runs scored per game, last 10
    "season_runs_avg",     # season-to-date avg runs (prior-season fallback)
    "runs_trend",          # runs_last5_avg − season_runs_avg
    # On-base and speed
    "savant_woba",         # best single predictor of getting on base
    "savant_sprint_speed", # faster players score more often from 2nd/3rd
    # Context
    "batting_order",       # leadoff/2-hole batters score most often
    "opp_team_era",        # weaker pitching = more baserunners who score
    "is_dome_game",
]

PROP_BATTER_SB_FEATURES = [
    # Rolling form — wider windows needed (SBs are rare, ~0.05/game average)
    "sb_last10_avg",       # avg SBs per game, last 10
    "sb_last20_avg",       # avg SBs per game, last 20 (key for rare-event stability)
    "season_sb_avg",       # season-to-date avg (prior-season fallback)
    # Speed — primary predictor of stolen bases
    "savant_sprint_speed", # sprint speed is the best available SB predictor
    # Context
    "batting_order",       # leadoff/table-setters steal most often
    "is_dome_game",
]

PROP_BATTER_WALKS_FEATURES = [
    # Rolling form
    "walks_last5_avg",         # avg walks per game, last 5
    "walks_last10_avg",        # avg walks per game, last 10
    "season_walks_avg",        # season-to-date avg walks (prior-season fallback)
    "walks_trend",             # walks_last5_avg − season_walks_avg
    # Plate discipline — best walk predictors
    "savant_batter_bb_pct",    # career BB% — patience is a stable skill
    "savant_batter_k_pct",     # K% correlates with BB% (two-true-outcome batters)
    # Context
    "batting_order",           # leadoff/2-hole batters see more pitches, walk more
    "opp_team_era",            # weaker pitchers issue more walks to avoid damage
    "is_dome_game",
]

PROP_PITCHER_HITS_FEATURES = [
    # Rolling form
    "hits_last3_avg",    # avg hits allowed per start, last 3
    "hits_last5_avg",
    "hits_last10_avg",
    "hit_rate_last3",    # hits per true inning, last 3 (controls for IP)
    "ip_last3_avg",      # innings pitched last 3 — more IP = more hits exposure
    "season_hits_avg",   # season-to-date avg hits allowed (prior-season fallback)
    "hits_trend",        # hits_last3_avg − season_hits_avg
    # Savant — contact/whiff signals
    "savant_whiff_pct",  # more whiffs = less contact = fewer hits
    "savant_k_pct",      # K replaces ball-in-play → fewer hits
    "savant_xera",       # overall stuff quality
    "savant_avg_velocity",
    # Opponent offense quality
    "opp_team_woba",     # how well does this lineup make contact?
    # Context
    "is_dome_game",
    "temp_f",
]

PROP_PITCHER_ER_FEATURES = [
    # Rolling form
    "er_last3_avg",      # avg earned runs per start, last 3
    "er_last5_avg",
    "er_last10_avg",
    "er_rate_last3",     # ER per true inning, last 3
    "ip_last3_avg",      # more IP = more ER exposure
    "season_er_avg",
    "er_trend",
    # Savant — walks and HR rate drive ER most
    "savant_bb_pct",     # walks precede ER
    "savant_xera",
    "savant_avg_velocity",
    # Opponent
    "opp_team_woba",
    # Context
    "park_hr_factor",    # HR-friendly parks inflate ER directly
    "is_dome_game",
    "temp_f",
]

PROP_PITCHER_OUTS_FEATURES = [
    # Rolling form — how deep does this pitcher typically go?
    "outs_last3_avg",    # avg outs recorded per start, last 3
    "outs_last5_avg",
    "outs_last10_avg",
    "season_outs_avg",
    "outs_trend",
    # Savant — quality pitchers go deeper
    "savant_xera",
    "savant_k_pct",
    # Opponent — tough lineup forces pitchers out earlier
    "opp_team_woba",
    # Context
    "is_dome_game",
]

PROP_PITCHER_WALKS_FEATURES = [
    # Rolling form — command consistency
    "walks_last3_avg",
    "walks_last5_avg",
    "walks_last10_avg",
    "bb_rate_last3",     # walks per true inning, last 3
    "ip_last3_avg",
    "season_walks_avg",
    "walks_trend",
    # Savant — command/control signals
    "savant_bb_pct",     # best walk predictor
    "savant_avg_velocity",
    # Opponent — patient lineups draw more walks
    "opp_team_bb_pct",
    "opp_team_k_pct",       # aggressive (high-K) lineups draw fewer walks
    "opp_team_chase_pct",   # season avg chase% — process signal beyond bb-rate outcome
    # Umpire — ASOF walk-zone tendency (tight zone → more walks)
    "ump_bb_plus_minus",
    # Context
    "is_dome_game",
]

PROP_FEATURE_MAP: dict[str, list[str]] = {
    "mlb_prop_pitcher_k":     PROP_PITCHER_K_FEATURES,
    "mlb_prop_pitcher_hits":  PROP_PITCHER_HITS_FEATURES,
    "mlb_prop_pitcher_er":    PROP_PITCHER_ER_FEATURES,
    "mlb_prop_pitcher_outs":  PROP_PITCHER_OUTS_FEATURES,
    "mlb_prop_pitcher_walks": PROP_PITCHER_WALKS_FEATURES,
    "mlb_prop_batter_hits":   PROP_BATTER_HITS_FEATURES,
    "mlb_prop_batter_tb":     PROP_BATTER_TB_FEATURES,
    "mlb_prop_batter_hr":     PROP_BATTER_HR_FEATURES,
    "mlb_prop_batter_rbi":    PROP_BATTER_RBI_FEATURES,
    "mlb_prop_batter_runs":   PROP_BATTER_RUNS_FEATURES,
    "mlb_prop_batter_sb":     PROP_BATTER_SB_FEATURES,
    "mlb_prop_batter_walks":  PROP_BATTER_WALKS_FEATURES,
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
               'p_strikeouts', 'innings_pitched', 'p_walks', 'p_hits_allowed', 'p_earned_runs']
    gl_rows = conn.execute("""
        SELECT player_id, player_name, team, game_id, game_date, season,
               p_strikeouts, innings_pitched, p_walks, p_hits_allowed, p_earned_runs
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
        d['outs']   = round(d['ip_dec'] * 3) if d['ip_dec'] is not None else None
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

    # ── Team stats (opponent batting quality for all pitcher prop models) ──────
    # woba and bb_pct are used by hits/ER/walks models in addition to k_pct.
    ts_cols = ['team', 'season', 'as_of_date', 'k_pct', 'woba', 'bb_pct']
    ts_rows = conn.execute(f"""
        SELECT team, season, as_of_date, k_pct, woba, bb_pct
        FROM mlb_team_stats
        WHERE season IN ({sp_load})
        ORDER BY team, season, as_of_date
    """, load_seasons).fetchall()

    # (team, season) → (sorted_dates, stat_dicts)
    # stat_dicts[i] holds {k_pct, woba, bb_pct} for the i-th snapshot date.
    team_stats: dict = {}
    for r in ts_rows:
        d = dict(zip(ts_cols, r))
        k = (d['team'], d['season'])
        if k not in team_stats:
            team_stats[k] = ([], [])
        team_stats[k][0].append(d['as_of_date'])
        team_stats[k][1].append({
            'k_pct':  d['k_pct'],
            'woba':   d['woba'],
            'bb_pct': d['bb_pct'],
        })

    # ── Opponent plate discipline: team avg batter chase% (season-level) ──────
    # player_savant_stats.team is NULL for batters, so map batters→teams via the
    # game log (our abbrevs) and join Savant chase by player_id+season. Season-level
    # constant per (team, season); prior-season fallback handled at lookup time.
    tc_rows = conn.execute(f"""
        SELECT gl.team, gl.season, AVG(sv.chase_pct) AS chase
        FROM (SELECT DISTINCT player_id, team, season
              FROM player_game_log
              WHERE player_type = 'batter' AND season IN ({sp_load})) gl
        JOIN player_savant_stats sv
          ON sv.player_id = gl.player_id AND sv.season = gl.season
         AND sv.player_type = 'batter'
        WHERE sv.chase_pct IS NOT NULL
        GROUP BY gl.team, gl.season
    """, load_seasons).fetchall()
    team_chase: dict = {(r[0], r[1]): r[2] for r in tc_rows}
    _chase_vals = [v for v in team_chase.values() if v is not None]
    league_chase = sum(_chase_vals) / len(_chase_vals) if _chase_vals else None

    # ── Weather (include venue for park factor lookup in ER model) ────────────
    w_rows = conn.execute("""
        SELECT game_id, temp_f, is_dome_game, venue
        FROM game_weather
    """).fetchall()
    weather: dict = {r[0]: {'temp_f': r[1], 'is_dome_game': r[2], 'venue': r[3]}
                     for r in w_rows}

    # ── Games (home/away team lookup for opponent derivation) ─────────────────
    g_rows = conn.execute(f"""
        SELECT game_id, home_team, away_team
        FROM games
        WHERE sport = 'MLB'
          AND season IN ({sp_all})
    """, all_seasons).fetchall()
    games: dict = {r[0]: {'home_team': r[1], 'away_team': r[2]} for r in g_rows}

    # ── Umpire assignments + per-game k_plus_minus ───────────────────────────
    # Load HP umpire per game, then compute k_plus_minus from the pitcher_logs
    # already in memory (no extra DB join needed).
    u_rows = conn.execute("""
        SELECT game_id, umpire_name FROM umpires WHERE umpire_name IS NOT NULL
    """).fetchall()
    ump_by_game: dict = {r[0]: r[1] for r in u_rows}

    # Build game_id → average starting pitcher K for that game (both starters)
    _game_k: dict = {}
    for pid, (_, logs) in pitcher_logs.items():
        for log in logs:
            k = log.get('p_strikeouts')
            if k is not None:
                _game_k.setdefault(log['game_id'], []).append(k)
    game_avg_k: dict = {gid: sum(ks) / len(ks) for gid, ks in _game_k.items() if ks}

    # Per-umpire average K per game (career, over all logged games)
    _ump_ks: dict = {}
    for gid, ump in ump_by_game.items():
        if gid in game_avg_k:
            _ump_ks.setdefault(ump, []).append(game_avg_k[gid])
    ump_k_pg: dict = {u: sum(v) / len(v) for u, v in _ump_ks.items() if v}

    # League average K per game across all umpire-covered games
    _all_k = [v for vals in _ump_ks.values() for v in vals]
    _league_avg_k = sum(_all_k) / len(_all_k) if _all_k else 5.5

    # game_id → k_plus_minus  (umpire_avg − league_avg)
    ump_k_pm: dict = {
        gid: ump_k_pg[ump] - _league_avg_k
        for gid, ump in ump_by_game.items()
        if ump in ump_k_pg
    }

    # ── Umpire walk tendency (ASOF) for the walks model ──────────────────────
    # Per-game average starter walks, an umpire's date-sorted series of those, plus
    # a career fallback. The feature (_ump_bb_plus_minus) averages only the umpire's
    # games strictly BEFORE the scored game's date — no look-ahead. The career
    # fallback keeps it non-null for an umpire's first few games so rows aren't
    # dropped by the null-feature filter in build_prop_training_dataset.
    _game_date_map: dict = {}
    _game_bb: dict = {}
    for _pid, (_, _logs) in pitcher_logs.items():
        for _log in _logs:
            _gid = _log['game_id']
            _game_date_map.setdefault(_gid, _log['game_date'])
            _bb = _log.get('p_walks')
            if _bb is not None:
                _game_bb.setdefault(_gid, []).append(_bb)
    game_avg_bb: dict = {g: sum(v) / len(v) for g, v in _game_bb.items() if v}

    _ump_bb_pairs: dict = {}
    for gid, ump in ump_by_game.items():
        if gid in game_avg_bb and gid in _game_date_map:
            _ump_bb_pairs.setdefault(ump, []).append((_game_date_map[gid], game_avg_bb[gid]))
    ump_bb_series: dict = {}
    ump_bb_pg: dict = {}
    for ump, pairs in _ump_bb_pairs.items():
        pairs.sort()
        ump_bb_series[ump] = ([p[0] for p in pairs], [p[1] for p in pairs])
        ump_bb_pg[ump] = sum(p[1] for p in pairs) / len(pairs)
    _all_bb = [v for vals in _ump_bb_pairs.values() for (_, v) in vals]
    league_bb_avg = sum(_all_bb) / len(_all_bb) if _all_bb else 1.5

    logger.debug(
        f"Bulk loads: {len(gl_rows)} pitcher starts, {len(sv_rows)} savant rows, "
        f"{len(ts_rows)} team-stat rows, {len(w_rows)} weather rows, {len(g_rows)} games, "
        f"{len(u_rows)} umpire assignments ({len(ump_k_pg)} unique umpires)"
    )

    return dict(
        pitcher_logs=pitcher_logs,
        savant=savant,
        team_stats=team_stats,
        weather=weather,
        games=games,
        ump_k_pm=ump_k_pm,
        ump_by_game=ump_by_game,
        ump_bb_series=ump_bb_series,
        ump_bb_pg=ump_bb_pg,
        league_bb_avg=league_bb_avg,
        team_chase=team_chase,
        league_chase=league_chase,
    )


# ── Per-Row Feature Builders ───────────────────────────────────────────────────

def _pitcher_rolling_all(bulk: dict, player_id: str, game_date: str, season: int) -> dict:
    """
    Rolling pitcher stats for ALL prop targets (K, hits, ER, walks, outs) computed
    in one pass from prior starts strictly before game_date.
    Uses true decimal IP for rate calculations.
    Returns empty dict if no prior starts exist.
    """
    if player_id not in bulk['pitcher_logs']:
        return {}

    dates, rows = bulk['pitcher_logs'][player_id]
    cutoff = bisect.bisect_left(dates, game_date)
    prior = rows[:cutoff]

    if not prior:
        return {}

    def _avg_window(field: str, n: int) -> float | None:
        window = prior[-n:]
        if len(window) < n:
            return None
        vals = [r[field] for r in window if r[field] is not None]
        return round(float(np.mean(vals)), 3) if vals else None

    def _rate(num_field: str, n: int) -> float | None:
        """num_field per true inning over last n starts."""
        window = prior[-n:]
        if len(window) < n:
            return None
        num = sum(r[num_field] for r in window if r[num_field] is not None)
        den = sum(r['ip_dec'] for r in window if r['ip_dec'] is not None)
        return round(num / den, 3) if den else None

    def _season_avg(field: str) -> float | None:
        """Season-to-date avg, with prior-season fallback for season openers."""
        for s in (season, season - 1):
            s_rows = [r for r in prior if r['season'] == s]
            if s_rows:
                vals = [r[field] for r in s_rows if r[field] is not None]
                return round(float(np.mean(vals)), 3) if vals else None
        return None

    def _trend(last3_val: float | None, season_val: float | None) -> float | None:
        if last3_val is None or season_val is None:
            return None
        return round(last3_val - season_val, 3)

    # ── Pre-compute shared last3 and season values for trend calc ──────────────
    k3     = _avg_window('p_strikeouts', 3)
    h3     = _avg_window('p_hits_allowed', 3)
    er3    = _avg_window('p_earned_runs', 3)
    w3     = _avg_window('p_walks', 3)
    outs3  = _avg_window('outs', 3)

    k_s    = _season_avg('p_strikeouts')
    h_s    = _season_avg('p_hits_allowed')
    er_s   = _season_avg('p_earned_runs')
    w_s    = _season_avg('p_walks')
    outs_s = _season_avg('outs')

    return {
        # ── K ───────────────────────────────────────────────────────────────
        'k_last3_avg':     k3,
        'k_last5_avg':     _avg_window('p_strikeouts', 5),
        'k_last10_avg':    _avg_window('p_strikeouts', 10),
        'k_rate_last3':    _rate('p_strikeouts', 3),
        'k_rate_last5':    _rate('p_strikeouts', 5),
        'ip_last3_avg':    _avg_window('ip_dec', 3),
        'ip_last5_avg':    _avg_window('ip_dec', 5),
        'season_k_avg':    k_s,
        'k_trend':         _trend(k3, k_s),
        # ── Hits allowed ────────────────────────────────────────────────────
        'hits_last3_avg':  h3,
        'hits_last5_avg':  _avg_window('p_hits_allowed', 5),
        'hits_last10_avg': _avg_window('p_hits_allowed', 10),
        'hit_rate_last3':  _rate('p_hits_allowed', 3),
        'season_hits_avg': h_s,
        'hits_trend':      _trend(h3, h_s),
        # ── Earned runs ─────────────────────────────────────────────────────
        'er_last3_avg':    er3,
        'er_last5_avg':    _avg_window('p_earned_runs', 5),
        'er_last10_avg':   _avg_window('p_earned_runs', 10),
        'er_rate_last3':   _rate('p_earned_runs', 3),
        'season_er_avg':   er_s,
        'er_trend':        _trend(er3, er_s),
        # ── Walks ───────────────────────────────────────────────────────────
        'walks_last3_avg': w3,
        'walks_last5_avg': _avg_window('p_walks', 5),
        'walks_last10_avg': _avg_window('p_walks', 10),
        'bb_rate_last3':   _rate('p_walks', 3),
        'season_walks_avg': w_s,
        'walks_trend':     _trend(w3, w_s),
        # ── Outs recorded ───────────────────────────────────────────────────
        'outs_last3_avg':  outs3,
        'outs_last5_avg':  _avg_window('outs', 5),
        'outs_last10_avg': _avg_window('outs', 10),
        'season_outs_avg': outs_s,
        'outs_trend':      _trend(outs3, outs_s),
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


def _opp_team_stat(bulk: dict, opp_team: str, season: int,
                   game_date: str, stat_key: str) -> float | None:
    """
    ASOF bisect lookup for any team batting stat (k_pct, woba, bb_pct).
    Falls back to prior season if current season has no rows yet.
    """
    ts = bulk['team_stats']
    for s in (season, season - 1):
        key = (opp_team, s)
        if key in ts:
            dates, stat_dicts = ts[key]
            idx = bisect.bisect_right(dates, game_date) - 1
            if idx >= 0:
                return stat_dicts[idx].get(stat_key)
    return None


def _opp_team_chase(bulk: dict, opp_team: str, season: int) -> float | None:
    """
    Opponent lineup average batter chase% (season-level, prior-season fallback).
    Lower chase = more patient lineup = more walks drawn off the pitcher.
    """
    tc = bulk.get('team_chase', {})
    for s in (season, season - 1):
        v = tc.get((opp_team, s))
        if v is not None:
            return v
    # Fall back to league-average chase so a single missing team-season doesn't
    # null-drop the row; returns None only if chase is unpopulated everywhere.
    return bulk.get('league_chase')


def _ump_bb_plus_minus(bulk: dict, game_id: str, game_date: str,
                       min_prior: int = 3) -> float | None:
    """
    Home-plate umpire walk tendency vs league = (umpire avg starter walks − league avg).
    ASOF: averages only the umpire's games strictly before game_date (no look-ahead).
    Falls back to the umpire's career average when fewer than `min_prior` prior games
    exist so the feature stays non-null (rows aren't dropped). None only when the
    umpire is unknown for this game (not yet announced / not in the umpires table).
    """
    ump = bulk.get('ump_by_game', {}).get(game_id)
    if ump is None:
        return None
    league = bulk.get('league_bb_avg', 1.5)
    series = bulk.get('ump_bb_series', {}).get(ump)
    if series:
        dates, vals = series
        cut = bisect.bisect_left(dates, game_date)   # entries strictly before game_date
        if cut >= min_prior:
            return sum(vals[:cut]) / cut - league
    career = bulk.get('ump_bb_pg', {}).get(ump)
    if career is not None:
        return career - league
    return None


def _build_pitcher_row(bulk: dict,
                       player_id: str, player_name: str,
                       team: str, game_id: str, game_date: str,
                       season: int, targets: dict | None,
                       training_mode: bool = True) -> dict | None:
    """
    Build a comprehensive feature row covering all pitcher prop models.
    Includes rolling stats for K, hits, ER, walks, and outs in one pass.

    targets: dict with keys target_k/target_hits/target_er/target_walks/target_outs,
             or None at scoring time.
    Returns None if game_id not in games table (e.g. Tokyo Series).
    """
    game_info = bulk['games'].get(game_id)
    if not game_info:
        return None

    opp_team = (game_info['away_team']
                if team == game_info['home_team']
                else game_info['home_team'])

    rolling = _pitcher_rolling_all(bulk, player_id, game_date, season)
    savant  = _pitcher_savant(bulk, player_id, season, training_mode)
    weather = bulk['weather'].get(game_id, {})

    venue       = weather.get('venue', '') or ''
    park_hr_fac = PARK_HR_FACTORS.get(venue, 1.0)

    row = {
        # Metadata (excluded from model features)
        'player_id':   player_id,
        'player_name': player_name,
        'team':        team,
        'opp_team':    opp_team,
        'game_id':     game_id,
        'game_date':   game_date,
        'season':      season,
        # Rolling stats (all models share the same bulk compute)
        **rolling,
        # Savant pitcher metrics
        **savant,
        # Opponent batting quality (ASOF)
        'opp_team_k_pct':  _opp_team_stat(bulk, opp_team, season, game_date, 'k_pct'),
        'opp_team_woba':   _opp_team_stat(bulk, opp_team, season, game_date, 'woba'),
        'opp_team_bb_pct': _opp_team_stat(bulk, opp_team, season, game_date, 'bb_pct'),
        # Park and environment
        'park_hr_factor':   park_hr_fac,
        'is_dome_game':     int(weather.get('is_dome_game') or 0),
        'temp_f':           weather.get('temp_f'),
        # Umpire — k_plus_minus is None if umpire not yet announced or not in table
        'ump_k_plus_minus': bulk.get('ump_k_pm', {}).get(game_id),
        # Umpire walk tendency (ASOF, career fallback) — walks model
        'ump_bb_plus_minus': _ump_bb_plus_minus(bulk, game_id, game_date),
        # Opponent plate discipline (season-level) — walks model
        'opp_team_chase_pct': _opp_team_chase(bulk, opp_team, season),
    }

    if targets is not None:
        row.update(targets)

    return row


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

    _PITCHER_MODELS = (
        'mlb_prop_pitcher_k', 'mlb_prop_pitcher_hits', 'mlb_prop_pitcher_er',
        'mlb_prop_pitcher_outs', 'mlb_prop_pitcher_walks',
    )
    _PITCHER_TARGET = {
        'mlb_prop_pitcher_k':     'target_k',
        'mlb_prop_pitcher_hits':  'target_hits',
        'mlb_prop_pitcher_er':    'target_er',
        'mlb_prop_pitcher_outs':  'target_outs',
        'mlb_prop_pitcher_walks': 'target_walks',
    }
    _BATTER_MODELS = (
        'mlb_prop_batter_hits', 'mlb_prop_batter_tb', 'mlb_prop_batter_hr',
        'mlb_prop_batter_rbi',  'mlb_prop_batter_runs',
        'mlb_prop_batter_sb',   'mlb_prop_batter_walks',
    )
    _BATTER_TARGET = {
        'mlb_prop_batter_hits':  'target_hits',
        'mlb_prop_batter_tb':    'target_tb',
        'mlb_prop_batter_hr':    'target_hr',
        'mlb_prop_batter_rbi':   'target_rbi',
        'mlb_prop_batter_runs':  'target_runs',
        'mlb_prop_batter_sb':    'target_sb',
        'mlb_prop_batter_walks': 'target_walks',
    }

    if model_id in _PITCHER_MODELS:
        conn = get_connection()
        bulk = _build_bulk_prop_lookups(conn, seasons)
        conn.close()
        raw_rows = _all_pitcher_rows(bulk, seasons, training_mode=True)
        target_col = _PITCHER_TARGET[model_id]
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
    df = df.dropna(subset=num_cols + ['target'])   # also drop null targets
    dropped = before - len(df)
    if dropped:
        logger.info(f"  Dropped {dropped}/{before} rows with null features/target "
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


def _all_pitcher_rows(bulk: dict, seasons: list[int],
                      training_mode: bool) -> list[dict]:
    """
    Iterate all pitcher starts in the requested seasons and build comprehensive
    feature rows covering every pitcher prop target (K, hits, ER, walks, outs).
    build_prop_training_dataset selects the appropriate target column per model.
    """
    season_set = set(seasons)
    rows = []
    skipped_no_game = 0

    for player_id, (dates, log_rows) in bulk['pitcher_logs'].items():
        for log in log_rows:
            if log['season'] not in season_set:
                continue

            targets = {
                'target_k':     log['p_strikeouts'],
                'target_hits':  log['p_hits_allowed'],
                'target_er':    log['p_earned_runs'],
                'target_walks': log['p_walks'],
                'target_outs':  log['outs'],
            }

            row = _build_pitcher_row(
                bulk,
                player_id=log['player_id'],
                player_name=log['player_name'],
                team=log['team'],
                game_id=log['game_id'],
                game_date=log['game_date'],
                season=log['season'],
                targets=targets,
                training_mode=training_mode,
            )
            if row is None:
                skipped_no_game += 1
            else:
                rows.append(row)

    if skipped_no_game:
        logger.debug(f"  Skipped {skipped_no_game} starts: game_id not in games table")

    logger.info(f"Built {len(rows)} pitcher candidate rows")
    return rows


# ── Scoring Row Builder (daily pipeline) ───────────────────────────────────────

def build_pitcher_scoring_rows(model_id: str,
                               game_date: str,
                               pitchers: list[dict]) -> pd.DataFrame:
    """
    Build pitcher feature rows for today's probable starters for any pitcher prop model.

    Args:
        model_id:  e.g. 'mlb_prop_pitcher_k', 'mlb_prop_pitcher_hits', etc.
        game_date: YYYY-MM-DD scoring date
        pitchers:  list of dicts with keys: player_id, player_name, team, game_id

    player_game_log is NOT used for today's entries (those don't exist pre-game).
    Rolling stats use historical log rows strictly before game_date via bisect.

    Returns DataFrame with feature columns for model_id. Missing features left as
    NaN — scorer fills with 0.0 and logs affected pitchers.
    """
    if not pitchers:
        return pd.DataFrame()

    feature_cols = PROP_FEATURE_MAP.get(model_id, [])
    season = int(game_date[:4])
    conn = get_connection()
    bulk = _build_bulk_prop_lookups(conn, [season])
    conn.close()

    rows = []
    for p in pitchers:
        row = _build_pitcher_row(
            bulk,
            player_id=p['player_id'],
            player_name=p['player_name'],
            team=p['team'],
            game_id=p['game_id'],
            game_date=game_date,
            season=season,
            targets=None,         # no target at scoring time
            training_mode=False,  # use current season savant with prior fallback
        )
        if row is not None:
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
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
    Build a single batter feature row covering all seven batter prop models
    (hits, TB, HR, RBI, runs, SB, walks). The caller selects the right target
    column and feature subset via build_prop_training_dataset or
    build_batter_scoring_rows.

    log_row must contain at minimum: batting_order, hits, total_bases,
    home_runs, rbi, runs, stolen_bases, walks, at_bats (from player_game_log
    or lineup_slots at score time).
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
    batter_hand     = None   # init here — referenced in return dict regardless of opp_starter_id
    pitcher_hand    = None
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

    # ── Rolling stats for new batter prop models ──────────────────────────────
    rbi5     = _batter_rolling_avg(bulk, player_id, game_date, 'rbi', 5)
    rbi10    = _batter_rolling_avg(bulk, player_id, game_date, 'rbi', 10)
    s_rbi    = _batter_season_avg(bulk, player_id, game_date, season, 'rbi')

    runs5    = _batter_rolling_avg(bulk, player_id, game_date, 'runs', 5)
    runs10   = _batter_rolling_avg(bulk, player_id, game_date, 'runs', 10)
    s_runs   = _batter_season_avg(bulk, player_id, game_date, season, 'runs')

    sb10     = _batter_rolling_avg(bulk, player_id, game_date, 'stolen_bases', 10)
    sb20     = _batter_rolling_avg(bulk, player_id, game_date, 'stolen_bases', 20)
    s_sb     = _batter_season_avg(bulk, player_id, game_date, season, 'stolen_bases')

    walks5   = _batter_rolling_avg(bulk, player_id, game_date, 'walks', 5)
    walks10  = _batter_rolling_avg(bulk, player_id, game_date, 'walks', 10)
    s_walks  = _batter_season_avg(bulk, player_id, game_date, season, 'walks')

    rbi_trend   = (round(rbi5 - s_rbi, 3)
                   if rbi5 is not None and s_rbi is not None else None)
    runs_trend  = (round(runs5 - s_runs, 3)
                   if runs5 is not None and s_runs is not None else None)
    walks_trend = (round(walks5 - s_walks, 3)
                   if walks5 is not None and s_walks is not None else None)

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
        'target_hits':  log_row.get('hits')          if log_row else None,
        'target_tb':    log_row.get('total_bases')   if log_row else None,
        'target_hr':    log_row.get('home_runs')     if log_row else None,
        'target_rbi':   log_row.get('rbi')           if log_row else None,
        'target_runs':  log_row.get('runs')          if log_row else None,
        'target_sb':    log_row.get('stolen_bases')  if log_row else None,
        'target_walks': log_row.get('walks')         if log_row else None,
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
        # ── RBI features ─────────────────────────────────────────────────────
        'rbi_last5_avg':    rbi5,
        'rbi_last10_avg':   rbi10,
        'season_rbi_avg':   s_rbi,
        'rbi_trend':        rbi_trend,
        # ── Runs features ─────────────────────────────────────────────────────
        'runs_last5_avg':   runs5,
        'runs_last10_avg':  runs10,
        'season_runs_avg':  s_runs,
        'runs_trend':       runs_trend,
        # ── SB features ───────────────────────────────────────────────────────
        'sb_last10_avg':    sb10,
        'sb_last20_avg':    sb20,
        'season_sb_avg':    s_sb,
        # ── Batter walks features ─────────────────────────────────────────────
        'walks_last5_avg':  walks5,
        'walks_last10_avg': walks10,
        'season_walks_avg': s_walks,
        'walks_trend':      walks_trend,
        # ── Opposing starter (HR model v2) ────────────────────────────────────
        'opp_starter_hr9':       opp_hr9,
        'opp_starter_hr9_last3': opp_hr9_last3,
        'opp_starter_gb_pct':    opp_gb,
        # ── Park and platoon (HR model v2) ────────────────────────────────────
        'park_hr_factor':     park_hr_factor,
        'platoon_advantage':  platoon_adv,
        'bat_hand':           batter_hand,      # metadata — for website display
        'pitcher_throw_hand': pitcher_hand,     # metadata — for website display
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
                 'game_id', 'game_date', 'season', 'batting_order',
                 'bat_hand', 'pitcher_throw_hand']
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
