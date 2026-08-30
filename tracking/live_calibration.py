"""Live models are the ones that have to keep earning their cutoff.

A pre-game model is scored once a day against a line that barely moves. A live
model prices a market that moves every few seconds, locks its bet at the first
crossing, and never re-prices — so its cutoff is a claim about a distribution
that shifts under it. The lock landing on 2026-08-29 took MLB live from ~35% of
games producing a bet to 100%, at an unchanged threshold. Nobody changed a cut;
the meaning of the cut changed.

So this module re-derives the cutoff from the settled record on every run and
says, in writing, whether the current one is still defensible. It answers four
questions per model:

1. **Is it calibrated?** Mean predicted probability against realised win rate.
   A model claiming 72% and winning 56% is not mispriced by the book, it is
   overconfident — and no threshold repairs that.
2. **Does EV predict?** Mean predicted EV against realised ROI. `mlb_live_total_runs`
   has run a +29.5% mean EV into a +3.1% realised return. That does not make EV
   useless as a RANKING, but it does mean an EV floor is not a promise, and the
   dashboard says so rather than printing the EV as though it were.
3. **What would a different cut have produced?** A prob x EV sweep over the
   settled sample, with a plateau score, because a cell whose neighbours flip
   negative is noise (sessions 74 and 87, and CLAUDE.md section 7).
4. **What does it cost per week?** Retention measured on the RECENT regime, not
   the lifetime average — that is the number the lifetime average got wrong.

The verdict is allowed to be "no cut works, retrain or pause". A recommender
that always recommends something is a recommender you cannot trust.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import date, datetime, timedelta

from loguru import logger

import config
from data.db import get_connection
from tracking.discord_notifier import stake_for

# Sweep grid. Prob runs from a little under every live model's current floor to
# where the samples run out; EV likewise. Both are coarse on purpose — a finer
# grid finds more peaks, not more signal.
PROB_GRID = [0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.74, 0.76]
EV_GRID = [0.00, 0.14, 0.18, 0.22, 0.26, 0.28, 0.30, 0.32, 0.34]

# The window that defines "the regime we are in now" for volume. Short, because
# the whole point is that live volume moves when the machinery moves.
REGIME_DAYS = 3
# A cell needs at least this many settled bets before its ROI is reported as
# anything but noise.
MIN_SETTLED = 12
# ...and this many before the recommender is allowed to prefer it to the status quo.
MIN_SETTLED_TO_RECOMMEND = 15


# ── helpers ──────────────────────────────────────────────────────────────────

def decimal_odds(american) -> float | None:
    try:
        a = float(american)
    except (TypeError, ValueError):
        return None
    if a == 0:
        return None
    return 1.0 + (a / 100.0 if a > 0 else 100.0 / abs(a))


def expected_value(prob: float, american) -> float | None:
    dec = decimal_odds(american)
    return None if dec is None else prob * dec - 1.0


def wilson(wins: int, n: int) -> tuple[float, float] | None:
    """95% CI on a win rate. Reported so a 3-bet cell cannot masquerade as a result."""
    if n <= 0:
        return None
    z, p = 1.96, wins / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - m) / d, (c + m) / d)


def _fetch(conn, model_id: str) -> list[dict]:
    """Every live BET this model has made, priced, newest last."""
    sql = """
        SELECT game_date, created_at, result,
               model_probability::float8  AS prob,
               dk_odds::float8            AS odds,
               edge::float8               AS edge,
               profit_flat::float8        AS profit_flat
        FROM picks
        WHERE is_live IS TRUE AND signal_type = 'BET'
          AND model_id = %(m)s AND dk_odds IS NOT NULL
        ORDER BY game_date, created_at
    """
    # Explicit column list rather than cursor.description: data.db wraps
    # psycopg2 in a sqlite-shaped helper whose result object exposes fetch*()
    # only (the "DBConnection is not a psycopg2 connection" trap, PR #295).
    cols = ("game_date", "created_at", "result", "prob", "odds", "edge",
            "profit_flat")
    rows = []
    for raw in conn.execute(sql, {"m": model_id}).fetchall():
        r = dict(zip(cols, raw))
        r["ev"] = expected_value(r["prob"], r["odds"])
        # Units LAID, from the one definition the app and Discord both use.
        r["risk_u"] = stake_for(None, r["odds"]).risk
        rows.append(r)
    return rows


def _grade(rows: list[dict]) -> dict:
    """Record and P&L for a set of picks. Flat 1u, the repo's ROI convention."""
    settled = [r for r in rows if r["result"] in ("WIN", "LOSS", "PUSH")]
    w = sum(1 for r in settled if r["result"] == "WIN")
    l = sum(1 for r in settled if r["result"] == "LOSS")
    p = sum(1 for r in settled if r["result"] == "PUSH")
    units = sum((r["profit_flat"] or 0.0) for r in settled) / 100.0
    ci = wilson(w, w + l)
    return {
        "bets": len(rows), "settled": len(settled), "w": w, "l": l, "push": p,
        "units_flat": round(units, 2),
        "roi_pct": round(100 * units / len(settled), 1) if settled else None,
        "win_pct": round(100 * w / (w + l), 1) if (w + l) else None,
        "ci_low_pct": round(100 * ci[0], 1) if ci else None,
        "ci_high_pct": round(100 * ci[1], 1) if ci else None,
    }


def _regime(rows: list[dict], today: date) -> tuple[list[dict], float]:
    """The recent slice, and how many days it spans — the forward-volume basis."""
    cutoff = (today - timedelta(days=REGIME_DAYS - 1)).isoformat()
    recent = [r for r in rows if r["game_date"] >= cutoff]
    if not recent:
        return [], 0.0
    days = len({r["game_date"] for r in recent})
    return recent, float(days)


def _project(recent: list[dict], days: float, prob_min: float, ev_min: float) -> dict:
    """Bets and units per week if this cut had been live over the recent regime."""
    if not recent or days <= 0:
        return {"bets_per_week": None, "units_per_week": None}
    kept = [r for r in recent
            if r["prob"] >= prob_min and (r["ev"] is None or r["ev"] >= ev_min)]
    return {
        "bets_per_week": round(len(kept) / days * 7, 1),
        "units_per_week": round(sum(r["risk_u"] for r in kept) / days * 7, 1),
    }


def _sweep(rows: list[dict], recent: list[dict], days: float) -> list[dict]:
    cells = []
    for pmin in PROB_GRID:
        for evmin in EV_GRID:
            kept = [r for r in rows
                    if r["prob"] >= pmin and (r["ev"] is None or r["ev"] >= evmin)]
            if not kept:
                continue
            cell = {"min_prob": pmin, "min_ev": evmin, **_grade(kept),
                    **_project(recent, days, pmin, evmin)}
            cells.append(cell)
    # Plateau score: of the 8 neighbouring cells, how many are also profitable.
    by_key = {(c["min_prob"], c["min_ev"]): c for c in cells}
    for c in cells:
        pi, ei = PROB_GRID.index(c["min_prob"]), EV_GRID.index(c["min_ev"])
        good = 0
        for dp in (-1, 0, 1):
            for de in (-1, 0, 1):
                if dp == 0 and de == 0:
                    continue
                if not (0 <= pi + dp < len(PROB_GRID) and 0 <= ei + de < len(EV_GRID)):
                    continue
                n = by_key.get((PROB_GRID[pi + dp], EV_GRID[ei + de]))
                if n and (n["roi_pct"] or 0) > 0:
                    good += 1
        c["plateau"] = good
    return cells


def _recommend(cells: list[dict], current: dict,
               max_per_week: float | None) -> tuple[dict | None, str]:
    """The honest recommendation, including 'none'.

    Optimises ROI UNDER a volume ceiling, not ROI alone. A cut that earns more
    by betting more is not an answer to "too many bets", and left unconstrained
    the sweep proposes exactly that — its first run wanted a looser cut than the
    one it was checking.
    """
    usable = [c for c in cells if c["settled"] >= MIN_SETTLED_TO_RECOMMEND]
    if not usable:
        return None, ("NOT ENOUGH DATA — no cut has "
                      f"{MIN_SETTLED_TO_RECOMMEND}+ settled bets yet. "
                      "Leave the cutoff alone and re-run when it does.")
    if max_per_week is not None:
        # An unmeasurable projection (no picks in the recent regime) is not
        # evidence of low volume — keep those cells rather than assume.
        within = [c for c in usable
                  if c["bets_per_week"] is None or c["bets_per_week"] <= max_per_week]
        if not within:
            return None, (f"NO CUT FITS THE {max_per_week:g}/week ceiling on the "
                          "settled sample. Either raise the ceiling or accept "
                          "that this model cannot be tuned to it yet.")
        usable = within
    positive = [c for c in usable if (c["roi_pct"] or 0) > 0]
    if not positive:
        return None, ("NO PROFITABLE CUT anywhere on the grid at volume. This is "
                      "not a threshold problem — retrain or pause. Shipping the "
                      "least-bad cell would be fitting noise.")
    # Prefer a plateau over a peak: rank on ROI, but only among cells whose
    # neighbourhood also holds up.
    plateau = [c for c in positive if c["plateau"] >= 4]
    pool = plateau or positive
    best = max(pool, key=lambda c: (c["roi_pct"], c["settled"]))
    cur_roi = current.get("roi_pct") or 0
    if not plateau:
        note = ("PEAK, NOT A PLATEAU — the best cell's neighbours do not hold up, "
                "so treat this as a candidate to watch, not a cut to ship.")
    elif best["roi_pct"] <= cur_roi:
        note = ("KEEP THE CURRENT CUT — nothing within the volume ceiling beats "
                "it on a neighbourhood that holds up.")
    else:
        note = (f"CANDIDATE — prob >= {best['min_prob']:.2f}, EV >= {best['min_ev']:.2f} "
                f"({best['settled']} settled, {best['roi_pct']:+.1f}%, "
                f"{best['plateau']}/8 neighbours positive, "
                f"{best['bets_per_week']}/wk).")
    return best, note


def _calibration(rows: list[dict]) -> dict:
    settled = [r for r in rows if r["result"] in ("WIN", "LOSS")]
    if not settled:
        return {"mean_pred_prob": None, "realised_win_pct": None,
                "calibration_gap_pp": None, "mean_pred_ev_pct": None,
                "realised_roi_pct": None, "ev_gap_pp": None}
    mean_p = sum(r["prob"] for r in settled) / len(settled)
    realised = sum(1 for r in settled if r["result"] == "WIN") / len(settled)
    evs = [r["ev"] for r in settled if r["ev"] is not None]
    mean_ev = sum(evs) / len(evs) if evs else None
    roi = sum((r["profit_flat"] or 0.0) for r in settled) / 100.0 / len(settled)
    return {
        "mean_pred_prob": round(mean_p, 4),
        "realised_win_pct": round(100 * realised, 1),
        "calibration_gap_pp": round(100 * (mean_p - realised), 1),
        "mean_pred_ev_pct": round(100 * mean_ev, 1) if mean_ev is not None else None,
        "realised_roi_pct": round(100 * roi, 1),
        "ev_gap_pp": (round(100 * (mean_ev - roi), 1)
                      if mean_ev is not None else None),
    }


def analyse(conn, model_id: str, today: date | None = None) -> dict:
    today = today or date.today()
    rows = _fetch(conn, model_id)
    recent, days = _regime(rows, today)

    cur_prob = config.MODEL_PROB_THRESHOLDS.get(model_id, 0.0)
    cur_ev = config.MODEL_MIN_EV.get(model_id)
    cur_rows = [r for r in rows
                if r["prob"] >= cur_prob
                and (cur_ev is None or r["ev"] is None or r["ev"] >= cur_ev)]
    current = {"min_prob": cur_prob, "min_ev": cur_ev, **_grade(cur_rows),
               **_project(recent, days, cur_prob, cur_ev if cur_ev is not None else 0.0)}

    cells = _sweep(rows, recent, days)
    ceiling = config.LIVE_MAX_BETS_PER_WEEK.get(model_id)
    best, verdict = _recommend(cells, current, ceiling)
    cal = _calibration(rows)

    if cal["calibration_gap_pp"] is not None and cal["calibration_gap_pp"] >= 8:
        verdict = (f"OVERCONFIDENT by {cal['calibration_gap_pp']:.1f}pp "
                   f"(claims {100 * cal['mean_pred_prob']:.1f}%, wins "
                   f"{cal['realised_win_pct']:.1f}%). A threshold cannot fix a "
                   "calibration error — retrain is the lever. " + verdict)

    return {
        "model_id": model_id,
        "sport": config.LIVE_MODELS.get(model_id, ("?",))[0],
        "computed_at": datetime.now().astimezone().isoformat(),
        "regime_days": days,
        "calibration": cal,
        "max_bets_per_week": ceiling,
        "current": current,
        "recommended": best,
        "verdict": verdict,
        "grid": sorted(cells, key=lambda c: (-(c["roi_pct"] or -999), -c["settled"]))[:40],
    }


# ── persistence ──────────────────────────────────────────────────────────────

DDL = """
CREATE TABLE IF NOT EXISTS live_calibration (
    model_id     TEXT PRIMARY KEY,
    sport        TEXT,
    computed_at  TEXT NOT NULL,
    verdict      TEXT,
    payload      TEXT NOT NULL
)
"""

# Creating the table at write time is the run_ledger.py precedent: the Supabase
# MCP is read-only and setup_database() only runs at first-time setup, so a
# feature that needs a manual migration first does nothing until someone
# remembers. The cost is that the table is born with Postgres' default grants,
# which hand anon everything -- so lock it down in the same breath. Best-effort:
# SQLite has no RLS and a non-owner role cannot revoke, and neither case should
# stop a calibration report being written.
LOCKDOWN = (
    "ALTER TABLE live_calibration ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON live_calibration FROM anon",
    "REVOKE ALL ON live_calibration FROM authenticated",
)


def persist(conn, report: dict) -> None:
    """One row per model, overwritten each run — the dashboard wants the latest."""
    conn.execute(DDL)
    for stmt in LOCKDOWN:
        try:
            conn.execute(stmt)
        except Exception:  # noqa: BLE001 - see LOCKDOWN
            pass
    conn.execute(
        """
        INSERT INTO live_calibration (model_id, sport, computed_at, verdict, payload)
        VALUES (%(model_id)s, %(sport)s, %(computed_at)s, %(verdict)s, %(payload)s)
        ON CONFLICT (model_id) DO UPDATE SET
            sport = EXCLUDED.sport, computed_at = EXCLUDED.computed_at,
            verdict = EXCLUDED.verdict, payload = EXCLUDED.payload
        """,
        {"model_id": report["model_id"], "sport": report["sport"],
         "computed_at": report["computed_at"], "verdict": report["verdict"],
         "payload": json.dumps(report)},
    )


def run_live_calibration(conn=None, today: date | None = None) -> list[dict]:
    """Refresh every live model's calibration report. Never raises into a caller."""
    own = conn is None
    conn = conn or get_connection()
    out = []
    try:
        for model_id in sorted(config.LIVE_MODELS):
            try:
                report = analyse(conn, model_id, today)
                persist(conn, report)
                out.append(report)
                c = report["current"]
                logger.info(
                    "live calibration {}: {} settled at the live cut, ROI {}, "
                    "{} bets/wk — {}",
                    model_id, c["settled"], c["roi_pct"], c["bets_per_week"],
                    report["verdict"][:90])
            except Exception as exc:  # one model must not sink the rest
                logger.warning("live calibration failed for {}: {}", model_id, exc)
        conn.commit()
    finally:
        if own:
            conn.close()
    return out


def _fmt(report: dict) -> str:
    c, r = report["current"], report["recommended"]
    cal = report["calibration"]
    lines = [
        "", "=" * 78,
        f"{report['model_id']}  ({report['sport']})",
        "=" * 78,
        f"  calibration : claims {cal['mean_pred_prob']}, wins "
        f"{cal['realised_win_pct']}%  (gap {cal['calibration_gap_pp']}pp)",
        f"  EV honesty  : predicts {cal['mean_pred_ev_pct']}%, returns "
        f"{cal['realised_roi_pct']}%  (gap {cal['ev_gap_pp']}pp)",
        f"  ceiling     : {report['max_bets_per_week']} bets/wk",
        f"  CURRENT  prob>={c['min_prob']} EV>={c['min_ev']}: "
        f"{c['settled']} settled {c['w']}-{c['l']}, ROI {c['roi_pct']}%, "
        f"{c['bets_per_week']} bets/wk, {c['units_per_week']}u/wk",
    ]
    if r:
        lines.append(
            f"  BEST     prob>={r['min_prob']} EV>={r['min_ev']}: "
            f"{r['settled']} settled {r['w']}-{r['l']}, ROI {r['roi_pct']}%, "
            f"{r['bets_per_week']} bets/wk, {r['units_per_week']}u/wk, "
            f"plateau {r['plateau']}/8")
    lines.append(f"  VERDICT  : {report['verdict']}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", help="one live model id (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()

    conn = get_connection()
    try:
        models = [args.model] if args.model else sorted(config.LIVE_MODELS)
        for model_id in models:
            report = analyse(conn, model_id)
            print(_fmt(report))
            if not args.dry_run:
                persist(conn, report)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
