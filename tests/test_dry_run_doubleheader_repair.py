"""scripts/dry_run_doubleheader_repair.py: read-only, and its game assignment
and grading behave on small doubleheader fixtures (DET@CLE 2026-09-04 shape)."""
import ast
import re
from pathlib import Path

import pytest

from scripts import dry_run_doubleheader_repair as dr

SCRIPT = Path(dr.__file__)
WRITE = re.compile(r"\b(INSERT|UPDATE|DELETE|MERGE|UPSERT|TRUNCATE|DROP|ALTER|"
                   r"CREATE|GRANT|REVOKE|COPY|REFRESH|VACUUM|CALL)\b", re.I)


def _sql_blobs():
    yield "BETS_SQL", dr.BETS_SQL
    yield "ROWS_SQL", dr.ROWS_SQL
    yield "SID_SQL", dr.SID_SQL
    yield "publish", dr._publish_sql()
    yield "TRACK_RECORD_SQL", dr.TRACK_RECORD_SQL
    yield "PARLAY_SQL", dr.PARLAY_SQL
    yield "RECAP_SQL", dr.RECAP_SQL


@pytest.mark.parametrize("name,sql", list(_sql_blobs()))
def test_every_statement_is_a_select(name, sql):
    body = re.sub(r"--[^\n]*", "", sql).strip()
    assert re.match(r"^(SELECT|WITH)\b", body, re.I), name
    assert ";" not in body.rstrip(";"), f"{name}: one statement only"
    assert not WRITE.search(body), f"{name}: write keyword"


def test_no_write_path_in_the_file():
    src = SCRIPT.read_text()
    tree = ast.parse(src)
    calls = {n.func.attr for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert "commit" not in calls
    assert not calls & {"post", "put", "patch", "delete", "executemany"}
    # Every SQL-looking literal is a SELECT, or the statement that makes the
    # session itself read-only.
    verbs = re.compile(r"^\s*(SELECT|WITH|SET|INSERT|UPDATE|DELETE|MERGE|TRUNCATE|"
                       r"DROP|ALTER|CREATE|GRANT|COPY|REFRESH|BEGIN|COMMIT)\b")
    stmts = [n.value.strip() for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and verbs.match(n.value)]
    assert stmts
    for st in stmts:
        assert (st.upper().startswith(("SELECT", "WITH"))
                or st == "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY"), st[:80]


# ── fixtures ─────────────────────────────────────────────────────────────────

def _dh():
    return {"collapsed_id": "MLB_2026-09-04_DET_CLE", "games": {
        1: {"first_pitch": "2026-09-04T19:14:00+00:00", "end": "2026-09-04T23:00:00+00:00",
            "home_runs": 5, "away_runs": 2, "home_f5": 0, "away_f5": 0,
            "players": {"111": {"innings_pitched": 6.0, "p_strikeouts": 7},
                        "900": {"hits": 1, "walks": 0}}},
        2: {"first_pitch": "2026-09-04T23:45:00+00:00", "end": "2026-09-05T02:35:00+00:00",
            "home_runs": 4, "away_runs": 3, "home_f5": 0, "away_f5": 3,
            "players": {"222": {"innings_pitched": 6.0, "p_strikeouts": 4},
                        "900": {"hits": 0, "walks": 2}}},
    }}


def _bet(**kw):
    b = {"pick_id": 1, "game_id": "MLB_2026-09-04_DET_CLE", "game_date": "2026-09-04",
         "model_id": "mlb_moneyline", "pick_label": "x", "pick_side": "home",
         "decision_odds": -110, "recommended_bet": 100, "scored_line": None,
         "player_id": None, "is_live": False, "result": "WIN", "profit_flat": 90.91,
         "created_at": "2026-09-04T12:00:00+00:00",
         "game_time": "2026-09-04T19:10:00+00:00", "settled_at": None}
    b.update(kw)
    return b


# ── assignment ───────────────────────────────────────────────────────────────

def test_sid_family_still_up_after_game_1_is_game_2():
    d = _dh()["games"]
    s1, e1, s2 = (dr._ts(d[1]["first_pitch"]), dr._ts(d[1]["end"]),
                  dr._ts(d[2]["first_pitch"]))
    fam = {"fam_first": "2026-09-04 20:17:01+00", "fam_last": "2026-09-04 23:40:01+00",
           "board_next": "2026-09-04 23:50:01+00"}
    assert dr.sid_game(fam, s1, e1, s2) == 2


def test_sid_family_gone_before_game_2_is_game_1():
    d = _dh()["games"]
    s1, e1, s2 = (dr._ts(d[1]["first_pitch"]), dr._ts(d[1]["end"]),
                  dr._ts(d[2]["first_pitch"]))
    fam = {"fam_first": "2026-09-04 04:17:01+00", "fam_last": "2026-09-04 18:17:01+00",
           "board_next": "2026-09-04 19:17:01+00"}
    assert dr.sid_game(fam, s1, e1, s2) == 1
    # No later snapshot at all: proves nothing.
    assert dr.sid_game({**fam, "board_next": None}, s1, e1, s2) is None


def test_pitcher_prop_goes_to_the_game_he_pitched():
    a = dr.assign_game(_bet(model_id="mlb_prop_pitcher_k", player_id=222), _dh(), None)
    assert (a.game, a.decided_by, a.confidence) == (2, "pitcher", "high")


def test_pregame_bet_written_between_the_games_is_game_2():
    a = dr.assign_game(_bet(created_at="2026-09-04T23:20:00+00:00"), _dh(), None)
    assert (a.game, a.decided_by) == (2, "created")


def test_bet_written_during_game_1_is_not_evidence_and_is_low_confidence():
    a = dr.assign_game(_bet(created_at="2026-09-04T20:30:00+00:00",
                            game_time="2026-09-04T23:40:00+00:00"), _dh(), None)
    assert (a.game, a.decided_by, a.confidence) == (2, "time", "low")
    assert "in play" in a.note


def test_conflicting_evidence_is_flagged():
    fam = {"fam_first": "2026-09-04 20:17:01+00", "fam_last": "2026-09-04 23:40:01+00",
           "board_next": None}
    a = dr.assign_game(_bet(model_id="mlb_prop_pitcher_k", player_id=111), _dh(), fam)
    assert a.game == 2 and a.decided_by == "sid" and a.conflict


# ── grading (settler math) ───────────────────────────────────────────────────

def test_prop_graded_on_the_assigned_games_box():
    b = _bet(model_id="mlb_prop_pitcher_k", player_id=222, pick_side="under",
             scored_line=5.5, decision_odds=-119)
    res, flat, _ = dr.grade(b, _dh()["games"][2])
    assert res == "WIN" and flat == pytest.approx(84.03, abs=0.01)


def test_player_not_in_that_games_box_is_no_action():
    b = _bet(model_id="mlb_prop_pitcher_k", player_id=222, pick_side="under", scored_line=5.5)
    assert dr.grade(b, _dh()["games"][1])[0] == "NO_ACTION"


def test_pitcher_outs_use_innings_to_outs():
    b = _bet(model_id="mlb_prop_pitcher_outs", player_id=222, pick_side="under",
             scored_line=17.5)
    assert dr.grade(b, _dh()["games"][2])[0] == "LOSS"          # 18 outs


def test_game_line_uses_that_games_final():
    b = _bet(model_id="mlb_moneyline", pick_side="away")
    assert dr.grade(b, _dh()["games"][1])[0] == "LOSS"
    assert dr.grade(b, _dh()["games"][2])[0] == "LOSS"
    assert dr.grade(_bet(pick_side="home"), _dh()["games"][2])[0] == "WIN"


# ── report ───────────────────────────────────────────────────────────────────

def test_report_counts_changes_and_net_units():
    rows = {
        "bets": [
            _bet(pick_id=1, model_id="mlb_prop_pitcher_k", player_id=222,
                 pick_side="under", scored_line=5.5, decision_odds=-119,
                 result="NO_ACTION", profit_flat=0),
            _bet(pick_id=2, pick_side="home", result="WIN", profit_flat=90.91,
                 created_at="2026-09-04T23:20:00+00:00"),
        ],
        "rows": [{"game_id": "MLB_2026-09-04_DET_CLE", "home_score": 5, "away_score": 2}],
        "publish": [{"pick_id": 1, "kind": "discord_signal"}],
        "track_record": [{"pick_id": 1, "counted_now": False}],
    }
    rep = dr.build_report([_dh()], rows)
    by = {r["pick_id"]: r for r in rep["bets"]}
    assert by[1]["corrected"] == "WIN" and by[1]["changes"]
    assert by[1]["discord"] == ["discord_signal"] and by[1]["track_record_eligible"]
    assert by[2]["corrected"] == "WIN" and not by[2]["changes"]
    assert by[2]["row_score_is"] == "G1"
    assert rep["n_changed"] == 1
    assert rep["net_units_change"] == pytest.approx(0.8403, abs=1e-4)
    assert "| 1 |" in dr.markdown(rep)
