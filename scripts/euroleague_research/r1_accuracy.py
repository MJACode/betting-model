"""Round 1, task 3: the market's own accuracy, and how the first half and
first quarter relate to the full game.

 (a) De-vig each book's main line proportionally (both sides), at T-10 and at
     the earliest mark on the SAME games, and score it against the result
     (pushes and tied periods out): log loss, Brier, against a coin flip
     (0.6931 / 0.25). Plus the line's bias (result minus line).
 (b) The full-game anchor: Pinnacle's ladder fair number at T-10 (every
     season) and the five-book US consensus at T-10 (2025-26, the spool).
     The books' first-half / first-quarter number (median over every book's
     on-centre main at T-10) and the RESULT, each regressed on the anchor.
     Then the line's error by anchor band.

    python scripts/euroleague_research/r1_accuracy.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
g = L.load_games()
Q = L.load_main_quotes(g)
Q = Q[~Q.offc]
FG = pd.read_parquet(Path(r"C:\Users\micha\AppData\Local\Temp\el_r1\fullgame.parquet"))


def target(x: pd.DataFrame, market: str):
    """y = 1 if side a (home / over / home win) wins, 0 if it loses, NaN push."""
    r = L.result(market, np.array(["home" if not market.startswith("totals") else "over"] * len(x)),
                 x.line.to_numpy(), x.margin.to_numpy(), x.total.to_numpy())
    return np.where(r > 0, 1.0, np.where(r < 0, 0.0, np.nan))


def ll(p, y):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


print("==== (a) the close (T-10) against the earliest mark, same games, by market, season and book ====")
rows = []
for m in L.MARKETS:
    xm = Q[Q.market == m].copy()
    xm["y"] = target(xm, m)
    for (season, book), x in xm.groupby(["season", "bookmaker"]):
        close = x[x.mark == "T-10"].set_index("game_id")
        early = x.sort_values("mark_min", ascending=False).drop_duplicates("game_id").set_index("game_id")
        ids = close.index.intersection(early.index)
        c, e = close.loc[ids], early.loc[ids]
        ok = c.y.notna() & e.y.notna()
        c, e = c[ok], e[ok]
        if len(c) < 25:
            continue
        resid = (c.total - c.line) if m.startswith("totals") else (c.margin + c.line if m.startswith("spreads") else np.nan)
        rows.append({"market": m, "season": season, "book": book + ("" if book in L.DECIDABLE else " (ref)"),
                     "games": len(c), "a_rate": round(float(c.y.mean()), 3),
                     "ll_close": round(ll(c.pa_fair, c.y), 4), "ll_early": round(ll(e.pa_fair, e.y), 4),
                     "brier_close": round(float(np.mean((c.pa_fair - c.y) ** 2)), 4),
                     "brier_early": round(float(np.mean((e.pa_fair - e.y) ** 2)), 4),
                     "ll_coin": 0.6931,
                     "bias": round(float(np.mean(resid)), 2) if not m.startswith("h2h") else np.nan,
                     "mean_ovr": round(float(c.ovr.mean()), 4)})
acc = pd.DataFrame(rows)
print("a_rate = share of side a (home cover / over / home win) among graded; bias = result minus line")
print(acc.to_string(index=False))

# pooled
pooled = []
for m in L.MARKETS:
    xm = Q[(Q.market == m) & (Q.mark == "T-10")].copy()
    xm["y"] = target(xm, m)
    for tag, sel in [("decidable", xm.decidable), ("offshore (ref)", xm.bookmaker.isin(L.OFFSHORE))]:
        x = xm[sel & xm.y.notna()]
        if not len(x):
            continue
        # one row per game: the median de-vigged probability over the books in the group (same number not
        # required; this is a calibration read, not a bet)
        pooled.append({"market": m, "books": tag, "quote_rows": len(x), "games": x.game_id.nunique(),
                       "ll_close": round(ll(x.pa_fair, x.y), 4),
                       "brier": round(float(np.mean((x.pa_fair - x.y) ** 2)), 4),
                       "calib_slope": round(float(np.polyfit(x.pa_fair - 0.5, x.y - 0.5, 1)[0]), 3)})
print("\n==== (a') pooled over seasons at T-10 (every quote row; calib_slope = slope of result on the de-vigged probability, 1.0 = calibrated) ====")
print(pd.DataFrame(pooled).to_string(index=False))

# ── (b) the half and the quarter against the full game ──────────────────────
print("\n==== (b) the books' period number and the result, against the full-game anchor at T-10 ====")
c10 = Q[Q.mark == "T-10"]
med = c10.groupby(["game_id", "market"]).line.median().unstack()
fg10 = FG[FG.mark == "T-10"].set_index("game_id")
G = g.set_index("game_id")
D = med.join(fg10[["pin_total", "pin_spread", "total_us", "spread_us"]], how="left").join(
    G[["season", "h1_total", "h1_margin", "q1_total", "q1_margin", "fg_total", "fg_margin", "went_to_ot"]], how="left")
reg_rows = []
for anchor, tag in [("pin", "Pinnacle ladder, every season"), ("us", "US five-book consensus, 2025-26")]:
    for per in ["h1", "q1"]:
        for kind in ["total", "spread"]:
            a = D[f"{anchor}_{kind}" if anchor == "pin" else f"{kind}_us"]
            line = D[f"{'totals' if kind == 'total' else 'spreads'}_{per}"]
            res = D[f"{per}_total"] if kind == "total" else -D[f"{per}_margin"]   # spreads: compare home numbers
            for season in sorted(D.season.dropna().unique()):
                ok = a.notna() & line.notna() & res.notna() & (D.season == season)
                if ok.sum() < 30:
                    continue
                bl = np.polyfit(a[ok], line[ok], 1)
                br = np.polyfit(a[ok], res[ok], 1)
                reg_rows.append({"anchor": tag, "period": per, "kind": kind, "season": int(season),
                                 "games": int(ok.sum()),
                                 "line_on_fg_b": round(bl[0], 4), "line_on_fg_a": round(bl[1], 3),
                                 "result_on_fg_b": round(br[0], 4), "result_on_fg_a": round(br[1], 3),
                                 "ratio_line": round(float((line[ok] / a[ok]).mean()), 4) if kind == "total" else np.nan,
                                 "ratio_line_sd": round(float((line[ok] / a[ok]).std()), 4) if kind == "total" else np.nan,
                                 "ratio_result": round(float((res[ok] / a[ok]).mean()), 4) if kind == "total" else np.nan,
                                 "resid_sd_line": round(float(np.std(line[ok] - np.polyval(bl, a[ok]))), 3),
                                 "mean_res_minus_line": round(float((res[ok] - line[ok]).mean()), 3)})
print("For spreads the 'result' is minus the home margin (a home number), so both columns are home numbers;")
print("b = slope, a = intercept; ratio = period number / full-game number; resid_sd_line = how far the book's")
print("period number strays from its own straight-line map off the full game.")
print(pd.DataFrame(reg_rows).to_string(index=False))

print("\n==== (b') the period line's error by full-game band (Pinnacle ladder fair at T-10, every season pooled) ====")
for per in ["h1", "q1"]:
    for kind in ["total", "spread"]:
        a = D[f"pin_{kind}"]
        line = D[f"{'totals' if kind == 'total' else 'spreads'}_{per}"]
        if kind == "total":
            res = D[f"{per}_total"]
            err = res - line
            bins = [0, 155, 160, 165, 170, 175, 180, 999]
        else:
            res = D[f"{per}_margin"]
            err = res + line           # > 0 home covered the period number
            bins = [-99, -12, -8, -4, 0, 4, 8, 99]
        ok = a.notna() & line.notna() & res.notna()
        t = pd.DataFrame({"band": pd.cut(a[ok], bins), "err": err[ok], "season": D.season[ok]})
        s = t.groupby("band", observed=True).agg(games=("err", "size"), mean_err=("err", "mean"),
                                                 side_a_rate=("err", lambda v: float((v > 0).sum() / max((v != 0).sum(), 1))))
        print(f"-- {per} {kind}: err = {'result minus line (over > 0)' if kind == 'total' else 'home margin + home number (home covers > 0)'}")
        print(s.round(3).to_string())
