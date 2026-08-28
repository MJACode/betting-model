"""
test_sbr_loader.py — Tests for SBR parsing utilities and DB loading.
"""

import pytest

from data.ingestors.sbr_loader import (
    normalize_team,
    parse_american_odds,
    american_to_decimal,
    _parse_sbr_date,
    _safe_float,
    load_to_db,
)


# ── normalize_team ─────────────────────────────────────────────────────────────

class TestNormalizeTeam:
    def test_exact_mlb_full_name(self):
        assert normalize_team("New York Yankees", "MLB") == "NYY"
        assert normalize_team("Boston Red Sox", "MLB") == "BOS"
        assert normalize_team("Los Angeles Dodgers", "MLB") == "LAD"
        assert normalize_team("Tampa Bay Rays", "MLB") == "TB"

    def test_exact_mlb_short_name(self):
        assert normalize_team("Yankees", "MLB") == "NYY"
        assert normalize_team("Red Sox", "MLB") == "BOS"
        assert normalize_team("Dodgers", "MLB") == "LAD"

    def test_case_insensitive_mlb(self):
        assert normalize_team("new york yankees", "MLB") == "NYY"
        assert normalize_team("NEW YORK YANKEES", "MLB") == "NYY"

    def test_whitespace_stripped(self):
        assert normalize_team("  Boston Red Sox  ", "MLB") == "BOS"

    def test_exact_nhl_full_name(self):
        assert normalize_team("Toronto Maple Leafs", "NHL") == "TOR"
        assert normalize_team("Vegas Golden Knights", "NHL") == "VGK"
        assert normalize_team("Tampa Bay Lightning", "NHL") == "TBL"

    def test_nhl_short_names(self):
        assert normalize_team("Bruins", "NHL") == "BOS"
        assert normalize_team("Maple Leafs", "NHL") == "TOR"

    def test_nhl_utah_hockey_club(self):
        assert normalize_team("Utah Hockey Club", "NHL") == "UTA"
        assert normalize_team("Utah", "NHL") == "UTA"

    def test_nhl_coyotes_franchise(self):
        # Arizona -> Utah is canonicalized to UTA across EVERY season so the
        # franchise has one identity (feature history must not split when a
        # team relocates). Asserting ARI here would re-break that decision.
        assert normalize_team("Arizona Coyotes", "NHL") == "UTA"

    def test_nhl_city_only(self):
        assert normalize_team("Boston", "NHL") == "BOS"

    def test_mlb_cleveland_name_change(self):
        # Both old and new names should map to CLE
        assert normalize_team("Cleveland Guardians", "MLB") == "CLE"
        assert normalize_team("Cleveland Indians", "MLB") == "CLE"


# ── parse_american_odds ────────────────────────────────────────────────────────

class TestParseAmericanOdds:
    def test_positive_string_odds(self):
        assert parse_american_odds("+130") == 130.0

    def test_negative_string_odds(self):
        assert parse_american_odds("-150") == -150.0

    def test_numeric_input(self):
        assert parse_american_odds(110.0) == 110.0
        assert parse_american_odds(-150) == -150.0

    def test_none_returns_none(self):
        assert parse_american_odds(None) is None

    def test_nan_returns_none(self):
        import math
        result = parse_american_odds(float("nan"))
        assert result is None

    @pytest.mark.parametrize("val", ["", "NL", "pk", "PK", "N/A"])
    def test_non_numeric_strings_return_none(self, val):
        assert parse_american_odds(val) is None

    def test_trailing_letters_stripped(self):
        result = parse_american_odds("100EV")
        assert result == 100.0

    def test_spaces_stripped(self):
        assert parse_american_odds(" -110 ") == -110.0


# ── american_to_decimal ────────────────────────────────────────────────────────

class TestAmericanToDecimal:
    def test_even_money(self):
        # +100 → 100/100 + 1 = 2.0
        assert american_to_decimal(100) == pytest.approx(2.0, rel=1e-5)

    def test_negative_heavy_favourite(self):
        # -300 → 100/300 + 1 ≈ 1.3333
        assert american_to_decimal(-300) == pytest.approx(1.333333, rel=1e-4)

    def test_negative_standard(self):
        # -150 → 100/150 + 1 ≈ 1.6667
        assert american_to_decimal(-150) == pytest.approx(1.666667, rel=1e-4)

    def test_positive_underdog(self):
        # +250 → 250/100 + 1 = 3.5
        assert american_to_decimal(250) == pytest.approx(3.5, rel=1e-5)

    def test_none_returns_none(self):
        assert american_to_decimal(None) is None

    def test_decimal_always_greater_than_1(self):
        for odds in [-500, -200, -110, 100, 110, 200, 500]:
            result = american_to_decimal(odds)
            assert result > 1.0, f"Decimal odds should be > 1 for {odds}, got {result}"


# ── _parse_sbr_date ────────────────────────────────────────────────────────────

class TestParseSbrDate:
    def test_8_digit_format(self):
        assert _parse_sbr_date("20190401", 2019) == "2019-04-01"
        assert _parse_sbr_date("20211025", 2021) == "2021-10-25"

    def test_4_digit_mmdd_format(self):
        assert _parse_sbr_date("0401", 2019) == "2019-04-01"
        assert _parse_sbr_date("1025", 2021) == "2021-10-25"

    def test_3_digit_format(self):
        # "401" → zero-padded to "0401" → April 1
        assert _parse_sbr_date("401", 2019) == "2019-04-01"
        assert _parse_sbr_date("930", 2021) == "2021-09-30"

    def test_slash_separators_stripped(self):
        assert _parse_sbr_date("04/01", 2019) == "2019-04-01"

    def test_dash_separators_stripped(self):
        assert _parse_sbr_date("04-01", 2019) == "2019-04-01"

    def test_empty_returns_none(self):
        assert _parse_sbr_date("", 2019) is None

    def test_nan_string_returns_none(self):
        assert _parse_sbr_date("nan", 2019) is None

    def test_invalid_month_returns_none(self):
        # 9999 → month=99 which is invalid
        assert _parse_sbr_date("9999", 2019) is None


# ── _safe_float ────────────────────────────────────────────────────────────────

class TestSafeFloat:
    def test_integer(self):
        assert _safe_float(5) == 5.0

    def test_float(self):
        assert _safe_float(3.14) == pytest.approx(3.14)

    def test_string_number(self):
        assert _safe_float("3.14") == pytest.approx(3.14)

    def test_none_returns_none(self):
        assert _safe_float(None) is None

    def test_non_numeric_string_returns_none(self):
        assert _safe_float("abc") is None

    def test_nan_string_returns_none(self):
        assert _safe_float("nan") is None

    def test_zero(self):
        assert _safe_float(0) == 0.0


# ── load_to_db ─────────────────────────────────────────────────────────────────

class _SqliteCursorShim:
    """sqlite3 cursor that accepts psycopg2-style %s placeholders."""

    def __init__(self, cur):
        self._cur = cur
        self.rowcount = 0

    def execute(self, sql, params=None):
        self._cur.execute(sql.replace("%s", "?"), params or ())
        self.rowcount = self._cur.rowcount
        return self._cur


class _SqliteConnShim:
    """
    Stands in for data.db.DBConnection in these tests. load_to_db became
    Postgres-native (psycopg2 execute_batch against conn._conn), so it can no
    longer run against the raw sqlite3 fixture -- but its SQL is what these
    tests exist to exercise, so the shim adapts rather than the tests dying.
    """

    def __init__(self, sqlite_conn):
        self._sqlite = sqlite_conn
        self._conn = self          # load_to_db does conn._conn.cursor()

    def cursor(self):
        return _SqliteCursorShim(self._sqlite.cursor())

    def commit(self):
        self._sqlite.commit()

    def execute(self, sql, params=None):
        return self._sqlite.execute(sql, params or ())


@pytest.fixture
def loader_conn(db_conn, monkeypatch):
    """db_conn wrapped for load_to_db, with execute_batch looped per-row."""
    import psycopg2.extras as _extras

    def _batch(cursor, sql, rows, page_size=100):
        for r in rows:
            cursor.execute(sql, r)

    monkeypatch.setattr(_extras, "execute_batch", _batch)
    # sbr_loader imported psycopg2 at module level; patch its reference too.
    import data.ingestors.sbr_loader as _mod
    monkeypatch.setattr(_mod.psycopg2.extras, "execute_batch", _batch,
                        raising=False)
    return _SqliteConnShim(db_conn)


class TestLoadToDb:
    def _sample_game(self, game_id="MLB_2021-04-01_BOS_NYY"):
        return {
            "game_id":     game_id,
            "sport":       "MLB",
            "season":      2021,
            "game_date":   "2021-04-01",
            "home_team":   "NYY",
            "away_team":   "BOS",
            "home_score":  5.0,
            "away_score":  3.0,
            "home_win":    1,
            "data_source": "sbr",
            # Current loader field names (the open_line/close_line/ml_home era
            # names predate the datawarehouse CSV format and emit no odds rows)
            "ml_home_open":  -150.0,
            "ml_away_open":  130.0,
            "ml_home_close": -155.0,
            "ml_away_close": 135.0,
            "total_open":    8.5,
            "total_close":   9.0,
            "spread_home":   -1.5,
        }

    def test_inserts_one_game(self, loader_conn):
        games_n, _ = load_to_db([self._sample_game()], loader_conn)
        assert games_n == 1

    def test_game_data_stored_correctly(self, loader_conn):
        load_to_db([self._sample_game()], loader_conn)
        row = loader_conn.execute(
            "SELECT home_team, away_team, home_score, away_score, home_win "
            "FROM games WHERE game_id = ?",
            ("MLB_2021-04-01_BOS_NYY",)
        ).fetchone()
        assert row == ("NYY", "BOS", 5.0, 3.0, 1)

    def test_odds_records_inserted(self, loader_conn):
        _, odds_n = load_to_db([self._sample_game()], loader_conn)
        assert odds_n >= 1

    def test_upsert_updates_score(self, loader_conn):
        game = self._sample_game()
        load_to_db([game], loader_conn)
        game["home_score"] = 7.0
        game["home_win"] = 1
        load_to_db([game], loader_conn)
        row = loader_conn.execute(
            "SELECT home_score FROM games WHERE game_id = ?",
            ("MLB_2021-04-01_BOS_NYY",)
        ).fetchone()
        assert row[0] == 7.0

    def test_empty_list_returns_zeros(self, loader_conn):
        games_n, odds_n = load_to_db([], loader_conn)
        assert games_n == 0
        assert odds_n == 0

    def test_multiple_games_inserted(self, loader_conn):
        games = [
            self._sample_game("MLB_2021-04-01_BOS_NYY"),
            self._sample_game("MLB_2021-04-02_LAD_SF"),
        ]
        games[1]["home_team"] = "SF"
        games[1]["away_team"] = "LAD"
        games_n, _ = load_to_db(games, loader_conn)
        assert games_n == 2
