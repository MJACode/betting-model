# NBA — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 23. NBA — Pipeline Operations
NBA is the 5th sport, built by mirroring the WNBA architecture (same `nba_api`
source, same basketball feature shape). It joins the global sport toggle
(MLB | WNBA | NBA | UFC | GOLF) — no new mobile tab.

### Models (10 LIVE — trained 2026-06-19 on 2019-2024 / holdout-2025; 8,284 games backfilled)

Holdout-2025 metrics (O/U acc for props, win-acc for ML; CalErr = calibration error):

| Model ID | Type | Market | Holdout | Status |
|---|---|---|---|---|
| `nba_moneyline` | binary XGBoost + Platt | h2h (real DK) | acc 70.0% / AUC 0.757 / CalErr 3.04% | **LIVE** |
| `nba_over_under` | binary XGBoost + Platt | totals (real DK) | — | BLOCKED — no historical DK lines for the target (trains once live odds accrue) |
| `nba_spread` | binary XGBoost + Platt | spreads (real DK) | — | BLOCKED — same as O/U |
| `nba_prop_player_points` | Poisson | DK player props | O/U 75.6% / CalErr 12.3% | **LIVE** (high CalErr = count variance, like WNBA) |
| `nba_prop_player_rebounds` | Poisson | DK player props | O/U 73.8% / CalErr 3.7% | **LIVE** |
| `nba_prop_player_assists` | Poisson | DK player props | O/U 73.6% / CalErr 4.7% | **LIVE** |
| `nba_prop_player_threes` | Poisson | DK player props | O/U 75.8% / CalErr 3.7% | **LIVE** |
| `nba_prop_player_pra` | Poisson | DK player props | O/U 77.2% / CalErr 16.0% | **LIVE** (high CalErr = count variance) |
| `nba_prop_player_blocks` | Poisson | DK player props | O/U 71.8% / CalErr 1.2% | **LIVE** |
| `nba_prop_player_steals` | Poisson | DK player props | O/U 62.1% / CalErr 2.6% | **LIVE** (weakest acc) |
| `nba_prop_player_turnovers` | Poisson | DK player props | O/U 70.6% / CalErr 3.2% | **LIVE** |
| `nba_prop_player_dd` | **logistic** + Platt | player_double_double (prob-only) | AUC 0.870 / CalErr 4.6% | **LIVE** (8.8% base rate) |

The prop 5% CalErr gate does not apply (natural high-count variance) — points/pra mirror WNBA.
**Off-season caveat:** NBA runs Oct–Jun, so the first LIVE picks won't fire until the 2026-27
season tips off (~late Oct 2026). Until then the daily Basketball Daily Ingest job and the scoring
steps no-op cleanly (no games).

Thresholds (placeholder — tune after live odds accumulate): game models 66%/12%,
props 60%/8%, double-double 55% prob-only. **NBA mainline markets (ML/totals/
spread) are the sharpest in US sports** — treat their backtest ROI as directional
only and expect the realistic edge to live in the props.

### Conventions (load-bearing — don't break)

- **Season label = ENDING year (the NHL convention):** season `2025` = the
  2024-25 season (Oct 2024 – Jun 2025). The stats ingestor converts our int
  season → the nba_api `"YYYY-YY"` string (`_nba_season_str`). Because games
  straddle two calendar years, the season is **threaded explicitly**, never
  derived from a game's date — `_nba_season_for_date` (Oct-Dec → year+1) is used
  for the live/daily paths, and `odds_ingestor` already labels Oct+ NBA games
  `year+1`.
- **Backfill team-stat snapshot = `{season-1}-09-01`** (before any Oct game), so
  the ASOF feature lookup (`as_of_date <= game_date`) always finds an in-season
  row. (WNBA uses `{season}-01-01` because it's a summer league — do NOT copy
  that for NBA or every Oct-Dec game falls back to the prior season.)
- **30 teams** — `NBA_TEAMS`, `NBA_ODDS_API_MAP` in config. ESPN injury ids use
  the static `ESPN_NBA_TEAM_IDS` (NBA franchises are stable) with a live-resolver
  overlay (`_fetch_nba_espn_team_ids`) as a self-heal.
- **Double-double** is a binary Yes/No market (≥10 in ≥2 of pts/reb/ast/stl/blk).
  It's logistic + over-only + prob-only (`nba_prop_player_dd` in
  `PROB_ONLY_MODELS`). The prop odds parser defaults its line to 0.5 (no `point`),
  and settlement uses the `COMPUTE_DD` sentinel.

### stats.nba.com constraint

`nba_api` calls `stats.nba.com`, which blocks GitHub Actions datacenter IPs — so
`nba_stats` and `nba-game-log` (team stats + box scores) must run on a residential
IP. They were folded into the existing local Task Scheduler job
(`scripts/wnba_daily_ingest.bat`, now a combined "Basketball Daily Ingest" running
WNBA **and** NBA at 7am). NBA odds, prop odds, scoring, and settlement all run in
GitHub Actions (The Odds API, reachable). NBA plays nightly, so the local job is
load-bearing daily during the season.

### Pipeline

| Step | Runs where | What it does |
|---|---|---|
| NBA game odds | GitHub Actions (`step_odds`) | DK ML/totals/spread via The Odds API (NBA in the default sport list) |
| NBA prop odds (`nba-prop-odds`) | GitHub Actions | 9 DK player-prop markets via the event-level endpoint |
| NBA team stats (`nba_stats`) | **Local machine** | season-to-date team ratings → game scorer features |
| NBA game log (`nba-game-log`) | **Local machine** | yesterday's box scores → settlement + rolling prop features |
| NBA injuries | GitHub Actions (`step_injuries`) | ESPN hidden API (`run_injury_ingestor` defaults include NBA) |
| NBA game scoring | GitHub Actions (`step_scoring`) | `run_scorer` NBA branch → picks |
| NBA prop scoring (`nba-prop-scoring`) | GitHub Actions | `run_nba_prop_scorer` (9 markets, Poisson + logistic DD) → picks |
| Settlement | GitHub Actions (`settle`) | game picks via the generic path; props via `_settle_prop_picks` (`nba_player`, trailing 14-day window) |

### First-time setup (Matt's machine — pending)

```bash
# 1. Games + scores + regulation outcomes (~27 schedule calls/season, ~3 min for 7 seasons)
python -m data.ingestors.nhl_stats_ingestor --backfill-games 2019 2025
# 2. Team + goalie season snapshots (season-start as_of_date)
python -m data.ingestors.nhl_stats_ingestor --backfill 2019 2025
# 3. (optional) load historical NHL odds for O/U + puckline targets
#    — SBR/datawarehouse files into data/raw/datawarehouse/nhl/, then:
python -m data.ingestors.sbr_loader --sport NHL
# 4. Train (multiclass branch handles nhl_moneyline_regulation automatically)
python -m models.trainer --model nhl_moneyline
python -m models.trainer --model nhl_moneyline_regulation
python -m models.trainer --model nhl_over_under
python -m models.trainer --model nhl_puckline
# 5. Backtest (moneyline/regulation prob-only at synthetic -110 — directional)
python -m models.backtester --model nhl_moneyline --season 2025
# 6. Commit the trained artifacts so GitHub Actions scoring can load them:
git add -f models/saved/nhl_*.pkl && git commit -m "Add trained NHL model artifacts"
```

### Mobile

NHL is the fourth option in the global sport toggle (MLB | WNBA | UFC | NHL).
Matchups render "A @ B" (standard). Model labels: ML / Reg 3-Way / O/U / PL.
No NHL player-stat leaderboard (only team + goalie stats are ingested) — the
Stats tab shows an empty state for NHL. The Claude-mobile `docs/mobile_picks_prompt.md` SQL already
includes the four NHL models (regulation maps to the `h2h_3way` market in the
odds-join CASE).

---
