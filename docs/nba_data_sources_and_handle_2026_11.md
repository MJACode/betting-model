# NBA data sources, and handle / money data across markets (2026-11-26)

mike, 2026-11-26: *"Research other nba data sources - props and game makers as these models have
been weak. Research broadly across all markets reliable data source for handle / money data on
betting - confirm this data would be helpful."*

Two parts. Part A is measured here, on production data (read-only queries, 2026-11-26). Part B is
web research (vendor pages, papers), and every claim in it names its URL. Units are 1 unit to win,
risk capped at 3, at the price stored with the row.

## A. Measured

### A1. The live NBA record this season

`picks`, `sport='NBA'`, `signal_type='BET'`, game dates 2026-10-20 to 2026-11-25, settled, leaving
out `VOID` / `DUPLICATE` and rows marked `downgrade_reason = 'model paused'` (a paused model keeps
writing its BET rows with that marker; every record query leaves them out). This is the `picks`
table, not the Discord-published view (`v_discord_published`).

| Model | Bets | W-L | Units | Return |
|---|---|---|---|---|
| `nba_prop_projection` | 128 | 47-81 | -15.98 | -15.7% |
| `nba_team_total_luck` | 39 | 20-19 | -1.13 | -2.6% |
| `nba_total_luck` | 37 | 18-19 | -2.71 | -6.7% |
| `nba_first_half_total_luck` | 21 | 13-8 | +4.01 | +17.2% |
| `nba_prop_market` | 18 | 6-12 | -5.69 | -33.1% |
| `nba_live_spread_q12` | 15 | 8-7 | +0.17 | +1.0% |
| `nba_prop_first_basket` | 10 | 2-8 | +1.01 | n/a (plus-money) |
| `nba_q1_trend` | 1 | 1-0 | +1.00 | n/a |
| **All** | **269** | **115-154** | **-19.32** | **-7.9%** |

The two prop models are -21.67 of the -19.32 units. Both have been in `config.PAUSED_MODELS`
since the low-volume plan merged (2026-11-22 18:06 UTC); their 21 BET rows since then carry the
pause marker and are not in the table above.

### A2. What splits data is stored

| Table | Source | Window | Timestamped before the start? |
|---|---|---|---|
| `nba_public_splits` (`archive_undated`) | Action Network consensus (book 15) | 2020-12-22 to 2026-11-25, about 7,200 regular-season games | No: the split at the close, known only after tip (`docs/nba_public_splits.md`) |
| `nba_public_splits` (`pregame_poll`) | Action Network consensus | 2026-10-20 to 2026-11-25, 270 games, 45,248 rows | Yes (`observed_at`) |
| `public_betting` | Action Network consensus, MLB | 2026-05-31 to 2026-10-28, 1,541 games | Mostly overwritten after the start; about 136 games pre-commence (`docs/mlb_market_handicap_features.md`) |
| `scoreboard_splits_history` | Action Network consensus: NBA 78 games, NHL 84, NCAAF 88, NFL 19, NCAAB 6 | 2026-11-16 on | Yes (`snapshot_at`) |
| `scoreboard_splits_history` | DraftKings Network (DraftKings' own Handle % and Bets %): NFL 30 games | 2026-11-16 on | Yes |

### A3. Does the NBA closing split predict results at the closing line?

`nba_public_splits`, `archive_undated`, `quality IS NULL`, v2 where it exists else v1, seasons
2020-21 to 2025-26, graded at the consensus line and price stored with the split. Every cell
graded is shown. Break-even at -110 is 52.38%.

**Spreads** (home cover = margin + home number > 0):

| Rule | Bets | Win % | Units | Return |
|---|---|---|---|---|
| Fade the side with tickets >= 60% | 3,960 | 48.99 | -281.0 | -6.56% |
| >= 65% | 2,661 | 49.56 | -156.9 | -5.45% |
| >= 70% | 1,641 | 48.98 | -116.6 | -6.58% |
| >= 75% | 896 | 49.03 | -62.3 | -6.47% |
| >= 80% | 391 | 49.74 | -21.3 | -5.09% |
| Follow money when money % - tickets % >= 10 | 3,241 | 49.75 | -178.3 | -5.08% |
| >= 15 | 2,310 | 50.09 | -110.2 | -4.40% |
| >= 20 | 1,629 | 50.16 | -75.1 | -4.25% |
| >= 30 | 743 | 50.75 | -25.2 | -3.11% |

**Totals:**

| Rule | Bets | Win % | Units | Return |
|---|---|---|---|---|
| Fade over tickets >= 60% (nearly all unders) | 5,127 | 49.90 | -269.6 | -4.83% |
| >= 65% | 4,199 | 49.34 | -271.4 | -5.92% |
| >= 70% | 3,372 | 49.19 | -229.8 | -6.23% |
| >= 75% | 2,642 | 48.95 | -194.2 | -6.73% |
| >= 80% | 2,010 | 48.60 | -163.6 | -7.45% |
| Follow money, gap >= 10 | 3,244 | 51.90 | -31.2 | -0.88% |
| >= 15 | 2,651 | 51.83 | -29.4 | -1.02% |
| >= 20 | 2,126 | 51.83 | -24.1 | -1.04% |
| >= 30 | 1,286 | 51.88 | -13.2 | -0.94% |
| Every under (baseline; this row also holds 2026-27 to date) | 7,114 | 49.66 | | -5.27% |

The gap >= 15 totals cell by season: 51.47% (552 bets), 51.99% (763), 49.93% (735), 54.53% (593),
then **7 bets in 2024-25 and 1 in 2025-26**, because the gap itself disappeared (A4).

**Moneyline:** fade tickets >= 65 / 75 / 85: -4.23% / -5.00% / -3.47% (4,905 / 3,655 / 2,252
bets). Follow money gap >= 15 / 30 / 45: -5.34% / -2.11% / -2.21%.

**Read:** no cell of 24 clears break-even on six seasons. The only cell above a coin flip is the
totals money gap (about 51.9%), below break-even at the consensus price, chosen as the best of
nine, and it cannot be bet any more because the source stopped producing the gap.

### A4. Action Network's money % stopped being a separate measurement after 2023-24

Absolute gap between money % and tickets %, home / over side, closing archive:

| Season | Moneyline median (p90) | Spread median (p90) | Total median (p90) |
|---|---|---|---|
| 2020-21 | 21 (53) | 13 (33) | 18 (44) |
| 2021-22 | 18 (52.6) | 14 (33) | 22 (49) |
| 2022-23 | 19 (49) | 16 (36) | 19 (44) |
| 2023-24 | 19 (58) | 14 (35) | 16 (41) |
| 2024-25 | 8 (26) | 3 (9) | 2 (6) |
| 2025-26 | 6 (22) | 3 (10) | 1 (4) |
| 2026-27 pre-tip polls | 5 (21) | 4 (14) | 3 (9) |

Both endpoints (v1 and v2) show the same break, so it is the source, not our parser. Over the same
November 2026 NFL games, DraftKings Network's Handle % vs Bets % has a median gap of 12 (moneyline),
11 (spread) and 16 (total), against Action Network's 8 / 3 / 1 (`scoreboard_splits_history`,
counted over stored snapshot rows, not games). So since 2024-25 the free Action Network "money %"
is close to a copy of its ticket %, and the "sharp money vs public tickets" reading cannot be made
from it. Why it changed: Part B, B3.

### A5. Does an early split predict where the line goes?

2026-27 NBA pre-tip polls: the last poll at least 4 hours before the listed start (mean 4.5 h)
against the last poll in the final 20 minutes, 251 games.

| Market | corr(tickets lean, move) | corr(money lean, move) | corr(money - tickets, move) | Games where the line moved | Mean move |
|---|---|---|---|---|---|
| Spread (home number) | -0.022 | -0.088 | -0.124 | 95 | 0.51 pt |
| Total | +0.051 | -0.004 | -0.116 | 136 | 0.63 pt |

One standard error is about 0.063. The gap correlation is about two standard errors in both markets
but points the right way on spreads (money on the home side, home number falls) and the wrong way
on totals. Inconclusive. Most games do not move at all in the last 4.5 hours.

### A6. The one splits model that went live

`mlb_total_public_fade` (fade 70%+ over tickets): 33 settled bets, 14-18-1, -5.28 units
(`picks`, read 2026-11-26).

