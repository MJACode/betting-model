"""Team name -> X hashtag.

The games table stores a 3-letter abbreviation for the pro leagues and the
CFBD school name for NCAAF (CLAUDE.md §4). A hashtag is the club's common
nickname with spaces and punctuation removed: NYY -> #Yankees, BOS in MLB ->
#RedSox, SF in the NFL -> #49ers. The same letters are a different club in
another sport, so the map is keyed on (sport, abbreviation).

College mascots are not in this file. ncaaf_teams.mascot is the nickname, and
it is read at post time. Two schools in one game can share a mascot (Troy and
USC are both Trojans); that pair falls back to the school names so the tags
still name both teams.
"""

from __future__ import annotations

import re

from data.ingestors.book_team_map import MLB_NICKNAMES

# Nicknames that are more than the last word of the franchise name.
_MULTI_WORD_NICKS = (
    "red sox", "white sox", "blue jays",
    "blue jackets", "red wings", "maple leafs", "golden knights",
    "trail blazers",
)


def hashtag_token(name: str) -> str:
    """'Red Sox' -> 'RedSox'. '49ers' -> '49ers'. 'USC' stays 'USC'.

    A short all-caps word is an abbreviation (USC, LSU, TCU, UL), not a
    word to title-case into 'Usc'.
    """
    parts = re.findall(r"[A-Za-z0-9]+", name or "")
    bits: list[str] = []
    for part in parts:
        if part[0].isdigit():
            bits.append(part.lower())
        elif part.isupper() and len(part) <= 5:
            bits.append(part)
        else:
            bits.append(part[:1].upper() + part[1:].lower())
    return "".join(bits)


def _nickname(full_name: str) -> str:
    low = " ".join(full_name.lower().replace(".", " ").split())
    for nick in sorted(_MULTI_WORD_NICKS, key=len, reverse=True):
        if low.endswith(nick):
            return hashtag_token(nick)
    words = low.split()
    return hashtag_token(words[-1]) if words else ""


def _from_full_names(mapping: dict[str, str],
                     overrides: dict[str, str] | None = None) -> dict[str, str]:
    """Abbreviation -> hashtag, from a full-name -> abbreviation map.

    The longest name for an abbreviation wins, then `overrides` correct the
    cases where a historical name is longer than the current one
    ('Washington Football Team' is longer than 'Washington Commanders').
    """
    best: dict[str, str] = {}
    for name, abbr in mapping.items():
        key = abbr.upper()
        if key not in best or len(name) > len(best[key]):
            best[key] = name
    out = {abbr: _nickname(name) for abbr, name in best.items()}
    if overrides:
        out.update({k.upper(): v for k, v in overrides.items()})
    return out


def _index(*tables: dict[str, str]) -> dict[str, str]:
    """Look up by abbreviation, by the hashtag itself, or by a lowercase nickname."""
    out: dict[str, str] = {}
    for table in tables:
        for key, tag in table.items():
            out[key.upper()] = tag
            out[tag.lower()] = tag
    return out


def _mlb() -> dict[str, str]:
    # Keyed on the nickname the books actually share (book_team_map), valued
    # with the abbreviation the games table uses. Inverted here.
    return {abbr.upper(): hashtag_token(nick) for nick, abbr in MLB_NICKNAMES.items()}


def _pro_maps() -> dict[str, dict[str, str]]:
    import config
    nba = _from_full_names(config.NBA_ODDS_API_MAP)
    wnba = _from_full_names(config.WNBA_ODDS_API_MAP)
    nfl = _from_full_names(config.NFL_ODDS_API_MAP, {"WAS": "Commanders"})
    return {
        "MLB": _index(_mlb()),
        "NBA": _index(nba),
        "WNBA": _index(wnba),
        "NFL": _index(nfl),
        "NHL": _index(_NHL),
    }


# Current NHL nicknames. UTA is the Mammoth; the Coyotes name is the same
# franchise and must not win by being a longer string.
_NHL = {
    "ANA": "Ducks", "UTA": "Mammoth", "BOS": "Bruins", "BUF": "Sabres",
    "CAR": "Hurricanes", "CBJ": "BlueJackets", "CGY": "Flames",
    "CHI": "Blackhawks", "COL": "Avalanche", "DAL": "Stars",
    "DET": "RedWings", "EDM": "Oilers", "FLA": "Panthers", "LAK": "Kings",
    "MIN": "Wild", "MTL": "Canadiens", "NJD": "Devils", "NSH": "Predators",
    "NYI": "Islanders", "NYR": "Rangers", "OTT": "Senators", "PHI": "Flyers",
    "PIT": "Penguins", "SEA": "Kraken", "SJS": "Sharks", "STL": "Blues",
    "TBL": "Lightning", "TOR": "MapleLeafs", "VAN": "Canucks",
    "VGK": "GoldenKnights", "WSH": "Capitals", "WPG": "Jets",
}

BY_SPORT = _pro_maps()


def team_hashtag(sport: str | None, name: str | None,
                 mascots: dict[str, str] | None = None) -> str | None:
    """The hashtag token for one club, without the leading '#'. None if blank."""
    if name is None or not str(name).strip():
        return None
    sport_u = (sport or "").upper()
    raw = str(name).strip()
    table = BY_SPORT.get(sport_u)
    if table:
        hit = table.get(raw.upper()) or table.get(raw.lower())
        if hit:
            return hit
    if sport_u == "NCAAF":
        mascot = (mascots or {}).get(raw)
        if mascot:
            return hashtag_token(mascot)
        return hashtag_token(raw) or None
    if table is None:
        # UFC stores fighter names. Compact them; there is no club nickname.
        return hashtag_token(raw) or None
    return None


def _both_teams(pick: dict) -> bool:
    """Totals and game props name both clubs. A side names the club it takes.

    A player prop is an over/under too, and the row carries the game's two
    clubs rather than the player's club, so both are tagged.
    """
    side = str(pick.get("side") or "").lower()
    if side in ("over", "under"):
        return True
    model = str(pick.get("model_id") or "")
    market = str(pick.get("prop_market") or "")
    if market or "prop" in model or "total" in model or "over_under" in model:
        return True
    label = str(pick.get("label") or "")
    return re.search(r"\b(Over|Under)\b", label) is not None


def team_tags(pick: dict, mascots: dict[str, str] | None = None) -> list[str]:
    """'#Yankees' for a side, '#Yankees' and '#RedSox' for a total. No duplicates."""
    sport = pick.get("sport")
    home, away = pick.get("home"), pick.get("away")
    if _both_teams(pick):
        names = [home, away]
    else:
        side = str(pick.get("side") or "").lower()
        if side == "home":
            names = [home]
        elif side == "away":
            names = [away]
        elif home or away:
            names = [home, away]
        else:
            names = []
    resolved: list[str | None] = [
        team_hashtag(sport, name, mascots) for name in names]
    if ((sport or "").upper() == "NCAAF" and len(names) == 2
            and resolved[0] and resolved[0] == resolved[1]):
        resolved = [hashtag_token(name) if name else None for name in names]
    tags: list[str] = []
    for token in resolved:
        if token and token not in tags:
            tags.append(token)
    return [f"#{token}" for token in tags]
