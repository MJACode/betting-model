# NHL — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

> **2026-10-20 (mike): NO NHL BET OF ANY KIND UNTIL BOTH STARTING GOALIES ARE
> CONFIRMED.** *"We should absolutely always know the goalie matchup before
> making a bet as well."* All eight NHL models (`nhl_moneyline`,
> `nhl_moneyline_regulation`, `nhl_over_under`, `nhl_puckline` and the four
> prop models) and any added later. No exemptions.
>
> **Why.** `nhl_goalie_stats` held one row per team per game, written once at
> ~10:06Z from ESPN's probable starter (`data/ingestors/nhl_stats_ingestor.py`).
> ESPN says whether that name is `expected` or `confirmed`; the parser kept
> the flag and the writer threw it away. The 6am goalie did not start in 65
> of 251 team-games 2026-10-01..10-19, and in 22 of 70 (31%) for
> 10-14..10-19. On 10-20, MTL (a Fowler row; Dobes confirmed) and SEA
> (Daccord; Grubauer confirmed) changed after the write. The moneyline gate
> only checked that a row existed. The totals card and the prop cards had no
> goalie gate.
>
> **Known**, for a game (`models/nhl_goalie_gate.py`), means for both teams:
> ESPN's latest designation is `confirmed`; the game's `nhl_goalie_stats` row
> names the same goalie; and DailyFaceoff, if it has named anyone for that
> team, names the same goalie. DailyFaceoff's status is not required: it is
> a veto on a disagreement. ESPN's "confirmed" follows the morning skate and
> is looser than DailyFaceoff's (10-20: ESPN confirmed Kuemper while
> DailyFaceoff said Likely). Names compare with accents stripped and a small
> first-name alias step (Matt/Matthew, Dan/Daniel); ids decide when both
> sides have one. The gate fails closed: a read that fails means not known.
>
> **Where it holds.** The scorer: both side models decide through
> `_nhl_game_day_reason`, which reads the gate, and `score_game` applies it to
> every NHL model by sport (puckline, and any later kind). The totals card and
> both prop cards drop unknown games before anything is pooled, so an unknown
> game cannot take the one prop bet a game allows. And the last line, at every
> INSERT that can write an NHL pick: `_insert_picks` turns an unknown BET into
> NONE with the reason, and the two prop cards' `publish` drop it.
> `tests/test_nhl_goalie_guards.py` fails on any file that inserts into
> `picks` without the guard and is not on its allowlist. The allowlist is the
> NBA/NFL/WNBA cards, and `tracking/first_signal_repair.py`: it restores a
> BET that already existed (CLAUDE.md §1c), and refusing it would erase a
> pick rather than stop a bet.
>
> **When the side models decide.** No clock. The 16:00Z-18:00Z window is gone.
> Both side models decide at the first scoring run where the matchup is
> known, last night's games are in the logs (`stale_teams`, unchanged), and
> the game has not started. The lower bound is data: a game is known only
> once its game-day goalie row exists (the ~10:06Z write), and the poll
> rewrites rows, never creates them. The 16:00Z window was justified as
> "what the walk-forward decided against". It did not: the original grade
> decided at each game's first stored quote, 95.8% of them the day before
> (median lead about 27 hours). Re-graded with the goalies who actually
> started (as-built artifact, EV ≥ 0.06, −200 floor, best price, the games
> all four timings share): at the 16:00Z game-day quote +5.08% on 1,588 bets
> (bootstrap 95% +0.3..+10.0); at the last pre-game quote +5.21% on 1,633
> (+0.6..+10.0). A confirmed-goalie decision lands between the two.
>
> **`nhl_over_under`'s decision moment moved.** It took a game's first
> qualifying fetch, often the day before puck drop, and its evidence leans on
> those prior-day quotes. It now takes the first qualifying fetch after both
> goalies are confirmed on game day. That regime has not been graded on its
> own.
>
> **The history: `nhl_goalie_designations`** (append-only; migration
> `add_nhl_goalie_designations_2026_10_20.sql`, RLS on, anon locked out). One
> row per (game, team, source) each time the named goalie or the status
> changes: `source` `espn` or `dailyfaceoff`; `status` `confirmed`,
> `expected`, `likely`, `unconfirmed`, `none` (listed with no starter);
> `player_id` resolved the way the 6am write resolves a name;
> `source_player_id`. Written by `data/ingestors/nhl_goalie_designations.py`,
> which also rewrites the game's goalie row when ESPN confirms someone else
> (same row builder as the 6am write: `nhl_stats_ingestor.goalie_row`). Only
> today's games are rewritten, a started game is never touched, and a run on
> unchanged data writes nothing. DailyFaceoff sits behind Cloudflare and has
> not been tested from the worker, so it fails open with one warning.
>
> **When it runs.** Early in every refresh pass (step
> `nhl-goalie-designations`, before any NHL decider; today and tomorrow on
> the hourly passes, today only on the evening ones), after `nhl_stats` in
> the 6am run, and every five minutes from 11:00 to 23:55 ET in the NHL
> goalie window (`scheduler.run_nhl_goalie_window`,
> `scripts/nhl_goalie_window.py`). The window polls today's games; for any
> game that has just become known it runs the NHL prop odds step, the NHL
> game models for exactly those games (`run_scorer(only_games=...)`, the
> pre-game poller's entry point), the totals card and the prop cards, then
> publishes. A matinee confirmed at warmups falls between two hourly passes;
> this is for that. It stands down while a refresh pass or the daily run is
> in progress, and a pass that starts while it is writing waits for it.
> An unchanged slate costs ESPN the listing plus one call a game, a tick.
>
> **Props decide on a fetch taken after the confirmation.** A game whose
> matchup became known after its newest prop fetch owes one more opening
> snapshot (`nhl_prop_odds_ingestor.due`), and the cards will not decide it
> on the older fetch. That is one extra snapshot per such game per night:
> two event calls (featured + alternates). The older "5 credits a game per
> snapshot" below predates the alternates call; `api_call_log` measured the
> pair at 10-11 credits on the quiet evening passes of 2026-10-19 (featured
> 5-6, alternates 5). A saves bet is taken on the confirmed starter only.

> **2026-10-17 (mike, "Build the fix"): ONE NHL GAME NEVER GETS TWO PICKS
> THAT CANNOT BOTH WIN, AND THE TWO SIDE MODELS DECIDE AT THE SAME MOMENT.**
> That day the regulation model had locked "BOS (Regulation)" at 18:26Z the
> day before, ahead of Boston's game at Anaheim that night. The moneyline
> model then took "LAK ML" at 16:22Z on game day, knowing Boston was on a
> back-to-back. Its LA number went from 58.7% to 64.8% once that game was in
> the logs. "LAK ML" was voided at his request. It had happened once before:
> on 2026-10-04 "FLA ML" and "ANA (Regulation)" both lost. Two changes:
> - `nhl_moneyline_regulation` now decides only in the moneyline model's
>   window: 16:00Z-18:00Z on game day, both listed goalies, last night's logs
>   in (superseded 2026-10-20: no clock, both goalies CONFIRMED, above).
>   Every other run writes its rows NONE with the reason. Both models read
>   one gate (`models/scorer._nhl_game_day_reason`). Before this change, every
>   one of its 33 BETs this season was written 10-72 hours before puck drop.
>   Graded on the 120 finished 2026-27 games
>   (`scripts/nhl_regulation_game_day_grade.py`): the game-day decision made
>   7 bets for +1.1 units, against 31 for -4.9 the early one actually made.
>   The 7 are all among the 31 and on the same outcome, at a better average
>   price (+173 against +159). The 24 it would not have made lost 5.8 units.
>   About 120 games: this rules out "clearly worse", nothing more. (Until
>   2026-10-20 a game that started by 16:00Z had no window; with the clock
>   gone, a Europe game is decided once its goalies are confirmed.)
> - Both side models' rows for a game are held back and checked before they
>   are written (`_apply_side_conflicts`). Each pick maps to the endings it
>   wins on. A BET already standing on the game keeps it, and the new pick is
>   written NONE with why. Two such BETs from the same pass are both written
>   NONE: the models disagree and there is no telling which is wrong. A VOID
>   or paused-model BET holds nothing. Moneyline and same-team regulation, or
>   moneyline and the regulation draw, can both win and both stand.

> **2026-10-08: `docs/nhl_clv_ev_assessment.md` is the current grade of every
> NHL model for closing-line value and expected value.** The prop backtest
> figures quoted below before that date are inflated by a shared-name defect
> (#895). The nightly prop limit is four (mike).

> **2026-10-08 (mike): `nhl_over_under` is LIVE, as a rule** (*"This is live
> model, stop asking about paper"*). It is no longer a trained model and no
> longer untrained: it is out of `config.MODELS` and the feature map, and the
> trainer refuses it. On every refresh pass, right after the odds fetch, it
> takes the newest stored fetch that holds Pinnacle's full-game total,
> de-vigs Pinnacle, and bets the bettable book in THAT SAME FETCH with the best
> EV at the same number, if EV is at least 0.01 and the price is -200 or
> better. One bet a game, written once and never re-priced.
> `models/nhl_totals_market.py` (the rule and its evidence),
> `scripts/nhl_totals_card.py` (step `nhl-over-under`). Six seasons at the
> bettable books: 1,276 bets, +60.2 units, +4.72%, EV at Pinnacle's close
> +1.32%. The return is not established (interval -0.6% to +10.1%); closing
> line value is the case for it. Thresholds and the full grid:
> `docs/thresholds.md`.

> **Read `docs/nhl_market_research.md` first (2026-09-20).** The 2026-06-21
> holdout numbers in the table below were produced on season-final inputs. On
> the rebuilt inputs `nhl_moneyline` walks forward at AUC 0.585 and a log loss
> no better than quoting the home-win rate. The six defects that doc lists
> (team ids, the September season label, the goalie lookup, "GSAA", the 3-way
> market key, the missing 2025-26 season) were fixed the same day; the
> sections below marked **(2026-09-20)** describe the pipeline as it is now.

> **THE NHL MODELS ARE LIVE, WITH THE GO-LIVE GATE NOT MET** (mike,
> 2026-10-01: *"this is a live model"*). Raised with the grade below in front
> of him, restated, his call. Do not describe them as held back, do not hold
> their picks back, and do not restore the gate without asking him.
>
> **NHL HAS NO 10-GAME HOLD** (mike, same day, on a proposal to hold picks until
> both teams had played ten games: *"no, this is fucking why we have back testing
> and seasons worth of data frmo out data sources"*). **Backtested the same day,
> and he was right:** over five seasons the live inputs do no worse in the
> early weeks than in the rest of the season, and the alternative built to
> replace them (every team number blended toward last season) graded worse.
> Nothing was switched. `docs/nhl_market_lab.md`, "The early weeks, backtested".
>
> **2026-10-03 (mike): `nhl_moneyline_regulation` decides on its OWN
> probability** (`config.MODELS_ON_OWN_PROBABILITY`). The correction is a
> two-way map and made the three regulation outcomes sum to 1.144; it lifted
> every outcome under 50% by ~6 points. `nhl_moneyline` keeps it. The note
> below is the 10-01 decision this partly reverses.
>
> **THE PROBABILITY CORRECTION STAYS AS IT IS** (mike, same day: underdog
> plus-money bets are wanted). What it does to these two models is measured in
> `docs/nhl_market_lab.md` ("The live artifacts, graded"); that is a record,
> not an open question.
>
> **State at 2026-10-01, three days into 2026-27** (queries and tables:
> `docs/nhl_market_lab.md`; open items: `docs/followups.md`).
> - 11 BETs in `picks` (4 moneyline, 7 regulation). One reached push and
>   Discord: "CAR ML", written 2026-09-22 for 09-29, a loss, -1.0 unit. The
>   other ten clear the scorer and fail the publishers' cut: the scorer decides
>   on the corrected probability, the publishers filter on the model's own.
> - Graded at real 2025-26 prices, neither live artifact made money at any cut
>   (`scripts/nhl_live_artifact_grade.py`).
> - Blind underdogs lost in five of the last six seasons at DraftKings
>   (`scripts/nhl_underdog_grid.py`). The "best price against Pinnacle" grid in
>   the same script is NOT a rule: it compared quotes taken at different
>   moments, and with simultaneous quotes there is nothing
>   (`scripts/nhl_moneyline_market_lab.py`).
> - **`nhl_prop_blocked_shots` is live** (mike, 2026-10-01: *"just build
>   profitable models"*): a Poisson model of a skater's blocked shots priced
>   against DraftKings, unders, EV >= 0.10 on its own probability. Walk-forward
>   on three priced seasons: +6.2% on 2,054 bets, every season positive.
>   `models/nhl_prop_blocked_shots.py`, `scripts/nhl_prop_card.py` (step
>   `nhl-prop-scoring`, right after the prop prices). Settles from
>   `nhl_skater_game_log`; a scratched player is NO_ACTION.
> - **`nhl_prop_saves`, `nhl_prop_shots_on_goal` and `nhl_prop_assists` are
>   live** (mike, 2026-10-01: *"build saves, shots on goal and assists models
>   and we need total goals"*). One engine, a Spec per market
>   (`models/nhl_props.py`); unders only, EV >= 0.10 on the model's own
>   probability, **at the best price among the bettable books** (FanDuel left
>   out), one pick per player per game. Walk-forward on three priced seasons
>   (`scripts/nhl_prop_backtest.py`): saves +7.8% on 1,755 bets, shots on goal
>   +5.7% on 4,707, assists +10.9% on 1,063, every season positive in each.
>   Shots on goal needs the best price: at DraftKings alone it is +3.3% with a
>   flat 2024-25. **Shots on goal bets at most 3 a game**, best EV first, picks
>   already written included (mike, 2026-10-01, after an 11-bet game): +5.4% on
>   4,210 with the limit (`docs/nhl_market_lab.md`). Card: `scripts/nhl_props_card.py`, in the same
>   `nhl-prop-scoring` step. A goalie who does not start is NO_ACTION (the
>   books void it), a relief appearance included. The row is the scorer's
>   shape for a pick decided away from DraftKings: `decision_*` is the book
>   and price bet, the DraftKings columns hold DraftKings' own number at that
>   line or nothing, `line_book` says whose line it is when DraftKings has
>   none, `best_*` carries the deciding book's betslip link. No book in the
>   label.
> - **Total goals: still no model, on purpose.** A fourth round
>   (`scripts/nhl_totals_lab.py`, six seasons, simultaneous quotes) found the
>   book's margin on BOTH sides of the full-game number (every over -4.0%,
>   every under -4.4%), no edge from Pinnacle against DraftKings, and a ceiling
>   of +3% to +5% even for a bettor who knew which way the number would move.
>   `nhl_over_under` stays untrained. The derivative totals (team, alternate,
>   first period) were graded on the stored `odds_api_nhl_totals_history` rows
>   and nothing cleared (`docs/nhl_derivative_totals.md`). They are not
>   registered and not in the pipeline. The buyer has no credit cap; `--apply`
>   had not been run as of 2026-10-03 because this environment had no
>   `ODDS_API_KEY`. (Superseded for the full-game total on 2026-10-08: the
>   Pinnacle rule above is live.)
> - **Player prop prices are collected from 2026-10-01**: an opening and a
>   closing snapshot per game, six markets, ten books
>   (`data/ingestors/nhl_prop_odds_ingestor.py`, refresh-pass step
>   `nhl-prop-odds`, kill switch `RUN_NHL_PROP_ODDS=0`). Measured on the live
>   endpoint: 5 credits a game per snapshot. (Since the alternate-lines call
>   was added, a snapshot is two calls: 10-11 credits a game on 2026-10-19,
>   `api_call_log`.) Four of the six markets now have a model; points and
>   anytime scorer do not.
> - A returning starter is now matched to his own history before his first
>   game of the season (`GoalieBook.player_named`); until 2026-10-01, 28 of 32
>   probable starters carried the league-average line.
> - `nhl_puckline` is still untrained; its stated blocker (no historical
>   lines) ended 2026-09-21. `nhl_over_under` is untrained because four rounds
>   found nothing to train toward (above). It is a rule since 2026-10-08.
> - The month's odds-feed allowance ran out on 2026-09-26 and reset on 10-01
>   (mike: it refreshes every month; nothing to diagnose). No NHL price was
>   stored between 09-26 22:59Z and 10-01 00:02Z, so opening night has no
>   closing line and "CAR ML" was graded against a three-day-old price.

### Inputs as they are now (2026-09-20)

- **Per-game logs**, from the NHL's free stats API (`?isGame=true`), in
  Supabase: `nhl_team_game_log`, `nhl_goalie_game_log`, `nhl_skater_game_log`
  (2017-18 → 2025-26 team and goalie; skaters 2018-19 →). `season` on
  `nhl_skater_game_log` is the ENDING year (2027 is 2026-27). Measured
  2026-10-17: season 2027, `game_type` 2, 4,247 rows from 2026-09-29 through
  2026-10-15.   The shots column is `shots`. The log also has `blocked_shots` and
  `hits`; the Stats board does not chip them. The Stats Players tab sums
  it with `player_window_totals_nhl` (same RPC shape as the other sports).
  The function is SECURITY INVOKER. Until this migration and #962's anon
  SELECT are both applied, the call errors (function not found, or
  permission denied). The app treats those two as an empty average and
  still shows posted lines. Importer:
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
### `nhl_moneyline` REBUILT (mike, 2026-10-13; shipped on his "Yes", 2026-10-15)

`models/nhl_moneyline_anchored.py`, artifact `kind = "anchored_logit"`
(`models/saved/nhl_moneyline_20261013_225002.pkl`, fit on 7,900 priced games
2020-21 → 2025-26). DraftKings' no-vig price is an unpenalised offset; 34
inputs built from `nhl_team_game_log` / `nhl_goalie_game_log` / `games` move
it (form, shots, special teams, goalie, rest / back-to-back / road trip,
rating, goalie workload, home ice, travel). It is NOT fit by
`models.trainer` (`OWN_FIT_PATH` refuses it): refit with
`scripts/nhl_moneyline_anchored_train.py`, grade with
`scripts/nhl_moneyline_anchored_backtest.py` (it must reproduce before a new
artifact goes live). **One decision a game, at the first scoring run where
both starting goalies are confirmed (the NHL goalie gate, top of this file;
no clock since 2026-10-20), with both teams' games of the last two days
already in `nhl_team_game_log`** (they land ~10:05Z; if that ingest is late
the model waits rather than read stale rest and form);
every other run writes NONE with the reason, and it never writes AVOID. EV ≥ 0.06 on its own
probability at the best price, −200 floor; evidence in `docs/thresholds.md`
and `docs/nhl_moneyline_rebuild.md`. Gate standing: 0 settled bets, live by
mike's rule (CLAUDE.md §2, "never propose paper"). The regulation model below
is unchanged.

### Models (2026-09-20: moneyline + regulation RETRAINED on honest inputs; LIVE since 2026-10-01, gate not met — mike; O/U + puckline untrained)

**Retrained 2026-09-20 (mike), train 2018-19 → 2024-25, holdout 2025-26, 1,352 games.** A retrain resets the go-live gate (≥ 50 settled picks, positive flat ROI, calibration ≤ 5%); **mike made both LIVE on 2026-10-01 with the gate not met** (top of this file).

| Model | Holdout 2025-26 | The do-nothing baseline on the same season |
|---|---|---|
| `nhl_moneyline` `20260920_131606` | accuracy 52.9%, AUC 0.558, Brier 0.2477, calibration error 2.82% | always-home 52.1%; Brier ≈ 0.2498 quoting the training home-win rate |
| `nhl_moneyline_regulation` `20260920_133544` | accuracy 41.6%, one-vs-rest AUC 0.550, log loss 1.0772, calibration error 3.95% | always-home-in-regulation 39.5%; log loss ≈ 1.0855 quoting training class rates (computed on all 1,394 games) |

Both are calibrated and both are barely better than quoting base rates. Published closing lines run 0.655-0.674 log loss on the moneyline (`docs/nhl_market_research.md` §5); fixed-parameter walk-forward puts this model near 0.69. **Neither model has shown it knows anything the line does not.** The table below is the 2026-06-21 record, kept for provenance; its numbers came from season-final inputs.


| Model ID | Type | Market | Odds source | Status |
|---|---|---|---|---|
| `nhl_moneyline` | binary XGBoost + Platt | h2h | real DK h2h (bulk feed) | **LIVE** — holdout 2025 acc 60.4% / AUC 0.642 / CalErr 5.09% (6870 train rows); backtest 942 bets 64.2% +22.6% (prob-only synthetic −110 — directional only, NHL favorites are heavily juiced) |
| `nhl_moneyline_regulation` | **3-class** XGBoost (`multi:softprob`) + calibrated | h2h_3way | real DK 3-way (per-event endpoint) | **LIVE** — holdout acc 50.0% / OvR-AUC 0.596 / CalErr 2.55% |
| `nhl_over_under` | **rule** (no artifact): Pinnacle's no-vig price vs the bettable books, same fetch, same number | totals | Pinnacle + the bettable books (one stored fetch) | **LIVE from 2026-10-08** (mike) — EV >= 0.01 on Pinnacle's own number, price -200 or better, one bet a game. `models/nhl_totals_market.py` |
| `nhl_puckline` | binary XGBoost + Platt | spreads (±1.5) | real DK puck line | BLOCKED — same (needs historical spread_home) |

**Trained 2026-06-21 after fixing 4 stacked ingestion bugs that had silently blocked NHL (see session log):** (1) `/schedule` games carry no `gameDate` (it's on the gameWeek day) → 0 games upserted; (2) `/team/summary` returns `teamFullName` not `teamAbbrev` → every team-stat row skipped (all stats null); (3) `/team/advanced` is dead (500) → Corsi now from `/team/realtime` satPct; (4) summary has no `goalDifferential` (derive from goalsFor−goalsAgainst) and xGF% isn't in the free NHL API at all (removed `d_xgf_pct` from the feature list — it was 100% null and dropna would have zeroed the matrix). Backfill: ~8,991 games 2019-2025 + team/goalie season snapshots. Top moneyline features: d_goal_differential (23%), d_goals_per_game, d_goals_against_pg, d_goalie_gsaa, away_win_pct. `nhl_moneyline` CalErr 5.09% is just above the 5% gate — provisional, re-check after 50 live settled picks. Artifacts committed + active in `model_registry`; GitHub Actions scores NHL automatically.

Thresholds (placeholder — tune after 50+ settled picks): ML 55%/5%, regulation 40%/5% (3-way → lower per-side prob), puckline 55%/5%. O/U is the rule: action cut 0.0 / 0.0, EV floor 0.01, price floor -200 (`docs/thresholds.md`).

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
| NHL results (`nhl-results`) | GitHub Actions (step 0b, **before settle**) and every refresh pass | daily 7am, hourly 7am–5pm ET, every 10 min 6–11pm ET | `ingest_nhl_scores_for_date` — trailing-3-day final scores + regulation outcomes into `games` (settlement reads `home_score`; the MLB statsapi fetch in paper_tracker doesn't cover NHL). Then `nhl_period_scores_api.top_up`: finals that have no `nhl_api_score` row, from the same `/v1/score` goals array, at most 40 dates a pass |
| NHL odds (h2h/totals/spreads bulk + per-event 3-way) | GitHub Actions (`step_odds`) | 6am + hourly to 5pm + every 10 min 6pm–11pm | DK lines; 3-way attempted per-event (bulk 422s it), non-fatal when absent |
| NHL team + goalie stats (`nhl_stats`) | GitHub Actions (`step_nhl_stats`) | daily 7am | season-to-date team metrics + probable-starter goalie rows (ESPN `probableStartingGoalie` overlay) |
| NHL totals (`nhl-over-under`) | Railway worker (`step_nhl_over_under`) | 6am (right after the odds step) + every refresh pass (right after `par odds`) | `scripts/nhl_totals_card.py`: every unstarted NHL game, Pinnacle vs the bettable books in the newest fetch; writes at most one `nhl_over_under` BET a game, once, under the model's advisory lock. Logs a diagnostic line every pass (`no_sharp`, `pinnacle_withdrawn`, ...) so an empty card can be told from a broken one |
| NHL scoring (`step_scoring`) | GitHub Actions | 6am + every refresh pass | `run_scorer` NHL branch → picks (incl. `_score_nhl_3way`); `nhl_over_under` is not in it |
| Settlement | Railway worker (`settle`) | every refresh pass and the 6am run | Game lines grade off `games` once `nhl-results` has the final. Props grade in the same `settle_picks` once a final that is still missing its skater or goalie log has a box from `/gamecenter/{id}/boxscore`. The morning `top_up` still writes the full stats-API row; the box insert is `ON CONFLICT DO NOTHING`, so it does not blank that row. 3-way draw is handled in `_compute_result`. |

NHL picks won't generate until the four models are trained and the `.pkl`
artifacts are committed (like MLB/WNBA/UFC) — until then the NHL steps no-op
cleanly (scorer logs "no trained model").
