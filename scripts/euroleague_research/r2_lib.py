"""EuroLeague FULL-GAME research, round 1 (files r2_*): the shared pieces.

FROZEN BEFORE ANY RESULT WAS READ (2026-11-13):

  Data      the local parquet cache only (C:\\Users\\micha\\euroleague_research\\cache):
            games.parquet, fullgame_quotes.parquet. No database, no API.
  Markets   h2h, spreads, totals (full game, overtime included).
  Books     decidable: draftkings, fanduel, betmgm, betrivers, fanatics.
            Sharp reference (never a bet): pinnacle.
            Reference only: bovada, marathonbet, unibet, paddypower.
  Coherent  a quote counts only when both prices are finite American odds
            (|p| >= 100) and the two implied chances sum to 1.00-1.15. The
            rest are dropped and counted (r2_coverage.py).
  Settle    spread: home covers when (home - away) + spread_home > 0, push at 0.
            total: push when equal. moneyline: overtime included, a full game
            cannot tie (every regulation tie went to overtime).
  Stake     1 unit to win, risk capped at 3: p < 0 risks min(|p|/100, 3) to
            win risk*100/|p|; p > 0 risks 1 to win p/100.
  Return    units won / units risked on graded (non-push) bets.
  Interval  90%, resampling game DATES (1,000 draws), r1_lib.summary.
  Board at T  per (game, market, book), the last stored row with
            snapshot_at <= T (the store is change-only). T is always a LEDGER
            snapshot time (snapshots.parquet): snapshot_at is the book's own
            update stamp, which the snapshot at or after it captured
            (r2_coverage.py F: 100% within 900 s). seen_at = that ledger time.

DECISION TIMES (fixed before any return was read):
  close     the last ledger snapshot <= tip - 10 min
  6h        the last ledger snapshot <= tip - 6 h
  60m       the last ledger snapshot <= tip - 60 min
  15utc     the last ledger snapshot <= 15:00 UTC on the game date (the
            catalogued line-shopping / own-spread instant); a game tipping
            less than 5 minutes after it is not priced
  first     a book's first post = the ledger snapshot that captured its
            first row (seen_at of that row)
  Main read: (a) line shopping and (b) own spread at 15utc; (d) sharp-vs-soft
  at close; the rest are "other reads".

CUT GRIDS (fixed before any return was read):
  (a) spreads / totals edge (P(win|no push) - implied incl. vig):
      0.00, 0.01, 0.02, 0.03, 0.04, 0.05; catalogued 0.03, >= 3 other books
      in the consensus.
  (b) moneyline own-spread edge: 0.000 .. 0.030 step 0.005; catalogued 0.010.
  (c) first post, Pinnacle reference: 0.000 .. 0.030 step 0.005; catalogued
      0.015 (the first-post card's cut).
  (d) sharp-vs-soft edge (Pinnacle no-vig P - implied of the soft price,
      same line): 0.00, 0.01, 0.02, 0.03, 0.04; headline 0.01.
  Moneylines: every side shorter than -200 removed BEFORE the pick (the
  repo's cap); the unfloored version reported once, by price band.

DE-VIG: power for moneylines, multiplicative for spreads and totals.

CONSENSUS for (a): the median of every book's standing line at T (all ten,
  Pinnacle and the references included, the priced book included), >= 3
  others up. Before 2025-26 DraftKings is the only decidable book, so a
  decidable-only median is its own line and could bet nothing; the
  catalogued decidable-only consensus is run as a variant (2025-26 on).

MARGIN TABLE: models/ncaab_margin_dist.fit unchanged (kernel to 500 games),
  fitted on every earlier season's (final margin, -closing consensus);
  totals the same kernel on (total - 160, closing consensus total - 160).
  The walk-forward headline starts at 2024 (2022-23, trained on 2021-22 and
  2022-23); 2022-23 read on a one-season table is printed separately and
  flagged. c = mean(margin + consensus at 15utc) over the training seasons.

RELOCATED "HOME" GAMES (from the stored venue names, r2_venues.py):
  R1, the scout's list: TEL at ALEKSANDAR NIKOLIC HALL, BELGRADE ARENA
      (Belgrade) and SPYROS KYPRIANOU ATHLETIC CENTER (Limassol); HTA at
      ARENA 8888 SOFIA and ARENA BOTEVGRAD; DUB at ZETRA ARENA (Sarajevo) and
      ARENA HUSEJIN SMAJLOVIC ZENICA.
  R2, other one-off venues outside the club's country, not flagged neutral:
      IST at MORACA (Podgorica) and ARENA RIGA; ULK at SAP GARDEN (Munich),
      KALNAPILIO ARENA (Panevezys) and ZALGIRIO ARENA (Kaunas); PAR at
      BMW PARK (Munich).
  Excluded, location not established from the name: IST at XIAOMI ARENA.
  Not relocated (same country): TEL and HTA at PAIS ARENA JERUSALEM and
  MENORA MIVTACHIM ARENA, IST at ANTALYA SPORTS HALL.
  neutral_site = True (Final Four and other flagged games) is excluded from
  every "home" baseline.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent.parent))   # the repo, for models.ncaab_margin_dist

import r1_lib  # noqa: E402  (imp, dec, stake, summary, bh)

CACHE = Path(r"C:\Users\micha\euroleague_research\cache")
DECIDABLE = ["draftkings", "fanduel", "betmgm", "betrivers", "fanatics"]
SHARP = "pinnacle"
REFS = ["bovada", "marathonbet", "unibet", "paddypower"]
ALLBOOKS = DECIDABLE + [SHARP] + REFS
MARKETS = ["h2h", "spreads", "totals"]
ISUM_LO, ISUM_HI = 1.00, 1.15

imp = r1_lib.imp
dec = r1_lib.dec
stake = r1_lib.stake
summary = r1_lib.summary
bh = r1_lib.bh


def power_fair(p1, p2):
    """Power de-vig (the k with p1^k + p2^k = 1), the repo's routine."""
    p1 = np.asarray(p1, float)
    p2 = np.asarray(p2, float)
    lo = np.full(p1.shape, 0.5)
    hi = np.full(p1.shape, 3.0)
    for _ in range(60):
        k = (lo + hi) / 2
        s = p1 ** k + p2 ** k
        lo = np.where(s > 1, k, lo)
        hi = np.where(s > 1, hi, k)
    k = (lo + hi) / 2
    return p1 ** k, p2 ** k


def load_games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "games.parquet")
    g["tip"] = pd.to_datetime(g.commence_time, utc=True)
    g["margin"] = g.home_score - g.away_score
    g["total"] = g.home_score + g.away_score
    return g


def load_quotes(coherent_only: bool = True, games: pd.DataFrame | None = None) -> pd.DataFrame:
    """Long quotes: line (spread_home / total_line / NaN), pa (home or over),
    pb (away or under), isum, pa_mult (multiplicative no-vig P(side a)),
    pa_pow (power no-vig), coherent, lead_min (minutes before tip), plus the
    game's season, date, tip, margin, total, played."""
    g = load_games() if games is None else games
    q = pd.read_parquet(CACHE / "fullgame_quotes.parquet")
    tot = q.market == "totals"
    q["line"] = np.where(q.market == "spreads", q.spread_home,
                         np.where(tot, q.total_line, np.nan))
    q["pa"] = np.where(tot, q.over_price, q.home_price)
    q["pb"] = np.where(tot, q.under_price, q.away_price)
    ok = np.isfinite(q.pa) & np.isfinite(q.pb) & (q.pa.abs() >= 100) & (q.pb.abs() >= 100)
    ok &= (q.market == "h2h") | np.isfinite(q.line)
    ia = np.where(ok, imp(np.where(ok, q.pa, 100)), np.nan)
    ib = np.where(ok, imp(np.where(ok, q.pb, 100)), np.nan)
    q["isum"] = ia + ib
    q["coherent"] = ok & (q.isum >= ISUM_LO) & (q.isum <= ISUM_HI)
    q["pa_mult"] = ia / q.isum
    pf = power_fair(np.where(ok, ia, 0.5), np.where(ok, ib, 0.5))[0]
    q["pa_pow"] = np.where(ok, pf, np.nan)
    q = q.merge(g[["game_id", "season", "game_date", "tip", "played", "margin", "total",
                   "home_code", "away_code", "phase"]], on="game_id", how="left")
    q["lead_min"] = (q.tip - q.snapshot_at).dt.total_seconds() / 60
    q = q[q.snapshot_at <= q.tip]
    q = q.drop(columns=["created_at", "home_price", "away_price", "spread_home", "total_line",
                        "over_price", "under_price"])
    q = q.sort_values(["game_id", "market", "bookmaker", "snapshot_at"], kind="mergesort")
    if coherent_only:
        q = q[q.coherent]
    return q.reset_index(drop=True)


_LEDGER = None


def ledger() -> np.ndarray:
    """Sorted ledger snapshot times, int64 microseconds UTC."""
    global _LEDGER
    if _LEDGER is None:
        s = pd.read_parquet(CACHE / "snapshots.parquet").snapshot_ts
        _LEDGER = np.sort(s.values.astype("datetime64[us]").astype(np.int64))
    return _LEDGER


def _to_us(t) -> np.ndarray:
    return pd.to_datetime(t, utc=True).values.astype("datetime64[us]").astype(np.int64)


def _from_us(a) -> pd.DatetimeIndex:
    return pd.to_datetime(np.asarray(a).astype("datetime64[us]")).tz_localize("UTC")


def seen_at(snapshot_at: pd.Series) -> pd.Series:
    """The ledger snapshot at or after each update stamp (the one that captured it)."""
    st = ledger()
    i = np.clip(np.searchsorted(st, _to_us(snapshot_at), side="left"), 0, len(st) - 1)
    return pd.Series(_from_us(st[i]), index=snapshot_at.index)


def ledger_before(t: pd.Series) -> pd.Series:
    """The last ledger snapshot at or before each time."""
    st = ledger()
    i = np.searchsorted(st, _to_us(t), side="right") - 1
    out = _from_us(st[np.clip(i, 0, len(st) - 1)])
    return pd.Series(np.where(i >= 0, out, pd.NaT), index=t.index)


def decision_times(g: pd.DataFrame) -> pd.DataFrame:
    """Per game_id: close, 6h, 60m, 15utc (ledger times, see the docstring)."""
    tip = g.set_index("game_id").tip
    d = pd.DataFrame(index=tip.index)
    d["close"] = ledger_before(tip - pd.Timedelta(minutes=10))
    d["6h"] = ledger_before(tip - pd.Timedelta(hours=6))
    d["60m"] = ledger_before(tip - pd.Timedelta(minutes=60))
    t15 = pd.to_datetime(g.set_index("game_id").game_date).dt.tz_localize("UTC") + pd.Timedelta(hours=15)
    ok = t15 <= tip - pd.Timedelta(minutes=5)
    d["15utc"] = ledger_before(t15).where(ok)
    for c in d.columns:
        d[c] = pd.to_datetime(d[c], utc=True)
    return d


def board_at(q: pd.DataFrame, T: pd.Series) -> pd.DataFrame:
    """Per (game, market, book) the last row with snapshot_at <= T[game].
    T: Series indexed by game_id (UTC timestamps)."""
    z = q.merge(T.rename("T").reset_index().rename(columns={"index": "game_id"}),
                on="game_id", how="inner")
    z = z[z.snapshot_at <= z["T"]]
    return z.drop_duplicates(["game_id", "market", "bookmaker"], keep="last").reset_index(drop=True)


def first_posts(q: pd.DataFrame) -> pd.DataFrame:
    return q.drop_duplicates(["game_id", "market", "bookmaker"], keep="first").reset_index(drop=True)


def last_pretip(q: pd.DataFrame) -> pd.DataFrame:
    return q.drop_duplicates(["game_id", "market", "bookmaker"], keep="last").reset_index(drop=True)


def result(market, side, line, margin, total):
    """+1 win, 0 push, -1 loss. side: home/away/over/under."""
    side = np.asarray(side)
    line = np.asarray(line, float)
    margin = np.asarray(margin, float)
    total = np.asarray(total, float)
    if market == "spreads":
        r = np.sign(margin + line)
        return np.where(side == "home", r, -r).astype(int)
    if market == "totals":
        r = np.sign(total - line)
        return np.where(side == "over", r, -r).astype(int)
    r = np.sign(margin)
    return np.where(side == "home", r, -r).astype(int)


def _check():
    assert list(result("spreads", ["home", "away"], [-6.5, -6.5], [7, 7], [0, 0])) == [1, -1]
    assert list(result("spreads", ["home", "away"], [3, 3], [-3, -3], [0, 0])) == [0, 0]
    assert list(result("spreads", ["home", "away"], [3.5, 3.5], [-3, -3], [0, 0])) == [1, -1]
    assert list(result("totals", ["over", "under"], [160, 160.5], [0, 0], [160, 160])) == [0, 1]
    assert list(result("h2h", ["home", "away"], [np.nan, np.nan], [2, 2], [0, 0])) == [1, -1]
    r, w = stake(np.array([-150, -400, 120]))
    assert np.allclose(r, [1.5, 3.0, 1.0]) and np.allclose(w, [1.0, 0.75, 1.2])


_check()


def grade(df: pd.DataFrame, market_col="market", side_col="side", line_col="line",
          price_col="price") -> pd.DataFrame:
    """Adds res, risk, units. df needs margin, total."""
    df = df.copy()
    res = np.zeros(len(df), int)
    for m in MARKETS:
        k = (df[market_col] == m).to_numpy()
        if k.any():
            res[k] = result(m, df.loc[k, side_col].to_numpy(), df.loc[k, line_col].to_numpy(),
                            df.loc[k, "margin"].to_numpy(), df.loc[k, "total"].to_numpy())
    df["res"] = res
    risk, win = stake(df[price_col].to_numpy())
    df["risk"] = np.where(df.res == 0, 0.0, risk)
    df["units"] = np.where(df.res > 0, win, np.where(df.res < 0, -risk, 0.0))
    return df


def sides_long(b: pd.DataFrame) -> pd.DataFrame:
    """Each quote as two sides: side, price, fair (multiplicative no-vig of
    that side), fav (True when the side is the favourite by price)."""
    a = b.copy()
    a["side"] = np.where(a.market == "totals", "over", "home")
    a["price"] = a.pa
    a["fair"] = a.pa_mult
    c = b.copy()
    c["side"] = np.where(c.market == "totals", "under", "away")
    c["price"] = c.pb
    c["fair"] = 1 - c.pa_mult
    z = pd.concat([a, c], ignore_index=True)
    z["fav"] = z.fair > 0.5
    return z


def ml_band(price) -> np.ndarray:
    p = np.asarray(price, float)
    return np.select([p <= -500, p <= -200, p <= 100, p <= 300],
                     ["<=-500", "-500..-200", "-200..+100", "+100..+300"], ">+300")


BANDS = ["<=-500", "-500..-200", "-200..+100", "+100..+300", ">+300"]


def p_one_sided(df: pd.DataFrame, n_boot: int = 1000, seed: int = 7) -> float:
    """One-sided p for 'return > 0': normal tail of return / sd of the same
    date bootstrap r1_lib.summary draws (seed 7), for the multiplicity test."""
    if len(df) == 0 or df.risk.sum() <= 0:
        return np.nan
    by = df.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    rng = np.random.default_rng(seed)
    k = len(by)
    idx = rng.integers(0, k, size=(n_boot, k))
    U = by.u.to_numpy()[idx].sum(1)
    R = by.r.to_numpy()[idx].sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rr = U / R
    sd = np.nanstd(rr)
    ret = df.units.sum() / df.risk.sum()
    if not np.isfinite(sd) or sd == 0:
        return np.nan
    from math import erfc, sqrt
    return 0.5 * erfc((ret / sd) / sqrt(2))


def row(label: dict, df: pd.DataFrame) -> dict:
    s = summary(df) if len(df) else summary(df.iloc[0:0])
    d = dict(label)
    d.update({k: s[k] for k in ("bets", "W", "L", "P", "units", "ret%", "lo%", "hi%")})
    d["p_one"] = round(p_one_sided(df), 4) if len(df) else np.nan
    return d


def md_table(df: pd.DataFrame) -> str:
    """A pandas frame as a markdown table, NaN shown as blank."""
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for i in range(len(df)):
        vals = []
        for c in cols:
            v = df[c].iloc[i]
            if isinstance(v, (np.integer, int)) and not isinstance(v, bool):
                vals.append(str(int(v)) if "season" in str(c) else f"{int(v):,}")
            elif isinstance(v, (float, np.floating)):
                v = float(v)
                if "season" in str(c) and np.isfinite(v):
                    vals.append(str(int(v)))
                    continue
                if str(c) == "cut" and np.isfinite(v):
                    vals.append(f"{v:.3f}")
                    continue
                four = any(k in str(c) for k in ("loss", "brier", "slope", "icpt", "corr", "fair_", "p_", "rate"))
                vals.append("" if not np.isfinite(v) else (f"{v:,.4f}" if four else f"{v:,.2f}"))
            else:
                vals.append(str(v))
        out.append("| " + " | ".join(vals) + " |")
    return "\n".join(out)
