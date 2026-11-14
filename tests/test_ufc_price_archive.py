"""The free UFC price archives are parsed into one row per fighter per market,
and placed on our own fight ids by the unordered slug pair within two days."""
from __future__ import annotations

import csv
import sqlite3

import pytest

from data.ingestors import ufc_price_archive as A


def _canon(tmp_path):
    p = tmp_path / "canon.db"
    con = sqlite3.connect(p)
    con.executescript("""
        CREATE TABLE events (event_id INTEGER PRIMARY KEY, name TEXT, date TEXT, promotion TEXT);
        CREATE TABLE fights (fight_id INTEGER PRIMARY KEY, event_id INTEGER);
        CREATE TABLE fighters (fighter_id INTEGER PRIMARY KEY, name TEXT);
        CREATE TABLE fight_participants (fight_id INTEGER, fighter_id INTEGER, corner INTEGER);
        CREATE TABLE odds (fight_id INTEGER, fighter_id INTEGER, source TEXT, book TEXT,
                           open INTEGER, close INTEGER, close_low INTEGER, close_high INTEGER);
        INSERT INTO events VALUES (1, 'UFC 300', '2024-04-13', 'UFC'), (2, 'PFL 1', '2024-04-13', 'PFL');
        INSERT INTO fights VALUES (10, 1), (11, 2), (12, 1);
        INSERT INTO fighters VALUES (1, 'Alex Pereira'), (2, 'Jamahal Hill'), (3, 'Nobody A'),
                                    (4, 'Nobody B'), (5, 'Zhang Weili'), (6, 'Yan Xiaonan');
        INSERT INTO fight_participants VALUES (10, 1, 0), (10, 2, 1), (11, 3, 0), (11, 4, 1),
                                              (12, 5, 0), (12, 6, 1);
        INSERT INTO odds VALUES (10, 1, 'bestfightodds', 'all', -150, NULL, -140, -125),
                                (10, 2, 'bestfightodds', 'all', 120, NULL, 105, 120),
                                (11, 3, 'bestfightodds', 'all', -200, NULL, -210, -190),
                                (11, 4, 'bestfightodds', 'all', 160, NULL, 150, 170);
    """)
    con.commit(); con.close()
    return p


def test_canon_keeps_only_ufc_fights_with_a_price_both_ways(tmp_path):
    rows = A.parse_canon(_canon(tmp_path))
    # the PFL fight is not UFC; fight 12 has no odds row at all
    assert {r["source_fight_id"] for r in rows} == {"10"}
    by = {r["fighter_slug"]: r for r in rows}
    assert by["alex-pereira"]["price_open"] == -150
    assert (by["alex-pereira"]["close_low"], by["alex-pereira"]["close_high"]) == (-140, -125)
    assert by["jamahal-hill"]["opponent_slug"] == "alex-pereira"
    assert all(r["source"] == A.SOURCE_BFO and r["market"] == "h2h" for r in rows)


def test_uud_writes_the_fight_and_every_method_price_it_has(tmp_path):
    p = tmp_path / "ufc-master.csv"
    with open(p, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["R_fighter", "B_fighter", "R_odds", "B_odds", "date", "r_dec_odds", "b_dec_odds",
                    "r_ko_odds", "b_ko_odds", "r_sub_odds", "b_sub_odds"])
        w.writerow(["José Aldo", "Max Holloway", "-130", "110", "2017-06-03", "250", "", "300", "400", "0", "900"])
    rows = A.parse_uud(p)
    got = {(r["fighter_slug"], r["market"]): r["price"] for r in rows}
    assert got == {("jose-aldo", "h2h"): -130, ("max-holloway", "h2h"): 110,
                   ("jose-aldo", "method_decision"): 250,
                   ("jose-aldo", "method_ko_tko"): 300, ("max-holloway", "method_ko_tko"): 400,
                   ("max-holloway", "method_submission"): 900}
    assert {r["source_fight_id"] for r in rows} == {"2017-06-03|jose-aldo|max-holloway"}


@pytest.mark.parametrize("cell,want", [("-130", -130), ("110.0", 110), ("", None), ("0", None),
                                       ("nan", None), (None, None), ("abc", None)])
def test_american_reads_only_real_prices(cell, want):
    assert A.american(cell) == want


def test_a_fight_is_placed_by_its_unordered_pair_within_two_days():
    rows = [dict(source="s", source_fight_id="1", fight_date="2024-04-13",
                 fighter_slug="alex-pereira", opponent_slug="jamahal-hill"),
            dict(source="s", source_fight_id="2", fight_date="2024-04-20",
                 fighter_slug="alex-pereira", opponent_slug="jamahal-hill")]
    log = [("UFC_2024-04-13_alex-pereira_jamahal-hill", "2024-04-14", "jamahal-hill", "alex-pereira")]
    assert A.attach_game_ids(rows, log) == 1
    assert rows[0]["game_id"] == "UFC_2024-04-13_alex-pereira_jamahal-hill"
    assert rows[1]["game_id"] is None          # a week out is another fight


def test_the_table_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert A.TABLE in WORKER_ONLY_TABLES
