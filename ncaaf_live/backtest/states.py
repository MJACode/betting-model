"""
Reconstruct a GameState time series from CFBD play-by-play.

The training-set builder AND the future backtest replay source, so this is the
single place the state schema is defined for anything historical - the same
role nfl/live_model/backtest/states.py plays for the NFL, and its three
load-bearing lessons carry over directly:

1. PRE-play scores. A bettor faces the state BEFORE the play runs. CFBD does
   not document whether offenseScore/defenseScore are pre- or post-play, so
   `_detect_score_convention` measures it from the scoring plays themselves
   and the builder ASSERTS a clear verdict instead of assuming one. Getting
   this wrong trains the model on states that already contain the touchdown
   being predicted.

2. Targets are REMAINING points: platform-final minus pre-play score. Finals
   come from the platform `games` table, never from the last play row - the
   last play's running score misses end-of-game administrative rows and
   inherits whatever the pre/post convention is.

3. Regulation only. CFB overtime is alternating untimed possessions from the
   opponent 25 - even less regulation-shaped than the NFL's sudden death.
   OT states (period >= 5) are dropped from training and the engine declines
   to price in-OT games.

CFBD-specific relabelling this file owns (and nothing else does):
  * offense/defense-relative -> home/away, via offense == home
  * clock counts DOWN within a 900-second period
  * pass/rush/scrimmage derived from playType strings (no booleans upstream)
  * pregame lines, finals and weather joined from the PLATFORM tables on
    (season, season_type, week, home, away) - school names are shared with
    CFBD on both sides, so the join is exact, and the lines are the same
    archive-provider-priority numbers every pregame model trains on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live.config import (  # noqa: E402
    ALL_SEASONS, LEAGUE_PASS_RATE, LEAGUE_PLAYS_PER_GAME,
    PASS_RATE_PRIOR_PLAYS, PBP_DIR)

# ── playType classification ──────────────────────────────────────────────────
# CFBD ships a free-text playType. Substring classes rather than an exact list
# so a new variant ("Pass Reception 2pt" etc.) lands in the right bucket, and
# unknown ACTIVE types are reported by classify_report rather than silently
# treated as dead ball.
_PASS_TOKENS = ("pass", "sack", "interception")
_RUSH_TOKENS = ("rush", "run")
_DEAD_TOKENS = ("kickoff", "timeout", "end period", "end of", "penalty",
                "uncategorized", "placeholder", "coin toss", "start of")
_SCRIM_EXTRA = ("punt", "field goal", "blocked", "fumble")


def _classify(play_type: pd.Series) -> pd.DataFrame:
    pt = play_type.fillna("").str.lower()
    is_pass = pt.str.contains("|".join(_PASS_TOKENS))
    is_rush = ~is_pass & pt.str.contains("|".join(_RUSH_TOKENS))
    is_dead = pt.str.contains("|".join(_DEAD_TOKENS))
    is_scrim = (is_pass | is_rush |
                pt.str.contains("|".join(_SCRIM_EXTRA))) & ~is_dead
    return pd.DataFrame({"is_pass": is_pass, "is_rush": is_rush,
                         "is_scrim": is_scrim})



# THE play-order key. CFBD playNumber is a PER-DRIVE counter (max ~13 in a
# 174-play game), so sorting a game by it alone scrambles the play sequence -
# which is exactly the kind of silent corruption the score-convention gate
# exists to catch (it read 82% under the scrambled order, 99.0% under this
# one, measured across 2016/2019/2024).
_ORDER_COLS = ["gameId", "_drive_ord", "playNumber"]


def _with_order(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["_drive_ord"] = pd.to_numeric(out["driveId"], errors="coerce")
    return out


def load_pbp(seasons=ALL_SEASONS) -> pd.DataFrame:
    frames = []
    for season in seasons:
        path = PBP_DIR / f"plays_{season}.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"{path} missing - run ncaaf_live.backtest.pull_pbp first")
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def load_platform_games(conn=None) -> pd.DataFrame:
    """
    One row per platform NCAAF game: finals, pregame archive lines (the same
    provider-priority numbers the pregame models use), and weather.
    """
    from data.db import get_connection
    import config as platform_config

    owned = conn is None
    conn = conn or get_connection()
    try:
        priority = list(platform_config.NCAAF_LINE_BOOKMAKER_PRIORITY)
        in_ph = ",".join(["%s"] * len(priority))
        case_ph = " ".join(f"WHEN %s THEN {i}" for i in range(len(priority)))
        rows = conn.execute(f"""
            SELECT g.game_id, g.season, g.week, g.game_date,
                   g.home_team, g.away_team, g.home_score, g.away_score,
                   sp.spread_home, tl.total_line,
                   w.wind_mph, w.is_dome_game
            FROM games g
            LEFT JOIN LATERAL (
                SELECT o.spread_home FROM odds o
                WHERE o.game_id = g.game_id AND o.market = 'spreads'
                  AND o.spread_home IS NOT NULL
                  AND o.bookmaker IN ({in_ph})
                  AND o.snapshot_type != 'in_play'
                ORDER BY CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                         o.snapshot_at ASC
                LIMIT 1
            ) sp ON TRUE
            LEFT JOIN LATERAL (
                SELECT o.total_line FROM odds o
                WHERE o.game_id = g.game_id AND o.market = 'totals'
                  AND o.total_line IS NOT NULL
                  AND o.bookmaker IN ({in_ph})
                  AND o.snapshot_type != 'in_play'
                ORDER BY CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                         o.snapshot_at ASC
                LIMIT 1
            ) tl ON TRUE
            LEFT JOIN game_weather w ON w.game_id = g.game_id
            WHERE g.sport = 'NCAAF' AND g.home_score IS NOT NULL
        """, priority * 4).fetchall()
    finally:
        if owned:
            conn.close()

    df = pd.DataFrame(rows, columns=[
        "game_id", "season", "week", "game_date", "home_team", "away_team",
        "final_home", "final_away", "pregame_spread", "pregame_total",
        "wind_mph", "is_dome"])
    for c in ("final_home", "final_away", "pregame_spread", "pregame_total",
              "wind_mph", "season", "week"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["is_dome"] = pd.to_numeric(df["is_dome"], errors="coerce").fillna(0) == 1
    return df


def _detect_score_convention(df: pd.DataFrame) -> str:
    """
    'post' if offenseScore/defenseScore already include the play's points,
    'pre' if they are the score the play started from.

    Measured on scoring plays: under a POST convention the score visibly
    changes ON the scoring row (vs the previous row); under PRE it changes on
    the row AFTER. The builder requires a >90% majority - an ambiguous answer
    means the feed changed shape and everything downstream would be wrong.
    """
    d = _with_order(df).sort_values(_ORDER_COLS, kind="mergesort")
    g = d.groupby("gameId", sort=False)
    total = d["home_pts_raw"] + d["away_pts_raw"]
    prev_total = g["home_pts_raw"].shift(1).fillna(0) + \
        g["away_pts_raw"].shift(1).fillna(0)
    scoring = d["scoring"].fillna(False).astype(bool)
    # administrative rows can repeat a score; require real scoring plays
    changed_on_row = (total > prev_total) & scoring
    if not scoring.any():
        # With zero scoring plays the two conventions are literally identical
        # (shifting a constant-zero score changes nothing), so either answer
        # is correct. "post" keeps the shift path exercised.
        return "post"
    frac_post = changed_on_row[scoring].mean()
    if frac_post >= 0.90:
        return "post"
    if frac_post <= 0.10:
        return "pre"
    raise AssertionError(
        f"score convention ambiguous: {frac_post:.1%} of scoring plays change "
        "their own row - the CFBD feed shape has drifted, refusing to build")


def build_states(pbp: pd.DataFrame, platform: pd.DataFrame,
                 *, regulation_only: bool = True) -> pd.DataFrame:
    """One row per play: PRE-play state + both remaining-points targets."""
    df = pbp.copy()

    # ── home/away relabelling ────────────────────────────────────────────────
    has_ball_home = df["offense"].eq(df["home"])
    df["has_ball_home"] = has_ball_home.astype(float)
    df["home_pts_raw"] = np.where(has_ball_home, df["offenseScore"],
                                  df["defenseScore"]).astype(float)
    df["away_pts_raw"] = np.where(has_ball_home, df["defenseScore"],
                                  df["offenseScore"]).astype(float)
    df["home_timeouts"] = pd.to_numeric(
        np.where(has_ball_home, df["offenseTimeouts"], df["defenseTimeouts"]),
        errors="coerce")
    df["away_timeouts"] = pd.to_numeric(
        np.where(has_ball_home, df["defenseTimeouts"], df["offenseTimeouts"]),
        errors="coerce")

    # ── clock ────────────────────────────────────────────────────────────────
    df["period"] = pd.to_numeric(df["period"], errors="coerce")
    clock_in_period = (pd.to_numeric(df["clock_minutes"], errors="coerce") * 60
                       + pd.to_numeric(df["clock_seconds"], errors="coerce"))
    df["clock_in_period"] = clock_in_period.clip(0, 900)
    df["seconds_remaining"] = (
        df["clock_in_period"] + (4 - df["period"]).clip(lower=0) * 900
    ).clip(lower=0)
    df["half_seconds_remaining"] = np.where(
        df["period"] <= 2,
        df["clock_in_period"] + (2 - df["period"]).clip(lower=0) * 900,
        np.where(df["period"] <= 4,
                 df["clock_in_period"] + (4 - df["period"]).clip(lower=0) * 900,
                 0.0))

    # ── order + pre-play scores ──────────────────────────────────────────────
    df = _with_order(df).sort_values(_ORDER_COLS, kind="mergesort") \
           .reset_index(drop=True)
    convention = _detect_score_convention(df)
    g = df.groupby("gameId", sort=False)
    if convention == "post":
        df["home_score"] = g["home_pts_raw"].shift(1).fillna(0.0)
        df["away_score"] = g["away_pts_raw"].shift(1).fillna(0.0)
    else:
        df["home_score"] = df["home_pts_raw"]
        df["away_score"] = df["away_pts_raw"]

    # ── pace + pass rate, cumulative and strictly pre-play ──────────────────
    cls = _classify(df["playType"])
    df["_scrim"] = cls["is_scrim"].astype(float)
    df["plays_run"] = g["_scrim"].cumsum() - df["_scrim"]

    hb = has_ball_home & cls["is_scrim"]
    ab = ~has_ball_home & cls["is_scrim"] & df["offense"].notna()
    df["_h_play"] = hb.astype(float)
    df["_a_play"] = ab.astype(float)
    df["_h_pass"] = (hb & cls["is_pass"]).astype(float)
    df["_a_pass"] = (ab & cls["is_pass"]).astype(float)
    for col in ("_h_play", "_a_play", "_h_pass", "_a_pass"):
        df[col + "_cum"] = g[col].cumsum() - df[col]

    prior = LEAGUE_PASS_RATE * PASS_RATE_PRIOR_PLAYS
    df["home_pass_rate"] = (df["_h_pass_cum"] + prior) / \
        (df["_h_play_cum"] + PASS_RATE_PRIOR_PLAYS)
    df["away_pass_rate"] = (df["_a_pass_cum"] + prior) / \
        (df["_a_play_cum"] + PASS_RATE_PRIOR_PLAYS)

    # ── join the platform: finals, pregame lines, weather ───────────────────
    # Key = (season, home, away) disambiguated by DATE: each pbp game carries
    # play wallclocks, and the platform row whose game_date is nearest (within
    # 2 days) wins. A (season, week) key would collide on a week-1 rematch in
    # a bowl (postseason weeks restart at 1), and games has no season_type
    # column to break the tie.
    wall = pd.to_datetime(df["wallclock"], errors="coerce", utc=True,
                          format="ISO8601")
    game_date_pbp = wall.dt.normalize().groupby(df["gameId"]).transform("min")
    df["_pbp_date"] = game_date_pbp

    plat = platform.rename(columns={"home_team": "home", "away_team": "away"}).copy()
    plat["_plat_date"] = pd.to_datetime(plat["game_date"], errors="coerce",
                                        utc=True)
    plat = plat.drop(columns=["game_date", "week"])

    df = df.merge(plat, on=["season", "home", "away"], how="left")
    # keep only the nearest-dated platform row per pbp game; the rest are the
    # rematch rows the merge fanned out
    gap = (df["_plat_date"] - df["_pbp_date"]).abs()
    df["_gap"] = gap.dt.total_seconds()
    df.loc[df["_gap"] > 2 * 86400, ["final_home", "final_away",
                                    "pregame_spread", "pregame_total"]] = np.nan
    # Dedupe key is the PLAY ID - the only per-play-unique column. playNumber
    # is a per-drive counter, so deduping on it collapsed 172-play games to 23
    # rows (the bug this comment memorialises); the canonical sort is
    # _ORDER_COLS, never bare playNumber.
    df = df.sort_values(_ORDER_COLS + ["_gap"], kind="mergesort")
    df = df.drop_duplicates(subset=["gameId", "id"], keep="first")
    df = df.sort_values(_ORDER_COLS, kind="mergesort").reset_index(drop=True)

    # ── targets (platform finals minus PRE-play score) ──────────────────────
    df["home_remaining_pts"] = df["final_home"] - df["home_score"]
    df["away_remaining_pts"] = df["final_away"] - df["away_score"]

    # ── situation ────────────────────────────────────────────────────────────
    df["down"] = pd.to_numeric(df["down"], errors="coerce")
    df["distance"] = pd.to_numeric(df["distance"], errors="coerce")
    # yardsToGoal is the OFFENSE's distance to the opponent goal line - the
    # exact meaning of the NFL's yardline_100
    df["yardline_100"] = pd.to_numeric(df["yardsToGoal"], errors="coerce")

    # ── wall clock, for snapshot alignment in the harness ───────────────────
    # CFBD wallclock is ISO with mixed fractional seconds - the exact pandas
    # inference trap the NFL build hit (15% of rows silently NaT). Explicit
    # format, then the same narrow day-offset repair.
    df["wall_ts"] = pd.to_datetime(df["wallclock"], errors="coerce",
                                   utc=True, format="ISO8601")
    df["game_half"] = np.where(df["period"] <= 2, "h1", "h2")
    for grp_cols in (["gameId", "game_half"], ["gameId"]):
        grp = df.groupby(grp_cols, sort=False)["wall_ts"]
        df["wall_ts"] = grp.ffill()
        df["wall_ts"] = df.groupby(grp_cols, sort=False)["wall_ts"].bfill()
    df["wall_ts"] = _repair_day_offsets(df)

    # ── halftime scores, for 2H settlement ──────────────────────────────────
    # max of the POST-play score over first-half rows == the halftime score
    fh_h = np.where(df["period"] <= 2, df["home_pts_raw"], np.nan)
    fh_a = np.where(df["period"] <= 2, df["away_pts_raw"], np.nan)
    df["half_home_score"] = df.assign(_x=fh_h).groupby(
        "gameId", sort=False)["_x"].transform("max").fillna(0.0)
    df["half_away_score"] = df.assign(_x=fh_a).groupby(
        "gameId", sort=False)["_x"].transform("max").fillna(0.0)

    # ── filters ──────────────────────────────────────────────────────────────
    keep = (
        df["period"].notna()
        & df["clock_in_period"].notna()
        & df["final_home"].notna()
        & df["final_away"].notna()
        & df["pregame_spread"].notna()
        & df["pregame_total"].notna()
    )
    if regulation_only:
        keep &= df["period"].le(4)
    df = df[keep].copy()

    # A negative remaining target means the shift, the join or a final is
    # wrong for that game. Drop the GAME, not the row: one impossible row
    # brands the whole game's score series untrustworthy.
    bad = df.loc[(df["home_remaining_pts"] < 0) |
                 (df["away_remaining_pts"] < 0), "gameId"].unique()
    if len(bad):
        df = df[~df["gameId"].isin(bad)]

    df["wind_mph"] = np.where(df["is_dome"].fillna(False), np.nan,
                              df["wind_mph"])
    df["is_dome"] = df["is_dome"].fillna(False).astype(bool)

    drop = [c for c in df.columns if c.startswith("_")]
    out = df.drop(columns=drop).reset_index(drop=True)
    out.attrs["score_convention"] = convention
    out.attrs["dropped_games_negative_target"] = int(len(bad))
    return out


def _repair_day_offsets(df: pd.DataFrame) -> pd.Series:
    """Same narrow repair as the NFL builder: only >6h backsteps, whole days."""
    ts = df["wall_ts"]
    out = ts.copy()
    for _, idx in df.groupby("gameId", sort=False).indices.items():
        vals = ts.iloc[idx]
        delta = vals.diff().dt.total_seconds()
        need = np.where(delta < -6 * 3600, np.ceil(-delta / 86400.0), 0.0)
        need = np.nan_to_num(need, nan=0.0)
        if need.any():
            out.iloc[idx] = vals + pd.to_timedelta(np.cumsum(need), unit="D")
    return out


def classify_report(pbp: pd.DataFrame) -> pd.DataFrame:
    """Distinct playTypes with their class - eyeball for misrouted types."""
    cls = _classify(pbp["playType"])
    rep = pbp.assign(**cls).groupby("playType").agg(
        n=("playType", "size"), is_pass=("is_pass", "mean"),
        is_rush=("is_rush", "mean"), is_scrim=("is_scrim", "mean"))
    return rep.sort_values("n", ascending=False)


def pace_report(states: pd.DataFrame) -> dict:
    """Verify the configured pace prior against the data it will serve."""
    per_game = states.groupby("gameId")["plays_run"].max()
    return {"median_plays_per_game": float(per_game.median()),
            "configured_prior": LEAGUE_PLAYS_PER_GAME}


def sample_states(states: pd.DataFrame, every: int = 1) -> pd.DataFrame:
    if every <= 1:
        return states
    out = states.groupby("gameId", sort=False, group_keys=False).apply(
        lambda d: d.iloc[::every], include_groups=True)
    return out.reset_index(drop=True)
