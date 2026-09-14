"""Game-model injury gate: timestamped, fail-open, not a feature.

The clock is the whole product. A starter/star Out before the quote
suppresses the BET; news after the line must not. Healthy / unknown /
Questionable fail open. Tests FAILED against a version that vetoed on
status alone and against one that used `>` instead of `<=`.
"""
from __future__ import annotations

from pathlib import Path

from data.ingestors.nfl_props_data_ingestor import norm_player_name
from models.game_injury_gate import (
    GOALIE_STATUSES,
    PITCHER_STATUSES,
    STAR_STATUSES,
    apply_to_picks,
    load_sport_injury_index,
    player_matches_veto,
    relevant_players,
    stars_from_logs,
    veto_reason,
)
from models.nfl_prop_injury_veto import should_veto

STATUS_TS = "2026-09-13T18:00:00Z"
QUOTE_AFTER = "2026-09-13T19:00:00Z"
QUOTE_BEFORE = "2026-09-13T17:00:00Z"


def _idx(status, status_ts=STATUS_TS, player="Gerrit Cole"):
    return {norm_player_name(player): [
        {"status": status, "status_ts": status_ts, "player_name": player}
    ]}


def _relevant(player="Gerrit Cole", role="NYY starter", statuses=PITCHER_STATUSES):
    return [{"player_name": player, "role": role, "statuses": statuses}]


def _bet(label="NYY ML"):
    return {
        "signal_type": "BET", "pick_label": label,
        "kelly_fraction": 0.03, "recommended_bet": 30.0,
        "downgrade_reason": None,
    }


def test_pitcher_out_before_quote_vetoes():
    assert should_veto("Out", STATUS_TS, QUOTE_AFTER, statuses=PITCHER_STATUSES)
    reason = veto_reason(QUOTE_AFTER, _relevant(), _idx("Out"))
    assert reason is not None
    assert "Gerrit Cole" in reason
    picks = [_bet()]
    diag = apply_to_picks(picks, QUOTE_AFTER, _relevant(), _idx("Out"))
    assert picks[0]["signal_type"] == "NONE"
    assert picks[0]["recommended_bet"] == 0.0
    assert diag["injury_gate"] == 1


def test_pitcher_il_before_quote_vetoes():
    assert should_veto("IL15", STATUS_TS, QUOTE_AFTER, statuses=PITCHER_STATUSES)
    assert veto_reason(QUOTE_AFTER, _relevant(), _idx("IL15"))


def test_pitcher_out_after_quote_does_not_veto():
    """Look-ahead: the scratch did not exist when this line was taken."""
    assert should_veto("Out", STATUS_TS, QUOTE_BEFORE, statuses=PITCHER_STATUSES) is False
    picks = [_bet()]
    diag = apply_to_picks(picks, QUOTE_BEFORE, _relevant(), _idx("Out"))
    assert picks[0]["signal_type"] == "BET"
    assert diag["injury_gate"] == 0


def test_equal_timestamps_veto():
    assert should_veto("Out", STATUS_TS, STATUS_TS, statuses=PITCHER_STATUSES) is True


def test_questionable_and_healthy_fail_open():
    assert should_veto("Questionable", STATUS_TS, QUOTE_AFTER,
                       statuses=PITCHER_STATUSES) is False
    assert should_veto("Day-To-Day", STATUS_TS, QUOTE_AFTER,
                       statuses=PITCHER_STATUSES) is False
    assert veto_reason(QUOTE_AFTER, _relevant(), _idx("Questionable")) is None
    assert veto_reason(QUOTE_AFTER, _relevant(), {}) is None
    picks = [_bet()]
    apply_to_picks(picks, QUOTE_AFTER, _relevant(), {})
    assert picks[0]["signal_type"] == "BET"


def test_missing_clocks_fail_open():
    assert should_veto("Out", None, QUOTE_AFTER, statuses=PITCHER_STATUSES) is False
    assert should_veto("Out", STATUS_TS, None, statuses=PITCHER_STATUSES) is False
    picks = [_bet()]
    apply_to_picks(picks, None, _relevant(), _idx("Out"))
    assert picks[0]["signal_type"] == "BET"


def test_nba_star_out_vetoes_doubtful_does_not():
    rel = _relevant("LeBron James", "LAL star", STAR_STATUSES)
    assert veto_reason(QUOTE_AFTER, rel, _idx("Out", player="LeBron James"))
    assert veto_reason(QUOTE_AFTER, rel, _idx("Doubtful", player="LeBron James")) is None


def test_nhl_goalie_doubtful_vetoes():
    rel = _relevant("Sergei Bobrovsky", "FLA goalie", GOALIE_STATUSES)
    assert veto_reason(QUOTE_AFTER, rel, _idx("Doubtful", player="Sergei Bobrovsky"))
    assert veto_reason(QUOTE_AFTER, rel, _idx("Questionable", player="Sergei Bobrovsky")) is None


def test_avoid_and_none_are_not_downgraded():
    picks = [
        {**_bet(), "signal_type": "AVOID"},
        {**_bet(), "signal_type": "NONE", "recommended_bet": 0.0},
        _bet(),
    ]
    apply_to_picks(picks, QUOTE_AFTER, _relevant(), _idx("Out"))
    assert picks[0]["signal_type"] == "AVOID"
    assert picks[1]["signal_type"] == "NONE"
    assert picks[2]["signal_type"] == "NONE"


def test_per_pick_quote_clock_wins():
    """Decision-book snapshot on the pick, not a shared DK clock."""
    picks = [_bet()]
    picks[0]["_quote_snapshot_at"] = QUOTE_BEFORE
    apply_to_picks(picks, QUOTE_AFTER, _relevant(), _idx("Out"))
    assert picks[0]["signal_type"] == "BET"


def test_name_normalisation():
    assert player_matches_veto(
        "Gerrit Cole", QUOTE_AFTER, _idx("Out", player="Gerrit Cole"),
        PITCHER_STATUSES)
    assert player_matches_veto(
        "gerritcole", QUOTE_AFTER, _idx("Out", player="Gerrit Cole"),
        PITCHER_STATUSES)


def test_stars_from_logs_takes_top_two_not_the_bench():
    rows = []
    for i, (name, mpg) in enumerate([
        ("Star A", 34.0), ("Star B", 31.0), ("Sixth", 22.0), ("Bench", 12.0),
    ]):
        for d in range(10):
            rows.append({
                "player_id": str(i), "player_name": name, "team": "NY",
                "game_date": f"2026-08-{d+1:02d}", "minutes": mpg,
            })
    stars = stars_from_logs(rows, "NY", "2026-08-20")
    assert stars == ["Star A", "Star B"]
    assert "Sixth" not in stars
    assert "Bench" not in stars


def test_stars_from_logs_empty_when_no_history():
    assert stars_from_logs([], "NY", "2026-08-20") == []


class _InjConn:
    def __init__(self, latest, rows):
        self.latest = latest
        self.rows = rows

    def execute(self, sql, params=None):
        self._last = sql
        return self

    def fetchone(self):
        return (self.latest,)

    def fetchall(self):
        return self.rows


def test_loader_fail_open_on_missing_column():
    assert load_sport_injury_index(None, "MLB") == {}
    boom = _InjConn("2026-09-14", [])
    boom.execute = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no such column"))
    assert load_sport_injury_index(boom, "MLB", "2026-09-14") == {}


def test_loader_keys_by_norm_name():
    conn = _InjConn("2026-09-14", [
        ("Gerrit Cole", "Out", STATUS_TS, "NYY"),
        ("Juan Soto", "Questionable", STATUS_TS, "NYY"),
    ])
    idx = load_sport_injury_index(conn, "MLB", "2026-09-14")
    assert "gerritcole" in idx
    assert idx["gerritcole"][0]["status"] == "Out"


def test_relevant_players_fail_open_without_conn():
    assert relevant_players(None, "MLB", "2026-09-14", "NYY", "BOS") == []
    assert relevant_players(_InjConn(None, []), "NCAAF", "2026-09-14", "a", "b") == []


def test_scorer_applies_the_gate_before_insert():
    src = Path(__file__).parent.parent.joinpath("models/scorer.py").read_text(
        encoding="utf-8")
    assert "def _apply_game_injury_gate" in src
    # Both the binary game path and NHL 3-way call it, before insert.
    assert src.count("_apply_game_injury_gate(conn, picks") >= 2


def test_gate_is_not_an_xgb_column():
    """The product: this is emit-time, not home_starter_out / injury_adj."""
    src = Path(__file__).parent.parent.joinpath(
        "models/game_injury_gate.py").read_text(encoding="utf-8")
    assert "NOT A FEATURE" in src
    feat = Path(__file__).parent.parent.joinpath(
        "features/feature_engine.py").read_text(encoding="utf-8")
    assert "home_starter_out" in feat  # still the trained average; leave it
