# Shipping: every file, table, test and production step

Step 7 of `SKILL.md`. Traced from the commits that added the women's college
basketball sport and its first two models and the college football moneyline
model (2026-11-09 to 11-11): `c4ddc15b` (sport groundwork, nothing bets),
`08e4a7fa` (a pre-game card, 75 files), `1d62c0bd` (a pre-game card, 22
files), `c2b383a6` (an in-play loop, 42 files). `git show --stat` on them is
the fastest way to see the whole shape. **Re-check this list against the
newest such commit before relying on it** — the plumbing moves.

## Which kind of model it is

- **A rule card** (all three recent models): `SCORING_METHODS[id] = "rule"`,
  a JSON artifact committed under `models/saved/` and loaded by a fixed path,
  built by a script that replays the card's own decision code to the research
  numbers. No `model_registry` row, no `--store`. The card refuses an artifact
  for another season.
- **A trained model**: `python -m models.trainer --model <id>`, then
  `git add -f models/saved/<id>_<ts>.pkl`, a `!` keep line in `.gitignore`,
  `models/saved/MANIFEST.md` updated, the old file `git rm --cached`
  (`docs/local_ops.md`, "Model retrains"). Before registering, open the file in
  a throwaway environment with the worker's library versions (its Railway build
  log) and compare output hashes. **A `.pkl` that is not committed silently
  stops the model scoring** (a month of one sport's picks, four weeks of three
  others). Registered JSON models: `--store <ABSOLUTE path>` then `--register`,
  after the merge.
- **An in-play loop**: a module under `models/` run as a pollers job, with its
  own decision ledger table.

## The shared gates every writer goes through

A new writer that skips one of these bets something it should not:

- **`models/honest_ev.gate`** and `config.min_ev_for`: the EV floor on the
  calibrated probability at the deciding price. A writer that skips it bets
  the raw number.
- **`data/schedule_context`**: no pre-game decision while a team still has an
  earlier game to play or log; rest from the stored schedule.
- **`models.scorer.prop_feature_matrix`** for any prop scorer: a missing
  feature drops the row, never becomes 0.0.
- **`tracking/pick_integrity.pick_problems`**: the label and the fields agree.
- **The lock** (`scripts.nfl_wind_publisher._lock_model` for cards; the
  first-signal live lock for in-play): a game is decided once and the row is
  never overwritten. Write NONE rows for every scored game so the whole
  universe can be graded.
- **Side conflicts**: no two picks on one game that cannot both win; in college
  basketball, `models/cbb_pairs.hold_back`.
- **Starter gates** where the sport has one (`models/nhl_goalie_gate.py`).
- **Quote bounds**: every reader of a price goes through the sport's bounds
  guard (a stored total of 1465.0 exists).

## config.py, for a new model

| Entry | What | Pinned by |
|---|---|---|
| `ACTION_THRESHOLDS[id]` | `{"min_prob", "min_edge"}` with the evidence in a comment | `test_config::test_every_model_carries_its_own_thresholds` |
| `MODEL_EDGE_THRESHOLDS[id]`, `MODEL_PROB_THRESHOLDS[id]` | the same cut, with who asked | same |
| `MODEL_MIN_ODDS[id]` | the price floor, pinned per model (default -200) | `test_mobile_threshold_parity::test_the_price_floors_match_config` |
| `MODEL_OWN_EV_FLOOR[id]` | its own EV floor, swept on its own record | `test_config::test_every_own_floor_names_a_live_model`, `test_no_own_floor_tightens_a_model_past_the_global_floor` |
| `MODELS_ON_OWN_PROBABILITY` | if it decides on its own probability | hand-pinned sets in `test_config` and `test_global_ev_floor` |
| `SCORING_METHODS[id]` | `"rule"` for a card | `test_dashboard_rule_models.KNOWN_RULES` |
| `LIVE_MODELS[id]` | in-play only: `(sport, market, "engine", description)`; this is how the pick settles | `test_live_game_features` (prefix tuple) |
| `PAUSED_MODELS` | not touched: a new model ships live | `test_mobile_threshold_parity::test_the_paused_set_matches_config` |

**For a new sport:** `DISCORD_SPORTS`; `DISCORD_LIVE_CHANNEL_REQUIRED` and
`LIVE_ANNOUNCE_WHILE_IN_PROGRESS` if it has an in-play model;
`<SPORT>_ODDS_API_MAP` (feed name to our id); `<SPORT>_EXTRA_BOOKMAKERS`.
`SPORTS` and `MODELS` only for a trained sport. The commit carries
`Updated-By:`.

## Ingestion, for a new sport

- `data/ingestors/odds_ingestor.py`: `SPORT_KEYS`, the resolver and schedule
  lists, `SPORT_EXTRA_BOOKMAKERS`, name normalisation, the season label, the
  default sport lists. Pinned in the sport's odds-intake test.
- New ingestors: teams and schedule (the whole season, not a two-week window),
  paid history (`--spool DIR --fetch --store`, walking the feed's chain), free
  history imports, box scores, play-by-play, the live score feed, odds capture.
- `run_pipeline.py`: each new step needs three edits (the call inside
  `run_daily_pipeline`, the `--step` choices, the step map).
  `scripts/refresh_pass.sh` for intraday steps.
- `data/prune_odds.py`: `PROTECTED_SOURCES` for bought history,
  `PATH_KEPT_SPORTS` if the whole price path is kept.
  `monitoring/probe.py` `_SPORT_TOKENS`.
- **Tables**: every new table in `data/anon_readable.py`
  `WORKER_ONLY_TABLES`; write-time `ensure_tables` gated by
  `data/ddl_guard.schema_is_current`; a migration-created table is one
  idempotent block registered in `data/view_migrations.py`
  `ACTIVE_MIGRATIONS`, before the two posted-stake migrations that must stay
  last. REVOKE from `anon` and `authenticated` by name, then read
  `get_advisors(security)`.

## Scoring and publishing

- **Pre-game card** (`scripts/ncaabw_total_card.py` is the shape):
  `scheduler.py` `run_<card>()` with `--publish` then `_publish_new_signals`,
  a `sched.add_job`, the id in `_PIPELINE_JOBS`, a `RUN_<X>=0` kill switch;
  `tracking/job_heartbeat.MAX_SILENCE`; `tests/test_monitoring.py`
  `INSTRUMENTED_ENTRYPOINTS`; `tests/test_nhl_goalie_guards.py` `ALLOWED`;
  the scorer's sweep spares the card's NONE rows
  (`tests/test_scorer_spares_other_writers_no_bet_rows.py`);
  `models/scorer.check_line_movement` names the model.
- **In-play loop** (`models/ncaabw_live_loop.py` is the shape): a
  `scheduler.run_<x>_live` gated by `RUN_<X>_LIVE`, in `_POLLER_JOBS`;
  `tests/test_service_role_split._EXPECTED_POLLERS`; heartbeat with active
  hours; the ledger table; prices through
  `data/ingestors/live_price_log.record_live_prices`; posts through the live
  notifier.
- **Thresholds**: `data/threshold_sync.py` writes `model_action_thresholds`
  from config (every refresh pass, and before every Discord post).
- **Settlement**: pre-game cards in `tracking/paper_tracker._RULE_MODEL_MARKETS`;
  in-play through `config.LIVE_MODELS`. `picks.prop_market` decides which
  column settles a prop pick: take it from the model.
- **The app's name for the model**: `mobile/src/lib/modelMeta.ts` `MODEL_META`
  and the `open_picks` view's name `CASE`, kept equal by
  `test_open_picks_view::test_every_model_has_its_app_name`; re-hash the view
  marker after editing it.
- **CLV**: the `clv_game_market` `CASE` and its comment stamp
  (`tests/test_rule_model_markets_everywhere.py`), for a pre-game model only.
  The closing-line recompute skips in-play picks (`p.is_live IS NOT TRUE`), so
  an in-play model is not added (EuroLeague, 2026-11-13).
- **Mobile thresholds**: `python -m scripts.generate_mobile_thresholds`
  (`--check` fails on drift).
- **A new sport in the app**: the sport chip, the model catalog order, the
  market mapping, look-ahead and live lists, a verify script, and the UX review
  before the PR (`/ux-review`, `.claude/rules/frontend.md`). Prefix matches on
  sport codes are a known trap.
- **Discord**: the sport's channel and live channel variables
  (`docs/discord.md`, `docs/cloud_worker.md`). Creating a channel is a worker
  job that has been refused in auto mode; ask mike once for the channel and its
  variable together.

## Tests and docs

- New test files per model (the card, and a real-Postgres test of it), and per
  sport (teams, schedule, box, odds capture, odds history, imports). Every
  test must have been **watched failing** without the change.
- Hand-maintained pins that fail until the new id or sport is named: the ones
  in the tables above, plus the sport-list pins (odds intake, prune, the
  mobile sport filter). Four of these broke on master once because the full
  suite was not run before a merge: **run `python -m pytest -q tests/` and
  report it as a failing-set diff against `origin/master`**, from a worktree
  with no `.env` in it.
- Docs: the league doc ("What runs, and where it lands", a section per model,
  the grid); `docs/thresholds.md` (a table per model); `docs/cloud_worker.md`;
  `docs/discord.md` and `docs/live_betting.md` for in-play;
  `docs/followups.md`; the session log and its README row; CLAUDE.md §8's
  sport list and the model and pause counts (`len(ACTION_THRESHOLDS)`,
  `len(PAUSED_MODELS)`, not pinned by a test).
- The code graph rebuilt in its own commit, named last
  (`graphify update .`, then the community names checked).

## Before the reply that ships it

- **The price range**: median, shortest, the share shorter than -300 and
  -500, and what the stake becomes there.
- **The bar it cleared** (`references/kill-tests.md`), and plainly if it did
  not.
- **Expected volume** per night and per week, from the backtest at the
  live cadence.
- **Go-live gate standing** as a fact: ≥ 50 settled, positive flat-bet
  return, calibration error ≤ 5%. Reported, never a hold.

## After mike's "merge"

1. **Timing.** Not over the 6am ET pipeline (about 10:00 to 10:45 UTC), not
   over a live slate, not over a card's only deciding run. A merge redeploys
   both services. A docs-only merge usually skips the deploy, but not always:
   on 2026-11-12 a markdown-only merge redeployed the in-play service during
   live games, landing while another merge's deploy was still running. So
   first check that neither service has a deploy building or deploying.
2. **A table the app reads exists before the merge**, because app changes ship
   over the air on push.
3. **Both deploys show SUCCESS** on the merge commit.
4. **`python -m data.view_migrations`** (never `data.db_setup`), from a clean
   master worktree with the database URL passed to that one process. Read back
   "N/N applied", the new tables' security, and that `open_picks` and
   `clv_game_market` name the model.
5. **`python -m data.threshold_sync`**, then read the model's
   `model_action_thresholds` row: its cut, its floor, not paused.
6. **The first run**: the job registered, its heartbeat, its ledger rows, and
   the reasons on its first non-bet rows.
7. **The first bet reaches every surface**: the app, the Discord channel,
   push.
8. **Trained models**: `--store`/`--register` with an absolute path, then
   queue `health_check` and read `model_artifacts_load`.
9. **Volume after shipping** is set with `set_model_volume` (tighten-only,
   stamped with who asked), never by moving the model's cut.
