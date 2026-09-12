# Best line on pre-game picks — why picks read as DraftKings, and the route off it

> mike, 2026-09-02: *"investigate why mlb/wnba/ncaaf/ufc picks continue to only
> come from DraftKings lines. I mentioned earlier that picks should have the
> best possible line. they are all available in the odds api. design the best
> solution. this is only for pregame picks for now."*
>
> Live/in-play lanes are explicitly **out of scope** and unchanged.
> Every number below was measured on 2026-09-02, with the query stated.

---

## 1. The answer is three separate things, and only two of them are bugs

**(a) Two markets were fetched DraftKings-only at the source. This was a bug and
it is fixed.**

`data/ingestors/odds_ingestor._get_event_odds` hard-coded
`"bookmakers": ODDS_API_BOOKMAKER`. It is the **only** route by which MLB
first-five markets and UFC round totals are fetched — both are "additional
markets" that the bulk `/odds` endpoint does not carry — so those two markets
had one book in the database while every bulk market had seven:

| market | draftkings | every other book |
|---|---|---|
| `h2h_1st_5_innings` (MLB F5) | 704 rows | **0** |
| UFC `totals` (round totals) | 891 rows | **0** |
| MLB `h2h` / `spreads` / `totals` | ~3,000 each | 520–871 each, ×6 books |
| UFC `h2h` | 1,613 | 435–1,570, ×5 books |

*(`SELECT sport, market, bookmaker, count(*) FROM odds WHERE snapshot_at >=
'2026-09-01' AND snapshot_type <> 'in_play' GROUP BY 1,2,3`, sport from the
game_id prefix.)*

Consequence: **51 of 176 recent MLB pre-game BETs — every `mlb_f5_moneyline`
pick — had nothing to line-shop against**, and neither did any
`ufc_total_rounds` pick. Not "the shop found DK best": there was one quote.

This is the same bug, in the same file, that mike named on 2026-09-01 about
`_get_historical_odds` (*"Pinnacle data is in odds api. I have brought this up
several times. why do you ignore it."*).

**What it costs, measured against the live endpoint on 2026-09-03 rather than
read off the docs — and it is NOT free.** `x-requests-last` on one event:

| call | credits | markets returned |
|---|---|---|
| F5, `bookmakers=draftkings` | 1 | `h2h_1st_5_innings` |
| F5, all seven books | **3** | + `spreads_1st_5_innings`, `totals_1st_5_innings` |
| UFC totals, DK-only | 1 | `totals` |
| UFC totals, all seven books | **1** | `totals` |

The per-event endpoint bills **per market RETURNED, not per market requested**.
DK alone offers only F5 moneyline; the other six offer F5 spreads and totals
too, so the widened call comes back with three markets and is billed for three.
UFC round totals is one market either way and does not move.

Net: **~+2 credits per MLB event per F5 fetch** — ~15 events, daily pipeline
only (`FETCH_F5_LIVE`) — so roughly **+30/day against 4,900,852 remaining**.
And the extra spend buys F5 spreads and F5 totals, which this repo has never
held. An earlier draft of this doc and of the code comment said "zero extra
credits" on the strength of the one-region rule; the A/B above is why the rule
is measured and not quoted (§1b).

**(b) Most picks that show no best price simply predate the feature.**

Best-line stamping shipped ~2026-08-28. Coverage by week of `created_at`, all
pre-game BETs:

| week | bets | with a best price |
|---|---|---|
| 07-13 → 08-17 (6 weeks) | 191 | **0** |
| 08-24 | 30 | 19 |
| 08-31 | 70 | **69** |

The one miss in the clean window is the UFC round-totals pick from (a). So the
"MLB 48%, WNBA 12%, UFC 0%" coverage figures that opened this investigation were
an artifact of pooling six pre-feature weeks with four post-feature days — a
BET-count answering the wrong question, exactly the §1b trap. **WNBA was never
broken**; its season ended 2026-08-30, two days after the feature landed.

**(c) The price that DECIDES is DraftKings, by calibrated design — and that is
the part mike is actually asking to change.**

CLAUDE.md §6 pins `edge`, the BET/AVOID call, the Kelly stake, settled P&L and
CLV to DK, because every threshold was swept on DK-implied edge. `picks.best_*`
records the better number for display and the betslip hand-off only, and
`tests/test_best_line.py` asserts the decision path never sees it. That is not a
defect; it is the calibration boundary, and moving it is §2 below.

---

## 2. The finding that mattered most: a quarter of "best prices" cannot be bet

`BEST_LINE_BOOKMAKERS` defaulted to `LINE_SHOP_BOOKMAKERS`, which includes
**pinnacle** and **bovada**. Pinnacle does not accept US customers; Bovada is
offshore. Both belong in the feed — Pinnacle is the sharp de-vig reference
`SHARP_BOOKMAKERS` is built on, Bovada carried the NCAAF opener signal — but
neither is an answer to *"where should I place this?"*

Of the **69** pre-game BETs since 08-31 carrying a best price:

- **35** named a book other than DraftKings, and
- **18 of those 35 named Pinnacle or Bovada.**

So **over half of every "we found you a better number" claim, and 26% of all
bets, pointed at a price the bettor could not take** — while the column's own
docstring says it is "what the bettor should actually take". Lifetime, Pinnacle
is the stamped `best_book` on 398 picks and Bovada on 261.

Fixed by splitting the roles: `BEST_LINE_EXCLUDE_BOOKMAKERS` removes a book
from *shopping* while leaving it in `LINE_SHOP_BOOKMAKERS` and
`ODDS_API_BOOKMAKERS_PARAM` for analysis.

### The book list mike set, 2026-09-03

> *"add fanatics / ceasars / wynnbet to betable books, remove william will and
> espn bet (shut down last year)"*

Every name was checked against the live endpoint before the list moved, per the
`curl` instruction that already sits above `LINE_SHOP_BOOKMAKERS`. Keys actually
returned on `regions=us,us2`: ballybet, betanysports, betmgm, betonlineag,
betparx, betrivers, betus, bovada, draftkings, espnbet, fanatics, fanduel,
fliff, hardrockbet, lowvig, mybookieag, rebet, williamhill_us.

| asked | done | why |
|---|---|---|
| add **fanatics** | ✅ added to both lists | real key, returns MLB/NCAAF/WNBA (no UFC) |
| add **caesars** | ⚠️ already there, as `williamhill_us` | `caesars` is not a key this API returns |
| add **wynnbet** | ❌ impossible | the endpoint does not return that key; Wynn left US online sports betting |
| remove **williamhill_us** | ❌ **not done** | it IS Caesars — removing it deletes the book asked for in the line above |
| remove **espnbet** | ✅ excluded from shopping, still fetched | see below |

**espnbet, measured the same day:** 82 h2h quotes across MLB/NCAAF/WNBA with a
**median age of 0.7 minutes** — the feed says it is still pricing, not shut
down. It is excluded anyway, because which books a bettor will actually use is
mike's call and not the feed's; it stays in `LINE_SHOP_BOOKMAKERS` so the data
keeps arriving and the decision is one env var to reverse.

Resulting split:

- **Fetched** (`LINE_SHOP_BOOKMAKERS`): draftkings, fanduel, betmgm,
  williamhill_us, espnbet, fanatics, bovada, pinnacle
- **Offered as a price** (`BEST_LINE_BOOKMAKERS`): draftkings, fanduel, betmgm,
  williamhill_us (Caesars), fanatics

**Added 2026-09-03** (mike: "do the extra books"): betrivers, hardrockbet,
ballybet, betparx, rebet — all with live quotes and full coverage including WNBA
and UFC, the two sports that shopped fewest books.

**They cost double, and the repo's own comment said they would not.** These five
live in the `us2` region and The Odds API bills markets × REGIONS. Measured on
one bulk MLB call for h2h+spreads+totals: the 8 existing books cost **3**
credits, these 5 alone cost **3**, all 13 together cost **6**. The same doubling
hits the per-event fetch and the prop fetch. Against ~35k credits/day and a
5,000,000 monthly plan (August used 737,085) that moves toward ~2.1M/month.

The marginal cost of books 2-5 is **zero** — once one `us2` book is on the list
the second region is paid for — so this is all-or-nothing, not a dial.

---

## 3. Stage 1 — shipped in this change (no model behaviour changes)

| # | Fix | Effect |
|---|---|---|
| 1 | `_get_event_odds` takes `bookmakers`, defaulting to `ODDS_API_BOOKMAKERS_PARAM`, with a 400 fallback to DK-only | MLB F5 and UFC round totals become shoppable for the first time, and F5 spreads/totals arrive as well. ~+30 credits/day, measured |
| 2 | `_best_game_price` resolves the UFC sibling orientation, flipping the side for `h2h` and keeping it for `totals` | `_get_dk_odds` has done this since the 2026-08-29 card; best-price lookup did not, so a fight five books had priced could silently stamp NULL |
| 3 | Unbettable books excluded from shopping, kept in the feed | §2 |

Nothing here touches `edge`, the BET/AVOID call, Kelly, settlement or CLV, so
there is no `Updated-By:` trailer — this is ingest and display plumbing.

**Verify after deploy** (do not trust the comment — CLAUDE.md §1b):

```sql
-- (1) other books arrive on the two per-event markets
-- bare 'totals' would match every sport, so the UFC half is scoped by game_id
SELECT market, bookmaker, count(*) FROM odds
WHERE (market LIKE '%_1st_5_innings'
       OR (market = 'totals' AND game_id LIKE 'UFC_%'))
  AND snapshot_at >= '<deploy date>' GROUP BY 1,2 ORDER BY 1,2;
-- (2) credits per fetch did not move
SELECT * FROM odds_api_quota ORDER BY checked_at DESC LIMIT 20;
```

---

## 4. Stage 2 — moving qualification to the best price

> **mike, 2026-09-03: "stage 2 go."** That is the authorization, recorded here
> because the flip commit will land weeks from now and this instruction is its
> provenance. The flip is a model update and carries `Updated-By: mike`.
>
> Step 1 shipped: **`scripts/best_line_threshold_sweep.py`** — re-derives every
> pre-game cut on best-price edge, writes nothing. Re-run it weekly;
> `tests/test_best_line_sweep.py` pins its arithmetic.

This is the real request, and it cannot be shipped as a side effect of Stage 1.

**What it costs.** Every cut in `MODEL_EDGE_THRESHOLDS` /
`MODEL_PROB_THRESHOLDS` was swept on DK-implied edge. Qualifying on the best of
N books lowers the implied probability, so every cut loosens by that amount with
nobody deciding to. Measured on the 69 clean-window bets: **0.68pp on average,
3.61pp at most**. `config.py` carries an older ~2pp figure from 92 MLB games on
08-28; the populations differ (market-wide games vs same-line picks) and the
re-sweep is what settles it — do not relitigate it beforehand.

**The evidence needed already mostly exists, which is better than assumed.**
§7's evaluation rule requires grading BET, AVOID and dead-zone NONE alike. The
stamping runs on every scored row, not just bets — since 08-31: **NONE
2,621/2,647, AVOID 311/312, BET 69/70**. So the re-sweep sample is the full
scored universe, not a BET-only one.

The residual gap is real but narrow: propositions that get **no row at all**
(`abs(edge) > MAX_EDGE_CAP` — 35.3% of `mlb_runline` games per §7) and NONE rows
removed by `cleanup-picks`. Reconstructing those needs raw non-DK history, and
`PRUNE_NON_DK_KEEP_DAYS = 2` deletes it after two days.

**Retention, measured rather than estimated.** Non-DK rows written per day:
252,705 in `odds` (573 B/row) + 98,680 in `player_prop_odds` (663 B/row) ≈
**210 MB/day, ~6.3 GB/month**. The comment in `config.py` says ~2.7 GB/month;
that counted one table. So "raise it to 90 days" is a ~19 GB commitment, which
is why it is a decision and not a default. Two cheaper options, in order of
preference:

1. **Do nothing.** Accept the narrow gap and re-sweep off the picks table, which
   already carries the full scored universe. Free.
2. **Keep one snapshot per book per proposition per day** instead of ~21. Same
   reconstruction power for the re-sweep at roughly 1/20th the volume, and it is
   a change to `data/prune_odds.py`, not a retention number.

> **mike chose option 2 on 2026-09-03, and it shipped.** The detail that
> mattered: after `keep_days` the pruner already kept exactly one non-DK row per
> (proposition, book) — but it was the **opener**, which cannot reconstruct a
> decision-time price. It now keeps the opener AND the **close** (the last
> pre-game-typed snapshot). Measured cost: **+6 MB/day**. See
> `data/prune_odds.py` and `tests/test_prune_keeps_the_close.py`.

Raising `PRUNE_NON_DK_KEEP_DAYS` wholesale is the expensive third option. What
must not happen is deciding this in three months: pruned rows are gone.

### First read, 2026-09-03 (5 days of data — nothing shippable)

`now` and `same @best` replay today's cut over the **whole graded universe**
(§7's evaluation rule), so they are not the bets actually placed.

| model | rows | now | same @best | gain | verdict |
|---|---|---|---|---|---|
| mlb_prop_pitcher_outs | 107 | 14-5 +60.1% | 14-5 +63.6% | **+3.5pp** | candidate 0.50/0.10 — not shippable, 5-day window |
| mlb_runline | 70 | 3-1 +43.5% | 3-1 +48.3% | **+4.8pp** | no cut at 25+ settled |
| mlb_prop_pitcher_hits | 110 | 11-5 +32.3% | 11-5 +33.0% | +0.7pp | candidate 0.50/0.04 — not shippable |
| mlb_prop_batter_runs | 1,130 | 5-3 +13.9% | 5-3 +14.4% | +0.5pp | peak, not a plateau |
| mlb_prop_pitcher_k | 121 | 8-12 −23.0% | 8-12 −22.2% | +0.8pp | no cut |
| mlb_over_under | 91 | 6-10 −25.5% | 6-10 −24.3% | +1.2pp | no cut |
| wnba_prop_player_rebounds | 42 | 5-1 +53.7% | 5-1 +61.5% | **+7.8pp** | no cut (42 rows) |

**What this says so far.** The free half is real and small: the *same* picks
paid at the best price gain **0 to +7.8pp of ROI**, typically under a point.
Nothing clears the shipping gate — every candidate is a five-day window, which
cannot produce a credible time split, and the models with thousands of graded
rows (`batter_hits` 1,302, `batter_walks` 1,043) return **no profitable cut at
all** on best-price edge, which is the sweep working rather than failing.

**Cadence.** Re-run weekly. Prop models accumulate 200–1,300 graded rows a day,
so their time split becomes credible in roughly two to three weeks; game models
add 15–20 a day and need a month or more. **Earliest credible flip: the
high-volume props, mid-to-late September.**

### The flip, 2026-09-09

> **mike: "we should remove DK only - we want best lines for us regardless."**
> That is the instruction that lifted the re-sweep gate above. Shipped the same
> day, `Updated-By: mike`.

What the sweep said the morning it shipped (`scripts/best_line_threshold_sweep`,
12 days of best-price history, 25+ settled rows per cell): **no cut is
shippable on best-price edge** — every candidate fails the time split or the
volume gate, and the models with thousands of graded rows return no profitable
cut at all. The same picks paid at the best price gain **0 to +7.8pp of ROI,
typically under a point** (pitcher_outs +2.3pp on 39 bets, runline +3.2pp on
6, wnba rebounds +7.8pp on 6). So **no cut moved**: every cut is applied
unchanged at the better price, which is 0.68pp looser on average and 3.61pp at
the extreme by the 09-02 measurement. Re-run the sweep weekly; move a cut only
on the section-7 standards.

What that loosening would have drawn in, measured before the PR merged (query
in session 279: pre-game rows since 2026-08-28 with a stamped `best_odds`,
NONE or AVOID at DraftKings, passing their model's `min_prob` / `min_edge` /
`min_odds` on `best_edge` / `best_odds`, graded through
`mv_scored_pick_outcomes` and paid at the best price; excludes rows with no
stamp and games over `MAX_EDGE_CAP`, which have no row): **at most 17 rows
would have become BETs beside the 324 pre-game BETs actually written (296 of
them stamped, 139 at a book other than DraftKings) — 16 graded, 11-5, +5.1
units.** Seven models, five of them MLB props; no model contributes more than
5. A ceiling, not the population: those stamps were written before the cutoff
bound, the in-play exclusion and the freshness filter existed, so the new
lookup can only flip a subset. Too small to be evidence either way; reported so
the first weekly sweep has a baseline.

What shipped, in one change:

- **`picks.decision_book / decision_odds / decision_implied_prob /
  decision_edge`** — the price the pick was DECIDED at. Rows from before the
  flip carry NULL and every reader `COALESCE`s to `dk_*`, which is exact (they
  were decided at DraftKings). `edge` and `dk_*` keep their DraftKings meaning.
  Mirrored on `picks_log` and copied by the audit trigger, so a first-signal
  restore keeps the deciding price.
- **The scorer** builds each pick at the DraftKings quote through one pair of
  rule functions (`_decide` / `_size`), then `_requalify_at_best` re-runs the
  same two at the best bettable price the moment the pick is shopped —
  `_stamp_best_game_prices` for game markets (now including NHL 3-way),
  `_tag_prop(pick, ctx, conn)` for every prop lane — BEFORE dedupe, the daily
  caps and the first-signal lock read `signal_type`. The best-price lookups
  are bounded at the pre-game cutoff like the DraftKings reads, exclude in-play
  rows, and drop a book whose newest quote lags the shop by more than
  `BEST_LINE_MAX_LAG_MIN` (30; measured max 4.3 minutes on 2026-09-09).
- **Settlement** grades at `COALESCE(decision_odds, dk_odds)` on all four
  settle paths; `mv_scored_pick_outcomes` carries `decision_*` and grades
  `profit_units` there; the record views, the custom-model RPCs, the Discord
  and push producers, the emitted action-filter SQL and the app's
  `passesActionFilter` all cut on the decision columns
  (`data/migrations/decide_on_best_price_2026_09_09.sql`, applied to
  production before the code deployed; the two active view files re-applied
  once).
- **What stays DraftKings:** the LINE a pick is scored at (until 2026-09-12,
  when a prop DraftKings does not list gained a line from the first bettable
  book that does -- the last section of this file), training features, CLV
  (`closing_dk_odds` vs `dk_odds`), the line-movement monitor, and the
  opening-signal shadow track. The live lanes were fenced out on 2026-09-09
  (his 2026-09-02 "only for pregame picks for now") and joined on 2026-09-10
  — the section below. `MAX_EDGE_CAP` is judged on the DraftKings edge in the
  builders and not re-applied at the best price.
- **Flag:** `DECIDE_ON_BEST_PRICE=0` restores DraftKings as the deciding price.

**The order, when the evidence arrives.**

1. Re-sweep each pre-game model's cut on best-implied edge — **per model, never
   copied across** (§1b), with the plateau/CI/time-split standards of §7.
2. Flip qualification, Kelly and settlement to the best price in ONE change,
   `Updated-By: mike`. **Done 2026-09-09, ahead of step 1, on mike's
   "regardless" — see above.** `tests/test_multi_book_odds.py` and
   `tests/test_best_line.py` will fail — they are the tripwires being
   deliberately retired, and that failure is how you know it is the intended
   change rather than a leak.
3. **CLV stays DK-to-DK** in either case: there is no best-price closing history
   to measure against, and mixing the two would make the number meaningless.

---

## 5. Scope fences

- **Same line only.** A better price on Over 9.0 is not a better price on
  Over 8.5 — it is a different bet, and the model probability was computed at
  the scored line. Line-aware shopping means re-scoring at the alternate line;
  that is a separate piece of work, not part of this.
- **No backfill of `best_*` onto locked picks.** Stamping today's shop onto an
  old pick fabricates score-time data — §1c, timing is data.
- **Live lanes untouched on 2026-09-09, with ONE deliberate exception.**
  `_best_live_price` and the in-play loops were unchanged in mechanics that
  day, per mike's instruction. But the unbettable-book exclusion in §2 is a
  shared config constant, so it applied to live stamping too — a price the
  bettor cannot take is the wrong number on a live pick for exactly the same
  reason it is wrong on a pre-game one. The fence came down the next day
  (below).
- **No UI change.** Whether the headline price members see becomes best-instead-
  of-DK is a product decision, not a consequence of this.

### The live lanes join, 2026-09-10

> **mike, 2026-09-10, to the list of decisions the 09-09 reply put to him
> (widen the live lanes among them): "Yes do everything".**

Measured first, on the live BETs written since 08-30 with a stamped best
price (query in session 289: `picks` where `is_live`, BET, `dk_odds` present,
paid at `dk_odds` vs at `COALESCE(best_odds, dk_odds)` on the stored result):

| lane | BETs graded | with a non-DK best | best vs DK, implied | units at DK | units at best |
|---|---|---|---|---|---|
| `mlb_live_total_runs` | 99 | 59 | 1.81pp cheaper on average, 10.7pp at most | +7.48 | +10.41 |
| `ncaaf_live_total` / `_win_prob` | 47 / 5 | 0 (the feed asked DraftKings only) | — | +1.35 / +1.49 | same |
| `nfl_live_prop` | 0 | 0 (DK-only feed, no in-play prop rows from any other book) | — | — | — |

The NONE→BET population is NOT measurable for the live lanes: a dead-zone live
pick is never written, so there is no row to re-price. Say so rather than
estimate it.

The 10.7pp outlier (FanDuel +122 against DK −126 on a live total, 2026-08-31)
is the shape of a frozen book: the old stamp was age-gated only. Every
candidate quote is now also gated on the score-change clock the DK quote
passes through (`quote_predates_score`), on both lanes.

What shipped:

- **MLB (`models/live_scorer.py`).** `_make_live_pick` takes the best
  bettable in-play quote at the same line (`scorer._live_book_quotes` →
  `_best_live_side`, one LATERAL top-1-per-book read per (game, market) per
  pass: 41 ms against the 951 ms of the previous sort-the-game shape) and
  decides, sizes and stamps `decision_*` at the better of it and DraftKings
  (`scorer._live_decision_quote`; a tie keeps DK), through the SAME
  `classify_live_signal` — with the stale-line cap (`LIVE_MAX_EDGE_CAP`)
  judged on the DK edge, as pre-game keeps `MAX_EDGE_CAP` on it. The decision
  has to happen inside the builder: a dead-zone live pick returns None and is
  never written, so there is no NONE row to requalify later. The lane
  signature (what makes a rewrite) carries the deciding price.
- **NCAAF (`ncaaf_live/`).** The in-play poll asks for the bettable books in
  DraftKings' Odds API region (`SNAPSHOT_BOOKS`, pinned to
  `config.LIVE_FEED_BOOKMAKERS`): measured 2026-09-11, `x-requests-last` = 2
  with DK alone and 2 with all five, so it costs nothing; a us2 book would
  double every poll. `parse_event_odds` keeps DK on top as the reference and
  carries every book underneath; `serve.best_takeable_quote` picks the best
  same-line quote whose OWN publish clock passes `market_is_takeable`;
  `LiveEngine._deciding` / `_decide(cap_edge=)` decide at it; gameday logs
  every book's quote to `odds`, not only DK's.
- **`nfl_live_prop` cannot join**: its feed is DraftKings-only and no other
  book has an in-play prop row in `player_prop_odds` (0 since 08-28). It keeps
  deciding at DK, `decision_book = draftkings`.
- **Surfaces.** The live Discord card headlines the deciding price and book
  through `publish_price` and bounds "good to" at it; settlement already read
  `COALESCE(decision_odds, dk_odds)` on every path; the live record views cut
  on the decision columns since 09-09.
- **Flag:** `DECIDE_ON_BEST_PRICE=0` puts every lane back on DraftKings.

---

## 6. Where the pieces live

| Thing | File |
|---|---|
| Book roles: shop / sharp / feed / excluded | `config.py` — `LINE_SHOP_BOOKMAKERS`, `BEST_LINE_BOOKMAKERS`, `BEST_LINE_EXCLUDE_BOOKMAKERS`, `SHARP_BOOKMAKERS` |
| Best-price lookup (pre-game, prop, live) | `models/scorer.py` — `_best_game_price`, `_best_prop_price`, `_best_live_price` |
| Per-event fetch (F5, UFC round totals) | `data/ingestors/odds_ingestor.py` — `_get_event_odds` |
| Retention | `data/prune_odds.py`, `config.PRUNE_NON_DK_KEEP_DAYS` |
| The DK-decides invariant | CLAUDE.md §6; `tests/test_multi_book_odds.py`, `tests/test_best_line.py` |

---

## Scoring off another book's line, 2026-09-12

> **mike: "Yes, scoring of other books lines."**

Until this change a proposition with no DraftKings quote produced no pick at
all, however many bettable books priced it. Measured over the markets an
ACTIVE model prices, 2026-08-28 onward (query in session 290):

| | player propositions since 08-28 |
|---|---|
| DraftKings listed | 11,780 |
| a bettable book listed, DraftKings did not | 1,357 |
| where those came from | FanDuel 607, Hard Rock 550, Fanatics 291, Caesars 259, Fliff 245, BetMGM 109, BetRivers 69, BetPARX 12 |

Counting the PAUSED models too it is 5,344, and the two largest pools are
theirs: batter stolen bases (2,110) and batter total bases (1,723). Unpausing
those is a separate decision this change does not make.

**The line is the proposition.** The book is taken in
`config.BEST_LINE_BOOKMAKERS` order -- the list mike curated, DraftKings
first -- and never by price: Over 5.5 is a different bet from Over 6.5, so
picking whichever book quotes the softest number would be choosing the bet to
suit the model. Once the line is fixed, the ordinary best-price check runs at
THAT line, so the bet is still placed at the best bettable price on the same
number.

What shipped:

- **`picks.line_book`** (and on `picks_log`, copied by the audit trigger):
  the book whose line it is, NULL for DraftKings, which is every row before
  today.
- **`scorer._fallback_line_quote`**, called by `_get_prop_dk_odds` only when
  DraftKings has nothing. Same pre-game cutoff bound and same in-play
  exclusion as the DraftKings read.
- **The DraftKings columns stay DraftKings.** `dk_odds` NULL,
  `dk_implied_prob` and `edge` at their NOT NULL placeholders, `dk_bet_link`
  NULL (a DraftKings slip for a proposition DraftKings does not list opens
  empty). The deciding price is in `decision_*` as it has been since 09-09.
- **The best-price re-check keyed on `dk_odds`** and would have skipped every
  one of these; it keys on the deciding price now.
- **The published record gated its units on `p.dk_odds IS NOT NULL`** (the
  2026-09-03 fabrication guard), which would have bet these and counted
  none of them. It reads `COALESCE(p.decision_odds, p.dk_odds)` now; the
  guard is unchanged in substance, because that is NULL only when no book
  priced the pick at all.
- **The app** carries `line_book`, says whose line it is on the pick's detail
  and line-movement copy, and bumps the settled-pick cache key (a cached row
  from before would claim DraftKings' line).
- **GAME markets are deliberately out.** DraftKings lists every game we
  model; the markets it does not list (MLB first-five spreads and totals, 114
  each since 08-28) have no model; and a game-level DraftKings line is a model
  FEATURE, so changing its source is a retrain question rather than a config
  one.
- **Flag:** `SCORE_OFF_ANY_BOOK_LINE=0` restores "no DraftKings quote, no
  pick".

**These picks have no settled record yet**, and every cut in this repo was
swept on DraftKings-lined picks. `line_book` is what keeps them separable:
report them on their own before folding them into any model's record.
