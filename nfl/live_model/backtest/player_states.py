"""
Reconstruct PlayerState time series and remaining-production targets from pbp.

The prop analogue of backtest/states.py, and it exists for the same reason:
without it the prop engine is unfalsifiable. The unit tests in
tests/test_props.py check that the game-script mechanism responds in the right
DIRECTION, which is necessary and nowhere near sufficient. A prop price is a
tail question, and a distribution can have the right mean and badly wrong tails.

SAME DISCIPLINE AS THE SCORE MODEL:
  * Accrued production is strictly PRE-play. A receiving-yards row must not
    contain the catch it is being asked to predict.
  * Targets are REMAINING production, measured from the pre-play accrual to the
    player's final line.
  * Regulation only, matching the score engine.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Per-play contributions, keyed by which id column owns them.
PASSER_COLS = {
    "pass_att": "pass_attempt", "pass_cmp": "complete_pass",
    "pass_yds": "passing_yards", "pass_tds": "pass_touchdown",
}
RUSHER_COLS = {"rush_att": "rush_attempt", "rush_yds": "rushing_yards"}
RECEIVER_COLS = {"receptions": "complete_pass", "rec_yds": "receiving_yards"}

STAT_COLS = ["pass_att", "pass_cmp", "pass_yds", "pass_tds",
             "rush_att", "rush_yds", "targets", "receptions", "rec_yds"]

# Which accrued stat each market settles on.
MARKET_STAT = {
    "player_pass_yds": "pass_yds",
    "player_pass_attempts": "pass_att",
    "player_pass_completions": "pass_cmp",
    "player_pass_tds": "pass_tds",
    "player_rush_yds": "rush_yds",
    "player_rush_attempts": "rush_att",
    "player_reception_yds": "rec_yds",
    "player_receptions": "receptions",
}

PBP_PLAYER_COLS = [
    "game_id", "season", "play_id", "qtr", "quarter_seconds_remaining",
    "game_seconds_remaining", "posteam", "home_team", "away_team",
    "passer_player_id", "rusher_player_id", "receiver_player_id",
    "passing_yards", "rushing_yards", "receiving_yards",
    "pass_attempt", "rush_attempt", "complete_pass",
    "pass_touchdown", "rush_touchdown", "play_type",
]


def load_pbp_players(seasons) -> pd.DataFrame:
    """
    Read the pbp parquets with the PLAYER columns.

    Separate from backtest.states.load_pbp because the two need disjoint column
    sets and reading the union of them roughly doubles the memory footprint of
    an eleven season load for no benefit.
    """
    from ..config import PBP_DIR
    frames = []
    for season in seasons:
        path = PBP_DIR / f"play_by_play_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing. Run live_model/backtest/pull_pbp.py first.")
        frames.append(pd.read_parquet(path, columns=PBP_PLAYER_COLS))
    return pd.concat(frames, ignore_index=True)


def _long_contributions(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per (play, player) with that play's contribution to each stat."""
    frames = []
    specs = [
        ("passer_player_id", PASSER_COLS, None),
        ("rusher_player_id", RUSHER_COLS, None),
        # A target is any play where the player is named as the receiver,
        # completed or not. nflverse has no explicit target column, so it is
        # derived here rather than left absent: target share is the single
        # most load bearing input to a receiving prop.
        ("receiver_player_id", RECEIVER_COLS, "targets"),
    ]
    for id_col, mapping, extra in specs:
        sub = pbp[pbp[id_col].notna()].copy()
        if sub.empty:
            continue
        out = pd.DataFrame({
            "game_id": sub["game_id"].to_numpy(),
            "play_id": sub["play_id"].to_numpy(),
            "player_id": sub[id_col].to_numpy(),
        })
        for stat in STAT_COLS:
            out[stat] = 0.0
        for stat, src in mapping.items():
            out[stat] = pd.to_numeric(sub[src], errors="coerce").fillna(0.0).to_numpy()
        if extra:
            out[extra] = 1.0
        out["team_side"] = np.where(
            sub["posteam"].to_numpy() == sub["home_team"].to_numpy(),
            "home", "away")
        frames.append(out)
    if not frames:
        return pd.DataFrame(columns=["game_id", "play_id", "player_id"] + STAT_COLS)
    return pd.concat(frames, ignore_index=True)


def build_player_states(pbp: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (play, player involved) with PRE-play accruals and remaining
    production targets, joined to the game clock.
    """
    df = pbp[PBP_PLAYER_COLS].copy()
    df = df[df["qtr"].le(4) & df["quarter_seconds_remaining"].notna()]
    df["seconds_remaining"] = (
        df["quarter_seconds_remaining"] + (4 - df["qtr"]) * 900).clip(lower=0)

    long = _long_contributions(df)
    if long.empty:
        return long

    clock = df[["game_id", "play_id", "season", "qtr",
                "quarter_seconds_remaining", "seconds_remaining"]]
    long = long.merge(clock, on=["game_id", "play_id"], how="left")

    # Play order within a game. Sorting on the clock rather than play_id keeps
    # this consistent with backtest/states.py.
    long = long.sort_values(
        ["game_id", "player_id", "qtr", "seconds_remaining"],
        ascending=[True, True, True, False], kind="mergesort").reset_index(drop=True)

    g = long.groupby(["game_id", "player_id"], sort=False)
    for stat in STAT_COLS:
        cum = g[stat].cumsum()
        # PRE-play accrual: the running total MINUS this play's contribution.
        long[f"acc_{stat}"] = cum - long[stat]
        total = g[stat].transform("sum")
        long[f"rem_{stat}"] = total - long[f"acc_{stat}"]

    # Plays run so far by the PLAYER'S OWN OFFENCE. This is the denominator of
    # every usage share, so getting it wrong scales every rushing and receiving
    # projection by a constant factor. Counting plays per GAME rather than per
    # TEAM inflates it by roughly two, which understated rushing yards by 20%
    # and receiving yards by 38% the first time this gate was run.
    scrim = df[df["play_type"].isin(("pass", "run", "qb_kneel", "qb_spike"))
               & df["posteam"].notna()]
    counts = (scrim.sort_values(["game_id", "qtr", "seconds_remaining"],
                                ascending=[True, True, False], kind="mergesort")
              .assign(one=1.0))
    counts["team_plays_so_far"] = (
        counts.groupby(["game_id", "posteam"], sort=False)["one"].cumsum() - 1.0)
    long = long.merge(counts[["game_id", "play_id", "team_plays_so_far"]],
                      on=["game_id", "play_id"], how="left")
    # Forward fill WITHIN the player's own series, not across players: a
    # global ffill would hand a receiver the running count of whichever play
    # happened to precede his in the frame.
    long["team_plays_so_far"] = (
        long.groupby(["game_id", "player_id"], sort=False)["team_plays_so_far"]
        .ffill().fillna(0.0))
    return long


def attach_game_context(player_states: pd.DataFrame,
                        game_states: pd.DataFrame) -> pd.DataFrame:
    """
    Join each player row to the game state on the same play.

    The prop engine needs the score and the clock, which live on the game state
    frame. Joining on play_id rather than re-deriving them keeps a single
    definition of the state the model sees.
    """
    ctx = game_states[[
        "game_id", "play_id", "home_score_pre", "away_score_pre",
        "home_timeouts_remaining", "away_timeouts_remaining",
        "pregame_spread", "pregame_total", "wind_mph", "is_dome",
        "plays_run", "home_pass_rate", "away_pass_rate",
    ]].copy() if "play_id" in game_states.columns else None
    if ctx is None:
        raise KeyError(
            "game_states must carry play_id to join player rows. Add it to "
            "backtest.states.PBP_COLS."
        )
    return player_states.merge(ctx, on=["game_id", "play_id"], how="inner")
