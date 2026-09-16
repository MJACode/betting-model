# MLB market-handicap features

Wired 2026-09-16 (mike: game models should learn the same board work a
handicapper uses — not another pure “who covers / who wins” fundamentals
model). Code: `features/market_handicap.py`. Consumed by `mlb_runline` and
`mlb_over_under` train + score. **Not an unpause. Not a live-artifact
register.**

`game_market_gate` is unchanged: it still only downgrades a new BET → NONE
after `_decide`. These columns teach the model the same signals *before*
the cut.

Job **121848** (`mlb_runline_retrain_sweep`, register=false, 2019–2025 /
holdout 2026) trained on the first (#740) block and found **no shippable
cut**: holdout AUC **0.6056**, best volume cell **0.42 / 0.04 = −0.32% /
314**. Verdict in the job: feature work, not a re-cut. This file is that
feature work plus the coverage dig that explains why the first block could
not have helped.

#741 added worker job `mlb_over_under_retrain_sweep` (declared
`mlb-over-under-retrain-sweep-2026-09-16`). After this merges, that job’s
`FEATURE_MAP` includes the richer columns below. Do not unpause either
model. Do not register a live pickle. Do not flip `MLB_*_MARKET_PUBLISH`.

## Coverage dig (measured 2026-09-16)

Completed MLB games (`home_score IS NOT NULL`):

| Season | Games | Role |
|---|---|---|
| 2019 | 2,758 | train |
| 2020 | 1,109 | train |
| 2021 | 2,400 | train |
| 2022 | 2,408 | train |
| 2023 | 2,436 | train |
| 2024 | 2,443 | train |
| 2025 | 2,446 | train |
| **2019–2025** | **16,000** | **train** |
| 2026 | 2,059 | holdout |

Same matrix for `mlb_runline` and `mlb_over_under` (both attach the
handicap block via `include_handicap=True`). Public columns differ by
market (home-runline vs over); movement columns are shared except
`mkt_spread_move` vs `mkt_total_move`.

### Public (`pub_*`) — hypothesis confirmed

`public_betting` exists **only** 2026-05-31 → 2026-09-16 (8,214 rows /
1,369 games). **Zero rows in 2019–2025.** A 2019–2025 train cannot split
on ticket/money/RLM no matter how the column is named.

Honest as-of coverage uses `_parse_iso_ts` (offset-aware), **not** text
`snapshot_at > commence_time`. `public_betting.snapshot_at` is
`-04:00`; `games.commence_time` is `+00:00`. Lexicographic compare on
those strings is the bug `_parse_iso_ts` exists to prevent:

| Bound | Home-runline games with a pre-game split |
|---|---|
| Text `snapshot_at <= commence_time` (#740 note) | **585 / 1,369** |
| `::timestamptz` vs commence | 99 |
| Python-equivalent (timestamptz + trusted first pitch), completed 2026 | **101 / 2,059** |

#740’s 585 was the text bound. Feature code has always parsed offsets, so
job 121848 actually saw **~101** holdout games with `pub_*`, not 585.

2026 by month (completed games, Python-equivalent bound, home-runline
ticket **and** totals-over — the two counts matched):

| Month | Completed | Any `public_betting` row | Pregame `pub_*` |
|---|---|---|---|
| 2026-05 | 417 | 15 | 0 |
| 2026-06 | 378 | 400 | 59 |
| 2026-07 | 338 | 342 | 25 |
| 2026-08 | 397 | 397 | 2 |
| 2026-09 | 200 | 215 | 15 |
| **2026** | **2,059** | 1,327 | **101 (4.9%)** |

Last-upsert-wins is why August is 2: hourly refresh overwrote the
pre-game split with a post-start fetch. The ingestor now refuses
post-start upserts; history already overwritten stays NaN.

**NaN rate, `pub_home_*` / `pub_fav_*` / `pub_over_*` (same games):**

| Window | Non-null | NaN rate |
|---|---|---|
| Train 2019–2025 | **0 / 16,000** | **100%** |
| Holdout 2026 | **101 / 2,059** | **95.1%** |

### Movement (`mkt_*`) — fires in train; SBR open/close is the 2019–2020 source

Distinct-timestamp proxy (full-game `h2h`/`spreads`/`totals`, pregame
bound, DK series when DK exists else all books). `mkt_open_implied_home`
is filled whenever one priced snapshot exists (SBR), so it is **not**
sparse. Move columns need two ticks:

| Season | Games | `mkt_move_home_pp` | `mkt_spread_move` | `mkt_total_move` | Pinnacle sharp | ≥2 books |
|---|---|---|---|---|---|---|
| 2019 | 2,758 | 0* | 0 | 0* | 0 | 0 |
| 2020 | 1,109 | 0* | 0 | 0* | 0 | 0 |
| 2021 | 2,400 | 16 | 756 | 0 | 1,389 | 1,452 |
| 2022 | 2,408 | 673 | 658 | 0 | 1,707 | 1,848 |
| 2023 | 2,436 | 1,153 | 1,142 | 0 | 1,883 | 2,180 |
| 2024 | 2,443 | 2,145 | 1,699 | 2,102 | 2,266 | 2,386 |
| 2025 | 2,446 | 2,205 | 1,566 | 2,172 | 2,298 | 2,384 |
| **Train** | **16,000** | **6,192 (38.7%)*** | **5,821 (36.4%)** | **4,274 (26.7%)*** | **9,543 (59.6%)** | |
| 2026 | 2,059 | 2,053 (99.7%) | 2,053 | 2,053 | 2,021 | 2,059 |

\*2019–2020 SBR stores **open and close on the same `snapshot_at`** (a
calendar date) with different prices: 2,655 / 2,758 of 2019 h2h games,
and the same open+close pattern on **totals** (spreads are open-only).
Counting distinct timestamps therefore reports move = 0, while the #740
builder treated the two rows as a move whose **sign depended on fetch
order**. Job 121848 trained on that unstable sign.

This pass sorts `snapshot_type` open→close on a tied timestamp, skips
`*_1st_5_innings` markets (F5 −0.5 mixed into FG −1.5 invented a spread
move), and unique-keys `(snap, snapshot_type)` per book. After that,
2019–2020 `mkt_move_home_pp` and `mkt_total_move` are the SBR open→close
window (~3,867 games), and `mkt_spread_move` stays empty there (no SBR
spread close).

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
| `pub_dog_ticket_pct` / `pub_dog_rlm` | complement of the favorite (only when fav framing exists) |
| `pub_over_ticket_pct` / `pub_over_money_pct` / `pub_over_rlm` | totals over |

Classic board: favorite −1.5 at **90% tickets / 20% money** → `pub_fav_rlm = -70`
→ lean the dog +1.5. We do **not** mix h2h splits onto a runline row — the
ticket pile in that example is the runline market.

### Line move / sharp (already computed)

| Feature | Handicap language |
|---|---|
| `mkt_open_implied_home` | opening pre-game home implied (vig in; movement is a difference) |
| `mkt_move_home_pp` / `mkt_move_abs_pp` | latest − open, signed / abs, probability points (steam) |
| `mkt_spread_move` / `mkt_total_move` | latest − open on the number |
| `mkt_book_disagree_pp` | cross-book spread at each book’s own latest pre-game price |
| `mkt_snapshots` | how many pre-game snapshots we saw (thin vs thick) |
| `mkt_sharp_devig_home` / `mkt_dk_vs_sharp_pp` | Pinnacle no-vig home, DK distance from it |

### Gated / interaction (this pass)

These **only activate when the raw inputs exist**. Presence flags are
1.0/0.0 after attach (“we looked”). Steam/RLM flags are None when
tickets or the move is missing — not a fake 0-steam.

| Feature | When it is non-null | Meaning |
|---|---|---|
| `pub_home_present` / `pub_over_present` | always 0/1 | splits vs not |
| `mkt_move_present` / `mkt_total_move_present` | always 0/1 | a real open→latest tick vs one snapshot |
| `pub_home_rlm_x_move` / `pub_fav_rlm_x_move` / `pub_over_rlm_x_move` | both RLM and move | magnitude kept; sign is “money vs tickets × line” |
| `pub_home_public_steam` / `pub_fav_public_steam` / `pub_over_public_steam` | tickets **and** move | 1 if tickets ≥ 55% **and** the line moved with them |
| `pub_home_rlm_flag` / `pub_fav_rlm_flag` / `pub_over_rlm_flag` | tickets **and** move | 1 if tickets ≥ 55% **and** the line moved against them |
| `pub_fade_public_fav` | fav tickets + RLM | 1 if fav tickets ≥ 65% and `pub_fav_rlm < 0` |
| `pub_home_vs_sharp` | home tickets + Pinnacle | ticket share (0–1) minus sharp no-vig home |
| `mkt_steam_home` | home-prob move | 1 if move ≥ +3pp |
| `mkt_total_steamed` | total move | 1 if abs(move) ≥ 0.5 |

55% is the same `public_heavy` default as `models/game_market_gate.py`.
3pp is the steam bucket in `docs/market_movement_features.md`. Runline
steam uses **price** move (`mkt_move_home_pp`), not `mkt_spread_move` —
the FG number stays ±1.5; the juice moves.

`mkt_move_present` varies in 2021–2025 (~39% of train after the
distinct-timestamp proxy; higher once SBR open/close is ordered). That
is the flag a 2019–2025 fit can actually split on. `pub_*_present` is
constant 0 in that freeze; it is there for a later train that includes
2026.

## Leakage rules (non-negotiable)

Same bound the rest of the engine already uses (`_is_pregame_snapshot` /
`trusted_first_pitch`):

1. Odds: `snapshot_type <> 'in_play'` **and** `snapshot_at <= first pitch`
   (scheduled start when first pitch is missing or implausibly early).
   Full-game markets only (`h2h`, `spreads`, `totals`).
2. Public: the same **parsed** bound on `public_betting.snapshot_at`.
   Offset-aware. Text compare is not a bound.
3. Raw percentages / RLM / line-move: missing is `None`, never `0.0`.
   Presence flags are 0/1. Steam/RLM flags are None unless both inputs
   exist.
4. All handicap columns are in `SPARSE_OK_FEATURES`. A null does **not**
   `dropna` the row.

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

Job 121848 already ran the first block and did not ship. After **this**
merges:

```
python -m models.trainer --model mlb_runline \
  --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026 --trials 100
# register=false. Do not unpause. Do not commit a live pkl
# until the holdout sweep (scripts/mlb_runline_sweep --artifact <pkl>) is read.

python -m models.trainer --model mlb_over_under \
  --seasons 2019 2020 2021 2022 2023 2024 2025 --holdout 2026 --trials 100
```

Same freeze: `register=false`, `PAUSED_MODELS` untouched, no `PUBLISH`
env. Worker job types `mlb_runline_retrain_sweep` and
`mlb_over_under_retrain_sweep` chain retrain → sweep on the just-trained
pickle (`scripts.mlb_over_under_sweep --artifact`). Public columns will
still be 100% NaN in 2019–2025 train; the O/U fit can use SBR open→close
`mkt_total_move`, 2024–2025 DK ticks, and the gated move flags.

## What this is not

- Not a pause/unpause.
- Not a live-artifact register.
- Not `mlb_spread_market` / `mlb_total_market` (those are Pin-vs-soft cards;
  INSERT still gated).
- Not PCG. `PublicSplits.source` on the gate stays the hook; this block reads
  `public_betting` only.
- Not a cut change.
