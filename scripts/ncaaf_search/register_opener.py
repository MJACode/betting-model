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


def register(artifact: dict, dry_run: bool = False) -> str:
    from loguru import logger
    from data.db import get_connection

    version = artifact["version"]
    out = (Path(__file__).parent.parent.parent / "models" / "saved"
           / f"ncaaf_spread_{version}.pkl")
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
            WHERE model_id = 'ncaaf_spread' AND is_active = 1
        """)
        conn.execute("""
            INSERT INTO model_registry (
                model_id, version, trained_on, train_seasons, holdout_season,
                holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                is_active, model_path, notes
            ) VALUES ('ncaaf_spread', %s, %s, %s, NULL, %s, %s, %s, NULL, 1, %s, %s)
        """, (version, date.today().isoformat(), str(bt["seasons"]),
              round(bt["win_rate"], 4), round(bt["roi"], 4), bt["bets"], rel,
              f"cross-book opener | sharp={artifact['sharp_book']} "
              f"| gate |dev|>={artifact['d_threshold']} "
              f"| max opener skew {artifact['max_skew_min']}min"))
        conn.commit()
    finally:
        conn.close()

    logger.success(f"Registered ncaaf_spread v{version} (cross-book opener)")
    print(f"\nCommit the artifact so the worker can score:")
    print(f"  git add -f {rel}")
    return version


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=float, default=DEFAULT_GATE,
                    choices=sorted(GATE_RECORDS))
    ap.add_argument("--sharp-book", default=SHARP_BOOK)
    ap.add_argument("--max-skew-min", type=float, default=DEFAULT_MAX_SKEW_MIN)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

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
