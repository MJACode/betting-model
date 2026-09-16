# MLB game-market gate

Decision-time overlay for MLB *game* models (`mlb_moneyline`, `mlb_runline`,
`mlb_over_under`, `mlb_f5_moneyline`). Not a retrain. Not a prop-model change.
Code: `models/game_market_gate.py`. Config: `GAME_MARKET_GATE_*` in `config.py`.

## What was already true

- **Edge at pick time** is `model_prob − vig-included implied` of the posted
  price, then `_decide` requires that model's `min_prob` **and** `min_edge`
  (`models/scorer.py`). That *is* a +EV-vs-juice test. It is **not** a
  no-vig-vs-open test, and it does not look at ticket splits.
- **`models/market_relative.py`** is the sharp-vs-soft *prop* construction. MLB
  game scoring never calls it.
- **`features/market_movement.py`** exists; **no model consumes it**
  (`docs/market_movement_features.md`) — 17 seasons of SBR history are one
  snapshot per game, so a retrain on movement would drop every pre-2026 row.
- **`check_line_movement`** is a post-hoc SKIP/CAUTION log, not a BET gate.
- **`public_betting`** (Action Network) is stamped on the pick for display
  (`public_bet_pct` / `public_money_pct`) and is not read by `_decide`.
  Measured 2026-09-15: 8,124 MLB rows, 1,354 games, 2026-05-31 → 2026-09-15.
  There is **no PCG feed** in this repo; `PublicSplits.source` is the hook.

## Live-artifact record (queried 2026-09-15, not a sweep)

Whole published BET set, `condition_status <> VOID`, `is_live` not true.
`profit_flat / 100` units, gated on a real price.

| model | live artifact from | settled BET | W-L | units | avg `clv_pct` |
|---|---|---|---|---|---|
| `mlb_moneyline` | 2026-09-03 | **0** | — | 0 | — |
| `mlb_f5_moneyline` | 2026-09-03 | 8 | 4-4 | −1.22 | +0.554 (n=12 BET rows) |
| `mlb_over_under` | 2026-07-04 (paused 09-03) | 37 | 11-26 | −16.08 | −0.075 |
| `mlb_runline` | 2026-08-23 (paused) | 4 | 3-1 | +1.74 | −1.193 |

Lifetime (all artifacts) on the same four: moneyline 56-45 −2.40u, CLV −0.068;
O/U 70-92 −28.58u; runline 23-21 −0.87u; F5 119-88 −3.95u.

**No cut is wired.** Section 7 needs 25+ settled on the *live* artifact, a
plateau, and both time halves. Moneyline has zero BETs on the honest artifact;
F5 has eight; runline has four; O/U is paused and negative. mike, 2026-09-15:
default is **live** anyway. Extra no-vig floor stays off.

## What the gate does

At score time, after `_decide` / best-price requalify / injury gate:

1. No-vig fair of **our side** from the current two-way (the same quote
   `_get_dk_odds` already bounded at first pitch). `no_vig_edge = model_prob −
   fair`. Extra floor is **off** (`GAME_MARKET_GATE_MIN_NO_VIG_EDGE` unset)
   until a cut clears.
2. **PASS_STEAMED** when the opener we actually stored (first pre-game tick
   `≤ as_of` and `≤ commence`) has already moved through the model: juice
   steam on an unchanged line, or a totals/spreads number that moved ≥ 0.5
   against us. Snapshots after `as_of` or after first pitch are dropped.
3. **PASS_PUBLIC_STEAM** when `public_bet_pct ≥ 55` on our side **and** the
   market moved with the tickets. RLM (tickets heavy the other way, line
   toward us) is stored as `rlm=true` and is **not** required to CLEAR.
4. One-way / missing opener: fail-open (no invented fair, no invented steam).

`GAME_MARKET_GATE_MODE=live` (default; mike, 2026-09-15, despite no §7 cut)
downgrades a **new** BET → NONE on PASS_STEAMED / PASS_PUBLIC_STEAM, with
`downgrade_reason` like `market: market steamed through the model — no chase`.
PASS_EDGE only if `GAME_MARKET_GATE_MIN_NO_VIG_EDGE` is set (it is not).
Fail-open; never upgrades NONE. A locked BET is still a pick (§1c); this
only affects the pass that would *write* a new BET. `shadow` restores
persist-only.

`mlb_spread_market` and `mlb_total_market` are **not** in
`GAME_MARKET_GATE_MODELS`. Their cards apply this module in **shadow** so a
cut that has not been re-measured under the overlay is not silently vetoed.
INSERT is gated by `MLB_SPREAD_MARKET_PUBLISH` / `MLB_TOTAL_MARKET_PUBLISH`
(default 0). `docs/mlb_runline_ou_edge_search.md`.


## How to evaluate the next week

Query `game_market_gate` joined to `picks` on `(game_id, model_id, pick_side)`
for `game_date` since this shipped:

- **CLV** on BET rows (`picks.clv_pct` / `clv_beat_close`, same-line only —
  `docs/clv.md`), split `verdict = 'CLEAR'` vs `PASS_*`.
- **ROI** in units (`profit_flat / 100`, only where
  `COALESCE(decision_odds, dk_odds) IS NOT NULL`) on (a) published BETs,
  (b) the full graded universe (`BET`/`AVOID`/`NONE` with a result), (c) the
  counterfactual of BETs whose gate was CLEAR.
- Do not recut from a BET-only sample. Do not pause/unpause from this file.
  `GAME_MARKET_GATE_MODE=shadow` is the env override if a week of live
  downgrades needs to be measured without changing `signal_type`.
