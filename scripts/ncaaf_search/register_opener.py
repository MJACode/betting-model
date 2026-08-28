"""
Register the NCAAF cross-book opener rule as the active `ncaaf_spread`.

This is NOT a fitted model. It is a deterministic rule: where a SHARP book's
opening spread disagrees with a SOFT book's by >= the gate, back the side the
sharp book favours, at the soft book's stale number. The soft book is
DraftKings, which is also the book we price against, so the DK-only invariant
is untouched.

Backtest (CFBD archive, 2023-2025, 2,119 games carrying both books' openers):

    min |dev|   bets   win%    ROI
    1.0        1,050   58.1%   +10.9%
    2.0          483   59.6%   +13.8%
    2.5          344   60.5%   +15.4%

Positive in all three seasons (+7.7 / +14.8 / +9.2), CLV 0.694, and the
REVERSED book assignment is null (0 cells clear) -- the asymmetry that
distinguishes an edge from an artefact. Both placebos pass: the edge vanishes
if you bet the sharp book's open (-0.8%) or DK's close (-0.4%).

WHAT IS STILL UNPROVEN, and why the scorer enforces preconditions rather than
trusting this table: CFBD ships no timestamps, so we cannot tell from history
whether both openers were observable at the SAME MOMENT. If the sharp book's
number is merely recorded later, `dev` measures elapsed line movement and the
edge is not real. The scorer therefore refuses to bet unless the two openers
were captured within max_skew_min of each other AND DK is still on its opening
number. Those checks answer the question with live data instead of assuming it.

Consequence worth knowing: every NCAAF game already in the odds table was first
polled 2026-08-22, before Bovada was ingested at all. None of them can satisfy
simultaneity, so the rule will decline every one -- including Week 1. It starts
producing picks only for games first polled after Bovada is live.

Run:
    python -m scripts.ncaaf_search.register_opener
    python -m scripts.ncaaf_search.register_opener --gate 2.0 --dry-run
"""

from __future__ import annotations

import argparse
import pickle
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Validated records by gate (see module docstring). model_prob is the pooled
# out-of-sample win rate at that gate -- a flat number, because the rule has no
# per-game probability curve. Same shape as the section-28 NFL opener rule.
GATE_RECORDS = {
    1.0: {"bets": 1050, "win_rate": 0.5810, "roi": 0.1091},
    2.0: {"bets": 483, "win_rate": 0.5963, "roi": 0.1383},
    2.5: {"bets": 344, "win_rate": 0.6047, "roi": 0.1543},
}

# DISJOINT BANDS (scripts/ncaaf_search/opener_strategy.py --experiment bands).
# A tighter gate is a SUBSET of a looser one, so two models sharing a floor
# would double-bet the same game. These bands do not overlap: every qualifying
# game belongs to exactly one, which is what makes the premium tier additive
# rather than a re-slice. Both clear breakeven at 95% on their own and are
# positive in all three seasons.
BAND_RECORDS = {
    "ncaaf_spread": {              # [1.0, 2.5)  -- the standard tier
        "gate": 1.0, "gate_max": 2.5,
        "bets": 706, "win_rate": 0.5694, "roi": 0.0870,
        "ci": (0.533, 0.605), "per_season": {2023: 0.552, 2024: 0.590, 2025: 0.564},
    },
    "ncaaf_spread_premium": {      # [2.5, inf)  -- high conviction, low volume
        "gate": 2.5, "gate_max": None,
        "bets": 344, "win_rate": 0.6047, "roi": 0.1543,
        "ci": (0.552, 0.655), "per_season": {2023: 0.597, 2024: 0.620, 2025: 0.590},
    },
}

SHARP_BOOK = "bovada"
DEFAULT_GATE = 1.0
DEFAULT_MAX_SKEW_MIN = 90.0


def build_artifact(gate: float = DEFAULT_GATE,
                   sharp_book: str = SHARP_BOOK,
                   max_skew_min: float = DEFAULT_MAX_SKEW_MIN) -> dict:
    rec = GATE_RECORDS.get(gate)
    if rec is None:
        raise SystemExit(f"No validated record for gate {gate}; "
                         f"known gates: {sorted(GATE_RECORDS)}")
    return {
        "kind": "cross_book_opener",
        "model": None,              # deterministic rule; the scorer never predicts
        "feature_cols": [],         # needs no features
        "market": "spreads",
        "sharp_book": sharp_book,
        "soft_book": "draftkings",
        "d_threshold": float(gate),
        "max_skew_min": float(max_skew_min),
        "model_prob": rec["win_rate"],
        "backtest": {"seasons": [2023, 2024, 2025], **rec},
        "version": datetime.now().strftime("%Y%m%d_%H%M%S"),
    }


def build_band_artifact(model_id: str, sharp_book: str = SHARP_BOOK,
                        max_skew_min: float = DEFAULT_MAX_SKEW_MIN) -> dict:
    """
    Artifact for one DISJOINT band. `d_threshold_max` is what keeps the tiers
    mutually exclusive in the scorer; without it the premium band's games would
    also fire the standard model.
    """
    rec = BAND_RECORDS.get(model_id)
    if rec is None:
        raise SystemExit(f"No band record for {model_id}; "
                         f"known: {sorted(BAND_RECORDS)}")
    a = build_artifact(rec["gate"], sharp_book, max_skew_min)
    a["d_threshold_max"] = rec["gate_max"]
    a["model_prob"] = rec["win_rate"]
    a["backtest"] = {"seasons": [2023, 2024, 2025],
                     "bets": rec["bets"], "win_rate": rec["win_rate"],
                     "roi": rec["roi"], "band": [rec["gate"], rec["gate_max"]],
                     "per_season": rec["per_season"]}
    return a


def register(artifact: dict, dry_run: bool = False,
             model_id: str = "ncaaf_spread") -> str:
    from loguru import logger
    from data.db import get_connection

    version = artifact["version"]
    out = (Path(__file__).parent.parent.parent / "models" / "saved"
           / f"{model_id}_{version}.pkl")
    rel = out.relative_to(Path(__file__).parent.parent.parent).as_posix()

    if dry_run:
        print(f"[dry-run] would write {rel}")
        for k in ("kind", "sharp_book", "soft_book", "d_threshold",
                  "max_skew_min", "model_prob"):
            print(f"    {k}: {artifact[k]}")
        return version

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(artifact, f)

    bt = artifact["backtest"]
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE model_registry SET is_active = 0
            WHERE model_id = %s AND is_active = 1
        """, (model_id,))
        conn.execute("""
            INSERT INTO model_registry (
                model_id, version, trained_on, train_seasons, holdout_season,
                holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                is_active, model_path, notes
            ) VALUES (%s, %s, %s, %s, NULL, %s, %s, %s, NULL, 1, %s, %s)
        """, (model_id, version, date.today().isoformat(), str(bt["seasons"]),
              round(bt["win_rate"], 4), round(bt["roi"], 4), bt["bets"], rel,
              f"cross-book opener | sharp={artifact['sharp_book']} "
              f"| gate |dev|>={artifact['d_threshold']} "
              f"| max opener skew {artifact['max_skew_min']}min"))
        conn.commit()
    finally:
        conn.close()

    logger.success(f"Registered {model_id} v{version} (cross-book opener)")
    print(f"\nCommit the artifact so the worker can score:")
    print(f"  git add -f {rel}")
    return version


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=float, default=DEFAULT_GATE,
                    choices=sorted(GATE_RECORDS))
    ap.add_argument("--sharp-book", default=SHARP_BOOK)
    ap.add_argument("--max-skew-min", type=float, default=DEFAULT_MAX_SKEW_MIN)
    ap.add_argument("--bands", action="store_true",
                    help="register BOTH disjoint tiers (standard + premium) "
                         "instead of a single unbounded gate")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.bands:
        for model_id in ("ncaaf_spread", "ncaaf_spread_premium"):
            art = build_band_artifact(model_id, a.sharp_book, a.max_skew_min)
            bt = art["backtest"]
            hi = art["d_threshold_max"]
            band = (f"[{art['d_threshold']:g}, {hi:g})" if hi
                    else f"[{art['d_threshold']:g}, inf)")
            print("")
            print(f"{model_id}  band {band}")
            print(f"  {bt['bets']} bets, {bt['win_rate']:.1%}, "
                  f"ROI {bt['roi']:+.1%}, per-season {bt['per_season']}")
            print(f"  flat model_prob = {art['model_prob']:.4f}")
            register(art, a.dry_run, model_id=model_id)
        return 0

    art = build_artifact(a.gate, a.sharp_book, a.max_skew_min)
    rec = art["backtest"]
    print(f"cross-book opener | sharp={art['sharp_book']} soft={art['soft_book']}")
    print(f"gate |dev| >= {art['d_threshold']}  ->  "
          f"{rec['bets']} bets, {rec['win_rate']:.1%}, ROI {rec['roi']:+.1%}")
    print(f"flat model_prob = {art['model_prob']:.4f}")
    print(f"max opener skew = {art['max_skew_min']:.0f} min")
    register(art, a.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
