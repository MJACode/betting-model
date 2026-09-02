"""
Restore the FIRST BET signal as the bet of record.

THE RULE (Matt, 2026-08-29): *a pick is a pick.* Once a model produces a BET,
that pick existed at that line, at that price, at that moment. If the line then
moves so the model would no longer take it, that is LINE MOVEMENT — it does not
retract the bet. The number you were given is the number you were given, and
the timing is the whole point.

Every lock in this repo implements that rule going forward:
`LOCK_GAME_PICKS_AT_FIRST_RUN`, `LOCK_PROP_PICKS_AT_FIRST_SIGNAL`,
`LOCK_LIVE_PICKS_AT_FIRST_SIGNAL`, and the §28 NFL rules, which are insert-once
by construction and are the model the rest were built to match.

This module is the BACKWARD-looking half: where delete-and-replace ran before a
lock covered it, the original pick is not lost — the `picks_log` audit trigger
recorded every INSERT and DELETE. This reads the first BET back out and restores
it, so the record and the published signal both show the bet that was actually
made rather than the last one the churn happened to leave behind.

Worked example, and why this exists. NCAAF live, 2026-08-29:

    16:14:38  INSERT  Over 44.5  -115   <- the bet of record
    16:15:31  DELETE  Over 44.5
    16:15:31  INSERT  Over 45.5  -115
    ...       (delete + insert every ~45s)
    16:41:12  INSERT  Over 54.5  -120   <- what survived, ten points later

A user told to take Over 44.5 at -115 was not told to take Over 54.5. The
second is a different bet. Only the first one ever existed as a signal.

Idempotent: restoring an already-correct lane is a no-op, so this is safe to
run on every pass.
"""

from __future__ import annotations

import argparse
from datetime import date

from loguru import logger

import config
from data.db import get_connection, DBConnection


# picks_log carries no is_live column (the audit trigger predates it), so a
# restored live pick would come back as a PRE-GAME row: invisible to the Live
# tab and to notify_discord_live, both of which filter is_live = TRUE. Set it
# from the model id, which is the only signal available.
_LIVE_MODEL_IDS = frozenset(getattr(config, "LIVE_MODELS", {}))

# Columns copied verbatim from the audit row. created_at is deliberately
# included: the pick's timing IS its meaning, and restoring it with today's
# clock would misreport when the number was available.
_COPY_COLS = (
    "game_id", "model_id", "sport", "game_date", "game_time", "pick_side",
    "pick_label", "model_probability", "dk_implied_prob", "edge", "dk_odds",
    "scored_line", "kelly_fraction", "recommended_bet", "bankroll_at_pick",
    "injury_flag", "injury_detail", "signal_type", "confidence_tier",
    "created_at",
)


def _first_bets(conn: DBConnection, game_date: str,
                models: tuple[str, ...] | None) -> list[dict]:
    """The earliest BET insert per (game_id, model_id, pick_side) for the date.

    DISTINCT ON over logged_at ASC — the audit log is append-only, so the first
    INSERT row for a lane/side is by definition the first time that pick existed.
    """
    model_pred = "AND l.model_id = ANY(%(models)s)" if models else ""
    rows = conn.execute(f"""
        SELECT DISTINCT ON (l.game_id, l.model_id, l.pick_side)
               {', '.join('l.' + c for c in _COPY_COLS)}, l.logged_at
        FROM picks_log l
        WHERE l.game_date = %(d)s
          AND l.operation = 'INSERT'
          AND l.signal_type = 'BET'
          {model_pred}
        ORDER BY l.game_id, l.model_id, l.pick_side, l.logged_at ASC
    """, {"d": game_date, "models": list(models) if models else None}).fetchall()
    return [dict(zip(_COPY_COLS + ("logged_at",), r)) for r in rows]



def _sibling_rows(conn: DBConnection, first: dict) -> list[dict]:
    """The rest of the lane as it stood when the first BET was written.

    A totals/moneyline pass writes BOTH sides together — the BET and the
    complementary AVOID at the same line, in one insert. Restoring only the BET
    side leaves the opposite side stranded at whatever line the churn last
    wrote, so the board shows 'Over 44.5' beside 'Under 54.5': two different
    propositions presented as one lane. §21 is explicit that the complementary
    AVOID freezes with its BET, so the whole lane is restored as one unit.

    Matched on logged_at, not merely on lane, so this picks up the sides written
    in the SAME pass rather than any later re-price.
    """
    rows = conn.execute(f"""
        SELECT {', '.join('l.' + c for c in _COPY_COLS)}, l.logged_at
        FROM picks_log l
        WHERE l.game_id = %(g)s AND l.model_id = %(m)s
          AND l.operation = 'INSERT'
          AND l.logged_at = %(t)s
          AND l.pick_side <> %(s)s
    """, {"g": first["game_id"], "m": first["model_id"],
          "t": first["logged_at"], "s": first["pick_side"]}).fetchall()
    return [dict(zip(_COPY_COLS + ("logged_at",), r)) for r in rows]


def _standing(conn: DBConnection, game_id: str, model_id: str,
              pick_side: str) -> dict | None:
    """The unsettled pick currently occupying that lane/side, if any."""
    r = conn.execute("""
        SELECT pick_id, scored_line, dk_odds, pick_label, created_at
        FROM picks
        WHERE game_id = %(g)s AND model_id = %(m)s AND pick_side = %(s)s
          AND result IS NULL
        ORDER BY created_at ASC
        LIMIT 1
    """, {"g": game_id, "m": model_id, "s": pick_side}).fetchone()
    if r is None:
        return None
    return {"pick_id": r[0], "scored_line": r[1], "dk_odds": r[2],
            "pick_label": r[3], "created_at": r[4]}


def _same_bet(first: dict, standing: dict) -> bool:
    """Is the standing row already the original bet?

    Compared on the two things that define the proposition — the line and the
    price — not on the label, which carries the line as text and would make the
    comparison circular, nor on pick_id, which changes on every re-insert.
    """
    def _n(v):
        return None if v is None else round(float(v), 4)
    return (_n(first["scored_line"]) == _n(standing["scored_line"])
            and _n(first["dk_odds"]) == _n(standing["dk_odds"]))


def restore_first_signals(game_date: str | None = None,
                          models: tuple[str, ...] | None = None,
                          dry_run: bool = False,
                          renotify: bool = True) -> int:
    """Put the first BET back as the standing pick wherever churn replaced it.

    Returns the number of lanes repaired. Safe to call on every pass: a lane
    whose standing pick already IS the first bet is skipped without a write.
    """
    game_date = game_date or date.today().isoformat()
    conn = get_connection()
    repaired = 0
    try:
        for first in _first_bets(conn, game_date, models):
            gid, mid, side = first["game_id"], first["model_id"], first["pick_side"]
            standing = _standing(conn, gid, mid, side)
            if standing is not None and _same_bet(first, standing):
                continue                      # already the bet of record

            was = (f"{standing['pick_label']} @ {standing['dk_odds']}"
                   if standing else "nothing standing")
            logger.warning(
                f"first-signal repair: {gid}/{mid}/{side} — restoring "
                f"'{first['pick_label']}' @ {first['dk_odds']} "
                f"(first seen {first['logged_at']}); displacing {was}"
            )
            if dry_run:
                repaired += 1
                continue

            # Remove only the rows that exist BECAUSE the original was deleted.
            # Settled rows are never touched: a graded pick is history.
            conn.execute("""
                DELETE FROM picks
                WHERE game_id = %(g)s AND model_id = %(m)s AND pick_side = %(s)s
                  AND result IS NULL
            """, {"g": gid, "m": mid, "s": side})

            # Restore the WHOLE lane as it stood in that pass -- the BET and
            # the complementary AVOID together. Restoring the BET alone leaves
            # the other side stranded at the churned line.
            for row in [first] + _sibling_rows(conn, first):
                if row is not first:
                    conn.execute("""
                        DELETE FROM picks
                        WHERE game_id = %(g)s AND model_id = %(m)s
                          AND pick_side = %(s)s AND result IS NULL
                    """, {"g": gid, "m": mid, "s": row["pick_side"]})
                cols = list(_COPY_COLS)
                vals = {c: row[c] for c in cols}
                if mid in _LIVE_MODEL_IDS:
                    cols.append("is_live")
                    vals["is_live"] = True
                conn.execute(
                    f"INSERT INTO picks ({', '.join(cols)}) "
                    f"VALUES ({', '.join('%(' + c + ')s' for c in cols)})", vals)

            if renotify:
                # The wrong number may already have been announced. Clearing the
                # ledger lets the corrected pick post; the stale message is
                # removed separately (Discord gives no way to edit a webhook
                # post we did not capture an id for).
                conn.execute("""
                    DELETE FROM push_sent
                    WHERE lock_key = %(k)s
                      AND kind IN ('discord_live', 'live_signal')
                """, {"k": f"live:{gid}:{mid}:{side}"})
            repaired += 1

        if not dry_run and repaired:
            conn.commit()
        logger.info(f"first-signal repair: {repaired} lane(s) restored "
                    f"for {game_date}")
        return repaired
    finally:
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=None, help="game_date (default: today)")
    ap.add_argument("--models", nargs="*", default=None,
                    help="restrict to these model_ids")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-renotify", action="store_true",
                    help="repair the row but leave the notification ledger")
    a = ap.parse_args()
    restore_first_signals(a.date, tuple(a.models) if a.models else None,
                          a.dry_run, not a.no_renotify)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
