"""Checks on the market-anchored rebuild before anyone believes it.

1. Blind baselines on the same games at the same best price: always the
   favourite, always the underdog, always home. The anchored model bets mostly
   favourites, and the openers have leaned against favourites before
   (docs/nhl_market_lab.md, round one) -- so its edge has to be measured
   against simply taking the favourite.
2. Without the lineup inputs: they use who actually dressed, which production
   cannot know at noon on game day. Without the goalie workload group too
   (the ablation said it hurts).
3. Inside the anchored model's bets: favourites against underdogs.

    python -m scripts.nhl_moneyline_rebuild_checks
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from scripts.nhl_market_lab import summarise, win_per_unit  # noqa: E402
from scripts.nhl_moneyline_rebuild import (GROUPS, TEST_SEASONS, bet_grid, bets, load,  # noqa: E402
                                           show, walk)

pd.set_option("display.width", 250)


def blind(df: pd.DataFrame, rule: str) -> dict:
    s = df.dropna(subset=["best_home", "best_away", "pin_mkt_home", "pin_close_home"])
    if rule == "favourite":
        home = s.dra_mkt_home >= 0.5
    elif rule == "underdog":
        home = s.dra_mkt_home < 0.5
    else:
        home = pd.Series(True, index=s.index)
    price = np.where(home, s.best_home, s.best_away)
    won = np.where(home, s.hs > s.as_, s.as_ > s.hs)
    profit = np.where(won, [win_per_unit(p) for p in price], -1.0)
    clv = np.where(home, s.pin_close_home - s.pin_mkt_home, s.pin_mkt_home - s.pin_close_home)
    per = {str(k): f"{profit[(s.season == k).values].mean() * 100:+.1f}" for k in sorted(s.season.unique())}
    return {"blind": f"always the {rule}", **summarise(profit, clv), **per}


def main() -> None:
    df = load()
    full = [f for g in GROUPS.values() for f in g]
    anchored = walk(df, full, kind="offset", seasons=TEST_SEASONS[1:], min_season=2021)
    games = df[df.game_id.isin(anchored.game_id)]
    show(f"Blind baselines on the same {len(games):,} games, best bettable price", [
        blind(games, "favourite"), blind(games, "underdog"), blind(games, "home")])

    no_lineup = [f for f in full if f not in GROUPS["lineup"]]
    lean = [f for f in no_lineup if f not in GROUPS["workload"]]
    rows = []
    for name, feats in (("anchored, ALL inputs", full),
                        ("anchored, without lineup", no_lineup),
                        ("anchored, without lineup and goalie workload", lean)):
        pred = anchored if feats is full else walk(df, feats, kind="offset", seasons=TEST_SEASONS[1:],
                                                   min_season=2021)
        pred = pred[pred.game_id.isin(anchored.game_id)]
        rows += [r for r in bet_grid(name, pred, "best") if r["EV>="] in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10)]
    show("The anchored model at the best bettable price, with and without the inputs production "
         "cannot know at noon", rows)

    b = bets(anchored, 0.06, "best")
    fav = np.where(b.side_home, b.dra_mkt_home >= 0.5, b.dra_mkt_home < 0.5)
    show("Anchored, ALL inputs, EV >= 0.06 at the best price: favourites against underdogs", [
        {"bets on": "favourites", **summarise(b.profit.values[fav], b.clv.values[fav])},
        {"bets on": "underdogs", **summarise(b.profit.values[~fav], b.clv.values[~fav])}])


if __name__ == "__main__":
    main()
