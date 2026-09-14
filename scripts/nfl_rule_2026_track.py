"""2026 paper-track for nfl_opener_spread and nfl_wind_totals.

    python -m scripts.nfl_rule_2026_track
    python -m scripts.nfl_rule_2026_track --season 2026
    python -m scripts.nfl_rule_2026_track --settle     # settle then report

WHY THIS EXISTS
---------------
Both rules are LIVE on a thin, fragile evidence base. The 2026 season is the
forward test. This is the October (and end-of-season) command so nobody has to
hunt SQL, a backtest script, or a session log to re-score them.

POLICY (encoded, not a unit increase)
-------------------------------------
* Do not bump units. opener UNIT_PCT and wind UNIT_PCT stay 0.01; wind
  MAX_UNITS stays 2; opener MAX_UNITS stays 4.
* nfl_opener_spread: paper-track through 2026. Retire if the 2026 settled
  BET record (WIN/LOSS/PUSH, VOID excluded) finishes at or below flat.
  Six-season restatement already spans zero (2024 carried; 2020-22 lost).
  Do not unpause the paused XGB / distributional NFL props as a response.
* nfl_wind_totals: keep the physical residual. MAX_FIRE_LEAD stays 4.
  Measure the deployed Open-Meteo issued-forecast population (2024 and 2025
  lost on observed wind; see docs/nfl_wind_lead_evidence.md). Do not widen
  the fire window.

WHAT IT GRADES
--------------
The production `picks` table is the paper track. Settlement is
`tracking.paper_tracker.settle_picks` (already the daily grader). This script
reads that record. `--settle` runs the existing grader on any still-unsettled
dates for these two models, then reports. It does not re-price, does not
void, and does not change a threshold.

Units = profit_flat / 100 on priced settled BETs (CLAUDE.md section 4 and 6).
An unpriced settled pick is counted in W-L and dropped from units/ROI,
because profit_flat fabricates -110 when the price is missing.
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
NFL_ROOT = ROOT / "nfl"

MODELS = ("nfl_opener_spread", "nfl_wind_totals")

# Policy pins. Tests read these names. Changing a value here is a product
# decision, not a refactor.
NO_UNIT_BUMP = True
OPENER_RETIRE_IF_FLAT_2026 = True
WIND_MAX_FIRE_LEAD_STAYS = 4.0
DO_NOT_UNPAUSE_XGB_PROPS = True

SETTLED = ("WIN", "LOSS", "PUSH")


def _load_nfl_model(name: str):
    sys.path.insert(0, str(NFL_ROOT))
    try:
        from _nfl_models import load_nfl_model
        return load_nfl_model(name)
    finally:
        if str(NFL_ROOT) in sys.path:
            sys.path.remove(str(NFL_ROOT))


def season_bounds(season: int) -> tuple[str, str]:
    """NFL season `season` runs August of that year through February of the next."""
    return f"{season}-08-01", f"{season + 1}-03-01"


def units_from_profit_flat(profit_flat: float | None, odds: float | None,
                           result: str | None) -> float | None:
    """Units on one priced settled bet. None when unpriced -- do not invent -110."""
    if result not in SETTLED:
        return None
    if odds is None:
        return None
    if result == "PUSH":
        return 0.0
    if profit_flat is None:
        return None
    return float(profit_flat) / 100.0


def is_void(row: dict) -> bool:
    return row.get("condition_status") == "VOID" or (
        row.get("result") == "NO_ACTION" and row.get("condition_status") == "VOID")


def classify(row: dict) -> str:
    if is_void(row):
        return "void"
    if row.get("result") in SETTLED:
        return "settled"
    if row.get("result") in (None, ""):
        return "unsettled"
    return "other"


def grade_rows(rows: list[dict]) -> dict:
    """Split one model's rows into the paper-track buckets. Pure; no DB."""
    settled, void, unsettled, other = [], [], [], []
    for row in rows:
        bucket = classify(row)
        if bucket == "settled":
            settled.append(row)
        elif bucket == "void":
            void.append(row)
        elif bucket == "unsettled":
            unsettled.append(row)
        else:
            other.append(row)

    w = sum(1 for r in settled if r.get("result") == "WIN")
    l = sum(1 for r in settled if r.get("result") == "LOSS")
    p = sum(1 for r in settled if r.get("result") == "PUSH")
    priced = []
    unpriced = 0
    for r in settled:
        u = units_from_profit_flat(r.get("profit_flat"), r.get("odds"), r.get("result"))
        if u is None:
            unpriced += 1
        else:
            priced.append(u)
    n_priced = len(priced)
    units = sum(priced) if priced else 0.0
    roi = (100.0 * units / n_priced) if n_priced else None
    return {
        "n": len(rows),
        "settled": len(settled),
        "wins": w,
        "losses": l,
        "pushes": p,
        "void": len(void),
        "unsettled": len(unsettled),
        "other": len(other),
        "unpriced_settled": unpriced,
        "priced": n_priced,
        "units": round(units, 2),
        "roi": None if roi is None else round(roi, 1),
        "rows": settled,
    }


def opener_verdict(grade: dict, season: int, season_over: bool) -> str:
    """Retire if 2026 finishes <= flat. Do not retire mid-season on a thin n."""
    if not OPENER_RETIRE_IF_FLAT_2026:
        return "HOLD -- retire-if-flat-2026 is off"
    if grade["priced"] == 0:
        if season_over:
            return (f"HOLD -- {season} finished with no priced settled BETs; "
                    "retire-if-flat needs a record")
        return f"HOLD -- no priced settled BETs yet; retire if {season} finishes <= flat"
    roi = grade["roi"]
    rec = f"{grade['wins']}-{grade['losses']}"
    if grade["pushes"]:
        rec += f"-{grade['pushes']}"
    line = f"{rec}, {grade['units']:+.2f}u, ROI {roi:+.1f}% on {grade['priced']} priced"
    if not season_over:
        return f"HOLD -- {line}. Retire if {season} finishes <= flat. Season is not over."
    if roi is not None and roi <= 0:
        return f"RETIRE-CANDIDATE -- {season} <= flat ({line})"
    return f"HOLD -- {season} finished above flat ({line})"


def wind_verdict(grade: dict, past_window: list[dict]) -> str:
    extra = ""
    if past_window:
        extra = (f" FLAG: {len(past_window)} standing BET(s) locked past "
                 f"MAX_FIRE_LEAD={WIND_MAX_FIRE_LEAD_STAYS:.0f}.")
    if grade["priced"] == 0:
        return ("HOLD -- physical residual, MAX_FIRE_LEAD stays 4, no unit bump. "
                f"No priced settled BETs yet ({grade['unsettled']} unsettled)."
                + extra)
    rec = f"{grade['wins']}-{grade['losses']}"
    roi = grade["roi"]
    return (f"HOLD -- physical residual, MAX_FIRE_LEAD stays 4, no unit bump. "
            f"{rec}, {grade['units']:+.2f}u, ROI {roi:+.1f}% on {grade['priced']} priced."
            + extra)


def lead_days(created_at: Any, commence_time: Any) -> float | None:
    if created_at is None or commence_time is None:
        return None
    a, b = created_at, commence_time
    if getattr(a, "tzinfo", None) is None:
        a = a.replace(tzinfo=timezone.utc)
    if getattr(b, "tzinfo", None) is None:
        b = b.replace(tzinfo=timezone.utc)
    return (b - a).total_seconds() / 86400.0


def fetch(conn, season: int) -> list[dict]:
    lo, hi = season_bounds(season)
    like = f"NFL_{season}_%"
    rows = conn.execute("""
        SELECT p.pick_id, p.model_id, p.game_id, p.game_date::text,
               p.pick_label, p.pick_side, p.scored_line,
               COALESCE(p.decision_odds, p.dk_odds) AS odds,
               p.result, p.condition_status, p.condition_note,
               p.profit_flat, p.created_at,
               g.commence_time, g.home_score, g.away_score
        FROM picks p
        LEFT JOIN games g ON g.game_id = p.game_id
        WHERE p.model_id IN ('nfl_opener_spread', 'nfl_wind_totals')
          AND p.signal_type = 'BET'
          AND (p.game_id LIKE %s
               OR (p.game_date >= %s AND p.game_date < %s))
        ORDER BY p.model_id, p.created_at
    """, (like, lo, hi)).fetchall()
    cols = ("pick_id", "model_id", "game_id", "game_date", "pick_label",
            "pick_side", "scored_line", "odds", "result", "condition_status",
            "condition_note", "profit_flat", "created_at", "commence_time",
            "home_score", "away_score")
    out = []
    for r in rows:
        if isinstance(r, dict):
            out.append(dict(r))
        else:
            out.append(dict(zip(cols, r)))
    return out


def settle_unsettled(season: int) -> list[str]:
    """Run the existing grader on dates that still hold an unsettled rule BET."""
    from data.db import get_connection
    from tracking.paper_tracker import settle_picks

    lo, hi = season_bounds(season)
    conn = get_connection()
    try:
        dates = [str(d) for (d,) in conn.execute("""
            SELECT DISTINCT game_date::text
            FROM picks
            WHERE model_id IN ('nfl_opener_spread', 'nfl_wind_totals')
              AND signal_type = 'BET'
              AND result IS NULL
              AND COALESCE(condition_status, '') <> 'VOID'
              AND game_date >= %s AND game_date < %s
            ORDER BY 1
        """, (lo, hi)).fetchall()]
    finally:
        conn.close()
    for d in dates:
        settle_picks(game_date=d)
    return dates


def report(season: int, rows: list[dict], *, settled_dates: list[str] | None = None
           ) -> dict:
    wind = _load_nfl_model("wind_totals")
    opener = _load_nfl_model("opener_spread")
    assert wind.MAX_FIRE_LEAD == WIND_MAX_FIRE_LEAD_STAYS, (
        f"MAX_FIRE_LEAD drifted to {wind.MAX_FIRE_LEAD}; policy is "
        f"{WIND_MAX_FIRE_LEAD_STAYS}")
    assert opener.UNIT_PCT == 0.01 and wind.UNIT_PCT == 0.01, (
        "unit bump: UNIT_PCT is not 0.01")
    assert NO_UNIT_BUMP and DO_NOT_UNPAUSE_XGB_PROPS

    by_model = {m: [r for r in rows if r["model_id"] == m] for m in MODELS}
    grades = {m: grade_rows(by_model[m]) for m in MODELS}

    past_window = []
    for r in by_model["nfl_wind_totals"]:
        if classify(r) == "void":
            continue
        lead = lead_days(r.get("created_at"), r.get("commence_time"))
        if lead is not None and lead > wind.MAX_FIRE_LEAD + 0.05:
            past_window.append({**r, "lead_days": round(lead, 2)})

    lo, hi = season_bounds(season)
    season_over = datetime.now(timezone.utc).date().isoformat() >= hi
    opener_v = opener_verdict(grades["nfl_opener_spread"], season, season_over)
    wind_v = wind_verdict(grades["nfl_wind_totals"], past_window)

    print(f"NFL rule 2026 paper-track  season={season}  window {lo} .. {hi}")
    print("Policy: no unit bump; opener retire-if-flat-2026; "
          "wind MAX_FIRE_LEAD stays 4; do not unpause paused XGB props.")
    if settled_dates:
        print(f"Settled dates this run: {', '.join(settled_dates) or '(none)'}")
    print()
    for mid in MODELS:
        g = grades[mid]
        rec = f"{g['wins']}-{g['losses']}"
        if g["pushes"]:
            rec += f"-{g['pushes']}"
        roi = "n/a" if g["roi"] is None else f"{g['roi']:+.1f}%"
        print(f"{mid}")
        print(f"  standing settled BETs: {g['settled']}  {rec}  "
              f"{g['units']:+.2f}u  ROI {roi}  (priced {g['priced']}, "
              f"unpriced {g['unpriced_settled']})")
        print(f"  unsettled {g['unsettled']}  VOID {g['void']}  other {g['other']}")
        for r in g["rows"]:
            label = r.get("pick_label") or ""
            print(f"    {r.get('result')} {label}")
        print()
    print(f"nfl_opener_spread: {opener_v}")
    print(f"nfl_wind_totals:   {wind_v}")
    if past_window:
        print("Standing wind BETs locked past MAX_FIRE_LEAD (emission bug, "
              "do not widen the window):")
        for r in past_window:
            print(f"  lead {r['lead_days']}d  {r.get('pick_label')}")
    return {
        "season": season,
        "grades": grades,
        "opener_verdict": opener_v,
        "wind_verdict": wind_v,
        "past_window": past_window,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--settle", action="store_true",
                   help="run paper_tracker.settle_picks on unsettled dates, then report")
    args = p.parse_args(argv)

    settled_dates: list[str] | None = None
    if args.settle:
        settled_dates = settle_unsettled(args.season)

    from data.db import get_connection
    conn = get_connection()
    try:
        rows = fetch(conn, args.season)
    finally:
        conn.close()
    report(args.season, rows, settled_dates=settled_dates)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
