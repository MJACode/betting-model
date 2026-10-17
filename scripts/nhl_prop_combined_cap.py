"""All four NHL prop models graded TOGETHER: what a per-game cap across them, and
one bet per player, would have done over the three priced seasons.

    python -m scripts.nhl_prop_combined_cap

Read-only. Builds each model's walk-forward sides with the production backtest
code, caches them in the temp folder (nhl_cache4), then sweeps the combined rules.
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, ".")
import numpy as np
import pandas as pd

import scripts.nhl_prop_backtest as bt
import models.nhl_props as np_

C = Path(tempfile.gettempdir()) / "nhl_cache4"     # a cache of database reads, regenerable
C.mkdir(exist_ok=True)
pd.set_option("display.width", 300)
pd.set_option("display.max_columns", 40)
CUT = 0.10
KEEP = ["model_id", "game_id", "pkey", "game_date", "season", "side", "price", "p", "ev", "profit", "won", "book", "line"]


def build():
    data = bt.load(None)
    frames, out = {}, []
    for spec in np_.SPECS.values():
        if spec.kind not in frames:
            frames[spec.kind] = np_.build_frame(spec, data[spec.kind], data["teams"])
        px = bt.prices(data, spec)
        pred = bt.predictions(spec, frames[spec.kind])
        m = px.merge(pred.drop(columns=["season"]), on=["game_id", "pkey"], how="inner")
        m = m[m.book.isin(list(np_.books()))]
        s = bt.sides(m)
        live = bt.card(s, CUT, spec.sides, per_game=spec.max_per_game)       # the live rule today
        nocap = bt.card(s, CUT, spec.sides, per_game=None)
        live["model_id"] = nocap["model_id"] = spec.model_id
        live["rule"], nocap["rule"] = "live", "nocap"
        out += [live, nocap]
        print(spec.model_id, "live", len(live), "no cap", len(nocap), flush=True)

    import scripts.nhl_prop_blocked_shots_backtest as bsb
    import models.nhl_prop_blocked_shots as bs
    from data.db import get_connection
    conn = get_connection()
    try:
        frame = bs.build_frame(bs.load_skaters(conn), bs.load_teams(conn))
        s = bsb.bets(frame, conn)
    finally:
        conn.close()
    b = bsb.card(s, "ev", CUT, -200)
    b = b.assign(model_id="nhl_prop_blocked_shots", book="draftkings", won=(b.profit > 0).astype(int),
                 game_date=pd.to_datetime(b.game_date))
    for rule in ("live", "nocap"):
        out.append(b.assign(rule=rule))
    print("blocked live", len(b), flush=True)
    allb = pd.concat([x.assign(game_date=pd.to_datetime(x.game_date))[KEEP + ["rule"]] for x in out], ignore_index=True)
    allb.to_pickle(C / "bets.pkl")
    return allb


def summary(label, b):
    p = b.profit.values
    per_night = b.groupby("game_date").size()
    per_game = b.groupby("game_id").size()
    r = {**label, "bets": len(b), "units": round(float(p.sum()), 1), "roi%": round(float(p.mean()) * 100, 2),
         "95% by day": bt.day_interval(b), "bets/night": round(float(per_night.mean()), 1),
         "max/night": int(per_night.max()), "max/game": int(per_game.max())}
    for season in bt.SEASONS:
        q = b[b.season == season].profit.values
        r[f"{season - 1}-{str(season)[2:]}"] = f"{q.mean() * 100:+.1f}% ({len(q)})" if len(q) else "(0)"
    return r


def cap(b, n, one_per_player):
    b = b.sort_values("ev", ascending=False, kind="mergesort")
    if one_per_player:
        b = b.drop_duplicates(["game_id", "pkey"])
    if n is not None:
        b = b.groupby("game_id", sort=False).head(n)
    return b.sort_values(["game_date", "game_id", "pkey"])


def main():
    allb = pd.read_pickle(C / "bets.pkl") if (C / "bets.pkl").exists() else build()
    live = allb[allb.rule == "live"]
    nocap = allb[allb.rule == "nocap"]
    rows = [summary({"rule": "each model alone (today)", "model": m}, live[live.model_id == m])
            for m in sorted(live.model_id.unique())]
    rows.append(summary({"rule": "TODAY: all four together", "model": "all"}, live))
    print(pd.DataFrame(rows).to_string(index=False))
    rows = []
    for opp in (False, True):
        for n in (1, 2, 3, 4, 5, 6, None):
            rows.append(summary({"cap per game (all 4)": n if n else "none", "1 per player": opp},
                                cap(nocap, n, opp)))
    print("\n### Combined cap across all four, best EV first (SOG's own cap of 3 replaced by the combined one)\n")
    print(pd.DataFrame(rows).to_string(index=False))
    print("\nshare of today's-rule bets that are unders:", round(float((live.side == "under").mean()), 4))


if __name__ == "__main__":
    main()
