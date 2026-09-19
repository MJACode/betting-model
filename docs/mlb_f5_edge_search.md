# MLB F5 market family: the edge search (2026-09-19)

Perpetual hunt after parked full-game families (`mlb_runline` #757 empty,
`mlb_over_under` #758/#759 empty, I24 / `mlb_total_public_fade` #760
production remesure red, `mlb_spread_market` 1.8pp #761 parked). This
pass hunted a **different** construction in first-five innings:
`mlb_f5_moneyline`, `mlb_f5_over_under`, `mlb_f5_runline`.

**Pause/unpause is Mike’s.** XGBoost is not unpaused. No `PUBLISH=1`.
I24 guards and `MLB_SPREAD_MARKET_PUBLISH` were not touched.

**Verdict: empty.** No construction cleared selective + month-stable
+ROI, n≥40, few/day, no fragile K-peak. Closest misses are below so
the next hunt can chain props / other sports instead of re-deriving
these SQL cells.

---

## Coverage (Supabase `execute_sql`, 2026-09-19)

| Source | What is actually there |
|---|---|
| F5 scores | 1,749 / 2,257 2026 MLB games; `home_score_f5` from 2026-04-16 → 2026-09-18 |
| `h2h_1st_5_innings` DK | 1,640 games, 2026-05-10 → 2026-09-19. Multi-book only from **2026-09-02** (~224 games) |
| Pinnacle F5 ML | **0 rows** on `h2h_1st_5_innings` |
| `totals_1st_5_innings` / `spreads_1st_5_innings` real books | Pin / FD / MGM / WH / Bovada from **2026-09-02** only (~223–224 games). Pre-May `sbr_consensus` is synthetic (full-game × 0.62 / fixed −0.5) |
| Pin F5 spreads | `spread_home = 0` on 4,583 / 4,591 rows — stored as F5 ML, not −0.5. Equal-line vs soft −0.5 is empty |
| `public_betting` | Full-game `h2h` / `spreads` / `totals` only. **No F5 splits** |
| Public pre-commence (`snapshot_at < commence_time`) | May 0, Jun 59, Jul 25, **Aug 0**, Sep 54 (h2h home consensus) |

Live `mlb_f5_moneyline` settled BET (not VOID, priced): **213, 123-90, −3.29u, −1.54%**.
`mlb_f5_over_under` / `mlb_f5_runline`: May 9–10 synthetic-era leftovers (unpriced) + NONE rows from 2026-09-15. BET stays paused (leak-era 2026-05-08 artifacts).

---

## What was measured

Every cell below is leak-bounded (`snapshot_type='open'` and
`snapshot_at <= commence_time`). F5 ML / F5 totals grade
`home_score_f5` / `away_score_f5`. Pushes (F5 tie; total = line) are
out of the ROI denominator. Soft books are `BEST_LINE_BOOKMAKERS`
minus Pinnacle unless named.

### 1. Pin de-vig vs bettable-soft de-vig — F5 totals (closest miss)

Equal `total_line`, 300s, one bet/game, best edge. **September only**
(Pin F5 totals begin 2026-09-02).

| mode | cut | n | units | ROI | notes |
|---|---|---|---|---|---|
| `dev_any` | 1.5pp | **69** | **+5.09u** | **+7.37%** | 42 over / 27 under; 16 days; avg **5.1**/day; **max 9**/day |
| `dev_any` | 2.0pp | 34 | +5.18u | +15.23% | n<40 |
| `dev_lean` | 1.5pp | 38 | +4.96u | +13.04% | n<40 |
| `imp_*` | 1.5pp+ | 0 | — | — | juice eats Pin-fair − soft-implied |

Week split at `dev_any` 1.5pp: Sep 2–10 **+11.70% / 31**; Sep 11–18
**+4.90% / 38**. Both halves +. That is **not month-stable** (one
calendar month, 16 days). Max 9/day fails “few/day”. Full-game analog
is the parked Pin-de-vig vs soft-de-vig totals 2pp **−11.13% / 79**
(`docs/mlb_runline_ou_edge_search.md`). Do **not** ship a
`mlb_f5_total_market` card on this cell. Remeasure when Pin F5 has
two full months (`scripts/game_line_market_sweep.py --market
totals_1st_5_innings`).

### 2. F5 ML DK steam (May 10 → Sep 18; 1,595 games, avg 11.8 snaps)

Follow steam ≥1–5pp: **red every month** at 1pp and 2pp (Aug −13.0% /
191 at 1pp; −11.7% / 104 at 2pp).

Fade steam 2pp: pooled **+2.07% / 339**, early +6.23% / 74, late
+0.91% / 265. **Neighbours flip**: 1pp −3.27% / 693; 3pp −4.50% / 167.
Monthly at 2pp: May +39% / 18, Jun **−4.37% / 56**, Jul +1.32% / 85,
Aug +2.55% / 104, Sep **−1.80% / 76**. Fragile peak, not a plateau.

### 3. FG public overlay on F5 ML (pre-commence only)

Fade the FG consensus ticket pile, bet the other F5 ML side at last
DK open.

| cut | n | ROI | Jun | Jul | Aug | Sep |
|---|---|---|---|---|---|---|
| t60 | 82 | +6.59% | +16.33% / 33 | +23.21% / 20 | **empty** | **−15.96% / 29** |

Pooled plus is Jun/Jul. August public pre-commence is **0** (same
caveat as I24). September is red. Not month-stable.

RLM (tickets − money ≥10pp, fade tickets) on the same join: Jun
−6.24% / 28, Jul +14.47% / 6, Sep +1.92% / 19. Thin and mixed.

### 4. F5 ML vs FG ML implied gap (DK vs DK)

Bet the F5 side that is *softer* than the full-game implied. May 1pp
−3.54% / 168; Jun 1pp −11.37% / 208; Jul 1pp −5.71% / 179. Tighter
cuts stay red. Opposite (bet the *sharper* F5 side) also red in July.
Favorite-disagreement (F5 fav ≠ FG fav) is thin (Aug n=18, −19.4%).

### 5. Blind / juice F5 ML

| rule | n | ROI |
|---|---|---|
| Bet every F5 dog | 1,353 | **−8.81%** (early −10.4%, late −7.7%) |
| Bet every F5 fav | 1,353 | **−3.67%** |
| Dog by fav band (−120 / −140 / −160 / −200) | 81–550 | all **−6% to −17%** |
| Fav at −119 or shorter | 81 | +3.86% pooled; May–Jul + then Aug **−27% / 18**, Sep **−32% / 11** |

### 6. FG public OVER → F5 under (Sep only; FD F5 total)

t60 / t70 / t80: **−24.6% / 37** (t80 −26.9% / 33). Pin F5 line
over-rate 110-90-10 (under WR 45%) — no blind F5-under lean.

### 7. Pin F5 “spreads” line 0 vs DK F5 ML

210 joins, 145 inside 1h. Pin-lean vs DK *implied*: **n=0** at 1.5pp+
(DK juice). vs DK *de-vig*: 1.5pp n=28 −6.8%; 2pp n=13 +16.8% (thin).
Not a card.

---

## What this is not

- **Not** an unpause of `mlb_f5_moneyline` / `mlb_f5_over_under` /
  `mlb_f5_runline`. Live F5 ML is −1.54% / 213. F5 O/U and F5 RL
  artifacts are leak-era + synthetic-line.
- **Not** another 1.8pp `mlb_spread_market` neighbour.
- **Not** a weakening of I24 / `MLB_TOTAL_PUBLIC_FADE_*` / spread
  publish env.
- **Not** a `PUBLISH=1` card. No new publisher was added.

---

## What shipped (plumbing only)

| piece | where |
|---|---|
| Assessment | this file |
| Sweep | `scripts/game_line_market_sweep.py` accepts F5 Odds API keys and grades `home_score_f5` |
| Worker job | `mlb-f5-totals-market-sweep-2026-09-19` — measure-only remesure of cell 1 |
| Tests | `tests/test_game_line_market_sweep.py` F5 family / grade / validator |

```bash
python -m scripts.game_line_market_sweep \
  --sport MLB --market totals_1st_5_innings \
  --bettable --edges 0.015 0.02 0.025 --by-month \
  --date-from 2026-09-02
```

**Next hunt:** wait until Pin F5 totals has a second full month, then
re-run that command. If 1.5pp is still + in both months, n≥40, max
few/day, neighbours not a lone peak — *then* a `PUBLISH=0`
`mlb_f5_total_market` card is a conversation. Until then, chain
**props / other sports**. Do not re-hunt F5 ML steam, FG-public-on-F5,
or F5-vs-FG implied on this window.
