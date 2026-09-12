# Can the paused models be made profitable? The assessment, 2026-09-12

> **mike, 2026-09-12:** *"I didn't fucking tell you to pause the NCA models. I
> said find profitable cuts. Find profitable models. I want profitable
> backtest... I need you to always run an assessment if these models can be
> profitable. That is the whole point."*

CLAUDE.md §1b now carries that as a standing rule: a losing model is an
assessment to run, not a model to pause, and "shall we unpause it?" is never
the question. This file is the first run of that assessment, over **seventeen**
models — the fifteen in `config.PAUSED_MODELS` and the two the 250-bet review
paused on its own the day before.

```bash
python -m scripts.paused_model_assessment                      # both pause registers
python -m scripts.paused_model_assessment --model mlb_runline --grid
python -m scripts.paused_model_assessment --all                # every model
```

## The answer, in one line

**No model has a cut that clears the standards on the artifact that is actually
deployed.** Three cuts clear on pooled history, and all three collapse to
between 0 and 19 settled bets once the record is scoped to the model currently
live. The two NCAAF live models now have a real answer instead of a small one:
a full out-of-sample season replay puts them at −3.4% and −13.1%. Nothing is
shippable today, and the rest of this file is what would have to change.

## The standards a cut has to clear

All of them are the repo's own scar tissue (§7, `docs/rules_evidence.md`):

1. **The whole graded universe** — BET, AVOID and dead-zone NONE alike. A
   BET-only sample contains only picks that already cleared the live bar.
2. **25+ settled picks in the cell.** Below that an ROI is a number, not a
   result.
3. **A plateau, not a peak** — at least 4 of 8 neighbouring cells positive.
4. **The time split** — positive in BOTH halves of the model's own era.
5. **The era.** Added while running this, because it changed the answer: a
   record measured across a retrain describes a blend of the live model and its
   dead predecessors. Every candidate is re-graded on
   `model_registry.trained_on WHERE is_active`.

A confidence interval is printed beside every cell. It is not a gate — at these
sample sizes nothing would clear one — but it stops a headline being read as a
forecast.

## The result

| model | graded rows | rows on the live artifact | current cut record | verdict |
|---|---|---|---|---|
| `mlb_over_under` | 875 | 875 | 49-59 −12.2% | no cut clears (20 cells at 25+) |
| `mlb_prop_batter_hits` | 22,596 | 10,622 | 59-21 +9.5% | best cell fails the time split |
| `mlb_prop_batter_runs` *(auto)* | 23,486 | 1,134 | 378-180 −1.9% | peak, not a plateau; **0** settled at that cell since the retrain |
| `mlb_prop_batter_sb` | 6,197 | 4,136 | 4-2 −18.8% | no cut clears (33 cells) |
| `mlb_prop_batter_tb` | 12,042 | 5,082 | 31-12 −5.2% | no cut clears (88 cells) |
| `mlb_prop_pitcher_er` | 2,074 | 2,074 | 110-86 −0.6% | peak, not a plateau (1 of 8) |
| `mlb_prop_pitcher_k` *(auto)* | 2,184 | 133 | 194-166 −1.4% | 0.54/0.16 clears pooled (75-59, +3.5%); **19** settled since the retrain, −0.6% |
| `mlb_prop_pitcher_walks` | 2,408 | 1,585 | 80-62 −2.5% | no cut clears (84 cells) |
| `mlb_runline` | 1,438 | 252 | 18-11 +10.2% | 0.70/0.08 clears pooled (17-10, +5.7%); **3** settled since the retrain |
| `ncaaf_live_total` | 60 BETs only | 0 | 30-25 +1.7% | **season replay: −3.4% over 280 bets** (below) |
| `ncaaf_live_win_prob` | 6 BETs only | 0 | 4-2 +8.1% | **season replay: −13.1% over 51 bets** (below) |
| `ncaaf_moneyline` | 0 settled | 0 | — | nothing to sweep |
| `ufc_total_rounds` | 8 BETs only | 8 | 4-4 −13.6% | nothing to sweep |
| `wnba_over_under` | 0 settled | 0 | — | nothing to sweep |
| `wnba_prop_player_points` | 1,670 | 782 | 61-53 −0.6% | best cell fails the time split |
| `wnba_prop_player_threes` | 1,381 | 680 | 50-40 −15.5% | 0.74/0.12 clears pooled (21-9, +6.1%); **8** settled since the retrain |
| `wnba_spread` | 6 BETs only | 6 | 2-4 −35.8% | nothing to sweep |

*(auto)* = paused by `tracking/threshold_review.py` at the 250-bet milestone on
2026-09-11, not by a person. Both registers are swept; sweeping only
`config.PAUSED_MODELS` had missed exactly the two models most in need of it.

## Why the era check changed the answer

`mlb_prop_pitcher_k` is the case worth keeping. Pooled over everything since
May, the cut 0.54/0.16 is **75-59, +3.5%**, positive in both halves (+4.5% then
+2.3%), 5 of 8 neighbours positive — a clean pass on the first four standards.
But that record spans **three** artifacts (2026-05-14, 06-07 and 09-03), and on
the one actually deployed it is **19 settled bets at −0.6%**. The same collapse
happens to `mlb_runline` (27 → 3) and `wnba_prop_player_threes` (30 → 8).

So the pooled numbers are not evidence about the models we are running. They
are evidence that this shape of cut is worth watching on the next few hundred
settled bets, which is what `tracking/threshold_review.py` is for.

## What the "no cut" models are telling us

`mlb_prop_pitcher_er` is the clearest: its best cell is +2.5% over 156 settled
with **one** of eight neighbours positive, and every cell with real volume sits
between −2% and +2.5%. A grid flat around zero everywhere is not a threshold
problem — the model has no edge to cut for, and the fix is features or a
different model, not a different number. `pitcher_walks`, `batter_tb` and
`batter_sb` have the same shape.

## NCAAF in play: the backtest was run, and both models lose

The forward record was never going to settle this: the live models write no
dead-zone rows by construction, so the only population was their own 60 settled
bets. mike approved the season purchase on 2026-09-12 and it came to **8,360
credits, not the 373,240 planned** — 5,765 of the season's in-play snapshots
were already in Supabase from an earlier run and the ingestor's resume skipped
every one of them. The stored season is 57,979 rows over 736 games,
2025-08-23 to 2026-01-20.

The replay (`scripts/ncaaf_inplay_history_backtest.py`) then ran the production
pricing path over every stored snapshot. 2025 is out of sample for the live
artifact: Stage 1 trained through 2024 and held 2025 out.

**Fresh quotes only** — the ones production can actually take, where the score
has not moved since the book's own last update:

| | candidates | production cut (prob ≥ 0.66, EV ≥ 0.22) |
|---|---|---|
| `ncaaf_live_total` | 32,304 | **280 bets, 146-134, −9.50u, −3.4%** |
| `ncaaf_live_win_prob` | 27,920 | **51 bets, 26-25, −6.69u, −13.1%** |

And no cut in the grid rescues it. The best totals cell with 30+ bets is
prob ≥ 0.72 / EV ≥ 0.22 at **+3.1% over 54 bets**, with its neighbour at
+0.9% and the rest of the region hovering on either side of zero. That is a
flat surface, not a plateau.

Two things worth keeping from the run:

* **The all-quotes table reads +1.8% and is a trap.** It includes quotes the
  book had not re-hung since the last score — the score priced twice, which
  production already declines. The fresh-only table is the one to read a cut
  off, and it is −3.4%.
* **The probabilities are honest; the prices are not beatable.** In the
  calibration table every claimed band lands within a couple of points of its
  realised win rate (claimed 0.675 → 74.5% won in the 0.65-0.70 band, claimed
  0.934 → 94.8%), and every band still loses money. A well-calibrated model
  that cannot beat the vig is not a threshold problem.

So the pause stands on evidence now rather than on a slate, and the next move
for NCAAF in play is a better model, not a better cut.

## Re-run cadence

Run this whenever a paused or losing model comes up, and at minimum whenever
`tracking/threshold_review.py` fires a milestone. Nothing here writes a
threshold: that is a model update and carries `Updated-By:`.
