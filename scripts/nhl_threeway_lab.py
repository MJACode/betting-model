"""NHL regulation 3-way line (home / draw / away after 60 minutes), in units.

PRICES. Bought with the prop history (data/ingestors/nhl_prop_odds_history.py):
one pre-game snapshot per game, stored in `odds` as market `h2h_3way`. One
snapshot, so no closing-line value.

THREE RULES, each at DraftKings and at the best price among the bettable books:

    MODEL          a regularised 3-class logistic model on the round-two inputs
                   (scripts/nhl_market_lab2.py), trained on seasons before the
                   test season; bet an outcome when model EV >= the cut
    SHARP-VS-SOFT  no model: Pinnacle's no-vig 3-way probability against the
                   soft book's price
    BLIND          always home / always draw / always away at DraftKings

    python -m scripts.nhl_threeway_lab --season 2026
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, ".")

import config
from data.db import get_connection
from data.ingestors.nhl_prop_odds_history import SOURCE
from scripts.nhl_market_lab import implied, summarise, win_per_unit
from scripts.nhl_market_lab2 import GROUPS, build

EV_CUTS = (0.02, 0.04, 0.06, 0.10)
OUTCOMES = ("away", "draw", "home")            # classes 0 / 1 / 2, the repo's encoding
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)


def prices(conn, season: int) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT o.game_id, o.bookmaker, o.home_price, o.away_price, o.draw_price,
               g.game_date, g.home_score, g.away_score, g.went_to_ot
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE o.source = ? AND o.market = 'h2h_3way' AND g.season = ?
    """, (SOURCE, season)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "home", "away", "draw", "gdate",
                                     "hs", "as_", "ot"])
    for c in ("home", "away", "draw", "hs", "as_", "ot"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.dropna(subset=["home", "away", "draw"]).drop_duplicates(["game_id", "book"], keep="last")
    px["result"] = np.where(px.ot == 1, "draw", np.where(px.hs > px.as_, "home", "away"))
    return px


def long(px: pd.DataFrame, probs: dict[str, str]) -> pd.DataFrame:
    """One row per (game, book, outcome) with its price, the rule's probability, EV, profit."""
    parts = []
    for o in OUTCOMES:
        s = px.dropna(subset=[probs[o]]).copy()
        s["outcome"], s["price"], s["p"] = o, s[o], s[probs[o]]
        s["ev"] = s.p * (1 + s.price.map(win_per_unit)) - 1
        s["profit"] = np.where(s.result == o, s.price.map(win_per_unit), -1.0)
        parts.append(s)
    return pd.concat(parts)


def table(name: str, s: pd.DataFrame) -> list[dict]:
    out = []
    for c in EV_CUTS:
        b = (s[s.ev >= c].sort_values("ev", ascending=False)
             .drop_duplicates(["game_id"]).sort_values("gdate"))       # one bet per game
        if len(b) < 30:
            out.append({"rule": name, "EV>=": c, "bets": len(b)})
            continue
        half = len(b) // 2
        mix = b.outcome.value_counts(normalize=True).round(2).to_dict()
        out.append({"rule": name, "EV>=": c, **summarise(b.profit.values),
                    "early": round(float(b.profit.values[:half].mean()) * 100, 1),
                    "late": round(float(b.profit.values[half:].mean()) * 100, 1),
                    "home/draw/away": f"{mix.get('home', 0)}/{mix.get('draw', 0)}/{mix.get('away', 0)}"})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    a = ap.parse_args()
    conn = get_connection()
    try:
        df, px = build(conn, with_prices=False), prices(conn, a.season)
        ot = dict(conn.execute("SELECT game_id, went_to_ot FROM games WHERE sport='NHL' "
                               "AND home_score IS NOT NULL").fetchall())
    finally:
        conn.close()
    feats = [f for g in GROUPS.values() for f in g]
    df["y3"] = np.where(df.game_id.map(ot) == 1, 1, np.where(df.hs > df.as_, 2, 0))
    use = df.dropna(subset=feats)
    tr, te = use[use.season.between(2019, a.season - 1)], use[use.season == a.season]
    m = make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=3000))
    m.fit(tr[feats].values.astype(float), tr.y3.values)
    P = m.predict_proba(te[feats].values.astype(float))
    pred = pd.DataFrame({"game_id": te.game_id.values, "m_away": P[:, 0], "m_draw": P[:, 1],
                         "m_home": P[:, 2]})
    print(f"3-way prices: {len(px):,} rows, {px.game_id.nunique():,} games, books "
          f"{sorted(px.book.unique())}; draws {float((px.drop_duplicates('game_id').result == 'draw').mean()):.3f}; "
          f"model's mean draw probability {P[:, 1].mean():.3f}")
    px = px.merge(pred, on="game_id", how="left")
    pin = px[px.book == "pinnacle"].copy()
    tot = pin.home.map(implied) + pin.draw.map(implied) + pin.away.map(implied)
    for o in OUTCOMES:
        pin[f"pin_{o}"] = pin[o].map(implied) / tot
    px = px.merge(pin[["game_id", "pin_home", "pin_draw", "pin_away"]], on="game_id", how="left")
    print(f"Pinnacle's 3-way hold on these games: {float((tot - 1).mean()) * 100:.2f}%; "
          f"DraftKings': {float((px[px.book == 'draftkings'][['home', 'draw', 'away']].map(implied).sum(axis=1) - 1).mean()) * 100:.2f}%")
    dk, soft = px[px.book == "draftkings"], px[px.book.isin(BETTABLE)]
    model_p = {o: f"m_{o}" for o in OUTCOMES}
    pin_p = {o: f"pin_{o}" for o in OUTCOMES}
    rows = []
    rows += table("MODEL @ DraftKings", long(dk, model_p))
    rows += table("MODEL @ best bettable book", long(soft, model_p))
    rows += table("SHARP-VS-SOFT (Pinnacle no-vig) @ DraftKings", long(dk, pin_p))
    rows += table("SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable", long(soft, pin_p))
    bl = long(dk, model_p)
    for o in OUTCOMES:
        s = bl[bl.outcome == o]
        rows.append({"rule": f"BLIND always {o} @ DraftKings", **summarise(s.profit.values)})
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
