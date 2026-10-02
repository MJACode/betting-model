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

> **THE NHL MODELS ARE LIVE, WITH THE GO-LIVE GATE NOT MET** (mike,
> 2026-10-01: *"this is a live model"*). Raised with the grade below in front
> of him, restated, his call. Do not describe them as paper-only, do not hold
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
>   flat 2024-25. Card: `scripts/nhl_props_card.py`, in the same
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
>   `nhl_over_under` stays untrained. The total-goals markets shaped like the
>   props (team totals, period totals, alternates) have no stored price.
> - **Player prop prices are collected from 2026-10-01**: an opening and a
>   closing snapshot per game, six markets, ten books
>   (`data/ingestors/nhl_prop_odds_ingestor.py`, refresh-pass step
>   `nhl-prop-odds`, kill switch `RUN_NHL_PROP_ODDS=0`). Measured on the live
>   endpoint: 5 credits a game per snapshot. Four of the six markets now have a
>   model; points and anytime scorer do not.
> - A returning starter is now matched to his own history before his first
>   game of the season (`GoalieBook.player_named`); until 2026-10-01, 28 of 32
>   probable starters carried the league-average line.
> - `nhl_puckline` is still untrained; its stated blocker (no historical
>   lines) ended 2026-09-21. `nhl_over_under` is untrained because four rounds
>   found nothing to train toward (above).
> - The month's odds-feed allowance ran out on 2026-09-26 and reset on 10-01
>   (mike: it refreshes every month; nothing to diagnose). No NHL price was
>   stored between 09-26 22:59Z and 10-01 00:02Z, so opening night has no
>   closing line and "CAR ML" was graded against a three-day-old price.

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
