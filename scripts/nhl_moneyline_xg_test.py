"""Does a shot-quality (expected goals) input group make the rebuilt NHL moneyline better?

RESEARCH ONLY. Reads caches, writes nothing to the database, registers nothing.

The rebuilt model is models/nhl_moneyline_anchored.py (DraftKings' no-vig
log-odds as an unpenalised offset, plus 34 inputs from the per-game logs). This
script grades it the way scripts/nhl_moneyline_anchored_backtest.py does --
walk-forward over 2021-22 .. 2025-26, each test season fit only on earlier
seasons from 2020-21, the penalty chosen on the training seasons by
`choose_C` -- for

    (a) FEATURES     the 34 production inputs
    (b) FEATURES_XG  the 34 plus the "xg" group (team xGF/xGA all situations
                     and 5-on-5, 5-on-5 xG share, finishing above expected,
                     the starter's shrunk goals saved above expected)
    and the ablation: (b) without the xG team inputs, (b) without the goalie one.

The xG behind the "xg" group is scripts/nhl_xg_walkforward.py's: every season
scored by an xG model that never saw it, level-corrected as of the previous
completed season. Its per-team-game and per-goalie-game sums are read from
NHL_XG_TEST_DIR (default %TEMP%/nhl_xg_test).

Prices, logs and best prices are the rebuild's caches
(NHL_REBUILD_CACHE, default %TEMP%/nhl_ml_rebuild_cache). A missing cache is an
error here, never a database read.

    python -m scripts.nhl_moneyline_xg_test --reproduce     # (a) only, against the reference
    python -m scripts.nhl_moneyline_xg_test                 # everything
    python -m scripts.nhl_moneyline_xg_test --parity        # serve-vs-train parity, FEATURES_XG
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
from scripts.nhl_market_lab import summarise  # noqa: E402
from scripts.nhl_market_lab3 import _nv  # noqa: E402
from scripts.nhl_moneyline_rebuild import TEST_SEASONS, bets  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)

CACHE = os.environ.get("NHL_REBUILD_CACHE", r"C:/Users/micha/AppData/Local/Temp/nhl_ml_rebuild_cache")
XG_DIR = os.environ.get("NHL_XG_TEST_DIR", r"C:/Users/micha/AppData/Local/Temp/nhl_xg_test")
CUTS = (0.02, 0.04, 0.06, 0.08, 0.10)
# The production module's walk-forward (commit 4a855392, after the goalie
# as-of fix): best price, -200 floor.
REFERENCE = {0.06: (1326, 83.2, 6.28), 0.04: (2020, 93.5, None)}


def _load(name: str):
    path = os.path.join(CACHE, f"{name}.pkl")
    if not os.path.exists(path):
        raise SystemExit(f"missing cache {path} -- this script never reads the database")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def xg_logs() -> dict:
    """The walk-forward xG sums, as the two optional `logs` keys build_inputs reads."""
    team = pd.read_parquet(os.path.join(XG_DIR, "team_game_xg_wf.parquet"))
    goalie = pd.read_parquet(os.path.join(XG_DIR, "goalie_game_xg_wf.parquet"))
    return {"team_xg": team, "goalie_xg": goalie}


def frame(with_xg: bool) -> pd.DataFrame:
    """scripts/nhl_moneyline_anchored_backtest.module_frame, from the caches only."""
    logs = dict(_load("module_logs_v1"))
    if with_xg:
        logs.update(xg_logs())
    px = _load("inputs_v1")[4]                 # the research run's own price read
    best = _load("best_prices_v1")
    df = m.build_inputs(logs)
    df = df.merge(px, on="game_id", how="left").merge(best, on="game_id", how="left")
    df["y"] = (df.hs > df.as_).astype(int)
    for b in ("dra", "pin"):
        df[f"{b}_mkt_home"] = _nv(df, f"{b}_ml_home_open", f"{b}_ml_away_open")
    df["pin_close_home"] = _nv(df, "pin_ml_home_close", "pin_ml_away_close")
    df["mkt_logit"] = np.log(df.dra_mkt_home / (1 - df.dra_mkt_home))
    return df.copy()


def walk(df: pd.DataFrame, feats: list[str], seasons=TEST_SEASONS[1:]) -> pd.DataFrame:
    """scripts/nhl_moneyline_anchored_backtest.walk with the input list as an argument."""
    use = df[df.season >= m.FIRST_PRICED_SEASON].dropna(subset=feats + ["mkt_logit", "y"])
    parts = []
    for test in seasons:
        tr, te = use[use.season < test], use[use.season == test].copy()
        if len(tr) < 800 or te.empty:
            continue
        model, C = m.fit(tr, feats)
        te["C"] = C
        te["p"] = model.predict_proba(te[feats].values, te.mkt_logit.values)[:, 1]
        parts.append(te)
    return pd.concat(parts)


def grid(name: str, pred: pd.DataFrame, floor: float, cuts=CUTS) -> list[dict]:
    """Best bettable price, the production price floor, units / ROI / 95% interval /
    CLV vs Pinnacle's close, early and late halves, ROI by season (bets)."""
    rows = []
    for c in cuts:
        b = bets(pred, c, "best")
        b = b[b.price >= floor]
        row = {"model": name, "EV>=": c, **summarise(b.profit.values, b.clv.values)}
        if len(b) >= 2:
            order = np.argsort(b.game_date.values, kind="stable")
            half = len(order) // 2
            row["early"] = round(float(b.profit.values[order[:half]].mean()) * 100, 1)
            row["late"] = round(float(b.profit.values[order[half:]].mean()) * 100, 1)
        for s in sorted(pred.season.unique()):
            bs = b[b.season == s]
            row[str(int(s))] = f"{bs.profit.mean() * 100:+.1f} ({len(bs)})" if len(bs) else "- (0)"
        rows.append(row)
    return rows


def show(title: str, rows) -> None:
    print(f"\n### {title}\n")
    print((rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)).to_string(index=False))


def _ll(y, p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def paired(a: pd.DataFrame, b: pd.DataFrame, label: str) -> list[dict]:
    """Per-game log loss of b minus a, on the games both scored; mean and a
    normal 95% interval, overall and by season. Negative = b is more accurate."""
    j = a[["game_id", "season", "y", "p"]].merge(b[["game_id", "p"]], on="game_id", suffixes=("_a", "_b"))
    assert len(j) == len(a) == len(b), f"{label}: the two runs scored different games"
    j["d"] = _ll(j.y, j.p_b) - _ll(j.y, j.p_a)
    rows = []
    for s, g in list(j.groupby("season")) + [("all", j)]:
        se = g.d.std(ddof=1) / np.sqrt(len(g))
        rows.append({"comparison": label, "season": s if s == "all" else int(s), "games": len(g),
                     "log loss a": round(float(_ll(g.y, g.p_a).mean()), 5),
                     "log loss b": round(float(_ll(g.y, g.p_b).mean()), 5),
                     "b - a": round(float(g.d.mean()), 5),
                     "95% interval": f"{g.d.mean() - 1.96 * se:+.5f}..{g.d.mean() + 1.96 * se:+.5f}"})
    return rows


def reproduce(pred: pd.DataFrame, floor: float) -> bool:
    ok = True
    for c, (n, units, roi) in REFERENCE.items():
        b = bets(pred, c, "best")
        b = b[b.price >= floor]
        s = summarise(b.profit.values, b.clv.values)
        hit = s["bets"] == n and s["units"] == units and (roi is None or s["roi"] == roi)
        ok &= hit
        print(f"  EV>={c}: {s['bets']:,} bets {s['units']:+.1f} units {s['roi']:+.2f}%  "
              f"(reference {n:,} bets {units:+.1f} units{'' if roi is None else f' {roi:+.2f}%'}) "
              f"-> {'REPRODUCED' if hit else 'DIFFERENT'}")
    return ok


XG_TEAM = [f for f in m.GROUPS["xg"] if f != "d_g_gsax"]
XG_GOALIE = ["d_g_gsax"]


def serve_parity(n_dates: int = 30) -> None:
    """Score past games the way production scores tonight's: every log (the xG
    sums included) cut to the games dated before the game day, the game passed
    in as UPCOMING with the goalie who started it as the listed one. Every
    FEATURES_XG input must equal the training frame's row for that game."""
    logs = dict(_load("module_logs_v1"))
    logs.update(xg_logs())
    train = m.build_inputs(logs)
    played = train[train.season == 2026]
    dates = sorted(played.game_date.unique())
    rng = np.random.default_rng(11)
    pick = sorted(rng.choice(dates, size=min(n_dates, len(dates)), replace=False))
    gl = logs["goalie"]
    starters = gl[pd.to_numeric(gl.started) == 1][["game_id", "team", "player_id"]]
    n_vals, n_xg, bad = 0, 0, []
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
            for f in m.FEATURES_XG:
                a, b = served.at[gid, f], ref.at[gid, f]
                n_vals += 1
                n_xg += f in m.GROUPS["xg"]
                if not ((pd.isna(a) and pd.isna(b)) or abs(float(a) - float(b)) < 1e-9):
                    bad.append((d, gid, f, a, b))
    print(f"\nserve-vs-train parity, FEATURES_XG: {len(pick)} dates of 2025-26, {n_vals:,} values "
          f"({n_xg:,} of them xG inputs), {len(bad)} disagreements")
    for row in bad[:20]:
        print("   ", row)


def gsax_starts_only(dx: pd.DataFrame) -> pd.Series:
    """The goalie input with its EWMA over the goalie's prior STARTS only
    (the module's d_g_gsax, like d_g_sv, spans every prior appearance)."""
    logs = _load("module_logs_v1")
    x = xg_logs()["goalie_xg"][["nhl_game_id", "player_id", "unblocked_faced", "xg_faced", "goals_allowed"]]
    gl = logs["goalie"]
    st = gl[pd.to_numeric(gl.started) == 1][["nhl_game_id", "game_id", "team", "player_id", "game_date"]].copy()
    st = st.merge(x, on=["nhl_game_id", "player_id"], how="left", validate="m:1")
    for c in ("unblocked_faced", "xg_faced", "goals_allowed"):
        st[c] = st[c].fillna(0)
    st["game_date"] = pd.to_datetime(st.game_date.astype(str).str[:10])
    st = st.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = st.groupby("player_id", sort=False)
    ews = {c: g[c].transform(lambda s: s.shift(1).ewm(halflife=m.GOALIE_HALF_LIFE, min_periods=1).sum()).fillna(0)
           for c in ("unblocked_faced", "xg_faced", "goals_allowed")}
    st["r"] = (ews["xg_faced"] - ews["goals_allowed"]) / (ews["unblocked_faced"] + m.GOALIE_PRIOR_SHOTS)
    st = st.drop_duplicates(["game_id", "team"]).set_index(["game_id", "team"]).r
    h = st.reindex(pd.MultiIndex.from_arrays([dx.game_id, dx.home])).to_numpy()
    a = st.reindex(pd.MultiIndex.from_arrays([dx.game_id, dx.away])).to_numpy()
    return pd.Series(h - a, index=dx.index)


def starts_only(floor: float) -> None:
    dx = frame(with_xg=True)
    dx["d_g_gsax_starts"] = gsax_starts_only(dx)
    use = dx[dx.season >= m.FIRST_PRICED_SEASON].dropna(subset=m.FEATURES + ["mkt_logit", "y"])
    print(f"starts-only goalie input: missing on {int(use.d_g_gsax_starts.isna().sum())} of {len(use):,} rows; "
          f"r with the all-appearances version {use.d_g_gsax_starts.corr(use.d_g_gsax):.4f}")
    a = walk(dx, m.FEATURES)
    runs = {"34 + goalie GSAx (starts only)": walk(dx, m.FEATURES + ["d_g_gsax_starts"]),
            "34 + xG team + goalie GSAx (starts only)": walk(dx, m.FEATURES + XG_TEAM + ["d_g_gsax_starts"])}
    rows, g = [], []
    for name, pred in runs.items():
        rows += [r for r in paired(a, pred, f"{name}  vs  (a) 34") if r["season"] == "all"]
        g += grid(name, pred, floor)
    show("Goalie input over prior STARTS only: paired log loss against (a)", rows)
    show("... and its grid (best price, price floor)", g)


def decompose(floor: float) -> None:
    """Where (b)'s bets differ from (a)'s, cut by cut: the bets both make on the
    same side, and the bets only one of them makes. Reads the predictions the
    full run saved."""
    with open(os.path.join(XG_DIR, "xg_test_predictions.pkl"), "rb") as fh:
        pred = pickle.load(fh)
    df = frame(with_xg=False)
    cols = [c for c in df.columns if c not in ("p", "C")]
    A = df[cols].merge(pred["(a) 34"][["game_id", "p"]], on="game_id")
    B = df[cols].merge(pred["(b) 34 + xG"][["game_id", "p"]], on="game_id")
    rows = []
    for c in CUTS:
        a = bets(A, c, "best")
        a = a[a.price >= floor]
        b = bets(B, c, "best")
        b = b[b.price >= floor]
        ka, kb = set(zip(a.game_id, a.side_home)), set(zip(b.game_id, b.side_home))
        sets = (("both, same side", a[[k in kb for k in zip(a.game_id, a.side_home)]]),
                ("only (a)", a[[k not in kb for k in zip(a.game_id, a.side_home)]]),
                ("only (b)", b[[k not in ka for k in zip(b.game_id, b.side_home)]]))
        for name, s in sets:
            rows.append({"EV>=": c, "set": name, **summarise(s.profit.values, s.clv.values)})
    show("(a) and (b) bets, split into shared and one-model-only (best price, price floor)", rows)


def main() -> None:
    floor = config.min_odds_for(m.MODEL_ID)
    print(f"production price floor for {m.MODEL_ID}: {floor:+.0f}")
    if "--parity" in sys.argv:
        serve_parity()
        return
    if "--decompose" in sys.argv:
        decompose(floor)
        return
    if "--starts-only" in sys.argv:
        starts_only(floor)
        return
    df = frame(with_xg=False)
    a0 = walk(df, m.FEATURES)
    print(f"(a) 34 inputs, module WITHOUT xG logs: {len(a0):,} games, "
          f"C by season {a0.groupby('season').C.first().to_dict()}")
    ok = reproduce(a0, floor)
    if "--reproduce" in sys.argv:
        return
    if not ok:
        raise SystemExit("(a) does not reproduce the reference -- not grading (b)")

    dx = frame(with_xg=True)
    # The xG logs must not move the 34: same rows, same values.
    assert list(dx.game_id) == list(df.game_id), "the xG logs changed the row set"
    worst = max(float(np.nanmax(np.abs(dx[f].values.astype(float) - df[f].values.astype(float)))
                      if dx[f].notna().any() else 0.0) for f in m.FEATURES)
    same_nan = all((dx[f].isna() == df[f].isna()).all() for f in m.FEATURES)
    print(f"the 34 inputs with and without the xG logs: max |difference| {worst:.1e}, "
          f"same missing pattern: {same_nan}")
    graded = dx[dx.season >= m.FIRST_PRICED_SEASON].dropna(subset=["mkt_logit", "y"])
    print("rows (2020-21 on, priced) with every input -- 34: "
          f"{len(graded.dropna(subset=m.FEATURES)):,}; 34 + xG: {len(graded.dropna(subset=m.FEATURES_XG)):,}")
    print("xG inputs missing where the 34 are complete: "
          f"{graded.dropna(subset=m.FEATURES)[m.GROUPS['xg']].isna().sum().to_dict()}")

    runs = {
        "(a) 34": walk(dx, m.FEATURES),
        "(b) 34 + xG": walk(dx, m.FEATURES_XG),
        "(b) without xG team inputs (34 + goalie GSAx)": walk(dx, m.FEATURES + XG_GOALIE),
        "(b) without xG goalie input (34 + xG team)": walk(dx, m.FEATURES + XG_TEAM),
    }
    a = runs["(a) 34"]
    assert np.array_equal(a.p.values, a0.p.values), "(a) differs with the xG logs loaded"
    for name, pred in runs.items():
        print(f"{name}: {len(pred):,} games, C by season {pred.groupby('season').C.first().to_dict()}")

    show("Paired log loss, per game, b minus a (negative = more accurate than the 34; 95% interval)",
         paired(a, runs["(b) 34 + xG"], "(b) 34 + xG  vs  (a) 34"))
    b = runs["(b) 34 + xG"]
    abl = []
    abl += paired(b, runs["(b) without xG team inputs (34 + goalie GSAx)"], "remove xG team inputs from (b)")
    abl += paired(b, runs["(b) without xG goalie input (34 + xG team)"], "remove goalie GSAx from (b)")
    abl += paired(a, runs["(b) without xG team inputs (34 + goalie GSAx)"], "34 + goalie GSAx  vs  (a) 34")
    abl += paired(a, runs["(b) without xG goalie input (34 + xG team)"], "34 + xG team  vs  (a) 34")
    show("Ablation, paired log loss (removing a part: positive = that part helped (b))",
         [r for r in abl if r["season"] == "all"])
    show("Ablation by season", [r for r in abl if r["season"] != "all"])

    rows = []
    for name, pred in runs.items():
        rows += grid(name, pred, floor)
    show(f"Best bettable price, price floor {floor:+.0f}, model's own probability: units, ROI %, "
         "95% interval, CLV (no-vig points vs Pinnacle's close), % beating the close, halves, ROI by season (bets)",
         rows)

    # How much of the xG group is new: correlation with its nearest existing input,
    # on the rows the walk-forward trains and tests on.
    use = dx[dx.season >= m.FIRST_PRICED_SEASON].dropna(subset=m.FEATURES_XG + ["mkt_logit", "y"])
    near = {"d_xg_share5": "d_sat_share", "d_xgf": "d_sf", "d_xga": "d_sa", "d_xgf5": "d_sat_share",
            "d_xg_fin": "d_sh_pct", "d_g_gsax": "d_g_sv"}
    show("Each xG input against its nearest existing input (Pearson r, 2020-21 .. 2025-26 rows)",
         [{"xG input": k, "existing input": v, "r": round(float(use[k].corr(use[v])), 3)}
          for k, v in near.items()])
    model, C = m.fit(use[use.season < 2026], m.FEATURES_XG)
    w = pd.Series(model.w[1:], index=m.FEATURES_XG)
    top = set(w.abs().nlargest(8).index) | set(m.GROUPS["xg"])
    wt = w[[f for f in w.abs().sort_values(ascending=False).index if f in top]]
    show(f"(b) fit on 2020-21 .. 2024-25 (the 2025-26 fold), C={C}: weight per standard deviation of each "
         "xG input and of the 8 largest overall",
         [{"input": f, "group": "xg" if f in m.GROUPS["xg"] else "34", "weight": round(float(v), 4)}
          for f, v in wt.items()])

    out = os.path.join(XG_DIR, "xg_test_predictions.pkl")
    with open(out, "wb") as fh:
        pickle.dump({k: v[["game_id", "season", "game_date", "y", "p", "C"]] for k, v in runs.items()}, fh)
    print(f"\npredictions: {out}")


if __name__ == "__main__":
    main()
