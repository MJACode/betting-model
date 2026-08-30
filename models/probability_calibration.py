"""What the models CLAIM versus what actually happens, and the map between them.

Measured 2026-08-30 over the full graded universe (`mv_scored_pick_outcomes`,
BET + AVOID + dead-zone alike per CLAUDE.md section 7), at the probabilities
that actually get bet:

    mlb_prop_pitcher_hits   claims 65.8%  wins 49.6%   +16.2pp
    wnba_prop_player_points claims 66.5%  wins 51.5%   +15.0pp
    mlb_moneyline           claims 65.9%  wins 55.3%   +10.5pp
    mlb_prop_pitcher_k      claims 67.1%  wins 59.2%    +7.8pp
    mlb_prop_batter_rbi     claims 68.6%  wins 74.7%    -6.0pp   <- the other way

Twelve models are 6-16pp overconfident; one is under. It is not a sport, a
market or a model type — it tracks SAMPLE SIZE, and the mechanism is visible on
`mlb_live_total_runs`, where the same measurement run by season says:

    2022-24 (in sample)      -2 to -3pp    well calibrated
    2025    (out of sample)  +9 to +10pp
    2026    (out of sample)  +7 to +13pp

The models fit their training seasons more tightly than any season they have
not seen, and every live pick is made out of sample. That is why this is a
mapping and not a retrain: retraining moves the boundary, not the behaviour —
2027 would look exactly like 2025 and 2026 do now.

PHASE 1 (this module): every pick is STAMPED with its calibrated probability at
score time, and the honest number is what gets published. The DECISION still
runs on the raw probability against the existing thresholds.

That split is deliberate, and the arithmetic is why: `mlb_moneyline`'s cut is
0.72 claimed, which maps to roughly 0.62 calibrated. Applying calibration to the
decision without re-cutting the thresholds would take the model from ~2 picks a
week to none at all — every threshold in `config.py` was swept on RAW
probabilities. This is the `best_line` precedent exactly: the better number is
published immediately and adopted as the qualifying number only once someone
deliberately re-cuts against it.

PHASE 2 (not this module): re-sweep thresholds on calibrated probabilities and
flip the decision path. A model update under section 1b — needs a person's call
and an `Updated-By` trailer.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime

from loguru import logger

import config
from data.db import get_connection

# Below this many graded picks in a model's own current-version era, no mapping
# is fitted at all. A map from 40 points is a map of 40 points.
MIN_GRADED = 150
# Only the actionable range is fitted. Below this the models are near enough
# calibrated and it is not where money is placed.
MIN_PROB = 0.55
# A fitted map has to hold on data it was not fitted on, or it is describing
# this half of the season rather than the model.
MAX_TRANSFER_GAP_PP = 6.0

# Contamination the repo documents, which would otherwise be fitted as if it
# were the model talking: mlb_over_under's live probabilities before the
# NaN-total_line fix, and mlb_runline's before the frozen-bullpen catch-up.
HONEST_ERA_FROM = {
    "mlb_over_under": "2026-07-05",
    "mlb_runline": "2026-07-05",
}
# The dead-zone NONE rows were deleted 2026-06-26..08-08 (section 7, trap 2), so
# that window silently holds only BET+AVOID -- the high-|edge| tail.
CLEAN_WINDOWS = (("2026-05-12", "2026-06-25"), ("2026-08-09", "2100-01-01"))
PAPER_START = "2026-04-14"


# ── the map ──────────────────────────────────────────────────────────────────

def _logit(p: float) -> float:
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    e = math.exp(z)
    return e / (1.0 + e)


def fit_platt(probs: list[float], wins: list[int],
              iters: int = 400, lr: float = 0.08) -> tuple[float, float]:
    """Two-parameter Platt scaling on the logit: p' = sigmoid(a * logit(p) + b).

    Two parameters rather than isotonic on purpose. Several of these models have
    a few hundred graded picks, and the gap is smooth in confidence — it widens
    steadily as the claim rises. Isotonic would fit the tail's noise and produce
    a step function nobody could defend.
    """
    xs = [_logit(p) for p in probs]
    a, b = 1.0, 0.0
    n = len(xs)
    for _ in range(iters):
        ga = gb = 0.0
        for x, y in zip(xs, wins):
            err = _sigmoid(a * x + b) - y
            ga += err * x
            gb += err
        a -= lr * ga / n
        b -= lr * gb / n
    return a, b


def apply_calibration(prob: float, params: dict | None) -> float:
    """Map a raw probability to its calibrated value.

    SYMMETRIC by construction: the map is fitted on the preferred side only
    (p >= 0.5) and the other side is defined as 1 - f(1 - p). Without that a
    prop's over and under would not sum to 1, and the app would publish two
    probabilities for one proposition that disagree.
    """
    if not params or params.get("method") != "platt":
        return prob
    a, b = float(params["a"]), float(params["b"])
    if prob >= 0.5:
        return _sigmoid(a * _logit(prob) + b)
    return 1.0 - _sigmoid(a * _logit(1.0 - prob) + b)


# ── the data ─────────────────────────────────────────────────────────────────

def _era_start(model_id: str, active_since: str | None) -> str:
    """A map fitted across a version swap describes a blend of two models."""
    return max(active_since or PAPER_START,
               HONEST_ERA_FROM.get(model_id, PAPER_START))


def fetch_graded(conn, model_id: str, since: str) -> list[tuple[float, int]]:
    """(claimed probability, won) for the preferred side, current era, clean windows."""
    clauses = " OR ".join(
        f"(game_date BETWEEN '{lo}' AND '{hi}')" for lo, hi in CLEAN_WINDOWS)
    rows = conn.execute(f"""
        SELECT model_probability::float8, result
        FROM mv_scored_pick_outcomes
        WHERE model_id = %(m)s AND result IN ('WIN','LOSS')
          AND model_probability >= %(minp)s AND game_date >= %(since)s
          AND ({clauses})
    """, {"m": model_id, "minp": MIN_PROB, "since": since}).fetchall()
    return [(float(p), 1 if r == "WIN" else 0) for p, r in rows]


def _gap_pp(pairs: list[tuple[float, int]], params: dict | None = None) -> float:
    if not pairs:
        return 0.0
    claimed = sum(apply_calibration(p, params) for p, _ in pairs) / len(pairs)
    realised = sum(y for _, y in pairs) / len(pairs)
    return 100.0 * (claimed - realised)


# ── fitting ──────────────────────────────────────────────────────────────────

def fit_model(conn, model_id: str, active_since: str | None) -> dict:
    """Fit one model's map, or refuse and say why."""
    since = _era_start(model_id, active_since)
    pairs = fetch_graded(conn, model_id, since)
    out = {"model_id": model_id, "era_from": since, "n": len(pairs),
           "method": None, "a": None, "b": None,
           "raw_gap_pp": round(_gap_pp(pairs), 2),
           "fitted_at": datetime.now().astimezone().isoformat()}

    if model_id in config.PROB_ONLY_MODELS:
        out["note"] = ("prob-only model — its probability is the whole signal and "
                       "is not compared to a price; not fitted")
        return out
    if len(pairs) < MIN_GRADED:
        out["note"] = (f"only {len(pairs)} graded picks since {since} "
                       f"(need {MIN_GRADED}) — identity map, unfitted")
        return out

    # Time split: fit on the older half, check the map on the newer half. A map
    # that cannot transfer across six weeks of its own season will not transfer
    # to next week either.
    half = len(pairs) // 2
    a1, b1 = fit_platt([p for p, _ in pairs[:half]], [y for _, y in pairs[:half]])
    holdout = pairs[half:]
    # BOTH numbers, because "the map does not fully close the gap" and "the map
    # does not help" are different verdicts. The in-sample gap after fitting is
    # ~0 by construction and says nothing; what matters is whether the map
    # applied to unseen picks beats leaving them raw.
    transfer_raw = abs(_gap_pp(holdout))
    transfer = abs(_gap_pp(holdout, {"method": "platt", "a": a1, "b": b1}))

    a, b = fit_platt([p for p, _ in pairs], [y for _, y in pairs])
    params = {"method": "platt", "a": a, "b": b}
    out.update(method="platt", a=round(a, 6), b=round(b, 6),
               cal_gap_pp=round(_gap_pp(pairs, params), 2),
               transfer_gap_pp=round(transfer, 2),
               transfer_raw_gap_pp=round(transfer_raw, 2),
               helps=bool(transfer < transfer_raw),
               transfers=bool(transfer <= MAX_TRANSFER_GAP_PP))
    # A map is only PUBLISHED where it demonstrably makes the number more honest
    # on picks it was not fitted on. Nine models earn that (pitcher_hits goes
    # 12.9pp -> 1.3pp); seven do not, and for those the honest answer is to keep
    # the raw number and say the gap is not stable enough to map. Fitting a map
    # and applying it anyway would be trading a known bias for an unknown one.
    out["applied"] = bool(out["helps"])
    if not out["transfers"] and out["helps"]:
        out["note"] = (f"improves but does not close: {transfer_raw:.1f}pp raw -> "
                       f"{transfer:.1f}pp calibrated on the held-out half. Publish "
                       f"it; do not build a threshold on it yet")
    elif not out["helps"]:
        out["note"] = (f"DOES NOT HELP out of sample: {transfer_raw:.1f}pp raw -> "
                       f"{transfer:.1f}pp calibrated on the held-out half. The gap "
                       f"is not stable enough to map")
    return out


DDL = """
CREATE TABLE IF NOT EXISTS model_calibration (
    model_id    TEXT PRIMARY KEY,
    fitted_at   TEXT NOT NULL,
    method      TEXT,
    a           NUMERIC,
    b           NUMERIC,
    n           INTEGER,
    era_from    TEXT,
    applied     BOOLEAN NOT NULL DEFAULT FALSE,
    payload     TEXT NOT NULL
)
"""
# Postgres hands anon everything on a new public table by default, and a REVOKE
# FROM PUBLIC does nothing about it — the roles have to be named (section 7).
LOCKDOWN = (
    "ALTER TABLE model_calibration ENABLE ROW LEVEL SECURITY",
    "REVOKE ALL ON model_calibration FROM anon",
    "REVOKE ALL ON model_calibration FROM authenticated",
)


def persist(conn, report: dict) -> None:
    conn.execute(DDL)
    for stmt in LOCKDOWN:
        try:
            conn.execute(stmt)
        except Exception:  # noqa: BLE001 — sqlite has no RLS; non-owner cannot revoke
            pass
    try:
        conn.execute("ALTER TABLE model_calibration ADD COLUMN IF NOT EXISTS "
                     "applied BOOLEAN NOT NULL DEFAULT FALSE")
    except Exception:  # noqa: BLE001 - sqlite / already present
        pass
    conn.execute("""
        INSERT INTO model_calibration (model_id, fitted_at, method, a, b, n,
                                       era_from, applied, payload)
        VALUES (%(model_id)s, %(fitted_at)s, %(method)s, %(a)s, %(b)s, %(n)s,
                %(era_from)s, %(applied)s, %(payload)s)
        ON CONFLICT (model_id) DO UPDATE SET
            fitted_at = EXCLUDED.fitted_at, method = EXCLUDED.method,
            a = EXCLUDED.a, b = EXCLUDED.b, n = EXCLUDED.n,
            era_from = EXCLUDED.era_from, applied = EXCLUDED.applied,
            payload = EXCLUDED.payload
    """, {**{k: report.get(k) for k in
             ("model_id", "fitted_at", "method", "a", "b", "n", "era_from")},
          "applied": bool(report.get("applied")),
          "payload": json.dumps(report)})


def load_calibrations(conn) -> dict[str, dict]:
    """model_id -> params, for the scorer. Missing table means identity maps."""
    try:
        rows = conn.execute(
            "SELECT model_id, method, a, b FROM model_calibration "
            "WHERE applied").fetchall()
    except Exception:
        return {}
    return {m: {"method": meth, "a": float(a), "b": float(bb)}
            for m, meth, a, bb in rows if meth == "platt" and a is not None}


def run_calibration_fit(conn=None) -> list[dict]:
    own = conn is None
    conn = conn or get_connection()
    reports = []
    try:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        for model_id in sorted(config.ACTION_THRESHOLDS):
            try:
                rep = fit_model(conn, model_id, active.get(model_id))
                persist(conn, rep)
                reports.append(rep)
            except Exception as exc:  # one model must not sink the rest
                logger.warning("calibration fit failed for {}: {}", model_id, exc)
        conn.commit()
    finally:
        if own:
            conn.close()
    fitted = [r for r in reports if r.get("method")]
    logger.info("probability calibration: {} fitted, {} left as identity",
                len(fitted), len(reports) - len(fitted))
    return reports


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing")
    args = ap.parse_args()
    conn = get_connection()
    try:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        print(f"{'model':<30}{'n':>7}{'raw gap':>9}"
              f"{'held-out raw->cal':>14}{'helps':>7}  note")
        for model_id in sorted(config.ACTION_THRESHOLDS):
            rep = fit_model(conn, model_id, active.get(model_id))
            if rep["n"] == 0:
                continue
            if rep.get("method"):
                tr = f"{rep['transfer_raw_gap_pp']:.1f}->{rep['transfer_gap_pp']:.1f}"
                helps = "yes" if rep["helps"] else "NO"
            else:
                tr, helps = "—", "—"
            print(f"{model_id:<30}{rep['n']:>7}{rep['raw_gap_pp']:>+9.1f}"
                  f"{tr:>14}{helps:>7}  {rep.get('note','')[:44]}")
            if not args.dry_run:
                persist(conn, rep)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
