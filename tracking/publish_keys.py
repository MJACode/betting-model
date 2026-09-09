"""The publishing lock_key, in ONE place, because three producers mint it.

WHAT A LOCK_KEY IS. Every publishing surface (Discord, push) and the
opening-signal shadow track identify a pick by a synthesised string, and
`push_sent(lock_key, kind)` is UNIQUE — so the key IS the answer to "have we
already announced this bet?". Two picks that share a key are one pick as far as
every surface is concerned, and the second one is not "delayed": it is gone,
permanently and silently, because the ledger row for the first one blocks it
forever.

THE BUG THIS FIXES (2026-09-09). The key was
`game_id:model_id[:player_id]`, which is unique per pick for every model that
writes `player_id` — every distributional prop model does, and game-level
models have one pick per game by construction. `nfl_prop_market` does neither:
it writes `player_key` (a name slug, its settlement join) and `prop_market`,
and leaves `player_id` NULL. So EVERY nfl_prop_market pick in a game collapsed
to the single key `<game_id>:nfl_prop_market`.

Measured against production on 2026-09-09: 8 eligible BETs, 7 ledgered keys.
`Sam Darnold Under 19.5 Comp (MGM)` (NE @ SEA, written 09-09 08:26 ET for that
night's kickoff) was in the app and could never reach Discord or push, because
`Jadarian Price Over 1.5 Rec (FD)` had claimed `NFL_2026_01_NE_SEA:
nfl_prop_market` the previous morning. `opening_signals` lost the same row to
its own `ON CONFLICT (lock_key) DO NOTHING`.

That is CLAUDE.md §1b's "the app, Discord and push show the same picks" broken
in a new place: not by an extra gate this time, but by an identity that cannot
tell two picks apart. It gets worse, not better, with the 24h prop lead ceiling
(#610) — a ceiling clusters a game's prop picks onto game day, which is exactly
when they collide.

WHAT THE KEY IS NOW. The same string, with `player_key` and `prop_market`
appended when the row carries them:

    game_id : model_id [: player_id] [: player_key] [: prop_market]

- A row with `player_id` set and the other two NULL — every distributional prop
  model, every game-level model, every sport but this one — produces a
  BYTE-IDENTICAL key to the old expression. Verified against production before
  the change: of every ledgered key, `nfl_prop_market`'s were the only ones
  that moved. So no other surface republishes anything.
- `nfl_prop_market` gets one key per proposition, which is what it always
  needed.

`pick_side` is deliberately NOT in the key, and must not be added. The key is
COARSER than the `picks` unique row on purpose (§1c): a pre-#311 side flip has
to collapse to the one bet of record, not announce both halves of it.

MIGRATION. The seven already-posted `nfl_prop_market` picks were re-ledgered
under their new keys before this shipped (`scripts/backfill_publish_keys.py`),
so the change posts the ONE pick that was swallowed and republishes nothing.
Re-run that script if a key component is ever added again.
"""
from __future__ import annotations

# The components that identify a pick, in order. `player_id` first so a row
# carrying only that one — the overwhelming majority, and every row ledgered
# before 2026-09-09 — keeps the exact key it was published under.
KEY_PARTS = ("player_id", "player_key", "prop_market")


def lock_key_sql(alias: str = "p") -> str:
    """The synthesised lock_key, as a SQL expression over `picks`."""
    tail = "".join(
        f"\n                       || COALESCE(':' || {alias}.{c}, '')"
        for c in KEY_PARTS
    )
    return f"{alias}.game_id || ':' || {alias}.model_id{tail}"


def key_partition_sql(alias: str = "p") -> str:
    """The same identity as a DISTINCT ON / GROUP BY tuple.

    Must always move WITH `lock_key_sql`: a DISTINCT ON coarser than the key
    drops rows before the ledger ever sees them, which is the failure this
    module exists to stop.
    """
    cols = ", ".join(f"COALESCE({alias}.{c}, '')" for c in KEY_PARTS)
    return f"{alias}.game_id, {alias}.model_id, {cols}"


# ── The LIVE key ─────────────────────────────────────────────────────────────
# In-play picks ledger under their own key -- `live:` prefixed, and carrying
# pick_side, because a live lane can legitimately hold an over AND an under on
# the same total across a game (each locked as its own bet of record, §1c).
#
# THE SAME COLLISION, ONE DAY LATER (2026-09-09). The live key was
# `live:game_id:model_id:pick_side` with NO player component, so every live
# prop BET a model wrote in one game collapsed onto one key -- a second
# quarterback's pass-attempt over, a second batter's hits over -- and the
# second one never announced. Same tail as the pre-game key, same guarantee:
# a row with no player columns produces a BYTE-IDENTICAL key to the old
# expression, which every game-level live model is, so nothing republishes.
# Measured before the change: of 172 discord_live and 609 live_signal ledger
# rows, ONE belonged to a pick with a player, and it was settled.

LIVE_KEY_PREFIX = "live:"


def live_lock_key_sql(alias: str = "p") -> str:
    """The in-play lock_key, as a SQL expression over `picks`."""
    tail = "".join(
        f"\n                       || COALESCE(':' || {alias}.{c}, '')"
        for c in KEY_PARTS
    )
    return (f"'{LIVE_KEY_PREFIX}' || {alias}.game_id || ':' || {alias}.model_id "
            f"|| ':' || {alias}.pick_side{tail}")


def live_lock_key(game_id: str, model_id: str, pick_side: str,
                  player_id: str | None = None, player_key: str | None = None,
                  prop_market: str | None = None) -> str:
    """The same key, minted in Python. MUST agree with live_lock_key_sql --
    pinned by tests/test_publish_key_identity.py."""
    parts = {"player_id": player_id, "player_key": player_key,
             "prop_market": prop_market}
    tail = "".join(f":{parts[c]}" for c in KEY_PARTS if parts[c])
    return f"{LIVE_KEY_PREFIX}{game_id}:{model_id}:{pick_side}{tail}"
