"""
NCAAF look-ahead and let-down spot analysis.

The two classic schedule-context angles, neither of which the 18-spot
structure scan covered (it tested rest, weeknight, spread size, neutral site
and conference, but nothing about the games either side of the one being bet):

  LOOK-AHEAD  team is a solid favourite this week, but a much harder game is
              waiting next week. The claim is that attention leaks forward and
              they underperform the number. Bet the OPPONENT.

  LET-DOWN    team is coming off an emotional win -- a close game or an
              upset -- and now faces a soft opponent. The claim is an
              emotional trough. Bet the OPPONENT.

Opponent strength is measured by THE MARKET'S OWN NUMBER (the spread in the
adjacent game) rather than by rankings or our SP+ ratings. That matters: the
spread already prices talent, injuries and home field, so "next week they are
an underdog" is a cleaner statement of "next week is hard" than any rating we
could substitute, and it cannot leak anything about the game being bet.

METHODOLOGY NOTES, because this is exactly the kind of analysis that
manufactures false positives:

  * every definition is fixed BEFORE looking at results, and the variant count
    is kept small and reported, so the multiple-comparisons burden is visible.
    At 95% confidence, ~1 in 20 null spots clears by chance.
  * per-season records are always shown. A spot that only exists in one season
    is noise however good the pooled number looks.
  * the adjacent game must be in the SAME season -- a "next game" that is
    actually next September is not a look-ahead.
  * bowl games are excluded (no next game, and opt-outs make them a different
    sport), and pushes are dropped.

Run:
    python -m scripts.ncaaf_search.situational_spots
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BREAKEVEN = 0.5238
MIN_BETS = 40


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_team_games(conn=None) -> pd.DataFrame:
    """
    One row per (game, team) with that team's own spread, plus the adjacent
    games' context. Two rows per game: each side's perspective.
    """
    from data.db import get_connection
    import config
    from features.ncaaf_feature_engine import is_bowl_game

    owned = conn is None
    conn = conn or get_connection()
    try:
        rows = conn.execute("""
            SELECT g.game_id, g.season, g.week, g.game_date,
                   g.home_team, g.away_team, g.home_score, g.away_score,
                   g.neutral_site, g.conference_game
            FROM games g
            WHERE g.sport = 'NCAAF' AND g.home_score IS NOT NULL
            ORDER BY g.game_date
        """).fetchall()
        cols = ["game_id", "season", "week", "game_date", "home_team",
                "away_team", "home_score", "away_score", "neutral_site",
                "conference_game"]
        g = pd.DataFrame(rows, columns=cols)

        priority = list(config.NCAAF_LINE_BOOKMAKER_PRIORITY)
        in_ph = ",".join(["%s"] * len(priority))
        case_ph = " ".join(f"WHEN %s THEN {i}" for i in range(len(priority)))
        odds = conn.execute(f"""
            SELECT o.game_id, o.spread_home
            FROM odds o JOIN games g ON g.game_id = o.game_id
            WHERE g.sport = 'NCAAF' AND o.market = 'spreads'
              AND o.bookmaker IN ({in_ph})
              AND o.snapshot_type != 'in_play'
            ORDER BY o.game_id,
                     CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                     o.snapshot_at ASC
        """, priority + priority).fetchall()
    finally:
        if owned:
            conn.close()

    sp: dict = {}
    for gid, s in odds:
        if gid not in sp and s is not None:
            sp[gid] = float(s)
    g["spread_home"] = g["game_id"].map(sp)

    g["is_bowl"] = g.apply(
        lambda r: is_bowl_game(r.week, None, r.game_date, r.season), axis=1)
    g = g[(g["is_bowl"] == 0) & g["spread_home"].notna()].copy()
    g["game_date"] = pd.to_datetime(g["game_date"])

    # long form: one row per team per game, spread from THAT team's side
    home = g.rename(columns={"home_team": "team", "away_team": "opp"}).copy()
    home["team_spread"] = home["spread_home"]
    home["team_margin"] = home["home_score"] - home["away_score"]
    home["is_home"] = 1
    away = g.rename(columns={"away_team": "team", "home_team": "opp"}).copy()
    away["team_spread"] = -away["spread_home"]
    away["team_margin"] = away["away_score"] - away["home_score"]
    away["is_home"] = 0

    keep = ["game_id", "season", "week", "game_date", "team", "opp",
            "team_spread", "team_margin", "is_home", "neutral_site",
            "conference_game"]
    long = pd.concat([home[keep], away[keep]], ignore_index=True)

    long["team_cover_margin"] = long["team_margin"] + long["team_spread"]
    long = long[long["team_cover_margin"] != 0].copy()      # drop pushes
    long["team_covered"] = (long["team_cover_margin"] > 0).astype(int)
    long["team_won"] = (long["team_margin"] > 0).astype(int)

    # adjacent games, WITHIN season
    long = long.sort_values(["team", "season", "game_date"])
    grp = long.groupby(["team", "season"], sort=False)
    long["next_spread"] = grp["team_spread"].shift(-1)
    long["prev_spread"] = grp["team_spread"].shift(1)
    long["prev_won"] = grp["team_won"].shift(1)
    long["prev_margin"] = grp["team_margin"].shift(1)
    long["prev_covered"] = grp["team_covered"].shift(1)
    return long


def evaluate(df: pd.DataFrame, mask: pd.Series, name: str) -> dict | None:
    """
    Grade a spot. Every spot here bets AGAINST the flagged team, so the bet
    wins when the flagged team FAILS to cover.
    """
    sub = df[mask]
    n = len(sub)
    if n < MIN_BETS:
        return None
    wins = int((1 - sub["team_covered"]).sum())
    wr = wins / n
    lo, hi = wilson(wins, n)
    per = {}
    for s, ss in sub.groupby("season"):
        if len(ss) >= 10:
            per[int(s)] = round(float((1 - ss["team_covered"]).mean()), 3)
    return {
        "spot": name, "bets": n, "wins": wins, "win_rate": round(wr, 4),
        "roi": round(wr * (100 / 110) - (1 - wr), 4),
        "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
        "clears": lo > BREAKEVEN,
        "seasons_above": sum(1 for v in per.values() if v > BREAKEVEN),
        "seasons": len(per), "per_season": per,
    }


def build_spots(d: pd.DataFrame) -> list[dict]:
    """
    Fixed, pre-specified definitions. Kept deliberately few — every extra
    variant raises the chance one clears by luck alone.
    """
    out = []
    have_next = d["next_spread"].notna()
    have_prev = d["prev_spread"].notna()

    # ── LOOK-AHEAD: big favourite now, much harder game next week ───────────
    for fav, nxt, label in (
        (-7.0, 0.0, "fav by 7+, UNDERDOG next week"),
        (-10.0, 0.0, "fav by 10+, UNDERDOG next week"),
        (-7.0, -3.0, "fav by 7+, next game within 3 pts"),
    ):
        m = have_next & (d["team_spread"] <= fav) & (d["next_spread"] >= nxt)
        out.append(evaluate(d, m, f"LOOK-AHEAD: {label}"))

    # swing: how much harder next week is, in points
    m = have_next & (d["team_spread"] <= -7.0) & \
        ((d["next_spread"] - d["team_spread"]) >= 14.0)
    out.append(evaluate(d, m, "LOOK-AHEAD: fav by 7+, next game 14+ pts harder"))

    # ── LET-DOWN: emotional win last week, soft opponent now ───────────────
    for prev_sp, fav, label in (
        (0.0, -7.0, "won as UNDERDOG last week, fav by 7+ now"),
        (-3.0, -7.0, "won a <=3pt game last week, fav by 7+ now"),
        (0.0, -10.0, "won as UNDERDOG last week, fav by 10+ now"),
    ):
        m = have_prev & (d["prev_won"] == 1) & (d["prev_spread"] >= prev_sp) & \
            (d["team_spread"] <= fav)
        out.append(evaluate(d, m, f"LET-DOWN: {label}"))

    # covered big last week, now a big favourite
    m = have_prev & (d["prev_covered"] == 1) & (d["prev_margin"] >= 21) & \
        (d["team_spread"] <= -7.0)
    out.append(evaluate(d, m, "LET-DOWN: won by 21+ last week, fav by 7+ now"))

    # ── SANDWICH: both at once ─────────────────────────────────────────────
    m = have_prev & have_next & (d["prev_won"] == 1) & (d["prev_spread"] >= 0.0) & \
        (d["team_spread"] <= -7.0) & (d["next_spread"] >= 0.0)
    out.append(evaluate(d, m, "SANDWICH: upset win behind, tough game ahead"))

    # ── CONTROL: big favourite, nothing special either side ────────────────
    m = have_prev & have_next & (d["team_spread"] <= -7.0) & \
        (d["next_spread"] < 0.0) & (d["prev_won"] != 1)
    out.append(evaluate(d, m, "CONTROL: fav by 7+, no look-ahead, no let-down"))

    return [r for r in out if r is not None]


def main() -> int:
    d = load_team_games()
    print(f"team-games with a spread (non-bowl): {len(d)} "
          f"across {d['season'].min()}-{d['season'].max()}")
    base = 1 - d["team_covered"].mean()
    print(f"baseline: betting AGAINST a random team covers {base:.1%} "
          f"(breakeven {BREAKEVEN:.2%})\n")

    rows = build_spots(d)
    rows.sort(key=lambda r: -r["win_rate"])

    bar = "=" * 104
    print(bar)
    print("LOOK-AHEAD / LET-DOWN SCAN — every spot BETS AGAINST the flagged team")
    print(f"min {MIN_BETS} bets | {len(rows)} definitions tested "
          f"| at 95% conf, ~{len(rows) * 0.05:.1f} clear by chance alone")
    print(bar)
    print(f"{'Spot':<52} {'N':>5} {'Win%':>7} {'ROI':>8} {'95% CI':>17} {'Szn>BE':>7}")
    print("-" * 104)
    for r in rows:
        ci = f"[{r['ci_lo']:.1%},{r['ci_hi']:.1%}]"
        flag = "  <<<" if r["clears"] else ("  *" if r["win_rate"] > BREAKEVEN else "")
        print(f"{r['spot']:<52} {r['bets']:>5} {r['win_rate']:>6.1%} "
              f"{r['roi']:>+7.1%} {ci:>17} {r['seasons_above']}/{r['seasons']:<3}{flag}")

    print()
    passing = [r for r in rows if r["clears"]]
    if passing:
        print(f"{len(passing)} spot(s) clear breakeven at 95% confidence:")
        for r in passing:
            print(f"  {r['spot']}: {r['wins']}/{r['bets']} = {r['win_rate']:.1%}, "
                  f"ROI {r['roi']:+.1%}")
            print(f"     per season: {r['per_season']}")
    else:
        print("No spot clears breakeven at 95% confidence.")

    promising = [r for r in rows if r["win_rate"] > BREAKEVEN and not r["clears"]]
    if promising:
        print(f"\n{len(promising)} above breakeven but CI still includes it "
              "(i.e. not distinguishable from noise):")
        for r in promising:
            print(f"  {r['spot']}: {r['bets']} bets, {r['win_rate']:.1%}, "
                  f"{r['seasons_above']}/{r['seasons']} seasons above BE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
