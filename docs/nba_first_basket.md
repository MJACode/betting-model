# NBA first basket: a market this project has never priced

mike, 2026-11-20, after NBA went 0-6 on 2026-11-19: *"You need to fucking invent a new way to make
this profitable."* Every earlier NBA search (about 280 graded ideas, `docs/nba_reassessment_2026_11.md`)
priced spreads, totals, team totals, alternates and stat props. None priced who scores first. This
file is the record of that market: what drives it, a fair price, what the books charge, and what is
still unknown. Results are in units where there are any; there are none yet.

Research scripts (not in the repo; they read the local Supabase mirror and write under
`<R>/first_basket/`, `<R>` = `data/local/research/nba_research`):
`scripts/fb_model.py` (the facts and the walk-forward grade), `scripts/fb_price.py` (store bought
quotes in Supabase, price a board), `scripts/fb_probe_live.py`, `scripts/fb_probe_hist.py`.

## 1. The market

| Market (Odds API key) | Settles on | Books quoting it (2026-11-20) | Their margin |
|---|---|---|---|
| `player_first_basket` | the game's first score of any kind, free throws included | DraftKings, FanDuel, BetMGM, Caesars, Fanatics, Hard Rock, Courtside; BetRivers in history | 11.6% (Caesars) to 32.4% (Fanatics) over the ten listed starters on one game; median 19.7% over 53 book-games on 2026-11-20's 9 games (FanDuel 16.1%, DraftKings 18.3%, Fanatics 19.7%, Hard Rock 21.3%, BetMGM 22.0%, Caesars 23.3%) |
| `player_first_team_basket` | each team's first score | FanDuel on the live probe; FanDuel, DraftKings, Hard Rock, BetMGM, BetRivers in history (2026-01-15) | not measured |

Prices: live 1 credit an event a market (`x-requests-last` 4 for two markets at two regions);
history 10 credits an event a market with up to ten books named (`x-requests-last` 10). History
exists on 2024-03-15, 2024-11-15 and 2026-01-15 and not on 2023-11-15 or 2024-01-10 (both billed 0),
so it starts between 2024-01-10 and 2024-03-15; `player_first_team_basket` history is there on 2026-01-15.
Every quote bought for this file is stored in `player_prop_odds` (305 rows, `market IN ('player_first_basket','player_first_team_basket')`).

## 2. What drives it (stored play-by-play, 2018-19 to 2026-27)

Read from `nba_first_basket_games` (the Stats tab's table, Matt 2026-11-08) and the mirror's
`nba_pbp` / `nba_pbp_box`:

- **The tip is a skill.** 33 jumpers with 30+ opening tips in 2025-26: split-half correlation of tip
  win rate 0.79, first-half rates from 0.20 to 0.93.
- **The tip decides the first score.** The team that won the tip scored first 66.6% of the time in
  2025-26 (2,462 team-games) and 61.1% so far in 2026-27 (452).
- **Stardom does not.** Sharing the first score by points per game among the five starters prices
  it worse than giving each starter a fifth (log loss below, every season).

## 3. The fair price

`fb_model.py`, walk-forward: each game is priced from games on earlier dates only.

- Tip: each jumper's opening-tip win rate, shrunk toward 0.5 (Beta, `a_tip`), seasons decayed by half;
  the jumper is the starter who jumped most in his team's last 15 games. Two jumpers by log5.
- Team first = c x P(tip) + (1 - c) x (1 - P(tip)), c the running league rate (prior 0.64).
- Each starter's share of his team's first score: his team-first scores over his starts (decayed),
  shrunk toward his points share (`k_share`), normalised over the five, less the bench's share.
- Settings chosen on 2019-20..2022-23 only: `a_tip` 2, `k_share` 40 (the grid is flat: 0.32141 to
  0.32200 over nine settings). Graded on the four seasons after.

| Season | Starter-games | Log loss: model | uniform fifth | points share | Tip log loss (coin 0.6931) |
|---|---|---|---|---|---|
| 2023-24 | 12,310 | **0.32057** | 0.32508 | 0.32512 | 0.6294 |
| 2024-25 | 12,310 | **0.32289** | 0.32508 | 0.32719 | 0.6389 |
| 2025-26 | 12,310 | **0.32184** | 0.32508 | 0.32483 | 0.6262 |
| 2026-27 (to 11-18) | 2,220 | **0.31921** | 0.32508 | 0.32230 | 0.6322 |

Team-first calibration on the test seasons: claimed 0.417 won 0.396 (1,246 team-games); claimed 0.583
won 0.604 (1,246). The model under-states the tip at both ends. Player calibration: the lowest tenth
claims 0.050 and wins 0.069; the 0.128-0.144 tenth claims 0.135 and wins 0.124.

## 4. Tonight's board (2026-11-20, read about 12:00Z, before lineups)

Eight of nine games priced (NOP's listed players at NOP v OKC mapped to four starters, not five). Best price per
player: 7 of 80 at an EV of 0.10 or more, every one of them a price of +800 or longer, most at
DraftKings (`<R>/first_basket/board_2026-11-20.parquet`). Example: Kelly Oubre Jr. +1400 at
DraftKings, the model 0.093 against DraftKings' no-vig 0.060.

**This is not evidence of profit.** It is one board, read before lineups, and the long prices are where
books shade hardest and where the model's calibration is least tested.

## 5. What is not known, and the test that answers it

Whether the fair price beats the books' prices after their margin. The only test is the model graded
at the prices on sale before each tip, walk-forward, for every listed starter (the evaluation rule):
units, ROI with an interval, by season and early/late, as a neighbourhood of EV floors.

That needs the history (section 1). `scripts/fb_buy_history.py --dry-run` (2026-11-20, spent 0): 3,369
finished regular-season games from 2024-01-10 to 2026-11-19, 2,168 snapshot times, 6,736 market-calls
for both markets, one snapshot 10 minutes before each tip with the seven deciding books in one
request. **Ceiling 69,528 credits** (events 2,168 + odds 67,360), taken from that plan. Games before
history starts bill 0, so the spend is lower. Balance 1,357,416; the reserve floor is 387,639 (7 days at
the median 55,377 a day, `odds_quota.plan_credit_budget`). The grade must split by price band and by
the player's prior starts (tonight's 0.10+ EV prices were all +875 or longer, four of seven rookies).

Forward from the merge of the change that adds both markets to `config.PROP_MARKETS_NBA`, every
refresh pass and prop window job stores the boards, so the price path to tip is collected every night.
Those passes land about every 10 minutes in the last hour, the last about a minute before tip
(NBA_2026-11-19_GSW_MEM, DraftKings points), so the forward boards hold the point the history buys.

## 6. The grade at real prices (2026-11-20): nothing passes; the blend fails only the interval

mike said yes to the history on 2026-11-20. `fb_buy_history.py` stored 246,350 rows on 3,094 games in
its final run and billed 50,698 credits (its own count of `x-requests-last`; three earlier runs,
restarted for speed and for an unhandled 502, stored the first 266 games and did not log a total).
273 games had no quote. Balance afterwards 1,286,602 (2026-11-20 21:37Z, all spending included).
Stored, by season: `player_first_basket` 684 / 1,228 / 1,230 / 226 games (2023-24 from January),
`player_first_team_basket` 304 / 1,230 / 226 from 2024-25.

Three tests, each written in `<R>/first_basket/prereg.md` before it was computed, each against six
bars: 200+ bets; the ROI interval above zero (bootstrap over game dates); positive in each full
season; the floors either side positive; positive before and after day 45; the probability beating the
books' own fair price. One bet a game (a team, for the team market), best of the seven books, 1 unit
to win.

| Test | Bets | Units | ROI (95% interval) | Bars passed | Fails |
|---|---|---|---|---|---|
| 1. The model alone, first basket, EV 0.10, graded 2024..2027 | 2,924 | +18.78 | +5.9% (-4.8 to +16.7) | 4 | the interval; the books' median prices it better (log loss 0.32142 against 0.32249) |
| 2a. The other books' median price alone, EV 0.05, 2024-25 on | 1,953 | +6.24 | +3.2% (-10.5 to +16.6) | 3 | the interval, 2025-26 (-2.0%), the first 45 days |
| 2b. Blend, 0.25 model + 0.75 the other books' median (weight fitted on 2023-24), EV 0.05 | 1,930 | +14.56 | +7.5% (-5.0 to +20.9) | 5 | the interval |
| 3. The same blend on the team market, EV 0.05 | 1,056 | +25.14 | +9.5% (-3.8 to +22.6) | 5 | the interval |

What the blend shows: positive in every season graded (2b: +8.5% 2024-25, +7.9% 2025-26; 3: +17.9%,
+8.2%), at every floor tried, and before and after day 45, and it predicts the first scorer slightly
better than the books' median. What it does not show: an interval clear of zero. Its bets are priced
around +1000 (first basket) and +425 (team), so about 2,000 and 1,000 bets cannot tell +8% from 0.

**The team market cannot be bet by this rule this season.** Of the seven books only DraftKings (221
games) and FanDuel (226) quote it in 2026-27; BetMGM, BetRivers and Hard Rock did in 2025-26. The rule
needs three other books for its fair price.

Not registered, seen in test 1's splits, not acted on: home starters +19.4% (1,265 bets) against away
-4.6%; bets taken at FanDuel +23.1% (861).

Files: `<R>/first_basket/grade_*.csv|parquet`, `grade2_*`, `grade3_bets.parquet`; scripts
`fb_grade.py`, `fb_grade2.py`, `fb_grade3.py`.
