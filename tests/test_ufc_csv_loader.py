"""
test_ufc_csv_loader.py — Pure-function tests for the UFC CSV-mirror loader.

The loader reshapes Greco1899/scrape_ufc_stats CSV rows into the same dict
shapes the ufcstats HTML parsers emit, then hands them to the shared
_ingest_event DB writer. These tests exercise the reshaping (no network, no DB)
against synthetic rows mirroring the real CSV columns.
"""

from data.ingestors.ufc_csv_loader import (
    _kd_int,
    _scheduled_rounds,
    _split_bout,
    build_events,
    build_fighter_index,
)


# ── small helpers ─────────────────────────────────────────────────────────────

def test_kd_int_handles_float_strings_and_blanks():
    assert _kd_int("1.0") == 1
    assert _kd_int("0.0") == 0
    assert _kd_int("3") == 3
    assert _kd_int("") is None
    assert _kd_int("--") is None
    assert _kd_int(None) is None


def test_split_bout():
    assert _split_bout("Arnold Allen vs. Melquizael Costa") == ("Arnold Allen", "Melquizael Costa")
    assert _split_bout("no separator here") is None


def test_scheduled_rounds():
    assert _scheduled_rounds("3 Rnd (5-5-5)") == 3
    assert _scheduled_rounds("5 Rnd (5-5-5-5-5)") == 5
    assert _scheduled_rounds("No Time Limit") is None


def test_build_fighter_index_keeps_first_on_collision():
    tott = [
        {"FIGHTER": "Mike Davis", "URL": "http://ufcstats.com/fighter-details/aaaa1111"},
        {"FIGHTER": "Mike Davis", "URL": "http://ufcstats.com/fighter-details/bbbb2222"},
        {"FIGHTER": "Jon Jones", "URL": "http://ufcstats.com/fighter-details/cccc3333"},
    ]
    idx = build_fighter_index(tott)
    assert idx["Mike Davis"] == "aaaa1111"   # first wins
    assert idx["Jon Jones"] == "cccc3333"


# ── full event reshape ────────────────────────────────────────────────────────

def _fixture():
    fighters = [
        {"FIGHTER": "Arnold Allen", "HEIGHT": "5' 8\"", "REACH": "70\"",
         "STANCE": "Orthodox", "DOB": "Jan 22, 1994",
         "URL": "http://ufcstats.com/fighter-details/aaaa0001"},
        {"FIGHTER": "Melquizael Costa", "HEIGHT": "5' 9\"", "REACH": "72\"",
         "STANCE": "Orthodox", "DOB": "Mar 03, 1997",
         "URL": "http://ufcstats.com/fighter-details/bbbb0002"},
    ]
    meta = {"UFC Test: Allen vs Costa": ("eeee0009", "2024-05-16")}
    results = [{
        "EVENT": "UFC Test: Allen vs Costa",
        "BOUT": "Arnold Allen vs. Melquizael Costa",
        "OUTCOME": "W/L",
        "WEIGHTCLASS": "Featherweight Bout",
        "METHOD": "Decision - Unanimous",
        "ROUND": "5", "TIME": "5:00", "TIME FORMAT": "5 Rnd (5-5-5-5-5)",
        "URL": "http://ufcstats.com/fight-details/ffff0007",
    }]
    # two rounds of per-fighter stats — loader sums across rounds
    stats = []
    for rnd, a_kd, a_sig in (("Round 1", "1.0", "9 of 9"), ("Round 2", "0.0", "23 of 38")):
        stats.append({"EVENT": "UFC Test: Allen vs Costa",
                      "BOUT": "Arnold Allen vs. Melquizael Costa", "ROUND": rnd,
                      "FIGHTER": "Arnold Allen", "KD": a_kd, "SIG.STR.": a_sig,
                      "TOTAL STR.": a_sig, "TD": "0 of 0", "SUB.ATT": "0",
                      "REV.": "0", "CTRL": "1:00"})
        stats.append({"EVENT": "UFC Test: Allen vs Costa",
                      "BOUT": "Arnold Allen vs. Melquizael Costa", "ROUND": rnd,
                      "FIGHTER": "Melquizael Costa", "KD": "0.0", "SIG.STR.": "5 of 10",
                      "TOTAL STR.": "5 of 10", "TD": "1 of 3", "SUB.ATT": "1",
                      "REV.": "0", "CTRL": "0:30"})
    return fighters, meta, results, stats


def test_build_events_winner_first_and_stat_aggregation():
    fighters, meta, results, stats = _fixture()
    events = build_events(results, stats, build_fighter_index(fighters), meta)
    assert len(events) == 1
    ev = events["eeee0009"]
    assert ev["date"] == "2024-05-16"
    assert len(ev["fights"]) == 1

    f = ev["fights"][0]
    # W/L → first listed (Allen) won, placed first
    assert f["fighter_names"] == ["Arnold Allen", "Melquizael Costa"]
    assert f["fighter_ids"] == ["aaaa0001", "bbbb0002"]
    assert f["outcome"] == "first_won"
    assert f["is_title_fight"] == 0

    # KD summed across rounds: Allen 1+0 = 1, Costa 0+0 = 0
    assert f["kd"] == [1, 0]
    # sig landed summed: Allen 9+23 = 32, Costa 5+5 = 10
    assert f["sig_landed"] == [32, 10]

    detail = ev["_details"]["ffff0007"]
    assert detail["scheduled_rounds"] == 5
    # control time summed: Allen 60+60 = 120s, Costa 30+30 = 60s
    assert detail["totals"]["control_sec"] == [120, 60]
    # takedowns attempted summed for Costa: 3+3 = 6
    assert detail["totals"]["td_attempted"] == [0, 6]


def test_build_events_loser_first_outcome_is_swapped():
    fighters, meta, results, stats = _fixture()
    results[0]["OUTCOME"] = "L/W"   # second fighter (Costa) won
    events = build_events(results, stats, build_fighter_index(fighters), meta)
    f = events["eeee0009"]["fights"][0]
    # winner (Costa) is placed first so 'first_won' holds
    assert f["fighter_names"] == ["Melquizael Costa", "Arnold Allen"]
    assert f["fighter_ids"] == ["bbbb0002", "aaaa0001"]
    assert f["outcome"] == "first_won"
    # stats re-ordered to match: Costa's summed sig = 10 now first
    assert f["sig_landed"] == [10, 32]


def test_build_events_draw_and_nc():
    fighters, meta, results, stats = _fixture()
    results[0]["OUTCOME"] = "D/D"
    assert build_events(results, stats, build_fighter_index(fighters), meta)["eeee0009"]["fights"][0]["outcome"] == "draw"
    results[0]["OUTCOME"] = "NC/NC"
    assert build_events(results, stats, build_fighter_index(fighters), meta)["eeee0009"]["fights"][0]["outcome"] == "nc"
