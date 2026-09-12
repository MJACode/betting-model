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
live. Nothing is shippable today, and the rest of this file is what would have
to change.

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
| `ncaaf_live_total` | 60 BETs only | 0 | 30-25 +1.7% | peak, not a plateau — and see below |
| `ncaaf_live_win_prob` | 6 BETs only | 0 | 4-2 +8.1% | nothing to sweep |
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

## NCAAF in play: the backtest exists, the data does not

`ncaaf_live_total` cannot be assessed properly for a structural reason: **the
live models write no dead-zone rows by construction** (a live game would write
hundreds a day), so the only population is its own 60 settled bets —
systematically optimistic and far too few. Its grid is flat: every cell from
0.66/0.00 to 0.66/0.08 is the same 55 bets at +1.7%, and everything above that
is a 12-bet corner.

The honest backtest is the one already built and never run: a 2025 season of
DraftKings in-play snapshots replayed through the production rule
(`data/ingestors/ncaaf_inplay_history.py`,
`scripts/ncaaf_inplay_history_backtest.py` — both written and tested on
synthetic data; dry-run 2025: **18,662 calls, 373,240 credits**). The Odds API
balance on 2026-09-12 is **2,178,760 credits remaining**, so the replay is about
17% of what is left this month. That spend is mike's call (§1b) and it is the
only route to a real backtest on this model.

## Re-run cadence

Run this whenever a paused or losing model comes up, and at minimum whenever
`tracking/threshold_review.py` fires a milestone. Nothing here writes a
threshold: that is a model update and carries `Updated-By:`.
