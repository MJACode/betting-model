"""The shadow-track de-duplicator deletes a duplicate and nothing else.

WHY THIS EXISTS (2026-09-11). Widening the publishing key
(`tracking/publish_keys.KEY_PARTS`) can leave a proposition holding TWO
`opening_signals` rows: the original under the old key shape, and one capture
wrote under the new shape. `scripts/backfill_publish_keys.py` refuses to re-key
into an occupied slot (#633) and logs the pair, so something has to clear it.

Measured on the set this shipped for: 15 `nfl_prop_market` shadow rows for 8
propositions. All seven duplicates carried ONE identical `locked_at` —
`2026-09-09 18:31:09.415888` — i.e. a single re-capture pass, not seven
crossings. The CLV track was double-counting them, and the surviving copy would
have reported the wrong signal time.

THE TESTS ARE ABOUT WHAT IT REFUSES TO DELETE. Getting the delete right is
easy; the risk in a script like this is entirely in the rows it should have
left alone. Each gate gets its own test, and each was watched failing.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import scripts.dedupe_opening_signals as dedupe


_SRC = Path(dedupe.__file__).read_text(encoding="utf-8")   # §7: explicit encoding


# ── the gates, read off the statement the script actually runs ───────────────

@pytest.mark.parametrize("field", [
    "pick_label", "pick_side", "dk_odds", "scored_line", "model_probability",
    "edge",
])
def test_every_field_that_defines_the_bet_must_agree(field):
    """Differ on any of these and the pair is two BETS, not one bet twice —
    which is a decision for a person, not a migration."""
    assert re.search(
        rf"n\.{field}\s+IS NOT DISTINCT FROM o\.{field}", dedupe._DUPES), (
        f"{field} is not compared, so the script could delete a row that is a "
        f"different bet from the one it keeps")


def test_the_row_kept_is_the_one_locked_earlier():
    """§1c: timing is data. The later row is a RE-CAPTURE of a proposition that
    had already crossed, stamped with the clock of the pass that re-read it."""
    assert "n.locked_at::timestamptz < o.locked_at::timestamptz" in dedupe._DUPES


@pytest.mark.parametrize("side", ["n", "o"])
def test_a_graded_row_is_never_deleted(side):
    """A settled outcome is a measurement. WIN/LOSS/PUSH on EITHER side of the
    pair takes the whole pair off the table."""
    assert (f"COALESCE({side}.result, '') NOT IN ('WIN', 'LOSS', 'PUSH')"
            in dedupe._DUPES)


@pytest.mark.parametrize("side", ["n", "o"])
def test_a_row_with_computed_clv_is_never_deleted(side):
    """A row already differenced against the close is an input to a published
    number; deleting it changes a measurement rather than a duplicate."""
    assert f"{side}.clv_pct IS NULL" in dedupe._DUPES


def test_the_pair_must_be_an_old_shape_new_shape_pair():
    """`n.lock_key LIKE o.lock_key || ':%'` is what makes this a key-migration
    duplicate rather than any two rows that happen to look alike. Without it a
    genuine same-bet-different-proposition row could be matched."""
    assert "n.lock_key LIKE o.lock_key || ':%'" in dedupe._DUPES


# ── the report must not contradict the delete ────────────────────────────────

def test_the_unresolved_report_excludes_what_the_delete_resolves():
    """ONE OLD KEY CAN MATCH SEVERAL NEW ONES, and that is not hypothetical: a
    game with two `nfl_prop_market` propositions has `<game>:nfl_prop_market`
    LIKE-matching both `…:jadarianprice:player_receptions` and
    `…:samdarnold:player_pass_completions`. The row is a true duplicate of the
    first and unrelated to the second.

    Found in the dry run against production before this shipped: the report
    printed "NOT touched — needs a person" for the exact row the same run
    deleted. A tool that contradicts itself in its own log is one an operator
    stops reading, so the exclusion is pinned.
    """
    assert "NOT IN (SELECT d.lock_key FROM (" in dedupe._UNRESOLVED, (
        "the unresolved report must exclude rows _DUPES already handles")


def test_the_report_and_the_delete_share_one_definition():
    """_UNRESOLVED embeds _DUPES rather than restating its gates, so the two
    cannot drift into disagreeing about what a duplicate is."""
    assert "{_DUPES}" in _SRC or dedupe._DUPES in dedupe._UNRESOLVED


# ── the shape of the script ──────────────────────────────────────────────────

def test_it_is_dry_run_by_default():
    """A destructive script whose default is to write is one that gets run by
    accident."""
    sig = re.search(r"def run\(apply: bool = (\w+)\)", _SRC)
    assert sig and sig.group(1) == "False"
    assert '"--apply"' in _SRC, "writing must be opt-in behind a flag"


def test_the_delete_selects_through_the_same_gates():
    """The DELETE must reuse _DUPES, not a hand-written WHERE that could be
    looser than the report the operator just read."""
    i = _SRC.index("DELETE FROM opening_signals")
    stmt = _SRC[i:_SRC.index('"""', i)]
    assert "{_DUPES}" in stmt, (
        "the DELETE must select through _DUPES so it cannot be looser than the "
        "dry run")
