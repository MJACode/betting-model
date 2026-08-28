"""
Nothing an entrypoint needs may be defined after its __main__ guard.

The reason this file exists: gameday.py once had check_feed_assumptions defined
BELOW `if __name__ == "__main__": main()`. Importing the module bound the name
fine, so every test that imported and called the function passed. Running the
module as an entrypoint did not: the guard fires mid module, main() runs, and
the self check dies on NameError before a single game is priced. The worker
failed on every scheduled tick for a full deploy cycle while a 149 test suite
stayed green, because no test executed a module as __main__.

The check is structural rather than behavioural on purpose. A behavioural test
would have to run the entrypoint, which means network, a slate, and a clock.
The defect is a source ordering property, so assert the property.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG.parent))

# Statement types that bind a name the entrypoint may go on to reference.
_BINDING = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
            ast.Assign, ast.AnnAssign, ast.Import, ast.ImportFrom)


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If):
        return False
    t = node.test
    return (isinstance(t, ast.Compare)
            and isinstance(t.left, ast.Name)
            and t.left.id == "__name__"
            and any(isinstance(c, ast.Constant) and c.value == "__main__"
                    for c in t.comparators))


def _modules_with_guard():
    out = []
    for path in sorted(PKG.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for i, node in enumerate(tree.body):
            if _is_main_guard(node):
                out.append((path, tree, i))
                break
    return out


def test_at_least_one_entrypoint_is_scanned():
    """Guards against the scan silently matching nothing and passing."""
    mods = _modules_with_guard()
    assert mods, "no __main__ guard found anywhere in live_model"
    names = {p.name for p, _, _ in mods}
    assert "gameday.py" in names, names


@pytest.mark.parametrize("case", _modules_with_guard(),
                         ids=lambda c: c[0].name)
def test_nothing_is_defined_after_the_main_guard(case):
    path, tree, idx = case
    after = [n for n in tree.body[idx + 1:] if isinstance(n, _BINDING)]
    if after:
        offenders = ", ".join(
            getattr(n, "name", None) or f"line {n.lineno}" for n in after)
        pytest.fail(
            f"{path.relative_to(PKG.parent)} defines {offenders} AFTER its "
            "__main__ guard. Those names do not exist when the module is run "
            "as an entrypoint. Move the guard to the end of the file.")
