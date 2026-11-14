"""Build models/saved/ufc_open_moneyline.json, the UFC opening-price model's
artifact, from Supabase alone.

The fit is the research fit (scripts/ufc_study/ml_anchor.py, ridge 30): every
UFC fight with a win or a loss and a BestFightOdds open and close for both
fighters (ufc_price_archive, source bfo_fight_canon_db, both slugs equal to
our fight log's), the open's no-vig price as the unpenalised offset, the
fighter-minus-fighter inputs of models/ufc_ratings.py standardised on the
fitted fights. --through YEAR fits on the fights before YEAR+1 only, which
is how the research's walk-forward fold for that year is reproduced.

    python -m scripts.ufc_open_moneyline_build                # print, write nothing
    python -m scripts.ufc_open_moneyline_build --write
    python -m scripts.ufc_open_moneyline_build --through 2025 # the research's 2026 fold
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timezone

import numpy as np
from loguru import logger

from models import ufc_ratings as R
from models.ufc_open_moneyline import (ARTIFACT, MAX_GAP_MIN, MIN_LEAD_H, MODEL_ID, RIDGE,
                                       fit, logit, novig_a)

SOURCE = "bfo_fight_canon_db"


def training_rows(conn, through: int | None = None) -> list[dict]:
    rows, profiles = R.load(conn)
    z_by_game, sides = {}, {}

    def keep(gid, a, b, z):
        z_by_game[gid] = z
        sides[gid] = (R.slugify(a["fighter_name"]), R.slugify(b["fighter_name"]),
                      a["result"], R._day(a["game_date"]))

    R.replay(rows, profiles, on_fight=keep)
    prices = defaultdict(dict)
    for gid, slug, op, lo in conn.execute("""
            SELECT game_id, fighter_slug, price_open, close_low FROM ufc_price_archive
             WHERE source = %s AND market = 'h2h' AND game_id IS NOT NULL""", (SOURCE,)).fetchall():
        prices[gid][slug] = (op, lo)
    out = []
    for gid, (sa, sb, res, on) in sides.items():
        p = prices.get(gid, {})
        if res not in ("win", "loss") or sa not in p or sb not in p:
            continue
        (oa, la), (ob, lb) = p[sa], p[sb]
        if None in (oa, ob, la, lb):
            continue
        if through is not None and on.year > through:
            continue
        out.append({"game_id": gid, "date": on, "a_won": res == "win",
                    "p_open": novig_a(oa, ob), **z_by_game[gid]})
    return out


def build(conn, through: int | None = None) -> dict:
    T = training_rows(conn, through)
    feats = list(R.FEATURES)
    X = np.array([[t[f] for f in feats] for t in T], dtype=float)
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0, ddof=1)
    sd[sd == 0] = 1.0
    Xs = np.nan_to_num((X - mu) / sd, nan=0.0)
    off = np.array([logit(t["p_open"]) for t in T])
    y = np.array([t["a_won"] for t in T], dtype=float)
    b = fit(Xs, off, y, RIDGE)
    return {
        "model_id": MODEL_ID,
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fitted_through": max(t["date"] for t in T).isoformat(),
        "n_fights": len(T),
        "ridge": RIDGE, "min_lead_h": MIN_LEAD_H, "max_gap_min": MAX_GAP_MIN,
        "features": feats, "mu": [float(v) for v in mu], "sd": [float(v) for v in sd],
        "b": [float(v) for v in b],
        "source": "ufc_fight_log + fighters + ufc_price_archive (bfo_fight_canon_db opens)",
        "evidence": "docs/ufc_market_audit.md section 3d",
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--through", type=int)
    a = ap.parse_args()
    from data.db import get_connection
    conn = get_connection()
    try:
        art = build(conn, a.through)
    finally:
        conn.close()
    logger.info(f"{art['n_fights']} fights through {art['fitted_through']}; "
                f"b = {dict(zip(art['features'], [round(v, 3) for v in art['b']]))}")
    if a.write:
        if a.through is not None:
            raise SystemExit("--write builds on every fight; drop --through")
        ARTIFACT.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8")
        logger.success(f"wrote {ARTIFACT}")


if __name__ == "__main__":
    main()
