"""Full-game round 1: rerun every r2 script and write the one results file.

  python scripts/euroleague_research/r2_report.py

Runs r2_coverage, r2_venues, r2_baselines, r2_accuracy, r2_methods,
r2_firstpost, r2_kill, r2_leads, r2_leads2 in turn (stdout captured in memory),
then the multiplicity count: every result row of a HYPOTHESIS table with 25+
bets (the baselines, the price bands, every method's read x cut grid, the
first-post grids, the lead bets; not season splits, kill-test subsets or
neighbourhood reads), Benjamini-Hochberg at a 10% false-discovery rate on the
one-sided p of 'return > 0' (r2_lib.p_one_sided). Writes
C:\\Users\\micha\\AppData\\Local\\Temp\\euroleague_fullgame_round1.md.
"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = Path(r"C:\Users\micha\AppData\Local\Temp\euroleague_fullgame_round1.md")
SCRIPTS = ["r2_coverage", "r2_venues", "r2_baselines", "r2_accuracy", "r2_methods", "r2_firstpost",
           "r2_kill", "r2_leads", "r2_leads2"]
HYPOTHESIS_SCRIPTS = {"r2_baselines", "r2_methods", "r2_firstpost", "r2_leads", "r2_leads2"}
SKIP_ROW = re.compile(r"(season 20\d\d|early half|late half|without its|book: |price median|2022-23 \(1-season)")

sys.path.insert(0, str(HERE))
import r2_lib as L  # noqa: E402


def run(name):
    env = dict(__import__("os").environ)
    env["PYTHONIOENCODING"] = "utf-8"
    r = subprocess.run([sys.executable, str(HERE / f"{name}.py")], cwd=str(HERE), capture_output=True,
                       text=True, encoding="utf-8", env=env)
    if r.returncode != 0:
        raise SystemExit(f"{name} failed:\n{r.stderr[-3000:]}")
    return r.stdout


def tables(text):
    """Yield (title, header, rows) for every markdown table, with the last ### title before it."""
    title = ""
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("### "):
            title = ln[4:].strip()
        if ln.startswith("| ") and i + 1 < len(lines) and lines[i + 1].startswith("|---"):
            header = [c.strip() for c in ln.strip("|").split("|")]
            rows = []
            j = i + 2
            while j < len(lines) and lines[j].startswith("|"):
                rows.append([c.strip() for c in lines[j].strip("|").split("|")])
                j += 1
            yield title, header, rows
            i = j
            continue
        i += 1


def num(s):
    try:
        return float(s.replace(",", ""))
    except Exception:
        return np.nan


outs = {}
for s in SCRIPTS:
    print("running", s, flush=True)
    outs[s] = run(s)

cells = []
for s in HYPOTHESIS_SCRIPTS:
    for title, header, rows in tables(outs[s]):
        if "by season" in title or "bets" not in header or "p_one" not in header:
            continue
        if "R1 by season" in title or "band by season" in title:
            continue
        ib, ip, ir = header.index("bets"), header.index("p_one"), header.index("ret%")
        isea = [k for k, h in enumerate(header) if h in ("season", "seasons", "subset")]
        for r in rows:
            if len(r) != len(header):
                continue
            txt = " / ".join(r)
            if SKIP_ROW.search(txt):
                continue
            if any(re.fullmatch(r"20\d\d", r[k]) for k in isea):
                continue
            b, p = num(r[ib]), num(r[ip])
            if np.isfinite(b) and b >= 25 and np.isfinite(p):
                cells.append((s, title, txt, b, num(r[ir]), p))

p = np.array([c[5] for c in cells])
keep = L.bh(p, alpha=0.10)
mult = [f"## Multiplicity (r2_report.py)\n",
        f"Hypothesis cells with 25+ bets: **{len(cells)}** (scripts {', '.join(sorted(HYPOTHESIS_SCRIPTS))}; "
        f"season splits, kill-test subsets and neighbourhood reads excluded). "
        f"One-sided p < 0.05: {int((p < 0.05).sum())}; < 0.01: {int((p < 0.01).sum())}; "
        f"positive return: {int(sum(1 for c in cells if c[4] > 0))}. "
        f"**Surviving Benjamini-Hochberg at a 10% false-discovery rate: {int(keep.sum())}.**\n",
        f"The BH bar for the single best cell is p <= {0.10 / max(len(cells), 1):.5f}.\n",
        "The 15 smallest p-values:\n",
        "| script | table | row | bets | ret% | p_one | survives |", "|---|---|---|---|---|---|---|"]
order = np.argsort(p)[:15]
for k in order:
    s, t, txt, b, r, pp = cells[k]
    mult.append(f"| {s} | {t[:60]} | {txt[:110]} | {int(b)} | {r} | {pp:.4f} | {'yes' if keep[k] else 'no'} |")

HEAD = ("# EuroLeague full-game markets (moneyline, spread, total): research round 1, 2026-11-13\n\n"
        "<!-- the verdicts section is written by hand from the tables below, after the run -->")
parts = [HEAD] + ["\n".join(mult)] + [outs[s] for s in SCRIPTS]
OUT.write_text("\n\n".join(parts), encoding="utf-8")
print("wrote", OUT, "cells", len(cells), "BH survivors", int(keep.sum()))
