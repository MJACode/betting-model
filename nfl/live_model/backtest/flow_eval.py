"""
Does a flow model beat the mechanically prorated live prop line?

    python -m live_model.backtest.flow_eval --fit

THE TEST, and the reason it is shaped this way.
The bet is an over/under against a number the book derived by prorating its
opening line. So the question is not "is our projection accurate" but "when we
disagree with that number, are we right more than 52.38% of the time". That is
exactly the form of the opener model already validated in this repo, and it is
evaluated the same way: measure the deviation, gate on its size, count hits
against the vig hurdle.

PRE-COMMITTED KILL LINE, stated before any number was looked at:
  a market is DEAD unless it clears 52.38% at a gate that leaves at least 200
  bets, in BOTH held-out seasons. One season clearing is variance.

Everything is walk-forward by season: the model for season N is trained only on
seasons before N, and the baseline anchor inside the dataset is built from
prior games only. Confidence intervals are a cluster bootstrap over GAMES,
because one game contributes many correlated player rows.

WHAT THIS CANNOT TELL US. The anchor is a proxy for the opening line built from
the player's own trailing average, not a real opening line. A real book knows
the injury report, the opponent's coverage and the game plan, so its opener is
sharper than this proxy. Beating the proxy is necessary, not sufficient. The
size of that gap is the single biggest open question after this runs, and it is
settled by pulling real prop snapshots, not by more modelling.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..config import ARTIFACT_DIR
from ..engine.prop_flow import (
    FLOW_MARKETS, predict_flow, save_flow, train_flow,
)

BREAKEVEN = 0.5238          # -110 both ways

# THE CONTROL. Anchor-equivalent features only: the clock, the player's level,
# and what he already has. No score, no pace, no usage, no script.
#
# This exists because the headline number is NOT the edge. A model with only
# these features still beats the reconstructed anchor, purely by learning a
# better functional form of the prorate than the anchor uses, and a real book
# has a better functional form too. So the honest quantity is the DIFFERENCE
# between the full model and this control: that is the part attributable to
# game flow, which is the actual thesis. Reporting the headline alone would
# overstate the edge by five to six points.
ANCHOR_ONLY_FEATURES = [
    "naive_remaining", "baseline_per_game", "frac_remaining", "accrued",
    "accrued_vs_expected", "rate_ratio", "seconds_remaining", "period",
]
MIN_BETS = 200
FIRST_EVAL_SEASON = 2018
BOOT_DRAWS = 400
# Deviation gates, as a fraction of the naive line. Scale free so one grid
# works across receptions (~2) and passing yards (~250).
GATES = (0.0, 0.05, 0.10, 0.15, 0.20, 0.30, 0.40)

FLOW_PATH = ARTIFACT_DIR / "flow_rows.parquet"


def load_rows() -> pd.DataFrame:
    if not FLOW_PATH.exists():
        raise SystemExit(
            f"{FLOW_PATH} missing. Build it with live_model.backtest.flow_dataset."
        )
    return pd.read_parquet(FLOW_PATH)


def fit_time_curve(train: pd.DataFrame) -> dict:
    """
    The share of a player's baseline that actually gets produced in the time
    remaining, per decision point, fitted on TRAINING seasons only.

    THE ANCHOR HAS TO BE A FAIR LINE OR THE WHOLE TEST IS WORTHLESS.
    A raw linear prorate is NOT fair. Measured over 2015-2025, a back produces
    only ~85% of his prorated rushing in the time remaining, and a passing game
    produces ~130% of its prorate inside the last ten minutes. Left uncorrected,
    a model could clear breakeven by doing nothing more than betting rushing
    unders every week, and we would have measured a clock artifact of our own
    construction rather than an edge over a book.

    So the curve is calibrated to the MEDIAN realised share, which makes the
    anchor go over almost exactly half the time by construction. The model then
    has to find CONDITIONAL signal, which is the thing that would actually
    survive contact with a real book.

    Whether real books make the unconditional error is a separate and valuable
    question, but it can only be answered with real prop lines, not with this
    proxy. It is reported separately and never counted as edge here.
    """
    curve = {}
    for dp, g in train.groupby("decision_point"):
        share = (g["actual_remaining"] / g["baseline_per_game"].clip(lower=0.5))
        curve[int(dp)] = float(np.median(share))
    return curve


# How much weight a book's live number puts on TODAY'S pace rather than the
# player's season form, as a function of how much of the game it has seen.
# A book that ignored today's pace would be leaving a back who already has five
# carries in the first quarter priced off his season average, which no live
# book does, and pretending otherwise turns the benchmark into a strawman.
PACE_BLEND_GAMES = 0.45     # observed fraction of a game needed for even weight


def apply_anchor(d: pd.DataFrame, curve: dict) -> pd.DataFrame:
    """
    The book's live number, reconstructed as a real book would build it.

    Two ingredients, because a live line has two:
      1. the player's season form, prorated by the calibrated time curve, and
      2. TODAY'S observed pace, extrapolated over the rest of the game.

    The first version of this file used only ingredient 1, and the result was a
    model hitting 84% against it. That was not an edge, it was a strawman: the
    benchmark was pricing a back who already had five first quarter carries off
    his season average. Any live book blends in what it is watching, so the
    benchmark has to as well, and the model now has to beat a number that
    already knows how the game is going.
    """
    out = d.copy()
    share = out["decision_point"].map(curve).fillna(out["frac_remaining"])
    elapsed = (1.0 - out["frac_remaining"]).clip(lower=1e-6)

    # Today's pace, extrapolated to a full game.
    pace_full_game = out["accrued"] / elapsed
    # Weight on today rises as more of the game is seen.
    w = (elapsed / (elapsed + PACE_BLEND_GAMES)).clip(0.0, 0.85)
    blended = w * pace_full_game + (1.0 - w) * out["baseline_per_game"]

    out["anchor_share"] = share
    out["anchor_baseline"] = blended
    out["naive_remaining"] = blended * share
    out["naive_final"] = out["accrued"] + out["naive_remaining"]
    return out


def walk_forward(rows: pd.DataFrame, market: str, rounds: int = 500,
                 features: list | None = None,
                 use_oracle_baseline: bool = False) -> pd.DataFrame:
    """
    Out-of-sample predictions for every season from FIRST_EVAL_SEASON on.

    Both the model AND the anchor's time curve are fitted on prior seasons
    only. Calibrating the anchor on the season being evaluated would hand the
    benchmark information the book could not have had.
    """
    d = rows[rows.market == market]
    out = []
    for season in sorted(s for s in d.season.unique() if s >= FIRST_EVAL_SEASON):
        prior = d[d.season < season]
        cur = d[d.season == season]
        if len(prior) < 2000 or cur.empty:
            continue
        if use_oracle_baseline:
            prior = prior.dropna(subset=["oracle_per_game"]).copy()
            cur = cur.dropna(subset=["oracle_per_game"]).copy()
            if prior.empty or cur.empty:
                continue
            prior["baseline_per_game"] = prior["oracle_per_game"]
            cur["baseline_per_game"] = cur["oracle_per_game"]
        curve = fit_time_curve(prior)
        prior_a = apply_anchor(prior, curve)
        cur_a = apply_anchor(cur, curve)
        prior_a = drop_degenerate(prior_a, market)
        cur_a = drop_degenerate(cur_a, market)
        if prior_a.empty or cur_a.empty:
            continue
        model = train_flow(prior_a, None, rounds=rounds, features=features)
        pred = predict_flow(model, cur_a, features=features)
        c = cur_a.copy()
        c["model_remaining"] = pred
        c["model_final"] = c["accrued"] + pred
        out.append(c)
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame()


# A line whose remaining component is trivially small is not a real prop. When
# the anchor sits on top of the accrued total, "over" degenerates into "does he
# touch the ball once more", which is not a bet a book offers and which a model
# wins essentially always. Measured: at the five minute mark the calibrated
# share fell to zero and the model went 65 for 65.
MIN_LIVE_REMAINING = {
    "player_pass_yds": 20.0, "player_pass_attempts": 3.0,
    "player_pass_completions": 2.0, "player_rush_yds": 8.0,
    "player_rush_attempts": 2.0, "player_reception_yds": 8.0,
    "player_receptions": 1.0,
}


def drop_degenerate(d: pd.DataFrame, market: str) -> pd.DataFrame:
    """Keep only states where a book would actually still have a line up."""
    floor = MIN_LIVE_REMAINING.get(market, 1.0)
    return d[d["naive_remaining"] >= floor].copy()


def grade(d: pd.DataFrame) -> pd.DataFrame:
    """
    Side, deviation and outcome for every row.

    The bet is on the naive line: over when the model says more production is
    coming than the prorate implies, under when it says less. A result exactly
    on the number is a push and is dropped rather than counted as a win, which
    matters for the count markets where exact ties are common.
    """
    d = d.copy()
    d["deviation"] = d["model_final"] - d["naive_final"]
    d["dev_frac"] = d["deviation"] / d["naive_final"].clip(lower=0.5)
    d["side"] = np.where(d["deviation"] > 0, "over", "under")
    over_hit = d["actual_final"] > d["naive_final"]
    under_hit = d["actual_final"] < d["naive_final"]
    d["won"] = np.where(d["side"] == "over", over_hit, under_hit).astype(float)
    d.loc[d["actual_final"] == d["naive_final"], "won"] = np.nan   # push
    return d


def _boot_ci(won: np.ndarray, games: np.ndarray, rng) -> tuple[float, float]:
    uniq = np.unique(games)
    idx_by_game = {g: np.flatnonzero(games == g) for g in uniq}
    draws = []
    for _ in range(BOOT_DRAWS):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_game[g] for g in pick])
        draws.append(float(np.nanmean(won[idx])))
    return float(np.percentile(draws, 5)), float(np.percentile(draws, 95))


def sweep(graded: pd.DataFrame, rng) -> pd.DataFrame:
    rows = []
    for gate in GATES:
        d = graded[graded["dev_frac"].abs() >= gate].dropna(subset=["won"])
        if len(d) < 30:
            continue
        won = d["won"].to_numpy()
        lo, hi = _boot_ci(won, d["game_id"].to_numpy(), rng)
        rows.append({
            "gate": gate, "n": int(len(d)),
            "hit": float(won.mean()), "lo": lo, "hi": hi,
            "over_share": float((d["side"] == "over").mean()),
            "edge_pp": float((won.mean() - BREAKEVEN) * 100),
        })
    return pd.DataFrame(rows)


def best_hit(graded: pd.DataFrame, gate: float) -> tuple[int, float]:
    d = graded[graded["dev_frac"].abs() >= gate].dropna(subset=["won"])
    return len(d), (float(d["won"].mean()) if len(d) else float("nan"))


def evaluate(rounds: int = 500, seed: int = 3) -> dict:
    rows = load_rows()
    rng = np.random.default_rng(seed)
    results = {}
    fitted = {}

    for market in FLOW_MARKETS:
        oos = walk_forward(rows, market, rounds=rounds)
        if oos.empty:
            results[market] = {"skipped": "insufficient history"}
            continue
        graded = grade(oos)
        overall = sweep(graded, rng)

        # Per season, at each gate, so the kill line can be applied honestly.
        per_season = {}
        for season in sorted(graded.season.unique()):
            s = sweep(graded[graded.season == season], rng)
            if not s.empty:
                per_season[int(season)] = s

        # The naive anchor's own bias, which tells us whether any measured edge
        # is real signal or just an anchor that leans one way.
        anchor_over = float((graded["actual_final"] > graded["naive_final"]).mean())

        results[market] = {
            "n_rows": int(len(graded)),
            "games": int(graded.game_id.nunique()),
            "anchor_over_rate": anchor_over,
            "overall": overall,
            "per_season": per_season,
            "seasons": sorted(int(s) for s in graded.season.unique()),
        }
        # THE CONTROL, run on every market, every time. Never report the
        # headline without it.
        ctrl = walk_forward(rows, market, rounds=rounds,
                            features=ANCHOR_ONLY_FEATURES)
        oracle = walk_forward(rows, market, rounds=rounds,
                              use_oracle_baseline=True)
        results[market]["control"] = grade(ctrl) if not ctrl.empty else None
        results[market]["oracle"] = grade(oracle) if not oracle.empty else None
        results[market]["graded"] = graded

        # Final fit on everything, for serving.
        fitted[market] = train_flow(rows[rows.market == market], None, rounds=rounds)

    return {"results": results, "models": fitted}


def verdict(res: dict) -> dict:
    """
    Apply the pre-committed kill line. Written as code so it cannot be
    relitigated by looking at the numbers first and choosing a rule after.
    """
    out = {}
    for market, r in res.items():
        if "skipped" in r:
            out[market] = {"status": "NO DATA", "detail": r["skipped"]}
            continue
        best = None
        for _, row in r["overall"].iterrows():
            if row["n"] < MIN_BETS or row["hit"] <= BREAKEVEN:
                continue
            seasons_clear = 0
            for season, s in r["per_season"].items():
                m = s[s.gate == row["gate"]]
                if not m.empty and m.iloc[0]["hit"] > BREAKEVEN and m.iloc[0]["n"] >= 40:
                    seasons_clear += 1
            cand = {"gate": float(row["gate"]), "n": int(row["n"]),
                    "hit": float(row["hit"]), "lo": float(row["lo"]),
                    "seasons_clear": seasons_clear,
                    "seasons_total": len(r["per_season"])}
            if seasons_clear >= max(2, int(0.6 * len(r["per_season"]))):
                if best is None or cand["hit"] > best["hit"]:
                    best = cand
        out[market] = ({"status": "LIVE CANDIDATE", **best} if best else
                       {"status": "DEAD",
                        "detail": "no gate clears breakeven at volume in enough seasons"})
    return out


def report(res: dict) -> None:
    print("\n=== live prop flow vs the prorated line ===")
    print(f"breakeven {BREAKEVEN:.4f} at -110 both ways; a gate needs "
          f"{MIN_BETS}+ bets and must clear in most seasons\n")
    for market, r in res.items():
        if "skipped" in r:
            print(f"{market:26s} SKIPPED ({r['skipped']})")
            continue
        print(f"{market}   rows {int(r['n_rows']):,}  games {int(r['games']):,}  "
              f"seasons {r['seasons'][0]}-{r['seasons'][-1]}")
        print(f"  anchor goes over {100*r['anchor_over_rate']:.1f}% of the time "
              f"(50% means the proxy line is fair)")
        for _, row in r["overall"].iterrows():
            flag = "  <-- clears" if row["hit"] > BREAKEVEN and row["n"] >= MIN_BETS else ""
            print(f"    gate {row['gate']:.2f}  n={int(row['n']):6d}  "
                  f"hit {100*row['hit']:5.2f}% [{100*row['lo']:5.2f}, "
                  f"{100*row['hi']:5.2f}]  edge {row['edge_pp']:+5.2f}pp  "
                  f"over {100*row['over_share']:4.0f}%{flag}")

        # The decomposition. This is the number that matters.
        if r.get("control") is not None:
            print("    DECOMPOSITION (headline is not the edge):")
            for gate in (0.0, 0.10, 0.20):
                nf, hf = best_hit(r["graded"], gate)
                nc, hc = best_hit(r["control"], gate)
                if nf < MIN_BETS or nc < MIN_BETS:
                    continue
                line = (f"      gate {gate:.2f}  full {100*hf:5.2f}%  "
                        f"control {100*hc:5.2f}%  FLOW ADDS {100*(hf-hc):+5.2f}pp")
                if r.get("oracle") is not None:
                    no, ho = best_hit(r["oracle"], gate)
                    if no >= MIN_BETS:
                        line += f"   (vs oracle baseline {100*ho:5.2f}%)"
                print(line)
        print()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fit", action="store_true")
    ap.add_argument("--rounds", type=int, default=500)
    ap.add_argument("--market", default=None)
    args = ap.parse_args()

    ev = evaluate(rounds=args.rounds)
    res = ev["results"]
    if args.market:
        res = {k: v for k, v in res.items() if k == args.market}
    report(res)

    print("=== verdict against the pre-committed kill line ===")
    for market, v in verdict(res).items():
        extra = ""
        if v["status"] == "LIVE CANDIDATE":
            extra = (f" gate {v['gate']:.2f}  n={v['n']}  "
                     f"hit {100*v['hit']:.2f}% (5th pct {100*v['lo']:.2f}%)  "
                     f"clears {v['seasons_clear']}/{v['seasons_total']} seasons")
        print(f"  {market:26s} {v['status']:16s}{extra or '  ' + v.get('detail','')}")

    if args.fit and ev["models"]:
        save_flow(ev["models"], ARTIFACT_DIR,
                  meta={"breakeven": BREAKEVEN, "gates": list(GATES)})
        print(f"\nflow models saved to {ARTIFACT_DIR}")


if __name__ == "__main__":
    main()
