"""Does the live prop model improve when it is told what the player has already done?

THE DEFECT THIS MEASURES. `nfl/live_model/workers/gameday.py` prices every live
quote with `over_prob(q.line, None, seconds_remaining)` -- the accrued count is
passed as None, and the function ignores the clock too. Its answer is the same
number on every quote in every game. So the model cannot distinguish a line the
player has nearly reached from one he would have to double his pace to clear,
and the record shows it: on 2026-09-20 it went 4-13, and the five bets that
needed the biggest pace surge went 0-for-5.

WHAT IS TESTED, IN ORDER.

  1. THE GATE. Bucket every archived quote by the pace the over still needed
     against the pace the player had been managing, and compare the realised
     over rate to the price the book was charging. If the book already prices
     feasibility, the gaps are flat and there is nothing here.
  2. THE MODEL. A market-anchored logistic fit: start from the book's own
     de-vigged probability and ask whether game state adds anything on top.
     This is the construction `.claude/rules/model-updates.md` specifies --
     priced RELATIVE to the book's number, not a player projection rebuilt
     from scratch with the line thrown away.
  3. THE MONEY. Walk-forward -- fit on 2023-24, bet 2025 -- graded at the real
     posted prices with the real vig, as a threshold NEIGHBOURHOOD rather than
     a peak, split early against late.

WHY EVERY INTERVAL IS CLUSTERED ON THE GAME. The archive snapshots each game
about every five minutes, so one game contributes ~40 quotes on the same
players and the same script. Those are repeated looks at one outcome, not 40
independent bets: 33,286 quotes come from 849 games. Treating them as
independent shrinks every standard error by roughly sqrt(40) and would make
noise look decisive. Every interval below resamples GAMES.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

STATE = "nfl/data/live_model/_quotes_state.parquet"
MARKETS = ["attempts", "completions", "receptions", "carries"]

# The deployed model's own gates, so the comparison is like for like.
MIN_SECONDS = 240
MAX_SECONDS = 3600


# ------------------------------------------------------------------ utilities
def american_b(a: np.ndarray) -> np.ndarray:
    """Decimal profit per unit staked on a winning bet."""
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, a / 100.0, 100.0 / np.abs(np.where(a == 0, -100.0, a)))


def implied(a: np.ndarray) -> np.ndarray:
    a = np.asarray(a, dtype=float)
    return np.where(a < 0, -a / (-a + 100.0), 100.0 / (a + 100.0))


def logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-6, 1 - 1e-6)
    return np.log(p / (1.0 - p))


def boot_roi(profit: np.ndarray, games: np.ndarray, draws: int = 4000,
             seed: int = 0) -> tuple[float, float]:
    """Percentile CI for ROI, resampling GAMES rather than quotes."""
    rng = np.random.default_rng(seed)
    uniq = pd.unique(games)
    by = {g: profit[games == g] for g in uniq}
    out = np.empty(draws)
    for i in range(draws):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        s = np.concatenate([by[g] for g in pick])
        out[i] = s.mean() if len(s) else 0.0
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def brier(y: np.ndarray, p: np.ndarray) -> float:
    return float(np.mean((p - y) ** 2))


# ------------------------------------------------------------------- the data
def load() -> pd.DataFrame:
    d = pd.read_parquet(STATE)
    d = d[d["secs"].between(MIN_SECONDS, MAX_SECONDS)].copy()

    # A line the player has ALREADY passed is not a live proposition -- the
    # over is decided and the book has moved on. The deployed model has a gate
    # for exactly this (MIN_SLACK) that never fires, because production passes
    # accrued=None. Excluded here rather than bet, and counted so the size of
    # what that dead gate was letting through is on the record.
    d["settled_over"] = d["accrued"] > d["line"]

    d["pace_so_far"] = d["accrued"] / d["elapsed_min"].clip(lower=1.0)
    d["pace_needed"] = d["slack"] / d["min_left"].clip(lower=1e-9)
    # Projecting the player's own pace over the time left is the book's
    # mechanical prorate; the ratio of what is needed to what that projects is
    # the single number the deployed rule is missing.
    d["proj_remaining"] = d["pace_so_far"] * d["min_left"]
    d["gap"] = d["proj_remaining"] - d["slack"]
    return d


def bettable(d: pd.DataFrame) -> pd.DataFrame:
    need = ["imp_over", "over_price", "under_price", "went_over", "push",
            "accrued", "slack", "min_left", "trail", "final"]
    return d[~d["settled_over"] & d[need].notna().all(axis=1)].copy()


# ------------------------------------------------------- 1. the feasibility gate
def section_gate(d: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("1. DOES THE BOOK PRICE FEASIBILITY?")
    print("=" * 78)
    print("   Each row: how the over actually landed, against what the book")
    print("   charged for it. A book that already prices the clock and the")
    print("   player's pace would show a flat gap column.\n")
    b = bettable(d)
    b = b[b["pace_so_far"] > 0]
    bins = [0, 0.6, 0.8, 1.0, 1.25, 1.6, 99]
    for stat in MARKETS:
        s = b[b["stat"] == stat]
        if s.empty:
            continue
        t = s.groupby(pd.cut(s["pace_ratio"], bins), observed=True).agg(
            quotes=("went_over", "size"), games=("game_id", "nunique"),
            over_rate=("went_over", "mean"), book=("imp_over", "mean"))
        t["gap_pp"] = 100.0 * (t["over_rate"] - t["book"])
        print(f"   --- {stat}  (n={len(s):,}, {s['game_id'].nunique()} games) ---")
        print(t.to_string(float_format=lambda x: f"{x:8.3f}"))
        print()


# ------------------------------------------------------------- 2. the model
FEATURES = ["anchor", "gap", "log_time", "pace_so_far", "slack", "trail"]


def design(d: pd.DataFrame) -> pd.DataFrame:
    x = pd.DataFrame(index=d.index)
    # The book's own number, on the log-odds scale: the model starts from the
    # market and is only ever asked what state adds to it.
    x["anchor"] = logit(d["imp_over"].to_numpy())
    x["gap"] = d["gap"].clip(-25, 25)
    x["log_time"] = np.log(d["min_left"].clip(lower=1.0))
    x["pace_so_far"] = d["pace_so_far"].clip(0, 5)
    x["slack"] = d["slack"].clip(-20, 40)
    x["trail"] = d["trail"].fillna(0.0).clip(-30, 30)
    return x


def fit_market(train: pd.DataFrame):
    import statsmodels.api as sm
    x = sm.add_constant(design(train), has_constant="add")
    y = train["went_over"].to_numpy(float)
    return sm.Logit(y, x).fit(disp=0)


def predict(model, frame: pd.DataFrame) -> np.ndarray:
    import statsmodels.api as sm
    return model.predict(sm.add_constant(design(frame), has_constant="add"))


def section_model(d: pd.DataFrame) -> dict:
    print("\n" + "=" * 78)
    print("2. WALK-FORWARD: FIT ON 2023-24, SCORE 2025")
    print("=" * 78)
    print("   Proper scoring rules against the market's own de-vigged price.")
    print("   The market is the baseline; beating it is the only thing that")
    print("   counts. Lower is better for both.\n")
    b = bettable(d)
    fits = {}
    rows = []
    for stat in MARKETS:
        s = b[b["stat"] == stat]
        tr = s[s["season"] <= 2024]
        te = s[s["season"] == 2025]
        if len(tr) < 500 or len(te) < 100:
            rows.append({"stat": stat, "train": len(tr), "test": len(te),
                         "note": "INSUFFICIENT DATA"})
            continue
        m = fit_market(tr)
        fits[stat] = m
        p = predict(m, te).to_numpy()
        y = te["went_over"].to_numpy(float)
        mk = te["imp_over"].to_numpy(float)
        rows.append({
            "stat": stat, "train": len(tr), "test": len(te),
            "games": te["game_id"].nunique(),
            "ll_model": log_loss(y, p), "ll_market": log_loss(y, mk),
            "brier_model": brier(y, p), "brier_market": brier(y, mk),
        })
    t = pd.DataFrame(rows)
    if "ll_model" in t:
        t["ll_gain"] = t["ll_market"] - t["ll_model"]
    print(t.to_string(index=False, float_format=lambda x: f"{x:9.5f}"))
    print("\n   ll_gain > 0 means the model carries information the price does not.")
    return fits


# --------------------------------------------------------------- 3. the money
def grade(te: pd.DataFrame, p: np.ndarray, cut: float) -> pd.DataFrame:
    """Bet whichever side the model likes by more than `cut`, at the real price."""
    edge_over = p - te["imp_over"].to_numpy(float)
    side = np.where(edge_over >= cut, "over",
                    np.where(edge_over <= -cut, "under", ""))
    take = side != ""
    g = te[take].copy()
    g["side"] = side[take]
    price = np.where(g["side"] == "over", g["over_price"], g["under_price"])
    g["price"] = price
    won = np.where(g["side"] == "over", g["went_over"] == 1, g["went_over"] == 0)
    # A push returns the stake: the final landed exactly on an integer line.
    g["profit"] = np.where(g["push"] == 1, 0.0,
                           np.where(won, american_b(price), -1.0))
    return g


def section_money(d: pd.DataFrame, fits: dict) -> None:
    print("\n" + "=" * 78)
    print("3. UNITS AT THE REAL POSTED PRICES, 2025 (out of sample)")
    print("=" * 78)
    print("   One unit = one flat bet. ROI interval resamples GAMES, because")
    print("   ~40 quotes come from each one and they are not 40 bets.\n")
    b = bettable(d)
    for stat in MARKETS:
        if stat not in fits:
            print(f"   --- {stat}: INSUFFICIENT DATA / CANNOT ASSUME ---\n")
            continue
        te = b[(b["stat"] == stat) & (b["season"] == 2025)]
        p = predict(fits[stat], te).to_numpy()
        rows = []
        for cut in (0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10):
            g = grade(te, p, cut)
            if g.empty:
                rows.append({"cut": cut, "bets": 0})
                continue
            prof = g["profit"].to_numpy()
            lo, hi = boot_roi(prof, g["game_id"].to_numpy())
            rows.append({
                "cut": cut, "bets": len(g), "games": g["game_id"].nunique(),
                "over": int((g["side"] == "over").sum()),
                "units": prof.sum(), "roi": prof.mean(),
                "ci_lo": lo, "ci_hi": hi,
            })
        print(f"   --- {stat} ---")
        print(pd.DataFrame(rows).to_string(
            index=False, float_format=lambda x: f"{x:8.4f}"))
        print()


def section_split(d: pd.DataFrame, fits: dict, cut: float = 0.04) -> None:
    print("\n" + "=" * 78)
    print(f"4. EARLY AGAINST LATE WITHIN 2025 (cut {cut:.2f})")
    print("=" * 78)
    print("   A pooled edge that lives in one half of the season is noise.\n")
    b = bettable(d)
    rows = []
    for stat in MARKETS:
        if stat not in fits:
            continue
        te = b[(b["stat"] == stat) & (b["season"] == 2025)]
        g = grade(te, predict(fits[stat], te).to_numpy(), cut)
        if g.empty:
            continue
        mid = g["ts"].median()
        for half, part in (("early", g[g["ts"] <= mid]), ("late", g[g["ts"] > mid])):
            if part.empty:
                continue
            rows.append({"stat": stat, "half": half, "bets": len(part),
                         "units": part["profit"].sum(),
                         "roi": part["profit"].mean()})
    print(pd.DataFrame(rows).to_string(
        index=False, float_format=lambda x: f"{x:8.4f}") if rows else "   none")


def section_second_season(d: pd.DataFrame, cut: float = 0.04) -> None:
    """The same rule, fitted and tested on a completely different pair of years.

    2025 is one season and four markets were looked at, so a single positive
    cell there is a cell that had several chances to appear. Refitting on 2023
    alone and betting 2024 reuses none of the test data that produced it: if
    the edge is real it survives, and if it was the best of four it does not.
    """
    print("\n" + "=" * 78)
    print(f"5. A SECOND, INDEPENDENT OUT-OF-SAMPLE SEASON (cut {cut:.2f})")
    print("=" * 78)
    print("   fit 2023 -> bet 2024, beside fit 2023-24 -> bet 2025.\n")
    b = bettable(d)
    rows = []
    for stat in MARKETS:
        for label, tr_y, te_y in (("fit 23 -> bet 24", [2023], 2024),
                                  ("fit 23-24 -> bet 25", [2023, 2024], 2025)):
            tr = b[(b["stat"] == stat) & b["season"].isin(tr_y)]
            te = b[(b["stat"] == stat) & (b["season"] == te_y)]
            if len(tr) < 500 or len(te) < 100:
                rows.append({"stat": stat, "split": label, "bets": 0,
                             "note": "INSUFFICIENT DATA"})
                continue
            g = grade(te, predict(fit_market(tr), te).to_numpy(), cut)
            if g.empty:
                rows.append({"stat": stat, "split": label, "bets": 0})
                continue
            prof = g["profit"].to_numpy()
            lo, hi = boot_roi(prof, g["game_id"].to_numpy())
            rows.append({"stat": stat, "split": label, "bets": len(g),
                         "games": g["game_id"].nunique(),
                         "under": int((g["side"] == "under").sum()),
                         "units": prof.sum(), "roi": prof.mean(),
                         "ci_lo": lo, "ci_hi": hi})
    print(pd.DataFrame(rows).to_string(
        index=False, float_format=lambda x: f"{x:8.4f}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--section", type=int, choices=[1, 2, 3, 4, 5], default=None)
    a = ap.parse_args()
    d = load()
    b = bettable(d)
    print(f"{len(d):,} archived quotes inside the model's own clock gate "
          f"({MIN_SECONDS}s-{MAX_SECONDS}s), {d['game_id'].nunique():,} games.")
    print(f"{int(d['settled_over'].sum()):,} of them were already decided -- the "
          f"player had passed the line. The deployed model has a gate for these "
          f"that never fires, because production passes accrued=None.")
    print(f"{len(b):,} bettable quotes remain, over rate {b['went_over'].mean():.3f}.")

    fits = {}
    if a.section in (None, 1):
        section_gate(d)
    if a.section in (None, 2, 3, 4):
        fits = section_model(d)
    if a.section in (None, 3):
        section_money(d, fits)
    if a.section in (None, 4):
        section_split(d, fits)
    if a.section in (None, 5):
        section_second_season(d)


if __name__ == "__main__":
    main()
