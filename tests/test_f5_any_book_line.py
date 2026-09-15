"""F5 totals/spreads score off the first bettable book when DraftKings has none.

mike, 2026-09-15: the "DK does not carry totals_1st_5_innings /
spreads_1st_5_innings" disable was false. Measured that day against production
`odds`: 0 DraftKings rows ever; FanDuel and BetMGM priced 18 of today's games.
The platform decides at the best bettable price, not DK-only.

These pin:

  1. A real FanDuel (or any BEST_LINE book) quote scores F5 O/U and F5 RL.
  2. No real price (missing, or unpriced sbr_consensus synthetic) → skip.
  3. The read is bounded at first pitch and excludes in-play (no future-close
     leak). SCORE_OFF_ANY_BOOK_LINE=0 restores the skip.
  4. mlb_runline / mlb_over_under stay paused; a human CLE -1.5 is not an
     unpause. F5 O/U and F5 RL are paused for leak-era artifacts, not because
     the market is missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from models import scorer
from models.scorer import (
    F5_ANY_BOOK_MARKETS,
    _fallback_game_line_quote,
    _get_scoring_odds,
    _has_real_game_price,
    _make_pick,
    score_game,
)

ROOT = Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _totals_row(line=4.5, over=-110, under=-110, snap="2026-09-15T17:00:00Z"):
    # home_price, away_price, draw_price, spread_home, total_line,
    # over_price, under_price, home_link, away_link, draw_link, over_link,
    # under_link, snapshot_at
    return (None, None, None, None, line, over, under,
            None, None, None, "over-link", "under-link", snap)


def _spreads_row(spread=-0.5, home=-115, away=-105, snap="2026-09-15T17:00:00Z"):
    return (home, away, None, spread, None, None, None,
            "home-link", "away-link", None, None, None, snap)


class _GameOddsConn:
    """execute(sql, params).fetchone(), keyed on the bookmaker the query asks
    for. `rows` maps book -> the 13-tuple _latest_book_game_odds selects."""

    def __init__(self, rows: dict, commence="2026-09-15T23:05:00Z"):
        self.rows = rows
        self.commence = commence
        self.asked: list[str] = []
        self._last = None

    def execute(self, sql, params=None):
        self._last = (" ".join(sql.split()), params or ())
        return self

    def fetchone(self):
        sql, params = self._last
        if "FROM games" in sql:
            return (self.commence,)
        if "FROM odds" not in sql:
            return None
        book = params[2] if len(params) > 2 else None
        self.asked.append(book)
        row = self.rows.get(book)
        if row is None:
            return None
        if "substr(snapshot_at, 1, 19) <=" in sql and len(params) > 3:
            cutoff = str(params[3])[:19]
            snap = str(row[-1])[:19]
            if snap > cutoff:
                return None
        return row

    def fetchall(self):
        return []


@pytest.fixture
def _on(monkeypatch):
    monkeypatch.setattr(scorer, "SCORE_OFF_ANY_BOOK_LINE", True)
    monkeypatch.setattr(scorer, "BEST_LINE_BOOKMAKERS",
                        ["draftkings", "fanduel", "betmgm", "williamhill_us"])


# ── which book sets the F5 line ──────────────────────────────────────────────

def test_fanduel_sets_the_f5_total_when_draftkings_has_none(_on):
    conn = _GameOddsConn({"fanduel": _totals_row(line=4.5, over=-105),
                          "betmgm": _totals_row(line=5.5, over=-120)})
    q = _fallback_game_line_quote(conn, "MLB_2026-09-15_CLE_MIN",
                                  "totals_1st_5_innings",
                                  "2026-09-15T23:05:00")
    assert q["line_book"] == "fanduel" and q["total_line"] == 4.5
    assert q["over_price"] == -105, (
        "config order, NOT the better price — the line is the proposition")


def test_fanduel_sets_the_f5_spread_when_draftkings_has_none(_on):
    conn = _GameOddsConn({"fanduel": _spreads_row(spread=-0.5, home=-115)})
    q = _fallback_game_line_quote(conn, "MLB_2026-09-15_CLE_MIN",
                                  "spreads_1st_5_innings",
                                  "2026-09-15T23:05:00")
    assert q["line_book"] == "fanduel" and q["spread_home"] == -0.5
    assert q["home_price"] == -115


def test_draftkings_is_not_asked_twice(_on):
    conn = _GameOddsConn({"fanduel": _totals_row()})
    _fallback_game_line_quote(conn, "G", "totals_1st_5_innings")
    assert "draftkings" not in conn.asked


def test_unpriced_sbr_synthetic_is_not_a_real_price(_on):
    sbr = _totals_row(over=None, under=None)
    assert not _has_real_game_price(
        dict(zip(scorer._GAME_ODDS_COLS, sbr)), "totals_1st_5_innings")
    conn = _GameOddsConn({"sbr_consensus": sbr})
    assert _fallback_game_line_quote(
        conn, "G", "totals_1st_5_innings") is None


def test_no_bettable_book_is_none_not_a_crash(_on):
    assert _fallback_game_line_quote(
        _GameOddsConn({}), "G", "totals_1st_5_innings") is None


def test_the_flag_off_restores_no_draftkings_no_pick(monkeypatch, _on):
    monkeypatch.setattr(scorer, "SCORE_OFF_ANY_BOOK_LINE", False)
    conn = _GameOddsConn({"fanduel": _totals_row()})
    assert _fallback_game_line_quote(conn, "G", "totals_1st_5_innings") is None
    assert conn.asked == []


def test_full_game_totals_do_not_use_the_f5_fallback(_on):
    conn = _GameOddsConn({"fanduel": _totals_row()})
    assert _fallback_game_line_quote(conn, "G", "totals") is None
    assert conn.asked == []


def test_the_read_is_bounded_and_excludes_in_play(_on):
    conn = _GameOddsConn({"fanduel": _totals_row()})
    _fallback_game_line_quote(conn, "MLB_2026-09-15_CLE_MIN",
                              "totals_1st_5_innings",
                              "2026-09-15T23:05:00")
    sql = conn._last[0]
    assert "snapshot_type != 'in_play'" in sql
    assert "substr(snapshot_at, 1, 19) <=" in sql


def test_a_quote_after_first_pitch_does_not_score(_on):
    """The evening refresh keeps writing `open` rows after first pitch
    (CLAUDE.md section 7). A FanDuel F5 total stamped after first pitch is
    not a pre-game price."""
    conn = _GameOddsConn(
        {"fanduel": _totals_row(snap="2026-09-15T23:40:00Z")},
        commence="2026-09-15T23:05:00Z",
    )
    q = _get_scoring_odds(conn, "MLB_2026-09-15_CLE_MIN",
                          "totals_1st_5_innings")
    assert q is None


def test_scoring_odds_prefers_priced_draftkings(_on):
    conn = _GameOddsConn({
        "draftkings": _totals_row(line=4.5, over=-110),
        "fanduel": _totals_row(line=5.5, over=-105),
    })
    q = _get_scoring_odds(conn, "MLB_2026-09-15_CLE_MIN",
                          "totals_1st_5_innings")
    assert q["line_book"] is None
    assert q["total_line"] == 4.5 and q["over_price"] == -110


def test_scoring_odds_skips_unpriced_sbr_and_takes_fanduel(_on):
    conn = _GameOddsConn({
        "sbr_consensus": _totals_row(over=None, under=None),
        "fanduel": _totals_row(line=4.5, over=-108),
    })
    q = _get_scoring_odds(conn, "MLB_2026-09-15_CLE_MIN",
                          "totals_1st_5_innings")
    assert q["line_book"] == "fanduel" and q["over_price"] == -108


# ── the pick ─────────────────────────────────────────────────────────────────

@pytest.fixture
def _cut(monkeypatch):
    monkeypatch.setattr(config, "MODEL_PROB_THRESHOLDS",
                        {"mlb_f5_over_under": 0.55, "mlb_f5_runline": 0.55},
                        raising=False)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS",
                        {"mlb_f5_over_under": 0.55, "mlb_f5_runline": 0.55})
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS",
                        {"mlb_f5_over_under": 0.05, "mlb_f5_runline": 0.05})
    monkeypatch.setattr(scorer, "MODEL_MIN_ODDS", {})
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(scorer, "MAX_EDGE_CAP", 0.30)
    monkeypatch.setattr(scorer, "REQUIRE_DK_PRICE", True)


def test_a_non_dk_f5_total_pick_keeps_dk_columns_null(_cut):
    p = _make_pick(
        "MLB_2026-09-15_CLE_MIN", "mlb_f5_over_under", "MLB", "2026-09-15",
        pick_side="over", pick_label="Over 4.5",
        model_prob=0.70, dk_implied_prob=0.5238, edge=0.1762,
        dk_odds=-110, bankroll=1000.0, features={},
        scored_line=4.5, line_book="fanduel",
    )
    assert p["line_book"] == "fanduel"
    assert p["dk_odds"] is None
    assert p["decision_book"] == "fanduel"
    assert p["decision_odds"] == -110
    assert p["signal_type"] == "BET"


def test_a_non_dk_f5_spread_pick_keeps_dk_columns_null(_cut):
    p = _make_pick(
        "MLB_2026-09-15_CLE_MIN", "mlb_f5_runline", "MLB", "2026-09-15",
        pick_side="home", pick_label="CLE -0.5 F5",
        model_prob=0.70, dk_implied_prob=0.5349, edge=0.1651,
        dk_odds=-115, bankroll=1000.0, features={},
        scored_line=-0.5, line_book="fanduel",
    )
    assert p["line_book"] == "fanduel"
    assert p["dk_odds"] is None
    assert p["decision_book"] == "fanduel"
    assert p["signal_type"] == "BET"


class _Clf:
    def predict_proba(self, x):
        return [[0.30, 0.70]]


def _mlb_feat():
    return {
        "home_starter_era": 3.50, "away_starter_era": 4.20,
        "home_team": "MIN", "away_team": "CLE", "game_date": "2026-09-15",
        "total_line": 4.5, "spread_home": -0.5,
    }


def test_score_game_fires_f5_ou_when_fanduel_prices_it(monkeypatch, _cut, _on):
    artifact = {"model": _Clf(),
                "feature_cols": ["home_starter_era", "away_starter_era"]}
    monkeypatch.setattr(scorer, "load_model", lambda mid: artifact)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    monkeypatch.setattr(
        scorer, "_fallback_game_line_quote",
        lambda *a, **k: {
            "total_line": 4.5, "over_price": -110, "under_price": -110,
            "spread_home": None, "line_book": "fanduel",
            "over_link": "fd-over", "snapshot_at": "2026-09-15T17:00:00Z",
        })
    monkeypatch.setattr(scorer, "_get_public_betting",
                        lambda *a, **k: {"public_bet_pct": None,
                                         "public_money_pct": None})
    monkeypatch.setattr(scorer, "_stamp_best_game_prices", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_apply_game_injury_gate", lambda *a, **k: None)

    picks = score_game(None, "MLB_2026-09-15_CLE_MIN", "mlb_f5_over_under",
                       _mlb_feat(), bankroll=1000.0, dry_run=True)
    overs = [p for p in picks if p["pick_side"] == "over"]
    assert overs, "a real FanDuel F5 total must produce a pick"
    assert overs[0]["line_book"] == "fanduel"
    assert overs[0]["dk_odds"] is None
    assert overs[0]["dk_bet_link"] is None
    assert overs[0]["scored_line"] == 4.5


def test_score_game_fires_f5_rl_when_fanduel_prices_it(monkeypatch, _cut, _on):
    artifact = {"model": _Clf(),
                "feature_cols": ["home_starter_era", "away_starter_era"]}
    monkeypatch.setattr(scorer, "load_model", lambda mid: artifact)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    monkeypatch.setattr(
        scorer, "_fallback_game_line_quote",
        lambda *a, **k: {
            "spread_home": -0.5, "home_price": -115, "away_price": -105,
            "total_line": None, "line_book": "fanduel",
            "home_link": "fd-home", "snapshot_at": "2026-09-15T17:00:00Z",
        })
    monkeypatch.setattr(scorer, "_get_public_betting",
                        lambda *a, **k: {"public_bet_pct": None,
                                         "public_money_pct": None})
    monkeypatch.setattr(scorer, "_stamp_best_game_prices", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_apply_game_injury_gate", lambda *a, **k: None)

    picks = score_game(None, "MLB_2026-09-15_CLE_MIN", "mlb_f5_runline",
                       _mlb_feat(), bankroll=1000.0, dry_run=True)
    home = [p for p in picks if p["pick_side"] == "home"]
    assert home, "a real FanDuel F5 spread must produce a pick"
    assert home[0]["line_book"] == "fanduel"
    assert home[0]["scored_line"] == -0.5


def test_score_game_skips_f5_when_no_real_price(monkeypatch, _cut, _on):
    artifact = {"model": _Clf(),
                "feature_cols": ["home_starter_era", "away_starter_era"]}
    monkeypatch.setattr(scorer, "load_model", lambda mid: artifact)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: None)
    monkeypatch.setattr(scorer, "_fallback_game_line_quote",
                        lambda *a, **k: None)
    picks = score_game(None, "MLB_2026-09-15_CLE_MIN", "mlb_f5_over_under",
                       _mlb_feat(), bankroll=1000.0, dry_run=True)
    assert picks == []


def test_score_game_skips_unpriced_synthetic_sbr(monkeypatch, _cut, _on):
    artifact = {"model": _Clf(),
                "feature_cols": ["home_starter_era", "away_starter_era"]}
    monkeypatch.setattr(scorer, "load_model", lambda mid: artifact)
    monkeypatch.setattr(
        scorer, "_get_dk_odds",
        lambda *a, **k: {
            "total_line": 4.5, "over_price": None, "under_price": None,
            "spread_home": None, "home_price": None, "away_price": None,
        })
    monkeypatch.setattr(scorer, "_fallback_game_line_quote",
                        lambda *a, **k: None)
    picks = score_game(None, "MLB_2026-09-15_CLE_MIN", "mlb_f5_over_under",
                       _mlb_feat(), bankroll=1000.0, dry_run=True)
    assert picks == []


# ── pause register: full-game runline/O/U stay paused; F5 is paper/paused ──

def test_full_game_runline_and_over_under_stay_paused():
    """No live-artifact §7 cut cleared. A human CLE -1.5 is not mlb_runline."""
    assert "mlb_runline" in config.PAUSED_MODELS
    assert "mlb_over_under" in config.PAUSED_MODELS


def test_f5_ou_and_rl_are_paused_for_the_artifact_not_the_market():
    assert "mlb_f5_over_under" in config.PAUSED_MODELS
    assert "mlb_f5_runline" in config.PAUSED_MODELS
    src = _src("config.py")
    assert "DK does not carry totals_1st_5_innings" not in src
    assert "leak-era" in src or "leak-mismatched" in src


def test_f5_markets_are_the_any_book_set():
    assert F5_ANY_BOOK_MARKETS == {
        "totals_1st_5_innings", "spreads_1st_5_innings"}


def test_the_disable_lie_is_gone_from_the_scorer():
    src = _src("models/scorer.py")
    assert "DK does not carry these at any tier" not in src
    assert "no real DK F5 odds" not in src
    assert "_get_scoring_odds" in src
    assert "_fallback_game_line_quote" in src


def test_known_untrained_no_longer_lists_the_f5_pair():
    from tracking.system_health import KNOWN_UNTRAINED
    assert "mlb_f5_over_under" not in KNOWN_UNTRAINED
    assert "mlb_f5_runline" not in KNOWN_UNTRAINED


def test_action_thresholds_carry_the_f5_pair():
    assert config.ACTION_THRESHOLDS["mlb_f5_over_under"] == {
        "min_prob": 0.65, "min_edge": 0.15}
    assert config.ACTION_THRESHOLDS["mlb_f5_runline"] == {
        "min_prob": 0.65, "min_edge": 0.15}
