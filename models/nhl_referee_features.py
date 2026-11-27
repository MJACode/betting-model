"""Point-in-time NHL referee features for the full-game total.

The live total (`nhl_over_under`) is a rule: Pinnacle's no-vig price against a
bettable book in the same fetch. These features do not enter that rule unless
`models.nhl_totals_market.USE_NHL_REF_FEATURES` is on, and that flag ships
off. The only thing that fits them is
`scripts/nhl_totals_referee_backtest.py`.

Each feature is a crew mean. For one referee, at one game, it uses only games
whose commence time is strictly earlier (a referee does not work two games on
the same date in the stored officials, measured with the backtest; games that
share a commence time still do not see each other). The rate is shrunk toward
the league mean of those earlier games:

    (n * ref_mean + K * league_mean) / (n + K) - league_mean

which is 0 when the referee has no earlier game, and 0 when the crew is at
the league mean. K is 50 games, the same prior weight the NBA crew study used.
There is no intercept in the headline model: a crew at the league mean leaves
Pinnacle's probability where it was.

Penalties are `times_shorthanded` summed across both teams (penalties that
left a team shorthanded). The team log has no raw penalty-event count.
Power-play opportunities are both teams' `pp_opportunities`, summed.
The backtest passes the scoreboard total as goals, because
`nhl_team_game_log.goals_for` omits the shootout goal the total counts.
All three enter the model as deviations from the league mean, because the
total's price already carries the league scoring level.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

REF_K = 50.0
FEATURES = ("ref_goals_dev", "ref_pp_dev", "ref_pen_dev")
# Chosen on each training fold's own time split. Not a test-season search.
C_GRID = (0.1, 1.0, 10.0)
DEFAULT_C = 1.0
STAT_COLS = ("goals", "pp_opp", "penalties")
_DEV_NAME = {
    "goals": "goals_dev", "pp_opp": "pp_dev", "penalties": "pen_dev", "pim": "pim_dev",
}


def shrunk_deviation(stat_sum: float, n: float, league_mean: float, k: float = REF_K) -> float:
    """Shrunk rate minus the league mean. 0 when there is no history."""
    if n is None or league_mean is None:
        return 0.0
    n = float(n)
    league_mean = float(league_mean)
    if n <= 0 or not math.isfinite(n) or not math.isfinite(league_mean):
        return 0.0
    return (float(stat_sum) + k * league_mean) / (n + k) - league_mean


def season_folds(seasons) -> list[tuple[list[int], int]]:
    """Expanding walk-forward: each season is tested on every earlier season only."""
    ordered = sorted({int(s) for s in seasons})
    return [(ordered[:i], ordered[i]) for i in range(1, len(ordered))]


def flat_profit(total, line, side: str, price) -> float:
    """One unit risked at the American price. Push is 0. The totals lab's grade."""
    total = float(total)
    line = float(line)
    if total == line:
        return 0.0
    won = total > line if side == "over" else total < line
    if not won:
        return -1.0
    price = float(price)
    if price > 0:
        return price / 100.0
    return 100.0 / abs(price)


def select_first_plus_ev(long: pd.DataFrame, min_ev: float) -> pd.DataFrame:
    """The totals lab's first hit, one bet a game.

    `long` is already restricted to a coherent same-number pair in one fetch,
    a bettable book, and a price at or above the floor. Among rows with
    EV >= min_ev, the earliest snapshot wins; inside that snapshot the highest
    EV; an exact EV tie goes to the earlier book (`book_ord`), then over
    before under. The lab's own sort broke EV ties by row order. This order
    is deterministic and both arms of the backtest use it.
    """
    if long.empty:
        return long.copy()
    b = long[long["ev"] >= min_ev].copy()
    if b.empty:
        return b
    b["_side"] = np.where(b["side"].to_numpy() == "over", 0, 1)
    b = b.sort_values(
        ["game_id", "snap_t", "ev", "book_ord", "_side"],
        ascending=[True, True, False, True, True],
        kind="mergesort",
    )
    return b.drop_duplicates("game_id", keep="first").drop(columns="_side").reset_index(drop=True)


def build_referee_features(
    games: pd.DataFrame,
    officials: pd.DataFrame,
    *,
    k: float = REF_K,
    role: str = "referee",
    prefix: str | None = None,
    stat_cols: tuple[str, ...] = STAT_COLS,
) -> pd.DataFrame:
    """One row per game. Deviations use only strictly earlier commence times.

    `games` needs game_id, commence_time, and the stat columns. Games with a
    missing stat or commence time are dropped from the history and from the
    output. `officials` needs game_id, role, full_name.
    """
    prefix = prefix or ("ref" if role == "referee" else role[:3])
    dev_cols = [f"{prefix}_{_DEV_NAME[c]}" for c in stat_cols]
    empty_cols = ["game_id", *dev_cols, f"{prefix}_n_mean", f"{prefix}_n"]
    g = games[["game_id", "commence_time", *stat_cols]].copy()
    g["commence_time"] = pd.to_datetime(g["commence_time"], utc=True, errors="coerce")
    g = g.dropna(subset=["commence_time", *stat_cols]).drop_duplicates("game_id")
    if g.empty:
        return pd.DataFrame(columns=empty_cols)
    g = g.sort_values(["commence_time", "game_id"])

    bucket = g.groupby("commence_time", sort=True)
    league = bucket[list(stat_cols)].sum()
    league["n"] = bucket.size()
    prior_n = league["n"].cumsum().shift(1)
    league_mean = league[list(stat_cols)].cumsum().shift(1).div(prior_n, axis=0)
    league_mean.columns = [f"league_{c}" for c in stat_cols]
    league_mean["league_n"] = prior_n
    league_mean = league_mean.reset_index()

    off = officials.loc[officials["role"] == role, ["game_id", "full_name"]].copy()
    off["full_name"] = off["full_name"].astype(str).str.strip()
    off = off[off["full_name"] != ""].drop_duplicates(["game_id", "full_name"])
    x = off.merge(g, on="game_id", how="inner")
    if x.empty:
        out = g[["game_id"]].copy()
        for c in dev_cols:
            out[c] = np.nan
        out[f"{prefix}_n_mean"] = np.nan
        out[f"{prefix}_n"] = 0
        return out

    person = (
        x.groupby(["full_name", "commence_time"], sort=True)[list(stat_cols)]
        .sum()
        .join(x.groupby(["full_name", "commence_time"], sort=True).size().rename("n"))
        .reset_index()
        .sort_values(["full_name", "commence_time"])
    )
    grp = person.groupby("full_name", sort=False)
    for c in stat_cols:
        person[f"ps_{c}"] = grp[c].cumsum() - person[c]
    person["pn"] = grp["n"].cumsum() - person["n"]
    person = person.merge(league_mean, on="commence_time", how="left")
    for c in stat_cols:
        lm = person[f"league_{c}"]
        pn = person["pn"].astype(float)
        ps = person[f"ps_{c}"].astype(float)
        league_n = person["league_n"].fillna(0).astype(float)
        dev = (ps + k * lm) / (pn + k) - lm
        dev = dev.where((pn > 0) & (league_n > 0) & lm.notna(), 0.0)
        person[f"dev_{c}"] = dev.fillna(0.0).astype(float)

    dev_src = [f"dev_{c}" for c in stat_cols]
    x = x.merge(
        person[["full_name", "commence_time", "pn", *dev_src]],
        on=["full_name", "commence_time"],
        how="left",
    )
    named = {f"dev_{c}": f"{prefix}_{_DEV_NAME[c]}" for c in stat_cols}
    crew = x.groupby("game_id", sort=False)[dev_src].mean().rename(columns=named)
    crew[f"{prefix}_n_mean"] = x.groupby("game_id", sort=False)["pn"].mean()
    crew[f"{prefix}_n"] = x.groupby("game_id", sort=False).size()
    out = g[["game_id"]].merge(crew, on="game_id", how="left")
    out[f"{prefix}_n"] = out[f"{prefix}_n"].fillna(0).astype(int)
    return out


class RefTotalsModel:
    """L2 logistic shift of a market log-odds. No intercept unless asked.

    The offset is the market's log-odds and is not a coefficient. Features are
    divided by their training standard deviation so the penalty treats a goal
    and a power play on one scale, and they are NOT recentered: a deviation of
    0 (a crew at the league mean, or a referee with no earlier game) leaves
    the market probability exactly where it was. Recentering would have turned
    that zero into a constant shift. The intercept, when on, is unpenalised,
    so a control can separate "recalibrate Pinnacle" from "the crew moved it".
    """

    def __init__(self, C: float = DEFAULT_C, intercept: bool = False, features=FEATURES):
        self.C = float(C)
        self.lam = 1.0 / (2.0 * self.C)
        self.intercept = bool(intercept)
        self.features = tuple(features)
        self.w = None
        self.mu = None
        self.sd = None

    def fit(self, X, y, offset):
        from scipy.optimize import minimize

        X = np.asarray(X, float)
        y = np.asarray(y, float)
        offset = np.asarray(offset, float)
        # Scale only. Do not subtract the mean: raw 0 must stay a zero shift.
        self.mu = np.zeros(X.shape[1], dtype=float)
        self.sd = X.std(axis=0) + 1e-9
        Z = X / self.sd
        n, k = Z.shape

        def objective(w):
            if self.intercept:
                eta = offset + w[0] + Z @ w[1:]
                pen_w = w[1:]
            else:
                eta = offset + Z @ w
                pen_w = w
            ll = np.logaddexp(0.0, eta) - y * eta
            g = 1.0 / (1.0 + np.exp(-np.clip(eta, -60, 60))) - y
            if self.intercept:
                grad = np.r_[g.mean(), Z.T @ g / n]
                grad[1:] += 2.0 * self.lam * pen_w / n
            else:
                grad = Z.T @ g / n + 2.0 * self.lam * pen_w / n
            return float(ll.mean() + self.lam * np.dot(pen_w, pen_w) / n), grad

        w0 = np.zeros(k + (1 if self.intercept else 0))
        res = minimize(objective, w0, jac=True, method="L-BFGS-B")
        if not res.success:
            raise RuntimeError(f"referee logit did not converge: {res.message}")
        self.w = res.x
        return self

    def _eta(self, X, offset) -> np.ndarray:
        Z = np.asarray(X, float) / self.sd
        offset = np.asarray(offset, float)
        if self.intercept:
            return offset + self.w[0] + Z @ self.w[1:]
        return offset + Z @ self.w

    def predict_over(self, X, offset) -> np.ndarray:
        eta = np.clip(self._eta(X, offset), -60, 60)
        return 1.0 / (1.0 + np.exp(-eta))

    def adjust_over(self, p_over, features) -> float | None:
        """Market over-probability moved by this fit. None if it cannot be priced."""
        if self.w is None or p_over is None:
            return None
        p = float(p_over)
        if not math.isfinite(p) or not (0.0 < p < 1.0):
            return None
        try:
            row = [float(features[c]) for c in self.features]
        except (KeyError, TypeError, ValueError):
            return None
        if not np.isfinite(row).all():
            return None
        off = math.log(p / (1.0 - p))
        out = float(self.predict_over(np.asarray(row, float).reshape(1, -1), np.array([off]))[0])
        if not math.isfinite(out) or not (0.0 < out < 1.0):
            return None
        return out

    def standardized_coefficients(self) -> dict[str, float]:
        """Logit change per training standard deviation of each feature."""
        if self.w is None:
            return {}
        coef = self.w[1:] if self.intercept else self.w
        return {name: float(c) for name, c in zip(self.features, coef)}


def market_logit(p) -> np.ndarray:
    p = np.clip(np.asarray(p, float), 1e-6, 1.0 - 1e-6)
    return np.log(p / (1.0 - p))


def log_loss(y, p) -> float:
    p = np.clip(np.asarray(p, float), 1e-12, 1.0 - 1e-12)
    y = np.asarray(y, float)
    return float(-np.mean(y * np.log(p) + (1.0 - y) * np.log(1.0 - p)))


def choose_c(train: pd.DataFrame, feats, *, intercept: bool = False) -> float:
    """Penalty from the last quarter of the training rows, by time. Never the test season."""
    ordered = train.sort_values(["commence_time", "game_id"])
    cut = int(len(ordered) * 0.75)
    if cut < 200 or len(ordered) - cut < 80:
        return DEFAULT_C
    early, late = ordered.iloc[:cut], ordered.iloc[cut:]
    scores = {}
    for C in C_GRID:
        model = RefTotalsModel(C=C, intercept=intercept, features=feats).fit(
            early[list(feats)].to_numpy(), early["y"].to_numpy(), early["offset"].to_numpy(),
        )
        pred = model.predict_over(late[list(feats)].to_numpy(), late["offset"].to_numpy())
        scores[C] = log_loss(late["y"].to_numpy(), pred)
    return min(scores, key=scores.get)
