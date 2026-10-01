"""nhl_prop_blocked_shots, backtested the way production will run it.

docs/nhl_market_lab.md found blocked-shot unders at DraftKings positive in all
three priced seasons. That table was produced by the lab script; this one runs
the PRODUCTION module (models/nhl_prop_blocked_shots.py) and applies what the
live system applies and the lab did not:

  * the price floor (config.MODEL_MIN_ODDS / the -200 default) -- unders on this
    market are juiced, so a floor removes real bets and has to be in the sweep;
  * the probability correction every model decides on, both ways: the model's
    OWN probability, and the borrowed correction a model with no record gets.

Walk-forward: for each priced season the model is fit only on earlier seasons.
Prices are the bought history (`player_prop_odds`, DraftKings, one pre-game
snapshot a game). One bet per player-game: the side with the better EV.

    python -m scripts.nhl_prop_blocked_shots_backtest
"""
import sys

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import models.nhl_prop_blocked_shots as bs  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.probability_calibration import apply_calibration  # noqa: E402
from scripts.nhl_market_lab import implied, summarise  # noqa: E402

pd.set_option("display.width", 250)
SEASONS = [2024, 2025, 2026]
EV_CUTS = (0.0, 0.03, 0.06, 0.08, 0.10, 0.12, 0.15)
FLOORS = (None, -250, -200, -170, -140)
BORROWED = {"method": "platt", "a": 1.0, "b": -0.259947}     # what a no-record model is given
COHERENT_SUM = (1.00, 1.15)


def prices(conn, season: int) -> pd.DataFrame:
    ids = [r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NHL' AND season = %s", (season,)).fetchall()]
    rows = []
    for i in range(0, len(ids), 300):
        rows += conn.execute(
            "SELECT game_id, player_name, line, over_price, under_price FROM player_prop_odds "
            "WHERE game_id = ANY(%s) AND market = %s AND bookmaker = %s AND snapshot_type = 'open'",
            (ids[i:i + 300], bs.MARKET, bs.BOOK)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "player", "line", "over", "under"])
    for c in ("line", "over", "under"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px["pkey"] = px.player.map(bs.name_key)
    two = px.over.notna() & px.under.notna()
    total = px.over.map(implied, na_action="ignore") + px.under.map(implied, na_action="ignore")
    return px[~(two & ~total.between(*COHERENT_SUM))].drop_duplicates(["game_id", "pkey", "line"])


def bets(frame: pd.DataFrame, conn) -> pd.DataFrame:
    """Every priced side of every priced player-game, with the model's probability."""
    parts = []
    for season in SEASONS:
        model, n_train = bs.fit(frame, season - 1)
        te = bs.usable(frame[(frame.season == season) & ~frame.upcoming]).dropna(subset=[bs.STAT]).copy()
        te["mu"] = bs.predict_mean(model, te)
        px = prices(conn, season)
        m = px.merge(te[["game_id", "pkey", "game_date", "mu", bs.STAT]], on=["game_id", "pkey"], how="inner")
        print(f"{season - 1}-{str(season)[2:]}: fit on {n_train:,} skater-games; DraftKings priced "
              f"{len(px):,} player-games, {len(m):,} matched to a prediction")
        m["season"] = season
        parts.append(m)
    df = pd.concat(parts, ignore_index=True)
    po = bs.p_over(df.mu.values, df.line.values)
    out = []
    for side, col, p in (("over", "over", po), ("under", "under", 1 - po)):
        s = df[df[col].notna()].copy()
        s["side"], s["price"], s["p"] = side, s[col], p[df[col].notna().values]
        won = (s[bs.STAT] > s.line) if side == "over" else (s[bs.STAT] < s.line)
        s["profit"] = np.where(s[bs.STAT] == s.line, 0.0, np.where(won, s.price.map(bs.win_per_unit), -1.0))
        out.append(s)
    s = pd.concat(out, ignore_index=True)
    s["p_borrowed"] = s.p.map(lambda v: apply_calibration(float(v), BORROWED))
    s["ev"] = s.p * (1 + s.price.map(bs.win_per_unit)) - 1
    s["ev_borrowed"] = s.p_borrowed * (1 + s.price.map(bs.win_per_unit)) - 1
    return s


def card(s: pd.DataFrame, ev_col: str, cut: float, floor: float | None) -> pd.DataFrame:
    b = s[s[ev_col] >= cut]
    if floor is not None:
        b = b[b.price >= floor]
    return (b.sort_values(ev_col, ascending=False).drop_duplicates(["game_id", "pkey"])
            .sort_values(["game_date", "game_id", "pkey"]))


def line(label: dict, b: pd.DataFrame) -> dict:
    if len(b) < 30:
        return {**label, "bets": len(b)}
    p = b.profit.values
    half = len(b) // 2
    r = {**label, **summarise(p), "early": round(float(p[:half].mean()) * 100, 1),
         "late": round(float(p[half:].mean()) * 100, 1),
         "unders": round(float((b.side == "under").mean()), 2),
         "win%": round(float((p > 0).mean()) * 100, 1), "median price": int(b.price.median())}
    for season in SEASONS:
        m = (b.season == season).values
        r[f"{season - 1}-{str(season)[2:]}"] = (f"{p[m].mean() * 100:+.1f}% ({int(m.sum())})"
                                                if m.sum() >= 30 else f"({int(m.sum())})")
    return r


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    conn = get_connection()
    try:
        frame = bs.build_frame(bs.load_skaters(conn), bs.load_teams(conn))
        s = bets(frame, conn)
    finally:
        conn.close()
    u = s[s.side == "under"]
    print(f"\n{s.groupby(['game_id', 'pkey']).ngroups:,} priced player-games; under prices: median "
          f"{int(u.price.median())}, shorter than -200: {float((u.price < -200).mean()) * 100:.1f}%, "
          f"shorter than -140: {float((u.price < -140).mean()) * 100:.1f}%; lines: "
          f"{s.drop_duplicates(['game_id', 'pkey']).line.value_counts().to_dict()}")
    for side in ("over", "under"):
        q = s[s.side == side]
        print(f"blind always {side}: {summarise(q.profit.values)}")

    show("The model's OWN probability, no price floor (the lab's rule)",
         [line({"EV>=": c}, card(s, "ev", c, None)) for c in EV_CUTS])
    show("The model's OWN probability, by price floor",
         [line({"EV>=": c, "floor": f} , card(s, "ev", c, f)) for c in (0.03, 0.06, 0.10) for f in FLOORS])
    show("The BORROWED correction applied (what a model with no record is given), floor -200",
         [line({"EV>=": c}, card(s, "ev_borrowed", c, -200)) for c in EV_CUTS])

    # is the probability honest where it is bet?
    b = card(s, "ev", 0.06, -200)
    b = b[b.side == "under"]
    rows = []
    for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)):
        q = b[(b.p >= lo) & (b.p < hi)]
        if len(q) >= 30:
            rows.append({"model says under": f"{lo:.1f}-{min(hi, 1.0):.1f}", "bets": len(q),
                         "claimed": round(float(q.p.mean()), 3),
                         "borrowed correction says": round(float(q.p_borrowed.mean()), 3),
                         "happened": round(float((q[bs.STAT] < q.line).mean()), 3)})
    show("Claimed against realised, the unders bet at EV >= 0.06 with the -200 floor", rows)

    per_day = b.groupby("game_date").size()
    print(f"\nat EV >= 0.06, floor -200: {len(b):,} under bets over {s.game_date.nunique():,} priced game days "
          f"({len(b) / max(s.game_date.nunique(), 1):.1f} a day; most on one day {int(per_day.max())})")


if __name__ == "__main__":
    main()
