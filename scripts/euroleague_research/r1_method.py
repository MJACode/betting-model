"""Round 1, task 4: "a half priced from the full-game consensus", run unchanged.

THE METHOD (references/methods.md section 3; the repo's own pricing code,
models/ncaab_first_half_spread.py and models/ncaab_first_half_total.py,
IMPORTED, not copied):
  1. Fit ONE least-squares map of the period outcome on the full-game number
     on the fitting games:  outcome = a + b x anchor.
       totals:   outcome = the period's total points, anchor = full-game total
       spreads / moneylines: outcome = the period's home margin, anchor =
                 minus the full-game home spread (the expected home margin)
  2. The empirical outcome table: the repo's kernel table (fit_table, Gaussian
     weights in the key a + b x anchor, bandwidth 0.75, widened x1.25 until
     the weights reach 500 games or the bandwidth passes 20). The 201- and
     291-game fits never reach 500, so their table is the method's own
     fallback: every fitting game, shifted to the mean. The 621- and
     1,023-game fits reach it by widening to about 1.2-4.5 points at the
     median key (r1_kill2.py, table 1).
  3. mu = a + b x anchor at the decision; every decidable book's on-centre
     main quote is priced through the table: q = P(side a wins | no push),
     edge = q - 1/decimal(price) per side, the larger side kept. Moneylines:
     q = P(margin > 0) / (P(margin > 0) + P(margin < 0)) (a tie pushes).
  4. One decision a game: the single quote with the largest edge; a bet
     when that edge is above the cut. Graded at that book's quoted price.
  Left out this round: the catalogued method's shrunk team half-tendency
  (it needs last season's full-game lines for its prior; in its source it
  moved the mean by at most about a quarter of a point).

TWO VERSIONS, decided before any result was read:
  V1  the brief's: 2025-26 only, anchor = the five-book US consensus from the
      spool at the same snapshot (r1_fullgame.py). Time split at the median
      tip of the 402 games: the first 201 fit, the last 201 grade.
  V2  walk-forward on Pinnacle's ladder fair number (same fetch as the
      period quote, every season): fit on every earlier season, grade the
      next (2024 -> 2025, 2024-25 -> 2026, 2024-26 -> 2027 to date).
      Graded at the decidable books (2025-26 on) and, as reference only, at
      the offshore books (every graded season).
  Decision mark T-10 (fit keys are T-10 too); other read T-60.
  Cut grid 0.00 .. 0.05; the catalogued cut is 0.02.

Writes the bet rows to C:\\Users\\micha\\AppData\\Local\\Temp\\el_r1\\method_bets.parquet
(temporary, for the kill tests; deleted at the end of the round).

    python scripts/euroleague_research/r1_method.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, r"C:\Users\micha\documents\bm-euroleague-fix")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import models.ncaab_first_half_spread as fh  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402
import r1_lib as L  # noqa: E402

pd.set_option("display.width", 250)
TMP = Path(r"C:\Users\micha\AppData\Local\Temp\el_r1")
g = L.load_games()
G = g.set_index("game_id")
Q = L.load_main_quotes(g)
Q = Q[~Q.offc]
FG = pd.read_parquet(TMP / "fullgame.parquet")


def anchor_col(version: str, kind: str) -> str:
    if version == "V1":
        return "total_us" if kind == "total" else "spread_us"
    return "pin_total" if kind == "total" else "pin_spread"


def kind_of(market):
    return "total" if market.startswith("totals") else "spread"


def outcome_of(market):
    per = L.period_of(market)
    return f"{per}_total" if market.startswith("totals") else f"{per}_margin"


def anchor_values(version, market, mark, ids):
    col = anchor_col(version, kind_of(market))
    a = FG[FG.mark == mark].set_index("game_id")[col].reindex(ids)
    return a if market.startswith("totals") else -a          # spreads/moneylines: expected home margin


def fit(version, market, fit_ids):
    a = anchor_values(version, market, "T-10", fit_ids)
    y = G.loc[fit_ids, outcome_of(market)]
    ok = a.notna() & y.notna()
    b1, b0 = np.polyfit(a[ok], y[ok], 1)
    key = b0 + b1 * a[ok]
    if market.startswith("totals"):
        T = ft.fit_table(y[ok].to_numpy(), key.to_numpy())
    else:
        T = fh.fit_table(y[ok].to_numpy(), key.to_numpy())
    return {"a": b0, "b": b1, "T": T, "n": int(ok.sum())}


def price(market, mu, x, T):
    """Per quote: side ('home'/'away'/'over'/'under'), edge, q of that side."""
    if market.startswith("totals"):
        side, edge, qq = ft.price_quote(mu, x.line.to_numpy(), x.pa.to_numpy(), x.pb.to_numpy(), T)
        names = np.where(side == 1, "over", "under")
    elif market.startswith("spreads"):
        side, edge, qq = fh.price_quote(mu, x.line.to_numpy(), x.pa.to_numpy(), x.pb.to_numpy(), T)
        names = np.where(side == 1, "home", "away")
    else:
        pw, pp, pl = fh.probs(mu, np.zeros(len(x)), T)
        q1 = pw / np.maximum(pw + pl, 1e-12)
        e1 = q1 - 1 / fh.dec(x.pa.to_numpy())
        e2 = (1 - q1) - 1 / fh.dec(x.pb.to_numpy())
        side = np.where(e1 >= e2, 1, 2)
        edge = np.maximum(e1, e2)
        qq = np.where(side == 1, q1, 1 - q1)
        names = np.where(side == 1, "home", "away")
    return names, edge, qq


def decide(version, market, mark, model, grade_ids, books):
    x = Q[(Q.market == market) & (Q.mark == mark) & Q.game_id.isin(grade_ids) & Q.bookmaker.isin(books)].copy()
    if not len(x):
        return pd.DataFrame()
    anc = anchor_values(version, market, mark, x.game_id.unique())
    x["anchor"] = x.game_id.map(anc)
    x = x[x.anchor.notna()]
    x["mu"] = model["a"] + model["b"] * x.anchor
    side, edge, qq = price(market, x.mu.to_numpy(), x, model["T"])
    x["side"], x["edge"], x["q"] = side, edge, qq
    x["price"] = np.where(np.isin(side, ["home", "over"]), x.pa, x.pb)
    # one decision a game: the largest edge, ties to the alphabetically first book
    x = x.sort_values(["game_id", "edge", "bookmaker"], ascending=[True, False, True]).drop_duplicates("game_id")
    return L.grade_rows(x, market)


def main():
    rows, bets = [], []
    s26 = g[(g.season == 2026) & g.played].sort_values("tip")
    split = s26.tip.iloc[len(s26) // 2]
    fit26 = s26[s26.tip < split].game_id.to_numpy()
    grade26 = s26[s26.tip >= split].game_id.to_numpy()
    print(f"V1 time split at {split}: {len(fit26)} fitting games, {len(grade26)} graded")

    for m in L.MARKETS:
        # V1
        model = fit("V1", m, fit26)
        print(f"V1 {m}: a = {model['a']:.3f}, b = {model['b']:.4f} on {model['n']} games")
        for mark in ["T-10", "T-60"]:
            d = decide("V1", m, mark, model, grade26, L.DECIDABLE)
            d["version"], d["mark_read"], d["book_set"], d["grade_season"] = "V1", mark, "decidable", 2026
            bets.append(d)
        # V2
        for S in [2025, 2026, 2027]:
            fit_ids = g[(g.season < S) & (g.season >= 2024) & g.played].game_id.to_numpy()
            gr_ids = g[(g.season == S) & g.played].game_id.to_numpy()
            model = fit("V2", m, fit_ids)
            print(f"V2 {m} grade {S}: a = {model['a']:.3f}, b = {model['b']:.4f} on {model['n']} games")
            for mark in ["T-10", "T-60"]:
                for tag, books in [("decidable", L.DECIDABLE), ("offshore (ref)", L.OFFSHORE)]:
                    d = decide("V2", m, mark, model, gr_ids, books)
                    if len(d):
                        d["version"], d["mark_read"], d["book_set"], d["grade_season"] = "V2", mark, tag, S
                        bets.append(d)

    B = pd.concat([b for b in bets if len(b)], ignore_index=True)
    B.to_parquet(TMP / "method_bets.parquet", index=False)

    out = []
    for (ver, m, mark, bs), x in B.groupby(["version", "market", "mark_read", "book_set"]):
        for cut in L.CUTS:
            y = x[x.edge > cut]
            out.append({"version": ver, "market": m, "mark": mark, "books": bs, "cut": cut,
                        "seasons": ",".join(str(s) for s in sorted(y.grade_season.unique())), **L.summary(y)})
    T = pd.DataFrame(out)
    cols = ["version", "market", "mark", "books", "cut", "seasons", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]
    for ver in ["V1", "V2"]:
        print(f"\n==== {ver}: the cut grid, every graded season pooled ====")
        print(T[T.version == ver][cols].to_string(index=False))

    print("\n==== V2 by graded season, cut 0.02 (the catalogued cut), T-10 ====")
    per = []
    for (m, bs, S), x in B[(B.version == "V2") & (B.mark_read == "T-10")].groupby(["market", "book_set", "grade_season"]):
        per.append({"market": m, "books": bs, "season": S, **L.summary(x[x.edge > 0.02])})
    print(pd.DataFrame(per)[["market", "books", "season", "bets", "W", "L", "P", "units", "ret%", "lo%", "hi%"]].to_string(index=False))

    print("\n==== side split and price at cut 0.02, T-10 ====")
    sp = []
    for (ver, m, bs), x in B[B.mark_read == "T-10"].groupby(["version", "market", "book_set"]):
        y = x[x.edge > 0.02]
        if not len(y):
            continue
        sp.append({"version": ver, "market": m, "books": bs, "bets": len(y),
                   **{f"side_{s}": int((y.side == s).sum()) for s in ["home", "away", "over", "under"]},
                   "median_price": float(y.price.median()), "shortest": float(y.price.min()),
                   "share_lt_-200": round(float((y.price < -200).mean()), 3),
                   "share_lt_-300": round(float((y.price < -300).mean()), 3),
                   "median_edge": round(float(y.edge.median()), 4),
                   "distinct_mu": int(y.mu.round(3).nunique()),
                   "books_named": ",".join(f"{k}:{v}" for k, v in y.bookmaker.value_counts().items())})
    print(pd.DataFrame(sp).to_string(index=False))


if __name__ == "__main__":
    main()
