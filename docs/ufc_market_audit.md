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
retired. Round totals: nothing clears (§4). Method, distance and round
markets, graded on BestFightOdds' per-book history 2021-2026 (§5f): no cut
clears. One lead, a market-anchored model on goes the distance, was +10.0%
on 791 bets at the last recorded price; at the price an hour before the
fight it is +6.8% [-0.9, +14.4] with 2026 losing, so it goes to the
frontier.

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
DraftKings' margin on the bought history. One lead came out of the ladder
(§4f, rung 4); it fails the bar and is written into the frontier.

**Corrected 2026-11-13.** This section said the bought history holds
DraftKings' totals only from 2025, and that DraftKings against Pinnacle at
the same line in the same pull gave 22 bets. Measured: DraftKings carries
totals on 1,072 fights at any line (31 in 2023, 417 in 2024, 430 in 2025,
194 to June 2026), 1,058 at the lines bet here; Pinnacle on 2,421 from 2020,
2,384 at the lines bet here. No other book a pick may name carries totals
in the history. The 22 was a
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
at about 606 bets; DraftKings posted 22 of these in 2024 and 23 in 2025
(53 in the history). At Pinnacle's own price: 95 bets +7.2% [−5.4, +20.2], 4/5 years.

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
   failed. It does not clear. Even at its full history return the interval
   would need about 400 bets to clear zero; it has 228. Nothing records it
   forward today.
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
would cost about 2); (2) the card-day over passing on fights
it has not seen: its return holding with 2025 and the three best dates in,
on enough bets for the interval to clear zero (about 400 at the history's
return); (3) about 600 bets of the 4.5 over, which DraftKings posts about
22 times a year.

## 5. Method of victory, goes the distance, round betting (`method_study.py`, `dk_props_probe.py`, `bfo_probe.py`)

### 5a. A live price exists: DraftKings' own board (`dk_props_probe.py`, 2026-11-14 01:00-01:50 UTC)

The odds feed rejects every key for these markets (§2), and that was the
only route checked when they were parked. DraftKings' own board prices all
four. Read from mike's PC with the client `data/ingestors/dk_live_board.py`
uses; UFC is DraftKings league 9034. One example fight, Alateng vs Diaz:

| Market | DraftKings page | Fights priced | Alateng vs Diaz |
|---|---|---|---|
| Method of victory, by fighter | Method of Victory | 13 | KO/TKO/DQ Alateng +1200, Diaz +330; submission +3500, +500; decision +500, −120 |
| Goes the distance | Fight to go the Distance | 13 | Yes −185, No +140 |
| Round betting | Winning Round | 13 | Round 1 +425, Round 2 +500, Round 3 +750, Draw +5000, By Decision −185 |
| Inside the distance | To Win by Finish | 13 | Diaz Yes +185, No −250; Alateng Yes +1000, No −4000 |

The board also lists, not fetched: Exact Method of Victory, Method of
Victory Double Chance, Round of Finish, Round and Method of Victory, Round
and Exact Method of Victory, moneylines for a finish, decision, first-round,
submission or KO/TKO/DQ win only, Alternative Total Rounds, To Start Round
X, First Minute Finish, Last Second Finish, and strike and takedown props.

- **Lead time.** The board's main page listed 28 fights: 13 dated Nov 14-15
  (UTC), 8 dated Nov 21, 7 later, with the fight winner, a points spread and
  round totals. The four prop pages listed only the 13 Nov 14-15 fights. So
  at the read, the evening before that card, its props were up and the
  card eight days out had none. When DraftKings first posts them is not
  measured.
- **Where it runs.** mike's PC. DraftKings refuses the Railway worker
  (`docs/live_odds_freshness.md`, measured 2026-08-31, as
  `dk_live_board.py` records). DraftKings' terms forbid
  automated access; mike's call on that is recorded in
  `data/ingestors/dk_direct_feed.py`.
- **Not stored.** Nothing reads these pages on a schedule, and none of these
  prices is in Supabase yet.

### 5b. History to backtest: BestFightOdds, per book (`bfo_probe.py`, 2026-11-13)

Each event page shows every book's last price for every prop. The site's
chart endpoint (`/api/ggd`) gives one book's price history for one prop: a
price with a timestamp each time it changed. Prop rows on every page
probed cover every market asked for: by fighter by KO/TKO, by submission,
by decision, inside the distance, in round N, by KO/TKO or submission in
round N; and for the fight: goes to decision, ends in round N, over or
under N.5 rounds, starts round N, draw.

| Card | Prop rows | Books with prop prices on the page (priced prop cells) |
|---|---|---|
| UFC 198, 2016-05-14 | 248 | none of today's columns; the chart's mean of books: 11 prices, 2016-03-21 to 05-14, for one prop |
| UFC 227, 2018-08-04 | 204 | none of today's columns; the chart for 5Dimes (book id 1): 10 prices, 08-02 to 08-05, for one prop |
| UFC 256, 2020-12-12 | 190 | none |
| UFC Fight Night 190, 2021-06-26 | 167 | BetWay 407, BetRivers 398, Unibet 385, DraftKings 190, BetMGM 91, Caesars 82; no FanDuel |
| UFC 281, 2022-11-12 | 165 | FanDuel 594, Unibet 580, BetRivers 577, DraftKings 445, BetWay 395, BetMGM 80, Caesars 50 |
| 2024-09-28 card | 144 | FanDuel 690, BetRivers 669, BetWay 447, DraftKings 300, BetMGM 98, Caesars 28 |
| UFC Vegas 123, 2026-11-01 | 163 | Unibet 649, BetRivers 577, FanDuel 512, BetWay 397, Caesars 84 |
| UFC 334, 2026-11-14 | 92 | FanDuel 382, Unibet 380, BetRivers 336, BetWay 224, Caesars 49 |

- **Movement is there.** One prop (a fighter by KO/TKO) per probe: BetRivers
  2026, 3 prices from Oct 27 to Nov 1, the last one equal to the page's price;
  DraftKings 2024, 3 prices over 3 days; DraftKings 2022 and FanDuel 2024,
  1 price each (never moved).
- **Bettable books.** DraftKings, FanDuel, BetMGM, Caesars and BetRivers are
  books a pick may name (`config.BEST_LINE_BOOKMAKERS`; Caesars is
  `williamhill_us`). Pinnacle has no column on any page probed.
- **DraftKings and BetMGM are missing from both November 2026 pages,**
  fight winner included, while DraftKings prices those fights on its own
  board (5a). Why is not known.
- **Size.** The event sitemap lists 819 UFC event pages (ids 1 to 4453;
  the lowest are UFC 72, UFC 73 and the TUF 5 finale). How many fights
  carry prop prices per book is not counted; that is the crawl below.
- **robots.txt** allows everything but `/cnadm/`.

### 5c. Paid providers (their own pages, read 2026-11-13; none called)

SportsGameOdds' UFC page lists round betting, distance markets and fighter
props; it does not name method of victory or say how far its history goes
(free tier: 2,500 objects a month). SportsData.io's MMA page says its
pre-fight props include method of victory and win by type; price on
request. odds-api.io lists method of victory, round betting and historical
odds, with no depth stated. None of these is needed for the next test.

### 5d. Blind bets at the free archive's near-close price

The Ultimate UFC Dataset's near-close method prices, 2012-2026:

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
the market carries 20-40% margin on finishes. That is one near-close price
per fighter-method, with no book named. No model has been fitted to these
markets yet.

### 5e. Next test

1. Crawl the BestFightOdds UFC event pages from 2021 for each book's last
   price on every method, distance and round prop. The US books' columns
   are empty on the December 2020 card probed and filled on the June 2021
   one; the first card with them is found by the crawl. One request per
   card. Store it in
   Supabase first, keyed on `source`.
2. Re-grade 5d at each bettable book's own last price, then fit a method
   and round model (finish rates from `ufc_fight_log`, anchored on the
   fight-winner price) and grade it there. Opening prices take one chart
   request per prop per book, so fetch them only for the props the
   last-price test points at.
3. If a model clears, it bets off DraftKings' prop pages, read on mike's
   PC on the day before each card (5a).

Steps 1 and 2 were run on 2026-11-14: §5f.

### 5f. The crawl and the grade (`data/ingestors/ufc_prop_history.py`; `prop_load.py`, `prop_grade.py`, `prop_leads.py`, `prop_staleness.py`)

**Verdict.** No prop market clears. Every blind bet loses except two near
break-even (goes the distance yes +0.9%, favourite by decision +2.4%; both
intervals span zero, both positive in 2 of 6 years). One lead passed the
kill tests at the last recorded price: the market-anchored model on **goes
the distance**, +10.0% on 791 bets. **At the price an hour before each
fight it does not hold**: +6.8% on 745 bets [-0.9, +14.4], 2026 -3.6%,
and its cut neighbourhood is a hump that fades to nothing by 0.20. It goes to the frontier.
Decision by fighter, the same event seen per fighter, fails the early/late
split. Method of victory by KO/TKO or submission, inside the distance,
round betting, fight ends in round N and round totals: nothing clears.

**What was stored** (2026-11-14, one request per page, 3 s apart). 328 UFC
event pages (325 with fights), cards 2021-06-05 to 2026-11-07 (the June 2021 cards are the
first with the US books' columns filled). 563,286 prices in
`ufc_prop_history`, 3,146 fights in `ufc_prop_history_fights`, 328 pages in
the ledger `ufc_prop_history_pulls` (a price on two pages for one card is
stored once); the copy on mike's PC holds the same three counts (`local_mirror.py`, which checks each table against the
server). The raw pages are a cache in
`betting_local_copies\ufc_prop_history_2026_11_14`.

| Market | DraftKings | FanDuel | BetMGM | Caesars | BetRivers | BetWay, Unibet, prediction markets | Total |
|---|---|---|---|---|---|---|---|
| Fighter wins by method in round N | 0 | 34,825 | 0 | 0 | 29,076 | 26,589 | 90,490 |
| Fighter wins in round N | 5,424 | 17,418 | 0 | 4,401 | 76 | 31,447 | 58,766 |
| Round totals | 0 | 5,264 | 0 | 2,146 | 10,630 | 19,962 | 38,002 |
| Decision by fighter | 3,659 | 5,447 | 4,046 | 0 | 6,624 | 17,220 | 36,996 |
| Fight winner | 3,880 | 5,748 | 4,582 | 5,674 | 5,684 | 11,320 | 36,888 |
| Fight ends in round N | 2,585 | 8,599 | 0 | 0 | 7,265 | 13,959 | 32,408 |
| Submission by fighter | 3,583 | 5,445 | 4,046 | 2 | 5,508 | 9,845 | 28,429 |
| KO/TKO by fighter | 3,583 | 5,446 | 4,040 | 0 | 5,496 | 9,816 | 28,381 |
| Goes the distance | 3,441 | 5,343 | 0 | 3,706 | 5,407 | 9,058 | 26,955 |
| Inside the distance by fighter | 7,147 | 0 | 0 | 0 | 2,222 | 16,090 | 25,459 |
| Other props (starts round N, draw, minute of finish, strikes, ...) | 23,840 | 46,856 | 1,984 | 687 | 52,129 | 35,016 | 160,512 |

Prop prices (fight winner excluded) by year:

| Year | Card dates | Fights | DraftKings | FanDuel | BetMGM | Caesars | BetRivers | Others |
|---|---|---|---|---|---|---|---|---|
| 2021 (from June) | 26 | 335 | 10,040 | 11,927 | 1,915 | 1,364 | 9,135 | 18,708 |
| 2022 | 46 | 598 | 19,967 | 25,096 | 3,145 | 2,254 | 20,633 | 36,560 |
| 2023 | 58 | 581 | 7,221 | 25,269 | 3,547 | 1,058 | 24,192 | 39,882 |
| 2024 | 70 | 566 | 11,046 | 25,398 | 3,553 | 1,008 | 24,475 | 25,123 |
| 2025 | 72 | 542 | 4,988 | 24,493 | 1,774 | 1,764 | 23,541 | 28,454 |
| 2026 | 52 | 498 | 0 | 22,460 | 182 | 3,494 | 22,457 | 40,275 |

DraftKings' prop prices thin out from 2023 and are absent in 2026: the site
stopped carrying DraftKings, not DraftKings its props (§5a prices all four
markets for the 2026-11-14 card). "Card dates" counts dates: the site
sometimes keeps two pages for one card.

**Placement.** 2,823 of the 3,146 fights are on our fight ids, 2,788
distinct: the site splits a fight in two when books spell a fighter
differently, and both halves are folded into one. Of the 323 unplaced, 198
have neither fighter on that card in our log and 120 one of them: bouts that
fell through or were rebooked, most with only the fight winner priced. 3 are
cards the site dates Dec 31 or Jan 1 as placeholders; 2 are a reshuffled
card. 20 spellings found on the same card under another name were aliased
(`BFO_NAME_ALIASES`; the site's "Bobby Green" is ufcstats' "King Green").

**Settlement** (`prop_load.py`). A no contest or an overturned result voids
every prop. A disqualification or a "could not continue" stoppage (20 fights)
voids the method and round props, because books split on calling it a TKO;
graded as a TKO instead, KO/TKO by fighter moves from -15.7% to -15.0%. A
draw voids the fight winner, wins "goes to decision" and loses every
fighter-method and round prop. Round totals settle on elapsed time; exactly
2:30 is a push.

**Blind, every price at the best of the five books a pick may name**
(`prop_grade.py blind`; 1 unit to win, risk capped at 3):

| Market | Side | Bets | Units | Return | 90% interval | Years positive |
|---|---|---|---|---|---|---|
| Goes the distance | yes | 2,712 | +27.7 | +0.9% | [-2.4, +4.1] | 2/6 |
| Goes the distance | no | 2,710 | -381.3 | -9.2% | [-11.7, -6.6] | 0/6 |
| Decision by fighter | yes | 5,412 | -42.5 | -2.1% | [-5.6, +1.3] | 2/6 |
| Decision by fighter, the fight's favourite | yes | 2,702 | +33.8 | +2.4% | [-2.1, +7.1] | 2/6 |
| Decision by fighter, the underdog | yes | 2,710 | -76.2 | -12.6% | [-19.8, -5.8] | 1/6 |
| Inside the distance by fighter | no | 3,524 | -200.4 | -2.3% | [-3.5, -1.0] | 1/5 |
| Inside the distance by fighter | yes | 3,540 | -264.7 | -14.1% | [-17.3, -11.0] | 0/5 |
| Round totals | over | 5,528 | -234.7 | -2.4% | [-4.8, -0.2] | 2/6 |
| Round totals | under | 5,528 | -534.4 | -9.5% | [-12.3, -6.5] | 0/6 |
| KO/TKO by fighter | yes | 5,412 | -262.6 | -15.7% | [-19.3, -11.9] | 0/6 |
| Submission by fighter | yes | 5,412 | -149.5 | -19.3% | [-24.9, -14.1] | 0/6 |
| Fight ends in round N | yes | 8,506 | -315.0 | -13.9% | [-16.6, -11.3] | 0/6 |
| Fighter wins in round N | yes | 17,209 | -427.3 | -19.7% | [-22.1, -17.2] | 0/6 |
| Fighter wins by method in round N | yes | 34,063 | -459.6 | -22.6% | [-25.1, -20.2] | 0/6 |

Goes the distance (yes) by year: 2021 -9.6%, 2022 -3.4%, 2023 +8.6%, 2024
+12.9%, 2025 -0.6%, 2026 -7.9%. The decisions came in 2023-2024 and the
market priced them as it had before. At each book alone the same markets
lose more; every book's row, and every market by year, is in the script's
output.

**Three mechanisms of our own per market** (`prop_grade.py models`; fitted
on earlier years only, graded 2022-2026 at the best of five, EV against the
mechanism's own chance):

1. **Price**: the five books' consensus no-vig chance (power method, over
   the market's full set of outcomes). A bet is a book that strays from the
   others.
2. **Anchored**: that chance as a fixed logit offset, plus a free intercept,
   a free slope on the market's own logit, one intercept per line or round,
   and ridge-penalised fighter inputs from `models/ufc_ratings` (finish,
   decision and knockdown rates, strike and takedown rates, fight length,
   rating, age, reach). **2r** is the same fit with no fighter inputs: the
   market recalibrated, the control.
3. **Coherent**: each fighter's method or round prices rescaled to the
   fight-winner market's no-vig chance; goes the distance from the rescaled
   decisions.

At EV >= 0.08 (bets, return, interval, years positive of 5):

| Market | Price | Recalibrated (2r) | Anchored | Coherent |
|---|---|---|---|---|
| Goes the distance | 3 bets | 612, +4.9% [-6.5, +16.4] | **791, +10.0% [+2.6, +17.3], 3/5** | 14 bets |
| Decision by fighter | 10 bets | 174, -17.1% | 1,112, +9.7% [+1.1, +18.5], 3/5 | 15 bets |
| Submission by fighter | 37 bets | 64, +1.2% | 519, +0.6% [-14.0, +15.6] | 47, +13.8% [-68.9, +126.3] |
| KO/TKO by fighter | 31 bets | 45, +13.8% [-49.4, +80.7] | 690, -16.8% [-28.1, -5.2] | 37, -23.3% |
| Inside the distance by fighter | 0 | 1 bet | 528, -2.9% [-11.1, +5.2] | 12 bets |
| Fighter wins in round N | 20 bets | 142, -51.4% | 1,046, -4.9% [-19.0, +9.7] | 32, +14.6% [-54.4, +87.7] |
| Fight ends in round N | 38, -29.5% | 277, -35.0% | 498, -15.7% | none |
| Round totals | 5 bets | 395, +4.6% [-4.7, +14.0] | 1,034, +0.5% [-5.2, +6.3]; 45% of placebos at or above | none |
| Fighter wins by method in round N | no book prices the full set | | | |

The price mechanism makes almost no bets: the five books rarely stray from
each other by 8%. The coherent rule's bets are a few dozen longshots; its
decision version at EV >= 0.02 is 60 bets, +68.7% [+29.3, +106.8], too few
to call, and re-graded below.

**The lead: goes the distance, anchored**, at the last recorded price
(`prop_leads.py tables`; the price-timing re-grade below undoes it):

| | Bets | Units | Return | 90% interval |
|---|---|---|---|---|
| All, EV >= 0.08 | 791 | +50.3 | +10.0% | [+2.5, +17.8] |
| 2022 | 241 | -3.8 | -2.1% | [-14.4, +9.9] |
| 2023 | 116 | +14.7 | +21.1% | [+4.3, +38.8] |
| 2024 | 116 | +27.5 | +37.3% | [+18.4, +57.2] |
| 2025 | 152 | +12.8 | +13.4% | [-6.2, +32.3] |
| 2026 to Nov 7 | 166 | -0.8 | -1.0% | [-19.1, +16.1] |
| The recalibrated market alone, same cut | 612 | +12.9 | +4.9% | [-7.0, +16.2] |
| Yes side / no side | 600 / 191 | +39.8 / +10.6 | +11.5% / +6.7% | |

- **Cut neighbourhood**: +5.2% at 0.04, +11.0% at 0.06 (5/5 years), +9.0% at
  0.10, +6.9% at 0.15, +5.9% at 0.20: a plateau on every fight, but a hump
  on the fights with a start time (below).
- **Penalty**: ridge 10 +12.1%, 30 +10.0%, 100 +11.1%, 300 +14.2%.
- **Early/late**: 2022-23 +4.3%, 2024-26 +15.7%.
- **Placebo** (fighter inputs shuffled within the training years, 50 runs):
  median +2.3%, 90th percentile +6.1%, none at or above +10.0%.
- **By book**, the model's bet wherever that book had a price: FanDuel
  +9.0% [+0.5, +17.6] on 648, Caesars +8.7% on 346, BetRivers +1.5% on 457,
  **DraftKings -4.0% [-16.2, +8.7] on 288**.
- **What it is**: the market priced decisions too low in 2023-2025. The
  recalibrated market alone catches about half of it and the fighter inputs
  add the rest; the placebo median (+2.3%) is that recalibration. About 10
  units a year on about 160 bets at these prices, and about 7 at the price
  an hour before (below).

**Decision by fighter** is the same event per fighter, and fails: 2022
-0.2%, 2023 -5.5%, 2024 +35.7%, 2025 +7.6%, 2026 +6.2%; early -2.6%, late
+14.4%. Its return climbs to the edge of the cut grid (+6.4% at 0.06 to
+21.6% at 0.20), a peak and not a plateau; the recalibrated market alone
loses (-17.1%); 3 of 50 placebos reach it. At DraftKings alone -7.2%.

**Is a last recorded price live?** The page shows each book's last change,
not the price at any given time. A book that stopped moving shows an old
price, and against a consensus that moved, an old price looks like value.
Two measurements, on price histories (`/api/ggd`, stored in
`ufc_prop_history_ticks`):

- **How old a last recorded price is** (`prop_staleness.py`, a seeded
  random 600 of the 147,356 priced histories at the five books). Every
  history's last price equals the page's. Of the 498 fights with a start
  time, the last change came after the start in 3.4%, in the final hour in
  12.9%, 1-6 hours before in 16.1%, 6-24 hours in 20.1%, 1-3 days in 31.5%
  and 3-7 days in 15.9%. Median hours before the start, by book: FanDuel
  9.3, DraftKings 19.0, BetRivers 22.1, Caesars 49.1, BetMGM 49.6. A price
  that has not moved is not proof the book still offered it; the history
  cannot tell the two apart.
- **The lead re-graded at the price standing before the start**
  (`prop_leads.py retime`). The start is the odds feed's latest start time
  for the fight; failing that, the games table's; failing that, the odds
  feed's start for the same two surnames within a day (the feed spells
  some fighters differently, "Sergey" Pavlovich). 46 of the 791 bets have
  no start time on any of the three and are left out:

| Goes the distance, anchored, EV >= 0.08 | Bets | Units | Return | 90% interval | Years positive |
|---|---|---|---|---|---|
| Last recorded price (the same 745 bets) | 745 | +39.7 | +8.4% | [+0.6, +15.6] | 3/5 |
| **Price 1 hour before the start** | 745 | +33.1 | **+6.8%** | **[-0.9, +14.4]** | 3/5 |
| Price 1 hour before, only bets still at EV >= 0.08 there | 666 | +28.0 | +6.6% | [-1.4, +14.6] | 4/5 |
| Price 24 hours before the start | 729 | +31.9 | +6.4% | [-0.9, +13.9] | 3/5 |
| Price 24 hours before, only bets still at EV >= 0.08 there | 571 | +25.2 | +7.1% | [-1.6, +16.5] | 4/5 |

  The last recorded price equals the price an hour before on 70% of the
  bets (DraftKings 89%, BetRivers 89%, Caesars 68%, FanDuel 62%). Where it
  differs it is usually longer: the hour-before price was shorter on 25%
  and longer on 5%, so the page's price flatters the bet.

  At the price an hour before, by year: 2022 -3.2% (229), 2023 +14.4%
  (113), 2024 +31.7% (114), 2025 +7.7% (140), **2026 -3.6% (149)**. By
  book: FanDuel +9.7% [-1.4, +21.3] on 415, Caesars +16.7% [+1.2, +30.7]
  on 142, DraftKings -7.7% on 74, BetRivers -5.5% on 114 (a split, not a
  rule: choosing Caesars after seeing this is selection). By side: yes
  +7.3% (565), no +5.6% (180). Prices taken: median +174, shortest -280,
  longest +1200, none shorter than -300.

  The cut neighbourhood, on the 1,311 of the 1,389 bets down to EV 0.02
  that have a start time:

| Cut | At the page's price | Decided at the page's price, graded an hour before | Decided and graded an hour before |
|---|---|---|---|
| 0.02 | -1.0% (1,311) | -2.2% | -2.4% (1,199) |
| 0.04 | +4.0% (1,086) | +2.6% | +2.3% (984) |
| 0.06 | +9.4% (914) | +7.8% | +7.8% [+1.3, +14.8] (830) |
| 0.08 | +8.4% (745) | +6.8% | +6.0% [-2.0, +14.0] (679) |
| 0.10 | +7.0% (621) | +5.4% | +4.2% (559) |
| 0.15 | +3.7% (379) | +1.7% | +1.0% (346) |
| 0.20 | +0.9% (256) | -1.0% | -1.2% (235) |

  On these bets the neighbourhood is a hump at every price, peaking at
  0.06 and fading to nothing by 0.20. The plateau on the full set (+6.9% at
  0.15, +5.9% at 0.20) rested on the fights with no start time.

  The placebo (0 of 50 at or above, above) was run at the last recorded
  price only: the placebo's bets are other props, and their histories were
  not fetched.

  **The lead does not hold at the price an hour before the fight**: its
  interval reaches below zero, 2026 and 2022 lose, and the cut
  neighbourhood is a hump, not a plateau. It goes to the frontier, not to a
  model.

  The decision-by-fighter bets' histories were still being fetched when
  this was written; that lead had already failed.

**Where it could be bet.** DraftKings' own board (§5a) is the only live prop
price read today, from mike's PC, and at DraftKings alone the lead loses.
The other route is this site's page for the upcoming card: every book's
current price, allowed by robots.txt, readable from anywhere. A model naming
FanDuel or Caesars would read that page on the day of the card.

**What would have to change** for goes the distance to ship: a return
whose interval clears zero at the price an hour before the fight (it is
[-0.9, +14.4]); 2026 turning positive on the cards still to come (-3.6% at
that price so far); a cut neighbourhood that holds at that price; and a
live read of FanDuel's or Caesars' price at decision time. It goes to the
frontier (`methods.md`) and is graded forward on each card's page.

**Not run.** The full chart stage (147,356 histories at the five books,
about five days at 3 s apart): only a 600-history sample and the leads' own
histories were asked for. Fighter wins by method in round N has no full
outcome set at any book to de-vig, so only its blind row exists.

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
- Props: blind by market, side, book, year and favourite/underdog; three
  mechanisms per market walk-forward by year; the recalibrated market alone
  as the control; cut and penalty neighbourhoods, early/late, side, price
  band and book splits, a 50-run placebo; DQ and could-not-continue graded
  both ways; the last recorded price against the price an hour and a day
  before the fight: §5f.

## 8. Leads from outside the repo

Scouted 2026-11-13 (web, GitHub, papers; no paid calls).

| Lead | Source | Claim | Status |
|---|---|---|---|
| The closing moneyline is efficient | Miller & Nichols, J. Econ. Finance 2026 (doi:10.1007/s12197-026-09757-x); Lam 2025 HEC thesis; Robbins 2023 | No broad bias at the close; calibration error 0.015 | **Agrees** with §3a and §3b at the close |
| The opening line is soft | github.com/SolvAI/ufcash (self-reported, 226 held-out bets +24.1%) | A stats model beats the BestFightOdds open | **Reproduced** on our data (§3b); **fails** at DraftKings' opener on 2026 (§3c) |
| Big line moves are under-reacted to, even at the close | ufcalendar.com 14-year study (a vendor; win rates, no prices) | Steamed side wins more than its close implies | **Dead** at the worst closing price (`ml_steam.py`): the side the line moved toward loses in every band of move size, -0.32% (590 bets, 10-15 points) to -8.91% (314, 15+ points) |
| Favourite by decision is under-priced | Stanhope 2021 (UCSAS poster, SSRN 3906072) | Miscalibrated, p = 0.0028 | **Tested** (§5d, §5f): least over-priced, not profitable; at the five US books 2021-2026, +2.4% [-2.1, +7.1] blind, 2 of 6 years |
| Short-notice replacements, missed weight | agentmma, Fightful (win rates only) | Replacements win 37-42% | **Totals: dead** (§4e, M4: fights first listed under 7 days out); fight winner still queued |
| Totals, goes the distance, round betting | nothing found (searched again 2026-11-13) | No public test | Totals: §4 is the first test, nothing clears. Goes the distance and round betting: graded (§5f); round betting nothing, goes the distance one lead to the frontier |

Data sources found: fight-canon-db and the Ultimate UFC Dataset (stored);
nlbair/ufc-data (CC BY 4.0, BestFightOdds open and close range plus judges'
scorecards; not imported, it duplicates fight-canon-db's prices).
BestFightOdds' per-book prop history is read in §5b. OddsPortal
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

4. **Props, three per market** (§5f): a book straying from the other four;
   the market recalibrated, then moved by fighter inputs; the method and
   round prices made coherent with the fight winner. The first barely bets
   (the five books agree within 8%); the third bets a few dozen longshots;
   the second leaves one lead, goes the distance.

Frontier, written into `.claude/skills/league-models/references/methods.md`.
