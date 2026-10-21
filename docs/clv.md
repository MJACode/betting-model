# Closing line value (CLV)

The formula, the book, and the worked examples. Capture lives in
`tracking/paper_tracker.py` (`_capture_clv` / `_backfill_clv`); the arithmetic
is `tracking/clv_math.py`. The bulk rewrite is
`data/migrations/clv_standard_v2_2026_10_14.sql`. This is a grade of the
*process*. It does not size bets and it does not recut models.

## Two numbers

**Primary — same-book raw price CLV.** Did the book we actually bet
(`decision_book`, stored as `clv_bet_book`) close worse than the price we
took, on the same side and the same line?

```
taken  = raw implied probability of COALESCE(decision_odds, dk_odds)
close  = raw implied probability of THAT book's last pre-start American
clv_pp = (close − taken) × 100
clv_pct = (taken_decimal / close_decimal − 1) × 100
```

Neither side is de-vigged. A beat is `clv_pct > 0`. Equal prices are 0 and
are not a beat. `clv_beat_close` is that comparison, and it is NULL when
`clv_pct` is NULL.

If that book has no pre-start snapshot on the same line, both are NULL and
the pick is left out of the average. No other book is filled in.

**Secondary — market edge.** Raw taken versus Pinnacle's fair close, only
when Pinnacle has a pre-start snapshot on the same line.

```
fair        = power de-vig of Pinnacle's close (power_3way when a draw is quoted)
market_clv_pp  = (fair − taken) × 100
market_clv_pct = (taken_decimal × fair − 1) × 100
```

`market_clv_method` is `power`, `power_3way`, or `zero_vig` (Kalshi and
Polymarket, which are not de-vigged again). No soft-book fallback. Missing
Pinnacle close → NULL. This column is not the headline beat rate.

`clv_method = standard_v2` is the only stamp in the pedigree
(`PEDIGREE_CLV_METHODS`). Older stamps (`no_vig`, `zero_vig`, `raw_one_way`,
`raw_one_sided`, `graded_at_dk_legacy`) stay on the row until rewritten and
are excluded from averages.

## Which price is the bet?

The price is `COALESCE(decision_odds, dk_odds)`. The book, in order
(`paper_tracker._bet_price_and_book`):

1. `decision_book`, whenever the row carries one;
2. the book the label names, for `nfl_prop_market`, `wnba_prop_market`,
   `nfl_wind_totals` and `nfl_opener_spread`;
3. DraftKings.

`clv_bet_book` records it. The app prints the same price at the same book
(`mobile/src/lib/clvBet.ts`).

## Same line, and the close bound

The price snapshot is filtered to the signed `scored_line` (`spread_home =
scored_line`, not `ABS`). A later puck line at the opposite sign is a
different bet. NHL puck-line rows in `odds` keep the sign the book sent;
this capture does not rewrite them.

Line movement uses the book's latest main line. MLB and NHL spreads stay on
`ABS(spread_home) = 1.5` for that read, so an alternate is not the close.
When that number has left `scored_line`, `clv_pct` is NULL and `line_clv_pts`
is kept. The headline beat does not treat the point move as a beat.

The bound is the earlier of `games.commence_time` and `picks.game_time`.
Game rows require `snapshot_type <> 'in_play'` and
`snapshot_at <= bound`. There is no post-pitch fallback. Props do not filter
`snapshot_type` (the feed's prop rows are not stamped that way); they are
still bounded by the start. A pick with `created_at` after first pitch is
not measured.

## Worked examples

Pinned by `tests/test_clv_standard_v2.py` and `tests/test_clv_math.py`.
Power de-vig is bisection, 80 steps, k in [0.05, 12], then renormalised.
It is not the multiplicative de-vig in the OddsShopper write-up, so the
Dodgers fair price here is −143, not −141.

| Pick | Taken | Same-book close | Primary | Pinnacle | Market edge |
|---|---|---|---|---|---|
| 3114189 Dach Under 1.5 SOG | DK −120 | DK −145 | **+8.50% / +4.64pp**, beat | −142 / +107 | +1.51% / +0.82pp, `power` |
| 2387645 MIA +1.5 | Rebet −132 | Rebet −133 | **+0.33% / +0.18pp**, beat | −125 / +113 | **−4.47% / −2.54pp**, `power` |
| 3114194 Dunn Under 0.5 assists | DK −160 | DK −160 | **0 / 0**, not a beat | −160 / +120 | −5.21% / −3.21pp, `power` |
| Dodgers −130 (illustration) | −130 | — | — | −150 / +135 | +4.08% / +2.31pp, fair −143 |

2387645 is the sign flip: the old no-vig column stored +1.10. The book we
bet (Rebet) closed one cent worse, which is a small beat. Pinnacle's fair
close was better than the price we took, which is the negative market edge.

## What this is not

- **In-play.** `is_live IS NOT TRUE`. No unbounded latest snapshot.
- **A substitute book.** A missing bet-book close is NULL, not DraftKings
  and not Pinnacle.
- **P&L, a threshold, or a pause.** `results_snapshots` units and the
  win–loss record are not rewritten. The cutoffs in the model-quality
  monitor were not retuned when the unit became a percent.

## Where it shows

`v_public_track_record` averages `standard_v2` only. `clv_settled` /
`clv_beat` / `avg_clv_pct` are the same-book headline. `clv_game_*` and
`clv_prop_*` split game lines from props. `market_clv_*` is the Pinnacle
column. The app's beat-the-close figure is the same-book rate. A row is
shown as a percent only when `clv_method` is `standard_v2`.

`opening_signals.clv_pct` stores the same-book raw **probability points**
(DraftKings only) from this change forward. It is a shadow track. Rows
already settled there are not rewritten.

The migration recomputes every priced pre-game BET whose game has started
and whose method is not yet `standard_v2`. A row with a measurable close or
line move is stamped and captured. A row that cannot be measured, and whose
game started more than six hours ago or that already carried an older
stamp, is stamped `standard_v2` with NULLs so the old number leaves the
average. A recent never-captured miss is left for the Python backfill.
