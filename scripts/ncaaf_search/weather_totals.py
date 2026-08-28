"""
NCAAF weather-totals scan: the CFB analog of the validated NFL wind rule.

WHY THIS IS THE MOST PROMISING REMAINING LEVER
----------------------------------------------
The one rule in this whole project whose own documentation clears it for live
money is the NFL wind-totals under (57.09% under at wind >= 12mph, confirmed
on ERA5 independent of the odds source). The mechanism is not subtle: wind
suppresses passing and kicking, scoring falls ~5 points from calm to windy,
and the NFL market hangs nearly the same total anyway. College football has
MORE outdoor games, MORE bad-weather venues, and LESS liquidity per game than
the NFL -- so if the market inattention exists anywhere else, this is where.

METHODOLOGY (inherited from the NFL work and from situational_spots.py)
-----------------------------------------------------------------------
  * every definition is fixed BEFORE looking at results; the variant count is
    reported so the multiple-comparisons burden is visible (~1 in 20 null
    definitions clears at 95% by chance).
  * TIME SPLIT is the primary robustness test: a rule must hold in BOTH the
    early half (2014-2019) and the late half (2021-2025). This is the test
    that killed every candidate in the NFL edge hunt except rain-in-calm.
  * per-season records always shown; Wilson CIs vs the -110 breakeven.
  * dome games are excluded from every weather rule (their weather rows are
    fabricated placeholders) and kept as a CONTROL that must sit near 50%.

THE HONEST CAVEAT, STATED UP FRONT
----------------------------------
Historical weather here is Open-Meteo REANALYSIS at 3pm local -- truth, not a
forecast. A live bet is placed on a forecast, so any edge found here is an
UPPER BOUND. The NFL work measured that haircut directly: ~0.41pp of win rate
per day of forecast lead, ~2.5pp at the day-3 lead it deploys at. Any CFB rule
must survive that haircut with room to spare, which in practice means the
reanalysis number needs to clear ~55%, not just the 52.38% breakeven.

Run:
    python -m scripts.ncaaf_search.weather_totals
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BREAKEVEN = 0.5238
MIN_BETS = 60
EARLY = (2014, 2019)      # time-split halves; 2020 excluded project-wide
LATE = (2021, 2025)


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_games(conn=None) -> pd.DataFrame:
    """
    One row per completed NCAAF game with a totals line and a weather row.
    The line is the archive provider priority (the number the label was
    computed from), never the live-DK row.
    """
    from data.db import get_connection
    import config

    owned = conn is None
    conn = conn or get_connection()
    try:
        priority = list(config.NCAAF_LINE_BOOKMAKER_PRIORITY)
        in_ph = ",".join(["%s"] * len(priority))
        case_ph = " ".join(f"WHEN %s THEN {i}" for i in range(len(priority)))
        rows = conn.execute(f"""
            SELECT g.game_id, g.season, g.week, g.game_date,
                   g.home_score, g.away_score,
                   w.wind_mph, w.temp_f, w.precip_mm, w.is_dome_game,
                   o.total_line
            FROM games g
            JOIN game_weather w ON w.game_id = g.game_id
            JOIN LATERAL (
                SELECT o.total_line
                FROM odds o
                WHERE o.game_id = g.game_id AND o.market = 'totals'
                  AND o.total_line IS NOT NULL
                  AND o.bookmaker IN ({in_ph})
                  AND o.snapshot_type != 'in_play'
                ORDER BY CASE o.bookmaker {case_ph} ELSE {len(priority)} END,
                         o.snapshot_at ASC
                LIMIT 1
            ) o ON TRUE
            WHERE g.sport = 'NCAAF' AND g.home_score IS NOT NULL
        """, priority + priority).fetchall()
    finally:
        if owned:
            conn.close()

    df = pd.DataFrame(rows, columns=[
        "game_id", "season", "week", "game_date", "home_score", "away_score",
        "wind_mph", "temp_f", "precip_mm", "is_dome_game", "total_line"])
    for c in ("wind_mph", "temp_f", "precip_mm", "total_line",
              "home_score", "away_score"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["total"] = df["home_score"] + df["away_score"]
    df = df[df["total"] != df["total_line"]].copy()          # drop pushes
    df["under"] = (df["total"] < df["total_line"]).astype(int)
    df["is_dome"] = pd.to_numeric(df["is_dome_game"], errors="coerce").fillna(0) == 1
    return df


def evaluate(df: pd.DataFrame, mask: pd.Series, name: str,
             side: str = "under") -> dict | None:
    sub = df[mask]
    n = len(sub)
    if n < MIN_BETS:
        return None
    wins = int(sub["under"].sum() if side == "under" else (1 - sub["under"]).sum())
    wr = wins / n
    lo, hi = wilson(wins, n)
    per = {int(s): round(float(
        (ss["under"] if side == "under" else 1 - ss["under"]).mean()), 3)
        for s, ss in sub.groupby("season") if len(ss) >= 10}

    def half(a, b):
        h = sub[(sub["season"] >= a) & (sub["season"] <= b)]
        if len(h) < 30:
            return (float("nan"), 0)
        w = (h["under"] if side == "under" else 1 - h["under"]).mean()
        return (float(w), len(h))

    e_wr, e_n = half(*EARLY)
    l_wr, l_n = half(*LATE)
    return {
        "spot": name, "side": side, "bets": n, "wins": wins,
        "win_rate": round(wr, 4),
        "roi": round(wr * (100 / 110) - (1 - wr), 4),
        "ci_lo": round(lo, 4), "ci_hi": round(hi, 4),
        "clears": lo > BREAKEVEN,
        "early": (round(e_wr, 3), e_n), "late": (round(l_wr, 3), l_n),
        "both_halves": (e_wr > BREAKEVEN) and (l_wr > BREAKEVEN),
        "seasons_above": sum(1 for v in per.values() if v > BREAKEVEN),
        "seasons": len(per), "per_season": per,
    }


def build_spots(d: pd.DataFrame) -> list[dict]:
    """Fixed, pre-specified. Deliberately few."""
    out = []
    o = ~d["is_dome"]          # outdoor only for every weather rule

    # ── WIND -> UNDER (the NFL rule, threshold ladder) ──────────────────────
    for t in (8.0, 10.0, 12.0, 15.0):
        out.append(evaluate(d, o & (d["wind_mph"] >= t), f"wind >= {t:g} mph"))

    # ── PRECIP -> UNDER (incl. the NFL rain-in-calm candidate verbatim) ─────
    out.append(evaluate(d, o & (d["precip_mm"] > 0.2), "precip > 0.2mm"))
    out.append(evaluate(d, o & (d["precip_mm"] > 0.2) & (d["wind_mph"] < 11.0),
                        "precip > 0.2mm AND wind < 11 (NFL rain-in-calm)"))

    # ── COLD -> UNDER ───────────────────────────────────────────────────────
    for t in (32.0, 25.0):
        out.append(evaluate(d, o & (d["temp_f"] <= t), f"temp <= {t:g}F"))

    # ── COMPOUND ────────────────────────────────────────────────────────────
    out.append(evaluate(d, o & (d["wind_mph"] >= 12.0) & (d["precip_mm"] > 0.2),
                        "wind >= 12 AND precip > 0.2"))

    # ── CONTROLS (must sit near 50% or the harness itself is biased) ────────
    out.append(evaluate(d, d["is_dome"], "CONTROL: dome games"))
    out.append(evaluate(d, o & (d["wind_mph"] < 8.0) & (d["precip_mm"] <= 0.0)
                        & (d["temp_f"] >= 50.0), "CONTROL: calm, dry, warm"))

    return [r for r in out if r is not None]


def scoring_by_wind(d: pd.DataFrame) -> None:
    """
    The mechanism check the NFL work leaned on: does scoring actually fall
    with wind while the market's number does not? If scoring is flat, any
    win-rate blip above is noise wearing a story.
    """
    o = d[~d["is_dome"] & d["wind_mph"].notna()]
    bins = [(0, 4), (4, 8), (8, 11), (11, 14), (14, 18), (18, 99)]
    print("\nMECHANISM: actual total and market line by wind band (outdoor)")
    print(f"{'band':>10} {'n':>6} {'avg_total':>10} {'avg_line':>9} "
          f"{'total-line':>11} {'under%':>7}")
    for a, b in bins:
        s = o[(o["wind_mph"] >= a) & (o["wind_mph"] < b)]
        if len(s) < 30:
            continue
        print(f"{f'{a}-{b}':>10} {len(s):>6} {s['total'].mean():>10.2f} "
              f"{s['total_line'].mean():>9.2f} "
              f"{(s['total'] - s['total_line']).mean():>+11.2f} "
              f"{s['under'].mean():>7.1%}")


def main() -> int:
    d = load_games()
    n_out = int((~d["is_dome"]).sum())
    print(f"NCAAF games with a totals line + weather: {len(d)} "
          f"({n_out} outdoor) across {d['season'].min()}-{d['season'].max()}")
    print(f"baseline under rate (all): {d['under'].mean():.1%}  "
          f"breakeven {BREAKEVEN:.2%}")

    scoring_by_wind(d)

    rows = build_spots(d)
    rows.sort(key=lambda r: -r["win_rate"])
    n_defs = sum(1 for r in rows if not r["spot"].startswith("CONTROL"))
    bar = "=" * 118
    print(f"\n{bar}")
    print("WEATHER -> UNDER SCAN (reanalysis weather = UPPER BOUND; "
          "live forecast costs ~2.5pp)")
    print(f"min {MIN_BETS} bets | {n_defs} definitions + 2 controls "
          f"| ~{n_defs * 0.05:.1f} clear by chance at 95%")
    print(bar)
    print(f"{'Spot':<44} {'N':>6} {'Win%':>7} {'ROI':>8} {'95% CI':>17} "
          f"{'early':>12} {'late':>12} {'Szn>BE':>7}")
    print("-" * 118)
    for r in rows:
        ci = f"[{r['ci_lo']:.1%},{r['ci_hi']:.1%}]"
        e = f"{r['early'][0]:.3f}({r['early'][1]})"
        l = f"{r['late'][0]:.3f}({r['late'][1]})"
        flag = ("  <<< BOTH-HALVES" if (r["clears"] and r["both_halves"])
                else ("  <<<" if r["clears"]
                      else ("  *" if r["win_rate"] > BREAKEVEN else "")))
        print(f"{r['spot']:<44} {r['bets']:>6} {r['win_rate']:>6.1%} "
              f"{r['roi']:>+7.1%} {ci:>17} {e:>12} {l:>12} "
              f"{r['seasons_above']}/{r['seasons']:<3}{flag}")

    print()
    for r in rows:
        if r["clears"]:
            print(f"{r['spot']}: per-season {r['per_season']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
