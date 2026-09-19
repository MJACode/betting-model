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

PHASE 2 LANDED FOR GAME MODELS ON 2026-08-31 and for PLAYER PROPS ONLY ON
2026-09-07 (mike), which is six days in which the props were the models that
most needed it and the only ones not getting it. `DECIDE_ON_CALIBRATED_PROB`
was added to `classify_edge`; props are built in `_make_prop_pick`, which never
called it. Every model carrying a promoted map is a prop, so the flag was on by
default and changed nothing anywhere, while the twelve cuts shipped the same day
were chosen on CALIBRATED sweeps and applied to RAW numbers. Measured: 56 of 57
MLB prop BETs written while a map was live would not have fired on the
calibrated number the pick already stored. `docs/mlb_volume_efficiency.md`.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime

from loguru import logger

import config
from data.db import get_connection
from data.ddl_guard import schema_is_current

# Below this many graded picks in a model's own current-version era, no mapping
# is fitted at all. A map from 40 points is a map of 40 points.
MIN_GRADED = 150
# Only the actionable range is fitted. Below this the models are near enough
# calibrated and it is not where money is placed.
MIN_PROB = 0.55
# A fitted map has to hold on data it was not fitted on, or it is describing
# this half of the season rather than the model.
MAX_TRANSFER_GAP_PP = 6.0
# a or b moving by more than this is a different map, not fit noise. Measured
# 2026-09-14 on mlb_prop_batter_runs: promoted (1.138, 0.377) vs candidate
# (1.106, 0.012) — the b-shift alone is 0.36, an order of magnitude above this.
MAP_PARAM_ATOL = 0.02

# ── PHASE 3 (2026-09-19, mike: "I want only best of the best in terms of
# expected value ... it should be a best big bet model"): EVERY model decides
# on an honest number, and a global EV floor on that number is the selector.
#
# The two-parameter Platt fit above needs MIN_GRADED picks and a held-out gap
# under MAX_TRANSFER_GAP_PP, and the models that overclaim MOST are exactly the
# ones that can never clear it: a live model's evidence is one BET band above
# its own floor (fetch_graded), a rule model has a few dozen settled bets, a
# new model has none. Under phase 2 those kept deciding on the RAW claim --
# ncaaf_live_total claiming 69.8% and delivering 52.0% over 98 bets (measured
# 2026-09-19), mlb_live_total_runs 73.0% vs 59.7% over 144. The overclaim
# tracks sample size, not sport (module header), so a thin record is not "no
# evidence": it is evidence the model is one of these.
#
# So the fit is tiered. A model with a fat record and a Platt map that helps
# AND transfers keeps that map. Every other model gets a ONE-parameter offset
# on the logit (a = 1, b fitted), shrunk toward the POOLED offset fitted
# across every model with a record, with the prior worth SHRINK_K graded
# picks: b = argmin sum(logloss) + (SHRINK_K / 2) (b - b_pool)^2. n = 0 lands
# on the pooled correction; n >> SHRINK_K lands on the model's own. It is verified the same way as the Platt map -- fitted on the older
# half, judged on the newer half against leaving the number raw -- and a
# model under OFFSET_HOLDOUT_MIN graded picks is prior-dominated by
# construction and takes the pooled correction without a held-out verdict
# (25 rows cannot deliver one).
SHRINK_K = float(MIN_GRADED)
# A model with fewer graded picks than this in its era contributes nothing to
# the pooled prior (its own offset is noise) and takes the prior without a
# held-out test.
POOL_MIN_N = 25
OFFSET_HOLDOUT_MIN = 50

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


def fit_offset(probs: list[float], wins: list[int], *, prior_b: float = 0.0,
               k: float = 0.0, iters: int = 400, lr: float = 0.08) -> float:
    """One-parameter offset on the logit, shrunk toward a prior:
    p' = sigmoid(logit(p) + b), b = argmin sum logloss + (k/2)(b - prior_b)^2.

    `k` is the prior's weight in graded picks: with n = k the data and the
    prior carry equal weight; with n = 0 the answer IS the prior. a is pinned
    at 1 because on one band of evidence the slope is not identified (a Platt
    fit there "is close to a single offset", fetch_graded) and a free slope
    fitted on 40 picks is a slope of 40 picks.
    """
    xs = [_logit(p) for p in probs]
    n = len(xs)
    b = prior_b
    scale = float(max(n, 1))
    for _ in range(iters):
        g = sum(_sigmoid(x + b) - y for x, y in zip(xs, wins))
        g += k * (b - prior_b)
        b -= lr * g / (scale + k)
    return b


def pooled_prior(pairs_by_model: dict[str, list[tuple[float, int]]]) -> dict:
    """The offset the models share, fitted with every model counting once.

    Equal weight per model, not per pick, or the two batter props with 10,000
    graded rows each would BE the prior and the thin models it exists for
    would be shrunk toward a number two well-calibrated models produced.
    Models under POOL_MIN_N contribute nothing. Returns the pooled b, the
    per-model unshrunk offsets it was pooled from, and their count.
    """
    per_model = {}
    for m, pairs in pairs_by_model.items():
        if len(pairs) < POOL_MIN_N:
            continue
        per_model[m] = round(fit_offset([p for p, _ in pairs],
                                        [y for _, y in pairs]), 6)
    if not per_model:
        return {"b": 0.0, "per_model": {}, "n_models": 0}
    # Weighted MLE with weight 1/n_m per pair == mean of the per-model score
    # equations; the mean of the per-model offsets is its first-order solution
    # and is the number a reader can check by hand.
    b = sum(per_model.values()) / len(per_model)
    return {"b": round(b, 6), "per_model": per_model, "n_models": len(per_model)}


def maps_materially_differ(a1, b1, a2, b2, atol: float = MAP_PARAM_ATOL) -> bool:
    """True when two Platt maps are not the same decision.

    A missing parameter on either side is a difference: a promoted row with
    NULL a/b is not a map, and comparing it to a fitted candidate must not
    read as 'already in sync'.
    """
    if a1 is None or b1 is None or a2 is None or b2 is None:
        return True
    return (abs(float(a1) - float(a2)) > atol
            or abs(float(b1) - float(b2)) > atol)


def eligibility_clause(model_id: str, *, helps: bool, transfers: bool,
                       transfer_gap_pp: float | None,
                       promoted: bool,
                       cand_a, cand_b, prom_a, prom_b,
                       endorsed: bool | None = None) -> str | None:
    """One sentence for the health check: promote, re-promote, or not eligible.

    `helps` alone is the publish bar (`applied`). Promotion requires the fit's
    `endorsed` verdict -- `helps AND transfers` for a two-parameter map, which
    is also what a caller that does not pass `endorsed` gets. A promoted map
    whose transferring candidate has moved is the 2026-09-14 batter_runs
    failure: the 09-07 map inflated claimed probabilities by ~10pp on a
    version that was already calibrated.
    """
    if endorsed is None:
        endorsed = bool(helps and transfers)
    if not helps and not endorsed:
        return None
    if not endorsed:
        gap = (f"{float(transfer_gap_pp):.1f}pp"
               if transfer_gap_pp is not None else "held-out")
        return (f"{model_id} candidate helps but does not close "
                f"({gap} > {MAX_TRANSFER_GAP_PP:.1f}pp); not eligible to promote")
    if not promoted:
        return f"{model_id} candidate helps+transfers and is not promoted"
    if maps_materially_differ(cand_a, cand_b, prom_a, prom_b):
        return (f"{model_id} promoted map has drifted from a transferring "
                f"candidate; re-promote")
    return None


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


def invert_calibration(cal_prob: float, params: dict | None) -> float:
    """The raw probability that maps to this calibrated one.

    The map is monotone, so a cut chosen in CALIBRATED space has an exact
    equivalent in RAW space — which is what lets a threshold derived from honest
    numbers be applied by a decision path that still reads the raw one. That is
    how the phase-2 sweep's cuts ship before the decision flip does.
    """
    if not params or params.get("method") != "platt":
        return cal_prob
    a, b = float(params["a"]), float(params["b"])
    if a == 0:
        return cal_prob
    if cal_prob >= 0.5:
        return _sigmoid((_logit(cal_prob) - b) / a)
    return 1.0 - _sigmoid((_logit(1.0 - cal_prob) - b) / a)


# ── the data ─────────────────────────────────────────────────────────────────

def _era_start(model_id: str, active_since: str | None) -> str:
    """A map fitted across a version swap describes a blend of two models."""
    return max(active_since or PAPER_START,
               HONEST_ERA_FROM.get(model_id, PAPER_START))


def _is_live_lane(model_id: str) -> bool:
    """A model whose picks are written with is_live, so the matview cannot see it.

    `config.LIVE_MODELS` alone is not enough: it registers the three lanes THIS
    scorer prices, and `nfl_live_prop` is written by nfl/live_model/pick_writer
    and is absent from it. The name test is the same one
    live_record_start_2026_09_01.sql uses for the published record, and it is
    what makes this cover a lane added by a subsystem that never registers here.
    """
    return (model_id in getattr(config, "LIVE_MODELS", {})
            or "_live_" in model_id)


def fetch_graded(conn, model_id: str, since: str) -> list[tuple[float, int]]:
    """(claimed probability, won) for the preferred side, current era, clean windows.

    TWO SOURCES, because the matview cannot see half the models (2026-09-07,
    mike). `mv_scored_pick_outcomes` excludes `is_live` by construction
    (materialize_scored_pick_outcomes.sql: pre-game and in-play prices never
    mix), so every live lane read back ZERO graded picks and the weekly pass
    reported "only 0 graded picks (need 150) - identity map, unfitted" for
    mlb_live_total_runs, ncaaf_live_total, ncaaf_live_win_prob and
    nfl_live_prop, on every run since it shipped. That reads as "not enough data
    yet" and means "this model is invisible to me" - the empty-board-versus-
    broken-pipeline failure in .claude/rules/operations.md, arriving in the one
    place that decides whether a model's probabilities get corrected.
    mlb_live_total_runs has 126 graded BETs and was reported as 0.

    A LIVE LANE'S EVIDENCE IS THINNER PER BET, and the caller should know it:
    live lanes write BET and AVOID only, never the dead-zone NONE rows
    (classify_live_signal), and live AVOIDs are never settled - measured
    2026-09-07, 232 live AVOID rows and 0 graded, against 213 graded BETs. So a
    live map is fitted on the BET band alone, which is one narrow slice above
    the model's own probability floor. A Platt fit on one band is close to a
    single offset, and its held-out `transfers` test may never clear
    MAX_TRANSFER_GAP_PP however many bets accrue. That is a property of the
    evidence, not a bar to lower.
    """
    if _is_live_lane(model_id):
        # CLEAN_WINDOWS is deliberately NOT applied. It exists because the
        # dead-zone NONE rows were deleted 2026-06-26..08-08, leaving that
        # window holding only the high-|edge| BET+AVOID tail -- a CHANGE in the
        # population's shape. A live lane's population is that shape in every
        # window, by construction, so excluding the gap corrects nothing and
        # costs real bets (18 of mlb_live_total_runs' 126).
        rows = conn.execute("""
            SELECT model_probability::float8, result
            FROM picks
            WHERE model_id = %(m)s AND is_live AND result IN ('WIN','LOSS')
              AND model_probability >= %(minp)s AND game_date >= %(since)s
              AND dk_odds IS NOT NULL
        """, {"m": model_id, "minp": MIN_PROB, "since": since}).fetchall()
        return [(float(p), 1 if r == "WIN" else 0) for p, r in rows]

    if not _in_graded_matview(model_id):
        # THE THIRD SOURCE (2026-09-19). The matview grades MLB and WNBA only
        # (materialize_scored_pick_outcomes.sql: five game models plus the
        # mlb_prop_/wnba_prop_ families), so every NFL, NCAAF, UFC and
        # market-rule model read back ZERO here -- nfl_prop_market with 39
        # settled BETs claiming 55.2% and hitting 48.7%, ncaaf_over_under
        # with 16 claiming 70.2% and hitting 43.8% (measured 2026-09-19). The
        # same "invisible, reported as thin" failure the live branch above
        # fixed on 09-07, one source over. These models write BET rows only
        # (a rule has no dead zone), so like a live model the evidence is the
        # bet band alone.
        rows = conn.execute("""
            SELECT model_probability::float8, result
            FROM picks
            WHERE model_id = %(m)s AND NOT coalesce(is_live, false)
              AND signal_type = 'BET' AND result IN ('WIN','LOSS')
              AND model_probability >= %(minp)s AND game_date >= %(since)s
              AND coalesce(decision_odds, dk_odds) IS NOT NULL
              AND coalesce(condition_status, '') <> 'VOID'
        """, {"m": model_id, "minp": MIN_PROB, "since": since}).fetchall()
        return [(float(p), 1 if r == "WIN" else 0) for p, r in rows]

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


# The models mv_scored_pick_outcomes grades -- the WHERE clause of
# data/migrations/materialize_scored_pick_outcomes.sql, restated. Everything
# else settles in `picks` and is read from there.
MATVIEW_GAME_MODELS = frozenset({"mlb_moneyline", "mlb_over_under", "mlb_runline",
                                 "mlb_f5_moneyline", "wnba_moneyline"})


def _in_graded_matview(model_id: str) -> bool:
    return (model_id in MATVIEW_GAME_MODELS
            or model_id.startswith("mlb_prop_")
            or model_id.startswith("wnba_prop_"))


def _gap_pp(pairs: list[tuple[float, int]], params: dict | None = None) -> float:
    if not pairs:
        return 0.0
    claimed = sum(apply_calibration(p, params) for p, _ in pairs) / len(pairs)
    realised = sum(y for _, y in pairs) / len(pairs)
    return 100.0 * (claimed - realised)


# ── fitting ──────────────────────────────────────────────────────────────────

def _platt_report(pairs: list[tuple[float, int]]) -> dict:
    """Fit the two-parameter map and judge it on the newer half."""
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
    return {"a": round(a, 6), "b": round(b, 6),
            "cal_gap_pp": round(_gap_pp(pairs, {"method": "platt", "a": a, "b": b}), 2),
            "transfer_gap_pp": round(transfer, 2),
            "transfer_raw_gap_pp": round(transfer_raw, 2),
            "helps": bool(transfer < transfer_raw),
            "transfers": bool(transfer <= MAX_TRANSFER_GAP_PP)}


def _offset_report(pairs: list[tuple[float, int]], pool_b: float) -> dict:
    """Fit the shrunk offset and, where there are enough rows, judge it the
    same way: fitted on the older half (with the prior), gap on the newer."""
    b = fit_offset([p for p, _ in pairs], [y for _, y in pairs],
                   prior_b=pool_b, k=SHRINK_K)
    out = {"a": 1.0, "b": round(b, 6), "pool_b": round(pool_b, 6),
           "prior_dominated": len(pairs) < OFFSET_HOLDOUT_MIN,
           "cal_gap_pp": round(_gap_pp(pairs, {"method": "platt", "a": 1.0, "b": b}), 2),
           "helps": None, "transfers": None,
           "transfer_gap_pp": None, "transfer_raw_gap_pp": None}
    if out["prior_dominated"]:
        return out
    half = len(pairs) // 2
    b1 = fit_offset([p for p, _ in pairs[:half]], [y for _, y in pairs[:half]],
                    prior_b=pool_b, k=SHRINK_K)
    holdout = pairs[half:]
    transfer_raw = abs(_gap_pp(holdout))
    transfer = abs(_gap_pp(holdout, {"method": "platt", "a": 1.0, "b": b1}))
    out.update(transfer_gap_pp=round(transfer, 2),
               transfer_raw_gap_pp=round(transfer_raw, 2),
               helps=bool(transfer < transfer_raw),
               transfers=bool(transfer <= MAX_TRANSFER_GAP_PP))
    return out


def fit_model(conn, model_id: str, active_since: str | None,
              pool: dict | None = None) -> dict:
    """Fit one model's map, or refuse and say why.

    `pool` is pooled_prior()'s result (optionally carrying "pairs", the graded
    rows it was pooled from, so they are not fetched twice). Without it the
    prior is 0 -- the offset then shrinks toward "calibrated", which is the
    pre-2026-09-19 behaviour for a thin model and is only right for a test.

    The report's `method` / `a` / `b` are the map that DECIDES if promoted;
    `fit` says which tier produced it ("platt" or "offset"), and the raw
    two-parameter numbers stay visible under "platt" even when the offset
    was chosen. `endorsed` is the promotion bar (see promote()).
    """
    since = _era_start(model_id, active_since)
    if pool and model_id in (pool.get("pairs") or {}):
        pairs = pool["pairs"][model_id]
    else:
        pairs = fetch_graded(conn, model_id, since)
    out = {"model_id": model_id, "era_from": since, "n": len(pairs),
           "method": None, "a": None, "b": None, "fit": None,
           "raw_gap_pp": round(_gap_pp(pairs), 2),
           "helps": None, "transfers": None, "applied": False, "endorsed": False,
           "fitted_at": datetime.now().astimezone().isoformat()}

    if model_id in config.PROB_ONLY_MODELS:
        out["note"] = ("prob-only model — its probability is the whole signal and "
                       "is not compared to a price; not fitted")
        return out

    # TIER 1: the two-parameter map, where the record can carry one.
    if len(pairs) >= MIN_GRADED:
        platt = _platt_report(pairs)
        out["platt"] = platt
        if platt["helps"] and platt["transfers"]:
            out.update(method="platt", fit="platt", applied=True, endorsed=True,
                       **{k: platt[k] for k in ("a", "b", "cal_gap_pp", "transfer_gap_pp",
                                                "transfer_raw_gap_pp", "helps", "transfers")})
            return out

    # TIER 2: one offset, shrunk toward what the models share. Stored with
    # method "platt" and a = 1 so apply_calibration and every reader of the
    # promoted_* columns need no new case; `fit` records how it was made.
    pool_b = float((pool or {}).get("b", 0.0))
    off = _offset_report(pairs, pool_b)
    out["offset"] = off
    common = {k: off[k] for k in ("a", "b", "cal_gap_pp", "transfer_gap_pp",
                                  "transfer_raw_gap_pp", "helps", "transfers")}
    if off["prior_dominated"]:
        out.update(method="platt", fit="offset", applied=True, endorsed=True, **common)
        out["note"] = (f"prior-dominated: {len(pairs)} graded picks since {since} "
                       f"(< {OFFSET_HOLDOUT_MIN}); pooled offset {pool_b:+.3f} "
                       f"worth {SHRINK_K:.0f} picks pulls to b={off['b']:+.3f}")
        return out
    if off["helps"]:
        out.update(method="platt", fit="offset", applied=True, endorsed=True, **common)
        closes = "closes" if off["transfers"] else "does not close"
        out["note"] = (f"offset (shrunk to pool {pool_b:+.3f}) helps and {closes}: "
                       f"{off['transfer_raw_gap_pp']:.1f}pp raw -> "
                       f"{off['transfer_gap_pp']:.1f}pp on the held-out half")
        return out
    # Neither tier beats the raw number on picks it was not fitted on. Fitting
    # a map and applying it anyway would be trading a known bias for an
    # unknown one. The Platt numbers, if any, stay visible under "platt".
    out.update(**common)
    out["note"] = (f"DOES NOT HELP out of sample: {off['transfer_raw_gap_pp']:.1f}pp raw -> "
                   f"{off['transfer_gap_pp']:.1f}pp with the shrunk offset on the "
                   f"held-out half. The gap is not stable enough to map")
    return out


def fit_pool(conn, active: dict[str, str] | None = None) -> dict:
    """Fetch every model's graded record once and pool the prior from it."""
    if active is None:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
    pairs = {}
    for model_id in sorted(config.ACTION_THRESHOLDS):
        if model_id in config.PROB_ONLY_MODELS:
            continue
        pairs[model_id] = fetch_graded(conn, model_id,
                                       _era_start(model_id, active.get(model_id)))
    pool = pooled_prior(pairs)
    pool["pairs"] = pairs
    return pool


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
    promoted    BOOLEAN NOT NULL DEFAULT FALSE,
    promoted_a  NUMERIC,
    promoted_b  NUMERIC,
    promoted_at TEXT,
    promoted_method     TEXT,
    promoted_helps      BOOLEAN,
    promoted_transfers  BOOLEAN,
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


# Columns added by ALTER after the table shipped. Named once so the guard in
# ensure_schema asks the catalog for exactly what the ALTERs below would add.
_LATE_COLUMNS = (
    ("applied", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("promoted", "BOOLEAN NOT NULL DEFAULT FALSE"),
    ("promoted_a", "NUMERIC"),
    ("promoted_b", "NUMERIC"),
    ("promoted_at", "TEXT"),
    # The promoted map's OWN method and endorsement, frozen at promotion time
    # (2026-09-07, mike). Everything the decision path needs must live in a
    # column the nightly fit does not touch; see load_calibrations().
    ("promoted_method", "TEXT"),
    ("promoted_helps", "BOOLEAN"),
    ("promoted_transfers", "BOOLEAN"),
)
_COLUMNS = tuple(c for c, _ in _LATE_COLUMNS)


def ensure_schema(conn) -> None:
    """Create the table and its columns. Safe to call repeatedly.

    Split out of persist() 2026-08-31 because `--promote` never called it:
    promote() went straight to `UPDATE ... SET promoted = TRUE` and died with
    `column "promoted" does not exist` on a database where only the daily fit
    had ever run. The columns were the fix for the inert-map bug earlier the
    same day, and the ONE command that needed them could not create them.

    Every writer calls this first now, so no entry point can assume another one
    ran before it.
    """
    # Every writer calls this, and each statement below is lock-taking DDL
    # that also forces a PostgREST schema-cache reload (503s to the app while
    # it rebuilds). Skip the block when the catalog already matches --
    # data/ddl_guard.py. The column list is the same one the ALTERs add, so a
    # database missing any of them still runs the whole block.
    if schema_is_current(conn, "model_calibration", columns=_COLUMNS, rls=True,
                         revoked_from=("anon", "authenticated")):
        return

    conn.execute(DDL)

    def _try(stmt: str) -> None:
        """Run a best-effort statement, ROLLING BACK if it fails.

        The rollback is the whole point and its absence was a real bug. A failed
        statement poisons a Postgres transaction, so every LATER statement on
        the same connection fails too -- and because these are all swallowed,
        it fails INVISIBLY. That is how production ended up with `applied` but
        without `promoted`, `promoted_a`, `promoted_b` and `promoted_at`: one
        LOCKDOWN statement failed, poisoned the transaction, and the column
        ALTERs below it were skipped in silence. load_calibrations() then hit
        its own except-branch on every call and returned {} forever, so the
        calibration map was inert in production while looking installed --
        `model_probability_cal` equalled the raw probability on all 583 picks
        that carried it.

        Same hazard, same fix, as the rollback in load_calibrations().
        """
        try:
            conn.execute(stmt)
        except Exception:  # noqa: BLE001 — sqlite has no RLS; non-owner cannot revoke
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass

    for stmt in LOCKDOWN:
        _try(stmt)
    for col, decl in _LATE_COLUMNS:
        _try(f"ALTER TABLE model_calibration "
             f"ADD COLUMN IF NOT EXISTS {col} {decl}")


def persist(conn, report: dict) -> None:
    ensure_schema(conn)
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
            -- promoted / promoted_a / promoted_b are DELIBERATELY not updated:
            -- the daily fit writes a CANDIDATE, and a candidate must never move
            -- a live decision. See PROMOTION below.
    """, {**{k: report.get(k) for k in
             ("model_id", "fitted_at", "method", "a", "b", "n", "era_from")},
          "applied": bool(report.get("applied")),
          "payload": json.dumps(report)})


# ── promotion ────────────────────────────────────────────────────────────────
# THE DAILY FIT WRITES A CANDIDATE. THE SCORER READS A PROMOTED MAP.
#
# Under phase 1 the map only moved a display number, so refitting it nightly was
# harmless. The moment the DECISION reads it, a nightly refit silently moves
# every mapped model's effective cut with nobody deciding -- a model update
# under section 1b happening on a cron. So the two are separated: `applied` is
# the fit's own verdict on a candidate, `promoted` is what production uses, and
# moving one to the other is a deliberate act carrying a person's name.


def load_calibrations(conn, promoted_only: bool = True) -> dict[str, dict]:
    """model_id -> params. Missing table or column means identity maps.

    `promoted_only` is the default because this is what the scorer calls. Pass
    False to see today's candidates (the dashboard's drift view).

    THE PROMOTED MAP IS READ ENTIRELY OUT OF THE `promoted_*` COLUMNS
    (2026-09-07, mike). It used to read `promoted_a`/`promoted_b` while
    filtering on `method` -- the CANDIDATE's method, rewritten by the nightly
    fit. So a refit that could not fit a model wrote `method = NULL` and the
    PROMOTED map vanished on the next read, with nothing said and nothing
    logged. Measured: `mlb_prop_pitcher_k` and `mlb_prop_pitcher_hits` carried a
    distinct `model_probability_cal` on 166 of 166 picks from 2026-08-31 to
    09-03, on 11 of 43 on 09-04, and on 0 of 95 from 09-05 -- three days with no
    calibration at all, from a cron. That is the exact failure mode the
    candidate/promoted split exists to prevent, arriving through the one column
    the split forgot to duplicate. `docs/mlb_volume_efficiency.md` section 2.
    """
    col_a, col_b, col_m, where = ("promoted_a", "promoted_b",
                                  "promoted_method", "promoted")
    if not promoted_only:
        col_a, col_b, col_m, where = ("a", "b", "method", "applied")
    try:
        rows = conn.execute(
            f"SELECT model_id, {col_m}, {col_a}, {col_b} FROM model_calibration "
            f"WHERE {where}").fetchall()
    except Exception:
        # ROLL BACK. A failed statement poisons a Postgres connection, so
        # without this a miss here (the promoted column not existing yet) makes
        # every LATER query on the same connection fail too -- which is exactly
        # how one bad game voided a whole PBP backfill earlier today. Caught by
        # this function returning 0 candidates when the raw query returned 10.
        try:
            conn.rollback()
        except Exception:
            pass
        return {}
    return {m: {"method": meth, "a": float(a), "b": float(bb)}
            for m, meth, a, bb in rows if meth == "platt" and a is not None}


def promote(conn, model_ids: list[str] | None = None) -> list[str]:
    """Copy today's candidate map into the promoted slot. A model update.

    TWO BARS, NOT ONE (2026-09-07, mike). This used to promote on `applied`,
    which is `helps` alone -- the map beats leaving the number raw on the
    held-out half. That is the right bar for PUBLISHING a number and the wrong
    one for DECIDING on it: `mlb_prop_pitcher_er` helps (11.9pp -> 6.8pp) and
    still does not close, and its own fit says so in the note -- "publish it; do
    not build a threshold on it yet". A cut built on a map that does not close
    is a cut aimed at a number that is still wrong, only less so.

    So promotion now requires `helps AND transfers`, and it writes the map's
    method and both verdicts into the `promoted_*` columns, so the decision path
    reads an endorsement frozen at promotion rather than one a nightly fit can
    rewrite underneath it (see load_calibrations).
    """
    ensure_schema(conn)
    rows = conn.execute(
        "SELECT model_id, a, b, method, payload FROM model_calibration "
        "WHERE applied").fetchall()
    done = []
    for model_id, a, b, method, payload in rows:
        if model_ids and model_id not in model_ids:
            continue
        if a is None or b is None or method != "platt":
            logger.warning("promote: {} has no fitted map — skipped", model_id)
            continue
        try:
            verdict = json.loads(payload) if payload else {}
        except (TypeError, ValueError):
            verdict = {}
        helps = bool(verdict.get("helps"))
        transfers = bool(verdict.get("transfers"))
        # `endorsed` is the fit's own promotion verdict (2026-09-19): helps AND
        # transfers for a two-parameter map, helps (or prior-dominated) for a
        # shrunk offset. A payload written before it existed falls back to the
        # two-bar rule it encoded.
        endorsed = bool(verdict.get("endorsed", helps and transfers))
        if not endorsed:
            logger.warning(
                "promote: {} not endorsed (helps={}, transfers={}) — skipped",
                model_id, helps, transfers)
            continue
        conn.execute("""
            UPDATE model_calibration
            SET promoted = TRUE, promoted_a = %(a)s, promoted_b = %(b)s,
                promoted_at = %(at)s, promoted_method = %(method)s,
                promoted_helps = %(helps)s, promoted_transfers = %(transfers)s
            WHERE model_id = %(m)s
        """, {"m": model_id, "a": a, "b": b, "method": method,
              "helps": helps, "transfers": transfers,
              "at": datetime.now().astimezone().isoformat()})
        done.append(model_id)
    return done


def promote_external(conn, model_id: str, a: float, b: float, *, n: int,
                     source: str, helps: bool, transfers: bool) -> None:
    """Promote a map fitted OUTSIDE the nightly candidate path. A model update.

    The nightly fit reads a lane's settled BETs, which for a live lane is one
    narrow band above its own floor (fetch_graded); a map fitted on a bought
    season of in-play history covers the whole range and is the better map,
    but it has no candidate row to be promoted from -- and `promote()` copies
    from the candidate columns, which the 6am fit rewrites. This writes the
    promoted_* columns directly, with the verdicts the caller measured on its
    own date split, and leaves the candidate columns to the nightly fit.

    Provenance lives in `promoted_source` (added here), a column the nightly
    fit never touches: "<source> n=<n> a=<a> b=<b>".
    """
    ensure_schema(conn)
    if not schema_is_current(conn, "model_calibration", columns=("promoted_source",)):
        try:
            conn.execute("ALTER TABLE model_calibration ADD COLUMN IF NOT EXISTS promoted_source TEXT")
        except Exception:  # noqa: BLE001 -- sqlite lacks IF NOT EXISTS on some versions
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
    if not (helps and transfers):
        raise ValueError(f"{model_id}: a map that does not help AND transfer is not promoted "
                         f"(helps={helps}, transfers={transfers})")
    now = datetime.now().astimezone().isoformat()
    conn.execute("""
        INSERT INTO model_calibration (model_id, fitted_at, n, applied, payload,
                                       promoted, promoted_a, promoted_b, promoted_at,
                                       promoted_method, promoted_helps, promoted_transfers,
                                       promoted_source)
        VALUES (%(m)s, %(at)s, 0, FALSE, '{}',
                TRUE, %(a)s, %(b)s, %(at)s, 'platt', TRUE, TRUE, %(src)s)
        ON CONFLICT (model_id) DO UPDATE SET
            promoted = TRUE, promoted_a = EXCLUDED.promoted_a,
            promoted_b = EXCLUDED.promoted_b, promoted_at = EXCLUDED.promoted_at,
            promoted_method = 'platt', promoted_helps = TRUE, promoted_transfers = TRUE,
            promoted_source = EXCLUDED.promoted_source
    """, {"m": model_id, "at": now, "a": a, "b": b,
          "src": f"{source} n={n} a={a:.6f} b={b:.6f}"})


def demote(conn, model_ids: list[str]) -> list[str]:
    """Take a map back out of the decision path. The inverse of promote().

    Exists because there was no way to undo a promotion except by hand-editing
    the table, and a lever with no off switch is one nobody dares pull. Clears
    every `promoted_*` column, so a demoted row cannot be read as half-promoted.
    """
    ensure_schema(conn)
    done = []
    for model_id in model_ids:
        conn.execute("""
            UPDATE model_calibration
            SET promoted = FALSE, promoted_a = NULL, promoted_b = NULL,
                promoted_method = NULL, promoted_helps = NULL,
                promoted_transfers = NULL, promoted_at = %(at)s
            WHERE model_id = %(m)s
        """, {"m": model_id, "at": datetime.now().astimezone().isoformat()})
        done.append(model_id)
    return done


def run_calibration_fit(conn=None) -> list[dict]:
    own = conn is None
    conn = conn or get_connection()
    reports = []
    try:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        pool = fit_pool(conn, active)
        logger.info("probability calibration: pooled offset {:+.4f} from {} models",
                    pool["b"], pool["n_models"])
        for model_id in sorted(config.ACTION_THRESHOLDS):
            try:
                rep = fit_model(conn, model_id, active.get(model_id), pool)
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
    ap.add_argument("--promote", action="store_true",
                    help="copy every ENDORSED candidate (helps AND transfers) "
                         "into the promoted slot the scorer reads. A model "
                         "update (CLAUDE.md 1b).")
    ap.add_argument("--demote", metavar="MODEL_ID", nargs="+",
                    help="take these maps back out of the decision path. Also "
                         "a model update.")
    ap.add_argument("--models", metavar="MODEL_ID", nargs="+",
                    help="restrict --promote to these model_ids")
    ap.add_argument("--promote-external", metavar=("MODEL_ID", "A", "B", "N", "SOURCE"),
                    nargs=5, help="promote a map fitted outside the nightly path "
                                  "(its own date-split verdicts must be helps AND "
                                  "transfers; state them with --verdict). A model update.")
    ap.add_argument("--verdict", metavar=("HELPS", "TRANSFERS"), nargs=2, default=None)
    args = ap.parse_args()
    conn = get_connection()
    if args.promote_external:
        m, a, b, n, src = args.promote_external
        helps, transfers = [v.lower() == "true" for v in (args.verdict or ("false", "false"))]
        try:
            promote_external(conn, m, float(a), float(b), n=int(n), source=src,
                             helps=helps, transfers=transfers)
            conn.commit()
            print(f"PROMOTED (external) {m}: a={float(a):.6f} b={float(b):.6f} from {src}")
        finally:
            conn.close()
        return
    if args.demote:
        try:
            done = demote(conn, list(args.demote))
            conn.commit()
            print(f"DEMOTED {len(done)}: {', '.join(sorted(done))}")
        finally:
            conn.close()
        return
    if args.promote:
        try:
            done = promote(conn, args.models)
            conn.commit()
            print(f"PROMOTED {len(done)}: {', '.join(sorted(done)) or '(none)'}")
        finally:
            conn.close()
        return
    try:
        active = dict(conn.execute("""
            SELECT model_id, substring(created_at,1,10)
            FROM model_registry WHERE is_active = 1
        """).fetchall())
        pool = fit_pool(conn, active)
        print(f"pooled offset {pool['b']:+.4f} from {pool['n_models']} models: "
              + ", ".join(f"{m} {b:+.2f}" for m, b in sorted(pool["per_model"].items())))
        print(f"{'model':<30}{'n':>7}{'raw gap':>9}{'fit':>7}{'b':>8}"
              f"{'held-out raw->cal':>18}{'helps':>7}  note")
        for model_id in sorted(config.ACTION_THRESHOLDS):
            rep = fit_model(conn, model_id, active.get(model_id), pool)
            if rep.get("transfer_gap_pp") is not None:
                tr = f"{rep['transfer_raw_gap_pp']:.1f}->{rep['transfer_gap_pp']:.1f}"
                helps = "yes" if rep["helps"] else "NO"
            else:
                tr, helps = "—", "—"
            b = f"{rep['b']:+.3f}" if rep.get("b") is not None else "—"
            print(f"{model_id:<30}{rep['n']:>7}{rep['raw_gap_pp']:>+9.1f}"
                  f"{rep.get('fit') or '—':>7}{b:>8}"
                  f"{tr:>18}{helps:>7}  {rep.get('note','')[:60]}")
            if not args.dry_run:
                persist(conn, rep)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    main()
