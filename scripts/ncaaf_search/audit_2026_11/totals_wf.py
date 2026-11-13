"""Walk-forward out-of-sample predictions of the live NCAAF totals regression, cached once.

One read of the production tables through the repo's own frame builder (the same call
scripts/ncaaf_search/totals_lead.py makes), then everything else works from the cache.
"""
import sys
from pathlib import Path

import pandas as pd

from paths import REPO as ROOT  # noqa: E402
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
from scripts.ncaaf_margin_eval import build_frames  # noqa: E402
from scripts.ncaaf_search.totals_lead import oos_predictions, DEFAULT_SEASONS  # noqa: E402

from paths import CACHE as D  # noqa: E402
frame = build_frames(DEFAULT_SEASONS)
print("frame", frame.shape, sorted(frame["_season"].unique().tolist()))
frame.to_pickle(D / "totals_frame.pkl")
pred = oos_predictions(frame, [2022, 2023, 2024, 2025])
pred.to_parquet(D / "totals_oos.parquet")
print(pred.groupby("_season").size().to_string())
d = pred.pred - pred._total_line
print("mean(pred-line) by season:", d.groupby(pred._season).mean().round(2).to_dict())
print("mean(actual-line) by season:", (pred._total - pred._total_line).groupby(pred._season).mean().round(2).to_dict())
