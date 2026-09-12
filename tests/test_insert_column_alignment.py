"""Every INSERT's column list must line up with its VALUES list.

2026-09-12. `line_book` was added to `models/scorer._insert_picks` in #672 at a
DIFFERENT POSITION in the column list than in the VALUES list, so every value
from that point on landed one column to the left: `is_live`'s `false` went into
`inning_at_pick` (smallint), Postgres rejected it, and **pre-game scoring failed
for every sport on every refresh pass for five hours** — 540 model-game failures
a pass, the board frozen at its 6am state on a 110-game Saturday.

Nothing caught it. The unit tests build pick dicts and never execute the SQL;
the suite is green with the statement broken. This test reads the SQL itself,
which is the only place the defect exists.

It is a pure text check on purpose: no database, no fixture that can drift from
the statement it is meant to describe.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Every module that writes a pick row with a named-parameter INSERT.
SOURCES = [
    "models/scorer.py",
    "nfl/live_model/pick_writer.py",
    "scripts/nfl_prop_market_card.py",
    "scripts/nfl_wind_publisher.py",
    "scripts/wnba_prop_market_card.py",
]

_INSERT = re.compile(
    r"INSERT\s+INTO\s+(\w+)\s*\((?P<cols>[^)]*?)\)\s*VALUES\s*\((?P<vals>.*?)\)\s*(?:--|ON\s+CONFLICT|\"\"\"|$)",
    re.S | re.I,
)


def _statements(path: Path):
    text = path.read_text(encoding="utf-8")
    for m in _INSERT.finditer(text):
        cols = [c.strip() for c in m.group("cols").replace("\n", " ").split(",") if c.strip()]
        vals = m.group("vals")
        # Only named-parameter statements can be checked this way; a
        # positional or dynamically built statement is skipped by design.
        names = re.findall(r"%\((\w+)\)s", vals)
        other = re.sub(r"%\(\w+\)s", "", vals).replace(",", "").strip()
        if not names or other:
            continue
        yield m.group(1), cols, names


@pytest.mark.parametrize("rel", SOURCES)
def test_columns_and_values_line_up(rel):
    path = ROOT / rel
    if not path.exists():                      # module moved or retired
        pytest.skip(f"{rel} not present")
    checked = 0
    for table, cols, names in _statements(path):
        checked += 1
        assert len(cols) == len(names), (
            f"{rel}: INSERT INTO {table} lists {len(cols)} columns but "
            f"{len(names)} values")
        mismatched = [(i, c, n) for i, (c, n) in enumerate(zip(cols, names)) if c != n]
        assert not mismatched, (
            f"{rel}: INSERT INTO {table} column/value order diverges at "
            f"{mismatched[:4]} — the value lands in the wrong column")
    assert checked, f"{rel}: no named-parameter INSERT found; update SOURCES"


def test_the_scorer_pick_insert_is_actually_covered():
    """The regression that motivated this file. If the statement stops being
    parseable the test above silently checks nothing, so name it here."""
    tables = [t for t, _, _ in _statements(ROOT / "models/scorer.py")]
    assert "picks" in tables
