# MLB runline edge hunt (2026-09-19)

Standing search for a **stakeable** `mlb_runline` replacement that is not
an XGBoost unpause. Families: public fade RL, Pin-vs-soft aligned, RLM
dog, steam / anti-steam.

**This pass did not ship a paper publisher.** No cell was both selective
and month-stable at n≥40 **and** a neighbourhood, not a peak. The ticket
fade +1.2% / 42 is a peak (Sep red, t65 neighbour loses). Money-heavy
top-3 at m70/m75/m80 is a **K-peak** (top-2 and top-4 go Sep-red).
Public × steam overlays that print three green months are n<40.

`mlb_runline` stays in `PAUSED_MODELS`. Do **not** set
`MLB_SPREAD_MARKET_PUBLISH=1`. Do **not** register a live artifact.
Do **not** add a `mlb_runline_public_fade` id. **Deliverable B** — empty
report; the owner can chain `mlb_over_under` next.

Sweep: `python -m scripts.mlb_runline_edge_hunt`
(DB) or `--json` of the Supabase rows this session pulled.

As-of: public `snapshot_at < commence_time` (offset-aware);
odds `snapshot_type='open'` and `snapshot_at <= commence_time`.
Prices shopped DK/FD/MGM/WH at DK's open ±1.5, American in [−200, 200].
Flat 1 unit. `scored_line` is the HOME number (§4).

---

## Coverage (measured 2026-09-19)

`public_betting` spreads-home consensus, 2026-05-31 → 2026-09-19:

| Month | Any row | Pregame | Pregame settled |
|---|---:|---:|---:|
| 2026-05 | 15 | 0 | 0 |
| 2026-06 | 400 | 59 | 59 |
| 2026-07 | 342 | 25 | 25 |
| 2026-08 | 397 | 0 | 0 |
| 2026-09 | 254 | 54 | 39 |
| **total** | | **138** | **123** |

August is empty — last-upsert overwrite, same trap as
`docs/mlb_total_public_fade.md`. Two 2026-07-01 rows with home tickets
100 and away tickets 99 were dropped as Action Network garbage
(`home+away` far from 100). Board after DK ±1.5 shop: **119** games.

Pin / steam families use the full 2026 odds book, not this 119.

---

## Verdict by family

| Family | Verdict |
|---|---|
| Public fade RL (tickets) | **Dead as a publisher.** Only n≥40 "clear" is fade-heaviest / fade-fav **t70 or t75 ticket top-2: +0.51u / 42 = +1.2%**. Jun +1.8%/23, Jul +1.2%/13, **Sep −1.0%/6**. Neighbour t65 top-2 is **−1.8%/50**. Juice band [−110, −100] is n=11 and red. |
| Money-heavy fade | **Dead as a publisher.** All-pass m75 **+4.42u / 59 = +7.5%** and m80 **+2.45u / 48 = +5.1%** are three-month green but max/day is 6 and 5 (bar is ≤4). **top-3** at m70/m75/m80 is a mechanical CLEAR (n=57/51/44, every month +, max/day=3) and a **K-peak**: top-2 and top-4 go Sep-red at the same cuts. m85 top-3 is n=38. Not shipped. |
| Home-dog | **Dead.** Same population as fade-away once the home number is +1.5. Jul −50% to −74%. |
| RLM dog | **Dead.** Every (tickets, money−tickets) cut is n<40 and/or red. Follow-money favorite also loses. |
| Public × steam | **Dead.** Fade-public when steam opposes is n≤16. Follow-steam any t65 ≥3pp is **+4.33u / 20** three-month green — n<40. Fade-public any t80 ≥1pp top-2 is **+6.03u / 26** three-month green — n<40. Neighbour t75 top-2 is Sep-red. |
| Pin-vs-soft aligned | **No new card.** Latest Pin-vs-DK *implied* lean ≥2pp is empty in June (0 bets). First-open same construction: 3 bets, −1.42u. GROK's ≥2pp Pin-open vs DK-open (~−5% / ~200) is a different pairing and stays the reason `MLB_SPREAD_MARKET_PUBLISH` is 0. Latest Pin-vs-DK *de-vig* ≥1.8pp: Jun **−3.36u / 28**, Jul **−4.08u / 34**. Aug BEST_LINE de-vig ≥1.8pp still **+6.34u / 97** — that is the existing `mlb_spread_market` paper card, not a new id. Sep BEST_LINE timed out on MCP (week chunk, same as the first pass). |
| Steam | **Dead.** DK open→latest home-implied move, equal ±1.5, follow ≥2pp: Apr −9.86/73, May −13.43/123, Jun **+4.86/92**, Jul −14.33/101, Aug −7.12/124, **Sep −12.39/87 = −14.2%** (1–9 −4.00/39, 10–14 +0.19/24, 15–19 −8.58/24). One green month (June). Sep fade ≥2pp was +5.73u / 87 and does not rescue Apr–Aug. |

---

## Public fade RL (119-game board)

Fade the named pile, bet the other runline side. Top-K ranks by the
faded ticket pile, cap 2 per `game_date`.

| Construction | n | Units | ROI | Jun | Jul | Sep |
|---|---:|---:|---:|---:|---:|---:|
| fade heaviest t70 all-pass | 71 | −3.56 | −5.0% | +4.5%/30 | −11.8%/17 | −12.2%/24 |
| **fade heaviest t70 top-2** | **42** | **+0.51** | **+1.2%** | **+1.8%/23** | **+1.2%/13** | **−1.0%/6** |
| fade heaviest t65 top-2 | 50 | −0.88 | −1.8% | −1.8%/29 | −2.1%/15 | −1.0%/6 |
| fade heaviest t80 top-2 | 36 | +1.50 | +4.2% | +4.8%/19 | +5.9%/11 | −1.0%/6 |
| fade heaviest t90 top-2 | 17 | +3.14 | +18.5% | −0.8%/6 | +17.9%/7 | +48.5%/4 |
| fade fav t70 top-2 | 42 | +0.51 | +1.2% | same 42 as heaviest | | |
| fade home t60 all-pass | 49 | +1.58 | +3.2% | +13.0%/26 | +22.5%/12 | **−41.0%/11** |
| fade public ∩ Pin-agree t70 | 54 | −1.16 | −2.2% | +12.4%/26 | **−43.8%/12** | +5.3%/16 |
| t70 juice [−110, −100] | 11 | −1.32 | −12.0% | −3.8%/6 | +100%/1 | −52.3%/4 |

Why the +1.2% cell is not a publisher:

1. **September is red.** "2+ months green" is Jun+Jul only.
2. **Neighbourhood fails.** t65 top-2 (same rank, looser pile) is −1.8%.
3. **n=42 on three partial months**, August missing. Wilson on 23–19 is
   wide.
4. Fade-fav t70 top-2 is the **same 42 bets** — not a second signal.

---

## Money-heavy fade and home-dog (same 119)

Fade the **money** pile (not tickets). Rank by that pile.

| Construction | n | Units | ROI | Jun | Jul | Sep | max/day |
|---|---:|---:|---:|---:|---:|---:|---:|
| fade money m75 all-pass | 59 | +4.42 | +7.5% | +13.4%/26 | +0.5%/18 | +5.6%/15 | **6** |
| fade money m80 all-pass | 48 | +2.45 | +5.1% | +9.5%/21 | +0.4%/15 | +3.3%/12 | **5** |
| **fade money m70 top-3** | **57** | **+4.60** | **+8.1%** | **+11.1%/31** | **+6.5%/17** | **+0.8%/9** | **3** |
| **fade money m75 top-3** | **51** | **+5.65** | **+11.1%** | **+13.4%/26** | **+13.1%/16** | **+0.8%/9** | **3** |
| **fade money m80 top-3** | **44** | **+3.13** | **+7.1%** | **+9.5%/21** | **+7.5%/14** | **+0.8%/9** | **3** |
| fade money m75 top-2 | 42 | +2.68 | +6.4% | +6.6%/23 | +12.2%/13 | **−7.1%/6** | 2 |
| fade money m75 top-4 | 56 | +2.29 | +4.1% | +13.4%/26 | +0.5%/18 | **−10.7%/12** | 4 |
| fade money m85 top-3 | 38 | +2.50 | +6.6% | +9.2%/18 | +3.7%/13 | +5.1%/7 | 3 |
| home-dog fade-away t65 | 41 | −0.95 | −2.3% | +4.3%/18 | **−57.9%/8** | +19.4%/15 | 7 |

Why top-3 is not a publisher (same bar that refused +1.2%/42):

1. **K-neighbourhood fails.** top-2 and top-4 at m75 (and m70/m80) are
   September-red. Only K=3 keeps Sep green at n≥40.
2. **July at the looser all-pass is +0.5% / 18** (m75) and **−4.7% / 19**
   (m70). top-3 manufactures the July print by dropping the 4th+ bet on
   busy days.
3. All-pass m75/m80 *do* have three green months and fail **max/day ≤ 4**.
   Raising the cap to 5–6 to keep them is not a selective rule.
4. August missing. Wilson on Sep 9 and Jul 16–18 is wide.

Home-dog is fade-away on DK +1.5. July is a wipeout.

---

## Public × steam overlay (119-game board, all 119 have move_pp)

DK open→latest home-implied move attached to the public board. Prices
stay the shopped open (same as fade_public_side). Steam is a direction
and magnitude filter. `oppose` + fade-public is the same side as
`oppose` + follow-steam.

| Construction | n | Units | ROI | Months |
|---|---:|---:|---:|---|
| fade-public oppose t65 ≥1pp | 16 | +3.74 | +23.4% | Jun +36.5%/11, Jul +2.5%/3, **Sep −17.5%/2** |
| fade-public any t80 ≥1pp top-2 | 26 | +6.03 | +23.2% | Jun +16.4%/11, Jul +34.9%/10, Sep +14.8%/5 (n<40) |
| fade-public any t65 ≥1pp top-2 | 40 | +7.91 | +19.8% | Jun +16.6%/22, Jul +37.7%/12, **Sep −4.4%/6** |
| follow-steam any t65 ≥3pp | 20 | +4.33 | +21.7% | three months + (n<40) |
| follow-steam agree t65 ≥3pp | 13 | +3.39 | +26.1% | three months + (n<40) |

Every overlay that is month-stable is under the n≥40 bar. Every overlay
that reaches n≥40 has a red September.

---

## RLM dog (same 119)

Classic board: favorite tickets ≥ cut and `fav_money − fav_tickets ≤ gap`,
bet the dog.

| Construction | n | Units | ROI | Months |
|---|---:|---:|---:|---|
| t55 rlm≤−5 | 30 | −0.20 | −0.7% | Jun +1.1%/12, Jul −37.1%/5, Sep +11.7%/13 |
| t65 rlm≤−5 | 25 | +0.02 | +0.1% | Jul −100%/2 |
| t70 rlm≤−5 | 20 | +0.26 | +1.3% | n<40 |
| t80 rlm≤−5 | 13 | +0.36 | +2.8% | n<40 |
| t55 rlm≤−10 | 17 | −0.22 | −1.3% | |
| t70 rlm≤−10 | 10 | −2.76 | −27.6% | |
| follow-money fav t55 rlm≥5 | 31 | −4.76 | −15.3% | all three months red |

No RLM cut clears n≥40. Tightening the gap makes it worse, not better.

---

## Pin-vs-soft (full 2026 odds)

Equal ±1.5, leak-bounded open, price window [−200, 200].

**Implied lean (Pin no-vig side minus DK juiced implied):**

| Pairing | Window | ≥2pp n | Units |
|---|---|---:|---:|
| latest Pin ∩ latest DK | 2026-06 | **0** | — |
| first-open Pin ∩ first-open DK | 2026-06 | 3 | −1.42 |

GROK's month table (Apr −15.9%/23 … Aug +5.7%/57, pooled ~−5% / ~200)
used a pairing this pass cannot reproduce from first-or-latest equal
lines. It remains the documented reason the existing spreads card
does not INSERT.

**De-vig (Pin fair − soft fair), one bet per game = largest edge:**

| Soft set | Month | ≥1.8pp n | Units | ROI |
|---|---|---:|---:|---:|
| DK only | 2026-06 | 28 | −3.36 | −12.0% |
| DK only | 2026-07 | 34 | −4.08 | −12.0% |
| BEST_LINE (DK/FD/MGM/WH) | 2026-08 | 97 | +6.34 | +6.5% |

August BEST_LINE still prints — that is `mlb_spread_market` at 1.8pp,
already wired, INSERT gated 0. DK-only is not a substitute. September
BEST_LINE timed out on MCP this pass; remesure on the worker with
`python -m scripts.game_line_market_sweep --sport MLB --market spreads --bettable --by-month`.

---

## Steam (DK open → latest, equal ±1.5)

`move_home_pp` = 100 × (latest juiced home implied − first juiced home
implied). Follow bets the steamed side; fade bets the other.

| Month | follow ≥2pp n | Units | ROI | fade ≥2pp units | follow ≥3pp n | Units |
|---|---:|---:|---:|---:|---:|---:|
| 2026-04 | 73 | −9.86 | −13.5% | +3.77 | 34 | −8.51 |
| 2026-05 | 123 | −13.43 | −10.9% | −2.72 | 50 | +2.61 |
| 2026-06 | 92 | **+4.86** | **+5.3%** | −13.04 | 47 | +1.31 |
| 2026-07 | 101 | −14.33 | −14.2% | +3.92 | 63 | −5.72 |
| 2026-08 | 124 | −7.12 | −5.7% | −0.59 | 74 | +0.52 |
| 2026-09 | 87 | **−12.39** | **−14.2%** | +5.73 | | |

September follow ≥2pp by week (same as-of bound, last line ±1.5, last
prices in [−200, 200]): 1–9 **−4.00u / 39**, 10–14 **+0.19u / 24**,
15–19 **−8.58u / 24**. June is a lone green month. Not month-stable.

---

## What this is not

- Not an unpause of `mlb_runline` / `mlb_over_under` / F5.
- Not `MLB_SPREAD_MARKET_PUBLISH=1` and not a new PUBLISH env.
- Not a live-artifact register.
- Not `mlb_total_public_fade` (totals OVER pile → UNDER). That card
  stays its own paper lane.
- Not permission to treat the +1.2% / 42 cell **or** money-heavy top-3
  as I24-shaped. I24 on totals is tickets≥80, under American
  [−110, −100], max 2/slate — **untouched** this hunt (`config.py` and
  `models/mlb_total_public_fade.py` are byte-identical to
  `origin/master`).
- Not a new PUBLISH env. Any later card defaults PUBLISH=0.

**Next for the owner:** chain `mlb_over_under` (same constraints: no
XGBoost unpause, no PUBLISH=1 without Michael OK, I24 guards stay).
Worker remesure of BEST_LINE de-vig through September
(`game_line_market_sweep`) remains a remesure of the *existing*
`mlb_spread_market` card, not a new model. Sep BEST_LINE timed out on
MCP again this pass.
