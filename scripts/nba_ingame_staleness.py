"""Step 0 of the in-game search: the staleness gate (docs/nba_models_2026.md 7.1).

THE QUESTION (7.1, as pre-registered): do points scored in the 60-120 seconds
before a quote's stamp predict that quote's result, against Pinnacle's live
no-vig price? If they do, a quote is used only when no point was scored since
the book's last update, and only when Pinnacle quoted within 60 seconds of it.

HOW "PREDICT" IS SCORED (fixed 2026-10-17, before this script was first run):

  ROWS       quotes_state.parquet (scripts/nba_ingame_data.py): in-play quotes
             by the play-by-play clock, every season 2020-21 -> 2025-26, with a
             coherent two-way price and a coherent Pinnacle quote on the same
             game and market in the same fetch, stamped within 60 s.
  y          side A (home / over) wins at the quote's own number, settled on
             the full-game score, overtime included; pushes are left out.
  p          Pinnacle's no-vig probability for side A (proportional). For
             spreads and totals p is a fair price only at Pinnacle's own
             number, so a quote at another number is left out (counted).
  x          points scored in (stamp - 120 s, stamp - 60 s] by the ESPN
             wallclock: home minus away for the moneyline and spread, both
             teams together for the total. A positive x favours side A.
  STATISTIC  the slope of (y - p) on x, with an intercept, per market and
             pooled over the three; a whole-day bootstrap 95% interval (4,000
             resamples, seed 7: the harness's convention).
  PANELS     1 (the pre-registered test): every book's quote, Pinnacle's own
             included, against Pinnacle's no-vig. 2: Pinnacle's own quotes
             only. 3: the 8 deciding books only. 4: the 8 deciding books
             against their OWN no-vig (a stale soft book is invisible against
             a fresh Pinnacle); the number need not match Pinnacle's there.
  DECISION   the freshness rule is imposed when ANY panel's interval, in any
             market or pooled, lies wholly ABOVE zero (recent scoring the price
             has not absorbed). Decided on all six seasons pooled; each season
             is reported beside. An interval wholly below zero is recorded as
             over-reaction, which is not staleness, and imposes nothing.
  THE RULE   when imposed, it applies to every in-game family and to both the
             deciding quote and the Pinnacle quote it is measured against: no
             point scored between the quote's stamp and the moment the feed
             served it (`served_at`), and Pinnacle stamped within 60 s.

DIAGNOSTICS (reported, never the gate): the same slope for points in other
windows around the stamp -- the lag profile, which also checks the clock
mapping -- and the coverage per season and decision window after the rule.

    PYTHONPATH=. python -m scripts.nba_ingame_staleness
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts import nba_game_harness as H  # noqa: E402
from scripts.nba_game_market_lab import settle  # noqa: E402
from scripts.nba_ingame_data import OUT, TIMELINE  # noqa: E402

WINDOW = (120, 60)                 # seconds before the stamp: (start, end]
N_BOOT, SEED = H.N_BOOT, H.SEED
DECIDING = set(H.BETTABLE)


def signed_points(market: pd.Series, dh: pd.Series, da: pd.Series) -> np.ndarray:
    """Points toward side A: home minus away (h2h, spreads), both (totals)."""
    return np.where(market.to_numpy() == "totals", (dh + da).to_numpy(), (dh - da).to_numpy())


def outcome(q: pd.DataFrame) -> pd.Series:
    """1 when side A wins at the quote's number, 0 when it loses, NaN on a push."""
    side = np.where(q["market"] == "totals", "over", "home")
    r = settle(q["market"].to_numpy(), side, q["line"].to_numpy(),
               q["final_home"].to_numpy(), q["final_away"].to_numpy())
    return pd.Series(np.where(r == "W", 1.0, np.where(r == "L", 0.0, np.nan)), index=q.index)


def day_sums(df: pd.DataFrame, x: str, r: str) -> pd.DataFrame:
    d = df.assign(_xr=df[x] * df[r], _xx=df[x] ** 2)
    return d.groupby("game_date").agg(n=(x, "size"), sx=(x, "sum"), sr=(r, "sum"),
                                      sxr=("_xr", "sum"), sxx=("_xx", "sum"))


def slope_from(s) -> np.ndarray:
    n, sx, sr, sxr, sxx = (np.asarray(s[k], float) for k in ("n", "sx", "sr", "sxr", "sxx"))
    den = n * sxx - sx * sx
    return np.where(den > 0, (n * sxr - sx * sr) / np.where(den > 0, den, 1), np.nan)


def slope_ci(df: pd.DataFrame, x: str = "x", r: str = "resid", n_boot: int = N_BOOT,
             seed: int = SEED) -> dict:
    """OLS slope of r on x with an intercept, and its whole-day bootstrap 95% interval."""
    if len(df) < 30 or df[x].var() == 0:
        return {"n": int(len(df)), "slope": np.nan, "lo": np.nan, "hi": np.nan}
    d = day_sums(df, x, r)
    tot = d.sum()
    b = float(slope_from({k: tot[k] for k in d.columns}))
    rng = np.random.default_rng(seed)
    arr = {k: d[k].to_numpy() for k in d.columns}
    out = np.empty(n_boot)
    step = max(1, 2_000_000 // max(len(d), 1))
    for i in range(0, n_boot, step):
        k = min(step, n_boot - i)
        idx = rng.integers(0, len(d), size=(k, len(d)))
        out[i:i + k] = slope_from({c: arr[c][idx].sum(1) for c in arr})
    lo, hi = np.nanpercentile(out, [2.5, 97.5])
    return {"n": int(len(df)), "games": int(df["game_id"].nunique()), "slope": b,
            "lo": float(lo), "hi": float(hi)}


def panels(q: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """The four panels' rows, each with x, resid (y - benchmark)."""
    base = q[q["coherent"] & q["pin_fa"].notna()].copy()
    base["y"] = outcome(base)
    base = base[base["y"].notna()]
    same = (base["market"] == "h2h") | np.isclose(base["line"].fillna(0), base["pin_line"].fillna(np.inf))
    vs_pin = base[same].assign(resid=lambda d: d["y"] - d["pin_fa"])
    own = base[base["book"].isin(DECIDING)].assign(resid=lambda d: d["y"] - d["fa"])
    return {"1 every book vs Pinnacle (pre-registered)": vs_pin,
            "2 Pinnacle's own quotes": vs_pin[vs_pin["book"] == H.SHARP],
            "3 deciding books vs Pinnacle": vs_pin[vs_pin["book"].isin(DECIDING)],
            "4 deciding books vs their own no-vig": own}


def with_window(q: pd.DataFrame, tl: pd.DataFrame, start_s: float, end_s: float | str) -> pd.Series:
    """Signed points in (stamp - start_s, stamp - end_s]; end_s = 'served'
    means (stamp, served_at] and start_s is ignored."""
    from scripts.nba_ingame_data import state_at
    if end_s == "served":
        a, b = q["stamp"], q["served_at"]
    else:
        a = q["stamp"] - pd.Timedelta(seconds=start_s)
        b = q["stamp"] - pd.Timedelta(seconds=end_s)
    z = q[["game_id"]].assign(_a=a, _b=b)
    sa = state_at(z, tl, "_a", ["h_pts", "a_pts"]).fillna(0)
    sb = state_at(z, tl, "_b", ["h_pts", "a_pts"]).fillna(0)
    return pd.Series(signed_points(q["market"], sb["h_pts"] - sa["h_pts"], sb["a_pts"] - sa["a_pts"]),
                     index=q.index)


def gate(q: pd.DataFrame) -> tuple[pd.DataFrame, bool, bool]:
    q = q.assign(x=signed_points(q["market"], q["h_pts_m60"] - q["h_pts_m120"],
                                 q["a_pts_m60"] - q["a_pts_m120"]))
    rows = []
    for name, df in panels(q).items():
        for mk in ("h2h", "spreads", "totals", "pooled"):
            d = df if mk == "pooled" else df[df["market"] == mk]
            rows.append({"panel": name, "market": mk, "seasons": "all", **slope_ci(d)})
            if mk == "pooled":
                for s in sorted(d["season"].unique()):
                    rows.append({"panel": name, "market": mk, "seasons": str(s),
                                 **slope_ci(d[d["season"] == s])})
    t = pd.DataFrame(rows)
    allp = t[t["seasons"] == "all"]
    fires = bool((allp["lo"] > 0).any())
    over = bool((allp["hi"] < 0).any())
    return t, fires, over


def lag_profile(q: pd.DataFrame, tl: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic: the panel-1 and panel-4 slope for points in windows around
    the stamp. A clock mapping that is off shows as a shifted profile."""
    wins = [(600, 300), (300, 180), (180, 120), (120, 60), (60, 30), (30, 0), (0, "served")]
    pn = panels(q)
    rows = []
    for a, b in wins:
        label = f"(t-{a}, t-{b}]" if b != "served" else "(t, served]"
        for name in ("1 every book vs Pinnacle (pre-registered)", "4 deciding books vs their own no-vig"):
            df = pn[name]
            df = df.assign(x=with_window(df, tl, a, b))
            for mk in ("h2h", "spreads", "totals"):
                rows.append({"window": label, "panel": name[:1], "market": mk,
                             **slope_ci(df[df["market"] == mk], n_boot=1000)})
    return pd.DataFrame(rows)


WINDOWS = ("Q1-Q2", "Q2", "halftime", "Q3", "Q4 6+ min")


def window_of(q: pd.DataFrame) -> pd.DataFrame:
    """Boolean column per decision window (Q2 is a part of Q1-Q2)."""
    per, ph = q["period"], q["phase"]
    return pd.DataFrame({
        "Q1-Q2": per.isin([1, 2]) & ph.isin(["live", "break"]),
        "Q2": (per == 2) & ph.isin(["live", "break"]),
        "halftime": ph == "halftime",
        "Q3": (per == 3) & ph.isin(["live", "break"]),
        "Q4 6+ min": (per == 4) & (ph == "live") & (q["clock_s"] >= 360),
    }, index=q.index)


def coverage(q: pd.DataFrame, fresh_rule: bool) -> pd.DataFrame:
    """Deciding books' coherent quotes with a coherent Pinnacle quote within
    60 s; with the rule, the quote and its Pinnacle quote both fresh."""
    d = q[q["book"].isin(DECIDING) & q["coherent"] & q["pin_fa"].notna()].copy()
    if fresh_rule:
        pin_fresh = q[q["book"] == H.SHARP].set_index(["game_id", "market", "fetch_at", "stamp"])["pts_since_stamp"]
        key = pd.MultiIndex.from_frame(d[["game_id", "market", "fetch_at", "pin_stamp"]])
        d["pin_pts_since"] = pin_fresh.reindex(key).to_numpy()
        d = d[(d["pts_since_stamp"] == 0) & (d["pin_pts_since"] == 0)]
    w = window_of(d)
    rows = []
    for s in sorted(d["season"].unique()):
        for name in WINDOWS:
            x = d[(d["season"] == s) & w[name]]
            rows.append({"season": s, "window": name, "quotes": len(x), "games": x["game_id"].nunique(),
                         **{f"games_{m}": x.loc[x["market"] == m, "game_id"].nunique()
                            for m in ("h2h", "spreads", "totals")}})
    return pd.DataFrame(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quotes", default=str(OUT))
    ap.add_argument("--no-profile", action="store_true")
    a = ap.parse_args()
    q = pd.read_parquet(a.quotes)
    tl = pd.read_parquet(Path(a.quotes).parent / TIMELINE.name)
    pd.set_option("display.width", 220)
    t, fires, over = gate(q)
    base = q[q["coherent"] & q["pin_fa"].notna()]
    off = base[(base["market"] != "h2h") & ~np.isclose(base["line"].fillna(0), base["pin_line"].fillna(np.inf))]
    print(f"rows with Pinnacle within 60 s: {len(base):,}; spread/total quotes off Pinnacle's number "
          f"(left out of panels 1-3): {len(off):,}")
    fmt = t.assign(slope=t["slope"].round(4), lo=t["lo"].round(4), hi=t["hi"].round(4))
    print("\nTHE GATE: slope of (result - benchmark) on points in (stamp-120 s, stamp-60 s]")
    print(fmt[fmt["seasons"] == "all"].to_string(index=False))
    print("\nper season, pooled markets:")
    print(fmt[fmt["seasons"] != "all"].to_string(index=False))
    print(f"\nFIRES (an interval wholly above zero): {fires};  over-reaction recorded: {over}")
    if not a.no_profile:
        lp = lag_profile(q, tl)
        print("\nlag profile (diagnostic, 1,000 resamples):")
        print(lp.assign(slope=lp["slope"].round(4), lo=lp["lo"].round(4), hi=lp["hi"].round(4))
              .to_string(index=False))
    for rule in (False, True):
        cov = coverage(q, rule)
        print(f"\ncoverage, deciding books with Pinnacle within 60 s{' + both fresh (the rule)' if rule else ''}:")
        print(cov.pivot(index="season", columns="window", values="games")[list(WINDOWS)].to_string())
        print("quotes:")
        print(cov.pivot(index="season", columns="window", values="quotes")[list(WINDOWS)].to_string())


if __name__ == "__main__":
    main()
