"""
Calibration gate for the PROP engine. The prop analogue of calibrate.py.

    python -m live_model.backtest.calibrate_props --season 2025

WHY THIS EXISTS. The prop engine shipped with sixteen unit tests that check the
game-script mechanism responds in the right DIRECTION: trailing teams throw,
the back's remaining rushing yards collapse, the receiver's rise. That is
necessary and nowhere near sufficient. A prop price is entirely a tail
question. With eight minutes left, the difference between a 55% and a 45% over
is almost all in the SPREAD of the distribution, not in its mean. A model can
be right on average and wrong in the tails, and it will then find fake edges in
exactly the props that sit furthest from the mean, which are the ones a book
prices laziest and we would therefore bet most.

So this measures the same two things the score gate measures, on the same
held-out season, with the same randomised PIT and the same game-clustered
bootstrap:

  1. Is the projected MEAN unbiased, per market and per time bucket?
  2. Is the DISTRIBUTION calibrated, so a stated 60% over happens 60% of
     the time?

Gate 2 is the one that decides whether props can be bet at all.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from ..config import ARTIFACT_DIR
from ..engine.distribution import time_bucket
from ..engine.props import price_over, project
from ..state import GameState, PlayerState
from .player_states import (
    MARKET_STAT, attach_game_context, build_player_states, load_pbp_players,
)
from .train_engine import load_states

QUANTILES = (0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95)
COVERAGE_GATE_PP = 3.0      # looser than the score gate: see the note below
BIAS_GATE = 0.15            # mean projection within 15% of realised
PIT_SEED = 23
BOOT_DRAWS = 300

# Markets to gate. Pass touchdowns are excluded: the per attempt TD rate is a
# flat constant in the engine rather than a modelled quantity, so gating it
# would be measuring a hardcoded number, not the model.
GATED_MARKETS = (
    "player_pass_yds", "player_pass_attempts", "player_pass_completions",
    "player_rush_yds", "player_rush_attempts",
    "player_reception_yds", "player_receptions",
)

# Positions inferred from usage, because nflverse pbp carries no position on
# the play row. Crude but sufficient: the engine only uses position to pick a
# shrinkage prior.
def _infer_position(row) -> str:
    if row["acc_pass_att"] > 0 or row["pass_att"] > 0:
        return "QB"
    if row["acc_rush_att"] >= row["acc_targets"]:
        return "RB"
    return "WR"


def _rows_for_market(joined: pd.DataFrame, market: str,
                     min_opportunity: float = 1.0) -> pd.DataFrame:
    """
    Rows where the market is live enough to price.

    A player with no accrued involvement and no snaps has no prop quoted on
    him, so including those rows would measure the model on states no book
    would ever price.
    """
    stat = MARKET_STAT[market]
    d = joined[joined["seconds_remaining"] > 60].copy()
    if market.startswith("player_pass"):
        d = d[d["acc_pass_att"] >= 5]
    elif market.startswith("player_rush"):
        d = d[d["acc_rush_att"] >= min_opportunity]
    else:
        d = d[d["acc_targets"] >= min_opportunity]
    d["actual_remaining"] = d[f"rem_{stat}"]
    d["accrued"] = d[f"acc_{stat}"]
    return d


def _pool_prior(row, market: str) -> float:
    """Realised share of the opportunity pool this market draws from."""
    plays = max(float(row["team_plays_so_far"]), 1.0)
    side = row["team_side"]
    rate = float(row["home_pass_rate"] if side == "home" else row["away_pass_rate"])
    if market.startswith("player_pass"):
        return 1.0 if row["position"] == "QB" else 0.0
    if market.startswith("player_rush"):
        return min(float(row["acc_rush_att"]) / max(plays * (1 - rate), 1.0), 1.0)
    return min(float(row["acc_targets"]) / max(plays * rate, 1.0), 1.0)


def _to_states(row) -> tuple[GameState, PlayerState]:
    gs = GameState(
        game_id=row["game_id"], ts=pd.Timestamp("2020-01-01", tz="UTC"),
        period=int(row["qtr"]), clock_seconds=int(row["quarter_seconds_remaining"]),
        home_score=int(row["home_score_pre"]), away_score=int(row["away_score_pre"]),
        possession=row["team_side"], down=None, distance=None, yardline_100=None,
        home_timeouts=int(row["home_timeouts_remaining"]),
        away_timeouts=int(row["away_timeouts_remaining"]),
        pregame_spread=float(row["pregame_spread"]),
        pregame_total=float(row["pregame_total"]),
        wind_mph=None if pd.isna(row["wind_mph"]) else float(row["wind_mph"]),
        is_dome=bool(row["is_dome"]), plays_run=int(row["plays_run"]),
        home_pass_rate=float(row["home_pass_rate"]),
        away_pass_rate=float(row["away_pass_rate"]),
    )
    ps = PlayerState(
        player_id=row["player_id"], game_id=row["game_id"], ts=gs.ts,
        team_side=row["team_side"], position=row["position"],
        pass_att=int(row["acc_pass_att"]), pass_cmp=int(row["acc_pass_cmp"]),
        pass_yds=int(row["acc_pass_yds"]), pass_tds=int(row["acc_pass_tds"]),
        rush_att=int(row["acc_rush_att"]), rush_yds=int(row["acc_rush_yds"]),
        targets=int(row["acc_targets"]), receptions=int(row["acc_receptions"]),
        rec_yds=int(row["acc_rec_yds"]),
        # The live engine gets this from pregame usage history. Here it is the
        # player's own realised share so far in the game, which is the same
        # quantity the engine blends toward and keeps the gate honest about
        # what the engine actually receives.
        # Prior for the pool this market draws from. The live engine gets a
        # pregame usage expectation here; the gate supplies the player's own
        # realised share of the SAME pool, which is the quantity the engine
        # blends toward.
        snap_share_prior=float(row["usage_prior"]), active=True,
    )
    return gs, ps


def evaluate(season: int, sample_every: int = 40) -> dict:
    game_states = load_states()
    gs_season = game_states[game_states.season == season]
    if gs_season.empty:
        raise SystemExit(f"no game states for {season}")

    ps = build_player_states(load_pbp_players([season]))
    joined = attach_game_context(ps, gs_season)
    joined["team_side"] = joined["team_side"]
    joined["position"] = joined.apply(_infer_position, axis=1)
    # Usage share so far, the engine's blend target.
    denom = joined["team_plays_so_far"].clip(lower=1.0)
    joined["usage_prior"] = np.where(
        joined["position"] == "QB", 1.0,
        ((joined["acc_rush_att"] + joined["acc_targets"]) / denom).clip(0, 1))

    rng = np.random.default_rng(PIT_SEED)
    results = {}
    for market in GATED_MARKETS:
        d = _rows_for_market(joined, market).iloc[::sample_every]
        if len(d) < 200:
            results[market] = {"n": int(len(d)), "skipped": "too few rows"}
            continue

        mu = np.zeros(len(d))
        pit = np.zeros(len(d))
        actual = d["actual_remaining"].to_numpy(dtype=float)
        secs = d["seconds_remaining"].to_numpy(dtype=float)

        for i, (_, row) in enumerate(d.iterrows()):
            r = dict(row)
            r["usage_prior"] = _pool_prior(row, market)
            gs, plr = _to_states(r)
            proj = project(plr, gs, market, float(row["team_plays_so_far"]))
            mu[i] = proj.mu_remaining
            # PIT via the model's own over price at the realised value. A
            # randomised correction handles the atom at zero, which for a
            # backup's remaining carries is most of the mass.
            line_at = float(row["accrued"]) + actual[i]
            p_above = price_over(proj, line_at)["over"]
            p_at_or_below = 1.0 - p_above
            p_below = price_over(proj, line_at - 0.5)["under"] \
                if market.endswith(("attempts", "completions", "receptions")) \
                else p_at_or_below
            p_below = min(p_below, p_at_or_below)
            pit[i] = p_below + rng.random() * max(p_at_or_below - p_below, 0.0)

        bias = float(np.mean(mu) / max(np.mean(actual), 1e-9) - 1.0)
        cov = {q: float((pit <= q).mean()) for q in QUANTILES}
        worst = max(abs(cov[q] - q) * 100 for q in QUANTILES)

        games = d["game_id"].to_numpy()
        uniq = np.unique(games)
        idx_by_game = {g: np.flatnonzero(games == g) for g in uniq}
        worsts = []
        for _ in range(BOOT_DRAWS):
            pick = rng.choice(uniq, size=len(uniq), replace=True)
            idx = np.concatenate([idx_by_game[g] for g in pick])
            c = {q: float((pit[idx] <= q).mean()) for q in QUANTILES}
            worsts.append(max(abs(c[q] - q) * 100 for q in QUANTILES))

        tb = time_bucket(secs)
        by_bucket = []
        for b in sorted(set(tb.tolist())):
            m = tb == b
            if m.sum() < 60:
                continue
            c = {q: float((pit[m] <= q).mean()) for q in QUANTILES}
            by_bucket.append({
                "bucket": int(b), "n": int(m.sum()),
                "worst_pp": max(abs(c[q] - q) * 100 for q in QUANTILES),
                "bias": float(np.mean(mu[m]) / max(np.mean(actual[m]), 1e-9) - 1.0),
            })

        results[market] = {
            "n": int(len(d)), "games": int(len(uniq)),
            "mean_projected": float(np.mean(mu)),
            "mean_actual": float(np.mean(actual)),
            "bias": bias, "mae": float(np.mean(np.abs(mu - actual))),
            "coverage": cov, "worst_pp": worst,
            "worst_pp_lo": float(np.percentile(worsts, 5)),
            "worst_pp_hi": float(np.percentile(worsts, 95)),
            "by_bucket": by_bucket,
            "bias_pass": abs(bias) <= BIAS_GATE,
            "coverage_pass": worst <= COVERAGE_GATE_PP,
        }
    return {"season": season, "markets": results}


def report(res: dict) -> None:
    print(f"\n=== prop engine calibration, season {res['season']} ===")
    print(f"gates: |bias| <= {BIAS_GATE:.0%}, worst quantile coverage "
          f"<= {COVERAGE_GATE_PP:.1f}pp")
    print("\nNOTE the coverage gate is 3pp here against 2pp for the score "
          "model. A prop distribution is coarser (many have a hard atom at "
          "zero remaining) and the sample per market is smaller, so demanding "
          "the same tolerance would be demanding precision the data cannot "
          "resolve rather than accuracy the model can deliver.\n")

    any_fail = False
    for market, r in res["markets"].items():
        if "skipped" in r:
            print(f"{market:26s} SKIPPED ({r['skipped']}, n={r['n']})")
            continue
        ok = r["bias_pass"] and r["coverage_pass"]
        any_fail |= not ok
        print(f"{market:26s} {'PASS' if ok else 'FAIL'}  n={r['n']:5d} "
              f"games={r['games']:3d}")
        print(f"  projected {r['mean_projected']:6.2f} vs actual "
              f"{r['mean_actual']:6.2f}  bias {100*r['bias']:+6.1f}% "
              f"{'ok' if r['bias_pass'] else 'FAIL'}   mae {r['mae']:.2f}")
        print(f"  worst coverage {r['worst_pp']:5.2f}pp "
              f"[{r['worst_pp_lo']:.2f}, {r['worst_pp_hi']:.2f}] "
              f"{'ok' if r['coverage_pass'] else 'FAIL'}")
        buckets = "  ".join(f"b{b['bucket']}:{b['worst_pp']:.1f}pp/"
                            f"{100*b['bias']:+.0f}%" for b in r["by_bucket"])
        if buckets:
            print(f"  by time bucket (0 = final 2 min): {buckets}")

    print(f"\nVERDICT: {'SOME MARKETS FAIL' if any_fail else 'ALL GATED MARKETS PASS'}")
    if any_fail:
        print("A failing market must not be bet. Bias is fixable (the "
              "opportunity model); coverage failure means the tails are wrong "
              "and the market should stay off until it is rebuilt.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2025)
    ap.add_argument("--sample-every", type=int, default=40)
    args = ap.parse_args()
    report(evaluate(args.season, args.sample_every))


if __name__ == "__main__":
    main()
