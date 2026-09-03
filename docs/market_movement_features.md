# Market movement as a feature

Built 2026-08-31 (mike: "yes build the market movement features"). The
computation is live in `features/market_movement.py` and tested; **no model
consumes it yet**, for a reason the coverage numbers make unavoidable.

## Why

Across every feature engine the only market-derived inputs are `total_line`,
`spread_home`, `implied_team_total` and `implied_opp_total` — four static numbers
from one snapshot of one book. The models price against a market they are never
allowed to watch move.

Measured on MLB, DraftKings h2h, games with ≥4 pre-game snapshots, bucketed by
how the home implied probability moved from the first pre-game snapshot to the
last:

| Movement | Games | Avg opening prob | Home win rate |
|---|---|---|---|
| Away steamed >3pp | 166 | 0.552 | **49.4%** |
| Away drift 1–3pp | 334 | 0.550 | 52.7% |
| Flat (<1pp) | 551 | 0.550 | 50.8% |
| Home drift 1–3pp | 316 | 0.549 | 55.4% |
| Home steamed >3pp | 167 | 0.550 | **55.1%** |

Every bucket opens at essentially the same price, so this is not team strength in
disguise — yet the realised win rate spans six points, monotonically. Beat-the-close
is 0 to −4pp in every bucket, the ordinary finding that the closing line is
efficient: the move is not to beat the close but to **read** it.

## The features

`MARKET_MOVEMENT_FEATURES` in `features/market_movement.py`:

| Feature | What it is |
|---|---|
| `mkt_open_implied_home` | opening pre-game price, as a probability |
| `mkt_move_home_pp` | latest − open, signed, in probability points |
| `mkt_move_abs_pp` | magnitude, direction discarded |
| `mkt_book_disagree_pp` | spread across books, each at its own latest pre-game price |
| `mkt_snapshots` | how many pre-game snapshots were seen |
| `mkt_total_move` | latest total_line − opening total_line |
| `mkt_spread_move` | latest spread_home − opening spread_home |
| `mkt_sharp_devig_home` | Pinnacle's no-vig home probability |
| `mkt_dk_vs_sharp_pp` | DK implied − sharp no-vig |

Rules the module holds to: **pre-game twice over** (`snapshot_type <> 'in_play'`
AND `snapshot_at <= commence_time`, because the evening refresh keeps writing
`open` rows after first pitch); **train and serve compute the same thing**
("latest" always means latest pre-game); and **missing is `None`, never `0.0`** —
"the line did not move" and "we saw it once" are different facts, and conflating
them teaches a model that absence is a signal.

## The constraint that decides everything — measured, not assumed

MLB pre-game rows by book:

| Book | Rows | Games | Distinct snapshot times per game | First seen |
|---|---|---|---|---|
| sbr_consensus | 231,996 | 40,488 | **1.00** | 2009-04-05 |
| draftkings | 151,841 | **1,908** | **23.6** | 2026-04-05 |
| fanduel | 3,334 | 106 | — | 2026-08-26 |
| espnbet | 3,277 | 106 | — | 2026-08-26 |
| williamhill_us | 3,266 | 105 | — | 2026-08-26 |
| bovada | 3,178 | 75 | — | 2026-08-27 |
| betmgm | 3,005 | 104 | — | 2026-08-26 |
| pinnacle | 2,465 | **73** | — | 2026-08-27 |

Three things follow, and they are not negotiable:

1. **The 17 seasons of history carry no movement.** `sbr_consensus` is exactly
   one snapshot per game — a single consensus line, 2009 to 2026. There is
   nothing to difference.
2. **Movement exists for 1,906 MLB games, all in the 2026 season.** That is the
   entire trainable universe for these features, and it is disjoint from where
   the current game models train (2019–2024, holdout 2025). Adding the columns to
   an existing model would delete every pre-2026 row through `dropna` — the same
   trap as the 2019 Savant gap, and a bigger one.
3. **The sharp prior cannot be trained at all yet.** Pinnacle has 73 MLB games
   and five days of history. Only 49 games carry both a DK and a Pinnacle
   two-sided pre-game quote. It accumulates from here; revisit at ~500 games.

## So the activation is a new model, not a retrain

Not `mlb_moneyline` plus nine columns. A **market-aware model trained on 2026
alone**, roughly 1,900 games, judged against the existing model on the same
window. Small, which argues for keeping the feature set small — nine columns is
already the right order — and for a strict in-season time split rather than a
single holdout.

Steps, when someone runs it on a machine with `DATABASE_URL`:

1. Build the matrix: `load_market_movement(conn, "MLB")` merged onto the existing
   2026 feature rows by `game_id`.
2. Check coverage per month before training. `mkt_move_home_pp` needs ≥2 priced
   DK snapshots; April may be thinner than August.
3. Train on 2026 with a chronological split (first 60% train, last 40% test) —
   not a random one. Every finding in this repo that survived a time split was
   real and most that did not, were not.
4. Compare against the incumbent **on the same 2026 games**, or the comparison
   measures the season change rather than the features.
5. Only then decide whether it earns a threshold and a place on the board.

Until that happens these features cost nothing and change nothing — which is the
correct state for a feature whose training data is one season old.
