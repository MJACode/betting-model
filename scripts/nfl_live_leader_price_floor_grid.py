"""Price-floor grid for nfl_live_leader_ml on the population of record.

    PYTHONIOENCODING=utf-8 python -m scripts.nfl_live_leader_price_floor_grid

Reads the same local research cache as the builder (NFL_EDGE_CACHE).

Same frames as `build_nfl_live_leader_artifact --population` (grading fits,
the loop's scoring/conversion refusal, DraftKings' pre-kickoff spread band,
state lagged behind the quote). A floor is applied INSIDE the rule, the way
gameday.platform_gates does it: a BET priced shorter than the floor is
refused and the game is tried again at its next snapshot.
"""
import io
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_nfl_live_leader_artifact as B  # noqa: E402
from nfl_live_leader import model as M  # noqa: E402
from tracking.discord_notifier import stake_for  # noqa: E402

FLOORS = [None, -2000, -1500, -1000, -800, -700, -600, -500, -400, -350, -300, -250, -200,
          -180, -160, -150, -140, -130, -120, -110]
LAGS = (0, 15, 30, 45)


def first_bets(x, art, spread_home, eligible, floor):
    bets, seen = [], set()
    for i, r in enumerate(x.itertuples(index=False)):
        if r.game_id in seen or not eligible[i]:
            continue
        poss = None if pd.isna(r.home_ball) else ("home" if int(r.home_ball) == 1 else "away")
        sp = None if pd.isna(spread_home[i]) else float(spread_home[i])
        d = M.decide(art, period=r.qtr, secs=r.secs, home_score=r.home_sc,
                     away_score=r.away_sc, possession=poss, spread_home=sp,
                     home_price=r.price_home, away_price=r.price_away)
        if not d.bet:
            continue
        if floor is not None and d.price < floor:
            continue                       # refused; the game is tried again later
        seen.add(r.game_id)
        fin = r.result if d.side == "home" else -r.result
        v = 1.0 if fin > 0 else (0.0 if fin < 0 else 0.5)
        st = stake_for(None, d.price)
        bets.append({"game_id": r.game_id, "price": d.price, "dec": d.decimal, "v": v,
                     "risk": st.risk, "win": st.win})
    b = pd.DataFrame(bets, columns=["game_id", "price", "dec", "v", "risk", "win"])
    b["pnl"] = B._grade(b.v, b.dec)
    b["pnl_pub"] = np.where(b.v == 1, b.win, np.where(b.v == 0, -b.risk, 0.0))
    return b


def main():
    from scripts import nfl_edge_inplay_2024 as B24
    from scripts import nfl_edge_inplay_2025 as B25
    from scripts.nfl_edge_lib import games as bt_games

    g = bt_games()
    dk_spread = B._dk_pregame_spread()
    tr_all = B.attach_games(B.play_states(range(2016, 2025)), g)
    out = {}
    for season, tgt in B.PARITY_TARGETS.items():
        coefs, _ = B.fit_block(tgt["train"], g, tr=tr_all[tr_all.season < season])
        art = M.artifact_from_dict(json.loads(json.dumps(
            {"coefficients": {str(L): [float(v) for v in coefs[L - 4]] for L in range(4, 17)},
             "features": {"columns": list(M.COLUMNS)}, "rule": {}, "identity": {}})))
        with redirect_stdout(io.StringIO()):
            d = B24.load_inplay(season, g)
            st, _ = B24.states(season, g)
        snaps = d[["game_id", "snapshot_at"]].drop_duplicates(B24.KEYS)
        ident = st[["game_id", "t_known"] + B._STATE_COLS + B._PLAY_COLS].sort_values("t_known")
        for lag in LAGS:
            with redirect_stdout(io.StringIO()):
                sf = B24.snapshot_frame(d, g, st, lag)
                q = B25.venue_quotes(d, sf)
            xi = snaps.copy()
            xi["t_state"] = (xi.snapshot_at - pd.Timedelta(seconds=lag)).astype("datetime64[ns, UTC]")
            xi = pd.merge_asof(xi.sort_values("t_state"), ident, left_on="t_state",
                               right_on="t_known", by="game_id", direction="backward",
                               allow_exact_matches=True)
            dk = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][
                B24.KEYS + ["price_home", "price_away"]]
            x = sf[~sf.over.astype(bool)].merge(xi[B24.KEYS + B._PLAY_COLS], on=B24.KEYS,
                                                how="left") \
                .merge(dk, on=B24.KEYS).sort_values(B24.KEYS).reset_index(drop=True)
            f = lambda c: x[c].fillna(0).values == 1                       # noqa: E731
            scoring = (f("touchdown") | f("extra_point_attempt") | f("two_point_attempt")
                       | (x.field_goal_result == "made").values | f("safety"))
            sp = x.game_id.map(dk_spread).values
            for floor in FLOORS:
                out[(season, lag, floor)] = first_bets(x, art, sp, ~scoring, floor)

    def row(b):
        n = len(b)
        if n == 0:
            return "  0"
        return (f"{n:3d} {b.pnl.sum():+7.2f}u {100*b.pnl.mean():+5.1f}% | "
                f"{b.pnl_pub.sum():+7.2f}u/{b.risk.sum():5.1f} {100*b.pnl_pub.sum()/b.risk.sum():+5.1f}%")

    for lag in LAGS:
        print(f"\n=== state lag {lag} s: bets, flat units, flat ROI | published-stake units/risked, ROI;"
              f"  then 2024 / 2025 flat units")
        for floor in FLOORS:
            b24, b25 = out[(2024, lag, floor)], out[(2025, lag, floor)]
            b = pd.concat([b24, b25])
            lab = "none" if floor is None else f"{floor:+d}"
            print(f"  floor {lab:>6}: {row(b)}   2024 {b24.pnl.sum():+6.2f}u ({len(b24)})  "
                  f"2025 {b25.pnl.sum():+6.2f}u ({len(b25)})")
    # Price distribution of the population of record (lag 0, no floor)
    b = pd.concat([out[(2024, 0, None)], out[(2025, 0, None)]])
    bins = [-100000, -2000, -1000, -700, -500, -300, -200, 100000]
    labels = ["<= -2000", "-1999..-1000", "-999..-700", "-699..-500", "-499..-300",
              "-299..-200", ">= -199"]
    b["band"] = pd.cut(b.price, bins=bins, labels=labels, right=False)
    print("\n=== population of record (lag 0, no floor) by price band: n, flat units, wins")
    for lab, grp in b.groupby("band", observed=False):
        print(f"  {lab:>13}: {len(grp):3d}  {grp.pnl.sum():+6.2f}u  won {int((grp.v == 1).sum())}"
              f"  lost {int((grp.v == 0).sum())}")
    print(f"  median price {b.price.median():+.0f}; shorter than -900: {(b.price < -900).sum()} of {len(b)}")


if __name__ == "__main__":
    main()
