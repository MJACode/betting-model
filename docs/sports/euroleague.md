# EUROLEAGUE — data, odds capture, models

> **Started 2026-11-12** (mike: *"build the euroleague model. all markets
> including 1h and 1q"*), built with the league-models skill. The sport code is
> `EUROLEAGUE`. Season label: the ENDING year (2026-27 is 2027); EuroLeague's
> own code is the starting year (E2026), and the label is threaded from that
> code, never from a date. **Five models are live: the halftime spread,
> `euroleague_live_spread_ht` (2026-11-13, mike: "yes", knowing it misses part
> of the research bar; "Halftime spread" below), and four pre-game rules
> (2026-11-14, mike: "I told you to build all the models", knowing each misses
> part of the bar; "The four pre-game rules" below).** A fifth pre-game rule,
> the big-favourite moneyline, was removed before it went live (below). The
> rest of this file is the groundwork, the market grid and the purchase.

## What the sources hold (measured 2026-11-12)

| Source | What it holds |
|---|---|
| The odds feed, key `basketball_euroleague` | History from the 2020-21 season (nothing at 2020-06-15; 15 games listed at 2020-10-15). Its event lists, read every second day 2020-09-01 to 2026-11-12, named 2,164 distinct games: 344, 310, 330, 331, 331, 408 and 110 by season (2020-21 to 2026-27 so far; a game moved to another date counts twice there). |
| Its snapshots | One every **5 minutes** on a game day from 2022-23 on (288 on 2022-12-08 and 2025-12-11), every **10 minutes** before that (144 on 2021-03-11; 10 minutes apart on 2021-12-09 and 2022-03-10, 5 minutes on 2022-10-13). A day with nothing moving holds none (2025-12-13). Asked at 05:59, 11:59, 17:59 and 23:59 UTC of every day, a snapshot dated that day answered on 242, 209, 194, 209, 209 and 232 days of the six finished seasons, and 80 of 2026-27's first 104 (8,964 credits, `el_probe7`). |
| Its books (five history snapshots, every region) | 20 books on 2021-03-11, 26 on 2022-12-08, 37 on 2023-12-07, 32 on 2024-12-12, 51 on 2025-12-11. DraftKings priced 8 of 9, 8 of 9, 9 of 9 and 10 of 10 games from 2022-23 on and none in 2020-21; Pinnacle 7, 4, 8, 9 and 10; Bovada on most; FanDuel, BetMGM, BetRivers and Fanatics only in 2025-26. Marathonbet, Unibet and Paddy Power priced every sampled game of every season. **Caesars, Hard Rock and betPARX priced none.** On 12 game days a season read at noon UTC: DraftKings held a moneyline, spread and total on 42 of 42, 49 of 51, 47 of 47, 46 of 46, 61 of 61 and 52 of 52 same-day games, 2021-22 to 2026-27. |
| Its other markets | Only through the per-event endpoint, and only from 2023: a 2022-12 game answered HTTP 422. First half (moneyline, spread, total) at two offshore books in 2024-12; at FanDuel, BetMGM, BetRivers, Fanatics, GTbets, BetUS and MyBookie from 2025-26. First quarter at FanDuel, BetMGM, BetRivers (Fanatics too on one game). FanDuel also posts second-quarter spreads and totals. Team totals (full game and first half), alternate spreads and totals (Pinnacle among them), alternate team totals. **DraftKings priced no period, team-total or alternate market in any sample.** No player prop key answered. |
| EuroLeague's shot chart (`live.euroleague.net/api/Points`, no key) | Every shot with a **UTC wall-clock stamp** (`UTC`, e.g. 20251211190842 on a game that tipped 19:05:00Z), the running score (A is the home club), the game clock and court coordinates. The play-by-play carries only the game clock, so this is what places halftime against the 5-minute in-play prices. Stored in `euroleague_shots` (`data/ingestors/euroleague_shots.py`, 2026-11-13). Four calls at once tripped Cloudflare's rate limit (HTTP 429, error 1015) after 63 games; the ingest asks one game every 1.5 seconds and backs off on a 429. |
| Today's board (2026-11-12) | 10 games listed 11-13 to 11-17; 49 books priced at least one. DraftKings, BetMGM and Pinnacle each priced 3 of the 10 (the nearest games). **Corrected 2026-11-13:** in the stored history DraftKings first posts a median 45-73 hours before the tip (Pinnacle 28-43), so it posts later than the books that list a round five days out, not near the tip. |
| EuroLeague's own API (`api-live.euroleague.net`, no key) | `v2/competitions/E/seasons/<code>/games`: a season's every game in one call, with the UTC start, both clubs, the score, the four quarter scores and each overtime, the referees, the venue and a neutral-venue flag. `live.euroleague.net/api` Header, Boxscore (quarter scores, referees, attendance) and PlayByPlay (from 2007-08, per the scout). The whole 2026-27 regular season (380 games) is published. |

### The market grid

Every row gets a verdict. **Status as of 2026-11-12: nothing has been
researched yet, because the price history is not bought** (see "The
purchase"). Inputs held: EuroLeague's finals and quarter scores for 2020-21
on (2,398 games); referees, venue and attendance per game.

| Market | Settles on | Prices | Status |
|---|---|---|---|
| Full-game moneyline | final, overtime included | bought: 2021-22 on, 10 books | **rounds 1-2: nothing clears**; **live 2026-11-14 anyway** (mike): the home moneyline at -200 or longer (`euroleague_home_ml`), missing part of the bar (below); favourites at -500 or shorter (`euroleague_heavy_fav_ml`) removed before going live, as a -200 floor leaves them no bet |
| Full-game spread | final margin, overtime included | the same | **rounds 1-2: nothing clears**; **live 2026-11-14 anyway**: home underdogs (`euroleague_home_dog_spread`); a market-anchored spread model dies on 2026-27 |
| Full-game total | both scores, overtime included | the same | **rounds 1-2: nothing clears**; referee crews null, the opening total and its movement null |
| First-half moneyline, spread, total | quarters 1-2; a tied half pushes the two-way moneyline | bought, 2023-24 on; a book a pick may name only from 2025-26 (2023-24 BetUS alone, 2024-25 BetUS and GTbets); live from the period feed 2026-11-14 | **rounds 1-2: nothing clears**, three mechanisms run (`docs/euroleague_market_audit.md`); **live 2026-11-14 anyway**: the first-half moneyline underdog (`euroleague_h1_dog_ml`) |
| First-quarter moneyline, spread, total | quarter 1; a tied quarter (6.31% of games) pushes the two-way moneyline | bought with the first half; live from the period feed 2026-11-14 | **rounds 1-2: nothing clears**; **live 2026-11-14 anyway**: the club first-quarter share total (`euroleague_q1_club_share_total`, 63 bets +22.23%); the unders lead stays frozen |
| Second-quarter spread and total | quarter 2 | FanDuel only | to do; likely parked (one book) |
| Team totals, full game and first half | one club's points | BetMGM, BetRivers, Fanatics (first half: BetRivers) | to do |
| Alternate spreads and totals | final | BetMGM, BetRivers, Fanatics, Pinnacle | to do |
| Regulation 3-way (a draw after 40 minutes) | quarters 1-4 | `h2h_3_way` at two books on today's board | to do; check depth |
| In play: full game | final | the full path's in-play snapshots (5 minutes) | to do |
| In play: full game at halftime | final, overtime included | the full path's in-play snapshots (every 5 minutes during games), halftime placed by the shot chart | **total and moneyline null; the halftime spread a lead that misses the bar** (364 bets +10.93% [+3.40, +18.48]; `docs/euroleague_market_audit.md`, Halftime) |
| Player props | | the feed: no player key answered | **to do** (reopened 2026-11-14): only the odds feed was asked; DraftKings' own board and the odds-comparison sites are untried (the league-models skill, market-grid route 4) |
| Futures (champion) | | not checked | parked |

## What runs, and where it lands

| What | Where | When |
|---|---|---|
| The schedule, finals and quarter scores | `euroleague-games` step (`data/ingestors/euroleague_api.py --current`) | the 6am pipeline and every hourly refresh pass |
| The pre-game board (thirteen books, Pinnacle among them) | the worker's odds passes (`odds_ingestor.SPORT_KEYS`) | every odds pass |
| The halftime spread | `models/euroleague_live_loop.py`, job `euroleague_live` on pollers | every 10 minutes, 9am-5:58pm ET; reads at each five-minute mark plus 37 s while a game is at its break |
| Its decisions, bet or not | `euroleague_live_decisions` (one final row a game) | at the deciding read |
| Its bets | `picks` (`is_live`), the app's Live board, push, the EuroLeague live Discord channel only | at the deciding read |
| Settlement | `tracking/paper_tracker` through `config.LIVE_MODELS` (a full-game spread against `scored_line`, the home number) | the next settle pass after `games` holds the final |
| The period and full-game lines at the decision times | `scripts/euroleague_pregame_window.py`, job `euroleague_pregame_window` on the worker (`data/ingestors/euroleague_period_odds.py`) | every minute; one call per game 60, 10 and 2 minutes before tip |
| The four pre-game rules | `scripts/euroleague_pregame_card.py` in the same job | each game once, on its tip-minus-10 call |
| Their decisions, bet or not | `euroleague_pregame_decisions` (one row a game and model) | at the decision |
| Their bets and NONE rows | `picks`, the app, push, the EuroLeague pre-game Discord channel (`DISCORD_CHANNEL_EUROLEAGUE` / `DISCORD_WEBHOOK_EUROLEAGUE`; unset, nothing posts) | at the decision |
| Their settlement | `tracking/paper_tracker._RULE_MODEL_MARKETS`: the moneylines on `home_win`, the spread on the final margin against the home number, the first half on quarters 1-2 and the first quarter on quarter 1 of `euroleague_period_scores` (overtime never counts; a tied half pushes) | the next settle pass after the final and its quarters are stored |

## Halftime spread: `euroleague_live_spread_ht` (live 2026-11-13, mike)

**The rule.** The full-game spread, home or away, bet once a game during the
halftime break. The first five-minute price read inside the break that holds
an eligible quote decides the game: its best-EV quote is bet when EV >= 0.05,
and the game is spent either way. It is the women's college halftime method
ported (`models/ncaabw_live_ht.py`), with Pinnacle's pre-game close as the
pre-game number:

- **The margin still to come** (final margin minus the half-time margin, home
  minus away, overtime included) is normal. Its mean is
  `f*prior_m*b0 + f*sur*b1 + f^2*sur*b2`, with f = 0.5 at the break,
  `prior_m` = minus Pinnacle's last pre-game home spread, and
  `sur` = the half-time margin minus half of `prior_m`. Its variance is
  `s0 + s1*f + s2*f^2`. Fitted by weighted least squares, three passes, on the
  score every 30 seconds of regulation of every qualifying game of 2021-22 to
  2025-26 (114,014 states). At the half the fit keeps 44.6% of Pinnacle's
  margin to come and gives back 26.6% of the first half's surprise; sd 9.19.
- **Pricing.** For a home spread `s` with the home side up `m` at the half:
  `k = -s - m`, P(home covers) = P(margin to come > k) with pushes removed on a
  whole number; EV = p x decimal - 1 for each side; the higher EV is the side.
- **Eligible quotes** (the research's rule, unchanged): a book a pick may name
  (DraftKings, FanDuel, BetMGM, BetRivers, Fanatics); stamped at or after the
  game's first shot and after the half's last shot; both prices real; the
  side's price within -250 to +250; at least two other in-play books quoting
  the game's spread in the read (Pinnacle, Bovada, Marathonbet, Unibet and
  Paddy Power count but are never bet); within 6 points of the read's median;
  |line| <= 70. The read must fall more than a minute after the half's last
  shot and more than a minute before the third quarter's first.
- **The pre-game number** is Pinnacle's last coherent spread and total stamped
  at or before min(tip, the first shot). A game without both is not priced.

**The evidence** (`docs/euroleague_halftime.md`, section 3b, "B spread, V2
Pinnacle prior"; walk-forward, each season on a model fitted on every earlier
one):

| Season | Bets | W-L | Units (research stake) | Return | Units (posted stake) |
|---|---|---|---|---|---|
| 2022-23 | 107 | 60-47 | +6.05 | +4.94% | +5.95 |
| 2023-24 | 61 | 32-29 | -1.15 | -1.65% | -1.35 |
| 2024-25 | 58 | 39-19 | +17.90 | +27.18% | +17.94 |
| 2025-26 | 107 | 62-45 | +10.69 | +8.73% | +10.69 |
| 2026-27 to 11-12 | 31 | 22-9 | +11.85 | +34.09% | +11.85 |
| **All** | **364** | **215-149** | **+45.34** | **+10.93% [90%: +3.40, +18.48]** | **+45.08** |

The research staked an underdog 1 unit to win its price; the app posts every
bet as 1 unit to win (risk capped at 3), which is the "posted stake" column
(the build prints both). Every cut from 0.02 to 0.12 is positive (+4.45%,
+7.31%, +10.93%, +11.98%, +17.59%); 200 shuffles of the half-time score never
reached it (95th percentile -1.09%); the blind bets on the same kind of side
lose (-2.2% to -8.6%); the bets turned round lose 23.91%.

**What it missed, plainly.** It failed the false-discovery correction across
all 183 cells of the halftime study (its p 0.0096 against a first-rank
threshold of 0.00055). 2023-24 was negative. The 2021-22 second look was
negative (-3.55% on 33). 78% of its bets are halftime underdogs. 2026-27's 31
bets carry 11.85 of the 45.34 units. It was the best of five spread rules, not
the one written down first. mike approved it knowing this.

**The replay.** `scripts/build_euroleague_live_ht_artifact.py` decides every
walk-forward game again through `models/euroleague_live_ht.read_break`, the
code the loop runs, then runs the research's own code on the same cache:
**364 identical bets (game, book, side, line, price, read), +45.34 units, no
difference in either direction**, and the same count at every cut. The
artifact (`models/saved/euroleague_live_ht_2027.json`) is the 2026-27 fold,
the model the research graded 2026-27 to date on; the loop refuses an
artifact for another season.

**Prices.** Median -115, shortest -135, longest +105; none shorter than -300.
The platform's -200 floor (`config.MODEL_MIN_ODDS`) never binds; it is pinned
so a default change cannot move it. The edge cap (`models/euroleague_quote_bounds.py`)
is 0.40 against a largest replayed decision edge of 0.166.

**Volume.** 58 to 107 bets a full season (2022-23 to 2025-26), 31 in the first
105 games of 2026-27: about one bet every three or four games, roughly 5 a
week in a two-round week. 2025-26, the one season with all five bookable
books, made 107.

**Go-live gate standing:** 0 settled of 50. Reported, never a hold.

### The live path, and why

- **Halftime and the half-time score: EuroLeague's own live API**
  (`data/ingestors/euroleague_live_feed.py`, free, no key), one game at a
  time, 1.5 s between calls, a 30-second back-off on Cloudflare's HTTP 429.
  `PlayByPlay`: the half is over at the second quarter's 'EP' (End Period);
  the third has begun at its 'BP' (Begin Period) or its first shot. Read off a
  finished game (E2026 game 110): the third quarter's substitutions are
  numbered before its 'BP', so they are logged during the break, and "the
  third quarter is not empty" would have ended the break early. `Points`: the
  half's last shot and the game's first, in UTC, and the half-time score as the
  running maximum over the first 20 minutes (equal to the quarter scores on
  1,798 of 1,798 stored games). `Header`: the score after two quarters, a
  second witness; any disagreement skips the read. The API is read before the
  odds call and again after it; a half that changed between the two is skipped.
- **The pre-game number: stored `odds`.** Pinnacle is in the forward pull.
  Measured 2026-11-13 (read-only): on the three games of that day, Pinnacle's
  last pre-game spread and total were stamped 0, 11 and 11 minutes before the
  tip (`source` NULL, the forward pull). The research's own close came from
  the five-minute history; a game whose last Pinnacle quote is older is still
  priced on it.
- **The books: the Odds API live endpoint**, one bulk call a read at the ten
  books the history was bought at (`config.EUROLEAGUE_HISTORY_BOOKMAKERS`):
  the five that may be bet and the five reference books, so the read's median
  and its count of other books are over the books the grade had. Ten named
  books bill as one region: **3 credits a call** for moneylines, spreads and
  totals. That number is derived, not measured live: the history billed 30
  credits a snapshot for the same ten books and three markets, and the
  historical endpoint bills ten times the live one. The loop logs the first
  call's `x-requests-last`. A game gets two or three reads, about 6-9 credits.
- **DraftKings' own live board is not used.** On 2026-11-13 at about 23:15
  UTC, DraftKings' basketball navigation for Ohio (the state the board feed
  reads), New Jersey and Massachusetts listed no EuroLeague league; the next
  EuroLeague game was 89 hours away, and DraftKings lists a league only while
  it has offers. So its league id could not be read. The rule also needs two
  other books beside the decider, which only the odds feed carries, and the
  graded population is the odds feed's DraftKings quote. The next step: read
  the navigation again while a EuroLeague round is on the board, and if
  DraftKings lists it, add the id and a club-name resolver to
  `data/ingestors/dk_live_board.py`.

### Differences from the research a live loop cannot avoid

- **Breaks longer than 25 minutes or shorter than 10** were left out of the
  grade; a live loop cannot know a break's length in advance. A read more
  than 25 minutes after the half's last shot is treated as past.
- **The end of the break.** The grade's window closed a minute before the third
  quarter's first shot. Live, a read is past once the third quarter's 'BP' or
  first shot is on the API; a read in the last minute before a first shot that
  has not happened yet cannot be told apart.
- **The read time** is when the bulk call returned, a few seconds after the
  five-minute mark plus 37 s once EuroLeague's API has been read (the
  history's snapshots were stamped 36-40 s after the mark). Every decision row
  records it.
- **EuroLeague's live API timing is not yet measured on a live game**: how
  soon 'EP', 'BP' and each shot appear. The first live slate (2026-11-17) is
  the measurement; every read's state is in `euroleague_live_decisions`.

## The four pre-game rules (live 2026-11-14, mike)

mike, 2026-11-14: *"I told you to build all the models"*, knowing each one
MISSED part of the research bar. Each is a rule card
(`models/euroleague_pregame.py`, one card for all four,
`scripts/euroleague_pregame_card.py`), decided once a game ten minutes before
the tip, at the best price among the five books a pick may name (DraftKings,
FanDuel, BetMGM, BetRivers, Fanatics). Each has its own switch
(`RUN_EUROLEAGUE_HOME_ML`, `RUN_EUROLEAGUE_HOME_DOG_SPREAD`,
`RUN_EUROLEAGUE_H1_DOG_ML`, `RUN_EUROLEAGUE_Q1_SHARE_TOTAL`);
`RUN_EUROLEAGUE_PREGAME=0` stops all four and their feed.

**The replay.** `scripts/euroleague_pregame_build.py` decides every game of the
research cache again through the card's own decision code, runs the research's
own scripts on the same cache, and compares them bet for bet (game, side,
number, price, book). On the research's data state (games through 2026-11-12)
every read matched with no difference in either direction:

| Model | Research read | Bets | Units | Card's replay |
|---|---|---|---|---|
| euroleague_home_ml | DraftKings close | 972 | +59.64 | 972, +59.64 |
| | best deciding-book close | 984 | +64.80 | 984, +64.80 |
| euroleague_home_dog_spread | DraftKings close | 454 | +48.34 | 454, +48.34 |
| | best deciding-book close | 455 | +54.54 | 455, +54.54 |
| euroleague_h1_dog_ml | best deciding book at tip minus 10 | 465 | +19.14 | 465, +19.14 |
| euroleague_q1_club_share_total | best deciding book at tip minus 10 | 63 | +17.71 | 63, +17.71 |

The card bets the best deciding-book price (CLAUDE.md 6), so the "best" rows
are the live populations. The cache has gained one game since (2026-11-13):
the full-game purchase's quotes end at 05:45 UTC that day, so its "close" is a
stale board and it is not read.

**One game never carries two bets that cannot both win.** The two full-game
rules both bet the home side (the moneyline, and the spread only when the home
number is above 0), so they can always win together, and a first-half or
first-quarter bet can win beside any full-game bet: no two of the four decided
in one pass conflict, and the replay loses no game to the rule. A full-game
moneyline or spread that cannot win beside a standing EuroLeague full-game BET
(the halftime spread) is written NONE; the standing BET keeps the game. The
halftime loop checks its spread against the pre-game rules' standing bets the
same way (`models/euroleague_live_loop.standing_spreads`: the moneyline is the
spread at -0.5 home). Until the big-favourite rule was removed, it and the home
moneyline sat on opposite sides of 6 replayed games, and both were written
NONE there; with it gone, the home moneyline keeps those 6 (net -1.00 units).

**The probability.** A blind rule has no probability of its own. Each pick
carries the market's no-vig chance of the bet side (power de-vig for the
full-game moneylines, multiplicative otherwise, as the research priced them)
plus the rule's walk-forward uplift: its replayed bets' win share minus that
mean no-vig chance over the seasons before 2026-27, pushes out. Every uplift is
larger than the vig, so every replayed bet carries a positive EV. The EV floor
and the edge cut (`config.py`) sit just under the smallest replayed EV and
edge: they remove none of the replayed bets. The rule is the cut.

| Model | Uplift (bets) | Smallest EV / median | Smallest edge | EV floor | Edge cut |
|---|---|---|---|---|---|
| euroleague_home_ml | +0.0520 (921) | +0.0401 / +0.0628 | +0.0197 | 0.04 | 0.01 |
| euroleague_home_dog_spread | +0.0904 (421) | +0.1181 / +0.1272 | +0.0632 | 0.11 | 0.06 |
| euroleague_h1_dog_ml | +0.0524 (347, 2025-26) | +0.0106 / +0.0902 | +0.0055 | 0.01 | 0.00 |
| euroleague_q1_club_share_total | +0.1575 (53, 2025-26) | +0.1779 / +0.2240 | +0.1053 | 0.17 | 0.10 |

Read every model probability as an upper bound: each uplift is the extra the
rule's own bets won, in sample.

### euroleague_home_ml — "EuroLeague Moneyline"

- **The rule** (round 2, A1, `r3_a_home.py`): the home side's moneyline at the
  close when its price is -200 or longer, not at a neutral site; every quote
  shorter than -200 is removed BEFORE the best price is picked.
- **The evidence:** 972 bets, 506-466, +59.64 units, +4.89% [90%: -0.68,
  +10.39] at DraftKings' close; 984, 513-471, +64.80, +5.24% [-0.27, +11.08]
  at the best deciding book, which is the live population. By season (best
  book): 2021-22 +18.28% (165), 2022-23 +4.11% (172), 2023-24 +0.74% (176),
  2024-25 +3.36% (178), 2025-26 +6.79% (230), 2026-27 to 11-12 -12.70% (63).
- **What it missed:** the interval reaches below zero; +0.29% without its 10
  best dates; 2026-27 -18.50% at DraftKings; the false-discovery correction (p
  0.071); the price bands do not rise in order (-200 to -151 lost -5.55%);
  one side by construction (the away side under the same floor lost -13.84% on
  1,572).
- **Prices:** median -110, shortest -200, longest +550; none shorter than
  -300. The -200 floor is the rule itself.
- **Volume:** about 184 bets a full season, about 6 a week.

### euroleague_heavy_fav_ml — removed

Removed before going live (mike, 2026-11-14: "odds cutoff for favorites should
be -200"): every bet the rule found was -500 or shorter (188 bets +34.59 units
+6.13% at DraftKings' close), so at a -200 floor it could never bet.

### euroleague_home_dog_spread — "EuroLeague Spreads"

- **The rule** (full game round 1, H3, `r2_leads2.py`): the home side against
  the full-game spread when the modal deciding-book home number is above 0, at
  its best price on that number. Own-country games only: not neutral, and not at
  one of the research's relocated venues (`RELOCATED_VENUES`, `r2_leads.py`'s
  lists: Maccabi in Belgrade and Limassol, Hapoel in Sofia and Botevgrad, Dubai
  in Sarajevo and Zenica, and six one-off venues abroad).
- **The evidence:** 454 bets, +48.34 units, +9.72% [+2.44, +16.89] at
  DraftKings' close; 455, 262-189-4, +54.54 units, +11.00% [+3.63, +17.95] at
  the best deciding book. By season: 2021-22 +14.33% (93), 2022-23 +8.95% (77),
  2023-24 -6.12% (81), 2024-25 +10.06% (79), 2025-26 +33.32% (95), 2026-27
  -16.68% (30).
- **What it missed:** 2025-26 carries 64% of the units (DraftKings); +5.37%
  without its 10 best dates; the walk-forward version (buckets chosen from
  earlier seasons) +3.16%; 2026-27 -24.06% on 30 at DraftKings; the
  multiplicity bar; it was chosen with the residual table in view.
- **Prices:** median -110, shortest -120, longest -102.
- **Volume:** about 85 bets a full season, about 3 a week.

### euroleague_h1_dog_ml — "EuroLeague First Half Moneyline"

- **The rule** (first half round 1, `r1_baselines.py`, the best baseline): the
  first-half moneyline side whose mean deciding-book no-vig chance is under
  one half, at its best deciding-book price, on the tip-minus-10 fetch. A level
  mean (a pick'em) is not bet. **A tied half pushes**: the two-way first-half
  moneyline voids a tie (the research measured it: BetRivers' two-way price
  de-vigged equals its three-way draw-no-bet price); Fanatics posts only the
  three-way, which is a different market and is not read.
- **The evidence:** 465 bets, 192-258-15, +19.14 units, +4.22% [-4.64,
  +12.35]: 2025-26 +8.38% (358), 2026-27 -9.76% (107).
- **What it missed:** the interval runs through zero; 2026-27 negative; one
  priced season before the live one.
- **Prices:** median +142, shortest -115, longest +475.
- **Volume:** about 358 bets a full season (2025-26), about 11 a week: the
  rule bets nearly every game a deciding book prices.

### euroleague_q1_club_share_total — "EuroLeague First Quarter Totals"

- **The rule** (round 2, Q1-i at margin 1.0, `r3_d_periods.py`): each club's
  share of its games' points scored in the first quarter, from every earlier
  game (tipped 3+ hours before) since 2020-21, shrunk n / (n + 40) toward the
  league mean; the pair's share times the full-game total (Pinnacle's
  alternate ladder in the same fetch, interpolated where its no-vig over chance
  crosses one half; else Pinnacle's main total; else DraftKings') against the
  modal deciding-book first-quarter total, rungs set aside (a main number whose
  no-vig side chance is outside 0.35-0.65, or 2+ points from every other book's
  main number). Over when the implied number is a point or more above the
  book's, under when a point or more below.
- **The evidence:** 63 bets, 43-20, +17.71 units, +22.23% [+4.08, +39.66]:
  2025-26 +21.38% (53), 2026-27 +26.89% (10). Placebo: 1% of 200 shuffles at
  or above it.
- **What it missed:** 63 bets against the 200-bet bar; one season with 30+
  bets; the false-discovery correction (p 0.0188); no plateau (margin 0.75
  +4.44%, 0.5 -3.68%); and 1.0 was the grid's best cell, not the pre-registered
  0.5, which lost.
- **Prices:** median -122, shortest -145, longest -111.
- **Volume:** about 53 bets a full season (2025-26), about 2 a week.

**Go-live gate standing, all four:** 0 settled of 50. Reported, never a hold.

**In the app** (UX review, 2026-11-14): the names above; each model page says
what it bets and the prices it lays.

### When they decide, and on what

- **The decision fetch.** The live feed
  (`data/ingestors/euroleague_period_odds.py`) makes one per-event call per
  game at 60, 10 and 2 minutes before the tip: every first-half, quarter,
  team-total and alternate key the purchase asked, plus the full game's
  moneyline, spread and total, at the ten books of
  `config.EUROLEAGUE_PERIOD_BOOKMAKERS`, stored in `odds` under source
  `odds_api_euroleague_period_live` (protected from the odds clean-up), with
  one ledger row a call in `euroleague_period_live_fetches`. The rows are
  parsed by the purchase's own code, so each book's main number is chosen
  exactly as the research's rows were.
- **The card** decides each game on the call made for tip minus 10 that landed
  5 to 10.5 minutes before the tip: the full-game rules on the board at that
  instant (every stored pre-game quote stamped at or before it, the call's own
  included), the period rules on the call's own rows. Why the call carries the
  full game too: EuroLeague tips at 17:00-20:30 UTC, inside the hourly refresh
  window, so a stored full-game quote can be nearly an hour old at tip minus
  10, where the research read a five-minute snapshot.
- **With no decision call by 5 minutes before tip** the full-game rules decide
  on the stored board as of tip minus 10 (the row says so) and the period rules
  record `missed`; a game that tips with a model undecided is `missed` too. A
  miss fails the run after every other write.
- **The cost, from the code's billing model, not measured live.** The
  per-event endpoint bills about 1 credit per market a book returns, per
  region (the history bills ten times that: the period trial's 2,821 credits on
  24 answers, 11 to 13 markets each), and ten named books are one region. So a
  call costs about 14-16 credits (11-13 period markets and the 3 full-game
  ones), at most 34; a game about 45 (three calls), at most 102; a 380-game
  regular season about 17,000, at most about 39,000. The ledger records each
  call's `x-requests-last`: the first live call measures it. The feed buys
  nothing under one day of the platform's measured burn
  (`EUROLEAGUE_PERIOD_RESERVE_DAYS`).
- **Closing-line value** for the two period rules is read from a call made
  after the pick (the tip-minus-2 call), as the NCAAB first half's is: the
  decision call is the price taken, so it is never its own close.

## What differs from the games we already bet

- **FIBA rules:** four 10-minute quarters, 5-minute overtimes. Stored overtime
  share 3.6% to 6.1% a season in the six finished seasons (20 of 328, 13 of 299, 16 of 328, 18 of 331, 12
  of 330, 17 of 402, 5 of 107 so far). Every overtime game was tied after four
  quarters and every regulation tie went to overtime, in every season (the
  stored `went_to_ot` equals `regulation_tie` on all 2,398 games).
- **Totals near 165-176** (Pinnacle's closes on 2025-12-11's ten games).
- **The ids are EuroLeague's**: `EUROLEAGUE_<season code>_<game code>`, which a
  date change cannot split into twins (2020-21 moved several games).
- **Team ids are EuroLeague's three-letter club codes** (MAD, PAN, ULK, TEL
  ...), stable through sponsor renames ("Cazoo Baskonia", "Kosner Baskonia" are
  both BAS).
- **"Home" is not always home.** Read from the stored venues and attendances
  (`euroleague_events`, 2026-11-12): Maccabi Tel Aviv played 53 "home" games in
  Belgrade from 2023-24 on (Aleksandar Nikolic Hall and Belgrade Arena; an
  average attendance of 118, 188, 310 and 218 a season), and one in Limassol;
  Hapoel Tel Aviv 21 in Sofia and Botevgrad (2025-26 on; 816 and 312 on
  average so far in 2026-27); Dubai 6 in Sarajevo and Zenica (2025-26).
  **None is flagged neutral** by EuroLeague's `isNeutralVenue`. The stored
  `neutral_site` is that flag or a Final Four game, so a relocated "home" game
  must be told apart by its venue (an open item, below). 2020-21 was played
  without crowds (Maccabi's home average that season: 624), so a home-edge
  baseline reads it separately.
- **No sharp book problem**: Pinnacle prices most games every season.
- **DraftKings prices no period market** (and posts its full-game lines a
  median 45-73 hours before the tip, later than FanDuel), so a
  first-half or quarter pick names FanDuel, BetMGM, BetRivers or Fanatics, a
  population reported separately (CLAUDE.md §6).
- **The 28 cancelled 2021-22 games** (the Russian clubs' after 2022-02) have an
  event row with status Cancelled and no games row.

## Identity: EuroLeague owns the games row

`data/ingestors/euroleague_teams.py` and `data/ingestors/euroleague_api.py`.

- `euroleague_teams` (club code, newest name, every name carried),
  `euroleague_events` (one row a game: season, phase, round, UTC start, clubs,
  neutral, status, venue, referees, attendance), `euroleague_period_scores`
  (periods 1-4, overtimes 5 on), `euroleague_api_raw` (each season's answer as
  fetched, once per change). Worker-only.
- `games`: sport `EUROLEAGUE`, home_team / away_team the club codes, the
  score filled once (never overwritten), `went_to_ot`, `regulation_tie`,
  `home_win`. Data source `euroleague_api_v2`.
- **The odds feed never mints a EuroLeague game** (`odds_ingestor`
  `RESOLVE_ONLY_SPORTS`). An event is placed on the stored game with the same
  unordered club pair whose start is nearest, within 30 hours; when the feed
  calls EuroLeague's away club home the names are swapped first, so a stored
  spread is the home club's number (CLAUDE.md §4).
- **Feed names** (`config.EUROLEAGUE_ODDS_API_MAP`): the 27 names on the feed's
  2,164 events map to 26 clubs (Fenerbahce appears as "Fenerbahce SK" and
  "Fenerbahçe Beko"). A name outside the map is matched, accent-folded, against
  every name a club has carried, only when exactly one club matches.

**Stored 2026-11-12:**

| Season | Events | Games rows | Scored | Overtime | Neutral | Quarter rows |
|---|---|---|---|---|---|---|
| 2020-21 | 328 | 328 | 328 | 20 | 4 | 1,334 |
| 2021-22 | 327 | 299 | 299 | 13 | 4 | 1,210 |
| 2022-23 | 328 | 328 | 328 | 16 | 4 | 1,328 |
| 2023-24 | 331 | 331 | 331 | 18 | 4 | 1,346 |
| 2024-25 | 330 | 330 | 330 | 12 | 4 | 1,333 |
| 2025-26 | 402 | 402 | 402 | 17 | 3 | 1,631 |
| 2026-27 to 11-12 | 380 | 380 | 107 | 5 | 0 | 433 |

The first write held each season in one transaction of single-row statements
and lost its connection in the fourth season (the transaction was discarded
whole); the writes are batched now (`executemany`), and all seven seasons took
31 seconds.

## The purchase

Two purchases, both bought into Supabase in the same run, both protected from
the odds clean-up (`data/prune_odds.PROTECTED_SOURCES`), and EuroLeague keeps
its whole price path going forward (`PATH_KEPT_SPORTS`).

The credit planner refuses a run whose worst case (every 5-minute slot of
every day) would cross the floor, and seven seasons at their worst case are
past any balance, so the full purchase runs with `--chunk-days 30`: seasons
newest first, 30-day chunks newest first, each cleared by the planner, each
season stored once fetched, stopping for good at the first refusal or floor
stop.

**1. The full game, every snapshot** (`data/ingestors/euroleague_odds_history.py`,
a fork of the women's college purchase). Moneyline, spread and total at the ten
books of `config.EUROLEAGUE_HISTORY_BOOKMAKERS`: the five a pick may name that
price EuroLeague, Pinnacle and Bovada, and Marathonbet, Unibet and Paddy Power.
Ten named books bill as one region: **30 credits a snapshot** (an eleventh book
billed 60). It walks the feed's own chain a UTC day at a time, spools each
answer, and stores pre-game quotes change-only in `odds` (source
`odds_api_euroleague_history`) and every in-play quote in
`euroleague_inplay_quotes`, with one ledger row a snapshot in
`euroleague_odds_snapshots`.

- **The trial, 2025-12-11:** 288 snapshots, 8,640 credits, 2,963 pre-game rows
  and 2,683 in-play rows, every event placed (0 unresolved names, 0 pairs with
  no game). Read back: all ten books on all ten games, and every home favourite
  carries a negative stored spread (Milan +2.5 and Virtus +3.5 as home
  underdogs).
- **The estimate for every season**, from the census (the share of a day's
  four asks answered within 10 minutes, times 288 or 144 slots, times 30):
  about 0.69M (2026-27 to date), 1.90M, 1.66M, 1.67M, 1.48M, 0.80M and 1.01M,
  newest first: **about 9.2M credits**.

**2. First half, quarters, team totals and alternates**
(`data/ingestors/euroleague_period_history.py`). One per-event call per game
at 24 h, 12 h, 6 h, 3 h, 2 h, 1 h, 30 and 10 minutes before the tip, for the 31
period, team-total and alternate keys, at the ten books of
`config.EUROLEAGUE_PERIOD_BOOKMAKERS`. It bills 10 credits per market a book
actually returns.

- **The trial, the newest date:** 24 answers, 2,633 rows, 2,821 credits
  (about 117 a call, 11 to 13 markets returned).
- **The plan:** 9,360 (game, time) pairs on the 1,170 played games of 2023-24
  to date; at most 2,902,436 credits (every key at every time), **about 1.1M**
  at the trial's rate.
- **Bought, 2023-24 to 2025-26 (2026-11-13 01:39Z to 03:03Z):** all 8,504
  pairs asked, 478,983 rows, **801,918 credits**. Read back from the ledger:

  | Season | Games | Pairs answered | No line at any book | Rows | Credits | Pairs with a first-half spread | with a first-quarter total |
  |---|---|---|---|---|---|---|---|
  | 2023-24 | 331 | 2,648 | 70 | 62,375 | 164,150 | 2,190 | 2,050 |
  | 2024-25 | 330 | 2,640 | 6 | 72,770 | 159,280 | 2,492 | 1,437 |
  | 2025-26 | 402 | 3,216 | 1 | 343,838 | 478,090 | 3,215 | 2,313 |

  **Corrected:** first-quarter lines go back to 2023-24, not only 2025-26 as
  the three sampled games suggested.

**The floor.** The plan holds 15M credits a cycle; it refilled 2026-11-08 and
11,605,707 were left after the trials. The platform's own burn measured
58,664 a day. Both purchases stop before the balance would fall under 33 days
of that burn (1,935,912): the days to a refill on 12-08 plus the 7-day
reserve. At about 10.3M for both, about 9.7M fits above that floor this
cycle; the oldest days (part of 2020-21) would wait for the refill and resume
from the spool.

**What mike approved (2026-11-13: "Do the 4.4m").** No 2020-21 (no
DraftKings, no crowds; its finals and quarter scores are stored free). The full
game every snapshot from 30 minutes before each tip to 2.5 hours after it, and
one every 15 minutes otherwise (`--pregame-step-min 15`): the trial day held 35
snapshots with a game in play and 253 without. About 3.3M for the full game and
1.1M for the period lines. 2021-22 to 2025-26 are bought first; 2026-27 waits
for the merge, because the clean-up never visits a date before 2026-09-01
(`data/prune_odds.BACKLOG_FLOOR`) but does visit this season's.

**Before the approval.** Both are waiting on (a) this branch's merge, because
until the clean-up protects these sources in production it would thin bought
first-half rows to an opener and a close, and (b) mike's yes to the spend.

## The forward collection

From the merge, the worker's odds passes pull EuroLeague with every other
sport (`odds_ingestor.SPORT_KEYS`), at the line-shop ten plus
`config.EUROLEAGUE_EXTRA_BOOKMAKERS` (thirteen books, two regions: 6 credits a
pass), resolved onto the stored schedule and kept even when DraftKings has not
posted (`DK_GATE_EXEMPT_SPORTS`). The schedule and finals come from the
`euroleague-games` step (`euroleague_api --current`): in the 6am pipeline
before the odds step, and on every hourly refresh pass. The live first-half,
quarter and full-game fetch at the decision times is the pre-game window's
(`data/ingestors/euroleague_period_odds.py`, "When they decide, and on what"
above), from 2026-11-14.

## Open items

- The halftime spread's first live slate: EuroLeague's API timing at the
  break, whether `games` ever holds a mid-game score (the `euroleague-games`
  step writes a game EuroLeague's API marks played; not yet watched during a
  game), and the decision rows' reasons.
- DraftKings' EuroLeague board: read the navigation while a round is posted.

- The four pre-game rules' first live slate: the first call's
  `x-requests-last` (the cost above is derived), each rule's first decision
  rows and reasons, and the first bet on every surface.
- The relocated-venue lists the home-underdog spread reads are the research's
  (2026-11-12). A relocation after that date is not on them: a club-arena
  table would replace the hand-typed lists.
- Relocated "home" games: a club-arena table, so a home game away from the
  club's own city is known before a model reads home advantage.
- The research: baselines on every grid row, the leads in
  `docs/euroleague_market_audit.md`, then the method search.

Commands (from a checkout with production settings):

    python -m data.ingestors.euroleague_api --seasons 2021 2027 --apply
    python -m data.ingestors.euroleague_odds_history --seasons 2021 2027 --spool DIR --fetch --store --chunk-days 30 --reserve-days 33
    python -m data.ingestors.euroleague_period_history --seasons 2024 2027 --apply --floor 1936000
