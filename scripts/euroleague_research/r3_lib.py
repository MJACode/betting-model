"""EuroLeague research, round 2 (files r3_*): the shared pieces.

The pre-registration (decision times, anchors, cut grids, constants) is
section 0 of C:\\Users\\micha\\AppData\\Local\\Temp\\euroleague_round2.md and
was written before any r3 script ran. This module only loads data, grades
and prints; it holds no tuned number.

Reused unchanged: r2_lib (full-game quotes, the ledger, board_at, grading,
p_one_sided, md_table) and r1_lib (period quotes, period settlement,
summary). One clarification fixed before any result was read: "an earlier
game" for every prior-games feature means a game whose tip is at least 3
hours before this game's tip (a game tipping two hours earlier the same
evening has not finished at this game's close).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import r1_lib as L1  # noqa: E402
import r2_lib as L2  # noqa: E402

CACHE = L2.CACHE
DECIDABLE = L2.DECIDABLE
PRIOR_GAP = pd.Timedelta(hours=3)
REG: list[dict] = []          # the multiplicity registry: one entry per counted cell


# ── summaries ────────────────────────────────────────────────────────────────

def row(label: dict, df: pd.DataFrame) -> dict:
    return L2.row(label, df)


def reg(exp: str, cell: str, df: pd.DataFrame) -> dict:
    """Count a cell toward Benjamini-Hochberg and return its row."""
    r = row({"experiment": exp, "cell": cell}, df)
    REG.append({"experiment": exp, "cell": cell, "bets": r["bets"], "units": r["units"],
                "ret%": r["ret%"], "lo%": r["lo%"], "hi%": r["hi%"],
                "p_one": r["p_one"] if np.isfinite(r["p_one"]) else 1.0})
    return r


def price_range(x: pd.DataFrame) -> str:
    if not len(x):
        return "no bets"
    p = x.price.to_numpy(float)
    return (f"median {np.median(p):+.0f}, shortest {p.min():+.0f}, longest {p.max():+.0f}, "
            f"shorter than -300: {100 * np.mean(p < -300):.1f}%, shorter than -500: {100 * np.mean(p < -500):.1f}%, "
            f"risked {x.risk.sum():.1f} units")


def price_band(p) -> np.ndarray:
    p = np.asarray(p, float)
    return np.select([p < -300, p <= -151, p <= -100, p <= 150], ["< -300", "-300..-151", "-150..-100", "+100..+150"], "> +150")


def kill_rows(name: str, x: pd.DataFrame, side_cols=("side",), fav_col: str | None = "fav") -> list[dict]:
    """The standard kill-test sub-rows for one rule's graded bets."""
    rows = []
    if not len(x):
        return [row({"rule": name, "subset": "no bets"}, x)]
    rows.append(row({"rule": name, "subset": "all"}, x))
    for s, xs in x.groupby("season"):
        rows.append(row({"rule": name, "subset": f"season {int(s)}"}, xs))
    med = x.groupby("season").game_date.transform(lambda d: sorted(d)[len(d) // 2])
    rows.append(row({"rule": name, "subset": "early half of each season"}, x[x.game_date < med]))
    rows.append(row({"rule": name, "subset": "late half of each season"}, x[x.game_date >= med]))
    best = x.groupby("game_date").units.sum().sort_values(ascending=False).head(10).index
    rows.append(row({"rule": name, "subset": "without its 10 best dates"}, x[~x.game_date.isin(best)]))
    for c in side_cols:
        for v, xs in x.groupby(c):
            d = row({"rule": name, "subset": f"{c} = {v}"}, xs)
            d["share%"] = round(100 * len(xs) / len(x), 1)
            rows.append(d)
    if fav_col and fav_col in x:
        for v, xs in x.groupby(fav_col):
            d = row({"rule": name, "subset": "favourite" if v else "underdog"}, xs)
            d["share%"] = round(100 * len(xs) / len(x), 1)
            rows.append(d)
    xb = x.assign(_band=price_band(x.price))
    for v, xs in xb.groupby("_band"):
        d = row({"rule": name, "subset": f"price band {v}"}, xs)
        d["share%"] = round(100 * len(xs) / len(x), 1)
        rows.append(d)
    return rows


def table(rows) -> str:
    return L2.md_table(pd.DataFrame(rows))


# ── full game ────────────────────────────────────────────────────────────────

_FG = {}


def fullgame():
    """(games played, coherent quotes, decision times, close board, first posts)."""
    if not _FG:
        g = L2.load_games()
        g = g[g.played].copy()
        q = L2.load_quotes(games=g)
        q = q[q.played]
        dt = L2.decision_times(g)
        cb = L2.board_at(q, dt["close"])
        fp = L2.first_posts(q)
        _FG.update(g=g, q=q, dt=dt, cb=cb, fp=fp)
    return _FG["g"], _FG["q"], _FG["dt"], _FG["cb"], _FG["fp"]


def one_book(board: pd.DataFrame, market: str, book: str, cols=("line", "pa", "pb", "pa_mult", "pa_pow"),
             prefix: str = "") -> pd.DataFrame:
    b = board[(board.market == market) & (board.bookmaker == book)][["game_id", *cols]]
    return b.rename(columns={c: f"{prefix}{c}" for c in cols})


def ml_sides(b: pd.DataFrame) -> pd.DataFrame:
    """h2h quotes -> two rows each with side, price, fair (power de-vig), fav."""
    z = L2.sides_long(b[b.market == "h2h"])
    z["fair"] = np.where(z.side == "home", z.pa_pow, 1 - z.pa_pow)
    z["fav"] = z.fair > 0.5
    return z


def best_price(z: pd.DataFrame, keys=("game_id", "side")) -> pd.DataFrame:
    z = z.assign(_dz=L2.dec(z.price))
    return z.sort_values([*keys, "_dz"], ascending=[True] * len(keys) + [False]).drop_duplicates(list(keys)).drop(columns="_dz")


def early_late_med(x: pd.DataFrame) -> pd.Series:
    return x.groupby("season").game_date.transform(lambda d: sorted(d)[len(d) // 2])


# ── periods ──────────────────────────────────────────────────────────────────

_PQ = {}


def period_main(drop_rungs: bool = True) -> pd.DataFrame:
    """Main period quotes (r1_lib.load_main_quotes) with the rung rule:
    off-centre (r1_lib OFFC) or, for spreads/totals, a number 2+ points from
    every other book's main number at the same mark (when another book quotes)."""
    if "q" not in _PQ:
        g = L1.load_games()
        q = L1.load_main_quotes(g)
        q = q.copy().reset_index(drop=True)
        q["_rid"] = np.arange(len(q))
        st = q[~q.market.str.startswith("h2h")][["_rid", "game_id", "market", "mark", "bookmaker", "line"]]
        m = st.merge(st, on=["game_id", "market", "mark"], suffixes=("", "_o"))
        m = m[m._rid != m._rid_o]
        m["d"] = (m.line - m.line_o).abs()
        mind = m.groupby("_rid").d.min()
        q["far"] = q._rid.map(mind).fillna(0.0).to_numpy() >= 2
        q = q.drop(columns="_rid")
        q["rung"] = q.offc | q.far
        _PQ["q"] = q
        _PQ["g"] = g
    q = _PQ["q"]
    return q[~q.rung] if drop_rungs else q


def period_games() -> pd.DataFrame:
    if "g" not in _PQ:
        period_main()
    return _PQ["g"]


def modal_best(x: pd.DataFrame, side_a: str, side_b: str) -> pd.DataFrame:
    """Per game: the modal number over the quotes given (ties nearest the
    median, then the lower) and the best price on it for each side. Returns
    one row per game with line, best_pa, book_a, best_pb, book_b."""
    out = []
    for gid, y in x.groupby("game_id"):
        vc = y.line.value_counts()
        top = sorted(vc[vc == vc.max()].index, key=lambda v: (abs(v - y.line.median()), v))
        ln = top[0]
        z = y[y.line == ln]
        ia = int(np.argmax(L1.dec(z.pa.to_numpy())))
        ib = int(np.argmax(L1.dec(z.pb.to_numpy())))
        out.append({"game_id": gid, "line": ln, "best_pa": z.pa.iloc[ia], "book_a": z.bookmaker.iloc[ia],
                    "best_pb": z.pb.iloc[ib], "book_b": z.bookmaker.iloc[ib], "nbooks": len(z)})
    return pd.DataFrame(out)


def ladder_fair(x: pd.DataFrame, col: str, a: str, b: str) -> float:
    """r1_fullgame.py part B's ladder_fair, verbatim: where the ladder's no-vig
    side-a probability crosses 0.5, linear between the bracketing rungs."""
    pa = L1.imp(x[a]) / (L1.imp(x[a]) + L1.imp(x[b]))
    x = x.assign(pa=pa).sort_values(col)
    v = x[col].to_numpy(float)
    p = x["pa"].to_numpy(float)
    for i in range(len(v) - 1):
        lo, hi = p[i], p[i + 1]
        if (lo - 0.5) * (hi - 0.5) <= 0 and lo != hi:
            return float(v[i] + (0.5 - lo) * (v[i + 1] - v[i]) / (hi - lo))
    return np.nan


_PIN = {}


def pin_ladder() -> pd.DataFrame:
    """r1_fullgame.py part B rebuilt in memory: per (game, mark) Pinnacle's
    ladder fair full-game total and home spread."""
    if "x" not in _PIN:
        q = pd.read_parquet(CACHE / "period_quotes.parquet")
        q = q[(q.bookmaker == "pinnacle") & q.market.isin(["alternate_totals", "alternate_spreads"])].copy()
        out = None
        for mk, col, a, b, name in (("alternate_totals", "total_line", "over_price", "under_price", "pin_total"),
                                    ("alternate_spreads", "spread_home", "home_price", "away_price", "pin_spread")):
            x = q[q.market == mk][["game_id", "mark", col, a, b]].copy()
            x["pa"] = L1.imp(x[a]) / (L1.imp(x[a]) + L1.imp(x[b]))
            x = x.sort_values(["game_id", "mark", col], kind="mergesort").reset_index(drop=True)
            v, p = x[col].to_numpy(float), x.pa.to_numpy(float)
            same = (x.game_id.to_numpy()[1:] == x.game_id.to_numpy()[:-1]) & (x.mark.to_numpy()[1:] == x.mark.to_numpy()[:-1])
            lo, hi = p[:-1], p[1:]
            cross = same & ((lo - 0.5) * (hi - 0.5) <= 0) & (lo != hi)
            with np.errstate(divide="ignore", invalid="ignore"):
                f = v[:-1] + (0.5 - lo) * (v[1:] - v[:-1]) / (hi - lo)
            c = pd.DataFrame({"game_id": x.game_id.to_numpy()[:-1], "mark": x.mark.to_numpy()[:-1], name: f})[cross]
            c = c.drop_duplicates(["game_id", "mark"], keep="first")      # the first crossing, as the loop
            keys = x[["game_id", "mark"]].drop_duplicates()
            r = keys.merge(c, on=["game_id", "mark"], how="left")
            out = r if out is None else out.merge(r, on=["game_id", "mark"], how="outer")
        _PIN["x"] = out
    return _PIN["x"]


def pin_ladder_loop() -> pd.DataFrame:
    """The loop form (r1_fullgame part B as written), for the equivalence check."""
    q = pd.read_parquet(CACHE / "period_quotes.parquet")
    q = q[(q.bookmaker == "pinnacle") & q.market.isin(["alternate_totals", "alternate_spreads"])].copy()
    rows = []
    for (gid, mark), x in q.groupby(["game_id", "mark"]):
        t = x[x.market == "alternate_totals"]
        s = x[x.market == "alternate_spreads"]
        rows.append({"game_id": gid, "mark": mark,
                     "pin_total": ladder_fair(t, "total_line", "over_price", "under_price") if len(t) else np.nan,
                     "pin_spread": ladder_fair(s, "spread_home", "home_price", "away_price") if len(s) else np.nan})
    return pd.DataFrame(rows)


# ── prior-games-only helpers ─────────────────────────────────────────────────

def prior_index(tips: pd.Series) -> np.ndarray:
    """For games sorted by tip: how many games tipped >= 3 h before each one
    (so rows [0, idx) are 'earlier' in the pre-registered sense)."""
    t = pd.to_datetime(tips, utc=True).values.astype("datetime64[us]").astype(np.int64)
    gap = int(PRIOR_GAP / pd.Timedelta(microseconds=1))
    return np.searchsorted(t, t - gap, side="right")
