"""Host -> API identity.

Everything the dashboard groups, colours and bills by comes from this table.
It is deliberately data, not logic: a new ingestor pointed at a new host shows
up immediately as an UNKNOWN row (with its real hostname) rather than silently
vanishing, and naming it here is a one-line change.

`paid` marks the APIs with a credit ceiling that can take the pipeline down —
the 2026-08-14 Odds API exhaustion killed MLB and WNBA picks for 2.5 days, and
CFBD is metered per call on a Patreon tier. Those get the credit panel.
"""

from __future__ import annotations

from urllib.parse import urlsplit

# suffix-matched, longest first — 'sports.core.api.espn.com' must win over
# 'espn.com'. Order in this list is irrelevant; _match sorts by length.
_HOSTS: dict[str, tuple[str, str, bool]] = {
    # host suffix                        (display name,        category,   paid)
    "api.the-odds-api.com":              ("The Odds API",      "odds",     True),
    "the-odds-api.com":                  ("The Odds API",      "odds",     True),
    "api.collegefootballdata.com":       ("CFBD",              "stats",    True),
    "collegefootballdata.com":           ("CFBD",              "stats",    True),
    "feeds.datagolf.com":                ("DataGolf",          "odds",     True),
    "api.elections.kalshi.com":          ("Kalshi",            "odds",     True),
    "api.oddspapi.io":                   ("OddsPapi",          "odds",     True),
    "p.rapidapi.com":                    ("RapidAPI",          "odds",     True),

    "statsapi.mlb.com":                  ("MLB Stats API",     "stats",    False),
    "baseballsavant.mlb.com":            ("Baseball Savant",   "stats",    False),
    "api-web.nhle.com":                  ("NHL API",           "stats",    False),
    "api.nhle.com":                      ("NHL API",           "stats",    False),
    "stats.nba.com":                     ("stats.nba.com",     "stats",    False),
    "site.api.espn.com":                 ("ESPN (site)",       "stats",    False),
    "sports.core.api.espn.com":          ("ESPN (core)",       "stats",    False),
    "espn.com":                          ("ESPN",              "stats",    False),
    "ufcstats.com":                      ("ufcstats.com",      "stats",    False),
    "raw.githubusercontent.com":         ("GitHub raw",        "stats",    False),
    "github.com":                        ("GitHub",            "stats",    False),
    "www.sportsbookreviewsonline.com":   ("SBR",               "stats",    False),

    "api.open-meteo.com":                ("Open-Meteo",        "weather",  False),
    "archive-api.open-meteo.com":        ("Open-Meteo",        "weather",  False),
    "historical-forecast-api.open-meteo.com": ("Open-Meteo",   "weather",  False),

    "api.actionnetwork.com":             ("Action Network",    "public",   False),
    "www.actionnetwork.com":             ("Action Network",    "public",   False),

    "sportsbook.draftkings.com":         ("DraftKings",        "book",     False),
    "sportsbook-nash.draftkings.com":    ("DraftKings",        "book",     False),
    "draftkings.com":                    ("DraftKings",        "book",     False),

    "discord.com":                       ("Discord",           "notify",   False),
    "discordapp.com":                    ("Discord",           "notify",   False),
    "exp.host":                          ("Expo Push",         "notify",   False),
    "supabase.co":                       ("Supabase",          "db",       False),
    "api.sharpsports.io":                ("SharpSports",       "book",     False),
}

# Longest suffix first so the most specific host wins.
_ORDERED = sorted(_HOSTS.items(), key=lambda kv: -len(kv[0]))

UNKNOWN = ("other", "other", False)


def classify(url: str) -> tuple[str, str, str, bool]:
    """(host, api_name, category, paid) for a URL. Never raises."""
    try:
        host = (urlsplit(url).hostname or "").lower()
    except Exception:
        return ("", "other", "other", False)
    for suffix, (name, category, paid) in _ORDERED:
        if host == suffix or host.endswith("." + suffix):
            return (host, name, category, paid)
    return (host, host or "other", "other", False)


def paid_apis() -> list[str]:
    """Display names of the metered APIs, de-duplicated, in stable order."""
    seen: list[str] = []
    for _suffix, (name, _cat, paid) in _ORDERED:
        if paid and name not in seen:
            seen.append(name)
    return sorted(seen)
