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
set -euo pipefail
MODE="${1:-hourly}"

python run_pipeline.py --step odds
python run_pipeline.py --step prop-odds
python run_pipeline.py --step wnba-prop-odds
python run_pipeline.py --step nba-prop-odds
python run_pipeline.py --step lineups
python run_pipeline.py --step public-betting
python run_pipeline.py --step scoring
python run_pipeline.py --step prop-scoring
python run_pipeline.py --step wnba-prop-scoring
python run_pipeline.py --step nba-prop-scoring
# Golf data + scoring run last so a DataGolf hiccup can never abort the
# chain before game/prop picks are scored above.
python run_pipeline.py --step golf-field
python run_pipeline.py --step golf-odds
python run_pipeline.py --step golf-scoring
# Safety net: prune NONE picks for games that have already started so the
# day's prop NONE rows don't pile past the app's row cap (which would
# drop the morning's locked signals off the board). Runs after scoring.
python run_pipeline.py --step cleanup-picks
# Lock the first BET cross per market into the opening-signal shadow
# track. Must run last — after every game + prop scoring step above.
python run_pipeline.py --step opening-signals
# Lock the day's canonical cross-game parlay (public parlay record).
# Must run after opening-signals (it reads the locked legs).
python run_pipeline.py --step parlay-track-record
# Push new/dropped signal alerts + track-a-bet line-change alerts off
# this refresh's latest odds (idempotent via the push_sent ledger).
python run_pipeline.py --step push-notifications

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
python run_pipeline.py --step game-log-today
python run_pipeline.py --step nfl-results
python run_pipeline.py --step nhl-results
python run_pipeline.py --step ufc-results-poll

# Hourly only. Both hit an external service hard enough that a 10-minute
# cadence is a real risk: WNBA results is ~40 ESPN calls per game (ESPN
# IP-blocked this worker in August, and WNBA settlement was dead for two
# weeks), and golf results is a per-event DataGolf pull.
if [ "$MODE" = "hourly" ]; then
  python run_pipeline.py --step wnba-results
  python run_pipeline.py --step golf-results
fi

python run_pipeline.py --step settle
