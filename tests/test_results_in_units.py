"""Results and stakes are shown in units, never dollars (CLAUDE.md §4).

mike, 2026-11-03: "everything must be units". A unit is the posted stake,
`stake_for`: one unit to win at the decided price, risk capped at 3.
`profit_flat` / 100 is the 1u-risked figure, which no surface shows.

Each test here pins one surface a person reads: the Streamlit dashboard, the
picks email, the settle and summary logs, the shadow-track logs, the
model-quality volume check, the MLB record audit and the two NFL cards.
Stored columns (profit_flat, profit_kelly, recommended_bet, bankroll_at_pick)
are not touched; only what is shown changes.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import io
import json
import re
import sqlite3
import sys
import tempfile
import tokenize
from pathlib import Path

import pytest
from loguru import logger

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _string_literals(src: str) -> list[tuple[int, str]]:
    """Every string constant in the module, f-string pieces included."""
    out = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append((node.lineno, node.value))
    return out


class _Logs:
    """Collect loguru messages for the duration of a test."""

    def __init__(self):
        self.lines: list[str] = []
        self._id = None

    def __enter__(self):
        self._id = logger.add(lambda m: self.lines.append(str(m.record["message"])),
                              level="DEBUG", format="{message}")
        return self

    def __exit__(self, *exc):
        logger.remove(self._id)

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


# ── dashboard/app.py ─────────────────────────────────────────────────────────
# Streamlit runs the page and a database query on import, so the page is
# pinned by its source, and its pure helpers are lifted out of it and run.

DASH = "dashboard/app.py"


def test_the_dashboard_shows_no_dollar_amount():
    hits = [(ln, s) for ln, s in _string_literals(_read(DASH)) if "$" in s]
    assert hits == [], f"dollar text on the dashboard: {hits}"


def _code_without_comments(src: str) -> str:
    toks = tokenize.generate_tokens(io.StringIO(src).readline)
    return " ".join(t.string for t in toks if t.type != tokenize.COMMENT)


def test_the_dashboard_never_shows_the_paper_kelly_bankroll():
    """The Kelly bankroll is dollars on a paper roll no published stake uses."""
    code = _code_without_comments(_read(DASH))
    for gone in ("profit_kelly", "bankroll_at_pick", "recommended_bet", "BANKROLL"):
        assert gone not in code, f"{gone} is still read by the dashboard"


def test_every_dashboard_query_actually_applies_the_action_filter():
    """A plain (not f-) string sends the text '{_ACTION_FILTER}' to Postgres,
    which is a syntax error: six of the page's queries did this."""
    plain = [ln for ln, s in _string_literals(_read(DASH))
             if "{_ACTION_FILTER}" in s]
    assert plain == [], f"plain strings carry the placeholder at lines {plain}"


def _dashboard_helpers() -> dict:
    src = _read(DASH)
    tree = ast.parse(src)
    wanted = {"_price_or_none", "_units_cell", "_stake_cell", "_units_at_risk", "_stake_or_none"}
    found = {n.name: ast.get_source_segment(src, n) for n in tree.body
             if isinstance(n, ast.FunctionDef) and n.name in wanted}
    assert set(found) == wanted, f"missing helpers: {wanted - set(found)}"
    import pandas as pd
    from tracking.discord_notifier import fmt_stake, fmt_units, stake_for, units_for
    from tracking.published_units import unit_profit
    ns = {"pd": pd, "fmt_stake": fmt_stake, "fmt_units": fmt_units,
          "stake_for": stake_for, "units_for": units_for, "unit_profit": unit_profit}
    for code in found.values():
        exec(code, ns)
    return ns


def test_the_dashboard_pick_log_shows_units_from_the_result():
    # The published stake (tests/test_units_one_basis.py pins the basis):
    # a +150 win is +1u to win, a -110 loss lays 1.1u.
    h = _dashboard_helpers()
    assert h["_units_cell"]("WIN", 150) == "+1.00u"
    assert h["_units_cell"]("LOSS", -110) == "-1.10u"
    assert h["_units_cell"](None, -110) == "–"
    assert h["_units_cell"](float("nan"), -110) == "–"


def test_the_dashboard_stake_is_the_published_stake():
    h = _dashboard_helpers()
    # decision_odds wins over dk_odds; pandas hands a missing one over as NaN.
    assert h["_stake_cell"](0.03, -110, -130) == "1.1u to win 1u"
    assert h["_stake_cell"](0.03, float("nan"), -200) == "2u to win 1u"
    assert h["_stake_cell"](0.03, None, None) == "1u"
    assert h["_units_at_risk"]([(0.03, -110, None), (0.03, None, -200)]) == "3.1u"


def test_the_dashboard_reads_a_picks_own_stake():
    # picks.stake_units (pick_stake_units_2026_11_06.sql): 2u to win at -110
    # lays 2.2u; at -200 the 3u risk cap binds and the win is recomputed.
    h = _dashboard_helpers()
    assert h["_stake_cell"](0.03, -110, None, 2) == "2.2u to win 2u"
    assert h["_stake_cell"](0.03, -200, None, 2) == "3u to win 1.5u"
    assert h["_stake_cell"](0.03, -110, None, float("nan")) == "1.1u to win 1u"
    assert h["_units_cell"]("WIN", -110, 2) == "+2.00u"
    assert h["_units_cell"]("LOSS", -110, 2) == "-2.20u"
    assert h["_units_at_risk"]([(0.03, -110, None, 2), (0.03, -110, None, None)]) == "3.3u"


# ── email/render_picks_email.py ──────────────────────────────────────────────
# Loaded from its path: the folder has no __init__.py and shares a name with
# the standard library's email package, so `import email.…` cannot reach it.

def _email_module():
    path = ROOT / "email" / "render_picks_email.py"
    spec = importlib.util.spec_from_file_location("render_picks_email_under_test", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod          # @dataclass looks its module up here
    spec.loader.exec_module(mod)
    return mod


def _render_mock_email(mod) -> str:
    params = inspect.signature(mod.render_email).parameters
    kwargs = {"picks": mod.MOCK_PICKS, "date_str": mod.MOCK_DATE}
    if "bankroll" in params:
        kwargs["bankroll"] = 1500.0
    return mod.render_email(**kwargs)


def test_the_picks_email_states_stakes_in_units():
    html = _render_mock_email(_email_module())
    assert "$" not in html
    assert "1.1u to win 1u" in html          # the -110 total
    assert "Bankroll" not in html


def test_the_committed_email_preview_has_no_dollar_amount():
    assert "$" not in _read("email/preview.html")


# ── tracking/opening_signals.py and tracking/parlay_track_record.py ─────────

class _ScriptedConn:
    """Answers the one SELECT each settler starts with; everything else empty."""

    def __init__(self, scripted: dict[str, list]):
        self.scripted = scripted

    def execute(self, sql, params=None):
        for marker, rows in self.scripted.items():
            if marker in sql:
                return _Rows(rows)
        return _Rows([])


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


def test_the_opening_signal_settle_log_is_in_units():
    from tracking.opening_signals import settle_opening_signals
    # A home moneyline win at +150: profit_flat 150 per $100, 1.5 units.
    row = (1, "MLB_2026-04-04_NYY_BOS", "mlb_moneyline", "home", 150.0, None,
           20.0, None, 5, 3, 1, None, 0, "2026-04-04T23:05:00Z", None, None)
    conn = _ScriptedConn({"FROM opening_signals os": [row]})
    with _Logs() as logs:
        out = settle_opening_signals(conn, "2026-04-04", "2026-04-05T12:00:00Z")
    assert out[0] == 1 and out[4] == pytest.approx(150.0)   # stored scale kept
    line = next(l for l in logs.lines if "Opening-signal shadow settle" in l)
    assert "$" not in line
    assert "+1.50u" in line


def test_the_parlay_settle_log_is_in_units():
    """Parlay profit_flat is already units (PARLAY_FLAT_STAKE = 1.0): relabel,
    never divide."""
    from tracking.parlay_track_record import settle_parlay_track_record
    conn = _ScriptedConn({
        "FROM parlay_track_record": [(1, json.dumps(["a", "b"]), json.dumps([150, 150]))],
        "FROM opening_signals": [("a", "WIN"), ("b", "WIN")],
    })
    with _Logs() as logs:
        out = settle_parlay_track_record(conn, "2026-04-04", "2026-04-05T12:00:00Z")
    assert out[3] == pytest.approx(5.25)                     # 2.5 x 2.5 - 1
    line = next(l for l in logs.lines if "Parlay track record settle" in l)
    assert "$" not in line
    assert "+5.25u" in line


# ── tracking/paper_tracker.py ────────────────────────────────────────────────

def test_the_settle_log_has_no_dollar_amount():
    src = _read("tracking/paper_tracker.py")
    body = src[src.index("def settle_picks("):src.index("def print_performance_summary(")]
    hits = [s for _ln, s in _string_literals(body) if "$" in s]
    assert hits == [], hits
    assert "Kelly P&L" not in body


class _SqliteShim:
    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql.replace("%s", "?"), tuple(params or ()))

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()

    def close(self):
        self._c.close()


def test_the_performance_summary_is_in_units_and_ignores_unpriced_profit(monkeypatch):
    from data.db_setup import SCHEMA_SQL
    import tracking.paper_tracker as pt

    path = tempfile.mktemp(suffix=".db")
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA_SQL)
    from datetime import date
    today = date.today().isoformat()
    for i, (result, odds, flat, kelly) in enumerate((
            ("WIN", 150.0, 150.0, 30.0),
            ("LOSS", -110.0, -100.0, -22.0),
            ("LOSS", None, -100.0, -20.0),       # unpriced: -110 was made up
    )):
        raw.execute("""
            INSERT INTO picks (game_id, model_id, sport, game_date, pick_side,
                pick_label, model_probability, dk_implied_prob, edge, dk_odds,
                kelly_fraction, recommended_bet, bankroll_at_pick, signal_type,
                result, profit_flat, profit_kelly, settled_at)
            VALUES (?, 'mlb_moneyline', 'MLB', ?, 'home', ?, 0.6, 0.5, 0.1, ?,
                    0.02, 20, 1000, 'BET', ?, ?, ?, ?)
        """, (f"g{i}", today, f"pick {i}", odds, result, flat, kelly,
              f"{today}T0{i}:00:00Z"))
    raw.commit()
    raw.close()
    monkeypatch.setattr(pt, "get_connection", lambda: _SqliteShim(path))
    with _Logs() as logs:
        pt.print_performance_summary(days=7)
    text = logs.text
    assert "$" not in text
    assert "Bankroll" not in text and "Kelly" not in text
    # priced picks only: +150 - 100 = +50 per $100 = +0.50 units
    assert "+0.50u" in text


# ── tracking/model_quality.py ────────────────────────────────────────────────

def test_the_volume_check_counts_the_published_stake():
    """`recommended_bet` is paper-Kelly dollars; /100 is not a unit. The
    units a model lays are stake_for's risk at the decided price."""
    import tracking.model_quality as mq
    today = [{"model_id": "mlb_moneyline", "sport": "MLB", "game_id": f"g{i}",
              "pick_side": "home", "recommended_bet": 40.0,
              "kelly_fraction": 0.02, "dk_odds": -130, "decision_odds": -200}
             for i in range(6)]
    finding = mq.detect_volume_spike(today, [(2, 4.0)] * 6)
    assert finding["metrics"]["units_today"] == pytest.approx(12.0)
    assert "12.0u today" in finding["detail"]


def test_the_volume_history_counts_the_published_stake(monkeypatch):
    from data.db_setup import SCHEMA_SQL
    import tracking.model_quality as mq

    path = tempfile.mktemp(suffix=".db")
    raw = sqlite3.connect(path)
    raw.executescript(SCHEMA_SQL)
    days = ["2026-09-13", "2026-09-14", "2026-09-15", "2026-09-16",
            "2026-09-17", "2026-09-18", "2026-09-19"]
    for d in days:
        for i in range(2):
            raw.execute("""
                INSERT INTO picks (game_id, model_id, sport, game_date, pick_side,
                    pick_label, model_probability, dk_implied_prob, edge, dk_odds,
                    decision_odds, kelly_fraction, recommended_bet,
                    bankroll_at_pick, signal_type)
                VALUES (?, 'mlb_moneyline', 'MLB', ?, 'home', ?, 0.6, 0.5, 0.1,
                        -130, -200, 0.02, 40, 1000, 'BET')
            """, (f"MLB_{d}_T{i}", d, f"pick {d} {i}"))
    raw.commit()
    raw.close()
    monkeypatch.setattr(mq, "get_connection", lambda: _SqliteShim(path))
    out = mq.run_model_quality("2026-09-19")
    vol = next(r for r in out["results"]
               if r["check_name"] == mq.VOLUME_SPIKE and r["model_key"] == "mlb_moneyline")
    metrics = vol["metrics"] if isinstance(vol["metrics"], dict) else json.loads(vol["metrics"])
    # two picks a day at -200: 2 units laid each, 4 a day; today the same.
    assert metrics["units_today"] == pytest.approx(4.0)
    assert metrics["median_units"] == pytest.approx(4.0)


# ── scripts/mlb_bet_record_audit.py ──────────────────────────────────────────

def test_the_mlb_record_audit_prints_units():
    from scripts import mlb_bet_record_audit as audit
    rec = audit.Rec()
    rec.add({"result": "WIN", "dk_odds": 150.0, "profit_flat": 150.0})
    rec.add({"result": "LOSS", "dk_odds": -110.0, "profit_flat": -100.0})
    line = rec.line("x")
    assert "+0.50u" in line
    assert "50.00" not in line.replace("+0.50u", "")
    assert "units" in audit.HEAD and "P&L" not in audit.HEAD
    assert rec.roi == pytest.approx(25.0)


def test_the_mlb_record_audit_reconcile_is_not_scaled_to_dollars():
    src = _read("scripts/mlb_bet_record_audit.py")
    assert "profit_units) * 100" not in src
    assert "P&L" not in src[src.index("def main("):]


# ── nfl/scripts/daily_opener_card.py, weekly_wind_card.py ────────────────────

@pytest.mark.parametrize("rel", ["nfl/scripts/daily_opener_card.py",
                                 "nfl/scripts/weekly_wind_card.py"])
def test_the_nfl_cards_print_units_not_a_dollar_stake(rel):
    src = _read(rel)
    printed = re.findall(r"cols = \[(.*?)\]", src, flags=re.S)
    assert printed, "the printed column list moved"
    for cols in printed:
        assert "stake_amt" not in cols
    assert "a.bankroll:,." not in src
