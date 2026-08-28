"""
Build the live-prop flow dataset: one row per (player, decision point).

TWO THINGS HERE ARE LOAD BEARING.

1. THE PREGAME BASELINE IS A STAND-IN FOR THE BOOK'S OPENING LINE, and it must
   be built from PRIOR GAMES ONLY. We hold no historical prop lines, so the
   baseline is the player's trailing per-game average, which is what a book's
   opener approximates. If it were computed over the whole season it would
   contain the game being predicted and every measured edge would be fiction.
   The trailing window is expanding within a season with a prior-season carry
   in, exactly the ASOF discipline the platform's other feature engines use.

   Because the baseline is a PROXY, it is weaker than a real opening line: a
   book knows about the injury report, the opponent, and the game plan. A model
   that beats a proxy anchor has not yet been shown to beat a real one. That
   caveat is stated wherever a result from this file is reported.

2. DECISION POINTS, not every play. A bettor looks at the board a handful of
   times, and consecutive plays are near duplicates that would inflate every
   sample size while adding almost no information. Rows are taken at fixed
   game-clock marks, which is both realistic and keeps the effective sample
   close to the number of player-games.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..engine.prop_flow import FLOW_MARKETS, naive_line
from .player_states import (
    build_player_states, load_pbp_players,
)

# Game seconds remaining at which a bettor would plausibly be looking. Includes
# halftime (1800), which is the window the whole package treats as most
# valuable: the market is open and no plays are being run.
DECISION_POINTS = (2700, 2100, 1800, 1500, 900, 600, 300)

# Minimum prior games before a player has a usable baseline. Below this a book
# would be pricing off projection rather than form, and so would we.
MIN_PRIOR_GAMES = 3

# A book does not hang a prop on everyone who touches the ball. It lists the
# starting quarterback, the one or two backs with real volume, and the three or
# four pass catchers who matter. Modelling the whole long tail is not a
# harmless superset: a fullback with one career carry has zero remaining
# production almost always, and enough of them drag the population's median to
# zero, which makes the anchor uncalibratable and the whole test meaningless.
#
# These floors are on the player's own trailing baseline and are set to the
# rough level at which a line actually appears on a board.
MIN_BASELINE = {
    "pass_yds": 150.0,
    "pass_att": 20.0,
    "pass_cmp": 12.0,
    "rush_yds": 25.0,
    "rush_att": 6.0,
    "rec_yds": 25.0,
    "receptions": 2.5,
}

# Accrued stats we carry. This is the market list PLUS targets, which is not a
# market but is the denominator of a receiver's usage share.
ACCRUAL_STATS = sorted(set(FLOW_MARKETS.values()) | {"targets"})


def _season_totals(player_states: pd.DataFrame) -> pd.DataFrame:
    """Final per-player per-game totals for every stat."""
    stat_cols = [f"rem_{s}" for s in FLOW_MARKETS.values()]
    acc_cols = [f"acc_{s}" for s in FLOW_MARKETS.values()]
    first = player_states.sort_values(
        ["game_id", "player_id", "seconds_remaining"],
        ascending=[True, True, False], kind="mergesort"
    ).groupby(["game_id", "player_id"], sort=False).first().reset_index()
    out = first[["game_id", "player_id", "season", "team_side"]].copy()
    for stat, a, r in zip(FLOW_MARKETS.values(), acc_cols, stat_cols):
        out[f"total_{stat}"] = first[a] + first[r]
    return out


def build_baselines(totals: pd.DataFrame) -> pd.DataFrame:
    """
    Expanding per-player trailing average, STRICTLY prior games.

    Game order within a season comes from the game_id, whose nflverse form is
    `{season}_{week:02d}_{away}_{home}`, so a lexical sort is a chronological
    one.
    """
    t = totals.sort_values(["player_id", "season", "game_id"],
                           kind="mergesort").reset_index(drop=True)
    g = t.groupby("player_id", sort=False)
    t["prior_games"] = g.cumcount()
    # LEAVE-ONE-OUT SEASON AVERAGE: an upper bound on how good a book's own
    # opening number could be. It uses the player's whole season EXCEPT the
    # game in question, so it knows his true role far better than a trailing
    # average does, which is exactly the advantage a real book's opener has
    # (depth chart, injury report, matchup). It is not available in real time
    # and is never a model feature. It exists only to answer one question: is a
    # measured edge about in-game flow, or merely about our proxy baseline
    # being noisier than a book's?
    for stat in ACCRUAL_STATS:
        col = f"total_{stat}"
        gs = t.groupby(["player_id", "season"], sort=False)[col]
        n = gs.transform("size")
        tot = gs.transform("sum")
        t[f"oracle_{stat}"] = np.where(n > 1, (tot - t[col]) / (n - 1), np.nan)

    for stat in ACCRUAL_STATS:
        col = f"total_{stat}"
        # shift(1) BEFORE the expanding mean is what makes this leak free: the
        # baseline for game N is the average of games 1..N-1 and never includes N.
        t[f"baseline_{stat}"] = (
            g[col].apply(lambda s: s.shift(1).expanding().mean())
            .reset_index(level=0, drop=True))
    return t


def accrual_at(long: pd.DataFrame, mark: int) -> pd.DataFrame:
    """
    Every player's accrued production AS OF `mark` seconds remaining.

    THIS IS AN AS-OF SUM, NOT A SNAP TO THE PLAYER'S LAST ROW. Taking the last
    row in which a player appears before the mark is subtly wrong and badly so:
    a receiver whose final target came in the second quarter has no row near
    the two minute warning, so his "last row before the mark" carries a second
    quarter accrual while its remaining-production target still counts
    everything from the second quarter onward. Production that had already
    happened gets labelled as production still to come.

    Measured, that bug made a receiver look like he still had a THIRD of his
    game total left with five minutes to play, and it was inflating the target
    for every late decision point in the dataset.
    """
    stat_cols = ACCRUAL_STATS
    before = long[long["seconds_remaining"] >= mark]
    acc = (before.groupby(["game_id", "player_id"], sort=False)[stat_cols]
           .sum().reset_index())
    acc.columns = ["game_id", "player_id"] + [f"acc_{c}" for c in stat_cols]
    return acc


def team_context_at(pbp: pd.DataFrame, mark: int) -> pd.DataFrame:
    """Team play count and pass rate as of the mark, per (game, team)."""
    scrim = pbp[pbp["play_type"].isin(("pass", "run", "qb_kneel", "qb_spike"))
                & pbp["posteam"].notna()
                & (pbp["seconds_remaining"] >= mark)]
    if scrim.empty:
        return pd.DataFrame(columns=["game_id", "posteam", "team_plays_so_far",
                                     "team_pass_rate_obs"])
    g = scrim.groupby(["game_id", "posteam"], sort=False)
    out = g.size().rename("team_plays_so_far").reset_index()
    passes = g["pass_attempt"].sum().rename("team_pass").reset_index()
    out = out.merge(passes, on=["game_id", "posteam"], how="left")
    # Shrink toward the league rate so a five play sample does not report a
    # 100% pass offence.
    out["team_pass_rate_obs"] = (
        (out["team_pass"].fillna(0) + 0.575 * 20.0)
        / (out["team_plays_so_far"] + 20.0))
    return out.drop(columns=["team_pass"])


def build_flow_rows(seasons, decision_points=DECISION_POINTS) -> pd.DataFrame:
    """
    The modelling frame: one row per (player, market, decision point).

    Long in market so a single model per market can be fitted from one build.
    Every quantity is computed AS OF the decision point.
    """
    from ..config import ARTIFACT_DIR
    from .player_states import _long_contributions, PBP_PLAYER_COLS

    game_states = pd.read_parquet(ARTIFACT_DIR / "states_all.parquet")
    game_states = game_states[game_states.season.isin(seasons)]

    pbp = load_pbp_players(seasons)
    pbp = pbp[pbp["qtr"].le(4) & pbp["quarter_seconds_remaining"].notna()].copy()
    pbp["seconds_remaining"] = (
        pbp["quarter_seconds_remaining"] + (4 - pbp["qtr"]) * 900).clip(lower=0)

    long = _long_contributions(pbp)
    if long.empty:
        return long
    long = long.merge(
        pbp[["game_id", "play_id", "season", "seconds_remaining"]],
        on=["game_id", "play_id"], how="left")

    stat_cols = ACCRUAL_STATS
    totals = (long.groupby(["game_id", "player_id"], sort=False)
              .agg(**{f"total_{c}": (c, "sum") for c in stat_cols},
                   season=("season", "first"),
                   team_side=("team_side", "first")).reset_index())
    baselines = build_baselines(totals)

    ctx_cols = ["game_id", "home_score_pre", "away_score_pre", "pregame_total",
                "pregame_spread", "wind_mph", "is_dome", "seconds_remaining",
                "qtr"]
    gs = game_states[ctx_cols].sort_values(
        ["game_id", "seconds_remaining"], ascending=[True, False],
        kind="mergesort")

    frames = []
    for mark in decision_points:
        acc = accrual_at(long, mark)
        if acc.empty:
            continue
        acc["decision_point"] = mark

        game_ctx = gs[gs["seconds_remaining"] >= mark] \
            .groupby("game_id", sort=False).last().reset_index()
        team_ctx = team_context_at(pbp, mark)

        d = acc.merge(
            baselines[["game_id", "player_id", "season", "team_side",
                       "prior_games"]
                      + [f"baseline_{c}" for c in stat_cols]
                      + [f"oracle_{c}" for c in stat_cols]
                      + [f"total_{c}" for c in stat_cols]],
            on=["game_id", "player_id"], how="inner")
        d = d.merge(game_ctx.drop(columns=["seconds_remaining"]),
                    on="game_id", how="inner")
        d["posteam_key"] = d["team_side"]
        # Resolve the player's team abbreviation so team context joins.
        team_map = (long.groupby(["game_id", "player_id"], sort=False)
                    .agg(team_side=("team_side", "first")).reset_index())
        d = d.merge(team_map, on=["game_id", "player_id"], how="left",
                    suffixes=("", "_dup"))
        frames.append((d, team_ctx, mark))

    if not frames:
        return pd.DataFrame()

    # Team context is keyed on the abbreviation; map home/away to it once.
    side_map = game_states.groupby("game_id").first()[
        ["home_team", "away_team"]].reset_index()

    rows = []
    for d, team_ctx, mark in frames:
        d = d.merge(side_map, on="game_id", how="left")
        d["team_abbrev"] = np.where(d["team_side"] == "home",
                                    d["home_team"], d["away_team"])
        d = d.merge(team_ctx.rename(columns={"posteam": "team_abbrev"}),
                    on=["game_id", "team_abbrev"], how="left")
        d["team_plays_so_far"] = d["team_plays_so_far"].fillna(0.0)
        d["team_pass_rate"] = d["team_pass_rate_obs"].fillna(0.575)
        d["decision_point"] = mark
        d["seconds_remaining"] = float(mark)
        rows.append(d)
    rows = pd.concat(rows, ignore_index=True)

    rows["frac_remaining"] = (rows["decision_point"] / 3600.0).clip(0, 1)
    rows["team_margin"] = np.where(
        rows["team_side"] == "home",
        rows["home_score_pre"] - rows["away_score_pre"],
        rows["away_score_pre"] - rows["home_score_pre"])
    rows["pregame_spread_team"] = np.where(
        rows["team_side"] == "home", rows["pregame_spread"], -rows["pregame_spread"])

    out = []
    for market, stat in FLOW_MARKETS.items():
        d = rows.copy()
        d["market"] = market
        d["accrued"] = d[f"acc_{stat}"].astype(float)
        d["season_total"] = d[f"total_{stat}"].astype(float)
        d["actual_remaining"] = (d["season_total"] - d["accrued"]).clip(lower=0)
        d["baseline_per_game"] = d[f"baseline_{stat}"].astype(float)
        d["oracle_per_game"] = d[f"oracle_{stat}"].astype(float)
        d["usage_share"] = _usage_share_for(d, market)
        out.append(d[[
            "game_id", "player_id", "season", "market", "decision_point",
            "team_side", "qtr", "seconds_remaining", "frac_remaining",
            "accrued", "actual_remaining", "baseline_per_game", "prior_games",
            "team_margin", "team_pass_rate", "team_plays_so_far", "usage_share",
            "pregame_total", "pregame_spread_team", "wind_mph", "is_dome",
            "season_total", "oracle_per_game",
        ]])
    flow = pd.concat(out, ignore_index=True)

    flow = flow[
        flow["baseline_per_game"].notna()
        & (flow["prior_games"] >= MIN_PRIOR_GAMES)
        & flow["actual_remaining"].notna()
    ].copy()
    floors = flow["market"].map({m: MIN_BASELINE[s] for m, s in FLOW_MARKETS.items()})
    flow = flow[flow["baseline_per_game"] >= floors].copy()
    flow["actual_final"] = flow["accrued"] + flow["actual_remaining"]
    return flow.reset_index(drop=True)


def _usage_share_for(d: pd.DataFrame, market: str) -> np.ndarray:
    plays = d["team_plays_so_far"].clip(lower=1.0)
    rate = d["team_pass_rate"].astype(float)
    if market.startswith("player_pass"):
        return np.where(d["acc_pass_att"] > 0, 1.0, 0.0)
    if market.startswith("player_rush"):
        return np.clip(d["acc_rush_att"] / np.maximum(plays * (1 - rate), 1.0), 0, 1)
    return np.clip(d["acc_targets"] / np.maximum(plays * rate, 1.0), 0, 1)


def _game_context(game_states: pd.DataFrame, decision_points) -> pd.DataFrame:
    keep = ["game_id", "home_score_pre", "away_score_pre", "home_pass_rate",
            "away_pass_rate", "pregame_total", "pregame_spread", "wind_mph",
            "is_dome", "seconds_remaining"]
    gs = game_states[keep].sort_values(["game_id", "seconds_remaining"],
                                       ascending=[True, False], kind="mergesort")
    frames = []
    for mark in decision_points:
        at = gs[gs["seconds_remaining"] >= mark]
        if at.empty:
            continue
        snap = at.groupby("game_id", sort=False).last().reset_index()
        snap["decision_point"] = mark
        frames.append(snap.drop(columns=["seconds_remaining"]))
    return pd.concat(frames, ignore_index=True)
