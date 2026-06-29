"""
Public parlay track record.

Logs ONE canonical parlay per (sport, game_date) — the day's top cross-game BET
picks — then settles it from the already-settled `opening_signals` legs and
publishes the record (win%, flat ROI, equity curve) on the mobile Track Record
screen. This is the "we publish our parlay record, wins and losses" trust wedge.

Why legs reference `opening_signals` lock_keys (not live pick_ids):
  The live `picks` table is delete+rescored every hourly refresh, so a pick's
  pick_id is unstable until game time. `opening_signals` already snapshots the
  first BET cross per game/market with a stable UNIQUE lock_key AND is settled
  game-by-game by settle_opening_signals(). So a tracked parlay = the top N
  game-level opening signals (distinct game, highest edge), and settling it is
  just reading those legs' results — no pick_id churn, no duplicated settlement.

Canonical parlay = up to PARLAY_LEGS game-level opening signals for the day,
distinct game_id, highest edge first, each with a real DK price. Locked once per
sport/day (ON CONFLICT DO NOTHING) — the "opening" recommendation, consistent
with the opening-signal philosophy. Cross-game legs are independent, so the
combined probability is the exact product (matches the app's engine, which only
adds correlation for same-game legs).

Shadow/parallel to the live paper-trading gate — never folded into settle totals.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

# Self-heal window: re-check unsettled parlays this many days back so one that was
# stuck (its legs settled late) settles on a later run instead of staying pending.
_PARLAY_SETTLE_WINDOW_DAYS = 21
from zoneinfo import ZoneInfo

from loguru import logger

from data.db import DBConnection, get_connection

# Model prefixes that are NOT settleable as game-level opening signals — excluded
# from parlay legs so every leg settles via settle_opening_signals (mirrors the
# _NON_GAME_PREFIXES filter in tracking/opening_signals.py).
_NON_GAME_PREFIXES = ("mlb_prop_", "wnba_prop_", "nba_prop_", "ufc_", "golf_", "mlb_live_")

PARLAY_LEGS = 3        # target legs; falls back to 2 when only 2 are eligible
MIN_PARLAY_LEGS = 2
PARLAY_FLAT_STAKE = 1.0  # one unit per parlay (flat-bet record)


def _american_to_decimal(odds: float) -> float:
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def _decimal_to_american(dec: float) -> float:
    return (dec - 1) * 100 if dec >= 2 else -100 / (dec - 1)


# ── Capture ─────────────────────────────────────────────────────────────────

def capture_parlay_track_record(target_date: str | None = None,
                                dry_run: bool = False) -> int:
    """
    Lock one canonical cross-game parlay per sport for target_date from that
    day's game-level opening signals. Idempotent (parlay_key UNIQUE) — the first
    run of the day locks it. Must run AFTER capture_opening_signals.

    Returns the number of NEW parlays locked.
    """
    if target_date is None:
        target_date = date.today().isoformat()

    not_game = " ".join(
        f"AND os.model_id NOT LIKE '{p}%%'" for p in _NON_GAME_PREFIXES
    )

    conn = get_connection()
    try:
        locked_at = datetime.now(ZoneInfo("America/New_York")).isoformat()

        # One row per eligible game-level opening signal, best edge first. We dedupe
        # to one leg per game_id in Python (keep the highest-edge market per game).
        rows = conn.execute(f"""
            SELECT os.sport, os.lock_key, os.game_id, os.pick_label,
                   os.model_probability, os.dk_odds, os.edge
            FROM opening_signals os
            WHERE os.game_date = %s
              AND os.dk_odds IS NOT NULL
              {not_game}
            ORDER BY os.sport, os.edge DESC
        """, (target_date,)).fetchall()

        # Group eligible legs by sport, one per game_id (highest edge wins).
        by_sport: dict[str, list] = {}
        for sport, lock_key, game_id, label, prob, dk_odds, edge in rows:
            legs = by_sport.setdefault(sport, [])
            if any(l["game_id"] == game_id for l in legs):
                continue  # already have a (higher-edge) leg for this game
            legs.append({
                "lock_key": lock_key, "game_id": game_id, "label": label,
                "prob": float(prob), "odds": float(dk_odds), "edge": float(edge),
            })

        new_locked = 0
        for sport, legs in by_sport.items():
            chosen = legs[:PARLAY_LEGS]
            if len(chosen) < MIN_PARLAY_LEGS:
                continue

            combined_decimal = 1.0
            model_prob = 1.0
            for l in chosen:
                combined_decimal *= _american_to_decimal(l["odds"])
                model_prob *= l["prob"]
            dk_implied = 1.0 / combined_decimal if combined_decimal > 0 else 0.0

            parlay_key = f"{sport}:{target_date}"
            if dry_run:
                logger.info(
                    f"[dry-run] {parlay_key}: {len(chosen)}-leg parlay "
                    f"{_decimal_to_american(combined_decimal):+.0f} "
                    f"model={model_prob:.3f} edge={model_prob - dk_implied:+.3f}"
                )
                continue

            cur = conn.execute("""
                INSERT INTO parlay_track_record (
                    parlay_key, sport, game_date, n_legs,
                    leg_keys, leg_labels, leg_odds,
                    combined_decimal, combined_american,
                    model_prob, dk_implied_prob, edge, locked_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (parlay_key) DO NOTHING
            """, (
                parlay_key, sport, target_date, len(chosen),
                json.dumps([l["lock_key"] for l in chosen]),
                json.dumps([l["label"] for l in chosen]),
                json.dumps([l["odds"] for l in chosen]),
                round(combined_decimal, 4),
                round(_decimal_to_american(combined_decimal), 1),
                round(model_prob, 4), round(dk_implied, 4),
                round(model_prob - dk_implied, 4), locked_at,
            ))
            # rowcount is unreliable through the wrapper; count via a follow-up.
            new_locked += 1

        if not dry_run:
            conn.commit()
            logger.info(
                f"Parlay track record: locked up to {new_locked} parlays for {target_date}"
            )
        return new_locked
    finally:
        conn.close()


# ── Settle ──────────────────────────────────────────────────────────────────

def settle_parlay_track_record(conn: DBConnection, game_date: str,
                               settled_at: str) -> tuple[int, int, int, float]:
    """
    Settle tracked parlays for game_date from their (already-settled)
    opening_signals legs. Standard parlay rules: any leg LOSS → parlay LOSS;
    PUSH/NO_ACTION legs drop out; remaining all-WIN → parlay WIN at the surviving
    legs' combined odds; all legs dropped → PUSH. Only settles once every leg has
    a result (no pending leg). Flat 1-unit stake.

    Must be called AFTER settle_opening_signals(game_date). Shadow track — NOT
    folded into the live settle totals.
    Returns (wins, losses, pushes, profit_flat).
    """
    # Trailing window (self-heal) so a parlay whose legs settled late isn't stuck.
    window_start = (datetime.strptime(game_date, "%Y-%m-%d")
                    - timedelta(days=_PARLAY_SETTLE_WINDOW_DAYS)).strftime("%Y-%m-%d")
    parlays = conn.execute("""
        SELECT id, leg_keys, leg_odds
        FROM parlay_track_record
        WHERE game_date >= %s AND result IS NULL
    """, (window_start,)).fetchall()

    wins = losses = pushes = 0
    total_flat = 0.0

    for parlay_id, leg_keys_json, leg_odds_json in parlays:
        leg_keys = json.loads(leg_keys_json)
        leg_odds = json.loads(leg_odds_json)

        leg_rows = conn.execute("""
            SELECT lock_key, result FROM opening_signals
            WHERE lock_key IN ({})
        """.format(",".join(["%s"] * len(leg_keys))), tuple(leg_keys)).fetchall()
        results = {k: r for k, r in leg_rows}

        # Every leg must be present and settled before we grade the parlay.
        if any(results.get(k) is None for k in leg_keys):
            continue

        odds_by_key = dict(zip(leg_keys, leg_odds))
        any_loss = any(results[k] == "LOSS" for k in leg_keys)
        surviving = [k for k in leg_keys if results[k] == "WIN"]

        if any_loss:
            result, profit_flat = "LOSS", -PARLAY_FLAT_STAKE
        elif not surviving:
            result, profit_flat = "PUSH", 0.0
        else:
            dec = 1.0
            for k in surviving:
                dec *= _american_to_decimal(float(odds_by_key[k]))
            result, profit_flat = "WIN", round((dec - 1) * PARLAY_FLAT_STAKE, 4)

        conn.execute("""
            UPDATE parlay_track_record
            SET result = %s, profit_flat = %s, settled_at = %s
            WHERE id = %s
        """, (result, profit_flat, settled_at, parlay_id))

        if result == "WIN":
            wins += 1
            total_flat += profit_flat
        elif result == "LOSS":
            losses += 1
            total_flat += profit_flat
        else:
            pushes += 1

    if wins + losses + pushes:
        logger.info(
            f"Parlay track record settle {game_date}: "
            f"{wins}W / {losses}L / {pushes}P (flat ${total_flat:+,.2f})"
        )
    return wins, losses, pushes, total_flat


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture the daily tracked parlay")
    parser.add_argument("--date", help="game_date YYYY-MM-DD (default today)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    capture_parlay_track_record(args.date, dry_run=args.dry_run)
