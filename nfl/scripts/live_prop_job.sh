#!/usr/bin/env bash
# One-off runner for the live prop validation, for a Railway job service.
#
# WHY THIS EXISTS. The dev sandbox's gateway denies api.the-odds-api.com, so
# the pull cannot run there. Railway can reach it and already holds
# ODDS_API_KEY, so a short-lived service in the same project is the cheapest
# way to get a real answer without waiting on a human to press a button.
#
#   bash nfl/scripts/live_prop_job.sh probe     # ~154 credits, measures cost
#   bash nfl/scripts/live_prop_job.sh run       # the full pull, then grades
#
# TWO SEASON SETS, and conflating them is the easy mistake. Snapshots are
# pulled only for PULL_SEASONS, because that is where the credits go. But
# flow_validate walks forward, training on every prior season, so the flow
# rows and their leak-free baselines need the FULL history or the anchor it
# grades against is not the anchor the model was measured on.
#
# The verdict prints to stdout, which is the Railway deploy log, so the whole
# answer is readable without an artifact store. Snapshots land in
# data/live_model/prop_snaps, which is a mounted volume: a cache hit costs
# zero credits, so a crash resumes instead of re-paying.

set -euo pipefail

MODE="${1:-probe}"
PULL_SEASONS="${PULL_SEASONS:-2023 2024}"
HISTORY_SEASONS="${HISTORY_SEASONS:-2015 2016 2017 2018 2019 2020 2021 2022 2023 2024}"
BUDGET="${BUDGET:-120000}"

cd "$(dirname "$0")/.."

if [ -z "${THE_ODDS_API_KEY:-}" ] && [ -z "${ODDS_API_KEY:-}" ]; then
  echo "FATAL: neither THE_ODDS_API_KEY nor ODDS_API_KEY is set."
  exit 1
fi

# Probe mode needs only the seasons it samples from; the full run needs the
# whole history for the walk-forward. Fetching ten seasons for a four-call
# probe would waste several minutes on every retry.
if [ "${MODE}" = "run" ]; then
  SEASONS="${HISTORY_SEASONS}"
else
  SEASONS="${PULL_SEASONS}"
fi

echo "=== fetching play-by-play: ${SEASONS} ==="
python -m live_model.backtest.pull_pbp --seasons ${SEASONS}
if [ ! -f data/pbp/players.parquet ]; then
  curl -sfL --retry 3 -o data/pbp/players.parquet \
    "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"
fi

echo "=== rebuilding game states ==="
python - <<PY
from live_model.backtest.states import load_pbp, build_states
from live_model.config import ARTIFACT_DIR
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
st = build_states(load_pbp([int(s) for s in "${SEASONS}".split()]))
st.to_parquet(ARTIFACT_DIR / "states_all.parquet", index=False)
print(f"{len(st):,} states, {st.game_id.nunique():,} games")
PY

echo "=== plan (free) ==="
python -m live_model.backtest.pull_prop_snaps \
  --plan --seasons ${PULL_SEASONS} --budget "${BUDGET}"

# Always probe. On a resumed run the same four snapshots are cache hits, so
# this costs nothing and still rewrites the ledger the run mode requires.
echo "=== probe (measures real cost per call) ==="
python -m live_model.backtest.pull_prop_snaps \
  --probe --seasons ${PULL_SEASONS} --budget "${BUDGET}"

if [ "${MODE}" = "run" ]; then
  echo "=== building the flow dataset over ${HISTORY_SEASONS} ==="
  python - <<PY
from live_model.backtest.flow_dataset import build_flow_rows
from live_model.config import ARTIFACT_DIR
f = build_flow_rows([int(s) for s in "${HISTORY_SEASONS}".split()])
f.to_parquet(ARTIFACT_DIR / "flow_rows.parquet", index=False)
print(f"{len(f):,} flow rows, {f.season.nunique()} seasons")
PY

  echo "=== pulling snapshots for ${PULL_SEASONS} ==="
  python -m live_model.backtest.pull_prop_snaps \
    --run --seasons ${PULL_SEASONS} --budget "${BUDGET}"

  echo "=== grading against the real lines ==="
  python -m live_model.backtest.flow_validate
fi

echo "=== credits spent ==="
cat data/live_model/prop_pull_ledger.json 2>/dev/null || echo "no ledger written"
echo "=== job complete ==="
