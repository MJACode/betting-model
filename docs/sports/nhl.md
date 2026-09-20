# NHL — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> **Read `docs/nhl_market_research.md` first (2026-09-20).** The 2026-06-21
> holdout numbers in the table below were produced on season-final inputs. On
> the rebuilt inputs `nhl_moneyline` walks forward at AUC 0.585 and a log loss
> no better than quoting the home-win rate. The six defects that doc lists
> (team ids, the September season label, the goalie lookup, "GSAA", the 3-way
> market key, the missing 2025-26 season) were fixed the same day; the
> sections below marked **(2026-09-20)** describe the pipeline as it is now.

### Inputs as they are now (2026-09-20)

- **Per-game logs**, from the NHL's free stats API (`?isGame=true`), in
  Supabase: `nhl_team_game_log`, `nhl_goalie_game_log`, `nhl_skater_game_log`
  (2017-18 → 2025-26 team and goalie; skaters 2018-19 →). Importer:
  `data/ingestors/nhl_game_logs.py` (`--seasons A B --apply`, `--no-skaters`
  for the fast pass, `--recent N` for the daily top-up). Skater reports are
  capped at 10,000 rows a call, so they are pulled a week at a time and a
  capped page is refused. `totalShotAttempts` is NULL before 2022-23; the 5v5
  counts (`sat_for_5v5`) go back the whole way and are what Corsi uses.
- **One function rates goalies and teams for training and for scoring**:
  `data/nhl_asof.py`. Strictly before the date asked about. A goalie's save%
  and GAA are taken over this season and last and regressed to the league
  (500 shots / 600 minutes); `gsaa` is real goals saved above average, this
  season only; the `_last5` columns are his last five starts. A team's shot
  share, power play, penalty kill and shot rates are
  `(n·current + 25·prior) / (n + 25)` on games played.
  `python -m data.nhl_asof --seasons 2019 2026 --apply` rebuilds history;
  `run_nhl_stats_ingestor` tops the logs up and calls the same functions.
- `nhl_goalie_stats` now holds **one row per team per game — the starter's
  line before that game** (20,770 rows 2019-2026), not one row per season.
  The pre-rebuild rows are in `nhl_goalie_stats_pre_asof_20260920`; the live
  2026 team rows the rebuild replaced are in `nhl_team_stats_live_2026_20260920`.
- **Season label**: `data/season_labels.nhl_season_label` — the new season
  starts in SEPTEMBER (2026-27 opened 09-29). The October rule is gone.
- **A team's first game of a season is `is_early_season = 1`.** It used to read
  last season's final row (`games_played 82`) and come out 0.
- **Known gap:** `games` holds no 2020 bubble playoffs (it stops 2020-03-11);
  the logs do (130 games).

## 24. NHL — Pipeline Operations
### Models (moneyline + regulation LIVE — trained 2026-06-21; O/U + puckline blocked)

| Model ID | Type | Market | Odds source | Status |
|---|---|---|---|---|
| `nhl_moneyline` | binary XGBoost + Platt | h2h | real DK h2h (bulk feed) | **LIVE** — holdout 2025 acc 60.4% / AUC 0.642 / CalErr 5.09% (6870 train rows); backtest 942 bets 64.2% +22.6% (prob-only synthetic −110 — directional only, NHL favorites are heavily juiced) |
| `nhl_moneyline_regulation` | **3-class** XGBoost (`multi:softprob`) + calibrated | h2h_3way | real DK 3-way (per-event endpoint) | **LIVE** — holdout acc 50.0% / OvR-AUC 0.596 / CalErr 2.55% |
| `nhl_over_under` | binary XGBoost + Platt | totals | real DK totals | BLOCKED — "no training data" (target needs historical total_line; trains once live DK lines accrue) |
| `nhl_puckline` | binary XGBoost + Platt | spreads (±1.5) | real DK puck line | BLOCKED — same (needs historical spread_home) |

**Trained 2026-06-21 after fixing 4 stacked ingestion bugs that had silently blocked NHL (see session log):** (1) `/schedule` games carry no `gameDate` (it's on the gameWeek day) → 0 games upserted; (2) `/team/summary` returns `teamFullName` not `teamAbbrev` → every team-stat row skipped (all stats null); (3) `/team/advanced` is dead (500) → Corsi now from `/team/realtime` satPct; (4) summary has no `goalDifferential` (derive from goalsFor−goalsAgainst) and xGF% isn't in the free NHL API at all (removed `d_xgf_pct` from the feature list — it was 100% null and dropna would have zeroed the matrix). Backfill: ~8,991 games 2019-2025 + team/goalie season snapshots. Top moneyline features: d_goal_differential (23%), d_goals_per_game, d_goals_against_pg, d_goalie_gsaa, away_win_pct. `nhl_moneyline` CalErr 5.09% is just above the 5% gate — provisional, re-check after 50 live settled picks. Artifacts committed + active in `model_registry`; GitHub Actions scores NHL automatically.

Thresholds (placeholder — tune after 50+ settled picks): ML 55%/5%, regulation 40%/5% (3-way → lower per-side prob), O/U 55%/5%, puckline 55%/5%.

### Data source — NHL API (free, no key)

- `api-web.nhle.com/v1` — schedule (`/schedule/{date}`), live scores (`/score/{date}`), standings.
- `api.nhle.com/stats/rest/en` — team summary / advanced (Corsi, xGF%), goalie summary.
- **Blocked from the dev sandbox egress allowlist** — backfill + training run on Matt's machine or GitHub Actions (the daily pipeline runner reaches it, same as ESPN/MLB statsapi). No paid source needed.

### Conventions (load-bearing — don't break)

- **Regulation 3-class encoding** (`feature_engine._compute_target` for `h2h_3way`): `0 = away regulation win`, `1 = draw (game went to OT/SO)`, `2 = home regulation win`. Must match `NHL_3WAY_CLASSES = ["away","draw","home"]` in the scorer and the `_evaluate_result` / `_compute_result` settlement logic. A draw bet WINS iff `went_to_ot = 1`.
- **games encoding** (`parse_nhl_game`): `went_to_ot = 1` for OT/SO; `home_win_reg = 1` only for a home regulation win (0 for away reg win OR any OT/SO game); `regulation_tie = went_to_ot`. `home_win` counts OT/SO (full-game moneyline).
- **Franchise id:** Arizona Coyotes → Utah (Hockey Club → Mammoth) all map to the canonical **`UTA`** across every season — in `nhl_stats_ingestor.NHL_API_ABBREV_MAP`, `odds_ingestor.NHL_ODDS_API_MAP`, and `sbr_loader.NHL_NAME_MAP`. Historical ARI rows fold into UTA so the franchise has one identity.
- **Goalie features:** save%/GAA/GSAA diffs, built as-of from the per-game log (see "Inputs as they are now"). The `_last5` columns are populated for every game since 2026-09-20 but are NOT in the model feature lists — `build_training_dataset` keeps only listed features, and adding them is a feature-list change that needs its own walk-forward.
- **Starting-goalie confirm:** NHL `/v1/schedule` has no `probableGoalie` (measured 2026-09-14). ESPN core `probableStartingGoalie` overlays the game-day `nhl_goalie_stats` row (`data/ingestors/espn_probables.py`). The game-model gate then vetoes a BET when that named goalie is Out/Doubtful with `status_ts` ≤ the quote (`docs/game_injury_gate.md`). No ASOF fallback to the season snapshot for the gate — that is last year's #1.
- **Season label:** ending year, rolling from SEPTEMBER (`data/season_labels.py`); the 2020 bubble playoffs are the one September that belongs to the season before.

### Pipeline

| Step | Runs where | Frequency | What it does |
|---|---|---|---|
| NHL results (`nhl-results`) | GitHub Actions (step 0b, **before settle**) | daily 7am | `ingest_nhl_scores_for_date` — trailing-3-day final scores + regulation outcomes into `games` (settlement reads `home_score`; the MLB statsapi fetch in paper_tracker doesn't cover NHL) |
| NHL odds (h2h/totals/spreads bulk + per-event 3-way) | GitHub Actions (`step_odds`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | DK lines; 3-way attempted per-event (bulk 422s it), non-fatal when absent |
| NHL team + goalie stats (`nhl_stats`) | GitHub Actions (`step_nhl_stats`) | daily 7am | season-to-date team metrics + probable-starter goalie rows (ESPN `probableStartingGoalie` overlay) |
| NHL scoring (`step_scoring`) | GitHub Actions | 6am + every refresh pass | `run_scorer` NHL branch → picks (incl. `_score_nhl_3way`) |
| Settlement | GitHub Actions (`settle`) | 7am | generic game-level settle (NHL is not excluded); 3-way draw handled in `_compute_result` |

NHL picks won't generate until the four models are trained and the `.pkl`
artifacts are committed (like MLB/WNBA/UFC) — until then the NHL steps no-op
cleanly (scorer logs "no trained model").
