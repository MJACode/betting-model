"""Stop a pipeline between steps when Railway sends SIGTERM.

A merge to master redeploys the worker. Railway delivers SIGTERM, then
SIGKILL if the process is still alive when the platform's stop grace
ends. SIGKILL cannot be caught. SIGTERM can: the step already running
is left alone, and the next step does not start. The open
``pipeline_runs`` row is closed with ``failed_steps`` containing
``deploy-cutoff`` so it is not left unfinished.

``aborted`` stays the stamp the boot sweep writes when a previous
process died before it could close its own row. Both are deploy-kills:
they do not consume the one-retry failure cap.
"""

from __future__ import annotations

import signal
import threading

from loguru import logger

# Token written into pipeline_runs.failed_steps. Hyphenated so it cannot
# be mistaken for a pipeline step name. refresh_pass_steps treats it as
# metadata, the same way it treats ``aborted``.
DEPLOY_CUTOFF = "deploy-cutoff"

# Tokens that mean the worker was replaced, not that a step failed.
DEPLOY_KILL_MARKERS = frozenset({"aborted", DEPLOY_CUTOFF})


class DeployCutoff(Exception):
    """Raised between steps once SIGTERM has been seen.

    ``before_step`` is the step that did not start.
    """

    def __init__(self, before_step: str):
        super().__init__(before_step)
        self.before_step = before_step


_requested = False
_children: list = []
_lock = threading.Lock()


def requested() -> bool:
    return _requested


def request() -> None:
    """Record that this process should stop after the current step."""
    global _requested
    _requested = True


def reset_for_tests() -> None:
    global _requested
    _requested = False
    with _lock:
        _children.clear()


def checkpoint(before_step: str) -> None:
    """Call immediately before starting a step.

    A step that is already inside its work is not interrupted. The next
    call raises ``DeployCutoff`` so the caller can close the ledger and
    return.
    """
    if _requested:
        raise DeployCutoff(before_step)


def note_sigterm(signum, frame) -> None:  # noqa: ARG001 — signal handler signature
    """Pipeline SIGTERM handler. Return, so the current step can finish."""
    request()
    logger.warning(
        "deploy drain: SIGTERM — this step will finish; the next step will not start"
    )


def install_pipeline_handler() -> None:
    """Swallow SIGTERM in a pipeline process.

    The default action is to die at once, which is the mid-step kill.
    Installed for the daily process and for a single ``--step`` so a
    signal delivered to that process does not abandon the step it is in.
    """
    signal.signal(signal.SIGTERM, note_sigterm)


def track(proc) -> None:
    """Remember a scheduler child so SIGTERM can be forwarded to it.

    If the drain already started, signal the child now. A job that
    passed the pre-start check and then lost the race still stops
    between its own steps instead of running the rest of the chain.
    """
    with _lock:
        _children.append(proc)
    if _requested and proc.poll() is None:
        _signal_one(proc)


def untrack(proc) -> None:
    with _lock:
        try:
            _children.remove(proc)
        except ValueError:
            pass


def _signal_one(proc) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
    except OSError:
        pass


def signal_children() -> None:
    """Forward SIGTERM to direct children. Do not signal their children.

    The daily child is ``python run_pipeline.py``. The refresh child is
    ``bash scripts/refresh_pass.sh``. Each of those stops after the step
    it is in. Signaling the process group would kill the step itself.
    """
    with _lock:
        kids = list(_children)
    for proc in kids:
        _signal_one(proc)


def wait_children() -> None:
    """Block until tracked children have exited.

    Polls instead of calling ``Popen.wait`` from this thread. The job
    thread is already in ``wait``, and two waiters on one Popen can
    contend. Railway's SIGKILL is the backstop if a step never returns.
    """
    import time

    while True:
        with _lock:
            live = [p for p in _children if p.poll() is None]
        if not live:
            return
        time.sleep(0.2)
