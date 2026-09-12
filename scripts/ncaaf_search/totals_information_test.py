"""
Does the NCAAF totals regression know anything DraftKings' closing total does not?

The `docs/nfl_prop_information_test.md` harness, applied to `ncaaf_over_under`
(session 280, 2026-09-10). The totals rule was validated as a win rate at a
gate (55.9% / +6.7% at |pred - line| >= 8, CI not clearing breakeven); it has
never had the information test the eleven NFL prop models got, which is the
question a win rate cannot answer: is the disagreement with the line
INFORMATION, or a calibrated copy of the line plus noise?

    logit P(over) = a + c * logit(book_fair) + b * z,   z = (pred - line) / sd

fitted on one season, read on another. The projection adds something only
if `b` is positive with an interval excluding zero in a season the fit never
saw, and the blend beats the book on Brier there. Two independent pairs:
fit 2023 -> read 2024, fit 2024 -> read 2025.

DEFINITIONS (fixed before any number was looked at)
- Rows: the `totals_lead.py --csv` table at lead == "close" (walk-forward
  prediction per test season, graded at DraftKings' last pre-kick total in
  the 2023-25 backfill). One row per game; pushes dropped.
- book_fair: DK's over/under prices at that closing snapshot, de-vigged
  (over_implied / (over_implied + under_implied)). A game with no price pair
  is dropped, and the count is printed.
- p_over (the model's own claim): the OOS-residual ECDF the scorer uses,
  rebuilt per TRAIN season from that season's own walk-forward residuals
  (actual - pred), evaluated at line - pred: P(over) = 1 - ECDF(line - pred).
  Clipped to [0.02, 0.98] so the logit is finite.
- Bets: the blend against the DK price at 3/5/8 pp of edge, graded at the
  quoted price, bootstrap CI as in the NFL harness.

    python -m scripts.ncaaf_search.totals_information_test --rows /tmp/totals_lead_rows.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from data.db import get_connection                       # noqa: E402
from scripts.nfl_prop_information_test import analyse, implied  # noqa: E402


def closing_prices(conn, game_ids: list[str]) -> pd.DataFrame:
    """DK's last pre-kick totals row per game: line, over and under price."""
    out = []
    for i in range(0, len(game_ids), 500):
        chunk = game_ids[i:i + 500]
        ph = ",".join(["%s"] * len(chunk))
        rows = conn.execute(f"""
            SELECT DISTINCT ON (o.game_id) o.game_id, o.total_line,
                   o.over_price, o.under_price
            FROM odds o JOIN games g ON g.game_id = o.game_id
            WHERE o.game_id IN ({ph}) AND o.bookmaker = 'draftkings'
              AND o.market = 'totals' AND o.snapshot_type <> 'in_play'
              AND o.snapshot_at::timestamptz < g.commence_time::timestamptz
            ORDER BY o.game_id, o.snapshot_at DESC
        """, chunk).fetchall()
        out += [dict(game_id=r[0], dk_line=r[1], over_price=r[2], under_price=r[3])
                for r in rows]
    return pd.DataFrame(out)


def devig(over_price, under_price):
    po, pu = implied(over_price), implied(under_price)
    return po / (po + pu)


def ecdf_p_over(train: pd.DataFrame, target: pd.DataFrame) -> np.ndarray:
    resid = np.sort((train["actual"] - train["pred"]).values)
    x = (target["line"] - target["pred"]).values
    # P(actual - pred > line - pred)
    cdf = np.searchsorted(resid, x, side="right") / len(resid)
    return np.clip(1.0 - cdf, 0.02, 0.98)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--rows", required=True, help="totals_lead.py --csv output")
    ap.add_argument("--cuts", nargs="+", type=float, default=[0.03, 0.05, 0.08])
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    t = pd.read_csv(args.rows)
    c = t[t["lead"] == "close"].copy()
    print(f"rows at close: {len(c)} across seasons {sorted(c['season'].unique().tolist())}")

    conn = get_connection()
    try:
        px = closing_prices(conn, c["game_id"].tolist())
    finally:
        conn.close()
    c = c.merge(px, on="game_id", how="left")
    have = c["over_price"].notna() & c["under_price"].notna()
    print(f"with a DK price pair at the close: {int(have.sum())} "
          f"(dropped {int((~have).sum())})")
    c = c[have].copy()
    c["fair_over"] = [devig(o, u) for o, u in zip(c["over_price"], c["under_price"])]
    # The rows' `line` is the same DK close the harness graded at; keep it.
    c["actual"] = c["actual"].astype(float)

    rng = np.random.default_rng(args.seed)
    for train, test in ((2023, 2024), (2024, 2025)):
        tr = c[c["season"] == train]
        c.loc[c["season"] == train, "p_over"] = ecdf_p_over(tr, tr)
        c.loc[c["season"] == test, "p_over"] = ecdf_p_over(tr, c[c["season"] == test])
        df = c[c["season"].isin([train, test])].copy()
        res = analyse(df, rng, args.cuts, train=train, test=test)
        print(f"\n== fit {train} -> read {test} ==")
        for k, v in res.items():
            if k == "bets":
                for cut, g in v.items():
                    print(f"  blend as a bet, cut {cut:.2f}: {g}")
            elif isinstance(v, float):
                print(f"  {k:16s} {v:+.4f}")
            else:
                print(f"  {k:16s} {v}")
        # The rule's own claim on the test season, for the record.
        te = df[df["season"] == test]
        y = (te["actual"] > te["line"]).astype(float)
        print(f"  model mean P(over) {te['p_over'].mean():.3f} vs actual over-rate "
              f"{y.mean():.3f} vs book fair {te['fair_over'].mean():.3f}")


if __name__ == "__main__":
    main()
