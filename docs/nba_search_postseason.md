# NBA postseason search: the two prop models that make money, on games no NBA model was graded on (pre-registered 2026-10-31, before any bet in it was graded)

mike, 2026-10-30, on the NBA having no spread or moneyline model: *"whatever is missing, find
it"*. The sweep that followed ranked this first: the only two NBA mechanisms that have made money
have never been bet or graded on a play-in, playoff or Cup final game.

**Written before any bet was graded. Nothing below changes after a result is seen; a later change
gets its own dated line and reason.** Lab: `scripts/nba_s_postseason.py`. Pass/fail:
`scripts/nba_game2_verdict.py --house5` (`docs/nba_models_2026.md` 9.1's bars). The prices were
bought with mike's approval (272 games, 243,058 rows, 37,299 credits). Nothing further is bought.

## 1. What is tested, and what earlier searches did and did not cover

- **Tested:** whether `nba_prop_market` and `nba_prop_projection`, unchanged, make money on these
  games. There is no new rule, cut or feature to choose. The question is only whether the
  population carries over. Playoffs shorten rotations and draw more casual money; that could widen
  or shrink the over-lean both models feed on, and only a grade can say which.
- **Their regular-season record:** `nba_prop_market` 24,572 bets, +781.3 units, +2.96% (record
  4.3). `nba_prop_projection` 83,360 bets, +3,410.1 units, +4.12% (record 5).
- **Covered before:** every one of the eight searches graded regular-season games only. The stored
  prop history holds 0 of these 272 games, and `docs/sports/nba.md` says every NBA model skips them.
- **Not tested here:** the two shooting-luck game models. The sweep listed them as "reported only",
  and they need game lines this purchase did not buy.

## 2. Data

| What | Held | Source |
|---|---|---|
| Prop prices | 243,058 rows, 272 games, 14 markets, 10 books, one snapshot a game | `nba_postseason_prop_odds` |
| Games | 2023-24: 82 playoff, 6 play-in, 1 Cup final. 2024-25: 84, 6, 1. 2025-26: 85, 6, 1 | `nba_schedule` (phase, round, tip) |
| Plays | every game's plays | `nba_pbp`, `nba_pbp_games` |
| Who played | starter, ESPN's whole minutes, did not play | `nba_pbp_box` |
| Seconds played, inactive lists | every postseason game | `nba_player_game_adv`, `nba_game_inactives` |
| ESPN's own box score, counting stats | every game | the public sportsdataverse file, section 3.3 |

- The tables not in the research cache are pulled once, read-only, by indexed key, into the
  scratch folder (`--pull`, which regenerates all of them).
- **The moment.** Leads before tip are 54 minutes (150 games), 59 (63) and 64 (59). The one snapshot
  is each game's decision, as the regular-season archive's was (54 for 87% of bets, 64 for 13%).
  The live window of 45-57 minutes would drop 122 games, so it is not applied; each row reports the
  three leads beside the pool.
- **Pinnacle** quotes points, rebounds and assists in 270 of the 272 games, and threes and
  points+rebounds+assists in 179.

## 3. Settlement

`nba_player_game_log` has none of these games, so settlement is built.

### 3.1 The derivation from the play feed

| Stat | Rule |
|---|---|
| Points | the `points` of every scoring play, to `athlete_id_1` |
| Threes | scoring plays with `shot_value` 3, free throws excluded |
| Assists | `athlete_id_2` of a made field goal |
| Rebounds | play types 155 and 156, to `athlete_id_1`; team rebounds name nobody |
| Blocks | `athlete_id_2` of a missed shot whose text reads "blocks" (`athlete_id_1` is the shooter) |
| Steals | `athlete_id_2` of a play whose text reads "steals)" |
| Turnovers | the 22 turnover play types (`TURNOVER_TYPES`), to `athlete_id_1`; "No Turnover" and team turnovers count for nobody |

A heave (type 282) is not a field-goal attempt. It settles nothing; attempts are inputs to the
projection model. A player in ESPN's box who played and has no event is a line of zeros.

### 3.2 The validation on regular-season games: zero was not reached

Against `nba_player_game_log`, every game of 2023-24 to 2025-26. Rows differing, games differing:

| Stat | Rows | Games |
|---|---|---|
| Points | 61 | 30 |
| Rebounds | 585 | 338 |
| Assists | 233 | 127 |
| Threes | 11 | 8 |
| Blocks | 215 | 171 |
| Steals | 402 | 217 |
| Turnovers | 237 | 153 |
| Any of them | | 746 |

The causes read so far are in the feed, not the rule: a stale copy of a scoring play left beside
its replacement, and rebounds or steals credited to a teammate in the plays and not in the final
box. So the play feed alone cannot settle a bet to the standard asked for. **A second source on the
same games is required.**

### 3.3 The second source, and the rule that leaves a game out

ESPN's own box score is public and free
(`sportsdataverse-data/releases/download/espn_nba_player_boxscores/player_box_<season>.parquet`,
the file the repo's play-by-play ingestor already reads). Against the log it differs in 34 of the
regular-season games. It holds every postseason game.

**A game is left out, and counted, when the derivation and ESPN's box disagree on any of the seven
stats for any player.** A line only one source holds counts as zeros in the other. Both sources
agree on what remains, so the number settled is the same whichever is named. **18 of the 272 are
left out, 254 kept:** 2 play-in and 16 playoff, 0 Cup finals (3 in 2023-24, 10 in 2024-25, 5 in
2025-26). No game differs on points or threes. They differ on rebounds in 10 games, assists 5,
blocks 3, steals 3, turnovers 2.

A game left out keeps its lines as projection-model history. Those inputs are not settlement, and
rows differ by one count.

**This file is not in Supabase.** `nba_pbp_box` keeps minutes only, and this job may not write. It
is read from the scratch folder and refetched by `--pull`.

### 3.4 Voids

The shipped rule (`scripts/nba_prop_market_lab.build_quotes`): a player takes the court when his
minutes are above zero or NBA.com's box gives him seconds. Measured on these games, a missing
seconds value is exactly the not-played rows (1,809 of 1,809). A bet on a player who did not take
the court is void and leaves the record.

### 3.5 Impossible numbers

Fixed before any offer was read. A row is refused and counted, never repaired, when:

- its line is outside the market's range (`LINE_RANGE`: half a point up to well past any single
  game on record), or
- an American price is under 100 or over 10,000 in size, or
- a two-way quote's implied sum is outside 1.00-1.15.

The range is set by hand and not read from the archive, because the archive itself stores a points
line of 113.5. A one-sided quote is not refused here; both rules decide on two-sided quotes only,
as shipped. Measured: 0 lines, 0 prices, 1 incoherent quote refused, of 181,506 rows in the nine
markets the rules read.

## 4. The rules, unchanged

### 4.1 `nba_prop_market` (`models/nba_prop_market.py`)

Points, rebounds, assists, threes, points+rebounds+assists. Pinnacle's proportional no-vig under
in the snapshot, its two-way quote coherent. Every bettable book at Pinnacle's exact line, coherent,
under at -200 or better. EV = fair under × decimal price - 1, floor 0.00. One bet per (game,
player, market), the best EV. **The soft-clock refusal applies:** a book whose clock is more than
10 minutes behind Pinnacle's is refused. The regular-season archive stored no clock and this
purchase does, so the shipped rule can run in full; without it is a control.

### 4.2 `nba_prop_projection` (`models/nba_prop_projection.py`)

| Market | Sides | EV floor |
|---|---|---|
| Steals | over + under | 0.02 |
| Rebounds | under | 0.01 |
| Blocks + steals | over + under | 0.05 |
| Blocks | under | 0.02 |
| Rebounds + assists | under | 0.04 |
| Threes | over + under | 0.04 |

The consensus main line only (DraftKings' two-sided line, else the line most bettable books hang,
ties to the lower). The best bettable price per side at -200 or better. The higher-EV side where
both clear. Never a proposition `nba_prop_market` bets. A quote more than 10 minutes behind the
freshest book's clock in its market is refused.

### 4.3 What the projection model needs for postseason dates

`scripts/nba_prop_projection_train.py` fits, for a season S:

| Part | How | For the postseason of S |
|---|---|---|
| Minutes and rate models | every usable played row, regular seasons 2018-19 to S | no postseason game is fitted on |
| Negative-binomial width | S as predicted by the fit through S-1 | |
| Calibration map | main-line pairs of priced regular seasons up to S | 2023-24: its own pairs. 2024-25: both. 2025-26: all three |

- **2025-26 is the shipped artifact itself** (`models/saved/nba_prop_projection_20261016_091702.pkl`).
  The two earlier postseasons are the same recipe stopped at their season. All fitted games are
  earlier than the games they price.
- **Rebuilt from the cache alone, the recipe reproduces the artifact:** its six widths and six maps
  to every digit printed, on the same 241,731 pairs. Run on the regular seasons, this lab's code
  rebuilds `nba_prop_market`'s 24,572 graded bets and the six cells' 54,571 bets of 2024-25 and
  2025-26, bet for bet.
- **A Cup final is played in December, mid-season.** It reads what a regular-season game of that
  date read: the fit through S-1, its width, and the map of pairs before S. For December 2023 that
  is the season's pairs before that week, with the 2022-23 stand-in for a market holding fewer than
  300, as 2023-24 was graded.

**Inputs at each decision, read as of that game:**

- **The player's and team's earlier games, including earlier games of this postseason.** The same
  frame code as graded, with box lines derived in section 3 added as history. The shipped frame
  filters to regular-season lines (`box_from_log`), so this is a stated difference, and a pass needs
  that filter opened and the results step writing postseason lines.
  - Why not regular-season lines only, the filter as it stands: every row in the conference finals
    and Finals would then read the frame's maximum of 30 days since the player last played. In
    training 2.3% of rows look like that (4,458 of 191,095) and they play 0.874 of their recent
    minutes, against 1.029 for rows under 5 days. Projected minutes fall from 18.3 to 15.8 in the
    conference finals and from 17.2 to 16.2 in the Finals. That is a false reason to bet unders, not
    a test of the model. It is graded anyway, as a control, never judged.
  - Earlier postseasons of 2018-19 to 2022-23 are not in the history.
- **No injury report.** `nba_injury_report`, `nba_injury_asof` and `nba_injury_report_pulls` hold no
  play-in or playoff game of these seasons (2026-05 holds 8 rows on 4 games from one pull, dropped so
  those games read as the others). `injuries` holds NBA rows from 2026-06 only. So every play-in and
  playoff row reads "no report", the frame's own state for an uncovered game, and "never a player
  listed Out" cannot apply.
  - **This is a measured difference from the regular-season grade:** 1.0% of postseason rows are
    covered (the three Cup finals), against every game from 2019-20 on and 67% of 2018-19 in
    training. The model's "no report" branch learned from that part of 2018-19.
  - It does not touch `nba_prop_market`, whose only input is Pinnacle's price. It may hurt the
    projection cells: teammates' absences are unknown to the model and known to the line.
  - A later backfill of the free official reports could be re-run as a control. It never replaces
    this grade.

## 5. The cells

Every cell is decided at the one snapshot, at the best of `config.BEST_LINE_BOOKMAKERS` (eight
books; never Pinnacle or Bovada), one unit to win, risk capped at 3, a push out of the denominator.

| Family | Cell | Side | Cut |
|---|---|---|---|
| PM | `nba_prop_market`, its five markets pooled | under | EV ≥ 0.00 |
| PJ | steals | over + under | EV ≥ 0.02 |
| PJ | rebounds | under | EV ≥ 0.01 |
| PJ | blocks + steals | over + under | EV ≥ 0.05 |
| PJ | blocks | under | EV ≥ 0.02 |
| PJ | rebounds + assists | under | EV ≥ 0.04 |
| PJ | threes | over + under | EV ≥ 0.04 |

**7 cells judged.** No cut is chosen here: each is the shipped floor.

**How a proposition passes through the game harness.** `H.choose` keeps one bet per (game, market)
and `H.grade` settles a "totals" row on the two scores. So each proposition is one synthetic game:
id `<game>|<player>|<market>`, market "totals", home score the stat, away score 0. An over wins
above the line, an under below, a push returns the stake; a void has no row and drops out at the
join. The whole-day bootstrap reads the real date.

**Bands (bar 5), on the EV floor:**

- `nba_prop_market`: [-0.01, 0), [0, 0.01), 0.01 and up.
- Each projection cell, relative to its floor f: [f-0.02, f), [f, f+0.02), [f+0.02, f+0.05),
  [f+0.05, f+0.10), f+0.10 and up. These edges are new, because the projection search graded nested
  floors, not bands. They are wider than its 0.01 grid steps because a 0.01 band here is thin enough
  that one bad night would decide bar 5; EV on this card runs to 0.5 and more, against 0.13 for the
  first rule. Fixed from the two rules' EV scales, before any band was graded.
- A band under 30 bets is reported and not judged.

**Reported beside every row, never bars:** DraftKings alone; the play-in, the playoffs and the Cup
final separately; the three leads; bets void.

## 6. Bars, placebo, controls

**Section 9.1's house standard, unchanged, pooled over the three postseasons:**

1. 200 or more pooled bets.
2. The pooled whole-day bootstrap 95% interval of the return is above zero (4,000 resamples, seed 7).
3. At least two postseasons have 30 or more bets, and of those all but at most one are positive.
4. Beats the blind bet on its dominant side, on the same propositions at the best price. For
   `nba_prop_market` that is a blind under at Pinnacle's line.
5. Each band from section 5 with 30 or more bets is positive, and the cell's own return is above zero.
6. The return on the choosing seasons beats the 95th percentile of 200 placebo runs.

2023-24 and 2024-25 are the choosing seasons bar 6 reads (`P3.choosing`, as section 12 did). Nothing
is fitted or chosen on them. Closing-line value cannot be read from one snapshot a game.

**Placebo, 200 runs, seeds 1-200.** Each proposition keeps its own line, books and prices and takes
another proposition's number, within (date, market):

- `nba_prop_market`: Pinnacle's no-vig under.
- `nba_prop_projection`: the model's mean over its main line, re-priced through the same width and
  map (the projection search's placebo).
- The caps control: both, then the caps run again.

**A (date, market) with fewer than 5 propositions joins the other thin propositions of its (season,
round, market).** The rounds are the play-in, first round, conference semifinals, conference finals,
Finals and Cup final. No proposition is alone in its group on the real data.

**Is the placebo a null on real data? (no result read; 10 seeds; the final run is in section 7)**

| Cell | Placebo bets that are not real bets | Share of propositions the cell bets |
|---|---|---|
| `nba_prop_market` | 0.76 | 0.17 |
| Steals | 0.62 | 0.53 |
| Rebounds | 0.36 | 0.46 |
| Blocks + steals | 0.62 | 0.48 |
| Blocks | 0.32 | 0.38 |
| Rebounds + assists | 0.45 | 0.27 |
| Threes | 0.67 | 0.50 |

It differs on every round, the thin ones included (`nba_prop_market`: 0.80 on the Finals, 0.70 on
the Cup finals). Rebounds and blocks are low for a reason a wider group does not fix: shuffling
within a season, or across all three postseasons, moves their shares by 0.03 at most (rebounds 0.36
to 0.38, blocks 0.32 to 0.34). Those cells bet about half their propositions, and much of the choice
is the price, not the model: the 2025-26 map's slope on rebounds is 0.48 and on rebounds + assists
0.31. So bar 6 there asks whether the model adds to what the price alone selects. A cell earning
from the price alone will not clear it, which is the question it should answer. This is stated now
so it is not read later as a broken bar.

**Controls, graded and reported, never judged** (`control_*` families):

| Control | What |
|---|---|
| `control_PJ_card` | the six cells pooled, caps off, with 200 placebo runs |
| `control_caps_on` | both models through the shipped door (`scripts/nba_props_card.choose`), with 200 placebo runs |
| `control_PM_no_clock`, `control_PJ_no_clock` | the population as the archive graded it, without the clock refusal |
| `control_PJ_frozen_history` | the six cells on regular-season history only (4.3) |

- **Caps.** The door takes one bet a game across both models, strongest first by each model's own EV
  percentile, and four a night. **No date holds more than 4 of these games, so the night cap never
  binds**, and caps on means one a game. Caps off is the seven judged cells.
- **A thin row is still reported.** The play-in (18 games) and the Cup final (3) read "too few games
  to tell", not "it loses".
- **Expected passes by chance:** 7 × 0.025 ≈ 0.18 cells clear bar 2 alone, before correlation. Bars
  3 to 6 make a chance pass rarer still.
- **A pass is built live** (CLAUDE.md 2) with the prices it lays stated first. It needs the results
  step writing postseason box lines and the frame reading them.

## 7. What the lab writes, and how to run it

```
python C:/Users/micha/AppData/Local/Temp/q1trend/run_with_db.py scripts.nba_s_postseason --pull
NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.nba_s_postseason --smoke
NBA_GAME2_GO=1 NBA_GAME2_RESULTS=<dir> NBA_GAME2_BETS=<dir>/bets NBA_RESEARCH_CACHE=<cache> \
    PYTHONPATH=. python -m scripts.nba_s_postseason --full
python -m scripts.nba_game2_verdict --results <dir> --house5
python -m scripts.nba_s_postseason --report <dir>
```

`--smoke` runs the synthetic checks, then prints on the real data only counts, extremes, the
placebo's differing share and a timed placebo run graded on a table of zeros. It never grades a real
bet. `--full` refuses without its three switches and writes `cells_registered.parquet`,
`cells_controls.parquet` and each cell's bets. Counts before grading follow in a dated section once
the lab's own run has printed them.
