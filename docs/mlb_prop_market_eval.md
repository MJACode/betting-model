# The market-relative rule does not transfer to MLB

Status: **measured and closed, 2026-09-07.** `mlb_prop_market` is NOT wired and
should not be wired on this evidence. It stays in the repo as a library.

This is the MLB counterpart of `docs/nfl_props_model.md` §5c. The construction is
identical — de-vig Pinnacle, bet DraftKings where it disagrees by more than the
juice — and the shared arithmetic lives in `models/market_relative.py`. On NFL it
returns **+10.33% over 954 bets**, positive in all three seasons and replicated
blind. On MLB it does not work.

---

## 0. Why this was measured at all

`models/mlb_prop_market.py` was built in #366 and had **never produced a pick**:
no card script, no scheduler job, no pipeline step, no `config.py` entry, and no
settlement mapping. It was a library nothing imported. That was found on
2026-09-06 while answering why NFL props were silent for Week 1 — at which point
`select count(*) from picks where model_id like '%prop_market'` returned **0**
across all three sports.

The obvious next step was to wire it. This document is why that did not happen.

---

## 1. Two things had to be fixed before any number meant anything

**The loader read in-play prices.** `load_quotes` excluded
`snapshot_type='in_play'` and stopped there, but the prop ingestor keeps
snapshotting after first pitch and labels those rows `open` — 5,583 of 24,034
DraftKings `batter_total_bases` rows, **23%**. Ordering by `snapshot_at DESC`
then preferentially selected exactly those. Measured against DraftKings' own
de-vigged probability:

| | n | actual over | DK implies | gap |
|---|---|---|---|---|
| unbounded | 1,585 | 24.7% | 34.9% | **−10.1pp** |
| pre-game bounded | 1,116 | 41.6% | 41.7% | **−0.2pp** |

Qualifying bets at a 5pp cut fell from 291 to 37. **Seven of every eight "edges"
the rule would have bet were this bug.** Fixed in #534.

Two things about how that was found are worth keeping. The −10.1pp gap is the
same fingerprint that condemned NFL tackles+assists (§5b, −9.1pp, one-sided) —
*our number disagrees with the book's own price by a lot, in one direction*.
And the first suspicion fell on our data, which was wrong: `player_game_log` was
checked against the official MLB box scores for 2026-09-05 and is **exact**, 321
of 321 batter lines matching on total bases and at-bats. The column was right;
the reader was wrong. Check the reader before the source.

**There was almost no history.** Pinnacle MLB prop coverage began 2026-08-27 —
ten dates. `backfill_mlb_prop_odds` (#534, hardened in #535) bought
2026-04-01 → 08-26: **145 dates, 1,919 games, 75,548 rows, ~92k credits.**

---

## 2. The result

158 dates, 2026-04-01 → 2026-09-05. 6,931 graded selections at the 2pp floor
(701 unmatched to a game log, 9%). One bet per proposition, pushes returned,
graded at the DraftKings price actually quoted.

| min edge | bets | win% | units | ROI |
|---|---|---|---|---|
| 2pp | 6,931 | 51.0% | −277.8 | −4.01% |
| 3pp | 3,286 | 50.5% | −167.2 | −5.09% |
| 4pp | 1,298 | 51.6% | −40.4 | −3.11% |
| 5pp | 511 | 49.9% | −28.3 | −5.53% |
| 6pp | 182 | 51.6% | −1.0 | −0.54% |
| **7pp** | **76** | **53.9%** | **+5.4** | **+7.11%** |
| 8pp | 30 | 46.7% | −1.1 | −3.54% |

**The 7pp cell is not an edge and must not be taken.** §7 requires a plateau,
not a peak: its neighbours are −0.54% and −3.54%, it rests on 76 bets, and it is
the single positive cell in a grid that is otherwise negative everywhere. This
is precisely the shape the NFL threshold work warned about — selecting 6pp
greedily on 2023-24 returned −0.46% blind on 2025.

**The time split confirms it.** Every threshold is negative in BOTH halves:

| min edge | early bets | early ROI | late bets | late ROI |
|---|---|---|---|---|
| 2pp | 3,876 | −1.93% | 3,055 | −6.64% |
| 3pp | 1,978 | −1.56% | 1,308 | −10.42% |
| 4pp | 826 | −1.02% | 472 | −6.77% |
| 5pp | 308 | −5.56% | 203 | −5.48% |
| 6pp | 90 | −0.52% | 92 | −0.57% |

**And the month split.** At 3pp: −5.23 / +0.65 / −4.42 / −6.93 / −10.87 /
−25.56. Five of six negative, and the one positive month is +0.65%.

---

## 3. What this says, and what it does not

**It does not weaken the NFL result.** That rests on its own 954 bets, its own
placebo test across six reference books, and its own blind season. Nothing here
touches it.

**It says the edge is specific to a market, not to the construction.** The
honest reading is that DraftKings prices MLB props close to Pinnacle — which the
NFL document's own placebo table hints at from the other direction: with
DraftKings as the *reference*, NFL returned −1.88%, i.e. DK is not a soft book
in general, it is soft on NFL player props specifically. On MLB, the two books
appear to agree often enough that the residual is noise plus juice.

**`pitcher_outs` is roughly flat throughout** (+6.2u at 3pp, +13.8u at 4pp) and
`batter_total_bases` carries most of the loss (−96u at 3pp). Do not read that as
a per-market opportunity: it is four markets sliced after the fact from a
negative pool, which is exactly how §5b's tackles result was manufactured. If
anyone wants to pursue `pitcher_outs`, it needs its own pre-registered test.

---

## 4. What was NOT done, deliberately

- **`mlb_prop_market` was not wired.** No card, no scheduler entry, no
  `config.py` threshold, no settlement mapping. All of that was scoped and then
  not built, because the measurement came back negative.
- **No threshold was borrowed from NFL.** The module ships no default on
  purpose; that is still correct.
- The 5 markets traded are the ones above `MIN_COVERAGE` 10%; widening the set
  was not tried, because a negative pool does not become positive by adding
  thinner markets.

## 5. If this is revisited

The measurement is reproducible in one command:

```bash
python -m scripts.mlb_prop_market_sweep --start 2026-04-01 --end 2026-09-05
```

The history is in `player_prop_odds` and stays there — it is paid data and
CLAUDE.md §1b says extracted data lives in Supabase. Re-running the backfill
skips dates already stored rather than re-buying them (`skip_existing`).

The thing that would change the answer is a genuinely soft MLB book. The rule's
`SOFT_BOOKS` is DraftKings alone, because DK is what every threshold, settlement
and CLV measure in this repo is pinned to (§6). Testing a book we do not bet is
cheap and is the obvious next experiment — but note the NFL finding that adding
books bought 51% more bets for 1.4% more units, so breadth is not where the
money was there either.
