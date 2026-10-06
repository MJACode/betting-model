"""NCAAF ingest must not mint a second games row for a game that already exists.

Measured 2026-10-06 (clusters2026): 112 games had 2-3 rows, 117 extra rows.
59 are an ET date against the UTC date CFBD preloaded on 2026-08-29. A 10:30pm
ET kickoff is the next calendar day in UTC. 3 are home/away swapped at a
neutral site (Army/Navy, Kansas/Arizona State, Virginia/West Virginia).

These tests use those rows. They do not touch the database.
"""

import inspect
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from loguru import logger

import data.ingestors.cfbd_ingestor as cf
import data.ingestors.odds_ingestor as oi
from data.ingestors.cfbd_ingestor import parse_games, retain_existing_cfbd_ids
from data.ingestors.odds_ingestor import resolve_ncaaf_game_id

# Memphis @ UNLV, commence 2026-08-30T02:19Z = 10:19pm ET on the 29th.
# The UTC twin is the CFBD preload; the ET id is what the odds ingestor mints.
MEMPHIS_UTC = "NCAAF_2026-08-30_memphis_unlv"
MEMPHIS_ET = "NCAAF_2026-08-29_memphis_unlv"
# Fresno State @ USC, 2026-09-05T01:00Z = 9:00pm ET on the 4th.
FRESNO_ET_DATE = "2026-09-04"
# Army @ Navy on the odds feed; CFBD has Navy @ Army. Same calendar day.
ARMY_NAVY_ODDS = "NCAAF_2026-12-12_army_navy"
ARMY_NAVY_CFBD = "NCAAF_2026-12-12_navy_army"


def _schools(monkeypatch):
    monkeypatch.setattr(cf, "_SCHOOL_CACHE", [
        {"school": "UNLV", "mascot": "Rebels", "alt": []},
        {"school": "Memphis", "mascot": "Tigers", "alt": []},
        {"school": "Army", "mascot": "Black Knights", "alt": []},
        {"school": "Navy", "mascot": "Midshipmen", "alt": []},
        {"school": "USC", "mascot": "Trojans", "alt": []},
        {"school": "Fresno State", "mascot": "Bulldogs", "alt": []},
    ])


def _event(home, away, commence):
    return {
        "id": "e1",
        "commence_time": commence,
        "home_team": home,
        "away_team": away,
        "bookmakers": [{
            "key": "draftkings",
            "markets": [{"key": "h2h", "last_update": commence, "outcomes": [
                {"name": home, "price": -150},
                {"name": away, "price": 130},
            ]}],
        }],
    }


def _row(game_id, game_date, home, away):
    return {"game_id": game_id, "game_date": game_date,
            "home_team": home, "away_team": away}


class _Conn:
    def __init__(self, rows, boom=False):
        self.rows = rows
        self.boom = boom
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        if self.boom:
            raise RuntimeError("no database")
        self.sql = sql
        self.params = params
        rows = self.rows

        class _Cur:
            def fetchall(_self):
                return rows

        return _Cur()


def _memphis_parsed():
    return parse_games([{
        "id": 99, "season": 2026, "week": 1,
        "startDate": "2026-08-30T02:19:00.000Z",
        "homeTeam": "UNLV", "awayTeam": "Memphis",
        "homeClassification": "fbs", "awayClassification": "fbs",
    }])


# ── both ingestors, one id ────────────────────────────────────────────────────

@pytest.mark.parametrize("commence", [
    "2026-08-30T02:19:00Z",   # measured Memphis @ UNLV, 10:19pm ET
    "2026-08-30T02:30:00Z",   # 10:30pm ET = next-day UTC
])
def test_late_kickoff_reuses_the_utc_row_both_ingestors_share(commence, monkeypatch):
    """The UTC row is the only one stored and it has team logs. CFBD keeps
    it; the odds path looks it up instead of minting the ET id."""
    _schools(monkeypatch)
    rows = _memphis_parsed()
    retain_existing_cfbd_ids(rows, {MEMPHIS_UTC})

    existing = [_row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis")]
    conn = _Conn([(MEMPHIS_UTC, date(2026, 8, 30), "UNLV", "Memphis")])
    reuse = oi._ncaaf_resolver(conn, "2026-08-29")
    games, odds = oi._process_events(
        [_event("UNLV Rebels", "Memphis Tigers", commence)],
        "NCAAF", "open", "2026-08-29T12:00:00-04:00",
        reuse_game_id=reuse,
    )
    assert rows[0]["game_id"] == MEMPHIS_UTC
    assert games[0]["game_id"] == MEMPHIS_UTC
    assert games[0]["home_team"] == "UNLV"
    assert games[0]["away_team"] == "Memphis"
    assert {o["game_id"] for o in odds} == {MEMPHIS_UTC}
    # Exact home/away. The book's home price stays on home_price.
    assert odds[0]["home_price"] == -150
    assert odds[0]["away_price"] == 130
    assert resolve_ncaaf_game_id(existing, "UNLV", "Memphis", "2026-08-29") == MEMPHIS_UTC
    # A game row is still emitted. NCAAF is not the NFL: this ingestor writes
    # the schedule when it has to, and the upsert does not overwrite a score.
    assert len(games) == 1


def test_a_fresh_late_kickoff_is_the_et_id_from_both_ingestors(monkeypatch):
    """Nothing stored. Both sides date the 10:19pm ET kick on the 29th."""
    _schools(monkeypatch)
    rows = _memphis_parsed()
    retain_existing_cfbd_ids(rows, set())
    games, odds = oi._process_events(
        [_event("UNLV Rebels", "Memphis Tigers", "2026-08-30T02:19:00Z")],
        "NCAAF", "open", "2026-08-29T12:00:00-04:00",
        reuse_game_id=lambda *_a: None,
    )
    assert rows[0]["game_id"] == MEMPHIS_ET
    assert rows[0]["game_date"] == "2026-08-29"
    assert games[0]["game_id"] == MEMPHIS_ET
    assert games[0]["game_date"] == "2026-08-29"
    assert {o["game_id"] for o in odds} == {MEMPHIS_ET}


def test_a_failed_lookup_returns_none_and_does_not_skip_the_sport():
    """Unlike the NFL resolver, a lookup we could not build is permission to
    mint, not to drop the slate."""
    assert oi._ncaaf_resolver(_Conn([], boom=True), "2026-09-01") is None


# ── swapped neutral site ──────────────────────────────────────────────────────

def test_swapped_home_away_at_a_neutral_site_matches_the_existing_row(monkeypatch):
    """Army/Navy 2026-12-12. Odds lists Army @ Navy. CFBD preloaded Navy @ Army.
    One row, the one that already exists."""
    _schools(monkeypatch)
    conn = _Conn([(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy")])
    reuse = oi._ncaaf_resolver(conn, "2026-09-01")
    games, odds = oi._process_events(
        [_event("Navy Midshipmen", "Army Black Knights", "2026-12-12T20:00:00Z")],
        "NCAAF", "open", "2026-09-01T12:00:00-04:00",
        reuse_game_id=reuse,
    )
    assert games[0]["game_id"] == ARMY_NAVY_CFBD
    # The stub agrees with the stored row (home Army), not the book's home.
    assert games[0]["home_team"] == "Army"
    assert games[0]["away_team"] == "Navy"
    assert {o["game_id"] for o in odds} == {ARMY_NAVY_CFBD}
    # Book home was Navy -150. Stored home is Army, so Army's +130 is home_price.
    assert odds[0]["home_price"] == 130
    assert odds[0]["away_price"] == -150
    # The load window from the day Army-Navy first appeared on the board
    # (2026-09-01) has to reach the kickoff. The NFL's +10 days does not.
    assert "NCAAF" in conn.sql
    assert conn.params[1] >= "2026-12-12"
    anchor = date(2026, 9, 1)
    assert conn.params == (
        (anchor - timedelta(days=oi._NCAAF_REUSE_LOOKBACK_DAYS)).isoformat(),
        (anchor + timedelta(days=oi._NCAAF_REUSE_LOOKAHEAD_DAYS)).isoformat(),
    )


def test_when_both_orientations_exist_the_exact_order_wins():
    """Both Army/Navy rows are already stored. The odds event matches
    army_navy exactly and navy_army swapped. Exact order wins, and the
    ambiguity is logged."""
    games = [
        _row(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy"),
        _row(ARMY_NAVY_ODDS, "2026-12-12", "Navy", "Army"),
    ]
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(games, "Navy", "Army", "2026-12-12")
    finally:
        logger.remove(sink)
    assert chosen == ARMY_NAVY_ODDS
    assert seen and ARMY_NAVY_CFBD in seen[0] and ARMY_NAVY_ODDS in seen[0]


def test_exact_orientation_beats_a_nearer_swapped_row():
    """Sort is (exact order, then nearest date). A swapped row on the ET
    date loses to an exact-order row one day away."""
    games = [
        _row(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy"),
        _row("NCAAF_2026-12-11_army_navy", "2026-12-11", "Navy", "Army"),
    ]
    assert resolve_ncaaf_game_id(games, "Navy", "Army", "2026-12-12") == \
        "NCAAF_2026-12-11_army_navy"


# ── +/- 1 day window ──────────────────────────────────────────────────────────

def _fresno(game_date):
    return _row(f"NCAAF_{game_date}_fresno-state_usc", game_date, "USC", "Fresno State")


@pytest.mark.parametrize("game_date,expected", [
    ("2026-09-02", None),                                          # 2 days before
    ("2026-09-03", "NCAAF_2026-09-03_fresno-state_usc"),          # 1 day before
    ("2026-09-04", "NCAAF_2026-09-04_fresno-state_usc"),          # the ET date
    ("2026-09-05", "NCAAF_2026-09-05_fresno-state_usc"),          # the UTC twin
    ("2026-09-06", None),                                          # 2 days after
])
def test_match_window_is_one_day_either_side_of_the_et_date(game_date, expected):
    """Fresno State @ USC kicks 2026-09-05T01:00Z, which is 2026-09-04 in ET.
    The boundary is the day, not 'about a day'."""
    assert resolve_ncaaf_game_id(
        [_fresno(game_date)], "USC", "Fresno State", FRESNO_ET_DATE,
    ) == expected


def test_a_different_opponent_inside_the_window_does_not_match():
    ucla = _row("NCAAF_2026-09-04_ucla_california", "2026-09-04",
                "California", "UCLA")
    assert resolve_ncaaf_game_id(
        [ucla], "USC", "Fresno State", FRESNO_ET_DATE,
    ) is None


def test_two_exact_rows_prefer_the_nearest_date_and_log_it():
    """Both Memphis rows. ET kickoff date is the 29th. The 29th wins over
    the 30th, and the warning names both."""
    games = [
        _row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis"),
        _row(MEMPHIS_ET, "2026-08-29", "UNLV", "Memphis"),
    ]
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(games, "UNLV", "Memphis", "2026-08-29")
    finally:
        logger.remove(sink)
    assert chosen == MEMPHIS_ET
    assert len(seen) == 1
    assert MEMPHIS_UTC in seen[0] and MEMPHIS_ET in seen[0]


def test_a_single_match_is_not_logged_as_ambiguous():
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        chosen = resolve_ncaaf_game_id(
            [_row(MEMPHIS_UTC, "2026-08-30", "UNLV", "Memphis")],
            "UNLV", "Memphis", "2026-08-29",
        )
    finally:
        logger.remove(sink)
    assert chosen == MEMPHIS_UTC
    assert seen == []


# ── swapped-only reuse flips every side the writers store ────────────────────

def _inserts(src: str) -> dict[str, list[str]]:
    """Every INSERT column list in odds_ingestor, keyed by table.

    Parsed from the source. A hand-kept list of columns would stay green
    when a new home/away column was added to the INSERT and not flipped.
    """
    found: dict[str, list[str]] = {}
    for match in re.finditer(
            r"INSERT INTO\s+(\w+)\s*\((.*?)\)", src, re.S | re.IGNORECASE):
        table = match.group(1)
        cols = [c.strip() for c in match.group(2).split(",") if c.strip()]
        previous = found.get(table)
        if previous is not None and previous != cols:
            raise AssertionError(f"{table} has two different INSERT column lists")
        found[table] = cols
    return found


def _book_oriented(columns: list[str]) -> dict:
    """One distinct value per column, in the book's home/away orientation."""
    row = {}
    for col in columns:
        partner = oi._side_partner(col)
        if partner and partner in columns:
            row[col] = f"book:{col}"
        elif partner:
            row[col] = -3.5
        else:
            row[col] = f"neutral:{col}"
    return row


def _expect_flipped(book: dict, columns: list[str]) -> dict:
    expected = dict(book)
    colset = set(columns)
    done = set()
    for col in columns:
        if col in done:
            continue
        partner = oi._side_partner(col)
        if partner is None:
            continue
        if partner in colset:
            expected[col] = book[partner]
            expected[partner] = book[col]
            done.add(col)
            done.add(partner)
        else:
            expected[col] = -book[col]
            done.add(col)
    return expected


def _army_navy_event():
    """Book lists Army @ Navy. Navy -3.5, Army +3.5. Total 42.5 is the same either way."""
    home, away = "Navy Midshipmen", "Army Black Knights"
    when = "2026-12-12T18:00:00Z"
    return {
        "id": "army-navy",
        "commence_time": "2026-12-12T20:00:00Z",
        "home_team": home,
        "away_team": away,
        "bookmakers": [{
            "key": "draftkings",
            "markets": [
                {"key": "h2h", "last_update": when, "outcomes": [
                    {"name": home, "price": -180, "link": "ml-navy", "sid": "ml-navy-sid"},
                    {"name": away, "price": 155, "link": "ml-army", "sid": "ml-army-sid"},
                ]},
                {"key": "spreads", "last_update": when, "outcomes": [
                    {"name": home, "price": -115, "point": -3.5,
                     "link": "sp-navy", "sid": "sp-navy-sid"},
                    {"name": away, "price": -105, "point": 3.5,
                     "link": "sp-army", "sid": "sp-army-sid"},
                ]},
                {"key": "totals", "last_update": when, "outcomes": [
                    {"name": "Over", "price": -108, "point": 42.5,
                     "link": "over", "sid": "over-sid"},
                    {"name": "Under", "price": -112, "point": 42.5,
                     "link": "under", "sid": "under-sid"},
                ]},
            ],
        }],
    }


def _run(monkeypatch, stored, events):
    _schools(monkeypatch)
    conn = _Conn(stored)
    reuse = oi._ncaaf_resolver(conn, "2026-12-01")
    seen = []
    sink = logger.add(lambda m: seen.append(m.record["message"]),
                      level="WARNING", format="{message}")
    try:
        games, odds = oi._process_events(
            events, "NCAAF", "open", "2026-12-01T12:00:00-05:00",
            reuse_game_id=reuse,
        )
    finally:
        logger.remove(sink)
    return games, odds, [m for m in seen if "flipped side-specific" in m]


def test_every_side_keyed_write_column_flips_on_a_swapped_reuse_and_not_on_an_exact_one(
        monkeypatch):
    """Army @ Navy on the book, Navy @ Army stored (the measured neutral-site
    swap). Every home/away column the odds writers INSERT is flipped.
    The same event against an exact-orientation row is not.

    The column list is parsed from the INSERT statements. Adding a
    side-specific column to one of them without a flip fails this test.
    """
    src = Path(oi.__file__).read_text(encoding="utf-8")
    inserts = _inserts(src)
    assert inserts, "odds_ingestor no longer has an INSERT to enumerate"
    process_src = inspect.getsource(oi._process_events)
    assert "flip_sides(" in process_src
    flipped_lists = {oi._GAMES_WRITE_COLS, oi._ODDS_WRITE_COLS}

    for table, cols in inserts.items():
        side = [c for c in cols if oi._side_partner(c)]
        if not side:
            continue
        assert tuple(cols) in flipped_lists, (
            f"{table} writes side-keyed columns {side} and the reuse path "
            f"does not flip that INSERT"
        )
        book = _book_oriented(cols)
        flipped = oi.flip_sides(book, cols)
        expected = _expect_flipped(book, cols)
        for col in cols:
            assert flipped[col] == expected[col], col
            partner = oi._side_partner(col)
            if partner is None:
                assert flipped[col] == book[col]
            elif partner in cols:
                assert flipped[col] == book[partner]
                assert flipped[col] != book[col]
            else:
                assert flipped[col] == -book[col]

    event = _army_navy_event()
    swapped_games, swapped_odds, swapped_warn = _run(
        monkeypatch,
        [(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy")],
        [event],
    )
    exact_games, exact_odds, exact_warn = _run(
        monkeypatch,
        [(ARMY_NAVY_ODDS, "2026-12-12", "Navy", "Army")],
        [event],
    )

    assert swapped_games[0]["game_id"] == ARMY_NAVY_CFBD
    assert exact_games[0]["game_id"] == ARMY_NAVY_ODDS
    assert swapped_warn == [
        "NCAAF: flipped side-specific lines onto 1 "
        "reused games row(s) stored with home/away reversed from the "
        f"book: [{ARMY_NAVY_CFBD!r}]"
    ]
    assert exact_warn == []

    odds_side = [c for c in oi._ODDS_WRITE_COLS if oi._side_partner(c)]
    games_side = [c for c in oi._GAMES_WRITE_COLS if oi._side_partner(c)]
    for col in oi._GAMES_WRITE_COLS:
        assert col in swapped_games[0] and col in exact_games[0]
    for col in games_side:
        partner = oi._side_partner(col)
        assert swapped_games[0][col] == exact_games[0][partner]
        assert swapped_games[0][col] != exact_games[0][col]

    by_market = lambda rows: {r["market"]: r for r in rows}
    swapped_by = by_market(swapped_odds)
    exact_by = by_market(exact_odds)
    assert set(swapped_by) == {"h2h", "spreads", "totals"}
    for market, exact in exact_by.items():
        got = swapped_by[market]
        for col in oi._ODDS_WRITE_COLS:
            assert col in got and col in exact
        for col in odds_side:
            partner = oi._side_partner(col)
            if partner and partner in oi._ODDS_WRITE_COLS:
                assert got[col] == exact[partner], (market, col)
            else:
                if exact[col] is None:
                    assert got[col] is None
                else:
                    assert got[col] == -exact[col], (market, col)
        for col in oi._ODDS_WRITE_COLS:
            # game_id is the reused row, so the two cases point at different
            # ids on purpose. Every other non-side column (the total, the
            # draw, the snapshot) is the book's number and must match.
            if oi._side_partner(col) is None and col != "game_id":
                assert got[col] == exact[col], (market, col)

    # The book's home is Navy -3.5 / -180. Stored home is Army, so the
    # spread stored for that row is +3.5 and Army's moneyline is home_price.
    assert exact_by["spreads"]["spread_home"] == -3.5
    assert swapped_by["spreads"]["spread_home"] == 3.5
    assert swapped_by["spreads"]["home_price"] == -105
    assert swapped_by["spreads"]["away_price"] == -115
    assert swapped_by["spreads"]["home_link"] == "sp-army"
    assert swapped_by["spreads"]["away_sid"] == "sp-navy-sid"
    assert swapped_by["h2h"]["home_price"] == 155
    assert swapped_by["h2h"]["away_price"] == -180
    assert swapped_by["h2h"]["home_link"] == "ml-army"
    assert swapped_by["h2h"]["away_sid"] == "ml-navy-sid"
    assert swapped_by["totals"]["total_line"] == 42.5
    assert swapped_by["totals"]["over_price"] == -108
    assert swapped_by["totals"]["under_price"] == -112
    assert swapped_by["totals"]["over_link"] == "over"
    assert exact_by["totals"]["total_line"] == 42.5
    assert exact_by["h2h"]["home_price"] == -180
    assert exact_by["spreads"]["spread_home"] == -3.5
    assert exact_games[0]["home_team"] == "Navy"
    assert swapped_games[0]["home_team"] == "Army"
    assert swapped_games[0]["away_team"] == "Navy"


def test_one_warning_counts_every_swapped_reuse_in_the_run(monkeypatch):
    event = _army_navy_event()
    second = dict(event)
    second["id"] = "army-navy-2"
    _games, _odds, warnings = _run(
        monkeypatch,
        [(ARMY_NAVY_CFBD, "2026-12-12", "Army", "Navy")],
        [event, second],
    )
    assert warnings == [
        "NCAAF: flipped side-specific lines onto 2 "
        "reused games row(s) stored with home/away reversed from the "
        f"book: [{ARMY_NAVY_CFBD!r}, {ARMY_NAVY_CFBD!r}]"
    ]
