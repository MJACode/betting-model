"""Discord publish state is the board. VOID does not retract a post.

Matt, 2026-09-23: Discord is the source of truth. The app shows the same bets
the channel still has, and it does not present a bet the channel never got.

A confirmed post is a `push_sent` row of kind `discord_signal` (pre-game) or
`discord_live` (in-play). The row is written only after Discord accepts the
message. VOID does not delete that message and does not delete the row, so
the ledger IS the channel.

`opening_signals` is the CLV shadow track, not the board.
`opening_lock_is_live` / `discord_published_exists_sql` are the join a
reader should use (a capture is live only when this ledger has the key).
Capture, system health, and the publisher do not call them yet — those
readers still treat a capture row as locked. Wiring them is TBD. Nothing
here deletes a capture.
"""

from __future__ import annotations

from tracking.publish_keys import KEY_PARTS, LIVE_KEY_PREFIX

# The two kinds that are a message in a Discord channel. `new_bet` is the
# phone push and stores no message. `discord_free_pick.message_id` stores a
# lock_key, not a snowflake, and is a different channel.
DISCORD_LED_KINDS = ("discord_signal", "discord_live")


def lock_key_for_pick(row: dict, *, live: bool = False) -> str:
    """The same string `lock_key_sql` / `live_lock_key_sql` mint.

    Null and empty identity parts are omitted, matching
    `COALESCE(':' || col, '')`.
    """
    tail = "".join(f":{row[c]}" for c in KEY_PARTS if row.get(c))
    if live:
        return (f"{LIVE_KEY_PREFIX}{row['game_id']}:{row['model_id']}:"
                f"{row.get('pick_side') or ''}{tail}")
    return f"{row['game_id']}:{row['model_id']}{tail}"


def discord_published_exists_sql(lock_expr: str) -> str:
    """SQL: this lock was posted to a Discord channel and the post stands.

    Kinds are the channel posts only. A `new_bet` row is not Discord.
    """
    kinds = ", ".join(f"'{k}'" for k in DISCORD_LED_KINDS)
    return (f"EXISTS (SELECT 1 FROM push_sent s "
            f"WHERE s.lock_key = {lock_expr} AND s.kind IN ({kinds}))")


def discord_led_visible(condition_status: str | None,
                        published: bool | None) -> bool:
    """Whether a BET is an active Discord-led bet.

    `published` True  — the ledger has the lock. VOID does not hide it.
    `published` False — Discord does not have it. Not an active Discord bet.
    `published` None  — the ledger could not be read. A non-VOID bet keeps
    the pre-ledger display so a missing view cannot blank the board. A VOID
    stays hidden: there is no evidence the channel still shows it.
    """
    if published is True:
        return True
    if condition_status == "VOID":
        return False
    if published is False:
        return False
    return True


def void_hidden_from_board(condition_status: str | None,
                           published: bool | None) -> bool:
    """Today's scored list drops a VOID the channel does not still show.

    A published VOID stays: members who saw Discord must see the same bet.
    """
    if condition_status != "VOID":
        return False
    return published is not True


def opening_lock_is_live(captured: bool, discord_published: bool) -> bool:
    """Predicate for a reader that wants capture AND a Discord post.

    Not called by capture, system health, or the publisher yet. Those still
    treat "row exists" as locked. The capture row is not deleted on VOID
    (ON CONFLICT would just re-lock it). Wiring this in is TBD.
    """
    return bool(captured) and bool(discord_published)
