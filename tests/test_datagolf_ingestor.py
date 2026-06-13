"""
test_datagolf_ingestor.py — Pure-function tests for the DataGolf ingestor.

These exercise the reshaping of DataGolf JSON payloads into the dict shapes the
DB writers consume (no network, no DB). Fixtures mirror the documented DataGolf
response shapes; if Phase-0 verification reveals different field names, update
the fixtures + parsers together.
"""

from data.ingestors.datagolf_ingestor import (
    normalize_dg_name,
    slugify_golfer,
    event_slug,
    build_game_id,
    is_team_event,
    parse_finish,
    parse_player_list,
    parse_event_list,
    parse_event_rounds,
    parse_field_update,
    parse_outright_odds,
    parse_matchup_odds,
)


# ── name + slug helpers ───────────────────────────────────────────────────────

def test_normalize_dg_name_last_first():
    assert normalize_dg_name("Scheffler, Scottie") == "Scottie Scheffler"
    assert normalize_dg_name("McIlroy, Rory") == "Rory McIlroy"


def test_normalize_dg_name_passthrough():
    assert normalize_dg_name("Tiger Woods") == "Tiger Woods"
    assert normalize_dg_name("") == ""
    assert normalize_dg_name("Cabrera Bello, Rafa") == "Rafa Cabrera Bello"


def test_slugify_golfer_strips_accents_and_punct():
    assert slugify_golfer("Rory McIlroy") == "rory-mcilroy"
    assert slugify_golfer("Joaquín Niemann") == "joaquin-niemann"
    assert slugify_golfer("Scheffler, Scottie") == "scottie-scheffler"


def test_event_slug_drops_the_prefix():
    assert event_slug("The Masters") == "masters"
    assert event_slug("U.S. Open") == "u-s-open"
    assert event_slug("the Memorial Tournament") == "memorial-tournament"


def test_build_game_id():
    assert build_game_id("2024-06-13", "U.S. Open") == "GOLF_2024-06-13_u-s-open"


def test_is_team_event():
    assert is_team_event("Zurich Classic of New Orleans") is True
    assert is_team_event("the Masters") is False


# ── finish parsing ────────────────────────────────────────────────────────────

def test_parse_finish():
    assert parse_finish("1") == (1, 1)
    assert parse_finish("T10") == (10, 1)
    assert parse_finish("T2") == (2, 1)
    assert parse_finish("CUT") == (None, 0)
    assert parse_finish("MC") == (None, 0)
    assert parse_finish("WD") == (None, None)
    assert parse_finish("DQ") == (None, None)
    assert parse_finish("") == (None, None)
    assert parse_finish(None) == (None, None)


# ── payload parsers ───────────────────────────────────────────────────────────

def test_parse_player_list():
    raw = [
        {"dg_id": 18417, "player_name": "Scheffler, Scottie", "country": "USA", "amateur": 0},
        {"dg_id": 10091, "player_name": "McIlroy, Rory", "country": "NIR", "amateur": 0},
    ]
    out = parse_player_list(raw)
    assert out[0] == {"dg_id": 18417, "player_name": "Scottie Scheffler",
                      "slug": "scottie-scheffler", "country": "USA", "amateur": 0}
    assert out[1]["player_name"] == "Rory McIlroy"


def test_parse_event_list_filters_team_and_non_pga():
    raw = {"events": [
        {"event_id": 26, "calendar_year": 2024, "event_name": "U.S. Open", "tour": "pga", "date": "2024-06-13"},
        {"event_id": 99, "calendar_year": 2024, "event_name": "Zurich Classic", "tour": "pga", "date": "2024-04-25"},
        {"event_id": 5, "calendar_year": 2024, "event_name": "Some Euro Event", "tour": "euro", "date": "2024-05-01"},
    ]}
    out = parse_event_list(raw)
    assert out == [{"dg_event_id": 26, "season": 2024, "event_name": "U.S. Open",
                    "start_date": "2024-06-13", "tour": "pga"}]


def test_parse_event_rounds_finish_and_madecut():
    raw = {"scores": [
        {"dg_id": 18417, "player_name": "Scheffler, Scottie", "fin_text": "T7",
         "round_1": {"score": 70, "sg_total": 1.5, "sg_ott": 1.2, "course_num": 1},
         "round_2": {"score": 71}, "round_3": {"score": 68}, "round_4": {"score": 73}},
        {"dg_id": 12345, "player_name": "Smith, Joe", "fin_text": "CUT",
         "round_1": {"score": 75}, "round_2": {"score": 74}},
        {"dg_id": 999, "player_name": "Doe, John", "fin_text": "WD",
         "round_1": {"score": 80}},
    ]}
    rows = parse_event_rounds(raw, 26, 2024, "GOLF_x", "2024-06-13")
    byp = {}
    for r in rows:
        byp.setdefault(r["player_name"], []).append(r)
    # Scheffler: 4 rounds, finish 7, made the cut
    assert len(byp["Scottie Scheffler"]) == 4
    assert byp["Scottie Scheffler"][0]["finish_pos"] == 7
    assert byp["Scottie Scheffler"][0]["made_cut"] == 1
    assert byp["Scottie Scheffler"][0]["sg_ott"] == 1.2
    # Joe Smith: missed cut
    assert byp["Joe Smith"][0]["made_cut"] == 0
    assert byp["Joe Smith"][0]["finish_pos"] is None
    # John Doe: WD after 1 round → made_cut ambiguous (None, dropped from make_cut training)
    assert byp["John Doe"][0]["made_cut"] is None


def test_parse_event_rounds_wd_after_made_cut():
    """WD in round 3+ means the player did make the cut."""
    raw = {"scores": [
        {"dg_id": 7, "player_name": "Late, Withdraw", "fin_text": "WD",
         "round_1": {"score": 70}, "round_2": {"score": 71}, "round_3": {"score": 69}},
    ]}
    rows = parse_event_rounds(raw, 1, 2024, "GOLF_x", "2024-01-01")
    assert rows[0]["made_cut"] == 1


def test_parse_field_update():
    raw = {"event_name": "the Memorial Tournament", "current_round": 1, "event_id": 100,
           "field": [{"dg_id": 18417, "player_name": "Scheffler, Scottie"},
                     {"dg_id": 10091, "player_name": "McIlroy, Rory"}]}
    fu = parse_field_update(raw)
    assert fu["event_name"] == "the Memorial Tournament"
    assert fu["dg_event_id"] == 100
    assert len(fu["players"]) == 2
    assert fu["players"][0]["player_name"] == "Scottie Scheffler"


def test_parse_outright_odds_dk_price_and_dg_prob():
    raw = {"market": "win", "odds": [
        {"dg_id": 18417, "player_name": "Scheffler, Scottie",
         "datagolf": {"baseline": 0.18, "baseline_history_fit": 0.19}, "draftkings": "+450"},
        {"dg_id": 10091, "player_name": "McIlroy, Rory",
         "datagolf": {"baseline": 0.08}, "draftkings": "+1100"},
        {"dg_id": 3, "player_name": "No, Price", "datagolf": {"baseline": 0.01}},
    ]}
    out = parse_outright_odds(raw, "win")
    assert out[0]["price"] == 450.0 and out[0]["datagolf_prob"] == 0.19
    assert out[1]["price"] == 1100.0 and out[1]["datagolf_prob"] == 0.08  # falls back to baseline
    assert out[2]["price"] is None  # DK doesn't price this player


def test_parse_matchup_odds_skips_threeballs_and_strings():
    raw = {"match_list": [
        {"p1_dg_id": 18417, "p1_player_name": "Scheffler, Scottie",
         "p2_dg_id": 10091, "p2_player_name": "McIlroy, Rory", "p3_dg_id": None,
         "ties": "void", "draftkings": {"p1": "-130", "p2": "+110"}, "datagolf": {"p1": 0.56}},
        {"p1_dg_id": 1, "p1_player_name": "A B", "p2_dg_id": 2, "p2_player_name": "C D",
         "p3_dg_id": 3, "draftkings": {}},  # 3-ball, skipped
    ]}
    out = parse_matchup_odds(raw)
    assert len(out) == 1
    assert out[0]["price"] == -130.0 and out[0]["opp_price"] == 110.0
    assert out[0]["opp_player_name"] == "Rory McIlroy"
    assert out[0]["market"] == "matchup_tournament"


def test_parse_matchup_odds_no_matchups_string():
    assert parse_matchup_odds({"match_list": "no tournament matchups available"}) == []
    assert parse_matchup_odds({}) == []
