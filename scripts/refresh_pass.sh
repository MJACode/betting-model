#!/usr/bin/env bash
# One full odds-and-scoring refresh pass. This is the single source of truth for
# the refresh step chain — called once per run by refresh_picks.yml (hourly,
# 7am-5pm ET) and repeatedly by evening_lines.yml (every 10 minutes, 6pm-11pm ET).
# Edit the chain here, never inline in a workflow, so the two schedules can't drift.
#
# Requires: DATABASE_URL, ODDS_API_KEY, DATAGOLF_API_KEY, FETCH_F5_LIVE in the env.
#
# Usage: refresh_pass.sh [hourly|evening]   (default hourly)
#   The only difference is the WNBA results ingest, which costs ~40 ESPN calls
#   per game. ESPN IP-blocked this worker in August 2026 and WNBA settlement was
#   dead for two weeks; running that every 10 minutes is how it happens again.
#   Everything else runs on every pass.
# NOT `set -e`. Every step below is an independent producer, so one failure must
# never abort the rest of the pass. On 2026-08-27 a NameError in the WNBA prop
# scorer (step 9 of 24) aborted every hourly pass for three days: opening-signal
# capture, Discord + push notifications, the parlay record, all four results
# ingests and settle never ran. Ordering alone can't fix that — a failure can
# land anywhere — so steps now run to completion and failures are collected.
# The pass still exits non-zero, so a broken step stays visible in the worker log.
set -uo pipefail
MODE="${1:-hourly}"

# Record that this pass ran. Until 2026-08-27 nothing did, so a pass that died
# mid-chain left no trace except missing side-effects. `|| true` throughout:
# observability must never be able to break the pass it is observing.
RUN_ID="$(python -m tracking.run_ledger start --kind "$MODE" 2>/dev/null | tail -1 || true)"

FAILED_STEPS=()
STEPS_TOTAL=0

step() {
  STEPS_TOTAL=$((STEPS_TOTAL + 1))
  if ! python run_pipeline.py --step "$1"; then
    echo "WARN: step '$1' failed - continuing with the rest of the pass" >&2
    FAILED_STEPS+=("$1")
  fi
}

# ── Parallel groups ──────────────────────────────────────────────────────────
# The pass took ~12 minutes against a 10-minute evening tick, so 18 passes ran
# in a 5-hour window instead of 30 and the rest were silently skipped.
# mike, 2026-08-30: "we absolutely need to get the 12 minutes down."
#
# Nothing here is CPU-bound: the worker peaks at 1.1GB of 8GB and 1.4 of 8
# CPUs. Every slow step is waiting on a socket -- an odds endpoint, ESPN, the
# database. Running independent waits sequentially is the whole problem, and
# no amount of extra Railway workers fixes it because a second machine does not
# make a socket answer faster.
#
# So independent steps run CONCURRENTLY and the group waits for all of them.
# Only steps with no data dependency on each other may share a group; the
# ordering comments further down are load-bearing and unchanged.
#
# Failure bookkeeping cannot use FAILED_STEPS here: a background job runs in a
# subshell and cannot append to the parent's array. Each job instead drops a
# marker file, which the group collects after the wait. Getting this wrong
# would make a failed step invisible -- the exact blindness the run ledger was
# built to end.
PAR_DIR="$(mktemp -d)"
trap 'rm -rf "$PAR_DIR"' EXIT

par() {
  STEPS_TOTAL=$((STEPS_TOTAL + 1))
  (
    if ! python run_pipeline.py --step "$1"; then
      echo "WARN: step '$1' failed - continuing with the rest of the pass" >&2
      : > "$PAR_DIR/$1.failed"
    fi
  ) &
}

par_wait() {
  wait
  # Collect what the subshells could not append themselves.
  for f in "$PAR_DIR"/*.failed; do
    [ -e "$f" ] || continue
    local name; name="$(basename "$f" .failed)"
    FAILED_STEPS+=("$name")
    rm -f "$f"
  done
}

# Idempotent VIEW migrations. First so a schema fix lands on the next pass
# after a deploy rather than waiting for the 6am daily run; a cheap no-op
# once applied (each migration skips itself). See data/view_migrations.py.
step apply-view-migrations

# GROUP 1 — market + model inputs. Every one of these is an independent
# producer writing its own table (odds, player_prop_odds, lineups, injuries,
# weather, public betting), and every one is network-bound. They only have to
# finish before SCORING reads them, not before each other.
par odds
par prop-odds
par wnba-prop-odds
par nba-prop-odds
par lineups
# The MODEL's own inputs, not just the market's. Until 2026-08-30 these ran at
# 6am only, so the price re-priced all day against a frozen view of who was
# hurt and what the weather would do -- which is exactly what makes a
# late-crossing pick adverse rather than informed. Both are self-limiting
# (config.REFRESH_*_MAX_AGE_MIN), so running them on all ~42 passes does not
# mean fetching 42 times: ESPN has IP-blocked this worker twice.
par injuries-refresh
par weather-refresh
par public-betting
par_wait

# GROUP 2 — scoring. Reads everything above, so it MUST come after the wait.
# The four scorers touch different model families and different pick rows, but
# they share the picks table and the same look-ahead delete window, so they
# stay sequential: concurrent deletes over overlapping windows is exactly how
# a board gets emptied (§7), and the measured cost here is ~25s, not minutes.
step scoring
step prop-scoring
step wnba-prop-scoring
step nba-prop-scoring
# Golf data + scoring run last so a DataGolf hiccup can never abort the
# chain before game/prop picks are scored above.
step golf-field
step golf-odds
step golf-scoring
# Safety net: prune NONE picks for games that have already started so the
# day's prop NONE rows don't pile past the app's row cap (which would
# drop the morning's locked signals off the board). Runs after scoring.
step cleanup-picks
# Lock the first BET cross per market into the opening-signal shadow
# track. Must run last — after every game + prop scoring step above.
step opening-signals
# Lock the day's canonical cross-game parlay (public parlay record).
# Must run after opening-signals (it reads the locked legs).
step parlay-track-record
# Push new/dropped signal alerts + track-a-bet line-change alerts off
# this refresh's latest odds (idempotent via the push_sent ledger).
step push-notifications

# ── Settlement ───────────────────────────────────────────────────────────────
# Grade games as they finish instead of waiting for the 6am run. Everything
# below is idempotent (settlement only touches result IS NULL) and cheap.
#
# Order matters: the results/box-score ingests must precede settle, or there is
# nothing new for it to grade.
#
# Final scores for MLB are fetched by settle itself, so MLB game-level picks
# need nothing extra. Everything below supplies what the OTHER sports' picks —
# and MLB props — settle against.
#
# Every-pass steps are the ones that cost nothing when there is nothing to do:
#   game-log-today   skips per game; no boxscore call for games already stored
#   nfl-results      returns without fetching unless a started NFL game is unscored
#   nhl-results      3 calls to a free API; no-ops out of season
#   ufc-results-poll one HEAD against the mirror's ETag unless a card has landed
# GROUP 3 — results ingests. Independent of each other, each hitting a
# different external service, and all of them must finish before settle.
par game-log-today
par nfl-results
par nhl-results
par ufc-results-poll
par_wait

# Hourly only. Both hit an external service hard enough that a 10-minute
# cadence is a real risk: WNBA results is ~40 ESPN calls per game (ESPN
# IP-blocked this worker in August, and WNBA settlement was dead for two
# weeks), and golf results is a per-event DataGolf pull.
if [ "$MODE" = "hourly" ]; then
  step wnba-results
  step golf-results
fi

step settle

# Health check LAST, on every pass. It used to run only as the final step of the
# daily 6am pipeline, so a break that only affected refresh passes was invisible
# for up to 24 hours - exactly what happened 8/24-8/27. It is pure SQL over
# tables already written, so running it hourly is cheap.
step health-check

# Close the ledger row. Runs whatever happened above, so a pass that completes
# with failures is still recorded as finished-with-failures rather than missing.
python -m tracking.run_ledger finish --run-id "$RUN_ID" \
    --steps-total "$STEPS_TOTAL" --failed "${FAILED_STEPS[*]:-}" 2>/dev/null || true

if [ ${#FAILED_STEPS[@]} -gt 0 ]; then
  echo "refresh pass finished with ${#FAILED_STEPS[@]} failed step(s): ${FAILED_STEPS[*]}" >&2
  exit 1
fi
