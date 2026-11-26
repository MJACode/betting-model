"""Open the This PC window:  pythonw -m pc_monitor  (the desktop shortcut).

  * If the app is already running, it only opens another window onto it.
  * When run from its own copy under .claude/feeds/, it first moves that copy
    to origin/master, but only once origin/master contains this package, so the
    shortcut keeps working before the pull request that adds it is merged.
  * The window is Edge (or Chrome) in app mode: its own window, no tabs or
    address bar. Closing it leaves the app running for --idle-exit-min minutes
    (default 10), then it exits. --stay keeps it running with no window, for a
    start at sign-in.

Under pythonw there is no stdout or stderr. Both go to
betting_local_copies/logs/pc_monitor_<date>.log before anything else runs,
and every child process is started with no window (sources.hidden_run).
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

PORT = int(os.environ.get("PC_MONITOR_PORT", "8790"))
ROOT = Path(__file__).resolve().parent.parent
# While it runs, the monitor checks origin/master this often, and restarts on
# the new code when a merge changed one of WATCH_PATHS (mike, 2026-11-26:
# "Figure it out", after a merge reached the monitor only at the next sign-in).
MASTER_CHECK_SEC = 300.0
WATCH_PATHS = ("pc_monitor/", "data/db.py")


def _under_pythonw() -> bool:
    return Path(sys.executable).name.lower().startswith("pythonw")


def _quiet_stdio() -> None:
    """Send output to the log file when there is no console.

    Under pythonw both streams go to the log, even when they look present: a
    pythonw started by another pythonw (the relaunch after an update) is handed
    a pipe whose reader is already closed, and its first print raised OSError
    (measured 2026-11-21), so it died before writing a line."""
    if not _under_pythonw() and sys.stdout is not None and sys.stderr is not None:
        return
    from pc_monitor.sources import LOG_DIR
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        fh = open(LOG_DIR / f"pc_monitor_{datetime.now():%Y%m%d}.log", "a", encoding="utf-8", buffering=1)
    except OSError:
        fh = open(os.devnull, "w", encoding="utf-8")
    sys.stdout = fh
    sys.stderr = fh


def _message_box(text: str) -> None:
    """A Windows message box: the only way to tell the person something when
    there is no console."""
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, text, "This PC monitor", 0x10)
    except Exception:  # noqa: BLE001
        pass


def _running(port: int) -> bool | None:
    """True if this app answers on the port, False if nothing does, None if
    something else holds it."""
    import json
    import urllib.request
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=1.5) as r:
            return json.loads(r.read().decode()).get("app") == "pc_monitor" or None
    except OSError:
        return False
    except ValueError:
        return None


def open_window(url: str) -> None:
    import subprocess
    from pc_monitor.sources import CREATE_NO_WINDOW
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    for exe in (Path(pf86) / "Microsoft/Edge/Application/msedge.exe",
                Path(pf) / "Microsoft/Edge/Application/msedge.exe",
                Path(pf) / "Google/Chrome/Application/chrome.exe",
                Path(pf86) / "Google/Chrome/Application/chrome.exe"):
        if exe.is_file():
            subprocess.Popen([str(exe), f"--app={url}", "--window-size=1360,920"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
            return
    os.startfile(url)  # noqa: S606 - the default browser, as a last resort


def _update_checkout() -> bool:
    """Move the shortcut's own copy to origin/master. True when it moved, so
    the caller restarts on the new code. Only for a copy under .claude/feeds/."""
    from pc_monitor.sources import hidden_run
    if "/.claude/feeds/" not in ROOT.as_posix().lower() + "/":
        return False
    # origin/master in use; another remote branch only to test this path.
    ref = os.environ.get("PC_MONITOR_UPDATE_REF", "origin/master")
    if not ref.startswith("origin/"):
        return False
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}

    def git(*args: str, timeout: float = 30) -> str | None:
        try:
            r = hidden_run(["git", *args], timeout=timeout, cwd=str(ROOT), env=env)
        except Exception as exc:  # noqa: BLE001
            print(f"git {args[0]} failed: {type(exc).__name__}", file=sys.stderr)
            return None
        return r.stdout.strip() if r.returncode == 0 else None

    if git("fetch", "-q", "origin", ref[len("origin/"):], timeout=45) is None:
        print("git fetch failed - starting on the code already here", file=sys.stderr)
    if git("cat-file", "-e", f"{ref}:pc_monitor/__main__.py") is None:
        return False  # the pull request that adds this app is not merged yet
    head, master = git("rev-parse", "HEAD"), git("rev-parse", ref)
    if not head or not master or head == master:
        return False
    if git("checkout", "-q", "--detach", "-f", ref) is None:
        print(f"git checkout of {ref} failed - starting on the code already here", file=sys.stderr)
        return False
    print(f"moved {head[:8]} -> {master[:8]}", file=sys.stderr)
    return True


def changed_on_master(git) -> bool:
    """True when origin/master changes one of WATCH_PATHS against this copy's
    HEAD. `git(*args)` returns stdout or None. Any git failure is False: never
    restart on a doubt. Only for a copy under .claude/feeds/."""
    if "/.claude/feeds/" not in ROOT.as_posix().lower() + "/":
        return False
    git("fetch", "-q", "origin", "master")
    out = git("diff", "--name-only", "HEAD", "origin/master", "--", *WATCH_PATHS)
    return bool(out and out.strip())


def _git(*args: str) -> str | None:
    from pc_monitor.sources import hidden_run
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    try:
        r = hidden_run(["git", *args], timeout=60, cwd=str(ROOT), env=env)
    except Exception:  # noqa: BLE001
        return None
    return r.stdout if r.returncode == 0 else None


def watch_master(srv, flag: dict, every: float = MASTER_CHECK_SEC, check=None, sleep=time.sleep) -> None:
    """Every `every` seconds: when master changed the monitor, stop the server
    so main() restarts on the new code. Runs on its own daemon thread."""
    check = check or (lambda: changed_on_master(_git))
    while True:
        sleep(every)
        try:
            if check():
                flag["restart"] = True
                srv.shutdown()
                return
        except Exception:  # noqa: BLE001 - a failed check is a skipped check
            pass


def main() -> int:
    _quiet_stdio()
    ap = argparse.ArgumentParser(description="This PC: the betting model's jobs on this computer")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-window", action="store_true", help="serve without opening a window")
    ap.add_argument("--no-update", action="store_true", help="do not move this copy to origin/master")
    ap.add_argument("--stay", action="store_true", help="keep running with no window open")
    ap.add_argument("--idle-exit-min", type=float, default=10.0,
                    help="minutes with no window before exiting (ignored with --stay)")
    args = ap.parse_args()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} start pid {os.getpid()} from {ROOT}", flush=True)

    state = _running(args.port)
    if state is True:
        if not args.no_window:
            open_window(url)
        return 0
    if state is None:
        _message_box(f"Port {args.port} is in use by another program, so the monitor cannot start.")
        return 1

    if not args.no_update and _update_checkout():
        import subprocess
        from pc_monitor.sources import CREATE_NO_WINDOW
        subprocess.Popen([sys.executable, "-m", "pc_monitor", "--no-update", *sys.argv[1:]],
                         cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        print("restarting on the new code", flush=True)
        return 0

    sys.path.insert(0, str(ROOT))
    from pc_monitor.app import Collector, build_server, log, watch_idle
    collector = Collector(stay=args.stay)
    try:
        srv = build_server(args.port, collector)
    except OSError as exc:
        _message_box(f"The monitor could not start on port {args.port}: {exc}")
        return 1
    collector.start()
    if not args.stay:
        watch_idle(srv, collector, args.idle_exit_min * 60)
    log(f"serving {url}")
    if not args.no_window:
        time.sleep(0.3)
        open_window(url)
    flag = {"restart": False}
    if not args.no_update:
        import threading
        threading.Thread(target=watch_master, args=(srv, flag), name="watch_master", daemon=True).start()
    try:
        srv.serve_forever()
    finally:
        collector.stop.set()
    if flag["restart"]:
        # The port is released before the new copy starts; the new one moves
        # this copy to origin/master itself (_update_checkout) and serves.
        srv.server_close()
        import subprocess
        from pc_monitor.sources import CREATE_NO_WINDOW
        argv = [a for a in sys.argv[1:] if a != "--no-update"]
        subprocess.Popen([sys.executable, "-m", "pc_monitor", "--no-window", *[a for a in argv if a != "--no-window"]],
                         cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=CREATE_NO_WINDOW)
        log("a merge changed the monitor - restarting on the new code")
        return 0
    log("stopped")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception:  # noqa: BLE001 - with no console, the log is the only witness
        import traceback
        traceback.print_exc()
        _message_box("The monitor stopped with an error. Its log is in "
                     "Documents\\betting_local_copies\\logs\\pc_monitor_<date>.log")
        raise SystemExit(1)
