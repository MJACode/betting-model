"""mlb_live_total_runs against a full season of bought in-play DK totals.

THE INSTRUMENT. The 2026-09-09 cut sweep ran on 47 slates of our own feed --
34 bets at the shipped cut, an interval of [60%, 84%]. This runs the SAME
decision rule over every 5-minute DK in-play snapshot of the 2025 season
(data/ingestors/mlb_inplay_history.py), out of sample for the active artifact
(trained through 2024): ~2,400 games instead of 520.

HOW A QUOTE GETS A STATE. Each DK snapshot is paired with the play-by-play
via the plays' clock times (scripts/inplay_state_align.GameClock): the
plate appearance in progress when the snapshot was served, or the next one's
before-state between plate appearances. Pre-game features come from the
training path's bulk lookups with the pregame totals row, so
`pregame_total_line` means what it meant in training.

TWO GRIDS, NOT ONE. A DK market carries its own `last_update`; when the score
moved between that update and the snapshot, the quote is stale and the
"edge" is the run itself, priced twice (docs/thresholds.md, the cap
paragraph). Every candidate carries `runs_since_update`, and every table is
printed for ALL quotes and for FRESH quotes only (runs_since_update == 0).
Fresh-only is the production-realisable rule -- the live loop can enforce it
once it records DK's last_update -- and the honest one to read a cut off.

    python -m scripts.inplay_history_backtest --season 2025
    python -m scripts.inplay_history_backtest --season 2025 --rebuild

The candidate cache lives in the temp dir, like live_cut_sweep's.
"""
from __future__ import annotations

import argparse
import pickle
import tempfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from config import LIVE_MAX_EDGE_CAP
from data.db import get_connection
from features.live_game_features import build_live_state_row
from models.live_scorer import expected_value
from models.scorer import _count_over_prob
from models.trainer import load_model
from data.ingestors.mlb_pbp_ingestor import mlb_game_final
from scripts import live_cut_sweep as sweep
from scripts.inplay_state_align import GameClock
from scripts.live_inning_gate_replay import MODEL_ID, _grade, _implied

SPLIT = "2025-07-01"
PLAY_COLS = ["play_index", "inning", "half_inning", "outs_before", "bases_before",
             "score_home_before", "score_away_before", "start_time", "end_time"]


def _lu(source: str) -> str | None:
    if not source or "|lu=" not in source:
        return None
    v = source.split("|lu=", 1)[1].split("|", 1)[0]
    return None if v in ("", "None") else v


def build_cache(season: int, cache: Path) -> list[dict]:
    from features.feature_engine import (_build_bulk_mlb_lookups,
                                         _build_mlb_features_from_bulk)
    conn = get_connection()
    art = load_model(MODEL_ID)
    cols, clf, disp = art["feature_cols"], art["model"], art.get("dispersion")
    try:
        # Canonical ids only (the odds ingestor's abbreviations). A game whose
        # live row is unscored takes its final from the SBR twin -- see
        # mlb_pbp_ingestor._SBR_TWIN for the four-franchise split.
        raw = conn.execute("""
            SELECT game_id, game_date, season, home_team, away_team,
                   home_score, away_score
            FROM games WHERE sport = 'MLB' AND season = %s
              AND data_source <> 'sbr_csv'
            ORDER BY game_date, game_id""", (season,)).fetchall()
        gcols = ["game_id", "game_date", "season", "home_team", "away_team",
                 "home_score", "away_score"]
        games = []
        for r in raw:
            g = dict(zip(gcols, r))
            if g["home_score"] is None or g["away_score"] is None:
                final = mlb_game_final(conn, g["game_id"])
                if final is None:
                    continue
                g["home_score"], g["away_score"] = final[0], final[1]
            games.append(g)
        print(f"{len(games)} completed {season} games", flush=True)

        quotes = defaultdict(list)
        for r in conn.execute("""
            SELECT game_id, snapshot_at, total_line, over_price, under_price, source
            FROM odds WHERE snapshot_type = 'in_play' AND bookmaker = 'draftkings'
              AND market = 'totals' AND total_line IS NOT NULL
              AND source LIKE 'historical_inplay|%%'
              AND game_id LIKE %s
            ORDER BY game_id, snapshot_at""", (f"MLB_{season}-%",)).fetchall():
            quotes[r[0]].append({"snapshot_at": r[1], "total_line": r[2],
                                 "over_price": r[3], "under_price": r[4],
                                 "last_update": _lu(r[5])})
        print(f"{sum(map(len, quotes.values()))} quotes over {len(quotes)} games", flush=True)

        plays = defaultdict(list)
        for r in conn.execute(f"""
            SELECT game_id, {', '.join(PLAY_COLS)} FROM plays
            WHERE game_id LIKE %s AND start_time IS NOT NULL
            ORDER BY game_id, play_index""", (f"MLB_{season}-%",)).fetchall():
            plays[r[0]].append(dict(zip(PLAY_COLS, r[1:])))
        print(f"timed plays for {len(plays)} games", flush=True)

        bulk = _build_bulk_mlb_lookups(conn, [season])
    finally:
        conn.close()

    out = []
    rows, meta = [], []
    for g in games:
        gid = g["game_id"]
        if gid not in quotes or gid not in plays:
            continue
        pre = _build_mlb_features_from_bulk(
            bulk, gid, g["game_date"], g["home_team"], g["away_team"], g["season"],
            bulk["odds"].get((gid, "h2h")), totals_row=bulk["odds"].get((gid, "totals")))
        if not pre:
            continue
        clock = GameClock(plays[gid])
        gi = len(out)
        out.append({"game": g, "cands": [], "n_quotes": len(quotes[gid]), "n_priced": 0})
        for q in quotes[gid]:
            st = clock.state_at(q["snapshot_at"])
            if st is None:
                continue
            row = build_live_state_row(st, pre, MODEL_ID)
            if row is None:
                continue
            runs_moved = None
            if q["last_update"]:
                st_lu = clock.state_at(q["last_update"])
                if st_lu is not None:
                    runs_moved = (int(st["home_score"]) + int(st["away_score"])
                                  - int(st_lu["home_score"]) - int(st_lu["away_score"]))
            rows.append([np.nan if row.get(c) is None else float(row[c]) for c in cols])
            meta.append((gi, q, row["total_runs"], st.get("inning"), runs_moved))
    print(f"{len(rows)} priced states over {len(out)} games; predicting", flush=True)

    lam_all = np.clip(clf.predict(np.array(rows, dtype=float)), 1e-6, None)
    for lam, (gi, q, total_runs, inning, runs_moved) in zip(lam_all, meta):
        out[gi]["n_priced"] += 1
        rest = float(q["total_line"]) - total_runs
        if rest < 0:
            continue
        p_over = _count_over_prob(float(lam), rest, disp)
        for side, prob, odds in (("over", p_over, q["over_price"]),
                                 ("under", 1 - p_over, q["under_price"])):
            if odds is None:
                continue
            imp = _implied(odds)
            if imp is None:
                continue
            out[gi]["cands"].append({
                "side": side, "prob": prob, "odds": float(odds), "edge": prob - imp,
                "ev": expected_value(prob, odds), "line": float(q["total_line"]),
                "inning": inning, "snapshot_at": str(q["snapshot_at"]),
                "runs_moved": runs_moved})
    pickle.dump({"artifact_version": art["version"], "season": season, "games": out},
                open(cache, "wb"))
    return out


def fresh_only(games: list[dict]) -> list[dict]:
    return [{**g, "cands": [c for c in g["cands"] if c["runs_moved"] == 0]} for g in games]


def calibration(games: list[dict], title: str) -> None:
    """Every priced candidate side, bucketed by claimed prob: does it deliver?"""
    bands = defaultdict(list)
    for g in games:
        for c in g["cands"]:
            res, _ = _grade(c, g["game"])
            if res == "PUSH":
                continue
            bands[min(int(c["prob"] * 20) / 20, 0.95)].append(res == "WIN")
    print(f"\n{title}")
    print("  claimed   n      delivered")
    for b in sorted(bands):
        v = bands[b]
        if len(v) < 50:
            continue
        print(f"  {b:.2f}-{b + 0.05:.2f} {len(v):>8} {np.mean(v):>8.1%}")


def grid(games: list[dict], title: str) -> None:
    print(f"\n{title}")
    print("SHIPPED CUT prob 0.72 / edge 0.14 / ev 0.32")
    r = sweep.cell(games, 0.72, 0.14, 0.32)
    for k in ("all", "early", "late"):
        print(f"  {k:5s} {sweep.summarise(r[k])}")
    probs = [0.70, 0.72, 0.74, 0.76, 0.78, 0.80]
    edges = [0.14, 0.16, 0.18, 0.20]
    print("--- prob x edge at ev 0.32 (bets / units / delivers) ---")
    print("prob/edge " + "".join(f"{e:>26.2f}" for e in edges))
    for p in probs:
        print(f"  {p:.2f}    " + "".join(sweep.short(sweep.cell(games, p, e, 0.32)["all"])
                                         for e in edges))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--split", default=SPLIT)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()
    sweep.SPLIT = args.split
    cache = Path(tempfile.gettempdir()) / f"inplay_history_cache_{args.season}.pkl"
    if args.rebuild or not cache.exists():
        games = build_cache(args.season, cache)
    else:
        d = pickle.load(open(cache, "rb"))
        games = d["games"]
        print(f"[cache] artifact {d['artifact_version']}, {len(games)} games")

    n_q = sum(g["n_quotes"] for g in games)
    n_p = sum(g["n_priced"] for g in games)
    n_c = sum(len(g["cands"]) for g in games)
    n_fresh = sum(1 for g in games for c in g["cands"] if c["runs_moved"] == 0)
    n_unknown = sum(1 for g in games for c in g["cands"] if c["runs_moved"] is None)
    slates = len({g["game"]["game_date"] for g in games})
    print(f"\n{len(games)} games / {slates} slates; {n_q} quotes, {n_p} aligned to a live "
          f"state, {n_c} candidate sides ({n_fresh} fresh, {n_unknown} no last_update); "
          f"split at {args.split}")

    grid(games, "=== ALL QUOTES (as the live loop pairs today) ===")
    grid(fresh_only(games), "=== FRESH QUOTES ONLY (score unchanged since DK's last_update) ===")

    print("\n=== THE 0.20 CAP, shipped cut ===")
    for label, gs in (("all", games), ("fresh", fresh_only(games))):
        for cap in (0.20, 9.9):
            sweep.LIVE_MAX_EDGE_CAP = cap
            r = sweep.cell(gs, 0.72, 0.14, 0.32)["all"]
            print(f"  {label:5s} cap {cap:<4} {sweep.summarise(r)}")
    sweep.LIVE_MAX_EDGE_CAP = LIVE_MAX_EDGE_CAP

    calibration(games, "=== CALIBRATION, every candidate side, all quotes ===")
    calibration(fresh_only(games), "=== CALIBRATION, fresh quotes only ===")

    print("\n=== PER SLATE at the shipped cut (fresh) ===")
    r = sweep.cell(fresh_only(games), 0.72, 0.14, 0.32)["all"]
    print(f"  {len(r)} bets over {slates} slates = {len(r) / slates:.2f} per slate")


if __name__ == "__main__":
    main()
