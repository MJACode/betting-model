# NFL Game Lines Model System

> **DOCUMENT STATUS — last revised 2026-08-15**
>
> Three claims in this document were corrected by the Open-Meteo validation run
> and the clean opener re-test. Superseded passages are marked inline with
> **[SUPERSEDED]**. Index of changes:
>
> | Section | Was | Now |
> |---|---|---|
> | Forecast Leakage Is Handled | Open-Meteo archives issued forecasts from 2022; needs allowlisting | Issued forecasts (`previous_dayN`) start **2024-01-18**, not 2022. Endpoint validated. Rule holds at **57.09%** under real day-3 forecast error |
> | Known Gaps #4 | Weather excluded, no forecast-at-cutoff source | Resolved. Forecast wind is in production via `models/wind_totals.py` |
> | Impact 2: Opener | +8.38% ROI at -110 | **+6.98% at actual quoted prices**, 95% CI [-0.6, +14.5]. Books charge for the better number |
> | (new) Source agreement | nflverse `wind` treated as truth | nflverse and ERA5 correlate only **0.688**. The rule survives on both, so the effect is physical, not a data artifact |
>
> Operational code: `scripts/weekly_wind_card.py` (live card),
> `scripts/replay_wind_card.py` (regression test), `scripts/validate_wind_forecast.py`
> (all wind numbers), `scripts/screen_books.py` (integrity screen),
> `scripts/backtest_opener.py` (opener, correctly priced).
> The weekly routine is in **Runbook: Wind Totals** at the end of this document.


## Architecture Overview

Three interconnected pre-game models form the game lines subsystem:

1. **Spread Model**: Regression on margin of victory, LightGBM + Ridge meta-learner
2. **Moneyline Model**: Derived from spread output via fitted sigmoid, not independently trained
3. **Game Totals Model**: Regression on combined score, same ensemble architecture

The spread model is the anchor. Its output feeds both the moneyline derivation and the totals model (as an implied competitiveness feature). Team totals for each side are then computed from the combination of spread and total outputs, which propagate downstream into player props models.

```
Spread Model (margin)
  ├── Moneyline Derivation (sigmoid transform)
  ├── Game Totals Model (total points, consumes spread output)
  └── Team Totals = (Total ± Spread) / 2
        └── Player Props Models (downstream)
```

---

## 1A. Spread Model

### Target Variable

`margin = home_score - away_score`

Continuous regression target. Positive values indicate a home win. This aligns directly with the betting market convention where a home spread of -3.5 implies an expected margin of approximately +3.5 for the home team.

### Feature Engineering Pipeline

#### Category 1: Efficiency Metrics (EPA-Based)

Source: nflverse play-by-play via `nfl_data_py`

```python
import nfl_data_py as nfl
import pandas as pd
import numpy as np

def build_epa_features(seasons: list[int]) -> pd.DataFrame:
    """
    Build rolling and season-to-date EPA features per team per game.
    Uses only data available before each game (no leakage).
    """
    pbp = nfl.import_pbp_data(seasons)
    
    # Filter to meaningful plays
    plays = pbp[
        (pbp['play_type'].isin(['pass', 'run'])) &
        (pbp['epa'].notna()) &
        (pbp['aborted_play'] == 0)
    ].copy()
    
    # Offensive EPA per play, grouped by team and game
    off_epa = (
        plays.groupby(['posteam', 'game_id', 'season', 'week'])
        .agg(
            off_epa_play=('epa', 'mean'),
            off_epa_pass=('epa', lambda x: x[plays.loc[x.index, 'play_type'] == 'pass'].mean()),
            off_epa_run=('epa', lambda x: x[plays.loc[x.index, 'play_type'] == 'run'].mean()),
            off_pass_rate=('play_type', lambda x: (x == 'pass').mean()),
            off_plays=('epa', 'count'),
        )
        .reset_index()
    )
    
    # Defensive EPA per play (defteam perspective)
    def_epa = (
        plays.groupby(['defteam', 'game_id', 'season', 'week'])
        .agg(
            def_epa_play=('epa', 'mean'),
            def_epa_pass=('epa', lambda x: x[plays.loc[x.index, 'play_type'] == 'pass'].mean()),
            def_epa_run=('epa', lambda x: x[plays.loc[x.index, 'play_type'] == 'run'].mean()),
        )
        .reset_index()
        .rename(columns={'defteam': 'team'})
    )
    
    # Sort by season and week for rolling calculations
    off_epa = off_epa.sort_values(['posteam', 'season', 'week'])
    
    # Rolling 4-game window (shift(1) prevents leakage: current game excluded)
    for col in ['off_epa_play', 'off_epa_pass', 'off_epa_run']:
        off_epa[f'{col}_roll4'] = (
            off_epa.groupby('posteam')[col]
            .transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
        )
        off_epa[f'{col}_szn'] = (
            off_epa.groupby(['posteam', 'season'])[col]
            .transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
        )
    
    return off_epa  # Similarly for def_epa
```

Key details:
- `shift(1)` on every rolling/expanding calculation ensures the current game's data is never included
- Rolling window of 4 games captures recent form; season-to-date captures baseline
- Both pass and run splits are needed because defensive matchups are phase-specific
- `min_periods=2` on rolling prevents noisy single-game estimates early in season

#### Category 2: PFF Advanced Metrics

Source: PFF Premium Stats API or CSV exports

Features to extract per team per week (always shifted by one week to prevent leakage):

| Feature | Description | Granularity |
|---|---|---|
| `pff_off_grade` | Overall offensive grade | Rolling 4 + STD |
| `pff_def_grade` | Overall defensive grade | Rolling 4 + STD |
| `pff_pass_block_wr` | Pass block win rate | Rolling 4 |
| `pff_pressure_rate` | Pressure rate allowed (offense) | Rolling 4 |
| `pff_adj_line_yards` | Adjusted line yards (run blocking quality) | Rolling 4 |
| `pff_coverage_grade` | Secondary coverage grade | Rolling 4 |
| `pff_run_def_grade` | Run defense grade | Rolling 4 |
| `pff_st_grade` | Special teams grade | Season-to-date |
| `pff_recv_yac_grade` | Receiver YAC grade | Rolling 4 |

```python
def build_pff_features(pff_weekly: pd.DataFrame) -> pd.DataFrame:
    """
    pff_weekly has columns: team, season, week, and all PFF grade columns.
    All features are lagged by 1 week.
    """
    pff_weekly = pff_weekly.sort_values(['team', 'season', 'week'])
    
    grade_cols = [c for c in pff_weekly.columns if c.startswith('pff_')]
    
    for col in grade_cols:
        pff_weekly[f'{col}_roll4'] = (
            pff_weekly.groupby('team')[col]
            .transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
        )
        pff_weekly[f'{col}_szn'] = (
            pff_weekly.groupby(['team', 'season'])[col]
            .transform(lambda s: s.shift(1).expanding(min_periods=1).mean())
        )
    
    return pff_weekly
```

#### Category 3: Rest and Schedule Context

```python
def build_schedule_features(schedule: pd.DataFrame) -> pd.DataFrame:
    """
    schedule has: game_id, season, week, home_team, away_team, gameday (date),
    gametime, location, div_game, roof, surface
    """
    schedule = schedule.sort_values(['season', 'week'])
    
    # Rest days: compute days since last game for each team
    def calc_rest(team_col):
        team_games = schedule[['game_id', 'season', 'week', team_col, 'gameday']].copy()
        team_games = team_games.rename(columns={team_col: 'team'})
        team_games['gameday'] = pd.to_datetime(team_games['gameday'])
        team_games = team_games.sort_values(['team', 'gameday'])
        team_games['rest_days'] = team_games.groupby('team')['gameday'].diff().dt.days
        return team_games[['game_id', 'team', 'rest_days']]
    
    home_rest = calc_rest('home_team').rename(columns={'rest_days': 'home_rest_days'})
    away_rest = calc_rest('away_team').rename(columns={'rest_days': 'away_rest_days'})
    
    schedule = schedule.merge(home_rest, left_on=['game_id', 'home_team'],
                               right_on=['game_id', 'team'], how='left')
    schedule = schedule.merge(away_rest, left_on=['game_id', 'away_team'],
                               right_on=['game_id', 'team'], how='left')
    
    # Derived features
    schedule['rest_diff'] = schedule['home_rest_days'] - schedule['away_rest_days']
    schedule['home_short_week'] = (schedule['home_rest_days'] <= 5).astype(int)
    schedule['away_short_week'] = (schedule['away_rest_days'] <= 5).astype(int)
    schedule['home_bye_week_prior'] = (schedule['home_rest_days'] >= 12).astype(int)
    schedule['away_bye_week_prior'] = (schedule['away_rest_days'] >= 12).astype(int)
    
    # Timezone travel (requires a team-to-timezone mapping)
    tz_map = {
        'SEA': -8, 'SF': -8, 'LAR': -8, 'LAC': -8,
        'ARI': -7, 'DEN': -7, 'LV': -8,
        'KC': -6, 'DAL': -6, 'HOU': -6, 'MIN': -6,
        'GB': -6, 'CHI': -6, 'NO': -6, 'TEN': -6,
        'IND': -5, 'JAX': -5, 'CLE': -5, 'CIN': -5,
        'DET': -5, 'ATL': -5, 'CAR': -5, 'TB': -5,
        'PIT': -5, 'BAL': -5, 'WAS': -5, 'PHI': -5,
        'NYG': -5, 'NYJ': -5, 'NE': -5, 'MIA': -5,
        'BUF': -5,
    }
    schedule['tz_diff'] = (
        schedule['away_team'].map(tz_map).fillna(-6) -
        schedule['home_team'].map(tz_map).fillna(-6)
    ).abs()
    schedule['cross_country'] = (schedule['tz_diff'] >= 3).astype(int)
    
    return schedule
```

#### Category 4: Home Field Advantage (Learned Parameter)

Do not hard-code a fixed 2.5 or 3-point home field advantage. Instead, treat it as a learned, team-specific, time-varying parameter.

```python
def build_hfa_features(games: pd.DataFrame) -> pd.DataFrame:
    """
    Build a rolling home-field advantage estimate per team.
    games has: game_id, season, week, home_team, away_team, margin (home - away)
    """
    # League-wide rolling HFA
    home_games = games.sort_values(['season', 'week'])
    home_games['league_hfa_roll'] = (
        home_games['margin']
        .shift(1)
        .expanding(min_periods=50)
        .mean()
    )
    
    # Team-specific HFA: rolling home margin vs neutral expectation
    # This captures crowd noise differences (SEA, KC vs JAX)
    home_games['team_home_margin_roll'] = (
        home_games.groupby('home_team')['margin']
        .transform(lambda s: s.shift(1).rolling(16, min_periods=8).mean())
    )
    
    # Interaction features
    # Altitude advantage (DEN)
    home_games['dome_game'] = home_games['roof'].isin(['dome', 'closed']).astype(int)
    home_games['altitude_game'] = (home_games['home_team'] == 'DEN').astype(int)
    
    return home_games
```

The model itself will learn the HFA weight from the data rather than us injecting a fixed intercept.

#### Category 5: Weather

Source: OpenWeather API or WeatherAPI, keyed to stadium GPS coordinates

```python
from dataclasses import dataclass

@dataclass
class StadiumWeather:
    wind_mph: float
    temp_f: float
    precip_prob: float  # 0 to 1
    is_dome: bool

def build_weather_features(weather: StadiumWeather) -> dict:
    """
    Returns weather feature dict for a single game.
    Dome games get neutral weather values.
    """
    if weather.is_dome:
        return {
            'wind_mph': 0.0,
            'temp_f': 72.0,
            'precip_prob': 0.0,
            'extreme_cold': 0,
            'extreme_wind': 0,
            'precip_flag': 0,
        }
    
    return {
        'wind_mph': weather.wind_mph,
        'temp_f': weather.temp_f,
        'precip_prob': weather.precip_prob,
        'extreme_cold': int(weather.temp_f < 25),
        'extreme_wind': int(weather.wind_mph > 18),
        'precip_flag': int(weather.precip_prob > 0.5),
    }
```

Important: dome games must be zeroed out for weather features. Otherwise the model learns a spurious correlation between dome teams' performance and neutral weather readings.

#### Category 6: Market Signals

Source: ActionNetwork (sharp money, public %), The Odds API (opening/current lines)

```python
def build_market_features(odds_data: pd.DataFrame) -> pd.DataFrame:
    """
    odds_data has: game_id, open_spread, current_spread, sharp_pct,
    public_pct_home, total_handle_pct_home
    """
    odds_data['line_move'] = odds_data['current_spread'] - odds_data['open_spread']
    odds_data['line_move_abs'] = odds_data['line_move'].abs()
    
    # Reverse line movement: public on one side, line moves other way
    odds_data['reverse_line_move'] = (
        ((odds_data['public_pct_home'] > 60) & (odds_data['line_move'] > 0)) |
        ((odds_data['public_pct_home'] < 40) & (odds_data['line_move'] < 0))
    ).astype(int)
    
    # Sharp vs public disagreement
    odds_data['sharp_public_disagree'] = (
        (odds_data['sharp_pct'] > 55) &
        (odds_data['public_pct_home'] > 55)
    ).astype(int)  # Both sides loaded = no signal
    
    # Sharp is on opposite side of public
    odds_data['sharp_fade_public'] = (
        ((odds_data['sharp_pct'] > 55) & (odds_data['public_pct_home'] > 55)) == False
    ).astype(int)
    
    return odds_data
```

**Critical note on market features**: The opening line and line movement are powerful predictive features because they embed the market's aggregate information. However, you must be careful about what "current line" means at prediction time. If you are predicting at a fixed cutoff (say, Tuesday evening), freeze the line at that moment. Do not use the closing line as a feature, because the closing line is only available after you would have placed your bet.

#### Category 7: Contextual Flags

```python
def build_context_features(schedule: pd.DataFrame, 
                           standings: pd.DataFrame) -> pd.DataFrame:
    """
    Binary and categorical flags for game context.
    """
    # Divisional game
    div_map = {
        'NFC East': ['DAL', 'NYG', 'PHI', 'WAS'],
        'NFC North': ['CHI', 'DET', 'GB', 'MIN'],
        # ... complete division mapping
    }
    team_to_div = {}
    for div, teams in div_map.items():
        for t in teams:
            team_to_div[t] = div
    
    schedule['div_game'] = (
        schedule['home_team'].map(team_to_div) == 
        schedule['away_team'].map(team_to_div)
    ).astype(int)
    
    # Playoff implications (both teams in contention after week 10)
    # Merge standings to determine if teams are within 2 games of division lead
    # or wildcard spot after week 10
    schedule['playoff_implications'] = 0  # Computed via standings merge
    
    # Revenge game: team lost to this opponent in prior meeting within 2 seasons
    # Requires historical game results lookup
    schedule['revenge_game'] = 0  # Computed via prior matchup lookup
    
    return schedule
```

#### Category 8: Coaching Matchup History

```python
def build_coaching_features(games: pd.DataFrame, 
                            coaches: pd.DataFrame) -> pd.DataFrame:
    """
    coaches has: team, season, week, head_coach
    Build head-to-head coaching record and tendencies.
    """
    # Merge coaches onto games
    games = games.merge(
        coaches.rename(columns={'head_coach': 'home_coach'}),
        on=['home_team', 'season', 'week'], how='left'
    )
    games = games.merge(
        coaches.rename(columns={'head_coach': 'away_coach'}),
        on=['away_team', 'season', 'week'], how='left'
    )
    
    # H2H record: for each coach pair, rolling win rate
    games['coach_matchup_key'] = (
        games[['home_coach', 'away_coach']]
        .apply(lambda r: tuple(sorted([r['home_coach'], r['away_coach']])), axis=1)
    )
    
    # Coach tenure (games coached with current team, proxy for system stability)
    games['home_coach_tenure'] = (
        games.groupby(['home_team', 'home_coach']).cumcount()
    )
    games['away_coach_tenure'] = (
        games.groupby(['away_team', 'away_coach']).cumcount()
    )
    
    return games
```

#### Category 9: Referee Assignment

Source: nflverse officials data or Pro Football Reference

```python
def build_referee_features(games: pd.DataFrame,
                           ref_data: pd.DataFrame) -> pd.DataFrame:
    """
    ref_data has: referee_name, game_id, total_penalties, total_penalty_yards
    Build referee tendencies that are available pre-game.
    """
    # Referee career averages (shift by 1 to exclude current game)
    ref_stats = (
        ref_data.sort_values(['referee_name', 'game_id'])
        .groupby('referee_name')
        .apply(lambda g: g.assign(
            ref_penalties_avg=g['total_penalties'].shift(1).expanding().mean(),
            ref_penalty_yards_avg=g['total_penalty_yards'].shift(1).expanding().mean(),
        ))
    )
    
    # Referee pace-of-play: average game duration or plays per game
    # (from play-by-play data)
    
    games = games.merge(ref_stats[['game_id', 'ref_penalties_avg', 'ref_penalty_yards_avg']],
                        on='game_id', how='left')
    
    return games
```

### Final Feature Matrix Assembly

```python
def assemble_spread_features(seasons: list[int]) -> pd.DataFrame:
    """
    Master function that joins all feature categories into a single
    game-level DataFrame ready for modeling.
    """
    schedule = nfl.import_schedules(seasons)
    games = build_base_games(schedule)
    
    # Build each feature group
    epa = build_epa_features(seasons)
    pff = build_pff_features(load_pff_data(seasons))
    sched = build_schedule_features(schedule)
    hfa = build_hfa_features(games)
    weather = fetch_and_build_weather(games)  # API call + transform
    market = build_market_features(load_odds_data(seasons))
    context = build_context_features(schedule, load_standings(seasons))
    coaches = build_coaching_features(games, load_coaches(seasons))
    refs = build_referee_features(games, load_ref_data(seasons))
    
    # Join all on game_id
    features = (
        games
        .pipe(merge_team_features, epa, 'home')
        .pipe(merge_team_features, epa, 'away')
        .pipe(merge_team_features, pff, 'home')
        .pipe(merge_team_features, pff, 'away')
        .merge(sched, on='game_id', how='left')
        .merge(hfa, on='game_id', how='left')
        .merge(weather, on='game_id', how='left')
        .merge(market, on='game_id', how='left')
        .merge(context, on='game_id', how='left')
        .merge(coaches, on='game_id', how='left')
        .merge(refs, on='game_id', how='left')
    )
    
    # Compute differentials (home minus away) for symmetric features
    diff_cols = [
        'off_epa_play_roll4', 'off_epa_play_szn',
        'def_epa_play_roll4', 'def_epa_play_szn',
        'pff_off_grade_roll4', 'pff_def_grade_roll4',
        'pff_pass_block_wr_roll4',
    ]
    for col in diff_cols:
        features[f'{col}_diff'] = features[f'home_{col}'] - features[f'away_{col}']
    
    # Target
    features['margin'] = features['home_score'] - features['away_score']
    
    return features
```

**Differential vs. raw features**: For most team-level stats, include both the differential (home minus away) and the raw values for each side. The differential captures the matchup edge directly. The raw values let the model learn non-linear interactions (a defense with a 0.15 EPA against a 0.20 offense is different from a -0.10 defense against a -0.05 offense, even though the differential is the same).

### Training Setup

#### Train/Test Split: Walk-Forward Validation

```python
from dataclasses import dataclass
from typing import Generator

@dataclass
class WalkForwardSplit:
    train_seasons: list[int]
    val_season: int
    test_season: int

def walk_forward_splits(
    all_seasons: list[int],
    min_train_seasons: int = 3,
    holdout_seasons: int = 2,
) -> Generator[WalkForwardSplit, None, None]:
    """
    Generate walk-forward splits.
    
    Example with seasons 2015-2024:
      Split 1: train=[2015,2016,2017], val=2018, test=2019
      Split 2: train=[2015,2016,2017,2018], val=2019, test=2020
      Split 3: train=[2015,...,2019], val=2020, test=2021
      ...
    
    The two-season holdout ensures val and test never overlap.
    """
    all_seasons = sorted(all_seasons)
    
    for i in range(min_train_seasons, len(all_seasons) - holdout_seasons + 1):
        train = all_seasons[:i]
        val = all_seasons[i]
        test = all_seasons[i + 1]
        yield WalkForwardSplit(train_seasons=train, val_season=val, test_season=test)
```

Why this matters: NFL has only ~285 games per season. With 10 seasons of data, you have roughly 2,850 samples. A single random train/test split would leak temporal patterns (line movement trends, rule changes, team roster evolution). Walk-forward respects the temporal ordering and simulates real deployment conditions.

#### Ensemble Architecture

```python
import lightgbm as lgb
from sklearn.linear_model import Ridge
from sklearn.model_selection import cross_val_predict
import numpy as np

class SpreadEnsemble:
    """
    Level 1: Multiple LightGBM models with different hyperparameters
    Level 2: Ridge regression meta-learner
    """
    
    def __init__(self, n_base_models: int = 5):
        self.n_base_models = n_base_models
        self.base_models: list[lgb.LGBMRegressor] = []
        self.meta_model = Ridge(alpha=1.0)
        self.feature_names: list[str] = []
    
    def fit(self, X_train: np.ndarray, y_train: np.ndarray,
            X_val: np.ndarray, y_val: np.ndarray,
            feature_names: list[str]):
        """
        Fit the stacked ensemble.
        
        Step 1: Train N base LightGBM models with varied hyperparameters
        Step 2: Generate out-of-fold predictions from base models
        Step 3: Train Ridge meta-learner on the stacked predictions
        """
        self.feature_names = feature_names
        
        # Base model hyperparameter grid (diversified)
        base_params_list = [
            {'n_estimators': 800, 'max_depth': 5, 'learning_rate': 0.03,
             'num_leaves': 31, 'subsample': 0.7, 'colsample_bytree': 0.7,
             'min_child_samples': 30, 'reg_alpha': 0.1, 'reg_lambda': 1.0},
            {'n_estimators': 600, 'max_depth': 4, 'learning_rate': 0.05,
             'num_leaves': 20, 'subsample': 0.8, 'colsample_bytree': 0.6,
             'min_child_samples': 50, 'reg_alpha': 0.5, 'reg_lambda': 2.0},
            {'n_estimators': 1000, 'max_depth': 6, 'learning_rate': 0.02,
             'num_leaves': 40, 'subsample': 0.6, 'colsample_bytree': 0.8,
             'min_child_samples': 20, 'reg_alpha': 0.05, 'reg_lambda': 0.5},
            {'n_estimators': 500, 'max_depth': 3, 'learning_rate': 0.08,
             'num_leaves': 15, 'subsample': 0.9, 'colsample_bytree': 0.5,
             'min_child_samples': 60, 'reg_alpha': 1.0, 'reg_lambda': 3.0},
            {'n_estimators': 700, 'max_depth': 5, 'learning_rate': 0.04,
             'num_leaves': 25, 'subsample': 0.75, 'colsample_bytree': 0.75,
             'min_child_samples': 40, 'reg_alpha': 0.2, 'reg_lambda': 1.5},
        ]
        
        # Step 1: Train base models with early stopping on validation set
        oof_predictions = np.zeros((X_train.shape[0], self.n_base_models))
        val_predictions = np.zeros((X_val.shape[0], self.n_base_models))
        
        for i, params in enumerate(base_params_list[:self.n_base_models]):
            model = lgb.LGBMRegressor(**params)
            
            # Use 3-fold CV within training set for OOF predictions
            from sklearn.model_selection import KFold
            kf = KFold(n_splits=3, shuffle=False)  # No shuffle: temporal order
            
            for train_idx, oof_idx in kf.split(X_train):
                model_fold = lgb.LGBMRegressor(**params)
                model_fold.fit(
                    X_train[train_idx], y_train[train_idx],
                    eval_set=[(X_train[oof_idx], y_train[oof_idx])],
                    callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
                )
                oof_predictions[oof_idx, i] = model_fold.predict(X_train[oof_idx])
            
            # Refit on full training set for final base model
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
            )
            self.base_models.append(model)
            val_predictions[:, i] = model.predict(X_val)
        
        # Step 2: Train meta-learner on OOF predictions
        self.meta_model.fit(oof_predictions, y_train)
        
        return self
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate ensemble prediction."""
        base_preds = np.column_stack([
            model.predict(X) for model in self.base_models
        ])
        return self.meta_model.predict(base_preds)
    
    def predict_with_uncertainty(self, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return mean prediction and standard deviation across base models."""
        base_preds = np.column_stack([
            model.predict(X) for model in self.base_models
        ])
        mean_pred = self.meta_model.predict(base_preds)
        std_pred = base_preds.std(axis=1)
        return mean_pred, std_pred
```

Why Ridge as the meta-learner: Ridge is low-variance, which is critical when stacking only 5 base models. A non-linear meta-learner (like another gradient boosting model) on 5 features would overfit quickly. Ridge also provides interpretable weights showing which base model the ensemble trusts most.

### Hyperparameter Tuning with Optuna

```python
import optuna
from sklearn.metrics import mean_squared_error

def optuna_lgb_spread(X_train, y_train, X_val, y_val, n_trials=150):
    """
    Tune a single LightGBM base model using Optuna with walk-forward val.
    """
    def objective(trial):
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 300, 1500),
            'max_depth': trial.suggest_int('max_depth', 3, 7),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.1, log=True),
            'num_leaves': trial.suggest_int('num_leaves', 10, 60),
            'subsample': trial.suggest_float('subsample', 0.5, 0.95),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.4, 0.9),
            'min_child_samples': trial.suggest_int('min_child_samples', 15, 80),
            'reg_alpha': trial.suggest_float('reg_alpha', 0.01, 2.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 0.1, 5.0, log=True),
        }
        
        model = lgb.LGBMRegressor(**params)
        model.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)],
        )
        
        preds = model.predict(X_val)
        rmse = mean_squared_error(y_val, preds, squared=False)
        
        return rmse
    
    study = optuna.create_study(
        direction='minimize',
        sampler=optuna.samplers.TPESampler(seed=42),
        pruner=optuna.pruners.MedianPruner(n_startup_trials=20),
    )
    study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    
    print(f"Best RMSE: {study.best_value:.4f}")
    print(f"Best params: {study.best_params}")
    
    return study

# Run across multiple walk-forward splits
def tune_across_splits(features, splits):
    """
    Run Optuna on each walk-forward split and aggregate best params.
    This prevents overfitting to a single val period.
    """
    all_best_params = []
    for split in splits:
        X_train, y_train = get_split_data(features, split.train_seasons)
        X_val, y_val = get_split_data(features, [split.val_season])
        
        study = optuna_lgb_spread(X_train, y_train, X_val, y_val, n_trials=100)
        all_best_params.append(study.best_params)
    
    # Average numeric hyperparameters across splits
    avg_params = {}
    for key in all_best_params[0]:
        values = [p[key] for p in all_best_params]
        if isinstance(values[0], int):
            avg_params[key] = int(np.median(values))
        else:
            avg_params[key] = np.median(values)
    
    return avg_params
```

Critical tuning strategy: Run Optuna separately on each walk-forward split, then take the median of each hyperparameter across splits. This guards against finding hyperparameters that overfit one particular season's validation set.

### SHAP Value Interpretation

```python
import shap

def analyze_shap(model: lgb.LGBMRegressor, X: np.ndarray, 
                 feature_names: list[str]) -> None:
    """
    Generate SHAP analysis for model transparency and feature validation.
    """
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    
    # 1. Global feature importance ranking
    shap.summary_plot(shap_values, X, feature_names=feature_names, 
                      plot_type='bar', max_display=25)
    
    # 2. Directional impact (beeswarm)
    shap.summary_plot(shap_values, X, feature_names=feature_names, 
                      max_display=25)
    
    # 3. Feature interaction detection
    # Look for the top interactions to validate they make football sense
    shap_interaction = explainer.shap_interaction_values(X[:500])
    
    # 4. Single-game explanation (for bet auditing)
    def explain_game(game_idx: int):
        shap.waterfall_plot(
            shap.Explanation(
                values=shap_values[game_idx],
                base_values=explainer.expected_value,
                data=X[game_idx],
                feature_names=feature_names,
            ),
            max_display=15
        )
    
    return shap_values

def validate_shap_directions(shap_values, X, feature_names):
    """
    Sanity check: verify SHAP directions match domain knowledge.
    Flag any feature where the relationship is inverted.
    """
    expected_directions = {
        'off_epa_play_roll4_diff': 'positive',      # Better offense differential = higher margin
        'def_epa_play_roll4_diff': 'negative',       # Lower defensive EPA = better defense
        'rest_diff': 'positive',                      # More rest for home = higher margin
        'home_coach_tenure': 'positive',              # More stability = slight edge
        'wind_mph': 'near_zero',                      # Wind shouldn't predict spread direction
        'extreme_cold': 'near_zero',                  # Cold affects both teams
    }
    
    feature_idx = {name: i for i, name in enumerate(feature_names)}
    
    for feat, expected in expected_directions.items():
        if feat not in feature_idx:
            continue
        idx = feature_idx[feat]
        correlation = np.corrcoef(X[:, idx], shap_values[:, idx])[0, 1]
        
        if expected == 'positive' and correlation < -0.1:
            print(f"WARNING: {feat} has inverted SHAP direction (corr={correlation:.3f})")
        elif expected == 'negative' and correlation > 0.1:
            print(f"WARNING: {feat} has inverted SHAP direction (corr={correlation:.3f})")
        elif expected == 'near_zero' and abs(correlation) > 0.3:
            print(f"WARNING: {feat} has unexpectedly strong SHAP signal (corr={correlation:.3f})")
```

SHAP serves three purposes here:
1. **Feature validation**: If a feature's SHAP direction contradicts domain knowledge, investigate before shipping
2. **Bet auditing**: Before placing any bet, generate a waterfall plot showing which features drove the edge. If the edge is driven by a single noisy feature, skip the bet
3. **Feature selection**: Features with near-zero mean SHAP magnitude across the dataset are candidates for removal to reduce overfitting

### Data Leakage Detection

```python
def detect_leakage(features: pd.DataFrame, target_col: str = 'margin') -> list[str]:
    """
    Multi-layered leakage detection.
    Returns list of features flagged as potential leakers.
    """
    flagged = []
    feature_cols = [c for c in features.columns 
                    if c not in ['game_id', 'season', 'week', target_col,
                                 'home_score', 'away_score', 'result']]
    
    # Test 1: Suspiciously high correlation with target
    for col in feature_cols:
        if features[col].dtype in ['float64', 'int64']:
            corr = features[col].corr(features[target_col])
            if abs(corr) > 0.5:
                flagged.append((col, f'High correlation: {corr:.3f}'))
    
    # Test 2: Feature importance spike
    # Train a quick model and check if any single feature dominates
    from sklearn.ensemble import RandomForestRegressor
    X = features[feature_cols].fillna(0).values
    y = features[target_col].values
    rf = RandomForestRegressor(n_estimators=100, max_depth=5, random_state=42)
    rf.fit(X, y)
    importances = dict(zip(feature_cols, rf.feature_importances_))
    max_imp = max(importances.values())
    for col, imp in importances.items():
        if imp > 0.15:  # No single feature should dominate this much
            flagged.append((col, f'Dominant importance: {imp:.3f}'))
    
    # Test 3: Temporal consistency check
    # If a feature's predictive power drops drastically on future data,
    # it may be leaking from the target period
    for split in walk_forward_splits(sorted(features['season'].unique())):
        train_mask = features['season'].isin(split.train_seasons)
        test_mask = features['season'] == split.test_season
        
        for col in feature_cols:
            if features[col].dtype not in ['float64', 'int64']:
                continue
            train_corr = features.loc[train_mask, col].corr(
                features.loc[train_mask, target_col])
            test_corr = features.loc[test_mask, col].corr(
                features.loc[test_mask, target_col])
            
            if abs(train_corr) > 0.3 and abs(test_corr) < 0.05:
                flagged.append((col, f'Temporal instability: train={train_corr:.3f}, test={test_corr:.3f}'))
    
    # Test 4: Manual checklist
    leakage_keywords = [
        'final', 'actual', 'result', 'winner', 'closing_line',
        'postgame', 'box_score', 'game_total_points',
    ]
    for col in feature_cols:
        for keyword in leakage_keywords:
            if keyword in col.lower():
                flagged.append((col, f'Suspicious name contains "{keyword}"'))
    
    # Test 5: Verify all rolling features use shift(1)
    # This is a code review step, not an automated test, but log a reminder
    print("MANUAL CHECK: Verify every rolling/expanding feature applies shift(1)")
    print("MANUAL CHECK: Verify 'current_spread' is frozen at prediction cutoff, not closing")
    
    return flagged
```

The most common NFL model leakage sources:
1. Using the closing line instead of the line at your prediction cutoff time
2. Forgetting `shift(1)` on a rolling feature so the current game's stats leak in
3. Including any postgame data (final score, actual stats) in features
4. Using "season-to-date" stats that include the current game
5. Referee or weather data that was updated after the game started

---

## 1B. Moneyline Model (Derived from Spread)

### Concept

The moneyline is the probability of winning outright. There is a well-established empirical relationship between point spread and win probability in the NFL. Rather than training a separate classification model (which would waste data and risk calibration divergence), we fit a historical sigmoid curve that maps spread predictions to win probabilities.

### Fitting the Margin-to-Win-Probability Curve

```python
from scipy.optimize import curve_fit
from scipy.special import expit

def sigmoid(x, k, x0):
    """Standard sigmoid with slope k and midpoint x0."""
    return expit(k * (x - x0))

def fit_margin_to_winprob(
    historical_games: pd.DataFrame,
    bucket_by: list[str] = None,
) -> dict:
    """
    Fit sigmoid curves mapping predicted margin to empirical win probability.
    
    historical_games has:
      - predicted_margin: model's pre-game spread prediction (home perspective)
      - home_win: binary, 1 if home team won
      - weather_bucket: 'dome', 'normal', 'adverse' (wind>15 or precip>50%)
      - is_home: always 1 for home perspective (included for symmetry validation)
    
    Returns dict of fitted parameters keyed by bucket.
    """
    # Default: fit one global curve
    if bucket_by is None:
        bucket_by = ['global']
        historical_games['global'] = 'all'
    
    fitted_curves = {}
    
    for bucket_vals, group in historical_games.groupby(bucket_by):
        if len(group) < 100:
            # Insufficient data for this bucket; fall back to global
            continue
        
        margins = group['predicted_margin'].values
        wins = group['home_win'].values
        
        # Initial guess: slope=0.15 (standard NFL), midpoint=0
        try:
            popt, pcov = curve_fit(
                sigmoid, margins, wins,
                p0=[0.15, 0.0],
                bounds=([0.05, -3.0], [0.35, 3.0]),
                maxfev=5000,
            )
            fitted_curves[bucket_vals] = {
                'k': popt[0],
                'x0': popt[1],
                'n_games': len(group),
                'std_err': np.sqrt(np.diag(pcov)),
            }
        except RuntimeError:
            print(f"Curve fit failed for bucket {bucket_vals}")
    
    return fitted_curves


def margin_to_winprob(
    predicted_margin: float,
    weather_bucket: str,
    fitted_curves: dict,
) -> float:
    """
    Convert a spread model prediction to a win probability.
    
    A predicted margin of +3.0 for the home team means the model expects
    the home team to win by 3 points. This maps to roughly 60% win probability
    under normal conditions.
    """
    # Try specific bucket first, fall back to global
    key = weather_bucket
    if key not in fitted_curves:
        key = 'all'
    
    params = fitted_curves[key]
    prob = sigmoid(predicted_margin, params['k'], params['x0'])
    
    return prob
```

### Weather Bucket Stratification

Why bucket by weather: In adverse weather, the variance of game outcomes increases. A 3-point favorite in a blizzard wins less often than a 3-point favorite in a dome, because high-variance conditions make upsets more likely. The sigmoid slope (k parameter) should be shallower for adverse weather.

```python
def assign_weather_bucket(wind_mph: float, precip_prob: float, 
                          is_dome: bool) -> str:
    if is_dome:
        return 'dome'
    elif wind_mph > 18 or precip_prob > 0.5:
        return 'adverse'
    else:
        return 'normal'
```

Expected fitted parameters (approximate from NFL historical data):
- Dome: k ≈ 0.17, x0 ≈ 0.0 (steeper slope, spread is more predictive)
- Normal: k ≈ 0.15, x0 ≈ 0.0 (standard)
- Adverse: k ≈ 0.12, x0 ≈ 0.0 (flatter slope, more randomness)

### Validation of the Sigmoid Fit

```python
def validate_sigmoid_fit(games: pd.DataFrame, fitted_curves: dict):
    """
    Validate the margin-to-winprob mapping using binned calibration.
    """
    games['predicted_winprob'] = games.apply(
        lambda r: margin_to_winprob(
            r['predicted_margin'], r['weather_bucket'], fitted_curves
        ), axis=1
    )
    
    # Bin predictions into 5% buckets
    games['prob_bin'] = pd.cut(games['predicted_winprob'], 
                                bins=np.arange(0, 1.05, 0.05))
    
    calibration = (
        games.groupby('prob_bin')
        .agg(
            mean_predicted=('predicted_winprob', 'mean'),
            mean_actual=('home_win', 'mean'),
            count=('home_win', 'count'),
        )
        .dropna()
    )
    
    # Perfect calibration: mean_predicted == mean_actual
    # Compute calibration error
    calibration['abs_error'] = (calibration['mean_predicted'] - calibration['mean_actual']).abs()
    weighted_cal_error = (
        (calibration['abs_error'] * calibration['count']).sum() / calibration['count'].sum()
    )
    
    print(f"Weighted calibration error: {weighted_cal_error:.4f}")
    
    # Also compute log loss for overall quality
    from sklearn.metrics import log_loss
    ll = log_loss(games['home_win'], games['predicted_winprob'])
    print(f"Log loss: {ll:.4f}")
    
    return calibration
```

### Vig Removal and Market Comparison

```python
def remove_vig_moneyline(home_odds: float, away_odds: float) -> tuple[float, float]:
    """
    Convert American odds to no-vig probabilities using the
    multiplicative method (power method is more accurate but this is standard).
    
    home_odds, away_odds are in American format (e.g., -150, +130).
    """
    def american_to_implied(odds: float) -> float:
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)
    
    home_implied = american_to_implied(home_odds)
    away_implied = american_to_implied(away_odds)
    
    total_implied = home_implied + away_implied  # This exceeds 1.0 due to vig
    
    # Multiplicative removal (simplest, slightly biased toward favorites)
    home_fair = home_implied / total_implied
    away_fair = away_implied / total_implied
    
    return home_fair, away_fair

def power_method_devig(home_implied: float, away_implied: float,
                       tol: float = 1e-6, max_iter: int = 100) -> tuple[float, float]:
    """
    Shin/power method for more accurate vig removal.
    Finds exponent n such that home_implied^n + away_implied^n = 1.
    """
    lo, hi = 0.5, 1.5
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        total = home_implied ** mid + away_implied ** mid
        if total > 1.0:
            lo = mid
        else:
            hi = mid
        if abs(total - 1.0) < tol:
            break
    
    home_fair = home_implied ** mid
    away_fair = away_implied ** mid
    return home_fair, away_fair

def find_moneyline_edge(model_prob: float, book_home_odds: float, 
                        book_away_odds: float) -> dict:
    """
    Compare model's win probability against devigged book probability.
    """
    home_fair, away_fair = power_method_devig(
        *[american_to_implied(o) for o in [book_home_odds, book_away_odds]]
    )
    
    home_edge = model_prob - home_fair
    away_edge = (1 - model_prob) - away_fair
    
    return {
        'model_home_prob': model_prob,
        'model_away_prob': 1 - model_prob,
        'market_home_fair': home_fair,
        'market_away_fair': away_fair,
        'home_edge': home_edge,
        'away_edge': away_edge,
        'best_side': 'home' if home_edge > away_edge else 'away',
        'best_edge': max(home_edge, away_edge),
        'qualifies': max(home_edge, away_edge) >= 0.03,
    }
```

---

## 1C. Game Totals Model

### Target Variable

`total_points = home_score + away_score`

### Feature Engineering

Most features parallel the spread model structure with key differences in what matters.

#### Pace and Volume Features

```python
def build_pace_features(pbp: pd.DataFrame) -> pd.DataFrame:
    """
    Offensive pace features from play-by-play data.
    """
    game_pace = (
        pbp[pbp['play_type'].isin(['pass', 'run', 'no_play'])]
        .groupby(['posteam', 'game_id', 'season', 'week'])
        .agg(
            plays_per_game=('play_id', 'count'),
            avg_seconds_per_play=('play_clock', lambda x: x.dropna().mean()),  
            # Use time between snaps from play-by-play timing columns
            neutral_pass_rate=('play_type', lambda x: (x == 'pass').mean()),
            shotgun_rate=('shotgun', 'mean'),
            no_huddle_rate=('no_huddle', 'mean'),
        )
        .reset_index()
        .sort_values(['posteam', 'season', 'week'])
    )
    
    # Rolling 4-game pace (shifted)
    pace_cols = ['plays_per_game', 'neutral_pass_rate', 'no_huddle_rate']
    for col in pace_cols:
        game_pace[f'{col}_roll4'] = (
            game_pace.groupby('posteam')[col]
            .transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
        )
    
    return game_pace
```

#### EPA Splits (Pass vs Run, Offense vs Defense)

For totals, the pass/run split matters more than for spreads because passing correlates more strongly with scoring rate.

```python
def build_epa_splits_for_totals(pbp: pd.DataFrame) -> pd.DataFrame:
    """
    EPA features split by phase for totals prediction.
    Emphasis on passing efficiency and explosive play rate.
    """
    plays = pbp[pbp['play_type'].isin(['pass', 'run']) & pbp['epa'].notna()].copy()
    
    # Offensive splits
    off_splits = (
        plays.groupby(['posteam', 'game_id', 'season', 'week'])
        .apply(lambda g: pd.Series({
            'off_epa_pass': g.loc[g['play_type'] == 'pass', 'epa'].mean(),
            'off_epa_run': g.loc[g['play_type'] == 'run', 'epa'].mean(),
            'off_success_rate': (g['epa'] > 0).mean(),
            'off_explosive_rate': (g['yards_gained'] >= 20).mean(),
            'off_three_and_out_rate_proxy': None,  # Computed from drive-level data
        }))
        .reset_index()
    )
    
    # Defensive splits
    def_splits = (
        plays.groupby(['defteam', 'game_id', 'season', 'week'])
        .apply(lambda g: pd.Series({
            'def_epa_pass': g.loc[g['play_type'] == 'pass', 'epa'].mean(),
            'def_epa_run': g.loc[g['play_type'] == 'run', 'epa'].mean(),
            'def_success_rate_allowed': (g['epa'] > 0).mean(),
            'def_turnover_rate': g['interception'].sum() + g['fumble_lost'].sum() 
                                  if 'fumble_lost' in g.columns else 0,
        }))
        .reset_index()
    )
    
    return off_splits, def_splits
```

#### Implied Game Competitiveness (from Spread Model)

This is where the models interconnect. Blowouts suppress totals because the leading team runs the ball and burns clock in the second half.

```python
def build_competitiveness_feature(spread_prediction: float) -> dict:
    """
    Derive game competitiveness from the spread model output.
    A larger absolute spread implies a less competitive game,
    which historically correlates with fewer total points.
    """
    abs_spread = abs(spread_prediction)
    
    return {
        'abs_predicted_spread': abs_spread,
        'blowout_flag': int(abs_spread >= 10),
        'competitive_flag': int(abs_spread <= 3),
        'spread_squared': abs_spread ** 2,  # Non-linear suppression effect
    }
```

The empirical relationship: games with a spread of 0 to 3 average about 2 more total points than games with a spread of 10+. This is a small but consistent effect driven by game script dynamics.

#### Weather (Wind Dominant)

```python
def build_weather_for_totals(weather: StadiumWeather) -> dict:
    """
    Weather features with extra emphasis on wind for totals.
    Wind above 15 mph suppresses passing, which suppresses scoring.
    """
    if weather.is_dome:
        return {
            'wind_mph': 0.0,
            'wind_squared': 0.0,
            'wind_bucket': 'none',
            'temp_f': 72.0,
            'precip_prob': 0.0,
            'adverse_weather_score': 0.0,
        }
    
    # Wind is non-linear: 10 mph has negligible impact, 25 mph is devastating
    wind_impact = max(0, weather.wind_mph - 8) ** 1.5  # Threshold at 8 mph
    
    return {
        'wind_mph': weather.wind_mph,
        'wind_squared': weather.wind_mph ** 2,
        'wind_bucket': (
            'calm' if weather.wind_mph < 8 else
            'moderate' if weather.wind_mph < 18 else
            'heavy'
        ),
        'temp_f': weather.temp_f,
        'precip_prob': weather.precip_prob,
        'adverse_weather_score': wind_impact + (weather.precip_prob * 3),
    }
```

#### Referee Totals Tendencies

```python
def build_ref_totals_features(ref_data: pd.DataFrame) -> pd.DataFrame:
    """
    Referee impact on game totals.
    Some referees allow more holding (suppresses passing),
    others call more pass interference (inflates scoring).
    """
    ref_totals = (
        ref_data.sort_values(['referee_name', 'game_id'])
        .groupby('referee_name')
        .apply(lambda g: g.assign(
            ref_avg_total_points=g['total_points'].shift(1).expanding().mean(),
            ref_avg_penalties=g['total_penalties'].shift(1).expanding().mean(),
            ref_avg_penalty_yards=g['total_penalty_yards'].shift(1).expanding().mean(),
        ))
    )
    
    return ref_totals
```

#### Market Signals for Totals

```python
def build_totals_market_features(odds_data: pd.DataFrame) -> pd.DataFrame:
    """
    Opening total, line movement, and public betting percentages on the total.
    """
    odds_data['total_line_move'] = odds_data['current_total'] - odds_data['open_total']
    odds_data['total_line_move_abs'] = odds_data['total_line_move'].abs()
    
    # Public tends to bet overs; reverse movement on totals is a strong signal
    odds_data['total_reverse_move'] = (
        ((odds_data['public_pct_over'] > 60) & (odds_data['total_line_move'] < 0)) |
        ((odds_data['public_pct_over'] < 40) & (odds_data['total_line_move'] > 0))
    ).astype(int)
    
    return odds_data
```

### Training Pipeline (Same Architecture as Spread)

```python
class TotalsEnsemble(SpreadEnsemble):
    """
    Same LightGBM + Ridge architecture as the spread model.
    Key differences:
    1. Target is total_points instead of margin
    2. Feature set emphasizes pace, passing, wind
    3. Consumes spread model output as a feature
    """
    
    def fit(self, X_train, y_train, X_val, y_val, feature_names,
            spread_model: SpreadEnsemble = None, 
            X_train_spread: np.ndarray = None,
            X_val_spread: np.ndarray = None):
        """
        If spread_model is provided, generate competitiveness features
        and append them to X_train and X_val.
        """
        if spread_model is not None:
            spread_preds_train = spread_model.predict(X_train_spread)
            spread_preds_val = spread_model.predict(X_val_spread)
            
            comp_train = np.column_stack([
                np.abs(spread_preds_train),
                (np.abs(spread_preds_train) >= 10).astype(float),
                (np.abs(spread_preds_train) <= 3).astype(float),
                np.abs(spread_preds_train) ** 2,
            ])
            comp_val = np.column_stack([
                np.abs(spread_preds_val),
                (np.abs(spread_preds_val) >= 10).astype(float),
                (np.abs(spread_preds_val) <= 3).astype(float),
                np.abs(spread_preds_val) ** 2,
            ])
            
            X_train = np.hstack([X_train, comp_train])
            X_val = np.hstack([X_val, comp_val])
            feature_names = feature_names + [
                'abs_predicted_spread', 'blowout_flag', 
                'competitive_flag', 'spread_squared'
            ]
        
        return super().fit(X_train, y_train, X_val, y_val, feature_names)
```

### Deriving Team Totals

```python
def derive_team_totals(spread_pred: float, total_pred: float) -> dict:
    """
    Combine spread and total predictions to produce implied team totals.
    
    If spread_pred = -3.0 (home favored by 3) and total_pred = 45.0:
      home_total = (45.0 + 3.0) / 2 = 24.0
      away_total = (45.0 - 3.0) / 2 = 21.0
    
    These feed directly into player props models as a context feature.
    """
    home_total = (total_pred + spread_pred) / 2
    away_total = (total_pred - spread_pred) / 2
    
    return {
        'home_implied_total': round(home_total, 1),
        'away_implied_total': round(away_total, 1),
        'total': round(total_pred, 1),
        'spread': round(spread_pred, 1),
    }
```

---

## Cross-Cutting Concerns: All Three Models

### Backtesting Methodology

```python
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class BacktestResult:
    season: int
    week: int
    game_id: str
    market: str                    # 'spread', 'moneyline', 'total'
    model_prediction: float        # predicted margin, winprob, or total
    market_line: float             # book spread, ML implied prob, or total line
    bet_side: Optional[str]        # 'home', 'away', 'over', 'under', or None
    edge: float                    # model vs market difference
    bet_placed: bool               # True if edge >= 0.03
    result: Optional[float]        # actual outcome
    won: Optional[bool]
    closing_line: float            # Pinnacle closing line
    clv: Optional[float]          # Closing line value achieved

@dataclass 
class BacktestEngine:
    """
    Walk-forward backtesting engine for all game line models.
    """
    min_edge: float = 0.03
    kelly_fraction: float = 0.25
    max_bet_pct: float = 0.03     # 3% of bankroll cap per bet
    
    def run_backtest(
        self,
        features: pd.DataFrame,
        spread_ensemble: SpreadEnsemble,
        totals_ensemble: TotalsEnsemble,
        fitted_curves: dict,
        odds_data: pd.DataFrame,
        closing_lines: pd.DataFrame,
    ) -> list[BacktestResult]:
        """
        Full backtest across all walk-forward splits.
        """
        results = []
        splits = list(walk_forward_splits(
            sorted(features['season'].unique()), 
            min_train_seasons=3, holdout_seasons=2
        ))
        
        for split in splits:
            # Train on training seasons
            X_train, y_train_spread, y_train_total = self._get_data(
                features, split.train_seasons)
            X_val, y_val_spread, y_val_total = self._get_data(
                features, [split.val_season])
            X_test, y_test_spread, y_test_total = self._get_data(
                features, [split.test_season])
            
            # Fit spread model
            spread_ensemble.fit(X_train, y_train_spread, X_val, y_val_spread,
                               self.feature_names)
            
            # Fit totals model (consuming spread output)
            totals_ensemble.fit(
                X_train, y_train_total, X_val, y_val_total,
                self.totals_feature_names,
                spread_model=spread_ensemble,
                X_train_spread=X_train,
                X_val_spread=X_val,
            )
            
            # Generate predictions on test season
            spread_preds = spread_ensemble.predict(X_test)
            total_preds = totals_ensemble.predict(X_test)
            
            # Evaluate each game
            test_games = features[features['season'] == split.test_season]
            
            for idx, (_, game) in enumerate(test_games.iterrows()):
                game_id = game['game_id']
                
                # Spread bet evaluation
                spread_edge = self._eval_spread_bet(
                    spread_preds[idx], game, odds_data, closing_lines
                )
                if spread_edge:
                    results.append(spread_edge)
                
                # Moneyline bet evaluation
                ml_edge = self._eval_ml_bet(
                    spread_preds[idx], game, odds_data, 
                    closing_lines, fitted_curves
                )
                if ml_edge:
                    results.append(ml_edge)
                
                # Total bet evaluation
                total_edge = self._eval_total_bet(
                    total_preds[idx], game, odds_data, closing_lines
                )
                if total_edge:
                    results.append(total_edge)
        
        return results
    
    def _eval_spread_bet(self, pred_margin, game, odds, closing) -> Optional[BacktestResult]:
        """Evaluate a spread bet opportunity."""
        game_odds = odds[odds['game_id'] == game['game_id']]
        if game_odds.empty:
            return None
        
        book_spread = game_odds.iloc[0]['current_spread']
        
        # Edge: if model says home -2 and book says home -4.5,
        # model thinks home is 2.5 points better than the book gives credit
        # That means bet HOME (the spread is too wide, home will cover)
        edge_home = pred_margin - book_spread  # Positive = home undervalued
        
        # For spread bets at standard -110, edge must overcome vig
        # At -110, breakeven is 52.4%. We need the equivalent in points
        # Approximate: 1 point of spread edge ~ 3% of win probability
        
        actual_margin = game['home_score'] - game['away_score']
        
        if abs(edge_home) >= 1.0:  # ~3% edge threshold for spreads
            side = 'home' if edge_home > 0 else 'away'
            if side == 'home':
                won = actual_margin > -book_spread  # Home covers
            else:
                won = actual_margin < -book_spread  # Away covers
            
            # CLV: compare our bet line vs Pinnacle closing
            closing_spread = closing[closing['game_id'] == game['game_id']]
            clv = None
            if not closing_spread.empty:
                pinnacle_close = closing_spread.iloc[0]['pinnacle_spread']
                if side == 'home':
                    clv = book_spread - pinnacle_close  # Positive CLV = we got a better number
                else:
                    clv = pinnacle_close - book_spread
            
            return BacktestResult(
                season=game['season'], week=game['week'],
                game_id=game['game_id'], market='spread',
                model_prediction=pred_margin, market_line=book_spread,
                bet_side=side, edge=abs(edge_home),
                bet_placed=True, result=actual_margin,
                won=won, closing_line=pinnacle_close if clv is not None else 0,
                clv=clv,
            )
        
        return None
```

### Calibration Validation

```python
from sklearn.metrics import brier_score_loss
import matplotlib.pyplot as plt

def calibration_analysis(results: list[BacktestResult], market: str):
    """
    Full calibration analysis for a specific market.
    """
    market_results = [r for r in results if r.market == market and r.bet_placed]
    
    if market == 'moneyline':
        # For moneyline, we have direct probability predictions
        predicted_probs = [r.model_prediction for r in market_results]
        actual_outcomes = [int(r.won) for r in market_results]
        
        # Brier score
        brier = brier_score_loss(actual_outcomes, predicted_probs)
        print(f"Brier Score ({market}): {brier:.4f}")
        print(f"  Benchmark (market): ~0.20 for NFL moneylines")
        print(f"  Perfect: 0.0, Coin flip: 0.25")
        
        # Reliability curve (calibration plot)
        from sklearn.calibration import calibration_curve
        prob_true, prob_pred = calibration_curve(
            actual_outcomes, predicted_probs, n_bins=10, strategy='quantile'
        )
        
        fig, ax = plt.subplots(1, 1, figsize=(8, 6))
        ax.plot(prob_pred, prob_true, 'o-', label='Model')
        ax.plot([0, 1], [0, 1], '--', color='gray', label='Perfect')
        ax.set_xlabel('Predicted probability')
        ax.set_ylabel('Observed frequency')
        ax.set_title(f'Calibration: {market}')
        ax.legend()
        plt.savefig(f'calibration_{market}.png', dpi=150)
    
    elif market in ['spread', 'total']:
        # For spread/total, convert to cover probability for calibration
        # A 1-point edge implies roughly 53% cover probability
        # We can bin by edge size and check win rate
        
        edge_bins = pd.cut(
            [r.edge for r in market_results],
            bins=[0, 1.0, 2.0, 3.0, 5.0, 10.0, 20.0]
        )
        win_rate_by_edge = pd.DataFrame({
            'edge_bin': edge_bins,
            'won': [r.won for r in market_results],
        }).groupby('edge_bin').agg(
            win_rate=('won', 'mean'),
            count=('won', 'count'),
        )
        
        print(f"\nWin rate by edge size ({market}):")
        print(win_rate_by_edge)
        
        # Expected: higher edge bins should have higher win rates
        # If win rate is flat or inverted, model is not calibrated
```

### CLV Tracking

```python
@dataclass
class CLVTracker:
    """
    Track closing line value across all bets.
    CLV is the primary success metric, not raw win rate.
    """
    
    def compute_clv_summary(self, results: list[BacktestResult]) -> dict:
        """
        Compute CLV metrics across all placed bets.
        """
        placed = [r for r in results if r.bet_placed and r.clv is not None]
        
        if not placed:
            return {}
        
        clvs = [r.clv for r in placed]
        
        summary = {
            'n_bets': len(placed),
            'mean_clv': np.mean(clvs),
            'median_clv': np.median(clvs),
            'pct_positive_clv': np.mean([c > 0 for c in clvs]),
            'clv_by_market': {},
        }
        
        for market in ['spread', 'moneyline', 'total']:
            market_clvs = [r.clv for r in placed if r.market == market]
            if market_clvs:
                summary['clv_by_market'][market] = {
                    'n_bets': len(market_clvs),
                    'mean_clv': np.mean(market_clvs),
                    'pct_positive': np.mean([c > 0 for c in market_clvs]),
                }
        
        return summary
    
    def clv_significance_test(self, results: list[BacktestResult]) -> dict:
        """
        Test whether observed CLV is statistically significant.
        Uses a one-sample t-test against H0: mean CLV = 0.
        """
        from scipy import stats
        
        clvs = [r.clv for r in results if r.bet_placed and r.clv is not None]
        
        if len(clvs) < 30:
            return {
                'significant': False,
                'reason': f'Insufficient sample: {len(clvs)} bets (need 30+)',
            }
        
        t_stat, p_value = stats.ttest_1samp(clvs, 0)
        
        return {
            'n_bets': len(clvs),
            'mean_clv': np.mean(clvs),
            't_stat': t_stat,
            'p_value': p_value,
            'significant_at_05': p_value < 0.05,
            'significant_at_01': p_value < 0.01,
        }
```

#### What CLV Numbers Mean in Practice

For NFL game lines, target benchmarks:

| Metric | Marginal | Good | Excellent |
|---|---|---|---|
| Mean CLV (spreads) | 0.3 pts | 0.5 pts | 1.0+ pts |
| Mean CLV (totals) | 0.3 pts | 0.5 pts | 0.8+ pts |
| Mean CLV (moneyline) | 0.5% | 1.5% | 3.0%+ |
| % Positive CLV | 52% | 55% | 58%+ |

If you cannot achieve at least 0.3 points of mean CLV on spreads across 2+ seasons of backtesting, the model is not yet viable for deployment.

### Statistical Significance at NFL Sample Sizes

```python
def required_sample_for_significance(
    assumed_edge: float = 0.03,    # 3% edge over market
    assumed_variance: float = 0.25, # Bernoulli variance at 50%
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """
    Calculate minimum sample size needed to detect an edge.
    
    For a 3% edge (53% true win rate vs 50%):
      n ≈ (z_alpha + z_beta)^2 * p(1-p) / delta^2
      n ≈ (1.96 + 0.84)^2 * 0.25 / 0.03^2
      n ≈ 7.84 * 0.25 / 0.0009
      n ≈ 2,178 bets
    
    At ~150 bets per season (roughly half of games qualify), 
    that is approximately 14.5 seasons of betting.
    
    This is why CLV is the primary metric, not win rate.
    """
    from scipy import stats
    z_alpha = stats.norm.ppf(1 - alpha / 2)
    z_beta = stats.norm.ppf(power)
    
    n = ((z_alpha + z_beta) ** 2 * assumed_variance) / (assumed_edge ** 2)
    
    return int(np.ceil(n))

# For NFL specifically:
# ~270 regular season games
# ~50% qualify for a bet (edge >= 3%)
# = ~135 bets per season per market
# To reach 2,178 bets: ~16 seasons
#
# This is exactly why CLV matters more than raw win/loss record:
#   CLV can be measured per-bet with much lower variance,
#   so you can detect signal in 1-2 seasons rather than 15+.
```

### When to Retrain

```python
@dataclass
class RetrainTrigger:
    """
    Dual trigger system: scheduled + performance-based.
    """
    
    # Scheduled triggers
    preseason_retrain: bool = True       # Always retrain before week 1
    mid_season_retrain_week: int = 9     # Retrain at the bye midpoint
    
    # Performance triggers (checked weekly)
    clv_lookback_window: int = 20        # Last 20 bets
    clv_degradation_threshold: float = -0.3  # Mean CLV below this = retrain
    calibration_drift_threshold: float = 0.08  # Calibration error above this = retrain
    
    def should_retrain(self, recent_results: list[BacktestResult], 
                       current_week: int) -> tuple[bool, str]:
        """
        Check both scheduled and performance triggers.
        Returns (should_retrain, reason).
        """
        # Scheduled check
        if current_week == 1:
            return True, 'Scheduled: preseason retrain with new season data'
        if current_week == self.mid_season_retrain_week:
            return True, f'Scheduled: mid-season retrain at week {current_week}'
        
        # Performance check
        if len(recent_results) < self.clv_lookback_window:
            return False, 'Insufficient recent data for performance check'
        
        recent = recent_results[-self.clv_lookback_window:]
        recent_clvs = [r.clv for r in recent if r.clv is not None]
        
        if not recent_clvs:
            return False, 'No CLV data available'
        
        mean_recent_clv = np.mean(recent_clvs)
        
        if mean_recent_clv < self.clv_degradation_threshold:
            return True, (
                f'Performance: mean CLV over last {self.clv_lookback_window} '
                f'bets is {mean_recent_clv:.3f} (below {self.clv_degradation_threshold})'
            )
        
        # Calibration drift check
        if len(recent_clvs) >= 15:
            # Quick calibration check on recent moneyline bets
            ml_bets = [r for r in recent if r.market == 'moneyline']
            if len(ml_bets) >= 10:
                pred_probs = [r.model_prediction for r in ml_bets]
                actuals = [int(r.won) for r in ml_bets]
                cal_error = abs(np.mean(pred_probs) - np.mean(actuals))
                
                if cal_error > self.calibration_drift_threshold:
                    return True, (
                        f'Performance: calibration drift = {cal_error:.3f} '
                        f'(above {self.calibration_drift_threshold})'
                    )
        
        return False, 'No retrain needed'
```

#### Retrain Schedule Summary

| Trigger | Timing | Action |
|---|---|---|
| Preseason | Before Week 1 | Full retrain with prior season added to training data |
| Mid-season | Week 9 | Partial retrain: update rolling features, optionally re-tune hyperparameters |
| CLV degradation | Weekly check | Full retrain if trailing 20-bet CLV drops below -0.3 points |
| Calibration drift | Weekly check | Recalibrate sigmoid curves and/or full retrain |
| Rule change | Off-season | Full retrain with feature engineering review (e.g., kickoff rule changes) |

When retraining mid-season, add the current season's completed games to the training set but hold out the next 2 weeks as a fresh validation set. Never retrain and immediately bet on the same week's games without a gap.

---

## Staking: 25% Fractional Kelly with Flat Cap

```python
def kelly_stake(
    model_prob: float,
    book_odds: float,      # American odds
    kelly_fraction: float = 0.25,
    max_stake_pct: float = 0.03,  # 3% of bankroll
    bankroll: float = 10000.0,
) -> dict:
    """
    Calculate bet size using fractional Kelly criterion.
    
    Full Kelly: f* = (bp - q) / b
    where b = decimal odds - 1, p = model probability, q = 1 - p
    
    We use 25% Kelly (quarter Kelly) to reduce variance at the cost of
    slower bankroll growth. This is appropriate for NFL where
    the true edge is uncertain.
    """
    def american_to_decimal(odds):
        if odds > 0:
            return 1 + odds / 100
        else:
            return 1 + 100 / abs(odds)
    
    decimal_odds = american_to_decimal(book_odds)
    b = decimal_odds - 1
    p = model_prob
    q = 1 - p
    
    full_kelly = (b * p - q) / b
    
    if full_kelly <= 0:
        return {'stake': 0, 'stake_pct': 0, 'reason': 'No edge (Kelly <= 0)'}
    
    fractional = full_kelly * kelly_fraction
    stake_pct = min(fractional, max_stake_pct)
    stake = round(stake_pct * bankroll, 2)
    
    return {
        'full_kelly_pct': round(full_kelly * 100, 2),
        'fractional_kelly_pct': round(fractional * 100, 2),
        'capped_pct': round(stake_pct * 100, 2),
        'stake': stake,
        'bankroll': bankroll,
        'edge': round((p - (1 / decimal_odds)) * 100, 2),
    }
```

---

## Data Flow: Full Pipeline Summary

```
0. Data Ingestion (automated, pre-pipeline)
   ├── IngestOrchestrator fetches all sources in sequence
   ├── DataRegistry validates availability of every source
   ├── REQUIRED sources (nflverse PBP, schedules): fail pipeline if missing
   ├── RECOMMENDED sources: warn + degrade gracefully
   │   ├── PFF grades (API or CSV import from data/pff_exports/)
   │   ├── The Odds API (spreads, totals, moneylines across books)
   │   ├── OddsJam Pro (Pinnacle closing lines for CLV)
   │   ├── OpenWeather (wind, temp, precip at stadium coords)
   │   └── ActionNetwork (sharp money, public betting %)
   └── All data auto-fetched and cached in data/ as parquet

   Environment variables for API access:
     THE_ODDS_API_KEY      : The Odds API (market data)
     ODDSJAM_API_KEY       : OddsJam Pro (Pinnacle closing lines)
     OPENWEATHER_API_KEY   : OpenWeather (game-day weather)
     PFF_API_KEY           : PFF Premium Stats (team grades)
     ACTIONNETWORK_API_KEY : ActionNetwork (sharp money / public %)

   Source priority levels:
     REQUIRED    : Pipeline raises RuntimeError if missing
     RECOMMENDED : Pipeline warns, model accuracy degrades
     OPTIONAL    : Pipeline warns, minimal impact

1. Source Validation
   ├── DataRegistry.check_all() logs status of every source
   ├── Missing REQUIRED sources → pipeline aborts with error
   ├── Missing RECOMMENDED sources → explicit WARNING with
   │   actionable message (which env var to set, where to place files)
   └── No silent fallbacks: every absent source is logged

2. Feature Engineering
   ├── Rolling (4-game) and season-to-date calculations
   ├── Differential computation (home - away)
   ├── Weather bucket assignment
   ├── Missing-source features filled with NaN (model handles via imputation)
   └── Leakage audit (automated + manual)

3. Model Inference (pre-game, frozen at prediction cutoff)
   ├── Spread Model → predicted margin
   ├── Moneyline → derived from spread via sigmoid
   ├── Totals Model → predicted total (consumes spread output)
   └── Team Totals → (total ± spread) / 2

4. Edge Detection
   ├── Compare model output vs devigged market lines
   ├── Filter: edge >= 3%
   ├── Line shop across 5+ books for best available price
   └── Flag reverse line movement and sharp agreement

5. Staking
   ├── 25% fractional Kelly
   ├── 3% bankroll cap per bet
   └── Log bet with all metadata for CLV tracking

6. Post-Game
   ├── Record results
   ├── Compute CLV vs Pinnacle closing line
   ├── Update calibration metrics
   └── Check retrain triggers
```

---

## Data Ingestion Layer

### Architecture

The data ingestion layer sits upstream of feature engineering and handles all external data sourcing. It is designed around two core components:

1. **DataRegistry**: Central catalog of all data sources with their priority level, expected file paths, and current availability status. Checks are run at pipeline start and after every fetch attempt.

2. **IngestOrchestrator**: Runs all fetch modules in sequence, catches errors per-source (one failed source does not block others), and produces a status report.

### Fetch Modules

Each external data source has its own fetch module in `models/game_lines/data_ingest/`:

| Module | Source | API Key Env Var | Fallback |
|---|---|---|---|
| `fetch_nflverse.py` | nflverse release assets (direct parquet/csv) | None (open data) | None (required) |
| `odds_api.py` | The Odds API historical snapshots | `THE_ODDS_API_KEY` | None for bet-time lines |
| `fetch_weather.py` | OpenWeather API | `OPENWEATHER_API_KEY` | Excluded from pregame features |
| `fetch_pff.py` | PFF Premium API or CSV | `PFF_API_KEY` | CSV import from data/pff_exports/ |

`nfl_data_py` is no longer a dependency. It fails to build against current
toolchains (it requires `pkg_resources` and pins stale pandas), and it is only
a thin wrapper. Data is pulled directly from nflverse release assets:

  * schedules and closing consensus lines: `nflverse/nfldata` -> `data/games.csv`
  * play-by-play: `nflverse-data` release tag `pbp` -> `play_by_play_{season}.parquet`

**OddsJam Pro is removed from the stack.** Pinnacle closing lines are available
directly from The Odds API historical endpoint in the `eu` region back to 2020,
which eliminates the separate closing-line subscription.

### The Odds API Historical Backfill

Credit cost is `10 x n_markets x n_regions` per snapshot call. A snapshot
returns every game that has not yet kicked off, so snapshots are taken per
slate rather than per game:

  * **Bet-time**: one snapshot per (season, week) at Tuesday 18:00 UTC,
    `regions=us,eu`, `markets=spreads,totals`. 131 snapshots, 5,240 credits.
  * **Closing**: kickoff times are clustered per week (any two kickoffs within
    90 minutes merge), and a snapshot is taken 10 minutes before each cluster.
    Each game's closing quote is the latest cluster snapshot strictly before
    its own kickoff. 689 snapshots, `regions=eu`, `markets=spreads`.

Every snapshot is cached to disk keyed by (date, regions, markets), so reruns
cost zero credits. A persisted credit ledger tracks spend against quota, with
a `quota_guard` that refuses to spend below a floor. The ledger uses a lock
and atomic rename: concurrent writes will otherwise tear the JSON and abort a
backfill mid-run.

### Auto-Fetch Behavior

When the data_loader is asked for a source that does not exist on disk:

1. Logs `[DATA MISSING]` warning with the source name and expected path
2. Attempts auto-fetch via the corresponding fetch module
3. If fetch succeeds: saves to `data/` as parquet, logs `[DATA FETCHED]`, returns data
4. If fetch fails (no API key, API error, network): logs `[DATA FETCH FAILED]` with specific error and actionable fix instructions
5. Returns None and logs `[DATA UNAVAILABLE]` with the downstream impact

There are no silent fallbacks. Every missing source produces a warning visible in the pipeline log.

### CLI Usage

```bash
# Fetch all data sources (run before first backtest)
python -m scripts.run_pipeline --mode ingest --seasons 2016 2025

# Force re-download everything
python -m scripts.run_pipeline --mode ingest --seasons 2016 2025 --force-refresh

# Run backtest (automatically ingests data first)
python -m scripts.run_pipeline --mode backtest --seasons 2016 2025

# Skip ingestion if data is already cached
python -m scripts.run_pipeline --mode backtest --seasons 2016 2025 --skip-ingest
```

---

## Validated Backfill and CLV Results (2020-2025)

This section records empirically measured results, not design intent. Every
number below comes from a walk-forward run against real data in the container.

### Data Coverage Achieved

The opening-line coverage gap that previously blocked progress is closed. The
SportsBookReview archive ended in 2021; The Odds API historical endpoint now
supplies bet-time lines through 2025.

| Series | Source | Coverage | Games |
|---|---|---|---|
| Bet-time spread and total (Pinnacle) | Odds API `eu` | 2020-2025 | 1,576 of 1,693 (93.1%) |
| Bet-time spread (DraftKings) | Odds API `us` | 2020-2025 | 1,669 of 1,693 (98.6%) |
| Closing spread (Pinnacle) | Odds API `eu` | 2020-2025 | 1,693 of 1,693 (100%) |
| Closing total (Pinnacle) | Odds API `eu` | 2023-2025 | 855 |
| Closing consensus spread and total | nflverse | 2020-2025 | 1,693 (100%) |

Total spend 15,690 credits of 20,000. Median closing snapshot lands 10 minutes
before kickoff.

Independent validation of the backfill: Pinnacle closing spread versus nflverse
consensus closing spread gives r = 0.9978, mean difference +0.006, sd 0.447,
with 96.6% of games inside half a point. Two independent vendors agreeing to
this tolerance confirms both the sign convention and the game matching.

### Sign Convention (Locked)

The Odds API quotes the home handicap (negative means home favored). nflverse
`spread_line` is positive when home is favored. Everything in this codebase is
normalized to **nflverse orientation**, so `spread = expected home margin`:

```python
spread = -point_home_from_odds_api
```

CLV therefore resolves as:

```python
clv_home = closing_spread - bet_spread   # took home at a cheaper number
clv_away = bet_spread - closing_spread
```

### SBR Cross-Check (2020-2021 Overlap)

Joined on season, date, home score, and away score. Team names in the SBR
archive are unusable as a join key: the 2020-2021 window alone contains
`Fortyniners`, three Kansas City variants (`Chiefs`, `KCChiefs`, `Kansas`),
`Tampa` alongside `Buccaneers`, and the misspelling `Washingtom`. One Super
Bowl row is structurally garbled with a numeric team field.

Score-plus-date alone is **not** sufficient. It matched 99.5% of games but
produced 7 false matches and 14 ambiguous duplicates, because distinct games
on the same date can share a final score. The join must require team agreement
as well as score and date. With all three, 551 of 554 games match cleanly.

**The column-swap defect is now precisely characterized.** In 8.2% of rows
(45 of 551) the closing spread and closing total are *pairwise swapped*:

| game_id | sbr open spread | sbr close spread | sbr open total | sbr close total | true close (Pinnacle) |
|---|---|---|---|---|---|
| 2020_01_SEA_ATL | 1.0 | 49.5 | 49.5 | 1.0 | 1.0 |
| 2020_06_GB_TB | -2.5 | -55.0 | 51.5 | 2.5 | -2.0 |

The defect is recoverable by swapping the two fields back, but there is no
reason to bother. Quality comparison over the overlap:

| Series | vs nflverse consensus close | r | sd |
|---|---|---|---|
| SBR close, all rows | mean -1.043 | 0.556 | 12.585 |
| SBR close, corrupt rows removed | mean +0.012 | 0.990 | 1.029 |
| Pinnacle close (Odds API) | mean +0.006 | 0.998 | 0.447 |

Opening columns show zero physically impossible values, which is consistent
with the earlier decision to consume only opening columns. But even after
removing every corrupt row, SBR carries roughly twice the idiosyncratic noise
of the Odds API series.

**Decision: SBR is deprecated as a line source.** It is retained only as an
offline audit fixture. The Odds API backfill supersedes it on coverage
(through 2025 rather than 2021), on cleanliness, and on book identity, since
SBR does not identify which book produced the number.

### Target: Bet-Time to Close Movement

Confirmed and now measured on Pinnacle-to-Pinnacle data:

```python
spread_move = pinnacle_closing_spread - pinnacle_bettime_spread
```

Distribution over 1,576 games: mean +0.09, sd 1.42, range -11.5 to +9.0.
The target is heavily zero-inflated: **28.2% of games show exactly zero spread
movement** from Tuesday to close (19.7% for totals). Any calibration or
percent-positive metric must account for this, since a bet on a
zero-movement game scores as non-positive CLV without being a loss.

### Ensemble and Shrinkage Calibration

Five LightGBM base learners feed a shrinkage-calibrated linear meta-learner.
The meta-learner is deliberately not unconstrained OLS:

```python
pred = mu_train + beta * (base_blend - mu_train)    # beta clipped to [0, 1]
```

Bounding beta guarantees the ensemble can never be more aggressive than its
own base blend, only less. This is the fix for the earlier miscalibration
where an unconstrained fit on five collinear base predictions produced extreme
coefficients. Observed beta on the spread model was 1.000 on all three splits
(the base blend was already well scaled) and 0.896 on the first totals split,
so the constraint is currently binding only occasionally. It remains necessary
as a guardrail.

### Walk-Forward Design

| Split | Train | Validation | Test |
|---|---|---|---|
| A | 2020-2021 | 2022 | 2023 |
| B | 2020-2022 | 2023 | 2024 |
| C | 2020-2023 | 2024 | 2025 |

Two-season buffer between train and test preserved. 2020 is the hard floor
because The Odds API historical coverage begins mid-2020.

### Spread CLV Results

824 test-set bets across 2023, 2024, and 2025.

| Series | n | Mean CLV | % positive | t | p |
|---|---|---|---|---|---|
| Model (Pinnacle to Pinnacle) | 824 | +0.195 | 41.6% | +4.44 | 1.0e-05 |
| Execution (DraftKings to Pinnacle) | 823 | +0.012 | 36.9% | +0.26 | 0.80 |
| Line-shopped (best of N to Pinnacle) | 824 | +0.321 | 47.7% | +7.31 | 6.4e-13 |
| Benchmark: always bet home | 824 | +0.121 | 39.0% | +2.74 | 0.0063 |
| Benchmark: random side | 824 | +0.029 | 35.9% | +0.65 | 0.51 |

CLV rises monotonically with the conviction filter, replicating the earlier
finding on the extended dataset:

| Conviction threshold | n | Model CLV | % positive | t | p | Line-shopped CLV |
|---|---|---|---|---|---|---|
| 0.00 | 824 | +0.195 | 41.6% | +4.44 | 1.0e-05 | +0.321 |
| 0.15 | 480 | +0.330 | 46.2% | +5.88 | 7.5e-09 | +0.417 |
| 0.25 | 291 | +0.449 | 49.1% | +6.04 | 4.7e-09 | +0.509 |
| 0.35 | 157 | +0.440 | 51.6% | +4.06 | 7.9e-05 | +0.506 |
| 0.50 | 40 | +0.750 | 52.5% | +3.04 | 0.0042 | +0.800 |

Per season at conviction 0.25, the effect holds in all three holdout seasons:

| Season | n | Model CLV | t | p | Line-shopped CLV |
|---|---|---|---|---|---|
| 2023 | 87 | +0.339 | +2.37 | 0.020 | +0.397 |
| 2024 | 98 | +0.582 | +5.79 | 8.6e-08 | +0.628 |
| 2025 | 106 | +0.415 | +3.00 | 0.0034 | +0.491 |

### Totals CLV Results

Training target uses nflverse consensus close for source consistency across
all seasons; evaluation is reported against both consensus and Pinnacle close.

| Conviction | n | CLV vs consensus | t | CLV vs Pinnacle | t | p (Pinnacle) |
|---|---|---|---|---|---|---|
| 0.00 | 824 | +0.149 | +3.28 | +0.148 | +3.20 | 0.0014 |
| 0.25 | 302 | +0.376 | +4.91 | +0.407 | +5.28 | 2.5e-07 |
| 0.50 | 57 | +0.553 | +3.05 | +0.632 | +3.46 | 0.0010 |

Same monotonic conviction relationship as spreads.

### Critical Finding: Line Shopping Is Load-Bearing

Execution CLV against a single book (DraftKings) is **+0.012 points, t = 0.26,
statistically indistinguishable from zero**. The identical model, executed
across the full book set, returns +0.321.

The entire edge lives in the gap between the best available number and the
Pinnacle close. A model with genuine CLV signal that is executed at one
retail book captures none of it. This promotes line shopping from an
optimization to a hard precondition for deployment, and it means the
five-book minimum in the project principles is a floor, not a target.

### Critical Finding: The Signal Is Market Microstructure, Not Fundamentals

Feature ablation across the same walk-forward splits:

| Feature set | n features | corr(pred, move) at 0.25 | CLV at 0.25 | n bets |
|---|---|---|---|---|
| All | 137 | +0.307 | +0.449 | 291 |
| Market microstructure only | 21 | +0.278 | +0.368 | 389 |
| Fundamentals and context only | 116 | -0.087 | -0.019 | 27 |

Standalone, the 116 EPA, form, rest, and context features produce **no usable
signal**: only 27 games clear the conviction threshold at all, and their CLV
is negative. The dominant feature by gain is `pin_vs_consensus`, the deviation
of Pinnacle from the cross-book consensus at bet time. The model is largely
learning that the consensus converges toward the sharp book.

Fundamentals are not worthless. Adding them lifts correlation from 0.278 to
0.307 and CLV from +0.368 to +0.449 at the same threshold. But they are a
refinement on a market-microstructure core, not the engine. This extends the
earlier finding: fundamentals carry no signal beyond the closing line for game
margin, and they carry very little for predicting line movement either.

Implication for the roadmap: the elaborate PFF ingestion layer should be
re-justified before it is built. On current evidence its expected contribution
to spread and totals CLV is small, and PFF is the only paid data source in the
stack. The cheaper and higher-yield direction is more books and more frequent
snapshots, which directly strengthen the microstructure features that are
actually carrying the model.

### Honest Limitation: CLV Is Positive, ATS Is Not Yet

Against the bet-time number, the strategy's against-the-spread record is
**50.12% over 804 decided bets**, below the 52.38% breakeven at -110.

This is not a contradiction, but it must not be glossed. CLV is the leading
indicator and it is strongly significant. ATS at this sample size is close to
uninformative: detecting a 3% edge at 80% power needs roughly 2,178 bets, and
824 bets is about 38% of that. The correct reading is that the model reliably
acquires better numbers than the market closes at, and that this has not yet
converted into a measured win rate. Do not size up on the CLV result alone.

### Known Gaps

1. Pinnacle bet-time quotes are missing for 117 games (6.9%), concentrated in
   2020 and 2021 when Odds API book coverage was thinner.
2. Pinnacle closing totals cover 2023-2025 only. Earlier seasons fall back to
   nflverse consensus close.
3. DraftKings closing lines were not purchased, so execution CLV is measured
   bet-time DK against Pinnacle close rather than DK against DK.
4. ~~Weather is excluded from features.~~ **[RESOLVED 2026-08-15]** A genuine
   forecast-at-cutoff source now exists and is validated: Open-Meteo's
   `wind_speed_10m_previous_dayN`, the forecast as actually issued N days
   before kickoff. nflverse `temp` and `wind` remain observed conditions and
   still must never be used as features. See Forecast Validation below.
5. Moneyline CLV is not yet measured. `h2h` was dropped from the backfill to
   stay inside the credit budget.

---

## Efficiency Wall: Why Game Lines Will Not Produce +Units

This section documents a negative result. It is the most valuable finding in
the project so far because it redirects effort away from a dead end.

### The Points-to-Vig Arithmetic

CLV measured in points cannot tell you whether a bet is profitable. Breakeven
at -110 is 52.38%. An NFL spread point is worth roughly 3% of win probability
away from key numbers, so **roughly 0.8 points of CLV are required merely to
break even** on standard juice.

The movement model delivers +0.449 points at conviction 0.25. That is highly
significant and still not enough. This fully explains the earlier result of
strongly positive CLV alongside a 50.1% ATS record. The two were never in
conflict. Optimizing CLV in points was optimizing the wrong quantity.

Everything below therefore works in probability space: a discrete distribution
over integer margins, empirical key-number atoms, real per-book prices, and
output measured in units.

### Oracle Ceiling Analysis

The decisive experiment. Give the strategy **perfect knowledge of the Pinnacle
closing line** at bet time and measure the resulting ROI. This is an upper
bound no model can exceed.

| Truth estimator | n | Win rate | Flat ROI |
|---|---|---|---|
| Consensus bet-time (no model) | 546 | 46.34% | -5.60% |
| Pinnacle bet-time (no model) | 540 | 46.39% | -5.31% |
| Pinnacle + movement model | 541 | 47.25% | -3.58% |
| **ORACLE: actual closing line** | 569 | 51.08% | **+3.38%** |

The movement model does help, moving ROI from -5.31% to -3.58%. It is simply
nowhere near enough. And the ceiling itself is thin and unstable: the same
oracle returns +0.52% at a 2% EV threshold and +1.46% at 5%. The honest read
is a ceiling of roughly +1% to +3% ROI, achievable only with perfect
closing-line foresight.

### Bet Timing Does Not Open Value

Hypothesis tested: the market has already moved by Tuesday, so bet earlier.
Look-ahead lines were pulled at T-7, T-10, T-14, and T-21 days.

| Snapshot | n | sd vs close | mean abs vs close |
|---|---|---|---|
| Pinnacle T-21 days | 72 | 1.058 | 0.681 |
| Pinnacle T-14 days | 85 | 0.956 | 0.594 |
| Pinnacle T-10 days | 85 | 1.183 | 0.712 |
| Pinnacle T-7 days | 100 | 0.898 | 0.550 |
| Pinnacle Tuesday | 112 | 1.198 | 0.772 |

**Pinnacle's number three weeks out is as close to the eventual close as its
number on Tuesday.** There is no stale early window to exploit at the sharp
book. Pinnacle-only oracle ROI is negative at every single lead time.

The SBR archive suggested otherwise (open-to-Tuesday sd of 2.96), which would
have implied a large early edge. That figure is an artifact: SBR openers are
mixed-provenance look-ahead numbers carrying roughly a point of their own
measurement noise. Acting on it would have wasted a full backfill. This is the
second time SBR data has pointed the wrong way.

### Cross-Book Dispersion Is Real But Not Harvestable

Median 22 books quote each game; 67% of games show at least a full point of
cross-book line range. With oracle truth, shopping the best of 21 books turns
every lead time positive (+7% to +10% ROI). With any *realistic* truth
estimator it turns negative.

The gap is adverse selection. Predicted versus realized cover probability for
best-EV selections:

| Predicted p(win) bin | n | Predicted | Actual | Gap |
|---|---|---|---|---|
| 0.48 to 0.50 | 52 | 49.28% | 36.54% | -12.7 |
| 0.50 to 0.52 | 171 | 51.09% | 43.86% | -7.2 |
| 0.52 to 0.55 | 237 | 53.23% | 51.05% | -2.2 |

Selecting the maximum EV across roughly 44 book-and-side combinations selects
the quotes where our own truth estimate is most wrong. Diagnostically, the
selected bets sit at a line offset of exactly **0.00** versus consensus: the
apparent edge was coming entirely from price, not from beating any number.

### Middling Does Not Clear Vig

Betting the best home number and best away number simultaneously:

| Min middle width | n | Hit rate | ROI per unit staked |
|---|---|---|---|
| 0.5 | 798 | 2.38% | -1.81% |
| 1.0 | 493 | 3.85% | -1.96% |
| 1.5 | 231 | 4.33% | -1.82% |
| 2.0 | 111 | 6.31% | -2.55% |
| 2.5 | 38 | 7.89% | +0.28% |

Breakeven requires roughly a 9.1% hit rate at -110. Only widths of 2.5+ points
approach it, and those occur in 4% of games with a sample too small to trust.

### The One Confirmed Lever: Price

Median best available price at the consensus line is **-104**, not -110.

| Price | Breakeven win rate |
|---|---|
| -110 | 52.38% |
| -104 | 50.97% |
| -105 | 51.22% |

Systematically taking the best price hands over **1.4 points of win rate for
free**, with no model required. Book share of best-price selections was
dominated by matchbook, lowvig, and pinnacle. Two caveats: matchbook is an
exchange, so quoted prices are gross of roughly 2% commission and limited by
available liquidity; and reduced-juice books limit and restrict winners.

This halves the hurdle. It does not by itself create an edge, because a
random side at -104 still returns roughly -1.9%.

### Conclusion and Redirection

NFL game lines are the most efficiently priced market in North American
sports, and this analysis measures exactly how efficient. Perfect foresight of
the closing line yields 1% to 3%. Every realistic estimator loses. **Further
investment in spread and totals game-line modelling is not justified.**

Effort should move to markets where the same efficiency does not hold. The
concrete evidence for player props being the better target:

  * Only **6 books** quote props versus 21 for game lines, so pricing is far
    less arbitraged and books lean on their own numbers.
  * Cross-book line dispersion on player yardage props is a median of 1.5
    units with only 4+ books quoting, wide relative to the market.
  * Props **settle from free nflverse player statistics**, so ROI is measured
    directly against realized outcomes. No closing-line purchase is needed to
    evaluate profitability, unlike game lines.
  * nflverse supplies rich player-level inputs (target share, route
    participation, snap share, air yards, red-zone usage) that have no
    equivalent in the game-line feature set, where fundamentals were shown to
    contribute almost nothing.

Costing (confirmed empirically against the API): historical props are billed
at 10 credits per market, per region, per event, plus 1 credit per event
lookup. One season of three yardage markets across a full slate is roughly
8,600 credits.

---

## Feature Hunt: Is the Closing Line Wrong Anywhere?

The oracle analysis bounded strategies that *predict* the closing line. It did
not test whether the closing line is itself biased in identifiable subsets.
That is a separate question, and it is the one that found an edge.

Tested on nflverse closing lines for **7,276 games, 1999-2025** (4.3x the Odds
API sample, and free). Roughly 35 candidate rules were scanned, so a
Benjamini-Hochberg false-discovery correction was applied, and every candidate
was additionally required to survive a holdout era.

### Result: One Robust Edge, Several Dead Ends

**Wind suppresses scoring more than the market prices.** The dose-response is
monotonic, which is the signature of a real effect rather than a mined subset:

| Wind (mph) | n | Under rate | Total line | Actual total | Line minus actual |
|---|---|---|---|---|---|
| 0-4 | 1043 | 49.9% | 43.42 | 44.82 | -1.40 |
| 5-8 | 1867 | 47.7% | 42.89 | 43.97 | -1.08 |
| 9-11 | 931 | 51.9% | 42.63 | 43.06 | -0.43 |
| 12-14 | 606 | 55.1% | 42.45 | 42.41 | +0.04 |
| 15-17 | 385 | 55.1% | 42.10 | 40.79 | +1.31 |
| 18-20 | 172 | 61.1% | 41.81 | 40.48 | +1.33 |
| 21+ | 117 | 57.3% | 40.85 | 38.65 | +2.20 |

The mechanism is explicit. The market **does** adjust for wind, moving the
total from 43.42 to 40.85 across the range, about 2.6 points. Actual scoring
falls 6.2 points over the same range. **The market captures roughly 40% of the
true wind effect.**

Detrended against the same-season baseline under rate, to remove era drift in
scoring: wind >= 15 runs **+6.60% excess**, wind < 9 runs -1.99% excess.

### Strict Out-of-Sample Validation

Rule frozen on 1999-2015, tested on 2016-2025:

| Threshold | In-sample | Out n | Out under% | p | ROI @-110 | ROI @-104 |
|---|---|---|---|---|---|---|
| wind >= 12 | 55.16% | 408 | **58.09%** | 0.023 | +10.90% | +13.94% |
| wind >= 13 | 55.18% | 316 | 58.23% | 0.042 | +11.16% | +14.22% |
| wind >= 15 | 57.42% | 202 | 55.94% | 0.325 | +6.80% | +9.73% |

Out-of-sample exceeds in-sample, the opposite of an overfit. Bootstrap on the
out-of-sample window gives a 95% CI of [53.4%, 63.0%] and P(rate > breakeven)
= 0.992.

**The 12 mph threshold is preferred**, not 15. It produces the best
out-of-sample rate and roughly double the bet volume.

### This Beats the Closing Line, Not a Slow Market

Critical distinction: the under rate above is measured **against the closing
total**, when the wind forecast has already been public for days. This is not
a race to beat a market that has not yet adjusted. It is a standing closing-
line inefficiency.

Betting earlier still helps, because the market partially corrects during the
week:

| Benchmark (2023-2025, wind >= 12) | n | Under rate |
|---|---|---|
| vs Pinnacle bet-time total | 97 | 58.76% |
| vs Pinnacle closing total | 104 | 54.81% |
| vs nflverse consensus close | 106 | 54.72% |

### Forecast Validation (completed 2026-08-15)

**[SUPERSEDED]** The previous version of this section simulated forecast error
by adding Gaussian noise to observed wind, and stated that Open-Meteo archives
issued forecasts from 2022 pending domain allowlisting. Both the availability
claim and the noise model have now been replaced with measurements.

#### What Open-Meteo actually provides

`historical-forecast-api.open-meteo.com` works. But `wind_speed_10m_previous_dayN`,
the only leakage-free historical forecast, is **null before 2024-01-18** and
complete from 2024-02. Verified month by month. Before that date the endpoint
returns only its assembled best-estimate series, which is initialised from the
most recent run and is effectively analysis. Using that as a "Tuesday forecast"
is soft leakage. `previous-runs-api.open-meteo.com` is not reachable from the
project sandbox.

#### nflverse `wind` is not the same measurement as Open-Meteo

Checked for the first time here, and it matters more than the forecast question.

| Comparison | n | corr | bias | sd of difference |
|---|---|---|---|---|
| ERA5 at kickoff hour vs nflverse, 2016-2025 | 1,794 | 0.688 | -0.06 | 3.87 |
| Open-Meteo analysis vs nflverse, 2024-25 | 371 | 0.771 | -0.77 | 2.88 |

The two sources agree on the `>= 12` flag only **85.8%** of the time. There is
an irreducible source-disagreement floor of roughly 3.9 mph sd underneath any
forecast error, which the old Gaussian simulation did not model at all.

#### The rule survives on an independent wind source

The decisive test. 2016-2025 outdoor games, under rate against the closing total:

| Wind source | n | Under rate | 95% CI | ROI @ -110 |
|---|---|---|---|---|
| nflverse observed `wind` >= 12 | 408 | 58.09% | [53.2, 62.7] | +10.90% |
| **ERA5 reanalysis >= 12** | 354 | **59.32%** | [54.2, 64.4] | +13.25% |
| ERA5, rate-matched threshold (>= 11.40) | 414 | 59.66% | [54.8, 64.5] | +13.90% |

And the games where the sources disagree both hit: ERA5-only 62.1% (n=87),
nflverse-only 59.0% (n=166), both 57.4% (n=242). If this were an artifact of
nflverse's reporting, the ERA5-only bucket would be flat. It is the best bucket
in the table. **The effect is physical wind.**

#### Measured forecast error, replacing the assumed Gaussian

From 298,944 matched hourly forecast/ERA5 pairs:

| Lead | Bias | sd | MAE |
|---|---|---|---|
| Day 1 | +0.21 | 2.61 | 1.97 |
| Day 3 | +0.44 | 2.98 | 2.24 |
| Day 5 | +0.38 | 3.63 | 2.72 |

The old simulation's sd of 2 to 3 for a 2-to-3 day forecast was well calibrated.
What it missed is that the error is heteroscedastic and shrunk toward
climatology. Day-3 error conditional on true wind runs +1.51 at 0-4 mph and
-2.95 at 18-22 mph: forecasts over-call calm and under-call wind.

**Sign warning.** The table above is `E[forecast - truth | truth]`. Live you
observe the forecast, not the truth, and the valid correction is
`E[truth | forecast]`, which has the OPPOSITE sign: conditioning on a high
forecast, true wind regresses DOWN, because an extreme forecast is partly
extreme noise. At lead 3 a 12-14 mph forecast corresponds to 10.7 mph actual.
Both tables live in `data_ingest/weather.py`; only the second is applied, and
only as a diagnostic. Getting this backwards inflates wind and fires the rule
on far too many games.

#### Powered validation

Applying archived forecasts directly to 2024-25 gives n~70 and is useless. So
instead: resample the measured error, conditioned on true wind level, onto ERA5
wind across the full 2016-2025 sample and re-run the frozen rule. Intervals
bootstrap over games and forecast noise jointly.

| Lead | Threshold | Bets/season | Under rate | 95% CI | ROI @ -110 | P(beat vig) |
|---|---|---|---|---|---|---|
| Day 1 | 12 | 36.5 | 57.63% | [52.6, 62.6] | +10.02% | 0.980 |
| **Day 3** | **11** | **49.2** | **56.71%** | [52.3, 61.1] | +8.26% | 0.972 |
| **Day 3** | **12** | **38.5** | **57.09%** | [52.4, 61.9] | +9.00% | 0.975 |
| Day 5 | 12 | 34.6 | 56.17% | [51.0, 61.7] | +7.24% | 0.916 |
| *Perfect ERA5 knowledge >= 12* | | *35.4* | *59.32%* | | *+13.25%* | |

**Real forecast error costs about 2.2 points of win rate, not the rule.**

#### The direct 2024-25 test is uninformative

Reported so it is not re-run: nflverse baseline on the same games 47.30% (n=74),
day-1 forecast 54.69% (n=64), day-3 46.48% (n=71), day-5 45.28% (n=53). Every
interval spans roughly 35% to 70%. These are also the two losing seasons in the
record below, so the test cannot separate "forecasts degrade the rule" from
"these seasons lost". Do not cite any row of it.

### Season-by-Season, and the Reason for Caution

Out-of-sample, wind >= 12, flat 1 unit at -110:

| Season | Bets | Under rate | Units |
|---|---|---|---|
| 2016 | 38 | 44.7% | -5.55 |
| 2017 | 42 | 64.3% | +9.55 |
| 2018 | 37 | 64.9% | +8.82 |
| 2019 | 49 | 57.1% | +4.46 |
| 2020 | 42 | 47.6% | -3.82 |
| 2021 | 60 | 65.0% | +14.46 |
| 2022 | 34 | 70.6% | +11.82 |
| 2023 | 32 | 71.9% | +11.91 |
| 2024 | 38 | 47.4% | -3.64 |
| 2025 | 36 | 47.2% | -3.55 |
| **Total** | **408** | **58.1%** | **+44.45** |

Average +4.45 units per season, with 4 of 10 seasons losing.

**The last two seasons both lost.** At roughly 37 bets per season the standard
error is about 8%, so 2024 and 2025 combined sit about 1.9 SE below
expectation, which is not conclusive decay but is not nothing either. Two
readings are live: ordinary variance in a small annual sample, or the market
finally pricing wind correctly. These cannot be separated yet. Size
accordingly and monitor. Do not extrapolate the 2021-2023 run, which is the
part of the record most likely to be flattered by luck.

### Rejected Candidates

Recorded so they are not re-litigated later.

| Candidate | Verdict |
|---|---|
| Backup QB starting | **Lookahead artifact.** Defining "backup" from full-season starts gave 56.75% (p=0.004). A causal definition using only prior games collapses it to 51.79% (p=0.70), era-unstable. Dead. |
| Home underdog >= 7 | 55.8% overall but era-unstable (57.6, 55.2, 46.7, 62.8). ~110 games per era. Noise. |
| Cold weather unders | **Reversed.** At temp <= 35 with wind < 12, actual totals exceed the line by 2.4 points and overs hit 55.2%. The popular "cold means under" belief is wrong. The over version is era-unstable (n=348) and not tradable. |
| Referee totals tendency | Nothing. Causal prior-game referee history gives 50.0% and 51.1% on the two extreme buckets. |
| Divisional rematch | Nothing. Meeting 1 under 53.3%, meeting 2 under 50.2%. |
| Temperature generally | No monotonic effect once wind is controlled. |
| Rest, bye weeks, primetime, playoffs, big favorites, big dogs, key numbers, week 1-4 | All at or below breakeven. Several are significantly negative, meaning the market prices them correctly and the naive side loses to vig. |

### Deployment Notes

  * **Threshold units matter.** The published rule is `nflverse wind >= 12`.
    Live you have an Open-Meteo forecast, not nflverse, and the two are not the
    same measurement. The rate-matched equivalent is **11.40 on the Open-Meteo
    scale**; deployment uses **11**, which buys 28% more volume for 0.4 points
    of win rate. Apply the threshold to the RAW forecast: that is how it was
    validated, and thresholding a debiased value silently changes the selection.
  * This is a **totals-only** play. Wind does not move the spread: home cover
    rate is 48.8%, 49.4%, and 48.9% in calm, moderate, and high wind.
  * At 58% and -110, full Kelly is 12.0% of bankroll, so the project's 25%
    fractional Kelly lands at 3.0% and the flat cap binds. The cap should
    stay binding here; do not lift it on the strength of one rule.
  * Volume is roughly 41 bets per season. This is a small, low-capacity
    program, and totals limits are lower than side limits at most books.
  * Reduced juice matters as always: -104 instead of -110 lifts ROI from
    +10.9% to +13.9% on the same bets.
  * Wind is unavailable for about 5% of outdoor games in nflverse, and those
    games have higher totals (44.65 vs 42.76) and a higher under rate. Minor
    selection concern in the backtest; irrelevant in live use where a forecast
    is always available.

---

## Correction: The Opener IS Mispriced (Earlier Finding Was a Measurement Artifact)

An earlier section concluded there was no exploitable early-week window,
based on Pinnacle's line at T-7, T-10, T-14 and T-21 being as close to the
close as its Tuesday number. **That conclusion was wrong, and the error was in
the sampling design, not the data.**

Two flaws:

1. It sampled **Pinnacle**, which does not post until roughly 6.5 days out.
   Every "T-21 Pinnacle" observation was really a mature number captured at a
   later moment, not an opener.
2. It sampled at **arbitrary fixed timestamps**, never at the moment a book
   first posts a line. An opener that exists for a few hours is invisible to a
   snapshot taken on a fixed grid.

### Books Do Not Open at the Same Time

Dense 6-hourly scan from T-25 to T-3 days, 2024 weeks 8 and 12, 29 games,
21 books, first-posted line identified per (game, book):

| Book cohort | Median open (days out) | MAE vs close | sd | share 2+ pts off |
|---|---|---|---|---|
| BetOnline, lowvig, FanDuel, DraftKings, 1xBet, 888, WilliamHill | 11.7 | 1.57 | 2.41 | 35.1% |
| Pinnacle, Bovada, Matchbook, BetMGM, Nordicbet, Coolbet | 6.5 | 2.02 | 3.83 | 30.6% |
| *Pinnacle mature number (earlier measurement)* | - | *0.55-0.77* | *0.9-1.2* | - |

**First-posted numbers sit 2 to 3 times further from the close than a mature
Pinnacle number.** The soft and offshore books post first; the sharp book
arrives roughly five days later, by which time the early numbers have been
shaped. This is precisely the structure that makes opener betting viable.

### Openers Correct Slowly

Comparing each book's first posted number to the same book 24 hours later:
mean absolute error moves from 1.649 to 1.569. **Only 4.8% of the initial
error is corrected within a full day.** The correlation between the first-24h
move and the direction of the initial error is +0.398, so the number does
drift the right way, but slowly.

Operationally this matters a great deal: capturing opener value does **not**
require sub-second execution. It requires being in the window at all, which is
a far lower engineering bar than the folklore suggests.

### The Exploitable Signal: Sharp-vs-Soft Deviation

Being far from the close is worthless unless the direction is predictable. It
is, once Pinnacle posts. For every snapshot where a soft book and Pinnacle
both have a live number, define `dev = soft_line - pinnacle_line` and bet the
side Pinnacle favours, at the soft book's number.

One bet per (game, book) at the first qualifying moment:

| Threshold | n | Mean CLV (pts) | t | p | ATS |
|---|---|---|---|---|---|
| abs(dev) >= 1.0 | 98 | +0.811 | +4.09 | 0.0001 | 42.86% |
| abs(dev) >= 2.0 | 20 | +2.075 | +4.14 | 0.0006 | 80.00% |

**This is the first strategy in the project to clear the vig hurdle on CLV
grounds.** Recall the arithmetic: roughly 0.8 points of CLV are needed to break
even at -110. The Tuesday movement model produced +0.449 and could never get
there. Early-week sharp-vs-soft deviation produces +0.81 to +2.08.

Deviation frequency: `abs(dev) >= 1` occurs in 14.3% of paired observations,
`>= 2` in 2.7%. Across ~20 books that implies meaningful volume, on the order
of 200 qualifying bets per season at the wider threshold.

### What Is NOT Yet Established

  * **ATS is pure noise at this sample.** 42.86% at one threshold and 80.00%
    at the other, on 98 and 20 bets from 29 games. These numbers carry no
    information. Only the CLV result is currently supported.
  * **The apparent home drift is not established.** First-posted lines sit
    0.509 points less home-favoured than the close, which looks overwhelming
    at t = -5.30 across 538 book-quotes. But book-quotes within a game are not
    independent. Collapsed to one observation per game the same effect gives
    t = -1.24, p = 0.22 on 29 games. Not significant. Do not trade it.
  * Sample is two weeks of one season. Everything here needs a multi-season
    scan before sizing.
  * `betanysports` was excluded: its first-posted error had sd 10.3, i.e.
    stale or malformed quotes rather than real prices.

### Execution Constraints (the real reason this is hard)

The statistical edge is not the binding constraint. These are:

  * Early-week limits at soft books are small, often a few hundred to a couple
    of thousand dollars.
  * Books that lose to early sharp action limit or close accounts quickly, and
    the books opening earliest are exactly the ones most sensitive to it.
  * Requires monitoring ~20 books continuously through a multi-day window
    rather than pulling one Tuesday snapshot.
  * Capacity is low. This is an edge that compounds a modest bankroll, not one
    that absorbs size.

### Next Experiment (costed)

Scan T-7 to T-2 days at 6-hour resolution, which is the window where Pinnacle
is live and soft books are still stale. 20 snapshots per week, `regions=us,eu`,
`markets=spreads`, 20 credits each = 400 credits per week, roughly 8,800 per
season. Three seasons is about 26,400 credits, well inside the current balance
of ~95,800. That yields on the order of 600 qualifying bets, enough to test
ATS profitability rather than only CLV.

---

## CRITICAL DATA DEFECT: Home/Away Sign Flips in Four Books

A defect was found in The Odds API spreads feed that **contaminated the two
headline conclusions of this document in opposite directions**. It is recorded
here in full because every line-shopping analysis must screen for it.

### The Defect

Four books return spreads with the home and away sides transposed on a subset
of records. Example, BAL vs CLE, Week 18 2024, same event, same snapshot:

| Source | Home handicap (nflverse orientation) |
|---|---|
| Pinnacle | +18.0 (home favored by 18) |
| betanysports | -17.5 (home a 17.5-point underdog) |

Equal magnitude, opposite sign. This is not a mispriced line, it is a
transposed one. Detection rule:

```python
flip = (book_line + pinnacle_line).abs() <= 1 and pinnacle_line.abs() >= 3
```

Prevalence and dispersion, T-7 to T-2 window, 2023-2025:

| Book | n | Flip rate | dev sd |
|---|---|---|---|
| betanysports | 5850 | 12.43% | 4.395 |
| betsson | 7764 | 0.48% | 2.875 |
| nordicbet | 16049 | 0.37% | 2.243 |
| tipico_de | 10477 | 0.12% | 1.045 |
| draftkings / fanduel / betmgm / bovada / matchbook | - | <0.1% | 0.63-0.76 |

**Exclude `betanysports`, `betsson`, `nordicbet`, `tipico_de` from any
analysis that selects on cross-book deviation.** The flip rate understates the
damage: any selection procedure that picks extreme quotes will
over-sample these books by a large factor.

### Impact 1: The Efficiency Wall Was Overstated

The Tuesday EV backtest, re-run with the four books removed:

| Truth estimator | Originally reported | Defective books excluded |
|---|---|---|
| Pinnacle bet-time | 46.39% win, **-5.31% ROI** | 49.73% win, **+0.66% ROI** |
| ORACLE: actual close | 51.08% win, **+3.38% ROI** | 53.77% win, **+8.07% ROI** |

Two corrections follow:

1. **The "adverse selection" finding was largely an artifact.** Betting into a
   sign-flipped quote means betting the wrong side by construction, which
   manufactures sub-50% results. 16.7% of originally selected bets came from
   defective books. Cleaned, realistic performance is roughly breakeven rather
   than a 5-point loss.
2. **The oracle ceiling more than doubles, from +3.38% to +8.07% ROI.** The
   earlier statement that "perfect closing-line foresight yields only 1% to 3%"
   is wrong. The correct ceiling is around 8%, which is a workable target.

The conclusion that game lines should be abandoned is therefore **withdrawn**.
The honest position is: realistic strategies currently sit near breakeven, and
the gap to an 8% ceiling is what better truth estimation could capture.

### Impact 2: The Opener Finding Shrinks but Survives

The sharp-vs-soft opener result reported earlier (+2.075 CLV, 80% ATS) was
driven almost entirely by the defective books: nordicbet, tipico_de and
betsson supplied 651 of the qualifying bets. Re-run on 29 clean books,
2023-2025, one bet per game at the largest deviation:

| Threshold | n | CLV | ATS | p(ATS) | ROI @-110 |
|---|---|---|---|---|---|
| abs(dev) >= 0.5 | 855 | +1.291 | 57.70% | 0.0021 | +10.16% |
| abs(dev) >= 1.0 | 652 | +1.569 | 56.77% | 0.0252 | +8.38% |
| abs(dev) >= 1.5 | 361 | +2.310 | 56.27% | 0.1536 | +7.42% |

**Do not read the CLV column as evidence.** It is close to mechanical: CLV is
computed against the close, the close is close to Pinnacle, and the bet is
placed at the maximum deviation from Pinnacle, so CLV is approximately equal
to `abs(dev)` by construction. Only the ATS column carries information.

Sanity check on magnitude: getting a number 1.3 points better than close is
worth roughly 4 points of win probability, implying about 54% ATS. Observed is
57.7%, higher than theory but with a wide interval. The effect is plausible
and directionally consistent, not yet confirmed.

Per (game, book) rather than per game, the relationship is **not monotonic**
in the threshold (53.55%, 50.08%, 52.92%, 57.98% at 0.5/1.0/1.5/2.0), which is
a warning sign that some of this is still noise.

### Correction: Priced At What The Books Actually Quoted (2026-08-15)

**[SUPERSEDED]** The ROI column above assumes -110. It should not. Two further
method fixes were applied at the same time.

**Look-ahead in the selection.** "One bet per game at the largest deviation"
requires knowing which snapshot in the window turns out most extreme. Replaced
with the first qualifying moment, which is implementable live. The result barely
moves, so the look-ahead was not driving the finding, but all figures below use
first-qualifying.

**The right benchmark is not 50%.** CLV here is close to mechanical. What matters
is whether ATS beats the cover probability implied by the line advantage alone,
computed from the empirical margin-versus-close residual distribution
(n=7,276, mean +0.09, sd 13.20).

One bet per game, 853 games, 29 clean books, 2023-2025:

| Threshold | n | Mean CLV | ATS | Expected from line | Excess | 95% CI on excess |
|---|---|---|---|---|---|---|
| 0.5 | 835 | 0.51 | 55.69% | 51.17% | +4.52 | [+1.3, +7.8] |
| **1.0** | **593** | **0.89** | **58.18%** | **52.40%** | **+5.78** | **[+1.8, +9.6]** |
| 1.5 | 297 | 1.68 | 56.23% | 54.76% | +1.47 | [-4.5, +6.9] |
| 2.0 | 150 | 2.58 | 62.00% | 57.37% | +4.63 | [-3.0, +12.4] |

Placebo with DraftKings as the reference book instead of Pinnacle shows no
excess at any threshold (-0.25, +1.77, -2.59, -1.98, all straddling zero), so
the effect is specific to Pinnacle. Leave-one-book-out at threshold 1.0 keeps
the excess between +5.04 and +6.17 with the interval excluding zero in all
eight cases.

**Now the prices.** Books do not quote -110 on a line a point off Pinnacle:

| Threshold | Median price | Mean price | Break-even WR | Line value alone | ROI at actual prices | 95% CI |
|---|---|---|---|---|---|---|
| 0.5 | -115 | -115.9 | 53.79% | 51.17% | +3.53% | [-2.8, +9.8] |
| 1.0 | -115 | -124.0 | 54.47% | 52.40% | **+6.98%** | **[-0.6, +14.5]** |
| 1.5 | -115 | -137.0 | 55.62% | 54.76% | +1.45% | [-8.8, +11.9] |
| 2.0 | -115 | -155.0 | 57.08% | 57.37% | +9.82% | [-4.4, +23.6] |

Read "line value alone" against "break-even WR". At every threshold the juice
charged is very close to what the better number is worth. **The books price
their alternate lines correctly.** All realised profit therefore comes from the
Pinnacle-direction excess, none from the number itself.

Headline ROI is **+6.98%, not +8.38%**, and the interval touches zero. Three
seasons, 597 bets at threshold 1.0, +41.41 units at actual prices: 2023 +8.18,
2024 +29.00, 2025 +4.23. Roughly 70% of the profit is one season, and ATS
declines monotonically 2023 to 2025 at the 0.5 and 1.5 thresholds. Still the
best thing in the project; not a settled edge.

Reproduce with `python scripts/backtest_opener.py --placebo draftkings`.

### Process Lesson

Three separate findings in this project have now been reversed by data quality
rather than by modelling: the SBR closing column swap, the SBR opener noise
that falsely implied a large early window, and now the sign-flip defect.
Every future analysis that selects on extreme values must first run a
per-source integrity screen, because **selection procedures preferentially
sample corrupted records**. A defect present in 0.4% of rows can supply 15% of
selected bets.

---

# Runbook: Wind Totals

The only strategy in this project currently cleared for live money. Roughly 35
to 49 bets a season depending on threshold, expected +8% to +9% ROI at -110 and
+11% to +12% at -104. That is about 4 to 6 units a season at a 1% flat stake.
Small, and real.

## Why this can be bet late

The edge is measured **against the closing total**, when the wind forecast has
been public for days. It is a standing closing-line inefficiency, not a race
against a market that has not yet adjusted. Betting later is if anything better,
because forecast skill improves: day-1 scores 57.63% against day-3's 57.09% and
day-5's 56.17%. Do not confuse this with the opener strategy, whose edge IS
staleness and which therefore must be bet a week out.

## Weekly routine

    export THE_ODDS_API_KEY=...
    python scripts/weekly_wind_card.py --days 4          # Thursday, scan the slate
    python scripts/weekly_wind_card.py --days 2          # Saturday, firm forecast
    python scripts/weekly_wind_card.py --days 1 --regions us,eu   # Sunday morning, place

Cost is 1 credit per run at `regions=us, markets=totals`. Run it as often as you
like; the constraint is bankroll discipline, not credits.

Output is a printed card plus `data/cards/wind_card_YYYY-MM-DD.csv` with the
line, book, price, model probability, de-vigged market probability, edge, EV and
stake for each qualifying game.

## The rule, precisely

1. Outdoor games only. `roof in {dome, closed}` is excluded, and the script
   fails loudly on a stadium with no coordinates rather than dropping it.
2. Forecast wind at **kickoff hour**, not a game-window mean. Kickoff hour
   correlates 0.771 with observed wind against 0.730 for the 4-hour mean, and
   the rule scores 59.32% on it against 57.88%.
3. Threshold on the **raw forecast** at **11 mph** (Open-Meteo scale).
4. Bet the **UNDER**. Never the spread.
5. Take the highest total available, then the best price at that total, across
   the 29 clean books.
6. Minimum edge 3% after de-vig. Stake at 25% fractional Kelly, hard-capped at
   1% of bankroll. **The cap should bind on nearly every bet. Do not lift it.**

## Failure modes to watch

  * **`api.open-meteo.com` unreachable.** The live host is blocked in some
    sandboxed environments (403 via proxy) while the archive and historical
    hosts work. Run the live card from a machine with open egress.
  * **A new stadium appears.** International games and relocations add
    `stadium_id` values. `coverage_check` raises rather than silently skipping.
    Add coordinates to `STADIUM_COORDS`.
  * **A new book appears in the feed.** Re-run `scripts/screen_books.py`. Four
    books carry home/away sign flips and any selection on extremes over-samples
    them by a large factor.
  * **matchbook quoting best.** It is an exchange; the price is gross of roughly
    2% commission. The card flags this.
  * **Totals limits.** Lower than side limits at most books. This is a
    low-capacity program.

## Monitoring, and the live risk

2024 and 2025 both lost: -8.09u and +1.73u at -110 in ERA5 terms, -3.64u and
-3.55u as published on nflverse wind. At roughly 35 bets a season the standard
error is about 8%, so two seasons is not conclusive, but it is not nothing.

Two readings are live and cannot yet be separated: ordinary variance, or the
market finally pricing wind correctly. The discriminating test is whether the
market's wind adjustment is growing. Track the slope of closing total against
forecast wind season by season. If the market's captured share moves up from
roughly 40%, the edge is closing and the rule should be retired rather than
re-tuned.

Regression test before trusting any change:

    python scripts/replay_wind_card.py --season 2024 --week 12 --lead 3 --settle
    python scripts/validate_wind_forecast.py --section sim

## Next version

Make wind continuous rather than a threshold. The dose-response shows the market
captures only about 40% of the true wind effect across the whole range, not just
above 12 mph. Modelling expected total against forecast wind and betting the gap
turns roughly 180 outdoor games a season into candidates instead of 35, uses the
same plumbing, costs no credits, and is late-bettable for the same reason. It
needs a walk-forward holdout before any money goes near it.
