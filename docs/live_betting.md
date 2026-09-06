# Live (in-play) betting — pipeline operations

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 21. Live (In-Play) Betting — Pipeline Operations
### Architecture (Phases 1–5, code complete as of session 53)

```
live_game_state_poller (15s, free MLB API)
   → live_game_state snapshots + live_trigger_events
      → live_trigger_orchestrator (debounce + credit cap)
         → live_odds_ingestor (bulk DK fetch, snapshot_type='in_play', ~3 credits)
            → live_scorer (LIVE_MODELS) → picks with is_live=true
               → mobile Picks tab, Live segment (fetchLivePicks polls every 30s)
```

One process runs the whole loop: `python -m data.ingestors.live_trigger_orchestrator --loop`.
**GitHub Actions cannot host this** (long-lived 15s loop). **As of 2026-07-21 it runs on the
Railway worker**: `scheduler.py` has a `live_loop` supervisor job (`*/10`, 11am–midnight ET)
that relaunches the loop whenever it isn't running — the loop itself exits after ~1 min with
no active games, so idle ticks are cheap no-ops and during a slate one invocation runs for
hours (skipped-tick `max_instances` warnings in the worker log are the heartbeat). Kill
switch: `RUN_LIVE_LOOP=0` in Railway Variables. Manual runs on Matt's machine still work
(same command) — all writes are idempotent per pass.

### Models (config.LIVE_MODELS — separate registry from MODELS)

| Model ID | Type | Target | Scored vs |
|---|---|---|---|
| `mlb_live_total_runs` | Poisson | runs in the REMAINDER of the game | in-play DK total: P(over L) = P(rest > L − current) via Poisson CDF |
| ~~`mlb_live_win_prob`~~ | binary + Platt | home wins | **RETIRED 2026-08-30** — 15 bets 6-9 / −34.1% |
| ~~`mlb_live_runline`~~ | binary + Platt | home wins by 2+ | **RETIRED 2026-08-30** — 14 bets 5-9 / −39.9% |

**MLB live is ONE model now (2026-08-30).** Both binary models were paused on 2026-08-29 and
retired the next day: they were negative at every cut AND got worse as the probability floor rose
(win_prob 0.65/0.15 = −78.9% on 8 bets), with average model probability 0.73–0.76 against a 36–40%
realised win rate. That is overconfidence — a calibration failure a threshold cannot fix, so a
pause had nothing to learn and there was no cut left to find. Their 5.3% / 5.9% holdout CalErr,
both above the 5% go-live gate, said it before either took a bet. `mlb_live_total_runs` is the one
live model that is actually profitable (41 bets +8.2% at 0.65/0.10; re-cut to **0.68 / 0.14** =
17 bets 12-5 **+27.9%**, all eight neighbouring cells positive — thin and in-sample, re-sweep at
~50 settled picks).

**Retirement means removed from the registry, not hidden.** `LIVE_MODELS` drives the live scorer,
the trainer (`--all-live`) and `LIVE_FEATURE_MAP`, so a retired model cannot score, be retrained,
or write a row of any kind; its artifacts are deleted and its `model_registry` rows deactivated.
Two things deliberately survive, because its picks are still in the DB and a pick that existed is
the bet of record (§1c): `paper_tracker._RETIRED_MODEL_MARKETS` keeps mapping them to h2h /
spreads so those rows settle on the right math (without it the runline picks fall to the `h2h`
default and a failed −1.5 cover grades as a win), and the mobile `MODEL_META` labels + market
mapping keep history rendering. `thresholds.RETIRED_MODELS` makes them non-actionable in the app
ahead of the server threshold row being pruned — that row outlives the model and reports
`paused=false` while it does.

Feature row = 9 state features (inning, top/bottom, outs, 3 base flags, score_diff, total_runs,
half_innings_left) + a pre-game context subset (team ERA/bullpen/rolling runs/weather for totals;
the H2H diff list is retained in `live_game_features.py` but no longer wired into any model). One
shared encoder (`state_features`) serves both training (from `plays`) and serving (from
`live_game_state`) — zero train/serve drift. The live line never enters the totals feature vector
(no line leakage).

### Conventions (load-bearing — don't break)

- **Three staleness guards, and they measure different things** (`data/live_quote_guard.py`).
  A live book price is refused if any one fires:

  | Guard | Catches | Where |
  |---|---|---|
  | quote AGE (`LIVE_QUOTE_MAX_AGE_SEC` / `MAX_QUOTE_AGE_SEC`, 90s) | a market the book has FROZEN | NCAAF `serve.py`, NFL `executor.py` |
  | quote vs SCORE (`quote_predates_score`) | a number the book stamped BEFORE the last score | all three |
  | edge CAP (`MAX_EDGE_CAP` 0.18 / `LIVE_MAX_EDGE_CAP` 0.2) | republished, but not yet moved | NCAAF, MLB |

  The middle one was added 2026-09-03 after an NCAAF total was bet 0.6s after a
  touchdown against a quote 62.2s old — inside the 90s cap, with an edge of
  0.1577 inside the 0.18 cap. Both other guards are bounded on the quote's age
  or the edge's size, and **no such bound can see an event**. The score guard is
  self-clearing: it blocks only until the book republishes.
  **MLB reads the score change out of `live_game_state` instead of keeping a
  `ScoreClock`.** `run_live_scorer` is invoked fresh per trigger, so an
  in-memory clock would report first sight forever — a guard dead code can
  satisfy. `_score_changed_at` asks the state history, which already holds the
  answer and is an index lookup on `idx_live_state_game`.

  **Measured cost on MLB's own record**, across all 127 live MLB BETs: the
  guard declines 18 (14.2%), but 10 of those are already dropped by the 30s
  age bound. The MARGINAL effect — picks newly declined — is **8 of 127
  (6.3%), which went 4–4**. Note what this does NOT show: the 18 split 6 Over /
  5 Under on totals, and the Unders went 4–1, so these are not hindsight bets
  on a run that already landed, the way the NCAAF case was. The argument for
  the guard in MLB is fillability, not outcome: a price stamped before the run
  is one DraftKings has already moved off by the time anyone acts.

- **`snapshot_type='in_play'` isolation:** the pre-game `_get_dk_odds`, the training bulk odds
  lookup (`_build_bulk_mlb_lookups`), and CLV close capture (`_closing_dk_odds`) all EXCLUDE
  in-play rows. In-play prices must never leak into pre-game scoring, training features, or
  closing-line math.
- **Live picks are BET/AVOID only** (no NONE rows — a live game would write hundreds of dead rows
  per day). **First-signal lock (2026-08-29, `LOCK_LIVE_PICKS_AT_FIRST_SIGNAL`):** the first live
  BET per (game, model) lane is the bet of record — locked at its line and price, never deleted or
  re-priced, and it is what settles into the model record (`_locked_live_lanes` in scorer.py;
  `_write_live_picks` in live_scorer.py; `write_picks` in ncaaf_live/gameday.py). UNLOCKED lanes
  keep the delete-and-replace churn each pass — the board posts freely, only signals lock. The
  complementary AVOID row written in the locking pass freezes with its BET (same proposition,
  other side). Before this, a live BET was re-priced every pass and the NCAAF totals lane's Q4
  close ERASED any standing pick before it could settle.
- **Settlement:** flows through the standard game-level path; `_market_for_pick` resolves live
  model_ids via LIVE_MODELS (h2h/totals/spreads). Totals/spread picks settle against
  `scored_line` (the in-play line at pick time). **CLV capture skips `mlb_live_%`** — an in-play
  price has no meaningful closing-line comparison.
- **Credit safety:** every in-play fetch logs to `live_credit_telemetry` (`market='fg_bulk:...'`).
  The orchestrator debounces FG fetches to one per `LIVE_FG_DEBOUNCE_SEC` (60s, telemetry-based so
  it survives restarts) and stops dispatching when `LIVE_DAILY_CREDIT_CAP` would be exceeded
  (**default 1000** as of 2026-06-28 — safe for the first live runs; set `=0` in .env to run
  uncapped once you trust the burn). Worst case burn ≈ 3 credits/min while games are live;
  realistic evenings ≈ 300–600 credits.
- **Staleness guards:** scoring skips games whose newest state snapshot is older than
  `LIVE_STATE_MAX_AGE_SEC` (300s — poller died) or whose in-play odds are older than
  `LIVE_ODDS_MAX_AGE_SEC` (300s — line has moved since).
- **Pitching_change / due_up_change triggers are consumed with no action** — live F5 and live
  player-prop fetching/scoring are deferred (they're the per-event credit cost drivers and have
  no live models yet).
- **No ROI backtest for live models** — no historical in-play odds exist (Path A decision,
  session 31). The go/no-go proxy is holdout AUC/CalError (reported overall + by inning bucket)
  plus live paper trading. Treat the first 50 live picks as the calibration set.

### First-time setup (Matt's machine)

```bash
# 1. PBP backfill (~41K games / ~2.4M plays, ~2.5 hrs — overnight job)
python -m data.ingestors.mlb_pbp_ingestor --backfill 2019 2025

# 2. Train the live models (play-level matrices ~1M rows; Optuna runs on a
#    200K-row subsample at 25 trials — ~30-60 min/model). Since 2026-08-30 this
#    is mlb_live_total_runs only — the two binary models are retired.
python -m models.trainer --all-live

# 3. On a game day, start the live loop (poll + fetch + score until slate ends)
python -m data.ingestors.live_trigger_orchestrator --loop

# Useful: observe without writing odds/picks
python -m data.ingestors.live_trigger_orchestrator --once --dry-run
python -m models.live_scorer --dry-run
```

Model .pkl artifacts only need committing (`git add -f models/saved/mlb_live_*.pkl`) if the live
loop ever runs off Matt's machine — unlike pre-game scoring, the loop runs where the models were
trained, so this is optional for now.

### Mobile

The Live board polls `fetchLivePicks`
(is_live=true, **signal_type='BET' only** as of session 105 — AVOID/fade live picks are still
written + settled for model tracking but not surfaced on the actionable Live board) while
focused. Live picks are EXCLUDED from the pre-game Picks query
(`.not('is_live','is',true)`) so the churning in-play board never mixes with the locked pre-game
board. `modelMeta.ts` renders LIVE ML / LIVE O/U / LIVE RL chips; `thresholds.ts` carries the
65%/10% placeholders.

**It stopped being its own bottom tab on 2026-09-06 (matt)** and became a third segment on the
Picks screen — `Today | Signals | Live` — rendered ONLY when the selected sport has an in-play
pick standing. It was the same PickCard over the same sport filter (both screens already called
`useSportFilter`) in a lossy copy of the Picks header, and it was empty most of the time:
measured over the 30 days to 2026-09-06, 175 live BETs on 25 of 31 days, ~5.3h of board
occupancy per active day — empty ~81% of the clock, and empty 100% of it for NBA, NHL, NFL, UFC
and GOLF (the only sports firing were MLB 123, NCAAF 51, WNBA 1). Which sport is live is carried
by a red dot on the sport chips (`SportToggle` `liveSports`), which the tab never said. The poll
is 30s while the segment is open and 120s elsewhere, since the Picks screen is open for most of
a session. `tests/test_mobile_live_segment.py` pins the properties with silent failure modes.

**Live picks are addable to the betslip as of 2026-09-06 (matt).** `useResolvedSlip` therefore
resolves against pre-game **and** live picks: `fetchPicksForDate` excludes `is_live` rows by
construction, and that hook prunes any key its board cannot resolve, so a live add on the
pre-game board alone would have landed, ticked the badge and then silently deleted itself.

**Bet on DraftKings** already works on live BET picks — the live scorer captures the DK betslip
deep link (`dk_bet_link`) from the in-play odds feed (`includeLinks`), so the same PickCard
"Bet on DraftKings" button that pre-game picks use fires on live BET picks (session 105).

**Track on live picks (session 105):** live picks ARE trackable, but keyed on a stable
proposition key `game_id|model_id|pick_side` (NOT pick_id — live pick_ids churn every rescore
pass). `useTrackedBets` keeps a second on-device store (`trackedBets.live.v1`, a light snapshot
per key); `isTracked(pick)`/`toggle(pick)` branch on `pick.is_live`. NO `tracked_bets` DB row is
written for live picks (nothing is locked in the DB — the line-change notifier is pre-game only),
so live picks are NOT server-locked. On the Performance tab, `useTrackedBetResults` +
`lib/liveTracked.computeLiveTrackedResults` grade a tracked live bet from the **model's settled
live pick for that side** at game end (closing price): settled → WIN/LOSS/PUSH; in-progress →
open; game final but the model flipped off that side (no settled pick for it) → `no_action`
("model moved off this side"), rendered from the snapshot. Verified by
`scripts/verify_live_tracked.ts` (17 cases).

---


---

## Cutoffs, and why they are re-derived every pass (2026-08-30)

**A live cutoff decays in a way a pre-game one does not.** A pre-game model is
scored once a day against a line that barely moves. A live model prices a market
that moves every few seconds, locks at the first crossing and never re-prices —
so the cutoff is a claim about a distribution that shifts under it.

It shifted on 2026-08-29 and nobody touched a threshold:

| date | live MLB games | bets | conversion |
|---|---|---|---|
| 8/22–8/28 | 2–7/day | 0–3/day | ~35% of games |
| **8/29** | 9 | **9** | **100%** |
| **8/30** | 8 | **8** | **100%** |

The first-signal lock plus 5s polling turned every live game into exactly one
bet: before, delete-and-replace meant only a lane's FINAL state survived, so a
total that crossed and fell back left nothing behind. Average model probability
also rose 0.68 → 0.72, because the lock catches the most extreme moment rather
than a surviving one. **~63 bets/week at an unchanged cut.**

### The cuts mike set

| model | prob | edge | EV | ceiling |
|---|---|---|---|---|
| `mlb_live_total_runs` | 0.70 | 0.14 | 0.28 | 30/wk |
| `ncaaf_live_total` | 0.66 | 0.12 | 0.22 | 20/wk |
| `ncaaf_live_win_prob` | 0.66 | 0.10 | 0.22 | 10/wk |

`LIVE_MAX_BETS_PER_WEEK` is **not** a runtime cap — nothing enforces it at score
time. It is the constraint the recommender optimises UNDER, because a cut that
earns more ROI by making more bets is not an answer to "too many bets". Left
unconstrained the sweep's first run proposed a LOOSER cut than the one it was
checking.

The NCAAF numbers are **least-bad and explicitly unvalidated** — 10 settled bets
from one Saturday. Every EV cut on that sample is still negative overall.

### Two things measured on the way in, both worth keeping

- **The EV floor was already 0.32.** The sweep table that produced "EV 0.28"
  averaged 08-29 (pre-floor, EVs down to 0.178) with 08-30 (post-floor, every EV
  ≥ 0.320), which understated where the floor already sat. 0.28 is therefore a
  slight LOOSENING; it binds on nothing once prob ≥ 0.70 is applied.
- **EV does not predict.** `mlb_live_total_runs` runs a mean predicted EV of
  +28.5% into a realised +3.1%, and claims 70.0% while winning 56.0%. That is
  overconfidence, i.e. a calibration error, and no threshold repairs it. Treat
  EV as a ranking device; the dashboard prints the gap rather than the EV alone.

### The loop: `tracking/live_calibration.py`

Runs as pipeline step `live-calibration` on the daily run **and every refresh
pass** (after settle, so the pass's own finals are in the sample), writes one row
per model to `live_calibration`, and surfaces in the monitor dashboard under
**Models → Live tuning**. Per model it reports:

1. **calibration** — mean predicted probability vs realised win rate;
2. **EV honesty** — mean predicted EV vs realised ROI;
3. **the sweep** — prob × EV over the settled record, with a plateau score,
   because a cell whose neighbours flip negative is noise;
4. **the cost** — bets and units per week, projected from the RECENT regime
   rather than the lifetime average (the lifetime average said 10/week while the
   live rate was ~60).

**The verdict is allowed to be "no".** It refuses when no cell has 15+ settled
bets, when nothing on the grid is profitable ("retrain or pause — shipping the
least-bad cell would be fitting noise"), and when nothing fits the ceiling. A
recommender that always recommends something is one you cannot act on.

Run it by hand: `python -m tracking.live_calibration --dry-run`.

### Stake

Already flat: `conviction_for()` returns 1u for every pick (2026-08-29), so the
published stake is 1u to win, grossed up by price into units laid (1.2u risk at
−120) and capped at 3u. `kelly_fraction` is still stored and still carries the
model's own conviction, but nothing sizes off it.
