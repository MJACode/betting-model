"""Round 1, step 6: the kill tests on every positive result of r1_method.py
and r1_baselines.py, run on the method's own code (r1_method.decide).

Positive results tested (each at its own pre-registered decision, T-10, cut
0.02 unless stated):
  P1  V1 totals_h1  (2025-26 second half, US-consensus anchor)
  P2  V2 totals_q1  (walk-forward, Pinnacle-ladder anchor, decidable books)
  P3  V1 h2h_h1     (2025-26 second half)
  P5  V1 totals_q1  (2025-26 second half)
  P4  the blind first-half moneyline underdog at the best decidable price

Tests: fit on every season available; the frozen fit read on unseen seasons;
early/late split; side split against the blind same side on the same games;
other reads (every stored mark); without the 10 best dates; return by edge
band; a donor placebo (the anchor shuffled across the graded games, 200
times); the price range.

    python scripts/euroleague_research/r1_kill.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402
import r1_method as M  # noqa: E402

pd.set_option("display.width", 250)
g, G, Q, FG = M.g, M.G, M.Q, M.FG
COLS = ["bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]

s26 = g[(g.season == 2026) & g.played].sort_values("tip")
split = s26.tip.iloc[len(s26) // 2]
fit26 = s26[s26.tip < split].game_id.to_numpy()
grade26 = s26[s26.tip >= split].game_id.to_numpy()
ids = {S: g[(g.season == S) & g.played].game_id.to_numpy() for S in [2024, 2025, 2026, 2027]}


def summ(d, cut=0.02):
    return {k: v for k, v in L.summary(d[d.edge > cut] if len(d) else d).items() if k in COLS}


def line(label, d, cut=0.02):
    print(f"  {label:<62}", " ".join(f"{k}={v}" for k, v in summ(d, cut).items()))


def early_late(d, cut=0.02):
    d = d[d.edge > cut]
    if not len(d):
        return
    med = d.game_date.sort_values().iloc[len(d) // 2]
    line("early half of the bets (by date)", d[d.game_date < med], -1)
    line("late half of the bets (by date)", d[d.game_date >= med], -1)


def best10(d, cut=0.02):
    d = d[d.edge > cut]
    if not len(d):
        return
    top = d.groupby("game_date").units.sum().sort_values().tail(10).index
    line("without the 10 best dates", d[~d.game_date.isin(top)], -1)


def bands(d):
    d = d.copy()
    d["band"] = pd.cut(d.edge, [0.0, 0.01, 0.02, 0.03, 0.05, 1.0])
    for b, x in d.groupby("band", observed=True):
        line(f"edge band {b}", x, -1)


def placebo(version, market, model, grade_ids, books, real_ret, n=200, cut=0.02, seed=11):
    """Shuffle the anchor across the graded games (each game gets a donor's
    full-game number), re-decide, re-grade."""
    rng = np.random.default_rng(seed)
    orig = M.anchor_values
    rets = []
    try:
        for _ in range(n):
            perm = {}

            def shuffled(v, m, mark, idx, _perm=perm):
                a = orig(v, m, mark, idx)
                key = (mark, tuple(a.index))
                if key not in _perm:
                    _perm[key] = pd.Series(rng.permutation(a.to_numpy()), index=a.index)
                return _perm[key]

            M.anchor_values = shuffled
            d = M.decide(version, market, "T-10", model, grade_ids, books)
            y = d[d.edge > cut] if len(d) else d
            s = L.summary(y, n_boot=1)
            rets.append(s["ret%"])
    finally:
        M.anchor_values = orig
    rets = np.array([r for r in rets if np.isfinite(r)])
    print(f"  placebo (anchor shuffled across graded games, {n}x): mean {rets.mean():+.2f}%, "
          f"p95 {np.percentile(rets, 95):+.2f}%, real {real_ret:+.2f}% sits at percentile "
          f"{100 * np.mean(rets < real_ret):.1f}")


def blind_side(market, grade_ids, side, mark="T-10"):
    x = Q[(Q.market == market) & (Q.mark == mark) & Q.game_id.isin(grade_ids) & Q.decidable]
    rows = []
    for gid, y in x.groupby("game_id"):
        if market.startswith("h2h"):
            ln, yy = np.nan, y
        else:
            vc = y.line.value_counts()
            top = vc[vc == vc.max()].index.to_numpy(float)
            med = y.line.median()
            ln = sorted(top, key=lambda v: (abs(v - med), v))[0]
            yy = y[y.line == ln]
        p = yy.pa.max() if side in ("over", "home") else yy.pb.max()
        rows.append({"game_id": gid, "game_date": y.game_date.iloc[0], "margin": y.margin.iloc[0],
                     "total": y.total.iloc[0], "line": ln, "side": side, "price": p})
    out = L.grade_rows(pd.DataFrame(rows), market)
    out["edge"] = 1.0
    return out


def other_reads(version, market, model, grade_ids, books, cut=0.02):
    for mk in ["T-360", "T-180", "T-120", "T-60", "T-30", "T-10"]:
        d = M.decide(version, market, mk, model, grade_ids, books)
        line(f"read at {mk}", d, cut)


def report_v1(market, dom_side):
    print(f"\n==== {market}: V1 (2025-26 time split, US consensus anchor), decidable books ====")
    model = M.fit("V1", market, fit26)
    print(f"  frozen fit: a = {model['a']:.3f}, b = {model['b']:.4f} on {model['n']} games")
    d = M.decide("V1", market, "T-10", model, grade26, L.DECIDABLE)
    line("as run (T-10, cut 0.02)", d)
    real = L.summary(d[d.edge > 0.02])["ret%"]
    y = d[d.edge > 0.02]
    print(f"  side split: {y.side.value_counts().to_dict()}; prices median {y.price.median():.0f}, "
          f"shortest {y.price.min():.0f}; books {y.bookmaker.value_counts().to_dict()}")
    line(f"blind {dom_side} at the best decidable price, same graded games", blind_side(market, grade26, dom_side), -9)
    early_late(d)
    best10(d)
    bands(d)
    other_reads("V1", market, model, grade26, L.DECIDABLE)
    # fit on every season available (Pinnacle anchor: 2023-24, 2024-25 and the first half of 2025-26)
    fit_all = np.concatenate([ids[2024], ids[2025], fit26])
    mall = M.fit("V2", market, fit_all)
    print(f"  fit on every season available (Pinnacle anchor, {mall['n']} games): a = {mall['a']:.3f}, b = {mall['b']:.4f}")
    line("  -> graded on the same second half of 2025-26", M.decide("V2", market, "T-10", mall, grade26, L.DECIDABLE))
    # the frozen V1 fit read on unseen seasons (anchor: Pinnacle ladder; it matched the US consensus within
    # a median 0.0, SD 0.49 points in 2025-26)
    line("frozen V1 fit, Pinnacle anchor, same second half (anchor check)", M.decide("V2", market, "T-10", model, grade26, L.DECIDABLE))
    line("frozen V1 fit on 2026-27 to date, decidable books", M.decide("V2", market, "T-10", model, ids[2027], L.DECIDABLE))
    for S in [2024, 2025]:
        line(f"frozen V1 fit on {S - 1}-{str(S)[2:]}, offshore books (reference)", M.decide("V2", market, "T-10", model, ids[S], L.OFFSHORE))
    placebo("V1", market, model, grade26, L.DECIDABLE, real)


def report_v2(market, dom_side):
    print(f"\n==== {market}: V2 (walk-forward, Pinnacle-ladder anchor) ====")
    parts = []
    for S in [2026, 2027]:
        fit_ids = g[(g.season < S) & (g.season >= 2024) & g.played].game_id.to_numpy()
        model = M.fit("V2", market, fit_ids)
        d = M.decide("V2", market, "T-10", model, ids[S], L.DECIDABLE)
        d["S"] = S
        parts.append((S, model, d))
        line(f"season {S}, decidable", d)
    d = pd.concat([p[2] for p in parts])
    line("pooled 2025-26 + 2026-27 to date, decidable", d)
    real = L.summary(d[d.edge > 0.02])["ret%"]
    y = d[d.edge > 0.02]
    print(f"  side split: {y.side.value_counts().to_dict()}; prices median {y.price.median():.0f}, "
          f"shortest {y.price.min():.0f}; books {y.bookmaker.value_counts().to_dict()}")
    line(f"blind {dom_side} at the best decidable price, 2025-26 + 2026-27 games",
         pd.concat([blind_side(market, ids[S], dom_side) for S in [2026, 2027]]), -9)
    early_late(d)
    best10(d)
    bands(d)
    for S, model, _ in parts:
        print(f"  -- season {S} (fit a = {model['a']:.3f}, b = {model['b']:.4f}, {model['n']} games)")
        other_reads("V2", market, model, ids[S], L.DECIDABLE)
    for S in [2025]:
        fit_ids = g[(g.season < S) & (g.season >= 2024) & g.played].game_id.to_numpy()
        model = M.fit("V2", market, fit_ids)
        line(f"season {S}, offshore books (reference)", M.decide("V2", market, "T-10", model, ids[S], L.OFFSHORE))
    # placebo on the 2025-26 part, where the bets are
    S, model, d26 = parts[0]
    placebo("V2", market, model, ids[S], L.DECIDABLE, L.summary(d26[d26.edge > 0.02])["ret%"])


report_v1("totals_h1", "over")      # P1
report_v2("totals_q1", "under")     # P2
report_v1("h2h_h1", "away")         # P3
report_v1("totals_q1", "under")     # P5

# P4: the blind first-half moneyline underdog at the best decidable price
print("\n==== h2h_h1: the blind underdog at the best decidable price, T-10 ====")
x = Q[(Q.market == "h2h_h1") & (Q.mark == "T-10") & Q.decidable]
rows = []
for gid, y in x.groupby("game_id"):
    fair = y.pa_fair.mean()
    if np.isclose(fair, 0.5):
        continue
    home_dog = fair < 0.5
    rows.append({"game_id": gid, "game_date": y.game_date.iloc[0], "season": y.season.iloc[0],
                 "margin": y.margin.iloc[0], "total": y.total.iloc[0], "line": np.nan,
                 "side": "home" if home_dog else "away", "price": (y.pa if home_dog else y.pb).max()})
dd = L.grade_rows(pd.DataFrame(rows), "h2h_h1")
dd["edge"] = 1.0
line("pooled 2025-26 + 2026-27", dd, -9)
for S, z in dd.groupby("season"):
    line(f"season {S}", z, -9)
z = dd[dd.season == 2026].sort_values("game_date")
med = z.game_date.iloc[len(z) // 2]
line("2025-26 early half", z[z.game_date < med], -9)
line("2025-26 late half", z[z.game_date >= med], -9)
best10(dd, -9)
print(f"  side split: home dogs {int((dd.side == 'home').sum())}, away dogs {int((dd.side == 'away').sum())}")
for side, z in dd.groupby("side"):
    line(f"  {side} underdogs", z, -9)
dd["band"] = pd.cut(dd.price, [-300, 100, 150, 200, 300, 5000])
for b, z in dd.groupby("band", observed=True):
    line(f"price band {b}", z, -9)
