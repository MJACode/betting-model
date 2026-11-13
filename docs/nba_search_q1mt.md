# NBA search: first-quarter moneyline on the cover-record step, first-quarter total on the shooting-luck gap (pre-registered 2026-11-07, before any bet in it was graded)

mike, 2026-11-07: "find a winning model for ML and totals as well", after the first-quarter spread model
(`nba_q1_trend`) went live. **What every earlier search did with these two markets** (read from `nba_game2_cells`,
2026-11-07): the first-quarter moneyline, 32 cells across the fourth search's P1, P2 and P3_F1 and the fifth search's
F7, none with its 95% interval above zero (best +4.4%); the first-quarter total, 104 cells across P1, P2, P3_F1, F7,
the eighth search's over/under records (Q1T) and the starters search, none either (best +5.8%).

**Two ideas no search has graded on these markets,** each with a live sibling:

- **Family M:** the cover-record step that `nba_q1_trend` bets on the first-quarter spread (the eighth search's
  L5to10 step), bet on the same team's first-quarter **moneyline** instead. The eighth search graded spreads and totals
  only.
- **Family T:** the shooting-luck gap (the second search's F4) on the first-quarter **total**. The fourth search's
  P3_F4 ran it on the first-half total and both team totals, never on the first quarter. Its full-game form is
  `nba_total_luck` and its first-half form `nba_first_half_total_luck`, both live.

**Written before any bet was graded. Nothing below changes after a result is seen.** Lab: `scripts/nba_s_q1mt.py`.
Pass/fail: `python -m scripts.nba_game2_verdict --results DIR --house5` (section 9.1's house standard). The graded
run is stored in Supabase (`nba_game2_cells`) before it is read. No data is bought; no Odds API call is made.

## 1. Data, decision time, prices

The eighth search's (`docs/nba_models_2026.md` section 12.1): each game's one per-game purchase 45-75 minutes before
tip (decision point D), 2023-24, 2024-25 and 2025-26, the deciding books with Pinnacle; first-quarter scores through the
first search's check. **The price:** the best deciding offer on the cell's side, at -200 or better, under the
first-quarter market's fair line (Pinnacle's no-vig where it quotes coherently, else the deciding books' consensus;
the spread and total priced through `scripts.nba_game4_p3.market_pricing`, the moneyline from the no-vig prices
directly). One unit to win, risk capped at 3. A level first quarter voids a two-way first-quarter moneyline at every
book: it settles as a push.

## 2. Family M: the step's hot team on the first-quarter moneyline (4 cells)

The step, the check and k are `nba_q1_trend`'s, computed by the eighth search's own code
(`scripts.nba_game8_q1_trends.signals`, window L5to10): a team at last-5 venue cover net 3 or more against an opponent
at -1 or -2; k = min(its last-10 net, minus the opponent's). The bet is that team's first-quarter moneyline.

| Cells | Check | Cut on k |
|---|---|---|
| 2 | the season-average check (the spread check, as live) | k >= 2 / k >= 4 |
| 2 | none | k >= 2 / k >= 4 |

Bands (bar 5) along k from 0, edges 2 and 4. Placebo: the eighth search's (each game's trend inputs moved together to
another game on the same date), 200 runs. Control, never judged: the cold team's moneyline at the same cuts.

## 3. Family T: the shooting-luck gap on the first-quarter total (8 cells)

The gap is the fourth search's P3_F4 number for the first-half total, unchanged: the luck-adjusted minus the raw
projected full-game total, in full-game points, unscaled (`scripts.nba_game2_luck.f4_projections`); its population
rule, both teams with 10 or more games this season, is kept. A side is bet where the gap toward it reaches the cut.

| Cells | Sides | Cut on the gap |
|---|---|---|
| 8 | over, under | >= 1 / 2 / 3 / 4 points |

Bands along the gap from 0, edges 1, 2, 3, 4. Placebo: the gap shuffled between games on the same date, 200 runs.

## 4. Seasons and bars

2023-24, 2024-25 and 2025-26 graded and pooled; 2023-24 and 2024-25 are the choosing seasons the placebo reads (nothing
is fitted: the cuts are fixed). Section 9.1's house standard, unchanged: 200 or more pooled bets; the pooled whole-day
bootstrap 95% interval above zero; seasons mostly positive; beats the blind bet on its dominant side; the bands; the
choosing seasons' return above the 95th percentile of 200 placebo runs. A cell under 200 bets reads "too few games to
tell".

**Expected passes by chance:** 12 × 0.025 = 0.3 cells clear the interval alone.

## 5. What a pass means

A pass ships live (mike's standing rule: what passes goes live), with its own EV floor and the prices it lays stated
first. Family M needs a live first-quarter moneyline fetch beside the spread one; family T a live first-quarter total
fetch, each in the same call as `nba_q1_trend`'s spread fetch.

## 6. Counts before grading (2026-11-07, `--counts`, no bet graded)

Prepared in 348 seconds. First-quarter moneyline offers: 57,896 over 3,667 games; first-quarter total offers: 46,178;
games with a shooting-luck gap and a total offer: 3,202. The bets each cell would place (2023-24 / 2024-25 / 2025-26):

| Family | Cell | Bets | By season | Prices (min / median / max) |
|---|---|---|---|---|
| Q1M | no check, k >= 2 | 125 | 31 / 41 / 53 | -198 / +110 / +360 |
| Q1M | no check, k >= 4 | 29 | 6 / 12 / 11 | -162 / +120 / +250 |
| Q1M | the spread check, k >= 2 | 87 | 20 / 31 / 36 | -192 / +130 / +360 |
| Q1M | the spread check, k >= 4 | 23 | 5 / 9 / 9 | -155 / +128 / +250 |
| Q1L | over, gap >= 1 / 2 / 3 / 4 | 1,043 / 595 / 323 / 150 | 386-335-322 at >= 1 | -137 / -111 / +135 at >= 1 |
| Q1L | under, gap >= 1 / 2 / 3 / 4 | 1,067 / 594 / 295 / 122 | 365-366-336 at >= 1 | -141 / -111 / +138 at >= 1 |

**Every family M cell is under 200 bets and fails bar 1 by construction**: the step is rare (about 29 to 42 games a
season), so a first-quarter moneyline on it cannot be told from zero by the house standard. It is graded and reported
in full anyway. The over at gap >= 2 bets the same 595 games the live first-half over was graded on.

## 7. Results (graded 2026-11-07, run `2026-11-07-q1mt`)

Stored in Supabase before it was read (14 rows in `nba_game2_cells`: 12 registered, 2 controls). 200 placebo runs a
cell. **0 of the 12 cells pass; 1 clears the 95% interval alone** (0.3 expected by chance).

**Family T, the shooting-luck gap on the first-quarter total: nothing.**

| Side | Gap >= 1 | >= 2 | >= 3 | >= 4 |
|---|---|---|---|---|
| over | 1,043 bets, -2.5% | 595, +0.9% (-6.9% to +8.5%) | 323, -3.1% | 150, +2.7% |
| under | 1,067, -2.5% | 594, -5.5% | 295, -1.9% | 122, +8.4% (-9.3% to +26.6%) |

The over at gap >= 2 is the first-half model's cut on the same 595 games: +8.0% on the first half, +0.9% on the first
quarter. The effect does not carry to the first quarter. **Closed.**

**Family M, the step's hot team on the first-quarter moneyline:**

| Cell | Bets | Units | Return | 95% interval | 2023-24 / 2024-25 / 2025-26 | Fails |
|---|---|---|---|---|---|---|
| **the spread check, k >= 2 (the live rule)** | 87 | +17.78 | +25.8% | **+1.7% to +50.0%** | +39.3% / +45.5% / +4.3% | bar 1 (bets) only |
| the spread check, k >= 4 | 23 | +3.85 | +22.9% | -27.2% to +74.5% | +43.2% / +32.4% / +5.8% | bets, interval, seasons |
| no check, k >= 2 | 125 | +12.86 | +10.5% | -7.6% to +28.8% | +19.8% / +27.3% / -5.9% | bets, interval |
| no check, k >= 4 | 29 | +2.81 | +11.5% | -29.9% to +52.4% | +55.5% / +22.4% / -19.9% | bets, interval, seasons |

- **The live rule on the moneyline clears five of six bars and fails only the 200-bet bar**, the same standing as
  `nba_q1_trend` on the spread. Its bands are positive (k 0-2 +3.2% on 85; k 2-4 +26.8% on 64; k 4+ +22.9% on 23) and
  it is above its placebo.
- **It is the same bet, and the weaker way to make it.** It takes the same team in 87 of the spread model's 88 games
  (the 88th, POR @ MEM on 2024-11-25, drew no moneyline bet) and in no other game. On those games the spread made
  +26.33 units (+27.4%, 58-29-1) and the moneyline +17.78 (+25.8%, 46-35-6). The hot team is getting points in 66 of
  the 88 spread bets, so the moneyline is mostly a plus price (median +130, up to +360). Live beside the spread model it
  would double the stake on one signal; it adds no game.
- The control, the cold team's moneyline with no check: 123 bets, -14.62 units, -12.8%.
- 2025-26, the latest season, made +4.3% on 36 bets, against +39% and +46% in the two before.

**Built anyway (mike, 2026-11-07: "Build it anyway").** The moneyline cell with the spread check at k >= 2 is live as
`nba_q1_trend_ml` (`models/nba_q1_trend_ml.py`; `docs/sports/nba.md`, "First quarter"). The total stays closed.
