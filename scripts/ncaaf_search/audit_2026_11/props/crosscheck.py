"""Independent re-computation of three cells by a different code path (plain loops over raw rows, raw snapshot_at
as the pull key, no helper from main.py except the name normaliser and the actuals table)."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

OUT = str(WORK / "props")
sys.path.insert(0, OUT)
import main as M   # noqa: E402

np.seterr(divide="ignore")
p, g, lt = M.load()
q = M.build_quotes(p, list(M.MARKET_STAT))
actuals, _ = M.build_actuals(q, g, lt)
act = {(r.game_id, r.nn, r.market): (r.status, r.actual) for r in actuals.itertuples()}
grid = pd.read_csv(OUT + r"\grid.csv", dtype={"season": str})


def imp1(x):
    return 100.0 / (x + 100.0) if x > 0 else -x / (-x + 100.0)


def run(season, ref, cut, devig_soft=False):
    rows = p[(p.season == season) & p.pre & p.market.isin(list(M.MARKET_STAT)) & p.over_price.notna()
             & p.under_price.notna() & p.line.notna()]
    board = defaultdict(dict)          # (game, player, market, ts) -> {book: (line, o, u)}
    for r in rows.itertuples():
        board[(r.game_id, M.norm(r.player_name), r.market, r.ts)][r.bookmaker] = (r.line, r.over_price, r.under_price)
    first = {}                         # prop -> (ts, edge, prio, sidecode, book, side, price)
    for (gid, nn, mk, ts), books in board.items():
        if ref not in books:
            continue
        rl, ro, ru = books[ref]
        io, iu = imp1(ro), imp1(ru)
        fo, fu = io / (io + iu), iu / (io + iu)
        for bk, (l, o, u) in books.items():
            if bk == ref or bk not in M.BETTABLE or l != rl:
                continue
            so, su = imp1(o), imp1(u)
            for side, fair, pr, raw, other in (("over", fo, o, so, su), ("under", fu, u, su, so)):
                e = fair - (raw / (raw + other) if devig_soft else raw)
                if e < cut - 1e-12:
                    continue
                cand = (ts, -e, M.PRIO[bk], 0 if side == "over" else 1, bk, side, pr, l)
                k = (gid, nn, mk)
                if k not in first or cand[:4] < first[k][:4]:
                    first[k] = cand
    n = w = l_ = 0
    units = risk = 0.0
    for k, c in first.items():
        st, a = act.get(k, ("missing", np.nan))
        if st not in ("matched", "matched_fallback"):
            continue
        line, side, price = c[7], c[5], c[6]
        b = price / 100.0 if price > 0 else 100.0 / abs(price)
        rk = min(1.0 / b, 3.0)
        if a == line:
            n += 1; risk += rk; continue
        won = (a > line) if side == "over" else (a < line)
        n += 1; risk += rk
        if won:
            w += 1; units += rk * b
        else:
            l_ += 1; units -= rk
    return n, w, l_, units, risk


for variant, season, ref, cut, dv in (("PRIMARY", 2026, "pinnacle", 0.02, False),
                                      ("PRIMARY", 2025, "betonlineag", 0.02, False),
                                      ("PRIMARY", 2026, "bovada", 0.03, False),
                                      ("S4_POSTHOC_repo_edge_def", 2026, "pinnacle", 0.02, True),
                                      ("S4_POSTHOC_repo_edge_def", 2025, "betonlineag", 0.04, True)):
    n, w, l_, u, rk = run(season, ref, cut, dv)
    x = grid[(grid.variant == variant) & (grid.season == str(season)) & (grid.ref == ref) & np.isclose(grid.cut, cut)].iloc[0]
    ok = (n == x.bets) and (w == x.W) and (l_ == x.L) and abs(u - x.units) < 1e-6 and abs(rk - x.risked) < 1e-6
    print(f"{variant} {season} {ref} {cut}: independent {n} bets {w}-{l_} {u:+.4f}u risk {rk:.4f} | grid {int(x.bets)} bets "
          f"{int(x.W)}-{int(x.L)} {x.units:+.4f}u risk {x.risked:.4f} | {'MATCH' if ok else 'DIFFERENT'}")

# spot-check graded actuals against the raw log for a handful of bets
bets = pd.read_parquet(OUT + r"\bets.parquet")
s = bets[(bets.variant == "PRIMARY") & (bets.ref == "pinnacle") & (bets.cut == 0.02) & (bets.season == 2026)].head(6)
lt["nn"] = lt.player_name.map(M.norm)
for r in s.itertuples():
    col = M.MARKET_STAT[r.market]
    d = pd.to_datetime(r.game_date)
    m = lt[(lt.nn == r.nn) & (lt.season == 2026) & ((pd.to_datetime(lt.game_date) - d).abs() <= pd.Timedelta(days=1))]
    print(r.game_id, r.nn, r.market, "line", r.line, r.side, "graded actual", r.actual, r.result,
          "| raw log:", m[["game_id", "team", "player_name", col]].to_dict("records"))
