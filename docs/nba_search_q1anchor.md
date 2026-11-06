# NBA search: first-quarter player props anchored to the market's full-game number (pre-registered 2026-11-06, before any bet in it was graded)

mike, 2026-11-06: build an NBA first-quarter model that makes money. Every first-quarter search so far has failed
(`docs/nba_models_2026.md` section 13). The props search (`docs/nba_search_q1props.md`) priced each player from his own
box-score rate, and its points cells leaned the wrong way. No search has priced a first-quarter prop from what the
market already says about the same player's full game.

**Written before any bet was graded. Nothing below changes after a result is seen; a later change gets its own dated
line and reason.** Lab: `scripts/nba_s_q1anchor.py`. Pass/fail: `python -m scripts.nba_game2_verdict --results DIR
--house5` (section 9.1's bars of the record), then `python -m scripts.nba_s_q1anchor --verdict DIR` for the strict
season bar of section 6. No data is bought, no Odds API call is made, and the graded run is stored in Supabase
(`nba_game2_cells`) before anything reads it.

**What was read before this was written.** Prices, lines, books and timestamps, and how many first-quarter
propositions have a full-game quote from the same fetch (below). No mean was computed, and no result of any game was
read.

## 1. The idea

Pinnacle quotes no first-quarter prop, so no rule can measure a first-quarter price against a sharp one. **Pinnacle
does quote the same player's full-game points, rebounds and assists, in the same fetch.** That number already holds
everything the market knows about his game: his minutes, his role, tonight's injuries, the matchup. What it does not
say is how much of his game falls in the first quarter. That share differs by player: starters play 68% to 72% of the
first quarter against 62% to 64% of the game, and some play the whole quarter while others sit at the six-minute mark
(`docs/nba_search_starters.md` section 1).

So the first-quarter number is **the market's full-game number for him, times his own first-quarter share.** A book
that sets its first-quarter line as a flat share of its own full-game line, or from a full-game line that has not
caught up with Pinnacle's, is beaten by this number where the two disagree.

## 2. The population

The props search's propositions, unchanged: its quotes, its refusal rules in order (names, the 45-75 minute window,
prices, line ranges, a coherent two-way quote), its settlement from the plays of period 1 with every check, and its
voids (`docs/nba_search_q1props.md` sections 2-4; `scripts.nba_s_q1props.refuse_rows` and `with_props`, imported
unchanged). One-sided quotes are not in this search.

## 3. The anchor: the same player's full-game quote, same stat, same fetch

A full-game quote counts only when its `snapshot_at` equals the first-quarter quote's. The full-game quotes go through
the same name match the props searches use (`scripts.nba_prop_market_lab.build_quotes`, unchanged).

- **Kind P, Pinnacle.** Pinnacle's coherent two-way full-game quote (implied over plus implied under between 1.00 and
  1.15). Its proportional no-vig over at its line fixes the full-game mean through the negative-binomial table of the
  full-game searches (`PM.NBTable`, width `PM.nb_alpha` fitted on box scores of seasons strictly before the priced
  one).
- **Kind C, consensus, only where Pinnacle has no coherent quote.** Every other book's coherent two-way full-game quote
  in the same fetch (the bettable books and Bovada), each turned into a mean the same way; the median of those means.
  At least 3 books.
- A proposition with neither has no number and is not bet.

## 4. The share and the mean

- **The share** = his recency-weighted first-quarter minutes over his recency-weighted full-game minutes, both over the
  same earlier games: every stored regular-season game before tonight's date in which he had first-quarter court time
  and his team-game's lineup segments pass the props search's check. Half-life 3 such games (the rating engine's
  `min_hl`, used by the props and starters searches). Every season counts, and other teams. **Fewer than 3 such games
  means no number.**
- **The raw number** = the anchor's full-game mean × the share.
- **The first-quarter factor**, one per stat, anchor kind and priced season: the sum of actual first-quarter stats over
  the sum of raw numbers, on the fit rows of 2023-24 up to the season before the priced one (2023-24 is priced with its
  own and is never graded). It absorbs how a first-quarter minute differs from an average one, and any level bias in
  the anchor. **The mean** = raw × factor.
- **The fit rows**, per stat and kind: every regular-season player-game from 2023-24 on with an anchor of that kind,
  a share, first-quarter court time, and its game kept for that stat by settlement. The anchor of a proposition is from
  its own fetch. A player-game with no first-quarter quote takes its anchor from the game's latest full-game fetch 45-75
  minutes before tip. For kind C, a row with Pinnacle present still fits, using the consensus. 2023-24 holds no
  first-quarter price, so every 2023-24 row is of the second sort.
- **The distribution**, fitted walk-forward on the same fit rows with this mean (`scripts.nba_s_q1props.walk_forward`,
  unchanged): points through the per-line map of the props search's section 14, a line the map lacks through the
  negative binomial; rebounds and assists through the negative binomial.
- EV = the chance of the side × the decimal price − 1.

## 5. The cells (36)

| Family | Anchor | Markets | Sides | Cut on EV | Cells |
|---|---|---|---|---|---|
| Q1AP | Pinnacle | first-quarter points, rebounds, assists, each its own | over, under | ≥ 0.02 / 0.04 / 0.06 | 18 |
| Q1AC | consensus, Pinnacle absent | the same | over, under | ≥ 0.02 / 0.04 / 0.06 | 18 |

- **Price:** the best-EV offer among the deciding books that quote the proposition (`config.BEST_LINE_BOOKMAKERS`),
  at each book's own line, a coherent two-way quote, −200 floor. One bet per (game, player, market). No game or night
  cap. One unit to win, risk capped at 3. No line is whole, so no push.
- **The cuts** are the props search's, fixed before any mean was computed.
- **Bands (bar 5)** along EV within one family, market and side: [0.00, 0.02), [0.02, 0.04), [0.04, 0.06), 0.06 and
  up. The band just below the cut and every band from the cut up must be positive where they hold 30 or more bets.

## 6. Seasons and bars

- **Graded and pooled: 2024-25 and 2025-26.** 2024-25 is the choosing season the placebo reads. Nothing is chosen on
  it: the cuts are fixed.
- **Section 9.1's house standard, unchanged:** 200 or more pooled bets; the pooled whole-day bootstrap 95% interval
  above zero (4,000 resamples, seed 7); seasons positive; beats the blind bet on its dominant side, pooled; the bands;
  the choosing season's return above the 95th percentile of 200 placebo runs.
- **The season bar is read strictly, as the props search read it: both seasons, each with 30 or more bets,
  positive.** `--verdict` prints both readings; the stricter one is this search's.
- **The blind bet (bar 4):** the cell's side on every proposition in its own population, no model and no cut, at the
  best deciding offer by that book's own proportional no-vig price.

## 7. The placebo: 200 runs, seeds 1-200

The house placebo of the props search (its section 9), unchanged, run within each anchor kind: each proposition's
disagreement with the book (its mean over its main line) moves to another proposition on the same date in the same
market, and its offers are re-priced at their own lines. A (date, market) with fewer than 5 propositions joins the
other thin ones of its season and market. With the identity permutation the run returns exactly the real bets (a test
asserts it). This moves everything the model knows about a proposition, the anchor's view and the share together,
because a real edge from either is a real edge.

## 8. Controls, graded and reported, never judged

| Control | What |
|---|---|
| `control_league_P`, `control_league_C` | the same cells with the share replaced by 1: the market's full-game number times one factor per stat. If the registered cells do no better, the player's own share added nothing |
| `control_blind` | every proposition, each side, no model, at the best offer by its book's no-vig price |

**Expected passes by chance:** 36 × 0.025 ≈ 0.9 cells clear the interval alone, before correlation. The cuts are
nested and the markets share players, so the cells are far from independent.

## 9. Reported beside every cell, never a bar

- The prices each cell lays: minimum, 5th percentile, median, 95th percentile, maximum.
- Each book alone, and each season apart.
- Overlap with the live full-game prop models (`nba_prop_market`, `nba_prop_projection`): the share of the cell's bets
  on a (game, player) where either bet any full-game prop, the same stat, and the same stat and side.

## 10. The counts this was written on (prices only, read 2026-11-06)

First-quarter propositions with a coherent quote and kept by settlement, and how many have a full-game quote from the
same fetch:

| Season | Market | Propositions | Pinnacle full-game, same fetch | 3+ other books, same fetch (all propositions) |
|---|---|---|---|---|
| 2024-25 | points | 9,267 | 7,720 | 97% of points propositions over both seasons |
| 2024-25 | rebounds | 9,162 | 3,939 | 94% |
| 2024-25 | assists | 9,106 | 4,183 | 77% |
| 2025-26 | points | 8,626 | 8,022 | |
| 2025-26 | rebounds | 2,679 | 1,119 | |
| 2025-26 | assists | 2,540 | 950 | |

The full-game quotes come from the shared research cache (`nba_props`, 76,577 Pinnacle points, rebounds and assists
rows from 2023-10-25 on). The first-quarter fetch is the full-game fetch: the same `snapshot_at` on every proposition
that has both.

## 11. What a pass means

A pass goes live (CLAUDE.md section 2) with its own EV floor at its cut and the prices it lays stated first. The live
feed captures no first-quarter prop today, so a pass needs that capture added to the NBA prop fetch, in the same event
call as the full-game props, so the anchor and the first-quarter quote share a fetch live as they do here.

## 12. Counts before grading (2026-11-06, `--counts`, no bet graded)

The synthetic checks pass (84 rows: 36 cells and 48 controls through the harness, the placebo's identity run equal
to the real bets). One fix before this run, committed on its own: the proposition's fetch time is read as UTC (the
props search's `with_props` stores it without a zone, and the join to the anchor refused to run).

- **Fit rows:** 199,389 player-games with first-quarter court time (2023-24 65,706; 2024-25 66,123; 2025-26 67,560),
  196,920 with a share. With a Pinnacle anchor: 23,400 / 24,552 / 24,784; with a consensus anchor: 38,465 / 41,695 /
  43,189.
- **The share** (5th, 25th, 50th, 75th, 95th percentile): 0.194, 0.237, 0.261, 0.287, 0.333.
- **The first-quarter factor** (anchor × share against the actual first-quarter stat, before any factor): points
  0.951 / 0.960, rebounds 1.011 / 1.009, assists 1.071 / 1.054 (Pinnacle; pricing 2024-25 / 2025-26); consensus
  0.955 / 0.964, 0.997 / 1.000, 1.074 / 1.061. The league control's factor is about 0.26 for points, 0.27 for
  rebounds and 0.28 for assists.
- **Negative-binomial width** (pricing 2024-25 / 2025-26): rebounds 0.025 / 0.024 (Pinnacle), 0.034 / 0.031
  (consensus); assists 0 (Poisson). Points price through the line map.

The bets each cell would place (2024-25 + 2025-26), and the prices they lay (minimum / median / maximum):

| Family | Market | Side | EV 0.02 | EV 0.04 | EV 0.06 | Prices at 0.02 |
|---|---|---|---|---|---|---|
| Q1AP | points | over | 3,428 (1,525 + 1,903) | 2,598 | 1,914 | −200 / −105 / +170 |
| Q1AP | points | under | 3,788 (1,945 + 1,843) | 3,013 | 2,407 | −190 / −110 / +165 |
| Q1AP | rebounds | over | 629 (492 + 137) | 425 | 303 | −200 / +100 / +175 |
| Q1AP | rebounds | under | 662 (499 + 163) | 469 | 339 | −200 / −119 / +175 |
| Q1AP | assists | over | 729 (597 + 132) | 513 | 345 | −200 / +105 / +325 |
| Q1AP | assists | under | 481 (379 + 102) | 332 | 237 | −200 / −125 / +184 |
| Q1AC | points | over | 520 (395 + 125) | 424 | 327 | −190 / −110 / +178 |
| Q1AC | points | under | 370 (261 + 109) | 277 | 221 | −185 / −110 / +165 |
| Q1AC | rebounds | over | 516 (404 + 112) | 329 | 222 | −200 / −105.5 / +260 |
| Q1AC | rebounds | under | 525 (374 + 151) | 356 | 244 | −200 / +105 / +185 |
| Q1AC | assists | over | 754 (583 + 171) | 484 | 315 | −195 / +115 / +400 |
| Q1AC | assists | under | 139 (99 + 40) | 91 | 63 | −200 / +100 / +175 |

2025-26 holds far fewer coherent rebounds and assists quotes than 2024-25 (most of that season's are one-sided Hard
Rock quotes), so several rebounds and assists cells have under 30 bets in 2025-26 at the higher cuts and cannot meet
the strict season bar. That is a property of the data, stated before the grade.

## 13. Results (graded 2026-11-06, run `2026-11-06-q1anchor`)

Stored in Supabase before it was read: 84 rows in `nba_game2_cells` (36 cells, 48 controls). The grade took 11
minutes.

**0 of the 36 cells pass.** 5 clear the 95% interval alone, against about 0.9 expected by chance. All 5 are in the
consensus family, and each of the 5 fails only the bands bar.

**The Pinnacle-anchored family (Q1AP) has nothing.** Its best cell with 200+ bets is points over at EV 0.04: 2,598
bets, +1.7%, interval −2.1% to +5.5%. Assists overs lose 3.9% to 4.5%, and rebounds unders lose 3.8% to 8.3%.

**The consensus family (Q1AC): players with no Pinnacle full-game quote, anchored on the soft books' median.**

| Cell | Bets | Units | Return | 95% interval | 2024-25 / 2025-26 | Blind | Placebo 95th pct (choosing season) | Fails |
|---|---|---|---|---|---|---|---|---|
| assists over, EV 0.02 | 754 | +54.4 | +7.9% | +0.1% to +15.8% | +9.3% on 583 / +3.8% on 171 | −3.8% | −0.1% against +9.3% | bands |
| assists over, EV 0.04 | 484 | +45.5 | +10.4% | +2.1% to +19.0% | +10.8% / +9.3% | −3.8% | −0.3% against +10.8% | bands |
| assists over, EV 0.06 | 315 | +52.7 | +19.3% | +8.9% to +30.1% | +17.1% / +26.3% | −3.8% | −0.4% against +17.1% | bands |
| rebounds under, EV 0.04 | 356 | +38.6 | +10.0% | +0.9% to +19.3% | +7.2% / +16.0% | −8.3% | −3.8% against +7.2% | bands |
| rebounds under, EV 0.06 | 244 | +39.9 | +15.0% | +3.7% to +26.1% | +15.2% / +14.6% | −8.3% | −3.2% against +15.2% | bands |

- **Why they fail the bands bar.** Assists overs by EV band: 0.00-0.02 +5.8% on 311, 0.02-0.04 +3.5% on 270, **0.04-0.06
  −4.4% on 169**, 0.06 and up +19.3% on 315. One band below each cut loses, and the bar needs every band from the one
  below the cut up to be positive. Rebounds unders: 0.00-0.02 −4.8% on 246, 0.02-0.04 −4.0% on 169, 0.04-0.06 −1.1% on
  112, 0.06 and up +15.0% on 244. Every band below 0.06 loses, which is the shape of a peak.
- **The control says the player's own share matters for assists.** With the share replaced by one factor, the same
  assists-over cells return +5.1% to +5.4%, and every interval reaches below zero (lower ends −1.3% to −3.9%). The rebounds-under control loses (−0.4% to −3.8%).
- **Where the assists-over bets are.** 2024-25: Hard Rock (503 of 583 at EV 0.02, +10.4%) and Caesars (80, +3.9%).
  2025-26: BetMGM (170 of 171, +4.5%). None of these bets is on a player and stat the live full-game prop models bet;
  91% are on a (game, player) where they bet something else.
- **The rebounds-under bets overlap the live under model:** 61% to 63% are on the same player, stat and side as a live
  full-game prop bet. Most of their return is that model's lean carried into the first quarter.
- **Prices laid.** Assists overs, EV 0.02: −195 to +400, median +115, 5th to 95th percentile −154 to +220. Rebounds
  unders: −200 to +185, median +105.
- 54-minute fetches made the return; the few 64-minute fetches (48 assists-over bets at EV 0.02) made nothing.

**Answer: first-quarter props anchored on Pinnacle's full-game number are closed. Anchored on the soft books' number,
for players Pinnacle does not quote, assists overs clear five of six bars at every cut and fail the bands bar on one
band of 169 bets. Nothing is built from this search without the owner's decision to ship a cell that failed a bar.**

## 14. Would the near miss bet live? (measured 2026-11-06, after the grade)

The 2026-27 first-quarter props were bought for the season so far: 123 games at tip minus 60 minutes, 3,387 rows,
3,616 credits (`nba_odds_history --q1-props --seasons 2027 2027`; balance after, 964,593). Which books quote them:

| Market | Books (quotes, two-sided) |
|---|---|
| assists | Hard Rock only (403, 402 two-sided; 118 games) |
| rebounds | Hard Rock only (717, 700) |
| points | FanDuel (1,126, all) and Hard Rock (1,141, 1,117) |

BetMGM, which carried 170 of the 171 near-miss bets in 2025-26, quotes none. **Of Hard Rock's 402 two-sided
first-quarter assists quotes, 392 are on a player with a Pinnacle full-game assists quote in the live feed in the 75
minutes before tip, and 1 has no Pinnacle quote and three or more other books.** The consensus family's population is
players Pinnacle does not quote; live, with the feed fetching many times before tip, Pinnacle quotes almost everyone,
so the near miss would place about one bet in 16 days. The live population is the Pinnacle-anchored family's, which
found nothing. **Nothing from this search can be built.**
