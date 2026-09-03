"""
The accented-name prop gap (2026-08-30).

Roster feeds spell names with diacritics ("José Ramírez"); the Odds API writes
them flat ("Jose Ramirez"). _get_prop_dk_odds matched on the exact string, so
every accented player was skipped in every priced prop market — 20 of the 22
accented batters in that day's confirmed MLB lineups had a DraftKings home-run
price and no pick at all.

These pin the fold rule, the fallback lookup, and the two things the fallback
must NOT do: guess between two players who differ only by suffix, and hand
line shopping the roster's spelling instead of the feed's.
"""

import re
from pathlib import Path

import pytest

from data.name_match import normalize_player_name, resolve_feed_name
from models.scorer import _get_prop_dk_odds

REPO = Path(__file__).resolve().parent.parent

GAME = "MLB_2026-08-30_KC_CLE"
MARKET = "batter_home_runs"


# ── the fold rule ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("José Ramírez",      "jose ramirez"),
    ("Ronald Acuña Jr.",  "ronald acuna"),
    ("Teoscar Hernández", "teoscar hernandez"),
    ("Andrés Giménez",    "andres gimenez"),
    ("Jung-Hoo Lee",      "jung hoo lee"),
    ("Ryan O'Hearn",      "ryan ohearn"),
    ("  Pete   Alonso ",  "pete alonso"),
    ("Ken Griffey III",   "ken griffey"),
    ("", ""),
    (None, ""),
])
def test_normalize_folds_only_spelling(raw, expected):
    assert normalize_player_name(raw) == expected


def test_normalize_never_merges_two_different_players():
    # Same surname, different person — the fold must keep them apart.
    assert normalize_player_name("Luis García") != normalize_player_name("Luis Castillo")
    assert normalize_player_name("Willy Adames") != normalize_player_name("Will Adames")


# ── resolution ───────────────────────────────────────────────────────────────

def test_resolve_finds_the_flat_spelling():
    assert resolve_feed_name("José Ramírez", ["Aaron Judge", "Jose Ramirez"]) == "Jose Ramirez"


def test_resolve_refuses_an_ambiguous_suffix_match():
    """Dropping "Jr." can make two roster entries fold alike. A wrong price on
    the wrong player is worse than no pick, so ambiguity stays a miss."""
    assert resolve_feed_name("Luis García Jr.", ["Luis Garcia", "Luis Garcia Jr."]) is None


def test_resolve_misses_cleanly_when_the_market_is_not_listed():
    assert resolve_feed_name("José Ramírez", ["Aaron Judge"]) is None
    assert resolve_feed_name("", ["Jose Ramirez"]) is None


# ── the lookup ───────────────────────────────────────────────────────────────

class FakeConn:
    """player_prop_odds keyed by the FEED's spelling, like production."""

    def __init__(self, quotes: dict):
        self._quotes = quotes
        self._result = None

    def execute(self, sql, params=None):
        if "DISTINCT player_name" in sql:
            self._result = [(n,) for n in self._quotes]
        else:
            _game, name, _market = params
            q = self._quotes.get(name)
            self._result = [q] if q else []
        return self

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return self._result


QUOTE = (0.5, 490, -700, "https://dk/over", "https://dk/under")


def test_exact_spelling_still_takes_the_fast_path():
    conn = FakeConn({"Aaron Judge": QUOTE})
    odds = _get_prop_dk_odds(conn, GAME, "Aaron Judge", MARKET)
    assert odds["line"] == 0.5 and odds["over_price"] == 490
    assert odds["player_name"] == "Aaron Judge"


def test_accented_roster_name_matches_the_flat_feed_name():
    conn = FakeConn({"Jose Ramirez": QUOTE})
    odds = _get_prop_dk_odds(conn, GAME, "José Ramírez", MARKET)
    assert odds is not None, "accented player skipped — the 2026-08-30 gap is back"
    assert odds["over_price"] == 490


def test_the_feed_spelling_is_returned_for_line_shopping():
    """_best_prop_price queries player_prop_odds by name, so it must be handed
    the name the odds rows use — not the roster's accented one."""
    conn = FakeConn({"Jose Ramirez": QUOTE})
    odds = _get_prop_dk_odds(conn, GAME, "José Ramírez", MARKET)
    assert odds["player_name"] == "Jose Ramirez"


def test_an_unlisted_player_is_still_a_miss():
    conn = FakeConn({"Aaron Judge": QUOTE})
    assert _get_prop_dk_odds(conn, GAME, "José Ramírez", MARKET) is None


def test_ambiguity_is_a_miss_not_a_guess():
    conn = FakeConn({"Luis Garcia": QUOTE, "Luis Garcia Jr.": QUOTE})
    assert _get_prop_dk_odds(conn, GAME, "Luis García Jr.", MARKET) is None


# ── every prop path uses the resolved spelling ───────────────────────────────

def test_every_prop_lane_keys_line_shopping_on_the_resolved_name():
    """MLB, WNBA, NBA, NFL and the pitcher lane all build _best_ctx right after
    _get_prop_dk_odds. A lane that kept the roster spelling would line-shop a
    name the odds table doesn't hold (§1b: one gap fixed in one sport is a gap
    left in five)."""
    src = (REPO / "models" / "scorer.py").read_text(encoding="utf-8")
    # Matched as a PREFIX, not the whole call: the lookup gained a
    # commence_time argument on 2026-09-03 (the pre-game price bound), and a
    # test that pins the exact arity breaks on every future signature change
    # while telling us nothing about the property it exists to defend.
    lanes = len(re.findall(
        r"_get_prop_dk_odds\(conn, game_id, player_name, market[,)]", src))
    resolved = len(re.findall(
        r'_best_ctx = \(game_id,\s*\n\s*\(prop_odds or \{\}\)\.get\("player_name"\) or player_name,',
        src,
    ))
    assert lanes == resolved == 5, f"{lanes} prop lanes, {resolved} using the resolved name"
