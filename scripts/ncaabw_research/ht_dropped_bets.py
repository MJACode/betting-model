"""Which of the halftime total's replayed bets the in-play write bug would have dropped, and how they did
(2026-11-16, docs/sports/ncaabw.md, "Why the women's record trails the men's").

The bug (fixed in #1407): a bet was never stored when DraftKings had no quote at the bet's total, on the
side taken, in the same read. In the replay a read is a five-minute snapshot of the odds feed, so a bet
counts as dropped when its snapshot holds no DraftKings totals row for the game at that total with a
price on that side.

Prints only. Reads the decisions `scripts.build_ncaabw_live_ht_artifact --keep DIR` saves (the
production reading) and the research cache's in-play quotes.

    python -m scripts.build_ncaabw_live_ht_artifact --keep DIR
    python -m scripts.ncaabw_research.ht_dropped_bets DIR

Stake: one unit to win, risk capped at 3, at the quoted price.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.ncaabw_research._paths import CACHE  # noqa: E402

CUT = 0.05
LABEL = {2026: "2025-26 (walk-forward)", 2025: "2024-25 (second look)", 2027: "2026-27 to date"}


def line(name, z):
    if not len(z):
        return f"  {name:34s}    0 bets"
    roi = z["units"].sum() / z["risk"].sum() * 100
    w, l = int((z["units"] > 0).sum()), int((z["units"] < 0).sum())
    return f"  {name:34s} {len(z):4d} bets  {w}-{l}  {z['units'].sum():+7.2f} units  {roi:+6.2f}%"


def main(keep: Path) -> None:
    Q = pd.read_parquet(CACHE / "inplay_quotes.parquet")
    Q = Q[(Q["market"] == "totals") & (Q["bookmaker"] == "draftkings")]
    Q = Q[["snapshot_ts", "game_id", "total_line", "over_price", "under_price"]]
    for s in (2026, 2025, 2027):
        f = keep / f"ht_decisions_production_{s}.parquet"
        if not f.exists():
            print(f"\n{LABEL[s]}: {f.name} not found")
            continue
        b = pd.read_parquet(f)
        b = b[b["ev"] >= CUT].copy()
        m = b.merge(Q, on=["snapshot_ts", "game_id"], how="left")
        side_price = np.where(m["side"] == "over", m["over_price"], m["under_price"])
        m["dk_same"] = (m["total_line"].sub(m["line"]).abs() < 1e-9) & pd.notna(side_price)
        kept = m.groupby(["game_id", "snapshot_ts"])["dk_same"].any().rename("stored")
        b = b.merge(kept, left_on=["game_id", "snapshot_ts"], right_index=True, how="left")
        b["stored"] = b["stored"].fillna(False).astype(bool)
        print(f"\n{LABEL[s]}: {len(b)} bets at EV >= {CUT}")
        print(line("all bets", b))
        print(line("stored even with the bug", b[b["stored"]]))
        print(line("dropped by the bug (now stored)", b[~b["stored"]]))
        print(f"  dropped share {(~b['stored']).mean():.1%}; their books "
              f"{b.loc[~b['stored'], 'book'].value_counts().to_dict()}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
