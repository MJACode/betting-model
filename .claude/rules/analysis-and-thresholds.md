---
paths:
  - "models/**"
  - "scripts/**"
  - "tracking/threshold_review.py"
  - "tracking/live_calibration.py"
  - "tracking/model_calibration_agent.py"
---

# Analysis and thresholds

> Loaded only when Claude opens a file matching the paths above, so this costs
> nothing on a session that never touches this area. Rules that govern EVERY
> session stay in CLAUDE.md; the measured story behind each one is in
> `docs/rules_evidence.md`. Split out 2026-09-03 (mike: "this project will only
> continue to grow. How can we ensure we don't lose context?").

## THE ANALYSIS PROTOCOL — how a "find an edge" request is worked

(mike, 2026-09-20, after a full day on "explore all NHL markets and craft an
approach to profitable / +EV / CLV winning models" produced a literature review,
a bug hunt and one re-measured moneyline model — and no backtest, no other
market tried, 378,446 freshly loaded skater rows unused, and "there are no
historical lines" said while a free archive of open and close lines sat in the
session's own notes. *"You're supposed to be an analytic data scientist… you keep
missing basic shit."* Evidence: `docs/rules_evidence.md`.)

**Research means experiments against prices. Reading is orientation, and it is
timeboxed.** The deliverable is a RESULTS TABLE, not prose, and it comes BEFORE
any plumbing the work turns up.

1. **THE MARKET GRID FIRST.** One row per market the book offers — sides,
   totals, spreads, regulation / 3-way, periods, team totals, alternates, EVERY
   prop — with four columns filled in: the TARGET (which column settles it),
   the INPUTS we hold, the PRICE SOURCE, and the BASELINE result. A market with
   an empty cell is a to-do, not an omission. Nothing is "out of scope" by
   silence: say why a row is parked, in the table.
2. **A PRICE SOURCE BEFORE A MODEL.** No prices means no profit claim, so
   finding prices is step one, not a footnote: what we store, what the feed
   sells (and its cost), free archives, the prior-season close. **A source found
   in research is an INPUT TO USE TODAY, not a finding to report.** "We have no
   lines" is sayable only after every route in §1b has been tried and named.
3. **THE MARKET IS THE BASELINE.** Every model is scored against the no-vig
   market probability on the same games, and against the dumb baseline (home
   rate, season average, last-N mean). AUC and log loss are diagnostics; the
   RESULT is units won and closing-line value at real prices.
4. **RESULTS IN UNITS, WITH THE FOUR NUMBERS.** Bets, units, ROI with a
   confidence interval, and CLV — on every scored game (the evaluation rule),
   as a threshold NEIGHBOURHOOD not a peak, split early / late, walk-forward by
   season. "No cut clears, here is the grid" is a complete answer.
5. **FEATURES ARE HYPOTHESES, TESTED BY REMOVAL.** Ask what actually drives the
   sport (shot quality, special teams, goalie form, rest and travel, lineup and
   usage) and test each GROUP by ablation. Data that was loaded and not used is
   a finding against the analysis, not a footnote.
6. **PLUMBING IS TIMEBOXED AND SECOND.** Bugs found on the way are logged, and
   fixed first ONLY when they corrupt the experiment. The day ends with the
   results table even if the pipeline is still broken.
7. **A reply to an edge request leads with the grid and the table.** Then the
   approach, then everything else.

## Cuts and evaluation

These govern any change to how a model is CUT or evaluated. THE EVALUATION
RULE itself stays in CLAUDE.md, because analysis is routinely done in SQL
without opening any file here and the rule has to be known first.

- **THE EVALUATION RULE. Any analysis of model performance, thresholds or signal
  timing MUST evaluate every scored pick — `BET`, `AVOID` and dead-zone `NONE`
  alike.** A BET-only sample contains only picks that already cleared the live
  bar, so it is systematically optimistic and cannot see the population a looser
  cut would draw from. `mv_scored_pick_outcomes` grades the whole universe.
  Three coverage traps to check FIRST: `NONE` rows only exist from 2026-05-12;
  they were **deleted ~2026-06-26 → 2026-08-09**; and a game where `abs(edge) >
  MAX_EDGE_CAP` gets **no row at all**. Clean windows: 2026-05-12→06-25 and
  2026-08-09→present. Re-verify by month; never assume.
  Full version: `docs/signal_timing.md`.
- **Validate the grading before moving a cut.** Recompute outcomes from raw
  scores and reconcile against stored settlements first. A sign bug in away-side
  spread grading turned a −20.6% cut into a phantom +15%.
- **Require a plateau, not a peak.** A cell whose eight neighbours flip negative
  one grid step away is noise. Report the neighbourhood, the per-season split,
  the bet count and a CI — and when the grid is negative everywhere, say so and
  retrain instead of shipping the least-bad cut.
- **A time split kills most false positives.** Every situational edge in the
  NCAAF search that looked strong pooled collapsed when split early/late. Make
  the split part of the method, not a follow-up.
- **In-sample is in-sample.** Cuts swept on live picks regress forward. State
  which samples are trustworthy by volume and which are not.
