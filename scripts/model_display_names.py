"""The app's model names, for the database: keep one migration in step with
mobile/src/lib/modelMeta.ts.

    python -m scripts.model_display_names          # rewrite the migration
    python -m scripts.model_display_names --check  # exit 1 if it is out of step

The mobile app names every model in MODEL_META (`longLabel`, `shortLabel`).
The ops dashboard reads the same names from the view `model_display_names`
(data/migrations/dashboard_support_2026_11_12.sql), so the two never disagree.
This script writes the view's VALUES list from MODEL_META and re-stamps the
migration's marker, so the next view-migration pass applies the change.
tests/test_dashboard_support.py fails while the two are out of step.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL_META = ROOT / "mobile" / "src" / "lib" / "modelMeta.ts"
MIGRATION = ROOT / "data" / "migrations" / "dashboard_support_2026_11_12.sql"
BEGIN, END = "-- names:begin", "-- names:end"
MARK = re.compile(r"dashboard_support [0-9a-f]{12}")


def model_meta(src: str) -> list[tuple[str, str, str]]:
    """(model_id, longLabel, shortLabel) for every MODEL_META entry, in file order."""
    start = src.index("export const MODEL_META")
    body = src[start:src.index("\n};", start)]
    out = []
    for m in re.finditer(r"^  ([a-z0-9_]+): \{\n(.*?)^  \},", body, re.M | re.S):
        long_ = re.search(r"longLabel: '((?:[^'\\]|\\.)*)'", m.group(2))
        short = re.search(r"shortLabel: '((?:[^'\\]|\\.)*)'", m.group(2))
        if not long_ or not short:
            raise ValueError(f"{m.group(1)} has no longLabel or shortLabel")
        unescape = lambda s: s.replace("\\'", "'").replace("\\\\", "\\")  # noqa: E731
        out.append((m.group(1), unescape(long_.group(1)), unescape(short.group(1))))
    if not out:
        raise ValueError("no MODEL_META entries found")
    return out


def _lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def values_block(pairs: list[tuple[str, str, str]]) -> str:
    rows = [f"        ({_lit(mid)}, {_lit(name)}, {_lit(short)})" for mid, name, short in sorted(pairs)]
    return ",\n".join(rows)


def stamp(sql: str) -> str:
    blank = MARK.sub("dashboard_support " + "0" * 12, sql)
    return MARK.sub("dashboard_support " + hashlib.sha256(blank.encode("utf-8")).hexdigest()[:12], sql)


def render(sql: str, pairs: list[tuple[str, str, str]]) -> str:
    i, j = sql.index(BEGIN), sql.index(END)
    line_start = sql.rindex("\n", 0, i) + 1
    head = sql[:line_start] + sql[line_start:i] + BEGIN + "\n"
    tail_start = sql.rindex("\n", 0, j) + 1
    return stamp(head + values_block(pairs) + "\n" + sql[tail_start:])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the migration is out of step")
    args = ap.parse_args(argv)
    pairs = model_meta(MODEL_META.read_text(encoding="utf-8"))
    sql = MIGRATION.read_text(encoding="utf-8")
    want = render(sql, pairs)
    if want == sql:
        print(f"model_display_names is in step with modelMeta.ts ({len(pairs)} models)")
        return 0
    if args.check:
        print("model_display_names is out of step with modelMeta.ts: "
              "run python -m scripts.model_display_names")
        return 1
    MIGRATION.write_text(want, encoding="utf-8", newline="\n")
    print(f"rewrote {MIGRATION.relative_to(ROOT)} ({len(pairs)} models)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
