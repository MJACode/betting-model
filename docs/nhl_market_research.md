# NHL 2026-27: markets, data, what has actually made money, and a plan

> Researched 2026-09-20 (michael: *"explore all NHL markets and start to craft
> an approach to profitable / +EV / CLV winning models … do not make
> assumptions"*). Every number below names the query, call or page that
> produced it. **UNVERIFIED** means the page would not load or was only seen as
> a search snippet — nothing here is filled in from memory.
>
> Not reached at all: Reddit (the fetch tool refuses reddit.com and
> old.reddit.com), X/Twitter, and web.archive.org. No Reddit or X evidence is
> in this document.

## 0. The five things that matter

1. **The regular season starts 2026-09-29, not in October**, and it is **84
   games** a team, not 82 (`api-web.nhle.com/v1/schedule/2026-09-29`:
   `regularSeasonStartDate 2026-09-29`; `/club-schedule-season/{team}/20262027`
   returned 84 for 5 of 5 teams checked, 82 for 20252026).
2. **The NHL pipeline has never produced a pick** (`picks` where `sport='NHL'` or `model_id like 'nhl%'` or
   `game_id like 'NHL_%'` → 0 rows) and opening night is its first production run. Six
   defects found on the way (§1) would each corrupt that run.
3. **The two existing models were trained on the future, and on honest inputs
   the moneyline model is about as good as quoting the home-win rate.**
   Walk-forward mean AUC 0.605 with the leaked goalie inputs, 0.582 with them
   removed, **0.585 on the rebuilt inputs** with log loss 0.692 against 0.691
   for the home-win rate — and 0.655-0.674 for the market's close (§2, §5).
   *Corrected 2026-09-20: an earlier version of this item said 0.563 and
   called six inputs leaked. Three were; see §2.*
4. **The best-evidenced fact about NHL betting is that the moneyline close is
   efficient** — four independent large-sample null results (§5). The best
   public models roughly *match* the Pinnacle close; none has a published
   record of beating it with a sample that means anything. For player props
   there is **no independent record at all**, in either direction.
5. **Everything needed to test ideas honestly is already paid for.** The Odds
   API plan carries DraftKings + Pinnacle NHL game lines from the 2020-21
   season and props + the regulation 3-way line from 2023-05-03 (§3). The NHL's
   own free API carries per-game skater, goalie, shift and shot-location data
   (§4). We store none of it today.

---

## 1. Defects found in the NHL pipeline (all measured 2026-09-20, none fixed here)

| # | What is wrong | Evidence | Consequence on 2026-09-29 |
|---|---|---|---|
| 1 | Two teams are stored under invented ids. The odds feed spells them `Montréal Canadiens` and `St Louis Blues`; `NHL_ODDS_API_MAP` has `Montreal Canadiens` and `St. Louis Blues`; the fallback takes the first three letters of the last word. | Worker log 2026-09-20 14:17Z: `Unknown NHL team name from Odds API: 'Montréal Canadiens' → using 'CAN'` / `'St Louis Blues' → using 'BLU'`. `games` holds `NHL_2026-09-29_CAN_TOR`, `NHL_2026-10-02_BLU_DAL` etc. Stats tables use `MTL` / `STL`. `data/ingestors/odds_ingestor.py:288-292`. | Those games join to no team stats; when the schedule ingestor writes `…_MTL_TOR` the game exists twice. |
| 2 | The season label splits opening week in two. Four call sites use `month >= 10` to roll to the ending-year label. | `games`: 09-29 and 09-30 rows are `season 2026`, 10-01 onward `season 2027`. `run_pipeline.py:515`, `odds_ingestor.py:848`, `nhl_stats_ingestor.py:147, 824`. | This season's games land in two seasons. The 09-29/30 games join season-2026 stats rows, which today carry last season's finals (`games_played 82` for BOS and TOR at `as_of_date 2026-09-20`), so the early-season guard sees a mid-season team; 10-01 onward joins season-2027 rows that do not exist yet. The rule is wrong for this season and for any future September start. |
| 3 | Every probable goalie gets the same goalie's numbers. The ingestor matches on `goalieId`; the NHL stats API sends `playerId` (and `goalieId: null`). With no id, `"" == ""` matches the first row for everyone. | All 28 season-2026 rows in `nhl_goalie_stats` read save% 0.7143 / GAA 8.8999 (Markstrom, Vasilevskiy, Sorokin, Saros…), `player_id` NULL. Live API call: keys include `playerId`, not `goalieId`. `nhl_stats_ingestor.py:612-632`. | The three goalie features are identical for both teams in every game. |
| 4 | "GSAA" is a copy of goals-against average. | `nhl_stats_ingestor.py:671, 915` (`# placeholder`); table rows have `gsaa = gaa` to the digit. | `d_goalie_gsaa` (a top-5 feature of the trained model) duplicates `d_goalie_gaa`. |
| 5 | The regulation 3-way line is requested under a key the feed does not document. We ask for `h2h_3way`; the documented key is `h2h_3_way`. | `odds_ingestor.py:128`; the-odds-api.com betting-markets page; the research probe got NHL 3-way prices back under `h2h_3_way` (DraftKings and Pinnacle, 2023-11-15 and 2025-01-15). `odds` holds **zero** non-h2h/spreads/totals NHL rows, ever. | `nhl_moneyline_regulation` has never had a price to score against and will not get one. Strong evidence, not yet proven end-to-end: one per-event call on an opening-night game settles it. |
| 6 | The whole 2025-26 season is missing from `games`. | `select count(*) from games where sport='NHL' and game_date between '2025-07-01' and '2026-08-31'` → 0. Seasons 2019-2025 are complete (1,082-1,401 games each). | No prior-season baseline for the early-season blend; one fewer season to train and test on. The NHL API is reachable from this machine (HTTP 200), so it is a backfill, not a blocker. |

Also noted: `nhl_skater_stats` has 0 rows; `player_prop_odds` has 0 NHL rows;
`nhl_over_under` and `nhl_puckline` have never been trained (no historical
lines). I searched `config.py` for a switch that holds an un-gated model back
from publishing and found only the pause list, which holds no NHL model — so
as things stand a BET from either NHL model publishes like any other.

## 2. The existing models, re-measured on clean inputs

Both were trained 2026-06-21 (`model_registry` ids 77, 78), before the
2026-09-03 team-stats rebuild, and have not been retrained.

**CORRECTION (2026-09-20, same day).** The first version of this section said
six inputs were leaked. **Three were.** The team rates were constant within a
season, which I read as "the season's final number"; reading the rebuild code
and checking Boston against the NHL API showed they were the PRIOR season's
finals (table season 2025: PP .2222 / PK .8246 = the API's 2023-24 finals) —
stale, but known before the season started, so not a leak. The 0.563 figure
below came from removing those three honest inputs as well, and understates
the model. The goalie finding stands, to the digit.

**What was season-final in the training data** (so the model was told how the
season ended):

- Goalie save%, GAA, "GSAA": one row per team-season dated `YYYY-10-01`. BOS
  2025 read Swayman .8921 / 3.1145 — his **final** 2024-25 line per the NHL
  API, to the digit. The feature engine takes "latest row on or before game
  date", which was that row for every game.

**What was stale but honest:** `corsi_for_pct`, `power_play_pct`,
`penalty_kill_pct`, `shots_per_game` — at most one distinct value per
team-season 2020-2025, the prior season's final (none at all in 2019).

That is 3 leaked and 3 stale of the model's 22 features. The other team inputs were checked the
same way and do vary: goals home / away, last-5, last-10, goals against and
wins have at least 13 distinct values in every team-season 2019-2025.

**Walk-forward, `scripts/walk_forward_eval.py`, fixed XGBoost params, same
rows in both runs:**

| Test season | n | AUC, all 22 (goalie leak in) | AUC, 3 goalie inputs removed | AUC, 6 removed (over-strict) |
|---|---|---|---|---|
| 2021 | 834 | 0.594 | 0.556 | 0.536 |
| 2022 | 1,197 | 0.588 | 0.581 | 0.554 |
| 2023 | 1,277 | 0.622 | 0.601 | 0.585 |
| 2024 | 1,275 | 0.618 | 0.591 | 0.578 |
| mean | | **0.605** | **0.582** | 0.563 |

**After the rebuild** (every goalie number and team rate summed from per-game
logs strictly before the game date — `data/nhl_asof.py`; 2025-26 backfilled;
same fixed params; `base ll` is the log loss of quoting the training-set
home-win rate for every game):

| Test season | n | AUC | Brier | log loss | base ll |
|---|---|---|---|---|---|
| 2021 | 909 | 0.547 | 0.261 | 0.721 | 0.692 |
| 2022 | 1,351 | 0.605 | 0.244 | 0.686 | 0.690 |
| 2023 | 1,356 | 0.602 | 0.247 | 0.690 | 0.693 |
| 2024 | 1,355 | 0.615 | 0.242 | 0.678 | 0.691 |
| 2025 | 1,353 | 0.595 | 0.243 | 0.680 | 0.687 |
| 2026 | 1,352 | 0.548 | 0.252 | 0.699 | 0.693 |
| mean | | **0.585** | | **0.692** | 0.691 |

Dropping the three goalie inputs entirely scores 0.592 / log loss 0.690 — the
honest goalie numbers add nothing measurable at fixed parameters. The
published closes in §5 run 0.655-0.674 log loss. **A model at 0.69 does not
know more than a market at 0.66**; whatever "edge" it shows against a posted
line is the model's error, not the book's.

For scale: Lopez, Matthews & Baumer measured the **market's** AUC on 12,990
NHL games at 0.595. The registry's 60.4% / AUC 0.642 holdout was trained
2026-06-21, before the team-stats rebuild, when every input was its own
season's final (`docs/team_stats_leak.md`).
What this does *not* measure: profit. There are no historical NHL prices in
the database to grade against (the recorded "+22.6%" backtest assumed −110 on
every game).

## 3. Historical odds — what exists (full source table in the research notes)

| Season | Moneyline / puck line / total | Pinnacle | Regulation 3-way | Player props |
|---|---|---|---|---|
| 2018-19, 2019-20 | Sportsbook Reviews Online archive only (book not named; ML open+close, total open+close, one puck-line price; frozen at 2022-11-27) | none found | none found | none found |
| 2020-21 → 2022-23 | The Odds API, DraftKings + Pinnacle, 10-min snapshots (5-min from 2022-09) | yes, from between 2020-08-05 and 2020-09-19 | from 2023-05-03 only | from 2023-05-03 only |
| 2023-24 → 2025-26 | The Odds API | yes | yes (DK + Pinnacle seen) | yes (DK + Pinnacle seen: points, shots on goal, assists, saves, anytime scorer) |

Measured on live historical calls by the research probe (11 calls, **473
credits**, spent without asking first — see the session entry):

- Bulk history costs 10 credits × markets × regions; naming up to ten books
  counts as one region. The bulk endpoint returns the whole slate per call.
- The 3-way line and all props are per-game only: 10 × markets returned.
  The bulk endpoint rejects `h2h_3_way` with a 422.
- There is no "opening line" field. "Open" has to be defined — first snapshot
  a book shows the game, or a fixed time before puck drop.
- Thin props: blocked shots and power-play points appeared only at BetMGM /
  BetRivers / Caesars in the one 2025 game sampled; `player_goals` over/under
  only at FanDuel. One game is not a coverage study.

**Estimated backfill cost** (the formula is measured; the game-day and
start-time counts are assumptions): game lines DK+Pinnacle, open + per-slate
close, 2020-21 → 2025-26 ≈ **200,000 credits**; props + 3-way, open + close,
2023-24 → 2025-26 ≈ **672,000 credits**. Balance at 2026-09-20 14:27Z:
**988,028 of 5,000,000** (`odds_api_quota`). Any real pull goes through
`odds_quota.plan_credit_budget`, which prices the run from its own plan.

Paid alternatives add nothing we cannot already reach: the only useful overlap
is a Pinnacle-only archive (bettingiscool, EUR 99-599/month, open/close from
2021, props only from 2026-03). No verified source has NHL prop lines before
2023-05-03; SportsDataIO ("props from 2020", NHL not named, price on request)
is the one lead.

## 4. Stats and information sources

| Source | What it adds | Cost / terms | Read directly? |
|---|---|---|---|
| **NHL stats API** `api.nhle.com/stats/rest/en/skater/{summary,realtime,timeonice,powerplay}?isGame=true` | Per-game per-player shots, attempts, hits, blocks, EV / PP / SH seconds, PP shots. The missing skater log. | Free, no key. NHL.com terms say "private, non-commercial use" and bar unauthorised scraping; whether that covers the API host was not established. | yes |
| **NHL web API** `/gamecenter/{id}/boxscore`, `/play-by-play`, `/player/{id}/game-log`, `/shiftcharts` | Goalie saves / shots against by strength / `starter` flag; every shot with x/y, type, shooter, goalie, situation (the inputs to our own expected-goals model); shifts. | as above | yes |
| NHL web API `/schedule` | venue, time zone, start time → rest, back-to-backs, travel. `gameType` 1 / 2 / 3 = preseason / regular / playoffs (each seen live). | as above | yes |
| NHL EDGE endpoints | Season aggregates (shot speed, skating speed, zone time). No per-game series seen. | as above | yes |
| **MoneyPuck** downloads | Team game-by-game with expected goals by situation, 2008-09 → 2025-26 (126 MB); per-game skater / goalie / line files; shot-level file with its xG. 2026-27 files 404 today. Season label = STARTING year (ours is ending year). | **"Free to use for non-commercial purposes … For other purposes please inquire."** This platform sells memberships. | yes |
| **Daily Faceoff** starting goalies / line combinations | Goalie status, named source, ISO timestamp per item; lines, PP1/PP2, injuries. On 2026-04-09: 25 of 28 sides "Confirmed", news stamped 9.0 h → 0.3 h before puck drop, median 7.3 h (one date; final status only). | Free page, JSON embedded, no API, no terms page found. | yes |
| RotoWire lineups | "Expected" / "Confirmed" goalie label, PP units. No timestamps. | free page; subscription price UNVERIFIED | yes |
| Scouting The Refs | Referees per game; one post went up 3 h 47 m before puck drop. | free | yes (one post) |
| Evolving-Hockey | RAPM / GAR / xG tables, CSV export on Pro ($9.99/mo). | Terms bar commercial use. | price yes |
| Left Wing Lock API, SportsDataIO, Sportradar | Packaged confirmed goalies, lines, timestamped injuries. | **No price published** by any of the three. | yes |
| Natural Stat Trick, PuckPedia, ESPN NHL injuries endpoint | UNVERIFIED — 403 from this machine by every route tried. Not yet tried from the worker. | | no |

Open-source references: `sportsdataverse/fastRhockey` ships an XGBoost
expected-goals model (last push 2026-09-10); `coreyjs/nhl-api-py` tracks the
current API (2026-09-07); `HarryShomer/Hockey-Scraper` is unmaintained.

## 5. What has actually made money — graded

Grades: **A** published out-of-sample record against real lines with a sample
size · **B** credible practitioner, partial record · **C** plausible,
unverified · **D** anecdote or marketing · **A (null)** same standard, finding
is "no edge".

| Finding | Evidence | Grade |
|---|---|---|
| Blind betting by odds band loses in every band | Robbins 2023: 19,456 games 2007-23, 20 bands, −0.003% to −4.13%, difference between bands p = 0.905. "NHL odds appear to be the most efficient of the odds set we have examined." | A (null) |
| Pinnacle is as accurate at open as at close | Lahtinen 2019: 3,988 games, Brier 0.2401 open vs 0.2395 close; favourites ≈ −0.2%, underdogs ≈ −5%; no strategy significantly above zero | A (null) |
| Market probabilities are unbiased | Lopez et al. 2018: 12,990 games; market AUC 0.595 | A (null) |
| Closing log loss barely beats opening | Hockey-Statistics 2024: BetUS 0.6723 open vs 0.6709 close, ~18,850 games | A (null) |
| The best public goals-based models roughly match the Pinnacle close | HockeyViz leaderboards: 2018-19 (1,271 games) close 0.6739, Shomer 0.6718, Luszczyszyn 0.6739; 2020-21 close 0.6559, Luszczyszyn 0.6529, MoneyPuck 0.6595, HockeyViz 0.6716. Log loss derived from the site's stated scale; MoneyPuck's own 0.6596 cross-checks. | A as accuracy — not a bet record |
| Poisson goals + penalties simulation | Buttrey 2015/16: untouched 2014-15 season, 742 bets, +2.59% (standard error ≈ 3.7%, so inside one SE of zero); author says it lost in both training seasons | A− |
| Shot share + shooting% + save% + goalie ratings | Pizzola 2016-17: 341 bets, 11.7% ROI, beat the close 87.4% of the time; self-tracked; author says it "would not beat the market today" | B− |
| Betting against the public at Pinnacle's close | SportsInsights: +118.8 units / 3,281 games 2005-11 (3.6%); weaker later; −67.86 units in 2017-18. In-sample, vendor's own data | B |
| One-season ~2% backtests (Corsica vs Bovada, gschwaeb) | each *lost* to the market on log loss while showing ~2% ROI — what noise looks like | B / B− |
| xG Poisson model vs Pinnacle close | Porela 2024: 1,621 bets, −0.3% per bet | B/C (a loss) |
| Blind unders | Woodland & Woodland 2010: 52.15% on 5,475 games 2005-10, **prices assumed, not observed**; authors call it weak. 2017-18 went the other way (unders −80.81 units). | B+ in-sample, contradicted |
| Puck line either side | Action Network since 2005: favourites −2.8%, underdogs −1.8% | C+ |
| First-period totals | Barkley 2021: "about 23% ROI" over < 300 games, self-reported | C/D |
| **Bet a soft book when it is better than the sharp book's no-vig price** | Kaunitz et al. (soccer): 56,435 bets +3.5%; real money 265 bets +8.5%, then the accounts were limited. Buchdahl (football): 36,529 bets +2.36% vs +2.44% expected; forward record ~18,000 bets +3.7% vs +4.0% expected | **A — but not NHL** |
| Account limiting follows winning and beating the close | Massachusetts regulator: 0.64% of accounts limited, 57.6% of those cut to 1-24% of default stake; DraftKings' own notice wording: "targeting perceived market inefficiency" | A− |

**Player props: zero grade-A or grade-B records found for any NHL prop
market.** Nine GitHub prop projects publish no result against real lines; the
one vendor record (PropsBot, "15.1% ROI over 8,988 picks") is its own ledger.
Two measured facts that bear on props: scorekeeper bias barely moves **shots**
(only two rinks significant) but moves **blocks and hits** a lot (Schuckers &
Macdonald; a 2025 re-measure found hits narrowing); and Unabated's claim that
no book is reliably "sharp" on props, which is opinion and NFL-framed.

**Goalie timing, regulation-draw pricing, schedule spots, referees, in-play,
season point totals:** no test against real odds found for any of them.
Descriptive facts only — games tied after 60 minutes ran 20.5%-23.5% a season
2016-17 → 2024-25; backups allow ~0.15 more goals per 60 (Pinnacle); empty-net
goals were 7.0% of all goals in early 2024-25 vs 2.4% in 2005-06.

**Repeated everywhere, evidenced nowhere** (each was searched for): props are
soft / shots lines are set from season averages; books are slow after line or
power-play changes; a starter-to-backup swap moves the line 30-50 cents;
betting before goalie confirmation captures value; fade back-to-backs;
+1.5 underdogs are positive value; the regulation draw is mispriced; high-
penalty referees mean overs; first-period markets are soft; the under bias is
a standing edge; reverse line movement pays in the NHL.

**How long proof takes** (arithmetic, not a sourced figure): for flat bets
near even money the standard error of ROI is about 1/√n, so two-sided 95%
confidence needs ≈ 9,600 bets for a 2% edge, ≈ 4,300 for 3%, ≈ 1,500 for 5%.
A season is 1,344 games. A game-market edge of realistic size cannot be
confirmed in one season; **CLV can**, which is why it has to be the yardstick.

## 6. DraftKings NHL markets and how they settle

From DraftKings' house rules filed with the Massachusetts Gaming Commission
(dated 2025-08-18, hockey pp. 104-108, read in full; the 2024-08-01 filing for
the market lists). Rules can differ by state; no 2026 filing was found.

- **Moneyline, puck line, game total include overtime and the shootout**; a
  shootout adds one goal to the winner and to the total. Anything headed
  "Regulation Time", "60 minutes" or "Excl OT" does not. Period markets
  exclude overtime.
- **Skater props: void only if the player does not dress.** A player who
  dresses and never takes a shift is a LIVE bet — this changed between the
  2024 text ("must receive ice time") and the 2025 text. Overtime counts,
  shootout goals do not.
- **Goalie props are void if the goalie does not start** — the one prop where
  the book carries the confirmation risk.
- No listed-goalie rule exists for moneyline, puck line or total.
- 2024 text: the pre-game team total EXCLUDED overtime while the live 2-way
  team total included it. Current treatment UNVERIFIED — read the header.
- Payout caps in the 2024 text: $250,000 on game markets, **$20,000 on
  anything player-related**; the 2025 text replaces these with one customer
  cap DraftKings may lower "with or without notice". Stake limits are not
  published.

Markets DraftKings lists (its own category addresses, pages themselves 403):
game lines, alternate puck line / total, team totals, 60-minute game props,
first/last to score, goal in first ten minutes, period markets, goalscorer
(any / first / last, power-play goals), shots on goal, points, power-play
points, blocks, goalie saves, goalie shutout (incl. and excl. OT), futures and
awards. Hits and faceoff wins at DraftKings: UNVERIFIED. Assists: snippet only.

The Odds API keys for `icehockey_nhl`: `h2h`, `spreads`, `totals`,
`h2h_3_way`, `alternate_spreads`, `alternate_totals`, `team_totals`,
`alternate_team_totals`, the `_p1/_p2/_p3` families, and props
`player_points`, `player_assists`, `player_goals`, `player_shots_on_goal`,
`player_blocked_shots`, `player_power_play_points`, `player_total_saves`,
`player_goal_scorer_first/last/anytime`, each over/under prop with an
`_alternate`. Not served: hits, faceoffs, shutout, race-to-N, goal-in-first-10.

**No measured hold-by-market figure for NHL exists in anything found**, at
DraftKings or Pinnacle. It is computable from two-way prices once we store
them, and should be the first thing computed. Pinnacle's NHL limits
($6,000 moneyline, $3,000 regulation / spread / total on game day) are
snippet-only. Kalshi, Polymarket, ProphetX, Sporttrade and Novig all list NHL
game markets and some props; fee schedules conflict between sources and no
liquidity data was found.

## 7. A proposed approach (a proposal, not a finding)

The evidence says where *not* to expect a standing edge (predicting the
moneyline better than the close) and is silent on props. So the plan is built
to **measure first, with CLV as the yardstick**, and to reuse the two shapes
this repo already runs: sharp-vs-soft deviation (`nfl_opener_spread`) and
market-anchored props (`nfl_prop_market`).

**Step 0 — before 2026-09-29: make the pipeline tell the truth.** Fix defects
1-5, backfill 2025-26 (`games`, per-game team stats), and store per-game
goalie and skater logs from the NHL API so every feature is an as-of-date
series. Nothing else is worth building on top of the current inputs.

**Step 1 — buy the measuring stick.** Backfill DraftKings + Pinnacle game
lines 2020-21 → 2025-26 (≈ 200k credits) into `odds` with a `source` marker.
That alone answers, on the 6,551 games stored for 2020-21 → 2024-25 plus
2025-26 once it is backfilled: DraftKings' hold by market, how far DK
sits from Pinnacle's no-vig price and how often, and whether any model
candidate beats the *DraftKings* price (the only price that matters to us)
even where it cannot beat Pinnacle's.

**Step 2 — three candidates, each graded on every scored game (§7's
evaluation rule), walk-forward, plateau not peak:**

- **A. Sharp-vs-soft on NHL game lines.** Bet DraftKings when its price beats
  Pinnacle's no-vig fair by a margin. Grade-A evidence in other sports, the
  repo already has the machinery, and it needs no prediction model. Known
  ending: limits.
- **B. A goals-based team model on honest inputs** — expected goals from NHL
  shot data (our own model; MoneyPuck only if they grant permission), rolling
  goalie goals-saved-above-expected per start, rest / travel / back-to-back,
  confirmed starter. Target: match the close on log loss, then look for where
  DraftKings deviates from it. Its real use is pricing the markets nobody
  anchors well — regulation 3-way, team totals, period lines, alternates —
  from one simulated score distribution.
- **C. Market-anchored props, saves and shots on goal first.** Saves because
  the void rule removes starter risk and the inputs (shots against × save
  rate) are the most stable; shots on goal because it is a two-way market
  with alternates at both DraftKings and Pinnacle, so hold and CLV are
  measurable. Same recipe as `nfl_prop_market`: start from the no-vig line,
  adjust for what the line is slow to price (ice time, PP1 membership, opponent
  shot suppression), and require the history backfill (≈ 672k credits, three
  seasons) before believing anything.

**Step 3 — go-live per the §2 gate**, per model: paper until ≥ 50 settled
picks, positive flat ROI, calibration ≤ 5% — with CLV reported alongside from
the first pick, because §5's arithmetic says ROI alone will not separate edge
from luck inside a season.

What is deliberately NOT proposed: blind unders, puck-line underdogs,
back-to-back fades, referee overs, or any "system" from §5's no-evidence list.
