"""The "best few a night" variant, run only after the plain grid was written up.

DEFINITION (the NCAAB selection, models/ncaab_live_ig.night_cut and
scripts/ncaab_ingame_search.select_nights, on the four NCAAF rules):
  decision   per game and rule, its FIRST eligible quote, the better allowed
             side. That one quote decides: under the night's cut, or over it
             with the night full, the rule is spent for that game.
  night cut  the EV that the FIT-side decisions exceeded 4 times per expected
             decision on a slate that size (decisions per slate game x the
             slate's games), never under 0.02. Fit side: for test A the 2025
             replay's decisions under the all-2025 model; for B1 the weeks 1-7
             decisions under the weeks 1-7 model; for B2 the mirror. A slate's
             games = its games with an eligible quote.
  selection  a slate date's decisions in the order received (ties: higher EV
             first), each at or over the night cut, the first 5.
  placebo    200 runs: each game takes another game's model opinion at the same
             share of the game left (grid.py's placebo), same selection.
Plain model only (the port as specified). V3 exists for test A only and uses
the V2 fit-side table (2025 has no V3).
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from paths import CACHE, MIRROR, WORK  # noqa: E402

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import grid as G

OUT = WORK / "inplay"
NIGHT_TARGET, NIGHT_CAP, FLOOR = 4.0, 5, 0.02


def decisions(px: pd.DataFrame) -> pd.DataFrame:
    return G.pick_sides(px.drop_duplicates(["rule", "game_id"], keep="first").reset_index(drop=True))


def night_table(dec: pd.DataFrame):
    q = np.quantile(dec["ev"].to_numpy(float), np.linspace(0.0, 1.0, 1001))
    per_game = len(dec) / dec.groupby("slate")["game_id"].nunique().sum()
    return q, float(per_game)


def night_cut(q, per_game, n):
    expected = per_game * max(int(n), 0)
    qq = 1.0 - min(1.0, NIGHT_TARGET / expected) if expected > 0 else 0.0
    return max(float(np.interp(qq, np.linspace(0.0, 1.0, len(q)), q)), FLOOR)


def select(dec: pd.DataFrame, cuts: dict) -> pd.DataFrame:
    d = dec[dec["ev"] >= dec["slate"].map(cuts)]
    d = d.sort_values(["slate", "fetch_s", "ev"], ascending=[True, True, False], kind="stable")
    return d.groupby("slate", sort=False).head(NIGHT_CAP)


def placebo_night(px: pd.DataFrame, cuts: dict, runs: int = G.N_PLACEBO) -> np.ndarray:
    nb = int(round(1.0 / G.F_BAND))
    first = px.drop_duplicates(["rule", "game_id"], keep="first").reset_index(drop=True)
    parts = []
    for rule, g in px.groupby("rule", sort=False):
        gi, gids = pd.factorize(g["game_id"])
        n = len(gids)
        band = np.clip((g["f"].to_numpy(float) / G.F_BAND).astype(int), 0, nb - 1)
        cond = g["p_a"].to_numpy(float) / np.maximum(1.0 - g["p_push"].to_numpy(float), 1e-9)
        T = pd.DataFrame({"g": gi, "b": band, "op": cond - g["novig_a"].to_numpy(float)}) \
            .groupby(["g", "b"])["op"].mean().unstack().reindex(index=range(n), columns=range(nb)).to_numpy()
        F = T.copy()
        for k in (1, 2):
            for sh in (k, -k):
                S = np.full_like(T, np.nan)
                if sh > 0:
                    S[:, sh:] = T[:, :-sh]
                else:
                    S[:, :sh] = T[:, -sh:]
                F = np.where(np.isnan(F), S, F)
        fr = first[first["rule"] == rule]
        idx = pd.Index(gids).get_indexer(fr["game_id"])
        parts.append({"n": n, "F": F, "gi": idx,
                      "band": np.clip((fr["f"].to_numpy(float) / G.F_BAND).astype(int), 0, nb - 1), "fr": fr})
    out = []
    for seed in range(1, runs + 1):
        rng = np.random.default_rng(seed)
        frames = []
        for p in parts:
            perm = rng.permutation(p["n"])
            donor = np.empty(p["n"], dtype=int)
            donor[perm] = np.roll(perm, 1)
            fr = p["fr"]
            o = p["F"][donor[p["gi"]], p["band"]]
            push = fr["p_push"].to_numpy(float)
            pr = np.clip(fr["novig_a"].to_numpy(float) + o, 0.005, 0.995)
            pa, pb = pr * (1 - push), (1 - pr) * (1 - push)
            ea = np.where(fr["ok_a"].to_numpy(bool) & ~np.isnan(o), G.ev_of(fr["price_a"], pa, push), -np.inf)
            eb = np.where(fr["ok_b"].to_numpy(bool) & ~np.isnan(o), G.ev_of(fr["price_b"], pb, push), -np.inf)
            a = ea >= eb
            frames.append(pd.DataFrame({"slate": fr["slate"].to_numpy(), "fetch_s": fr["fetch_s"].to_numpy(),
                                        "ev": np.where(a, ea, eb),
                                        "units": np.where(a, fr["units_a"], fr["units_b"]),
                                        "risk": np.where(a, fr["risk_a"], fr["risk_b"])}))
        b = select(pd.concat(frames, ignore_index=True), cuts)
        out.append(G.roi(b) if len(b) else np.nan)
    return np.asarray(out)


def run(name: str, label: str, px: pd.DataFrame, fit_px: pd.DataFrame, split: str) -> dict:
    dec = decisions(px)
    q, per_game = night_table(decisions(fit_px))
    slate_n = dec.groupby("slate")["game_id"].nunique()
    cuts = {s: night_cut(q, per_game, n) for s, n in slate_n.items()}
    b = select(dec, cuts)
    per = b.groupby("slate").size()
    s = G.summarise(b, split)
    pl = placebo_night(px, cuts)
    s.update({
        "test": name, "variant": label, "decisions": int(len(dec)), "slates": int(len(slate_n)),
        "fit_side_decisions": int(len(decisions(fit_px))), "fit_side_per_game": round(per_game, 3),
        "per_slate": round(len(b) / len(slate_n), 2), "slates_without_a_bet": int(len(slate_n) - len(per)),
        "most_in_a_slate": int(per.max()) if len(per) else 0,
        "night_cut_min": round(min(cuts.values()), 4), "night_cut_median": round(float(np.median(list(cuts.values()))), 4),
        "night_cut_max": round(max(cuts.values()), 4),
        "by_rule": {r: {"bets": int(len(x)), "units": round(float(x["units"].sum()), 2), "roi": round(G.roi(x), 4)}
                    for r, x in b.groupby("rule")},
        "placebo_mean": round(float(np.nanmean(pl)), 4), "placebo_p95": round(float(np.nanpercentile(pl, 95)), 4),
        "placebo_max": round(float(np.nanmax(pl)), 4), "placebo_runs_above": int(np.nansum(pl >= s.get("roi", np.inf)))})
    b.assign(test=name, variant=label).to_parquet(OUT / f"night_{name}_{label}.parquet", index=False)
    return s


def main() -> int:
    res = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
    tr = pd.read_parquet(OUT / "train_states.parquet")
    fits = {"B1": G.fit_models(tr[tr["block"] == "early"]), "B2": G.fit_models(tr[tr["block"] == "late"])}
    pA, pB1, pB2 = (pd.read_parquet(OUT / f"priced_{n}.parquet") for n in ("A", "B1", "B2"))
    ins = pd.read_parquet(OUT / "priced_2025_insample.parquet")
    fit_side = {"A": ins, "B1": G.price_quotes(pB2, fits["B1"]),      # weeks 1-7 quotes, weeks 1-7 model
                "B2": G.price_quotes(pB1, fits["B2"])}                # weeks 8+ quotes, weeks 8+ model
    test = {"A": pA, "B1": pB1, "B2": pB2}
    out = []
    for name in ("A", "B1", "B2"):
        for label in ("V1", "V2") + (("V3",) if name == "A" else ()):
            px = test[name] if label == "V1" else test[name][test[name]["v2" if label == "V2" else "v3"]]
            fp = fit_side[name] if label == "V1" else fit_side[name][fit_side[name]["v2"]]
            s = run(name, label, px.reset_index(drop=True), fp.reset_index(drop=True), res[name]["split_date"])
            out.append(s)
            print(json.dumps(s, default=str))
    (OUT / "night.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
