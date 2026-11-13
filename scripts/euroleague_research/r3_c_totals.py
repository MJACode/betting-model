"""Round 2, experiment C: full-game totals by referee crew, the opening total
and open-to-close movement (pre-registration: section 0.4 of
euroleague_round2.md). Returns / prints markdown.

    python scripts/euroleague_research/r3_c_totals.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import r2_lib as L2
import r3_lib as R

EXP = "C"
K_REF = 30.0
K_CREW = 10.0
C_GRID = [0.5, 1.0, 1.5, 2.0]
C_HEAD = 1.0
M_GRID = [1, 2, 3, 4]
M_HEAD = 2


def base():
    g, q, dt, cb, fp = R.fullgame()
    g = g[g.season >= 2022].copy()
    pin = R.one_book(cb, "totals", "pinnacle", cols=("line",), prefix="pin_")
    dk = R.one_book(cb, "totals", "draftkings", cols=("line",), prefix="dk_")
    g = g.merge(pin, on="game_id", how="left").merge(dk, on="game_id", how="left")
    g["close_total"] = g.pin_line.fillna(g.dk_line)
    g["close_src"] = np.where(g.pin_line.notna(), "pinnacle", np.where(g.dk_line.notna(), "draftkings", "none"))
    g["r"] = g.total - g.close_total
    g = g.sort_values("tip").reset_index(drop=True)
    return g, cb, fp


def ref_scores(g: pd.DataFrame) -> pd.DataFrame:
    idx = R.prior_index(g.tip)
    refs = g.referees.fillna("").str.split("|")
    s_sum, s_n, c_sum, c_n = {}, {}, {}, {}
    crew, exact, nprior = np.zeros(len(g)), np.zeros(len(g)), np.zeros(len(g))
    ptr = 0
    for i in range(len(g)):
        while ptr < idx[i]:
            if np.isfinite(g.r.iloc[ptr]) and refs.iloc[ptr] != [""]:
                rr = float(g.r.iloc[ptr])
                for j in refs.iloc[ptr]:
                    s_sum[j] = s_sum.get(j, 0.0) + rr
                    s_n[j] = s_n.get(j, 0) + 1
                key = frozenset(refs.iloc[ptr])
                c_sum[key] = c_sum.get(key, 0.0) + rr
                c_n[key] = c_n.get(key, 0) + 1
            ptr += 1
        rs = refs.iloc[i]
        if rs == [""]:
            crew[i] = exact[i] = np.nan
            continue
        crew[i] = np.mean([s_sum.get(j, 0.0) / (s_n.get(j, 0) + K_REF) for j in rs])
        nprior[i] = np.mean([s_n.get(j, 0) for j in rs])
        key = frozenset(rs)
        exact[i] = c_sum.get(key, 0.0) / (c_n.get(key, 0) + K_CREW)
    g = g.copy()
    g["crew_score"], g["exact_score"], g["ref_prior_n"] = crew, exact, nprior
    return g


def slope(x, y):
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b
    s2 = (res ** 2).sum() / max(len(y) - 2, 1)
    cov = s2 * np.linalg.inv(X.T @ X)
    return float(b[1]), float(np.sqrt(cov[1, 1]))


def rule_bets(g, cb, score_col, c):
    dk = cb[(cb.market == "totals") & (cb.bookmaker == "draftkings")]
    z = L2.sides_long(dk).merge(g[["game_id", score_col]], on="game_id")
    z = z[((z.side == "over") & (z[score_col] >= c)) | ((z.side == "under") & (z[score_col] <= -c))]
    z = L2.grade(z)
    z["fav"] = z.price < z.groupby("game_id").price.transform("max")
    return z


def run():
    md = ["\n## C. Totals (r3_c_totals.py)\n"]
    g, cb, fp = base()
    g = ref_scores(g)
    md.append(f"Played games 2021-22 on: {len(g)}; closing total from Pinnacle {int((g.close_src == 'pinnacle').sum())}, "
              f"from DraftKings {int((g.close_src == 'draftkings').sum())}, none {int((g.close_src == 'none').sum())}; "
              f"with a crew listed {int(g.referees.notna().sum())}. Mean residual (actual - close) "
              f"{g.r.mean():+.2f} points, SD {g.r.std():.2f}.\n")
    gr = g[(g.season >= 2023) & g.r.notna() & g.crew_score.notna()]
    md.append("Score distribution on the graded games (2022-23 on): " +
              ", ".join(f"{c}: SD {gr[c].std():.3f}, share |score| >= 1.0: {100 * (gr[c].abs() >= 1.0).mean():.1f}%"
                        for c in ("crew_score", "exact_score")) +
              f"; mean earlier games per referee {gr.ref_prior_n.mean():.0f}.\n")

    md.append("### C1. Does the prior crew score predict the residual? (out of sample by season)\n")
    rows = []
    for col in ("crew_score", "exact_score"):
        for s, x in list(gr.groupby("season")) + [("pooled 2023-2027", gr)]:
            b, se = slope(x[col].to_numpy(), x.r.to_numpy())
            rows.append({"score": col, "season": s, "games": len(x), "slope (pts per pt)": round(b, 3), "se": round(se, 3),
                         "t": round(b / se, 2) if se > 0 else np.nan,
                         "corr": round(float(np.corrcoef(x[col], x.r)[0, 1]), 4)})
    md.append(R.table(rows))

    md.append("\n### C2. The crew bet rule at the DraftKings closing total, 2022-23 on\n")
    rows = []
    bets = {}
    for col in ("crew_score", "exact_score"):
        for c in C_GRID:
            z = rule_bets(gr, cb, col, c)
            bets[(col, c)] = z
            rows.append(R.reg(EXP, f"C2 {col} rule, DK close, c {c}", z) | {"over share%": round(100 * float((z.side == 'over').mean()), 1) if len(z) else np.nan})
    md.append(R.table(rows))

    # placebo at the headline
    rng = np.random.default_rng(11)
    prow = []
    for col in ("crew_score", "exact_score"):
        z = bets[(col, C_HEAD)]
        real = 100 * z.units.sum() / z.risk.sum() if z.risk.sum() > 0 else np.nan
        out = []
        for _ in range(200):
            x = gr.copy()
            x[col] = x.groupby("season")[col].transform(lambda v: rng.permutation(v.to_numpy()))
            zz = rule_bets(x, cb, col, C_HEAD)
            out.append(100 * zz.units.sum() / zz.risk.sum() if zz.risk.sum() > 0 else np.nan)
        o = np.array(out)
        prow.append({"score": col, "real ret%": round(real, 2), "placebo mean ret%": round(float(np.nanmean(o)), 2),
                     "placebo 95th pct": round(float(np.nanpercentile(o, 95)), 2), "share >= real": round(float(np.nanmean(o >= real)), 3)})
    md.append("\nPlacebo at the headline c = 1.0 (scores shuffled across each season's games, 200 times):\n")
    md.append(R.table(prow))
    for col in ("crew_score", "exact_score"):
        z = bets[(col, C_HEAD)]
        md.append(f"\nKill rows, {col} rule at c = 1.0: price range {R.price_range(z)}\n")
        md.append(R.table(R.kill_rows(f"C2 {col} c 1.0", z, fav_col=None)))

    # the opening total
    md.append("\n### C3. DraftKings' first-post total, blind, by season\n")
    f = fp[(fp.market == "totals") & (fp.bookmaker == "draftkings") & (fp.season >= 2022)]
    z = L2.grade(L2.sides_long(f))
    rows = []
    for side in ("over", "under"):
        x = z[z.side == side]
        rows.append(R.reg(EXP, f"C3 DK first post {side}", x) | {"subset": "2021-22 on"})
        for s, xs in x.groupby("season"):
            rows.append(R.row({"experiment": EXP, "cell": f"C3 DK first post {side}", "subset": f"season {int(s)}"}, xs))
    md.append(R.table(rows))

    # movement
    md.append("\n### C4. DraftKings open-to-close total movement\n")
    op = f[["game_id", "line"]].rename(columns={"line": "dk_open"})
    gm = g.merge(op, on="game_id", how="inner")
    gm = gm[gm.dk_line.notna()]
    gm["move"] = gm.dk_line - gm.dk_open
    gm["r_dk"] = gm.total - gm.dk_line
    rows = []
    for s, x in list(gm.groupby("season")) + [("pooled", gm)]:
        b, se = slope(x.move.to_numpy(), x.r_dk.to_numpy())
        rows.append({"season": s, "games": len(x), "mean |move|": round(float(x.move.abs().mean()), 2),
                     "share moved": round(100 * float((x.move != 0).mean()), 1),
                     "slope of (actual - DK close) on move": round(b, 3), "se": round(se, 3),
                     "corr": round(float(np.corrcoef(x.move, x.r_dk)[0, 1]), 4)})
    md.append(R.table(rows))
    dkc = cb[(cb.market == "totals") & (cb.bookmaker == "draftkings")]
    zc = L2.sides_long(dkc).merge(gm[["game_id", "move"]], on="game_id")
    rows = []
    mv = {}
    for k in M_GRID:
        x = zc[((zc.side == "over") & (zc.move >= k)) | ((zc.side == "under") & (zc.move <= -k))]
        x = L2.grade(x)
        mv[k] = x
        rows.append(R.reg(EXP, f"C4 follow the DK move at the DK close, k {k}", x) | {"over share%": round(100 * float((x.side == 'over').mean()), 1) if len(x) else np.nan})
    md.append("\nFollow the move at the DraftKings close (over when the total rose by k or more, under when it fell by k or more):\n")
    md.append(R.table(rows))
    rows = []
    for k in M_GRID:
        x = zc[((zc.side == "under") & (zc.move >= k)) | ((zc.side == "over") & (zc.move <= -k))]
        rows.append(R.row({"rule": f"fade the move at the DK close, k {k} (mirror, not counted)"}, L2.grade(x)))
    md.append("\nThe mirror (fade the move), printed for the side control, not counted:\n")
    md.append(R.table(rows))
    x = mv[M_HEAD]
    md.append(f"\nKill rows, follow rule at k = 2: price range {R.price_range(x)}\n")
    md.append(R.table(R.kill_rows("C4 follow k 2", x, fav_col=None)))
    # hindsight ceiling
    zo = L2.sides_long(f).merge(gm[["game_id", "move"]], on="game_id")
    zo = zo[((zo.side == "over") & (zo.move > 0)) | ((zo.side == "under") & (zo.move < 0))]
    md.append("\nThe hindsight ceiling (bet DraftKings' first post in the direction of its later move; not a rule, not counted):\n")
    md.append(R.table([R.row({"ceiling": "first post, direction of the later move"}, L2.grade(zo))]))
    return "\n".join(md)


if __name__ == "__main__":
    print(run())
