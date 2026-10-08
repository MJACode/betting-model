# NHL models: closing-line value and expected value, assessed (2026-10-08)

mike, 2026-10-08: *"assess all NHL models and optimize for CLV and expected value."*

Every number below comes from a query, a worker run, or a re-run of a committed
script. Each section names its source. Results are in units at one unit flat.
"Units a season" is total units divided by the three priced seasons
(2023-24, 2024-25, 2025-26). It is the quantity expected value is maximised on.
Return per bet is shown beside it, never instead of it.

Where it ran:
- Read-only SQL against production (the Supabase connector).
- Two worker runs of the new `nhl_research` job (#894, #895). Their output is on
  `worker_jobs` rows 444241, 444242 and 444467.
- Local re-runs on the cached three-season data an earlier session left on this
  machine.

Every positive claim was given to two independent verifiers: one re-checked the
data and the grading, the other the statistics and whether live could run the
rule. Claims that did not survive are marked as refuted, with the reason.

## The results table

| model | status | what the evidence says | live 2026-27 (BETs, settled) | CLV |
|---|---|---|---|---|
| `nhl_moneyline` | live, but has bet nothing since 10-04 | No cut clears on 2025-26 (every neighbourhood cell -0.3% to -19.5%). The rule as it runs now finds **0 bets at DraftKings and 2 at the best price** in the whole holdout season. Its predictions are worse than DraftKings' de-vigged line (log loss 0.6884 vs 0.6836). | 6 bets, 1-5, -3.80u. 5 of 6 were never shown to members. | Stored -1.30 pp; at the price actually taken, -3.44 pp on 5 (one off-market quote excluded) |
| `nhl_moneyline_regulation` | live, own probability since #876 | No cut clears: own-probability EV cuts 0.00 to 0.20 lose -4.7% to -20.3% on 47-859 bets. As it runs: 21 bets -11.2% at DraftKings, 47 bets -12.7% at the best price. Live it fires on about 18% of games against 3.5% in the backtest, because it locks the first qualifying quote out of about 18 looks, up to 72h out. | 25 bets, 23 settled, 5-18, -9.10u. 18 of the 19 bets before #876 were never shown to members. | At the price bet, -1.73 pp, beat the close 6 of 23; EV at Pinnacle's close -4.7% a bet |
| `nhl_over_under` | registered, never trained | Every fitted model and every blind side loses on the full-game total. One market-anchored rule has positive CLV in all six seasons, at about +1.3% (EV ≥ 0.01) to +2.4% (0.02). That rule bets soft books that lag Pinnacle's no-vig price. Its ROI does not clear: +4.72% on 1,276 bets, CI -0.6..+10.1. | none | none |
| `nhl_puckline` | registered, never trained | The best lab result is a peak (+11.8% at one cut, neighbours -0.4% and +5.5%, one season losing at every cut). About 0 units expected. | none | none |
| `nhl_prop_blocked_shots` | live | Alone at 0.18: 532 bets +6.5% (-2.1..+15.2), 2023-24 -1.0%. DraftKings is the only book posting it live. It posts about 60 minutes before puck drop, by which time the overnight picks have usually filled the night. | 4 bets, 2-2, +0.25u. None since 10-03. | 0.00 on all 4, **by construction**: the bet quote is also the close |
| `nhl_prop_saves` | live | The steadiest: alone at 0.18, 783 bets +14.0% (+7.1..+20.6), every season +13% or better. It survives the live book set (DraftKings and Hard Rock only: +13.3%). Posted only in the 70-minute close, so overnight shots-on-goal picks can starve it. | 15 bets, 9-6, +2.03u. Current rule: 5 bets, 1-4, -3.17u. | Not usable: mostly same-instant, or the decision snapshot itself |
| `nhl_prop_shots_on_goal` | live | Weaker than published once shared names are refused. Alone at 0.18: 885 bets +6.1% (-0.6..+12.6). At 0.10: +4.4%, 2025-26 +1.4%. Strong only at a high EV (0.25: 192 bets +24.0%). | 52 bets, 51 settled, 29-22, +4.68u. Current rule: 6 bets, 1-4, -3.09u. | At the price paid against Pinnacle's close: EV +0.18% (n=37), i.e. break-even |
| `nhl_prop_assists` | live | Alone at 0.18: 213 bets +16.8% (+1.7..+30.6), but only 20 in 2024-25. Calibrated where it bets. Unders only is right: its overs lose. | 5 bets, 2-3, -0.97u. None under the current rule. | 1 of 5 is a real lock-to-close measure |
| derivative totals (team, alternate, first period) | built, not registered | The published grade has two defects. Team totals were graded on regulation goals, while every book prices full-game goals; on full-game goals the same unders lose. The alternate and first-period grades paid a push as an under win. Not re-graded. | none | none |
| anytime goalscorer (no model) | candidate | The lab's "+10.0% on 6,656" is inflated by the same name defect below (+254u on 93 bets from the two Elias Petterssons). Corrected, about +6.3%, and it leans on FanDuel, which production does not shop. | none | none |
| regulation draw, Pinnacle against the soft books (no model) | candidate | Positive in all three seasons, but no interval clears zero. Realised profit was about 3x what Pinnacle's own prices implied. DraftKings has since priced it out: 0 of 2,358 same-fetch prices qualify this season. | none | none |

## The defect that inflated the prop evidence

The prop backtests matched each price to a player by name only (`name_key`).
Two pairs of players share a name:

- **Elias Pettersson:** two Vancouver players, a forward and a defenceman.
- **Sebastian Aho:** Carolina's forward and the Islanders' defenceman.

A price was therefore attached to both namesakes. The backtest bet the one with
the better EV, and so graded the forward's shots-on-goal under on the
defenceman's count. The damage:

- 124 bets at a 90% win rate, +89.8 units.
- Under the current rule (one bet a game, two a night, EV ≥ 0.18): +60.9 of the
  +173.8 units the rule was justified on.

The live card was never affected: it refuses a name that matches more than one
player on either team. The backtests now apply the same test
(`scripts/nhl_prop_backtest.namesakes`, #895). Corrected, at most 3 a game:

| | Bets | Return per bet | 2025-26 |
|---|---|---|---|
| EV ≥ 0.10, before | 4,210 | +5.4% | — |
| EV ≥ 0.10, after | 4,144 | +3.9% | +1.7% |
| EV ≥ 0.20, after | 577 | +10.2% | — |

## The four prop models together, corrected (worker run 444467)

`scripts/nhl_prop_ev_lab.py` on production, shared names refused. It reads
every priced side at every bettable book, takes the card's rule (unders, own
probability, -200 floor, best EV per player-game) and applies each cap in the
card's order: best EV first, one a game, then the nightly limit. Units are
units a season. Intervals resample whole game days.

**Floor × bets a night, one bet a game**

| EV ≥ | per night | bets a season | units a season | return per bet (95%) | bets a night | 2023-24 / 24-25 / 25-26 |
|---|---|---|---|---|---|---|
| 0.18 | 2 (**today**) | 270 | **+38.8** | +14.4% (+7.7..+21.2) | 1.8 | +10.5 / +10.2 / +23.6% |
| 0.18 | 3 | 360 | +46.1 | +12.8% | 2.4 | +11.4 / +9.6 / +18.3% |
| 0.18 | 4 | 422 | +54.6 | +12.9% (+7.4..+18.7) | 2.8 | +12.7 / +10.1 / +16.7% |
| 0.18 | 6 | 495 | +56.8 | +11.5% | 3.3 | +11.1 / +9.2 / +14.8% |
| 0.18 | none | 538 | +65.6 | +12.2% (+7.3..+17.2) | 3.6 | +11.6 / +10.2 / +15.5% |
| 0.15 | 4 | 510 | +68.4 | +13.4% (+8.4..+18.4) | 3.1 | +14.9 / +12.0 / +13.2% |
| 0.15 | none | 735 | +86.0 | +11.7% (+7.4..+15.9) | 4.5 | +13.3 / +9.7 / +12.1% |
| 0.12 | none | 961 | +82.2 | +8.6% | 5.6 | +10.5 / +6.8 / +8.2% |
| 0.10 | none | 1,081 | +74.1 | +6.9% | 6.2 | +9.5 / +5.4 / +5.4% |

Read it as a neighbourhood:
- Every looser nightly cap earns more units a season than today's, in every
  season. Paired by night on the same corrected bets (independent verifier):
  - one a game, no nightly cap, gains **+29.6 units a season (+9.4..+50.4)**;
  - four a night gains **+23.4 (+9.1..+38.6)**;
  - three a night gains +9.3 (-1.4..+20.1), which does not clear zero.
- With one bet a game, the units-a-season peak is the 0.12-0.15 floor
  (+82 to +86). Below 0.12 the extra bets return less than they add in volume.
- More than one bet a game adds units at a falling return. At 0.15: 2 a game
  +114.0, 3 a game +124.5. At 0.10 with no cap at all: +173.9, but 18 bets a
  night and +3.3% in 2025-26. Same-game unders correlate weakly (+0.02); the
  4th and later bets in a game are near zero at 0.18.
- Risk scales with the units: units a season over the season-to-season spread
  is flat across rules (3.2-3.7). Worst single night: -2.0 units today,
  -5.3 with no nightly cap at 0.18.

**Two caveats, both lowering every level by roughly 10-20% without changing
the order:**
1. 28% of the backtest's bets at today's rule are at a book that posts no line
   for that market live (BetMGM saves, BetRivers and Caesars shots on goal).
   Restricted to books that do post live, today's rule is +35.5 units a season,
   and one a game with no nightly cap is +56.5.
2. The backtest takes each night's best bets. Live fills first-come, which is
   worse for today's rule (see timing, below). Removing the nightly cap mostly
   removes that problem too: a game's slot can be taken early, but no longer
   the whole night's.

**Each model alone, no cap (corrected)**

| model | EV ≥ 0.15 | EV ≥ 0.18 | EV ≥ 0.25 |
|---|---|---|---|
| saves | 1,072 bets +12.4%, all seasons +10..+15% | 783 bets +14.0% (+7.1..+20.6) | 345 bets +16.3% |
| shots on goal | 1,648 bets +5.1% (+0.2..+10.0) | 885 bets +6.1% (-0.6..+12.6) | 192 bets +24.0% |
| assists | 379 bets +16.6% | 213 bets +16.8% (+1.7..+30.6); 2024-25 has 20 | 55 bets |
| blocked shots | 900 bets +9.0% | 532 bets +6.5% (-2.1..+15.2); 2023-24 -1.0% | 127 bets +8.9% |

Shots on goal is the model the name defect flattered most. On its own it is
thin below an EV of about 0.20. Saves holds at every cut. The pooled rule
works because it ranks across the four models, and saves and assists win
many of those rankings.

**Not levers at today's rule**
- **Shopping FanDuel:** +1.9 units a season at today's caps, +2.7 with one a
  game and no nightly cap. FanDuel's history carries mispaired quotes, so these
  are upper bounds. FanDuel stays excluded.
- **Assists overs:** -2.5% at 0.10, -1.2% at 0.15. Unders only is right.

**2026-27 so far, deciding at the open against the close** (55 games). At EV ≥
0.10:
- 89 candidates qualify at the game's first stored price; 227 at the last.
- 156 qualify only at the close, mostly because the market was not posted
  earlier.
- On the 74 open candidates whose book still hung that line at the close, the
  open price won 11.2 units. The same bets at the close price would have won
  8.3.
- Against that book's own no-vig close, the open bets sit at -2.73 pp. A bet
  decided at the close sits at -3.78 pp, which is just the margin.

So deciding at the open buys about one point of price. It is not an edge
against the sharp close (see timing).

## What was measured about timing (closing-line value)

- **Game models — lock later? Refuted.** A no-edge underdog bet at T-2h instead
  of T-8h gains +0.3 to +0.45% of stake at the best price, in every season. But
  the live models lock 30-59h out, and across T-24h to T-2h the most recent
  season shows nothing (-0.03% best price, -0.42% DraftKings). 79% of the live
  bets are in the three-way market, which has one stored snapshot a game, so its
  timing cannot be measured. Two verifiers, both refuted. Nothing changed.
- **Props — the market does not drift toward the under from open to close.**
  Same book, same line, the no-vig under moves -0.4 to -0.7 pp toward the over at
  Hard Rock. Elsewhere it is within ±0.25 pp. The one real effect: when Hard
  Rock's overnight under is cheaper than the other books, it corrects by the close
  (+2.55 pp, n=25). The overnight picks beat Hard Rock's own close by +1.83 pp,
  but against Pinnacle's no-vig close they are +0.09% (n=14), i.e. nothing.
  16 of those 19 picks are from one night, under the old rules.
- **Props — the overnight pass takes the night's slots.** The first pass of each
  ET day (00:18 ET, about 19 hours before puck drop) sees only Hard Rock for
  shots on goal and assists. Saves and blocked shots are posted only about 70
  minutes before puck drop. Under first-come caps, the overnight picks fill the
  night: on 10-06 both slots went at 00:18 ET, and the evening pass logged "0
  bet(s) kept of 11 that clear". Choosing the night's best two by EV, instead of
  first-come, is +5.1 pp in the backtest at 0.18. Its paired interval is
  -0.5..+10.7, so the size is not established, and it shrinks to zero by 0.24.

## Closing-line value, as it is captured

Five defects, found by more than one assessment:

1. **Picks at a line DraftKings never hung got no CLV at all.** The capture
   filtered on `dk_odds IS NOT NULL`, so 30 NHL prop picks at Hard Rock were
   skipped. **Fixed in this change**: they close Pinnacle-first, then at the
   deciding book, graded at the price bet. These are the only rows of any model
   it touches.
2. **CLV is graded at DraftKings' price, not the price taken** when the pick was
   decided elsewhere. 17 of 23 regulation bets and 15 of 30 measured
   shots-on-goal bets. Not changed: it would change the published CLV of every
   model that shops books (a decision, below).
3. **The close is the decision snapshot** for every saves and blocked-shots
   pick, and for most evening picks. The ingestor buys only an open and a
   70-minute close, so those CLVs are zero (or a same-instant gap) by
   construction. A snapshot about 10 minutes before puck drop would fix it
   (a decision, below: it costs credits).
4. **Exact name matching** in the prop close lookup: Pinnacle's "Lafreniere"
   did not match DraftKings' "Lafrenière". Not fixed.
5. **Two start times.** Before a game, `games.commence_time` carries the feed's
   :10 time. After settlement it carries the NHL's scheduled :00. A close read
   before settlement can take a quote from the first ten minutes after the
   scheduled start. Whether those are in-play prices is not measured. Not fixed.

## Changes made

- #894: the `nhl_research` worker job (allowlisted, read-only NHL scripts) and
  `scripts/nhl_prop_ev_lab.py` (the four prop models together, in units a
  season, every floor × per-game cap × per-night cap).
- #895: the backtests refuse a shared name, as the card does.
- This change: CLV for the 30 picks at a line DraftKings never hung. The game
  grade now labels the row production actually runs. This document.

No threshold, cap, side, book set or model was changed.

## Decisions for mike

Recorded in `docs/followups.md` as `[needs-decision]` items. In order of units
a season:

1. **The nightly cap on NHL props.** Removing it (one bet a game stays) is
   +26.8 units a season on the corrected backtest. Raising it to four a night
   is +15.8. Both gains hold in every season. The cost is volume: about 3.6 bets
   a night on average with no nightly cap, at most one per game, against 1.8
   today. Lowering the floor to 0.15 as well is +47.2 units a season, at 4.5
   bets a night.
2. **A prop closing snapshot about 10 minutes before puck drop**, so CLV can be
   measured on saves, blocked shots and evening picks. About 6,600 credits a
   season (5 a game, measured).
3. **CLV at the price taken** for every model that shops books. It changes the
   published CLV of those models.
4. **`nhl_over_under` as a market-anchored paper model.** It would bet soft
   books that lag Pinnacle, and its CLV is positive in all six seasons. Its ROI
   interval still includes zero (+4.72%, -0.6..+10.1). About +3 to +4.5 units
   a season if it holds.

The game models need no decision. Neither has a cut that clears, and both stay
live (mike, 2026-10-01). The regulation model's measured cost at its live
firing rate is about -10 units a season.
