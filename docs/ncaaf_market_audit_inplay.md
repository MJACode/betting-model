# NCAAF in play: the NCAAB game-state model ported to football, measured at DraftKings' in-play prices

> Part of the 2026-11-10 NCAAF market audit (`docs/ncaaf_market_audit.md`). Written by a background
> study in that session. Its scripts are in `scripts/ncaaf_search/audit_2026_11/inplay/`; the output
> files it names are in the audit's work folder (`paths.py`), outside the repo.

Written 2026-11-10. Everything here was computed from the local extracts; nothing was written to a database,
nothing in the repo was edited, and no paid call was made. Results are in units: one unit to win, risk capped
at three. Scripts and their printed output are listed at the end; every table below is built from the files
those scripts wrote.

## 1. The answer

**No. A market-anchored game-state model does not beat DraftKings' in-play NCAAF totals or moneylines on the
stored data. No rule clears the bars under the eligibility rule as asked.**

| Rule | Test A (fit 2025, test 2026), every cut, as asked | Clears every bar? |
|---|---|---|
| Total, first half | -12.6% to -8.4% on 437 to 473 bets | No: negative in test A at every cut |
| Total, second half | -6.7% to -1.8% on 458 to 460 bets | No: negative in test A at every cut |
| Moneyline, first half | -7.3% to +6.2% on 409 to 423 bets | No: no cut is positive in A and in both halves of 2025 |
| Moneyline, second half | -7.7% to -3.3% on 333 to 344 bets | No: negative in test A at every cut |

The bars: at least 100 bets in test A; positive in test A and in both directions of test B; and an interval
whose lower bound is above zero, or a return above the placebo's 95th percentile. Cells clearing all of them,
as asked: **none**. Section 5 has every cell.

Three things a reader should know before the tables.

1. **The hypothesis was half right.** Anchoring on the pre-game line does make the model's total more
   informative than the two-stage engine's was (calibration slope 0.135 in `docs/sports/ncaaf.md`): on 2026
   second-half totals the slope of the result on this model's probability is 0.119
   as asked and 0.268 under the stricter eligibility, and
   0.310 and 0.397
   in the two halves of 2025. A calibrated model reads 1.0. In the first half of 2026 it is
   -0.068. So most of every edge the model claims on a total is not there,
   and what is left does not cover the price: second-half totals in 2026 return -6.7% to -1.8%, which is better than
   betting the same side blind (-8.4% on the over) and better than
   the placebo (mean -8.1%), and still a loss.
2. **The moneyline looks better only under a rule that peeks.** I added a stricter eligibility ("wait and
   confirm", section 3) before grading anything, because our 2026 score log trails DraftKings by a median 75
   seconds. Under it the 2026 moneylines are positive at every cut (+0.6% to +16.5% first half,
   +5.9% to +13.0% second half) and two single cells meet every bar (Moneyline, first half at 0.08; Moneyline, second half at 0.20). That rule
   conditions each bet on nothing being scored in the next four minutes. Re-run with no look-ahead at all
   ("no look-ahead", section 3, 2026 only) the same two cells are +5.5% on 388 bets (interval -8.1% .. +19.0%, placebo 95th +7.5%) and
   +4.5% on 237 bets (interval -9.2% .. +23.2%, placebo 95th +6.4%): inside what the placebo produces. In all 30 moneyline cells of test A (three
   eligibility rules) the early half of the window returns less than the late half, and it loses in 26 of them.
3. **The cut barely selects under a first-crossing rule.** With a new DraftKings quote about once a minute
   (116,963 total quotes on 620 games in 2026), "the first quote
   that clears the cut" is found in almost every game: in test A 99.6% of
   games bet a second-half total at EV 0.20 and 90.7% bet a first-half
   moneyline. The 2026 feed holds 77.9 eligible quotes per game and rule against
   14.8 in the 2025 replay, so the same cut is a different rule in tests A and B.

The "best few a night" variant (section 8) returns +12.8% on 109 bets in test A
(interval -9.6% .. +34.2%) and -1.8% and +2.9%
in the two halves of 2025. Positive in A, flat in B, interval across zero: not a pass.

## 2. The data actually used

| What | Count | Source |
|---|---|---|
| 2025 play-by-play | 293,383 plays, 1,659 games | `ncaaf_plays.parquet` |
| dropped: a negative drive id, so play order cannot be known | 14 games | |
| matched to a row of the games table (two team names, within two days) | 933 of 1,645 | the rest are games the games table does not hold |
| play-by-play ends on the stored final | 888 | |
| clean: ends on the final and every score step is 1, 2, 3, 6, 7 or 8 | 829 | a step of any other size is a hole in the plays |
| clean with a pre-game spread and total: the training games | 815 (397 weeks 1-7, 418 weeks 8+ and postseason) | |
| training states, one per 30 seconds of regulation clock | 95,345 (46,441 and 48,904) | 117 a game |
| prior of the training games | DraftKings' last pre-kick row 652, CFBD's DraftKings close 93, CFBD's Bovada close 70 | |
| 2026 logged game states | 23,535 on 496 games, 2026-09-19 16:50 UTC to 2026-11-08 07:04 UTC | `ncaaf_live_states.parquet` |
| 2026 logged score changes | 6,470, of which 147 are a score going down (120 games) | a correction or a feed error; not separated |
| DraftKings in-play quotes kept, 2025 replay | 49,050 (28,273 totals on 732 games, 20,777 moneylines on 683) | 57,979 rows less 8,929 exact duplicates |
| DraftKings in-play quotes kept, 2026 live | 200,663 (116,963 totals on 620 games, 83,700 moneylines on 570) | 211,472 rows less the 10,809 of 2026-08-29 that carry our clock, not the book's |
| 2026 games with a quote but before the state log starts (2026-09-19) | 145 games, 38,446 quotes: unusable | 475 games remain, all with logged states |
| 2025 replay games with a clean play-by-play game | 637 of 736 | |
| games graded | test A 473 on 32 slate dates; B1 324 on 57; B2 273 on 27 | |

Finals: a 2025 odds row with no score of its own takes its twin's (the same two teams within a day): 561 own,
167 from a twin, 8 with none. All 2026 rows carry their own. The prior of the graded games is DraftKings' last
pre-kick row on all 473 games of 2026 and on 468 of the 597 of 2025 (CFBD's DraftKings close on 68, CFBD's
Bovada close on 61). Pinnacle's pre-kick close is stored for 1,222 of the 1,377 games with a quote or a state;
where both exist DraftKings and Pinnacle differ by a mean 0.625 points on the spread and 0.727 on the total, and
are within a point on both on 76.6% of games. The model uses DraftKings' number.

There are no in-play spreads in the store, so the market that carried most of the NCAAB result cannot be tested.

**What was dropped, and why.** Counts are quotes unless the row says games, and each drop is taken from what
the rows above it left. The feed-error rules found no bad price and no impossible total; the only quotes they
removed are a total at or below the points already on the board and totals priced beyond +/-250 on a side.

| Step | 2025 replay | 2026 live |
|---|---|---|
| quotes kept (section above) | 49,050 | 200,663 |
| games those quotes are on | 736 | 620 |
| games with no final or no pre-game line | 11 | 0 |
| dropped: no final or no pre-game line | 574 | 0 |
| dropped: no state known on both sides of the stamp | 10,545 | 42,474 |
| ... of which on games with no state source at all | 6,677 | 38,446 |
| dropped: feed error: price missing or inside +/-100 | 0 | 0 |
| dropped: feed error: implied sum outside 1.00-1.25 | 0 | 0 |
| dropped: feed error: total outside 5-150 | 0 | 0 |
| dropped: feed error: total at or below points on the board | 56 | 11 |
| dropped: total with a side priced beyond +/-250 | 1,330 | 2,832 |
| dropped: not in a phase (last 5:00, overtime) | 2,060 | 6,701 |
| dropped: a score became known in the 60 s before the stamp | 1,511 | 9,897 |
| dropped: a score became known between stamp and fetch | 957 | 1,578 |
| **eligible, as asked** | 32,034 | 137,176 |
| wait and confirm drops: a score becomes known within 240 s after the stamp (or its bracket is open) | 5,593 | 25,632 |
| wait and confirm drops: older than 90 s when received, not halftime | 820 | 53 |
| **eligible, wait and confirm** | 25,621 | 111,491 |

Eligible quotes and games by rule:

| Test | Eligibility | Total, first half | Total, second half | Moneyline, first half | Moneyline, second half |
|---|---|---|---|---|---|
| A: fit 2025, test 2026 | as asked | 40,287 quotes, 473 games | 36,830 quotes, 460 games | 34,910 quotes, 451 games | 25,149 quotes, 377 games |
| A: fit 2025, test 2026 | wait and confirm | 31,996 quotes, 473 games | 30,533 quotes, 460 games | 27,832 quotes, 451 games | 21,130 quotes, 377 games |
| B1: fit 2025 weeks 1-7, test weeks 8+ | as asked | 5,020 quotes, 309 games | 5,348 quotes, 322 games | 4,608 quotes, 303 games | 3,924 quotes, 287 games |
| B1: fit 2025 weeks 1-7, test weeks 8+ | wait and confirm | 3,972 quotes, 309 games | 4,491 quotes, 321 games | 3,641 quotes, 303 games | 3,324 quotes, 283 games |
| B2: fit 2025 weeks 8+, test weeks 1-7 | as asked | 3,709 quotes, 254 games | 4,227 quotes, 269 games | 2,777 quotes, 220 games | 2,421 quotes, 196 games |
| B2: fit 2025 weeks 8+, test weeks 1-7 | wait and confirm | 2,763 quotes, 250 games | 3,372 quotes, 268 games | 2,082 quotes, 214 games | 1,976 quotes, 191 games |
| A: fit 2025, test 2026 | no look-ahead | 26,539 quotes, 473 games | 25,407 quotes, 460 games | 23,066 quotes, 451 games | 17,353 quotes, 376 games |

Two measurements made on the data before any grade, both of which shape the rules in section 3:

- **DraftKings is ahead of our 2026 score log.** For each logged score change I took DraftKings' nearest total
  move of 2.5 points or more within five minutes either side (3,995 matched). The log shows the score a median
  75 seconds AFTER the book moved; 75th percentile 120 s, 90th 182 s, 95th 221 s.
- **The 2025 play wallclocks are not the time of the play.** They are a last-edited stamp: 1.8% are a whole
  day off and 7.9% are missing or out of play order. A score's true time is only known to lie between the previous in-order
  wallclock and the wallclock the score is first seen at: median 44 seconds apart, 75th percentile 81 s, 90th
  217 s, 95th 290 s.

## 3. Method, as fixed before grading

The definitions are the docstring at the top of `grid.py`. In short:

- **Model.** What is still to come, the home margin and the total, is Normal with mean X b and standard
  deviation sqrt(s0 + s1 f + s2 f^2), f the share of the 3,600 seconds of regulation left. Weighted least
  squares, three passes, weight 1 / variance, on **one state per 30 seconds of regulation game clock**.
  Margin on: f x prior margin, f, current margin x f. Total on: f x prior total, f^2 x prior total, f, f^2,
  (points so far minus (1 - f) x prior total) x f, |margin| x f, and a late-and-close term. NCAAB's two bonus
  terms are dropped. No possession, down, distance or field position: the 2026 log carries possession on 58%
  of rows and field position on 41%.
- **Rules.** Total first half; total second half (halftime to 5:00 left); moneyline first half; moneyline second
  half. DraftKings only. One decision per game and rule: the first eligible quote, in the order received,
  whose better side has EV >= the cut. Cuts 0.02, 0.05, 0.08, 0.12, 0.20. No moneyline side shorter than -200.
- **State at a quote.** The quote's stamp is the book's own (2025 the `lu=` value; 2026 the stored
  last-update). 2025: the last play, in order, whose wallclock is in order and at or before the stamp. 2026: the
  last logged state at or before the stamp, the clock read between it and the next logged state.
- **Eligible, as asked.** A state before and after the stamp no more than 30 minutes apart; not a feed error;
  no score became known in the 60 seconds before the stamp; none between the stamp and when we received the
  quote. The 30-minute bound and the last condition (the repo's own freshness rule in `docs/live_betting.md`)
  are mine; the rest is the rule as it was given to me.
- **Eligible, wait and confirm** (added before grading, because of the 75-second lead above). As asked, plus:
  no score becomes known in the 240 seconds after the stamp; in 2025 no score whose time bracket is open at the
  stamp; and the quote no older than 90 seconds when received unless at halftime. Graded at the quote's own
  price, which a loop that waited four minutes would no longer get.
- **Eligible, no look-ahead** (added AFTER the first grid, test A only, in `variants.py`). As asked, plus: no
  score known in the 240 seconds before the stamp, and no jump by DraftKings in those 240 seconds (its total
  up 2.0 or more, or its no-vig moneyline probability moving 0.08 or more, between consecutive quotes). It
  asks the wait-and-confirm question using only the past. The 2025 replay has one snapshot every five minutes,
  so it cannot be run there.
- **Tests.** A: fit on all of 2025, test on 2026. B1: fit on 2025 weeks 1-7, test on weeks 8+ and the
  postseason. B2: the reverse. No test state was in its fit.
- **Grade.** Risk = min(1 / (decimal - 1), 3) to win risk x (decimal - 1); return = units / units risked; 95%
  interval from 2,000 resamples of slate dates; early and late half of each window split at the median slate
  date of its games; blind = each side at every game's first eligible quote.
- **Placebo, 200 runs.** Each game takes another game's model opinion at the same share of the game left
  (bands of 0.02, nearest within 0.04): the donor's model probability minus the donor's own no-vig market
  probability, added to this game's no-vig probability; then the same rule and cuts. A raw swap of probabilities
  would be meaningless on a moneyline, where the favourite differs by game; on a total the two are the same.

## 4. Model fit

Fit on all of 2025 (test A): margin b = [1.0545, 0.6496, -0.2198] on (f x prior margin, f, margin x f), variance
6.868 + 219.124 f + 13.89 f^2. Total b = [0.7869, 0.1692, 23.0055, -18.4836, 0.1978, -0.416, 4.1109] on
(f x prior total, f^2 x prior total, f, f^2, pace x f, |margin| x f, late-and-close), variance
12.606 + 157.592 f + 70.126 f^2. 95,345 states.

Out of sample, by share of regulation left. Mean error is the final minus the model's mean; the spread ratio is
the standard deviation of the standardised error (1.0 = the model's width is right).

**B1, fit on weeks 1-7, read on weeks 8+ and the postseason (418 games):**

| Target | Share of regulation left | States | Mean error (final - model), points | Realised sd | Model sd | Spread ratio | Within 1 sd |
|---|---|---|---|---|---|---|---|
| margin | (-0.001, 0.1] | 4,598 | -0.324 | 4.37 | 4.53 | 0.942 | 0.678 |
| margin | (0.1, 0.25] | 7,524 | -0.447 | 6.69 | 6.89 | 0.965 | 0.678 |
| margin | (0.25, 0.5] | 12,540 | -0.186 | 9.46 | 9.68 | 0.972 | 0.675 |
| margin | (0.5, 0.75] | 12,540 | -0.112 | 12.09 | 12.44 | 0.971 | 0.69 |
| margin | (0.75, 1.0] | 11,702 | -0.406 | 14.18 | 14.72 | 0.963 | 0.684 |
| total | (-0.001, 0.1] | 4,598 | +0.176 | 4.52 | 4.71 | 0.943 | 0.827 |
| total | (0.1, 0.25] | 7,524 | +0.383 | 6.60 | 6.53 | 1.007 | 0.659 |
| total | (0.25, 0.5] | 12,540 | -0.462 | 9.22 | 8.97 | 1.027 | 0.646 |
| total | (0.5, 0.75] | 12,540 | +0.328 | 11.97 | 11.61 | 1.029 | 0.652 |
| total | (0.75, 1.0] | 11,702 | -0.431 | 14.64 | 13.96 | 1.048 | 0.64 |

**B2, fit on weeks 8+, read on weeks 1-7 (397 games):**

| Target | Share of regulation left | States | Mean error (final - model), points | Realised sd | Model sd | Spread ratio | Within 1 sd |
|---|---|---|---|---|---|---|---|
| margin | (-0.001, 0.1] | 4,367 | -0.357 | 4.42 | 4.24 | 1.012 | 0.706 |
| margin | (0.1, 0.25] | 7,146 | -0.460 | 7.11 | 6.68 | 1.059 | 0.663 |
| margin | (0.25, 0.5] | 11,910 | -0.513 | 9.61 | 9.43 | 1.019 | 0.667 |
| margin | (0.5, 0.75] | 11,910 | +0.119 | 12.52 | 12.04 | 1.038 | 0.68 |
| margin | (0.75, 1.0] | 11,108 | +0.257 | 14.72 | 14.13 | 1.041 | 0.699 |
| total | (-0.001, 0.1] | 4,367 | +0.125 | 4.48 | 4.69 | 0.938 | 0.812 |
| total | (0.1, 0.25] | 7,146 | +0.129 | 6.66 | 6.55 | 1.008 | 0.667 |
| total | (0.25, 0.5] | 11,910 | -0.567 | 9.00 | 9.11 | 0.989 | 0.692 |
| total | (0.5, 0.75] | 11,910 | +1.045 | 11.78 | 11.93 | 0.985 | 0.698 |
| total | (0.75, 1.0] | 11,108 | +0.521 | 14.01 | 14.48 | 0.966 | 0.702 |

**A, fit on 2025, read on every logged 2026 state in regulation:**

| Target | Share of regulation left | States | Mean error (final - model), points | Realised sd | Model sd | Spread ratio | Within 1 sd |
|---|---|---|---|---|---|---|---|
| margin | (-0.001, 0.1] | 3,016 | +0.404 | 3.84 | 3.91 | 0.996 | 0.752 |
| margin | (0.1, 0.25] | 3,273 | +0.198 | 6.14 | 6.91 | 0.883 | 0.731 |
| margin | (0.25, 0.5] | 5,222 | +0.210 | 9.30 | 9.73 | 0.946 | 0.711 |
| margin | (0.5, 0.75] | 7,012 | +0.092 | 11.94 | 12.00 | 0.993 | 0.684 |
| margin | (0.75, 1.0] | 4,735 | -0.704 | 14.24 | 14.54 | 0.979 | 0.692 |
| total | (-0.001, 0.1] | 3,016 | +0.052 | 4.84 | 4.36 | 1.142 | 0.804 |
| total | (0.1, 0.25] | 3,273 | -0.460 | 7.01 | 6.65 | 1.053 | 0.635 |
| total | (0.25, 0.5] | 5,222 | -0.849 | 9.57 | 9.23 | 1.030 | 0.666 |
| total | (0.5, 0.75] | 7,012 | +0.567 | 12.19 | 11.55 | 1.054 | 0.65 |
| total | (0.75, 1.0] | 4,735 | +0.359 | 15.14 | 14.38 | 1.052 | 0.644 |

The widths are right (spread ratio 0.883 to 1.142) and the largest mean error is 1.045 points. Two shapes in it
matter for a total. The model's total runs high with a quarter to a half of the game left in all three reads
(mean error -0.462, -0.567, -0.849) and low with a half to three quarters left (+0.328, +1.045, +0.567):
football scores more late in each half and a clock-linear model cannot bend there. And the total's distribution is right-skewed: on the training states the
final lands above the model's own mean 45.6% of the time with a quarter of the game or less left and
46.2% between a quarter and a half, so a Normal around an unbiased mean leans over against a line set at
the median. In test A the model's mean sits above DraftKings' total by +1.36 points
on average between a quarter and a half left, and the model's bets there are mostly overs
(378 of 460 at EV 0.02). Section 7 removes both
shapes and re-grades.

## 5. The grid: every cell

Returns are units won per unit risked. "Blind, that side" is the cell's most-bet side taken at every game's first
eligible quote. "Placebo runs at or above" counts the 200 placebo runs that returned at least what the model did.

### Against the bars, eligibility as asked

| Rule | EV cut | A bets | A return | A interval | A placebo 95th | B1 return (bets) | B2 return (bets) | >= 100 bets in A | A > 0 | B1 > 0 | B2 > 0 | Interval above 0, or above placebo 95th | Clears all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 473 | -9.1% | -16.8% .. -2.9% | -0.5% | -3.3% (308) | -2.1% (249) | yes | no | no | no | no | no |
| Total, first half | 0.05 | 471 | -12.6% | -21.7% .. -6.5% | +0.1% | -2.9% (305) | -1.1% (245) | yes | no | no | no | no | no |
| Total, first half | 0.08 | 467 | -8.5% | -17.3% .. -0.5% | +0.6% | -4.6% (301) | +4.8% (240) | yes | no | no | yes | no | no |
| Total, first half | 0.12 | 466 | -11.1% | -22.1% .. -0.9% | +0.4% | -4.8% (276) | -1.2% (222) | yes | no | no | no | no | no |
| Total, first half | 0.20 | 437 | -8.4% | -15.4% .. -3.2% | +3.0% | +3.0% (167) | -2.7% (166) | yes | no | yes | no | no | no |
| Total, second half | 0.02 | 460 | -1.8% | -6.0% .. +2.9% | -2.0% | +3.2% (322) | +8.2% (269) | yes | no | yes | yes | yes | no |
| Total, second half | 0.05 | 460 | -2.5% | -7.1% .. +2.2% | -2.2% | +1.4% (322) | +11.2% (267) | yes | no | yes | yes | no | no |
| Total, second half | 0.08 | 460 | -4.3% | -9.8% .. +1.2% | -1.8% | -1.8% (322) | +10.8% (267) | yes | no | no | yes | no | no |
| Total, second half | 0.12 | 459 | -4.6% | -11.5% .. +2.6% | -0.6% | -7.8% (320) | +4.1% (264) | yes | no | no | yes | no | no |
| Total, second half | 0.20 | 458 | -6.7% | -17.5% .. +3.2% | -0.6% | +0.6% (309) | -1.4% (261) | yes | no | yes | no | no | no |
| Moneyline, first half | 0.02 | 423 | -7.3% | -19.6% .. +7.4% | +5.0% | +2.5% (280) | +7.6% (149) | yes | no | yes | yes | no | no |
| Moneyline, first half | 0.05 | 422 | -2.6% | -15.4% .. +11.0% | +6.2% | +3.4% (274) | -5.8% (142) | yes | no | yes | no | no | no |
| Moneyline, first half | 0.08 | 421 | +4.0% | -6.4% .. +16.6% | +7.5% | -0.1% (268) | +7.6% (139) | yes | yes | no | yes | no | no |
| Moneyline, first half | 0.12 | 421 | +6.2% | -3.6% .. +18.1% | +8.8% | -2.7% (260) | -4.3% (132) | yes | yes | no | no | no | no |
| Moneyline, first half | 0.20 | 409 | +5.7% | -6.1% .. +17.5% | +11.5% | +11.0% (219) | -4.5% (109) | yes | yes | yes | no | no | no |
| Moneyline, second half | 0.02 | 344 | -3.3% | -17.6% .. +8.5% | +5.9% | +11.2% (213) | -10.1% (129) | yes | no | yes | no | no | no |
| Moneyline, second half | 0.05 | 343 | -7.0% | -25.1% .. +7.8% | +5.3% | +9.0% (208) | -10.2% (125) | yes | no | yes | no | no | no |
| Moneyline, second half | 0.08 | 341 | -3.5% | -21.4% .. +10.9% | +6.3% | +3.3% (196) | -17.5% (121) | yes | no | yes | no | no | no |
| Moneyline, second half | 0.12 | 339 | -7.7% | -25.3% .. +8.9% | +5.8% | -4.1% (188) | -17.5% (116) | yes | no | no | no | no | no |
| Moneyline, second half | 0.20 | 333 | -5.0% | -22.2% .. +11.7% | +5.2% | +3.5% (176) | +2.6% (105) | yes | no | yes | yes | no | no |

Cells clearing every bar: **none**.

### Against the bars, wait and confirm

| Rule | EV cut | A bets | A return | A interval | A placebo 95th | B1 return (bets) | B2 return (bets) | >= 100 bets in A | A > 0 | B1 > 0 | B2 > 0 | Interval above 0, or above placebo 95th | Clears all |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 472 | -8.5% | -15.4% .. -2.2% | -1.6% | -2.2% (307) | -1.8% (247) | yes | no | no | no | no | no |
| Total, first half | 0.05 | 470 | -10.9% | -18.6% .. -3.7% | -1.5% | -2.8% (301) | +0.9% (242) | yes | no | no | yes | no | no |
| Total, first half | 0.08 | 462 | -7.1% | -16.2% .. +2.2% | +0.2% | -1.1% (292) | +9.4% (232) | yes | no | no | yes | no | no |
| Total, first half | 0.12 | 430 | -6.2% | -14.8% .. +2.1% | +0.7% | -2.0% (255) | -0.9% (205) | yes | no | no | no | no | no |
| Total, first half | 0.20 | 284 | -8.7% | -16.6% .. -0.4% | +2.3% | +7.1% (136) | -1.9% (144) | yes | no | yes | no | no | no |
| Total, second half | 0.02 | 460 | -0.5% | -4.1% .. +3.8% | -4.0% | +3.0% (321) | +4.5% (268) | yes | no | yes | yes | yes | no |
| Total, second half | 0.05 | 460 | -1.5% | -5.8% .. +3.5% | -3.7% | -1.3% (321) | +7.4% (266) | yes | no | no | yes | yes | no |
| Total, second half | 0.08 | 460 | -2.5% | -7.5% .. +3.2% | -3.2% | -1.7% (320) | +5.9% (265) | yes | no | no | yes | yes | no |
| Total, second half | 0.12 | 457 | -2.8% | -8.0% .. +4.5% | -3.0% | -3.9% (316) | -0.9% (261) | yes | no | no | no | yes | no |
| Total, second half | 0.20 | 451 | -1.2% | -6.2% .. +3.9% | -2.1% | -4.3% (292) | -0.0% (254) | yes | no | no | no | yes | no |
| Moneyline, first half | 0.02 | 392 | +0.6% | -13.8% .. +19.1% | +5.3% | +5.0% (263) | -5.9% (130) | yes | yes | yes | no | no | no |
| Moneyline, first half | 0.05 | 384 | +3.1% | -12.8% .. +22.8% | +7.5% | +7.2% (256) | -10.4% (123) | yes | yes | yes | no | no | no |
| Moneyline, first half | 0.08 | 377 | +14.3% | -1.4% .. +33.2% | +9.2% | +4.0% (239) | +3.1% (115) | yes | yes | yes | yes | yes | YES |
| Moneyline, first half | 0.12 | 369 | +16.5% | -0.6% .. +32.0% | +10.8% | +3.2% (217) | -1.3% (107) | yes | yes | yes | no | yes | no |
| Moneyline, first half | 0.20 | 317 | +3.5% | -13.7% .. +18.8% | +16.2% | +9.5% (159) | -11.3% (81) | yes | yes | yes | no | no | no |
| Moneyline, second half | 0.02 | 326 | +8.9% | -5.5% .. +21.2% | +6.4% | +21.7% (199) | -5.9% (113) | yes | yes | yes | no | yes | no |
| Moneyline, second half | 0.05 | 318 | +8.4% | -7.2% .. +23.5% | +6.0% | +17.3% (191) | -4.5% (105) | yes | yes | yes | no | yes | no |
| Moneyline, second half | 0.08 | 314 | +5.9% | -10.3% .. +19.4% | +6.7% | +11.2% (176) | -1.4% (101) | yes | yes | yes | no | no | no |
| Moneyline, second half | 0.12 | 297 | +12.0% | -5.3% .. +29.3% | +4.5% | +4.9% (167) | -7.6% (89) | yes | yes | yes | no | yes | no |
| Moneyline, second half | 0.20 | 263 | +13.0% | -8.9% .. +36.6% | +5.6% | +8.0% (141) | +24.8% (69) | yes | yes | yes | yes | yes | YES |

Cells clearing every bar: **Moneyline, first half at 0.08; Moneyline, second half at 0.20**. Each is one cut wide: the first-half moneyline at 0.05 and
0.12 is -10.4% and -1.3% in B2, and the second-half moneyline at
0.12 is -7.6% in B2 on 89 bets (its passing cell, 0.20, has
69). And this eligibility conditions on the future; the next table is the same season without that.

### Test A, the three eligibility rules side by side

| Rule | EV cut | As asked: bets, return | Wait and confirm: bets, return | No look-ahead: bets, return, interval, placebo 95th |
|---|---|---|---|---|
| Total, first half | 0.02 | 473, -9.1% | 472, -8.5% | 472, -7.2%, -15.8% .. -0.3%, -0.3% |
| Total, first half | 0.05 | 471, -12.6% | 470, -10.9% | 469, -13.0%, -20.0% .. -8.2%, +1.2% |
| Total, first half | 0.08 | 467, -8.5% | 462, -7.1% | 457, -8.3%, -17.1% .. -0.0%, +1.5% |
| Total, first half | 0.12 | 466, -11.1% | 430, -6.2% | 426, -3.7%, -10.7% .. +3.2%, +2.2% |
| Total, first half | 0.20 | 437, -8.4% | 284, -8.7% | 274, -11.4%, -18.6% .. -3.9%, +6.0% |
| Total, second half | 0.02 | 460, -1.8% | 460, -0.5% | 460, -1.6%, -5.3% .. +2.9%, -2.5% |
| Total, second half | 0.05 | 460, -2.5% | 460, -1.5% | 460, -0.7%, -5.6% .. +5.2%, -1.3% |
| Total, second half | 0.08 | 460, -4.3% | 460, -2.5% | 458, -4.2%, -8.3% .. +1.4%, -2.2% |
| Total, second half | 0.12 | 459, -4.6% | 457, -2.8% | 457, -5.9%, -11.6% .. +0.6%, -1.5% |
| Total, second half | 0.20 | 458, -6.7% | 451, -1.2% | 450, -1.1%, -7.2% .. +5.8%, -1.0% |
| Moneyline, first half | 0.02 | 423, -7.3% | 392, +0.6% | 401, -6.9%, -20.9% .. +8.6%, +5.4% |
| Moneyline, first half | 0.05 | 422, -2.6% | 384, +3.1% | 399, -0.7%, -14.3% .. +14.0%, +6.6% |
| Moneyline, first half | 0.08 | 421, +4.0% | 377, +14.3% | 388, +5.5%, -8.1% .. +19.0%, +7.5% |
| Moneyline, first half | 0.12 | 421, +6.2% | 369, +16.5% | 371, +6.8%, -7.8% .. +19.4%, +8.3% |
| Moneyline, first half | 0.20 | 409, +5.7% | 317, +3.5% | 297, +7.2%, -9.8% .. +23.4%, +15.9% |
| Moneyline, second half | 0.02 | 344, -3.3% | 326, +8.9% | 317, +2.4%, -12.0% .. +14.2%, +5.7% |
| Moneyline, second half | 0.05 | 343, -7.0% | 318, +8.4% | 310, +0.4%, -15.4% .. +12.7%, +6.8% |
| Moneyline, second half | 0.08 | 341, -3.5% | 314, +5.9% | 298, +5.8%, -5.6% .. +18.5%, +6.7% |
| Moneyline, second half | 0.12 | 339, -7.7% | 297, +12.0% | 288, +5.6%, -9.4% .. +24.1%, +6.9% |
| Moneyline, second half | 0.20 | 333, -5.0% | 263, +13.0% | 237, +4.5%, -9.2% .. +23.2%, +6.4% |

### Test A, as asked: 473 games, slate dates 2026-09-19 to 2026-11-07, halves split after 2026-10-13

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 473 | 230-243-0 | -49.79 | 546.00 | -9.1% | -16.8% .. -2.9% | -11.2% on 238 | -7.0% on 235 | -127 / -115 / -105 | over (344 of 473) | -8.1% | -6.6% | -0.5% | 152 of 200 |
| Total, first half | 0.05 | 471 | 220-251-0 | -68.48 | 542.38 | -12.6% | -21.7% .. -6.5% | -11.2% on 236 | -14.1% on 235 | -127 / -115 / -105 | over (292 of 471) | -8.1% | -6.5% | +0.1% | 187 of 200 |
| Total, first half | 0.08 | 467 | 228-239-0 | -45.20 | 534.31 | -8.5% | -17.3% .. -0.5% | -2.7% on 233 | -14.2% on 234 | -127 / -114 / -105 | under (257 of 467) | -5.1% | -6.6% | +0.6% | 137 of 200 |
| Total, first half | 0.12 | 466 | 221-245-0 | -59.21 | 533.86 | -11.1% | -22.1% .. -0.9% | -9.6% on 232 | -12.6% on 234 | -130 / -115 / -104 | under (357 of 466) | -5.1% | -6.5% | +0.4% | 174 of 200 |
| Total, first half | 0.20 | 437 | 213-224-0 | -41.85 | 498.02 | -8.4% | -15.4% .. -3.2% | -3.3% on 220 | -13.6% on 217 | -133 / -114 / +102 | under (369 of 437) | -5.1% | -6.7% | +3.0% | 120 of 200 |
| Total, second half | 0.02 | 460 | 241-219-0 | -9.64 | 525.83 | -1.8% | -6.0% .. +2.9% | -1.1% on 226 | -2.5% on 234 | -136 / -115 / +178 | over (378 of 460) | -8.4% | -8.1% | -2.0% | 9 of 200 |
| Total, second half | 0.05 | 460 | 239-221-0 | -13.28 | 524.65 | -2.5% | -7.1% .. +2.2% | -1.1% on 226 | -3.9% on 234 | -136 / -114 / +178 | over (370 of 460) | -8.4% | -8.2% | -2.2% | 15 of 200 |
| Total, second half | 0.08 | 460 | 234-226-0 | -22.68 | 523.25 | -4.3% | -9.8% .. +1.2% | -8.1% on 226 | -0.7% on 234 | -136 / -114 / +178 | over (347 of 460) | -8.4% | -8.2% | -1.8% | 28 of 200 |
| Total, second half | 0.12 | 459 | 233-226-0 | -23.78 | 520.81 | -4.6% | -11.5% .. +2.6% | -9.3% on 225 | -0.0% on 234 | -160 / -114 / +178 | over (323 of 459) | -8.4% | -7.7% | -0.6% | 44 of 200 |
| Total, second half | 0.20 | 458 | 225-233-0 | -34.43 | 511.37 | -6.7% | -17.5% .. +3.2% | -10.8% on 224 | -2.8% on 234 | -160 / -113 / +154 | over (248 of 458) | -8.4% | -7.0% | -0.6% | 100 of 200 |
| Moneyline, first half | 0.02 | 423 | 133-290-0 | -20.04 | 275.86 | -7.3% | -19.6% .. +7.4% | -15.5% on 196 | -1.4% on 227 | -199 / +219 / +4200 | away (216 of 423) | -8.7% | -3.5% | +5.0% | 153 of 200 |
| Moneyline, first half | 0.05 | 422 | 135-287-0 | -6.85 | 262.10 | -2.6% | -15.4% .. +11.0% | -9.4% on 196 | +2.2% on 226 | -199 / +223 / +4200 | away (217 of 422) | -8.7% | -3.1% | +6.2% | 99 of 200 |
| Moneyline, first half | 0.08 | 421 | 139-282-0 | +10.00 | 248.23 | +4.0% | -6.4% .. +16.6% | -3.2% on 196 | +9.3% on 225 | -199 / +224 / +4200 | away (214 of 421) | -8.7% | -2.8% | +7.5% | 33 of 200 |
| Moneyline, first half | 0.12 | 421 | 138-283-0 | +14.87 | 238.02 | +6.2% | -3.6% .. +18.1% | -4.5% on 196 | +14.1% on 225 | -199 / +236 / +4200 | away (215 of 421) | -8.7% | -3.1% | +8.8% | 20 of 200 |
| Moneyline, first half | 0.20 | 409 | 122-287-0 | +10.91 | 192.83 | +5.7% | -6.1% .. +17.5% | -4.4% on 191 | +13.7% on 218 | -178 / +276 / +4200 | away (206 of 409) | -8.7% | -3.4% | +11.5% | 33 of 200 |
| Moneyline, second half | 0.02 | 344 | 103-241-0 | -7.05 | 214.90 | -3.3% | -17.6% .. +8.5% | -20.8% on 158 | +8.0% on 186 | -200 / +280 / +4400 | home (189 of 344) | +1.2% | -5.5% | +5.9% | 79 of 200 |
| Moneyline, second half | 0.05 | 343 | 95-248-0 | -13.81 | 198.77 | -7.0% | -25.1% .. +7.8% | -22.7% on 158 | +3.2% on 185 | -200 / +299 / +4000 | home (181 of 343) | +1.2% | -6.7% | +5.3% | 99 of 200 |
| Moneyline, second half | 0.08 | 341 | 97-244-0 | -6.84 | 194.57 | -3.5% | -21.4% .. +10.9% | -16.4% on 158 | +4.9% on 183 | -200 / +312 / +4400 | home (181 of 341) | +1.2% | -7.3% | +6.3% | 64 of 200 |
| Moneyline, second half | 0.12 | 339 | 89-250-0 | -14.14 | 183.38 | -7.7% | -25.3% .. +8.9% | -22.5% on 156 | +1.7% on 183 | -200 / +334 / +4400 | home (175 of 339) | +1.2% | -7.8% | +5.8% | 95 of 200 |
| Moneyline, second half | 0.20 | 333 | 87-246-0 | -8.41 | 167.62 | -5.0% | -22.2% .. +11.7% | -13.1% on 153 | +0.3% on 180 | -200 / +341 / +4400 | home (170 of 333) | +1.2% | -9.3% | +5.2% | 64 of 200 |

### Test A, wait and confirm

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 472 | 231-241-0 | -46.10 | 544.33 | -8.5% | -15.4% .. -2.2% | -9.9% on 237 | -7.0% on 235 | -127 / -116 / -103 | over (375 of 472) | -9.3% | -7.4% | -1.6% | 128 of 200 |
| Total, first half | 0.05 | 470 | 224-246-0 | -59.01 | 540.61 | -10.9% | -18.6% .. -3.7% | -7.2% on 236 | -14.6% on 234 | -129 / -115 / -101 | over (340 of 470) | -9.3% | -7.5% | -1.5% | 164 of 200 |
| Total, first half | 0.08 | 462 | 229-233-0 | -37.42 | 528.08 | -7.1% | -16.2% .. +2.2% | -0.6% on 232 | -13.6% on 230 | -135 / -114 / +101 | over (296 of 462) | -9.3% | -7.2% | +0.2% | 97 of 200 |
| Total, first half | 0.12 | 430 | 215-215-0 | -30.57 | 491.08 | -6.2% | -14.8% .. +2.1% | -2.3% on 211 | -10.0% on 219 | -135 / -114 / +102 | over (248 of 430) | -9.3% | -7.1% | +0.7% | 84 of 200 |
| Total, first half | 0.20 | 284 | 138-146-0 | -28.14 | 324.25 | -8.7% | -16.6% .. -0.4% | -15.0% on 144 | -2.3% on 140 | -130 / -114 / +102 | over (160 of 284) | -9.3% | -7.6% | +2.3% | 109 of 200 |
| Total, second half | 0.02 | 460 | 244-216-0 | -2.77 | 525.85 | -0.5% | -4.1% .. +3.8% | -3.6% on 226 | +2.4% on 234 | -136 / -115 / +178 | over (397 of 460) | -9.2% | -8.8% | -4.0% | 0 of 200 |
| Total, second half | 0.05 | 460 | 241-219-0 | -7.57 | 523.30 | -1.5% | -5.8% .. +3.5% | -0.1% on 226 | -2.8% on 234 | -136 / -114 / +178 | over (400 of 460) | -9.2% | -8.6% | -3.7% | 2 of 200 |
| Total, second half | 0.08 | 460 | 238-222-0 | -12.86 | 521.66 | -2.5% | -7.5% .. +3.2% | -4.7% on 226 | -0.3% on 234 | -136 / -114 / +178 | over (386 of 460) | -9.2% | -8.6% | -3.2% | 7 of 200 |
| Total, second half | 0.12 | 457 | 235-222-0 | -14.18 | 513.53 | -2.8% | -8.0% .. +4.5% | -6.6% on 223 | +0.9% on 234 | -136 / -114 / +178 | over (378 of 457) | -9.2% | -8.8% | -3.0% | 8 of 200 |
| Total, second half | 0.20 | 451 | 232-219-0 | -6.11 | 492.85 | -1.2% | -6.2% .. +3.9% | -2.7% on 220 | +0.2% on 231 | -149 / -111 / +170 | over (363 of 451) | -9.2% | -8.2% | -2.1% | 4 of 200 |
| Moneyline, first half | 0.02 | 392 | 135-257-0 | +1.54 | 257.02 | +0.6% | -13.8% .. +19.1% | -14.0% on 185 | +10.8% on 207 | -199 / +218 / +4200 | home (214 of 392) | -3.1% | -2.8% | +5.3% | 60 of 200 |
| Moneyline, first half | 0.05 | 384 | 134-250-0 | +7.79 | 248.06 | +3.1% | -12.8% .. +22.8% | -10.1% on 181 | +12.3% on 203 | -199 / +218 / +4200 | home (221 of 384) | -3.1% | -2.5% | +7.5% | 37 of 200 |
| Moneyline, first half | 0.08 | 377 | 137-240-0 | +31.54 | 219.74 | +14.3% | -1.4% .. +33.2% | -1.2% on 179 | +25.5% on 198 | -199 / +232 / +4200 | home (222 of 377) | -3.1% | -2.2% | +9.2% | 0 of 200 |
| Moneyline, first half | 0.12 | 369 | 133-236-0 | +33.90 | 204.95 | +16.5% | -0.6% .. +32.0% | +2.5% on 175 | +26.5% on 194 | -199 / +246 / +4200 | home (213 of 369) | -3.1% | -1.3% | +10.8% | 1 of 200 |
| Moneyline, first half | 0.20 | 317 | 88-229-0 | +4.59 | 132.80 | +3.5% | -13.7% .. +18.8% | -12.4% on 153 | +15.7% on 164 | -173 / +297 / +2700 | home (180 of 317) | -3.1% | -1.5% | +16.2% | 58 of 200 |
| Moneyline, second half | 0.02 | 326 | 110-216-0 | +17.95 | 201.86 | +8.9% | -5.5% .. +21.2% | -8.0% on 154 | +19.5% on 172 | -199 / +261 / +4400 | home (185 of 326) | +2.5% | -6.3% | +6.4% | 6 of 200 |
| Moneyline, second half | 0.05 | 318 | 104-214-0 | +15.77 | 187.57 | +8.4% | -7.2% .. +23.5% | -6.4% on 152 | +18.0% on 166 | -199 / +278 / +4000 | home (177 of 318) | +2.5% | -7.8% | +6.0% | 4 of 200 |
| Moneyline, second half | 0.08 | 314 | 99-215-0 | +10.80 | 181.49 | +5.9% | -10.3% .. +19.4% | -9.5% on 150 | +16.1% on 164 | -199 / +298 / +4000 | home (170 of 314) | +2.5% | -8.4% | +6.7% | 11 of 200 |
| Moneyline, second half | 0.12 | 297 | 96-201-0 | +19.96 | 166.57 | +12.0% | -5.3% .. +29.3% | -8.4% on 140 | +23.9% on 157 | -199 / +302 / +3800 | home (162 of 297) | +2.5% | -9.4% | +4.5% | 3 of 200 |
| Moneyline, second half | 0.20 | 263 | 82-181-0 | +16.42 | 126.58 | +13.0% | -8.9% .. +36.6% | -1.4% on 124 | +22.7% on 139 | -192 / +326 / +4000 | home (140 of 263) | +2.5% | -10.9% | +5.6% | 2 of 200 |

### Test A, no look-ahead

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 472 | 234-238-0 | -39.38 | 543.42 | -7.2% | -15.8% .. -0.3% | -10.7% on 237 | -3.8% on 235 | -127 / -115 / -105 | over (365 of 472) | -7.8% | -6.2% | -0.3% | 117 of 200 |
| Total, first half | 0.05 | 469 | 218-251-0 | -69.99 | 538.99 | -13.0% | -20.0% .. -8.2% | -10.7% on 235 | -15.2% on 234 | -129 / -115 / +100 | over (324 of 469) | -7.8% | -6.4% | +1.2% | 188 of 200 |
| Total, first half | 0.08 | 457 | 223-234-0 | -43.40 | 521.31 | -8.3% | -17.1% .. -0.0% | -2.0% on 228 | -14.6% on 229 | -135 / -114 / +101 | over (270 of 457) | -7.8% | -6.3% | +1.5% | 134 of 200 |
| Total, first half | 0.12 | 426 | 218-208-0 | -17.79 | 484.78 | -3.7% | -10.7% .. +3.2% | +3.1% on 214 | -10.4% on 212 | -135 / -114 / +105 | over (223 of 426) | -7.8% | -6.0% | +2.2% | 61 of 200 |
| Total, first half | 0.20 | 274 | 129-145-0 | -35.43 | 311.24 | -11.4% | -18.6% .. -3.9% | -14.1% on 136 | -8.8% on 138 | -135 / -114 / +102 | over (142 of 274) | -7.8% | -6.1% | +6.0% | 154 of 200 |
| Total, second half | 0.02 | 460 | 241-219-0 | -8.26 | 523.88 | -1.6% | -5.3% .. +2.9% | -0.8% on 226 | -2.4% on 234 | -136 / -114 / +141 | over (389 of 460) | -7.8% | -7.7% | -2.5% | 5 of 200 |
| Total, second half | 0.05 | 460 | 243-217-0 | -3.45 | 522.86 | -0.7% | -5.6% .. +5.2% | +0.9% on 226 | -2.2% on 234 | -136 / -114 / +141 | over (390 of 460) | -7.8% | -7.6% | -1.3% | 8 of 200 |
| Total, second half | 0.08 | 458 | 233-225-0 | -21.58 | 517.14 | -4.2% | -8.3% .. +1.4% | -7.0% on 224 | -1.5% on 234 | -138 / -114 / +141 | over (372 of 458) | -7.8% | -7.9% | -2.2% | 33 of 200 |
| Total, second half | 0.12 | 457 | 227-230-0 | -29.99 | 512.29 | -5.9% | -11.6% .. +0.6% | -10.4% on 223 | -1.5% on 234 | -136 / -113 / +165 | over (366 of 457) | -7.8% | -7.4% | -1.5% | 67 of 200 |
| Total, second half | 0.20 | 450 | 230-220-0 | -5.45 | 483.82 | -1.1% | -7.2% .. +5.8% | +0.4% on 219 | -2.5% on 231 | -143 / -110 / +170 | over (343 of 450) | -7.8% | -6.8% | -1.0% | 12 of 200 |
| Moneyline, first half | 0.02 | 401 | 131-270-0 | -18.45 | 267.96 | -6.9% | -20.9% .. +8.6% | -8.4% on 187 | -5.9% on 214 | -200 / +200 / +4200 | home (218 of 401) | -2.3% | -3.8% | +5.4% | 142 of 200 |
| Moneyline, first half | 0.05 | 399 | 132-267-0 | -1.78 | 248.27 | -0.7% | -14.3% .. +14.0% | -3.4% on 187 | +1.1% on 212 | -199 / +217 / +4200 | home (216 of 399) | -2.3% | -3.5% | +6.6% | 69 of 200 |
| Moneyline, first half | 0.08 | 388 | 131-257-0 | +12.51 | 226.31 | +5.5% | -8.1% .. +19.0% | +0.7% on 184 | +8.9% on 204 | -199 / +222 / +4200 | home (214 of 388) | -2.3% | -3.1% | +7.5% | 20 of 200 |
| Moneyline, first half | 0.12 | 371 | 121-250-0 | +13.67 | 200.94 | +6.8% | -7.8% .. +19.4% | +4.9% on 179 | +8.1% on 192 | -199 / +252 / +4200 | home (210 of 371) | -2.3% | -3.7% | +8.3% | 17 of 200 |
| Moneyline, first half | 0.20 | 297 | 84-213-0 | +8.99 | 125.35 | +7.2% | -9.8% .. +23.4% | +6.4% on 144 | +7.7% on 153 | -192 / +318 / +4200 | home (173 of 297) | -2.3% | -2.2% | +15.9% | 32 of 200 |
| Moneyline, second half | 0.02 | 317 | 103-214-0 | +4.82 | 201.50 | +2.4% | -12.0% .. +14.2% | -14.8% on 147 | +13.5% on 170 | -197 / +255 / +4400 | home (180 of 317) | +1.2% | -5.8% | +5.7% | 32 of 200 |
| Moneyline, second half | 0.05 | 310 | 97-213-0 | +0.70 | 188.85 | +0.4% | -15.4% .. +12.7% | -21.9% on 144 | +15.1% on 166 | -197 / +256 / +4000 | home (170 of 310) | +1.2% | -6.1% | +6.8% | 42 of 200 |
| Moneyline, second half | 0.08 | 298 | 96-202-0 | +10.34 | 178.32 | +5.8% | -5.6% .. +18.5% | -12.5% on 138 | +17.7% on 160 | -197 / +259 / +4000 | home (162 of 298) | +1.2% | -7.4% | +6.7% | 15 of 200 |
| Moneyline, second half | 0.12 | 288 | 88-200-0 | +9.08 | 161.80 | +5.6% | -9.4% .. +24.1% | -12.7% on 131 | +17.3% on 157 | -197 / +290 / +3900 | home (153 of 288) | +1.2% | -8.7% | +6.9% | 14 of 200 |
| Moneyline, second half | 0.20 | 237 | 65-172-0 | +5.00 | 111.94 | +4.5% | -9.2% .. +23.2% | -0.3% on 112 | +8.3% on 125 | -194 / +358 / +4000 | away (119 of 237) | -16.6% | -12.8% | +6.4% | 17 of 200 |

### Test B1, as asked: 324 games, slate dates 2025-10-14 to 2026-01-20, halves split after 2025-11-15

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 308 | 159-149-0 | -11.48 | 352.15 | -3.3% | -11.6% .. +5.1% | +2.3% on 183 | -11.4% on 125 | -130 / -115 / -105 | over (229 of 308) | -11.6% | -7.8% | -0.2% | 34 of 200 |
| Total, first half | 0.05 | 305 | 158-147-0 | -9.98 | 348.38 | -2.9% | -13.9% .. +6.6% | +0.4% on 181 | -7.6% on 124 | -130 / -115 / +100 | over (212 of 305) | -11.6% | -7.7% | +0.3% | 36 of 200 |
| Total, first half | 0.08 | 301 | 153-148-0 | -15.80 | 342.72 | -4.6% | -17.8% .. +6.3% | -4.2% on 178 | -5.2% on 123 | -130 / -115 / +100 | over (204 of 301) | -11.6% | -6.8% | +2.1% | 63 of 200 |
| Total, first half | 0.12 | 276 | 140-136-0 | -14.98 | 313.55 | -4.8% | -22.4% .. +8.8% | -10.8% on 162 | +3.9% on 114 | -125 / -115 / +100 | over (170 of 276) | -11.6% | -6.5% | +3.9% | 80 of 200 |
| Total, first half | 0.20 | 167 | 91-76-0 | +5.60 | 188.55 | +3.0% | -9.6% .. +17.4% | -5.6% on 102 | +16.5% on 65 | -130 / -115 / +100 | over (84 of 167) | -11.6% | -6.2% | +9.6% | 31 of 200 |
| Total, second half | 0.02 | 322 | 177-145-0 | +11.87 | 367.90 | +3.2% | -7.0% .. +15.1% | +3.6% on 190 | +2.7% on 132 | -140 / -115 / +145 | over (284 of 322) | -4.9% | -5.6% | +0.2% | 0 of 200 |
| Total, second half | 0.05 | 322 | 173-149-0 | +4.99 | 365.89 | +1.4% | -8.1% .. +9.3% | -0.9% on 190 | +4.7% on 132 | -140 / -115 / +145 | over (266 of 322) | -4.9% | -5.7% | +0.5% | 4 of 200 |
| Total, second half | 0.08 | 322 | 167-155-0 | -6.74 | 363.32 | -1.8% | -15.3% .. +6.5% | -0.7% on 190 | -3.5% on 132 | -140 / -115 / +145 | over (255 of 322) | -4.9% | -5.5% | +0.9% | 41 of 200 |
| Total, second half | 0.12 | 320 | 155-165-0 | -27.71 | 356.53 | -7.8% | -17.5% .. +0.4% | -14.1% on 188 | +1.4% on 132 | -140 / -115 / +145 | over (247 of 320) | -4.9% | -5.3% | +1.2% | 144 of 200 |
| Total, second half | 0.20 | 309 | 160-149-0 | +1.99 | 332.38 | +0.6% | -12.1% .. +10.5% | -5.0% on 183 | +8.6% on 126 | -154 / -110 / +154 | over (224 of 309) | -4.9% | -5.0% | +3.0% | 24 of 200 |
| Moneyline, first half | 0.02 | 280 | 94-186-0 | +4.40 | 177.14 | +2.5% | -10.9% .. +18.3% | +11.7% on 170 | -12.2% on 110 | -200 / +218 / +4000 | home (161 of 280) | -1.4% | -8.2% | +4.6% | 17 of 200 |
| Moneyline, first half | 0.05 | 274 | 89-185-0 | +5.40 | 160.90 | +3.4% | -12.6% .. +20.3% | +10.0% on 169 | -7.4% on 105 | -200 / +220 / +4000 | home (153 of 274) | -1.4% | -8.5% | +6.3% | 16 of 200 |
| Moneyline, first half | 0.08 | 268 | 83-185-0 | -0.10 | 153.31 | -0.1% | -15.2% .. +17.1% | +10.9% on 166 | -17.9% on 102 | -200 / +240 / +4000 | home (146 of 268) | -1.4% | -7.6% | +7.0% | 34 of 200 |
| Moneyline, first half | 0.12 | 260 | 75-185-0 | -3.66 | 137.26 | -2.7% | -23.8% .. +17.9% | +7.9% on 160 | -19.5% on 100 | -200 / +270 / +4000 | home (142 of 260) | -1.4% | -8.1% | +7.3% | 68 of 200 |
| Moneyline, first half | 0.20 | 219 | 59-160-0 | +9.28 | 84.64 | +11.0% | -9.4% .. +32.5% | +31.2% on 131 | -14.5% on 88 | -180 / +325 / +4000 | home (113 of 219) | -1.4% | -8.6% | +13.9% | 16 of 200 |
| Moneyline, second half | 0.02 | 213 | 71-142-0 | +13.57 | 121.42 | +11.2% | -9.1% .. +26.8% | +21.8% on 131 | -4.7% on 82 | -200 / +280 / +3000 | home (127 of 213) | +3.0% | -1.8% | +13.4% | 18 of 200 |
| Moneyline, second half | 0.05 | 208 | 69-139-0 | +10.77 | 119.60 | +9.0% | -12.9% .. +25.9% | +18.3% on 128 | -5.1% on 80 | -200 / +270 / +3000 | home (125 of 208) | +3.0% | -3.0% | +12.8% | 23 of 200 |
| Moneyline, second half | 0.08 | 196 | 62-134-0 | +3.56 | 108.55 | +3.3% | -19.3% .. +21.4% | +15.6% on 120 | -14.8% on 76 | -200 / +280 / +3000 | home (114 of 196) | +3.0% | -4.9% | +13.6% | 41 of 200 |
| Moneyline, second half | 0.12 | 188 | 54-134-0 | -4.19 | 101.01 | -4.1% | -22.3% .. +12.4% | +4.6% on 116 | -19.9% on 72 | -200 / +280 / +4000 | home (105 of 188) | +3.0% | -7.2% | +12.7% | 81 of 200 |
| Moneyline, second half | 0.20 | 176 | 52-124-0 | +3.14 | 88.58 | +3.5% | -17.5% .. +23.2% | +5.7% on 107 | -0.1% on 69 | -200 / +285 / +4000 | home (100 of 176) | +3.0% | -11.1% | +11.6% | 27 of 200 |

### Test B1, wait and confirm

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 307 | 160-147-0 | -7.56 | 350.13 | -2.2% | -10.2% .. +7.6% | +3.6% on 183 | -10.7% on 124 | -130 / -115 / -105 | over (252 of 307) | -12.2% | -9.2% | -1.7% | 11 of 200 |
| Total, first half | 0.05 | 301 | 156-145-0 | -9.66 | 343.56 | -2.8% | -13.7% .. +7.1% | -3.2% on 178 | -2.3% on 123 | -130 / -115 / +100 | over (234 of 301) | -12.2% | -8.8% | -1.3% | 19 of 200 |
| Total, first half | 0.08 | 292 | 154-138-0 | -3.53 | 333.05 | -1.1% | -14.5% .. +11.2% | -3.1% on 174 | +2.0% on 118 | -130 / -115 / +100 | over (219 of 292) | -12.2% | -8.4% | -0.3% | 13 of 200 |
| Total, first half | 0.12 | 255 | 133-122-0 | -5.93 | 290.25 | -2.0% | -16.9% .. +9.8% | -6.7% on 151 | +4.7% on 104 | -125 / -115 / +100 | over (179 of 255) | -12.2% | -7.9% | +2.4% | 35 of 200 |
| Total, first half | 0.20 | 136 | 77-59-0 | +10.95 | 153.45 | +7.1% | -5.3% .. +21.4% | -2.0% on 83 | +21.5% on 53 | -130 / -115 / +100 | over (84 of 136) | -12.2% | -7.9% | +10.2% | 15 of 200 |
| Total, second half | 0.02 | 321 | 176-145-0 | +11.08 | 365.17 | +3.0% | -7.8% .. +14.7% | +4.9% on 190 | +0.4% on 131 | -135 / -115 / +150 | over (289 of 321) | -5.9% | -6.1% | -0.6% | 0 of 200 |
| Total, second half | 0.05 | 321 | 168-153-0 | -4.64 | 363.98 | -1.3% | -9.9% .. +6.6% | -2.7% on 190 | +0.9% on 131 | -135 / -115 / +150 | over (282 of 321) | -5.9% | -6.4% | +0.1% | 20 of 200 |
| Total, second half | 0.08 | 320 | 166-154-0 | -6.03 | 360.02 | -1.7% | -14.0% .. +6.0% | -0.0% on 190 | -4.1% on 130 | -135 / -115 / +150 | over (279 of 320) | -5.9% | -6.8% | -0.0% | 21 of 200 |
| Total, second half | 0.12 | 316 | 159-157-0 | -13.79 | 350.00 | -3.9% | -16.3% .. +4.3% | -6.8% on 186 | +0.2% on 130 | -145 / -115 / +185 | over (273 of 316) | -5.9% | -7.0% | -0.3% | 50 of 200 |
| Total, second half | 0.20 | 292 | 142-150-0 | -13.26 | 309.04 | -4.3% | -21.3% .. +7.1% | -12.1% on 171 | +6.6% on 121 | -145 / -110 / +185 | over (248 of 292) | -5.9% | -8.1% | +0.4% | 43 of 200 |
| Moneyline, first half | 0.02 | 263 | 92-171-0 | +8.43 | 168.57 | +5.0% | -8.2% .. +20.1% | +12.0% on 160 | -6.3% on 103 | -200 / +210 / +4000 | home (157 of 263) | -3.7% | -8.1% | +4.6% | 10 of 200 |
| Moneyline, first half | 0.05 | 256 | 87-169-0 | +10.77 | 149.40 | +7.2% | -6.9% .. +19.9% | +14.3% on 156 | -4.5% on 100 | -200 / +240 / +4000 | home (149 of 256) | -3.7% | -7.5% | +6.6% | 9 of 200 |
| Moneyline, first half | 0.08 | 239 | 76-163-0 | +5.41 | 133.40 | +4.0% | -16.9% .. +22.4% | +16.4% on 146 | -14.5% on 93 | -200 / +250 / +4000 | home (138 of 239) | -3.7% | -6.9% | +6.8% | 16 of 200 |
| Moneyline, first half | 0.12 | 217 | 64-153-0 | +3.42 | 105.69 | +3.2% | -18.0% .. +23.0% | +12.5% on 129 | -8.7% on 88 | -200 / +280 / +4000 | home (123 of 217) | -3.7% | -7.5% | +9.0% | 32 of 200 |
| Moneyline, first half | 0.20 | 159 | 40-119-0 | +5.38 | 56.43 | +9.5% | -15.8% .. +32.5% | +29.4% on 92 | -11.7% on 67 | -180 / +360 / +4000 | home (93 of 159) | -3.7% | -9.2% | +16.1% | 18 of 200 |
| Moneyline, second half | 0.02 | 199 | 72-127-0 | +24.46 | 112.84 | +21.7% | +0.6% .. +38.2% | +25.4% on 120 | +16.2% on 79 | -200 / +280 / +3000 | home (123 of 199) | +4.0% | -1.2% | +16.7% | 3 of 200 |
| Moneyline, second half | 0.05 | 191 | 68-123-0 | +19.08 | 110.43 | +17.3% | -5.6% .. +33.8% | +22.2% on 116 | +10.2% on 75 | -200 / +270 / +3000 | home (119 of 191) | +4.0% | -2.4% | +16.2% | 8 of 200 |
| Moneyline, second half | 0.08 | 176 | 60-116-0 | +11.14 | 99.91 | +11.2% | -10.6% .. +29.9% | +15.0% on 108 | +5.7% on 68 | -200 / +280 / +3000 | home (103 of 176) | +4.0% | -4.5% | +15.2% | 20 of 200 |
| Moneyline, second half | 0.12 | 167 | 52-115-0 | +4.34 | 87.91 | +4.9% | -15.0% .. +22.7% | +11.6% on 104 | -7.0% on 63 | -200 / +280 / +4000 | home (93 of 167) | +4.0% | -6.5% | +15.5% | 33 of 200 |
| Moneyline, second half | 0.20 | 141 | 43-98-0 | +5.69 | 71.42 | +8.0% | -14.5% .. +27.6% | +8.6% on 91 | +6.8% on 50 | -200 / +300 / +4000 | home (79 of 141) | +4.0% | -11.7% | +13.4% | 15 of 200 |

### Test B2, as asked: 273 games, slate dates 2025-08-23 to 2025-10-11, halves split after 2025-09-12

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 249 | 130-119-0 | -6.00 | 285.65 | -2.1% | -14.3% .. +7.8% | -10.5% on 128 | +6.8% on 121 | -125 / -115 / +105 | over (175 of 249) | -1.9% | -4.5% | +6.5% | 69 of 200 |
| Total, first half | 0.05 | 245 | 129-116-0 | -3.10 | 279.70 | -1.1% | -13.3% .. +11.5% | -13.6% on 124 | +11.7% on 121 | -125 / -115 / +105 | over (162 of 245) | -1.9% | -5.0% | +4.0% | 53 of 200 |
| Total, first half | 0.08 | 240 | 134-106-0 | +13.25 | 273.80 | +4.8% | -3.7% .. +12.7% | -4.4% on 122 | +14.4% on 118 | -125 / -115 / +105 | over (155 of 240) | -1.9% | -5.0% | +4.0% | 9 of 200 |
| Total, first half | 0.12 | 222 | 117-105-0 | -3.00 | 253.55 | -1.2% | -13.5% .. +9.3% | -11.7% on 110 | +9.3% on 112 | -130 / -115 / +100 | over (144 of 222) | -1.9% | -4.9% | +5.7% | 55 of 200 |
| Total, first half | 0.20 | 166 | 86-80-0 | -5.05 | 188.50 | -2.7% | -12.9% .. +7.3% | -8.4% on 82 | +2.9% on 84 | -130 / -115 / +100 | over (103 of 166) | -1.9% | -3.9% | +9.6% | 90 of 200 |
| Total, second half | 0.02 | 269 | 155-114-0 | +25.24 | 307.17 | +8.2% | -5.8% .. +18.6% | +4.6% on 137 | +11.9% on 132 | -140 / -115 / +145 | over (231 of 269) | +5.8% | +2.0% | +9.2% | 14 of 200 |
| Total, second half | 0.05 | 267 | 157-110-0 | +33.88 | 302.28 | +11.2% | -2.6% .. +20.8% | +9.0% on 136 | +13.5% on 131 | -140 / -115 / +145 | over (226 of 267) | +5.8% | +1.5% | +9.8% | 4 of 200 |
| Total, second half | 0.08 | 267 | 156-111-0 | +32.41 | 300.46 | +10.8% | -3.2% .. +21.0% | +7.9% on 136 | +13.8% on 131 | -140 / -115 / +145 | over (225 of 267) | +5.8% | +1.1% | +10.0% | 5 of 200 |
| Total, second half | 0.12 | 264 | 144-120-0 | +11.96 | 294.01 | +4.1% | -8.6% .. +14.2% | +1.0% on 133 | +7.1% on 131 | -140 / -115 / +165 | over (216 of 264) | +5.8% | +0.7% | +7.5% | 50 of 200 |
| Total, second half | 0.20 | 261 | 133-128-0 | -3.88 | 282.03 | -1.4% | -17.9% .. +16.1% | -5.4% on 133 | +2.8% on 128 | -140 / -110 / +170 | over (217 of 261) | +5.8% | +1.1% | +9.3% | 140 of 200 |
| Moneyline, first half | 0.02 | 149 | 53-96-0 | +7.19 | 94.52 | +7.6% | -9.7% .. +27.1% | +13.8% on 61 | +3.8% on 88 | -200 / +220 / +4000 | away (94 of 149) | -8.5% | -9.0% | +7.4% | 9 of 200 |
| Moneyline, first half | 0.05 | 142 | 43-99-0 | -5.03 | 87.10 | -5.8% | -26.7% .. +15.3% | -19.5% on 54 | +1.7% on 88 | -200 / +230 / +4000 | away (88 of 142) | -8.5% | -9.6% | +9.6% | 73 of 200 |
| Moneyline, first half | 0.08 | 139 | 47-92-0 | +6.29 | 82.24 | +7.6% | -12.6% .. +32.6% | +8.8% on 53 | +7.1% on 86 | -200 / +230 / +4000 | away (83 of 139) | -8.5% | -10.0% | +9.3% | 16 of 200 |
| Moneyline, first half | 0.12 | 132 | 40-92-0 | -3.29 | 75.80 | -4.3% | -27.7% .. +16.9% | +7.8% on 49 | -9.3% on 83 | -200 / +235 / +4000 | away (79 of 132) | -8.5% | -10.9% | +12.9% | 68 of 200 |
| Moneyline, first half | 0.20 | 109 | 30-79-0 | -2.30 | 51.50 | -4.5% | -33.4% .. +17.7% | +4.3% on 38 | -8.1% on 71 | -160 / +280 / +4000 | away (57 of 109) | -8.5% | -13.2% | +14.1% | 64 of 200 |
| Moneyline, second half | 0.02 | 129 | 31-98-0 | -6.90 | 68.07 | -10.1% | -34.8% .. +12.4% | -21.7% on 57 | -1.3% on 72 | -200 / +310 / +4000 | away (67 of 129) | -14.4% | -11.1% | +6.8% | 95 of 200 |
| Moneyline, second half | 0.05 | 125 | 29-96-0 | -6.25 | 61.42 | -10.2% | -39.4% .. +6.5% | -25.6% on 54 | +0.5% on 71 | -195 / +325 / +4000 | away (67 of 125) | -14.4% | -11.1% | +8.3% | 95 of 200 |
| Moneyline, second half | 0.08 | 121 | 25-96-0 | -9.76 | 55.86 | -17.5% | -39.4% .. +2.4% | -26.6% on 52 | -11.0% on 69 | -195 / +390 / +4000 | away (67 of 121) | -14.4% | -12.3% | +10.2% | 127 of 200 |
| Moneyline, second half | 0.12 | 116 | 24-92-0 | -9.08 | 51.79 | -17.5% | -41.5% .. +7.1% | -23.3% on 50 | -13.9% on 66 | -195 / +420 / +4000 | away (62 of 116) | -14.4% | -13.5% | +12.5% | 122 of 200 |
| Moneyline, second half | 0.20 | 105 | 26-79-0 | +1.21 | 45.88 | +2.6% | -29.5% .. +32.6% | -8.7% on 47 | +10.4% on 58 | -195 / +400 / +4000 | home (54 of 105) | +4.2% | -15.7% | +13.6% | 41 of 200 |

### Test B2, wait and confirm

| Rule | EV cut | Bets | W-L-P | Units | Risked | Return | 95% interval | Early half | Late half | Prices min / median / max | Most-bet side | Blind, that side | Placebo mean | Placebo 95th | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 247 | 129-118-0 | -5.10 | 282.45 | -1.8% | -14.6% .. +7.4% | -8.9% on 126 | +5.6% on 121 | -125 / -115 / +105 | over (177 of 247) | -4.7% | -5.5% | +4.3% | 47 of 200 |
| Total, first half | 0.05 | 242 | 130-112-0 | +2.55 | 276.55 | +0.9% | -11.9% .. +12.6% | -9.8% on 123 | +12.1% on 119 | -125 / -115 / +105 | over (173 of 242) | -4.7% | -5.3% | +3.2% | 24 of 200 |
| Total, first half | 0.08 | 232 | 135-97-0 | +24.90 | 264.55 | +9.4% | -3.1% .. +19.1% | +0.4% on 118 | +18.7% on 114 | -125 / -115 / +105 | over (163 of 232) | -4.7% | -5.3% | +4.5% | 4 of 200 |
| Total, first half | 0.12 | 205 | 108-97-0 | -2.05 | 233.50 | -0.9% | -14.3% .. +10.2% | -8.0% on 102 | +6.2% on 103 | -130 / -115 / +100 | over (145 of 205) | -4.7% | -4.6% | +5.8% | 54 of 200 |
| Total, first half | 0.20 | 144 | 75-69-0 | -3.10 | 163.30 | -1.9% | -15.0% .. +11.9% | -12.2% on 73 | +8.6% on 71 | -125 / -115 / +100 | over (102 of 144) | -4.7% | -3.3% | +10.0% | 92 of 200 |
| Total, second half | 0.02 | 268 | 149-119-0 | +13.78 | 305.27 | +4.5% | -9.3% .. +13.4% | +7.4% on 137 | +1.5% on 131 | -140 / -115 / +145 | over (236 of 268) | +2.6% | +0.3% | +6.1% | 27 of 200 |
| Total, second half | 0.05 | 266 | 151-115-0 | +22.17 | 300.24 | +7.4% | -7.8% .. +16.0% | +13.2% on 136 | +1.3% on 130 | -140 / -115 / +154 | over (235 of 266) | +2.6% | -0.1% | +6.2% | 5 of 200 |
| Total, second half | 0.08 | 265 | 148-117-0 | +17.54 | 298.49 | +5.9% | -9.2% .. +14.8% | +7.9% on 136 | +3.8% on 129 | -145 / -115 / +154 | over (234 of 265) | +2.6% | -0.7% | +6.4% | 14 of 200 |
| Total, second half | 0.12 | 261 | 135-126-0 | -2.64 | 289.07 | -0.9% | -15.4% .. +10.3% | +2.1% on 132 | -4.0% on 129 | -145 / -115 / +154 | over (230 of 261) | +2.6% | -0.8% | +6.2% | 96 of 200 |
| Total, second half | 0.20 | 254 | 130-124-0 | -0.09 | 269.93 | -0.0% | -14.8% .. +12.5% | +2.8% on 129 | -3.0% on 125 | -140 / -110 / +175 | over (233 of 254) | +2.6% | -1.9% | +5.3% | 69 of 200 |
| Moneyline, first half | 0.02 | 130 | 42-88-0 | -5.06 | 84.95 | -5.9% | -24.4% .. +10.3% | -9.4% on 48 | -4.0% on 82 | -200 / +180 / +4000 | home (65 of 130) | +1.8% | -7.5% | +10.8% | 82 of 200 |
| Moneyline, first half | 0.05 | 123 | 37-86-0 | -8.24 | 79.08 | -10.4% | -38.4% .. +14.0% | -27.3% on 45 | -1.5% on 78 | -200 / +185 / +4000 | away (66 of 123) | -10.7% | -9.1% | +10.3% | 113 of 200 |
| Moneyline, first half | 0.08 | 115 | 38-77-0 | +2.17 | 68.99 | +3.1% | -29.2% .. +30.0% | +0.7% on 42 | +4.4% on 73 | -195 / +220 / +4000 | away (59 of 115) | -10.7% | -8.9% | +13.3% | 42 of 200 |
| Moneyline, first half | 0.12 | 107 | 34-73-0 | -0.83 | 61.86 | -1.3% | -37.4% .. +26.9% | +12.0% on 39 | -8.1% on 68 | -180 / +220 / +4000 | away (54 of 107) | -10.7% | -9.5% | +14.9% | 63 of 200 |
| Moneyline, first half | 0.20 | 81 | 21-60-0 | -4.39 | 38.66 | -11.3% | -48.6% .. +17.3% | -21.9% on 29 | -7.0% on 52 | -160 / +290 / +4000 | home (46 of 81) | +1.8% | -13.1% | +18.3% | 95 of 200 |
| Moneyline, second half | 0.02 | 113 | 29-84-0 | -3.54 | 60.14 | -5.9% | -31.0% .. +21.3% | -17.7% on 47 | +3.2% on 66 | -200 / +310 / +4000 | home (59 of 113) | +1.3% | -9.8% | +10.1% | 81 of 200 |
| Moneyline, second half | 0.05 | 105 | 26-79-0 | -2.31 | 51.62 | -4.5% | -34.9% .. +18.5% | -6.7% on 44 | -2.7% on 61 | -195 / +325 / +4000 | home (54 of 105) | +1.3% | -9.8% | +16.2% | 69 of 200 |
| Moneyline, second half | 0.08 | 101 | 25-76-0 | -0.70 | 48.32 | -1.4% | -34.7% .. +23.2% | +2.1% on 42 | -4.3% on 59 | -195 / +325 / +4000 | home (51 of 101) | +1.3% | -11.7% | +11.6% | 48 of 200 |
| Moneyline, second half | 0.12 | 89 | 21-68-0 | -3.13 | 41.32 | -7.6% | -43.3% .. +27.5% | -3.8% on 37 | -10.0% on 52 | -195 / +360 / +4000 | home (46 of 89) | +1.3% | -14.0% | +12.8% | 67 of 200 |
| Moneyline, second half | 0.20 | 69 | 20-49-0 | +7.13 | 28.69 | +24.8% | -15.1% .. +56.8% | +12.0% on 31 | +36.4% on 38 | -160 / +380 / +4000 | home (36 of 69) | +1.3% | -14.8% | +19.1% | 8 of 200 |

### The blind sides

| Test | Eligibility | Rule | Over / home: bets, return | Under / away: bets, return |
|---|---|---|---|---|
| A | as asked | Total, first half | 473, -8.1% | 473, -5.1% |
| A | as asked | Total, second half | 460, -8.4% | 460, -4.9% |
| A | as asked | Moneyline, first half | 320, -2.9% | 386, -8.7% |
| A | as asked | Moneyline, second half | 267, +1.2% | 304, -15.8% |
| A | wait and confirm | Total, first half | 473, -9.3% | 473, -4.0% |
| A | wait and confirm | Total, second half | 460, -9.2% | 460, -4.1% |
| A | wait and confirm | Moneyline, first half | 317, -3.1% | 385, -8.6% |
| A | wait and confirm | Moneyline, second half | 267, +2.5% | 302, -15.8% |
| B1 | as asked | Total, first half | 309, -11.6% | 309, -1.1% |
| B1 | as asked | Total, second half | 322, -4.9% | 322, -8.0% |
| B1 | as asked | Moneyline, first half | 212, -1.4% | 261, -19.6% |
| B1 | as asked | Moneyline, second half | 180, +3.0% | 227, -19.7% |
| B1 | wait and confirm | Total, first half | 309, -12.2% | 309, -0.6% |
| B1 | wait and confirm | Total, second half | 321, -5.9% | 321, -7.0% |
| B1 | wait and confirm | Moneyline, first half | 207, -3.7% | 259, -18.8% |
| B1 | wait and confirm | Moneyline, second half | 177, +4.0% | 224, -17.4% |
| B2 | as asked | Total, first half | 254, -1.9% | 254, -10.7% |
| B2 | as asked | Total, second half | 269, +5.8% | 269, -18.7% |
| B2 | as asked | Moneyline, first half | 107, +0.1% | 203, -8.5% |
| B2 | as asked | Moneyline, second half | 103, +4.2% | 158, -14.4% |
| B2 | wait and confirm | Total, first half | 250, -4.7% | 250, -7.9% |
| B2 | wait and confirm | Total, second half | 268, +2.6% | 268, -15.7% |
| B2 | wait and confirm | Moneyline, first half | 106, +1.8% | 195, -10.7% |
| B2 | wait and confirm | Moneyline, second half | 99, +1.3% | 153, -15.9% |

**Prices laid** (the 140 cells above). Totals: -160 at the shortest, a median of -116 to -110 by cell, +185 at
the longest. Moneylines: never shorter than -200 by rule; the median bet of every cell is an underdog, +180 to
+420, and the longest is +4400. A moneyline return therefore rests on few units risked
(192.83 units over 409 bets in test A's first-half cell at 0.20), and the
moneyline intervals are 22 to 72 points wide.

**Across the 140 cells:** all 30 total cells of test A are negative (-13.0% to -0.5%), and the first-half
total's interval is entirely below zero in 12 of its 15. One cell has an interval whose lower bound is above
zero: the second-half moneyline in B1 under wait and confirm at 0.02 (+21.7%,
lower bound +0.6%); the same cell is -5.9% in B2.

## 6. Why it does not pay: two reads that do not depend on a cut

**Does the model's probability add anything to the price?** The result of the over (or the home side)
regressed on the market's no-vig probability and the model's, both as log-odds, every eligible quote, games
resampled for the interval. A model that only repeats the price has weight 0. "Slope on the model alone" is
the calibration slope: 1.0 means a claimed edge is all there.

| Test | Eligibility | Rule | Quotes | Games | Weight on the market price | Weight on the model | 95% interval of the model's weight | Slope on the model alone |
|---|---|---|---|---|---|---|---|---|
| A | as asked | Total, first half | 40,287 | 473 | 1.390 | -0.085 | -0.322 .. 0.144 | -0.068 |
| A | as asked | Total, second half | 36,830 | 460 | 0.860 | 0.129 | 0.012 .. 0.254 | 0.119 |
| A | as asked | Moneyline, first half | 34,910 | 451 | 0.635 | 0.337 | -0.013 .. 0.716 | 0.936 |
| A | as asked | Moneyline, second half | 25,149 | 377 | 0.895 | 0.218 | 0.011 .. 0.443 | 0.953 |
| A | wait and confirm | Total, first half | 31,996 | 473 | 1.318 | -0.042 | -0.344 .. 0.260 | -0.021 |
| A | wait and confirm | Total, second half | 30,533 | 460 | 0.844 | 0.285 | 0.113 .. 0.496 | 0.268 |
| A | wait and confirm | Moneyline, first half | 27,832 | 451 | 0.412 | 0.537 | 0.058 .. 1.065 | 0.928 |
| A | wait and confirm | Moneyline, second half | 21,130 | 377 | 0.638 | 0.438 | 0.127 .. 0.765 | 0.981 |
| B1 | as asked | Total, first half | 5,020 | 309 | 0.601 | 0.330 | -0.007 .. 0.679 | 0.337 |
| B1 | as asked | Total, second half | 5,348 | 322 | 1.002 | 0.166 | -0.045 .. 0.408 | 0.157 |
| B1 | as asked | Moneyline, first half | 4,608 | 303 | 0.577 | 0.620 | 0.082 .. 1.225 | 1.191 |
| B1 | as asked | Moneyline, second half | 3,924 | 287 | 0.443 | 0.588 | 0.235 .. 1.001 | 0.975 |
| B1 | wait and confirm | Total, first half | 3,972 | 309 | 0.618 | 0.407 | 0.001 .. 0.830 | 0.414 |
| B1 | wait and confirm | Total, second half | 4,491 | 321 | 1.183 | 0.325 | 0.039 .. 0.645 | 0.310 |
| B1 | wait and confirm | Moneyline, first half | 3,641 | 303 | 0.456 | 0.757 | 0.140 .. 1.498 | 1.206 |
| B1 | wait and confirm | Moneyline, second half | 3,324 | 283 | 0.103 | 0.906 | 0.379 .. 1.442 | 0.999 |
| B2 | as asked | Total, first half | 3,709 | 254 | 0.492 | 0.237 | -0.110 .. 0.634 | 0.242 |
| B2 | as asked | Total, second half | 4,227 | 269 | 1.371 | 0.319 | 0.080 .. 0.572 | 0.292 |
| B2 | as asked | Moneyline, first half | 2,777 | 220 | 1.190 | -0.032 | -0.422 .. 0.468 | 0.982 |
| B2 | as asked | Moneyline, second half | 2,421 | 196 | 0.828 | 0.194 | -0.142 .. 0.679 | 0.877 |
| B2 | wait and confirm | Total, first half | 2,763 | 250 | 0.784 | 0.304 | -0.109 .. 0.711 | 0.311 |
| B2 | wait and confirm | Total, second half | 3,372 | 268 | 1.416 | 0.429 | 0.106 .. 0.722 | 0.397 |
| B2 | wait and confirm | Moneyline, first half | 2,082 | 214 | 1.136 | 0.027 | -0.473 .. 0.702 | 1.001 |
| B2 | wait and confirm | Moneyline, second half | 1,976 | 191 | 0.624 | 0.383 | -0.082 .. 1.032 | 0.906 |

On totals the slope on the model alone is 0.119 to 0.414 in ten of the twelve reads and -0.068 and -0.021 in
the other two, the first half of 2026; the interval of the model's weight is above zero in six of the twelve.
On moneylines the interval of the model's weight is above zero in seven of the eight reads of tests A and B1
and in none of the four of B2. Part of a moneyline weight can be the no-vig arithmetic itself (a proportional
no-vig understates favourites), so it is not evidence of a price that can be beaten; the grid is.

**Does a higher EV pay more?** Test A, as asked, one decision per game and rule at its first eligible quote
(no first-crossing selection):

| Rule | EV at the first eligible quote | Bets | Wins | Units | Return |
|---|---|---|---|---|---|
| Total, first half | below..0.00 | 115 | 53 | -19.11 | -14.3% |
| Total, first half | 0.00..0.02 | 49 | 27 | +1.52 | +2.7% |
| Total, first half | 0.02..0.05 | 103 | 59 | +8.29 | +7.0% |
| Total, first half | 0.05..0.08 | 120 | 56 | -17.76 | -12.8% |
| Total, first half | 0.08..0.12 | 59 | 30 | -3.33 | -4.9% |
| Total, first half | 0.12..0.20 | 20 | 11 | +0.65 | +2.8% |
| Total, first half | 0.20..up | 7 | 3 | -1.49 | -18.8% |
| Total, second half | below..0.00 | 85 | 44 | -2.94 | -3.0% |
| Total, second half | 0.00..0.02 | 15 | 5 | -7.17 | -40.2% |
| Total, second half | 0.02..0.05 | 43 | 22 | -2.45 | -4.9% |
| Total, second half | 0.05..0.08 | 42 | 17 | -12.48 | -25.4% |
| Total, second half | 0.08..0.12 | 62 | 42 | +19.26 | +27.1% |
| Total, second half | 0.12..0.20 | 95 | 38 | -27.60 | -25.2% |
| Total, second half | 0.20..up | 118 | 65 | +4.95 | +3.7% |
| Moneyline, first half | below..0.00 | 285 | 69 | -17.70 | -12.0% |
| Moneyline, first half | 0.00..0.02 | 29 | 10 | -10.07 | -32.8% |
| Moneyline, first half | 0.02..0.05 | 31 | 10 | -5.38 | -20.4% |
| Moneyline, first half | 0.05..0.08 | 24 | 11 | +0.75 | +3.6% |
| Moneyline, first half | 0.08..0.12 | 25 | 8 | -3.82 | -22.9% |
| Moneyline, first half | 0.12..0.20 | 24 | 8 | +0.47 | +3.5% |
| Moneyline, first half | 0.20..up | 33 | 12 | +5.86 | +49.8% |
| Moneyline, second half | below..0.00 | 263 | 57 | -16.99 | -14.6% |
| Moneyline, second half | 0.00..0.02 | 21 | 8 | -1.08 | -5.5% |
| Moneyline, second half | 0.02..0.05 | 23 | 10 | +0.41 | +2.1% |
| Moneyline, second half | 0.05..0.08 | 19 | 4 | -6.32 | -46.9% |
| Moneyline, second half | 0.08..0.12 | 16 | 6 | -0.39 | -3.7% |
| Moneyline, second half | 0.12..0.20 | 18 | 8 | +4.72 | +58.4% |
| Moneyline, second half | 0.20..up | 17 | 1 | -2.31 | -67.8% |

No rule's return rises steadily with the EV band. The second-half total returns +27.1% on 62 bets
at 0.08 to 0.12, -25.2% on 95 bets at 0.12 to 0.20 and +3.7% on 118 bets above. The top band
of the first-half moneyline is +49.8% on 33 bets and of the second-half moneyline -67.8% on 17 bets.
The NCAAB selection lives in a tail that climbs with EV (`docs/sports/ncaab.md`); nothing here shows one.

## 7. A football-shaped version (defined after the first grid; `variants.py`)

To see whether the totals result is only the two shapes of section 4, I refit with time measured as the share
of SCORING left (the training games' mean points still to come at each 30 seconds, over their mean final:
0.779 with three quarters of the clock left, 0.476 at the half, 0.261 with a quarter left) and read a total's
probability off the training states' own standardised errors instead of the Normal. Both come from training
states only. It was designed after the plain grid had been read, so it is a check on the conclusion, not a
candidate.

It does what it was built to do: in test A the model's mean now sits +0.26 to +0.66 points from DraftKings'
total in every band and its mean probability of the over is 0.497. Out of sample:

**A, fit on 2025, read on the 2026 logged states:**

| Target | Share of regulation left | States | Mean error, points | Spread ratio | Share of finals above the model's mean |
|---|---|---|---|---|---|
| margin | (-0.001, 0.1] | 3,016 | +0.355 | 0.981 | 0.455 |
| margin | (0.1, 0.25] | 3,273 | +0.170 | 0.879 | 0.511 |
| margin | (0.25, 0.5] | 5,222 | +0.302 | 0.961 | 0.515 |
| margin | (0.5, 0.75] | 7,012 | +0.060 | 0.989 | 0.493 |
| margin | (0.75, 1.0] | 4,735 | -0.652 | 0.981 | 0.478 |
| total | (-0.001, 0.1] | 3,016 | -0.186 | 1.130 | 0.321 |
| total | (0.1, 0.25] | 3,273 | -0.672 | 1.050 | 0.411 |
| total | (0.25, 0.5] | 5,222 | +0.012 | 1.051 | 0.470 |
| total | (0.5, 0.75] | 7,012 | +0.360 | 1.053 | 0.482 |
| total | (0.75, 1.0] | 4,735 | +0.474 | 1.054 | 0.487 |

And it does not change the answer (bets, return):

| Rule | EV cut | A as asked | A wait and confirm | A no look-ahead | B1 as asked | B1 wait and confirm | B2 as asked | B2 wait and confirm |
|---|---|---|---|---|---|---|---|---|
| Total, first half | 0.02 | 470, -4.7% | 470, -1.5% | 470, -12.6% | 309, -4.0% | 307, -2.3% | 248, -3.7% | 246, -0.6% |
| Total, first half | 0.05 | 469, -8.8% | 469, -5.7% | 467, -8.8% | 306, -4.5% | 304, +1.1% | 245, +5.6% | 238, +7.3% |
| Total, first half | 0.08 | 469, -14.5% | 462, -6.4% | 457, -8.2% | 303, -4.0% | 290, +1.0% | 237, +1.4% | 227, +5.1% |
| Total, first half | 0.12 | 466, -10.0% | 426, -8.3% | 409, -5.7% | 279, -1.5% | 253, +1.0% | 219, -2.5% | 197, +1.9% |
| Total, first half | 0.20 | 439, -5.2% | 268, -4.9% | 263, -4.8% | 162, +4.7% | 127, +6.9% | 153, -1.7% | 130, +1.7% |
| Total, second half | 0.02 | 460, -4.5% | 460, -4.9% | 460, -9.7% | 322, +2.0% | 318, +3.6% | 265, -2.1% | 264, -4.2% |
| Total, second half | 0.05 | 460, -3.1% | 458, -6.2% | 459, -8.8% | 322, -1.6% | 318, +1.2% | 264, -2.2% | 262, -4.9% |
| Total, second half | 0.08 | 459, -5.4% | 456, -6.7% | 457, -8.5% | 322, -1.8% | 317, +1.1% | 264, +5.4% | 261, +3.9% |
| Total, second half | 0.12 | 458, -8.2% | 454, -9.4% | 454, -5.2% | 322, +1.5% | 313, +4.4% | 262, -0.0% | 256, -4.1% |
| Total, second half | 0.20 | 455, -6.6% | 441, +3.0% | 434, -1.2% | 302, +1.7% | 273, +3.5% | 254, +0.9% | 243, -1.5% |
| Moneyline, first half | 0.02 | 425, -8.3% | 392, -1.5% | 402, -8.1% | 279, +2.7% | 263, +6.9% | 150, +9.9% | 131, -3.5% |
| Moneyline, first half | 0.05 | 422, -1.5% | 384, +5.6% | 396, +0.5% | 273, +3.5% | 256, +7.3% | 143, -5.9% | 127, -5.7% |
| Moneyline, first half | 0.08 | 421, +4.6% | 378, +13.6% | 388, +4.0% | 269, -2.9% | 238, +2.2% | 139, +8.1% | 116, +4.7% |
| Moneyline, first half | 0.12 | 421, +5.6% | 369, +15.4% | 372, +6.4% | 261, -4.2% | 218, +1.3% | 135, -4.5% | 109, +0.9% |
| Moneyline, first half | 0.20 | 410, +5.7% | 316, +5.0% | 299, +6.7% | 217, +12.0% | 158, +9.7% | 110, -10.6% | 80, -6.6% |
| Moneyline, second half | 0.02 | 343, -3.8% | 323, +6.2% | 314, +1.3% | 207, +12.1% | 192, +23.7% | 125, -2.6% | 110, +4.1% |
| Moneyline, second half | 0.05 | 341, -2.9% | 314, +10.0% | 307, +4.0% | 204, -3.1% | 188, +6.7% | 121, -10.6% | 99, -7.8% |
| Moneyline, second half | 0.08 | 340, -4.5% | 309, +1.4% | 296, +4.7% | 196, -4.1% | 178, +3.0% | 118, -18.6% | 94, -1.5% |
| Moneyline, second half | 0.12 | 336, -5.3% | 289, +11.7% | 281, +8.6% | 187, -6.4% | 165, +7.3% | 116, -15.7% | 86, -4.9% |
| Moneyline, second half | 0.20 | 333, -7.8% | 261, +7.3% | 236, +2.1% | 174, +1.7% | 135, +9.8% | 102, +3.0% | 67, +16.8% |

Totals stay negative in test A in 29 of the 30 cells (the exception: the second-half total under wait and
confirm at 0.20). The moneyline returns are close to the plain model's.

## 8. The best few a night (run after the grid was written up; `night.py`)

The NCAAB selection on the four rules together: each game and rule decides at its FIRST eligible quote; a
decision bets only at or over the night's EV cut and only while the slate date holds fewer than five bets, in
the order received; a decision under the cut, or over it with the night full, spends the rule for that game. The
night's cut is the EV that the fit-side decisions exceeded four times per expected decision on a slate that
size, never under 0.02 (fit side: the 2025 replay under the all-2025 model for test A; the other half of 2025
for B1 and B2).

| Test | Eligibility | Bets | W-L | Units | Risked | Return | 95% interval | Early half | Late half | Slate dates | Bets a slate | Slates with none | Night cut min / median / max | Prices min / median / max | Placebo mean | Placebo 95th | Placebo best | Placebo runs at or above |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | as asked | 109 | 54-55 | +12.08 | 94.62 | +12.8% | -9.6% .. +34.2% | -6.5% on 45 | +26.5% on 64 | 32 | 3.41 | 1 | 0.020 / 0.060 / 0.408 | -183 / -111 / +3200 | -7.9% | +5.1% | +17.6% | 1 of 200 |
| A | wait and confirm | 97 | 52-45 | +13.28 | 92.66 | +14.3% | -7.6% .. +35.7% | -4.5% on 37 | +27.1% on 60 | 32 | 3.03 | 3 | 0.020 / 0.058 / 0.402 | -183 / -112 / +3200 | -8.0% | +8.2% | +16.4% | 2 of 200 |
| A | no look-ahead | 105 | 54-51 | +10.87 | 96.65 | +11.2% | -9.1% .. +33.5% | -5.0% on 43 | +22.5% on 62 | 32 | 3.28 | 3 | 0.020 / 0.058 / 0.402 | -183 / -111 / +3200 | -7.2% | +7.5% | +13.7% | 3 of 200 |
| B1 | as asked | 167 | 75-92 | -2.75 | 152.44 | -1.8% | -20.3% .. +15.9% | +2.1% on 72 | -4.6% on 95 | 57 | 2.93 | 0 | 0.020 / 0.020 / 0.452 | -195 / -110 / +2500 | -6.7% | +3.3% | +6.8% | 42 of 200 |
| B1 | wait and confirm | 167 | 76-91 | -0.31 | 154.13 | -0.2% | -19.5% .. +17.7% | +1.2% on 73 | -1.2% on 94 | 57 | 2.93 | 2 | 0.020 / 0.020 / 0.437 | -195 / -110 / +2500 | -7.9% | +1.5% | +10.1% | 17 of 200 |
| B2 | as asked | 99 | 47-52 | +2.75 | 95.67 | +2.9% | -17.5% .. +22.2% | +9.2% on 44 | -2.7% on 55 | 27 | 3.67 | 1 | 0.020 / 0.050 / 0.349 | -130 / -110 / +1800 | -8.9% | +5.7% | +24.8% | 25 of 200 |
| B2 | wait and confirm | 100 | 46-54 | -1.09 | 99.31 | -1.1% | -21.9% .. +17.1% | +5.7% on 44 | -6.6% on 56 | 27 | 3.7 | 1 | 0.020 / 0.049 / 0.346 | -200 / -110 / +1800 | -6.8% | +8.0% | +20.0% | 55 of 200 |

By rule:

| Test | Eligibility | Total, first half | Total, second half | Moneyline, first half | Moneyline, second half |
|---|---|---|---|---|---|
| A | as asked | 16 bets, +0.93u, +5.0% | 51 bets, +4.03u, +7.0% | 29 bets, +8.71u, +62.9% | 13 bets, -1.59u, -38.6% |
| A | wait and confirm | 15 bets, +4.22u, +24.2% | 54 bets, +7.04u, +11.4% | 18 bets, +4.33u, +42.3% | 10 bets, -2.31u, -67.0% |
| A | no look-ahead | 18 bets, +0.88u, +4.2% | 52 bets, +3.03u, +5.1% | 24 bets, +8.39u, +64.3% | 11 bets, -1.42u, -35.9% |
| B1 | as asked | 30 bets, -6.32u, -18.5% | 74 bets, -0.74u, -0.9% | 32 bets, +1.55u, +7.1% | 31 bets, +2.76u, +21.1% |
| B1 | wait and confirm | 32 bets, -4.20u, -11.5% | 76 bets, +1.31u, +1.5% | 28 bets, -0.18u, -0.9% | 31 bets, +2.76u, +21.1% |
| B2 | as asked | 17 bets, +4.15u, +21.7% | 55 bets, -0.15u, -0.2% | 15 bets, -0.92u, -11.4% | 12 bets, -0.33u, -5.4% |
| B2 | wait and confirm | 19 bets, +1.90u, +8.8% | 57 bets, -2.01u, -3.1% | 12 bets, +0.41u, +5.2% | 12 bets, -1.40u, -24.5% |

Test A is positive under all three eligibility rules and beats the placebo's 95th percentile, on
97 to 109 bets, with intervals of -9.6% .. +34.2%,
-7.6% .. +35.7% and -9.1% .. +33.5%, and an early half
that loses each time. Neither half of 2025 repeats it (-1.8% and -0.2% in B1,
+2.9% and -1.1% in B2).
In test A as asked, the first-half moneyline supplies +8.71 of the
+12.08 units on 29 bets, and the selection's longest price is
+3200. The night's cut sits at the 0.02 floor on small slates (the median cut is
0.060 in A and 0.020 in B1), so on a weekday this bets nearly every
decision.

## 9. For context: the two live models' 2026 record (`picks_record.py`)

From `ncaaf_picks.parquet`, signal_type BET, VOID and DUPLICATE excluded (one row of each, both on the
win-probability model), one unit to win with risk capped at three at COALESCE(decision_odds, dk_odds):

| Model | Record | Units | Risked | Return | Settled bets | Game dates | Prices min / median / max |
|---|---|---|---|---|---|---|---|
| ncaaf_live_total | 51-47-0 | -5.20 | 117.90 | -4.4% | 98 | 2026-08-29 to 2026-09-17 | -176 / -120 / +105 |
| ncaaf_live_win_prob | 25-24-0 | +6.73 | 47.97 | +14.0% | 49 | 2026-08-29 to 2026-11-07 | -238 / +110 / +300 |

The win-probability model is 16-9, +4.70 units to 2026-09-18 and 9-15, +2.03 units from 2026-09-19 (the window
test A covers). No settled bet was missing a price and none carries a stake of its own.

## 10. What I could not do, and what I am unsure of

Could not do:

- **In-play spreads.** None are stored for NCAAF.
- **2026 before 2026-09-19.** 145 games and 38,446 quotes have no logged state, so test A is 32 slate dates.
- **The no-look-ahead rule on 2025.** One snapshot every five minutes does not show the book's last four minutes.
- **A second out-of-sample season, or a walk-forward.** Play-by-play is stored for 2025 only.

Unsure of:

- **The 2025 clock.** Play wallclocks are edit stamps (section 2). Test B's states are softer than test A's, in a
  direction I cannot sign.
- **The 2026 clock.** Between two logged states the clock is read off a straight line, which uses the next
  state's clock (not its score).
- **Wait and confirm flatters.** It bets only when nothing is scored in the next four minutes and grades at a
  price that would be gone. The no-look-ahead rule is the honest read of the same idea, and it was written after
  the first grid.
- **The moneyline tail.** The median moneyline bet of every cell is an underdog at +180 to +420. I did not
  measure how much of the model's disagreement with those prices is the Normal's tail and how much is the game
  state, and I did not test a different tail.
- **The placebo's form.** It moves a game's model-minus-market opinion, not its raw probability. On totals the
  two are the same; on moneylines the choice matters and I chose the harder one.
- **No possession or field position.** DraftKings prices them and this model cannot. That is a handicap of the
  stored 2026 log, not of the idea.
- **Cut meaning differs by season.** 78 eligible quotes per game and rule in 2026 against 15 in 2025.

## 11. Files

All in `scripts/ncaaf_search/audit_2026_11/inplay/`:

| File | What it is |
|---|---|
| `prep.py`, `prep_out.txt` | the extracts turned into games, training states, state timelines and quotes; every count and drop |
| `grid.py`, `grid_out.txt`, `results.json` | the definitions (docstring), the fits, calibration, eligibility and the plain grid for tests A, B1, B2 |
| `diag.py`, `diag_out.txt`, `diag.json` | orientation checks, the information test, the EV bands |
| `variants.py`, `variants_out.txt`, `variants.json` | the no-look-ahead rule and the football-shaped model |
| `night.py`, `night_out.txt`, `night.json` | the best few a night |
| `picks_record.py` | the two live models' 2026 record |
| `verify.py`, `numbers.json` | bets re-graded from the raw finals (the stored units match to the cent on four cells), the counts quoted above |
| `make_report.py` | builds this file from the JSON |
| `bets_*.parquet`, `night_*.parquet`, `priced_*.parquet` | every bet of every cell, and every eligible quote with the model's numbers |
