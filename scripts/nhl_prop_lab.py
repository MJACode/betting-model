"""NHL player-prop lab: distributions from the per-game logs, scored against naive baselines.

THERE ARE NO HISTORICAL NHL PROP PRICES IN THIS DATABASE (the feed sells them
from 2023-05-03; nothing is bought yet), so this cannot report units. What it
CAN report, and what decides whether a prop model is worth pricing at all:
does a model built from usage and matchup beat the two projections a book
could make for free — the player's season-to-date average, and his last ten
games — on games it has never seen?

MARKETS and the lines books commonly hang (docs/nhl_market_research.md §6):

    skater   shots on goal 1.5 / 2.5 / 3.5     points 0.5     assists 0.5
             goals 0.5 (anytime scorer)         blocked shots 1.5     hits 1.5 / 2.5
    goalie   saves 24.5 / 27.5 / 29.5          (starters only; void if he sits)

MODEL. One Poisson-objective gradient-boosted model per stat. Inputs are all
as-of (shifted one game): the player's own exponentially weighted rate (long
and short), his ice time and power-play time, his shot attempts, position,
home / away, rest; and the OPPONENT's allowed rate of the same thing.
P(over a line) comes from the Poisson tail of the predicted mean.

SCORE. Log loss of P(over) at each line on the holdout seasons (2024-25 and
2025-26), beside both baselines, plus calibration in the band that would be
bet (model P(over) >= 0.60 or <= 0.40). Walk-forward: train on every season
before the test season.

    python -m scripts.nhl_prop_lab
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.metrics import log_loss
from xgboost import XGBRegressor

sys.path.insert(0, ".")

from data.db import get_connection

TEST_SEASONS = [2025, 2026]
SKATER_MARKETS = {"shots": (1.5, 2.5, 3.5), "points": (0.5,), "assists": (0.5,),
                  "goals": (0.5,), "blocked_shots": (1.5,), "hits": (1.5, 2.5)}
GOALIE_LINES = (24.5, 27.5, 29.5)
PARAMS = dict(objective="count:poisson", n_estimators=400, max_depth=4, learning_rate=0.03,
              subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5.0,
              random_state=42, n_jobs=-1, verbosity=0)


def _ew(g, col, hl, minp=3):
    return g[col].transform(lambda s: s.shift(1).ewm(halflife=hl, min_periods=minp).mean())


def skaters(conn) -> pd.DataFrame:
    cols = ["nhl_game_id", "player_id", "position", "season", "game_date", "team", "opponent",
            "is_home", "goals", "assists", "points", "shots", "shot_attempts", "hits",
            "blocked_shots", "toi_seconds", "pp_toi_seconds"]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM nhl_skater_game_log "
                        f"WHERE game_type = 2").fetchall()
    d = pd.DataFrame(rows, columns=cols).sort_values(["player_id", "game_date", "nhl_game_id"])
    for c in cols[8:]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    g = d.groupby("player_id", sort=False)
    for stat in ("goals", "assists", "points", "shots", "shot_attempts", "hits", "blocked_shots"):
        d[f"{stat}_l"], d[f"{stat}_s"] = _ew(g, stat, 30), _ew(g, stat, 6)
        # the two free projections a book could make
        d[f"{stat}_std"] = d.groupby(["player_id", "season"])[stat].transform(
            lambda s: s.shift(1).expanding(min_periods=5).mean())
        d[f"{stat}_l10"] = g[stat].transform(lambda s: s.shift(1).rolling(10, min_periods=5).mean())
    d["toi_l"], d["toi_s"] = _ew(g, "toi_seconds", 20), _ew(g, "toi_seconds", 4)
    d["pp_toi_l"], d["pp_toi_s"] = _ew(g, "pp_toi_seconds", 20), _ew(g, "pp_toi_seconds", 4)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    d["is_d"] = (d.position == "D").astype(int)
    return d


def opponent_allowed(conn) -> pd.DataFrame:
    """What each team has ALLOWED per game, as-of: the matchup side of every prop."""
    cols = ["nhl_game_id", "team", "opponent", "game_date", "goals_against", "shots_against",
            "blocked_shots", "hits", "times_shorthanded", "shots_for"]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM nhl_team_game_log").fetchall()
    t = pd.DataFrame(rows, columns=cols).sort_values(["team", "game_date", "nhl_game_id"])
    for c in cols[4:]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    g = t.groupby("team", sort=False)
    out = t[["nhl_game_id", "team"]].copy()
    out["opp_ga"], out["opp_sa"] = _ew(g, "goals_against", 25, 5), _ew(g, "shots_against", 25, 5)
    out["opp_pk_opps"] = _ew(g, "times_shorthanded", 25, 5)
    out["opp_sf"] = _ew(g, "shots_for", 25, 5)          # how much the opponent shoots (blocks, saves)
    # hits / blocks the opponent's OPPONENTS have recorded is scorer- and style-driven; keep simple
    return out.rename(columns={"team": "opponent"})


def fit_score(d: pd.DataFrame, stat: str, feats: list[str], lines, base_cols: dict) -> list[dict]:
    rows = []
    use = d.dropna(subset=feats + [stat] + list(base_cols.values()))
    for test in TEST_SEASONS:
        tr, te = use[use.season.between(2020, test - 1)], use[use.season == test]
        if te.empty:
            continue
        m = XGBRegressor(**PARAMS)
        m.fit(tr[feats].values.astype(float), tr[stat].values.astype(float))
        mu = np.clip(m.predict(te[feats].values.astype(float)), 1e-3, None)
        y = te[stat].values
        for ln in lines:
            over = (y > ln).astype(int)
            k = int(np.floor(ln))
            row = {"market": stat, "line": ln, "test": test, "n": len(te),
                   "over_rate": round(float(over.mean()), 3),
                   "model": round(log_loss(over, np.clip(poisson.sf(k, mu), 1e-4, 1 - 1e-4)), 4)}
            for name, col in base_cols.items():
                b = np.clip(te[col].values, 1e-3, None)
                row[name] = round(log_loss(over, np.clip(poisson.sf(k, b), 1e-4, 1 - 1e-4)), 4)
            p = poisson.sf(k, mu)
            hi, lo = p >= 0.60, p <= 0.40
            row["n p>=.60"], row["hit p>=.60"] = int(hi.sum()), (round(float(over[hi].mean()), 3) if hi.sum() else None)
            row["avg p>=.60"] = round(float(p[hi].mean()), 3) if hi.sum() else None
            row["n p<=.40"], row["under hit p<=.40"] = int(lo.sum()), (round(float(1 - over[lo].mean()), 3) if lo.sum() else None)
            rows.append(row)
    return rows


def main() -> None:
    conn = get_connection()
    try:
        d, opp = skaters(conn), opponent_allowed(conn)
        gcols = ["nhl_game_id", "player_id", "team", "opponent", "season", "game_date", "is_home",
                 "started", "saves", "shots_against", "toi_seconds"]
        grows = conn.execute(f"SELECT {', '.join(gcols)} FROM nhl_goalie_game_log "
                             f"WHERE game_type = 2").fetchall()
    finally:
        conn.close()
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left")
    d = d[d.gp >= 10]                                     # a line is not hung on a debutant
    print(f"skater-games with 10+ prior games: {len(d):,} "
          f"({int((d.season.isin(TEST_SEASONS)).sum()):,} in the holdout seasons)")
    out = []
    common = ["toi_l", "toi_s", "pp_toi_l", "pp_toi_s", "is_home", "rest", "is_d", "gp"]
    spec = {
        "shots": ["shots_l", "shots_s", "shot_attempts_l", "shot_attempts_s", "opp_sa"],
        "points": ["points_l", "points_s", "shots_l", "goals_l", "assists_l", "opp_ga", "opp_pk_opps"],
        "assists": ["assists_l", "assists_s", "points_l", "opp_ga", "opp_pk_opps"],
        "goals": ["goals_l", "goals_s", "shots_l", "shots_s", "opp_ga", "opp_sa"],
        "blocked_shots": ["blocked_shots_l", "blocked_shots_s", "opp_sf"],
        "hits": ["hits_l", "hits_s"],
    }
    for stat, lines in SKATER_MARKETS.items():
        out += fit_score(d, stat, spec[stat] + common, lines,
                         {"season avg": f"{stat}_std", "last 10": f"{stat}_l10"})
    # ── goalie saves ─────────────────────────────────────────────────────────
    g = pd.DataFrame(grows, columns=gcols).sort_values(["player_id", "game_date", "nhl_game_id"])
    for c in ("saves", "shots_against", "toi_seconds"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g[(g.started == 1) & (g.toi_seconds >= 3300)]    # full starts: a pulled starter is a different bet
    gg = g.groupby("player_id", sort=False)
    g["saves_l"], g["saves_s"] = _ew(gg, "saves", 25), _ew(gg, "saves", 5)
    g["sa_l"] = _ew(gg, "shots_against", 25)
    g["saves_std"] = g.groupby(["player_id", "season"])["saves"].transform(
        lambda s: s.shift(1).expanding(min_periods=5).mean())
    g["saves_l10"] = gg["saves"].transform(lambda s: s.shift(1).rolling(10, min_periods=5).mean())
    g["gp"] = gg.cumcount()
    g = g.merge(opp[["nhl_game_id", "opponent", "opp_sf"]], on=["nhl_game_id", "opponent"], how="left")
    # his OWN team's shots allowed, as-of
    own = opp.rename(columns={"opponent": "team", "opp_sa": "own_sa"})[["nhl_game_id", "team", "own_sa"]]
    g = g.merge(own, on=["nhl_game_id", "team"], how="left")
    out += fit_score(g[g.gp >= 10], "saves", ["saves_l", "saves_s", "sa_l", "opp_sf", "own_sa", "is_home", "gp"],
                     GOALIE_LINES, {"season avg": "saves_std", "last 10": "saves_l10"})
    res = pd.DataFrame(out)
    res["beats both"] = (res.model < res[["season avg", "last 10"]].min(axis=1))
    res["gain vs best naive"] = (res[["season avg", "last 10"]].min(axis=1) - res.model).round(4)
    pd.set_option("display.width", 250)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
