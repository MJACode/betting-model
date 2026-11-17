"""tests/_pg.py finds whichever Postgres major the machine installed.

GitHub's runner moved from 16 to 18 in 2026-11 and every scratch-cluster test
failed CI with "initdb is missing", although initdb was installed: the finder
looked only in /usr/lib/postgresql/16/bin. These pin the version-agnostic
search on a fake layout, so no real Postgres is needed.
"""
from __future__ import annotations

from pathlib import Path

from tests import _pg


def _layout(root: Path, majors: list[str]) -> None:
    for m in majors:
        b = root / m / "bin"
        b.mkdir(parents=True)
        (b / "initdb").write_text("", encoding="utf-8")


def test_finds_a_major_other_than_16(tmp_path):
    _layout(tmp_path, ["18"])
    assert _pg._debian_bin("initdb", tmp_path) == str(tmp_path / "18" / "bin" / "initdb")


def test_newest_major_wins_numerically(tmp_path):
    # "9" sorts after "18" as a string; the major is compared as a number.
    _layout(tmp_path, ["9", "16", "18"])
    assert _pg._debian_bin("initdb", tmp_path) == str(tmp_path / "18" / "bin" / "initdb")


def test_missing_root_or_binary_is_none(tmp_path):
    assert _pg._debian_bin("initdb", tmp_path / "absent") is None
    _layout(tmp_path, ["18"])
    assert _pg._debian_bin("pg_ctl", tmp_path) is None


def test_no_test_hard_codes_a_postgres_major():
    """A pinned major is the bug itself. Every finder goes through _pg."""
    tests = Path(__file__).parent
    offenders = [
        p.name
        for p in tests.glob("*.py")
        if p.name != Path(__file__).name
        and ("postgresql/1" in p.read_text(encoding="utf-8") and "<major>" not in p.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders
