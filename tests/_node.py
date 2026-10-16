"""Where is node? The TypeScript-running tests shell out to it.

`shutil.which` finds a system install. This machine has none (no node, no
npm), so the fallback is the binary the `nodejs-wheel-binaries` pip package
ships beside its module (declared in requirements-test.txt). Either way the
tests get a real node >= 22.6, which is what `--experimental-strip-types`
needs; with neither, the node-backed tests skip.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess


def node_exe() -> str | None:
    found = shutil.which("node")
    if found:
        return found
    try:
        import nodejs_wheel  # type: ignore
    except ImportError:
        return None
    d = os.path.dirname(nodejs_wheel.__file__)
    for name in ("node.exe", "node"):
        p = os.path.join(d, name)
        if os.path.isfile(p):
            return p
    return None


def node_strips_types() -> bool:
    exe = node_exe()
    if exe is None:
        return False
    out = subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.strip()
    m = re.match(r"v(\d+)\.(\d+)", out)
    return bool(m) and (int(m.group(1)), int(m.group(2))) >= (22, 6)
