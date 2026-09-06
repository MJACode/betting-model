"""Grade EVERY scored UFC pick and sweep the cuts — the evaluation rule for UFC.

WHY THIS EXISTS (2026-09-05). mike: "there are NO UFC picks in the channel."
Delivery was fixed (#505) and the webhook verified (#513), which left the real
question: why do the UFC models produce ~3 bets on a 13-fight card, and would a
looser cut publish more?

That question cannot be answered from BET rows. CLAUDE.md section 7: any
analysis of thresholds MUST grade the whole universe -- BET, AVOID and NONE --
because a BET-only sample already cleared the live bar and cannot see the
population a looser cut would draw from. `mv_scored_pick_outcomes` does exactly
that for MLB and WNBA and **does not cover UFC**, and `picks.result` is only
ever written for BETs (paper_tracker settles `signal_type = 'BET'`), so before
this script there was no graded UFC universe at all.

So it grades here, from `ufc_fight_log` + `games`, using the SAME helper
production settles with (`rounds_completed`) so the sweep and the live record
cannot disagree about what won.

UNITS ARE ONLY EVER TAKEN FROM PRICED ROWS. `picks.profit_flat` fabricates -110
for a pick with no DK price and UFC is one of the named victims (CLAUDE.md
section 6), so this computes units from `dk_odds` and returns None without one
rather than inventing a payout.

Run: python -m scripts.ufc_threshold_sweep
"""

import sys, psycopg2
from collections import defaultdict
from dotenv import dotenv_values
sys.path.insert(0, ".")
from data.ingestors.ufc_stats_ingestor import rounds_completed

c = psycopg2.connect(dotenv_values(".env")["DATABASE_URL"], connect_timeout=30)
cur = c.cursor()

cur.execute("""
  SELECT p.pick_id, p.model_id, p.pick_side, p.model_probability, p.edge,
         p.dk_odds, p.scored_line, p.game_id, p.game_date, p.signal_type,
         g.home_win, g.home_score, g.away_score
  FROM picks p LEFT JOIN games g ON g.game_id = p.game_id
  WHERE p.sport='UFC' AND p.model_id IN ('ufc_moneyline','ufc_total_rounds')
""")
picks = cur.fetchall()

cur.execute("""SELECT game_id, method, end_round, end_time_sec, scheduled_rounds
               FROM ufc_fight_log""")
res = {r[0]: dict(zip(["gid","method","end_round","end_time_sec","sched"], r))
       for r in cur.fetchall()}

def units(odds, won):
    if odds is None: return None            # section 6: never fabricate -110
    d = (odds/100.0) if odds > 0 else (100.0/abs(odds))
    return d if won else -1.0

graded = []
missing = defaultdict(int)
for (pid, model, side, prob, edge, odds, line, gid, gdate, sig,
     home_win, hs, aws) in picks:
    won = None
    if model == 'ufc_moneyline':
        if home_win is None:
            missing['ml_no_result'] += 1; continue
        won = (home_win == 1) if side == 'home' else (home_win == 0)
    else:
        r = res.get(gid)
        if r is None or line is None:
            missing['tr_no_fightlog'] += 1; continue
        rc = rounds_completed(r["end_round"], r["end_time_sec"], r["sched"])
        if rc is None:
            missing['tr_no_rounds'] += 1; continue
        if float(rc) == float(line):
            continue                         # push
        over = float(rc) > float(line)
        won = over if side == 'over' else not over
    graded.append(dict(model=model, prob=float(prob), edge=float(edge),
                       odds=odds, won=won, date=str(gdate), sig=sig,
                       u=units(odds, won)))

print("graded:", len(graded), "| ungradeable:", dict(missing))
for m in ('ufc_moneyline','ufc_total_rounds'):
    g=[x for x in graded if x['model']==m]
    print(f"\n{m}: {len(g)} graded rows, {sum(1 for x in g if x['won'])} wins "
          f"({sum(1 for x in g if x['odds'] is not None)} priced)")
    print("  by signal_type:", {s: sum(1 for x in g if x['sig']==s)
                                for s in ('BET','AVOID','NONE')})

print("\n" + "="*70)
print("SWEEP — what each (min_prob, min_edge) would have BET, graded over the")
print("whole universe (BET+AVOID+NONE), units only from priced rows (section 6)")
print("="*70)
import statistics, math
for m, live in (('ufc_moneyline', (0.65, 0.08)), ('ufc_total_rounds', (0.62, 0.08))):
    g = [x for x in graded if x['model'] == m and x['u'] is not None]
    g.sort(key=lambda x: x['date'])
    mid = g[len(g)//2]['date'] if g else None
    print(f"\n### {m}   (live cut: prob>={live[0]}, edge>={live[1]})")
    print(f"{'prob':>6}{'edge':>7}{'n':>5}{'W':>4}{'L':>4}{'units':>8}{'roi%':>8}"
          f"{'early n/roi':>14}{'late n/roi':>13}")
    for P in [0.50,0.55,0.575,0.60,0.62,0.65,0.70]:
        for E in [0.02,0.04,0.06,0.08,0.10,0.12]:
            sel=[x for x in g if x['prob']>=P and x['edge']>=E]
            if not sel: continue
            w=sum(1 for x in sel if x['won']); l=len(sel)-w
            u=sum(x['u'] for x in sel); roi=100*u/len(sel)
            early=[x for x in sel if x['date']<mid]; late=[x for x in sel if x['date']>=mid]
            def rr(s): return f"{len(s)}/{100*sum(x['u'] for x in s)/len(s):+.0f}%" if s else "0/-"
            star = " <-- LIVE" if (abs(P-live[0])<1e-9 and abs(E-live[1])<1e-9) else ""
            print(f"{P:>6.3f}{E:>7.2f}{len(sel):>5}{w:>4}{l:>4}{u:>8.2f}{roi:>8.1f}"
                  f"{rr(early):>14}{rr(late):>13}{star}")
