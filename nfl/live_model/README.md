# NFL live (in-play) model

Status against the build spec's build order, honestly:

| # | Phase | Status |
|---|-------|--------|
| 1 | Backtest harness + snapshot pull | **Code complete, verified end to end on synthetic snapshots. NOT RUN on real data: needs an Odds API key and credits.** |
| 2 | Engine v1 (remaining, distribution, pricing) | **Built and trained on 2015-2024. Both calibration gates PASS on fully held out 2025.** |
| 3 | Props engine | Built. **Calibration gate run: ALL 7 GATED MARKETS FAIL. Not bettable as built.** |
| 4 | Feeds + worker | Built, ported to `sports.core` (site.api is blocked from Railway), self-checking. Shapes still unverified against a live payload. |
| 5 | Paper trade a slate | Not started. Blocked on 1 and 4. |
| 6 | Live at minimum size | Not started. |
| 7 | Evaluate a push feed | Not started, and per the spec must not be considered before 6. |

## What was actually established

**The engine is calibrated.** This is the one verdict that needed no odds data
at all, which makes it the first honest read available on the whole idea. On
2025, a season neither stage ever saw:

```
gate 1  win probability Brier   0.1654  [0.1496, 0.1798]   PASS vs 0.20
gate 2  total quantile coverage 1.26pp  [1.07, 4.95]       PASS vs 2.0pp
```

Intervals are a cluster bootstrap over **games**, not states: a game
contributes a dozen correlated rows, so a naive standard error understates the
noise badly. Gate 2 passes on the point estimate but its interval reaches
4.95pp, so it passes without margin to spare. Reliability is good at the
extremes and noisier in the middle (the 0.2-0.3 bucket runs +11.7pp), which is
worth rechecking on more seasons before anyone leans on mid range prices.

**Nothing about edge has been established.** Calibration says the engine
describes football correctly. It says nothing about whether any book is slow
enough to be worth betting. That is phase 1's question and it is unanswered.

**Props do NOT calibrate.** `calibrate_props.py` runs the same two gates on the
prop engine, on the same held-out season, for zero credits. Every gated market
fails:

```
market                    bias      worst coverage (gate 3pp)
player_pass_yds          +12.7%      9.12pp
player_pass_attempts      +5.6%     16.62pp
player_pass_completions  +17.3%     13.85pp
player_rush_yds          +15.5%     11.10pp
player_rush_attempts     +12.8%     24.32pp
player_reception_yds     +45.6%     14.99pp
player_receptions        +49.4%     11.02pp
```

Two real bugs were found and fixed along the way (a usage denominator counting
GAME plays instead of TEAM plays, and a units mismatch where a share of all
snaps was multiplied by the carry count, applying the run-pass split twice).
Both roughly halved the error and neither was visible to the sixteen unit tests,
because both scale everything by a constant and leave the game-script response
looking correct. That is the argument for this gate existing.

What remains is structural: every market over-projects and every distribution
is too narrow. That is the opportunity model, not a constant to tune, and
further tuning against the gate would be fitting to it. **Props stay off until
the opportunity model is rebuilt**, and the ~23k credits of prop snapshots
should not be spent until they pass.

## Two bugs worth knowing about

Both were silent, and either one alone would have invalidated every backtest
number the project would ever produce.

**1. 15% of play timestamps were being discarded.** nflverse mixes
`...T02:08:57Z` and `...T02:10:13.383Z` in one column. pandas infers a single
format from the first non-null value, so with a whole-second value first, every
fractional-second timestamp became `NaT`, got forward filled from the previous
play, and whole stretches of a game collapsed onto one instant. Concretely: it
placed early third quarter plays *before* a halftime odds snapshot, which is
look-ahead bias in the single most valuable lane the model has. Fixed with
`format="ISO8601"` and pinned by `test_backtest.py`.

**2. The first Stage 2 design could not represent late game football.** With two
minutes left a team scores exactly zero more points **77.5%** of the time; with
a full half left that atom is 2.5%. An additive residual distribution shifted
onto a mean cannot span that, and it failed coverage at 29pp in the final two
minutes while passing at under 2pp in the first half. Rebuilt as a distribution
conditioned on the predicted mean, storing the empirical pmf of actual remaining
points, which cannot place mass below zero and reproduces the atom exactly.

A third thing worth recording is not a bug but a measurement error I made: the
first coverage numbers used a midpoint PIT, which is not uniform under a
discrete distribution and manufactured an apparent late game failure. The
randomised PIT is the correct test and is what the gate now reports. The
midpoint figure is printed alongside it so the size of that artifact stays
visible.

## Credits: not a constraint

An earlier version of this document called the snapshot pull unaffordable. That
was wrong, and it came from trusting a stale comment in `data_ingest/odds_api.py`
that referenced a 20k quota instead of checking the live number. The actual
position, from the platform's own quota telemetry:

```
4,481,286 of 5,000,000 credits remaining (89.6%), burning ~2,200/day
```

The full 2023-2025 pull at 322,560 credits is **7.2% of remaining**. Nothing is
blocked. The scoping below is still worth having, because a cheaper answer to
the same question is better than an expensive one, but it is an efficiency
choice and not a constraint:

```
window     markets                    snapshots   credits
game       spec scope (4 markets)         8,064   322,560
halftime   spec scope (4 markets)         1,152    46,080
halftime   totals_h2, spreads_h2 only     1,152    23,040
```

Halftime is where the highest value lane lives and where the market is open with
no plays being run, so the puller **defaults to the halftime window**. Two
seasons of the halftime plus 2H-only scope is roughly 15,400 credits, which is
what it costs to answer the spec's kill criterion for the best lane. Widening to
the full game window is affordable whenever the narrow answer justifies it.

```bash
python -m live_model.backtest.pull_snaps --seasons 2023 2024 \
    --window halftime --markets totals_h2 spreads_h2 --dry-run
```

## The host problem, and why the feed check is automatic

`site.api.espn.com` has returned **HTTP 403 to this project's Railway worker
every day since early August**. The platform's own health probe records it:

```
2026-08-28  espn_wnba_api  site.api.espn.com HTTP 403 ... sports.core fallback OK
```

The live model runs on that worker, and the first version of this feed used
site.api for both the scoreboard and the summary, so it would never have
returned a single state in production. The feed now tries
`sports.core.api.espn.com` FIRST and falls back to site.api, which is the
reverse of the order the platform's WNBA ingestor uses: that one was written
while site.api still worked, this one was written after it stopped.

The assumption checks are no longer a script somebody remembers to run. The
worker validates the feed's shape on its first real payload each gameday
(`check_feed_assumptions`, shared with `verify_espn.py` so the two cannot
disagree) and alerts on a break, on a host switch, and when both hosts are
down. A one-time manual blessing goes stale the moment it passes, and the
failure it is meant to catch is silent: a payload that looks plausible with one
field renamed prices every game off a default.

## Before any of this touches money

1. **Pull snapshots and run the harness.** The kill criteria in
   `harness.kill_verdict` are encoded as code, so they cannot be quietly
   relitigated by looking at the numbers first and choosing a rule afterwards.
   A lane without positive pseudo-CLV in two seasons is cut.
2. **Run `python -m live_model.verify_espn` during a live game** as a belt to
   the worker's braces. It checks both hosts and runs the same predicate.
3. **Paper trade a full slate** with the worker writing decisions and alerting
   nothing.

## Layout

```
live_model/
  config.py            every tunable, including the credit caps
  state.py             GameState/PlayerState and BOTH builders
  feeds/espn.py        live state, host selection, defensively parsed
  feeds/espn_core.py   sports.core parser (the worker's primary host)
  feeds/odds_live.py   metered in-play odds
  engine/remaining.py  Stage 1: expected remaining points
  engine/distribution.py Stage 2: the joint final-score distribution
  engine/pricing.py    every game market, derived from that one object
  engine/props.py      per player remaining-stat distributions
  executor.py          guards, sizing, and the decision trail
  backtest/pull_pbp.py     nflverse parquets (free)
  backtest/states.py       pbp to state series
  backtest/train_engine.py walk-forward fit of both stages
  backtest/calibrate.py    the two gates
  backtest/player_states.py    pbp to player state series
  backtest/calibrate_props.py  the prop gate
  backtest/pull_snaps.py   credit-budgeted in-play snapshots
  backtest/harness.py      replay and the kill criteria
  workers/gameday.py   the always-on worker
  verify_espn.py       the live-feed spike
  migrations/          Supabase tables and the picks columns
```

## Reproducing the engine from scratch

```bash
python -m live_model.backtest.pull_pbp            # free, ~220MB
python -c "import sys;sys.path.insert(0,'.');\
from live_model.backtest.states import load_pbp,build_states;\
from live_model.config import ARTIFACT_DIR;\
build_states(load_pbp(range(2015,2026))).to_parquet(ARTIFACT_DIR/'states_all.parquet')"
python -m live_model.backtest.train_engine --fit   # ~15 min, 7 walk-forward folds
python -m live_model.backtest.calibrate --season 2025
python -m live_model.backtest.calibrate_props --season 2025
python -m pytest live_model/tests/ -q              # 105 tests
```

## Design decisions that are load bearing

- **The live main line is truth.** `pricing.anchor_to_market` recalibrates the
  distribution onto the devigged market moneyline and total before any
  derivative is priced. Without it, every derivative edge is contaminated by our
  disagreement with the sharpest number on the board, which is not a lag edge,
  it is a wrong model with extra steps.
- **Stage 2 is fitted on walk-forward out-of-sample Stage 1 predictions.** On
  in-sample predictions the spread of actual-given-predicted is too tight, so
  every derived market looks more certain than it is, so every derivative looks
  like it has an edge. That single mistake would make the whole system appear
  profitable and be worthless.
- **Alignment is one directional.** A snapshot is priced off the latest state at
  or *before* it, never the nearest state in either direction.
- **Quarter markets are approximate and off by default.** The engine models
  points remaining to the end of the game, not points inside one quarter.
  `price_quarter` returns `approx=True` and quarter markets are excluded from
  the bettable lanes until someone validates them.
- **Every pass is recorded, not just every bet.** Without the passes there is no
  way to tell later whether a lane produced no bets because there was no edge or
  because a guard was silently eating every candidate.
- **Overtime is declined, not guessed.** It is sudden-death shaped and pricing
  it with a regulation distribution would be wrong rather than approximate.

## Known limits

- The backtest granularity is 5 minutes. Any edge living inside that window is
  invisible, and any edge that survives it is easier to capture in a replay than
  live, where the market suspends at the snap. Reported ROI is an upper bound.
- 78 of 3,028 games have a wall clock that still runs backwards after the
  day-offset repair. The harness drops them and says so.
- The prop engine models opportunity, not who gets hot. Efficiency is shrunk
  hard toward positional priors on purpose.
- Retail books limit winning live bettors quickly. Per book fill quality needs
  tracking from the first real bet.
