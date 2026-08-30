# WNBA — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 19. WNBA — Pipeline Operations
### Models live (as of 2026-05-31)

| Model ID | Type | Train rows | OOS metric | Status |
|---|---|---|---|---|
| `wnba_moneyline` | XGBoost classifier | 1,204 | AUC 0.763 / CalErr 6.89% / backtest 74.8% win +42.7% ROI | LIVE (prob-only — no DK WNBA ML odds yet) |
| `wnba_prop_player_points` | Poisson | 25,153 (retrained 2026-07-19, +2025) | holdout-2026 O/U acc 76.1% | **PAUSED** — 2026 real-DK-line sweep: whole grid negative |
| `wnba_prop_player_rebounds` | Poisson | 20,177 | O/U acc 74.7%, CalErr 10.2% | **PAUSED 2026-07-29** — decayed to -13.9%/54 bets; every sweep cell negative (overs -44%..-53%) |
| `wnba_prop_player_assists` | Poisson | 20,177 | O/U acc 74.9%, CalErr 7.5% | LIVE |
| `wnba_prop_player_threes` | Poisson | 25,153 (retrained 2026-07-19, +2025) | holdout-2026 O/U acc 69.7%, CalErr 3.5% | **PAUSED** — same |
| `wnba_prop_player_pra` | Poisson | 25,153 (retrained 2026-07-19, +2025) | holdout-2026 O/U acc 78.8% | **PAUSED** — same (least-bad cell -0.9%) |
| `wnba_over_under` | XGBoost classifier | 1,103 | holdout-2025 (synthetic lines) acc 61.7% / AUC 0.669 / CalErr 7.85%; 2026 OOS "+14.5%" was **LEAKED** (see below) | **PAUSED 2026-07-29** — 0 BETs in 17 honest games (P(over) tops out at 0.599 vs its own 0.60 bar) |
| `wnba_spread` | XGBoost classifier | 1,103 | holdout-2025 (synthetic) acc 59.5% / AUC 0.611 / CalErr 3.39%; 2026 OOS "+22.6%" was **LEAKED** (see below) | **PAUSED 2026-07-29** — 2-2 / -3.7% on honest lines |

Backtest note: `wnba_moneyline` OOS ROI (+42.7%) is vs. synthetic −110. Real DK WNBA moneyline prices will be heavily juiced on favorites — live ROI will be lower. Treat as directional until 50+ live picks.

### Pipeline responsibilities

| Step | Runs where | Frequency | What it does |
|---|---|---|---|
| WNBA game odds | GitHub Actions (`step_odds`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | DK moneyline / O/U / spread via The Odds API |
| WNBA prop odds | GitHub Actions (`step_wnba_prop_odds`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | DK points/reb/ast/threes/PRA prop lines |
| WNBA game scoring | GitHub Actions (`step_scoring`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | `run_scorer` WNBA branch → picks written |
| WNBA prop scoring | GitHub Actions (`step_wnba_prop_scoring`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | `run_wnba_prop_scorer` → picks written |
| **WNBA results (ESPN)** | GitHub Actions (`step_wnba_results`, Step 0e **before settle**) | daily 6am | Finals + player box scores from the ESPN hidden API (trailing 3 days + self-heal over any ≤14-day-old NULL-score WNBA game), then rebuilds the season `wnba_team_stats` snapshot from our own DB. Makes WNBA settlement cloud-native — added 2026-07-09 after the local job kept lagging (see session summary). **Since 2026-08-11 any per-date site.api failure falls back to `sports.core.api.espn.com`** (the $ref-linked core v2 API — the host that kept serving the worker through the 2026-08-05 site.api IP block) |
| WNBA game log | **Local machine** (`wnba-game-log`) | Daily 7am (Task Scheduler) | Yesterday's box scores → settlement + rolling prop features. Now REDUNDANT with the ESPN step (idempotent upserts coexist); still needed for debut players ESPN can't name-resolve and as the authoritative nba_api-id source |
| WNBA team stats | **Local machine** (`wnba_stats`) | Daily 7am (Task Scheduler) | Season-to-date team ratings → game scorer features. Now redundant with the ESPN step's DB rebuild |
| WNBA injuries | GitHub Actions (`step_injuries`) | 7am | ESPN hidden API → `injuries` table → `home/away_injury_adj` features |

### stats.nba.com constraint

`nba_api` calls `stats.nba.com`, which consistently times out from GitHub Actions datacenter IPs. `wnba_stats` and `wnba-game-log` must run on a residential IP. Windows Task Scheduler job `\BettingModel\WNBA Daily Ingest` handles this at 7am daily. Log: `logs/wnba_ingest.log`.

If the machine is off at 7am, `StartWhenAvailable` triggers the job on next login. WNBA games run Tue/Thu/Sat/Sun — the ingestor no-ops cleanly on off days.

### Teams (2026 — 15 franchises)

ATL, CHI, CON, DAL, GSV, IND, LV, LA, MIN, NY, **PDX** (Portland Fire — 2026 expansion), PHX, SEA, **TOR** (Toronto Tempo — 2026 expansion), WAS.

### Injuries

WNBA injuries are ingested daily (7am pipeline) from the ESPN hidden API, the same source as MLB/NHL. `injury_ingestor.run_injury_ingestor` now defaults to `["MLB", "NHL", "WNBA"]`. Rows land in the shared `injuries` table (`sport='WNBA'`); the WNBA feature engine already consumes them as `home/away_injury_adj` + `home/away_has_returnee`.

**Team ids resolve dynamically.** `_espn_team_ids("WNBA")` calls `_fetch_wnba_espn_team_ids()`, which pulls ESPN's live WNBA teams list (`https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/teams`) and joins each team to our 3-letter abbrev by **full team name** via `WNBA_ODDS_API_MAP`. This resolves all 15 franchises — including the GSV/PDX/TOR expansion teams — with **no hardcoded numeric ids**, and self-maintains as the league changes. ESPN is reachable from the GitHub Actions runner (it already works for MLB/NHL injuries there). `config.ESPN_WNBA_TEAM_IDS` is now only an **offline fallback** (the 12 established franchises) used when that endpoint is unreachable, e.g. the sandbox allowlist. The injuries endpoint is league-scoped, so any unknown id 404s and unmapped teams are skipped — no wrong-team data is ever fetched.

### Thresholds (full-outcome sweep 2026-07-02 — grading validated 585/585 vs settlements; thin samples, re-sweep as season builds)

| Model | Min prob | Min edge | 2026-07-02 record at cut |
|---|---|---|---|
| `wnba_moneyline` | 64% | 4% | 17 bets 14-3 +31.9% (old 0.66/0.12 placeholder fired only 3 bets; plateau 0.60-0.68 × 0.00-0.04 all +25..+32%) |
| `wnba_over_under` | **PAUSED** (cut kept 60%/6%) | | **2026-07-29 PAUSED — the sweep behind this cut was leaked.** `build_bulk_wnba_lookups` took the latest odds snapshot with no pre-tipoff cutoff, so 89/133 completed 2026 games (67%) were featurized with a totals line that had already drifted toward the final score (avg leak 8.2 pts, worst 47). `total_line` is the model's top feature. Leak fixed via `_is_pregame_snapshot`; re-sweep with `scripts/wnba_line_sweep.py` before unpausing |
| `wnba_spread` | **PAUSED** (cut kept 60%/10%) | | **2026-07-29 PAUSED — same leaked sweep** (86/133 games, avg spread leak 4.6 pts, worst 41). The "most robust WNBA grid" claim was an artifact of reading post-tipoff lines. Honest live record 2-2 / -3.7%. Re-sweep on clean lines before unpausing |
| `wnba_prop_player_points` | 58% | 17% | **PAUSED — confirmed 2026-07-19**: retrained +2025, swept vs real 2026 DK lines (2,218 side-rows) — entire grid -5..-10% |
| `wnba_prop_player_rebounds` | **PAUSED** (cut kept 69%/8%) | | **2026-07-29 PAUSED** — the +5.6% that kept it live has decayed to **-13.9% over 54 bets**, and the full prob×edge sweep (with the -140 floor) is negative in every cell (-9.1% @ 0.69/0.16 → -23.7% @ 0.65/0.12). Side-structural: **overs 34-43 / -44%..-53%**, unders ~flat (82-64 / -1.1%). Only non-negative cell is under-only 0.73/0.14 = 17 bets +2.5% (noise, needs side-restriction the scorer can't express). Needs opponent-defense + minutes features, not a re-cut |
| `wnba_prop_player_assists` | 69% | 8% | KEPT 2026-07-11 re-sweep — ROI max (+19.3%/44). Units-max 0.53/0.06 (103 bets +13.3%) declined — no volume bets |
| `wnba_prop_player_threes` | 64% | 12% | **PAUSED — confirmed 2026-07-19**: real-line sweep all negative (-2..-17%) |
| `wnba_prop_player_pra` | 67% | 16% | **PAUSED — confirmed 2026-07-19**: real-line sweep all negative (least-bad -0.9% @ edge 0.16) |

---
