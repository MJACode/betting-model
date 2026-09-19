# MLB over/under edge hunt (2026-09-19) — empty

Same bar as the runline hunt (#757, failed). **No construction cleared.**
`mlb_over_under` and `mlb_runline` stay paused. I24
(`mlb_total_public_fade` at tickets≥80, under American [−110, −100],
max 2 / RANK=ticket) is **not recut** and is **not weakened**. No
`PUBLISH=1`. No paper publisher was added — there is nothing to
paper-publish.

Measure: `python -m scripts.mlb_over_under_edge_hunt`
(sandbox: `--json` cache of the Supabase pull). Tests:
`tests/test_mlb_over_under_edge_hunt.py`.

## The bar (identical to #757)

A cell **CLEAR**s when **all** of:

- n ≥ 40
- at least two populated months, **every** populated month ROI > 0
- overall ROI > 0
- max bets / day ≤ 4

Jun+Jul green / Sep red is a peak (the #757 +1.2%/42 public top-2).
A K-peak (only one K works) is refused the same way. August public
pre-commence is empty (last-upsert overwrite) and does not count as a
red month.

I24 is labelled on the grid as **live, not new**. A CLEAR that *is*
I24 is not a ship from this hunt.

## Coverage (Supabase, 2026-09-19)

| Board | n | Months | Bound |
|---|---|---|---|
| Public totals-over ∩ under, `snapshot_at < commence`, settled | **123** | Jun 59 / Jul 25 / Sep 39 / Aug **0** | offset-aware |
| Leak-bounded opens on that public board (DK/FD/MGM/WH/Pin, latest `open` ≤ commence) | **615** quotes / 123 games | same | `snapshot_type='open'` |
| Pin/soft latest-per-book opens (full slate) | **3,752** quotes / 755 games | Jun 378 + Jul 338 + Sep 16–18 39 | same; Sep 1–15 MCP timed out |
| DK first→last steam (equal-line juice + number move) | **712** | Jun 378 + Jul 334 | Sep steam MCP timed out even on the 39 public games |

Public × juice-steam overlay attached on **35 / 123** public games
(equal line only). A line change is the steam-number family, not this
overlay.

Worker / Matt can omit `--json` and load live (`load_db` month-chunks
the pin/steam scans). Sep steam and Sep 1–15 pin are the two holes a
worker re-run would fill; **Jun+Jul steam already produced no CLEAR**,
and every pin-devig cell that reached n≥40 went red in the Sep 16–18
window we do have.

## Verdict

| Family | Verdict |
|---|---|
| Public-over fade beyond I24 | **Empty.** Whole-slate and ticket top-K print +ROI on Jun+Jul and **Sep red** (same shape as #757). |
| Ticket × juice bands | **Empty.** I24-band itself is red on this window. Wider [−120, −100] top-2 is a Jun+Jul peak. |
| Public-under fade (bet OVER) | **Empty / thin.** Max under tickets on the board is 59. t40 n=11. |
| RLM / follow-money | **Empty / thin.** Best fade-over RLM is n=20, Jul −100% when Jun+Sep are green. |
| Pin-vs-soft, 300s, equal line | **Empty.** Pin-vs-soft *implied* ≥1.5pp is **n=0** (the earlier ≥2pp print was look-ahead). Pin-devig ≥1.8pp n=52 +8.4% is Jun+Jul green / Sep −20.6%/5. |
| Steam / anti-steam | **Empty.** Jun+Jul only; no n≥40 cell is green in both months. |
| Public × steam overlay | **Empty / thin.** 35 equal-line moves; no cell reaches n=40. |

**Do not unpause `mlb_over_under`.** **Do not set any `PUBLISH=1`.**
**Do not loosen I24.**

## I24 on this board (live, not a recut)

The hunt labels I24 as `t80 + [-110,-100] top-2 (live, not new)`.

| Window | n | Units | ROI | Months |
|---|---|---|---|---|
| I24 claim in `docs/mlb_total_public_fade.md` (2026-09-16 board) | 38 | +9.51u | +25% | Jun / Jul / Sep all + |
| **This hunt, settled public ∩ shopped open through 2026-09-18** | **22** | **−2.67u** | **−12.2%** | Jun −3.0%/12, Jul −22.6%/5, Sep −23.6%/5 |

That is **not** permission to recut I24. The live Railway card
(`TICKET_PCT=80`, band [−110, −100], `MAX_PER_SLATE=2`) stays where
I24 left it. Repo defaults stay `TICKET_PCT=70`, `MAX=0`, band unset,
`PUBLISH=0`. This hunt does not write those envs.

## Representative cells (not a ship list)

Prices are the shopped soft **open** (DK/FD/MGM/WH, same line as DK,
juice window [−200, 200]). Flat 1 unit. `scored_line` is the posted
total. Public rows require `snapshot_at < commence_time`.

### Public-over fade (bet UNDER)

| Cell | n | ROI | max/day | Months | Why not CLEAR |
|---|---|---|---|---|---|
| t70 all-pass | 104 | +2.8% | 15 | Jun +15.8%/47, Jul +15.0%/20, Sep −20.3%/37 | slate spam + Sep red |
| t70 ticket top-2 | 48 | +7.4% | 2 | Jun +15.5%/28, Jul +9.8%/14, Sep −36.4%/6 | Sep red (#757 shape) |
| t80 ticket top-2 | 42 | +13.4% | 2 | Jun +29.4%/25, Jul +4.1%/11, Sep −36.4%/6 | Sep red |
| t80 ticket top-3 | 52 | +13.5% | 3 | Jun +27.3%/30, Jul +2.5%/13, Sep −16.5%/9 | Sep red |
| t90 all-pass | 41 | +11.6% | 8 | Jun +30.3%/22, Jul −6.2%/4, Sep −11.1%/15 | Jul+Sep red, max/day 8 |
| I24 t80+[−110,−100] top-2 | 22 | −12.2% | 2 | all three red | live, not new; n<40 |
| fade-over-money m80 top-2 | 45 | +9.9% | 2 | Jun +16.5%/26, Jul +18.5%/13, Sep −37.1%/6 | Sep red |
| fade-over ∩ Pin-under t70 300s | 11 | −14.2% | 5 | Sep only | n thin, red |

### Ticket × juice

| Cell | n | ROI | max/day | Months | Why not CLEAR |
|---|---|---|---|---|---|
| t70 I24-band all-pass | 54 | −15.2% | 9 | Jun −15.4%/23, Jul +6.1%/11, Sep −26.7%/20 | red months |
| t70 [−120,−100] top-2 | 46 | +15.7% | 2 | Jun +26.7%/27, Jul +2.4%/13, Sep −5.3%/6 | Sep red |
| t80 [−120,−100] top-2 | 40 | +23.2% | 2 | Jun +42.5%/24, Jul −5.9%/10, Sep −5.3%/6 | Jul+Sep red |
| t90 [−120,−100] all-pass | 34 | +23.3% | 7 | Jun +38.0%/18, Jul −6.2%/4, Sep +11.1%/12 | n<40, Jul red, max/day 7 |

### Public-under fade / RLM

| Cell | n | ROI | Months | Why not CLEAR |
|---|---|---|---|---|
| fade-under t40 all-pass | 11 | −4.5% | Jun −44.8%/7, Jul +86.6%/2, Sep +45.5%/2 | n=11 |
| fade-under t55 | 1 | +90.9% | Jun only | one bet |
| RLM fade-over t80 rlm≤−5 | 15 | +15.7% | Jun +28.7%/9, Jul −100%/2, Sep +44.5%/4 | n=15, Jul red |
| follow-money over t70 rlm≥5 | 18 | −14.3% | Jun −68.2%/6, Jul −51.2%/4, Sep +44.6%/8 | red |

### Pin-vs-soft (300s, equal `total_line`)

A pair is refused when `|pin.snap − soft.snap| > 300s`. Latest-per-book
without that cap is the look-ahead that manufactured the earlier ≥2pp.

| Cell | n | ROI | max/day | Months | Why not CLEAR |
|---|---|---|---|---|---|
| pin-implied (lean or any) ≥1.5–3.0pp | 0 | — | — | — | no 300s pair reaches 1.5pp vs juiced implied |
| pin-devig lean ≥1.5pp | 83 | −4.5% | 6 | Jun +9.8%/28, Jul −8.8%/51, Sep −50.5%/4 | Jul+Sep red |
| pin-devig ≥1.8pp | 52 | +8.4% | 4 | Jun +16.2%/17, Jul +8.8%/30, Sep −20.6%/5 | Sep red |
| pin-devig ≥2.0pp | 44 | +6.0% | 4 | Jun +22.3%/13, Jul +9.7%/28, Sep −100%/3 | Sep red |
| pin-devig ≥2.5pp | 10 | +21.2% | 2 | Jun +35.7%/3, Jul +15.0%/7 (no Sep) | n=10 |

`mlb_total_market` (Pin fair − soft implied, INSERT off) is a
different card and is not unpaused here. This 300s remeasure says the
look-ahead ≥2pp vs *implied* is gone; the honest 300s *devig* print
does not survive September.

### Steam (Jun+Jul only)

Open price is the **first** DK open, so steam is not look-ahead.

| Cell | n | ROI | max/day | Months | Why not CLEAR |
|---|---|---|---|---|---|
| juice follow ≥1pp | 152 | −6.2% | 7 | Jun −4.5%/83, Jul −8.3%/69 | both red |
| juice fade ≥1pp | 152 | −2.1% | 7 | Jun −3.5%, Jul −0.5% | both red |
| number follow ≥0.5 runs | 386 | −5.7% | 11 | both red | slate |
| number follow ≥1.0 top-2 | 50 | +0.8% | 2 | Jun −7.0%/26, Jul +9.2%/24 | Jun red |
| number follow ≥1.5 runs | 6 | +24.8% | 1 | Jun +87%/1, Jul +12.4%/5 | n=6 |

Public × steam overlay (35 equal-line moves): fade-public oppose
t70 ≥1pp is n=9 +28.6% (Jun+Jul only). No overlay cell reaches n=40.

## What was deliberately not done

- No edit to `config.PAUSED_MODELS` (`mlb_over_under`, `mlb_runline`).
- No `MLB_TOTAL_PUBLIC_FADE_*` default change, no I24 recut, no
  `PUBLISH=1` on any totals card.
- No paper publisher (nothing cleared).
- No runline cells (that hunt is #757).
- Sep steam / Sep 1–15 pin left to a worker re-run of this same
  script; they are not required to call the hunt empty.

## Reproduce

```
python -m scripts.mlb_over_under_edge_hunt
python -m scripts.mlb_over_under_edge_hunt --json /tmp/ou_hunt.json
python -m pytest -q tests/test_mlb_over_under_edge_hunt.py
```
