# NCAAF — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 31. NCAAF — Pipeline Operations
NCAAF (FBS college football) is the 8th sport. Unlike every other sport, its two
live models are RULES over regressions/openers, not calibrated classifiers —
because the exhaustive model search (below) established that classifiers add
nothing over the closing line in this market.

### Models live (2026 season, PAPER-FIRST despite being active)

| Model ID | Kind | Rule | Status |
|---|---|---|---|
| `ncaaf_over_under` | `total_regression` | Predict the game total from fundamentals (market number NOT a feature); bet the side of the disagreement only when \|pred − DK total\| ≥ 8.0 (symmetric gate, stored in the artifact); P(over) from the OOS-residual ECDF. Refit 2026-11-10 (mike) as the **mean of eleven fits** (seeds 42 and 0-9, `models/seed_average.py`): the active file since 2026-11-11 14:25 UTC, switched on once the weather hold was deployed, because a game with no weather forecast moves it past the gate (the 2026-11-10 section at the end of this file). The single fit of 2026-08-25 is the file to switch back to | LIVE on the mean of eleven. Walk-forward 2022-2025 at the stored close: 235-191, 55.2%, +24.9 units (interval 50.4% to 59.9%, does not clear breakeven); seed 42 alone on the same games 244-230, 51.5%, -9.0 units. Sized small |
| `ncaaf_spread` | `cross_book_opener` | Back the side Bovada's OPENER favours, at DraftKings' stale OPENING number. Three preconditions in the scorer, each `return []`: (1) both openers captured within 90 min (`OPENER_MAX_SKEW_MIN`), (2) DK still ON its opener, (3) \|dev\| ≥ gate | LIVE but STRUCTURALLY DORMANT on this feed (measured 2026-09-07, session 252). Backtest 1,050 bets 58.1% +10.9%, CLV 0.694 — but CFBD's `spreadOpen` carries no timestamp, so the +10.9% was never measured under precondition 1. In production the Odds API lists next week's games from Tuesday with DraftKings and FanDuel priced and NO sharp book: a paid historical snapshot at 2026-09-03T17:55Z (requesting only DK, Bovada and Pinnacle) showed 16 events for 09-12/13 with DK priced and Bovada and Pinnacle absent, while both sharp books covered that week's own slate. Bovada's first stored number lands the Sunday before, by which time DK has moved off its opener on 40 of 49 games. The only firing condition observed is a game that ENTERS the feed with both books already priced (FAU@Florida 2026-09-05, 1-minute skew — the one spread BET this season). Two pre-game BETs all season, both lost |
| `ncaaf_spread_premium` | `cross_book_opener` | The SAME rule, band **[2.5, inf)** — the scorer's `d_threshold_max` on `ncaaf_spread` caps it at 2.5 so the two tiers are MUTUALLY EXCLUSIVE and a game fires exactly one | LIVE — 344 bets 60.5% +15.4%, positive all 3 seasons, CI [0.552,0.655] |
| `ncaaf_moneyline` | — | — | PAUSED — classifier held out at AUC ~0.50 |
| `ncaaf_moneyline_market` | `rule` | The best moneyline among the deciding books against the win chance the ten books' middle spread implies; bet when the gap is above 0.02 with three other books in the consensus; decided once, at 14:00 UTC on game day | LIVE from 2026-11-10 (mike: "ML model yes"). It did NOT clear: 2023-2025 311 bets, +14.70 units, interval -4.7% to +21.6%, one profitable season. Its own section, below |

Thresholds: over_under 0.65/0.0, spread 0.55/0.0 (the spread floor sits under
the rule's ~0.58 flat validated prob ON PURPOSE — the gate IS the filter, the
prob floor must never suppress a qualifying pick).

**The two spread tiers are DISJOINT, not nested.** A tighter gate is a strict
subset of a looser one, so shipping both with a shared floor would fire two
picks on the same side of the same game — double staking, two rows in the app
for one bet. `ncaaf_spread` is capped at 2.5 by `d_threshold_max`;
`ncaaf_spread_premium` starts there. Bands verified as a partition
(706 + 344 = 1,050) and each clears the 4% bar alone: standard 56.9%/+8.7%,
premium 60.5%/+15.4%, both positive in all three seasons. That independence is
what makes the tier ADDITIVE rather than a re-slice — if the remainder band had
collapsed, the right move would have been to tighten the single gate instead.
Re-derive with `opener_strategy.py --experiment bands`; register with
`register_opener.py --bands`.

### The NCAAF moneyline model (`ncaaf_moneyline_market`), live from 2026-11-10

mike, 2026-11-10, asked after the market audit (`docs/ncaaf_market_audit.md`)
whether he wanted a moneyline model live although nothing measured clears:
*"ML model yes"*. Real money, like every model (CLAUDE.md §2). Code:
`models/ncaaf_moneyline_market.py` (the rule),
`scripts/ncaaf_moneyline_card.py` (the card that writes its picks),
`scripts/ncaaf_moneyline_market_build.py` (the frozen numbers and the replay),
`models/saved/ncaaf_moneyline_market_2026.json` (those numbers for the 2026
season). It uses the NCAAB cards' quote read (`models/ncaab_book_quotes.py`)
and final-margin distribution (`models/ncaab_margin_dist.py`) unchanged. The
classifier `ncaaf_moneyline` is a different model and stays paused.

**It did not clear.** Say so whenever its record is quoted. On 2023-2025 its
95% interval runs from -4.7% to +21.6%, so it includes losing; all of its
profit is the 2024 season; and the same rule lost at six of the seven other
times the audit read it (-5.2%, +5.0%, -6.6%, -2.0%, -0.4%, -7.5%, -3.9%).
The rule is the audit's research code ported as written. Nothing in it was
tuned after the result.

**What it bets.** A moneyline that is cheaper than the books' spreads say it
should be. The spreads of the ten fetched books give one middle number for the
game, and that number gives each team a chance of winning. The model takes the
best moneyline among the seven books a pick may name, and bets it when the
team's chance is more than **0.02** above the chance its price implies. It
never lays a price shorter than -200. On the three replayed seasons every bet
was an underdog, priced +110 to +430 (median +146). The rule itself has no
upper limit on the price.

**How a side is priced, step by step:**

1. **Each book's quotes** are its newest pre-game full-game moneyline (both
   prices) and full-game spread (home line, both prices) stamped in the hour
   up to 14:00 UTC. Ten books are read: DraftKings, FanDuel, BetMGM, Caesars,
   Fanatics, BetRivers, Hard Rock, Bovada, Pinnacle and betPARX
   (`config.LINE_SHOP_BOOKMAKERS`).
2. **The consensus.** A spread counts when its line and both prices are there,
   the line is within 70 points, and its two implied chances add up to
   between 1.00 and 1.15. The consensus is the middle (median) home line over
   the spreads that count.
3. **Which moneylines are priced.** A moneyline is priced when both prices are
   there and its two implied chances add up to between 1.00 and 1.15. It is
   dropped when its favourite differs from the favourite at every other book
   (two or more others).
4. **The fair chance.** The expected home margin is minus the consensus, plus
   a fitted offset (-0.138 points for 2026). The home team's chance of
   winning is the chance of a positive final margin at that expected margin,
   from the final-margin distribution. Football has no ties.
5. **The edge** of a side is its fair chance minus the implied chance of its
   price, vig included. Only the seven deciding books' prices are considered
   (`config.BEST_LINE_BOOKMAKERS`: the ten less Bovada, Pinnacle and betPARX),
   and every side priced shorter than -200 is removed first.
6. **The bet** is the largest edge in the game, over every deciding book and
   both sides, when it is above 0.02 and at least three other books are in
   the consensus. A tie goes to the longer price, then the book's name.
7. **The distribution and the offset** for a season are fitted on every
   earlier season's scored games and their CFBD closing spreads (2014-2025
   for 2026: 10,123 games). The offset is the average of final margin plus
   closing spread: how far home teams finished from the number.

**When a game is decided: at 14:00 UTC on its Eastern date, once.** That is
9 a.m. ET in winter and 10 a.m. ET in summer time. The card runs hourly at
five past (UTC) and only the run in the 14:00 hour decides. The decision goes
into `ncaaf_moneyline_decisions` with every book's moneyline and spread and
its flags, bet or not, and the game is never decided again (CLAUDE.md §1c). A
game kicking off less than five minutes after 14:00 UTC, or already under way,
is not bet. A missed 14:00 is recorded as `missed` with no bet and fails the
run; every due game with no deciding book's moneyline in the hour, an artifact
for another season, and a best side at a book `config.BEST_LINE_BOOKMAKERS` no
longer lists fail it too. The research read the stored 13:55 UTC pull. The
session that commissioned this build measured production on 2026-11-10: the
hourly refresh stores every book's NCAAF moneyline and spread at :16-:17 past
each hour, 63-64 of 64 listed games per book.

**Which games.** NCAAF rows of `games` that kick off (Eastern time) today,
after 14:00 UTC, and that one of the ten books had priced by then. The
kickoff decides the day, not `game_date`: a night game can be stored twice
(Data / conventions, below), and the card decides the odds feed's row, which
carries the prices and takes the pick. CFBD's row of the same game has no
prices and is never the card's. Where two priced rows are one game (the same
two teams, kicking off within a day), the row with more quotes in the hour is
decided and the other is recorded as `duplicate_game`. A game first priced
after 14:00 UTC is not the card's and is not `missed`.

**One game never carries two bets that cannot both win.** A game on which the
opening spread model (`ncaaf_spread`, `ncaaf_spread_premium`) already holds a
bet is recorded as `other_model_bet` and not priced. The check runs before the
card prices the game and again inside the write. A voided spread bet holds
nothing. The other direction is not checked: the scorer does not look for this
model's bet before it writes a spread bet (its check covers NHL only). Those
two models bet at the opening number, days before, so in practice they come
first.

**The bet row.** A moneyline: `scored_line` and `line_book` are empty. The
label is the platform's ("Ohio State ML"), checked against the side before it
is written. `decision_*` and `best_*` are the bet book's price. When
DraftKings had a priced moneyline at 14:00 UTC, `dk_odds` / `dk_implied_prob`
/ `edge` are DraftKings' own price on that side, the reference; otherwise
`dk_odds` is empty and the other two 0.0. `model_probability` is the bet
side's fair chance, the number the 0.02 cut was measured on, so the
publishers' edge filter agrees with the card. The stake is the flat one unit
to win (no `stake_units`). A game priced and not bet (below the cut, or with
too few books) is a row with no stake, as the NCAAB cards write. Settlement:
full-game moneyline, overtime included (`games.home_win`, which the odds
feed's row takes from CFBD's).

| Setting | Value | Where |
|---|---|---|
| the cut | edge > 0.02 (fair chance from the consensus spread minus the bet price's implied chance) | `config.MODEL_EDGE_THRESHOLDS` |
| prob / edge filter | 0.0 / 0.02: the edge filter IS the card's cut | `ACTION_THRESHOLDS`, `MODEL_PROB_THRESHOLDS` |
| consensus | the median home line over the ten books' spreads that count; a bet needs three other books in it | `models/ncaaf_moneyline_market.py` |
| price floor | -200: sides shorter than -200 removed before the pick, and pinned again | `models/ncaaf_moneyline_market.MIN_PRICE`, `MODEL_MIN_ODDS` |
| EV floor | 0.04, just under the smallest EV the cut admitted in the replay (+0.0437; median +0.0816). It can remove a bet priced shorter than +100; the replay had none | `MODEL_OWN_EV_FLOOR`, `MODELS_ON_OWN_PROBABILITY` |
| decision instant | 14:00 UTC on the game's Eastern date; quotes stamped 13:00-14:00 UTC | `models/ncaaf_moneyline_market.py` |
| decided once | a row in `ncaaf_moneyline_decisions`, bet or not | `scripts/ncaaf_moneyline_card.py` |
| stake | flat, one unit to win | no `stake_units` |
| settlement | full-game moneyline, overtime included | `tracking/paper_tracker._RULE_MODEL_MARKETS` |
| kill switch | `RUN_NCAAF_MONEYLINE_CARD=0` | the card |
| frozen numbers | the 2014-2025 distribution (10,123 games) and the offset -0.138 | `models/saved/ncaaf_moneyline_market_2026.json` |

**The evidence: the card's own code, replayed** (2026-11-10,
`scripts/ncaaf_moneyline_market_build.py` on the audit's two extracts of
`games` and `odds`; each season priced with the distribution and offset
fitted on the seasons before it; one unit to win, risk capped at 3; units).
The replay runs the card's read and decision at 14:00 UTC on each game's
Eastern date, on the stored game-day morning pull. It matched all 311 of the
research's bets game by game: the same game, side, book and price on all 311,
and the same edge to the last digit (largest difference 0.0). No research bet
was missing and the replay added none.

| Season | Bets | Record | Units | Return | Without the 10 best dates |
|---|---|---|---|---|---|
| 2023 | 140 | 49-91 | -2.77 | -3.3% | -13.79 units |
| 2024 | 78 | 38-40 | +16.66 | +36.7% | -4.42 units |
| 2025 | 93 | 35-58 | +0.81 | +1.4% | -11.56 units |
| **2023-2025** | **311** | **122-189** | **+14.70** | **+7.8%** | **-9.26 units** |

188.76 units were risked. The 95% interval, resampling game dates, is -4.7%
to +21.6% as the audit printed it; the build's own resample, a different
random draw, prints -5.1% to +22.0%. Prices laid: +110 to +430 (median +146),
no favourites. EV at the bet price: +0.0437 to +0.2789 (median +0.0816). The
largest edge was 0.0611. The distribution for each season was fitted on 7,521
(2023), 8,370 (2024) and 9,193 (2025) games, with offsets -0.385, -0.358 and
-0.268. The read held 2,257 games; 2,197 had a side to price. Each season
split at its middle bet date: the early halves made +5.29 units on 149 bets,
the late halves +9.40 on 162. Neighbouring cuts on the same replay: 0.01 made
+13.78 units on 601 bets (+4.1%; it lays prices from -108 to +3500); 0.03
made +10.27 on 136 (+11.7%); 0.04 made +5.45 on 43 (+19.4%); 0.05 lost 1.96
on 11.

**The risks, plainly:**

- **It did not clear.** The interval is -4.7% to +21.6%. A rule that loses
  money is inside it.
- **Its profit is one season.** 2024 made +16.66 units; 2023 lost 2.77 and
  2025 made 0.81.
- **It is a bet on road underdogs, and that is the fitted offset at work.**
  294 of the 311 bets are road teams. The offset says home teams finished
  behind the closing spread by 0.27 to 0.39 points in the seasons each table
  was fitted on, which tilts every fair chance toward the road team. With the
  offset set to zero the same cut is 212 bets and -9.22 units (116 road
  teams). The offset fitted for 2026 is smaller, -0.138. What that does to
  the mix of bets has not been measured.
- **Road underdogs at these prices made money with no rule at all.** Every
  road team whose best deciding-book moneyline at the same read was +110 to
  +430: 813 bets, 275-538, +6.94 units. The rule's 294 road bets come from
  that group. What the rule adds is choosing which of them to bet, and three
  seasons do not show that the choice will keep paying.
- **It leans on a few dates.** Without its 10 best dates it is -9.26 units
  (-9.3), and each season is negative without its own 10 best dates.
- **One read only.** The same rule at the seven other stored reads lost at
  six of them (the audit's `lab_results.csv`: the evening before made +5.0%,
  the other six lost 0.4% to 7.5%).
- **No 2026 read exists.** A settled 2026 game kept only each book's opener
  and close until 2026-11-10 (`docs/ncaaf_market_audit.md` §8), so the rule
  could not be read on this season before going live.
- **The live read is not the research's read to the minute.** The research
  priced the stored 13:55 UTC pull, where every quote was stamped 4 to 19
  minutes before 14:00 UTC (the build prints it). Live, a quote is the hourly
  refresh's, stamped about 13:16 UTC. A price can move in those 40 minutes.

**Review at 50 settled bets** (gate standing, CLAUDE.md §2: at least 50
settled picks, positive flat-bet ROI, calibration within 5%). Read beside the
return: how many bets were road teams, and how often the bet book's price was
still up when the pick posted (the ledger keeps every book's 14:00 quote).

**Before the 2027 season** rebuild the frozen numbers
(`python -m scripts.ncaaf_moneyline_market_build --cache <the two extracts>
--last-season 2026`): the card refuses an artifact for another season. The
build reads `ncaaf_games.parquet` and `ncaaf_odds.parquet`, every NCAAF row of
`games` and `odds`, as `scripts/ncaaf_search/audit_2026_11/extract_ncaaf.py`
takes them from the local copy of the database. In 2026 a night game's final
is on both of its rows, so check the count of games the 2027 table is fitted
on against the count of distinct games before trusting it.

### The model search is CLOSED (2026-08-27) — every lever tested, verdicts pinned

All harnesses live in `scripts/ncaaf_search/` and re-run against the DB. House
rules for any future NCAAF analysis: definitions fixed before results, variant
count reported, per-season records, Wilson CI vs 0.5238, and a TIME SPLIT that
must hold in both halves — that split is what killed every false positive.

| Lever | Harness | Verdict |
|---|---|---|
| 42-config classifier search (6 families × feature groups, ATS + totals) | `run_search.py` | NULL — CLV 0.41–0.48 everywhere, nothing clears the 5 gates |
| QB continuity (31.6K passer-games, `ncaaf_qb_game`) | `qb.py` + `qb_ablation.py` | NULL — helps 2/7 totals + 3/7 margin gates (coin flip), RMSE unchanged; the one positive spot cell is home/away confounding (mirror case shows nothing). "Starter out this week" was untestable when this ran (no CFB injury feed) — only continuity was testable, and it is priced. The hindsight version is the row below |
| **Starter OUT, with hindsight** (perfect-information upper bound for the availability-report spike Matt approved 2026-09-07) | `starter_out.py` | NULL — 760 team-games 2021-2025 where the established starter (primary in ≥2 of the last 3 same-season games) has NO box-score row. At the Bovada close: fade the team 51.5% [0.479, 0.551], back it 48.5%, under 48.0%; no season clears 0.5238 and both halves of the time split sit at ~51%. Power: ~4pp detectable. Decisive in the null direction — nothing above breakeven is detectable at the close even when the absence is KNOWN (~4pp power), so an availability feed has nothing to rescue at the close. The 51.5% fade vs the 48.6% "starter played" row is a ~3pp gap inside the OUT arm's own interval, and that row is not an independent control (it holds the other side of every OUT game). What it cannot measure: the window between announcement and close, which needs an announcement timestamp and the intraday archive |
| Weather spot rules (12 seasons, reanalysis) | `weather_totals.py` | NULL — unlike the NFL, the CFB market MOVES its total with wind (55.7 calm → 53.4 at 18+); wind≥12 = 54.0% pooled but late-half 51.2% and the ~2.5pp forecast haircut kills it; the 61% wind+rain cell is a time-split mirage (70% early / 34% late) |
| Line-movement follow/fade at the close (4,311 Bovada open+close pairs) | `line_move_spots.py` | NULL — follow = 50.0–52.4% at every threshold, no fade signal either; the close subsumes its own movement |
| Look-ahead / let-down schedule spots | `situational_spots.py` | NULL |
| **Steam lag** (Pinnacle moved >= k between two stored pulls, DK moved < k/2 and DK's line is OLDER than Pinnacle's; bet DK's stale number the way Pinnacle went; 2023-2025, 47,303 consecutive-pull pairs) | `steam_lag.py` | NULL — totals k=1: 407 bets 52.1% [0.472, 0.569]; k=0.5: 705 at 50.2%; k=1.5: 59 at 54.2%. Spreads k=0.5: 781 at 48.1%; k=1: 229 at 50.7%; k=1.5: 115 at 53.0% (2024's 85.7% is 21 bets). Control "DK followed" 49.6-51.0% on 951-3,624. DK's close does drift toward Pinnacle after a lag (39% of totals events vs 22% away, +0.29 points), so the lag is real and the CLV is a third of a point — it does not turn into wins at a -110 price. Two pulls a day cannot see how long DK stays stale |
| **Consensus anchor + dispersion** (the totals rule gated on the 13-book median total, or on Pinnacle, instead of DK; and split by max-min across books) | `consensus_gate.py` | FLAT — DK 56.4% (314), 13-book median 56.9% (313), Pinnacle 55.4% (316): the same bets. DK sits a mean 0.16 points from the median; dispersion >= 1.5 in 17% of games, and gating on it does nothing (54.5% on 55). The edge, such as it is, is model-vs-market, not DK-vs-sharp. Time split, all anchors: early half 58.7-59.9% (+), late half 50.8-52.7% — the rule's record is early-season |
| **Totals rule at earlier leads** (0-5 days out, DK 14:00Z line, 2023-2025 backfill, 2,194 matched games) | `totals_lead.py` | FLAT — at the shipped ±8 gate: 0d 56.4% (307), 1d 55.2%, 2d 53.8%, 3d 54.0%, 4d 55.3%, 5d 55.6% (232), DK close 56.4% (314), archive close 57.3% (309); every Wilson interval overlaps every other and none clears 0.5238 at 95% (lower bounds 0.482-0.517). Close-minus-lead movement in the pick's direction is -0.12..+0.07 points at every lead: no CLV, the market does not converge on the model. First-signal lock from 5 days out: 384 bets 55.7% [0.507, 0.606] vs 321 at 57.0% [0.515, 0.623] on game day. Per season 2023 52-56%, 2024 57-62%, 2025 50-57%; time halves 52-58% / 52-60%, no sign flip. Verdict: earlier is not measurably worse and not measurably better; the lead limit is a timing choice, not an edge choice |
| Moneyline (margin regression -> P(win) vs real Bovada prices, 2,877 games) | `outcome_edge_scan.py` | NULL — calibration is superb (0.999 decile correlation) but EVERY edge cell loses at real prices (-2.8%..-8.9%): the book's implied probs are sharper than the model's and the 4.4% overround eats the rest. `ncaaf_moneyline` stays paused |
| Outcome x edge conditional surface (all 3 markets, 36 cells, 4-season walk-forward) | `outcome_edge_scan.py` | The one POSITIVE finding of the search — but it CONFIRMS the live totals rule rather than adding a new one: at the shipped ±8 gate, 9/9 cells are above breakeven (~55.6% over 464 bets, +6.4% at -110), the effect is DIRECTION-SYMMETRIC (over-side 56.1%, under-side 54.5%, both halves both sides), monotone turn-on lands exactly at 8 (the 6-8 band is 47-52%), and it holds in every line band and week band. Spread margin regression stays dead across 4 seasons (50.1-50.8% pooled; its 53.6% was a one-season artifact; the dog>fav asymmetry never reaches breakeven) |
| Margin regression (spread) | `ncaaf_margin_eval.py` | Passed its 2025 kill line (53.6% @ ±5.5) but ~50% across the 4-season walk-forward — 2025 was its one good year. Superseded by the opener rule |

**Added 2026-11-10 (the market audit, `docs/ncaaf_market_audit.md`).** Three
more verdicts, harnesses in `scripts/ncaaf_search/audit_2026_11/`:

| Lever | Harness | Verdict |
|---|---|---|
| **Line shopping against the consensus** (the NCAAB spread, total and moneyline rules, unchanged; 2023-2025 stored pulls, 2,314 games, walk-forward tables) | `lab.py`, `spread_dd.py`, `sym.py` | NULL. The spread rule as built for NCAAB reads +8.2% on 338 bets [-1.2, +16.7] at the game-day morning pull, and 337 of the 338 are road teams: the fitted table's home/away tilt, not an off-market number. Every road team at the consensus lost 4.4%. Tilt removed: 22 bets at a 0.02 cut. A number 1.0+ points better than the consensus exists in 13.2% of games and lost 8.8% (269 bets). Totals: 48 bets at 0.02. Moneyline against the book's own spread: -0.5% on 386. Moneyline against the consensus spread: +7.8% on 311 at one read, negative at six of the other seven (the audit's `lab_results.csv`; this said five until 2026-11-10), -9.3 units without its 10 best dates. Built live anyway on mike's call, as `ncaaf_moneyline_market` (its section above) |
| **College props, the second season** (the market-relative rule on 2026's three pulls a game day, and 2025 again; every book as a placebo) | `props/main.py` (`docs/ncaaf_market_audit_props.md`) | NULL. Pinnacle 2026 at 0.02: 42 bets -32.4%; consensus 2026 64 bets +2.3%; nothing reaches 150 bets in a season. The placebo fails again (FanDuel as the reference +13.5% on 111 in 2025). From the week of 2026-09-29 FanDuel and Hard Rock, the only two-way books in volume, stopped disagreeing at an equal line |
| **The totals fit's random seed** (11 seeds, same data and settings) | `totals_seeds.py`, `totals_seeds_fc.py` | A FINDING, not a verdict. One game's prediction moves 1.49 points (sd) with the seed; 3 in 10 games at the 8-point gate change with it. At the stored close the walk-forward is 51.5% to 56.4% by seed (the published 55.9% was one draw). In the live shape (first morning DraftKings read that crosses, 2023-2025) every seed is positive, +4.1% to +10.6%, and the 11-seed average is 346 bets +35.06 units (+9.35%). 2026 does not separate the average from a single fit. Acted on 2026-11-10 (mike): the fit is now the mean of the eleven, fitted and not yet registered (the 2026-11-10 section at the end of this file) |

**What this means:** the two live rules ARE the survivors. Do not re-mine
features on this data; new edge requires new INFORMATION (an injury/news feed,
or the bovada/pinnacle intraday history now accruing in `odds` for
future-season stale-number work).

### The board: a week-long window, and "watching" is a row (2026-08-29)

NCAAF plays one slate a week, so a same-day board is empty six days out of
seven — and both rules answered a game they would not bet with `return []`, no
row at all. The result was a sport that looked like it was not running. It also
made the opener rule structurally DORMANT: it only fires while DK is still on
its opening number, which is rarely true by kickoff.

- **Look-ahead**: `NCAAF_SCORE_AHEAD_DAYS` (150) is the outer edge of the
  scorer's game query and of the app's (`fetchUpcomingNcaafPicks`). It was 7
  until 2026-09-07 (Matt: *"it should be whenever lines are released. speed
  speed speed is what matters to get a good line"*). What admits a game is a
  CURRENT DraftKings price: a DraftKings row stored within
  `PREGAME_PRICE_MAX_AGE_MIN` (180 minutes). Until 2026-10-09 the check was
  "has DraftKings ever priced it", and that is how 31 games DraftKings pulled
  in early September were scored off their 09-04 to 09-06 rows into October
  (16 BETs; `docs/sessions/2026-10.md`, 2026-10-09).
  - **Corrected 2026-10-09.** This line used to say DraftKings listed 44
    games more than 14 days out on the day the window changed. That counted
    rows already stored. Our own DraftKings totals rows stamped 2026-09-07
    12:00-13:30Z cover 50 games, none more than 14 days out (latest 09-13).
    DraftKings lists the big games early, pulls them, and re-lists them about
    ten days before kickoff.
- **A decline writes a row.** Every precondition failure now yields a NONE row
  carrying DK's live number and a reason, instead of nothing. An empty board
  and a broken pipeline are indistinguishable to a user — which is exactly how
  the 2026-08-29 outage below stayed invisible.
- **The lock is signal-aware for NCAAF only.** `locked_pairs` excludes NCAAF
  NONE rows, so a "watching" row is refreshed every pass while a real signal
  still locks at first cross (the opener rule's whole thesis). Without this a
  Monday NONE row would freeze the game for the week and the totals rule —
  game-day by design — could never fire at all. The NONE rows are delete +
  rescored each pass, scoped to unstarted games.
- **The totals rule has NO lead limit** (`NCAAF_TOTALS_MAX_LEAD_DAYS` = inf):
  it fires at the first scoring pass where DK's total sits 8+ points from the
  model, whenever that is, and locks there. It shipped at 1 (game day) because
  it had only been walked forward against the archive's close. **Measured
  2026-09-07** on the 2023-2025 DraftKings backfill
  (`scripts/ncaaf_search/totals_lead.py`, row in the search table below):
  graded at DK's 14:00Z line 0-5 days out, the ±8 rule runs 53.8-56.4% at
  every lead against 56.4% at DK's close (its last 14:00Z/23:00Z pull before
  kickoff), every interval overlapping every other, and the close-minus-lead
  movement is ~0 points in the pick's direction at every lead — the market
  does not drift toward the model, so waiting buys nothing and going early
  costs nothing detectable at ~5pp. Under the first-signal lock from 5 days
  out: 384 bets at 55.7% [0.507, 0.606] vs 321 at 57.0% [0.515, 0.623] on
  game day. Nothing at any lead, game day included, clears 0.5238 at 95% on
  three out-of-sample seasons. It went to 5 that evening (PR #577) and to
  none the same night at Matt's call. Unmeasured: leads beyond ~7 days (DK
  listed 84 of 2,651 backfill games that early) — a statement about the
  sample, not the rule. **"All books" buys no speed on totals, measured:**
  every book's first NCAAF total lands a median 5.4-5.9 days before kickoff;
  the gap between the earliest book and DK is a median 0.0 days, 90th
  percentile 0.62, and only 205 of 2,651 games had any book a full day ahead.
  The opener rule has no limit either: its own preconditions are its window.
- **THE FBS GATE TRUSTS SP+, NOT THE REGISTRY** (2026-09-12, matt: *"make sure
  we have the right NCAA picks"*). `_is_fbs` used to read `classification` and
  consult `sp_overall` only as a FALLBACK when that column was NULL — so
  whenever a classification existed, the proof the function's own docstring
  calls decisive ("SP+ is FBS-only") was never reached. SP+ is now REQUIRED and
  `classification` may only ever VETO.
  The case that found it: **North Dakota State** and **Sacramento State** carry
  `fbs` in `ncaaf_teams` and in all 15 of their 2026 `ncaaf_team_stats`
  snapshots, with no SP+ on any. Their two DK-priced games that Saturday
  (NDSU @ Air Force, Sac State @ Fresno State) produced **no pick row at all** —
  `picks_log` holds zero rows for either id, because the gate passed them and
  four models then each returned `[]`.
  **THE REGISTRY IS NOT WRONG — this entry first said it was, corrected
  2026-09-13.** The theory was a bad ingest default writing `fbs` over an FCS
  school. It was tested: a `ncaaf_teams_refresh` for 2026 ran on the worker
  (job 82908, 683 rows — the whole table) and `_TEAM_UPSERT` overwrites
  classification and conference unconditionally from CFBD. Both came back
  `fbs`; the count stayed **138**. CFBD asserts they are FBS programs for 2026,
  so these are NEWLY PROMOTED schools and CLAUDE.md §4's "136" was the stale
  number.
  **The gate is still right, for a different reason:** a school SP+ has not
  rated cannot be MODELLED whatever division it plays in, because `sp_overall`
  is itself a feature (`d_sp_overall`) and a missing feature is not 0.0.
- **WHY A NEWLY PROMOTED SCHOOL IS UNRATED ALL SEASON — by design, not a lag**
  (corrected 2026-10-12; this said "SP+ needs FBS history, so it lags a
  promotion" and "it clears when SP+ rates the school"). A season's
  `sp_overall` is CFBD's **prior** season's final SP+, held constant all year
  (`cfbd_ingestor._prior_season_context`; measured: one distinct value per
  team-season). North Dakota State and Sacramento State were FCS in 2025,
  which SP+ does not rate, so they have no rating for any of 2026 and **their
  2026 games stay refused at the FBS gate**. A rating can first appear on the
  first run on or after **2027-03-01**, when the season label rolls to 2027
  and the 2027 preseason rows are built from the 2026 final SP+ — and only if
  CFBD rates them. Precedent in `ncaaf_team_stats`: Delaware and Missouri State
  (FBS from 2025) are unrated in 2025 and rated in 2026; Kennesaw State (FBS
  from 2024) unrated in 2024, rated in 2025.
  **`config.NCAAF_PROMOTED_TO_FBS`** lists each promoted school with its first
  FBS season (NDSU 2026, Sacramento State 2026). It is monitoring only — the
  gate never reads it and nothing boards these games with a stand-in rating
  (that would be a model update). `system_health`'s **`ncaaf_fbs_registry`**
  check reports a listed school as **OK in its promotion season**, with the
  reason and the earliest date it can change; the exemption ends with that
  season by itself, so a school still unrated in its second FBS season is
  STALE again, and so is any established school that loses its rating. Before
  this the check sat STALE for 30 straight days (2026-09-13 → 10-12), and the
  failure alerter repeats a standing STALE warning to the ops channel every 12
  hours — about something nobody could act on. **Add a school to the list the season CFBD
  first calls it FBS.**
  A decline where the registry calls the school FBS but it is unrated logs at
  WARNING, naming the school (and, for a listed school, why); an ordinary FCS
  opponent stays at debug, or 33 of a 98-game Saturday would bury the two that
  matter. Until 2026-10-12 that WARNING never fired: the live snapshot read
  carries no `classification`, so every refusal logged at debug. The scorer
  now reads the `ncaaf_teams` classification once per pass and hands it to the
  refusal log only — `classification` must NEVER be added to the feature
  engine's `_STAT_COLS`, which would switch the gate's classification veto on
  in training and backtests (a model update).
  **A re-pull does not change any of this** (`ncaaf_teams_refresh`, tried
  2026-09-13).
  Tests: `tests/test_ncaaf_fbs_registry.py` (the two gate cases watched
  failing, the check's FBS-only bound watched failing under mutation, and the
  promoted-school exemption, its expiry and the refusal log each watched
  failing on the code before 2026-10-12).
- **The FBS gate does most of the filtering.** Week 2 is 117 games, 39 both-FBS,
  ~52 DK-priced — so the board is tens of games, not hundreds.

### The schedule gate, rest at kickoff and the night-game stub (2026-10-20)

mike: *"The repo/models should look ahead schedules for all markets and sports
and models."* Three changes, all reading the stored schedule through one module
(`data/schedule_context.py`).

- **No decision while a team has an earlier game to play or log.** A game is
  held when either team has an earlier game that is not played, being played,
  or played but not yet in `ncaaf_team_game_log` (the log the team stats are
  built from). Every model's row is still written, as NONE, with the reason
  ("waiting for Wisconsin's 2026-10-17 game to be played and logged"). NONE
  never locks, so the first pass after the game is logged decides it
  (`models/scorer.run_scorer`, `_schedule_hold`). Why: `ncaaf_over_under`
  decided 9 of its 77 kept BETs before a team's intermediate game, all 9 more
  than 7 days ahead; its stats and early-season flag were one game stale. The 8
  graded went 3-5, -2.31 units, against 36-25, +7.48 units on the other 61 (too
  few to show a cost; the reason is input correctness). The open one, 3688041
  (Wisconsin vs USC Under 52.5, 10-24), is a locked BET and is not touched.
- **Rest at kickoff.** `_rest_days_live` read played games only, so the game in
  between looked like a bye (pick 3094504 read 14/14 where it was 7/7). It now
  counts a game still to be played. Training reads the latest played game,
  which for a past game is the same thing, so **no retrain**: the training
  value does not change. With the gate on, a game it lets through has no
  pending earlier game, so its rest was already right; this corrects the
  number on held rows and on any path that skips the gate. Only the paused
  `ncaaf_moneyline` has a rest input; the totals model does not.
- **The night-game stub takes CFBD's schedule row.** The odds feed's ET-dated
  row carries the prices and no week, venue, neutral-site or conference flag;
  the scorer used to read those as 0 (week 0 never occurs in training). It now
  takes them from CFBD's row for the same two teams within a day, or from the
  one CFBD game either team has within a day; none or two, and the game is not
  scored, with the reason logged (`_schedule_row_live`). Measured 2026-10-20:
  all 9 future stubs (Miami @ Notre Dame 11-07, Texas @ Texas A&M 11-27,
  Army-Navy 12-12 among them) have that row.
- **What counts as one game.** A team never plays twice inside two days, so
  every row for a team within a day of another is the same game. That is what
  catches the stub and an opponent spelled two ways ('LIU Sharks' beside 'Long
  Island University', 'Bryant Bulldogs' beside 'Bryant'). A past game that
  never gets a result stops holding after 10 days (the results step's own
  self-heal window).
- **On today's board (2026-10-20, read-only SQL):** 0 of the 56 priced games
  would be held. Every team's previous game is scored and logged, and no team
  has a game before this week's. The gate bites when DraftKings prices a game
  more than a week out.
- **What it costs.** A Saturday game reaches the team log in the next morning's
  6am ET run: 439 of 446 Saturday games since 2026-09-01 were logged on the
  Sunday, 6 on the Monday (log `created_at`, which an upsert never rewrites;
  median 14.2 hours after kickoff). So the next Saturday's game can be decided
  from Sunday morning, about 6.5 days before kickoff, against a median BET lead
  of 5.2 days.

### Data / conventions (load-bearing)

- **New CFBD games are dated by Eastern kickoff** (Matt, 2026-09-13, the
  option-2 call on the #701 reviewer handoff). `parse_games` / `parse_lines`
  convert CFBD's UTC `startDate` the same way the odds ingestor does
  (`America/New_York`), so a new night game shares the odds row's `game_id`
  instead of creating an ET/UTC twin. **Already-written CFBD `game_id`s are
  not rewritten.** If the historical UTC-prefix id already exists, ingest
  keeps it (`retain_existing_cfbd_ids`). Re-keying would orphan
  `ncaaf_team_game_log` and `ncaaf_qb_game` FKs across 2015–2025.
- **Old ET/UTC twins stay.** Night games ingested before that policy still
  have two rows (`NCAAF_2026-08-29_memphis_unlv` live and `..._2026-08-30_...`
  cfbd). PICKS ALWAYS ATTACH TO THE ODDS ROW — it is the one that exists when
  the board is priced — and CFBD wrote the final to its own.
  `mirror_scores_to_alias_rows` (called from both
  `ingest_ncaaf_results_for_date` and `ingest_ncaaf_games`) writes the
  orientation-corrected final onto every row that is the same game, matched
  on the slug pair within ±1 day. An existing final is never overwritten, and
  a candidate matched by two conflicting finals is left unscored rather than
  guessed (`±1 day` is load-bearing — an annual rivalry repeats the slug pair
  every season). The live-loop `load_context` guard (#701) is still required
  so a Saturday-night lookback cannot silently pick the unscored CFBD twin.
  Name-resolution phantoms (Tennessee vs Tennessee State) are a separate
  population — not this rule.
- Canonical team id = CFBD SCHOOL NAME (accents folded via `_fold`); game_id
  slugs. Odds API names no fold / "school mascot" / prefix rule can bridge
  (Southern Miss, App State, UMass, SE Louisiana, The Citadel) live in
  `config.NCAAF_ODDS_API_MAP`; without an entry the odds ingest mints a
  second `games` row and `ncaaf_game_identity` goes CRIT. Historical lines
  under `cfbd_*` bookmakers (provider priority
  `NCAAF_LINE_BOOKMAKER_PRIORITY`; 2023-25 DK, 2019-22 Bovada, 2015-18
  consensus). Openers are protected from the pruner (earliest snapshot per
  proposition per book — `test_prune_preserves_openers.py`).
- `ncaaf_qb_game` (added 2026-08-27): every passer per team-game 2015-2025,
  `is_primary` = most attempts (validated against the real 2023 QB carousels).
  Kept current by the weekly in-season step; feeds no model today but is the
  substrate if an injury feed ever lands. `--backfill-qb START END` refreshes.
- `ncaaf_player_game_log` (added 2026-08-30): EVERY player per team-game —
  passing, rushing, receiving and defense — behind the mobile Stats tab's NCAAF
  player leaderboard (`v_player_season_totals_ncaaf` +
  `player_window_totals_ncaaf` / `player_recent_games_ncaaf` /
  `player_season_stat_values_ncaaf`; migration
  `add_ncaaf_player_stats_leaderboard.sql`). **Display only — no model reads
  it**, and it does NOT replace `ncaaf_qb_game`, which stays the modelling
  substrate (one row per passer, `is_primary`, FK'd by a decade of training
  rows). Both are filled from ONE `/games/players` pull
  (`ingest_ncaaf_player_logs`), so the wider table cost zero extra CFBD calls.
  Three load-bearing details: **one row per PLAYER, not per category** (CFBD
  lists a running QB under both `passing` and `rushing`); **a player whose every
  tracked stat is zero is dropped** (kickers/punters/returners would otherwise
  go 12-for-12 on an "at most N yards" board — the NFL leaderboard lesson); and
  **no position column**, because CFBD's box score names participants, not
  positions, so the board groups by STAT rather than by a guessed position.
  Column names match `nfl_player_game_log` wherever the two sports share a stat,
  so one mobile catalog key means one thing in both football leagues; there are
  no `targets` (CFBD does not report them) and no NCAAF prop models, so the
  leaderboard never offers "Add to play" — but it does now carry a LINE, from
  `data/ingestors/ncaaf_prop_odds_ingestor.py` (2026-09-05): college props are
  pulled for games DraftKings already prices, and the board reaches its market
  through `FOOTBALL_STAT_TO_MARKET` rather than through a model, because it has
  none. A college prop row is research and never a pick. Live since 2026-09-05
  at 9am/1pm/6pm ET (`RUN_NCAAF_PROP_ODDS=1`), ~590 credits a pass over the 68
  events the feed lists — `docs/cloud_worker.md` has the measured breakdown. `--backfill-players START END` fills
  history (~17 calls per season).
- Weather: `game_weather` rows for ~99% of 2014-2025 games (3pm-local
  Open-Meteo REANALYSIS — truth, not forecast; any historical weather edge is
  an upper bound). `scripts/ncaaf_weather_backfill.py --seasons A B` fills
  gaps; `ingest_upcoming` writes forecasts for the coming week.
- Weekly ops in season: `step_ncaaf_stats` (schedule + box scores + QB log +
  player log + snapshots, ~50 CFBD calls — the player log rides the QB log's
  existing `/games/players` fetch and adds none) and `step_ncaaf_results`
  pre-settle. Off-season
  the schedule pull returns nothing — that IS the gate.
- Totals-regression refits are two steps since 2026-11-10 (the section at the
  end of this file). `python -m scripts.ncaaf_margin_eval --fit-totals` fits
  the mean of eleven seeds and writes the artifact; it refuses to write one if
  the average no longer clears the kill line at the gate, and it registers
  nothing. `--register-totals VERSION` makes it the active model, and runs
  only after the artifact is committed, merged and deployed. A refit is a
  model update (`Updated-By:`).

### First-half lines and team totals, 2023-2025 (built 2026-11-10)

No first-half or team-total price has ever been stored for college football
(`docs/ncaaf_market_audit.md`, section 7). mike approved buying them on
2026-11-10 ("Buy all"). The code is built
(`data/ingestors/ncaaf_derivative_history.py`); **nothing is bought until the
job is run.**

- **What is bought.** For every game of 2023, 2024 and 2025 that already
  holds stored full-game historical prices: the first-half moneyline, spread
  and total and the team totals, at the ten fetched books. One call a game.
  The feed bills 10 credits per market it returns, so at most 40 a game. An
  empty answer and a "not found" are free. Each date also costs one event
  list (1 credit), which names each game's event.
- **The two reads.** The stored full-game history was bought as two pulls a
  day, asked for at 14:00 and 23:00 UTC and served at about 13:55 and 22:55.
  The first-half lines are bought at the same two moments, so a first-half
  line can be set beside the full-game line of the same moment.

  | Read | Asked for | Games bought | Stored under source |
  |---|---|---|---|
  | `am` | 14:00 UTC on the game's Eastern date (game-day morning) | those with a stored full-game row from that morning's pull | `odds_api_ncaaf_derivative_am` |
  | `pm` | 23:00 UTC on the Eastern date before (the evening before) | those with a stored full-game row from that evening's pull | `odds_api_ncaaf_derivative_pm` |

  A game counts as holding a pull when it has a full-game row (source
  `odds_api_historical`) stamped in the hour up to the time asked for. A game
  is bought only if it kicks off more than five minutes after that time, so
  no price bought here can be in play.
- **A game stored twice is bought once.** Two things put one game in `games`
  twice. A night game has the odds feed's Eastern-dated row, which holds the
  prices, and CFBD's UTC-dated row, which holds the score ("Data /
  conventions" above). And the stored full-game history was written on
  2026-09-07, before the team registry held FCS schools: 245 of the games
  with a morning pull sit under the feed's own team name ("Furman Paladins",
  "Southern Mississippi Golden Eagles"), beside CFBD's row for the same game
  under the school's name, which holds the final. Rows whose names resolve to
  the same two schools, dated within a day of each other, are one game. It is
  bought once and stored under the id that holds the stored pull; if both ids
  hold it (35 games at the morning read), under the one with more stored
  rows.
- **Matching the feed to our games.** By the two team names (the same name
  resolution the odds feed uses: `config.NCAAF_ODDS_API_MAP`, then the team
  registry) and the kickoff time, within 24 hours of the stored kickoff. Each
  name is tried as the school it resolves to today and as the feed's own
  name, which is what a row written before the name resolved still holds. A
  feed event that lands on no planned game is printed and skipped. A planned
  game the feed's list does not name is printed and recorded as not listed.
  Neither is guessed. A row stored under a wrong school by the old prefix
  rule (Florida A&M at Miami stored as Florida at Miami) matches nothing and
  is not bought. When the feed calls our away team home, the stored spread
  is still our home team's number.
- **Where it is stored.** In `odds`, in the shape the NCAAB purchase stores
  the same four markets, so one reader fits both sports: markets `h2h_h1`,
  `spreads_h1`, `totals_h1`, `team_totals_home` and `team_totals_away`;
  `snapshot_type` `open`; `snapshot_at` the snapshot time the feed served.
  Both sources are protected from the odds clean-up (`data/prune_odds.py`).
- **Nothing is bought twice.** `ncaaf_derivative_fetches` holds one row per
  game and read: the time asked for, the time served, the credits the call
  billed, the rows stored and a status. The prices and that row are written
  together. A rerun skips every game marked `stored` or `empty`. A game the
  feed did not list, a "not found" and a failed call are recorded and asked
  for again on a rerun; listing a date again costs 1 credit. The table is
  read again just before each date is listed, so two runs at once do not
  both buy a game.
- **The most it can spend.** 40 credits a game plus 1 a date. Measured
  2026-11-10 on the audit's extract of the local copy of the database, with
  the purchase's own plan (not yet read from production):

  | Read | Games | Dates | With a final | Most it can spend |
  |---|---|---|---|---|
  | `am` | 2,510 | 180 | 2,467 | 100,580 |
  | `pm` | 2,435 | 186 | 2,405 | 97,586 |
  | Both | | | | 198,166 |

  **That is 12,636 credits above the 185,530 the audit stated for the two
  reads.** The audit's "2,314 games on 205 dates, 92,765 credits" a read
  counted games with any stored pull at any time, not either read. Its own
  extract holds 2,257 games with a final on 180 dates at the morning read and
  2,227 on 183 the evening before. The plan is larger than those because it
  also takes the games stored under the feed's own team name: at the morning
  read 210 more games get their final from CFBD's row, and 43 have no final
  stored (FCS opponents CFBD spells another way, and rows under a wrong
  school that no event will match). The dry run prints each read's own
  count, by season, from production.
- **The credit limits.** `--apply` needs `--max-credits` and `--floor`. The
  run then tightens both from what the system measures: its limit is the
  smaller of `--max-credits` and the plan's own most, and its floor is the
  larger of `--floor` and 7 days of the median daily spend in
  `odds_api_quota`. It refuses to start if it cannot read a daily spend or a
  balance, or if the team registry (`ncaaf_teams`) is empty, because then no
  feed name would land on a stored school and every date's list would be
  paid for to match nothing. It stops before a call would cross the limit or
  the floor. Newest date first, so a stop leaves the most recent season
  stored. Calls run 6 at once (at most
  10), each counted at 40 credits while it is waiting for its answer (the
  NCAAB purchase's meter, `docs/sports/ncaab.md`, "Paid calls side by side").
- **The test buy** (`--sample N`) buys N games a read, spread over the three
  seasons and four kickoff times (before 3pm, 3-6pm, 6-9pm, 9pm or later,
  Eastern). The games are picked by a fixed hash of the game id, so a rerun
  picks the same ones. They are stored under the same sources and the same
  table, so the full buy skips them. 50 games at one read cost at most 2,050
  credits (2,033 on the local copy: the 50 fall on 33 dates). It answers
  what is not known yet: whether the books had posted first-half lines and
  team totals by those two times.
- **What it prints.** The plan by season (games, dates, how many have a final
  score, how many are already bought) and why other games are not planned.
  After a run, read back from `odds`: for each book and market, how many of
  the bought games hold a quote.
- **Commands.** Without `--apply` nothing is called and nothing is written.
  - The plan: `python -m data.ingestors.ncaaf_derivative_history --read both`
  - Test buy, the plan: `python -m data.ingestors.ncaaf_derivative_history --read am --sample 50`
  - Test buy: the same with `--apply --max-credits 2050 --floor 300000`
  - Full buy: `python -m data.ingestors.ncaaf_derivative_history --read both --apply --max-credits 198166 --floor 300000`
- **Worker job** (job type `ncaaf_derivative_history`, not a declared job, so
  a merge buys nothing):

  | Buy | Args |
  |---|---|
  | The plan, no call | `{"read": "both", "dry_run": true}` |
  | Test buy, 50 games at the morning read | `{"read": "am", "sample": 50, "max_credits": 2050, "floor": 300000}` |
  | Morning read | `{"read": "am", "max_credits": 100580, "floor": 300000}` |
  | Evening read | `{"read": "pm", "max_credits": 97586, "floor": 300000}` |
  | Both | `{"read": "both", "max_credits": 198166, "floor": 300000}` |

  The job refuses a limit above these figures, which are the plan's most as
  measured above. A job may ask for less: the run then stops at its limit
  with the oldest games left, and a later run buys only those. If the dry
  run against production prints a larger plan, the limit in
  `tracking/job_queue.py` is the number to raise.
- **Not stored by this purchase.** Half and quarter scores, which grade these
  markets, are not stored for 2023 and 2024 (`ncaaf_plays` holds 2025 only).
  Quarter lines and alternate lines are not bought.

### `ncaaf_live_total` — what has been tried, and the standing instructions

**STANDING INSTRUCTIONS (mike, 2026-09-12). Do not re-raise either of these.**

- **`ncaaf_live_total` is NOT paused and NOT capped.** Asked and answered
  twice. It keeps betting at its current cut. A session that finds the
  evidence below and proposes a pause or a per-day cap is proposing something
  already refused — write the evidence down instead.
- **THE BEST BOOK ALWAYS PLACES THE BET.** Not DraftKings. This is the
  standing rule for the live models (mike: *"remove DK only - we want best
  lines for us regardless"*, #634). What shipped in #694 (2026-09-12) is the
  exact form: the models QUALIFY at DraftKings, the price every cut was swept
  on, and the bet is placed and recorded at the best bettable quote. Do not
  reopen either half.

**What is measured, so it is not re-measured.** Six attempts, all on the 2025
in-play replay, all first-signal-locked and read out of sample:

| Attempt | Result |
|---|---|
| Tighter prob/EV cut | No evidence above prob 0.72 — every cell there is first-half-only |
| Recalibrating the probability | Slope **0.135**. The whole 0.60–0.94 claimed range compresses to 0.51–0.59. Adding live-line deviation (+0.003) and time remaining (0.000) adds nothing |
| Rebuilding stage 2 | The distribution IS ~70% too wide inside 10 min (width ratio 0.51, tails 15.7% vs 20%), and `shrink_k` repairs it (0.92, 18.8%) — but re-priced at real DK lines it gets **worse**: slope 0.268 → 0.145, Brier 0.2534 → 0.2552, log-loss 0.7009 → 0.7047 |
| Per-day cap | Top-1/day is +11.4% on 21 bets, but taking the WORST 2–3 by EV returns +8.5%/+10.3%. The ranking does not discriminate, so the gain is from betting less, not choosing better |
| Smoothing the probability (rolling median over k looks, k=2..7) | Every k is negative in the second half. Requiring the crossing to persist does not pick better bets |
| Splitting by side or by quarter (2026-09-13) | Every split flips sign between the halves (over H2 −40.0% on 3, quarters 1–2 H2 −9.4% on 6). Not shipped |

**What shipped 2026-09-13 (mike: *"there were 55+ live picks this week for
NCAAF - no bueno. need only the best of the best"*).** Two changes, one PR:

- **The live models price FBS-vs-FBS only**, by the pre-game models' own rule
  (`_is_fbs`: SP+ necessary, classification may only veto), computed in
  `gameday.load_context` and enforced in `serve.price`. The loop was the one
  NCAAF surface without it. Week of 09-07: 24 of 43 `ncaaf_live_total` BETs
  and 3 of 18 `ncaaf_live_win_prob` BETs were FBS-vs-FCS. 2025 replay,
  `ncaaf_live_total`: those games fire 0.144 bets/game against 0.097 and
  return −1.1% against +2.9%. 2026 production to 09-13: 15-15, −3.19u against
  FBS-vs-FBS 36-31, −0.20u. The stage-1 training states DO include such games
  (121 of 891 in 2025), so this is scope alignment, not an out-of-distribution
  fix. All non-FBS replay bets fall in the first half, so no time split exists
  for this one; 2026 production is the second read and agrees in direction.
- **`ncaaf_live_total` 0.72 × EV 0.22 → 0.73 × EV 0.24.** FBS-vs-FBS replay:
  39 bets +2.9% → 17 bets +21.3%, 0.097 → 0.042 per game. Of the 17, 14 are
  first-half (+21.5%) and 3 second-half (+20.0%). Every cell in 0.725–0.73 ×
  EV 0.20–0.28 is positive in the first half; the second-half column is the
  same 3 bets in every one of them, so it is not a plateau read. **The replay
  says not worse; it does not prove better, and there is no production
  evidence of profit at this cut yet.**
- **`ncaaf_live_win_prob` unchanged at 0.65 × EV 0.26.** Its stricter cells
  (0.69 × 0.28, 15 bets) are peaks with 4 second-half bets, and its volume
  fix is #694, which had four clean games behind it when this shipped.

**What shipped 2026-09-19 (mike: honest re-sweep under the 0.30 floor).**
`ncaaf_live_win_prob` 0.65/0.10 → **0.50 × edge 0.16 × EV 0.30** on the
honest (promoted-map) number. Under the floor the old cut takes zero bets
on the 2025 replay; 0.50/0.16 is 43 bets 20-23 +38.6%, halves +26.4/+50.2,
plateau 5. A plus-money-dog population, not the favourites of the 2026
forward record. `ncaaf_live_total` kept at 0.73/0.12 (dark under the floor).
Canonical write-up: `docs/thresholds.md`.

**Production runs 2–3× the replay's bet rate per game, and the reason is not
fully measured.** DraftKings totals were snapshotted 141 times per in-play
game on 2026-09-12 against the replay's 64, and the best-book gate that ran
until #694 was 1.5–6pp looser. Neither has been shown to account for all of
it. Project from production, not the replay.

**Stage 1 is sound and was not changed.** Predicted remaining points are biased
by +0.2..+1.2 at every time bucket and every predicted level, and the error on
the total matches the error on the margin (RMSE 6.38 vs 5.69 late, 15.57 vs
15.03 early). The engine knows how much scoring is left.

**Why the same engine is acceptable for `ncaaf_live_win_prob`:** margin errors
partly cancel between the two sides and total errors do not, so the margin
width ratio is 0.95+ everywhere except the last ten minutes while the total's
falls to 0.51. That is also why the pregame-status correction worked there
(slope 0.816) and recalibration failed here (0.135).

**What would be a new attempt, as opposed to a repeat:** information the model
does not have. Everything above re-arranges the same two-stage output. The
harnesses are `scripts/ncaaf_live_total_rebuild.py` (stage-2 sweep, three
out-of-sample read-outs) and `scripts/ncaaf_live_total_repricing.py` (the
decisive one — re-prices held-out candidates at their OWN DK line under two
distributions). A proxy line does not decide this: the rebuild script's own
pregame-total read-out scores the shipped model at 1.30 where the real line
scores it at 0.27.

### Session 280 (2026-09-10) — the pre-game board audited, and what changed

Full detail in `docs/sessions/2026-09.md` (session 280). What a future
session needs to know:

- **The pre-game board is ONE model.** `ncaaf_moneyline` is paused; both
  spread tiers are live and cannot fire on this feed, measured on 2026: of
  249 DK-priced games, 18 had a Bovada opener inside the 90-minute skew and
  17 of those agreed within 0.5 pts; on the 128 games where Bovada posted
  later (median 5.2 days), DK's line at that moment sat 0.28 pts from
  Bovada's opener, zero at the premium band. mike declined to pause the
  tiers on 2026-09-10; they stay live, and they will keep writing "watching"
  rows.
- **"Watching" rows now say why.** Every precondition failure or inside-the-
  gate decline persists its reason in `picks.downgrade_reason`
  (`scorer._apply_no_signal`). Before this, 0 of 1,012 non-BET rows carried
  one; the doc above claimed they all did.
- **A paused model is paused on both sides** (`scorer._paused_signal`,
  sport-agnostic): `ncaaf_moneyline` had written 80 AVOID rows the Signals
  board rendered as fade signals.
- **The totals under-lean, as measured on 2026-09-10, looked spread across
  inputs.** That reading is not the 2026-09-26 one — see the remeasure below.
  What was measured that day, and is kept so it is not re-derived:
  `scripts/ncaaf_search/totals_input_drift.py`: on the 2026 board the
  production artifact predicts a mean 0.85 below DK (56.6% of games below)
  against +0.68 (47.3% below) on 2025's games through 09-20; the same lean
  inside 7 days as beyond. The market is 0.6 higher, the prediction 0.9
  lower, spread across scoring and defence inputs (no single feature, no
  NaN column); with every feature set to the 2025 mean the artifact predicts
  52.9 vs 53.1. The ECDF's −0.62 offset turns a −0.85 mean into P(under) > 0.5
  on ~three quarters of rows, which is what the board shows. The one-at-a-time
  weather deltas also fill the 44% of board rows that have no weather, so
  they partly measure missing weather; the within-7-days (−0.82, 16% missing)
  vs beyond (−0.91, 100% missing) split is what shows missing weather is not
  the driver.
- **The information test the NFL props got, run on the totals rule**
  (`scripts/ncaaf_search/totals_information_test.py`, DK close, de-vigged):
  b = +0.137 ± 0.085 (fit 2023 → read 2024) and +0.101 ± 0.086 (fit 2024 →
  read 2025). Positive both pairs, neither interval excludes zero; the book
  beats the raw model on Brier in both seasons and the blend beats the book
  by ≤ 0.001. The same verdict as the eleven NFL prop models: at the close
  the disagreement is at most marginal information.
- **Books we never request post LATER than DK, and FanDuel posts earlier.**
  One 20-credit historical snapshot (`book_timing_snapshot.py`, Monday
  2026-08-31 12:00Z, stored in `odds` as `odds_api_historical`): FanDuel,
  BetRivers, BallyBet, BetParx and Hard Rock carried 99-102 of 103 events
  against DK's 75 (FanDuel had 28 games DK did not); betonlineag 53, lowvig
  50, betus 43, betanysports 43, mybookieag 40, every one behind DK. Now that
  the decision price is best-of-book (#634), FanDuel's earlier posting is
  worth measuring as a lead; the offshore books' is not. The pull also
  created 11 `games` rows for already-played FCS-visitor games (two with the
  mascot in the id); none has a pick and they are listed for deletion in the
  session entry.
- **Kalshi lists NCAAF game markets and is now recorded** every hour at :45
  (`data/ingestors/kalshi_game_ingestor.py` → `kalshi_game_markets`): 478
  winner contracts on 239 events, 2,008 total-ladder and 2,541 spread-ladder
  contracts on 120 events at the first snapshot. Research only. The join to
  our game ids is `kalshi_ncaaf_events` (event code → `game_id`), refreshed
  after every snapshot from the winner contracts' team names: 154 of 239
  events resolved on 2026-09-11 and every FBS-vs-FBS event among them; the
  unresolved remainder are FCS games. Extend `KALSHI_TEAM_MAP` in
  `data/ingestors/kalshi_game_ingestor.py` when a label fails to resolve.
- **Issued forecasts exist for 2024-2025** (`game_weather_issued`, leads
  1/3/5, `scripts/ncaaf_weather_issued_backfill.py`), the train/serve repair
  for the three `wx_*` features. `scripts/ncaaf_search/totals_weather_source.py`
  measures the four arms (reanalysis / served / issued / none). At the 8-pt
  gate the deployed arm (train on reanalysis, serve the lead-3 forecast) reads
  53.8% in both 2024 and 2025 against reanalysis's 62.0% / 52.9%, every
  interval overlapping; training on one season of issued forecasts gives
  47.6%; no weather at all is worst (51.7% / 44.8%). The forecast haircut is
  real in one season of two and not separable at ~90 bets a season. Artifact
  unchanged; the issued series accrues for a two-season refit.

### Remeasured 2026-09-26 — low PPA, not an under-only scorer

The Sep 26 board was 10 open under BETs and 0 overs
(`picks`, `model_id='ncaaf_over_under'`, `signal_type='BET'`,
`game_date='2026-09-26'`). Season settled record from `profit_flat / 100`,
`WIN`/`LOSS` only, `result='NO_ACTION'` excluded (those 13 rows are the
2026-09-19 EV-floor void, `condition_status='VOID'`): over 6 bets 4-2
**+1.54 units**, under 16 bets 5-11 **−6.50 units**. The point gate is still
symmetric. The predictions are low, and a promoted calibration map then
deletes the marginal over.

**The scorer is side-symmetric in points.** `models/scorer.py` (`kind ==
"total_regression"`) sets `disagreement = predicted_total − DK total` and
forces NONE unless `abs(disagreement) >= artifact d_threshold` (8.0 on
`models/saved/ncaaf_over_under_20260825_204305.pkl`). Both sides are then
evaluated. The OOS residual ECDF (772 residuals, mean −0.618) is not centred:
P(over) at +8 is 0.6503 and P(under) at −8 is 0.7098, which is why the point
gate exists — a lone 0.65 floor would fire unders near −5. It is not doing
that. Every stored under BET inverts to a disagreement in **[−9.25, −8.0]**;
every stored over BET inverts to **[+8.12, +10.93]**.

**The market is not the lean.** 149 completed games that have a pick row:
mean actual − line **+0.29** (76 went over, 73 under). Mean predicted − line
on those games **−1.18**, so actual − predicted is **+1.47**. The model is
the thing sitting low. On the 200 games with a `game_date` before 2026-10-01
(one row per game; BET disagreements inverted through the ECDF, inside-gate
rows from `downgrade_reason` or the over-side probability): mean predicted −
line **−1.47** (median −1.50), 136 below the line and 64 above, 29 under the
−8 gate and 10 over the +8 gate. The Sep 26 slate is 51 games, mean **−2.31**,
10 at or past −8 and 1 at or past +8.

**Weather, tempo, SP+, and the line are not it.** All 10 open Sep 26 unders
have a `game_weather` row fetched 2026-09-26 10:21Z: temperature 58–90°F,
wind 4–12 mph, precipitation 0. FBS snapshot `as_of_date` 2026-09-23 versus
2025-09-24 (138 teams): plays/game 66.55 vs 66.57, SP+ offense 27.16 vs
27.14, SP+ defense 26.46 vs 26.61, points/game 29.18 vs 29.11. Raw scoring
in `ncaaf_team_game_log` through Sep 26 is **up**, not down: 27.90 points
per team-game in 2026 versus 27.23 in 2025 and 26.96 in 2024, on slightly
fewer plays (64.74 vs 65.35). `decision_book` on the open unders is
DraftKings or FanDuel; `line_book` is null; the gate reads the DraftKings
total.

**The input that moved is PPA, stored as `epa_per_play_*`.** Same two
snapshots: EPA offense 0.135 vs 0.202, EPA defense 0.066 vs 0.148. Success
rate and explosiveness, from the same CFBD advanced payload, did not move
(success rate offense 0.433 vs 0.435, explosiveness 1.240 vs 1.263). The
preseason prior (`as_of_date` August 1) matches the previous season's final
snapshot within 0.01 in every year 2022–2025. For 2026 it does not: offense
**−0.069**, defense **−0.068**, correlation with the 2025-12-12 finals still
0.944 (138 FBS teams). SP+ is the prior-season rating held constant on
purpose (`cfbd_ingestor._stat_row`); that part matches 2025. One snapshot,
2026-09-10, sat back near the old scale (EPA offense 0.183, defense 0.129)
and the weekends scored after 09-16 / 09-23 did not. A uniform −0.069 shift
on all four EPA columns of the production artifact, on 400 random games
drawn around these means, moves the predicted total by a mean **−2.36**
(median −2.55). That is the size of the Sep 26 lean. It is a sensitivity,
not a rescore of the live vectors. Every current under BET is only 0 to 1.3
points past the gate, so a shift of that size is what fills the under tail
and empties the over tail.

**The 0.65 floor does not treat the two arms the same, once the Platt map
is on.** The point gate is still symmetric (`abs(disagreement) >= 8`). The
decision is not, because `_decide` uses the calibrated probability and the
residual ECDF is not centred (772 residuals, mean −0.618). Read off that
ECDF and the promoted map (`a=1`, `b=−0.2816`):

| Disagreement | Raw P(side) | Calibrated | Clears 0.65? |
|---|---|---|---|
| +8.0 over | 0.6503 | 0.5838 | no |
| −8.0 under | 0.7098 | 0.6486 | no |
| +10.72 over | 0.7111 | 0.6501 | yes |
| −8.09 under | 0.7111 | 0.6501 | yes |

A large positive disagreement does produce a high P(over). It does not
produce one that clears 0.65 at the same point gap that a large negative
disagreement does. After the map, both sides need raw probability about
0.711. That is −8.1 points for an under (the gate already requires 8) and
+10.7 points for an over. Before the map, raw 0.65 is +7.95 for an over
and −5.13 for an under; the point gate is what stops the under arm firing
at −5. The map undoes that protection on the over arm only.

**What the rows do, split at the promotion.** Map promoted 2026-09-19
17:45 ET. Over BETs, all 11, were locked by 2026-09-18 13:36 UTC with
calibrated = raw (0.6516–0.7137). No over BET has been written since.
Under BETs written from 2026-09-20 on: 18, raw 0.7111–0.7280, calibrated
0.6500–0.6688, of which 16 are still open. The one post-map over that
cleared raw 0.65 is `Fresno State vs Rice Over 44.5` (raw 0.6593,
calibrated 0.5935, stored NONE). The under-BET probability knots are the
ECDF itself: 0.7150 (13 bets), 0.7176 (7), 0.7098 (4). 0.7098 is P(under)
at exactly −8.

**The 0.35–0.50 over rows are not large positive disagreements the floor
rejected.** 180 over-side `NONE` rows have median raw probability 0.4378.
They are games that have not locked a BET. 142 of them have P(over) below
0.50 (the model is not high versus the line); 109 of those carry the
inside-the-gate reason. Six more sit at raw 0.608–0.648, five of them
inside the gate, including `Boston College vs Virginia Tech Over 46.5`
(raw 0.6477) and `Georgia vs Oklahoma Over 43.5` (raw 0.6386). The over
side of an under BET is not in the table: 0 of 40 under BETs still have
an over row. The next scoring pass deletes `signal_type != 'BET'` and the
lock does not rewrite that side, so the complement (about 0.27–0.29) is
gone. Season settled record is unchanged: 22 priced bets, over 4-2
**+1.54 units**, under 5-11 **−6.50 units** (together **−4.96 units**;
the kelly sum of those 22 is −212.1).

**Demoted 2026-09-26.** Michael Alksninis approved taking that map out of
the decision path ("Demote ncaaf_over_under Platt map"). Updated-By:
mike. `data/migrations/demote_ncaaf_over_under_platt_2026_09_26.sql`
clears `promoted` on the row whose `promoted_at` is
`2026-09-19T17:45:14.751731-04:00` and whose `promoted_b` is −0.281555.
`load_calibrations` then misses the model, and `apply_calibration`
returns the raw probability. Both arms are back at the ±8 gate: raw
P(over) at +8 is 0.6503 and raw P(under) at −8 is 0.7098, and the point
gate is what still stops an under near −5. The 0.65 floor and the ±8
gate are unchanged. No side-only floor. Already-locked BETs are not
rewritten. A later promotion with a different `promoted_at` is a new
model update; this migration will not clear it.

**Open book, rechecked the same day.** Result-null BETs with
`game_date >= 2026-08-01`: **16 under, 0 over**. Raw `model_probability`
on those 16 is **0.7111–0.7280** (games 2026-09-26 through 2026-11-28).
That cluster is P(under) just past the −8 gate (the ECDF gives 0.7098 at
exactly −8). It is the left tail of a low predicted total.

**`ncaaf_live_total` does not share this path.** A search of `ncaaf_live/`
for `NCAAF_TOTALS_FEATURES`, `total_regression`, `epa_per_play`, and
`ncaaf_over_under` is empty. Its engine is LightGBM remaining points
(`ncaaf_live/engine/remaining.py`); the features are clock, score, the
posted pregame line, pace, and wind. Config kind is `"engine"`. Its record
stays with the Model Quality inventory.

**Not done, and why.** Nothing was paused. No side was flipped. The artifact
was not refit. The EV floor was not moved. The 0.65 floor was not moved.
Predicted totals are still low because 2026 PPA is. The next measurement
on that bias is one CFBD read: `/stats/season/advanced?year=2025` (no week bounds — that is what
`_prior_season_context` stores as the 2026 prior) and
`?year=2026&startWeek=1&endWeek=4`, and compare `offense.ppa` /
`defense.ppa` for one FBS school to the 2026-08-01 prior and the 2025-12-12
final. If the API still returns the ~0.18 scale, rebuild the 2026
snapshots with `refresh_ncaaf_stats`. If the API returns the low number,
the live scale has left the scale the artifact was fit on, and the prior
should be pinned to the 2025-12-12 snapshot before anyone refits.

### 2026-11-10 — the totals fit is the mean of eleven seeds; registered 2026-11-11

mike was asked "Refit the totals model as an average of 11 fits?" and answered
"yes" (2026-11-10, after `docs/ncaaf_market_audit.md` section 4).
`Updated-By: mike`.

**What changed.** The fit subsamples rows and columns, so one fit's
prediction for a game moves about 1.5 points with its random seed, against
a gate of 8. `--fit-totals` now fits the same regression eleven times (seeds
42 and 0 to 9, every other setting as before) and the model is their mean
(`models/seed_average.py`). The residuals the probability is read from, the
record at the gate and the kill line all come from the mean's out-of-sample
predictions. Same seasons as the live artifact: fitted on 2015-2019 and
2021-2025, residuals from the 2025 holdout, no 2026 rows (so the 2026 PPA
question above is untouched). The gate (8.0), the EV floor and the scorer are
unchanged. Nothing about a pick that already exists changes.

**Fitting and registering are now two steps.** `--fit-totals` writes the
artifact and prints the registry row; it registers nothing.
`--register-totals VERSION` switches the active row, after the artifact is
committed, merged and deployed. Before, one command did both, so the worker
was pointed at a file it did not have until the next deploy.

**The evidence.** `python -m scripts.ncaaf_margin_eval --walk-forward-totals
--frame <the cached frame>`: each season fitted on earlier seasons only, bet
at 8+ points from the stored close, graded at -110, units to win one. Frame:
7,574 games, built from production 2026-11-10.

| Season | Mean of eleven | Seed 42 alone (the fit that is live) |
|---|---|---|
| 2022 | 70-66, 51.5%, -2.6 units | 71-72, 49.7%, -8.2 units |
| 2023 | 76-62, 55.1%, +7.8 units | 78-73, 51.7%, -2.3 units |
| 2024 | 50-30, 62.5%, +17.0 units | 50-38, 56.8%, +8.2 units |
| 2025 | 39-33, 54.2%, +2.7 units | 45-47, 48.9%, -6.7 units |
| Pooled | **235-191, 55.2%, +24.9 units** | 244-230, 51.5%, -9.0 units |

These are the audit's records exactly. Single seeds run from seed 42 (-9.0
units) to seed 4 (266-206, +39.4 units). One game's eleven predictions have
a standard deviation of 1.49 points on average (95th percentile 2.38 over
3,071 games; the audit printed 2.39). The pooled interval is 50.4% to 59.9%
and does not clear the 52.38% breakeven. For the mean, 8 is the best gate in
hindsight in 2024 and 2025 only, and 2022 is below breakeven at 8. The gate
was not re-chosen.

**2026 did not separate the mean from a single fit.** The audit's replay of
2026 had the mean 45-44, -4.20 units, against the live artifact's 49-45,
-1.14 units, on about 90 bets each. The case for the change is the four
earlier seasons and the size of the seed noise, not this season.

**The artifact.** `models/saved/ncaaf_over_under_20261110_161059.pkl`,
18,975,013 bytes (the single fit is 1,726,409). Holdout record at the gate
39-33 (54.2%, +2.7 units). 772 residuals, mean -0.584 (the single fit:
-0.618). Seed-to-seed standard deviation on the holdout games 1.35 points
(95th percentile 2.10). On the frame's 7,570 usable games its predictions
average 0.05 points below the live artifact's (standard deviation of the
difference 1.32, correlation 0.990).

**The probability floor did not move: 0.65.** On the new residuals P(over)
at +8 is 0.6554 and P(under) at -8 is 0.7098 (the single fit: 0.6503 and
0.7098). The floor's job is to sit just under the weaker arm so it never
suppresses a pick the gate admits, and 0.65 does that for both artifacts, so
it also holds between the merge and a registration.
`tests/test_ncaaf_totals_seed_fit.py` checks it against every totals artifact
in the repo. At -110 the two arms at the gate are worth EV +0.251 and +0.355,
over the model's 0.20 floor; an over exactly at the gate clears that floor at
-120 or better, an under at -144 or better. The 0.20 stale-line cap writes no
row once the DraftKings edge passes 0.20, so at -110 an over can be bet from
+8.0 to +10.9 points (the single fit: +11.3) and an under from -8.0 to -8.92
(-8.85).

**WHY IT IS NOT REGISTERED: a game with no weather forecast.** The weather
step (`run_pipeline --step ncaaf-weather`) fetches forecasts for games up to
7 days out, once a day. The totals rule scores any game DraftKings prices,
with no lead limit. A game scored before its forecast exists is served with
its three weather inputs missing, and a tree sends a missing value wherever
its training rows taught it to. The frame this fit used has ONE game of
7,570 with no weather, so nothing taught it: 91% to 93% of each new member's
weather splits send a missing value to the high side, as if the wind, rain
and heat were extreme. The fit of 2026-08-25 sends 61% there. (Both were
fitted with the same xgboost, 3.4.1. The frame of 2026-08-25 was not kept, so
whether it had more games without weather is not established.) Measured on
the 768 games of 2025 that have every input:

| Inputs missing | Live single fit | Mean of eleven |
|---|---|---|
| The three weather inputs | -1.89 points (sd 3.61); unders at the gate 51 to 78 | **-11.66 points (sd 4.39); unders at the gate 48 to 547**, overs 73 to 4 |
| Venue elevation (dome and grass blanked too) | -2.57 points (sd 2.79); unders 51 to 123 | -2.05 points (sd 2.52); unders 48 to 103 |
| Both | -4.48 points (sd 4.83); unders 51 to 187 | -15.02 points (sd 6.07); 640 of 768 games an under |

Every one of the eleven members does it alone (-10.6 to -13.4), so this
belongs to any fit on today's frame, not to averaging: a plain refit would
have shipped it. Of the 547 games the mean puts at or past -8 with the
weather missing, 35 are inside the stale-line cap at -110 and could be
written as an under bet (a pick locks the first time the gate is crossed);
the other 512 are past the cap and would get no row. So the fit now measures
this and stores it in the artifact, and `--register-totals` refuses an
artifact whose prediction moves as far as the gate when an input is missing.
For the weather inputs one thing lifts the refusal: the scorer holding such a
game undecided. Registration proves that by calling the hold
(`models.scorer.totals_weather_hold`) on a game with each weather input
missing; a scorer without it, or with one that does not hold, leaves the
artifact refused. There is no flag that registers it anyway. So this artifact
cannot go live without the hold and can once the hold has shipped (its venue
shift, 2.05 points, is under the gate). NOT measured: how many 2026 games and bets were scored without
a weather row. One query answers it: the bets of this model in `picks` whose
`created_at` is more than 7 days before `game_date`.

The size is an accident of the fit, not something learned. The four
walk-forward fits, whose training seasons hold no game without weather at
all, move 3.99 points on average when the weather is missing; the final fit,
whose 2025 season holds the one such game, moves 11.66.

**What the rule is worth with no forecast.** The same walk-forward
(2022-2025, stored close, -110), every game scored as if its forecast did not
exist yet:

| Weather inputs | Record | Units | Mean shift |
|---|---|---|---|
| As stored (the true weather) | 235-191, 55.2% | +24.9 | |
| Missing, as the scorer serves it | 486-450, 51.9% | -9.0 | -3.99 points |
| Set to typical weather (the training seasons' medians: 70.7°F, 7 mph, no rain on the full frame) | 236-213, 52.6% | +1.7 | +0.59 points |

By season with the weather missing: 118-113, 113-101, 130-122, 125-114.
Without the weather the rule is about break-even over four seasons, however
the gap is filled. The stored weather is the reanalysis (what happened), so
+24.9 is an upper bound on what a forecast is worth; the live model is served
forecasts. No backtest in this file or in the audit grades a bet made before
a forecast existed: the audit's live-shape run starts five days out.

**The weather hold (mike, 2026-11-10: *"yes wait for a weather forecast"*).**
It was built as one commit ahead of his answer and ships with the refit: the
eleven-seed artifact cannot be registered without it. In practice it means no
totals bet more than 7 days before kickoff: this season the 9 kept bets placed
earlier than that went 4-5, -1.55 units, and none has been placed that early
since the schedule hold of 2026-10-20 (read-only SQL on `picks`, 2026-11-10).
While any of the
three weather inputs is missing at scoring time, the totals model does not
decide the game. Its rows are written NONE with "waiting for the weather
forecast", 0.5 a side (the model is not asked for a number it cannot give),
the way a schedule hold writes its rows (`models/scorer.py`,
`totals_weather_hold`). A NONE row never locks, so the first pass after the
forecast exists decides the game. A BET that is already locked is never
scored again, so it is untouched. What the hold rests on, from the code:

- *When the forecast arrives.* `run_pipeline.step_ncaaf_weather` calls
  `ingest_upcoming(days_ahead=7)`: games dated today to 7 days out. It runs
  once a day in the morning pipeline, before scoring. The hourly refresh pass
  (`scripts/refresh_pass.sh`) does not run it. So a held game is decided the
  first morning it is 7 days out, and a game first priced inside that window
  during the day waits for the next morning. Adding the step to the refresh
  pass would cut that wait to an hour; it was not added.
- *Domes.* Training rows and the forecast step both give a dome 72°F, no
  wind, no rain (312 of the 328 dome games in the training frame). So a dome
  game with no weather row is served those values and decided: it has no
  forecast to wait for, and one whose venue has no coordinates would never
  get a row.
- *Neutral sites.* Training has the weather at the game's own venue. The
  forecast step uses that venue once it is known and the home team's usual
  venue until then, so a neutral-site game gets a row like any other. A game
  whose venue has no coordinates at all gets none, in training or at serve
  time (one game of 7,570 in the frame), and is held until kickoff.
- *This model only.* The three inputs are in the totals feature list and no
  other NCAAF model's.

The live fit has a smaller version of the same thing: a game with no
forecast reads 1.9 points low and one with no known venue 2.6 low, which
turns 51 unders at the gate into 78 and 123. That may be part of the 2026
under lean measured on 2026-09-26. It has not been checked against the
stored picks.

**What it costs to run.** The scorer loads the artifact once per game
(`models/scorer.score_game` calls `models/trainer.load_model`, which reads
and unpickles the file every time) and then predicts one row. On this
machine, with nothing else running: the load is 473 ms (the single fit: 36)
and the first prediction after it was 62 ms (2.8). With other work running
on the machine the load took up to 844 ms and the prediction up to 391.

- *The prediction, fixed.* Each member was fitted with `n_jobs=-1` and
  started a thread pool to predict one row, eleven times a game.
  `models/seed_average.py` now sets every member to one thread when the model
  is built or loaded. Timed in pairs in one process (15 fresh loads each
  way): 155 ms as fitted, 40 ms on one thread; a second prediction on the
  same object 67 ms and 23 ms. No predicted value changes: all 7,570 games of
  the frame are identical to the last bit, largest difference 0.0.
- *The load, not fixed.* About 0.5 seconds a game, nine tenths of what the
  new artifact adds, is unpickling eleven sets of 700 trees. It is paid per
  game because the loader does not keep what it has read. Keeping it (one
  load per scoring process) is a change to the loader every model uses, so
  it was left as a decision.

**Other models.** `models/seed_average.py` holds any fitted regressors. The
seed noise was measured for this model only. `fit_and_register` (the retired
spread regression) still writes and registers in one step; it is unused and
was left alone. The research harnesses under `scripts/ncaaf_search/` still
fit one seed.

**Steps, in order.**

1. Decide what the totals model does with a game that has no weather
   forecast yet (mike's call; it changes when the model bets). The measured
   choices: hold the game as a watching row until its forecast exists, which
   is the only regime any backtest covers and is what the hold commit does;
   or price it with typical weather, which was 236-213, +1.7 units over four
   seasons. The hold changes the live fit too, from the day it deploys: a
   game more than 7 days out stops being bet until its forecast exists.
   Without the hold commit, merging this branch changes no pick.
2. Once the scorer holds such a game: merge, and wait for both services to
   deploy. The hold has to be running on the worker before the new artifact
   is active, so the order is hold deployed first, registration second.
3. `python -m scripts.ncaaf_margin_eval --register-totals 20261110_161059`,
   run from a checkout that has the same scorer the worker has (a production
   write: it checks that scorer for the hold, copies the file into
   `model_artifacts`, then switches the active `model_registry` row).
4. `python -m data.threshold_sync` (the floor did not move, so this changes
   nothing; it is the standing step after a model update).
5. Read back `model_registry` for `ncaaf_over_under` (one active row, the new
   path) and the next pass's `model_artifacts_load` health line.

To go back after a registration: set the 2026-08-25 row active again in
`model_registry` and the new one inactive. The old file stays in the repo
for that reason. `--register-totals` cannot do it, because the old file
carries no registry row of its own.

**2026-11-11: registered.** #1238 merged at 14:17 UTC, both services
deployed by 14:24, and the steps above were run at 14:25:35 UTC
(`Updated-By: mike`, "merge 1238"). `model_registry` holds
20261110_161059 active and 20260825_204305 inactive. The worker opened the
file: its health check at 14:30 UTC read `model_artifacts_load` OK across
all 43 active files, and its first scoring pass re-scored 48 games with no
new bet and none waiting for a forecast. The August file's bytes are in
`model_artifacts` too, so going back works even after that file leaves git.
Detail: `docs/sessions/2026-11.md`, the 2026-11-11 entry.
