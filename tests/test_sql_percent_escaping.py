"""
Tripwire for the bug class that silently killed opening-signal capture -- and
therefore every Discord post and mobile push -- for three days (2026-08-24..27).

psycopg2 interpolates the ENTIRE SQL string against the params tuple, so any
literal percent sign in a parameterised query is read as a format spec:

    conn.execute("... LIKE '%f5_moneyline%' ... WHERE d = ?", (date,))
    -> TypeError: not enough arguments for format string

The query does not fail loudly at import or review time. It fails at runtime,
inside a step whose caller catches exceptions, so the pipeline goes on looking
green while a whole feature stops working. That is exactly what happened, twice:
once via a ':early' literal being rewritten into a named param (fixed in
data/db.py by only converting placeholders OUTSIDE string literals), and once
via check_line_movement's LIKE patterns (fixed by doubling them).

Literal percents must therefore be written '%%'. This test walks the AST of the
pipeline modules, adapts every parameterised conn.execute SQL exactly as
data/db.py does, and asserts the result survives %-interpolation.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# Modules that run inside the pipeline and talk to Postgres. Analysis scripts
# under scripts/ and nfl/ are excluded -- they are run by hand, print f-strings
# full of format specs, and would drown the signal in false positives.
SCANNED = [
    "models/scorer.py",
    "models/live_scorer.py",
    "tracking/paper_tracker.py",
    "tracking/opening_signals.py",
    "tracking/system_health.py",
    "tracking/discord_notifier.py",
    "tracking/push_notifier.py",
    "tracking/run_ledger.py",
    "tracking/parlay_track_record.py",
    "data/view_migrations.py",
    "data/threshold_sync.py",
    "data/prune_odds.py",
]

_SQL_LITERAL_RE = re.compile(r"'(?:[^']|'')*'")
_NAMED_PARAM_RE = re.compile(r"(?<!:):([A-Za-z_]\w*)")


def _adapt(sql: str) -> str:
    """Mirror data/db.py: convert placeholders only OUTSIDE string literals."""
    out: list[str] = []
    pos = 0
    for m in _SQL_LITERAL_RE.finditer(sql):
        frag = sql[pos:m.start()]
        frag = _NAMED_PARAM_RE.sub(r"%(\1)s", frag).replace("?", "%s")
        out.append(frag)
        out.append(m.group(0))
        pos = m.end()
    tail = sql[pos:]
    out.append(_NAMED_PARAM_RE.sub(r"%(\1)s", tail).replace("?", "%s"))
    return "".join(out)


def _parameterised_sql(path: Path):
    """Yield (lineno, sql) for every conn.execute(<literal sql>, <params>)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr in ("execute", "executescript")):
            continue
        if len(node.args) < 2:          # no params -> psycopg2 does not interpolate
            continue
        sql_node = node.args[0]
        if isinstance(sql_node, ast.Constant) and isinstance(sql_node.value, str):
            yield node.lineno, sql_node.value


@pytest.mark.parametrize("relpath", SCANNED)
def test_parameterised_sql_escapes_literal_percents(relpath):
    path = ROOT / relpath
    if not path.exists():
        pytest.skip(f"{relpath} not present")

    offenders = []
    for lineno, sql in _parameterised_sql(path):
        adapted = _adapt(sql)
        # Strip the placeholders db.py just produced; whatever percent signs
        # remain are literals and must be doubled.
        residue = adapted.replace("%s", "").replace("%%", "")
        residue = re.sub(r"%\([A-Za-z_]\w*\)", "", residue)
        if "%" in residue:
            snippet = " ".join(sql.split())[:90]
            offenders.append(f"{relpath}:{lineno}: {snippet}")

    assert not offenders, (
        "Literal percent signs must be written '%%' in a parameterised query -- "
        "psycopg2 reads a lone % as a format spec and the query raises at "
        "runtime inside a step that swallows exceptions:\n  "
        + "\n  ".join(offenders)
    )


def test_the_scanner_actually_catches_the_regression():
    """A guard that fails loudly if the detector above stops detecting."""
    broken = "SELECT 1 WHERE m LIKE '%f5_moneyline%' AND d = ?"
    adapted = _adapt(broken)
    with pytest.raises(TypeError):
        adapted % ("2026-08-27",)

    fixed = "SELECT 1 WHERE m LIKE '%%f5_moneyline%%' AND d = ?"
    assert _adapt(fixed) % ("2026-08-27",)


def test_check_line_movement_query_interpolates():
    """The specific query this test was written for."""
    src = (ROOT / "models/scorer.py").read_text(encoding="utf-8")
    i = src.index("def check_line_movement")
    start = src.index('conn.execute("""', i) + len('conn.execute("""')
    sql = src[start:src.index('""", (game_date,)', i)]
    # Must not raise.
    assert _adapt(sql) % ("2026-08-27",)
