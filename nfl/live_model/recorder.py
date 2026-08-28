"""
Persist every decision, bet or pass, before anything else happens to it.

WHY A FILE AND NOT THE DATABASE. The hot path polls every ten seconds and must
never block on a network write. A JSONL append is a syscall; a Postgres round
trip from a container that may be mid redeploy is not. The file lives on the
mounted volume, so it survives the redeploys that wipe everything else in the
container, which is the same reason the paid snapshots live there.

WHY PASSES ARE RECORDED TOO. A log of only the bets cannot be audited. The
question after a slate is not just "did the bets win" but "did the lane see the
quotes it should have seen, and decline for the reasons it should have". A pass
with reason `too_late:180` is evidence the gate worked; its absence is evidence
of nothing at all.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

from .config import ARTIFACT_DIR

log = logging.getLogger(__name__)

DEFAULT_LOG = ARTIFACT_DIR / "prop_snaps" / "decisions"


def _log_dir() -> Path:
    return Path(os.getenv("DECISION_LOG_DIR", str(DEFAULT_LOG)))


class JsonlRecorder:
    """
    Append one JSON object per decision, flushed on every write.

    Flushing on every write costs a syscall and buys the only property that matters
    here: a worker killed mid slate has still persisted every decision it made
    up to the moment it died. Buffering would trade that for nothing, since the
    write rate is a few per minute.
    """

    def __init__(self, path: Path | None = None, day: str | None = None):
        d = _log_dir()
        d.mkdir(parents=True, exist_ok=True)
        day = day or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        self.path = path or (d / f"decisions_{day}.jsonl")
        self._lock = threading.Lock()

    def __call__(self, decision) -> None:
        row = decision.to_row()
        row["recorded_at"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(row, default=str)
        # Serialised because the worker may grow a second thread later, and a
        # torn line in an append only audit log is unrecoverable.
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())

    def read_back(self) -> list[dict]:
        """Every decision written so far. Used by the reporter and by tests."""
        if not self.path.exists():
            return []
        out = []
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                # A torn final line means the process died mid write. Keep the
                # rest rather than losing the slate to one bad row.
                log.warning("skipping unparseable decision line")
        return out


def load_day(day: str) -> list[dict]:
    """All decisions recorded on one UTC day."""
    return JsonlRecorder(day=day).read_back()
