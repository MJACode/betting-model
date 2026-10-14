#!/usr/bin/env python3
"""Post the 2026-10-14 record correction once, then stop.

The words are the constant below. A job argument cannot change them. Discord
gets that text. X gets the same words with the ** markers removed. The plain
text is longer than one tweet, so the tweet is everything before the per-sport
line and the reply is the rest of the words.

Each surface is checked in push_sent before it is sent. A failed read posts
nothing. A confirmed send is ledgered and committed before the next surface,
so a later failure cannot send the one that already went out.

Pinning uses the bot token. A webhook cannot pin. A missing token or a
rejected pin is reported and does not block the posts.
"""

from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

LOCK_KEY = "record_correction:2026-10-14"
KIND_DISCORD = "discord_correction"
KIND_X = "x_correction"
KIND_X_REPLY = "x_correction_reply"

# Verbatim. The unit losses use U+2212. Do not retype them as hyphens.
DISCORD_TEXT = (
    "**Record correction.** We audited every pick since Sep 1, and no pick was "
    "graded wrong. Our recaps had been counting 109 picks that were never "
    "posted, and those went 41-68. They're out now, so the record only counts what you saw. "
    "Corrected all-time: **431-375-2, +16.92u**. "
    "MLB 193-187-2 (\u221215.45u), NCAAF 96-83 (+3.44u), NFL 33-38 (\u221210.92u), "
    "NHL 63-46 (+13.58u), WNBA 45-21 (+25.27u), UFC 1-0 (+1.00u). "
    "Props now grade the night of the game, so no more morning restatements."
)

_ET = ZoneInfo("America/New_York")
_X_STATUS = "https://x.com/signalbasepicks/status/"
_DISCORD_API = "https://discord.com/api/v10"
_MAX_TWEET = 280


class LedgerUnread(RuntimeError):
    """The ledger could not be read. Posting would risk a duplicate."""


def x_posts(text: str = DISCORD_TEXT) -> tuple[str, str]:
    """Plain tweet, then the reply. The join is one space. Nothing is trimmed
    off either side except the ** markers X does not render."""
    plain = text.replace("**", "")
    at = plain.find("MLB ")
    if at < 0:
        raise RuntimeError("the per-sport line is missing")
    head, tail = plain[:at].rstrip(), plain[at:]
    if plain != head + " " + tail:
        raise RuntimeError("the X split dropped characters")
    if len(head) > _MAX_TWEET or len(tail) > _MAX_TWEET:
        raise RuntimeError(
            f"correction does not fit in two tweets ({len(head)}, {len(tail)})"
        )
    if not head or not tail:
        raise RuntimeError("the X split produced an empty post")
    return head, tail


def _results_url() -> str:
    import config
    return (config.DISCORD_WEBHOOK_RESULTS or "").strip()


def _read(conn, kind: str) -> tuple[bool, str | None]:
    try:
        row = conn.execute(
            "SELECT message_id FROM push_sent WHERE lock_key = %s AND kind = %s",
            (LOCK_KEY, kind),
        ).fetchone()
    except Exception as exc:  # noqa: BLE001 — an unread ledger must not post
        raise LedgerUnread(f"push_sent read failed for {kind}") from exc
    if row is None:
        return False, None
    message_id = row[0]
    return True, (str(message_id) if message_id else None)


def _write(conn, kind: str, message_id: str | None) -> bool:
    """Commit the row before the caller does anything else. False means the
    row is still absent: the caller must not send this surface again and must
    not send the next one."""
    try:
        conn.execute(
            "INSERT INTO push_sent (lock_key, kind, sent_at, message_id) "
            "VALUES (%s, %s, %s, %s) ON CONFLICT (lock_key, kind) DO NOTHING",
            (LOCK_KEY, kind, datetime.now(_ET).isoformat(), message_id),
        )
        conn.commit()
    except Exception:
        return False
    try:
        sent, _ = _read(conn, kind)
    except LedgerUnread:
        return False
    return sent


def _stored_id(message_id: str | None) -> str | None:
    """_post returns the sentinel 'ok' when Discord confirmed a body with no id."""
    if not message_id or message_id == "ok":
        return None
    return message_id


def _jump(guild_id: str | None, channel_id: str | None,
          message_id: str | None) -> str | None:
    if guild_id and channel_id and message_id:
        return f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
    return None


def _tweet_url(tweet_id: str | None) -> str | None:
    if tweet_id and tweet_id.isdigit():
        return _X_STATUS + tweet_id
    return None


def _place(url: str) -> tuple[str | None, str | None]:
    """Guild and channel for the results webhook. GET metadata posts nothing."""
    import requests
    try:
        resp = requests.get(url.split("?", 1)[0], timeout=15)
    except Exception:
        return None, None
    if resp.status_code != 200:
        return None, None
    try:
        body = resp.json()
    except Exception:
        return None, None
    guild = body.get("guild_id")
    channel = body.get("channel_id")
    return (str(guild) if guild else None, str(channel) if channel else None)


def _pin(channel_id: str | None, message_id: str | None) -> dict:
    """Best effort. Never raises. A webhook has no pin permission."""
    if not channel_id or not message_id:
        return {"status": "failed", "reason": "channel or message id missing"}
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        return {"status": "failed",
                "reason": "DISCORD_BOT_TOKEN is not set; a webhook cannot pin"}
    import requests
    try:
        resp = requests.put(
            f"{_DISCORD_API}/channels/{channel_id}/pins/{message_id}",
            headers={"Authorization": f"Bot {token}"},
            timeout=15,
        )
    except Exception as exc:  # noqa: BLE001 — pin failure is reported, not raised
        return {"status": "failed", "reason": type(exc).__name__}
    if resp.status_code in (200, 204):
        return {"status": "pinned"}
    return {"status": "failed", "reason": f"HTTP {resp.status_code}"}


def _real_post(url: str, text: str) -> str | None:
    from tracking.discord_notifier import _post
    return _post(url, {"content": text})


def _real_tweet(text: str, reply_to: str | None) -> str | None:
    from tracking.x_publisher import post_tweet
    return post_tweet(text, reply_to=reply_to)


def publish_record_correction(conn=None, *, post=None, tweet=None,
                              place=None, pin=None, can_post=None) -> dict:
    """Send the correction. Returns ids and urls. Raises LedgerUnread before
    any send when the ledger cannot be read, and raises when a send was not
    confirmed and nothing was ledgered for that surface (the job then retries
    only the surfaces still absent)."""
    from tracking.x_publisher import results_can_post

    own = conn is None
    if own:
        from data.db import get_connection
        conn = get_connection()
    post = post or _real_post
    tweet = tweet or _real_tweet
    place = place or _place
    pin = pin or _pin
    can_post = can_post or results_can_post
    try:
        return _publish(conn, post=post, tweet=tweet, place=place, pin=pin,
                        can_post=can_post)
    finally:
        if own:
            conn.close()


def _publish(conn, *, post, tweet, place, pin, can_post) -> dict:
    from tracking.x_publisher import _assert_no_link

    head, tail = x_posts()
    _assert_no_link(head)
    _assert_no_link(tail)
    if len(DISCORD_TEXT) > 2000:
        raise RuntimeError("Discord correction exceeds the content limit")

    discord_sent, discord_id = _read(conn, KIND_DISCORD)
    x_sent, x_id = _read(conn, KIND_X)
    reply_sent, reply_id = _read(conn, KIND_X_REPLY)

    url = _results_url()
    out: dict = {
        "lock_key": LOCK_KEY,
        "discord_message_id": _stored_id(discord_id),
        "discord_url": None,
        "pin": None,
        "tweet_id": x_id if x_sent else None,
        "tweet_url": _tweet_url(x_id) if x_sent else None,
        "reply_id": reply_id if reply_sent else None,
        "reply_url": _tweet_url(reply_id) if reply_sent else None,
    }

    if not discord_sent:
        if not url:
            raise RuntimeError("DISCORD_WEBHOOK_RESULTS is not set")
        message_id = post(url, DISCORD_TEXT)
        stored = _stored_id(message_id if isinstance(message_id, str) else None)
        if not message_id:
            raise RuntimeError("Discord results post was not confirmed")
        if not _write(conn, KIND_DISCORD, stored):
            out["discord_message_id"] = stored
            out["ledger"] = "discord_correction write failed; X was not sent"
            return _with_place(out, url, stored, place, pin)
        discord_id = stored
        out["discord_message_id"] = stored

    posted_id = _stored_id(discord_id)
    if posted_id and url:
        out = _with_place(out, url, posted_id, place, pin)
    elif out["pin"] is None:
        reason = ("no results webhook" if not url
                  else "channel or message id missing")
        out["pin"] = {"status": "failed", "reason": reason}

    if not x_sent:
        if not can_post():
            raise RuntimeError("X publisher is off or its credentials are missing")
        tweet_id = tweet(head, None)
        if not tweet_id or tweet_id == "dry-run":
            raise RuntimeError("X post was not confirmed")
        if not _write(conn, KIND_X, tweet_id):
            out["tweet_id"] = tweet_id
            out["tweet_url"] = _tweet_url(tweet_id)
            out["ledger"] = "x_correction write failed; the reply was not sent"
            return out
        x_id = tweet_id
        out["tweet_id"] = tweet_id
        out["tweet_url"] = _tweet_url(tweet_id)

    if not reply_sent:
        if not x_id or not str(x_id).isdigit():
            raise RuntimeError("the first tweet has no id, so the reply was not sent")
        if not can_post():
            raise RuntimeError("X publisher is off or its credentials are missing")
        reply = tweet(tail, str(x_id))
        if not reply or reply == "dry-run":
            raise RuntimeError("X reply was not confirmed")
        if not _write(conn, KIND_X_REPLY, reply):
            out["reply_id"] = reply
            out["reply_url"] = _tweet_url(reply)
            out["ledger"] = "x_correction_reply write failed"
            return out
        out["reply_id"] = reply
        out["reply_url"] = _tweet_url(reply)

    return out


def _with_place(out: dict, url: str, message_id: str | None, place, pin) -> dict:
    try:
        guild_id, channel_id = place(url)
    except Exception:
        guild_id, channel_id = None, None
    out["discord_url"] = _jump(guild_id, channel_id, message_id)
    try:
        out["pin"] = pin(channel_id, message_id)
    except Exception as exc:  # noqa: BLE001 — a pin must not cause a second post
        out["pin"] = {"status": "failed", "reason": type(exc).__name__}
    return out
