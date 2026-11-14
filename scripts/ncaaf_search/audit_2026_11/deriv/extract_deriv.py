"""Extract the bought NCAAF first-half and team-total quotes from the local copy of `odds`.

Reads the mirror only (docs/local_ops.md). Writes CACHE/deriv_odds.parquet: every row stored under
`odds_api_ncaaf_derivative_am` / `_pm` (data/ingestors/ncaaf_derivative_history.py), plus the purchase
ledger as CACHE/deriv_ledger.parquet.
"""
import sys
from pathlib import Path

import pyarrow.compute as pc
import pyarrow.dataset as ds

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR  # noqa: E402

SOURCES = ["odds_api_ncaaf_derivative_am", "odds_api_ncaaf_derivative_pm"]


def main():
    odds = ds.dataset(str(MIRROR / "public.odds"), format="parquet", exclude_invalid_files=True)
    print("odds columns:", ", ".join(f.name for f in odds.schema))
    t = odds.to_table(filter=pc.field("source").isin(SOURCES))
    df = t.to_pandas()
    print("rows", len(df), "| games", df.game_id.nunique())
    print(df.groupby(["source", "market"]).size().unstack(fill_value=0).to_string())
    print(df.groupby(["source", "snapshot_type"]).size().to_string())
    print(df.bookmaker.value_counts().to_string())
    df.to_parquet(CACHE / "deriv_odds.parquet")
    led = ds.dataset(str(MIRROR / "public.ncaaf_derivative_fetches"), format="parquet",
                     exclude_invalid_files=True).to_table().to_pandas()
    led.to_parquet(CACHE / "deriv_ledger.parquet")
    print("ledger", len(led))
    for m in sorted(df.market.unique()):
        print("\n", m)
        print(df[df.market == m].head(3).drop(columns=[c for c in ("odds_id",) if c in df]).to_string())


if __name__ == "__main__":
    main()
