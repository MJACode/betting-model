# NCAAB — men's college basketball: data, odds capture, models

> **Started 2026-10-26 (mike: "built an ncaab model - season starts early
> nov"; the brief was rewritten into a build prompt and he answered "1) yes,
> 2) yes, 3 approved").** The 2026-27 season opens Sunday 2026-11-01 (Notre
> Dame vs Villanova, Rome, 9:30 a.m. ET); the full US slate starts Monday
> 2026-11-02 (182 games on ESPN). Season label: the ENDING year (2026-27 is
> 2027), as ESPN labels it, like the NBA and NHL.

## The models

### The NCAAB totals model (`ncaab_total_blend`), live from 2026-10-30

mike, 2026-10-30: *"Yes to the totals model."* Real money, like every model
(CLAUDE.md §2). Code: `models/ncaab_total_blend.py` (the model),
`scripts/ncaab_total_card.py` (the card that writes its picks),
`scripts/ncaab_total_blend_build.py` (the frozen numbers),
`models/saved/ncaab_total_blend_2027.json` (those numbers for 2026-27).

**What it does, per game, as of the moment DraftKings' total is read:**

1. **Ratings.** Every team's offence, defence and pace, refit on this
   season's finals that had ENDED (tip + 2.5 hours) by DraftKings' own time on
   the quote, rounded down to the hour. Recent games weigh more (half-life 45
   days). The starting point is last season's final rating, carried at 0.72
   (scoring) and 0.9 (pace); a team new to Division I starts near the bottom.
   A team with fewer than 10 games on the schedule is pooled into one "other"
   team. Possessions are the box-score estimate (field-goal attempts minus
   offensive rebounds plus turnovers plus 0.475 free-throw attempts, the two
   teams averaged), because that is all the in-season ESPN feed gives. It runs
   0.30-0.46 possessions a game below NCAA's play-by-play count.
2. **A correction for luck and style.** A fixed linear adjustment on each
   team's three-point and free-throw percentages made and allowed so far, and
   its free-throw rate, three-point attempt rate, offensive-rebound rate and
   turnover rate, each pulled toward last season's league rate. Fitted on the
   2012-2026 seasons.
3. **Blended with DraftKings' total:** mean = line + c + beta x (model −
   line), normal spread sigma, with c, beta and sigma fitted separately for
   November and for December on, on the paid seasons 2021-2026, at
   DraftKings' first posted total (refit 2026-11-03: November c 0.2103, beta
   0.2368, sigma 17.22 on 5,735 games; December on c 0.6143, beta 0.4585,
   sigma 16.51 on 24,540).
4. **Priced at DraftKings' own two prices** on that total: the chance the bet
   wins, a push left out, minus the price's implied chance. The better side
   is bet when that edge is above **0.04**. DraftKings only: the evidence
   priced DraftKings and nothing else, so the line is not shopped.
5. **No games-played wait** (mike, 2026-11-02: *"we do not need to wait 10
   games, I never approved that, that is why we fucking have back testing, I
   want these models live now"*). Every game with a DraftKings total is priced
   from the first game of the season, on last season's ratings until this
   season's games come in. Nothing frozen changed: the November blend was
   always fitted on every quoted November game.

**When a game is decided (from 2026-11-03, mike).** At DraftKings' **first
posted** full-game total: the earliest pre-game DraftKings totals row stored
for the game, by DraftKings' own time on the row, with a total between 90 and
220 and both prices. A total outside 90-220 is a feed error and is skipped, so
the next row is the first post (the history holds one, 1465.0 for 146.5). The
odds capture stores DraftKings' first total within one five-minute poll, and
the card runs every five minutes, three minutes after each poll, so a game is
decided minutes after DraftKings posts it. Ratings and inputs are as of the
first post's hour, as the evidence's were. "First posted" here means first
stored: live, the capture polls every 5 minutes, which is closer to
DraftKings' true first post than the research's half-hourly history was.

**Only while the first post still stands.** The bet goes in at the first
post's total and prices only while that is still DraftKings' standing number
(its newest pre-game row stored in the last 90 minutes, the same total and the
same two prices). If it is not, the game is decided `first_post_gone`, with no
bet. The research graded the first post; a number no longer on the board
cannot be bet; and the game is never bet at a later number instead, because
the later instants are what the old rule bet, and they were weaker (the table
below). About half of DraftKings' first totals change by the next half-hourly
snapshot (median 31 minutes), 71% within 2 hours.

The decision, bet or not, goes into `ncaab_total_decisions` with the quote,
the cutoff and the reason, and the game is never decided again (CLAUDE.md
§1c). `check_hour` holds the run's instant, so `decided_at` minus `quote_at` is
the lag from the first post. Only BET rows go into `picks`. Games decided under
the 22:00 / 15:00 UTC rule before 2026-11-03 stay decided.

**The rule it replaced** (2026-10-30 to 2026-11-03): 22:00 UTC the evening
before if DraftKings had a total up then, else 15:00 UTC on the day, else each
hour after, at DraftKings' standing total. The evidence it shipped on was
DraftKings' first STORED total among the bought hours, which included the
previous evening's pre-tip hours (00:00-03:00 UTC) that the card never used,
so the card decided later than its own evidence.

**A hold is not a decision.** A game waits, and is looked at again on every
run, while either team has, among its games that ended before the first post,
one from the last 36 hours without a final score or both box rows
(`box_pending`), or two or more older ones without them (`box_missing`). The
36 hours are counted to the run's instant, so a box that never lands stops
holding. When the box lands the game is decided at the same first post, as of
the same hour, if that is still DraftKings' standing number, and is
`first_post_gone` if not. This is the one place the live rule bets less than
the research did: in 910 of 30,275 games of 2021-2026 (3.0%) DraftKings' first
total came within 4 hours of one team's previous game ending (tip + 2.5 hours),
and the ESPN feed stored a box a median 1.9 hours (90th percentile 3.9) after
that end time on 2026-11-02. One older game without a box does not hold (the
evidence also had a few games with no possessions). The boxes come from the
ESPN box feed (`data/ingestors/ncaab_espn_box.py`, source `espn_summary`, PR
#1103). **Before that feed runs no box is stored**: a team's first game, and
its second if the first ended more than 36 hours before the quote, is priced
on the prior alone; from the third game on its games hold.

**A run that cannot decide a due game fails.** `box_missing` can hold a
team's games all season, so it fails the run, as do an artifact built for
another season and a missing blend. The card first decides and writes every
other game, then exits 1: the job's heartbeat records `error` and the failure
alerter reports it (`CardIncomplete` in `scripts/ncaab_total_card.py`). The
worker log names the games and the teams.

**One box source per game.** The game key is ESPN's game id where the row
has one, else its contest id. Where NCAA's play-by-play rows hold a game, only
they are kept, both of them; otherwise the ESPN feed's rows. This is the source
rule the box feed (#1103) documents for `ncaab_team_game_stats`: choose the
source first. Never by team id: in 145 of NCAA's games (31 from 2022-23 on)
neither row has one (Mercy at FDU, 2022-11-09), and a key on the team id kept
one row of each, so its possessions were one team's estimate and the hold
counted it unboxed. Fixed 2026-10-31; the frozen numbers were rebuilt with it.

**The 10-game wait ran from 2026-10-30 to 2026-11-02.** It left a
`below_10_games` row on 106 games, 98 of them not yet tipped on 2026-11-02. That
row never looked at a price, so it is not a decision: a game with one that has
not tipped is decided again, and the row is replaced
(`scripts/ncaab_total_card.py`). Until 2026-11-03 that was at DraftKings'
standing total at its next hour; from 2026-11-03 it is at its first post, if
that still stands.

**The evidence for the first-post rule** (research round 5, 2026-11-03: the
model's own walk-forward replay, every game, on DraftKings' first posted total
from the stored history with the opener grid's half-hourly purchase in it,
the one feed typo removed, the blend refit on those quotes; stake_for, pushes
0, 95% interval resampled by date; 2021-2025 means seasons 2022-2025 bet, the
blend walk-forward from 2021):

| Cut | Seasons | Bets | Units | ROI | 95% interval | By season |
|---|---|---|---|---|---|---|
| 0.03 | 2021-2025 | 2,997 | +178.20 | +5.42% | [2.05, 8.69] | +7.9 / +12.5 / +4.0 / +2.2 |
| **0.04** | **2021-2025** | **1,787** | **+122.66** | **+6.26%** | **[1.72, 10.66]** | **+9.6 (307) / +13.0 (274) / +3.6 (496) / +4.1 (710)** |
| 0.05 | 2021-2025 | 1,045 | +90.12 | +7.87% | [2.49, 13.53] | +12.8 / +12.1 / +5.4 / +6.3 |
| 0.03 | 2025-26 | 998 | +55.54 | +5.09% | [-1.02, 10.86] | |
| **0.04** | **2025-26** | **649** | **+58.05** | **+8.17%** | **[0.42, 15.19]** | |
| 0.05 | 2025-26 | 387 | +45.94 | +10.86% | [0.78, 19.99] | |

At 0.04: record 983-785-19 on 2021-2025 and 367-282-0 on 2025-26. Close EV
against Pinnacle's no-vig close +1.72% and +3.87%; the bet line 1.28 and 1.77
points better than Pinnacle's close. Prices -120 to +110 (2025-26: -115 to
-105). 1,618 of 1,787 bets are overs (91%; 2025-26 613 of 649). Without the 10
best dates: +62.43 units on 2021-2025, -3.78 on 2025-26. Claimed chance of the
bets 0.580 against a hit rate of 0.542-0.592 by season: calibrated in
2022-2023, 1.4-3.9 points optimistic in 2024-2026. Betting every DraftKings
over blind lost 2.6% (2021-2025) and 5.5% (2025-26). Edge is larger at the
first post: 9.4% of games clear 0.04 there against 3.2% at the old rule's
instant (25,946 games scored both ways).

**The rule it replaced, at its own decision instant** (the same research, the
card's actual quote: DraftKings' total at 22:00 UTC the evening before if it
was in that snapshot, else 15:00 UTC, else the first later hour; every game,
cut 0.04):

| Blend | Seasons | Bets | Units | ROI | 95% interval |
|---|---|---|---|---|---|
| the shipped artifact's (fit on the evidence's quotes, so in-sample) | 2022-2025 | 1,089 | +48.63 | +4.11% | [-0.87, 9.27] |
| the shipped artifact's | 2022-2026 | 1,563 | +66.46 | +3.90% | [-0.50, 8.00] |
| walk-forward, refit at that instant | 2022-2025 | 591 | +17.78 | +2.77% | [-3.93, 9.50] |
| walk-forward, refit at that instant | 2025-26 | 228 | +21.38 | +8.61% | [-4.92, 20.76] |
| **first post (live from 2026-11-03)** | **2022-2025** | **1,787** | **+122.66** | **+6.26%** | **[1.72, 10.66]** |
| **first post** | **2025-26** | **649** | **+58.05** | **+8.17%** | **[0.42, 15.19]** |

Of the old rule's 591 walk-forward bets on 2021-2025, the first-post rule also
bets 525 games (+1.94% at its quote against +2.58% at the old one); the 1,262
games only it bets made
+8.06% (interval lower bound 2.76) on 2021-2025 and +8.95% (lower bound 0.56)
on 458 in 2025-26. Multiple
testing: about 330 cells were graded in that research; this one was
pre-registered and passes, but some passes are expected by chance. Files:
research round 5, `RESULTS.txt` (Q5 and the 2026-11-03 addendum).

**The shipped code reproduces it (2026-11-03).** `scripts/ncaab_total_blend_build.py`, run on research round 5's corrected first-post quote set, refits the blend to the research's numbers and its walk-forward replay makes the research's 2,436 bets on 2022-2026, game by game, same side and price. The card's own decision code, walk-forward over 2022-2026 (`card_path` in the build: the hold, the refit at one cutoff, the inputs, the price, the price and EV floors, each season's numbers built only from earlier seasons): 2,431 bets, every one the same game and side as the replay's (largest edge difference over every scored game 1.5e-8), no bet refused by a floor. The replay's other 5 bets are all 2021-22 IU Indianapolis games the card holds as `box_missing` (14 games of that season whose teams have two or more old games with no stored box); live, such a hold fails the run so the alerter reports it. By season: 2022: 302 bets +33.25 units, 2023 274 +39.05, 2024 496 +19.35, 2025 710 +32.21, 2026 649 +58.05. The build stores both in the artifact (`replay`, `replay.card_path`).

**The tables below are the evidence the model shipped on (2026-10-30 and
2026-11-02), graded at DraftKings' first STORED total before the opener grid
was stored.** They are kept as history.

**The replay with no wait** (2026-11-02; the build's own walk-forward replay and
grade on the copy of 2026-10-30, every quoted game kept, cut 0.04; 95% interval
resampled by date; the table's "lower team" is whichever of the two has played
fewer):

| Games | Seasons | Bets | Units | ROI | 95% interval |
|---|---|---|---|---|---|
| **Every game (live)** | **2022-2026** | **1,513** | **+93.44** | **+5.66%** | **[1.0, 10.3]** |
| Every game | 2022-2025 | 1,073 | +59.19 | +5.05% | [-0.5, 10.8] |
| Every game | 2025-26 | 440 | +34.25 | +7.13% | [-1.7, 16.3] |
| Both teams 10+ (the old wait) | 2022-2026 | 1,157 | +89.04 | +7.06% | [2.1, 12.1] |
| A team under 10 (what the wait kept out) | 2022-2026 | 356 | +4.40 | +1.13% | [-10.1, 12.1] |
| Lower team 0 games | 2022-2026 | 6 | -0.26 | -3.98% | too few |
| Lower team 1-4 games | 2022-2026 | 63 | -2.68 | -3.89% | [-29.1, 23.0] |
| Lower team 5-9 games | 2022-2026 | 287 | +7.34 | +2.34% | [-10.2, 14.0] |
| November | 2022-2026 | 97 | -2.10 | -1.98% | [-24.2, 20.9] |
| December on | 2022-2026 | 1,416 | +95.54 | +6.18% | [1.7, 10.8] |

Bets are sparse at the start of a season. The November blend carries little of
the model's gap to the line (beta 0.195), so at -110 a November bet needs the
model about 13 points over or 15.5 under. In these seasons 6 of 565 scored games
with a team on 0 games cleared the cut.

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.04 (P(win, push left out) minus DraftKings' implied) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.04: the edge filter IS the card's cut, because model_probability is that same P(win, push left out) | `ACTION_THRESHOLDS` |
| EV floor | 0.07, just under the smallest EV the cut admitted in the first-post replay of 2022-2026 (+0.0734, 2,436 bets; it was +0.0743 on the old quotes), on its own probability | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| price floor | -200, pinned (it laid -120 to +110) | `MODEL_MIN_ODDS` |
| decision moment | DraftKings' first posted total (earliest pre-game row, total 90-220, both prices), bet only while it still stands; the card every 5 minutes, 3 after each capture poll | `scripts/ncaab_total_card.load_first_posts`, `scheduler.run_ncaab_total_card` |
| decided once | a row in `ncaab_total_decisions`, bet or not | `scripts/ncaab_total_card.py` |
| settlement | full-game total, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| kill switch | `RUN_NCAAB_TOTAL_CARD=0` | the card |
| frozen numbers | built from 2011-2026; blend and residual refit at the first post 2026-11-03 | `models/saved/ncaab_total_blend_2027.json` |

**The evidence, graded exactly as it runs live** (scratch chain of
2026-10-30: box-score possessions in every season, no returning-minutes input,
ratings and inputs as of the hour-floored DraftKings first stored total, the
10-game rule, stake_for; 95% interval resampled by date):

| Cut | Seasons | Bets | Units | ROI | 95% interval | Close EV | Seasons positive |
|---|---|---|---|---|---|---|---|
| 0.02 | 2021-2025 | 3,380 | +191.68 | +5.18% | [1.9, 8.9] | -0.80% | 5/5 |
| 0.03 | 2021-2025 | 1,983 | +118.27 | +5.45% | [1.3, 9.7] | -0.31% | 5/5 |
| **0.04** | **2021-2025** | **1,094** | **+87.48** | **+7.32%** | **[2.0, 12.7]** | **+0.27%** | **5/5** |
| 0.05 | 2021-2025 | 605 | +65.02 | +9.85% | [2.7, 16.9] | +0.58% | 4/5 |
| 0.06 | 2021-2025 | 329 | +37.53 | +10.45% | [0.6, 20.5] | +1.17% | 4/5 |
| 0.02 | 2025-26 | 1,041 | +50.25 | +4.41% | [-1.5, 10.2] | +1.58% | |
| 0.03 | 2025-26 | 631 | +28.05 | +4.07% | [-3.3, 10.6] | +2.76% | |
| **0.04** | **2025-26** | **349** | **+26.76** | **+7.03%** | **[-2.0, 16.2]** | **+3.89%** | |
| 0.05 | 2025-26 | 182 | +23.27 | +11.74% | [-2.9, 26.0] | +4.86% | |
| 0.06 | 2025-26 | 85 | +20.05 | +21.64% | [0.3, 41.8] | +8.62% | |

At 0.04 by season: 2021 +6.46% (285 bets), 2022 +10.90% (110), 2023 +21.14%
(46), 2024 +4.14% (271), 2025 +7.57% (382), 2026 +7.03% (349). Record
606-475-13 on 2021-2025 and 195-154-0 on 2025-26. Calibration error over every
scored game: 0.70% on 2021-2025, 2.72% on 2025-26. No bet in November in any
season. The round-2 research version (NCAA possessions, returning minutes) made
+6.82% on 1,085 bets at the same cut; the live inputs did not weaken it.

**The shipped code reproduces it** (re-measured 2026-10-31, after the
one-source-per-game fix and the rebuild). `scripts/ncaab_total_blend_build.py`
replays the repo's own model walk-forward (blend fit on the paid seasons before
each one) on 2022-2026: 1,157 bets at 0.04 against the evidence's 1,158, 1,147
of them the same game (mean edge difference 0.0004). 2022-2025: 809 bets,
+63.28 units, +7.17% (the evidence: 809, +67.30, +7.63%). 2025-26: 348 bets,
+25.76 units, +6.78% (the evidence: 349, +26.76, +7.03%). The build prints this
replay and stores it in the artifact. **The card's own code path** (the season
load, the hold, the refit at one cutoff, the decision) run over 2025-26 at each
game's DraftKings first stored total, with numbers built through 2024-25, writes
the same 348 bets as the build on the same sides (largest edge difference
7e-9), and holds no game.

**Where the port differs from the evidence on 2025-26, measured game by game**
against the evidence's own predictions (5,586 quoted games): the 10-game counts
agree on every game, the model totals differ by a mean of 0.011 points, and the
edges by a mean of 0.0001. The one bet the evidence makes and the card does not
is Iowa vs Ohio State, 2026-03-12, over 140.5 at -110: edge 0.039946 against the
evidence's 0.040012, at the cut. The model total does not move it (the
evidence's total with the card's blend gives 0.039943). The blend does: the
build refits c and beta on its own predictions (Dec+ c 0.721, beta 0.367,
against the evidence's 0.719 and 0.368), and the card's total with the
evidence's blend gives 0.040016, a bet. The model-total differences that remain
sit on the 22 teams that played one of NCAA's 31 games from 2022-23 on with no
team id on either row: the build places those games and the evidence never did.
Their 110 games differ by a mean of 0.158 points, every other game by 0.008,
and 18 of the 20 games that differ by more than 0.3 involve one of them.

Four defects were found by replaying the card's path or in review, and
fixed: a game against an opponent with no ESPN id was dropped from the luck
and style inputs; the same game was read as unboxed (which held 2,857 of 5,586
games); the build pooled a team by another season's schedule; and a game with
no team id on either NCAA row kept one row, which on 2024-25 would have held
Fairleigh Dickinson and Saint Francis as `box_missing` all season (five such
games each).

**The risks, plainly** (the first five bullets are the first-post research
above; the rest are from the evidence it shipped on):

- **Speed.** About half of DraftKings' first totals change within about half
  an hour. Bets whose first total stood over 2 hours made +9.9% on 2021-2025;
  those that changed within 30 minutes +6.3% (2025-26: +2.3%). The card bets
  within about eight minutes of the capture's poll, and never at a number that
  has moved.
- **2025-26 rests on its best days.** Without its 10 best dates the first-post
  rule's 2025-26 is -3.78 units; 2021-2025 keeps +62.43.
- **It claims more than it hits in recent seasons.** The bets' claimed chance
  of winning is 0.580; they hit 1.4-3.9 points less in 2024-2026.
- **91% of its bets are overs** (1,618 of 1,787 on 2021-2025; 613 of 649 in
  2025-26). Betting every DraftKings over blind lost 2.6% and 5.5%, so it is
  not just an over lean, but expect an over-heavy card.
- **Closing-line value is positive but modest.** Close EV against Pinnacle's
  no-vig close is +1.72% (2021-2025) and +3.87% (2025-26) at the first post.
  On the quotes it shipped on it was +0.27%, with an interval that included
  zero.
- **The games the wait kept out are about break-even** (the table above):
  they add 356 bets and +4.40 units over five seasons, and the seasons split
  (2022 +25.20%, 2023 -6.02%, 2024 -0.51%, 2025 -10.14%, 2026 +8.46%).
- **The model reads low on opening night.** It starts from last season's
  end-of-season scoring, which has sat under the next November's: 145.2 against
  152.3 in 2025-26, and 148.4 for 2026-27. Model minus DraftKings' first total on
  each first full slate: +1.20, -1.06, +0.23, +0.24, -2.86 (2022-2026), and -4.45
  on the 106 games decided by 2026-11-02. In those past slates, 21 games had the
  model 7+ under the line, and the result beat the line in 15 of them (mean +7.14
  points). So early unders are the thinnest bets it makes; its November unders
  were 10-6-1 on 17 bets.
- **The cut was chosen on the seasons it is graded on**, though the returns
  form a plateau (+5.18% to +10.45% across 0.02-0.06), not a peak.
- **Pinnacle had posted no 2026-27 NCAAB totals** when this shipped (seven
  books in `odds` for season 2027 on 2026-10-30), so the closing-value
  columns start empty.

### The NCAAB spread model (`ncaab_spread_market`), live from 2026-11-02

mike, 2026-11-02: *"we need to build 1H and game lines ML and Spread no matter
what"*, and the same day, *"we do not need to wait 10 games ... I want these
models live now"*. Real money, like every model (CLAUDE.md §2), with no
games-played wait. Code: `models/ncaab_spread_market.py` (the rule),
`models/ncaab_book_quotes.py` (every book's quote at 15:00 UTC),
`models/ncaab_margin_dist.py` (the final-margin distribution),
`scripts/ncaab_spread_card.py` (the card that writes its picks),
`scripts/ncaab_spread_market_build.py` (the frozen numbers and the replay),
`models/saved/ncaab_spread_market_2027.json` (those numbers for 2026-27). The
quote reader and the distribution are separate modules so the moneyline and
first-half models planned next can use them.

**What it bets.** Line shopping against the books' own consensus. At 15:00 UTC
on game day (10 a.m. ET in winter, 11 a.m. ET from mid-March) it reads each of
the eight bettable books' full-game spread (DraftKings, FanDuel, BetMGM,
Caesars, Fanatics, BetRivers, Hard Rock, betPARX), takes the middle line, and
looks for one book whose line is better than the others for one side. When the
best quote's edge is above **0.03** and at least three other books quote the
game, it bets that quote, at that book's line and price.

**How a quote is priced, step by step:**

1. **Each book's quote** is its newest pre-game spread stamped in the hour up
   to 15:00 UTC. A game that tips at or before 15:00 UTC is not bet.
2. **Sign errors out.** A quote on the other side of zero from the other books'
   middle line is a pick'em sign error in the feed and is dropped.
3. **The consensus** is the middle (median) line of the remaining quotes, the
   book being priced included.
4. **The expected home margin** is minus the consensus plus a small offset:
   +0.25 points in November, -0.08 from December on. The offset is the average
   of (final margin + the Prediction Tracker opener) over the 2012-2020 free
   archive. It was fitted once and used for every season the research graded,
   including 2025-26. It was never refit on the paid seasons, so it is not
   refit here. The same average over the 2021-2026 paid seasons' 15:00 UTC
   consensus would be +0.31 / -0.02, numbers nobody has tested.
5. **The chance each side covers** comes from the distribution of final
   margins in earlier games whose closing line implied a similar margin (fitted
   on 2012-2026 for this season, 70,268 games). It keeps the real shape of
   basketball margins (few one-point games, overtime), so a push is possible
   only on a whole-number line.
6. **The edge** of a side is its chance of winning with a push left out, minus
   the implied chance of that side's own price, vig included. Each quote is
   priced on its better side (the home side on a tie). Across the books, the
   best quote is the largest edge; a tie goes to the better line, then the
   better price, then the book's name in alphabetical order. A tie on line and
   price is the same bet at two books, so the last step only names which.

**When a game is decided: at 15:00 UTC on its date, once.** The card runs
hourly at five past (UTC), but only the run in the 15:00 hour decides
anything, and it reads the quotes as of 15:00 UTC even if it runs late in that
hour. The decision, bet or not, goes into `ncaab_spread_decisions` with every
book's quote, the consensus and the reason, and the game is never decided
again (CLAUDE.md §1c). Only BET rows go into `picks`. A game that tips after
15:00 UTC but before the run gets to it is recorded as `tipped`, not bet: a
pick is never announced for a game under way.

**A missed 15:00 is a failure, never a late bet.** The research tested no
other hour that held up: 22:00 UTC the evening before failed, and the hour
before tip made +0.43%. So when a later run finds one of the day's games with
no decision (the 15:05 run died, was skipped, or the card was switched off),
it records the game as `missed` with no bet and the run exits 1: the heartbeat
records an error and the failure alerter reports it. The one exception is the
card's very first run: games whose 15:00 came before the card existed are
recorded as `missed` without an error. Two other conditions fail the run after
it writes what it can: every due game with no quote at all (the odds steps
have stopped), and a best quote at a book `config.BEST_LINE_BOOKMAKERS` no
longer lists. The next-best quote is not bet instead, because that is not the
quote the research chose.

**Is a fresh quote there at 15:00?** Measured on the 2026-27 slate on
2026-11-02 (119 games with odds): the hourly refresh pass at :17 past 9 a.m. ET
stores every listed book's spread, so at 15:00 UTC the median quote is 42
minutes old and inside the one-hour window. Across that day's hours, 83% to 96%
of book-and-game pairs had a quote inside the window. Caesars was missing from
the 14:00-16:00 UTC passes that day (3% of its games fresh at 15:00). The
five-minute capture job writes a row only when a number moves, so an unchanged
quote keeps the refresh pass's stamp. The research's quotes came from a bought
snapshot taken at 15:00 UTC (its bet quotes were a median 5.5 minutes old).
Live quotes are the
refresh pass's plus any changes since. They give the same number unless a book
takes its line down without the feed showing it.

**The bet row.** `scored_line` is the bet book's home number (CLAUDE.md §4).
The label is the platform's ("Duke -8.0"), checked against side and line
before it is written. `decision_*` and `best_*` are the bet book's price. When
DraftKings had the same line at 15:00 UTC, `line_book` is empty and `dk_odds`
/ `dk_implied_prob` / `edge` are DraftKings' own price on that side, the
reference. Otherwise `line_book` names the bet book and `dk_odds` is empty, the
same convention as a pick scored off another book's line. `model_probability`
is the chance of winning with a push left out, the number the 0.03 cut was
measured on, so the publishers' edge filter agrees with the card. **Read this
model's edge from `decision_edge`, never `edge`**: on a bet off DraftKings'
line `edge` is 0.0 by that convention. Settlement: full-game spread, overtime
included.

**The first live read (2026-11-02, read-only).** The card's own code, run
against production as of 15:05 UTC on the season's first full slate (no row it
read was stored after 15:05): 179 games due, 116 with at least one quote, 63
with none (mostly small schools the odds feed does not list). It would have
bet 9, labels as the card writes them: Vanderbilt -32.5 (Hard Rock -110),
Oklahoma -30.5 (Hard Rock -105), Oklahoma State -29.5 (betPARX +112), Wake
Forest -30.5 (Fanatics -110), Marquette -30.5 (betPARX -109), South Alabama
-1.5 (DraftKings +110), Radford +11.5 (FanDuel -102), Bryant +5.5 (DraftKings
-108) and South Carolina Upstate +14.5 (Fanatics -110). None was refused by
the price or EV floor. Five of the nine are favourites of 29.5 points or more.
In four of those the books split between two numbers and the bet takes the
smaller (Vanderbilt: 3 books at -32.5, 4 at -35.5; Oklahoma 3 and 3; Wake
Forest 2 and 3; Marquette 3 and 4); Oklahoma State is the price, +112 on a
line a point longer than the consensus. Nine bets from 116 quoted games is a
far higher rate than the research's 542 from about 32,000, as early-November
slates run, and it is the first thing to watch.

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.03 (P(win, push left out) minus the bet price's implied) | `config.MODEL_EDGE_THRESHOLDS` |
| other books | at least 3 other books in the consensus | `models/ncaab_spread_market.MIN_OTHER_BOOKS`, the artifact |
| prob / edge filter | 0.0 / 0.03: the edge filter IS the card's cut | `ACTION_THRESHOLDS`, `MODEL_PROB_THRESHOLDS` |
| EV floor | 0.05, just under the smallest EV the cut admitted in the replay (+0.0563; median +0.0697, 542 bets) | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| price floor | -200, pinned; the replay laid -120 to +114 (median -110) | `MODEL_MIN_ODDS` |
| decision instant | 15:00 UTC on the game's date; quotes stamped 14:00-15:00 UTC | `models/ncaab_book_quotes.py` |
| decided once | a row in `ncaab_spread_decisions`, bet or not | `scripts/ncaab_spread_card.py` |
| settlement | full-game spread, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| kill switch | `RUN_NCAAB_SPREAD_CARD=0` | the card |
| frozen numbers | offset from 2012-2020, distribution from 2012-2026 | `models/saved/ncaab_spread_market_2027.json` |

**The evidence: the card's own code, replayed** (2026-11-02,
`scripts/ncaab_spread_market_build.py` on the copy of the Supabase reads taken
for the research; each season priced with the distribution fitted on the
seasons before it; stake_for; units; 95% interval resampled by date). It
matched all 613 of the research's bets game by game (game, side, line, price,
and the same book on all 613). Its distributions equal the research's to the
last digit (largest difference 0.0).

| Population | Seasons | Bets | Record | Units | ROI | 95% interval |
|---|---|---|---|---|---|---|
| **Live: 3+ other books** | **2021-2025** | **409** | **230-170-9** | **+44.60** | **+9.97%** | **[0.8, 18.4]** |
| **Live: 3+ other books** | **2025-26** | **133** | **84-49-0** | **+30.34** | **+20.96%** | **[6.3, 35.4]** |
| Every game (the research's version) | 2021-2025 | 478 | 271-197-10 | +57.23 | +10.97% | [3.1, 18.7] |
| Every game | 2025-26 | 135 | 86-49-0 | +32.34 | +22.01% | [7.0, 36.4] |

By season, live version: 2020-21 +10.69% (14 bets), 2021-22 +15.55% (120),
2022-23 +1.29% (53), 2023-24 +11.59% (77), 2024-25 +7.59% (145), 2025-26
+20.96% (133). The three-other-books minimum was tested after the research had
seen its results; it removes 71 bets that leaned on one or two other books.
Neighbouring cuts (research, every game, 2021-2025): 0.02 +4.72% on 1,511 bets
[-0.4, 9.7]; 0.04 +23.32% on 163 [9.6, 36.1]. With three other books: 0.02
+4.21% on 1,342 [-1.1, 9.4]; 0.04 +19.39% on 129 [3.4, 34.6].

**The risks, plainly:**

- **The true edge is probably about +2% a bet, not +10%.** Against Pinnacle's
  closing line, the 613 bets were worth +2.28% a bet on 2021-2025 and -0.05% on
  2025-26 (the live version: +1.83% and -0.15%). The +10% and +21% are a
  favourable draw inside wide intervals. Without its 10 best dates the live
  version made +3.76% on 2021-2025 and +3.25% on 2025-26.
- **The edge is the off-market number, not a read on the game.** The
  research's 478 bets on 2021-2025, re-bet on the same sides at the consensus
  line at -110, made +1.71% [-6.1, 9.4]. In the live version the profit comes
  from quotes 1 point or more better than the
  other books: +13.6% on 187 bets at 1 to 1.5 points and +29.0% on 58 at 1.5 or
  more, against -4.4% on 134 at half a point to 1 (2021-2025). On 2021-2025 it
  sits in lines of 12.5 or more (250 bets, +17.58%); the 159 bets on smaller
  lines lost 2.22%. In 2025-26 the smaller lines made more (54 bets, +21.09
  units, against 79 bets, +9.25 units), so where the edge sits is not settled.
- **Nobody has measured how often a 15:00 UTC off-market number can actually
  be bet.** At the bet book's next poll (median 6 hours later) 48% of the
  research's 2021-2025 bets (41% in 2025-26) had already moved to the
  consensus. A number that is gone by the time a member opens the
  app is a bet of record they could not get. The ledger keeps every book's
  quote, so this is the first thing to measure live.
- **2025-26 is a second look, not a clean hold-out.** The research had already
  opened that season in an earlier round before choosing this rule.
- **Early-season games are in.** 185 of the 409 live 2021-2025 bets (45%) are
  in November (+9.97%), and a 10-game wait would have kept them all out. With
  that wait the live version made +6.56% on 178 bets on 2021-2025, interval
  [-7.5, 20.8].
- **The book mix depends on the feed.** FanDuel, BetMGM, betPARX, DraftKings and
  Caesars carry most bets (95, 93, 89, 84 and 83 of 542). A book the feed stops
  sending is simply absent; one whose quote is stale falls out of the window.

**The build's tables depend on read order in one place.** 140 games have two
archive rows from the same source (`ncaab_archive_lines`); the build keeps the
first as read, as the research did. Read in another order (sorted by row key),
the tables move by up to 0.0009. The 2026-11-02 build read the research's copy and reproduced
its tables exactly.

**Before the 2027-28 season** rebuild the frozen numbers through 2026-27
(`python -m scripts.ncaab_spread_market_build --cache <copy> --last-season
2027`). The card refuses a season the artifact was not built for, and those
games are then recorded as missed.

### The NCAAB moneyline model (`ncaab_moneyline_own_spread`), live from 2026-11-02

mike, 2026-11-02: *"we need to build 1H and game lines ML and Spread no matter
what"*, *"we do not need to wait 10 games"*, *"I want it all done and go live
now"*, and the cap: *"-200 max"*. Real money, like every model (CLAUDE.md §2),
with no games-played wait. Code: `models/ncaab_moneyline_own_spread.py` (the
rule), `scripts/ncaab_moneyline_card.py` (the card that writes its picks),
`scripts/ncaab_moneyline_build.py` (the frozen numbers and the replay),
`models/saved/ncaab_moneyline_own_spread_2027.json` (those numbers for
2026-27). It reuses the spread model's quote reader
(`models/ncaab_book_quotes.py`) and final-margin distribution
(`models/ncaab_margin_dist.py`), and prices with the spread model's own
2026-27 table.

**It did not clear the research bar, and it was chosen after the fact.** Say
both plainly whenever its record is quoted. The research's pre-registered
primary test (the hour before tip, the other books' spreads, the 10-game rule)
failed. This version was picked after mike's -200 limit, from the 162
versions the research regraded at that limit (18 rule variants, each at 9
cuts). Its 2021-2025
95% interval runs from -1.22% to +9.25%, so it includes losing. Every season
was positive, and 2025-26 was too, but against Pinnacle's closing line its
bets were worth slightly less than nothing (about -0.2% a bet on 2021-2025,
-1.4% on 2025-26).

**What it bets.** Each book's moneyline against that same book's own spread.
A book's spread and its moneyline are two prices for the same game; when the
moneyline is cheaper than the spread implies, the moneyline is the bet. At
15:00 UTC on game day (10 a.m. ET in winter, 11 a.m. ET from mid-March), the
same instant and the same one-hour freshness window as the spread model, it
reads each of the eight bettable books' full-game moneyline and full-game
spread. It bets the single best side of the game when its edge is above
**0.01**, at that book's price, and never at a price shorter than -200.

**How a side is priced, step by step:**

1. **Each book's quotes** are its newest pre-game moneyline and spread stamped
   in the hour up to 15:00 UTC. Pinnacle's and Bovada's moneylines are read
   too, only for the favourite check in step 3; they are never bet. A game
   that tips less than five minutes after 15:00 UTC is not priced.
2. **The book's fair chance of a home win, from its own spread.** The spread's
   two prices are de-vigged (power method) to the chance the home side covers.
   The final-margin distribution (fitted on 2012-2026, 70,268 games, the
   spread model's table) is turned around to find the expected home margin
   that gives that cover chance at that line. The chance of a home win is the
   chance of a positive final margin at that expected margin (overtime
   included, so a tie cannot happen). No consensus and no offset: each book is
   priced against itself. A spread is used only when both prices are -100 or
   longer, the two implied chances add up to between 1.00 and 1.15, and its
   line is not on the other side of zero from the other books' middle line.
3. **Suspect moneylines out.** A moneyline is not priced when its two implied
   chances add up outside 1.00-1.15; when its favourite differs from every
   other book's favourite (two or more other books, Pinnacle and Bovada
   counted); or when the same book's spread is 1.5 points or more and names
   the other team as favourite.
4. **The -200 cap comes before the pick.** Every side priced shorter than
   -200 is removed first. A game whose best side is -250 is then bet at its
   next-best side, if that side clears the cut.
5. **The edge** of a side is its fair chance minus the implied chance of its
   own price, vig included. The bet is the largest edge in the game, over
   every book and both sides; a tie goes to the longer price, then the book's
   name in alphabetical order (the same bet at two books, so the last step
   only names which).

**When a game is decided: at 15:00 UTC on its date, once.** Exactly as the
spread model (above): the card runs hourly at five past (UTC), only the run in
the 15:00 hour decides, the decision goes into `ncaab_moneyline_decisions`
with every book's moneyline, its own spread and its flags, and the game is
never decided again (CLAUDE.md §1c). A missed 15:00 is recorded as `missed`
with no bet and fails the run; every due game with no moneyline at all, an
artifact for another season, and a best side at a book
`config.BEST_LINE_BOOKMAKERS` no longer lists fail it too. It is its own job,
not the spread card's, so a moneyline failure never fails the spread model's
heartbeat, and the reverse.

**The bet row.** A moneyline: `scored_line` and `line_book` are empty. The
label is the platform's ("Duke ML"), checked against the side before it is
written. `decision_*` and `best_*` are the bet book's price. When DraftKings
had a clean moneyline at 15:00 UTC, `dk_odds` / `dk_implied_prob` / `edge` are
DraftKings' own price on that side, the reference; otherwise `dk_odds` is
empty and the other two 0.0. `model_probability` is the bet side's fair chance
from the bet book's own spread, the number the 0.01 cut was measured on, so
the publishers' edge filter agrees with the card. Settlement: full-game
moneyline, overtime included (`games.home_win`).

**The id has "spread" in it, and the pick is a moneyline.** Several places
read a pick's market from its model id by looking for the word "spread". Each
one now names this id first: the app (`mobile/src/lib/markets.ts`), the
Claude-mobile prompt (`docs/mobile_picks_prompt.md`), the closing-line
function, settlement and the line-movement check; `tests/test_ncaab_moneyline_own_spread.py`
and `tests/test_rule_model_markets_everywhere.py` pin them. One was left
alone: the production view `v_model_full_record`, which nothing in the repo
reads, maps any id with "spread" in it to spreads. A moneyline pick has no
line, so that view leaves this model's bets out rather than grading them
wrong.

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.01 (fair chance from the book's own spread minus the bet price's implied) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.01: the edge filter IS the card's cut | `ACTION_THRESHOLDS`, `MODEL_PROB_THRESHOLDS` |
| price cap | -200: sides shorter than -200 removed before the pick, and pinned again | `models/ncaab_moneyline_own_spread.MIN_PRICE`, `MODEL_MIN_ODDS` |
| EV floor | 0.015, just under the smallest EV the cut admitted in the replay (+0.0156; median +0.027). An edge above 0.01 at -200 or longer is always EV above 0.015, so it removes nothing the cut takes | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| decision instant | 15:00 UTC on the game's date; quotes stamped 14:00-15:00 UTC | `models/ncaab_book_quotes.py` |
| decided once | a row in `ncaab_moneyline_decisions`, bet or not | `scripts/ncaab_moneyline_card.py` |
| settlement | full-game moneyline, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| kill switch | `RUN_NCAAB_MONEYLINE_CARD=0` | the card |
| frozen numbers | the spread model's 2012-2026 distribution, pinned by its SHA-256 | `models/saved/ncaab_moneyline_own_spread_2027.json` |

**The evidence: the card's own code, replayed** (2026-11-02,
`scripts/ncaab_moneyline_build.py` on the copy of the Supabase reads taken for
the research; each season priced with the distribution fitted on the seasons
before it, which equals the research's to the last digit; stake_for; units;
95% interval resampled by date). It matched all 914 of the research's bets game by
game: the same game, side, price and book on all 914, and the same edge to the
last digit (largest difference 0.0). No research bet was missing and the replay
added none.

| Seasons | Bets | Record | Units | ROI | 95% interval | Without the 10 best dates |
|---|---|---|---|---|---|---|
| **2021-2025** | **838** | **511-327** | **+53.11** | **+4.22%** | **[-1.2, 9.3]** | +7.94 units |
| **2025-26** | **76** | **45-31** | **+14.04** | **+15.05%** | **[-4.9, 32.3]** | -6.24 units |

By season: 2020-21 +5.53% (21 bets), 2021-22 +4.90% (285), 2022-23 +5.42%
(233), 2023-24 +2.71% (174), 2024-25 +1.98% (125), 2025-26 +15.05% (76).
Neighbouring cuts, 2021-2025: 0.005 +12.00 units (1,450 bets, +0.55%); 0.015
+13.57 units (430 bets, +2.12%). It laid -200 to +1,000 (median -159).

**The risks, plainly:**

- **The close says there is no edge.** Against Pinnacle's no-vig closing line
  its bets were worth -0.21% a bet on 2021-2025 (813 with a Pinnacle close)
  and -1.38% on 2025-26; against the bettable books' close, -0.08% and -1.18%.
  A real edge shows up as positive close value. The profit so far is what a
  break-even bet can return by luck.
- **It leans on a few dates.** Without its 10 best dates, 2021-2025 is +7.94
  units on 828 bets and 2025-26 is -6.24 units.
- **The profit sits in home sides.** On 2021-2025 home bets made +68.31 units
  (623 bets, +7.08%) and away bets lost 15.20 (215, -5.15%); 2025-26 was
  positive on both. 86% of the 2021-2025 bets were favourites.
- **It was chosen after the fact, from 162 versions.** A version picked from
  162 regrades will look better than its true rate. The neighbouring cuts made
  much less (+12.00 and +13.57 units against +53.11).

**Review at 50 settled bets** (gate standing, CLAUDE.md §2: at least 50
settled picks, positive flat-bet ROI, calibration within 5%). Read beside the
ROI: the close value, and how often the bet book's price was still up when the
pick posted (the ledger keeps every book's 15:00 quote).

**Before the 2027-28 season** rebuild the spread model's frozen numbers first,
then this one (`python -m scripts.ncaab_moneyline_build --cache <copy>
--last-season 2027`): it refuses to write unless its own fit equals the spread
artifact's table, and the card refuses a table whose digest moved.
### The NCAAB first-half spread model (`ncaab_first_half_spread`), live from 2026-11-02

mike, 2026-11-02: *"we need to build 1H and game lines ML and Spread no matter
what"*, and the same day *"we do not need to wait 10 games ... I want these
models live now"*. Real money, like every model (CLAUDE.md §2). **It did not
clear the research bar on the evidence it was built on** (the 95% interval's
lower bound is below zero, below). Re-measured on fresher full-game lines on
2026-11-03, it does (below). It is live on mike's instruction. Code: `models/ncaab_first_half_spread.py` (the
model), `scripts/ncaab_first_half_spread_card.py` (the card),
`data/ingestors/ncaab_first_half_odds.py` (the first-half capture),
`scripts/ncaab_first_half_window.py` (the schedule), and
`scripts/ncaab_first_half_spread_build.py` (the frozen numbers in
`models/saved/ncaab_first_half_spread_2027.json`). The build's `--store` copies that file into
`model_artifacts` (a production write, run after a rebuild).

**What it bets.** One side of the first half's spread, at most once a game,
about ten minutes before tip, at whichever bettable book's quote has the
largest edge. It settles on the first half's score; a first half has no
overtime, and a level first half on a whole-number line is a push.

**How it prices a game** (the research's round 4, family A, market
`spreads_h1`, snapshot close, best book, cut 0.02, every game; confirmed line by
line from its `fh_lib.py`, `fh_prep.py`, `fh_score.py` and `fh_grade.py`):

1. **The full-game consensus.** The median of the bettable books' newest
   full-game home spread stored by the decision moment (DraftKings, FanDuel,
   BetMGM, Caesars, Fanatics, BetRivers, Hard Rock, betPARX; never Pinnacle).
   M is minus that number: the home team's expected full-game margin.
2. **The first-half mean.** a + b x M, plus half the difference of the two
   teams' first-half tendencies. a and b are one least-squares fit of the
   first-half home margin on the closing full-game consensus over every
   earlier season. They are fitted once per season and frozen, not refitted as
   the season goes (for 2026-27: a = -0.037, b = 0.557 on 2021-2026).
3. **The team tendency.** For each finished game with both halves and closing
   lines stored: the home team's first-half margin minus its second-half margin,
   less what the closing line predicts for that gap (a fitted line, frozen).
   Each team's sum this season, plus half of last season's, divided by its games
   plus half of last season's plus 782.2. The 782.2 is heavy shrinkage: a team
   with 30 games keeps about 4% of its own average, so the term moves the mean
   by a quarter of a point at most. Only games that ended (tip + 2.5 hours)
   before the decision count.
4. **The price.** Each bettable book's first-half spread is priced through a
   table of how first-half margins actually fell in past games with a similar
   mean (a kernel table of whole-point outcomes, so the 4.4% of first halves
   that end level at a pick'em mean are a push mass, not smoothed away). The
   chance the side covers, a push left out, minus the price's own implied
   chance (vig included) is the edge. Each quote takes its better side.
5. **The bet.** The single quote with the largest edge, ties to the
   alphabetically first book. Bet when that edge is above **0.02**; otherwise the
   game is decided with no bet.

**When.** The capture fetches each game's first-half lines nine times
(below). The decision is the fetch ten minutes before tip. If it fails, the
job retries every minute, and a fetch that lands 5 to 10 minutes before tip
still decides. With none by 5 minutes out, the game is not decided: the
20-minute fetch is not used instead, because the research graded only the
ten-minute snapshot. The card then fails its run, and the failure alerter names
the game once it tips (`undecided:ncaab_first_half_spread`). Each decision, bet
or not, goes into `ncaab_first_half_spread_decisions` with every book's priced
quote, and the game is never decided again (CLAUDE.md §1c).

**The evidence** (the research's `grid.csv`, every game, quotes bought ten
minutes before tip, graded at their own prices to win one unit; 95% interval
resampled by date):

| Cut | Seasons | Bets | Units | ROI | 95% interval |
|---|---|---|---|---|---|
| 0.01 | 2024-2026 | 2,666 | +81.36 | +2.75% | [-0.64, 6.31] |
| **0.02** | **2024-2026** | **1,253** | **+68.07** | **+4.91%** | **[-0.30, 10.63]** |
| 0.03 | 2024-2026 | 575 | +35.65 | +5.61% | [-1.74, 13.05] |
| 0.04 | 2024-2026 | 277 | -3.98 | -1.30% | [-11.93, 9.69] |

At 0.02 by season: 2023-24 +6.06% (477 bets, +31.44 units), 2024-25 +2.80% (533,
+16.47), 2025-26 +7.19% (243, +20.16). Record 682-556-15. Prices -140 to +125.
Without its 10 best dates: +16.75 units. With the old 10-game rule on, the same
cut made only +6.87 units on 698 bets (+0.90%): most of the profit is in the
early-season games that rule kept out.

**Re-measured on fresher full-game lines (research round 5, 2026-11-03; no code
changed).** The evidence above read the full-game consensus from a copy of the
odds taken on 2026-10-30. Read from every full-game row stored on 2026-11-03
(the opener grid and later purchases added rows), the same rule at cut 0.02
makes 1,143 bets, 628-503-12, +74.40 units, +5.90%, 95% interval [0.71,
11.69]. By season: 2023-24 435 bets, +40.18 units (+8.50%); 2024-25 511,
+16.94 (+3.00%); 2025-26 197, +17.28 (+7.66%). Neighbours: 0.01 +90.22 units,
0.03 +26.29. Without its 10 best dates +21.96 units. Prices -143 to +125. So it
now clears the bar it missed: the lower bound is above zero, every season is
positive, and both neighbouring cuts are positive. (Round 5 had graded this
time before, so it was a reference row there, not one of the versions it
chose among.) No earlier fetch time beats ten minutes before tip on the same
games: against 15:00 UTC, 18:00 UTC and an hour before tip, the paired
per-date difference's interval spans zero at cuts 0.01, 0.02 and 0.03 (at
0.02, the hour-before rule made 13.21 units less, interval [-62.11, 36.01]).

**The shipped code reproduces it exactly.** The build replays 2023-24 to 2025-26
through the card's own functions (the as-of consensus, the team term, the
pricing, the best-offer choice), refitting the frozen numbers before each season
on the earlier seasons only. Its 1,253 bets are the research's 1,253, the same
game, side, book, line and price on every one (largest edge difference 3e-16).
The research's period scores and `ncaab_period_scores` agree on all 35,307
graded games.

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.02 (P(cover, push left out) minus the bet book's implied) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.02: the edge filter IS the card's cut | `ACTION_THRESHOLDS` |
| EV floor | 0.03, just under the smallest EV the cut admitted in the replay (+0.0346; median +0.0552), on its own probability | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| price floor | -200, pinned (it laid -140 to +125) | `MODEL_MIN_ODDS` |
| books | the eight above, and only those `BEST_LINE_BOOKMAKERS` still lists | `models/ncaab_first_half_spread.BOOKS` |
| decision fetch | 5 to 10.5 minutes before tip, the tip-minus-10 call or its retries | `scripts/ncaab_first_half_spread_card.DECISION_LEAD_MIN` |
| decided once | a row in `ncaab_first_half_spread_decisions`, bet or not | the card |
| settlement | the first half's margin plus the home number (period 1 of `ncaab_period_scores`); pending while the periods are missing or do not add up to the final | `tracking/paper_tracker._ncaab_first_half_points` |
| closing value | not measured: no fetch after tip minus 10, and the decision fetch is never read as its own close | `tracking/paper_tracker._closing_odds`, the CLV migration |
| kill switch | `RUN_NCAAB_FIRST_HALF=0` stops the fetches and the card | `scripts/ncaab_first_half_window.enabled` |
| frozen numbers | fitted on 2021-2026 | `models/saved/ncaab_first_half_spread_2027.json` |

**The risks, plainly:**

- **It did not clear the bar on its first evidence.** The pooled interval's
  lower bound was -0.30%, and 2024-25 made only +2.80%. Without its 10 best
  dates it keeps +16.75 of its +68.07 units. On the fresher full-game lines the
  lower bound is +0.71% (above).
- **The quotes' freshness is unverified.** The purchase stamped every book's
  quote with the purchase time, not the book's own update time, so how stale a
  "tip minus 10" quote really was is unknown. Live, each book's own update age
  is stored on every fetch (`book_ages`).
- **The book mix changed.** Caesars (500 of the 1,253 bets) and BetRivers
  (254) quoted first halves in 2023-24 and 2024-25 and dropped out of the feed
  in 2025-26 (73 and 0 games quoted). 2025-26's 243 bets were FanDuel 139,
  Hard Rock 43, BetMGM 40, DraftKings 17 and Caesars 4.
- **It is an away-side card.** 971 of the 1,253 bets are the away team (282
  home); 178 of 243 in 2025-26.
- **No closing value can be measured.** The research has no quote after tip
  minus 10, and live takes none.
- **Live inputs are fresher than the evidence's.** The evidence's full-game
  consensus at tip minus 10 came from snapshots bought about an hour before
  tip; live it is the five-minute capture. The closing lines behind the team
  term come from the capture too.
- **Same-day period scores can be missing.** The ESPN box feed stores an
  evening's halves from the 12:17 am pass. A team's game that ended before the
  decision but has no stored halves is left out of its term and counted
  (`missing_halves` on the decision row). The term is a fraction of a point, so
  the game is decided anyway.

#### The first-half capture

`data/ingestors/ncaab_first_half_odds.py`, run by the window job
(`scheduler.run_ncaab_first_half_window`, every minute). For every game the
feed lists (one with a bettable book's full-game spread stored), one per-event
call at 15:00 UTC on its date and 180, 120, 60, 50, 40, 30, 20 and 10 minutes
before tip, the ten-minute call first on a busy tick. Each call asks for four
markets: first-half moneyline, spread and total, and both team totals. All
four are stored (source `odds_api_ncaab_first_half_live`, protected from the
odds prune), each book's main number under the market's own name and any
other rung under `<market>_alternate`. The spread decides the first-half
spread model's bets (the ten-minute call) and the total the first-half total
model's (the 60-minute call); the rest is history for the next first-half
models. Both decision calls are retried every minute when they fail, and a
fetch time that falls at the same instant as another is named for the
decision it serves (an 11am ET tip's 15:00 UTC call is its 60-minute call).
Before 2026-11-03 the earlier-listed name won, so a 10:10am ET tip's 15:00 UTC
call was named "15z" and could never decide the first-half spread. One row per call goes into
`ncaab_first_half_fetches` with the credits the feed billed.

**Cost.** The live endpoint bills one credit per market it returns, per region,
and nothing for an empty answer (measured on the live NBA and NCAAB feeds). So
a call costs at most 4 credits and a game at most 36. The measured ceiling for
2026-27, if every scheduled ESPN game were listed and every market returned:
57,204 credits in November and about 231,000 for the season (6,416 games; the
2026-11-02 purchase plan's count). The real spend is lower: unlisted games are
never called, and a book that offers fewer markets bills fewer. The balance was
4,305,317 at 22:18 UTC on 2026-11-02 (`odds_api_quota`).

**The balance floor.** Before buying, the run reads the newest recorded balance
and the platform's measured daily burn (the median day of the last two weeks).
Under one day of that burn (`NCAAB_FIRST_HALF_RESERVE_DAYS`, default 1) it buys
nothing and fails, so the alert fires. Above it every planned game is bought.
It exists only to keep the account off zero, where every live feed stops.

### The NCAAB first-half total model (`ncaab_first_half_total`), live from 2026-11-03

mike, 2026-11-03: *"we need to build 1H ... no matter what"* and *"I want it
all done and go live now"*. Real money, like every model (CLAUDE.md §2). Code:
`models/ncaab_first_half_total.py` (the model),
`scripts/ncaab_first_half_total_card.py` (the card) and
`scripts/ncaab_first_half_total_build.py` (the frozen numbers in
`models/saved/ncaab_first_half_total_2027.json`). It rides the first-half
spread model's capture and its every-minute job (above). The build's `--store`
copies the artifact into `model_artifacts` (a production write, run after a
rebuild).

**What it bets.** The over or the under of the first half's total, at most
once a game, about an hour before tip, at whichever bettable book's quote has
the largest edge. It settles on the first half's points (period 1 of
`ncaab_period_scores`). A first half has no overtime, and a total that lands
on a whole-number line is a push.

**How it prices a game** (the research's round 5, family A_to, market
`totals_h1`, the purchase an hour before tip, best book, cut 0.02, every game;
confirmed line by line from its `r5_lib.py`, `r5_prep.py`, `r5_score.py`,
`r5_grade.py` and `fh_lib.py`):

1. **The full-game consensus.** The median of the bettable books' newest
   full-game total stored by the decision moment (the eight books above; never
   Pinnacle). Call it T.
2. **The first-half mean.** a + b x T, plus the average of the two teams'
   first-half tendencies. a and b are one least-squares fit of the first-half
   total on the closing full-game consensus total over every earlier season,
   fitted once per season and frozen (for 2026-27: a = -1.928, b = 0.4850 on
   2021-2026; the research's 2025-26 numbers were -1.975 and 0.4856).
3. **The team tendency.** For each finished game with both halves and both
   closing lines stored: the game's first-half points minus its second-half
   points, less what the closing total predicts for that gap (a fitted line,
   frozen). Both teams get the same number. Each team's sum this season, plus
   half of last season's, divided by its games plus half of last season's
   plus 236. A team with 30 games this season and none last keeps about 11% of
   its own average. Only games that ended (tip + 2.5 hours) before the decision
   count. This term matters: without it the same cut made +51.29 units, not
   +125.78.
4. **The price.** Each bettable book's first-half total is priced through a
   table of how first-half totals actually fell in past games with a similar
   mean (a kernel table of whole-point outcomes). The chance the side wins, a
   push left out, minus the price's own implied chance (vig included) is the
   edge. Each quote takes its better side.
5. **The bet.** A side priced shorter than -200 is set aside first, the limit
   every NCAAB model carries. Of the rest, the single quote with the largest
   edge, ties to the alphabetically first book. Bet when that edge is above
   **0.02**; otherwise the game is decided with no bet.

**When.** The decision is the capture's call an hour before tip, the one it
already made for history. If it fails, the job retries every minute, and a
call that lands 55 to 60.5 minutes before tip still decides, if the card runs
within five minutes of it landing (it normally runs in the same minute; a bet
written later would carry a price that may be gone). With none by 55 minutes
out, the game is not decided: the 50-minute call is not used instead.
The card then fails its run, and the failure alerter names the game once it
tips (`undecided:ncaab_first_half_total`). The research's quotes were stamped
about 64 minutes before tip (median 64.4); live it is about 60. Each decision,
bet or not, goes into `ncaab_first_half_total_decisions` with every book's
priced quote and each book's own update age, and the game is never decided
again (CLAUDE.md §1c).

**The evidence** (the research's round 5 grid, every game, quotes bought an
hour before tip, graded at their own prices to win one unit; 95% interval
resampled by date):

| Cut | Bets | Units | ROI | 95% interval | 2023-24 | 2024-25 | 2025-26 |
|---|---|---|---|---|---|---|---|
| 0.00 | 7,696 | +12.21 | +0.14% | [-2.05, 2.35] | 0.00% | +0.77% | -0.39% |
| 0.01 | 4,529 | +129.76 | +2.53% | [-0.38, 5.24] | +1.61% | +5.28% | +0.66% |
| **0.02** | **2,529** | **+125.78** | **+4.40%** | **[0.57, 8.12]** | **+7.06%** | **+4.27%** | **+1.85%** |
| 0.03 | 1,369 | +76.86 | +4.98% | [-0.04, 9.94] | +7.26% | +5.30% | +2.29% |
| 0.04 | 716 | +26.33 | +3.28% | [-3.37, 10.17] | -0.75% | +10.12% | +1.38% |

At 0.02 by season: 2023-24 859 bets, +67.27 units; 2024-25 852, +41.03;
2025-26 818, +17.48. Record 1,385-1,121-23. Prices -240 to +155. **With the
-200 limit, as it runs live:** 2,527 bets, +123.78 units, +4.34%, [0.45,
8.05]; 2025-26 816 bets, +15.48 units (+1.65%); prices -160 to +155. Without
its 10 best dates: +48.11 units. Without Hard Rock: 2,320 bets, +122.02 units,
[0.91, 8.48]. November alone: 690 bets, +35.91 units.

**The shipped code reproduces it exactly.** The build replays 2023-24 to
2025-26 through the card's own functions (the as-of consensus total, the team
term, the pricing, the -200 limit, the best-offer choice), refitting the
frozen numbers before each season on the earlier seasons only. Its fitted
first-half maps equal the research's for every season (2025-26: a -1.97489,
b 0.48559 on 26,343 games). Without the limit its 2,529 bets are the
research's 2,529; with it, its 2,527 are the 2,527 of the research's own -200
test. The same game, side, book, line and price on every one (largest edge
difference 4e-16).

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.02 (P(win, push left out) minus the bet book's implied) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.02: the edge filter IS the card's cut | `ACTION_THRESHOLDS` |
| EV floor | 0.03, just under the smallest EV the cut admitted in the replay with the limit (+0.0343; median +0.059), on its own probability | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| price limit | -200, applied before the best book is chosen, and pinned | `models/ncaab_first_half_total.best_offer`, `MODEL_MIN_ODDS` |
| books | the eight above, and only those `BEST_LINE_BOOKMAKERS` still lists | `models/ncaab_first_half_total.BOOKS` |
| decision fetch | 55 to 60.5 minutes before tip, the tip-minus-60 call or its retries | `scripts/ncaab_first_half_total_card.DECISION_LEAD_MIN` |
| decided once | a row in `ncaab_first_half_total_decisions`, bet or not | the card |
| settlement | the first half's points against the line (period 1 of `ncaab_period_scores`); pending while the periods are missing or do not add up to the final | `tracking/paper_tracker.first_half_points` |
| closing value | not measured live: no fetch after tip minus 10, and the decision call is never read as its own close | `tracking/paper_tracker._closing_odds`, the CLV migration |
| kill switch | `RUN_NCAAB_FIRST_HALF=0` stops the fetches and both first-half cards | `scripts/ncaab_first_half_window.enabled` |
| frozen numbers | fitted on 2021-2026 | `models/saved/ncaab_first_half_total_2027.json` |

**The risks, plainly:**

- **It is one of many versions tried.** Round 5 graded 1,036 versions; 14
  cleared the interval test, where about 26 would with no edge at all. What
  sets this one apart: the same model is positive at every fetch time graded
  (15:00 UTC, 18:00 UTC, an hour before tip and ten minutes before) at every
  cut from 0.00 to 0.04, and this version is positive in all three seasons. Its
  lower bound is +0.57% (+0.45% with the limit), close to zero.
- **2025-26 was thin.** +1.85% on 818 bets (+1.65% with the limit), the
  weakest season. At cut 0.00 that season lost.
- **It beat the close by nothing.** Re-priced at the ten-minute close, its
  bets were worth -1.95% on average: the market did not move toward them. The
  profit is information the close lacks, not stale lines being corrected. Live,
  no close is taken, so closing value stays unmeasured.
- **It is an under card.** 1,969 of the 2,529 bets (78%) are unders (+67.84
  units); 560 overs made +57.93.
- **Hard Rock posts one first-half total a game at skewed prices.** It took
  397 of the bets, down to -240. Without it the version keeps +122.02 units.
- **The quotes' freshness is unverified.** The purchase stamped every quote
  with one snapshot time. Live, each book's own update age is stored on every
  decision.
- **Same-day period scores can be missing**, as for the first-half spread: a
  team's game with no stored halves is left out of its term and counted
  (`missing_halves`).

**Review at 50 settled bets** (gate standing, CLAUDE.md §2). Read the under
share and the book mix beside the ROI.

**Before the 2027-28 season** rebuild the frozen numbers: `python -m
scripts.ncaab_first_half_total_build --cache <copy of the three reads>
--last-season 2027` fits them; add `--quotes` and `--asof-fg` to replay too.

## Identity: ESPN owns the games row

`data/ingestors/ncaab_teams.py` is the contract every other piece reads.

- **Team ids are ESPN team ids**, held in `ncaab_teams` with the school name
  (ESPN's `location`), a slug, mascot, display name and conference, for every
  Division I school AND every non-D1 opponent ESPN lists. `games.home_team` is
  the school name; the slug only appears in the game id.
- **Game ids** are `NCAAB_<ET date>_<away slug>_<home slug>` in ESPN's
  orientation, written only by the ESPN ingestor. `ncaab_events` maps ESPN's
  event id to that game id with both ESPN team ids, and a postponed game keeps
  its id.
- **The odds feed never mints an NCAAB game.** Its events resolve onto ESPN's
  games by the UNORDERED team pair within a day of the tip
  (`ncaab_teams.make_resolver`). When the feed calls ESPN's away team home (a
  neutral court: ESPN shows 30 of 69 games neutral on 2026-11-25), the names
  are swapped before the outcomes are parsed, so the stored spread is ESPN's
  home number. Names resolve through ESPN's display name, "school mascot",
  school, short name, alternate names, a school that starts the name followed
  by its mascot, and last the feed's shortened school names (Feed team names,
  below). A name none of them places is dropped, counted, and fixed by an
  entry in `config.NCAAB_ODDS_API_MAP` (name -> ESPN id).
- Three-letter ids were never an option: the old fallback turned "Kentucky
  Wildcats" and "Kansas State Wildcats" into the same team (measured
  2026-10-26: `NCAAB_2026-11-03_WIL_WIL`).

## Feed team names (2026-10-29)

The odds feed shortens school names that ESPN spells out: "Michigan St
Spartans", "CSU Fullerton Titans", "Loyola (Chi) Ramblers". On 2026-10-29 82
feed names placed no team. The game-lines purchase (worker job 805227) keeps
every event it cannot place raw in `ncaab_odds_unmatched`, which then held
137,007 rows, nearly all because of those names. The job itself counted
137,083; the table keeps one row per event and feed time.

- **The rule** (`ncaab_teams._resolve_shortened_school`). It is tried only
  after every other step finds nothing, so a name that resolved before still
  resolves to the same team. The name is split into a school part and a
  mascot at every word. The school part's abbreviations are expanded (St, SE,
  Univ., CSU, Cal, Chi, Mt., BKN, Int'l; each one is there because a stored
  feed name needs it). The school part must then equal the school, short name
  or an alternate name of exactly one ESPN team, and the rest must be that
  team's mascot, or one of two aliases kept per team (Grand Canyon
  "Antelopes", Florida International "Golden Panthers"). The name resolves
  to nothing when two teams share that school and that mascot, or when two
  schools of the same length both start it (the step before this one; the
  rule is then not tried). A spelling two teams share places nothing by
  itself.
- **The overrides.** 20 names no rule can place are in
  `config.NCAAB_ODDS_API_MAP`, each with the ESPN team and how many of the
  name's events ESPN's schedule plays as that team: schools or mascots ESPN
  names differently ("Dixie State", "Houston Baptist", "IUPUI", "UMKC",
  "George Washington Colonials", "Valparaiso Crusaders", "Long Beach St
  49ers") and names unlike ESPN's ("Albany", "Fort Wayne", "Tenn-Martin").
  "LIU Brooklyn Blackbirds" is ESPN 112358, Long Island University, not the
  non-Division I row 6446 called "LIU Brooklyn": ESPN's schedule has all 19
  of its events under 112358.
- **Measured 2026-10-29.** Over 7,468 names, no name changed team from the
  resolver before this rule: every feed name in `ncaab_odds_unmatched` and
  every name form built from the ESPN registry (display name, school, short
  name and abbreviation, with and without the mascot, and the feed's
  contractions of each). 80 feed names now resolve, 60 by the rule and 20 by
  override, each to the team ESPN's schedule plays it as. Two stay unresolved
  on purpose: "Regent University Royals" and "Western State Colorado
  Mountaineers" each fit two ESPN rows.
- **The live capture uses the same resolver**, so these names now place from
  opening night too.

## Replaying the kept raw events

`python -m data.ingestors.ncaab_odds_history --replay-unmatched --seasons 2021 2026 --apply`
re-reads the events the purchase kept raw and stores the ones that resolve
now, as the game-line purchase would have stored them: ESPN's game, ESPN's home number,
the in-play label from ESPN's tip, and the same filter of what is kept (the
first quote, the evening-before and morning anchors, and the three hours
before the tip). It makes no paid call, never writes the pull ledger, never
deletes a raw row, and does not store a quote that is already stored, so a
second run stores nothing new. Each insert into `odds` also updates
`latest_odds`, through that table's insert trigger.

- **Without `--apply` it is a dry run** that prints what it would store, and
  its database connection is read only: every transaction opens READ ONLY.
- **The raw rows carry the feed's own time** (21:55:38Z for the 22Z
  snapshot). The replay maps each one back to the hour that was bought: the
  first pull-ledger hour at or after it, within an hour. A time with no such
  hour is counted and skipped. Stored rows carry each market's own last-update
  time as `snapshot_at` (the bought hour only when the feed sends none), as
  the purchase's rows do.
- **Two differences from the purchase.** A listing whose start is 12 hours
  or more from the ESPN game it lands on is not stored. The matcher takes the
  nearest game within a day either side, so a second listing of the same two
  teams a day later lands on the same game; in the kept events every such
  game also has a listing within the hour (24 events, 144 event snapshots;
  SQL on the Supabase connector, 2026-10-29). And when the feed answered
  several bought hours with the same stale snapshot, the raw table kept it
  once, so it is replayed only at the first of those hours (2020-11-27, 18Z
  to 20Z, the one case found).
- **A write cut off at its commit is retried safely.** Each write reads
  `odds` back before it inserts, so a retry after a commit that did land
  stores nothing twice.
- **On the worker:** job `ncaab_odds_history` with `{"mode":
  "replay_unmatched"}` stores (every purchased season, 2020-21 to 2025-26);
  `{"mode": "replay_unmatched", "dry_run": true}` only prints what it would
  store. It takes no credit limit because it spends nothing.
- **What to expect.** The 2025-26 dry run, read only, 2026-10-29 23:26Z to
  23:41Z: 1,260 raw feed times, all mapped to a bought hour; 24,914 event
  snapshots, of which 24,692 place on an ESPN game, 209 do not (31 team pairs
  ESPN has no game for) and 13 (2 events) are refused as far listings; 1,956
  events placed; 484,773 rows parsed, 59,867 of them in play; 256,684 kept,
  none already stored, so 256,684 would be stored. A placed event snapshot
  parses into about 20 rows and the keep filter keeps about half of them, so
  the replay stores far more rows than event snapshots. Across the six
  seasons, SQL on the Supabase connector (2026-10-29, the new name answers)
  places 11,349 of the 11,857 kept events on 11,300 ESPN games, before the
  24 far-listing events are set aside; the dry-run job prints the rest.
- **What it stored.** Worker job 827394, 2026-10-30 04:00-04:40Z, seasons
  2020-21 to 2025-26: 7,340 raw feed times, all mapped to a bought hour;
  137,007 event snapshots, of which 133,064 placed, 3,799 not (508 events)
  and 144 (24 events) refused as far listings; 2,239,062 rows parsed,
  245,242 of them in play; 1,201,028 kept and stored, none already stored,
  no write failed. Read back from `odds` (sport NCAAB, source
  `odds_api_historical`): 1,201,028 rows on 11,296 games, every game in
  `games`, no row after its game's tip.

## The opener grid (built 2026-10-30, not queued)

`python -m data.ingestors.ncaab_odds_history --opener-grid --step 30 --seasons 2021 2026 --dry-run`
prints what the grid would buy. **Nothing is queued.** The spend needs mike's
approval before a `worker_jobs` row is added.

- **Why.** The game-line purchase bought fixed hours: the evening before
  (22Z), mid-morning (15Z) and the hour before each tip. A book's first posted
  line is then dated only to the gap between two of those hours, and that gap
  is over two hours for 42% to 68% of first spreads and totals, depending on
  the book (41.6% for BetMGM totals to 67.6% for betPARX totals; the
  opener-route design, 2026-10-30, against the pull ledger). The grid buys
  the same bulk snapshot (moneyline, spread and total at the ten fetched
  books, 30 credits for the whole listed slate) at every clock time, every
  hour or every half hour, from 72 hours before each tip up to the tip. Each
  book's first post is then dated to the hour or the half hour.
- **Grid times are on the clock, not on the tip.** A 01:20Z tip wants 01:00Z
  and not 01:30Z; its window starts at the first grid time at or after 01:20Z
  three days earlier. One snapshot serves every game whose window holds it.
- **`--pre-start`** adds every grid time from 240 to 72 hours before each
  season's first tip, for boards posted before the first window opens: 168
  snapshots a season every hour, 336 every half hour.
- **What it costs** (the dry run on 2026-10-30, against ESPN's schedule and
  the pull ledger, both checked equal to production that day; 30 credits a
  snapshot):

  | Every | Grid times | Already bought | To buy | Credits | With `--pre-start` |
  |---|---|---|---|---|---|
  | 60 minutes | 21,710 | 7,403 | 14,307 | 429,210 | 15,315 snapshots, 459,450 credits |
  | 30 minutes | 43,415 | 7,403 | 36,012 | 1,080,360 | 38,028 snapshots, 1,140,840 credits |

  At the game-line purchase's pace (7,403 snapshots in 2 hours 40 minutes on
  2026-10-29) that is about 5 hours every hour and 13 hours every half hour.
  These are estimates from that one run, not measurements of this one.
- **What is stored.** Each book's first quote on each game and market, and
  every quote that differs from the one before it in price or line. A repeat
  is not kept, and an in-play price never is. Each row's time is the market's
  own last update, as the feed sends it. A book's first row is therefore the
  time it posted, unless it changed that line again before the first snapshot
  that shows it.
- **A quote already stored is not stored again.** The filter above only
  knows what the current run has seen. The game-line purchase stored its own
  hours' quotes before the grid existed, and the grid skips those hours as
  already bought. A run that stops and starts again also begins with an empty
  filter. So before writing, the grid reads `odds` back, as the replay does.
  A quote with the same game, market, book, feed time, prices and line is not
  stored again, whoever stored it first. `odds` has no unique index on a
  quote, so this read is the only thing that stops a second copy. It happens
  inside the write, so a retry after a dropped connection stores nothing
  twice. How many rows the grid stores is not measured. At most it is one row
  per game, market, book, feed time and quote.
- **Raw events.** Events that resolve onto no ESPN game are kept raw in
  `ncaab_odds_unmatched`, as the game-line purchase keeps them. The replay
  stores those with the game-line purchase's filter, which keeps every
  snapshot in the three hours before the tip. So a replay of grid events can
  store a price there again under a later feed time, where the grid itself
  would not.
- **Where a bought time is recorded.** A time on the hour goes in
  `odds_history_pulls`, keyed on (sport, date, hour), exactly as the game-line
  purchase records it. So an hour either one bought is never bought again. A
  half hour goes in `odds_history_fetches`, keyed on (sport, exact time),
  with `why = 'opener_grid'`. That is the table the NBA purchase already uses
  for its off-the-hour times, and every NBA reader of it filters on sport.
  The shared ledger's key is not changed. Every sport's history purchase
  writes to it naming those three columns, so a different key would make
  any copy of that code pay for a snapshot and then lose it. The replay of
  kept raw events reads both tables, so a feed time of 22:25 maps to the
  22:30 snapshot, not to 23:00.
- **The floor.** The same 300,000-credit floor as the other purchases, and
  its own ceiling (1,170,000, the half-hour grid with the pre-start window
  plus room for calls billed above 30). Before its first call it reads the
  newest balance on record (`odds_api_quota`) and refuses to start without
  one, so the first call is checked against the floor too.
- **On the worker, once approved:** job `ncaab_odds_history` with
  `{"mode": "opener_grid", "step_min": 30, "max_credits": N, "floor":
  300000}`; add `"pre_start": true` for the pre-start window and
  `"seasons": [2024, 2026]` to narrow the seasons. `{"mode": "opener_grid",
  "step_min": 30, "dry_run": true}` prints the plan against production and
  buys nothing.

## Paid calls side by side (2026-11-02)

The opener grid and every first-half purchase (open, close and the three
game-day times below) send up to 6 paid calls at once by default, at most 10.
One at a time, the grid bought about 48 snapshots a minute (job 936020).

- **Only the calls run side by side.** Every database write, the parsing,
  the filters on what is stored and the credit count stay in one place, and
  each answer is handled in the order it was asked for. So what is stored is
  what a one-at-a-time run stores.
- **The floor still holds.** Before every call, the job counts each call
  still waiting for an answer at its most (30 credits for a grid snapshot, 40
  for a game's first-half call). A call is sent only if all of them together
  stay above the 300,000 floor and under the job's limit. Until the balance
  is known, calls go one at a time. Answers can arrive out of order, so the
  job keeps the lowest balance any answer reports. A run still going when
  the monthly refill lands (about 00:00 UTC on the 1st) keeps the old, lower
  number and may stop at the floor early. That is a stop too soon, never a
  spend under the floor; running the job again picks up the new balance.
- **Rate limits.** The feed asks for requests to be spaced out when it
  answers 429. Every call then pauses together (2 seconds, doubling to at
  most 30), the call is asked again, and one fewer call runs at once; 100
  answers in a row without a 429 add one back. The run's report counts the
  429s (`rate_limited_429`).
- **The setting.** Job arg `"concurrency": N` (1 to 10) on the grid and the
  first-half modes; a job that names none runs at 6. That includes a job the
  queue runs again after a redeploy, such as the grid's job 936020, whose
  stored args name none. On the command line, `--concurrency N`.
- **A rerun buys nothing twice.** The grid's plan skips every time either
  ledger holds, hours and half hours. Checked 2026-11-02 23:43Z: the grid's
  dry run counted 11,825 times already bought, between the ledgers' 11,821
  and 11,826 rows at the start and end of that read, with 31,590 left
  (947,700 credits). Each time is read against the ledger again just before
  its call.

## First-half lines and team totals at three game-day times (built 2026-11-02)

The stored first-half and team-total lines are at two times only: the open
(the evening before, or 20 hours before the tip) and the close (10 minutes
before the tip). mike approved three more times on 2026-11-02. The code is
built; **nothing is bought until a worker job is queued.**

- **What is bought.** The same as the open and the close: one call per game
  for the first-half moneyline, spread and total and the team totals at the
  ten fetched books. The feed bills 10 credits per market it returns, so at
  most 40 a game. An empty answer and a "not found" are free. Each game
  date also costs one event list (1 credit), which names each game's event.
- **The three times.** The game's date is ESPN's, which is the Eastern date
  of the tip (all 18,836 games of 2023-24 to 2025-26, read 2026-11-02).

  | Time | Games bought | Stored under source | Job mode | Most it can spend | Measured ceiling |
  |---|---|---|---|---|---|
  | 15:00 UTC on the game's date | those that tip after 15:00 UTC (18,816 of 18,836) | `odds_api_ncaab_derivative_15z` | `deriv_15z` | 700,000 | 687,686 |
  | 18:00 UTC on the game's date | those that tip after 18:00 UTC (17,173) | `odds_api_ncaab_derivative_18z` | `deriv_18z` | 650,000 | 628,965 |
  | 60 minutes before the tip | every game with a tip (18,836) | `odds_api_ncaab_derivative_tip60` | `deriv_tip60` | 700,000 | 689,286 |

  A game that tips at or before 15:00 or 18:00 UTC is skipped at that time,
  because its price there could be in play. It is never listed for and never
  costs a credit. The measured ceiling is 40 credits for each game whose
  full-game line was already listed at that time, plus 1 for each date
  (2026-11-02, from the stored full-game lines and the billing log: 17,181
  games and 446 dates at 15:00, 15,713 and 445 at 18:00, 17,221 and 446 at
  60 minutes). The dry run prints a higher figure, 40 for every game with
  that time, because it cannot know which games the feed lists. A game the
  feed does not list costs nothing, and the job's own limit caps the spend.
- **Each time is its own source.** So each resumes on its own: a game
  already holding rows under that source is not bought again, and a later
  read can tell the times apart. All three are protected from the odds
  clean-up, like the open and the close (`data/prune_odds.py`).
- **Newest date first, the same floor.** The same credit meter as the other
  purchases: the job stops before a call would cross its own limit, or take
  the balance under the 300,000 floor.
- **The test buy** (`deriv_15z_test`) buys 50 games at 15:00 UTC, at most
  2,050 credits (50 x 40, plus at most 50 event lists). It answers whether
  the books post first-half lines by 15:00 UTC before the full 15:00 buy is
  spent. Its rows are stored under the full buy's source, so the full buy
  skips them later.
  - **How the 50 are chosen.** The games are split by season and by Eastern
    tip time (before 1pm, 1-4pm, 4-7pm, 7-9pm, 9pm or later): 15 groups,
    each with at least 264 games. Each group is ordered by a fixed hash of
    the game's id, and the groups take turns, so each gives 3 or 4 games.
    Only games with a stored close are drawn, so no slot goes to a game no
    book ever priced. The hash, not a random draw, means a re-run picks
    the same 50 and buys none of them twice.
  - **What it prints**, read back from `odds` after the buy: for each book
    and each market (first-half moneyline, spread, total, home and away team
    totals), how many of the 50 games hold a quote at 15:00 UTC, beside how
    many hold one at the close. Then, for any book, the same by tip time.
    It prints last, so the worker's copy of the output keeps it.
- **Commands.**
  - Test buy, dry run (read only, no call):
    `python -m data.ingestors.ncaab_odds_history --derivatives 15z --sample 50 --seasons 2024 2026 --dry-run`
  - Test buy: the same with `--apply --max-credits 2500 --floor 300000`.
  - A full buy: `--derivatives 15z` (or `18z`, `tip60`) `--seasons 2024 2026`,
    with `--apply --max-credits 700000 --floor 300000` (650000 for `18z`).
    Without `--apply` it is a dry run.
- **Worker jobs** (job type `ncaab_odds_history`):

  | Buy | Args |
  |---|---|
  | Test buy, 50 games at 15:00 UTC | `{"mode": "deriv_15z_test", "max_credits": 2500, "floor": 300000}` |
  | Full 15:00 UTC | `{"mode": "deriv_15z", "max_credits": 700000, "floor": 300000}` |
  | Full 18:00 UTC (from 2026-12-01) | `{"mode": "deriv_18z", "max_credits": 650000, "floor": 300000}` |
  | Full 60 minutes before the tip (from 2026-12-01) | `{"mode": "deriv_tip60", "max_credits": 700000, "floor": 300000}` |

  Any of the four with `{"mode": ..., "dry_run": true}` and no limits prints
  the plan against production and makes no call. Each purchase runs 6 calls
  at once unless its args name `"concurrency"` (Paid calls side by side,
  above).
- **The test buy's dry run, 2026-11-02** (read only, against production):
  50 games on 45 dates, at most 2,045 credits; by season 16, 17 and 17 (2024,
  2025, 2026); every group gave 3 or 4. The stored close holds a quote for
  all 50 on at least one first-half or team-total market (49 of 50 on the
  first-half moneyline). Nothing is stored at 15:00 UTC yet.
- **The same snapshot under two times.** A 2pm Eastern tip in winter is at
  19:00 UTC, so 60 minutes before it is 18:00 UTC. 1,683 games have the same
  time for the 18:00 buy and the 60-minute buy, and 120 (11am Eastern tips)
  for the 15:00 buy and the 60-minute buy (2026-11-02). Each buy asks for
  that snapshot under its own source, so it is paid twice, up to 40 credits
  a game. One game's close falls on 18:00 UTC; none on 15:00 UTC.
- **63 games carry a 23:59 Eastern tip** in ESPN's schedule (2023-24 to
  2025-26). Some may be ESPN's placeholder for a time not yet set. At 15:00
  and 18:00 UTC that changes nothing. For the 60-minute buy it would set the
  wrong time, as it already does for the close. Not checked game by game.

## What runs, and where it lands

| Piece | What | Where |
|---|---|---|
| ESPN schedule + results | Teams, venues, every game (neutral flag, conference game), finals for settlement; the daily pipeline refreshes 14 days ahead, every refresh pass fills finals for started games | `data/ingestors/ncaab_espn_ingestor.py`, steps `ncaab-schedule` / `ncaab-results` |
| Live odds | Full-game moneyline, spread and total from the ten line-shop books on every refresh pass; NCAAB is exempt from the DraftKings-must-list gate so every book's first post is kept | `data/ingestors/odds_ingestor.py` |
| Totals model card | Hourly at five past, UTC: decides each game once at DraftKings' standing total (22:00 UTC the evening before, else 15:00 UTC on the day and each hour to tip), writes the bets, then publishes them | `scripts/ncaab_total_card.py`, job `ncaab_total_card` |
| First-half spread model and capture | Every minute: each listed game's first-half lines (moneyline, spread, total, team totals) at 15:00 UTC on its date and 180, 120, 60, 50, 40, 30, 20 and 10 minutes before tip, at most 4 credits a call; the first-half spread model decides each game once on the tip-minus-10 fetch and the first-half total model on the tip-minus-60 fetch, each writes its bets, then the job publishes them | `scripts/ncaab_first_half_window.py`, `data/ingestors/ncaab_first_half_odds.py`, `scripts/ncaab_first_half_spread_card.py`, `scripts/ncaab_first_half_total_card.py`, job `ncaab_first_half_window` |
| Opener capture | Every 5 minutes, change-only (a row is written only when a book's price or line moved), so the time each book first posts is known | `scripts/ncaab_odds_capture.py`, job `ncaab_odds_capture` |
| Price-path retention | NCAAB keeps every book's whole price path (the clean-up job only removes unchanged middles), and the close it keeps for any sport is the last price before the start | `data/prune_odds.py` (`PATH_KEPT_SPORTS`) |
| Paid history | Game lines 2020-21 → 2025-26 (bulk snapshots: the evening before, mid-morning, and the hour before every tip); first-half and team-total lines 2023-24 → 2025-26, opener and close; the same at 15:00 UTC and 18:00 UTC on game day and 60 minutes before the tip (built 2026-11-02, bought only by a queued job; First-half lines and team totals at three game-day times, above). Unmatched events are kept raw in `ncaab_odds_unmatched`, never dropped | `data/ingestors/ncaab_odds_history.py`, job `ncaab_odds_history` |
| Free history | Prediction Tracker lines and systems 2004-26, SBRO lines 2007-21 (matched onto ESPN games by date and final score), NCAA possession box scores and season player minutes 2010-26 | `data/ingestors/ncaab_archive_import.py`, `ncaab_sdv_import.py` |
| Feed probe | Which NCAAB events the odds feed lists and which names fail to resolve; which markets each book prices; whether the football data key opens College Basketball Data | `scripts/ncaab_feed_probe.py`, job `ncaab_feed_probe` |
| Pre-tip injuries | RotoWire's public injury JSON about every 10 minutes, every 5 while a game tips within three hours; Covers' public page about every 30 minutes as the fallback. Change rows, including a `cleared` row when a listed player leaves a non-empty report. Tags only | `data/ingestors/ncaab_injury_feed.py`, job `ncaab_injury_feed`; reachability `scripts/ncaab_injury_probe.py`, job `ncaab_injury_probe` |
| Replay of kept raw events | Stores the kept raw events that resolve now; no paid call (Replaying the kept raw events, above) | `data/ingestors/ncaab_odds_history.py --replay-unmatched`, job `ncaab_odds_history` mode `replay_unmatched` |
| Box and period scores (2026-27 on) | Each final's team box score into `ncaab_team_game_stats` (source `espn_summary`) and its half and overtime scores into `ncaab_period_scores`, one ESPN game summary per final, on the hourly refresh passes after the results step (Box scores and period scores, below) | `data/ingestors/ncaab_espn_box.py`, step `ncaab-box`; backfill job `ncaab_box_backfill` |
| Opener grid (built, not queued) | Game lines every hour or half hour from 72 hours before each tip, so each book's first post is dated to the step (The opener grid, above) | `data/ingestors/ncaab_odds_history.py --opener-grid`, job `ncaab_odds_history` mode `opener_grid` |

## Box scores and period scores (ESPN, from 2026-27)

**Why.** The rating models refit on `ncaab_team_game_stats`: possessions,
points, shooting, rebounds and turnovers per team per game. Until
2026-10-30 its only source was the sportsdataverse season files (NCAA's own
play-by-play), which have no 2026-27 file and no in-season build. ESPN's free
game summary carries the box score, so the table now fills as the season is
played. `data/ingestors/ncaab_espn_box.py` is the writer.

**What it stores, per final game, in one transaction:**

- Two rows in `ncaab_team_game_stats` with source `espn_summary`.
  `contest_id` is `espn:<ESPN event id>`; NCAA's contest ids are digits only
  (all 188,424 rows, 2026-10-30), so the two sources never share a key.
  `team` is the school name `games` carries. Filled: points for and against,
  FGA, FGM, 3PA, 3PM, FTA, FTM, offensive and defensive rebounds, turnovers,
  assists, blocks, the game's length in `mins` (40, plus 5 per overtime),
  ESPN's team and event ids and the possession estimate below. Left empty,
  because ESPN has no equivalent: shots at the rim, `e_poss`,
  `time_per_poss` and NCAA's team id.
- One row per period in `ncaab_period_scores`: periods 1 and 2 are the
  halves, 3 and later the overtimes, in the stored home/away orientation.
  `source` names the ESPN endpoint (`espn_summary` here, `espn_scoreboard`
  from the backfill).
- A game it will not store gets a row in `ncaab_box_misses` instead: the
  reason and the attempt count.

**When it runs.** Step `ncaab-box` on the hourly refresh passes, at :17
from midnight to 5 am and from 7 am to 5 pm ET, after the `ncaab-results`
step that writes the finals it reads (and after settle, since nothing settles
off it). Not on the 10-minute evening passes (6 to 11 pm ET): those already
take 455-526 seconds (median and 90th percentile, `pipeline_runs`, 7 days to
2026-10-30) of their 600-second tick, and a pass that overruns makes the next
one skip. The evening's finals are stored from the 12:17 am pass on; nothing
reads them sooner. It looks at the finals of the last 3 ET dates that have
no `espn_summary` row, newest first. A pass takes at most 80 games and about
150 seconds of fetching (checked before each call), one request at a time
with 0.3 seconds between them; the rest wait for the next pass. With nothing
due it makes no ESPN call.

**The possession estimate.** ESPN's summary has no possession count, so
`o_poss` is each team's box-score estimate, FGA − offensive rebounds +
turnovers + 0.475 × FTA, and `d_poss` is the opponent's (one team's `o_poss`
is the other's `d_poss`, as in NCAA's rows). It is NOT NCAA's play-by-play
count. Against that count in 2020-21 to 2025-26 it runs 0.30 to 0.46
possessions a team-game below it (the mean, by season), with a mean absolute
gap of about 1.2 a team and a correlation of about 0.967; averaged over the
two teams of a game the correlation is 0.978 and the gap about 1.0. Given to
the frozen rating model in place of NCAA's count it left totals error where
it was (13.638 against 13.644 points, 2012-19). Measured in the NCAAB
research round (`poss_agreement.csv`, `poss_substitution.csv`, 2026-10-30);
the per-team figures were measured the same day on the research copy of the
stored NCAA rows (188,424 rows, 2010-11 to 2025-26).

**Two sources, one game.** If a game is ever held under both sources (for
example a sportsdataverse 2026-27 file appears), it has two pairs of rows
with the same `espn_game_id` and different `contest_id`. Keep one source per
game, both of its rows, NCAA's where it holds the game. This query keeps
every row of the table today (188,424 of 188,424, read 2026-10-30) and runs
as printed on Postgres and in the tests:

    SELECT * FROM (
      SELECT s.*, RANK() OVER (
               PARTITION BY COALESCE('espn:' || s.espn_game_id, s.contest_id)
               ORDER BY (s.source = 'sportsdataverse_ncaa') DESC) AS source_rank
        FROM ncaab_team_game_stats s) ranked
     WHERE source_rank = 1;

Two traps it avoids:

- **Older seasons have no `espn_game_id`.** NCAA's rows carry none before
  2022-23 (138,338 of 188,424 rows). A query that requires one keeps only the
  last four seasons, without an error. The game key is the ESPN id where the
  row has one and the `contest_id` where it does not.
- **A non-Division I team has no `team_espn_id` in NCAA's rows** (8,854 rows),
  and this feed fills it (Hawaii Pacific is 2269). A query keyed on the team id
  would keep three rows of such a game, NCAA's two and ESPN's row for that
  side. To match one side across the two sources, use the game and `pts`.
  No game ends level, and the two sources' points agreed on every row
  compared. Not the team id: in 31 of NCAA's 25,054 games from 2022-23 on,
  neither row has one. Not `is_home`: at neutral sites the two sources can
  disagree (below).

A reader that matches on date and team pair and drops duplicate keys (the
research prep does) would lose such a game rather than choose, so choose the
source first.

**Four more columns follow each source's own rules.** Measured 2026-10-30 on
2025-26, NCAA's rows joined to the stored events and games (12,047 team rows):

- `team`: this feed writes the name `games` carries ("Arizona State"), NCAA's
  rows carry NCAA's ("Arizona St."). They differ for 121 of 365 schools. Key
  a team on `team_espn_id`, never on `team`.
- `is_home`: this feed follows the stored event, NCAA its own home team. At
  neutral sites they disagree: 74 rows, 37 games, every one neutral.
- `game_date`: this feed uses the ET date from `games`, NCAA its own. Tips at
  03:59Z or 04:59Z land a day apart: 48 rows, 24 games.
- `mins`: this feed writes 40 plus 5 per overtime, NCAA the measured playing
  time (season means 39.50 to 39.69). A pace per 40 minutes moves about 1%
  across the boundary between the sources.

`ast` and `blk` are stored as ESPN reports them. In a 10-game check against
NCAA's rows, assists matched on 20 of 20 team rows and blocks on 19 of 20.

**What it refuses.** A summary that is not final, names other teams than the
stored event, or lacks any of the shooting, rebound or turnover numbers; a
box whose points are not 2 × FGM + 3PM + FTM; an ESPN final that differs
from the stored one (the stored final settled the picks); period scores that
do not sum to the stored final, differ in count between the teams, or
disagree with `went_to_ot`. Nothing of a refused game is stored. It is tried
again after 50 minutes, at most 6 times. A 404 for a game is a miss. A 403
or 429 stops the pass's run and turns the step red, since ESPN has blocked
the worker before. So does the first fetch that fails outright (no answer
after the fetch's own retry): the next pass is the retry, so an ESPN outage
costs one fetch a pass, about 46 seconds at worst. The season backfills stop
after three.

**When every game is refused.** If ESPN changes its game summary (a renamed
statistic, a moved endpoint), every game is refused, and each one alone is
only a miss. So after each pass the step counts the newest finals of the
3-date window that ESPN answered for and that were refused, back to the
newest one stored. Five in a row turns the step red (`espn-box-refused` in
the log, the step named in `pipeline_runs`). It stays red on every pass,
including passes with nothing due, until a game is stored again. Counted from
the stored rows, it catches a break that arrives one game a pass, and it
stays green while an occasional bad game is retried behind newer stored ones.
The refused games use up their 6 attempts meanwhile; once the cause is fixed,
the box backfill (`--box`, or the `ncaab-box-scores-2027` declaration
switched on) fetches them again, ignoring the misses.

**Measured 2026-10-30, 25 games of 2025-26 (`summary?event=`).** Every call
answered 200 in 1.00 s on average (max 1.12 s), 447-566 KB each. On the 49
team rows NCAA also holds, every one of points, FGA, FGM, 3PA, 3PM, FTA,
FTM, offensive and defensive rebounds and turnovers matched NCAA's number;
points = 2 × FGM + 3PM + FTM and the periods summed to the final on all 50.
One scoreboard date (2026-02-07, 155 events) carried every period,
overtimes included, and every completed side's periods summed to its score
(310 of 310).

**Backfill.** `python -m data.ingestors.ncaab_espn_box --periods --seasons
2021 2026` reads one scoreboard per date and stores the period scores of
every final with none (855 dates, 35,323 finals in 2020-21 to 2025-26,
counted 2026-10-30). `--box --seasons 2027 2027` fetches a summary for every
2026-27 final with no ESPN box row. Both skip what is stored. On the worker:
job `ncaab_box_backfill` with `{"kind": "periods", "first": 2021, "last":
2026}` or `{"kind": "box"}` (box is held to 2026-27, the season NCAA's files
do not cover). Both are declared in `jobs/declared_jobs.json`.
`ncaab-period-scores-2021-2026` ships ON (mike, 2026-10-30), so the worker
queues it once on its first tick after the merge. `ncaab-box-scores-2027`
ships off. Turning it on is one line: set `enabled` to true and merge. No test
pins either switch, and the NCAAB credit-approval test leaves this free job
out. The ESPN schedule backfill made the same kind of calls on the worker on
2026-10-28/29: 17 seasons, one scoreboard per date, about 13 minutes a season,
all 17 done.

**The research round's halves file.** It held first- and second-half scores
for 36,796 ESPN events of 2020-21 to 2025-26, on one laptop only. It is not
imported: it keeps the two halves and a period count but not each overtime's
score, and it was built by a script outside the repo. The period backfill
re-reads the same ESPN scoreboards through the repo's own code, so every
stored row names its endpoint.

## In the app (2026-10-30)

- **NCAAB is a sport chip beside NCAAF** on the Picks, Models and Stats tabs
  (`mobile/src/hooks/useSportFilter.ts`). A push that names NCAAB opens its
  board, because the push router accepts only the sports on that list.
- **A model whose id starts `ncaab` is filed under NCAAB.** Before this, the
  app had no `ncaab` prefix and filed every such model under MLB
  (`modelMeta.sportOfModel`, and its copy in `ModelsScreen`).
- **The totals model's label is "NCAAB Totals", badge O/U, under the id
  `ncaab_total_blend`**, the id the model writes its picks under
  (`models/ncaab_total_blend.py`). The app first used `ncaab_over_under`, the
  id in the model's build plan; no model writes that id. If config scores an
  id the app has no label for, `tests/test_mobile_pick_categories.py` fails.
- **It is priced off the `totals` rows because it is named.** An id with
  `over_under` in it reaches the totals rows on its own; `ncaab_total_blend`
  does not, so `markets.gameMarketForModel` names it (else every price,
  movement and line-shop lookup reads the moneyline rows), and so does
  `marketClassForModel` (else a parlay treats it as independent of the same
  game's other legs).
- **Its page and its picks say when it decides.** The model page says it
  decides each game once, the evening before, at DraftKings' total, and that a
  posted bet is never re-priced (`modelMeta.modelPageTiming`). It prints no
  Eastern clock time: the card runs at 22:00 UTC, which is 6pm ET until
  1 November and 5pm ET after it. Pick Detail says "Posted" once, not "the
  first scoring run of the day" (`markets.pickTimingInfo`). A row for a game
  that is not today shows its day as well as its time, as the Signals card
  does.
- **The Today board reads NCAAB picks up to 7 days ahead**
  (`fetchUpcomingNcaabPicks`), because the totals model decides the evening
  before the game. It reads the picks first, then only those
  picks' games and lines, 80 game ids per request. Reading the whole window
  instead would have been too big: over 2025-26 the biggest day held 4,417
  main-market rows across all books, and the biggest seven days held 10,424
  (Supabase, read only, 2026-10-30).
- **Today's DraftKings lines are read in pages, main markets only.** The
  same-day read was one request, and a full college basketball day went past
  the 1,000-row response cap: 1,132 DraftKings rows for 2026-01-10, of which
  743 were in the markets a pick reads. Past the cap the server returns an
  arbitrary 1,000 rows without saying so, which could blank any sport's line
  pill.
- **When a game leaves the board.** Three hours after the tip if ESPN's final
  has not landed by then (`format.GAME_DURATION_HOURS`); it stops reading
  LIVE on the clock alone after four (`BLIND_LIVE_WINDOW_MS`).
- **Stats tab, Players board (Matt, 2026-11-03).** Men's college basketball
  player stats: Points, Rebounds, Assists, 3PM, PRA, Steals, Blocks, Minutes,
  with Hit Rates (H2H, L3, L5, L10, season) and Averages, the WNBA set.
  Source `ncaab_player_game_log`, one row per player per game from ESPN's
  game summary `boxscore.players` (`data/ingestors/ncaab_player_box.py`). The
  team box feed hands over the summary it already fetched, so a new final
  costs no second call; the `ncaab-box` step's catch-up and the
  `ncaab-player-box-2026-2027` job (kind `players`) fetch games with no
  player rows. A team whose players' points do not sum to the stored final is
  refused (`ncaab_player_box_misses`). Reads: `v_player_season_totals_ncaab`,
  `player_window_totals_ncaab`, `player_recent_games_ncaab`,
  `player_season_stat_values_ncaab`, `player_h2h_stat_values_ncaab`
  (`add_ncaab_player_game_log_2026_11_03.sql`). No player-prop line column:
  Matt, 2026-11-03, "Don't include those". Season label is the ending year
  (`boardSeasonET`). Not built yet: the Teams board, the same-position card
  on the player page (no college position source), team names abbreviated.
- **Not in the app yet.** NCAAB team stats. School abbreviations: cards show the
  school name, because the app cannot read `ncaab_teams` (anon has no SELECT
  on it, RLS is on and it has no policy; read only, 2026-10-30). Opening it is
  a worker-side change as well as an app one: the code that creates the table
  (`data/ingestors/ncaab_teams.py`, `ensure_tables`) re-runs its create and
  lock-down whenever it finds anon holding a grant, so a grant alone would be
  revoked the next time that runs. Every school name on the games from 1 to
  8 November matches `ncaab_teams.school` (492 of 492). Nine school names
  appear twice in `ncaab_teams`, six of them with two different
  abbreviations, so those six must keep the school name. Live scores and the
  Scoreboard: the live scoreboard poller (`data/ingestors/live_scoreboard.py`)
  does not cover NCAAB.

## Data accounts and sources (measured 2026-10-28)

- **cbbdata (Torvik's API).** Account created 2026-10-28 (mike: "articulate the
  cbbdata sign-up with your email") and re-registered 2026-10-29 under the
  dedicated sign-up mailbox (mike: "change email for signups"): username
  `signalbaseskinny`, no confirmation e-mail required; the first account
  (`malkatrazz`, personal Gmail) is superseded and its values are kept as
  `CBBDATA_OLD_*`. The password and API key are in the local `.env` as
  `CBBDATA_USER`, `CBBDATA_EMAIL`, `CBBDATA_PASSWORD`, `CBBDATA_API_KEY`, and
  on the Railway worker since 2026-10-29 about 22:58Z (names checked with
  list-variables). Calls are
  `https://www.cbbdata.com/api/<endpoint>?key=<key>&year=2025&team=Duke` and
  return Parquet. Measured: `torvik/ratings/archive` holds daily T-Rank
  ratings for 364 teams per date for the seasons 2014-15 → 2024-25 (2024-25:
  232 dates, 2024-11-02 → 2025-06-30, 84,383 rows; columns rank, team, conf,
  record, barthag, adj_o, adj_d, adj_tempo, wab, proj_record, date, year);
  `torvik/ratings` holds season-end ratings 2008 → 2025; `torvik/game/stats`,
  `torvik/game/factors` and `torvik/player/game` answer for 2024-25;
  `torvik/team/schedule` is 404 and `torvik/game/prediction` 500. **The
  2025-26 season (`year` 2026) returned zero rows everywhere** — the API has
  no current-season Torvik data as of 2026-10-28, the package's issue tracker
  has had "No Bart Torvik Data for 2025-26 Season" open since 2025-11-11 with
  no maintainer reply, and two independent projects report the API stopped
  updating after June 2025, so nothing says it will return. The archive serves
  backtests; current-season ratings come from Torvik's own season file
  (`https://barttorvik.com/2027_team_results.csv`, HTTP 200 on 2026-10-28),
  which his robots.txt lets general agents fetch (Load-bearing facts below).
  Terms of use: none exist in writing for cbbdata or for Torvik's data; mike,
  2026-10-29: no permission requests to any data source.
- **KenPom.** The API subscription is $145.00 for 12 months with web access;
  web-only is $24.95 and has no data feed (live pages read 2026-10-28 23:34Z;
  the API page read $95.00 in June 2026). mike buys it in his own browser
  under the sign-up mailbox; the key then goes into the local `.env` and the
  worker as `KENPOM_API_KEY`, and the checks in the hand-off doc run. Eleven
  endpoints, the daily archive and preseason ratings included; no player
  availability. No permission request (mike, 2026-10-29).
- **College Basketball Data (api.collegebasketballdata.com).** Matt's
  question, answered by the feed probe on the worker (`ncaab-feed-probe-2026-10-26`,
  2026-10-28 23:25Z): **the football data key opens it.** `/teams` season
  2027 → 365 records; `/games` 2026 Duke → 38; `/lines` 2026 Duke → 38 with
  providers ESPN BET, Bovada, DraftKings, consensus, teamrankings,
  numberfire; `X-CallLimit-Remaining` 121,421. Lines coverage by season,
  plays, lineups and substitutions are unmeasured — the next probe.
- **The odds feed, first look (same probe).** 7 NCAAB events listed for
  2026-11-01 → 11-03; every one of 7 books prices h2h, spreads and totals;
  FanDuel also listed first-half, second-half, team-total, alternate and
  player-points markets on one game; BetRivers and Hard Rock alternate lines
  and odd/even; William Hill first basket. 14 of 14 feed names were
  unresolved only because the ESPN registry was still empty (the schedule
  job runs after the probe).
- **First night, measured 2026-10-28 23:36Z.** 747 ESPN teams and 3,491 games were stored within six minutes of the schedule job starting; the 5-minute capture resolved all 7 listed feed events onto ESPN rows (one of them flipped: the feed's "High Point @ Liberty" is ESPN's `NCAAB_2026-11-01_liberty_high-point`) and `latest_odds` held 143 prices from 7 books.
- **The purchase floor is 300,000 credits** (lowered from 500,000 on
  2026-10-28, mike: "dont stop the spend"): 3.5 of October's worst organic
  days (84,534 on 2026-10-04, `odds_api_quota`). The refill lands between
  the last day's 23:50Z reading and roughly 01:00Z on the 1st (Sept and Oct
  both show a full day's burn by the 1st's 23:40Z reading), so the resumes
  fire at 06:00Z–06:20Z on 2026-11-01 with 2026-11-02 copies as backstops.

## Load-bearing facts

- **Sign conventions.** `scored_line` / `spread_home` is the HOME number
  (CLAUDE.md §4). The Prediction Tracker's sign is the reverse (+3 means home
  favoured); the importer stores `-line`.
- **SBRO's second-half score is regulation only.** Grading a second-half total
  on it shows a phantom under edge (46.25% overs, against 50.04% with overtime,
  SBRO 2015-19).
- **Overtime** happens in about 6% of games: in full-game and second-half
  markets, never in first-half ones.
- **Player availability tags** come from RotoWire's public injury JSON, with
  Covers' public page as the fallback (`data/ingestors/ncaab_injury_feed.py`).
  A row is stored when the status changes, including `cleared` when a listed
  player leaves a non-empty report. `injury_tags_before_tip` is the status at
  or before tip, for a tag. On a game day an empty report fails the tick
  only for the source those tags are using. An empty Covers poll while
  RotoWire listed players is a warning. It is not a model feature. A team or player the
  NCAAB resolver and the override maps cannot place is logged and not guessed.
  Official conference reports still cover conference games only.
- **Torvik's robots.txt** (read 2026-10-29) bars six named crawlers, ClaudeBot
  and anthropic-ai among them, from the whole site, and every agent from the
  time-machine pages, `db.php`, `box.php`, `results.php`, `playerstat.php`
  and `.json` files; general agents may fetch the season CSVs with a
  10-second crawl delay. cbbdata holds nothing after 2024-25. The headline
  projection in his schedule files is rewritten after games (61.8% against
  the line in 2025-26) and must never be used.
- **College player props** are barred in 13 states (Unabated, 2026-07-29).
