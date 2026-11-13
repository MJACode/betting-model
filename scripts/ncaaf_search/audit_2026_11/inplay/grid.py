"""NCAAF in-play: the NCAAB game-state model (models/ncaab_live_ig.py) ported to football.

DEFINITIONS. Written before any graded result was looked at; the only things
read first were data-quality counts (prep.py: coverage, drops, timestamp lags).

MODEL (the port, as close to models/ncaab_live_ig.StateModel as football allows)
  What is still to come ~ Normal(X b, sqrt(s0 + s1 f + s2 f^2)), f = share of the
  3,600 s of regulation left. Fit by weighted least squares, three passes, the
  weight 1 / variance(f), on ONE STATE PER 30 S OF REGULATION GAME CLOCK (game
  seconds 60 .. 3540; the state is the score after the last in-order play that
  started at or before that second), 2025 play-by-play.
    margin  final home margin - current margin  on  f x prior margin, f, margin x f
    total   final total - current total  on  f x prior total, f^2 x prior total, f, f^2,
            (points so far - (1 - f) x prior total) x f   [pace against the pre-game total],
            |margin| x f   [a blowout slows down],
            a late-and-close term max(0, 1 - |margin| / 16) x max(0, 1 - secs_left / 300).
  Left out against NCAAB: the two bonus (team-foul) terms; basketball only.
  Not added: possession, down, distance, field position. The 2026 state log
  carries possession on 58% of rows and field position on 41% (prep), so a
  model that needs them could not be run on the season that is the real test.
  PRIOR: DraftKings' last spread and total at or before kickoff; where a 2025
  game has none stored, CFBD's DraftKings close, then CFBD's Bovada close
  (training games only need it; ginfo counts each source). The finals include
  overtime, as the markets settle.

RULES (one decision per game per rule)
  total_H1  totals, first half      total_H2  totals, halftime to 5:00 left
  h2h_H1    moneyline, first half   h2h_H2    moneyline, halftime to 5:00 left
  Overtime is in no rule. DraftKings quotes only. The decision is the FIRST
  eligible quote, in the order we received them, whose better side has EV at
  the quoted price >= the cut (first-signal lock). Cuts 0.02 0.05 0.08 0.12 0.20.
  A moneyline side shorter than -200 is never bet.
  EV = p_win x (decimal - 1) - (1 - p_win - p_push). Integer outcomes, continuity
  0.5; a level regulation goes to overtime so P(home) = P(M >= 1) / (P(M >= 1) + P(M <= -1)).

STATE AT A QUOTE
  stamp  the BOOK's timestamp: 2025 the `lu=` of the bought replay's source
         string; 2026 `snapshot_at` (the live price log stores the book's
         last_update; the 10,809 rows of 2026-08-29 stamped with our own clock
         are dropped). fetch = when we had it: 2025 `served=`, 2026 `created_at`.
  2025   the last play, in play order, whose wallclock is in order and at or
         before the stamp (score after that play, its clock). Halftime = that
         play is in period 2 and the next such play is in period 3 or later.
  2026   the last state the live loop logged at or before the stamp (score);
         the clock is read between that state and the next logged one (the loop
         logs on a change of score, period or possession, not every clock tick).
  KNOWN  a state before AND after the stamp, no more than 30 minutes apart, in
         regulation, on a game with a final and a prior.

ELIGIBLE (V1, the rule as asked): KNOWN, in a phase, not a feed error, and FRESH:
  no score became known in the 60 s before the stamp, and none between the stamp
  and the fetch.
FEED ERRORS (counted, dropped): a price missing or strictly between -100 and
  +100; the two sides' implied probabilities summing to less than 1.00 or more
  than 1.25; a total outside 5 .. 150; a total at or below the points already
  on the board; a total with either side priced beyond +/-250 (the NCAAB bound:
  not a main-line price).

V2, "CONFIRMED" (defined here, before any grade, because prep measured that the
  2026 logged score trails DraftKings' own total move by a median 75 s, 90th
  percentile 182 s, 95th 221 s: at the stamp our score is often one touchdown
  behind the book, and the "edge" is then the touchdown, the Delaware bet of
  2026-09-19 in docs/live_betting.md). V1 plus: no score becomes known in the
  240 s AFTER the stamp; in 2025 also no score whose bracket (the previous
  in-order wallclock .. the wallclock it is first seen at) opens less than 60 s
  after the stamp and closes after it; and the quote is no older than 90 s at
  the fetch (the loop's own age bound) unless the stamp is in the halftime
  break. V2 is graded at the quote's own price, as the NCAAB grade is; a loop
  would bet about four minutes later.

TESTS
  A   fit on every 2025 state; test on 2026 (logged states, live DraftKings rows).
  B1  fit on 2025 weeks 1-7; test on 2025 weeks 8+ and the postseason (the replay).
  B2  fit on 2025 weeks 8+ and the postseason; test on 2025 weeks 1-7.

GRADE  units: one to win, risk = min(1 / (decimal - 1), 3), win = risk x (decimal - 1).
  ROI = units / units risked. 95% interval: 2,000 resamples of slate dates.
  Early / late: the window's eligible games split at their median slate date.
  Blind: over, under, home, away at every game's first eligible quote.
  PLACEBO (200 runs): each game takes ANOTHER game's model opinion at the same
  share of the game left (f in 0.02 bands, the nearest band within 0.04): the
  donor's model probability minus the donor's own no-vig market probability is
  added to this game's no-vig probability, and the same first-signal rule and
  cuts are run. (A raw swap of probabilities would be degenerate on a moneyline,
  where the favourite differs by game; on a total the two are the same thing.)
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import ndtr

OUT = WORK / "inplay"
REG_S = 3600.0
H2_MIN_SECS_LEFT = 300.0
CUTS = (0.02, 0.05, 0.08, 0.12, 0.20)
PRICE_FLOOR = -200.0
MAX_RISK = 3.0
LINE_PRICE_MAX = 250.0
S0_FLOOR = 0.25
FRESH_BEFORE_S = 60.0
CONFIRM_S = 240.0
BRACKET_OPEN_S = 60.0
AGE_MAX_S = 90.0
KNOWN_GAP_S = 1800.0
N_BOOT = 2000
N_PLACEBO = 200
F_BAND = 0.02
MARGIN_COLS = ("x_mu", "x_f", "x_mf")
TOTAL_COLS = ("y_T", "y_T2", "y_f", "y_f2", "y_pace", "y_lead", "y_late")
RULES = ("totals_H1", "totals_H2", "h2h_H1", "h2h_H2")
EPOCH = pd.Timestamp("1970-01-01", tz="UTC")


def secs(s: pd.Series) -> pd.Series:
    return (s - EPOCH).dt.total_seconds()


# ── the model (ported from models/ncaab_live_ig.py) ──────────────────────────

def features(st: pd.DataFrame) -> pd.DataFrame:
    f = st["f"].to_numpy(float)
    m, t = st["m"].to_numpy(float), st["t"].to_numpy(float)
    mu, T = st["mu_pre"].to_numpy(float), st["T_pre"].to_numpy(float)
    sl = st["secs_left"].to_numpy(float)
    late = np.clip(1.0 - np.abs(m) / 16.0, 0.0, None) * np.clip(1.0 - sl / 300.0, 0.0, 1.0)
    return st.assign(x_mu=f * mu, x_f=f, x_mf=m * f,
                     y_T=f * T, y_T2=f * f * T, y_f=f, y_f2=f * f,
                     y_pace=(t - (1.0 - f) * T) * f, y_lead=np.abs(m) * f, y_late=late)


class StateModel:
    def __init__(self, target: str):
        self.target = target
        self.cols = MARGIN_COLS if target == "margin" else TOTAL_COLS
        self.beta = None
        self.s0 = self.s1 = self.s2 = 0.0
        self.n_train = 0

    def _y(self, df):
        if self.target == "margin":
            return (df["final_margin"] - df["m"]).to_numpy(float)
        return (df["final_total"] - df["t"]).to_numpy(float)

    def fit(self, train: pd.DataFrame) -> "StateModel":
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
        self.n_train = len(train)
        return self

    def var(self, f):
        f = np.asarray(f, float)
        return np.maximum(self.s0 + self.s1 * f + self.s2 * f * f, S0_FLOOR)

    def predict(self, df):
        base = df["m"] if self.target == "margin" else df["t"]
        mean = base.to_numpy(float) + df[list(self.cols)].to_numpy(float) @ self.beta
        return mean, np.sqrt(self.var(df["f"].to_numpy(float)))

    def describe(self) -> dict:
        return {"cols": list(self.cols), "beta": [round(float(b), 4) for b in self.beta],
                "s0": round(self.s0, 3), "s1": round(self.s1, 3), "s2": round(self.s2, 3),
                "n_train": self.n_train}


def fit_models(train: pd.DataFrame) -> dict:
    x = features(train)
    return {t: StateModel(t).fit(x) for t in ("margin", "total")}


def calibration(models: dict, st: pd.DataFrame) -> pd.DataFrame:
    x = features(st)
    rows = []
    for t, mdl in models.items():
        mean, sd = mdl.predict(x)
        y = x["final_margin" if t == "margin" else "final_total"].to_numpy(float)
        z = (y - mean) / sd
        fb = pd.cut(x["f"], [0, 0.1, 0.25, 0.5, 0.75, 1.0], include_lowest=True)
        d = pd.DataFrame({"fb": fb, "err": y - mean, "z": z, "sd": sd, "g": x["gkey"].to_numpy()})
        for b, gg in d.groupby("fb", observed=True):
            rows.append({"target": t, "share_left": str(b), "states": len(gg), "games": gg["g"].nunique(),
                         "mean_err": round(gg["err"].mean(), 3),
                         "realised_sd": round(gg["err"].std(), 2), "model_sd": round(gg["sd"].mean(), 2),
                         "spread_ratio": round(gg["z"].std(), 3),
                         "cover_68": round((gg["z"].abs() <= 1).mean(), 3)})
    return pd.DataFrame(rows)


def dec(price):
    a = np.asarray(price, float)
    return np.where(a >= 100, 1.0 + a / 100.0, 1.0 + 100.0 / np.abs(a))


def risk_win(price):
    d = dec(price)
    r = np.minimum(1.0 / (d - 1.0), MAX_RISK)
    return r, r * (d - 1.0)


def probs_total(line, mu, sd):
    """(P over, P push) of a total: integer outcomes, continuity 0.5."""
    line = np.asarray(line, float)
    is_int = np.isclose(line, np.round(line))
    p_over = 1.0 - ndtr((np.floor(line) + 0.5 - mu) / sd)
    p_push = np.where(is_int, ndtr((line + 0.5 - mu) / sd) - ndtr((line - 0.5 - mu) / sd), 0.0)
    return p_over, p_push


def prob_home(mu, sd):
    pa = 1.0 - ndtr((0.5 - mu) / sd)
    pb = ndtr((-0.5 - mu) / sd)
    return pa / (pa + pb)


def ev_of(price, p_win, p_push=0.0):
    d = dec(price)
    return p_win * (d - 1.0) - (1.0 - p_win - p_push)


# ── quotes -> states ─────────────────────────────────────────────────────────

def asof(left: pd.DataFrame, right: pd.DataFrame, lk: str, rk: str, direction: str,
         exact: bool = True) -> pd.DataFrame:
    l = left.sort_values(lk, kind="stable")
    r = right.dropna(subset=[rk]).sort_values(rk, kind="stable")
    return pd.merge_asof(l, r, left_on=lk, right_on=rk, by="game_id", direction=direction,
                         allow_exact_matches=exact)


def states_2025(q: pd.DataFrame) -> pd.DataFrame:
    tl = pd.read_parquet(OUT / "tl_2025.parquet")
    tl["ts"] = secs(tl["t"])
    ev = pd.read_parquet(OUT / "ev_2025.parquet")
    ev["hi"], ev["lo"] = secs(ev["t_hi"]), secs(ev["t_lo"])
    a = tl[["game_id", "ts", "per_ff", "secs_ff", "hs", "as_"]].rename(
        columns={"ts": "t_prev", "per_ff": "per_prev", "secs_ff": "secs_prev"})
    b = tl[["game_id", "ts", "per_ff"]].rename(columns={"ts": "t_next", "per_ff": "per_next"})
    x = asof(q, a, "stamp_s", "t_prev", "backward")
    x = asof(x, b, "stamp_s", "t_next", "forward", exact=False)
    x = asof(x, ev[["game_id", "hi"]].rename(columns={"hi": "last_chg"}), "stamp_s", "last_chg", "backward")
    x = asof(x, ev[["game_id", "hi", "lo"]].rename(columns={"hi": "next_chg", "lo": "next_lo"}),
             "stamp_s", "next_chg", "forward", exact=False)
    x["known"] = x["t_prev"].notna() & x["t_next"].notna() & ((x["t_next"] - x["t_prev"]) <= KNOWN_GAP_S) \
        & (x["per_prev"] <= 4)
    x["is_break"] = (x["per_prev"] == 2) & (x["per_next"] >= 3)
    x["secs_left"] = np.where(x["is_break"], 1800.0, x["secs_prev"])
    x["period"] = x["per_prev"]
    # a score whose bracket opens within 60 s after the stamp and closes after it
    x["bracket_open"] = x["next_chg"].notna() & x["next_lo"].notna() \
        & (x["next_lo"] < x["stamp_s"] + BRACKET_OPEN_S)
    return x


def states_2026(q: pd.DataFrame) -> pd.DataFrame:
    st = pd.read_parquet(OUT / "st_2026.parquet")
    st["ts"] = secs(st["seen"])
    a = st[["game_id", "ts", "period", "secs_left", "home_score", "away_score", "clock_seconds"]].rename(
        columns={"ts": "t_prev", "period": "per_prev", "secs_left": "secs_prev", "home_score": "hs",
                 "away_score": "as_", "clock_seconds": "clk_prev"})
    b = st[["game_id", "ts", "period", "secs_left"]].rename(
        columns={"ts": "t_next", "period": "per_next", "secs_left": "secs_next"})
    ch = st[st["score_chg"]][["game_id", "ts"]]
    x = asof(q, a, "stamp_s", "t_prev", "backward")
    x = asof(x, b, "stamp_s", "t_next", "forward", exact=False)
    x = asof(x, ch.rename(columns={"ts": "last_chg"}), "stamp_s", "last_chg", "backward")
    x = asof(x, ch.rename(columns={"ts": "next_chg"}), "stamp_s", "next_chg", "forward", exact=False)
    x["known"] = x["t_prev"].notna() & x["t_next"].notna() & ((x["t_next"] - x["t_prev"]) <= KNOWN_GAP_S) \
        & x["per_prev"].between(1, 4)
    w = (x["stamp_s"] - x["t_prev"]) / (x["t_next"] - x["t_prev"]).where((x["t_next"] - x["t_prev"]) > 0)
    interp = x["secs_prev"] + (x["secs_next"] - x["secs_prev"]) * w
    ok = (x["secs_next"] <= x["secs_prev"]) & w.notna()
    x["secs_left"] = np.where(ok, interp, x["secs_prev"])
    x["is_break"] = (x["per_prev"] == 2) & (x["clk_prev"] == 0)
    x["secs_left"] = np.where(x["is_break"], 1800.0, x["secs_left"])
    x["period"] = np.where(x["secs_left"] > 1800.0, 2.0, 3.0)      # only the half matters below
    x["period"] = np.where(x["is_break"], 2.0, x["period"])
    x["bracket_open"] = False
    return x


def eligibility(x: pd.DataFrame, ginfo: pd.DataFrame, label: str, log: dict) -> pd.DataFrame:
    """Flags every quote; returns the V1-eligible ones (v2 marks the confirmed)."""
    x = x.merge(ginfo[["game_id", "slate", "fh", "fa", "sp_pre", "T_pre", "prior_src"]], on="game_id", how="left")
    n = {"quotes": len(x), "games": x["game_id"].nunique()}
    x["m"], x["t"] = x["hs"] - x["as_"], x["hs"] + x["as_"]
    tot = x["market"] == "totals"
    pa = np.where(tot, x["over_price"], x["home_price"]).astype(float)
    pb = np.where(tot, x["under_price"], x["away_price"]).astype(float)
    x["price_a"], x["price_b"] = pa, pb
    bad_price = np.isnan(pa) | np.isnan(pb) | ((pa > -100) & (pa < 100)) | ((pb > -100) & (pb < 100))
    with np.errstate(invalid="ignore", divide="ignore"):
        over_round = 1.0 / dec(pa) + 1.0 / dec(pb)
    bad_round = ~bad_price & ((over_round < 1.0) | (over_round > 1.25))
    line = x["total_line"].to_numpy(float)
    bad_line = tot.to_numpy() & (np.isnan(line) | (line < 5) | (line > 150))
    wide = tot.to_numpy() & ~bad_price & ((np.abs(pa) > LINE_PRICE_MAX) | (np.abs(pb) > LINE_PRICE_MAX))
    x["novig_a"] = (1.0 / dec(pa)) / over_round
    have = x["fh"].notna() & x["T_pre"].notna()
    known = x["known"] & have
    below = tot.to_numpy() & known.to_numpy() & ~bad_line & (line <= x["t"].to_numpy(float))
    x["err"] = bad_price | bad_round | bad_line | wide | below
    h1 = (x["period"] <= 2) & ~x["is_break"] & (x["secs_left"] >= 1800.0)
    h2 = x["is_break"] | ((x["period"] >= 3) & (x["secs_left"] >= H2_MIN_SECS_LEFT) & (x["secs_left"] <= 1800.0))
    x["phase"] = np.select([h1, h2], ["H1", "H2"], "")
    fresh_before = x["last_chg"].isna() | ((x["stamp_s"] - x["last_chg"]) > FRESH_BEFORE_S)
    fresh_fetch = ~(x["next_chg"] <= x["fetch_s"])
    confirm = ~(x["next_chg"] <= x["stamp_s"] + CONFIRM_S) & ~x["bracket_open"]
    age_ok = (x["age"] <= AGE_MAX_S) | x["is_break"]
    n["no final or no prior (games)"] = int(x.loc[~have, "game_id"].nunique())
    n["no final or no prior"] = int((~have).sum())
    n["state not known at the stamp"] = int((have & ~x["known"]).sum())
    n["  of which on games with no state source at all"] = int((have & x["t_prev"].isna() & x["t_next"].isna()).sum())
    k = known
    n["feed error: price missing or inside +/-100"] = int((k & bad_price).sum())
    n["feed error: implied sum outside 1.00-1.25"] = int((k & bad_round).sum())
    n["feed error: total outside 5-150"] = int((k & bad_line).sum())
    n["feed error: total at or below points on the board"] = int((k & below).sum())
    n["total with a side priced beyond +/-250"] = int((k & wide & ~bad_round).sum())
    k = k & ~x["err"]
    n["not in a phase (last 5:00, overtime)"] = int((k & (x["phase"] == "")).sum())
    k = k & (x["phase"] != "")
    n["a score became known in the 60 s before the stamp"] = int((k & ~fresh_before).sum())
    n["a score became known between stamp and fetch"] = int((k & fresh_before & ~fresh_fetch).sum())
    k = k & fresh_before & fresh_fetch
    n["ELIGIBLE V1"] = int(k.sum())
    n["V2: a score becomes known within 240 s after (or its bracket is open)"] = int((k & ~confirm).sum())
    n["V2: older than 90 s at the fetch, not halftime"] = int((k & confirm & ~age_ok).sum())
    x["v2"] = k & confirm & age_ok
    n["ELIGIBLE V2"] = int(x["v2"].sum())
    log[label] = n
    e = x[k].copy()
    e["rule"] = e["market"] + "_" + e["phase"]
    e["f"] = e["secs_left"] / REG_S
    e["mu_pre"] = -e["sp_pre"]
    e["final_margin"], e["final_total"] = e["fh"] - e["fa"], e["fh"] + e["fa"]
    return e


def price_quotes(e: pd.DataFrame, models: dict) -> pd.DataFrame:
    """Both sides of every eligible quote priced; side A = over / home."""
    x = features(e)
    mu_m, sd_m = models["margin"].predict(x)
    mu_t, sd_t = models["total"].predict(x)
    tot = (x["market"] == "totals").to_numpy()
    p_over, p_push = probs_total(np.where(tot, x["total_line"], 0.0), mu_t, sd_t)
    p_home = prob_home(mu_m, sd_m)
    pa = np.where(tot, p_over, p_home)
    push = np.where(tot, p_push, 0.0)
    pb = 1.0 - pa - push
    x = x.assign(mu_m=mu_m, sd_m=sd_m, mu_t=mu_t, sd_t=sd_t, p_a=pa, p_push=push, p_b=pb)
    x["ev_a"] = ev_of(x["price_a"], pa, push)
    x["ev_b"] = ev_of(x["price_b"], pb, push)
    x["ok_a"] = tot | (x["price_a"] >= PRICE_FLOOR)
    x["ok_b"] = tot | (x["price_b"] >= PRICE_FLOOR)
    # settle each side once
    won_a = np.where(tot, x["final_total"] > x["total_line"], x["final_margin"] > 0)
    pushd = np.where(tot, x["final_total"] == x["total_line"], False)
    ra, wa = risk_win(x["price_a"])
    rb, wb = risk_win(x["price_b"])
    x["risk_a"], x["risk_b"] = ra, rb
    x["units_a"] = np.where(pushd, 0.0, np.where(won_a, wa, -ra))
    x["units_b"] = np.where(pushd, 0.0, np.where(won_a, -rb, wb))
    x["res_a"] = np.where(pushd, "P", np.where(won_a, "W", "L"))
    x["res_b"] = np.where(pushd, "P", np.where(won_a, "L", "W"))
    return x.sort_values(["rule", "game_id", "fetch_s", "stamp_s", "odds_id"], kind="stable").reset_index(drop=True)


# ── decisions and grades ─────────────────────────────────────────────────────

def pick_sides(x: pd.DataFrame, ev_a=None, ev_b=None) -> pd.DataFrame:
    """The better allowed side of every quote."""
    ea = np.where(x["ok_a"], x["ev_a"] if ev_a is None else ev_a, -np.inf)
    eb = np.where(x["ok_b"], x["ev_b"] if ev_b is None else ev_b, -np.inf)
    a = ea >= eb
    tot = (x["market"] == "totals").to_numpy()
    return pd.DataFrame({
        "game_id": x["game_id"].to_numpy(), "rule": x["rule"].to_numpy(), "slate": x["slate"].to_numpy(),
        "fetch_s": x["fetch_s"].to_numpy(), "stamp_s": x["stamp_s"].to_numpy(),
        "side": np.where(tot, np.where(a, "over", "under"), np.where(a, "home", "away")),
        "line": x["total_line"].to_numpy(float),
        "price": np.where(a, x["price_a"], x["price_b"]),
        "ev": np.where(a, ea, eb), "p_win": np.where(a, x["p_a"], x["p_b"]),
        "units": np.where(a, x["units_a"], x["units_b"]), "risk": np.where(a, x["risk_a"], x["risk_b"]),
        "result": np.where(a, x["res_a"], x["res_b"]),
        "f": x["f"].to_numpy(float), "m": x["m"].to_numpy(float), "t": x["t"].to_numpy(float),
        "v2": x["v2"].to_numpy(bool)})


def first_signal(d: pd.DataFrame, cut: float) -> pd.DataFrame:
    """One bet per (rule, game): the first quote, in fetch order, at or over the cut.
    `d` is already sorted by rule, game, fetch."""
    return d[d["ev"] >= cut].drop_duplicates(["rule", "game_id"], keep="first")


def roi(b) -> float:
    r = b["risk"].sum()
    return float(b["units"].sum() / r) if r else float("nan")


def boot_ci(b: pd.DataFrame, seed: int = 7):
    if not len(b):
        return (float("nan"), float("nan"))
    by = b.groupby("slate")[["units", "risk"]].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(by), size=(N_BOOT, len(by)))
    u, r = by["units"].to_numpy()[idx].sum(1), by["risk"].to_numpy()[idx].sum(1)
    return float(np.percentile(u / r, 2.5)), float(np.percentile(u / r, 97.5))


def summarise(b: pd.DataFrame, split_date: str) -> dict:
    out = {"bets": int(len(b))}
    if not len(b):
        return out
    lo, hi = boot_ci(b)
    e, l = b[b["slate"] <= split_date], b[b["slate"] > split_date]
    sides = b["side"].value_counts()
    out.update({
        "w": int((b["result"] == "W").sum()), "l": int((b["result"] == "L").sum()),
        "p": int((b["result"] == "P").sum()),
        "units": round(float(b["units"].sum()), 2), "risked": round(float(b["risk"].sum()), 2),
        "roi": round(roi(b), 4), "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
        "early_n": int(len(e)), "early_roi": round(roi(e), 4) if len(e) else None,
        "late_n": int(len(l)), "late_roi": round(roi(l), 4) if len(l) else None,
        "price_min": float(b["price"].min()), "price_med": float(b["price"].median()),
        "price_max": float(b["price"].max()),
        "sides": {k: int(v) for k, v in sides.items()}, "dominant": str(sides.idxmax()),
        "mean_ev": round(float(b["ev"].mean()), 4), "median_ev": round(float(b["ev"].median()), 4),
        "slates": int(b["slate"].nunique())})
    return out


def blind(x: pd.DataFrame) -> dict:
    """Each side at every game's first eligible quote (moneyline: -200 floor)."""
    out = {}
    for rule, g in x.groupby("rule", sort=False):
        tot = rule.startswith("totals")
        for s, nm in (("a", "over" if tot else "home"), ("b", "under" if tot else "away")):
            o = g[g[f"ok_{s}"]].drop_duplicates("game_id", keep="first")
            r = o[f"risk_{s}"].sum()
            out[f"{rule}|{nm}"] = {"bets": int(len(o)), "units": round(float(o[f"units_{s}"].sum()), 2),
                                   "roi": round(float(o[f"units_{s}"].sum() / r), 4) if r else None}
    return out


def placebo(x: pd.DataFrame, runs: int = N_PLACEBO) -> dict:
    """{rule: {cut: [roi per run]}}: another game's model opinion at the same f."""
    out = {}
    nb = int(round(1.0 / F_BAND))
    for rule, g in x.groupby("rule", sort=False):
        g = g.reset_index(drop=True)
        gi, gids = pd.factorize(g["game_id"])
        n = len(gids)
        if n < 3:
            continue
        band = np.clip((g["f"].to_numpy(float) / F_BAND).astype(int), 0, nb - 1)
        cond_a = g["p_a"].to_numpy(float) / np.maximum(1.0 - g["p_push"].to_numpy(float), 1e-9)
        op = cond_a - g["novig_a"].to_numpy(float)
        T = pd.DataFrame({"g": gi, "b": band, "op": op}).groupby(["g", "b"])["op"].mean().unstack() \
            .reindex(index=range(n), columns=range(nb)).to_numpy()
        F = T.copy()
        for k in (1, 2):                                   # the nearest band within 0.04
            for sh in (k, -k):
                S = np.full_like(T, np.nan)
                if sh > 0:
                    S[:, sh:] = T[:, :-sh]
                else:
                    S[:, :sh] = T[:, -sh:]
                F = np.where(np.isnan(F), S, F)
        novig, push = g["novig_a"].to_numpy(float), g["p_push"].to_numpy(float)
        da, db = dec(g["price_a"]), dec(g["price_b"])
        ok_a, ok_b = g["ok_a"].to_numpy(bool), g["ok_b"].to_numpy(bool)
        ua, ub = g["units_a"].to_numpy(float), g["units_b"].to_numpy(float)
        ra, rb = g["risk_a"].to_numpy(float), g["risk_b"].to_numpy(float)
        res = {c: [] for c in CUTS}
        for seed in range(1, runs + 1):
            rng = np.random.default_rng(seed)
            perm = rng.permutation(n)
            donor = np.empty(n, dtype=int)
            donor[perm] = np.roll(perm, 1)                 # never itself
            o = F[donor[gi], band]
            p = np.clip(novig + o, 0.005, 0.995)
            pa, pb = p * (1.0 - push), (1.0 - p) * (1.0 - push)
            ea = np.where(ok_a & ~np.isnan(o), pa * (da - 1.0) - (1.0 - pa - push), -np.inf)
            eb = np.where(ok_b & ~np.isnan(o), pb * (db - 1.0) - (1.0 - pb - push), -np.inf)
            a = ea >= eb
            ev = np.where(a, ea, eb)
            u, r = np.where(a, ua, ub), np.where(a, ra, rb)
            for c in CUTS:
                idx = np.flatnonzero(ev >= c)
                if not len(idx):
                    res[c].append(np.nan)
                    continue
                _, first = np.unique(gi[idx], return_index=True)   # rows are in fetch order per game
                pick = idx[first]
                res[c].append(float(u[pick].sum() / r[pick].sum()))
        out[rule] = {c: np.asarray(v) for c, v in res.items()}
    return out


def grade_test(name: str, x: pd.DataFrame, results: dict) -> None:
    """The grid, the blind sides and the placebo for V1 and V2 of one test."""
    games = x.drop_duplicates("game_id")
    split = str(games["slate"].sort_values().iloc[(len(games) - 1) // 2])
    results[name] = {"split_date": split, "games": int(len(games)),
                     "slates": int(games["slate"].nunique()),
                     "first_slate": str(games["slate"].min()), "last_slate": str(games["slate"].max())}
    for v in ("V1", "V2"):
        xv = x if v == "V1" else x[x["v2"]].reset_index(drop=True)
        d = pick_sides(xv)
        counts = xv.groupby("rule").agg(quotes=("game_id", "size"), games=("game_id", "nunique"))
        bl = blind(xv)
        pl = placebo(xv)
        cells = []
        for rule in RULES:
            dr = d[d["rule"] == rule]
            for c in CUTS:
                b = first_signal(dr, c)
                s = summarise(b, split)
                s.update({"rule": rule, "cut": c})
                if s["bets"]:
                    nm = s["dominant"]
                    s["blind_same_side"] = bl.get(f"{rule}|{nm}", {}).get("roi")
                    pr = pl.get(rule, {}).get(c)
                    if pr is not None:
                        s["placebo_mean"] = round(float(np.nanmean(pr)), 4)
                        s["placebo_p95"] = round(float(np.nanpercentile(pr, 95)), 4)
                        s["placebo_runs_above"] = int(np.nansum(pr >= s["roi"]))
                cells.append(s)
                b.assign(test=name, variant=v, cut=c).to_parquet(
                    OUT / f"bets_{name}_{v}_{rule}_{c:.2f}.parquet", index=False)
        results[name][v] = {"eligible": {r: {"quotes": int(counts.loc[r, "quotes"]), "games": int(counts.loc[r, "games"])}
                                         for r in counts.index},
                            "blind": bl, "cells": cells}
        tab = pd.DataFrame(cells)
        cols = [c for c in ("rule", "cut", "bets", "w", "l", "p", "units", "risked", "roi", "ci_lo", "ci_hi",
                            "early_n", "early_roi", "late_n", "late_roi", "price_min", "price_med",
                            "price_max", "dominant", "blind_same_side", "placebo_mean", "placebo_p95",
                            "placebo_runs_above", "mean_ev") if c in tab.columns]
        print(f"\n=== TEST {name} / {v}: {len(games)} games, slates {results[name]['first_slate']} .. "
              f"{results[name]['last_slate']}, early/late split after {split} ===")
        print("eligible:", {r: (int(counts.loc[r, 'quotes']), int(counts.loc[r, 'games'])) for r in counts.index})
        print("blind:", {k: (v_["bets"], v_["roi"]) for k, v_ in bl.items()})
        print(tab[cols].to_string(index=False))


def main() -> int:
    pd.set_option("display.width", 320)
    pd.set_option("display.max_columns", 60)
    ginfo = pd.read_parquet(OUT / "ginfo.parquet")
    g25 = pd.read_parquet(OUT / "games_2025.parquet")
    tr = pd.read_parquet(OUT / "train_states.parquet")
    tr["gkey"] = tr["cfbd"]
    q = pd.read_parquet(OUT / "quotes.parquet")
    q["stamp_s"], q["fetch_s"] = secs(q["stamp"]), secs(q["fetch"])
    print(f"quotes with no stamp or no fetch time (dropped): {int((q.stamp_s.isna() | q.fetch_s.isna()).sum())}")
    q = q[q["stamp_s"].notna() & q["fetch_s"].notna()]
    results: dict = {"definitions": {"cuts": CUTS, "confirm_s": CONFIRM_S, "fresh_before_s": FRESH_BEFORE_S,
                                     "age_max_s": AGE_MAX_S, "price_floor": PRICE_FLOOR}}

    # block of every 2025 odds game row
    blk = {}
    for _, r in g25[g25["clean"]].iterrows():
        for gid in filter(None, r["game_ids"].split("|")):
            blk[gid] = r["block"]

    # ── fits and out-of-sample calibration ──────────────────────────────────
    fits = {"A": fit_models(tr), "B1": fit_models(tr[tr["block"] == "early"]),
            "B2": fit_models(tr[tr["block"] == "late"])}
    results["fits"] = {k: {t: m.describe() for t, m in v.items()} for k, v in fits.items()}
    for k, v in fits.items():
        print(f"\nfit {k}: margin {v['margin'].describe()}\n       total  {v['total'].describe()}")
    cal = {"B1 (fit weeks 1-7, read on weeks 8+)": calibration(fits["B1"], tr[tr["block"] == "late"]),
           "B2 (fit weeks 8+, read on weeks 1-7)": calibration(fits["B2"], tr[tr["block"] == "early"])}
    st26 = pd.read_parquet(OUT / "st_2026.parquet").merge(
        ginfo[["game_id", "fh", "fa", "sp_pre", "T_pre"]], on="game_id")
    st26 = st26[st26["period"].between(1, 4) & st26["fh"].notna() & st26["T_pre"].notna()].copy()
    st26["f"] = st26["secs_left"] / REG_S
    st26["m"], st26["t"] = st26["home_score"] - st26["away_score"], st26["home_score"] + st26["away_score"]
    st26["mu_pre"] = -st26["sp_pre"]
    st26["final_margin"], st26["final_total"] = st26["fh"] - st26["fa"], st26["fh"] + st26["fa"]
    st26["gkey"] = st26["game_id"]
    cal["A (fit 2025, read on the 2026 logged states)"] = calibration(fits["A"], st26)
    results["calibration"] = {k: v.to_dict(orient="records") for k, v in cal.items()}
    for k, v in cal.items():
        print(f"\ncalibration, {k}:\n{v.to_string(index=False)}")

    # ── quotes to states, eligibility ───────────────────────────────────────
    log: dict = {}
    x25 = eligibility(states_2025(q[q["season"] == 2025]), ginfo, "2025 replay", log)
    x26 = eligibility(states_2026(q[q["season"] == 2026]), ginfo, "2026 live", log)
    results["eligibility"] = log
    for k, v in log.items():
        print(f"\n{k}:")
        for kk, vv in v.items():
            print(f"   {kk}: {vv:,}")
    x25["block"] = x25["game_id"].map(blk)
    print("2025 eligible quotes by block:", x25.groupby("block").agg(q=("game_id", "size"), g=("game_id", "nunique")).to_dict())
    print("prior source of the eligible games:",
          pd.concat([x25, x26]).drop_duplicates("game_id").groupby(["season", "prior_src"]).size().to_dict())

    tests = {"A": (x26, fits["A"]), "B1": (x25[x25["block"] == "late"], fits["B1"]),
             "B2": (x25[x25["block"] == "early"], fits["B2"])}
    for name, (e, mdl) in tests.items():
        px = price_quotes(e, mdl)
        px.drop(columns=[c for c in ("stamp", "fetch") if c in px.columns]).to_parquet(OUT / f"priced_{name}.parquet", index=False)
        grade_test(name, px, results)
    # the in-sample replay priced by the all-2025 fit: ONLY the night table reads it
    price_quotes(x25, fits["A"]).drop(columns=["stamp", "fetch"], errors="ignore").to_parquet(
        OUT / "priced_2025_insample.parquet", index=False)
    (OUT / "results.json").write_text(json.dumps(results, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
