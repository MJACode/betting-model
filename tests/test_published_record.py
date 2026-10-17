"""The published record is the picks Discord still has.

Daily, the 7-day restatement, and all-time share _SETTLED_SQL. X and the
snapshot builder read that query. The two app views get the same lock in
published_picks_record_2026_10_14.sql. Units are stake_for at the taken
price. nfl_live_prop stays struck. An unposted settled BET stays in picks
and out of the record.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import config
from tracking.discord_notifier import _SETTLED_SQL, stake_for
from tracking.publish_keys import live_lock_key_sql, lock_key_sql, posted_sql

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "published_picks_record_2026_10_14.sql"


def _code(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def test_the_recap_counts_a_pick_only_when_discord_still_has_it():
    assert posted_sql("p") in _SETTLED_SQL
    assert "v_discord_published" not in _code(_SETTLED_SQL).replace(posted_sql("p"), "")


def test_the_recap_query_drops_an_unposted_bet_and_a_voided_lock():
    if sqlite3.sqlite_version_info < (3, 39):
        pytest.skip("IS DISTINCT FROM needs SQLite >= 3.39")
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE picks (
        sport, model_id, result, kelly_fraction, dk_odds, decision_odds,
        clv_pct, is_live, game_date, signal_type, downgrade_reason,
        condition_status, game_id, pick_side, player_id, player_key, prop_market,
        clv_method)""")
    db.execute("CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT)")
    rows = [
        ("MLB", "m_posted", "WIN", 0.02, -110, None, None, 0, "2026-10-01", "BET", None, None, "g1", None, None, None, None),
        ("MLB", "m_silent", "WIN", 0.02, -110, None, None, 0, "2026-10-01", "BET", None, None, "g2", None, None, None, None),
        ("MLB", "m_voided", "WIN", 0.02, -110, None, None, 0, "2026-10-01", "BET", None, None, "g3", None, None, None, None),
        ("NFL", "nfl_live_prop", "WIN", 0.02, -110, None, None, 1, "2026-10-01", "BET", None, None, "g4", "over", "p", "p", "player_pass_attempts"),
        ("MLB", "m_void_result", "NO_ACTION", 0.02, -110, None, None, 0, "2026-10-01", "BET", None, "VOID", "g5", None, None, None, None),
    ]
    db.executemany(
        "INSERT INTO picks (sport, model_id, result, kelly_fraction, dk_odds, "
        "decision_odds, clv_pct, is_live, game_date, signal_type, downgrade_reason, "
        "condition_status, game_id, pick_side, player_id, player_key, prop_market) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    db.executemany(
        "INSERT INTO push_sent VALUES (?, ?, ?)",
        [
            ("g1:m_posted", "discord_signal", "2026-10-01T12:00:00"),
            ("g3:m_voided", "discord_signal", "2026-10-01T12:00:00"),
            ("g3:m_voided", "discord_void", "2026-10-01T13:00:00"),
            ("live:g4:nfl_live_prop:over:p:p:player_pass_attempts", "discord_live", "2026-10-01T12:00:00"),
            ("g5:m_void_result", "discord_signal", "2026-10-01T12:00:00"),
        ])
    sql = _SETTLED_SQL.format(window="= ?").replace("%%", "%")
    got = sorted(r[1] for r in db.execute(sql, ("2026-10-01",)).fetchall())
    assert got == ["m_posted"]


def test_the_publish_lock_uses_the_same_key_as_the_ledger():
    text = _code(MIG.read_text(encoding="utf-8"))
    pregame = "p.game_id || ':' || p.model_id"
    live = "'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side"
    # Once in the snapshot rewrite, once in the view patch.
    assert text.count(pregame) >= 2
    assert text.count(live) >= 2
    for col in ("p.player_id", "p.player_key", "p.prop_market"):
        assert text.count(col) >= 4, col
    assert "v_discord_published" in text
    assert lock_key_sql("p")
    assert "player_id" in live_lock_key_sql("p")


def _marked(name: str) -> str:
    text = MIG.read_text(encoding="utf-8")
    start = text.index(f"-- {name}\n") + len(f"-- {name}\n")
    end = text.index(f"-- END_{name}", start)
    line = text[start:end].strip()
    assert line.startswith("-- ")
    return line[3:].strip()


def test_the_snapshot_stake_is_stake_for_not_a_flat_unit():
    """1u to win, risk capped at 3. A missing price is the bare conviction."""
    risk_sql = _marked("STAKE_EXPR_RISK")
    win_sql = _marked("STAKE_EXPR_WIN")
    db = sqlite3.connect(":memory:")
    # The migration runs on Postgres, which has LEAST. SQLite does not.
    db.create_function("LEAST", 2, min)
    prices = [None, 0, -110, -115, -300, -400, -100, 100, 150, 250]
    for price in prices:
        expected = stake_for(None, price)
        got_risk, got_win = db.execute(
            f"SELECT {risk_sql}, {win_sql} FROM (SELECT ? AS price)",
            (price,),
        ).fetchone()
        assert got_risk == pytest.approx(expected.risk, abs=1e-9)
        assert got_win == pytest.approx(expected.win, abs=1e-9)
    # The executable rewrite uses that pair, at the taken price.
    body = _code(MIG.read_text(encoding="utf-8"))
    assert "COALESCE(p.decision_odds, p.dk_odds)" in body
    assert "LEAST(" in body and "3.0" in body
    assert "nfl_live_prop" in body
    assert "'2026-09-01'" in body
    assert config.PAPER_TRADING_START == "2026-09-01"


def test_the_migration_is_one_statement_and_runs_after_the_view_owners():
    from data.view_migrations import ACTIVE_MIGRATIONS, MIGRATIONS_DIR
    assert MIG.name in ACTIVE_MIGRATIONS
    # clv patches v_public_track_record. It no longer has to be the final
    # file, but nothing after it may recreate that view.
    clv = "clv_standard_v2_2026_10_14.sql"
    assert clv in ACTIVE_MIGRATIONS
    clv_i = ACTIVE_MIGRATIONS.index(clv)
    assert ACTIVE_MIGRATIONS.index(MIG.name) < clv_i
    for later in ACTIVE_MIGRATIONS[clv_i + 1:]:
        body = (MIGRATIONS_DIR / later).read_text(encoding="utf-8")
        assert "v_public_track_record" not in body, later
    i = ACTIVE_MIGRATIONS.index(MIG.name)
    for owner in (
        "record_strikes_nfl_live_prop_2026_10_04.sql",
        "record_views_count_each_event_once_2026_10_09.sql",
        "recompute_snapshot_units_2026_10_14.sql",
    ):
        assert ACTIVE_MIGRATIONS.index(owner) < i, owner
    text = MIG.read_text(encoding="utf-8")
    assert text.count("DO $mig$") == 1
    assert text.strip().endswith(";")
    assert "results_snapshot_published_backfill" in text
    assert "before_units" in text and "after_units" in text
    assert "before_wins" in text and "after_wins" in text
    for view in ("v_public_track_record", "v_public_track_record_daily"):
        assert view in text
    assert "ENABLE ROW LEVEL SECURITY" in text
    # The receipt's original stamp stays. This pass does not post.
    assert "published_at" not in _code(text).split("CREATE TABLE")[1].split("CREATE TEMP")[0]
    assert "INSERT INTO push_sent" not in text
    assert "discord_results" not in text


def test_the_daily_recap_leaves_an_unpublished_graded_bet_out():
    src = (ROOT / "mobile" / "src" / "lib" / "dailyResults.ts").read_text(encoding="utf-8")
    assert "p.discordPublish === 'unpublished'" in src
    hook = (ROOT / "mobile" / "src" / "hooks" / "useDailyResults.ts").read_text(encoding="utf-8")
    assert "attachDiscordPublish" in hook


def test_the_app_record_leaves_an_unpublished_graded_bet_out():
    """The published view already locks on v_discord_published. These are the
    client tallies that were still counting the unfiltered settled set."""
    thresholds = (ROOT / "mobile/src/lib/thresholds.ts").read_text(encoding="utf-8")
    record = thresholds.split("export function passesRecordFilter(")[1].split("\n}")[0]
    assert "publishedRecordKeeps" not in record
    assert "export function publishedRecordKeeps(" in thresholds
    backtest = (ROOT / "mobile/src/lib/customModelBacktest.ts").read_text(encoding="utf-8")
    custom = backtest.split("export function computeCustomModelStats(")[1].split("export function")[0]
    built = backtest.split("export function computeBuiltInModelStats(")[1]
    assert "publishedRecordKeeps(p)" in built
    assert "publishedRecordKeeps" not in custom
    screen = (ROOT / "mobile/src/screens/BuiltInModelDetailScreen.tsx").read_text(encoding="utf-8")
    assert "publishedRecordKeeps(p)" in screen
    assert "p.discordPublish === 'published'" in screen
    assert "viewPresent && ledgerUnread" in screen
    assert "The Discord check did not finish, so this list can be wider than the tiles." in screen
    assert "both keep picks whose posting status is unknown" in screen
    assert "useModelPickHistory" not in screen
    assert "v_model_full_outcome_picks" not in screen
    for rel in ("mobile/src/lib/teamDetail.ts", "mobile/src/lib/playerDetail.ts"):
        assert "publishedRecordKeeps(p)" in (ROOT / rel).read_text(encoding="utf-8")
    hook = (ROOT / "mobile/src/hooks/useCustomModelStats.ts").read_text(encoding="utf-8")
    load = hook.split("export function useSettledPicksSincePaperStart(")[1].split("export function viewRecordToStats")[0]
    assert load.index("writeSettledCache(merged)") < load.index("attachDiscordPublish(merged)")
    queries = (ROOT / "mobile/src/lib/queries.ts").read_text(encoding="utf-8")
    cols = queries.split("const SETTLED_PICK_COLUMNS =")[1].split(";")[0]
    assert "player_key" in cols and "prop_market" in cols
    assert queries.count("return attachDiscordPublish(") == 2
    cache = (ROOT / "mobile/src/lib/settledPickCache.ts").read_text(encoding="utf-8")
    assert "const KEY = 'settledPicks.v9';" in cache
