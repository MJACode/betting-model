# The Pinnacle run-line rule (`mlb_spread_market`): the 2026 season, month by month

> **Provenance.** First written 2026-09-19 for PR #761, which was never
> merged. Carried to master 2026-10-10 as a write-up only (the PR's test,
> module docstring and card comment were not kept). Figures marked
> **2026-09-19** are the PR's own. Figures marked **2026-10-10** were
> re-measured with read-only SQL against production during the review of
> PR #761, or for this write-up. Where the two disagree, both are shown.

**The rule.** Take Pinnacle's no-vig price on the MLB run line (±1.5), take
a bettable soft book's no-vig price on the same line, and bet the soft book
when Pinnacle's side is at least 1.8 points more likely there. One bet a
game. This is the model `mlb_spread_market`; its cut and the 2026-09-15
evidence for it are in `docs/mlb_runline_ou_edge_search.md`.

**The finding.** Across the season the rule is a thin positive (+3.2% to
+3.7% depending on the book list), but it is not positive month by month:
April is flat or red and May is red on every book list measured. It does
not clear the bar the 2026 MLB searches used (positive in every month, at
least 40 bets, a few bets a day, part of a neighbourhood rather than one
setting). Whether this model publishes, stays off or is retired is mike's
call.

---

## Where it stands (2026-10-10)

It is not betting, for three separate reasons:

1. **The publish switch is off.** The repo default for
   `MLB_SPREAD_MARKET_PUBLISH` is 0. On Railway the variable read True at
   13:26 UTC and False at 14:25 UTC on 2026-09-19, on a redeploy of the same
   commit, and has been off on every pass since (`config.py`, the
   "CORRECTED THE SAME DAY" comment).
2. **The own-EV floor blocks it even with the switch on.** Its floor is
   0.00 on the calibrated probability (#796), and the calibration map turns
   its flags negative: the three flags of 2026-09-20 came out at −0.109,
   −0.148 and −0.111 (#801). It is not in `MODELS_ON_OWN_PROBABILITY`.
3. **The MLB season is over**, and since #901 (2026-10-09) the MLB cards
   skip a game that has already started.

**Live record** (`picks`, every BET this model wrote, read 2026-10-10):

| Game date | Rows | W-L | No action | Units (flat) |
|---|---:|---|---:|---:|
| 2026-09-16 | 2 | 1-1 | 0 | −0.09 |
| 2026-09-17 | 9 | 6-3 | 0 | +2.64 |
| 2026-09-18 | 13 | 5-8 | 0 | −2.90 |
| 2026-09-19 | 5 | 1-0 | 4 | +1.60 |
| **Total** | **29** | **13-12** | **4** | **+1.24** |

The last row was written 2026-09-19 at 11:24 UTC. Nothing since.

**One stale number on master.** The module docstring in
`models/mlb_game_market.py` still justifies the cut with the 2026-09-15
monthly table ("Sep +11.19 (5 of 6 months positive)"). The grid below,
which runs to the end of the season, does not support that reading. The
docstring was not edited here because this change is docs only.

---

## How it was measured

This copies `models/mlb_game_market.load_latest_quotes`, `find_spread_bets`
and the card's price floor:

- `odds.snapshot_type = 'open'` and `snapshot_at <= games.commence_time`
  (no quote taken after first pitch)
- the latest such row per (game, book)
- sharp book Pinnacle, two-way, run line only (|spread| = 1.5)
- soft books from `BEST_LINE_BOOKMAKERS` (Pinnacle, Bovada and ESPN Bet are
  not a price to take)
- the same `spread_home` at both books, quotes no more than 300 seconds
  apart
- edge = Pinnacle no-vig minus soft no-vig; one bet a game, the largest
  edge
- edge at least 1.8 points and an American price of −200 or better
- graded on the home number (CLAUDE.md §4): home covers when
  (home − away) + line > 0; units from the price taken; a push counts 0

This is not the first-open, DraftKings-only construction that produced the
old +25% figure for the totals public fade (`docs/mlb_total_public_fade.md`).

**Two book lists.** On 2026-09-19 the soft list had 11 books (today's 8
plus Rebet, Fliff and Bally Bet). Four books were dropped from the shopped
list on 2026-09-20 (`config.py`, the "TEN BOOKS" comment), so the 8-book
column is what the model would see today.

---

## Monthly grid at 1.8 points

| Month | 11 books, 2026-09-19 (PR) | 11 books, 2026-10-10 | 8 books, 2026-10-10 |
|---|---|---|---|
| Apr | 77 bets, −0.14u (−0.2%) | 77, **−2.01u** (−2.6%) ¹ | 73, +0.19u (+0.3%) |
| May | 71, −1.53u (−2.2%) | 71, −1.53u | 69, −1.28u (−1.9%) |
| Jun | 62, +4.89u (+7.9%) | 62, +4.89u | 59, +2.63u (+4.5%) |
| Jul | 46, +4.19u (+9.1%) | 46, +4.19u | 44, +4.23u (+9.6%) |
| Aug | 72, +6.25u (+8.7%) | 72, +6.25u | 68, +4.73u (+7.0%) |
| Sep 1-18 | 40, +2.09u (+5.2%), 23-17 | 40, +2.09u | 36, +0.54u (+1.5%) |
| Sep 19-28 | — | 24, +0.73u (+3.0%), 14-10, max 7 a day | 24, +0.73u |
| **Through Sep 18** | **368, +15.75u (+4.3%)** | **368, +13.88u (+3.8%)** | 349, +11.04u (+3.2%) |
| **Regular season** | — | **392, +14.61u (+3.7%)** | **373, +11.77u (+3.2%)** |
| Postseason, to Oct 9 | — | 9, −1.05u, 5-4 | — |

¹ April re-measured on 2026-10-10 is the same 77 bets as on 09-19 but
−2.01u, not −0.14u. No April MLB score has been updated since 09-19 (a
`games.updated_at` check returned no rows), so the cause of the difference
is **not established**. April is flat or red on every version.

Other facts from the 2026-09-19 measurement (11 books, not re-run):

- Early against late: April to June +1.53% on 210; July to Sep 18 +7.9% on
  158. (With the re-measured April, April to June is +1.35u on 210, +0.6%.)
- At most 7 bets a day (in April and June).
- July was not stable inside the month: July 1-15 +11.87u on 25, July 16-31
  −7.68u on 21.
- August's +6.25u on 72 is the same neighbourhood an earlier search
  reported as +6.34u on 97 (looser: no −200 price floor and a 1.5-point
  mix). Same sign, same month, not a new edge.
- The worker job `mlb-game-line-market-sweep-open-bettable-2026-09-15` ran
  this rule at 2, 3 and 4 points through 2026-09-16. Its 2-point monthly
  cells were reproduced (May −3.15u on 47; July +3.53u on 28; August +6.70u
  on 41).

---

## Neighbouring cuts (2026-09-19, 11 books, not re-run)

| cut | Apr | May | Jun | Jul | Aug | Sep 1-18 | note |
|---|---|---|---|---|---|---|---|
| 1.5 points | 127, −10.22u | 123, −7.74u | 103, +11.50u | 80, +1.71u | 116, +17.73u | 76, +0.73u | April and May worse |
| **1.8 points** | **77, −0.14u** | **71, −1.53u** | **62, +4.89u** | **46, +4.19u** | **72, +6.25u** | **40, +2.09u** | the model's cut |
| 2.0 points | 49, −1.37u | 47, −3.15u | 41, +3.48u | 28, +3.53u | 41, +6.69u | 32, +6.34u | Sep under 40 bets; April and May still red |

The 2-point September (+6.34u on 32) is the best September cell. It does
not repair April and May, and it is under 40 bets in the month that was
meant to confirm the rule.

## Narrowing it (2026-09-19, 11 books, not re-run)

| setting | Apr | May | rest | result |
|---|---|---|---|---|
| Top 2 a day by edge | 44, **−5.66u** | 53, **−7.16u** | Aug 48, +9.02u; Sep 29, +3.87u | the red months get redder |
| Pinnacle's favoured side only (fair ≥ 0.5) | 38, **−10.90u** | — | — | worst on the worst month |
| Home side only | 33, +6.92u | 40, **−2.94u** | — | the side that wins April loses May |
| Away side only | 44, **−7.06u** | 31, +1.41u | — | the mirror of home |
| Public split or reverse line movement | — | — | — | cannot be measured: see the coverage gap below |

No setting both narrows the rule and makes every month positive.

---

## Public-betting coverage gap

`public_betting` consensus run-line splits, counting only a split taken
before first pitch (an offset-aware time comparison; a plain text
comparison lets post-start rows through, the same trap as
`docs/mlb_market_handicap_features.md`).

As measured 2026-09-19:

| month | MLB games | games with any public row | split taken before first pitch |
|---|---:|---:|---:|
| Apr | 395 | 0 | **0** |
| May | 424 | 15 | **0** |
| Jun | 400 | 400 | 59 |
| Jul | 370 | 342 | 25 |
| Aug | 414 | 397 | **0** |
| Sep (to 18) | 239 | 239 | 39 |

August has 794 run-line split rows and none survives the before-first-pitch
bound; a text comparison would show 208, which is the leak, not coverage.
May's 15 rows are also after first pitch. Re-counted 2026-10-10 (home side,
consensus, before first pitch): Jun 59, Jul 25, Aug 0, Sep 154, Oct 17.
The table keeps one row per game, market, side and book, so a later update
overwrites the pre-game split; the August gap is permanent.

---

## The live bets against the re-measure

The 29 live rows were written at the first moment each game qualified and
then locked (CLAUDE.md §1c), not at the last pre-game quote. On
2026-09-19 the PR compared the two for Sep 16-18: the live rows were 24
bets, −0.36u (13 of them on the 18th); the last-quote re-measure for the
same three days was 7 bets, −1.52u, at most 5 a day. The disagreement the
rule bets on is often gone by first pitch, so the live card bets more
games than the re-measure does.

---

## What this is not

- Not a change to `MLB_SPREAD_MARKET_PUBLISH` or to the model's cut.
- Not an unpause of `mlb_runline` or of any trained MLB model.
- Not the totals public fade (`docs/mlb_total_public_fade.md`), which has
  its own re-measure.
- Not evidence for the first-open or DraftKings-only versions of this
  rule; those are different constructions.
