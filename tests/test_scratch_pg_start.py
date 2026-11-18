"""Only tests/_pg.py starts a scratch Postgres, and it never captures pg_ctl.

A test that runs `pg_ctl ... start` itself, with the output captured, waits
forever on Windows, where this repo runs: the server inherits the pipe and
never closes it. Two copies of that start did exactly this. One was
tests/test_nhl_stats_views.py: every full run on this PC stopped there from
2026-11-16 (#1445). The other was tests/byom_scratch.py (measured
2026-11-13 and again 2026-11-17). tests/_pg.py's `scratch_cluster` sends
pg_ctl's output to a file instead, so every scratch test goes through it.

The PR check runs on Linux, where a captured start returns, so this file is
the only thing that stops a new copy before a Windows run hangs on it.
"""
from __future__ import annotations

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent
ALLOWED = {"_pg.py"}
PG = TESTS / "_pg.py"


def _read(path: Path) -> str:
    # utf-8-sig drops a byte-order mark, which ast.parse would refuse.
    return path.read_text(encoding="utf-8-sig")


def _start_lists(tree: ast.AST, source: str) -> list[ast.AST]:
    """Lists or tuples that spell a `pg_ctl ... start` command.

    One literal holding the word "start" and either naming pg_ctl or carrying
    pg_ctl's "-D" data flag. A command assembled from pieces (a base list plus
    the action, or the action in a variable) is not seen. No file here has
    ever built one that way (git log -G pg_ctl, 2026-11-17).
    """
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.List, ast.Tuple)):
            continue
        words = {e.value for e in node.elts
                 if isinstance(e, ast.Constant) and isinstance(e.value, str)}
        if "start" not in words:
            continue
        text = ast.get_source_segment(source, node) or ""
        if "pg_ctl" in text or "-D" in words:
            found.append(node)
    return found


def _offenders(source: str, filename: str = "<string>") -> list[int]:
    """Lines where a `pg_ctl ... start` command is written out."""
    tree = ast.parse(source, filename)
    return [node.lineno for node in _start_lists(tree, source)]


def _captured_starts(source: str, filename: str = "<string>") -> list[int]:
    """Lines of a subprocess call that runs a start and does not send its
    output to a file: capture_output=True, a PIPE, or no stdout at all."""
    tree = ast.parse(source, filename)
    starts = {id(n) for n in _start_lists(tree, source)}
    bad = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and node.args and id(node.args[0]) in starts):
            continue
        kw = {k.arg: ast.get_source_segment(source, k.value) or "" for k in node.keywords}
        piped = any("PIPE" in kw.get(name, "") for name in ("stdout", "stderr"))
        if kw.get("capture_output", "False") != "False" or piped or "stdout" not in kw:
            bad.append(node.lineno)
    return bad


def test_no_test_starts_pg_ctl_itself() -> None:
    found = {}
    for path in sorted(TESTS.rglob("*.py")):
        if path.name in ALLOWED:
            continue
        lines = _offenders(_read(path), str(path))
        if lines:
            found[path.relative_to(TESTS.parent).as_posix()] = lines
    assert not found, (
        "these files start pg_ctl themselves: "
        + ", ".join(f"{p} line {', '.join(map(str, ls))}" for p, ls in found.items())
        + ". Use tests._pg.scratch_cluster(); a captured pg_ctl start never "
        "returns on Windows (#1445)."
    )


def test_the_one_allowed_start_writes_its_output_to_a_file() -> None:
    source = _read(PG)
    assert _offenders(source, str(PG)), "tests/_pg.py no longer starts pg_ctl where this looks"
    assert _captured_starts(source, str(PG)) == [], (
        "tests/_pg.py's pg_ctl start no longer sends its output to a file. "
        "On Windows a captured start never returns (#1445)."
    )
    # The same check on the edit it exists to stop.
    captured = source.replace("check=True, stdout=sink, stderr=sink", "check=True, capture_output=True")
    assert captured != source
    assert _captured_starts(captured) != []


def test_the_detector_sees_the_shape_it_guards() -> None:
    old = (
        "subprocess.run(\n"
        "    [pg_ctl, '-D', owned, '-o', f'-p {port}', '-l', log, '-w', 'start'],\n"
        "    check=True, capture_output=True, text=True)\n"
    )
    assert _offenders(old) == [2]
    assert _captured_starts(old) == [1]
    built_first = "cmd = (ctl, '-D', data, 'start')\nsubprocess.run(cmd)\n"
    assert _offenders(built_first) == [1]
    assert _offenders("subprocess.run([pg_ctl, '-D', d, '-w', 'stop'])\n") == []
    assert _offenders("app.run(['npm', 'start'])\n") == []


def test_runs_in_pr_ci() -> None:
    workflow = (TESTS.parent / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
    assert "tests/test_scratch_pg_start.py" in workflow


def test_a_folder_the_server_still_holds_is_retried(monkeypatch, tmp_path: Path) -> None:
    """scratch_cluster's cleanup tries again while files are still held open."""
    from tests import _pg

    folder = tmp_path / "cluster"
    folder.mkdir()
    calls = []

    def rmtree(path, ignore_errors=False):
        calls.append(path)
        if len(calls) == 3:
            folder.rmdir()  # the third try finds the files released

    monkeypatch.setattr(_pg.shutil, "rmtree", rmtree)
    monkeypatch.setattr(_pg.time, "sleep", lambda _s: None)
    _pg._remove(str(folder))
    assert len(calls) == 3 and not folder.exists()

    folder.mkdir()
    calls.clear()
    monkeypatch.setattr(_pg.shutil, "rmtree", lambda path, ignore_errors=False: calls.append(path))
    _pg._remove(str(folder), tries=4)
    assert len(calls) == 4, "it gives up after its tries instead of looping"


def test_a_file_saved_with_a_byte_order_mark_is_read(tmp_path: Path) -> None:
    """PowerShell's `>` writes UTF-8 with a mark; Python runs such a file."""
    path = tmp_path / "test_marked.py"
    path.write_bytes(b"\xef\xbb\xbfsubprocess.run([pg_ctl, '-D', d, 'start'])\n")
    assert _offenders(_read(path), str(path)) == [1]
