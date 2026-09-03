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
