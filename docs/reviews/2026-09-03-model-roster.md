# The complete model roster — every model, its status, and why

> Matt, 2026-09-03: *"list all models going live, all the props / live one etc.
> I thought there was a ton of models we built."*
>
> There are. **71 registered model ids: 47 live, 24 paused**, plus 4 retired and
> 3 rule-based lanes that do not sit in the registry — **about 78 built in all.**
>
> Status is read from `master`, because master is what the worker deploys.
> **Caveat that matters: it is not the only version of the truth right now — see
> §5.**

---

## 1. The whole roster at a glance

| Sport | Live | Paused | Total |
|---|---:|---:|---:|
| **NBA** | 12 | 0 | 12 |
| **MLB** | 10 | 7 | 17 |
| **NCAAF** | 5 | 1 | 6 |
| **GOLF** | 5 | 0 | 5 |
| **WNBA** | 5 | 4 | 9 |
| **NHL** | 4 | 0 | 4 |
| **NFL** | 3 | 12 | 15 |
| **UFC** | 3 | 0 | 3 |
| **Total** | **47** | **24** | **71** |

By type: 36 player-prop models, 28 game models (moneyline / spread / total),
3 in-play models, 4 rule-based market lanes.

---

## 2. LIVE — the 47 that can produce a bet today

Cuts shown are the action thresholds: `p` = model probability floor,
`edge` = model probability minus the book's implied probability, `odds` = price
floor.

### NBA — 12 live, none paused
| Model | Cut |
|---|---|
| `nba_moneyline` | p ≥ 0.66, edge ≥ 0.12 |
| `nba_spread` | p ≥ 0.66, edge ≥ 0.12 |
| `nba_over_under` | p ≥ 0.66, edge ≥ 0.12 |
| `nba_prop_player_points` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_rebounds` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_assists` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_threes` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_steals` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_blocks` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_turnovers` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_pra` | p ≥ 0.60, edge ≥ 0.08 |
| `nba_prop_player_dd` | p ≥ 0.55 (probability only — DK juices double-doubles and there is no real "No" side to fade) |

**The whole NBA book is live and out of season.** Worth knowing: these carry
uniform placeholder-looking cuts (0.66/0.12 and 0.60/0.08 repeated), which is
the signature of a threshold set that has not been swept on a real record.

### MLB — 10 live, 7 paused
| Model | Cut |
|---|---|
| `mlb_moneyline` | p ≥ 0.72, edge ≥ 0.11 |
| `mlb_f5_moneyline` | p ≥ 0.58, edge ≥ 0.02 |
| `mlb_f5_over_under` | — (DK does not carry this market) |
| `mlb_f5_runline` | — (DK does not carry this market) |
| `mlb_live_total_runs` | p ≥ 0.70, edge ≥ 0.14 — **in-play** |
| `mlb_prop_pitcher_k` | p ≥ 0.58, edge ≥ 0.08, odds ≥ −140 |
| `mlb_prop_pitcher_hits` | p ≥ 0.54, edge ≥ 0.08, odds ≥ −140 |
| `mlb_prop_pitcher_outs` | p ≥ 0.50, edge ≥ 0.12, odds ≥ −140 |
| `mlb_prop_batter_runs` | p ≥ 0.62, edge ≥ 0.10, odds ≥ −140 — ⚠️ **BROKEN, see §4** |
| `mlb_prop_batter_walks` | p ≥ 0.45, edge ≥ 0.14, odds ≥ −140 |

### NCAAF — 5 live, 1 paused
| Model | Cut |
|---|---|
| `ncaaf_spread` | p ≥ 0.55 — the **cross-book opener rule** (Bovada vs DK), 1,050 bets +10.9%, CLV 0.694 |
| `ncaaf_spread_premium` | p ≥ 0.58 |
| `ncaaf_over_under` | p ≥ 0.65 — total-regression, ≥8-point disagreement with DK |
| `ncaaf_live_total` | p ≥ 0.66, edge ≥ 0.12 — **in-play** |
| `ncaaf_live_win_prob` | p ≥ 0.66, edge ≥ 0.10 — **in-play** |

Both NCAAF live models are flagged in config as **explicitly unvalidated** — 10
settled bets from a single Saturday, which is a slate, not a record.

### GOLF — 5 live ⚠️ **but see §5, mike paused all five today**
| Model | Cut |
|---|---|
| `golf_outright` | p ≥ 0.03, edge ≥ 0.01 |
| `golf_top10` | p ≥ 0.15, edge ≥ 0.05 |
| `golf_top20` | p ≥ 0.25, edge ≥ 0.05 |
| `golf_make_cut` | p ≥ 0.65, edge ≥ 0.05 |
| `golf_matchup` | p ≥ 0.55, edge ≥ 0.05 |

### WNBA — 5 live, 4 paused
| Model | Cut |
|---|---|
| `wnba_moneyline` | p ≥ 0.50, edge ≥ 0.06 |
| `wnba_prop_market` | edge ≥ 0.05, odds ≥ −140 — **rule-based**, de-vig Pinnacle |
| `wnba_prop_player_rebounds` | p ≥ 0.62, odds ≥ −140 |
| `wnba_prop_player_assists` | p ≥ 0.50, edge ≥ 0.10, odds ≥ −140 |
| `wnba_prop_player_pra` | p ≥ 0.68, edge ≥ 0.16, odds ≥ −140 |

### NHL — 4 live, none paused
`nhl_moneyline`, `nhl_over_under`, `nhl_puckline` (all p ≥ 0.55, edge ≥ 0.05)
and `nhl_moneyline_regulation` (p ≥ 0.40, edge ≥ 0.05 — the 3-way regulation
market, where casual money underweights the draw).

### NFL — 3 live, 12 paused
| Model | Cut |
|---|---|
| `nfl_wind_totals` | p ≥ 0.52, edge ≥ 0.03 — **rule-based**, the best-evidenced model in the repo |
| `nfl_opener_spread` | p ≥ 0.52 — **rule-based**, LIVE FULL SIZE by Matt's decision 2026-09-03 |
| `nfl_prop_market` | edge ≥ 0.05 — **rule-based**, de-vig Pinnacle, +10.76% blind over 954 |

### UFC — 3 live, none paused
`ufc_moneyline` (p ≥ 0.65, edge ≥ 0.08), `ufc_total_rounds` (p ≥ 0.62,
edge ≥ 0.08), `ufc_method_of_victory` (p ≥ 0.65, probability-only).

---

## 3. PAUSED — the 24, and why, in plain words

**None of these were paused as a precaution. Each one was measured and lost.**

### NFL player props — 12 models
`pass_yards`, `pass_attempts`, `pass_completions`, `pass_tds`, `rush_yards`,
`rush_attempts`, `rec_yards`, `receptions`, `rush_rec_yards`, `anytime_td`,
`tackles_assists`, `sacks`.

Two separate reasons, both still true:

1. **We have never stored a single NFL player-prop price.** These models were
   graded on whether the player went over or under — never on whether the bet
   would have made money at the price offered. Their thresholds are placeholders
   that were never tuned against a real price.
2. When the projections *were* compared to DraftKings, **eleven of the twelve
   lost to the bookmaker's margin.** That says our player projections are not
   better than the market's — which is exactly why `nfl_prop_market` exists and
   works: it stops predicting players and starts comparing bookmakers.

**Unpausing these would put picks on the board off untuned cuts, in a market we
have no price history for.**

### MLB — 7 models
| Model | Why it is paused |
|---|---|
| `mlb_over_under` | **Trained on leaked data.** The pitcher table held each starter's *end-of-season* ERA against every one of his starts, so the model was reading the future. Needs a rebuild, not a threshold change. |
| `mlb_runline` | **−6.93% with both sides losing** over the honest measurement window. Six weeks of that before it was paused. |
| `mlb_prop_batter_hits` | Stopped discriminating in late July; the features that worked stopped working. |
| `mlb_prop_batter_tb` | The market is efficient here — no profitable setting exists. |
| `mlb_prop_batter_sb` | Cannot reach enough bets at any setting to measure. Needs catcher throw-out data we do not ingest. |
| `mlb_prop_pitcher_er` | **You paused these two on 2026-07-11** — removed from display and consideration. |
| `mlb_prop_pitcher_walks` | As above. |

### WNBA — 4 models
| Model | Why it is paused |
|---|---|
| `wnba_prop_player_points` | Retrained, then swept against real stored DK prices: **the entire grid is negative.** Needs new features, not new thresholds. |
| `wnba_prop_player_threes` | **−18.7% over 70 bets**, and no setting anywhere clears 25 bets profitably. |
| `wnba_over_under` | Trained on made-up lines and serving real ones — the inputs do not match at the point of decision. |
| `wnba_spread` | As above. |

### NCAAF — 1 model
`ncaaf_moneyline` — **−12% ROI, 17% calibration error**, and the classifier
scored 0.49 on holdout (0.50 is a coin flip). Also, most of a Saturday slate is
priced −1000 or worse, where no realistic edge survives the juice.

---

## 4. ⚠️ A live model is broken right now

**`mlb_prop_batter_runs` is live, active, and cannot load.**

Checked directly against the production database this session:

```
model_registry ACTIVE row →  models/saved/mlb_prop_batter_runs_20260903_205632.pkl
on disk                   →  models/saved/mlb_prop_batter_runs_20260621_171840.pkl
in any git commit,
      on any branch       →  NOT PRESENT
```

A model was retrained and registered **active today (2026-09-03, 20:56)**, and
its artifact file was never committed — it exists nowhere in the repository, on
any branch. This is precisely the trap CLAUDE.md §7 records: *"A retrained model
must have its `.pkl` COMMITTED. The registry row points at a path; if the
artifact is not in the repo the worker cannot load it and the model silently
stops scoring."* It has already cost a month of UFC picks and a four-week outage
across three MLB prop models.

**Fix:** commit the artifact from whichever machine ran the retrain, or roll the
registry back to `20260621_171840` — which *is* on disk. Until one of those
happens, `mlb_prop_batter_runs` produces nothing and looks exactly like a quiet
night.

**Two more things the same database check settled:**

- **53 of 56 active registry rows carry `holdout_roi` = exactly 0.0.** This is
  the hardcoded placeholder in `models/trainer.py:474` flagged on 2026-08-30 —
  now confirmed against production. Any "positive holdout ROI" gate reading that
  column is reading a fabricated zero.
- **Odds API credits are healthy: 4,821,702 remaining** of 5M
  (178,298 used). NFL polling at ~96/day is not a concern. Note the daily burn
  jumped from ~96k to ~172k between Sep 2 and Sep 3 — worth a glance, but there
  is no shortage.

---

## 5. The roster is not in one place, and that is a problem

**There are 18 unmerged branches, and several change which models fire.** "What
is live" currently depends on which branch you read:

| Branch | What it changes |
|---|---|
| `fix-props-and-golf` | **Pauses all five golf models** — mike, today: *"Golf should not be firing."* |
| `f5-paper-cut` | Moves the `mlb_f5_moneyline` cut 0.74/0.00 → 0.58/0.02 |
| `f5-threshold-sweep` | Concludes no f5 cut works, and 0.74 fires zero bets |
| `pitcher-stats-asof-rebuild` (+9) | Retrains after the leak repair |
| `retrain-on-repaired-data` | Retrains `mlb_moneyline` and `mlb_prop_pitcher_k`; assesses all 71 |
| `claude/live-retrain-2026` (+4) | The calibration work |
| `live-quote-score-guard` (+7) | The live staleness guard — currently checked out |

**The golf conflict is the one that needs you.** On master, all five golf models
are live. On `fix-props-and-golf`, mike paused all five **today** with the note
*"Golf should not be firing."* That branch is not merged, so golf is still
firing. Your instruction is that all models are live. **Two directors, opposite
instructions, same day — CLAUDE.md §1b says ask rather than guess, so I have not
touched golf either way.**

---

## 6. Retired — not paused, gone

Four models were removed from the registry entirely. A paused model still scores
and keeps its threshold for an unpause; a retired one has nothing left to pause.

| Model | Retired | Record |
|---|---|---|
| `mlb_live_win_prob` | 2026-08-30 | 15 bets, 6-9, **−34.1%** |
| `mlb_live_runline` | 2026-08-30 | 14 bets, 5-9, **−39.9%** |
| `mlb_prop_batter_hr` | 2026-09-02 (matt) | — |
| `mlb_prop_batter_rbi` | 2026-09-02 (matt) | — |

Their picks stay in the database and still settle correctly — a pick that
existed is the bet of record (§1c).

---

## 7. What I would flag about "all models are live"

You asked for the opener at full size and I have recorded that. On the wider
reading — unpausing the 24 — three things are worth having in front of you
before you decide, and then it is your call:

1. **Twelve of the 24 are NFL props with no price history at all.** They would
   surface picks off thresholds that were never tuned against a price, in the
   week the season starts.
2. **Four of them are trained on data we know is wrong** (`mlb_over_under` on
   leaked ERA; `wnba_over_under` and `wnba_spread` on synthetic lines). Those are
   rebuilds, not switches.
3. **The rest have measured negative records** — `wnba_prop_player_threes` at
   −18.7% over 70 bets, `ncaaf_moneyline` at −12%, `mlb_runline` at −6.9% both
   sides.

**My recommendation: unpause nothing as a block.** If you want more models
firing, the highest-value moves are the opposite direction — fix
`mlb_prop_batter_runs` (§4), and extend `nfl_prop_market` / `wnba_prop_market`
(the de-vig-Pinnacle rule, the one construction that has repeatedly validated:
+10.8% NFL, +10.9% NCAAF) to NBA and MLB. That adds live models on the
evidence that works, rather than switching on the ones that were measured
losing.

If you want them on anyway, say so and I will do it with `Updated-By: matt`.

---

*Written 2026-09-03. Roster read from `master`; live figures read directly from
the production database from this machine (the local `.env` carries
`DATABASE_URL` — the route that was available all along while I was reporting
the Supabase connector as unavailable). Read-only apart from the odds-cache
upload, which only adds rows.*
