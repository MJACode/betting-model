"""
NCAAF search — feature matrix assembly.

Turns the label set + feature layer into ONE row per game carrying every
registry column, the two labels, and the metadata the walk-forward needs
(season, week, date, provider).

Leakage boundary, restated because this is where it would break:
  * adjusted ratings come from the (season, week) cut, fit on week < w
  * rolling variants are shifted so a game never sees itself
  * ASOF team stats use the newest snapshot with as_of_date <= game_date;
    `<=` is safe because snapshots are stamped at week boundaries and a game
    played on date D is not in the snapshot taken at D
  * the closing line is a FEATURE only under the close-time betting
    assumption, which is what we simulate; it is also the label anchor
  * openers are strictly pre-close, so open->close movement is legitimate
    only when bet timing is at close (spec Group D rule)
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.ncaaf_search.dataset import build_label_set  # noqa: E402
from scripts.ncaaf_search.qb import (
    load_qb_games, build_qb_team_features, merge_qb_features)
from scripts.ncaaf_search.features import (  # noqa: E402
    ADJ_METRICS, RIDGE_ALPHA, CARRYOVER_K, load_team_games,
    load_fbs_membership, pool_fcs_opponents, build_adjusted_ratings,
    build_prior_season_ratings, blended_rating, rolling_variants,
)

OPENER_PARQUET = (Path(__file__).parent.parent.parent / "data" / "raw"
                  / "datawarehouse" / "ncaaf" / "lines_cache"
                  / "openers_bovada.parquet")

_STAT_ASOF_COLS = [
    "games_played", "sp_overall", "sp_offense", "sp_defense", "srs", "talent",
    "returning_ppa", "epa_per_play_off", "epa_per_play_def",
    "success_rate_off", "success_rate_def", "explosiveness_off",
    "explosiveness_def", "havoc_rate", "third_down_rate_off",
    "turnover_margin_pg", "plays_per_game", "seconds_per_play",
]

_EARTH_MI = 3958.8


def _haversine(lat1, lon1, lat2, lon2) -> float | None:
    if any(v is None or (isinstance(v, float) and np.isnan(v))
           for v in (lat1, lon1, lat2, lon2)):
        return None
    p1, p2 = np.radians(float(lat1)), np.radians(float(lat2))
    dp = p2 - p1
    dl = np.radians(float(lon2) - float(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return float(2 * _EARTH_MI * np.arcsin(np.sqrt(a)))


def _load_asof_stats(conn, seasons: list[int]) -> pd.DataFrame:
    ph = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT team, season, as_of_date, {', '.join(_STAT_ASOF_COLS)}
        FROM ncaaf_team_stats
        WHERE season IN ({ph})
        ORDER BY team, season, as_of_date
    """, seasons).fetchall()
    df = pd.DataFrame(rows, columns=["team", "season", "as_of_date"] + _STAT_ASOF_COLS)
    for c in _STAT_ASOF_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    return df


def _load_venues(conn) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT venue_id, latitude, longitude, elevation_ft, dome, grass
        FROM ncaaf_venues
    """).fetchall()
    df = pd.DataFrame(rows, columns=["venue_id", "latitude", "longitude",
                                     "elevation_ft", "dome", "grass"])
    for c in ("latitude", "longitude", "elevation_ft"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _load_weather(conn) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT gw.game_id, gw.temp_f, gw.wind_mph, gw.precip_mm, gw.is_dome_game
        FROM game_weather gw JOIN games g ON g.game_id = gw.game_id
        WHERE g.sport = 'NCAAF'
    """).fetchall()
    df = pd.DataFrame(rows, columns=["game_id", "wx_temp_f", "wx_wind_mph",
                                     "wx_precip_mm", "is_dome_game"])
    for c in ("wx_temp_f", "wx_wind_mph", "wx_precip_mm", "is_dome_game"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _asof_merge(games: pd.DataFrame, stats: pd.DataFrame,
                team_col: str, prefix: str,
                true_prior: pd.DataFrame | None = None) -> pd.DataFrame:
    """
    Newest stat snapshot at or before kickoff, per (team, season) -- with a
    hard leakage guard.

    `as_of_date <= game_date` is NOT sufficient here. Audited 2026-08-25:
    snapshots are stamped Mon-Fri and 53.8% of team-games matched a snapshot
    whose `games_played` EXCEEDED the true number of strictly-prior games
    (+1 in 1,925 cases, i.e. the snapshot already contained the game being
    predicted; +2/+3/+4 in others). Training on that inflates ATS results and
    was responsible for the only sub-ln(2) log loss we saw.

    So every matched snapshot is checked against a prior-game count computed
    from the game log (which is itself shift-tested), and any snapshot
    claiming more games than could have been played is discarded -- stats
    nulled, XGBoost handles the NaN natively. This is a verifiable guard
    rather than a date heuristic.
    """
    left = games[["game_id", "season", "game_dt", team_col]].rename(
        columns={team_col: "team"}).sort_values("game_dt")
    right = stats.sort_values("as_of_date")
    merged = pd.merge_asof(
        left, right, left_on="game_dt", right_on="as_of_date",
        by=["team", "season"], direction="backward")

    if true_prior is not None:
        merged = merged.merge(true_prior, on=["team", "season", "game_id"], how="left")
        bad = merged["games_played"].notna() & merged["true_prior"].notna() &             (merged["games_played"] > merged["true_prior"])
        merged.loc[bad, _STAT_ASOF_COLS] = np.nan
        if len(merged):
            logger.info(f"asof guard [{prefix}]: dropped {int(bad.sum())} / "
                        f"{len(merged)} leaking snapshots ({bad.mean():.1%})")

    keep = ["game_id"] + _STAT_ASOF_COLS
    return merged[keep].rename(columns={c: f"{prefix}{c}" for c in _STAT_ASOF_COLS})


def _true_prior_games(games: pd.DataFrame, team_col: str) -> pd.DataFrame:
    """
    Strictly-prior game count per (team, season) at each game, counting BOTH
    home and away appearances.

    Counting only the rows where the team appears in `team_col` would tally
    just its home (or just its away) games -- roughly half the truth -- and an
    earlier version of this function did exactly that, causing the leakage
    guard to reject 84.5% of snapshots instead of the real ~31%.
    """
    long = pd.concat([
        games[["game_id", "season", "game_dt", "home_team"]]
            .rename(columns={"home_team": "team"}),
        games[["game_id", "season", "game_dt", "away_team"]]
            .rename(columns={"away_team": "team"}),
    ], ignore_index=True).sort_values(["season", "team", "game_dt"])
    long["true_prior"] = long.groupby(["season", "team"]).cumcount()

    want = games[["game_id", "season", team_col]].rename(columns={team_col: "team"})
    return want.merge(long[["game_id", "season", "team", "true_prior"]],
                      on=["game_id", "season", "team"], how="left")


def build_matrix(seasons: list[int] | None = None,
                 alpha: float = RIDGE_ALPHA,
                 carryover_k: float = CARRYOVER_K,
                 include_openers: bool = True) -> pd.DataFrame:
    """One row per game, every registry feature, both labels."""
    from data.db import get_connection

    ls = build_label_set(seasons=seasons)
    games = ls.games.copy()
    if games.empty:
        return games
    seasons = sorted(games["season"].unique().tolist())
    games["game_dt"] = pd.to_datetime(games["game_date"])

    conn = get_connection()
    try:
        fbs = load_fbs_membership(conn)
        tg = pool_fcs_opponents(load_team_games(conn, seasons), fbs)
        stats = _load_asof_stats(conn, seasons)
        venues = _load_venues(conn)
        weather = _load_weather(conn)
    finally:
        conn.close()

    logger.info(f"matrix: {len(games)} games, {len(tg)} team-games (FCS pooled)")

    # ── opponent-adjusted ratings (strictly prior) ──────────────────────────
    adj = build_adjusted_ratings(tg, ADJ_METRICS, alpha)
    prior = build_prior_season_ratings(tg, ADJ_METRICS, alpha)
    logger.info(f"matrix: {len(adj)} (season, week, metric) rating cuts")

    # ── rolling / decay variants ────────────────────────────────────────────
    roll = rolling_variants(tg, ADJ_METRICS)
    roll_cols = [c for c in roll.columns if "__" in c]
    r_home = roll.rename(columns={"team": "home_team"})
    r_away = roll.rename(columns={"team": "away_team"})
    games = games.merge(
        r_home[["game_id", "home_team", "prior_games"] + roll_cols].rename(
            columns={**{c: f"h_{c}" for c in roll_cols}, "prior_games": "h_prior_games"}),
        on=["game_id", "home_team"], how="left")
    games = games.merge(
        r_away[["game_id", "away_team", "prior_games"] + roll_cols].rename(
            columns={**{c: f"a_{c}" for c in roll_cols}, "prior_games": "a_prior_games"}),
        on=["game_id", "away_team"], how="left")
    for c in roll_cols:
        games[f"d_{c}"] = games[f"h_{c}"] - games[f"a_{c}"]

    # ── adjusted differentials ──────────────────────────────────────────────
    for m in ADJ_METRICS:
        vals = []
        for row in games.itertuples():
            s, w = int(row.season), int(row.week or 0)
            hg, ag = getattr(row, "h_prior_games", None), getattr(row, "a_prior_games", None)
            ho = blended_rating(adj, prior, s, w, m, row.home_team, "off", hg, carryover_k)
            hd = blended_rating(adj, prior, s, w, m, row.home_team, "def", hg, carryover_k)
            ao = blended_rating(adj, prior, s, w, m, row.away_team, "off", ag, carryover_k)
            ad = blended_rating(adj, prior, s, w, m, row.away_team, "def", ag, carryover_k)
            if None in (ho, hd, ao, ad):
                vals.append(np.nan)
            else:
                # home's edge on offence minus away's edge on offence
                vals.append((ho - ad) - (ao - hd))
        games[f"d_adj_{m}"] = vals

    # ── ASOF season stats ───────────────────────────────────────────────────
    games = games.merge(
        _asof_merge(games, stats, "home_team", "home_",
                    _true_prior_games(games, "home_team")),
        on="game_id", how="left")
    games = games.merge(
        _asof_merge(games, stats, "away_team", "away_",
                    _true_prior_games(games, "away_team")),
        on="game_id", how="left")
    for c in _STAT_ASOF_COLS:
        games[f"d_{c}"] = games[f"home_{c}"] - games[f"away_{c}"]
    games["sum_plays_per_game"] = games["home_plays_per_game"] + games["away_plays_per_game"]
    games["d_epa_per_play_def"] = games["away_epa_per_play_def"] - games["home_epa_per_play_def"]
    games["d_success_rate_def"] = games["away_success_rate_def"] - games["home_success_rate_def"]

    # ── QB continuity (strictly prior; see scripts/ncaaf_search/qb.py) ──────
    conn = get_connection()
    try:
        qb_raw = load_qb_games(conn, seasons)
    finally:
        conn.close()
    qb_team = build_qb_team_features(qb_raw)
    logger.info(f"matrix: QB rows {len(qb_raw)} passer-games -> "
                f"{len(qb_team)} team-games")
    games = merge_qb_features(games, qb_team)

    # ── weather + venue ─────────────────────────────────────────────────────
    games = games.merge(weather, on="game_id", how="left")
    v = venues.rename(columns={"elevation_ft": "venue_elevation_ft"})
    games = games.merge(v[["venue_id", "venue_elevation_ft", "latitude", "longitude"]],
                        on="venue_id", how="left")

    # Away-team travel: distance from its modal home venue to this venue.
    home_venue = (games.dropna(subset=["venue_id"])
                       .groupby(["home_team", "season"])["venue_id"]
                       .agg(lambda s: s.value_counts().idxmax()).to_dict())
    vloc = venues.set_index("venue_id")[["latitude", "longitude"]].to_dict("index")
    travel = []
    for row in games.itertuples():
        hv = home_venue.get((row.away_team, row.season))
        here = vloc.get(row.venue_id)
        there = vloc.get(hv) if hv else None
        travel.append(_haversine(there["latitude"], there["longitude"],
                                 here["latitude"], here["longitude"])
                      if here and there else np.nan)
    games["d_travel_miles"] = travel

    # ── situational ─────────────────────────────────────────────────────────
    tg_dates = tg[["team", "season", "game_date"]].copy()
    tg_dates["game_date"] = pd.to_datetime(tg_dates["game_date"])
    tg_dates = tg_dates.drop_duplicates().sort_values("game_date")

    def _rest(team_col: str) -> pd.Series:
        # merge_asof with allow_exact_matches=False gives the most recent
        # STRICTLY earlier game -- the leakage-safe definition of rest.
        left = (games[["game_id", "season", "game_dt", team_col]]
                .rename(columns={team_col: "team"})
                .sort_values("game_dt"))
        m = pd.merge_asof(left, tg_dates.rename(columns={"game_date": "prev_dt"}),
                          left_on="game_dt", right_on="prev_dt",
                          by=["team", "season"], direction="backward",
                          allow_exact_matches=False)
        m["rest"] = (m["game_dt"] - m["prev_dt"]).dt.days
        return games["game_id"].map(dict(zip(m["game_id"], m["rest"])))

    games["home_rest"] = _rest("home_team")
    games["away_rest"] = _rest("away_team")
    games["d_rest_days"] = games["home_rest"] - games["away_rest"]
    hr, ar = games["home_rest"].fillna(7), games["away_rest"].fillna(7)
    games["is_bye_advantage"] = (((hr >= 10) & (ar <= 7)) |
                                 ((ar >= 10) & (hr <= 7))).astype(int)

    # ── market (Group D) ────────────────────────────────────────────────────
    games["close_spread"] = games["spread_home"]
    games["close_total"] = games["total_line"]
    games["line_move"] = np.nan
    games["abs_line_move"] = np.nan
    if include_openers and OPENER_PARQUET.exists():
        op = pd.read_parquet(OPENER_PARQUET)
        op = op[["season", "home_team", "away_team", "spread_open", "total_open"]]
        games = games.merge(op, on=["season", "home_team", "away_team"], how="left")
        games["line_move"] = games["close_spread"] - games["spread_open"]
        games["abs_line_move"] = games["line_move"].abs()
        games["total_move"] = games["close_total"] - games["total_open"]
        cov = games["spread_open"].notna().mean()
        logger.info(f"matrix: opener join covers {cov:.1%} of games")

    # `games` stores these unprefixed; the registry uses the is_ form.
    games["is_neutral_site"] = pd.to_numeric(
        games["neutral_site"], errors="coerce").fillna(0).astype(int)
    games["is_conference_game"] = pd.to_numeric(
        games["conference_game"], errors="coerce").fillna(0).astype(int)
    games["week"] = pd.to_numeric(games["week"], errors="coerce")
    return games


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="+", type=int, default=None)
    ap.add_argument("--out", default=None, help="write the matrix to parquet")
    a = ap.parse_args()
    m = build_matrix(a.seasons)
    if a.out:
        m.to_parquet(a.out)
        print(f"wrote {a.out}")
    print(f"\nmatrix: {len(m)} games x {len(m.columns)} cols")
    print(f"usable ATS: {int(m['home_covers'].notna().sum())}  "
          f"totals: {int(m['went_over'].notna().sum())}")
