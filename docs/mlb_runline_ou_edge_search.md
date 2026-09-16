# MLB runline / over-under: the edge search (2026-09-15)

Mike rejected “keep `mlb_runline` and `mlb_over_under` paused until someday.”
Standing rule (CLAUDE.md §1b): a losing model is an **assessment to run**, not
a model to pause. This file is the assessment. It names a shippable cut where
one exists, and names what failed where one does not. **It does not conclude
“stay paused forever.”**

**Pause/unpause is Mike’s.** This search does **not** edit `PAUSED_MODELS`.
`mlb_runline` and `mlb_over_under` stay paused. Do **not** resurrect the
2026-09-02 O/U RE-CUT 0.50/0.06 (+15.7%) — it did not survive later sweeps
(`model_calibration_sweeps` 2026-09-14: `mlb_over_under` NO CUT, cur −11.6%
n=107; `mlb_runline` NO CUT, cur −15.5% n=9).

This PR wires a **paper, INSERT-gated** totals *logger* of the construction
this pass measured: Pin de-vig vs bettable-soft de-vig at 2pp
(**−11.13% / 79** May–Jun). Defaults stay 0. Do **not** set
`MLB_TOTAL_MARKET_PUBLISH=1`. Do **not** set `MLB_SPREAD_MARKET_PUBLISH=1`.
This is not an unpause of `mlb_over_under` and not live money.

GROK Pin-lean vs DK implied (~+11% n≈103) is a **different** construction.
It is not this card. Confirming it is **not** permission to flip
`MLB_TOTAL_MARKET_PUBLISH` — that env would INSERT the −11% population.

---

## Recommendation (one screen)

| Market | Verdict |
|---|---|
| Totals | **Paper `mlb_total_market` at 2pp: Pin fair − soft implied, equal `total_line`, best soft book from `BEST_LINE_BOOKMAKERS`, pin-lean only (never fade Pinnacle).** GROK vs DK only: Apr–Jul ~+11% n≈103. Pin-de-vig vs bettable-soft-de-vig May–Jun 2pp **−11.13% / 79** is a sweep flag (`vs=devig`), not the card. INSERT off (`MLB_TOTAL_MARKET_PUBLISH` default 0). `mlb_over_under` stays paused. |
| Run line | **Do not live-publish pure Pin-vs-soft spreads.** GROK Pin-open vs DK-open ≥2pp: ~**−5% n≈200**. Earlier same-day bettable-soft de-vig at **1.8pp** was +4.16% / 328 through Aug (both halves +) — a different construction, and GROK’s ≥2pp result is the one that says “more work.” Code for `mlb_spread_market` at 1.8pp remains; INSERT is gated off. `mlb_runline` stays paused. |
| Hybrid | GROK on existing `mlb_over_under` BETs: disagree with Pin lean **−17.7u / 71**; agree any **−5.1u / 53**; agree ≥1.5pp **−0.5u / 8**. Stops the hemorrhage, is **not +EV**. Steam/public overlay stays **shadow** on the market cards. Live gate stays on the four predictive MLB game models. |
| Retrain | **Not run here** (no `DATABASE_URL`). Next only if the worker totals 2pp cell is still negative. Commands at the bottom. |

Do **not** flip `MLB_TOTAL_MARKET_PUBLISH` or `MLB_SPREAD_MARKET_PUBLISH`
until the worker grid confirms. Do not silently unpause `mlb_runline` /
`mlb_over_under`.

A **separate** paper lane, `mlb_total_public_fade`, fades public OVER
tickets. It is not this card and not an unpause.
`docs/mlb_total_public_fade.md`. `MLB_TOTAL_PUBLIC_FADE_PUBLISH` default 0.

---

## Production facts (Error Handler, 2026-09-15 — do not re-litigate calibration cuts)

`model_calibration_sweeps` latest 2026-09-14:

| model | verdict | current ROI |
|---|---|---|
| `mlb_over_under` | NO CUT | −11.6% n=107, paused=true |
| `mlb_runline` | NO CUT | −15.5% n=9, paused=true |

All-era pregame BET: O/U 70-92 **−16.6%**; runline 23-21 **−2.0%**.

Honest era ≥2026-07-05 O/U: ~39 BETs, −16u, avg edge negative, avg CLV
negative — the model is the wrong side of the market.

This pass’s own `picks` query (settled BET, not VOID, not live):

| model | n | W-L | units | avg `clv_pct` |
|---|---|---|---|---|
| `mlb_over_under` | 162 | 70-92 | **−28.58** | −0.127 (108) |
| `mlb_runline` | 44 | 23-21 | **−0.87** | +0.029 (40) |

---

## Odds schema (load-bearing)

`odds.snapshot_type` is `open` | `in_play` | `close`. `odds.snapshot_at` is
the quote clock. **`odds` has no `commence_time`** — that column lives on
`games`. The sweep and the live card filter `snapshot_type = 'open'` and
still leak-bound `snapshot_at <= games.commence_time` because the evening
refresh has written post-start rows as `open` (session 106).

`scripts/game_line_market_sweep.py` month-chunks on `game_date` so the odds
scan stays inside an index-friendly window. Unbounded joins time out on
MCP `execute_sql`.

---

## What was measured

### A. Market-relative — two constructions, they disagree

Same traps as `models/nfl_prop_market`: equal lines only, simultaneous
(≤300s), one bet per game, house juice −200.

#### Construction 1 — Pin de-vig vs **bettable** soft de-vig (this pass, MCP)

Soft books = `BEST_LINE_BOOKMAKERS` (not Bovada / espnbet / Pinnacle as a
price to take). Including those manufactured a fake 1pp plateau.

**Spreads** (run line ±1.5), latest pre-game ≠ in_play, 300s, price ≥ −200,
2026 through August (September timed out on this pass):

| cut | n | ROI | early (through 06-30) | late (Jul–Aug) |
|---|---|---|---|---|
| 1.5pp | 549 | +2.70% | **−1.30% / 353 FAIL** | +10.36% / 196 |
| **1.8pp** | **328** | **+4.16%** | **+1.53% / 210** | **+8.84% / 118** |
| 2.0pp | 205 | +5.88% | +0.61% / 137 | +16.51% / 68 |

1.8pp is the only cell in **this** construction with both halves clearly +.
GROK’s later Pin-vs-DK ≥2pp result (below) is why this is **not** live.

**Totals**, May–Jun 2026, same construction:

| cut | n | ROI |
|---|---|---|
| 1.0pp | 420 | **−1.43%** |
| 1.5pp | 187 | **−3.49%** |
| 2.0pp | 79 | **−11.13%** |

Negative, and more negative as the cut tightens. This is **not** GROK’s
totals number.

#### Construction 2 — Pin OPEN no-vig lean vs DK OPEN implied (GROK_BOT 2026-09-15)

Month-chunked on production. This agent did **not** re-query these cells;
they are GROK’s measurements, labelled as such.

**TOTALS** ≥2pp, equal `total_line`:

| month | ROI | n | units |
|---|---|---|---|
| Apr | +34.3% | 16 | +5.48u |
| May | −8.8% | 26 | −2.28u |
| Jun | +16.4% | 27 | +4.43u |
| Jul | +11.1% | 34 | +3.76u |
| Aug/Sep | still running | | |

Apr–Jul combined ~+11.4u / ~103 ≈ **~+11% ROI**. Leading O/U replacement.

**SPREADS** ≥2pp, equal line:

| month | ROI | n |
|---|---|---|
| Apr | −15.9% | 23 |
| May | −13.0% | 35 |
| Jun | +3.4% | 27 |
| Jul | −10.1% | 62 |
| Aug | +5.7% | 57 |

Overall ~**−5% on ~200**. Do **not** ship pure Pin-vs-soft spreads as the
runline fix without more work (timing alignment, best soft book, close vs
open, higher threshold, optional model-agree after retrain).

### B. Hybrid on existing `mlb_over_under` BETs (GROK_BOT)

| filter | units / n |
|---|---|
| disagree with Pin lean | **−17.7u / 71** |
| agree any | **−5.1u / 53** |
| agree ≥1.5pp | **−0.5u / 8** |

A disagreement filter stops the bleed. It does not create +EV. Not a
publish path.

### C. Predictive repair — not run here

No `DATABASE_URL` in this environment. The freeze marker
`data/TEAM_STATS_ASOF_REBUILD_COMPLETE` **is** in tree, so the trainer will
not refuse. Run **after** the worker sweep if totals 2pp is still negative.

```bash
python -m models.trainer --model mlb_runline \
    --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026
python -m scripts.mlb_runline_sweep --seasons 2026
# PROB REACH first. If max_p < 0.68 the current floor is still dormant.

python -m models.trainer --model mlb_over_under \
    --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026
python -m scripts.mlb_over_under_sweep --seasons 2026 --artifact <just-trained pkl>
# Worker job `mlb_over_under_retrain_sweep` (register=false) chains both.
# calibrated_threshold_sweep replays live graded picks — wrong tool after a retrain.
```

Do **not** use the close as a feature. Opener-vs-current belongs in
`game_market_gate`.

---

## Next concrete experiment (not “stay paused”)

1. **Worker jobs already declared** (this PR). After merge the worker
   enqueues them from `jobs/declared_jobs.json`:
   - `mlb-game-line-market-sweep-open-bettable-2026-09-15` — Pin de-vig vs
     bettable soft de-vig, `snapshot_type=open`, edges 0.02/0.03/0.04,
     by month, spreads + totals. Totals 2pp already measured −11% on MCP
     (May–Jun). Sweep only — not the card.
   - `mlb-game-line-market-sweep-open-dk-implied-2026-09-15` — GROK
     construction: Pin lean vs DK implied, same edges. The card shops
     BEST_LINE implied, not DK-only.
   Result JSON lands in `worker_jobs.result`.
2. **Do not set `MLB_TOTAL_MARKET_PUBLISH=1` until the worker grid on
   Pin-lean vs BEST_LINE implied confirms.** Keep `mlb_over_under` paused.
3. **If the BEST_LINE implied 2pp cell holds** (both halves +, n≥25,
   neighbours not a lone peak): that is the flip of this env. Until then
   INSERT stays 0.
4. **If GROK does not hold:** next knobs stay close-aligned quotes (CLV,
   not a feature) + optional model-agree after the 2019–2025 retrain.
   Spreads: do not ship ≥2pp Pin-vs-DK as-is.
5. **Hybrid steam gate** stays shadow on the cards until the overlay is
   re-measured on the market-relative record.

---

## What shipped

| piece | where |
|---|---|
| Sweep | `scripts/game_line_market_sweep.py` — `snapshot_type=open`, 2/3/4pp, `--by-month`, `--vs devig\|implied`, `--pin-lean`, month-chunked load. Thin n still prints. |
| Worker job | `tracking/job_queue.py` `game_line_market_sweep` + two keys in `jobs/declared_jobs.json` |
| Spreads rule | `models/mlb_game_market.py` `MIN_EDGE_SPREADS = 0.018`; INSERT gated by `MLB_SPREAD_MARKET_PUBLISH` (default 0) |
| Totals log | `mlb_total_market` at 0.02; **Pin fair − soft implied, BEST_LINE, pin-lean**; `find_total_bets` wall stays 1.0; INSERT gated by `MLB_TOTAL_MARKET_PUBLISH` (default 0). |
| Card | `scripts/mlb_game_market_card.py --market spreads\|totals\|both` |
| Pipeline | `run_pipeline.py --step mlb-game-market` logs both lanes; INSERT only if env=1 |
| Gate | `game_market_gate` live on the four predictive MLB game models; **shadow** on both cards |
| Settlement | `_RULE_MODEL_MARKETS` spreads + totals |
| App labels | `RL Mkt` / `O/U Mkt` |

`mlb_runline` and `mlb_over_under` remain in `PAUSED_MODELS`. Nothing
autopauses. No settled pick is touched.

---

## What this is not

This is **not** “Grok picked CLE −1.5.” It is the class of edge that number
belongs to: **money divergence** at the **same** line.

**Product split (do not blend):**

- **Card log / INSERT-if-env** = Construction 1: Pin de-vig vs bettable-soft
  de-vig. Totals 2pp **−11.13% / 79**. Env stays 0. Flipping it writes
  that loser.
- **GROK** (Pin no-vig lean vs DK juiced implied, DK-only, ~+11% n≈103)
  is a different population. Worker job may remeasure it. It is **not**
  this card and **not** a justification for `MLB_TOTAL_MARKET_PUBLISH=1`.
  A hold would need a new card.

GROK’s ≥2pp Pin-vs-DK spread sample lost. Pin-vs-soft totals 2pp lost.
Neither is a go-live.
