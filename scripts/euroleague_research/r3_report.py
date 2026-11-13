"""Round 2: run every r3 experiment, apply Benjamini-Hochberg across every
counted cell, and write the tables into the results file under its
pre-registration (section 0, written before any r3 script ran) and its
verdicts (written by hand from these tables). Re-running replaces only the
generated part, below the marker.

    python scripts/euroleague_research/r3_report.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

import r2_lib as L2
import r3_lib as R
import r3_a_home as A
import r3_b_anchored as B
import r3_c_totals as C
import r3_d_periods as D

OUT = Path(r"C:\Users\micha\AppData\Local\Temp\euroleague_round2.md")
MARK = "\n<!-- r3_report.py output below this line; regenerated on every run -->\n"


def main():
    parts = []
    for mod in (A, B, C, D):
        parts.append(mod.run())
    reg = pd.DataFrame(R.REG)
    reg["survives BH 10%"] = L2.bh(reg.p_one.to_numpy(float), 0.10)
    reg["25+ bets"] = reg.bets >= 25
    n = len(reg)
    k = int(reg["survives BH 10%"].sum())
    k25 = int((reg["survives BH 10%"] & reg["25+ bets"]).sum())
    big = reg[reg["25+ bets"]].copy()
    big_s = L2.bh(big.p_one.to_numpy(float), 0.10)
    bh = ["\n## Multiplicity (r3_report.py)\n",
          f"Cells counted (pre-registered grid and band cells at each experiment's main price): **{n}** "
          f"(planned 107). Surviving Benjamini-Hochberg at a 10% false-discovery rate: **{k}**, of which "
          f"{k25} hold 25+ bets (a cell under 25 bets is below the repo's floor: its p is from a handful of dates).\n",
          f"Sensitivity (not pre-registered): BH over the {len(big)} cells with 25+ bets only: "
          f"**{int(big_s.sum())}** survive.\n",
          "Counted cells by experiment: " + ", ".join(f"{e} {c}" for e, c in reg.groupby("experiment").size().items()) + "\n",
          "Every counted cell with a positive return, smallest p first:\n",
          L2.md_table(reg[reg["ret%"] > 0].sort_values("p_one").reset_index(drop=True)),
          "\nThe ten smallest p overall (with the BH threshold for each rank):\n"]
    top = reg.sort_values("p_one").head(10).reset_index(drop=True)
    top["bh p_threshold"] = [0.10 * (i + 1) / n for i in range(len(top))]
    bh.append(L2.md_table(top))
    text = OUT.read_text(encoding="utf-8")
    head = text.split(MARK)[0]
    OUT.write_text(head + MARK + "\n".join(parts) + "\n" + "\n".join(bh) + "\n", encoding="utf-8")
    print(f"wrote {OUT}: {n} counted cells, {k} survive BH")


if __name__ == "__main__":
    main()
