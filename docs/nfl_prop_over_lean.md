# NFL prop lines lean over, and that is where the stat-prop money is

*Measured 2026-09-12. mike: "I asked you to find evidence for stat models any way
you can... Figure it out. Find the solution."*

The eleven stat models were dead as PROJECTIONS — nine graded attempts, none
positive out of sample (`docs/nfl_prop_method_search.md`). This is the tenth
attempt and the first that pays, and it works by abandoning projection
altogether: **the market these models trade is itself biased toward the over,
and the bias is worth more than anything a projection ever added.**

---

## 1. The lean, with no model in the loop

`scripts/nfl_prop_over_lean.py`. Every NFL prop proposition 2023-25 with a
graded actual and at least three bettable books quoting: 27,976 of them, across
eight two-way markets. One bet per proposition, at the **best price across
`config.BETTABLE_BOOKS` at the same line**. No projection, no feature, no model
— the only inputs are which market it is and what the books are quoting.

| bet | bets | ROI | 90% CI |
|---|---|---|---|
| blind UNDER at the best price (2025) | 1,336 | −1.29% | (−5.2, +2.8) |
| blind OVER at the best price (2025) | 1,336 | **−7.91%** | (−11.9, −3.9) |
| blind UNDER at **DraftKings'** price (2025) | 720 | −6.48% | (−11.9, −1.2) |

Two things fall out at once.

**The under side is worth ~6.6pp more than the over side.** Both lose to the
hold, as a blind bet on a two-way market must; but they lose by very different
amounts, and the difference is the lean.

**Line shopping is worth 5.2pp on its own** (−6.48% at DraftKings against
−1.29% at the best of ~5.7 books). This is why the 2026-09-07 version of this
measurement (`scripts/nfl_prop_under_bias.py`) concluded "no market clears its
own vig": it graded at DraftKings' price, two days before the repo stopped
deciding at DraftKings (CLAUDE.md §6). It was measuring against a bar
production no longer has to clear.

## 2. The lean is in the LINE, not in the shopping

The obvious objection is that a widely-quoted proposition has more books to shop
and so a better price by construction. It does not survive the test. Grade the
same bets twice, once at the best bettable price and once at a **flat −110**:

| prominence tercile | under hit rate | ROI @ best price | ROI @ flat −110 |
|---|---|---|---|
| low (small line) | 49.7% | −4.06% | −5.05% |
| mid | 52.2% | −1.54% | −0.29% |
| high (big line) | **52.6%** | +0.22% | **+0.33%** |

Break-even at −110 is 52.4%. The gradient is essentially unchanged at a fixed
price, so it is a property of where the book puts the LINE, not of what we pay.

**It replicates in every season separately** — low ≤ mid ≤ high in 2023, in
2024 and in 2025, three independent times. The level moves between seasons
(2023-24 pooled −3.15%, 2025 +0.50%) but the ordering does not.

The mechanism is the documented one: recreational money buys overs, prop lines
get shaded up to absorb it, and the shading is biggest where the public money
is — on players with big numbers next to their name, quoted everywhere.

The top cell (big line AND widely quoted) is **+3.55% over 2,507 bets, CI
(−0.1, +7.2)** — positive in all three seasons, against a bottom-cell control of
−6.41%. On its own it grazes zero and is **not** shippable by §7's bar. It is
recorded because it is the mechanism's fingerprint, not because it is a bet.

## 3. Where it pays: the rule that already works was half an over bet

`models/nfl_prop_market` is the one NFL prop construction with a validated
record. Splitting its bets by side — a split the section above **predicted
before it was run** — shows its edge is almost entirely on one side.

At the shipped 5pp cut, `either` reference, 2023-25:

| side | bets | ROI | 90% CI | by season |
|---|---|---|---|---|
| over | 1,092 | +4.11% | (−0.8, +9.0) | +1.1 / +11.1 / +2.1 |
| **under** | **898** | **+12.36%** | **(+7.2, +17.5)** | +12.6 / +4.9 / +21.1 |

And the two sides respond to the cut in opposite ways — exactly as a line lean
predicts, since an over must overcome it and an under is carried by it:

| cut | over ROI | under ROI |
|---|---|---|
| 5pp | +4.11% | +12.36% |
| 6pp | +15.80% | +13.52% |
| 7pp | +20.50% | +12.24% |

The under curve is flat; the over curve climbs monotonically. So the under side
keeps its pre-committed 5pp and the over side is held to 6pp.

Replicated in DIRECTION at three independent snapshot offsets (unders minus
overs): `open` +8.3pp, `t48` +5.2pp, `t72` +2.2pp.

## 4. What shipped

`config.NFL_PROP_MARKET_SIDE_EDGE = {"over": 0.06, "under": 0.05}`, applied by
`models/market_relative.find_bets` through an **opt-in** `min_edge_by_side`
argument that can only tighten, never loosen. The WNBA, MLB and NCAAF ports of
the same rule pass nothing and are untouched — CLAUDE.md §1b: the mechanics are
shared, the cuts are measured per model and never copied.

Graded end to end (`nfl_prop_two_sharps --min-edge 0.05 --over-edge 0.06`):

| | bets | units | ROI | 90% CI | 2023 / 2024 / 2025 |
|---|---|---|---|---|---|
| shipped, one floor | 1,990 | +155.9 | +7.84% | (+4.3, +11.4) | +6.4 / +8.2 / +10.1 |
| **paired floors** | **1,248** | **+166.3** | **+13.33%** | **(+8.9, +17.8)** | **+13.2 / +12.6 / +14.5** |

**More profit from 742 fewer bets**, so this is not a volume-for-ROI trade. The
season spread also tightens, from 3.7pp to 1.9pp.

## 5. What is fitted, and what the downside is

Stated plainly, because §7 exists for exactly this.

- **The mechanism is not fitted.** It was measured first, on a different and
  much larger population (27,976 propositions vs 1,990 bets), with no model in
  the loop, and it predicted the direction of the side split before the split
  was run. It replicates in three seasons and at three offsets.
- **The number 6 is fitted.** It is chosen off the same grid it is quoted on.
- **The bound on being wrong**: if the over cut is pure curve-fitting, overs
  revert to their 5pp behaviour of +4.11%, and the pairing still returns
  ~+10.0% on 1,248 bets — better ROI than the single floor, fewer units.
- **The cell that argues against it**: 2025 overs at 6pp are −4.2% on 73 bets,
  while 2025 overs at 5pp are +2.1% on 283. On the newest season, tightening the
  overs made them worse. 73 bets is thin, and the pooled and per-season totals
  are positive anyway, but it is the one reading pointing the other way.
- **Re-measure on 2026 settled bets.** `docs/followups.md` carries it.

## 6. What this does NOT rescue

The eleven stat models still have no evidence for them as projections. This
finding says their MARKET is biased, not that their MODELS are right — and in
fact it explains their year of near-break-even mediocrity: they bet ~87% unders
(`docs/nfl_prop_method_search.md` §5a), which is the correct direction, at
DraftKings' price, which is the worst execution. They were accidentally betting
this lean and paying 5.2pp of shopping away to do it.

The blind version of that bet is still not profitable (−1.29% at the best
price). What is profitable is the lean **combined with a sharp reference**,
which is `nfl_prop_market` — and that is now cut per side.

## Reproducing

```bash
python -m scripts.nfl_prop_over_lean                      # the lean, no model
python -m scripts.nfl_prop_lean_concentration             # where it concentrates
python -m scripts.nfl_prop_lean_gradient                  # line vs price, per season
python -m scripts.nfl_prop_two_sharps --min-edge 0.05 --snapshot open --by-side
python -m scripts.nfl_prop_two_sharps --min-edge 0.05 --over-edge 0.06 --snapshot open
```

Zero Odds API credits: every input is already in `data/local`.
