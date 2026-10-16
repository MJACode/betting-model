# NBA models, 2026-27 rebuild — pre-registered bars, the market grid, the results

Asked for by mike on 2026-10-15: retire every previous NBA model, look at every
game and prop market, use every data source we hold or can get, and carry over
what the other sports taught us — schedule (back-to-backs, road trips) named
explicitly.

**This file was written BEFORE any NBA model was graded against a price.** The
bars in §1 are fixed. A model that misses one does not ship, and the grid row
says why. Nothing here is re-thresholded after the fact; a later change to a
bar gets its own dated line and reason.

---

## 1. Pre-registered bars (fixed 2026-10-15, before the first grid)

A candidate ships LIVE (CLAUDE.md §2: every model is live real money) only if
every line holds on the seasons it was NOT fit on:

1. **Graded at real prices.** The deciding price is the best bettable book at
   the same line (`config.BEST_LINE_BOOKMAKERS`); DraftKings alone is reported
   beside it. Pinnacle and Bovada are never a deciding price. No -110 fallback.
2. **Units, one unit to win** (`tracking/discord_notifier.stake_for`: risk =
   1/(decimal−1), capped at 3u). ROI is units won over units risked.
3. **Every scored candidate is graded, not just bets** (CLAUDE.md §7): the
   grid is built over every priced proposition, and a cut is a neighbourhood.
4. **Walk-forward.** Fit on seasons before S, grade S. Props: grade 2023-24,
   2024-25, 2025-26. Game lines: grade 2021-22 through 2025-26. The cut is
   chosen on the earlier graded seasons and **confirmed on 2025-26**, the
   newest season, which is never used to choose anything.
5. **Positive in every graded season** with ≥ 30 bets.
6. **≥ 200 bets at the chosen cut, whole-day bootstrap 90% CI above zero**
   (4,000 resamples, seed 7 — the NHL derivative-totals gate).
7. **Plateau, not a peak:** the cut's neighbours (±1 step on each axis) are
   positive too.
8. **Both date halves positive** (early/late split within the graded window).
9. **Beats the blind baseline on the same side.** If the model bets one side
   more than 70% of the time, it must beat a blind bet on that side at the
   same price and the same cut population — otherwise it is the market lean,
   not the model, and the lean is reported as the finding.
10. **Placebo:** model probabilities shuffled within each date must lose the
    edge.
11. **CLV where a later price exists:** the median bet beats the no-vig sharp
    close (Pinnacle when it quotes the market; the soft-book consensus
    otherwise).
12. **No look-ahead.** Every input is known at the decision timestamp: odds
    bounded `snapshot_at <= decision time < commence_time`; injury status from
    the official report filed before the decision; schedule inputs from the
    schedule (known in advance), never from a result after the opener posted.
13. **Name integrity:** two players sharing a name never share a price
    (the NHL namesake defect, +89.8u phantom).

**Kill criterion:** a market family with no cut passing 4-11 on the graded
seasons is closed for 2026-27 with its grid recorded here. It is not
re-thresholded to find a pass.

---

## 2. Data used (all in Supabase)

| Data | Table | Coverage | How it got there |
|---|---|---|---|
| Games, scores, tip-off, neutral site, OT | `games`, `nba_schedule` | 2018-19 → 2026-27 schedule | nba_api `leaguegamelog` + `scheduleleaguev2` (`data/ingestors/nba_schedule_ingestor.py`) |
| Player box scores | `nba_player_game_log` | 2018-19 → 2025-26 | nba_api |
| Box-score detail (starters, exact minutes, +/-, fouls, inactives, officials) | `nba_player_game_adv`, `nba_game_inactives`, `nba_game_officials` | 2018-19 → 2025-26 | `data/ingestors/nba_box_enrich.py` |
| Official injury report, timestamped | `nba_injury_report` | 2018-12 → 2026-04 | `data/ingestors/nba_injury_report.py` |
| Game lines h2h/spreads/totals, 10 books incl. Pinnacle | `odds` (`source='odds_api_historical'`) | 2020-21 → 2025-26, 9 snapshots per game date | `data/ingestors/nba_odds_history.py --lines` |
| Player props, 14 markets, 10 books | `player_prop_odds` | 2023-24 → 2025-26, one snapshot 60 min before each tip | `data/ingestors/nba_odds_history.py --props` |
| First half / first quarter / team totals | `odds` (`source='odds_api_nba_derivative_history'`) | 2024-25 → 2025-26, one snapshot 60 min before each tip | `data/ingestors/nba_odds_history.py --derivatives` |
| Points by quarter (settles half / quarter bets) | `nba_period_scores` | 2018-19 → 2025-26 | `data/ingestors/nba_period_scores.py` (ESPN scoreboard) |

**Measured coverage, 2026-10-15** (read from the research cache, `scripts/nba_research_cache.py`):

- Game lines: 7,684 fetches, 1,625,824 rows kept; every regular-season game priced — 1,080 games in 2020-21, 1,230 in each season since.
- Props: 1,230 games in each of 2023-24, 2024-25 and 2025-26 (894,575 / 896,610 / 943,774 rows). Points, rebounds, assists, threes, PRA, the three pairs, blocks, steals and the double-double are on 3,680-3,690 of 3,690 games; triple-double 3,554, blocks+steals 3,353, turnovers 2,414.
- Half / quarter / team totals: 2,459-2,460 of 2,460 games in each market.
- Cost: ~900k credits in total (props 499,077; derivatives 172,427; game lines the rest), balance 2,584,357 at 2026-10-16 01:34Z, the floor at 2,200,000 never reached.

## 3. The market grid

Filled in §4 as each row is graded. An empty cell is a to-do.

| Market | Settles on | Inputs | Price source | Blind baseline | Best candidate | Verdict |
|---|---|---|---|---|---|---|
| Moneyline | `games` scores | | `odds` h2h | | | |
| Spread | `games` scores | | `odds` spreads | | | |
| Total | `games` scores (OT counts) | | `odds` totals | | | |
| Points | box `points` | | `player_prop_odds` | | | |
| Rebounds | box `rebounds` | | | | | |
| Assists | box `assists` | | | | | |
| Threes | box `fg3_made` | | | | | |
| Pts+Reb+Ast | sum | | | | | |
| Pts+Reb / Pts+Ast / Reb+Ast | sum | | | | | |
| Blocks / Steals / Blocks+Steals | box | | | | | |
| Turnovers | box `turnovers` | | | | | |
| Double-double / Triple-double | computed | | | | | |
| 1st half / 1st quarter / team totals | not bought yet | | | | | |

## 4. Results (graded 2026-10-15/16)

Every number below was produced by a researcher agent and then rebuilt from the
raw cache by three independent verifiers (timing, prices/grading, statistics).
Full reports, bet lists and code: `C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/`
and `verify/` on the build machine; the lab scripts are committed under `scripts/nba_*_lab.py`.

### 4.1 Game markets — closed for 2026-27

Seasons 2020-21 → 2025-26, 692 + 286 cells (`scripts/nba_game_market_lab.py`, `scripts/nba_game_model_lab.py`).

- **Schedule is in the line.** At Pinnacle's close, holding team strength fixed, a home team
  on the second night of a back-to-back is priced −1.71 points and actually did −2.04
  (residual −0.34, 90% CI −1.30..+0.63); a visitor on one: priced +1.77, did +1.82. Of 22
  schedule residuals (rest, 3-in-4, road-trip game N, travel miles, time zones, altitude,
  early tips …), 2 have an interval clear of zero against ~2.2 expected by chance. Adding the
  whole schedule group to Pinnacle's price changes log loss by −0.08 / −0.00 / +0.16
  thousandths (moneyline / spread / total), every interval covering zero.
- **The published schedule spots do not beat the modern line** (spread, 3pm ET, best price):
  home on a back-to-back vs a rested visitor +0.7% on 753; Denver/Utah hosting a tired
  visitor −0.5% on 138; long-travel back-to-backs +1.1% on 342.
- **Availability is priced.** The 3pm line moves 2.26 points per 48 player-minutes ruled
  out; results moved 2.21 (residual +0.05, CI −0.49..+0.59). Referee crews add nothing.
- **Sharp-vs-soft (the NHL totals rule) does not transfer:** NBA soft books move the number,
  not the price — 274 same-number total disagreements in five seasons, −11%.
- **The one moneyline cell that passed on paper** (away side, Pinnacle no-vig vs best price,
  EV ≥ 0.02: 1,550 bets, +7.1%) was refuted by all three verifiers: 57% of its units came
  from snapshots 4-11 minutes before tip; 26 winning bets were broken William Hill quotes
  (without them the CI crosses zero); it fails Benjamini-Hochberg over the cells searched.
- Blind baselines all lose (−1.1% to −6.7%). Early-season unders lose (−7.6%).

### 4.2 First half / first quarter / team totals — closed for 2026-27

2024-25 and 2025-26, 2,772 cells (`scripts/nba_derivative_lab.py`). Every family's
2024-25-chosen cell fails bar 6. Nearest: home team total, same number, EV ≥ 0.01 —
182 bets, +6.6%, CI −6.3..+19.1. The halftime total is not full/2 in practice (books move
each game ~3 points off it, correctly). Ties void two-way 1H/1Q moneylines at every book.

### 4.3 Player props — one rule ships

**Over-lean, measured:** blind overs lose 7.3% and blind unders 2.2% across 505,932
propositions at the best bettable price — the same lean as NFL, NHL and WNBA.

**Ships: same-line unders against Pinnacle** (`scripts/nba_prop_market_lab.py`).
Under at the best bettable book whose line equals Pinnacle's in the same snapshot, when
Pinnacle's proportional no-vig under makes that price +EV (EV ≥ 0.00), one bet per
(game, player, market):

| | bets | ROI | 90% CI |
|---|---|---|---|
| all three seasons | 25,204 | +2.85% (+771.4 u) | +1.75..+3.96 |
| 2023-24 / 2024-25 / 2025-26 | 8,766 / 8,595 / 7,843 | +4.1 / +2.2 / +2.1% | 2025-26 alone +0.34..+3.85 |
| without Hard Rock | 19,847 | +2.29% | +1.12..+3.46 |
| DraftKings as the only book | 8,209 | +2.12% | +0.32..+3.81 |
| without double-double / triple-double | 24,513 | +2.90% | (positive every season) |

Neighbouring floors +3.1% (0.01) and +2.1% (−0.01); both date halves positive (+3.5 / +2.2);
placebo (Pinnacle shuffled within date and market) mean −1.5%, 95th percentile −1.0%; blind
under on the same 141,087 propositions −1.5%. It survives Bonferroni and Benjamini-Hochberg
over all 1,518 cells searched (p ≈ 9e-6). Every one of the 25,204 bets was regraded from raw
quotes and box scores with zero errors. It was the hypothesis stated before the grid ran (the
cross-sport over-lean plus a sharp reference).

Caveats the verifiers carried, all disclosed rather than hidden:
- **Expect about +2% live, not +2.9%** — the top cell of a search carries winner's curse;
  2025-26 (never used to choose anything) is +2.1%.
- **Bar 11 (closing-line value) could not be measured** — one archived snapshot per game.
  The live card stores a closing snapshot for every bet from night one.
- **Stale soft quotes cannot be ruled out** — the archive stores no per-book update time.
  Where the bet book agrees with the other soft books within half a point, +3.9% on 1,997.
- **Hard Rock** carries ~37% of the units, decaying (+16 / +8 / +3% by season); the rule
  clears without it.

**Not shipped** (each refuted or not significant once graded on the season it was not chosen
on, or after counting the 1,518 cells searched): the soft-book-consensus rule where Pinnacle
is absent (+1.8%, fails with Hard Rock or FanDuel removed, DraftKings alone −1.05%); the
line-gap rule (+2.2%, 2025-26 alone −1.82..+4.21, profit from 64-minute snapshots only);
every single-market carve-out (rebounds, assists, PRA, points, threes, steals, reb+ast).
Every over rule fails. Double-double and triple-double fail.

### 4.4 Player props — projection models (the NHL recipe)

`models/nba_props.py`, `scripts/nba_prop_model_lab.py`. Minutes model, then per-minute
rates, negative binomial, every input as of the prop snapshot.

- Beats season average, last ten and the weighted mean in 13 of 14 markets before any price;
  triple-double fails and is closed.
- Does **not** beat the books' own price on Brier in points, rebounds, assists and the combos.
- **The teammate-absence hypothesis failed:** absences improve the count fit the most of any
  feature group, but add nothing at the price — books have priced absences an hour before tip.
- Best card: pooled unders, one a game — 3,620 bets, +4.86%, CI +1.8..+7.8, every season
  positive (+42.0 / +25.1 / +79.3 u), DraftKings alone +4.83%. Not claimed as a pass by its
  researcher (bar 11 unmeasurable; variants of the model pick 50-76% of the same bets and
  return +2.9% to +5.0%). Strongest where Pinnacle does not quote: blocks unders +5.78% on
  7,878 (DraftKings alone +5.54%, every season positive). See §4.5 for its verification.
