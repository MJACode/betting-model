"""The NCAAF live lanes against a season of bought DraftKings in-play snapshots.

THE INSTRUMENT. The two NCAAF live lanes were paused on 2026-09-11 with a
forward record of 55 settled totals bets (28-27, -2.99u, claiming 67.5% and
winning 50.9%) and six moneyline bets. That is a slate, not a record, and no
cut on it is evidenced. This runs the PRODUCTION pricing path
(ncaaf_live.serve.LiveEngine.candidates + LiveEngine._decide) over every stored
DK in-play snapshot of a season -- 2025 is out of sample for the active
artifact (Stage 1 trained through 2024, 2025 the calibration holdout) -- and
reports every cut on a prob x EV grid, the production cut first.

HOW A QUOTE GETS A STATE. The states parquet (ncaaf_live.backtest.build_states)
carries one PRE-play state per play with the play's CFBD wallclock. A snapshot
served at T is paired with the state on the field at T: the pre-play state of
the first play whose wallclock is AFTER T. No later play means the game was
over (or the feed had stopped) and the quote is not priced.

TWO GRIDS, NOT ONE. Every DK market carries its own `last_update`; when the
score moved between that update and the snapshot, the quote is stale and the
"edge" is the score itself, priced twice. Every candidate carries
`points_since_update` (score at served minus score at last_update, same
alignment), and every table is printed for ALL quotes and for FRESH quotes
only (points_since_update == 0). Fresh-only is what production can take -- the
loop already declines a quote stamped before the last score -- and the honest
one to read a cut off. `--max-age-sec` additionally drops quotes older than the
loop's own age bound.

FIRST-SIGNAL LOCK. Production locks a lane at its first BET (CLAUDE.md 1c), so
each (game, lane) contributes ONE bet per cell: the earliest snapshot that
crosses. Bets are graded on the parquet's platform finals, OT included, which
is what the markets settle on.

    python -m scripts.ncaaf_inplay_history_backtest --season 2025
    python -m scripts.ncaaf_inplay_history_backtest --season 2025 --rebuild
    python -m scripts.ncaaf_inplay_history_backtest --season 2025 --max-age-sec 90

Needs: the states parquet (ncaaf_live/data/artifacts/states_all.parquet --
build it with ncaaf_live.backtest.pull_pbp + build_states, which need
CFBD_API_KEY), the engine artifacts, and the snapshots
(data/ingestors/ncaaf_inplay_history.py). The candidate cache lives in the
temp dir, like the MLB harness's.
"""
from __future__ import annotations

import argparse
import pickle
import sys
import tempfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from tracking.live_calibration import expected_value, wilson  # noqa: E402

LANES = ("ncaaf_live_total", "ncaaf_live_win_prob")
SOURCE_PREFIX = "historical_inplay|"
PROB_GRID = (0.55, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70, 0.72, 0.75, 0.80)
EV_GRID = (0.00, 0.10, 0.14, 0.18, 0.22, 0.26, 0.30, 0.34)
# Mid-season split for the two-half test (CLAUDE.md 7: a time split kills most
# false positives). Mid-October halves a late-August -> early-December slate.
SPLIT_MONTH_DAY = (10, 15)


# ── pure pieces (tested on synthetic data) ───────────────────────────────────

def _ts(s) -> datetime:
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(s).replace("Z", "+00:00")).astimezone(timezone.utc)


def state_index_at(wall_ts: np.ndarray, at: datetime) -> int | None:
    """Index of the state on the field at `at`: the PRE-play state of the
    first play whose wallclock is after `at`. None when no play follows (the
    game had ended, or the feed stopped). `wall_ts` is sorted, UTC."""
    if len(wall_ts) == 0:
        return None
    t = np.datetime64(at.astimezone(timezone.utc).replace(tzinfo=None), "ns")
    i = int(np.searchsorted(wall_ts, t, side="right"))
    return None if i >= len(wall_ts) else i


def odds_from_rows(rows: list[dict]) -> tuple[dict, dict]:
    """The {h2h:{home,away}, total:{line,over,under}} shape serve.price()
    reads, and each market's last_update, from `odds` rows of ONE snapshot."""
    odds: dict = {}
    lu: dict = {}
    for r in rows:
        src = r.get("source") or ""
        stamp = src.split("|lu=", 1)[1].split("|", 1)[0] if "|lu=" in src else None
        if r["market"] == "totals" and r.get("total_line") is not None:
            odds["total"] = {"line": float(r["total_line"]),
                             "over": r.get("over_price"), "under": r.get("under_price")}
            lu["total"] = stamp
        elif r["market"] == "h2h" and r.get("home_price") is not None \
                and r.get("away_price") is not None:
            odds["h2h"] = {"home": float(r["home_price"]), "away": float(r["away_price"])}
            lu["h2h"] = stamp
    return odds, lu


def grade(cand: dict, final_home: float, final_away: float) -> tuple[str, float]:
    """Result and flat units for one candidate against the platform final."""
    a = float(cand["dk_odds"])
    win_units = a / 100.0 if a > 0 else 100.0 / abs(a)
    if cand["model_id"] == "ncaaf_live_total":
        total = final_home + final_away
        line = float(cand["scored_line"])
        if total == line:
            return "PUSH", 0.0
        won = total > line if cand["pick_side"] == "over" else total < line
    else:
        if final_home == final_away:
            return "PUSH", 0.0
        won = (final_home > final_away) == (cand["pick_side"] == "home")
    return ("WIN", win_units) if won else ("LOSS", -1.0)


def decide(cand: dict, min_prob: float, min_edge: float, min_ev: float | None,
           cap: float) -> bool:
    """The production BET rule with the thresholds as parameters. Re-states
    LiveEngine._decide's arithmetic; tests pin that the two agree."""
    p, edge = cand["model_probability"], cand["edge"]
    if abs(edge) > cap:
        return False
    if p < min_prob or edge < min_edge:
        return False
    if min_ev is not None:
        ev = expected_value(p, cand["dk_odds"])
        if ev is not None and ev < min_ev:
            return False
    return True


def first_signals(cands: list[dict], min_prob: float, min_edge: dict,
                  min_ev: float | None, cap: float,
                  fresh_only: bool = False, max_age_sec: float | None = None) -> list[dict]:
    """One bet per (game, lane): the earliest candidate that crosses the cut.
    Sorted by served time here rather than trusted -- the lock's whole meaning
    is "first", and a caller's order is not evidence of it."""
    taken: set = set()
    out = []
    for c in sorted(cands, key=lambda c: c["served"]):
        key = (c["game_id"], c["model_id"])
        if key in taken:
            continue
        if fresh_only and c["points_since_update"] != 0:
            continue
        if max_age_sec is not None and (c["age_sec"] is None or c["age_sec"] > max_age_sec):
            continue
        if decide(c, min_prob, min_edge[c["model_id"]], min_ev, cap):
            taken.add(key)
            out.append(c)
    return out


def summarise(bets: list[dict]) -> dict:
    n = len(bets)
    w = sum(1 for b in bets if b["result"] == "WIN")
    l = sum(1 for b in bets if b["result"] == "LOSS")
    units = sum(b["units"] for b in bets)
    graded = w + l
    ci = wilson(w, graded) if graded else None
    return {"n": n, "w": w, "l": l, "push": n - graded, "units": round(units, 2),
            "roi_pct": round(100.0 * units / n, 1) if n else None,
            "win_pct": round(100.0 * w / graded, 1) if graded else None,
            "ci_low": round(100 * ci[0], 1) if ci else None,
            "ci_high": round(100 * ci[1], 1) if ci else None,
            "mean_p": round(float(np.mean([b["model_probability"] for b in bets])), 3) if n else None}


def split_halves(bets: list[dict], season: int) -> tuple[list[dict], list[dict]]:
    cut = datetime(season, *SPLIT_MONTH_DAY, tzinfo=timezone.utc)
    return ([b for b in bets if b["served"] < cut], [b for b in bets if b["served"] >= cut])


# ── the data ─────────────────────────────────────────────────────────────────

def load_snapshots(conn, season: int) -> dict[str, list[tuple[datetime, list[dict]]]]:
    """game_id -> [(served, rows)] in served order, bought snapshots only."""
    rows = conn.execute("""
        SELECT o.game_id, o.snapshot_at, o.market, o.total_line, o.over_price,
               o.under_price, o.home_price, o.away_price, o.source
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = 'NCAAF' AND g.season = %s AND o.bookmaker = 'draftkings'
          AND o.snapshot_type = 'in_play' AND o.source LIKE %s
        ORDER BY o.game_id, o.snapshot_at
    """, (season, SOURCE_PREFIX + "%")).fetchall()
    cols = ["game_id", "snapshot_at", "market", "total_line", "over_price",
            "under_price", "home_price", "away_price", "source"]
    by_game: dict = defaultdict(lambda: defaultdict(list))
    for r in rows:
        d = dict(zip(cols, r))
        by_game[d["game_id"]][d["snapshot_at"]].append(d)
    return {g: [(_ts(s), rs) for s, rs in sorted(snaps.items())]
            for g, snaps in by_game.items()}


def build_candidates(engine, states: pd.DataFrame, snaps: dict) -> list[dict]:
    """Every priceable proposition at every snapshot, no cut applied."""
    out = []
    games = states.groupby("game_id", sort=False)
    priced = skipped = 0
    for game_id, snap_list in snaps.items():
        if game_id not in games.groups:
            skipped += 1
            continue
        g = games.get_group(game_id).sort_values("wall_ts", kind="mergesort")
        g = g[g["wall_ts"].notna()]
        if g.empty:
            skipped += 1
            continue
        wall = g["wall_ts"].dt.tz_convert("UTC").dt.tz_localize(None).to_numpy(dtype="datetime64[ns]")
        final_h = float(g["final_home"].iloc[0])
        final_a = float(g["final_away"].iloc[0])
        for served, rows in snap_list:
            i = state_index_at(wall, served)
            if i is None:
                continue
            row = g.iloc[[i]]
            period = int(row["period"].iloc[0])
            hs, as_ = int(row["home_score"].iloc[0]), int(row["away_score"].iloc[0])
            odds, lu = odds_from_rows(rows)
            for c in engine.candidates(row, period, hs, as_, odds):
                mkt = "total" if c["model_id"] == "ncaaf_live_total" else "h2h"
                stamp = lu.get(mkt)
                age = None
                since = 0
                if stamp and stamp not in ("None", ""):
                    lu_t = _ts(stamp)
                    age = (served - lu_t).total_seconds()
                    j = state_index_at(wall, lu_t)
                    if j is not None:
                        since = (hs + as_) - int(g["home_score"].iloc[j] + g["away_score"].iloc[j])
                c.update({"game_id": game_id, "served": served, "period": period,
                          "seconds_remaining": float(row["seconds_remaining"].iloc[0]),
                          "age_sec": age, "points_since_update": since,
                          "final_home": final_h, "final_away": final_a})
                c["result"], c["units"] = grade(c, final_h, final_a)
                out.append(c)
            priced += 1
    print(f"candidates: {len(out):,} from {priced:,} priced snapshots; "
          f"{skipped} games in odds with no states")
    out.sort(key=lambda c: c["served"])
    return out


# ── the report ───────────────────────────────────────────────────────────────

def _fmt(s: dict) -> str:
    if not s["n"]:
        return "      0 bets"
    ci = f"[{s['ci_low']}, {s['ci_high']}]" if s["ci_low"] is not None else "-"
    return (f"{s['n']:5d} bets {s['w']:4d}-{s['l']:<4d} {s['units']:+8.2f}u "
            f"{s['roi_pct']:+6.1f}%  win {s['win_pct']:5.1f}% {ci:<16} p={s['mean_p']}")


def report(cands: list[dict], season: int, max_age: float | None) -> None:
    from ncaaf_live.serve import MAX_EDGE_CAP as cap   # the loop's own cap
    edge_floor = {m: config.ACTION_THRESHOLDS[m]["min_edge"] for m in LANES}
    prod = {m: (config.ACTION_THRESHOLDS[m]["min_prob"], config.MODEL_MIN_EV.get(m))
            for m in LANES}
    for lane in LANES:
        lane_c = [c for c in cands if c["model_id"] == lane]
        print(f"\n=== {lane}: {len(lane_c):,} candidates, edge floor {edge_floor[lane]}, "
              f"cap {cap} ===")
        for fresh in (False, True):
            tag = "FRESH quotes only (points_since_update == 0)" if fresh else "ALL quotes"
            if max_age is not None:
                tag += f", age <= {max_age:.0f}s"
            print(f"\n-- {tag} --")
            p0, ev0 = prod[lane]
            bets = first_signals(lane_c, p0, edge_floor, ev0, cap, fresh, max_age)
            h1, h2 = split_halves(bets, season)
            print(f"production cut prob>={p0} ev>={ev0}: {_fmt(summarise(bets))}")
            print(f"    first half : {_fmt(summarise(h1))}")
            print(f"    second half: {_fmt(summarise(h2))}")
            by_period = defaultdict(list)
            for b in bets:
                by_period[b["period"]].append(b)
            for per in sorted(by_period):
                print(f"    period {per}   : {_fmt(summarise(by_period[per]))}")
            by_side = defaultdict(list)
            for b in bets:
                by_side[b["pick_side"]].append(b)
            for side in sorted(by_side):
                print(f"    {side:<11}: {_fmt(summarise(by_side[side]))}")
            print(f"\n  grid (prob x EV), bets / units / ROI / [CI]:")
            print("  prob  " + "".join(f"{('ev>=' + str(ev)):>22}" for ev in EV_GRID))
            for pmin in PROB_GRID:
                cells = []
                for ev in EV_GRID:
                    s = summarise(first_signals(lane_c, pmin, edge_floor, ev, cap, fresh, max_age))
                    if not s["n"]:
                        cells.append(f"{'-':>22}")
                    else:
                        cells.append(f"{s['n']:5d} {s['units']:+7.1f}u {s['roi_pct']:+6.1f}%".rjust(22))
                print(f"  {pmin:<5} " + "".join(cells))
        # calibration by claimed-probability band, all candidates, one per
        # (game, lane, band) -- the honest read of "claims X, wins Y"
        print("\n  calibration (first fresh candidate per game in each claimed band):")
        bands = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 0.75),
                 (0.75, 0.80), (0.80, 0.90), (0.90, 1.01)]
        for lo, hi in bands:
            seen: set = set()
            rows = []
            for c in lane_c:
                if c["points_since_update"] != 0 or not (lo <= c["model_probability"] < hi):
                    continue
                if c["game_id"] in seen or abs(c["edge"]) > cap:
                    continue
                seen.add(c["game_id"])
                rows.append(c)
            s = summarise(rows)
            if s["n"]:
                print(f"    [{lo:.2f}, {hi:.2f}): {_fmt(s)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--rebuild", action="store_true")
    ap.add_argument("--states", default=None,
                    help="states parquet (default: the season's own build, "
                         "then the full corpus)")
    ap.add_argument("--max-age-sec", type=float, default=None)
    args = ap.parse_args()

    cache = Path(tempfile.gettempdir()) / f"ncaaf_inplay_candidates_{args.season}.pkl"
    if cache.exists() and not args.rebuild:
        cands = pickle.loads(cache.read_bytes())
        print(f"loaded {len(cands):,} cached candidates from {cache}")
    else:
        import pandas as _pd
        from data.db import get_connection
        from ncaaf_live.backtest.build_states import out_path
        from ncaaf_live.backtest.train_engine import STATES_PATH, load_states
        from ncaaf_live.serve import LiveEngine
        scoped = _pd.io.common.stringify_path(
            args.states or out_path([args.season]))
        if Path(scoped).exists():
            states = _pd.read_parquet(scoped)
            print(f"states: {scoped}")
        elif STATES_PATH.exists():
            states = load_states()
            print(f"states: {STATES_PATH}")
        else:
            raise SystemExit(
                f"no states parquet at {scoped} or {STATES_PATH} -- run "
                f"`python -m ncaaf_live.backtest.build_states --seasons "
                f"{args.season}` (plays come from ncaaf_plays, no CFBD key "
                f"needed)")
        states = states[states["season"] == args.season]
        if states.empty:
            raise SystemExit(f"no states for {args.season} -- run ncaaf_live.backtest.build_states")
        conn = get_connection()
        try:
            snaps = load_snapshots(conn, args.season)
        finally:
            conn.close()
        if not snaps:
            raise SystemExit(f"no bought in-play snapshots for {args.season} -- "
                             "run data.ingestors.ncaaf_inplay_history")
        print(f"{len(snaps):,} games with snapshots, "
              f"{sum(len(v) for v in snaps.values()):,} snapshots")
        cands = build_candidates(LiveEngine(), states, snaps)
        cache.write_bytes(pickle.dumps(cands))
    report(cands, args.season, args.max_age_sec)


if __name__ == "__main__":
    main()
