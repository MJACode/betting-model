"""Market-handicap features for MLB game lines — as-of, missing, dtype.

The runline/O/U models were fundamentals-only. Ticket/money splits and
line-move already lived in the pipeline (`public_betting`,
`features/market_movement.py`) but never reached the matrix. These tests pin
the leakage rules, the 90/20 RLM encoding Mike handicaps with, and the
#738 dtype coerce so a Decimal/empty public row cannot take down a retrain.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pandas as pd
import pytest

from features.feature_engine import (
    FEATURE_MAP,
    MLB_F5_SPREADS_FEATURES,
    MLB_H2H_FEATURES,
    SPARSE_OK_FEATURES,
    coerce_numeric_features,
    feature_matrix,
    numeric_feature_value,
)
from features.market_handicap import (
    HANDICAP_SPARSE_FEATURES,
    MLB_HANDICAP_GATES_SPREAD,
    MLB_HANDICAP_GATES_TOTAL,
    MLB_HANDICAP_MOVE_SHARED,
    MLB_HANDICAP_SPREAD_FEATURES,
    MLB_HANDICAP_TOTAL_FEATURES,
    PUBLIC_FADE_TICKET_PCT,
    PUBLIC_HEAVY_TICKET_PCT,
    attach_market_handicap,
    build_public_features,
    empty_handicap,
    favorite_side,
    row_is_pregame,
    select_latest_pregame_splits,
)
from features.market_movement import MARKET_MOVEMENT_FEATURES, build_market_features

ROOT = Path(__file__).resolve().parents[1]
COMMENCE = "2026-09-16T23:05:00Z"


def _split(game_id, market, side, ticket, money, snap, commence=COMMENCE,
           first_pitch=None):
    return {
        "game_id": game_id, "market": market, "side": side,
        "ticket": ticket, "money": money,
        "public_bet_pct": ticket, "public_money_pct": money,
        "snapshot_at": snap, "commence_time": commence,
        "first_pitch_at": first_pitch, "book": "consensus",
    }


# ── wiring ───────────────────────────────────────────────────────────────────

def test_movement_names_are_the_existing_module_not_a_fork():
    """Do not invent a second odds join. The move/sharp columns are the ones
    market_movement.py already computes."""
    for name in MLB_HANDICAP_MOVE_SHARED:
        assert name in MARKET_MOVEMENT_FEATURES
    assert "mkt_spread_move" in MARKET_MOVEMENT_FEATURES
    assert "mkt_total_move" in MARKET_MOVEMENT_FEATURES


def test_runline_and_ou_lists_include_the_handicap_block():
    for col in MLB_HANDICAP_SPREAD_FEATURES:
        assert col in FEATURE_MAP["mlb_runline"], col
    for col in MLB_HANDICAP_TOTAL_FEATURES:
        assert col in FEATURE_MAP["mlb_over_under"], col


def test_moneyline_and_f5_do_not_silently_pick_up_the_block():
    """Live mlb_moneyline artifact is not this change. F5 public splits do not
    exist (Action Network is full-game only)."""
    for col in HANDICAP_SPARSE_FEATURES:
        assert col not in MLB_H2H_FEATURES
        assert col not in FEATURE_MAP["mlb_moneyline"]
        assert col not in FEATURE_MAP["mlb_f5_moneyline"]
        assert col not in MLB_F5_SPREADS_FEATURES
        assert col not in FEATURE_MAP["mlb_f5_runline"]
        assert col not in FEATURE_MAP["mlb_f5_over_under"]


def test_every_handicap_column_is_sparse_ok():
    """Pre-2026 SBR games have no Action Network row and often no DK move.
    dropna on those columns would delete the matrix — the 2026-08-31 trap
    documented in docs/market_movement_features.md."""
    for col in HANDICAP_SPARSE_FEATURES:
        assert col in SPARSE_OK_FEATURES, col
    # Core runline strength columns stay strict.
    for col in ("d_starter_era", "d_woba", "spread_home", "d_bullpen_era"):
        assert col not in SPARSE_OK_FEATURES


def test_a_row_with_all_handicap_null_survives_dropna():
    cols = FEATURE_MAP["mlb_runline"]
    row = {c: 1.0 for c in cols}
    for c in MLB_HANDICAP_SPREAD_FEATURES:
        row[c] = None
    df = coerce_numeric_features(pd.DataFrame([row]), cols)
    strict = [c for c in cols if c not in SPARSE_OK_FEATURES]
    kept = df.dropna(subset=strict)
    assert len(kept) == 1
    assert pd.isna(kept["pub_fav_rlm"].iloc[0])
    assert pd.isna(kept["mkt_spread_move"].iloc[0])


# ── public encoding / RLM ────────────────────────────────────────────────────

def test_classic_rlm_ninety_tickets_twenty_money_leans_the_dog():
    """Favorite −1.5, 90% tickets / 20% money → pub_fav_rlm = −70 (lean +1.5)."""
    splits = {
        "spreads": {
            "home": {"ticket": 90.0, "money": 20.0},
            "away": {"ticket": 10.0, "money": 80.0},
        }
    }
    out = build_public_features(splits, spread_home=-1.5)
    assert out["pub_home_ticket_pct"] == 90.0
    assert out["pub_home_money_pct"] == 20.0
    assert out["pub_home_rlm"] == -70.0
    assert out["pub_fav_ticket_pct"] == 90.0
    assert out["pub_fav_money_pct"] == 20.0
    assert out["pub_fav_rlm"] == -70.0
    assert out["pub_over_ticket_pct"] is None


def test_favorite_framing_flips_when_home_is_the_dog():
    splits = {
        "spreads": {
            "home": {"ticket": 25.0, "money": 40.0},
            "away": {"ticket": 75.0, "money": 15.0},
        }
    }
    out = build_public_features(splits, spread_home=1.5)
    assert favorite_side(1.5) == "away"
    assert out["pub_fav_ticket_pct"] == 75.0
    assert out["pub_fav_money_pct"] == 15.0
    assert out["pub_fav_rlm"] == -60.0
    # Home-relative columns stay on HOME, not the favorite.
    assert out["pub_home_ticket_pct"] == 25.0
    assert out["pub_home_rlm"] == 15.0


def test_totals_over_rlm_does_not_read_runline_splits():
    splits = {
        "spreads": {"home": {"ticket": 90.0, "money": 20.0}},
        "totals": {"over": {"ticket": 62.0, "money": 41.0}},
    }
    out = build_public_features(splits, spread_home=-1.5)
    assert out["pub_over_ticket_pct"] == 62.0
    assert out["pub_over_money_pct"] == 41.0
    assert out["pub_over_rlm"] == -21.0


def test_missing_public_rows_are_none_not_zero():
    out = build_public_features(None, spread_home=-1.5)
    assert out == empty_handicap() or all(
        out[k] is None for k in (
            "pub_home_ticket_pct", "pub_home_money_pct", "pub_home_rlm",
            "pub_fav_ticket_pct", "pub_fav_money_pct", "pub_fav_rlm",
            "pub_over_ticket_pct", "pub_over_money_pct", "pub_over_rlm",
        )
    )
    assert out["pub_home_ticket_pct"] is None
    assert out["pub_home_rlm"] is None
    assert out["pub_fav_rlm"] is None


def test_ticket_without_money_does_not_invent_rlm():
    splits = {"spreads": {"home": {"ticket": 55.0, "money": None}}}
    out = build_public_features(splits, spread_home=-1.5)
    assert out["pub_home_ticket_pct"] == 55.0
    assert out["pub_home_money_pct"] is None
    assert out["pub_home_rlm"] is None


def test_flat_split_is_zero_rlm_not_none():
    splits = {"spreads": {"home": {"ticket": 50.0, "money": 50.0}}}
    out = build_public_features(splits, spread_home=-1.5)
    assert out["pub_home_rlm"] == 0.0


def test_pickem_spread_does_not_invent_a_favorite():
    assert favorite_side(0) is None
    assert favorite_side(None) is None
    splits = {"spreads": {"home": {"ticket": 55.0, "money": 40.0}}}
    out = build_public_features(splits, spread_home=None)
    assert out["pub_home_ticket_pct"] == 55.0
    assert out["pub_fav_ticket_pct"] is None
    assert out["pub_fav_rlm"] is None


# ── as-of / leakage ──────────────────────────────────────────────────────────

def test_post_start_public_snapshot_is_dropped():
    """Evening refresh snapshot_at is fetch time. After first pitch it is a leak."""
    rows = [
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-09-16T23:30:00Z", commence=COMMENCE),
    ]
    assert select_latest_pregame_splits(rows) == {}


def test_pre_start_public_snapshot_is_kept():
    rows = [
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-09-16T18:00:00Z", commence=COMMENCE),
        _split("g1", "spreads", "away", 10, 80,
               snap="2026-09-16T18:00:00Z", commence=COMMENCE),
    ]
    got = select_latest_pregame_splits(rows)
    assert got["g1"]["spreads"]["home"]["ticket"] == 90.0
    assert got["g1"]["spreads"]["home"]["money"] == 20.0


def test_newer_pregame_snapshot_wins_older_is_not_used():
    rows = [
        _split("g1", "spreads", "home", 60, 55,
               snap="2026-09-16T12:00:00Z"),
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-09-16T18:00:00Z"),
    ]
    got = select_latest_pregame_splits(rows)
    assert got["g1"]["spreads"]["home"]["ticket"] == 90.0


def test_as_of_ceiling_drops_a_snapshot_after_the_tick():
    """Serve-time reconstruction: never read a split written after `as_of`."""
    rows = [
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-09-16T18:00:00Z"),
    ]
    assert select_latest_pregame_splits(
        rows, as_of="2026-09-16T17:00:00Z") == {}
    kept = select_latest_pregame_splits(
        rows, as_of="2026-09-16T19:00:00Z")
    assert kept["g1"]["spreads"]["home"]["ticket"] == 90.0


def test_row_is_pregame_uses_first_pitch_when_believable():
    # First pitch 20 minutes before scheduled start — believe it, drop the snap.
    assert row_is_pregame(
        "2026-09-16T22:55:00Z",
        commence_time="2026-09-16T23:10:00Z",
        first_pitch_at="2026-09-16T22:50:00Z",
    ) is False
    assert row_is_pregame(
        "2026-09-16T22:40:00Z",
        commence_time="2026-09-16T23:10:00Z",
        first_pitch_at="2026-09-16T22:50:00Z",
    ) is True


def test_in_play_open_rows_are_still_bounded_in_the_movement_loader():
    """Both filters: snapshot_type AND snapshot_at. game_id is optional."""
    import inspect
    from features import market_movement
    src = inspect.getsource(market_movement.load_market_movement)
    assert "in_play" in src
    assert "_is_pregame_snapshot" in src
    assert "game_id" in src


def test_public_loader_sql_joins_games_for_the_cutoff():
    import inspect
    from features import market_handicap
    src = inspect.getsource(market_handicap.load_public_splits)
    assert "JOIN games" in src
    assert "commence_time" in src
    assert "first_pitch_at" in src
    assert "select_latest_pregame_splits" in src


# ── dtype (#738) ─────────────────────────────────────────────────────────────

def test_decimal_and_empty_public_pcts_coerce_numeric():
    splits = {
        "spreads": {
            "home": {"ticket": Decimal("90.0"), "money": Decimal("20.5")},
        }
    }
    out = build_public_features(splits, spread_home=Decimal("-1.5"))
    assert out["pub_home_ticket_pct"] == pytest.approx(90.0)
    assert out["pub_home_money_pct"] == pytest.approx(20.5)
    assert out["pub_home_rlm"] == pytest.approx(-69.5)
    assert favorite_side(Decimal("-1.5")) == "home"

    cols = FEATURE_MAP["mlb_runline"]
    row = {c: 1.0 for c in cols}
    row.update(out)
    row["pub_home_ticket_pct"] = Decimal("90.0")
    row["pub_fav_rlm"] = ""
    X = feature_matrix(row, cols)
    assert pd.api.types.is_numeric_dtype(X["pub_home_ticket_pct"])
    assert float(X["pub_home_ticket_pct"].iloc[0]) == pytest.approx(90.0)
    assert pd.isna(X["pub_fav_rlm"].iloc[0])


def test_numeric_feature_value_on_handicap_inputs():
    assert numeric_feature_value(Decimal("55.5")) == pytest.approx(55.5)
    assert numeric_feature_value("") is None
    assert numeric_feature_value(None) is None


# ── attach / train-serve ─────────────────────────────────────────────────────

def test_attach_overlays_movement_and_public_without_clobbering_fundamentals():
    feat = {"d_starter_era": 0.4, "spread_home": -1.5, "game_id": "g1"}
    movement = build_market_features([
        {"book": "draftkings", "snap": "2026-09-16T12:00:00Z",
         "home_price": -110, "away_price": -110,
         "total_line": 8.5, "spread_home": -1.5},
        {"book": "draftkings", "snap": "2026-09-16T18:00:00Z",
         "home_price": -130, "away_price": 110,
         "total_line": 8.5, "spread_home": -1.5},
    ])
    splits = {"spreads": {"home": {"ticket": 90.0, "money": 20.0}}}
    out = attach_market_handicap(
        feat, movement=movement, splits=splits, spread_home=-1.5)
    assert out["d_starter_era"] == 0.4
    assert out["pub_fav_rlm"] == -70.0
    assert out["mkt_move_home_pp"] is not None
    assert out["mkt_spread_move"] == 0.0
    assert out["pub_over_rlm"] is None
    assert out["pub_dog_ticket_pct"] == 10.0
    assert out["pub_dog_rlm"] == 70.0
    assert out["pub_home_present"] == 1.0
    assert out["mkt_move_present"] == 1.0
    assert out["pub_fade_public_fav"] == 1.0
    assert out["pub_home_public_steam"] == 1.0
    assert out["pub_home_rlm_flag"] == 0.0


def test_attach_with_nothing_fills_none_not_zero():
    out = attach_market_handicap({"spread_home": -1.5})
    present = {"pub_home_present", "mkt_move_present",
               "pub_over_present", "mkt_total_move_present"}
    for col in MLB_HANDICAP_SPREAD_FEATURES:
        if col in present:
            assert out[col] == 0.0, col
        else:
            assert out[col] is None, col


def test_train_and_score_builders_call_attach():
    engine = (ROOT / "features" / "feature_engine.py").read_text(encoding="utf-8")
    assert "attach_market_handicap" in engine
    assert "include_handicap" in engine
    assert "load_public_splits" in engine
    assert "load_market_movement_for_game" in engine


def test_runline_sweep_scores_the_artifact_feature_cols():
    """FEATURE_MAP growing must not reshape an old pickle mid-sweep."""
    sweep = (ROOT / "scripts" / "mlb_runline_sweep.py").read_text(encoding="utf-8")
    assert 'artifact.get("feature_cols")' in sweep
    assert "include_handicap" in sweep


def test_over_under_sweep_scores_the_artifact_feature_cols():
    """Same honesty as runline: artifact list wins, handicap lookup follows it."""
    sweep = (ROOT / "scripts" / "mlb_over_under_sweep.py").read_text(
        encoding="utf-8")
    assert 'artifact.get("feature_cols")' in sweep
    assert "include_handicap" in sweep
    assert "feature_matrix" in sweep


def test_ingestor_refuses_post_start_upserts():
    src = (ROOT / "data" / "ingestors" / "public_betting_ingestor.py").read_text(
        encoding="utf-8")
    assert "_is_pregame_snapshot" in src
    assert "first_pitch_at" in src
    assert "keeping last pre-game split" in src
    assert "skipped_started" in src


# ── offset-aware bound (the #740 585 vs 101 gap) ─────────────────────────────

def test_offset_aware_public_snapshot_after_utc_commence_is_dropped():
    """16:00-04:00 is 20:00Z. commence 17:36Z. Text compare would keep it."""
    rows = [
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-05-31T16:00:00-04:00",
               commence="2026-05-31T17:36:00+00:00"),
    ]
    assert select_latest_pregame_splits(rows) == {}


def test_offset_aware_public_snapshot_before_utc_commence_is_kept():
    rows = [
        _split("g1", "spreads", "home", 90, 20,
               snap="2026-05-31T12:00:00-04:00",
               commence="2026-05-31T17:36:00+00:00"),
    ]
    got = select_latest_pregame_splits(rows)
    assert got["g1"]["spreads"]["home"]["ticket"] == 90.0


# ── richer gated / interaction columns ───────────────────────────────────────

def test_rich_features_are_on_the_runline_and_ou_lists():
    for col in MLB_HANDICAP_GATES_SPREAD:
        assert col in FEATURE_MAP["mlb_runline"], col
        assert col in SPARSE_OK_FEATURES, col
    for col in MLB_HANDICAP_GATES_TOTAL:
        assert col in FEATURE_MAP["mlb_over_under"], col
        assert col in SPARSE_OK_FEATURES, col
    assert "pub_dog_ticket_pct" in FEATURE_MAP["mlb_runline"]
    assert "pub_dog_ticket_pct" not in FEATURE_MAP["mlb_over_under"]
    assert "pub_over_rlm_x_move" not in FEATURE_MAP["mlb_runline"]
    assert "pub_home_rlm_x_move" not in FEATURE_MAP["mlb_moneyline"]


def test_public_steam_and_rlm_flags_gate_on_both_inputs():
    """Tickets without a move is not 0-steam — it is unknown."""
    splits = {"spreads": {"home": {"ticket": 90.0, "money": 20.0}}}
    no_move = attach_market_handicap(
        {"spread_home": -1.5}, splits=splits, spread_home=-1.5)
    assert no_move["pub_home_ticket_pct"] == 90.0
    assert no_move["pub_home_present"] == 1.0
    assert no_move["mkt_move_present"] == 0.0
    assert no_move["pub_home_public_steam"] is None
    assert no_move["pub_home_rlm_flag"] is None
    assert no_move["pub_home_rlm_x_move"] is None
    assert no_move["pub_fade_public_fav"] == 1.0
    assert PUBLIC_FADE_TICKET_PCT == 65.0
    assert PUBLIC_HEAVY_TICKET_PCT == 55.0


def test_rlm_x_move_and_steam_when_line_fades_the_public():
    """90% tickets on home, line moves AWAY from home → RLM flag, not steam."""
    movement = build_market_features([
        {"book": "draftkings", "snap": "2026-09-16T12:00:00Z",
         "home_price": -140, "away_price": 120,
         "total_line": 8.5, "spread_home": -1.5},
        {"book": "draftkings", "snap": "2026-09-16T18:00:00Z",
         "home_price": -110, "away_price": -110,
         "total_line": 8.0, "spread_home": -1.5},
    ])
    splits = {
        "spreads": {"home": {"ticket": 90.0, "money": 20.0}},
        "totals": {"over": {"ticket": 70.0, "money": 40.0}},
    }
    out = attach_market_handicap(
        {"spread_home": -1.5}, movement=movement, splits=splits,
        spread_home=-1.5)
    assert out["mkt_move_home_pp"] < 0
    assert out["pub_home_public_steam"] == 0.0
    assert out["pub_home_rlm_flag"] == 1.0
    assert out["pub_fav_rlm_flag"] == 1.0
    assert out["pub_home_rlm_x_move"] == pytest.approx(
        (-70.0) * out["mkt_move_home_pp"], rel=1e-4)
    assert out["mkt_total_move"] == -0.5
    assert out["pub_over_public_steam"] == 0.0
    assert out["pub_over_rlm_flag"] == 1.0
    assert out["pub_over_rlm_x_move"] == pytest.approx((-30.0) * -0.5)
    assert out["mkt_total_steamed"] == 1.0
    assert out["mkt_steam_home"] == 0.0


def test_favorite_signed_move_flips_when_home_is_the_dog():
    movement = build_market_features([
        {"book": "draftkings", "snap": "2026-09-16T12:00:00Z",
         "home_price": -110, "away_price": -110,
         "total_line": 8.5, "spread_home": 1.5},
        {"book": "draftkings", "snap": "2026-09-16T18:00:00Z",
         "home_price": -140, "away_price": 120,
         "total_line": 8.5, "spread_home": 1.5},
    ])
    splits = {
        "spreads": {
            "home": {"ticket": 25.0, "money": 40.0},
            "away": {"ticket": 75.0, "money": 15.0},
        }
    }
    out = attach_market_handicap(
        {"spread_home": 1.5}, movement=movement, splits=splits,
        spread_home=1.5)
    assert out["mkt_move_home_pp"] > 0
    # Away is the fav; home steamed, so fav-signed move is negative.
    assert out["pub_fav_public_steam"] == 0.0
    assert out["pub_fav_rlm_flag"] == 1.0
    assert out["pub_dog_ticket_pct"] == 25.0
    assert out["pub_home_public_steam"] == 0.0  # 25% tickets, not heavy


def test_rich_columns_coerce_numeric_like_738():
    cols = FEATURE_MAP["mlb_runline"]
    row = {c: 1.0 for c in cols}
    row["pub_home_rlm_x_move"] = Decimal("-12.5")
    row["pub_home_public_steam"] = ""
    X = feature_matrix(row, cols)
    assert pd.api.types.is_numeric_dtype(X["pub_home_rlm_x_move"])
    assert float(X["pub_home_rlm_x_move"].iloc[0]) == pytest.approx(-12.5)
    assert pd.isna(X["pub_home_public_steam"].iloc[0])
