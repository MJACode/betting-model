# NFL — standalone wind/opener model (`nfl/`)

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 28. NFL — Standalone Wind/Opener Model (`nfl/`)
Imported 2026-08-15 (session 116) as a **self-contained package** — developed externally,
NOT wired into the platform pipeline, scheduler, or Supabase. It has its own `models/`,
`scripts/`, `data/`, `features/`, `data_ingest/`, README, RESTORE.md, and requirements.txt.
Everything below is from the package's own validation docs
(`nfl/nfl_game_lines_model_system.md` — the **Runbook: Wind Totals** at the end is the
weekly routine).

**What works (validated):**

| Strategy | Result | Notes |
|---|---|---|
| **Wind totals UNDER** | 57.09% under [52.4, 61.9], P(beat vig) 0.975, ~38 bets/season | Day-3 Open-Meteo issued forecast, wind ≥ 12mph threshold. Confirmed on ERA5 reanalysis (independent of nflverse): 59.32% on n=354. Noise model is measured forecast error from 298,944 hourly forecast/ERA5 pairs, not assumed Gaussian |
| **Opener strategy** | ROI +6.98%, 95% CI [-0.6, +14.5] | Priced at actually-quoted juice (mean -124, NOT -110). ATS excess +5.78pp [+1.8, +9.6] at threshold 1.0 vs line-implied cover prob; DraftKings placebo shows no excess. First-qualifying-moment selection (no lookahead) |
| **Book integrity screen** | 4 offenders confirmed on 1.4M quotes across 40 books | betanysports, betsson, nordicbet, tipico_de — exclude these |

**Critical data rules:**
- **`nfl/data/odds_cache/` (2,632 snapshots, ~12MB) is IRREPLACEABLE — ~45,000 Odds API
  credits of spend. Committed to git. Never delete, never gitignore.** Backup tarball:
  `nfl-model-odds-cache.tar.gz` (keep a copy outside this machine).
- `nfl/data/weather_cache/` is gitignored (108MB unpacked, free):
  `python nfl/scripts/validate_wind_forecast.py` rebuilds it automatically (~30 min).
- Open-Meteo **issued** forecasts (`previous_dayN`) only exist from **2024-01-18** — the
  plain historical series before that is near-analysis and LEAKS if used as a forecast.
- The package keeps its own credit ledger: `nfl/data/credit_ledger.json`.

**Run it (from `nfl/`):**
```powershell
pip install -r requirements.txt
$env:THE_ODDS_API_KEY="..."          # separate spend from the platform's Odds API usage
python scripts/weekly_wind_card.py --dry-run   # weather only, 0 credits
python scripts/weekly_wind_card.py --days 2    # live weekly bet card, 1 credit
python scripts/replay_wind_card.py             # replay harness vs completed weeks
```

**Key files:** `nfl/models/wind_totals.py` (the rule), `nfl/models/ev_engine.py`,
`nfl/scripts/weekly_wind_card.py` (live card), `nfl/scripts/validate_wind_forecast.py`
(regenerates every published number), `nfl/README.md` (what works and what does not).

**Verified working 2026-08-15** (dry run on Python 3.14, all deps already present, no
venv needed): default 7-day window correctly reports no games (season opener NE @ SEA is
2026-09-09); `--days 31` reaches Week 1 — 16 games loaded, domes filtered to 11 outdoor,
Open-Meteo queried, forecasts NaN because Week 1 is beyond Open-Meteo's ~16-day forecast
horizon. Expected, not a bug: the rule is validated at **day-3 lead** — run the card
in-week during the season.

**Operational notes:**
- **Deployed threshold in code is 11.0 mph** (`DEPLOY_THRESHOLD` in
  `weekly_wind_card.py`), not the 12 quoted in the validation summary. `--threshold 12`
  overrides to match the published number.
- 2026 schedule already in `nfl/data/games.csv` (full season through Week 18).
- First meaningful run: **~2026-09-06** (Week 1 enters forecast window). `--dry-run` then
  shows real wind numbers for 0 credits; `--days 2` prices qualifying games for 1 credit.
- **Cadence: AUTOMATED on the Railway worker (2026-08-15).** `scheduler.py` runs the
  runbook cadence — Thu 9am `--days 4` (scan), Sat 9am `--days 2` (firm), Sun 8am
  `--days 1 --regions us,eu` (place) — plus a **Mon 9am `--days 1`** run the runbook
  lacked (Sunday's 1-day window closes before MNF kickoff). Jobs run with cwd `nfl/`;
  ~5 credits/week in season, free off-season (script exits before the odds call when
  no games are in window). **No new Railway variable needed** — the scheduler maps
  the platform's existing `ODDS_API_KEY` into the `THE_ODDS_API_KEY` name the nfl
  package reads (same Odds API service; set a dedicated `THE_ODDS_API_KEY` only to
  isolate NFL spend, it takes precedence). With neither key the jobs fall back to
  `--dry-run` (weather only) with a log warning. Kill switch: `RUN_NFL_WIND_CARD=0`.
  **Since 2026-08-16 the card is also PUBLISHED INTO THE APP:** after each live
  card run the scheduler invokes `scripts/nfl_wind_publisher.py`, which mirrors the
  qualifying bets into `games` + `picks` (model_id `nfl_wind_totals`, sport `NFL`,
  always the under; game_id = `NFL_{nflverse_id}` — stable across flex-schedule
  moves). `dk_odds` holds the card's BEST-BOOK price with the book named in
  pick_label (this standalone model never scores vs DK, so the DK-only invariant
  doesn't apply). Each live run delete+replaces UNSTARTED wind picks (the UFC/golf
  look-ahead exemption from the first-run lock — the runbook says later is better);
  a live run with zero qualifying bets clears them. Results: Step 0f
  `nfl-results` fetches the hosted nflverse games.csv (raw.githubusercontent, the
  UFC-mirror host) pre-settle, and picks settle through the generic totals path
  (`_market_for_pick` maps the model → 'totals'). The mobile app has NFL in the
  sport toggle; picks appear up to 5 days ahead (`fetchUpcomingNflPicks`). The
  Railway-log card remains the primary read; the CSV in `nfl/data/cards/` is on
  ephemeral disk and resets on redeploy. Manual runs per the Runbook still work
  anytime.
- **The OPENER rule is also live (2026-08-16, `nfl_opener_spread`):** NEW
  `nfl/scripts/daily_opener_card.py` deploys the corrected backtest_opener rule —
  in the T-7..T-2 window, wherever a clean soft book's HOME spread deviates
  ≥ 1.0 pts from Pinnacle's (regions `us,eu`, 2 credits/run), bet the side
  Pinnacle favours at the soft book's stale number; one bet per game, largest
  |dev| at the first qualifying daily run. `scheduler.py` runs it daily 9:30am ET
  (same `RUN_NFL_WIND_CARD` kill switch), then `nfl_wind_publisher --opener`.
  **Lock semantics are the OPPOSITE of wind:** insert-once per (game, model) —
  an opener pick locks at its first qualifying card and is NEVER re-priced or
  cleared (the edge IS staleness; the runbook: "must be bet a week out").
  model_probability is the pooled validated ATS (0.5818 flat — no per-bet
  curve); dk_odds = the soft book's quoted price (book in pick_label);
  scored_line = the soft book's HOME spread (generic spreads settle). Matchbook
  excluded (commission-gross prices). Evidence: +5.78pp ATS excess
  [CI +1.8, +9.6] but ROI +6.98% [CI −0.6, +14.5] grazes zero — treat as
  PAPER-FIRST; wind stays the only `docs/sports/nfl.md` rule its own docs clear for live money.
- **DK line snapshots + pick-timing display (2026-08-19, session 121):** every
  LIVE card run also dumps DraftKings' totals/spreads for every game within 8
  days (`nfl/data_ingest/line_snapshots.py`, reusing the payload the card
  already fetched — zero extra credits; the daily opener run is what carries
  coverage through game day, wider than its own T-2 card window), and the
  publisher flushes the day's CSV into the `odds` table
  (`publish_line_snapshots`, bookmaker='draftkings', insert only for games a
  card has published, idempotent re-flush). The app maps `nfl_wind_totals` →
  totals / `nfl_opener_spread` → spreads in `gameMarketForModel`, so the
  movement chip + Line Movement card now work for NFL. Lines render from the
  PICK'S side (`lineForSide`/`formatSideLine`): spreads are stored home-relative,
  so an away pick labeled "NYJ +5" shows "Line +5 → +3", not the raw "-5 → -3"
  — **LINE-only**
  (`isNflLineOnly` / `computeMovement lineOnly`): the pick's stored price is
  best/soft-book, so comparing it to DK prices would be cross-book noise. NFL
  cards also always show "Locked Tue 8/18" (opener) / "Priced Sun 8:05 AM"
  (wind) from `created_at` (`nflTimingInfo` + `NflTimingCard` on the detail
  screen) so a day-of user knows the number is from earlier in the week —
  for the opener the note says outright that the model only endorsed the
  locked number.

---
