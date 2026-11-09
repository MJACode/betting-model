"""
NBA in-play game-state model: live spreads and the live moneyline.

LIVE, real money (mike, 2026-10-17: "Yes We are betting live models";
CLAUDE.md section 2). The research is docs/nba_models_2026.md section 7, family
IG-2; its lab is scripts/nba_ingame_ig2.py, which imports everything below.
This module is the ONE copy of the state features, the walk-forward fit, the
pricing, the eligibility rule and the decision rule. The loop that runs it is
nba_live/gameday.py.

THREE MODELS, ONE PER GRADED CELL (pooled 2021-22..2025-26 at bought in-play
prices, best of the 8 deciding books, -200 floor; scripts/nba_ingame_ig2.py
--grid, the house standard of section 6.7):

    nba_live_spread_h1   spread, Q1-Q2, EV >= 0.05   1,475 bets  +103.6 units  +6.2%
                         95% interval +1.4..+11.1, 4 of 5 seasons positive
    nba_live_spread_q3   spread, Q3, EV >= 0.05      1,055 bets   +79.6 units  +6.7%
                         95% interval +1.2..+12.6, 5 of 5
    nba_live_moneyline   moneyline, Q3, EV >= 0.08     545 bets   +49.6 units +15.8%
                         95% interval +3.8..+27.4, 5 of 5 (mostly underdogs)

  Why the spread is two models and not one. The lab bets a game's spread once
  in Q1-Q2 AND again in Q3: 269 of its games carry both, 208 on the same side.
  The platform identifies an in-play pick by (game, model, side): the live lock
  (models.scorer._locked_live_lanes), the unique indexes uq_picks_one_live_row
  and uq_picks_one_bet_per_publish_lock, and the publish key
  (tracking.publish_keys.live_lock_key_sql). Under one model id the 208
  same-side Q3 bets could not be stored or announced. One id per graded cell
  keeps every one of them and gives each cell its own record.

THE WARNING SIGNS, STATED PLAINLY (section 7.3, IG-2's grid result). The
profit may be stale soft-book quotes rather than prices a bettor can take:
  * without outlier prices (a price 20+ cents better than the next book's, or
    a number no other book hangs; about half of every cell's bets) the units
    fall to +21.7 (first-half spreads), +42.7 (third-quarter spreads) and -4.1
    / +8.0 (third-quarter moneylines at 0.05 / 0.08);
  * bets on the side that had just outscored its opponent in the 2 minutes
    before the quote earn more in every cell (the books' own lag);
  * DraftKings alone LOSES in 2025-26 in all six passing cells (-1.1% to
    -11.9%); the best of 8 books, quoted up to 60 s apart, picks the price that
    has moved least;
  * the information test found the foul inputs add nothing measurable, and
    against the deciding books' own moneyline prices the model adds nothing.
  That is why the live rule must be FAITHFUL to the graded one and enforce
  freshness against the LIVE score, and why it is judged on its live record.

THE RULE (the lab's docstring holds every definition; this is its live form):
  ELIGIBLE QUOTE  a deciding book's quote (config.BEST_LINE_BOOKMAKERS) on h2h
                  or spreads, coherent (implied sum 1.00-1.15), with a
                  coherent Pinnacle quote on the same game and market in the
                  same fetch stamped within 60 s, no point scored between the
                  quote's stamp (the book's own last_update) and the moment the
                  feed served it, and none between Pinnacle's stamp and then.
  PHASES          Q1-Q2: periods 1-2, live or the break after Q1. Q3: period
                  3, live or the break after it. Halftime is not a phase.
  DECISION        once per (game, model): the FIRST fetch in the phase that
                  carries an eligible quote. Every eligible quote in that
                  fetch is an offer, each priced at the state at its OWN stamp.
                  The side is the one whose best offer has the higher model EV
                  (chosen before the price floor, as the lab chose it); the bet
                  is the best-EV offer on that side at -200 or better if its EV
                  is at least the cell's cut, otherwise a no-bet decision. A
                  later fetch in the phase is never used, whatever its EV.
  THE MODEL       final home margin ~ Normal(m + E[R], sqrt(s1 f + s0)), with
                  f = seconds left / 2880, m = the margin so far, and
                    E[R] = b1 f mu_pre + b2 f + b3 m + b4 m f
                         + b5 pen_diff pl + b6 tf_diff pl
                         + b7 trouble_diff f + b8 out_diff f + b9 top_diff f
                  mu_pre is the home margin Pinnacle's last pre-tip coherent
                  spread implies, solved through the empirical distribution of
                  (final margin + Pinnacle's closing spread) on earlier seasons.
                  Moneyline P(home) = Phi(mean / sd); a spread offer is priced
                  with integer continuity, pushes at whole numbers.
  EV              per unit risked with a push refunded (the lab's EV,
                  scripts.nba_game_harness.with_ev).

THE ARTIFACT (ARTIFACT_PATH, built by scripts/nba_live_ingame_build.py): the
state model fit on every season before 2026-27 (2020-21..2025-26, the lab's
walk-forward rule: season S is predicted by a fit on seasons before S), and the
sample of (final margin + Pinnacle's closing spread) per season that prices the
pre-game prior. It must be refitted before 2027-28: the loop refuses a season
the artifact was not fitted for.
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import config
from scripts import nba_game_harness as H
from scripts.nba_game_market_lab import norm_cdf, threshold

SPORT = "NBA"
ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/nba_live_ingame_20261018_001323.pkl"
ARTIFACT_KIND = "nba_live_ingame"

PHASES = ("Q1-Q2", "Q3", "Q4")
_WINDOW = {"Q1-Q2": "Q1-Q2", "Q3": "Q3", "Q4": "Q4 6+ min"}
MARKETS = ("h2h", "spreads")
REG_S, PERIOD_S = 2880.0, 720.0
S0_FLOOR = 0.25
GRID_STEP_S = 30
TRAIN_SECS = (360, 2850)
CORE = ["x_mu_pre", "x_f", "x_m", "x_mf"]
FOULS = ["x_pen", "x_tf", "x_trouble", "x_out", "x_top"]
FEATURES = CORE + FOULS


@dataclass(frozen=True)
class Cell:
    """One graded cell, shipped as one model."""
    model_id: str
    market: str          # 'spreads' or 'h2h'
    phase: str           # 'Q1-Q2' or 'Q3'
    cut: float           # EV per unit risked, push refunded


CELLS: tuple[Cell, ...] = (
    Cell("nba_live_spread_h1", "spreads", "Q1-Q2", 0.05),
    Cell("nba_live_spread_q3", "spreads", "Q3", 0.05),
    Cell("nba_live_moneyline", "h2h", "Q3", 0.08),
)
MODEL_IDS: tuple[str, ...] = tuple(c.model_id for c in CELLS)
CELL_BY_MODEL: dict[str, Cell] = {c.model_id: c for c in CELLS}


# ── the decision windows (moved here from scripts/nba_ingame_staleness) ────

WINDOWS = ("Q1-Q2", "Q2", "halftime", "Q3", "Q4 6+ min")


def window_of(q: pd.DataFrame) -> pd.DataFrame:
    """Boolean column per decision window (Q2 is a part of Q1-Q2), from each
    row's own `period`, `phase` and `clock_s` (the state at its stamp)."""
    per, ph = q["period"], q["phase"]
    return pd.DataFrame({
        "Q1-Q2": per.isin([1, 2]) & ph.isin(["live", "break"]),
        "Q2": (per == 2) & ph.isin(["live", "break"]),
        "halftime": ph == "halftime",
        "Q3": (per == 3) & ph.isin(["live", "break"]),
        "Q4 6+ min": (per == 4) & (ph == "live") & (q["clock_s"] >= 360),
    }, index=q.index)


def phase_label(q: pd.DataFrame) -> pd.Series:
    """'Q1-Q2' / 'Q3' / 'Q4' from the windows above; '' outside."""
    w = window_of(q)
    return pd.Series(np.select([w[_WINDOW[p]].to_numpy() for p in PHASES], list(PHASES), ""),
                     index=q.index)


# ── eligibility and the first eligible fetch ───────────────────────────────

def with_pin_freshness(q: pd.DataFrame) -> pd.DataFrame:
    """pin_pts_since: points scored between the paired Pinnacle quote's stamp
    and its served_at (from Pinnacle's own row in the same fetch)."""
    pin = q[q["book"] == H.SHARP].set_index(["game_id", "market", "fetch_at", "stamp"])
    pin = pin[~pin.index.duplicated()]["pts_since_stamp"]
    key = pd.MultiIndex.from_frame(q[["game_id", "market", "fetch_at", "pin_stamp"]])
    return q.assign(pin_pts_since=pin.reindex(key).to_numpy())


def eligible(q: pd.DataFrame) -> pd.DataFrame:
    """Deciding-book quotes that pass section 7.1's freshness rule, in a phase."""
    if "pin_pts_since" not in q:
        q = with_pin_freshness(q)
    if "phase_ig2" not in q:
        q = q.assign(phase_ig2=phase_label(q))
    m = (q["book"].isin(H.BETTABLE) & q["market"].isin(MARKETS) & q["coherent"].astype(bool)
         & q["pin_fa"].notna() & (q["pts_since_stamp"] == 0) & (q["pin_pts_since"] == 0)
         & (q["phase_ig2"] != ""))
    return q[m].copy()


def decision_quotes(el: pd.DataFrame) -> pd.DataFrame:
    """The eligible quotes of the FIRST eligible fetch per (game, market, phase)."""
    first = el.groupby(["game_id", "market", "phase_ig2"])["fetch_at"].transform("min")
    return el[el["fetch_at"] == first].copy()


# ── features and the state model ───────────────────────────────────────────

def features(df: pd.DataFrame) -> pd.DataFrame:
    """The model's inputs from a state frame carrying secs_left, clock_s,
    period, h_pts, a_pts, mu_pre, team fouls in the period and the top
    players' fouls. Adds x_* columns, m and f."""
    f = df["secs_left"].to_numpy(float) / REG_S
    pl = df["clock_s"].to_numpy(float) / PERIOD_S
    m = (df["h_pts"] - df["a_pts"]).to_numpy(float)
    per = df["period"].to_numpy(float)
    htf, atf = df["h_tf_period"].fillna(0).to_numpy(float), df["a_tf_period"].fillna(0).to_numpy(float)
    ht = np.column_stack([df[f"h_top{k}_pf"].fillna(0).to_numpy(float) for k in (1, 2, 3)])
    at = np.column_stack([df[f"a_top{k}_pf"].fillna(0).to_numpy(float) for k in (1, 2, 3)])
    trouble = (at >= per[:, None] + 1).sum(1) - (ht >= per[:, None] + 1).sum(1)
    out_ = (at >= 6).sum(1) - (ht >= 6).sum(1)
    top = at.sum(1) - ht.sum(1)
    return df.assign(
        f=f, m=m,
        x_mu_pre=f * df["mu_pre"].to_numpy(float), x_f=f, x_m=m, x_mf=m * f,
        x_pen=((atf >= 5).astype(float) - (htf >= 5).astype(float)) * pl,
        x_tf=(atf - htf) * pl,
        x_trouble=trouble * f, x_out=out_ * f, x_top=top * f)


class StateModel:
    """Final home margin ~ Normal(m + X b, sqrt(s1 f + s0)), fit on seasons < S."""

    def __init__(self, cols=FEATURES):
        self.cols = list(cols)
        self.beta = self.s1 = self.s0 = None
        self.S = None
        self.n_train = 0

    def fit(self, train: pd.DataFrame, S: int, allow_own_season: bool = False) -> "StateModel":
        seasons = set(int(s) for s in train["season"].unique())
        if allow_own_season:
            if seasons != {S}:
                raise ValueError(f"an in-sample fit takes season {S} alone, got {sorted(seasons)}")
        elif any(s >= S for s in seasons):
            raise ValueError(f"walk-forward: a model for season {S} cannot see seasons {sorted(seasons)}")
        X = train[self.cols].to_numpy(float)
        y = (train["final_margin"] - train["m"]).to_numpy(float)
        f = train["f"].to_numpy(float)
        w = 1.0 / np.maximum(f, 1e-3)
        for _ in range(2):
            sw = np.sqrt(w)
            self.beta = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)[0]
            r2 = (y - X @ self.beta) ** 2
            A = np.column_stack([f, np.ones_like(f)])
            s1, s0 = np.linalg.lstsq(A, r2, rcond=None)[0]
            self.s1, self.s0 = max(float(s1), 1e-6), max(float(s0), S0_FLOOR)
            w = 1.0 / (self.s1 * f + self.s0)
        self.S, self.n_train = S, len(train)
        return self

    def predict(self, df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        """(mean final home margin, sd) at each state."""
        mean = df["m"].to_numpy(float) + df[self.cols].to_numpy(float) @ self.beta
        sd = np.sqrt(self.s1 * df["f"].to_numpy(float) + self.s0)
        return mean, sd

    def p_home(self, df: pd.DataFrame) -> np.ndarray:
        return p_home_from(*self.predict(df))

    def to_dict(self) -> dict:
        return {"cols": list(self.cols), "beta": [float(b) for b in self.beta],
                "s1": float(self.s1), "s0": float(self.s0), "S": int(self.S),
                "n_train": int(self.n_train)}

    @classmethod
    def from_dict(cls, d: dict) -> "StateModel":
        m = cls(d["cols"])
        m.beta = np.asarray(d["beta"], float)
        m.s1, m.s0, m.S, m.n_train = float(d["s1"]), float(d["s0"]), int(d["S"]), int(d["n_train"])
        return m


def p_home_from(mean, sd) -> np.ndarray:
    return norm_cdf(np.asarray(mean, float) / np.asarray(sd, float))


def grid_states(tl: pd.DataFrame, step: int = GRID_STEP_S, secs=TRAIN_SECS) -> pd.DataFrame:
    """Each game's state every `step` s of regulation game time: the latest play
    (by game time) at or before it, keeping secs_left in [secs[0], secs[1]].
    These are the training rows."""
    s = tl.dropna(subset=["game_s"]).sort_values(["game_s", "wc", "play_no"], kind="stable")
    g = np.arange(step, int(REG_S), step, dtype=float)
    left = pd.DataFrame({"game_id": np.repeat(s["game_id"].unique(), len(g)),
                         "g": np.tile(g, s["game_id"].nunique())}).sort_values("g", kind="stable")
    x = pd.merge_asof(left, s, left_on="g", right_on="game_s", by="game_id", direction="backward")
    x = x.dropna(subset=["period"])
    x = x[x["period"] <= 4]
    x["secs_left"] = x["clock_s"] + PERIOD_S * (4 - x["period"])
    x = x[(x["secs_left"] >= secs[0]) & (x["secs_left"] <= secs[1])]
    return x.drop_duplicates(["game_id", "play_no"]).drop(columns="g").reset_index(drop=True)


def models_by_season(train: pd.DataFrame, cols=FEATURES, seasons=(2021, 2022, 2023, 2024, 2025, 2026)) -> dict:
    """season -> StateModel fit on seasons before it (the first: on itself, in-sample)."""
    out = {}
    for S in seasons:
        prior = train[train["season"] < S]
        if len(prior):
            out[S] = StateModel(cols).fit(prior, S)
        else:
            out[S] = StateModel(cols).fit(train[train["season"] == S], S, allow_own_season=True)
    return out


def apply_model(df: pd.DataFrame, models: dict, prefix: str = "") -> pd.DataFrame:
    """mean / sd / p_home per row from its own season's model."""
    mean = np.full(len(df), np.nan)
    sd = np.full(len(df), np.nan)
    for S, mdl in models.items():
        k = (df["season"] == S).to_numpy()
        if k.any():
            mean[k], sd[k] = mdl.predict(df[k])
    return df.assign(**{f"{prefix}mean": mean, f"{prefix}sd": sd,
                        f"{prefix}p_home": p_home_from(mean, sd)})


# ── offers, pricing and the side ───────────────────────────────────────────

def offer_rows(dec: pd.DataFrame) -> pd.DataFrame:
    """Two rows per decision quote (home/away), with T = served_at and the
    points each side scored in the 120 s before the stamp."""
    base = dec.assign(T=dec["served_at"], pts120_h=dec["h_pts"] - dec["h_pts_m120"],
                      pts120_a=dec["a_pts"] - dec["a_pts_m120"])
    a = base.assign(side="home", price=base["price_a"])
    b = base.assign(side="away", price=base["price_b"])
    return pd.concat([a, b], ignore_index=True)


def priced(off: pd.DataFrame, mean, sd, p_home) -> pd.DataFrame:
    pw, pp = H.side_probs(off["market"].to_numpy(), off["side"].to_numpy(), off["line"].to_numpy(),
                          mu=np.asarray(mean, float), sigma=np.asarray(sd, float),
                          p_home=np.asarray(p_home, float))
    return H.with_ev(off.assign(p_win=pw, p_push=pp))


def with_side_pick(c: pd.DataFrame) -> pd.DataFrame:
    """side_pick per (game, market): the side whose best deciding offer has the
    higher EV under `c`'s own prices (the side the model favours). Read over
    every deciding offer, BEFORE any price floor, as the lab read it."""
    best = c[c["book"].isin(H.BETTABLE)].groupby(["game_id", "market", "side"])["ev"].max().unstack()
    for s in ("home", "away"):
        if s not in best:
            best[s] = np.nan
    pick = pd.Series(np.where(best["home"].fillna(-np.inf) >= best["away"].fillna(-np.inf), "home", "away"),
                     index=best.index, name="side_pick").reset_index()
    return c.drop(columns="side_pick", errors="ignore").merge(pick, on=["game_id", "market"], how="left")


# ── the pre-game prior ─────────────────────────────────────────────────────

def close_resid_frame(rows) -> pd.DataFrame:
    """(season, market, resid) from the artifact's [(season, resid), ...]:
    final home margin plus Pinnacle's closing home spread."""
    r = pd.DataFrame(rows, columns=["season", "resid"])
    return r.assign(season=r["season"].astype(int), market="spreads")[["season", "market", "resid"]]


_DIST_CACHE: dict = {}


def prior_dist(resid: pd.DataFrame, season: int, key=None):
    """The empirical spread distribution that prices season `season`'s prior:
    scripts.nba_game_harness.dist_by_season on the residuals, which uses the
    seasons BEFORE `season` (the lab's close_dist)."""
    k = (key, len(resid), int(season))
    if key is None or k not in _DIST_CACHE:
        d = H.dist_by_season(resid, [int(season)]).get((int(season), "spreads"))
        if d is None:
            raise ValueError(f"no spread residuals to price season {season}'s prior")
        if key is None:
            return d
        _DIST_CACHE[k] = d
    return _DIST_CACHE[k]


def solve_prior(close: pd.DataFrame, dist_for) -> pd.DataFrame:
    """(game_id, season, mu_pre) from Pinnacle's spread close per game
    (close_line = its home number, close_fa = its no-vig home share).
    `dist_for(season)` returns the season's ResidDist."""
    c = close[close["market"] == "spreads"].copy() if "market" in close else close.copy()
    if c.empty:
        return pd.DataFrame(columns=["game_id", "season", "mu_pre"])
    sig = np.array([dist_for(int(s)) for s in c["season"]], dtype=object)
    c["mu_pre"] = H.solve_any(threshold("spreads", c["close_line"]), c["close_fa"].to_numpy(float), sig)
    return c[["game_id", "season", "mu_pre"]].reset_index(drop=True)


# ── the decision ───────────────────────────────────────────────────────────

@dataclass
class Decision:
    """One (game, model) decided once: a bet, or the reason there is none."""
    model_id: str
    game_id: str
    market: str
    phase: str
    season: int | None
    fetch_at: object
    served_at: object
    bet: bool
    reason: str
    side: str | None = None          # 'home' / 'away' (the side the model favours)
    book: str | None = None
    line: float | None = None        # the stored HOME number for a spread, None for h2h
    price: float | None = None
    stamp: object = None             # the deciding quote's own last_update
    ev: float | None = None          # push refunded, the lab's EV
    p_win: float | None = None
    p_push: float | None = None
    mean: float | None = None        # model's mean final home margin at the stamp
    sd: float | None = None
    p_home: float | None = None
    mu_pre: float | None = None
    period: int | None = None
    clock_s: float | None = None
    h_pts: int | None = None
    a_pts: int | None = None
    offers: int = 0
    best_ev: float | None = None     # best EV on the side the model favours, any book
    dk_price: float | None = None    # DraftKings' price on the bet's side at the bet's number
    pts120_side: float | None = None
    extra: dict = field(default_factory=dict)


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(x) else x


def decide(rows: pd.DataFrame, prior: pd.DataFrame, model: StateModel, *,
           cells=CELLS, decided=frozenset(), books=None, floors: dict | None = None) -> list[Decision]:
    """Decide every (game, model) whose phase holds an eligible quote in
    `rows` and that is not already in `decided` ({(game_id, model_id)}).

    rows    quote-state rows in the lab's schema (scripts/nba_ingame_data.py):
            one or more fetches; the FIRST fetch with an eligible quote per
            (game, model) decides it. Live, the loop passes one fetch at a time.
    prior   (game_id, mu_pre)
    model   the StateModel for the rows' season: the live artifact's live, the
            lab's walk-forward model in the replay.
    floors  model_id -> price floor; default config.min_odds_for(model_id).

    Pure given its inputs: the live loop and the replay of the lab call it."""
    books = tuple(config.BEST_LINE_BOOKMAKERS) if books is None else tuple(books)
    out: list[Decision] = []
    if rows is None or rows.empty:
        return out
    q = rows
    if "pin_pts_since" not in q:
        q = with_pin_freshness(q)
    if "phase_ig2" not in q:
        q = q.assign(phase_ig2=phase_label(q))
    el = eligible(q)
    if el.empty:
        return out
    pri = prior.drop_duplicates("game_id").set_index("game_id")["mu_pre"] if len(prior) else pd.Series(dtype=float)
    for cell in cells:
        c = el[(el["market"] == cell.market) & (el["phase_ig2"] == cell.phase)]
        if c.empty:
            continue
        c = c[[(g, cell.model_id) not in decided for g in c["game_id"]]]
        if c.empty:
            continue
        dec = decision_quotes(c)
        dec = dec.assign(mu_pre=dec["game_id"].map(pri))
        for gid, g in dec[dec["mu_pre"].isna()].groupby("game_id", sort=True):
            r0 = g.iloc[0]
            out.append(Decision(cell.model_id, gid, cell.market, cell.phase, _season(r0),
                                r0["fetch_at"], r0["served_at"], False, "no_pregame_spread",
                                offers=len(g)))
        dec = dec[dec["mu_pre"].notna()]
        if dec.empty:
            continue
        d = features(dec)
        mean, sd = model.predict(d)
        d = d.assign(mean=mean, sd=sd, p_home=p_home_from(mean, sd))
        off = offer_rows(d)
        # EV to 12 places before any comparison: two books at the same number
        # and price, stamped in the same state, carry the same EV, but a row
        # priced in a smaller frame can differ in the last bit and win a tie
        # the lab gave to the earlier book (replay, 2026-10-17: 2 of 1,475
        # first-half bets). Nothing else is within 1e-12 of a tie.
        cand = with_side_pick(priced(off, off["mean"], off["sd"], off["p_home"]).pipe(
            lambda x: x.assign(ev=x["ev"].round(12))))
        floor = (floors or {}).get(cell.model_id, config.min_odds_for(cell.model_id))
        chosen = H.choose(cand, cell.cut, books=books, sides=["model"], floor=floor)
        by_game = {r.game_id: r for r in chosen.itertuples(index=False)}
        for gid, g in cand.groupby("game_id", sort=True):
            side = g["side_pick"].iloc[0]
            mine = g[g["side"] == side]
            r0 = mine.sort_values(["ev"], ascending=False).iloc[0]
            best_ev = _num(r0["ev"])
            n_off = int(len(g) // 2)
            b = by_game.get(gid)
            if b is None:
                floor_ok = mine[mine["price"] >= floor]
                if floor_ok.empty:
                    why = f"no_offer_at_floor:{side} best {r0['price']:+.0f}"
                else:
                    why = f"ev_below_cut:{side} best ev {floor_ok['ev'].max():.4f} < {cell.cut:.2f}"
                out.append(Decision(cell.model_id, gid, cell.market, cell.phase, _season(r0),
                                    r0["fetch_at"], r0["served_at"], False, why, side=side,
                                    mean=_num(r0["mean"]), sd=_num(r0["sd"]), p_home=_num(r0["p_home"]),
                                    mu_pre=_num(r0["mu_pre"]), period=_int(r0["period"]),
                                    clock_s=_num(r0["clock_s"]), h_pts=_int(r0["h_pts"]),
                                    a_pts=_int(r0["a_pts"]), offers=n_off, best_ev=best_ev))
                continue
            dk = g[(g["book"] == H.DK) & (g["side"] == b.side)
                   & ((g["market"] == "h2h") | np.isclose(g["line"].astype(float), float(b.line)
                                                         if b.line == b.line else np.nan))]
            dk_price = _num(dk["price"].iloc[0]) if len(dk) else None
            pts = (b.pts120_h - b.pts120_a) if b.side == "home" else (b.pts120_a - b.pts120_h)
            out.append(Decision(
                cell.model_id, gid, cell.market, cell.phase, _season(b), b.fetch_at, b.served_at,
                True, f"bet:{b.book} {b.side} {_fmt_line(b)} {b.price:+.0f}",
                side=b.side, book=b.book,
                line=(float(b.line) if cell.market == "spreads" else None),
                price=float(b.price), stamp=b.stamp, ev=float(b.ev), p_win=float(b.p_win),
                p_push=float(b.p_push), mean=_num(b.mean), sd=_num(b.sd), p_home=_num(b.p_home),
                mu_pre=_num(b.mu_pre), period=_int(b.period), clock_s=_num(b.clock_s),
                h_pts=_int(b.h_pts), a_pts=_int(b.a_pts), offers=n_off, best_ev=best_ev,
                dk_price=dk_price, pts120_side=_num(pts)))
    return out


def _season(r):
    try:
        v = r["season"] if isinstance(r, (pd.Series, dict)) else getattr(r, "season")
        return int(v)
    except Exception:  # noqa: BLE001
        return None


def _int(v):
    x = _num(v)
    return None if x is None else int(round(x))


def _fmt_line(b) -> str:
    if b.market != "spreads":
        return "ML"
    return f"{float(b.line):+g}"


# ── labels ─────────────────────────────────────────────────────────────────

def pick_label(d: Decision, home: str, away: str) -> str:
    """The bet as a person reads it: 'BOS -3.5 (live)' / 'BOS ML (live)'.

    A spread quotes the SIDE's own number. `line` is the stored HOME number
    (CLAUDE.md section 4), so an away pick shows its negation."""
    team = home if d.side == "home" else away
    if d.market == "h2h":
        return f"{team} ML (live)"
    num = float(d.line) if d.side == "home" else -float(d.line)
    num = 0.0 if num == 0 else num
    return f"{team} {num:+g} (live)"


# ── the artifact ───────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    """The committed artifact (ARTIFACT_PATH), else its copy in Supabase's
    model_artifacts table (models.trainer._restore_artifact), else raise."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    if not p.exists() and path is None:
        from data.db import get_connection
        from models.trainer import _restore_artifact
        conn = get_connection()
        try:
            got = _restore_artifact(conn, ARTIFACT_PATH)
        finally:
            conn.close()
        if got is None:
            raise FileNotFoundError(f"{ARTIFACT_PATH}: not on disk and not in model_artifacts")
        p = Path(got)
    with open(p, "rb") as fh:
        art = pickle.load(fh)
    if not isinstance(art, dict) or art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    return art


def live_model(art: dict, season: int) -> StateModel:
    """The state model for `season`; refuses a season it was not fitted for."""
    m = StateModel.from_dict(art["model"])
    if int(season) != m.S:
        raise ValueError(f"the artifact's state model is fitted for season {m.S}, not {season}: "
                         "refit it (scripts/nba_live_ingame_build.py) before betting this season")
    return m


def artifact_prior_dist(art: dict, season: int):
    return prior_dist(close_resid_frame(art["close_resid"]), season, key=art.get("built_at"))


def season_of(game_date) -> int:
    """NBA ending-year season label for an ET game date (CLAUDE.md section 4)."""
    d = pd.Timestamp(str(game_date)[:10])
    return int(d.year + 1 if d.month >= 7 else d.year)
