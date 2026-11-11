# NCAAF market audit, 2026-11-10

mike, 2026-11-10: *"Do a full audit of NCAAF markets - I dont see spread or ML
models or other markets firing; what optimizations can be made to maximize
units but also not too much crazy volume ... use what you have learned by
building recent models."*

Every number here is in units (1 unit to win, risk capped at 3, the published
stake). Each table names the script that printed it. The scripts are in
`scripts/ncaaf_search/audit_2026_11/` and read the local copy of the database
(`docs/local_ops.md`), not production.

## 1. The market grid

| Market | Settles on | Prices stored | What was measured | Result |
|---|---|---|---|---|
| Full-game total | `games` final score | 2023-2025: 13 books, two pulls a day. 2026: DraftKings' whole path; every other book's opener and close only | The live model's record, seed stability, timing, best line; line shopping against the consensus | Live model stands. Line shopping: no volume |
| Full-game spread | `games` final score | same | Line shopping against the consensus (the NCAAB spread rule), three ways | Nothing clears |
| Full-game moneyline | `games.home_win` | same | Each book against its own spread (the NCAAB rule); best price against the consensus spread; the paused model on every 2026 game | Nothing clears |
| In-play moneyline and total | `games` final score | DraftKings only: 2025 bought replay (one snapshot about every 5 minutes), 2026 live | A market-anchored game-state model, fitted on 2025 and read on 2026 | §6 |
| In-play spread | `games` final score | none | Not measurable | No prices |
| Player props, 8 over/under markets | `ncaaf_player_game_log` | 2025: one pull a game, 24 hours out. 2026: three pulls on game day | The market-relative rule (the NFL prop model's), 2025 and 2026, with every book as a placebo reference | Nothing clears |
| Anytime touchdown | player log | one-way (Yes only) | Not measurable: cannot be de-vigged | Parked |
| First half (spread, total, moneyline), team totals, quarters | half and quarter scores (not stored: play-by-play covers 2025 only) | none | Nothing | Needs a purchase, §7 |
| Alternate spreads and totals | `games` final score | 2026-10-29 onward only, 119 games | Nothing: twelve days is not a sample | Parked until a season is stored |
| Kalshi game contracts | `games` final score | hourly since 2026-09-10 | Not examined in this audit | Parked |

## 2. What the live models did in 2026

Settled BETs in `picks` through 2026-11-07, void and duplicate rows out,
at `COALESCE(decision_odds, dk_odds)` (read-only SQL on production,
`published_pick_unit_profit`).

| Model | Bets | Record | Units | Return | Note |
|---|---|---|---|---|---|
| Pre-game totals (`ncaaf_over_under`) | 94 | 54-40 | +9.76 | +9.3% | Under 45-33 (+8.55), over 9-7 (+1.21). Prices -118 to +100 |
| In-play moneyline (`ncaaf_live_win_prob`) | 49 | 25-24 | +6.73 | +14.0% | Before the 09-19 re-cut 18-9 (+6.70). Since: 22 bets, 7-15, +0.03, all at +173 to +300 |
| In-play total (`ncaaf_live_total`) | 98 | 51-47 | -5.20 | -4.4% | Its last bet was on a 2026-09-17 game. Nothing has cleared its cut since |
| Opening spread (`ncaaf_spread`) | 1 | 0-1 | -1.15 | | The premium tier has never bet |
| Moneyline (`ncaaf_moneyline`, paused) | 16 | 7-9 | -4.91 | -23.6% | Not bets: what it would have said. Never posted |

**Why the spread models do not fire.** Both wait for DraftKings' and Bovada's
opening numbers to be captured within 90 minutes of each other. On the 2026
board, 1,006 of the 1,197 spread rows (two a game) carry the reason "openers
not captured simultaneously"; 60 say DraftKings had moved off its opener, 14
that the books agreed, 4 that Bovada had no opener, and 113 carry no reason
(`grade_2026.py` prints the reasons). The rule cannot meet its own first
condition on this feed, as measured on 2026-09-07 and again 2026-09-10.

**Why the moneyline model does not fire.** It is paused. Graded on every
2026 game it scored (901 sides on 472 games, `grade_2026.py`): at its own cut
(probability 0.62, edge 0.08) and a price of -250 or longer it is 49 bets,
25-24, -8.56 units. All 25 cells of the probability-by-edge grid lose (-1.9%
to -29.2%), and a larger claimed edge loses more. No cut clears.

**The graded-universe view holds no NCAAF rows.** `mv_scored_pick_outcomes`
returned 0 rows for sport NCAAF on 2026-11-10, so no NCAAF model's non-bet
rows are graded anywhere in the database. This audit graded them from the
local copy. Not fixed here.

## 3. The four NCAAB market rules on three seasons of NCAAF prices

`lab.py`, `spread_dd.py`, `sym.py`. 2,314 scored games of 2023-2025 with
stored pulls. The final-margin and final-total tables are the NCAAB kernel
unchanged (`models/ncaab_margin_dist.py`), fitted for each season on every
earlier season's games and CFBD closes. A bet is the best quote among the
seven deciding books, needs three other books in the 10-book consensus, and
is graded at that book's line and price. Intervals resample game dates.
The primary read, fixed before any result, is the game-day morning pull
(13:55 UTC, the NCAAB instant).

| Rule | Cut | Bets | Units | Return | 95% interval | Verdict |
|---|---|---|---|---|---|---|
| Spread against the consensus, as built for NCAAB | 0.03 | 338 | +29.4 | +8.2% | -1.2 to +16.7 | **Not an edge: see below** |
| Spread, the home/away tilt removed | 0.015 | 47 | +4.9 | +9.9% | -16.1 to +38.8 | No volume. 22 bets at 0.02 |
| Spread, no table: 0.5+ points better than the consensus, -115 or longer | | 1,488 | +20.2 | +1.2% | -4.0 to +6.0 | Break-even; negative at seven of the eight reads |
| Spread, no table: 1.0+ points better | | 269 | -26.3 | -8.8% | -23.7 to +5.8 | Loses |
| Total against the consensus | 0.02 | 48 | +0.2 | +0.3% | -30 to +29 | No volume: books agree on totals |
| Moneyline against the same book's own spread (the NCAAB rule) | 0.01 | 386 | -1.5 | -0.5% | -11 to +12 | Nothing |
| Moneyline against the consensus spread | 0.02 | 311 | +14.7 | +7.8% | -4.7 to +21.6 | One read, one season: below |

**The spread rule's +29.4 units is 337 road teams out of 338 bets.** The
fitted table says the home side covers the consensus slightly under half the
time at most spread sizes (fitted offset -0.27 to -0.39 points, plus the
kernel's own noise on 7,500 to 9,200 games), and a 0.03 cut then admits one
side only: no bet on a spread of 7.5 to 14, and 314 of the 338 on underdogs.
Controls on the same games: every road team at the consensus at -110 lost 4.4%
(1108-1105-36) and every underdog lost 3.9%. The rule's own sides, re-bet at
the consensus at -110, made +5.3% (interval -3.8 to +14.7). With the tilt
taken out, 22 bets remain at a 0.02 cut. With no table at all, a number a
full point better than the consensus exists in 13.2% of games and lost 8.8%.
The evening reads of the first version did not hold either (-10.9% on
game-day evening, +1.1% the evening before). What is left is a bet on road underdogs at two
spread sizes that happened to pay over three seasons, which is not a rule.

**The moneyline against the consensus spread** is positive at the game-day
morning read only (other reads at the 0.02 cut: -5.2%, +5.0%, -6.6%, -2.0%,
-0.4%, -7.5%, -3.9%), its 2023-2025 seasons are -2.8, +16.7 and +0.8 units,
and without its 10 best dates it is -9.3 units. It bets underdogs (median
price +146).

**No 2026 forward read was possible for these rules.** At the game-day
morning read a 2026 game holds a quote from a median of one book, because a
settled NCAAF game kept only each book's opener and close (§8). The first
version of the spread rule formed 11 bets on all of 2026.

The same construction returned +10% and +21% on NCAAB. On NCAAF the books
sit on one number: this confirms the 2026-09-08 result (steam lag and the
consensus anchor, both null) with the rules that worked on basketball.

## 4. The totals model

The one pre-game earner. Five checks (`totals_wf.py`, `totals_seeds.py`,
`totals_seeds_fc.py`, `totals_opt.py`, `totals_2026_bag.py`,
`totals_2026_replay.py`, `grade_2026.py`).

**1. Each prediction carries about 1.5 points of random noise.** The fit
subsamples rows and columns, so the same data fitted under another random
seed predicts a different total: across 11 seeds the standard deviation of
one game's prediction is 1.49 points (95th percentile 2.39). The gate is 8
points and most bets lock within a point of it. Of 481 games at the gate
under one seed, 339 to 344 are at the gate under another.

| 2022-2025 walk-forward, 8+ from the stored close, -110 | Record | Win rate | Units |
|---|---|---|---|
| Worst of 11 single seeds (seed 42, as fitted today) | 244-230 | 51.5% | -9.0 |
| Best of 11 single seeds | 266-206 | 56.4% | +39.4 |
| The 11-seed average | 235-191 | 55.2% | +24.9 |

The published walk-forward (55.6% to 55.9%) sits inside that range. It was
one draw.

**2. In the shape it runs live, every seed is positive.** First morning
DraftKings read, five days out to game day, at which the line is 8+ from the
model; bet at DraftKings' line and price; 2023-2025, 2,167 games.

| | Bets | Units | Return | Seasons 2023 / 2024 / 2025 |
|---|---|---|---|---|
| 11 single seeds, range | 367 to 399 | +17.1 to +45.2 | +4.1% to +10.6% (median +6.8%) | all three positive for 8 of 11 |
| The 11-seed average | 346 | +35.06 | +9.35% (interval -2.2 to +21.0) | +3.94 / +17.55 / +13.57 |

The average, by gate: 7 points 489 bets +22.39 units; 8 points 346 bets
+35.06; 9 points 246 bets +21.19; 10 points 168 bets +22.08. Eight is where
the units peak, with positive neighbours on both sides. Overs +16.0 units on
224, unders +19.0 on 122; early half of each season +13.5%, late half +5.6%.

**3. 2026 does not separate the average from a single fit.** The 2026 season
replayed from the season's feature rows (89 to 100 bets each): the live
artifact 49-45, -1.14 units; the 11-seed average 45-44, -4.20; seed 42
refitted today 48-52, -10.07. That replay shares only 47 of its 94 games with
the 94 bets the model really placed (54-40, +9.76), so it is a second draw of
the same rule, not a re-grade of the live record.

**4. The real 2026 bets beat the closing total by 0.73 points on average**
(standard deviation 2.13 over 94 bets: 46 better than the close, 24 the same,
24 worse). That is the strongest single piece of evidence the rule is real.

**5. What does not help.**

- *A lead limit.* 2023-2025, first-cross bets by days out: five days 235 bets
  +19.84 units, four 53 bets -3.40, three 39 bets -2.94, two 29 bets +3.81,
  one 26 bets +9.36, game day 17 bets +3.43. In 2026 the late bets were the
  weak ones (9-11). No direction survives both.
- *A bigger stake on bigger disagreements.* 84 of the 94 live bets locked
  between 8 and 9 points, because a bet locks the first time the line
  crosses. There is no second band to size up.
- *Correcting the model's level.* In 2026 the model sits 2.30 points under
  the market on average (September -1.48, October -2.79, November -2.88)
  while games landed 0.46 over it. Shifting the model up by one point would
  have kept 6 of the 82 unders on the stored rows (52-30 as they stand) and
  added one over.
- *The best line instead of the best price.* The rule bets DraftKings' line
  at the best price. Taking the best line among the deciding books is 0.23
  points better on average and better by half a point on 37% of bets; over
  399 first-cross bets it changed four results: +30.10 units to +33.57. Real
  and small.

## 5. Player props

The market-relative rule (bet a soft book's price when a sharper book's
de-vigged probability at the same line says it is too cheap), 2025 and 2026,
five variants, 648 cells, every book also run as a placebo reference. Full
report: `docs/ncaaf_market_audit_props.md`; scripts in the audit folder's
`props/`.

| Reference, season, 0.02 cut | Bets | Record | Units | Return | 95% interval |
|---|---|---|---|---|---|
| Pinnacle, 2026 | 42 | 14-28 | -13.61 | -32.4% | -60.7 to +1.4 |
| Bovada, 2026 | 23 | 9-14 | -3.27 | -15.6% | -67.0 to +23.0 |
| Consensus of the other books, 2026 | 64 | 30-34 | +1.23 | +2.3% | -21.6 to +29.2 |
| BetOnline, 2025 | 42 | 20-22 | +2.31 | +6.3% | -20.5 to +33.2 |
| Consensus, 2025 | 107 | 54-53 | +6.82 | +6.9% | -14.1 to +31.2 |

Nothing clears, and the placebo fails as it did in September: with FanDuel as
the "reference" the rule returns +13.5% over 111 bets in 2025, and in 2026
Pinnacle has the lowest return of the eight references with a bet. The board
cannot carry the rule. DraftKings and BetRivers post no two-way college
props, so neither can be de-vigged. In 2026 only FanDuel and Hard Rock are
two-way in volume. From the week of 2026-09-29 those two stopped disagreeing
at an equal line: against Bovada and against the consensus, no soft side
reaches the 0.02 cut in any later week.

## 6. In play

The NCAAB in-play idea ported to football: what is still to come (margin and
total) as a Normal around the pre-game line, the score and the pace, fitted
on 2025's play-by-play and read on 2026 (473 games, 2026-09-19 to 11-07, the
dates the live loop logged a game state), at DraftKings' in-play prices, the
only in-play prices stored. Also fitted on each half of 2025 and read on the
other. One decision a game and rule, at the first fresh quote that clears the
cut. Full report: `docs/ncaaf_market_audit_inplay.md`; scripts in the audit
folder's `inplay/`.

| Rule | 2026, every cut from 0.02 to 0.20 | Verdict |
|---|---|---|
| Total, first half | -12.6% to -8.4% on 437 to 473 bets | Loses at every cut |
| Total, second half | -6.7% to -1.8% on 458 to 460 bets | Loses at every cut |
| Moneyline, first half | -7.3% to +6.2% on 409 to 423 bets | No cut positive on 2026 and on both halves of 2025 |
| Moneyline, second half | -7.7% to -3.3% on 333 to 344 bets | Loses at every cut |

No rule clears. Three things it showed:

- **The model's spread is right and its opinion is mostly not.** Out of
  sample its error bands hold (predicted against realised spread 0.88 to
  1.14 in every time band), which the live engine's did not. But on 2026
  second-half totals the result moves 0.119 for each 1.0 of claimed
  probability: about three quarters of every claimed edge is not there.
- **With a quote every few seconds, a cut selects almost nothing.** 99.6% of
  2026 games bet a second-half total at an EV cut of 0.20. The 2026 feed
  holds 77.9 fresh quotes a game and rule against 14.8 in the 2025 replay.
- **Our score log trails DraftKings by a median 75 seconds in 2026.** A rule
  that waits to confirm nothing was scored reads better (+14.3% on 377
  first-half moneylines at 0.08) because it peeks four minutes ahead. With no look-ahead
  the same cell is +5.5% on 388 bets, inside what the placebo produces.

**At most five a night, the NCAAB selection:** 2026 109 bets, 54-55, +12.08
units, +12.8% (interval -9.6 to +34.2), above the placebo's 95th percentile
(+5.1%), early half -6.5% on 45 and late half +26.5% on 64. The two halves of
2025: -1.8% on 167 bets and +2.9% on 99. Positive on 2026, flat on 2025: not
a pass. It is the nearest thing to a candidate this audit found, and it
rests on about 100 bets. Play-by-play is stored for 2025 only, so there is
no second season to read it on.

What the stored data cannot answer: in-play spreads (none stored), and any
season before 2025 (no play-by-play, no in-play prices).

## 7. Markets with no stored prices

First-half spread, total and moneyline, team totals and quarters have never
been stored for NCAAF, and half and quarter scores are not stored either
(`ncaaf_plays` holds 2025 only). On NCAAB the two first-half models came out
of exactly this purchase. The same purchase for NCAAF, sized from the NCAAB
billing (one call a game, 10 credits a market returned, at most 40 a game for
the first-half moneyline, spread, total and the team totals):

| Buy | Games | Most it can cost |
|---|---|---|
| Test: 50 games at the game-day morning read | 50 | 2,050 credits |
| Game-day morning read (13:55 UTC), 2023-2025 | 2,314 on 205 dates | 92,765 credits |
| The evening before (22:55 UTC), 2023-2025 | 2,314 on 205 dates | 92,765 credits |

The two reads are the times the full-game pulls are already stored at, so a
first-half line can be set beside the full-game line of the same moment.
The figure is 40 credits for every game plus one event list a date; a game
the feed does not list costs nothing.

**In-play prices for more seasons** (every book, spreads included) at the
NCAAB cadence, one bulk snapshot at each :00 and :30 with a lined game in
progress (kickoff to four hours after), 30 credits a snapshot: 2021-2025 is
6,191 snapshots, 185,730 credits (1,179 to 1,314 a season; counted from the
stored kickoff times, not bought or dry-run). It is only worth buying with
play-by-play whose clock times are real: CFBD's 2025 wallclocks are
last-edited stamps (§6 report), and no other source has been probed.

Balance on 2026-11-10 16:11 UTC: 11,932,481 credits (`odds_api_quota`).
Half and quarter scores come free from CFBD's game records through a worker
job. Nothing is bought until mike says so.

## 8. What changed in the repo with this audit

- **NCAAF keeps every book's price path from 2026-11-10**
  (`data/prune_odds.PATH_KEPT_SPORTS`). A settled 2026 game held a median of
  one full-game spread row at each book but DraftKings, against 92 to 121 on
  games still to be played, so 2026 could not be read forward for any rule
  that compares books. The weeks already thinned cannot be put back.
- The audit's scripts, `scripts/ncaaf_search/audit_2026_11/`. Run from that
  folder. `extract_ncaaf.py` then `prep.py` build the cache from the local
  copy of the database; `paths.py` says where. The props study reads
  `ncaaf_prop_odds.parquet` from the same cache: every `player_prop_odds`
  row whose `game_id` starts `NCAAF_`, pulled with the filter
  `extract_ncaaf.py` uses on `odds` (531,456 rows on 2026-11-10).

No model, cut, pause or stake was changed.
