# NCAAF — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 31. NCAAF — Pipeline Operations
NCAAF (FBS college football) is the 8th sport. Unlike every other sport, its two
live models are RULES over regressions/openers, not calibrated classifiers —
because the exhaustive model search (below) established that classifiers add
nothing over the closing line in this market.

### Models live (2026 season, PAPER-FIRST despite being active)

| Model ID | Kind | Rule | Status |
|---|---|---|---|
| `ncaaf_over_under` | `total_regression` | Predict the game total from fundamentals (market number NOT a feature); bet the side of the disagreement only when \|pred − DK total\| ≥ 8.0 (symmetric gate, stored in the artifact); P(over) from the OOS-residual ECDF | LIVE — walk-forward 55.9% / +6.7% at the gate, best in all 4 test seasons; CI does not clear breakeven, sized small |
| `ncaaf_spread` | `cross_book_opener` | Back the side Bovada's OPENER favours, at DraftKings' stale OPENING number. Three preconditions in the scorer, each `return []`: (1) both openers captured within 90 min (`OPENER_MAX_SKEW_MIN`), (2) DK still ON its opener, (3) \|dev\| ≥ gate | LIVE but STRUCTURALLY DORMANT on this feed (measured 2026-09-07, session 252). Backtest 1,050 bets 58.1% +10.9%, CLV 0.694 — but CFBD's `spreadOpen` carries no timestamp, so the +10.9% was never measured under precondition 1. In production the Odds API lists next week's games from Tuesday with DraftKings and FanDuel priced and NO sharp book: a paid historical snapshot at 2026-09-03T17:55Z (requesting only DK, Bovada and Pinnacle) showed 16 events for 09-12/13 with DK priced and Bovada and Pinnacle absent, while both sharp books covered that week's own slate. Bovada's first stored number lands the Sunday before, by which time DK has moved off its opener on 40 of 49 games. The only firing condition observed is a game that ENTERS the feed with both books already priced (FAU@Florida 2026-09-05, 1-minute skew — the one spread BET this season). Two pre-game BETs all season, both lost |
| `ncaaf_spread_premium` | `cross_book_opener` | The SAME rule, band **[2.5, inf)** — the scorer's `d_threshold_max` on `ncaaf_spread` caps it at 2.5 so the two tiers are MUTUALLY EXCLUSIVE and a game fires exactly one | LIVE — 344 bets 60.5% +15.4%, positive all 3 seasons, CI [0.552,0.655] |
| `ncaaf_moneyline` | — | — | PAUSED — classifier held out at AUC ~0.50 |

Thresholds: over_under 0.65/0.0, spread 0.55/0.0 (the spread floor sits under
the rule's ~0.58 flat validated prob ON PURPOSE — the gate IS the filter, the
prob floor must never suppress a qualifying pick).

**The two spread tiers are DISJOINT, not nested.** A tighter gate is a strict
subset of a looser one, so shipping both with a shared floor would fire two
picks on the same side of the same game — double staking, two rows in the app
for one bet. `ncaaf_spread` is capped at 2.5 by `d_threshold_max`;
`ncaaf_spread_premium` starts there. Bands verified as a partition
(706 + 344 = 1,050) and each clears the 4% bar alone: standard 56.9%/+8.7%,
premium 60.5%/+15.4%, both positive in all three seasons. That independence is
what makes the tier ADDITIVE rather than a re-slice — if the remainder band had
collapsed, the right move would have been to tighten the single gate instead.
Re-derive with `opener_strategy.py --experiment bands`; register with
`register_opener.py --bands`.

### The model search is CLOSED (2026-08-27) — every lever tested, verdicts pinned

All harnesses live in `scripts/ncaaf_search/` and re-run against the DB. House
rules for any future NCAAF analysis: definitions fixed before results, variant
count reported, per-season records, Wilson CI vs 0.5238, and a TIME SPLIT that
must hold in both halves — that split is what killed every false positive.

| Lever | Harness | Verdict |
|---|---|---|
| 42-config classifier search (6 families × feature groups, ATS + totals) | `run_search.py` | NULL — CLV 0.41–0.48 everywhere, nothing clears the 5 gates |
| QB continuity (31.6K passer-games, `ncaaf_qb_game`) | `qb.py` + `qb_ablation.py` | NULL — helps 2/7 totals + 3/7 margin gates (coin flip), RMSE unchanged; the one positive spot cell is home/away confounding (mirror case shows nothing). "Starter out this week" was untestable when this ran (no CFB injury feed) — only continuity was testable, and it is priced. The hindsight version is the row below |
| **Starter OUT, with hindsight** (perfect-information upper bound for the availability-report spike Matt approved 2026-09-07) | `starter_out.py` | NULL — 760 team-games 2021-2025 where the established starter (primary in ≥2 of the last 3 same-season games) has NO box-score row. At the Bovada close: fade the team 51.5% [0.479, 0.551], back it 48.5%, under 48.0%; no season clears 0.5238 and both halves of the time split sit at ~51%. Power: ~4pp detectable. Decisive in the null direction — nothing above breakeven is detectable at the close even when the absence is KNOWN (~4pp power), so an availability feed has nothing to rescue at the close. The 51.5% fade vs the 48.6% "starter played" row is a ~3pp gap inside the OUT arm's own interval, and that row is not an independent control (it holds the other side of every OUT game). What it cannot measure: the window between announcement and close, which needs an announcement timestamp and the intraday archive |
| Weather spot rules (12 seasons, reanalysis) | `weather_totals.py` | NULL — unlike the NFL, the CFB market MOVES its total with wind (55.7 calm → 53.4 at 18+); wind≥12 = 54.0% pooled but late-half 51.2% and the ~2.5pp forecast haircut kills it; the 61% wind+rain cell is a time-split mirage (70% early / 34% late) |
| Line-movement follow/fade at the close (4,311 Bovada open+close pairs) | `line_move_spots.py` | NULL — follow = 50.0–52.4% at every threshold, no fade signal either; the close subsumes its own movement |
| Look-ahead / let-down schedule spots | `situational_spots.py` | NULL |
| **Steam lag** (Pinnacle moved >= k between two stored pulls, DK moved < k/2 and DK's line is OLDER than Pinnacle's; bet DK's stale number the way Pinnacle went; 2023-2025, 47,303 consecutive-pull pairs) | `steam_lag.py` | NULL — totals k=1: 407 bets 52.1% [0.472, 0.569]; k=0.5: 705 at 50.2%; k=1.5: 59 at 54.2%. Spreads k=0.5: 781 at 48.1%; k=1: 229 at 50.7%; k=1.5: 115 at 53.0% (2024's 85.7% is 21 bets). Control "DK followed" 49.6-51.0% on 951-3,624. DK's close does drift toward Pinnacle after a lag (39% of totals events vs 22% away, +0.29 points), so the lag is real and the CLV is a third of a point — it does not turn into wins at a -110 price. Two pulls a day cannot see how long DK stays stale |
| **Consensus anchor + dispersion** (the totals rule gated on the 13-book median total, or on Pinnacle, instead of DK; and split by max-min across books) | `consensus_gate.py` | FLAT — DK 56.4% (314), 13-book median 56.9% (313), Pinnacle 55.4% (316): the same bets. DK sits a mean 0.16 points from the median; dispersion >= 1.5 in 17% of games, and gating on it does nothing (54.5% on 55). The edge, such as it is, is model-vs-market, not DK-vs-sharp. Time split, all anchors: early half 58.7-59.9% (+), late half 50.8-52.7% — the rule's record is early-season |
| **Totals rule at earlier leads** (0-5 days out, DK 14:00Z line, 2023-2025 backfill, 2,194 matched games) | `totals_lead.py` | FLAT — at the shipped ±8 gate: 0d 56.4% (307), 1d 55.2%, 2d 53.8%, 3d 54.0%, 4d 55.3%, 5d 55.6% (232), DK close 56.4% (314), archive close 57.3% (309); every Wilson interval overlaps every other and none clears 0.5238 at 95% (lower bounds 0.482-0.517). Close-minus-lead movement in the pick's direction is -0.12..+0.07 points at every lead: no CLV, the market does not converge on the model. First-signal lock from 5 days out: 384 bets 55.7% [0.507, 0.606] vs 321 at 57.0% [0.515, 0.623] on game day. Per season 2023 52-56%, 2024 57-62%, 2025 50-57%; time halves 52-58% / 52-60%, no sign flip. Verdict: earlier is not measurably worse and not measurably better; the lead limit is a timing choice, not an edge choice |
| Moneyline (margin regression -> P(win) vs real Bovada prices, 2,877 games) | `outcome_edge_scan.py` | NULL — calibration is superb (0.999 decile correlation) but EVERY edge cell loses at real prices (-2.8%..-8.9%): the book's implied probs are sharper than the model's and the 4.4% overround eats the rest. `ncaaf_moneyline` stays paused |
| Outcome x edge conditional surface (all 3 markets, 36 cells, 4-season walk-forward) | `outcome_edge_scan.py` | The one POSITIVE finding of the search — but it CONFIRMS the live totals rule rather than adding a new one: at the shipped ±8 gate, 9/9 cells are above breakeven (~55.6% over 464 bets, +6.4% at -110), the effect is DIRECTION-SYMMETRIC (over-side 56.1%, under-side 54.5%, both halves both sides), monotone turn-on lands exactly at 8 (the 6-8 band is 47-52%), and it holds in every line band and week band. Spread margin regression stays dead across 4 seasons (50.1-50.8% pooled; its 53.6% was a one-season artifact; the dog>fav asymmetry never reaches breakeven) |
| Margin regression (spread) | `ncaaf_margin_eval.py` | Passed its 2025 kill line (53.6% @ ±5.5) but ~50% across the 4-season walk-forward — 2025 was its one good year. Superseded by the opener rule |

**What this means:** the two live rules ARE the survivors. Do not re-mine
features on this data; new edge requires new INFORMATION (an injury/news feed,
or the bovada/pinnacle intraday history now accruing in `odds` for
future-season stale-number work).

### The board: a week-long window, and "watching" is a row (2026-08-29)

NCAAF plays one slate a week, so a same-day board is empty six days out of
seven — and both rules answered a game they would not bet with `return []`, no
row at all. The result was a sport that looked like it was not running. It also
made the opener rule structurally DORMANT: it only fires while DK is still on
its opening number, which is rarely true by kickoff.

- **Look-ahead**: `NCAAF_SCORE_AHEAD_DAYS` (150) puts every game DraftKings
  has priced in the scorer's game query and in the app
  (`fetchUpcomingNcaafPicks`). It was 7 until 2026-09-07 (Matt: *"it should
  be whenever lines are released. speed speed speed is what matters to get a
  good line"*); the DK-price prefilter is what admits a game, so the window
  is the season and the extra rows are the marquee games DK lists months out
  (44 beyond 14 days on the day it changed).
- **A decline writes a row.** Every precondition failure now yields a NONE row
  carrying DK's live number and a reason, instead of nothing. An empty board
  and a broken pipeline are indistinguishable to a user — which is exactly how
  the 2026-08-29 outage below stayed invisible.
- **The lock is signal-aware for NCAAF only.** `locked_pairs` excludes NCAAF
  NONE rows, so a "watching" row is refreshed every pass while a real signal
  still locks at first cross (the opener rule's whole thesis). Without this a
  Monday NONE row would freeze the game for the week and the totals rule —
  game-day by design — could never fire at all. The NONE rows are delete +
  rescored each pass, scoped to unstarted games.
- **The totals rule has NO lead limit** (`NCAAF_TOTALS_MAX_LEAD_DAYS` = inf):
  it fires at the first scoring pass where DK's total sits 8+ points from the
  model, whenever that is, and locks there. It shipped at 1 (game day) because
  it had only been walked forward against the archive's close. **Measured
  2026-09-07** on the 2023-2025 DraftKings backfill
  (`scripts/ncaaf_search/totals_lead.py`, row in the search table below):
  graded at DK's 14:00Z line 0-5 days out, the ±8 rule runs 53.8-56.4% at
  every lead against 56.4% at DK's close (its last 14:00Z/23:00Z pull before
  kickoff), every interval overlapping every other, and the close-minus-lead
  movement is ~0 points in the pick's direction at every lead — the market
  does not drift toward the model, so waiting buys nothing and going early
  costs nothing detectable at ~5pp. Under the first-signal lock from 5 days
  out: 384 bets at 55.7% [0.507, 0.606] vs 321 at 57.0% [0.515, 0.623] on
  game day. Nothing at any lead, game day included, clears 0.5238 at 95% on
  three out-of-sample seasons. It went to 5 that evening (PR #577) and to
  none the same night at Matt's call. Unmeasured: leads beyond ~7 days (DK
  listed 84 of 2,651 backfill games that early) — a statement about the
  sample, not the rule. **"All books" buys no speed on totals, measured:**
  every book's first NCAAF total lands a median 5.4-5.9 days before kickoff;
  the gap between the earliest book and DK is a median 0.0 days, 90th
  percentile 0.62, and only 205 of 2,651 games had any book a full day ahead.
  The opener rule has no limit either: its own preconditions are its window.
- **The FBS gate does most of the filtering.** Week 2 is 117 games, 39 both-FBS,
  ~52 DK-priced — so the board is tens of games, not hundreds.

### Data / conventions (load-bearing)

- **A night game has TWO `games` rows, and that is by design.** The odds
  ingestor dates a game by its EASTERN kickoff; `cfbd_ingestor.parse_games`
  dates it by CFBD's UTC `start_date`, so a ~8pm-ET-or-later kick exists under
  two ids (`NCAAF_2026-08-29_memphis_unlv` and `..._2026-08-30_...`). PICKS
  ALWAYS ATTACH TO THE ODDS ROW — it is the one that exists when the board is
  priced — and CFBD writes the final to its own. `mirror_scores_to_alias_rows`
  (called from both `ingest_ncaaf_results_for_date` and `ingest_ncaaf_games`)
  writes the orientation-corrected final onto every row that is the same game,
  matched on the slug pair within ±1 day. Deliberately NOT a re-key: `game_id`
  is the FK for `ncaaf_team_game_log` and `ncaaf_qb_game` across 2015-2025, so
  re-deriving the date would orphan a decade of training rows for no modelling
  benefit. An existing final is never overwritten, and a candidate matched by
  two conflicting finals is left unscored rather than guessed (`±1 day` is
  load-bearing — an annual rivalry repeats the slug pair every season).
- Canonical team id = CFBD SCHOOL NAME (accents folded via `_fold`); game_id
  slugs. Historical lines under `cfbd_*` bookmakers (provider priority
  `NCAAF_LINE_BOOKMAKER_PRIORITY`; 2023-25 DK, 2019-22 Bovada, 2015-18
  consensus). Openers are protected from the pruner (earliest snapshot per
  proposition per book — `test_prune_preserves_openers.py`).
- `ncaaf_qb_game` (added 2026-08-27): every passer per team-game 2015-2025,
  `is_primary` = most attempts (validated against the real 2023 QB carousels).
  Kept current by the weekly in-season step; feeds no model today but is the
  substrate if an injury feed ever lands. `--backfill-qb START END` refreshes.
- `ncaaf_player_game_log` (added 2026-08-30): EVERY player per team-game —
  passing, rushing, receiving and defense — behind the mobile Stats tab's NCAAF
  player leaderboard (`v_player_season_totals_ncaaf` +
  `player_window_totals_ncaaf` / `player_recent_games_ncaaf` /
  `player_season_stat_values_ncaaf`; migration
  `add_ncaaf_player_stats_leaderboard.sql`). **Display only — no model reads
  it**, and it does NOT replace `ncaaf_qb_game`, which stays the modelling
  substrate (one row per passer, `is_primary`, FK'd by a decade of training
  rows). Both are filled from ONE `/games/players` pull
  (`ingest_ncaaf_player_logs`), so the wider table cost zero extra CFBD calls.
  Three load-bearing details: **one row per PLAYER, not per category** (CFBD
  lists a running QB under both `passing` and `rushing`); **a player whose every
  tracked stat is zero is dropped** (kickers/punters/returners would otherwise
  go 12-for-12 on an "at most N yards" board — the NFL leaderboard lesson); and
  **no position column**, because CFBD's box score names participants, not
  positions, so the board groups by STAT rather than by a guessed position.
  Column names match `nfl_player_game_log` wherever the two sports share a stat,
  so one mobile catalog key means one thing in both football leagues; there are
  no `targets` (CFBD does not report them) and no NCAAF prop models, so the
  leaderboard never offers "Add to play" — but it does now carry a LINE, from
  `data/ingestors/ncaaf_prop_odds_ingestor.py` (2026-09-05): college props are
  pulled for games DraftKings already prices, and the board reaches its market
  through `FOOTBALL_STAT_TO_MARKET` rather than through a model, because it has
  none. A college prop row is research and never a pick. Live since 2026-09-05
  at 9am/1pm/6pm ET (`RUN_NCAAF_PROP_ODDS=1`), ~590 credits a pass over the 68
  events the feed lists — `docs/cloud_worker.md` has the measured breakdown. `--backfill-players START END` fills
  history (~17 calls per season).
- Weather: `game_weather` rows for ~99% of 2014-2025 games (3pm-local
  Open-Meteo REANALYSIS — truth, not forecast; any historical weather edge is
  an upper bound). `scripts/ncaaf_weather_backfill.py --seasons A B` fills
  gaps; `ingest_upcoming` writes forecasts for the coming week.
- Weekly ops in season: `step_ncaaf_stats` (schedule + box scores + QB log +
  player log + snapshots, ~50 CFBD calls — the player log rides the QB log's
  existing `/games/players` fetch and adds none) and `step_ncaaf_results`
  pre-settle. Off-season
  the schedule pull returns nothing — that IS the gate.
- Totals-regression refits: re-run `python -m scripts.ncaaf_margin_eval
  --fit-totals` periodically in season so the artifact sees the current year;
  the fit refuses to register if the walk-forward no longer clears the kill
  line.

### `ncaaf_live_total` — what has been tried, and the standing instructions

**STANDING INSTRUCTIONS (mike, 2026-09-12). Do not re-raise either of these.**

- **`ncaaf_live_total` is NOT paused and NOT capped.** Asked and answered
  twice. It keeps betting at its current cut. A session that finds the
  evidence below and proposes a pause or a per-day cap is proposing something
  already refused — write the evidence down instead.
- **THE BEST BOOK ALWAYS DECIDES.** Not DraftKings. This is the standing rule
  for the live models (mike: *"remove DK only - we want best lines for us
  regardless"*, shipped in #634) and it is not reopened because a cut was
  swept on DK-only history. If a cut and the decision price disagree,
  re-sweep the cut — do not move the price basis back.

**What is measured, so it is not re-measured.** Four attempts, all on the 2025
in-play replay, all first-signal-locked and read out of sample:

| Attempt | Result |
|---|---|
| Tighter prob/EV cut | No evidence above prob 0.72 — every cell there is first-half-only |
| Recalibrating the probability | Slope **0.135**. The whole 0.60–0.94 claimed range compresses to 0.51–0.59. Adding live-line deviation (+0.003) and time remaining (0.000) adds nothing |
| Rebuilding stage 2 | The distribution IS ~70% too wide inside 10 min (width ratio 0.51, tails 15.7% vs 20%), and `shrink_k` repairs it (0.92, 18.8%) — but re-priced at real DK lines it gets **worse**: slope 0.268 → 0.145, Brier 0.2534 → 0.2552, log-loss 0.7009 → 0.7047 |
| Per-day cap | Top-1/day is +11.4% on 21 bets, but taking the WORST 2–3 by EV returns +8.5%/+10.3%. The ranking does not discriminate, so the gain is from betting less, not choosing better |

**Stage 1 is sound and was not changed.** Predicted remaining points are biased
by +0.2..+1.2 at every time bucket and every predicted level, and the error on
the total matches the error on the margin (RMSE 6.38 vs 5.69 late, 15.57 vs
15.03 early). The engine knows how much scoring is left.

**Why the same engine is acceptable for `ncaaf_live_win_prob`:** margin errors
partly cancel between the two sides and total errors do not, so the margin
width ratio is 0.95+ everywhere except the last ten minutes while the total's
falls to 0.51. That is also why the pregame-status correction worked there
(slope 0.816) and recalibration failed here (0.135).

**What would be a new attempt, as opposed to a repeat:** information the model
does not have. Everything above re-arranges the same two-stage output. The
harnesses are `scripts/ncaaf_live_total_rebuild.py` (stage-2 sweep, three
out-of-sample read-outs) and `scripts/ncaaf_live_total_repricing.py` (the
decisive one — re-prices held-out candidates at their OWN DK line under two
distributions). A proxy line does not decide this: the rebuild script's own
pregame-total read-out scores the shipped model at 1.30 where the real line
scores it at 0.27.

### Session 280 (2026-09-10) — the pre-game board audited, and what changed

Full detail in `docs/sessions/2026-09.md` (session 280). What a future
session needs to know:

- **The pre-game board is ONE model.** `ncaaf_moneyline` is paused; both
  spread tiers are live and cannot fire on this feed, measured on 2026: of
  249 DK-priced games, 18 had a Bovada opener inside the 90-minute skew and
  17 of those agreed within 0.5 pts; on the 128 games where Bovada posted
  later (median 5.2 days), DK's line at that moment sat 0.28 pts from
  Bovada's opener, zero at the premium band. mike declined to pause the
  tiers on 2026-09-10; they stay live, and they will keep writing "watching"
  rows.
- **"Watching" rows now say why.** Every precondition failure or inside-the-
  gate decline persists its reason in `picks.downgrade_reason`
  (`scorer._apply_no_signal`). Before this, 0 of 1,012 non-BET rows carried
  one; the doc above claimed they all did.
- **A paused model is paused on both sides** (`scorer._paused_signal`,
  sport-agnostic): `ncaaf_moneyline` had written 80 AVOID rows the Signals
  board rendered as fade signals.
- **The totals under-lean is real and small; it is spread across inputs, with
  no single feature, NaN column or artifact bias found.**
  `scripts/ncaaf_search/totals_input_drift.py`: on the 2026 board the
  production artifact predicts a mean 0.85 below DK (56.6% of games below)
  against +0.68 (47.3% below) on 2025's games through 09-20; the same lean
  inside 7 days as beyond. The market is 0.6 higher, the prediction 0.9
  lower, spread across scoring and defence inputs (no single feature, no
  NaN column); with every feature set to the 2025 mean the artifact predicts
  52.9 vs 53.1. The ECDF's −0.62 offset turns a −0.85 mean into P(under) > 0.5
  on ~three quarters of rows, which is what the board shows. The one-at-a-time
  weather deltas also fill the 44% of board rows that have no weather, so
  they partly measure missing weather; the within-7-days (−0.82, 16% missing)
  vs beyond (−0.91, 100% missing) split is what shows missing weather is not
  the driver.
- **The information test the NFL props got, run on the totals rule**
  (`scripts/ncaaf_search/totals_information_test.py`, DK close, de-vigged):
  b = +0.137 ± 0.085 (fit 2023 → read 2024) and +0.101 ± 0.086 (fit 2024 →
  read 2025). Positive both pairs, neither interval excludes zero; the book
  beats the raw model on Brier in both seasons and the blend beats the book
  by ≤ 0.001. The same verdict as the eleven NFL prop models: at the close
  the disagreement is at most marginal information.
- **Books we never request post LATER than DK, and FanDuel posts earlier.**
  One 20-credit historical snapshot (`book_timing_snapshot.py`, Monday
  2026-08-31 12:00Z, stored in `odds` as `odds_api_historical`): FanDuel,
  BetRivers, BallyBet, BetParx and Hard Rock carried 99-102 of 103 events
  against DK's 75 (FanDuel had 28 games DK did not); betonlineag 53, lowvig
  50, betus 43, betanysports 43, mybookieag 40, every one behind DK. Now that
  the decision price is best-of-book (#634), FanDuel's earlier posting is
  worth measuring as a lead; the offshore books' is not. The pull also
  created 11 `games` rows for already-played FCS-visitor games (two with the
  mascot in the id); none has a pick and they are listed for deletion in the
  session entry.
- **Kalshi lists NCAAF game markets and is now recorded** every hour at :45
  (`data/ingestors/kalshi_game_ingestor.py` → `kalshi_game_markets`): 478
  winner contracts on 239 events, 2,008 total-ladder and 2,541 spread-ladder
  contracts on 120 events at the first snapshot. Research only. The join to
  our game ids is `kalshi_ncaaf_events` (event code → `game_id`), refreshed
  after every snapshot from the winner contracts' team names: 154 of 239
  events resolved on 2026-09-11 and every FBS-vs-FBS event among them; the
  unresolved remainder are FCS games. Extend `KALSHI_TEAM_MAP` in
  `data/ingestors/kalshi_game_ingestor.py` when a label fails to resolve.
- **Issued forecasts exist for 2024-2025** (`game_weather_issued`, leads
  1/3/5, `scripts/ncaaf_weather_issued_backfill.py`), the train/serve repair
  for the three `wx_*` features. `scripts/ncaaf_search/totals_weather_source.py`
  measures the four arms (reanalysis / served / issued / none). At the 8-pt
  gate the deployed arm (train on reanalysis, serve the lead-3 forecast) reads
  53.8% in both 2024 and 2025 against reanalysis's 62.0% / 52.9%, every
  interval overlapping; training on one season of issued forecasts gives
  47.6%; no weather at all is worst (51.7% / 44.8%). The forecast haircut is
  real in one season of two and not separable at ~90 bets a season. Artifact
  unchanged; the issued series accrues for a two-season refit.
