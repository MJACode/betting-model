"""PR CI runs the Record hero checks. CI does not install mobile/node_modules.

`mobile/scripts/verify_record_hero.ts` is the check. The libs it imports use
the app's `@/` alias, which plain node cannot resolve, and `tsx` is absent
on the PR runner. This copies the script and those libs into a temp directory,
rewrites the aliases to relative `.ts` imports, and runs
`node --experimental-strip-types` — the same node 22 the workflow sets up
before pytest.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from tests._node import NODE, node_strips_types  # noqa: E402

MOBILE = ROOT / "mobile"
LIB = MOBILE / "src" / "lib"

needs_node = pytest.mark.skipif(
    not node_strips_types(),
    reason="node >= 22.6 not available",
)

LIBS = (
    "format.ts",
    "equityGeometry.ts",
    "recordHero.ts",
    "a11y.ts",
    "recordStart.ts",
    "tone.ts",
)


def _rewrite(text: str) -> str:
    text = re.sub(r"from '(?:\.\./)+src/lib/(\w+)';", r"from './\1.ts';", text)
    text = re.sub(r"from '@/lib/(\w+)';", r"from './\1.ts';", text)
    # `import type` is erased by strip-types. Drop it here too so a leftover
    # `@/types` alias cannot fail the module load.
    text = re.sub(r"^import type .*;\n", "", text, flags=re.M)
    return text


def test_runs_in_pr_ci():
    yml = (ROOT / ".github/workflows/pr-ci.yml").read_text(encoding="utf-8")
    assert "tests/test_record_hero.py" in yml


@needs_node
def test_verify_record_hero_passes(tmp_path: Path):
    assert NODE is not None
    script = _rewrite((MOBILE / "scripts" / "verify_record_hero.ts").read_text(encoding="utf-8"))
    (tmp_path / "verify_record_hero.ts").write_text(script, encoding="utf-8")
    for name in LIBS:
        (tmp_path / name).write_text(_rewrite((LIB / name).read_text(encoding="utf-8")), encoding="utf-8")
    (tmp_path / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "verify_record_hero.ts"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "All record-hero checks passed." in proc.stdout
    assert "[PASS] stale scrub index is released" in proc.stdout
    assert "[PASS] a pill wider than the chart stays inside" in proc.stdout
    assert "[PASS] spoken grid does not use Yesterday's book name" in proc.stdout
