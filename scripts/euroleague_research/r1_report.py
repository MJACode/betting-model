"""Round 1: assemble C:\\Users\\micha\\AppData\\Local\\Temp\\euroleague_1h1q_round1.md
from each round-1 script's printed output.

    python scripts/euroleague_research/r1_report.py            # runs every script, then writes
    python scripts/euroleague_research/r1_report.py --from DIR # uses captured outputs in DIR

Run order when running the scripts (r1_fullgame.py writes the full-game working
copy the later scripts read): r1_settle, r1_settle2, r1_facts, r1_facts2,
r1_pinnacle_ladder, r1_fullgame, r1_coverage, r1_nbooks, r1_baselines,
r1_accuracy, r1_method, r1_kill, r1_kill2, r1_structure.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = Path(r"C:\Users\micha\AppData\Local\Temp\euroleague_1h1q_round1.md")

CAPTURE = {  # script -> capture file name
    "r1_settle": "r1_settle.txt", "r1_settle2": "r1_settle2.txt", "r1_facts": "r1_facts.txt",
    "r1_facts2": "r1_facts2.txt", "r1_pinnacle_ladder": "r1_pinnacle_ladder.txt",
    "r1_fullgame": "fullgame.txt", "r1_coverage": "coverage.txt", "r1_nbooks": "nbooks.txt",
    "r1_baselines": "baselines.txt", "r1_accuracy": "accuracy.txt", "r1_method": "method.txt",
    "r1_kill": "kill.txt", "r1_kill2": "kill2.txt", "r1_structure": "structure.txt",
}

TEXT = r"""
# EuroLeague first half and first quarter: research round 1

2026-11-13. Every number below was printed by a script in
`scripts/euroleague_research/` (named above each table) reading only the local
parquet cache (`C:\Users\micha\euroleague_research\cache`, a copy of
Supabase) and, for full-game lines, the purchase spool for 2025-26 only. No
database, no API call, no repo file edited.

**Conventions.** Results in units. Every bet sized to win 1 unit, risk capped
at 3 (a price p < 0 risks min(|p|/100, 3); p > 0 risks 1 to win p/100), graded
at the book's quoted price. Return = units won / units risked on graded
(non-push) bets. Intervals are 90%, resampling game dates (1,000 draws).
Seasons use the ending year: 2024 = 2023-24, 2025 = 2024-25, 2026 = 2025-26,
2027 = 2026-27 to date (107 played games). First half = quarters 1+2, first
quarter = quarter 1; overtime never counts. "Decidable" books (a pick may name
them): FanDuel, BetMGM, BetRivers, Fanatics (DraftKings quoted none). BetUS,
GTbets and MyBookie are offshore references only, marked "(ref)", never a book
a pick could name.

**Frozen before any result was read** (header of `r1_lib.py`): the six main
markets; decision marks T-10 (the close) and each game's earliest mark; the
off-centre rule (a main spread or total whose no-vig side probability is
outside 35-65% is set aside); best price = the best decidable price on the
modal decidable number (the repo's same-line rule); the method's cut grid
0.00-0.05 with the catalogued cut 0.02, decided at T-10, other read T-60. The
structural rule's thresholds (1.0 / 1.5 / 2.0 points) are fixed in
`r1_structure.py`'s header, written before that script first ran. The
off-centre rule was set after reading the price ranges (`r1_facts.py`) and
before any return was graded.

## Verdict in one paragraph

Nothing clears. The first-half and first-quarter two-way moneylines are
draw-no-bet (a tied period pushes), measured. Decidable books exist only from
2025-26, so every bettable table rests on about 423 games (2025-26 plus
2026-27 to date), which resolves a return to roughly +/-8 points. No blind
baseline is positive once 556 cells are corrected for multiplicity (0 of 103
positive cells with 25+ bets survive). The books price the first half at a
near-constant 50.2% of the full-game total and the first quarter at 25.1%, and
their period numbers sit within about half a point of that straight line, so
the full-game-to-half method can only disagree with them through its own
fitted slope. Run unchanged on the 2025-26 time split it shows one positive
(first-half totals, 51 bets, +29.8%), which comes from a slope that held in
2025-26 and failed when frozen and read on 2023-24 and 2026-27. A walk-forward
version on a sharp full-game anchor shows one lead (first-quarter unders, 59
bets, +15.0%, interval -5.5 to +33.0) that passes the placebo and the
market-alone control but fails the side split (57 of 59 unders), the
best-dates test, and rests on one season. Two data-quality problems were found in the
stored main numbers of BetMGM (2026-27) and Fanatics (2025-26).

## 1. Settlement

**The two-way first-half and first-quarter moneylines push on a tie.** No
two-way quote at any book carries a draw price; the three-way markets
(BetRivers, Fanatics) do. At BetRivers, on the same fetch, the two-way price
de-vigged equals the three-way price with the draw removed (draw no bet):
median difference 0.0000, mean absolute 0.0012 over 2,461 first-half pairs
(0.0046 first quarter). Had a tie lost the two-way bet, the two-way fair price
would match the three-way win price instead, and it is +0.028 (first half) and
+0.033 (first quarter) away from it. Measured at BetRivers only; the other
books' two-way raw margins (1.05-1.09) are what a push market carries, not what
a tie-loses market would (about 1.01-1.02 at the same vig). **Fanatics has no
two-way first-half moneyline at all**, only the three-way, where a tie loses: a
different bet. Ties are common: the first quarter ended level in 134 of 2,125
played games (6.31%; 3.7-8.2% a season), the first half in 72 (3.39%). Spreads
and totals push on whole numbers (about 22% of first-half main numbers are
whole; first-quarter numbers almost never are). The grading code asserts the
spread sign and the tie push on every import (`r1_lib._assert_settlement`).

{r1_settle2}

{r1_settle}

## 2. Data facts that shape every table

**Stored "main" numbers that are ladder rungs.** Many BetMGM 2026-27 and
Fanatics 2025-26 "main" quotes sit 4-8 points from every other book at long
prices (-550/+310). No `spreads_h1_alternate` or `totals_h1_alternate` market
exists in the cache, so the feed returned one number for those books and it was
stored as the main. Off-centre quotes (no-vig side outside 35-65%) were set
aside from every main-line table: BetMGM 2026-27 440 first-half spread rows (66
games), 694 first-half total rows (96 games), 794 first-quarter spread rows
(101 games), 829 first-quarter total rows (104 games); Fanatics 2025-26 127 and 111 rows (36 and 30 games). **Even the quotes
that passed that filter are rungs**: every on-centre BetMGM 2026-27 quote is 1+
points from the other books' median (median 3-5 points), and 79-85% of
Fanatics' 2025-26 ones are (`r1_nbooks.py`, table 2). Read every BetMGM
2026-27 and Fanatics 2025-26 per-book cell as a bet on a rung, not on the main
line. This looks like a main-number selection problem in the period purchase
for those two books (flagged, not investigated: no repo edits this round).
BetRivers' first-half spreads and totals hold 3 games in 2025-26 (its
moneyline holds 316); FanDuel's first-quarter totals in 2026-27 hold only the
T-10 mark.

{r1_facts2}

{r1_facts}

**A sharp full-game anchor exists for every season.** Pinnacle's full-game
alternate ladders were bought in the same per-event fetch as the period quote,
at every mark: 8,957 (game, mark) ladders on 291, 330, 402 and 107 games, 11
rungs half a point apart, and 100% of them bracket even money. The fair number
is where the ladder's no-vig probability crosses 50%. In 2025-26 it matches the
five-book US consensus read from the spool at the same mark: median difference
0.0, SD 0.49 points on totals and 0.46 on spreads (3,171 pairs). Pinnacle
prices no first-half or first-quarter line, so a sharp-against-soft read of the
periods themselves is not possible from what was bought.

{r1_pinnacle_ladder}

**The 2025-26 full-game consensus (the spool).** 25,904 snapshot files read
for 2025-09-01 to 2026-05-31; all 3,216 (game, mark) pairs found with a median
of 5 US books; every feed name mapped; no event had its home and away swapped
against EuroLeague. At T-10 the full-game snapshot was read a median 14.4
minutes before the tip; the period quotes at T-10 were last updated a median
14.8 minutes before it (5-95%: 14.2-15.7), about 4.8 minutes before each ask.
That stored time moves in lockstep across every book (SD under 2 minutes at
every mark), so it reads as the feed's snapshot time rather than each book's
own last update (flagged, not checked against the raw feed).

{r1_fullgame}

## 3. Coverage (task 1)

Games with an on-centre main quote, by season, book and mark. **No decidable
book quoted a period line before 2025-26**: 2023-24 is BetUS only, 2024-25
BetUS and GTbets. In 2025-26 FanDuel and BetMGM carry the first-half spread
and total (about 314 of 402 games), BetRivers the first-half and first-quarter
moneyline (316); in 2026-27 FanDuel and BetRivers carry every market on nearly
every game, except that FanDuel posts no first-quarter moneyline and its
first-quarter total only at T-10.

{r1_coverage}

**Best price is often one book.** On the modal decidable number at T-10, a
real shop (2+ decidable books on the same number) existed on 176 of 316
first-half spread games in 2025-26 and 74 of 107 in 2026-27; 141 of 316 and 58
of 107 for first-half totals; the first-quarter moneyline in 2025-26 was
BetRivers alone on 313 of 316 games.

{r1_nbooks}

## 4. Baselines (task 2)

Every blind bet, per market, season and decision (T-10; each game's earliest
stored mark), at each book's own number and price and at the best decidable
price. 556 cells; 502 with 25+ bets; 103 of those positive; **0 survive
Benjamini-Hochberg at a 10% false-discovery rate, and no positive cell has a
90% interval above zero.**

The pooled table (2025-26 + 2026-27 at the best decidable price; offshore books
over every season, reference only) is the one to read first. Best and worst
pooled at the best decidable price, T-10:

| Market | Best blind side | Worst blind side |
|---|---|---|
| First-half spread | underdog: 423 bets, -8.59 units, -1.75% [-8.59, +4.70] | favourite: 423 bets, -50.67 units, -10.65% [-17.21, -3.55] |
| First-half total | over: 423, -27.86, -5.58% [-12.38, +1.25] | under: 423, -36.00, -7.54% [-14.60, -0.57] |
| First-half moneyline | underdog: 465, +19.14, +4.22% [-4.64, +12.35] | favourite: 465, -81.98, -9.67% [-14.56, -4.29] |
| First-quarter spread | home: 423, -8.00, -1.69% [-9.72, +6.10] | away: 423, -52.67, -10.54% [-18.08, -2.54] |
| First-quarter total | under: 421, -25.22, -5.36% [-11.88, +1.27] | over: 421, -33.63, -6.83% [-13.27, -0.54] |
| First-quarter moneyline | underdog: 421, -13.07, -3.21% [-12.66, +5.75] | away: 423, -50.43, -10.80% [-19.39, -2.00] |

One pattern repeats: **the first-half favourite loses more than the underdog**
on the spread at the offshore reference in every season (BetUS pooled:
favourite -13.33% on 1,082 bets, underdog -2.17%) and at the decidable books in
2025-26 (favourite -13.23%, underdog +0.78%), though 2026-27 to date reverses it
(favourite -2.99%, underdog -9.38% on 107). The underdog never clears zero
pooled. The only pooled positive, the first-half moneyline underdog, is taken
through the kill tests in section 7 (P4) and fails them.

{r1_baselines}

## 5. The market's own accuracy, and the half against the full game (task 3)

**(a)** De-vigged proportionally, the spread and total closes score like a coin
flip at their own number (log loss 0.689-0.696 against 0.6931; Fanatics' few
rung quotes aside), as a main line priced near 50/50 should. The moneyline closes score 0.634-0.670 (first half)
and 0.660-0.681 (first quarter). The close is not measurably sharper than the
earliest mark on the same games (differences within about 0.007, Fanatics
aside). Pooled at
the decidable books, the moneyline's calibration slope (result on de-vigged
probability) is 0.877 for the first half and 0.751 for the first quarter: below
1, i.e. the close prices favourites too short, which agrees with the
favourite-underdog asymmetry in section 4. The slope column is not meaningful
for spreads and totals, whose probabilities cluster within a few points of 50%.

**(b)** **The books set the first-half total at 50.05-50.29% of the full-game
total and the first-quarter total at 25.07-25.37%**, with a standard deviation
of 0.2-0.3 percentage points a season, and their period number strays only
0.23-0.55 points from its own straight line off the full game. The results
centre on the same fractions (first half 49.87-50.68%, first quarter
24.75-25.63%), but their slope on the full-game total is noisier and steeper:
0.55, 0.57, 0.72 and 0.53 by season against the books' 0.49-0.50. 2025-26's
0.72 is the outlier that drives the V1 result below. First-half spreads are
0.52-0.54 of the full-game spread at the books (results 0.40-0.55), first
quarter 0.25-0.28 (results 0.18-0.39). By full-game band nothing stands out
beyond noise, with one band read worth a later look: where Pinnacle has the
home club as an underdog by 0-4 points, the home club covered the first-half
number in 58.9% of 175 games (found after looking; a hypothesis, section 10).

{r1_accuracy}

## 6. The catalogued method, run unchanged (task 4)

"A half priced from the full-game consensus", in the repo's own pricing code
(imported from `models/ncaab_first_half_spread.py` and
`models/ncaab_first_half_total.py`, not copied): one least-squares map of the
period outcome on the full-game number, the repo's kernel outcome table, every
decidable on-centre quote priced, one bet a game at the largest edge above the
cut, graded at that book's quoted price. Moneylines are priced off the margin
table with a tie pushing. **Two departures, both forced:** the team
half-tendency term is left out (its prior needs last season's full-game lines;
in its source it moved the mean by at most about a quarter point); and the
201-game (V1) and 291-game (V2, first fit) tables never reach the table's
500-game kernel floor, so they are the method's own fallback, every fitting
game shifted to the mean. The 621- and 1,023-game V2 tables reach the floor by
widening the bandwidth to about 1.2-4.5 points at the median key (up to 8.7 in
the tails; `r1_kill2.py`, table 1).

- **V1, the brief's version:** 2025-26 only, anchor = the five-book US
  consensus from the spool at the same snapshot, split at the median tip
  (2026-01-08 19:30Z): 201 games fit, 201 graded.
- **V2, a walk-forward on Pinnacle's ladder:** fit on every earlier season
  (2023-24 -> grade 2024-25; + 2024-25 -> grade 2025-26; + 2025-26 -> grade
  2026-27), graded at the decidable books and, as reference, the offshore ones.

Up to 216 cells (6 markets x 2 reads x 6 cuts, V1 decidable, V2 decidable and
offshore). At the catalogued cut 0.02, T-10:

| Version | Market | Bets | Units | Return [90%] |
|---|---|---|---|---|
| V1 | first-half total | 51 | +17.14 | +29.78% [+8.56, +49.99] |
| V1 | first-half spread | 91 | -13.84 | -13.36% [-29.37, +3.18] |
| V1 | first-half moneyline | 121 | +5.30 | +4.40% [-16.55, +24.35] |
| V1 | first-quarter total | 18 | +5.78 | +30.61% [-2.20, +63.04] |
| V1 | first-quarter spread | 9 | -1.15 | -8.63% |
| V1 | first-quarter moneyline | 15 | +7.93 | +42.63% |
| V2 decidable | first-half total | 37 | -3.24 | -7.80% [-31.21, +17.89] |
| V2 decidable | first-half spread | 65 | -12.72 | -16.88% [-35.77, +1.67] |
| V2 decidable | first-half moneyline | 118 | -26.55 | -19.87% [-34.46, -4.88] |
| V2 decidable | first-quarter total | 59 | +10.85 | +14.96% [-5.49, +32.97] |
| V2 decidable | first-quarter spread | 3 | -1.21 | |
| V2 decidable | first-quarter moneyline | 7 | +2.25 | |

**Does the full-game-to-half mapping look mispriced? No.** The books' map is a
near-constant fraction with half a point of scatter, and a map fitted on
enough games (V2: 621+, slope 0.51-0.59 for the first-half total) agrees with
it so closely that it rarely finds a 2% edge, and loses where it does. V1's
disagreements come from a slope of 0.71 fitted on 201 games of one season.

{r1_method}

## 7. Kill tests on every positive result

`r1_kill.py` runs the method's own decide/grade code for each test.

**P1. V1 first-half total** (51 bets, +17.14 units, +29.78% [+8.56, +49.99]).
Passed: neighbourhood of cuts (every cut 0.00-0.05 positive); early/late (+14.2%
on 25 bets, +44.5% on 26); every other read T-360 to T-30 positive (+23.5% to
+37.2%); placebo with the anchor shuffled across the graded games (real +29.8%,
200 shuffles' 95th percentile -0.3%); price range (median -113, shortest -140,
none shorter than -200). Failed: **fit on every season available** (822 games:
the slope falls to 0.544 and only 9 bets remain); **the frozen fit read on
unseen seasons** (2026-27 to date -15.1% on 38 bets; 2023-24 at offshore books
-9.6% on 127; 2024-25 +10.8% on 96); **without its 10 best dates** (+2.9% on
35 bets); side split borderline (37 overs of 51, 73%; the blind over on the
same games -0.8%); bets far below the 200-bet bar. Return does not rise
steadily with edge (bands +15.4, -14.6, +10.7, +26.8, +59.5). Verdict: a
2025-26-only slope. Dead as a rule.

**P2. V2 first-quarter total** (59 bets, +10.85 units, +14.96% [-5.49,
+32.97]). Passed: it is walk-forward by construction; neighbourhood at T-10
(+2.5, +10.6, +15.0, +26.4% at cuts 0.00-0.03); early/late (+16.5% / +13.3%);
every other read in 2025-26 positive (+22.0% to +26.8% at T-360 to T-30);
placebo (real +13.3% vs 95th percentile -0.5%); return rises with edge (bands
-6.3, +6.6, +9.7, +30.0%); price range (median -118, shortest -190). Failed:
**side split** (57 of 59 bets are unders; the blind under at the best decidable
price on the same seasons lost -5.4% on 421); **without its 10 best dates**
(-13.1% on 38); **one season carries it** (2025-26: 55 bets, +13.3%; 2026-27: 4
bets; 2024-25 at offshore books: 12 bets, -8.7%); interval includes zero.
**Passed the market-alone control row** (`r1_kill2.py`): the same table, cut,
books and seasons with the market's own median number in place of the
full-game anchor loses at every cut (-8.1% on 14 bets at 0.02, -1.9% on 61 at
0.01, -4.5% on 151 at 0.00), so the anchor, not plain line shopping, carries
the lead. Its mechanism is a fitted first-quarter mean about 0.2-0.3 points
under the books' 25.1% (fit a = 1.476, b = 0.2412 on 2023-24 and 2024-25), so
it buys unders; of its 52 bets on games with 2+ decidable books quoting, 44
sit at the highest decidable number (28 strictly above the lowest). Verdict: a
lead, not a pass (section 10).

{r1_kill2}

**P3. V1 first-half moneyline** (121 bets, +4.40%). Failed the placebo (84.5th
percentile; 95th +7.2%), early/late (+22.5% / -13.9%), the 10 best dates
(-27.5% without them), fit on every season (-17.7% on 71), the frozen fit on
unseen seasons (2023-24 -18.6% on 60, 2024-25 -10.8% on 115, 2026-27 +2.5% on
50), and its walk-forward twin V2 (-19.9% on 118). Dead.

**P5. V1 first-quarter total** (18 bets, +30.6%). Under 25 bets; failed the
neighbourhood (cuts 0.03 and 0.04 negative), the 10 best dates (-50.3%), the
frozen fit on 2023-24 (-4.4% on 127) and 2024-25 (-26.9% on 15). Dead.

**P4. The blind first-half moneyline underdog** at the best decidable price
(465 bets, +19.14 units, +4.22% [-4.64, +12.35]). Passed early/late inside
2025-26 (+8.1% / +8.6%). Failed the season split (2025-26 +8.4% on 358;
2026-27 -9.8% on 107; offshore earlier seasons: 2023-24 BetUS -17.8% on 256,
2024-25 GTbets -4.2% on 282) and the 10 best dates (-5.9% without them). It is
one side: home underdogs +15.8% on 134 [-1.0, +32.4], away underdogs -0.4% on
331, and the profit sits at +150 to +300 (prices past +300 went 0-18). Dead as
a blind rule; "the home underdog in the first half" is a hypothesis
(section 10).

{r1_kill}

## 8. Structural checks: do the books disagree at the same mark?

**Rarely across the US/offshore divide, often within the decidable books, and
mostly because of the rung problem.** At T-10 the decidable books' median
differs from the offshore median by 1+ points on 4.7% of first-half spread
games and about 17% of first-half total games (2025-26 and 2026-27).
Disagreement inside the decidable set looks large (62% of 2026-27 first-half
spread games 1+ points apart), but FanDuel's own first-half spread sits 1+
points off the other books on 12.8% of its 2025-26 quotes and 3.4% in 2026-27,
while BetMGM 2026-27 and Fanatics 2025-26 sit off on nearly all of theirs
(section 2). **Betting against a decidable book standing 1+ points off the
others loses or breaks even at every threshold** (T-10, threshold 1.0:
first-half spread -0.24% on 228, first-half total -6.78% on 313, first-quarter
spread -7.45% on 158, first-quarter total -14.25% on 142; the only positive
cells, first-quarter spreads at 1.5 and 2.0 points, +2.75% on 94 and +4.12% on
70, are mostly Fanatics rungs (57 of 94, 47 of 70) and their intervals run
from about -12% to +21%). The off-centre rungs themselves carry their own margin: blind on the
long-priced side -12.35% (415 bets, median +215), on the short-priced side
-6.69% (415, median -325).

{r1_structure}

## 9. What the sample can resolve

About 2,700 bets resolves a return to roughly +/-4 points. The decidable
history is about 423 games a market (2025-26 plus 2026-27 to date): the
measured 90% half-width on a pooled blind side is about 7-9 points, one season
(316-358 games) about 8-11, and a cut that keeps 50 bets about 20. The offshore
reference over three seasons (about 1,090 bets at BetUS) resolves to about +/-4
(90%) but cannot be bet. **Nothing in this round can resolve an edge of the
size these markets would plausibly hold (a few points);** a result has to be
large and pass the kill tests to mean anything, and none did. 2026-27 adds
about 270 more regular-season games by May.

## 10. What to test next

1. **The first-quarter under lead (P2)**, frozen as it stands (fit on 2023-24
   to 2025-26, cut 0.02, T-10, decidable books) and read unchanged on 2026-27
   as it is played; it bet 4 games of the first 107, so the read needs most
   of the season. Its control row is already negative (section 7), so what it
   still has to show is a second season and both sides of the total.
2. **The home underdog in the first half**: the moneyline (+15.8% on 134) and
   the spread band (home covered 58.9% of 175 games as a 0-4 point full-game
   underdog). Both were found after looking, so test them on what they did not
   come from: 2023-24 and 2024-25 at the offshore books, and 2026-27 forward;
   check relocated "home" games (Belgrade, Sofia, Sarajevo) are not driving it.
3. **The moneyline close's calibration** (slope 0.877 first half, 0.751 first
   quarter at the decidable books): a market-anchored shrink of the de-vigged
   probability toward 50%, fitted on 2025-26 and read on 2026-27.
4. **V1 on more seasons** once the 2023-24 and 2024-25 full-game spool is in,
   with the team half-tendency term restored; a slope fitted on one season is
   what killed P1.
5. **Fix the stored main number for BetMGM 2026-27 and Fanatics 2025-26**
   before any book-specific result is read; BetMGM is half the 2026-27
   decidable first-quarter moneyline coverage.
6. **The three-way first-half market**: BetRivers prices the first-half draw at
   a fair 4.8% and the first-quarter draw at 6.5%, against realised tie rates
   of 3.4% and 6.3%. Check whether the three-way sides are cheaper than the
   two-way ones on the same games (a low-priority price check, not an edge
   claim).
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", default=None)
    args = ap.parse_args()
    outs = {}
    for script, cap in CAPTURE.items():
        if args.src:
            raw = Path(args.src, cap).read_text(encoding="utf-8")
        else:
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            raw = subprocess.run([sys.executable, "-W", "ignore", str(HERE / f"{script}.py")], cwd=REPO,
                                 env=env, capture_output=True, text=True, encoding="utf-8").stdout
        lines = [ln for ln in raw.splitlines() if "Warning" not in ln and not ln.strip().startswith("return np.")]
        outs[script] = f"Printed by `scripts/euroleague_research/{script}.py`:\n\n```\n" + "\n".join(lines).rstrip() + "\n```"
    OUT.write_text(TEXT.format(**outs).lstrip(), encoding="utf-8")
    print("wrote", OUT, OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
