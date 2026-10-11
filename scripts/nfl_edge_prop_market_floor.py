"""What each EV floor would have bet: nfl_prop_market on its 2023-25 record,
and whether its 2026 production picks locked on quotes a book had pulled.

    python -m scripts.nfl_edge_prop_market_floor

WHY. nfl_prop_market is the one NFL model with a validated pre-game edge
(docs/nfl_prop_over_lean.md: 2023-25 +7.84% at a 5pp floor, +13.33% at
over 6pp / under 5pp). It has written no BET since 2026-09-19 20:27 UTC. The
worker's card log on 2026-10-11 prints the reason on every candidate:
"ev_below_floor:0.037<0.20 (p 0.573->0.506 at +105)". config.MODEL_OWN_EV_FLOOR
holds 0.20 for it. This prints what each floor would have bet on the record the
model was validated on, so the floor is a decision with numbers behind it.

PART A. Construction = scripts/nfl_edge_extreme_props.py Part 1 (the honest
board-synchronous version of the shipped rule): the latest board read stamped
before kickoff with lead <= 24h, references pinnacle / betonlineag, either,
proportional de-vig, a bettable soft book at the SAME line, the shipped side
cuts (over 6pp / under 5pp), one bet per (game, player, market), graded at the
best bettable price at that line on that read. THEN an EV floor:
EV = reference fair probability x decimal(best price) - 1, on the RAW
reference probability (the backtest has no calibration map; production applies
one, see the log line above, which only lowers EV further). Floors 0..0.20.

PART B. For every settled 2026 production BET (picks, model nfl_prop_market,
result WIN/LOSS/PUSH), was the selecting book still quoting that player and
market at the lock? From props_2026 (latest quote per lead bucket): the book's
newest quote for THIS proposition at or before created_at, against the same
book's newest quote for ANY player in the same game and market at or before
created_at. A gap of 2h or more means the book had stopped quoting the
proposition while it kept quoting the market: pulled, not placeable at lock.

Local cache only (scripts/nfl_edge_lib.py). No database, no Odds API.
Units: 1 unit = one flat bet.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from scripts import nfl_edge_lib as L
from scripts import nfl_edge_extreme_props as X

SIDE_CUT = {"over": 0.06, "under": 0.05}       # config NFL_PROP_MARKET_SIDE_EDGE
FLOORS = [0.0, 0.01, 0.02, 0.03, 0.05, 0.07, 0.10, 0.15, 0.20]

BOOK_LABEL = {"DK": "draftkings", "FD": "fanduel", "MGM": "betmgm",
              "CZR": "williamhill_us", "FAN": "fanatics", "BR": "betrivers",
              "HR": "hardrockbet", "PARX": "betparx"}


def part_a() -> None:
    books = set(L.BETTABLE) | set(X.REFS) | set(X.SOFT_0912)
    props = X.load_props(books)
    act = X.actuals()
    board = X.decision_boards(props)
    c = X.grade(X.add_modes(X.candidates(board, X.REFS, tuple(L.BETTABLE),
                                         tuple(L.BETTABLE)), X.REFS), act)
    sel = X.one_per_prop(c, "m_either", side_cut=SIDE_CUT)
    print("\nPART A. nfl_prop_market, shipped side cuts, then an EV floor (raw reference probability)")
    print(f"  {'floor':>6} {'bets':>5} {'/season':>8} {'units':>8} {'ROI%':>7} {'90% CI':>16} "
          f"| {'2023':>16} {'2024':>16} {'2025':>16}")
    for f in FLOORS:
        z = sel[sel["ev_either"] >= f]
        roi, (lo, hi) = L.boot_ci(z["profit"], z["game_id"]) if len(z) else (np.nan, (np.nan, np.nan))
        per = []
        for s in X.SEASONS:
            zs = z[z["season"] == s]
            per.append(f"{len(zs):>4} {100 * zs.profit.mean() if len(zs) else float('nan'):+6.1f}%")
        print(f"  {f:>6.2f} {len(z):>5} {len(z) / 3:>8.0f} {z.profit.sum():>+8.1f} {100 * roi:>+7.2f} "
              f"({100 * lo:>+6.1f},{100 * hi:>+6.1f}) | " + " | ".join(f"{p:>16}" for p in per))
    q = sel["ev_either"].quantile([.5, .9, .99])
    print(f"  EV of the selected bets: median {q.iloc[0]:.3f}, 90th pct {q.iloc[1]:.3f}, "
          f"99th pct {q.iloc[2]:.3f}, max {sel['ev_either'].max():.3f} (n={len(sel)})")


def _book_of(label: str) -> str | None:
    m = re.search(r"\(([^)]+)\)\s*$", label or "")
    if not m:
        return None
    tag = m.group(1).strip()
    return BOOK_LABEL.get(tag, tag.lower())


def part_b() -> None:
    p = pd.read_parquet(L.CACHE / "picks_nfl.parquet")
    b = p[(p.model_id == "nfl_prop_market") & (p.signal_type == "BET")
          & p.result.isin(["WIN", "LOSS", "PUSH"])].copy()
    b["book"] = b["pick_label"].map(_book_of)
    b["created_at"] = pd.to_datetime(b["created_at"], utc=True)
    pr = L.props_2026()
    pr = pr[pr["lead_label"] >= 0].copy()
    pr["snapshot_at"] = pd.to_datetime(pr["snapshot_at"], utc=True, format="mixed")
    pr["norm"] = pr["player_name"].map(X.norm_player_name)
    print(f"\nPART B. settled production BETs: {len(b)}")
    rows = []
    for r in b.itertuples():
        g = pr[(pr.game_id == r.game_id) & (pr.market == r.prop_market)
               & (pr.bookmaker == r.book) & (pr.snapshot_at <= r.created_at)]
        if g.empty:
            rows.append((r.pick_label, r.result, None, None, "no quote by that book in cache"))
            continue
        name = re.sub(r"\s+(Over|Under)\s.*$", "", r.pick_label)
        mine = g[g["norm"] == X.norm_player_name(name)]
        last_mkt = g["snapshot_at"].max()
        last_me = mine["snapshot_at"].max() if len(mine) else pd.NaT
        gap_h = (last_mkt - last_me).total_seconds() / 3600 if len(mine) else None
        rows.append((r.pick_label, r.result, last_me, gap_h,
                     "pulled at lock" if gap_h is not None and gap_h >= 2 else
                     ("quoted at lock" if gap_h is not None else "proposition not in cache")))
    t = pd.DataFrame(rows, columns=["pick_label", "result", "book_last_quote", "gap_h", "status"])
    print(t["status"].value_counts().to_string())
    print(t.groupby("status")["result"].value_counts().unstack(fill_value=0).to_string())
    print(t.sort_values("gap_h", ascending=False).head(12).to_string(index=False))


if __name__ == "__main__":
    part_a()
    part_b()
