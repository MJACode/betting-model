"""A 200 from Expo is not a delivery.

Until 2026-09-12 `_expo_send` counted `len(chunk)` on any 2xx response, so a
message Apple refused — for want of an APNs key, or to a phone that had been
reinstalled — was logged as sent. The pipeline's own output would have read
"Push: 3 new, 0 dropped; 1 device(s)" with nobody notified, which is the exact
failure `docs/push_notifications.md` spent a session diagnosing from the other
end (1,736 ledgered events, zero registered devices).

Expo answers every send with one ticket PER MESSAGE, paired positionally, and
the ticket is the only thing that says what happened. These tests are about
reading it — and about the three ways the pairing can go wrong, because
disabling the wrong person's device is worse than disabling nobody's.
"""

from __future__ import annotations

import pytest

from tracking.push_notifier import _read_tickets


def _msgs(*tokens: str) -> list[dict]:
    return [{"to": t, "title": "x", "body": "y"} for t in tokens]


def test_ok_tickets_count_as_accepted():
    chunk = _msgs("tok-a", "tok-b")
    body = {"data": [{"status": "ok", "id": "r1"}, {"status": "ok", "id": "r2"}]}
    assert _read_tickets(chunk, body) == (2, [])


def test_an_error_ticket_is_not_counted_as_sent():
    """The whole point. The pre-fix code returned 2 here."""
    chunk = _msgs("tok-a", "tok-b")
    body = {
        "data": [
            {"status": "ok", "id": "r1"},
            {"status": "error", "message": "nope", "details": {"error": "MessageTooBig"}},
        ]
    }
    accepted, dead = _read_tickets(chunk, body)
    assert accepted == 1
    assert dead == []


def test_a_retired_device_is_named_for_disabling():
    chunk = _msgs("tok-live", "tok-dead")
    body = {
        "data": [
            {"status": "ok", "id": "r1"},
            {
                "status": "error",
                "message": '"ExponentPushToken[dead]" is not a registered push notification recipient',
                "details": {"error": "DeviceNotRegistered"},
            },
        ]
    }
    accepted, dead = _read_tickets(chunk, body)
    assert accepted == 1
    # Positional pairing: the SECOND message's token, not the first.
    assert dead == ["tok-dead"]


def test_a_credentials_failure_disables_nobody():
    """InvalidCredentials is the platform being broken, not the device.

    Disabling on it would quietly empty `device_push_tokens` the first time a
    push key expired, and the recovery would then need every user to re-opt-in.
    """
    chunk = _msgs("tok-a")
    body = {
        "data": [
            {"status": "error", "message": "bad key", "details": {"error": "InvalidCredentials"}}
        ]
    }
    accepted, dead = _read_tickets(chunk, body)
    assert accepted == 0
    assert dead == []


def test_a_request_level_rejection_accepts_nothing():
    chunk = _msgs("tok-a", "tok-b")
    body = {"errors": [{"code": "PUSH_TOO_MANY_EXPERIENCE_IDS", "message": "no"}]}
    assert _read_tickets(chunk, body) == (0, [])


@pytest.mark.parametrize(
    "body",
    [
        None,
        "not json",
        [],
        {"data": []},
        {"data": [{"status": "ok"}, {"status": "ok"}, {"status": "ok"}]},
    ],
    ids=["none", "string", "list", "no-tickets", "too-many-tickets"],
)
def test_an_unpairable_reply_counts_nothing_and_disables_nothing(body):
    """Every shape we cannot pair message-to-ticket.

    Counting them as sent is the old bug; guessing which token an error belongs
    to would be a worse new one, so both halves are zero.
    """
    chunk = _msgs("tok-a", "tok-b")
    assert _read_tickets(chunk, body) == (0, [])


def test_a_single_message_reply_may_be_a_bare_object():
    """Expo answers a one-message send with the ticket unwrapped."""
    chunk = _msgs("tok-a")
    assert _read_tickets(chunk, {"data": {"status": "ok", "id": "r1"}}) == (1, [])


def test_a_ticket_that_is_not_an_object_is_not_a_delivery():
    chunk = _msgs("tok-a")
    assert _read_tickets(chunk, {"data": ["surprise"]}) == (0, [])
