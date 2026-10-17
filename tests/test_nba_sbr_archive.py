"""The NBA Sportsbook Reviews archive parser (data/ingestors/nba_sbr_archive.py).

Every rule that turns the page into a stored line is pinned here: which row is
the spread and which the total, the HOME-number sign, "pk", refusal of a cell
that is neither, the December -> January year roll, neutral-site orientation,
the synthetic snapshot times, that a re-run writes nothing twice, and that the
bookmaker the rows are written under survives the daily prune.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors import nba_sbr_archive as sbr  # noqa: E402


# ── which cell is the spread, and its sign ───────────────────────────────────

def test_spread_on_the_home_row_is_the_home_team_laying_points():
    # 2018-10-16 OKC @ GSW close: visitor row 220.5 (total), home row 12 (spread)
    assert sbr.classify("220.5", "12") == (-12.0, 220.5)


def test_spread_on_the_visitor_row_is_the_home_team_getting_points():
    # 2018-10-17 MIL @ CHA close: visitor row 3 (spread), home row 222 (total)
    assert sbr.classify("3", "222") == (3.0, 222.0)


@pytest.mark.parametrize("v,h", [("pk", "215"), ("215", "PK"), ("215", "pk")])
def test_pick_em_is_a_zero_spread_on_either_row(v, h):
    spread, total = sbr.classify(v, h)
    assert spread == 0.0 and total == 215.0


@pytest.mark.parametrize("v,h", [
    ("212.5", "1111"),    # 2019-12-09 OKC @ UTA opener: a typo, not a spread
    ("216", "1105"),      # 2019-12-09 LAC @ IND opener
    ("233", "nan"),       # 2019-12-19 HOU @ LAC close: missing
    ("4", "5"),           # two spreads
    ("210", "215"),       # two totals
    ("NL", "210"),        # no line
    ("-3", "210"),        # a signed number is not this page's shape
])
def test_a_column_that_is_not_one_spread_and_one_total_is_refused(v, h):
    assert sbr.classify(v, h) == (None, None)


def test_moneyline_needs_a_real_american_price():
    assert sbr._price("-1100") == -1100
    assert sbr._price("711") == 711
    assert sbr._price("nan") is None
    assert sbr._price("5") is None


# ── the page ─────────────────────────────────────────────────────────────────

def _page(rows: list[list]) -> str:
    head = ["Date", "Rot", "VH", "Team", "1st", "2nd", "3rd", "4th", "Final",
            "Open", "Close", "ML", "2H"]
    body = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>"
                   for r in [head] + rows)
    return f"<html><body><table>{body}</table></body></html>"


ROWS = [
    # Dec 31: home favourite at the open, visitor favourite at the close
    ["1231", "501", "V", "Philadelphia", 21, 21, 24, 21, 87, "208.5", "2", "-120", "106"],
    ["1231", "502", "H", "Boston", 21, 26, 30, 28, 105, "1.5", "211.5", "100", "1"],
    # Jan 2: the year must roll to the next calendar year
    ["102", "503", "V", "OklahomaCity", 23, 24, 32, 21, 100, "223.5", "220.5", "711", "108.5"],
    ["102", "504", "H", "GoldenState", 31, 26, 26, 25, 108, "11.5", "12", "-1100", "4.5"],
]


def test_parse_reads_both_columns_independently_and_rolls_the_year():
    games, unknown, bad = sbr.parse_season(_page(ROWS), 2018)
    assert unknown == [] and bad == {"pairing": 0, "open_refused": 0,
                                     "close_refused": 0, "ml_missing": 0}
    a, b = games
    assert (a["date"], a["away"], a["home"], a["season"]) == ("2018-12-31", "PHI", "BOS", 2019)
    assert (a["spread_open"], a["total_open"]) == (-1.5, 208.5)     # BOS -1.5 at the open
    assert (a["spread_close"], a["total_close"]) == (2.0, 211.5)    # PHI -2 at the close
    assert (a["ml_home"], a["ml_away"]) == (100, -120)
    assert (b["date"], b["away"], b["home"]) == ("2019-01-02", "OKC", "GSW")
    assert (b["spread_close"], b["total_close"]) == (-12.0, 220.5)
    assert (b["home_final"], b["away_final"]) == (108.0, 100.0)


def test_an_unmapped_team_is_reported_and_the_game_dropped():
    rows = [r[:] for r in ROWS]
    rows[0][3] = "Seattle"
    games, unknown, _ = sbr.parse_season(_page(rows), 2018)
    assert unknown == ["Seattle"]
    assert [g["away"] for g in games] == ["OKC"]


def test_a_broken_pair_is_refused_not_misaligned():
    rows = [r[:] for r in ROWS]
    rows[1][1] = "599"                 # home rotation must be visitor + 1
    games, _, bad = sbr.parse_season(_page(rows), 2018)
    assert bad["pairing"] == 1
    assert [g["home"] for g in games] == ["GSW"]


def test_every_team_maps_to_one_of_thirty_distinct_abbreviations():
    assert len(set(sbr.NBA_NAMES.values())) == 30
    assert sbr.team("GoldenState") == "GSW" and sbr.team("LA Clippers") == "LAC"
    assert sbr.team("Seattle") is None


# ── matching to `games` ──────────────────────────────────────────────────────

def _g(**kw):
    base = {"date": "2020-08-01", "season": 2020, "neutral": True, "away": "NOP",
            "home": "UTA", "away_final": 104.0, "home_final": 106.0,
            "spread_open": -4.5, "total_open": 230.0, "spread_close": -5.0,
            "total_close": 229.5, "ml_home": -200, "ml_away": 170,
            "raw_away": [], "raw_home": []}
    base.update(kw)
    return base


def test_direct_match_keeps_the_page_orientation():
    known = {"NBA_2020-08-01_NOP_UTA": (106, 104, "2020-08-01T00:30:00+00:00", 2020)}
    out, n = sbr.match([_g()], known)
    assert n["direct"] == 1 and out[0]["spread_close"] == -5.0
    assert out[0]["commence_time"] == "2020-08-01T00:30:00+00:00"


def test_a_neutral_pair_listed_the_other_way_is_swapped_with_its_signs():
    known = {"NBA_2020-08-01_UTA_NOP": (104, 106, "2020-08-01T00:30:00+00:00", 2020)}
    out, n = sbr.match([_g()], known)
    assert n["neutral_swapped"] == 1
    g = out[0]
    assert (g["away"], g["home"]) == ("UTA", "NOP")
    assert (g["spread_open"], g["spread_close"]) == (4.5, 5.0)   # UTA was the favourite
    assert (g["ml_home"], g["ml_away"]) == (170, -200)
    assert (g["home_final"], g["away_final"]) == (104.0, 106.0)


def test_a_labelled_pair_is_never_swapped():
    known = {"NBA_2020-08-01_UTA_NOP": (104, 106, "2020-08-01T00:30:00+00:00", 2020)}
    out, n = sbr.match([_g(neutral=False)], known)
    assert out == [] and n["labelled_but_swapped"] == 1


def test_a_score_that_disagrees_with_games_is_not_loaded():
    known = {"NBA_2020-08-01_NOP_UTA": (106, 103, "2020-08-01T00:30:00+00:00", 2020)}
    out, n = sbr.match([_g()], known)
    assert out == [] and n["score_disagrees"] == 1


# ── what is written ──────────────────────────────────────────────────────────

def test_snapshot_times_are_noon_on_the_date_and_one_minute_before_tip():
    t = sbr.snapshot_times("2018-10-16", "2018-10-17T00:00:00+00:00")
    assert t == {"open": "2018-10-16T12:00:00Z", "close": "2018-10-16T23:59:00Z"}
    assert sbr.snapshot_times("2020-08-01", "2020-08-01T22:30:00Z")["close"] == "2020-08-01T22:29:00Z"


def test_odds_rows_shape():
    g = {**_g(), "game_id": "NBA_2020-08-01_NOP_UTA",
         "commence_time": "2020-08-01T22:30:00+00:00"}
    rows = {(r[1], r[2]): r for r in sbr.odds_rows(g)}
    assert set(rows) == {("spreads", "open"), ("spreads", "close"), ("totals", "open"),
                         ("totals", "close"), ("h2h", "close")}
    sp = rows[("spreads", "close")]
    assert sp[3] == "2020-08-01T22:29:00Z" and sp[6] == -5.0
    assert sp[4] is None and sp[5] is None             # the page has no spread price
    tot = rows[("totals", "open")]
    assert tot[3] == "2020-08-01T12:00:00Z" and tot[7] == 230.0 and tot[8] is None
    ml = rows[("h2h", "close")]
    assert (ml[4], ml[5]) == (-200, 170)


def test_a_refused_column_writes_no_row_for_it():
    g = {**_g(spread_open=None, total_open=None), "game_id": "x",
         "commence_time": "2020-08-01T22:30:00Z"}
    assert {(r[1], r[2]) for r in sbr.odds_rows(g)} == {
        ("spreads", "close"), ("totals", "close"), ("h2h", "close")}


def test_ml_timing_and_sign_agreement_count_what_they_say():
    flip = _g(spread_open=2.0, spread_close=-1.0, ml_home=-115, ml_away=-105)
    same = _g()
    contra = _g(spread_close=-5.0, ml_home=-108, ml_away=-112)
    assert sbr.ml_timing([flip, same]) == {"favourite_changed": 1,
                                           "ml_follows_close": 1, "ml_follows_open": 0}
    assert sbr.sign_agreement([flip, same, contra]) == {"agree": 2, "disagree": 1}


class _Conn:
    """Stands in for DBConnection: answers the stored-keys read from `stored`,
    records every insert into it."""

    def __init__(self):
        self.stored: list[tuple] = []
        self.selects: list[str] = []

    def execute(self, sql, params=None):
        self.selects.append(sql)
        ids, source = params
        rows = [(r[0], r[1], r[3]) for r in self.stored if r[0] in ids and r[11] == source]

        class _R:
            def fetchall(self_inner):
                return rows
        return _R()

    def executemany(self, sql, payload):
        self.stored += payload

    def commit(self):
        pass


def test_a_rerun_writes_nothing_already_stored():
    g = {**_g(), "game_id": "NBA_2020-08-01_NOP_UTA",
         "commence_time": "2020-08-01T22:30:00Z"}
    c = _Conn()
    assert sbr.load(c, [g]) == 5
    assert all(r[2] == sbr.BOOK and r[11] == sbr.SOURCE for r in c.stored)
    assert sbr.load(c, [g]) == 0
    assert len(c.stored) == 5


def test_stored_rows_are_read_by_game_id_not_by_scanning_for_the_source():
    c = _Conn()
    sbr.stored_keys(c, ["NBA_2020-08-01_NOP_UTA"])
    assert all("game_id = ANY(" in s for s in c.selects)


def test_the_bookmaker_these_rows_use_survives_the_daily_prune():
    from data.prune_odds import PROTECTED_BOOKMAKERS, _unprotected, protected_for
    assert sbr.BOOK in PROTECTED_BOOKMAKERS
    assert sbr.BOOK in protected_for("odds")
    params: dict = {}
    pred = _unprotected(params, table="odds")
    assert "bookmaker NOT IN %(protected)s" in pred
    assert sbr.BOOK in params["protected"]
