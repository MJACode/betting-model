# TENNIS — data, odds capture, models

> **Started 2026-11-13** (mike: *"Use the model building skill to build
> professional tennis models"*), built with the league-models skill.
> **Two sports, not one** (mike, 2026-11-13: *"mens and womans should be
> different model groups / discord channels. But not just major tournaments,
> all pro tennis matches"*): `ATP` is men's professional singles at every level
> (the tour, Challengers, ITF), `WTA` is women's (the tour, the 125 level,
> ITF). Each has its own models, its own record and its own Discord channel.
> Season label: the year of play, threaded from the tournament (the archive's
> tourney id, ESPN's event id), never from a match date (an event starting
> 2023-12-31 is the 2024 season).
>
> **No model is live yet.** This file holds the groundwork, what each source
> holds, the settlement rules, the market grid and the purchases.

## Discord

Two channels, created 2026-11-13 by the worker's `discord_create_channel` job on
mike's yes (worker_jobs 1282265 and 1282266), as copies of #🏀-ncaabw (same
category, same four permission overwrites): **#atp-tennis** (1570859599299354677)
and **#wta-tennis** (1570860861705166878). `config.DISCORD_SPORTS` names `ATP`
and `WTA`, and `config.DEFAULT_DISCORD_CHANNELS` carries the two ids (a channel
id is not a secret; a `DISCORD_CHANNEL_<SPORT>` variable on the worker still
wins), so no Railway variable is needed. The first post through each is the
`discord_test_post` job once this branch is on master.

## What the sources hold (measured 2026-11-13)

| Source | What it holds |
|---|---|
| The odds feed | **One key per tournament, 53 in all** (`/v4/sports?all=true`): 26 men's (the four Grand Slams, the nine 1000-level events, the ATP Finals and twelve 500s) and 27 women's (Slams, 1000s, a set of 500s, the WTA Finals). No 250-level event, no Challenger, no ITF. A key is active only while its event runs: on 2026-11-13 only the two Finals were. |
| Its history | From the 2020 US Open (13 events listed at 2020-09-05), five-minute snapshots while prices move. Each key's yearly window is in `tennis_odds_fetches` (the coverage sweep, below). An ask for a time the key holds nothing at is answered with the key's previous snapshot, and billed: the Paris Masters key asked at 2026-10-29 answered 2025-11-02 (30 credits). An answer with no events is free. |
| Its books | 2025-08-30, US Open men's, every region: 56 books, among them DraftKings, FanDuel, BetMGM, Caesars (9 of 12 events), Fanatics, BetRivers, Hard Rock, Bovada, **Pinnacle (10 of 12)**, LowVig, BetOnline, and the **Betfair, Matchbook and Smarkets exchanges**. 2026-08-31, US Open men's: Pinnacle priced 42 of 51 events, DraftKings 51, FanDuel 51. 2021-06-02 (French Open): no Pinnacle in the sample; `betfair` (not `betfair_ex_*`) on 14 of 32 events. **Pinnacle was not on the 2026-11-13 board** for either Finals (61 books on the women's matches); whether it posts later in the day is an open item. |
| Its markets | Asked one at a time on the 2026-11-13 WTA Finals match: match winner (48 books), games spread (18), total games (23), first-set winner (`h2h_s1`: BetMGM and LeoVegas), alternate games spreads (LeoVegas) and totals (LeoVegas, Coral, Ladbrokes). No player games, aces, double faults or set betting: `player_aces`, `player_double_faults` and `set_betting` are "Invalid markets"; team totals and period keys return nothing. **DraftKings, FanDuel, BetMGM, Fanatics, ESPN BET and Hard Rock price only the match winner**; the games spread and total sit at BetRivers, Caesars, Bovada, Pinnacle, LowVig, BetOnline, Bally and betPARX. |
| Its bill | `x-requests-last`: 10 credits per market per region on the history endpoint; ten named books bill as one region (30 for three markets, 60 for twenty books); the history event list costs 1. |
| ESPN's scoreboard (`site.api.espn.com/apis/site/v2/sports/tennis/{atp,wta}/scoreboard?dates=`) | Free. Every tour-level singles match, the 250 and WTA 125 levels included, from 2010 at least: round, court, start, both players' ESPN ids, games per set, tiebreak points, and a status naming a retirement (`STATUS_RETIRED`) or walkover. One call returns each tournament in play that day, whole (the 2025 US Open: 239 men's singles matches with qualifying). Its `format` field reads 5 sets for best-of-three events (the women's US Open, Shanghai), so best-of is set from the tour and the event. ESPN's core odds endpoint holds nothing for tennis (`count: 0`). |
| The match archive | Jeff Sackmann's datasets via the public mirror `Aneeshers/tennis-sackmann-archive` (commit 83733587, an upstream snapshot of June 2026; the upstream repositories answer 404). Score, round, surface, ranks, minutes, and serve and return counts for both players. **Licence: CC BY-NC-SA 4.0, non-commercial**, as the mirror's README states. Stored: men's tour 2000-2026 and challengers/qualifying 2010-2026; women's tour 2000-2026 and qualifying/ITF 2010-2026 without the $10k-$25k levels. |
| Pinnacle's own site (`guest.api.arcadia.pinnacle.com/0.1`, no key) | Every level: on 2026-11-13 its tennis board held 33 leagues (Challengers, ITF men's and women's, a WTA 125, a 250, the Davis Cup, both Finals). Two calls hold the whole sport: every matchup (a match is a Sets parent and a Games child), and every price with its version and stake limit. Logged every 30 minutes from 2026-11-13 into `tennis_pinnacle_matchups` and `tennis_pinnacle_prices` (`data/ingestors/tennis_pinnacle.py`); the first pass held 121 matchups and 1,079 prices. It priced both Finals while the odds feed showed no Pinnacle for them. |
| TennisExplorer's results pages (`tennisexplorer.com/results/?type=atp-single` or `wta-single`) | Every level on one page a day per tour: both players (a stable profile link), sets, games with tiebreak points, two decimal prices. Robots allow the results pages; the terms page is closed to crawlers, so not read. 2025-08-31 men's: 417 matches, 290 ITF (23 priced), 75 Challenger (74 priced), 48 other (UTR series, a team league: dropped). Collecting 2020-01-01 to date into `tennis_te_matches`, one page every 2 seconds (`data/ingestors/tennis_explorer.py`). |
| DraftKings' own site | Every level. Its tennis page of 2026-11-13 named 54 leagues, 38 of them singles. Read by `scripts/tennis_dk_probe.py` from mike's terminal (a Claude session's read was refused by the permission check, twice), every 30 minutes into `tennis_dk_selections`, every selection of every market page, change-only. Its first pass (15:08 ET) stored 425 prices on 50 matches in 31 leagues. **What it offers by level**, read off the 31 boards: ITF events list the match winner alone before a match; Challengers and the WTA 125 add games spread, total games, set spread, set betting and each set's winner, total and correct score; tour events add the first-set winner, tiebreak, ace, service-game, break-of-serve, player-games and win-every-set props (33 market pages on the ATP Finals). The four Grand Slams show outright winners only. |
| ESPN, Challengers and ITF | None: ESPN's 2025 men's results hold 61 events (the tour, every 250) and its women's 106 (the tour and the 125s); no Challenger or ITF event. |
| tennis-data.co.uk (one price per match: Bet365, Pinnacle, best, average) | **Refused**: a Cloudflare block ("Sorry, you have been blocked") from mike's PC on 2026-11-13, its notes page too. Copies of its files on GitHub are not used. |
| Betfair historical data | BASIC (one-minute last traded price) is free with an account, from 2016 (scout). Not used: no account. |

## TennisExplorer's prices

Measured on the 11 trial matches both sources hold (2025-08-29 to 31, the men's
US Open), against the bought prices for the same matches. TennisExplorer's
pair carries a median overround of 5.3% (3.6% to 5.8%): an average of books,
not one sharp book (Pinnacle's runs near 3%) and not an exchange. It sits
closest to the average of the seven decidable books' last prices before the
start (mean gap 0.37 in decimal odds, equal on 3 of 11), further from
Pinnacle's last (0.55, never equal), Pinnacle's first (0.81) and the Betfair
exchange (2.30). So it is a consensus near the close: a baseline a model can
be ranked against, and **not a price a pick could have been decided at**.

## The listed start is not the start

Measured on the trial's 16 matches (2025-08-30, all 16 linked to ESPN by the
two players' names within 60 hours). The feed revised the listed start on 13
of them. For the day's later matches it was 10 to 60 minutes before ESPN's
start; for the next round's (not yet scheduled) it was a placeholder up to 29
hours early; once it was 10 minutes after ESPN's start (Sinner v Shapovalov,
17:30 against 17:20). When a match goes live the feed stamps the start to the
second (Musetti v Cobolli 15:03:57, ESPN 15:10; Wong v Rublev 18:04:47, ESPN
18:00), so the two disagree by up to about 10 minutes either way.

So every research read keeps a quote only when its snapshot and its last
update are at least 10 minutes before the earlier of ESPN's start and the
feed's last listed start (`scripts/tennis_market_study.pre_match`). A live
model decides at a fixed lead before the listed start (books first post a
median 17 to 19 hours before it: DraftKings 18.1, Pinnacle 18.6), far from
the start, and never on a match ESPN shows in progress.

## Settlement — read before grading anything

`models/tennis_common.py` states each rule and grades by it. The sources:

- **DraftKings** (house rules, Massachusetts edition dated 8.1.24, p. 47-48,
  read 2026-11-13): moneyline void if a player retires before the first set
  is complete; after it, *"the player or pairing progressing to the next round
  ... will be settled as the winner. Moneyline bets placed on the retiring or
  disqualified player or pairing will be void."* ITF matches: void on any
  retirement. Games spread and total games: graded on lines already decided
  once a set is complete (total games at the fewest games the match could
  have finished in), the rest void. A tiebreak and a super tiebreak each count
  as one game.
- **Pinnacle** (its rules page, via the scout): the moneyline has action once
  one set is complete, so the retiring player loses; every other market is
  void unless its period finished.
- **FanDuel and BetMGM**: one set for action; **Caesars**: the full match
  (Action Network's table, updated 2026-05-04). BetRivers, Fanatics and Hard
  Rock: not read; graded as void on any retirement until they are.

**Why it matters.** The men's tour file for 2025 holds 2,944 matches, 109
of them ended by a retirement and 22 walkovers. The archive lists the player
who advanced as the winner, so a retiring player is always its loser, and the
retiring player was usually behind: ahead on completed sets in only 9 of the
109. So a bet on a player at DraftKings carries an option no sharp book gives:
if that player retires after the first set, the stake comes back. Priced off a sharp book's
number, every DraftKings moneyline is worth about the retirement chance of
the side bet more than its price says. That is a mechanism, not yet a result
(see the grid).

**How much the option is worth** (the archive, tour-level matches 2015-2026,
walkovers out: 86,797 matches, 173,594 player-matches;
`python -m scripts.tennis_retirement_rates`, run 2026-11-13). A player retires after the first set is complete in **1.13%** of
their matches: men 1.14%, women 1.13%; men's Grand Slams 1.24% a side, women's
0.48%. The retiring player was the rating underdog in 51.8% of the 1,965
cases, so the option is not a disguised underdog bet. What moves it:

| Player-match | Retirement after set one | Player-matches |
|---|---|---|
| all | 1.13% | 173,594 |
| previous match in the same event over 3½ hours | 3.02% | 927 |
| previous match in the same event 2½ to 3½ hours | 1.17% | 7,856 |
| previous match in the same event under 1½ hours | 0.99% | 31,791 |
| retired after a set within the last 30 days | 1.73% | 4,347 |
| no such retirement in the last 180 days | 1.05% | 148,621 |
| men's best of five | 1.67% | 11,586 |
| aged 30 to 33 | 1.39% | 21,295 |
| aged under 22 | 0.94% | 29,834 |
| grass | 0.86% | 20,064 |

DraftKings' two prices on the 2026-11-13 WTA Finals match (-295 and +232)
carry a 4.8% overround, about 2.4 points a side. So the option hands back
about half of DraftKings' margin on an average bet, and up to all of it on the
riskiest player-matches: alone it is not an edge. Its value is as a term
added to every DraftKings price when that price is compared with a sharp
book's no-vig number (mechanism 1 below).

## The market grid

| Market | Settles on | Inputs held | Prices | Baseline | Method | Result | Status |
|---|---|---|---|---|---|---|---|
| Match winner | the player who advances; retirement and walkover rules per book (above) | results 2000-2026 (archive), 2010-2026 (ESPN); Elo; serve and return counts | DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers, Hard Rock; Pinnacle and the Betfair exchange as references; from 2020-09 | to do | line shop against the sharp reference at one snapshot; DraftKings' retirement option; ratings and fatigue as an anchored adjustment | — | to do (needs the purchase) |
| Games spread | games won by each player, completed matches | the same | BetRivers and Caesars (decidable); Pinnacle, Bovada, LowVig, BetOnline, Bally, betPARX | to do | a serve-and-return game model against the line; line shop | — | to do (needs the purchase) |
| Total games | both players' games, a tiebreak one game | the same | the same books | to do | a serve-and-return game model (hold rates, tiebreak chance); line shop | — | to do (needs the purchase) |
| First-set winner | set one | the same | BetMGM and LeoVegas only, per-event endpoint | | | | parked: one decidable book, history only by the per-event endpoint |
| **Below the top tier** (men's 250s, Challengers and ITF; women's 125s and ITF), all three markets | as above; DraftKings voids an ITF moneyline on any retirement | results: ESPN for the 250s and 125s, TennisExplorer for every level from 2020 (collecting), the archive to June 2026 | the odds feed: none (it sells only its 53 keys). Pinnacle direct: every level, from 2026-11-13 (collecting). TennisExplorer: one price pair a match, an average of books near the close (below), from 2020 (collecting). **DraftKings, from 2026-11-13**: the match winner at every level, games spread and total games from the Challenger and 125 level up | to do | ratings, serve and return, fatigue and retirement models against Pinnacle's price at the same moment | — | **collecting**: a backtest at a price we could have bet starts from 2026-11-13; before that, research ranks models against Pinnacle and the average close only |
| Alternate games spreads and totals | as above | | LeoVegas, Coral, Ladbrokes | | | | parked: no decidable book |
| Player games, aces, double faults, set betting | | | none: the feed rejects or returns nothing for these keys | | | | parked: no price source |
| In play | | | the feed serves in-play tennis prices | | | | parked: no point-by-point feed |
| Outrights | | | `has_outrights` false on every tennis key | | | | parked: no price source |

## Mechanisms to test (from the scout, and our own)

Fixed before any result is read: the decision times (each book's first post;
the latest quote 12 hours before the listed start; the latest before the
start), the decidable books, and Pinnacle's no-vig price at the same snapshot
as the reference.

1. **DraftKings' retirement option** (own; the settlement rule above). Bet
   DraftKings when `P_ref × decimal − 1 + P(retire after set one) > floor`,
   with the retirement chance modelled on the archive (age, previous match
   length, recent retirements, surface, heat). Prediction: DraftKings bets on
   the side more likely to retire return more than the same bets graded at
   Pinnacle's rule, by about that chance.
2. **Line shop against the sharp reference** at one snapshot (catalog §2).
3. **Total games and games spreads from a serve-and-return model** (own; the
   scout found no published test of these markets). Prediction: books set the
   total off the match price; two strong servers (more tiebreaks, fewer
   breaks) go over the line more often than the line's own probability says.
4. **Fatigue known at the next match's first post** (scout: men's Grand Slam
   win rate against surface Elo falls from 1.07 after a match under 1:30 to
   0.76 after one of 4:30 or more). Test against the market's own number.
5. **Best of five priced like best of three** (own): at men's Slams the
   better player's edge compounds over five sets; check whether the books'
   games spreads at Slams carry it.
6. **The favourite-longshot bias at soft books** (scout: Lahvicka 2014,
   Forrest and McHale 2007): blind favourites and dogs by price band at each
   decidable book's close, against Pinnacle's.

## The scout's leads (2026-11-13)

| Lead | Claim | Evidence | Test here |
|---|---|---|---|
| Lyócsa and Výrost 2018 (40 rules, data-snooping check) | apparent rules fade after correction | strong, for the null | apply a multiple-testing correction to every swept cut |
| Valtonen 2013 (7,555 men's matches at Betfair's close) | no favourite-longshot bias at the exchange close | strong, for the null | calibration of Pinnacle's no-vig close on our matches |
| Clegg and Cartlidge 2025 (8,375 matches) | Elo Brier 0.215 against Pinnacle's 0.196 | strong: Elo trails the market | the same order here: `models/tennis_ratings.py` on men's tour matches between players with 10+ rated matches, Brier 0.2176, 0.2152, 0.2188 in 2023, 2024, 2025 (a different test set from theirs) |
| Tennis Abstract 2017 (7,200 men's Slam matches) | previous-match length cuts the next win rate | weak (against Elo, not the market) | mechanism 4 |
| Point-based models (Barnett and Clarke 2005, Ingram 2019) | hold and break probabilities price games | weak; no betting test of games markets found anywhere | mechanism 3 |
| `pietroschiona/trading_alpha_tennis` | 63-65% win rate on 6,000 bets at Pinnacle's open | noise: its flat-stake equity implies +30% return, its "edge" is the close minus the open, its data is synthetic | none |
| BuzzFeed's 2016 line-move study | about 11% of matches move 10+ points of probability at a book | weak for edge | measure how far DraftKings lags a large Pinnacle move |

## The purchase

**The coverage sweep (2026-11-13, 332 credits plus 5 for one repair).** Three
history event lists per key and year find each window: asked at the end of the
year, the feed answers with the key's last snapshot; asked 40 days before that,
its `next_timestamp` is the window's first listing. Every answer is a row in
`tennis_odds_fetches` (endpoint `events`). **129 windows**: 4 in 2020, 8 a year
in 2021 to 2023 (the Grand Slams only), 17 in 2024, 31 in 2025, 53 in 2026. A
Grand Slam window runs 14 to 17 days (qualifying is listed from about three
days before the main draw). Three windows are odd and kept: the 2024 women's
US Open key runs 33 days (to 2024-09-25), the 2026 women's Madrid key 27 days
(from 2026-04-05), and the women's Rome key held a second listing in July 2025
(13 to 16 July) after its real event (6 to 17 May). That last case is why the
sweep repeats when the snapshot before a window is in the same year: the first
version found only the July listing.

**The plan.** Every window, newest first, one ask an hour for both groups of
ten books (60 credits an ask), each ask moved forward to the feed's next real
snapshot when it kept nothing in between: **38,204 asks, at most 2,292,240
credits** (`--plan`). Hours with no snapshot are not billed twice, so the real
bill is lower; Grand Slam days bill at the ceiling (the trial's 25 asks were
25 fresh snapshots). It buys every match the feed priced on these keys since
the 2020 US Open at DraftKings, FanDuel, BetMGM, Caesars, Fanatics, BetRivers,
Hard Rock, Pinnacle, Bovada, betPARX, the Betfair and Matchbook exchanges,
LowVig, BetOnline, Bally, ESPN BET, Marathonbet, Unibet, William Hill and
BetAnySports, in all three markets.

**Credits, read 2026-11-13.** The plan is 15,000,000 a month since 2026-11-08
(`odds_api_quota`: 19,666 used that day against 4,630,560 the day before).
5,814,551 left after the sweep; 5,772,644 were used on 11-13 before this build
spent anything. Measured burn 83,982 a day (`odds_quota.daily_burn`). The
run's floor is that burn for every day to the reset plus seven: **2,687,424**,
assuming the reset is 2026-12-08 (the later of the two candidates: earlier
cycles reset on the 1st). At the ceiling the purchase leaves about 3.5 million.
The meter stops the run at the floor whatever else is spending.

    python C:/Users/micha/tennis_research/run_with_db.py data.ingestors.tennis_odds_history         --buy C:/Users/micha/tennis_research/coverage_windows.json --step-min 60 --max-credits 2300000

**The purchase, as run (2026-11-13, mike's yes).** Launched 10:29 ET in six
shards whose ceilings summed to the plan. Two shards stopped on a database
connection lost at a commit and were relaunched on code that reconnects and
replays bought hours from the ledger for 0 credits. All six then stopped at the
7-day-reserve floor (account about 2,687,300); mike: *"lower the floor it's
fine"*, and six follow-on jobs continued with no reserve days (floor
2,099,550). Other jobs drew the account to that floor with three windows left
(the 2020 men's French Open, the last five days of the 2021 men's Wimbledon,
the last day of the 2021 women's Australian Open); mike: *"put the odds api
floor to zero"*, and those three were bought with no floor (32,640 credits).
**Result: all 129 windows, 74,803 calls, 2,242,680 credits** (the ledger,
`tennis_odds_fetches` source `odds_api_tennis_history`), **2,996,347
change-only prices on 17,071 matches** in `tennis_odds_quotes`; account at
1,989,219 afterwards. The calls are missing from `api_call_log`: the purchaser
imported `config` too late to install the call logger (fixed for later runs).

**The forward log (from 2026-11-13).** Every active tennis key, both book
groups, every 20 minutes, through the live endpoint (12 credits a pass),
stored in `tennis_odds_quotes` beside the history (`tennis_odds_fetches`
endpoint `live`). Started on mike's PC for the two Finals, until 2026-11-23.

**The trial (2026-11-13).** One day, the 2025 US Open men's key, hourly asks
from 2025-08-30 00:00 to 2025-08-31 00:00 UTC, both groups of ten books: 25
asks, **1,500 credits**, 2,861 change-only quotes on the 16 third-round
matches, 30 books (Pinnacle's match-winner on 127 rows, its games spread on
125).

**The study path, run end to end on the trial** (`scripts/tennis_market_study.
moneyline_candidates`, a plumbing check, not a result: one day). Ten of the 16
matches had a Pinnacle price inside the pre-match bound; at the 12-hours-out
decision the seven decidable books quoted 140 prices (both sides of each), and
their median EV against Pinnacle's no-vig price at the same snapshot was
-4.8% (-4.6% at the first post, -4.7% at the close). Three of the 16 matches
ended in a retirement, so 32 of the 140 graded VOID at the books' own rules.
Every decidable book's margin there is about twice the 2.4 points a side the
single women's quote suggested, so the retirement option (1.1 points) does not
cover it on an average quote; any edge is in the quotes that stand apart.

## Open items

- The research on the bought history: the baselines on every grid row,
  mechanisms 1 to 6 in that order, the kill tests on anything positive.
- The forward log runs on mike's PC until 2026-11-23; a worker job takes it
  over when the first model ships.
- The code graph is rebuilt and named once, after the last code change of
  this build, before its merge.

- Pinnacle on the feed's tennis board is thin and late (answered 2026-11-13,
  #1278): the women's Finals matches of that evening got no Pinnacle quote on
  the feed at all, and the men's Finals matches of 11-15 got their first one
  at 19:23 UTC on 11-13 (6 quotes), while Pinnacle's own site priced every one
  of them all day. A live model's sharp reference is Pinnacle's own site
  (`tennis_pinnacle_prices`), with the feed's Pinnacle as a second copy.
- DraftKings' own price, checked against the feed's DraftKings price for the
  same match (Sabalenka v Svitolina, 2026-11-13): -237 / +190 from the reader
  at 20:07 UTC, -237 / +190 from the feed at 20:04 UTC.
- DraftKings' rules are the Massachusetts edition of 2024-08-01; read the
  current rules page before the retirement option goes live.
- The archive's licence is non-commercial (above).
