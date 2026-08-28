"""
Reconstruct a GameState time series from nflverse play-by-play.

This is the training-set builder AND the backtest replay source, so it is the
single place the state schema is defined for anything historical. The live
ESPN builder must match it field for field (tests/test_state_parity.py).

Three things here are load-bearing and easy to get wrong:

1. PRE-play scores. nflverse total_home_score / total_away_score are running
   totals AFTER the play; score_differential is BEFORE it. A bettor faces the
   pre-play state, so the running totals are shifted within each game. Reading
   them off the row directly would leak the very points we are predicting: a
   touchdown play would train the model on a state that already contains its
   own touchdown.

2. Targets are REMAINING points, measured from the pre-play score to the final
   score. `home_score` / `away_score` in nflverse are the game finals.

3. Regulation only, by default. Overtime is a different, sudden-death-shaped
   distribution and folding it into the regulation target teaches the model
   that trailing teams score fewer remaining points than they do. OT states are
   dropped from training; the engine prices in-OT games separately or not at
   all.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import PBP_DIR
from ..state import LEAGUE_PASS_RATE, PASS_RATE_PRIOR_PLAYS

# Columns pulled off the parquet. Kept explicit so a schema change upstream
# fails loudly at read time rather than silently producing a column of NaN.
PBP_COLS = [
    "game_id", "season", "week", "season_type",
    "home_team", "away_team", "posteam", "defteam",
    "qtr", "quarter_seconds_remaining", "game_seconds_remaining",
    "half_seconds_remaining", "game_half",
    "down", "ydstogo", "yardline_100",
    "total_home_score", "total_away_score",
    "home_timeouts_remaining", "away_timeouts_remaining",
    "spread_line", "total_line", "roof", "wind",
    "home_score", "away_score",
    "play_type", "pass", "rush", "penalty", "timeout",
    "desc", "time_of_day", "play_id",
]

# Play types that are scrimmage plays for pace purposes.
SCRIMMAGE = ("pass", "run", "qb_kneel", "qb_spike", "field_goal", "punt")


def load_pbp(seasons) -> pd.DataFrame:
    """Read the nflverse parquets for `seasons` and keep only what we use."""
    frames = []
    for season in seasons:
        path = PBP_DIR / f"play_by_play_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing. Run live_model/backtest/pull_pbp.py first."
            )
        df = pd.read_parquet(path, columns=PBP_COLS)
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def build_states(pbp: pd.DataFrame, *, regulation_only: bool = True) -> pd.DataFrame:
    """
    One row per play, carrying the PRE-play state plus both remaining-point
    targets. Rows are ordered as the game was played.
    """
    df = pbp.copy()

    # nflverse is already in play order within a game, but never rely on file
    # order for a shift(): sort explicitly on the clock.
    df = df.sort_values(
        ["game_id", "qtr", "game_seconds_remaining"],
        ascending=[True, True, False],
        kind="mergesort",
    ).reset_index(drop=True)

    g = df.groupby("game_id", sort=False)

    # --- 1. pre-play scores -------------------------------------------------
    df["home_score_pre"] = g["total_home_score"].shift(1).fillna(0.0)
    df["away_score_pre"] = g["total_away_score"].shift(1).fillna(0.0)

    # --- 2. pace and pass rate, cumulative and strictly pre-play ------------
    is_scrim = df["play_type"].isin(SCRIMMAGE)
    df["_scrim"] = is_scrim.astype(float)
    df["plays_run"] = g["_scrim"].cumsum() - df["_scrim"]

    home_has_ball = df["posteam"].eq(df["home_team"])
    is_pass = df["pass"].fillna(0).astype(float).gt(0)

    df["_h_play"] = (is_scrim & home_has_ball).astype(float)
    df["_a_play"] = (is_scrim & ~home_has_ball & df["posteam"].notna()).astype(float)
    df["_h_pass"] = (is_scrim & home_has_ball & is_pass).astype(float)
    df["_a_pass"] = (is_scrim & ~home_has_ball & df["posteam"].notna() & is_pass).astype(float)

    for col in ("_h_play", "_a_play", "_h_pass", "_a_pass"):
        df[col + "_cum"] = g[col].cumsum() - df[col]

    prior = LEAGUE_PASS_RATE * PASS_RATE_PRIOR_PLAYS
    df["home_pass_rate"] = (df["_h_pass_cum"] + prior) / (df["_h_play_cum"] + PASS_RATE_PRIOR_PLAYS)
    df["away_pass_rate"] = (df["_a_pass_cum"] + prior) / (df["_a_play_cum"] + PASS_RATE_PRIOR_PLAYS)

    # --- 3. targets ---------------------------------------------------------
    df["home_remaining_pts"] = df["home_score"] - df["home_score_pre"]
    df["away_remaining_pts"] = df["away_score"] - df["away_score_pre"]

    # --- 4. filters ---------------------------------------------------------
    keep = (
        df["qtr"].notna()
        & df["quarter_seconds_remaining"].notna()
        & df["home_score"].notna()
        & df["away_score"].notna()
        & df["spread_line"].notna()
        & df["total_line"].notna()
    )
    if regulation_only:
        keep &= df["qtr"].le(4)
    df = df[keep].copy()

    # A negative remaining-points target is impossible and means the shift or
    # the final score is wrong for that game. Drop rather than clip: a silent
    # clip would hide a real data bug.
    df = df[(df["home_remaining_pts"] >= 0) & (df["away_remaining_pts"] >= 0)]

    # Wall clock, so the backtest harness can align an odds snapshot to the
    # state that PRECEDED it. About 3% of plays carry no time_of_day, so it is
    # forward filled within the game: the missing rows are almost all
    # administrative markers between real plays, and the preceding play's
    # timestamp is the correct answer for them.
    # format="ISO8601" is LOAD BEARING. nflverse mixes "...T02:08:57Z" and
    # "...T02:10:13.383Z" in the same column, and pandas infers ONE format from
    # the first non-null value. With the default inference every fractional
    # second timestamp becomes NaT, gets forward filled from the last whole
    # second play, and whole stretches of a game collapse onto one instant. In
    # this repo that silently placed early third quarter plays BEFORE a
    # halftime odds snapshot, which is look-ahead bias in the single most
    # valuable lane the model has. Verified against 2024: 40% of timestamps
    # carry fractional seconds.
    df["wall_ts"] = pd.to_datetime(df["time_of_day"], errors="coerce",
                                   utc=True, format="ISO8601")
    # Fill only within a half, never across the halftime break: a 13 minute
    # gap with no plays must not be bridged by carrying a first half timestamp
    # onto a third quarter play.
    grp = df.groupby(["game_id", "game_half"], sort=False)["wall_ts"]
    df["wall_ts"] = grp.ffill()
    # Back fill the handful of rows BEFORE a game's first timestamp (the
    # opening administrative markers), so no state is left unalignable.
    df["wall_ts"] = df.groupby(["game_id", "game_half"], sort=False)["wall_ts"].bfill()
    # Any half with no usable timestamp at all falls back to the game level.
    df["wall_ts"] = df.groupby("game_id", sort=False)["wall_ts"].ffill()
    df["wall_ts"] = df.groupby("game_id", sort=False)["wall_ts"].bfill()
    df["wall_ts"] = _repair_day_offsets(df)

    # Score at halftime, carried on every row. Second half markets settle on
    # (final minus halftime), so without this the harness could price a 2H
    # total but never adjudicate it.
    first_half = df["qtr"].le(2)
    hh = df.assign(_h=np.where(first_half, df["total_home_score"], np.nan)) \
           .groupby("game_id", sort=False)["_h"].transform("max")
    ha = df.assign(_a=np.where(first_half, df["total_away_score"], np.nan)) \
           .groupby("game_id", sort=False)["_a"].transform("max")
    df["half_home_score"] = hh.fillna(0.0)
    df["half_away_score"] = ha.fillna(0.0)

    df["is_dome"] = df["roof"].isin(["dome", "closed"])
    # Our standard form: negative = home laying. nflverse is the reverse.
    df["pregame_spread"] = -df["spread_line"].astype(float)
    df["pregame_total"] = df["total_line"].astype(float)
    df["wind_mph"] = np.where(df["is_dome"], np.nan, df["wind"])

    df["seconds_remaining"] = (
        df["quarter_seconds_remaining"] + (4 - df["qtr"]) * 900
    ).clip(lower=0)

    drop = [c for c in df.columns if c.startswith("_")]
    return df.drop(columns=drop).reset_index(drop=True)


def _repair_day_offsets(df: pd.DataFrame) -> pd.Series:
    """
    Repair wrong DATE components in nflverse time_of_day.

    Measured on 2015-2025: 211 of 3,028 games contain at least one timestamp
    whose date is a full day off, producing a roughly 20 hour backstep in the
    middle of a quarter. Left alone this makes the play order and the wall
    clock disagree, and the backtest harness aligns odds snapshots on the wall
    clock, so a snapshot would be matched to a state from the wrong part of the
    game.

    The repair is deliberately narrow: only jumps backwards by more than six
    hours are treated as date errors, and only whole days are added. A genuine
    six hour gap inside one NFL game does not exist, and anything the repair
    cannot straighten out is caught by the monotonicity check afterwards rather
    than being quietly accepted.
    """
    ts = df["wall_ts"]
    out = ts.copy()
    for _, idx in df.groupby("game_id", sort=False).indices.items():
        vals = ts.iloc[idx]
        delta = vals.diff().dt.total_seconds()
        need = np.where(delta < -6 * 3600, np.ceil(-delta / 86400.0), 0.0)
        need = np.nan_to_num(need, nan=0.0)
        if need.any():
            out.iloc[idx] = vals + pd.to_timedelta(np.cumsum(need), unit="D")
    return out


def monotonicity_report(states: pd.DataFrame) -> dict:
    """
    How many games still have a wall clock that runs backwards.

    Exposed rather than asserted so a caller can decide: the harness drops
    these games, while the calibration gate does not care about wall clock at
    all and keeps them.
    """
    bad = [gid for gid, g in states.groupby("game_id", sort=False)
           if not g["wall_ts"].is_monotonic_increasing]
    return {"games": int(states["game_id"].nunique()),
            "non_monotone": len(bad), "game_ids": bad}


def sample_states(states: pd.DataFrame, every: int = 1, seed: int = 0) -> pd.DataFrame:
    """
    Thin the state series.

    Consecutive plays are near-duplicates, so training on every one of ~1.2M
    rows mostly buys correlated noise and a slow fit. Sampling every Nth play
    WITHIN a game preserves the full clock range while cutting the row count.
    """
    if every <= 1:
        return states
    out = states.groupby("game_id", sort=False, group_keys=False).apply(
        lambda d: d.iloc[::every], include_groups=True
    )
    return out.reset_index(drop=True)
