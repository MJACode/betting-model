"""scripts/splits_coverage_probe.py: the per-book comparison and the DK page reader, on fixtures shaped like the
v2 scoreboard entries the 2026-11-26 probes printed (worker_jobs 1698627, 1717775)."""
from __future__ import annotations

import json
from pathlib import Path

import scripts.splits_coverage_probe as P
from tracking import job_queue

ROOT = Path(__file__).resolve().parents[1]


def _e(side, t, m, team=None, live=False, value=None):
    e = {"side": side, "is_live": live, "value": value,
         "bet_info": {"tickets": {"percent": t}, "money": {"percent": m}}}
    if team is not None:
        e["team_id"] = team
    return e


GAME = {"markets": {
    "15": {"event": {"spread": [_e("home", 60, 62), _e("away", 40, 38)],
                     "total": [_e("over", 0, 0), _e("under", 0, 0)],
                     "core_bet_type_6_team_score": [_e("over", 0, 0, team=251), _e("under", 0, 0, team=251)]}},
    "68": {"event": {"spread": [_e("home", 60, 62), _e("away", 40, 38)],
                     "core_bet_type_6_team_score": [_e("over", 70, 55, team=251), _e("under", 30, 45, team=251)]}},
    "69": {"event": {"spread": [_e("home", 99, 99, live=True), _e("home", 52, 70), _e("away", 48, 30)]}},
}}


def test_book_entries_drops_placeholders_and_live_entries():
    assert P.book_entries(GAME, "15", "event") == {("spread", "home", None): (60.0, 62.0),
                                                   ("spread", "away", None): (40.0, 38.0)}
    ents = P.book_entries(GAME, "68", "event")
    assert ents[("core_bet_type_6_team_score", "over", 251)] == (70.0, 55.0)
    # The live 99/99 entry for book 69 is not the pre-game split.
    assert P.book_entries(GAME, "69", "event")[("spread", "home", None)] == (52.0, 70.0)
    assert P.book_entries(GAME, "68", "firsthalf") == {}


def test_compare_books_counts_copies_of_consensus_and_the_gaps():
    cmp = P.compare_books({"games": [GAME]}, "event")
    # Book 68's spread is consensus copied: 2 of 2 sides the same, no ticket gap.
    assert cmp["68"]["sp"] == {"games": 1, "sides": 2, "same": 2, "compared": 2, "tk_gap_med": 0.0,
                               "mt_gap_med": 2.0}
    # Its team total has no consensus counterpart (consensus is 0/0 there), so nothing is compared.
    assert cmp["68"]["tt"]["compared"] == 0 and cmp["68"]["tt"]["mt_gap_med"] == 15.0
    # Book 69 differs from consensus by 8 tickets on each side and carries a real money gap.
    assert cmp["69"]["sp"]["same"] == 0 and cmp["69"]["sp"]["tk_gap_med"] == 8.0
    assert cmp["69"]["sp"]["mt_gap_med"] == 18.0
    # Consensus is never compared with itself; its totals are placeholders and do not appear.
    assert cmp["15"]["sp"]["compared"] == 0 and "tot" not in cmp["15"]


def test_first_split_entry_skips_consensus_and_placeholders():
    e = P.first_split_entry({"games": [GAME]}, "core_bet_type_6_team_score", skip_book="15")
    assert e["book"] == "68" and e["team_id"] == 251 and e["side"] == "over"
    assert P.first_split_entry({"games": [GAME]}, "total", skip_book="15") is None


DK_PAGE = (
    "<html><head><title>DraftKings Sportsbook Betting Splits | DKN</title></head><body>"
    '<a href="https://dknetwork.draftkings.com/draftkings-sportsbook-betting-splits/?tb_eg=42648&#038;tb_emt=Spread">x</a>'
    '<a href="https://dknetwork.draftkings.com/nba-player-props-today/">Player Props</a>'
    "<div>BKN Nets @ MIN Timberwolves Selection Odds Handle Bets Spread BKN Nets +9.5 -110 40% 35% "
    "MIN Timberwolves -9.5 -110 60% 65%</div></body></html>")


def test_dk_page_facts_reads_title_filters_rows_and_prop_text():
    d = P.dk_page_facts(DK_PAGE)
    assert d["title"] == "DraftKings Sportsbook Betting Splits | DKN"
    assert d["filters"] == ["Spread"]
    assert d["split_rows"] == 1
    assert d["prop_links"] == ["https://dknetwork.draftkings.com/nba-player-props-today/"]
    assert d["windows"]["Player"] and "Player Props" in d["windows"]["Player"][0]
    assert d["handle_windows"] and "Handle Bets" in d["handle_windows"][0]


def test_probe_asks_every_book_and_fails_when_a_live_sport_is_unreachable(capsys):
    calls = []

    class Conn:
        def execute(self, sql, params):
            past = "<" in sql
            return type("R", (), {"fetchall": lambda self: [("2026-09-10",)] if past else
                                  ([("2026-11-27",)] if params[0] in ("NBA", "NFL") else [])})()

    def get(url, **kw):
        calls.append((url, kw.get("params")))
        if "/scoreboard/nfl" in url:
            return 503, "", None
        if "actionnetwork" in url and "scoreboard" in url:
            return 200, json.dumps({"games": [GAME]}), None
        return 200, DK_PAGE, None

    assert P.probe(get=get, conn=Conn()) == 1
    out = capsys.readouterr().out
    assert P.SUMMARY_MARK in out and "an nfl 20261127 event: HTTP 503" in out
    an = [p for u, p in calls if "/scoreboard/" in u]
    # No bookIds filter: every book the endpoint carries comes back.
    assert an and all("bookIds" not in p for p in an)
    # NBA asked for every period; WNBA on its last played date, full game only.
    assert {p["periods"] for u, p in calls if "/scoreboard/nba" in u} == set(P.PERIODS)
    assert [p for u, p in calls if "/scoreboard/wnba" in u] == [{"date": "20260910", "periods": "event"}]
    assert "an ncaaf: no upcoming NCAAF date in games" in out
    assert "68[" in out and "same 2/2" in out
    # Every DK event group and both article pages were read.
    dk = [p for u, p in calls if u == P.DK_URL]
    assert {p["tb_eg"] for p in dk} == set(P.DK_EVENT_GROUPS.values())
    assert all(any(u == a for u, _ in calls) for a in P.DK_ARTICLES)


def test_job_is_registered_and_declared_without_args():
    assert "splits_coverage_probe" in job_queue.JOBS
    declared = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    entry = [d for d in declared if d.get("job_type") == "splits_coverage_probe"]
    assert len(entry) == 1 and entry[0]["args"] == {} and entry[0]["requested_by"] == "mike"


def test_match_counts_uses_the_ingestors_parser_and_matcher():
    from tests.test_scoreboard_splits import CAR_GB, GAMES, _game
    unknown = _game(CAR_GB, home=("ZZZ", "Nowhere Zeds"))
    no_split = {**_game(CAR_GB), "markets": {"15": {"event": {"spread": [], "total": [], "moneyline": []}}}}
    got = P.match_counts("NFL", {"games": [_game(CAR_GB), unknown, no_split]}, GAMES)
    assert got == {"listed": 3, "with_split": 2, "matched": 1}
