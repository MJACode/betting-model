# MLB totals public-fade: ticket × juice × holdout grid

**Lane:** selective construction to replace blunt `mlb_total_public_fade`
(over tickets ≥70 → under on the whole slate). That card wrote **12/12**
UNDER BETs on 2026-09-19; those 12 rows are `condition_status='VOID'`.
`mlb_over_under` stays paused. `MLB_TOTAL_PUBLIC_FADE_PUBLISH` stays **0**.

Measured 2026-09-19 against production (`public_betting` ∩ `odds` ∩ `games`).
Code: `scripts/mlb_total_public_fade_grid.py`. Finder knobs (default off):
`MLB_TOTAL_PUBLIC_FADE_JUICE`, `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE`.

## Recommendation (one rule)

| Knob | Value |
|---|---|
| Over tickets | **≥ 90** |
| Under juice | **any** (do not filter) |
| Max bets / slate | **3** (highest over-ticket %, then better American) |

Do **not** set `MLB_TOTAL_PUBLIC_FADE_PUBLISH=1`. Do **not** unpause
`mlb_over_under`. Defaults in `config.py` stay 70 / any / unlimited so
this report does not silently recut the live card. To paper-run the
recommended rule on the worker after merge:

```
MLB_TOTAL_PUBLIC_FADE_TICKET_PCT=90
MLB_TOTAL_PUBLIC_FADE_JUICE=any
MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE=3
MLB_TOTAL_PUBLIC_FADE_PUBLISH=0
```

The existing slate guard (`models.slate_concentration`, suppress-all at
n_bet ≥ 4 and ≥70% one side) stays. Cap 3 keeps a day under that trip,
so a 15-game public-OVER board cannot write 12 unders again.

**This cell does not clear the requested bar** (n≥40 OOS and ROI≥+5%
and not one-month). No cell in the grid does. September scored hold is
34 games; August honest pre-commence rows are **zero**. The pick is the
only construction that (1) does not flood a complete slate, (2) is not
deeply negative on those complete days, and (3) does not use a juice
floor that made every month worse.

## Universe (rebuilt, not reused from the 2026-09-16 write-up)

Last pre-commence consensus totals OVER ∩ best same-line open under
among DK / FD / MGM / WH at **DK’s** open total, main 5.5–14.5, under
American in [−200, 200]. Offset-aware `snapshot_at < commence_time`.
`odds.snapshot_type='open'` and still leak-bounded
`snapshot_at <= commence_time`.

| | n |
|---|---|
| Consensus totals-over rows 2026-05-31→09-19 | 1,406 |
| Honest pre-commence | **136** (Jun 59, Jul 25, Aug **0**, Sep 52) |
| Shopped (DK open in window) | **135** |
| Scored (final home+away) | **120** |
| Unscored (Sep 18 late + Sep 19) | 15 |

Sep 19 quotes for the 12 voided games are the **locked pick**
book/line/price (MCP odds on that date timed out). Those 12 are
unscored, so they enter concentration only, not ROI.

Blind under on the same 120 scored games: **+1.2% / 61–54 / +1.41u**.
The ticket cut has to beat that.

### The 12/12 flood (production `picks`)

| Date | n | W-L-P | units | notes |
|---|---|---|---|---|
| 2026-09-16 | 15 | 7-8-0 | **−1.66** | t70 fired 15/15 |
| 2026-09-17 | 8 | 4-4-0 | **−0.32** | t70 fired 8/9 |
| 2026-09-18 | 14 | 4-6-1 (+3 open) | **−2.21** | t70 fired 14/15 |
| 2026-09-19 | 12 | — | 0 | **VOID**; t70 fired 12/13 |

That is the blunt rule on honest coverage: a board, not a cut.

## Why t70’s +8.5% did not survive

Public history is `UNIQUE(game_id, market, side, book)` — last upsert
wins. Hourly refresh overwrote most pre-game splits. Honest leftovers
are **20–30% of a June/July slate**. On those leftover games t70 is
**+17.2% / 58**. On **complete-coverage** days (public on ≥50% of the
slate: 2026-06-08, 06-15, 09-16, 09-17, 09-18, 09-19) t70 is
**−11.5% / 43** and fires **79–100%** of the slate (max 1.00).

June+July (the original window) t70/any: 47 +15.7% and 20 +15.0%.
September hold t70/any: 34 **−15.8%**. The plus was the overwrite
sample. Going forward the ingestor keeps pre-commence rows, so the
relevant regime is the complete-coverage one.

Mean concentration across *all* days (including 20% June leftovers)
is ~0.33 and would have passed a naive 50% filter. **Concentration is
evaluated on complete-coverage days**, which is the regime the card
will see.

## Grid (uncapped, any juice)

Train = Jun+Jul. Hold = Aug+Sep (August empty). Units are flat 1u.

| Cut | n | ROI | units | Jun | Jul | Sep | complete ROI | complete conc (mean/max) |
|---|---|---|---|---|---|---|---|---|
| t65/any | 106 | +4.5% | +4.83 | 50 +14.5% | 22 +13.5% | 34 **−15.8%** | −11.5% / 43 | 0.81 / 1.00 |
| **t70/any** | **101** | **+5.0%** | **+5.01** | 47 +15.7% | 20 +15.0% | 34 **−15.8%** | **−11.5% / 43** | **0.79 / 1.00** |
| t75/any | 94 | +4.7% | +4.38 | 46 +14.2% | 17 +1.4% | 31 −7.7% | −4.9% / 40 | 0.74 / 0.93 |
| t80/any | 81 | +7.1% | +5.76 | 37 +26.4% | 14 **−4.8%** | 30 −11.1% | −5.0% / 38 | 0.70 / 0.93 |
| t85/any | 63 | +6.2% | +3.92 | 29 +28.9% | 12 −4.5% | 22 −17.9% | −8.3% / 30 | 0.54 / 0.73 |
| **t90/any** | **40** | **+12.3%** | **+4.91** | 22 +30.3% | 4 −6.2% | 14 −10.7% | **+0.4% / 20** | **0.33 / 0.53** |

t90 is the only uncapped ticket cut that is not a loser on complete
days. It is still July-and-September negative; June carries the plus.
Complete-day max concentration 0.53 is just over the 50% reject on
one day (Sep 18, 8/15). That is why the cap is required.

## Juice filters — all fail

Same ticket cuts with under American ≥ −115 / −110 / −105 / plus-money.
Every juice floor is worse than `any` in full, in June, and in
September. t70/ge_m115: 86 −4.6%, Sep −28.2%. t70/plus: 18 −27.2%.
The original write-up’s “t70 and under ≥ −115 → +10.8% / 56” does not
reproduce on this last-pre-commence shop (that number was a different
quote clock and did not include September). **Juice is not the
selector.**

## Max-per-slate (highest tickets)

| Cell | n | ROI | Jun | Jul | Sep | mean/max conc |
|---|---|---|---|---|---|---|
| t85/cap3 | 44 | +11.0% | 24 +27.9% | 12 −4.5% | 8 −16.5% | 0.17 / 0.38 |
| **t90/cap3** | **33** | **+12.8%** | 21 +27.6% | 4 −6.2% | 8 −16.5% | **0.16 / 0.38** |
| t90/cap2 | 26 | +10.6% | | | 5 −61.8% | 0.13 / — |
| t90 + suppress-all (drop day if n≥4) | 25 | +6.2% | 18 +16.1% | 4 −6.2% | 3 −36.4% | 0.14 |

Cap 3 on t90: complete-day ROI **+1.8% / 14**, conc 0.26, max 0.38.
Neighbour t85/cap3 is the same complete-day number (the top-3 tickets
on a complete slate are almost all ≥90). Prefer 90 so a 15-game board
does not start from an 8-game t85 pile.

Cap 2 is a Sep peak-dive (−61.8% / 5). Suppress-all (already shipped)
refuses the fat Sep 17/18 t90 slates in full and leaves Sep 16’s 3
(1–2, −36%). Cap 3 is the one that still *takes* a selective under
on a busy day instead of writing nothing.

## Failures (do not ship)

| Construction | Why |
|---|---|
| t65–t85 uncapped | Complete-day conc 0.54–0.81, max 0.73–1.00. Sep −8 to −18%. The 12/12 shape. |
| Any juice floor | Full ROI flips negative or worse; Sep worse than `any`. |
| t90 + plus-money | n=9, −55%. |
| Ticket−money gap ≥5 | t80 n=15, hold n=4. Thin, not a plateau (t70 gap≥5 train −16%). |
| t90 and money ≥ tickets | **+22.6% / 14** (Jun 7 +36%, Sep 6 +27%, Jul 1 −100%). Both calendar halves plus, conc max 0.44. **Neighbour t85 money-confirm hold is −5.3% / 12** — a peak, not a plateau. Revisit at n≥25. |
| n≥40 OOS / ROI≥+5% OOS | Impossible on this window. Sep scored hold is 34; no cell is +5% there. |
| May–Jul / Aug–Sep as a clean hold | August honest rows = 0. Hold is four September days. |

## What this is not

- Not an unpause of `mlb_over_under` / `mlb_runline`.
- Not `mlb_total_market` (Pin fair − soft implied).
- Not permission to flip `MLB_TOTAL_PUBLIC_FADE_PUBLISH`.
- Not a claim that t90/cap3 is +EV out of sample. Complete-day is flat;
  July and September are negative; June is the plus. The claim is:
  **this is the only selective rule in the grid that does not recreate
  12/12**, and it should stay paper until more honest pre-commence
  days exist (the ingestor now refuses post-start upserts).

Remeasure when August-equivalent coverage exists — every complete
slate from 2026-09-16 onward is new evidence. Same script:

```
python -m scripts.mlb_total_public_fade_grid
```
