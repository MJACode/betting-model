# Closing line value (CLV)

**An NBA bet whose only start is the odds feed's has no close, and its columns stay empty (2026-11-02,
mike).** The feed's start ran 2.3 to 20.2 minutes behind the league's on all 107 games it wrote 2026-10-20..11-02, and
refresh passes store in-play rows typed `open`, so bounding a close on it can record an in-play price. That covers a game the
schedule does not list, one with no tip there, and a postseason game whose ESPN start sits over 30 minutes before the
feed's. A game the schedule holds the other way round reads that row. Two places hold the test, and they must agree:
`tracking/paper_tracker._nba_league_tip` and `data/migrations/clv_standard_v2_2026_10_14.sql`, whose recompute reaches any
bet not yet stamped on every pass. The bet is stamped empty after two days, in case the schedule row arrives. Other
sports have no schedule table to test against, so they keep bounding on the earliest start on record.

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

Neither side is de-vigged. `clv_pct` is stored at 2 decimal places.
A beat is above that grain (`clv_pct >= 0.01`). A loss is below it.
Equal prices are 0.00, and anything that lands inside half a hundredth
of a percent is that zero: a **push**. A push is not a beat and not a
loss. The headline beat rate is beats / (beats + losses). Pushes are
left out of the denominator and shown beside it (`50% beat close (1/2, 7 push)`;
the push clause is omitted when there are none; an all-push set is
`all N matched the close`, or `1 matched the close`, and is not divided). The average still includes
them as 0. The all-push wording was `0 measured, N push` until 2026-11-20 (mike:
*"Euroleague said 0 measured in the records last night"*): that night every
pre-game EuroLeague bet with a close had been measured, 8 of 8 at the price
taken, and the line read as though none had been. `clv_beat_close` is true only for a beat, and it is NULL when
`clv_pct` is NULL.

If that book has no pre-start snapshot on the same line, both are NULL and
the pick is left out of the average. No other book is filled in.

**Secondary — market edge.** Raw taken versus Pinnacle's fair close, only
when Pinnacle's latest pre-start main line is that same number. Game
spreads and totals use the main-line read (MLB and NHL spreads stay on
±1.5). If that close has left the number we bet, the market-edge columns
are NULL.

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

Pinnacle's market edge uses that same main-line close. It is NULL when the
main line has left `scored_line`. The last snapshot that still showed our
number is not the close.

The bound is the earlier of `games.commence_time` and `picks.game_time`.
Game rows require `snapshot_type <> 'in_play'` and
`snapshot_at <= bound`. There is no post-pitch fallback. Props do not filter
`snapshot_type` (the feed's prop rows are not stamped that way); they are
still bounded by the start. A pick with `created_at` after first pitch is
not measured.

NCAAB first-half totals and spreads (`totals_h1`, `spreads_h1`) are not the
NBA first-half shape. `data/ingestors/ncaab_first_half_odds.py` files every
pull as `open`; it does not write a `close` row. The close is that bet book's
newest pre-tip row on the same line, and only a row pulled strictly after the
pick was created. The decision pull is the price taken. No such row leaves the
pick unmeasured (`clv_method` stays unset). NBA first-half markets and team
totals still read `snapshot_type = 'close'` only. A null close does not mark
a pick measured.

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

- **In-play.** Not measured, by design (mike, 2026-11-19). `is_live IS NOT TRUE`. No unbounded latest snapshot.
- **A substitute book.** A missing bet-book close is NULL, not DraftKings
  and not Pinnacle.
- **P&L, a threshold, or a pause.** `results_snapshots` units and the
  win–loss record are not rewritten. The cutoffs in the model-quality
  monitor were not retuned when the unit became a percent.

## Where it shows

`v_public_track_record` averages `standard_v2` only. `clv_settled` /
`clv_beat` / `clv_push` / `avg_clv_pct` are the same-book headline.
`clv_settled` still counts every measured close, including a push, and
that is the weight on the average. The beat rate is
`clv_beat / (clv_settled - clv_push)`. `clv_game_*` and `clv_prop_*`
split game lines from props, pushes included. `market_clv_*` is the
Pinnacle column and is not the headline rate. The app's beat-the-close
figure is the same-book rate. A row is shown as a percent only when
`clv_method` is `standard_v2`.

`opening_signals.clv_pct` stores the same-book raw **probability points**
(DraftKings only) from this change forward. It is a shadow track. Rows
already settled there are not rewritten.

The migration recomputes every priced pre-game BET whose game has started
and whose method is not yet `standard_v2`. A row with a measurable close or
line move is stamped and captured. A row that cannot be measured, and whose
game started more than six hours ago or that already carried an older
stamp, is stamped `standard_v2` with NULLs so the old number leaves the
average, except an NCAAB first-half total or spread: that row stays
unmeasured. A recent never-captured miss is left for the Python backfill.
`scripts/recompute_empty_clv.py` recomputes rows already stamped
`standard_v2` with every closing field empty. It is a dry run until
`--apply`.

## Model health: per model, in blocks and rolling (2026-11-18)

`data/migrations/model_health_2026_11_18.sql` builds three read-only views over
the published record's graded bets. The bets are the ones
`v_public_track_record` counts: the views read its filter out of its own
definition and carry the filter's hash, so they cannot drift from it.

- `v_model_health_bets`: one row per bet. `status` is `price` (the bet book
  closed on our number; `clv_pct` is the measure), `line_for` / `line_against`
  (the main line left our number, our way or against), `in_play`, `no_close`,
  `not_measured`, `old_method`. `verdict` is beat / push / miss for a price
  close (push = `|clv_pct| < 0.005`, as above) and beat / miss for a line move.
  `seq` 1 is the model's newest bet (`created_at`, then `pick_id`).
- `v_model_health_windows`: blocks of 25, 50 and 100 over each model's newest
  500 bets, `block_no` 1 the newest; average CLV with its standard error, beat
  rates with and without line moves, Pinnacle's market edge, units.
- `v_model_health_summary`: one row per model, over every bet and its newest
  25, 50 and 100.

`price_beat_rate` is the record's headline rate. `beat_rate_with_line` adds
line moves by direction. Neither counts a push. The average CLV uses price
closes only.

The ops dashboard's Model Health tab reads these and nothing else, and the
Picks & CLV tab takes its bets from `v_model_health_bets`.

**Superseded 2026-11-19 by "The final close" below**, which closes the
three gaps this section listed (a close older than the bet, no price at our
number after a line move, NCAAB first-half spreads with no later pull). In-play
bets stay unmeasured, by design. NCAAB first-half spreads also gained a
tip-minus-3 pull (`data/ingestors/ncaab_first_half_odds.CLOSE_MARK`).

## The final close (2026-11-19, issue #1470)

mike: *"yes I want it to be accurate please correct"*. In-play bets are not
measured for closing-line value, by design (*"don't need clv for in play
bets"*). Every pre-game bet's close is now set once, after its start, by
`tracking/clv_close.py`, under one rule:

**The bet book's quote at the exact number we bet, in that book's last pull
before the start, pulled after the bet.** From the main line when its number in
that last pull is ours; otherwise from the book's alternate ladder
(`alternate_spreads` / `alternate_totals`, `<market>_alternate` for first half,
quarters, team totals and props), when that ladder's newest pull is no more
than 15 minutes older than the last main pull. Otherwise the bet has no closing
price: `clv_pct` is NULL, never 0.00, and the main line's move stays in
`line_clv_pts` when a post-bet pull exists.

"Pulled" is the row's `created_at` (the instant we fetched it), not
`snapshot_at` (the book's own last change). Both earlier writers bounded on
`snapshot_at` only, so a bet placed after the book's last pull was compared
with a price from before the bet: 4 of 73 measured bets on games from
2026-11-15, three stored as 0.00.

**Where it runs.** The settle step, after `_capture_clv` and `_backfill_clv`,
measures every started pre-game BET (games from 2026-11-15, ten minutes after
the start) not yet in `clv_close_measurements`, and writes the bet's closing
columns stamped `standard_v2`. Neither earlier writer revisits a row stamped
`standard_v2`, so this is the last word. Each measurement row keeps the
values the row held before (`before`); `picks_log` keeps the update too.
Pinnacle's market-edge columns are not changed.

**The closing pull.** `data/ingestors/clv_closing_pull.py`, every minute on
the worker (`clv_closing_pull`): for each game with a pre-game BET starting in
the next four minutes, one call to the feed's event endpoint for the bet books,
the bet markets and their alternate ladders, stored in `clv_close_quotes` with
the instant it was pulled. One credit per market returned (an NFL spread and
its ladder: 2 credits, measured 2026-11-19). Before it, the regular passes
stopped pulling many books about ten minutes before the start and pulled no
alternate ladder for most markets.

**Older games.** The odds prune deleted later rows of settled games until
2026-11-14, so bets on games before 2026-11-15 are measured from the bet
book's quotes bought from the feed's history at the start
(`scripts/clv_close_history.py`, main line and alternate ladder, into
`clv_close_quotes`; ledger `clv_close_purchases`). Measured cost: an event
list is 1 credit; one game at one book is 10 credits per market returned
(241 credits for the first 10 games).

**Measured on the 145 published pre-game bets of games 2026-11-15..18, from
stored rows** (applied 2026-11-19): 111 priced (98 from the main line, 13 from
the alternate ladder), 24 whose book's last pull no longer priced our number,
10 with no pull of the bet book between the bet and the start (5 NCAAB
first-half spreads placed on the last pull, 3 NHL moneylines placed 4 minutes
before the start, 2 Hard Rock props). The closing pull is what closes the last
group from now on.

**Two fixes, 2026-11-19 (after the first full run).** A player is matched
across accents, case, punctuation and Jr./III (`clv_close.player_key`): the
feed's history spells "Jose Soriano" and "Walbert Urena" where our labels say
"José Soriano" and "Walbert Ureña". And a prop's line move is recorded whether
or not the pick row carries `prop_market` (the single-market prop models leave
it empty), so an Under the book no longer offered at our number shows as a
line move, not as "no closing price". The closing pull now pulls a game again
when a bet lands after its last closing pull (NHL moneylines are decided about
four minutes before the start). After both, the published record's pre-game
bets: 1,163 priced, 102 line moved our way, 53 against, 32 no closing price
(22 placed in the last ten minutes before the start, after the book's final
pull; 8 whose player or market the book no longer listed at the start; 1 with
no main line in the last pull; 1 other).

**The listed start and the first play (rule v2, 2026-11-19).** mike: *"figure
out the last 22 missing"*. The start the rule bounds on is the listed one, and
an NHL puck drops 8 to 18 minutes after it (ESPN's wall clock on the first
play, 11 games measured). A bet placed in the last minutes before the listed
start can have no pull of its book between the bet and that time. For that bet
only, the close is the book's last price before the game actually began: the
first play (`game_first_play`) less one minute. A bet placed at or after the
first play is not a pre-game bet and has no close. `scripts/clv_close_history.py
first-play` stores first plays from ESPN (NHL and NCAAF matched) and `buy-late`
buys the bet book at that moment from the feed's history (19 game-and-book
calls, 174 credits). The worker's settle step has no first plays of its own and
still measures bets placed before the listed start; the closing pull, which
runs to 40 seconds before it, covers all but a bet placed in those last
seconds.

After it, the published record's pre-game bets: 1,180 priced, 101 line moved
our way, 53 against, 16 no closing price. Of the 22: 8 priced at the last
pre-game price before puck drop. 13 have no price after the bet anywhere, and
3 are NCAAF totals placed after kickoff:

* 3 BetRivers NHL bets placed 1.5 to 8 seconds after the feed's last BetRivers
  snapshot. BetRivers takes its pre-game market down at the listed start: the
  snapshot 36 seconds after it lists DraftKings and not BetRivers, and our own
  last BetRivers pull (local copy) came before each bet.
* 8 shots-on-goal props (7 Hard Rock, 1 William Hill): the book stopped
  offering that player's shots line after the bet while it kept listing his
  other props, through the start and in the history before the first play.
* 1 NFL prop at Fliff: no Fliff pull after the bet, and the history at kickoff
  lists Fliff without the player.
* 1 NBA Under at FanDuel: its last pull before the tip offered only Overs at
  our number; the main line came back at another number.
* 3 NCAAF totals placed after kickoff, because the feed listed the start 4 to
  8 minutes after the real kickoff (issue #1484). One was among the 22; the
  other two had been measured against post-kickoff prices (one +0.38%, one a
  line move our way) and now read "placed after the game began".

Pinnacle's fair close covers 10 of the 13 (`market_clv_pct`; its timing is
issue #1482). A close from another book at our number would change what the
same-book column measures, so it is not used. mike: *"leave the 13 missing blank"*.

**A bet placed after its game's first play is in-play on Model Health**
(mike, 2026-11-19: the three NCAAF totals *"should be moved to live bets"*).
`v_model_health_bets` reads any bet placed at or after its game's first play
(`game_first_play`) as `in_play`, whatever model wrote it, so it is out of the
pre-game closing-line figures. Setting `is_live` on the pick rows would not
move them into a live record (the record counts an in-play bet only from an
in-play model posted to a live channel); mike chose to take the three out of
the record instead, and they were voided the same day (`docs/sports/ncaaf.md`).


**Tennis (2026-11-20).** The final close read only `odds`, `player_prop_odds`
and `clv_close_quotes`, and tennis prices are in none of them: the tennis card
stores them in `tennis_odds_quotes` (`docs/sports/tennis.md`). So every tennis
bet was stamped "no pull of this book after the bet and before the start", and
the tennis models showed no closing-line value at all (the one bet then
settled, `atp_moneyline_shop`'s Alexander Zverev ML at Hard Rock -275 on
2026-11-19). `clv_close.tennis_quotes` now reads them. That table is
change-only, a row only when a book's quote changed, so a row after the bet
is not the test of a pull after the bet. The pulls are the card's own live
polls in `tennis_odds_fetches` (every 10 minutes, `events` > 0), and the
book's quote at a pull is its newest row at or before it. The match is the
feed event the card decided (`tennis_moneyline_decisions`, by game id).
Re-measured with `python -m scripts.clv_close_history remeasure-none --model
atp_moneyline_shop wta_moneyline_shop --apply`: the Zverev bet closed at Hard
Rock -300 (its 19:23 UTC pull, seven minutes before the listed 19:30 start),
+2.27%, a beat. A book that stops quoting a match leaves no row to say so, so
its last row reads as standing; the card decides on the same reading. The
feed moved that match's listed start from 19:30 to 19:37 after the bet; the
rule bounds on the start stored on the game (19:30). Pinnacle's fair close for
tennis is still not written (`market_clv_pct`): its writer reads `odds` only.
