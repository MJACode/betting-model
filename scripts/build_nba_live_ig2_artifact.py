"""Build the live NBA in-play model's artifact (models/nba_live_ig2.py) and
prove the serving code reproduces the graded rule.

    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.build_nba_live_ig2_artifact --build
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.build_nba_live_ig2_artifact --parity-held
    NBA_RESEARCH_CACHE=<cache> PYTHONPATH=. python -m scripts.build_nba_live_ig2_artifact --parity-live27
    PYTHONPATH=. python -m scripts.build_nba_live_ig2_artifact --store ABSOLUTE_PATH      # after merge
    PYTHONPATH=. python -m scripts.build_nba_live_ig2_artifact --register ABSOLUTE_PATH   # after merge

--build writes models/saved/nba_live_ig2_2027.json:
  * the state model: IG-2's StateModel (scripts/nba_ingame_ig2) fit for season
    2027 on every season before it -- the stored training states the graded
    run built, 2020-21 .. 2024-25 (ig2_train_states.parquet) and 2025-26
    (ig2_train_states_2026.parquet), exactly the frame scripts/nba_s_ingame27.
    step1_train reads and the call G.models_by_season(train, G.FEATURES,
    seasons=(2027,)) its grade made;
  * the prior's distribution: the empirical (final margin - Pinnacle close)
    distribution on 2020-21 .. 2025-26 that L.live_prior builds
    (H.dist_by_season(H.close_resid(H.pinnacle_close(H.load(cache, 2021..2026))),
    [2027])), stored as its finished tables (ResidDist.state);
  * a golden grid: states and closes with the means, sds, win chances and
    priors the graded code computes from them, so a test can prove the
    loaded artifact reproduces them.

--parity-held replays the serving decision (models.nba_live_ig2.
decide_first_fetch) over the held quotes the graded run read (quotes_state.
parquet, its own state join) with IG-2's walk-forward models, and compares
the bets with the graded run's bets (ig2_bets/, EV >= 0.05) for the three
rules. It also counts the games where two of the three rules bet outcomes that
cannot both win.

--parity-live27 runs the serving pipeline (fetch_quotes, prepare, eligible_for,
decide) over the 2026-27 search's pulled live rows twice: with every play of
each game (it must equal the search's own decisions and bets), and with each
fetch seeing only the plays logged up to its served time plus the loop's wait
to its second ESPN read, 230 s (what the live loop sees), at the loop's own
fetch times (each hour minus 264 s), and reports every decision the second
view moves. ESPN's publication lag is not in the archive, so the loop's
fail-closed skip (a play logged before the fetch that appears only on the
second read) cannot be replayed here; it was measured live instead
(docs/sports/nba.md, "In play").

Inputs are read-only caches of Supabase rows (CLAUDE.md section 1b): the
research cache (NBA_RESEARCH_CACHE), the third search's folder
(%TEMP%/nba_game_edge/ingame) and the 2026-27 search's pull
(%TEMP%/nba_s/ingame27). --store and --register write production and run only
after the merge, deliberately, with an absolute path.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import models.nba_live_ig2 as M  # noqa: E402

OUT = ROOT / M.ARTIFACT_PATH
CUT = 0.05                    # the three rules' graded cut
FLOOR = -200.0                # config.DEFAULT_MIN_ODDS, the graded floor
# The loop decides on ESPN's second read: PBP_WAIT_SEC (170) after the fetch,
# then PBP_RECHECK_SEC (60) more (models/nba_live_loop.py). The replay lets a
# fetch see every play logged by its served time plus those 230 s.
WAIT_S = 230.0


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _lab():
    return M._lab()


# ── build ───────────────────────────────────────────────────────────────────

GOLDEN_STATES = [
    # period, clock_s, h_pts, a_pts, mu_pre, h_tf, a_tf, h_top pf x3, a_top pf x3
    (1, 600.0, 4, 2, -3.5, 1, 0, (0, 0, 0), (1, 0, 0)),
    (1, 120.0, 20, 27, 6.0, 4, 5, (1, 2, 0), (0, 1, 1)),
    (2, 700.0, 30, 30, 0.0, 0, 0, (1, 1, 1), (2, 0, 1)),
    (2, 360.0, 48, 39, -8.5, 3, 5, (2, 3, 1), (1, 1, 2)),
    (2, 45.0, 55, 61, 2.5, 5, 6, (3, 1, 2), (2, 2, 0)),
    (3, 720.0, 60, 52, -1.5, 0, 0, (2, 2, 2), (3, 1, 1)),
    (3, 431.0, 71, 70, 11.0, 2, 4, (4, 2, 1), (1, 3, 2)),
    (3, 18.0, 80, 91, -4.0, 6, 3, (3, 4, 4), (2, 5, 1)),
]
GOLDEN_SPREADS = [-7.5, -3.0, 0.0, 2.5, 6.0, 11.5]
GOLDEN_CLOSES = [(-7.5, 0.52), (-3.0, 0.49), (1.5, 0.50), (4.5, 0.47), (12.0, 0.51)]


def golden_frame(states=GOLDEN_STATES) -> pd.DataFrame:
    rows = []
    for per, clk, hp, ap, mu, htf, atf, ht, at in states:
        r = {"period": per, "clock_s": clk, "h_pts": hp, "a_pts": ap, "mu_pre": mu,
             "h_tf_period": htf, "a_tf_period": atf,
             "secs_left": clk + 720 * (4 - per), "season": M.SEASON}
        for k in (1, 2, 3):
            r[f"h_top{k}_pf"], r[f"a_top{k}_pf"] = ht[k - 1], at[k - 1]
        rows.append(r)
    return pd.DataFrame(rows)


def golden(model, dist) -> dict:
    G, H, _D, _L = _lab()
    f = G.features(golden_frame())
    mean, sd = model.predict(f)
    ph = G.p_home_from(mean, sd)
    sp = []
    for i in range(len(f)):
        for line in GOLDEN_SPREADS:
            for side in ("home", "away"):
                w, p = H.side_probs(np.array(["spreads"]), np.array([side]), np.array([line]),
                                    mu=np.array([mean[i]]), sigma=np.array([sd[i]]))
                sp.append({"state": i, "line": line, "side": side, "p_win": float(w[0]), "p_push": float(p[0])})
    pri = H.solve_any(G.threshold("spreads", np.array([c[0] for c in GOLDEN_CLOSES], float)),
                      np.array([c[1] for c in GOLDEN_CLOSES], float),
                      np.array([dist] * len(GOLDEN_CLOSES), dtype=object))
    return {"states": [list(map(lambda x: list(x) if isinstance(x, tuple) else x, s)) for s in GOLDEN_STATES],
            "mean": [float(x) for x in mean], "sd": [float(x) for x in sd], "p_home": [float(x) for x in ph],
            "spreads": sp,
            "closes": [list(c) for c in GOLDEN_CLOSES], "prior_mu": [float(x) for x in pri]}


def build(out: Path = OUT) -> dict:
    G, H, D, L = _lab()
    t0 = time.time()
    train = L.step1_train()
    models = G.models_by_season(train, G.FEATURES, seasons=(M.SEASON,))
    m = models[M.SEASON]
    hist = H.load(H.CACHE, seasons=L.HELD_SEASONS)
    close_h = H.pinnacle_close(hist)
    resid = H.close_resid(close_h, hist.games)
    dist = H.dist_by_season(resid, [M.SEASON])[(M.SEASON, "spreads")]
    per_season = {str(int(s)): int(n) for s, n in train.groupby("season").size().items()}
    built = datetime.now(timezone.utc)
    art = {
        "kind": M.ARTIFACT_KIND,
        "model_ids": list(M.MODEL_IDS),
        "version": f"{M.SEASON}-{built.strftime('%Y%m%d')}",
        "identity": {
            "builder": "scripts/build_nba_live_ig2_artifact.py",
            "built_at": built.isoformat(),
            "evidence": "docs/nba_models_2026.md section 7.3 (IG-2), docs/nba_search_ingame27.md",
            "inputs": {
                "train_states_2021_2025": {"path": str(L.TRAIN_HELD), "sha256": _sha(L.TRAIN_HELD)},
                "train_states_2026": {"path": str(L.TRAIN_2026), "sha256": _sha(L.TRAIN_2026)},
                "research_cache": str(H.CACHE),
            },
        },
        "rules": [{"model_id": r.model_id, "phase": r.phase, "market": r.market,
                   "graded_cut": CUT, "graded_floor": FLOOR} for r in M.RULES],
        # graded with the same model, not live, never registered (models/nba_live_ig2.HELD_OUT_RULES)
        "held_out_rules": [{"model_id": r.model_id, "phase": r.phase, "market": r.market,
                            "graded_cut": CUT, "graded_floor": FLOOR} for r in M.HELD_OUT_RULES],
        "state_model": {"cols": list(G.FEATURES), "beta": [float(x) for x in m.beta],
                        "s1": float(m.s1), "s0": float(m.s0), "season": int(m.S),
                        "n_train": int(m.n_train), "train_seasons": sorted(int(s) for s in train["season"].unique()),
                        "states_per_season": per_season},
        "prior_dist": dist.state(),
        "prior_dist_note": (f"(2027, spreads) residuals of the final home margin about Pinnacle's "
                            f"close, 2020-21 .. 2025-26: n={dist.n}, sd={dist.sd:.4f}"),
    }
    art["golden"] = golden(m, dist)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(art, indent=1), encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size:,} bytes) in {time.time() - t0:.0f}s")
    print(json.dumps({k: art["state_model"][k] for k in ("beta", "s1", "s0", "n_train", "states_per_season")},
                     indent=1))
    print(art["prior_dist_note"])
    return art


# ── parity on the graded seasons ───────────────────────────────────────────

GRADED_FILES = {M.SPREAD_Q12: "bets_IG-2_Q1-Q2_spreads_0002.parquet",
                M.ML_Q3: "bets_IG-2_Q3_h2h_0003.parquet",
                M.SPREAD_Q3: "bets_IG-2_Q3_spreads_0004.parquet"}


def parity_held() -> dict:
    G, H, D, L = _lab()
    t0 = time.time()
    train = pd.read_parquet(G.TRAIN_CACHE)
    models = G.models_by_season(train, G.FEATURES)          # 2021 in-sample, 2022..2026 walk-forward
    prior = pd.read_parquet(G.PRIOR_CACHE)
    q = G.load_table()
    el = G.eligible(q).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
    bets = M.decide_first_fetch(el, models, CUT, FLOOR)
    res = {}
    mine_all = []
    for r in M.GRADED_RULES:
        mine = bets[(bets["market"] == r.market) & (bets["phase_ig2"] == r.phase)].copy()
        mine_all.append(mine.assign(model_id=r.model_id))
        g = pd.read_parquet(G.BETS_DIR / GRADED_FILES[r.model_id])
        g = g[g["cut"].round(2) == CUT]
        key = ["game_id", "market", "side", "book", "price"]
        a = mine.assign(line=mine["line"].round(2))[key + ["line", "ev"]]
        b = g.assign(line=g["line"].round(2))[key + ["line", "ev", "season"]]
        j = a.merge(b, on=key + ["line"], how="outer", indicator=True, suffixes=("_mine", "_graded"))
        both = j["_merge"] == "both"
        res[r.model_id] = {"bets_mine": int(len(a)), "bets_graded": int(len(b)),
                           "same_bet": int(both.sum()),
                           "only_mine": int((j["_merge"] == "left_only").sum()),
                           "only_graded": int((j["_merge"] == "right_only").sum()),
                           "max_ev_gap": float((j.loc[both, "ev_mine"] - j.loc[both, "ev_graded"]).abs().max())
                           if both.any() else None,
                           "graded_seasons_2022_2026": int(b["season"].isin([2022, 2023, 2024, 2025, 2026]).sum())}
        print(r.model_id, res[r.model_id], flush=True)
    # two rules on one game that cannot both win (graded seasons only)
    allb = pd.concat(mine_all, ignore_index=True)
    allb = allb[allb["season"].isin([2022, 2023, 2024, 2025, 2026])]
    pairs = conflicts = 0
    for gid, grp in allb.groupby("game_id"):
        recs = grp.to_dict("records")
        for i in range(len(recs)):
            for k in range(i + 1, len(recs)):
                pairs += 1
                a = {"market": recs[i]["market"], "side": recs[i]["side"], "line": recs[i]["line"]}
                b = {"market": recs[k]["market"], "side": recs[k]["side"], "line": recs[k]["line"]}
                conflicts += int(M.cannot_both_win(a, b))
    res["two_rules_one_game"] = {"games_with_2plus_bets": int((allb.groupby("game_id").size() >= 2).sum()),
                                 "pairs": pairs, "pairs_cannot_both_win": conflicts,
                                 "bets_graded_seasons": int(len(allb))}
    print("two rules on one game:", res["two_rules_one_game"], f"({time.time() - t0:.0f}s)")
    # The live loop's own path: M.decide on one game's first eligible fetch per
    # rule (a one-game frame), against the graded bets.
    dec = G.decision_quotes(el)
    by_rule = {(r.phase, r.market): r for r in M.GRADED_RULES}
    rows = []
    for (gid, mk, ph), grp in dec.groupby(["game_id", "market", "phase_ig2"], sort=False):
        r = by_rule.get((ph, mk))
        if r is None:
            continue
        d = M.decide(grp, r, models, float(grp["mu_pre"].iloc[0]), CUT, FLOOR)
        if d is not None and d.bet:
            rows.append({**{k: d.pick[k] for k in ("game_id", "market", "side", "book", "price", "line", "ev")},
                         "model_id": r.model_id})
    live = pd.DataFrame(rows)
    for r in M.GRADED_RULES:
        g = pd.read_parquet(G.BETS_DIR / GRADED_FILES[r.model_id])
        g = g[g["cut"].round(2) == CUT]
        key = ["game_id", "side", "book", "price"]
        a = live[live["model_id"] == r.model_id][key]
        j = a.merge(g[key], on=key, how="outer", indicator=True)
        res[f"{r.model_id}_live_path"] = {"bets_live_path": int(len(a)), "bets_graded": int(len(g)),
                                          "same_bet": int((j["_merge"] == "both").sum()),
                                          "only_live_path": int((j["_merge"] == "left_only").sum()),
                                          "only_graded": int((j["_merge"] == "right_only").sum())}
        print(r.model_id, "live path (M.decide per game):", res[f"{r.model_id}_live_path"], flush=True)
    return res


# ── parity on the 2026-27 live rows ────────────────────────────────────────

def _live27_inputs():
    G, H, D, L = _lab()
    p = {k: pd.read_parquet(L.SCRATCH / v) for k, v in L.PULL_FILES.items()}
    games = L.games_frame(p["games"])
    games = games[games["game_id"].isin(set(p["pbp"]["game_id"]))].reset_index(drop=True)
    pbp = p["pbp"][p["pbp"]["game_id"].isin(set(games["game_id"]))].copy()
    box = p["box"][p["box"]["game_id"].isin(set(games["game_id"]))].copy()
    top = L.box_top_players(box, L.box_prior_minutes(L.all_box()))
    return p, games, pbp, box, top


def loop_fetches(fetches, offset_s: float = 264.0, within_min: float = 10.0) -> list:
    """The worker fetches the loop's fetch times stand for: for each hour minus
    `offset_s`, the first worker fetch at or after it within `within_min`
    minutes (the worker fetched about every 10 minutes; the loop fetches at the
    instant itself)."""
    F = pd.DatetimeIndex(sorted(fetches))
    if len(F) == 0:
        return []
    lo = F.min().floor("h")
    hi = F.max().ceil("h") + pd.Timedelta(hours=1)
    keep = []
    for h in pd.date_range(lo, hi, freq="h", tz="UTC"):
        inst = h - pd.Timedelta(seconds=offset_s)
        k = F.searchsorted(inst, side="left")
        if k < len(F) and F[k] - inst < pd.Timedelta(minutes=within_min):
            keep.append(F[k])
    return sorted(set(keep))


def parity_live27(wait_s: float = WAIT_S, every_fetch: bool = False) -> dict:
    G, H, D, L = _lab()
    t0 = time.time()
    p, games, pbp, _box, top = _live27_inputs()
    art = M.load_artifact(OUT)
    prior = L.live_prior(H.CACHE, L.load_live())
    pm = prior.set_index("game_id")["mu_pre"]
    lab = {r.model_id: pd.read_parquet(L.SCRATCH / "results" / "bets" / f)
           for r, f in zip(M.GRADED_RULES, ("bets_S1_IG2_live27_Q1-Q2_spreads_0002.parquet",
                                     "bets_S1_IG2_live27_Q3_h2h_0003.parquet",
                                     "bets_S1_IG2_live27_Q3_spreads_0004.parquet"))}
    for k in lab:
        lab[k] = lab[k][lab[k]["cut"].round(2) == CUT]
    odds = p["odds"][p["odds"]["source"].isna()].copy()      # the search's rows: the worker's live pulls
    plays_all, wild = L.live_plays(pbp)
    # (1) every play known: the search's own view
    q_all, _d, _n = M.fetch_quotes(odds, games)
    qt, notes = M.prepare(q_all, plays_all, pbp, top, games, final_games=set(games["game_id"]))
    full = {}
    for r in M.GRADED_RULES:
        el = M.eligible_for(qt, r).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
        b = M.decide_first_fetch(el, art.models, CUT, FLOOR)
        full[r.model_id] = b
    res = {"games": int(len(games)), "wild_wallclock_games": wild, "notes": {k: v for k, v in notes.items()
                                                                            if not isinstance(v, dict)}}
    key = ["game_id", "side", "book", "price"]
    for r in M.GRADED_RULES:
        a, b = full[r.model_id], lab[r.model_id]
        j = a[key].merge(b[key], on=key, how="outer", indicator=True)
        res[f"{r.model_id}_all_plays_vs_search"] = {
            "bets_mine": int(len(a)), "bets_search": int(len(b)),
            "same": int((j["_merge"] == "both").sum()), "only_mine": int((j["_merge"] == "left_only").sum()),
            "only_search": int((j["_merge"] == "right_only").sum())}
        print(r.model_id, "all plays:", res[f"{r.model_id}_all_plays_vs_search"], flush=True)
    # (2) the live view: each fetch the loop would make sees the plays logged
    # by its served time plus the wait. The loop fetches at each hour minus
    # 264 s (loop_fetches); --every-fetch replays every worker fetch instead.
    pbp = pbp.assign(_wc=pd.to_datetime(pbp["wallclock"], utc=True, format="mixed"))
    fetches = sorted(set(pd.to_datetime(odds["created_at"], utc=True, format="mixed")))
    if not every_fetch:
        fetches = loop_fetches(fetches)
    res["view"] = "every worker fetch" if every_fetch else "the loop's fetch times (hour minus 264 s)"
    res["fetches_in_view"] = len(fetches)
    # (1b) every play known, at the view's fetches only: what separates the
    # loop's cadence from the search's (1 vs 1b) and the plays the loop can
    # see from every play (1b vs 2).
    at_view = pd.to_datetime(odds["created_at"], utc=True, format="mixed").isin(set(fetches))
    q_v, _d, _n = M.fetch_quotes(odds[at_view], games)
    qt_v, _nv = M.prepare(q_v, plays_all, pbp.drop(columns="_wc"), top, games, final_games=set(games["game_id"]))
    full_v = {}
    for r in M.GRADED_RULES:
        el = M.eligible_for(qt_v, r).merge(prior[["game_id", "mu_pre"]], on="game_id", how="inner")
        full_v[r.model_id] = (el, M.decide_first_fetch(el, art.models, CUT, FLOOR))
    seen: set = set()
    decided: dict = {}
    n_fetch = 0
    for fa in fetches:
        rows = odds[pd.to_datetime(odds["created_at"], utc=True, format="mixed") == fa]
        q, _d, _n = M.fetch_quotes(rows, games, seen)
        if q.empty:
            continue
        gids = {g for g in set(q["game_id"])
                if any((g, r.model_id) not in decided for r in M.GRADED_RULES)}
        served = q["served_at"].max()
        known = pbp[pbp["game_id"].isin(gids) & (pbp["_wc"] <= served + pd.Timedelta(seconds=wait_s))]
        if known.empty:
            continue
        pl, _w = L.live_plays(known.drop(columns="_wc"))
        n_fetch += 1
        qt_f, _nn = M.prepare(q[q["game_id"].isin(gids)], pl, known.drop(columns="_wc"), top, games)
        for r in M.GRADED_RULES:
            el = M.eligible_for(qt_f, r)
            for gid, grp in el.groupby("game_id"):
                if (gid, r.model_id) in decided:
                    continue
                d = M.decide(grp, r, art.models, pm.get(gid), CUT, FLOOR)
                if d is not None:
                    decided[(gid, r.model_id)] = (fa, d)
    for r in M.GRADED_RULES:
        live_bets = pd.DataFrame([{**d.pick, "fetch_at": fa} for (gid, mid), (fa, d) in decided.items()
                                  if mid == r.model_id and d.bet])
        live_dec = {gid: fa for (gid, mid), (fa, d) in decided.items() if mid == r.model_id}
        el_full, a = full_v[r.model_id]
        first_full = G.decision_quotes(el_full).drop_duplicates("game_id").set_index("game_id")["fetch_at"] \
            if len(el_full) else pd.Series(dtype=object)
        same_fetch = sum(1 for g, fa in live_dec.items() if g in first_full.index and first_full[g] == fa)
        only_live = sorted(set(live_dec) - set(first_full.index))
        only_full = sorted(set(first_full.index) - set(live_dec))
        # the cadence alone: every play known, the view's fetches vs every fetch
        js = a[key].merge(full[r.model_id][key], on=key, how="outer", indicator=True)
        res[f"{r.model_id}_cadence_alone"] = {
            "decisions_view_fetches": int(len(first_full)),
            "bets_view_fetches": int(len(a)), "bets_every_fetch": int(len(full[r.model_id])),
            "same_bet": int((js["_merge"] == "both").sum())}
        bk = live_bets[key] if len(live_bets) else pd.DataFrame(columns=key)
        j = bk.merge(a[key], on=key, how="outer", indicator=True)
        jl = bk.merge(lab[r.model_id][key], on=key, how="outer", indicator=True)
        res[f"{r.model_id}_live_view_vs_search_bets"] = {
            "bets_live_view": int(len(bk)), "bets_search": int(len(lab[r.model_id])),
            "same_bet": int((jl["_merge"] == "both").sum()),
            "only_live_view": int((jl["_merge"] == "left_only").sum()),
            "only_search": int((jl["_merge"] == "right_only").sum())}
        res[f"{r.model_id}_live_view_vs_all_plays_same_fetches"] = {
            "decisions_live_view": len(live_dec), "decisions_all_plays": int(len(first_full)),
            "decided_at_same_fetch": int(same_fetch),
            "games_decided_only_live_view": only_live, "games_decided_only_all_plays": only_full,
            "bets_live_view": int(len(bk)), "bets_all_plays": int(len(a)),
            "same_bet": int((j["_merge"] == "both").sum()),
            "only_live_view": int((j["_merge"] == "left_only").sum()),
            "only_all_plays": int((j["_merge"] == "right_only").sum()),
            "games_bet_only_live_view": sorted(set(j.loc[j["_merge"] == "left_only", "game_id"])),
            "games_bet_only_all_plays": sorted(set(j.loc[j["_merge"] == "right_only", "game_id"]))}
        print(r.model_id, "live view vs every play at the same fetches:",
              res[f"{r.model_id}_live_view_vs_all_plays_same_fetches"],
              "| cadence alone:", res[f"{r.model_id}_cadence_alone"], flush=True)
    res["fetches_replayed"] = n_fetch
    res["games_left_out_by_rule_6_all_plays"] = sorted(L.jump_games(pbp.drop(columns="_wc")))
    res["games_left_out_by_rule_5_all_plays"] = sorted(notes.get("games_first_play_before_listed_tip") or {})
    print("rule 6 games (all plays):", res["games_left_out_by_rule_6_all_plays"],
          "rule 5 games:", res["games_left_out_by_rule_5_all_plays"])
    res["wait_s"] = wait_s
    print(f"done in {time.time() - t0:.0f}s")
    return res


# ── after the merge ────────────────────────────────────────────────────────

def store(path: Path) -> None:
    """Copy the artifact into Supabase's model_artifacts (the restore source
    load_artifact falls back to). A production write: run it after the merge."""
    from data.db import get_connection
    from models.trainer import _store_artifact
    art = json.loads(Path(path).read_text(encoding="utf-8"))
    conn = get_connection()
    try:
        # model_artifacts is keyed by the file's path, and the three rules share
        # one file, so it is stored once (under the first rule's id).
        _store_artifact(conn, art["model_ids"][0], art["version"], Path(path))
    finally:
        conn.close()


def register(path: Path) -> None:
    """One active model_registry row per model id, pointing at the committed
    artifact. A production write: run it after the merge and after --store."""
    from datetime import date
    from data.db import get_connection
    art = json.loads(Path(path).read_text(encoding="utf-8"))
    rel = M.ARTIFACT_PATH
    conn = get_connection()
    try:
        for r in art["rules"]:
            mid = r["model_id"]
            if mid not in M.MODEL_IDS:          # only the live rules are registered
                continue
            conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_id = %s AND is_active = 1", (mid,))
            conn.execute("""
                INSERT INTO model_registry (model_id, version, trained_on, train_seasons, holdout_season,
                                            holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                                            is_active, model_path, notes)
                VALUES (%s, %s, %s, %s, %s, NULL, NULL, NULL, NULL, 1, %s, %s)
            """, (mid, art["version"], date.today().isoformat(),
                  json.dumps(art["state_model"]["train_seasons"]), art["state_model"]["train_seasons"][-1],
                  rel, f"IG-2 game-state model, {r['phase']} {r['market']} EV >= {r['graded_cut']} "
                       "(docs/nba_models_2026.md 7.3); JSON artifact, models/nba_live_ig2.py"))
        conn.commit()
    finally:
        conn.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--parity-held", action="store_true")
    ap.add_argument("--parity-live27", action="store_true")
    ap.add_argument("--wait", type=float, default=WAIT_S)
    ap.add_argument("--every-fetch", action="store_true",
                    help="--parity-live27 over every worker fetch, not the loop's fetch times")
    ap.add_argument("--json-out", type=Path, default=None)
    ap.add_argument("--store", type=Path)
    ap.add_argument("--register", type=Path)
    a = ap.parse_args(argv)
    for p in (a.store, a.register):
        if p is not None and not p.is_absolute():
            sys.exit("--store / --register take an ABSOLUTE path")
    pd.set_option("display.width", 220)
    out = {}
    if a.build:
        build()
    if a.parity_held:
        out["held"] = parity_held()
    if a.parity_live27:
        out["live27"] = parity_live27(a.wait, a.every_fetch)
    if a.json_out and out:
        a.json_out.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    if a.store:
        store(a.store)
    if a.register:
        register(a.register)


if __name__ == "__main__":
    main()
