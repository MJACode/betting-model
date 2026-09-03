"""Stage 2 step 1: re-derive every pre-game cut on the BEST available price.

mike, 2026-09-03: **"stage 2 go."** That is the authorization for this work and
for the flip it leads to; the flip itself is a model update and will carry
`Updated-By: mike` when it lands. This script writes nothing.

WHAT STAGE 2 IS. Today a model decides against DraftKings: `edge` is
`model_probability - dk_implied_prob`, and every cut in `config.ACTION_THRESHOLDS`
was swept on that number. `picks.best_*` records the better price found across
`config.BEST_LINE_BOOKMAKERS` but never reaches the decision (CLAUDE.md §6,
`tests/test_best_line.py`). Stage 2 makes the best price the deciding one.

WHY IT IS NOT A ONE-LINE SWITCH. A better price is a lower implied probability,
so the same pick has a bigger edge measured against it — and the same cut is
therefore a LOOSER cut. Measured 2026-09-02 over 69 clean-window bets: the best
price is 0.68pp cheaper on average and 3.61pp at the extreme, so a 0.10 edge
cut quietly becomes about 0.093. Flipping without re-cutting would loosen every
model at once with nobody deciding to, which is the same mistake §6 was written
to prevent.

THE THREE NUMBERS THIS PRINTS, and the middle one is the point:

  now         current cut on DK edge, settled at the DK price   -- today
  same @best  THE SAME PICK SET, settled at the best price      -- free half
  best cut    swept cut on best edge, settled at the best price -- the flip

`same @best` changes no threshold and no pick: it is purely "we already made
these bets, here is what the better number would have paid". It carries zero
calibration risk and it is the half that can ship first.

READ `now` CAREFULLY: it is today's cut REPLAYED over the whole graded universe,
which is §7's evaluation rule, not the bets that were actually placed. A model
whose live board produced nothing still shows a record here, because the rows it
declined are graded too. That is the point -- a BET-only sample can only ever
describe picks that already cleared the bar.

THE GATE, stated up front because the sample is young. Best-price stamping
began 2026-08-28, so this reads days, not seasons. Nothing here is shippable
until a cut clears the repo's standing tests (§7): >= MIN_SETTLED settled rows,
a PLATEAU rather than a peak, and positive ROI in BOTH halves of its own
window. A five-day window cannot produce a credible time split. The verdict
column says so per model rather than leaving it implied.

The sample DOES grade the whole universe, which is the one thing that usually
sinks a sweep this young: `mv_scored_pick_outcomes` grades BET, AVOID and
dead-zone NONE alike (§7's evaluation rule), and best-price stamping runs on
every scored row rather than only on bets — so the high-volume prop models
already have 500-1,300 graded rows each.

    python -m scripts.best_line_threshold_sweep
    python -m scripts.best_line_threshold_sweep --model mlb_prop_pitcher_k
    python -m scripts.best_line_threshold_sweep --min-rows 200
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

import config
from data.db import get_connection
# The load-bearing statistics are the calibrated sweep's, deliberately: plateau
# counting, Wilson intervals and the settled-and-per-week grading are the same discipline
# whichever price basis is underneath, and a second copy would drift from it.
from scripts.calibrated_threshold_sweep import (EDGE_GRID, MIN_SETTLED,
                                                PROB_GRID, REGIME_DAYS,
                                                _apply_price_floor, grade,
                                                sweep)

BEST_LINE_FROM = "2026-08-28"          # first day picks carry best_* at all


def american_to_decimal(odds: float) -> float:
    return 1.0 + (odds / 100.0 if odds > 0 else 100.0 / abs(odds))


def units_at(odds: float, result: str) -> float:
    """Profit in units on a 1u FLAT stake, which is the convention
    mv_scored_pick_outcomes.profit_units already uses -- verified 2026-09-03
    against stored rows: WIN at -140 is +0.7143, at -110 +0.9091, at +150
    +1.5000; LOSS is -1.0 at every price and PUSH is 0."""
    if result == "WIN":
        return american_to_decimal(odds) - 1.0
    if result == "LOSS":
        return -1.0
    return 0.0


def fetch(conn, model_id: str) -> list[dict]:
    """Every graded, pre-game, best-price-stamped row for one model.

    Joins the matview (which grades the FULL scored universe, not just bets) to
    picks for the best-price columns the matview does not carry.
    """
    rows = conn.execute("""
        SELECT m.pick_id, m.game_date, m.model_probability::float8, m.edge::float8,
               m.dk_odds::float8, p.best_edge::float8, p.best_odds::float8,
               p.best_book, m.result
        FROM mv_scored_pick_outcomes m
        JOIN picks p ON p.pick_id = m.pick_id
        WHERE m.model_id = %(m)s
          AND m.result IN ('WIN','LOSS','PUSH')
          AND m.game_date >= %(since)s
          AND m.dk_odds IS NOT NULL AND m.edge IS NOT NULL
          AND p.best_edge IS NOT NULL AND p.best_odds IS NOT NULL
          AND p.is_live IS NOT TRUE
    """, {"m": model_id, "since": BEST_LINE_FROM}).fetchall()
    return [{
        "pick_id": pid, "date": d, "p": float(p), "dk_edge": float(e),
        "dk_odds": float(dko), "best_edge": float(be), "best_odds": float(bo),
        "best_book": bk, "result": r,
    } for pid, d, p, e, dko, be, bo, bk, r in rows]


def _basis(rows: list[dict], model_id: str, price: str) -> list[dict]:
    """Rows expressed on one price basis, in the shape sweep()/grade() want.

    `cal_p` / `cal_edge` are the calibrated sweep's field names; here they carry
    the RAW probability and the chosen basis's edge. The probability is
    deliberately raw: Stage 2 changes the PRICE the decision is measured
    against, and folding the probability-calibration flip in at the same time
    would confound two changes whose effects point the same way.

    The price floor is applied on the basis's own price, because a flipped
    scorer would compare config.MODEL_MIN_ODDS to the price it actually bets.
    """
    odds_key, edge_key = f"{price}_odds", f"{price}_edge"
    out = [{**r, "odds": r[odds_key], "cal_p": r["p"], "cal_edge": r[edge_key],
            "units": units_at(r[odds_key], r["result"])} for r in rows]
    return _apply_price_floor(model_id, out)


def _cut(rows: list[dict], min_prob: float, min_edge: float) -> list[dict]:
    return [r for r in rows
            if r["cal_p"] >= min_prob and r["cal_edge"] >= min_edge]


def analyse(conn, model_id: str, today: date, min_rows: int) -> dict | None:
    raw = fetch(conn, model_id)
    if len(raw) < min_rows:
        return {"model_id": model_id, "total": len(raw), "thin": True}

    dk_rows = _basis(raw, model_id, "dk")
    best_rows = _basis(raw, model_id, "best")

    cur = config.ACTION_THRESHOLDS.get(model_id, {})
    pmin, emin = cur.get("min_prob", 0.0), cur.get("min_edge", 0.0)

    # 1. Today: the DK cut on DK edge, paid at the DK price.
    now_set = _cut(dk_rows, pmin, emin)
    now = grade(now_set, 0)

    # 2. The free half: THE SAME PICKS -- qualified on DK exactly as today --
    #    paid at the best price. No threshold moves, no pick appears or
    #    disappears; only the payout changes.
    #    Keyed on pick_id, not (date, probability, price): prop rows collide on
    #    those three constantly -- a slate has dozens at p=0.65 and -110 on the
    #    same day -- and a collision would silently pay the better price to bets
    #    this cut never made, which is the exact overstatement this column
    #    exists to avoid. test_the_free_half_never_changes_the_pick_set pins it.
    same_ids = {r["pick_id"] for r in now_set}
    same_at_best = grade([r for r in best_rows if r["pick_id"] in same_ids], 0)

    # 3. The flip: re-swept cut on best edge, paid at the best price.
    cutoff = (today - timedelta(days=REGIME_DAYS)).isoformat()
    recent = [r for r in best_rows if r["date"] >= cutoff]
    days = float(len({r["date"] for r in recent})) or 0.0
    cells = sweep(best_rows, days, recent)
    usable = [c for c in cells if c["n"] >= MIN_SETTLED]
    positive = [c for c in usable if (c["roi"] or 0) > 0]
    plateau = [c for c in positive if c["plateau"] >= 4]

    ordered = sorted(best_rows, key=lambda r: r["date"])
    mid = len(ordered) // 2
    halves = (ordered[:mid], ordered[mid:])

    def split(cell):
        out = []
        for half in halves:
            keep = _cut(half, cell["min_prob"], cell["min_edge"])
            out.append(round(100 * sum(r["units"] for r in keep) / len(keep), 1)
                       if len(keep) >= 8 else None)
        return out

    survivors = []
    for c in (plateau or positive):
        c["half_a"], c["half_b"] = split(c)
        if c["half_a"] is not None and c["half_b"] is not None \
                and c["half_a"] > 0 and c["half_b"] > 0:
            survivors.append(c)
    best = (max(survivors, key=lambda c: (c["roi"], c["n"])) if survivors
            else (max(plateau or positive, key=lambda c: (c["roi"], c["n"]))
                  if positive else None))

    span = len({r["date"] for r in raw})
    if best is None:
        verdict = f"NO CUT at {MIN_SETTLED}+ settled on best-price edge"
    elif best in survivors and plateau:
        verdict = (f"candidate {best['min_prob']:.2f}/{best['min_edge']:.2f} "
                   f"({best['half_a']}% / {best['half_b']}% by half) — "
                   f"NOT SHIPPABLE, {span}-day window")
    elif best in survivors:
        verdict = "PEAK, NOT A PLATEAU — watch"
    else:
        verdict = (f"FAILS THE TIME SPLIT ({best.get('half_a')}% then "
                   f"{best.get('half_b')}%) — watch")

    gain = (None if now["roi"] is None or same_at_best["roi"] is None
            else round(same_at_best["roi"] - now["roi"], 1))
    return {"model_id": model_id, "total": len(raw), "days": span,
            "now": now, "same_at_best": same_at_best, "gain": gain,
            "cur": (pmin, emin), "best": best, "verdict": verdict,
            "thin": False}


def main() -> None:
    ap = argparse.ArgumentParser(description="Stage 2 step 1 — best-price sweep")
    ap.add_argument("--model")
    ap.add_argument("--min-rows", type=int, default=MIN_SETTLED,
                    help="skip models with fewer graded best-price rows")
    args = ap.parse_args()

    conn = get_connection()
    try:
        # Retired models have no model_action_thresholds row (session 170
        # deleted batter_hr and batter_rbi that way), and a recommended cut for
        # a model that no longer scores is noise. Join, never hand-list.
        live = {r[0] for r in conn.execute(
            "SELECT model_id FROM model_action_thresholds").fetchall()}
        models = ([args.model] if args.model
                  else sorted(m for m in config.ACTION_THRESHOLDS if m in live))
        today = date.today()

        print(f"Best-price threshold sweep — data from {BEST_LINE_FROM}, "
              f"grid {len(PROB_GRID)}x{len(EDGE_GRID)}, MIN_SETTLED={MIN_SETTLED}")
        print("`now` and `same @best` REPLAY today's cut over the whole graded "
              "universe (§7), so they")
        print("  are not the bets actually placed — a model with no live BETs "
              "still shows a record here.")
        print("`same @best` = the SAME picks, paid at the best price: no "
              "threshold moves, no pick added.")
        print("A cut is shippable only on a PLATEAU that is positive in BOTH "
              "halves of its window (§7).\n")
        print(f"{'model':<30}{'rows':>6}{'d':>3}{'now':>18}"
              f"{'same @best':>18}{'gain':>7}  verdict")

        thin = []
        for model_id in models:
            r = analyse(conn, model_id, today, args.min_rows)
            if r is None:
                continue
            if r["thin"]:
                thin.append(f"{r['model_id']} ({r['total']})")
                continue
            n, s = r["now"], r["same_at_best"]
            def fmt(g):
                if not g["n"] or g["roi"] is None:
                    return "—"
                return f"{g['w']}-{g['l']} {g['roi']:+.1f}%"
            gain = "—" if r["gain"] is None else f"{r['gain']:+.1f}pp"
            print(f"{r['model_id']:<30}{r['total']:>6}{r['days']:>3}"
                  f"{fmt(n):>18}{fmt(s):>18}{gain:>7}  {r['verdict']}")
        if thin:
            print(f"\nToo few graded best-price rows to sweep "
                  f"(<{args.min_rows}): {', '.join(thin)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
