"""Run npm with the pip-packaged node when no system node exists.

    python scripts/npm.py ci --no-audit --no-fund      # from mobile/, installs node_modules

`requirements-test.txt` brings `nodejs-wheel-binaries`, which ships node and
npm beside its module but puts neither on PATH. Package install scripts
(`node install.js`) need `node` on PATH too, so this prepends the wheel's
directory before exec'ing npm's CLI through that node. A system npm, when
present, is used as-is.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys


def main(argv: list[str]) -> int:
    system = shutil.which("npm")
    if system:
        return subprocess.call([system, *argv])
    try:
        import nodejs_wheel  # type: ignore
    except ImportError:
        print("no npm on PATH and nodejs-wheel-binaries is not installed: "
              "python -m pip install -r requirements-test.txt", file=sys.stderr)
        return 2
    d = os.path.dirname(nodejs_wheel.__file__)
    node = next((p for p in (os.path.join(d, "node.exe"), os.path.join(d, "node")) if os.path.isfile(p)), None)
    cli = os.path.join(d, "lib", "node_modules", "npm", "bin", "npm-cli.js")
    if node is None or not os.path.isfile(cli):
        print(f"nodejs_wheel at {d} has no node/npm", file=sys.stderr)
        return 2
    env = dict(os.environ, PATH=d + os.pathsep + os.environ.get("PATH", ""))
    return subprocess.call([node, cli, *argv], env=env)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
