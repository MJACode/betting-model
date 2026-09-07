"""Two ufc_total_rounds artifacts, one population, the same cuts.

WHY THIS EXISTS (2026-09-07). mike: "retrain ufc_total_rounds", after #514
showed the live model negative in all 42 cells of its threshold grid.

A retrain cannot be judged on the trainer's own holdout metrics here, for two
measured reasons:

  * `holdout_roi` is 0.0 on every UFC registry row and came back 0.0 again on a
    2026 holdout -- `_simulate_flat_roi` finds no odds to simulate against, so
    the trainer reports accuracy and calibration and NOTHING about money.
  * Accuracy over all fights is not the bar. The live 2026-06-19 model holds
    out at 0.6386 accuracy / 0.0384 calibration and still lost at every cut,
    because what decides the money is the small tail of fights where the model
    disagrees with DraftKings enough to bet.

So this scores BOTH artifacts over the same 2026 fights, joins the real
pre-game DraftKings total, and runs the #514 grid on each. Same population,
same prices, same cells; the only thing that differs is the model.

PRE-GAME ONLY, AND THE LINE HAS TO MATCH. Odds are bounded to
`snapshot_at <= commence_time` with `snapshot_type <> 'in_play'` (the leak rule
in .claude/rules/data-integrity.md), and a fight is skipped when DK's stored
total differs from the line its label was graded against -- a different line is
a different bet (section 1c).

Run: python -m scripts.ufc_model_compare
     python -m scripts.ufc_model_compare --candidate models/saved/_baseline/<new>.pkl
"""

import warnings, pickle, sys; warnings.filterwarnings("ignore")
import numpy as np, psycopg2
from dotenv import dotenv_values
sys.path.insert(0, ".")
from features.feature_engine import build_training_dataset, FEATURE_MAP

df = build_training_dataset("ufc_total_rounds", seasons=[2026])
feats = FEATURE_MAP["ufc_total_rounds"]

conn = psycopg2.connect(dotenv_values(".env")["DATABASE_URL"], connect_timeout=30)
cur = conn.cursor()
cur.execute("""
    SELECT DISTINCT ON (o.game_id) o.game_id, o.total_line, o.over_price, o.under_price
    FROM odds o JOIN games g ON g.game_id = o.game_id
    WHERE o.bookmaker='draftkings' AND o.market='totals'
      AND o.snapshot_type <> 'in_play'
      AND g.sport='UFC'
      AND (g.commence_time IS NULL
           OR o.snapshot_at::timestamptz <= g.commence_time::timestamptz)
      AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
    ORDER BY o.game_id, o.snapshot_at::timestamptz DESC
""")
odds = {r[0]: {"line": float(r[1]) if r[1] is not None else None,
               "over": float(r[2]), "under": float(r[3])} for r in cur.fetchall()}
print(f"2026 fights: {len(df)} | with a pre-game DK total: {sum(1 for g in df.game_id if g in odds)}")

def implied(american):
    return 100.0/(american+100.0) if american > 0 else abs(american)/(abs(american)+100.0)
def payout(american):
    return american/100.0 if american > 0 else 100.0/abs(american)

def rows_for(path):
    with open(path, "rb") as fh:
        art = pickle.load(fh)
    model = art["model"] if isinstance(art, dict) and "model" in art else art
    p = model.predict_proba(df[feats])[:, 1]
    out = []
    for i, (gid, line, target) in enumerate(zip(df.game_id, df.total_line, df.target)):
        o = odds.get(gid)
        if not o or o["line"] is None or float(o["line"]) != float(line):
            continue                      # a different line is a different bet
        for side, prob, price, won in (
                ("over",  p[i],     o["over"],  target == 1),
                ("under", 1 - p[i], o["under"], target == 0)):
            out.append({"gid": gid, "date": str(df.game_date.iloc[i]), "side": side,
                        "prob": float(prob), "edge": float(prob) - implied(price),
                        "u": payout(price) if won else -1.0, "won": bool(won)})
    return out

def grid(rows, label, live=(0.62, 0.08)):
    rows = sorted(rows, key=lambda r: r["date"])
    mid = rows[len(rows)//2]["date"]
    print(f"\n### {label}   (live cut prob>={live[0]}, edge>={live[1]})")
    print(f"{'prob':>6}{'edge':>7}{'n':>5}{'W':>4}{'L':>4}{'units':>8}{'roi%':>8}{'early':>12}{'late':>12}")
    for P in (0.55, 0.58, 0.60, 0.62, 0.65, 0.70):
        for E in (0.02, 0.04, 0.06, 0.08, 0.10):
            sel = [r for r in rows if r["prob"] >= P and r["edge"] >= E]
            if not sel: continue
            w = sum(1 for r in sel if r["won"]); u = sum(r["u"] for r in sel)
            e = [r for r in sel if r["date"] < mid]; l = [r for r in sel if r["date"] >= mid]
            f = lambda s: f"{len(s)}/{100*sum(x['u'] for x in s)/len(s):+.0f}%" if s else "0/-"
            star = " <-- LIVE" if (P == live[0] and E == live[1]) else ""
            print(f"{P:>6.2f}{E:>7.2f}{len(sel):>5}{w:>4}{len(sel)-w:>4}{u:>8.2f}"
                  f"{100*u/len(sel):>8.1f}{f(e):>12}{f(l):>12}{star}")

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--current",
                    default="models/saved/ufc_total_rounds_20260619_211436.pkl")
    ap.add_argument("--candidate",
                    default="models/saved/_baseline/ufc_total_rounds_20260907_095926.pkl")
    a = ap.parse_args()
    grid(rows_for(a.current), f"CURRENT   {a.current}")
    grid(rows_for(a.candidate), f"CANDIDATE {a.candidate}")
