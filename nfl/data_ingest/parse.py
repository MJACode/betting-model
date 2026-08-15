"""Parse Odds API snapshot payloads into tidy long-format frames."""

from __future__ import annotations

import pandas as pd

# Odds API uses full franchise names; nflverse uses abbreviations.
# Note LA (not LAR) for the Rams, and the Washington rebrand mid-window.
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


def snapshot_to_frame(payload: dict, snap_label: str) -> pd.DataFrame:
    """
    Flatten one snapshot into rows of:
      snap_label, snap_ts, event_id, commence_time, home, away,
      book, market, side, price, point, last_update

    'side' is normalized to 'home' / 'away' for spreads and h2h,
    and 'Over' / 'Under' for totals.
    """
    rows = []
    snap_ts = payload.get("timestamp")
    for ev in payload.get("data", []) or []:
        home_raw, away_raw = ev.get("home_team"), ev.get("away_team")
        home, away = TEAM_MAP.get(home_raw), TEAM_MAP.get(away_raw)
        if home is None or away is None:
            continue  # unmapped franchise, surfaced by the audit below
        for bk in ev.get("bookmakers", []) or []:
            for mk in bk.get("markets", []) or []:
                mkey = mk.get("key")
                for oc in mk.get("outcomes", []) or []:
                    name = oc.get("name")
                    if mkey in ("spreads", "h2h"):
                        if name == home_raw:
                            side = "home"
                        elif name == away_raw:
                            side = "away"
                        else:
                            continue
                    elif mkey == "totals":
                        side = name  # Over / Under
                    else:
                        continue
                    rows.append(
                        {
                            "snap_label": snap_label,
                            "snap_ts": snap_ts,
                            "event_id": ev.get("id"),
                            "commence_time": ev.get("commence_time"),
                            "home": home,
                            "away": away,
                            "book": bk.get("key"),
                            "market": mkey,
                            "side": side,
                            "price": oc.get("price"),
                            "point": oc.get("point"),
                            "last_update": mk.get("last_update") or bk.get("last_update"),
                        }
                    )
    if not rows:
        return pd.DataFrame(
            columns=[
                "snap_label", "snap_ts", "event_id", "commence_time", "home", "away",
                "book", "market", "side", "price", "point", "last_update",
            ]
        )
    return pd.DataFrame(rows)


def unmapped_teams(payload: dict) -> set:
    out = set()
    for ev in payload.get("data", []) or []:
        for k in ("home_team", "away_team"):
            v = ev.get(k)
            if v is not None and v not in TEAM_MAP:
                out.add(v)
    return out
