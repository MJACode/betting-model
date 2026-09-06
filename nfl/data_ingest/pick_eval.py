"""
Per-tick model evaluation dump — the raw material for locked-pick history.

Both live cards already fetch a full board on every run and then keep only the
qualifying bets. This module records what the model thought about EVERY game it
looked at, qualifying or not, so the platform can answer a question the cards
alone cannot:

    "This pick locked on Tuesday. Does it still qualify right now, and if not,
     what changed?"

The pick itself is immutable once locked. Nothing here can retract a bet — the
money went down at the locked number. This is the audit trail beside it, and
`scripts/nfl_pick_monitor.py` is what turns these rows into history and into
the loud flag on a pick whose conditions have collapsed.

Zero extra API credits: this reuses the payload the card already paid for.

One row per (game, model) per tick, written to
`data/cards/pick_eval_YYYY-MM-DD.csv` and appended across ticks, because a tick
is an observation and observations accumulate.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

# Both publishers write `picks.game_id` as "NFL_" + the nflverse id
# (scripts/nfl_wind_publisher.py, and its docstring at line 12). This dump is
# joined to `picks` on that column, so it has to speak the same id.
#
# It did not, for its whole life. The models hand `evaluate_board` the bare
# nflverse id, this module wrote it through unchanged under a field comment
# claiming it was "the join key to picks", and
# scripts/nfl_pick_monitor.latest_per_pick keyed the dump on it. Every lookup
# missed. Measured 2026-09-06: `nfl_pick_status_history` held 0 rows for every
# model, `picks.condition_status` was NULL on all five live wind picks, and the
# worker logged "0 locked pick(s) observed" hourly and exited 0 -- which is
# exactly what a quiet week looks like.
#
# Normalised HERE rather than in each model, because both wind and opener feed
# this one helper and the opener would otherwise have to be fixed separately.
_PICKS_ID_PREFIX = "NFL_"


def _picks_game_id(game_id: str) -> str:
    """The nflverse id as `picks.game_id` holds it. Idempotent."""
    gid = str(game_id)
    return gid if gid.startswith(_PICKS_ID_PREFIX) else _PICKS_ID_PREFIX + gid


EVAL_CSV_FIELDS = [
    "game_id",         # "NFL_" + nflverse id -- the join key to picks.game_id
    "model_id",        # nfl_wind_totals | nfl_opener_spread
    "observed_at",     # ISO-8601 UTC, the tick
    "kick_utc",
    "lead_hours",      # hours to kickoff at this tick
    "qualifies",       # "1" / "0" — would the model take this bet RIGHT NOW
    "reason",          # human-readable; why not, or why yes
    "current_line",    # total (wind) or soft home spread (opener)
    "current_price",   # American price on the model's side
    "current_book",
    "model_prob",
    "edge",
]

CARDS_DIR = Path("data/cards")


def eval_row(game_id: str, model_id: str, kick_utc, lead_hours,
             qualifies: bool, reason: str, current_line=None,
             current_price=None, current_book=None, model_prob=None,
             edge=None, observed_at: str | None = None) -> dict:
    """Build one evaluation row. Nulls are fine — a game with no quote at all
    is itself an observation worth keeping."""
    def _num(v):
        return "" if v is None else v
    return {
        "game_id": _picks_game_id(game_id),
        "model_id": model_id,
        "observed_at": observed_at or datetime.now(timezone.utc).isoformat(),
        "kick_utc": str(kick_utc),
        "lead_hours": "" if lead_hours is None else round(float(lead_hours), 2),
        "qualifies": "1" if qualifies else "0",
        "reason": reason,
        "current_line": _num(current_line),
        "current_price": _num(current_price),
        "current_book": _num(current_book),
        "model_prob": _num(model_prob),
        "edge": _num(edge),
    }


def dump_eval_rows(rows: list[dict], run_date: str | None = None) -> Path | None:
    """
    APPEND rows to today's evaluation CSV. Appending, not overwriting: several
    ticks land on the same date and each is a separate observation.

    Never raises — this is enrichment, and a bet card must not die because an
    audit file could not be written.
    """
    if not rows:
        return None
    try:
        run_date = run_date or datetime.now(timezone.utc).date().isoformat()
        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        path = CARDS_DIR / f"pick_eval_{run_date}.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=EVAL_CSV_FIELDS)
            if new:
                w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in EVAL_CSV_FIELDS})
        return path
    except Exception as exc:                                   # noqa: BLE001
        import sys
        print(f"WARNING: pick-eval dump failed: {exc}", file=sys.stderr)
        return None


BOARD_CSV_FIELDS = ["snapshot_at", "commence_time", "home", "away", "bookmaker",
                    "market", "point", "price_home", "price_away"]


def dump_board(frame, run_date: str | None = None) -> Path | None:
    """
    Persist the WHOLE board this tick saw — every book, every market — so the
    odds history keeps growing without another API call.

    The cards pay for a full-sport pull on every tick and then keep only the
    qualifying bets. `line_snapshots.py` already skims DraftKings off that
    payload for the app's movement chip; this keeps everything, which is what
    the models and any future prop work actually need. Zero extra credits.

    Long format, one row per (book, market) per game, both sides on the row —
    the same grain as nfl_odds_history so the publisher can insert it directly.
    """
    if frame is None or len(frame) == 0:
        return None
    try:
        import pandas as pd
        run_date = run_date or datetime.now(timezone.utc).date().isoformat()
        now = datetime.now(timezone.utc).isoformat()

        d = frame[frame.market.isin(("spreads", "totals", "h2h"))].copy()
        if d.empty:
            return None
        first = d[d.side.isin(("home", "Over"))][
            ["event_id", "commence_time", "home", "away", "book", "market",
             "point", "price"]].rename(columns={"price": "price_home"})
        second = d[d.side.isin(("away", "Under"))][
            ["event_id", "book", "market", "price"]].rename(
                columns={"price": "price_away"})
        m = first.merge(second.drop_duplicates(["event_id", "book", "market"]),
                        on=["event_id", "book", "market"], how="left")
        m["snapshot_at"] = now
        m = m.rename(columns={"book": "bookmaker"})

        CARDS_DIR.mkdir(parents=True, exist_ok=True)
        path = CARDS_DIR / f"board_{run_date}.csv"
        new = not path.exists()
        with path.open("a", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=BOARD_CSV_FIELDS)
            if new:
                w.writeheader()
            for r in m.to_dict("records"):
                w.writerow({k: ("" if r.get(k) is None else r.get(k))
                            for k in BOARD_CSV_FIELDS})
        return path
    except Exception as exc:                                   # noqa: BLE001
        import sys
        print(f"WARNING: board dump failed: {exc}", file=sys.stderr)
        return None
