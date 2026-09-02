#!/usr/bin/env python3
"""
Locked NFL picks: record what happened after the lock. Never re-price.

    python -m scripts.nfl_pick_monitor              # today's evaluation dump
    python -m scripts.nfl_pick_monitor --date 2026-09-20

THE RULE THIS ENFORCES
----------------------
A pick is IMMUTABLE from the moment it locks. The bet went down at that line,
at that price, at that book, at that timestamp, and nothing later can retract
it — that is what betting is. What can and must change is our *description* of
whether the conditions that justified it still hold.

So this module never updates `picks.scored_line`, `dk_odds`, `model_probability`
or anything else about the bet. It writes:

  * one `nfl_pick_status_history` row per locked pick per tick, and
  * a loud flag on the pick (`condition_status` / `condition_note` /
    `condition_checked_at`) so a collapsed forecast or a corrected line is
    visible in the app rather than silently deleted.

STATUS LADDER
-------------
  OK        conditions still hold; the model would take this bet again now
  DEGRADED  it no longer qualifies, but not dramatically — the line moved
            against us, or the edge has been eaten by juice
  GONE      the premise is gone: the wind forecast collapsed below threshold,
            or the soft book's number has been corrected to Pinnacle's

GONE is the case worth staring at. It does NOT mean the bet was wrong — the
edge was measured at the moment of the lock, and for the opener a corrected
line is the market agreeing with us, which is a GOOD sign for the bet. It means
you should not add to it, and it is the raw material for asking later whether
locking early was right.

Input is `nfl/data/cards/pick_eval_YYYY-MM-DD.csv`, appended by both live cards
on every tick at zero extra API credits.
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CARDS_DIR = ROOT / "nfl" / "data" / "cards"

NFL_MODEL_IDS = ("nfl_wind_totals", "nfl_opener_spread")

# Phrases in a model's `reason` that mean the premise itself is gone, not just
# that the price drifted. Kept as substrings so the models stay free to word
# their reasons naturally.
_GONE_MARKERS = (
    "below the",              # wind fell under threshold / dev under threshold
    "beyond the",             # lead outside the calibrated range
    "no forecast",
    "no total quoted",
    "no spread quotes",
    "no clean soft book",
    "zero units",
)


def read_eval_rows(run_date: str) -> list[dict]:
    path = CARDS_DIR / f"pick_eval_{run_date}.csv"
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def latest_per_pick(rows: list[dict]) -> dict[tuple[str, str], dict]:
    """
    Last observation per (game_id, model_id). A date's CSV holds every tick, so
    the newest row is the current state; the rest are history and are written
    as such.
    """
    out: dict[tuple[str, str], dict] = {}
    for r in rows:
        key = (r.get("game_id", ""), r.get("model_id", ""))
        prev = out.get(key)
        if prev is None or (r.get("observed_at") or "") >= (prev.get("observed_at") or ""):
            out[key] = r
    return out


def classify(row: dict) -> tuple[bool, str, str]:
    """(still_qualifies, status, reason) for one evaluation row."""
    qualifies = str(row.get("qualifies", "0")) == "1"
    reason = (row.get("reason") or "").strip()
    if qualifies:
        return True, "OK", reason
    low = reason.lower()
    if any(m in low for m in _GONE_MARKERS):
        return False, "GONE", reason
    return False, "DEGRADED", reason


def _f(v):
    try:
        return float(v) if v not in (None, "", "nan") else None
    except (TypeError, ValueError):
        return None


def monitor(run_date: str | None = None) -> int:
    """Write history + flags for every unstarted locked NFL pick. Returns rows written."""
    from data.db import get_connection

    if run_date is None:
        run_date = datetime.now(timezone.utc).date().isoformat()

    rows = read_eval_rows(run_date)
    if not rows:
        print(f"NFL pick monitor {run_date}: no evaluation dump — nothing to do")
        return 0
    current = latest_per_pick(rows)

    conn = get_connection()
    written = 0
    try:
        picks = conn.execute("""
            SELECT p.pick_id, p.game_id, p.model_id, p.created_at, g.commence_time
            FROM picks p
            LEFT JOIN games g ON g.game_id = p.game_id
            WHERE p.sport = 'NFL'
              AND p.model_id = ANY(%s)
              AND p.result IS NULL
        """, (list(NFL_MODEL_IDS),)).fetchall()

        now_iso = datetime.now(timezone.utc).isoformat()
        for pk in picks:
            pick_id, game_id, model_id = pk[0], pk[1], pk[2]
            row = current.get((game_id, model_id))
            if row is None:
                continue                      # not on this tick's board; say nothing
            still, status, reason = classify(row)

            conn.execute("""
                INSERT INTO nfl_pick_status_history
                    (pick_id, game_id, model_id, observed_at, lead_hours,
                     still_qualifies, status, reason, current_line, current_price,
                     current_book, model_prob_now, edge_now)
                VALUES (%(pick_id)s, %(game_id)s, %(model_id)s, %(observed_at)s,
                        %(lead_hours)s, %(still_qualifies)s, %(status)s, %(reason)s,
                        %(current_line)s, %(current_price)s, %(current_book)s,
                        %(model_prob_now)s, %(edge_now)s)
                ON CONFLICT (pick_id, observed_at) DO NOTHING
            """, {
                "pick_id": pick_id, "game_id": game_id, "model_id": model_id,
                "observed_at": row.get("observed_at") or now_iso,
                "lead_hours": _f(row.get("lead_hours")),
                "still_qualifies": still, "status": status, "reason": reason,
                "current_line": _f(row.get("current_line")),
                "current_price": _f(row.get("current_price")),
                "current_book": (row.get("current_book") or None),
                "model_prob_now": _f(row.get("model_prob")),
                "edge_now": _f(row.get("edge")),
            })

            # The flag on the pick. NOTHING about the bet itself is touched.
            conn.execute("""
                UPDATE picks
                SET condition_status = %s, condition_note = %s, condition_checked_at = %s
                WHERE pick_id = %s
            """, (status, reason[:500], now_iso, pick_id))
            written += 1

        conn.commit()
    finally:
        conn.close()

    print(f"NFL pick monitor {run_date}: {written} locked pick(s) observed")
    return written


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="UTC run date (default: today)")
    a = ap.parse_args()
    try:
        monitor(a.date)
    except Exception as exc:                                   # noqa: BLE001
        # A monitoring step must never take the pipeline down: the bets are
        # already locked and correct without it. But say WHY loudly, because a
        # silent no-op here looks exactly like "nothing changed".
        msg = str(exc)
        if "nfl_pick_status_history" in msg or "condition_status" in msg:
            print("NFL pick monitor: schema not applied yet. The locked-pick "
                  "history table and the picks.condition_* columns are additive "
                  "and are created by:\n"
                  "    python -m data.db_setup\n"
                  "Picks and locks are unaffected until then; only the history "
                  "and the condition flag are missing.", file=sys.stderr)
        else:
            print(f"NFL pick monitor failed: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    # API telemetry for the live monitor (monitoring/). Guarded: this package is
    # standalone, and the repo root only reaches sys.path when the scheduler
    # supplies PYTHONPATH — run on its own it simply records nothing.
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("nfl-pick-monitor")
    except Exception:  # noqa: BLE001
        pass

    raise SystemExit(main())
