"""Apply the pre-declared CLEARS rule to every named-reference cell. Reads grid.csv only."""
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import numpy as np
import pandas as pd

pd.set_option("display.width", 280); pd.set_option("display.max_columns", 80); pd.set_option("display.max_rows", 900)
OUT = str(WORK / "props")
NAMED = ["pinnacle", "bovada", "betonlineag", "consensus"]
RETAIL = ["draftkings", "fanduel", "betmgm", "williamhill_us", "betrivers", "hardrockbet", "espnbet", "fliff",
          "rebet", "fanatics"]


def verdict(grid_path=OUT + r"\grid.csv"):
    r = pd.read_csv(grid_path, dtype={"season": str})
    rows = []
    for (v, s, cut), grp in r.groupby(["variant", "season", "cut"]):
        plc = grp[grp.ref.isin(RETAIL) & (grp.bets >= 50)]
        best_plc = plc.roi.max() if len(plc) else np.nan
        best_plc_ref = plc.loc[plc.roi.idxmax(), "ref"] if len(plc) else None
        allp = grp[grp.ref.isin(RETAIL) & (grp.bets > 0)]
        for _, x in grp[grp.ref.isin(NAMED)].iterrows():
            c1 = x.bets >= 150
            c2 = (x.h1_bets > 0) and (x.h2_bets > 0) and (x.h1_roi > 0) and (x.h2_roi > 0)
            c3a = bool(x.ci_lo > 0) if pd.notna(x.ci_lo) else False
            c3b = bool(x.clv_mean > 0) if pd.notna(x.get("clv_mean", np.nan)) else False
            c3 = c3a or c3b
            if x.bets == 0:
                c4, c4txt = False, "no bets"
            elif len(plc) == 0:
                c4, c4txt = False, "no placebo with >=50 bets"
            else:
                c4 = bool(x.roi > best_plc)
                c4txt = f"best placebo {best_plc_ref} {best_plc:+.4f}"
            rank = int((allp.roi > x.roi).sum() + 1) if x.bets > 0 else np.nan
            rows.append(dict(variant=v, season=s, ref=x.ref, cut=cut, bets=int(x.bets), roi=x.roi,
                             ci_lo=x.ci_lo, ci_hi=x.ci_hi, h1_roi=x.h1_roi, h2_roi=x.h2_roi,
                             clv_n=x.get("clv_n", np.nan), clv_mean=x.get("clv_mean", np.nan),
                             c1_150_bets=c1, c2_both_halves_pos=c2, c3_ci_or_close=c3, c4_beats_placebos=c4,
                             placebo_note=c4txt, rank_among_refs_with_bets=rank,
                             n_placebos_with_bets=len(allp), CLEARS=bool(c1 and c2 and c3 and c4)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    v = verdict()
    v.to_csv(OUT + r"\verdict.csv", index=False)
    print("named cells:", len(v), " with bets:", int((v.bets > 0).sum()), " CLEAR:", int(v.CLEARS.sum()))
    print(v.groupby("variant")[["c1_150_bets", "c2_both_halves_pos", "c3_ci_or_close", "c4_beats_placebos", "CLEARS"]].sum())
    print("\ncells meeting the 150-bet bar:\n", v[v.c1_150_bets].round(4).to_string(index=False))
    print("\ncells failing ONLY one criterion:\n",
          v[(v[["c1_150_bets", "c2_both_halves_pos", "c3_ci_or_close", "c4_beats_placebos"]].sum(axis=1) == 3)].round(4).to_string(index=False))
