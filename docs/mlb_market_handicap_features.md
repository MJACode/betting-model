# MLB market-handicap features

Wired 2026-09-16 (mike: game models should learn the same board work a
handicapper uses — not another pure “who covers / who wins” fundamentals
model). Code: `features/market_handicap.py`. Consumed by `mlb_runline` and
`mlb_over_under` train + score. **Not an unpause. Not a live-artifact
register. Retrain is the next job after this merges.**

`game_market_gate` is unchanged: it still only downgrades a new BET → NONE
after `_decide`. These columns teach the model the same signals *before*
the cut.

## What was already in the pipeline and unused

| Piece | Lived | Used as a feature? |
|---|---|---|
| `features/market_movement.py` | 2026-08-31 | **No** — `docs/market_movement_features.md` said so on purpose |
| `public_betting` (Action Network tickets/money) | 2026-05-31 | **No** — stamped on the pick for display; `_decide` never read it |
| `models/game_market_gate.py` | 2026-09-15 | Decision overlay only. Does not enter the matrix |

Hypothesis confirmed by reading `FEATURE_MAP["mlb_runline"]` /
`mlb_over_under` (starter/team/bullpen/weather + `spread_home`/`total_line`)
and by grepping: `load_market_movement` had no train/score caller.

## The features

Names live in `features/market_handicap.py` (`MLB_HANDICAP_SPREAD_FEATURES`,
`MLB_HANDICAP_TOTAL_FEATURES`). Movement names are **reused** from
`MARKET_MOVEMENT_FEATURES` — no new odds join.

### Public (Action Network)

Home-relative (runline) and over-relative (totals). Percentages are 0–100.

| Feature | Handicap language |
|---|---|
| `pub_home_ticket_pct` / `pub_home_money_pct` | tickets % and handle % on HOME −1.5 / +1.5 |
| `pub_home_rlm` | **money − tickets** on home. Positive = money ahead of tickets on home |
| `pub_fav_ticket_pct` / `pub_fav_money_pct` / `pub_fav_rlm` | the same three on the **favorite** (`spread_home < 0` → home is fav) |
| `pub_over_ticket_pct` / `pub_over_money_pct` / `pub_over_rlm` | totals over |

Classic board: favorite −1.5 at **90% tickets / 20% money** → `pub_fav_rlm = -70`
→ lean the dog +1.5. We do **not** mix h2h splits onto a runline row — the
ticket pile in that example is the runline market.

Favorite framing is side-relative without baking in a BET side: the model still
predicts home-covers; `pub_fav_*` is how a handicapper talks about the same
number.

### Line move / sharp (already computed)

| Feature | Handicap language |
|---|---|
| `mkt_open_implied_home` | opening pre-game home implied (vig in; movement is a difference) |
| `mkt_move_home_pp` / `mkt_move_abs_pp` | latest − open, signed / abs, probability points (steam) |
| `mkt_spread_move` / `mkt_total_move` | latest − open on the number |
| `mkt_book_disagree_pp` | cross-book spread at each book’s own latest pre-game price |
| `mkt_snapshots` | how many pre-game snapshots we saw (thin vs thick) |
| `mkt_sharp_devig_home` / `mkt_dk_vs_sharp_pp` | Pinnacle no-vig home, DK distance from it |

Public-steam (tickets heavy **and** the line moved with them) is the
**interaction** of `pub_*` and `mkt_*_move`. XGBoost can split on both; we do
not pre-multiply them into a 0/1 that throws away magnitude.

## Leakage rules (non-negotiable)

Same bound the rest of the engine already uses (`_is_pregame_snapshot` /
`trusted_first_pitch`):

1. Odds: `snapshot_type <> 'in_play'` **and** `snapshot_at <= first pitch`
   (scheduled start when first pitch is missing or implausibly early).
2. Public: the same Python bound on `public_betting.snapshot_at`.
3. Missing is `None`, never `0.0`. “We never saw splits” is not “0% public”.
4. All handicap columns are in `SPARSE_OK_FEATURES`. A null does **not**
   `dropna` the row. That is how 2019–2025 fundamentals rows survive next to
   2026 games that have splits and DK movement.

### Why the public bound deletes most stored rows today

`public_betting` is `UNIQUE(game_id, market, side, book)` — last upsert wins.
`snapshot_at` is **fetch time**, not Action Network’s print time. Measured
2026-09-16: **4,704 of 8,214** rows have `snapshot_at > commence_time`
because the hourly refresh kept writing after first pitch.

Those rows are **dropped** at feature time, not used. Honest pre-commence
coverage on the home runline: **585 / 1,369** games (2026-05-31 → 2026-09-16).
The ingestor now **refuses post-start upserts**, so future last-rows stay the
last pre-game split. Historical overwrites are already gone; they stay NaN.

### Movement coverage is wider than the 2026-08-31 note

`docs/market_movement_features.md` measured Pinnacle at 73 MLB games. Re-queried
2026-09-16: Pinnacle **11,913** MLB games from 2021-04-09; DraftKings **12,677**.
SBR consensus is still one snapshot per game 2009–2026, so pre-DK seasons stay
NaN on the move columns (SPARSE_OK). The “must be a 2026-only model” constraint
is **not** why these columns are sparse — `dropna` is.

## Train vs serve

| Path | How the block is attached |
|---|---|
| Train / sweep / backtest | `_build_bulk_mlb_lookups(..., include_handicap=True)` when the model’s `FEATURE_MAP` lists a handicap column; `_build_mlb_features_from_bulk` merges |
| Live `score_game` | `build_mlb_game_features` loads one game’s movement + splits. Favorite framing looks up the pre-game **spreads** line because the shared feature row is built from h2h odds |

Existing live artifacts still score on `artifact["feature_cols"]` (the old
list). Extra keys on the dict are ignored until a retrain writes a new pickle.
`scripts/mlb_runline_sweep.py` reads the **artifact** list, not `FEATURE_MAP`,
so growing the map cannot reshape an old pickle.

`mlb_moneyline` and all F5 lists are **unchanged**. Helpers are shared; wiring
moneyline is a later call (it is live, not paused).

## Retrain next (not this PR)

```
python -m models.trainer --model mlb_runline \
  --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026 --trials 100
# register=false on the worker job. Do not unpause. Do not commit a live pkl
# until the holdout sweep (scripts/mlb_runline_sweep --artifact <pkl>) is read.

python -m models.trainer --model mlb_over_under \
  --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026 --trials 100
```

Same freeze as every queued MLB retrain: `register=false`, `PAUSED_MODELS`
untouched, no `PUBLISH` env. Worker job type `mlb_runline_retrain_sweep`
already chains retrain → sweep on the just-trained pickle.

## What this is not

- Not a pause/unpause.
- Not `mlb_spread_market` / `mlb_total_market` (those are Pin-vs-soft cards;
  INSERT still gated).
- Not PCG. `PublicSplits.source` on the gate stays the hook; this block reads
  `public_betting` only.
- Not a cut change.
