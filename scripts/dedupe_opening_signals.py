"""Remove a shadow row that a key migration left behind as a duplicate.

WHAT THIS IS FOR. `opening_signals` is the CLV / opening-signal shadow track,
UNIQUE on `lock_key`, one row per proposition. When the publishing key gained
components (`tracking/publish_keys.KEY_PARTS`, 2026-09-09), a proposition could
end up holding TWO rows: the original under the OLD key shape, and a second one
that `capture_opening_signals` wrote under the NEW shape. The pair is the same
bet at the same number — so the track double-counts it, and one of the two
carries a `locked_at` that is not when the signal actually crossed.

`scripts/backfill_publish_keys.py` deliberately REFUSES to re-key into an
occupied slot (#633, after job 47297 rolled back three times on
`opening_signals_lock_key_key`) and logs the pair instead. This script is the
other half: it clears the duplicate once someone has confirmed the two rows are
the same bet.

WHICH ROW GOES, AND WHY IT IS NOT A JUDGEMENT CALL. The row kept is the one
whose `locked_at` is EARLIER. §1c: "timing is data, not metadata" — `locked_at`
is when the number was available and is part of the signal's meaning. The later
row is a RE-CAPTURE of a proposition that had already crossed, stamped with the
clock of the pass that re-read it, which is precisely what §1c says misreports
the bet. Measured on the 2026-09-09 set: all seven later rows carried one
identical timestamp, 18:31:09.415888 — a single capture pass, not seven
crossings.

FOUR GATES, and the script deletes NOTHING that fails any of them:

  1. The surviving partner is keyed as the old key plus a suffix, so the pair is
     genuinely an old-shape/new-shape pair and not two unrelated propositions.
  2. The two rows agree on EVERY field that defines the bet — pick_label,
     pick_side, dk_odds, scored_line, model_probability, edge. Differ anywhere
     and this is two bets, which is a decision, not a migration.
  3. Neither row carries a graded result (WIN / LOSS / PUSH). A settled outcome
     is a measurement; deleting one rewrites the record. NO_ACTION and NULL are
     allowed — neither contributes to a record.
  4. Neither row carries a computed `clv_pct`. A row that has already been
     differenced against the close is an input to a published number.

So a pair that has since been graded, or whose two halves have drifted apart,
is REPORTED and left alone rather than silently resolved.

Dry-run by default; `--apply` writes. Idempotent — a second run finds nothing.

    python -m scripts.dedupe_opening_signals            # show what would go
    python -m scripts.dedupe_opening_signals --apply    # delete it
"""
from __future__ import annotations

import argparse

from loguru import logger

from data.db import get_connection

# A duplicate: an `opening_signals` row whose proposition ALSO has a row under a
# longer key that is the same bet, locked earlier, and ungraded on both sides.
# `n.lock_key LIKE o.lock_key || ':%'` is what makes the pair an old/new SHAPE
# pair rather than any two rows that happen to look alike.
_DUPES = """
    SELECT o.lock_key, o.pick_label, o.locked_at, o.result,
           n.lock_key AS keeps, n.locked_at AS keeps_locked_at
    FROM opening_signals o
    JOIN opening_signals n
      ON n.lock_key LIKE o.lock_key || ':%'
     AND n.pick_label        IS NOT DISTINCT FROM o.pick_label
     AND n.pick_side         IS NOT DISTINCT FROM o.pick_side
     AND n.dk_odds           IS NOT DISTINCT FROM o.dk_odds
     AND n.scored_line       IS NOT DISTINCT FROM o.scored_line
     AND n.model_probability IS NOT DISTINCT FROM o.model_probability
     AND n.edge              IS NOT DISTINCT FROM o.edge
     AND n.locked_at::timestamptz < o.locked_at::timestamptz
     AND COALESCE(n.result, '') NOT IN ('WIN', 'LOSS', 'PUSH')
     AND n.clv_pct IS NULL
    WHERE COALESCE(o.result, '') NOT IN ('WIN', 'LOSS', 'PUSH')
      AND o.clv_pct IS NULL
"""

# Pairs that share a proposition but fail a gate — same old/new key shape, but
# the bet differs, or something is graded. Reported so they are not invisible.
#
# EXCLUDES anything _DUPES already resolves, and that exclusion is load-bearing
# rather than tidiness. One old key can LIKE-match SEVERAL new keys: a game with
# two `nfl_prop_market` propositions has `<game>:nfl_prop_market` matching both
# `…:jadarianprice:player_receptions` and `…:samdarnold:player_pass_completions`.
# The row is a true duplicate of the first and unrelated to the second, so
# without this the script would print "NOT touched — needs a person" about a row
# it deletes in the same run. A tool that contradicts itself in its own log is
# one an operator stops reading.
_UNRESOLVED = f"""
    SELECT o.lock_key, n.lock_key AS partner, o.pick_label, n.pick_label,
           o.result, n.result
    FROM opening_signals o
    JOIN opening_signals n ON n.lock_key LIKE o.lock_key || ':%'
    WHERE o.lock_key NOT IN (SELECT d.lock_key FROM ({_DUPES}) d)
      AND NOT (
        n.pick_label        IS NOT DISTINCT FROM o.pick_label
    AND n.pick_side         IS NOT DISTINCT FROM o.pick_side
    AND n.dk_odds           IS NOT DISTINCT FROM o.dk_odds
    AND n.scored_line       IS NOT DISTINCT FROM o.scored_line
    AND n.model_probability IS NOT DISTINCT FROM o.model_probability
    AND n.edge              IS NOT DISTINCT FROM o.edge
    AND n.locked_at::timestamptz < o.locked_at::timestamptz
    AND COALESCE(n.result, '') NOT IN ('WIN', 'LOSS', 'PUSH')
    AND COALESCE(o.result, '') NOT IN ('WIN', 'LOSS', 'PUSH')
    AND n.clv_pct IS NULL AND o.clv_pct IS NULL
    )
"""


def run(apply: bool = False) -> int:
    """Returns the number of duplicate rows removed (or that would be)."""
    with get_connection() as conn:
        dupes = conn.execute(_DUPES).fetchall()
        unresolved = conn.execute(_UNRESOLVED).fetchall()

        for key, partner, olabel, nlabel, ores, nres in unresolved:
            logger.warning(
                f"NOT touched — {key} and {partner} share a proposition but "
                f"fail a gate (labels {olabel!r} / {nlabel!r}; results "
                f"{ores} / {nres}). Needs a person.")

        for key, label, locked, result, keeps, keeps_locked in dupes:
            logger.info(f"delete {key}  ({label}, locked {locked}, "
                        f"result {result}) — keeping {keeps} locked "
                        f"{keeps_locked}")

        if not dupes:
            logger.info("no duplicate shadow rows")
            return 0
        if not apply:
            logger.info(f"[dry-run] would delete {len(dupes)} row(s); "
                        f"re-run with --apply")
            return len(dupes)

        conn.execute(f"""
            DELETE FROM opening_signals
             WHERE lock_key IN (SELECT lock_key FROM ({_DUPES}) d)
        """)
        conn.commit()
        logger.success(f"deleted {len(dupes)} duplicate shadow row(s)")
        return len(dupes)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="write the deletion (default is a dry run)")
    args = ap.parse_args()
    run(apply=args.apply)
