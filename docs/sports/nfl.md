# NFL — standalone wind/opener model (`nfl/`)

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 28. NFL — Standalone Wind/Opener Model (`nfl/`)

> **2026-10-11: the NFL edge search** (`docs/nfl_edge_search.md`). It covers why
> the in-play model was retired, and 14 ideas tested at zero credits. The
> in-play rushing-attempt under survives in-sample only. `nfl_prop_market` has
> bet nothing since 2026-09-19 (its EV floor grid is in §5).
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
| **Opener strategy** | **NOT proven profitable.** On the books you can actually bet at, 2020-2025: |dev| 1.0 = 728 bets, -0.03%; |dev| 2.0 (deployed since 2026-09-11) = 125 bets, +3.97%, CI [-11.8, +19.1] | The +6.98% [-0.6, +14.5] that stood here until 2026-09-11 was 2023-2025 only, all 35 books, exchange included. Adding 2020-2022 took it to +1.34% (2026-08-23, kept by Matt's call); restricting to bettable books (mike, 2026-09-06) took it to flat. Each step is in `nfl/models/opener_spread.py` and `docs/thresholds.md`. It runs as a forward test, not a proven edge |
| **Book integrity screen** | 4 offenders confirmed on 1.4M quotes across 40 books | betanysports, betsson, nordicbet, tipico_de — exclude these |

**Critical data rules:**
- **`nfl/data/odds_cache/` is IRREPLACEABLE — ~45,000 Odds API credits of spend.
  Remains tracked in git. Never delete, never gitignore.** Snapshot counts and
  on-disk size drift as the season accrues; do not treat a stale MB figure as
  current. Backup tarball: `nfl-model-odds-cache.tar.gz` (keep a copy outside
  this machine). See `nfl/data/odds_cache/README.md`.
- `nfl/data/weather_cache/` is gitignored and is a CACHE of Supabase, in both
  directions (2026-09-20). `fetch_issued_forecasts` reads the file on disk,
  else every hour of the window from `nfl_stadium_weather_hourly` (measured:
  a full season for one stadium, 2,976 hours, in 1.5 s with no network), else
  Open-Meteo -- and an Open-Meteo response is written to the table in the same
  call (only a full 1..7-lead pull; a one-lead replay pull is not stored, so
  it cannot block the full row). With no `DATABASE_URL` the module falls
  through to the file and the API and warns that the fetch was NOT stored;
  `python -m data.ingestors.nfl_weather_cache_import --apply` catches up (it
  resumes on its `source` marker, so a re-run writes nothing already stored).
  The 44 files / 117,192 stadium-hours on this machine went in that way.
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
- **Wind fires only inside 4 days of kickoff** (`MAX_FIRE_LEAD` in
  `nfl/models/wind_totals.py`, mike 2026-09-06). Polling still starts at T-10 —
  the eval board wants the whole slate and the opener needs the window — but
  nothing LOCKS past T-4. Three separate lead constants, do not conflate them:
  `MIN_LIVE_LEAD` (1) floors the probability, `MAX_CALIBRATED_LEAD` (7) is where
  the measured error distribution stops and the stake clips, `MAX_FIRE_LEAD` (4)
  is where we are willing to commit money.

  Why it was needed: making the stake clip past lead 7 (Matt, 2026-09-05) was
  right on its own terms, but the zero stake had been the de-facto firing gate.
  With it gone and the poll horizon at 10 days, **all five Week 1 picks locked
  at leads of 7.2–8.7 days, every one carrying `model_probability` 0.5489 — the
  lead-7 clip value — and 5 of 11 outdoor games qualified (45%) against a
  validated ~19%.** Waiting costs nothing: the rule is a standing closing-line
  inefficiency, not a race, and `CALIBRATED_UNDER_RATE` rises as the lead falls
  (0.5489 at 7 days → 0.5671 at 3 → 0.5735 at 1). Since the pick is insert-once,
  firing early bought the worse number permanently.
  Pinned by `tests/test_nfl_wind_fire_window.py`.
- **The six Week 1 picks written before the gate were VOIDED on 2026-09-07 and
  DELETED on 2026-09-11**, both on mike's instruction (the second overriding,
  for those rows, his own §1c "voided, never deleted" corollary — the rule
  stands). `picks_log` holds all six; see `docs/sessions/2026-09.md`,
  session 281. Their `opening_signals` captures stayed (`ON CONFLICT DO
  NOTHING`). mike, 2026-09-14: delete those leftovers (BUF@HOU, CLE@JAX,
  BAL@IND, NYJ@TEN, DAL@NYG, TB@CIN) and any other `nfl_wind_totals` capture
  with no standing pick; **keep DEN@KC Under 43.5 (pick_id 1969489)**. Worker
  migration `drop_voided_nfl_wind_opening_signals_2026_09_14.sql` in
  `ACTIVE_MIGRATIONS` applies on the next Railway pipeline/refresh pass
  after merge. No Discord re-announce.
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
  **≥ 2.0 pts** from Pinnacle's (regions `us,eu`, 2 credits/run), bet the side
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
  **The floor is 2.0 points since 2026-09-11 (mike: "way too many picks, I
  need statistical profitability"), was 1.0.** Measured on the selection the
  card actually runs — bettable books only, Kelly-skipped — over 2020-2025
  (`nfl/scripts/opener_cut_sweep.py`): |dev| ≥ 1.0 is 728 bets at −0.03%,
  ≥ 1.5 is 268 at −5.09%, ≥ 2.0 is 125 at +3.97% (5 of 6 seasons positive,
  CI [−11.8, +19.1]), ≥ 2.5 is 76 at −11.00%. No cell in the sweep has an
  interval excluding zero, so 2.0 is the strictest defensible cut, not a
  proven edge. `config` gate restored to 0.55 the same day (0.5557 at |dev|
  2.0 clears, 0.5470 at 1.0 does not — the calibration's original intent,
  lowered to 0.52 on 2026-08-22). The seven open Week-1 picks under 2.0 were
  VOIDED, not deleted (`scripts/void_picks.py`); BUF @ HOU at |dev| 2.0
  stands. Full table: `docs/thresholds.md`.

  **2026 live track (no unit bump):** live through 2026; retire if the season
  finishes ≤ flat. Wind: `MAX_FIRE_LEAD` stays 4; measure the deployed
  Open-Meteo population. Do not unpause paused XGB props off this track.
  `python -m scripts.nfl_rule_2026_track`. `docs/nfl_rule_2026_track.md`.

  **A fresh number is labelled, not blocked (`FRESH_MINUTES = 60`,
  2026-09-22, mike).** On 2026-09-22 the Odds API served BetMGM on TEN @ NYG
  at NYG -1 for one tick and NYG +1 for the next fourteen minutes, every
  other book at -3, and the 21:29Z tick locked `TEN @ NYG — NYG -1 (Opener +2
  vs Pinnacle, MGM) · 1.96u` — a number nobody found at the book (voided).
  It was the second BetMGM episode of that shape in 15 days (CHI @ CAR
  09-08, CAR +1 for 6-17 minutes). The first fix gated any number under an
  hour old; mike rejected it: a book hanging a wrong number for minutes is
  the BEST case this model can find IF it is placeable, and a gate guarantees
  it is never caught. So `held_minutes` measures how long the book has quoted
  its current point (from the card's own board dumps ∪ Supabase, change
  points, 24h) and the pick SAYS it — `· NEW 0m`, `· up 5h`, `· age unknown`
  — via `age_tag`, one formatter for the label, the printed card and the
  audit-trail reason. Nothing is skipped; `prior=None` (backtest) changes no
  selection. Whether fresh numbers are placeable is recorded per pick in
  `pick_placement_checks` by `scripts/mark_placeable.py` (`--report` lists
  every fresh-number pick and its answer); that record, not the feed or the
  backtest, decides the question. Speed: the poll's publish step re-flushed
  the whole day's DK snapshot CSV every minute (75 s at 21:30Z), so the
  one-minute poll ran every two — it is incremental now (`.flushed` marker),
  and the Discord post is made inside the tick, before the rest of the
  publish chain (`scheduler._post_opener_discord`). Measured latency before:
  number at 21:28:26Z, Discord at 21:29:41Z. Session entry in
  `docs/sessions/2026-09.md`.
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

## NONE rows: every game the wind and opener rules evaluated (2026-09-26)

Matt, 2026-09-26: *"There are only 7 bets showing under NFL. All bet lines
should be showing on the today tab."* Measured that morning: `picks` held 7 NFL
rows for the 9/27 slate (6 wind BET, 1 opener BET) against 14 games with odds
stored, and the app displayed all 7. The two rules only ever wrote BETs, so
the rest of the slate never reached the board.

`scripts/nfl_wind_publisher.py --scored` (`publish_scored`), run by
`scheduler.run_nfl_poll` right after `nfl_pick_monitor`, now writes one
`signal_type='NONE'` row per (game, model) from the newest row in
`pick_eval_<date>.csv`, the per-tick dump both cards already wrote.

- **What the row carries.** The quote the model looked at: wind is the best-book
  UNDER at its total; the opener is the soft book's HOME spread at the home
  price (DraftKings first while Pinnacle has not posted). The label uses the
  BET rows' `(…, BOOK)` shape, e.g. `CIN @ PIT Under 42.5 (no bet, DK)`, because
  the app reads the quote's book from it. The model's own words go in
  `downgrade_reason`.
- **Numbers.** Where the model priced the game (wind at or above threshold), its
  model probability and edge are used. Where it did not (wind below threshold,
  any opener row), the rule has no opinion, so model probability = the market's
  and edge = 0. `kelly_fraction` and `recommended_bet` are 0.
- **Never a lock.** Both BET locks are keyed on `signal_type='BET'`, and a BET
  that lands deletes its game's unsettled NONE row first. No NONE row is ever
  written beside a BET.
- **Refreshed until kickoff, then frozen.** The row is updated in place only
  when a number or the reason changes (with `created_at` set to the refresh
  time). Started games are not touched, so the last pre-game view is what gets
  graded (CLAUDE.md §7, the evaluation rule).
- **Never priceless.** A game with no line or price gets no row.
- **Not published anywhere.** Discord, push, opening signals and every record
  query read `signal_type='BET'`. `nfl_pick_monitor` now reads BET rows only.
- **Coverage.** Wind evaluates outdoor games only, so indoor games carry an
  opener row and no wind row. The opener watches T-0..T-10 days.

## NFL player-prop injury veto

Pre-game props (`nfl_prop_market`, and `run_nfl_prop_scorer` for any live
distributional sibling) refuse a player listed **Out** or **Doubtful**
when ESPN's injury `date` (`injuries.status_ts`) is ≤ the quote's
`snapshot_at`. News after the line is ignored. Not an XGB feature.
Detail: `docs/nfl_prop_injury_veto.md`.

---

## In-play leader moneyline (`nfl_live_leader_ml`) — LIVE 2026-10-13

mike, 2026-10-13: *"reenable the model"*. Built LIVE (CLAUDE.md §2: a model
mike asks for is built live, gate met or not). **Go-live gate: 0 settled of 50.**

**What it bets.** In the 4th quarter, once the last play was snapped with
10:00 or less left, when one team leads by 4 to 16 points: the leader's
DraftKings live moneyline, when the model's win probability beats the price's
implied probability (vig included) by 0.02 or more. One bet per game, the first
evaluation that qualifies. Overtime is never priced.

**The model.** Thirteen logistic regressions, one per exact lead 4..16, on
every 2016-2025 regulation play with 10:00 or less left (47,681 states in 2,123
games): win probability from the log of the seconds left, whether the leader
has the ball after the play (and its interaction with the clock), and whether
the leader was a pregame favourite or underdog by 3.5+ on the closing spread.
Artifact: `models/saved/nfl_live_leader_ml_wp.json` (coefficients at full
precision, a golden grid, the rule). Builder:
`python -m scripts.build_nfl_live_leader_artifact` (`--seasons` to refit).

**The evidence, and how thin it is.** The 2024/2025 in-game study
(`scripts/nfl_edge_inplay_2024.py`, `docs/nfl_edge_search.md`), cell "leader
ref=pbp secs<=600 edge>=0.02" at DraftKings:

| Season | Fit used | Bets | Units | Return |
|---|---|---|---|---|
| 2024 | 2016-2023 | 87 | +13.79 | +15.8% |
| 2025 | 2016-2024 | 80 | +1.84 | +2.3% |
| Pooled | | 167 | +15.62 | +9.4% (90% CI +1.8% to +16.8%, p 0.022) |

It did not survive the study's pre-registered multiple-testing family; 2025 on
its own is flat; and the shipped artifact is fitted on 2016-2025, so **both
graded seasons are in-sample for it** — it has no out-of-sample record of its
own. `--parity` rebuilds the two grading fits, checks them bit-for-bit against
the study's own fit, and replays the bought 2024 and 2025 snapshots through the
model's decision function: 87 bets / +13.79u / 0 pushes and 80 bets / +1.84u
/ 1 push, bet for bet. That proves the decision function, on the study's own
states. It does not prove the loop, which sees different states.

**The population of record: what the loop would have bet.**
`python -m scripts.build_nfl_live_leader_artifact --population` replays the
same snapshots the way the loop sees them. It refuses a state straight after
a touchdown, extra point, two-point try, made field goal or safety, and tries
the game again at its next snapshot. It takes the favourite band from
DraftKings' last pre-kickoff spread. And it lags the game state behind the
quote. Grading fits, first bet per game:

| State lag behind the quote | 2024 | 2025 | Pooled |
|---|---|---|---|
| 0 s | 83 bets, +10.91u | 80 bets, +2.17u | **163 bets, +13.08u, +8.0%** |
| 15 s | 80 bets, +10.41u | 82 bets, +1.80u | 162 bets, +12.21u, +7.5% |
| 30 s | 77 bets, +10.32u | 82 bets, +0.71u | 159 bets, +11.03u, +6.9% |
| 45 s | 79 bets, +12.45u | 81 bets, −0.44u | 160 bets, +12.01u, +7.5% |
| 60 s | 78 bets, +13.69u | 82 bets, +0.04u | 160 bets, +13.72u, +8.6% |

The lag is real. ESPN core posted a play a median 23 s after its snap (10th to
90th percentile 12 to 37 s; 40 plays in two college games read every 5 s,
2026-10-14). The study timed each play from when it ended, a few seconds after
the snap, and the loop reads ESPN every 20 s. So **the rows to expect are 15 to
45 s, not 0 s.** The pooled return moves within noise across them. 2025, the
season closest to out-of-sample, goes from +2.17u to −0.44u. Every EVAL log
line carries `play_lag`, the seconds between the last play's ESPN stamp and the
evaluation, so the first NFL Sunday measures the NFL figure directly.

**At the published stake the return is lower.** The tables above risk 1 unit
on every bet. Discord, X and `results_snapshots` publish 1 unit TO WIN with the
risk capped at 3 units (`tracking/discord_notifier.stake_for`), so this
model's short prices risk 2 to 3 units each. On the population of record that
is +19.92u on 401.2u risked, +5.0%. At 15/30/45 s of lag: +4.6%, +3.6%, +2.1%.
2025 alone at that stake: +2.77u, +2.47u, −0.28u, −5.28u at 0/15/30/45 s. The
go-live gate and the 50-bet re-read are on the flat 1-unit basis
(`tracking/live_calibration.py`), the same basis as the tables above.

The shipped 2016-2025 fit is not the graded one. On the same lag-0 frames it
keeps 154 of the 167 graded bets, drops 13 and adds 19: 173 bets, +16.13u on
the study's states. Both seasons are in-sample for it, so that is not evidence.

**How it runs.** `nfl_live_leader/` from the repo root (not `nfl/` — the import
trap in `data/live_quote_guard.py`), scheduler job `nfl_live_leader` on the
poller service, 9am-midnight ET every 10 minutes, `RUN_NFL_LIVE_LEADER` (default
on). The loop reads ESPN's core API every 20 s (site.api is 403 from the
worker) and exits after three idle ticks. A game in the window is evaluated
at most once per five-minute slot of the wall clock (:00, :05 ...), at the
first read inside the slot, as the study's 5-minute snapshots were. A slot whose
state is not evaluable is used up, not carried to the next read.
Only then does it make ONE bulk DraftKings moneyline call for every due game:
`x-requests-last` measured **1 credit per call** (2026-10-13). Capped at
`NFL_LIVE_LEADER_CREDIT_CAP` (2000) per process, and at
`NFL_LIVE_LEADER_CALL_CAP` (400) calls, because a call that fails before its
header is read moves no credit meter. A failed call backs off 60, then 120,
then 300 s. A game is priced only at the DraftKings event with its own two
teams AND its own kickoff (within six hours), so a later rematch listed in the
same feed can never price it. Each DraftKings quote it decides on is written to
`odds` as `in_play`. The push and Discord notifiers are called on the pass that
writes a bet, then at most every 300 s for any slate date that carries a bet of
record, so a failed post is retried (their ledgers make repeats no-ops). Only regular season
and playoff games are priced (ESPN core season type 2 or 3); preseason and an
unknown type are refused. After the final snap, before ESPN marks the game
final, an end-of-game row or a 4th-quarter clock at 0:00 is a refusal.

**The inputs are built to the training definitions, and were measured.**
Against 17 finished 2026 games (weeks 4-5; core event 401872980, TB @ DAL, is
the week-5 one), matching each ESPN core play document to the same nflverse
play:
- `play.clock.value` is the clock at the SNAP on 2,190 of 2,191 non-scoring
  plays, and `play.homeScore`/`awayScore` are the post-play score on 2,191 of
  2,191 — which is what the model was trained on. The running clock is never
  used.
- A scoring play's clock is the END of the play (0 of 65 equal the snap). In
  the finished game document its score already includes the extra point; live
  core instead posts "Extra Point Good" as its own play after the touchdown.
  The loop refuses both, so it never evaluates straight after a score.
- Timeouts, the two-minute warning and period ends are skipped when choosing
  the last play (the training data has no such rows).
- Replaying those games' 4th quarters through the adapter (the situation taken
  as the next play's start): 270 of 270 evaluable states in the window match
  training on clock, score and possession.
- The live `situation` document names the team with the ball as `team` and
  never carries a `possession` key: a live core football game (college event
  401871067), read every 20 s for 51 minutes on 2026-10-13, 146 in-progress
  reads, `team` in 96, `possession` in 0. `team` is blank after a score and
  after a kickoff until the next snap is posted (40, 40, 60 and 81 s on the
  four kickoffs); the loop skips those reads.

**Possession bugs in the old core parser, fixed here.**
`nfl/live_model/feeds/espn_core.py` (retired worker, not used) read
`situation.possession`, which core does not send, so it never found a
possession at all. And it matched the team id as a substring of the whole
reference URL. Core's team references carry the season
(".../seasons/2026/teams/27"), so a home team whose id is part of "2026" —
Dallas is 6 — would have read as having the ball on every play.

**The spread.** DraftKings' last spread before kickoff from `odds`
(`snapshot_type <> 'in_play'`, `snapshot_at <= commence_time`), else
`nfl_odds_history`. It is the HOME handicap, so the leader's expected margin is
`-spread_home` when the leader is home and `+spread_home` when away. No spread
means no bet, never 0. The study used nflverse's consensus closing line, and
the two differ: on TB @ DAL (2026 week 5) DraftKings' last pre-kickoff spread
was -8.5 against nflverse's 9.5. Measured on the bought seasons
(`--population`): DraftKings had a spread for 285 of 285 games each season; it
equalled nflverse's on 196 (2024) and 220 (2025), and differed by a point or
more on 17 and 34. Of the in-window snapshot states, 25 of 670 (2024) and 3 of
693 (2025) land in a different band. The population of record above uses
DraftKings' line.

**What differs from the study, and is not measured.**
- Timeouts: after a timeout live core's situation reads down 0 with no team,
  which the loop refuses. The study cannot see timeouts, so how many of its
  snapshots fell in one is unknown.
- Quote age: the study could not see DraftKings' own quote age or its market
  suspensions. The loop skips a quote DraftKings stamped before the last score
  change it saw; nothing else.
- **Price floor −140** (mike, 2026-10-16, after the first live bet laid −980
  on SEA @ DEN; `config.MODEL_MIN_ODDS`). A shorter price is refused and the
  game is tried again at its next slot. On the population of record that
  leaves 43-46 bets over two seasons (about 22 a season), +12.02u at no lag and
  +15.40u to +19.85u at 15-45 s, against 163 bets and +13.08u with no floor;
  the bets at −500 or shorter had made −0.10u. In-sample; table in
  `docs/thresholds.md`.
- No book-move, settled-state or edge-cap guard: none was in the study. The
  EV floor is set not to bind (`MODEL_OWN_EV_FLOOR` 0.02, its own
  probability).
- The model knows no field position, down, distance or timeouts; DraftKings
  does.
- Settlement: a tie leaves `games.home_win` NULL, which settles the pick at 0
  units, as the study's push did.
