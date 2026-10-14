"""The production module's own walk-forward: models/nhl_moneyline_anchored.py.

Before the module may score a game it must reproduce the grade it goes live
on (docs/nhl_moneyline_rebuild.md, "anchored, without lineup"): the same
inputs, the same fit, the same probabilities, game by game, as the research
harness (scripts/nhl_moneyline_rebuild.py) -- and then the same bets.

Also reported: the production price floor (config.min_odds_for -- the research
grade had none), so the number the model goes live on is the number with it.

    python -m scripts.nhl_moneyline_anchored_backtest
"""
from __future__ import annotations

import os
import pickle
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

import config  # noqa: E402
import models.nhl_moneyline_anchored as m  # noqa: E402
from data.db import get_connection  # noqa: E402
from scripts.nhl_market_lab import summarise, win_per_unit  # noqa: E402
from scripts.nhl_market_lab3 import _nv, feed_prices  # noqa: E402
from scripts.nhl_moneyline_rebuild import (CACHE, GROUPS as RESEARCH_GROUPS,  # noqa: E402
                                           PRICED_SEASONS, TEST_SEASONS, _cached, _db_quiet,
                                           best_prices, bet_grid, bets, show)

pd.set_option("display.width", 250)


def module_frame() -> pd.DataFrame:
    def _logs():
        conn = get_connection()
        try:
            _db_quiet(conn, "game logs (module)")
            return m.load_logs(conn)
        finally:
            conn.close()

    def _px():
        conn = get_connection()
        try:
            _db_quiet(conn, "prices")
            return feed_prices(conn, PRICED_SEASONS)
        finally:
            conn.close()

    def _best():
        conn = get_connection()
        try:
            _db_quiet(conn, "best prices")
            return best_prices(conn, PRICED_SEASONS)
        finally:
            conn.close()

    logs = _cached("module_logs_v1", _logs)
    inputs_cache = os.path.join(CACHE, "inputs_v1.pkl")
    if os.path.exists(inputs_cache):                    # the research run's own price read
        with open(inputs_cache, "rb") as fh:
            px = pickle.load(fh)[4]
    else:
        px = _cached("prices_v1", _px)
    df = m.build_inputs(logs)
    df = df.merge(px, on="game_id", how="left").merge(_cached("best_prices_v1", _best), on="game_id", how="left")
    df["y"] = (df.hs > df.as_).astype(int)
    for b in ("dra", "pin"):
        df[f"{b}_mkt_home"] = _nv(df, f"{b}_ml_home_open", f"{b}_ml_away_open")
    df["pin_close_home"] = _nv(df, "pin_ml_home_close", "pin_ml_away_close")
    df["mkt_logit"] = np.log(df.dra_mkt_home / (1 - df.dra_mkt_home))
    return df


def walk(df: pd.DataFrame, seasons=TEST_SEASONS[1:]) -> pd.DataFrame:
    use = df[df.season >= m.FIRST_PRICED_SEASON].dropna(subset=m.FEATURES + ["mkt_logit", "y"])
    parts = []
    for test in seasons:
        tr, te = use[use.season < test], use[use.season == test].copy()
        if len(tr) < 800 or te.empty:
            continue
        model, C = m.fit(tr)
        te["C"] = C
        te["p"] = model.predict_proba(te[m.FEATURES].values, te.mkt_logit.values)[:, 1]
        parts.append(te)
    return pd.concat(parts)


def floored(pred: pd.DataFrame, floor: float) -> list[dict]:
    """The best-price grid with the production price floor applied."""
    rows = []
    for c in (0.02, 0.04, 0.06, 0.08):
        b = bets(pred, c, "best")
        kept = b[b.price >= floor]
        rows.append({"EV>=": c, "bets before floor": len(b), "removed by floor": len(b) - len(kept),
                     **summarise(kept.profit.values, kept.clv.values)})
    return rows


def serve_parity(n_dates: int = 40) -> None:
    """Score past games the way production scores tonight's: logs cut to the
    morning of the game date, the game passed in as UPCOMING with the goalie
    who started it as the listed one. Every input must equal the training
    frame's row for that game."""
    logs = _cached("module_logs_v1", lambda: None)
    train = m.build_inputs(logs)
    played = train[train.season == 2026]
    dates = sorted(played.game_date.unique())
    rng = np.random.default_rng(7)
    pick = sorted(rng.choice(dates, size=min(n_dates, len(dates)), replace=False))
    gl = logs["goalie"]
    starters = gl[pd.to_numeric(gl.started) == 1][["game_id", "team", "player_id"]]
    n_vals, bad = 0, []
    for d in pick:
        cut = {k: v[v.game_date.astype(str).str[:10] < d] for k, v in logs.items()}
        today = played[played.game_date == d][["game_id", "game_date", "season", "home", "away"]].copy()
        st = starters[starters.game_id.isin(today.game_id)]
        today = today.merge(st.rename(columns={"team": "home", "player_id": "home_goalie_id"}),
                            on=["game_id", "home"], how="left")
        today = today.merge(st.rename(columns={"team": "away", "player_id": "away_goalie_id"}),
                            on=["game_id", "away"], how="left")
        served = m.build_inputs(cut, upcoming=today)
        served = served[served.game_id.isin(today.game_id)].set_index("game_id")
        ref = played[played.game_id.isin(today.game_id)].set_index("game_id")
        for gid in ref.index:
            for f in m.FEATURES:
                a, b = served.at[gid, f], ref.at[gid, f]
                n_vals += 1
                if not ((pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) < 1e-9):
                    bad.append((d, gid, f, a, b))
    print(f"\nserve-vs-train parity: {len(pick)} dates of 2025-26, {n_vals:,} values, "
          f"{len(bad)} disagreements")
    for row in bad[:20]:
        print("   ", row)


def main() -> None:
    if "--parity" in sys.argv:
        serve_parity()
        return
    df = module_frame()
    mod = walk(df)
    print(f"module walk-forward: {len(mod):,} games, C by season "
          f"{mod.groupby('season').C.first().to_dict()}")

    # parity with the research harness, game by game
    from scripts.nhl_moneyline_rebuild import load as research_load, walk as research_walk
    rdf = research_load()
    no_lineup = [f for g, cols in RESEARCH_GROUPS.items() if g != "lineup" for f in cols]
    assert no_lineup == m.FEATURES, "the module's input list is not the graded one"
    res = research_walk(rdf, no_lineup, kind="offset", seasons=TEST_SEASONS[1:], min_season=2021)
    both = mod[["game_id", "p"] + m.FEATURES].merge(
        res[["game_id", "p"] + m.FEATURES], on="game_id", suffixes=("_mod", "_res"))
    print(f"\nparity: {len(both):,} games in both (module {len(mod):,}, research {len(res):,})")
    print(f"  max |p_module - p_research| = {np.abs(both.p_mod - both.p_res).max():.2e}")
    worst = {f: float(np.nanmax(np.abs(both[f'{f}_mod'] - both[f'{f}_res']))) for f in m.FEATURES}
    off = {f: v for f, v in worst.items() if v > 1e-9}
    print(f"  inputs that differ anywhere (max |diff|): {off if off else 'none'}")

    # the research grade was taken on the games every research run scored
    allin = [f for cols in RESEARCH_GROUPS.values() for f in cols]
    graded = set(rdf.dropna(subset=allin + ['mkt_logit', 'y']).game_id)
    show("Module, best bettable price, on the graded games (should equal the research grade)",
         [r for r in bet_grid("module", mod[mod.game_id.isin(graded)], "best")])
    show("Module, best bettable price, every game it can score", bet_grid("module", mod, "best"))
    floor = config.min_odds_for(m.MODEL_ID)
    show(f"With the production price floor ({floor:+.0f})", floored(mod, floor))


if __name__ == "__main__":
    main()
