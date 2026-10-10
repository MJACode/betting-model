# MLB totals: the search for a second betting rule (2026-09-19)

> **Provenance.** From PR #759 (2026-09-19, never merged), carried to
> master 2026-10-10 as a write-up only; its 1,029-line measurement script
> and tests were not kept. On 2026-09-19 the search had only three days of
> September with a public split taken before first pitch, so where the
> whole season has since been measured, this page gives the whole-season
> figure and says so. Figures marked **2026-09-19** are the PR's and were
> not re-run.

**The question.** Is there a bettable MLB totals rule other than the
public-over fade (`docs/mlb_total_public_fade.md`)? `mlb_over_under` was
paused; this looked at rules built on market data instead of a trained
model.

**The answer: no.** Nothing met the bar, and the full September made the
closest misses worse, not better. No model, cut or publish switch was
changed.

**The bar** (the same one the run-line search used,
`docs/mlb_runline_edge_hunt.md`): at least 40 bets; at least two months
with bets, and every one of them positive; positive overall; at most 4 bets
a day; and not a lone good setting whose neighbours fail (for example, a
top-3-a-day rule whose top-2 and top-4 versions lose). August counts as
missing, not red: its pre-game public splits were overwritten.

**Coverage.** Games with a consensus totals split taken before first
pitch, re-counted 2026-10-10: Jun 59, Jul 25, Aug 0, Sep 154, Oct 17; 252
with a final score. On 2026-09-19 it was 123 settled games, 39 of them in
September.

---

## What was tried

| Approach | Result | Measured |
|---|---|---|
| Fade the public over (bet the under), 70% of tickets, every game | 214 bets, **−3.1%**. Jun +15.8% on 47, Jul +15.0% on 20, **Sep −12.9% on 138**, Oct +6.9% on 9 | 2026-10-10, whole season |
| Same, the two heaviest over piles a day, 70% | 78 bets, −1.4%. **Sep −27.6% on 27** | 2026-10-10, whole season |
| Same, top 2 a day, 80% | 69 bets, +3.0%. Jun +29.4% on 25, Jul +4.1% on 11, **Sep −27.6% on 27**, Oct +28.8% on 6 | 2026-10-10, whole season |
| The narrow price band on the under, −110 to −100 (I24), as the live card builds it | 49 bets, **−12.6%** | 2026-10-10; detail in `docs/mlb_total_public_fade.md` |
| Ticket share combined with price bands (for example under priced −120 to −100, top 2 a day) | June and July positive, September red in every version with 40 or more bets | 2026-09-19 |
| Fade the money share instead of the ticket share (80%, top 2 a day) | 45 bets, +9.9%: Jun +16.5% on 26, Jul +18.5% on 13, **Sep −37.1% on 6** | 2026-09-19 |
| Fade the public under (bet the over) | Too thin to test. The highest under-ticket share on the board all season is 59% (one June game); 19 games all season have 40% or more on the under | 2026-10-10 |
| Reverse line movement, or follow the money | 20 bets or fewer in every setting, months mixed | 2026-09-19 |
| Pinnacle's no-vig price against a soft book's raw price (with its margin), both quotes within 300 seconds, same total | **No bets**: the gap never reaches 1.5 points (June, July and Sep 16-18) | 2026-09-19 |
| Pinnacle's no-vig price against a soft book's no-vig price, 1.8 points or more, within 300 seconds | Jun +16.2% on 17, Jul +8.8% on 30, **whole of September −22.4% on 31** (−6.93u) | June and September re-measured in the 2026-10-10 review of PR #759; July is the PR's |
| DraftKings line moves (steam), followed or faded | No setting with 40 or more bets was positive in both June and July. September was not measured (the query timed out) | 2026-09-19 |
| Public split combined with a line move | 35 games had an equal-line move; no setting reaches 40 bets | 2026-09-19 |

**The earlier Pinnacle totals figure.** The 2026-09-15 search
(`docs/mlb_runline_ou_edge_search.md`) called Pinnacle against DraftKings
on totals, about +11% on about 103 bets, the "leading" totals replacement.
PR #759 found that the gap came from pairing each book's latest quote
with no limit on how far apart the two were taken, so the prices could be
hours apart. With the two quotes required to be within 300 seconds of each
other, the gap it bet on does not occur (the "no bets" row above), and the
no-vig version lost the whole of September. A correction is in that file.

---

## What was not changed

- `mlb_over_under` and `mlb_runline` stay paused.
- No change to the public-fade settings or to any publish switch.
- No new model was added: nothing met the bar.
