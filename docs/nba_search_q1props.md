# NBA search: first-quarter player props against a projection of first-quarter minutes (pre-registered 2026-11-03, before any bet in it was graded)

mike, 2026-10-30: *"whatever is missing, find it"*; 2026-11-03: *"Buy 1Q data"*. No first-quarter spread or
total has passed in three searches (`docs/nba_models_2026.md` sections 9 and 12, and `docs/nba_search_starters.md`).
First-quarter player props have never been graded, because their prices were never held. They were bought on
2026-11-03.

**Written before any bet was graded. Nothing below changes after a result is seen; a later change gets its own
dated line and reason.** Lab: `scripts/nba_s_q1props.py`. Pass/fail: `python -m scripts.nba_game2_verdict
--results DIR --house5` (`docs/nba_models_2026.md` section 9.1's bars), with the season bar read as section 7
below says. No data is bought for this search, no Odds API call is made, and nothing is written to the database.

**What was read before this was written.** The prices (lines, prices, books, timestamps), and which tables hold
what. No projection was computed on real games, and no result of any game was read.

## 1. What is tested, and what earlier searches did and did not cover

**The idea.** A first-quarter prop is a player's points, rebounds or assists in the first 12 minutes. Most of
what decides that number is how long he is on the floor in those 12 minutes, and that varies by player far more
than his full-game minutes suggest: starters play 68% to 72% of the first quarter against 62% to 64% of the game
(`docs/nba_search_starters.md` section 1, measured from the lineup segments). Some starters play the whole quarter,
others sit at the six-minute mark. If the books set first-quarter lines mostly as a share of the full-game line,
the players whose first-quarter minutes differ from the usual share are mispriced. **This search projects
first-quarter minutes from the lineup segments, times a per-minute rate, and bets where that projection disagrees
with the book's price.**

| Search | What it tested on first quarters | Players |
|---|---|---|
| First, fourth, fifth, eighth (`docs/nba_models_2026.md` 4.2, 8, 9, 12) | spreads and totals: league shares, ratings, team shares, cover records | none |
| Starters (`docs/nba_search_starters.md`) | spreads and totals: the starters' ratings tilt | the whole rotation's minutes, as a team rating |
| **This search** | **player points, rebounds and assists** | **each player's own first-quarter minutes** |

**No sharp reference exists here.** Pinnacle prices none of the three markets (the purchase's probe, and 0 Pinnacle
rows in what was bought). The shipped same-line rule (`models/nba_prop_market.py`) needs Pinnacle, so it cannot run,
and neither can any rule that measures a book against a sharper one. This search is a projection against the book's
own price, like the shipped full-game projection model (`models/nba_prop_projection.py`, record 5 of
`docs/nba_models_2026.md`).

## 2. Data

### 2.1 The prices (measured 2026-11-03 on the rows pulled for this search)

Pulled read-only from `player_prop_odds`, markets `player_points_q1`, `player_rebounds_q1` and `player_assists_q1`,
by game id in chunks of 60 (`python run_with_db.py scripts.nba_s_q1props --pull`, into the scratch folder).

| | 2024-25 | 2025-26 |
|---|---|---|
| Rows | 40,144 | 62,861 |
| Games with any row | 889 (first 2024-12-05) | 1,222 (first 2025-10-21) |
| Snapshot | one per game, `snapshot_type` 'open' | the same |

- **2023-24 has none,** and 2024-25 starts on 2024-12-05: the feed holds no earlier first-quarter prop. The purchase
  note's 1,213 games for 2024-25 is not what is stored; 889 is. Every row is a regular-season game in `nba_schedule`.
- **The books are not the ones the purchase note named.** Rows by book (games in brackets):

| Season | Market | Hard Rock | FanDuel | Caesars (`williamhill_us`) | BetMGM | Fanatics |
|---|---|---|---|---|---|---|
| 2024-25 | points | 8,849 (868) | 2,585 (452) | 3,952 (446) | – | – |
| 2024-25 | rebounds | 8,875 (868) | – | 3,380 (309) | – | – |
| 2024-25 | assists | 8,806 (868) | – | 3,697 (344) | – | – |
| 2025-26 | points | 16,150 (1,186) | 7,198 (1,172) | – | 2,508 (273) | 214 (23) |
| 2025-26 | rebounds | 16,129 (1,184) | – | – | 2,514 (273) | 150 (20) |
| 2025-26 | assists | 15,425 (1,175) | – | – | 2,508 (273) | 65 (20) |

  Caesars quotes from December 2024 to March 2025; BetMGM from March 2026. All five are deciding books
  (`config.BEST_LINE_BOOKMAKERS`).
- **46,743 rows are one-sided: an over price and no under.** All are Hard Rock's, 63% of its rows. Every other book's
  quote is two-sided. On 35,120 of the 77,155 (game, player, market) propositions the only quote is a one-sided Hard
  Rock over.
- **One line per book per proposition.** No book lists two lines for one player in one market, so there is no
  ladder to choose a main number from. No line is a whole number, so no bet can push.
- **The snapshot's lead before tip:** 54 minutes in 1,878 games, 64 in 207, 49 in 7, 59 in 2. 17 games sit outside
  45 to 75 minutes (84, 114, 144, 174, 24, 4, and two snapshots taken six minutes after tip) and are dropped.
- **Lines read:** points 0.5 to 13.5, rebounds 0.5 to 4.5, assists 0.5 to 4.5. Prices: over −375 to +1,400, under
  −754 to +195.

### 2.2 Everything else

- **Plays:** `nba_pbp`, every regular-season game of 2023-24 to 2025-26 (3,693 games, 1,753,559 plays). The pull
  reads each game's stored play count from `nba_pbp_games` and copies a game from an earlier local pull made by the
  same query (the postseason search's, 2026-10-31) only when its row count equals that stored count; any other game
  is pulled. All 3,693 matched, so none was pulled again. Without that seed, `--pull` pulls every game.
- **From the research cache** (a cache of Supabase, read-only): `nba_player_game_log` (box scores, 2018-19 on),
  `nba_stints` (lineup segments, 2018-19 on), `nba_injury_report` (2018-19 on, every game from 2021-22),
  `nba_period_scores`, `nba_player_id_map`, `nba_games`, `nba_schedule`, `nba_player_game_adv`,
  `nba_game_inactives`.
- `nba_pbp_box` and `nba_pbp_games` for 2023-24 to 2025-26, pulled fresh.

## 3. Settlement

First-quarter points, rebounds and assists per player exist in no table, so they are built.

### 3.1 The derivation

The postseason search's play rules (`docs/nba_search_postseason.md` 3.1, `scripts/nba_s_postseason.derive_events`,
imported unchanged), on the plays of period 1:

| Stat | Rule |
|---|---|
| Points | the `points` of every scoring play, to `athlete_id_1` |
| Assists | `athlete_id_2` of a made field goal |
| Rebounds | play types 155 and 156, to `athlete_id_1`; team rebounds name nobody |

ESPN's player ids become NBA ids through `nba_player_id_map`. A player on the floor in the first quarter with no
event there has a line of zeros.

**First-quarter court time** comes from the lineup segments (`nba_stints`, period 1, five a side): a player's
seconds are the summed length of every segment he is in. Segments not five a side are dropped.

### 3.2 The checks, and the rule that leaves a game out

1. **The full game against the box score.** The same rules on every period give each player's full-game points,
   rebounds and assists. They are compared with `nba_player_game_log`, every player of the game; a player only one
   side holds counts as zeros on the other, and a player whose ESPN id has no NBA id never matches. **A game is left
   out of a market when any player's full-game number in that market's stat differs.** It stays in the other two
   markets if they agree. Each stat is checked on its own because the play feed's known faults are stat-specific: a
   teammate credited with a rebound, a stale copy of a scoring play (`docs/nba_search_postseason.md` 3.2 found 30
   games differing on points, 127 on assists and 338 on rebounds over these three seasons). The target is zero
   differences on what is kept, and the rule keeps only games that reach it.
2. **The first quarter's points against the period scores.** Each team's first-quarter points summed from the
   derived lines must equal `nba_period_scores` period 1. A game that differs, or has no period score, is left out of
   the points market. **This is the only direct check of a first-quarter number.** Rebounds and assists have no
   period source, so for them a game rests on its full-game check alone: a right game total with an event filed in
   the wrong quarter would pass. That limit is stated, not fixed.
3. **Court time.** A team-game whose first-quarter segments do not sum to 60 player-minutes within 1 is left out of
   every market: its voids cannot be told.
4. **Events and court time agree.** A game in which a player has a first-quarter event and no first-quarter court
   time is left out of every market.

Counts of each, by season and stat, are printed by `--smoke` and written into section 12 before any grade. The
three settlements rest on: points, the plays checked against the box score and the period scores; rebounds and
assists, the plays checked against the box score.

### 3.3 Voids

**Caesars' published rule** (Caesars Sportsbook house rules, Iowa, version 25, effective 2026-05-01, basketball,
"Quarter Player Points (Over/Under)"): *"Markets will be void if the player does not record any time on-court during
the listed quarter."* Hard Rock's, FanDuel's, BetMGM's and Fanatics' period-prop rules were not found published
(Hard Rock's New Jersey rules page loads its sport sections by script, so the fetch returned none of them;
DraftKings' basketball rules page refused the fetch with HTTP 403; FanDuel's, BetMGM's and Fanatics' were not
found by search).
**Assumed for every book and all three markets: a player with no first-quarter court time is void.** A void bet has
no row and leaves the record.

**Why it matters, and what is reported for it.** Under the other reading, a player who played the game but not the
first quarter would settle at 0, a sure under. `--smoke` counts the propositions where the player played the game
and had no first-quarter court time. Every under result is to be read against that count.

## 4. Impossible numbers, stated before anything is read

A row is refused and counted, never repaired, when:

1. Its name is not one player on the game's two teams, or is shared by two players (the first search's matcher,
   `scripts/nba_prop_market_lab.build_quotes`, imported unchanged; it reads the game's roster for identification
   only).
2. Its snapshot is outside 45 to 75 minutes before tip.
3. Either price is under 100 or over 10,000 in size.
4. Its line is under 0.5 or above points 35.5, rebounds 15.5, assists 12.5: about half of the postseason search's
   full-game ceilings (70.5, 30.5, 25.5). A quarter is a quarter of the game, so half the full-game ceiling is past
   any quarter. The ceilings are set by hand, not read from the archive.
5. Its quote is two-sided and its implied sum is outside 1.00 to 1.15.

**A one-sided quote is not a bad row, and it is not in the judged cells.** Section 6.2 of the record prices every
cell at a coherent two-way quote; a one-sided price cannot be checked for coherence, and the blind bet's fair price
needs both sides. The one-sided Hard Rock overs are graded as a control (section 10), never judged.

**A wide gap between the projection and the line is not an impossible number.** `--smoke` prints the highest-EV
offers; they stay in.

## 5. The projection

Each proposition is priced at its decision time T, the snapshot. **Nothing from the game itself or later is read:**
no box score, segment or play of that game or a later one, and an injury report counts as known 30 minutes after its
printed time (`docs/nba_models_2026.md` 6.1; `docs/nba_search_propoffline.md`'s dated line of 2026-10-31).

**What the number is.** A bet has action only if the player takes the floor in the first quarter (3.3). So the
number that prices it is his expected first-quarter stat **given that he plays in the first quarter**:

    mean = expected first-quarter minutes when he plays it × per-minute rate × the first-quarter factor

The brief asked for minutes times his chance of playing from the injury report. **For the player himself that would
be wrong for a void-if-he-sits bet:** a Questionable player who plays is not a fraction of a player, and multiplying
by 0.6 would shade every Questionable player's number toward the under. His own chance of playing is used where it is
right: in his teammates' numbers, through the minutes he frees if he sits (5.2).

### 5.1 First-quarter minutes when he plays it

His first-quarter minutes in his earlier games in which he had first-quarter court time, weighted by recency with a
half-life of 3 such games (the half-life the rating engine fits for minutes, `min_hl`, which the starters search
used). Every earlier stored game counts, reaching into earlier seasons and other teams. A team-game whose segments
fail check 3 is not read. **A player with fewer than 3 such games has no number.**

### 5.2 Teammates' absences

- **His team tonight:** the team of his latest box-score game before today. If that is neither team of this game,
  he has no number.
- **The team's pool:** every player whose latest team before today is this team and who had first-quarter court time
  in at least one of the team's last 10 games before today (segment-checked games only).
- For each pool player: **s** = the share of those games in which he had first-quarter court time; **m** = his 5.1
  minutes; **a** = his chance of playing from the injury report at T: 0 if Out; the rate at which players of his
  status played, fitted on the reports of 2021-22 through the season before the priced one (each player listed on
  the report as known at tip minus 60 minutes, against whether he played), if Doubtful, Questionable, Probable or
  Available; 1 if not listed.
  A report row with no NBA id takes the one roster player with its name (`models.nba_props._attach_report_ids`).
- **The team's expected first-quarter minutes** E = Σ a × s × m over the pool. **r = 60 / E**, and his expected
  minutes are min(12, his m × r). A team whose E is under 30 is a hole in the data, and its players have no number.
- **What this does.** A starter who has played every recent game and is Out tonight takes about 9 minutes out of E,
  and his teammates' minutes rise about 18%. A player out for weeks has s near 0 and changes nothing: his absence is
  already in everyone's recent minutes. The reallocation is proportional, so the player who actually takes the
  starter's place gets too few; no lineup is known at T, so nothing better is available (the starters search's stated
  limit).
- **A player listed Out at T has no number.**

### 5.3 The per-minute rate

His **full-game** per-minute rate from the box score: four times the minutes of a first-quarter rate, so far less
noise. Season to date, shrunk toward his two previous seasons, which are shrunk toward the league:

    prior = (his points over the two previous seasons + Kp × the league's rate last season) / (his minutes there + Kp)
    rate  = (his points this season before today + Kc × prior) / (his minutes this season before today + Kc)

(points stand for each stat). Kc and Kp are chosen once per stat on 2023-24, a season no bet is graded on, from
25, 50, 100, 200, 400, 800 and 1,600 minutes, by the Poisson deviance of the full-game stat given the minutes played.

### 5.4 The first-quarter factor and the count distribution

- **The factor** turns a full-game rate times first-quarter minutes into the first-quarter mean: Σ actual first-quarter
  stat / Σ (5.1-5.2 minutes × 5.3 rate), over every settled player-game with first-quarter court time and a number, in
  the seasons from 2023-24 to the one before the priced season. **2024-25 is priced with 2023-24's factor; 2025-26
  with 2023-24's and 2024-25's together.** It absorbs any level bias in the minutes and the rate, and how a first-quarter
  minute differs from an average one. One number per stat and priced season.
- **The distribution:** negative binomial, variance = mean + alpha × mean², alpha fitted by `models.nba_props.fit_alpha`
  (maximum likelihood; 0, Poisson, unless the negative binomial fits better) on the same earlier seasons' settled
  player-games, each season's means carrying its own factor. 2023-24's own means carry a factor fitted on 2023-24
  itself; that season is history and is never graded.
- **The chance of over** at each book's own line: `models.nba_props.p_over`. EV = the chance of the side × the
  decimal price − 1.

## 6. The cells (18)

| Family | Markets | Sides | Cut on EV | Cells |
|---|---|---|---|---|
| Q1P | first-quarter points, rebounds, assists, each its own cell | over, under | ≥ 0.02 / 0.04 / 0.06 | 3 × 2 × 3 = 18 |

- **Price:** the best-EV offer among the deciding books that quote the proposition, at each book's own line, a
  coherent two-way quote, −200 floor (`H.choose`). One bet per (game, player, market). No game or night cap.
- **Units:** one unit to win, risk capped at 3 (`H.risk_win`). No line is whole, so no push.
- **Through the harness:** a proposition is one synthetic game to `H.run_cells` (the postseason and propoffline
  searches' device): its own id, its first-quarter stat as the home score and 0 as the away score, its offers filed
  under the harness's total market, so `H.choose` takes one bet per proposition and `H.settle` gives over when the
  stat is above the line. A void has no row and drops out at the grade's join.
- **Bands (bar 5)** along EV within one market and side: [0.00, 0.02), [0.02, 0.04), [0.04, 0.06), 0.06 and up
  (`G5.band_bounds` with lowest 0.00). The band just below the cut and every band from the cut up must be positive where
  they hold 30 or more bets.
- **The cuts** are the brief's, fixed before any EV was computed.

## 7. Seasons

- **Graded and pooled: 2024-25 and 2025-26.** 2023-24 holds no first-quarter price; it is history for the fits only.
- **2024-25 is the choosing season the placebo reads** (`choose_seasons = (2025,)`, as the propoffline search's anchored
  family with the same two seasons). Nothing is chosen on it: the cuts are fixed.
- **"Seasons mostly positive" means both.** With two graded seasons, the verdict's bar 3 as coded allows one to lose.
  This search reads it strictly: **both seasons, each with 30 or more bets, positive.** `--verdict DIR` prints the
  verdict's own result and the result under this reading; the stricter one is this search's.

## 8. The bars

Section 9.1's house standard, unchanged but for bar 3's reading above: 200 or more pooled bets; the pooled whole-day
bootstrap 95% interval above zero (4,000 resamples, seed 7); seasons positive; beats the blind bet on its dominant
real side, pooled; the bands; the choosing season's return above the 95th percentile of 200 placebo runs, a run with
no bet counting as 0.

**The blind bet (bar 4):** the cell's side on every proposition in its own population, no model and no cut, at the
best deciding offer by the offer's own book's proportional no-vig price. No sharp or consensus price exists, so the
book's own is the only market price there is.

**A thin cell is still reported in full.** A cell under 200 pooled bets fails bar 1; its answer is "too few games to
tell", not "it loses" (the record's 9.9 reading).

Closing-line value and "still offered at the next fetch" cannot be measured: one snapshot a game.

## 9. The placebo: 200 runs, seeds 1-200

**Each proposition's disagreement with the book moves to another proposition on the same date in the same market.**
The disagreement is the projected mean over the proposition's main line (the commonest line among its coherent
deciding quotes, a tie to the lower). In a run, each proposition takes another's ratio, times its own main line, and
all its offers are re-priced through its own market's alpha. Every proposition keeps its own lines, books and prices.
A (date, market) with fewer than 5 propositions joins the other thin propositions of its season and market. With the
identity permutation the run returns exactly the real bets (a test asserts it).

**Is it a null on the real data?** `--smoke` prints, by cell, the share of a placebo run's bets that are not real bets
(same proposition, side and book), averaged over three runs, and names any cell under 0.5 in words. A cell where that
share is low cannot pass this bar honestly, and the print says so.

A model with a level bias passes the bias to every donor too, so a cell earning only from a lean to one side does not
beat its shuffles. Only the per-player part of the projection can.

## 10. Controls, graded and reported, never judged

| Control | What |
|---|---|
| `control_HR` | the 18 cells at Hard Rock alone |
| `control_FD` | the points cells at FanDuel alone (FanDuel quotes no rebounds or assists) |
| `control_blind` | every proposition in the population, each side, no model, at the best offer by its own book's no-vig price |
| `control_one_sided` | the over cells on the one-sided Hard Rock quotes, priced by the same projection |

**Expected passes by chance:** 18 × 0.025 ≈ 0.45 cells clear bar 2 alone, before correlation. The cuts are nested and
the three markets share players, so the cells are far from independent.

## 11. Reported beside every cell, never a bar

- DraftKings alone (the harness's columns): DraftKings quotes none of these markets, so they read empty.
- Each book alone, 2024-25 and 2025-26 apart, and the 54-minute against the 64-minute snapshot.
- Bets void and propositions left out by each settlement check.
- The propositions where the player played the game and not the first quarter (3.3).
- **Overlap with the live full-game prop models:** the share of the cell's bets on a (game, player) where
  `nba_prop_market` (its five markets, its graded bets of record 4.3) or `nba_prop_projection` (its six cells at their
  shipped floors, from its graded card) bet any full-game prop; the share where they bet the same stat; and the same
  stat on the same side. Only the bet keys of those files are read.
- **The prices each cell lays:** minimum, 5th percentile, median, 95th percentile, maximum.

## 12. What a pass means, and running it

A pass is built live (CLAUDE.md section 2) with its own EV floor and the prices it lays stated before it ships. The
live feed captures no first-quarter prop today (no code on master reads `player_points_q1`), so a pass needs that
capture first.

    python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_q1props --pull [--seed FILE]
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_q1props --smoke
    NBA_RESEARCH_CACHE=<cache> NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<folder> NBA_GAME2_BETS=<folder>/bets \
        PYTHONPATH=. python -m scripts.nba_s_q1props --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results <folder> --house5
    PYTHONPATH=. python -m scripts.nba_s_q1props --verdict <folder>

`--smoke` runs the synthetic checks, then on the real data prints only counts, extremes, the highest-EV offers, the
settlement checks, the placebo's differing share and a timed placebo run graded on results set to zero. It never
grades a real bet. `--full` refuses without its three variables, prints progress, and writes one `cells_*.parquet` per
group, the bets and the beside tables.

Counts before grading follow in a dated section once the lab's own run has printed them.

## 13. Counts before grading, under the rules as registered (2026-11-03)

Counted by `python -m scripts.nba_s_q1props --smoke` on the lab as first committed (`f00501cf`), before any cell was
graded. Lines, prices, timestamps and settlement checks only; the fits read 2023-24's results, and 2024-25's for
2025-26's factor and alpha. No win, loss or unit of any bet this search would place was computed. **Section 14 changes
the points distribution after these counts; the points rows below are the registered rule's.**

**Settlement (section 3), 2023-24 / 2024-25 / 2025-26: 1,230 games each, every one with plays.**

| Check | Points | Rebounds | Assists |
|---|---|---|---|
| Full game differs from the box score: games (rows) | 30 (61) | 338 (585) | 127 (233) |
| First-quarter points differ from the period score: games | 3 | – | – |
| Segments miss 60 player-minutes: games | 1 | 1 | 1 |
| A first-quarter event with no court time: games | 0 | 0 | 0 |
| **Games kept, 2023-24 / 2024-25 / 2025-26** | **1,218 / 1,223 / 1,218** | **1,116 / 1,124 / 1,111** | **1,194 / 1,185 / 1,183** |

- The full-game differences equal the postseason search's to the row (its 3.2: 61, 585, 233 rows; 30, 338, 127 games).
- 0 ESPN ids with an event lack an NBA id. 12 of 62,006 first-quarter segments (2018-19 on) are not five a side, and 14
  of 19,044 team-games miss 60 player-minutes; in these three seasons that leaves out 1 game, of 2023-24.

**The row ledger (section 4).** 103,005 rows pulled. The first search's table drops 117: two games whose only snapshot
was taken after tip (`NBA_2025-01-09_POR_DAL`, `NBA_2026-03-17_SAS_SAC`). Of the 102,888 left:

| Rule | Rows |
|---|---:|
| Name not one player on the two teams (2 names unmatched; no namesake, no duplicate) | 6 |
| Snapshot outside 45-75 minutes | 771 |
| Price under 100 or over 10,000 in size | 0 |
| Line outside 0.5 to the ceiling | 0 |
| Two-sided and incoherent | 0 |
| One-sided (to the control) | 46,389 |
| In a game left out of the market by settlement | 4,280 |
| Void: no first-quarter court time | 1,840 |
| **Coherent two-sided rows the cells read** | **52,965** |
| One-sided rows the control reads | 43,026 |

**The void rule's weight (3.3).** In a kept game, after the row rules, 512 of 73,012 propositions are on a player who
played the game and had no first-quarter court time: 70 in 2024-25, 442 in 2025-26. Under the other reading of a book's
rule each would settle under.

**Which books the judged cells read.** Coherent rows by season:

| Season | Market | Hard Rock | FanDuel | Caesars | BetMGM | Fanatics |
|---|---|---:|---:|---:|---:|---:|
| 2024-25 | points | 8,612 | 2,522 | 3,815 | – | – |
| 2024-25 | rebounds | 7,913 | – | 2,936 | – | – |
| 2024-25 | assists | 8,381 | – | 3,431 | – | – |
| 2025-26 | points | 447 | 6,993 | – | 2,418 | 198 |
| 2025-26 | rebounds | 307 | – | – | 2,326 | 106 |
| 2025-26 | assists | 129 | – | – | 2,370 | 61 |

In 2025-26 Hard Rock's quotes are almost all one-sided, so that season's judged rebounds and assists population is
about 2,400 propositions each, nearly all BetMGM's from March and April 2026 (two-sided propositions: points 8,454,
rebounds 2,483, assists 2,437). **The strict season bar (section 7) will bite there:** a rebounds or assists cell needs
30 bets and a positive return inside that window.

**Propositions** (settled, not void; in brackets, with a projection): 2024-25 points 9,151 (9,039), rebounds 8,285
(8,189), assists 8,782 (8,670); 2025-26 points 15,974 (15,825), rebounds 14,360 (14,244), assists 14,952 (14,824). No
number: the team pool under 30 minutes 488, the latest team neither side 142, fewer than 3 earlier first-quarter games 83.

**The fits.**

- Kc, Kp (2023-24): points 100, 50; rebounds 200, 50; assists 100, 200 minutes.
- The chance a listed player plays (reports of 2021-22 to the season before): Doubtful 0.02, Questionable 0.49 to 0.51,
  Probable 0.92, **Available 0.72 to 0.76**. An unlisted player counts 1, as registered. "Available" is a listed status,
  and players listed with it played that often.
- The first-quarter factor: points 0.864 / 0.862, rebounds 0.894 / 0.885, assists 0.953 / 0.935 (2024-25 / 2025-26).
- alpha: points 0.593 / 0.612, rebounds 0.062 / 0.061, assists 0.024 / 0.022.
- Expected first-quarter minutes when he plays it, percentiles 1 / 25 / 50 / 75 / 99: 3.0, 6.1, 8.0, 9.7, 12.0. The
  reallocation r: 1st percentile 0.98, median 1.14, 99th 1.75. The mean team pool expects 52 of the 60 minutes: about
  8 minutes of each night's recent rotation is out or doubtful.

**Bets each cell would place, under the rules as registered** (2024-25 + 2025-26 = pooled; no result read):

| Market | Side | EV ≥ 0.02 | EV ≥ 0.04 | EV ≥ 0.06 |
|---|---|---|---|---|
| points | over | 634 + 273 = 907 | 553 + 220 = 773 | 499 + 187 = 686 |
| points | under | 6,212 + 6,075 = 12,287 | 5,731 + 5,600 = 11,331 | 5,242 + 5,123 = 10,365 |
| rebounds | over | 1,547 + 490 = 2,037 | 1,278 + 415 = 1,693 | 1,019 + 345 = 1,364 |
| rebounds | under | 2,253 + 709 = 2,962 | 1,864 + 592 = 2,456 | 1,541 + 490 = 2,031 |
| assists | over | 2,365 + 607 = 2,972 | 2,010 + 524 = 2,534 | 1,714 + 445 = 2,159 |
| assists | under | 1,749 + 551 = 2,300 | 1,455 + 459 = 1,914 | 1,212 + 379 = 1,591 |

The points under bets 12,287 of the 17,420 points propositions at the lowest cut. The points distribution decides that,
not the projection (section 14).

**The placebo on the real data.** The identity permutation returned the real bets in every group; no proposition is
alone in its group (median group: points 59, rebounds 69, assists 74). Share of a run's bets that are not real bets,
three runs: points over 0.91 to 0.93; **points under 0.25 to 0.34, named LOW by the lab**; rebounds 0.71 to 0.85;
assists 0.66 to 0.80.

**Overlap with the live full-game prop models** (share of the lowest cut's bets). On a player and game where either
model bet any full-game prop: 0.81 to 0.94 in every cell. The same stat on the same side: **rebounds under 0.69 to
0.73** (the projection card bets full-game rebounds under), points under 0.16, assists under 0.16 to 0.18, every over
0.00. The live files hold 16,062 `nba_prop_market` bets and 54,571 projection-card bets in these two seasons (the card's
is the postseason search's figure, to the bet).

**Prices each cell would lay:** from −200 up to +184 on points, +260 on rebounds, +400 on assists. Assists overs have a
median of +135 to +145; every other cell's median is −115 to +105.

**Time and memory.** One placebo run across a group's three cuts took 0.22 to 0.50 seconds. The projected `--full` is
6.8 minutes of cells plus 1.3 minutes of loading; peak memory 2.2 GB, plus at most 0.04 GB for one market's 200 runs.
The smoke run took 2.6 minutes.

## 14. A change before any grade: the points distribution (2026-11-03)

No cell had been graded when this changed. No cell, cut, side, band, bar, season, book or minutes rule changes.

**What was measured, on 2023-24 alone** (a season no bet is graded on, whose first-quarter points the factor and alpha
were already fitted on). Over 21,251 settled player-games, the share above each line, against the registered negative
binomial (alpha 0.593) and a Poisson at the same means:

| Line | 0.5 | 1.5 | 2.5 | 3.5 | 4.5 | 5.5 | 6.5 |
|---|---|---|---|---|---|---|---|
| Actual share over | 0.693 | 0.678 | 0.495 | 0.382 | 0.289 | 0.211 | 0.147 |
| Negative binomial | 0.787 | 0.591 | 0.439 | 0.327 | 0.245 | 0.186 | 0.141 |
| Poisson | 0.899 | 0.721 | 0.535 | 0.376 | 0.256 | 0.170 | 0.109 |

Points come in twos and threes: 30.7% of these player-games scored 0 and 1.5% scored exactly 1. A count that steps by
one puts too much on 1 and too little on 0. At 2.5, 3.5 and 4.5, where the books hang most points lines, the negative
binomial is 4 to 6 points too low on the over, and it is low in every band of the mean as well. That alone makes most
points propositions read as unders, which is what section 13's counts show. Rebounds and assists are within 0.01 of
actual at every line, so they keep the negative binomial.

**The change, for points only.** The chance of over at line L is a logistic in the log of the projected mean, one fit
per line: P(over L) = 1 / (1 + exp(−(a_L + b_L × log mean))), for L = 0.5, 1.5 … 15.5. It is fitted on the same settled
player-games the factor and alpha read (2023-24 for 2024-25; 2023-24 and 2024-25 for 2025-26), each with its own
season's mean (`models.nba_props.fit_platt` on the log of the mean). For one mean, the chance is made non-increasing
across lines by carrying the smaller value forward. A line outside 0.5 to 15.5 falls back to the negative binomial and
is counted. The placebo re-prices through the same map.

**Its check, also on 2023-24 alone:** fitted on the season's first half of dates and read on its second half, at lines
1.5 to 6.5. `--smoke` prints it, and section 15 records it before any grade.

**Not re-checked:** the minutes, the rate and the factor are unchanged. Section 13's counts stand for rebounds and
assists; section 15 repeats every count under the change.

## 15. Counts before grading, under section 14 (2026-11-03)

Counted by `python -m scripts.nba_s_q1props --smoke` on the lab at `f3181352`, before any cell was graded, under the
same terms as section 13. Settlement, the row ledger, the books, the propositions, the minutes, the rate, the factor and
alpha are identical to section 13, and so is every rebounds and assists count below.

**The points line map's check, on 2023-24 alone** (fitted on the season's first half of dates, read on the second half,
10,704 player-games):

| Line | 1.5 | 2.5 | 3.5 | 4.5 | 5.5 | 6.5 |
|---|---|---|---|---|---|---|
| Actual share over | 0.680 | 0.498 | 0.384 | 0.287 | 0.208 | 0.146 |
| Line map | 0.667 | 0.486 | 0.375 | 0.286 | 0.211 | 0.145 |
| Negative binomial (fitted on the same first half) | 0.587 | 0.436 | 0.324 | 0.243 | 0.184 | 0.140 |

The map is within 0.013 of actual at every line; the negative binomial is 6 to 9 points low at 1.5 to 3.5. Both priced
seasons' maps hold all 16 lines (0.5 to 15.5), so no offer falls back to the negative binomial (0 coherent, 0 one-sided).

**Bets each cell would place** (2024-25 + 2025-26 = pooled; no result read). Only the points rows moved:

| Market | Side | EV ≥ 0.02 | EV ≥ 0.04 | EV ≥ 0.06 |
|---|---|---|---|---|
| points | over | 2,136 + 1,679 = 3,815 | 1,770 + 1,361 = 3,131 | 1,435 + 1,089 = 2,524 |
| points | under | 3,289 + 3,305 = 6,594 | 2,833 + 2,878 = 5,711 | 2,428 + 2,489 = 4,917 |
| rebounds | over | 1,547 + 490 = 2,037 | 1,278 + 415 = 1,693 | 1,019 + 345 = 1,364 |
| rebounds | under | 2,253 + 709 = 2,962 | 1,864 + 592 = 2,456 | 1,541 + 490 = 2,031 |
| assists | over | 2,365 + 607 = 2,972 | 2,010 + 524 = 2,534 | 1,714 + 445 = 2,159 |
| assists | under | 1,749 + 551 = 2,300 | 1,455 + 459 = 1,914 | 1,212 + 379 = 1,591 |

Every cell has 200 or more pooled bets and 30 or more in each season, so none is "too few games to tell" by count.
Controls at the lowest cut: Hard Rock alone, points 1,968 over and 3,003 under; FanDuel alone, points 1,571 over and
3,945 under; the one-sided Hard Rock overs, points 3,900, rebounds 2,838, assists 3,890.

**The placebo on the real data.** The identity permutation returned the real bets in every group; no proposition is
alone. Share of a run's bets that are not real bets, three runs: points over 0.74 to 0.81, **points under 0.57 to 0.66
(no longer low)**, rebounds 0.71 to 0.85, assists 0.66 to 0.80. No cell is under 0.5.

**Bets at the lowest cut by the reallocation r** (beside each graded cell, never a bar): points over 770 / 1,814 / 1,231
at r under 1.1 / 1.1 to 1.3 / 1.3 and up; points under 3,445 / 2,479 / 670; rebounds over 276 / 960 / 801, under
1,712 / 1,040 / 210; assists over 738 / 1,440 / 794, under 1,102 / 897 / 301. The overs sit where teammates are out,
which is where the proportional reallocation is weakest (5.2's stated limit).

**Overlap with the live full-game prop models** (lowest cut): on a player and game either model bet, 0.81 to 0.95 in
every cell. Same stat, same side: rebounds under 0.69 to 0.73, points under 0.15 to 0.16, assists under 0.16 to 0.18,
every over 0.00.

**Prices each cell would lay:** points over −200 to +184 (median −105), points under −199 to +165 (median −112 to
−110); the rebounds and assists prices are section 13's.

**Each rule watched failing.** `tests/test_nba_s_q1props.py` holds 24 tests. Each of 32 rules was broken once in the
lab, its test run, and the lab restored (scratch `explore/mutate.py`): period 1 only; an unmapped id never matching;
the per-stat exclusion; the period-score check; the court-time tolerance; the price limit; the line ceiling; coherence;
the window; the void; a left-out game dropping; minutes read strictly before the date; the 10-game pool; teammates'
status moving the team's minutes; a player's own status never scaling his own minutes; the 12-minute cap; the prior
shrinking to the league; K by least deviance; the 30-minute report lag; each offer at its own book's line; the placebo
staying in its group; the placebo's identity; thin dates joining; settlement on the stat; the planted edge showing;
`--full` refusing; the strict season bar; the line map's monotonicity; its own lines only; points priced through it;
and both walk-forward fits never reading their own season. **31 failed as they should. One passed with its rule broken:**
the own-line test read each offer's line back from the offer, so a break that moved every line moved the expectation
too. The test now asserts each book's quoted line, and fails with that break (`9460b9d6`).

**Time and memory.** One placebo run across a group's three cuts took 0.21 to 0.27 seconds. The projected `--full` is
5.3 minutes of cells plus 1.9 minutes of loading; peak memory 2.1 GB, plus at most 0.04 GB for one market's 200 runs.
The smoke run took 3.0 minutes.

**The graded run, for the owner:**

    NBA_RESEARCH_CACHE=C:/Users/micha/documents/bm-nba-q1trend/data/local/nba NBA_GAME2_GO=1 \
        NBA_GAME2_RESULTS=C:/Users/micha/AppData/Local/Temp/nba_s/q1props/results \
        NBA_GAME2_BETS=C:/Users/micha/AppData/Local/Temp/nba_s/q1props/results/bets \
        PYTHONPATH=. PYTHONIOENCODING=utf-8 python -W ignore -m scripts.nba_s_q1props --full
    PYTHONPATH=. python -m scripts.nba_game2_verdict --results C:/Users/micha/AppData/Local/Temp/nba_s/q1props/results --house5
    PYTHONPATH=. python -m scripts.nba_s_q1props --verdict C:/Users/micha/AppData/Local/Temp/nba_s/q1props/results

## 16. Changes after an independent review, before any cell was graded (2026-11-03)

An independent review of the lab and sections 1 to 15 came back on 2026-11-03 (its scripts:
`%TEMP%/nba_s/q1props_review/`). **No cell had been graded when these changed, and none has been since.** No cell, cut,
side, band, bar, season, book or price rule changes. Three changes move which bets the cells would place; two make the
lab refuse or report more; four lines document choices sections 3 to 15 left unsaid.

### 16.1 A player's own status no longer moves his own minutes

**What was wrong.** Section 5 prices a bet given that the player plays. But the lab's team total E counted the priced
player's own term at his status rate: a Questionable player entered his own team's E at about 0.5 of his minutes, so his
own r rose and his own minutes rose with it.

**The change.** For the priced player only, his own status counts 1: his E is E − a × s × m + s × m, from his own pool
row. His teammates' rows keep the plain E, so a Questionable teammate still frees minutes for them.

### 16.2 The chance a listed player plays is fitted on pool players only

**What was wrong.** The rates were fitted on every player listed on the report and applied only to pool players, who
have recent first-quarter court time. A pool player listed Available plays far more often than a listed player in
general: the review measured 0.906 on 2023-24's pools against the fitted 0.72 to 0.76.

**The change.** For each priced season S, every team-game of 2021-22 through S − 1 gets its pool at tip minus 60
minutes, by the same rule as a priced game (section 5.2, with 16.3's roster). Each pool player listed on the report as
known then counts once: did he play? The share by status is the rate. Out is still 0.

| Status | Fitted on every listed player (sections 13 and 15) | Fitted on pool players (now) |
|---|---|---|
| Doubtful | 0.02 | 0.02 |
| Questionable | 0.49 to 0.51 | 0.52 to 0.54 |
| Probable | 0.92 | 0.93 to 0.94 |
| Available | 0.72 to 0.76 | 0.84 to 0.88 |

(2023-24 / 2024-25 / 2025-26 rows of the fit: 2,698 / 4,053 / 5,519 Questionable; 946 / 1,645 / 2,420 Available.)

### 16.3 A player who has left the team leaves its pool once anything known says so

**What was wrong.** "His latest team" read only box-score lines. A player traded away stayed in his old team's pool
until he played for his new one. The review counted 1,231 of 25,190 priced player-games whose team total held more than
3 minutes of such players, mostly in October 2025 and around the February trade deadlines.

**The change: an as-of roster built from the cache.** A player's team as of the decision is the team of the latest of:

- his box-score lines and his **inactive listings** (`nba_game_inactives`) in games dated before today;
- **a report listing** (any of the report's five statuses) whose printed time plus 30 minutes is at or before the
  decision. It wins when its game is on or after the latest box or inactive date.

Every piece is known before the decision: earlier games' lines and inactive lists, and reports already printed. The rule
applies to the pool (section 5.2) and to the priced player's own team ("his team tonight" in 5.2 now reads it).

**What it removed, by the review's own measure.** The measure reads later box lines to say who left; it is a diagnostic
only, never an input. Priced player-games whose team total holds more than 3 minutes of players who had left:

| | Box lines only (sections 13 and 15) | As-of roster (now) |
|---|---:|---:|
| All months | 1,231 of 25,201 | 689 of 25,187 |
| February 2025 | 177 | 47 |
| February 2026 | 222 | 22 |
| October 2025 | 491 | 378 |
| November 2025 | 129 | 74 |

Priced players whose latest team is neither side of the game fell from 277 to 192, mostly traded players now placed on
their new team.

**The limit that stays.** A player who left in the summer is still counted in his old team's pool in October 2025 unless
his new team listed him inactive or on its report before the decision; nothing else in the cache says where he went
before he plays. That is the 378. **So each cell's bets in October and in February are reported beside it,** in the beside
table and in `--smoke`, never judged.

### 16.4 `--full` refuses any other books or floor

`refuse_full` now checks `config.BEST_LINE_BOOKMAKERS` and the harness's deciding books against the eight this doc
registers (draftkings, fanduel, betmgm, williamhill_us, fanatics, betrivers, hardrockbet, betparx), and
`config.DEFAULT_MIN_ODDS` and the harness's floor against −200. A checkout whose `.env` or environment overrides either
refuses to run.

### 16.5 Four choices, stated

- **Section 14's check now fits its factor on 2023-24's first half too.** It had used the factor fitted on all of 2023-24.
  The first-half factor is 0.857 (the whole season's: 0.8665). On the second half the map reads 0.666 / 0.486 / 0.374 /
  0.285 / 0.210 / 0.145 at lines 1.5 to 6.5 against actual 0.680 / 0.498 / 0.384 / 0.287 / 0.208 / 0.146. That is within
  0.014 at every line. The negative binomial reads 0.583 / 0.432 / 0.321 / 0.240 / 0.181 / 0.138.
- **A points line with fewer than 30 overs or fewer than 30 unders in the fit has no map,** and prices through the negative
  binomial. Every priced season's map holds all 16 lines, 0.5 to 15.5, so no offer falls back (0 counted).
- **An ESPN id that `nba_player_id_map` lacks takes the NBA id paired with it in the lineup segments,** when one ESPN id
  always sits beside one NBA id there. Measured: all 799 ESPN ids with an event in these three seasons are in the map, so
  the fallback resolves none.
- **Rows used only for the fits** (2023-24 and 2024-25 player-games with no proposition: the factor, alpha and the points
  map) are decided at tip minus 60 minutes, as the starters search's fits were. A proposition is decided at its snapshot.

### 16.6 Counts before grading, under sections 14 and 16

Counted by `python -m scripts.nba_s_q1props --smoke` on the changed lab, before any cell was graded, on the terms of
section 13. Settlement, the row ledger and the books are unchanged.

**Bets each cell would place** (2024-25 + 2025-26 = pooled; no result read):

| Market | Side | EV ≥ 0.02 | EV ≥ 0.04 | EV ≥ 0.06 |
|---|---|---|---|---|
| points | over | 2,055 + 1,676 = 3,731 | 1,703 + 1,362 = 3,065 | 1,386 + 1,060 = 2,446 |
| points | under | 3,365 + 3,260 = 6,625 | 2,885 + 2,818 = 5,703 | 2,487 + 2,422 = 4,909 |
| rebounds | over | 1,496 + 467 = 1,963 | 1,230 + 395 = 1,625 | 972 + 318 = 1,290 |
| rebounds | under | 2,295 + 722 = 3,017 | 1,914 + 603 = 2,517 | 1,575 + 497 = 2,072 |
| assists | over | 2,282 + 587 = 2,869 | 1,938 + 500 = 2,438 | 1,656 + 428 = 2,084 |
| assists | under | 1,793 + 563 = 2,356 | 1,489 + 465 = 1,954 | 1,244 + 382 = 1,626 |

Every cell has 200 or more pooled bets and 30 or more in each season.

**What each change moved.** Each change was switched off in turn, the other two kept, and the bets compared. The number is
the bets placed by one version and not the other (a proposition and book), per cell, lowest to highest:

| Change | Bets moved per cell |
|---|---|
| 16.1 own status | 52 to 201 |
| 16.2 pool-only rates | 62 to 263 |
| 16.3 as-of roster | 53 to 290 |

With all three switched off, the lab gives section 15's counts within 2 bets in every cell. The as-of roster's box events
also count box lines of 0 minutes, which the old rule skipped.

**The fits moved slightly.** First-quarter factor, 2024-25 / 2025-26: points 0.866 / 0.866, rebounds 0.897 / 0.889, assists
0.956 / 0.939 (section 13: 0.864 / 0.862, 0.894 / 0.885, 0.953 / 0.935). alpha: points 0.594 / 0.613, rebounds 0.062 /
0.062, assists 0.024 / 0.022. No number: the team pool under 30 minutes 477, the latest team neither side 192, fewer than 3
earlier first-quarter games 549, listed Out 1 (of 60,190 targets, fit rows included).

**Bets in October and in February** (lowest cut; beside, never judged). 2024-25 has no October prop. Rebounds and assists
have no two-sided quote in February 2026, because BetMGM quotes from March:

| Cell | October of 2025-26 | February of 2024-25 | February of 2025-26 |
|---|---:|---:|---:|
| points over | 167 | 417 | 213 |
| points under | 132 | 605 | 312 |
| rebounds over | 0 | 304 | 0 |
| rebounds under | 0 | 340 | 0 |
| assists over | 0 | 436 | 0 |
| assists under | 0 | 339 | 0 |

**The placebo on the real data.** The identity permutation returned the real bets in every group; no proposition is alone.
Share of a run's bets that are not real bets, three runs: points over 0.74 to 0.82, points under 0.56 to 0.66, rebounds
0.70 to 0.85, assists 0.67 to 0.79. No cell is under 0.5.

**Each change watched failing.** Seven tests (the changed own-status test and six new ones) were run on the lab as committed
at `ef414f4f`, and all seven failed. Four of them call functions the old lab did not have (`pool_status_rates`,
`team_as_of`, `pool_frame`, `map_check`), so their failure there is the function's absence. For those, and for every other
rule here, the rule was also broken inside the new lab, one at a time (scratch `explore/mutate16.py`): 11 breaks, and its
test failed every time. Two of the 11 break `roster_events`, whose test was added after the run on the old lab.
`tests/test_nba_s_q1props.py` now holds 31 tests, all passing.

**What no test pins:** that the rates are fitted on pool players rather than every listed player. That is a choice of
which rows `project` hands the fit, and the rates table in 16.2 is its measurement.

**Time and memory.** One placebo run across a group's three cuts took 0.25 to 0.39 seconds in one smoke run and 0.28 to
0.94 in the next, on a machine shared with other jobs. The projected `--full` is 7.3 to 11.6 minutes of cells plus 1.9
minutes of loading; peak memory 2.1 to 2.2 GB. The projection takes about a minute now, against 21
seconds before, because the rate fit builds pools for every team-game of 2021-22 to 2024-25.


## 17. Results (graded 2026-11-04)

Run `2026-11-04-q1props`, stored in Supabase. 18 cells and 39 controls. The grade took 412 seconds.

**0 of the 18 cells pass. First-quarter player props stay closed.** The median return is -2.0%, and 3 of 18 are
positive, all assists overs.

| Market, side | EV 0.02 | EV 0.04 | EV 0.06 |
|---|---|---|---|
| Points, over | 3,731 bets, -3.5% | 3,065, -2.1% | 2,446, -2.0% |
| Points, under | 6,625, -3.4% | 5,703, -3.2% | 4,909, -2.4% |
| Rebounds, over | 1,963, -1.4% | 1,625, -1.9% | 1,290, -1.9% |
| Rebounds, under | 3,017, -4.4% | 2,517, -3.4% | 2,072, -1.1% |
| Assists, over | 2,869, +1.2% | 2,438, +3.0% | 2,084, +2.5% |
| Assists, under | 2,356, -0.9% | 1,954, -2.5% | 1,626, -2.0% |

- **The nearest miss is assists over at EV 0.04:** 2,438 bets, +59.01 units, +3.0%, interval -1.7% to +7.6%, +3.3% in
  2024-25 and +1.9% in 2025-26. It fails the interval and the bands, since EV 0.06 returns less than 0.04.
- **The blind bets lose 4.8% to 8.3%** on every market and side. These books take a wide margin on first-quarter
  props, and the projection's choice beats the blind bet by 3 to 6 points without beating the price.
- **Points unders lose with an interval below zero** at EV 0.02 and 0.04 (-3.4%, -5.5% to -1.3%), so the projection
  leans the wrong way on first-quarter points.
