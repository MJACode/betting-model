# The live prop model changed market: rushing attempts, the under

**2026-09-21.** The live player-prop model traded live PASS attempts from
2026-09-05. It went 6-16 for -10.62 units, and 4-13 on 2026-09-20 alone. This
records why that market cannot be fixed, what replaced it, and — as plainly as
the evidence allows — what is still not known about the replacement.

Reproduce every number here, in order, with no API credits spent:

```bash
python scripts/nfl_live_prop_state.py        # join state to the quote archive
python scripts/nfl_live_prop_rule.py         # the rule, season by season
python scripts/nfl_live_prop_staleness.py    # is it just catching stale prices?
python scripts/nfl_live_prop_feasibility.py  # the fitted alternative, for contrast
```

---

## 1. Why the old market was not fixable

The deployed model priced every quote with `over_prob(q.line, None,
seconds_remaining)`. Three defects in one call:

- **It never knew what the player had already done.** `accrued` was passed as
  `None` — so the model could not tell a line the quarterback had nearly
  reached from one he would have had to double his pace to clear.
- **It returned a constant.** 0.600344 on every quote in every game, which made
  the expected-value threshold a pure price filter.
- **Its constants were default argument values**, bound once at import, so
  editing the shipped number changed nothing.

Bucketing its own 2026 bets by what they actually required at the moment they
were placed shows the consequence:

| the over needed | bets | wins | units |
|---|---|---|---|
| **over 1.25x his pace (a surge)** | 5 | **0** | **-4.00** |
| 1.0 - 1.25x | 6 | 2 | -2.13 |
| 0.8 - 1.0x | 2 | 0 | -2.00 |
| under 0.8x (easy) | 9 | 3 | -1.26 |

Jayden Daniels needed 0.57 attempts a minute having thrown at 0.39, and
finished on 17 against a line of 31.5. Four more bets were placed before the
quarterback had thrown a single pass.

**And the market itself carries no edge.** Re-measured on 39,901 archived
quotes across 849 games, the 2.33-attempt book bias the model was built on is
**-0.12, 95% CI (-0.42, +0.18)**. Betting pass-attempt unders on the
feasibility rule below returns **-2.8% pooled**, and 2023 / 2024 / 2025 disagree
in sign. There is no threshold that rescues it.

---

## 2. What the archive says the book does misprice

Every archived DraftKings quote, bucketed by how much more pace the over still
needed than the player had actually been managing, against what the book
charged for it:

| the over needed | quotes | over hit | book charged | gap |
|---|---|---|---|---|
| under 0.6x | 772 | 62.2% | 52.0% | **+10.1pp** |
| 0.6 - 0.8x | 1,084 | 54.7% | 50.2% | +4.5pp |
| 0.8 - 1.0x | 1,151 | 50.0% | 50.1% | -0.1pp |
| 1.0 - 1.25x | 1,066 | 44.5% | 49.5% | -5.0pp |
| 1.25 - 1.6x | 925 | 37.8% | 49.1% | **-11.3pp** |
| over 1.6x | 971 | 41.4% | 48.8% | -7.4pp |

That is **rushing attempts**. The same table is far flatter for pass attempts
and completions, and only the extreme tail moves for receptions.

**Why a book would be wrong here.** A live line is re-hung mechanically off the
pregame number and the clock. Carries are the most game-script-dependent
counting stat in the sport: a back behind his line at halftime is usually
behind it because his team has been throwing, and the same script goes on
producing the shortfall. The book marks down for time elapsed and not enough
for the reason.

---

## 3. The rule, season by season

Bet the **under** when the over needs at least **1.25x** the pace the back has
been managing, at DraftKings, no worse than **-140**. One bet per player per
game — the archive snapshots every five minutes, and forty looks at one game is
not forty bets. Intervals resample **games**.

| season | bets | games | under hit | units | ROI | 95% CI |
|---|---|---|---|---|---|---|
| 2023 | 294 | 195 | 57.5% | +27.04 | +9.2% | (-2.3%, +20.6%) |
| 2024 | 321 | 170 | 57.3% | +25.68 | +8.0% | (-2.3%, +18.3%) |
| 2025 | 278 | 188 | 60.8% | +45.27 | +16.3% | (+5.1%, +27.3%) |
| **pooled (DraftKings)** | **874** | **546** | **58.6%** | **+98.36** | **+11.2%** | **(+4.9%, +17.6%)** |

Bonferroni-adjusted for the four markets examined, the interval is
**(+3.4%, +19.0%)**; 0.05% of bootstrap draws fall at or below zero.

**A plateau, not a peak.** Every threshold is positive: 1.0 → +7.8%,
1.1 → +8.8%, 1.25 → +11.0%, 1.4 → +7.4%, 1.6 → +8.6%, 2.0 → +11.8%.

**It is not stale-line capture**, which was the obvious objection — the archive
stores a snapshot only every five minutes.

| | bets | ROI |
|---|---|---|
| the first qualifying quote | 874 | +11.2% |
| the second, ~5 min later | 318 | +9.7% |
| the third, ~10 min later | 161 | +11.7% |
| quotes where the book had **not** moved | 68 | **+23.7%** |
| quotes where the book **had** moved | 113 | +12.1% |

No decay, and the profit is strongest where the number had not moved. Nothing
here races anybody.

---

## 4. What the model emits

`nfl/live_model/models/rush_attempt_pace.py`. Inside the selected population,
neither the size of the required surge (p=0.45, and wrong-signed) nor the
book's price (p=0.19) is significant — **the edge is in the selection, not in a
gradient within it**. So the model is an offset on the book's own number and
nothing more:

```
logit P(under) = logit(book's de-vigged under) + delta
```

`delta` is the single estimated quantity: **0.3655**, 95% CI (0.229, 0.502)
clustered on game, z = 5.24. **Deployed at 0.25** — a haircut just above the
interval's lower bound, following the same convention the old model should have
used. It beats the market on both proper scoring rules (log loss 0.6778 against
0.6942; Brier 0.2424 against 0.2505).

The gates, in order: at least 240 seconds left, at least one carry recorded, the
line not already passed, a price no worse than -140, both sides quoted, and the
pace ratio at or above 1.25.

**Where the accrued count comes from.** ESPN's site boxscore carries `CAR` per
player, but core is the only host that answers the Railway worker, and core's
per-athlete statistics endpoint 404s. Core's competition `leaders` document
reads `"18 CAR, 81 YDS, 1 TD"`, and against every rush-attempt prop DraftKings
listed on 2026-09-18 it covered **79 of 82 players (96.3%)**; the three misses
were backups with almost no carries. **A miss is safe**: a player with no
accrued count is declined, never priced, so a name-matching failure costs a bet
and can never cause one at the wrong number.

**The halftime population exists in production, measured rather than assumed.**
The edge sits at a median of 30 minutes left, which is halftime and the start
of the third quarter, and `fetch_live_events` keeps only games the core host
reports as `state="in"`. Asked of the running system rather than a fixture: of
the 29 live BETs the worker has actually written, **5 were placed within a
minute of the halftime whistle** (game clock 1800s) and 6 fall in the 25-35
minute band. Core reports halftime as live and the worker prices it.

One difference worth knowing: production's pricing skews EARLIER than the
archive's (median 44 minutes left against 30), because it polls from the first
snap. Early quotes are mostly declined by the pace gate -- two minutes into a
game a back's measured pace is one carry over a tiny window -- so the deployed
bet count will be lower than the archive's per game.

---

## 5. What is not known

**There is no holdout.** The 1.25 threshold predates the archive — it came from
bucketing the deployed model's own 2026 losses — but the **market** and the
**side** were both chosen by reading the pooled table over all three seasons.
The per-season agreement in §3 is a consistency check on data the rule has
already seen, not an out-of-sample test.

**2026 is the first genuine test and it has not happened.** The worker has only
ever bought pass attempts, so no 2026 rushing quote exists to grade.

**A fitted six-feature version of this does not replicate.** Fitting a
market-anchored logistic per market and walking it forward gave +13.4% on 2025
carries and **+0.8% on 2024 carries** over 1,897 bets. The two numbers are not
in conflict: that model bet both sides on every snapshot, so its overs and its
forty-fold repeated quotes diluted the under edge away. It is recorded here
because a reader who runs `nfl_live_prop_feasibility.py` will see it, and
because it is the reason this model has one degree of freedom rather than six.

**The settled record does not transfer.** The 22 settled pass-attempt picks
stay exactly as they are (CLAUDE.md §1c) and still settle against attempts —
`picks.prop_market` now resolves the stat per pick rather than per model id. The
rushing population starts at **zero settled bets**, so the go-live gate question
(≥50 settled, positive flat ROI, calibration ≤5%) is open again.

**Not measured, and next.** The over at a LOW pace ratio is the other half of
the table above (+10.1pp below 0.6x) and has not been tested. One edge shipped
honestly beats two half-measured.
