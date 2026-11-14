"""No migration splits an escape string across lines.

Postgres joins two plain string constants separated by a newline, but an
E'' (escape) constant cannot continue another literal: E'a'<newline>E'b' is a
syntax error. record_strikes_ufc_retired_2026_11_13.sql shipped that way and
failed on production (2026-11-13, "syntax error at or near E'..."). The tests
that read migrations as text never ran them, so this reads every migration
for the shape itself.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

MIGRATIONS = Path(__file__).resolve().parents[1] / "data" / "migrations"
# a quoted literal (with '' escapes), then only whitespace and a newline, then E'
SPLIT = re.compile(r"'(?:[^']|'')*'[ \t]*\r?\n\s*E'")


@pytest.mark.parametrize("path", sorted(MIGRATIONS.glob("*.sql")), ids=lambda p: p.name)
def test_no_escape_string_continues_another_literal(path):
    sql = path.read_text(encoding="utf-8")
    bad = [sql.count("\n", 0, m.start()) + 1 for m in SPLIT.finditer(sql)]
    assert not bad, f"{path.name}: an E'' literal continues the literal on line(s) {bad}"


def test_the_check_catches_the_shape_that_failed():
    broken = ("d := regexp_replace(d, 'x',\n"
              "    E'\\n    AND model_id <> ''a''::text'\n"
              "    E'\\n    AND model_id <> ''b''::text');\n")
    assert SPLIT.search(broken)
    fixed = "d := regexp_replace(d, 'x', E'\\n AND a\\n AND b');\n"
    assert not SPLIT.search(fixed)
