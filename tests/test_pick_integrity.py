"""Every pick that goes out must say the same bet in its words and its numbers.

mike, 2026-09-12: *"I want error checking ... You must check every pick that
goes out."* A reply turned BUF @ HOU "BUF +1" into "Bills -1" by reading
`picks.scored_line` -- the HOME number, Houston's -1 -- as the Bills' line, and
that number went to his followers. The row and the label were right; the
reading was wrong, and the app did the same thing in three places.

Four layers, each tested here:
  1. tracking/pick_integrity -- the check itself, on the REAL row.
  2. every publisher refuses a pick that fails it (Discord pre-game, restate,
     live and free pick; push pre-game and live), and never ledgers it.
  3. the health check turns a refusal into a CRIT, so it cannot sit quietly.
  4. the app never renders a stored line without converting it to the side.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tracking import discord_notifier, push_notifier
from tracking.pick_integrity import pick_problems, refuse_mismatched

# The production row, verbatim from picks_log (INSERT, 2026-09-07 01:37 UTC).
BUF_LABEL = "BUF @ HOU — BUF +1 (Opener -2 vs Pinnacle, fanatics) · 0.98u"
BUF = dict(label=BUF_LABEL, side="away", line=-1.0, model_id="nfl_opener_spread",
           home="HOU", away="BUF")


# ── 1. the check ─────────────────────────────────────────────────────────────

def test_the_real_bills_pick_passes():
    assert pick_problems(**BUF) == []


def test_bills_minus_one_is_refused():
    """The exact error that was published: the home number shown as the side's."""
    bad = dict(BUF, label=BUF_LABEL.replace("BUF +1", "BUF -1"))
    problems = pick_problems(**bad)
    assert problems and "+1" in problems[0]


@pytest.mark.parametrize("label,side,line,ok", [
    ("SD -1.5", "away", 1.5, True),        # away pick: label is -home
    ("SD +1.5", "away", 1.5, False),
    ("DAL -1.5", "home", -1.5, True),      # home pick: label is the home number
    ("DAL +1.5", "home", -1.5, False),
    ("DET +0.5 F5", "away", -0.5, True),   # "F5" is not a signed number
    ("LAD +1.5 (live)", "away", -1.5, True),
    ("BUF PK", "away", 0.0, True),
    ("BUF", "away", -1.0, False),          # a spread label with no number
])
def test_spreads_compare_the_label_to_the_sides_line(label, side, line, ok):
    got = pick_problems(label, side, line, "mlb_runline")
    assert (got == []) is ok, got


def test_a_label_naming_the_other_team_is_refused():
    got = pick_problems("HOU +1", "away", -1.0, "nfl_opener_spread", "HOU", "BUF")
    assert any("names HOU" in p for p in got), got


def test_team_prefixes_do_not_collide():
    """LA and LAC: 'LA +3.5' is the away side, not a mention of LAC."""
    assert pick_problems("LA +3.5", "away", -3.5, "nfl_opener_spread", "LAC", "LA") == []


def test_a_moneyline_naming_the_other_team_is_refused():
    assert pick_problems("NYY ML", "home", None, "mlb_moneyline", "BOS", "NYY")
    assert pick_problems("BOS ML", "home", None, "mlb_moneyline", "BOS", "NYY") == []


@pytest.mark.parametrize("label,side,line,ok", [
    ("Under 43.5", "under", 43.5, True),
    ("Over 43.5", "under", 43.5, False),   # wrong side
    ("Under 44.5", "under", 43.5, False),  # wrong number
    ("Blake Snell Over 5.5 Ks", "over", 5.5, True),
    ("Blake Snell", "over", 5.5, False),   # no number at all
])
def test_totals_and_props(label, side, line, ok):
    got = pick_problems(label, side, line, "mlb_over_under")
    assert (got == []) is ok, got


def test_no_label_is_refused():
    assert pick_problems("", "home", None, "mlb_moneyline")


def test_a_producer_that_does_not_supply_side_and_line_is_refused():
    """A check that a producer can skip by omitting a key is not a check."""
    assert refuse_mismatched([{"lock_key": "k", "label": "BOS ML"}], "t") == []


# ── 2. every publisher refuses it ────────────────────────────────────────────

class _Conn:
    """Records every statement; returns nothing for every read."""

    def __init__(self):
        self.calls: list[tuple[str, tuple]] = []

    def execute(self, sql, params=()):
        self.calls.append((sql, tuple(params)))

        class _R:
            def fetchall(self):
                return []

            def fetchone(self):
                return None
        return _R()

    def commit(self):
        pass

    def close(self):
        pass

    def ledgered(self) -> set:
        return {p[0] for sql, p in self.calls if "INSERT INTO push_sent" in sql}


def _sig(key, label, line=-1.0):
    return {"lock_key": key, "label": label, "sport": "NFL", "pick_id": 1,
            "model_id": "nfl_opener_spread", "side": "away", "line": line,
            "home": "HOU", "away": "BUF", "prob": 0.55, "edge": 0.02,
            "dk_odds": -115, "kelly": 0.01, "commence": None, "posted_at": None}


GOOD = _sig("G1:nfl_opener_spread", BUF_LABEL)
BAD = _sig("G2:nfl_opener_spread", BUF_LABEL.replace("BUF +1", "BUF -1"))


@pytest.fixture
def discord_sent(monkeypatch):
    sent: list[str] = []

    def fake_post(url, sport, group, target_date, **kw):
        sent.extend(s["label"] for s in group)
        return [(group, "m1")]
    monkeypatch.setattr(discord_notifier, "_post_picks", fake_post)
    monkeypatch.setattr(discord_notifier, "_webhook_for_sport", lambda s: "https://x")
    monkeypatch.setattr(discord_notifier, "_live_webhook_for_sport", lambda s: "https://x")
    return sent


def test_discord_pregame_refuses_and_does_not_ledger(monkeypatch, discord_sent):
    monkeypatch.setattr(discord_notifier, "_new_signals", lambda c, d: [GOOD, BAD])
    conn = _Conn()
    assert discord_notifier._post_new_signals(conn, "2026-09-13", False) == 1
    assert discord_sent == [GOOD["label"]]
    assert conn.ledgered() == {GOOD["lock_key"]}


def test_discord_live_refuses_and_does_not_ledger(monkeypatch, discord_sent):
    monkeypatch.setattr(discord_notifier, "_new_live_signals", lambda c, d: [GOOD, BAD])
    conn = _Conn()
    assert discord_notifier._post_new_live_signals(conn, "2026-09-13", False) == 1
    assert discord_sent == [GOOD["label"]]
    assert conn.ledgered() == {GOOD["lock_key"]}


def test_discord_restate_refuses(monkeypatch, discord_sent):
    monkeypatch.setattr(discord_notifier, "DISCORD_RESTATE_DATES", {"2026-09-13"})
    monkeypatch.setattr(discord_notifier, "_configured", lambda: True)
    monkeypatch.setattr(discord_notifier, "_locked_signals", lambda c, d: [GOOD, BAD])
    monkeypatch.setattr(discord_notifier, "_delete_posted", lambda *a, **k: 0)
    monkeypatch.setattr(discord_notifier.config, "DISCORD_WEBHOOK_FREE", "", raising=False)
    conn = _Conn()
    monkeypatch.setattr(discord_notifier, "get_connection", lambda: conn)
    discord_notifier.notify_discord_restate("2026-09-13")
    assert discord_sent == [GOOD["label"]]


def test_discord_free_pick_candidates_refuse(monkeypatch):
    """The free channel reads its own query, so it needs its own guard."""
    def row(key, label):
        return (key, label, "NFL", -115, 0.01, "HOU", "BUF", None, None, None,
                None, "nfl_opener_spread", 0.55, 0.0, -200, "away", -1.0)

    class _Rows(_Conn):
        def execute(self, sql, params=()):
            class _R:
                def fetchall(self):
                    return [row(GOOD["lock_key"], GOOD["label"]),
                            row(BAD["lock_key"], BAD["label"])]
            return _R()
    monkeypatch.setattr(discord_notifier, "price_bound", lambda *a, **k: None)
    got = discord_notifier._free_pick_candidates(_Rows(), "2026-09-13")
    assert [c["lock_key"] for c in got] == [GOOD["lock_key"]]


def test_push_pregame_refuses_and_does_not_ledger(monkeypatch):
    monkeypatch.setattr(push_notifier, "_new_bet_signals", lambda c, d: [GOOD, BAD])
    monkeypatch.setattr(push_notifier, "_dropped_signals", lambda c, d: [])
    conn = _Conn()
    push_notifier._send_signal_changes(conn, "2026-09-13", False)
    assert conn.ledgered() == {GOOD["lock_key"]}


def test_push_live_refuses_and_does_not_ledger(monkeypatch):
    monkeypatch.setattr(push_notifier, "_new_live_signals", lambda c, d: [GOOD, BAD])
    conn = _Conn()
    monkeypatch.setattr(push_notifier, "get_connection", lambda: conn)
    push_notifier.notify_live_signals("2026-09-13")
    assert conn.ledgered() == {GOOD["lock_key"]}


def test_push_dropped_refuses_and_does_not_ledger(monkeypatch):
    """The "moved past the bet line" alert names a pick too, so it is checked
    like every other send path."""
    monkeypatch.setattr(push_notifier, "_new_bet_signals", lambda c, d: [])
    monkeypatch.setattr(push_notifier, "_dropped_signals", lambda c, d: [GOOD, BAD])
    conn = _Conn()
    push_notifier._send_signal_changes(conn, "2026-09-13", False)
    assert conn.ledgered() == {GOOD["lock_key"]}


def test_push_line_change_refuses_and_does_not_ledger(monkeypatch):
    """A tracked bet's line-move alert carries the pick's label into a push."""
    def alert(sig):
        return dict(sig, device_id="d1", kind="line_change_1", locked=-115,
                    current=-130, against=True)
    monkeypatch.setattr(push_notifier, "_line_change_alerts",
                        lambda c, d: [alert(GOOD), alert(BAD)])
    conn = _Conn()
    monkeypatch.setattr(push_notifier, "get_connection", lambda: conn)
    push_notifier.notify_line_changes("2026-09-13")
    assert conn.ledgered() == {GOOD["lock_key"]}


# ── 3. the health check makes a refusal loud ─────────────────────────────────

class _Shim:
    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql, tuple(params))

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


@pytest.fixture
def health_db(monkeypatch):
    from data.db_setup import SCHEMA_SQL, _MIGRATIONS
    import tracking.system_health as sh
    path = tempfile.mktemp(suffix=".db")
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_SQL)
    for tbl, col, defn in _MIGRATIONS:
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    c.execute("CREATE TABLE model_action_thresholds (model_id TEXT PRIMARY KEY,"
              " min_prob REAL, min_edge REAL, prob_only BOOLEAN, paused BOOLEAN,"
              " min_odds REAL)")
    c.commit()
    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    yield c, sh
    c.close()


def _health(sh, name="pick_label_integrity"):
    return {r["check_name"]: r for r in sh.run_system_health()["results"]}[name]


def _add_pick(c, label, line=-1.0):
    from config import today_et
    today = today_et()
    c.execute("INSERT OR IGNORE INTO games (game_id, sport, season, game_date,"
              " home_team, away_team) VALUES ('G', 'NFL', 2026, ?, 'HOU', 'BUF')",
              (today,))
    c.execute("INSERT INTO picks (game_id, model_id, sport, game_date, pick_side,"
              " pick_label, model_probability, dk_implied_prob, edge, scored_line,"
              " kelly_fraction, recommended_bet, bankroll_at_pick, signal_type)"
              " VALUES ('G', 'nfl_opener_spread', 'NFL', ?, 'away', ?, 0.55, 0.53,"
              " 0.02, ?, 0.01, 10, 1000, 'BET')", (today, label, line))
    c.commit()


def test_health_check_is_ok_when_every_label_agrees(health_db):
    c, sh = health_db
    _add_pick(c, BUF_LABEL)
    assert _health(sh)["status"] == sh.OK


def test_health_check_is_crit_on_a_mismatched_label(health_db):
    c, sh = health_db
    _add_pick(c, BUF_LABEL.replace("BUF +1", "BUF -1"))
    r = _health(sh)
    assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")
    assert "BUF -1" in r["detail"]


# ── 4. the app never shows a stored line raw ─────────────────────────────────

# `scored_line`, `closing_line` and a book row's `spread_home` are HOME numbers
# for spreads. On screen they must go through formatSideLine / lineForSide.
_RAW = re.compile(
    r"String\(\s*pick\.(?:scored_line|closing_line)\s*\)"
    r"|\$\{\s*(?:pick\.(?:scored_line|closing_line)|quoteLine|quote\.line)\s*\}"
    r"|[>{]\s*\{?\s*pick\.(?:scored_line|closing_line)\s*\}"
    # A book row's line rendered straight out of a ternary: the All books
    # table did `{q.line != null ? q.line : '—'}` and the first version of
    # this pattern did not see it (UX review, 2026-09-12).
    r"|\?\s*\w+\.line\s*:\s*'")


def test_the_app_never_renders_a_pick_line_without_the_side_flip():
    offenders = []
    for path in (ROOT / "mobile" / "src").rglob("*.ts*"):
        src = path.read_text(encoding="utf-8")
        # A book quote only carries a pick's spread in a file that renders a
        # pick; a prop board's own quote is not one.
        about_a_pick = "displayQuoteForPick(" in src or "pick.pick_side" in src
        for m in _RAW.finditer(src):
            if "scored_line" not in m.group(0) and "closing_line" not in m.group(0) \
                    and not about_a_pick:
                continue
            line_no = src.count("\n", 0, m.start()) + 1
            offenders.append(f"{path.relative_to(ROOT)}:{line_no}: {m.group(0)}")
    assert not offenders, (
        "a pick's stored line is the HOME number for spreads; show it through "
        "formatSideLine(line, pick.pick_side, market):\n" + "\n".join(offenders))


# ── the rule, where every session reads it ───────────────────────────────────

def test_the_rule_is_in_the_always_loaded_file():
    """Answering "what are tomorrow's picks" opens no file under tracking/, so
    a path-scoped copy would not load for the session that makes this error."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "QUOTE A PICK FROM ITS LABEL" in text
