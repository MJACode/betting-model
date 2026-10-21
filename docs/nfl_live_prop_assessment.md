# The live pass-attempt bias does not exist, and the model was a price filter

*Measured 2026-09-21. mike: "I really don't get the live props. When the ev
threshold was tightened there were no picks, when it's slightly loosened you
literally pick the over on pass attempts for every game — this tells me the
model is shit."*

Both halves of that observation are correct, and they have the same cause. This
is the standing assessment CLAUDE.md §1b requires before any decision about the
model's future.

**Reproduce everything here with `scripts/nfl_live_prop_assessment.py`.** It
restores the archive from Supabase, rebuilds the join and prints every table
below. Zero Odds API credits — the quotes are already bought and stored.

---

## 0. The short version

| | |
|---|---|
| What the model asserted | DK's live pass-attempt line sits **2.33 attempts low**; 64.2% go over |
| What it actually is | **−0.12 attempts**, 95% CI (−0.42, +0.18); 2025 went over **45.7%** |
| What it returned per quote | **a constant**, 0.6003 (or 0.642 on the blind arm) |
| What that made the EV cut | a **pure price filter** — "any over better than −130.6" |
| Graded at real prices | **−8.47%** over 3,794 bets; **worse** as the cut tightens |
| Can game state rescue it | significant in-sample (p=0.013), **ties the market out of sample** |

---

## 1. The output was a constant, which is why the card looked like that

`over_prob()` computed `z = bias / sigma` from two module constants and read
neither the line, the accrued total nor the clock:

```
p = Phi(DEPLOY_BIAS / SIGMA) = Phi(1.50 / 5.90) = 0.600344   for every quote
```

Production confirms it. Across all 80 `nfl_live_prop` rows ever written there
are exactly **two** distinct model probabilities, and one market, and one side:

| model_probability | signal | rows | markets | sides |
|---|---|---|---|---|
| 0.6003 | AVOID | 51 | pass attempts only | over only |
| 0.6003 | BET | 16 | pass attempts only | over only |
| 0.6420 | BET | 13 | pass attempts only | over only |

With a constant probability the EV test collapses to arithmetic on the price
alone. At p = 0.6003 the fair price is **−150.2**, so:

| EV cut | bets anything priced better than |
|---|---|
| 0.06 | −130.6 |
| 0.10 | −120.2 |

That is the whole decision rule. Tighten it and no price qualifies; loosen it
and every game does. There was never a per-game opinion to be had.

---

## 2. The bias is not there

Re-derived from the 5,333 archived snapshots (restored from
`nfl_live_prop_snapshots`, checksum-verified) joined to `nfl_player_game_log`
finals. 96.3% of quotes matched a final.

`err = line − final`; **negative means the book posts low**, which is what an
over bettor harvests. Standard errors clustered on the game, because five-minute
snapshots of one game are not independent draws.

| market | book | quotes | units | games | bias | SE naive | SE clustered | 95% CI (clustered) |
|---|---|---|---|---|---|---|---|---|
| **pass attempts** | **DK** | **4,071** | **1,437** | **776** | **−0.12** | 0.091 | 0.153 | **(−0.42, +0.18)** |
| pass completions | DK | 4,032 | 1,449 | 780 | +0.16 | 0.063 | 0.107 | (−0.05, +0.37) |
| receptions | DK | 16,928 | 7,154 | 739 | −0.14 | 0.011 | 0.019 | (−0.17, −0.10) |
| rush attempts | DK | 6,360 | 2,742 | 775 | −0.11 | 0.038 | 0.055 | (−0.22, −0.01) |

By season, pass attempts at DK — no season supports it:

| season | quotes | bias | SE clustered | t | over rate | 95% CI |
|---|---|---|---|---|---|---|
| 2023 | 1,858 | −0.33 | 0.236 | −1.4 | 50.5% | (46.7%, 54.4%) |
| 2024 | 1,703 | +0.12 | 0.247 | +0.5 | 48.2% | (44.3%, 52.1%) |
| 2025 | 510 | −0.16 | 0.264 | −0.6 | 45.7% | (41.6%, 49.8%) |

### Why this is the right number and the old one was not

The reconstruction **reproduces the original's dispersion and contradicts only
its centre** — which is the fingerprint of an offset `actual_final`, not of a
different sample:

- MAE **4.41** here against the **4.72–4.97** originally reported.
- `corr(line, final) = 0.70`, mean line **32.3** against mean final **32.4**.
- Bias flat across the game (−0.66 to +0.26 by wall-clock band), no drift.
- 0.00% of matched rows have a zero final, so no dead joins dragging the mean.

Clustering also inflates every standard error by **1.4–1.8×**, so the original's
confidence was overstated as well. That is secondary: the point estimate itself
is ~0, not −2.33.

**The economic result does not depend on any of this.** Section 3 is a profit
and loss on real posted prices and is model-free.

---

## 3. Graded at real prices it loses, and tightening makes it worse

Every archived DK pass-attempt quote, bet on the over at the posted price, with
the `MIN_PRICE = −140` floor the live rule already applies. 90% CI bootstrapped
by resampling **games**, not quotes.

| arm | bets | units | ROI | 90% CI |
|---|---|---|---|---|
| every over, no filter | 4,071 | −335.1 | −8.23% | (−12.1, −4.4) |
| EV ≥ 0.00 | 4,048 | −330.7 | −8.17% | (−12.0, −4.3) |
| **EV ≥ 0.06 (shipped)** | **3,794** | **−321.4** | **−8.47%** | **(−12.4, −4.6)** |
| EV ≥ 0.10 | 2,916 | −272.5 | −9.34% | (−13.6, −5.1) |

Per season at the shipped cut: **2023 −4.41% / 2024 −10.71% / 2025 −15.29%.**

### Why tightening hurts: adverse selection, measured

The book's price is informative. Regressing the outcome on the de-vigged over
probability gives a slope of **+1.22** (1.0 = perfectly calibrated), and the
buckets track:

| de-vigged over prob | quotes | mean implied | actual over rate |
|---|---|---|---|
| 0.45–0.48 | 1,133 | 0.473 | 0.479 |
| 0.48–0.50 | 1,163 | 0.495 | 0.457 |
| 0.50–0.52 | 551 | 0.510 | 0.510 |
| 0.52–0.55 | 1,082 | 0.528 | 0.539 |

So a price filter that keeps the *cheapest* overs keeps the *least likely* ones:

| | bets | mean de-vigged | actual over rate |
|---|---|---|---|
| kept by EV ≥ 0.06 | 3,794 | 0.496 | **0.485** |
| rejected | 277 | 0.543 | **0.549** |

The model asserted 0.600 on every one of those rows. A constant probability plus
a price filter is an adverse-selection machine, and tightening the cut tightens
the adverse selection.

---

## 4. The market grid — nothing clears anywhere

Every market the archive holds, both books, both sides, blind, at the posted
price. `edge` = actual hit rate − the book's own de-vigged probability.

| market | book | side | quotes | units | ROI | 90% CI | edge |
|---|---|---|---|---|---|---|---|
| pass attempts | DK | over | 4,071 | −335.1 | −8.23% | (−12.1, −4.4) | −1.0 |
| pass attempts | DK | under | 4,071 | −184.7 | −4.54% | (−8.3, −0.7) | +1.0 |
| pass completions | DK | over | 4,032 | −362.1 | −8.98% | (−12.8, −5.0) | −1.5 |
| pass completions | DK | under | 4,032 | −131.7 | −3.27% | (−7.2, +0.6) | +1.5 |
| receptions | DK | over | 16,928 | −1625.5 | −9.60% | (−11.5, −7.7) | −1.8 |
| receptions | DK | under | 16,928 | −474.1 | −2.80% | (−4.6, −1.0) | +1.8 |
| rush attempts | DK | over | 6,360 | −689.1 | −10.83% | (−13.5, −8.1) | −2.5 |
| rush attempts | DK | under | 6,360 | −88.0 | −1.38% | (−4.1, +1.2) | +2.5 |

**The live market leans over exactly as the pre-game one does**
(`docs/nfl_prop_over_lean.md`): at DraftKings the under beats the book's own
de-vigged price by 1.0–2.5pp in all four markets. The shipped model bet the
**over**, which is the wrong side of the only real effect on this page.

It is still not a bet. The hold is ~6.5% and a 1–2.5pp lean does not cover it.
The best cell is rush-attempt unders at **−0.32%**, CI (−3.2, +2.5) — a
confidence interval straddling zero on the most favourable of 16 cells, which is
a peak and not a plateau.

---

## 5. Can game state rescue it? In sample yes, out of sample no

The module's own docstring named a conditional mechanism — late passing volume
arrives in hurry-up, so "a game with no late deficit has no hurry-up to
under-forecast" — and then implemented an unconditional constant. So it was
worth testing properly.

nflverse play-by-play was joined to every quote: score margin for the **passer's
own team**, game seconds remaining, accrued attempts, slack, pace, and the
margin × √time interaction. All 4,071 quotes got a live state.

**In sample the signal is real.** Added to the book's de-vigged price:

- likelihood-ratio test of the state block: **χ² = 16.13, df 6, p = 0.013**
- the deficit term carries the sign the hurry-up story predicts
  (coef +0.043, z = 2.11) and its √time interaction is negative (z = −1.91),
  i.e. the effect concentrates late
- and strikingly, **the book barely prices state at all**: R² of its de-vigged
  price on the six state features is **0.010**

**Out of sample it is nothing.** Trained on 2023–24, tested on 2025:

| | log loss | Brier |
|---|---|---|
| model | 0.6917 | 0.2493 |
| **market** | **0.6917** | **0.2493** |

Identical to four decimal places. Calibration is non-monotone (predicted 0.516 →
actual 0.390), and the only cut that produced bets returned **−18.9% on 18 of
them**. The in-sample block does not survive, which is the ordinary fate of a
p=0.013 result on six features.

One honest caveat: the 2025 hold-out is **501 quotes over 280 games**, which is
thin. This says "not demonstrated", not "impossible". Section 7 says what would
change the answer.

---

## 6. What was changed

`nfl/live_model/models/pass_attempt_bias.py` now **declines to price**:
`MEASURED_BIAS = −0.12`, `MEASURED_BIAS_CI = (−0.42, +0.18)`, `DEPLOY_BIAS =
0.0`, and `over_prob()` returns `None` with reason `no_measured_bias`. The
caller already treats a `None` read as "no opinion, no bet"
(`workers/gameday.py`), and records the reason in `prop_skips`.

**This is not a pause and not a retirement.** Both are mike's call, the settled
record is untouched (CLAUDE.md §1c), and the model is not removed from any
surface. It simply stops asserting a number the data contradicts. Restoring the
old behaviour is one constant.

Two bugs were found in passing and are fixed:

- **`bias` and `sigma` were bound as default ARGUMENT VALUES**, captured at
  import. Rebinding `DEPLOY_BIAS` — in a test, a replay or a hotfix — changed
  nothing. They are now read at call time.
- **`MIN_SLACK` has never fired in production**: `workers/gameday.py` calls
  `over_prob(q.line, None, ...)`, so the accrued gate is always skipped. Left in
  place (the replay harness does pass it) but now documented as such.

The guard that would have caught all of this is
`test_a_deployed_bias_must_sit_inside_its_measured_interval`: **a deployed bias
must lie inside its own measured confidence interval.** Both 1.50 and 2.33 sit
outside (−0.42, +0.18). A "haircut" below a wrong number is still a wrong
number.

---

## 7. What would change the answer

Stated so this is a standing assessment and not a verdict.

1. **A real opening line.** Everything here grades against the book's own live
   number. The repo's pre-game work found its edge in *cross-book disagreement*
   (`docs/nfl_prop_over_lean.md`), not in beating one book's centring. The
   archive holds DK and FD only, and FD's coverage is thin (568 pass-attempt
   quotes). **Pulling a third live book is the single highest-value next step**,
   because it converts this from "beat DK" — which §5 says we cannot — into the
   cross-book construction that already works pre-game.
2. **More 2025–26 hold-out.** 501 quotes is thin, and the state signal is the
   one live hypothesis. Re-run §5 once another season has accrued.
3. **The under side, with a real price.** §4 says the lean is on the under and
   that the vig eats it at one book. At the best of three books it might not.
   That is the same measurement as (1).

What is **not** worth redoing: the flow model (it ties the book on MAE and the
repo has been down that road twice), and any further tuning of `EV_THRESHOLDS`,
which is the dial that produced this complaint and cannot fix a constant.

---

## 8. Production follow-up (2026-09-22) — publish backstop, model stays live

Ledger confirmation (Supabase `picks`, `model_id=nfl_live_prop`, queried 2026-09-22).
Dual-arm worker (pre-#811) evaluated **priced** then **blind** on every OVER:

| raw `p` | `p_cal` | n | BET | AVOID | W–L | kelly u (priced W/L) | arm |
|---|---|---|---|---|---|---|---|
| 0.600344 | ≈0.6003 | 35 | 12 | 23 | 2–3 (+7 NO_ACTION) | −6.80 on settled | priced |
| 0.600344 | 0.5355 | 32 | 4 | 28 | 2–2 | 0.00 | priced |
| **0.642000** | **0.5792** | **13** | **13** | **0** | **2–11** | **−46.30** | **blind** |
| **Pass OVER W+L** | | | **22** | | **6–16** | **−53.10** | |
| rush under (~0.50) | | 1 | 1 | 0 | 0–1 | −5.00 | #811+ |

Why blind is all-BET: higher constant clears EV on nearly every quote above −140;
priced often AVOIDs first, then blind BETs into the adverse-selected remainder.

Also measured: `live_pick_features` n=0 for this model; all BET rows have null
`game_time` / `run_time` / `clv_pct` (quality `clv_degradation` SKIPPED).

**Kill switches (default safe):**

- `DEPLOY_BIAS = 0.0` — module refuses with `no_measured_bias`
- `NFL_LIVE_ALLOW_PASS_ATTEMPT_BIAS` unset/`0` — even a non-zero `DEPLOY_BIAS`
  returns `pass_attempt_overs_disabled` on the module-constant path
- `pick_writer.refuse_publish_reason` — refuses any decision whose market is not
  `player_rush_attempts`, side is not `under`, or raw prob fingerprints
  `CONSTANT_OVER_PROBS` (0.600344, 0.642)

**Not done:** `PAUSED_MODELS` — product owner (Michael, 2026-09-22) requires the
model stay live; pass overs are killed at selection/publish, not by pausing.
