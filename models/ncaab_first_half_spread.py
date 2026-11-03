"""NCAAB first-half spread: `ncaab_first_half_spread`.

LIVE, real money (mike, 2026-11-02: "we need to build 1H and game lines ML and
Spread no matter what"; and the same day, "we do not need to wait 10 games ...
I want these models live now", so there is no games-played wait).

THE RULE (the NCAAB research's round 4, family A, market spreads_h1, snapshot
close, books best, cut 0.02, every game; its PREREGISTRATION.txt and
scripts/fh_lib.py, fh_prep.py, fh_score.py, fh_grade.py). About ten minutes
before each tip:

  1. M, the full-game consensus: the median over the bettable books of each
     book's newest full-game spread (the home number) stored at or before the
     moment, negated, so M is the home team's expected full-game margin.
  2. The expected first-half home margin is
         mu = a + b x M + (tau(home) - tau(away)) / 2
     a and b are ONE least-squares fit of the first-half home margin on the
     CLOSING full-game consensus over every earlier season (2021 through the
     last finished season), fitted once per season and frozen in the artifact.
     They are not refitted during the season.
     tau is each team's first-half tendency, shrunk and as of the moment (THE
     TEAM TERM, below).
  3. Every bettable book's first-half spread quote is priced through an
     empirical distribution of the first-half margin (THE DISTRIBUTION, below):
     q = P(home covers | no push) at the quote's home number, and both sides'
     edges are e_home = q - 1/decimal(home price), e_away = (1 - q) - 1/decimal
     (away price). The quote's side is the larger edge (a tie goes to home).
  4. The single best quote of the game is the one with the largest edge, ties
     to the alphabetically first book key. The game is bet there when that edge
     is above 0.02 (config.MODEL_EDGE_THRESHOLDS); otherwise it is decided with
     no bet. One decision a game, ever (CLAUDE.md 1c).

The edge is raw: the price's own implied probability, vig included, against
the model's P(win | no push). model_probability on the pick is that P(win | no
push), so decision_edge is exactly the edge the card cut on.

A FEED TYPO NEVER BECOMES A BET (models/ncaab_quote_bounds.py). A first-half
quote beyond +/-35, or priced beyond +/-100000, is not priced; a full-game line
outside its plausible range (a spread beyond +/-60, a total outside 90-220)
never enters a consensus. The dropped first-half quotes are listed on the
decision. A best edge above the data-error cap is not a bet: the game is
decided as edge_cap with none, and the card's run fails.

THE TEAM TERM. For every finished game with both halves stored and a closing
full-game consensus spread AND total (the research's sample requires both), the
home team's first-vs-second-half margin tilt is
    dm = (home h1 - away h1) - (home h2 - away h2) - (alpha + beta x Mc)
where h2 is period 2 only (overtime is excluded), Mc is the negated closing
consensus spread, and alpha / beta are one fit on the earlier seasons (frozen).
The home team carries +dm and the away team -dm. A team's tau at the moment is
    tau = (sum of this season's dm that ENDED, tip + 2.5 h, at or before the
           moment + 0.5 x sum of last season's dm)
          / (count of those + 0.5 x last season's count + 782.2)
782.2 is a method-of-moments shrinkage fitted on 2021-2023 (the research's
tilt_reliability.csv) and frozen. It is large: a 30-game team keeps about 4% of
its raw mean, so the term moves mu by at most about a quarter of a point.

THE DISTRIBUTION (the research's kernel table, fh_lib.fit_table). For each mean
m on a grid from -30 to +30 in steps of 0.25, the historical distribution of the
whole-point first-half margin over the training games whose a + b x Mc is near
m: Gaussian weights in that key with bandwidth 0.75, widened by x1.25 until the
weights sum to at least 500 games, each outcome shifted by round(m - key) when
widened. No smoothing over outcomes, so a level first half (about 4.4% of games
at mean 0) has whatever mass history shows. Probabilities interpolate linearly
between grid means. First halves can end level and have no overtime; a level
first half against a whole-number line is a push.

THE EVIDENCE (every game, 10-game rule off; grid.csv of the research): pooled
2023-24 to 2025-26, 1,253 bets, +68.07 units, +4.91%, date-resampled 95%
interval -0.30% to +10.63%. 2023-24 +6.06%, 2024-25 +2.80%, 2025-26 +7.19% on
243 bets. Cut 0.01 +81.36 units, 0.03 +35.65 units. Without the 10 best dates
+16.75 units. Prices -140 to +125. IT DID NOT CLEAR THE RESEARCH BAR: the
interval's lower bound is below zero. It is live on mike's instruction.

The pure functions here are shared by the card (scripts/ncaab_first_half_spread_card.py)
and the build's replay (scripts/ncaab_first_half_spread_build.py), so the
replay runs the card's own code path.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from models import ncaab_quote_bounds as qb

MODEL_ID = "ncaab_first_half_spread"
SPORT = "NCAAB"
MARKET = "spreads_h1"
REFERENCE_BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_KIND = "ncaab_first_half_spread"


def artifact_path(season: int) -> Path:
    return ROOT / f"models/saved/ncaab_first_half_spread_{int(season)}.json"


# The research's bettable books (fh_lib.BETTABLE): the full-game consensus is
# a median over these, and only these quotes are priced. Frozen with the
# model, not read from config: the consensus was fitted on exactly this set.
# The card bets only at the ones config.BEST_LINE_BOOKMAKERS still lists.
BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers",
         "hardrockbet", "betparx")

GAME_LEN = pd.Timedelta(hours=2.5)     # a game has ended this long after its tip

# The distribution table's shape (fh_lib.MARGIN_SPEC, fit_table defaults).
GRID = (-30.0, 30.0, 0.25)
SUPPORT = (-80, 80)
H0 = 0.75
NMIN = 500


# ── prices ───────────────────────────────────────────────────────────────────

def dec(a):
    """American -> decimal, vectorised."""
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


# ── the distribution ─────────────────────────────────────────────────────────

def grid() -> np.ndarray:
    lo, hi, step = GRID
    return np.arange(lo, hi + 0.0001, step)


def fit_table(outcome, key, weight=None, h0: float = H0, nmin: float = NMIN,
              means=None, support=None) -> dict:
    """The research's kernel table (fh_lib.fit_table), with an optional
    per-row count so a sample stored as (key, outcome, count) rebuilds the same
    table. `weight` = None is one row each, exactly the research's call.
    `means` / `support` default to this model's first-half margin grid and
    support (MARGIN_SPEC); the first-half total model
    (models/ncaab_first_half_total.py) passes its own (TOTAL_SPEC)."""
    outcome = np.asarray(outcome).astype(int)
    key = np.asarray(key, float)
    cnt = np.ones(len(outcome)) if weight is None else np.asarray(weight, float)
    g = grid() if means is None else np.asarray(means, float)
    klo, khi = SUPPORT if support is None else support
    nk = khi - klo + 1
    base_idx = np.clip(outcome, klo, khi) - klo
    pmf = np.zeros((len(g), nk))
    for i, m in enumerate(g):
        h = h0
        while True:
            w = np.exp(-0.5 * ((key - m) / h) ** 2) * cnt
            if w.sum() >= nmin or h > 20:
                break
            h *= 1.25
        if h > h0:
            idx = np.clip(outcome + np.round(m - key).astype(int), klo, khi) - klo
        else:
            idx = base_idx
        p = np.bincount(idx, weights=w, minlength=nk)
        pmf[i] = p / p.sum()
    ge = np.cumsum(pmf[:, ::-1], axis=1)[:, ::-1]   # P(X >= k)
    return {"pmf": pmf, "ge": ge, "grid": g, "klo": klo, "khi": khi, "step": g[1] - g[0]}


def _interp(T: dict, mu, col, which: str):
    mu = np.asarray(mu, float)
    bad = ~np.isfinite(mu)
    g = T["grid"]
    x = np.clip((np.where(bad, g[0], mu) - g[0]) / T["step"], 0, len(g) - 1 - 1e-9)
    i0 = np.floor(x).astype(int)
    f = x - i0
    A = T[which]
    out = A[i0, col] * (1 - f) + A[i0 + 1, col] * f
    return np.where(bad, np.nan, out)


def probs(mu, thresh, T: dict):
    """P(X > thresh), P(X == thresh) (whole-number thresh only), P(X < thresh)
    at mean mu (fh_lib.probs)."""
    mu, thresh = np.broadcast_arrays(np.asarray(mu, float), np.asarray(thresh, float))
    klo, khi = T["klo"], T["khi"]
    nk = khi - klo + 1
    integer = np.isclose(thresh, np.round(thresh))
    m = np.where(integer, np.round(thresh) + 1, np.ceil(thresh)).astype(int)
    col = np.clip(m - klo, 0, nk - 1)
    pw = _interp(T, mu, col, "ge")
    pw = np.where(m > khi, 0.0, np.where(m < klo, 1.0, pw))
    t = np.round(thresh).astype(int)
    pp = np.where(integer & (t >= klo) & (t <= khi),
                  _interp(T, mu, np.clip(t - klo, 0, nk - 1), "pmf"), 0.0)
    return pw, pp, 1 - pw - pp


def price_quote(mu, line, p_home, p_away, T: dict):
    """Both sides of a first-half spread quote at mean mu (fh_lib.price_quote,
    market spreads_h1). `line` is the HOME number: home covers when the
    first-half margin > -line. -> (side 1 = home / 2 = away, edge, P(side wins |
    no push))."""
    pw1, pp1, pl1 = probs(mu, -np.asarray(line, float), T)
    q1 = pw1 / np.maximum(pw1 + pl1, 1e-12)
    e1 = q1 - 1 / dec(p_home)
    e2 = (1 - q1) - 1 / dec(p_away)
    side = np.where(e1 >= e2, 1, 2)
    edge = np.maximum(e1, e2)
    return side, edge, np.where(side == 1, q1, 1 - q1)


# ── the full-game consensus ──────────────────────────────────────────────────

def asof_consensus(rows: pd.DataFrame, cutoff: pd.DataFrame, books=BOOKS,
                   market: str | None = None) -> pd.DataFrame:
    """Median over `books` of each book's newest full-game line at or before
    each game's cutoff.

    market ('spreads' or 'totals') drops a book whose newest line is outside
    that market's plausible range (models/ncaab_quote_bounds.py) before the
    median: that book is not in the consensus, and its older line is not used
    instead. With no market nothing is dropped (a caller that has not said
    which market its lines are).

    rows:   game_id, bookmaker, ts (the row's snapshot_at, the book's own time,
            tz-aware), line (spread_home or total_line), optional order (a
            tie-break after ts, e.g. created_at).
    cutoff: game_id, cutoff (tz-aware).
    -> game_id, cons (the median line), nb (books in it). A game with no book
    has no row.

    ONE definition for the two places it is read: the as-of consensus at a
    decision (cutoff = the decision moment) and a finished game's closing
    consensus (cutoff = its tip), the research's M_asof (fh_prep.py) and
    spreads_c_cons / totals_c_cons (build_lines.py, prep_odds.py).
    """
    if rows is None or not len(rows) or cutoff is None or not len(cutoff):
        return pd.DataFrame(columns=["game_id", "cons", "nb"])
    x = rows[rows["bookmaker"].isin(list(books)) & rows["line"].notna()]
    x = x.merge(cutoff[["game_id", "cutoff"]], on="game_id")
    x = x[x["ts"] <= x["cutoff"]]
    if not len(x):
        return pd.DataFrame(columns=["game_id", "cons", "nb"])
    order = ["ts", "order"] if "order" in x.columns else ["ts"]
    x = x.sort_values(order, kind="mergesort").drop_duplicates(["game_id", "bookmaker"], keep="last")
    if market is not None:
        x = qb.split(x, market, "line", ())[0]
    if not len(x):
        return pd.DataFrame(columns=["game_id", "cons", "nb"])
    out = x.groupby("game_id")["line"].agg(cons="median", nb="size").reset_index()
    return out


# ── the halves ───────────────────────────────────────────────────────────────

def valid_halves(per: pd.DataFrame, finals: pd.DataFrame) -> pd.DataFrame:
    """Per game: h1_home, h1_away (period 1), h2_home, h2_away (period 2 only;
    overtime is never in either half).

    per:    game_id, period, home_points, away_points (ncaab_period_scores).
    finals: game_id, home_score, away_score (games).
    A game counts when its periods are 1..n with n >= 2 and add up to the
    stored final, the rule the settlement reads too
    (tracking/paper_tracker._ncaab_first_half_points). On 2021-2026 that is
    exactly the research's 35,307 graded games (its h1_ok), with the same
    halves on every one.
    """
    cols = ["game_id", "h1_home", "h1_away", "h2_home", "h2_away"]
    if per is None or not len(per):
        return pd.DataFrame(columns=cols)
    p = per.copy()
    p["period"] = p["period"].astype(int)
    for c in ("home_points", "away_points"):
        p[c] = pd.to_numeric(p[c], errors="coerce")
    agg = p.groupby("game_id").agg(n=("period", "max"), k=("period", "nunique"),
                                   rows=("period", "size"), hs=("home_points", "sum"),
                                   as_=("away_points", "sum"),
                                   miss=("home_points", lambda v: int(v.isna().sum())))
    p1 = p[p["period"] == 1].drop_duplicates("game_id").set_index("game_id")[["home_points", "away_points"]]
    p2 = p[p["period"] == 2].drop_duplicates("game_id").set_index("game_id")[["home_points", "away_points"]]
    out = agg.join(p1.rename(columns={"home_points": "h1_home", "away_points": "h1_away"}))              .join(p2.rename(columns={"home_points": "h2_home", "away_points": "h2_away"}))
    f = finals.drop_duplicates("game_id").set_index("game_id")[["home_score", "away_score"]]
    out = out.join(f.apply(pd.to_numeric, errors="coerce"))
    ok = ((out["n"] >= 2) & (out["k"] == out["n"]) & (out["rows"] == out["n"]) & (out["miss"] == 0)
          & out["h1_home"].notna() & out["h1_away"].notna()
          & out["h2_home"].notna() & out["h2_away"].notna()
          & np.isclose(out["hs"], out["home_score"]) & np.isclose(out["as_"], out["away_score"]))
    return out[ok][cols[1:]].astype(float).reset_index()


# ── the team term ────────────────────────────────────────────────────────────

TEAM_GAME_COLS = ("game_id", "season", "tip", "home_team", "away_team", "h1_home", "h1_away",
                  "h2_home", "h2_away", "spread_close", "total_close")


def team_game_residuals(tg: pd.DataFrame, alpha: float, beta: float) -> pd.DataFrame:
    """Finished games -> one row per (team, game): season, team, end (tip +
    2.5 h), r (that team's first-vs-second-half margin tilt residual).

    A game counts only with both halves and BOTH closing consensus numbers
    (the research's tg.dropna on h2 and both spreads_c_cons and totals_c_cons).
    """
    g = tg.dropna(subset=["h1_home", "h1_away", "h2_home", "h2_away", "spread_close",
                          "total_close"]).copy()
    dm = (g["h1_home"] - g["h1_away"]) - (g["h2_home"] - g["h2_away"])
    mc = -g["spread_close"].astype(float)
    g["rm"] = dm - (beta * mc + alpha)
    g["end"] = pd.to_datetime(g["tip"], utc=True) + GAME_LEN
    home = pd.DataFrame({"season": g["season"].astype(int), "team": g["home_team"],
                         "end": g["end"], "r": g["rm"], "game_id": g["game_id"]})
    away = pd.DataFrame({"season": g["season"].astype(int), "team": g["away_team"],
                         "end": g["end"], "r": -g["rm"], "game_id": g["game_id"]})
    return pd.concat([home, away], ignore_index=True)


def prior_sums(res: pd.DataFrame, season: int) -> dict[str, list]:
    """{team: [sum of r, games]} over one finished season: the artifact's
    last-season term."""
    s = res[res["season"] == int(season)].groupby("team")["r"].agg(["sum", "size"])
    return {str(t): [float(v["sum"]), int(v["size"])] for t, v in s.iterrows()}


def team_effects(res: pd.DataFrame, season: int, prior: dict, targets: pd.DataFrame,
                 k: float, w_prev: float) -> pd.DataFrame:
    """Each target's two shrunk tendencies as of its moment.

    res:     team_game_residuals rows (any seasons; only `season`'s are used,
             and only those that ended at or before the moment).
    prior:   {team: [sum, n]} of the season before (the artifact's).
    targets: game_id, home_team, away_team, stamp (tz-aware).
    -> game_id, tau_home, tau_away, n_home, n_away (this season's games each
    team's term counts).
    """
    cur = res[res["season"] == int(season)].dropna(subset=["end"]).sort_values("end", kind="mergesort")
    cur = cur.assign(cm=cur.groupby("team")["r"].cumsum(), cn=cur.groupby("team").cumcount() + 1)
    cur = cur[["team", "end", "cm", "cn"]].copy()
    cur["end"] = cur["end"].astype("datetime64[ns, UTC]")
    # One key dtype on both sides: a team read from Postgres is an object
    # column, one built in pandas a string column, and merge_asof refuses a mix.
    cur["team"] = cur["team"].astype(str)
    out = targets[["game_id"]].copy()
    for side in ("home", "away"):
        q = targets[["game_id", f"{side}_team", "stamp"]].rename(columns={f"{side}_team": "team"}).copy()
        q["team"] = q["team"].astype(str)
        q["stamp_ns"] = pd.to_datetime(q["stamp"], utc=True).astype("datetime64[ns, UTC]")
        q = q.sort_values("stamp_ns", kind="mergesort")
        if len(cur):
            m = pd.merge_asof(q, cur.sort_values("end", kind="mergesort"), left_on="stamp_ns",
                              right_on="end", by="team", direction="backward")
        else:
            m = q.assign(cm=np.nan, cn=np.nan)
        pm = m["team"].map(lambda t: (prior.get(str(t)) or [0.0, 0])[0]).astype(float)
        pn = m["team"].map(lambda t: (prior.get(str(t)) or [0.0, 0])[1]).astype(float)
        cm = m["cm"].fillna(0.0).astype(float)
        cn = m["cn"].fillna(0.0).astype(float)
        m[f"tau_{side}"] = (cm + w_prev * pm) / (cn + w_prev * pn + k)
        m[f"n_{side}"] = cn.astype(int)
        out = out.merge(m[["game_id", f"tau_{side}", f"n_{side}"]], on="game_id", how="left")
    return out


# ── the artifact ─────────────────────────────────────────────────────────────

def load_artifact(season: int | None = None, path: str | Path | None = None) -> dict:
    """The frozen numbers for one season, with the distribution table rebuilt
    from its stored sample (deterministic: the same call the build made)."""
    p = Path(path) if path is not None else artifact_path(season)
    art = json.loads(p.read_text(encoding="utf-8"))
    if art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    if season is not None and int(art["season"]) != int(season):
        raise ValueError(f"{p}: built for season {art['season']}, not {season}")
    return with_table(art)


def with_table(art: dict) -> dict:
    """The artifact with its table (art['_T']) built from table.sample."""
    s = np.asarray(art["table"]["sample"], float)
    a, b = float(art["map"]["a"]), float(art["map"]["b"])
    key = b * (-s[:, 0]) + a
    art = dict(art)
    art["_T"] = fit_table(s[:, 1], key, weight=s[:, 2], h0=float(art["table"]["h0"]),
                          nmin=float(art["table"]["nmin"]))
    return art


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass
class Offer:
    """One book's priced first-half spread quote."""
    book: str
    line: float          # the HOME number
    home_price: float
    away_price: float
    side: str            # 'home' / 'away', the larger edge
    edge: float
    prob: float          # P(side wins | no push)
    home_link: str | None = None
    away_link: str | None = None

    def link_for(self, side: str) -> str | None:
        return self.home_link if side == "home" else self.away_link

    @property
    def link(self) -> str | None:
        """The bet slip link of this offer's own side."""
        return self.link_for(self.side)


@dataclass
class Decision:
    game_id: str
    status: str                      # bets / below_cut / no_quote / no_fg_line
    detail: str
    mu: float | None = None
    fg_spread: float | None = None   # the consensus home spread (M = -fg_spread)
    fg_books: int = 0
    tau_home: float | None = None
    tau_away: float | None = None
    n_home: int = 0
    n_away: int = 0
    best: Offer | None = None
    offers: list = field(default_factory=list)
    dropped: list = field(default_factory=list)   # quotes dropped as data errors

    @property
    def price(self) -> float | None:
        if self.best is None:
            return None
        return self.best.home_price if self.best.side == "home" else self.best.away_price


QUOTE_PRICES = ("home_price", "away_price")


def out_of_range(quotes: pd.DataFrame, books) -> pd.DataFrame:
    """The quotes of `books` that are data errors (models/ncaab_quote_bounds.py),
    with `market` and `why`: never priced, listed on the decision."""
    if not len(quotes):
        return quotes.assign(market=MARKET, why=None).iloc[0:0]
    q = quotes[quotes["bookmaker"].isin(list(books))]
    return qb.split(q, MARKET, "spread_home", QUOTE_PRICES)[1]


def quote_offers(quotes: pd.DataFrame, mu: float, T: dict, books) -> list[Offer]:
    """Price every quote of one game: one row per book (bookmaker, spread_home,
    home_price, away_price, optional home_link / away_link). A quote with no
    number or a missing price is not priced (the research's dropna), nor is a
    data error (out_of_range)."""
    q = quotes[quotes["bookmaker"].isin(list(books))].dropna(
        subset=["spread_home", "home_price", "away_price"])
    q = qb.split(q, MARKET, "spread_home", QUOTE_PRICES)[0]
    if not len(q):
        return []
    side, edge, p = price_quote(np.full(len(q), mu), q["spread_home"].astype(float).values,
                                q["home_price"].astype(float).values,
                                q["away_price"].astype(float).values, T)
    def text(v):
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)

    out = []
    for i, r in enumerate(q.itertuples(index=False)):
        out.append(Offer(book=str(r.bookmaker), line=float(r.spread_home),
                         home_price=float(r.home_price), away_price=float(r.away_price),
                         side="home" if side[i] == 1 else "away", edge=float(edge[i]),
                         prob=float(p[i]), home_link=text(getattr(r, "home_link", None)),
                         away_link=text(getattr(r, "away_link", None))))
    return out


def best_offer(offers: list[Offer]) -> Offer | None:
    """Largest edge, ties to the alphabetically first book key (fh_grade.pick:
    sort by edge descending, book ascending, first row)."""
    if not offers:
        return None
    return sorted(offers, key=lambda o: (-o.edge, o.book))[0]


def decide(game_id: str, quotes: pd.DataFrame, fg: dict | None, tau: dict | None,
           art: dict, cut: float, books=BOOKS) -> Decision:
    """One game's decision from its decision-fetch quotes.

    fg:  {"cons": consensus home spread, "nb": books} or None.
    tau: {"tau_home", "tau_away", "n_home", "n_away"} or None (zero tendencies).
    """
    bad = out_of_range(quotes, books)
    dropped = [{"book": str(r["bookmaker"]), "line": r["spread_home"], "home": r["home_price"],
                "away": r["away_price"], "why": r["why"]} for r in bad.to_dict("records")]
    note = ("; dropped as data errors: " + ", ".join(
        f"{x['book']} {x['line']} ({x['why']})" for x in dropped)) if dropped else ""
    if fg is None or fg.get("cons") is None or not np.isfinite(float(fg["cons"])):
        return Decision(game_id, "no_fg_line", "no bettable book's full-game spread stored "
                        "at or before the decision" + note, dropped=dropped)
    tau = tau or {}
    th, ta = float(tau.get("tau_home") or 0.0), float(tau.get("tau_away") or 0.0)
    M = -float(fg["cons"])
    mu = float(art["map"]["b"]) * M + float(art["map"]["a"]) + (th - ta) / 2
    d = Decision(game_id, "no_quote", "", mu=mu, fg_spread=float(fg["cons"]),
                 fg_books=int(fg.get("nb") or 0), tau_home=th, tau_away=ta,
                 n_home=int(tau.get("n_home") or 0), n_away=int(tau.get("n_away") or 0),
                 dropped=dropped)
    d.offers = quote_offers(quotes, mu, art["_T"], books)
    d.best = best_offer(d.offers)
    if d.best is None:
        d.detail = "no bettable book quoted a first-half spread in the decision fetch" + note
        return d
    b = d.best
    capped = qb.edge_problem(b.edge, MODEL_ID)
    d.status = "edge_cap" if capped else "bets" if b.edge > cut else "below_cut"
    d.detail = (f"{b.side} {b.line:+g} @{b.book} {d.price:+.0f} edge {b.edge:+.4f} "
                f"p {b.prob:.4f} mu {mu:+.3f} M {M:+.2f} ({d.fg_books} books)"
                + (f"; {capped}: a data error, not a bet" if capped else "") + note)
    return d
