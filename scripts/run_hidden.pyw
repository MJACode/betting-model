"""Start a console program with no window and hand back its exit code.

The PC's scheduled tasks (BettingModel\\LocalMirror, DkLiveBoard, TennisFeeds;
docs/local_ops.md, "Every scheduled task starts windowless") run as

    pythonw.exe C:\\Users\\micha\\Documents\\betting_local_copies\\bin\\run_hidden.pyw powershell.exe <arguments>

`powershell.exe -WindowStyle Hidden` alone opened a visible window on every
start, because console programs on this PC open in Windows Terminal and Windows
Terminal ignores that flag (measured 2026-11-21). `conhost.exe --headless`
hid the window but always reported 0 to Task Scheduler, so a failed backup read
as a success. This launcher is a windowless program (pythonw), starts the
command with CREATE_NO_WINDOW, waits for it, and exits with its code.

Ending the task in Task Scheduler stops this launcher, not the command it
started. Each job's own lock keeps a second copy from running.
"""
from __future__ import annotations

import subprocess
import sys

CREATE_NO_WINDOW = 0x08000000


def main(argv: list[str]) -> int:
    if not argv:
        return 2
    return subprocess.run(argv, creationflags=CREATE_NO_WINDOW).returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
