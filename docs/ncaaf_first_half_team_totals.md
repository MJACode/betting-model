# NCAAF first-half and team-total prices, graded (2026-11-11)

mike, 2026-11-10, on the market audit's purchase question: *"Buy all"*. The
prices were bought that evening (`docs/ncaaf_market_audit.md` §7,
`data/ingestors/ncaaf_derivative_history.py`). This is what they say.

**Verdict: nothing clears.** No rule fixed in advance returns a profit on the
first-half moneyline, first-half spread, first-half total or either team
total, at either stored time of day, across 2023-2025. One cell looked
positive on a table fitted on two seasons and is negative on the same table
fitted on ten (§5). No model is built from this.

Harness: `scripts/ncaaf_search/audit_2026_11/deriv/` (run from that folder).
Reads the local copy of the database, never production.

## 1. The grid

Game-day read (13:55 UTC, median 6.6 hours before kickoff), 2023-2025, one
unit to win with risk capped at three, return on units risked, 95% interval
by resampling dates.

| Market | Settles on | Games graded | Books' margin | Every quote, both sides | A better price (R1p) | A better line (R2) | Against the full game (R3, R4) | Verdict |
|---|---|---|---|---|---|---|---|---|
| First-half moneyline | half-time lead, a tie is a push | 2,152 | 4.2% to 6.5% | 14,635 quotes, -3.7% [-4.8, -2.6] | 40 bets, -6.39 u | no line | 495 bets, -1.1% | nothing |
| First-half spread | half-time margin | 2,152 | 3.8% to 6.7% | 14,703 quotes, -4.8% [-5.6, -4.1] | 25 bets, +0.19 u | 691 bets, -6.2% | 406 bets, -5.6%; evening read 393 bets, -10.1% | nothing (§5) |
| First-half total | half-time points | 2,152 | 4.7% to 6.7% | 13,306 quotes, -3.9% [-4.9, -3.1] | 36 bets, -2.06 u | 588 bets, -2.7% | 637 bets, -0.4% | nothing |
| Home team total | home final points, overtime in | 2,233 | 3.9% to 7.9% | 12,948 quotes, -6.1% [-6.8, -5.4] | 46 bets, +7.39 u | 765 bets, -8.3% | both teams: over 927 bets, -7.6%; under 386 bets, -2.8% | nothing |
| Away team total | away final points, overtime in | 2,233 | 3.9% to 7.9% | 12,816 quotes, -6.6% [-7.3, -5.9] | 61 bets, -5.81 u | 779 bets, -3.4% | (the same row) | nothing |

"Every quote, both sides" is the dumb baseline: a bet on each side of every
main-line quote at the six books a pick may name. It loses the books' margin,
which is the check that the grading is right. The rules are §4; the last
column's first-half numbers are the table fitted back to 2015 (R4b).

## 2. The data

- **Bought:** 153,286 rows on 2,450 games, eight books (DraftKings, FanDuel,
  BetMGM, Caesars, BetRivers, Hard Rock, Bovada, Pinnacle), at two reads: the
  game-day morning (median 6.6 hours before kickoff) and the evening before
  (median 21.6 hours). 2,233 of the games have a final score. DraftKings
  posts a ladder of alternate team totals (up to 11 lines a team); the other
  books post one line.
- **Half-time scores did not exist.** They were built from play-by-play: the
  2025 season was stored, and 2015 to 2024 were pulled on the worker that day
  (`ncaaf_pbp_pull`, free; `ncaaf_plays` went from 293,383 rows to
  2,128,039). A game's half-time score is read two ways, the score on the
  last plays of the second period and the score on the first plays of the
  third, and used only when the two agree: 9,261 games over 2015-2025, and
  2,152 of the 2,233 games with bought prices (`h1_scores.py`).
  A maximum over the half is wrong: a score can appear and be taken back, and
  rows are not reliably in order.
- **Checked against ESPN's quarter scores** on 18 Saturdays, six a season:
  846 of 854 games agree (99.1%). The eight that differ are off by 1 to 28
  points on a side. A check, not a source: nothing from ESPN is kept
  (`h1_check_espn.py`).
- **A first-half moneyline tied at the half is a push.** The books' margin on
  it is the same as on their first-half spread (4.2% to 6.5%), which is what
  a two-way market with a refunded tie looks like; 8.0% of halves are tied.
- **The full-game number of the same minute** is the middle of the ten stored
  books at the read the quote was taken at (the audit's `q_hist`).

## 3. Baselines, by who the bet backs

Game-day read, every main-line quote at a deciding book (`deriv_rules.py base`).

| Market | Side | Quotes | Return |
|---|---|---|---|
| First-half spread | underdog, home / away | 2,862 / 4,595 | -1.0% / -2.9% |
| First-half spread | favourite, home / away | 4,480 / 2,750 | -7.0% / -8.1% |
| First-half moneyline | favourite, home / away | 4,612 / 2,942 | -1.8% / -5.2% |
| First-half moneyline | underdog, home / away | 2,680 / 4,387 | -3.3% / -8.7% |
| First-half total | over / under | 6,601 / 6,705 | -3.6% / -4.2% |
| Away team total, away is the underdog | over / under | 3,937 / 3,926 | -10.6% / -2.1% |
| Away team total, away is the favourite | over / under | 2,454 / 2,489 | -8.0% / -6.0% |
| Home team total, home is the underdog | over / under | 2,490 / 2,467 | -5.3% / -7.1% |
| Home team total, home is the favourite | over / under | 3,989 / 3,990 | -5.0% / -7.2% |

Two leans show and neither pays. First-half underdogs against the spread lose
less than favourites (51.2% of underdog quotes win; 52.4% is needed at -110).
The over on an away underdog's team total loses in every season (-106, -173,
-200 units) while its under loses 2.1%; taken at the best line and then the
best price, one bet a team, the under is 674-615, -9.31 units on 1,289 bets
(-0.6%, interval -6.0% to +4.7%), and by season -19.11, -6.45, +16.26. Not a
bet. This second lean was found in the table above, not fixed in advance.

The first-half moneyline's no-vig chance is right across the range (seven
bins from 12% to 88%, the largest gap 1.9 points).

## 4. The rules

All fixed before a result was read (`deriv_lab.py`, top of file), except R1p
and R4b, which were added the same day, each before it was run, and say so. One bet a game and market:
the best qualifying quote. Game-day read unless stated.

| Rule | First-half moneyline | First-half spread | First-half total | Home team total | Away team total |
|---|---|---|---|---|---|
| **R1** same line, a better price than the middle no-vig chance of the other books; edge above 0.01 | 21 bets, -7.76 u | 9 bets, +0.84 u | 34 bets, +4.64 u | 24 bets, +4.05 u | 34 bets, +0.28 u |
| **R1p** the same against Pinnacle alone; edge above 0.01 | 40 bets, -6.39 u | 25 bets, +0.19 u | 36 bets, -2.06 u | 46 bets, +7.39 u | 61 bets, -5.81 u |
| **R2** a line at least 1 point better than the other books' middle, price -125 or longer | (no line) | 691 bets, -6.2% | 588 bets, -2.7% | 765 bets, -8.3% | 779 bets, -3.4% |
| **R3** team total at least 1 point off (total -/+ spread)/2 of the full game | | | | over 927 bets, -7.6%; under 386 bets, -2.8% (both teams) | |
| **R4** first half priced from the full game, fitted on the bought seasons only (711 and 1,419 games); expected return above 0.04; tests 2024, 2025 | 618 bets, -7.7% | 301 bets, +6.7% | 597 bets, -0.1% | | |
| **R4b** the same, fitted on every earlier season back to 2015 (6,197 to 7,811 games); tests 2023, 2024, 2025 | 495 bets, -1.1% | 406 bets, -5.6% | 637 bets, -0.4% | | |

- **R1 and R1p find almost nothing to bet.** At the same line the six books
  price inside each other's margin: in three seasons no market has more than
  61 quotes a full point of chance better than the market, and those are flat.
  With the cut at zero R1 has 108 to 204 bets a market, returning -20.2% to
  +5.1%, and R1p 167 to 249, returning -13.6% to +0.6%.
- **R2: a better line at one book is not value.** Every cell is negative at
  0.5, 1.0, 1.5 and 2.0 points and at both reads, bar three cells of 62 to 102
  bets. The book standing off the market is as often the one that is right.
- **R3: team totals agree with the full game.** An underdog's team total sits
  0.29 points below (total + spread)/2 and a favourite's on it; teams go over
  49.2% and 50.2% of the time. Bets where a line strays 0.5 to 2.5 points lose
  1% to 8% in every cell with more than 50 bets.
- **R4 and R4b** are §5.

## 5. The cell that looked positive, and why it is not

R4 prices a first-half line from the full-game middle: first-half margin =
a slope x the full-game spread, first-half total = a slope x the full-game
total + a constant, with the spread of results around those taken from
earlier seasons as it fell. Fitted on the bought seasons only it had 711
games behind its 2024 table and 1,419 behind its 2025 table.

First-half spread on that short table, best quote a game, expected return
above the cut:

| Cut | Game-day read | Evening before |
|---|---|---|
| 0.00 | 889 bets, -8.75 u | 897 bets, -32.37 u |
| 0.02 | 580 bets, +8.94 u | 555 bets, -14.83 u |
| 0.04 | 301 bets, +16.62 u (+6.7%, interval -6.1% to +18.6%) | 298 bets, -2.14 u |
| 0.06 | 160 bets, +4.47 u | 146 bets, -5.62 u |
| 0.08 | 99 bets, -1.53 u | 90 bets, +4.07 u |
| 0.12 | 46 bets, -0.18 u | 41 bets, -0.71 u |

Both test seasons were positive at 0.04 on the game-day read (+8.79, +7.83).
It was never a bet as it stood: the interval spans zero, the neighbouring
cuts fall away, and the evening read of the same rule loses.

**Then the table was fitted properly.** Play-by-play for 2015 to 2022 was
pulled the same day, which gives half-time scores for 6,197 to 7,811 earlier
games (CFBD's closing spread and total as the full-game number in training)
and makes 2023 a third test season. Three forms, all fixed before the longer
table was run (`deriv_r4b.py`): leftovers pooled (R4b), leftovers by size of
spread and of total, and the repo's margin-distribution kernel (R4c).

| First-half spread, cut 0.04 | Game-day read | Evening before |
|---|---|---|
| R4b, pooled | 406 bets, -21.39 u (-5.6%) | 393 bets, -38.95 u (-10.1%) |
| R4b, by size | 374 bets, -11.65 u (-3.2%) | 403 bets, -37.93 u (-9.5%) |
| R4c, kernel | 332 bets, -17.29 u (-5.5%) | 346 bets, -34.15 u (-10.0%) |

Every cut from 0.00 to 0.08 is negative in all three forms at both reads.
By test season (pooled, 0.04, game-day read): -20.49, -0.38, -0.51.

**Why the short table said otherwise.** Its slope was 0.555. Season by season
the slope runs from 0.54 to 0.64 with a standard error of 0.02 to 0.03 each; over
2015-2022 it is 0.605 (plus or minus 0.018) and over 2023-2025 0.583 (plus or
minus 0.029). Two seasons could not tell 0.555 from 0.60, and the bets it
chose were the ones that difference picks out.

**What the long table says about the market.** Where it gives a first-half
spread quote a 52% to 55% chance, the quote won 49.8% (2,161 quotes); 55% to
60%, 52.6% (470). Totals: 51.0% and 53.6%. The first-half line already holds
what the full-game line holds. First-half totals priced this way come out
level (637 bets, -0.4%; kernel 549 bets, 0.0%), which removes the books'
margin and nothing more.

## 6. Asked of the data afterwards (not fixed in advance)

Read as questions, not results (`deriv_r4.py f`).

- **The first-half moneyline at the best price, one bet a game and side.**
  Home underdog 264-474 with 66 pushes, +15.67 units on 804 bets (+3.4%,
  interval -4.9% to +11.9%; by season +10.83, +9.31, -4.47). Home favourite
  -1.1% on 1,291, away favourite -3.8%, away underdog -5.9%.
- **Team totals at the best line then price, all eight corners.** The away
  underdog under is the best at -0.6%; the other seven are -2.9% to -8.5%.

## 7. Not tried, and why

- **DraftKings' alternate team-total ladder as its own market.** Its lines
  are in R1, R1p and R3 with every other quote; a ladder priced against a
  fitted scoring distribution was not built, because the main line shows no
  lean to anchor one on.
- **Quarters, and first-half team totals.** Not bought.
- **A closing price for these markets.** Only two reads a game exist, so no
  bet here can be scored against a close. The evening read against the
  game-day read is the only movement in the data.

## 8. What would have to change

- Nothing here points at a next test on these prices. The baseline loses the
  margin, the off-market quotes are not value, and the full-game line adds
  nothing to the first-half line. A bet in these markets would need
  information the full-game market does not have, which is where the
  full-game audit ended too.
- Nothing collects these markets as games are played: this week's games hold
  the full-game moneyline, spread, total and their alternates only
  (`latest_odds`, read 2026-11-11). No case is made here for starting.
- A first-half model that shipped would need half-time scores as a stored
  table for settling (`ncaaf_period_scores`, from ESPN's quarter scores or
  CFBD's line scores), not the play-by-play read used here, which is right
  99.1% of the time. `docs/followups.md`.

## 9. Reproduce

```
cd scripts/ncaaf_search/audit_2026_11/deriv
python extract_deriv.py          # the bought rows and the ledger, from the mirror
python h1_scores.py              # half-time scores from ncaaf_plays
python h1_check_espn.py 2025-09-06 2025-10-11 ...   # the ESPN check
python deriv_rules.py            # baseline, R1, R1p (r1p), R2, R3
python deriv_r4.py               # R4 and the two follow-ups
python deriv_r4b.py              # R4 on the longer table
```

`paths.py` one level up names the mirror and the cache
(`C:\Users\micha\ncaaf_research\data`).
