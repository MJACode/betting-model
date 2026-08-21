"""
mlb_runline_sweep.py — re-derive the `mlb_runline` threshold on real DraftKings
run-line prices, with a mechanical plateau check.

WHY THIS EXISTS
---------------
`mlb_runline` went dormant: it has not produced a single BET pick since
2026-07-19, and in August 2026 its maximum probability across the whole month
was 0.625 — it never reaches its own 0.68 prob floor, so it cannot fire. That is
the same "0 picks, ever" symptom `wnba_over_under` had (session 106).

The cause is NOT the threshold drifting; it is that the model's live INPUTS were
broken when the 0.68 cut was chosen, and were then repaired:

  * 2026-07-04 — the bullpen freeze fix (session 92/93). `mlb_bullpen_stats` had
    been frozen since 2026-04-14, so `home/away_bullpen_ip_last1/3` were 0.0 for
    every live-scored game — the model was told every bullpen was fully rested.
  * 2026-07-05 — the NaN-line fix (session 95b). Full-game totals/spreads were
    predicted with `spread_home` NaN at every live scoring call.

Weekly max probability collapses exactly across that boundary:

    wk 06-29  max_p 0.757   (4-11 sides/wk over the 0.68 bar in June)
    wk 07-06  max_p 0.554   (zero, every week since)

So the pre-July probabilities were inflated by out-of-distribution inputs, and
the +21.7% / 20-bet record the current cut shows was earned almost entirely in
that broken-input era. The cut was already documented as "carried over
UNVALIDATED" when the model was swapped on 2026-07-04 (§17) — 2025 has no
run-line prices to validate against and 2026 was in-sample for that model.

WHAT THIS SCRIPT IS FOR
-----------------------
2026 is the ONLY season carrying real DK run-line prices (1,694 priced games;
2019-2025 have the fixed -1.5 line but zero prices). So a model retrained on
2019-2025 with 2026 held out can — for the first time — be swept out-of-sample
against real prices. This script does that sweep.

    python -m scripts.mlb_runline_sweep --seasons 2026
    python -m scripts.mlb_runline_sweep --seasons 2026 --csv /tmp/rl.csv

Run it where the DB is reachable (Railway worker, Matt's machine, or the
`Runline Threshold Sweep` GitHub Action) — the dev sandbox has neither psycopg2
nor DATABASE_URL.

READ THE OUTPUT LIKE THIS
-------------------------
  * The `PROB REACH` block is the first thing to check. If the model never
    reaches a candidate prob floor, that floor is unusable no matter how good
    its ROI looks — that is exactly how this model went dormant.
  * Ignore thin cells. A 15-bet +30% cell is noise.
  * Take a cut from a PLATEAU, not a peak. This script scores that for you:
    `nbrs+` counts how many of a cell's 8 neighbours are also positive. The
    repeated lesson (sessions 68 / 74 / 87 / 101) is that a high-ROI cell with
    negative neighbours is an artifact — session 87 found a runline cut that
    rested on a grading sign bug, and session 74 found the documented "+23.8%"
    cut was actually -20% once outcomes were graded correctly.
  * Check `away_pct`. Session 74 established that this model's only real edge is
    high-conviction AWAY +1.5 (laying home -1.5 has never been profitable). A
    grid that is 100% one side is a systematic lean, not per-game skill — but
    for this market a strong away tilt is expected and is not by itself a red
    flag.
  * If the whole grid is negative, the honest answer is that the model needs
    feature work and should stay off. Do NOT ship the least-bad cell.
"""

import argparse
from pathlib import Path
import sys

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection
from features.feature_engine import (
    FEATURE_MAP,
    _build_bulk_mlb_lookups,
    _build_mlb_features_from_bulk,
    _is_pregame_snapshot,
)
from models.scorer import american_to_implied_prob, american_to_decimal
from models.trainer import load_model

MODEL_ID = "mlb_runline"


def _fetch_games(conn, seasons: list[int]) -> list[dict]:
    """Completed MLB games in the requested seasons."""
    placeholders = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT game_id, game_date, home_team, away_team,
               home_score, away_score, commence_time
        FROM games
        WHERE sport = 'MLB'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
          AND CAST(SUBSTR(game_date, 1, 4) AS INTEGER) IN ({placeholders})
        ORDER BY game_date, game_id
    """, seasons).fetchall()
    return [
        dict(game_id=r[0], game_date=r[1], home_team=r[2], away_team=r[3],
             home_score=float(r[4]), away_score=float(r[5]), commence_time=r[6])
        for r in rows
    ]


def _pregame_odds(conn) -> dict:
    """
    (game_id) → newest genuinely PRE-GAME DK run-line row.

    `ABS(spread_home) = 1.5` matches the scorer / paper_tracker run-line filter:
    MLB spreads rows can also carry alternate numbers, and only +/-1.5 is the
    run line this model prices.

    Deliberately independent of the bulk loader's odds dict so the GRADING
    prices are verified pre-game here too — a post-start price would distort ROI
    even when the feature line is clean (the session-106 leak class).
    """
    rows = conn.execute("""
        SELECT o.game_id, o.snapshot_at, g.commence_time,
               o.spread_home, o.home_price, o.away_price
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE g.sport = 'MLB'
          AND o.market = 'spreads'
          AND o.bookmaker = 'draftkings'
          AND o.snapshot_type != 'in_play'
          AND o.spread_home IS NOT NULL
          AND ABS(o.spread_home) = 1.5
        ORDER BY o.game_id, o.snapshot_at DESC
    """).fetchall()

    out: dict = {}
    for gid, snap, commence, spread_home, home_p, away_p in rows:
        if gid in out:
            continue                                   # newest-first: first kept
        if not _is_pregame_snapshot(snap, commence):
            continue                                   # post-start → leaked
        out[gid] = dict(spread_home=spread_home, home_price=home_p,
                        away_price=away_p, snapshot_at=snap)
    return out


def _side_rows(game: dict, prob_home: float, odds: dict) -> list[dict]:
    """
    One row per bettable side with the model prob, real pre-game price, edge and
    whether that side actually covered.

    Grading convention — MUST match paper_tracker and the record views.
    `scored_line` is the HOME spread, so:
        home covers iff (home - away) + spread_home > 0
        away covers iff the same quantity is < 0      [the session-87 sign fix]
    A misread of this is what produced the phantom "+14.9%" runline plateau that
    session 87 had to retract, so it is asserted rather than assumed.
    """
    line = odds.get("spread_home")
    if line is None:
        return []

    margin = game["home_score"] - game["away_score"]
    home_cover = margin + float(line)
    if home_cover == 0:
        return []                                       # push (x.5 → shouldn't occur)

    won = {"home": home_cover > 0, "away": home_cover < 0}
    price = {"home": odds.get("home_price"), "away": odds.get("away_price")}
    prob = {"home": prob_home, "away": 1.0 - prob_home}

    rows: list[dict] = []
    for side in ("home", "away"):
        american = price[side]
        if american is None:
            continue
        implied = american_to_implied_prob(american)
        if not implied:
            continue
        stake = 100.0
        profit = (stake * (american_to_decimal(american) - 1.0)
                  if won[side] else -stake)
        rows.append(dict(
            game_id=game["game_id"], game_date=game["game_date"], side=side,
            spread_home=float(line), model_prob=prob[side],
            dk_odds=float(american), implied=implied,
            edge=prob[side] - implied, won=bool(won[side]),
            stake=stake, profit=profit,
        ))
    return rows


def build_side_table(seasons: list[int]) -> pd.DataFrame:
    """Score every completed game and return one row per bettable side."""
    artifact = load_model(MODEL_ID)
    if not artifact:
        raise SystemExit(f"No active model artifact for {MODEL_ID} — train it first.")
    clf = artifact["model"]
    feature_cols = FEATURE_MAP[MODEL_ID]

    conn = get_connection()
    try:
        games = _fetch_games(conn, seasons)
        if not games:
            raise SystemExit(f"No completed MLB games found for seasons {seasons}.")
        odds_by_game = _pregame_odds(conn)
        logger.info(f"{len(games)} completed games; "
                    f"{len(odds_by_game)} have a pre-game DK run line")
        bulk = _build_bulk_mlb_lookups(conn, seasons)
    finally:
        conn.close()

    rows: list[dict] = []
    skipped_no_odds = skipped_no_features = 0

    for game in games:
        odds = odds_by_game.get(game["game_id"])
        if not odds:
            skipped_no_odds += 1
            continue

        season = int(game["game_date"][:4])
        feats = _build_mlb_features_from_bulk(
            bulk, game["game_id"], game["game_date"],
            game["home_team"], game["away_team"], season,
            # Feed the verified pre-game row so the model sees exactly what live
            # scoring would have seen. `spread_home` is a run-line feature, and
            # feeding NaN here is the very bug that broke live scoring until
            # 2026-07-05 — so this must never be omitted.
            odds_row=odds,
        )
        if not feats:
            skipped_no_features += 1
            continue

        X = pd.DataFrame([{c: feats.get(c) for c in feature_cols}])[feature_cols]
        if X.isnull().all(axis=1).iloc[0]:
            skipped_no_features += 1
            continue

        prob_home = float(clf.predict_proba(X)[0][1])
        rows.extend(_side_rows(game, prob_home, odds))

    logger.info(f"skipped: {skipped_no_odds} no pre-game run line, "
                f"{skipped_no_features} no features")
    return pd.DataFrame(rows)


PROB_FLOORS = [round(x, 2) for x in np.arange(0.40, 0.73, 0.02)]
EDGE_FLOORS = [round(x, 2) for x in np.arange(0.00, 0.21, 0.02)]


def sweep(df: pd.DataFrame, min_bets: int) -> pd.DataFrame:
    """Grid prob x edge over the side table; flat $100 stakes at real DK prices."""
    out = []
    for pf in PROB_FLOORS:
        for ef in EDGE_FLOORS:
            sel = df[(df.model_prob >= pf) & (df.edge >= ef)]
            if len(sel) == 0:
                continue
            staked = sel.stake.sum()
            profit = sel.profit.sum()
            wins = int(sel.won.sum())
            away = int((sel.side == "away").sum())
            out.append(dict(
                min_prob=pf, min_edge=ef, bets=len(sel),
                wins=wins, losses=len(sel) - wins,
                win_pct=round(100.0 * wins / len(sel), 1),
                units=round(profit / 100.0, 2),
                roi_pct=round(100.0 * profit / staked, 2),
                away_pct=round(100.0 * away / len(sel), 0),
                thin=len(sel) < min_bets,
            ))
    return pd.DataFrame(out)


def plateau_score(grid: pd.DataFrame, min_prob: float, min_edge: float) -> tuple[int, int]:
    """
    (positive_neighbours, total_neighbours) for a cell.

    A cut is only trustworthy when the cells one grid step around it are ALSO
    positive. This encodes mechanically what sessions 68/74/87/101 had to learn
    by retracting cuts taken from thin peaks.
    """
    p_i = PROB_FLOORS.index(min_prob)
    e_i = EDGE_FLOORS.index(min_edge)
    pos = tot = 0
    for dp in (-1, 0, 1):
        for de in (-1, 0, 1):
            if dp == 0 and de == 0:
                continue
            pi, ei = p_i + dp, e_i + de
            if not (0 <= pi < len(PROB_FLOORS) and 0 <= ei < len(EDGE_FLOORS)):
                continue
            cell = grid[(grid.min_prob == PROB_FLOORS[pi])
                        & (grid.min_edge == EDGE_FLOORS[ei])]
            if cell.empty:
                continue
            tot += 1
            if float(cell.iloc[0].roi_pct) > 0:
                pos += 1
    return pos, tot


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seasons", nargs="+", type=int, default=[2026],
                    help="seasons to sweep (default 2026 — the only season with "
                         "real DK run-line prices)")
    ap.add_argument("--min-bets", type=int, default=30,
                    help="cells thinner than this are excluded from the "
                         "recommendation (default 30)")
    ap.add_argument("--csv", help="also write the raw side table here")
    args = ap.parse_args()

    df = build_side_table(args.seasons)
    if df.empty:
        raise SystemExit("No gradable sides — check that games have pre-game run lines.")

    if args.csv:
        df.to_csv(args.csv, index=False)
        logger.info(f"wrote side table → {args.csv}")

    print(f"\n=== {MODEL_ID} — sweep on real DK run-line prices, "
          f"seasons {args.seasons} ===")
    print(f"{len(df)} bettable sides across {df.game_id.nunique()} games")

    # ── PROB REACH ────────────────────────────────────────────────────────────
    # The dormancy check. A prob floor the model never reaches cannot produce a
    # single pick, however good its ROI looks in the grid.
    print(f"\n--- PROB REACH (model prob range "
          f"{df.model_prob.min():.3f} – {df.model_prob.max():.3f}) ---")
    for bar in (0.55, 0.60, 0.65, 0.68, 0.70):
        n = int((df.model_prob >= bar).sum())
        flag = "  <-- UNREACHABLE" if n == 0 else ""
        print(f"  sides at prob >= {bar:.2f}: {n:5d}{flag}")

    grid = sweep(df, args.min_bets)
    if grid.empty:
        print("\nNo gradable cells at all.")
        return

    usable = grid[~grid.thin]
    if usable.empty:
        print(f"\nNo cell reaches {args.min_bets} bets — sample too thin to cut on.")
        return

    usable = usable.sort_values("roi_pct", ascending=False)
    print(f"\n--- top cells (>= {args.min_bets} bets, by ROI) ---")
    show = usable.head(20).copy()
    show["nbrs+"] = [f"{plateau_score(grid, r.min_prob, r.min_edge)[0]}"
                     f"/{plateau_score(grid, r.min_prob, r.min_edge)[1]}"
                     for r in show.itertuples()]
    print(show[["min_prob", "min_edge", "bets", "wins", "losses", "win_pct",
                "units", "roi_pct", "away_pct", "nbrs+"]].to_string(index=False))

    best = usable.iloc[0]
    if best.roi_pct <= 0:
        print("\nVERDICT: every cell with real volume is negative. The honest "
              "answer is that this model needs FEATURE work, not a re-cut — "
              "leave it off and do not ship the least-bad cell.")
        return

    pos, tot = plateau_score(grid, best.min_prob, best.min_edge)
    print(f"\nBest cell: {best.min_prob:.2f}/{best.min_edge:.2f} = "
          f"{int(best.bets)} bets {int(best.wins)}-{int(best.losses)} "
          f"{best.roi_pct:+.2f}% ROI  ({int(best.away_pct)}% away +1.5)")
    print(f"Plateau: {pos}/{tot} neighbouring cells are also positive.")
    if tot and pos / tot >= 0.6:
        print("VERDICT: this sits on a plateau — safe to ship as the cut, and it "
              "IS reachable (see PROB REACH above). Re-sweep after ~40 settled "
              "forward picks.")
    else:
        print("VERDICT: this is a PEAK, not a plateau — its neighbours flip "
              "negative one grid step away. Shipping it would be fitting noise "
              "(the session-74/87 mistake). Prefer a lower-ROI cell with "
              "positive neighbours, or leave the model off.")


if __name__ == "__main__":
    main()
