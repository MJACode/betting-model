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
| `ncaaf_over_under` | `total_regression` | Predict the game total from fundamentals (market number NOT a feature); bet the side of the disagreement only when \|pred − DK total\| ≥ 8.0 (symmetric gate, stored in the artifact); P(over) from the OOS-residual ECDF | LIVE — walk-forward 55.9% / +6.7% at the gate, best in all 4 test seasons; CI does not clear breakeven, sized small |
| `ncaaf_spread` | `cross_book_opener` | Back the side Bovada's OPENER favours, at DraftKings' stale OPENING number. Three preconditions in the scorer, each `return []`: (1) both openers captured within 90 min (`OPENER_MAX_SKEW_MIN`), (2) DK still ON its opener, (3) \|dev\| ≥ gate | LIVE — backtest 1,050 bets 58.1% +10.9%, CLV 0.694. Will NOT fire Week 1 (all games first polled 2026-08-22, before Bovada ingestion — ~4-day skew fails precondition 1 by design) |
| `ncaaf_spread_premium` | `cross_book_opener` | The SAME rule, band **[2.5, inf)** — the scorer's `d_threshold_max` on `ncaaf_spread` caps it at 2.5 so the two tiers are MUTUALLY EXCLUSIVE and a game fires exactly one | LIVE — 344 bets 60.5% +15.4%, positive all 3 seasons, CI [0.552,0.655] |
| `ncaaf_moneyline` | — | — | PAUSED — classifier held out at AUC ~0.50 |

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

### The model search is CLOSED (2026-08-27) — every lever tested, verdicts pinned

All harnesses live in `scripts/ncaaf_search/` and re-run against the DB. House
rules for any future NCAAF analysis: definitions fixed before results, variant
count reported, per-season records, Wilson CI vs 0.5238, and a TIME SPLIT that
must hold in both halves — that split is what killed every false positive.

| Lever | Harness | Verdict |
|---|---|---|
| 42-config classifier search (6 families × feature groups, ATS + totals) | `run_search.py` | NULL — CLV 0.41–0.48 everywhere, nothing clears the 5 gates |
| QB continuity (31.6K passer-games, `ncaaf_qb_game`) | `qb.py` + `qb_ablation.py` | NULL — helps 2/7 totals + 3/7 margin gates (coin flip), RMSE unchanged; the one positive spot cell is home/away confounding (mirror case shows nothing). "Starter out this week" is unknowable pre-kickoff (no CFB injury feed) — only continuity was testable, and it is priced |
| Weather spot rules (12 seasons, reanalysis) | `weather_totals.py` | NULL — unlike the NFL, the CFB market MOVES its total with wind (55.7 calm → 53.4 at 18+); wind≥12 = 54.0% pooled but late-half 51.2% and the ~2.5pp forecast haircut kills it; the 61% wind+rain cell is a time-split mirage (70% early / 34% late) |
| Line-movement follow/fade at the close (4,311 Bovada open+close pairs) | `line_move_spots.py` | NULL — follow = 50.0–52.4% at every threshold, no fade signal either; the close subsumes its own movement |
| Look-ahead / let-down schedule spots | `situational_spots.py` | NULL |
| Moneyline (margin regression -> P(win) vs real Bovada prices, 2,877 games) | `outcome_edge_scan.py` | NULL — calibration is superb (0.999 decile correlation) but EVERY edge cell loses at real prices (-2.8%..-8.9%): the book's implied probs are sharper than the model's and the 4.4% overround eats the rest. `ncaaf_moneyline` stays paused |
| Outcome x edge conditional surface (all 3 markets, 36 cells, 4-season walk-forward) | `outcome_edge_scan.py` | The one POSITIVE finding of the search — but it CONFIRMS the live totals rule rather than adding a new one: at the shipped ±8 gate, 9/9 cells are above breakeven (~55.6% over 464 bets, +6.4% at -110), the effect is DIRECTION-SYMMETRIC (over-side 56.1%, under-side 54.5%, both halves both sides), monotone turn-on lands exactly at 8 (the 6-8 band is 47-52%), and it holds in every line band and week band. Spread margin regression stays dead across 4 seasons (50.1-50.8% pooled; its 53.6% was a one-season artifact; the dog>fav asymmetry never reaches breakeven) |
| Margin regression (spread) | `ncaaf_margin_eval.py` | Passed its 2025 kill line (53.6% @ ±5.5) but ~50% across the 4-season walk-forward — 2025 was its one good year. Superseded by the opener rule |

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

- **Look-ahead**: `NCAAF_SCORE_AHEAD_DAYS` (7) puts the whole week in the
  scorer's game query and in the app (`fetchUpcomingNcaafPicks`).
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
- **`NCAAF_TOTALS_MAX_LEAD_DAYS` (1)** keeps the totals rule firing on game day.
  It was walked forward against the archive's stored line per game, not against
  an opener a week out; the look-ahead exposes leads it was never measured at.
  Earlier may well be better (the usual CLV story) — it is simply not measured.
  The opener rule has no such limit: its own preconditions are its window.
- **The FBS gate does most of the filtering.** Week 2 is 117 games, 39 both-FBS,
  ~52 DK-priced — so the board is tens of games, not hundreds.

### Data / conventions (load-bearing)

- **A night game has TWO `games` rows, and that is by design.** The odds
  ingestor dates a game by its EASTERN kickoff; `cfbd_ingestor.parse_games`
  dates it by CFBD's UTC `start_date`, so a ~8pm-ET-or-later kick exists under
  two ids (`NCAAF_2026-08-29_memphis_unlv` and `..._2026-08-30_...`). PICKS
  ALWAYS ATTACH TO THE ODDS ROW — it is the one that exists when the board is
  priced — and CFBD writes the final to its own. `mirror_scores_to_alias_rows`
  (called from both `ingest_ncaaf_results_for_date` and `ingest_ncaaf_games`)
  writes the orientation-corrected final onto every row that is the same game,
  matched on the slug pair within ±1 day. Deliberately NOT a re-key: `game_id`
  is the FK for `ncaaf_team_game_log` and `ncaaf_qb_game` across 2015-2025, so
  re-deriving the date would orphan a decade of training rows for no modelling
  benefit. An existing final is never overwritten, and a candidate matched by
  two conflicting finals is left unscored rather than guessed (`±1 day` is
  load-bearing — an annual rivalry repeats the slug pair every season).
- Canonical team id = CFBD SCHOOL NAME (accents folded via `_fold`); game_id
  slugs. Historical lines under `cfbd_*` bookmakers (provider priority
  `NCAAF_LINE_BOOKMAKER_PRIORITY`; 2023-25 DK, 2019-22 Bovada, 2015-18
  consensus). Openers are protected from the pruner (earliest snapshot per
  proposition per book — `test_prune_preserves_openers.py`).
- `ncaaf_qb_game` (added 2026-08-27): every passer per team-game 2015-2025,
  `is_primary` = most attempts (validated against the real 2023 QB carousels).
  Kept current by the weekly in-season step; feeds no model today but is the
  substrate if an injury feed ever lands. `--backfill-qb START END` refreshes.
- Weather: `game_weather` rows for ~99% of 2014-2025 games (3pm-local
  Open-Meteo REANALYSIS — truth, not forecast; any historical weather edge is
  an upper bound). `scripts/ncaaf_weather_backfill.py --seasons A B` fills
  gaps; `ingest_upcoming` writes forecasts for the coming week.
- Weekly ops in season: `step_ncaaf_stats` (schedule + box scores + QB log +
  snapshots, ~50 CFBD calls) and `step_ncaaf_results` pre-settle. Off-season
  the schedule pull returns nothing — that IS the gate.
- Totals-regression refits: re-run `python -m scripts.ncaaf_margin_eval
  --fit-totals` periodically in season so the artifact sees the current year;
  the fit refuses to register if the walk-forward no longer clears the kill
  line.
