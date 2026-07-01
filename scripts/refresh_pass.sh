#!/usr/bin/env bash
# One full odds-and-scoring refresh pass. This is the single source of truth for
# the refresh step chain — called once per run by refresh_picks.yml (hourly,
# 7am-5pm ET) and repeatedly by evening_lines.yml (every 10 minutes, 6pm-11pm ET).
# Edit the chain here, never inline in a workflow, so the two schedules can't drift.
#
# Requires: DATABASE_URL, ODDS_API_KEY, DATAGOLF_API_KEY, FETCH_F5_LIVE in the env.
set -euo pipefail

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
