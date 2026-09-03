---
paths:
  - "data/**"
  - "models/**"
  - "tracking/**"
  - "monitoring/**"
---

# Data integrity

> Loaded only when Claude opens a file matching the paths above, so this costs
> nothing on a session that never touches this area. Rules that govern EVERY
> session stay in CLAUDE.md; the measured story behind each one is in
> `docs/rules_evidence.md`. Split out 2026-09-03 (mike: "this project will only
> continue to grow. How can we ensure we don't lose context?").

Every one of these is a way a number can be wrong while looking right.

- **Leakage hides in "latest snapshot".** Every bulk feature loader that takes
  the newest odds row must bound on `snapshot_at <= commence_time` AND exclude
  `in_play`. Without it, 67% of completed 2026 WNBA games were featurized with a
  total that had already drifted toward the final score. Guards must FAIL OPEN
  when a timestamp is missing, so synthetic and SBR historical rows survive.
- **A pick stamped after its own first pitch is not a pre-game pick, and any
  measurement against market state must exclude it.** CLV, line movement and
  opening-signal comparisons all difference the pick's number against a market
  snapshot, which is only meaningful if the pick existed before the market
  closed. Bound on `created_at <= commence_time`, not just on the snapshot side.
  Without it a stale number always reads as a favourable move, so the fabricated
  verdicts are **nearly all positive**.
- **A self-healing backfill that walks "the oldest N un-done items" jams on the
  items it can never do.** Filter the queue by the SAME predicate the worker
  applies, or the head of the queue is permanently occupied and the backfill
  silently never converges.
- **Parse timestamps before comparing them.** These columns are TEXT in mixed
  shapes (`Z` suffix vs `-04:00` offset vs naive); a string comparison silently
  keeps leaked rows.
- **"Today" is the wrong question for a LIVE loop, and it has now cost two
  outages.** A game carries the `game_date` of its FIRST PITCH, so a 10pm ET
  start is still in the fourth inning at 00:30 the next day — under YESTERDAY's
  date. Anything resolving which games to poll, price or score uses
  `config.live_slate_dates()` (today + yesterday in the early window), never
  `today_et()` alone. **Both failures were silent for the same reason: "no
  active games" is also exactly what an empty slate looks like** — so the guard
  is a test, not a log line.
- **Use ET, never UTC, for "today".** `new Date().toISOString().slice(0,10)` is
  tomorrow after 8pm ET. Python has the same trap.
- **A model's PROBABILITY is a separate claim from its point estimate, and
  needs its own gate.** Twelve models publish probabilities 6-16pp above what
  they deliver at the levels actually bet, and it tracks sample size rather than
  sport or market — every live pick is made out of sample. **So a retrain is not
  the fix**; it moves the boundary, not the behaviour. The fix is a
  claimed-to-realised map (`models/probability_calibration.py`,
  `docs/probability_calibration.md`), published but deliberately NOT yet used to
  decide, because every threshold was swept on raw probabilities.
- **Gate the number that gets BET, not the one that is convenient to compute.**
  `_mean_calibration_error` averages bins unweighted and across the whole
  probability range, so a 10pp error in the small band that gets bet is diluted
  by the large well-calibrated band near 0.5. Use `cal_error_actionable`.
- **A stat that is always NULL deletes the training matrix.** One sparse column
  plus `dropna` silently drops most rows. Check population before adding a
  feature.
- **Season-to-date rates are noise early.** Blend toward the prior season by
  games played; a raw average over the first month of a 12-game season is the
  single biggest modelling error available.
