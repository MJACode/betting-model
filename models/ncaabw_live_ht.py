"""Women's college basketball halftime total: `ncaabw_live_total_ht`.

WHAT IT BETS. The full-game total, over or under, at a book's in-play number
during the halftime break. One decision a game: the first five-minute price
read of the break that holds an eligible quote decides it, on the best quote
there, bet at EV >= the cut and spent either way. Settled on the final total,
overtime included, against the line taken.

THE MODEL. The points still to come are normal with mean X b and variance
s0 + s1 f + s2 f^2, f the share of regulation (2,400 seconds, four quarters)
left. X: f x the pre-game total; f x the surprise so far (the points scored
less the share of the pre-game total already due); f^2 x the surprise; and a
late-and-close term (under 5 minutes left, within 8 points) that is zero at
the break and is fitted because the fit uses the whole game. The pre-game
total is the median of the books' last pre-game totals. Fitted by weighted
least squares on the score at every 30 seconds of every priced game.

WHY THE BREAK. The research rule was "the first second-half read holding an
eligible quote". In 1,039 of 1,055 games of 2025-26 that read sits in the
break: the state is the halftime score and the quote was stamped a median 2.2
minutes after the half ended. The rule is that population and nothing else.

A QUOTE IS ELIGIBLE when: it is a bettable book's (config.BEST_LINE_BOOKMAKERS);
the half had ended on ESPN's play list when the book stamped it, and the third
quarter had not started at the read; no point was logged between its stamp and
the read; the price of the side taken is between -250 and +250; its total is
within 6 points of the median of every book's total for the game in that read;
at least 2 other books quote the game's total in that read; and the total is
between 60 and 260.

ONE CODE PATH. `read_break` is the decision the build replays on the two
priced seasons (scripts/build_ncaabw_live_ht_artifact.py, which must match the
research bet for bet before it writes an artifact) and the decision the loop
makes (models/ncaabw_live_loop.py). Plays reach it through one parser
(data/ingestors/ncaabw_pbp.py).

Evidence, prices and what does not clear: docs/sports/ncaabw.md, "In play".
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

MODEL_ID = "ncaabw_live_total_ht"
SPORT = "NCAABW"
MARKET = "totals"
REG_S = 2400.0
HALF_S = 1200.0
GRID_STEP_S = 30.0
MIN_PLAYS = 50                    # fewer logged plays than this is not a play list
LATE_F = 300.0 / REG_S            # the late-and-close term: under five minutes left ...
LATE_MARGIN = 8.0                 # ... and within eight points
PRICE_BAND = (-250.0, 250.0)      # the side taken, American
OUTLIER_PTS = 6.0                 # a total further than this from the read's median is not bet
MIN_OTHERS = 2                    # other books quoting the game's total in the read
LINE_RANGE = (60.0, 260.0)
PRIOR_SPREAD_MAX = 70.0           # a pre-game spread beyond this is not a spread
PRIOR_TOTAL_RANGE = (90.0, 200.0)
MAX_RISK = 3.0                    # one unit to win, risk capped here (config stake_for)
# The purchase the rule was graded on: one snapshot every five minutes, stamped
# 36-39 seconds after the mark (median 38; 21,879 in-play snapshots).
CADENCE_MIN = 5
FETCH_AFTER_SEC = 37.0

ARTIFACT_KIND = "ncaabw_live_ht"
ARTIFACT_PATH = "models/saved/ncaabw_live_ht_2027.json"
SEASON = 2027


# ── the game state ───────────────────────────────────────────────────────────

@dataclass
class States:
    """One game's logged plays in the order ESPN logged them: wallclock (ns),
    game seconds gone, the score in OUR orientation, and the score's version
    (it rises each time the score changes). Game seconds and the score never
    run backwards: see states_from_rows."""
    wall: np.ndarray
    gs: np.ndarray
    h: np.ndarray
    a: np.ndarray
    ver: np.ndarray

    def at(self, ns) -> np.ndarray:
        """Index of the last play logged at or before each instant; -1 = none."""
        return np.searchsorted(self.wall, ns, side="right") - 1


def states_from_rows(rows, as_logged: bool = False) -> States | None:
    """Parser rows (data.ingestors.ncaabw_pbp) -> States, or None when fewer
    than MIN_PLAYS plays carry a wallclock, a clock and a score. Sorted by
    wallclock then play number: ESPN's play number alone is not time order.

    THE SCORE IS THE HIGHEST LOGGED SO FAR. ESPN logs corrections late with a
    new wallclock and the running score of the moment they belong to: a
    first-quarter substitution entered during the break reads 2-2 two minutes
    after the half ended 37-20 (Fresno State at Washington, 2025-11-20
    02:47:35Z). Reading "the last play logged" as the state gave that game a
    2-2 halftime, and 54 of the research's 689 bets of 2025-26 a wrong score
    (24-30, -10.71 units, against 374-261, +77.30 on the other 635). A score
    never falls in a game, so the state is the running maximum, as game
    seconds already were.

    `as_logged=True` is the research's reading (each play's own score; the
    version counts ESPN's scoring flags). It exists so the build can show this
    code reproduces the research bet for bet; nothing live uses it."""
    recs = [(r["wallclock"], r["play_no"], r["game_s"], r["home_score"], r["away_score"],
             bool(r.get("scoring_play")))
            for r in rows
            if r.get("wallclock") is not None and r.get("game_s") is not None
            and r.get("home_score") is not None and r.get("away_score") is not None]
    if len(recs) < MIN_PLAYS:
        return None
    recs.sort(key=lambda t: (t[0], t[1]))
    wall = _ns([t[0] for t in recs])
    gs = np.maximum.accumulate(np.array([t[2] for t in recs], dtype=float))
    h = np.array([t[3] for t in recs], dtype=float)
    a = np.array([t[4] for t in recs], dtype=float)
    if as_logged:
        return States(wall, gs, h, a, np.cumsum(np.array([t[5] for t in recs], dtype=bool)))
    h, a = np.maximum.accumulate(h), np.maximum.accumulate(a)
    return States(wall, gs, h, a, np.concatenate([[0], np.cumsum(np.diff(h + a) > 0)]))


def _ns(ts) -> np.ndarray:
    return pd.DatetimeIndex(pd.to_datetime(ts, utc=True)).as_unit("ns").asi8


# ── the model ────────────────────────────────────────────────────────────────

def design(f, cur_m, cur_t, prior_t) -> np.ndarray:
    f = np.atleast_1d(np.asarray(f, float))
    sur = np.asarray(cur_t, float) - prior_t * (1 - f)
    late = ((f < LATE_F) & (np.abs(cur_m) <= LATE_MARGIN)).astype(float)
    return np.column_stack([f * prior_t, f * sur, f * f * sur, late])


@dataclass(frozen=True)
class TotalModel:
    b: tuple                      # the four mean coefficients, in design()'s order
    s: tuple                      # the variance: s0 + s1 f + s2 f^2

    def predict(self, f, cur_m, cur_t, prior_t):
        """(mean, sd) of the points still to come."""
        f = np.atleast_1d(np.asarray(f, float))
        mu = design(f, cur_m, cur_t, prior_t) @ np.asarray(self.b, float)
        var = np.maximum(self.s[0] + self.s[1] * f + self.s[2] * f * f, 1.0)
        return mu, np.sqrt(var)

    def to_dict(self) -> dict:
        return {"b": [float(x) for x in self.b], "s": [float(x) for x in self.s]}

    @classmethod
    def from_dict(cls, d: dict) -> "TotalModel":
        b, s = tuple(float(x) for x in d["b"]), tuple(float(x) for x in d["s"])
        if len(b) != 4 or len(s) != 3 or not all(math.isfinite(x) for x in b + s):
            raise ValueError("a total model is four mean and three variance numbers")
        return cls(b, s)


def training_rows(st: States, prior_t: float, final_t: float) -> pd.DataFrame:
    """The score every GRID_STEP_S of regulation, and the points that followed."""
    grid = np.arange(GRID_STEP_S, REG_S, GRID_STEP_S)
    idx = np.searchsorted(st.gs, grid, side="right") - 1
    ok = idx >= 0
    cur_t = (st.h + st.a)[idx[ok]]
    return pd.DataFrame({"f": 1 - grid[ok] / REG_S, "cur_m": (st.h - st.a)[idx[ok]], "cur_t": cur_t,
                         "prior_t": float(prior_t), "rem_t": float(final_t) - cur_t})


def fit(tr: pd.DataFrame) -> TotalModel:
    """Weighted least squares, the weights from the fitted variance, three passes."""
    X = design(tr["f"], tr["cur_m"], tr["cur_t"], tr["prior_t"].values)
    y = tr["rem_t"].values
    f = tr["f"].values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    V = np.column_stack([np.ones(len(tr)), f, f ** 2])
    s = None
    for _ in range(3):
        s = np.linalg.lstsq(V, (y - X @ b) ** 2, rcond=None)[0]
        w = 1.0 / np.sqrt(np.maximum(V @ s, 1.0))
        b = np.linalg.lstsq(X * w[:, None], y * w, rcond=None)[0]
    return TotalModel(tuple(float(x) for x in b), tuple(float(x) for x in s))


def p_over(mu, sd, k):
    """P(points to come > k), P(push); the points to come are a whole number."""
    whole = np.abs(k - np.round(k)) < 1e-9
    pw = np.where(whole, norm.sf((k + 0.5 - mu) / sd), norm.sf((k - mu) / sd))
    pp = np.where(whole, norm.cdf((k + 0.5 - mu) / sd) - norm.cdf((k - 0.5 - mu) / sd), 0.0)
    return pw, pp


def decimal(american) -> np.ndarray:
    a = np.asarray(american, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))


def units(side, line, price, final_total) -> tuple:
    """(units won, units risked): one unit to win, risk capped at MAX_RISK, a push returns the stake."""
    d = float(decimal(price))
    risk = min(1.0 / (d - 1.0), MAX_RISK)
    diff = float(final_total) - float(line)
    res = diff if side == "over" else -diff
    return (risk * (d - 1.0) if res > 0 else (-risk if res < 0 else 0.0)), risk


# ── one game at one price read ───────────────────────────────────────────────

OFFER_COLS = ("book", "stamp", "line", "side", "price", "ev", "prob", "p_push", "mean", "sd",
              "over_price", "under_price", "h_pts", "a_pts", "off", "others", "fresh", "half_over",
              "eligible")


@dataclass
class Read:
    """What one price read says about one game.
    status: 'early'    the half had not ended on the play list at the read
            'past'     the third quarter was under way at the read
            'none'     in the break, no eligible quote
            'decided'  in the break with an eligible quote: `best` is the decision
    """
    status: str
    state: dict = field(default_factory=dict)       # the score at the read
    offers: pd.DataFrame | None = None              # every quote with a state, priced
    best: dict | None = None


def read_break(quotes: pd.DataFrame, st: States, fetch_at, prior_t: float, model: TotalModel,
               books: tuple) -> Read:
    """One game's total quotes at one read -> Read. `quotes`: book, stamp (the
    book's own last update), total_line, over_price, under_price; one row a
    book (the first is kept when the feed lists a book twice)."""
    j = int(st.at(_ns([fetch_at]))[0])
    if j < 0 or st.gs[j] < HALF_S:
        return Read("early")
    state = {"h_pts": int(st.h[j]), "a_pts": int(st.a[j]), "game_s": float(st.gs[j])}
    if st.gs[j] > HALF_S:
        return Read("past", state)
    q = quotes.drop_duplicates("book", keep="first")
    i = st.at(_ns(q["stamp"])) if len(q) else np.array([], dtype=int)
    q = q[i >= 0]
    i = i[i >= 0]
    if not len(q):
        return Read("none", state)
    line = pd.to_numeric(q["total_line"], errors="coerce").values.astype(float)
    cur_t, cur_m = (st.h + st.a)[i], (st.h - st.a)[i]
    mu, sd = model.predict(np.clip(1 - st.gs[i] / REG_S, 0, 1), cur_m, cur_t, float(prior_t))
    pw, pp = p_over(mu, sd, line - cur_t)
    pl = 1 - pw - pp
    p1 = pw / (pw + pl)
    a1 = pd.to_numeric(q["over_price"], errors="coerce").values.astype(float)
    a2 = pd.to_numeric(q["under_price"], errors="coerce").values.astype(float)
    ev1, ev2 = p1 * decimal(a1) - 1, (1 - p1) * decimal(a2) - 1
    first = ev1 >= ev2
    price = np.where(first, a1, a2)
    off = np.abs(line - np.nanmedian(line)) if np.isfinite(line).any() else np.full(len(q), np.nan)
    o = pd.DataFrame({
        "book": q["book"].values, "stamp": q["stamp"].values, "line": line,
        "side": np.where(first, "over", "under"), "price": price, "ev": np.where(first, ev1, ev2),
        "prob": np.where(first, p1, 1 - p1), "p_push": pp, "mean": mu, "sd": sd,
        "over_price": a1, "under_price": a2,
        "h_pts": st.h[i], "a_pts": st.a[i], "off": off, "others": len(q) - 1,
        "fresh": st.ver[j] == st.ver[i], "half_over": st.gs[i] == HALF_S})
    o["eligible"] = (o["book"].isin(books) & (o["price"] >= PRICE_BAND[0]) & (o["price"] <= PRICE_BAND[1])
                     & (o["off"] <= OUTLIER_PTS) & (o["others"] >= MIN_OTHERS) & o["fresh"] & o["half_over"]
                     & (o["line"] >= LINE_RANGE[0]) & (o["line"] <= LINE_RANGE[1]))
    el = o[o["eligible"]]
    if el.empty:
        return Read("none", state, o)
    rank = {b: k for k, b in enumerate(books)}
    el = el.assign(_r=el["book"].map(rank)).sort_values(["ev", "_r"], ascending=[False, True], kind="stable")
    return Read("decided", state, o, el.iloc[0].drop("_r").to_dict())


# ── the pre-game numbers ─────────────────────────────────────────────────────

PRIOR_CLOSE_SQL = """
    SELECT DISTINCT ON (o.market, o.bookmaker)
           o.market, o.bookmaker, o.spread_home, o.total_line
      FROM odds o JOIN games g ON g.game_id = o.game_id
     WHERE o.game_id = %s AND o.market IN ('spreads', 'totals')
       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
       AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
     ORDER BY o.market, o.bookmaker, o.snapshot_at::timestamptz DESC
"""


def _finite(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def prior_from_closes(rows) -> tuple | None:
    """(expected home margin, pre-game total) from each book's last pre-game
    spread and total: the median over books. None when either is missing (the
    grade priced only games with both)."""
    sp = [v for m, _b, s, _t in rows if m == "spreads" and (v := _finite(s)) is not None
          and abs(v) <= PRIOR_SPREAD_MAX]
    to = [v for m, _b, _s, t in rows if m == "totals" and (v := _finite(t)) is not None
          and PRIOR_TOTAL_RANGE[0] <= v <= PRIOR_TOTAL_RANGE[1]]
    if not sp or not to:
        return None
    return -float(np.median(sp)), float(np.median(to))


# ── the artifact ─────────────────────────────────────────────────────────────

@dataclass
class Artifact:
    total: TotalModel
    cut: float
    raw: dict = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.raw.get("version", ""))


def artifact_from_dict(d: dict) -> Artifact:
    if d.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"not an {ARTIFACT_KIND} artifact (kind={d.get('kind')!r})")
    cut = float(d["cut"])
    if not 0.0 < cut < 1.0:
        raise ValueError("the cut is an expected value between 0 and 1")
    return Artifact(TotalModel.from_dict(d["total"]), cut, d)


def load_artifact(path=None) -> Artifact:
    p = Path(path) if path is not None else Path(__file__).resolve().parents[1] / ARTIFACT_PATH
    return artifact_from_dict(json.loads(p.read_text(encoding="utf-8")))


# ── the pick ─────────────────────────────────────────────────────────────────

def pick_label(side: str, line: float, home: str, away: str) -> str:
    """'Drake @ Iowa Over 138.5 (live)'. No half is named: the bet is on the
    full game, and in this app "First Half" names a bet on that half alone."""
    return f"{away} @ {home} {'Over' if side == 'over' else 'Under'} {float(line):g} (live)"
