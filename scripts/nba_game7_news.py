"""Seventh NBA game-market search: the minutes after an injury report (docs/nba_models_2026.md section 11).

Section 11.2 fixes the rules, 11.3 the 26 cells and two controls, 11.4 the bars. Events come
from scripts/nba_news_window_plan.events (the definitions the purchase was planned on); prices
are the harness's quotes (scripts/nba_game_harness.load), whose fetch instants include the
5-minute news-window purchase (odds_history_fetches, why = 'news_window').

  EVENT      (game, printed report time R, s): s = implied change in the HOME margin, |s| >= 0.5.
             One bet per game, market and cell: the game's first qualifying event.
  SNAPSHOT   the feed returns the latest 5-minute snapshot AT OR BEFORE a request, 38-39 s
             past its mark (11.5): a fetch's SLOT is that mark (nba_news_window_plan.slot) and
             its SNAPSHOT TIME is the stored body timestamp (ledger snapshot_ts), else slot + 38 s.
             "R+5" is the fetch whose slot is R+5: prices as the feed saw them at about R+5:38.
  QUOTE AT X the quote a book returned in fetch X.
  FRESH      a deciding quote stamped (snapshot_at) within FRESH_MIN minutes of its fetch's
             SNAPSHOT TIME (not of the request).
  CENTRE     Pinnacle's no-vig price at its own number at a fetch: spreads -> the home margin's
             centre through the line-size shape (scripts/nba_game6_alt.game_sigma); totals ->
             the total's centre through the pooled shape; moneylines -> the home win chance.
  MOVE       centre(t) - centre(R-5).
  N1         |MOVE| >= 1 point (spreads, totals) or 0.02 (moneylines); a FRESH deciding quote at
             t identical (number and both prices) to that book's quote at R-5; bet toward the
             move at that book, priced at Pinnacle's centre at t.
  N2         |MOVE| < |s|/4 (spreads) or < 0.01 (moneylines); fair centre = Pinnacle's spread
             centre at R-5 + N2_SLOPE * s (moneylines: that margin centre's win chance); bet the
             side s favours at the best FRESH deciding price at t.
  CONTROLS   N1 quiet: the N1 rule at report times of games whose own report did not change
             by 0.5 points' worth, where the slate was bought for another game. N1 hourly: the
             N1 rule with R-5 -> the last hourly fetch at or before R-5 and t -> the first
             hourly fetch at least 30 minutes after R.
  PLACEBO    N1: each event's move direction is shuffled between events on the same date in
             the same market and offset; the fair centre becomes centre(R-5) + shuffled
             direction x |MOVE|, so a flipped event bets the stale book the other way at a price
             the shifted centre calls good. N2: s shuffled between events on the same date.
  POOL       2024-25 and 2025-26 pooled; roi_choose is the pooled return (no choosing seasons).

    PYTHONPATH=. python -m scripts.nba_game7_news --synthetic
    PYTHONPATH=. python -m scripts.nba_game7_news --full --results DIR
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_game6_alt as A  # noqa: E402

SEASONS = (2025, 2026)
OFFSETS = (5, 10, 15)                       # t = R + offset minutes
PRE_MIN = 5                                 # the pre-report fetch is R - 5
FRESH_MIN = 5
N1_MOVE = {"spreads": 1.0, "totals": 1.0, "h2h": 0.02}
N2_SLOPE = 0.47                              # 10.1: 0.375 in the window + 0.097 after (2021-22..2023-24)
N2_STILL_SPREAD_FRAC, N2_STILL_ML = 0.25, 0.01
CUTS = (0.02, 0.04)
EDGES = (0.0, 0.02, 0.04, np.inf)
PLACEBO_RUNS = 200
EXPECTED_CELLS = 26
SIDE_A = {"spreads": "home", "h2h": "home", "totals": "over"}
SIDE_B = {"spreads": "away", "h2h": "away", "totals": "under"}


# ── prices at a fetch ───────────────────────────────────────────────────────

def at_fetch(quotes: pd.DataFrame) -> pd.DataFrame:
    """One quote per (game, market, book, fetch_at): the newest stamp that fetch returned."""
    q = quotes[quotes["coherent"] & quotes["market"].isin(SIDE_A)]
    q = q.sort_values(["game_id", "market", "book", "fetch_at", "snapshot_at"])
    q = q.drop_duplicates(["game_id", "market", "book", "fetch_at"], keep="last")
    # a full-game spread or total hangs one number per book per fetch (§8.2); keep the main one
    return q.reset_index(drop=True)


def centres(q: pd.DataFrame, sig: dict, shapes: dict | None) -> pd.DataFrame:
    """Pinnacle's centre per (game, market, fetch_at): mu for spreads / totals with its sigma,
    p_home for moneylines."""
    p = q[q["book"] == H.SHARP].copy()
    ia, ib = H.imp(p["price_a"]), H.imp(p["price_b"])
    p["fa"] = ia / (ia + ib)
    p["sigma"] = pd.Series([A.game_sigma(s, m, ln, sig, shapes) if m != "h2h" else None
                            for s, m, ln in zip(p["season"], p["market"], p["line"].fillna(0.0))],
                           index=p.index, dtype=object)
    sp = p["market"] != "h2h"
    ok = sp & p["sigma"].notna()
    p["mu"] = np.nan
    if ok.any():
        x = p[ok]
        p.loc[ok, "mu"] = H.solve_any(H.threshold(x["market"], x["line"]), x["fa"].to_numpy(),
                                      x["sigma"].to_numpy())
    p["p_home"] = np.where(sp, np.nan, p["fa"])
    p["centre"] = np.where(sp, p["mu"], p["p_home"])
    return p[["game_id", "season", "market", "fetch_at", "line", "mu", "sigma", "p_home", "centre"]]


def win_chance(mu, sigma) -> np.ndarray:
    """P(home wins) for a home-margin centre, no level result: win / (win + lose) at 0."""
    out = np.full(len(mu), np.nan)
    for i, (m, s) in enumerate(zip(mu, sigma)):
        if s is None or not np.isfinite(m):
            continue
        w, _, l = H.probs_any(np.array([m]), np.array([s], dtype=object), np.array([0.0]))
        out[i] = w[0] / max(w[0] + l[0], 1e-12)
    return out


# ── the windows ─────────────────────────────────────────────────────────────

def snap_times(fetches: pd.DataFrame, ledger: pd.DataFrame | None) -> dict:
    """fetch_at -> the snapshot time it bought: the ledger's snapshot_ts, else slot + 38 s."""
    from scripts.nba_news_window_plan import slot
    out = {}
    if ledger is not None and "snapshot_ts" in ledger:
        led = ledger.dropna(subset=["snapshot_ts"])
        for r, t in zip(pd.to_datetime(led["requested_at"], utc=True),
                        pd.to_datetime(led["snapshot_ts"], utc=True, format="mixed")):
            out[r] = t
    for f in pd.to_datetime(fetches["fetch_at"].unique(), utc=True):
        out.setdefault(f, slot(f) + pd.Timedelta(seconds=38))
    return out


def slot_index(fetches: pd.DataFrame, snaps: dict | None = None) -> dict:
    """(game_id, mark) -> fetch_at: the fetch whose RETURNED snapshot sits at that 5-minute
    mark. The mark is read from the snapshot time the purchase stored (snaps: the ledger's
    snapshot_ts), so a request the feed answered with an older snapshot is filed where that
    snapshot belongs, not where it was asked for; without a stored time, the mark a request
    returns (slot). The newest request wins when two return the same snapshot."""
    from scripts.nba_news_window_plan import slot
    f = fetches.sort_values("fetch_at")
    out = {}
    for g, t in zip(f["game_id"], f["fetch_at"]):
        st = (snaps or {}).get(t)
        out[(g, pd.Timestamp(st).floor("5min") if st is not None else slot(t))] = t
    return out


def misdated_fetches(fetches: pd.DataFrame, snaps: dict) -> int:
    """Fetches whose stored snapshot is not the one their request time should return (the
    feed skipped a snapshot): reported with the grade."""
    from scripts.nba_news_window_plan import slot
    n = 0
    for t in pd.to_datetime(fetches["fetch_at"].unique(), utc=True):
        st = snaps.get(t)
        if st is not None and pd.Timestamp(st).floor("5min") != slot(t):
            n += 1
    return n

WINDOW_COLS = ["game_id", "R", "s", "season", "offset", "pre_at", "t_at", "t_snap", "r_at"]


def windows(events: pd.DataFrame, slots: dict, snaps: dict, offsets=OFFSETS,
            hourly: dict | None = None) -> pd.DataFrame:
    """(game_id, R, s, season, offset, pre_at, t_at, t_snap, r_at) per event and offset whose
    two fetches exist (pre_at, t_at: the fetches; t_snap: t's snapshot time; r_at: the fetch
    whose slot is R itself, for the before-the-report report, else NaT).

    Five-minute windows: pre = the fetch whose slot is R - 5, t = the fetch whose slot is
    R + offset, its snapshot before tip - MIN_LEAD. Hourly (the control): pre = the last
    hourly fetch whose snapshot is at or before R - 5, t = the first whose snapshot is at least
    30 minutes after R (offset -1)."""
    rows = []
    for e in events.itertuples(index=False):
        late = e.tip - pd.Timedelta(minutes=H.MIN_LEAD)
        if hourly is None:
            pre = slots.get((e.game_id, e.report_ts - pd.Timedelta(minutes=PRE_MIN)))
            if pre is None:
                continue
            r_at = slots.get((e.game_id, e.report_ts), pd.NaT)
            for k in offsets:
                t = slots.get((e.game_id, e.report_ts + pd.Timedelta(minutes=k)))
                if t is not None and snaps[t] < late:
                    rows.append((e.game_id, e.report_ts, e.s, e.season, k, pre, t, snaps[t], r_at))
        else:
            hf = hourly.get(e.game_id)
            if hf is None:
                continue
            st = np.array([snaps[pd.Timestamp(x)] for x in hf])
            before = [x for x, t in zip(hf, st) if t <= e.report_ts - pd.Timedelta(minutes=PRE_MIN)]
            after = [(x, t) for x, t in zip(hf, st) if t >= e.report_ts + pd.Timedelta(minutes=30)]
            if before and after and after[0][1] < late:
                rows.append((e.game_id, e.report_ts, e.s, e.season, -1, pd.Timestamp(before[-1]),
                             pd.Timestamp(after[0][0]), after[0][1], pd.NaT))
    return pd.DataFrame(rows, columns=WINDOW_COLS)


def n1_candidates(win: pd.DataFrame, q: pd.DataFrame, cen: pd.DataFrame) -> pd.DataFrame:
    """N1 offers: a fresh deciding quote at t identical to its quote at R-5, toward Pinnacle's
    move, priced at Pinnacle's centre at t."""
    c = cen.set_index(["game_id", "market", "fetch_at"])
    out = []
    for market in SIDE_A:
        w = win.copy()
        w["market"] = market
        k0 = list(zip(w["game_id"], w["market"], w["pre_at"]))
        k1 = list(zip(w["game_id"], w["market"], w["t_at"]))
        w["c0"] = [c["centre"].get(k, np.nan) for k in k0]
        w["c1"] = [c["centre"].get(k, np.nan) for k in k1]
        w["mu"] = [c["mu"].get(k, np.nan) for k in k1]
        w["sigma"] = [c["sigma"].get(k) for k in k1]
        w["p_home"] = [c["p_home"].get(k, np.nan) for k in k1]
        w["sigma1"] = w["sigma"]
        w["move"] = w["c1"] - w["c0"]
        w = w[w["move"].abs() >= N1_MOVE[market] - 1e-12]
        if w.empty:
            continue
        w["side"] = np.where(w["move"] > 0, SIDE_A[market], SIDE_B[market])
        qm = q[(q["market"] == market) & q["book"].isin(H.BETTABLE)]
        q0 = qm.rename(columns={"fetch_at": "pre_at", "line": "line0", "price_a": "pa0", "price_b": "pb0"})[
            ["game_id", "book", "pre_at", "line0", "pa0", "pb0"]]
        q1 = qm.rename(columns={"fetch_at": "t_at"})
        x = w.merge(q1, on=["game_id", "market", "t_at"], suffixes=("", "_q")).merge(
            q0, on=["game_id", "book", "pre_at"])
        same = (np.isclose(x["line"].fillna(-999), x["line0"].fillna(-999))
                & np.isclose(x["price_a"], x["pa0"]) & np.isclose(x["price_b"], x["pb0"]))
        fresh = x["snapshot_at"] >= x["t_snap"] - pd.Timedelta(minutes=FRESH_MIN)
        x = x[same & fresh]
        if x.empty:
            continue
        x = x.assign(price=np.where(x["side"] == SIDE_A[market], x["price_a"], x["price_b"]))
        out.append(x)
    if not out:
        return pd.DataFrame()
    x = pd.concat(out, ignore_index=True)
    pw, pp = H.side_probs(x["market"].to_numpy(), x["side"].to_numpy(), x["line"].to_numpy(),
                          mu=x["mu"].to_numpy(float), sigma=x["sigma"].to_numpy(),
                          p_home=x["p_home"].to_numpy(float))
    x = H.with_ev(x.assign(p_win=pw, p_push=pp))
    return x.assign(T=x["t_at"])


def n2_candidates(win: pd.DataFrame, q: pd.DataFrame, cen: pd.DataFrame, s_col: str = "s") -> pd.DataFrame:
    """N2 offers: the market has not moved; fair centre = Pinnacle's spread centre at R-5 +
    N2_SLOPE * s; bet the side s favours at every fresh deciding quote at t."""
    c = cen.set_index(["game_id", "market", "fetch_at"])
    w = win.copy()
    sk0 = list(zip(w["game_id"], ["spreads"] * len(w), w["pre_at"]))
    sk1 = list(zip(w["game_id"], ["spreads"] * len(w), w["t_at"]))
    mk0 = list(zip(w["game_id"], ["h2h"] * len(w), w["pre_at"]))
    mk1 = list(zip(w["game_id"], ["h2h"] * len(w), w["t_at"]))
    w["mu0"] = [c["mu"].get(k, np.nan) for k in sk0]
    w["sigma"] = [c["sigma"].get(k) for k in sk0]
    w["sp_move"] = np.array([c["centre"].get(k, np.nan) for k in sk1]) - w["mu0"].to_numpy()
    w["ml_move"] = (np.array([c["centre"].get(k, np.nan) for k in mk1])
                    - np.array([c["centre"].get(k, np.nan) for k in mk0]))
    w["mu"] = w["mu0"] + N2_SLOPE * w[s_col]
    w = w[w["mu"].notna() & w["sigma"].notna() & (w[s_col] != 0)]
    out = []
    for market in ("spreads", "h2h"):
        if market == "spreads":
            still = w["sp_move"].abs() < N2_STILL_SPREAD_FRAC * w[s_col].abs()
        else:
            still = w["ml_move"].abs() < N2_STILL_ML
        ww = w[still.fillna(False)].assign(market=market)
        if ww.empty:
            continue
        ww["side"] = np.where(ww[s_col] > 0, "home", "away")
        if market == "h2h":
            ww["p_home"] = win_chance(ww["mu"].to_numpy(float), ww["sigma"].to_numpy())
        else:
            ww["p_home"] = np.nan
        qm = q[(q["market"] == market) & q["book"].isin(H.BETTABLE)].rename(columns={"fetch_at": "t_at"})
        x = ww.merge(qm, on=["game_id", "market", "t_at"], suffixes=("", "_q"))
        x = x[x["snapshot_at"] >= x["t_snap"] - pd.Timedelta(minutes=FRESH_MIN)]
        x = x.assign(price=np.where(x["side"] == "home", x["price_a"], x["price_b"]))
        out.append(x)
    if not out:
        return pd.DataFrame()
    x = pd.concat(out, ignore_index=True)
    pw, pp = H.side_probs(x["market"].to_numpy(), x["side"].to_numpy(), x["line"].to_numpy(),
                          mu=x["mu"].to_numpy(float), sigma=x["sigma"].to_numpy(),
                          p_home=x["p_home"].to_numpy(float))
    x = H.with_ev(x.assign(p_win=pw, p_push=pp))
    return x.assign(T=x["t_at"])


# ── choosing and grading ────────────────────────────────────────────────────

def choose_first_event(cand: pd.DataFrame, cut: float, books=H.BETTABLE) -> pd.DataFrame:
    """One bet per (game, market): the earliest qualifying event, its best-EV offer."""
    if cand.empty:
        return cand
    c = cand[cand["book"].isin(books) & (cand["price"] >= H.PRICE_FLOOR) & (cand["ev"] >= cut)]
    c = c.assign(_r=c["book"].map(H.BOOK_RANK).fillna(99))
    c = c.sort_values(["game_id", "market", "R", "ev", "_r"], ascending=[True, True, True, False, True])
    first = c.drop_duplicates(["game_id", "market"])
    return first.drop(columns="_r").reset_index(drop=True)


def pooled(g: pd.DataFrame) -> dict:
    if not len(g):
        return {"pool_n": 0, "pool_units": 0.0, "pool_roi": np.nan, "pool_ci95_lo": np.nan,
                "pool_ci95_hi": np.nan, "pool_seasons_counted": 0, "pool_seasons_positive": 0}
    lo, hi = H.ci95(g)
    counted = positive = 0
    out = {}
    for s in SEASONS:
        gs = g[g["season"] == s]
        out[f"n_{s}"], out[f"roi_{s}"] = int(len(gs)), (H.roi(gs) if len(gs) else np.nan)
        if len(gs) >= 30:
            counted += 1
            positive += int(H.roi(gs) > 0)
    return {"pool_n": int(len(g)), "pool_units": float(g["units"].sum()), "pool_roi": H.roi(g),
            "pool_ci95_lo": lo, "pool_ci95_hi": hi, "pool_seasons_counted": counted,
            "pool_seasons_positive": positive, **out}


def bands(cand: pd.DataFrame, k: int, games: pd.DataFrame) -> dict:
    out = {}
    for slot, lo_i in enumerate(range(k, len(EDGES) - 1)):
        lo, hi = EDGES[lo_i], EDGES[lo_i + 1]
        if cand.empty:
            out[f"band{slot}_lo"], out[f"band{slot}_n"], out[f"band{slot}_roi"] = lo, 0, np.nan
            continue
        at_lo = choose_first_event(cand, lo)
        at_hi = choose_first_event(cand, hi) if np.isfinite(hi) else at_lo.iloc[0:0]
        keys = set(zip(at_hi["game_id"], at_hi["market"]))
        b = at_lo[[x not in keys for x in zip(at_lo["game_id"], at_lo["market"])]] if len(at_lo) else at_lo
        g = H.grade(b, games) if len(b) else b
        out[f"band{slot}_lo"], out[f"band{slot}_n"] = lo, int(len(g))
        out[f"band{slot}_roi"] = H.roi(g) if len(g) else np.nan
    return out


def blinds(win: pd.DataFrame, q: pd.DataFrame, market: str, games: pd.DataFrame, cen: pd.DataFrame) -> dict:
    """The blind bet on each real side (the house standard's, H.blind_pool): every window in
    the cell's population (its first window per game) with a Pinnacle centre at t, the best
    fresh deciding offer on that side under Pinnacle's centre at t, no cut."""
    w = win.sort_values("R").drop_duplicates("game_id").assign(market=market)
    c = cen[cen["market"] == market].rename(columns={"fetch_at": "t_at"})[
        ["game_id", "market", "t_at", "mu", "sigma", "p_home"]]
    w = w.merge(c, on=["game_id", "market", "t_at"])
    w = w[w["mu"].notna() | w["p_home"].notna()]
    qm = q[(q["market"] == market) & q["book"].isin(H.BETTABLE)].rename(columns={"fetch_at": "t_at"})
    x = w.merge(qm, on=["game_id", "market", "t_at"], suffixes=("", "_q"))
    x = x[x["snapshot_at"] >= x["t_snap"] - pd.Timedelta(minutes=FRESH_MIN)]
    out = {}
    if x.empty:
        return out
    off = pd.concat([x.assign(side=SIDE_A[market], price=x["price_a"]),
                     x.assign(side=SIDE_B[market], price=x["price_b"])], ignore_index=True)
    pw, pp = H.side_probs(off["market"].to_numpy(), off["side"].to_numpy(), off["line"].to_numpy(),
                          mu=off["mu"].to_numpy(float), sigma=off["sigma"].to_numpy(),
                          p_home=off["p_home"].to_numpy(float))
    off = H.with_ev(off.assign(p_win=pw, p_push=pp))
    for side in (SIDE_A[market], SIDE_B[market]):
        g = H.grade(H.choose(off, -np.inf, sides=[side]), games)
        if len(g):
            out[f"blind_pool_{side}"] = H.roi(g)
    return out


def shuffle_col(df: pd.DataFrame, col: str, run: int, by=("date", "market")) -> pd.DataFrame:
    rng = np.random.default_rng(run)
    d = df.copy()
    for _, idx in d.groupby(list(by)).groups.items():
        idx = np.asarray(list(idx))
        if len(idx) > 1:
            d.loc[idx, col] = d.loc[rng.permutation(idx), col].to_numpy()
    return d


def n1_placebo(cand: pd.DataFrame, run: int) -> pd.DataFrame:
    """11.4's placebo for N1. Each event's move direction (per game, market, report and
    offset) is shuffled between events on the same date in the same market and offset. The
    fair centre at t becomes centre(R-5) + shuffled direction x |MOVE| (the move's own size),
    and every stale offer bets toward the SHUFFLED move at its own book and number, priced at
    that shifted centre. An event whose direction did not flip is the real bet; one that did
    flip bets the stale book the other way, at a price the shifted centre calls good."""
    if cand.empty:
        return cand
    key = ["game_id", "market", "R", "offset"]
    c = cand.assign(date=cand["R"].dt.strftime("%Y-%m-%d"), dir=np.sign(cand["move"]))
    ev_dir = c.drop_duplicates(key)[key + ["date", "dir"]]
    ev_dir = shuffle_col(ev_dir, "dir", run, by=("date", "market", "offset"))
    c = c.drop(columns="dir").merge(ev_dir[key + ["dir"]], on=key)
    centre = c["c0"] + c["dir"] * c["move"].abs()
    ml = c["market"] == "h2h"
    c = c.assign(mu=np.where(ml, np.nan, centre),
                 p_home=np.where(ml, np.clip(centre, 0.005, 0.995), np.nan),
                 side=np.where(c["dir"] > 0, c["market"].map(SIDE_A), c["market"].map(SIDE_B)))
    c = c.assign(price=np.where(c["side"] == c["market"].map(SIDE_A), c["price_a"], c["price_b"]))
    pw, pp = H.side_probs(c["market"].to_numpy(), c["side"].to_numpy(), c["line"].to_numpy(),
                          mu=c["mu"].to_numpy(float), sigma=c["sigma"].to_numpy(),
                          p_home=c["p_home"].to_numpy(float))
    return H.with_ev(c.drop(columns=["ev", "p_win", "p_push"]).assign(p_win=pw, p_push=pp))


def clv_any(g: pd.DataFrame, close, sig, shapes) -> pd.Series:
    """Closing value of each bet at Pinnacle's last pre-tip no-vig price: spreads and totals
    through the shape their closing number selects (nba_game6_alt.clv_shaped), moneylines at
    the closing no-vig win chance directly."""
    out = pd.Series(np.nan, index=g.index)
    if close is None or not len(g):
        return out
    st = g[g["market"] != "h2h"]
    if len(st):
        out.loc[st.index] = A.clv_shaped(st, close, sig, shapes)
    ml = g[g["market"] == "h2h"]
    if len(ml):
        x = ml.reset_index().merge(close[close["market"] == "h2h"].drop(columns="season"),
                                   on=["game_id", "market"], how="left")
        x = x[(x["close_at"] > x["T"]) & x["close_fa"].notna()]
        pw = np.where(x["side"] == "home", x["close_fa"], 1 - x["close_fa"])
        ev = pw * (H.dec(x["price"]) - 1.0) - (1.0 - pw)
        out.loc[x["index"].to_numpy()] = ev
    return out


def before_report_share(cand: pd.DataFrame, cen: pd.DataFrame) -> float:
    """11.4: the share of Pinnacle's move (R-5 to t) already made at the snapshot of R itself,
    over the events a cell bet on: sum of (centre(R) - centre(R-5)) toward the move over the
    sum of |move|."""
    if cand.empty:
        return np.nan
    e = cand.drop_duplicates(["game_id", "market", "R", "offset"])
    e = e[e["r_at"].notna()]
    if e.empty:
        return np.nan
    c = cen.set_index(["game_id", "market", "fetch_at"])["centre"]
    cr = np.array([c.get(k, np.nan) for k in zip(e["game_id"], e["market"], e["r_at"])])
    ok = np.isfinite(cr)
    if not ok.any():
        return np.nan
    toward = (cr[ok] - e["c0"].to_numpy()[ok]) * np.sign(e["move"].to_numpy()[ok])
    return float(toward.sum() / e["move"].abs().to_numpy()[ok].sum())


def stale_minutes(bets: pd.DataFrame, q: pd.DataFrame, slots: dict) -> tuple[float, int]:
    """11.4: minutes after R until each bet's stale book first showed a different quote, at the
    5-minute slots after its decision up to R + 25 (median, and how many never moved there)."""
    if not len(bets):
        return np.nan, 0
    qq = q.set_index(["game_id", "market", "book", "fetch_at"])
    mins, never = [], 0
    for b in bets.itertuples(index=False):
        moved = None
        for k in range(int(b.offset) + 5, 30, 5):
            f = slots.get((b.game_id, b.R + pd.Timedelta(minutes=k)))
            if f is None:
                continue
            try:
                r = qq.loc[(b.game_id, b.market, b.book, f)]
            except KeyError:
                continue
            r = r.iloc[-1] if isinstance(r, pd.DataFrame) else r
            if not (np.isclose(r["line"] if pd.notna(r["line"]) else -999, b.line0 if pd.notna(b.line0) else -999)
                    and np.isclose(r["price_a"], b.pa0) and np.isclose(r["price_b"], b.pb0)):
                moved = k
                break
        if moved is None:
            never += 1
        else:
            mins.append(moved)
    return (float(np.median(mins)) if mins else np.nan), never


def cell_rows(family: str, cand: pd.DataFrame, win: pd.DataFrame, q: pd.DataFrame, games: pd.DataFrame,
              cen: pd.DataFrame, close, sig, shapes, placebos: list, markets, offsets,
              slots: dict | None = None) -> tuple[list[dict], list]:
    rows, bets = [], []
    for market in markets:
        for off in offsets:
            cm = cand[(cand["market"] == market) & (cand["offset"] == off)] if len(cand) else cand
            wm = win[win["offset"] == off]
            bl = blinds(wm, q, market, games, cen)
            for k, cut in enumerate(CUTS):
                b = choose_first_event(cm, cut)
                g = H.grade(b, games) if len(b) else b
                row = {"family": family, "point": f"R+{off}" if off >= 0 else "hourly", "market": market,
                       "side": "toward" if family.startswith("N1") or family.startswith("control_N1") else "news",
                       "cut_index": k, "cut": cut, "population_games": int(wm["game_id"].nunique()),
                       **pooled(g), **bl, **bands(cm, k, games)}
                if len(g):
                    sp = g[H.kind(g["market"]) != "total"]
                    if len(sp):
                        row["pool_share_home"] = float((sp["side"] == "home").mean())
                    tt = g[H.kind(g["market"]) == "total"]
                    if len(tt):
                        row["pool_share_over"] = float((tt["side"] == "over").mean())
                    row["dk_roi"] = (lambda d: H.roi(d) if len(d) else np.nan)(
                        H.grade(choose_first_event(cm, cut, books=(H.DK,)), games)
                        if len(choose_first_event(cm, cut, books=(H.DK,))) else pd.DataFrame())
                    if close is not None:
                        ev = clv_any(g, close, sig, shapes)
                        row["clv_n"] = int(ev.notna().sum())
                        row["clv_median"] = float(np.nanmedian(ev)) if ev.notna().any() else np.nan
                        row["clv_mean"] = float(np.nanmean(ev)) if ev.notna().any() else np.nan
                    if "c0" in cm:
                        row["pin_share_before_R"] = before_report_share(b, cen)
                        if slots is not None and "pa0" in b:
                            row["stale_minutes_median"], row["stale_never_moved"] = stale_minutes(b, q, slots)
                    bets.append(g.assign(family=family, cut=cut))
                row["roi_choose"] = row["pool_roi"]
                pl = []
                for pc in placebos:
                    pm = pc[(pc["market"] == market) & (pc["offset"] == off)] if len(pc) else pc
                    gp = H.grade(choose_first_event(pm, cut), games) if len(pm) and len(choose_first_event(pm, cut)) else pd.DataFrame()
                    pl.append(H.roi(gp) if len(gp) else np.nan)
                row["placebo_rois"] = pl
                rows.append(row)
    return rows, bets


# ── the run ─────────────────────────────────────────────────────────────────

def hourly_fetches(data: H.Data, ledger: pd.DataFrame | None) -> dict | None:
    """game_id -> sorted fetch instants that are NOT news-window purchases (the archive every
    earlier search had)."""
    if ledger is None:
        return None
    led = ledger.copy()
    led["requested_at"] = pd.to_datetime(led["requested_at"], utc=True)
    news = set(led.loc[led["why"].astype(str) == H.NEWS_WINDOW_WHY, "requested_at"])
    f = data.fetches[~data.fetches["fetch_at"].isin(news)]
    return {g: np.sort(x["fetch_at"].to_numpy()) for g, x in f.groupby("game_id")}


def run(data: H.Data, events: pd.DataFrame, quiet: pd.DataFrame, sig: dict, shapes: dict | None,
        ledger: pd.DataFrame | None, runs: int = PLACEBO_RUNS) -> tuple[pd.DataFrame, pd.DataFrame]:
    games = data.games
    q = at_fetch(data.quotes)
    cen = centres(q, sig, shapes)
    close = H.pinnacle_close(data) if len(data.quotes) else None
    snaps = snap_times(data.fetches, ledger)
    slots = slot_index(data.fetches, snaps)
    print(f"  fetches whose snapshot is not the one their request should return: "
          f"{misdated_fetches(data.fetches, snaps)}", flush=True)
    win = windows(events, slots, snaps)
    rows, bets = [], []
    c1 = n1_candidates(win, q, cen)
    pl1 = [n1_placebo(c1, r) for r in range(1, runs + 1)] if len(c1) else [pd.DataFrame()] * runs
    r, b = cell_rows("N1", c1, win, q, games, cen, close, sig, shapes, pl1, ("spreads", "totals", "h2h"),
                     OFFSETS, slots=slots)
    rows += r; bets += b
    c2 = n2_candidates(win, q, cen)
    pl2 = []
    for run_ in range(1, runs + 1):
        ws = shuffle_col(win.assign(date=win["R"].dt.strftime("%Y-%m-%d"), market="all"), "s", run_)
        pl2.append(n2_candidates(ws, q, cen))
    r, b = cell_rows("N2", c2, win, q, games, cen, close, sig, shapes, pl2, ("spreads", "h2h"), OFFSETS[:2])
    rows += r; bets += b
    if quiet is not None and len(quiet):
        wq = windows(quiet, slots, snaps)
        r, _ = cell_rows("control_N1_quiet", n1_candidates(wq, q, cen), wq, q, games, cen, close, sig, shapes,
                         [], ("spreads", "totals", "h2h"), OFFSETS, slots=slots)
        rows += r
    hourly = hourly_fetches(data, ledger)
    if hourly is not None:
        wh = windows(events, slots, snaps, hourly=hourly)
        r, _ = cell_rows("control_N1_hourly", n1_candidates(wh, q, cen), wh, q, games, cen, close, sig, shapes,
                         [], ("spreads", "totals", "h2h"), (-1,))
        rows += r
    cells = pd.DataFrame(rows)
    cand = cells[~cells["family"].astype(str).str.startswith("control_")]
    assert len(cand) == EXPECTED_CELLS, (len(cand), EXPECTED_CELLS)
    return cells, (pd.concat(bets, ignore_index=True) if bets else pd.DataFrame())


def quiet_reports(ir: pd.DataFrame, adv: pd.DataFrame, games: pd.DataFrame) -> pd.DataFrame:
    """Report times of games whose own report changed by less than the event bar (control)."""
    from scripts import nba_news_window_plan as P
    tc = P.team_changes(ir, P.player_minutes(adv), games)
    g = games.set_index("game_id")
    home = tc["team"].to_numpy() == g.loc[tc["game_id"], "home_team"].to_numpy()
    tc["s"] = np.where(home, 1.0, -1.0) * tc["d_min"] * P.K_PTS_PER_MIN
    tc["abs_team"] = tc["s"].abs()
    e = tc.groupby(["game_id", "report_ts"]).agg(s=("s", "sum"), team_max=("abs_team", "max")).reset_index()
    e["tip"] = e["game_id"].map(g["tip"])
    e["season"] = e["game_id"].map(g["season"]).astype(int)
    # 11.3: NEITHER team's expected minutes changed by 0.5 points' worth (not the net of both)
    keep = (e["team_max"] < P.MIN_MOVE) & (e["report_ts"] < e["tip"] - pd.Timedelta(minutes=30))
    return e[keep].reset_index(drop=True)


# ── synthetic world ─────────────────────────────────────────────────────────

def synthetic_world(seed: int = 4, n_days: int = 260, per_day: int = 4, soft_lag_min: int = 20):
    """Games whose home margin ~ N(mu1, 13). A report at R moves the fair centre from mu0 to
    mu1 = mu0 + s. Pinnacle moves at R; 'draftkings' keeps its pre-report quote until
    R + soft_lag_min, then moves; 'fanduel' moves with Pinnacle. Fetches every 5 minutes
    R-5 .. R+25. Returns (Data, events, sig)."""
    from math import erf, sqrt
    rng = np.random.default_rng(seed)
    cdf = lambda z: 0.5 * (1 + erf(z / sqrt(2)))
    games, quotes, fetches, events = [], [], [], []
    day0 = pd.Timestamp("2024-11-01T22:30:00Z")

    def am(p):
        p = min(max(p, 0.02), 0.98)
        return -100 * p / (1 - p) if p >= 0.5 else 100 * (1 - p) / p

    def quote(gid, season, gd, tip, book, at, mu, hold, line=None):
        line = -np.round(mu * 2) / 2 if line is None else line
        p_home = 1 - cdf((-line - mu) / 13.0)
        quotes.append({"game_id": gid, "season": season, "game_date": gd, "tip": tip, "market": "spreads",
                       "book": book, "snapshot_at": at - pd.Timedelta(seconds=30), "fetch_at": at, "line": float(line),
                       "price_a": am(p_home * (1 + hold / 2)), "price_b": am((1 - p_home) * (1 + hold / 2)),
                       "coherent": True})
    for d in range(n_days):
        season = 2025 if d < n_days / 2 else 2026
        for j in range(per_day):
            gid = f"SYN_{d:03d}_{j}"
            R = day0 + pd.Timedelta(days=d, minutes=5 * j)
            tip = R + pd.Timedelta(hours=2)
            mu0 = float(rng.normal(0, 5))
            small = rng.random() < 0.2              # news worth less than N1's 1-point bar
            s = float(rng.choice([-1, 1]) * (rng.uniform(0.2, 0.8) if small else rng.uniform(1.5, 4.0)))
            mu1 = mu0 + s
            margin = int(np.round(rng.normal(mu1, 13.0))) or 1
            gd = str(R.date())
            games.append({"game_id": gid, "season": season, "game_date": gd, "tip": tip, "home_team": "H",
                          "away_team": "A", "home_score": 110 + max(margin, 0), "away_score": 110 - min(margin, 0)})
            events.append({"game_id": gid, "report_ts": R, "s": s, "tip": tip, "season": season,
                           "small": small})
            for k in range(-5, 30, 5):
                # requested one minute past the mark: the snapshot it returns is the mark's
                at = R + pd.Timedelta(minutes=k + 1)
                fetches.append({"game_id": gid, "tip": tip, "fetch_at": at,
                                "lead_min": (tip - at).total_seconds() / 60})
                quote(gid, season, gd, tip, "pinnacle", at, mu0 if k < 0 else mu1, 0.02)
                quote(gid, season, gd, tip, "fanduel", at, mu0 if k < 0 else mu1, 0.045)
                quote(gid, season, gd, tip, "draftkings", at, mu0 if k < soft_lag_min else mu1, 0.045)
                # betmgm keeps its pre-report NUMBER but re-prices with the news: it has moved
                quote(gid, season, gd, tip, "betmgm", at, mu0 if k < 0 else mu1, 0.045,
                      line=-np.round(mu0 * 2) / 2)
    g = pd.DataFrame(games)
    g["home_score"] = g["home_score"].astype(float)
    g["away_score"] = (g["home_score"] - pd.Series([0] * len(g))).astype(float)
    # rebuild away score from the stored margin
    g["away_score"] = [110 - min(int(np.round(x)), 0) for x in (g["home_score"] - 110)]
    data = H.Data(games=pd.DataFrame(games), quotes=pd.DataFrame(quotes), fetches=pd.DataFrame(fetches))
    data.games["home_score"] = data.games["home_score"].astype(float)
    data.games["away_score"] = data.games["away_score"].astype(float)
    dist = H.ResidDist(rng.normal(0, 13.0, 6000), "synthetic spreads")
    sig = {(s, "spreads"): dist for s in SEASONS}
    return data, pd.DataFrame(events), sig


def synthetic_checks() -> None:
    data, ev, sig = synthetic_world()
    q = at_fetch(data.quotes)
    cen = centres(q, sig, None)
    win = windows(ev, slot_index(data.fetches, snap_times(data.fetches, None)), snap_times(data.fetches, None))
    c1 = n1_candidates(win, q, cen)
    assert len(c1) and set(c1["book"]) == {"draftkings"}, "only the lagging book is ever stale"
    small_ids = set(ev.loc[ev["small"], "game_id"])
    assert small_ids and not set(c1["game_id"]) & small_ids, "N1 fired on a move below its bar"
    for off in (5, 10, 15):
        b = choose_first_event(c1[c1["offset"] == off], 0.02)
        g = H.grade(b, data.games)
        print(f"  synthetic N1 R+{off}: {len(g)} bets ROI {H.roi(g):+.3f}")
        assert len(g) > 300 and H.roi(g) > 0.03, "a planted stale book was not found or did not pay"
        # every bet goes toward the move: home when the centre rose
        assert ((g["s"] > 0) == (g["side"] == "home")).all(), "N1 bet against the move"
    assert c1[c1["offset"] >= 20].empty, "the book had moved by R+20 and is not stale there"
    # no stale book at all when every book moves with Pinnacle
    data2, ev2, sig2 = synthetic_world(soft_lag_min=0)
    q2 = at_fetch(data2.quotes)
    c2 = n1_candidates(windows(ev2, slot_index(data2.fetches, snap_times(data2.fetches, None)),
                               snap_times(data2.fetches, None)), q2,
                       centres(q2, sig2, None))
    assert c2.empty, "books that moved with Pinnacle were read as stale"
    # N2 never fires once the market has moved, and bets the side the news favours when it has not
    n2 = n2_candidates(win, q, cen)
    assert n2.empty, "N2 fired after Pinnacle had moved"
    pre = win.copy()
    pre["t_at"] = pre["pre_at"]                  # read the pre-report fetch as t: nobody has moved
    pre["t_snap"] = pre["pre_at"].map(snap_times(data.fetches, None))
    n2b = n2_candidates(pre, q, cen)
    assert len(n2b) and ((n2b["s"] > 0) == (n2b["side"] == "home")).all(), "N2 bet against the news"
    assert n2b["ev"].median() > 0.02, "N2's fair line does not lean the way the news points"
    # a stale book whose feed stamp is older than FRESH_MIN is not read as unmoved
    old_q = data.quotes.copy()
    dk = old_q["book"].eq("draftkings")
    old_q.loc[dk, "snapshot_at"] = old_q.loc[dk, "fetch_at"] - pd.Timedelta(minutes=FRESH_MIN + 2)
    q3 = at_fetch(old_q)
    assert n1_candidates(win, q3, centres(q3, sig, None)).empty, "an old feed stamp was read as a live quote"
    # the whole run builds every registered cell (two placebo runs, to exercise the path)
    cells, _ = run(data, ev, None, sig, None, None, runs=40)
    assert len(cells) == EXPECTED_CELLS and cells["placebo_rois"].map(len).eq(40).all()
    best = cells[(cells["family"] == "N1") & (cells["market"] == "spreads")]
    assert (best["pool_roi"] > 0).all() and (best["pool_n"] > 300).all(), "the run lost the planted edge"
    # the placebo is a null, not a copy of the real bets: the planted edge clears its 95th percentile
    p95 = best["placebo_rois"].map(lambda v: np.nanpercentile(np.nan_to_num(np.array(v, float), nan=0.0), 95))
    assert (best["pool_roi"] > p95).all(), f"the planted edge did not beat its placebo: {list(zip(best['pool_roi'], p95))}"
    # the stale book moved at R + soft_lag_min = 20
    assert (best["stale_minutes_median"] == 20).all(), list(best["stale_minutes_median"])
    print("synthetic checks pass")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--synthetic", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--results", type=Path)
    ap.add_argument("--runs", type=int, default=PLACEBO_RUNS)
    a = ap.parse_args()
    if a.synthetic:
        synthetic_checks()
        return
    if a.full:
        if a.results is None:
            ap.error("--full needs --results DIR")
        synthetic_checks()
        from scripts import nba_news_window_plan as P
        data = H.load(require_seasons=SEASONS, include_news_windows=True)
        g_all = H.load(seasons=tuple(range(2021, 2027)))
        close_all = H.pinnacle_close(g_all)
        sig = dict(H.close_dist(close_all, g_all.games))
        shapes = {"spreads": A.spread_shapes(close_all, g_all.games, seasons=SEASONS)}
        ledger = pd.read_parquet(H.CACHE / "nba_fetch_ledger.parquet")
        if not (ledger["why"].astype(str) == "news_window").any():
            raise SystemExit("the cache holds no news-window fetches: refresh it after the purchase")
        g, ir, adv, _ = P.load_cache(H.CACHE, SEASONS)
        ev = P.events(ir, adv, g)
        quiet = quiet_reports(ir, adv, g)
        if "snapshot_ts" not in ledger:
            raise SystemExit("the cache's ledger has no snapshot_ts: refresh it with scripts.nba_research_cache")
        cells, bets = run(data, ev, quiet, sig, shapes, ledger, runs=a.runs)
        a.results.mkdir(parents=True, exist_ok=True)
        cells.to_parquet(a.results / "cells_N.parquet")
        if len(bets):
            bets.to_parquet(a.results / "bets_N.parquet")
        print(f"wrote {len(cells)} rows to {a.results}")
        return
    ap.error("give --synthetic or --full")


if __name__ == "__main__":
    main()
