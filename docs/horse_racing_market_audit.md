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
| `horse_racing|nch015_horserace_data` (added the same evening, §7) | 6 (gzipped CSVs, stored as fetched) | 40.6 MB | 40.5 MB |
| `horse_racing|deltaromeo_uk_ireland_1988_2026` (added the same evening, §8) | 34 parts of the 1.12 GB zip | 1,120.7 MB | 1,120.9 MB |

(The last two rows: a read-only count on Supabase, 2026-11-16, grouped by
`source`.)

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

## 8. UK and Ireland at starting price, 1988–2026

The free Kaggle set `deltaromeo/horse-racing-results-ukireland-2015-2025`
holds three CSVs (1988–2004, 2005–2014, 2015-01-01 to 2026-10-23), stored in
Supabase as the downloaded zip (§1). The loader is
`scripts/horse/uk_sp_data.py`; running `python -I scripts/horse/uk_sp_data.py`
prints its checks.

**What the price is.** The starting price (SP) is the bookmakers' price at
the off. UK and Irish bookmakers settle bets at it, so a rule may be graded
at it, but it is a close: there is no earlier price in these files. A table
that chooses its bets on the SP, the order of the betting, the favourite's
price or the race's book (every runner's chance implied by its SP, added
up; the amount over 1.0 is the bookmakers' margin) has seen the close. It
is an upper bound or a description, not a bet.

**For a bettor in the US**, the outlets found sell UK and Irish races as
pools, and bet365 in Colorado and New Jersey sells fixed odds on them
(`docs/sports/racing.md`; the New Jersey launch rests on a search excerpt).
No option to bet at SP was found (`docs/horse_racing_scout_us_outlets.md`).
So a rule that cleared here would still be graded at a price a US user may
not be able to take.

**Data checks.** From the loader's printed output unless a bullet names
another source.

- **Rows.** 5,113,697 valid rows, matching the manifest; 732 exact duplicate
  rows dropped, leaving **5,112,965 runners in 506,076 races**. The
  1988–2004 file repeats its header 12 more times inside it; the SQLite
  copies keep those as data rows, so the loader reads the CSVs. 700 of the
  source's race numbers each label two to five different races, so a race
  is keyed on file, race number, date, course and off time.
- **Region.** From explicit course lists: 332,578 British races, 80,945
  Irish, 92,553 other. (The loader's notes record why: Irish courses carry
  no "(IRE)" suffix in either archive, nor again from 2025-10 to 2026-04.)
  727 foreign races written under British course names (Ascot in Perth,
  Sandown in Melbourne, Newcastle NSW, 496 races at South Africa's
  Newmarket) are moved to "other" by off time and by breeding. **There are
  no Irish rows in 2000, 2001 or 2002.**
- **Gradeable.** 409,872 of 413,523 British and Irish races. Left out:
  1,687 races (all 1988–2004) holding fewer rows than runners, races with
  no result, races where a runner has no SP, and two checks that a race's
  prices are valid (1,521 races whose book is under 1.0, and 120 more whose
  favourite marker is missing or not on the shortest price). Both studies
  also report their rules with those two groups put back.
- **SP strings.** 912 distinct strings over every region, 281 of them in
  British and Irish rows, each parsed once. A trailing F, J or C is the
  favourite marker (653 strings once it is removed). "Evens", "Evs" and
  "1/1" are 2.0, and "100/30" and "10/3" are 4.33. Only a bare "F" (10
  rows) does not parse. 5,314 British and Irish prices are not on the usual
  list of bookmaker fractions (the commonest are 16/5, 9/10 and 18/5):
  under 0.1% of prices a year to 2019, and 0.30% to 0.52% a year from 2020.
- **Results.** Dead heats are split (the share of the win sums to 1 in
  100.00% of races with a result). Results are the amended official ones
  (2,096 disqualifications in every region), which can differ from how bets
  were settled. There is no non-runner code: non-runners are simply not
  listed, so Rule 4 deductions (the cut UK books take from winning bets when
  a runner is withdrawn late) cannot be measured.
- **Rows are in finishing order** inside a race in 1988–2014: the first row
  won 99.7–99.8% of races (the fundamentals study's first table). That
  study picks one runner a race, so it shuffles the runners inside each race
  with a fixed seed before it builds anything, and prints the check. The
  structure study never uses row order to choose a horse: horses on equal
  prices or ratings share a rank, and the top-rated horse's margin uses only
  the rating numbers.
- **The source changes format on 2026-05-01**: no favourite marker and no
  Racing Post or Topspeed figures, and jockeys and trainers written as
  initials. Official ratings are still there: 99.8% of British and 100.0%
  of Irish handicaps May–Oct 2026 have every runner rated (the structure
  study's rating-coverage table). The loader links horses, jockeys and
  trainers across the change; 79.7% of British and Irish rows from that
  date link to a horse seen earlier.
- **The official rating is the mark going into the race.** Winners' marks
  had risen +0.3 to +0.8 lb going into a race, and rose +4.0 to +5.0 lb
  after it (measured by the structure study's look-ahead reviewer).

**Grading.** Win at SP, with dead-heat shares. Each-way at the standard
terms: 2–4 runners win only; 5–7 runners 2 places at 1/4; 8+ 3 places at
1/5; handicaps of 12–15 3 places at 1/4, of 16+ 4 places at 1/4. Books often
paid extra places, which is not modelled. Field size is the final field,
which is how bets settle; a rule meant for betting early would need the
declared field. Handicaps are detected from the race name, which misses a
few famous handicaps whose names lack the word. **The flat stake (1 unit
risked) is the figure a bettor at SP could get.** The repo's unit stake
(bet enough to win 1 unit) depends on the price, and at SP the price is not
known when the bet goes on. So a result that is positive only on units
relies on knowing the SP, and is not a bet.

### 8a. The starting price as a market (`scripts/horse/uk_sp_structure.py`)

Fit on 1988–2004 (training), graded on 2005–2014 and 2015–2026. A cell is
examined if it has 200+ bets on 1988–2004, and flagged if it is positive
there on either stake. A flagged cell clears only if, on 2005–2026, its
flat interval is above zero, its units return is positive, and its flat
return is positive in both 2005–2014 and 2015–2026.

**Calibration.** A/E is actual wins divided by the wins the price implies:
1.0 is fair, under 1 means over-bet. Power de-vig (raise each 1/SP to the
power that makes the race's book 1) removes most of the favourite-longshot
bias at short prices: A/E 0.998 to 1.023 for British runners up to 7/1.
Longshots stay over-bet, and less each decade (A/E at 50/1 to 100/1,
Britain: 0.40 in 1988–99, 0.60, 0.62, then 0.81 in 2020–26; Ireland 0.19 to
0.80). Irish books run far above British: median 1.356 against 1.186 in
1988–2004, 1.228 against 1.155 in 2015–2026.

**Blind win bets at SP** (flat stake):

| Bet | Britain 2005–2014 | Britain 2015–2026 | Ireland 2005–2014 | Ireland 2015–2026 |
|---|---:|---:|---:|---:|
| Every runner priced under 1/2 | −2.6% | −3.2% | −2.0% | −2.7% |
| Every runner priced 4/1 to 7/1 | −13.3% | −14.1% | −14.2% | −18.0% |
| Every runner priced 50/1 to 100/1 | −56.9% | −54.1% | −89.2% | −65.1% |
| The favourite (incl. joint) | −7.3% | −7.8% | −8.8% | −10.7% |

These rows choose their runners by SP, so they describe the market. The
rule "back every runner" lost −21.6% to −26.0% a year in Britain and
−30.7% to −39.9% a year in Ireland over 2011–2026.

**Rules that do not read the SP.** Blind win and each-way bets by race
type, handicap and field size; the official-rating rank; and the
top-rated horse's margin over the next. 143 such cells had 200+ bets on
1988–2004 and **one** was positive there: in British non-handicaps of 8–11
runners where the top-rated horse is clear by 6–11 lb, the second-rated
horse each-way, flat +7.0% on 231 bets. It lost on 2005–2026: 710 bets,
flat −10.0%, units −5.4% [−12.3, +1.5].

Chosen by looking at 2005–2026: of the 200 rule cells with 200+ bets there,
194 lost on both stakes, and 6 are positive on at least one:

- **British handicaps of 16+ runners, the place part** (4 places at 1/4):
  109,804 bets, +300.5 units, +0.9% [+0.6, +1.1] on units, but flat −0.0%,
  and −1.2% flat on 2015–2026; 7 of 22 years positive on flat.
- **British 8-runner non-handicaps, the place part**: 71,232 bets, +397.3
  units, +0.6% [+0.3, +1.0] on units, flat −3.2%; 6 of 22 years positive.
- Both are positive on units only, which relies on knowing the SP. At
  each-way terms the place part is sold only inside an each-way bet, and
  that loses on both shapes: flat −15.0% and −16.3%. Both place parts were
  −4.2% and −1.0% on units in 1988–2004.
- **Three small official-rating cells** (four bets, one cell graded both as
  a place part and each-way; 300 to 805 bets) are positive on flat over
  2005–2026. No rule cell has a flat interval above zero there. Each had 62
  to 189 bets in 1988–2004, too few to be examined, and three of the four
  lost 24% to 28% on units in those years.

**Upper bounds** (cells that choose on the SP). 40 cells clear, all of them
the place part of an each-way bet chosen on the SP. Most are a place model's
picks; nine are races with a short favourite. For example, in British
non-handicaps of 8–11 runners with a favourite under 1/2, the place part of
a bet on the second favourite made +25.4% [+21.3, +29.5] on units (+25.7%
flat) on 1,792 bets, and on the third favourite +31.5% flat on 1,761.
Backing the place part whenever the place model says it is worth more than
its price was positive in Britain in all 22 years from 2005. **The whole
each-way bet loses at a flat stake in every family where it was graded over
2005–2026** (the place model's picks and the short-favourite races; the
place model's by-shape cells were graded as place parts only), with one
exception: +0.9% when the place model's value is over 0.20 and the races
that failed the price checks are put back. Every one chose its runner on the
close. These describe how standard each-way terms misprice the place part,
most of all when the favourite is short. They are not a bet.

**How it was built.** The place model, the exact-field-size table and the
place-model value tables were shaped on five development runs over
2005–2012, inside the graded period. No development run touched
2015–2026, so 2015–2026 is the only clean half for those tables and for
the 8-runner cell. Five full runs (two by the reviewers) agree on every
table apart from the two whose layout was changed for the reviewers.

**Verdict: null.** No rule that can be decided before the off clears. Both
reviewers reran the whole script, with identical output, and one re-graded
straight from the loader's rows with its own SP parser and place rules (SPs
to 8.9e-16, each-way terms 0 disagreements). Their findings, all applied
above or flagged: the development-window note; field size is the final
field; units rely on knowing the SP; the 8-runner cell's positive years were
undercounted (6, not 5; the script now counts from unrounded returns); the
training-years grading has 29 races whose position numbering has a gap (a
horse with no placing between placed horses, or a dead heat whose next
place is not skipped) and 12 horses withdrawn under starter's orders in
1988–1994, neither of which touches 2005–2026; and handicaps detected by
name miss a few (re-detected from weight following rating, the 16+ cell is
unchanged).

### 8b. Fundamentals, then the starting price (`scripts/horse/uk_sp_fundamentals.py`)

**Stage 1** gives each horse a chance of winning from facts known before
the race, with a race's chances adding to 1 (a conditional logit), fitted
apart for the Flat and for jumps. It is walk-forward: each year is
predicted only from a fit on earlier years. The groups are official
rating, weight, age, draw, layoff, form, earlier-run figures (Racing Post
and Topspeed from the horse's last three runs), course and distance, and
the jockey's and trainer's records: their wins against what their horses'
field sizes would predict, over the previous two years, counting only races
that went off at least 30 minutes earlier. **Stage 2** mixes those chances
with the SP's, `softmax(b · log p_stage1 + c · log p_SP)`, with the weights
`b` and `c` fitted on the year before. The bet uses a stage 1 fitted on the
five years before (Y−5 to Y−1); the blend uses one fitted a year further
back (Y−6 to Y−2), so that `b` and `c` are fitted on predictions made out
of sample. Graded 1995–2026: 352,633 races. From 2026-05-01 the source has
no figures, so those races use a stage 1 fitted without them.

Two switches were added after a first full run showed 1998–1999 and
May–Oct 2026 collapsing: an input that is almost always empty in a fit's
years gets no weight, and races from 2026-05 use the model without
figures. Both are triggered by data coverage and the source's format, not
by results. The look-ahead reviewer found they moved the strictest cells
by at most 0.15 points and changed no verdict.

**What the model knows that SP does not** (log-likelihood of the winner per
race, higher is better; SP is the close, so this is an information test,
not a bet). Pseudo-R² is the share of the uncertainty explained, compared
with picking at random.

| | Races | SP calibrated | Stage 1 (Y−6 to Y−2, as the blend uses it) | Blend | Blend − SP (×1000, 95% CI) | Pseudo-R²: stage 1 / SP |
|---|---:|---:|---:|---:|---:|---:|
| Britain | 278,027 | −1.7991 | −1.9070 | −1.7955 | +3.60 [+3.25, +3.95] | 0.127 / 0.177 |
| Ireland | 64,956 | −1.9093 | −2.0657 | −1.9054 | +3.88 [+3.08, +4.69] | 0.146 / 0.211 |

Stage 1 alone is far weaker than SP. The blend's gain over SP has shrunk to
about nothing (×1000 a race): in Britain it was +5.8 to +13.0 a year in
1996–2004, and between −0.69 and +1.32 from 2015, with intervals spanning
zero in 2015–2017, 2020, 2022, 2023, 2025 and both parts of 2026. Since
2022 it has been within ±0.7 every year (2024's +0.16 has an interval just
above zero). The Flat weight on stage 1 fell from +0.19 to +0.33 in
1995–2003 to between −0.01 and +0.03 in 2021–2025. Ireland is the same
shape. **Removing one group at a time**: most of the gain (59% to 94% by
country and code) is the earlier-run figures, whose removal costs the blend
2.0 to 4.4 ×1000 a race; the jockey and trainer records carry 0.5 to 1.2;
removing form makes the British blend better (+0.48 and +0.72), so form is
already in the price.

**The bet a person could place**: back stage 1's top-rated runner at SP. It
never reads the SP to choose. `p` is stage 1's chance for its top-rated
runner, and `margin` is that minus the second-rated runner's chance.

| | Cut | Bets | Units | Return on units (95% CI) | Flat (95% CI) |
|---|---|---:|---:|---:|---:|
| Britain 2011–2026 | none | 154,784 | −3,858.9 | −4.28% [−4.93, −3.64] | −4.73% [−5.61, −3.86] |
| Britain 2011–2026 | p > 0.5, margin > 0.2 | 11,788 | −191.3 | −0.92% [−2.21, +0.36] | −0.11% [−1.73, +1.52] |
| Ireland 2011–2026 | none | 41,956 | −1,699.4 | −7.00% [−8.23, −5.78] | −10.19% [−11.90, −8.48] |
| Ireland 2011–2026 | p > 0.6 (Ireland's best late cut) | 1,574 | −7.0 | −0.23% [−3.39, +2.94] | −1.51% [−5.73, +2.72] |
| Britain 1995–2010 | p > 0.5, margin > 0.2 | 13,301 | +673.7 | +3.29% [+1.97, +4.61] | +6.93% [+5.23, +8.62] |
| Ireland 1995–2010 | p > 0.5, margin > 0.2 | 2,065 | +132.0 | +4.58% [+1.08, +8.08] | +5.12% [+0.43, +9.80] |

- **2011–2026: no cut clears.** Every one of the 24 cuts per country has
  its interval spanning zero or below, on both stakes, and every point
  estimate is negative. With the races that failed the price checks put
  back, Britain's p > 0.5, margin > 0.2 cell is −0.91% on units and +0.06%
  [−1.57, +1.69] flat.
- **1995–2010 is positive and is not taken.** Most of what the model knows
  beyond SP comes from the earlier-run figures, and nothing in these files
  shows whether a stored figure is the one published on the day or a later
  revision. The early bets were not re-graded without the figures. Backing
  the horse with the best earlier figure, with no model, was tried four
  ways, all printed, and made money in only one: in Britain 1995–2010, the
  best Racing Post figure of the last three runs made +1.09% [+0.30, +1.89]
  on units (flat +2.35%), and the other three lost (the latest Racing Post
  figure −1.38%, best Topspeed −5.25%, latest Topspeed −5.48%). A race is
  bet only when two runners have different earlier figures. In Ireland all
  four lost in both eras. In Britain 2011–2026 all four lost (−2.00% to
  −7.99%).
- **Splits chosen after looking.** Race type is known before the race, so
  it was split by era, with the late era also in halves; all 384 cells are
  printed. Of the 96 cells for 2011–2026, two have an interval above zero,
  and they are nearly the same bets: **Irish chases at p > 0.5**, 872 bets,
  +5.55% [+0.79, +10.32] on units (flat +6.91%), and at p > 0.5 with margin
  > 0.2, 838 bets, +76.1 units, +5.48% [+0.66, +10.31] (flat +6.47%
  [+0.32, +12.62]). It is a peak, not a plateau: at p > 0.4 it is +2.03% to
  +2.72% with intervals spanning zero, and at p > 0.6 +4.42% [−1.39,
  +10.23]. Each half alone spans zero (p > 0.5, margin > 0.2: 2011–2018
  +5.01% [−1.98, +12.00]; 2019–2026 +5.94% [−0.72, +12.60]), 1995–2010 was
  +1.07% [−6.63, +8.78], and British chases lose at every cut in 2011–2026.
  A separate split of British handicaps at p > 0.5, margin > 0.2 made
  +2.40% [−1.14, +5.93] on units (flat +3.79%) on 2,164 bets. **Neither is
  taken**: each is one of many cells looked at after the pooled results
  were seen.
- **Upper bound** (chooses on the SP): the blend's best value runner,
  where `p_blend × SP − 1 > 0`, made +3.42% on units in Britain over
  1995–2026 (+4.16% early, +1.63% late) and lost in Ireland (−2.42%).
- **Leak check.** Adding the race's own Racing Post figure, which is known
  only after the race, makes the same code show huge profits on 2010–2025,
  as a working leak test should: Britain's stage-1 log-likelihood goes
  from −1.8790 to −0.2793, and the top-rated runner from −4.01% to
  +193.83% on 156,054 bets.

**Reviewers.** Both reviewers reran the bet from the script, and one
re-graded all 352,633 picks with its own code (0 SP and 0 win-share
mismatches); every cell they reran matched. The leak check and the
remove-one-group table were compared with the saved output, not rerun.
Their corrections, applied above: the figure-based picks are printed as
four (the study had chosen one and reported it alone; the reviewer ran the
other three); the race-type split is printed whole; the flat stake is
negative at every cut only when Britain and Ireland are each taken whole
(it is positive for British handicaps and Irish chases). Also from them,
not changing the result: dropping the 201 picks graded as losers because
the horse was disqualified or has no placing moves any return by at most
0.12 points (this removes losers only, so it shows one direction, not a
bound); dropping picks at prices off the usual fractions leaves Britain
2011–2026 at −4.30% to −0.94%; from May 2026 the loader matches each
trainer's new short name to the old full name using the horses that
trainer runs in later months, which uses who trains which horse, not any
result; and each input is put on a common scale using its spread over all
years, which uses no results.

**Verdict for 8a and 8b: null.** No rule that can be decided before the
off clears on 2011–2026 in Britain or Ireland, at either stake. What a form
model knows beyond the starting price has been within ±0.7 per 1000 races
every year since 2022. The positives either choose on the close, come from
1995–2010 (not taken, because the figures' timing is unknown), or are
among many splits looked at after the results were seen. **What would
have to change**: a price before the off (these files hold none). The
model's information is small against the close and was larger earlier, so
a decision against an earlier price is the main test left. From the US,
the outlets found sell these races as pools, and bet365 in Colorado and
New Jersey sells fixed odds; no option to bet at SP was found.
