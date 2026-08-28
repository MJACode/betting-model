#!/usr/bin/env bash
# One-off runner for the live prop validation, for a Railway job service.
#
# WHY THIS EXISTS. The dev sandbox's gateway denies api.the-odds-api.com, so
# the pull cannot run there. Railway can reach it and already holds
# ODDS_API_KEY, so a short-lived service in the same project is the cheapest
# way to get a real answer without waiting on a human to press a button.
#
#   bash nfl/scripts/live_prop_job.sh probe            # a few dozen credits
#   bash nfl/scripts/live_prop_job.sh run 2023 2024    # the full pull
#
# The verdict prints to stdout, which is the Railway deploy log, so the whole
# answer is readable without an artifact store. Disk here is ephemeral: a
# `run` must therefore pull AND grade in the same invocation, because losing
# the snapshots means re-paying for them.

set -euo pipefail

MODE="${1:-probe}"
shift || true
SEASONS="${*:-2023 2024}"
BUDGET="${BUDGET:-114000}"

cd "$(dirname "$0")/.."

if [ -z "${THE_ODDS_API_KEY:-}" ] && [ -z "${ODDS_API_KEY:-}" ]; then
  echo "FATAL: neither THE_ODDS_API_KEY nor ODDS_API_KEY is set."
  exit 1
fi

echo "=== fetching play-by-play ==="
python -m live_model.backtest.pull_pbp --seasons ${SEASONS}
curl -sfL --retry 3 -o data/pbp/players.parquet \
  "https://github.com/nflverse/nflverse-data/releases/download/players/players.parquet"

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
  --plan --seasons ${SEASONS} --budget "${BUDGET}"

echo "=== probe (measures real cost per call) ==="
python -m live_model.backtest.pull_prop_snaps \
  --probe --seasons ${SEASONS} --budget "${BUDGET}"

if [ "${MODE}" = "run" ]; then
  echo "=== building the flow dataset ==="
  python - <<PY
from live_model.backtest.flow_dataset import build_flow_rows
from live_model.config import ARTIFACT_DIR
f = build_flow_rows([int(s) for s in "${SEASONS}".split()])
f.to_parquet(ARTIFACT_DIR / "flow_rows.parquet", index=False)
print(f"{len(f):,} flow rows")
PY

  echo "=== pulling snapshots ==="
  python -m live_model.backtest.pull_prop_snaps \
    --run --seasons ${SEASONS} --budget "${BUDGET}"

  echo "=== grading against the real lines ==="
  python -m live_model.backtest.flow_validate
fi

echo "=== credits spent ==="
cat data/live_model/prop_pull_ledger.json 2>/dev/null || echo "no ledger written"
echo "=== job complete ==="
