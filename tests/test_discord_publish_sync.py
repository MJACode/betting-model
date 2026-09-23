"""Discord is the board. VOID does not retract a post, and the app follows
the ledger.

Matt, 2026-09-23: if the channel still has the bet, the app shows it. If the
channel does not, it is not an active Discord-led bet. opening_signals is a
live lock only when that same ledger has the key. Nothing here deletes a
Discord message.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from tracking.discord_publish import (  # noqa: E402
    discord_led_visible,
    discord_published_exists_sql,
    lock_key_for_pick,
    opening_lock_is_live,
    void_hidden_from_board,
)
from tracking.publish_keys import live_lock_key_sql, lock_key_sql  # noqa: E402

MIG = ROOT / "data/migrations/discord_publish_state_2026_09_23.sql"


def _sql_key(row: dict, *, live: bool) -> str:
    raw = sqlite3.connect(":memory:")
    raw.execute(
        "CREATE TABLE p (game_id TEXT, model_id TEXT, player_id TEXT, "
        "player_key TEXT, prop_market TEXT, pick_side TEXT)")
    raw.execute(
        "INSERT INTO p VALUES (?, ?, ?, ?, ?, ?)",
        (row["game_id"], row["model_id"], row.get("player_id"),
         row.get("player_key"), row.get("prop_market"), row.get("pick_side")))
    expr = live_lock_key_sql("p") if live else lock_key_sql("p")
    return raw.execute(f"SELECT {expr} FROM p").fetchone()[0]


@pytest.mark.parametrize("live", [False, True])
def test_the_lock_key_matches_the_sql_the_ledger_was_written_with(live):
    """A key the app computes and a key the notifier ledgered are one key,
    or the join hides a post that is standing."""
    row = {
        "game_id": "NFL_2026_03_TEN_NYG",
        "model_id": "nfl_prop_market" if not live else "nfl_live_prop",
        "pick_side": "over",
        "player_id": None,
        "player_key": "samdarnold",
        "prop_market": "player_pass_yds",
    }
    assert lock_key_for_pick(row, live=live) == _sql_key(row, live=live)


def test_a_game_level_key_has_no_tail():
    row = {"game_id": "UFC_2482412", "model_id": "ufc_moneyline",
           "pick_side": "home", "player_id": None, "player_key": None,
           "prop_market": None}
    assert lock_key_for_pick(row) == "UFC_2482412:ufc_moneyline"
    assert lock_key_for_pick(row) == _sql_key(row, live=False)


@pytest.mark.parametrize(
    "status, published, want",
    [
        (None, True, True),
        ("VOID", True, True),       # channel still has it
        ("VOID", False, False),     # channel never got it
        ("VOID", None, False),      # ledger unread: do not invent a bet
        (None, False, False),       # not an active Discord-led bet
        ("OK", False, False),
        ("GONE", False, False),
        (None, None, True),         # unread ledger must not blank the board
        ("GONE", None, True),
        ("DEGRADED", None, True),
    ],
)
def test_discord_led_visibility(status, published, want):
    assert discord_led_visible(status, published) is want


def test_today_keeps_a_published_void_and_drops_the_rest():
    assert void_hidden_from_board("VOID", True) is False
    assert void_hidden_from_board("VOID", False) is True
    assert void_hidden_from_board("VOID", None) is True
    assert void_hidden_from_board(None, False) is False
    assert void_hidden_from_board("OK", False) is False


def test_an_opening_signal_is_live_only_when_discord_published_it():
    """The capture row staying put is not locked=true. The join is."""
    assert opening_lock_is_live(True, True) is True
    assert opening_lock_is_live(True, False) is False
    assert opening_lock_is_live(False, True) is False


def test_the_join_is_the_discord_ledger_and_not_a_new_bet_row():
    raw = sqlite3.connect(":memory:")
    raw.execute(
        "CREATE TABLE push_sent (lock_key TEXT, kind TEXT, message_id TEXT)")
    raw.execute(
        "CREATE TABLE opening_signals (lock_key TEXT, result TEXT)")
    raw.executemany(
        "INSERT INTO push_sent VALUES (?, ?, ?)",
        [
            ("G:posted", "discord_signal", "1552"),
            ("G:phone", "new_bet", None),
            ("live:G:m:over", "discord_live", "99"),
        ],
    )
    raw.executemany(
        "INSERT INTO opening_signals VALUES (?, ?)",
        [("G:posted", None), ("G:phone", None), ("G:never", None)],
    )
    pred = discord_published_exists_sql("os.lock_key")
    rows = raw.execute(
        f"SELECT os.lock_key FROM opening_signals os WHERE {pred} "
        "ORDER BY os.lock_key"
    ).fetchall()
    assert [r[0] for r in rows] == ["G:posted"]
    assert "discord_signal" in pred and "discord_live" in pred
    assert "new_bet" not in pred


def test_the_view_exposes_the_ledger_without_the_message_id():
    sql = MIG.read_text(encoding="utf-8")
    assert "v_discord_published" in sql
    assert "security_invoker = on" in sql
    assert "s.lock_key, s.kind" in sql
    assert "discord_signal" in sql and "discord_live" in sql
    # The view body does not project the snowflake.
    view = sql.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    assert "message_id" not in view
    assert "DELETE FROM" not in sql
    assert "_delete_message" not in sql


def test_void_picks_does_not_retract_discord():
    src = (ROOT / "scripts/void_picks.py").read_text(encoding="utf-8")
    assert "_delete_message" not in src
    assert "discord" not in src.lower()


def test_the_app_predicate_matches():
    """The board and this module are one decision. Drift here is the desync."""
    script = r"""
import { discordLedVisible, lockKeyForPick, voidHiddenFromBoard }
  from "./mobile/src/lib/discordPublish.ts";

const cases = [
  [null, true, true],
  ["VOID", true, true],
  ["VOID", false, false],
  ["VOID", null, false],
  [null, false, false],
  ["OK", false, false],
  ["GONE", false, false],
  [null, null, true],
  ["GONE", null, true],
  ["DEGRADED", null, true],
];
for (const [status, published, want] of cases) {
  const publish = published === true ? "published"
    : published === false ? "unpublished" : undefined;
  const got = discordLedVisible(status, publish);
  if (got !== want) throw new Error(status + " " + published + " -> " + got);
}
const key = lockKeyForPick({
  game_id: "G", model_id: "nfl_prop_market",
  player_id: null, player_key: "sam", prop_market: "player_pass_yds",
});
if (key !== "G:nfl_prop_market:sam:player_pass_yds") throw new Error(key);
const live = lockKeyForPick({
  game_id: "G", model_id: "nfl_live_prop", pick_side: "over", is_live: true,
  player_key: "cj", prop_market: "player_pass_attempts",
});
if (live !== "live:G:nfl_live_prop:over:cj:player_pass_attempts") throw new Error(live);
const plain = lockKeyForPick({ game_id: "UFC_2482412", model_id: "ufc_moneyline" });
if (plain !== "UFC_2482412:ufc_moneyline") throw new Error(plain);
if (voidHiddenFromBoard({ condition_status: "VOID", discordPublish: "published" }))
  throw new Error("published void hidden");
if (!voidHiddenFromBoard({ condition_status: "VOID", discordPublish: "unpublished" }))
  throw new Error("unpublished void shown");
if (!voidHiddenFromBoard({ condition_status: "VOID" }))
  throw new Error("unknown void shown");
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr


def test_the_settled_record_still_excludes_every_void():
    """Display follows Discord. The record does not. A published VOID is
    still not a settled bet."""
    src = (ROOT / "mobile/src/lib/thresholds.ts").read_text(encoding="utf-8")
    body = src[src.index("export function passesRecordFilter"):]
    body = body[:body.index("\n}")]
    assert "condition_status === 'VOID'" in body
    assert "discordPublish" not in body
    assert "discordLedVisible" not in body
