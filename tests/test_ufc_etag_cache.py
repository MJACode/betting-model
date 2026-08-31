"""
The UFC poll's ETag cache has to survive a deploy, or the poll is pointless.

Measured on the 2026-08-30 17:17 pass — the first with per-step timing —
`ufc-results-poll` was the SLOWEST step in the whole pass at 119.7s, on a day
with no UFC card.

The design was already right: the mirror serves an ETag, an unchanged poll
should cost one HEAD, and the daily 6am run deliberately does NOT take the
skip path so a broken check can't silently swallow a card. What was wrong was
where the cache lived.

    _ETAG_CACHE = tempfile.gettempdir() / "ufc_mirror_etag.json"

with the comment "losing it costs exactly one extra download after a redeploy".
True per redeploy, wrong in aggregate: /tmp is wiped by EVERY deploy, and this
repo took fifteen of them that day, so the cache was almost never warm and the
hourly poll almost always paid the full ingest.

The network was only ~3s of the 119.7s. The rest is parsing and ingesting
1.9MB of CSV that had not changed — which is why the fix is to skip the work,
not to speed it up.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors import ufc_csv_loader as ufc  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("UFC_CSV_ETAG_CACHE", raising=False)
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    yield


def test_a_mounted_volume_is_preferred_over_tmp(monkeypatch, tmp_path):
    """The whole fix: a volume survives a deploy, /tmp does not."""
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    assert ufc._etag_cache_path() == tmp_path / "ufc_mirror_etag.json"


def test_no_volume_still_falls_back_to_tmp(monkeypatch):
    """A laptop, a CI box, or a service with no volume must still work."""
    p = ufc._etag_cache_path()
    assert p.parent == Path(tempfile.gettempdir())


def test_a_volume_path_that_does_not_exist_falls_back(monkeypatch):
    """
    Railway sets the variable; the mount is what makes it real. Writing to a
    path that isn't mounted would fail silently inside _store_etag's except and
    leave the cache permanently cold — the exact bug being fixed, in a new
    costume.
    """
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", "/definitely/not/mounted")
    assert ufc._etag_cache_path().parent == Path(tempfile.gettempdir())


def test_an_explicit_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    monkeypatch.setenv("UFC_CSV_ETAG_CACHE", "/custom/etag.json")
    assert ufc._etag_cache_path() == Path("/custom/etag.json")


def test_the_path_is_resolved_per_call_not_at_import():
    """
    A module-level snapshot cannot be exercised by a test that sets the env
    var, and an untestable path is how this bug survived in the first place.
    """
    src = (Path(__file__).parent.parent / "data" / "ingestors"
           / "ufc_csv_loader.py").read_text(encoding="utf-8")
    assert "_ETAG_CACHE = " not in src, (
        "the cache path must be a function call, not a module constant")
    assert src.count("_etag_cache_path()") >= 3, (
        "every reader and writer must resolve the path itself")


def test_a_round_trip_actually_persists(monkeypatch, tmp_path):
    """Store then read, through the real functions, at the real path."""
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    assert ufc._cached_etag() is None
    ufc._store_etag('W/"abc123"')
    assert ufc._cached_etag() == 'W/"abc123"'


def test_an_empty_etag_is_never_stored(monkeypatch, tmp_path):
    """
    Storing a falsy value would make mirror_unchanged() compare None to None
    and skip a real card.
    """
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    ufc._store_etag(None)
    ufc._store_etag("")
    assert ufc._cached_etag() is None


def test_mirror_unchanged_is_false_when_anything_is_unknown(monkeypatch, tmp_path):
    """
    Conservative by design: a HEAD failure or a cold cache must FETCH, never
    skip. A skipped poll that should have run loses a card silently, and the
    6am daily run deliberately doesn't take this path precisely so a broken
    check has a backstop.
    """
    monkeypatch.setenv("RAILWAY_VOLUME_MOUNT_PATH", str(tmp_path))
    monkeypatch.setattr(ufc, "_mirror_etag", lambda: None)
    assert ufc.mirror_unchanged() is False          # HEAD failed

    monkeypatch.setattr(ufc, "_mirror_etag", lambda: 'W/"new"')
    assert ufc.mirror_unchanged() is False          # nothing cached

    ufc._store_etag('W/"new"')
    assert ufc.mirror_unchanged() is True           # match -> skip


def test_the_daily_run_never_takes_the_skip_path():
    """
    A silently-skipping poll is invisible; the 6am run is the backstop that
    isn't. Pinned because 'make the daily run fast too' is a tempting and
    wrong optimisation.
    """
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "if poll and mirror_unchanged():" in src, (
        "the skip must be gated on poll=True, never taken by the daily run")
