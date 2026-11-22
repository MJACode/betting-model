# NHL, every market: Pinnacle's no-vig price against a bettable book (2026-11-21)

**Asked.** mike, 2026-11-21, after the NHL timing investigation: build models
that beat Pinnacle's no-vig line, and look at the markets we do not bet yet.
*"Yes, run it."*

**The rule.** `nhl_over_under`'s rule (`models/nhl_totals_market.py`), unchanged,
on every NHL market the odds table stores. Per game, walk the pre-game fetches
in time order. In each fetch that holds Pinnacle at a number, de-vig Pinnacle
(proportionally, as the live rule does; overround strictly between 1.00 and
1.15, 1.20 for the 3-way). Price every bettable book
(`config.BEST_LINE_BOOKMAKERS`) in that same fetch at the same number, -200 or
better. Bet the best EV the first time it clears the floor. One bet a game per
market. Units are the published stake (1u to win, risk capped at 3); "flat" is
1u risked. Closing-line value is the taken price against Pinnacle's last
pre-game no-vig price at the same number.

**The script.** `scripts/nhl_sharp_vs_soft_lab.py` (read-only, reads the local
copy of the database). `validate` reproduces `nhl_over_under`'s evidence table
bet for bet: 2,768 / 1,859 / 1,276 / 819 / 548 bets at floors 0 / 0.005 / 0.01 /
0.015 / 0.02, and +60.2u, +4.72% at 0.01. Every table below was printed by
`grid`, `kill` or `check` (with `--devig power` or `--reference <book>` where
stated), except the 2026-27 goalie-gated replay, which was a one-off research
run (noted where it is quoted). 2026-27 figures from `grid` read thinned prices
(below) and are not evidence.
About 216 cells were read (9 markets, 3 windows, 8 floors), so a single cell's
interval means little on its own; the verdicts lean on neighbourhoods and the
kill tests.

## The grid

These are verdicts **for this rule**. A market-level null under the
league-models skill also needs three invented mechanisms and the stuck ladder;
those are listed at the end as the next experiments.

| Market | Settles on | Prices stored (Pinnacle with a bettable book) | Prior result | This rule | Verdict |
|---|---|---|---|---|---|
| Full-game total | final, shootout goal in | 2020-21 to 2026-27, 4-7 snapshots a game | live as `nhl_over_under` | reproduced; keeps +2.1% without its ten best dates, +3.6% to +4.8% on the power de-vig | live |
| Puck line ±1.5 | final margin vs the home line | 2020-21 to 2026-27, 8,312 games | models only (`docs/nhl_market_lab.md`); this rule never run | +6.0% on 1,710 at 0.015, CLV +2.3%; **+1.4% without its ten best dates; +1.5% on the power de-vig** | not established |
| Moneyline | final, OT/SO in | 2020-21 to 2026-27 | same-moment shop rule: no edge (`scripts/nhl_moneyline_market_lab.py`) | -0.6% on 1,479 at 0.01; +2.9% to +5.8% at 0.015-0.04 (987-161 bets); every interval spans zero; published-stake units -27.1 to +16.5 | null for this rule: no neighbourhood |
| Regulation 3-way | regulation result (period scores) | 2023-24 to 2025-26 one snapshot a game; 2026-27 live | +10% on 416, almost all draws | +3.8% to +10.0% on 578-1,893 (2023-24 to 2025-26) | not established: every interval spans zero, no closing value measurable, and 2026-27's price path is deleted |
| **1st-period total** | P1 goals (`nhl_period_scores`) | 2023-24 to 2026-27 one snapshot a game (2026-27 bought 2026-11-21) | +19.3% on 160 at 0.02, failed the season test | +16.2% on 250 at 0.015 (+1.9..+30.0); power de-vig +18.2% on 298 at 0.01 (+6.1..+30.3), all three seasons positive; retail references -3.7% to +2.8%; 88% unders, 74% at William Hill | **not a model now: the book that carried it quotes no first-period total in 2026-27** (4 bets on 362 games at 0.015) |
| Team totals | team's final goals | 2023-24 to 2025-26 one snapshot; no DraftKings | model -5.0% | 18-115 bets, negative | null for this rule |
| Alternate totals | final | 2023-24 to 2025-26 one snapshot; 2026-27 live | +28.1% on 117 at 0.06, noise | published-stake units -15.0 to -0.1 at floors 0 to 0.04 (+5.8 on 134 at 0.06); last two hours -10% to -30% | null for this rule |
| Alternate spreads | final margin | 2026-27 only, 171 games | never run | not read: the only season's settled games have lost their price path | parked: no gradable season until the price path is kept |

## Puck line

**The floor neighbourhood, every pre-game fetch, proportional de-vig:**

| EV floor | bets | units | flat return | 95% | CLV | beat close | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---|---:|---:|---|---|---|---|---|---|
| 0.000 | 3,635 | +72.2 | +2.5% | -1.5..+6.5 | +1.06% | 67% | +2.0 (795) | +6.3 (1,008) | +0.3 (498) | -3.9 (427) | +2.5 (453) | +6.6 (409) |
| 0.010 | 2,178 | +38.9 | +3.1% | -2.3..+8.5 | +1.91% | 75% | -0.9 (677) | +8.3 (757) | -2.0 (208) | -5.9 (167) | +11.9 (211) | +1.2 (144) |
| 0.015 | 1,710 | +63.9 | +6.0% | -0.3..+12.3 | +2.32% | 78% | +1.3 (618) | +10.0 (646) | +8.8 (126) | -7.9 (92) | +15.1 (129) | +8.0 (92) |
| 0.020 | 1,363 | +47.3 | +5.4% | -1.8..+12.6 | +2.74% | 80% | +1.0 (562) | +7.6 (541) | +14.8 (73) | -18.4 (43) | +17.3 (77) | +15.8 (63) |
| 0.030 | 868 | +10.9 | +3.9% | -5.4..+13.2 | +3.38% | 83% | | | | | | |
| 0.040 | 540 | +9.0 | +4.5% | -7.4..+16.5 | +4.20% | 87% | | | | | | |

Intervals resample whole game days. 2026-27 had 7 bets at 0.015 (see below on
why this season cannot be replayed).

**What it passes:**
- **The grading is right.** Pinnacle's close against what happened, home -1.5
  (the line where the sign has gone wrong before): said 0.320 / happened 0.314,
  0.393 / 0.390, 0.492 / 0.464, 0.582 / 0.616; home +1.5: 0.612 / 0.618, 0.680 /
  0.661.
- **The blind bet loses the margin.** Every book, both sides, at its own last
  pre-game quote, 2020-21 to 2025-26: -2.6% (Pinnacle) to -6.3% (Hard Rock).
- **The placebo.** The same rule with a retail book as the reference loses:
  DraftKings -1.7% / -2.2% / -1.4% at 0.01 / 0.015 / 0.02 (1,903-1,127 bets),
  FanDuel -1.7% / -2.5% / -2.6%, Bovada -2.0% / -2.1% / -0.3%. Pinnacle as the
  reference: +3.2% / +6.1% / +5.3%.
- **Simultaneous quotes.** Pinnacle's snapshot time minus the bet book's on the
  0.015 bets: median -1 s, 90th percentile 54 s, 99th 225 s.
- **Both sides, no one book, every lead time.** Favourite -1.5 +5.0% (1,576),
  underdog +1.5 +18.2% (134); DraftKings +18.6% (217), BetRivers +11.3% (204),
  FanDuel +4.7% (662), BetMGM +0.8% (417), William Hill -7.0% (175); every lead
  bucket from 0-0.5 h to 24 h+ positive.
- **The last two hours** (the closest stored stand-in for the goalie rule):
  862 bets +6.7% (-2.0..+15.9), CLV +3.1%.

**What it fails:**
- **Ten nights carry it.** Without its ten best dates: 0.01 -0.6% (2,101 bets,
  -9.3u), 0.015 +1.4% (1,634, +18.5u), 0.02 -0.05% (1,305, +7.6u). The live
  totals rule keeps +2.1% / +4.2% at 0.01 / 0.015 on the same test.
- **The de-vig method.** 92% of the bets are the favourite at -1.5, mostly at
  plus money (median +185): the less likely side of the pair, which a
  proportional split favours. On the power de-vig: 0.01 +2.7% on
  1,883, 0.015 +1.5% on 1,251 (-5.1..+8.0), 0.02 +5.9% on 873 (-2.0..+14.4);
  without the ten best dates, -0.6% / -2.7% / -0.1%. The totals rule on the
  power de-vig: +3.6% / +4.8% / +4.3%.
- **The stricter bar.** 2023-24 lost at every floor up to 0.02; the interval
  reaches below zero at every floor.

**Price range at 0.015:** median +180 (the -1.5 favourite at plus money); 35 of
1,710 (2%) between -150 and -200; none shorter than -200 (the floor).
**Volume:** 92-129 bets a season from 2022-23 on (618-646 in 2020-22, when the
books disagreed more); 24-66 a season in the last two hours.

## First-period total

| EV floor | de-vig | bets | units | flat return | 95% | 2024 | 2025 | 2026 | without ten best dates |
|---|---|---:|---:|---:|---|---|---|---|---|
| 0.010 | proportional | 333 | +29.2 | +10.7% | -1.9..+22.8 | -0.2 (56) | +20.7 (108) | +8.0 (169) | +2.0% |
| 0.015 | proportional | 250 | +32.8 | +16.2% | +1.9..+30.0 | -13.0 (34) | +20.1 (85) | +21.2 (131) | +5.4% |
| 0.020 | proportional | 160 | +26.0 | +19.3% | +1.9..+37.3 | +4.9 (14) | +20.0 (53) | +21.1 (93) | +6.6% |
| 0.010 | power | 298 | +47.2 | +18.2% | +6.1..+30.3 | +13.3 (60) | +17.6 (95) | +20.7 (143) | |
| 0.015 | power | 197 | +24.4 | +15.2% | +0.1..+30.3 | -8.0 (34) | +18.5 (65) | +21.1 (98) | |

- **The placebo: the edge is Pinnacle's.** The same rule with a retail
  reference: DraftKings +2.8% / +2.0% / -3.7% at 0.01 / 0.015 / 0.02 (366-178
  bets), FanDuel +0.2% / +0.9% / +2.3% (1,102-699), William Hill -9.8% / -11.3%
  / -15.0%. Pinnacle: +10.7% / +16.2% / +19.3%. Pinnacle's close calibrates
  (1.5 line: said 0.523, happened 0.519 on 3,003 games). Blind at each book's
  last quote, every side loses the margin (unders -2.4% at William Hill to -6.8%
  at FanDuel; overs -3.3% to -15.5%).
- **One book and one side carry it.** At 0.015: unders 220 bets +19.3%, overs 30
  bets -6.2%; William Hill 184 bets +16.7%, FanDuel 48 +9.0%, DraftKings 17
  +32.2%. Median price +126: William Hill hangs the under 1.5 longer than
  Pinnacle's fair price. William Hill's blind under loses 2.4%, so the rule's
  +16.7% there is selection, not the book's lean alone. It is the "margin sits
  on the over" shape seen in other markets here, at one book.
- **One snapshot a game** (an hour before that day's first puck), so the close
  is the decision snapshot and closing-line value cannot be measured. The live
  rule would decide after both goalies are confirmed, later than this snapshot
  for most games.
- **2026-27, bought 2026-11-21 (mike: "Yes, buy them"): the opportunity is gone.**
  346 games, 19,875 rows, 10,430 credits (1,187,193 left). William Hill and
  Fanatics quote no first-period total in the feed this season (0 of 362 games,
  against 1,365 for William Hill in 2025-26); BetRivers and espnbet are back. On
  2026-27 the rule finds 10 bets at any EV and 4 at 0.015 (`grid --market
  totals_p1 --fresh-source odds_api_nhl_totals_history --env-file ...`), where
  2025-26 found 309 and 131. Too few to grade.
- **Before the purchase, 2026-27 was not stored.** 16 games: the buyer
  (`data.ingestors.nhl_derivative_odds_history`) ran once, on 2026-10-03, and is
  not scheduled. Its dry run on 2026-11-21 measured 30.0 credits a game (61
  credits for the two-game probe): **344 scored games, about 10,370 credits**,
  balance 1,203,046 after the probe. The purchase was refused by this session's
  permission check and waits on mike (#1569). The live odds fetch does not collect
  `totals_p1` at all (every stored row is the buyer's), so there is no forward
  collection either.

## Regulation 3-way

| EV floor | bets | flat return | 2024 | 2025 | 2026 |
|---|---:|---:|---|---|---|
| 0.000 | 1,893 | +3.8% | +3.4 (961) | +1.9 (592) | +12.9 (272) |
| 0.010 | 1,511 | +4.4% | +3.7 (834) | +3.5 (456) | +14.4 (175) |
| 0.020 | 1,149 | +5.1% | +7.9 (692) | +0.0 (325) | +10.6 (96) |
| 0.040 | 578 | +10.0% | +8.0 (388) | +8.9 (146) | +68.5 (23) |

Pooled over 2023-24 to 2025-26 (the bet counts include the few 2026-27 bets
the thinned prices produce, which are not evidence). Median price +360 to +390:
nearly all draws. Every interval spans zero. One snapshot a game, so no closing
value.

## 2026-27 cannot be replayed from the stored prices

The odds clean-up (`data/prune_odds.py`) keeps only each non-DraftKings book's
opener and close once a game is a few days old. Pinnacle is protected in
`player_prop_odds` only (`PROTECTED_BY_TABLE`), not in `odds`, and NHL is not in
`PATH_KEPT_SPORTS` (the sports whose whole price path is kept). Measured
2026-11-21 on the local copy: CGY at EDM 2026-10-28 keeps 110 fetches but 2 with
Pinnacle; TBL at MIN 2026-11-07 the same; BUF at WSH 2026-11-19, not yet
cleaned, keeps 92. A replay of 2026-27 under the goalie gate (decide only after
both goalies are confirmed, from 2026-10-24; a one-off research run, not in
the committed script) finds 1 totals bet where
`nhl_over_under` wrote 15. So this season can only be read from the live
record, and the puck line has no out-of-sample season. Issue #1343 is the
standing item on the jobs that still delete data.

## Read

- **The puck line looks like the totals rule until two kill tests.** Same
  mechanism, the grading checks out, retail references lose, quotes are
  simultaneous, both sides and most books are positive. But ten nights carry
  most of its units and the power de-vig takes most of the rest. On both
  tests it is weaker than the rule we already run. Not established; not
  recommended to ship on this evidence.
- **The first-period total was the strongest number, and its book has left.**
  On 2023-24 to 2025-26 its interval clears zero on both de-vig methods, it
  survives losing its ten best dates, retail references do not reproduce it,
  and two of three seasons are strongly positive. But it was one book's
  unders, and in 2026-27 that book quotes no first-period total in the feed,
  so there is nothing to bet and nothing to grade.
- **Moneyline, team totals, alternate totals: nothing for this rule.**

## What would have to change

- **First period:** William Hill (or another book that prices the under the
  same way) quoting the market again. Collecting `totals_p1` in the live NHL
  fetch would show it the day it happens; the fetch does not collect it now.
- **Puck line:** a season it has never seen. That needs NHL's price path kept
  (NHL in `PATH_KEPT_SPORTS`, or Pinnacle protected in `odds`), so 2026-27 and
  later can be replayed at the live check rate.
- **3-way:** a season with more than one snapshot a game, kept, as above.

## Next mechanisms (the stuck ladder for the null markets)

1. **Team totals priced off the full-game total and moneyline.** Prediction: a
   soft book's team total lags a move in its own full-game total within the
   same fetch. Cheapest test: the same-fetch replay with the soft book's own
   implied team total (from its total and moneyline) as the reference.
2. **The puck line re-hung off the moneyline.** Prediction: when the moneyline
   moves and the -1.5 price does not, the -1.5 price is stale. Test: needs the
   price path (above).
3. **First-period under at books that copy the full-game over lean.**
   Prediction: books whose full-game over carries the margin price the P1
   under long. Test: blind P1 unders by book against blind full-game unders by
   book, on the 2023-24 to 2025-26 snapshot.
