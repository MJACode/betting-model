"""
mlb_bet_record_audit.py — the defensible answer to "what is the MLB record?"

WHY THIS EXISTS
---------------
The MLB record gets questioned, and the honest answer is that THREE different
numbers are defensible depending on which population is being counted. Answering
from memory (or from whichever view is nearest to hand) is how two people end up
quoting different records for the same models. This script prints all three from
one snapshot, plus the grading validation that makes any of them citable.

    python -m scripts.mlb_bet_record_audit
    python -m scripts.mlb_bet_record_audit --csv /tmp/mlb_bets.csv

Run it where the DB is reachable (Railway worker, Matt's machine) — the dev
sandbox has neither psycopg2 nor DATABASE_URL. The Supabase MCP can run the same
SQL read-only.

THE THREE NUMBERS, AND WHEN EACH ONE IS THE RIGHT ANSWER
--------------------------------------------------------
1. **Every BET signal ever issued.** Every row in `picks` with
   `signal_type = 'BET'` and an MLB model, whatever cut was live at the time.
   Includes models since paused or retired. This is the lifetime signal history
   and it is the number to give when someone asks "what have the models
   actually said?". It loses money — the lifetime win rate is comfortably above
   50%, but the wins came at much shorter prices than the losses, which is the
   exact failure the -140 prop price floor was added to stop in July 2026.

2. **Signals that clear today's cuts.** The same real bets, filtered to unpaused
   models at their current `model_action_thresholds` prob / edge / min-odds
   values from the 2026-04-14 evaluation start. This is the number to give when
   someone asks "what does the model do now?". It is in-sample — the cuts were
   swept on much of this same data — so it is a description, not a projection.

3. **The published track record** (`v_public_track_record`). Read it, do not
   re-derive it, and know what it is: for the MLB game models and every MLB
   prop it sources `v_model_full_outcome_picks`, which selects from `picks`
   **with no `signal_type` filter at all** and then applies today's thresholds
   retrospectively. Dead-zone NONE rows that happen to clear the current cut are
   counted as picks even though no bet was ever published for them. That is
   correct for a threshold sweep (CLAUDE.md's evaluation rule: a BET-only sample
   is systematically optimistic and cannot see the population a looser cut would
   draw from) and wrong for a public record. The `--reconcile` block quantifies
   the gap per model; measured 2026-08-30 it was material on
   `mlb_prop_batter_rbi` (11 of 34 published picks were real BET signals) and
   `mlb_prop_batter_runs` (22 of 47).

WHAT THE VALIDATION BLOCK DOES
------------------------------
Every settled pre-game BET pick is re-graded from scratch out of `games` and
`player_game_log` — moneyline, totals, runline (home-signed: an away cover is
`(away - home) - scored_line > 0`), F5, and all twelve prop markets — and
compared against the stored `result`. Separately, `profit_flat` is recomputed
from result and DK odds. CLAUDE.md is explicit that a threshold or a record is
not citable until the grading under it has been reconciled: a sign bug in
away-side spread grading once survived a threshold change and turned a -20.6%
cut into a phantom +15%. Run this before quoting any number above.

Rows the script cannot re-grade are reported, never silently dropped —
`mlb_f5_over_under` and `mlb_f5_runline` have no independent grading path (DK
does not carry those markets) and a handful of props have no game log.

READ THE OUTPUT LIKE THIS
-------------------------
  * DISAGREE must be 0. Anything else invalidates every record below it and is
    the only thing worth working on.
  * Compare `pre-game` against `live`. In-play rows are a different product and
    should never be pooled into a headline record without saying so.
  * `created_at > commence_time` counts restore/backfill re-stamping, not
    in-play betting. It does not affect any win or loss, but CLV and
    beat-the-close cannot be measured on those rows, so no such claim about them
    is supportable.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection  # noqa: E402

# Every MLB pick the models have ever issued as a BET, with the flags the three
# populations are cut on. `qualifies_today` mirrors the action filter exactly:
# unpaused, prob floor, edge floor (unless prob-only), and the min-odds price
# floor, from the evaluation start.
PICKS_SQL = """
SELECT p.pick_id,
       p.game_date,
       p.model_id,
       p.pick_label,
       p.pick_side,
       p.scored_line,
       p.dk_odds,
       p.model_probability,
       p.edge,
       COALESCE(p.is_live, FALSE)                          AS is_live,
       p.result,
       p.profit_flat,
       p.created_at,
       g.commence_time,
       g.home_score, g.away_score, g.home_win,
       g.home_score_f5, g.away_score_f5,
       pl.actual,
       (t.paused IS NOT TRUE
         AND p.model_probability >= t.min_prob
         AND (t.prob_only OR p.edge >= t.min_edge)
         AND (t.min_odds IS NULL OR p.dk_odds IS NULL OR p.dk_odds >= t.min_odds)
         AND p.game_date >= '2026-04-14')                  AS qualifies_today
  FROM picks p
  LEFT JOIN model_action_thresholds t ON t.model_id = p.model_id
  LEFT JOIN games g                   ON g.game_id  = p.game_id
  LEFT JOIN LATERAL (
        SELECT CASE p.model_id
                 WHEN 'mlb_prop_pitcher_k'      THEN l.p_strikeouts
                 WHEN 'mlb_prop_pitcher_walks'  THEN l.p_walks
                 WHEN 'mlb_prop_pitcher_hits'   THEN l.p_hits_allowed
                 WHEN 'mlb_prop_pitcher_er'     THEN l.p_earned_runs
                 WHEN 'mlb_prop_pitcher_outs'   THEN (FLOOR(l.innings_pitched) * 3
                        + ROUND((l.innings_pitched - FLOOR(l.innings_pitched)) * 10))::int
                 WHEN 'mlb_prop_batter_hits'    THEN l.hits
                 WHEN 'mlb_prop_batter_tb'      THEN l.total_bases
                 WHEN 'mlb_prop_batter_rbi'     THEN l.rbi
                 WHEN 'mlb_prop_batter_runs'    THEN l.runs
                 WHEN 'mlb_prop_batter_sb'      THEN l.stolen_bases
                 WHEN 'mlb_prop_batter_walks'   THEN l.walks
                 WHEN 'mlb_prop_batter_hr'      THEN l.home_runs
               END AS actual
          FROM player_game_log l
         WHERE l.game_id = p.game_id AND l.player_id = p.player_id
         LIMIT 1) pl ON TRUE
 WHERE p.signal_type = 'BET'
   AND (p.sport = 'MLB' OR p.model_id LIKE 'mlb%')
 ORDER BY p.game_date, p.pick_id
"""

# The wrapped cursor in data/db.py mimics sqlite3 and exposes no `.description`,
# so the column names are named here and must stay in step with PICKS_SQL.
PICK_COLS = (
    "pick_id", "game_date", "model_id", "pick_label", "pick_side", "scored_line",
    "dk_odds", "model_probability", "edge", "is_live", "result", "profit_flat",
    "created_at", "commence_time", "home_score", "away_score", "home_win",
    "home_score_f5", "away_score_f5", "actual", "qualifies_today",
)

SETTLED = ("WIN", "LOSS", "PUSH")


def _regrade(r: dict) -> str | None:
    """Re-derive the outcome from raw scores. None = no independent path."""
    m, side, line = r["model_id"], r["pick_side"], r["scored_line"]
    sh, sa = r["home_score"], r["away_score"]

    if m == "mlb_moneyline":
        if sh is None:
            return None
        if sh == sa:
            return "PUSH"
        return "WIN" if (side == "home") == (sh > sa) else "LOSS"

    if m == "mlb_over_under":
        if sh is None or line is None:
            return None
        total = sh + sa
        if total == line:
            return "PUSH"
        return "WIN" if (side == "over") == (total > line) else "LOSS"

    if m == "mlb_runline":
        if sh is None or line is None:
            return None
        # `scored_line` is always the HOME number; an away cover is
        # (away - home) - scored_line > 0. Getting this sign wrong has produced
        # a wrong threshold twice — CLAUDE.md §4.
        margin = (sh - sa) + line if side == "home" else (sa - sh) - line
        if margin == 0:
            return "PUSH"
        return "WIN" if margin > 0 else "LOSS"

    if m == "mlb_f5_moneyline":
        fh, fa = r["home_score_f5"], r["away_score_f5"]
        if fh is None or fa is None:
            return None
        if fh == fa:
            return "PUSH"
        return "WIN" if (side == "home") == (fh > fa) else "LOSS"

    if m.startswith("mlb_prop_"):
        actual = r["actual"]
        if actual is None or line is None:
            return None
        if actual == line:
            return "PUSH"
        return "WIN" if (side == "over") == (actual > line) else "LOSS"

    return None  # f5_over_under / f5_runline: DK carries no such market


def _expected_profit(result: str, odds) -> float | None:
    if odds is None:
        return None
    if result == "PUSH":
        return 0.0
    if result == "WIN":
        return float(odds) if odds > 0 else 10000.0 / abs(float(odds))
    return -100.0


class Rec:
    """Win/loss/push tally plus flat-stake P&L at the recorded DK price."""

    def __init__(self):
        self.w = self.l = self.p = self.pending = 0
        self.pnl = 0.0
        self.staked = 0

    def add(self, r: dict) -> "Rec":
        res = r["result"]
        if res == "WIN":
            self.w += 1
        elif res == "LOSS":
            self.l += 1
        elif res == "PUSH":
            self.p += 1
        else:
            self.pending += 1
        if res in SETTLED and r["dk_odds"] is not None:
            self.pnl += float(r["profit_flat"] or 0)
            self.staked += 100
        return self

    @property
    def n(self):
        return self.w + self.l + self.p + self.pending

    @property
    def win_pct(self):
        return 100.0 * self.w / (self.w + self.l) if (self.w + self.l) else 0.0

    @property
    def roi(self):
        return 100.0 * self.pnl / self.staked if self.staked else 0.0

    def line(self, label: str, width: int = 26) -> str:
        rec = f"{self.w}-{self.l}" + (f"-{self.p}" if self.p else "")
        return (f"{label:<{width}} {self.n:>6} {rec:>12} {self.win_pct:>7.1f}% "
                f"{self.pnl:>11,.2f} {self.roi:>8.2f}% {self.pending:>6}")


HEAD = (f"{'':<26} {'rows':>6} {'W-L-P':>12} {'win%':>8} "
        f"{'flat P&L':>11} {'ROI':>9} {'open':>6}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", help="write every BET row to this path")
    ap.add_argument("--reconcile", action="store_true",
                    help="also show published-view picks that were never BET signals")
    args = ap.parse_args()

    with get_connection() as conn:
        rows = [dict(zip(PICK_COLS, r)) for r in conn.execute(PICKS_SQL).fetchall()]

        print(f"\n{len(rows):,} MLB BET rows\n")

        # ---- validation first: no record below is citable until this passes.
        agree = disagree = skipped = 0
        bad_profit = 0
        mismatches = []
        for r in rows:
            if r["result"] not in SETTLED or r["is_live"]:
                continue
            got = _regrade(r)
            if got is None:
                skipped += 1
            elif got == r["result"]:
                agree += 1
            else:
                disagree += 1
                mismatches.append(r)
            exp = _expected_profit(r["result"], r["dk_odds"])
            if exp is not None and abs(exp - float(r["profit_flat"] or 0)) > 0.02:
                bad_profit += 1

        print("GRADING VALIDATION (settled pre-game bets, re-graded from raw scores)")
        print(f"  agree {agree:,}   DISAGREE {disagree:,}   no independent path {skipped:,}")
        print(f"  profit_flat arithmetic mismatches: {bad_profit:,}")
        for r in mismatches[:20]:
            print(f"    !! {r['game_date']} {r['model_id']} {r['pick_label']}: "
                  f"stored {r['result']}, recomputed {_regrade(r)}")
        if disagree:
            print("\n  Grading disagrees with the stored settlements. Every record "
                  "below is unsafe to quote until this is resolved.\n")

        # ---- the three numbers
        live = [r for r in rows if r["is_live"]]
        pre = [r for r in rows if not r["is_live"]]
        qual = [r for r in rows if r["qualifies_today"]]

        print("\nTOTAL RECORD")
        print(HEAD)
        for label, sel in (("1 all BET signals", rows),
                           ("    pre-game", pre),
                           ("    live / in-play", live),
                           ("2 clears today's cuts", qual)):
            rec = Rec()
            for r in sel:
                rec.add(r)
            print(rec.line(label))

        pub = conn.execute("""
            SELECT COALESCE(SUM(picks),0), COALESCE(SUM(wins),0),
                   COALESCE(SUM(losses),0), COALESCE(SUM(pushes),0),
                   COALESCE(SUM(profit_flat),0), COALESCE(SUM(staked_flat),0)
              FROM v_public_track_record WHERE sport = 'MLB'
        """).fetchone()
        n, w, l, p, pnl, staked = pub
        roi = 100.0 * float(pnl) / staked if staked else 0.0
        wp = 100.0 * w / (w + l) if (w + l) else 0.0
        rec = f"{w}-{l}" + (f"-{p}" if p else "")
        print(f"{'3 published board':<26} {n:>6} {rec:>12} {wp:>7.1f}% "
              f"{float(pnl):>11,.2f} {roi:>8.2f}% {'':>6}")
        print("   (3 counts re-graded NONE rows that were never issued as bets — "
              "see --reconcile)")

        # ---- per model
        for title, sel in (("PER MODEL — all BET signals", rows),
                           ("PER MODEL — clears today's cuts", qual)):
            by: dict[str, Rec] = {}
            for r in sel:
                by.setdefault(r["model_id"], Rec()).add(r)
            print(f"\n{title}")
            print(HEAD)
            for mid in sorted(by, key=lambda k: -by[k].n):
                print(by[mid].line(mid))

        # ---- timing note: what CLV cannot be measured on
        restamped = sum(
            1 for r in pre
            if r["created_at"] and r["commence_time"]
            and str(r["created_at"]) > str(r["commence_time"])
        )
        print(f"\nTIMING: {restamped:,} of {len(pre):,} pre-game bets carry a "
              f"created_at after first pitch (restore/backfill re-stamping).")
        print("  Outcomes are unaffected; CLV and beat-the-close are not "
              "measurable on those rows.")

        if args.reconcile:
            print("\nRECONCILE — published picks that were never BET signals")
            print(f"{'model':<26} {'published':>10} {'were BET':>9} {'never':>7} "
                  f"{'pub P&L':>11} {'real-bet P&L':>13}")
            for row in conn.execute("""
                SELECT f.model_id,
                       COUNT(*),
                       COUNT(*) FILTER (WHERE p.signal_type = 'BET'),
                       COUNT(*) FILTER (WHERE p.signal_type <> 'BET'),
                       ROUND(SUM(f.profit_units) * 100, 2),
                       ROUND(SUM(f.profit_units) FILTER (WHERE p.signal_type = 'BET') * 100, 2)
                  FROM v_model_full_outcome_picks f
                  JOIN picks p ON p.pick_id = f.pick_id
                 WHERE f.model_id LIKE 'mlb%'
                 GROUP BY 1 ORDER BY 2 DESC
            """).fetchall():
                mid, tot, was, never, pub_pnl, real_pnl = row
                print(f"{mid:<26} {tot:>10} {was:>9} {never:>7} "
                      f"{float(pub_pnl or 0):>11,.2f} {float(real_pnl or 0):>13,.2f}")

    if args.csv:
        out = Path(args.csv)
        with out.open("w", newline="", encoding="utf-8") as fh:
            wtr = csv.writer(fh)
            wtr.writerow(["pick_id", "game_date", "model_id", "pick_label",
                          "dk_odds", "model_probability", "edge", "is_live",
                          "result", "profit_flat", "qualifies_today"])
            for r in rows:
                wtr.writerow([r["pick_id"], r["game_date"], r["model_id"],
                              r["pick_label"], r["dk_odds"], r["model_probability"],
                              r["edge"], r["is_live"], r["result"],
                              r["profit_flat"], r["qualifies_today"]])
        print(f"\nwrote {len(rows):,} rows -> {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
