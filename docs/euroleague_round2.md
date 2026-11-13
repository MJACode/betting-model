# EuroLeague research, round 2 (2026-11-13)

Run by a read-only research agent on the local parquet cache
(`C:\Users\micha\euroleague_research\cache`). No paid call, no database, no
API key, no .env (none exists in the checkout: `ls .env` -> "No such file").
Scripts: `scripts/euroleague_research/r3_*.py` in `bm-euroleague-fix`. Every
table below names the script that printed it.

## 0. Frozen before any return was read (written 2026-11-13, before the first r3 script ran)

### 0.1 Common rules

- **Data state.** games.parquet: 2026-27 has 107 played games, the last on
  2026-11-12; period_quotes last stamp 2026-11-12 19:45 UTC; fullgame_quotes
  last stamp 2026-11-13 05:45 UTC. **These are the same 107 games round 1
  read.** Every "hold-out read on 2026-27" below therefore re-reads games
  round 1 already had in view; there is no unseen game in the cache. Those
  reads are reported as "no new games since round 1", not as new evidence.
- **Books.** Decidable (a pick may name): draftkings, fanduel, betmgm,
  betrivers, fanatics. Reference only: pinnacle, bovada, marathonbet,
  unibet, paddypower (full game); betus, gtbets, mybookieag (periods).
- **Stake.** 1 unit to win, risk capped at 3 (p<0: risk=min(|p|/100,3),
  win=risk*100/|p|; p>0: risk 1, win p/100). Pushes return the stake.
  Return = units / units risked on graded bets. Interval 90%, resampling game
  dates, 1,000 draws, seed 7 (`r1_lib.summary`).
- **Full-game board at T**: `r2_lib.board_at` (last change-only row with
  snapshot_at <= T). Close = the last ledger snapshot <= tip - 10 min. First
  post = a book's first row. Coherent quotes only (`r2_lib.load_quotes`).
  Neutral-site games out of every "home" experiment.
- **Period quotes**: main markets at mark T-10 (the close) unless stated.
  A spread/total main quote is set aside as a rung when either side's no-vig
  probability is outside [0.35, 0.65] (`r1_lib` OFFC) **or** its number sits
  2+ points from every other book's main number at the same mark (when at
  least one other book quotes). Two-way period moneylines: a tie pushes.
  Same-line rule: the modal decidable number at the mark (ties nearest the
  median, then the lower), the best decidable price on it.
- **Moneyline floor**: every side shorter than -200 is removed BEFORE the
  best price is picked, wherever a moneyline is bet (unfloored only where
  stated).
- **Early / late**: within each season, before / on-or-after the median
  date of that season's bets.
- **"Earlier game"** in every prior-games feature (attendance, rest is
  exact, referee scores, club shares) = a game tipping at least 3 hours
  before this game's tip (a game tipping two hours earlier the same evening
  has not finished at this game's close). Fixed with the rest of section 0,
  before any result.
- **Kill tests on every positive headline cell**: by season, early/late,
  side split, price band, without its 10 best dates, the cut neighbourhood,
  a placebo where one exists, Benjamini-Hochberg. Price range (median,
  shortest, share shorter than -300 and -500) for every positive cell.
- **The bar (stricter, `kill-tests.md`)**: pooled walk-forward 200+ bets
  with the 90% interval above zero; 2+ seasons of 30+ bets, all positive;
  both halves positive; neighbouring cuts positive on both sides; no side
  above 70%; positive without its 10 best dates; placebo below the real
  result; survives BH at 10%.
- **Multiplicity (BH, 10% false-discovery rate, one-sided p from the date
  bootstrap, `r2_lib.p_one_sided`)**: the cells that count are every cell of
  every pre-registered cut grid or band list at the experiment's MAIN price,
  pooled over its graded seasons; kill-test sub-rows (season, early/late,
  best-10, side) do not count. Planned count: A1 15, A2 10, A3 1, B 42,
  C 14, D 24, frozen first-quarter lead 1 = **107** (the script prints the
  real count).

### 0.2 A. The home lean

- **A1. Home moneyline at the full-game close, -200 floor** (home price -200
  or longer). Main price: DraftKings close (the only decidable book every
  season, 2021-22 to 2026-27). Second read: the best decidable close
  (2025-26 on adds four books). Bands (fixed now): -200..-151, -150..-121,
  -120..-101, +100..+150, +151..+250, +251 or longer. A blind rule has no
  fit, so "walk-forward" is the by-season table; plus one walk-forward band
  rule fixed now: in season s (2022-23 on) bet home only in the bands whose
  return at the DraftKings close over every earlier season (from 2021-22)
  was > 0. Descriptive (no bet): home win rate against Pinnacle's
  power-de-vigged close by season, all prices.
- **A2. First-half home**, mark T-10, seasons 2025-26 and 2026-27
  separately and pooled: home first-half spread at FanDuel, at BetRivers,
  and at the best of the two on the same-line rule; home first-half
  moneyline (-200 floor) at FanDuel, BetRivers and the best of the two.
  Split of the best-price rows by home underdog / home favourite (spread:
  home line > 0 / < 0; moneyline: home price > +100 / < -100).
- **A3. The frozen round-1 lead, read unchanged**: home underdog against the
  spread at the DraftKings close, home line > 0, own-country games only (not
  neutral, not the relocated lists R1/R2/excluded of `r2_leads.py`),
  2026-27. Expected to reproduce round 1's 2026-27 row (30 bets) exactly.

### 0.3 B. Market-anchored logistic model (moneyline) and anchored residual model (spread)

- **One row per game**, own-country and relocated games both in (neutral
  out), seasons 2021-22 to 2026-27. Games with no Pinnacle close in the
  market are dropped (counted).
- **Moneyline**: logit P(home wins) = logit(Pinnacle power-de-vigged home
  probability at the close) [offset, coefficient fixed at 1] + X b.
  **Spread**: predicted home margin = -(Pinnacle closing home spread) + X d;
  P(home covers at line L) = Phi((pred + L) / sigma), sigma = SD of
  (margin + Pinnacle spread) on the training seasons; pushes out of the fit.
- **Inputs X** (each column standardised on the training seasons; every
  coefficient penalised, L2):
  1. home: a constant 1 (it is the home dummy; every row is the home side);
  2. home underdog: Pinnacle no-vig home P < 0.5 (moneyline) / Pinnacle home
     spread > 0 (spread);
  3. attendance: log(1 + the home club's mean attendance over its earlier
     home games this season and last season, audience > 0 only, the current
     game excluded), plus a missing flag (no earlier game with audience >
     0); the missing value is the training mean, never 0. The game's own
     attendance is NOT an input (measured at the game);
  4. venue: (a) the venue differs from the club-season's most common venue
     (the brief's definition; the season's arena schedule is published before
     the games, but relocations decided mid-season make this partly
     hindsight, flagged); (b) the venue is on the name-derived relocated
     lists R1 or R2 (`r2_lib` docstring);
  5. rest: days between each club's previous EuroLeague tip and this tip
     (rounded), within the season; the minimum stored is 2 days, so
     "back-to-back" = "short rest" = 3 days or fewer, one flag per club;
     rest difference = clip(home, 2, 8) - clip(away, 2, 8); a club's first
     game of the season gets a missing flag and rest 7;
  6. double-round week: the ISO week (local game_date) holds 2+ distinct
     regular-season rounds; and, per club, the game is its second of that
     week.
  7. Travel: **not derivable** from the stored data (no coordinates stored,
     only venue names). Parked; not hand-typed.
- **Fit**: ridge logit (moneyline) / ridge least squares (spread) with the
  offset; penalty from {0.3, 1, 3, 10, 30, 100, 300, 1000} by
  leave-one-season-out log loss (MSE for the spread) on the training seasons
  only. **Walk-forward**: graded seasons 2023-24, 2024-25, 2025-26, 2026-27,
  each fitted on every earlier season from 2021-22 (2022-23 is not graded:
  one training season leaves no leave-one-season-out).
- **Bet**: edge = model P(side) - the decidable book's no-vig P(side)
  (power de-vig for moneylines, multiplicative for spreads). Main price: the
  DraftKings close (moneyline -200 floor before the pick; one bet a game,
  the larger-edge side). Second read (moneyline): the best decidable close,
  the largest edge over decidable books. Cut grid 0.00, 0.01, 0.02, 0.03,
  0.04, 0.05; **headline 0.02**.
- **Rows**: the market-alone control (offset only, X b = 0: then the edge
  is Pinnacle against DraftKings); the full model; the full model minus one
  group at a time (at the headline cut); log loss / Brier against the
  market-alone row on the graded games.
- **Placebo**: the model's X b shuffled across the graded games of each
  season, 200 times, at the headline cut.

### 0.4 C. Totals

- **Residual** r = actual total (overtime in) - closing total, closing total
  = Pinnacle's close, else DraftKings' close (counted). Seasons 2021-22 on.
- **Per-referee score**: for referee j before game g, S_j = (sum of r over
  j's earlier games) / (n_j + 30). Crew score = mean of the crew's three S_j.
  **Exact-crew score**: the same trio's earlier games, sum r / (n + 10).
  Earlier = tip strictly before this game's tip.
- **Out-of-sample test**: per graded season (2022-23 on), the slope of r on
  the crew score (with its SE) and the correlation; pooled.
- **Bet rule** at the DraftKings closing total: over when the score >= +c,
  under when <= -c; c grid 0.5, 1.0, 1.5, 2.0 points; **headline 1.0**.
  Both scores. Placebo: crew scores shuffled across the season's games, 200
  times.
- **The opening total**: DraftKings' first-post over and under, blind, by
  season. **Line movement** m = DraftKings close total - DraftKings first-post
  total (same book): the correlation of m with (actual - DraftKings close);
  bet rule "follow" at the DraftKings close (over when m >= +k, under when
  m <= -k), k grid 1, 2, 3, 4; **headline 2**. The hindsight ceiling (betting
  the first post in the direction of the later move) is printed as a ceiling,
  not a rule.

### 0.5 D. First half and first quarter: three mechanisms of our own per market

Graded at the decidable books, mark T-10, seasons 2025-26 and 2026-27; the
offshore books on 2023-24 and 2024-25 printed as reference only (never a
bet). Full-game anchor = Pinnacle's ladder fair total at the SAME fetch (mark)
as the period quote (`r1_fullgame.py` part B, rebuilt in memory), else
Pinnacle's main full-game total on the board at the period quote's
snapshot, else DraftKings' (counted).

**First half**

- **H1-i Club-pair first-half share.** *Mechanism*: the books hang the half
  at about 50.1% of the full-game total for every pair; clubs that rotate
  early, press, or foul late make the half's share of the total a club
  property. *Prediction*: a prior-games-only club share predicts the half
  total beyond the book's number; over when share x full-game total - the
  book's half line >= m, under when <= -m. *Experiment*: share = h1 total /
  full-game total (overtime in) per game; club deviation = mean(share -
  league mean) over the club's earlier games (home or away, from 2020-21),
  shrunk n / (n + 40); pair share = league mean of earlier games + home dev
  + away dev. m grid 0.5, 1.0, 1.5, 2.0 points; **headline 1.0**. Placebo:
  the pair deviations shuffled across games, 200 times.
- **H1-ii The first-half moneyline's calibration (slope 0.877).**
  *Mechanism*: the half moneyline is derived from the full-game favourite and
  priced too short. *Prediction*: logit P = k x logit(no-vig P), k < 1,
  fitted on earlier seasons, beats the decidable price on the underdog.
  *Experiment*: k by maximum likelihood, no intercept, ties out, on every
  game of the earlier seasons (2023-24 on) with the median no-vig over every
  book quoting at T-10 (offshore included); graded 2025-26 (fit 2023-24 to
  2024-25) and 2026-27 (fit 2023-24 to 2025-26). Bet the side with
  P_shrunk - the decidable no-vig > cut, one bet a game (largest edge);
  cut grid 0.00, 0.01, 0.02, 0.03, 0.04; **headline 0.02**. **A shrink toward
  50% always favours the underdog**: the side split will read about 100%
  underdog by construction; the control row is the blind first-half
  underdog at the best decidable price on the same games.
- **H1-iii The stale derivative.** *Mechanism*: the book re-hangs the half
  total off the full-game total, but not every time the full game moves
  late. *Prediction*: when the full-game total moves between T-60 and T-10
  and the book's half line moves less than half of it, the half line is
  stale; bet the direction of the full-game move. *Experiment*: gap =
  0.5 x (Pinnacle ladder fair at T-10 - at T-60) - (the book's half line at
  T-10 - at T-60), per decidable book with on-centre quotes at both marks;
  over when gap >= m, under when <= -m, the largest |gap| per game; m grid
  0.5, 1.0, 1.5; **headline 1.0**.

**First quarter**

- **Q1-i Club first-quarter share.** As H1-i with the first-quarter total;
  m grid 0.25, 0.5, 0.75, 1.0; **headline 0.5**.
- **Q1-ii The first-quarter moneyline's calibration (slope 0.751).** As
  H1-ii on h2h_q1.
- **Q1-iii The stale derivative.** As H1-iii with 0.25 x the full-game move;
  m grid 0.25, 0.5, 0.75; **headline 0.5**.

**The frozen first-quarter under lead (round 1's P2)**, read unchanged:
`r1_method` V2 totals_q1, fitted on 2023-24 to 2025-26 (round 1: a = -7.826,
b = 0.2978 on 1,023 games; the fit must reproduce this before its grade is
read), T-10, decidable books, cut 0.02, graded on 2026-27. Round 1 read 4
bets there; the cache holds no later game, so this must reproduce exactly.
`r1_method` is run by its own code (`fit`, `decide`), with its full-game
input rebuilt in memory from `r1_fullgame.py` part B (no file written).

**Two departures, both made before the affected result was read, both
reported:** the "home dummy only" variant was added to both model tables as
the direct home-lean test (109 counted cells, not 107); and every
non-headline grid cell of the club-share rules whose interval came out above
zero got the same placebo and kill rows as the headline (one did: first
quarter, m = 1.0).

## Verdicts (written by hand from the tables below; each number is from the script named in its table)

**Nothing clears the bar.** 109 cells were counted for multiplicity. One
survives Benjamini-Hochberg at 10%, and it is a 3-bet cell (the first-quarter
moneyline shrink at cut 0.03, +5.65 units): below the 25-bet floor, so a
number, not a result. Of the 91 cells with 25+ bets, none survives. One new
lead is frozen (D, Q1-i at m = 1.0). The two frozen round-1 leads could not
get a true hold-out read: the cache holds no game after 2026-11-12, the same
107 games of 2026-27 that round 1 read.

### A. The home lean

- **A1, home moneyline at the DraftKings close, -200 floor**, 2021-22 to
  2026-27: 972 bets, +59.64 units, +4.89% [-0.68, +10.39]; at the best
  decidable close 984 bets, +5.24% [-0.27, +11.08]. Price range: median
  -110, shortest -200, longest +550, none shorter than -300. *Passed*: early
  (+4.56%) and late (+5.22%) halves; 5 of 6 seasons positive. *Failed*: the
  interval reaches below zero; +0.29% without its 10 best dates; 2026-27
  -18.50% on 61 bets; BH (p 0.071); the bands do not rise in order (-200..-151
  -5.55% and +100..+150 -3.50% sit between the winning bands); one side by
  construction (the away side under the same floor: 1,572 bets, -13.84%).
  The walk-forward band rule: 433 bets, +3.68% [-5.73, +12.66], 2026-27
  -19.84%. Descriptive: home teams won 63.62% against Pinnacle's 60.27%
  no-vig close over 1,520 games of 2021-22 to 2025-26, and 54.21% against
  59.64% on the 107 games of 2026-27.
- **The A1 cells with an interval above zero, all read off the band table**:
  +151..+250, 172 bets, +44.20 units, +25.70% [+7.33, +43.53]: two seasons
  negative (2022-23 -28.44%, 2023-24 -8.77%), 2021-22 carries 27.70 of the
  44.20 units, +7.79% [-9.52, +24.34] without its 10 best dates, the band
  beside it loses, BH fails (p 0.0090). -120..-101, 137 bets, +14.91%
  [+2.11, +28.16]: 2024-25 -21.08%, 2025-26 carries 15.99 of 22.72 units,
  +7.03% without its 10 best dates, BH fails. Home underdogs at +100 or
  longer (post hoc), 429 bets, +11.81% [+0.15, +24.03]: three of six seasons
  negative, +0.88% without its 10 best dates, its +100..+150 half loses.
- **A2, the first half (2025-26 and 2026-27)**: home first-half spread at the
  best of FanDuel/BetRivers, 417 bets, -24.30 units, -5.15% [-13.13, +2.47]
  (2025-26 -8.44%, 2026-27 +4.53%); home first-half moneyline, 275 bets,
  -1.91% [-11.31, +6.65]. Home underdog on the first-half moneyline, 99
  bets, +12.56% [-7.39, +34.02], 2026-27 -4.58%, -15.96% without its 10 best
  dates. Home favourite on the first-half spread, 299 bets, -8.69% [-17.42,
  -0.06]. Null.
- **A3, round 1's frozen home-underdog spread rule**: reproduced exactly (454
  bets, +48.34 units, +9.72%). Its 2026-27 read: 30 bets, 12-18, -8.10
  units, -24.06% [-49.70, +1.39], the same 30 games round 1 read.

### B. The market-anchored models

- **Moneyline**: leave-one-season-out picked the largest penalty in the grid
  (1,000) in 3 of 4 graded seasons, and the full model's log loss equals the
  market's (0.6075 on 1,121 games, +0.0001). At the DraftKings close, cut
  0.02: 159 bets, -7.18 units, -4.13% [-19.71, +12.67]; the cut grid 0.00 to
  0.05 reads -5.68, -4.13, -4.13, -21.81, -9.61 and +10.19% (22 bets). The
  market-alone control (Pinnacle against DraftKings) at 0.02: 33 bets,
  -14.98%. Best decidable close: 338 bets, -8.26%. Placebo: 42% of shuffles
  at or above the real result. "Home dummy only": 585 bets, +2.35% [-4.81,
  +9.31]. Null.
- **Spread**: full model, DraftKings close, cut 0.02: 428 bets, +4.44 units,
  +0.95% [-7.07, +8.60]; every cut positive (+0.18 to +5.76%), every interval
  through zero; mean squared error 134.72 against the market's 135.41.
  *Failed*: the interval; 2026-27 -23.92% on 60; -5.62% without its 10 best
  dates; 82.5% home; placebo 27% of shuffles at or above it; BH. No input
  group's removal moves the result beyond noise. Null.
- **Travel** could not be built: no coordinates are stored.

### C. Totals

- **Referee crews**: the per-referee score's out-of-sample slope was +2.43
  points per point (t 2.83) in 2022-23, then -0.07, +0.52, -1.04, -0.67;
  pooled +0.45 (SE 0.47) on 1,480 games. The exact-crew score: pooled -1.42
  (SE 1.27). The rule at the DraftKings close, c = 1.0: 466 bets, +6.63
  units, +1.31% [-5.52, +8.09]. *Failed*: 81.5% overs, 2025-26 -12.09%, late
  half -6.09%, -3.63% without its 10 best dates, placebo 9% of shuffles at
  or above it, BH. Exact crew at 1.0: 43 bets, -27.26%. Null.
- **The opening total**: DraftKings' first-post overs, 1,772 bets, -1.38%
  [-5.48, +2.53]; unders -7.69% [-11.68, -3.64], negative in every season.
  The margin sits on the under; no blind side makes money.
- **Open-to-close movement**: slope of (actual - DraftKings close) on
  DraftKings' own move +0.020 (SE 0.19) on 1,772 games. Following the move
  at k = 2: 659 bets, -4.35%; fading it: -4.72%. The hindsight ceiling
  (DraftKings' first post bet in the direction of its later move, perfect
  foresight): 1,524 bets, +101.74 units, +6.07% [+2.36, +9.73]. A forecast
  of the move can earn at most about 6%.

### D. First half and first quarter (the invention floor: three mechanisms each, all run)

- **H1-i, club-pair first-half share**: m = 1.0, 118 bets, +11.05 units,
  +7.77% [-7.72, +21.94]. *Failed*: the interval, -12.44% without its 10 best
  dates, placebo 14% of shuffles at or above it, the offshore reference on
  2023-24 and 2024-25 negative at every m (-11.03% on 158 at 1.0). Null.
- **Q1-i, club first-quarter share**: the headline m = 0.5, 191 bets,
  -3.68%. **m = 1.0 (the top of the grid, not the headline): 63 bets, 43-20,
  +17.71 units, +22.23% [+4.08, +39.66].** *Passed*: placebo (1% of
  shuffles at or above it), side split 54% over / 46% under, both halves
  positive (+14.26%, +30.36%), both seasons positive (2025-26 +21.38% on 53,
  2026-27 +26.89% on 10), +4.46% without its 10 best dates. *Failed*: 63
  bets against the 200-bet bar; one season with 30+ bets, not two; BH (p
  0.0188); no plateau (m = 0.75 +4.44%, m = 0.5 -3.68%, nothing above 1.0);
  not the pre-registered headline; the offshore reference at 1.0 is +2.54%
  on 129, 97.7% unders. Price range: median -122, shortest -145, none
  shorter than -300. **Frozen as a lead**, to be read on games after
  2026-11-12.
- **H1-ii, the first-half moneyline shrink**: k fitted on the earlier seasons
  came out ABOVE 1 (1.233 on 552 games for 2025-26, 1.064 on 942 for
  2026-27). The fit used the median no-vig over every book quoting, and the
  earlier seasons available to it are priced only by the offshore books
  (2023-24, 2024-25) plus 2025-26 for the second read; round 1's 0.877 was
  measured on the decidable books. So what failed is narrower than round 1's
  claim: **the shrink did not reproduce when fitted on the stored earlier
  seasons.** The pre-registration's "a shrink always favours the underdog"
  was wrong because k came out above 1: the rule bet favourites (92%) and
  lost, cut 0.02 150 bets, -42.68 units, -17.00% [-27.52, -6.30]. The blind
  first-half underdog at the best decidable price: 397 bets, +1.86%
  (2026-27 -16.86%). Not tested: k fitted on 2025-26's decidable prices
  alone and read on 2026-27.
- **Q1-ii, the first-quarter moneyline shrink**: k 0.937 and 0.873; cut
  0.02, 19 bets, -16.84%; cut 0.00, 402 bets, -3.21% [-12.66, +5.75]. Null.
- **H1-iii and Q1-iii, the stale derivative**: on the 832 decidable
  first-half quotes held at both T-60 and T-10, Pinnacle's full-game total
  had moved on 71.3% but by a mean 0.21 points, and the book's own half line
  had moved on 7.6%, so a one-point gap is rare (4.9%). First half m = 1.0: 39 bets, +6.99% [-17.87,
  +29.88], 2025-26 -32.54%, 2026-27 +34.60%. First quarter: 12 bets. Null on
  this window; too few bets to say more.
- **P2, round 1's frozen first-quarter under lead**: the fit reproduced
  exactly (a -7.83, b 0.30 on 1,023 games; pooled 59 bets, +10.85 units,
  +14.96%). Its 2026-27 read: 4 bets, 3-1, +1.80 units, the same 4 round 1
  read.

### What to try next

1. Read the three frozen leads only on games after 2026-11-12, unchanged:
   round 1's home underdog against the spread, round 1's first-quarter under
   rule, and this round's first-quarter club-share rule at m >= 1.0 (K 40,
   Pinnacle's ladder at T-10, the best decidable price on the modal number).
2. The first-quarter club-share rule's other reads: the T-60 mark, and K at
   20 and 80, frozen before reading.
3. The 2026-27 home-lean reversal: split it by the relocated clubs (Tel
   Aviv, Hapoel, Dubai play away from home this season) before reading any
   home rule forward.
4. New inputs, not new fits: domestic-league schedules (rest and travel),
   venue coordinates, and box-score fouls and free throws for the referee
   mechanism. Nothing on the stored inputs moved the full-game price.
5. The opening total: the margin sits on DraftKings' first-post under, so a
   rule that picks which first-post overs to bet is the shape that fits; it
   needs a sharp first post beside DraftKings', which round 1 found on only
   45, 52 and 6 games a season.


<!-- r3_report.py output below this line; regenerated on every run -->

## A. The home lean (r3_a_home.py)

### A1. Home moneyline at the full-game close, -200 floor (r3_a_home.py)

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | subset |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | A1 home ML DraftKings close, all bands | 972 | 506 | 466 | 0 | 59.64 | 4.89 | -0.68 | 10.39 | 0.0710 | all bands |
| A | A1 home ML DraftKings close, band -200..-151 | 211 | 127 | 84 | 0 | -20.63 | -5.55 | -14.06 | 2.81 | 0.8520 | band -200..-151 |
| A | A1 home ML DraftKings close, band -150..-121 | 195 | 115 | 80 | 0 | 6.90 | 2.60 | -7.29 | 11.37 | 0.3254 | band -150..-121 |
| A | A1 home ML DraftKings close, band -120..-101 | 137 | 83 | 54 | 0 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 | band -120..-101 |
| A | A1 home ML DraftKings close, band +100..+150 | 207 | 90 | 117 | 0 | -7.25 | -3.50 | -17.34 | 9.17 | 0.6682 | band +100..+150 |
| A | A1 home ML DraftKings close, band +151..+250 | 172 | 75 | 97 | 0 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 | band +151..+250 |
| A | A1 home ML DraftKings close, band +251 or longer | 50 | 16 | 34 | 0 | 13.70 | 27.40 | -17.14 | 71.90 | 0.1565 | band +251 or longer |
| A | A1 home ML best decidable close, all bands | 984 | 513 | 471 | 0 | 64.80 | 5.24 | -0.27 | 11.08 | 0.0643 | all bands |
| A | A1 home ML best decidable close, band -200..-151 | 211 | 131 | 80 | 0 | -11.51 | -3.08 | -12.76 | 5.81 | 0.7101 | band -200..-151 |
| A | A1 home ML best decidable close, band -150..-121 | 199 | 115 | 84 | 0 | 0.63 | 0.23 | -9.39 | 9.58 | 0.4840 | band -150..-121 |
| A | A1 home ML best decidable close, band -120..-101 | 132 | 75 | 57 | 0 | 11.17 | 7.58 | -4.05 | 21.66 | 0.1661 | band -120..-101 |
| A | A1 home ML best decidable close, band +100..+150 | 214 | 97 | 117 | 0 | -0.88 | -0.41 | -13.63 | 11.89 | 0.5211 | band +100..+150 |
| A | A1 home ML best decidable close, band +151..+250 | 176 | 78 | 98 | 0 | 49.09 | 27.89 | 10.73 | 44.32 | 0.0042 | band +151..+250 |
| A | A1 home ML best decidable close, band +251 or longer | 52 | 17 | 35 | 0 | 16.30 | 31.35 | -8.12 | 76.99 | 0.1160 | band +251 or longer |

By season (DraftKings close, all bands, and each band):

| season | band | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|---|
| 2022 | all | 165 | 90 | 75 | 0 | 37.02 | 18.28 | 2.56 | 33.59 | 0.0260 |
| 2023 | all | 172 | 92 | 80 | 0 | 9.05 | 4.11 | -8.21 | 16.66 | 0.2944 |
| 2024 | all | 176 | 90 | 86 | 0 | 1.66 | 0.74 | -12.02 | 13.67 | 0.4618 |
| 2025 | all | 178 | 90 | 88 | 0 | 7.36 | 3.36 | -10.95 | 15.66 | 0.3378 |
| 2026 | all | 220 | 120 | 100 | 0 | 18.55 | 6.72 | -2.93 | 15.88 | 0.1293 |
| 2027 | all | 61 | 24 | 37 | 0 | -14.00 | -18.50 | -43.81 | 7.03 | 0.8777 |
| 2022 | -200..-151 | 31 | 19 | 12 | 0 | -2.15 | -3.87 | -26.80 | 17.62 | 0.6134 |
| 2023 | -200..-151 | 43 | 25 | 18 | 0 | -6.50 | -8.74 | -30.96 | 12.41 | 0.7478 |
| 2024 | -200..-151 | 44 | 30 | 14 | 0 | 5.40 | 6.95 | -11.38 | 23.63 | 0.2573 |
| 2025 | -200..-151 | 30 | 19 | 11 | 0 | -1.04 | -1.95 | -26.17 | 22.40 | 0.5536 |
| 2026 | -200..-151 | 50 | 27 | 23 | 0 | -12.80 | -14.61 | -30.40 | 0.95 | 0.9356 |
| 2027 | -200..-151 | 13 | 7 | 6 | 0 | -3.54 | -15.42 | -42.56 | 11.42 | 0.8266 |
| 2022 | -150..-121 | 28 | 15 | 13 | 0 | -2.58 | -6.73 | -34.12 | 19.96 | 0.6591 |
| 2023 | -150..-121 | 37 | 27 | 10 | 0 | 13.45 | 26.40 | 8.32 | 43.79 | 0.0087 |
| 2024 | -150..-121 | 34 | 23 | 11 | 0 | 7.51 | 15.86 | -6.95 | 39.14 | 0.1238 |
| 2025 | -150..-121 | 42 | 23 | 19 | 0 | -2.68 | -4.71 | -26.83 | 16.18 | 0.6402 |
| 2026 | -150..-121 | 43 | 23 | 20 | 0 | -3.53 | -6.14 | -26.39 | 14.37 | 0.6916 |
| 2027 | -150..-121 | 11 | 4 | 7 | 0 | -5.27 | -35.42 | -82.54 | 8.53 | 0.8993 |
| 2022 | -120..-101 | 22 | 15 | 7 | 0 | 7.15 | 29.07 | -4.94 | 57.21 | 0.0592 |
| 2023 | -120..-101 | 21 | 13 | 8 | 0 | 3.95 | 16.60 | -15.65 | 50.66 | 0.2113 |
| 2024 | -120..-101 | 26 | 15 | 11 | 0 | 3.04 | 10.68 | -18.36 | 39.85 | 0.2755 |
| 2025 | -120..-101 | 29 | 12 | 17 | 0 | -6.73 | -21.08 | -44.58 | 5.86 | 0.9132 |
| 2026 | -120..-101 | 31 | 24 | 7 | 0 | 15.99 | 45.99 | 23.21 | 69.25 | 0.0005 |
| 2027 | -120..-101 | 8 | 4 | 4 | 0 | -0.68 | -7.68 | -40.41 | 19.25 | 0.6566 |
| 2022 | +100..+150 | 31 | 11 | 20 | 0 | -6.60 | -21.29 | -52.19 | 14.48 | 0.8580 |
| 2023 | +100..+150 | 32 | 16 | 16 | 0 | 3.25 | 10.16 | -21.94 | 39.88 | 0.2926 |
| 2024 | +100..+150 | 36 | 11 | 25 | 0 | -11.07 | -30.75 | -58.61 | -2.33 | 0.9613 |
| 2025 | +100..+150 | 38 | 21 | 17 | 0 | 8.41 | 22.13 | -9.50 | 52.74 | 0.1238 |
| 2026 | +100..+150 | 51 | 27 | 24 | 0 | 8.96 | 17.57 | -7.21 | 42.02 | 0.1185 |
| 2027 | +100..+150 | 19 | 4 | 15 | 0 | -10.20 | -53.68 | -88.89 | -11.26 | 0.9871 |
| 2022 | +151..+250 | 38 | 23 | 15 | 0 | 27.70 | 72.89 | 35.76 | 112.27 | 0.0007 |
| 2023 | +151..+250 | 32 | 8 | 24 | 0 | -9.10 | -28.44 | -65.76 | 12.06 | 0.8821 |
| 2024 | +151..+250 | 31 | 10 | 21 | 0 | -2.72 | -8.77 | -47.92 | 33.42 | 0.6392 |
| 2025 | +151..+250 | 26 | 12 | 14 | 0 | 10.50 | 40.38 | -7.99 | 88.75 | 0.0883 |
| 2026 | +151..+250 | 38 | 18 | 20 | 0 | 13.33 | 35.08 | -1.27 | 70.65 | 0.0547 |
| 2027 | +151..+250 | 7 | 4 | 3 | 0 | 4.49 | 64.14 | -20.14 | 149.14 | 0.1148 |
| 2022 | +251 or longer | 15 | 7 | 8 | 0 | 13.50 | 90.00 | -9.29 | 181.12 | 0.0558 |
| 2023 | +251 or longer | 7 | 3 | 4 | 0 | 4.00 | 57.14 | -44.29 | 158.57 | 0.1653 |
| 2024 | +251 or longer | 5 | 1 | 4 | 0 | -0.50 | -10.00 | -100.00 | 170.00 | 0.5497 |
| 2025 | +251 or longer | 13 | 3 | 10 | 0 | -1.10 | -8.46 | -72.31 | 83.08 | 0.5712 |
| 2026 | +251 or longer | 7 | 1 | 6 | 0 | -3.40 | -48.57 | -100.00 | 54.29 | 0.8517 |
| 2027 | +251 or longer | 3 | 1 | 2 | 0 | 1.20 | 40.00 | -100.00 | 180.00 | 0.3595 |

By season, best decidable close (all bands):

| season | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| 2022 | 165 | 90 | 75 | 0 | 37.02 | 18.28 | 2.56 | 33.59 | 0.0260 |
| 2023 | 172 | 92 | 80 | 0 | 9.05 | 4.11 | -8.21 | 16.66 | 0.2944 |
| 2024 | 176 | 90 | 86 | 0 | 1.66 | 0.74 | -12.02 | 13.67 | 0.4618 |
| 2025 | 178 | 90 | 88 | 0 | 7.36 | 3.36 | -10.95 | 15.66 | 0.3378 |
| 2026 | 230 | 125 | 105 | 0 | 19.68 | 6.79 | -2.92 | 15.83 | 0.1257 |
| 2027 | 63 | 26 | 37 | 0 | -9.97 | -12.70 | -38.85 | 13.89 | 0.7802 |

Walk-forward band rule (DraftKings close; in season s, the bands positive over every earlier season):

Bands chosen: 2023: -120..-101, +151..+250, +251 or longer; 2024: -150..-121, -120..-101, +151..+250, +251 or longer; 2025: -150..-121, -120..-101, +151..+250, +251 or longer; 2026: -150..-121, -120..-101, +151..+250, +251 or longer; 2027: -150..-121, -120..-101, +100..+150, +151..+250, +251 or longer

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | subset |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | A1 walk-forward band rule, DraftKings close | 433 | 206 | 227 | 0 | 18.10 | 3.68 | -5.73 | 12.66 | 0.2583 | 2022-23 on |
|  |  | 60 | 24 | 36 | 0 | -1.15 | -1.83 | -28.88 | 27.29 | 0.5426 | season 2023 |
|  |  | 96 | 49 | 47 | 0 | 7.33 | 6.56 | -11.37 | 25.16 | 0.2786 | season 2024 |
|  |  | 110 | 50 | 60 | 0 | -0.01 | -0.01 | -16.83 | 17.17 | 0.5003 | season 2025 |
|  |  | 119 | 66 | 53 | 0 | 22.39 | 16.31 | 1.99 | 31.36 | 0.0318 | season 2026 |
|  |  | 48 | 17 | 31 | 0 | -10.46 | -19.84 | -53.55 | 15.51 | 0.8247 | season 2027 |

Descriptive: home win rate against Pinnacle's power-de-vigged close, every price (neutral out):

| season | games | home won % | Pinnacle no-vig home % | gap (pts of %) |
|---|---|---|---|---|
| 2022 | 238 | 64.71 | 58.99 | 5.71 |
| 2023 | 268 | 62.69 | 60.80 | 1.89 |
| 2024 | 289 | 65.40 | 60.97 | 4.43 |
| 2025 | 326 | 61.96 | 60.15 | 1.82 |
| 2026 | 399 | 63.66 | 60.26 | 3.39 |
| 2027 | 107 | 54.21 | 59.64 | -5.43 |
| 2022-2026 pooled | 1,520 | 63.62 | 60.27 | 3.35 |
| all | 1,627 | 63.00 | 60.23 | 2.77 |

Kill rows, DraftKings close, all bands: price range median -110, shortest -200, longest +550, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 1218.8 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 DK close home ML, -200 floor | all | 972 | 506 | 466 | 0 | 59.64 | 4.89 | -0.68 | 10.39 | 0.0710 |  |
| A1 DK close home ML, -200 floor | season 2022 | 165 | 90 | 75 | 0 | 37.02 | 18.28 | 2.56 | 33.59 | 0.0260 |  |
| A1 DK close home ML, -200 floor | season 2023 | 172 | 92 | 80 | 0 | 9.05 | 4.11 | -8.21 | 16.66 | 0.2944 |  |
| A1 DK close home ML, -200 floor | season 2024 | 176 | 90 | 86 | 0 | 1.66 | 0.74 | -12.02 | 13.67 | 0.4618 |  |
| A1 DK close home ML, -200 floor | season 2025 | 178 | 90 | 88 | 0 | 7.36 | 3.36 | -10.95 | 15.66 | 0.3378 |  |
| A1 DK close home ML, -200 floor | season 2026 | 220 | 120 | 100 | 0 | 18.55 | 6.72 | -2.93 | 15.88 | 0.1293 |  |
| A1 DK close home ML, -200 floor | season 2027 | 61 | 24 | 37 | 0 | -14.00 | -18.50 | -43.81 | 7.03 | 0.8777 |  |
| A1 DK close home ML, -200 floor | early half of each season | 475 | 247 | 228 | 0 | 27.38 | 4.56 | -3.62 | 12.53 | 0.1778 |  |
| A1 DK close home ML, -200 floor | late half of each season | 497 | 259 | 238 | 0 | 32.26 | 5.22 | -3.08 | 12.63 | 0.1344 |  |
| A1 DK close home ML, -200 floor | without its 10 best dates | 929 | 468 | 461 | 0 | 3.41 | 0.29 | -4.95 | 5.78 | 0.4646 |  |
| A1 DK close home ML, -200 floor | side = home | 972 | 506 | 466 | 0 | 59.64 | 4.89 | -0.68 | 10.39 | 0.0710 | 100.00 |
| A1 DK close home ML, -200 floor | underdog | 429 | 181 | 248 | 0 | 50.65 | 11.81 | 0.15 | 24.03 | 0.0515 | 44.10 |
| A1 DK close home ML, -200 floor | favourite | 543 | 325 | 218 | 0 | 8.99 | 1.14 | -4.51 | 6.49 | 0.3667 | 55.90 |
| A1 DK close home ML, -200 floor | price band +100..+150 | 207 | 90 | 117 | 0 | -7.25 | -3.50 | -17.34 | 9.17 | 0.6682 | 21.30 |
| A1 DK close home ML, -200 floor | price band -150..-100 | 332 | 198 | 134 | 0 | 29.62 | 7.08 | -1.09 | 14.91 | 0.0718 | 34.20 |
| A1 DK close home ML, -200 floor | price band -300..-151 | 211 | 127 | 84 | 0 | -20.63 | -5.55 | -14.06 | 2.81 | 0.8520 | 21.70 |
| A1 DK close home ML, -200 floor | price band > +150 | 222 | 91 | 131 | 0 | 57.90 | 26.08 | 10.47 | 43.09 | 0.0048 | 22.80 |

Kill rows, A1 DK close home ML, band +151..+250 (a band read off the table): price range median +190, shortest +154, longest +250, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 172.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 DK close home ML, band +151..+250 (a band read off the table) | all | 172 | 75 | 97 | 0 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2022 | 38 | 23 | 15 | 0 | 27.70 | 72.89 | 35.76 | 112.27 | 0.0007 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2023 | 32 | 8 | 24 | 0 | -9.10 | -28.44 | -65.76 | 12.06 | 0.8821 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2024 | 31 | 10 | 21 | 0 | -2.72 | -8.77 | -47.92 | 33.42 | 0.6392 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2025 | 26 | 12 | 14 | 0 | 10.50 | 40.38 | -7.99 | 88.75 | 0.0883 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2026 | 38 | 18 | 20 | 0 | 13.33 | 35.08 | -1.27 | 70.65 | 0.0547 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | season 2027 | 7 | 4 | 3 | 0 | 4.49 | 64.14 | -20.14 | 149.14 | 0.1148 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | early half of each season | 84 | 38 | 46 | 0 | 23.57 | 28.06 | 0.34 | 54.98 | 0.0460 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | late half of each season | 88 | 37 | 51 | 0 | 20.63 | 23.44 | -0.35 | 49.54 | 0.0662 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | without its 10 best dates | 156 | 59 | 97 | 0 | 12.15 | 7.79 | -9.52 | 24.34 | 0.2283 |  |
| A1 DK close home ML, band +151..+250 (a band read off the table) | side = home | 172 | 75 | 97 | 0 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 | 100.00 |
| A1 DK close home ML, band +151..+250 (a band read off the table) | price band > +150 | 172 | 75 | 97 | 0 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 | 100.00 |

Kill rows, A1 DK close home ML, band -120..-101 (a band read off the table): price range median -110, shortest -120, longest -102, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 152.4 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 DK close home ML, band -120..-101 (a band read off the table) | all | 137 | 83 | 54 | 0 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2022 | 22 | 15 | 7 | 0 | 7.15 | 29.07 | -4.94 | 57.21 | 0.0592 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2023 | 21 | 13 | 8 | 0 | 3.95 | 16.60 | -15.65 | 50.66 | 0.2113 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2024 | 26 | 15 | 11 | 0 | 3.04 | 10.68 | -18.36 | 39.85 | 0.2755 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2025 | 29 | 12 | 17 | 0 | -6.73 | -21.08 | -44.58 | 5.86 | 0.9132 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2026 | 31 | 24 | 7 | 0 | 15.99 | 45.99 | 23.21 | 69.25 | 0.0005 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | season 2027 | 8 | 4 | 4 | 0 | -0.68 | -7.68 | -40.41 | 19.25 | 0.6566 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | early half of each season | 65 | 37 | 28 | 0 | 5.78 | 8.00 | -9.58 | 27.67 | 0.2311 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | late half of each season | 72 | 46 | 26 | 0 | 16.94 | 21.13 | 4.50 | 38.81 | 0.0208 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | without its 10 best dates | 124 | 70 | 54 | 0 | 9.72 | 7.03 | -5.45 | 20.14 | 0.1898 |  |
| A1 DK close home ML, band -120..-101 (a band read off the table) | side = home | 137 | 83 | 54 | 0 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 | 100.00 |
| A1 DK close home ML, band -120..-101 (a band read off the table) | price band -150..-100 | 137 | 83 | 54 | 0 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 | 100.00 |

Kill rows, A1 DK close home ML, home underdog +100 or longer (post hoc): price range median +154, shortest +100, longest +550, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 429.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A1 DK close home ML, home underdog +100 or longer (post hoc) | all | 429 | 181 | 248 | 0 | 50.65 | 11.81 | 0.15 | 24.03 | 0.0515 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2022 | 84 | 41 | 43 | 0 | 34.60 | 41.19 | 12.39 | 72.19 | 0.0113 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2023 | 71 | 27 | 44 | 0 | -1.85 | -2.61 | -29.50 | 22.44 | 0.5653 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2024 | 72 | 22 | 50 | 0 | -14.29 | -19.85 | -42.01 | 2.79 | 0.9258 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2025 | 77 | 36 | 41 | 0 | 17.81 | 23.13 | -3.23 | 50.13 | 0.0840 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2026 | 96 | 46 | 50 | 0 | 18.89 | 19.68 | -0.81 | 40.14 | 0.0573 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | season 2027 | 29 | 9 | 20 | 0 | -4.51 | -15.55 | -66.84 | 37.41 | 0.6875 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | early half of each season | 208 | 92 | 116 | 0 | 37.59 | 18.07 | 1.25 | 34.31 | 0.0432 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | late half of each season | 221 | 89 | 132 | 0 | 13.06 | 5.91 | -8.41 | 20.06 | 0.2514 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | without its 10 best dates | 405 | 159 | 246 | 0 | 3.58 | 0.88 | -9.83 | 11.92 | 0.4483 |  |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | side = home | 429 | 181 | 248 | 0 | 50.65 | 11.81 | 0.15 | 24.03 | 0.0515 | 100.00 |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | price band +100..+150 | 207 | 90 | 117 | 0 | -7.25 | -3.50 | -17.34 | 9.17 | 0.6682 | 48.30 |
| A1 DK close home ML, home underdog +100 or longer (post hoc) | price band > +150 | 222 | 91 | 131 | 0 | 57.90 | 26.08 | 10.47 | 43.09 | 0.0048 | 51.70 |

Side control and placebo (not counted): the away side under the same floor, and the nominal home side at neutral-site games (no home crowd), DraftKings close:

| control | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| away ML, -200 floor, every non-neutral game | 1,572 | 539 | 1,033 | 0 | -237.38 | -13.84 | -18.41 | -9.12 | 1.0000 |
| away ML underdog +100 or longer | 1,202 | 353 | 849 | 0 | -174.91 | -14.55 | -20.41 | -8.32 | 1.0000 |
| nominal home ML at neutral-site games, -200 floor | 14 | 7 | 7 | 0 | -1.99 | -10.44 | -43.51 | 23.81 | 0.6935 |

### A2. First-half home bets at T-10, 2025-26 and 2026-27 (r3_a_home.py)

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | subset |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A | A2 home spreads_h1 fanduel | 417 | 210 | 207 | 0 | -24.90 | -5.26 | -13.21 | 2.35 | 0.8695 | 2025-26 + 2026-27 |
| A | A2 home spreads_h1 fanduel | 310 | 151 | 159 | 0 | -29.70 | -8.44 | -17.03 | 1.06 | 0.9372 | season 2026 |
| A | A2 home spreads_h1 fanduel | 107 | 59 | 48 | 0 | 4.80 | 3.97 | -9.24 | 15.53 | 0.2956 | season 2027 |
| A | A2 home spreads_h1 betrivers | 106 | 59 | 47 | 0 | 3.23 | 2.55 | -10.54 | 14.06 | 0.3655 | 2025-26 + 2026-27 |
| A | A2 home spreads_h1 betrivers | 106 | 59 | 47 | 0 | 3.23 | 2.55 | -10.54 | 14.06 | 0.3655 | season 2027 |
| A | A2 home spreads_h1 best of fanduel/betrivers | 417 | 210 | 207 | 0 | -24.30 | -5.15 | -13.13 | 2.47 | 0.8638 | 2025-26 + 2026-27 |
| A | A2 home spreads_h1 best of fanduel/betrivers | 310 | 151 | 159 | 0 | -29.70 | -8.44 | -17.03 | 1.06 | 0.9372 | season 2026 |
| A | A2 home spreads_h1 best of fanduel/betrivers | 107 | 59 | 48 | 0 | 5.40 | 4.53 | -8.85 | 16.11 | 0.2715 | season 2027 |
| A | A2 home spreads_h1 best of fanduel/betrivers, home underdog | 118 | 65 | 53 | 0 | 5.09 | 3.82 | -10.78 | 17.96 | 0.3289 | home underdog |
| A | A2 home spreads_h1 best of fanduel/betrivers, home underdog | 86 | 47 | 39 | 0 | 2.44 | 2.50 | -14.62 | 18.92 | 0.4059 | season 2026 |
| A | A2 home spreads_h1 best of fanduel/betrivers, home underdog | 32 | 18 | 14 | 0 | 2.65 | 7.46 | -20.72 | 30.68 | 0.3164 | season 2027 |
| A | A2 home spreads_h1 best of fanduel/betrivers, home favourite | 299 | 145 | 154 | 0 | -29.39 | -8.69 | -17.42 | -0.06 | 0.9510 | home favourite |
| A | A2 home spreads_h1 best of fanduel/betrivers, home favourite | 224 | 104 | 120 | 0 | -32.14 | -12.64 | -23.46 | -1.55 | 0.9733 | season 2026 |
| A | A2 home spreads_h1 best of fanduel/betrivers, home favourite | 75 | 41 | 34 | 0 | 2.75 | 3.28 | -10.88 | 16.63 | 0.3507 | season 2027 |
| A | A2 home h2h_h1 fanduel | 254 | 128 | 117 | 9 | -6.99 | -2.18 | -12.50 | 7.52 | 0.6425 | 2025-26 + 2026-27 |
| A | A2 home h2h_h1 fanduel | 182 | 87 | 88 | 7 | -14.98 | -6.55 | -17.66 | 4.02 | 0.8404 | season 2026 |
| A | A2 home h2h_h1 fanduel | 72 | 41 | 29 | 2 | 7.99 | 8.68 | -9.99 | 26.15 | 0.2202 | season 2027 |
| A | A2 home h2h_h1 betrivers | 265 | 134 | 121 | 10 | -3.49 | -1.04 | -10.85 | 8.35 | 0.5715 | 2025-26 + 2026-27 |
| A | A2 home h2h_h1 betrivers | 190 | 93 | 90 | 7 | -6.47 | -2.70 | -14.01 | 7.68 | 0.6598 | season 2026 |
| A | A2 home h2h_h1 betrivers | 75 | 41 | 31 | 3 | 2.98 | 3.06 | -15.88 | 19.21 | 0.3906 | season 2027 |
| A | A2 home h2h_h1 best of fanduel/betrivers | 275 | 138 | 127 | 10 | -6.66 | -1.91 | -11.31 | 6.65 | 0.6365 | 2025-26 + 2026-27 |
| A | A2 home h2h_h1 best of fanduel/betrivers | 199 | 96 | 96 | 7 | -12.11 | -4.82 | -14.80 | 5.24 | 0.7762 | season 2026 |
| A | A2 home h2h_h1 best of fanduel/betrivers | 76 | 42 | 31 | 3 | 5.45 | 5.63 | -13.62 | 22.16 | 0.3066 | season 2027 |
| A | A2 home h2h_h1 best of fanduel/betrivers, home underdog | 99 | 44 | 50 | 5 | 11.81 | 12.56 | -7.39 | 34.02 | 0.1614 | home underdog |
| A | A2 home h2h_h1 best of fanduel/betrivers, home underdog | 74 | 34 | 36 | 4 | 12.91 | 18.44 | -7.92 | 44.02 | 0.1140 | season 2026 |
| A | A2 home h2h_h1 best of fanduel/betrivers, home underdog | 25 | 10 | 14 | 1 | -1.10 | -4.58 | -32.00 | 23.48 | 0.6049 | season 2027 |
| A | A2 home h2h_h1 best of fanduel/betrivers, home favourite | 176 | 94 | 77 | 5 | -18.47 | -7.26 | -17.57 | 3.12 | 0.8757 | home favourite |
| A | A2 home h2h_h1 best of fanduel/betrivers, home favourite | 125 | 62 | 60 | 3 | -25.02 | -13.79 | -25.56 | -2.62 | 0.9741 | season 2026 |
| A | A2 home h2h_h1 best of fanduel/betrivers, home favourite | 51 | 32 | 17 | 2 | 6.55 | 8.99 | -13.51 | 26.67 | 0.2306 | season 2027 |

Kill rows, A2 first-half moneyline, home underdog, best of FanDuel/BetRivers: price range median +128, shortest +100, longest +250, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 94.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | all | 99 | 44 | 50 | 5 | 11.81 | 12.56 | -7.39 | 34.02 | 0.1614 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | season 2026 | 74 | 34 | 36 | 4 | 12.91 | 18.44 | -7.92 | 44.02 | 0.1140 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | season 2027 | 25 | 10 | 14 | 1 | -1.10 | -4.58 | -32.00 | 23.48 | 0.6049 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | early half of each season | 49 | 24 | 21 | 4 | 13.00 | 28.89 | 2.63 | 61.63 | 0.0555 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | late half of each season | 50 | 20 | 29 | 1 | -1.19 | -2.43 | -31.70 | 27.11 | 0.5543 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | without its 10 best dates | 82 | 29 | 49 | 4 | -12.45 | -15.96 | -34.68 | 2.94 | 0.9200 |  |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | side = home | 99 | 44 | 50 | 5 | 11.81 | 12.56 | -7.39 | 34.02 | 0.1614 | 100.00 |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | price band +100..+150 | 71 | 31 | 35 | 5 | 2.45 | 3.71 | -16.32 | 25.52 | 0.3872 | 71.70 |
| A2 first-half moneyline, home underdog, best of FanDuel/BetRivers | price band > +150 | 28 | 13 | 15 | 0 | 9.36 | 33.43 | -13.04 | 79.64 | 0.1201 | 28.30 |

Kill rows, A2 first-half spread, home underdog, best of FanDuel/BetRivers: price range median -113, shortest -125, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 133.2 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | all | 118 | 65 | 53 | 0 | 5.09 | 3.82 | -10.78 | 17.96 | 0.3289 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | season 2026 | 86 | 47 | 39 | 0 | 2.44 | 2.50 | -14.62 | 18.92 | 0.4059 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | season 2027 | 32 | 18 | 14 | 0 | 2.65 | 7.46 | -20.72 | 30.68 | 0.3164 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | early half of each season | 59 | 37 | 22 | 0 | 12.17 | 18.22 | -3.85 | 38.18 | 0.0734 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | late half of each season | 59 | 28 | 31 | 0 | -7.08 | -10.65 | -29.73 | 8.51 | 0.8190 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | without its 10 best dates | 92 | 41 | 51 | 0 | -16.67 | -16.01 | -32.09 | -1.48 | 0.9618 |  |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | side = home | 118 | 65 | 53 | 0 | 5.09 | 3.82 | -10.78 | 17.96 | 0.3289 | 100.00 |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | price band +100..+150 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 0.80 |
| A2 first-half spread, home underdog, best of FanDuel/BetRivers | price band -150..-100 | 117 | 64 | 53 | 0 | 4.09 | 3.09 | -11.38 | 17.55 | 0.3618 | 99.20 |

### A3. Round 1's frozen home-underdog spread rule, read unchanged (r3_a_home.py)

Rule: home against the spread at the DraftKings close when the home line is above 0, own-country games only. Round 1 (all seasons): 454 bets, +48.34 units, +9.72%; its 2026-27 row: 30 bets, -8.10 units, -24.06%.

| subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | experiment | cell |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all seasons (reproduction check) | 454 | 259 | 191 | 4 | 48.34 | 9.72 | 2.44 | 16.89 | 0.0126 |  |  |
| 2026-27 (no new games since round 1) | 30 | 12 | 18 | 0 | -8.10 | -24.06 | -49.70 | 1.39 | 0.9467 | A | A3 frozen home underdog ATS, 2026-27 read |
| 2021-22 to 2025-26 | 424 | 247 | 173 | 4 | 56.44 | 12.18 | 5.19 | 20.17 | 0.0047 |  |  |

Last played 2026-27 game in the cache: 2026-11-12; 2026-27 bets read: 30. These are the games round 1 already read, so this is a reproduction, not a hold-out.

## B. Market-anchored models (r3_b_anchored.py)

Input coverage (neutral out, 2021-22 on): attendance missing 0.9%, venue differs from the club-season's usual 7.1%, on the relocated lists 5.0%, home short rest 25.8%, away short rest 25.1%, double-round week 53.3%, first game of a season 3.1%. Travel: not derivable (no coordinates stored).


### B1. Moneyline: market-anchored logit, walk-forward (r3_b_anchored.py)

Games (neutral out, 2021-22 on): 1778; with a Pinnacle close moneyline: 1627; dropped: 151. By season with Pinnacle: {2022: 238, 2023: 268, 2024: 289, 2025: 326, 2026: 399, 2027: 107}.

Full-model coefficients by graded season (standardised inputs; the penalty chosen on the training seasons):

| graded season | penalty | coefficients |
|---|---|---|
| 2024 | 1,000.00 | const +0.017, hdog +0.022, log_att -0.001, att_missing -0.004, reloc_season -0.013, reloc_list +0.000, rest_diff -0.003, home_short +0.002, away_short -0.003, first_game +0.002, dbl_week +0.004, dbl2_home -0.000, dbl2_away -0.004 |
| 2025 | 1,000.00 | const +0.027, hdog +0.013, log_att +0.003, att_missing -0.005, reloc_season -0.003, reloc_list +0.017, rest_diff -0.001, home_short +0.001, away_short -0.001, first_game +0.007, dbl_week +0.015, dbl2_home -0.001, dbl2_away -0.002 |
| 2026 | 1,000.00 | const +0.030, hdog +0.022, log_att -0.008, att_missing -0.012, reloc_season -0.010, reloc_list +0.021, rest_diff -0.003, home_short -0.006, away_short -0.007, first_game +0.015, dbl_week +0.013, dbl2_home -0.007, dbl2_away -0.008 |
| 2027 | 300.00 | const +0.080, hdog +0.080, log_att +0.003, att_missing -0.001, reloc_season -0.037, reloc_list +0.023, rest_diff +0.005, home_short +0.001, away_short -0.012, first_game +0.028, dbl_week +0.049, dbl2_home -0.004, dbl2_away -0.016 |

Accuracy on the graded games (log loss / Brier; lower is better):

| variant | games | log loss | brier | log loss vs market |
|---|---|---|---|---|
| market alone (offset only) | 1,121 | 0.6075 | 0.2113 | 0.0000 |
| full model | 1,121 | 0.6075 | 0.2114 | 0.0001 |
| full minus home | 1,121 | 0.6075 | 0.2113 | 0.0000 |
| full minus home underdog | 1,121 | 0.6083 | 0.2117 | 0.0008 |
| full minus attendance | 1,121 | 0.6067 | 0.2110 | -0.0007 |
| full minus venue | 1,121 | 0.6072 | 0.2112 | -0.0003 |
| full minus rest | 1,121 | 0.6075 | 0.2114 | 0.0001 |
| full minus double week | 1,121 | 0.6075 | 0.2114 | 0.0001 |
| home dummy only | 1,121 | 0.6066 | 0.2110 | -0.0009 |

Cut grid, DraftKings close (main price), -200 floor, graded 2023-24 .. 2026-27:

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | cut |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B | B1 ML market alone (offset only), DK close, cut 0.00 | 822 | 323 | 499 | 0 | -95.87 | -10.21 | -16.71 | -4.27 | 0.9956 | 0.000 |
| B | B1 ML market alone (offset only), DK close, cut 0.01 | 147 | 59 | 88 | 0 | -19.06 | -11.27 | -26.10 | 3.05 | 0.8970 | 0.010 |
| B | B1 ML market alone (offset only), DK close, cut 0.02 | 33 | 13 | 20 | 0 | -5.83 | -14.98 | -46.90 | 14.00 | 0.7906 | 0.020 |
| B | B1 ML market alone (offset only), DK close, cut 0.03 | 9 | 5 | 4 | 0 | 1.15 | 9.80 | -49.04 | 71.42 | 0.3960 | 0.030 |
| B | B1 ML market alone (offset only), DK close, cut 0.04 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  | 0.040 |
| B | B1 ML market alone (offset only), DK close, cut 0.05 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  | 0.050 |
| B | B1 ML full model, DK close, cut 0.00 | 800 | 329 | 471 | 0 | -51.17 | -5.68 | -13.73 | 1.62 | 0.8951 | 0.000 |
| B | B1 ML full model, DK close, cut 0.01 | 354 | 151 | 203 | 0 | -16.21 | -4.13 | -14.53 | 6.67 | 0.7412 | 0.010 |
| B | B1 ML full model, DK close, cut 0.02 | 159 | 67 | 92 | 0 | -7.18 | -4.13 | -19.71 | 12.67 | 0.6666 | 0.020 |
| B | B1 ML full model, DK close, cut 0.03 | 80 | 28 | 52 | 0 | -18.86 | -21.81 | -44.45 | 1.46 | 0.9425 | 0.030 |
| B | B1 ML full model, DK close, cut 0.04 | 42 | 16 | 26 | 0 | -4.17 | -9.61 | -42.77 | 28.63 | 0.6674 | 0.040 |
| B | B1 ML full model, DK close, cut 0.05 | 22 | 11 | 11 | 0 | 2.28 | 10.19 | -26.76 | 50.04 | 0.3349 | 0.050 |

Ablation at the headline cut 0.02, DraftKings close:

| variant | cut | bets | W | L | P | units | ret% | lo% | hi% | p_one | experiment | cell |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| market alone (offset only) | 0.020 | 33 | 13 | 20 | 0 | -5.83 | -14.98 | -46.90 | 14.00 | 0.7906 |  |  |
| full model | 0.020 | 159 | 67 | 92 | 0 | -7.18 | -4.13 | -19.71 | 12.67 | 0.6666 |  |  |
| full minus home |  | 125 | 42 | 83 | 0 | -25.52 | -19.05 | -35.59 | -2.07 | 0.9661 | B | B1 ML full minus home, DK close, cut 0.02 |
| full minus home underdog |  | 166 | 78 | 88 | 0 | -3.00 | -1.52 | -15.69 | 12.54 | 0.5703 | B | B1 ML full minus home underdog, DK close, cut 0.02 |
| full minus attendance |  | 209 | 96 | 113 | 0 | 7.86 | 3.42 | -9.62 | 17.31 | 0.3355 | B | B1 ML full minus attendance, DK close, cut 0.02 |
| full minus venue |  | 124 | 55 | 69 | 0 | -0.82 | -0.60 | -18.27 | 16.41 | 0.5232 | B | B1 ML full minus venue, DK close, cut 0.02 |
| full minus rest |  | 145 | 62 | 83 | 0 | -1.03 | -0.66 | -17.83 | 16.12 | 0.5259 | B | B1 ML full minus rest, DK close, cut 0.02 |
| full minus double week |  | 145 | 64 | 81 | 0 | 2.53 | 1.60 | -14.54 | 17.46 | 0.4361 | B | B1 ML full minus double week, DK close, cut 0.02 |
| home dummy only |  | 585 | 302 | 283 | 0 | 17.31 | 2.35 | -4.81 | 9.31 | 0.2974 | B | B1 ML home dummy only, DK close, cut 0.02 |

Second read: the best decidable close (largest edge over the decidable books), full model:

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | cut |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B | B1 ML full model, best decidable close, cut 0.00 | 913 | 349 | 564 | 0 | -76.55 | -7.57 | -13.68 | -0.80 | 0.9725 | 0.000 |
| B | B1 ML full model, best decidable close, cut 0.01 | 561 | 220 | 341 | 0 | -32.81 | -5.31 | -13.32 | 2.81 | 0.8653 | 0.010 |
| B | B1 ML full model, best decidable close, cut 0.02 | 338 | 128 | 210 | 0 | -30.69 | -8.26 | -18.43 | 1.83 | 0.9022 | 0.020 |
| B | B1 ML full model, best decidable close, cut 0.03 | 193 | 70 | 123 | 0 | -28.48 | -13.53 | -28.15 | 2.12 | 0.9256 | 0.030 |
| B | B1 ML full model, best decidable close, cut 0.04 | 94 | 34 | 60 | 0 | -11.08 | -11.11 | -33.52 | 13.18 | 0.7832 | 0.040 |
| B | B1 ML full model, best decidable close, cut 0.05 | 52 | 23 | 29 | 0 | 5.02 | 9.20 | -24.33 | 44.19 | 0.3275 | 0.050 |

The market-alone row at the best decidable close (not counted; the second read's control):

| cut | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| 0.000 | 945 | 359 | 586 | 0 | -97.41 | -9.12 | -15.78 | -3.07 | 0.9905 |
| 0.010 | 442 | 175 | 267 | 0 | -25.64 | -5.13 | -15.12 | 5.53 | 0.7994 |
| 0.020 | 255 | 97 | 158 | 0 | -13.95 | -4.90 | -17.13 | 5.74 | 0.7673 |
| 0.030 | 110 | 32 | 78 | 0 | -21.69 | -18.47 | -39.53 | 1.89 | 0.9272 |
| 0.040 | 32 | 11 | 21 | 0 | 3.23 | 9.71 | -36.51 | 56.87 | 0.3671 |
| 0.050 | 9 | 4 | 5 | 0 | 5.16 | 54.03 | -48.69 | 160.96 | 0.2006 |

### B2. Spread: market-anchored residual model, walk-forward (r3_b_anchored.py)

Games with a Pinnacle closing spread (pushes on Pinnacle's number out of the fit): 1601; by season {2022: 234, 2023: 268, 2024: 287, 2025: 317, 2026: 390, 2027: 105}.

Full-model coefficients by graded season (points per standard deviation):

| graded season | penalty | sigma | coefficients |
|---|---|---|---|
| 2024 | 1,000.00 | 11.52 | const +0.274, hdog +0.565, log_att +0.058, att_missing +0.044, reloc_season -0.076, reloc_list +0.000, rest_diff +0.143, home_short +0.020, away_short -0.011, first_game -0.004, dbl_week +0.042, dbl2_home -0.005, dbl2_away -0.022 |
| 2025 | 1,000.00 | 11.50 | const +0.350, hdog +0.492, log_att +0.130, att_missing +0.031, reloc_season +0.001, reloc_list +0.272, rest_diff +0.124, home_short +0.003, away_short -0.019, first_game +0.134, dbl_week +0.084, dbl2_home -0.023, dbl2_away -0.031 |
| 2026 | 1,000.00 | 11.64 | const +0.334, hdog +0.648, log_att +0.093, att_missing -0.013, reloc_season -0.094, reloc_list +0.214, rest_diff +0.106, home_short -0.026, away_short -0.080, first_game +0.205, dbl_week +0.048, dbl2_home -0.050, dbl2_away -0.091 |
| 2027 | 300.00 | 11.63 | const +0.451, hdog +1.160, log_att +0.321, att_missing +0.161, reloc_season -0.524, reloc_list +0.180, rest_diff +0.431, home_short +0.297, away_short -0.204, first_game +0.327, dbl_week +0.166, dbl2_home +0.230, dbl2_away -0.233 |

Accuracy on the graded games (mean squared error of the residual; market alone predicts 0):

| variant | games | mse | mse vs market |
|---|---|---|---|
| market alone (offset only) | 1,099 | 135.41 | 0.00 |
| full model | 1,099 | 134.72 | -0.69 |
| full minus home | 1,099 | 134.65 | -0.76 |
| full minus home underdog | 1,099 | 135.44 | 0.04 |
| full minus attendance | 1,099 | 134.86 | -0.54 |
| full minus venue | 1,099 | 134.55 | -0.86 |
| full minus rest | 1,099 | 134.68 | -0.72 |
| full minus double week | 1,099 | 134.55 | -0.86 |
| home dummy only | 1,099 | 135.35 | -0.05 |

Cut grid, DraftKings close spread:

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | cut |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B | B2 spread market alone (offset only), DK close, cut 0.00 | 963 | 482 | 476 | 5 | -38.04 | -3.63 | -8.96 | 1.76 | 0.8695 | 0.000 |
| B | B2 spread market alone (offset only), DK close, cut 0.01 | 453 | 220 | 232 | 1 | -32.95 | -6.67 | -13.43 | 1.10 | 0.9260 | 0.010 |
| B | B2 spread market alone (offset only), DK close, cut 0.02 | 74 | 38 | 36 | 0 | -1.90 | -2.32 | -21.54 | 15.58 | 0.5818 | 0.020 |
| B | B2 spread market alone (offset only), DK close, cut 0.03 | 24 | 13 | 11 | 0 | 0.51 | 1.87 | -29.47 | 32.71 | 0.4606 | 0.030 |
| B | B2 spread market alone (offset only), DK close, cut 0.04 | 16 | 7 | 9 | 0 | -3.27 | -17.84 | -53.35 | 17.89 | 0.7715 | 0.040 |
| B | B2 spread market alone (offset only), DK close, cut 0.05 | 11 | 5 | 6 | 0 | -1.88 | -14.80 | -65.46 | 19.75 | 0.7074 | 0.050 |
| B | B2 spread full model, DK close, cut 0.00 | 1,099 | 574 | 520 | 5 | 2.17 | 0.18 | -4.70 | 5.03 | 0.4757 | 0.000 |
| B | B2 spread full model, DK close, cut 0.01 | 664 | 347 | 313 | 4 | 2.20 | 0.30 | -6.17 | 7.15 | 0.4695 | 0.010 |
| B | B2 spread full model, DK close, cut 0.02 | 428 | 225 | 200 | 3 | 4.44 | 0.95 | -7.07 | 8.60 | 0.4202 | 0.020 |
| B | B2 spread full model, DK close, cut 0.03 | 321 | 173 | 145 | 3 | 13.16 | 3.75 | -4.82 | 12.66 | 0.2398 | 0.030 |
| B | B2 spread full model, DK close, cut 0.04 | 230 | 124 | 104 | 2 | 9.18 | 3.65 | -7.99 | 14.21 | 0.2917 | 0.040 |
| B | B2 spread full model, DK close, cut 0.05 | 153 | 84 | 67 | 2 | 9.64 | 5.76 | -7.81 | 18.44 | 0.2323 | 0.050 |

Ablation at the headline cut 0.02:

| variant | bets | W | L | P | units | ret% | lo% | hi% | p_one | experiment | cell |
|---|---|---|---|---|---|---|---|---|---|---|---|
| market alone (offset only) | 74 | 38 | 36 | 0 | -1.90 | -2.32 | -21.54 | 15.58 | 0.5818 |  |  |
| full model | 428 | 225 | 200 | 3 | 4.44 | 0.95 | -7.07 | 8.60 | 0.4202 |  |  |
| full minus home | 518 | 267 | 248 | 3 | -6.69 | -1.17 | -8.13 | 5.57 | 0.6098 | B | B2 spread full minus home, DK close, cut 0.02 |
| full minus home underdog | 307 | 165 | 140 | 2 | 11.34 | 3.38 | -6.21 | 13.26 | 0.2843 | B | B2 spread full minus home underdog, DK close, cut 0.02 |
| full minus attendance | 427 | 221 | 203 | 3 | -2.91 | -0.62 | -7.86 | 7.16 | 0.5540 | B | B2 spread full minus attendance, DK close, cut 0.02 |
| full minus venue | 415 | 223 | 189 | 3 | 14.38 | 3.16 | -4.99 | 11.32 | 0.2558 | B | B2 spread full minus venue, DK close, cut 0.02 |
| full minus rest | 395 | 209 | 183 | 3 | 7.06 | 1.63 | -6.74 | 9.72 | 0.3733 | B | B2 spread full minus rest, DK close, cut 0.02 |
| full minus double week | 410 | 220 | 187 | 3 | 13.76 | 3.06 | -4.90 | 10.62 | 0.2566 | B | B2 spread full minus double week, DK close, cut 0.02 |
| home dummy only | 678 | 351 | 322 | 5 | -2.00 | -0.27 | -6.80 | 5.55 | 0.5294 | B | B2 spread home dummy only, DK close, cut 0.02 |

### B3. Kill tests on the headline cells (r3_b_anchored.py)


B1 ML full model, DK close, cut 0.02: price range median +120, shortest -198, longest +900, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 173.9 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 ML full model, DK close, cut 0.02 | all | 159 | 67 | 92 | 0 | -7.18 | -4.13 | -19.71 | 12.67 | 0.6666 |  |
| B1 ML full model, DK close, cut 0.02 | season 2024 | 18 | 5 | 13 | 0 | -7.09 | -36.58 | -73.82 | 0.89 | 0.9432 |  |
| B1 ML full model, DK close, cut 0.02 | season 2025 | 31 | 15 | 16 | 0 | 7.50 | 21.83 | -17.57 | 62.95 | 0.1883 |  |
| B1 ML full model, DK close, cut 0.02 | season 2026 | 70 | 34 | 36 | 0 | 4.52 | 5.91 | -14.47 | 27.43 | 0.3210 |  |
| B1 ML full model, DK close, cut 0.02 | season 2027 | 40 | 13 | 27 | 0 | -12.11 | -27.70 | -59.56 | 8.16 | 0.9061 |  |
| B1 ML full model, DK close, cut 0.02 | early half of each season | 75 | 35 | 40 | 0 | 1.77 | 2.12 | -19.26 | 24.61 | 0.4368 |  |
| B1 ML full model, DK close, cut 0.02 | late half of each season | 84 | 32 | 52 | 0 | -8.95 | -9.91 | -30.79 | 11.31 | 0.7799 |  |
| B1 ML full model, DK close, cut 0.02 | without its 10 best dates | 142 | 51 | 91 | 0 | -38.98 | -24.91 | -36.61 | -11.59 | 0.9996 |  |
| B1 ML full model, DK close, cut 0.02 | side = away | 28 | 7 | 21 | 0 | -10.96 | -37.18 | -70.98 | -2.22 | 0.9658 | 17.60 |
| B1 ML full model, DK close, cut 0.02 | side = home | 131 | 60 | 71 | 0 | 3.78 | 2.62 | -14.41 | 21.39 | 0.4071 | 82.40 |
| B1 ML full model, DK close, cut 0.02 | underdog | 128 | 51 | 77 | 0 | -0.78 | -0.61 | -19.76 | 20.06 | 0.5199 | 80.50 |
| B1 ML full model, DK close, cut 0.02 | favourite | 31 | 16 | 15 | 0 | -6.40 | -14.16 | -35.18 | 7.35 | 0.8654 | 19.50 |
| B1 ML full model, DK close, cut 0.02 | price band +100..+150 | 63 | 24 | 39 | 0 | -11.02 | -17.49 | -39.44 | 4.70 | 0.9027 | 39.60 |
| B1 ML full model, DK close, cut 0.02 | price band -150..-100 | 36 | 21 | 15 | 0 | 3.24 | 7.56 | -15.26 | 30.12 | 0.2889 | 22.60 |
| B1 ML full model, DK close, cut 0.02 | price band -300..-151 | 11 | 4 | 7 | 0 | -7.96 | -41.83 | -72.59 | -5.58 | 0.9754 | 6.90 |
| B1 ML full model, DK close, cut 0.02 | price band > +150 | 49 | 18 | 31 | 0 | 8.56 | 17.47 | -21.81 | 54.03 | 0.2240 | 30.80 |

B1 ML market alone, DK close, cut 0.02: price range median +110, shortest -185, longest +900, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 38.9 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 ML market alone, DK close, cut 0.02 | all | 33 | 13 | 20 | 0 | -5.83 | -14.98 | -46.90 | 14.00 | 0.7906 |  |
| B1 ML market alone, DK close, cut 0.02 | season 2024 | 3 | 2 | 1 | 0 | 1.00 | 23.09 | -28.74 | 62.37 | 0.2774 |  |
| B1 ML market alone, DK close, cut 0.02 | season 2025 | 9 | 4 | 5 | 0 | -1.38 | -13.56 | -76.42 | 31.31 | 0.6641 |  |
| B1 ML market alone, DK close, cut 0.02 | season 2026 | 15 | 6 | 9 | 0 | -1.08 | -6.21 | -56.56 | 38.77 | 0.5866 |  |
| B1 ML market alone, DK close, cut 0.02 | season 2027 | 6 | 1 | 5 | 0 | -4.37 | -62.16 | -100.00 | -4.25 | 0.9760 |  |
| B1 ML market alone, DK close, cut 0.02 | early half of each season | 15 | 6 | 9 | 0 | -2.70 | -14.69 | -61.65 | 30.04 | 0.6996 |  |
| B1 ML market alone, DK close, cut 0.02 | late half of each season | 18 | 7 | 11 | 0 | -3.13 | -15.24 | -56.08 | 20.73 | 0.7436 |  |
| B1 ML market alone, DK close, cut 0.02 | without its 10 best dates | 20 | 1 | 19 | 0 | -20.28 | -91.02 | -100.00 | -75.75 | 1.0000 |  |
| B1 ML market alone, DK close, cut 0.02 | side = away | 18 | 5 | 13 | 0 | -7.63 | -37.33 | -75.58 | 4.04 | 0.9392 | 54.50 |
| B1 ML market alone, DK close, cut 0.02 | side = home | 15 | 8 | 7 | 0 | 1.80 | 9.74 | -29.24 | 48.28 | 0.3416 | 45.50 |
| B1 ML market alone, DK close, cut 0.02 | underdog | 21 | 6 | 15 | 0 | -5.63 | -26.71 | -67.36 | 13.34 | 0.8643 | 63.60 |
| B1 ML market alone, DK close, cut 0.02 | favourite | 12 | 7 | 5 | 0 | -0.20 | -1.12 | -41.22 | 38.62 | 0.5184 | 36.40 |
| B1 ML market alone, DK close, cut 0.02 | price band +100..+150 | 8 | 4 | 4 | 0 | 0.25 | 3.13 | -49.38 | 55.00 | 0.4653 | 24.20 |
| B1 ML market alone, DK close, cut 0.02 | price band -150..-100 | 8 | 4 | 4 | 0 | -0.93 | -9.11 | -73.95 | 40.45 | 0.6002 | 24.20 |
| B1 ML market alone, DK close, cut 0.02 | price band -300..-151 | 5 | 3 | 2 | 0 | -0.35 | -4.02 | -67.20 | 55.19 | 0.5472 | 15.20 |
| B1 ML market alone, DK close, cut 0.02 | price band > +150 | 12 | 2 | 10 | 0 | -4.80 | -40.00 | -100.00 | 20.43 | 0.8622 | 36.40 |

B1 ML full model, best decidable close, cut 0.02: price range median +144, shortest -200, longest +1080, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 371.7 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B1 ML full model, best decidable close, cut 0.02 | all | 338 | 128 | 210 | 0 | -30.69 | -8.26 | -18.43 | 1.83 | 0.9022 |  |
| B1 ML full model, best decidable close, cut 0.02 | season 2024 | 18 | 5 | 13 | 0 | -7.09 | -36.58 | -73.82 | 0.89 | 0.9432 |  |
| B1 ML full model, best decidable close, cut 0.02 | season 2025 | 31 | 15 | 16 | 0 | 7.50 | 21.83 | -17.57 | 62.95 | 0.1883 |  |
| B1 ML full model, best decidable close, cut 0.02 | season 2026 | 221 | 87 | 134 | 0 | -15.36 | -6.28 | -18.13 | 6.28 | 0.7983 |  |
| B1 ML full model, best decidable close, cut 0.02 | season 2027 | 68 | 21 | 47 | 0 | -15.74 | -21.41 | -46.32 | 4.38 | 0.9190 |  |
| B1 ML full model, best decidable close, cut 0.02 | early half of each season | 164 | 60 | 104 | 0 | -28.93 | -15.94 | -32.56 | 1.38 | 0.9447 |  |
| B1 ML full model, best decidable close, cut 0.02 | late half of each season | 174 | 68 | 106 | 0 | -1.76 | -0.92 | -13.86 | 12.44 | 0.5466 |  |
| B1 ML full model, best decidable close, cut 0.02 | without its 10 best dates | 313 | 106 | 207 | 0 | -69.94 | -20.22 | -29.34 | -11.37 | 0.9999 |  |
| B1 ML full model, best decidable close, cut 0.02 | side = away | 135 | 32 | 103 | 0 | -39.36 | -28.57 | -45.55 | -9.79 | 0.9965 | 39.90 |
| B1 ML full model, best decidable close, cut 0.02 | side = home | 203 | 96 | 107 | 0 | 8.67 | 3.71 | -9.30 | 17.34 | 0.3238 | 60.10 |
| B1 ML full model, best decidable close, cut 0.02 | underdog | 273 | 97 | 176 | 0 | -10.41 | -3.81 | -16.69 | 10.34 | 0.6785 | 80.80 |
| B1 ML full model, best decidable close, cut 0.02 | favourite | 65 | 31 | 34 | 0 | -20.28 | -20.65 | -36.03 | -5.43 | 0.9859 | 19.20 |
| B1 ML full model, best decidable close, cut 0.02 | price band +100..+150 | 99 | 44 | 55 | 0 | -4.49 | -4.54 | -22.00 | 12.25 | 0.6696 | 29.30 |
| B1 ML full model, best decidable close, cut 0.02 | price band -150..-100 | 51 | 23 | 28 | 0 | -13.00 | -20.05 | -39.77 | 0.97 | 0.9504 | 15.10 |
| B1 ML full model, best decidable close, cut 0.02 | price band -300..-151 | 26 | 13 | 13 | 0 | -9.62 | -20.95 | -43.08 | 0.72 | 0.9366 | 7.70 |
| B1 ML full model, best decidable close, cut 0.02 | price band > +150 | 162 | 48 | 114 | 0 | -3.58 | -2.21 | -21.62 | 18.43 | 0.5736 | 47.90 |

B2 spread full model, DK close, cut 0.02: price range median -110, shortest -122, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 469.3 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B2 spread full model, DK close, cut 0.02 | all | 428 | 225 | 200 | 3 | 4.44 | 0.95 | -7.07 | 8.60 | 0.4202 |  |
| B2 spread full model, DK close, cut 0.02 | season 2024 | 93 | 46 | 45 | 2 | -3.65 | -3.64 | -21.39 | 14.69 | 0.6293 |  |
| B2 spread full model, DK close, cut 0.02 | season 2025 | 109 | 58 | 51 | 0 | 2.03 | 1.69 | -12.98 | 14.98 | 0.4223 |  |
| B2 spread full model, DK close, cut 0.02 | season 2026 | 166 | 97 | 68 | 1 | 21.97 | 12.03 | 0.88 | 23.32 | 0.0420 |  |
| B2 spread full model, DK close, cut 0.02 | season 2027 | 60 | 24 | 36 | 0 | -15.91 | -23.92 | -43.13 | -5.10 | 0.9789 |  |
| B2 spread full model, DK close, cut 0.02 | early half of each season | 211 | 115 | 94 | 2 | 11.47 | 4.97 | -5.81 | 16.18 | 0.2260 |  |
| B2 spread full model, DK close, cut 0.02 | late half of each season | 217 | 110 | 106 | 1 | -7.03 | -2.95 | -13.91 | 7.17 | 0.6789 |  |
| B2 spread full model, DK close, cut 0.02 | without its 10 best dates | 397 | 195 | 199 | 3 | -24.46 | -5.62 | -12.76 | 1.77 | 0.8925 |  |
| B2 spread full model, DK close, cut 0.02 | side = away | 75 | 32 | 43 | 0 | -15.47 | -18.67 | -37.68 | -1.13 | 0.9554 | 17.50 |
| B2 spread full model, DK close, cut 0.02 | side = home | 353 | 193 | 157 | 3 | 19.91 | 5.15 | -3.86 | 14.29 | 0.1706 | 82.50 |
| B2 spread full model, DK close, cut 0.02 | underdog | 367 | 196 | 169 | 2 | 9.26 | 2.29 | -5.43 | 10.06 | 0.3155 | 85.70 |
| B2 spread full model, DK close, cut 0.02 | favourite | 61 | 29 | 31 | 1 | -4.82 | -7.35 | -25.40 | 12.59 | 0.7387 | 14.30 |
| B2 spread full model, DK close, cut 0.02 | price band +100..+150 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 0.20 |
| B2 spread full model, DK close, cut 0.02 | price band -150..-100 | 427 | 224 | 200 | 3 | 3.44 | 0.73 | -7.27 | 8.31 | 0.4377 | 99.80 |

B2 spread market alone, DK close, cut 0.02: price range median -110, shortest -122, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 82.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| B2 spread market alone, DK close, cut 0.02 | all | 74 | 38 | 36 | 0 | -1.90 | -2.32 | -21.54 | 15.58 | 0.5818 |  |
| B2 spread market alone, DK close, cut 0.02 | season 2024 | 11 | 6 | 5 | 0 | 0.49 | 4.07 | -48.22 | 56.34 | 0.4461 |  |
| B2 spread market alone, DK close, cut 0.02 | season 2025 | 18 | 9 | 9 | 0 | -0.84 | -4.29 | -43.51 | 31.66 | 0.5752 |  |
| B2 spread market alone, DK close, cut 0.02 | season 2026 | 32 | 16 | 16 | 0 | -1.85 | -5.17 | -32.70 | 21.55 | 0.6227 |  |
| B2 spread market alone, DK close, cut 0.02 | season 2027 | 13 | 7 | 6 | 0 | 0.30 | 2.05 | -41.27 | 45.53 | 0.4688 |  |
| B2 spread market alone, DK close, cut 0.02 | early half of each season | 35 | 20 | 15 | 0 | 3.46 | 8.95 | -17.58 | 32.53 | 0.2817 |  |
| B2 spread market alone, DK close, cut 0.02 | late half of each season | 39 | 18 | 21 | 0 | -5.36 | -12.37 | -36.63 | 15.10 | 0.7859 |  |
| B2 spread market alone, DK close, cut 0.02 | without its 10 best dates | 61 | 25 | 36 | 0 | -14.90 | -22.01 | -39.10 | -4.69 | 0.9797 |  |
| B2 spread market alone, DK close, cut 0.02 | side = away | 39 | 16 | 23 | 0 | -9.43 | -21.84 | -46.46 | 2.96 | 0.9290 | 52.70 |
| B2 spread market alone, DK close, cut 0.02 | side = home | 35 | 22 | 13 | 0 | 7.53 | 19.39 | -7.66 | 46.52 | 0.1210 | 47.30 |
| B2 spread market alone, DK close, cut 0.02 | underdog | 51 | 23 | 28 | 0 | -8.11 | -14.29 | -36.67 | 6.26 | 0.8593 | 68.90 |
| B2 spread market alone, DK close, cut 0.02 | favourite | 23 | 15 | 8 | 0 | 6.21 | 24.58 | -8.67 | 55.90 | 0.0979 | 31.10 |
| B2 spread market alone, DK close, cut 0.02 | price band +100..+150 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 1.40 |
| B2 spread market alone, DK close, cut 0.02 | price band -150..-100 | 73 | 37 | 36 | 0 | -2.90 | -3.58 | -22.83 | 13.68 | 0.6265 | 98.60 |

Placebo, moneyline full model at the DraftKings close (the model's shift shuffled across each season's games):

| placebo runs | real ret% | placebo mean ret% | placebo 95th pct | share >= real |
|---|---|---|---|---|
| 200 | -4.13 | -5.55 | 5.79 | 0.42 |

Placebo, spread full model at the DraftKings close:

| placebo runs | real ret% | placebo mean ret% | placebo 95th pct | share >= real |
|---|---|---|---|---|
| 200 | 0.95 | -1.63 | 4.74 | 0.27 |

## C. Totals (r3_c_totals.py)

Played games 2021-22 on: 1797; closing total from Pinnacle 1642, from DraftKings 130, none 25; with a crew listed 1797. Mean residual (actual - close) +0.85 points, SD 16.64.

Score distribution on the graded games (2022-23 on): crew_score: SD 0.911, share |score| >= 1.0: 31.5%, exact_score: SD 0.339, share |score| >= 1.0: 2.9%; mean earlier games per referee 58.

### C1. Does the prior crew score predict the residual? (out of sample by season)

| score | season | games | slope (pts per pt) | se | t | corr |
|---|---|---|---|---|---|---|
| crew_score | 2023 | 310 | 2.4290 | 0.86 | 2.83 | 0.1591 |
| crew_score | 2024 | 331 | -0.0660 | 1.06 | -0.06 | -0.0034 |
| crew_score | 2025 | 330 | 0.5240 | 0.95 | 0.55 | 0.0303 |
| crew_score | 2026 | 402 | -1.0390 | 1.07 | -0.97 | -0.0485 |
| crew_score | 2027 | 107 | -0.6650 | 2.35 | -0.28 | -0.0276 |
| crew_score | pooled 2023-2027 | 1,480 | 0.4510 | 0.47 | 0.95 | 0.0248 |
| exact_score | 2023 | 310 | 7.4530 | 4.61 | 1.62 | 0.0917 |
| exact_score | 2024 | 331 | -2.1420 | 1.89 | -1.13 | -0.0622 |
| exact_score | 2025 | 330 | -5.0260 | 2.78 | -1.81 | -0.0993 |
| exact_score | 2026 | 402 | -1.1050 | 2.56 | -0.43 | -0.0216 |
| exact_score | 2027 | 107 | 15.7150 | 9.62 | 1.63 | 0.1574 |
| exact_score | pooled 2023-2027 | 1,480 | -1.4210 | 1.27 | -1.12 | -0.0291 |

### C2. The crew bet rule at the DraftKings closing total, 2022-23 on

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C | C2 crew_score rule, DK close, c 0.5 | 910 | 450 | 449 | 11 | -43.58 | -4.41 | -9.39 | 0.10 | 0.9377 | 74.70 |
| C | C2 crew_score rule, DK close, c 1.0 | 466 | 244 | 216 | 6 | 6.63 | 1.31 | -5.52 | 8.09 | 0.3743 | 81.50 |
| C | C2 crew_score rule, DK close, c 1.5 | 215 | 113 | 99 | 3 | 3.93 | 1.69 | -8.66 | 11.86 | 0.3937 | 82.30 |
| C | C2 crew_score rule, DK close, c 2.0 | 59 | 34 | 25 | 0 | 6.40 | 9.88 | -12.90 | 30.77 | 0.2227 | 89.80 |
| C | C2 exact_score rule, DK close, c 0.5 | 68 | 26 | 41 | 1 | -19.05 | -25.90 | -42.94 | -7.45 | 0.9926 | 47.10 |
| C | C2 exact_score rule, DK close, c 1.0 | 43 | 16 | 26 | 1 | -12.53 | -27.26 | -48.80 | -6.16 | 0.9829 | 48.80 |
| C | C2 exact_score rule, DK close, c 1.5 | 19 | 5 | 13 | 1 | -9.30 | -47.09 | -78.85 | -10.70 | 0.9907 | 42.10 |
| C | C2 exact_score rule, DK close, c 2.0 | 13 | 4 | 8 | 1 | -4.80 | -36.56 | -82.50 | 11.43 | 0.9171 | 38.50 |

Placebo at the headline c = 1.0 (scores shuffled across each season's games, 200 times):

| score | real ret% | placebo mean ret% | placebo 95th pct | share >= real |
|---|---|---|---|---|
| crew_score | 1.31 | -3.93 | 1.67 | 0.09 |
| exact_score | -27.26 | -5.52 | 15.60 | 0.94 |

Kill rows, crew_score rule at c = 1.0: price range median -110, shortest -115, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 505.1 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 crew_score c 1.0 | all | 466 | 244 | 216 | 6 | 6.63 | 1.31 | -5.52 | 8.09 | 0.3743 |  |
| C2 crew_score c 1.0 | season 2023 | 104 | 63 | 39 | 2 | 19.80 | 17.62 | 3.82 | 32.10 | 0.0193 |  |
| C2 crew_score c 1.0 | season 2024 | 100 | 54 | 44 | 2 | 5.74 | 5.34 | -10.68 | 19.82 | 0.2781 |  |
| C2 crew_score c 1.0 | season 2025 | 106 | 54 | 50 | 2 | -1.00 | -0.87 | -15.43 | 13.79 | 0.5390 |  |
| C2 crew_score c 1.0 | season 2026 | 124 | 57 | 67 | 0 | -16.43 | -12.09 | -25.58 | 1.73 | 0.9275 |  |
| C2 crew_score c 1.0 | season 2027 | 32 | 16 | 16 | 0 | -1.48 | -4.25 | -31.58 | 24.20 | 0.5979 |  |
| C2 crew_score c 1.0 | early half of each season | 230 | 130 | 98 | 2 | 22.14 | 8.84 | -0.99 | 18.98 | 0.0699 |  |
| C2 crew_score c 1.0 | late half of each season | 236 | 114 | 118 | 4 | -15.51 | -6.09 | -16.56 | 3.80 | 0.8429 |  |
| C2 crew_score c 1.0 | without its 10 best dates | 442 | 220 | 216 | 6 | -17.37 | -3.63 | -10.19 | 2.86 | 0.8193 |  |
| C2 crew_score c 1.0 | side = over | 380 | 196 | 180 | 4 | -1.68 | -0.41 | -8.10 | 7.24 | 0.5341 | 81.50 |
| C2 crew_score c 1.0 | side = under | 86 | 48 | 36 | 2 | 8.31 | 9.01 | -7.16 | 24.30 | 0.1746 | 18.50 |
| C2 crew_score c 1.0 | price band +100..+150 | 1 | 1 | 0 | 0 | 1.00 | 100.00 | 100.00 | 100.00 |  | 0.20 |
| C2 crew_score c 1.0 | price band -150..-100 | 465 | 243 | 216 | 6 | 5.63 | 1.12 | -5.77 | 7.84 | 0.3937 | 99.80 |

Kill rows, exact_score rule at c = 1.0: price range median -110, shortest -112, longest -105, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 46.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C2 exact_score c 1.0 | all | 43 | 16 | 26 | 1 | -12.53 | -27.26 | -48.80 | -6.16 | 0.9829 |  |
| C2 exact_score c 1.0 | season 2023 | 4 | 2 | 2 | 0 | -0.20 | -4.55 | -100.00 | 45.57 | 0.5381 |  |
| C2 exact_score c 1.0 | season 2024 | 14 | 6 | 7 | 1 | -1.72 | -12.03 | -52.87 | 32.26 | 0.6785 |  |
| C2 exact_score c 1.0 | season 2025 | 8 | 1 | 7 | 0 | -6.68 | -76.26 | -100.00 | -42.86 | 1.0000 |  |
| C2 exact_score c 1.0 | season 2026 | 15 | 5 | 10 | 0 | -5.93 | -36.25 | -70.48 | -3.96 | 0.9676 |  |
| C2 exact_score c 1.0 | season 2027 | 2 | 2 | 0 | 0 | 2.00 | 93.02 | 90.91 | 95.24 | 0.0000 |  |
| C2 exact_score c 1.0 | early half of each season | 21 | 7 | 14 | 0 | -8.33 | -36.20 | -71.08 | -4.12 | 0.9698 |  |
| C2 exact_score c 1.0 | late half of each season | 22 | 9 | 12 | 1 | -4.20 | -18.29 | -49.95 | 13.08 | 0.8323 |  |
| C2 exact_score c 1.0 | without its 10 best dates | 33 | 6 | 26 | 1 | -22.53 | -64.46 | -82.36 | -44.06 | 1.0000 |  |
| C2 exact_score c 1.0 | side = over | 21 | 9 | 11 | 1 | -3.03 | -13.89 | -49.45 | 20.78 | 0.7523 | 48.80 |
| C2 exact_score c 1.0 | side = under | 22 | 7 | 15 | 0 | -9.50 | -39.32 | -65.45 | -8.65 | 0.9839 | 51.20 |
| C2 exact_score c 1.0 | price band -150..-100 | 43 | 16 | 26 | 1 | -12.53 | -27.26 | -48.80 | -6.16 | 0.9829 | 100.00 |

### C3. DraftKings' first-post total, blind, by season

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | subset |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C | C3 DK first post over | 1,772 | 912 | 854 | 6 | -26.76 | -1.38 | -5.48 | 2.53 | 0.7153 | 2021-22 on |
| C | C3 DK first post over | 292 | 143 | 148 | 1 | -19.45 | -6.08 | -14.54 | 3.21 | 0.8697 | season 2022 |
| C | C3 DK first post over | 310 | 159 | 148 | 3 | -4.20 | -1.24 | -10.66 | 8.55 | 0.5833 | season 2023 |
| C | C3 DK first post over | 331 | 172 | 157 | 2 | -0.53 | -0.15 | -9.13 | 8.54 | 0.5112 | season 2024 |
| C | C3 DK first post over | 330 | 174 | 156 | 0 | 2.90 | 0.80 | -9.38 | 11.12 | 0.4483 | season 2025 |
| C | C3 DK first post over | 402 | 206 | 196 | 0 | -9.63 | -2.18 | -10.95 | 6.12 | 0.6627 | season 2026 |
| C | C3 DK first post over | 107 | 58 | 49 | 0 | 4.15 | 3.54 | -9.18 | 15.74 | 0.3198 | season 2027 |
| C | C3 DK first post under | 1,772 | 854 | 912 | 6 | -149.44 | -7.69 | -11.68 | -3.64 | 0.9992 | 2021-22 on |
| C | C3 DK first post under | 292 | 148 | 143 | 1 | -9.40 | -2.93 | -12.35 | 5.73 | 0.7034 | season 2022 |
| C | C3 DK first post under | 310 | 148 | 159 | 3 | -26.95 | -7.99 | -17.69 | 1.35 | 0.9119 | season 2023 |
| C | C3 DK first post under | 331 | 157 | 172 | 2 | -31.80 | -8.79 | -17.46 | 0.07 | 0.9547 | season 2024 |
| C | C3 DK first post under | 330 | 156 | 174 | 0 | -35.92 | -9.87 | -20.16 | 0.19 | 0.9461 | season 2025 |
| C | C3 DK first post under | 402 | 196 | 206 | 0 | -30.31 | -6.86 | -15.20 | 1.96 | 0.9070 | season 2026 |
| C | C3 DK first post under | 107 | 49 | 58 | 0 | -15.06 | -12.76 | -24.82 | -0.13 | 0.9548 | season 2027 |

### C4. DraftKings open-to-close total movement

| season | games | mean |move| | share moved | slope of (actual - DK close) on move | se | corr |
|---|---|---|---|---|---|---|
| 2022 | 292 | 1.33 | 86.60 | -0.8560 | 0.56 | -0.0886 |
| 2023 | 310 | 1.19 | 83.90 | -0.2720 | 0.57 | -0.0271 |
| 2024 | 331 | 1.59 | 90.30 | 0.4030 | 0.45 | 0.0495 |
| 2025 | 330 | 1.60 | 90.00 | -0.1680 | 0.44 | -0.0210 |
| 2026 | 402 | 1.77 | 79.90 | 0.0660 | 0.38 | 0.0087 |
| 2027 | 107 | 2.68 | 87.90 | 0.5440 | 0.55 | 0.0962 |
| pooled | 1,772 | 1.58 | 86.00 | 0.0200 | 0.19 | 0.0025 |

Follow the move at the DraftKings close (over when the total rose by k or more, under when it fell by k or more):

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C | C4 follow the DK move at the DK close, k 1 | 1,255 | 636 | 610 | 9 | -32.54 | -2.38 | -6.24 | 1.76 | 0.8405 | 57.60 |
| C | C4 follow the DK move at the DK close, k 2 | 659 | 327 | 327 | 5 | -31.14 | -4.35 | -10.09 | 1.78 | 0.8836 | 59.50 |
| C | C4 follow the DK move at the DK close, k 3 | 320 | 156 | 160 | 4 | -19.01 | -5.49 | -14.76 | 3.31 | 0.8428 | 61.30 |
| C | C4 follow the DK move at the DK close, k 4 | 148 | 79 | 68 | 1 | 4.76 | 2.96 | -10.39 | 16.21 | 0.3526 | 64.20 |

The mirror (fade the move), printed for the side control, not counted:

| rule | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| fade the move at the DK close, k 1 (mirror, not counted) | 1,255 | 610 | 636 | 9 | -91.74 | -6.67 | -10.80 | -2.84 | 0.9975 |
| fade the move at the DK close, k 2 (mirror, not counted) | 659 | 327 | 327 | 5 | -34.06 | -4.72 | -10.84 | 0.88 | 0.9027 |
| fade the move at the DK close, k 3 (mirror, not counted) | 320 | 160 | 156 | 4 | -11.95 | -3.42 | -12.23 | 5.76 | 0.7355 |
| fade the move at the DK close, k 4 (mirror, not counted) | 148 | 68 | 79 | 1 | -19.05 | -11.73 | -24.91 | 1.70 | 0.9336 |

Kill rows, follow rule at k = 2: price range median -110, shortest -120, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 716.5 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| C4 follow k 2 | all | 659 | 327 | 327 | 5 | -31.14 | -4.35 | -10.09 | 1.78 | 0.8836 |  |
| C4 follow k 2 | season 2022 | 89 | 46 | 43 | 0 | -0.60 | -0.62 | -18.55 | 18.48 | 0.5223 |  |
| C4 follow k 2 | season 2023 | 69 | 33 | 35 | 1 | -5.35 | -7.17 | -25.00 | 10.45 | 0.7443 |  |
| C4 follow k 2 | season 2024 | 123 | 66 | 56 | 1 | 4.56 | 3.41 | -9.94 | 16.59 | 0.3364 |  |
| C4 follow k 2 | season 2025 | 119 | 56 | 60 | 3 | -9.96 | -7.79 | -22.70 | 6.02 | 0.8111 |  |
| C4 follow k 2 | season 2026 | 189 | 89 | 100 | 0 | -20.67 | -9.98 | -21.01 | 1.66 | 0.9258 |  |
| C4 follow k 2 | season 2027 | 70 | 37 | 33 | 0 | 0.88 | 1.15 | -15.60 | 20.09 | 0.4570 |  |
| C4 follow k 2 | early half of each season | 325 | 163 | 160 | 2 | -12.36 | -3.49 | -13.20 | 4.84 | 0.7400 |  |
| C4 follow k 2 | late half of each season | 334 | 164 | 167 | 3 | -18.78 | -5.19 | -13.59 | 2.72 | 0.8450 |  |
| C4 follow k 2 | without its 10 best dates | 627 | 297 | 325 | 5 | -58.97 | -8.65 | -14.47 | -2.86 | 0.9922 |  |
| C4 follow k 2 | side = over | 392 | 192 | 196 | 4 | -22.43 | -5.28 | -13.14 | 2.33 | 0.8721 | 59.50 |
| C4 follow k 2 | side = under | 267 | 135 | 131 | 1 | -8.71 | -2.99 | -11.65 | 6.74 | 0.6924 | 40.50 |
| C4 follow k 2 | price band +100..+150 | 12 | 7 | 5 | 0 | 2.00 | 16.67 | -20.00 | 60.00 | 0.2402 | 1.80 |
| C4 follow k 2 | price band -150..-100 | 647 | 320 | 322 | 5 | -33.14 | -4.70 | -10.98 | 1.05 | 0.8989 | 98.20 |

The hindsight ceiling (bet DraftKings' first post in the direction of its later move; not a rule, not counted):

| ceiling | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| first post, direction of the later move | 1,524 | 845 | 673 | 6 | 101.74 | 6.07 | 2.36 | 9.73 | 0.0041 |

## D. First half and first quarter: our own mechanisms (r3_d_periods.py)


### H1-i. Club-pair H1 share of the full-game total (r3_d_periods.py)

Pair-share deviation from the league mean on the priced games: SD 0.0040, league mean share 0.5006; anchor sources at T-10: {'pinnacle ladder': 1113, 'draftkings main': 38}.

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | H1-i totals_h1 share rule, decidable, m 0.5 | 243 | 137 | 106 | 0 | 10.22 | 3.53 | -5.65 | 12.17 | 0.2621 | 55.10 |
| D | H1-i totals_h1 share rule, OFFSHORE reference 2023-24/2024-25, m 0.5 | 392 | 192 | 192 | 8 | -35.25 | -7.76 | -15.54 | -0.29 | 0.9473 | 43.90 |
| D | H1-i totals_h1 share rule, decidable, m 1.0 | 118 | 70 | 48 | 0 | 11.05 | 7.77 | -7.72 | 21.94 | 0.1904 | 63.60 |
| D | H1-i totals_h1 share rule, OFFSHORE reference 2023-24/2024-25, m 1.0 | 158 | 74 | 79 | 5 | -19.98 | -11.03 | -23.97 | 3.02 | 0.9108 | 46.80 |
| D | H1-i totals_h1 share rule, decidable, m 1.5 | 41 | 27 | 14 | 0 | 9.03 | 17.78 | -7.39 | 41.03 | 0.1086 | 65.90 |
| D | H1-i totals_h1 share rule, OFFSHORE reference 2023-24/2024-25, m 1.5 | 64 | 29 | 33 | 2 | -10.61 | -14.38 | -31.83 | 5.33 | 0.8923 | 48.40 |
| D | H1-i totals_h1 share rule, decidable, m 2.0 | 11 | 8 | 3 | 0 | 4.20 | 30.61 | -13.15 | 65.48 | 0.1198 | 81.80 |
| D | H1-i totals_h1 share rule, OFFSHORE reference 2023-24/2024-25, m 2.0 | 10 | 4 | 6 | 0 | -3.32 | -27.55 | -65.29 | 27.15 | 0.8310 | 40.00 |

Placebo (pair deviations shuffled across each season's games, 200 times), the headline:

| m | real ret% | placebo mean ret% | placebo 95th pct | share >= real |
|---|---|---|---|---|
| 1.00 | 7.77 | 1.38 | 11.71 | 0.20 |

Kill rows at m = 1.0 (the headline): price range median -120, shortest -140, longest -104, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 142.3 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1-i m 1.0 | all | 118 | 70 | 48 | 0 | 11.05 | 7.77 | -7.72 | 21.94 | 0.1904 |  |
| H1-i m 1.0 | season 2026 | 86 | 50 | 36 | 0 | 5.16 | 4.93 | -11.93 | 21.83 | 0.3145 |  |
| H1-i m 1.0 | season 2027 | 32 | 20 | 12 | 0 | 5.89 | 15.66 | -13.74 | 43.93 | 0.1851 |  |
| H1-i m 1.0 | early half of each season | 57 | 34 | 23 | 0 | 5.34 | 7.66 | -13.59 | 27.06 | 0.2707 |  |
| H1-i m 1.0 | late half of each season | 61 | 36 | 25 | 0 | 5.71 | 7.87 | -10.78 | 27.00 | 0.2513 |  |
| H1-i m 1.0 | without its 10 best dates | 93 | 45 | 48 | 0 | -13.95 | -12.44 | -26.52 | 1.38 | 0.9323 |  |
| H1-i m 1.0 | side = over | 75 | 43 | 32 | 0 | 2.80 | 3.02 | -15.22 | 20.70 | 0.3920 | 63.60 |
| H1-i m 1.0 | side = under | 43 | 27 | 16 | 0 | 8.25 | 16.65 | -8.02 | 40.78 | 0.1317 | 36.40 |
| H1-i m 1.0 | price band -150..-100 | 118 | 70 | 48 | 0 | 11.05 | 7.77 | -7.72 | 21.94 | 0.1904 | 100.00 |

### Q1-i. Club-pair Q1 share of the full-game total (r3_d_periods.py)

Pair-share deviation from the league mean on the priced games: SD 0.0028, league mean share 0.2495; anchor sources at T-10: {'pinnacle ladder': 1113, 'draftkings main': 38}.

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | Q1-i totals_q1 share rule, decidable, m 0.25 | 285 | 152 | 133 | 0 | -4.62 | -1.37 | -10.24 | 8.16 | 0.5968 | 43.20 |
| D | Q1-i totals_q1 share rule, OFFSHORE reference 2023-24/2024-25, m 0.25 | 435 | 229 | 206 | 0 | -17.76 | -3.41 | -11.59 | 4.62 | 0.7546 | 17.20 |
| D | Q1-i totals_q1 share rule, decidable, m 0.5 | 191 | 100 | 91 | 0 | -8.45 | -3.68 | -15.00 | 8.39 | 0.6938 | 48.20 |
| D | Q1-i totals_q1 share rule, OFFSHORE reference 2023-24/2024-25, m 0.5 | 301 | 161 | 140 | 0 | -6.63 | -1.84 | -12.11 | 7.98 | 0.6201 | 11.30 |
| D | Q1-i totals_q1 share rule, decidable, m 0.75 | 106 | 61 | 45 | 0 | 5.84 | 4.44 | -10.75 | 20.41 | 0.3203 | 53.80 |
| D | Q1-i totals_q1 share rule, OFFSHORE reference 2023-24/2024-25, m 0.75 | 193 | 108 | 85 | 0 | 6.32 | 2.74 | -9.50 | 14.56 | 0.3567 | 6.20 |
| D | Q1-i totals_q1 share rule, decidable, m 1.0 | 63 | 43 | 20 | 0 | 17.71 | 22.23 | 4.08 | 39.66 | 0.0188 | 54.00 |
| D | Q1-i totals_q1 share rule, OFFSHORE reference 2023-24/2024-25, m 1.0 | 129 | 72 | 57 | 0 | 3.92 | 2.54 | -11.37 | 16.47 | 0.3836 | 2.30 |

Placebo (pair deviations shuffled across each season's games, 200 times), the headline and every other grid cell with its interval above zero:

| m | real ret% | placebo mean ret% | placebo 95th pct | share >= real |
|---|---|---|---|---|
| 0.50 | -3.68 | -4.47 | 4.60 | 0.41 |
| 1.00 | 22.23 | -1.64 | 14.68 | 0.01 |

Kill rows at m = 0.5 (the headline): price range median -120, shortest -148, longest +100, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 229.9 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1-i m 0.5 | all | 191 | 100 | 91 | 0 | -8.45 | -3.68 | -15.00 | 8.39 | 0.6938 |  |
| Q1-i m 0.5 | season 2026 | 150 | 78 | 72 | 0 | -7.85 | -4.36 | -17.01 | 8.80 | 0.7094 |  |
| Q1-i m 0.5 | season 2027 | 41 | 22 | 19 | 0 | -0.60 | -1.21 | -26.77 | 26.71 | 0.5299 |  |
| Q1-i m 0.5 | early half of each season | 95 | 48 | 47 | 0 | -9.40 | -8.01 | -23.44 | 7.55 | 0.7998 |  |
| Q1-i m 0.5 | late half of each season | 96 | 52 | 44 | 0 | 0.95 | 0.84 | -16.91 | 20.78 | 0.4708 |  |
| Q1-i m 0.5 | without its 10 best dates | 164 | 73 | 91 | 0 | -35.45 | -18.01 | -28.71 | -6.91 | 0.9972 |  |
| Q1-i m 0.5 | side = over | 92 | 48 | 44 | 0 | -6.87 | -5.95 | -22.82 | 11.32 | 0.7235 | 48.20 |
| Q1-i m 0.5 | side = under | 99 | 52 | 47 | 0 | -1.58 | -1.38 | -15.92 | 13.46 | 0.5596 | 51.80 |
| Q1-i m 0.5 | price band +100..+150 | 3 | 2 | 1 | 0 | 1.00 | 33.33 | -33.33 | 100.00 | 0.2698 | 1.60 |
| Q1-i m 0.5 | price band -150..-100 | 188 | 98 | 90 | 0 | -9.45 | -4.17 | -15.73 | 7.67 | 0.7184 | 98.40 |

Kill rows at m = 1.0 (NOT the headline: a grid cell with its interval above zero): price range median -122, shortest -145, longest -111, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 79.7 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1-i m 1.0 | all | 63 | 43 | 20 | 0 | 17.71 | 22.23 | 4.08 | 39.66 | 0.0188 |  |
| Q1-i m 1.0 | season 2026 | 53 | 36 | 17 | 0 | 14.43 | 21.38 | 2.45 | 40.39 | 0.0332 |  |
| Q1-i m 1.0 | season 2027 | 10 | 7 | 3 | 0 | 3.28 | 26.89 | -9.96 | 82.73 | 0.1630 |  |
| Q1-i m 1.0 | early half of each season | 31 | 20 | 11 | 0 | 5.74 | 14.26 | -10.41 | 38.25 | 0.1685 |  |
| Q1-i m 1.0 | late half of each season | 32 | 23 | 9 | 0 | 11.97 | 30.36 | 4.55 | 57.76 | 0.0302 |  |
| Q1-i m 1.0 | without its 10 best dates | 48 | 28 | 20 | 0 | 2.71 | 4.46 | -13.71 | 25.32 | 0.3560 |  |
| Q1-i m 1.0 | side = over | 34 | 23 | 11 | 0 | 8.66 | 19.71 | -7.46 | 48.99 | 0.1198 | 54.00 |
| Q1-i m 1.0 | side = under | 29 | 20 | 9 | 0 | 9.05 | 25.32 | -5.37 | 48.86 | 0.0618 | 46.00 |
| Q1-i m 1.0 | price band -150..-100 | 63 | 43 | 20 | 0 | 17.71 | 22.23 | 4.08 | 39.66 | 0.0188 | 100.00 |

### H1-ii. The H1 moneyline shrunk toward 50% (r3_d_periods.py)

k (logit P = k x logit(median no-vig over every book at T-10), no intercept, ties out), fitted on earlier seasons: graded 2026: k = 1.2330 on 552 games; graded 2027: k = 1.0638 on 942 games

Decidable books quoting at T-10 in the graded seasons: {(2026, 'betmgm'): 356, (2026, 'betrivers'): 316, (2026, 'fanduel'): 287, (2027, 'betmgm'): 105, (2027, 'betrivers'): 106, (2027, 'fanduel'): 107}

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | underdog share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | H1-ii h2h_h1 shrink, decidable, cut 0.00 | 331 | 157 | 174 | 0 | -68.93 | -14.45 | -21.90 | -6.13 | 0.9989 | 19.60 |
| D | H1-ii h2h_h1 shrink, decidable, cut 0.01 | 250 | 122 | 128 | 0 | -62.38 | -16.35 | -25.67 | -7.58 | 0.9984 | 12.80 |
| D | H1-ii h2h_h1 shrink, decidable, cut 0.02 | 150 | 77 | 73 | 0 | -42.68 | -17.00 | -27.52 | -6.30 | 0.9965 | 8.00 |
| D | H1-ii h2h_h1 shrink, decidable, cut 0.03 | 69 | 36 | 33 | 0 | -23.93 | -19.05 | -34.24 | -3.63 | 0.9788 | 1.40 |
| D | H1-ii h2h_h1 shrink, decidable, cut 0.04 | 31 | 14 | 17 | 0 | -16.90 | -29.81 | -53.50 | -4.30 | 0.9777 | 3.20 |

Controls (not counted): the blind underdog at the best decidable price:

| control | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| every graded game | 397 | 159 | 238 | 0 | 7.39 | 1.86 | -7.22 | 11.25 | 0.3730 |
| the headline rule's games only | 144 | 65 | 79 | 0 | 11.49 | 7.98 | -8.07 | 23.21 | 0.2020 |
| every graded game, season 2026 | 309 | 130 | 179 | 0 | 22.23 | 7.19 | -4.23 | 18.59 | 0.1549 |
| every graded game, season 2027 | 88 | 29 | 59 | 0 | -14.84 | -16.86 | -31.58 | -2.62 | 0.9686 |

Kill rows at the headline cut 0.02: price range median -175, shortest -200, longest +380, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 251.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1-ii cut 0.02 | all | 150 | 77 | 73 | 0 | -42.68 | -17.00 | -27.52 | -6.30 | 0.9965 |  |
| H1-ii cut 0.02 | season 2026 | 120 | 61 | 59 | 0 | -35.59 | -17.59 | -29.01 | -6.50 | 0.9933 |  |
| H1-ii cut 0.02 | season 2027 | 30 | 16 | 14 | 0 | -7.09 | -14.56 | -37.47 | 4.23 | 0.8750 |  |
| H1-ii cut 0.02 | early half of each season | 75 | 37 | 38 | 0 | -26.17 | -21.14 | -38.06 | -5.75 | 0.9833 |  |
| H1-ii cut 0.02 | late half of each season | 75 | 40 | 35 | 0 | -16.51 | -12.98 | -26.93 | 0.57 | 0.9339 |  |
| H1-ii cut 0.02 | without its 10 best dates | 127 | 55 | 72 | 0 | -62.94 | -29.77 | -40.12 | -19.04 | 1.0000 |  |
| H1-ii cut 0.02 | side = away | 44 | 19 | 25 | 0 | -22.00 | -30.41 | -51.40 | -8.66 | 0.9906 | 29.30 |
| H1-ii cut 0.02 | side = home | 106 | 58 | 48 | 0 | -20.68 | -11.58 | -23.47 | 0.31 | 0.9430 | 70.70 |
| H1-ii cut 0.02 | underdog | 12 | 3 | 9 | 0 | -5.74 | -47.83 | -82.50 | -6.09 | 0.9780 | 8.00 |
| H1-ii cut 0.02 | favourite | 138 | 74 | 64 | 0 | -36.94 | -15.46 | -26.73 | -3.89 | 0.9880 | 92.00 |
| H1-ii cut 0.02 | price band +100..+150 | 6 | 3 | 3 | 0 | 0.26 | 4.33 | -60.00 | 66.40 | 0.4534 | 4.00 |
| H1-ii cut 0.02 | price band -150..-100 | 18 | 8 | 10 | 0 | -5.42 | -23.22 | -54.52 | 9.40 | 0.8788 | 12.00 |
| H1-ii cut 0.02 | price band -300..-151 | 120 | 66 | 54 | 0 | -31.52 | -14.62 | -26.56 | -3.79 | 0.9835 | 80.00 |
| H1-ii cut 0.02 | price band > +150 | 6 | 0 | 6 | 0 | -6.00 | -100.00 | -100.00 | -100.00 |  | 4.00 |

### Q1-ii. The Q1 moneyline shrunk toward 50% (r3_d_periods.py)

k (logit P = k x logit(median no-vig over every book at T-10), no intercept, ties out), fitted on earlier seasons: graded 2026: k = 0.9365 on 337 games; graded 2027: k = 0.8733 on 641 games

Decidable books quoting at T-10 in the graded seasons: {(2026, 'betmgm'): 3, (2026, 'betrivers'): 316, (2027, 'betmgm'): 104, (2027, 'betrivers'): 106}

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | underdog share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.00 | 402 | 172 | 230 | 0 | -13.08 | -3.21 | -12.66 | 5.75 | 0.7173 | 82.10 |
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.01 | 98 | 33 | 65 | 0 | -17.11 | -17.38 | -36.97 | 2.76 | 0.9274 | 89.80 |
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.02 | 19 | 6 | 13 | 0 | -3.20 | -16.84 | -60.25 | 28.16 | 0.7315 | 100.00 |
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.03 | 3 | 3 | 0 | 0 | 5.65 | 188.33 | 171.67 | 205.00 | 0.0000 | 100.00 |
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.04 | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |

Controls (not counted): the blind underdog at the best decidable price:

| control | bets | W | L | P | units | ret% | lo% | hi% | p_one |
|---|---|---|---|---|---|---|---|---|---|
| every graded game | 330 | 133 | 197 | 0 | -16.59 | -5.03 | -15.34 | 5.87 | 0.7806 |
| the headline rule's games only | 19 | 6 | 13 | 0 | -3.20 | -16.84 | -60.25 | 28.16 | 0.7315 |
| every graded game, season 2026 | 257 | 107 | 150 | 0 | -2.19 | -0.85 | -13.05 | 11.30 | 0.5431 |
| every graded game, season 2027 | 73 | 26 | 47 | 0 | -14.40 | -19.73 | -36.90 | -2.81 | 0.9717 |

Kill rows at the headline cut 0.02: price range median +155, shortest +110, longest +215, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 19.0 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1-ii cut 0.02 | all | 19 | 6 | 13 | 0 | -3.20 | -16.84 | -60.25 | 28.16 | 0.7315 |  |
| Q1-ii cut 0.02 | season 2026 | 1 | 1 | 0 | 0 | 1.55 | 155.00 | 155.00 | 155.00 | 0.0000 |  |
| Q1-ii cut 0.02 | season 2027 | 18 | 5 | 13 | 0 | -4.75 | -26.39 | -71.05 | 20.56 | 0.8290 |  |
| Q1-ii cut 0.02 | early half of each season | 9 | 1 | 8 | 0 | -6.35 | -70.56 | -100.00 | -11.67 | 0.9925 |  |
| Q1-ii cut 0.02 | late half of each season | 10 | 5 | 5 | 0 | 3.15 | 31.50 | -25.55 | 97.22 | 0.2018 |  |
| Q1-ii cut 0.02 | without its 10 best dates | 8 | 0 | 8 | 0 | -8.00 | -100.00 | -100.00 | -100.00 |  |  |
| Q1-ii cut 0.02 | side = away | 16 | 4 | 12 | 0 | -5.10 | -31.87 | -81.04 | 14.67 | 0.8720 | 84.20 |
| Q1-ii cut 0.02 | side = home | 3 | 2 | 1 | 0 | 1.90 | 63.33 | -25.00 | 151.67 | 0.1722 | 15.80 |
| Q1-ii cut 0.02 | underdog | 19 | 6 | 13 | 0 | -3.20 | -16.84 | -60.25 | 28.16 | 0.7315 | 100.00 |
| Q1-ii cut 0.02 | price band +100..+150 | 9 | 2 | 7 | 0 | -4.40 | -48.89 | -100.00 | 15.00 | 0.9221 | 47.40 |
| Q1-ii cut 0.02 | price band > +150 | 10 | 4 | 6 | 0 | 1.20 | 12.00 | -48.00 | 87.55 | 0.3903 | 52.60 |

### H1-iii. The stale H1 total: the full game moved T-60 -> T-10 (r3_d_periods.py)

Decidable quotes with both marks and a Pinnacle move: 832 on 423 games; Pinnacle full-game total moved on 71.3% of them (mean |move| 0.21); the book's h1 line moved on 7.6%; |gap| >= 1.0 on 4.9%.

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | H1-iii totals_h1 stale rule, decidable, m 0.5 | 68 | 35 | 33 | 0 | -5.07 | -6.14 | -25.81 | 13.03 | 0.7038 | 41.20 |
| D | H1-iii totals_h1 stale rule, decidable, m 1.0 | 39 | 23 | 16 | 0 | 3.35 | 6.99 | -17.87 | 29.88 | 0.3192 | 38.50 |
| D | H1-iii totals_h1 stale rule, decidable, m 1.5 | 11 | 6 | 5 | 0 | -0.23 | -1.65 | -48.40 | 39.97 | 0.5235 | 36.40 |
| D | H1-iii totals_h1 stale rule, OFFSHORE reference 2023-24/2024-25, m 0.5 | 71 | 39 | 31 | 1 | 2.96 | 3.61 | -14.22 | 21.15 | 0.3698 | 39.40 |
| D | H1-iii totals_h1 stale rule, OFFSHORE reference 2023-24/2024-25, m 1.0 | 14 | 10 | 4 | 0 | 5.40 | 32.83 | -5.92 | 69.53 | 0.0640 | 42.90 |
| D | H1-iii totals_h1 stale rule, OFFSHORE reference 2023-24/2024-25, m 1.5 | 5 | 5 | 0 | 0 | 5.00 | 82.64 | 81.17 | 84.32 | 0.0000 | 40.00 |

Kill rows at the headline m = 1.0: price range median -121, shortest -135, longest -108, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 47.9 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| H1-iii m 1.0 | all | 39 | 23 | 16 | 0 | 3.35 | 6.99 | -17.87 | 29.88 | 0.3192 |  |
| H1-iii m 1.0 | season 2026 | 16 | 6 | 10 | 0 | -6.41 | -32.54 | -67.59 | 1.82 | 0.9326 |  |
| H1-iii m 1.0 | season 2027 | 23 | 17 | 6 | 0 | 9.76 | 34.60 | 7.19 | 58.40 | 0.0162 |  |
| H1-iii m 1.0 | early half of each season | 19 | 7 | 12 | 0 | -7.82 | -33.36 | -69.41 | -0.13 | 0.9369 |  |
| H1-iii m 1.0 | late half of each season | 20 | 16 | 4 | 0 | 11.17 | 45.65 | 17.25 | 71.36 | 0.0025 |  |
| H1-iii m 1.0 | without its 10 best dates | 24 | 8 | 16 | 0 | -11.65 | -39.73 | -73.55 | -14.88 | 0.9881 |  |
| H1-iii m 1.0 | side = over | 15 | 12 | 3 | 0 | 8.16 | 43.80 | 10.38 | 70.53 | 0.0105 | 38.50 |
| H1-iii m 1.0 | side = under | 24 | 11 | 13 | 0 | -4.81 | -16.43 | -47.30 | 13.85 | 0.8048 | 61.50 |
| H1-iii m 1.0 | price band -150..-100 | 39 | 23 | 16 | 0 | 3.35 | 6.99 | -17.87 | 29.88 | 0.3192 | 100.00 |

### Q1-iii. The stale Q1 total: the full game moved T-60 -> T-10 (r3_d_periods.py)

Decidable quotes with both marks and a Pinnacle move: 506 on 275 games; Pinnacle full-game total moved on 69.0% of them (mean |move| 0.17); the book's q1 line moved on 2.4%; |gap| >= 0.5 on 2.4%.

| experiment | cell | bets | W | L | P | units | ret% | lo% | hi% | p_one | over share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| D | Q1-iii totals_q1 stale rule, decidable, m 0.25 | 16 | 8 | 8 | 0 | -1.71 | -8.51 | -41.98 | 23.22 | 0.6605 | 43.80 |
| D | Q1-iii totals_q1 stale rule, decidable, m 0.5 | 12 | 7 | 5 | 0 | 0.67 | 4.29 | -29.16 | 33.25 | 0.4137 | 33.30 |
| D | Q1-iii totals_q1 stale rule, decidable, m 0.75 | 10 | 5 | 5 | 0 | -1.33 | -10.18 | -44.21 | 24.13 | 0.6785 | 40.00 |
| D | Q1-iii totals_q1 stale rule, OFFSHORE reference 2023-24/2024-25, m 0.25 | 37 | 22 | 15 | 0 | 3.54 | 7.89 | -17.14 | 31.71 | 0.2984 | 37.80 |
| D | Q1-iii totals_q1 stale rule, OFFSHORE reference 2023-24/2024-25, m 0.5 | 29 | 17 | 12 | 0 | 2.02 | 5.69 | -20.29 | 31.92 | 0.3692 | 31.00 |
| D | Q1-iii totals_q1 stale rule, OFFSHORE reference 2023-24/2024-25, m 0.75 | 27 | 17 | 10 | 0 | 4.42 | 13.36 | -14.64 | 41.31 | 0.2221 | 33.30 |

Kill rows at the headline m = 0.5: price range median -128, shortest -155, longest -120, shorter than -300: 0.0%, shorter than -500: 0.0%, risked 15.6 units

| rule | subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | share% |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Q1-iii m 0.5 | all | 12 | 7 | 5 | 0 | 0.67 | 4.29 | -29.16 | 33.25 | 0.4137 |  |
| Q1-iii m 0.5 | season 2026 | 12 | 7 | 5 | 0 | 0.67 | 4.29 | -29.16 | 33.25 | 0.4137 |  |
| Q1-iii m 0.5 | early half of each season | 5 | 2 | 3 | 0 | -1.80 | -27.15 | -100.00 | 14.18 | 0.8161 |  |
| Q1-iii m 0.5 | late half of each season | 7 | 5 | 2 | 0 | 2.47 | 27.47 | -10.23 | 78.74 | 0.1570 |  |
| Q1-iii m 0.5 | without its 10 best dates | 0 | 0 | 0 | 0 | 0.00 |  |  |  |  |  |
| Q1-iii m 0.5 | side = over | 4 | 2 | 2 | 0 | -0.40 | -7.97 | -56.24 | 73.80 | 0.5737 | 33.30 |
| Q1-iii m 0.5 | side = under | 8 | 5 | 3 | 0 | 1.07 | 10.09 | -33.59 | 51.63 | 0.3552 | 66.70 |
| Q1-iii m 0.5 | price band -150..-100 | 11 | 6 | 5 | 0 | -0.33 | -2.35 | -36.32 | 28.93 | 0.5447 | 91.70 |
| Q1-iii m 0.5 | price band -300..-151 | 1 | 1 | 0 | 0 | 1.00 | 64.52 | 64.52 | 64.52 |  | 8.30 |

### P2. Round 1's frozen first-quarter total lead, read unchanged (r3_d_periods.py, running r1_method's own fit and decide)

Round 1: graded 2026-27 fit a = -7.826, b = 0.2978 on 1,023 games; pooled cut 0.02: 59 bets, +10.85 units, +14.96%; 2026-27 alone 4 bets, +1.80 units.

| graded season | fit a | fit b | fit games | games decided | bets | W | L | P | units | ret% | lo% | hi% | unders |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | 1.48 | 0.24 | 621 | 314 | 55 | 34 | 21 | 0 | 9.05 | 13.34 | -7.97 | 33.50 | 55 |
| 2027 | -7.83 | 0.30 | 1,023 | 107 | 4 | 3 | 1 | 0 | 1.80 | 38.63 | -8.77 | 88.50 | 2 |

Pooled (reproduction check) and the 2026-27 read:

| subset | bets | W | L | P | units | ret% | lo% | hi% | p_one | experiment | cell |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pooled 2025-26 + 2026-27 (reproduction) | 59 | 37 | 22 | 0 | 10.85 | 14.96 | -5.49 | 32.97 | 0.1090 |  |  |
| 2026-27 (no new games since round 1) | 4 | 3 | 1 | 0 | 1.80 | 38.63 | -8.77 | 88.50 | 0.1718 | D | P2 frozen Q1 total lead, 2026-27 read |

## Multiplicity (r3_report.py)

Cells counted (pre-registered grid and band cells at each experiment's main price): **109** (planned 107). Surviving Benjamini-Hochberg at a 10% false-discovery rate: **1**, of which 0 hold 25+ bets (a cell under 25 bets is below the repo's floor: its p is from a handful of dates).

Sensitivity (not pre-registered): BH over the 91 cells with 25+ bets only: **0** survive.

Counted cells by experiment: A 26, B 44, C 14, D 25

Every counted cell with a positive return, smallest p first:

| experiment | cell | bets | units | ret% | lo% | hi% | p_one | survives BH 10% | 25+ bets |
|---|---|---|---|---|---|---|---|---|---|
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.03 | 3 | 5.65 | 188.33 | 171.67 | 205.00 | 0.0000 | True | False |
| A | A1 home ML best decidable close, band +151..+250 | 176 | 49.09 | 27.89 | 10.73 | 44.32 | 0.0042 | False | True |
| A | A1 home ML DraftKings close, band +151..+250 | 172 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 | False | True |
| D | Q1-i totals_q1 share rule, decidable, m 1.0 | 63 | 17.71 | 22.23 | 4.08 | 39.66 | 0.0188 | False | True |
| A | A1 home ML DraftKings close, band -120..-101 | 137 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 | False | True |
| A | A1 home ML best decidable close, all bands | 984 | 64.80 | 5.24 | -0.27 | 11.08 | 0.0643 | False | True |
| A | A1 home ML DraftKings close, all bands | 972 | 59.64 | 4.89 | -0.68 | 10.39 | 0.0710 | False | True |
| D | H1-i totals_h1 share rule, decidable, m 1.5 | 41 | 9.03 | 17.78 | -7.39 | 41.03 | 0.1086 | False | True |
| A | A1 home ML best decidable close, band +251 or longer | 52 | 16.30 | 31.35 | -8.12 | 76.99 | 0.1160 | False | True |
| D | H1-i totals_h1 share rule, decidable, m 2.0 | 11 | 4.20 | 30.61 | -13.15 | 65.48 | 0.1198 | False | False |
| A | A1 home ML DraftKings close, band +251 or longer | 50 | 13.70 | 27.40 | -17.14 | 71.90 | 0.1565 | False | True |
| A | A2 home h2h_h1 best of fanduel/betrivers, home underdog | 99 | 11.81 | 12.56 | -7.39 | 34.02 | 0.1614 | False | True |
| A | A1 home ML best decidable close, band -120..-101 | 132 | 11.17 | 7.58 | -4.05 | 21.66 | 0.1661 | False | True |
| D | P2 frozen Q1 total lead, 2026-27 read | 4 | 1.80 | 38.63 | -8.77 | 88.50 | 0.1718 | False | False |
| D | H1-i totals_h1 share rule, decidable, m 1.0 | 118 | 11.05 | 7.77 | -7.72 | 21.94 | 0.1904 | False | True |
| C | C2 crew_score rule, DK close, c 2.0 | 59 | 6.40 | 9.88 | -12.90 | 30.77 | 0.2227 | False | True |
| B | B2 spread full model, DK close, cut 0.05 | 153 | 9.64 | 5.76 | -7.81 | 18.44 | 0.2323 | False | True |
| B | B2 spread full model, DK close, cut 0.03 | 321 | 13.16 | 3.75 | -4.82 | 12.66 | 0.2398 | False | True |
| B | B2 spread full minus venue, DK close, cut 0.02 | 415 | 14.38 | 3.16 | -4.99 | 11.32 | 0.2558 | False | True |
| B | B2 spread full minus double week, DK close, cut 0.02 | 410 | 13.76 | 3.06 | -4.90 | 10.62 | 0.2566 | False | True |
| A | A1 walk-forward band rule, DraftKings close | 433 | 18.10 | 3.68 | -5.73 | 12.66 | 0.2583 | False | True |
| D | H1-i totals_h1 share rule, decidable, m 0.5 | 243 | 10.22 | 3.53 | -5.65 | 12.17 | 0.2621 | False | True |
| B | B2 spread full minus home underdog, DK close, cut 0.02 | 307 | 11.34 | 3.38 | -6.21 | 13.26 | 0.2843 | False | True |
| B | B2 spread full model, DK close, cut 0.04 | 230 | 9.18 | 3.65 | -7.99 | 14.21 | 0.2917 | False | True |
| B | B1 ML home dummy only, DK close, cut 0.02 | 585 | 17.31 | 2.35 | -4.81 | 9.31 | 0.2974 | False | True |
| D | H1-iii totals_h1 stale rule, decidable, m 1.0 | 39 | 3.35 | 6.99 | -17.87 | 29.88 | 0.3192 | False | True |
| D | Q1-i totals_q1 share rule, decidable, m 0.75 | 106 | 5.84 | 4.44 | -10.75 | 20.41 | 0.3203 | False | True |
| A | A1 home ML DraftKings close, band -150..-121 | 195 | 6.90 | 2.60 | -7.29 | 11.37 | 0.3254 | False | True |
| B | B1 ML full model, best decidable close, cut 0.05 | 52 | 5.02 | 9.20 | -24.33 | 44.19 | 0.3275 | False | True |
| A | A2 home spreads_h1 best of fanduel/betrivers, home underdog | 118 | 5.09 | 3.82 | -10.78 | 17.96 | 0.3289 | False | True |
| B | B1 ML full model, DK close, cut 0.05 | 22 | 2.28 | 10.19 | -26.76 | 50.04 | 0.3349 | False | False |
| B | B1 ML full minus attendance, DK close, cut 0.02 | 209 | 7.86 | 3.42 | -9.62 | 17.31 | 0.3355 | False | True |
| C | C4 follow the DK move at the DK close, k 4 | 148 | 4.76 | 2.96 | -10.39 | 16.21 | 0.3526 | False | True |
| A | A2 home spreads_h1 betrivers | 106 | 3.23 | 2.55 | -10.54 | 14.06 | 0.3655 | False | True |
| B | B2 spread full minus rest, DK close, cut 0.02 | 395 | 7.06 | 1.63 | -6.74 | 9.72 | 0.3733 | False | True |
| C | C2 crew_score rule, DK close, c 1.0 | 466 | 6.63 | 1.31 | -5.52 | 8.09 | 0.3743 | False | True |
| C | C2 crew_score rule, DK close, c 1.5 | 215 | 3.93 | 1.69 | -8.66 | 11.86 | 0.3937 | False | True |
| B | B1 ML market alone (offset only), DK close, cut 0.03 | 9 | 1.15 | 9.80 | -49.04 | 71.42 | 0.3960 | False | False |
| D | Q1-iii totals_q1 stale rule, decidable, m 0.5 | 12 | 0.67 | 4.29 | -29.16 | 33.25 | 0.4137 | False | False |
| B | B2 spread full model, DK close, cut 0.02 | 428 | 4.44 | 0.95 | -7.07 | 8.60 | 0.4202 | False | True |
| B | B1 ML full minus double week, DK close, cut 0.02 | 145 | 2.53 | 1.60 | -14.54 | 17.46 | 0.4361 | False | True |
| B | B2 spread market alone (offset only), DK close, cut 0.03 | 24 | 0.51 | 1.87 | -29.47 | 32.71 | 0.4606 | False | False |
| B | B2 spread full model, DK close, cut 0.01 | 664 | 2.20 | 0.30 | -6.17 | 7.15 | 0.4695 | False | True |
| B | B2 spread full model, DK close, cut 0.00 | 1,099 | 2.17 | 0.18 | -4.70 | 5.03 | 0.4757 | False | True |
| A | A1 home ML best decidable close, band -150..-121 | 199 | 0.63 | 0.23 | -9.39 | 9.58 | 0.4840 | False | True |

The ten smallest p overall (with the BH threshold for each rank):

| experiment | cell | bets | units | ret% | lo% | hi% | p_one | survives BH 10% | 25+ bets | bh p_threshold |
|---|---|---|---|---|---|---|---|---|---|---|
| D | Q1-ii h2h_q1 shrink, decidable, cut 0.03 | 3 | 5.65 | 188.33 | 171.67 | 205.00 | 0.0000 | True | False | 0.0009 |
| A | A1 home ML best decidable close, band +151..+250 | 176 | 49.09 | 27.89 | 10.73 | 44.32 | 0.0042 | False | True | 0.0018 |
| A | A1 home ML DraftKings close, band +151..+250 | 172 | 44.20 | 25.70 | 7.33 | 43.53 | 0.0090 | False | True | 0.0028 |
| D | Q1-i totals_q1 share rule, decidable, m 1.0 | 63 | 17.71 | 22.23 | 4.08 | 39.66 | 0.0188 | False | True | 0.0037 |
| A | A1 home ML DraftKings close, band -120..-101 | 137 | 22.72 | 14.91 | 2.11 | 28.16 | 0.0273 | False | True | 0.0046 |
| A | A1 home ML best decidable close, all bands | 984 | 64.80 | 5.24 | -0.27 | 11.08 | 0.0643 | False | True | 0.0055 |
| A | A1 home ML DraftKings close, all bands | 972 | 59.64 | 4.89 | -0.68 | 10.39 | 0.0710 | False | True | 0.0064 |
| D | H1-i totals_h1 share rule, decidable, m 1.5 | 41 | 9.03 | 17.78 | -7.39 | 41.03 | 0.1086 | False | True | 0.0073 |
| A | A1 home ML best decidable close, band +251 or longer | 52 | 16.30 | 31.35 | -8.12 | 76.99 | 0.1160 | False | True | 0.0083 |
| D | H1-i totals_h1 share rule, decidable, m 2.0 | 11 | 4.20 | 30.61 | -13.15 | 65.48 | 0.1198 | False | False | 0.0092 |
