"""Parsing Kalshi's tickers — where this silently returned nothing once.

Every failure mode here looks identical to "the market does not exist", which is
the expensive kind of wrong: a coverage collapse reads as an empty board and
nobody questions it. Two have already happened in one session.
"""
from __future__ import annotations

import config
from data.ingestors.kalshi_prop_ingestor import (
    SERIES_MARKET, _event_date, _player,
)


def test_the_event_date_is_searched_not_anchored():
    """`event_ticker` carries the SERIES PREFIX, not the bare event code.

    The first version anchored the date regex at the start of the string, so all
    2,028 markets failed to parse and the probe reported "0 usable ladders" —
    indistinguishable from Kalshi having no prop board at all.
    """
    assert _event_date("KXNFLPASSYDS-26SEP13ATLPIT") == "2026-09-13"
    assert _event_date("KXNFLRECYDS-26SEP09NESEA") == "2026-09-09"
    assert _event_date("KXNFLREC-26SEP14DENKC") == "2026-09-14"
    assert _event_date("KXNFLPASSCOMP-26SEP14DENKC") == "2026-09-14"


def test_a_ticker_with_no_event_code_returns_none_not_a_wrong_date():
    assert _event_date("KXNFLPASSYDS") is None
    assert _event_date("") is None
    assert _event_date(None) is None


def test_an_impossible_date_is_rejected():
    """A bad month or day must not become a plausible-looking timestamp."""
    assert _event_date("KXNFLPASSYDS-26XXX13ATLPIT") is None
    assert _event_date("KXNFLPASSYDS-26FEB99ATLPIT") is None


def test_the_player_comes_from_the_title():
    """The ticker's participant key (`ATLTTAGOVAILOA1`) cannot be turned back
    into a name that matches nflverse; the title carries the real spelling."""
    assert _player("Tua Tagovailoa: 300+ passing yards") == "Tua Tagovailoa"
    assert _player("Ja'Marr Chase: 90+ receiving yards") == "Ja'Marr Chase"
    assert _player("Patrick Mahomes: 27+ passing completions") == "Patrick Mahomes"
    assert _player("RJ Harvey: 8+ receptions") == "RJ Harvey"


def test_a_title_without_a_player_returns_none():
    assert _player("Total touchdowns 3+") is None
    assert _player("") is None
    assert _player(None) is None


def test_only_per_game_player_series_are_mapped():
    """Season-long, head-to-head and "most yards" series share a stat name with
    the per-game ones and are a different proposition entirely. Mapping one by
    accident would price a Sunday prop off a season total."""
    for series in SERIES_MARKET:
        assert not any(bad in series for bad in
                       ("SEASON", "H2H", "MOST", "LEADER", "RECORD", "TEAM")), series
        assert series.startswith("KXNFL")
    for market in SERIES_MARKET.values():
        assert market.startswith("player_"), market


def test_the_mapped_series_are_exactly_the_probed_per_game_player_board():
    """Pin the live 1:1 map. A silent add of KXNFLTD (player + D/ST) or a
    SEASON/H2H ticker would price the wrong proposition; a silent drop of
    KXNFLREC would look like Kalshi still had no receptions market.

    Allowed markets: PROP_MARKETS_NFL, plus player_pass_interceptions which
    the original six already mapped (NCAAF board / not pulled for NFL).
    """
    assert SERIES_MARKET == {
        "KXNFLPASSYDS": "player_pass_yds",
        "KXNFLRECYDS": "player_reception_yds",
        "KXNFLRSHYDS": "player_rush_yds",
        "KXNFLRRYDS": "player_rush_reception_yds",
        "KXNFLPASSTDS": "player_pass_tds",
        "KXNFLPASSINT": "player_pass_interceptions",
        "KXNFLPASSATT": "player_pass_attempts",
        "KXNFLPASSCOMP": "player_pass_completions",
        "KXNFLREC": "player_receptions",
        "KXNFLRSHATT": "player_rush_attempts",
    }
    assert len(SERIES_MARKET) == len(set(SERIES_MARKET.values()))
    allowed = set(config.PROP_MARKETS_NFL) | {"player_pass_interceptions"}
    assert set(SERIES_MARKET.values()) <= allowed
    # Templates that exist on /series but had 0 open per-game player ladders
    # on the 2026-09-14 probe, plus mixed/team/season names.
    for skipped in (
        "KXNFLSACK", "KXNFLTKL", "KXNFLINT", "KXNFLANYTD", "KXNFLTD",
        "KXNFLTEAMSACK", "KXNFLGAMESACK", "KXNFLFIRSTTD",
        "KXNFLSEASONREC", "KXNFLMOSTRECYDS", "KXNFLRECYDSH2H",
    ):
        assert skipped not in SERIES_MARKET, skipped
