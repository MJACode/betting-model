"""NCAAB first-half closing line value.

The live feed (data/ingestors/ncaab_first_half_odds.py) files every pull as
'open'. The close is the bet book's newest pre-tip row on the same line, and
only a row pulled strictly after the pick was created. The decision pull is
the price taken. No such row leaves the pick unmeasured: it is not stamped
standard_v2 with empty closing fields.

NBA first-half markets still read snapshot_type = 'close' only. A null close
does not mark any pick measured.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from tests.test_clv_price_taken import _pick  # noqa: E402
from tests.test_nba_team_total_clv import _SnapConn  # noqa: E402
from tracking import paper_tracker as pt  # noqa: E402
from tracking.clv_math import same_book_clv  # noqa: E402

TIP = "2026-11-03T23:00:00Z"
MIGRATION = ROOT / "data" / "migrations" / "clv_standard_v2_2026_10_14.sql"


def _quote(book, market, at, *, line, over, under, spread=None, home=None, away=None,
           kind="open"):
    return (book, market, at, {
        "total_line": line, "over_price": over, "under_price": under,
        "spread_home": spread, "home_price": home, "away_price": away,
        "snapshot_type": kind,
    })


def _half_pick(**kw):
    base = dict(
        pick_id=11, game_id="NCAAB_2026-11-03_DUKE_UNC", model_id="ncaab_first_half_total",
        pick_side="over", dk_odds=None, commence_time=TIP, game_time=TIP,
        pick_label="DUKE @ UNC Over 70.5 First Half", scored_line=70.5,
        created_at="2026-11-03 22:00:00+00", prop_market=None, clv_method=None,
        decision_odds=-110.0, decision_book="fanduel", game_date="2026-11-03",
    )
    base.update(kw)
    return base


def _capture(pick, quotes):
    conn = _SnapConn([pick], quotes)
    n = pt._capture_clv(conn, "2026-11-03", "TS")
    return n, conn.updates


def test_an_ncaab_first_half_total_uses_the_post_creation_pre_tip_row():
    """Same book, same line, pulled 10 minutes before tip, after the pick existed."""
    pick = _half_pick()
    quotes = [
        _quote("fanduel", "totals_h1", "2026-11-03T21:50:00Z", line=70.5, over=-110, under=-110),
        _quote("fanduel", "totals_h1", "2026-11-03T22:50:00Z", line=70.5, over=-120, under=100),
        _quote("fanduel", "totals_h1", "2026-11-03T22:55:00Z", line=70.5, over=-200, under=170,
               kind="in_play"),
    ]
    n, (u,) = _capture(pick, quotes)
    assert n == 1
    assert u["closing_dk_odds"] == -120
    assert u["closing_line"] == 70.5
    assert u["clv_close_book"] == "fanduel"
    assert u["clv_method"] == pt.CLV_METHOD_STANDARD
    assert u["clv_pct"] == same_book_clv(-110.0, -120)[0]
    assert u["clv_beat_close"] is True


def test_an_ncaab_first_half_spread_with_no_pull_after_creation_stays_unmeasured():
    """A row at the decision instant is the price taken, not the close."""
    pick = _half_pick(
        pick_id=12, model_id="ncaab_first_half_spread", pick_side="home",
        scored_line=-2.5, created_at="2026-11-03 22:50:00+00",
        decision_odds=-108.0, pick_label="DUKE @ UNC — UNC -2.5 First Half",
    )
    quotes = [
        _quote("fanduel", "spreads_h1", "2026-11-03T22:40:00Z", line=None, over=None, under=None,
               spread=-2.5, home=-105, away=-115),
        _quote("fanduel", "spreads_h1", "2026-11-03T22:50:00Z", line=None, over=None, under=None,
               spread=-2.5, home=-108, away=-112),
    ]
    n, updates = _capture(pick, quotes)
    assert (n, updates) == (0, [])


def test_an_nba_first_half_still_reads_only_a_close_row():
    """An 'open' row after the pick, even a later one, is not an NBA close."""
    pick = _pick(
        pick_id=13, game_id="NBA_2026-11-03_BOS_MIL", model_id="nba_first_half_total_luck",
        pick_side="over", scored_line=70.5, dk_odds=None, decision_odds=-110.0,
        decision_book="fanduel", created_at="2026-11-03 21:00:00+00",
        commence_time=TIP, game_time=TIP, game_date="2026-11-03",
        pick_label="BOS @ MIL Over 70.5 First Half",
    )
    open_only = [
        _quote("fanduel", "totals_h1", "2026-11-03T22:55:00Z", line=70.5, over=-200, under=170),
    ]
    n, updates = _capture(pick, open_only)
    assert (n, updates) == (0, [])

    both = open_only + [
        _quote("fanduel", "totals_h1", "2026-11-03T22:40:00Z", line=70.5, over=-125, under=105,
               kind="close"),
    ]
    n, (u,) = _capture(pick, both)
    assert n == 1
    assert u["closing_dk_odds"] == -125
    assert u["clv_method"] == pt.CLV_METHOD_STANDARD


def test_a_null_close_is_not_stamped_measured():
    """Only a real close sets standard_v2. Empty fields are not a measurement."""
    assert pt._real_close(None, None, None, None) is False
    assert pt._real_close(None, None, 0.0, None) is True
    assert pt._real_close(-120, None, None, None) is True

    pick = _half_pick(clv_method="graded_at_dk_legacy")
    quotes = [
        _quote("fanduel", "totals_h1", "2026-11-03T21:50:00Z", line=70.5, over=-110, under=-110),
    ]
    n, updates = _capture(pick, quotes)
    assert (n, updates) == (0, [])

    src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    assert "_real_close(" in src
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").split())
    assert ("p.model_id NOT IN ('ncaab_first_half_total', 'ncaab_first_half_spread')"
            in sql)
    assert "o.snapshot_at::timestamptz > s.created_at" in sql
    assert "ncaab_first_half_total" in src.split("def _backfill_clv", 1)[1].split(
        "def _closing_line_for", 1)[0]
