"""NCAAB first-half total: `ncaab_first_half_total`.

LIVE, real money (mike, 2026-11-03: "we need to build 1H ... no matter what",
"I want it all done and go live now"). No games-played wait.

THE RULE (the NCAAB research's round 5, family A_to, market totals_h1, snapshot
tip60, books best, cut 0.02, every game; its PREREGISTRATION.txt and
scripts/r5_lib.py, r5_prep.py, r5_score.py, r5_grade.py, fh_lib.py). At the
first-half fetch an hour before each tip:

  1. T, the full-game consensus: the median over the bettable books of each
     book's newest full-game total stored at or before the moment.
  2. The expected first-half total is
         mu = a + b x T + (tau(home) + tau(away)) / 2
     a and b are ONE least-squares fit of the first-half total on the CLOSING
     full-game consensus total over every earlier season (2021 through the last
     finished season), fitted once per season and frozen in the artifact (for
     2025-26 the research's a = -1.975, b = 0.4856). tau is each team's shrunk
     first-half-minus-second-half scoring tendency as of the moment (THE TEAM
     TERM, below). The two tendencies are ADDED: both teams' halves make the
     total.
  3. Every bettable book's first-half total is priced through an empirical
     distribution of first-half totals (THE DISTRIBUTION, below): q = P(over |
     no push) at the quote's number, and both sides' edges are e_over = q -
     1/decimal(over price), e_under = (1 - q) - 1/decimal(under price). The
     quote's side is the larger edge (a tie goes to the over).
  4. A side priced shorter than -200 is not eligible (config.MODEL_MIN_ODDS,
     the limit every NCAAB model carries): its quote is set aside BEFORE the
     best is chosen, so the next book takes the game (the research's -200
     floor test, after_fact.py AF1). The single best eligible quote is the one
     with the largest edge, ties to the alphabetically first book key. The game
     is bet there when that edge is above the cut, 0.025 from 2026-11-06
     (0.02 before; config.MODEL_EDGE_THRESHOLDS);
     otherwise it is decided with no bet. One decision a game, ever (CLAUDE.md
     1c).

The edge is raw: the price's own implied probability, vig included, against
the model's P(win | no push). model_probability on the pick is that P(win | no
push), so decision_edge is exactly the edge the card cut on.

A FEED TYPO NEVER BECOMES A BET (models/ncaab_quote_bounds.py). A first-half
total outside 40-120, or priced beyond +/-100000, is not priced; a full-game
total outside 90-220 never enters the consensus T. The dropped first-half
quotes are listed on the decision. A best edge above the data-error cap is not
a bet: the game is decided as edge_cap with none, and the card's run fails.

THE TEAM TERM. For every finished game with both halves stored and a closing
full-game consensus spread AND total (the research's sample requires both), the
game's first-vs-second-half scoring tilt is
    dt = (home h1 + away h1) - (home h2 + away h2) - (alpha + beta x Tc)
where h2 is period 2 only (overtime is excluded), Tc is the closing consensus
total, and alpha / beta are one fit on the earlier seasons (frozen). BOTH teams
carry +dt. A team's tau at the moment is
    tau = (sum of this season's dt that ENDED, tip + 2.5 h, at or before the
           moment + 0.5 x sum of last season's dt)
          / (count of those + 0.5 x last season's count + 236.0)
236.0 is the research's method-of-moments shrinkage (round 4,
tilt_reliability.csv, 2021-2023), frozen.

THE DISTRIBUTION (the research's kernel table, fh_lib.fit_table with
TOTAL_SPEC). For each mean m on a grid from 30 to 110 in steps of 0.25, the
historical distribution of the whole-point first-half total over the training
games whose a + b x Tc is near m: Gaussian weights in that key with bandwidth
0.75, widened by x1.25 until the weights sum to at least 500 games, each
outcome shifted by round(m - key) when widened. A total on a whole number can
land on it: that is a push, left out of q.

THE EVIDENCE (the research's passing.csv, every game, the tip-minus-60
purchase, best book, cut 0.02): 2023-24..2025-26 2,529 bets, +125.78 units,
+4.40%, date-resampled 95% interval [0.57, 8.12]; 2023-24 +67.27, 2024-25
+41.03, 2025-26 +17.48 units (+1.85%). With the -200 floor: 2,527 bets,
+123.78 units, [0.45, 8.05]. About 80% of the bets are unders.

The pure functions here are shared by the card (scripts/ncaab_first_half_total_card.py)
and the build's replay (scripts/ncaab_first_half_total_build.py), so the replay
runs the card's own code path. The pricing, the as-of consensus, the halves
rule and the shrunk team sum are the first-half spread model's own
(models/ncaab_first_half_spread.py), imported, not copied.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import models.ncaab_first_half_spread as fh
from models import ncaab_quote_bounds as qb
from models.ncaab_first_half_spread import (  # noqa: F401 - re-exported for the card and the build
    BOOKS, GAME_LEN, asof_consensus, dec, prior_sums, probs, team_effects, valid_halves,
)

MODEL_ID = "ncaab_first_half_total"
SPORT = "NCAAB"
MARKET = "totals_h1"
REFERENCE_BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_KIND = "ncaab_first_half_total"

# The distribution table's shape (fh_lib.TOTAL_SPEC, fit_table defaults).
GRID = (30.0, 110.0, 0.25)
SUPPORT = (0, 200)
H0 = 0.75
NMIN = 500
# The team term's shrinkage (the research's K_T, round 4 tilt_reliability.csv).
K_TOTAL = 236.0
W_PREV = 0.5


def artifact_path(season: int) -> Path:
    return ROOT / f"models/saved/ncaab_first_half_total_{int(season)}.json"


def grid() -> np.ndarray:
    lo, hi, step = GRID
    return np.arange(lo, hi + 0.0001, step)


def fit_table(outcome, key, weight=None, h0: float = H0, nmin: float = NMIN) -> dict:
    """The research's first-half total table (fh_lib.fit_table, TOTAL_SPEC)."""
    return fh.fit_table(outcome, key, weight=weight, h0=h0, nmin=nmin, means=grid(),
                        support=SUPPORT)


def price_quote(mu, line, p_over, p_under, T: dict):
    """Both sides of a first-half total quote at mean mu (fh_lib.price_quote,
    market totals_h1: side 1 = over, which wins when the first half's points
    are above the line). -> (side 1 = over / 2 = under, edge, P(side wins | no
    push))."""
    pw1, pp1, pl1 = probs(mu, np.asarray(line, float), T)
    q1 = pw1 / np.maximum(pw1 + pl1, 1e-12)
    e1 = q1 - 1 / dec(p_over)
    e2 = (1 - q1) - 1 / dec(p_under)
    side = np.where(e1 >= e2, 1, 2)
    edge = np.maximum(e1, e2)
    return side, edge, np.where(side == 1, q1, 1 - q1)


# ── the team term ────────────────────────────────────────────────────────────

def team_game_residuals(tg: pd.DataFrame, alpha: float, beta: float) -> pd.DataFrame:
    """Finished games -> one row per (team, game): season, team, end (tip +
    2.5 h), r (the game's first-vs-second-half scoring tilt residual, the SAME
    for both teams).

    A game counts only with both halves and BOTH closing consensus numbers
    (the research's tg.dropna on h2 and both spreads_c_cons and totals_c_cons).
    """
    g = tg.dropna(subset=["h1_home", "h1_away", "h2_home", "h2_away", "spread_close",
                          "total_close"]).copy()
    dt = (g["h1_home"] + g["h1_away"]) - (g["h2_home"] + g["h2_away"])
    tc = g["total_close"].astype(float)
    g["rt"] = dt - (beta * tc + alpha)
    g["end"] = pd.to_datetime(g["tip"], utc=True) + GAME_LEN
    home = pd.DataFrame({"season": g["season"].astype(int), "team": g["home_team"],
                         "end": g["end"], "r": g["rt"], "game_id": g["game_id"]})
    away = pd.DataFrame({"season": g["season"].astype(int), "team": g["away_team"],
                         "end": g["end"], "r": g["rt"], "game_id": g["game_id"]})
    return pd.concat([home, away], ignore_index=True)


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
    """The artifact with its table (art['_T']) built from table.sample: rows
    [closing consensus total, first-half total, games]; the key is a + b x the
    total (no sign flip: a total is not a home number)."""
    s = np.asarray(art["table"]["sample"], float)
    a, b = float(art["map"]["a"]), float(art["map"]["b"])
    key = b * s[:, 0] + a
    art = dict(art)
    art["_T"] = fit_table(s[:, 1], key, weight=s[:, 2], h0=float(art["table"]["h0"]),
                          nmin=float(art["table"]["nmin"]))
    return art


# ── the decision ─────────────────────────────────────────────────────────────

@dataclass
class Offer:
    """One book's priced first-half total quote."""
    book: str
    line: float          # the first half's total points
    over_price: float
    under_price: float
    side: str            # 'over' / 'under', the larger edge
    edge: float
    prob: float          # P(side wins | no push)
    over_link: str | None = None
    under_link: str | None = None

    @property
    def price(self) -> float:
        return self.over_price if self.side == "over" else self.under_price

    def link_for(self, side: str) -> str | None:
        return self.over_link if side == "over" else self.under_link

    @property
    def link(self) -> str | None:
        """The bet slip link of this offer's own side."""
        return self.link_for(self.side)


@dataclass
class Decision:
    game_id: str
    status: str                      # bets / below_cut / below_floor / no_quote / no_fg_line
    detail: str
    mu: float | None = None
    fg_total: float | None = None    # the consensus full-game total (T)
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
        return None if self.best is None else self.best.price


QUOTE_PRICES = ("over_price", "under_price")


def out_of_range(quotes: pd.DataFrame, books) -> pd.DataFrame:
    """The quotes of `books` that are data errors (models/ncaab_quote_bounds.py),
    with `market` and `why`: never priced, listed on the decision."""
    if not len(quotes):
        return quotes.assign(market=MARKET, why=None).iloc[0:0]
    q = quotes[quotes["bookmaker"].isin(list(books))]
    return qb.split(q, MARKET, "total_line", QUOTE_PRICES)[1]


def quote_offers(quotes: pd.DataFrame, mu: float, T: dict, books) -> list[Offer]:
    """Price every quote of one game: one row per book (bookmaker, total_line,
    over_price, under_price, optional over_link / under_link). A quote with no
    number or a missing price is not priced (the research's dropna), nor is a
    data error (out_of_range)."""
    q = quotes[quotes["bookmaker"].isin(list(books))].dropna(
        subset=["total_line", "over_price", "under_price"])
    q = qb.split(q, MARKET, "total_line", QUOTE_PRICES)[0]
    if not len(q):
        return []
    side, edge, p = price_quote(np.full(len(q), mu), q["total_line"].astype(float).values,
                                q["over_price"].astype(float).values,
                                q["under_price"].astype(float).values, T)

    def text(v):
        return None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)

    out = []
    for i, r in enumerate(q.itertuples(index=False)):
        out.append(Offer(book=str(r.bookmaker), line=float(r.total_line),
                         over_price=float(r.over_price), under_price=float(r.under_price),
                         side="over" if side[i] == 1 else "under", edge=float(edge[i]),
                         prob=float(p[i]), over_link=text(getattr(r, "over_link", None)),
                         under_link=text(getattr(r, "under_link", None))))
    return out


def best_offer(offers: list[Offer], min_price: float | None = None) -> Offer | None:
    """Largest edge, ties to the alphabetically first book key (r5_grade.pick:
    sort by edge descending, book ascending, first row), among the offers whose
    own side is priced at min_price or longer (after_fact.py's -200 floor: an
    ineligible quote's edge is -inf before the pick)."""
    ok = [o for o in offers if min_price is None or o.price >= float(min_price)]
    if not ok:
        return None
    return sorted(ok, key=lambda o: (-o.edge, o.book))[0]


def first_half_mean(T: float, tau_home: float, tau_away: float, art: dict) -> float:
    return float(art["map"]["b"]) * float(T) + float(art["map"]["a"]) + (tau_home + tau_away) / 2


def decide(game_id: str, quotes: pd.DataFrame, fg: dict | None, tau: dict | None,
           art: dict, cut: float, books=BOOKS, min_price: float | None = None) -> Decision:
    """One game's decision from its decision-fetch quotes.

    fg:  {"cons": consensus full-game total, "nb": books} or None.
    tau: {"tau_home", "tau_away", "n_home", "n_away"} or None (zero tendencies).
    min_price: the shortest price a side may lay (config.min_odds_for), None
    for none (the research's own grid).
    """
    bad = out_of_range(quotes, books)
    dropped = [{"book": str(r["bookmaker"]), "line": r["total_line"], "over": r["over_price"],
                "under": r["under_price"], "why": r["why"]} for r in bad.to_dict("records")]
    note = ("; dropped as data errors: " + ", ".join(
        f"{x['book']} {x['line']} ({x['why']})" for x in dropped)) if dropped else ""
    if fg is None or fg.get("cons") is None or not np.isfinite(float(fg["cons"])):
        return Decision(game_id, "no_fg_line", "no bettable book's full-game total stored "
                        "at or before the decision" + note, dropped=dropped)
    tau = tau or {}
    th, ta = float(tau.get("tau_home") or 0.0), float(tau.get("tau_away") or 0.0)
    T = float(fg["cons"])
    mu = first_half_mean(T, th, ta, art)
    d = Decision(game_id, "no_quote", "", mu=mu, fg_total=T,
                 fg_books=int(fg.get("nb") or 0), tau_home=th, tau_away=ta,
                 n_home=int(tau.get("n_home") or 0), n_away=int(tau.get("n_away") or 0),
                 dropped=dropped)
    d.offers = quote_offers(quotes, mu, art["_T"], books)
    if not d.offers:
        d.detail = "no bettable book quoted a first-half total in the decision fetch" + note
        return d
    d.best = best_offer(d.offers, min_price)
    if d.best is None:
        d.status = "below_floor"
        d.detail = (f"every quote's better side is priced shorter than {min_price:+.0f}; "
                    f"mu {mu:.3f} T {T:.2f} ({d.fg_books} books)" + note)
        return d
    b = d.best
    capped = qb.edge_problem(b.edge, MODEL_ID)
    d.status = "edge_cap" if capped else "bets" if b.edge > cut else "below_cut"
    d.detail = (f"{b.side} {b.line:g} @{b.book} {b.price:+.0f} edge {b.edge:+.4f} "
                f"p {b.prob:.4f} mu {mu:.3f} T {T:.2f} ({d.fg_books} books)"
                + (f"; {capped}: a data error, not a bet" if capped else "") + note)
    return d
