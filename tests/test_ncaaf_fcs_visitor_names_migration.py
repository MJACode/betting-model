"""
The one-off that renames nine NCAAF visitors, writes their finals, and fixes
44 pick labels -- pinned the way the other worker-applied migrations are.

Nine games rows written 2026-09-03..06 name an FCS visitor as the FBS school
its name starts with (the resolver bug fixed in the same PR). Six live-total
BETs were published under those names. mike, 2026-09-07: "fix the labels ...
settle the picks". The migration runs from the worker's own pass, because the
Supabase connector available to sessions is read-only.
"""
from __future__ import annotations

import re
from pathlib import Path

MIG = Path(__file__).parent.parent / "data/migrations/ncaaf_fcs_visitor_names_2026_09_07.sql"
CODE = MIG.read_text(encoding="utf-8")

# (wrong visitor, real visitor, home score, away score) as measured against the
# CFBD rows on 2026-09-07. Idaho State WON at Utah State, which is why home_win
# is derived in the migration rather than typed.
EXPECTED = {
    "NCAAF_2026-09-03_arkansas_missouri":            ("Arkansas",       "Arkansas-Pine Bluff", 54, 14),
    "NCAAF_2026-09-04_indiana_purdue":               ("Indiana",        "Indiana State",       44, 19),
    "NCAAF_2026-09-04_north-carolina_georgia-state": ("North Carolina", "North Carolina A&T",  59, 10),
    "NCAAF_2026-09-05_tennessee_georgia":            ("Tennessee",      "Tennessee State",     63,  3),
    "NCAAF_2026-09-05_houston_rice":                 ("Houston",        "Houston Christian",   31,  3),
    "NCAAF_2026-09-05_northwestern_louisiana-tech":  ("Northwestern",   "Northwestern State",  80,  6),
    "NCAAF_2026-09-05_utah_byu":                     ("Utah",           "Utah Tech",           63,  7),
    "NCAAF_2026-09-06_utah_byu":                     ("Utah",           "Utah Tech",           63,  7),
    "NCAAF_2026-09-05_idaho_utah-state":             ("Idaho",          "Idaho State",         17, 29),
}

_ROW = re.compile(r"\('(?P<gid>NCAAF_[^']+)',\s*'(?P<wrong>[^']+)',\s*'(?P<actual>[^']+)',\s*"
                  r"(?P<hs>\d+),\s*(?P<as>\d+)\)")


def _rows():
    return {m["gid"]: (m["wrong"], m["actual"], int(m["hs"]), int(m["as"]))
            for m in _ROW.finditer(CODE)}


def test_migration_is_registered_with_the_worker_runner():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS


def test_migration_is_one_statement():
    """The runner uses conn.execute(), never executescript; a second top-level
    statement would be shredded at its semicolons."""
    assert CODE.count("$$") == 2
    assert CODE.split("$$")[-1].strip() == ";"


def test_the_nine_rows_and_their_finals_are_the_measured_ones():
    assert _rows() == EXPECTED


def test_every_real_visitor_extends_the_wrong_one():
    """The whole point: the wrong name is a PREFIX of the real one, which is
    how the resolver produced it and why a whole-word replace is safe."""
    for wrong, actual, _hs, _as in EXPECTED.values():
        assert actual.startswith(wrong) and actual != wrong


def test_home_win_is_derived_from_the_scores():
    assert "home_win   = CASE WHEN fix.home_score > fix.away_score THEN 1" in CODE
    assert "WHEN fix.home_score < fix.away_score THEN 0" in CODE


def test_each_write_guards_on_its_own_property():
    """A second pass must be a no-op: the rename guards on the wrong name still
    being there, the final on the row still being unscored, and the label on
    not yet carrying the real name -- which matters because 'Indiana State'
    still contains the whole word 'Indiana'."""
    assert "AND away_team = fix.wrong" in CODE
    assert "AND home_score IS NULL" in CODE
    assert "AND pick_label NOT LIKE '%' || fix.actual || '%'" in CODE


def test_the_label_replace_is_whole_word_and_scoped_to_the_row():
    assert "regexp_replace(pick_label, '\\m' || fix.wrong || '\\M', fix.actual)" in CODE
    assert "WHERE game_id = fix.game_id" in CODE


def test_a_final_is_never_overwritten_and_ids_are_never_rekeyed():
    assert "SET game_id" not in CODE
    assert "UPDATE picks" in CODE and "SET result" not in CODE
