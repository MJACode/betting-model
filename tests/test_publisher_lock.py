"""Two publishers must not post the same pick twice.

THE BUG, MEASURED (2026-09-06). The #ncaaf channel carried

    NCAAF Picks · Sun Sep 6 — Ole Miss vs Louisville Under 55.5, -115 @ DK

TWICE at 12:29 PM, and `push_sent` holds exactly ONE row for it:

    lock_key NCAAF_2026-09-06_louisville_ole-miss:ncaaf_over_under
    kind     discord_signal
    sent_at  2026-09-06T12:29:11.358415-04:00
    message  1546195572803772550

One ledger row and two messages is the signature of a read-post-ledger race,
not of a duplicate pick: `picks` holds a single BET for that game+model. Two
processes read "not yet posted" inside the same window, both posted, and the
second INSERT was swallowed by ON CONFLICT DO NOTHING.

Both processes exist by design. `signal_publisher.publish_new_signals` shipped
2026-09-05 so a poller tick that writes a BET publishes it immediately, and it
is called from the pre-game line poller (the `pollers` service, every 30s) AND
from the scheduler's card polls, the refresh pass and the daily pipeline (the
`worker` service). The push half of the same publish is stamped 12:29:11.106,
252ms earlier, so both surfaces were inside the window.

The ledger cannot fix this on its own: it only learns about a send AFTER the
send. So the sequence is serialized with a Postgres advisory lock
(tracking/publish_lock.py), which is held by a session and visible cluster-wide.
"""

from __future__ import annotations

import pytest

from tracking import discord_notifier as dn
from tracking import publish_lock as pl
from tracking import push_notifier as pn


class _Conn:
    """A Postgres-ish connection whose advisory lock is really exclusive."""

    #: shared across instances, the way a real cluster's lock table is
    held: set[int] = set()

    def __init__(self, rows=()):
        self.rows = list(rows)
        self.posts: list = []
        self.inserts: list = []

    def execute(self, sql, params=None):
        s = sql.strip()
        if "pg_try_advisory_lock" in s:
            key = params[0]
            if key in _Conn.held:
                return _Result([(False,)])
            _Conn.held.add(key)
            return _Result([(True,)])
        if "pg_advisory_unlock" in s:
            _Conn.held.discard(params[0])
            return _Result([(True,)])
        if s.upper().startswith("INSERT"):
            self.inserts.append(params)
            return _Result([])
        return _Result(self.rows)

    def commit(self):
        pass

    def close(self):
        pass


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


@pytest.fixture(autouse=True)
def _clear_locks():
    _Conn.held.clear()
    yield
    _Conn.held.clear()


# ── the lock itself ──────────────────────────────────────────────────────────

def test_the_second_holder_is_turned_away_not_queued():
    """Waiting would just post the same batch a moment later. The right answer
    is to do nothing: the holder is publishing these very signals right now."""
    a, b = _Conn(), _Conn()
    with pl.publish_lock(a, pl.DISCORD_SIGNALS_LOCK, "A") as first:
        assert first is True
        with pl.publish_lock(b, pl.DISCORD_SIGNALS_LOCK, "B") as second:
            assert second is False


def test_the_lock_is_released_so_the_next_pass_can_publish():
    a = _Conn()
    with pl.publish_lock(a, pl.DISCORD_SIGNALS_LOCK, "A"):
        pass
    with pl.publish_lock(_Conn(), pl.DISCORD_SIGNALS_LOCK, "B") as owned:
        assert owned is True, "a released lock must not block the next pass"


def test_an_exception_mid_publish_does_not_wedge_every_later_pass():
    """Without the finally, one raised webhook error would silence the channel
    until the pod restarted — a worse outage than the duplicate it prevents."""
    with pytest.raises(RuntimeError):
        with pl.publish_lock(_Conn(), pl.DISCORD_SIGNALS_LOCK, "A"):
            raise RuntimeError("webhook 500")
    with pl.publish_lock(_Conn(), pl.DISCORD_SIGNALS_LOCK, "B") as owned:
        assert owned is True


def test_the_producers_do_not_share_one_key():
    """A slow Discord webhook must not hold up the push path, or vice versa."""
    keys = [pl.DISCORD_SIGNALS_LOCK, pl.DISCORD_LIVE_LOCK, pl.PUSH_SIGNALS_LOCK]
    assert len(set(keys)) == len(keys)


def test_a_connection_that_cannot_lock_still_publishes():
    """FAILS OPEN. A publisher that refused to publish because it could not take
    a lock would be a worse failure than the duplicate."""

    class _NoLock:
        def execute(self, sql, params=None):
            raise RuntimeError("no such function: pg_try_advisory_lock")

    with pl.publish_lock(_NoLock(), pl.DISCORD_SIGNALS_LOCK, "A") as owned:
        assert owned is True


# ── the producers actually take it ───────────────────────────────────────────

def _signal_row(lock_key="NCAAF_2026-09-06_louisville_ole-miss:ncaaf_over_under"):
    # _new_signals' SELECT list, in order. Dated forward so the started-game
    # guard keeps treating it as an upcoming game as the real clock moves on.
    return (lock_key, "Ole Miss vs Louisville Under 55.5", "NCAAF",
            "ncaaf_over_under", 0.7176, 0.1827, -115.0, 0.02, "HIGH",
            "Ole Miss", "Louisville", "2099-09-06T23:30:00+00:00",
            None, "2026-09-06T16:29:04+00:00", None, None, 0.0, -200.0)


def test_two_overlapping_discord_runs_post_the_card_once(monkeypatch):
    """THE REGRESSION, end to end. Both runs see an un-ledgered signal; only the
    one holding the lock may post it."""
    posts: list = []
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {"NCAAF": "http://ncaaf"})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_LIVE", "")
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_RESULTS", "")
    monkeypatch.setattr(dn.config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    monkeypatch.setattr(dn, "_post", lambda url, payload: posts.append(payload) or "1")

    outer = _Conn([_signal_row()])
    inner = _Conn([_signal_row()])

    # The `pollers` tick lands while the `worker` pass is mid-post: real
    # _post, called from the run that owns the lock, re-enters the notifier.
    def _post_then_reenter(url, payload):
        posts.append(payload)
        monkeypatch.setattr(dn, "get_connection", lambda: inner)
        assert dn.notify_discord_signals(target_date="2026-09-06") == 0, (
            "the second run posted while the first still held the lock")
        return "1"

    monkeypatch.setattr(dn, "get_connection", lambda: outer)
    monkeypatch.setattr(dn, "_post", _post_then_reenter)

    assert dn.notify_discord_signals(target_date="2026-09-06") == 1
    assert len(posts) == 1, "the Ole Miss card went to the channel twice"
    assert [p[0] for p in inner.inserts] == [], "the blocked run must ledger nothing"


def test_the_blocked_run_leaves_the_signal_eligible_for_the_next_pass(monkeypatch):
    """Nothing is consumed by being turned away: the batch is still un-ledgered,
    so the very next pass publishes it if the holder died first."""
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {"NCAAF": "http://ncaaf"})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    monkeypatch.setattr(dn.config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    monkeypatch.setattr(dn.time, "sleep", lambda _s: None)
    monkeypatch.setattr(dn, "_post", lambda url, payload: "1")

    blocker = _Conn()
    with pl.publish_lock(blocker, pl.DISCORD_SIGNALS_LOCK, "held"):
        conn = _Conn([_signal_row()])
        monkeypatch.setattr(dn, "get_connection", lambda: conn)
        assert dn.notify_discord_signals(target_date="2026-09-06") == 0
        assert conn.inserts == []

    conn = _Conn([_signal_row()])
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    assert dn.notify_discord_signals(target_date="2026-09-06") == 1
    assert [p[0] for p in conn.inserts] == [_signal_row()[0]]


@pytest.mark.parametrize(
    "module, fn, key",
    [
        (dn, "notify_discord_signals", "DISCORD_SIGNALS_LOCK"),
        (dn, "notify_discord_live", "DISCORD_LIVE_LOCK"),
        (pn, "notify_signal_changes", "PUSH_SIGNALS_LOCK"),
    ],
)
def test_every_signal_publisher_takes_the_lock(module, fn, key):
    """CLAUDE.md §1b: a change to how one surface publishes is assessed against
    all of them. The duplicate was VISIBLE in Discord because Discord renders a
    card; the push path has the identical shape and is worse when it doubles."""
    import inspect
    src = inspect.getsource(getattr(module, fn))
    assert "publish_lock(" in src, f"{fn} publishes without the lock"
    assert key in src, f"{fn} must take {key}"
