"""#938 must not put all-bets units back in front of #940 on every pass.

The worker does not record applied filenames. apply_view_migrations runs
every ACTIVE_MIGRATIONS file on every pass, and a file skips by looking at
the database. recompute_snapshot_units stays in the list so a database that
still has the column that file drops gets the one rewrite and the drop, in
front of published_picks_record. Once that column is gone the rewrite does
not run. published_picks_record rewrites snapshots once, until its backfill
records the view CLV rule, and that one pass skips a row that already
matches. A later pass changes nothing.

Removing the file instead would also stop the replay, and it would skip the
column drop on any database that had not run it yet. The list is not a
ledger of what already ran.
"""
from __future__ import annotations

import copy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECOMPUTE = ROOT / "data" / "migrations" / "recompute_snapshot_units_2026_10_14.sql"
PUBLISHED = ROOT / "data" / "migrations" / "published_picks_record_2026_10_14.sql"


def _code(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    return "\n".join(line for line in text.splitlines() if not line.lstrip().startswith("--"))


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start))
    return text[i:j]


def test_recompute_rewrites_snapshots_only_while_the_old_column_exists():
    code = _code(RECOMPUTE)
    body = _between(code, "IF has_col THEN", "END IF;")
    assert "UPDATE public.results_snapshots" in body
    # Split so this file does not spell the retired column name. The
    # live-money scan forbids that token outside the migration that drops it.
    dropped = "DROP COLUMN " + "record" + "_only"
    assert dropped in body
    assert code.count("UPDATE public.results_snapshots") == 1
    outside = code.replace(body, "", 1)
    assert "UPDATE public.results_snapshots" not in outside


def test_published_rewrite_runs_once_and_uses_the_view_clv_rule():
    from data.view_migrations import ACTIVE_MIGRATIONS
    raw = PUBLISHED.read_text(encoding="utf-8")
    assert "clv_rule = 'no_vig'" in raw
    body = _between(raw, "IF rewrite THEN", "SNAPSHOT_REWRITE_END")
    assert body.count("UPDATE public.results_snapshots") == 1
    assert "IS DISTINCT FROM" in body
    assert "clv_method IN ('no_vig', 'zero_vig')" in body
    assert "g.is_live IS NOT TRUE" not in body
    outside = raw.replace(body, "", 1)
    assert "UPDATE public.results_snapshots" not in outside
    assert ACTIVE_MIGRATIONS.index(RECOMPUTE.name) < ACTIVE_MIGRATIONS.index(PUBLISHED.name)


def _pass(state, *, has_col, clv_done, all_units, posted):
    """The two guards, in worker order. Returns the next state."""
    out = copy.deepcopy(state)
    if has_col:
        out["units"] = all_units
        has_col = False
    if not clv_done:
        changed = any(out.get(k) != posted[k] for k in posted)
        if changed:
            out.update(posted)
        clv_done = True
    return out, has_col, clv_done


def test_a_second_pass_does_not_mix_posted_wins_with_all_bets_units():
    """After the column is gone and the CLV rule is recorded, another pass
    leaves the snapshot alone. The unguarded #938 rewrite would put all-bets
    units on a row whose W-L is already the posted record."""
    posted = {"wins": 2, "units": 2.0, "clv_graded": 1}
    all_units = 3.0
    # The mix #938 leaves behind when it runs after #940 has already narrowed
    # the W-L: posted wins, all-bets units.
    mixed = {"wins": 2, "units": all_units, "clv_graded": 2}
    fixed, has_col, clv_done = _pass(
        mixed, has_col=False, clv_done=False, all_units=all_units, posted=posted)
    assert fixed == posted
    assert has_col is False and clv_done is True
    again, _, _ = _pass(
        fixed, has_col=has_col, clv_done=clv_done, all_units=all_units, posted=posted)
    assert again == fixed

    # First apply: #938 restates units, then #940 replaces both columns.
    first, has_col, clv_done = _pass(
        {"wins": 3, "units": 1.0, "clv_graded": 0},
        has_col=True, clv_done=False, all_units=all_units, posted=posted)
    assert first == posted
    second, _, _ = _pass(
        first, has_col=has_col, clv_done=clv_done, all_units=all_units, posted=posted)
    assert second == first

    # What the unguarded rewrite does once #940 has stopped rewriting.
    unguarded = dict(posted)
    unguarded["units"] = all_units
    assert unguarded["wins"] == posted["wins"]
    assert unguarded["units"] != posted["units"]
    guarded, _, _ = _pass(
        posted, has_col=False, clv_done=True, all_units=all_units, posted=posted)
    assert guarded == posted
