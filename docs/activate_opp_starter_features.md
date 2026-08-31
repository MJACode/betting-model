# Activating the opposing-starter features (MLB batter props)

The features are **built and tested but not live**. This file is the whole
activation: one patch, five retrains, four checks. It has to be done on a
machine with `DATABASE_URL` — training reads six seasons of game logs, which
the dev sandbox cannot reach.

## Why it is two steps and not one

Adding a column to a `PROP_*_FEATURES` list does **not** change what gets bet.
The prop scorer predicts off `artifact["feature_cols"]` (models/scorer.py
:2917, :3149, :3316) and NaN-fills anything the frame is missing, so a list
naming features the `.pkl` never learned scores exactly as it did yesterday —
silently, no error, no log line.

What the list *does* control is **training** (features/prop_feature_engine.py
:895, :1677). So the half-done version of this change is worse than not doing
it: nothing improves now, and the next retrain of those models — for any
reason, by anyone — silently picks the features up, which is a model change
with no decision behind it and no `Updated-By:` trailer.

`tests/test_feature_artifact_agreement.py` exists to make that state loud. It
goes **red** the moment the patch below is applied and stays red until the
retrained artifacts are committed. That is the intended behaviour, not a
problem to work around.

## What the features are

Per-market, from Baseball Savant, prior season (no leakage), NaN when the
opposing starter is not yet confirmed:

| Model | Added |
|---|---|
| `mlb_prop_batter_hits` | `opp_starter_k_pct`, `opp_starter_whiff_pct`, `opp_starter_xera` |
| `mlb_prop_batter_tb` | `opp_starter_k_pct`, `opp_starter_whiff_pct`, `opp_starter_xera` |
| `mlb_prop_batter_rbi` | `opp_starter_k_pct`, `opp_starter_xera` |
| `mlb_prop_batter_runs` | `opp_starter_k_pct`, `opp_starter_xera` |
| `mlb_prop_batter_walks` | `opp_starter_bb_pct`, `opp_starter_whiff_pct` |

Chosen per market rather than applied uniformly: walks care about the
starter's control, hits and total bases about contact suppression, RBI and
runs about both on top of the lineup context already there. The builder is
`_opp_starter_savant()` in features/prop_feature_engine.py, covered by
tests/test_opp_starter_features.py.

The gap they close: every one of these models already carries `opp_team_era`
— a season-long *team* average — as its only opposing-pitching signal. The
batter does not face the team. `mlb_prop_batter_hr` has had real starter
features (`opp_starter_hr9`, `opp_starter_gb_pct`) since v2; the other five
never got them.

## Step 1 — apply the patch

```bash
git apply docs/patches/activate_opp_starter_features.patch
python -m pytest -q tests/test_feature_artifact_agreement.py   # EXPECT: red
```

Red here is the guard doing its job — five models now advertise features no
committed artifact has learned. Do not proceed to a commit from this state.

## Step 2 — coverage is MEASURED, and it changes the training seasons

`build_prop_training_dataset` calls `df.dropna(subset=all feature columns)`
(features/prop_feature_engine.py:955). Any row missing one new feature is
deleted from the matrix — CLAUDE.md §7's "a stat that is always NULL deletes
the training matrix". So coverage was measured before writing this, against
production on 2026-08-31:

| Season | Batter rows | Opposing starter known | …with prior-season Savant | Coverage |
|---|---|---|---|---|
| 2019 | 52,754 | 52,719 | **0** | **0.0%** |
| 2020 | 21,722 | 21,693 | 18,716 | 86.2% |
| 2021 | 43,641 | 43,620 | 36,853 | 84.4% |
| 2022 | 41,245 | 41,176 | 36,681 | 88.9% |
| 2023 | 42,357 | 42,320 | 35,685 | 84.2% |
| 2024 | 39,579 | 39,549 | 33,320 | 84.2% |
| 2025 | 36,352 | 36,323 | 31,194 | 85.8% |
| 2026 | 36,638 | 36,629 | 32,115 | 87.7% |

Two things fall straight out of that table.

**2019 is unusable and cannot be fixed.** Training takes the PRIOR season to
avoid leakage, and `player_savant_stats` starts at 2019 — there is no 2018 to
look up, and Statcast's public leaderboards do not go back far enough to
backfill one for these metrics. Four of the five models currently train on
2019-2024, so activating the features without changing the seasons silently
deletes 52,754 rows — about a fifth of the matrix — and the retrain would look
like a feature result when it is really a sample result.

**So pin the seasons and re-baseline.** Train on 2020 onward, and produce the
comparison baseline by re-running the OLD feature set on the SAME seasons.
Comparing a 2020-2024 model against the 2019-2024 artifact in the repo
measures two changes at once and attributes both to the features.

The remaining ~15% per season is starters with no prior-season Savant row —
rookies and call-ups, i.e. genuinely-unknown pitchers, not a data gap. Those
rows are dropped from training. That is a real cost of the feature and it is
the thing the holdout comparison in Step 4 has to justify.

Re-run the measurement before retraining rather than trusting this table:

```sql
-- what fraction of batter training rows can see the opposing starter's Savant?
WITH starters AS (
  SELECT DISTINCT ON (game_id, team) game_id, team, player_id
  FROM   player_game_log
  WHERE  player_type = 'pitcher' AND is_starter = TRUE
         AND p_home_runs IS NOT NULL          -- same filter the loader applies
)
SELECT b.season,
       COUNT(*)                                          AS batter_rows,
       COUNT(s.player_id)                                AS starter_known,
       COUNT(sv.k_pct)                                   AS starter_savant_known,
       ROUND(100.0 * COUNT(sv.k_pct) / COUNT(*), 1)      AS pct
FROM   player_game_log b
LEFT   JOIN starters s
       ON s.game_id = b.game_id AND s.team <> b.team     -- the OPPOSING starter
LEFT   JOIN player_savant_stats sv
       ON sv.player_id = s.player_id
      AND sv.player_type = 'pitcher'
      AND sv.season = b.season - 1                       -- training takes prior season
WHERE  b.player_type = 'batter' AND b.at_bats >= 1 AND b.hits IS NOT NULL
GROUP  BY b.season ORDER BY b.season;
```

## Step 3 — retrain all five, plus a matched baseline, and commit

Seasons pinned per Step 2. Run the baseline FIRST, on master, before applying
the patch — same seasons, old feature set — so Step 4 compares one change:

```bash
# 1. baseline, on master (patch NOT applied). Note the holdout numbers; these
#    artifacts are throwaway, do not commit them.
for m in hits tb rbi runs walks; do
  python -m models.trainer --model mlb_prop_batter_$m \
    --seasons 2020 2021 2022 2023 2024 --holdout 2025
done

# 2. apply the patch, then the real run
git apply docs/patches/activate_opp_starter_features.patch
for m in hits tb rbi runs walks; do
  python -m models.trainer --model mlb_prop_batter_$m \
    --seasons 2020 2021 2022 2023 2024 --holdout 2025
done

git add models/saved/mlb_prop_batter_{hits,tb,rbi,runs,walks}_*.pkl
```

Watch the `Dropped N/M rows with null features/target` line on each run — it
is the coverage table above showing up in the matrix. A drop materially worse
than ~15% means something other than the starter is null; stop and find it.

**An uncommitted `.pkl` is a silent outage** — the registry row points at a
path the worker cannot load, and the model stops scoring with no error. This
has already cost a month of UFC picks and a four-week outage across three MLB
prop models.

## Step 4 — accept or reject, on the numbers

The artifacts in the repo today, for reference only — they are trained on
different seasons, so they are NOT the comparison. The comparison is the
matched baseline from Step 3.1. `holdout_ou_acc` is the number that matters:
it is over/under accuracy, which is what actually gets bet.

| Model | Holdout | MAE | O/U acc | cal_error |
|---|---|---|---|---|
| `mlb_prop_batter_hits` | 2025 | 0.6858 | 0.6043 | 0.0118 |
| `mlb_prop_batter_tb` | 2025 | 1.3268 | 0.5963 | 0.0274 |
| `mlb_prop_batter_rbi` | 2024 | 0.6199 | 0.7121 | 0.0107 |
| `mlb_prop_batter_runs` | 2025 | 0.5662 | 0.6370 | 0.0094 |
| `mlb_prop_batter_walks` | 2024 | 0.4496 | 0.7281 | 0.0068 |

Compare against the Step 3.1 baseline, not against that table: `rbi` and
`walks` were last trained before 2024 existed, and all five include 2019,
which Step 2 removes.

Accept a model only if holdout O/U accuracy is **not worse** and MAE is not
worse. A feature set that helps three models and hurts two is a per-model
decision — keep the winners, revert the losers by dropping their lines from
the patch and retraining those two only. Nothing here entitles the whole batch
to ship together.

## Step 5 — clear the guard and commit

Once all five artifacts are committed:

```bash
python -m pytest -q tests/test_feature_artifact_agreement.py   # EXPECT: green
python -m pytest -q tests/
```

The patch already empties `PENDING_RETRAIN_FEATURES`, so the
`test_pending_features_are_not_live_without_a_retrain` assertion passes
trivially once there is nothing pending.

This is a model update under CLAUDE.md §1b — a feature-list change plus a
retrain. The commit needs the trailer:

```
Updated-By: mike
```

(or `matt`, whoever's call it actually was — guessing an attribution is worse
than none.)

## Rollback

The old `.pkl` files stay in `models/saved/`. Reverting is `git revert` of the
activation commit plus pointing `model_registry` back at the previous
`model_path` for each of the five — the scorer reads the artifact, so the
older file is a complete rollback on its own.

## Two pre-existing drifts this guard pins on the way past

Found while writing the guard, present before any of this work, **not fixed**
here because trimming a feature someone added on purpose is itself a model
decision:

- `mlb_prop_pitcher_hits` — list names `opp_team_whiff_pct`, `opp_team_k_pct`,
  `park_hr_factor`; the artifact was trained on 14 features without them.
- `mlb_prop_batter_sb` — list names `opp_team_sb_allowed`; the artifact was
  trained on 6 features without it.

Neither affects scoring today (the scorer uses the artifact). Both mean the
*next* retrain of those models silently changes them. They are recorded in
`_KNOWN_DRIFT` in the guard, so the decision is now visible instead of
waiting in a config file. Resolving them is either "retrain, the features were
wanted" or "trim the list, they were not" — someone has to say which.
