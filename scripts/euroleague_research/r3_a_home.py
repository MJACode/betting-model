"""Round 2, experiment A: the home lean (pre-registration: section 0.2 of
euroleague_round2.md). Returns / prints markdown.

  A1  home moneyline at the full-game close, -200 floor, DraftKings close
      (main) and the best decidable close; six price bands; by season; the
      walk-forward band rule; home win rate against Pinnacle's close.
  A2  first-half home spread and moneyline at T-10, FanDuel, BetRivers and
      the best of the two, 2025-26 and 2026-27.
  A3  round 1's frozen home-underdog spread rule read unchanged on 2026-27.

    python scripts/euroleague_research/r3_a_home.py
"""
from __future__ import annotations

import contextlib
import io

import numpy as np
import pandas as pd

import r1_lib as L1
import r2_lib as L2
import r3_lib as R

EXP = "A"
BANDS = [(-200, -151, "-200..-151"), (-150, -121, "-150..-121"), (-120, -101, "-120..-101"),
         (100, 150, "+100..+150"), (151, 250, "+151..+250"), (251, 100000, "+251 or longer")]


def band_of(p):
    p = np.asarray(p, float)
    out = np.full(len(p), "", object)
    for lo, hi, lab in BANDS:
        out[(p >= lo) & (p <= hi)] = lab
    return out


def a1(md: list):
    g, q, dt, cb, fp = R.fullgame()
    g = g[~g.neutral_site & (g.season >= 2022)]
    ok = set(g.game_id)
    b = cb[(cb.market == "h2h") & cb.game_id.isin(ok)]
    z = R.ml_sides(b)
    home = z[(z.side == "home") & (z.price >= -200)].copy()
    dk = L2.grade(home[home.bookmaker == "draftkings"])
    best = L2.grade(R.best_price(home[home.bookmaker.isin(R.DECIDABLE)]))
    dk["band"] = band_of(dk.price)
    best["band"] = band_of(best.price)

    md.append("### A1. Home moneyline at the full-game close, -200 floor (r3_a_home.py)\n")
    rows = []
    for lab, x in (("DraftKings close", dk), ("best decidable close", best)):
        rows.append(R.reg(EXP, f"A1 home ML {lab}, all bands", x) | {"subset": "all bands"})
        for _, _, bl in BANDS:
            rows.append(R.reg(EXP, f"A1 home ML {lab}, band {bl}", x[x.band == bl]) | {"subset": f"band {bl}"})
    md.append(R.table(rows))
    md.append("\nBy season (DraftKings close, all bands, and each band):\n")
    rows = []
    for s, xs in dk.groupby("season"):
        rows.append(R.row({"season": int(s), "band": "all"}, xs))
    for _, _, bl in BANDS:
        for s, xs in dk[dk.band == bl].groupby("season"):
            rows.append(R.row({"season": int(s), "band": bl}, xs))
    md.append(R.table(rows))
    md.append("\nBy season, best decidable close (all bands):\n")
    md.append(R.table([R.row({"season": int(s)}, xs) for s, xs in best.groupby("season")]))

    # walk-forward band rule
    picks = []
    chosen = {}
    for s in range(2023, 2028):
        prior = dk[dk.season < s]
        good = [bl for _, _, bl in BANDS
                if len(prior[prior.band == bl]) and prior[prior.band == bl].units.sum() > 0]
        chosen[s] = good
        picks.append(dk[(dk.season == s) & dk.band.isin(good)])
    wf = pd.concat(picks)
    md.append("\nWalk-forward band rule (DraftKings close; in season s, the bands positive over every earlier season):\n")
    md.append("Bands chosen: " + "; ".join(f"{s}: {', '.join(v) or 'none'}" for s, v in chosen.items()) + "\n")
    rows = [R.reg(EXP, "A1 walk-forward band rule, DraftKings close", wf) | {"subset": "2022-23 on"}]
    rows += [R.row({"subset": f"season {int(s)}"}, xs) for s, xs in wf.groupby("season")]
    md.append(R.table(rows))

    # descriptive: home win rate vs Pinnacle close
    pin = b[b.bookmaker == "pinnacle"][["game_id", "pa_pow"]].merge(g[["game_id", "season", "margin"]], on="game_id")
    rows = []
    for s, x in list(pin.groupby("season")) + [("2022-2026 pooled", pin[pin.season <= 2026]), ("all", pin)]:
        rows.append({"season": s, "games": len(x), "home won %": round(100 * float((x.margin > 0).mean()), 2),
                     "Pinnacle no-vig home %": round(100 * float(x.pa_pow.mean()), 2),
                     "gap (pts of %)": round(100 * float((x.margin > 0).mean() - x.pa_pow.mean()), 2)})
    md.append("\nDescriptive: home win rate against Pinnacle's power-de-vigged close, every price (neutral out):\n")
    md.append(R.table(rows))
    md.append(f"\nKill rows, DraftKings close, all bands: price range {R.price_range(dk)}\n")
    md.append(R.table(R.kill_rows("A1 DK close home ML, -200 floor", dk.assign(fav=dk.price < 0))))
    # the positive sub-cells, read off this table (post hoc, labelled so)
    for lab, x in (("A1 DK close home ML, band +151..+250 (a band read off the table)", dk[dk.band == "+151..+250"]),
                   ("A1 DK close home ML, band -120..-101 (a band read off the table)", dk[dk.band == "-120..-101"]),
                   ("A1 DK close home ML, home underdog +100 or longer (post hoc)", dk[dk.price >= 100])):
        md.append(f"\nKill rows, {lab}: price range {R.price_range(x)}\n")
        md.append(R.table(R.kill_rows(lab, x, fav_col=None)))
    # side control and the neutral-site placebo
    allg, _, _, cb_all, _ = R.fullgame()
    neu = set(allg.game_id[allg.neutral_site & (allg.season >= 2022)])
    zz = R.ml_sides(cb_all[(cb_all.market == "h2h") & (cb_all.bookmaker == "draftkings")])
    away = L2.grade(zz[(zz.side == "away") & (zz.price >= -200) & zz.game_id.isin(ok)])
    nh = L2.grade(zz[(zz.side == "home") & (zz.price >= -200) & zz.game_id.isin(neu)])
    md.append("\nSide control and placebo (not counted): the away side under the same floor, and the nominal home side "
              "at neutral-site games (no home crowd), DraftKings close:\n")
    md.append(R.table([R.row({"control": "away ML, -200 floor, every non-neutral game"}, away),
                       R.row({"control": "away ML underdog +100 or longer"}, away[away.price >= 100]),
                       R.row({"control": "nominal home ML at neutral-site games, -200 floor"}, nh)]))
    return dk, best


def a2(md: list):
    q = R.period_main()
    q = q[(q.mark == "T-10") & q.season.isin([2026, 2027])]
    g1 = R.period_games()
    neutral = set(g1.game_id[g1.neutral_site])
    q = q[~q.game_id.isin(neutral)]
    md.append("\n### A2. First-half home bets at T-10, 2025-26 and 2026-27 (r3_a_home.py)\n")
    rows = []
    out = {}
    for market in ("spreads_h1", "h2h_h1"):
        x = q[q.market == market]
        for book in ("fanduel", "betrivers", "best of fanduel/betrivers"):
            if book.startswith("best"):
                y = x[x.bookmaker.isin(["fanduel", "betrivers"])]
                if market == "spreads_h1":
                    mb = R.modal_best(y, "home", "away")
                    z = mb.rename(columns={"best_pa": "price", "book_a": "bookmaker"})[["game_id", "line", "price", "bookmaker"]]
                else:
                    y = y[y.pa >= -200]
                    z = y.assign(_d=L1.dec(y.pa)).sort_values(["game_id", "_d"], ascending=[True, False]) \
                        .drop_duplicates("game_id")[["game_id", "line", "pa", "bookmaker"]].rename(columns={"pa": "price"})
            else:
                y = x[x.bookmaker == book]
                if market == "h2h_h1":
                    y = y[y.pa >= -200]
                z = y[["game_id", "line", "pa", "bookmaker"]].rename(columns={"pa": "price"})
            z = z.merge(g1[["game_id", "season", "game_date", "h1_margin", "h1_total"]], on="game_id")
            z["side"] = "home"
            z["margin"], z["total"] = z.h1_margin, z.h1_total
            z = L1.grade_rows(z, market)
            if market == "spreads_h1":
                z["grp"] = np.where(z.line < 0, "home favourite", np.where(z.line > 0, "home underdog", "pick'em"))
            else:
                z["grp"] = np.where(z.price < 0, "home favourite", "home underdog")
            out[(market, book)] = z
            rows.append(R.reg(EXP, f"A2 home {market} {book}", z) | {"subset": "2025-26 + 2026-27"})
            for s, xs in z.groupby("season"):
                rows.append(R.row({"experiment": EXP, "cell": f"A2 home {market} {book}", "subset": f"season {int(s)}"}, xs))
            if book.startswith("best"):
                for lab in ("home underdog", "home favourite"):
                    xs = z[z.grp == lab]
                    rows.append(R.reg(EXP, f"A2 home {market} {book}, {lab}", xs) | {"subset": lab})
                    for s, xss in xs.groupby("season"):
                        rows.append(R.row({"experiment": EXP, "cell": f"A2 home {market} {book}, {lab}", "subset": f"season {int(s)}"}, xss))
    md.append(R.table(rows))
    for key, lab in ((("h2h_h1", "best of fanduel/betrivers"), "A2 first-half moneyline, home underdog, best of FanDuel/BetRivers"),
                     (("spreads_h1", "best of fanduel/betrivers"), "A2 first-half spread, home underdog, best of FanDuel/BetRivers")):
        x = out[key]
        x = x[x.grp == "home underdog"]
        md.append(f"\nKill rows, {lab}: price range {R.price_range(x)}\n")
        md.append(R.table(R.kill_rows(lab, x, fav_col=None)))
    return out


def a3(md: list):
    with contextlib.redirect_stdout(io.StringIO()):
        import r2_leads as LD
    g, cb = LD.g, LD.cb
    okid = set(g.game_id[g.grp.isin(["own country", "own country, attendance 1-999", "own country, attendance missing (0)"])])
    b = cb[(cb.market == "spreads") & (cb.bookmaker == "draftkings") & cb.game_id.isin(okid)]
    z = L2.sides_long(b)
    z = L2.grade(z[(z.side == "home") & (z.line > 0)])
    md.append("\n### A3. Round 1's frozen home-underdog spread rule, read unchanged (r3_a_home.py)\n")
    md.append("Rule: home against the spread at the DraftKings close when the home line is above 0, "
              "own-country games only. Round 1 (all seasons): 454 bets, +48.34 units, +9.72%; its 2026-27 row: "
              "30 bets, -8.10 units, -24.06%.\n")
    rows = [R.row({"subset": "all seasons (reproduction check)"}, z)]
    rows.append(R.reg(EXP, "A3 frozen home underdog ATS, 2026-27 read", z[z.season == 2027]) | {"subset": "2026-27 (no new games since round 1)"})
    rows.append(R.row({"subset": "2021-22 to 2025-26"}, z[z.season <= 2026]))
    md.append(R.table(rows))
    last = g[g.season == 2027].game_date.max()
    md.append(f"\nLast played 2026-27 game in the cache: {last}; 2026-27 bets read: {int((z.season == 2027).sum())}. "
              "These are the games round 1 already read, so this is a reproduction, not a hold-out.")
    return z


def run():
    md = ["\n## A. The home lean (r3_a_home.py)\n"]
    a1(md)
    a2(md)
    a3(md)
    return "\n".join(md)


if __name__ == "__main__":
    print(run())
