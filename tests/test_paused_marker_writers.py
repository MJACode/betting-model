"""Every pick writer stamps the #850 paused marker, not just the main scorer.

#850 (2026-10-01) keeps a paused model's real verdict and marks the row
downgrade_reason = config.PAUSED_NOTE; Discord, push, opening_signals, the
public views and the app all key on that marker. The post-merge review found
writers that never stamp it, so a paused model's BET from any of them was
written unmarked -- announceable and counted:

  scripts/nhl_props_card.py, scripts/nhl_prop_card.py,
  scripts/wnba_prop_market_card.py, scripts/nfl_prop_market_card.py,
  nfl/live_model/pick_writer.py, the golf builder and the prob-only builders
  in models/scorer.py -- and, found on the same sweep, scripts/
  mlb_game_market_card.py, scripts/mlb_total_public_fade_card.py and
  scripts/nfl_wind_publisher.py.

Each stamps models.scorer._pause_note(model_id) -- the same function, so the
same two pause sources (config.PAUSED_MODELS and model_auto_pauses) -- in the
row it builds, and binds the column in its INSERT.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import config
from models import scorer

ROOT = Path(__file__).resolve().parents[1]
NOTE = config.PAUSED_NOTE


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


@pytest.fixture
def paused(monkeypatch):
    """Pause exactly the given ids, through the scorer's own two sources."""
    def _set(*model_ids, auto=()):
        monkeypatch.setattr(scorer, "PAUSED_MODELS", set(model_ids))
        monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set(auto))
    _set()
    return _set


# ── the insert binds the column wherever the writer has its own INSERT ───────

_OWN_INSERTS = {
    "scripts/nhl_props_card.py": "_COLS",
    "scripts/nhl_prop_card.py": "_COLS",
    "scripts/wnba_prop_market_card.py": "_INSERT",
    "scripts/nfl_prop_market_card.py": "_INSERT",
    "nfl/live_model/pick_writer.py": "_INSERT_SQL",
}


@pytest.mark.parametrize("rel", sorted(_OWN_INSERTS))
def test_each_writer_binds_and_stamps_the_marker(rel):
    src = _src(rel)
    name = _OWN_INSERTS[rel]
    block = src.split(f"\n{name} = ")[1].split("\n\n")[0]
    assert "downgrade_reason" in block, f"{rel}: {name} does not write downgrade_reason"
    assert re.search(r'"downgrade_reason":\s*_pause_note\(', src), rel


def test_the_wind_and_opener_bets_bind_the_marker():
    src = _src("scripts/nfl_wind_publisher.py")
    assert src.count("signal_type, model_probability_cal, downgrade_reason)") == 2
    assert src.count("%(model_probability_cal)s, %(downgrade_reason)s)") == 2
    assert '"downgrade_reason": _pause_note(NFL_WIND_MODEL_ID),' in src
    assert '"downgrade_reason": _pause_note(NFL_OPENER_MODEL_ID),' in src
    # A NONE row's own reason yields to the marker, as in the scorer.
    assert '"downgrade_reason": (_pause_note(model_id)' in src


@pytest.mark.parametrize("rel", ["scripts/mlb_game_market_card.py",
                                 "scripts/mlb_total_public_fade_card.py"])
def test_the_mlb_cards_stamp_the_marker(rel):
    """These go through scorer._insert_picks, which binds downgrade_reason."""
    assert re.search(r'"downgrade_reason":\s*_pause_note\((model_id|MODEL_ID)\)', _src(rel))


def test_no_scorer_pick_dict_omits_the_marker():
    """Every literal pick dict in the scorer carries downgrade_reason."""
    lines = _src("models/scorer.py").split("\n")
    missing = []
    for i, line in enumerate(lines):
        if not re.search(r'"signal_type":\s', line):
            continue
        j = i
        while j > 0 and not re.search(r"(=|return|append\()\s*\{\s*$", lines[j]):
            j -= 1
        k = i
        while k < len(lines) and not re.match(r"\s*\}\)?\s*$", lines[k]):
            k += 1
        if "downgrade_reason" not in "\n".join(lines[j:k + 1]):
            missing.append(j + 1)
    assert not missing, f"pick dicts without downgrade_reason at scorer.py:{missing}"


# ── behaviour: the row a paused model writes is marked ───────────────────────

def test_the_nfl_live_lane_marks_a_paused_bet(monkeypatch):
    sys.path.insert(0, str(ROOT / "nfl"))
    from live_model.pick_writer import MODEL_ID, build_pick, _INSERT_SQL

    class _D:
        bet, model_id, side, line, price = True, MODEL_ID, "under", 11.5, -115.0
        model_prob, market_prob, stake_fraction = 0.58, 0.5349, 0.011
        player, market = "Blake Corum", "player_rush_attempts"
        context = {}

    monkeypatch.setattr(config, "PAUSED_MODELS", set())
    row = build_pick(_D(), "NFL_2026_01_BUF_HOU", 1000.0, game_date="2026-09-13")
    assert row["downgrade_reason"] is None
    monkeypatch.setattr(config, "PAUSED_MODELS", {MODEL_ID})
    row = build_pick(_D(), "NFL_2026_01_BUF_HOU", 1000.0, game_date="2026-09-13")
    assert row["downgrade_reason"] == NOTE
    assert row["signal_type"] == "BET"            # the verdict is kept
    bound = {p.split(")s")[0] for p in _INSERT_SQL.split("%(")[1:]}
    assert set(row) == bound


def test_the_nfl_lane_reads_both_pause_sources_like_the_scorer(paused, monkeypatch):
    """pick_writer cannot import models.scorer (nfl/models shadows it), so it
    reads config.PAUSED_MODELS and model_auto_pauses itself -- pinned to the
    scorer's answer here."""
    sys.path.insert(0, str(ROOT / "nfl"))
    from live_model import pick_writer as pw

    class _C:
        def execute(self, *a): return self
        def fetchall(self): return [("nfl_live_prop",)]

    monkeypatch.setattr(pw, "_AUTO_PAUSED", None)
    monkeypatch.setattr(config, "PAUSED_MODELS", set())
    assert pw._pause_note("nfl_live_prop") is None
    pw._load_auto_pauses(_C())
    assert pw._pause_note("nfl_live_prop") == NOTE
    paused(auto={"nfl_live_prop"})
    assert scorer._pause_note("nfl_live_prop") == NOTE
    monkeypatch.setattr(pw, "_AUTO_PAUSED", set())
    monkeypatch.setattr(config, "PAUSED_MODELS", {"nfl_live_prop"})
    assert pw._pause_note("nfl_live_prop") == NOTE


def test_the_nfl_lane_loads_the_auto_pauses_before_each_write():
    src = _src("nfl/live_model/pick_writer.py")
    assert src.count("_load_auto_pauses(conn)\n            row = build_pick(") == 2


def test_the_golf_builder_marks_a_paused_bet(paused, monkeypatch):
    mid = "golf_top20"
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, mid, 0.01)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", {mid: 0.0})
    args = dict(game_id="GOLF_X", model_id=mid, game_date="2026-10-01",
                player_name="A B", model_prob=0.30, dk_implied_prob=0.25,
                edge=0.05, dk_odds=300.0, bankroll=1000.0, label="A B Top 20",
                player_id="1")
    assert scorer._make_golf_pick(**args)["downgrade_reason"] is None
    paused(mid)
    pick = scorer._make_golf_pick(**args)
    assert pick["signal_type"] == "BET" and pick["downgrade_reason"] == NOTE


def test_the_prob_only_builders_mark_a_paused_bet(paused, monkeypatch):
    mid = "mlb_f5_moneyline"
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", False)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", {mid: 0.5})
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", {mid: 0.01})
    monkeypatch.setattr(scorer, "_build_injury_flag", lambda *a: (None, None))
    paused(mid)
    picks = scorer._score_f5_prob_only(
        "G", mid, "MLB", "2026-10-01", "h2h_1st_5_innings", "H", "A",
        0.60, 0.40, {}, 1000.0, True, None)
    assert picks and all(p["downgrade_reason"] == NOTE for p in picks)
    for market in ("spreads_1st_5_innings",):
        picks = scorer._score_f5_prob_only(
            "G", mid, "MLB", "2026-10-01", market, "H", "A",
            0.60, 0.40, {}, 1000.0, True, None)
        assert picks and all(p["downgrade_reason"] == NOTE for p in picks)
    mid = "ufc_totals"
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", {mid: 0.5})
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", {mid: 0.01})
    paused(mid)
    picks = scorer._score_ufc_totals_prob_only(
        None, "U", mid, "UFC", "2026-10-01", "H", "A", 0.6, 0.4,
        {"total_line": 2.5}, {}, 1000.0, True, None)
    assert picks and picks[0]["downgrade_reason"] == NOTE


def test_this_file_is_on_the_pr_ci_subset():
    assert "tests/test_paused_marker_writers.py" in _src(".github/workflows/pr-ci.yml")


# ── the internal counters leave the paused row out too ───────────────────────

def test_model_quality_reads_no_paused_row():
    from tracking import model_quality as mq
    assert mq._PAUSED == config.paused_row_exclusion_sql("p")
    for name in ("_OPEN_BET_SQL", "_SETTLED_BET_SQL", "_VOLUME_HISTORY_SQL"):
        assert "{paused}" in getattr(mq, name), name
    src = _src("tracking/model_quality.py")
    assert "_OPEN_BET_SQL.format(paused=_PAUSED)" in src
    assert "_SETTLED_BET_SQL.format(excl=excl, paused=_PAUSED)" in src
    assert "_VOLUME_HISTORY_SQL.format(paused=_PAUSED)" in src


def test_the_ops_dashboard_signal_counts_skip_the_paused_row():
    src = _src("monitoring/store.py")
    for fn in ("def pick_counts(", "def picks_over_time("):
        body = src.split(fn)[1].split("\ndef ")[0]
        assert "downgrade_reason IS DISTINCT FROM 'model paused'" in body, fn
    assert NOTE == "model paused"


def test_the_paper_summary_skips_the_paused_row_and_sizes_like_the_scorer():
    body = _src("tracking/paper_tracker.py").split(
        "def print_performance_summary(")[1].split("\ndef ")[0]
    assert body.count('{paused_row_exclusion_sql("picks")}') == 3
    assert "_get_current_bankroll(conn)" in body


def test_the_paper_summary_bankroll_is_the_scorers(monkeypatch):
    """The bankroll the summary prints is the one every model sizes from."""
    from tracking import paper_tracker as pt

    class _C:
        def execute(self, sql, params=None):
            self.sql = sql
            return self
        def fetchone(self):
            return (0, 0, 0, 0, 0, 0, 0, 0) if "COUNT(*)" in self.sql else None
        def fetchall(self):
            return []
        def close(self):
            pass

    monkeypatch.setattr(pt, "get_connection", lambda: _C())
    seen = []
    monkeypatch.setattr(pt, "_get_current_bankroll", lambda c: seen.append(c) or 1234.0)
    pt.print_performance_summary(days=7)
    assert len(seen) == 1


def test_the_model_screen_lists_no_paused_bet_as_todays_pick():
    src = _src("mobile/src/screens/BuiltInModelDetailScreen.tsx")
    block = src.split("const todayPicks = useMemo(")[1].split("[todayRows, modelId]")[0]
    assert "!isPausedRow(d.pick)" in block
