"""NFL team identity across the three feeds this model joins.

  * the platform `games` table uses nflverse abbreviations (LA for the Rams,
    WAS for Washington) -- measured on the 2026 week-5 rows in Supabase;
  * the Odds API uses full franchise names;
  * ESPN core team documents carry their own abbreviation, which differs from
    nflverse on exactly WSH (Washington) and LAR (the Rams) -- measured on the
    2026 core team documents; JAC is the historical Jacksonville spelling.

TEAM_MAP is a COPY of nfl/data_ingest/parse.TEAM_MAP rather than an import:
that module lives under nfl/, which runs as its own package root with cwd=nfl/,
and importing across that boundary is the trap data/live_quote_guard.py
documents. tests/test_nfl_live_leader_state.py pins the two equal.
"""

from __future__ import annotations

TEAM_MAP = {
    "Arizona Cardinals": "ARI",
    "Atlanta Falcons": "ATL",
    "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF",
    "Carolina Panthers": "CAR",
    "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN",
    "Cleveland Browns": "CLE",
    "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN",
    "Detroit Lions": "DET",
    "Green Bay Packers": "GB",
    "Houston Texans": "HOU",
    "Indianapolis Colts": "IND",
    "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC",
    "Las Vegas Raiders": "LV",
    "Oakland Raiders": "LV",
    "Los Angeles Chargers": "LAC",
    "San Diego Chargers": "LAC",
    "Los Angeles Rams": "LA",
    "St. Louis Rams": "LA",
    "Miami Dolphins": "MIA",
    "Minnesota Vikings": "MIN",
    "New England Patriots": "NE",
    "New Orleans Saints": "NO",
    "New York Giants": "NYG",
    "New York Jets": "NYJ",
    "Philadelphia Eagles": "PHI",
    "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF",
    "Seattle Seahawks": "SEA",
    "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN",
    "Washington Commanders": "WAS",
    "Washington Football Team": "WAS",
    "Washington Redskins": "WAS",
}

ABBREVS = frozenset(TEAM_MAP.values())
ESPN_ABBREV_FIXES = {"WSH": "WAS", "LAR": "LA", "JAC": "JAX"}


def abbrev(name: str | None) -> str | None:
    """The platform abbreviation for a team, from either a book's full name or
    an ESPN abbreviation. None when it is neither -- never a guess."""
    if not name:
        return None
    n = str(name).strip()
    if n in TEAM_MAP:
        return TEAM_MAP[n]
    up = ESPN_ABBREV_FIXES.get(n.upper(), n.upper())
    return up if up in ABBREVS else None
