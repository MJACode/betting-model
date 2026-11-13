"""2026 forward check: an 11-seed average of the live totals regression (fit on 2015-2025, the live
artifact's own seasons) against 2026 games. One production read through the repo's frame builder."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from paths import REPO as ROOT  # noqa: E402
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from scripts.ncaaf_margin_eval import TOTAL_FEATURES, _matrix, build_frames  # noqa: E402
from scripts.ncaaf_search.totals_lead import DEFAULT_SEASONS  # noqa: E402
from xgboost import XGBRegressor  # noqa: E402

from paths import CACHE as D, TOTALS_ARTIFACT  # noqa: E402
SEEDS = [42, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
frame = build_frames(DEFAULT_SEASONS + [2026])
frame.to_pickle(D / "totals_frame_2026.pkl")
print("frame", frame.shape, frame.groupby("_season").size().to_dict(), flush=True)
tr, cols = _matrix(frame[frame["_season"] <= 2025], TOTAL_FEATURES)
te, _ = _matrix(frame[frame["_season"] == 2026], TOTAL_FEATURES)
print("train", len(tr), "2026 rows", len(te), "of", int((frame._season == 2026).sum()), flush=True)
out = te[["_game_id", "_season", "_total", "_total_line"]].copy()
for s in SEEDS:
    m = XGBRegressor(n_estimators=700, learning_rate=0.03, max_depth=5, subsample=0.8, colsample_bytree=0.8,
                     min_child_weight=5, objective="reg:squarederror", n_jobs=-1, random_state=s)
    m.fit(tr[cols], tr["_total"])
    out[f"p{s}"] = m.predict(te[cols])
    print("seed", s, flush=True)
out["pavg"] = out[[f"p{s}" for s in SEEDS]].mean(axis=1)
# the live artifact itself on the same rows
import pickle  # noqa: E402
art = pickle.load(open(TOTALS_ARTIFACT, "rb"))
fc = art["feature_cols"]
X = te.reindex(columns=fc)
for c in fc:
    X[c] = pd.to_numeric(X[c], errors="coerce")
out["plive"] = art["model"].predict(X[fc])
out.to_parquet(D / "totals_2026_bag.parquet")
d = out.pavg - out._total_line
print("2026 games predicted:", len(out), "| mean(avg model - line)", round(d.mean(), 2), "| mean(live artifact - line)",
      round((out.plive - out._total_line).mean(), 2), "| corr(avg, live)", round(np.corrcoef(out.pavg, out.plive)[0, 1], 4))
