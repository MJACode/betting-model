"""One unit basis everywhere (mike, 2026-11-03), and the older faults found
while moving every result to units.

CLAUDE.md §2: units are the graded set sized by stake_for, 1u to win at
COALESCE(decision_odds, dk_odds), risk capped at 3u, a pick with no price at
1u. That is what Discord #results and the Record tab book
(published_pick_unit_profit / published_pick_unit_risked). The dashboard used
profit_flat / 100 instead (1u risked per pick), so the same model showed two
different unit totals. These pin the dashboard on the published basis, and:

* the dashboard's record queries no longer re-cut settled picks with today's
  action filter (CLAUDE.md §1c: a record query filters on what the pick WAS);
* the settle log's total no longer counts an unpriced pick at an invented -110;
* the opening-signal shadow track writes no profit for a pick with no price;
* the NFL wind and opener cards no longer write a dollar stake_amt column;
* the picks prompt no longer tells a reader to re-paste a threshold block.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DASH = "dashboard/app.py"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _query_sql(src: str, name: str) -> str:
    """The SQL source passed to query(...) for the assignment `name = query(...)`."""
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == name
                and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", None) == "query"):
            return ast.get_source_segment(src, node.value.args[0])
    raise AssertionError(f"no `{name} = query(...)` in {DASH}")


# The dashboard's record queries: settled picks, a result, a total. Today's
# Picks and Avoid Signals are the live board and keep the app's action cut.
RECORD_QUERIES = ("week_stats", "units_hist", "model_perf", "cal_df", "edge_df", "log_df")


@pytest.mark.parametrize("name", RECORD_QUERIES)
def test_a_dashboard_record_query_does_not_recut_with_todays_filter(name):
    sql = _query_sql(_read(DASH), name)
    assert "_ACTION_FILTER" not in sql, f"{name} re-cuts settled picks"
    assert "model_action_thresholds" not in sql, name


def test_the_live_board_still_applies_the_action_cut():
    src = _read(DASH)
    assert "_ACTION_FILTER" in _query_sql(src, "picks_df")


@pytest.mark.parametrize("name", ("week_stats", "units_hist", "model_perf"))
def test_the_dashboard_totals_are_the_published_record(name):
    """The same rows and units as the app's Record tab and Discord."""
    sql = _query_sql(_read(DASH), name)
    assert "v_public_track_record" in sql, name
    assert "units" in sql and "risked" in sql, name
    assert "profit_flat" not in sql, name


def _dash_units_cell():
    src = _read(DASH)
    tree = ast.parse(src)
    import pandas as pd
    from tracking.published_units import unit_profit
    ns = {"pd": pd, "unit_profit": unit_profit}
    for name in ("_stake_or_none", "_units_cell"):
        fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        exec(ast.get_source_segment(src, fn), ns)
    return ns["_units_cell"]


def test_the_pick_log_shows_the_published_units():
    cell = _dash_units_cell()
    # 1u to win: a -200 win is +1u, a -200 loss is -2u (not +0.50u / -1.00u).
    assert cell("WIN", -200) == "+1.00u"
    assert cell("LOSS", -200) == "-2.00u"
    # Risk capped at 3u: -400 to win 1 would lay 4u.
    assert cell("LOSS", -400) == "-3.00u"
    # No price is the bare 1u, not an invented -110.
    assert cell("WIN", None) == "+1.00u"
    assert cell("PUSH", -110) == "0.00u"
    assert cell(None, -110) == "–"


# ── tracking/paper_tracker.py: the settle log ────────────────────────────────

class _FakeConn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None
        self.params = None

    def execute(self, sql, params=()):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return self.rows


def test_the_settle_log_total_is_the_published_units():
    from tracking import paper_tracker as pt
    conn = _FakeConn([(None, "WIN"), (-200, "LOSS"), (-110, "WIN"), (150, "PUSH")])
    line = pt._posted_units_line(conn, "2026-11-03T11:00:00Z")
    # 1 (no price, bare 1u) - 2 (a -200 loss) + 1 (a -110 win) = 0.00u on
    # 1 + 2 + 1.1 = 4.10u risked. A push lays nothing.
    assert "0.00u" in line and "4.10u risked" in line, line
    assert "settled_at" in conn.sql and "signal_type = 'BET'" in conn.sql
    assert conn.params == ("2026-11-03T11:00:00Z",)


def test_settle_picks_logs_the_published_units_not_the_flat_total():
    src = _read("tracking/paper_tracker.py")
    body = src[src.index("def settle_picks("):src.index("def print_performance_summary(")]
    assert "_posted_units_line(conn, settled_at)" in body
    assert "total_profit_flat / 100" not in body


# ── tracking/opening_signals.py: no price, no profit ─────────────────────────

def test_an_unpriced_opening_signal_gets_no_profit():
    from tracking import opening_signals as os_
    assert os_._priced_profit(None, -100.0, -12.0) == (None, None)
    assert os_._priced_profit(-110, 90.91, 3.0) == (90.91, 3.0)


def test_the_shadow_settle_writes_the_gated_profit():
    src = _read("tracking/opening_signals.py")
    body = src[src.index("def settle_opening_signals("):]
    assert "_priced_profit(dk_odds, profit_flat, profit_kelly)" in body


# ── NFL cards: no dollar stake column ────────────────────────────────────────

def test_the_wind_model_writes_no_dollar_stake():
    from nfl.models import wind_totals
    assert "bankroll" not in inspect.signature(wind_totals.select_bets).parameters
    assert "stake_amt" not in _read("nfl/models/wind_totals.py")


@pytest.mark.parametrize("rel", ["nfl/scripts/daily_opener_card.py",
                                 "nfl/scripts/weekly_wind_card.py"])
def test_the_cards_take_no_bankroll(rel):
    src = _read(rel)
    assert "stake_amt" not in src
    assert '"--bankroll"' not in src


# ── The picks prompt: nothing to re-paste on a threshold change ──────────────

def test_the_prompt_doc_does_not_ask_for_a_threshold_paste():
    doc = _read("docs/mobile_picks_prompt.md")
    assert "paste the block it prints" not in doc
    emit = _read("scripts/emit_threshold_sql.py")
    assert "whenever a\nthreshold changes" not in emit and "whenever a threshold changes" not in emit
