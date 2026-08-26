"""
NCAAF market-structure scan — find schedule/situational spots where the
closing spread systematically misprices.

The margin-regression model (walk-forward: 52.1% pooled) confirms what the
Coleman (2025) metamodel study found: no combination of team-strength metrics
contains useful information not already in the final spread. Adding more
features (turnover margin, havoc rate, returning production, third-down rate)
made it WORSE, not better.

This script takes the opposite approach: ignore team strength entirely and
look for structural spots where the market is inefficient for reasons that
have nothing to do with who is playing. Thursday MACtion, early-season lines
built on stale priors, bye-week mismatches, etc.

Run:
    python -m scripts.ncaaf_structure_scan
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


BREAKEVEN = 0.5238
MIN_BETS = 30           # Lower bar than the margin model — structural spots are narrow


def load_data() -> pd.DataFrame:
    """All completed, non-bowl NCAAF games with a closing spread."""
    from data.db import get_connection
    from features.ncaaf_feature_engine import is_bowl_game

    conn = get_connection()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.season, g.game_date, g.home_team, g.away_team,
                   g.home_score, g.away_score, g.week, g.neutral_site,
                   g.conference_game, g.venue_id,
                   g.commence_time
            FROM games g
            WHERE g.sport = 'NCAAF'
              AND g.home_score IS NOT NULL
            ORDER BY g.game_date
        """).fetchall()
        cols = ["game_id", "season", "game_date", "home_team", "away_team",
                "home_score", "away_score", "week", "neutral_site",
                "conference_game", "venue_id", "commence_time"]
        df = pd.DataFrame(rows, columns=cols)

        # Closing spread (best available)
        import config
        priority = list(config.NCAAF_LINE_BOOKMAKER_PRIORITY)
        in_ph = ",".join(["%s"] * len(priority))
        case_ph = " ".join(f"WHEN %s THEN {i}" for i in range(len(priority)))
        odds_rows = conn.execute(f"""
            SELECT o.game_id, o.spread_home, o.total_line
            FROM odds o JOIN games g ON g.game_id = o.game_id
            WHERE g.sport = 'NCAAF'
              AND o.market = 'spreads'
              AND o.bookmaker IN ({in_ph})
              AND o.snapshot_type != 'in_play'
            ORDER BY o.game_id,
                     CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                     o.snapshot_at ASC
        """, priority + priority).fetchall()
        # First row per game_id wins (priority + earliest snapshot)
        spread_map = {}
        total_map = {}
        for gid, sp, tl in odds_rows:
            if gid not in spread_map and sp is not None:
                spread_map[gid] = float(sp)
            if gid not in total_map and tl is not None:
                total_map[gid] = float(tl)
        df["spread_home"] = df["game_id"].map(spread_map)
        df["total_line"] = df["game_id"].map(total_map)

        # Team metadata (conference, SP+)
        team_rows = conn.execute("""
            SELECT DISTINCT ON (team, season)
                team, season, conference, sp_overall, returning_ppa,
                games_played, wins, losses
            FROM ncaaf_team_stats
            WHERE as_of_date <= '2099-12-31'
            ORDER BY team, season, as_of_date DESC
        """).fetchall()
        team_cols = ["team", "season", "conference", "sp_overall",
                     "returning_ppa", "games_played", "wins", "losses"]
        team_df = pd.DataFrame(team_rows, columns=team_cols)
        team_lookup = {(r.team, r.season): r for r in team_df.itertuples()}

    finally:
        conn.close()

    # Derived columns
    df["margin"] = df["home_score"] - df["away_score"]
    df["is_bowl"] = df.apply(
        lambda r: is_bowl_game(r.week, None, r.game_date, r.season), axis=1)
    df = df[(df["is_bowl"] == 0) & df["spread_home"].notna()].copy()

    # Day of week
    df["dow"] = pd.to_datetime(df["game_date"]).dt.dayofweek  # 0=Mon .. 6=Sun

    # Conference info
    def _conf(team, season):
        t = team_lookup.get((team, season))
        return t.conference if t else None
    def _sp(team, season):
        t = team_lookup.get((team, season))
        return t.sp_overall if t else None
    df["home_conf"] = df.apply(lambda r: _conf(r.home_team, r.season), axis=1)
    df["away_conf"] = df.apply(lambda r: _conf(r.away_team, r.season), axis=1)
    df["home_sp"] = df.apply(lambda r: _sp(r.home_team, r.season), axis=1)
    df["away_sp"] = df.apply(lambda r: _sp(r.away_team, r.season), axis=1)

    # Cover result: home covers iff margin + spread > 0; push excluded
    df["cover_result"] = np.sign(df["margin"] + df["spread_home"])
    df = df[df["cover_result"] != 0].copy()  # drop pushes
    df["home_covers"] = (df["cover_result"] > 0).astype(int)

    # Underdog flag: home is the dog if spread_home > 0
    df["home_is_dog"] = (df["spread_home"] > 0).astype(int)
    # Dog covers (regardless of which side)
    df["dog_covers"] = np.where(
        df["home_is_dog"] == 1, df["home_covers"], 1 - df["home_covers"])

    # Rest days (from prior game in the season)
    game_dates = df.sort_values("game_date").groupby(
        ["season", "home_team"])["game_date"].apply(list).to_dict()
    away_dates = df.sort_values("game_date").groupby(
        ["season", "away_team"])["game_date"].apply(list).to_dict()

    def _rest(team, season, game_date, is_home):
        key = (season, team)
        dates = (game_dates if is_home else away_dates).get(key, [])
        prior = [d for d in dates if d < game_date]
        if not prior:
            return 7  # season opener
        d0 = pd.Timestamp(prior[-1])
        d1 = pd.Timestamp(game_date)
        return (d1 - d0).days

    df["home_rest"] = df.apply(
        lambda r: _rest(r.home_team, r.season, r.game_date, True), axis=1)
    df["away_rest"] = df.apply(
        lambda r: _rest(r.away_team, r.season, r.game_date, False), axis=1)

    # Power-4 flags
    p4 = {"SEC", "Big Ten", "ACC", "Big 12"}
    df["home_p4"] = df["home_conf"].isin(p4).astype(int)
    df["away_p4"] = df["away_conf"].isin(p4).astype(int)
    df["game_tier"] = df["home_p4"] + df["away_p4"]  # 2=both P4, 1=mixed, 0=G5vG5

    return df


def scan_spot(df: pd.DataFrame, name: str, mask: pd.Series,
              side: str = "dog") -> dict | None:
    """
    Evaluate a structural spot.

    side = "dog"  -> bet the underdog in every qualifying game
    side = "home" -> bet the home team
    side = "away" -> bet the away team
    """
    sub = df[mask].copy()
    n = len(sub)
    if n < MIN_BETS:
        return None

    if side == "dog":
        wins = int(sub["dog_covers"].sum())
    elif side == "home":
        wins = int(sub["home_covers"].sum())
    else:
        wins = int((1 - sub["home_covers"]).sum())

    wr = wins / n
    roi = wr * (100 / 110) - (1 - wr)
    se = (wr * (1 - wr) / n) ** 0.5
    lo, hi = wr - 1.96 * se, wr + 1.96 * se

    return {
        "spot": name,
        "side": side,
        "n": n,
        "wins": wins,
        "win_rate": round(wr, 4),
        "roi": round(roi, 4),
        "ci_lo": round(lo, 4),
        "ci_hi": round(hi, 4),
        "clears": lo > BREAKEVEN,
        "seasons": sorted(sub["season"].unique().tolist()),
    }


def main():
    df = load_data()
    print(f"Loaded {len(df)} non-bowl NCAAF games with spreads "
          f"({df['season'].min()}-{df['season'].max()})")
    print(f"Baseline dog cover rate: {df['dog_covers'].mean():.1%} "
          f"({int(df['dog_covers'].sum())}/{len(df)})\n")

    spots = []

    # ── 1. Weeknight games (Tue-Thu) ─────────────────────────────────────────
    weeknight = df["dow"].isin([1, 2, 3])  # Tue, Wed, Thu
    spots.append(scan_spot(df, "Weeknight (Tue-Thu) — dog", weeknight, "dog"))
    spots.append(scan_spot(df, "Weeknight (Tue-Thu) — home", weeknight, "home"))

    # Weeknight G5-only
    weeknight_g5 = weeknight & (df["game_tier"] == 0)
    spots.append(scan_spot(df, "Weeknight G5-vs-G5 — dog", weeknight_g5, "dog"))

    # ── 2. Early season (weeks 1-3) ──────────────────────────────────────────
    early = df["week"] <= 3
    spots.append(scan_spot(df, "Weeks 1-3 — dog", early, "dog"))

    early_nonconf = early & (df["conference_game"] != 1)
    spots.append(scan_spot(df, "Weeks 1-3 non-conf — dog", early_nonconf, "dog"))

    # Early-season P4 vs G5 (the P4 team is usually a heavy favorite with stale lines)
    early_p4_host = early & (df["home_p4"] == 1) & (df["away_p4"] == 0)
    spots.append(scan_spot(df, "Weeks 1-3 P4 hosting G5 — away (dog)", early_p4_host, "away"))

    # ── 3. Bye-week mismatches ───────────────────────────────────────────────
    # One team off bye (10+ rest), opponent on normal week (<=8)
    home_bye = (df["home_rest"] >= 10) & (df["away_rest"] <= 8)
    spots.append(scan_spot(df, "Home off bye vs normal — home", home_bye, "home"))

    away_bye = (df["away_rest"] >= 10) & (df["home_rest"] <= 8)
    spots.append(scan_spot(df, "Away off bye vs normal — away", away_bye, "away"))

    # Team off bye as underdog
    bye_dog = ((df["home_rest"] >= 10) & (df["home_is_dog"] == 1)) | \
              ((df["away_rest"] >= 10) & (df["home_is_dog"] == 0))
    spots.append(scan_spot(df, "Team off bye as underdog — dog", bye_dog, "dog"))

    # ── 4. Short week (<=5 days rest) ────────────────────────────────────────
    short_home = df["home_rest"] <= 5
    spots.append(scan_spot(df, "Home on short rest (<=5d) — away", short_home, "away"))

    short_away = df["away_rest"] <= 5
    spots.append(scan_spot(df, "Away on short rest (<=5d) — home", short_away, "home"))

    # ── 5. Large spreads (market overreaction) ───────────────────────────────
    big_fav = df["spread_home"].abs() >= 21
    spots.append(scan_spot(df, "Spread >= 21 pts — dog", big_fav, "dog"))

    huge_fav = df["spread_home"].abs() >= 28
    spots.append(scan_spot(df, "Spread >= 28 pts — dog", huge_fav, "dog"))

    # ── 6. Conference games as toss-ups ──────────────────────────────────────
    conf_tossup = (df["conference_game"] == 1) & (df["spread_home"].abs() <= 3)
    spots.append(scan_spot(df, "Conf game, spread <= 3 — home", conf_tossup, "home"))
    spots.append(scan_spot(df, "Conf game, spread <= 3 — dog", conf_tossup, "dog"))

    # ── 7. Late season (week >= 10) underdogs ────────────────────────────────
    late_dog = df["week"] >= 10
    spots.append(scan_spot(df, "Week 10+ — dog", late_dog, "dog"))

    # ── 8. Neutral site ──────────────────────────────────────────────────────
    neutral = df["neutral_site"] == 1
    spots.append(scan_spot(df, "Neutral site — dog", neutral, "dog"))

    # ── 9. P4 vs P4 as dog ───────────────────────────────────────────────────
    p4vp4_dog = df["game_tier"] == 2
    spots.append(scan_spot(df, "P4 vs P4 — dog", p4vp4_dog, "dog"))

    # ── 10. G5 vs G5 ────────────────────────────────────────────────────────
    g5vg5 = df["game_tier"] == 0
    spots.append(scan_spot(df, "G5 vs G5 — dog", g5vg5, "dog"))

    # ── Print results ────────────────────────────────────────────────────────
    results = [s for s in spots if s is not None]
    results.sort(key=lambda r: r["win_rate"], reverse=True)

    bar = "=" * 90
    print(bar)
    print("NCAAF STRUCTURAL MARKET SCAN")
    print(f"Breakeven at -110: {BREAKEVEN:.2%} | Min bets: {MIN_BETS}")
    print(bar)
    print(f"{'Spot':<45} {'Side':<6} {'N':>5} {'W':>5} {'Win%':>7} "
          f"{'ROI':>7} {'95% CI':>15} {'Pass':>5}")
    print("-" * 90)

    for r in results:
        ci = f"[{r['ci_lo']:.1%},{r['ci_hi']:.1%}]"
        flag = " <<<" if r["clears"] else (" *" if r["win_rate"] >= BREAKEVEN else "")
        print(f"{r['spot']:<45} {r['side']:<6} {r['n']:>5} {r['wins']:>5} "
              f"{r['win_rate']:>6.1%} {r['roi']:>+6.1%} {ci:>15}{flag}")

    print()
    passing = [r for r in results if r["clears"]]
    promising = [r for r in results if r["win_rate"] >= BREAKEVEN and not r["clears"]]
    if passing:
        print(f"{len(passing)} spot(s) clear breakeven with 95% confidence:")
        for r in passing:
            print(f"  {r['spot']} ({r['side']}): {r['wins']}/{r['n']} = "
                  f"{r['win_rate']:.1%}, ROI {r['roi']:+.1%}")
    else:
        print("No spot clears breakeven with 95% confidence.")

    if promising:
        print(f"\n{len(promising)} spot(s) above breakeven but CI still includes it:")
        for r in promising:
            print(f"  {r['spot']} ({r['side']}): {r['wins']}/{r['n']} = "
                  f"{r['win_rate']:.1%}, ROI {r['roi']:+.1%}")


if __name__ == "__main__":
    main()
