"""The NHL team / alternate / first-period totals purchase: what is bought is stored as it was offered,
in Supabase, in the run that buys it, and a re-run buys nothing twice (CLAUDE.md 1b)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import nhl_totals_odds_history as h

ROOT = Path(__file__).resolve().parents[1]


def _o(name, point, price, description=None):
    out = {"name": name, "point": point, "price": price}
    if description is not None:
        out["description"] = description
    return out


class TestParse:
    def test_alternate_totals_is_one_row_per_number_with_both_sides_paired(self):
        m = {"key": "alternate_totals", "outcomes": [
            _o("Over", 4.5, -310), _o("Under", 4.5, 240), _o("Over", 6.5, 105), _o("Under", 6.5, -125),
            _o("Over", 7.5, 210)]}
        rows = {r["total_line"]: r for r in h.parse_market(m, "NYR", "BOS")}
        assert set(rows) == {4.5, 6.5, 7.5}
        assert (rows[4.5]["over_price"], rows[4.5]["under_price"]) == (-310, 240)
        assert (rows[6.5]["over_price"], rows[6.5]["under_price"]) == (105, -125)
        assert (rows[7.5]["over_price"], rows[7.5]["under_price"]) == (210, None)     # one side offered: kept as offered
        assert {r["market"] for r in rows.values()} == {"alternate_totals"}

    def test_a_team_total_lands_on_the_side_its_team_plays(self):
        m = {"key": "team_totals", "outcomes": [
            _o("Over", 3.5, 120, "New York Rangers"), _o("Under", 3.5, -145, "New York Rangers"),
            _o("Over", 2.5, -130, "Boston Bruins"), _o("Under", 2.5, 105, "Boston Bruins")]}
        rows = {r["market"]: r for r in h.parse_market(m, "NYR", "BOS")}
        assert (rows["team_totals_home"]["total_line"], rows["team_totals_home"]["over_price"],
                rows["team_totals_home"]["under_price"]) == (3.5, 120, -145)
        assert (rows["team_totals_away"]["total_line"], rows["team_totals_away"]["over_price"],
                rows["team_totals_away"]["under_price"]) == (2.5, -130, 105)

    def test_the_two_teams_at_the_same_number_are_not_paired_with_each_other(self):
        """Both teams at 2.5: the home over must not be stored beside the away under."""
        m = {"key": "team_totals", "outcomes": [
            _o("Over", 2.5, 110, "New York Rangers"), _o("Under", 2.5, -135, "New York Rangers"),
            _o("Over", 2.5, -120, "Boston Bruins"), _o("Under", 2.5, 100, "Boston Bruins")]}
        rows = {r["market"]: r for r in h.parse_market(m, "NYR", "BOS")}
        assert (rows["team_totals_home"]["over_price"], rows["team_totals_home"]["under_price"]) == (110, -135)
        assert (rows["team_totals_away"]["over_price"], rows["team_totals_away"]["under_price"]) == (-120, 100)

    def test_a_team_total_naming_neither_team_is_dropped_not_guessed(self):
        m = {"key": "team_totals", "outcomes": [_o("Over", 2.5, 110, "Seattle Kraken"), _o("Under", 2.5, -135)]}
        assert h.parse_market(m, "NYR", "BOS") == []

    def test_first_period_totals_keep_their_own_market(self):
        m = {"key": "totals_p1", "outcomes": [_o("Over", 1.5, -115), _o("Under", 1.5, -105)]}
        assert h.parse_market(m, "NYR", "BOS") == [
            {"market": "totals_p1", "total_line": 1.5, "over_price": -115, "under_price": -105}]

    def test_an_outcome_with_no_number_or_no_price_is_not_a_row(self):
        m = {"key": "totals_p1", "outcomes": [{"name": "Over", "price": -115}, {"name": "Under", "point": 1.5}]}
        assert h.parse_market(m, "NYR", "BOS") == []


class _Resp:
    def __init__(self, body, status=200):
        self._b, self.status_code = body, status

    def json(self):
        return self._b


class _Meter:
    def __init__(self, room=10_000):
        self.room, self.calls = room, []

    def get(self, url, params):
        self.calls.append(url)
        if url.endswith("/events"):
            return _Resp({"data": [{"id": "ev1", "home_team": "New York Rangers", "away_team": "Boston Bruins",
                                    "commence_time": "2026-01-16T00:10:00Z"}]})
        return _Resp({"timestamp": "2026-01-15T23:05:00Z", "data": {"bookmakers": [
            {"key": "draftkings", "markets": [
                {"key": "alternate_totals", "outcomes": [_o("Over", 5.5, -150), _o("Under", 5.5, 125)]},
                {"key": "h2h", "outcomes": [_o("Over", 1, 1)]}]},            # not asked for: ignored
            {"key": "fanduel", "markets": [
                {"key": "team_totals", "outcomes": [_o("Over", 3.5, 120, "New York Rangers"),
                                                    _o("Under", 3.5, -145, "New York Rangers")]}]}]}})


class _Conn:
    def __init__(self):
        self.rows, self.commits = [], 0

    def executemany(self, sql, rows):
        self.sql = sql
        self.rows += list(rows)

    def commit(self):
        self.commits += 1


GAMES = [{"game_id": "NHL_2026-01-15_BOS_NYR", "home": "NYR", "away": "BOS",
          "start": datetime(2026, 1, 16, 0, 10, tzinfo=timezone.utc)}]


class TestTheRun:
    def test_what_is_bought_is_written_in_the_same_run_with_the_source_marker(self):
        conn, meter = _Conn(), _Meter()
        s = h.pull_date(conn, meter, "2026-01-15", GAMES)
        assert s["events"] == 1 and s["rows"] == 2 and conn.commits == 1
        assert f"'{h.SOURCE}'" in conn.sql and "'NHL'" in conn.sql
        # every book of one snapshot carries the SNAPSHOT's time: simultaneous by construction
        assert {r[3] for r in conn.rows} == {"2026-01-15T23:05:00Z"}
        assert sorted((r[1], r[2], r[4], r[5], r[6]) for r in conn.rows) == [
            ("alternate_totals", "draftkings", 5.5, -150, 125),
            ("team_totals_home", "fanduel", 3.5, 120, -145)]

    def test_a_probe_writes_nothing(self):
        conn = _Conn()
        s = h.pull_date(conn, _Meter(), "2026-01-15", GAMES, apply=False)
        assert s["rows"] == 2 and conn.rows == [] and conn.commits == 0

    def test_it_stops_before_a_game_it_cannot_pay_for(self):
        conn, meter = _Conn(), _Meter(room=29)                # three markets cost 30
        s = h.pull_date(conn, meter, "2026-01-15", GAMES)
        assert s.get("stopped") == "ceiling" and s["events"] == 0 and conn.rows == []
        assert all(u.endswith("/events") for u in meter.calls)

    def test_a_date_already_stored_is_not_bought_again(self):
        class Conn:
            def execute(self, sql, params):
                assert "source = %s" in sql and params[1] == h.SOURCE and "game_id = ANY(%s)" in sql

                class R:
                    def fetchall(s):
                        return [("G1",)]
                return R()
        by_date = {"2026-01-15": [{"game_id": "G1"}, {"game_id": "G2"}], "2026-01-16": [{"game_id": "G3"}]}
        assert h._done_dates(Conn(), by_date) == {"2026-01-15"}

    def test_nothing_that_scores_reads_these_markets(self):
        """The rows share `odds` with the live game lines. They are safe there only
        while no reader names them or pattern-matches 'totals'."""
        for path in list((ROOT / "models").glob("*.py")) + list((ROOT / "features").glob("*.py")) + [
                ROOT / "tracking" / "paper_tracker.py"]:
            src = path.read_text(encoding="utf-8")
            for name in ("team_totals_home", "team_totals_away", "alternate_totals", "totals_p1"):
                assert name not in src, f"{path.name} reads {name}"
            assert "LIKE 'totals" not in src and "LIKE '%totals" not in src, path.name
