"""EuroLeague first-half / first-quarter research, round 1: the shared pieces.

FROZEN BEFORE ANY RESULT WAS READ (2026-11-13):

  Data      the local parquet cache only (C:\\Users\\micha\\euroleague_research\\cache)
            and, for full-game lines, the purchase spool for 2025-26 only.
            No database, no API.
  Markets   spreads_h1, totals_h1, h2h_h1, spreads_q1, totals_q1, h2h_q1, at the
            book's MAIN number (one stored row per game, market, book, mark).
  Off-centre "mains"  a spread or total main quote with either side's
            no-vig probability outside [0.35, 0.65] is not the book's main
            line (BetMGM 2026-27, Fanatics 2025-26: a rung 4-8 points from the
            other books' number). It is set aside from the main-line tables
            and the method, and counted.
  Books     decidable: fanduel, betmgm, betrivers, fanatics, draftkings (none
            quoted). Reference only (never a pick): betus, gtbets, mybookieag
            (offshore); pinnacle (full-game alternate ladders only).
  Settle    first half = quarters 1+2, first quarter = quarter 1, overtime never
            counts. Spread: home covers when margin + spread_home > 0, push at 0.
            Total: push when equal. Two-way moneyline: a tie PUSHES (measured,
            r1_settle2.py: BetRivers' two-way price de-vigged equals its
            three-way draw-no-bet price, mean abs difference 0.0012 first
            half, 0.0046 first quarter, 2,461 pairs each).
  Stake     1 unit to win, risk capped at 3: price p < 0 risks min(|p|/100, 3)
            to win risk*100/|p|; p > 0 risks 1 to win p/100.
  Return    units won / units risked on graded (non-push) bets.
  Interval  90%, resampling game DATES (1,000 draws, 5th and 95th percentile).
  Decision  T-10 (the close) and each game's earliest stored mark.
  Best price  the repo's same-line rule: the modal decidable number at the
            mark (ties: nearest the median, then the lower), the best decidable
            price on that number for the side.
  Method cut grid  edge 0.00, 0.01, 0.02, 0.03, 0.04, 0.05; the catalogued cut
            is 0.02. Decision mark T-10, other read T-60.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"C:\Users\micha\documents\bm-euroleague-fix")
CACHE = Path(r"C:\Users\micha\euroleague_research\cache")
SPOOL = Path(r"C:\Users\micha\el_spool")

DECIDABLE = ["fanduel", "betmgm", "betrivers", "fanatics", "draftkings"]
OFFSHORE = ["betus", "gtbets", "mybookieag"]
MARKETS = ["spreads_h1", "totals_h1", "h2h_h1", "spreads_q1", "totals_q1", "h2h_q1"]
MARKS = ["T-1440", "T-720", "T-360", "T-180", "T-120", "T-60", "T-30", "T-10"]
MARK_MIN = {m: int(m[2:]) for m in MARKS}
OFFC = 0.15         # |no-vig p - 0.5| beyond this = not the main line
CUTS = [0.00, 0.01, 0.02, 0.03, 0.04, 0.05]


# ── prices and stakes ────────────────────────────────────────────────────────

def imp(a):
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 100 / (a + 100), -a / (-a + 100))


def dec(a):
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def stake(price):
    """(risk, win) per the brief: 1 to win, risk capped at 3; dogs risk 1."""
    p = np.asarray(price, float)
    neg = p < 0
    risk = np.where(neg, np.minimum(np.abs(p) / 100.0, 3.0), 1.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        win = np.where(neg, risk * 100.0 / np.abs(p), p / 100.0)
    return risk, win


# ── outcomes ─────────────────────────────────────────────────────────────────

def load_games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "games.parquet")
    p = pd.read_parquet(CACHE / "periods.parquet")
    pv = p[p.period <= 2].pivot_table(index="game_id", columns="period",
                                       values=["home_points", "away_points"], aggfunc="sum")
    o = pd.DataFrame({
        "q1h": pv[("home_points", 1)], "q1a": pv[("away_points", 1)],
        "q2h": pv[("home_points", 2)], "q2a": pv[("away_points", 2)],
    }).reset_index()
    g = g.merge(o, on="game_id", how="left")
    g["tip"] = pd.to_datetime(g.commence_time, utc=True)
    g["h1h"] = g.q1h + g.q2h
    g["h1a"] = g.q1a + g.q2a
    g["h1_margin"] = g.h1h - g.h1a
    g["h1_total"] = g.h1h + g.h1a
    g["q1_margin"] = g.q1h - g.q1a
    g["q1_total"] = g.q1h + g.q1a
    g["fg_total"] = g.home_score + g.away_score
    g["fg_margin"] = g.home_score - g.away_score
    return g


def period_of(market: str) -> str:
    return "h1" if market.endswith("_h1") else "q1"


def result(market: str, side, line, margin, total):
    """+1 win, 0 push, -1 loss. side: home/away/over/under. line: the HOME
    spread number, the total, or NaN for a moneyline (a tie pushes)."""
    side = np.asarray(side)
    line = np.asarray(line, float)
    margin = np.asarray(margin, float)
    total = np.asarray(total, float)
    if market.startswith("spreads"):
        c = margin + line
        r = np.sign(c)
        return np.where(side == "home", r, -r).astype(int)
    if market.startswith("totals"):
        r = np.sign(total - line)
        return np.where(side == "over", r, -r).astype(int)
    r = np.sign(margin)
    return np.where(side == "home", r, -r).astype(int)


def _assert_settlement() -> None:
    """The spread sign and the moneyline tie, checked on every import."""
    # home -6.5 wins by 7: home covers; away loses
    assert list(result("spreads_h1", ["home", "away"], [-6.5, -6.5], [7, 7], [0, 0])) == [1, -1]
    # home +3 loses by 3: push both sides
    assert list(result("spreads_h1", ["home", "away"], [3, 3], [-3, -3], [0, 0])) == [0, 0]
    # home +3 loses by 2: home covers
    assert list(result("spreads_q1", ["home", "away"], [3, 3], [-2, -2], [0, 0])) == [1, -1]
    # tied half on the two-way moneyline: push
    assert list(result("h2h_h1", ["home", "away"], [np.nan, np.nan], [0, 0], [0, 0])) == [0, 0]
    assert list(result("totals_h1", ["over", "under"], [80, 80.5], [0, 0], [80, 80])) == [0, 1]


_assert_settlement()


# ── quotes ───────────────────────────────────────────────────────────────────

def load_main_quotes(games: pd.DataFrame | None = None) -> pd.DataFrame:
    """Main-market quotes, one row per (game, market, book, mark), normalised:
    line (spread_home / total_line / NaN), pa (home or over price), pb (away or
    under price), pa_fair (no-vig side-a probability), offc (off-centre flag)."""
    g = load_games() if games is None else games
    q = pd.read_parquet(CACHE / "period_quotes.parquet")
    q = q[q.market.isin(MARKETS)].copy()
    tot = q.market.str.startswith("totals")
    q["line"] = np.where(q.market.str.startswith("spreads"), q.spread_home,
                         np.where(tot, q.total_line, np.nan))
    q["pa"] = np.where(tot, q.over_price, q.home_price)
    q["pb"] = np.where(tot, q.under_price, q.away_price)
    s = imp(q.pa) + imp(q.pb)
    q["pa_fair"] = imp(q.pa) / s
    q["ovr"] = s
    q["offc"] = (~q.market.str.startswith("h2h")) & ((q.pa_fair - 0.5).abs() > OFFC)
    q["mark_min"] = q.mark.map(MARK_MIN)
    q["snap"] = pd.to_datetime(q.snapshot_at, utc=True)
    q = q.merge(g[["game_id", "season", "game_date", "tip", "played", "h1_margin", "h1_total",
                   "q1_margin", "q1_total"]], on="game_id", how="left")
    q["margin"] = np.where(q.market.str.endswith("_h1"), q.h1_margin, q.q1_margin)
    q["total"] = np.where(q.market.str.endswith("_h1"), q.h1_total, q.q1_total)
    q = q[q.played & q.margin.notna()]
    q["decidable"] = q.bookmaker.isin(DECIDABLE)
    return q.drop(columns=["home_price", "away_price", "over_price", "under_price",
                           "spread_home", "total_line", "draw_price"])


# ── grading summaries ────────────────────────────────────────────────────────

def grade_rows(df: pd.DataFrame, market: str, side_col="side", line_col="line",
               price_col="price") -> pd.DataFrame:
    df = df.copy()
    df["res"] = result(market, df[side_col].to_numpy(), df[line_col].to_numpy(),
                       df["margin"].to_numpy(), df["total"].to_numpy())
    risk, win = stake(df[price_col].to_numpy())
    df["risk"] = np.where(df.res == 0, 0.0, risk)
    df["units"] = np.where(df.res > 0, win, np.where(df.res < 0, -risk, 0.0))
    return df


def summary(df: pd.DataFrame, n_boot: int = 1000, seed: int = 7) -> dict:
    """bets, W-L-P, units, risked, return (units/risked) with a 90% interval
    from resampling dates; also units per bet."""
    n = len(df)
    if n == 0:
        return {"bets": 0, "W": 0, "L": 0, "P": 0, "units": 0.0, "risked": 0.0,
                "ret%": np.nan, "lo%": np.nan, "hi%": np.nan, "u/bet": np.nan, "p_le0": np.nan}
    w = int((df.res > 0).sum())
    l = int((df.res < 0).sum())
    p = int((df.res == 0).sum())
    units = float(df.units.sum())
    risked = float(df.risk.sum())
    ret = 100 * units / risked if risked > 0 else np.nan
    by = df.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    rng = np.random.default_rng(seed)
    k = len(by)
    idx = rng.integers(0, k, size=(n_boot, k))
    U = by.u.to_numpy()[idx].sum(1)
    R = by.r.to_numpy()[idx].sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rr = 100 * U / R
    lo, hi = np.nanpercentile(rr, [5, 95])
    return {"bets": n, "W": w, "L": l, "P": p, "units": round(units, 2), "risked": round(risked, 2),
            "ret%": round(ret, 2), "lo%": round(lo, 2), "hi%": round(hi, 2),
            "u/bet": round(units / n, 4), "p_le0": float(np.mean(rr <= 0))}


def bh(pvals, alpha=0.10):
    """Benjamini-Hochberg: which hypotheses survive at false-discovery rate alpha."""
    p = np.asarray(pvals, float)
    n = len(p)
    order = np.argsort(p)
    thresh = alpha * (np.arange(1, n + 1) / n)
    passed = p[order] <= thresh
    k = np.max(np.where(passed)[0]) + 1 if passed.any() else 0
    out = np.zeros(n, bool)
    out[order[:k]] = True
    return out


def fmt(df: pd.DataFrame) -> str:
    return df.to_string(index=False)
