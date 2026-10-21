"""Pool the priced prop backtest across seasons, per BET, and print the table.

`scripts.nhl_prop_lab_priced --season S --dump S.csv` writes every bet behind
every row of its tables. Three seasons of those, pooled here: one row per
(rule, market, cut) with bets, units, ROI and a 95% interval over the POOLED
bets (not an average of three season ROIs), then each season's ROI and count
beside it. The interval is the ordinary normal one on per-bet profit, the same
`summarise` the labs print.

    python -m scripts.nhl_prop_pool a.csv b.csv c.csv [--rules "MODEL @ DraftKings"]
"""
from __future__ import annotations

import argparse
import sys

import pandas as pd

sys.path.insert(0, ".")

from scripts.nhl_market_lab import summarise  # noqa: E402

RULES = ("MODEL @ DraftKings", "MODEL @ best bettable book")


def pooled(df: pd.DataFrame, rules=RULES) -> pd.DataFrame:
    out = []
    seasons = sorted(df.season.unique())
    for (rule, market, cut), g in df[df.rule.isin(rules)].groupby(["rule", "market", "cut"]):
        row = {"rule": rule, "market": market, "EV>=": cut, **summarise(g.profit.values),
               "under share": round(float((g.side == "under").mean()), 2)}
        for s in seasons:
            gs = g[g.season == s]
            row[f"{s - 1}-{str(s)[2:]}"] = (f"{gs.profit.mean() * 100:+.1f}% ({len(gs):,})"
                                            if len(gs) else "-")
        out.append(row)
    return pd.DataFrame(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dumps", nargs="+")
    ap.add_argument("--rules", nargs="*", default=list(RULES))
    a = ap.parse_args()
    df = pd.concat(pd.read_csv(p) for p in a.dumps)
    pd.set_option("display.width", 250)
    print(f"{len(df):,} bet rows over seasons {sorted(df.season.unique())}\n")
    for market, t in pooled(df, a.rules).groupby("market", sort=False):
        print(f"### {market}\n")
        print(t.drop(columns="market").to_string(index=False))
        print()


if __name__ == "__main__":
    main()
