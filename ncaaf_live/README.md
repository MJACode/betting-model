# NCAAF live (in-play) model

A port of `nfl/live_model` (see its README for the architecture) retargeted at
college football: CFBD play-by-play, the platform's NCAAF tables for finals /
pregame lines / weather, ESPN's college endpoints for live state, The Odds API
`americanfootball_ncaaf` for snapshots. Standalone package on purpose — `nfl/`
has internal `models/` and `scripts/` dirs that shadow the platform's the
moment it lands on `sys.path`.

Status against the NFL build order, honestly:

| # | Phase | Status |
|---|-------|--------|
| 0 | Feed verification | **DONE.** CFBD `/plays` 2015–2025; ESPN college football answers on `sports.core` (the host Railway can reach); The Odds API serves HISTORICAL in-play NCAAF snapshots (probe: 21 mid-game events with live DK totals, measured 10 credits/snapshot). |
| 1 | State corpus | **DONE.** 1.48M leak-checked states, 8,208 games. 23 tests. |
| 2 | Engine (remaining, distribution, pricing) | **Built and trained.** Gate 1 (win probability) **PASS**: Brier 0.115 [0.107, 0.122] vs 0.20. Gate 2 (total shape) **FAIL**: 2.60pp [2.22, 4.19] vs 2.0pp — see below, the fail is tails-and-endgame; the median is calibrated to −0.04pp. |
| 3 | Snapshot harness + kill criteria | Not started. The next step, credit-scoped. |
| 4 | Feeds + worker | Not started (the NFL feed generalizes; league slug swap). |
| 5+ | Paper slate → live | Not started. |

## What the calibration gates established

**Win probability is strongly calibrated** on held-out 2025 (a season no stage
ever saw): Brier 0.115 against a 0.20 gate and a 0.23 base rate — skill 0.50.
CFB is *easier* than the NFL here (blowouts are common), and every derived
moneyline probability is licensed by this.

**The total distribution fails the inherited 2.0pp coverage standard, and the
verdict is honest: 2.60pp with a CI of [2.22, 4.19].** The structure of the
fail matters more than the number:

```
q0.05  -1.07pp      q0.50  -0.04pp      q0.90  +2.60pp
q0.25  -2.24pp      q0.75  +2.33pp      q0.95  +1.87pp

bucket 6 (pregame/Q1)   1.78pp  PASS
bucket 4-5 (mid-game)   ~2.85pp
bucket 0 (final 2 min)  8.84pp
```

The MEDIAN of the total distribution is essentially perfect and early-game
states pass outright. What fails is symmetric tail width plus the final two
minutes. Consequences, per the NFL spec's own logic:

* **Licensed:** moneyline-derived probabilities (gate 1), and main-line total
  pricing in early/mid-game states, where the relevant region of the CDF (the
  median neighbourhood) is calibrated.
* **NOT licensed:** alternate lines, team totals, quarter markets, and
  anything priced off the tails — and ALL pricing inside the final two
  minutes. These were already off by default; the gate makes it a verdict
  rather than a caution.

## The 2025 holdout was consulted three times — recorded, not hidden

1. The first run failed at 4.02pp with ZERO mean bias, which localised the
   problem to distribution *shape*, not drift of the mean.
2. Diagnosis and every fix was tuned on a **2024 pseudo-holdout** (17
   configurations examined there — that count is the multiple-comparisons
   budget this file exists to disclose). The winner: **era drift in shape** —
   at a fixed predicted mean, older seasons' outcome distributions are wider
   than modern ones. Fitting Stage 2 on the two most recent seasons took 2024
   coverage from 4.39pp to 2.76pp, monotone in recency, while five smoothing
   variants moved nothing (4.4–4.5pp each) and every exponential half-life
   underperformed the hard window.
3. The second 2025 run (after the era fix) read 2.73pp; the third and final
   run (after the compose backoff below) reads 2.60pp. Both fails. Any future
   improvement must re-tune on 2024 and treat a further 2025 run as a fourth
   consultation.

## Design decisions recorded (including the failed one)

* **Two-season Stage 2 window + all-history backoff** (`compose`). Windowing
  fixes era drift but thins late-game cells, and the original thin-cell
  backoff — the mu-only pmf pooled ACROSS ALL CLOCK STATES — is structurally
  wrong for a nearly-deterministic endgame. Thin recent cells now fall back to
  the all-history (mu, time) cell (clock conditioning kept, era precision
  sacrificed) before mu-only.
* **Tilt-serve was tried and MEASURED WORSE.** Mixture interpolation between
  mu bins widens the served distribution by up to D²/4 of variance, which
  looked like the tail problem — but exponentially tilting one cell to the
  exact mu scored 3.95pp on 2024 vs the mixture's 2.76pp. The mixture's width
  evidently compensates real within-cell heterogeneity. Kept, with the failed
  idea recorded in `_marginal`'s docstring so it is not re-invented.
* **The score-convention gate caught a real corruption on first contact with
  data.** CFBD `playNumber` is a PER-DRIVE counter; sorting by it scrambles
  games, and the convention detector (expects >90% of scoring plays to change
  their own row) read 82% and refused to build. True order: (driveId,
  playNumber) — 99.0% "post", 98.2–99.8% every season.
* **Platform join by wallclock date, not week.** `games` has no season_type
  and postseason weeks restart at 1, so a week-1 meeting and a bowl rematch
  collide. Each pbp game's own wallclock date picks the platform row.
* **OT states drop from training; OT points stay in targets** (markets settle
  including OT). CFB OT is alternating untimed possessions — the engine
  declines to price in-OT games entirely.

## Where the strongest live model actually is, given all of this

The lane analysis from the pregame work still stands: our one validated NCAAF
edge is the totals disagreement, and the live/halftime totals market inherits
the pregame number's error while adding realised pace. The calibration
verdict narrows the license to the **main total, early/mid-game and at
halftime**, priced off a median-calibrated distribution — and rules out the
derivative lanes until the tail problem is solved (more recent seasons
accruing may solve it by itself: each season of extra modern data both
extends the window and thickens the cells).

The edge question — is any book slow enough to be worth betting — is phase
3's, needs snapshots and credits, and its kill criteria are separate from and
senior to everything above.

## Reproducing

```bash
python -m ncaaf_live.backtest.pull_pbp             # ~165 CFBD calls, free
python -m ncaaf_live.backtest.build_states         # + platform join, prints diagnostics
python -m ncaaf_live.backtest.train_engine --fit   # Stage 1 + walk-forward Stage 2
python -m ncaaf_live.backtest.calibrate --season 2025
python -m ncaaf_live.backtest.tune_stage2          # the 2024 pseudo-holdout harness
python -m pytest ncaaf_live/tests/ -q              # 23 tests
```
