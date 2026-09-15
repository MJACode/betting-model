# MLB runline / over-under: the edge search (2026-09-15)

Mike rejected “keep `mlb_runline` and `mlb_over_under` paused until someday.”
Standing rule (CLAUDE.md §1b): a losing model is an **assessment to run**, not
a model to pause. This file is the assessment. It names a shippable cut where
one exists, and names what failed where one does not.

**Pause/unpause is Mike’s.** This search does **not** edit `PAUSED_MODELS`.
The ask in the PR is: **approve going live of `mlb_spread_market` (not an
unpause of `mlb_runline`).**

---

## Recommendation (one screen)

| Market | Verdict |
|---|---|
| Run line | **Replace the publish path.** New rule `mlb_spread_market` at **1.8pp** (Pinnacle de-vig vs bettable soft books, equal ±1.5 only, pre-game, simultaneous quotes, one bet per game). `mlb_runline` stays paused. |
| Totals | **No cut.** Same construction is negative at every measured threshold. `mlb_over_under` stays paused. Predictive AUC 0.486 in the only honest season (`docs/sports/mlb.md` §11a). Unpause path is a rebuilt model, not a bar. |
| Hybrid steam/public overlay | **Shadow on the new rule** (do not veto a cut that has not been re-measured under it). **Live** on the four predictive MLB game models (`mlb_moneyline`, `mlb_runline`, `mlb_over_under`, `mlb_f5_moneyline`) per mike 2026-09-15 on the gate PR — those models are paused or thin on the live artifact, so the live default writes NONE on steamed/public-steam rather than betting them. |

Approve: **going live of `mlb_spread_market`.** Updated-By required. Do not
silently unpause `mlb_runline` / `mlb_over_under`.

---

## What was measured (2026-09-15, Supabase `execute_sql`, project Betting Model)

How each number was produced is named. An hour-old value is a memory; these
are from this pass unless labelled otherwise.

### Predictive models, settled BET record (not live, not VOID)

`picks` where `signal_type='BET'` and `result IN ('WIN','LOSS')` and
`COALESCE(condition_status,'') <> 'VOID'` and `COALESCE(is_live,false) IS NOT TRUE`.
Units = `SUM(profit_flat)/100`.

| model | n | W-L | units | avg `clv_pct` (n with CLV) |
|---|---|---|---|---|
| `mlb_over_under` | 162 | 70-92 | **−28.58** | −0.127 (108) |
| `mlb_runline` | 44 | 23-21 | **−0.87** | +0.029 (40) |

2026 settled MLB games (`home_score`/`away_score` not null, `game_date` in
`[2026-03-01, 2026-09-16)`): **2044**. Of those, **1991** have at least one
pre-game Pinnacle spread quote.

The 2026-09-12 paused-model assessment (`docs/paused_model_assessment.md`)
already said: no §7 cut on the **live artifact** for either model. Runline is
dormant (cannot reach its 0.68 floor). O/U honest-era walk-forward AUC **0.486**.
This pass did not retrain — no `DATABASE_URL` in the cloud agent; the marker
`data/TEAM_STATS_ASOF_REBUILD_COMPLETE` is present, so a Railway retrain is
allowed. Commands at the bottom.

### A. Market-relative (the construction that printed)

Same rule as `models/nfl_prop_market`, pointed at game lines:

- de-vig Pinnacle (proportional)
- bet a **bettable** soft book (`config.BEST_LINE_BOOKMAKERS`, i.e. LINE_SHOP
  minus `pinnacle` / `bovada` / `espnbet`)
- **equal lines only**
- **pre-game only** (`snapshot_at <= commence_time`, `in_play` excluded)
- **simultaneous** (quote clocks ≤ 300s apart)
- **one bet per game** (largest edge)
- run line only (`|spread_home| = 1.5`)
- house juice floor **−200** (the default that ships)

**Including Bovada / espnbet as “soft” manufactured a 1pp plateau that
disappeared on the bettable set.** That is why SOFT_BOOKS is BEST_LINE, not
LINE_SHOP.

Query shape: latest pre-game quote per `(game_id, bookmaker)` joined through
`games` with `snapshot_at` bounded to the month (unbounded `odds` scans time
out). One bet per game = `DISTINCT ON (game_id) ORDER BY edge DESC`. Grade:
away cover `(away − home) − scored_line > 0` (CLAUDE.md §4; `scored_line` is
the HOME number).

#### Spreads — monthly cells (price ≥ −200)

| window | 1.0pp n / ROI | 1.5pp n / ROI | **1.8pp n / ROI** | 2.0pp n / ROI |
|---|---|---|---|---|
| 2026-03-20 → 04-30 | 213 / −3.74% | 127 / −6.58% | **77 / −0.19%** | 49 / +1.01% |
| 2026-05-01 → 06-30 | 480 / +0.21% | 226 / +1.67% | **133 / +2.53%** | 88 / +0.38% |
| 2026-07-01 → 07-31 | 180 / −10.82% | 80 / +2.13% | **46 / +9.10%** | 27 / +16.77% |
| 2026-08-01 → 08-31 | 210 / +11.42% | 116 / +15.28% | **72 / +8.68%** | 41 / +16.33% |
| 2026-09-01 → 09-15 | MCP timeout this pass | | | |

Pooled **without September** (the window that timed out):

| cut | n | ROI | early (through 06-30) | late (Jul–Aug) |
|---|---|---|---|---|
| 1.5pp | 549 | +2.70% | **−1.30% / 353 FAIL** | +10.36% / 196 |
| **1.8pp** | **328** | **+4.16%** | **+1.53% / 210** | **+8.84% / 118** |
| 2.0pp | 205 | +5.88% | +0.61% / 137 | +16.51% / 68 |

**1.8pp is the cell that clears the standards on this remeasure:** n ≫ 25,
both time halves positive, neighbours (1.5pp pooled and 2.0pp pooled) also
positive. 1.5pp fails the early half. 2.0pp’s early half is +0.61% on 137 —
thin, and the unfloored reconstruction the same day had it at −0.05% / 139.
Do not chase 2.0pp.

July +9.10% / 46 and August +8.68% / 72 on this query **match the same-day
full-season reconstruction of those two months exactly**, so the construction
is stable. September’s 15-day window timed out on this pass; it is not filled
in from memory.

#### Totals — no cut

May–Jun 2026, same construction (Pinnacle vs the eight us-region bettable
books that returned in time, equal total, 300s, one per game):

| cut | n | ROI |
|---|---|---|
| 1.0pp | 420 | **−1.43%** |
| 1.5pp | 187 | **−3.49%** |
| 2.0pp | 79 | **−11.13%** |

Negative, and more negative as the cut tightens. `find_total_bets` exists
with `MIN_EDGE_TOTALS = 1.0` (a wall). The card does **not** publish totals.

`public_betting` is present (Action Network, from 2026-05-31) but a
public-fade join on totals timed out; it is not a shipped totals cut.

### B. Predictive repair — not run here

No `DATABASE_URL` in this environment. The freeze marker
`data/TEAM_STATS_ASOF_REBUILD_COMPLETE` **is** in tree, so the trainer will
not refuse.

Railway / Matt’s machine (leak-repaired stats only; 2026 is the only season
with real DK run-line prices):

```bash
python -m models.trainer --model mlb_runline \
    --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026
python -m scripts.mlb_runline_sweep --seasons 2026
# PROB REACH first. If max_p < 0.68 the current floor is still dormant.

python -m models.trainer --model mlb_over_under \
    --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026
python -m scripts.calibrated_threshold_sweep --model mlb_over_under
```

Feature ideas **if** that grid is still flat, leak-safe at pick time only:
park / weather (already in the feature map), bullpen workload (already),
starter FIP/xERA diffs, `public_betting` ticket/handle. **Do not use the
close as a feature.** Opener-vs-current belongs in `game_market_gate`, which
is already wired.

### C. Hybrid

`mlb_spread_market` persists `game_market_gate` in **shadow** (`mode=shadow`).
PASS_STEAMED / PASS_PUBLIC_STEAM do **not** change `signal_type` on this rule
until the overlay is re-measured on its own record. The four predictive MLB
game models apply the gate **live** (mike, 2026-09-15): steamed / public-steam
BETs become NONE. Extra no-vig floor (`PASS_EDGE`) stays off.

---

## What shipped

| piece | where |
|---|---|
| Rule | `models/mlb_game_market.py` (`MIN_EDGE_SPREADS = 0.018`) |
| Card | `scripts/mlb_game_market_card.py` — insert-once, `model_id=mlb_spread_market` |
| Pipeline | `run_pipeline.py --step mlb-game-market`; daily after scoring; `scripts/refresh_pass.sh` |
| Gate (PR #732, incorporated) | `models/game_market_gate.py` live on the four predictive MLB game models; shadow on this card |
| Cut | `config.ACTION_THRESHOLDS["mlb_spread_market"] = {min_prob: 0.0, min_edge: 0.018}` |
| Scoring method | `rule` (no artifact) |
| Settlement | `tracking/paper_tracker._RULE_MODEL_MARKETS["mlb_spread_market"] = "spreads"` |
| App label | `mobile/src/lib/modelMeta.ts` shortLabel `RL Mkt` |

`mlb_runline` and `mlb_over_under` remain in `PAUSED_MODELS`. Nothing
autopauses. No settled pick is touched.

---

## What this is not

This is **not** “Grok picked CLE −1.5.” It is the class of edge that number
belongs to: **money divergence** (Pinnacle’s de-vigged price vs a bettable
soft book at the **same** run line), with a steamed-through pass sitting next
to it in shadow so the next assessment can split the record.
