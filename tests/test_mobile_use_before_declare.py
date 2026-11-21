"""No name in the app is read before the line that declares it (2026-11-21).

Bet all crashed on every open (OTA 01a1fef3, five `render` rows in
`app_errors` at 16:58 UTC, "Cannot read property 'has' of undefined" in
BetAllSheet): `trackedTicked` read `selected.has(...)` five lines above
`const [selected] = useState(...)`. tsc does not flag a read inside a callback.

* `mobile/scripts/verify_no_use_before_declare.ts` walks every function body
  under mobile/src with the TypeScript parser. It needs `npm ci` in mobile/
  (tsx + typescript), so it skips without them.
* The BetAllSheet pin runs everywhere: `trackedTicked` sits below `selected`.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"


def test_no_name_is_read_before_its_declaration():
    from tests._node import tsx_cmd

    cmd = tsx_cmd(MOBILE)
    if cmd is None or not (MOBILE / "node_modules" / "typescript").is_dir():
        pytest.skip("mobile/node_modules (tsx, typescript) not installed")
    proc = subprocess.run(
        [*cmd, "scripts/verify_no_use_before_declare.ts"],
        cwd=MOBILE, capture_output=True, text=True, encoding="utf-8",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_bet_all_reads_selected_after_declaring_it():
    src = (MOBILE / "src" / "components" / "BetAllSheet.tsx").read_text(encoding="utf-8")
    declared = src.index("const [selected, setSelected] = useState")
    read = src.index("const trackedTicked = ")
    assert read > declared, "trackedTicked reads `selected` above its useState: Bet all crashes on open"
