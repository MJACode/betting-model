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
#   bash nfl/scripts/live_prop_job.sh bias      # one decision point, no model
#   bash nfl/scripts/live_prop_job.sh slice     # ZERO credits, cached snapshots
#
# SLICE MODE spends NOTHING. It re-reads the snapshots already paid for and
# sitting on the volume and asks whether the pass attempt bias is uniform
# across game states or concentrated in one slice. It never touches the Odds
# API: no plan, no probe, no pull, so it cannot cost a credit even on a cache
# miss. That property is the point and is why it exits before the probe.
#
# BIAS MODE answers the only question that decides the lane, and answers it
# without a model: is the book's posted line still sitting below the actual
# final? Set PULL_SEASONS to the season under test and PULL_POINTS to a
# single decision point; that is a fifth of the credits of a full pull.
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

# Cap the thread pools. Every one of these libraries sizes its pool from the
# HOST core count while the cgroup grants a fraction, and the oversubscription
# that follows is what turned the first grading run into 25 silent minutes at
# zero percent CPU.
export OMP_NUM_THREADS="${OMP_NUM_THREADS:-2}"
export LGB_NUM_THREADS="${LGB_NUM_THREADS:-2}"
export OPENBLAS_NUM_THREADS="${OPENBLAS_NUM_THREADS:-2}"
export MKL_NUM_THREADS="${MKL_NUM_THREADS:-2}"

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

# The bias question needs no model and no history: only the book's line
# against the actual final, for the season being tested. One decision point
# instead of five is a fifth of the credits.
if [ "${MODE}" = "bias" ]; then
  SEASONS="${PULL_SEASONS}"
  export PULL_POINTS="${PULL_POINTS:-1800}"
  echo "BIAS MODE: seasons ${PULL_SEASONS}, decision points ${PULL_POINTS}"
fi

# lightgbm is not in the platform's requirements.txt (nothing else in the repo
# trains one) and the grading step needs it. Installing here rather than in the
# shared requirements keeps the production worker's build untouched.
if ! python -c "import lightgbm" 2>/dev/null; then
  echo "=== installing lightgbm ==="
  pip install --quiet lightgbm
fi

# The ledger records the MEASURED cost per call, and --run refuses to start
# without it. It lives outside the snapshot cache, so a dead container takes it
# with it while the paid snapshots survive on the volume. Keep a copy on the
# volume so a resume never has to re-pay for a probe.
LEDGER=data/live_model/prop_pull_ledger.json
LEDGER_BACKUP=data/live_model/prop_snaps/_ledger_backup.json
if [ -f "${LEDGER_BACKUP}" ]; then
  mkdir -p "$(dirname "${LEDGER}")"
  cp "${LEDGER_BACKUP}" "${LEDGER}"
  echo "restored the credit ledger from the volume"
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

if [ "${MODE}" = "slice" ]; then
  echo "=== building flow rows for ${PULL_SEASONS} ==="
  python - <<PYEOF
from live_model.backtest.flow_dataset import build_flow_rows
from live_model.config import ARTIFACT_DIR
f = build_flow_rows([int(s) for s in "${PULL_SEASONS}".split()])
f.to_parquet(ARTIFACT_DIR / "flow_rows.parquet", index=False)
print(f"{len(f):,} flow rows, {f.season.nunique()} seasons")
PYEOF

  echo "=== subgroup slice: is the bias structural or one slice? (0 credits) ==="
  python -m live_model.backtest.flow_slice \
    --market "${SLICE_MARKET:-player_pass_attempts}" --seasons ${PULL_SEASONS}
  echo "=== line churn: would finer data buy anything? (0 credits) ==="
  python -m live_model.backtest.line_churn \
    --market "${SLICE_MARKET:-player_pass_attempts}"

  echo "=== slice done, no Odds API call was made ==="
  exit 0
fi

echo "=== plan (free) ==="
python -m live_model.backtest.pull_prop_snaps \
  --plan --seasons ${PULL_SEASONS} --budget "${BUDGET}"

# Always probe. On a resumed run the same four snapshots are cache hits, so
# this costs nothing and still rewrites the ledger the run mode requires.
echo "=== probe (measures real cost per call) ==="
python -m live_model.backtest.pull_prop_snaps \
  --probe --seasons ${PULL_SEASONS} --budget "${BUDGET}"

if [ "${MODE}" = "bias" ]; then
  echo "=== building flow rows for ${PULL_SEASONS} ==="
  python - <<PYEOF
from live_model.backtest.flow_dataset import build_flow_rows
from live_model.config import ARTIFACT_DIR
f = build_flow_rows([int(s) for s in "${PULL_SEASONS}".split()])
f.to_parquet(ARTIFACT_DIR / "flow_rows.parquet", index=False)
print(f"{len(f):,} flow rows, {f.season.nunique()} seasons")
PYEOF

  echo "=== pulling one decision point for ${PULL_SEASONS} ==="
  python -m live_model.backtest.pull_prop_snaps \
    --run --seasons ${PULL_SEASONS} --budget "${BUDGET}"

  echo "=== book bias: line against the actual final, no model ==="
  python -m live_model.backtest.flow_bias --seasons ${PULL_SEASONS}
fi

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

if [ -f "${LEDGER}" ]; then
  cp "${LEDGER}" "${LEDGER_BACKUP}"
fi

echo "=== credits spent ==="
cat data/live_model/prop_pull_ledger.json 2>/dev/null || echo "no ledger written"
echo "=== job complete ==="
