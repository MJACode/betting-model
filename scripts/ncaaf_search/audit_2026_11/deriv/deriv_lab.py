"""NCAAF first-half and team-total lab: the price history bought 2026-11-10, graded.

Definitions fixed before any result was read (2026-11-11):

  DATA      `odds` rows under odds_api_ncaaf_derivative_am / _pm (extract_deriv.py): first-half
            moneyline, spread and total, and full-game team totals, 2023-2025, 8 books, read at
            13:55 UTC on the game's Eastern date ("am", median 6.6 h before kickoff) and 22:55 UTC
            the evening before ("pm", median 21.6 h). Full-game quotes of the same minute: q_hist.
  SCORES    finals from `games`; half-time scores from the stored play-by-play (h1_scores.py),
            used only where two independent reads of the half agree.
  BOOKS     a bet may be placed at the deciding books that quote these markets (DraftKings, FanDuel,
            BetMGM, Caesars, BetRivers, Hard Rock); Bovada and Pinnacle count toward the market only.
  GRADING   1 unit to win, risk capped at 3. ROI = units / units risked. 95% interval by resampling
            Eastern dates. A first-half moneyline tied at the half is a push (checked against the
            books' own margin in `overround`). Team totals settle on the final score, overtime in.
  RULES     B   baseline: every deciding-book quote, each side.
            R1  same line, better price: a deciding book's price against the middle no-vig chance of
                the OTHER books quoting the same line (>= 2 others; moneyline >= 3 others).
            R2  better line: a deciding book's line better than the other books' middle line by k
                points, at a price no shorter than -125.
            R3  team total against the full game: line minus (total -/+ spread)/2 from the full-game
                middle of the same minute; over when the line is k below it, under when k above.
            R4  first half against the full game, walk-forward: season S prices a first-half line
                from the full-game middle with slopes and leftovers fitted on earlier seasons only.
            One bet a game and market per rule: the best qualifying quote.
  ADDED     the same day, each before it was run and marked where it lives: R1p (R1 with Pinnacle
            alone as the fair price, deriv_rules.py) and R4b / R4c (R4 with its table fitted on every
            earlier season back to 2015, deriv_r4b.py). F1 and F2 in deriv_r4.py are NOT rules: they
            were read off the baseline's side table.

Result (docs/ncaaf_first_half_team_totals.md): nothing clears.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import CACHE as D  # noqa: E402

pd.set_option("display.width", 250)
pd.set_option("display.max_columns", 60)
pd.set_option("display.max_rows", 400)

BETTABLE = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet"]
MARKET_BOOKS = BETTABLE + ["bovada", "pinnacle"]
MIN_PRICE = -125
RNG = np.random.default_rng(20261111)
NUM = ["home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"]
LINE_MARKETS = ["spreads_h1", "totals_h1", "team_totals_home", "team_totals_away"]


def dec(a):
    a = np.asarray(a, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def stake(d):
    d = np.asarray(d, float)
    risk = np.minimum(1.0 / (d - 1.0), 3.0)
    return risk, risk * (d - 1.0)


def power_devig(d1, d2):
    p1, p2 = 1 / np.asarray(d1, float), 1 / np.asarray(d2, float)
    lo, hi = np.full(p1.shape, 0.5), np.full(p1.shape, 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = p1 ** k + p2 ** k
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    return p1 ** ((lo + hi) / 2)


# ── data ─────────────────────────────────────────────────────────────────────

def load(verbose=True):
    """Every bought quote in long form: one row per (game, read, book, market, line, SIDE), graded."""
    d = pd.read_parquet(D / "deriv_odds.parquet")
    for c in NUM:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["ts"] = pd.to_datetime(d.snapshot_at, utc=True, errors="coerce", format="mixed")
    d["slot"] = d.source.str[-2:]
    d = d[d.bookmaker.isin(MARKET_BOOKS)]

    g = pd.read_parquet(D / "g.parquet")
    g["home_score"] = pd.to_numeric(g.home_score, errors="coerce")
    g["away_score"] = pd.to_numeric(g.away_score, errors="coerce")
    home_of = g.set_index("game_id").home_team
    g["canon"] = g.twin_of.fillna(g.game_id)
    g["flip"] = g.twin_of.notna() & (g.twin_of.map(home_of) != g.home_team)
    h = pd.read_parquet(D / "h1_scores.parquet").set_index("game_id")
    g["h1_home"] = np.where(g.flip, g.canon.map(h.h1_away), g.canon.map(h.h1_home))
    g["h1_away"] = np.where(g.flip, g.canon.map(h.h1_home), g.canon.map(h.h1_away))
    g["h1m"] = g.h1_home - g.h1_away
    g["h1t"] = g.h1_home + g.h1_away
    cols = ["game_id", "canon", "season", "week", "kick", "et_date", "home_team", "away_team", "margin", "total",
            "home_score", "away_score", "h1m", "h1t", "close_spread", "close_total"]
    d = d.merge(g[cols], on="game_id", how="inner")
    d = d[d.margin.notna() & d.season.isin([2023, 2024, 2025]) & (d.ts < d.kick - pd.Timedelta(minutes=5))].copy()
    # one odds id per real game
    n = d.groupby(["canon", "game_id"]).size().reset_index(name="n").sort_values(["canon", "n"], ascending=[True, False])
    keep = set(n.drop_duplicates("canon").game_id)
    dropped = d.game_id.nunique() - len(keep)
    d = d[d.game_id.isin(keep)].copy()

    # the full-game middle of the same minute (ten fetched books)
    q = pd.read_parquet(D / "q_hist.parquet")
    q = q[q.game_id.isin(keep)].copy()
    q["hour"] = q.pull_ts.dt.floor("h")
    q = q.sort_values("pull_ts").drop_duplicates(["game_id", "hour", "bookmaker"], keep="last")
    med = q.groupby(["game_id", "hour"]).spread_home.transform("median")
    cnt = q.groupby(["game_id", "hour"]).spread_home.transform("count")
    q.loc[(np.sign(q.spread_home) * np.sign(med) < 0) & (cnt >= 3), "spread_home"] = np.nan   # feed sign errors
    fg = q.groupby(["game_id", "hour"]).agg(fg_spread=("spread_home", "median"), fg_total=("total_line", "median"),
                                            fg_n=("spread_home", "count")).reset_index()
    d["hour"] = d.ts.dt.floor("h")
    d = d.merge(fg, on=["game_id", "hour"], how="left")

    # long form: a row per side
    def side_rows(x, market, side, price, line, res):
        o = x[["game_id", "canon", "slot", "bookmaker", "season", "week", "et_date", "kick", "ts", "home_team",
               "away_team", "fg_spread", "fg_total", "fg_n", "close_spread", "close_total", "margin", "total",
               "home_score", "away_score", "h1m", "h1t"]].copy()
        o["market"], o["side"] = market, side
        o["price"], o["line"], o["res"] = price, line, res
        return o

    out = []
    m = d[d.market == "h2h_h1"]
    out += [side_rows(m, "h2h_h1", "home", m.home_price, np.nan, np.sign(m.h1m)),
            side_rows(m, "h2h_h1", "away", m.away_price, np.nan, -np.sign(m.h1m))]
    m = d[d.market == "spreads_h1"]
    out += [side_rows(m, "spreads_h1", "home", m.home_price, m.spread_home, np.sign(m.h1m + m.spread_home)),
            side_rows(m, "spreads_h1", "away", m.away_price, -m.spread_home, -np.sign(m.h1m + m.spread_home))]
    m = d[d.market == "totals_h1"]
    out += [side_rows(m, "totals_h1", "over", m.over_price, m.total_line, np.sign(m.h1t - m.total_line)),
            side_rows(m, "totals_h1", "under", m.under_price, m.total_line, -np.sign(m.h1t - m.total_line))]
    for mk, pts in (("team_totals_home", "home_score"), ("team_totals_away", "away_score")):
        m = d[d.market == mk]
        out += [side_rows(m, mk, "over", m.over_price, m.total_line, np.sign(m[pts] - m.total_line)),
                side_rows(m, mk, "under", m.under_price, m.total_line, -np.sign(m[pts] - m.total_line))]
    L = pd.concat(out, ignore_index=True)
    # pair id: the two sides of one quote share it (the other side's price de-vigs this one)
    L["qkey"] = (L.game_id + "|" + L.slot + "|" + L.bookmaker + "|" + L.market + "|" +
                 L.line.abs().round(2).fillna(-1.0).astype(str))   # a moneyline has no line
    L = L[L.price.notna()].copy()
    L["dec"] = dec(L.price)
    other = L.groupby("qkey").dec.transform("sum") - L.dec
    both = L.groupby("qkey").dec.transform("size") == 2
    L = L[both].copy()
    L["dec_o"] = other[both]
    s = 1 / L.dec + 1 / L.dec_o
    L = L[(s >= 1.0) & (s <= 1.15)].copy()
    L["over_round"] = 1 / L.dec + 1 / L.dec_o - 1
    L["p_nv"] = power_devig(L.dec.to_numpy(), L.dec_o.to_numpy())
    # the main line of a book that posts a ladder: the pair nearest even money
    L["gap"] = (L.dec - L.dec_o).abs()
    L["main"] = L.gap == L.groupby(["game_id", "slot", "bookmaker", "market"]).gap.transform("min")
    L["risk"], L["win"] = stake(L.dec)
    L["pnl"] = np.where(L.res > 0, L.win, np.where(L.res < 0, -L.risk, 0.0))
    L.loc[L.res.isna(), "pnl"] = np.nan
    L["fav"] = np.where(L.fg_spread.isna(), "", np.where(L.fg_spread < 0, "home", np.where(L.fg_spread > 0, "away", "pick")))
    if verbose:
        print(f"quotes (a row per side): {len(L)} | games {L.canon.nunique()} ({dropped} duplicate odds ids dropped) | "
              f"graded {int(L.res.notna().sum())}")
        print(L.groupby(["market", "season"]).agg(rows=("res", "size"), graded=("res", "count"),
                                                  games=("canon", "nunique")).unstack().to_string())
    return L


# ── grading ──────────────────────────────────────────────────────────────────

def boot(b, n=2000):
    if b.empty:
        return np.nan, np.nan
    per = b.groupby("et_date").agg(p=("pnl", "sum"), r=("risk", "sum"))
    idx = RNG.integers(0, len(per), size=(n, len(per)))
    p, r = per.p.to_numpy()[idx].sum(1), per.r.to_numpy()[idx].sum(1)
    roi = p / np.where(r == 0, np.nan, r)
    return float(np.nanpercentile(roi, 2.5)), float(np.nanpercentile(roi, 97.5))


def summ(b, label=""):
    b = b[b.res.notna()]
    if b.empty:
        return dict(rule=label, bets=0)
    lo, hi = boot(b)
    w, l, p = int((b.res > 0).sum()), int((b.res < 0).sum()), int((b.res == 0).sum())
    out = dict(rule=label, bets=len(b), w=w, l=l, push=p, risked=round(b.risk.sum(), 1), units=round(b.pnl.sum(), 2),
               roi=round(b.pnl.sum() / b.risk.sum(), 4), lo=round(lo, 4), hi=round(hi, 4),
               med_price=int(np.median(b.price)))
    for s in (2023, 2024, 2025):
        x = b[b.season == s]
        out[f"n{s % 100}"] = len(x)
        out[f"u{s % 100}"] = round(x.pnl.sum(), 2)
    wk = b.week.fillna(99)
    out["early"] = round(b[wk <= 7].pnl.sum(), 2)
    out["late"] = round(b[wk > 7].pnl.sum(), 2)
    return out


def table(rows):
    t = pd.DataFrame(rows)
    return t.to_string(index=False)


def one_per_game(b, by=("canon", "slot", "market"), score="edge"):
    return b.sort_values(score, ascending=False).drop_duplicates(list(by))


if __name__ == "__main__":
    load()
