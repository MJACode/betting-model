# models/saved keep-list

The default checkout tracks **live scoring artifacts** plus one documented
exception. Everything else matching `models/saved/*_YYYYMMDD_HHMMSS.pkl` is
gitignored (and removed from the index with `git rm --cached`) so new clones
stay thin. Bytes remain in git history. `nfl_prop_params.json` stays tracked.

**Do not gitignore `nfl/data/odds_cache/`.** That tree is irreplaceable.

## How a path gets here

`load_model` opens `model_registry.model_path` where `is_active = 1`. The
keep-list is that set, not "newest filename per model_id". #710's first
gitignore used newest-filename and would have dropped the live WNBA assists
artifact (`20260531_125558`) in favour of an unregistered NB experiment
(`20260831_213734`).

Paused models still score NONE rows and still load; their active pkls stay.
Retired models (`config.RETIRED_MODELS`) have no active registry row and no
pkl in this list.

Verified against production `model_registry` on 2026-09-14 (Supabase
`execute_sql`, project Betting Model). Re-verify before the next diet.

## Keep (tracked)

```
models/saved/mlb_f5_moneyline_20260903_163809.pkl
models/saved/mlb_f5_over_under_20260508_091542.pkl
models/saved/mlb_f5_runline_20260508_092705.pkl
models/saved/mlb_live_total_runs_20260908_230751.pkl
models/saved/mlb_moneyline_20260903_182812.pkl
models/saved/mlb_over_under_20260704_104508.pkl
models/saved/mlb_prop_batter_hits_20260621_072613.pkl
models/saved/mlb_prop_batter_runs_20260903_205632.pkl
models/saved/mlb_prop_batter_sb_20260611_182551.pkl
models/saved/mlb_prop_batter_tb_20260621_075327.pkl
models/saved/mlb_prop_batter_walks_20260904_010357.pkl
models/saved/mlb_prop_pitcher_er_20260513_155339.pkl
models/saved/mlb_prop_pitcher_hits_20260903_230550.pkl
models/saved/mlb_prop_pitcher_k_20260903_190319.pkl
models/saved/mlb_prop_pitcher_outs_20260903_233111.pkl
models/saved/mlb_prop_pitcher_walks_20260620_164336.pkl
models/saved/mlb_runline_20260823_105841.pkl
models/saved/nba_moneyline_20260619_120533.pkl
models/saved/nba_prop_player_assists_20260619_140445.pkl
models/saved/nba_prop_player_blocks_20260619_155307.pkl
models/saved/nba_prop_player_dd_20260619_172853.pkl
models/saved/nba_prop_player_points_20260619_124633.pkl
models/saved/nba_prop_player_pra_20260619_152317.pkl
models/saved/nba_prop_player_rebounds_20260619_132555.pkl
models/saved/nba_prop_player_steals_20260619_162228.pkl
models/saved/nba_prop_player_threes_20260619_143841.pkl
models/saved/nba_prop_player_turnovers_20260619_165437.pkl
models/saved/ncaaf_moneyline_20260821_113517.pkl
models/saved/ncaaf_over_under_20260825_204305.pkl
models/saved/ncaaf_spread_20260828_103438.pkl
models/saved/ncaaf_spread_premium_20260828_103439.pkl
models/saved/nfl_prop_anytime_td_20260907_034919.pkl
models/saved/nfl_prop_pass_attempts_20260906_232300.pkl
models/saved/nfl_prop_pass_completions_20260906_234411.pkl
models/saved/nfl_prop_pass_tds_20260907_000722.pkl
models/saved/nfl_prop_pass_yards_20260906_222207.pkl
models/saved/nfl_prop_rec_yards_20260907_014520.pkl
models/saved/nfl_prop_receptions_20260907_024950.pkl
models/saved/nfl_prop_rush_attempts_20260907_012725.pkl
models/saved/nfl_prop_rush_rec_yards_20260907_030837.pkl
models/saved/nfl_prop_rush_yards_20260907_001931.pkl
models/saved/nfl_prop_sacks_20260907_052908.pkl
models/saved/nfl_prop_tackles_assists_20260909_160911.pkl
models/saved/nhl_moneyline_20260621_185312.pkl
models/saved/nhl_moneyline_regulation_20260621_190032.pkl
models/saved/ufc_method_of_victory_20260619_211955.pkl
models/saved/ufc_moneyline_20260619_211307.pkl
models/saved/ufc_total_rounds_20260619_211436.pkl
models/saved/wnba_moneyline_20260531_120224.pkl
models/saved/wnba_over_under_20260719_113025.pkl
models/saved/wnba_prop_player_assists_20260531_125558.pkl
models/saved/wnba_prop_player_assists_20260831_213734.pkl
models/saved/wnba_prop_player_points_20260719_114702.pkl
models/saved/wnba_prop_player_pra_20260719_115815.pkl
models/saved/wnba_prop_player_rebounds_20260531_124906.pkl
models/saved/wnba_prop_player_threes_20260719_115218.pkl
models/saved/wnba_spread_20260719_113238.pkl
```

## Exceptions that are not `is_active = 1`

- `wnba_prop_player_assists_20260831_213734.pkl` — unregistered Negative
  Binomial head (`nb_r=13.56`). `tests/test_wnba_prop_market.py` asserts it
  remains on disk; the scorer does not load it. Do not drop it without
  rewriting those tests. The live assists path is `20260531_125558`.

## After a retrain

1. `git add -f models/saved/<model_id>_<new>.pkl`
2. Add a `!models/saved/<new>.pkl` line in `.gitignore` and here.
3. `git rm --cached models/saved/<old>.pkl` (file can stay on disk).
4. Remove the old `!` line and the old MANIFEST row.

`docs/local_ops.md` carries the same sequence.
