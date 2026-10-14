"""nhl_moneyline, rebuilt: DraftKings' game-day price, moved by what the logs say.

mike, 2026-10-13: "Look at and rebuild the money line model." The evidence is
docs/nhl_moneyline_rebuild.md: walk-forward over 2021-22 -> 2025-26 at the
bought game-day prices, this model returns +4.55% on 2,415 bets at EV 0.04 and
+5.46% on 1,567 at EV 0.06 at the best bettable price, beating Pinnacle's close
about 64% of the time; taking the favourite blind on the same games loses 2.2%.

THE MODEL. An L2 logistic regression whose OFFSET is DraftKings' no-vig
log-odds for the home side, unpenalised: the inputs can only move the market's
number, and with no signal they shrink back to it (`OffsetLogit`).

THE INPUTS. Every one is built from a team's or goalie's PRIOR games only
(nhl_team_game_log, nhl_goalie_game_log, games), the same code for training
rows and for tonight's games -- `build_inputs`, which takes tonight's games as
rows with no result, so every rolling number at that row is its value going
into the game. Groups (docs/nhl_moneyline_rebuild.md has what each one is
worth): form, shots, special teams, goalie, schedule (rest, back-to-back, road
trip), rating, goalie workload, home ice, travel. NOT lineup: it was graded,
but it reads who dressed, which nobody knows at noon on game day.

THE DECISION. Once, on game day, in the first scoring runs at or after 16:00Z
(DECISION_START_UTC_HOUR) -- the archive's first game-day quote is the 16:00Z
snapshot, which is what the walk-forward decided against -- and only with the
listed starting goalie of both teams (the game-day `nhl_goalie_stats` row). The
grade assumed both. Outside that window the model's number is written as NONE
with the reason, never as a BET.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import asin, cos, radians, sin, sqrt

import numpy as np
import pandas as pd

MODEL_ID = "nhl_moneyline"
KIND = "anchored_logit"
MARKET = "h2h"

HALF_LIFE_LONG, HALF_LIFE_SHORT = 25, 6        # games
GOALIE_HALF_LIFE, GOALIE_PRIOR_SHOTS = 30, 300.0
LEAGUE_GOALS_PER_SHOT_FALLBACK = 0.09          # only the first date in the logs has no history
C_GRID = (0.003, 0.01, 0.03, 0.1, 0.3)
FIRST_PRICED_SEASON = 2021                     # 2020-21: the bought archive's first season
UPCOMING_NHL_GAME_ID = 9_999_999_999           # sorts after every real game on the same date

# The decision window, UTC. 16:00Z is the archive snapshot the walk-forward
# decided against; two hourly scoring runs fit inside it.
DECISION_START_UTC_HOUR = 16
DECISION_END_UTC_HOUR = 18

# Arena latitude, longitude and UTC offset in standard time. A neutral-site
# game is treated as the home team's arena.
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

GROUPS = {
    "form":     ["d_gf_l", "d_ga_l", "d_gf_s", "d_ga_s"],
    "shots":    ["d_sf", "d_sa", "d_sat_share", "d_sh_pct"],
    "special":  ["d_pp_pct", "d_pk_pct", "d_pp_opp", "d_pk_opp", "d_fo"],
    "goalie":   ["d_g_sv", "h_g_starts", "a_g_starts"],
    "schedule": ["h_rest", "a_rest", "h_b2b", "a_b2b", "a_road_trip"],
    "rating":   ["d_rate"],
    "workload": ["h_g_days", "a_g_days", "h_g_starts7", "a_g_starts7", "h_g_share", "a_g_share"],
    "venue":    ["h_home_gd", "a_road_gd"],
    "travel":   ["h_travel_km", "a_travel_km", "h_tz_shift", "a_tz_shift"],
}
FEATURES = [f for g in GROUPS.values() for f in g]

_TEAM_COLS = ["nhl_game_id", "game_id", "team", "opponent", "season", "game_date", "is_home",
              "goals_for", "goals_against", "shots_for", "shots_against", "sat_for_5v5",
              "sat_against_5v5", "pp_opportunities", "pp_goals", "times_shorthanded",
              "pp_goals_against", "faceoff_win_pct"]
_GOALIE_COLS = ["nhl_game_id", "game_id", "team", "player_id", "game_date", "started",
                "shots_against", "goals_against", "toi_seconds"]


# ── data ─────────────────────────────────────────────────────────────────────

def load_logs(conn, before: str | None = None) -> dict:
    """The three tables the inputs are built from. `before` (YYYY-MM-DD) keeps
    only games dated earlier -- the morning-of-game-day view, for checks."""
    cut = " WHERE game_date < %s" if before else ""
    args = (before,) if before else None
    team = pd.DataFrame(conn.execute(
        f"SELECT {', '.join(_TEAM_COLS)} FROM nhl_team_game_log{cut}", args).fetchall(), columns=_TEAM_COLS)
    goalie = pd.DataFrame(conn.execute(
        f"SELECT {', '.join(_GOALIE_COLS)} FROM nhl_goalie_game_log{cut}", args).fetchall(), columns=_GOALIE_COLS)
    games = pd.DataFrame(conn.execute(
        "SELECT game_id, game_date, season, home_team, away_team, home_score, away_score FROM games "
        "WHERE sport = 'NHL' AND home_score IS NOT NULL" + (" AND game_date < %s" if before else ""),
        args).fetchall(), columns=["game_id", "game_date", "season", "home", "away", "hs", "as_"])
    return {"team": team, "goalie": goalie, "games": games}


# ── inputs ───────────────────────────────────────────────────────────────────

def _team_frame(team: pd.DataFrame, upcoming: pd.DataFrame | None) -> pd.DataFrame:
    t = team.copy()
    if upcoming is not None and len(upcoming):
        add = []
        for r in upcoming.itertuples():
            for side, opp, home in ((r.home, r.away, 1), (r.away, r.home, 0)):
                add.append({"nhl_game_id": UPCOMING_NHL_GAME_ID, "game_id": r.game_id, "team": side,
                            "opponent": opp, "season": r.season, "game_date": r.game_date, "is_home": home})
        t = pd.concat([t, pd.DataFrame(add)], ignore_index=True)
    t["nhl_game_id"] = pd.to_numeric(t.nhl_game_id)
    t["game_date"] = pd.to_datetime(t.game_date.astype(str).str[:10])
    t = t.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    for c in _TEAM_COLS[7:]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["is_home"] = pd.to_numeric(t.is_home).astype(int)
    g = t.groupby("team", sort=False)

    def ew(col, hl):                     # rate over PRIOR games only
        return g[col].transform(lambda s: s.shift(1).ewm(halflife=hl, min_periods=5).mean())

    for hl, tag in ((HALF_LIFE_LONG, "l"), (HALF_LIFE_SHORT, "s")):
        t[f"gf_{tag}"], t[f"ga_{tag}"] = ew("goals_for", hl), ew("goals_against", hl)
    t["sf"], t["sa"] = ew("shots_for", HALF_LIFE_LONG), ew("shots_against", HALF_LIFE_LONG)
    satf, sata = ew("sat_for_5v5", HALF_LIFE_LONG), ew("sat_against_5v5", HALF_LIFE_LONG)
    t["sat_share"] = satf / (satf + sata)
    t["pp_pct"] = ew("pp_goals", 40) / ew("pp_opportunities", 40)
    t["pk_pct"] = 1 - ew("pp_goals_against", 40) / ew("times_shorthanded", 40)
    t["pp_opp"], t["pk_opp"] = ew("pp_opportunities", 40), ew("times_shorthanded", 40)
    t["fo"] = ew("faceoff_win_pct", HALF_LIFE_LONG)
    t["sh_pct"] = ew("goals_for", HALF_LIFE_LONG) / t["sf"]
    prev = g["game_date"].shift(1)
    t["rest"] = (t["game_date"] - prev).dt.days.clip(upper=6).fillna(6)
    t["b2b"] = (t["rest"] == 1).astype(int)
    t["road_trip"] = g["is_home"].transform(
        lambda s: (1 - s).groupby((s != s.shift()).cumsum()).cumsum().shift(1).fillna(0))

    # home ice and travel
    t["gd"] = (t.goals_for - t.goals_against).clip(-4, 4)
    t["venue"] = np.where(t.is_home == 1, t.team, t.opponent)
    parts = []
    for _team, gg in t.groupby("team", sort=False):
        gg = gg.copy()
        home_gd = gg.gd.where(gg.is_home == 1)
        road_gd = gg.gd.where(gg.is_home == 0)
        gg["home_gd"] = home_gd.shift(1).ewm(halflife=40, min_periods=10, ignore_na=True).mean().ffill()
        gg["road_gd"] = road_gd.shift(1).ewm(halflife=40, min_periods=10, ignore_na=True).mean().ffill()
        v = gg.venue.values
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
        gg["travel_km"], gg["tz_shift"] = km, tz
        new_season = gg.season.ne(gg.season.shift(1))
        gg.loc[new_season, ["travel_km", "tz_shift"]] = 0.0
        parts.append(gg)
    return pd.concat(parts)


def _goalie_frame(goalie: pd.DataFrame, upcoming: pd.DataFrame | None,
                  last_starter: dict) -> pd.DataFrame:
    gl = goalie.copy()
    if upcoming is not None and len(upcoming):
        add = []
        for r in upcoming.itertuples():
            for side, pid in ((r.home, getattr(r, "home_goalie_id", None)),
                              (r.away, getattr(r, "away_goalie_id", None))):
                if pid is None or (isinstance(pid, float) and np.isnan(pid)):
                    pid = last_starter.get(side)      # placeholder for a NONE row only
                if pid is None:
                    continue
                add.append({"nhl_game_id": UPCOMING_NHL_GAME_ID, "game_id": r.game_id, "team": side,
                            "player_id": pid, "game_date": r.game_date, "started": 1})
        gl = pd.concat([gl, pd.DataFrame(add)], ignore_index=True)
    gl["player_id"] = gl.player_id.astype(str)
    gl["nhl_game_id"] = pd.to_numeric(gl.nhl_game_id)
    gl["started"] = pd.to_numeric(gl.started).fillna(0).astype(int)
    gl["game_date"] = pd.to_datetime(gl.game_date.astype(str).str[:10])
    gl = gl.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    for c in ("shots_against", "goals_against"):
        gl[c] = pd.to_numeric(gl[c], errors="coerce").fillna(0)
    # League goals per shot AS OF each date: every game strictly before it. The
    # research harness (scripts/nhl_market_lab2.goalie_frame) used one rate over
    # all seasons, later ones included -- a look-ahead, and the reason its
    # d_g_sv differed from tonight's scoring in the 4th decimal on 274 of 274
    # served-vs-trained checks. As-of, the two paths agree exactly.
    daily = gl.groupby("game_date")[["goals_against", "shots_against"]].sum().sort_index()
    before = daily.cumsum().shift(1)
    lg_by_date = (before.goals_against / before.shots_against).fillna(LEAGUE_GOALS_PER_SHOT_FALLBACK)
    lg = gl.game_date.map(lg_by_date)
    g = gl.groupby("player_id", sort=False)
    sa = g["shots_against"].transform(lambda s: s.shift(1).ewm(halflife=GOALIE_HALF_LIFE, min_periods=1).sum())
    ga = g["goals_against"].transform(lambda s: s.shift(1).ewm(halflife=GOALIE_HALF_LIFE, min_periods=1).sum())
    k = GOALIE_PRIOR_SHOTS
    gl["g_sv"] = 1 - (ga.fillna(0) + k * lg) / (sa.fillna(0) + k)
    gl["g_starts"] = g.cumcount()
    st = gl[gl.started == 1].drop_duplicates(["game_id", "team"]).copy()

    # workload: this goalie's days since his last start, starts in the 7 days
    # before, and his share of the team's previous 20 starts
    st = st.sort_values(["player_id", "game_date", "nhl_game_id"])
    prev = st.groupby("player_id").game_date.shift(1)
    st["g_days"] = (st.game_date - prev).dt.days.clip(upper=10).fillna(10)
    st["g_starts7"] = 0
    for _pid, gg in st.groupby("player_id", sort=False):
        d = gg.game_date.values
        lo = np.searchsorted(d, d - np.timedelta64(7, "D"), side="left")
        st.loc[gg.index, "g_starts7"] = np.arange(len(d)) - lo
    st = st.sort_values(["team", "game_date", "nhl_game_id"])
    shares = []
    for _team, gg in st.groupby("team", sort=False):
        pids = gg.player_id.values
        for i in range(len(pids)):
            window = pids[max(0, i - 20):i]
            shares.append(float(np.mean(window == pids[i])) if len(window) else np.nan)
    st["g_share"] = shares
    return st[["game_id", "team", "player_id", "g_sv", "g_starts", "g_days", "g_starts7", "g_share"]]


def _add_rating(games: pd.DataFrame) -> pd.DataFrame:
    """A running goal-margin rating, updated AFTER each game (so it is as-of)."""
    rating: dict[str, float] = {}
    out_h, out_a = [], []
    g = games.sort_values(["game_date", "game_id"]).copy()
    for r in g.itertuples():
        h, a = rating.get(r.home, 0.0), rating.get(r.away, 0.0)
        out_h.append(h)
        out_a.append(a)
        if pd.notna(r.hs):
            err = float(np.clip(r.hs - r.as_, -4, 4)) - (h - a + 0.18)
            rating[r.home], rating[r.away] = h + 0.02 * err, a - 0.02 * err
    g["rate_h"], g["rate_a"] = out_h, out_a
    return g


def build_inputs(logs: dict, upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per game with every input, as of the game. `upcoming`: games to
    score (game_id, game_date, season, home, away, home_goalie_id,
    away_goalie_id) -- rows with no result yet. The played games come back too,
    which is the training frame."""
    games = logs["games"].copy()
    games[["hs", "as_"]] = games[["hs", "as_"]].astype(float)
    if upcoming is not None and len(upcoming):
        games = pd.concat([games, upcoming[["game_id", "game_date", "season", "home", "away"]]
                           .assign(hs=np.nan, as_=np.nan)], ignore_index=True)
    games["game_date"] = games.game_date.astype(str).str[:10]

    team_log = logs["team"]
    last_starter = {}
    gl = logs["goalie"]
    if len(gl):
        s = gl[pd.to_numeric(gl.started) == 1].sort_values(["game_date", "nhl_game_id"])
        last_starter = s.groupby("team").player_id.last().to_dict()

    t = _team_frame(team_log, upcoming)
    gk = _goalie_frame(gl, upcoming, last_starter)
    t = t.merge(gk, on=["game_id", "team"], how="left")
    keep = ["game_id", "gf_l", "ga_l", "gf_s", "ga_s", "sf", "sa", "sat_share", "sh_pct",
            "pp_pct", "pk_pct", "pp_opp", "pk_opp", "fo", "rest", "b2b", "road_trip",
            "g_sv", "g_starts", "g_days", "g_starts7", "g_share", "home_gd", "road_gd",
            "travel_km", "tz_shift", "player_id"]
    h = t[t.is_home == 1][keep].add_prefix("h_").rename(columns={"h_game_id": "game_id"})
    a = t[t.is_home == 0][keep].add_prefix("a_").rename(columns={"a_game_id": "game_id"})
    df = _add_rating(games).merge(h, on="game_id").merge(a, on="game_id")
    for c in ("gf_l", "ga_l", "gf_s", "ga_s", "sf", "sa", "sat_share", "sh_pct", "pp_pct",
              "pk_pct", "pp_opp", "pk_opp", "fo", "g_sv"):
        df[f"d_{c}"] = df[f"h_{c}"] - df[f"a_{c}"]
    df["d_rate"] = df.rate_h - df.rate_a
    df["season"] = pd.to_numeric(df.season)
    return df


# ── the model ────────────────────────────────────────────────────────────────

class OffsetLogit:
    """L2 logistic regression around a fixed offset (the market's log-odds).
    The offset is NOT penalised: the inputs can only move the market's number,
    and with no signal they shrink to it -- unlike the market as a penalised
    input, which a strong penalty shrinks away from."""

    def __init__(self, C: float):
        self.C = C
        self.lam = 1.0 / (2.0 * C)

    def fit(self, X, y, offset):
        from scipy.optimize import minimize
        X, y, offset = np.asarray(X, float), np.asarray(y, float), np.asarray(offset, float)
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
        Z = (np.asarray(X, float) - self.mu) / self.sd
        p = 1 / (1 + np.exp(-(np.asarray(offset, float) + self.w[0] + Z @ self.w[1:])))
        return np.c_[1 - p, p]


def market_logit(p_home_novig) -> np.ndarray:
    p = np.asarray(p_home_novig, float)
    return np.log(p / (1 - p))


def _log_loss(y, p) -> float:
    p = np.clip(np.asarray(p, float), 1e-12, 1 - 1e-12)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def choose_C(train: pd.DataFrame, feats: list[str] = FEATURES) -> float:
    """The penalty, chosen on the training seasons only: each of the last three
    is scored by a fit on the seasons before it, mean log loss decides."""
    seasons = sorted(train.season.unique())
    vals = [v for v in seasons[-3:] if len(train[train.season < v]) >= 800]
    if not vals:
        return C_GRID[0]
    scores = {}
    for C in C_GRID:
        lls = []
        for v in vals:
            a, b = train[train.season < v], train[train.season == v]
            m = OffsetLogit(C).fit(a[feats].values, a.y.values, a.mkt_logit.values)
            lls.append(_log_loss(b.y.values, m.predict_proba(b[feats].values, b.mkt_logit.values)[:, 1]))
        scores[C] = float(np.mean(lls))
    return min(scores, key=scores.get)


def fit(train: pd.DataFrame, feats: list[str] = FEATURES) -> tuple[OffsetLogit, float]:
    """Fit on rows carrying every input, the market's log-odds and the result."""
    use = train.dropna(subset=feats + ["mkt_logit", "y"])
    C = choose_C(use, feats)
    return OffsetLogit(C).fit(use[feats].values, use.y.values, use.mkt_logit.values), C


# ── tonight's games ──────────────────────────────────────────────────────────

LOGS_TTL = timedelta(minutes=60)    # the logs gain last night's games once a day (~10:05Z)
_CACHE: dict = {"logs": None, "logs_at": None, "rows": {}}


def listed_goalies(conn, game_ids) -> dict:
    """{(game_id, team): player_id} from the game-day probable-starter rows
    (`nhl_goalie_stats` with the game's id, newest first). A team absent here
    has no listed goalie yet."""
    ids = list(game_ids)
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT game_id, team, player_id FROM nhl_goalie_stats "
        "WHERE game_id = ANY(%s) AND player_id IS NOT NULL ORDER BY created_at DESC", (ids,)).fetchall()
    out: dict = {}
    for gid, team, pid in rows:
        out.setdefault((gid, team), pid)
    return out


def inputs_for_date(conn, game_date: str, now: datetime | None = None) -> tuple[pd.DataFrame, dict]:
    """Every input for the NHL games dated `game_date`, built exactly as the
    training rows are (logs cut to the games before that date), and the listed
    goalies. Built once per (date, listed goalies) per hour of logs."""
    now = now or datetime.now(timezone.utc)
    if _CACHE["logs"] is None or now - _CACHE["logs_at"] > LOGS_TTL:
        _CACHE["logs"], _CACHE["logs_at"], _CACHE["rows"] = load_logs(conn), now, {}
    d = str(game_date)[:10]
    up = pd.DataFrame(conn.execute(
        "SELECT game_id, game_date, season, home_team, away_team FROM games "
        "WHERE sport = 'NHL' AND game_date = %s", (d,)).fetchall(),
        columns=["game_id", "game_date", "season", "home", "away"])
    goalies = listed_goalies(conn, up.game_id)
    up["home_goalie_id"] = [goalies.get((g, h)) for g, h in zip(up.game_id, up.home)]
    up["away_goalie_id"] = [goalies.get((g, a)) for g, a in zip(up.game_id, up.away)]
    key = (d, tuple(sorted((str(g), str(h), str(a)) for g, h, a in
                           zip(up.game_id, up.home_goalie_id, up.away_goalie_id))))
    if key not in _CACHE["rows"]:
        cut = {k: v[v.game_date.astype(str).str[:10] < d] for k, v in _CACHE["logs"].items()}
        built = build_inputs(cut, upcoming=up)
        _CACHE["rows"][key] = built[built.game_id.isin(up.game_id)].set_index("game_id")
    return _CACHE["rows"][key], goalies


# ── the decision window ──────────────────────────────────────────────────────

def decision_window(game_date: str, commence_time: str | None,
                    now: datetime | None = None) -> str | None:
    """None when this run may decide the game; otherwise the reason it may not."""
    now = now or datetime.now(timezone.utc)
    day = datetime.fromisoformat(str(game_date)[:10]).replace(tzinfo=timezone.utc)
    start = day + timedelta(hours=DECISION_START_UTC_HOUR)
    end = day + timedelta(hours=DECISION_END_UTC_HOUR)
    if commence_time:
        ct = datetime.fromisoformat(str(commence_time).replace("Z", "+00:00"))
        if ct.tzinfo is None:
            ct = ct.replace(tzinfo=timezone.utc)
        end = min(end, ct)
    if now < start:
        return "decides on game day from 16:00Z, with both listed goalies"
    if now >= end:
        return "decision window closed (16:00Z-18:00Z on game day, before the start)"
    return None
