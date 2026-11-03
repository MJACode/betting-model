"""Add the finished price table to the three NBA game total artifacts, and change
nothing else in them (models/nba_total_luck.py, THE PRICE TABLE IS STORED).

Refits store the table themselves (each model's build script). This is how the
artifacts of 2026-27 got theirs without a refit: each is loaded, the table of the
season it prices live is built from its own rows and added, and a new timestamped
file is written. Before it is accepted, every other key must pickle to the same bytes
as the old file's, and every array of the stored table must equal a full rebuild, on
the table itself and on the probabilities it gives.

Reads the committed files only: no database, no API. The new files are copied into
model_artifacts by each model's build script (--store), deliberately, not here.

    python -m scripts.nba_pricing_table_embed
"""
from __future__ import annotations

import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_first_half_total_luck as fh  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402

MODELS = (tl, tt, fh)
TABLE_VALUES = ("mean", "n", "sd", "label")


def tables_identical(a, b) -> bool:
    return (all(np.array_equal(getattr(a, k), getattr(b, k)) for k in a.TABLES)
            and all(getattr(a, k) == getattr(b, k) for k in TABLE_VALUES))


def probs_identical(a, b) -> bool:
    """The two tables' probabilities at every line from 80 to 280 by half points, which
    holds all three models' numbers, around centres a point either way by hundredths."""
    t = np.arange(80.0, 280.5, 0.5)[:, None]
    mu = t + np.arange(-1.0, 1.005, 0.01)[None, :]
    return all(np.array_equal(x, y) for x, y in zip(a.probs(mu, t), b.probs(mu, t)))


def embed(mod, stamp: str) -> Path:
    src = ROOT / mod.ARTIFACT_PATH
    with open(src, "rb") as f:
        old = pickle.load(f)
    if old.get("pricing_tables"):
        raise SystemExit(f"{src.name} already stores its table")
    new = tl.with_pricing_table(old, mod.pricing_dist, mod.newest_season)
    out = ROOT / "models" / "saved" / f"{mod.MODEL_ID}_{stamp}.pkl"
    with open(out, "wb") as f:
        pickle.dump(new, f, protocol=4)
    with open(out, "rb") as f:
        back = pickle.load(f)
    if set(back) != set(old) | {"pricing_tables"}:
        raise SystemExit(f"{out.name}: keys {sorted(back)}")
    for k, v in old.items():
        if pickle.dumps(v, protocol=4) != pickle.dumps(back[k], protocol=4):
            raise SystemExit(f"{out.name}: {k} changed")
    live = mod.newest_season(old) + 1
    mod._DIST_CACHE.clear()
    built = mod.pricing_dist(old, live)
    mod._DIST_CACHE.clear()
    stored = mod.pricing_dist(back, live)
    if stored is built or not tables_identical(stored, built) or not probs_identical(stored, built):
        raise SystemExit(f"{out.name}: the stored table is not a rebuild's")
    print(f"{out.relative_to(ROOT).as_posix()}: {out.stat().st_size / 1e6:.2f} MB, season {live}, "
          f"{stored.n} residuals; every other key identical, table and probabilities identical "
          f"to a full rebuild", flush=True)
    return out


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for mod in MODELS:
        embed(mod, stamp)


if __name__ == "__main__":
    main()
