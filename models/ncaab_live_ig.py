"""NCAAB in-play game-state model: the pure part (no network, no database, no clock).

The backtest (scripts/ncaab_ingame_search.py) and the live loop
(models/ncaab_live_loop.py) call these functions and nothing else to decide, so
the loop decides a fetch exactly as the grade did (the NBA in-play rule:
docs/sports/nba.md, "In play").

THE MODEL. The NBA IG-2 structure (models/nba_live_ig2.py) on two 20-minute
halves: what is still to come ~ Normal(X b, sqrt(s0 + s1 f + s2 f^2)), f the share of
regulation left, fit by weighted least squares on every 30-second game state
of earlier seasons (walk-forward: a season's model never sees that season).

  margin   final home margin - current margin, on: f x the pre-game margin
           prior, f, current margin x f, and the bonus terms (a team at 7
           team fouls in the half shoots one-and-one, at 10 two shots), each
           weighted by the share of the half left.
  total    final total - current total, on: f x the pre-game total prior, f,
           the points above or below the prior's pace so far x f, the lead's
           size x f (blowouts slow down), the bonus terms, and a late-and-close
           term (the trailing team fouls to stop the clock).

  PRIOR    Pinnacle's last pre-tip spread and total (the home number, as
           stored), else the median of the deciding books' last pre-tip quotes;
           `prior_src` says which.

THE DECISION, per game and rule (a market and a phase), at a fetch:
  STATE     at a quote's stamp (the book's last_update): the last ESPN play
            logged at or before it, ties broken by play order.
  FRESH     no point scored between the quote's stamp and the moment the fetch
            was served. (NBA also pairs every quote with a Pinnacle quote; in
            NCAAB in-play Pinnacle quotes 6 of 26 games at 2026-01-23 00:55Z,
            so the deciding quote's own freshness is the rule. A deviation from
            the NBA rule, named.)
  BAD ROWS  a price strictly between -100 and +100; a spread or total more than
            OUTLIER_PTS from the median of the other books' numbers on the same
            game, market and fetch; a moneyline more than OUTLIER_NOVIG no-vig
            from the others' median.
  PHASES    H1: period 1 live. H2: the halftime break, or period 2 live with at
            least H2_MIN_SECS_LEFT seconds of regulation left. Overtime is in
            neither. A quote's phase is read at its OWN stamp.
  CHOICE    the first fetch holding an eligible quote of the rule's market in
            its phase decides. The side is the one whose best offer has the
            higher model EV; the bet is that side's best-EV offer at one of
            config.BEST_LINE_BOOKMAKERS at the price floor or better, when its
            EV clears the cut. A fetch whose best offer misses the cut SPENDS
            the rule: a later fetch is never used.
  STAKE     one unit to win, risk capped at 3.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

REG_S = 2400.0
HALF_S = 1200.0
GRID_STEP_S = 30
TRAIN_SECS = (60, 2370)            # game seconds gone, regulation
S0_FLOOR = 0.25
BONUS1, BONUS2 = 7, 10             # men's NCAA: one-and-one at the 7th team foul, two at the 10th
H2_MIN_SECS_LEFT = 120
OUTLIER_PTS = 6.0
OUTLIER_NOVIG = 0.25
PRICE_FLOOR = -200.0
MAX_RISK = 3.0
PHASES = ("H1", "H2")
MARKETS = ("spreads", "totals", "h2h")
FOUL_TYPES = ("PersonalFoul", "Technical Foul")

MARGIN_COLS = ("x_mu", "x_f", "x_mf", "x_b1", "x_b2")
TOTAL_COLS = ("y_T", "y_T2", "y_f", "y_f2", "y_pace", "y_lead", "y_b1", "y_b2", "y_late")


# ── game state ───────────────────────────────────────────────────────────────

def with_team_fouls(plays: pd.DataFrame) -> pd.DataFrame:
    """Adds h_tf / a_tf: each team's fouls so far in the current period, after
    each play (one game or many, sorted by game and play order)."""
    p = plays.sort_values(["game_id", "play_no"], kind="stable").copy()
    foul = p["type_text"].isin(FOUL_TYPES)
    key = [p["game_id"], p["period"]]
    p["h_tf"] = (foul & (p["team_side"] == "H")).astype(int).groupby(key).cumsum()
    p["a_tf"] = (foul & (p["team_side"] == "A")).astype(int).groupby(key).cumsum()
    return p


def state_columns(st: pd.DataFrame) -> pd.DataFrame:
    """secs_left, f, half_left, m, t and the break flag from the state's play."""
    period = st["period"].to_numpy(float)
    clock = st["clock_s"].to_numpy(float)
    reg = period <= 2
    secs_left = np.where(reg, clock + HALF_S * (2 - period), 0.0)
    brk = ((st["type_text"] == "End Period") & (period == 1)).to_numpy()
    return st.assign(
        secs_left=secs_left, f=secs_left / REG_S, half_left=np.where(reg, clock / HALF_S, 0.0),
        m=(st["h_pts"] - st["a_pts"]).to_numpy(float),
        t=(st["h_pts"] + st["a_pts"]).to_numpy(float), is_break=brk)


def phase_of(st: pd.DataFrame) -> np.ndarray:
    """'H1' / 'H2' / '' at each state."""
    p = st["period"].to_numpy(float)
    brk = st["is_break"].to_numpy(bool)
    h1 = (p == 1) & ~brk
    h2 = brk | ((p == 2) & (st["secs_left"].to_numpy(float) >= H2_MIN_SECS_LEFT))
    return np.select([h1, h2], ["H1", "H2"], "")


def features(st: pd.DataFrame) -> pd.DataFrame:
    """The model inputs from a state frame carrying f, half_left, m, t, h_tf,
    a_tf, mu_pre (prior home margin) and T_pre (prior total)."""
    f = st["f"].to_numpy(float)
    hl = st["half_left"].to_numpy(float)
    m = st["m"].to_numpy(float)
    t = st["t"].to_numpy(float)
    mu = st["mu_pre"].to_numpy(float)
    T = st["T_pre"].to_numpy(float)
    htf = st["h_tf"].fillna(0).to_numpy(float)
    atf = st["a_tf"].fillna(0).to_numpy(float)
    # the HOME team shoots bonus free throws when the AWAY team is at the count
    home_b1, away_b1 = (atf >= BONUS1).astype(float), (htf >= BONUS1).astype(float)
    home_b2, away_b2 = (atf >= BONUS2).astype(float), (htf >= BONUS2).astype(float)
    secs_left = st["secs_left"].to_numpy(float)
    late = np.clip(1.0 - np.abs(m) / 12.0, 0.0, None) * np.clip(1.0 - secs_left / 300.0, 0.0, 1.0)
    return st.assign(
        x_mu=f * mu, x_f=f, x_mf=m * f,
        x_b1=(home_b1 - away_b1) * hl, x_b2=(home_b2 - away_b2) * hl,
        y_T=f * T, y_T2=f * f * T, y_f=f, y_f2=f * f,
        y_pace=(t - (1.0 - f) * T) * f, y_lead=np.abs(m) * f,
        y_b1=(home_b1 + away_b1) * hl, y_b2=(home_b2 + away_b2) * hl, y_late=late)


@dataclass
class StateModel:
    """What is still to come ~ Normal(X b, sqrt(s0 + s1 f + s2 f^2)), fit on seasons < S."""
    target: str                       # "margin" | "total"
    cols: tuple = ()
    beta: np.ndarray | None = None
    s1: float = 0.0
    s0: float = 0.0
    s2: float = 0.0
    S: int = 0
    n_train: int = 0

    def __post_init__(self):
        if not self.cols:
            self.cols = MARGIN_COLS if self.target == "margin" else TOTAL_COLS

    def _y(self, df: pd.DataFrame) -> np.ndarray:
        if self.target == "margin":
            return (df["final_margin"] - df["m"]).to_numpy(float)
        return (df["final_total"] - df["t"]).to_numpy(float)

    def fit(self, train: pd.DataFrame, S: int) -> "StateModel":
        seasons = set(int(s) for s in train["season"].unique())
        if any(s >= S for s in seasons):
            raise ValueError(f"walk-forward: a season-{S} model cannot see {sorted(seasons)}")
        X = train[list(self.cols)].to_numpy(float)
        y = self._y(train)
        f = train["f"].to_numpy(float)
        w = 1.0 / np.maximum(f, 1e-3)
        for _ in range(3):
            sw = np.sqrt(w)
            self.beta = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
            r2 = (y - X @ self.beta) ** 2
            A = np.column_stack([f, f * f, np.ones_like(f)])
            s1, s2, s0 = np.linalg.lstsq(A, r2, rcond=None)[0]
            self.s1, self.s2, self.s0 = float(s1), float(s2), max(float(s0), S0_FLOOR)
            w = 1.0 / self.var(f)
        self.S, self.n_train = int(S), len(train)
        return self

    def var(self, f) -> np.ndarray:
        f = np.asarray(f, float)
        return np.maximum(self.s0 + self.s1 * f + self.s2 * f * f, S0_FLOOR)

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """(mean of the final margin or total, sd) at each state."""
        base = df["m"] if self.target == "margin" else df["t"]
        mean = base.to_numpy(float) + df[list(self.cols)].to_numpy(float) @ self.beta
        return mean, np.sqrt(self.var(df["f"].to_numpy(float)))

    def to_dict(self) -> dict:
        return {"target": self.target, "cols": list(self.cols), "beta": [float(b) for b in self.beta],
                "s0": self.s0, "s1": self.s1, "s2": self.s2, "season": self.S,
                "n_train": self.n_train}

    @classmethod
    def from_dict(cls, d: dict) -> "StateModel":
        m = cls(d["target"], tuple(d["cols"]))
        m.beta = np.asarray(d["beta"], float)
        m.s0, m.s1, m.s2 = float(d["s0"]), float(d["s1"]), float(d.get("s2", 0.0))
        m.S, m.n_train = int(d["season"]), int(d.get("n_train", 0))
        if m.beta.shape != (len(m.cols),) or not np.isfinite(m.beta).all() or m.s0 <= 0:
            raise ValueError("bad state model block")
        return m


# ── prices ───────────────────────────────────────────────────────────────────

def _phi(x):
    """The standard normal CDF (scipy is a worker dependency, requirements.txt)."""
    from scipy.special import ndtr
    return ndtr(np.asarray(x, float))


def dec(price) -> np.ndarray:
    a = np.asarray(price, float)
    return np.where(a >= 100, 1.0 + a / 100.0, 1.0 + 100.0 / np.abs(a))


def risk_win(price) -> tuple[np.ndarray, np.ndarray]:
    """One unit to win, risk capped at MAX_RISK."""
    d = dec(price)
    r = np.minimum(1.0 / (d - 1.0), MAX_RISK)
    return r, r * (d - 1.0)


def side_probs(market, side, line, mu, sd) -> tuple[np.ndarray, np.ndarray]:
    """(P win, P push) of a side. spreads: home covers when margin + line > 0
    (`line` the HOME number); totals: over when total > line; h2h: home wins
    (a level regulation goes to overtime, so the margin is never 0: P(home) is
    P(M >= 1) / (P(M >= 1) + P(M <= -1))). Integer outcomes, continuity 0.5."""
    market, side = np.asarray(market, object), np.asarray(side, object)
    mu, sd = np.asarray(mu, float), np.asarray(sd, float)
    line = np.asarray(line, float)
    th = np.where(market == "spreads", -line, line)          # side A wins when X > th
    th = np.where(market == "h2h", 0.0, th)
    is_int = np.isclose(th, np.round(th))
    lo_a = np.floor(th) + 0.5                                  # A wins: X >= floor(th)+1
    p_a = 1.0 - _phi((lo_a - mu) / sd)
    p_push = np.where(is_int, _phi((th + 0.5 - mu) / sd) - _phi((th - 0.5 - mu) / sd), 0.0)
    p_b = 1.0 - p_a - p_push
    ml = market == "h2h"
    tot = np.where(ml, p_a + p_b, 1.0)            # only a moneyline is renormalised
    p_a = np.where(ml, p_a / tot, p_a)
    p_b = np.where(ml, p_b / tot, p_b)
    p_push = np.where(ml, 0.0, p_push)
    a_side = (side == "home") | (side == "over")
    return np.where(a_side, p_a, p_b), p_push


def ev_of(price, p_win, p_push) -> np.ndarray:
    d = dec(price)
    return np.asarray(p_win, float) * (d - 1.0) - (1.0 - np.asarray(p_win, float) - np.asarray(p_push, float))


# ── quotes -> offers ─────────────────────────────────────────────────────────

def offers_from_quotes(q: pd.DataFrame) -> pd.DataFrame:
    """One row per (quote, side) from odds-shaped quote rows (market, book,
    home_price, away_price, spread_home, total_line, over_price, under_price).
    `line` is the HOME number for spreads, the total for totals, NaN for h2h."""
    out = []
    keep = [c for c in q.columns if c not in ("home_price", "away_price", "over_price",
                                              "under_price", "spread_home", "total_line")]
    sp = q[q["market"] == "spreads"]
    for side, pc in (("home", "home_price"), ("away", "away_price")):
        out.append(sp[keep].assign(side=side, price=sp[pc].to_numpy(float),
                                   line=sp["spread_home"].to_numpy(float)))
    to = q[q["market"] == "totals"]
    for side, pc in (("over", "over_price"), ("under", "under_price")):
        out.append(to[keep].assign(side=side, price=to[pc].to_numpy(float),
                                   line=to["total_line"].to_numpy(float)))
    ml = q[q["market"] == "h2h"]
    for side, pc in (("home", "home_price"), ("away", "away_price")):
        out.append(ml[keep].assign(side=side, price=ml[pc].to_numpy(float), line=np.nan))
    o = pd.concat(out, ignore_index=True) if out else pd.DataFrame()
    if len(o):
        o = o[o["price"].notna() & ~((o["price"] > -100) & (o["price"] < 100))]
        o = o[(o["market"] == "h2h") | o["line"].notna()]
    return o.reset_index(drop=True)


_BOUNDS_COLS = {"spreads": ("spread_home", ("home_price", "away_price")),
                "totals": ("total_line", ("over_price", "under_price")),
                "h2h": (None, ("home_price", "away_price"))}


def in_bounds(q: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(quotes, data errors): every NCAAB card's one guard against a feed typo
    (models/ncaab_quote_bounds: a line outside its market's range, a price
    beyond +/-100000), applied before anything else reads a quote. Its ranges
    were measured on pre-game rows; an in-play spread past +/-60 (a blowout) is
    dropped with them, which removes a number no rule here would bet."""
    from models import ncaab_quote_bounds as QB
    keep, bad = [], []
    for mk, (line_col, prices) in _BOUNDS_COLS.items():
        part = q[q["market"] == mk]
        if not len(part):
            continue
        ok, err = QB.split(part, mk, line_col=line_col, price_cols=prices)
        keep.append(ok)
        bad.append(err)
    other = q[~q["market"].isin(list(_BOUNDS_COLS))]
    keep.append(other)
    good = pd.concat(keep).sort_index() if keep else q.iloc[:0]
    errs = pd.concat(bad) if bad else q.iloc[:0]
    return good, errs


def novig_home(home_price, away_price) -> np.ndarray:
    ph, pa = 1.0 / dec(home_price), 1.0 / dec(away_price)
    return ph / (ph + pa)


def drop_outliers(q: pd.DataFrame, by=("game_id", "market", "fetch_at")) -> pd.DataFrame:
    """Drops a book's quote that sits far from the median of the OTHER books'
    quotes on the same game, market and fetch (BAD ROWS). A quote with no other
    book beside it is kept."""
    q = q.copy()
    num = np.where(q["market"] == "spreads", q["spread_home"],
                   np.where(q["market"] == "totals", q["total_line"],
                            novig_home(q["home_price"].fillna(-110), q["away_price"].fillna(-110))))
    q["_num"] = num.astype(float)
    g = q.groupby(list(by))["_num"]
    s, n = g.transform("sum"), g.transform("count")
    # median of the others is costly per row; the others' mean is a close,
    # conservative stand-in for 2-9 books, and an exact median when n <= 3
    others = (s - q["_num"]) / (n - 1).where(n > 1)
    gap = (q["_num"] - others).abs()
    cap = np.where(q["market"] == "h2h", OUTLIER_NOVIG, OUTLIER_PTS)
    bad = gap.notna() & (gap > cap)
    return q[~bad].drop(columns="_num")


def choose(offers: pd.DataFrame, cut: float, books: tuple[str, ...],
           floor: float = PRICE_FLOOR) -> pd.DataFrame:
    """Per (game_id, rule): the side whose best allowed offer has the higher EV,
    that side's best-EV offer (ties to the earlier book in `books`), kept only
    when EV >= cut. `offers` carries p_win, p_push and ev. Rows that do not
    clear come back with bet=False so the caller can spend the rule."""
    rank = {b: i for i, b in enumerate(books)}
    o = offers[offers["book"].isin(books) & (offers["price"] >= floor)].copy()
    if not len(o):
        return o.assign(bet=pd.Series(dtype=bool))
    o["_r"] = o["book"].map(rank)
    o["ev"] = np.round(o["ev"].to_numpy(float), 12)
    o = o.sort_values(["game_id", "rule", "ev", "_r"], ascending=[True, True, False, True])
    best = o.drop_duplicates(["game_id", "rule"]).drop(columns="_r")
    return best.assign(bet=best["ev"] >= cut).reset_index(drop=True)


def settle(market, side, line, home, away) -> np.ndarray:
    """'W' / 'L' / 'P' of a full-game bet (overtime included)."""
    market, side = np.asarray(market, object), np.asarray(side, object)
    line = np.asarray(line, float)
    home, away = np.asarray(home, float), np.asarray(away, float)
    margin, total = home - away, home + away
    x = np.where(market == "spreads", margin + line,
                 np.where(market == "totals", total - line, margin))
    a_side = (side == "home") | (side == "over")
    v = np.where(a_side, x, -x)
    return np.where(v > 0, "W", np.where(v < 0, "L", "P"))


def units(result, price) -> tuple[np.ndarray, np.ndarray]:
    """(units won or lost, risk) at one unit to win, risk capped at 3."""
    r, w = risk_win(price)
    res = np.asarray(result, object)
    return np.where(res == "W", w, np.where(res == "L", -r, 0.0)), r
