"""NHL moneyline, rebuilt: every input group we can build, graded against the market.

mike, 2026-10-13: "What else is missing in the models ... Look at and rebuild
the money line model." The live `nhl_moneyline` reads 22 season-snapshot
inputs, six of them dead (injuries, no NHL history before 2026-04-05), with no
rest, no travel, no lineup and the previous game's goalie at decision time.
This script rebuilds the inputs from the per-game logs and tests each group by
removal, walk-forward, at real prices.

INPUT GROUPS (all as-of: built from a team's or goalie's PRIOR games only)
  form, shots, special, goalie, schedule, rating -- round two's
      (`scripts/nhl_market_lab2.build`): exponentially weighted goals, shots,
      5-on-5 shot attempts, finishing, power play / penalty kill and their
      volume, faceoffs, the starter's shrunk save rate and starts, rest,
      back-to-back, road trip, a running goal-margin rating.
  workload -- the starter's days since his last start, starts in the last 7
      days, and his share of the team's last 20 starts (is he the number one).
  venue -- home-ice: the home side's EWMA goal margin in its home games and
      the visitor's in its road games.
  travel -- km from each team's previous game to this one, and the time-zone
      shift (arena table below).
  lineup -- the share of the team's regular ice time that dressed (regulars =
      the 18 skaters with the most ice time over the team's last 20 games among
      those who played in its last 10), and the points-per-game of regulars
      who did not dress.
  shot quality (expected goals) is NOT here: no shot-level data is stored yet.

TIMING. The goalie and lineup inputs are the ones that actually played, as
every training row of the live model's goalie input already is. That is the
game-day decision with the confirmed starter, not a decision days ahead.

PRICES. `scripts/nhl_market_lab3.feed_prices` (the bought archive, read by
game id): DraftKings' and Pinnacle's first and last pre-game quote on game day.
Decide against DraftKings' first quote, grade at that price; closing-line
value = Pinnacle's last no-vig minus its first, on the side taken.

WALK-FORWARD. Test seasons 2021..2026 (2020-21..2025-26); each is fit on every
earlier season from 2018-19. The logistic model's strength is chosen on the
season before the test season, never on the test season.

    python -m scripts.nhl_moneyline_rebuild
"""
from __future__ import annotations

import os
import pickle
import sys
import time
from math import asin, cos, radians, sin, sqrt

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, ".")

from data.db import get_connection  # noqa: E402
from scripts.nhl_market_lab import novig, summarise, win_per_unit  # noqa: E402
from scripts.nhl_market_lab2 import GROUPS as LAB_GROUPS, TREE, build  # noqa: E402
from scripts.nhl_market_lab3 import _nv, feed_prices  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 40)
CACHE = os.environ.get("NHL_REBUILD_CACHE", r"C:/Users/micha/AppData/Local/Temp/nhl_ml_rebuild_cache")
TEST_SEASONS = [2021, 2022, 2023, 2024, 2025, 2026]
PRICED_SEASONS = list(range(2021, 2027))
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3)
EV_CUTS = (0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20)

# Arena latitude, longitude, UTC offset in standard time. Neutral-site games
# are treated as the home team's arena.
ARENA = {
    "ANA": (33.807, -117.877, -8), "ARI": (33.532, -112.261, -7), "BOS": (42.366, -71.062, -5),
    "BUF": (42.875, -78.876, -5), "CAR": (35.803, -78.722, -5), "CBJ": (39.969, -83.006, -5),
    "CGY": (51.037, -114.052, -7), "CHI": (41.881, -87.674, -6), "COL": (39.749, -105.008, -7),
    "DAL": (32.790, -96.810, -6), "DET": (42.341, -83.055, -5), "EDM": (53.547, -113.498, -7),
    "FLA": (26.158, -80.326, -5), "LAK": (34.043, -118.267, -8), "MIN": (44.945, -93.101, -6),
    "MTL": (45.496, -73.569, -5), "NJD": (40.734, -74.171, -5), "NSH": (36.159, -86.779, -6),
    "NYI": (40.711, -73.726, -5), "NYR": (40.750, -73.993, -5), "OTT": (45.297, -75.927, -5),
    "PHI": (39.901, -75.172, -5), "PIT": (40.439, -79.989, -5), "SEA": (47.622, -122.354, -8),
    "SJS": (37.333, -121.901, -8), "STL": (38.627, -90.203, -6), "TBL": (27.943, -82.452, -5),
    "TOR": (43.643, -79.379, -5), "UTA": (40.768, -111.901, -7), "VAN": (49.278, -123.109, -8),
    "VGK": (36.103, -115.178, -8), "WPG": (49.893, -97.144, -6), "WSH": (38.898, -77.021, -5),
}

NEW_GROUPS = {
    "workload": ["h_g_days", "a_g_days", "h_g_starts7", "a_g_starts7", "h_g_share", "a_g_share"],
    "venue":    ["h_home_gd", "a_road_gd"],
    "travel":   ["h_travel_km", "a_travel_km", "h_tz_shift", "a_tz_shift"],
    "lineup":   ["h_lineup_share", "a_lineup_share", "h_missing_ppg", "a_missing_ppg"],
}
GROUPS = {**LAB_GROUPS, **NEW_GROUPS}


def _db_quiet(conn, label: str) -> None:
    """Wait while the live database is busy (games are on)."""
    for _ in range(10):
        n, longest = conn.execute(
            "SELECT count(*) FILTER (WHERE state='active'), "
            "coalesce(extract(epoch FROM max(now()-query_start) FILTER (WHERE state='active')), 0) "
            "FROM pg_stat_activity WHERE datname = current_database()").fetchone()
        if int(n) <= 5 and float(longest) < 60:
            print(f"[load] {label}: {int(n)} active, longest {float(longest):.0f}s -- reading")
            return
        print(f"[load] {label}: {int(n)} active, longest {float(longest):.0f}s -- waiting 120s")
        time.sleep(120)
    raise RuntimeError("database stayed busy")


def _cached(name: str, fn):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"{name}.pkl")
    if os.path.exists(path):
        with open(path, "rb") as fh:
            return pickle.load(fh)
    out = fn()
    with open(path, "wb") as fh:
        pickle.dump(out, fh)
    return out


# ── the new input groups ─────────────────────────────────────────────────────

def goalie_workload(conn) -> pd.DataFrame:
    cols = ["nhl_game_id", "game_id", "team", "player_id", "game_date", "started"]
    gl = pd.DataFrame(conn.execute(f"SELECT {', '.join(cols)} FROM nhl_goalie_game_log").fetchall(),
                      columns=cols)
    gl["game_date"] = pd.to_datetime(gl.game_date)
    st = gl[gl.started == 1].sort_values(["player_id", "game_date", "nhl_game_id"]).copy()
    prev = st.groupby("player_id").game_date.shift(1)
    st["g_days"] = (st.game_date - prev).dt.days.clip(upper=10).fillna(10)
    # starts in the 7 days before this one (this goalie)
    st["g_starts7"] = 0
    for pid, g in st.groupby("player_id", sort=False):
        d = g.game_date.values
        lo = np.searchsorted(d, d - np.timedelta64(7, "D"), side="left")
        st.loc[g.index, "g_starts7"] = np.arange(len(d)) - lo
    # his share of the team's previous 20 starts
    st = st.sort_values(["team", "game_date", "nhl_game_id"])
    shares = []
    for team, g in st.groupby("team", sort=False):
        pids = g.player_id.values
        for i in range(len(pids)):
            window = pids[max(0, i - 20):i]
            shares.append(float(np.mean(window == pids[i])) if len(window) else np.nan)
    st["g_share"] = shares
    return st.drop_duplicates(["game_id", "team"])[["game_id", "team", "g_days", "g_starts7", "g_share"]]


def venue_and_travel(conn) -> pd.DataFrame:
    cols = ["nhl_game_id", "game_id", "team", "opponent", "game_date", "is_home", "goals_for",
            "goals_against", "season"]
    t = pd.DataFrame(conn.execute(f"SELECT {', '.join(cols)} FROM nhl_team_game_log").fetchall(),
                     columns=cols)
    t["game_date"] = pd.to_datetime(t.game_date)
    t[["goals_for", "goals_against"]] = t[["goals_for", "goals_against"]].apply(pd.to_numeric, errors="coerce")
    t = t.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    t["gd"] = (t.goals_for - t.goals_against).clip(-4, 4)
    t["venue"] = np.where(t.is_home == 1, t.team, t.opponent)
    out = []
    for team, g in t.groupby("team", sort=False):
        g = g.copy()
        home_gd = g.gd.where(g.is_home == 1)
        road_gd = g.gd.where(g.is_home == 0)
        # EWMA over prior home (road) games only, carried forward to every row
        g["home_gd"] = home_gd.shift(1).ewm(halflife=40, min_periods=10, ignore_na=True).mean().ffill()
        g["road_gd"] = road_gd.shift(1).ewm(halflife=40, min_periods=10, ignore_na=True).mean().ffill()
        v = g.venue.values
        km, tz = [np.nan], [np.nan]
        for i in range(1, len(v)):
            a, b = ARENA.get(v[i - 1]), ARENA.get(v[i])
            if a is None or b is None:
                km.append(np.nan)
                tz.append(np.nan)
                continue
            la1, lo1, la2, lo2 = map(radians, (a[0], a[1], b[0], b[1]))
            h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
            km.append(2 * 6371 * asin(sqrt(h)))
            tz.append(b[2] - a[2])
        g["travel_km"], g["tz_shift"] = km, tz
        new_season = g.season.ne(g.season.shift(1))
        g.loc[new_season, ["travel_km", "tz_shift"]] = 0.0
        out.append(g)
    t = pd.concat(out)
    return t[["game_id", "team", "home_gd", "road_gd", "travel_km", "tz_shift"]]


def lineup(conn) -> pd.DataFrame:
    """Within a season only: a summer's roster turnover is not an absence. The
    first five games of a team's season read as a full lineup (share 1, nothing
    missing) -- unknown, so neutral."""
    cols = ["game_id", "team", "player_id", "game_date", "toi_seconds", "points", "season"]
    s = pd.DataFrame(conn.execute(f"SELECT {', '.join(cols)} FROM nhl_skater_game_log").fetchall(),
                     columns=cols)
    s["game_date"] = pd.to_datetime(s.game_date)
    s[["toi_seconds", "points"]] = s[["toi_seconds", "points"]].apply(pd.to_numeric, errors="coerce").fillna(0)
    rows = []
    for (team, _season), g in s.groupby(["team", "season"], sort=False):
        games = g[["game_id", "game_date"]].drop_duplicates().sort_values(["game_date", "game_id"])
        gid_idx = {gid: i for i, gid in enumerate(games.game_id)}
        pids = sorted(g.player_id.unique())
        pid_idx = {p: j for j, p in enumerate(pids)}
        toi = np.zeros((len(games), len(pids)))
        pts = np.zeros((len(games), len(pids)))
        gi = g.game_id.map(gid_idx).values
        pj = g.player_id.map(pid_idx).values
        toi[gi, pj] = g.toi_seconds.values
        pts[gi, pj] = g.points.values
        dressed = toi > 0
        for i, gid in enumerate(games.game_id):
            if i < 5:
                rows.append((gid, team, 1.0, 0.0))
                continue
            w = slice(max(0, i - 20), i)
            tot = toi[w].sum(axis=0)
            recent = dressed[max(0, i - 10):i].any(axis=0)
            cand = np.where(recent & (tot > 0))[0]
            reg = cand[np.argsort(-tot[cand])[:18]]
            gp = dressed[w][:, reg].sum(axis=0)
            avg = tot[reg] / np.maximum(gp, 1)
            here = dressed[i, reg]
            share = float(avg[here].sum() / avg.sum()) if avg.sum() > 0 else np.nan
            ppg = pts[w][:, reg].sum(axis=0) / np.maximum(gp, 1)
            rows.append((gid, team, share, float(ppg[~here].sum())))
    return pd.DataFrame(rows, columns=["game_id", "team", "lineup_share", "missing_ppg"])


def best_prices(conn, seasons: list[int]) -> pd.DataFrame:
    """Best bettable moneyline per side, from the SAME snapshot as DraftKings'
    first game-day quote (comparing quotes taken at different times manufactures
    an edge -- docs/nhl_market_lab.md, the "best price against Pinnacle" test)."""
    import config
    from scripts.nhl_market_lab3 import FEED, _ts
    books = list(config.BEST_LINE_BOOKMAKERS)
    games = conn.execute(
        "SELECT game_id, commence_time FROM games WHERE sport = 'NHL' AND season = ANY(%s) "
        "AND home_score IS NOT NULL AND commence_time IS NOT NULL", (seasons,)).fetchall()
    start = {g: _ts(t) for g, t in games}
    ids = list(start)
    rows = []
    for i in range(0, len(ids), 300):
        rows += conn.execute(
            "SELECT game_id, bookmaker, snapshot_at, home_price, away_price FROM odds "
            "WHERE game_id = ANY(%s) AND source = %s AND snapshot_type = 'open' "
            "AND bookmaker = ANY(%s) AND market = 'h2h'",
            (ids[i:i + 300], FEED, books)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "snap", "hp", "ap"])
    px["snap"] = px.snap.map(_ts)
    px = px[[s <= start[g] for g, s in zip(px.game_id, px.snap)]]
    px[["hp", "ap"]] = px[["hp", "ap"]].apply(pd.to_numeric, errors="coerce")
    dk_first = px[px.book == "draftkings"].groupby("game_id").snap.min().rename("dk_snap")
    px = px.merge(dk_first, on="game_id")
    same = px[px.snap == px.dk_snap]
    out = same.groupby("game_id").agg(best_home=("hp", "max"), best_away=("ap", "max"),
                                      books_at_snap=("book", "nunique")).reset_index()
    return out


def load() -> pd.DataFrame:
    def _go():
        conn = get_connection()
        try:
            _db_quiet(conn, "game logs")
            df = build(conn, with_prices=False)
            _db_quiet(conn, "goalie workload")
            wl = goalie_workload(conn)
            _db_quiet(conn, "venue and travel")
            vt = venue_and_travel(conn)
            _db_quiet(conn, "skater logs")
            lu = lineup(conn)
            _db_quiet(conn, "prices")
            px = feed_prices(conn, PRICED_SEASONS)
        finally:
            conn.close()
        return df, wl, vt, lu, px

    df, wl, vt, lu, px = _cached("inputs_v1", _go)
    side = wl.merge(vt, on=["game_id", "team"], how="outer").merge(lu, on=["game_id", "team"], how="outer")
    df = df.merge(side.rename(columns=lambda c: c if c in ("game_id", "team") else f"h_{c}"),
                  left_on=["game_id", "home"], right_on=["game_id", "team"], how="left").drop(columns="team")
    df = df.merge(side.rename(columns=lambda c: c if c in ("game_id", "team") else f"a_{c}"),
                  left_on=["game_id", "away"], right_on=["game_id", "team"], how="left").drop(columns="team")
    df = df.merge(px, on="game_id", how="left")

    def _best():
        conn = get_connection()
        try:
            _db_quiet(conn, "best prices")
            return best_prices(conn, PRICED_SEASONS)
        finally:
            conn.close()

    df = df.merge(_cached("best_prices_v1", _best), on="game_id", how="left")
    df["y"] = (df.hs > df.as_).astype(int)
    for b in ("dra", "pin"):
        df[f"{b}_mkt_home"] = _nv(df, f"{b}_ml_home_open", f"{b}_ml_away_open")
    df["pin_close_home"] = _nv(df, "pin_ml_home_close", "pin_ml_away_close")
    df["mkt_logit"] = np.log(df.dra_mkt_home / (1 - df.dra_mkt_home))
    return df


# ── models ───────────────────────────────────────────────────────────────────

def _logit(C):
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=3000))


class OffsetLogit:
    """L2 logistic regression around a fixed offset (the market's log-odds).
    The offset is NOT penalised: the inputs can only move the market's number,
    and with no signal they shrink to it -- unlike the market as a penalised
    input, which a strong penalty shrinks away from."""

    def __init__(self, C: float):
        self.lam = 1.0 / (2.0 * C)

    def fit(self, X, y, offset):
        from scipy.optimize import minimize
        self.mu, self.sd = X.mean(axis=0), X.std(axis=0) + 1e-9
        Z = (X - self.mu) / self.sd
        n, k = Z.shape

        def f(w):
            eta = offset + w[0] + Z @ w[1:]
            ll = np.logaddexp(0, eta) - y * eta
            g = 1 / (1 + np.exp(-eta)) - y
            grad = np.r_[g.mean(), Z.T @ g / n] + np.r_[0.0, 2 * self.lam * w[1:] / n]
            return ll.mean() + self.lam * (w[1:] ** 2).sum() / n, grad

        self.w = minimize(f, np.zeros(k + 1), jac=True, method="L-BFGS-B").x
        return self

    def predict_proba(self, X, offset):
        Z = (X - self.mu) / self.sd
        p = 1 / (1 + np.exp(-(offset + self.w[0] + Z @ self.w[1:])))
        return np.c_[1 - p, p]


def _choose_C(tr: pd.DataFrame, feats: list[str], offset: bool) -> float:
    """The penalty is chosen on the training seasons only: each of the last
    three is scored by a fit on the seasons before it, and the mean log loss
    decides. One validation season picked C=0.3 for 2025-26 and overfit."""
    seasons = sorted(tr.season.unique())
    vals = [v for v in seasons[-3:] if len(tr[tr.season < v]) >= 800]
    if not vals:
        return C_GRID[0]
    scores = {}
    for C in C_GRID:
        lls = []
        for v in vals:
            a, b = tr[tr.season < v], tr[tr.season == v]
            if offset:
                m = OffsetLogit(C).fit(a[feats].values.astype(float), a.y.values, a.mkt_logit.values)
                p = m.predict_proba(b[feats].values.astype(float), b.mkt_logit.values)[:, 1]
            else:
                m = _logit(C).fit(a[feats].values.astype(float), a.y.values.astype(int))
                p = m.predict_proba(b[feats].values.astype(float))[:, 1]
            lls.append(log_loss(b.y.values, p))
        scores[C] = float(np.mean(lls))
    return min(scores, key=scores.get)


def walk(df: pd.DataFrame, feats: list[str], kind: str = "logit", seasons=TEST_SEASONS,
         min_season: int = 2019) -> pd.DataFrame:
    need = feats + ["y"] + (["mkt_logit"] if kind == "offset" else [])
    use = df[df.season >= min_season].dropna(subset=need)
    parts = []
    for test in seasons:
        tr, te = use[use.season < test], use[use.season == test].copy()
        if len(tr) < 800 or te.empty:
            continue
        X, y = tr[feats].values.astype(float), tr.y.values.astype(int)
        if kind == "logit":
            C = _choose_C(tr, feats, offset=False)
            m = _logit(C).fit(X, y)
            te["C"] = C
            te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
        elif kind == "offset":
            C = _choose_C(tr, feats, offset=True)
            m = OffsetLogit(C).fit(X, y.astype(float), tr.mkt_logit.values)
            te["C"] = C
            te["p"] = m.predict_proba(te[feats].values.astype(float), te.mkt_logit.values)[:, 1]
        else:
            m = XGBClassifier(**TREE).fit(X, y)
            te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
        parts.append(te)
    return pd.concat(parts) if parts else pd.DataFrame()


# ── grading ──────────────────────────────────────────────────────────────────

def accuracy(name: str, pred: pd.DataFrame) -> dict:
    s = pred.dropna(subset=["dra_mkt_home", "pin_mkt_home"])
    y = s.y.values
    out = {"model": name, "games": len(s),
           "log loss": round(log_loss(y, s.p), 5),
           "DK no-vig": round(log_loss(y, s.dra_mkt_home), 5),
           "Pinnacle no-vig": round(log_loss(y, s.pin_mkt_home), 5),
           "AUC": round(roc_auc_score(y, s.p), 4),
           "AUC DK": round(roc_auc_score(y, s.dra_mkt_home), 4)}
    d = -(y * np.log(s.p) + (1 - y) * np.log(1 - s.p)) + (y * np.log(s.dra_mkt_home) + (1 - y) * np.log(1 - s.dra_mkt_home))
    se = d.std(ddof=1) / np.sqrt(len(d))
    out["model - DK"] = f"{d.mean():+.5f} ({d.mean() - 1.96 * se:+.5f}..{d.mean() + 1.96 * se:+.5f})"
    return out


def bets(pred: pd.DataFrame, cut: float, at: str = "dk") -> pd.DataFrame:
    """One bet per game on the side with the higher EV, if it clears `cut`;
    decided and graded at DraftKings' first game-day price (`at="dk"`) or at the
    best bettable book's price in that same snapshot (`at="best"`)."""
    hcol, acol = ("dra_ml_home_open", "dra_ml_away_open") if at == "dk" else ("best_home", "best_away")
    s = pred.dropna(subset=[hcol, acol, "pin_mkt_home", "pin_close_home"]).copy()
    ev_h = s.p * (1 + s[hcol].map(win_per_unit)) - 1
    ev_a = (1 - s.p) * (1 + s[acol].map(win_per_unit)) - 1
    home = (ev_h >= cut) & (ev_h >= ev_a)
    away = (ev_a >= cut) & (ev_a > ev_h)
    s = s[home | away].copy()
    h = home[home | away].values
    s["side_home"] = h
    s["price"] = np.where(h, s[hcol], s[acol])
    won = np.where(h, s.hs > s.as_, s.as_ > s.hs)
    s["profit"] = np.where(won, s.price.map(win_per_unit), -1.0)
    s["clv"] = np.where(h, s.pin_close_home - s.pin_mkt_home, s.pin_mkt_home - s.pin_close_home)
    return s


def bet_grid(name: str, pred: pd.DataFrame, at: str = "dk") -> list[dict]:
    rows = []
    for c in EV_CUTS:
        b = bets(pred, c, at)
        if len(b) < 30:
            rows.append({"model": name, "EV>=": c, "bets": len(b)})
            continue
        order = np.argsort(b.game_date.values, kind="stable")
        half = len(order) // 2
        per = {f"{s}": f"{b[b.season == s].profit.mean() * 100:+.1f} ({int((b.season == s).sum())})"
               for s in sorted(b.season.unique())}
        rows.append({"model": name, "EV>=": c, **summarise(b.profit.values, b.clv.values),
                     "early": round(float(b.profit.values[order[:half]].mean()) * 100, 1),
                     "late": round(float(b.profit.values[order[half:]].mean()) * 100, 1),
                     "dogs": round(float((b.price > 0).mean()), 2), **per})
    return rows


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def per_season(name: str, pred: pd.DataFrame) -> list[dict]:
    rows = []
    for season, g in pred.dropna(subset=["dra_mkt_home"]).groupby("season"):
        y = g.y.values
        rows.append({"model": name, "season": int(season), "games": len(g),
                     "log loss": round(log_loss(y, g.p), 4), "DK no-vig": round(log_loss(y, g.dra_mkt_home), 4),
                     "model - DK": round(log_loss(y, g.p) - log_loss(y, g.dra_mkt_home), 4),
                     "C": g.C.iloc[0] if "C" in g else None})
    return rows


def main() -> None:
    df = load()
    lab = [f for g in LAB_GROUPS.values() for f in g]
    full = [f for g in GROUPS.values() for f in g]
    print(f"games with inputs: {len(df):,}; with a DraftKings game-day quote: {int(df.dra_mkt_home.notna().sum()):,}; "
          f"with a best bettable price in the same snapshot: {int(df.best_home.notna().sum()):,}")
    print("rows with every input, by season:", df.dropna(subset=full).groupby("season").size().to_dict())

    runs = {
        "market only (DraftKings no-vig, no model)": None,
        "round-two inputs, logistic": walk(df, lab),
        "ALL inputs, logistic": walk(df, full),
        "ALL inputs, regularised trees": walk(df, full, kind="xgb"),
        "market + ALL inputs (market as offset)": walk(df, full, kind="offset", seasons=TEST_SEASONS[1:],
                                                        min_season=2021),
    }
    common = set.intersection(*[set(p.game_id) for p in runs.values() if p is not None])
    acc, seas, grid_dk, grid_best = [], [], [], []
    for name, pred in runs.items():
        if pred is None:
            base = runs["ALL inputs, logistic"]
            pred = base.assign(p=base.dra_mkt_home)
        pred = pred[pred.game_id.isin(common)]
        acc.append(accuracy(name, pred))
        if "market only" in name:
            continue
        seas += per_season(name, pred)
        grid_dk += bet_grid(name, pred, "dk")
        if "trees" not in name:
            grid_best += bet_grid(name, pred, "best")
    show(f"Accuracy on the same {len(common):,} games (2021-22 .. 2025-26; lower log loss is better)", acc)
    show("Accuracy by season (the penalty C is chosen on earlier seasons only)", seas)
    show("Bets decided and graded at DraftKings' game-day price: EV cut on the model's own probability "
         "(units, ROI %, CI, CLV in no-vig points vs Pinnacle's close, per-season ROI (bets))", grid_dk)
    show("Bets decided and graded at the BEST bettable price in the same snapshot", grid_best)

    base = runs["ALL inputs, logistic"]
    base = base[base.game_id.isin(common)]
    rows = []
    for g, cols in GROUPS.items():
        pred = walk(df, [f for f in full if f not in cols])
        pred = pred[pred.game_id.isin(common)]
        merged = base[["game_id", "p"]].merge(pred[["game_id", "p", "y"]], on="game_id", suffixes=("_all", "_minus"))
        y = merged.y.values
        l_all = -(y * np.log(merged.p_all) + (1 - y) * np.log(1 - merged.p_all))
        l_min = -(y * np.log(merged.p_minus) + (1 - y) * np.log(1 - merged.p_minus))
        d = l_min - l_all
        se = d.std(ddof=1) / np.sqrt(len(d))
        b = bets(pred, 0.06, "best")
        rows.append({"without": g, "inputs removed": len(cols),
                     "log loss change": f"{d.mean():+.5f} ({d.mean() - 1.96 * se:+.5f}..{d.mean() + 1.96 * se:+.5f})",
                     **{f"best EV>=0.06 {k}": v for k, v in summarise(b.profit.values, b.clv.values).items()}})
    show("Ablation: ALL inputs minus one group (positive log loss change = the group helps)", rows)

    live_frame = os.environ.get(
        "NHL_LIVE_FRAME_2026",
        r"C:/Users/micha/AppData/Local/Temp/nhl_rest_candidate/cache_frame_nhl_moneyline_2026_newlist.pkl")
    if os.path.exists(live_frame):
        with open(live_frame, "rb") as fh:
            lf = pickle.load(fh)
        lf = lf[0] if isinstance(lf, tuple) else lf
        with open(os.path.join("models", "saved", "nhl_moneyline_20260920_131606.pkl"), "rb") as fh:
            art = pickle.load(fh)
        lf = lf.assign(p_live=art["model"].predict_proba(lf[art["feature_cols"]].values.astype(float))[:, 1])
        acc26, grid26 = [], []
        base26 = runs["ALL inputs, logistic"]
        base26 = base26[base26.season == 2026].merge(lf[["game_id", "p_live"]], on="game_id")
        live = base26.assign(p=base26.p_live)
        acc26.append(accuracy("LIVE model 20260920_131606", live))
        for at in ("dk", "best"):
            grid26 += bet_grid(f"LIVE model, own probability @{at}", live, at)
        for name in ("ALL inputs, logistic", "market + ALL inputs (market as offset)"):
            pred = runs[name]
            pred = pred[pred.season == 2026].merge(lf[["game_id"]], on="game_id")
            acc26.append(accuracy(name, pred))
            for at in ("dk", "best"):
                grid26 += bet_grid(f"{name} @{at}", pred, at)
        show("2025-26 only, same games: the live model against the rebuild", acc26)
        show("2025-26 only: bets", grid26)

    with open(os.path.join(CACHE, "predictions_v2.pkl"), "wb") as fh:
        pickle.dump({k: v for k, v in runs.items() if v is not None}, fh)


if __name__ == "__main__":
    main()
