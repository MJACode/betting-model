"""Discord #results and the Record tab book the same stake.

Measured 2026-10-16, posted record through 2026-10-15, 439-377-2 over 818
settled picks: stake_for is +22.6501u and +2.4697% ROI; flat $100 is
+$2,785.85 and +3.4057% ROI (equity +27.8585u). Same picks. The stake on
the card is stake_for, so that is the number both surfaces use.

The SQL body of published_pick_stake is the definition. The recap adds the
two columns it produces and does not recompute them. The Record tab sums
the same columns off the two views.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from tracking.discord_notifier import _SETTLED_SQL, _tally, stake_for
from tracking.published_units import (
    PROFIT_FN,
    RISKED_FN,
    STAKE_FN,
    unit_profit,
    unit_risked,
)

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "published_record_units_2026_10_16.sql"

_PRICES = [None, 0, -110, -115, -300, -301, -400, -100, 100, 150, 250]


def _migration() -> str:
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
        for result in ("WIN", "LOSS", "PUSH"):
            assert unit_profit(price, result) == pytest.approx(
                expected.win if result == "WIN" else (
                    -expected.risk if result == "LOSS" else 0.0),
                abs=1e-9,
            )
            assert unit_risked(price, result) == pytest.approx(
                0.0 if result == "PUSH" else expected.risk, abs=1e-9)


def test_profit_and_risked_call_the_stake_function_and_nothing_else():
    text = _migration()
    profit = _between(text, "profit")
    risked = _between(text, "risked")
    assert f"(public.{STAKE_FN}(price)).win" in profit
    assert f"- (public.{STAKE_FN}(price)).risk" in profit
    assert "WHEN 'WIN'" in profit and "WHEN 'LOSS'" in profit
    assert f"(public.{STAKE_FN}(price)).risk" in risked
    assert "result = 'PUSH'" in risked
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


def test_both_record_views_sum_the_same_functions():
    text = _migration()
    for view in ("v_public_track_record", "v_public_track_record_daily"):
        assert view in text
    assert text.count(PROFIT_FN) >= 2
    assert text.count(RISKED_FN) >= 2
    assert "COALESCE(sum(published_pick_unit_profit" in text
    assert "COALESCE(sum(published_pick_unit_risked" in text
    assert "AS units" in text and "AS risked" in text
    # Flat columns stay. This pass does not restamp a published snapshot.
    assert "profit_flat" not in text.split("DO $mig$")[1]
    assert "INSERT INTO" not in text
    assert "results_snapshots" not in text.split("DO $mig$")[1]
    assert "push_sent" not in text.split("DO $mig$")[1]
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name == ACTIVE_MIGRATIONS[-1]
    assert ACTIVE_MIGRATIONS.index("clv_standard_v2_2026_10_14.sql") < ACTIVE_MIGRATIONS.index(MIG.name)
    assert text.count("DO $mig$") == 1
    assert text.strip().endswith(";")
    assert "GRANT EXECUTE" in text
    assert "security_invoker" in text


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
    assert "Number(r.units ?? 0)" in summary
    assert "Number(r.risked ?? 0)" in summary
    assert "risked > 0 ? units / risked" in summary
    equity = screen.split("const equity", 1)[1].split("}, [visibleDaily]);", 1)[0]
    assert "d.units" in equity
    assert "profit_flat" not in equity
    assert "/ 100" not in equity
    # Option B: Discord's all-time label, the units number, the same pill.
    assert "DISCORD_ALL_TIME_LABEL" in screen
    assert "endUnits={heroUnits}" in screen
    assert 'export const DISCORD_ALL_TIME_LABEL = \'All-time\'' in hero
    assert "return formatSigned(units, 2, 'u')" in hero
    assert "Units unavailable" in hero
    assert "unknownCountSpeech('— settled picks')" in hero
    assert "since ${LIVE_RECORD_START_SHORT}" in hero
    assert "Flat-bet ROI" in card
    assert "Beat the closing line" in card
    assert 'accessibilityRole="summary"' in card
    assert "accessibilityLabel={heroLabel}" in card
    assert "heroAccessibilityLabel" in hero
    assert "pnlColor(units, 2)" in card
    assert "pnlColor(summary.roiFlat, 1, 100)" in card
    assert "Yesterday and the Models tab still use a flat $100 bet" in screen
    assert "wins less than 1" in hero
    assert "unpriced, staked at 1u" in screen
    assert "flat $100" not in curve
    assert "colors.positive" not in curve
    assert "colors.betInk" in curve
    assert "Cumulative units, 1 to win" in curve
    assert "formatSigned(endUnits, 2, 'u')" in curve
    assert "pnlColor(endUnits, 2)" in curve
    assert "strokeDasharray" in curve
    assert "unitAxisTicks" in curve
    assert "colors.betInk" in spark
    assert "colors.positive" not in spark
    assert "units, 1 to win" in share
    assert "flat-bet ROI" not in share
    assert "flat $100" not in share
