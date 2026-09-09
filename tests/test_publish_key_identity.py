"""One pick, one publishing key — and two picks are never one key.

THE BUG (2026-09-09, found auditing "do the NFL bets line up with Discord?").
The key every publishing surface identifies a pick by was
`game_id:model_id[:player_id]`. `push_sent(lock_key, kind)` is UNIQUE, so two
picks sharing a key are ONE pick to Discord, to push, and to the CLV shadow
track — and the second is not delayed, it is gone, because the first one's
ledger row answers "already announced" forever.

`nfl_prop_market` shares no identity with the rest of the repo: it writes
`player_key` (a name slug) and `prop_market`, and leaves `player_id` NULL. So
every prop it picked in one game collapsed onto `<game_id>:nfl_prop_market`.

Measured against production before the fix: 8 eligible BETs, 7 ledgered keys.
`Sam Darnold Under 19.5 Comp (MGM)` — written 2026-09-09 08:26 ET for that
night's NE @ SEA kickoff — was on the app's board and could never reach Discord
or a phone, because `Jadarian Price Over 1.5 Rec (FD)` had taken the key the
morning before. That is CLAUDE.md §1b broken in a new place: not an extra gate
this time, an identity too coarse to tell two bets apart.

WHAT THESE TESTS PIN, and why each one is separate:

  * two propositions -> two keys        (the bug itself)
  * player_id-only rows keep the OLD key BYTE FOR BYTE (nothing republishes;
    this is the property that let the fix ship without re-announcing 119 picks)
  * pick_side stays OUT of the key      (§1c: a side flip is ONE bet of record)
  * every producer mints it from the shared helper, and the DISTINCT ON matches
    the key it dedupes toward — a partition coarser than the key drops rows
    before the ledger is ever consulted, which is the same bug one layer up.
"""
from __future__ import annotations

import re

from tracking import discord_notifier as dn
from tracking import opening_signals as osig
from tracking import push_notifier as pn
from tracking.publish_keys import KEY_PARTS, key_partition_sql, lock_key_sql


# ── the key, evaluated as Python so the property is checked, not the string ──

def _key(row: dict) -> str:
    """`lock_key_sql` applied to one row, by the same rule Postgres applies:
    `COALESCE(':' || x, '')` is '' when x IS NULL, else ':' + x."""
    out = f"{row['game_id']}:{row['model_id']}"
    for part in KEY_PARTS:
        v = row.get(part)
        if v is not None:
            out += f":{v}"
    return out


_PRICE = {"game_id": "NFL_2026_01_NE_SEA", "model_id": "nfl_prop_market",
          "player_id": None, "player_key": "jadarianprice",
          "prop_market": "player_receptions", "pick_side": "over"}
_DARNOLD = {"game_id": "NFL_2026_01_NE_SEA", "model_id": "nfl_prop_market",
            "player_id": None, "player_key": "samdarnold",
            "prop_market": "player_pass_completions", "pick_side": "under"}
_DOWNS_REC = {"game_id": "NFL_2026_01_MIA_LV", "model_id": "nfl_prop_receptions",
              "player_id": "00-0038997", "player_key": None,
              "prop_market": None, "pick_side": "under"}


def test_two_propositions_in_one_game_are_two_keys():
    """The measured failure: these two shared a key, so only one ever posted."""
    assert _key(_PRICE) != _key(_DARNOLD), (
        "two nfl_prop_market picks in one game still collapse to one key — the "
        "second one can never reach Discord or a phone")


def test_the_same_player_on_two_markets_is_two_keys():
    """`nfl_prop_market` is ONE model covering EVERY market, unlike the eleven
    distributional models (one model per market, so player alone was enough).
    A quarterback with a completions pick and a pass-yards pick is two bets."""
    comp = dict(_DARNOLD)
    yards = dict(_DARNOLD, prop_market="player_pass_yards")
    assert _key(comp) != _key(yards)


def test_a_player_id_row_keeps_the_key_it_was_published_under():
    """THE PROPERTY THAT LET THIS SHIP.

    Every row ledgered before 2026-09-09 — every sport, every game-level model,
    every distributional prop model — carries player_id and neither of the new
    components. Its key must be byte-identical to the old expression, or the
    first pass after deploy re-announces the entire published history.

    Verified against production the same way before applying: of every ledgered
    key, `nfl_prop_market`'s were the only ones that moved.
    """
    old = (f"{_DOWNS_REC['game_id']}:{_DOWNS_REC['model_id']}"
           f":{_DOWNS_REC['player_id']}")
    assert _key(_DOWNS_REC) == old


def test_a_game_level_row_keeps_the_key_it_was_published_under():
    """Same property with every component NULL — the opener and wind cards."""
    row = {"game_id": "NFL_2026_01_CLE_JAX", "model_id": "nfl_opener_spread",
           "player_id": None, "player_key": None, "prop_market": None}
    assert _key(row) == "NFL_2026_01_CLE_JAX:nfl_opener_spread"


def test_pick_side_is_not_in_the_key():
    """§1c, and it must stay this way. The key is deliberately COARSER than the
    `picks` unique row: a pre-#311 side flip has to collapse to the one bet of
    record, not announce both halves of it. Adding pick_side here would look
    like more precision and would publish the same game twice."""
    assert "pick_side" not in KEY_PARTS
    flipped = dict(_PRICE, pick_side="under")
    assert _key(flipped) == _key(_PRICE)


# ── every producer mints it the same way ─────────────────────────────────────

class _Conn:
    def __init__(self):
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchall(self):
        return []

    def fetchone(self):
        return (0,)

    def commit(self):
        pass


def _sql(producer, *args):
    conn = _Conn()
    producer(conn, *args)
    return conn.sql


def test_every_publisher_mints_the_key_from_the_shared_helper():
    """A hand-rolled copy is how the surfaces drifted in the first place."""
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09"),
                _sql(pn._dropped_signals, "2026-09-09")):
        assert lock_key_sql() in sql


def test_the_restate_delete_path_resolves_the_same_key():
    """`_delete_posted` joins push_sent back to picks to find the message a
    restatement replaces. Joined on a key the poster no longer mints, it finds
    nothing and leaves the stale post standing next to its correction — the
    worst of the three outcomes, and the one nobody goes looking for.

    Read from the SOURCE, not by calling it: `_delete_posted` returns before it
    reaches the query when no webhook is configured, which is every test run.
    """
    import inspect
    src = inspect.getsource(dn._delete_posted)
    assert "{lock_key_sql()}" in src or lock_key_sql() in src


def test_capture_mints_the_same_key_as_the_publishers():
    """`opening_signals` has `ON CONFLICT (lock_key) DO NOTHING`, so a coarse
    key there silently drops the second proposition from the CLV track too —
    measured: 8 prop_market BETs, 7 shadow rows."""
    import inspect
    src = inspect.getsource(osig.capture_opening_signals)
    assert "{lock_key_sql()}" in src or lock_key_sql() in src, (
        "capture must build its key from tracking.publish_keys")


def test_the_distinct_on_is_never_coarser_than_the_key():
    """A partition coarser than the key drops the row before the ledger sees
    it, so the ledger backfill cannot save it. They must move together."""
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09")):
        assert f"DISTINCT ON ({key_partition_sql()})" in sql
    for part in KEY_PARTS:
        assert f"COALESCE(p.{part}, '')" in key_partition_sql(), (
            f"{part} is in the key but not in the DISTINCT ON")


# ── a voided pick is not publishable ─────────────────────────────────────────

def test_no_publisher_announces_a_voided_pick():
    """CLAUDE.md §1c: a VOIDED row is a pick the model should never have
    produced, kept as evidence and stopped from counting. The six Week 1 wind
    picks were voided on 2026-09-07 and removed from Discord BY HAND, and
    nothing carried that to the app — so all six were still drawing as green
    BETs on the 09-13 board. Both halves of the fix are pinned: this one, and
    `passesActionFilter` in mobile/src/lib/thresholds.ts.

    Only 'VOID'. NCAAF writes 'OK' / 'GONE' here on real picks, and excluding
    those would empty its board.
    """
    for sql in (_sql(dn._new_signals, "2026-09-09"),
                _sql(dn._locked_signals, "2026-09-09"),
                _sql(pn._new_bet_signals, "2026-09-09")):
        assert ("p.condition_status IS NULL OR p.condition_status <> 'VOID'"
                in sql)
        # Compared against, not merely mentioned — the comment above the clause
        # names both of NCAAF's states on purpose.
        assert "condition_status <> 'GONE'" not in sql
        assert "condition_status = 'OK'" not in sql


def test_the_app_refuses_a_voided_pick_too():
    """The app is the other half. A server-side exclusion alone would just
    reverse which surface shows the extra rows."""
    src = (__file__.rsplit("tests", 1)[0]
           + "mobile/src/lib/thresholds.ts")
    with open(src, encoding="utf-8") as fh:      # §7: explicit encoding
        text = fh.read()
    body = text[text.index("export function passesActionFilter"):]
    body = body[:body.index("\n}")]
    assert re.search(r"condition_status\s*===\s*'VOID'", body), (
        "passesActionFilter must refuse a VOIDED row, or the app shows picks "
        "Discord does not")
