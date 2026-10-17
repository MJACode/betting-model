"""
Robustness checks on the sharp-vs-soft UNDER signal found by scripts/nba_prop_market_lab.py (section 3).

Question: is "bet the under at a bettable book when Pinnacle's no-vig under, at the same line in the same
snapshot, makes it +EV" real information, or an artefact? Checks:
  A. each soft book alone (a single stale or mispriced book carrying the result is the stale-quote tell);
  B. the bet book against the OTHER soft books at the same line: is the bet book an outlier (its under
     implied far from the soft median) or does it agree with them (Pinnacle alone disagrees)?
  C. price bands of the under taken;
  D. injury news: the player's own status, and whether either team's official injury report changed in the
     3 hours before the snapshot (reports with report_ts <= snapshot_at only);
  E. per market x season at the floors around the chosen one.
Every number is units, one unit to win, best bettable price, whole-day bootstrap CI (seed 7).

Run: PYTHONPATH=. PYTHONIOENCODING=utf-8 python -m scripts.nba_prop_market_robust
Writes C:/Users/micha/AppData/Local/Temp/nba_rebuild/results/props_market_robust.md
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts.nba_prop_market_lab import (BETTABLE, CACHE, OUT, SEASONS, SEASON_NAME, SHORT, YESNO, WORK, add_units,
                                          best_per_key, candidates_from, fmt, load_quotes, md_table, power_devig,
                                          roi_n, soft_rows, summ)

LINES: list[str] = []


def say(s: str = "") -> None:
    print(s, flush=True)
    LINES.append(s)


def main() -> None:
    q, _ = load_quotes(False)
    u = q[q.usable & q.x.notna()]
    pin = u[(u.bookmaker == "pinnacle") & u.coherent][["game_id", "player_id", "market", "line", "od", "ud"]].copy()
    pin["fair_prop"] = (1 / pin.od) / (1 / pin.od + 1 / pin.ud)
    pin["fair_pow"] = power_devig(pin.od.values, pin.ud.values)
    pin_markets = [m for m in pin.market.unique() if (pin.market == m).sum() >= 300]
    soft = soft_rows(u, BETTABLE)
    soft = soft[soft.market.isin(pin_markets)]
    m = soft.merge(pin[["game_id", "player_id", "market", "line", "fair_prop", "fair_pow"]], on=["game_id", "player_id", "market", "line"])
    # soft-median under implied at the same line, excluding the book itself (B)
    tw = u[u.coherent & u.bookmaker.isin(BETTABLE)][["game_id", "player_id", "market", "line", "bookmaker", "od", "ud"]].copy()
    tw["pu"] = (1 / tw.ud) / (1 / tw.od + 1 / tw.ud)
    c = candidates_from(m, "fair_prop")
    c = c[c.side == "under"].reset_index(drop=True)
    c["cid"] = np.arange(len(c))
    j = c[["cid", "game_id", "player_id", "market", "line", "bookmaker"]].merge(
        tw[["game_id", "player_id", "market", "line", "bookmaker", "pu"]].rename(columns={"bookmaker": "ob"}),
        on=["game_id", "player_id", "market", "line"])
    j = j[j.ob != j.bookmaker]
    med = j.groupby("cid").pu.agg(["median", "size"]).rename(columns={"median": "soft_med_under", "size": "n_soft"})
    c = c.join(med, on="cid")
    c["own_under"] = (1 / c.ud) / (1 / c.od + 1 / c.ud)
    c["own_minus_soft_pp"] = 100 * (c.own_under - c.soft_med_under)     # negative = this book's under is cheaper than the others
    c["pin_minus_soft_pp"] = 100 * (c.fair_prob - c.soft_med_under)      # Pinnacle's no-vig under vs the soft median

    say("# Robustness of the sharp-vs-soft UNDER signal (props_market)")
    say()
    say("Population: every bettable two-way under quote at Pinnacle's exact line, same snapshot; EV = Pinnacle proportional "
        "no-vig under x decimal - 1; one bet per (game, player, market) = the best under price. ROI % (bets).")
    say()
    floors = [0.0, 0.02, 0.03, 0.04, 0.05, 0.06]
    best = best_per_key(c, ("under",))
    # A. each book alone
    say("## A. Each soft book alone (the rule run with only that book as the bettable one)")
    say()
    rows = {}
    for bk in BETTABLE:
        cb = c[c.bookmaker == bk]
        if len(cb) < 500:
            continue
        bb = best_per_key(cb, ("under",))
        rows[bk] = {f"EV>={f:.2f}": roi_n(bb[bb.ev >= f]) for f in floors}
        bb0 = bb[bb.ev >= 0.0]
        rows[bk].update({f"{SEASON_NAME[s]} @0.00": roi_n(bb0[bb0.season == s]) for s in SEASONS})
    say(md_table(pd.DataFrame(rows).T))
    say()
    say("Units by the book the pooled rule actually bet (best price), EV >= 0.00 and >= 0.03:")
    say()
    for f in (0.0, 0.03):
        d = best[best.ev >= f]
        bb = d.groupby("bookmaker").agg(n=("units", "size"), units=("units", "sum"), risk=("risk", "sum"))
        bb["roi"] = 100 * bb.units / bb.risk
        say(f"EV >= {f:.2f}:")
        say()
        say(md_table(bb.sort_values("units"), floatfmt="{:.1f}"))
        say()
    # B. outlier vs agreement
    say("## B. Is the bet book an outlier among the soft books, or does only Pinnacle disagree?")
    say()
    say("own_minus_soft = the bet book's no-vig under minus the median of the OTHER bettable books at the same line "
        "(negative = the bet book's under is cheaper than the other soft books). pin_minus_soft = Pinnacle's no-vig under "
        "minus that same soft median (positive = Pinnacle leans under harder than the soft books).")
    say()
    d0 = best[(best.ev >= 0.0) & best.n_soft.notna()]
    d0 = d0.assign(ob=pd.cut(d0.own_minus_soft_pp, [-100, -3, -1.5, -0.5, 0.5, 100],
                             labels=["<-3", "-3..-1.5", "-1.5..-0.5", "-0.5..+0.5", ">+0.5"]))
    t = d0.groupby("ob", observed=True).apply(lambda d: pd.Series({"bets": len(d), "roi": fmt(summ(d, ci=True), ci=True)}))
    say("EV >= 0.00, by own_minus_soft (pp):")
    say()
    say(md_table(t))
    say()
    d0 = d0.assign(pb=pd.cut(d0.pin_minus_soft_pp, [-100, 0, 1, 2, 3, 5, 100], labels=["<=0", "0-1", "1-2", "2-3", "3-5", ">5"]))
    t = d0.groupby("pb", observed=True).apply(lambda d: pd.Series({"bets": len(d), "roi": fmt(summ(d, ci=True), ci=True)}))
    say("EV >= 0.00, by pin_minus_soft (pp):")
    say()
    say(md_table(t))
    say()
    # agreement-only subset across floors
    agree = best[best.own_minus_soft_pp.abs() <= 0.5]
    say("Only bets where the bet book agrees with the other soft books within 0.5pp (so the gap is Pinnacle's view, "
        "not one stale book):")
    say()
    say(md_table(pd.DataFrame({f"EV>={f:.2f}": {"all": roi_n(agree[agree.ev >= f]),
                                                 **{SEASON_NAME[s]: roi_n(agree[(agree.ev >= f) & (agree.season == s)]) for s in SEASONS}}
                               for f in floors})))
    say()
    # C. price bands
    say("## C. Price band of the under taken (EV >= 0.00)")
    say()
    d0 = best[best.ev >= 0.0]
    d0 = d0.assign(pb=pd.cut(d0.price, [-10000, -200, -150, -125, -110, -101, 99, 10000],
                             labels=["<=-200", "-199..-150", "-149..-125", "-124..-110", "-109..-101", "+100..+99", ">=+100"]))
    t = d0.groupby("pb", observed=True).apply(lambda d: pd.Series({"bets": len(d), "roi": fmt(summ(d, ci=True), ci=True)}))
    say(md_table(t))
    say()
    # D. injury news
    say("## D. Injury news at decision time (official report, report_ts <= the prop snapshot)")
    say()
    inj = pd.read_parquet(CACHE / "nba_injury_report.parquet",
                          columns=["report_ts", "game_date", "game_id", "team", "player_id", "player_name", "status"])
    inj = inj[inj.status.isin(["Out", "Questionable", "Doubtful", "Probable", "Available"])]
    inj = inj[inj.game_id.isin(best.game_id.unique())]
    snap = q.drop_duplicates("game_id")[["game_id", "snapshot_at"]]
    snap["snap"] = pd.to_datetime(snap.snapshot_at, utc=True, format="ISO8601")
    inj = inj.merge(snap[["game_id", "snap"]], on="game_id")
    inj = inj[inj.report_ts <= inj.snap]
    last = inj.groupby("game_id").report_ts.max().rename("t_last")
    inj = inj.join(last, on="game_id")
    cur = inj[inj.report_ts == inj.t_last]
    prev_t = inj[inj.report_ts <= inj.t_last - pd.Timedelta(hours=3)].groupby("game_id").report_ts.max().rename("t_prev")
    inj = inj.join(prev_t, on="game_id")
    prev = inj[inj.report_ts == inj.t_prev]
    a = cur[["game_id", "player_id", "status"]].dropna(subset=["player_id"]).drop_duplicates(["game_id", "player_id"])
    b = prev[["game_id", "player_id", "status"]].dropna(subset=["player_id"]).drop_duplicates(["game_id", "player_id"])
    ab = a.merge(b, on=["game_id", "player_id"], how="outer", suffixes=("", "_prev"))
    changed = ab[(ab.status != ab.status_prev)].groupby("game_id").size().rename("n_changed")
    games_cov = set(cur.game_id)
    best2 = best.merge(a.rename(columns={"status": "own_status"}), on=["game_id", "player_id"], how="left")
    best2 = best2.join(changed, on="game_id")
    best2["own_status"] = np.where(best2.game_id.isin(games_cov), best2.own_status.fillna("not listed"), "no report")
    best2["news3h"] = np.where(~best2.game_id.isin(games_cov), "no report",
                               np.where(best2.n_changed.fillna(0) > 0, "report changed in last 3h", "no change in 3h"))
    for col in ("own_status", "news3h"):
        rows = {}
        for f in (0.0, 0.03, 0.05):
            d = best2[best2.ev >= f]
            for k, dd in d.groupby(col):
                rows.setdefault(k, {})[f"EV>={f:.2f}"] = roi_n(dd)
        say(f"By {col}:")
        say()
        say(md_table(pd.DataFrame(rows).T))
        say()
    # blind under on the same split, for comparison
    blind = add_units(c.sort_values("dec", ascending=False).drop_duplicates(["game_id", "player_id", "market"]))
    blind = blind.merge(best2[["game_id", "player_id", "market", "news3h"]], on=["game_id", "player_id", "market"], how="left")
    say("Blind under at the best price on the same eligible population, by news3h: " +
        "; ".join(f"{k} {roi_n(d)}" for k, d in blind.groupby("news3h")))
    say()
    # E. market x season
    say("## E. Market x season, under only (prop de-vig)")
    say()
    rows = {}
    for mk in sorted(best.market.unique(), key=lambda x: list(SHORT).index(x)):
        for f in (0.0, 0.03, 0.05):
            d = best[(best.market == mk) & (best.ev >= f)]
            rows[f"{SHORT[mk]} EV>={f:.2f}"] = {SEASON_NAME[s]: roi_n(d[d.season == s]) for s in SEASONS}
            rows[f"{SHORT[mk]} EV>={f:.2f}"]["all"] = fmt(summ(d, ci=True), ci=True)
    say(md_table(pd.DataFrame(rows).T))
    say()
    best2.to_parquet(OUT / "props_market_robust_under_bets.parquet", index=False)
    (OUT / "props_market_robust.md").write_text("\n".join(LINES), encoding="utf-8")


if __name__ == "__main__":
    main()
