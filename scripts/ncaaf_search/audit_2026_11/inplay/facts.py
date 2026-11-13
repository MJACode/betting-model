import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402
import json
res = json.load(open("results.json", encoding="utf-8")); var = json.load(open("variants.json", encoding="utf-8")); diag = json.load(open("diag.json", encoding="utf-8"))
allc = []
for t in ("A", "B1", "B2"):
    for v in ("V1", "V2"):
        allc += [dict(c, test=t, v=v) for c in res[t][v]["cells"]]
allc += [dict(c, test="A", v="V3") for c in var["plain"]["A"]["V3"]["cells"]]
tot = [c for c in allc if c["rule"].startswith("totals") and c["bets"]]
ml = [c for c in allc if c["rule"].startswith("h2h") and c["bets"]]
print("totals price min", min(c["price_min"] for c in tot), "max", max(c["price_max"] for c in tot), "median range", min(c["price_med"] for c in tot), max(c["price_med"] for c in tot))
print("ml price min", min(c["price_min"] for c in ml), "max", max(c["price_max"] for c in ml), "median range", min(c["price_med"] for c in ml), max(c["price_med"] for c in ml))
w = [c["ci_hi"] - c["ci_lo"] for c in ml]; print("ml CI width range", round(min(w), 4), round(max(w), 4))
w = [c["ci_hi"] - c["ci_lo"] for c in tot]; print("totals CI width range", round(min(w), 4), round(max(w), 4))
mlA = [c for c in ml if c["test"] == "A"]
print("A moneyline cells:", len(mlA), "early < late in", sum(c["early_roi"] < c["late_roi"] for c in mlA), "| early negative in", sum(c["early_roi"] < 0 for c in mlA), "| late positive in", sum(c["late_roi"] > 0 for c in mlA))
totA = [c for c in tot if c["test"] == "A"]
print("A totals cells:", len(totA), "negative:", sum(c["roi"] < 0 for c in totA), "roi range", min(c["roi"] for c in totA), max(c["roi"] for c in totA))
print("A totals cells above placebo p95:", [(c["v"], c["rule"], c["cut"], c["roi"], c["placebo_p95"]) for c in totA if c["roi"] > c["placebo_p95"]])
print("A ml cells above placebo p95:", [(c["v"], c["rule"], c["cut"], c["roi"], c["placebo_p95"]) for c in mlA if c["roi"] > c["placebo_p95"]])
print("any cell CI lower bound > 0:", [(c["test"], c["v"], c["rule"], c["cut"], c["roi"], c["ci_lo"]) for c in allc if c["bets"] and c["ci_lo"] > 0])
print("any cell CI upper bound < 0:", [(c["test"], c["v"], c["rule"], c["cut"], c["roi"], c["ci_hi"]) for c in allc if c["bets"] and c["ci_hi"] < 0])
fb = []
for t, vs in (("A", ("V1", "V2", "V3")), ("B1", ("V1", "V2")), ("B2", ("V1", "V2"))):
    for v in vs:
        fb += [dict(c, test=t, v=v) for c in var["fb"][t][v]["cells"]]
fa = [c for c in fb if c["test"] == "A" and c["rule"].startswith("totals")]
print("FB A totals cells", len(fa), "negative", sum(c["roi"] < 0 for c in fa), "positive:", [(c["v"], c["rule"], c["cut"], c["roi"]) for c in fa if c["roi"] >= 0])
sl = []
for t in ("A", "B1", "B2"):
    for v in ("V1", "V2"):
        for r in ("totals_H1", "totals_H2", "h2h_H1", "h2h_H2"):
            i = diag[t][v]["info"][r]; sl.append((t, v, r, i["slope_model_alone"], i["w_model"], i["w_model_lo"], i["w_model_hi"]))
ts = [s for s in sl if s[2].startswith("totals")]
print("totals slopes excluding A H1:", sorted(s[3] for s in ts if not (s[0] == "A" and s[2] == "totals_H1")))
print("A H1 totals slopes:", [s[3] for s in ts if s[0] == "A" and s[2] == "totals_H1"])
print("totals w_model interval above 0:", sum(s[5] > 0 for s in ts), "of", len(ts))
ms = [s for s in sl if s[2].startswith("h2h")]
print("ml w_model interval above zero A+B1:", sum(s[5] > 0 for s in ms if s[0] in ("A", "B1")), "of", sum(1 for s in ms if s[0] in ("A", "B1")), "| B2:", sum(s[5] > 0 for s in ms if s[0] == "B2"), "of", sum(1 for s in ms if s[0] == "B2"))
cal = res["calibration"]
sr = [r["spread_ratio"] for k in cal for r in cal[k]]; me = [abs(r["mean_err"]) for k in cal for r in cal[k]]
print("spread ratio range", min(sr), max(sr), "max |mean err|", max(me))
