"""
The injury sweep was the single slowest step in the pass, and it set the floor
for everything parallel to it.

Measured on the 2026-08-30 16:17 pass — the first with per-step timing:

    injuries-refresh  103.9s   <- the whole parallel ingest group
    odds               46.3s
    everything else    <10s

1,569 requests to sports.core.api.espn.com, 98.0 seconds of them. ESPN's core
API is a graph of $ref links, so ONE team costs 1 + 2N requests: the injury
list, a detail fetch per injury, and an athlete fetch per injury purely to turn
an id into a display name.

TWO FIXES, and the order matters. Caching names REMOVES requests; threading
only makes the remaining ones overlap. ESPN has IP-blocked this worker twice
(CLAUDE.md §7) and WNBA settlement was dead for two weeks as a result, so
fewer requests is strictly safer than the same number issued faster — which is
why the pool is deliberately small and why the cache carries the bigger win.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.ingestors.injury_ingestor as inj  # noqa: E402

_SRC = (Path(__file__).parent.parent / "data" / "ingestors"
        / "injury_ingestor.py").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def _clear_cache():
    inj._ATHLETE_NAME_CACHE = {}
    yield
    inj._ATHLETE_NAME_CACHE = {}


# ── the cache removes requests ────────────────────────────────────────────────

def test_a_known_athlete_costs_no_request(monkeypatch):
    """The whole point: two thirds of the calls asked a question we knew."""
    called = []
    monkeypatch.setattr(inj.requests, "get",
                        lambda *a, **k: called.append(a) or (_ for _ in ()).throw(
                            AssertionError("should not fetch")))
    inj._ATHLETE_NAME_CACHE["12345"] = "Aaron Judge"
    assert inj._athlete_name("12345", "https://espn/athletes/12345") == "Aaron Judge"
    assert not called


def test_an_unknown_athlete_is_fetched_and_then_remembered(monkeypatch):
    calls = []

    class _R:
        status_code = 200
        def json(self): return {"displayName": "Shohei Ohtani"}

    monkeypatch.setattr(inj.requests, "get",
                        lambda *a, **k: calls.append(a) or _R())
    assert inj._athlete_name("999", "https://espn/athletes/999") == "Shohei Ohtani"
    assert len(calls) == 1
    # second time is free
    assert inj._athlete_name("999", "https://espn/athletes/999") == "Shohei Ohtani"
    assert len(calls) == 1, "a name was fetched twice — the cache is not holding"


def test_a_failed_lookup_is_not_cached(monkeypatch):
    """A transport failure must not poison the cache."""
    def _boom(*a, **k):
        raise RuntimeError("espn down")
    monkeypatch.setattr(inj.requests, "get", _boom)
    assert inj._athlete_name("777", "https://espn/athletes/777") == "Unknown"
    assert "777" not in inj._ATHLETE_NAME_CACHE


def test_a_SUCCESSFUL_response_with_no_name_is_not_cached(monkeypatch):
    """
    The case the previous test misses, and the one that actually bites: ESPN
    answers 200 but the payload has no displayName. Caching that "Unknown"
    would make one bad response permanent for the life of the process and the
    real name would never be recovered.

    The first version of this file only exercised the EXCEPTION path, so a
    mutation removing the `!= "Unknown"` guard passed cleanly — the raising
    branch returns before ever reaching the cache write. A test that cannot
    reach the line it is guarding is not guarding it.
    """
    class _R:
        status_code = 200
        def json(self): return {}          # 200, but no displayName

    calls = []
    monkeypatch.setattr(inj.requests, "get", lambda *a, **k: calls.append(a) or _R())
    assert inj._athlete_name("888", "https://espn/athletes/888") == "Unknown"
    assert "888" not in inj._ATHLETE_NAME_CACHE, (
        "an Unknown was cached — this athlete's real name can never be learned")
    # and it must retry next time rather than serving the cached Unknown
    inj._athlete_name("888", "https://espn/athletes/888")
    assert len(calls) == 2


def test_the_cache_seeds_from_our_own_stored_injuries(monkeypatch):
    """
    The answers are already in our `injuries` table from previous runs, so the
    cache is warm on the FIRST fetch after a restart rather than the second.
    """
    class _Conn:
        def execute(self, sql, params=None):
            assert "FROM injuries" in sql
            return self
        def fetchall(self):
            return [("1", "Mookie Betts"), ("2", "Freddie Freeman")]
        def close(self): pass

    import data.db as db
    monkeypatch.setattr(db, "get_connection", lambda *a, **k: _Conn())
    assert inj._seed_athlete_cache() == 2
    assert inj._ATHLETE_NAME_CACHE["1"] == "Mookie Betts"


def test_a_dead_database_leaves_the_cache_empty_not_broken(monkeypatch):
    """A cold cache costs the old number of requests. It must never cost a
    wrong name, and must never raise into the ingest."""
    import data.db as db
    monkeypatch.setattr(db, "get_connection",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no db")))
    assert inj._seed_athlete_cache() == 0


# ── the pool overlaps what is left ────────────────────────────────────────────

def test_teams_are_fetched_concurrently():
    assert "ThreadPoolExecutor" in _SRC
    assert "as_completed" in _SRC


def test_the_pool_is_small_because_espn_has_blocked_us_twice():
    """
    Not a style preference. ESPN IP-blocked this worker twice and WNBA
    settlement was dead for two weeks; a large pool trades one outage for
    another.
    """
    import re
    m = re.search(r"max_workers=(\d+)", _SRC)
    assert m, "no explicit worker count — an unbounded pool is the risk"
    assert int(m.group(1)) <= 8, f"pool of {m.group(1)} is too aggressive for ESPN"


def test_one_team_failing_does_not_lose_the_others():
    """The same rule the refresh pass itself lives by."""
    i = _SRC.index("with ThreadPoolExecutor")
    block = _SRC[i:i + 900]
    assert "except Exception as exc:" in block
    assert "results[ab] = []" in block


def test_output_order_follows_the_team_list_not_completion_order():
    """
    Threads complete out of order. Iterating completion order would shuffle the
    output rows for no reason and make every future comparison against a stored
    run noisy.
    """
    assert "for abbrev in team_ids:" in _SRC
    assert _SRC.index("with ThreadPoolExecutor") < _SRC.index("for abbrev in team_ids:")
