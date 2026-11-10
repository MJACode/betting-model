"""The live totals rule (|model - DraftKings total| >= 8), on walk-forward predictions 2022-2025.

Questions, fixed before reading results:
  A. Does the win rate rise with the size of the disagreement? (would a bigger stake on a band be earned)
  B. The rule decides against DraftKings' total and bets DraftKings' LINE at the best price.
     What does taking the best LINE among the deciding books add? (2023-2025, the stored pulls)
  C. The live shape: first morning read, 5 days out to game day, at which the gate is crossed.
"""
from pathlib import Path

import numpy as np
import pandas as pd

import lab
from lab import D, BETTABLE, dec, stake

pd.set_option("display.width", 250)
pd.set_option("display.max_rows", 300)
RNG = np.random.default_rng(7)


def summ(tag, res, price, dates=None):
    res = np.asarray(res, float)
    price = np.asarray(price, float)
    risk, win = stake(dec(price))
    pnl = np.where(res > 0, win, np.where(res < 0, -risk, 0.0))
    rk = np.where(res != 0, risk, 0.0)
    w, l, p = int((res > 0).sum()), int((res < 0).sum()), int((res == 0).sum())
    ci = ""
    if dates is not None and len(res) > 20:
        df = pd.DataFrame({"d": np.asarray(dates), "p": pnl, "r": rk}).groupby("d").sum()
        idx = RNG.integers(0, len(df), size=(2000, len(df)))
        boot = df.p.to_numpy()[idx].sum(1) / np.maximum(df.r.to_numpy()[idx].sum(1), 1e-9)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        ci = f" [{100*lo:+.1f},{100*hi:+.1f}]"
    print(f"{tag:<46} {len(res):>4} {w:>3}-{l:<3}-{p:<2} {pnl.sum():>+7.2f}u {100*pnl.sum()/max(rk.sum(),1e-9):>+6.1f}%{ci}  win {w/max(w+l,1):.3f}")
    return pnl.sum()


pred = pd.read_parquet(D / "totals_oos.parquet").rename(columns={"_game_id": "game_id", "_season": "season", "_total": "total", "_total_line": "close"})
pred["d"] = pred.pred - pred.close
g = pd.read_parquet(D / "g.parquet")
pred = pred.merge(g[["game_id", "et_date", "week"]], on="game_id", how="left")
print("OOS games:", pred.groupby("season").size().to_dict(), "| mean(model-close):", pred.groupby("season").d.mean().round(2).to_dict())

print("\n== A. at the CFBD close, -110 both ways, by size of the disagreement (2022-2025) ==")
for lo, hi in ((0, 2), (2, 4), (4, 6), (6, 7), (7, 8), (8, 9), (9, 10), (10, 12), (12, 15), (15, 99), (8, 99), (10, 99)):
    x = pred[(pred.d.abs() >= lo) & (pred.d.abs() < hi)]
    res = np.sign(np.where(x.d > 0, x.total - x.close, x.close - x.total))
    summ(f"|d| {lo}-{hi}", res, np.full(len(x), -110.0), x.et_date)
for s in (2022, 2023, 2024, 2025):
    for lo, hi in ((8, 10), (10, 99)):
        x = pred[(pred.d.abs() >= lo) & (pred.d.abs() < hi) & (pred.season == s)]
        res = np.sign(np.where(x.d > 0, x.total - x.close, x.close - x.total))
        summ(f"  {s} |d| {lo}-{hi}", res, np.full(len(x), -110.0))
for side, m in (("over", pred.d >= 8), ("under", pred.d <= -8)):
    x = pred[m]
    res = np.sign(np.where(x.d > 0, x.total - x.close, x.close - x.total))
    summ(f"  {side} at 8+", res, np.full(len(x), -110.0), x.et_date)

# ── B / C need the stored pulls (2023-2025) ──────────────────────────────────
_, q = lab.load()
q = q[q.total_line.notna() & q.over_price.notna() & q.under_price.notna() & lab._sanity(dec(q.over_price), dec(q.under_price))]
canon = g.set_index("game_id").twin_of
q["canon"] = q.game_id.map(canon).fillna(q.game_id)
P = pred.set_index("game_id")
q = q[q.canon.isin(P.index)].copy()
q["pred"] = q.canon.map(P.pred)
print("\ngames with both a walk-forward prediction and stored pulls:", q.canon.nunique(), q.groupby("season").canon.nunique().to_dict())


def decide(slotq):
    """One slot: the rule's decision per game against DraftKings' total, and three ways to place it."""
    dk = slotq[slotq.bookmaker == "draftkings"].drop_duplicates("game_id").set_index("game_id")
    dk = dk.assign(d=dk.pred - dk.total_line)
    hit = dk[dk.d.abs() >= 8].copy()
    hit["side"] = np.where(hit.d > 0, "over", "under")
    rows = []
    bb = slotq[slotq.bookmaker.isin(BETTABLE)]
    for gid, r in hit.iterrows():
        x = bb[bb.game_id == gid]
        over = r.side == "over"
        pr_col = "over_price" if over else "under_price"
        # (i) DraftKings line and price
        a = dict(line_dk=r.total_line, price_dk=r[pr_col])
        # (ii) DraftKings' line, best price among deciding books at that line (the live rule)
        same = x[x.total_line == r.total_line]
        a["price_bestprice"] = same[pr_col].iloc[int(np.argmax(dec(same[pr_col])))] if len(same) else r[pr_col]
        # (iii) best LINE among deciding books for the side (price -120 or longer), then best price
        ok = x[dec(x[pr_col]) >= dec(-120)]
        if len(ok):
            ok = ok.assign(_d=dec(ok[pr_col]))
            ok = ok.sort_values(["total_line", "_d"], ascending=[over, False])
            a["line_best"], a["price_bestline"], a["book_bestline"] = ok.total_line.iloc[0], ok[pr_col].iloc[0], ok.bookmaker.iloc[0]
        else:
            a["line_best"], a["price_bestline"], a["book_bestline"] = r.total_line, r[pr_col], "draftkings"
        a.update(game_id=gid, side=r.side, d=r.d, total=r.total, et_date=r.et_date, season=r.season, close=r.close_total)
        rows.append(a)
    return pd.DataFrame(rows)


def res_of(b, line_col):
    return np.sign(np.where(b.side == "over", b.total - b[line_col], b[line_col] - b.total))


def report(tag, b):
    if not len(b):
        print(tag, "0 bets")
        return
    print(f"-- {tag}: {len(b)} bets; over {int((b.side=='over').sum())}, under {int((b.side=='under').sum())}")
    summ("   DraftKings line, DraftKings price", res_of(b, "line_dk"), b.price_dk, b.et_date)
    summ("   DraftKings line, best price (live rule)", res_of(b, "line_dk"), b.price_bestprice, b.et_date)
    summ("   best line among deciding books", res_of(b, "line_best"), b.price_bestline, b.et_date)
    better = np.where(b.side == "over", b.line_dk - b.line_best, b.line_best - b.line_dk)
    print(f"   best line beats DraftKings' by: mean {better.mean():.3f} pts; share >=0.5: {(better>=0.5).mean():.3f}; >=1.0: {(better>=1.0).mean():.3f}"
          f" | flips a result on {int((res_of(b,'line_dk') != res_of(b,'line_best')).sum())} bets")
    clv = np.where(b.side == "over", b.close - b.line_dk, b.line_dk - b.close)
    print(f"   DraftKings line vs CFBD close, points in the bet's favour: mean {np.nanmean(clv):+.3f}")
    for s, x in b.groupby("season"):
        summ(f"     {int(s)} best line", res_of(x, "line_best"), x.price_bestline)


print("\n== B. game-day morning read (D0_AM) ==")
b0 = decide(q[q.slot == "D0_AM"])
report("D0_AM", b0)

print("\n== C. first morning read that crosses the gate, 5 days out to game day ==")
seen, parts = set(), []
for k in (5, 4, 3, 2, 1, 0):
    b = decide(q[(q.slot == f"D{k}_AM") & ~q.game_id.isin(seen)])
    if len(b):
        seen |= set(b.game_id)
        parts.append(b.assign(lead=k))
fc = pd.concat(parts)
report("first cross D5..D0", fc)
print(fc.groupby("lead").size().to_dict())
fc.to_pickle(D / "totals_firstcross.pkl")
