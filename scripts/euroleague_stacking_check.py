"""EuroLeague: when several models bet one game, is that several edges or one
edge bet several times, and what does it do to the units?

mike, 2026-11-17, after three bets on Virtus in one game (first-half moneyline,
+7.5 and the moneyline): "too many duplicative bets ... what impact does this
have on potential winnings".

Reads the replayed bets of the five EuroLeague models -- the four pre-game
rules (scripts/euroleague_pregame_build.replay, the card's own decision code,
matched bet for bet to the research) and the halftime spread
(scripts/build_euroleague_live_ht_artifact.replay at EV >= 0.05) -- and
prints:

  1. structure: how often each pair of models bets the same game, the same
     team or the opposite team, on games BOTH could bet (each model priced it);
  2. the discriminating split: each model's record when it bets alone and when
     another model is on the same team or the other team;
  3. one bet a game: every fixed priority order among the side models, and the
     bets each drops, graded on their own (units, return, 95% interval
     resampled by game date), by season;
  4. risk beside units: stake per game, the spread of a game's result, the
     worst night and the deepest drawdown, for every-bet against one-a-game;
  5. the live rule since 2026-11-19 (mike: "Strict, moneyline first"): one
     bet a game across all five models, through the card's own
     models.euroleague_pregame.one_bet_a_game, on games all five priced.

Graded on the POSTED stake (tracking.discord_notifier.stake_for: one unit to
win, risk capped at 3, a push returns the stake). The pre-game build's own
units (models.euroleague_pregame.stake: an underdog risks 1) are printed
beside it so the two can be reconciled with docs/sports/euroleague.md.

    python -m scripts.euroleague_stacking_check            # replay once, then reuse
    python -m scripts.euroleague_stacking_check --refresh  # replay again
    python -m scripts.euroleague_stacking_check --live     # the live rules instead

By default the four pre-game rules are the RESEARCH's (the build's
RESEARCH_PARAMS: the rules as they ran until the same-team cuts of
2026-11-17), which is what the 2026-11-17 result measured; --live replays the
build's PARAMS, the cuts included.

Reads only the local research cache (scripts/euroleague_research/_paths.py:
the main checkout's data/local/research/euroleague_research/cache, a copy of
Supabase; scripts/euroleague_research/cache*.py rebuild it) and writes one
derived file beside it (stacking_bets.parquet), regenerable from the cache.
No database, no network. The 2026-11-17 run and its result:
docs/sports/euroleague.md, "Several bets on one game".
"""
from __future__ import annotations

import argparse
import contextlib
import io
import itertools
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import models.euroleague_pregame as R  # noqa: E402

HT = "euroleague_live_spread_ht"
SIDE_MODELS = (R.HOME_ML, R.HOME_DOG_SPREAD, R.H1_DOG_ML, HT)
SHORT = {R.HOME_ML: "ML", R.HOME_DOG_SPREAD: "spread", R.H1_DOG_ML: "1H ML",
         R.Q1_SHARE_TOTAL: "Q1 total", HT: "HT spread"}
PRICED = {"bet", "no_bet", "pick_em"}      # a decision on a quote, bet or not
BOOT = 2000
MAX_RISK = 3.0


def research_root() -> Path:
    from scripts.euroleague_research._paths import ROOT as RR
    return RR


# ── the bets ────────────────────────────────────────────────────────────────

def posted(price) -> tuple[np.ndarray, np.ndarray]:
    """(risk, win) at stake_for: one unit to win, risk capped at 3."""
    p = np.asarray(price, float)
    d = np.where(p > 0, 1 + p / 100, 1 + 100 / np.abs(p))
    risk = np.minimum(1.0 / (d - 1.0), MAX_RISK)
    return risk, risk * (d - 1.0)


def pregame_frames(live: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    import scripts.euroleague_pregame_build as B
    data = B.load(B.cache_dir())
    g = data["games"]
    played = g[g.played & g.margin.notna()].copy()
    research = played[played.game_date <= B.RESEARCH_LAST_DATE]
    with contextlib.redirect_stdout(io.StringIO()):
        dec = B.replay(data, research, params=B.PARAMS if live else B.RESEARCH_PARAMS)
    cov = pd.DataFrame([{"game_id": d.game_id, "model_id": m, "status": d.status}
                        for m in R.MODELS for d in dec[m]])
    art = json.loads(R.artifact_path(B.SEASON).read_text(encoding="utf-8"))
    bets = []
    for m in R.MODELS:
        x = B.graded(dec[m], played, m)
        x["p_model"] = np.clip(x.p_fair + art["models"][m]["uplift"], 0.01, 0.99)
        x["ev"] = x.p_model * R.dec(x.price) - 1
        x["units_build"], x["risk_build"] = x["units"], x["risk"]
        bets.append(x[["game_id", "model_id", "season", "game_date", "side", "line", "price", "book",
                       "ev", "res", "units_build", "risk_build"]])
    return pd.concat(bets, ignore_index=True), cov


def halftime_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    import scripts.build_euroleague_live_ht_artifact as H
    with contextlib.redirect_stdout(io.StringIO()):
        data = H.load(H.CACHE)
        g = H.qualifying(data)
        st = H.states(data["shots"])
        folds = {s: H.fold(g, st, range(H.FIRST_TRAIN, s))[0] for s in H.WF_SEASONS}
        every = H.replay(g, data["inplay"], folds)
    every = every[every.game_date <= "2026-11-12"]
    cov = pd.DataFrame({"game_id": every.game_id, "model_id": HT,
                        "status": np.where(every.ev >= 0.05, "bet", "no_bet")})
    b = every[every.ev >= 0.05].copy()
    b["model_id"] = HT
    b["units_build"], b["risk_build"] = b["units_posted"], b["risk_posted"]
    return b[["game_id", "model_id", "season", "game_date", "side", "line", "price", "book", "ev",
              "res", "units_build", "risk_build"]], cov


def load(refresh: bool, live: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    rr = research_root()
    tag = "_live" if live else ""
    pb, pc = rr / f"stacking_bets{tag}.parquet", rr / f"stacking_coverage{tag}.parquet"
    if refresh or not pb.exists():
        b1, c1 = pregame_frames(live)
        try:
            b2, c2 = halftime_frames()
        except FileNotFoundError as e:      # no shots cache: the four pre-game rules only
            print(f"halftime spread left out (no shot cache: {e})")
            b2, c2 = b1.iloc[0:0], c1.iloc[0:0]
        pd.concat([b1, b2], ignore_index=True).to_parquet(pb, index=False)
        pd.concat([c1, c2], ignore_index=True).to_parquet(pc, index=False)
    b, c = pd.read_parquet(pb), pd.read_parquet(pc)
    b["season"] = b.season.astype(int)
    risk, win = posted(b.price)
    b["risk_placed"] = risk
    b["units"] = np.where(b.res > 0, win, np.where(b.res < 0, -risk, 0.0))
    b["risk"] = np.where(b.res == 0, 0.0, risk)
    b["win"] = (b.res > 0).astype(int)
    b["lose"] = (b.res < 0).astype(int)
    # the team a side bet is on; a total is on no team
    b["team"] = np.where(b.side.isin(["home", "away"]), b.side, None)
    return b, c


# ── grading ─────────────────────────────────────────────────────────────────

def summary(x: pd.DataFrame, label: str, rng, seasons=()) -> dict:
    if not len(x):
        return {"rule": label, "bets": 0}
    d = x.groupby("game_date").agg(u=("units", "sum"), r=("risk", "sum"))
    j = rng.integers(0, len(d), size=(BOOT, len(d)))
    with np.errstate(invalid="ignore", divide="ignore"):
        lo, hi = np.nanpercentile(d.u.values[j].sum(1) / d.r.values[j].sum(1) * 100, [2.5, 97.5])
    row = {"rule": label, "bets": len(x), "games": x.game_id.nunique(),
           "W-L-P": f"{int(x.win.sum())}-{int(x.lose.sum())}-{int((x.res == 0).sum())}",
           "units": round(x.units.sum(), 2),
           "ret%": round(x.units.sum() / x.risk.sum() * 100, 2) if x.risk.sum() else None,
           "95%": f"[{lo:.1f}, {hi:.1f}]"}
    for s in seasons:
        row[f"u{s}"] = round(x.loc[x.season == s, "units"].sum(), 1)
    return row


def risk_profile(x: pd.DataFrame, label: str) -> dict:
    """Exposure and swing of a set of bets, by game and by night."""
    gm = x.groupby("game_id").agg(u=("units", "sum"), r=("risk_placed", "sum"))
    nt = x.groupby("game_date").units.sum().sort_index()
    eq = nt.cumsum()
    dd = float((eq - eq.cummax()).min())
    return {"rule": label, "bets": len(x), "units": round(x.units.sum(), 2),
            "staked/game": round(gm.r.mean(), 2), "max staked/game": round(gm.r.max(), 2),
            "sd/game": round(gm.u.std(), 2), "worst game": round(gm.u.min(), 2),
            "worst night": round(nt.min(), 2), "max drawdown": round(dd, 2),
            "units/sd(night)": round(x.units.sum() / (nt.std() * np.sqrt(len(nt))), 2)}


def keep_one(x: pd.DataFrame, order: tuple) -> pd.DataFrame:
    """One bet a game: the first model in `order` that bet it keeps the game."""
    rank = {m: i for i, m in enumerate(order)}
    return (x.assign(_o=x.model_id.map(rank)).sort_values(["game_id", "_o"])
             .drop_duplicates("game_id").drop(columns="_o"))


def one_bet_a_game(x: pd.DataFrame) -> pd.DataFrame:
    """The live rule (models.euroleague_pregame.one_bet_a_game, the card's own
    code): per game, the first BET in ONE_A_GAME_ORDER keeps it, the halftime
    spread last."""
    rows = [{"game_id": g, "model_id": m, "signal_type": "BET", "pick_label": m}
            for g, m in zip(x.game_id, x.model_id)]
    drop = R.one_bet_a_game(rows, [])
    return x[[(g, m) not in drop for g, m in zip(x.game_id, x.model_id)]]


def keep_one_per_team(x: pd.DataFrame, order: tuple) -> pd.DataFrame:
    """One bet a game per TEAM: same-team stacks collapse, opposite sides stay."""
    rank = {m: i for i, m in enumerate(order)}
    return (x.assign(_o=x.model_id.map(rank)).sort_values(["game_id", "team", "_o"])
             .drop_duplicates(["game_id", "team"]).drop(columns="_o"))


# ── the report ──────────────────────────────────────────────────────────────

def both_could(cov: pd.DataFrame, m1: str, m2: str) -> set:
    ok = cov[cov.status.isin(PRICED)]
    return set(ok[ok.model_id == m1].game_id) & set(ok[ok.model_id == m2].game_id)


def structure(b: pd.DataFrame, cov: pd.DataFrame, models) -> None:
    print("\n=== 1. pairs, on games both models priced")
    rows = []
    for m1, m2 in itertools.combinations(models, 2):
        games = both_could(cov, m1, m2)
        a = b[(b.model_id == m1) & b.game_id.isin(games)].set_index("game_id")
        c = b[(b.model_id == m2) & b.game_id.isin(games)].set_index("game_id")
        both = a.index.intersection(c.index)
        if not len(games):
            continue
        same = (a.loc[both, "side"] == c.loc[both, "side"]) if len(both) else pd.Series(dtype=bool)
        row = {"pair": f"{SHORT[m1]} + {SHORT[m2]}", "priced both": len(games),
               f"{SHORT[m1]} bets": len(a), f"{SHORT[m2]} bets": len(c), "both bet": len(both),
               f"share of {SHORT[m1]}'s": f"{len(both) / max(len(a), 1):.0%}",
               f"share of {SHORT[m2]}'s": f"{len(both) / max(len(c), 1):.0%}",
               "same side": int(same.sum()), "other side": int((~same).sum())}
        if len(both) >= 3:
            s = same[same].index
            if len(s) >= 3:
                row["win corr (same side)"] = round(np.corrcoef(a.loc[s, "win"], c.loc[s, "win"])[0, 1], 2)
                row["both lose (same side)"] = f"{(a.loc[s, 'lose'] & c.loc[s, 'lose']).mean():.0%}"
        rows.append(row)
    for r in rows:
        print("  " + "; ".join(f"{k}: {v}" for k, v in r.items()))


def split(b: pd.DataFrame, cov: pd.DataFrame, models, rng, seasons) -> None:
    """Each model's record alone, beside a same-team bet, and beside an other-team bet,
    over games where every model in `models` priced."""
    ok = cov[cov.status.isin(PRICED) & cov.model_id.isin(models)]
    n = ok.groupby("game_id").model_id.nunique()
    games = set(n[n == len(models)].index)
    x = b[b.model_id.isin(models) & b.game_id.isin(games) & b.team.notna()]
    print(f"\n=== 2. alone / with a same-team bet / with an other-team bet: "
          f"{', '.join(SHORT[m] for m in models)}, on the {len(games)} games all of them priced")
    per = x.groupby(["game_id", "team"]).model_id.nunique().rename("n_same")
    teams = x.groupby("game_id").team.nunique().rename("n_teams")
    x = x.join(per, on=["game_id", "team"]).join(teams, on="game_id")
    rows = []
    for m in models:
        z = x[x.model_id == m]
        rows.append(summary(z[(z.n_same == 1) & (z.n_teams == 1)], f"{SHORT[m]} alone", rng, seasons))
        rows.append(summary(z[z.n_same > 1], f"{SHORT[m]} with a same-team bet", rng, seasons))
        rows.append(summary(z[z.n_teams > 1], f"{SHORT[m]} with an other-team bet", rng, seasons))
    print(pd.DataFrame(rows).to_string(index=False))
    stacks = x.groupby(["game_id", "team"]).model_id.apply(lambda s: " + ".join(sorted(SHORT[m] for m in s)))
    print("same-team stacks:", stacks[stacks.str.contains(r"\+")].value_counts().to_dict())
    print("games by number of these models betting:", x.groupby("game_id").size().value_counts()
          .sort_index().to_dict(), "of", len(games))


def one_a_game(b: pd.DataFrame, cov: pd.DataFrame, models, rng, seasons, title) -> None:
    ok = cov[cov.status.isin(PRICED) & cov.model_id.isin(models)]
    n = ok.groupby("game_id").model_id.nunique()
    games = set(n[n == len(models)].index)
    x = b[b.model_id.isin(models) & b.game_id.isin(games)]
    print(f"\n=== 3/4. {title}: {', '.join(SHORT[m] for m in models)}, {len(games)} games all priced")
    rows = [summary(x, "every bet (live today)", rng, seasons)]
    risks = [risk_profile(x, "every bet (live today)")]
    for order in itertools.permutations(models):
        k = keep_one(x, order)
        lab = "one a game: " + " > ".join(SHORT[m] for m in order)
        rows.append(summary(k, lab, rng, seasons))
        rows.append(summary(x.drop(k.index), "   the bets it drops", rng, seasons))
        risks.append(risk_profile(k, lab))
    for order in itertools.permutations(models):
        k = keep_one_per_team(x, order)
        lab = "one a team: " + " > ".join(SHORT[m] for m in order)
        rows.append(summary(k, lab, rng, seasons))
        rows.append(summary(x.drop(k.index), "   the bets it drops", rng, seasons))
        risks.append(risk_profile(k, lab))
    k = x.sort_values("ev", ascending=False).drop_duplicates("game_id")
    rows.append(summary(k, "one a game: highest EV", rng, seasons))
    risks.append(risk_profile(k, "one a game: highest EV"))
    print(pd.DataFrame(rows).to_string(index=False))
    print(pd.DataFrame(risks).drop_duplicates("rule").to_string(index=False))


def live_rule(b: pd.DataFrame, cov: pd.DataFrame, rng, seasons=(2026, 2027)) -> None:
    models = list(R.ONE_A_GAME_MODELS)
    ok = cov[cov.status.isin(PRICED) & cov.model_id.isin(models)]
    n = ok.groupby("game_id").model_id.nunique()
    games = set(n[n == len(models)].index)
    x = b[b.model_id.isin(models) & b.game_id.isin(games)]
    k = one_bet_a_game(x)
    print(f"\n=== 5. one bet a game, moneyline first (live since 2026-11-19), {len(games)} games all five priced")
    print(pd.DataFrame([summary(x, "every bet", rng, seasons), summary(k, "one bet a game", rng, seasons),
                        summary(x.drop(k.index), "   the bets it drops", rng, seasons)]).to_string(index=False))
    print(pd.DataFrame([risk_profile(x, "every bet"), risk_profile(k, "one bet a game")]).to_string(index=False))
    kept = k.groupby("model_id").size().reindex(models, fill_value=0)
    print("bets kept by model:", {SHORT[m]: int(v) for m, v in kept.items()},
          "| games with 2+ bets:", int((k.groupby("game_id").size() >= 2).sum()))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--refresh", action="store_true", help="replay the models again")
    ap.add_argument("--live", action="store_true", help="the live rules (the build's PARAMS), not the research's")
    a = ap.parse_args(argv)
    rng = np.random.default_rng(7)
    b, cov = load(a.refresh, a.live)
    print("=== replayed bets by model and season: posted stake (units) and the build's stake")
    t = b.groupby(["model_id", "season"]).agg(bets=("units", "size"), units=("units", "sum"),
                                              build=("units_build", "sum")).round(2)
    print(t.unstack(0).to_string())
    tot = b.groupby("model_id").agg(bets=("units", "size"), posted=("units", "sum"), risk=("risk", "sum"),
                                    build=("units_build", "sum"), build_risk=("risk_build", "sum"))
    tot["posted ret%"] = (tot.posted / tot.risk * 100).round(2)
    tot["build ret%"] = (tot.build / tot.build_risk * 100).round(2)
    print(tot.round(2).to_string())

    win = b[b.season >= 2026]
    per_game = win.groupby("game_id").size()
    print(f"\n2025-26 on (every model priced in some games): bets a game with any bet "
          f"{per_game.value_counts().sort_index().to_dict()}; nights mean "
          f"{win.groupby('game_date').size().mean():.1f} bets")
    side = [m for m in SIDE_MODELS if m in set(b.model_id)]
    structure(b, cov, list(R.MODELS) + ([HT] if HT in side else []))
    split(b, cov, [R.HOME_ML, R.HOME_DOG_SPREAD], rng, (2022, 2023, 2024, 2025, 2026, 2027))
    split(b, cov, [R.HOME_ML, R.HOME_DOG_SPREAD, R.H1_DOG_ML], rng, (2026, 2027))
    one_a_game(b, cov, [R.HOME_ML, R.HOME_DOG_SPREAD], rng, (2022, 2023, 2024, 2025, 2026, 2027),
               "the two full-game models, every season")
    one_a_game(b, cov, [R.HOME_ML, R.HOME_DOG_SPREAD, R.H1_DOG_ML], rng, (2026, 2027),
               "the three pre-game side models, 2025-26 on")
    if HT in side:
        one_a_game(b, cov, side, rng, (2026, 2027), "the four side models, 2025-26 on")
        live_rule(b, cov, rng)


if __name__ == "__main__":
    main()
