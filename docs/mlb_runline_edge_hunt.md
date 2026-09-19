# MLB runline edge hunt (2026-09-19)

Standing search for a **stakeable** `mlb_runline` replacement that is not
an XGBoost unpause. Families: public fade RL, Pin-vs-soft aligned, RLM
dog, steam / anti-steam.

**This pass did not ship a paper publisher.** No cell was both selective
and month-stable at n≥40. The one technical clear (+1.2% / 42) is a
peak, not a plateau — September is red and the t65 neighbour loses.

`mlb_runline` stays in `PAUSED_MODELS`. Do **not** set
`MLB_SPREAD_MARKET_PUBLISH=1`. Do **not** register a live artifact.
Do **not** add a `mlb_runline_public_fade` id until a later pass beats
the tables below.

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
| Public fade RL | **Dead as a publisher.** Only n≥40 "clear" is fade-heaviest / fade-fav **t70 or t75 ticket top-2: +0.51u / 42 = +1.2%**. Jun +1.8%/23, Jul +1.2%/13, **Sep −1.0%/6**. Neighbour t65 top-2 is **−1.8%/50**. Juice band [−110, −100] is n=11 and red. |
| RLM dog | **Dead.** Every (tickets, money−tickets) cut is n<40 and/or red. Follow-money favorite also loses. |
| Pin-vs-soft aligned | **No new card.** Latest Pin-vs-DK *implied* lean ≥2pp is empty in June (0 bets). First-open same construction: 3 bets, −1.42u. GROK's ≥2pp Pin-open vs DK-open (~−5% / ~200) is a different pairing and stays the reason `MLB_SPREAD_MARKET_PUBLISH` is 0. Latest Pin-vs-DK *de-vig* ≥1.8pp: Jun **−3.36u / 28**, Jul **−4.08u / 34**. Aug BEST_LINE de-vig ≥1.8pp still **+6.34u / 97** — that is the existing `mlb_spread_market` paper card, not a new id. |
| Steam | **Dead.** DK open→latest home-implied move, equal ±1.5, follow ≥2pp: Apr −9.86/73, May −13.43/123, Jun **+4.86/92**, Jul −14.33/101, Aug −7.12/124. One green month. Fade ≥2pp is not the complement that prints (Jun fade −13.04). Sep steam timed out on MCP; Apr–Aug is enough. |

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
| 2026-09 | (MCP timeout) | | | | | |

June is a lone green month. Not month-stable.

---

## What this is not

- Not an unpause of `mlb_runline` / `mlb_over_under` / F5.
- Not `MLB_SPREAD_MARKET_PUBLISH=1` and not a new PUBLISH env.
- Not a live-artifact register.
- Not `mlb_total_public_fade` (totals OVER pile → UNDER). That card
  stays its own paper lane.
- Not permission to treat the +1.2% / 42 cell as I24-shaped. I24 on
  totals had three green months and a juice band; this cell has
  neither.

Next hunt, if any: worker remesure of BEST_LINE de-vig through
September (`game_line_market_sweep`), and only then a judgement on
whether the *existing* spreads card's neighbourhood still holds.
That is a remesure of `mlb_spread_market`, not a new model.
