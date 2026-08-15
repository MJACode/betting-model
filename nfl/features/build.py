"""
Feature matrix for the line-movement model.

Target: Pinnacle spread movement from bet time (Tue 18:00 UTC) to close.
    spread_move = cl_spread - bt_spread     (nflverse orientation)
A positive value means the market moved toward the home team after we bet.

Leakage discipline:
  * Every team-form feature is a shift(1) rolling/expanding aggregate, so the
    current game never enters its own features.
  * Every market feature is measured at the bet-time snapshot only. The
    closing line appears solely in the target and in CLV accounting.
  * Weather is excluded. nflverse temp/wind are observed conditions, not the
    Tuesday forecast, so including them would leak.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

SEASONS = [2020, 2021, 2022, 2023, 2024, 2025]

PBP_COLS = [
    "game_id", "season", "week", "posteam", "defteam", "play_type", "epa",
    "yards_gained", "pass", "rush", "success", "interception", "fumble_lost",
    "shotgun", "no_huddle", "penalty", "wp",
]


# ---------------------------------------------------------------- team form
def team_game_stats() -> pd.DataFrame:
    frames = []
    for s in SEASONS:
        d = pd.read_parquet(f"data/raw/pbp_{s}.parquet", columns=PBP_COLS)
        d = d[d.play_type.isin(["pass", "run"]) & d.epa.notna()]
        frames.append(d)
    p = pd.concat(frames, ignore_index=True)

    p["is_pass"] = (p.play_type == "pass").astype(float)
    p["explosive"] = (p.yards_gained >= 20).astype(float)
    p["neutral"] = p.wp.between(0.20, 0.80).astype(float)

    off = p.groupby(["posteam", "game_id", "season", "week"], as_index=False).agg(
        off_epa=("epa", "mean"),
        off_sr=("success", "mean"),
        off_explosive=("explosive", "mean"),
        off_pass_rate=("is_pass", "mean"),
        off_plays=("epa", "size"),
        off_shotgun=("shotgun", "mean"),
        off_nohuddle=("no_huddle", "mean"),
    ).rename(columns={"posteam": "team"})

    # phase splits
    ps = p[p.play_type == "pass"].groupby(["posteam", "game_id"], as_index=False).agg(
        off_epa_pass=("epa", "mean")).rename(columns={"posteam": "team"})
    rs = p[p.play_type == "run"].groupby(["posteam", "game_id"], as_index=False).agg(
        off_epa_run=("epa", "mean")).rename(columns={"posteam": "team"})
    npr = p[p.neutral == 1].groupby(["posteam", "game_id"], as_index=False).agg(
        off_neutral_pass_rate=("is_pass", "mean")).rename(columns={"posteam": "team"})
    off = off.merge(ps, on=["team", "game_id"], how="left") \
             .merge(rs, on=["team", "game_id"], how="left") \
             .merge(npr, on=["team", "game_id"], how="left")

    dfn = p.groupby(["defteam", "game_id", "season", "week"], as_index=False).agg(
        def_epa=("epa", "mean"),
        def_sr=("success", "mean"),
        def_explosive=("explosive", "mean"),
        def_takeaway=("interception", "sum"),
    ).rename(columns={"defteam": "team"})
    dfn["def_takeaway"] = dfn.def_takeaway.astype(float)

    dps = p[p.play_type == "pass"].groupby(["defteam", "game_id"], as_index=False).agg(
        def_epa_pass=("epa", "mean")).rename(columns={"defteam": "team"})
    drs = p[p.play_type == "run"].groupby(["defteam", "game_id"], as_index=False).agg(
        def_epa_run=("epa", "mean")).rename(columns={"defteam": "team"})
    dfn = dfn.merge(dps, on=["team", "game_id"], how="left") \
             .merge(drs, on=["team", "game_id"], how="left")

    tg = off.merge(dfn, on=["team", "game_id", "season", "week"], how="outer")
    return tg.sort_values(["team", "season", "week"]).reset_index(drop=True)


ROLL_COLS = [
    "off_epa", "off_sr", "off_explosive", "off_pass_rate", "off_plays",
    "off_epa_pass", "off_epa_run", "off_neutral_pass_rate", "off_shotgun",
    "off_nohuddle", "def_epa", "def_sr", "def_explosive", "def_epa_pass",
    "def_epa_run", "def_takeaway",
]


def add_form(tg: pd.DataFrame) -> pd.DataFrame:
    """shift(1) rolling-4 and season-to-date. Current game never included."""
    g_team = tg.groupby("team", sort=False)
    g_ts = tg.groupby(["team", "season"], sort=False)
    out = {}
    for c in ROLL_COLS:
        out[f"{c}_r4"] = g_team[c].transform(
            lambda s: s.shift(1).rolling(4, min_periods=2).mean())
        out[f"{c}_szn"] = g_ts[c].transform(
            lambda s: s.shift(1).expanding(min_periods=1).mean())
    # volatility of recent form: a noisy team is one the market re-prices
    out["off_epa_r4_sd"] = g_team["off_epa"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=3).std())
    out["def_epa_r4_sd"] = g_team["def_epa"].transform(
        lambda s: s.shift(1).rolling(4, min_periods=3).std())
    return pd.concat([tg, pd.DataFrame(out, index=tg.index)], axis=1)


FORM_COLS = [f"{c}_r4" for c in ROLL_COLS] + [f"{c}_szn" for c in ROLL_COLS] + \
            ["off_epa_r4_sd", "def_epa_r4_sd"]


# ------------------------------------------------------------ market layer
def market_features(odds: pd.DataFrame) -> pd.DataFrame:
    """Cross-book microstructure measured at the bet-time snapshot."""
    bt = odds.dropna(subset=["bt_spread"])
    agg = bt.groupby("game_id", as_index=False).agg(
        mkt_n_books=("bt_spread", "size"),
        mkt_spread_mean=("bt_spread", "mean"),
        mkt_spread_sd=("bt_spread", "std"),
        mkt_spread_min=("bt_spread", "min"),
        mkt_spread_max=("bt_spread", "max"),
    )
    agg["mkt_spread_range"] = agg.mkt_spread_max - agg.mkt_spread_min

    btt = odds.dropna(subset=["bt_total"])
    aggt = btt.groupby("game_id", as_index=False).agg(
        mkt_total_mean=("bt_total", "mean"),
        mkt_total_sd=("bt_total", "std"),
    )

    pin = odds[odds.book == "pinnacle"][["game_id", "bt_spread", "bt_total",
                                          "bt_spread_px_home", "bt_spread_px_away"]]
    pin = pin.rename(columns={
        "bt_spread": "pin_bt_spread", "bt_total": "pin_bt_total",
        "bt_spread_px_home": "pin_px_home", "bt_spread_px_away": "pin_px_away"})
    dk = odds[odds.book == "draftkings"][["game_id", "bt_spread", "bt_total"]].rename(
        columns={"bt_spread": "dk_bt_spread", "bt_total": "dk_bt_total"})

    m = agg.merge(aggt, on="game_id", how="outer").merge(
        pin, on="game_id", how="outer").merge(dk, on="game_id", how="outer")

    # deviation of the sharp book from the consensus: the market's own
    # disagreement is the single best prior on which way it will resolve
    m["pin_vs_consensus"] = m.pin_bt_spread - m.mkt_spread_mean
    m["dk_vs_pin"] = m.dk_bt_spread - m.pin_bt_spread
    m["pin_total_vs_consensus"] = m.pin_bt_total - m.mkt_total_mean
    # price asymmetry: juice skew signals which side the book wants
    m["pin_px_skew"] = m.pin_px_home - m.pin_px_away
    m["abs_spread"] = m.pin_bt_spread.abs()
    m["is_key_number"] = m.pin_bt_spread.abs().isin([3.0, 7.0]).astype(int)
    m["is_pickem"] = (m.pin_bt_spread.abs() <= 1.0).astype(int)
    return m


# ------------------------------------------------------------------ assembly
def build() -> pd.DataFrame:
    g = pd.read_csv("data/raw/games.csv")
    g = g[g.season.isin(SEASONS)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime)
    g["kick_utc"] = dt.dt.tz_localize(
        ZoneInfo("America/New_York"), ambiguous=True, nonexistent="shift_forward"
    ).dt.tz_convert("UTC")

    tg = add_form(team_game_stats())
    form = tg[["team", "game_id"] + FORM_COLS]

    base = g[["game_id", "season", "week", "game_type", "home_team", "away_team",
              "kick_utc", "home_rest", "away_rest", "div_game", "roof", "surface",
              "spread_line", "total_line", "result", "total",
              "home_score", "away_score"]].copy()

    for side in ["home", "away"]:
        f = form.rename(columns={c: f"{side}_{c}" for c in FORM_COLS})
        base = base.merge(
            f.rename(columns={"team": f"{side}_team"}),
            on=["game_id", f"{side}_team"], how="left")

    for c in FORM_COLS:
        base[f"d_{c}"] = base[f"home_{c}"] - base[f"away_{c}"]

    # schedule context
    base["rest_diff"] = base.home_rest - base.away_rest
    base["home_short"] = (base.home_rest <= 5).astype(int)
    base["away_short"] = (base.away_rest <= 5).astype(int)
    base["home_off_bye"] = (base.home_rest >= 12).astype(int)
    base["away_off_bye"] = (base.away_rest >= 12).astype(int)
    base["is_dome"] = base.roof.isin(["dome", "closed"]).astype(int)
    base["is_turf"] = (~base.surface.isin(["grass"])).astype(int)
    base["is_playoff"] = (base.game_type != "REG").astype(int)
    base["late_season"] = (base.week >= 14).astype(int)
    base["kick_hour_utc"] = base.kick_utc.dt.hour
    base["is_primetime"] = base.kick_hour_utc.isin([0, 1, 23]).astype(int)

    odds = pd.read_parquet("data/processed/odds_by_game_book.parquet")
    base = base.merge(market_features(odds), on="game_id", how="left")

    pin_close = odds[odds.book == "pinnacle"][["game_id", "cl_spread", "cl_total"]].rename(
        columns={"cl_spread": "pin_cl_spread", "cl_total": "pin_cl_total"})
    base = base.merge(pin_close, on="game_id", how="left")

    # ---- targets ----
    base["spread_move"] = base.pin_cl_spread - base.pin_bt_spread
    base["total_move"] = base.pin_cl_total - base.pin_bt_total
    base["margin"] = base.home_score - base.away_score

    return base


FEATURE_COLS = None


def feature_columns(df: pd.DataFrame) -> list[str]:
    drop = {
        "game_id", "season", "week", "game_type", "home_team", "away_team",
        "kick_utc", "roof", "surface", "spread_line", "total_line", "result",
        "total", "home_score", "away_score", "margin",
        "spread_move", "total_move", "pin_cl_spread", "pin_cl_total",
    }
    return [c for c in df.columns
            if c not in drop and pd.api.types.is_numeric_dtype(df[c])]


if __name__ == "__main__":
    import os
    os.makedirs("data/processed", exist_ok=True)
    df = build()
    df.to_parquet("data/processed/features.parquet", index=False)
    fc = feature_columns(df)
    print(f"games: {len(df)}  features: {len(fc)}")
    print(df.groupby("season").agg(
        n=("game_id", "size"),
        has_bt=("pin_bt_spread", lambda s: s.notna().sum()),
        has_cl=("pin_cl_spread", lambda s: s.notna().sum()),
        has_move=("spread_move", lambda s: s.notna().sum()),
    ))
    print(f"\nspread_move describe:\n{df.spread_move.describe().round(3)}")
