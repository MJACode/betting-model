"""
Integration tests: the WNBA prop engine's v2 context wiring.

Builds a fake bulk dict shaped exactly like build_bulk_wnba_prop_lookups
output and drives _build_player_row through it — no DB. The backward-compat
test matters most: v1 models keep byte-identical rows when the bulk dict lacks
the new indexes.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from features.wnba_prop_feature_engine import (  # noqa: E402
    CONTEXT_FEATURES,
    PROP_PLAYER_POINTS_V2_FEATURES,
    _build_player_row,
    _context_features_for,
)


def _log(pid, team, date, minutes, pts=10, fga=8, fta=2, season=2026):
    return {
        "player_id": pid, "player_name": f"Player {pid}", "team": team,
        "game_id": f"WNBA_{date}_{team}", "game_date": date, "season": season,
        "minutes": minutes, "is_starter": None, "points": pts, "rebounds": 5,
        "assists": 3, "steals": 1, "blocks": 0, "turnovers": 2,
        "fg3_made": 1, "fg3": 1, "pra": pts + 8, "fg_att": fga, "ft_att": fta,
    }


def _fake_bulk(n_games=8):
    """A 6-player LV rotation over n_games; p6 sits under the 15-min bar."""
    player_logs, team_logs, presence, games = {}, {}, {}, {}
    pids = ["p1", "p2", "p3", "p4", "p5", "p6"]
    for g in range(n_games):
        date = f"2026-06-{g + 1:02d}"
        gid = f"WNBA_{date}_LV"
        games[gid] = {"home_team": "LV", "away_team": "SEA", "game_date": date}
        for i, pid in enumerate(pids):
            row = _log(pid, "LV", date, minutes=32 - i * 4)
            row["game_id"] = gid
            player_logs.setdefault(pid, ([], []))
            player_logs[pid][0].append(date)
            player_logs[pid][1].append(row)
            team_logs.setdefault("LV", []).append(row)
            presence.setdefault((gid, "LV"), set()).add(pid)
    return dict(player_logs=player_logs, team_stats={}, games=games,
                team_logs=team_logs, presence=presence)


def test_v2_feature_list_extends_v1():
    for c in CONTEXT_FEATURES:
        assert c in PROP_PLAYER_POINTS_V2_FEATURES
    # and no accidental duplicates
    assert len(PROP_PLAYER_POINTS_V2_FEATURES) == len(set(PROP_PLAYER_POINTS_V2_FEATURES))


def test_context_features_appear_on_built_rows():
    bulk = _fake_bulk()
    date = "2026-06-08"
    gid = f"WNBA_{date}_LV"
    log = [r for r in bulk["player_logs"]["p3"][1] if r["game_date"] == date][0]
    row = _build_player_row(bulk, "p3", "Player p3", "LV", gid, date, 2026, log_row=log)
    assert row is not None
    for c in CONTEXT_FEATURES:
        assert c in row, f"missing context feature {c}"
    assert row["rotation_rank"] == 3
    assert row["is_starter_tier"] == 1
    assert row["teammates_out"] == 0            # full box-score presence
    assert row["target_minutes"] == log["minutes"]


def test_absent_teammate_is_counted_from_box_presence():
    bulk = _fake_bulk()
    date = "2026-06-08"
    gid = f"WNBA_{date}_LV"
    bulk["presence"][(gid, "LV")].discard("p1")   # the 32-min player sat
    row = _build_player_row(bulk, "p3", "Player p3", "LV", gid, date, 2026,
                            log_row=bulk["player_logs"]["p3"][1][7])
    assert row["teammates_out"] == 1
    assert row["teammate_minutes_out"] == 32.0
    assert row["top_teammate_out"] == 1


def test_future_game_defaults_to_full_strength():
    """Serve time: no presence row exists yet → zero teammates out, never all."""
    bulk = _fake_bulk()
    feats = _context_features_for(bulk, "p3", "LV", "WNBA_2026-06-20_LV", "2026-06-20")
    assert feats["teammates_out"] == 0


def test_future_game_respects_out_players_list():
    bulk = _fake_bulk()
    bulk["out_players"] = {("LV", "2026-06-20"): {"p1"}}
    feats = _context_features_for(bulk, "p3", "LV", "WNBA_2026-06-20_LV", "2026-06-20")
    assert feats["teammates_out"] == 1
    assert feats["teammate_minutes_out"] == 32.0


def test_bulk_without_new_indexes_is_backward_compatible():
    """A v1-shaped bulk dict (no team_logs) must produce NO context keys."""
    bulk = _fake_bulk()
    del bulk["team_logs"]
    del bulk["presence"]
    date = "2026-06-08"
    gid = f"WNBA_{date}_LV"
    log = [r for r in bulk["player_logs"]["p3"][1] if r["game_date"] == date][0]
    row = _build_player_row(bulk, "p3", "Player p3", "LV", gid, date, 2026, log_row=log)
    assert row is not None
    for c in CONTEXT_FEATURES:
        assert c not in row


def test_rotation_cache_is_shared_across_players():
    bulk = _fake_bulk()
    date = "2026-06-08"
    gid = f"WNBA_{date}_LV"
    _context_features_for(bulk, "p1", "LV", gid, date)
    assert ("LV", date) in bulk["_rotation_cache"]
    cached = bulk["_rotation_cache"][("LV", date)]
    _context_features_for(bulk, "p2", "LV", gid, date)
    assert bulk["_rotation_cache"][("LV", date)] is cached


def test_usage_features_use_only_prior_games():
    bulk = _fake_bulk()
    date = "2026-06-01"                          # first game: no prior history
    gid = f"WNBA_{date}_LV"
    feats = _context_features_for(bulk, "p3", "LV", gid, date)
    assert feats["fga_last3_avg"] is None
    assert feats["ts_pct"] is None
