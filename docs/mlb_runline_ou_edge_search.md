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

This PR wires a **paper, INSERT-gated** totals card. Defaults stay 0.
Do **not** set `MLB_TOTAL_MARKET_PUBLISH=1` on merge. Do **not** set
`MLB_SPREAD_MARKET_PUBLISH=1`. This is not an unpause of `mlb_over_under`
and not live money. The env flip is a later ops step, and only after the
worker GROK job confirms the **same** construction the card now fires.

---

## Recommendation (one screen)

| Market | Verdict |
|---|---|
| Totals | **Paper publisher `mlb_total_market` at 2pp is GROK**: Pin no-vig **lean** minus **DraftKings juiced implied**, equal `total_line`, DK-only. Apr–Jul ~**+11% n≈103**. Not Pin-vs-soft-devig (−11.13% / 79 at 2pp) and not best-soft implied (unmeasured). `mlb_over_under` stays paused. INSERT off until env=1 **after** the worker GROK job confirms. |
| Run line | **Do not live-publish pure Pin-vs-soft spreads.** GROK Pin-open vs DK-open ≥2pp: ~**−5% n≈200**. Earlier same-day bettable-soft de-vig at **1.8pp** was +4.16% / 328 through Aug (both halves +) — a different construction, and GROK’s ≥2pp result is the one that says “more work.” Code for `mlb_spread_market` at 1.8pp remains; INSERT is gated off. `mlb_runline` stays paused. |
| Hybrid | GROK on existing `mlb_over_under` BETs: disagree with Pin lean **−17.7u / 71**; agree any **−5.1u / 53**; agree ≥1.5pp **−0.5u / 8**. Stops the hemorrhage, is **not +EV**. Steam/public overlay stays **shadow** on the market cards. Live gate stays on the four predictive MLB game models. |
| Retrain | **Not run here** (no `DATABASE_URL`). Next only if the worker totals 2pp cell is still negative. Commands at the bottom. |

Do **not** flip `MLB_TOTAL_MARKET_PUBLISH` on this merge. Flip it only
after `mlb-game-line-market-sweep-open-dk-implied-2026-09-15` confirms
GROK 2pp on `snapshot_type=open` (both halves +, n≥25, neighbours not a
lone peak) — that job is the same Pin-lean vs DK-implied population the
card INSERTs. Do **not** flip on the bettable-soft de-vig job (that is
Construction 1, the −11% loser). Do not set `MLB_SPREAD_MARKET_PUBLISH=1`.
Do not silently unpause `mlb_runline` / `mlb_over_under`. Live money still
needs Updated-By after the paper record exists.

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
python -m scripts.calibrated_threshold_sweep --model mlb_over_under
```

Do **not** use the close as a feature. Opener-vs-current belongs in
`game_market_gate`.

---

## Next concrete experiment (not “stay paused”)

1. **Worker jobs already declared** (this PR). After merge the worker
   enqueues them from `jobs/declared_jobs.json`:
   - `mlb-game-line-market-sweep-open-bettable-2026-09-15` — Pin de-vig vs
     bettable soft de-vig, `snapshot_type=open`, edges 0.02/0.03/0.04,
     by month, spreads + totals. **Not** the card’s INSERT population.
     Do not flip `MLB_TOTAL_MARKET_PUBLISH` off this job.
   - `mlb-game-line-market-sweep-open-dk-implied-2026-09-15` — GROK
     construction: Pin lean vs DK implied, same edges. **This** is the
     card. Env flip waits on this result.
   Result JSON lands in `worker_jobs.result`. If Error Handler needs to
   fire them before merge, open a one-off worker-job PR; this branch
   already registers `job_type=game_line_market_sweep`.
2. **If that GROK job’s totals 2pp holds** (both halves +, n≥25,
   neighbours not a lone peak): *then* set `MLB_TOTAL_MARKET_PUBLISH=1`.
   The card already fires that population, so the env writes the measured
   set, not Construction 1. Keep `mlb_over_under` paused. Still paper
   until §2’s go-live gate — env=1 is the paper record, not live money.
3. **If it does not hold:** do not flip the env. Next knobs: best-soft
   implied (unmeasured — a **new** card, not this one) +
   `snapshot_type=close`-aligned quotes (CLV, not a feature) + optional
   model-agree after the 2019–2025 retrain. Spreads: same; do not ship
   ≥2pp Pin-vs-DK as-is.
4. **Hybrid steam gate** stays shadow on the cards until the overlay is
   re-measured on the market-relative record.

---

## What shipped

| piece | where |
|---|---|
| Sweep | `scripts/game_line_market_sweep.py` — `snapshot_type=open`, 2/3/4pp, `--by-month`, `--vs devig\|implied`, `--pin-lean`, month-chunked load. Thin n still prints. |
| Worker job | `tracking/job_queue.py` `game_line_market_sweep` + two keys in `jobs/declared_jobs.json` |
| Spreads rule | `models/mlb_game_market.py` `MIN_EDGE_SPREADS = 0.018`; INSERT gated by `MLB_SPREAD_MARKET_PUBLISH` (default 0) |
| Totals paper | `mlb_total_market` at 0.02; **GROK: Pin lean − DK implied, pin-lean, DK-only**; `find_total_bets` wall stays 1.0; INSERT gated by `MLB_TOTAL_MARKET_PUBLISH` (default 0) |
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

- **Card INSERT** = GROK totals: Pin no-vig lean vs **DK juiced implied**,
  DK-only. That is the +11% sample. Platform §6 usually shops the best
  bettable price at the DK line; this card does **not**, because shopping
  would grade a different P&L than GROK measured. Flag, not a silent
  exception to invent a hybrid.
- **Construction 1** (Pin de-vig vs bettable-soft de-vig) is the −11%
  loser. The worker bettable job measures it. The card must not INSERT it.
- **Best-soft implied** (Pin lean vs the best BEST_LINE juiced implied)
  was a generalisation of GROK. It has no measured ROI. Sweeps may pass
  other `soft_books`; the card must not.

GROK’s ≥2pp Pin-vs-DK spread sample lost. GROK’s ≥2pp Pin-vs-DK totals
sample is the paper candidate until the worker confirms it on
`snapshot_type=open`.
