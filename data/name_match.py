"""
data/name_match.py — one normalized form for a player's name, shared by every
sport's prop path.

The roster feeds (MLB Stats API, and the NBA/WNBA/NFL game logs) spell names
with diacritics — "José Ramírez", "Ronald Acuña Jr.", "Luis García Jr.". The
Odds API spells the same player in plain ASCII — "Jose Ramirez". Every prop
odds lookup was an exact string match on player_name, so the two spellings
never met and the player was simply skipped:

    2026-08-30   20 of the 22 accented batters in the day's confirmed lineups
                 had a DraftKings home-run price and no pick at all.
    August 2026  16 of 570 accented lineup slots were ever scored (2.8%),
                 against 3,580 of 6,108 plain-ASCII slots (58.6%).

That is ~9% of every MLB slate — every Hernández, Ramírez, Acuña, Díaz —
silently absent from every priced prop market since the feature shipped.

The rule below is deliberately conservative. It folds only differences that
cannot distinguish two real people: diacritics, case, punctuation,
generational suffixes and whitespace. It never truncates, initialises, or
fuzzy-matches, so it cannot merge two different players. Callers that resolve
a name through it must still refuse an AMBIGUOUS match (see
resolve_feed_name) rather than guess — MLB has carried two same-named players
on one roster before, and a wrong price is worse than no pick.
"""

import unicodedata

# Generational suffixes are dropped, so "Luis García Jr." matches a feed that
# writes "Luis Garcia". Two players who differ ONLY by suffix therefore
# normalize alike — resolve_feed_name refuses that case instead of picking one.
_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# Deleted outright (an apostrophe is written inconsistently but never separates
# two name parts: "O'Neill" and "ONeill" are one player).
_DELETE = str.maketrans("", "", "'‘’ʼ.")
# Folded to a space (a hyphen DOES separate parts: "Jung-Hoo Lee").
_TO_SPACE = str.maketrans("-‐‑‒–—_", "       ")


def normalize_player_name(name: object) -> str:
    """
    Fold a player's name to the form used for cross-feed matching.

    Diacritics stripped, lowercased, punctuation folded, generational suffix
    dropped, whitespace collapsed. Returns "" for anything empty.

        normalize_player_name("José Ramírez")     -> "jose ramirez"
        normalize_player_name("Ronald Acuña Jr.") -> "ronald acuna"
        normalize_player_name("Jung-Hoo Lee")     -> "jung hoo lee"
    """
    if name is None:
        return ""
    s = str(name).strip()
    if not s:
        return ""
    # NFKD splits "é" into "e" + combining accent; drop the combining marks.
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().translate(_DELETE).translate(_TO_SPACE)
    parts = s.split()
    # Drop trailing suffixes only — "Jr" is never a first name, but a middle
    # token could legitimately be "V" in some other alphabet's transliteration.
    while len(parts) > 1 and parts[-1] in _SUFFIXES:
        parts.pop()
    return " ".join(parts)


def resolve_feed_name(target: object, candidates) -> str | None:
    """
    Find the ONE candidate spelling that means the same player as `target`.

    `candidates` is whatever spellings the odds feed carries for the market
    being priced. Returns the candidate verbatim (so the caller can key its
    own follow-up queries on the feed's spelling), or None when nothing
    matches OR when two distinct candidates normalize alike — an ambiguous
    match is not a match.
    """
    key = normalize_player_name(target)
    if not key:
        return None
    hits = {c for c in candidates if normalize_player_name(c) == key}
    if len(hits) != 1:
        return None
    return hits.pop()
