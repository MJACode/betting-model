# Horse racing — first market audit on the free files

Written 2026-11-15, the day after the scope (`docs/horse_racing_scope.md`) and
the source catalogue (`docs/horse_racing_sources.md`). The league doc, with the
market grid, is `docs/sports/racing.md`. No model, no `picks` row, no config.

Every table names the script that printed it. Units are the repo's published
stake: 1 unit to win, risk `1/(decimal - 1)` capped at 3, net of exchange
commission on a winning bet where there is one. Return is units over units
risked, with a 95% interval clustered by race. "Flat" is return on a 1-unit
stake, printed beside it so a short-priced bet's capped risk is visible.

## 1. What was stored, and where

`scripts/horse/fetch_datasets.py` downloaded the free files;
`scripts/horse/store_files.py` stored every CSV in Supabase **before any table
below was read**: 86 files, 360.5 MB raw, 97.4 MB gzipped, one row per file in
`nfl_research_data_backup` (the per-file research backup; the name is
historical and the `source` marker says whose file it is):

| `source` | Files | Raw | Gzipped |
|---|---:|---:|---:|
| `horse_racing|betfair_anz_thoroughbreds` | 82 monthly CSVs, 2020-01 to 2026-10 | 340.2 MB | 91.7 MB |
| `horse_racing|gdaley_hkracing` | 2 (races, runs) | 11.5 MB | 3.5 MB |
| `horse_racing|lantanacamara_hong_kong_horse_racing` | 2 | 8.8 MB | 2.2 MB |

`store_files --verify` read every row back, decompressed it and matched its
sha256 to the file on disk: 86 stored, 0 missing, 0 mismatches. The PC mirror
(`scripts/local_mirror.py run --only public.nfl_research_data_backup`) then
held 3,780 rows against Supabase's 3,780 (it held 3,694 before the store).
`data/horse/` is now a cache of those rows.

The existing table was used, rather than a new `racing_*` table, because a new
table is DDL and DDL forces a PostgREST schema reload (`data/ddl_guard.py`);
the store ran at 15:30 ET on an NFL Sunday with games live.

## 2. What these files can and cannot decide

| File | A decision may read | Hindsight, never an input | Price a bet is graded at |
|---|---|---|---|
| Betfair ANZ CSVs | the best back and lay at the **scheduled** start, and the two book percentages at that moment | every `WIN_PREPLAY_*` and `PLACE_*_PRICE_TAKEN` field and every volume: they run to the actual off | BSP (a bet at BSP is executable), or the scheduled-off best back |
| Hong Kong 1997–2005 | runner and race facts from earlier rows | `win_odds` and `place_odds` of the race itself: they are the **final** pools | the final pool odds, which are what a pool bet is paid |
| Hong Kong 2014–2017 | the same | the same | the same |

So the Betfair files hold **one** decision moment, the scheduled start. The
scope's 60/30/15/5-minute neighbourhood cannot be run on them. The best back
carries no size, so a fill at that price is assumed, not known.

In a pool, the final odds are the price the bet is paid at, so grading at them
is right. Deciding on them is not: the bettor sees the pool a minute or more
before the off and the late money moves it. Every Hong Kong rule below that
reads the race's own pool is an **upper bound**, an information test, not a
units claim. The scope said "a backtest that bets final odds is betting the
close, phase 2 has to refuse that"; corrected in place there: for a pool bet
the close is the price; the rule is that the decision may not read it.

## 3. Hong Kong, 1997–2005: the final pools

`python scripts/horse/hk_study.py`. 6,348 races, 79,447 runners; 6,286 races
graded after dropping 12 races without exactly one winner and 50 whose pool
book sits outside 1.10–1.35 (data errors). Dates are obscured by the set's
author; race order equals date order (checked on every race), and seasons are
cut at 1 September.

**The pool.** Median win book 1.2305 (sum of 1/odds), so about **18.7% comes
out of the win pool**. The place pool's median book is 1.2266 per place paid.
A winner's odds × 10 over its HK$10 dividend has a median of 0.992: the odds
are the dividend, rounded down.

**Calibration.** The pool share against the win rate, by band: within 0.4
points in every band of 14,000+ runners. Shorter horses win a little more
often than their pool share says (+0.36 points at 10–20%, +0.79 at 20–30%
on 4,370 runners, +2.08 at 40–50% on 623), and longshots under 2% a little
less (0.88% won against 1.16% said). A slight favourite-longshot lean, far
smaller than the take.

**Blind win bets at final odds** (each runner in the band, one unit to win):

| Odds | Bets | Units | Return [95%] | Flat |
|---|---:|---:|---|---:|
| 1–2 | 858 | −205.5 | −16.7% [−22.5, −11.0] | −16.0% |
| 2–3 | 2,571 | −293.4 | −17.7% [−22.2, −13.2] | −17.6% |
| 3–5 | 6,882 | −351.3 | −15.1% [−18.5, −11.7] | −15.1% |
| 5–8 | 10,571 | −340.7 | −17.4% [−20.9, −13.8] | −17.7% |
| 8–13 | 15,167 | −369.9 | −22.6% [−26.5, −18.7] | −23.1% |
| 13–21 | 11,501 | −129.9 | −17.8% [−24.1, −11.4] | −17.6% |
| 21–51 | 16,200 | −107.5 | −20.1% [−27.4, −12.7] | −20.6% |
| over 51 | 14,965 | −90.2 | −48.1% [−58.4, −37.8] | −52.2% |
| the favourite | 6,284 | −651.4 | −16.7% [−19.8, −13.6] | −16.2% |

Every band loses about the take; the longest odds lose more.

**By meeting.** Happy Valley's night meetings have the smaller pools, which is
where a longshot bias would show if it shows anywhere. It does not differ:
favourites −15.5% [−20.8, −10.1] there (2,320 bets) against −17.3% at Sha Tin
(3,964); runners over 20 lose −26.5% and −26.9%.

**Hong Kong 2014–2017** (the second set, licence unknown, research only;
2,361 races): every band loses again, −13.5% to −28.0%, the favourite −14.2%
on 2,360 bets, and over 51 −54.2%. 11.4% of its runners show odds of 99,
which is the site's display cap, so its longshot prices are a floor.

### 3a. Place pool against win pool (the "Dr Z" test)

The place probability of each runner from the final win pool by Harville,
against the final place odds, races of 7 or more runners (3 places paid).

Harville over-rates short horses for a place, as the literature says: said
0.843, placed 0.752 at 80–90%; said 0.917, placed 0.781 above 90%. Betting
every runner the raw formula calls +EV loses (EV > 0: 5,112 bets −348.6 units,
−8.7% [−11.8, −5.7]).

Calibrated on 1997–2000 (a logistic on Harville's log-odds and the field size)
and graded on 2001–2004, 2,636 races, at final place odds:

| Calibrated EV cut | Bets | Units | Return [95%] | Seasons positive |
|---|---:|---:|---|---|
| > 0 | 3,345 | −71.3 | −10.1% [−17.3, −3.0] | 1 of 4 |
| > 0.05 | 2,590 | −20.0 | −7.2% [−18.0, +3.5] | 1 of 4 |
| > 0.10 | 2,133 | −16.7 | −14.9% [−32.0, +2.1] | 1 of 4 |
| > 0.15 | 1,870 | −22.1 | −30.0% [−49.6, −10.4] | 0 of 4 |
| > 0.20 | 1,678 | −21.1 | −37.5% [−58.4, −16.6] | 0 of 4 |

No cut is positive, and this is the upper bound (the rule read both final
pools). **Null.**

### 3b. Fundamentals, then the public: Bolton–Chapman plus Benter

Stage 1 is a conditional logit (one softmax per race) on 25 runner facts in
seven groups, every one built from earlier rows only: form (last and last-three
finishing position, lengths beaten, starts, debut), rating and weights, draw
(and draw at Happy Valley), jockey and trainer win rates shrunk toward 8%,
a speed figure against a par time built from earlier races only, layoff and
trip changes, and the horse's own odds last time. A missing value is the race
mean with a debut flag beside it, never 0. Stage 2 is Benter's blend,
`softmax(b · log p_model + c · log p_public)`, fit on the season before the
graded one; stage 1 on every season before that. Graded seasons 1999–2004,
4,581 races.

| Probability | Log-likelihood per race (higher is better) |
|---|---:|
| The final pool, de-vigged | −2.04455 |
| The pool, calibrated (stage 2 with the pool alone) | −2.04425 |
| Stage 1, fundamentals only | −2.23865 |
| Benter's blend | −2.04447 |

| Season | `b` on the model | `c` on the pool | pool-only `c` |
|---|---:|---:|---:|
| 1999 | +0.012 | +1.052 | +1.060 |
| 2000 | −0.106 | +1.164 | +1.093 |
| 2001 | −0.052 | +1.054 | +1.018 |
| 2002 | −0.058 | +1.126 | +1.089 |
| 2003 | +0.044 | +1.023 | +1.051 |
| 2004 | −0.000 | +1.108 | +1.108 |

The weight on the model is indistinguishable from 0 in every season, and the
blend scores worse out of sample than the calibrated pool alone.

**The harness catches a leak, so its null means something.** With the race's
own speed figure (from its own finish times) added as a feature, the same
walk-forward scores −0.167 for the model and −0.083 for the blend, and `b`
on the model is +2.9 to +9.1 in every season (`hk_study.py`, "leak check"). Removing any
one feature group moves the blend by at most 0.0004 (`hk_study.py`, the
ablation). Betting the blend's best runner per race at final odds: 5 bets
at EV > 0 and none above 0.10. **Null: on these facts, the model holds nothing
the final pool does not.** Per the scope (§3, stage 2), this is the written
result, and stage 2 is not re-run without a new feature.

Why this is weaker than it looks against Benter's published success: Benter's
pool was the odds minutes before the off, not the final pool, and his model
had over a hundred engineered variables. Our test blends against the final
pool, which already holds the late money, so it is the harder test of the two.
The scout found the published Hong Kong models reporting positive returns
(Bolton and Chapman 1986; Chapman 2008 on 2,000 Hong Kong races; Benter 1994)
as abstracts or summaries, not as replications on this set
(`docs/sports/racing.md`, the leads table).

## 4. Australia and New Zealand on the Betfair exchange, 2020-01 to 2026-10

`python scripts/horse/anz_study.py --commission state` (net) and
`--commission 0` (gross). 132,750 races with a winner; 132,681 with every
runner priced at BSP and at the scheduled-start back; **115,296 races
(1,128,588 runners) with a usable scheduled-start book** (the 13.1% removed
are listed in `docs/sports/racing.md`).

**Commission.** Betfair Australia charges its market base rate on a market's
net win: NSW and ACT 10%; every other state 7% until 2025-03-24 and 8% from
2025-03-25 (The Straight, 2025-03-04; Betfair's own commission page says
8–10% "currently"). No source gives a New Zealand rate; the study charges
New Zealand races the non-Australian rate in the same article, 5% then 6%.
Every Betfair tutorial the scout read assumed 5%. One bet per market, so the
per-market netting changes nothing here.

**The exchange is as accurate as a market gets.** Log loss of the winner per
race: scheduled-start back 1.8017, BSP 1.7981, so the money between the
scheduled start and the off adds information. BSP's de-vigged chance against
the win rate is within 0.2 points in every band holding 8,000 or more
runners; +0.85 points at 60–80% (4,509 runners) and +3.66 above 80% (213).

**Blind win bets**, decided on the scheduled-start back, graded at that back
and at BSP:

| Back price | Bets | At the back, gross | At BSP, gross | At BSP, net [95%] |
|---|---:|---:|---:|---|
| 1.0–1.5 | 2,296 | +0.72% | +1.50% | −0.70% [−3.11, +1.72] |
| 1.5–2 | 11,903 | −1.57% | −0.83% | −4.22% [−5.75, −2.68] |
| 2–3 | 42,867 | −1.32% | −0.56% | −5.23% [−6.31, −4.16] |
| 3–5 | 122,382 | −1.36% | −0.08% | −5.84% [−6.63, −5.05] |
| 5–8 | 156,922 | −3.00% | −1.22% | −7.61% [−8.56, −6.66] |
| 8–13 | 183,930 | −1.65% | +0.63% | −6.33% [−7.53, −5.13] |
| 13–21 | 170,040 | −3.74% | −1.82% | −8.90% [−10.57, −7.23] |
| 21–51 | 228,848 | −3.61% | −0.76% | −8.10% [−10.14, −6.05] |
| over 51 | 209,400 | −10.68% | −5.24% | −12.55% [−16.58, −8.51] |

Before commission the exchange is close to fair everywhere except the
longest prices; after it, every band loses, and the shortest band's interval
is the only one that reaches zero.

**The favourite at BSP, by year** (shortest scheduled-start back), gross then
net: 2020 +0.09% / −4.37%; 2021 −0.62% / −4.98%; 2022 +2.34% / −2.23%; 2023
−1.54% / −5.84%; 2024 +1.44% / −2.99%; 2025 −0.11% / −4.76%; 2026 +0.68% /
−4.12% (14,155 to 19,176 bets a year). Never positive net.

**BSP pays more than the scheduled-start back on the same runner**, by a
median of 0.0% at 1.0–1.5, 1.5% at 3–5, 2.9% at 8–13 and 8.6% over 51. Part
of that is the back-lay spread (the back is the worse side of it). So for any
rule decided at the scheduled start, **taking BSP beats taking the best back**
in every band; it is an execution choice, not an edge.

**Favourites by track size** (a track's mean matched volume per race the year
before, quartiles, 25,000 favourites each): gross −0.10%, +0.75%, −0.33%,
+0.89% from the smallest to the largest; net −4.39%, −4.06%, −4.71%, −3.66%.
The small tracks are not where the favourite is cheap.

**A back book under 100% at the scheduled start**, where backing every
runner in proportion would lock a profit: 818 of 115,296 races (0.7%),
median 0.99. The file carries no sizes, so whether those prices could be
filled is unknown; not graded.

### 4a. Place against win on the exchange

Harville from the scheduled-start win prices over-rates short horses for a
place exactly as in Hong Kong (said 0.846, placed 0.750 at 80–90%), and the
place BSP already prices that (1/place BSP 0.748 in the same band). Every
Harville band loses net, −0.58% at 90–100% to −13.0% below 10%; the Lo and
Bacon-Shone discount (exponent 0.76) moves the bands and not the result
(−0.07% [−0.84, +0.71] at 90–100%, every other band negative).

**A decidable place rule**: Harville calibrated on 2020–2022 (a logistic on
its log-odds, the field size and the number of places), times a place BSP
predicted from the same scheduled-start prices on the same years, graded on
2023–2026 at the place BSP, net. One input is not from the decision moment:
the number of places is read from the count of place winners, and only races
with 2 or 3 are kept, so a race with a dead heat for the last place drops
out. The place terms are set before the race, so this changes which races
are graded, not what the rule could know.

| Predicted EV | Bets | Units | Return [95%] | Years positive |
|---|---:|---:|---|---|
| > −0.05 | 299,304 | −7,768.7 | −3.10% [−3.37, −2.83] | 0 of 4 |
| > 0 | 80,041 | −1,181.5 | −1.78% [−2.33, −1.24] | 0 of 4 |
| > 0.02 | 38,112 | −309.1 | −3.97% [−5.30, −2.65] | 0 of 4 |
| > 0.05 | 16,673 | −160.3 | −9.36% [−12.20, −6.52] | 0 of 4 |
| > 0.10 | 3,979 | −29.9 | −9.38% [−17.13, −1.62] | 0 of 4 |

Gross, the best cut is −0.09% [−0.52, +0.33] (EV > 0.02, 184,685 bets). The
calibrated place chance holds on the graded years (within 1 point up to 70%;
1.8 points high at 70–80%, 3.3 at 80–90%, 3.4 above 90%). **Null: the
exchange's place market is priced consistently with its win market, and
commission is the whole loss.**

**By field size** (place terms step at field-size boundaries, so a boundary
field is where a generous place market would show): every field size from 4
to 15 runners loses net, −1.86% to −6.33% betting every runner and −0.95% to
−10.17% on runners with a calibrated place chance over 0.5. The two positive
cells are 3-runner fields (111 bets) and 16+ runners over 0.5 (508 bets,
+1.29% [−5.00, +7.58]).

### 4b. A logit on the scheduled-start prices alone

After Sung and Johnson (*Economica* 2010), who report abnormal returns from a
conditional logit on market prices. Inputs, all visible at the scheduled
start: the de-vigged back, the back-lay spread, and the back interacted with
the spread, the field size and the book. Fit on 2020–2023 one-winner races;
graded on 2024–2026. The bet is the race's best runner by EV at BSP, the EV
using a BSP predicted from the same snapshot (fit on 2020–2023), net.

| | Log loss 2024–26 |
|---|---:|
| The scheduled-start back | 1.7907 |
| The logit | 1.7906 |
| BSP | 1.7855 |

| EV cut | Bets | Units | Return [95%] | 2024 / 2025 / 2026 |
|---|---:|---:|---|---|
| > 0 | 35,674 | −814.7 | −3.99% [−5.29, −2.68] | −3.22% / −4.81% / −3.89% |
| > 0.02 | 30,444 | −746.3 | −3.97% [−5.33, −2.61] | −3.21% / −4.90% / −3.74% |
| > 0.05 | 23,374 | −635.6 | −3.89% [−5.35, −2.43] | −3.25% / −5.09% / −3.17% |
| > 0.10 | 14,476 | −472.2 | −3.73% [−5.39, −2.07] | −3.89% / −4.39% / −2.68% |

The snapshot's shape adds 0.0001 to the back price's log loss, and BSP is
0.005 better than both: what moves the price after the scheduled start is
not in the snapshot. **Null.**

## 5. Mechanisms, and the stuck ladder

The skill asks for three mechanisms of our own per market before a null, and
every rung of its stuck ladder. Several of the mechanisms below were named
after the baseline tables were on screen, so they are the search's record,
not pre-registered hypotheses.

**Win, Hong Kong pools.**
1. *Happy Valley's smaller night pools carry more longshot bias.* Venue
   split: runners over 20 lose −26.5% there and −26.9% at Sha Tin. Null.
2. *A runner fact the pool under-weights* (the draw at Happy Valley, a weight
   change, a layoff). Removing any one group moves the blend's
   log-likelihood by at most 0.0004. Null.
3. *The pool's own lean* (`c` above 1 every season, so the pool slightly
   under-rates favourites). Betting on the calibrated pool alone finds no
   runner with EV above 0 at any cut: the lean is far smaller than the take.
   Null.

**Place, Hong Kong pools.**
1. *The place pool is priced off a Harville-like reading of the win pool.*
   Calibrated rule, every cut negative (§3a). Null.
2. *Short horses are over-bet to place* (the Harville bias, inverted). The
   place pool already pays them less: the calibrated rule's bets lose most
   where Harville over-rates them. Null.
3. *The place pool at the 7-runner boundary* (3 places paid from 7 runners,
   2 below, so a 7-runner field is the most generous contract). Blind place
   bets at final place odds by field size: every size loses −16% to −26%;
   7 runners −19.0% [−24.7, −13.4] on 173 bets (`hk_study.py`, "by field
   size"). Hong Kong runs few small fields (most are 12 or 14). Null.

**Win, the exchange.**
1. *The favourite is cheap at small tracks*, where fewer informed bettors
   play. Null in every quartile of track size.
2. *A wide back-lay spread or an odd book marks a market the late money will
   move*, so a logit on the snapshot finds value. Log loss 1.7906 against the
   back's 1.7907; every cut −3.7% to −4.0% net, every graded year negative
   (§4b). Null.
3. *BSP drifts out from the scheduled-start back on longshots.* True (median
   +8.6% over 51), and it makes BSP the better way to take any bet decided at
   the scheduled start; it does not make a bet profitable.

**Place, the exchange.** Harville raw, discounted (Lo and Bacon-Shone), and
calibrated with a predicted place BSP; the field-size boundaries. All null.

**The ladder**, once for the league, because one constraint (no price before
the scheduled start, no form outside Hong Kong) binds every row:

| Rung | Done | What it returned |
|---|---|---|
| 1. Stop tuning | no cut was swept beyond an EV neighbourhood; no feature was added after a result | — |
| 2. Back to the mechanism | a pool is priced by the last money in, and the last money in US pools is the computer teams' (25–30% of handle) | a pre-off bettor competes with the best-informed money at the close |
| 3. Change the information | form held only for Hong Kong (null); Australia's form is Punting Form Starter ($59.00/Month as printed); a price path is behind a Betfair account | not bought: a decision |
| 4. Change the market or the moment | place against win (null twice); the scheduled start against BSP (an execution choice); exotics, each-way and fixed odds have no price held | parked with reasons in the grid |
| 5. Invert the question | the take sits evenly across Hong Kong's bands (−15% to −23%) and is worst on longshots; on the exchange the shortest band loses least | no cheap side |
| 6. Look outside, deeper | two scouts: 28 method leads, and every US outlet's price and pools | `docs/sports/racing.md` |
| 7. A read not anchored on ours | the advisor, before and after the work | |
| 8. Re-check the plumbing | the day-first file, the broken snapshots, the 99 cap, dead heats, the leak check | each fixed or measured; the leak check proves the harness sees an edge |

**What would have to change** is in `docs/sports/racing.md`.

## 6. What was not run in the first pass

The first pass (above) ran without a price path and without the UK/Ireland
set. Both were added the same evening (mike: *"lets use the free hong kong
history"*): §7 and §8. Still not run: anything on US racing (no free US
price), the National Hunt set, and exotic pools (no exotic dividends beyond
Hong Kong's 2016–2018 `all_dividends`).

## 7. Hong Kong pools before the off, 2016–2018

The free GitHub set `nch015/horserace_data` holds the HKJC win and place
pools sampled before every Hong Kong race from 2016-09-27 to 2018-06-27
(1,510 races, median 171 snapshots a race), the dividends, and results with
final odds back to 1979. Stored in Supabase (`horse_racing|nch015_horserace_data`,
6 rows, verified). This is the price a US bettor watches on a commingling
ADW's screen before betting the pool, so these are the first rules here that
are decided on a price the bettor could see and paid at the price they would
be paid.

**The clock** (`scripts/horse/hk_preoff_data.py`, `python -I` it to print
the checks). `capture_time` is UTC; `race_time` is the scheduled start in Hong
Kong time (UTC+8). The evidence: with +8 hours, the first snapshot showing the
final odds comes after the listed start in every one of 1,483 races (median
4.4 minutes after: the pools close when the race actually starts); no
snapshot before the start ever shows the final odds; no other whole-hour
offset fits; the monthly median does not drift over 21 months. Snapshots come
every 12 minutes until about 3½ hours out, then every 6 minutes to the off,
so each race has one snapshot in its last 6 minutes. **The latest decision
these files can test is about 5.6 minutes before the scheduled start**
(the median real lead of the "2-minute" frame); the "5-minute" and
"2-minute" frames use the same snapshot in 1,083 of 1,474 races.

**Grading.** 1,508 graded races, 18,474 starters. Win and place paid at the
dividend per HK$10 (decimal = dividend / 10); a winner's final pool share
times its dividend / 10 has a median of 0.8252 against 1 − takeout = 0.8250,
so the grading reproduces the 17.5% take. Dead heats are already split in the
dividend. A runner priced at the lead and scratched later is a refund, not a
bet.

### 7a. The pool before the off (`scripts/horse/hk_preoff_pool_study.py`)

**How much the late money knows.** Log loss of the winner per race, on the
1,406 single-winner races present at every lead:

| Moment | Log loss | Gap to the close (SE) |
|---|---:|---:|
| 30 minutes | 2.0926 | +0.0754 (0.0083) |
| 15 minutes | 2.0930 | +0.0758 (0.0087) |
| 10 minutes | 2.0879 | +0.0707 (0.0083) |
| 5 minutes | 2.0830 | +0.0658 (0.0078) |
| 2 minutes (real lead ~5.6) | 2.0806 | +0.0634 (0.0077) |
| the close (hindsight) | 2.0172 | — |
| uniform | 2.4979 | |

Of what the pool learns after 30 minutes out, 84% (0.0634 of 0.0754) arrives
after the last snapshot a bettor can act on. The pool is close to calibrated
at every lead (a one-parameter fit of share^β gives β 0.97 to 1.07); at the
close it shows a mild favourite-longshot lean (β 1.05 and 1.07).

**Blind win bets, decided at the lead, paid at the final dividend.** Every
runner loses −19.2% to −19.6% at every lead (about 18,100 bets and 2,350 to
2,430 units risked a lead), against −16.9% deciding on the final pool, which
no one can see. Every odds band loses at every lead; over 51 is worst
(−36% to −47%). The favourite loses −20.7% to −22.1%. A winner backed at the
screen price is paid a median 0.950 to 0.975 of it: 61.6% to 65.0% of runners
lose pool share between the lead and the close.

**Late money.** The change in pool share between two leads (30→15, 15→5,
10→2, 30→5, 15→2, 30→2), backed or faded, by size of move, by odds, and the
race's biggest steamer and drifter. The biggest steamer loses −12.9% to
−19.3%; the biggest drifter −7.4% to −20.5%, negative in at least one season
in every pair. 16 of 61 move cells beat their own season's odds-band control
in both seasons, which is about the rate chance gives, and none is positive
in both seasons.

**Win pool against place pool at the lead** (the "Dr Z" test on live
pools). Harville from the win pool at the lead, calibrated on 2016/17 (its
log-odds coefficient 0.83 to 0.91 confirms it over-rates short horses for a
place), against the place pool's odds at the same lead, graded on 2017/18 at
the final place dividend: every lead and every EV cut from −0.20 to +0.30
loses, −7.6% to −36.9% (the −7.6% is 52 bets, 33.9 units risked).

**Verdict.** 183 decidable bet sets were graded (111 on both seasons, plus
50 place sets on the out-of-sample season, plus the restored lead pairs). 6
have a positive return, all on small stakes; **none has its 95% interval
above zero, and none is positive in both seasons. Null.** Two lead pairs
(30→5, 15→2) were dropped from an early draft of the script after their
results were seen; a reviewer caught it, and they are restored in the
committed script, so the count above includes them.

### 7b. Benter against the pool before the off (`scripts/horse/hk_preoff_benter.py`)

Stage 1: a conditional logit on runner facts from earlier Hong Kong races
(form, rating and weights, draw, jockey and trainer rates, layoff, a speed
figure, the horse's own odds last time), fit on the ten seasons 2006/07 to
2015/16 (7,509 races). Stage 2: `softmax(b · log p_model + c · log p_pool)`
with the pool at the lead, fit on one season, graded on the other at the
final dividend. Fold A (fit 2016/17, graded 2017/18) is the forward test;
fold B reverses it and is a robustness row only.

| Pool / fold | Races | Pool | Stage 1 | Blend | Blend − pool (± SE) |
|---|---:|---:|---:|---:|---:|
| 10 min, A | 756 | −2.0904 | −2.2042 | −2.0871 | +0.0033 ± 0.0037 |
| 5 min, A | 755 | −2.0854 | −2.2054 | −2.0835 | +0.0019 ± 0.0031 |
| 2 min, A | 752 | −2.0787 | −2.2039 | −2.0776 | +0.0010 ± 0.0029 |
| final pool, A (hindsight) | 756 | −2.0095 | −2.2022 | −2.0072 | +0.0023 ± 0.0017 |

(log-likelihood of the winner per race, higher is better)

The model's weight against the pool at the lead is `b` = +0.14 to +0.21
(1.8 to 2.7 standard errors) in every fit: **the form model carries a little
information the pool 5–12 minutes out does not**. Out of sample that is worth
+0.001 to +0.003 nats a race, within one standard error, and against the
final pool `b` goes to zero or below: the late money absorbs it. The blend's
best-EV runners are longshots (median decision odds 49 to 200); the largest
bet set (10 minutes, fold A, EV > 0) lost 5.01 units on 13.59 risked over 331
bets, −36.8% (a race bootstrap gives −71.1% to +0.8%), and −70.7% at a flat
stake. **Null.** The leak check lit the same harness up (the race's own
finishing position: stage-1 log-likelihood −2.21 → −0.01, `b` +0.18 → +4.05,
756 of 756 bets won).

**What it means.** In Hong Kong's pools the last money in (after the final
bettable snapshot) holds what a fundamentals model knows, and a bettor paid at
the final dividend cannot get ahead of it from 5 minutes out. A model would
have to be decided seconds before the off, at the moment the large late
bettors act, which a retail bettor through a US ADW cannot do.

Both studies were rerun by two independent reviewers each (look-ahead; grading
and data). Every table reproduced byte for byte; one reviewer re-graded the
pool study from the raw files with its own parser and got the same results.
None found look-ahead. Their corrections to the wording are applied above.
