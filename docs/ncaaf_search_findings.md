# NCAAF Model Search — Findings

**Run date:** 2026-08-25
**Harness:** `scripts/ncaaf_search/` (reads production, writes nothing back)
**Status:** leak found, root-caused and FIXED; snapshots re-ingested; model
search to be re-run on corrected data

---

## 1. Headline

Two findings, one of which affects production.

**A. `ncaaf_team_stats` snapshots contained look-ahead information — FIXED.**
32.7% of all snapshots (40,194 audited, 2014–2025) reported a `games_played`
count higher than the number of games actually played before that snapshot's
`as_of_date`. The rate was stable at 30–36% in **every** season — a property of
the ingestion, not a recent regression.

`features/ncaaf_feature_engine.py` reads these snapshots with
`as_of_date <= game_date` for every production NCAAF feature, so this fed
straight into training. Same look-ahead class CLAUDE.md already documents for
the MLB pitcher backfill.

**Root cause.** CFBD restarts week numbering for the postseason: every bowl and
playoff game is `season_type='postseason', week=1`. The snapshot builder
selected completed games with `week < wk`, which from week 2 onward admitted
the ENTIRE postseason into every in-season snapshot. This was not a ±1
counting quirk — January playoff results were inside September features.

Ohio State 2024, before and after:

| snapshot | before | after | truth |
|---|---|---|---|
| 2024-09-04 | 5 games, 5-0 | 1 game, 1-0 | 1 game (Aug 31 vs Akron) |
| 2024-12-13 | 16 games, 14-2 | 12 games, 10-2 | 12-game regular season, 10-2 |

The old `5` was their opener plus four playoff games from that December and
January. The old `16 / 14-2` was the full national-title run, stamped on a
snapshot dated five weeks before it ended.

**Fix** (`data/ingestors/cfbd_ingestor._completed_before`): filter on DATE, not
week number — immune to week-numbering semantics. The other data path,
`/stats/season/advanced` with `startWeek`/`endWeek`, was verified clean
(`endWeek=2` returns 136 plays, exactly two games' worth; `seasonType=regular`
is identical).

**Post-fix audit: every season 2015–2025 reports a 0.0000 look-ahead rate.**

**B. Once leakage is controlled, no configuration beats the closing line.**
Every model family, every feature group, both targets: out-of-sample log loss
at or above ln(2) = 0.69315, the no-information floor.

---

## 2. The experiment that isolates the leak

Identical model, features and thresholds; the only difference is whether the
leakage guard is applied.

| ATS · XGB depth-3 · all features · threshold 0.03 | bets | win% | flat ROI | log loss |
|---|---|---|---|---|
| before guard | 329 | 58.4% | **+11.4%** | 0.69207 |
| after guard | 331 | 50.8% | **−3.1%** | 0.69477 |

The pre-guard result also failed three independent smell tests, all of which
pointed the same way before the guard was written:

* the harness's own `leak_suspect` flag fired (win rate > 55%)
* **CLV = 0.446** — the market moved *against* our picks more often than
  toward them, which a genuinely predictive model does not do
* per-season instability: 2023 produced 260 bets, **2025 produced zero**, and
  fold log loss degraded to 0.69549 (worse than ln2) by 2025

---

## 3. Full results after the guard

ln(2) = 0.69315. Threshold 0.03. Test seasons 2022–2025, expanding window.

### ATS (`home_covers`)

| config | log loss | bets | win% | ROI | CLV |
|---|---|---|---|---|---|
| market-only baseline | 0.69315 | — | 50.4% | — | — |
| all features, XGB | 0.69477 | 331 | 50.8% | −3.1% | 0.463 |
| clean features, XGB | 0.69363 | 52 | 61.5% | +17.5% | 0.466 |
| all features, logreg | 0.69326 | 0 | — | — | 0.430 |

### Totals (`went_over`)

| config | log loss | bets | win% | ROI | CLV |
|---|---|---|---|---|---|
| market-only baseline | 0.69319 | — | 49.6% | — | — |
| all features, XGB | 0.69487 | 216 | 50.9% | −2.8% | 0.455 |
| clean features, XGB | 0.69450 | 89 | 52.8% | +0.8% | 0.453 |
| all features, logreg | 0.69405 | 2 | 50.0% | — | 0.411 |

**The 61.5% / +17.5% ATS cell is not a finding.** It is 52 bets across four
seasons — 13 per season, with 2024 producing zero — which the spec itself
rules untestable ("an edge that only fires 10 times/season is untestable").

**CLV is below 0.500 in every configuration** (0.411–0.466). Consistently
failing to beat the close is the single most damning number here, because it
is independent of how thresholds are cut.

---

## 4. Regularisation probe — is the null real or over-shrinkage?

Run because a model pinned at p≈0.50 can mean "no signal" or "too much
penalty". It is the former.

| model | OOS log loss | bets @1% |
|---|---|---|
| logreg C=0.001 | 0.69353 | 0 |
| logreg C=0.05 | 0.69460 | 1364 |
| logreg C=100 | 0.69458 | 1836 |
| XGB depth-3 | 0.69207 (leaky) | 746 |
| LGBM depth-3 | 0.69432 | 730 |

Relaxing the penalty produces predictions with real spread but *worse* loss.
The single-fold check settles it:

```
unregularised, train ≤2024 → test 2025, 47 features
  in-sample log loss 0.68813   (below ln2 — signal found in training)
  OOS 2025   log loss 0.69699   (above ln2 — worse than guessing)
```

Memorisation without generalisation. Not over-regularisation.

---

## 5. Harness validation

The market-only sanity gate passed before any model was trained:

| target | win rate vs close | n | log loss |
|---|---|---|---|
| ATS | 0.5039 | 1020 | 0.69349 |
| totals | 0.4961 | 649 | 0.69319 |

Given only the closing line you cannot beat the closing line — as required.
Labels independently validated two ways: base rates `home_covers` 0.4944 /
`went_over` 0.4910 (n≈9.3k/9.0k), and our stored close agrees with CFBD's
Bovada close **exactly 99.6%** of the time (mean |diff| 0.017, n=4,265).

Leakage tests (`tests/test_ncaaf_search_features.py`, 12 passing) poison all
games from week 5 onward and assert every earlier rating cut is byte-identical,
with a control test proving later cuts *do* change so the assertion cannot pass
vacuously.

---

## 6. Two bugs found and fixed during the build

**FCS games inflated home-field advantage ~80%.** Unfiltered ridge put HFA at
+0.10 pts/play ≈ **+6.9 points/game**; real CFB home advantage is ~2.5–3.5.
FBS teams host FCS teams and bury them, so "home" partly encoded "talent
mismatch". Pooling FCS opponents into one `__FCS__` pseudo-team gives
**+3.68 / +3.92 pts/game** for 2023/24 and removes artefacts like Stephen F.
Austin ranking top-8 in offence.

**The first leakage guard was itself buggy** — it rejected 84.5% of snapshots
because `_true_prior_games` counted only a team's home (or only away) games,
roughly half the truth. Fixed; the true rate is ~31%.

Both were caught by testing against known ground truth, not by inspection.

---

## 7. Validation that the ratings measure something real

| season | best offence | best defence |
|---|---|---|
| 2023 | **LSU**, USC, Notre Dame, Oregon, Michigan | **Ohio State**, Michigan, Iowa, Penn State |
| 2024 | Notre Dame, Ohio State, Indiana, Miami | **Ohio State**, Texas, Notre Dame, Ole Miss |

LSU 2023 was the actual national #1 scoring offence (Jayden Daniels' Heisman
year); Michigan 2023 and Ohio State 2024 were the national #1 defences. The
opponent adjustment is measuring football, not noise — it simply is not
measuring anything the closing line has missed.

---

## 8. Results on CORRECTED data (the fair test)

Matrix rebuilt after the snapshot fix: 9,317 games, 8,505 usable ATS rows,
seasons 2015-2025 (2020 and 2014 excluded). The leakage guard now rejects
**0 / 9,317 (0.0%)** -- an independent confirmation, since the guard is a
different code path from the audit. `A_raw` and `C_roster` (SP+, talent,
returning production) are intact for the first time.

Market-only sanity gate passed in all three arms (ATS 0.5041 n=1208,
totals 0.5154 n=714).

### The one statistic that settles it

**CLV is below 0.500 in every row of every arm** -- 6 model families x 2
targets x 3 era arms, ranging 0.411 to 0.479. **Not one configuration ever
beat the closing line.**

CLV does not depend on where thresholds are cut, how many bets are taken, or
which season ran hot. If any of these models had predictive content, some
configuration somewhere would show CLV above 0.5. None does.

### Configs that clear the raw ROI test but fail everything else

| arm | config | bets | win% | ROI | ci_lo | CLV | bets by season |
|---|---|---|---|---|---|---|---|
| ATS full | xgb_d3 | 290 | 54.5% | +4.0% | 0.4873 | 0.436 | 0 / 149 / 141 / 0 |
| ATS full | xgb recency-wt | 437 | 54.7% | +4.4% | 0.5000 | 0.448 | 1 / 223 / 175 / 38 |
| ATS portal | xgb recency-wt | 166 | 54.8% | +4.65% | 0.4722 | 0.452 | 145 / 0 / 21 / 0 |

Every one has a confidence interval sitting below the 0.5238 breakeven, CLV
under 0.5, and bets concentrated in one or two of four seasons. The portal-era
candidate places 87% of its bets in a single season. That combination is the
signature of noise surviving a threshold sweep, not an edge.

### Ablation -- no feature group contributes

ATS, delta log loss vs the market-only baseline (negative = helps):

| group | delta | bets | ROI |
|---|---|---|---|
| A_adj | -0.00012 | 84 | -18.2% |
| A_raw | -0.00027 | 28 | +15.9% |
| B_decay | -0.00026 | 63 | +12.1% |
| C_roster | -0.00011 | 116 | -7.8% |
| D_market | +0.00045 | 117 | -7.0% |
| E_pace | -0.00065 | 29 | -7.8% |
| F_situ | +0.00185 | 344 | -3.4% |

Every delta is in the 4th-5th decimal place. Two groups actively hurt. The
positive-ROI cells sit on 28 and 63 bets.

**For totals, every single delta is POSITIVE** (+0.00096 to +0.00153) -- every
feature group makes totals worse than the closing total alone, and zero
configs clear the kill line.

### Verdict against the spec's kill criterion

NOT honestly met. Nothing survives the spec's own consistency requirement,
which it ranks above ROI ("prefer +2% in all four seasons over +8% in one").

`run_search.py` originally reported the ROI test in isolation and printed
"2 configs cleared" for candidates failing three other checks. That was a
reporting flaw capable of producing a false positive, and the verdict now
applies all five gates (volume, ROI, CI vs breakeven, CLV, season coverage)
with per-config failure reasons.

---

## 9. What this does NOT establish

The null now holds on CORRECTED data, so the "compromised inputs" caveat that
applied to the first pass is discharged. What remains genuinely untested:

* **Group C's QB features** -- QB continuity, QB-isolated EPA, backup-QB flag.
  These need player-level CFBD ingestion that does not exist. Only the roster
  priors (returning production, talent) were testable.
* **Market-structure spots** (`scripts/ncaaf_structure_scan.py`) -- a different
  hypothesis entirely: that inefficiency lives in schedule situations rather
  than team strength. Written, never run.
* **2014** -- unusable until CFBD fixes its endpoint 500.

Not yet run (and not recommended -- see section 10): Optuna hyperparameter search (≤200 trials/family/target),
LightGBM at scale, ensembles, isotonic-vs-Platt comparison, the portal-era-only
arm, and QB features (Group C is partial — QB continuity / QB-isolated EPA /
backup-QB flag need player-level CFBD ingestion that does not exist).

---

## 9. Recommended next steps, in priority order

1. **Fix the snapshot ingestion.** Re-pull `ncaaf_team_stats` from CFBD with
   correctly timed week boundaries and verify with the audit in
   `scripts/ncaaf_search/` (`games_played` must never exceed the strictly-prior
   game count). This is worth doing regardless of whether any model ships,
   because production trains and scores on these features today.
2. **Re-evaluate the production NCAAF models afterwards.** `ncaaf_spread` is
   LIVE in config on a margin-regression rule whose walk-forward is 52.1%
   pooled (−0.5% ROI, below the 52.38% breakeven), and its registry row
   currently points at an AUC-0.49 classifier with no committed artifact.
3. **Do NOT spend the 200-trial Optuna budget.** Hyperparameter search
   optimises within a family; it cannot manufacture signal that no family, no
   feature group, no era arm and no calibration method shows a trace of. It
   would find a peak and the walk-forward would reject it.
4. If NCAAF is worth more effort, the honest next hypotheses are the two
   untested ones above -- QB continuity (needs ingestion) and market structure
   (needs only a run of the existing script) -- not more team-strength
   features.

The pre-committed kill line from PR #229 — "no cell clearing +3% flat ROI over
≥150 bets on either spread or totals" — has **not** been honestly cleared by
anything in this run.

---

## 11. THE CROSS-BOOK OPENER SIGNAL (2026-08-25) — the one positive result

Every experiment above bets at the CLOSE. This one bets at the OPEN, which is
the section-28 NFL pattern applied to NCAAF.

**Rule.** Where DraftKings' and Bovada's OPENING spreads disagree, bet the side
Bovada favours, at DraftKings' number.

| min \|dev\| | bets | win% | flat ROI | 95% CI |
|---|---|---|---|---|
| 1.0 | 1,050 | 58.1% | +10.9% | [55.1%, 61.0%] |
| 2.0 | 483 | 59.6% | +13.8% | [55.2%, 63.9%] |
| 2.5 | 344 | 60.5% | +15.4% | [55.2%, 65.5%] |

Five cells clear breakeven at 95% with >= 100 bets. The REVERSED assignment
(sharp=DraftKings, soft=Bovada) is null — 0 cells clear. That one-directional
behaviour was pre-committed as the test distinguishing edge from artifact.

### It survived every falsification test

| check | result | reading |
|---|---|---|
| per-season | 2023 +7.7%, 2024 +14.8%, 2025 +9.2% | positive in all three |
| CLV | **0.694**, avg **+2.05 pts** | first CLV > 0.5 in the whole study |
| home/favourite artifact | pick_home 53.6%, pick_fav 49.6% | neither |
| placebo: bet Bovada's open | **-0.8%** | edge vanishes |
| placebo: bet DK's close | **-0.4%** | edge vanishes |
| convergence | opens differ 1.37 pts, closes 0.62 | books agree by close |

The two placebos are what make this credible: the edge exists ONLY at
DraftKings' opening number. That is what "DK's opener is stale" predicts and
what a data artifact would not produce.

### The unresolved question — EXECUTABILITY

Are both openers observable at the SAME MOMENT? If Bovada's "open" is simply
captured later, its number embeds information DK's opener lacks, and by the
time you can see it DK has already moved. The strategy would be untradeable.

CFBD ships no timestamps, so this CANNOT be settled from history. The evidence
is genuinely ambiguous:

* Bovada's opener is closer to the consensus close (1.374 vs 1.877)
* but its RMSE advantage vs actual margin is only 0.11 pts (15.255 vs 15.369),
  against a total open->close information gain of 0.26

So Bovada's opener sits ~40% of the way from DK's opener to the close. That is
consistent with EITHER a sharper simultaneous number (tradeable) OR a later
capture (not tradeable).

### How it gets resolved

Forward, with timestamped capture. Both books are available on The Odds API —
and so is **pinnacle**, the canonical sharp reference section 28 actually uses.
`bovada` and `pinnacle` were added to `LINE_SHOP_BOOKMAKERS` on 2026-08-25
(zero extra credits: the `bookmakers` param counts as one region).

`data/prune_odds.py` was fixed in the same change so this data survives:
previously tier 1 deleted every non-protected row for settled games and tier 2
kept only the NEWEST snapshot, so openers lived at most 2 days. The pruner now
keeps the earliest snapshot per (proposition, book) forever — verified on live
data as exactly 1,650 openers across 1,650 propositions, while still discarding
~99.5% of redundant snapshots.

**Status: CANDIDATE, not a model.** Do not stake money on the backtest. The
2026 season opens 2026-08-29; after a few weeks of timestamped capture, check
whether DK's opener is still gettable when Bovada's/Pinnacle's number is known.
If yes, this is deployable and should then be paper-traded to the standard
go-live gate. If no, it is an artifact of capture timing and dies.

Section 28's own opener rule shipped PAPER-FIRST on weaker evidence than this
(ROI CI grazing zero). The same standard applies here.
