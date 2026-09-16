# MLB 2026 game-line edge search (2026-09-16)

Mike: find a real MLB betting edge. Do not declare defeat. This file is the
search, not a pause. **It does not edit `PAUSED_MODELS`.** `mlb_runline`,
`mlb_over_under`, `mlb_f5_over_under`, and `mlb_f5_runline` stay paused.
`MLB_SPREAD_MARKET_PUBLISH` and `MLB_TOTAL_MARKET_PUBLISH` stay default 0.

The construction that clears the standards is already coded:
**`mlb_spread_market` at 1.8pp** — Pin de-vig vs bettable-soft de-vig, equal
±1.5, ≤300s, one bet per game. Paper-ready. Not live. Do not unpause
`mlb_runline`. Do not register a pickle.

Numbers below are from production (`vvprgnrmzeekokzkrkfu`) on 2026-09-16
unless labelled otherwise. Units, never dollars. A spread’s `scored_line` is
the HOME number.

---

## Recommendation (one screen)

| Rank | Construction | n | ROI | Period | Paper? |
|---|---|---|---|---|---|
| **1** | **`mlb_spread_market` 1.8pp** Pin de-vig − bettable-soft de-vig, equal ±1.5, 300s | **367** | **+4.80%** (+17.6u) | 2026 through the 2026-09-15 card measure; both halves + | **Yes — INSERT still 0** |
| 2 | Same rule at **2.0pp** (worker 2026-09-16) | 234 | +6.82% (+16.0u), CI90 [−4.3, +17.7] | 2026-03-20→09-16 | **No** — early half **−0.05% / 139** (flat). This is why 1.8pp is the cut. |
| 3 | Fade public over, tickets ≥70 (DK under, leak-bounded splits) | 67 | +13.30% (+8.9u); early +15.6%/46, late +8.3%/21 | Honest pregame public 2026-06/07 (85 games) | **No** — n<100, August wiped, June sample is under-biased vs league |
| 4 | F5 totals Pin de-vig vs FD/MGM/WH, 2pp | 28 | +12.41% | **2026-09-02→09-16 only** (Pin F5 totals do not exist before that) | **No** — one fortnight, thin. Neighbours + at 1.5/2.5. Worker remeasures. |

Live money stays off every row in this table until Mike sets
`MLB_SPREAD_MARKET_PUBLISH=1` (rank 1 only) or asks for a new card.

---

## Rank 1 — the paper strategy

**Definition.** For each settled 2026 MLB game, take the latest
`odds.snapshot_type='open'` quote per book with `snapshot_at <= games.commence_time`.
De-vig Pinnacle’s two-way run-line price. De-vig each `BEST_LINE_BOOKMAKERS`
book at the **same** `spread_home` (±1.5 only). Keep pairs ≤300 seconds apart.
One bet per game: the side and book with the largest `pin_fair − soft_fair`,
if that gap is ≥ **1.8pp**. Price is the soft American. Grade on the full-game
score. `scored_line` is the HOME number.

**Where it lives.** `models/mlb_game_market.py` `MIN_EDGE_SPREADS = 0.018`.
`scripts/mlb_game_market_card.py`. Pipeline `--step mlb-game-market`. INSERT
gated by `MLB_SPREAD_MARKET_PUBLISH` (default 0). `mlb_runline` stays paused.

**Measured 2026-09-15** (card docstring / `docs/mlb_runline_ou_edge_search.md`
MCP through August plus September on that pass):

| cut | n | ROI | early (to 06-30) | late (from 07-01) |
|---|---|---|---|---|
| 1.5pp | 622 | +2.22% | **−1.55% / 361 FAIL** | +7.44% / 261 |
| **1.8pp** | **367** | **+4.80%** | **+1.52% / 214** | **+9.38% / 153** |
| 2.0pp | 233 | +7.28% | **−0.05% / 139 FAIL** | +18.12% / 94 |

1.8pp is the only cell in that neighbourhood with both time halves positive,
n ≫ 25, and pooled neighbours also positive. Monthly at 1.8pp: Apr +0.45 /
May −2.15 / Jun +9.69 / Jul +9.10 / Aug +8.68 / Sep +11.19 (5 of 6 months +).
Both sides + (away +3.25%/175, home +7.19%/192). Every matching line is ±1.5.

**Worker confirmation of the 2pp neighbour**
(`mlb-game-line-market-sweep-open-bettable-2026-09-15`, done 2026-09-16,
`vs=devig`, `pin_lean=false`, `BEST_LINE` books, through 2026-09-16):

| cut | n | ROI | units | CI90 | early | late |
|---|---|---|---|---|---|---|
| 2.0pp | 234 | **+6.82%** | +15.96 | [−4.3, +17.7] | **−0.05% / 139** | +16.88% / 95 |
| 3.0pp | 34 | +3.35% | +1.14 | [−26.7, +33.6] | −5.42% / 19 | +14.46% / 15 |
| 4.0pp | 3 | −100% | −3.0 | thin | — | — |

Monthly at 2pp: Apr −1.76 / May −6.70 / Jun +9.42 / Jul +12.60 / Aug +16.33 /
Sep +22.34. Totals 2pp on the same job: **−4.27% / 229** (dead; early +1.16%/135,
late −12.07%/94).

The worker did **not** remeasure 1.8pp (edges were 2/3/4). Declared
`mlb-game-line-market-sweep-spreads-plateau-2026-09-16` fills 1.5/1.8/2.0/2.5.
Until that returns, the card cut stays 1.8pp on the 2026-09-15 neighbourhood.

**Why this beats the dead ends.** `mlb_runline` XGBoost + #740/#742 handicap
features: holdout AUC ~0.61, volume cells flat-negative. This rule does not
train on `pub_*`, does not use leak-era team stats, and does not peek at the
close.

**Paper-ready means:** log the card; do **not** set `MLB_SPREAD_MARKET_PUBLISH=1`
without Mike. GROK Pin-vs-DK implied ≥2pp spreads (~−5% n≈200) is a different
population and is **not** this card.

---

## Search log (what was tried)

### 1. 2026-only public RLM / steam — leak-bounded

`public_betting`: **8,214 rows / 1,369 games**, 2026-05-31→2026-09-16.
UNIQUE last-upsert-wins. Honest pregame (`snapshot_at::timestamptz <= commence_time`
**and** `_is_pregame_snapshot`): **85 settled games** with DK prices
(Jun 59 / Jul 25 / Aug **0** / Sep 1). Train 2019–2025 is empty — cannot
learn `pub_*` there.

Graded 2026-09-16 on those 85 games, DK latest OPEN ≤ commence, American
profit, units:

| Strategy | n | ROI | early | late | Verdict |
|---|---|---|---|---|---|
| Control: always under | 83 | +7.51% | +13.2%/57 | **−4.91%/26** | Sample bias, not an edge |
| Control: always over | 83 | −18.24% | −24.1%/57 | −5.3%/26 | Dead |
| Fade public over tix≥65 | 71 | +12.29% | +14.6%/48 | +7.5%/23 | Neighbour of 70; still the biased sample |
| **Fade public over tix≥70** | **67** | **+13.30%** | **+15.6%/46** | **+8.3%/21** | Best public cell; n<100; Aug missing |
| Fade public over tix≥75 | 63 | +8.45% | +14.0%/45 | **−5.4%/18 FAIL** | Late dies |
| Fade public over tix≥80 | 51 | +15.37% | +26.6%/36 | **−11.7%/15 FAIL** | Peak |
| Totals follow RLM ≥10pp | 17 | +1.52% | +8.0%/9 | −5.8%/8 | Thin, late − |
| Totals follow RLM ≥15/20pp | 5 / 2 | — | — | — | n<25 |
| Fade public fav RL tix≥70 money≤45 | **0** | — | — | — | Does not fire |
| Fade public fav RL tix≥65 money≤50 | 3 | +3.50% | n=3 | — | Thin |
| Spreads follow RLM ≥10pp | 25 | +0.98% | +22.8%/18 | **−55%/7** | Late dies |
| Spreads follow RLM ≥15/20pp | 12 / 10 | −19% / −28% | + then − | −100% | Dead |
| H2H follow RLM ≥10pp | 34 | −21.96% | −33.6%/28 | +32%/6 | Dead |
| Fade public ML fav tix≥70 | 48 | −25.52% | −26%/29 | −24%/19 | Dead both halves |

**League control (DK always-under, W-L, pushes excluded):**

| Month | n (incl. push) | Under-Over | Under WR |
|---|---|---|---|
| 2026-04 | 329 | 145–167 | 46.5% |
| 2026-05 | 417 | 208–192 | 52.0% |
| 2026-06 | 378 | 178–182 | 49.4% |
| 2026-07 | 338 | 180–150 | 54.5% |
| 2026-08 | 397 | 190–184 | 50.8% |

Apr–Jun graded under is **531–541 / 1,072**. The 85-game public sample’s
always-under **+7.51%** is June-heavy selection: league June was 49.4% under,
the 57 June public games were not. July fade-over-70 (+13.8%/20) sits in a
month the league also went under (54.5%) — possible signal, n=20.

Steam (prior pass, DK totals first vs last OPEN, Apr–Jun): follow |move|≥0.5
**−5.92% / 538**; fade **−2.84%**. Worker job `mlb-public-rlm-sweep-2026-09-16`
re-runs the public grid plus steam on the full 2026 board.

### 2. Pin lean vs soft implied (open, ≤5 min)

Worker `mlb-game-line-market-sweep-open-dk-implied-2026-09-15`
(`vs=implied`, `pin_lean=true`, DK only, 2/3/4pp): **0 bets** at ≥2pp on
spreads and on totals. Equal-line + simultaneous + Pin-lean vs juiced implied
almost never reaches 2pp (vig inflates both implieds). GROK’s ~+11% n≈103
totals figure is **unreproducible** under those traps.

Pin-de-vig vs bettable-soft-de-vig totals 2pp: worker **−4.27% / 229**.
Known dead end, confirmed on a longer window than the May–Jun −11.13%/79.

### 3. Hybrid public RLM × Pin lean

On the 85-game sample the hybrid (fade over tix≥70 **and** Pin no-vig prefers
under) is coded in `scripts/mlb_public_rlm_sweep.py` as
`hybrid_fade_over_70_pin_lean_under`. It cannot outrun the sample-bias problem:
the parent cell is already 67 of 83 totals. Not paper.

Classic fade-fav-RL × Pin dog: parent n=0–3.

### 4. F5 markets

Pinnacle `totals_1st_5_innings` / `spreads_1st_5_innings`: **175 games,
2026-09-02→2026-09-16 only.** No 2019–2025 Pin F5. DK does not carry F5
totals/spreads in this window; soft books are FanDuel / BetMGM / William Hill.

Equal-line, ≤300s, Pin de-vig vs those three, grade `home_score_f5` /
`away_score_f5` (never the full-game score):

| cut | n | ROI | pin-lean only |
|---|---|---|---|
| 1.5pp | 54 | +1.41% | +13.09% / 27 |
| 2.0pp | 28 | +12.41% | +24.97% / 17 |
| 2.5pp | 13 | +6.69% | +38.99% / 7 |

All one fortnight. No early/late split that is not a week vs a week. Leak-era
`mlb_f5_*` XGBoost stay paused. Market-relative F5 is **paper-only and thin**.
`scripts/game_line_market_sweep.py` now accepts F5 market keys and grades F5
scores. Declared `mlb-game-line-market-sweep-f5-totals-2026-09-16`.

F5 moneyline always-home/away/dog/fav on DK (prior pass, May–Sep, n=1,322):
all negative.

### 5. MLB h2h Pin vs soft de-vig

Prior MCP Apr–Jun: 1.5pp +3.73%/107 (home −2.22%/69, away +14.53%/38);
1.2pp −1.62%/207; 1.0pp −7.08%/347. **1.5 is a peak** (1.2 early negative).
Declared `mlb-game-line-market-sweep-h2h-2026-09-16` remeasures 1.2/1.5/1.8/2.0
on bettable books. Not paper until the plateau holds.

### Predictive models (settled 2026 pregame BET, not VOID)

Prior pass: `mlb_moneyline` −2.38%/101; `mlb_over_under` −17.64%/162;
`mlb_runline` −1.98%/44; `mlb_f5_moneyline` −1.53%/208. Not this search’s
publish path.

---

## What shipped

| piece | where |
|---|---|
| F5 grading on the game-line sweep | `scripts/game_line_market_sweep.py` — `F5_MARKETS`, scores from `home_score_f5` / `away_score_f5` |
| Worker markets | `tracking/job_queue.py` `_allowed_game_line_markets` includes the three F5 keys |
| Public RLM grader | `scripts/mlb_public_rlm_sweep.py` — `_is_pregame_snapshot`, DK price, control always-under, hybrid Pin-lean |
| Worker job | `mlb_public_rlm_sweep` |
| One-shots | `jobs/declared_jobs.json` — spreads 1.5/1.8/2.0/2.5, h2h, F5 totals, public RLM+steam |

**Not done:** `PAUSED_MODELS` unchanged. `MLB_*_MARKET_PUBLISH` unchanged.
No pickle registered. No live Discord/app publisher for a new model id.

---

## What this is not

This is not an unpause of `mlb_runline`. It is not GROK’s Pin-vs-DK implied
totals +11%. It is not “fade the public” as a live model — the honest public
sample is 85 games and August is gone. Rank 1 is the market-relative run-line
rule that already has both-halves-positive evidence at n=367.
