"""Round 4 (halftime): run every experiment in one process (so the
Benjamini-Hochberg registry holds every graded cell) and write the results
file after its pre-registration (section 0, kept unchanged)."""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

import r4_lib as L
import r1_lib as L1
import r4_coverage
import r4_baselines
import r4_ported
import r4_kill
import r4_structure
import r4_posthoc


def bh_section() -> str:
    R = pd.DataFrame(L.REG)
    R = R[R.bets > 0].reset_index(drop=True)
    out = []
    for lab, sub in (("every graded cell", R), ("cells with 25+ bets", R[R.bets >= 25].reset_index(drop=True))):
        surv = L1.bh(sub.p_one.to_numpy(), 0.10)
        s = sub[surv]
        out.append(f"**{lab}: {len(sub)} cells; {int(surv.sum())} survive at a 10% false-discovery rate.**")
        if len(s):
            out.append(L.md(s.sort_values("p_one").to_dict("records")))
    # secondary reads, NOT pre-registered (labelled): the method cells alone, and the spread family alone
    meth = R[R.experiment.str.startswith("3 ") | R.experiment.str.startswith("P1")].reset_index(drop=True)
    sp = R[R.experiment.str.startswith("3 ") & R.cell.str.startswith("spread")].reset_index(drop=True)
    for lab, sub in (("secondary, not pre-registered: the method cells only (experiment 3 and P1)", meth),
                     ("secondary, not pre-registered: the 25 spread cells of experiment 3 only (a family chosen "
                      "after seeing it; the cells share most of their bets)", sp)):
        surv = L1.bh(sub.p_one.to_numpy(), 0.10)
        out.append(f"**{lab}: {len(sub)} cells; {int(surv.sum())} survive at 10%.**")
        if surv.any():
            out.append(L.md(sub[surv].sort_values("p_one").to_dict("records")))
    top = R.sort_values("p_one").head(15)
    out.append("The 15 smallest one-sided p-values (date bootstrap, `r2_lib.p_one_sided`):\n\n" + L.md(top.to_dict("records")))
    n_exp = R.groupby("experiment").size().rename("cells").reset_index()
    out.append("Cells per experiment:\n\n" + L.md(n_exp.to_dict("records")))
    return "\n\n".join(out)


def main():
    t0 = time.time()
    text = L.OUT.read_text(encoding="utf-8")
    head = text.split("\n---\n")[0] + "\n---\n"
    parts = [head]
    parts.append(L.section("1. Coverage, data notes and what a live loop gets", "r4_coverage.py", r4_coverage.run()))
    parts.append(L.section("2. Baselines at halftime", "r4_baselines.py", r4_baselines.run()))
    parts.append(L.section("3. The women's college halftime method, ported unchanged, then the variants", "r4_ported.py",
                           r4_ported.run()))
    parts.append(L.section("3b. Kill tests on what read positive", "r4_kill.py", r4_kill.run()))
    parts.append(L.section("4. Structural check: are halftime lines re-hung mechanically, and where do they miss?",
                           "r4_structure.py", r4_structure.run()))
    parts.append(L.section("4b. P1, after the fact: fade the book's stray from the mechanical total", "r4_posthoc.py",
                           r4_posthoc.run()))
    parts.append(L.section("5. Multiplicity: Benjamini-Hochberg across every registered cell", "r4_report.py", bh_section()))
    L.OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {L.OUT} in {time.time() - t0:.0f} s; {len(L.REG)} registered cells")


if __name__ == "__main__":
    main()
