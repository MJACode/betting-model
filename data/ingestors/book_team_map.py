"""One place that turns a sportsbook's team string into our team abbreviation.

Every direct book feed has to solve this, and it is the step where a mistake is
both easy and unrecoverable: a wrongly matched game writes one team's price onto
another team's row, and nothing downstream can tell. A dropped game only costs a
market and shows up in a counter.

TWO BUGS ALREADY LIVE IN THIS FILE'S HISTORY, both caught by tests rather than
by review, which is why the map is shared rather than copied per book:

  1. Matching on the abbreviation PREFIX of the book's own string. DraftKings
     writes "NY Yankees" and "NY Mets" -- both yield "NY", so one game is
     dropped or, worse, the wrong one matches. "CHI White Sox" is our CWS, which
     a prefix never reaches at all.
  2. The nickname map that replaced it said ATH for the Athletics, where the
     games table actually uses OAK. A map that is internally tidy but disagrees
     with our own ids matches nothing -- which on a dashboard looks exactly like
     a quiet slate.

NICKNAMES ARE THE RELIABLE KEY. They are unique across MLB and stable across the
formats different books use: DraftKings writes "BOS Red Sox", Bovada writes
"Boston Red Sox", and both end in the nickname. So the match is a SUFFIX match
on the nickname, and anything unrecognised returns None rather than a guess.
"""
from __future__ import annotations

# Keyed on nickname, valued with the abbreviation the `games` table uses.
# `tests/test_book_team_map.py` pins these values against the abbreviations that
# actually appear in the database, so the two cannot drift.
MLB_NICKNAMES: dict[str, str] = {
    "diamondbacks": "ARI", "braves": "ATL", "orioles": "BAL", "red sox": "BOS",
    "cubs": "CHC", "white sox": "CWS", "reds": "CIN", "guardians": "CLE",
    "rockies": "COL", "tigers": "DET", "astros": "HOU", "royals": "KC",
    "angels": "LAA", "dodgers": "LAD", "marlins": "MIA", "brewers": "MIL",
    "twins": "MIN", "mets": "NYM", "yankees": "NYY",
    # OAK, not ATH: the book dropped the city after the move, but our games
    # table still keys the club as OAK and it is the authority here.
    "athletics": "OAK",
    "phillies": "PHI", "pirates": "PIT", "padres": "SD", "giants": "SF",
    "mariners": "SEA", "cardinals": "STL", "rays": "TB", "rangers": "TEX",
    "blue jays": "TOR", "nationals": "WSH",
}


def abbr_from_team_string(side: str) -> str | None:
    """"BOS Red Sox" -> "BOS". "Boston Red Sox" -> "BOS". Unknown -> None.

    Longest nickname first, so "White Sox" is not shadowed by a shorter entry
    that happens to be a suffix of it.
    """
    if not side:
        return None
    s = " ".join(str(side).split()).lower()
    for nickname in sorted(MLB_NICKNAMES, key=len, reverse=True):
        if s.endswith(nickname):
            return MLB_NICKNAMES[nickname]
    return None


def split_matchup(event_name: str) -> tuple[str | None, str | None]:
    """"<away> @ <home>" -> (away_abbr, home_abbr). Either may be None.

    Both DraftKings and Bovada use "away @ home"; a book that does not will need
    its own splitter rather than a tweak to this one, because silently reversing
    home and away is the same class of unrecoverable error as matching the wrong
    game.
    """
    if not event_name or "@" not in event_name:
        return None, None
    away, home = (s.strip() for s in event_name.split("@", 1))
    return abbr_from_team_string(away), abbr_from_team_string(home)


# A resolution is re-read after this long. Per event NAME for the whole run
# was wrong on a doubleheader day: both games share the name, so the first
# answer (game 1, or None while both rows were unscored) stuck after game 1
# ended and game 2 went live.
_CACHE_TTL_S = 10 * 60


def resolve_game_id(conn, sport: str, event_name: str, slate_dates: list[str],
                    cache: dict) -> str | None:
    """Our game_id for a book's LIVE event name, or None when it is not unique.

    Refuses on ambiguity by design. MLB only: NCAAF ids are CFBD school names
    and would need their own map, so this returns None rather than pretending.

    A doubleheader has two unscored rows for one name (base and `_G2`). These
    feeds are in-play only, so the game meant is the one that is LIVE: the
    unscored row whose first pitch has happened. Exactly one such row
    resolves; anything else is None. Only a single-row answer is cached, and
    only for _CACHE_TTL_S; a doubleheader answer, or a refusal, is re-read
    every time.
    """
    import time
    hit = cache.get(event_name)
    if isinstance(hit, tuple) and time.monotonic() - hit[1] < _CACHE_TTL_S:
        return hit[0]
    if sport != "MLB":
        return None

    away_abbr, home_abbr = split_matchup(event_name)
    if not away_abbr or not home_abbr:
        return None

    rows = conn.execute("""
        SELECT game_id, away_team, home_team, first_pitch_at FROM games
        WHERE sport = %s AND game_date = ANY(%s) AND home_score IS NULL
    """, (sport, slate_dates)).fetchall()
    hits = [(r[0], r[3] if len(r) > 3 else None) for r in rows
            if (r[1] or "").upper() == away_abbr and (r[2] or "").upper() == home_abbr]
    if len(hits) == 1:
        cache[event_name] = (hits[0][0], time.monotonic())
        return hits[0][0]
    live = [g for g, fp in hits if fp]
    return live[0] if len(hits) > 1 and len(live) == 1 else None
