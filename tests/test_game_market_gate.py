"""Market-relative gate for MLB game picks.

Pins the four properties the overlay is for:

  * no BET when no-vig edge is below the floor
  * BET (CLEAR) when the edge is there and the line has not run through us
  * explicit PASS when the market has already steamed through the model
  * a snapshot after as_of (the close, or any later tick) cannot become the
    opener — that is the leak the rest of this repo paid for once already
"""
from __future__ import annotations

import pytest

from models import game_market_gate as gmg


def _h2h(home, away, snap="2026-09-15T16:00:00Z", book="draftkings"):
    return {"home_price": home, "away_price": away, "snapshot_at": snap,
            "book": book, "snap": snap}


def _tot(over, under, line, snap="2026-09-15T16:00:00Z"):
    return {"over_price": over, "under_price": under, "total_line": line,
            "snapshot_at": snap, "book": "draftkings", "snap": snap}


def _spread(home_px, away_px, line, snap="2026-09-15T16:00:00Z"):
    return {"home_price": home_px, "away_price": away_px, "spread_home": line,
            "snapshot_at": snap, "book": "draftkings", "snap": snap}


# ── no-vig edge floor ────────────────────────────────────────────────────────

def test_no_bet_when_no_vig_edge_is_below_the_floor():
    # Home -150 / away +130 → no-vig home ≈ 0.580. Model 0.59 is only +1pp.
    current = gmg.bookend_from_odds(_h2h(-150, 130), "home", "h2h")
    v = gmg.evaluate(model_prob=0.59, side="home", market="h2h",
                     current=current, min_no_vig_edge=0.02)
    assert v.verdict == gmg.PASS_EDGE
    assert v.no_vig_edge < 0.02
    assert v.market_fair_prob == pytest.approx(0.5797, abs=0.002)


def test_clear_when_no_vig_edge_beats_the_floor():
    current = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    v = gmg.evaluate(model_prob=0.58, side="home", market="h2h",
                     current=current, min_no_vig_edge=0.02)
    assert v.verdict == gmg.CLEAR
    assert v.no_vig_edge == pytest.approx(0.08, abs=0.001)
    assert v.market_fair_prob == pytest.approx(0.5)


def test_missing_two_way_is_fail_open_not_a_fake_fair():
    current = gmg.bookend_from_odds(
        {"home_price": -150, "away_price": None, "snapshot_at": "t"},
        "home", "h2h")
    v = gmg.evaluate(model_prob=0.70, side="home", market="h2h",
                     current=current, min_no_vig_edge=0.02)
    assert v.verdict == gmg.NO_TWO_WAY
    assert v.market_fair_prob is None
    assert v.no_vig_edge is None


# ── steamed through — no chase ───────────────────────────────────────────────

def test_pass_when_juice_has_already_moved_through_the_model():
    """Model 0.55. Opened -110 (fair 0.50) — there was value. Now -150 /
    +130 (no-vig home ≈ 0.580) which is PAST the model. Chasing is -EV."""
    opening = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    current = gmg.bookend_from_odds(_h2h(-150, 130), "home", "h2h")
    v = gmg.evaluate(model_prob=0.55, side="home", market="h2h",
                     current=current, opening=opening, min_no_vig_edge=0.0)
    assert v.verdict == gmg.PASS_STEAMED
    assert v.steamed is True
    assert v.open_fair_prob == pytest.approx(0.5)
    assert v.market_fair_prob > 0.55


def test_a_move_that_has_not_reached_the_model_is_not_a_chase():
    """Open -110 (0.50), now -115 (~0.535), model 0.58 — value remains."""
    opening = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    current = gmg.bookend_from_odds(_h2h(-115, -105), "home", "h2h")
    v = gmg.evaluate(model_prob=0.58, side="home", market="h2h",
                     current=current, opening=opening, min_no_vig_edge=0.02)
    assert v.verdict == gmg.CLEAR
    assert v.steamed is False


def test_totals_pass_when_the_number_moved_against_the_over():
    opening = gmg.bookend_from_odds(_tot(-110, -110, 8.5), "over", "totals")
    current = gmg.bookend_from_odds(_tot(-110, -110, 8.0), "over", "totals")
    v = gmg.evaluate(model_prob=0.56, side="over", market="totals",
                     current=current, opening=opening, min_no_vig_edge=0.02)
    assert v.verdict == gmg.PASS_STEAMED


def test_totals_under_does_not_pass_when_the_line_dropped():
    """Under 8.5 became Under 8.0 — that is a BETTER number for the under, not a chase."""
    opening = gmg.bookend_from_odds(_tot(-110, -110, 8.5), "under", "totals")
    current = gmg.bookend_from_odds(_tot(-110, -110, 8.0), "under", "totals")
    v = gmg.evaluate(model_prob=0.56, side="under", market="totals",
                     current=current, opening=opening, min_no_vig_edge=0.02)
    assert v.verdict == gmg.CLEAR
    assert v.steamed is False


def test_runline_home_steams_when_the_home_number_gets_worse():
    opening = gmg.bookend_from_odds(_spread(-110, -110, -1.5), "home", "spreads")
    current = gmg.bookend_from_odds(_spread(-110, -110, -2.0), "home", "spreads")
    v = gmg.evaluate(model_prob=0.56, side="home", market="spreads",
                     current=current, opening=opening)
    assert v.verdict == gmg.PASS_STEAMED


def test_no_opener_cannot_look_like_a_steam():
    current = gmg.bookend_from_odds(_h2h(-150, 130), "home", "h2h")
    v = gmg.evaluate(model_prob=0.70, side="home", market="h2h",
                     current=current, opening=None, min_no_vig_edge=0.02)
    assert v.steamed is False
    assert v.verdict == gmg.CLEAR  # 0.70 - 0.58 > 0.02


# ── public steam / RLM hook (Action Network; PCG is the same dataclass) ──────

def test_public_steam_passes_when_tickets_and_the_line_agree():
    opening = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    current = gmg.bookend_from_odds(_h2h(-125, 105), "home", "h2h")
    splits = gmg.PublicSplits(ticket_pct=68.0, money_pct=55.0,
                              source="action_network")
    v = gmg.evaluate(model_prob=0.62, side="home", market="h2h",
                     current=current, opening=opening, splits=splits,
                     min_no_vig_edge=0.02)
    # Fair of -125 is ~0.556, model 0.62 still has edge, but tickets are
    # heavy on home AND the price moved with them → PASS_PUBLIC_STEAM.
    assert v.verdict == gmg.PASS_PUBLIC_STEAM
    assert v.public_steam is True
    assert v.rlm is False


def test_rlm_is_recorded_not_required():
    """Tickets on the away side, price moving toward home — classic RLM.
    We do not require it to CLEAR; we store it so a later cut can use it."""
    opening = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    current = gmg.bookend_from_odds(_h2h(-120, 100), "home", "h2h")
    splits = gmg.PublicSplits(ticket_pct=32.0, source="action_network")
    v = gmg.evaluate(model_prob=0.60, side="home", market="h2h",
                     current=current, opening=opening, splits=splits,
                     min_no_vig_edge=0.02)
    assert v.verdict == gmg.CLEAR
    assert v.rlm is True
    assert v.public_steam is False


def test_missing_splits_do_not_invent_pcg_percentages():
    current = gmg.bookend_from_odds(_h2h(-110, -110), "home", "h2h")
    v = gmg.evaluate(model_prob=0.58, side="home", market="h2h",
                     current=current, splits=None, min_no_vig_edge=0.02)
    assert v.public_steam is False
    assert v.rlm is False
    assert v.verdict == gmg.CLEAR


# ── leak: future close is not an opener ──────────────────────────────────────

def test_a_snapshot_after_as_of_is_not_the_opener():
    """The close (or any later tick) sitting in `odds` must not become open."""
    snaps = [
        _h2h(-110, -110, "2026-09-15T16:00:00Z"),          # real open
        _h2h(-150, 130, "2026-09-15T23:05:00Z"),           # post-as_of / close
    ]
    as_of = "2026-09-15T17:00:00Z"
    opening = gmg.opening_from_snapshots(
        snaps, side="home", market="h2h", as_of=as_of,
        commence="2026-09-15T23:00:00Z")
    assert opening is not None
    assert opening.our_price == -110
    # If the close had leaked in, our_price would be -150.


def test_a_snapshot_after_first_pitch_is_not_the_opener():
    snaps = [
        _h2h(-200, 170, "2026-09-15T23:10:00Z"),           # in-play, labelled open
    ]
    opening = gmg.opening_from_snapshots(
        snaps, side="home", market="h2h",
        as_of="2026-09-16T01:00:00Z",
        commence="2026-09-15T23:00:00Z")
    assert opening is None


def test_as_of_after_the_close_still_cannot_see_the_close_when_commence_bounds():
    snaps = [
        _h2h(-110, -110, "2026-09-15T16:00:00Z"),
        _h2h(-180, 150, "2026-09-15T23:40:00Z"),           # close
    ]
    opening = gmg.opening_from_snapshots(
        snaps, side="home", market="h2h",
        as_of="2026-09-16T04:00:00Z",                      # next-day replay
        commence="2026-09-15T23:00:00Z")
    assert opening is not None
    assert opening.our_price == -110


# ── live vs shadow on a pick dict ────────────────────────────────────────────

def _pick(**kw):
    base = {
        "game_id": "MLB_2026-09-15_NYY_BOS",
        "model_id": "mlb_moneyline",
        "pick_side": "home",
        "pick_label": "BOS ML",
        "model_probability": 0.55,
        "signal_type": "BET",
        "kelly_fraction": 0.03,
        "recommended_bet": 300.0,
        "downgrade_reason": None,
        "public_bet_pct": None,
        "public_money_pct": None,
    }
    base.update(kw)
    return base


def test_live_mode_downgrades_a_steamed_bet():
    pick = _pick()
    opening = _h2h(-110, -110)
    current = _h2h(-150, 130)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="live", min_no_vig_edge=0.0,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "NONE"
    assert pick["kelly_fraction"] == 0.0
    assert pick["downgrade_reason"].startswith("market:")
    assert pick["_market_gate"].applied is True
    assert pick["_market_gate"].verdict == gmg.PASS_STEAMED


def test_live_mode_downgrades_public_steam():
    pick = _pick(model_probability=0.62, public_bet_pct=68.0, public_money_pct=55.0)
    opening = _h2h(-110, -110)
    current = _h2h(-125, 105)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="live", min_no_vig_edge=None,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "NONE"
    assert pick["recommended_bet"] == 0.0
    assert pick["downgrade_reason"].startswith("market:")
    assert pick["_market_gate"].applied is True
    assert pick["_market_gate"].verdict == gmg.PASS_PUBLIC_STEAM


def test_live_mode_does_not_pass_edge_when_the_extra_floor_is_off():
    """MIN_NO_VIG_EDGE unset (production default): a thin no-vig edge is
    still CLEAR. PASS_EDGE is not a live downgrade unless that floor is set."""
    pick = _pick(model_probability=0.59)
    current = _h2h(-150, 130)          # no-vig home ≈ 0.580; edge ≈ +1pp
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=None,
        mode="live", min_no_vig_edge=None,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "BET"
    assert pick["_market_gate"].verdict == gmg.CLEAR
    assert pick["_market_gate"].applied is False


def test_shadow_mode_does_not_change_signal_type():
    pick = _pick()
    opening = _h2h(-110, -110)
    current = _h2h(-150, 130)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="shadow", min_no_vig_edge=0.0,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "BET"
    assert pick["kelly_fraction"] == 0.03
    assert pick.get("downgrade_reason") is None
    assert pick["_market_gate"].applied is False
    assert pick["_market_gate"].verdict == gmg.PASS_STEAMED


def test_live_mode_never_upgrades_a_none():
    pick = _pick(signal_type="NONE", kelly_fraction=0.0, recommended_bet=0.0)
    current = _h2h(-110, -110)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=None,
        mode="live", min_no_vig_edge=0.02,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "NONE"
    assert pick["_market_gate"].verdict == gmg.CLEAR
    assert pick["_market_gate"].applied is False


def test_a_model_not_in_the_set_is_untouched():
    pick = _pick(model_id="nhl_moneyline")
    current = _h2h(-150, 130)
    opening = _h2h(-110, -110)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="live", min_no_vig_edge=0.0,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["signal_type"] == "BET"
    assert "_market_gate" not in pick


def test_existing_downgrade_reason_is_not_overwritten():
    pick = _pick(downgrade_reason="injury: starter out")
    opening = _h2h(-110, -110)
    current = _h2h(-150, 130)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="live", min_no_vig_edge=0.0,
        enabled_models={"mlb_moneyline"},
    )
    assert pick["downgrade_reason"] == "injury: starter out"
    assert pick["_market_gate"].applied is False


def test_persist_writes_the_verdict_and_does_not_need_a_close_column():
    import sqlite3
    from pathlib import Path

    schema = Path(__file__).parent.parent.joinpath("data/db_setup.py").read_text(
        encoding="utf-8")
    # Pull just our CREATE TABLE so this test does not boot the whole schema.
    start = schema.index("CREATE TABLE IF NOT EXISTS game_market_gate")
    end = schema.index("CREATE TABLE IF NOT EXISTS model_registry")
    ddl = schema[start:end]
    db = sqlite3.connect(":memory:")
    db.execute(ddl)
    pick = _pick()
    opening = _h2h(-110, -110)
    current = _h2h(-150, 130)
    gmg.apply_to_picks(
        [pick], market="h2h", current_odds=current, opening_odds=opening,
        mode="shadow", min_no_vig_edge=0.0,
        enabled_models={"mlb_moneyline"},
    )
    gmg.persist(db, [pick], mode="shadow")
    row = db.execute(
        "SELECT verdict, applied, steamed FROM game_market_gate"
    ).fetchone()
    assert row == ("PASS_STEAMED", 0, 1)
    cols = {r[1] for r in db.execute("PRAGMA table_info(game_market_gate)")}
    assert "closing_dk_odds" not in cols
    assert "clv_pct" not in cols


def test_load_opening_odds_drops_rows_after_as_of():
    class _Conn:
        def execute(self, sql, params=None):
            self.sql = sql
            return self
        def fetchall(self):
            return [
                ("2026-09-15T16:00:00Z", "draftkings", -110, -110,
                 None, None, None, None),
                ("2026-09-15T23:40:00Z", "draftkings", -180, 150,
                 None, None, None, None),
            ]
    out = gmg.load_opening_odds(
        _Conn(), "MLB_2026-09-15_NYY_BOS", "h2h",
        as_of="2026-09-15T17:00:00Z",
        commence="2026-09-15T23:00:00Z")
    assert out is not None
    assert out["home_price"] == -110


def test_config_defaults_are_live_on_the_four_mlb_game_models():
    import config
    assert config.GAME_MARKET_GATE_ENABLED is True
    assert config.GAME_MARKET_GATE_MODE == "live"
    assert config.GAME_MARKET_GATE_MIN_NO_VIG_EDGE is None
    assert config.GAME_MARKET_GATE_MODELS <= set(config.MODELS)
    assert config.GAME_MARKET_GATE_MODELS == frozenset({
        "mlb_moneyline", "mlb_runline", "mlb_over_under", "mlb_f5_moneyline",
    })
