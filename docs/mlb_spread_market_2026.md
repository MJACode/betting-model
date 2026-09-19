# mlb_spread_market — September 2026 remesure (park)

**2026-09-19.** Production as-of remesure of the existing Pin-vs-BEST_LINE
de-vig card. **Does not clear the ship bar.** No cut change. No
`MLB_SPREAD_MARKET_PUBLISH=1`. Not an unpause of `mlb_runline` or XGBoost.
I24 / `mlb_total_public_fade` untouched.

The 2026-09-15 print (+4.16% / 328 through August; module docstring Sep
+11.19 on a few days) was the same *family*, not this window. September
BEST_LINE previously timed out on MCP; this pass month-chunked, then
re-ran each month as one window so last-day quotes were not clipped.

---

## Verdict (one screen)

| Question | Answer |
|---|---|
| Construction | Last pre-commence `open` quote per `(game, book)`, `snapshot_at <= commence`, Pin de-vig vs `BEST_LINE` de-vig, equal ±1.5, 300s, one bet/game (best edge), price ≥ −200 |
| Sep settled (through 2026-09-18) | **40 bets, +2.09u, +5.2%**, 23-17, max 5/day |
| Season Apr–Sep 18 | **368 bets, +15.75u, +4.3%** |
| Early / late | Apr–Jun **+1.53% / 210**; Jul–Sep **+7.9% / 158** |
| Month-stable +ROI? | **No.** Apr −0.2% / 77; May −2.2% / 71 |
| Max / day | **7** (Jun, Apr). Not “few” |
| Ship bar | **Fail.** Needs selective + month-stable +ROI + n≥40 + few/day |
| Tighten-only? | Empty. 2.0pp / 1.5pp / top-2 / pin-lean / home-only / away-only all leave Apr or May red. Public last-pre-commence is a hole (Aug **0** games) |
| PUBLISH | **Stays 0** in repo. Do not flip |

Park this family. Next hunt is a *different* construction, not another
neighbour of 1.8pp.

---

## Production as-of (what was measured)

Matches `models/mlb_game_market.load_latest_quotes` + `find_spread_bets`
+ the card’s `min_odds_for` floor (−200 default):

- `odds.snapshot_type = 'open'`
- `odds.snapshot_at::timestamptz <= games.commence_time` (evening-refresh leak bound)
- latest row per `(game_id, bookmaker)`
- Sharp = Pinnacle, two-way, run line only (`abs(|spread_home| − 1.5) < 1e-9`)
- Soft = `BEST_LINE_BOOKMAKERS` (pinnacle / bovada / espnbet excluded)
- Equal `spread_home`, simultaneous ≤300s
- Edge = Pin de-vig − soft de-vig; one bet per game = max edge
- Keep edge ≥ 1.8pp and American price ≥ −200
- Grade: home cover `(home − away) + scored_line > 0` (§4). Units from the
  taken American price. Pushes (margin 0) count 0, not in n_decided.

This is **not** first-open DK-only. That was the I24 trap (old +9.51u).
Worker job `mlb-game-line-market-sweep-open-bettable-2026-09-15` already
ran this family at **2.0 / 3.0 / 4.0pp** through 2026-09-16; the live
card is **1.8pp**, so 1.8 was remesured here. Worker 2.0pp monthly cells
replicated (May −3.15u / 47; Jul +3.53u / 28; Aug +6.70u / 41).

---

## Monthly grid — 1.8pp (the card)

Settled MLB 2026-04-01 → 2026-09-18. Full-month windows (snapshot pad
+2 days past month-end so a west-coast night quote is not clipped).

| month | n | units | ROI | W-L | max/day |
|---|---:|---:|---:|---|---:|
| Apr | 77 | −0.14 | −0.2% | — | 7 |
| May | 71 | −1.53 | −2.2% | — | 5 |
| Jun | 62 | +4.89 | +7.9% | — | 7 |
| Jul | 46 | +4.19 | +9.1% | — | 5 |
| Aug | 72 | +6.25 | +8.7% | — | 5 |
| Sep (through 18) | 40 | +2.09 | +5.2% | 23-17 | 5 |
| **Pooled** | **368** | **+15.75** | **+4.3%** | | **7** |

Aug +6.25u / 72 is the existing neighbourhood the prior hunt called
**+6.34u / 97** (looser n: no −200 floor and/or 1.5pp mix). Same sign,
same month, not a new edge.

Jul is not intra-month stable: 1–15 **+11.87u / 25**, 16–31 **−7.68u / 21**.

---

## Neighbourhood (not a peak hunt — honesty check)

| cut | Apr | May | Jun | Jul | Aug | Sep 1–18 | note |
|---|---|---|---|---|---|---|---|
| 1.5pp | 127 −10.22u | 123 −7.74u | 103 +11.50u | 80 +1.71u | 116 +17.73u | 76 +0.73u | Apr/May worse |
| **1.8pp** | **77 −0.14u** | **71 −1.53u** | **62 +4.89u** | **46 +4.19u** | **72 +6.25u** | **40 +2.09u** | card |
| 2.0pp | 49 −1.37u | 47 −3.15u | 41 +3.48u | 28 +3.53u | 41 +6.69u | 32 +6.34u | Sep n<40; Apr/May still red |

2.0pp Sep +6.34u / 32 is the closest *September* print. It does not
repair Apr/May and it fails n≥40 on the month that was supposed to
confirm the card.

---

## Tighten-only attempts (all miss)

| knob | Apr | May | rest | why it is not a ship |
|---|---|---|---|---|
| Top-2 / day by edge | 44 **−5.66u** | 53 **−7.16u** | Aug 48 +9.02u; Sep 29 +3.87u | Makes the red months redder |
| Pin-lean only (fair ≥ 0.5) | 38 **−10.90u** | — | — | Peak / anti-selective on the worst month |
| Home only | 33 +6.92u | 40 **−2.94u** | — | Side that wins April loses May |
| Away only | 44 **−7.06u** | 31 +1.41u | — | Inverse of home |
| Public / RLM overlay | — | — | — | Last-pre-commence public is a **hole** (below). No fill |

No knob is tighten-only *and* month-stable.

---

## Public / RLM coverage holes (do not invent)

`public_betting` consensus spreads, offset-aware
`snapshot_at < commence_time` (same trap as
`docs/mlb_market_handicap_features.md` / I24):

| month | MLB games | games with any public row | last-pre-commence |
|---|---:|---:|---:|
| Apr | 395 | 0 | **0** |
| May | 424 | 15 | **0** |
| Jun | 400 | 400 | 59 |
| Jul | 370 | 342 | 25 |
| Aug | 414 | 397 | **0** |
| Sep (through 18) | 239 | 239 | 39 |

August has 794 spread rows. **Zero** survive an offset-aware
pre-commence bound. A lexicographic `snapshot_at < commence_time`
fakes 208 — that is the leak, not coverage. May’s 15 rows are also
post-commence. **Do not join August public into a “tighten.”**

---

## Live first-signal vs last-pre-commence

Repo default `MLB_SPREAD_MARKET_PUBLISH` is **0**. Production `picks`
already holds **29** `mlb_spread_market` BETs (2026-09-16 → 19): the
worker is inserting (env on the box, not this PR). Those rows are
first-signal locks (§1c), not last-pre-commence.

Settled first-signal 2026-09-16…18 (price present; `profit_flat/100`):

| date | n | units |
|---|---:|---:|
| 16 | 2 | −0.09 |
| 17 | 9 | +2.64 |
| 18 | 13 | −2.90 |
| **16–18** | **24** | **−0.36** |

Same dates, last-pre-commence 1.8pp: **7** bets, **−1.52u**. First-signal
is thicker (13 on the 18th vs remesure max 5/day). The market often
corrects the disagreement before first pitch — the I24 lesson applied
to this card. Sep 19 (5 rows) was unsettled at remesure time.

This PR does **not** flip the env. Reporting the write is not permission
to set `PUBLISH=1`, and it is not permission to turn it off from here.

---

## Ship bar (applied)

Selective, month-stable +ROI, n≥40, max few/day.

- Sep n=40 just clears the count, +5.2% on the month.
- Apr and May are not +.
- Max 7/day is not a top-2 slate.
- Neighbours are not a plateau that is green in every month.
- Public overlay cannot be measured on August without inventing fills.

**Fail.** Closest miss is the card itself: season +4.3% / 368 with a
green late half and two red early months.

---

## What this is not

- Not a flip of `MLB_SPREAD_MARKET_PUBLISH`.
- Not an unpause of `mlb_runline` or any XGBoost id.
- Not I24 / `mlb_total_public_fade` (those guards and flags are
  untouched; I24 remesure is red on its own as-of — PR #760).
- Not permission to treat first-open or DK-only as this card.

Code for `mlb_spread_market` at 1.8pp stays. INSERT stays gated in
config. Park the family.
