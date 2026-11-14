"""Build the EuroLeague halftime spread artifact, and show it reproduces the
research bet for bet first.

    python -m scripts.build_euroleague_live_ht_artifact            # replay and compare; write nothing
    python -m scripts.build_euroleague_live_ht_artifact --write    # ... then write models/saved/euroleague_live_ht_2027.json

THE REPLAY. Every walk-forward season of the research (2022-23 to 2026-27 to
2026-11-12) is decided again by models/euroleague_live_ht.read_break, the code
the live loop runs: the margin model fitted on every earlier season from
2021-22 (models.euroleague_live_ht.fit, on the score every 30 seconds of each
qualifying game), Pinnacle's last coherent pre-game spread and total as the
pre-game number (models.euroleague_live_ht.prior_from_pinnacle), each
in-play snapshot inside the break read in order, the first holding an
eligible quote deciding the game, bet at EV >= 0.05. Then the research's own
code (scripts/euroleague_research/r4_lib.py, variant V2) is run on the same
cache and the two bet lists are compared on (game, book, side, line, price,
read). Any difference is printed; --write refuses to write while one exists.

THE ARTIFACT is the 2026-27 fold: the margin model fitted on 2021-22 to
2025-26, the one the research graded 2026-27 to date on. The loop refuses an
artifact for another season.

Reads only the local research cache (EUROLEAGUE_RESEARCH_DIR, default
~/euroleague_research; cache/ holds parquet copies of Supabase). No database,
no API, no paid call.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models import euroleague_live_ht as M  # noqa: E402

CACHE = Path(os.environ.get("EUROLEAGUE_RESEARCH_DIR") or Path.home() / "euroleague_research") / "cache"
WF_SEASONS = (2023, 2024, 2025, 2026, 2027)
FIRST_TRAIN = 2022
BREAK_OK = (10.0, 25.0)
CUTS = (0.02, 0.03, 0.05, 0.08, 0.12)
SEASON_NAME = {2022: "2021-22", 2023: "2022-23", 2024: "2023-24", 2025: "2024-25", 2026: "2025-26",
               2027: "2026-27 to 11-12"}
# What the research reported for this rule (docs/euroleague_halftime.md, section 3b, "B spread,
# V2 Pinnacle prior, cut 0.05"), on its own stake.
RESEARCH = {"bets": 364, "units": 45.34, "by_season": {2023: 107, 2024: 61, 2025: 58, 2026: 107, 2027: 31}}


# ── the cache ────────────────────────────────────────────────────────────────

def load(cache: Path) -> dict:
    g = pd.read_parquet(cache / "games.parquet")
    g = g[g["played"]].copy()
    g["tip"] = pd.to_datetime(g["commence_time"], utc=True)
    g["margin"] = g["home_score"] - g["away_score"]
    h = pd.read_parquet(cache / "halftime.parquet")
    g = g.merge(h, on="game_id", how="inner")
    sh = pd.read_parquet(cache / "shots.parquet", columns=["game_id", "num_anot", "minute", "console",
                                                            "points_home", "points_away", "shot_utc"])
    g = g.merge(sh.groupby("game_id")["shot_utc"].min().rename("first_shot").reset_index(), on="game_id",
                how="left")
    g["break_ok"] = g["break_minutes"].between(*BREAK_OK)
    fq = pd.read_parquet(cache / "fullgame_quotes.parquet")
    iq = pd.read_parquet(cache / "inplay_quotes.parquet")
    return {"games": g, "shots": sh, "fullgame": fq, "inplay": iq}


def pinnacle_priors(g: pd.DataFrame, fq: pd.DataFrame) -> pd.DataFrame:
    """(prior_m, prior_t) per game through models.euroleague_live_ht.prior_from_pinnacle,
    Pinnacle's rows stamped at or before min(tip, first shot), in stored order."""
    p = fq[(fq["bookmaker"] == "pinnacle") & fq["market"].isin(["spreads", "totals"])]
    p = p.sort_values(["game_id", "snapshot_at"], kind="mergesort")
    bound = g.set_index("game_id")[["tip", "first_shot"]]
    out = []
    for gid, x in p.groupby("game_id", sort=False):
        if gid not in bound.index:
            continue
        tip, fs = bound.loc[gid, "tip"], bound.loc[gid, "first_shot"]
        before = tip if pd.isna(fs) else min(tip, fs)
        rows = list(zip(x["market"], x["snapshot_at"], x["spread_home"], x["total_line"], x["home_price"],
                        x["away_price"], x["over_price"], x["under_price"]))
        pr = M.prior_from_pinnacle(rows, before=before)
        if pr is not None:
            out.append((gid, pr[0], pr[1]))
    return pd.DataFrame(out, columns=["game_id", "prior_m", "prior_t"])


def qualifying(data: dict) -> pd.DataFrame:
    g = data["games"].merge(pinnacle_priors(data["games"], data["fullgame"]), on="game_id", how="left")
    g["qual"] = g["break_ok"] & g["prior_m"].notna() & g["prior_t"].notna()
    return g


# ── the walk-forward models ──────────────────────────────────────────────────

def states(shots: pd.DataFrame) -> dict:
    return {gid: M.states_from_shots(x) for gid, x in shots.groupby("game_id", sort=False)}


def fold(g: pd.DataFrame, st: dict, seasons) -> tuple:
    parts = []
    for r in g[g["qual"] & g["season"].isin(list(seasons))].itertuples(index=False):
        s = st.get(r.game_id)
        if s is not None:
            parts.append(M.training_rows(s, r.prior_m, r.margin))
    tr = pd.concat(parts, ignore_index=True)
    return M.fit(tr), len(tr)


# ── the replay through read_break ────────────────────────────────────────────

def replay(g: pd.DataFrame, iq: pd.DataFrame, models: dict, cut: float = -np.inf) -> pd.DataFrame:
    """Every decided game (no cut unless given): the first read in the break
    holding an eligible quote, its best quote, through read_break."""
    q = iq[iq["market"] == "spreads"].rename(columns={"bookmaker": "book", "last_update": "stamp"})
    games = g[g["qual"] & g["season"].isin(list(models))].set_index("game_id")
    q = q[q["game_id"].isin(games.index)]
    out = []
    for gid, x in q.groupby("game_id", sort=False):
        r = games.loc[gid]
        half = M.Half(r["first_shot"], r["last_q2_shot"], int(r["ht_home"]), int(r["ht_away"]), r["first_q3_shot"])
        model = models[int(r["season"])]
        for ts, xr in x.sort_values("snapshot_ts", kind="mergesort").groupby("snapshot_ts", sort=True):
            rd = M.read_break(xr, ts, half, float(r["prior_m"]), model)
            if rd.status != "decided":
                continue
            b = rd.best
            out.append({"game_id": gid, "season": int(r["season"]), "game_date": r["game_date"], "read": ts,
                        "book": b["book"], "side": b["side"], "line": float(b["line"]), "price": float(b["price"]),
                        "ev": float(b["ev"]), "prob": float(b["prob"]), "margin": float(r["margin"]),
                        "ht_m": int(r["ht_home"]) - int(r["ht_away"]), "prior_m": float(r["prior_m"])})
            break
    d = pd.DataFrame(out)
    if not len(d):
        return d
    d = d[d["ev"] >= cut].copy()
    d["res"] = [M.covers(s, ln, m) for s, ln, m in zip(d["side"], d["line"], d["margin"])]
    ru = [M.research_units(s, ln, p, m) for s, ln, p, m in zip(d["side"], d["line"], d["price"], d["margin"])]
    pu = [M.units(s, ln, p, m) for s, ln, p, m in zip(d["side"], d["line"], d["price"], d["margin"])]
    d["units"], d["risk"] = [u for u, _ in ru], [k for _, k in ru]
    d["units_posted"], d["risk_posted"] = [u for u, _ in pu], [k for _, k in pu]
    return d.reset_index(drop=True)


def summary(d: pd.DataFrame, units="units", risk="risk") -> dict:
    if not len(d):
        return {"bets": 0, "W": 0, "L": 0, "P": 0, "units": 0.0, "return_pct": None}
    rk = float(d[risk].sum())
    return {"bets": int(len(d)), "W": int((d["res"] > 0).sum()), "L": int((d["res"] < 0).sum()),
            "P": int((d["res"] == 0).sum()), "units": round(float(d[units].sum()), 2),
            "return_pct": round(100 * float(d[units].sum()) / rk, 2) if rk > 0 else None}


# ── the research's own code, for the comparison ─────────────────────────────

def research_bets(cut: float) -> pd.DataFrame | None:
    here = ROOT / "scripts" / "euroleague_research"
    if not (here / "r4_lib.py").exists():
        return None
    sys.path.insert(0, str(here))
    import r4_lib as L  # noqa: E402
    P2 = L.priced_wf(prior=("pin_m", "pin_t"))
    b = L.grade(L.decide(P2[P2["market"] == "spreads"], cut))
    b = b[b["wf"]]
    return b.rename(columns={"bookmaker": "book", "snapshot_ts": "read"})[
        ["game_id", "season", "read", "book", "side", "line", "price", "ev", "units", "risk", "res"]]


def compare(mine: pd.DataFrame, theirs: pd.DataFrame) -> dict:
    key = ["game_id", "book", "side", "line", "price", "read"]

    def keyed(d):
        k = d[key].copy()
        k["read"] = pd.to_datetime(k["read"], utc=True)
        k["line"] = k["line"].astype(float).round(3)
        k["price"] = k["price"].astype(float).round(3)
        return set(map(tuple, k.to_numpy().tolist()))
    a, b = keyed(mine), keyed(theirs)
    return {"same": len(a & b), "only_build": sorted(a - b, key=str)[:20], "only_research": sorted(b - a, key=str)[:20],
            "n_only_build": len(a - b), "n_only_research": len(b - a)}


def snapshot_census(iq: pd.DataFrame, g: pd.DataFrame) -> dict:
    s = iq.drop_duplicates(["snapshot_ts", "game_id"]).merge(g[["game_id", "season"]], on="game_id")
    sec = (s["snapshot_ts"].dt.minute % 5) * 60 + s["snapshot_ts"].dt.second
    return {int(k): float(v) for k, v in sec.groupby(s["season"]).median().items()}


def price_range(d: pd.DataFrame) -> dict:
    p = d["price"].to_numpy(float)
    return {"median": float(np.median(p)), "shortest": float(p.min()), "longest": float(p.max()),
            "share_shorter_than_-300": float(np.mean(p < -300)), "share_shorter_than_-500": float(np.mean(p < -500))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", type=Path, default=CACHE)
    ap.add_argument("--write", action="store_true", help="write the artifact (refused while the replay differs)")
    ap.add_argument("--no-compare", action="store_true", help="skip running the research's own code")
    a = ap.parse_args(argv)
    data = load(a.cache)
    g = qualifying(data)
    st = states(data["shots"])
    # the research reads the half-time score from the quarter scores; the loop reads it off the shot
    # chart (the running maximum over the first 20 minutes, data.ingestors.euroleague_live_feed)
    q2 = data["shots"][data["shots"]["minute"] <= 20].groupby("game_id")[["points_home", "points_away"]].max()
    ht = g.join(q2, on="game_id")
    ht_ok = int(((ht["points_home"] == ht["ht_home"]) & (ht["points_away"] == ht["ht_away"])).sum())
    print(f"games played with a halftime row: {len(g)}; qualifying (break 10-25 min, Pinnacle's spread and total): "
          f"{int(g['qual'].sum())}; half-time score equal to the shot chart's running maximum: {ht_ok}")
    models, n_states = {}, {}
    for s in WF_SEASONS:
        models[s], n_states[s] = fold(g, st, range(FIRST_TRAIN, s))
        mm = models[s]
        print(f"fold {SEASON_NAME[s]}: fitted on {SEASON_NAME[FIRST_TRAIN]}..{SEASON_NAME[s - 1]}, "
              f"{n_states[s]} states; at the half: share of the prior still to come {0.5 * mm.b[0]:.3f}, "
              f"share of the surprise carried {0.5 * mm.b[1] + 0.25 * mm.b[2]:.3f}, "
              f"sd {float(np.sqrt(mm.s[0] + 0.5 * mm.s[1] + 0.25 * mm.s[2])):.2f}")
    every = replay(g, data["inplay"], models)
    bets = every[every["ev"] >= 0.05].reset_index(drop=True)
    head = summary(bets)
    print(f"\nREPLAY at EV >= 0.05: {head}  (the research: {RESEARCH['bets']} bets, {RESEARCH['units']:+.2f} units)")
    print(f"  on the posted stake (1u to win, risk capped at 3, every price): "
          f"{summary(bets, 'units_posted', 'risk_posted')}")
    by_season = {}
    for s in WF_SEASONS:
        x = bets[bets["season"] == s]
        by_season[s] = {**summary(x), "posted_units": round(float(x["units_posted"].sum()), 2)}
        print(f"  {SEASON_NAME[s]}: {by_season[s]}  (research {RESEARCH['by_season'][s]} bets)")
    grid = {c: summary(every[every["ev"] >= c]) for c in CUTS}
    for c, v in grid.items():
        print(f"  cut {c:.2f}: {v}")
    pr = price_range(bets)
    edge = (bets["prob"] - M.implied(bets["price"])).to_numpy(float)
    print(f"  prices: {pr}; decision edge (prob - implied) {edge.min():.3f} to {edge.max():.3f}")
    print(f"  in-play snapshot second past each five-minute mark, median by season: "
          f"{snapshot_census(data['inplay'], data['games'])}")
    diff = None
    if not a.no_compare:
        theirs = research_bets(0.05)
        if theirs is None:
            print("the research's code is not in this checkout: not compared")
        else:
            diff = compare(bets, theirs)
            r_units = float(theirs["units"].sum())
            print(f"\nCOMPARED with the research's own code (r4_lib V2): {len(theirs)} bets, {r_units:+.2f} units; "
                  f"identical {diff['same']}; only in this build {diff['n_only_build']}; only in the research "
                  f"{diff['n_only_research']}")
            for k in ("only_build", "only_research"):
                for t in diff[k]:
                    print(f"  {k}: {t}")
    if a.write:
        if diff is not None and (diff["n_only_build"] or diff["n_only_research"]):
            print("REFUSED: the replay differs from the research; nothing written")
            return 1
        live = models[2027]
        art = {
            "kind": M.ARTIFACT_KIND, "model_id": M.MODEL_ID, "season": M.SEASON,
            "version": f"{M.ARTIFACT_KIND}_{M.SEASON}_{datetime.now(timezone.utc):%Y%m%d}",
            "cut": 0.05, "margin": live.to_dict(),
            "fitted_on_seasons": list(range(FIRST_TRAIN, 2027)), "fitted_states": int(n_states[2027]),
            "prior": "pinnacle's last coherent pre-game spread and total, at or before min(tip, first shot)",
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "replay": {"cut_0.05": head, "posted_stake": summary(bets, "units_posted", "risk_posted"),
                       "by_season": {str(k): v for k, v in by_season.items()},
                       "cut_grid": {f"{k:.2f}": v for k, v in grid.items()}, "prices": pr,
                       "decision_edge_max": round(float(edge.max()), 4),
                       "matches_research": None if diff is None else (diff["n_only_build"] == 0
                                                                      and diff["n_only_research"] == 0)},
        }
        out = ROOT / M.ARTIFACT_PATH
        out.write_text(json.dumps(art, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
