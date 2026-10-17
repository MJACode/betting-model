"""NBA full-game markets lab: moneyline, spread, total -- priced, graded, in units.

Owner: the game_market research key of the 2026-27 NBA rebuild
(docs/nba_models_2026.md section 1 holds the pre-registered bars this grades
against; nothing here re-thresholds after the fact).

WHAT IT DOES (every section reads the local parquet cache, never Supabase):

  checks      fetches per game, books per fetch, in-play exclusion, coherent
              quotes, Pinnacle coverage by season and by fetch hour, open/close
              timing, score validation against summed player points, and a
              hand-worked spread-sign assertion.
  baselines   blind home/away, favourite/dog, over/under at the open and the
              close, at DraftKings and at the best bettable price at
              DraftKings' number, by season.
  sharp       the NHL totals rule for all three markets: Pinnacle de-vigged
              (proportional and power) inside ONE fetch, compared with every
              bettable book at the SAME number in that fetch; a game is bet once
              per market, at the first fetch that qualifies, at the best EV.
              Grid: EV floor 0.000-0.050 x market x side family x de-vig, plus a
              DraftKings-only variant and a DraftKings-as-reference placebo.
  gap         a bettable book whose spread/total NUMBER differs from Pinnacle's
              in the same fetch; fair probability at the off-market number from
              a normal margin/total distribution (mean solved from Pinnacle's
              no-vig price, SD fit on the seasons before).
  situational early-season unders, and league scoring drifting away from the
              closing total.

DEFINITIONS (stated once, used everywhere):

  FETCH       one historical snapshot = one `created_at` (the ingestor writes a
              snapshot in one transaction). Its decision time is the latest
              `snapshot_at` in it (the API snapshot sits 3-16 minutes before
              the requested hour, which is that time rounded up to the hour).
  PRE-GAME    snapshot_type 'open' AND snapshot_at <= commence_time AND the
              fetch's decision time < commence_time.
  COHERENT    a two-way quote whose implied probabilities sum to 1.00-1.15.
  BETTABLE    config.BEST_LINE_BOOKMAKERS (Pinnacle and Bovada are not).
  PRICE FLOOR config.DEFAULT_MIN_ODDS (-200), the house rule every live model
              bets under; the count it removes is reported.
  UNITS       one unit to win; risk = 1/(decimal-1) capped at 3
              (tracking/discord_notifier.stake_for). A push returns the stake
              (0 units) and its risk stays in the ROI denominator.
  SPREAD      spread_home is the HOME number. Home covers when
              (home - away) + spread_home > 0; away covers when < 0; 0 pushes.
  SEASONS     ending-year labels (2026 = 2025-26). Graded: 2022-2026. The cut is
              chosen on 2022-2025 and confirmed on 2026. 2021 is fit-only.

    PYTHONPATH=. PYTHONIOENCODING=utf-8 python scripts/nba_game_market_lab.py --all
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import config  # noqa: E402

CACHE = ROOT / "data" / "local" / "nba"
OUT = Path(os.environ.get("NBA_REBUILD_RESULTS",
                          "C:/Users/micha/AppData/Local/Temp/nba_rebuild/results"))
SCRATCH = OUT / "game_market_work"
REPORT = OUT / "game_market.md"

SHARP = "pinnacle"
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
BOOK_RANK = {b: i for i, b in enumerate(BETTABLE)}
REF_BOOK = "draftkings"
PRICE_FLOOR = float(config.DEFAULT_MIN_ODDS)          # -200
COHERENT = (1.00, 1.15)
MAX_RISK = 3.0
GRADED = [2022, 2023, 2024, 2025, 2026]
CHOOSE = [2022, 2023, 2024, 2025]
CONFIRM = 2026
ALL_SEASONS = [2021] + GRADED
LIVE_SEASON_START = "2026-10-20"
EV_FLOORS = [round(0.005 * i, 3) for i in range(11)]  # 0.000 .. 0.050
# The live scorer prices games up to GAME_SCORE_AHEAD_DAYS out; a quote further
# ahead than that (Christmas and MLK-day fixtures listed ~1,500 h early) is not a
# decision the live card could take.
MAX_LEAD_H = 24.0 * float(getattr(config, "GAME_SCORE_AHEAD_DAYS", 7))
N_BOOT, SEED = 4000, 7
MARKETS = ("h2h", "spreads", "totals")
MARKET_NAME = {"h2h": "moneyline", "spreads": "spread", "totals": "total"}
FAMILIES = {"h2h": ["all", "home", "away", "fav", "dog"],
            "spreads": ["all", "home", "away", "fav", "dog"],
            "totals": ["all", "over", "under"]}

_REPORT_PARTS: dict[str, str] = {}


# ── small helpers ───────────────────────────────────────────────────────────

def dec(american):
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 1.0 + a / 100.0, 1.0 + 100.0 / np.abs(a))


def imp(american):
    a = np.asarray(american, dtype=float)
    return np.where(a > 0, 100.0 / (a + 100.0), np.abs(a) / (np.abs(a) + 100.0))


def risk_win(price):
    d = dec(price)
    r = np.minimum(1.0 / (d - 1.0), MAX_RISK)
    return r, r * (d - 1.0)


def units_for(result, price):
    r, w = risk_win(price)
    res = np.asarray(result)
    return np.where(res == "W", w, np.where(res == "L", -r, 0.0)), r


def power_devig(pa, pb, iters=30):
    """k such that pa**k + pb**k = 1 (pa+pb > 1 so k > 1); returns (qa, qb). Newton."""
    pa = np.asarray(pa, float)
    pb = np.asarray(pb, float)
    la, lb = np.log(pa), np.log(pb)
    k = np.ones(pa.shape)
    for _ in range(iters):
        ea, eb = np.exp(k * la), np.exp(k * lb)
        f = ea + eb - 1.0
        fp = ea * la + eb * lb
        step = f / np.where(fp == 0, -1e-12, fp)
        k = k - step
        if np.nanmax(np.abs(step)) < 1e-12:
            break
    return np.exp(k * la), np.exp(k * lb)


def norm_cdf(x):
    from scipy.special import ndtr
    return ndtr(np.asarray(x, float))


def norm_ppf(p):
    from scipy.special import ndtri
    return ndtri(np.asarray(p, float))


def md_table(df: pd.DataFrame, floatfmt: str = "{:.2f}") -> str:
    if df is None or len(df) == 0:
        return "(empty)\n"
    cols = list(df.columns)
    out = ["| " + " | ".join(str(c) for c in cols) + " |",
           "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, (float, np.floating)):
                cells.append("" if pd.isna(v) else floatfmt.format(v))
            else:
                cells.append(str(v))
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def report(section: str, text: str) -> None:
    """Keep every section's text, and rewrite the report each time one lands."""
    _REPORT_PARTS[section] = text
    path = SCRATCH / f"report_{section}.md"
    path.write_text(text, encoding="utf-8")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ── settlement ──────────────────────────────────────────────────────────────

def settle(market, side, line, home, away):
    """W/L/P from final scores (OT included). Vectorised over arrays."""
    market = np.asarray(market)
    side = np.asarray(side)
    line = np.asarray(line, float)
    margin = np.asarray(home, float) - np.asarray(away, float)
    total = np.asarray(home, float) + np.asarray(away, float)
    out = np.full(margin.shape, "", dtype=object)
    # moneyline: no ties in the NBA
    ml = market == "h2h"
    hw = margin > 0
    out[ml & (side == "home")] = np.where(hw, "W", "L")[ml & (side == "home")]
    out[ml & (side == "away")] = np.where(hw, "L", "W")[ml & (side == "away")]
    sp = market == "spreads"
    cov = margin + line                       # line = spread_home
    hres = np.where(cov > 0, "W", np.where(cov < 0, "L", "P"))
    ares = np.where(cov < 0, "W", np.where(cov > 0, "L", "P"))
    out[sp & (side == "home")] = hres[sp & (side == "home")]
    out[sp & (side == "away")] = ares[sp & (side == "away")]
    tt = market == "totals"
    ores = np.where(total > line, "W", np.where(total < line, "L", "P"))
    ures = np.where(total < line, "W", np.where(total > line, "L", "P"))
    out[tt & (side == "over")] = ores[tt & (side == "over")]
    out[tt & (side == "under")] = ures[tt & (side == "under")]
    return out


def _assert_spread_sign() -> None:
    """CLAUDE.md section 4: this sign has flipped twice. Fail loudly."""
    m = np.array(["spreads"] * 5)
    s = np.array(["home", "away", "home", "away", "home"])
    line = np.array([-6.5, -6.5, -6.5, -6.5, 3.0])
    home = np.array([107, 107, 100, 100, 97])
    away = np.array([100, 100, 103, 103, 100])
    got = list(settle(m, s, line, home, away))
    # home -6.5 wins by 7 -> home covers; away loses; home loses by 3 -> away
    # covers; home +3 loses by 3 -> push.
    assert got == ["W", "L", "L", "W", "P"], got
    # totals and moneyline
    assert list(settle(np.array(["totals"] * 3), np.array(["over", "under", "over"]),
                       np.array([220.5, 220.5, 207.0]), np.array([110, 110, 107]),
                       np.array([111, 111, 100]))) == ["W", "L", "P"]
    assert list(settle(np.array(["h2h", "h2h"]), np.array(["home", "away"]),
                       np.array([np.nan, np.nan]), np.array([99, 99]),
                       np.array([100, 100]))) == ["L", "W"]


# ── loading ─────────────────────────────────────────────────────────────────

def load_games() -> pd.DataFrame:
    g = pd.read_parquet(CACHE / "nba_games.parquet")
    g = g[g["game_date"] < LIVE_SEASON_START].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True)
    keep = ["game_id", "season", "game_date", "home_team", "away_team",
            "home_score", "away_score", "tip", "neutral_site", "went_to_ot"]
    return g[keep]


def load_lines(seasons=ALL_SEASONS) -> tuple[pd.DataFrame, dict]:
    """Pre-game game-line rows, one per (game, market, book, fetch)."""
    cols = ["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "source",
            "created_at", "home_price", "away_price", "spread_home", "total_line",
            "over_price", "under_price"]
    o = pd.read_parquet(CACHE / "nba_odds.parquet", columns=cols)
    stats = {"rows_cache": len(o)}
    try:
        stats["cache_pulled_at"] = json.loads((CACHE / "manifest.json").read_text(
            encoding="utf-8"))["nba_odds"]["pulled_at"]
    except Exception:  # noqa: BLE001 - the manifest is informational here
        stats["cache_pulled_at"] = "unknown"
    o = o[(o["source"] == "odds_api_historical") & o["market"].isin(MARKETS)].copy()
    stats["rows_historical_lines"] = len(o)
    o["snap"] = pd.to_datetime(o["snapshot_at"], utc=True)
    # The fetch's decision time is its newest quote, measured over EVERY row the
    # fetch wrote (in-play rows included: they are the same API snapshot).
    # integer fetch id: one per created_at (string keys make every merge slow)
    o["fid"] = pd.factorize(o["created_at"], sort=True)[0].astype(np.int32)
    ft = o.groupby("fid")["snap"].max().rename("fetch_ts")
    # Two ingestor processes walking one season from both ends can buy the same snapshot
    # twice (measured: 3 requested hours, byte-identical rows 1.5 s apart). Keep the
    # later purchase of each requested hour so no quote is counted twice.
    req = ft.dt.ceil("h")
    keep_fid = req.reset_index().groupby("fetch_ts")["fid"].max()
    stats["duplicate_fetches_dropped"] = int(len(ft) - len(keep_fid))
    stats["rows_in_duplicate_fetches"] = int((~o["fid"].isin(keep_fid.to_numpy())).sum())
    o = o[o["fid"].isin(keep_fid.to_numpy())]
    o = o.join(ft, on="fid")
    o["req_ts"] = o["fetch_ts"].dt.ceil("h")
    g = load_games()
    o = o.merge(g, on="game_id", how="inner")
    o = o[o["season"].isin(seasons)]
    stats["rows_in_seasons"] = len(o)
    stats["rows_in_play"] = int((o["snapshot_type"] == "in_play").sum())
    o = o[o["snapshot_type"] == "open"]
    late = (o["snap"] > o["tip"]) | (o["fetch_ts"] >= o["tip"])
    stats["rows_open_after_tip"] = int(late.sum())
    o = o[~late]
    o = o.sort_values("snap")
    before = len(o)
    o = o.drop_duplicates(["game_id", "market", "bookmaker", "fid"], keep="last")
    stats["rows_duplicate_dropped"] = before - len(o)
    o["hours_to_tip"] = (o["tip"] - o["fetch_ts"]).dt.total_seconds() / 3600.0
    # the two-way implied sum
    a, b = _sides(o)
    o["imp_a"], o["imp_b"] = imp(a), imp(b)
    o["overround"] = o["imp_a"] + o["imp_b"]
    o["coherent"] = (o["overround"] >= COHERENT[0]) & (o["overround"] <= COHERENT[1]) \
        & np.isfinite(a) & np.isfinite(b)
    o["line"] = np.where(o["market"] == "spreads", o["spread_home"],
                         np.where(o["market"] == "totals", o["total_line"], np.nan))
    o = o.reset_index(drop=True)
    stats["rows_used"] = len(o)
    return o, stats


def _sides(o: pd.DataFrame):
    """(side A price, side B price): home/away for h2h and spreads, over/under for totals."""
    is_t = (o["market"] == "totals").to_numpy()
    a = np.where(is_t, o["over_price"], o["home_price"]).astype(float)
    b = np.where(is_t, o["under_price"], o["away_price"]).astype(float)
    return a, b


SIDE_A = {"h2h": "home", "spreads": "home", "totals": "over"}
SIDE_B = {"h2h": "away", "spreads": "away", "totals": "under"}


def fetch_table(o: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, fetch): when it is, relative to tip and the ET date."""
    f = (o.groupby(["game_id", "fid"])
         .agg(fetch_ts=("fetch_ts", "first"), req_ts=("req_ts", "first"),
              hours_to_tip=("hours_to_tip", "first"), game_date=("game_date", "first"),
              season=("season", "first"), tip=("tip", "first"))
         .reset_index())
    f["bucket"] = timing_bucket(f)
    f["hbucket"] = hours_bucket(f["hours_to_tip"])
    return f


def timing_bucket(f: pd.DataFrame) -> pd.Series:
    """evening before / morning / afternoon / within 2h, from the requested hour.

    'evening before' = requested before 12Z on the game's ET date (the D-1 22Z/23Z
    and D 00Z-03Z snapshots, and anything earlier); 'morning' = the 15Z game-day
    snapshot; 'within 2h' = 2 hours or less to tip; 'afternoon' = the rest."""
    gd = pd.to_datetime(f["game_date"]).dt.tz_localize("UTC")
    noon = gd + pd.Timedelta(hours=12)
    out = np.where(f["hours_to_tip"] <= 2.0, "within 2h",
                   np.where(f["req_ts"] < noon, "evening before",
                            np.where(f["req_ts"].dt.hour == 15, "morning", "afternoon")))
    return pd.Series(out, index=f.index)


def hours_bucket(h: pd.Series) -> pd.Series:
    bins = [-0.01, 2, 6, 12, 20, 32, 1e9]
    labels = ["0-2h", "2-6h", "6-12h", "12-20h", "20-32h", ">32h"]
    return pd.cut(h, bins=bins, labels=labels).astype(str)


# ── bootstrap and summaries ─────────────────────────────────────────────────

def boot_ci(bets: pd.DataFrame, n=N_BOOT, seed=SEED) -> tuple[float, float]:
    """Whole-day bootstrap 90% CI of ROI (units / risk), percent."""
    if len(bets) == 0:
        return (np.nan, np.nan)
    d = bets.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    U, R = d["u"].to_numpy(), d["r"].to_numpy()
    rng = np.random.default_rng(seed)
    D = len(d)
    idx = rng.integers(0, D, size=(n, D))
    roi = U[idx].sum(1) / R[idx].sum(1)
    return (100 * np.percentile(roi, 5), 100 * np.percentile(roi, 95))


def summ(b: pd.DataFrame, ci=False) -> dict:
    n = len(b)
    if n == 0:
        return {"bets": 0, "units": 0.0, "roi": np.nan}
    u, r = b["units"].sum(), b["risk"].sum()
    out = {"bets": n, "units": u, "roi": 100 * u / r if r else np.nan,
           "win%": 100 * (b["result"] == "W").sum() / max(1, (b["result"] != "P").sum())}
    if ci:
        lo, hi = boot_ci(b)
        out["ci_lo"], out["ci_hi"] = lo, hi
    return out


def by_season(b: pd.DataFrame, seasons=ALL_SEASONS) -> pd.DataFrame:
    rows = []
    for s in seasons:
        x = b[b["season"] == s]
        rows.append({"season": s, **summ(x)})
    return pd.DataFrame(rows)


def halves(b: pd.DataFrame) -> tuple[dict, dict]:
    """Chronological halves of the bet list by date (equal bet counts, split on a day)."""
    if len(b) == 0:
        return summ(b), summ(b)
    days = np.sort(b["game_date"].unique())
    cum = b.groupby("game_date").size().reindex(days).cumsum().to_numpy()
    cut = days[np.searchsorted(cum, cum[-1] / 2.0)]
    return summ(b[b["game_date"] <= cut]), summ(b[b["game_date"] > cut])


# ── score validation ────────────────────────────────────────────────────────

def validate_scores(g: pd.DataFrame) -> str:
    pl = pd.read_parquet(CACHE / "nba_player_game_log.parquet")
    cols = pl.columns.tolist()
    tcol = "team" if "team" in cols else ("team_abbrev" if "team_abbrev" in cols else None)
    pcol = "points" if "points" in cols else ("pts" if "pts" in cols else None)
    if tcol is None or pcol is None or "game_id" not in cols:
        return f"player game log lacks game_id/team/points columns ({cols[:20]}); not validated.\n"
    s = pl.groupby(["game_id", tcol])[pcol].sum().rename("pts").reset_index()
    gg = g[g["season"].isin(ALL_SEASONS)].copy()
    h = gg.merge(s, left_on=["game_id", "home_team"], right_on=["game_id", tcol], how="left")
    a = gg.merge(s, left_on=["game_id", "away_team"], right_on=["game_id", tcol], how="left")
    gg["home_pl"] = h["pts"].to_numpy()
    gg["away_pl"] = a["pts"].to_numpy()
    have = gg["home_pl"].notna() & gg["away_pl"].notna()
    bad = have & ((gg["home_pl"] != gg["home_score"]) | (gg["away_pl"] != gg["away_score"]))
    txt = (f"Scores checked against summed player points (nba_player_game_log): "
           f"{int(have.sum()):,} of {len(gg):,} games have both teams' box rows; "
           f"{int(bad.sum())} disagree.\n")
    if bad.any():
        txt += md_table(gg.loc[bad, ["game_id", "home_score", "away_score", "home_pl", "away_pl"]].head(15))
    nos = gg["home_score"].isna().sum()
    txt += f"Games with no stored final score: {int(nos)}.\n"
    return txt


# ── section: checks ─────────────────────────────────────────────────────────

def section_checks(o: pd.DataFrame, stats: dict, g: pd.DataFrame) -> None:
    log("checks")
    _assert_spread_sign()
    t = ["## 1. Data checks\n",
         "Spread-sign hand examples (home -6.5 wins by 7 covers; away covers when home "
         "loses by 3 at -6.5; home +3 losing by 3 pushes) asserted in code: PASS.\n",
         f"Row accounting (nba_odds.parquet pulled {stats.get('cache_pulled_at')}, source "
         "odds_api_historical, h2h/spreads/totals):\n",
         md_table(pd.DataFrame([{k: v for k, v in stats.items() if k != "cache_pulled_at"}]).T
                  .reset_index().rename(columns={"index": "step", 0: "rows"}), "{:,.0f}")]
    # one created_at per requested hour?
    fx = o.groupby("fid").agg(req_ts=("req_ts", "first")).reset_index()
    per_req = fx.groupby("req_ts").size()
    t.append(f"\nFetches: {len(fx):,} distinct `created_at`; {len(per_req):,} distinct requested "
             f"hours; requested hours holding more than one fetch: {int((per_req > 1).sum())}.\n")
    t.append(f"That count is after the loader dropped "
             f"{stats.get('duplicate_fetches_dropped', 0)} duplicate purchases of an already-bought "
             f"requested hour ({stats.get('rows_in_duplicate_fetches', 0):,} rows, byte-identical "
             "to the kept copy, written 1.5 s apart by two ingestor processes).\n")
    # coverage per season
    gs = g[g["season"].isin(ALL_SEASONS)].groupby("season").size().rename("games_in_schedule")
    cov = (o.groupby("season").agg(games_priced=("game_id", "nunique"),
                                   fetches=("fid", "nunique")))
    ft = fetch_table(o)
    fpg = ft.groupby(["season", "game_id"]).size().groupby("season").agg(["mean", "min", "max"])
    fpg.columns = ["fetches_per_game_mean", "min", "max"]
    bpf = (o.groupby(["season", "game_id", "fid", "market"])["bookmaker"].nunique()
           .groupby("season").mean().rename("books_per_fetch_market"))
    cv = pd.concat([gs, cov, fpg, bpf], axis=1).reset_index()
    t.append("\nCoverage by season (graded window 2022-2026; 2021 is fit-only):\n")
    t.append(md_table(cv))
    # books present
    bk = (o.groupby(["season", "bookmaker"])["game_id"].nunique().unstack(0).fillna(0).astype(int))
    t.append("\nGames each book quotes (any market, any pre-game fetch), by season:\n")
    t.append(md_table(bk.reset_index(), "{:,.0f}"))
    # coherence by book x market
    coh = (o.groupby(["bookmaker", "market"])["coherent"].agg(["size", "mean"]).reset_index())
    coh["incoherent"] = ((1 - coh["mean"]) * coh["size"]).round().astype(int)
    coh["incoherent%"] = 100 * (1 - coh["mean"])
    coh = coh.drop(columns="mean").rename(columns={"size": "quotes"})
    t.append("\nCoherent-quote check (two-way implied sum within 1.00-1.15), by book and market:\n")
    t.append(md_table(coh, "{:.2f}"))
    ovr = o[o["coherent"]].groupby(["bookmaker", "market"])["overround"].median().unstack()
    t.append("\nMedian overround of coherent quotes:\n")
    t.append(md_table(ovr.reset_index(), "{:.4f}"))
    # Pinnacle coverage by season and market, and by fetch hour
    pin = o[(o["bookmaker"] == SHARP) & o["coherent"]]
    pc = []
    for s in ALL_SEASONS:
        row = {"season": s}
        for m in MARKETS:
            gm = o[(o["season"] == s) & (o["market"] == m)]
            pm = pin[(pin["season"] == s) & (pin["market"] == m)]
            row[f"{MARKET_NAME[m]} games w/ pin"] = (100 * pm["game_id"].nunique()
                                                     / max(1, gm["game_id"].nunique()))
            gfe = gm.groupby(["game_id", "fid"]).ngroups
            pfe = pm.groupby(["game_id", "fid"]).ngroups
            row[f"{MARKET_NAME[m]} game-fetches w/ pin"] = 100 * pfe / max(1, gfe)
        pc.append(row)
    t.append("\nPinnacle coherent quote coverage, percent (games with any Pinnacle quote; "
             "game-fetches holding one):\n")
    t.append(md_table(pd.DataFrame(pc), "{:.1f}"))
    # by requested hour and timing bucket
    gf = (o.groupby(["game_id", "fid", "market"])
          .agg(has_pin=("bookmaker", lambda s: SHARP in set(s)))
          .reset_index().merge(ft[["game_id", "fid", "req_ts", "bucket", "hbucket"]],
                               on=["game_id", "fid"]))
    gf["req_hour"] = gf["req_ts"].dt.hour
    hh = gf.groupby(["req_hour", "market"])["has_pin"].agg(["size", "mean"]).reset_index()
    hh["pin%"] = 100 * hh["mean"]
    hh = hh.pivot(index="req_hour", columns="market", values=["size", "pin%"])
    hh.columns = [f"{a}_{MARKET_NAME[b]}" for a, b in hh.columns]
    t.append("\nGame-fetches by requested UTC hour, and the share holding a Pinnacle quote "
             "(any quote; coherence aside):\n")
    t.append(md_table(hh.reset_index(), "{:.1f}"))
    bb = gf.groupby(["bucket", "market"])["has_pin"].agg(["size", "mean"]).reset_index()
    bb["pin%"] = 100 * bb["mean"]
    t.append("\nBy timing bucket:\n")
    t.append(md_table(bb.drop(columns="mean"), "{:.1f}"))
    # open vs close
    oc = ft.groupby("game_id").agg(open_h=("hours_to_tip", "max"), close_h=("hours_to_tip", "min"),
                                   n=("fid", "size"), season=("season", "first"))
    q = oc.groupby("season")[["open_h", "close_h"]].describe(percentiles=[0.1, 0.5, 0.9])
    q = q.loc[:, [(c, s) for c in ["open_h", "close_h"] for s in ["10%", "50%", "90%", "min", "max"]]]
    q.columns = [f"{a} {b}" for a, b in q.columns]
    t.append("\nOpen (earliest pre-game fetch) and close (last pre-tip fetch), hours before tip, "
             "per game:\n")
    t.append(md_table(q.reset_index(), "{:.2f}"))
    t.append("\nThe ingestor writes a game into a fetch only when DraftKings lists it "
             "(data/ingestors/odds_ingestor._process_events), so 'the opener' here is "
             "DraftKings' first listing inside the stored schedule (the D-1 22Z snapshot "
             "at the earliest, about 25-29 hours before a 23-03Z tip; a game listed "
             "earlier by the D-1 15Z/19Z snapshot of the previous slate can reach ~36h). "
             "Lead-time analysis has that ceiling.\n")
    t.append("\n" + validate_scores(g))
    report("checks", "\n".join(t))


# ── quotes: Pinnacle against the bettable books, same fetch ─────────────────

def sharp_pairs(o: pd.DataFrame, ref: str = SHARP, books=None, same_number=True,
                sigma=None) -> pd.DataFrame:
    """Every (game, market, fetch, bettable book) priced against `ref` in the SAME fetch.

    Returns two rows per pair (side A and side B) with the reference no-vig
    probability (proportional and power) and EV at that book's price. With
    same_number=False the soft number may differ (the line-gap rule); fair at the
    soft number then comes from the normal model (sigma by season)."""
    books = books or [b for b in BETTABLE if b != ref]
    sh = o[(o["bookmaker"] == ref) & o["coherent"]]
    so = o[o["bookmaker"].isin(books) & o["coherent"]]
    k = ["game_id", "market", "fid"]
    shc = sh[k + ["line", "imp_a", "imp_b", "snap", "home_price", "away_price",
                  "over_price", "under_price"]].rename(
        columns={"line": "ref_line", "imp_a": "ref_ia", "imp_b": "ref_ib", "snap": "ref_snap",
                 "home_price": "ref_hp", "away_price": "ref_ap", "over_price": "ref_op",
                 "under_price": "ref_up"})
    keep = k + ["bookmaker", "line", "snap", "fetch_ts", "req_ts", "hours_to_tip", "season",
                "game_date", "tip", "home_score", "away_score", "home_price", "away_price",
                "over_price", "under_price"]
    p = so[keep].merge(shc, on=k, how="inner")
    if same_number:
        p = p[(p["market"] == "h2h") | (p["line"] == p["ref_line"])]
    else:
        p = p[(p["market"] != "h2h") & (p["line"] != p["ref_line"])]
    p = p.reset_index(drop=True)
    pa_prop = p["ref_ia"] / (p["ref_ia"] + p["ref_ib"])
    qa, _ = power_devig(p["ref_ia"].to_numpy(), p["ref_ib"].to_numpy())
    p["fa_prop"], p["fa_pow"] = pa_prop.to_numpy(), qa
    is_t = (p["market"] == "totals").to_numpy()
    pr_a = np.where(is_t, p["over_price"], p["home_price"]).astype(float)
    pr_b = np.where(is_t, p["under_price"], p["away_price"]).astype(float)
    A = p.copy()
    A["side"] = [SIDE_A[m] for m in A["market"]]
    A["price"] = pr_a
    A["fair_prop"], A["fair_pow"] = p["fa_prop"], p["fa_pow"]
    B = p.copy()
    B["side"] = [SIDE_B[m] for m in B["market"]]
    B["price"] = pr_b
    B["fair_prop"], B["fair_pow"] = 1 - p["fa_prop"], 1 - p["fa_pow"]
    x = pd.concat([A, B], ignore_index=True)
    d = dec(x["price"])
    x["ev_prop"] = x["fair_prop"] * d - 1
    x["ev_pow"] = x["fair_pow"] * d - 1
    # favourite / dog by the reference book in that fetch
    if True:
        ml = (x["market"] == "h2h").to_numpy()
        sp = (x["market"] == "spreads").to_numpy()
        fav_ml = np.where(x["side"] == "home", x["fa_prop"] > 0.5, x["fa_prop"] < 0.5)
        tie_ml = np.isclose(x["fa_prop"], 0.5)
        fav_sp = np.where(x["side"] == "home", x["ref_line"] < 0, x["ref_line"] > 0)
        tie_sp = x["ref_line"].to_numpy() == 0
        x["fav"] = np.where(ml, np.where(tie_ml, "pk", np.where(fav_ml, "fav", "dog")),
                            np.where(sp, np.where(tie_sp, "pk", np.where(fav_sp, "fav", "dog")),
                                     ""))
    x["soft_lag_min"] = (x["ref_snap"] - x["snap"]).dt.total_seconds() / 60.0
    return x


def family_mask(x: pd.DataFrame, fam: str) -> np.ndarray:
    if fam == "all":
        return np.ones(len(x), bool)
    if fam in ("fav", "dog"):
        return (x["fav"] == fam).to_numpy()
    return (x["side"] == fam).to_numpy()


def first_qualifying(c: pd.DataFrame, floor: float, evcol: str) -> pd.DataFrame:
    """The live decision: per game, the first fetch with a qualifying quote, best EV there."""
    q = c[(c[evcol] >= floor) & (c["price"] >= PRICE_FLOOR)]
    if len(q) == 0:
        return q
    q = q.assign(_rank=q["bookmaker"].map(BOOK_RANK))
    q = q.sort_values(["game_id", "fetch_ts", evcol, "_rank", "side"],
                      ascending=[True, True, False, True, True])
    return q.drop_duplicates(["game_id"], keep="first").drop(columns="_rank")


def grade(b: pd.DataFrame) -> pd.DataFrame:
    if len(b) == 0:
        return b.assign(result=[], units=[], risk=[])
    b = b.copy()
    b["result"] = settle(b["market"].to_numpy(), b["side"].to_numpy(), b["line"].to_numpy(),
                         b["home_score"].to_numpy(), b["af_score"].to_numpy()
                         if "af_score" in b else b["away_score"].to_numpy())
    u, r = units_for(b["result"].to_numpy(), b["price"].to_numpy())
    b["units"], b["risk"] = u, r
    return b


# ── the margin / total distribution (line-gap fair prices and CLV at a moved number) ──
#
# X is the home margin (spreads) or the game total (totals), an integer. It is
# modelled as N(mu, sigma) discretised to integers: P(X = k) is the normal mass on
# [k - 0.5, k + 0.5]. Side A (home / over) wins when X > t, where t = -spread_home
# for spreads and t = total_line for totals; X == t pushes. sigma is the SD of
# (result - Pinnacle's closing number) on the seasons BEFORE the graded one; mu is
# solved so the model reproduces Pinnacle's no-vig price at Pinnacle's number
# (price skew included, not just the number).

def probs_at(mu, sigma, t):
    """(P side A wins, P push, P side A loses) for threshold t."""
    mu, sigma, t = (np.asarray(v, float) for v in (mu, sigma, t))
    whole = np.isclose(t, np.round(t))
    # side A wins when X >= floor(t) + 1  (t whole) or X >= t + 0.5 (t half)
    up = np.where(whole, t + 0.5, t)
    lo = np.where(whole, t - 0.5, t)
    p_lose = norm_cdf((lo - mu) / sigma)
    p_win = 1.0 - norm_cdf((up - mu) / sigma)
    p_push = np.clip(1.0 - p_win - p_lose, 0.0, 1.0)
    return p_win, p_push, p_lose


def solve_mu(t, p_cond, sigma, iters=60):
    """mu such that P(win)/(P(win)+P(lose)) at t equals p_cond (side A)."""
    t, p_cond, sigma = (np.asarray(v, float) for v in (t, p_cond, sigma))
    lo = t - 6 * sigma
    hi = t + 6 * sigma
    for _ in range(iters):
        mid = 0.5 * (lo + hi)
        w, _, l = probs_at(mid, sigma, t)
        c = w / np.maximum(w + l, 1e-12)
        lo = np.where(c < p_cond, mid, lo)
        hi = np.where(c >= p_cond, mid, hi)
    return 0.5 * (lo + hi)


def threshold(market, side_a_line):
    """t for side A from the stored number (spread_home or total)."""
    return np.where(np.asarray(market) == "spreads", -np.asarray(side_a_line, float),
                    np.asarray(side_a_line, float))


def pin_close(o: pd.DataFrame) -> pd.DataFrame:
    """Pinnacle's last pre-tip coherent quote per (game, market): its no-vig close."""
    p = o[(o["bookmaker"] == SHARP) & o["coherent"]].sort_values("fetch_ts")
    p = p.drop_duplicates(["game_id", "market"], keep="last")
    c = p[["game_id", "market", "line", "imp_a", "imp_b", "fetch_ts", "hours_to_tip",
           "season", "home_score", "away_score"]].copy()
    c["close_fa_prop"] = c["imp_a"] / (c["imp_a"] + c["imp_b"])
    c["close_fa_pow"] = power_devig(c["imp_a"].to_numpy(), c["imp_b"].to_numpy())[0]
    return c.rename(columns={"line": "close_line", "fetch_ts": "close_ts",
                             "hours_to_tip": "close_h"}).drop(columns=["imp_a", "imp_b"])


def fit_sigma(close: pd.DataFrame) -> tuple[dict, pd.DataFrame]:
    """SD of (result - Pinnacle closing number), fit on the seasons before each season."""
    c = close[close["market"].isin(["spreads", "totals"])].copy()
    margin = c["home_score"] - c["away_score"]
    total = c["home_score"] + c["away_score"]
    c["resid"] = np.where(c["market"] == "spreads", margin + c["close_line"],
                          total - c["close_line"])
    rows, sig = [], {}
    for s in ALL_SEASONS:
        sig[s] = {}
        for m in ("spreads", "totals"):
            prior = c[(c["market"] == m) & (c["season"] < s)]
            src = "prior seasons"
            if len(prior) < 300:
                prior = c[(c["market"] == m) & (c["season"] == s)]
                src = "own season (no prior season priced)"
            sd = float(prior["resid"].std())
            mean = float(prior["resid"].mean())
            sig[s][m] = sd
            rows.append({"season": s, "market": MARKET_NAME[m], "sd": sd, "mean_resid": mean,
                         "n": len(prior), "fit_on": src})
    return sig, pd.DataFrame(rows)


def sigma_for(season, market, sig):
    return np.array([sig.get(int(s), {}).get(m, np.nan) for s, m in zip(season, market)], float)


def attach_close(b: pd.DataFrame, close: pd.DataFrame, sig: dict, devig: str = "prop") -> pd.DataFrame:
    """close_fair_prob and clv_ev: the bet's price against Pinnacle's no-vig close.

    Same number: Pinnacle's no-vig probability of the side. Moved number: the
    normal model, mu solved from Pinnacle's close, evaluated at the bet's number
    (conditional on no push). clv_ev = P(win) x (decimal - 1) - P(lose)."""
    if len(b) == 0:
        return b.assign(close_fair_prob=[], clv_ev=[], close_same_number=[])
    col = "close_fa_prop" if devig == "prop" else "close_fa_pow"
    c = close[["game_id", "market", "season", "close_line", col, "close_ts"]].rename(
        columns={col: "cfa"}).copy()
    st_c = c["market"].isin(["spreads", "totals"]).to_numpy()
    c["sg"] = np.nan
    c["mu"] = np.nan
    if st_c.any():
        cs = c[st_c]
        sg = sigma_for(cs["season"], cs["market"], sig)
        c.loc[st_c, "sg"] = sg
        c.loc[st_c, "mu"] = solve_mu(threshold(cs["market"], cs["close_line"]),
                                     cs["cfa"].to_numpy(float), sg)
    c = c.drop(columns="season")
    x = b.drop(columns=[k for k in ("close_line", "cfa", "close_ts", "sg", "mu", "clv_later",
                                    "close_fair_prob", "clv_ev", "close_same_number") if k in b])
    x = x.merge(c, on=["game_id", "market"], how="left")
    is_a = x["side"].isin(["home", "over"]).to_numpy()
    d = dec(x["price"])
    ml = (x["market"] == "h2h").to_numpy()
    pa = x["cfa"].to_numpy(float)
    direct = np.where(is_a, pa, 1 - pa)
    w, pu, l = probs_at(x["mu"].to_numpy(float), x["sg"].to_numpy(float),
                        threshold(x["market"], x["line"]))
    pw = np.where(is_a, w, l)
    pl = np.where(is_a, l, w)
    cond = pw / np.maximum(pw + pl, 1e-12)
    eq = ml | np.isclose(x["close_line"].to_numpy(float), x["line"].to_numpy(float))
    # at the same number keep the two-way convention (push share ignored, as the EV is)
    x["close_fair_prob"] = np.where(eq, direct, cond)
    clv = np.where(eq, direct * d - 1, pw * (d - 1) - pl)
    # CLV needs a LATER price: a bet decided in Pinnacle's own closing fetch has none (its
    # "CLV" would be its own EV, positive by construction), so it gets NaN and is left out
    # of every CLV median.
    if "fetch_ts" in x:
        later = (x["close_ts"] > x["fetch_ts"]).to_numpy()
    else:
        later = np.ones(len(x), bool)
    x["clv_later"] = later
    x["clv_ev"] = np.where(later, clv, np.nan)
    x["close_same_number"] = eq
    return x


# ── the sharp-vs-soft rule ──────────────────────────────────────────────────

def decision_order(x: pd.DataFrame, evcol: str) -> np.ndarray:
    """Row order of the live decision: game, fetch time, best EV, book order, side."""
    return np.lexsort((x["_side"].to_numpy(), x["_rank"].to_numpy(), -x[evcol].to_numpy(),
                       ts_int(x["fetch_ts"]), x["_gk"].to_numpy()))


def ts_int(s: pd.Series) -> np.ndarray:
    """A tz-aware timestamp column as int64 (object iteration is what made sorts slow)."""
    return s.dt.tz_convert(None).to_numpy().astype("datetime64[us]").astype(np.int64)


def prepare_candidates(x: pd.DataFrame, evcol: str, close=None, sig=None,
                       devig: str = "prop") -> pd.DataFrame:
    """Graded, Pinnacle's close attached, sorted in decision order."""
    x = x[(x["hours_to_tip"] <= MAX_LEAD_H)].copy()
    x["result"] = settle(x["market"].to_numpy(), x["side"].to_numpy(), x["line"].to_numpy(),
                         x["home_score"].to_numpy(), x["away_score"].to_numpy())
    u, r = units_for(x["result"].to_numpy(), x["price"].to_numpy())
    x["units"], x["risk"] = u, r
    x["_rank"] = x["bookmaker"].map(BOOK_RANK).fillna(99).astype(int)
    x["_side"] = x["side"].map({"home": 0, "over": 0, "away": 1, "under": 1}).astype(int)
    x["_gk"] = pd.factorize(x["game_id"])[0]
    if close is not None:
        x = attach_close(x, close, sig, devig)
    x = x.iloc[decision_order(x, evcol)]
    return x.reset_index(drop=True)


def select(x: pd.DataFrame, mask: np.ndarray) -> pd.DataFrame:
    """First qualifying row per game (x is pre-sorted in decision order)."""
    y = x[mask]
    return y[~y["_gk"].duplicated()]


def rule_mask(x, fam, floor, evcol, price_floor=True):
    m = family_mask(x, fam) & (x[evcol].to_numpy() >= floor)
    if price_floor:
        m &= x["price"].to_numpy() >= PRICE_FLOOR
    return m


def bet_frame(b: pd.DataFrame, evcol: str, fair: str, cell: str) -> pd.DataFrame:
    out = pd.DataFrame({
        "cell": cell, "game_id": b["game_id"].to_numpy(), "game_date": b["game_date"].to_numpy(),
        "season": b["season"].to_numpy(), "market": b["market"].to_numpy(),
        "side": b["side"].to_numpy(), "fav": b["fav"].to_numpy() if "fav" in b else "",
        "line": b["line"].to_numpy(), "book": b["bookmaker"].to_numpy(),
        "price": b["price"].to_numpy(), "fair_prob": b[fair].to_numpy(),
        "ev": b[evcol].to_numpy(), "decision_fetch": b["fetch_ts"].astype(str).to_numpy(),
        "hours_to_tip": b["hours_to_tip"].to_numpy(),
        "result": b["result"].to_numpy(), "units": b["units"].to_numpy(),
        "risk": b["risk"].to_numpy(),
    })
    for c in ("close_fair_prob", "clv_ev", "clv_later", "close_same_number", "soft_lag_min", "bucket",
              "ref_line", "gap"):
        if c in b:
            out[c] = b[c].to_numpy()
    return out


def cell_row(b: pd.DataFrame, seasons=GRADED) -> dict:
    gb = b[b["season"].isin(seasons)]
    row = summ(gb)
    for s in seasons:
        x = gb[gb["season"] == s]
        row[f"{s}"] = 100 * x["units"].sum() / x["risk"].sum() if len(x) else np.nan
        row[f"n{s}"] = len(x)
    if "clv_ev" in gb and len(gb):
        row["clv_med%"] = 100 * float(np.nanmedian(gb["clv_ev"]))
        cv = gb["clv_ev"].dropna()
        row["beat_close%"] = 100 * float((cv > 0).mean()) if len(cv) else np.nan
        row["clv_n"] = len(cv)
    return row


def bars(b_all: pd.DataFrame, neighbours: list[pd.DataFrame], blind_same: dict | None,
         placebo_rois: list[float] | None) -> tuple[dict, list[str]]:
    """The pre-registered bars 4-11 on the graded seasons."""
    b = b_all[b_all["season"].isin(GRADED)]
    s = summ(b, ci=True)
    failed = []
    per = by_season(b, GRADED)
    neg = per[(per["bets"] >= 30) & (per["roi"] <= 0)]
    if len(neg):
        failed.append("5 every season positive (" + ", ".join(
            f"{int(r.season)} {r.roi:+.1f}%" for r in neg.itertuples()) + ")")
    conf = per[per["season"] == CONFIRM]
    if not len(conf) or conf["bets"].iloc[0] < 30 or conf["roi"].iloc[0] <= 0:
        failed.append("4 confirm on 2025-26")
    if s["bets"] < 200 or not (s.get("ci_lo", -1) > 0):
        failed.append(f"6 >=200 bets and CI>0 (n={s['bets']}, CI {s.get('ci_lo', np.nan):+.1f}"
                      f"..{s.get('ci_hi', np.nan):+.1f})")
    nb = [summ(n[n["season"].isin(GRADED)])["roi"] for n in neighbours if n is not None]
    if any((not np.isfinite(r)) or r <= 0 for r in nb):
        failed.append("7 plateau (" + ", ".join(f"{r:+.1f}%" for r in nb) + ")")
    h1, h2 = halves(b)
    if not (h1["roi"] > 0 and h2["roi"] > 0):
        failed.append(f"8 halves ({h1['roi']:+.1f}% / {h2['roi']:+.1f}%)")
    share = b["side"].value_counts(normalize=True)
    top = share.index[0] if len(share) else None
    if len(share) and share.iloc[0] > 0.70 and blind_same is not None:
        bs = blind_same.get(top)
        if bs is None or not (s["roi"] > bs):
            failed.append(f"9 beats blind {top} ({s['roi']:+.1f}% vs {bs if bs is None else round(bs, 1)}%)")
    if placebo_rois:
        if not (s["roi"] > np.percentile(placebo_rois, 95)):
            failed.append(f"10 placebo (real {s['roi']:+.1f}% vs shuffled p95 "
                          f"{np.percentile(placebo_rois, 95):+.1f}%)")
    cv = b["clv_ev"].dropna() if "clv_ev" in b else pd.Series(dtype=float)
    if len(cv):
        med = float(cv.median())
        if not med > 0:
            failed.append(f"11 median CLV ({100 * med:+.2f}% on {len(cv)} bets with a later price)")
    else:
        failed.append("11 median CLV (no bet has a later Pinnacle price)")
    info = {**s, "h1": h1["roi"], "h2": h2["roi"],
            "top_side": top, "top_share": float(share.iloc[0]) if len(share) else np.nan,
            "neighbours": nb}
    return info, failed


def shuffle_reference(x: pd.DataFrame, rng, evcol: str) -> pd.DataFrame:
    """Placebo: each game-fetch's reference probability swapped with another game's
    in the same date, requested hour and market; prices and outcomes untouched."""
    fcol = "fair_prop" if evcol == "ev_prop" else "fair_pow"
    acol = "fa_prop" if evcol == "ev_prop" else "fa_pow"
    gf = x.groupby(["_gk", "fid"], sort=False).ngroup().to_numpy()
    first = ~pd.Series(gf).duplicated().to_numpy()
    keys = x.loc[first, ["game_date", "req_ts", "market", acol]].reset_index(drop=True)
    kid = gf[first]
    grp = keys.groupby(["game_date", "req_ts", "market"], sort=False).ngroup().to_numpy()
    vals = keys[acol].to_numpy()
    o0 = np.argsort(grp, kind="stable")
    o1 = np.lexsort((rng.random(len(grp)), grp))
    sh = np.empty_like(vals)
    sh[o0] = vals[o1]
    lut = np.empty(gf.max() + 1)
    lut[kid] = sh
    y = x.copy()
    a = lut[gf]
    is_a = (y["_side"] == 0).to_numpy()
    y[fcol] = np.where(is_a, a, 1 - a)
    y[evcol] = y[fcol] * dec(y["price"]) - 1
    y = y.iloc[decision_order(y, evcol)]
    return y.reset_index(drop=True)


def blind_first_fetch(x: pd.DataFrame, evcol: str) -> dict:
    """Blind same-side return: every game, at the first fetch where the reference quotes
    it, best bettable price at the reference number (the rule with no EV floor)."""
    out = {}
    for side in ("home", "away", "over", "under", "fav", "dog"):
        m = family_mask(x, side) & (x["price"].to_numpy() >= PRICE_FLOOR)
        if not m.any():
            continue
        # best price on that side at the first fetch: re-sort by price within fetch
        y = x[m]
        y = y.iloc[np.lexsort((-y["price"].to_numpy(), ts_int(y["fetch_ts"]),
                               y["_gk"].to_numpy()))]
        y = y[~y["_gk"].duplicated()]
        y = y[y["season"].isin(GRADED)]
        if len(y):
            out[side] = 100 * y["units"].sum() / y["risk"].sum()
    return out


def run_rule_grid(name: str, x_raw: pd.DataFrame, close, sig, ft, devigs=("prop", "pow"),
                  placebo_reps: int = 0, full=True):
    """The EV-floor grid for every market and side family; returns (grid, chosen, bets)."""
    grids, chosen, bet_parts = [], [], []
    for dv in devigs:
        evcol, fair = ("ev_prop", "fair_prop") if dv == "prop" else ("ev_pow", "fair_pow")
        x = x_raw.merge(ft[["game_id", "fid", "bucket"]], on=["game_id", "fid"], how="left")
        x = prepare_candidates(x, evcol, close, sig, dv)
        for m in MARKETS:
            xm = x[x["market"] == m].reset_index(drop=True)
            if not len(xm):
                continue
            blind = blind_first_fetch(xm, evcol)
            for fam in FAMILIES[m]:
                log(f"  {name} {dv} {m} {fam}: {len(xm):,} candidate rows")
                cells = {}
                for fl in EV_FLOORS:
                    b = select(xm, rule_mask(xm, fam, fl, evcol))
                    cells[fl] = b
                    row = {"variant": name, "devig": dv, "market": MARKET_NAME[m], "family": fam,
                           "floor": fl, **cell_row(b)}
                    ch = b[b["season"].isin(CHOOSE)]
                    row["units_choose"] = ch["units"].sum()
                    grids.append(row)
                    if full:
                        bet_parts.append(bet_frame(b, evcol, fair, f"{name}|{dv}|{m}|{fam}|{fl}"))
                # choose the floor on 2021-22..2024-25 by units (ties: lower floor)
                uc = {fl: cells[fl][cells[fl]["season"].isin(CHOOSE)]["units"].sum()
                      for fl in EV_FLOORS}
                best = max(EV_FLOORS, key=lambda f: (round(uc[f], 6), -f))
                i = EV_FLOORS.index(best)
                nbrs = [cells[EV_FLOORS[j]] for j in (i - 1, i + 1) if 0 <= j < len(EV_FLOORS)]
                pl = None
                if placebo_reps:
                    rng = np.random.default_rng(SEED)
                    pl = []
                    for _ in range(placebo_reps):
                        y = shuffle_reference(xm, rng, evcol)
                        pb = select(y, rule_mask(y, fam, best, evcol))
                        pb = pb[pb["season"].isin(GRADED)]
                        pl.append(100 * pb["units"].sum() / pb["risk"].sum() if len(pb) else 0.0)
                info, failed = bars(cells[best], nbrs, blind, pl)
                nof = select(xm, rule_mask(xm, fam, best, evcol, price_floor=False))
                nof = nof[nof["season"].isin(GRADED)]
                chosen.append({"variant": name, "devig": dv, "market": MARKET_NAME[m],
                               "family": fam, "floor": best,
                               "removed_by_-200": int((nof["price"] < PRICE_FLOOR).sum()), **{k: v for k, v in info.items()
                                                                if k != "neighbours"},
                               "neighbours": ", ".join(f"{r:+.1f}" for r in info["neighbours"]),
                               "placebo_mean": float(np.mean(pl)) if pl else np.nan,
                               "placebo_p95": float(np.percentile(pl, 95)) if pl else np.nan,
                               "blind_same": blind.get(info["top_side"]),
                               "failed": "; ".join(failed) if failed else "",
                               "passes": not failed})
    return pd.DataFrame(grids), pd.DataFrame(chosen), (pd.concat(bet_parts, ignore_index=True)
                                                       if bet_parts else pd.DataFrame())


def section_sharp(o, g, ft, close, sig, placebo_reps=20):
    log("sharp: candidates")
    x = sharp_pairs(o)
    n_all = len(x)
    lead_out = int((x["hours_to_tip"] > MAX_LEAD_H).sum())
    grid, chosen, bets = run_rule_grid("pinnacle_vs_bettable", x, close, sig, ft,
                                       placebo_reps=placebo_reps)
    log("sharp: DraftKings only")
    xdk = sharp_pairs(o, books=[REF_BOOK])
    grid_dk, chosen_dk, bets_dk = run_rule_grid("pinnacle_vs_draftkings", xdk, close, sig, ft,
                                                devigs=("prop",))
    log("sharp: DraftKings-as-reference placebo")
    xref = sharp_pairs(o, ref=REF_BOOK, books=[b for b in BETTABLE if b != REF_BOOK])
    grid_ref, chosen_ref, bets_ref = run_rule_grid("draftkings_ref_placebo", xref, close, sig, ft,
                                                   devigs=("prop",))
    allgrid = pd.concat([grid, grid_dk, grid_ref], ignore_index=True)
    allchosen = pd.concat([chosen, chosen_dk, chosen_ref], ignore_index=True)
    allbets = pd.concat([bets, bets_dk, bets_ref], ignore_index=True)
    allgrid.to_csv(SCRATCH / "sharp_grid.csv", index=False)
    allchosen.to_csv(SCRATCH / "sharp_chosen.csv", index=False)
    allbets.to_parquet(OUT / "game_market_sharp_bets.parquet", index=False)
    (SCRATCH / "sharp_info.json").write_text(json.dumps({"candidates": n_all, "beyond_lead": lead_out}),
                                             encoding="utf-8")
    return x, allgrid, allchosen, allbets, {"candidates": n_all, "beyond_lead": lead_out}


# ── blind baselines ─────────────────────────────────────────────────────────

def quote_points(o: pd.DataFrame, which: str) -> pd.DataFrame:
    """Per (game, market): DraftKings' quote at the chosen fetch, plus the best bettable
    price per side at DraftKings' number in that same fetch.

    which: 'open'  = earliest pre-game fetch (within the live horizon) holding DK
           'close' = last pre-tip fetch holding DK
           'morning' = the game-day 15Z fetch."""
    q = o[o["coherent"] & (o["hours_to_tip"] <= MAX_LEAD_H)]
    dk = q[q["bookmaker"] == REF_BOOK].sort_values("fetch_ts")
    if which == "morning":
        gd = pd.to_datetime(dk["game_date"]).dt.tz_localize("UTC") + pd.Timedelta(hours=15)
        dk = dk[dk["req_ts"] == gd]
        pick = dk.drop_duplicates(["game_id", "market"], keep="last")
    else:
        pick = dk.drop_duplicates(["game_id", "market"], keep="first" if which == "open" else "last")
    a, b = _sides(pick)
    pick = pick.assign(dk_a=a, dk_b=b)
    bt = q[q["bookmaker"].isin(BETTABLE)].merge(
        pick[["game_id", "market", "fid", "line"]].rename(columns={"line": "dk_line"}),
        on=["game_id", "market", "fid"])
    bt = bt[(bt["market"] == "h2h") | (bt["line"] == bt["dk_line"])]
    ba, bb = _sides(bt)
    bt = bt.assign(pa=ba, pb=bb)
    ia = bt.groupby(["game_id", "market", "fid"])["pa"].idxmax()
    ib = bt.groupby(["game_id", "market", "fid"])["pb"].idxmax()
    best_a = bt.loc[ia, ["game_id", "market", "fid", "pa", "bookmaker"]].rename(
        columns={"pa": "best_a", "bookmaker": "book_a"})
    best_b = bt.loc[ib, ["game_id", "market", "fid", "pb", "bookmaker"]].rename(
        columns={"pb": "best_b", "bookmaker": "book_b"})
    out = pick.merge(best_a, on=["game_id", "market", "fid"], how="left").merge(
        best_b, on=["game_id", "market", "fid"], how="left")
    return out


def blind_bets(qp: pd.DataFrame, timing: str) -> pd.DataFrame:
    """Every game, every side, at DK and at the best bettable price; no EV, no price floor."""
    parts = []
    for m in MARKETS:
        x = qp[qp["market"] == m]
        if not len(x):
            continue
        ia, ib = imp(x["dk_a"]), imp(x["dk_b"])
        if m == "h2h":
            a_fav = np.where(np.isclose(ia, ib), "pk", np.where(ia > ib, "fav", "dog"))
        elif m == "spreads":
            a_fav = np.where(x["line"] == 0, "pk", np.where(x["line"] < 0, "fav", "dog"))
        else:
            a_fav = np.full(len(x), "")
        b_fav = np.where(a_fav == "fav", "dog", np.where(a_fav == "dog", "fav", a_fav))
        for side, pdk, pbest, bk, fv in ((SIDE_A[m], x["dk_a"], x["best_a"], x["book_a"], a_fav),
                                         (SIDE_B[m], x["dk_b"], x["best_b"], x["book_b"], b_fav)):
            for src, price, book in (("draftkings", pdk, pd.Series(REF_BOOK, index=x.index)),
                                     ("best", pbest, bk)):
                y = pd.DataFrame({
                    "game_id": x["game_id"].to_numpy(), "game_date": x["game_date"].to_numpy(),
                    "season": x["season"].to_numpy(), "market": m, "side": side, "fav": fv,
                    "line": x["line"].to_numpy(), "book": book.to_numpy(),
                    "price": np.asarray(price, float), "decision_fetch": x["fetch_ts"].astype(str).to_numpy(),
                    "fetch_ts": x["fetch_ts"].to_numpy(),
                    "hours_to_tip": x["hours_to_tip"].to_numpy(),
                    "home_score": x["home_score"].to_numpy(), "away_score": x["away_score"].to_numpy(),
                    "timing": timing, "price_source": src})
                parts.append(y)
    b = pd.concat(parts, ignore_index=True)
    b = b[np.isfinite(b["price"])]
    b["result"] = settle(b["market"].to_numpy(), b["side"].to_numpy(), b["line"].to_numpy(),
                         b["home_score"].to_numpy(), b["away_score"].to_numpy())
    u, r = units_for(b["result"].to_numpy(), b["price"].to_numpy())
    b["units"], b["risk"] = u, r
    return b


def section_baselines(o, close, sig):
    log("baselines")
    lists = []
    for timing in ("open", "close"):
        qp = quote_points(o, timing)
        lists.append(blind_bets(qp, timing))
    b = pd.concat(lists, ignore_index=True)
    b = attach_close(b, close, sig, "prop")
    keep = ["game_id", "game_date", "season", "market", "side", "fav", "line", "book", "price",
            "decision_fetch", "hours_to_tip", "timing", "price_source", "result", "units", "risk",
            "close_fair_prob", "clv_ev"]
    b[keep].assign(fair_prob=np.nan, ev=np.nan).to_parquet(OUT / "game_market_blind_bets.parquet",
                                                          index=False)
    rows = []
    for (m, timing, src), x in b.groupby(["market", "timing", "price_source"]):
        for side in FAMILIES[m][1:]:
            y = x[family_mask(x, side)]
            row = {"market": MARKET_NAME[m], "side": side, "timing": timing, "price": src}
            for s in ALL_SEASONS:
                z = y[y["season"] == s]
                row[str(s)] = 100 * z["units"].sum() / z["risk"].sum() if len(z) else np.nan
            gy = y[y["season"].isin(GRADED)]
            row["graded n"] = len(gy)
            row["graded units"] = gy["units"].sum()
            row["graded ROI"] = 100 * gy["units"].sum() / gy["risk"].sum() if len(gy) else np.nan
            row["clv_med%"] = 100 * float(np.nanmedian(gy["clv_ev"])) if len(gy) else np.nan
            rows.append(row)
    tab = pd.DataFrame(rows)
    tab["_m"] = tab["market"].map({"moneyline": 0, "spread": 1, "total": 2})
    tab = tab.sort_values(["_m", "side", "timing", "price"]).drop(columns="_m")
    tab.to_csv(SCRATCH / "baselines.csv", index=False)
    pushes = b[(b["market"] != "h2h")].groupby("market")["result"].apply(lambda r: 100 * (r == "P").mean())
    t = ["## 2. Blind baselines\n",
         "Every game, every side, no EV cut and no price floor. 'open' = DraftKings' earliest "
         "pre-game fetch inside the 7-day live horizon; 'close' = its last pre-tip fetch. "
         "'best' = the best bettable price at DraftKings' number in that same fetch. ROI by "
         "season in percent (units won / units risked); 'clv_med%' = median EV of the bet "
         "at Pinnacle's no-vig close. Bet list: `game_market_blind_bets.parquet`.\n",
         md_table(tab, "{:.2f}"),
         "\nPush rate on spreads/totals (all blind rows): "
         + ", ".join(f"{MARKET_NAME[k]} {v:.2f}%" for k, v in pushes.items()) + ".\n"]
    report("baselines", "\n".join(t))
    return b, tab


# ── line-gap rule ───────────────────────────────────────────────────────────

GAPS = [0.5, 1.0, 1.5, 2.0]
GAP_HEAD = (
    "## 4. Line-gap rule\n\n"
    "A bettable book whose spread/total NUMBER differs from Pinnacle's in the same fetch; the "
    "side the gap favours is bet at that book (spread: the side getting the extra points; "
    "total: the under at a higher number, the over at a lower one). Fair probability at the "
    "book's number: the margin/total X ~ N(mu, sigma) on the integers, sigma = SD of (result - "
    "Pinnacle's closing number) on the seasons before, mu solved so the model reproduces "
    "Pinnacle's proportional no-vig price at Pinnacle's own number (its price skew included). "
    "EV = P(win) x (decimal-1) - P(lose), push-aware. One bet a game per market, first "
    "qualifying fetch, best EV there, price -200 or better. Cells: gap >= {0.5, 1, 1.5, 2} x "
    "EV filter {none, >=0, >=0.02} x {spread, total} = 24, plus the same 24 with DraftKings as "
    "the reference (placebo). Bet lists: `game_market_gap_bets.parquet`.\n")
GAP_EV = [None, 0.0, 0.02]


def gap_candidates(o, sig, ref=SHARP, books=None) -> pd.DataFrame:
    x = sharp_pairs(o, ref=ref, books=books, same_number=False)
    x["gap"] = x["line"] - x["ref_line"]
    fav_side = np.where(x["market"] == "spreads", np.where(x["gap"] > 0, "home", "away"),
                        np.where(x["gap"] > 0, "under", "over"))
    x = x[x["side"].to_numpy() == fav_side].reset_index(drop=True)
    sg = sigma_for(x["season"], x["market"], sig)
    mu = solve_mu(threshold(x["market"], x["ref_line"]), x["fa_prop"].to_numpy(float), sg)
    w, pu, l = probs_at(mu, sg, threshold(x["market"], x["line"]))
    is_a = x["side"].isin(["home", "over"]).to_numpy()
    pw, pl = np.where(is_a, w, l), np.where(is_a, l, w)
    d = dec(x["price"])
    x["gap_fair"] = pw / np.maximum(pw + pl, 1e-12)
    x["gap_ev"] = pw * (d - 1) - pl
    x["p_push"] = pu
    x["abs_gap"] = x["gap"].abs()
    return x


def section_gap(o, close, sig, ft, placebo_reps=20):
    log("gap")
    res = {}
    t = ["## 4. Line-gap rule\n",
         "A bettable book whose spread/total NUMBER differs from Pinnacle's in the same fetch. "
         "The side the gap favours is bet at that book (spread: the side getting the extra "
         "points; total: under a higher number, over a lower one). Fair probability at the "
         "book's number: X ~ N(mu, sigma) on integers, sigma = SD of (result - Pinnacle's "
         "closing number) on the seasons before (table below), mu solved so the model "
         "reproduces Pinnacle's proportional no-vig price at Pinnacle's number. EV = "
         "P(win) x (decimal-1) - P(lose), push-aware. One bet a game per market, first "
         "qualifying fetch, best EV there, price -200 or better. Cells: gap >= "
         f"{GAPS} x EV filter (none, >=0, >=0.02) x market = {len(GAPS) * len(GAP_EV) * 2}.\n"]
    variants = [("pinnacle_gap", SHARP, None)]
    variants.append(("draftkings_ref_gap_placebo", REF_BOOK, [b for b in BETTABLE if b != REF_BOOK]))
    grids, chosen, parts, props = [], [], [], []
    for name, ref, books in variants:
        xg = gap_candidates(o, sig, ref=ref, books=books)
        xg = xg.merge(ft[["game_id", "fid", "bucket"]], on=["game_id", "fid"], how="left")
        xg = prepare_candidates(xg, "gap_ev", close, sig, "prop")
        for m in ("spreads", "totals"):
            xm = xg[xg["market"] == m].reset_index(drop=True)
            # every priced gap proposition, by gap size (each fetch x book; correlated)
            for gb, y in xm.groupby(np.minimum(xm["abs_gap"], 3.0)):
                yy = y[y["season"].isin(GRADED) & (y["price"] >= PRICE_FLOOR)]
                props.append({"variant": name, "market": MARKET_NAME[m],
                              "abs_gap": "3+" if gb >= 3 else gb, "propositions": len(yy),
                              "ROI": 100 * yy["units"].sum() / yy["risk"].sum() if len(yy) else np.nan,
                              "mean_model_ev%": 100 * yy["gap_ev"].mean(),
                              "clv_med%": 100 * np.nanmedian(yy["clv_ev"]) if len(yy) else np.nan})
            cells = {}
            for gmin in GAPS:
                for evf in GAP_EV:
                    mask = (xm["abs_gap"].to_numpy() >= gmin - 1e-9) & \
                           (xm["price"].to_numpy() >= PRICE_FLOOR)
                    if evf is not None:
                        mask &= xm["gap_ev"].to_numpy() >= evf
                    b = select(xm, mask)
                    cells[(gmin, evf)] = b
                    row = {"variant": name, "market": MARKET_NAME[m], "gap>=": gmin,
                           "ev_filter": "none" if evf is None else evf, **cell_row(b)}
                    row["units_choose"] = b[b["season"].isin(CHOOSE)]["units"].sum()
                    grids.append(row)
                    parts.append(bet_frame(b.assign(fair_prop=b["gap_fair"]), "gap_ev", "gap_fair",
                                           f"{name}|{m}|{gmin}|{evf}"))
            uc = {k: v[v["season"].isin(CHOOSE)]["units"].sum() for k, v in cells.items()}
            best = max(cells, key=lambda k: (round(uc[k], 6), -k[0]))
            gi, ei = GAPS.index(best[0]), GAP_EV.index(best[1])
            nb = [cells[(GAPS[j], best[1])] for j in (gi - 1, gi + 1) if 0 <= j < len(GAPS)]
            nb += [cells[(best[0], GAP_EV[j])] for j in (ei - 1, ei + 1) if 0 <= j < len(GAP_EV)]
            blind = {}
            for side in (SIDE_A[m], SIDE_B[m]):
                yb = select(xm, (xm["side"] == side).to_numpy() & (xm["price"].to_numpy() >= PRICE_FLOOR))
                yb = yb[yb["season"].isin(GRADED)]
                blind[side] = 100 * yb["units"].sum() / yb["risk"].sum() if len(yb) else None
            pl = None
            if placebo_reps and best[1] is not None and name == "pinnacle_gap":
                rng = np.random.default_rng(SEED)
                pl = []
                for _ in range(placebo_reps):
                    y = xm.copy()
                    # shuffle Pinnacle's price (not the gap) across games in the date/hour
                    y["ev_prop"] = y["gap_ev"]
                    y = shuffle_reference(y, rng, "ev_prop")
                    sg_ = sigma_for(y["season"], y["market"], sig)
                    # shuffle_reference rewrote fair_prop from the shuffled fa; rebuild mu from it
                    fa_sh = np.where(y["_side"] == 0, y["fair_prop"], 1 - y["fair_prop"])
                    mu_ = solve_mu(threshold(y["market"], y["ref_line"]), fa_sh, sg_)
                    w_, _, l_ = probs_at(mu_, sg_, threshold(y["market"], y["line"]))
                    ia_ = (y["_side"] == 0).to_numpy()
                    pw_, pl_ = np.where(ia_, w_, l_), np.where(ia_, l_, w_)
                    y["gap_ev"] = pw_ * (dec(y["price"]) - 1) - pl_
                    y = y.iloc[decision_order(y, "gap_ev")].reset_index(drop=True)
                    mk = (y["abs_gap"].to_numpy() >= best[0] - 1e-9) & \
                         (y["price"].to_numpy() >= PRICE_FLOOR) & (y["gap_ev"].to_numpy() >= best[1])
                    pb = select(y, mk)
                    pb = pb[pb["season"].isin(GRADED)]
                    pl.append(100 * pb["units"].sum() / pb["risk"].sum() if len(pb) else 0.0)
            info, failed = bars(cells[best], nb, blind, pl)
            chosen.append({"variant": name, "market": MARKET_NAME[m], "gap>=": best[0],
                           "ev_filter": "none" if best[1] is None else best[1],
                           **{k: v for k, v in info.items() if k != "neighbours"},
                           "neighbours": ", ".join(f"{r:+.1f}" for r in info["neighbours"]),
                           "placebo_p95": float(np.percentile(pl, 95)) if pl else np.nan,
                           "blind_same": blind.get(info["top_side"]),
                           "failed": "; ".join(failed), "passes": not failed})
            res[(name, m)] = cells[best]
    grid = pd.DataFrame(grids)
    ch = pd.DataFrame(chosen)
    pr = pd.DataFrame(props)
    grid.to_csv(SCRATCH / "gap_grid.csv", index=False)
    ch.to_csv(SCRATCH / "gap_chosen.csv", index=False)
    pd.concat(parts, ignore_index=True).to_parquet(OUT / "game_market_gap_bets.parquet", index=False)
    return grid, ch, pr


# ── situational totals ──────────────────────────────────────────────────────

def season_openers(g: pd.DataFrame) -> dict:
    return g.groupby("season")["game_date"].min().to_dict()


def section_situational(o, g, close, sig, placebo_reps=20):
    log("situational")
    opener = season_openers(g)
    qps = {t: quote_points(o, t) for t in ("open", "morning", "close")}
    tot = {t: blind_bets(q[q["market"] == "totals"], t) for t, q in qps.items()}
    tot = {t: attach_close(b, close, sig, "prop") for t, b in tot.items()}
    for t, b in tot.items():
        b["days_in"] = (pd.to_datetime(b["game_date"])
                        - pd.to_datetime(b["season"].map(opener))).dt.days
    out = {}
    # (a) early season, blind, by bucket and season
    rows = []
    for t in ("open", "close"):
        b = tot[t]
        for src in ("best", "draftkings"):
            for side in ("under", "over"):
                y = b[(b["price_source"] == src) & (b["side"] == side)]
                for lo, hi in ((0, 6), (7, 13), (14, 20), (21, 27), (28, 400)):
                    z = y[(y["days_in"] >= lo) & (y["days_in"] <= hi)]
                    row = {"timing": t, "price": src, "side": side,
                           "days": f"{lo}-{hi}" if hi < 400 else f"{lo}+"}
                    for s in ALL_SEASONS:
                        zz = z[z["season"] == s]
                        row[str(s)] = 100 * zz["units"].sum() / zz["risk"].sum() if len(zz) else np.nan
                        row[f"n{s}"] = len(zz)
                    gz = z[z["season"].isin(GRADED)]
                    row["graded ROI"] = 100 * gz["units"].sum() / gz["risk"].sum() if len(gz) else np.nan
                    row["graded n"] = len(gz)
                    rows.append(row)
    early_tab = pd.DataFrame(rows)
    # early-season under as a rule: first N days, at open or close, best price, -200 floor
    ecells, echosen, eparts = {}, [], []
    NS = [7, 14, 21, 28]
    erows = []
    for t in ("open", "close"):
        b = tot[t]
        y = b[(b["price_source"] == "best") & (b["side"] == "under") & (b["price"] >= PRICE_FLOOR)]
        for n in NS:
            z = y[y["days_in"] < n]
            ecells[(t, n)] = z
            erows.append({"timing": t, "first_days": n, **cell_row(z)})
            eparts.append(z.assign(cell=f"early_under|{t}|{n}"))
        # placebo: the same-length window everywhere else in the season
        for n in NS:
            pl = []
            for start in range(n, 160, 7):
                zz = y[(y["days_in"] >= start) & (y["days_in"] < start + n) & y["season"].isin(GRADED)]
                if len(zz) > 30:
                    pl.append(100 * zz["units"].sum() / zz["risk"].sum())
            blind = {"under": 100 * y[y["season"].isin(GRADED)]["units"].sum()
                     / y[y["season"].isin(GRADED)]["risk"].sum()}
            i = NS.index(n)
            nb = [ecells[(t, NS[j])] for j in (i - 1, i + 1) if 0 <= j < len(NS)
                  and (t, NS[j]) in ecells]
            info, failed = bars(ecells[(t, n)], nb, blind, pl)
            echosen.append({"rule": f"under, first {n} days", "timing": t,
                            **{k: v for k, v in info.items() if k != "neighbours"},
                            "neighbours": ", ".join(f"{r:+.1f}" for r in info["neighbours"]),
                            "placebo_p95": float(np.percentile(pl, 95)) if pl else np.nan,
                            "blind_same": blind["under"],
                            "failed": "; ".join(failed), "passes": not failed})
    early_grid = pd.DataFrame(erows)
    early_ch = pd.DataFrame(echosen)
    # (b) league scoring drift
    cl = qps["close"]
    cl = cl[cl["market"] == "totals"][["game_id", "line", "season", "game_date", "home_score",
                                       "away_score", "tip"]].copy()
    cl["actual"] = cl["home_score"] + cl["away_score"]
    cl["miss"] = cl["actual"] - cl["line"]
    cl = cl.sort_values("tip")
    days = sorted(cl["game_date"].unique())
    drift = {}
    for N in (50, 100, 200):
        vals = {}
        for s, cs in cl.groupby("season"):
            cs = cs.sort_values("tip")
            gd = cs["game_date"].to_numpy()
            miss = cs["miss"].to_numpy()
            for d in np.unique(gd):
                prior = miss[gd < d]
                if len(prior) >= N:
                    vals[(s, d)] = float(prior[-N:].mean())
        drift[N] = vals
    drows, dparts, dcells = [], [], {}
    XS = [1.0, 2.0, 3.0, 4.0]
    for t in ("morning", "close"):
        b = tot[t]
        b = b[(b["price_source"] == "best") & (b["price"] >= PRICE_FLOOR)]
        for N in (50, 100, 200):
            dv = np.array([drift[N].get((s, d), np.nan) for s, d in zip(b["season"], b["game_date"])])
            for x in XS:
                pick = np.where(dv <= -x, "under", np.where(dv >= x, "over", ""))
                z = b[(pick != "") & (b["side"].to_numpy() == pick)]
                dcells[(t, N, x)] = z
                drows.append({"timing": t, "window": N, "drift>=": x, **cell_row(z),
                              "share_under": float((z["side"] == "under").mean()) if len(z) else np.nan})
                dparts.append(z.assign(cell=f"drift|{t}|{N}|{x}"))
    drift_grid = pd.DataFrame(drows)
    # choose per timing on 2022-2025 units
    dchosen = []
    for t in ("morning", "close"):
        keys = [k for k in dcells if k[0] == t]
        uc = {k: dcells[k][dcells[k]["season"].isin(CHOOSE)]["units"].sum() for k in keys}
        best = max(keys, key=lambda k: (round(uc[k], 6), -k[2]))
        _, N, x = best
        nb = []
        for N2 in (50, 100, 200):
            if N2 != N and abs([50, 100, 200].index(N2) - [50, 100, 200].index(N)) == 1:
                nb.append(dcells[(t, N2, x)])
        for x2 in XS:
            if abs(XS.index(x2) - XS.index(x)) == 1:
                nb.append(dcells[(t, N, x2)])
        b = tot[t]
        b = b[(b["price_source"] == "best") & (b["price"] >= PRICE_FLOOR) & b["season"].isin(GRADED)]
        blind = {sd: 100 * b[b["side"] == sd]["units"].sum() / b[b["side"] == sd]["risk"].sum()
                 for sd in ("over", "under")}
        # placebo: drift values shuffled across dates within each season
        rng = np.random.default_rng(SEED)
        pl = []
        bb = tot[t]
        bb = bb[(bb["price_source"] == "best") & (bb["price"] >= PRICE_FLOOR)]
        keysd = list(drift[N].keys())
        for _ in range(placebo_reps):
            sh = {}
            for s in set(k[0] for k in keysd):
                ks = [k for k in keysd if k[0] == s]
                vs = rng.permutation([drift[N][k] for k in ks])
                sh.update(dict(zip(ks, vs)))
            dv = np.array([sh.get((s, d), np.nan) for s, d in zip(bb["season"], bb["game_date"])])
            pick = np.where(dv <= -x, "under", np.where(dv >= x, "over", ""))
            z = bb[(pick != "") & (bb["side"].to_numpy() == pick) & bb["season"].isin(GRADED)]
            pl.append(100 * z["units"].sum() / z["risk"].sum() if len(z) else 0.0)
        info, failed = bars(dcells[best], nb, blind, pl)
        dchosen.append({"rule": f"follow drift, window {N}, |drift|>={x}", "timing": t,
                        **{k: v for k, v in info.items() if k != "neighbours"},
                        "neighbours": ", ".join(f"{r:+.1f}" for r in info["neighbours"]),
                        "placebo_p95": float(np.percentile(pl, 95)) if pl else np.nan,
                        "blind_same": blind.get(info["top_side"]),
                        "failed": "; ".join(failed), "passes": not failed})
    drift_ch = pd.DataFrame(dchosen)
    # drift vs the next day's miss, blind by season (N=100)
    dd = cl.copy()
    dd["drift100"] = [drift[100].get((s, d), np.nan) for s, d in zip(dd["season"], dd["game_date"])]
    corr = []
    for s, z in dd.dropna(subset=["drift100"]).groupby("season"):
        corr.append({"season": s, "games": len(z), "corr(drift100, miss)": z["drift100"].corr(z["miss"]),
                     "mean miss": z["miss"].mean(),
                     "over% when drift<0": 100 * (z.loc[z["drift100"] < 0, "miss"] > 0).mean(),
                     "over% when drift>0": 100 * (z.loc[z["drift100"] > 0, "miss"] > 0).mean()})
    corr = pd.DataFrame(corr)
    allparts = pd.concat(eparts + dparts, ignore_index=True)
    allparts.assign(fair_prob=np.nan, ev=np.nan).to_parquet(
        OUT / "game_market_situational_bets.parquet", index=False)
    for nm, df in (("early_tab", early_tab), ("early_grid", early_grid), ("early_chosen", early_ch),
                   ("drift_grid", drift_grid), ("drift_chosen", drift_ch), ("drift_corr", corr)):
        df.to_csv(SCRATCH / f"sit_{nm}.csv", index=False)
    return early_tab, early_grid, early_ch, drift_grid, drift_ch, corr


# ── report writing ──────────────────────────────────────────────────────────

def _pivot_cells(grid: pd.DataFrame, by: str = "floor") -> pd.DataFrame:
    g = grid.copy()
    g["cell"] = [f"{int(n)} / {r:+.1f}% / {u:+.1f}u" if n else "0"
                 for n, r, u in zip(g["bets"], g["roi"].fillna(0), g["units"].fillna(0))]
    return g.pivot(index=by, columns="family", values="cell").reset_index()


CHOSEN_COLS = ["bets", "units", "roi", "ci_lo", "ci_hi", "h1", "h2", "top_side", "top_share", "removed_by_-200",
               "neighbours", "blind_same", "placebo_p95"]


def _timing_table(b: pd.DataFrame) -> pd.DataFrame:
    b = b[b["season"].isin(GRADED)].copy()
    b["hbucket"] = hours_bucket(b["hours_to_tip"])
    rows = []
    for col in ("bucket", "hbucket"):
        for k, z in b.groupby(col):
            rows.append({"split": col.replace("hbucket", "hours to tip").replace("bucket", "named"),
                         "bucket": k, "bets": len(z), "units": z["units"].sum(),
                         "roi": 100 * z["units"].sum() / z["risk"].sum(),
                         "clv_med%": 100 * np.nanmedian(z["clv_ev"]) if "clv_ev" in z else np.nan})
    return pd.DataFrame(rows)


def sharp_report(grid, chosen, bets, info) -> str:
    t = ["## 3. Sharp-vs-soft rule (the NHL totals rule, all three markets)\n",
         "Inside ONE fetch, Pinnacle's two-way quote is de-vigged (proportional; power as the "
         "second method) and compared with every bettable book in the SAME fetch at the SAME "
         "number (moneyline: direct). EV = fair x decimal - 1. A game is bet once per market, "
         "at the first fetch (from the opener on, inside the 7-day live horizon) in which a "
         "quote clears the floor, at the best EV there (ties: book order of "
         "BEST_LINE_BOOKMAKERS, then home/over). A fetch without Pinnacle is never used, which "
         "is the live rule's 'skip if Pinnacle withdrew'. Price -200 or better. Families: "
         "moneyline and spread {all, home, away, fav, dog} (favourite by Pinnacle in that "
         "fetch), total {all, over, under}. The floor is chosen per family on 2021-22..2024-25 "
         "by units, then every bar is read on 2021-22..2025-26.\n",
         f"Candidate quotes (soft book x side x fetch at Pinnacle's number): {info['candidates']:,}; "
         f"beyond the 168 h live horizon and dropped: {info['beyond_lead']:,}.\n",
         f"Cells searched: {len(grid):,} (floors x families x de-vig x variant). "
         "Bet lists for every cell: `game_market_sharp_bets.parquet` (column `cell`).\n"]
    for variant, label in (("pinnacle_vs_bettable", "Pinnacle vs every bettable book"),
                           ("pinnacle_vs_draftkings", "Pinnacle vs DraftKings only"),
                           ("draftkings_ref_placebo",
                            "PLACEBO: DraftKings as the reference, the other bettable books bet")):
        gv = grid[grid["variant"] == variant]
        for dv in sorted(gv["devig"].unique(), key=lambda d: d != "prop"):
            for m in ("moneyline", "spread", "total"):
                gm = gv[(gv["devig"] == dv) & (gv["market"] == m)]
                if not len(gm):
                    continue
                t.append(f"\n### {label}, {m}, {dv} de-vig: bets / ROI / units, graded seasons "
                         "2021-22..2025-26\n")
                t.append(md_table(_pivot_cells(gm.assign(floor=gm["floor"].map("{:.3f}".format)))))
                if variant == "pinnacle_vs_bettable" and dv == "prop":
                    cols = ["family", "floor", "bets", "units", "roi"] + [str(s) for s in GRADED] \
                        + ["clv_med%", "beat_close%"]
                    t.append("\nPer season ROI (%), and CLV at Pinnacle's no-vig close:\n")
                    t.append(md_table(gm[cols].assign(floor=gm["floor"].map("{:.3f}".format))))
    t.append("\n### The chosen cut per family, and the bars\n")
    t.append("Bars: 4 = 2025-26 positive (the confirmation season, never used to choose); "
             "5 = every graded season with >= 30 bets positive; 6 = >= 200 bets and whole-day "
             "bootstrap 90% CI above zero; 7 = the floors one step either side positive; "
             "8 = both chronological halves positive; 9 = when > 70% of bets are one side, beats "
             "the blind bet on that side (every graded game, first Pinnacle-quoted fetch, best "
             "price at Pinnacle's number, -200 floor); 10 = beats the 95th percentile of 20 "
             "within-date shuffles of Pinnacle's probability; 11 = median bet's EV at "
             "Pinnacle's no-vig close above zero.\n")
    ch = chosen.copy()
    ch["floor"] = ch["floor"].map("{:.3f}".format)
    cols = ["variant", "devig", "market", "family", "floor"] + CHOSEN_COLS + ["failed"]
    t.append(md_table(ch[[c for c in cols if c in ch]]))
    # timing and lag on the main variant
    mainb = bets[bets["cell"].str.startswith("pinnacle_vs_bettable|prop|")]
    for m in MARKETS:
        for fl in (0.0, 0.01, 0.02):
            key = f"pinnacle_vs_bettable|prop|{m}|all|{fl}"
            b = mainb[mainb["cell"] == key]
            if not len(b):
                continue
            t.append(f"\nWhere the units sit, {MARKET_NAME[m]} all sides, floor {fl}: by fetch "
                     "timing (graded seasons):\n")
            t.append(md_table(_timing_table(b)))
            gb = b[b["season"].isin(GRADED)]
            if "soft_lag_min" in gb and len(gb):
                q = np.nanpercentile(gb["soft_lag_min"], [10, 50, 90, 99])
                fresh = gb[gb["soft_lag_min"].abs() <= 30]
                t.append(f"\nSoft quote age vs Pinnacle's (minutes, Pinnacle last_update minus "
                         f"the soft book's; positive = soft quote older): p10 {q[0]:.0f}, "
                         f"p50 {q[1]:.0f}, p90 {q[2]:.0f}, p99 {q[3]:.0f}. Restricted to soft "
                         f"quotes within 30 minutes of Pinnacle's: {len(fresh)} bets, "
                         f"{fresh['units'].sum():+.1f}u, "
                         f"{100 * fresh['units'].sum() / max(1e-9, fresh['risk'].sum()):+.1f}% "
                         f"(all: {len(gb)} bets, {gb['units'].sum():+.1f}u, "
                         f"{100 * gb['units'].sum() / max(1e-9, gb['risk'].sum()):+.1f}%).\n")
    return "\n".join(t)


def gap_report(grid, chosen, props, sigtab) -> str:
    t = [_REPORT_PARTS.get("gap_head", "")]
    t.append("\nSigma used for each season (fit on the seasons before it; 2020-21 has no "
             "earlier priced season and uses its own):\n")
    t.append(md_table(sigtab))
    t.append("\nEvery priced gap proposition (each fetch x book, correlated; graded seasons, "
             "-200 floor), by gap size:\n")
    t.append(md_table(props))
    t.append("\nThe rule grid (one bet a game per market, first qualifying fetch):\n")
    cols = ["variant", "market", "gap>=", "ev_filter", "bets", "units", "roi"] + \
        [str(s) for s in GRADED] + ["clv_med%", "beat_close%"]
    t.append(md_table(grid[[c for c in cols if c in grid]]))
    t.append("\nChosen cell per market (chosen on 2021-22..2024-25 units) and the bars "
             "(neighbours: gap one step either side, then EV filter one step either side):\n")
    cols = ["variant", "market", "gap>=", "ev_filter"] + CHOSEN_COLS + ["failed"]
    t.append(md_table(chosen[[c for c in cols if c in chosen]]))
    return "\n".join(t)


def situational_report(early_tab, early_grid, early_ch, drift_grid, drift_ch, corr) -> str:
    t = ["## 5. Situational totals\n",
         "### 5a. Early season: blind totals by days since the season's opening night\n",
         "ROI % by season (n = bets). 'open' = DraftKings' first pre-game fetch, 'close' = its "
         "last pre-tip fetch; best = best bettable price at DraftKings' number. No price floor "
         "on this blind table. 2020-21 opened 2020-12-22 (the COVID start).\n"]
    t.append(md_table(early_tab[[c for c in early_tab.columns if not c.startswith("n")
                                 or c == "graded n"]]))
    t.append("\nAs a rule: bet every under in the first N days (best bettable price, -200 floor):\n")
    t.append(md_table(early_grid))
    t.append("\nBars (placebo = the same-length window placed at every other week of the season; "
             "blind = every under all season at the same timing):\n")
    cols = ["rule", "timing"] + CHOSEN_COLS + ["failed"]
    t.append(md_table(early_ch[[c for c in cols if c in early_ch]]))
    t.append("\n### 5b. League scoring drifting away from the totals\n"
             "drift_N = mean(actual total - DraftKings' closing total) over the season's last N "
             "games completed before the game date. Signal: drift <= -x -> under, drift >= +x -> "
             "over (follow the drift: scoring below the lines means the lines are high). Decided "
             "at the game-day 15Z fetch (primary: every earlier day's games are final by then) "
             "and at the close; best bettable price at DraftKings' number, -200 floor. Cells: "
             "N {50, 100, 200} x x {1, 2, 3, 4} x timing = 24.\n")
    t.append("\nBlind, by season (window 100): does recent drift predict tonight's miss?\n")
    t.append(md_table(corr))
    t.append("\nThe grid:\n")
    cols = ["timing", "window", "drift>=", "bets", "units", "roi"] + [str(s) for s in GRADED] + \
        ["share_under", "clv_med%"]
    t.append(md_table(drift_grid[[c for c in cols if c in drift_grid]]))
    t.append("\nChosen per timing (on 2021-22..2024-25 units) and the bars (placebo = drift "
             "shuffled across dates within each season, 20 times):\n")
    cols = ["rule", "timing"] + CHOSEN_COLS + ["failed"]
    t.append(md_table(drift_ch[[c for c in cols if c in drift_ch]]))
    return "\n".join(t)


BET_COLS = ["game_id", "game_date", "season", "market", "side", "line", "book", "price",
            "fair_prob", "ev", "decision_fetch", "result", "units", "risk", "close_fair_prob",
            "clv_ev", "clv_later", "hours_to_tip", "bucket", "soft_lag_min", "fav"]


def section_candidate(o: pd.DataFrame, close: pd.DataFrame) -> str:
    """Robustness checks on every sharp-rule cell that passed the bars.

    The bars are read with Pinnacle's PROPORTIONAL no-vig close. For a list of long
    underdogs the de-vig method matters, so: (1) CLV re-read against the POWER close;
    (2) which de-vig is calibrated for NBA underdogs at Pinnacle's close (every game);
    (3) claimed EV vs realised; (4) 2020-21, the season no cut was ever near;
    (5) books, timing, price bands; (6) overlap with the DraftKings-reference control;
    (7) whether the quote-age field can see a stale quote at all."""
    log("candidate checks")
    ch = pd.read_csv(SCRATCH / "sharp_chosen.csv")
    bets = pd.read_parquet(OUT / "game_market_sharp_bets.parquet")
    t = ["## 3b. The cell that passed: checks before anyone reads it as a model\n"]
    passed = ch[ch["passes"]]
    t.append("Cells passing every bar, all variants:\n")
    passed = passed.assign(floor=passed["floor"].map("{:.3f}".format))
    t.append(md_table(passed[["variant", "devig", "market", "family", "floor", "bets", "units",
                              "roi", "ci_lo", "ci_hi", "h1", "h2", "top_side", "top_share"]]))
    t.append("\nThe within-date shuffle placebo (bar 10) was run on the main variant only; the "
             "DraftKings-only and DraftKings-reference variants were not shuffled, so their "
             "'passes' omits bar 10.\n")
    main = ch[(ch["passes"]) & (ch["variant"] == "pinnacle_vs_bettable")]
    hc = close[close["market"] == "h2h"][["game_id", "close_fa_prop", "close_fa_pow", "close_ts"]]
    # calibration of the two de-vig methods, Pinnacle close, underdog side, every game
    c = close[close["market"] == "h2h"].copy()
    away_win = (c["away_score"] > c["home_score"]).astype(int)
    dog_away = (1 - c["close_fa_prop"]) < 0.5
    c["dog_prop"] = np.where(dog_away, 1 - c["close_fa_prop"], c["close_fa_prop"])
    c["dog_pow"] = np.where(dog_away, 1 - c["close_fa_pow"], c["close_fa_pow"])
    c["dog_win"] = np.where(dog_away, away_win, 1 - away_win)
    c["band"] = pd.cut(c["dog_prop"], [0, .1, .15, .2, .25, .3, .35, .4, .45, .5]).astype(str)
    cal = c.groupby("band").agg(games=("dog_win", "size"), proportional=("dog_prop", "mean"),
                                power=("dog_pow", "mean"), realised=("dog_win", "mean")).reset_index()
    cal["realised_se"] = np.sqrt(cal["realised"] * (1 - cal["realised"]) / cal["games"])
    ll = {}
    for col in ("dog_prop", "dog_pow"):
        p = c[col].clip(1e-6, 1 - 1e-6)
        y = c["dog_win"]
        ll[col] = float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())
    ref_cells = ch[(ch["variant"] == "draftkings_ref_placebo") & (ch["market"] == "moneyline")
                   & (ch["family"] == "all")]
    ref_key = (f"draftkings_ref_placebo|prop|h2h|all|{ref_cells['floor'].iloc[0]}"
               if len(ref_cells) else None)
    cstats = {"calibration": cal.to_dict("records"), "logloss": ll, "candidates": []}
    for r in main.itertuples():
        mkt = {v: k for k, v in MARKET_NAME.items()}[r.market]
        key = f"{r.variant}|{r.devig}|{mkt}|{r.family}|{r.floor}"
        b = bets[bets["cell"] == key].copy()
        name = f"{r.variant}_{r.devig}_{mkt}_{r.family}_ev{r.floor:.3f}"
        path = OUT / f"game_market_candidate_{name}.parquet"
        b[[col for col in BET_COLS if col in b]].to_parquet(path, index=False)
        t.append(f"\n### {r.market}, {r.family}, EV >= {r.floor:.3f} ({r.devig} de-vig)\n")
        t.append(f"Bet list: `{path.name}` ({len(b)} bets including 2020-21).\n")
        b = b.merge(hc, on="game_id", how="left")
        d = dec(b["price"])
        later = pd.to_datetime(b["decision_fetch"], utc=True) < b["close_ts"]
        is_a = b["side"].isin(["home", "over"]).to_numpy()
        pp = np.where(is_a, b["close_fa_pow"], 1 - b["close_fa_pow"])
        b["clv_pow"] = np.where(later, pp * d - 1, np.nan)
        rows = []
        for s in ALL_SEASONS:
            z = b[b["season"] == s]
            rows.append({"season": s, "bets": len(z), "units": z["units"].sum(),
                         "roi": 100 * z["units"].sum() / z["risk"].sum() if len(z) else np.nan,
                         "risked": z["risk"].sum(),
                         "clv_med% (proportional close)": 100 * z["clv_ev"].median(),
                         "clv_med% (power close)": 100 * z["clv_pow"].median(),
                         "beat close% (power)": 100 * (z["clv_pow"].dropna() > 0).mean()})
        t.append("\nBy season (2020-21 was never used to choose anything and is not a graded "
                 "season; it is shown as a sixth read):\n")
        t.append(md_table(pd.DataFrame(rows)))
        g = b[b["season"].isin(GRADED)]
        # claimed vs realised; power EV at the same decision
        pr = sharp_pairs(o[o["market"] == mkt])
        pr = pr[pr["side"] == r.family] if r.family in ("home", "away", "over", "under") else pr
        pr = pr[["game_id", "bookmaker", "fetch_ts", "side", "fair_pow", "ev_pow"]].assign(
            decision_fetch=lambda v: v["fetch_ts"].astype(str)).drop(columns="fetch_ts")
        y = g.merge(pr.rename(columns={"bookmaker": "book"}), on=["game_id", "book", "side",
                                                                  "decision_fetch"], how="left")
        t.append(f"\nGraded seasons: {len(g)} bets, {g['units'].sum():+.2f}u, risked "
                 f"{g['risk'].sum():.1f}u, ROI {100 * g['units'].sum() / g['risk'].sum():+.2f}%. "
                 f"Claimed at decision (risk-weighted EV): proportional "
                 f"{100 * (g['risk'] * g['ev']).sum() / g['risk'].sum():+.2f}%, power "
                 f"{100 * (y['risk'] * y['ev_pow']).sum() / y['risk'].sum():+.2f}% "
                 f"(power EV >= 0 on {100 * (y['ev_pow'] >= 0).mean():.1f}% of the bets). Win "
                 f"rate claimed {100 * g['fair_prob'].mean():.2f}% (proportional) / "
                 f"{100 * y['fair_pow'].mean():.2f}% (power), realised "
                 f"{100 * (g['result'] == 'W').mean():.2f}%. Median CLV over the "
                 f"{int(g['clv_ev'].notna().sum())} bets with a later Pinnacle price: "
                 f"{100 * g['clv_ev'].median():+.2f}% against the proportional close, "
                 f"{100 * g['clv_pow'].median():+.2f}% against the power close.\n")
        # CLV of the blind bet on the same side (line drift can make a side look like CLV)
        blind_clv = {}
        bp = SCRATCH / "baselines.csv"
        if bp.exists():
            bl = pd.read_csv(bp)
            for tmg in ("open", "close"):
                q = bl[(bl["market"] == r.market) & (bl["side"] == r.family) & (bl["timing"] == tmg)
                       & (bl["price"] == "best")]
                if len(q):
                    blind_clv[tmg] = float(q["clv_med%"].iloc[0])
        # why the two de-vig methods disagree: the probability gap times a long decimal
        gl = g[g["clv_pow"].notna()]
        p_side_prop = np.where(gl["side"].isin(["home", "over"]), gl["close_fa_prop"],
                               1 - gl["close_fa_prop"])
        p_side_pow = np.where(gl["side"].isin(["home", "over"]), gl["close_fa_pow"],
                              1 - gl["close_fa_pow"])
        gap_pp = 100 * float(np.mean(p_side_prop - p_side_pow))
        dmed = float(np.median(dec(gl["price"])))
        if blind_clv:
            t.append(f"\nCLV against the blind bet on the same side: the blind {r.family} bet at "
                     f"the best price has median CLV {blind_clv.get('open', np.nan):+.2f}% at "
                     f"the open and {blind_clv.get('close', np.nan):+.2f}% at the close "
                     "(proportional close, section 2), against "
                     f"{100 * g['clv_ev'].median():+.2f}% for these bets. Line drift toward the "
                     "side does not explain the candidate's CLV.\n")
        t.append(f"\nWhy the two closes disagree by so much: at the close, proportional gives "
                 f"these sides {gap_pp:.2f} percentage points more win probability than power "
                 f"(mean), and the median bet pays {dmed:.2f} in decimal, so the same gap moves "
                 f"EV by about {gap_pp * dmed:.1f} points. The CLV swing is that arithmetic on "
                 "long prices, not two different pictures of the bets.\n")
        t.append("\nThe cadence risk points one way. The live worker takes the FIRST qualifying "
                 "quote out of ~53 looks a day instead of 8-9, so live bets land earlier than "
                 "the backtest's, and the earliest bucket (evening before) is the one that "
                 "loses. The unmeasured live version is more likely worse than this backtest "
                 "than better.\n")
        for col, lab in (("book", "book"), ("bucket", "fetch timing"), ("fav", "favourite/dog")):
            tb = g.groupby(col).agg(bets=("units", "size"), units=("units", "sum"),
                                    risked=("risk", "sum")).reset_index()
            tb["roi"] = 100 * tb["units"] / tb["risked"]
            t.append(f"\nBy {lab}:\n")
            t.append(md_table(tb))
        g2 = g.assign(price_band=pd.cut(g["price"], [-201, -110, 100, 150, 250, 400, 10000]).astype(str))
        tb = g2.groupby("price_band").agg(bets=("units", "size"), units=("units", "sum"),
                                          risked=("risk", "sum")).reset_index()
        tb["roi"] = 100 * tb["units"] / tb["risked"]
        t.append("\nBy price band (American):\n")
        t.append(md_table(tb))
        if ref_key is not None:
            rb = bets[(bets["cell"] == ref_key) & bets["season"].isin(GRADED)]
            both = g[g["game_id"].isin(rb["game_id"])]
            only = g[~g["game_id"].isin(rb["game_id"])]
            t.append(f"\nOverlap with the DraftKings-reference control's chosen moneyline cell "
                     f"(`{ref_key}`, {len(rb)} bets): {len(both)} of these {len(g)} bets are on "
                     f"games the control also bet, carrying {both['units'].sum():+.2f}u "
                     f"({100 * both['units'].sum() / max(1e-9, both['risk'].sum()):+.2f}%); the "
                     f"{len(only)} Pinnacle-only bets carry {only['units'].sum():+.2f}u "
                     f"({100 * only['units'].sum() / max(1e-9, only['risk'].sum()):+.2f}%).\n")
        else:
            rb, both, only = g.iloc[:0], g.iloc[:0], g
        bk = g.groupby("book")["units"].sum().sort_values(ascending=False)
        tm = g.groupby("bucket").agg(n=("units", "size"), u=("units", "sum"), r=("risk", "sum"))
        z21 = b[b["season"] == 2021]
        cstats["candidates"].append({
            "key": key, "market": r.market, "family": r.family, "floor": float(r.floor),
            "bets": int(len(g)), "units": float(g["units"].sum()), "risked": float(g["risk"].sum()),
            "roi": float(100 * g["units"].sum() / g["risk"].sum()),
            "ci": [float(r.ci_lo), float(r.ci_hi)], "h1": float(r.h1), "h2": float(r.h2),
            "season_roi": {int(s_): float(100 * g.loc[g["season"] == s_, "units"].sum()
                                          / g.loc[g["season"] == s_, "risk"].sum())
                           for s_ in GRADED if (g["season"] == s_).any()},
            "roi_2021": float(100 * z21["units"].sum() / z21["risk"].sum()) if len(z21) else None,
            "bets_2021": int(len(z21)), "units_2021": float(z21["units"].sum()),
            "clv_prop_med": float(100 * g["clv_ev"].median()),
            "clv_pow_med": float(100 * g["clv_pow"].median()),
            "beat_pow": float(100 * (g["clv_pow"].dropna() > 0).mean()),
            "clv_n": int(g["clv_ev"].notna().sum()),
            "claimed_prop": float(100 * (g["risk"] * g["ev"]).sum() / g["risk"].sum()),
            "claimed_pow": float(100 * (y["risk"] * y["ev_pow"]).sum() / y["risk"].sum()),
            "dog_share": float(100 * (g["fav"] == "dog").mean()),
            "median_price": float(g["price"].median()),
            "blind_same": float(r.blind_same) if pd.notna(r.blind_same) else None,
            "placebo_p95": float(r.placebo_p95) if pd.notna(r.placebo_p95) else None,
            "top_book": bk.index[0], "top_book_units": float(bk.iloc[0]),
            "timing": {k: [int(v.n), float(v.u), float(100 * v.u / v.r)] for k, v in tm.iterrows()},
            "ref_key": ref_key, "ref_bets": int(len(rb)), "overlap_bets": int(len(both)),
            "overlap_units": float(both["units"].sum()), "only_units": float(only["units"].sum()),
            "bets_a_season": float(len(g) / len(GRADED)),
            "units_a_season": float(g["units"].sum() / len(GRADED)),
            "risked_a_season": float(g["risk"].sum() / len(GRADED)),
            "blind_clv": blind_clv, "devig_gap_pp": gap_pp, "median_decimal": dmed})
    (SCRATCH / "candidate_stats.json").write_text(json.dumps(cstats, default=str, indent=1),
                                                  encoding="utf-8")
    t.append("\nIs the proportional close the right yardstick for long underdogs? Pinnacle's "
             "closing moneyline, underdog side, every priced game 2020-21..2025-26 "
             f"({len(c):,} games): mean no-vig probability by band against the realised win "
             f"rate. Log loss: proportional {ll['dog_prop']:.5f}, power {ll['dog_pow']:.5f}.\n")
    t.append(md_table(cal, "{:.4f}"))
    age = (o["fetch_ts"] - o["snap"]).dt.total_seconds() / 60
    aq = age.groupby(o["bookmaker"]).quantile([0.5, 0.99, 1.0]).unstack()
    aq.columns = ["p50 min", "p99 min", "max min"]
    t.append("\nCan the quote-age field see a stale quote? Minutes between each quote's "
             "`snapshot_at` (the feed's last_update) and its fetch, every pre-game row:\n")
    t.append(md_table(aq.reset_index(), "{:.1f}"))
    t.append("\nEvery book's last_update sits within 15 minutes of the fetch, so in this "
             "historical feed the field tracks the feed's poll, not the moment the price last "
             "changed. It cannot show whether a soft quote was stale; the soft-age split in "
             "section 3 is reported but proves nothing either way.\n")
    t.append("\nLive cadence. scheduler.py runs the refresh pass at :17 each hour 7am-5pm ET "
             "(11 passes) and midnight-5am ET (6), and every 10 minutes 6-11pm ET (36): 53 "
             "passes a day. Whether the evening mode re-reads NBA game lines was not checked. "
             "The backtest saw the 8-9 stored snapshots per game date. A first-qualifying-quote "
             "rule with ~6x more looks fires on more games and earlier (the NHL regulation-"
             "model lesson); that version is NOT measured here.\n")
    txt = "\n".join(t)
    report("candidate", txt)
    return txt


def section_summary() -> str:
    """Section 0, written from the saved results (no number is typed by hand)."""
    W = SCRATCH
    ls = json.loads((W / "load_stats.json").read_text(encoding="utf-8")) \
        if (W / "load_stats.json").exists() else {}
    sg = pd.read_csv(W / "sharp_grid.csv")
    sc = pd.read_csv(W / "sharp_chosen.csv")
    gg = pd.read_csv(W / "gap_grid.csv")
    eg = pd.read_csv(W / "sit_early_grid.csv")
    et = pd.read_csv(W / "sit_early_tab.csv")
    dg = pd.read_csv(W / "sit_drift_grid.csv")
    dc = pd.read_csv(W / "sit_drift_chosen.csv")
    corr = pd.read_csv(W / "sit_drift_corr.csv")
    bl = pd.read_csv(W / "baselines.csv")
    cs = json.loads((W / "candidate_stats.json").read_text(encoding="utf-8")) \
        if (W / "candidate_stats.json").exists() else {"candidates": []}
    n_cells = len(sg) + len(gg) + len(eg) + len(dg) + len(bl)
    t = ["## 0. Summary\n"]
    t.append(f"**What was tested.** Moneyline, spread and total for every NBA game 2020-21.."
             f"2025-26 ({ls.get('games_priced', 'n/a')} games with prices; "
             f"{ls.get('rows_used', 0):,} pre-game quotes after the checks in section 1). Every "
             "price is a real quote from one stored fetch, decided and graded at the best bettable "
             "book at the same number; no -110 fallback; one unit to win. Graded: 2021-22.."
             "2025-26, cut chosen on 2021-22..2024-25, confirmed on 2025-26. Cells searched: "
             f"{n_cells} (sharp-vs-soft {len(sg)}, line-gap {len(gg)}, early-season unders "
             f"{len(eg)}, league drift {len(dg)}, blind baselines {len(bl)}).\n")
    ctrl = sc[(sc["variant"] == "draftkings_ref_placebo") & sc["passes"]]
    for c in cs.get("candidates", []):
        sr = " / ".join(f"{v:+.1f}%" for v in c["season_roi"].values())
        t.append(f"**Result: one cell passes every pre-registered bar (4-11).** {c['market']}, "
                 f"{c['family'].upper()} side, Pinnacle's proportional no-vig against the best "
                 f"bettable price in the same fetch, EV >= {c['floor']:.3f}: {c['bets']:,} bets, "
                 f"{c['units']:+.2f}u, ROI {c['roi']:+.2f}%, whole-day bootstrap 90% CI "
                 f"{c['ci'][0]:+.2f}..{c['ci'][1]:+.2f}; every graded season positive ({sr}); "
                 f"halves {c['h1']:+.1f} / {c['h2']:+.1f}%; beats the blind {c['family']} bet "
                 f"({c['blind_same']:+.1f}%) and the 20-shuffle placebo (95th percentile "
                 f"{c['placebo_p95']:+.1f}%); median CLV against Pinnacle's proportional close "
                 f"{c['clv_prop_med']:+.2f}% on {c['clv_n']:,} bets with a later price. It is one "
                 "of 26 side families on the main variant (13 families x 2 de-vig methods).\n")
        t.append("**Six facts that come with it, all measured in section 3b:**\n")
        ct = ""
        if len(ctrl):
            r = ctrl.iloc[0]
            ct = (f"DraftKings' no-vig as the reference instead of Pinnacle, betting the other "
                  f"bettable books, ALSO clears every bar it was put to ({r['market']}, "
                  f"{r['family']} sides, EV >= {r['floor']:.3f}: {int(r['bets']):,} bets, "
                  f"{r['roi']:+.2f}%, CI {r['ci_lo']:+.2f}..{r['ci_hi']:+.2f}; it was not "
                  "shuffled). ")
        tm = c["timing"]
        eb = tm.get("evening before", [0, 0, float("nan")])
        cal = {d["band"]: d for d in cs.get("calibration", [])}
        bands = ["(0.15, 0.2]", "(0.2, 0.25]", "(0.25, 0.3]", "(0.3, 0.35]"]
        fmt = lambda k: " / ".join(f"{100 * cal[b][k]:.1f}" for b in bands if b in cal)  # noqa
        t.append(
            f"1. **The control passes too.** {ct}{c['overlap_bets']:,} of the candidate's "
            f"{c['bets']:,} bets are on games the control also bet, and they carry "
            f"{c['overlap_units']:+.2f}u of its {c['units']:+.2f}u. So this is not Pinnacle's "
            "information: it is soft books posting away-underdog prices longer than ANY consensus. "
            "The honest name is away-underdog moneyline outlier shopping; the Pinnacle "
            "arithmetic is only how the outliers are found. (The CLV is not line drift: the "
            f"blind {c['family']} bet's median CLV is "
            f"{c.get('blind_clv', {}).get('open', float('nan')):+.2f}% at the open and "
            f"{c.get('blind_clv', {}).get('close', float('nan')):+.2f}% at the close.)\n"
            f"2. **The de-vig method decides bar 11.** Against Pinnacle's POWER-de-vigged close "
            f"the same bets' median CLV is {c['clv_pow_med']:+.2f}% ({c['beat_pow']:.1f}% beat "
            "it), negative in every season. That swing is arithmetic: at the close proportional "
            f"gives these sides {c.get('devig_gap_pp', float('nan')):.2f} points more win "
            f"probability than power, and the median bet pays {c.get('median_decimal', float('nan')):.2f} "
            "in decimal. In the 15-35% underdog band where these bets sit, Pinnacle's close is "
            f"no worse calibrated under proportional than power (realised {fmt('realised')} vs "
            f"proportional {fmt('proportional')} vs power {fmt('power')}; log loss "
            f"{cs['logloss']['dog_prop']:.5f} vs {cs['logloss']['dog_pow']:.5f}), so the "
            "proportional reading is the defensible one, but the bar flips on a method choice.\n"
            f"3. **2020-21, never used to choose anything, is negative:** {c['bets_2021']} bets, "
            f"{c['units_2021']:+.2f}u, {c['roi_2021']:+.2f}%.\n"
            f"4. **Realised beat claimed.** Claimed EV at the decision {c['claimed_prop']:+.2f}% "
            f"(proportional) / {c['claimed_pow']:+.2f}% (power) against {c['roi']:+.2f}% "
            f"realised. {c['dog_share']:.0f}% of the bets are underdogs, median price "
            f"{c['median_price']:+.0f}; part of the result is luck on long prices.\n"
            f"5. **Where the units sit.** {c['top_book']} carries {c['top_book_units']:+.2f}u of "
            f"{c['units']:+.2f}u. The evening-before fetches lose ({eb[2]:+.2f}% on {eb[0]} "
            "bets), the opposite of the NHL totals rule's timing; reported, not cut. The live "
            "worker looks ~53 times a day against the backtest's 8-9 snapshots and takes the "
            "first qualifying quote, so live bets would land earlier, where this rule loses: "
            "the unmeasured live version is more likely worse than the backtest than better.\n"
            f"6. **It is small.** One unit to win, so a +320 underdog risks 0.31u: "
            f"{c['units_a_season']:+.1f}u a season on about {c['bets_a_season']:.0f} bets, with "
            f"about {c['risked_a_season']:.0f}u risked a season.\n")
        t.append("The bars as written are passed, so by docs/nba_models_2026.md section 1 this "
                 "cell is a candidate. Whether outlier shopping on away underdogs, which a "
                 "control with no Pinnacle finds just as well, is what should ship is a "
                 "judgement the bars do not make.\n")
    if not cs.get("candidates"):
        t.append("**Result: no cell passes every bar.**\n")
    # failures
    main = sg[(sg["variant"] == "pinnacle_vs_bettable") & (sg["devig"] == "prop")
              & (sg["family"] == "all") & (sg["floor"] == 0.0)].set_index("market")
    t.append("**What failed:**\n")
    if {"spread", "total"} <= set(main.index):
        sp, tt = main.loc["spread"], main.loc["total"]
        t.append(f"- **Sharp-vs-soft on spreads and totals: nothing.** NBA soft books almost "
                 "never disagree with Pinnacle on PRICE at the same number; they move the number. "
                 f"At EV >= 0, five seasons give {int(sp['bets'])} spread bets ({sp['roi']:+.1f}%) "
                 f"and {int(tt['bets'])} total bets ({tt['roi']:+.1f}%). The NHL totals rule does "
                 "not transfer.\n")
    gp = gg[(gg["variant"] == "pinnacle_gap")]
    best_g = gp.sort_values("units", ascending=False).iloc[0]
    t.append(f"- **Line-gap rule: nothing.** Best cell {best_g['market']} gap >= "
             f"{best_g['gap>=']}, EV filter {best_g['ev_filter']}: {int(best_g['bets'])} bets, "
             f"{best_g['roi']:+.2f}%, median CLV {best_g['clv_med%']:+.2f}% with a later price; "
             "seasons and CLV fail (section 4). The DraftKings-reference version is flat.\n")
    wk = et[(et["side"] == "under") & (et["price"] == "best") & (et["days"] == "0-6")]
    if len(wk):
        o_ = wk[wk["timing"] == "open"].iloc[0]
        c_ = wk[wk["timing"] == "close"].iloc[0]
        t.append(f"- **Early-season unders: dead.** First-week blind unders "
                 f"{o_['graded ROI']:+.1f}% at the open, {c_['graded ROI']:+.1f}% at the close "
                 f"(2025-26 {c_['2026']:+.1f}%); every cut fails five or more bars.\n")
    if len(dc):
        r = dc[dc["timing"] == "morning"].iloc[0] if (dc["timing"] == "morning").any() else dc.iloc[0]
        t.append(f"- **League scoring drift: nothing.** Best cell ({r['rule']}, {r['timing']}) "
                 f"{int(r['bets'])} bets {r['roi']:+.2f}%, CI {r['ci_lo']:+.1f}..{r['ci_hi']:+.1f}; "
                 f"fails: {r['failed']}. Drift's correlation with tonight's miss is "
                 f"{corr['corr(drift100, miss)'].min():+.3f} to {corr['corr(drift100, miss)'].max():+.3f} "
                 "by season.\n")
    t.append(f"- **Blind baselines: all negative**, {bl['graded ROI'].max():+.2f}% to "
             f"{bl['graded ROI'].min():+.2f}% (section 2).\n")
    txt = "\n".join(t)
    report("notes", txt)
    return txt


def section_units() -> str:
    """Section 6: every candidate's verdict, and units a season for any that clears."""
    rows = []
    sc = SCRATCH / "sharp_chosen.csv"
    if sc.exists():
        c = pd.read_csv(sc)
        for r in c.itertuples():
            rows.append({"name": f"{r.variant} {r.devig} {r.market} {r.family}",
                         "rule": f"EV >= {r.floor}", "bets": r.bets, "units": r.units, "roi": r.roi,
                         "ci": f"{r.ci_lo:+.1f}..{r.ci_hi:+.1f}", "passes": bool(r.passes),
                         "failed bars": r.failed if isinstance(r.failed, str) else ""})
    gc = SCRATCH / "gap_chosen.csv"
    if gc.exists():
        c = pd.read_csv(gc)
        for _, r in c.iterrows():
            rows.append({"name": f"{r['variant']} {r['market']}",
                         "rule": f"gap >= {r['gap>=']}, EV filter {r['ev_filter']}",
                         "bets": r["bets"], "units": r["units"], "roi": r["roi"],
                         "ci": f"{r['ci_lo']:+.1f}..{r['ci_hi']:+.1f}", "passes": bool(r["passes"]),
                         "failed bars": r["failed"] if isinstance(r["failed"], str) else ""})
    for f in ("sit_early_chosen.csv", "sit_drift_chosen.csv"):
        p = SCRATCH / f
        if p.exists():
            c = pd.read_csv(p)
            for r in c.itertuples():
                rows.append({"name": f"situational total ({r.timing})", "rule": r.rule,
                             "bets": r.bets, "units": r.units, "roi": r.roi,
                             "ci": f"{r.ci_lo:+.1f}..{r.ci_hi:+.1f}", "passes": bool(r.passes),
                             "failed bars": r.failed if isinstance(r.failed, str) else ""})
    v = pd.DataFrame(rows)
    v["role"] = np.where(v["name"].str.contains("placebo"), "control", "candidate")
    t = ["## 6. Verdicts, and units a season\n",
         "Every cell the grids chose (one per market x side family x method), graded on "
         "2021-22..2025-26 at the best bettable price. A candidate ships only if it fails no bar. "
         "Rows marked 'control' are the DraftKings-as-reference placebos: they are tests of the "
         "candidates, never candidates themselves.\n",
         md_table(v[["role"] + [c for c in v.columns if c != "role"]])]
    passing = v[v["passes"] & (v["role"] == "candidate")] if len(v) else v
    ctrl = v[v["passes"] & (v["role"] == "control")] if len(v) else v
    if len(ctrl):
        t.append("\n**A control passed too:** " + "; ".join(
            f"{r['name']} ({r['rule']}, {int(r['bets'])} bets, {r['roi']:+.2f}%)"
            for _, r in ctrl.iterrows())
            + ". Any candidate on the same market must be read against it (section 3b).\n")
    if len(passing) == 0:
        t.append("\n**No candidate clears every bar, so nothing is simulated as a live model.** "
                 "Units a season below are for reading the size of what was found, not a "
                 "proposal: graded units / 5 seasons, at one bet a game per market and the "
                 "historical fetch cadence (up to ~9 looks a game date, decided at the first "
                 "qualifying look).\n")
        top = v.sort_values("units", ascending=False).head(8).copy()
        top["units a season"] = top["units"] / len(GRADED)
        t.append(md_table(top[["name", "rule", "bets", "units", "units a season", "roi", "ci"]]))
    else:
        t.append("\nCandidates clearing every bar (units a season = graded units / 5):\n")
        p2 = passing.copy()
        p2["units a season"] = p2["units"] / len(GRADED)
        t.append(md_table(p2[["name", "rule", "bets", "units", "units a season", "roi", "ci"]]))
        t.append("\nOnly moneyline candidates clear, so 'one bet a game across all three markets' "
                 "is the same list. Per season, the stake each bet risks, and the realistic cadence "
                 "are in section 3b: the units are one unit TO WIN, so a +320 underdog risks "
                 "0.31u. The live worker looks ~6x more often than the stored snapshots; that "
                 "version of the rule was not simulated.\n")
        cand = list(SCRATCH.parent.glob("game_market_candidate_*.parquet"))
        for p in cand:
            b = pd.read_parquet(p)
            rows2 = []
            for s in ALL_SEASONS:
                z = b[b["season"] == s]
                rows2.append({"season": s, "bets": len(z), "units": z["units"].sum(),
                              "risked": z["risk"].sum(),
                              "roi": 100 * z["units"].sum() / z["risk"].sum() if len(z) else np.nan})
            t.append(f"\n`{p.name}`, units a season (2020-21 was never graded or used to choose):\n")
            t.append(md_table(pd.DataFrame(rows2)))
    txt = "\n".join(t)
    report("units", txt)
    return txt


def assemble() -> None:
    order = ["notes", "checks", "baselines", "sharp", "candidate", "gap", "situational", "units"]
    parts = []
    for k in order:
        p = SCRATCH / f"report_{k}.md"
        if p.exists():
            parts.append(p.read_text(encoding="utf-8"))
    head = ("# NBA full-game markets (moneyline, spread, total): game_market lab\n\n"
            f"Generated {time.strftime('%Y-%m-%d %H:%M')} local by `scripts/nba_game_market_lab.py` "
            "from the local parquet cache (`data/local/nba/`, nba_odds pulled "
            f"{json.loads((CACHE / 'manifest.json').read_text(encoding='utf-8'))['nba_odds']['pulled_at']}). "
            "No Odds API call, no Supabase read. Seasons are ending-year labels (2026 = 2025-26). "
            "Units: one unit to win, risk capped at 3u. Bars: docs/nba_models_2026.md section 1.\n")
    REPORT.write_text(head + "\n\n" + "\n\n".join(parts), encoding="utf-8")
    log(f"report written: {REPORT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sections", default="checks,baselines,sharp,gap,situational")
    ap.add_argument("--seasons", nargs="*", type=int, default=ALL_SEASONS)
    ap.add_argument("--placebo", type=int, default=20)
    args = ap.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    if args.sections == "assemble":
        if (SCRATCH / "sharp_grid.csv").exists():
            info = json.loads((SCRATCH / "sharp_info.json").read_text(encoding="utf-8"))
            report("sharp", sharp_report(pd.read_csv(SCRATCH / "sharp_grid.csv"),
                                         pd.read_csv(SCRATCH / "sharp_chosen.csv"),
                                         pd.read_parquet(OUT / "game_market_sharp_bets.parquet"),
                                         info))
        section_units()
        section_summary()
        assemble()
        sys.exit(0)
    t0 = time.time()
    g = load_games()
    o, st = load_lines(args.seasons)
    log(f"loaded {len(o):,} rows in {time.time() - t0:.0f}s")
    (SCRATCH / "load_stats.json").write_text(json.dumps(
        {**st, "games_priced": int(o["game_id"].nunique())}), encoding="utf-8")
    secs = args.sections.split(",")
    if "checks" in secs:
        section_checks(o, st, g)
        print(_REPORT_PARTS["checks"])
    ft = fetch_table(o)
    close = pin_close(o)
    sig, sigtab = fit_sigma(close)
    log("sigma:\n" + sigtab.to_string())
    sigtab.to_csv(SCRATCH / "sigma.csv", index=False)
    if "baselines" in secs:
        section_baselines(o, close, sig)
    if "sharp" in secs:
        x, grid, chosen, bets, info = section_sharp(o, g, ft, close, sig,
                                                     placebo_reps=args.placebo)
        log(f"sharp done: {info}")
        report("sharp", sharp_report(grid, chosen, bets, info))
        del x, bets
    if "gap" in secs:
        _REPORT_PARTS["gap_head"] = GAP_HEAD
        grid, chosen, props = section_gap(o, close, sig, ft, placebo_reps=args.placebo)
        report("gap", gap_report(grid, chosen, props, sigtab))
    if "situational" in secs:
        res = section_situational(o, g, close, sig, placebo_reps=args.placebo)
        report("situational", situational_report(*res))
    if "candidate" in secs or "sharp" in secs:
        section_candidate(o, close)
    section_units()
    section_summary()
    assemble()
