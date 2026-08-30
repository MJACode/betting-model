# Build state, data sources, model registry, spec (2026-08 snapshot)

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 4. Current Build State
### What's Built

```
betting-model/
├── CLAUDE.md                          ← this file
├── .env.example                       ← copy to .env, add ODDS_API_KEY
├── config.py                          ← central config, env vars, constants
├── requirements.txt                   ← all Python dependencies
├── run_pipeline.py                    ← master daily orchestrator (9 steps)
│
├── data/
│   ├── db_setup.py                    ← Supabase/Postgres schema (17 tables)
│   └── ingestors/
│       ├── sbr_loader.py              ← SBR Excel historical odds parser
│       ├── injury_ingestor.py         ← ESPN Hidden API + MLB Stats API
│       ├── odds_ingestor.py           ← The Odds API (DraftKings live + F5 ML)
│       ├── prop_odds_ingestor.py      ← The Odds API (DK player prop markets)
│       ├── mlb_stats_ingestor.py      ← MLB Stats API + Baseball Savant + game log
│       ├── nhl_stats_ingestor.py      ← NHL API v1 team/goalie stats
│       ├── weather_ingestor.py        ← Open-Meteo weather (wind/temp/dome)
│       ├── baseball_savant_ingestor.py ← Statcast leaderboard CSV (pitcher + batter)
│       └── lineup_ingestor.py         ← MLB live feed batting lineups (order/pos/hand)
│
├── features/
│   ├── feature_engine.py             ← Feature matrix builder (game models)
│   └── prop_feature_engine.py        ← Feature builder (Poisson prop models)
│
├── models/
│   ├── trainer.py                     ← XGBoost + Optuna (classification + Poisson)
│   ├── scorer.py                      ← BET/AVOID signals: game models + prop models
│   └── backtester.py                  ← Historical simulation + go-live gate
│
├── tracking/
│   └── paper_tracker.py              ← Morning result settler + P&L log
│
├── dashboard/
│   └── app.py                        ← Streamlit 5-tab dashboard
│
└── logs/                             ← Auto-created by run_pipeline.py
```

### What's NOT Built Yet
- All 11 MLB prop models built, trained, and settling. Next: threshold tuning after 50+ settled picks.
- mlb_prop_batter_hr: v2 LIVE (Poisson, binary AUC 0.617, 88.5% O/U acc — enabled 2026-05-13)
- mlb_prop_pitcher_k: v2 LIVE (retrained 2026-05-14, 18 features incl. ump_k_plus_minus — feature added no signal improvement, see Section 11)
- **WNBA: 8 models LIVE** (moneyline + O/U + spread + 5 props; points/threes/PRA paused). `wnba_over_under` + `wnba_spread` trained 2026-07-19 on synthetic 2019-2025 lines (wnba_odds_synthesizer, F5 precedent) and validated OOS on the 118 real-DK-line 2026 games. Full pipeline operational — see Section 19.
- **UFC: 3 models LIVE** (moneyline + total_rounds + method_of_victory). Backfilled from the CSV mirror (617 events / 14,462 fight-log rows) and trained (first 2026-06-11, retrained 2026-06-19). `ufc_moneyline` acc 66.2% / **CalErr 5.99% (above the 5% gate — provisional, flagged for feature work)**; `ufc_total_rounds` acc 63.9% / CalErr 3.84%; `ufc_method_of_victory` (3-class, prob-only) acc 56.5% / CalErr 3.23%. Artifacts committed + active. See Section 20.
- **NHL: 4 models code-complete, NOT yet trained** (moneyline + regulation 3-way + O/U + puck line). Full pipeline wired and validated offline; backfill + training run on Matt's machine (NHL API blocked from the sandbox). See Section 11 + Section 24.
- **Live (in-play) betting: LIVE on the Railway worker (2026-07-21).** All 3 live models trained + committed (2026-06-15); the live loop now runs as a supervised `*/10` job (11am–midnight ET) inside `scheduler.py` — see Section 21. First `is_live` picks appear the first slate after the worker redeploys.
- **NBA: 10 models LIVE** (moneyline + 9 props), trained 2026-06-19 on 2019-2024 / holdout-2025 (8,284 games backfilled). `nba_moneyline` AUC 0.757 / CalErr 3.04%; `nba_prop_player_dd` AUC 0.870. `nba_over_under` and `nba_spread` blocked pending live DK NBA odds (same as WNBA). **Off-season until ~Oct 2026 — no live picks until the 2026-27 season tips off.** See Section 23.
- Dashboard prop tab
- Website (picks display with signal_type filter — DB is ready)

---
## 5. Data Sources
| Source | What it provides | Cost | Notes |
|--------|-----------------|------|-------|
| The Odds API | Live lines at the US top-5 books (game markets + player props) | ~$79/mo Starter | Key in `.env` as `ODDS_API_KEY`. Books in `config.LINE_SHOP_BOOKMAKERS`: draftkings, fanduel, betmgm, williamhill_us (Caesars), espnbet. **The models score against DraftKings only** — the rest are display-only line shopping. The `bookmakers` param counts as ONE region, so extra books cost **zero** extra credits. |
| SBR (SportsBookReviewsOnline) | Historical odds 2007–2024 | Free | Manual Excel download |
| MLB Stats API (statsapi) | Team batting/pitching stats, probable starters, game scores | Free | Primary source for all MLB team + pitcher stats. Replaced FanGraphs 2026-04-11. |
| Baseball Savant | SwStr%, CSW%, xERA (xFIP proxy) per pitcher per season | Free | Official MLB property. Joined to MLB Stats API by MLBAM player_id. |
| Open-Meteo | Historical + forecast weather (temp, wind, precip) | Free | No API key needed. Used by weather_ingestor.py. |
| NHL API v1 | Team stats, goalie stats, schedule | Free | Direct HTTP to `api-web.nhle.com` |
| nba_api (stats.nba.com) | WNBA + NBA team stats + player box scores | Free | `nba_api` LeagueGameLog — WNBA via LeagueID `10`, NBA via `00`. Blocks GitHub Actions IPs → runs on Matt's machine via the local "Basketball Daily Ingest" Task Scheduler job. See Sections 19 (WNBA) + 22 (NBA). |
| ESPN Hidden API | Injury reports (all team sports) | Free | Hidden JSON endpoint, no auth needed (MLB/NHL/WNBA/NBA) |
| Greco1899/scrape_ufc_stats (GitHub CSV mirror) | UFC fight results + fighter stats (1993–present) | Free | **Primary UFC source** — maintained 1:1 CSV export of ufcstats.com, updated weekly. ufcstats.com itself is now behind a Cloudflare browser challenge (cloudscraper can't solve) — its scraper (`ufc_stats_ingestor.py`) is kept as plan B. See Section 20. |
| DataGolf (Scratch Plus API) | Golf round-level scoring + strokes gained (2017+) AND live DraftKings odds for every PGA event (win/top-N/make-cut/matchup) | ~$30/mo | **Sole GOLF source** — `feeds.datagolf.com`, key in `.env` as `DATAGOLF_API_KEY`. The Odds API is NOT used for golf (majors-only). See Section 21. |

**FanGraphs / pybaseball — REMOVED (2026-04-11, completed 2026-04-12):**
FanGraphs blocked our IP after repeated scraping during development. Replaced entirely
with MLB Stats API + Baseball Savant for all team and per-pitcher stats. pybaseball is
still in requirements.txt but no longer called anywhere. Do NOT add back any FanGraphs
scraping without a different mechanism.

**Datawarehouse / CSV data (2026-03-31 — updated):**

MLB historical data is now loaded from a flat CSV (`data/raw/datawarehouse/mlb/MLB_Basic.csv`).
This file covers 2009–2025 (40,996 games) in one-row-per-game format. The `sbr_loader`
was extended to support this format alongside the original Excel format.

The raw data folder was renamed from `data/raw/sbr/` → `data/raw/datawarehouse/` to reflect
its role as the source of historical baseball data. Config paths updated in `config.py`.

NHL data not yet loaded — deprioritized in favour of getting MLB working first.

To reload from scratch:
```bash
python -m data.ingestors.sbr_loader        # loads all CSV/xlsx in data/raw/datawarehouse/
```

CSV columns (MLB_Basic.csv):
`game id, date, away team, away score, away ml open, away ml close, over open,
over open odds, over close, over close odds, home team, home score, home ml open,
home ml close, under open, under open odds, under close, under close odds`

MLB runline spread is derived as `spread_home = -1.5` (fixed constant) — the CSV
has no spread column. The `spreads` odds row is written automatically by the loader.

---
## 6. Models Registry
| Model ID | Sport | Market | Target variable |
|----------|-------|--------|----------------|
| `mlb_moneyline` | MLB | Moneyline (h2h) | Home team wins full game |
| `mlb_over_under` | MLB | Totals | Total runs > line |
| `mlb_runline` | MLB | Spreads (±1.5) | Home covers spread |
| `nhl_moneyline` | NHL | Moneyline full game | Home team wins (incl. OT/SO) |
| `nhl_moneyline_regulation` | NHL | 3-way regulation | Home wins in regulation |
| `nhl_over_under` | NHL | Totals | Total goals > line |
| `nhl_puckline` | NHL | Puck line (±1.5) | Home covers spread |
| `nfl_wind_totals` | NFL | Totals (under-only) | Game total stays under the line in high forecast wind — the `docs/sports/nfl.md` standalone wind card, published into picks by `scripts/nfl_wind_publisher.py` |
| `nfl_opener_spread` | NFL | Spreads | The `docs/sports/nfl.md` opener rule: side Pinnacle favours at a soft book's stale number (|dev| ≥ 1.0, T-7..T-2 window) — locked at first qualifying card, never re-priced; published by `scripts/nfl_wind_publisher.py --opener` |
| `ncaaf_over_under` | NCAAF | Totals | Total-REGRESSION rule: predict the game total from fundamentals, bet only when \|pred − DK line\| ≥ 8.0 (gate in the artifact). LIVE — REAL MONEY (Matt skipped the paper gate 2026-08-27; both pass the multi-year >=4% ROI bar) |
| `ncaaf_spread` | NCAAF | Spreads | CROSS-BOOK OPENER rule: back the side Bovada's opener favours at DK's stale opening number; fires only when both openers were captured within 90 min and DK is still on its opener. LIVE — REAL MONEY (Matt skipped the paper gate 2026-08-27; both pass the multi-year >=4% ROI bar) |
| `ncaaf_spread_premium` | NCAAF | Spreads | Same cross-book opener rule, DISJOINT high-conviction band (openers disagree by 2.5+ instead of 1.0-2.5). Fewer picks, higher rate. LIVE — REAL MONEY |
| `ncaaf_moneyline` | NCAAF | Moneyline | PAUSED — classifier held out at AUC ~0.50 |
| `ufc_moneyline` | UFC | Moneyline (h2h) | Home-slot fighter wins |
| `ufc_total_rounds` | UFC | Round totals | Fight passes the round line (O2.5 = past 2:30 of R3) |
| `ufc_method_of_victory` | UFC | Method (3-class) | Decision / KO-TKO / Submission (prob-only) |
| `nba_moneyline` | NBA | Moneyline (h2h) | Home team wins |
| `nba_over_under` | NBA | Totals | Total points > line |
| `nba_spread` | NBA | Spreads | Home covers the spread |
| `nba_prop_player_points` | NBA | player_points | Player points > line (Poisson) |
| `nba_prop_player_rebounds` | NBA | player_rebounds | Player rebounds > line (Poisson) |
| `nba_prop_player_assists` | NBA | player_assists | Player assists > line (Poisson) |
| `nba_prop_player_threes` | NBA | player_threes | Player made threes > line (Poisson) |
| `nba_prop_player_pra` | NBA | player_points_rebounds_assists | Player P+R+A > line (Poisson) |
| `nba_prop_player_blocks` | NBA | player_blocks | Player blocks > line (Poisson) |
| `nba_prop_player_steals` | NBA | player_steals | Player steals > line (Poisson) |
| `nba_prop_player_turnovers` | NBA | player_turnovers | Player turnovers > line (Poisson) |
| `nba_prop_player_dd` | NBA | player_double_double | Player records a double-double (logistic, prob-only) |
| `golf_outright` | GOLF | win | Player wins the tournament (field-renormalized) |
| `golf_top10` | GOLF | top_10 | Player finishes in the top 10 |
| `golf_top20` | GOLF | top_20 | Player finishes in the top 20 |
| `golf_make_cut` | GOLF | make_cut | Player makes the cut |
| `golf_matchup` | GOLF | matchup_tournament | Player A beats Player B over the tournament |

---
## 3. Technical Spec Reference
The full approved spec is:
`Bet Repos/Betting Model Platform — Technical Spec v1.2.docx`

Key decisions from the spec (Section 4, decisions log 4.1–4.11):

| Decision | What we chose | Why |
|----------|--------------|-----|
| Historical odds source | SBR (free Excel downloads) | Odds API historical costs 10× credits |
| Database | SQLite (single file) | Simple, local-first, cloud-migratable later |
| Models | 7 XGBoost models (one per sport×market) | Best calibration for tabular sports data |
| Calibration | Platt scaling post-XGBoost | Converts raw scores to real probabilities |
| Hyperparameter tuning | Optuna (Bayesian, 100 trials) | Better than grid search for this use case |
| Bet sizing | Tenth-Kelly, capped at 5% | Quarter-Kelly always hit the cap (flat-betting); tenth-Kelly gives 2-4% bets with real edge-driven differentiation |
| Edge threshold | ±3% for BET/AVOID signals | No-signal zone between −3% and +3% |
| Injuries | 3 scenarios: A (active), B (return ramp), C (opponent edge) | Injuries matter; ramp prevents overconfidence on return |
| Early season rule | No picks until ≥10 games played | Avoids unstable small-sample stats |
| NHL overtime | Two models: full-game ML + regulation-only 3-way | Regulation market often has better value |
| Props | Phase 2 only | Too much data infrastructure needed for Phase 1 |

---
