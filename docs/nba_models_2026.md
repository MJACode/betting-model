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

## 4. Results

(written as each family is graded)
