"""DK's own feed written into `odds`: the parts that must not go wrong quietly.

The feed exists because the aggregator is too coarse to price a book that
reprices every 15-25s (measured 2026-08-30: 1,890 distinct in-play quotes to its
654, and we saw 29.7% of DK's line changes). Writing a second source into the
table the models read is the highest-leverage change available and also the
easiest to get subtly wrong, so most of these pin INVARIANTS rather than output.
"""
from __future__ import annotations

import inspect
from pathlib import Path

from data.ingestors import dk_direct_feed as f

ROOT = Path(__file__).parent.parent


def _rec(market, line=None, a=-110, b=-110):
    return {"market": market, "line": line, "price_a": a, "price_b": b,
            "event_name": "BOS Red Sox @ NY Yankees"}


# -- the row it writes --------------------------------------------------------

def test_it_writes_as_draftkings_in_play_so_the_scorer_finds_it():
    """CLAUDE.md 6: the models only ever DECIDE on DraftKings. These rows ARE
    DraftKings -- fresher ones -- so _get_live_dk_odds must pick them up with no
    code change, and the invariant is preserved rather than bent."""
    r = f._row_for(_rec("totals", 8.5), "G", "MLB", "T")
    assert r["bookmaker"] == "draftkings"
    assert r["snapshot_type"] == "in_play"


def test_every_row_is_tagged_dk_direct():
    """Without `source` the freshness comparison that justified this work
    becomes circular -- you cannot measure the aggregator's lag against DK once
    both are the same rows in the same table. It is also the rollback."""
    for rec in (_rec("totals", 8.5), _rec("h2h"), _rec("spreads", -1.5)):
        assert f._row_for(rec, "G", "MLB", "T")["source"] == "dk_direct"


def test_totals_map_to_over_under_and_spreads_to_the_home_number():
    t = f._row_for(_rec("totals", 8.5, -105, -115), "G", "MLB", "T")
    assert (t["total_line"], t["over_price"], t["under_price"]) == (8.5, -105, -115)
    # scored_line is always the HOME number for spreads (CLAUDE.md section 4);
    # getting this sign wrong has produced a wrong threshold twice.
    s = f._row_for(_rec("spreads", -1.5, 120, -140), "G", "MLB", "T")
    assert (s["spread_home"], s["home_price"], s["away_price"]) == (-1.5, 120, -140)


def test_h2h_carries_no_line():
    h = f._row_for(_rec("h2h", None, -150, 130), "G", "MLB", "T")
    assert h["total_line"] is None and h["spread_home"] is None
    assert (h["home_price"], h["away_price"]) == (-150, 130)


def test_a_market_we_do_not_understand_is_dropped_not_guessed():
    assert f._row_for(_rec("player_props", 1.5), "G", "MLB", "T") is None


def test_a_priced_market_with_no_line_is_dropped():
    """A total with no number is not a bet, and writing it NULL would make it
    look like a moneyline."""
    assert f._row_for(_rec("totals", None), "G", "MLB", "T") is None
    assert f._row_for(_rec("spreads", None), "G", "MLB", "T") is None


# -- first-seen, not every-poll ----------------------------------------------

def test_the_dedup_key_ignores_the_clock():
    """At 5s polling a per-poll write is ~12 identical rows a minute for a
    number that has not moved -- the same fact 12 times, burying the change."""
    a = f._row_for(_rec("totals", 8.5), "G", "MLB", "2026-08-30T18:00:00Z")
    b = f._row_for(_rec("totals", 8.5), "G", "MLB", "2026-08-30T23:59:59Z")
    assert f._seen_key(a) == f._seen_key(b)


def test_a_price_move_is_a_new_quote():
    a = f._row_for(_rec("totals", 8.5, -110, -110), "G", "MLB", "T")
    b = f._row_for(_rec("totals", 8.5, -115, -105), "G", "MLB", "T")
    assert f._seen_key(a) != f._seen_key(b)


def test_a_line_move_is_a_new_quote():
    a = f._row_for(_rec("totals", 8.5), "G", "MLB", "T")
    b = f._row_for(_rec("totals", 9.5), "G", "MLB", "T")
    assert f._seen_key(a) != f._seen_key(b)


def test_the_same_numbers_on_a_different_game_are_not_deduped():
    a = f._row_for(_rec("totals", 8.5), "GAME_A", "MLB", "T")
    b = f._row_for(_rec("totals", 8.5), "GAME_B", "MLB", "T")
    assert f._seen_key(a) != f._seen_key(b)


# -- refusals and safety ------------------------------------------------------

class _Conn:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, params=None):
        return self

    def fetchall(self):
        return self._rows


def test_an_ambiguous_event_name_writes_nothing():
    """Two candidate games means we do not know which one this price is for.
    Writing a Yankees number onto a Mets row is worse than writing nothing, and
    a dropped game is visible in the `unmatched` counter."""
    rows = [("MLB_2026-08-30_BOS_NYY", "BOS", "NYY"),
            ("MLB_2026-08-30_BOS_NYY_2", "BOS", "NYY")]
    assert f._game_id_for(_Conn(rows), "MLB", "BOS Red Sox @ NY Yankees", {}) is None


def test_an_unmatched_event_name_writes_nothing():
    assert f._game_id_for(_Conn([]), "MLB", "BOS Red Sox @ NY Yankees", {}) is None


def test_an_event_name_with_no_at_sign_is_refused():
    assert f._game_id_for(_Conn([]), "MLB", "some futures market", {}) is None


def test_a_unique_match_resolves():
    rows = [("MLB_2026-08-30_BOS_NYY", "BOS", "NYY"),
            ("MLB_2026-08-30_SD_TB", "SD", "TB")]
    assert f._game_id_for(_Conn(rows), "MLB", "BOS Red Sox @ NY Yankees", {}) \
        == "MLB_2026-08-30_BOS_NYY"


def test_the_insert_rolls_back_per_row():
    """A failed statement poisons a psycopg2 connection, so every later write in
    the pass fails silently behind it -- the backfill_pbp lesson, same day."""
    src = inspect.getsource(f.poll_once)
    assert "conn.rollback()" in src


def test_the_feed_is_off_by_default():
    """Turning it on changes what every live MLB model prices against. That is a
    decision, not a deploy."""
    sched = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'os.environ.get("RUN_DK_DIRECT_FEED", "0") != "0"' in sched
    assert "RUN_DK_DIRECT_FEED=0" in sched, "the off state must log why"


def test_the_source_column_is_created_idempotently():
    joined = " ".join(f.DDL)
    assert "ADD COLUMN IF NOT EXISTS source" in joined
    assert "CREATE INDEX IF NOT EXISTS" in joined


def test_a_run_that_writes_nothing_is_not_reported_as_success():
    """An empty board and a broken feed look identical (CLAUDE.md section 7)."""
    src = inspect.getsource(f.run)
    assert 'level = "info" if totals["written"] or dry_run else "warning"' in src

# -- the team map, which is where a silent mismatch would live ---------------

def test_the_city_abbreviations_that_prefix_matching_gets_wrong():
    """The bug this map replaced. DK writes "NY Yankees" and "NY Mets", so a
    prefix match yields NY for both -- dropping one game or pricing the wrong
    one. "CHI White Sox" is our CWS, which a prefix match never reaches."""
    cases = {"NY Yankees": "NYY", "NY Mets": "NYM", "CHI White Sox": "CWS",
             "CHI Cubs": "CHC", "LA Angels": "LAA", "LA Dodgers": "LAD",
             "WAS Nationals": "WSH", "Athletics": "OAK", "BOS Red Sox": "BOS"}
    for side, abbr in cases.items():
        assert f._abbr_from_dk_side(side) == abbr, side


def test_every_mlb_club_is_mapped_exactly_once():
    assert len(f._MLB_NICKNAMES) == 30
    assert len(set(f._MLB_NICKNAMES.values())) == 30, "two nicknames share an abbr"


def test_the_abbreviations_are_the_ones_the_games_table_uses():
    """A map that is internally consistent but disagrees with our own ids would
    silently match nothing, which looks exactly like a quiet slate."""
    from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS
    ours = set(STATSAPI_TEAM_IDS.values())
    assert set(f._MLB_NICKNAMES.values()) == ours, (
        set(f._MLB_NICKNAMES.values()) ^ ours)


def test_an_unrecognised_club_is_refused_not_guessed():
    assert f._abbr_from_dk_side("Sacramento Whatevers") is None


def test_a_non_mlb_sport_is_refused_rather_than_guessed():
    """NCAAF ids are CFBD school names and need their own map."""
    assert f._game_id_for(_Conn([]), "NCAAF", "Ohio State @ Michigan", {}) is None
