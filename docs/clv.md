# Closing line value (CLV)

The formula, the book, and the worked example. Capture lives in
`tracking/paper_tracker.py` (`_capture_clv` / `_backfill_clv`); the arithmetic
is `tracking/clv_math.py`. This is a grade of the *process*. It does not size
bets and it does not recut models.

Industry write-up this matches:
[OddsShopper, CLV explained (2026-06-05)](https://www.oddsshopper.com/articles/betting-101/closing-line-value-explained)
and the companion
[CLV vs variance (2026-08-18)](https://www.oddsshopper.com/articles/betting-101/clv-vs-variance).

## Formula

**Price CLV** (same line only), stored as `picks.clv_pct` in probability
points:

```
fair_close_p = no-vig probability of our side at the close
fair_bet_p   = no-vig probability of the PRICE TAKEN at lock, when the
               two-way at the book it was taken shows that price;
               otherwise raw bet implied
clv_pct      = (fair_close_p − fair_bet_p) × 100
```

Positive = we bought cheaper than the market’s true close.

No-vig (multiplicative / proportional de-vig): convert **both** sides of the
two-way market to implied probability, divide each by the sum. A 3-way (NHL
regulation) divides by the sum of all three. One-way quotes (anytime TD and
other one-sided markets) have no second side: `clv_method = raw_one_way`,
the raw implied is stored so pick-detail still has a number, and the
published pedigree **excludes** it.

OddsShopper’s worked Dodgers example only shows one bet price, so `fair_bet_p`
is raw implied (−130 → 56.52%). Capture looks up the snapshot at the book the
bet was taken (`clv_bet_book`) at `created_at` and de-vigs the bet too when
that row’s price on our side equals the price taken.

## Which price is the bet? (mike, 2026-10-08: "grade CLV at the price taken")

The bet is the price the pick was decided and settled at, at the book it was
taken (`paper_tracker._bet_price_and_book`). The price is
`COALESCE(decision_odds, dk_odds)`. The book is, in order:

1. `decision_book`, whenever the row carries one (since 2026-09-09);
2. the book the label names, for the four cards that keep a soft book's price
   in `dk_odds` and name the book only in the label: `nfl_prop_market` and
   `wnba_prop_market` (a `(FD)` suffix), `nfl_wind_totals` and
   `nfl_opener_spread` (`(Wind 11 mph, FD)`);
3. DraftKings, for every row decided before 2026-09-09.

`clv_bet_book` records it on every capture. The app's CLV card prints the
same price at the same book (`mobile/src/lib/clvBet.ts`, pinned to this
function by `tests/test_clv_card_price_taken.py`); for a row captured before
the column existed it derives the book with the same three steps, which on
every captured row (2026-10-09) gives the book it was graded at.

Until 2026-10-08 a pick decided
at another book but carrying DraftKings' price in `dk_odds` was graded at
DraftKings' price against DraftKings' lock quote, and the MLB market cards'
line-book price was looked up at DraftKings, where it never matched, so the
bet kept its margin while the close lost it. A line DraftKings never hung
(`dk_odds` NULL) has been graded at the price taken since earlier that day.

**Line CLV** (`picks.line_clv_pts`) is a different bet: points the number
moved toward our side. When the line moved, `clv_pct` is NULL. The two are
never mixed into one `clv_pct`. `clv_beat_close` is the one verdict: line CLV
where the number moved, price CLV where it held.

## Which book is the close?

1. **Pinnacle**, when a pre-game snapshot exists for that game + market
   ( Circa is not in The Odds API feed we store).
2. Else **DraftKings**, for every pick at DraftKings' line. Only the BET moved
   to the price taken on 2026-10-08; the close did not, because a soft book's
   "close" is junk-prone (pick 2899429: Fanatics −110/−130 nine minutes before
   first pitch while DraftKings sat at +380/−600).
3. Two exceptions keep the fallback they already had: a line DraftKings never
   hung falls back to the book it was taken at, and the market-relative prop
   cards to their label book.

**The close is bounded by the earliest start on record**: the earlier of
`games.commence_time` and `picks.game_time` (the start the pick was written
against). `games.commence_time` moves — the odds feed rewrites it on every
poll, and for NHL it read :10 before puck drop, 00:10:37 after it, and the
league's :00 once settled — and a close read against a start that moved later
took an in-play quote ("Alex Nedeljkovic Under 25.5 Saves", 2026-10-08).

`clv_close_book` names it. `closing_dk_odds` is the American on our side at
that book (legacy column name).

Prediction-market prices (Kalshi, Polymarket) are already no-vig. If a close
is ever read from those books, `clv_method = zero_vig` and the raw implied
**is** the fair close — they are not de-vigged again. Measured 2026-09-14:
zero `odds` rows and zero pick labels at Kalshi, so this is a guard, not a
current path.

## Worked example (OddsShopper’s Dodgers)

Bet Dodgers −130. Close −150 / +135.

| Step | Number |
|---|---|
| Dodgers raw close | 150/250 = 60.0% |
| Padres raw close | 100/235 ≈ 42.55% |
| Sum (vig) | 102.55% |
| Fair Dodgers | 60.0 / 102.55 ≈ **58.505%** ≈ **−141** |
| Bet implied | 130/230 ≈ 56.522% |
| `clv_pct` | (58.505 − 56.522) × 100 = **+1.98 pp** |

Raw one-sided implied on −150 would have reported +3.48 pp. The extra 1.5 pp
is hold, not edge. Pinned by `tests/test_clv_math.py::test_oddsshopper_dodgers_no_vig_close`.

Vig *widening* at close (−110/−110 → −115/−115) is +1.11 pp raw. Close-only
de-vig vs raw bet is −2.38 pp (juice paid, not a beat). De-vigging **both**
two-ways is **exactly 0**. That is the trap. Capture de-vigs both when the
lock snapshot at the bet book shows the price taken.

## What this is not

- **In-play.** Live picks are excluded (`is_live IS NOT TRUE`). The close is
  the last snapshot with `snapshot_at <= commence_time`; there is no
  unbounded “latest” fallback. Post-pitch rows labelled `open` (§106) are
  not a close.
- **A pick stamped after first pitch.** `created_at > commence_time` is
  skipped. Measuring it fabricates a favourable move.
- **Thin / one-sided / influencer markets.** Price CLV on a one-way quote is
  stamped `raw_one_way` and kept out of `avg_clv_pct`. Be suspicious of CLV
  in illiquid props even when two-way.
- **P&L.** Short-sample results are variance. This audit does not change
  unit sizes or recut models.

## Old vs new on existing rows

Through 2026-09-14, `clv_pct` was raw one-sided implied on the pick’s book.
Those rows are stamped `clv_method = raw_one_sided` by
`data/migrations/add_clv_method_2026_09_14.sql`. `_backfill_clv` rewrites
them on the worker (same 40-date bound as the uncaptured scan). Until a row
is rewritten, **`v_public_track_record` averages only `no_vig` and
`zero_vig`**, so the app pedigree (Sharp Score / `useModelClvPedigree`) never
mixes the two definitions. During the catch-up the CLV sample on the Models
tab shrinks, then grows back with the honest number.

**The price taken (2026-10-08).** Rows captured before it that were graded at
DraftKings although the bet was taken elsewhere are stamped
`clv_method = graded_at_dk_legacy` by
`data/migrations/clv_price_taken_2026_10_08.sql` (216 rows on 27 game dates
when written) and re-measured once by `_backfill_clv`, run in one go by the
declared job `clv-price-taken-recompute-2026-10-08`. Like `raw_one_sided`,
the stamp is outside the pedigree, so a stamped row leaves the published
average until it is re-measured. `clv_bet_book` is the visited mark: a row the
recompute cannot re-measure is marked, keeps the stamp and its old number, and
stays out of the average. `results_snapshots` (what Discord posted) is never
rewritten.

`opening_signals.clv_pct` uses the same no-vig formula from this change
forward. It grades the *opening lock* vs close, not the live BET vs close,
and it is a shadow track — not the public pedigree. Rows already settled
there keep the old raw number; they are not rewritten.

## Other CLV-shaped numbers in the repo

| Surface | What it is |
|---|---|
| `picks.clv_pct` | This document. Production. |
| `opening_signals.clv_pct` | Same formula, vs the opening lock. Shadow. |
| `scripts/nfl_prop_clv.py` | Line-CLV research on the market-relative card (almost never same-line). |
| `nfl/scripts/backtest_clv.py` | Spread *points* vs Pinnacle close, a different bet. |
| NFL live `devig_power` | Power de-vig for *pricing*, not this capture. |

Power de-vig (solve \(p_a^k + p_b^k = 1\)) is what the NFL moneyline arm uses
to *price*. CLV capture is multiplicative, matching OddsShopper’s worked
example. Do not swap one for the other without a new measurement.
