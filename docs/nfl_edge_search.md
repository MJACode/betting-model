# The NFL edge search, 2026-10-11: why the in-play model was retired, and what else was tested

*mike, 2026-10-11: "Why did we retire live nfl betting, let's find a profitable
nfl model leveraging all available data and sources, and look online for non
arbitrage methods ... don't want too high of volume, want to find extreme +EV
opps."*

Zero Odds API credits were spent. Every test reads a local cache of data
already stored in Supabase, or free public data (nflverse, Open-Meteo, Kalshi's
public market data). Each one wrote its construction down before it read an
outcome. Each was then attacked by two independent verifiers: one looking for
look-ahead and grading errors, one for multiplicity and peak-chasing. Every
number below names the script that prints it.

---

## 0. The short version

| question | answer |
|---|---|
| Why was in-play NFL betting retired? | mike's instruction, 2026-10-04, at 7-17 (−10.27 units over 24 settled bets, one still open). It is 7-18 (−11.27 units over 25) since that bet settled. 22 of the 25 came from a pass-attempt OVER model that gave every quote the same probability (§1). |
| Is there a new low-volume, extreme-EV NFL model? | **No new one survives.** Fourteen ideas were tested. Thirteen are null, negative, or a selection artefact (§3). |
| What does survive? | **The in-play rushing-attempt UNDER**, the rule that replaced the pass-attempt overs on 09-21. It was rebuilt independently: 960 bets, +11.79% (90% CI +6.8, +16.8), positive in every season. It has no out-of-sample season (§4). |
| What is the biggest practical finding? | **The one validated pre-game model, `nfl_prop_market`, has bet nothing since 2026-09-19.** Two things block it: a 0.20 EV floor, which allows 1 bet in three seasons of its own record, and a calibration offset borrowed from other models. At a 0.07 floor on its own probability, the same record is 54 bets a season at +20.89% (§5). |

---

## 1. Why the in-play model was retired

Taken from `picks` (`model_id='nfl_live_prop'`) and docs/sessions/2026-10.md (2026-10-04):

- Retired 2026-10-04 on mike's instruction: *"I want these stricken from the
  record. It was never a good model. Remove this model."* It is in
  `config.RETIRED_MODELS` and `RECORD_EXCLUSIONS`. The worker has
  `RUN_NFL_LIVE=0`.
- Settled record when he ordered it: 7-17, −10.27 units over 24 bets, with one open. Since that bet settled: **7-18, −11.27 units over 25 bets.**
- **22 of the 25** were pass-attempt OVERS (09-09 to 09-20). That model returned
  one constant probability (0.6003, or 0.642 on the blind arm). Its EV cut was
  therefore a price filter, and the 2.33-attempt bias it was built on measures
  −0.12 (95% CI −0.42, +0.18) (docs/nfl_live_prop_assessment.md).
- **3 of the 25** were rushing-attempt UNDERS, the replacement from 09-21:
  - MarShawn Lloyd Under 4.5 Carries, WIN
  - Blake Corum Under 11.5 Carries, LOSS
  - Kaytron Allen Under 2.5 Carries, LOSS

  That is 1-2, −0.65 units.

So the record that ended the model was the pass-attempt model's. The rushing rule
that replaced it had three settled bets. Section 4 tests it.

---

## 2. Data and method

The cache comes from `python -m scripts.nfl_edge_cache` and is written to
`%TEMP%/nfl_edge`. Every read is indexed, read-only and chunked.

| data | rows | from |
|---|---|---|
| game lines by book, snapshots every few hours, 2020-25 | 2,259,325 | `nfl_odds_history` |
| 2026 spreads, per minute, 12 books (spreads only) | 5,935,121 | `nfl_odds_history` |
| player props incl. alternate ladders, ~15 books, 2023 to 2026-09-09 | 6,494,635 | main checkout `data/local/nfl_prop_odds.parquet` (holds history Supabase has pruned) |
| 2026 prop board weeks 1-5, latest quote per lead bucket | 2,083,174 | `player_prop_odds` |
| DK/FD in-play prop archive 2023-25 | 5,333 blobs → 74,317 two-sided quotes | `nfl_live_prop_snapshots` |
| play-by-play 1999-2026, schedules with closing lines, injuries, officials | — | nflverse (free) |
| ERA5 / issued wind and rain forecasts | ~2,600 responses | Open-Meteo (free) |
| Kalshi NFL winner markets, 1-minute candles, 2025 + 2026 | 338 games | Kalshi public API (free) |

Research: 7 web lenses (academic, practitioner game lines, in-play, prop
settlement, exchanges, situational and alt data, derivatives) plus a catalogue of
the 57 NFL tests this repo had already run. The catalogue set the "already
closed" list, so nothing closed was re-run as if it were new.

**The protocol for every test:**
- the construction is fixed first;
- parameters are fit on earlier seasons and the hold-out is read once;
- grading is at real bettable prices;
- each test has a placebo;
- the grid is reported as a neighbourhood;
- every season is shown separately;
- confidence intervals are bootstrapped by game;
- multiplicity is counted.

---

## 3. Everything tested

"Verdict" is after both verifiers.

| # | idea | best honest cell | bets / season | verdict | script |
|---|---|---|---|---|---|
| 1 | **In-play rushing-attempt under, pace ratio ≥ 1.25** | 960 bets, +11.79% (+6.8, +16.8) | ~320 (halftime only: ~155) | **survives, in-sample only** | `nfl_edge_live_rush_pace` |
| 2 | Wong teasers (6 pts through 3 and 7) | at DraftKings' own line: 74.33% legs, 194 two-team tickets +1.1% at −120 | ~32 tickets | null (break-even at one book) | `nfl_edge_wong_teaser` |
| 3 | Extreme sharp-vs-soft prop gaps (10-25pp) | they barely exist: largest single-read gap 12.4pp, 1 bet ≥ 10pp a season | ~0 | null | `nfl_edge_extreme_props` |
| 4 | Wind × passing props (all) | observed ≥ 15 mph: +8.7% (+1.1, +16.4) on 1,411 correlated bets | — | marginal | `nfl_edge_prop_wind` |
| 5 | Wind × QB passing-yards under (forecast ≥ 16 mph) | 34 bets, +49.1%, but a step at 15 mph; no slope in 10-18 mph over ten seasons | ~17 | selection artefact (§6) | `nfl_edge_qb_wind` |
| 6 | Rain-in-calm unders, true hold-out 2000-15 | 181 bets, +5.58% (−6.0, +17.1), BH-adj p 0.84 | ~11 | null | `nfl_edge_weather` |
| 7 | Heat unders (≥ 85°F) | 177 bets, −1.80% | ~9 | null | `nfl_edge_weather` |
| 8 | Luck regression, sides and totals | hold-out 179 bets, −6.36% | ~30 | negative | `nfl_edge_luck_gap` |
| 9 | Week-1 holdover (bet against last year's playoff team) | hold-out 2013-25: +1.8% | ~7 | null | `nfl_edge_gameline_rules` |
| 10 | Small moneyline dogs, big dogs in low totals, late-season spoilers, fading big moves, moneyline-vs-spread | 0 of 297 cells survive Benjamini-Hochberg | — | null | `nfl_edge_gameline_rules` |
| 11 | Halftime second-half lines (SBR 2011-21) | 0 of 7 rules survive; 2H under in wind pooled +10.9%, p 0.038 vs a 0.014 bar | ~20 | null | `nfl_edge_halftime` |
| 12 | Settlement mismatches (FanDuel special-teams tackles, half sacks, QB kneel-downs, return TDs) | 0 of 9 tests survive; FanDuel tackles untestable (16 quotes) | — | null | `nfl_edge_settlement` |
| 13 | Kalshi as a venue (pre-game vs Pinnacle; late-game leaders in play) | pre-game mid within ±2.7¢ of Pinnacle on 266 games; late leaders −1.35% | — | null | `nfl_edge_kalshi` |
| 14 | 2026 out-of-sample reads of the existing rules | 5 weeks; no cell distinguishable from its backtest or from zero | — | untestable yet | `nfl_edge_preregistered_2026` |

Already closed before today, so not re-run: the eleven stat projection
models, the market-anchored shape simulation, the DK ladder, opener totals and
moneylines, and the ~35-rule situational scan (docs/nfl_prop_method_search.md,
nfl/README.md).

---

## 4. The survivor: in-play rushing-attempt UNDER

**The rule.** This is the rule as the repo shipped it on 09-21 (docs/nfl_live_rush_attempts.md):
- Bet the UNDER on a live DraftKings rushing-attempts prop when the over still
  needs the player to run at ≥ 1.25× his own pace so far.
- pace ratio = ((line − carries so far) / minutes left) ÷ (carries so far / minutes elapsed).
- The price must be −140 or better.
- One bet per player per game.

**The independent rebuild.** Game state is joined from play-by-play using only
plays that had ENDED before the quote's timestamp:

| | bets | won | units | ROI | 90% CI |
|---|---|---|---|---|---|
| 2023 | 304 | 58.6% | +33.06 | +10.87% | (+1.7, +19.7) |
| 2024 | 347 | 57.3% | +28.01 | +8.07% | (−0.3, +16.4) |
| 2025 | 309 | 61.2% | +52.09 | +16.86% | (+7.8, +25.9) |
| **pooled** | **960** | **59.0%** | **+113.16** | **+11.79%** | **(+6.8, +16.8)** |
| blind under, same gates, no pace cut | 2,315 | 52.0% | −5.22 | −0.23% | (−3.3, +2.7) |
| the complement (pace < 1.25) | 1,704 | 48.8% | −96.36 | −5.66% | (−9.3, −2.1) |

**Why it is credible:**
- **Placebo.** Accrued carries were shuffled within season × phase × line: 0 of
  200 draws reach +11.79% (mean +0.60%).
- **Plateau.** Every pace cut from 1.0 to 2.5 is positive (+8.19% to +17.27%).
- **Matched strata.** Within season, phase, line and price, the pace cut adds
  +14.6pp per bet.
- **Timing test.** Building the state 15-600 s too early leaves ROI at
  +9.8-12.5%. Building it too late inflates it. So the state is not leaking.

**Placeability.** Almost all of the profit comes in stoppages. Mid-drive quotes
made +0.31 units on 217 bets. The halftime-only subset is **466 bets, +15.84%
(+8.6, +22.9)**, at 120 / 132 / 214 bets per season. It is the one moment
DraftKings cannot suspend the market on the snap. That is why it is the
operational subset, not because it is the best ROI cell.

**What is NOT established (read before acting):**
1. **No out-of-sample season.** The market (carries) and side (under) were
   chosen by reading the pooled 2023-25 table of 4 markets × 2 sides. An ×8
   adjustment still leaves the interval above zero, at (+4.0, +19.3).
2. **2025 is one snapshot per game, near halftime**, and that season had a
   market-wide under lean (the blind under made +5.25%). Without 2025 the rule
   is +9.38% (+3.2, +15.6).
3. **The archive is five fixed game-clock points per game (2023-24) and one
   (2025)**, not "a snapshot every five minutes" as
   docs/nfl_live_rush_attempts.md said. That doc now carries the correction.
4. **No 2026 quote was stored.** The worker polled this market from 09-21 to
   10-04, but only its picks rows survive (3 BET and 8 AVOID carries rows). Nothing
   recorded the quotes, so the 2026 out-of-sample read cannot be made.
5. The same pace construction on receptions and completions, read once on
   2025, is flat or negative (−0.98% on 335 and 143 bets).

**What a forward test needs:**
- a new model id (`nfl_live_prop` is struck);
- a scheduler job, because `RUN_NFL_LIVE` defaults off;
- one live event-odds call per game at halftime, for one market in one region.

By the documented live formula (unique markets × regions = 1 credit a call),
that is about 16-20 credits a week. That figure is arithmetic, not a measured
bill.

---

## 5. The validated pre-game model is switched off

`nfl_prop_market` de-vigs Pinnacle or BetOnline and bets a soft book quoting
the same line at a better price. It is the only NFL model with a clean pre-game
record: 2023-25, 1,990 bets, +7.84% (docs/nfl_prop_over_lean.md).

**It has written no BET since 2026-09-19 20:27 UTC** (`picks`). The cause is in
the worker's own card log on 2026-10-11:

```
nfl_prop_market: ev_below_floor:0.037<0.20 (p 0.573->0.506 at +105) — dropped carnelltate player_receptions under 4.5
nfl_prop_market: ev_below_floor:0.075<0.20 (p 0.523->0.500 at +115) — dropped dandreswift player_receptions over 2.5
```

Two things stop it:
- **The floor.** `config.MODEL_OWN_EV_FLOOR["nfl_prop_market"]` is 0.20.
- **The calibration map.** It pulls its probabilities to about 0.50 before the
  EV is taken (0.573 → 0.506, 0.523 → 0.500, 0.584 → 0.517).
  - `model_calibration` holds an offset (a = 1, b = −0.28) fitted on n = 23 graded
    picks. Its own note reads "prior-dominated: pooled offset −0.268 worth 150
    picks", so it is mostly the offset borrowed from the other models.
  - It was promoted 2026-09-19 21:45 UTC with `promoted_helps = false`. That is
    78 minutes after the model's last BET.
  - This is the same situation that put wind, opener and NHL blocked shots into
    `config.MODELS_ON_OWN_PROBABILITY`.

Lowering the floor alone would not restore it.

**What each floor would have bet on its own record.**
`python -m scripts.nfl_edge_prop_market_floor` Part A uses the board-synchronous
version of the shipped rule:
- the latest read inside 24h;
- the shipped side cuts, over 6pp / under 5pp;
- the best bettable price;
- EV on the raw reference probability.

| EV floor | bets | / season | units | ROI | 90% CI | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|
| 0.00 | 971 | 324 | +138.7 | +14.29% | (+9.5, +19.4) | +14.0% | +19.8% | +10.1% |
| 0.03 | 868 | 289 | +131.3 | +15.13% | (+9.9, +20.4) | +13.6% | +23.5% | +10.7% |
| 0.05 | 473 | 158 | +87.0 | +18.39% | (+10.8, +26.4) | +19.2% | +31.0% | +8.8% |
| **0.07** | **163** | **54** | **+34.0** | **+20.89%** | **(+7.2, +34.3)** | **+18.6%** | **+35.1%** | **+13.2%** |
| 0.10 | 29 | 10 | +3.2 | +11.00% | (−24.0, +47.8) | +59.0% | −39.2% | +20.0% |
| 0.20 (today) | 1 | 0 | −1.0 | — | — | — | — | — |

ROI rises with the floor up to 0.07, every season stays positive, and the
interval excludes zero. That is a plateau, and it is the shape a sharp reference
predicts.

**Caveats:**
- The floor was swept in-sample.
- The realised ROI runs above the EV the reference promises. Part of that is the
  documented over-lean (unders win more).
- **2026 points the other way.** The production record is 39 bets, 19-20,
  −2.49 units, −6.4%. A replay of weeks 1-5 on quotes actually on the board is
  −18.4% on 67 bets. Five weeks cannot separate +13% from zero: that needs
  ~250-370 bets.
- 2026 volume is about a third of the 2023-25 rate per game.

**Pulled props.** The production loader keeps each book's latest row however
old it is. A prop the book has pulled therefore stays "bettable" at its old
price. Of production's 39 settled BETs, **6 locked on a proposition the book had
stopped quoting** while it still quoted the rest of the market (gap ≥ 2h at the
lock, bucket resolution). Those 6 went 2-4. Example: Tyjae Spears Under 2.5 Rec
(hardrockbet), last quoted 66 hours before the lock. Not fixed here.

**Settlement.** Two picks on 2026-09-17 settled NO_ACTION although the player
played: `Joshua Palmer Under 1.5 Rec (MGM)` and `Joshua Palmer Under 11.5 Rec
Yds (betrivers)`. The stat log spells him "Josh". Graded through a nickname
join, the first wins and the second loses (he had 43 yards). Not fixed here; the
fix belongs in the grader's name join.

---

## 6. Wind and QB passing yards: why the +49% is not the edge

Forecast ≥ 16 mph, QB passing-yards under, one QB per team, 2024-25: **34 bets,
17 games, +49.1%**. Both fit directions chose 16 mph. DraftKings alone matches
the best price. It still fails:

- **No slope where the bets sit.** Over ten seasons (2016-25, 1,862 open-air
  games) the effect of real wind on passing yards rests on 9 games at 22+ mph.
  Fitted over 10-18 mph it is +0.1 / −0.3 yards per mph (p 0.90 / 0.77).
- **A step, not a dose-response.** In 1-mph forecast bins the under loses in
  every bin from 10 to 15 (14-15: −31.6%) and wins in every bin from 15 up
  (15-16: +41.6%). That is one passing slump across 25 games tied to a label.
- **The label beats the wind.** Of 36 games with real 15+ mph wind, the 19 the
  forecast flagged returned +26.8% and the 17 it missed −6.1%.
- **Placebo.** The same venue's forecast a week later swings ROI by −25% to −53%
  in cells this size. That is the noise floor.
- **The books already adjust.** QB lines sit 9-16 yards below the same QB's calm
  lines in windy games.

The implied edge from the mechanism and the line's own adjustment is about −1% to
+3%, with intervals of about ±15 points. Nothing survives the family-wise test
(best p 0.087-0.118).

---

## 7. Data this search did not buy

None was bought on 2026-10-11. The first two rows were bought on 2026-10-12
(§9); the last two are still not bought.

| data | what it would answer | credits |
|---|---|---|
| 2H spreads + totals at halftime, 2023-25 | test idea 11 at real prices, not SBR at −110 | 34,200 per season (~102,600) |
| 2025 in-play featured markets, every 5 min | live game-line tests on a full season | ~170,490 for one season |
| team totals + 1H spreads/totals at T-1h, 2023-25 | derivative pricing vs full game | ~25,842 |
| alternate spreads + totals at T-1h, 2023-25 | key-number ladder pricing | ~17,292 |

These figures come from the documented historical formula and the repo's game
counts. The research agent did the arithmetic; nothing was measured on a live
call.

---

## 9. 2026-10-12: the decisions carried out

mike: "1) yes 2) no 3) yes 4) yes 5) yes 6) merge 918".

**The prop model is back on** (#920, `Updated-By: mike`).
- `nfl_prop_market` now has an EV floor of 0.07 and decides on the sharp
  reference's own probability.
- Measured in the card's own setup (its six soft books, its own price), 0.07 on
  2023-25 is 148 bets, ~49 a season, +21.95% (90% CI +7.7, +36.0). Every season
  is positive (`scripts/nfl_edge_prop_market_floor.py part_a_card`).
- The card drops props a book has pulled. On its first run after deploy (14:25Z)
  it logged "26 quote(s) dropped". It found no qualifying edge on the one game in
  range.

**The settlement fallback** joins "Joshua" and "Josh" Palmer. It needs:
- the same surname;
- a matching first name: equal, a nickname, or a 3+ letter prefix;
- that the pick's spelling appears nowhere else in the stat log.

A first version without those guards matched 130 of 13,895 skill-player
absences to a different player; the shipped version matches 0. The two picks
were re-graded on production:
- `Joshua Palmer Under 1.5 Rec (MGM)`: WIN, +0.54 units.
- `Joshua Palmer Under 11.5 Rec Yds (betrivers)`: LOSS, −1 unit.

**The two purchases** (#921, `data/ingestors/nfl_inplay_history.py`):

| purchase | calls | credits | rows |
|---|---|---|---|
| halftime 2H spreads + totals, 2023-25 (835 games) | 2,941 + 409 event lists | 59,129 | 14,601 |
| 2025 in-game h2h / spreads / totals every 5 min (285 games) | 5,491 | 164,700 | 216,782 |

Both purchases sit in `nfl_odds_history` with a `source` marker, and every call
is recorded in `nfl_odds_history_pulls`.

**Halftime, out of sample at real prices** (`scripts/nfl_edge_halftime_oos.py`): null.
- Real 2H lines carry about −115 on both sides, so break-even is ~53.5%, not the
  52.4% the SBR study assumed.
- None of the 9 frozen rules survives Benjamini-Hochberg. Wind ≥ 15 mph 2H
  under: 51 bets, −0.7%.
- The trailing-team rule went −15% on the 217 bets outside its published record.
- 2H dogs +7: 47 bets, +10.7%, p 0.22.
- The market does over-react to the first half: +0.058 points per point of
  surprise (90% CI +0.006, +0.111). That is smaller than the vig.

**2025 in-game, at real prices** (`scripts/nfl_edge_inplay_2025.py`): null.
- 0 of 132 cells survive Benjamini-Hochberg.
- Late-game leader moneylines at DraftKings: −4.6% to +2.7% across cuts.
- DraftKings' live hold is 5.6% on the moneyline, 6.6% on spreads and 6.7% on
  totals, against 4.3-4.7% pre-kick.
- The only positive cells come from the best of five books at one snapshot.
  Graded at the median book they earn +1.1%: the gain is a book that had not
  caught up, i.e. cross-book latency, not a model.
- A second season would cost about 161,940 credits (2024).

**A second in-game season, 2024** (mike, 2026-10-12: "Yes buy a second in-game
season"). 5,398 calls, 161,940 credits, 182,581 rows. Graded with
`scripts/nfl_edge_inplay_2024.py`:
- every model refit on 2016-23, so 2024 is out of sample;
- the 2025 reviewers' fixes applied to both seasons;
- 2025 reproduced cell for cell first.

Result: marginal, not a model.
- **The pre-registered family:** pooled 2024+2025, 0 of 60 clean cells survive
  Benjamini-Hochberg at DraftKings' price or at the median book.
- **Late-game leader moneyline at DraftKings** (≤ 10 min left, lead 4-16, the
  2016-23 model's win probability at least 2 points above DK's price): 2024
  +15.8% on 87 bets, 2025 +2.3% on 80. Pooled 167 bets, +9.4% (90% CI +1.8,
  +16.8), p 0.022.
- **The two seasons are statistically consistent** with one effect of about
  +9-11%. Part of the 2024 gain is that leaders beat the model that season more
  than usual (+0.026, about one season-to-season SD). Two seasons cannot rule
  out a +5% edge; its power is about 0.27.
- **The lagging book is real and is latency.** William Hill and FanDuel quotes
  were often stale: William Hill's moneyline was unchanged after a score in
  19.8% of 2024 snapshots, DraftKings' in 3-5%. Buying a stale quote against the
  other books' median pays on moneylines in both seasons. By the next snapshot
  the gap had closed in 60-71% of cases. Not proposed: it is cross-book
  latency, and 5-minute snapshots cannot show whether a quote was bettable.

**The fetched free data** is in `nfl_research_data_backup`:
- 3,067 files, 467 MB raw, 271.6 MB gzipped;
- `--verify` found 0 mismatches;
- two files were spot-restored.

## 8. Reproduce

```bash
python -m scripts.nfl_edge_cache            # build the cache (read-only, ~1h)
python -m scripts.nfl_edge_live_rush_pace   # section 4
python -m scripts.nfl_edge_prop_market_floor  # section 5
python -m scripts.nfl_edge_qb_wind          # section 6
# every other row of section 3 names its script
```

**Not in Supabase:**
- the Kalshi candles (136 MB);
- the Open-Meteo responses (~29 MB);
- nflverse play-by-play 1999-2015.

All three sit only in `%TEMP%/nfl_edge`. Every result built on them is null, and
the scripts re-fetch them for free.
