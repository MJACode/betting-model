# NBA search: first-quarter and first-half team totals against Pinnacle's own period spread and total (pre-registered 2026-11-06, before any bet in it was graded)

mike, 2026-11-06: build an NBA first-quarter model that makes money. The team-totals search
(`docs/nba_search_q1tt.md`) priced each book's first-quarter and first-half team totals at the points implied by
the book's own period spread and total, or by the books' median. It left Pinnacle out, on the ground that Pinnacle sells
no team total. **Pinnacle does price the first-quarter and first-half spread and total** (3,613 games in the
derivative purchase, `odds` source `odds_api_nba_derivative_history`), in the same fetch as the team totals. No search
has priced a team total at Pinnacle's period numbers.

**Written before any bet was graded. Nothing below changes after a result is seen.** Lab: `scripts/nba_s_q1pin.py`.
Pass/fail: `python -m scripts.nba_game2_verdict --results DIR --house5`, then `python -m scripts.nba_s_q1pin --judge
--results DIR` for the strict season bar. No data is bought, no Odds API call is made, and the graded run is stored
in Supabase (`nba_game2_cells`) before it is read.

**What was read before this was written.** Prices and timestamps only (2026-11-06): 19,874 deciding-book first-quarter
team-total quotes over 2,426 games of 2024-25 and 2025-26 sit in the same fetch as Pinnacle's first-quarter spread and
total (the snapshot times are equal on every one). Pinnacle's numbers, read as (total ∓ spread) / 2 from the lines
alone, sit 1.0 point or more from the book's line on 621 of them, and 1.5 or more on 7. The median gap is 0.25 points.
No centre was solved and no result was read.

## 1. Everything is the team-totals search's, but the reference

The quotes, the main-number and ladder rules, the decision time (each game's one purchase 45-75 minutes before tip),
the period-market pricing that turns a quote into a centre, the result shape, the offers, the price floor, units,
settlement, the bands and the placebo are `scripts/nba_s_q1tt.py`'s, imported unchanged (`docs/nba_search_q1tt.md`
sections 2-4 and 7-10).

**The reference, family `A_pinnacle`:** Pinnacle's own coherent period spread and total quotes in that fetch, each
solved to its centre through the period market's pricing (`quote_centres` with Pinnacle as the only book). Home points
= (total centre + home margin centre) / 2, away = (total centre − home margin centre) / 2. A game where Pinnacle has
no coherent spread or no coherent total in the fetch has no number. Each deciding book's team-total offer is priced at
that number through the period's shape.

## 2. The cells (12)

| Family | Periods | Sides | Cut on EV | Cells |
|---|---|---|---|---|
| A_pinnacle | first quarter, first half (each its own) | over, under | ≥ 0.02 / 0.04 / 0.06 | 12 |

Both teams' totals form one cell per period, side and cut, as in the team-totals search. The first half is registered
beside the first quarter because the purchase holds both and Pinnacle prices both.

## 3. Bars, seasons and the placebo

- **Graded and pooled: 2024-25 and 2025-26.** 2024-25 is the choosing season the placebo reads.
- **Section 9.1's house standard, unchanged**, and the season bar read strictly: both seasons, each with 30 or more
  bets, positive (`judge_table`).
- **The placebo:** the team-totals search's consensus-style placebo, unchanged: each offer keeps its line and price,
  and its centre in a run is the team-total market's own fair centre plus the disagreement (Pinnacle's number minus
  that centre) of another game on the same date, same team role. 200 runs, seeds 1-200.

**Expected passes by chance:** 12 × 0.025 = 0.3 cells clear the interval alone.

## 4. What a pass means

A pass goes live with its own EV floor at its cut and the prices it lays stated first. The live feed fetches no
first-quarter or first-half team total and no Pinnacle period spread or total for the NBA today, so a pass needs those
markets added to the NBA game fetch.

## 5. Counts before grading (2026-11-06, `--counts`, no bet graded)

The synthetic checks pass (12 cells through the harness, both periods betting, every cell with its placebo runs).

| Period | Games with a Pinnacle number | Games with team-total offers | Offers priced | Pinnacle's number minus the team-total market's fair centre: median / 75th / 90th / 95th / 99th percentile of the gap, points | Mean |
|---|---|---|---|---|---|
| First quarter | 2,409 | 2,442 | 39,440 | 0.16 / 0.27 / 0.39 / 0.47 / 0.64 | +0.10 |
| First half | 2,411 | 2,442 | 39,930 | 0.16 / 0.28 / 0.40 / 0.49 / 0.67 | −0.03 |

Once each quote is solved to its centre, the books' team totals sit within half a point of Pinnacle's period numbers
95% of the time. The bets each cell would place (2024-25 + 2025-26):

| Period | Side | EV 0.02 | EV 0.04 | EV 0.06 |
|---|---|---|---|---|
| First quarter | over | 368 (82 + 286) | 82 | 18 |
| First quarter | under | 91 (81 + 10) | 17 | 3 |
| First half | over | 91 (49 + 42) | 30 | 15 |
| First half | under | 147 (71 + 76) | 34 | 7 |

**11 of the 12 cells are under 200 bets and fail bar 1 by construction**: too few games to tell. Only the
first-quarter over at EV 0.02 can be judged. Prices laid run from −130 to +110.

## 6. Results (graded 2026-11-06, run `2026-11-06-q1pin`)

Stored in Supabase before it was read (12 rows in `nba_game2_cells`). The grade took 8.4 minutes.

**0 of the 12 cells pass, and none clears the 95% interval.** 11 are under 200 bets: too few games to tell. The one
cell that can be judged, the first-quarter over at EV 0.02: 368 bets, +20.9 units, +5.1%, interval −3.6% to +14.1%,
+0.2% in 2024-25 (82 bets) and +6.6% in 2025-26 (286); it fails the interval, the bands and the placebo. The blind
first-quarter over returned −1.2%.

**Closed: the books set their first-quarter and first-half team totals within half a point of Pinnacle's own period
spread and total 95% of the time, and the few larger gaps do not pay.**
