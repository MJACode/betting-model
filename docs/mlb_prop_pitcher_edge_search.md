# MLB pitcher props: the edge search (2026-09-19)

Perpetual MLB hunt after parked FG / I24 / spread / F5 families
(#757–#762). This pass remesured the **live pitcher-prop cards**
(`mlb_prop_pitcher_k` / `_outs` / `_hits`) and the paused twins
(`_er` / `_walks`), preferring market / public / Pin / RLM / line-shop
filters over an XGBoost unpause.

**Verdict: empty (B).** No construction cleared selective + month-stable
+ROI, n≥40, few/day, no fragile lone peak. No new publisher. No
`PUBLISH=1`. XGBoost stays paused. I24 guards and
`MLB_SPREAD_MARKET_PUBLISH` / `MLB_TOTAL_*_PUBLISH` were not touched.

`mlb_prop_market` stays unwired. The 2026-09-07 pool result
(`docs/mlb_prop_market_eval.md`) still holds; the pitcher-only
pre-registered remesure this pass ran does not rescue it.

---

## Recommendation (one screen)

| Card | Verdict |
|---|---|
| Production K / outs / hits | **Do not overlay, recut, or unpause anything.** Current-artifact K is −10.73u / 56 (win 42.9% vs breakeven 52.9%). Outs −3.47u / 36. Hits −4.60u / 39. Dated-review n≥75 is **not** met; both live cards are still below breakeven. |
| Pin agree / fade on those BETs | K red on both sides of Pin. Outs-under agree-Pin **+48.5% / 9** — n=9. Hits-under any-Pin +6.69u / 28 is the Aug 31–Sep 3 streak. |
| FG public / RLM on those BETs | **Not honest.** `public_betting` is full-game only. Leak-bounded pre-commence on the BET set is a handful of rows (Aug = 0). Last-upsert t80 looks green only on the prior artifact. |
| `mlb_prop_market` pitcher-only | Outs 3pp: Aug **+2.0% / 52**, Sep **−9.7% / 28**. The 09-07 “roughly flat” slice does not survive a second month. Still not a card. |
| ER / walks | Paused 2026-07-11. Last BET mid-July. Lifetime red. Not unpaused. |

---

## Today’s live board (2026-09-19, unsettled)

Quoted from `pick_label`, checked against `pick_side` / `scored_line`:

| Label | Model | Odds | Book |
|---|---|---|---|
| `Robert Gasser Under 5.5 Ks` | `mlb_prop_pitcher_k` | −120 | draftkings |
| `Jackson Jobe Over 4.5 Ks` | `mlb_prop_pitcher_k` | −104 | fanduel |
| `Michael McGreevy Under 17.5 Outs` | `mlb_prop_pitcher_outs` | −115 | draftkings |
| `Reid Detmers Under 17.5 Outs` | `mlb_prop_pitcher_outs` | +150 | fanatics |

Yesterday (settled): `Tyler Phillips Over 3.5 Ks` LOSS, `Ranger Suarez Under 4.5 Ks` LOSS, `Gerrit Cole Over 15.5 Outs` WIN, `Bryan Woo Under 17.5 Outs` WIN, `Connor Prielipp Over 4.5 Hits` LOSS, `Clay Holmes Over 4.5 Hits` LOSS.

---

## Production cells (Supabase, 2026-09-19)

Pregame `signal_type='BET'`, not VOID, priced, `result IN ('WIN','LOSS')`.
Units = `profit_flat / 100`.

### Lifetime by month

| Model | May | Jun | Jul | Aug | Sep | Lifetime u / n |
|---|---|---|---|---|---|---|
| `mlb_prop_pitcher_k` | −3.21 / 83 | +5.87 / 31 | −0.53 / 45 | −6.79 / 23 | **−16.09 / 74** | **−20.75 / 256** |
| `mlb_prop_pitcher_outs` | −0.77 / 48 | −0.18 / 35 | — | +1.51 / 3 | +0.38 / 45 | **+0.94 / 131** |
| `mlb_prop_pitcher_hits` | −12.29 / 46 | −5.86 / 19 | — | +1.48 / 4 | +2.99 / 57 | **−13.68 / 126** |
| `mlb_prop_pitcher_er` | +5.35 / 62 | −1.80 / 14 | −7.33 / 35 | — | — | **−3.78 / 111** (paused 07-11) |
| `mlb_prop_pitcher_walks` | −6.32 / 41 | −0.03 / 15 | −9.31 / 18 | — | — | **−15.66 / 74** (paused 07-11) |

K is not month-stable. Outs is flat, then a 3-bet August, then a flat September. Hits is red until a September that is one hot week then fade (see below).

### Current artifact (the cards that fire today)

Active registry: K `20260903_190319` (live from 2026-09-04), outs / hits
`20260903_233111` / `20260903_230550` (live from 2026-09-04; dated-review
clock for outs is 2026-09-05).

| Cell | n | W-L | units | ROI | CLV |
|---|---|---|---|---|---|
| K over | 16 | 2-14 | **−11.88** | −74.3% | +3.36 |
| K under | 40 | 22-18 | +1.15 | +2.9% | +1.47 |
| Outs over | 4 | 2-2 | −0.01 | −0.2% | +6.21 |
| Outs under | 33 | 14-19 | **−4.46** | −13.5% | +1.99 |
| Hits over | 27 | 11-16 | **−5.90** | −21.8% | +1.76 |
| Hits under | 12 | 7-5 | +1.30 | +10.9% | +1.53 |

**Dated review** (`docs/thresholds.md`, n≥75, pause if still below
breakeven). Pregame, current artifact, 2026-09-19:

| Model | Since | n | W | wr | breakeven | units | per day |
|---|---|---|---|---|---|---|---|
| `mlb_prop_pitcher_k` | 2026-09-04 | **56** | 24 | .429 | .529 | **−10.73** | 4.31 |
| `mlb_prop_pitcher_outs` | 2026-09-05 | **36** | 16 | .444 | .487 | **−3.47** | 2.57 |

Neither has hit n=75. Both remain below their own mean implied. This
search does **not** pause them — that is mike’s (`Updated-By:`).

Full-universe `mv_scored_pick_outcomes` (BET+NONE+AVOID, clean window
≥2026-08-09, −140 floor) is red in the dead zone too. Loosening the cut
does not draw from a hidden +EV pool.

---

## Overlays on the existing BET cells

### Pin (leak-bounded, equal line, player-matched)

Window 2026-08-27 → 2026-09-18. Newest pre-game Pinnacle quote,
`snapshot_at <= commence_time`, same `scored_line`.

| Cell | agree Pin | fade Pin | no Pin |
|---|---|---|---|
| K over | −61.8% / 10 | −82.0% / 11 | +41.7% / 4 |
| K under | −16.9% / 39 | −18.2% / 17 | +25.4% / 6 |
| Outs under | **+48.5% / 9** | −1.3% / 26 | −40.0% / 8 |
| Hits under | +14.7% / 11 | +35.0% / 9 | +24.1% / 8 |
| Hits over | +6.1% / 12 | −5.6% / 15 | −35.3% / 6 |

Agree-with-Pin does not save K. Outs-under agree is n=9. Hits-under is
green on every Pin bucket because the week of Aug 31–Sep 3 is in all
three (daily: +0.66, +0.87, +1.64, +2.22u; then current-artifact under
is +1.30u / 12).

### FG public / RLM

`public_betting` markets are `h2h` / `spreads` / `totals` only — **no
prop splits**. Pre-commence consensus totals-over (offset-aware
`snapshot_at < commence_time`):

| Month | games with a row | pre-commence |
|---|---|---|
| May | 15 | 0 |
| Jun | 400 | 59 |
| Jul | 342 | 25 |
| Aug | 397 | **0** |
| Sep | 254 | 54 |

Leak-bounded join onto pitcher BETs is 0–6 rows per cell. Last-upsert
(the UNIQUE(game, market, side, book) overwrite) covers the current
artifact 100% and is **post-commence / August-empty**. Outs-under
last-upsert t80 is +5.93u / 49 pooled and **−1.25u / 20** on the
current artifact. Not a filter.

### Juice / book

Current-artifact juice buckets are all n<30 except K under to-140
(+0.84u / 28, +3.0%). K over is red in plus, even, and to-140. Line-shop
`decision_book` slices are smaller still.

### High-edge outs under (full-outcome)

`mv_scored_pick_outcomes` outs-under edge 0.16–0.20 since 2026-08-09 is
+16.70u / 42. Neighbours at 0.12–0.16 are +4.48u / 71. **That green is
prior-artifact August NONE rows** (+15.00u / 29). Current-artifact BET
at e16 is −1.00u / 9. A cut that only wins on dead-zone rows the scorer
already refused is not a card.

---

## Pitcher-only `mlb_prop_market` remesure

The 2026-09-07 write-up said `pitcher_outs` was “roughly flat” and asked
for a **pre-registered** test before anyone treated that slice as an
edge. This is that test: Pin de-vig vs DK de-vig, equal line, leak-bounded
open, 3pp, pitcher_outs only.

| Month | n | units | ROI | under n / u |
|---|---|---|---|---|
| 2026-08 | 52 | +1.03 | **+2.0%** | 25 / +4.72 |
| 2026-09 (1–19) | 28 | −2.73 | **−9.7%** | 22 / −3.18 |

August is the “flat” month. September is red. Combined it is not
month-stable and September is the one that is still posting. Do not
wire `mlb_prop_market`. Do not invent a pitcher-outs card from the
August half.

Reproduce:

```bash
python -m scripts.mlb_prop_market_sweep --start 2026-08-01 --end 2026-09-19 \
  --markets pitcher_outs pitcher_strikeouts pitcher_hits_allowed
```

---

## Closest misses (not shipped)

1. **K under, current artifact** — +2.9% / 40. Only September. Overs on
   the same card −74.3% / 16. Lifetime K −20.75u.
2. **Hits under since 2026-08-27** — +6.69u / 28. Daily mass is Aug 31–
   Sep 3 (prior artifact). Current artifact +1.30u / 12.
3. **Outs under agree-Pin** — +48.5% / 9. n=9.
4. **Outs under last-upsert FG-over t80** — +5.93u / 49 pooled;
   current artifact −1.25u / 20. Public is FG-only; August pre-commence
   is empty.
5. **Outs under e16 full-outcome** — +16.70u / 42, almost all August
   NONE on the prior artifact.
6. **Pin-vs-DK pitcher_outs 3pp** — Aug +2.0% / 52, Sep −9.7% / 28.

---

## What this does not do

- No `PAUSED_MODELS` edit. No XGBoost unpause.
- No `PUBLISH=1`. No new `MLB_*_PUBLISH` env.
- No I24 / spread-market / F5 / totals-fade guard change.
- `mlb_prop_market` stays a library.
- Dated-review pause at n≥75 is **not** taken here.

## If this is revisited

Wait for (a) current-artifact K and outs to hit n≥75 on the dated-review
query in `docs/thresholds.md`, or (b) a second full month of Pinnacle
pitcher-prop quotes after September. Then re-run the sweep above. Do not
re-hunt FG-public-on-props or F5-vs-FG until public pre-commence August
is repaired — there is no history to grade.
