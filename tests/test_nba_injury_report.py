"""The NBA injury report archive: slot names, report times, and the parser.

The fixtures are real league PDFs trimmed to a few pages with pypdf, so the
parser runs on the same ruled lines and word positions as production:

  * 2019-01-15 05PM, pages 1-2 -- the nine-column layout (Category and Reason
    separate, Previous Status), a team name wrapped over two lines, and a
    game whose rows continue over the page break.
  * 2018-12-17 05PM, page 3 -- a team printed as ALL PLAYERS AVAILABLE,
    which is a team row and not the tail of the reason above it.
  * 2020-07-30 05PM, page 1 -- the seven-column layout of the old renderer.
  * 2026-01-15 05:00PM, pages 1, 8 and 9 -- the current layout, which prints
    the column header on page 1 only, a two-line reason with the player's
    name between its lines, a reason cut by the page break between 8 and 9,
    and teams listed as NOT YET SUBMITTED. Pages 2-7 are cut, so the rows at
    the top of page 8 inherit page 1's game: only rows from where page 8 names
    its own game are asserted.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from data.ingestors import nba_injury_report as m

FIX = Path(__file__).parent / "fixtures" / "nba_injury_report"
ET = m.ET


def _rows(name: str):
    rep = m.parse_pdf((FIX / name).read_bytes())
    return rep, {r["player_name"]: r for r in rep.rows if r["player_name"]}


# ── slots and times ──────────────────────────────────────────────────────────

def test_slot_names_both_formats():
    assert m.old_slot(0) == "12AM"
    assert m.old_slot(12) == "12PM"
    assert m.old_slot(17) == "05PM"
    assert m.old_slot(23) == "11PM"
    assert m.new_slot(0, 0) == "12_00AM"
    assert m.new_slot(17, 15) == "05_15PM"
    assert m.report_url(date(2026, 2, 18), "05_30PM") == (
        "https://ak-static.cms.nba.com/referee/injury/Injury-Report_2026-02-18_05_30PM.pdf")


def test_hourly_dates_get_sixteen_hourly_slots():
    slots = m.slots_for_date(date(2024, 3, 12))
    assert slots == ["08AM", "09AM", "10AM", "11AM", "12PM"] + [
        f"{h:02d}PM" for h in range(1, 12)]


def test_quarter_hour_dates_get_half_hours_plus_the_slot_before_each_tip():
    tips = [datetime(2026, 2, 19, 19, 0, tzinfo=ET),      # -> 06_45PM
            datetime(2026, 2, 19, 19, 30, tzinfo=ET),     # -> 07_15PM
            datetime(2026, 2, 19, 22, 10, tzinfo=ET),     # -> 10_00PM, already there
            datetime(2026, 2, 20, 19, 0, tzinfo=ET)]      # another day: ignored
    slots = m.slots_for_date(date(2026, 2, 19), tips)
    assert len(slots) == 32 + 2
    assert slots[0] == "08_00AM" and slots[-1] == "11_30PM"
    assert "06_45PM" in slots and "07_15PM" in slots and "10_00PM" in slots
    assert "06_15PM" not in slots
    assert all(len(s) == 7 for s in slots)


def test_format_switch_is_measured_and_both_are_probed_around_it():
    assert m.slots_for_date(date(2025, 12, 18))[0] == "08AM"
    assert all("_" not in s for s in m.slots_for_date(date(2025, 12, 18)))
    assert all("_" in s for s in m.slots_for_date(date(2025, 12, 26)))
    both = m.slots_for_date(date(2025, 12, 22))
    assert "05PM" in both and "05_00PM" in both


def test_pre_tip_slot_is_strictly_before_the_tip():
    assert m.pre_tip_slot(datetime(2026, 1, 15, 19, 0, tzinfo=ET)) == (18, 45)
    assert m.pre_tip_slot(datetime(2026, 1, 15, 19, 10, tzinfo=ET)) == (19, 0)
    assert m.pre_tip_slot(datetime(2026, 1, 15, 19, 30, tzinfo=ET)) == (19, 15)


class _DatesConn:
    def __init__(self, dates):
        self.dates = dates

    def execute(self, sql, params=None):
        return type("C", (), {"fetchall": lambda _s: [(d,) for d in self.dates]})()


def test_scope_is_every_game_date_and_the_day_before_newest_first():
    # The evening report before a game is the one a game-morning bet could see.
    got = m.scope_dates(_DatesConn(["2026-01-15", "2026-01-17", "2026-01-16", "2099-01-01"]),
                        2026, 2026)
    assert got == [date(2026, 1, 17), date(2026, 1, 16), date(2026, 1, 15), date(2026, 1, 14)]


def test_slot_time_is_eastern():
    assert m.slot_time(date(2024, 3, 12), "05PM") == datetime(2024, 3, 12, 17, 0, tzinfo=ET)
    assert m.slot_time(date(2024, 3, 12), "12AM") == datetime(2024, 3, 12, 0, 0, tzinfo=ET)
    assert m.slot_time(date(2026, 1, 15), "05_15PM") == datetime(2026, 1, 15, 17, 15, tzinfo=ET)
    with pytest.raises(ValueError):
        m.slot_time(date(2026, 1, 15), "5PM")


def test_report_time_comes_from_the_header_and_is_stored_in_utc():
    # 2024-03-12 is after the switch to daylight time: EDT, UTC-4.
    assert m.parse_title("Injury Report: 03/12/24 05:30 PM") == datetime(
        2024, 3, 12, 21, 30, tzinfo=timezone.utc)
    # January: EST, UTC-5.
    assert m.parse_title("Injury Report: 01/15/19 05:30 PM") == datetime(
        2019, 1, 15, 22, 30, tzinfo=timezone.utc)
    # 12:30 AM is the start of the named day, not the end of it.
    assert m.parse_title("Injury Report: 03/12/24 12:30 AM") == datetime(
        2024, 3, 12, 4, 30, tzinfo=timezone.utc)
    assert m.parse_title("no title here") is None


# ── the 403 ledger rule ──────────────────────────────────────────────────────

class _Cur:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class _Conn:
    """Records writes; answers the predecessor lookup with `prev`."""

    def __init__(self, prev=None):
        self.calls = []
        self.prev = prev

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return _Cur(self.prev if "ORDER BY report_ts DESC" in sql else None)

    def executemany(self, sql, rows):
        self.calls.append((sql, rows))

    def commit(self):
        pass

    def inserted_rows(self):
        return [rows for sql, rows in self.calls if "INSERT INTO nba_injury_report " in sql]

    def ledger(self):
        return [p for sql, p in self.calls if "INSERT INTO nba_injury_report_pulls" in sql]


class _Fetcher:
    def get(self, url):
        return 403, None


def test_a_recent_403_is_not_written_so_a_later_run_can_still_fetch_it():
    d = date(2026, 1, 15)
    conn = _Conn()
    soon = m.slot_time(d, "05_00PM").astimezone(timezone.utc) + m.MISSING_IS_FINAL_AFTER / 2
    res = m.pull_one(conn, _Fetcher(), d, "05_00PM", {}, {}, now=soon)
    assert res["ledgered"] is False and conn.calls == []


def test_an_old_403_is_written_so_a_rerun_never_asks_again():
    d = date(2026, 1, 15)
    conn = _Conn()
    later = m.slot_time(d, "05_00PM").astimezone(timezone.utc) + 2 * m.MISSING_IS_FINAL_AFTER
    res = m.pull_one(conn, _Fetcher(), d, "05_00PM", {}, {}, now=later)
    assert res["ledgered"] is True
    (sql, params), = conn.calls
    assert "nba_injury_report_pulls" in sql and params[0] == m.report_url(d, "05_00PM")
    assert params[3] == 403


# ── a report that repeats its predecessor ────────────────────────────────────

class _PdfFetcher:
    def __init__(self, name):
        self.data = (FIX / name).read_bytes()

    def get(self, url):
        return 200, self.data


NEW_FIX = "Injury-Report_2026-01-15_05_00PM_pages1-8-9.pdf"


def _content_of_fixture():
    return m.content_hash(m.finish_rows(m.parse_pdf((FIX / NEW_FIX).read_bytes()), {}, {}))


def test_a_report_identical_to_its_predecessor_stores_no_rows_and_points_at_it():
    first = "https://x/Injury-Report_2026-01-15_04_30PM.pdf"
    conn = _Conn(prev=(first, _content_of_fixture(), None))
    res = m.pull_one(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {})
    assert conn.inserted_rows() == []
    (led,) = conn.ledger()
    assert led[-1] == first and res["same_as"] == first
    assert led[5] == 49                 # the rows it carried are still counted


def test_a_repeat_of_a_repeat_points_at_the_report_that_holds_the_rows():
    conn = _Conn(prev=("https://x/b.pdf", _content_of_fixture(), "https://x/a.pdf"))
    m.pull_one(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {})
    assert conn.ledger()[0][-1] == "https://x/a.pdf"


def test_a_changed_report_stores_its_rows():
    conn = _Conn(prev=("https://x/a.pdf", "a different report", None))
    res = m.pull_one(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {})
    (rows,) = conn.inserted_rows()
    assert len(rows) == 49 and res["same_as"] is None
    assert {r["report_ts"] for r in rows} == {datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)}


def test_dedupe_off_stores_rows_even_when_identical():
    conn = _Conn(prev=("https://x/a.pdf", _content_of_fixture(), None))
    m.pull_one(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {}, dedupe=False)
    assert len(conn.inserted_rows()) == 1


# ── names, teams, seasons ────────────────────────────────────────────────────

def test_names_turn_round_with_their_suffix_on_the_surname():
    assert m.name_first_last("Pippen Jr., Scotty") == "Scotty Pippen Jr."
    assert m.name_first_last("Council IV, Ricky") == "Ricky Council IV"
    assert m.name_first_last("Jones Jr., Derrick") == "Derrick Jones Jr."
    assert m.name_first_last("Covington,  Robert") == "Robert Covington"
    assert m.name_first_last("Nene") == "Nene"
    assert m.name_first_last(None) is None


def test_name_key_drops_accents_punctuation_and_suffixes():
    assert m.norm_name("Nikola Jokić") == "nikola jokic"
    assert m.norm_name("Scotty Pippen Jr.") == m.norm_name("Scotty Pippen")
    assert m.norm_name("De'Anthony Melton") == "deanthony melton"
    assert m.norm_name("E.J. Liddell") == "ej liddell"


def test_team_names_map_to_our_codes():
    assert m.team_code("LA Clippers") == "LAC"
    assert m.team_code("Los Angeles Lakers") == "LAL"
    assert m.team_code("Philadelphia 76ers") == "PHI"
    assert m.team_code("Minnesota Timberwolves") == "MIN"
    assert m.team_code("Gotham Rogues") is None


def test_season_label_is_the_ending_year_and_the_bubble_is_2020():
    assert m.season_of("2019-01-15") == 2019
    assert m.season_of("2019-10-22") == 2020
    assert m.season_of("2020-08-14") == 2020
    assert m.season_of("2020-12-22") == 2021
    assert m.season_of(None) is None


def test_player_ids_match_on_team_first_then_a_unique_season_name():
    players = {"team": {(2026, "MEM", "scotty pippen"): "1630590"},
               "season": {(2026, "zach edey"): "1641744"},
               "any": {"fred vanvleet": ("1627832", {2024, 2025})}}
    assert m.match_player(players, 2026, "MEM", "Scotty Pippen Jr.") == "1630590"
    assert m.match_player(players, 2026, "MEM", "Zach Edey") == "1641744"
    assert m.match_player(players, 2025, "MEM", "Zach Edey") is None
    # Out all season, so no game log that season: matched on a name unique
    # across every season.
    assert m.match_player(players, 2026, "HOU", "Fred VanVleet") == "1627832"
    assert m.match_player(players, 2026, "HOU", "Nobody Atall") is None
    # A namesake whose game logs are years away is not the same player.
    assert m.match_player(players, 2019, "HOU", "Fred VanVleet") is None


def test_remap_rewrites_only_names_whose_id_changed():
    players = {"team": {(2026, "MEM", "zach edey"): "1641744"}, "season": {}, "any": {},
               "surname": {}}
    current = [(2026, "MEM", "Zach Edey", ["1641744"]),          # unchanged
               (2026, "MEM", "Zach Edey", [None]),               # newly matched
               (2026, "MEM", "Nobody Atall", ["999"]),           # no longer supported
               (2026, "MEM", "Nobody Else", [None])]             # still unmatched
    assert m.remap_changes(players, current) == [
        ("1641744", 2026, "MEM", "Zach Edey"), (None, 2026, "MEM", "Nobody Atall")]


def test_a_name_printed_differently_matches_on_surname_and_initial_within_the_team():
    class _C:
        def execute(self, sql, params=None):
            rows = [(2021, "BKN", 1629651, "Nic Claxton"),
                    (2021, "OKC", 1, "Jalen Williams"), (2021, "OKC", 2, "Jaylin Williams")]
            return type("R", (), {"fetchall": lambda _s: rows})()
    players = m.load_players(_C())
    assert m.match_player(players, 2021, "BKN", "Nicolas Claxton") == "1629651"
    # Two Williams with the same initial on one team: no guess.
    assert m.match_player(players, 2021, "OKC", "J. Williams") is None
    # The surname rule never crosses teams or seasons.
    assert m.match_player(players, 2022, "BKN", "Nicolas Claxton") is None
    assert m.match_player(players, 2021, "NYK", "Nicolas Claxton") is None


# ── the parser, on real PDFs ─────────────────────────────────────────────────

def test_nine_column_layout_2019():
    rep, by = _rows("Injury-Report_2019-01-15_05PM_pages1-2.pdf")
    assert rep.report_ts == datetime(2019, 1, 15, 22, 30, tzinfo=timezone.utc)
    assert len(rep.rows) == 53 and rep.warnings == []
    cov = by["Robert Covington"]
    # The team name wraps onto a second line: both lines are the team.
    assert (cov["team_name"], cov["team"]) == ("Minnesota Timberwolves", "MIN")
    assert (cov["game_date"], cov["game_time_et"], cov["matchup"]) == ("2019-01-15", "07:00", "MIN@PHI")
    assert cov["status"] == "Out"
    # Category and Reason joined the way the later layout prints them.
    assert cov["reason"] == "Injury/Illness - Right Knee Bone Bruise"
    # A '-' Reason is empty, not text.
    assert by["Jared Terrell"]["reason"] == "G League Team"
    # Previous Status is not the current status.
    assert by["Haywood Highsmith"]["status"] == "Out"
    assert by["Darren Collison"]["status"] == "Available"
    # Page 2 opens mid-game: date, time, matchup and team carry over the break.
    maten = by["Yante Maten"]
    assert (maten["game_date"], maten["game_time_et"], maten["matchup"], maten["team"]) == (
        "2019-01-15", "08:00", "MIA@MIL", "MIA")
    # A two-line reason, the player's name printed between its lines.
    g = by["Giannis Antetokounmpo"]
    assert g["team"] == "MIL" and g["status"] == "Probable"
    assert g["reason"] == "Injury/Illness - Right quadriceps soreness/Left hip contusion"


def test_seven_column_layout_2020():
    rep, by = _rows("Injury-Report_2020-07-30_05PM_page1.pdf")
    assert rep.report_ts == datetime(2020, 7, 30, 21, 30, tzinfo=timezone.utc)
    assert len(rep.rows) == 27 and rep.warnings == []
    z = by["Zion Williamson"]
    assert (z["matchup"], z["team"], z["game_time_et"], z["status"]) == ("UTA@NOP", "NOP", "06:30", "Questionable")
    assert z["reason"] == "Injury/Illness - N/a; Re-conditioning"
    assert by["Patrick Beverley"]["team"] == "LAC"
    assert by["Patrick Beverley"]["reason"] == "Not With Team - Self Isolating"
    assert by["Kentavious Caldwell-Pope"]["team"] == "LAL"


def test_current_layout_2026():
    rep, by = _rows("Injury-Report_2026-01-15_05_00PM_pages1-8-9.pdf")
    assert rep.report_ts == datetime(2026, 1, 15, 22, 0, tzinfo=timezone.utc)
    assert rep.warnings == []
    first = rep.rows[0]
    assert (first["game_date"], first["game_time_et"], first["matchup"], first["team"]) == (
        "2026-01-15", "02:00", "MEM@ORL", "MEM")
    # Name between the two lines of its reason; neither line goes to a neighbour.
    assert by["Brandon Clarke"]["reason"] == "Injury/Illness - Right Calf; Strain"
    assert by["Zach Edey"]["reason"] == "Injury/Illness - Left Ankle; Stress Reaction"
    assert by["Ty Jerome"]["reason"] == "Injury/Illness - Right Calf; Strain"
    p = by["Scotty Pippen Jr."]
    assert p["player_name_raw"] == "Pippen Jr., Scotty"
    assert p["reason"] == "Injury/Illness - Left Great Toe; Surgery Recovery"
    assert by["Jalen Suggs"]["team"] == "ORL"
    # Pages 8 and 9 print no column header: the columns come from page 1.
    assert by["Zach Collins"]["matchup"] == "CHI@BKN" and by["Zach Collins"]["team"] == "CHI"
    assert by["Ziaire Williams"]["team"] == "BKN"
    # The reason cut by the page break joins the row it belongs to...
    assert by["Bogdan Bogdanovic"]["reason"] == "Injury/Illness - Left Hamstring; Injury Management"
    # ...and the first row of page 9 keeps the game and team carried over the break.
    jc = by["John Collins"]
    assert (jc["matchup"], jc["team"], jc["status"]) == ("LAC@TOR", "LAC", "Questionable")
    assert jc["reason"] == "Injury/Illness - Right Groin; Soreness"
    nys = [(r["matchup"], r["team"]) for r in rep.rows if r["status"] == m.NOT_SUBMITTED]
    assert nys == [("MIN@HOU", "MIN"), ("MIN@HOU", "HOU"), ("WAS@SAC", "WAS"), ("WAS@SAC", "SAC")]
    assert all(r["player_name"] is None for r in rep.rows if r["status"] == m.NOT_SUBMITTED)
    assert {r["status"] for r in rep.rows} <= set(m.STATUSES) | {m.NOT_SUBMITTED}


def test_finish_rows_builds_our_game_id_and_season():
    rep = m.parse_pdf((FIX / "Injury-Report_2019-01-15_05PM_pages1-2.pdf").read_bytes())
    sched = {"NBA_2019-01-15_MIN_PHI": {"season": 2019, "commence_time": None}}
    rows = m.finish_rows(rep, sched, {})
    assert rows[0]["game_id"] == "NBA_2019-01-15_MIN_PHI" and rows[0]["season"] == 2019
    assert [r["row_no"] for r in rows] == list(range(len(rows)))
    # A game the schedule lacks still gets its id and the season from its date.
    mil = next(r for r in rows if r["matchup"] == "MIA@MIL")
    assert mil["game_id"] == "NBA_2019-01-15_MIA_MIL" and mil["season"] == 2019
    assert rep.warnings == []           # every team is one of its matchup's two


def test_all_players_available_is_a_team_row_not_the_tail_of_a_reason():
    # December 2018 reports print "ALL PLAYERS AVAILABLE" for a team with nobody
    # listed. It must not be glued onto the reason of the row above it.
    rep, by = _rows("Injury-Report_2018-12-17_05PM_page3.pdf")
    assert by["Lou Williams"]["reason"] == "Injury/Illness - Sore hamstring - left"
    # (Page 3 alone: the matchup was printed on page 2, so it is not asserted.)
    team_rows = [(r["team"], r["status"]) for r in rep.rows if r["player_name"] is None]
    assert team_rows == [("POR", m.ALL_AVAILABLE), ("CLE", m.NOT_SUBMITTED)]
    assert rep.warnings == []


def test_a_connection_lost_mid_write_re_runs_the_whole_slot():
    from data.db import ConnectionLost

    class _Flaky(_Conn):
        def __init__(self):
            super().__init__(prev=None)
            self.failures = 1

        def executemany(self, sql, rows):
            if self.failures:
                self.failures -= 1
                self.calls.clear()          # the lost transaction took its statements with it
                raise ConnectionLost("server closed the connection unexpectedly")
            super().executemany(sql, rows)

    conn = _Flaky()
    res = m.pull_with_retry(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {},
                            pause=0)
    assert res["status"] == 200 and res["rows"] == 49
    assert len(conn.inserted_rows()) == 1 and len(conn.ledger()) == 1


def test_a_statement_timeout_rolls_back_and_re_runs_the_slot():
    import psycopg2.errors

    class _Slow(_Conn):
        def __init__(self):
            super().__init__(prev=None)
            self.failures, self.rollbacks = 1, 0

        def executemany(self, sql, rows):
            if self.failures:
                self.failures -= 1
                self.calls.clear()
                raise psycopg2.errors.QueryCanceled("canceling statement due to statement timeout")
            super().executemany(sql, rows)

        def rollback(self):
            self.rollbacks += 1

    conn = _Slow()
    res = m.pull_with_retry(conn, _PdfFetcher(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {},
                            pause=0)
    assert res["rows"] == 49 and conn.rollbacks == 1 and len(conn.inserted_rows()) == 1


def test_a_report_whose_cells_do_not_line_up_with_its_header_is_not_stored():
    good = {"status": "Out", "player_name": "A B"}
    nys = {"status": m.NOT_SUBMITTED, "player_name": None}
    shifted = {"status": "", "player_name": "Injury/Illness - Fractured Third"}
    assert m.garbled_note([good] * 9 + [nys] * 5) is None
    assert m.garbled_note([good] * 9 + [shifted]) is None            # one odd row is noted, kept
    assert "rows not stored" in m.garbled_note([good] * 2 + [shifted] * 8)
    assert m.garbled_note([nys] * 4) is None                          # nobody submitted yet


def test_a_garbled_report_writes_its_ledger_row_and_no_rows():
    class _Bad(_PdfFetcher):
        pass

    real = m.parse_pdf

    def shifted(data):
        rep = real(data)
        for r in rep.rows:
            if r["status"] != m.NOT_SUBMITTED:
                r["status"] = None
        return rep

    conn = _Conn()
    try:
        m.parse_pdf = shifted
        res = m.pull_one(conn, _Bad(NEW_FIX), date(2026, 1, 15), "05_00PM", {}, {})
    finally:
        m.parse_pdf = real
    assert conn.inserted_rows() == [] and res["rows"] == 0
    (led,) = conn.ledger()
    assert "layout not understood" in led[8] and led[9] is None    # notes; no content hash
