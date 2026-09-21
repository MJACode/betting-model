"""NHL props, graded in units against real prices.

scripts/nhl_prop_lab.py showed the log-built prop models beat the free
projections; this asks the question that pays: do they beat the BOOK?

PRICES. data/ingestors/nhl_prop_odds_history.py — one pre-game snapshot per
game (an hour before the day's first puck drop), ten books, DraftKings and
Pinnacle among them. One snapshot means NO closing-line value here.

DESIGN. Train every model on seasons before the test season; predict a Poisson
mean per player-game; for each priced (player, game, market, book) compute the
model's probability of each side AT THAT BOOK'S LINE and its expected value at
that book's price. Bet one unit when EV >= the cut. Three things are reported
per market, at DraftKings and at the best price among the bettable books:

    MODEL          bet when the model's EV clears the cut
    SHARP-VS-SOFT  no model: bet when Pinnacle's no-vig probability at the SAME
                   line gives the soft price EV >= the cut (the construction
                   behind nfl_prop_market)
    BLIND          always over / always under at DraftKings — the floor

Units, ROI, 95% interval, early / late halves, and the cut as a neighbourhood.

    python -m scripts.nhl_prop_lab_priced --season 2026
"""
from __future__ import annotations

import argparse
import sys
import unicodedata

import numpy as np
import pandas as pd
from scipy.stats import poisson
from xgboost import XGBRegressor

sys.path.insert(0, ".")

import config
from data.db import get_connection
from scripts.nhl_market_lab import implied, summarise, win_per_unit
from scripts.nhl_prop_lab import PARAMS, _ew, opponent_allowed, skaters

EV_CUTS = (0.03, 0.06, 0.10, 0.15)
COMMON = ["toi_l", "toi_s", "pp_toi_l", "pp_toi_s", "is_home", "rest", "is_d", "gp"]
SPEC = {
    "player_shots_on_goal": ("shots", ["shots_l", "shots_s", "shot_attempts_l", "shot_attempts_s", "opp_sa"]),
    "player_points": ("points", ["points_l", "points_s", "shots_l", "goals_l", "assists_l", "opp_ga", "opp_pk_opps"]),
    "player_assists": ("assists", ["assists_l", "assists_s", "points_l", "opp_ga", "opp_pk_opps"]),
    "player_goal_scorer_anytime": ("goals", ["goals_l", "goals_s", "shots_l", "shots_s", "opp_ga", "opp_sa"]),
    "player_blocked_shots": ("blocked_shots", ["blocked_shots_l", "blocked_shots_s", "opp_sf"]),
}
BETTABLE = [b for b in config.BEST_LINE_BOOKMAKERS]


def fold(name: str) -> str:
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(c for c in flat.lower() if c.isalpha())


def load_prices(conn, season: int) -> pd.DataFrame:
    # By game id, in chunks: the table is indexed on (game_id, market, ...) and a
    # join or a LIKE scans hundreds of millions of rows into the statement timeout.
    ids = [r[0] for r in conn.execute(
        "SELECT game_id FROM games WHERE sport = 'NHL' AND season = ?", (season,)).fetchall()]
    rows = []
    for i in range(0, len(ids), 300):
        rows += conn.execute(
            "SELECT game_id, player_name, market, bookmaker, line, over_price, under_price "
            "FROM player_prop_odds WHERE game_id = ANY(%s) AND snapshot_type = 'open'",
            (ids[i:i + 300],)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "player", "market", "book", "line", "over", "under"])
    for c in ("line", "over", "under"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px["pkey"] = px.player.map(fold)
    return px


def predictions(conn, season: int) -> pd.DataFrame:
    """One row per (game_id, player, market): the model's Poisson mean and the actual."""
    d = skaters(conn).merge(opponent_allowed(conn), on=["nhl_game_id", "opponent"], how="left")
    names = pd.DataFrame(conn.execute(
        "SELECT DISTINCT ON (player_id) player_id, player_name FROM nhl_skater_game_log "
        "ORDER BY player_id, game_date DESC").fetchall(), columns=["player_id", "player_name"])
    gid = pd.DataFrame(conn.execute(
        "SELECT DISTINCT nhl_game_id, game_id, game_date FROM nhl_team_game_log").fetchall(),
        columns=["nhl_game_id", "game_id", "gdate"])
    d = d.merge(names, on="player_id").merge(gid, on="nhl_game_id")
    d = d[d.gp >= 10]
    out = []
    for market, (stat, feats) in SPEC.items():
        feats = feats + COMMON
        use = d.dropna(subset=feats + [stat])
        tr, te = use[use.season.between(2020, season - 1)], use[use.season == season]
        m = XGBRegressor(**PARAMS).fit(tr[feats].values.astype(float), tr[stat].values.astype(float))
        out.append(pd.DataFrame({
            "game_id": te.game_id.values, "gdate": te.gdate.values, "market": market,
            "pkey": te.player_name.map(fold).values, "actual": te[stat].values,
            "mu": np.clip(m.predict(te[feats].values.astype(float)), 1e-3, None)}))
    # goalie saves: full starts only, and the bet is void if he does not start
    gcols = ["nhl_game_id", "player_id", "player_name", "team", "opponent", "season", "game_date",
             "started", "saves", "shots_against", "toi_seconds"]
    g = pd.DataFrame(conn.execute(f"SELECT {', '.join(gcols)} FROM nhl_goalie_game_log "
                                  f"WHERE game_type = 2").fetchall(), columns=gcols)
    g = g.sort_values(["player_id", "game_date", "nhl_game_id"])
    for c in ("saves", "shots_against", "toi_seconds"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[g.started == 1]
    gg = g.groupby("player_id", sort=False)
    g["saves_l"], g["saves_s"], g["sa_l"] = _ew(gg, "saves", 25), _ew(gg, "saves", 5), _ew(gg, "shots_against", 25)
    g["gp"] = gg.cumcount()
    opp = opponent_allowed(conn)
    g = g.merge(opp[["nhl_game_id", "opponent", "opp_sf"]], on=["nhl_game_id", "opponent"], how="left")
    own = opp.rename(columns={"opponent": "team", "opp_sa": "own_sa"})[["nhl_game_id", "team", "own_sa"]]
    g = g.merge(own, on=["nhl_game_id", "team"], how="left").merge(gid, on="nhl_game_id")
    feats = ["saves_l", "saves_s", "sa_l", "opp_sf", "own_sa", "gp"]
    use = g[g.gp >= 10].dropna(subset=feats + ["saves"])
    tr, te = use[use.season.between(2020, season - 1)], use[use.season == season]
    m = XGBRegressor(**PARAMS).fit(tr[feats].values.astype(float), tr["saves"].values.astype(float))
    out.append(pd.DataFrame({
        "game_id": te.game_id.values, "gdate": te.gdate.values, "market": "player_total_saves",
        "pkey": te.player_name.map(fold).values, "actual": te["saves"].values,
        "mu": np.clip(m.predict(te[feats].values.astype(float)), 1e-3, None)}))
    return pd.concat(out)


def sides(df: pd.DataFrame, p_over: np.ndarray) -> pd.DataFrame:
    """Expand to one row per bettable SIDE with its price, model prob, EV and result."""
    rows = []
    for side, price_col, p in (("over", "over", p_over), ("under", "under", 1 - p_over)):
        s = df[df[price_col].notna()].copy()
        pr = p[df[price_col].notna().values]
        s["side"], s["price"], s["p"] = side, s[price_col], pr
        s["ev"] = s.p * (1 + s.price.map(win_per_unit)) - 1
        won = (s.actual > s.line) if side == "over" else (s.actual < s.line)
        s["profit"] = np.where(s.actual == s.line, 0.0, np.where(won, s.price.map(win_per_unit), -1.0))
        rows.append(s)
    return pd.concat(rows)


def table(name: str, s: pd.DataFrame, cuts=EV_CUTS) -> list[dict]:
    out = []
    for c in cuts:
        b = s[s.ev >= c].sort_values("gdate")
        # one bet per player-game-market: the best EV on offer
        b = b.sort_values("ev", ascending=False).drop_duplicates(["game_id", "pkey", "market"]).sort_values("gdate")
        if len(b) < 30:
            out.append({"rule": name, "EV>=": c, "bets": len(b)})
            continue
        half = len(b) // 2
        out.append({"rule": name, "EV>=": c, **summarise(b.profit.values),
                    "over share": round(float((b.side == "over").mean()), 2),
                    "early": round(float(b.profit.values[:half].mean()) * 100, 1),
                    "late": round(float(b.profit.values[half:].mean()) * 100, 1)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2026)
    a = ap.parse_args()
    conn = get_connection()
    try:
        px, pred = load_prices(conn, a.season), predictions(conn, a.season)
    finally:
        conn.close()
    df = px.merge(pred, on=["game_id", "pkey", "market"], how="inner")
    print(f"priced rows {len(px):,}; matched to a model prediction {len(df):,} "
          f"({df.groupby(['game_id', 'pkey', 'market']).ngroups:,} player-game-markets, "
          f"{df.game_id.nunique():,} games)")
    k = np.floor(df.line.values)
    df["p_over"] = poisson.sf(k, df.mu.values)
    # Pinnacle's no-vig probability at the SAME line
    pin = df[(df.book == "pinnacle") & df.over.notna() & df.under.notna()].copy()
    pin["pin_over"] = [implied(o) / (implied(o) + implied(u)) for o, u in zip(pin.over, pin.under)]
    df = df.merge(pin[["game_id", "pkey", "market", "line", "pin_over"]],
                  on=["game_id", "pkey", "market", "line"], how="left")
    pd.set_option("display.width", 220)
    for market in list(SPEC) + ["player_total_saves"]:
        m = df[df.market == market]
        if m.empty:
            continue
        dk = m[m.book == "draftkings"]
        soft = m[m.book.isin(BETTABLE)]
        rows = []
        rows += table("MODEL @ DraftKings", sides(dk, dk.p_over.values))
        rows += table("MODEL @ best bettable book", sides(soft, soft.p_over.values))
        sp = soft[soft.pin_over.notna()]
        rows += table("SHARP-VS-SOFT (Pinnacle no-vig) @ best bettable", sides(sp, sp.pin_over.values))
        both = sp.copy()
        agree = sides(both, both.p_over.values).rename(columns={"ev": "ev_model"})
        agree["ev_pin"] = sides(both, both.pin_over.values)["ev"].values
        agree["ev"] = np.minimum(agree.ev_model, agree.ev_pin)          # BOTH must clear the cut
        rows += table("MODEL AND Pinnacle agree @ best bettable", agree)
        bl = sides(dk, dk.p_over.values)
        for side in ("over", "under"):
            s = bl[bl.side == side]
            rows.append({"rule": f"BLIND always {side} @ DraftKings", "EV>=": None, **summarise(s.profit.values)})
        print(f"\n### {market}  ({m.groupby(['game_id', 'pkey']).ngroups:,} player-games priced; "
              f"DraftKings {len(dk):,} rows; Pinnacle same-line {int(m.pin_over.notna().sum()):,})\n")
        print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
