"""Discord is the board. VOID does not retract a post, and the app follows
the ledger.

Matt, 2026-09-23: if the channel still has the bet, the app shows it. If the
channel does not, it is not an active Discord-led bet.
`opening_lock_is_live` is the join a reader should use; capture and health
do not call it yet. Nothing here deletes a Discord message.
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
from tests._node import node_exe, node_strips_types  # noqa: E402

NODE = node_exe() or "node"
needs_node = pytest.mark.skipif(not node_strips_types(),
                                reason="node >= 22.6 not available")

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
        "CREATE TABLE push_sent (lock_key TEXT, kind TEXT, message_id TEXT, "
        "sent_at TEXT)")
    raw.execute(
        "CREATE TABLE opening_signals (lock_key TEXT, result TEXT)")
    raw.executemany(
        "INSERT INTO push_sent VALUES (?, ?, ?, ?)",
        [
            ("G:posted", "discord_signal", "1552", "2026-09-01T00:00:00-04:00"),
            ("G:phone", "new_bet", None, "2026-09-01T00:00:00-04:00"),
            ("live:G:m:over", "discord_live", "99", "2026-09-01T00:00:00-04:00"),
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
    # Keyword check: this file must not put the narrower view back once a
    # void notice owns the definition. The later migration is the one that
    # adds the exclusion and lets anon see discord_void (security_invoker).
    assert "position('discord_void' in d)" in sql
    later = (ROOT / "data/migrations/discord_void_notice_2026_10_09.sql").read_text(
        encoding="utf-8")
    assert "position('discord_void' in d)" in later
    assert "position('discord_void' in pol)" in later
    assert "v.kind = 'discord_void'" in later
    assert "kind IN ('discord_signal', 'discord_live', 'discord_void')" in later
    later_view = later.split("CREATE OR REPLACE VIEW", 1)[1].split("$v$", 1)[0]
    assert "message_id" not in later_view
    assert "DELETE FROM" not in later
    assert "UPDATE public.picks" not in later
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "discord_void_notice_2026_10_09.sql" in ACTIVE_MIGRATIONS
    assert (ACTIVE_MIGRATIONS.index("discord_void_notice_2026_10_09.sql")
            > ACTIVE_MIGRATIONS.index(MIG.name))


def test_void_picks_does_not_retract_discord():
    """A void does not edit or delete the original message. A posted pick
    gets a notice after the void commits; an unposted void posts nothing."""
    src = (ROOT / "scripts/void_picks.py").read_text(encoding="utf-8")
    assert "_delete_message" not in src
    assert "DELETE FROM" not in src
    assert "notify_discord_void" in src
    assert "dry_run=False" in src
    main = src.split("def main(", 1)[1]
    assert main.index("conn.commit()") < main.index("announce_posted_voids(")


@needs_node
def test_the_app_predicate_matches():
    """The board and this module are one decision. Drift here is the desync."""
    script = r"""
import { discordLedVisible, discordPublishForPick, isMissingNoticeView,
  lockKeyForPick, voidHiddenFromBoard, voidNoticeFromChunk }
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
const published = new Set(["G:m"]);
const noticed = new Set(["G:m"]);
if (discordPublishForPick("VOID", "G:m", published, noticed) !== "unpublished")
  throw new Error("noticed void stayed published");
if (discordPublishForPick(null, "G:m", published, noticed) !== "published")
  throw new Error("later pick on a noticed key was hidden");
if (discordPublishForPick("VOID", "G:m", published, new Set()) !== "published")
  throw new Error("a void with no notice was hidden");
if (discordPublishForPick("VOID", "H:m", published, noticed) !== "unpublished")
  throw new Error("an unposted key was published");
if (discordPublishForPick("VOID", "G:m", published, null) !== "unpublished")
  throw new Error("a failed notice read showed a void as published");
if (discordPublishForPick(null, "G:m", published, null) !== "published")
  throw new Error("a failed notice read hid a pick that is not void");

const missing = {
  code: "PGRST205",
  message: "Could not find the table 'public.v_discord_void_notice' in the schema cache",
};
if (!isMissingNoticeView(missing)) throw new Error("PGRST205 was not a missing view");
if (!isMissingNoticeView({ code: "42P01", message: 'relation "v_discord_void_notice" does not exist' }))
  throw new Error("42P01 was not a missing view");
if (!isMissingNoticeView({ message: "Could not find the table 'public.v_discord_void_notice' in the schema cache" }))
  throw new Error("the table message was not a missing view");
const missingKeys = voidNoticeFromChunk(missing, null);
if (missingKeys == null || missingKeys.size !== 0)
  throw new Error("a missing view did not come back empty");
if (discordPublishForPick("VOID", "G:m", published, missingKeys) !== "published")
  throw new Error("a missing notice view hid a published void");

const denied = voidNoticeFromChunk(
  { code: "42501", message: "permission denied for table push_sent" }, null);
if (denied !== null) throw new Error("a permission error looked like no notices");
if (discordPublishForPick("VOID", "G:m", published, denied) !== "unpublished")
  throw new Error("a permission error showed a void as published");
const offline = voidNoticeFromChunk({ code: "", message: "TypeError: Failed to fetch" }, null);
if (offline !== null) throw new Error("a network error looked like no notices");
if (discordPublishForPick("VOID", "G:m", published, offline) !== "unpublished")
  throw new Error("a network error showed a void as published");
const server = voidNoticeFromChunk({ code: "PGRST000", message: "Internal server error" }, null);
if (server !== null) throw new Error("a server error looked like no notices");
if (discordPublishForPick("VOID", "G:m", published, server) !== "unpublished")
  throw new Error("a server error showed a void as published");

const present = voidNoticeFromChunk(null, [{ lock_key: "G:m" }]);
if (present == null || !present.has("G:m")) throw new Error("a notice row was dropped");
if (discordPublishForPick("VOID", "G:m", published, present) !== "unpublished")
  throw new Error("a notice present stayed published");
"""
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    src = (ROOT / "mobile/src/lib/discordPublish.ts").read_text(encoding="utf-8")
    body = src[src.index("export async function fetchVoidNoticeKeys"):]
    body = body[:body.index("\nexport async function attachDiscordPublish")]
    assert "voidNoticeFromChunk(error" in body


@needs_node
def test_a_published_void_keeps_track_and_betslip():
    """2026-09-26: Ailin Perez ML (pick 2482412) was VOID + published. The
    board drew it, but Track and betslip gated on `result == null`, and a VOID
    carries result NO_ACTION, so the card had no actions. Both surfaces go
    through openForAction."""
    script = r"""
import { openForAction } from "./mobile/src/lib/discordPublish.ts";
const cases = [
  [null, null, undefined, true],
  [null, "OK", "unpublished", true],
  ["NO_ACTION", "VOID", "published", true],
  ["NO_ACTION", "VOID", "unpublished", false],
  ["NO_ACTION", "VOID", undefined, false],
  ["NO_ACTION", null, "published", false],
  ["WIN", "VOID", "published", false],
  ["LOSS", null, "published", false],
];
for (const [result, condition_status, discordPublish, want] of cases) {
  const got = openForAction({ result, condition_status, discordPublish });
  if (got !== want) throw new Error(JSON.stringify([result, condition_status, discordPublish, got]));
}
"""
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    card = (ROOT / "mobile/src/components/PickCard.tsx").read_text(encoding="utf-8")
    detail = (ROOT / "mobile/src/screens/PickDetailScreen.tsx").read_text(encoding="utf-8")
    for src in (card, detail):
        assert "openForAction(pick)" in src
        assert "canTrack = pick.result == null" not in src
        assert "Boolean(onToggleTrack) && pick.result == null" not in src
        assert "hasPricedLine(pick) && pick.result == null" not in src


@needs_node
def test_a_tracked_void_reads_not_graded_and_detail_closes_when_over():
    """A VOID keeps result NO_ACTION for good. Tracked, it must not read as
    "No action" (a scratched fight) before the event, and PickDetail must
    switch its actions off once the game ends, since the result never will."""
    script = r"""
import { trackedBetStatus } from "./mobile/src/lib/trackedPerformance.ts";
const void_ = trackedBetStatus({ result: "NO_ACTION", condition_status: "VOID" });
if (void_ !== "not_graded") throw new Error("void " + void_);
const dnp = trackedBetStatus({ result: "NO_ACTION", condition_status: null });
if (dnp !== "no_action") throw new Error("dnp " + dnp);
const win = trackedBetStatus({ result: "WIN", condition_status: null });
if (win !== "won") throw new Error("win " + win);
"""
    proc = subprocess.run(
        [NODE, "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    perf = (ROOT / "mobile/src/screens/PerformanceScreen.tsx").read_text(encoding="utf-8")
    assert "case 'not_graded':" in perf
    detail = (ROOT / "mobile/src/screens/PickDetailScreen.tsx").read_text(encoding="utf-8")
    assert "openForAction(pick) && (pick.result == null || !over)" in detail
    assert "hasPricedLine(pick) && openHere" in detail


def test_the_settled_record_still_excludes_every_void():
    """Display follows Discord. The record does not. A published VOID is
    still not a settled bet."""
    src = (ROOT / "mobile/src/lib/thresholds.ts").read_text(encoding="utf-8")
    body = src[src.index("export function passesRecordFilter"):]
    body = body[:body.index("\n}")]
    assert "condition_status === 'VOID'" in body
    assert "discordPublish" not in body
    assert "discordLedVisible" not in body


def test_the_discord_pins_are_on_the_pr_ci_subset():
    """A local-only green is how the NHL pin stayed red. These files are the
    Discord display, the publish key, the void contract, and the anon
    read-surface tripwire that names v_discord_void_notice."""
    yml = (ROOT / ".github/workflows/pr-ci.yml").read_text(encoding="utf-8")
    for name in (
        "tests/test_discord_publish_sync.py",
        "tests/test_publish_key_identity.py",
        "tests/test_void_picks.py",
        "tests/test_discord_void_notice.py",
        "tests/test_anon_readable.py",
    ):
        assert name in yml
    assert 'node-version: "22"' in yml


def test_opening_lock_join_is_not_wired_into_readers_yet():
    """The helper is the contract. Capture and health still treat a row as
    locked. A reader that imports it has to update this pin and the docs."""
    for rel in (
        "tracking/opening_signals.py",
        "tracking/system_health.py",
        "tracking/signal_publisher.py",
        "tracking/discord_notifier.py",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "opening_lock_is_live" not in src, rel
        assert "discord_published_exists_sql" not in src, rel
