"""2026 season replay of the totals rule in its live shape, for the live artifact and the seed average.

Each game: every stored pre-kick DraftKings total from 6.5 days before kickoff; the first one whose
line sits 8+ points from the model locks the bet at that line and DraftKings' price.
The live artifact's replay is checked against the bets the model actually placed.
"""
from pathlib import Path

import numpy as np
import pandas as pd

from lab import D, dec, stake

pd.set_option("display.width", 220)
RNG = np.random.default_rng(3)
P = pd.read_parquet(D / "totals_2026_bag.parquet").rename(columns={"_game_id": "fid", "_total": "total"})
g = pd.read_parquet(D / "ncaaf_games.parquet")
g["d"] = pd.to_datetime(g.game_date)
g["kick"] = pd.to_datetime(g.commence_time, utc=True, errors="coerce", format="mixed")
gi = g.set_index("game_id")
P["home"], P["away"], P["gd"] = P.fid.map(gi.home_team), P.fid.map(gi.away_team), P.fid.map(gi.d)

q = pd.read_parquet(D / "q_2026_long.parquet")
q = q[(q.market == "totals") & (q.bookmaker == "draftkings") & q.total_line.notna() & q.over_price.notna() & q.under_price.notna()]
qg = g[g.game_id.isin(set(q.game_id))][["game_id", "home_team", "away_team", "d", "kick"]]
# frame game -> odds game: same two teams, date within a day
idx = {}
for r in qg.itertuples(index=False):
    idx.setdefault(frozenset((r.home_team, r.away_team)), []).append(r)
m = {}
for r in P.itertuples(index=False):
    c = [x for x in idx.get(frozenset((r.home, r.away)), []) if abs((x.d - r.gd).days) <= 1]
    if len(c) >= 1:
        m[r.fid] = max(c, key=lambda x: (q.game_id == x.game_id).sum()).game_id if len(c) > 1 else c[0].game_id
P["oid"] = P.fid.map(m)
print("2026 frame games:", len(P), "| matched to a game with stored DraftKings totals:", int(P.oid.notna().sum()))
P = P[P.oid.notna()].drop_duplicates("oid")
q = q.merge(qg[["game_id", "kick"]], on="game_id").merge(P[["oid", "total", "pavg", "plive", "p42"]], left_on="game_id", right_on="oid")
q = q[(q.pull_ts < q.kick - pd.Timedelta(minutes=5)) & (q.pull_ts >= q.kick - pd.Timedelta(days=6.5))].sort_values(["game_id", "pull_ts"])
print("DraftKings pre-kick totals rows inside 6.5 days:", len(q), "games", q.game_id.nunique())


def replay(col, gate=8.0):
    x = q.assign(dd=q[col] - q.total_line)
    h = x[x.dd.abs() >= gate].drop_duplicates("game_id")
    over = h.dd > 0
    res = np.sign(np.where(over, h.total - h.total_line, h.total_line - h.total))
    price = np.where(over, h.over_price, h.under_price)
    risk, win = stake(dec(price))
    pnl = np.where(res > 0, win, np.where(res < 0, -risk, 0.0))
    return h.assign(over=over, res=res, pnl=pnl, rk=np.where(res != 0, risk, 0.0), price=price,
                    date=h.kick.dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d"))


def show(tag, h):
    w, l, p = int((h.res > 0).sum()), int((h.res < 0).sum()), int((h.res == 0).sum())
    by = h.groupby("date").agg(p=("pnl", "sum"), r=("rk", "sum"))
    idx = RNG.integers(0, len(by), size=(2000, len(by)))
    boot = by.p.to_numpy()[idx].sum(1) / np.maximum(by.r.to_numpy()[idx].sum(1), 1e-9)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    print(f"{tag:<34} {len(h):>4} {w}-{l}-{p}  {h.pnl.sum():+7.2f}u {100*h.pnl.sum()/h.rk.sum():+6.1f}% [{100*lo:+.0f},{100*hi:+.0f}]"
          f"  overs {int(h.over.sum())} ({h[h.over].pnl.sum():+.1f}u) unders {int((~h.over).sum())} ({h[~h.over].pnl.sum():+.1f}u)")


for gate in (7.0, 8.0, 9.0, 10.0):
    print(f"\n-- gate {gate} --")
    hl = replay("plive", gate)
    ha = replay("pavg", gate)
    h42 = replay("p42", gate)
    show("live artifact, replayed", hl)
    show("seed 42 refit today", h42)
    show("11-seed average", ha)
    both = set(hl.game_id) & set(ha.game_id)
    print(f"   games bet by both: {len(both)}; only the live artifact: {len(set(hl.game_id)-both)}; only the average: {len(set(ha.game_id)-both)}")
    if gate == 8.0:
        only_l = hl[~hl.game_id.isin(both)]
        only_a = ha[~ha.game_id.isin(both)]
        show("   only the live artifact", only_l) if len(only_l) else None
        show("   only the average", only_a) if len(only_a) else None
        keep = (hl, ha)

# the replay of the live artifact against what it really bet
picks = pd.read_parquet(D / "ncaaf_picks.parquet")
real = picks[(picks.model_id == "ncaaf_over_under") & (picks.signal_type == "BET") & (picks.game_date >= "2026-08-01")
             & ~picks.condition_status.fillna("").isin(["VOID", "DUPLICATE"]) & picks.result.isin(["WIN", "LOSS", "PUSH"])]
hl = keep[0]
print("\nreal settled BETs:", len(real), "| replayed live-artifact bets:", len(hl), "| games in both:", len(set(real.game_id) & set(hl.game_id)),
      "| real bets on games the replay could not see (no frame row / no match):", len(set(real.game_id) - set(q.game_id)))
print("mean(model - DraftKings line) over every replay game's last row: live artifact",
      round(float((q.drop_duplicates('game_id', keep='last').plive - q.drop_duplicates('game_id', keep='last').total_line).mean()), 2),
      "| average", round(float((q.drop_duplicates('game_id', keep='last').pavg - q.drop_duplicates('game_id', keep='last').total_line).mean()), 2))
sd = P[[c for c in P.columns if c.startswith("p") and c[1:].isdigit()]].std(axis=1)
print("2026 seed-to-seed sd of one game's prediction: mean", round(sd.mean(), 2), "points")
