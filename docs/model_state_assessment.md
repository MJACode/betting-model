# Model state assessment — all 71 models

**Written 2026-09-03**, the day the two historical data leaks were repaired
(`docs/team_stats_leak.md`). mike asked for a standing assessment across every
model rather than a per-sport one, because the leak repair cut across sports and
the per-sport docs each tell only their own part of it.

> **This file is a SNAPSHOT with a date on it, not a live dashboard.** Every
> number below is a query anyone can re-run — the queries are named. When it
> disagrees with the database, the database is right and this file is stale.

---

## 1. The headline

**The data was repaired today. Three of ~20 affected models have been retrained
against it; the rest are still fitted to the leaked version.**

That is the single most important fact about the current state, and it is a
transitional problem rather than a permanent one:

* `mlb_team_stats`, `nba_team_stats`, `nhl_team_stats`, `wnba_team_stats`
  (Phase 1) and `mlb_pitcher_stats` (Phase 2) all carried each entity's
  SEASON-FINAL numbers on every historical row. They are now genuine
  as-of-date series.
* Every model whose artifact predates 2026-09-03 was FITTED on the leaked
  version of those tables and is now SERVED the repaired version.

That is a train/serve mismatch, and it is the repair's own side effect. It is
not an argument against the repair — the alternative is training on the future —
but it means **a rebuild is only finished for a model once that model has been
retrained.**

| model | artifact | status after the repair |
|---|---|---|
| `mlb_f5_moneyline` | **2026-09-03** | matched — retrained today |
| `mlb_moneyline` | **2026-09-03** | matched — retrained today |
| `mlb_prop_pitcher_k` | **2026-09-03** | matched — retrained today |
| `wnba_moneyline` | 2026-05-31 | **mismatched** |
| `wnba_over_under`, `wnba_spread` | 2026-07-19 | mismatched (both paused) |
| `nba_moneyline` | 2026-06-19 | **mismatched — season starts October** |
| `nhl_moneyline`, `nhl_moneyline_regulation` | 2026-06-21 | **mismatched — season starts October** |
| `mlb_f5_over_under`, `mlb_f5_runline` | 2026-05-08 | mismatched (produce no picks) |
| `mlb_prop_*` | various | partially — props read `mlb_team_stats` for opponent context |
| NCAAF, UFC, GOLF, NFL | various | **unaffected** — no leaked table in their feature path |

**NCAAF is unaffected because `ncaaf_team_stats` was always built correctly** —
14-16 weekly snapshots per season. It is the template the other four were
rebuilt to match.

### The deadline

NBA and NHL start in **October**. They have produced no picks all year, so
nothing is wrong today — but they will come out of the offseason running on
artifacts fitted to leaked data unless they are retrained first. That is the
only item here with a hard date on it.

---

## 2. Performance, and why the headline number misleads

Since 2026-07-01, splitting by whether a model is still switched on:

| bucket | lane | settled | win% | units | ROI |
|---|---|---|---|---|---|
| **Current lineup** | live | 235 | 60.9% | **+4.94** | **+2.10%** |
| **Current lineup** | pre-game | 343 | 53.4% | −18.11 | **−5.28%** |
| Now paused/retired | live | 265 | 49.8% | −52.79 | −19.92% |
| Now paused/retired | pre-game | 183 | 42.6% | −22.61 | −12.36% |

**The models that have since been switched off account for −75 of the −89 total
units.** The platform-wide figure is dominated by models that no longer fire, so
quoting it as "how we are doing" is wrong in both directions: it flatters
nothing and it hides that the live lane is currently positive.

Read this way the pruning is the story. `mlb_prop_batter_rbi` (−25% on 65),
`mlb_live_win_prob` (−32% on 17) and `mlb_live_runline` (−38% on 16) were
retired; `mlb_over_under` (−27% on 52) was paused today. Each was a real drain
and each is now off.

### The live thesis holds where it is supposed to

`mlb_live_total_runs` — **+14.66% ROI on 91 settled bets**, average price −111.
It is the best-performing model in the system and the only one clearly carrying
its own weight. CLAUDE.md's framing of live as the priority market is supported
by this model's own record.

### Pre-game is the weak lane

| model | settled (since 07-01) | ROI | note |
|---|---|---|---|
| `mlb_f5_moneyline` | 85 | −3.09% | retrained today; now paper-only |
| `mlb_prop_pitcher_k` | 90 | −11.77% | retrained today; now paper-only |
| `wnba_moneyline` | 28 | −16.11% | active, mismatched artifact |
| `mlb_over_under` | 52 | −26.73% | paused today |

---

## 3. Every model, by state

**71 registered: 43 active, 24 paused, 4 retired.** 38 have ever produced a
pick; **33 never have.**

### The 33 that have never fired

| sport | n | why |
|---|---|---|
| NBA | 12 | offseason — season starts October |
| NHL | 4 | offseason — season starts October |
| NFL | 12 | all 12 deliberately paused |
| GOLF | 5 | **no picks ever, and not paused — worth a question** |

GOLF is the odd one. Five models, none paused, none has ever produced a pick.
That is the `mlb_runline` shape — "publishes nothing" and "is switched off"
looking identical — and it should be resolved either way.

### Lifetime records worth knowing

Positive on a real sample:

| model | settled | lifetime ROI |
|---|---|---|
| `mlb_live_total_runs` | 91 | **+14.66%** |
| `mlb_prop_pitcher_outs` | 94 | +5.76% |

Negative on a real sample, still active:

| model | settled | lifetime ROI |
|---|---|---|
| `mlb_prop_pitcher_k` | 205 | −4.35% |
| `mlb_prop_batter_runs` | 395 | −3.26% |
| `mlb_f5_moneyline` | 198 | −0.87% |
| `mlb_moneyline` | 101 | −12.28% |

Thin samples that should not be read as records: `ufc_*` (3-13 bets each),
`mlb_f5_over_under` (9), `mlb_f5_runline` (7), `ncaaf_*` (0-8).

---

## 4. What the honest model quality actually is

Walk-forward on the rebuilt tables, train ≤ T and test T+1
(`scripts/walk_forward_eval.py`):

| model | mean AUC | 2026 (honest) | was, on leaked data |
|---|---|---|---|
| `mlb_moneyline` | 0.559 | 0.559 | 0.60-0.62 |
| `mlb_f5_moneyline` | 0.557 | 0.536 | 0.63-0.64 |
| `mlb_runline` | 0.555 (unstable) | 0.588 | 0.53-0.64 |
| `mlb_over_under` | **0.507** | **0.486** | 0.55-0.57 |

**The real MLB signal is worth about 0.55-0.56, not the 0.60-0.64 the leaked
seasons advertised.** `mlb_over_under` has none at all — below a coin flip in
the only honest season, which is why it was paused.

### The retrains corroborate it, which is the useful part

Both models retrained on repaired data hold out on 2026 at almost exactly the
walk-forward number, rather than above it:

| model | version | holdout 2026 AUC | walk-forward 2026 | CalError |
|---|---|---|---|---|
| `mlb_f5_moneyline` | 20260903_163809 | 0.5548 | 0.536 | 0.0240 |
| `mlb_moneyline` | 20260903_182812 | 0.5562 | 0.559 | 0.0242 |

An honest holdout agreeing with an independent walk-forward is what you want to
see; the old artifacts claimed 0.691 and 0.587 on holdouts that sat inside their
own training seasons.

**And both retrains went straight to the revived features.** Nothing exceeds 11%
importance in either, where `d_starter_era_last3` + `d_starter_era` used to be
40% of f5. Top features now:

* `mlb_f5_moneyline` — `d_run_differential` .109, `d_starter_k9` .081,
  `d_team_era` .065, `d_team_whip` .062, `away_win_pct` .061
* `mlb_moneyline` — `d_run_differential` .098, `d_team_whip` .073,
  `d_team_era` .071, `d_bullpen_era` .067, `away_win_pct` .051

`d_run_differential` is the top feature in BOTH, and `away_win_pct` is fifth in
both. Those are two of the eight features that were constant zero in every
training season before Phase 1 — XGBoost cannot split on a constant, so they
were inert. The rebuild revived them and both models immediately leant on them
harder than on anything else. That is the clearest evidence the repair did what
it was supposed to.

**All three retrained models are PAPER ONLY.** §2's go-live gate is per model
and a retrain RESETS it: ≥50 settled picks, positive flat ROI, calibration ≤5%.
Calibration already passes for the two game models (2.4%); both need live picks.

### `mlb_prop_pitcher_k` — retrained, and it did not rescue the model

Retrained because it reads `mlb_team_stats` for `opp_team_k_pct`, so it carried
the same train/serve mismatch. That feature is 5th by importance at 4.5%, so the
repair touched a real but modest part of it — its main features
(`k_last10_avg` .223, `season_k_avg` .137, `k_last5_avg` .081) come from
`player_game_log`, which was never leaked.

| version | holdout | O/U acc | cal error |
|---|---|---|---|
| **20260903_190319** | **2026 (honest)** | 0.6453 | **0.2305** |
| 20260607_091558 (previous active) | 2025 (leaked) | 0.6526 | 0.1120 |
| 20260514_090858 | 2024 (leaked) | 0.6406 | 0.1127 |

O/U accuracy is flat against its own history (0.641-0.653). **Calibration error
roughly doubled**, but the comparison is not clean: 0.2305 is measured on an
honest 2026 holdout while 0.1120 was measured on a leaked one, so some of that
gap is the leak leaving rather than the model worsening. Either way it is not
evidence the retrain fixed anything.

Note this is a POISSON/PIT calibration error, a different quantity from the
classifier `cal_error` the ≤5% gate refers to — do not compare 0.2305 against
0.05 and conclude anything.

Train MAE 1.750 against holdout MAE 1.760 means almost no overfit, so the model
is fitting what it can; there simply may not be much more there. Its live record
is **−4.35% over 205 settled bets**, which is a real sample. The retrain was a
CORRECTNESS fix, not a performance fix, and it should not be read as one.

NBA, NHL and WNBA have NOT been re-measured this way. Their tables were rebuilt
in Phase 1 but no walk-forward was run, so their honest quality is unknown.
Assume the MLB pattern until measured, not because it is proven but because the
same leak was in the same shape in all four tables.

---

## 5. How to gauge performance — fastest first

1. **CLV — available immediately, no waiting for settlement.** `picks.clv_pct`
   and `clv_beat_close`. Today it says **no model has a demonstrable edge**:
   every one clusters at 0.0-1.0% average CLV with 43-61% beating close.
   `mlb_f5_moneyline` is +0.20% and 48.9% over 94 picks — a coin flip, and
   consistent with its 0.536 AUC and −3.1% ROI. Three independent measures
   agreeing is worth more than any one of them.
   *Caveat: coverage is partial (53-100% by model), and the live lane has no
   close, so live models cannot be judged this way at all.*
2. **Walk-forward** (`scripts/walk_forward_eval.py`) — offline, honest for MLB
   now. Pass `--seasons` explicitly: the default stops at 2024 and never reaches
   the only honestly-featurised season.
3. **Out-of-sample threshold sweep** (`scripts/mlb_f5_sweep.py`,
   `scripts/mlb_runline_sweep.py`) — score a held-out season with the current
   artifact against real prices, with the price floor applied. Also answers
   whether a cut is REACHABLE, which is how 0.74 was caught firing zero bets.
4. **Settled ROI** — ground truth, but slow, and a BET-only sample is
   systematically optimistic because it contains only picks that already cleared
   the live bar. `mv_scored_pick_outcomes` grades the whole universe (CLAUDE.md
   §7's evaluation rule).
5. **Calibration** — claimed vs realised probability. Maps exist for 11 models;
   only 10 are promoted. `mlb_f5_moneyline`'s is NOT, which is why its old
   0.74 cut — swept on calibrated probabilities — was being applied to raw ones.

### The queries behind section 2

```sql
-- current lineup vs switched-off, since 2026-07-01
SELECT CASE WHEN model_id = ANY($paused_or_retired) THEN 'off' ELSE 'current' END,
       coalesce(is_live,false),
       count(*) FILTER (WHERE result IN ('WIN','LOSS')),
       sum(profit_flat) FILTER (WHERE result IN ('WIN','LOSS'))
         / count(*) FILTER (WHERE result IN ('WIN','LOSS')) AS roi_pct
FROM picks WHERE signal_type='BET' AND game_date >= '2026-07-01' GROUP BY 1,2;
```

`profit_flat` is **dollars on a $100 stake**, so ROI is
`sum(profit_flat) / count(*)`, not `100 * sum / count`. Getting that wrong
inflates every number by 100x.

---

## 6. Open items

**Retrains required by the repair** — NBA and NHL before October;
`wnba_moneyline`; the MLB prop models that read `mlb_team_stats`.

**Data gaps still open:**

* `player_game_log` holds no pre-2026 White Sox or Nationals games at all —
  not even the opponent's starter. Rebuilt pitcher coverage is 75-89% by season.
* `wrc_plus` and `woba` are not recoverable from data held; they need an
  external source, a computable proxy, or dropping.
* `nhl_skater_stats` has 0 rows, so NHL has no per-game player data to
  aggregate. Tier-1 counting stats are fine; rate stats are not.
* `injuries` starts 2026-04-05, so four injury features are dead in training.

**Never measured:** `mlb_f5_over_under`, `mlb_f5_runline` — both read the
rebuilt pitcher table, both produce no picks, both hold active registry rows.

**Questions for a person:** the five GOLF models that have never fired; whether
`mlb_prop_pitcher_k` should be paused on its record.
