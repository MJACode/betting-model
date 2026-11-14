# UFC market audit, 2026-11-13

mike, 2026-11-13: *"Use the model building skill to build models for UFC.
Ignore and delete any existing models in the repo."* Built with
`/league-models` (`.claude/skills/league-models/`). This is the study; the
league doc (`docs/sports/ufc.md`) holds the grid and points here for every
number.

**Verdict.** One model clears and ships: `ufc_open_moneyline`, the fight
winner a week or more out, a rating model anchored on Pinnacle's no-vig price
and bet at the best price a pick may name (§3d). On the bought feed history,
2020-06 to 2026-06, decided as the live card decides: 846 bets, +136.9 units,
+12.85% [+8.0, +17.5], every year positive, EV against Pinnacle's closing
price +2.2%, a donor-opinion placebo at -1.9%. The three old models are
retired. Round totals and every method, distance and round market: nothing
clears (§4, §5).

How it got there: on a free archive the model beat the first posted price
(§3b), but that price is whichever book posts first; on our own 2026 store
DraftKings' first price did not look soft (§3c, 104 bets). The purchase
(§6) priced the books a pick may name on 2,457 fights and answered it.

Every table names the script that printed it. The scripts are in
`scripts/ufc_study/` and read a research cache built from mike's local
mirror plus the two free archives (`scripts/ufc_study/README.md`). Stakes
are the published stake: 1 unit to win, risk capped at 3. Intervals are 90%
bootstrap intervals on return.

## 1. What was deleted

`ufc_moneyline`, `ufc_total_rounds`, `ufc_method_of_victory` (built
2026-06-11, retrained 06-19) are in `config.RETIRED_MODELS`, with their
feature engine, scorer branch, trainer branch and artifacts removed. Why they
go rather than retrain: all three were graded on probability alone at a
synthetic -110, because no historical UFC price had ever been stored; and
method of victory had no market price at all. Their record, from `picks`
on 2026-11-13: moneyline 5 settled BETs (3-2) plus one void, round totals 14
(9-5), method 5 (3-2), none unsettled. One of those bets is in the published
record (`v_public_track_record`): round totals 1-0, +1.0 units (Mario Pinto
vs Ryan Spann Under 1.5, the 2026-09-05 card), carried in every all-time
line posted since. Retiring takes it out of every published total; mike
approved that in chat on 2026-11-13. Retiring alone left the bet in the record views and the Discord recap, which exclude only `config.RECORD_EXCLUSIONS`, so the three are struck there (`data/migrations/record_strikes_ufc_retired_2026_11_13.sql`). The three models' registry rows were
switched off in production the same day, on his instruction.

## 2. What the sources hold (measured 2026-11-13)

| Source | What it holds | Script |
|---|---|---|
| `odds` (our store) | 255,849 UFC rows, all 2026 (June onward), h2h and round totals, 12 books; 345 feed fights, 250 placed on a UFC result, 203 distinct | `odds_census.py`, `pilot_2026.py` |
| `ufc_fight_log` | 7,690 fights 2010-01-02 to 2026-11-07, method, round and time, per-fighter stats | `fights.py` |
| Odds feed, live, one fight of the 2026-11-14 card | fight winner: 7 books incl. Pinnacle; round totals: DraftKings, Pinnacle, Caesars, Bovada; a points spread (DraftKings and Bovada, Holland +7.5); alternate round totals: Pinnacle only. Rejected as invalid keys (HTTP 422): every method-of-victory, goes-the-distance, round-betting and exact-round spelling tried (16) | `feed_probe.py markets` |
| Odds feed, history | Nothing before 2020-06-06. 2020-07-10: DraftKings, FanDuel, Pinnacle; 2021-06-11: 7 books; 2023-06-09: 9 books. Round totals in the bulk history: Pinnacle from 2021, DraftKings by 2025-06. 20 credits per market per snapshot (two regions) | `feed_probe.py history` |
| Feed horizon | The feed lists fights months ahead; DraftKings had 2027-01-31 fights priced on 2026-11-13. Our ingest stores a fight when DraftKings first lists it (a 2026-12-12 fight was first stored 2026-10-04); every book's first stored row equals DraftKings' on all 345 fights, so the stored first DraftKings row is DraftKings' opener to within a pass | live events call, `odds_census.py` |
| fight-canon-db (free, MIT) | BestFightOdds opening price (the first book to post) and the lowest and highest closing price across books, UFC 2007-2026; 7,676 of our 7,690 fights joined, results agree on 98.9% | `scripts_ml_hist.py` |
| Ultimate UFC Dataset (free, CC BY 4.0) | One near-close price per fighter for the fight and for each method of victory, 7,177 fights 2010-2026, method prices from 2012 | `method_study.py` |

Both archives are stored in Supabase by `data/ingestors/ufc_price_archive.py`
(table `ufc_price_archive`, keyed on `source`): 65,450 rows on 2026-11-13,
16,276 BestFightOdds rows over 8,138 fights and 49,174 fight and method rows
over 6,955 fights, 14,210 of the 15,093 archive fights placed on our fight
ids; row security on, no grant to the app's public roles (read back after the
store).

## 3. Moneyline

### 3a. Baselines, 7,541 fights 2010-2026 (`ml_base.py`, `ml_blind_open.py`)

The market's own accuracy: log loss 0.6273 at the open, 0.6093 at the close.

| Blind bet | Bets | Return | 90% interval |
|---|---|---|---|
| Favourite at the open | 7,541 | -3.32% | [-4.5, -2.0] |
| Underdog at the open | 7,541 | -7.65% | [-10.0, -5.5] |
| Favourite, worst closing price | 7,541 | -3.87% | [-5.1, -2.7] |
| Favourite, best closing price | 7,541 | -0.80% | [-2.0, +0.4] |
| Underdog, worst closing price | 7,541 | -8.30% | [-10.6, -5.9] |
| Underdog, best closing price | 7,541 | -2.32% | [-4.7, +0.2] |

A favourite-longshot bias, measured at the middle of the closing range:
favourites shorter than -400 returned +0.96% (1,121 bets), underdogs longer
than +250 lost -16.7% (1,361) and -21.4% (614). Nothing blind is profitable
at a price we could take.

### 3b. The market-anchored rating model (`ml_anchor.py`)

`logit P = logit(no-vig market) + b·z`, the market an unpenalised offset, `z`
the fighter-minus-fighter differences built strictly before the fight (an
Elo rating, experience, layoff, win, finish and decision rates, strike and
takedown rates per 15 minutes, age, reach, height, streak, debut), `b`
ridge-penalised. Walk-forward: each year fitted only on the years before it,
2014-2026, 6,276 fights. The pick is the side with the larger EV; -300
floor.

**Decided at the close** (graded at the worst closing price): the model
moves log loss from 0.60974 to 0.60804-0.60896 and finds nothing that
holds. Best cell: EV >= 0.10, ridge 1, 598 bets +7.50% [0.0, +15.0], early
+14.0% and late +1.4%, 8 of 13 years positive; at ridge 30 the same cut is
402 bets +6.10% [-3.4, +15.5] with the late half negative. Not a plateau.

**Decided at the open** (graded at the open price), ridge 30:

| Cut | Bets | Return | 90% interval | Early / late | Years positive | EV against the no-vig close |
|---|---|---|---|---|---|---|
| EV >= 0.00 | 3,377 | +3.89% | [+1.5, +6.4] | +3.3 / +4.5 | 9/13 | +0.24% |
| EV >= 0.03 | 2,334 | +4.89% | [+1.9, +7.9] | +3.1 / +6.6 | 11/13 | +1.12% |
| EV >= 0.06 | 1,531 | +7.82% | [+3.9, +11.8] | +5.2 / +10.2 | 11/13 | +1.88% |
| EV >= 0.10 | 826 | +16.63% | [+11.6, +22.1] | +14.4 / +18.5 | 12/13 | +3.49% |

Ridge 1 and ridge 300 tell the same story (ridge 1, EV >= 0.06: 1,845 bets
+6.12% [+2.6, +9.6]). The bets beat the middle of the closing range 60-62%
of the time, and their EV against the no-vig close is positive at every cut
(`ml_open_clv.py`), negative in 2014-2017 and positive in every year from
2018 to 2026. A placebo that keeps each year's coefficients but gives every
fight a donor fight's model opinion (50 permutations within the year,
`ml_open_placebo.py`) returns a median -6.54% and at best -2.39%, against
the real +7.82%. Read: **the open is a first guess, and the ratings know
which way it will be corrected.** It is a finding about line movement.

### 3c. It is not yet a bet: DraftKings' own opener (`ml_open_2026.py`, `ml_shop_2026.py`)

The model frozen on every fight through 2025, scored on the 193 fights of
2026 that a US book priced, at each book's FIRST stored quote (DraftKings:
a median 178 hours before the fight), anchored on that book's own no-vig
price:

| Book | Cut | Bets | Return | 90% interval | EV against Pinnacle's close |
|---|---|---|---|---|---|
| DraftKings | EV >= 0.00 | 104 | +9.5% | [-4, +23] | -2.5% |
| DraftKings | EV >= 0.06 | 48 | +25.7% | [+5, +48] | -2.1% |
| FanDuel, BetMGM, Caesars, BetRivers, Hard Rock | any cut | 13-59 | +8 to +79% | | -1.0% to -5.9% |

The same model on BestFightOdds' 2026 opens: EV >= 0.06, 123 bets +13.8%,
EV against the close +9.5%. So **the 2026 open was soft where BestFightOdds
saw it and was not soft at DraftKings**. Positive results with negative
closing-line value are the pattern `kill-tests.md` calls luck; nothing here
is presented as an edge.

The executable shape, anchored on Pinnacle at the first pull where Pinnacle
and a US book are both quoted (within five minutes) and bet at the best US
price, first qualifying pull locks: EV >= 0.00 63 bets +10.5% [-7, +29] at
-0.67% against Pinnacle's close; EV >= 0.06 36 bets +31.1% at +1.14%. Too few
fights to say anything. Two traps found on the way: the same rule with the
model removed showed "+24% to +129%" EV against the close at a lead of 0-1
hours, which is stale and in-play quotes leaking into the window (any card
decides at a fixed lead, on fresh quotes only); and every book's first stored
row equals DraftKings' because our ingest only stores a fight once DraftKings
lists it, so another book's true opener is not in our store.

The purchase answered it (§3d): on 2,457 fights the same model at the
deciding books' prices is positive in every year, and the 2026 store's 104
bets were too few to say otherwise.

### 3d. The bought history: the model at prices a pick may name (`feed_quotes.py`, `feed_open.py`, `feed_kill.py`, `card_replay.py`)

The purchase (§6) gives every book's price at noon UTC each day, and six
times on each card day, for 2,457 UFC fights from 2020-06 to 2026-06. The
rating model is fitted walk-forward exactly as in §3b (on the archive's
opens, each year only on the years before it) and applied unchanged.

**Each book's own first daily price** (anchored on itself, at least an hour
out, EV >= 0.06): DraftKings 632 bets +13.42% [+7.8, +18.7], FanDuel 531
+10.84%, BetMGM 494 +14.23%, Caesars 547 +12.63%, BetRivers 415 +10.64%,
every year positive at each. Their first daily price came a median 10.6 to
12.6 days before the fight.

**The rule that ships: Pinnacle-anchored, best deciding price in the same
pull.** At a pull where Pinnacle and a deciding book both quote the fight:
the model's probability from Pinnacle's no-vig price, each book's better
side by EV, prices shorter than -300 removed, the best EV across books bet
when it clears; the first pull that clears locks the fight. Decided only on
the noon pulls (the live card decides on its noon-UTC run, so it gets no
more chances to fire than the backtest had), and only a week or more before
the fight:

| EV cut | Bets | Units | Return | 90% interval | Early / late | Years positive | EV vs Pinnacle's close |
|---|---|---|---|---|---|---|---|
| 0.03 | 1,199 | +121.1 | +7.56% | +3.5 to +11.6 | +7.6 / +7.5 | 5/7 | +1.22% |
| **0.06** | **846** | **+136.9** | **+12.85%** | **+8.0 to +17.5** | **+11.4 / +14.3** | **7/7** | **+2.16%** |
| 0.10 | 484 | +105.4 | +19.61% | +13.4 to +26.1 | +16.9 / +22.5 | 7/7 | +4.25% |

The whole neighbourhood from EV 0.00 to 0.15 is positive with its interval
above zero (`feed_kill.py 168`). By year at 0.06, noon pulls: 2020 +0.6%
(67 bets), 2021 +19.3% (147), 2022 +6.5% (170), 2023 +13.4% (153), 2024
+16.7% (138), 2025 +15.1% (130), 2026 to June +15.3% (41). "Pinnacle's close" is its last quote before the start, from
the card-day pull five minutes before the fight.

**How far out.** The edge lives in early prices: locked 7-14 days out
+7.4%, 14-30 days +19.6%; inside a week it was negative (-6% to -10% in the
one-hour version). The minimum lead is a plateau, not a peak (EV >= 0.06,
daily pulls): 3 days 1,088 bets +8.98%, 5 days 985 +11.04%, 7 days 846
+12.85%, 10 days 668 +15.26%, 14 days 369 +18.27%, each interval above zero
and each placebo's best below its result. 7 days is the middle of it.

**Kill tests on the shipped version** (`feed_kill.py 168`):
- Placebo: each fight given a donor fight's opinion within its year, 50
  times: median -1.94%, best +3.88%, against the real +12.16% (all pulls).
- Without the ten best dates: +8.31%.
- Sides: 47% underdogs. Books named: DraftKings 236, FanDuel 219, Caesars
  174, BetMGM 148, BetRivers 95.
- Price bands: positive from -300 to +250 (+7% to +27%); +250 and longer
  lost (49 bets, -7% and -15%).
- Debuts: 71 of the 846 bets have a fighter making his UFC debut, whom the
  live card cannot place on a ufcstats record and skips; without them 775
  bets +13.21% (`feed_debut.py`).
- The card's own code (`card_replay.py`): the production ratings, build and
  decision reproduce the research's 846 bets fight for fight, side, pull and
  price, opinions equal to 2.6e-12; 49 had two books at the same best price
  and named a different one of them (the card now breaks a tie in the
  deciding-book order, DraftKings first).
- Fights that never happen (`non_ufc_events.py`): 474 events Pinnacle and a
  deciding book priced a week out, both fighters on ufcstats, were not
  fought on the card they were listed for (cancelled or moved bouts); 472
  sat within a day of a logged UFC card. A bet on one is refunded by the
  book; the settlement now writes NO_ACTION once the card is logged without
  either fighter, so it cannot hold the daily record. The other two carried
  the feed's placeholder date for an unscheduled fight (December 31), which
  the card skips; no UFC fight of the history was listed on that date or
  January 1.
- The live path can meet it: our store keeps a Pinnacle quote every pull
  (about every ten minutes, 2026-11-13) on most fights since 2026-09
  (Pinnacle on 78 of 102 October fights; before August our store kept
  DraftKings only).

**Price range of the shipped rule:** median -108, shortest -300 (risk 3
units to win 1), 16.5% shorter than -200; 7 bets at +400 or longer.
**Expected volume:** about 140 bets a year, two or three a card, decided on
the noon run 7 to 30 days before the card.

## 4. Round totals (`totals_search.py`; the 2026 pilot `totals_model.py`)

**Verdict: does not clear.** No rule decided at a fixed time beats
DraftKings' margin on the bought history. One lead survives as a forward
test (§4f, rung 4), and it is written down before it is watched.

**Corrected 2026-11-13.** This section said the bought history holds
DraftKings' totals only from 2025, and that DraftKings against Pinnacle at
the same line in the same pull gave 22 bets. Measured: DraftKings carries
totals on 31 fights in 2023, 417 in 2024, 430 in 2025 and 194 in 2026
(1,058 fights at the lines bet here); Pinnacle on 2,384 fights from 2020;
no other book a pick may name carries totals in the history. The 22 was a
count of bets, not of comparable pulls (there are 8,090).

**Fixed before looking.** Decided on the noon pull (served 11:55 UTC; the
live card decides at 12:00), at least an hour out; the first pull that
clears locks the fight; graded at DraftKings' own price at the same line in
the same pull as the Pinnacle quote it is compared with. Lines bet: 1.5, 2.5,
4.5 (0.5 and 3.5 have under 50 fights). Closing-line value is against
Pinnacle's last pre-fight no-vig price at that line, and §4f rung 5 shows
that witness is biased on totals. The 2026 pilot that stood here (187
fights of our own store, `totals_model.py`) is superseded by these 2,384;
its stat-only finish model, with no price as anchor, read log loss 0.684
against the price's 0.649.

### 4a. The bar: DraftKings' margin

| | Pinnacle | DraftKings |
|---|---|---|
| Margin (sum of implied probabilities − 1), every pull | 4.1% at each line | 6.2% at each line |
| Pulls with both at one line | 8,090 on 1,049 fights | |
| DraftKings priced above Pinnacle's no-vig on either side | 43 pulls (15 of them noon pulls) | |
| Median DraftKings EV at Pinnacle's fair price, better side | −5.22% | |
| Betting those pulls | noon: 14 bets −19.4%; card day: 20 bets −5.2% | |

A model that only matches Pinnacle loses about 5% at DraftKings. To bet a
total there it has to know about 5 points more than Pinnacle does.

### 4b. Is the data right: how often the over won against the price

Last pull at each line, Pinnacle. Settled on time: over 2.5 wins once the
fight passes 2:30 of round 3; a fight ending exactly on the line is dropped;
4.5 is posted only on five-round fights.

| Line | Fights | Over won | Pinnacle no-vig over |
|---|---|---|---|
| 1.5 | 697 | 50.6% | 52.1% |
| 2.5 | 1,594 | 60.4% | 57.9% |
| 3.5 | 46 | 52.2% | 52.3% |
| 4.5 | 127 | 63.0% | 54.9% |

At 2.5 the over beat its no-vig price in five of seven years (2022 and 2025
level). That gap is where the margin sits, not an edge: Pinnacle's blind over
at 2.5 returned +0.1%, its blind under −9.6%. Splitting the margin
proportionally between the two sides understates the over.

### 4c. Blind sides, last pull (CLV omitted: for a blind side it is only that side's margin)

| Book, line | Over | Under |
|---|---|---|
| Pinnacle 1.5 (697) | −6.8% [−12.4, −1.1] | −0.8% [−6.6, +5.1] |
| Pinnacle 2.5 (1,594) | +0.1% [−3.1, +3.2], 3/7 years | −9.6% [−14.0, −5.2], 0/7 |
| Pinnacle 4.5 (127) | +11.0% [−0.9, +22.6], 6/7 years | −18.8% [−33.5, −4.1] |
| DraftKings 1.5 (362) | −10.6% [−17.8, −2.8] | −3.9% [−12.2, +3.9] |
| DraftKings 2.5 (675) | −0.9% [−5.7, +3.6], 2/4 | −16.1% [−22.8, −9.1], 0/4 |
| DraftKings 4.5 (53) | +8.5% [−8.1, +24.3], 3/4, late half −4.4% | −21.3% [−44.8, +2.3] |

First pulls read the same within a point or two. The cheap side is the
over at 2.5 and 4.5 and the under at 1.5; only the 4.5 over is positive, on
127 fights.

### 4d. The Pinnacle-anchored finish model, walk-forward by year

logit P(over) = logit(Pinnacle no-vig over, same pull) + intercept for the
line + b·z, ridge 30, each test year (2022-2026) fitted on the years before
it. z: both fighters' finish, decision, knockout-loss, knockdown,
submission, takedown and strike rates and average fight time, gender, five
rounds, weight class, and the moneyline mismatch from the same Pinnacle
pull. Three nested models, log loss on the same 9,110 noon Pinnacle pulls:

| | All | 1.5 | 2.5 | 4.5 |
|---|---|---|---|---|
| (a) Pinnacle no-vig | 0.65545 | 0.66794 | 0.65054 | 0.64769 |
| (b) + one intercept per line | 0.65541 | 0.67149 | 0.64929 | 0.64331 |
| (c) + fighter and bout inputs | 0.66081 | 0.67481 | 0.65650 | 0.63988 |

The intercepts are stable across fits (1.5: −0.15 to +0.03; 2.5: +0.09 to
+0.14; 4.5: +0.29 to +0.43, in log-odds). Fighter inputs make the price
worse at 1.5 and 2.5; at 4.5 they help on noon pulls and not on the last
pull per fight (0.63519 against (b)'s 0.62726).

At DraftKings, first clearing noon pull, either side:

| Model, EV cut | Bets | Units | Return [90%] | CLV | Early / late | Years + |
|---|---|---|---|---|---|---|
| (b) 0.00 | 241 | +11.4 | +3.65% [−5.7, +13.4] | −4.17% | +6.5% / +0.0% | 3/4 |
| (b) 0.02 | 83 | +4.7 | +4.14% [−11.1, +19.3] | −4.39% | +12.8% / −6.5% | 2/4 |
| (b) 0.04 | 49 | +0.8 | +0.99% [−18.4, +19.5] | −5.76% | +20.8% / −18.4% | 2/4 |
| (b) 0.06 | 40 | −4.9 | −8.15% [−30.9, +14.0] | −5.53% | | 1/3 |
| (b) 0.10 | 19 | −0.6 | −2.55% | | | |
| (c) 0.00 | 552 | −26.2 | −3.20% [−9.2, +2.7] | −5.26% | −5.3% / −1.2% | 2/4 |
| (c) 0.04 | 304 | −23.3 | −5.34% [−12.9, +2.7] | −5.32% | −7.4% / −3.4% | 2/4 |
| (c) 0.06 | 222 | −22.4 | −7.24% [−16.8, +1.9] | −5.67% | | 1/4 |
| (c) 0.08 | 142 | −27.3 | −13.66% [−25.6, −1.5] | −5.50% | | 1/4 |
| (c) 0.10 | 103 | −20.7 | −15.54% [−30.2, −1.0] | −5.31% | | 1/4 |

- **The return falls as the cut rises**, for both models: the opposite of
  an edge. (b)'s bets are overs (229 of 241 at 0.00; at 0.04, 45 of 49 are
  the 4.5 over).
- **(c) split at 0.04**: 1.5 −6.4% (89), 2.5 −5.1% (181), 4.5 −4.5% (34);
  five rounds −6.7% (56), three −5.0% (248); overs −6.5% (203), unders
  −1.8% (101); locked 3-7 days out −7.8% (217), 1-3 days +0.8% (67).
- **Placebo**, each fight's inputs taken from another fight of the same year,
  the pull's own line and moneyline kept, 50 draws: real −5.34% against a
  placebo median of −5.30% (95th percentile +1.48%). The fighter inputs
  carry nothing another fight's would not.
- **Penalty**: ridge 3, 406 bets −3.31%; ridge 300, 114 bets −7.30%.
- **At Pinnacle's own price** (not bettable, to see the model without
  DraftKings' margin): (b) 202 bets −1.39%; (c) 832 bets −2.64%, no year
  positive.
- The first version of this model had no free intercept, so it could not
  correct the bias in §4b and bet mostly unders: 293 bets −8.83% at 0.04.
  The intercept was added before any number above was read.

**The 4.5 over as its own rule** (the line-4.5 intercept from earlier years
only, over side only, DraftKings): 47 bets +5.12% [−13.5, +23.2], 3/4 years,
early half +24.4%, late half −15.6%. At that return the interval clears zero
at about 606 bets; DraftKings posts about 20 of these a year (53 in the
history). At Pinnacle's own price: 95 bets +7.2% [−5.4, +20.2], 4/5 years.

### 4e. Mechanisms of this study's own

Each was written with its prediction before it ran.

| Mechanism and prediction | Result | Status |
|---|---|---|
| **M1. DraftKings leaves its total stale when its moneyline moves.** When DraftKings' favourite gets 3+ points more likely and its total (line and both prices) is unchanged from its previous pull, the under is under-priced; the reverse for the over. | 85 such pulls. At a 3-point move: 80 bets −4.98% [−20.7, +11.3], unders −15.0%. At 2 points: 242 bets −13.66% [−22.8, −4.5], unders −28.9%. | **Wrong in direction.** Dead. |
| **M2. Women's and flyweight bouts go the distance more than priced** (heavyweight the control, expected to finish). Overs beat their price in those divisions at both books. | Women: Pinnacle +1.84% [−3.7, +6.9] (394), DraftKings −0.96% (168). Men's flyweight: −8.40% (153) and −1.71% (77). Heavyweight over: +0.29% and +9.15% [−7.3, +24.8] (77), the opposite of the control's prediction. | **Dead.** |
| **M3. Five-round main events: the public bets the finish.** Overs in five-round fights beat their price. | Pinnacle 245 +1.07% [−8.3, +9.4], 4/7 years; DraftKings 104 −0.14%. | **Dead** outside the 4.5 line, which is the 4.5 rule above. |
| **M4 (ladder rung 3). Short-notice bouts finish more than priced.** A fight first listed in the feed under 7 days out (about 10% of fights) is a late replacement; the under beats its price. | Under: Pinnacle 271 −6.29%, DraftKings 94 −0.77% [−16.5, +15.0]; DraftKings' over −13.55%. | **Dead** on totals. The fight-winner version (§9) is not run. |

### 4f. The stuck ladder

1. **Stop tuning.** One cut grid per model, three penalties, no feature
   search.
2. **Back to the mechanism.** Totals go up about 4.5 days before the fight
   (median first quote, both books), after the moneyline. Pinnacle sets
   them; DraftKings sits about 2 points of margin wider. The margin sits on
   the under at 2.5 and the over at 1.5: the bettor who loses most is the
   one backing a finish in rounds two or three.
3. **Change the information.** Notice length from the feed (M4): dead.
   Missed weight and camp news are in no store; not tried.
4. **Change the moment.** First pull against last, lead bands, and the
   card-day pulls (six on fight day, median 5.5 hours out) in place of noon.
   **The card-day pulls are the one lead.** Model (b), DraftKings, card-day
   pulls:

   | Cut | Bets | Units | Return [90%] | CLV | Early / late | Years + |
   |---|---|---|---|---|---|---|
   | 0.00 | 228 | +21.3 | +6.92% [−2.5, +15.9] | −4.45% | +5.2% / +8.7% | 3/4 |
   | 0.02 | 79 | +8.9 | +7.48% [−6.9, +20.8] | −4.82% | +5.7% / +9.4% | 3/4 |
   | 0.04 | 51 | +5.2 | +6.54% [−12.8, +24.1] | −5.52% | +6.0% / +7.1% | 3/4 |

   By line: 2.5 over 164 bets +7.30% [−3.9, +18.0], every year positive; 4.5
   over 49 bets +8.07%. Against it: 2025, its biggest year (143 bets),
   returned −2.97%; with the three best card dates removed it is +3.21%
   [−6.7, +13.0] with a late half of −0.5%; closing value is −4.4%; and it
   is the second decision time tried, after the one fixed in advance
   failed. It does not clear. At its return the interval clears zero at
   about 400 bets, roughly two more years of cards.
   Another market: alternate totals are Pinnacle only. Another book: none
   a pick may name carries totals in the history.
5. **Invert the question.** The hindsight ceiling: DraftKings' noon price
   was above Pinnacle's own close on 1,417 of 5,055 pulls (502 fights).
   Betting the first such pull of each fight: 502 bets −2.82% [−10.1, +4.5],
   overs +0.0%, unders −7.2%. Knowing Pinnacle's close in advance does not
   pay at DraftKings, because the proportional no-vig close overstates the
   under (§4b). **So closing value against Pinnacle's no-vig close is a
   biased witness on totals**: it charges every over about 2.5 points at
   the 2.5 line. The CLV column above carries that bias.
6. **Look outside.** Web search, 2026-11-13: no published test of UFC
   round totals. Stanhope's 2021 poster finds round and method odds
   miscalibrated (§5's market); Miller and Nichols (2026) find the fight
   winner efficient at the close.
7. **A read not anchored on this one.** The advisor review found the
   missing intercept in §4d; fixed before the tables were read.
8. **Re-check the plumbing.** Settlement as in §4b; DraftKings' own price
   at the same line in the same pull; lines that are not totals (215, 250,
   450) and prices inside ±100 dropped.

**What would have to change.** One of: (1) a second book a pick may name,
with a smaller margin than DraftKings', posting totals (DraftKings' price
sits a median 5.2 points under Pinnacle's fair one; a Pinnacle-sized margin
would cost about 2); (2) the card-day over, decided at
fight-day pulls, holding on about 170 more bets forward, written now as a
frontier test so the forward record is not chosen after the fact; (3) about
600 bets of the 4.5 over, which DraftKings offers about 20 times a year.

## 5. Method of victory, goes the distance, round betting (`method_study.py`)

No live price: the odds feed rejects every key for these markets. The free
archive's near-close method prices, 2012-2026:

| Blind bet | Bets | Return | 90% interval | Years positive |
|---|---|---|---|---|
| Favourite by decision | 5,821 | -3.29% | [-6.1, -0.5] | 4/15 |
| Favourite by KO/TKO | 5,590 | -19.91% | [-23.0, -16.6] | 1/15 |
| Favourite by submission | 5,590 | -24.51% | [-28.7, -20.2] | 1/15 |
| Underdog by decision | 5,805 | -13.78% | [-17.9, -9.8] | 2/15 |
| Underdog by KO/TKO | 5,579 | -21.95% | [-26.5, -17.1] | 1/15 |
| Underdog by submission | 5,578 | -41.38% | [-46.8, -36.1] | 0/15 |

The published lead (favourite by decision is under-priced) is right in
direction: it is the cheapest method price by far. It is not a profit, and
the market carries 20-40% margin on finishes. Parked until a live price
exists.

## 6. The purchase (mike, 2026-11-13: "yes")

`data/ingestors/ufc_odds_history.py`: fight winner and round totals from the
odds feed, 2020-06-06 to 2026-06-13, one pull a day at 12:00 UTC (2,199) and
six on each card day timed off its fights' start times (1,557), 40 credits a
pull, quoted 150,360. **Spent 150,240** (a two-day trial of 80, then 87,880
and 62,280; every answer billed as quoted, none failed); the balance read
4,110,531 after it. Stored in `ufc_odds_history` (552,576 rows, change-only,
every promotion, UFC fights placed on our fight ids) with one ledger row per
pull in `ufc_odds_history_pulls` (3,755: one card-day ask fell on a daily
noon); both read back, and the copy on mike's PC holds the same counts. The
spool in `betting_local_copies\ufc_odds_history_2026_11_13` is a cache of
the table.

## 7. Kill tests run

- Look-ahead: the first blind open table defined the favourite by the
  closing price; redone at the open (§3a).
- Walk-forward by year, early/late halves, three penalties: §3b.
- Placebo (donor opinions, 50 permutations): §3b, passed at the open.
- Closing-line value as the second witness: it is what separates §3b
  (positive) from §3c (negative).
- The executable book: §3c on 2026 (104 bets, failed); §3d on the bought
  history (2,457 fights, passed).
- The live cadence: §3d decides on noon pulls only, as the card does.
- The lead neighbourhood and its placebo: §3d.
- The card's own code against the research, bet for bet: §3d.
- Fresh quotes and a fixed lead: §3c, the 0-1 hour artefact.
- Market alone as the control row: the blind tables and the market-only
  rule in §3c.
- The market's own log loss against the model's: §3b (close), §4d.
- Round totals: walk-forward by year, three nested models, the cut
  neighbourhood, side and line splits, early/late, a donor placebo, best
  card dates removed, the hindsight ceiling, a second decision time: §4.

## 8. Leads from outside the repo

Scouted 2026-11-13 (web, GitHub, papers; no paid calls).

| Lead | Source | Claim | Status |
|---|---|---|---|
| The closing moneyline is efficient | Miller & Nichols, J. Econ. Finance 2026 (doi:10.1007/s12197-026-09757-x); Lam 2025 HEC thesis; Robbins 2023 | No broad bias at the close; calibration error 0.015 | **Agrees** with §3a and §3b at the close |
| The opening line is soft | github.com/SolvAI/ufcash (self-reported, 226 held-out bets +24.1%) | A stats model beats the BestFightOdds open | **Reproduced** on our data (§3b); **fails** at DraftKings' opener on 2026 (§3c) |
| Big line moves are under-reacted to, even at the close | ufcalendar.com 14-year study (a vendor; win rates, no prices) | Steamed side wins more than its close implies | **Dead** at the worst closing price (`ml_steam.py`): the side the line moved toward loses in every band of move size, -0.32% (590 bets, 10-15 points) to -8.91% (314, 15+ points) |
| Favourite by decision is under-priced | Stanhope 2021 (UCSAS poster, SSRN 3906072) | Miscalibrated, p = 0.0028 | **Tested** (§5): least over-priced, not profitable, no live price |
| Short-notice replacements, missed weight | agentmma, Fightful (win rates only) | Replacements win 37-42% | **Totals: dead** (§4e, M4: fights first listed under 7 days out); fight winner still queued |
| Totals, goes the distance, round betting | nothing found (searched again 2026-11-13) | No public test | §4 is the first test: nothing clears |

Data sources found: fight-canon-db and the Ultimate UFC Dataset (stored);
nlbair/ufc-data (CC BY 4.0, BestFightOdds open and close range plus judges'
scorecards; not imported, it duplicates fight-canon-db's prices).
BestFightOdds' robots.txt allows everything but `/cnadm/`; its pages carry
per-book history for totals and props, a route not yet tried. OddsPortal
disallows its dated archive; Tapology disallows Claude's crawlers by name.

## 9. Inventions, and the frontier

Three mechanisms of this session's own, each with the experiment that would
kill it:

1. **Notice length from the feed.** A pairing's first appearance in the odds
   feed dates the booking. Prediction: fights booked inside 14 days close
   further from their open than others, and the side the ratings favour
   wins more than the close says. Experiment: the purchase's daily pulls
   give the first-listed date for every fight since 2020.
2. **DraftKings re-hangs its total off its moneyline.** Prediction: when
   DraftKings' moneyline moves and its total does not move within the same
   pull, the total is stale in the direction the moneyline went (a bigger
   favourite finishes more). **Run on the purchase, and wrong in
   direction** (§4e, M1): after a 2-point move the stale under lost
   28.9% (129 bets).
3. **Five rounds favour the better fighter, and the price ignores it.**
   Prediction: in five-round fights the favourite beats its price.
   **Run, and wrong in direction** (`ml_five_rounds.py`, `ml_five_dog.py`):
   the five-round favourite returned -7.66% at the middle of the closing
   range (702 fights) against -1.77% in three-round fights; the five-round
   underdog +5.71% [-2.5, +14.0] there. At the worst closing price the
   underdog is +2.07% [-5.8, +10.3], early half +10.5%, late half -5.0%,
   10 of 17 years positive, all of it from +100 to +250 (+250 and longer
   lost 24-33%). It fails the time split at a price we could take: null.
   The mechanism worth keeping (public money on the main event's star
   favourite) goes to the frontier with the per-book prices the purchase
   brings.

Frontier, written into `.claude/skills/league-models/references/methods.md`.
