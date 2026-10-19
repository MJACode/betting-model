"""Discord #results and the Record tab book the same stake.

Re-read 2026-10-17, SELECT only, results_snapshots all_time for game_date
2026-10-15: 439-378-2, units 21.5501, risked 918.2090. The 917.1090 measured
on 2026-10-16 is that total minus one later −110 loss. The view WHERE does
not filter result. The same posted set with no date cap also holds 106
NO_ACTION rows (122.0643) and 30 ungraded rows (31.5742). Counting those
stakes would make risked 1071.8475. The function and the view FILTER both
leave them out, so the graded total stays 918.2090.

The SQL body of published_pick_stake is the definition. The recap adds the
two columns it produces and does not recompute them. The Record tab sums
the same columns off the two views.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
from pathlib import Path

import pytest

from tracking.discord_notifier import (
    FLAT_CONVICTION,
    _SETTLED_SQL,
    _execute_settled,
    _tally,
    conviction_for,
    stake_for,
)
from tracking.published_units import (
    PROFIT_FN,
    RISKED_FN,
    STAKE_FN,
    install_sqlite,
    unit_profit,
    unit_risked,
)

ROOT = Path(__file__).resolve().parents[1]
FN_MIG = ROOT / "data" / "migrations" / "published_pick_units_2026_10_17.sql"
MIG = ROOT / "data" / "migrations" / "published_record_units_2026_10_16.sql"

_PRICES = [None, 0, -110, -115, -300, -301, -400, -100, 100, 150, 250]


def _migration() -> str:
    return FN_MIG.read_text(encoding="utf-8")


def _view_migration() -> str:
    return MIG.read_text(encoding="utf-8")


def _between(text: str, tag: str) -> str:
    start = text.index(f"${tag}$") + len(tag) + 2
    end = text.index(f"${tag}$", start)
    return text[start:end].strip()


def _stake_sql(price) -> tuple[float, float]:
    body = _between(_migration(), "stake")
    lit = "NULL" if price is None else repr(float(price))
    sql = re.sub(r"\bprice\b", lit, body)
    db = sqlite3.connect(":memory:")
    risk, win = db.execute(sql).fetchone()
    return float(risk), float(win)


def test_the_stake_function_is_stake_for():
    """1u to win, risk capped at 3. A missing or zero price is the bare 1u."""
    for price in _PRICES:
        expected = stake_for(None, price)
        risk, win = _stake_sql(price)
        assert risk == pytest.approx(expected.risk, abs=1e-9), price
        assert win == pytest.approx(expected.win, abs=1e-9), price
        for result in ("WIN", "LOSS", "PUSH", "NO_ACTION", None):
            assert unit_profit(price, result) == pytest.approx(
                expected.win if result == "WIN" else (
                    -expected.risk if result == "LOSS" else 0.0),
                abs=1e-9,
            )
            assert unit_risked(price, result) == pytest.approx(
                expected.risk if result in ("WIN", "LOSS") else 0.0, abs=1e-9)


def test_profit_and_risked_call_the_stake_function_and_nothing_else():
    text = _migration()
    profit = _between(text, "profit")
    risked = _between(text, "risked")
    assert f"(public.{STAKE_FN}(price)).win" in profit
    assert f"- (public.{STAKE_FN}(price)).risk" in profit
    assert "WHEN 'WIN'" in profit and "WHEN 'LOSS'" in profit
    assert f"(public.{STAKE_FN}(price)).risk" in risked
    assert "WHEN 'WIN'" in risked and "WHEN 'LOSS'" in risked
    assert "ELSE 0" in risked
    assert "result = 'PUSH'" not in risked
    # The price math lives in the stake body only.
    for body in (profit, risked):
        assert "100.0" not in body
        assert "3.0" not in body


def test_the_recap_adds_the_function_columns_and_does_not_recompute_them():
    assert f"{PROFIT_FN}(COALESCE(p.decision_odds, p.dk_odds), p.result)" in _SETTLED_SQL
    assert f"{RISKED_FN}(COALESCE(p.decision_odds, p.dk_odds), p.result)" in _SETTLED_SQL
    # A win at -110 is +1u on 1.1 risked via stake_for. The columns win.
    forced = _tally([("MLB", "m", "WIN", 0.02, -110, None, False, 5.5, 2.25)])
    assert forced["units"] == pytest.approx(5.5)
    assert forced["risked"] == pytest.approx(2.25)
    assert forced["w"] == 1
    # A short tuple still tallies, so the formatter tests keep a path.
    short = _tally([("MLB", "m", "LOSS", 0.02, -110, None)])
    assert short["units"] == pytest.approx(-stake_for(None, -110).risk)
    assert short["l"] == 1
    # A void and an ungraded row are not a stake, on the short path too.
    for result in ("NO_ACTION", None, "PUSH"):
        voided = _tally([("MLB", "m", result, 0.5, -110, None)])
        assert voided["units"] == 0
        assert voided["risked"] == 0


def test_conviction_is_flat_and_the_sql_ignores_it():
    """stake_for takes kelly and throws it away. The SQL never receives it."""
    for kelly in (None, 0, 0.002, 0.05, 1, ""):
        assert conviction_for(kelly) == FLAT_CONVICTION
    stake = _between(_migration(), "stake")
    assert "kelly" not in stake.lower()
    assert "conviction" not in stake.lower()
    assert "published_pick_stake(price numeric" in _migration()


def test_both_record_views_sum_the_same_functions():
    text = _view_migration()
    fns = _migration()
    for view in ("v_public_track_record", "v_public_track_record_daily"):
        assert view in text
    # One cols block, applied to both views by the loop. The name also
    # appears in the comment that points at the function file.
    assert text.count(f"sum({PROFIT_FN}") == 1
    assert text.count(f"sum({RISKED_FN}") == 1
    assert f"FUNCTION public.{PROFIT_FN}" in fns
    assert f"FUNCTION public.{RISKED_FN}" in fns
    assert "COALESCE(sum(published_pick_unit_profit" in text
    assert "COALESCE(sum(published_pick_unit_risked" in text
    assert text.count("FILTER (WHERE result IN ('WIN', 'LOSS', 'PUSH'))") == 2
    assert "AS units" in text and "AS risked" in text
    assert "CREATE FUNCTION" not in text
    assert "CREATE OR REPLACE FUNCTION" not in text
    # Flat columns stay. This pass does not restamp a published snapshot.
    assert "profit_flat" not in text.split("DO $mig$")[1]
    assert "INSERT INTO" not in text
    assert "results_snapshots" not in text.split("DO $mig$")[1]
    assert "push_sent" not in text.split("DO $mig$")[1]
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name == ACTIVE_MIGRATIONS[-1]
    assert ACTIVE_MIGRATIONS.index(FN_MIG.name) == ACTIVE_MIGRATIONS.index(MIG.name) - 1
    assert ACTIVE_MIGRATIONS.index("clv_standard_v2_2026_10_14.sql") < ACTIVE_MIGRATIONS.index(FN_MIG.name)
    assert text.count("DO $mig$") == 1
    assert fns.count("DO $mig$") == 1
    assert "CREATE VIEW" not in fns
    assert "CREATE OR REPLACE VIEW" not in fns
    assert text.strip().endswith(";")
    assert fns.strip().endswith(";")
    assert "GRANT EXECUTE" in fns
    assert "GRANT EXECUTE" not in text
    assert "security_invoker" in text
    # A view failure commits separately. The runner commits inside one file.
    from data.view_migrations import _apply_one
    import inspect
    assert "conn.commit()" in inspect.getsource(_apply_one)


def test_the_record_tab_sums_those_columns_and_not_the_flat_book():
    screen = (ROOT / "mobile/src/screens/TrackRecordScreen.tsx").read_text(encoding="utf-8")
    card = (ROOT / "mobile/src/components/RecordHeroCard.tsx").read_text(encoding="utf-8")
    hero = (ROOT / "mobile/src/lib/recordHero.ts").read_text(encoding="utf-8")
    queries = (ROOT / "mobile/src/lib/queries.ts").read_text(encoding="utf-8")
    summary = (ROOT / "mobile/src/lib/trackRecord.ts").read_text(encoding="utf-8")
    curve = (ROOT / "mobile/src/components/EquityCurve.tsx").read_text(encoding="utf-8")
    spark = (ROOT / "mobile/src/components/RecordSparkline.tsx").read_text(encoding="utf-8")
    share = (ROOT / "mobile/src/lib/shareRecord.ts").read_text(encoding="utf-8")
    assert "units, risked" in queries
    assert queries.count("units, risked") >= 2
    assert "postedStakeColumnsMissing" in queries
    assert "TRACK_RECORD_SELECT_WITHOUT_UNITS" in queries
    assert "TRACK_RECORD_DAILY_SELECT_WITHOUT_UNITS" in queries
    assert "42703" in queries and "PGRST204" in queries
    assert "It is marked unpriced, staked at 1u" not in screen
    assert "Number(r.units ?? 0)" in summary
    assert "Number(r.risked ?? 0)" in summary
    assert "risked > 0 ? units / risked" in summary
    equity = screen.split("const equity", 1)[1].split("}, [visibleDaily]);", 1)[0]
    assert "d.units != null" in equity
    assert "return []" in equity
    assert "profit_flat" not in equity
    assert "/ 100" not in equity
    on_share = screen.split("const onShare", 1)[1].split("}, [overall, equity]);", 1)[0]
    assert "(overall.risked ?? 0) > 0" in on_share
    assert "notLoaded || curveUnknown" in screen
    assert "overall.units == null || dailyLacksUnits" in screen
    assert "visibleDaily.some((d) => d.units != null)" in screen
    # Option B: Discord's all-time label, the units number, the same pill.
    assert "DISCORD_ALL_TIME_LABEL" in screen
    assert "endUnits={heroUnits}" in screen
    assert 'export const DISCORD_ALL_TIME_LABEL = \'All-time\'' in hero
    assert "return formatSigned(units, 2, 'u')" in hero
    assert "Units unavailable" in hero
    assert "unknownCountSpeech('— settled picks')" in hero
    assert "since ${LIVE_RECORD_START_SHORT}" in hero
    # Yesterday now uses this same posted stake. This screen says
    # "Return on bets", and it does not say "flat-bet ROI".
    for blob in (screen, card, hero):
        assert "Flat-bet ROI" not in blob
        assert "flat-bet ROI" not in blob
    assert 'label="Return on bets"' in card
    assert "Return on bets (ROI)" in hero
    assert "Total profit · all time" in hero
    assert "heroVisibleLabel(label)" in card
    assert "Units · 1 to win" in hero
    assert "{UNITS_CAPTION}" in card
    assert "Each pick risks the amount needed to win 1 unit" in hero
    assert "Risk is capped at 3 units" in hero
    assert "a pick with no price counts as 1 unit" in hero
    assert "Nothing risks more than 3" not in hero
    assert "wins less than 1" not in hero
    assert "The info button on Return on bets" in screen
    assert "not all green" not in screen
    assert "Beat the closing line" in card
    assert 'accessibilityRole="summary"' in card
    assert "accessibilityLabel={heroLabel}" in card
    assert "heroAccessibilityLabel" in hero
    assert "pnlColor(units, 2)" in card
    assert "pnlColor(summary.roi, 1, 100)" in card
    assert "summary.units != null" in card
    assert "overall.units == null" in screen
    assert "Models use a flat $100 bet" in hero
    assert "Yesterday and Models use a flat $100 bet" not in hero
    assert "unpriced, staked at 1u" in screen
    assert "flat $100" not in curve
    assert "colors.positive" not in curve
    assert "colors.betInk" in curve
    assert "Cumulative units, 1 to win" in curve
    assert "formatSigned(endUnits, 2, 'u')" in curve
    assert "pnlColor(endUnits, 2)" in curve
    assert "scrubIndexForSeries" in curve
    assert "equitySeriesKey(seriesId, points)" in curve
    assert "onBlur does not" in curve
    assert "onBlur={releaseScrub}" not in curve
    assert "scheduleScrubRelease" in curve
    assert "seriesId={sportSel}" in screen
    assert curve.count("<Circle") >= 2
    assert "maxWidth: pill.maxWidth" in curve
    geometry = (ROOT / "mobile/src/lib/equityGeometry.ts").read_text(encoding="utf-8")
    assert "export function scrubIndexForSeries" in geometry
    assert "SCRUB_RELEASE_MS" in geometry
    assert "scheduleScrubRelease" in geometry
    assert "maxWidth: chartW" in geometry
    assert "strokeDasharray" in curve
    assert "unitAxisTicks" in curve
    assert "colors.betInk" in spark
    assert "colors.positive" not in spark
    assert "units, 1 to win" in share
    assert "formatPctSigned(s.roi)" in share
    assert "(s.risked ?? 0) > 0" in share
    assert "s.roiFlat" not in share
    assert "flat-bet ROI" not in share
    assert "flat $100" not in share
    assert "roi:" in summary
    assert "localeCompare(String(b.model_id))" in summary
    assert "roiFlat:" not in summary.split("export interface ParlaySummary")[0]


def test_the_view_sum_drops_voids_and_ungraded_rows():
    """The cols block, executed. An all-void model risks 0, so the screen dashes."""
    if sqlite3.sqlite_version_info < (3, 30):
        pytest.skip("sum() FILTER needs SQLite >= 3.30")
    cols = _between(_view_migration(), "cols").strip().lstrip(",").strip()
    db = sqlite3.connect(":memory:")
    install_sqlite(db)
    db.execute(
        "CREATE TABLE picks (model_id TEXT, result TEXT, decision_odds REAL, dk_odds REAL)"
    )
    db.execute(
        f"CREATE VIEW v_public_track_record AS SELECT model_id, {cols} "
        "FROM picks p GROUP BY model_id"
    )
    db.executemany(
        "INSERT INTO picks VALUES (?,?,?,?)",
        [
            ("m", "WIN", -110, None),
            ("m", "LOSS", -110, None),
            ("m", "PUSH", -110, None),
            ("m", "NO_ACTION", -110, None),
            ("m", None, -110, None),
            ("void_only", "NO_ACTION", -300, None),
            ("void_only", None, 150, None),
        ],
    )
    got = {
        row[0]: row
        for row in db.execute("SELECT model_id, units, risked FROM v_public_track_record")
    }
    stake = stake_for(None, -110)
    assert got["m"][1] == pytest.approx(stake.win - stake.risk)
    assert got["m"][2] == pytest.approx(stake.risk * 2)
    assert got["void_only"][1] == pytest.approx(0)
    assert got["void_only"][2] == pytest.approx(0)


def test_a_missing_function_tallies_with_stake_for():
    """Settle runs before the migration on the deploy morning."""
    if sqlite3.sqlite_version_info < (3, 39):
        pytest.skip("IS DISTINCT FROM needs SQLite >= 3.39")
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE picks (
        sport, model_id, result, kelly_fraction, dk_odds, decision_odds,
        clv_pct, is_live, game_date, signal_type, downgrade_reason,
        condition_status, game_id, pick_side, player_id, player_key, prop_market,
        clv_method)""")
    db.execute("CREATE TABLE push_sent (lock_key TEXT, kind TEXT, sent_at TEXT)")
    db.execute(
        "INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("MLB", "m", "WIN", 0.02, -110, None, None, 0, "2026-10-01", "BET",
         None, None, "g1", None, None, None, None, None),
    )
    db.execute(
        "INSERT INTO picks VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("MLB", "voided", "NO_ACTION", 0.02, -110, None, None, 0, "2026-10-01",
         "BET", None, "VOID", "g2", None, None, None, None, None),
    )
    db.execute("INSERT INTO push_sent VALUES ('g1:m', 'discord_signal', '2026-10-01')")
    db.execute("INSERT INTO push_sent VALUES ('g2:voided', 'discord_signal', '2026-10-01')")
    sql = _SETTLED_SQL.format(window="= ?").replace("%%", "%")
    rows = _execute_settled(db, sql, ("2026-10-01",)).fetchall()
    assert all(len(row) < 9 for row in rows)
    tallied = _tally(rows)
    assert tallied["w"] == 1
    assert tallied["units"] == pytest.approx(stake_for(None, -110).win)
    assert tallied["risked"] == pytest.approx(stake_for(None, -110).risk)


def test_the_fallback_rollback_is_only_safe_because_callers_read_first():
    """An uncommitted insert on the same connection would not survive it."""
    src = (ROOT / "tracking/discord_notifier.py").read_text(encoding="utf-8")
    fn = src.split("def _execute_settled", 1)[1].split("\ndef ", 1)[0]
    assert "writes afterwards" in fn
    body = src.split("def notify_discord_results", 1)[1].split("\ndef ", 1)[0]
    assert body.index("_settled_rows(") < body.index("INSERT INTO push_sent")
    assert body.index("_settled_rows_since(") < body.index("INSERT INTO push_sent")
    for name in ("recaps_needing_restatement", "post_missed_recap", "_restate_x_if_behind"):
        other = src.split(f"def {name}", 1)[1].split("\ndef ", 1)[0]
        assert "INSERT" not in other


def test_the_share_text_drops_a_zero_from_before_the_migration():
    """verify_share_record.ts is the check. The hero calls the same function."""
    from tests._node import NODE, node_strips_types
    if not node_strips_types():
        pytest.skip("node >= 22.6 not available")
    assert NODE is not None
    mobile = ROOT / "mobile"
    script = (mobile / "scripts" / "verify_share_record.ts").read_text(encoding="utf-8")
    script = re.sub(r"from '(?:\.\./)+src/lib/(\w+)';", r"from './\1.ts';", script)
    script = re.sub(r"^import type .*;\n", "", script, flags=re.M)
    share = (mobile / "src" / "lib" / "shareRecord.ts").read_text(encoding="utf-8")
    share = re.sub(r"from '@/lib/(\w+)';", r"from './\1.ts';", share)
    share = re.sub(r"^import type .*;\n", "", share, flags=re.M)
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        (folder / "verify_share_record.ts").write_text(script, encoding="utf-8")
        (folder / "shareRecord.ts").write_text(share, encoding="utf-8")
        (folder / "format.ts").write_text(
            (mobile / "src" / "lib" / "format.ts").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (folder / "package.json").write_text('{"type": "module"}\n', encoding="utf-8")
        proc = subprocess.run(
            [NODE, "--experimental-strip-types", "verify_share_record.ts"],
            cwd=folder,
            capture_output=True,
            text=True,
            timeout=60,
        )
    assert proc.returncode == 0, proc.stdout + "\n" + proc.stderr
    assert "[PASS] missing stake drops the ROI line" in proc.stdout
    assert "[PASS] missing stake drops the units line" in proc.stdout
    assert "[PASS] missing stake keeps the record" in proc.stdout
    assert "[PASS] missing stake keeps the win rate" in proc.stdout
    assert "[PASS] all-void drops the ROI line" in proc.stdout
    assert "[PASS] all-void keeps the record" in proc.stdout
    assert "[PASS] all-void keeps the win rate" in proc.stdout
