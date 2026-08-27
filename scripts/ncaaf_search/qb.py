"""
QB continuity and quality features (feature group C_qb).

WHAT THIS IS, AND WHAT IT IS NOT
--------------------------------
A backup quarterback moves a college line 4-7 points, and QB identity is the
one major CFB information channel this project had never ingested. But the
useful version of that signal -- "the starter is OUT this week" -- is NOT
available to us pre-kickoff: college football has no mandatory injury report,
availability leaks through beat writers hours before kickoff, and CFBD ships no
depth chart. Any feature claiming to know this week's starter would be reading
the box score of the game being predicted. That is leakage, and it would
backtest beautifully.

So these features describe QB CONTINUITY and QUALITY, strictly from completed
games:

    "who has been taking this team's snaps, how well, and did that just change"

The bettable hypothesis is second-order and genuinely testable: when a team
changes quarterbacks, the market re-rates it, and the question is whether it
re-rates ENOUGH over the following weeks. A team on its third starter is a
different team than its season-long ratings imply, and opponent-adjusted
efficiency -- which is what every other feature group measures -- averages the
old QB and the new one together as though they were the same offence.

THE STARTER PROXY
-----------------
`is_primary` (most pass attempts in a game) is the starter proxy, and the
"current" QB entering week W is the primary of that team's most recent
COMPLETED game. That is exactly what a bettor knows on Friday night, and no
more.

LEAK DISCIPLINE
---------------
Every value for game G of team T is computed only from that team's games with
`game_date < G.game_date`. A team's first ever game has no prior game, so every
column is NaN there -- deliberately, rather than imputed, so the model's dropna
sees the missingness. Prior seasons DO carry over (a returning starter's
experience is real information), which is why the lookback is by date rather
than reset per season.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# How many recent games define "recent form" for the current QB.
RECENT_GAMES = 3

QB_TEAM_COLS = [
    "qb_prior_starts",     # starts by the current QB, before this game
    "qb_changed",          # the primary QB changed between the last two games
    "qb_is_new",           # current QB has <= 1 prior start (market may lag)
    "qb_share_recent",     # share of recent attempts thrown by the current QB
    "qb_ypa_recent",       # current QB yards per attempt, recent games
    "qb_int_rate_recent",  # interceptions per attempt, recent games
    "qb_rush_ypg_recent",  # rushing yards per game -- dual-threat signal
]

QB_FEATURES = [f"d_{c}" for c in QB_TEAM_COLS] + ["qb_either_changed"]

# For these, a HIGHER raw value is WORSE for the team, so the home-minus-away
# diff is negated to keep "positive = good for home" consistent registry-wide.
_LOWER_IS_BETTER = {"qb_changed", "qb_is_new", "qb_int_rate_recent"}


def load_qb_games(conn=None, seasons: list[int] | None = None) -> pd.DataFrame:
    """Every passer-game, ordered. One row per (game, team, player)."""
    from data.db import get_connection

    own = conn is None
    conn = conn or get_connection()
    try:
        where = "WHERE season = ANY(%(seasons)s)" if seasons else ""
        rows = conn.execute(f"""
            SELECT game_id, team, season, week, game_date, player_id,
                   player_name, is_primary, attempts, completions,
                   pass_yards, pass_td, interceptions, rush_yards
            FROM ncaaf_qb_game
            {where}
            ORDER BY team, game_date, game_id
        """, {"seasons": seasons} if seasons else {}).fetchall()
    finally:
        if own:
            conn.close()

    df = pd.DataFrame(rows, columns=[
        "game_id", "team", "season", "week", "game_date", "player_id",
        "player_name", "is_primary", "attempts", "completions", "pass_yards",
        "pass_td", "interceptions", "rush_yards"])
    if df.empty:
        return df
    for c in ("attempts", "completions", "pass_yards", "pass_td",
              "interceptions", "rush_yards", "is_primary"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["game_date"] = pd.to_datetime(df["game_date"])
    return df


def build_qb_team_features(qb: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (game_id, team) with QB_TEAM_COLS, computed from that team's
    STRICTLY PRIOR games only.

    An explicit backward walk rather than a groupby/shift chain, because the
    "current QB" is defined by the previous game's primary and then every other
    column is conditioned on that identity -- not expressible as a column-wise
    shift, and subtly wrong in a way that would be invisible.
    """
    empty = pd.DataFrame(columns=["game_id", "team"] + QB_TEAM_COLS)
    if qb is None or qb.empty:
        return empty

    out = []
    for team, tdf in qb.groupby("team", sort=False):
        games = []
        for (gid, gdate), g in tdf.groupby(["game_id", "game_date"], sort=False):
            prim = g[g["is_primary"] == 1]
            games.append({
                "game_id": gid,
                "game_date": gdate,
                "primary_id": prim["player_id"].iloc[0] if len(prim) else None,
                "passers": g,
            })
        games.sort(key=lambda x: (x["game_date"], x["game_id"]))

        for i, cur in enumerate(games):
            prior = games[:i]                      # strictly before this game
            rec = {"game_id": cur["game_id"], "team": team}
            rec.update({c: np.nan for c in QB_TEAM_COLS})
            out.append(rec)
            if not prior:
                continue

            current_qb = prior[-1]["primary_id"]
            if current_qb is None:
                continue

            starts = sum(1 for p in prior if p["primary_id"] == current_qb)
            rec["qb_prior_starts"] = float(starts)
            rec["qb_is_new"] = float(starts <= 1)
            if len(prior) >= 2:
                rec["qb_changed"] = float(
                    prior[-1]["primary_id"] != prior[-2]["primary_id"])

            window = prior[-RECENT_GAMES:]
            att_all = sum(float(p["passers"]["attempts"].sum() or 0)
                          for p in window)
            mine = pd.concat(
                [p["passers"][p["passers"]["player_id"] == current_qb]
                 for p in window])
            att_mine = float(mine["attempts"].sum() or 0)
            if att_all > 0:
                rec["qb_share_recent"] = att_mine / att_all
            if att_mine > 0:
                rec["qb_ypa_recent"] = float(mine["pass_yards"].sum() or 0) / att_mine
                rec["qb_int_rate_recent"] = float(
                    mine["interceptions"].sum() or 0) / att_mine
            appearances = int((mine["attempts"].fillna(0) > 0).sum())
            if appearances:
                rec["qb_rush_ypg_recent"] = float(
                    mine["rush_yards"].sum() or 0) / appearances

    return pd.DataFrame(out)


def merge_qb_features(games: pd.DataFrame, qb_team: pd.DataFrame) -> pd.DataFrame:
    """
    Attach home/away QB columns to a game-level matrix and emit the diffs the
    model consumes. Sign convention: home minus away, positive = good for home.
    """
    if qb_team is None or qb_team.empty:
        for c in QB_FEATURES:
            games[c] = np.nan
        return games

    h = qb_team.rename(columns={"team": "home_team",
                                **{c: f"home_{c}" for c in QB_TEAM_COLS}})
    a = qb_team.rename(columns={"team": "away_team",
                                **{c: f"away_{c}" for c in QB_TEAM_COLS}})
    games = games.merge(h, on=["game_id", "home_team"], how="left")
    games = games.merge(a, on=["game_id", "away_team"], how="left")

    for c in QB_TEAM_COLS:
        diff = games[f"home_{c}"] - games[f"away_{c}"]
        games[f"d_{c}"] = -diff if c in _LOWER_IS_BETTER else diff

    # Either side changing QB is a disruption for the GAME, not for one team --
    # a totals-relevant signal that the home-minus-away diff cancels out.
    games["qb_either_changed"] = (
        games["home_qb_changed"].fillna(0) + games["away_qb_changed"].fillna(0)
    ).clip(upper=1.0)
    return games
