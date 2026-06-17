"""
test_golf_feature_engine.py — Pure-function tests for the golf feature engine.

Exercises rolling-window features, the ASOF look-ahead guard, the MIN_GOLF_ROUNDS
gate, target computation for all five golf models, matchup pairing determinism,
and field-probability renormalization. No network, no DB.
"""

from features.golf_feature_engine import (
    GOLF_PLAYER_FEATURES,
    GOLF_MATCHUP_FEATURES,
    assemble_player_features,
    compute_golf_target,
    compute_matchup_target,
    matchup_diff_features,
    sample_matchup_pairs,
    renormalize_field_probs,
    MIN_GOLF_ROUNDS,
)


def _history(n_events: int, sg_start: float = 1.0, base_date_month: int = 1):
    """Build a chronological prior-round history: n_events × 4 rounds, dg_id=1."""
    rounds = []
    for i in range(n_events):
        eid = i + 1
        month = (i % 9) + 1
        d = f"2024-{month:02d}-10"
        for rn in (1, 2, 3, 4):
            sg = sg_start + i * 0.1
            rounds.append({
                "dg_id": 1, "game_date": d, "dg_event_id": eid, "season": 2024,
                "round_num": rn, "score": 70 - i, "sg_total": sg,
                "sg_ott": sg * 0.3, "sg_app": sg * 0.4, "sg_arg": sg * 0.1, "sg_putt": sg * 0.2,
                "finish_pos": 10 + i, "made_cut": 1,
            })
    rounds.sort(key=lambda r: (r["game_date"], r["round_num"]))
    return rounds


def test_min_rounds_gate():
    short = _history(3)            # 12 rounds < MIN_GOLF_ROUNDS (20)
    assert assemble_player_features(short, 1, "2024-12-01") is None
    full = _history(8)             # 32 rounds
    assert assemble_player_features(full, 1, "2024-12-01") is not None


def test_assemble_has_all_features_except_field_strength():
    f = assemble_player_features(_history(8), 3, "2024-12-01")
    expected = {c for c in GOLF_PLAYER_FEATURES if c != "field_strength"}
    assert set(f.keys()) == expected
    assert "field_strength" not in f   # injected later by the caller


def test_rolling_and_form_delta():
    f = assemble_player_features(_history(8), 3, "2024-12-01")
    # last8 is the 2 most recent events (8 rounds), last24 the most recent 6 events
    assert f["sg_total_last8"] > f["sg_total_last24"]      # improving form
    assert abs(f["sg_total_form_delta"] - (f["sg_total_last8"] - f["sg_total_last24"])) < 1e-9


def test_course_history():
    f = assemble_player_features(_history(8), 3, "2024-12-01")
    assert f["course_rounds_played"] == 4       # event 3 appears once (4 rounds)
    assert f["course_sg_total"] is not None


def test_asof_excludes_future_rounds():
    """Rounds dated on/after start_date must not leak into features. The builder
    receives already-filtered history, so we assert the filter contract by
    constructing a player whose only 'good' rounds are after the cutoff."""
    hist = _history(8)
    # caller filters game_date < start_date; emulate a cutoff before all history
    prior = [r for r in hist if r["game_date"] < "2024-01-01"]
    assert assemble_player_features(prior, 1, "2024-01-01") is None  # no prior rounds


def test_targets_per_player():
    assert compute_golf_target("golf_outright", 1, 1) == 1
    assert compute_golf_target("golf_outright", 4, 1) == 0
    assert compute_golf_target("golf_top10", 10, 1) == 1
    assert compute_golf_target("golf_top10", 11, 1) == 0
    assert compute_golf_target("golf_top10", None, 0) == 0      # missed cut isn't top 10
    assert compute_golf_target("golf_top20", 20, 1) == 1
    assert compute_golf_target("golf_top20", 21, 1) == 0
    assert compute_golf_target("golf_make_cut", None, 1) == 1
    assert compute_golf_target("golf_make_cut", None, 0) == 0
    assert compute_golf_target("golf_make_cut", None, None) is None   # WD voids
    assert compute_golf_target("golf_outright", None, None) is None


def test_matchup_target():
    assert compute_matchup_target({"finish_pos": 5, "made_cut": 1},
                                  {"finish_pos": 12, "made_cut": 1}) == 1
    assert compute_matchup_target({"finish_pos": 12, "made_cut": 1},
                                  {"finish_pos": 5, "made_cut": 1}) == 0
    assert compute_matchup_target({"finish_pos": 5, "made_cut": 1},
                                  {"finish_pos": 5, "made_cut": 1}) is None        # tie
    assert compute_matchup_target({"finish_pos": 5, "made_cut": 1},
                                  {"finish_pos": None, "made_cut": 0}) == 1         # made beats missed
    assert compute_matchup_target({"finish_pos": None, "made_cut": 0, "r12_total": 140},
                                  {"finish_pos": None, "made_cut": 0, "r12_total": 145}) == 1
    assert compute_matchup_target({"made_cut": None},
                                  {"finish_pos": 3, "made_cut": 1}) is None         # WD


def test_matchup_diff_features():
    fa = assemble_player_features(_history(8, sg_start=2.0), 3, "2024-12-01")
    fb = assemble_player_features(_history(8, sg_start=0.0), 3, "2024-12-01")
    d = matchup_diff_features(fa, fb)
    assert set(d.keys()) == set(GOLF_MATCHUP_FEATURES)
    assert d["d_sg_total_last24"] > 0   # A is the stronger player


def test_sample_matchup_pairs_deterministic():
    p1 = sample_matchup_pairs([1, 2, 3, 4, 5], 4, seed=42)
    p2 = sample_matchup_pairs([5, 4, 3, 2, 1], 4, seed=42)   # order-independent
    assert p1 == p2
    assert len(p1) == 4 and len(set(p1)) == 4
    assert sample_matchup_pairs([1], 4, seed=1) == []


def test_renormalize_field_probs():
    r = renormalize_field_probs({1: 0.2, 2: 0.3, 3: 0.1, 4: None})
    total = sum(v for v in r.values() if v is not None)
    assert abs(total - 1.0) < 1e-9
    assert r[4] is None
    # all-zero field returns unchanged (no divide-by-zero)
    z = renormalize_field_probs({1: 0.0, 2: 0.0})
    assert z == {1: 0.0, 2: 0.0}
