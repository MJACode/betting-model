"""The repo copy of the Retool ops dashboard and its sync script.

mike, 2026-11-15: "move the betting model retool application to the github repo
so I can make edits there". Retool's own GitHub sync needs the Enterprise plan
(this account is on Team), so `scripts/retool_app_files.py` is the check that
the repo copy and the live app hold the same bytes. These tests pin the
properties that make that check worth trusting.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import retool_app_files as raf

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "retool" / "models-ops"


def _dump(tmp_path: Path, files: list[dict], name: str = "dump.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps({"files": files}), encoding="utf-8")
    return p


def _entry(path: str, content: str, **kw) -> dict:
    return {"path": path, "content": content,
            "sizeBytes": len(content.encode("utf-8")), "truncated": False, **kw}


def test_write_then_check_round_trips_bytes_exactly(tmp_path):
    # LF endings and a non-ASCII character: the two things a Windows text-mode
    # write would silently change.
    content = "const a = '—'\nexport default a\n"
    dump = _dump(tmp_path, [_entry("/frontend/x.ts", content)])
    dest = tmp_path / "app"

    files = raf.load_dumps([dump])
    w = raf.write(files, dest)
    assert w.written == ["/frontend/x.ts"] and not w.errors
    assert (dest / "frontend" / "x.ts").read_bytes() == content.encode("utf-8")

    c = raf.check(files, dest)
    assert c.match == ["/frontend/x.ts"]
    assert not (c.differs or c.missing_in_repo or c.only_in_repo or c.errors)


def test_check_catches_a_one_byte_edit_and_both_kinds_of_missing_file(tmp_path):
    dump = _dump(tmp_path, [_entry("/a.ts", "x = 1\n"), _entry("/b.ts", "y = 2\n")])
    dest = tmp_path / "app"
    files = raf.load_dumps([dump])
    raf.write(files, dest)

    (dest / "a.ts").write_bytes(b"x = 2\n")          # same length, one byte changed
    (dest / "b.ts").unlink()                          # in Retool, not in the repo
    (dest / "extra.ts").write_bytes(b"z = 3\n")       # in the repo, not in Retool

    c = raf.check(files, dest)
    assert c.differs == ["/a.ts"]
    assert c.missing_in_repo == ["/b.ts"]
    assert c.only_in_repo == ["/extra.ts"]
    assert raf.main(["check", str(dump), "--dest", str(dest)]) == 1


def test_crlf_in_the_repo_copy_is_a_difference_not_a_match(tmp_path):
    # autocrlf=true on this machine: without the .gitattributes rule a checkout
    # turns LF into CRLF, and the copy no longer matches Retool.
    dump = _dump(tmp_path, [_entry("/a.ts", "x = 1\ny = 2\n")])
    dest = tmp_path / "app"
    files = raf.load_dumps([dump])
    raf.write(files, dest)
    (dest / "a.ts").write_bytes(b"x = 1\r\ny = 2\r\n")
    assert raf.check(files, dest).differs == ["/a.ts"]


def test_truncated_and_lockfile_entries_are_never_written(tmp_path):
    dump = _dump(tmp_path, [
        _entry("/big.ts", "partial", truncated=True),
        _entry("/pnpm-lock.yaml", "lockfileVersion: '9.0'\n"),
    ])
    dest = tmp_path / "app"
    w = raf.write(raf.load_dumps([dump]), dest)
    assert w.written == []
    assert len(w.skipped) == 2
    assert not (dest / "big.ts").exists() and not (dest / "pnpm-lock.yaml").exists()


def test_content_that_disagrees_with_retools_size_is_refused(tmp_path):
    entry = _entry("/a.ts", "x = 1\n")
    entry["sizeBytes"] += 1
    dest = tmp_path / "app"
    w = raf.write(raf.load_dumps([_dump(tmp_path, [entry])]), dest)
    assert w.written == [] and len(w.errors) == 1
    assert not (dest / "a.ts").exists()


def test_a_path_cannot_escape_the_destination(tmp_path):
    dump = _dump(tmp_path, [_entry("/../../evil.ts", "x\n")])
    with pytest.raises(ValueError):
        raf.write(raf.load_dumps([dump]), tmp_path / "app")


def test_the_same_path_in_two_dumps_is_refused(tmp_path):
    a = _dump(tmp_path, [_entry("/a.ts", "1\n")], "one.json")
    b = _dump(tmp_path, [_entry("/a.ts", "2\n")], "two.json")
    with pytest.raises(ValueError):
        raf.load_dumps([a, b])


def test_the_repo_copy_is_present_and_kept_lf():
    """The export exists, and git is told never to rewrite its line endings."""
    for rel in ("package.json", "frontend/App.tsx", "backend/ops/setModelVolume.ts"):
        assert (APP / rel).is_file(), rel
    attrs = (ROOT / ".gitattributes").read_text(encoding="utf-8")
    assert "retool/** text eol=lf" in attrs
    assert b"\r\n" not in (APP / "frontend" / "App.tsx").read_bytes()
