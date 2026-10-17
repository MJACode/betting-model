"""NBA schedule, travel and fatigue features, built from the SCHEDULE only.

WHY THIS MODULE EXISTS
----------------------
The owner asked (2026-10-15) that schedule be measured the way NHL never was:
back-to-backs, long road trips, travel, time zones, altitude. Every feature
here is a function of WHERE and WHEN games are played -- the published
schedule -- never of a result. The schedule is released before the season, so
every value is known at any decision time before the game.

One honest caveat on "known in advance": `nba_schedule` holds the schedule as
it was PLAYED. Games postponed and re-slotted (heavily in 2020-21, the COVID
season, whose second half was published mid-season; a handful of NBA Cup
knockout re-slots in December) appear at their final date. Features of PAST
games (rest, travel, last-N-days counts) are unaffected. Features that look
FORWARD -- the total length of the current road trip or home stand -- use the
final schedule, which for a re-slotted game may differ from what was published
when an early line was posted. The lab reports this rather than hiding it.

RESULT-DERIVED LOAD (overtime last night, minutes played) is NOT here. It is a
result, and on the second night of a back-to-back the night-two opener is
posted before night one is played. `previous_game_load` below is separate and
takes an explicit decision time so the gate is visible at the call site.

DEFINITIONS (one place; the lab report copies these)
----------------------------------------------------
Games counted: a team's REGULAR-SEASON games plus the NBA Cup final
(`game_type` in {'regular', 'cup_final'}) in that season. Preseason is ignored
(a team's first regular-season game is treated as coming off full rest).
Play-in / playoffs are not modelled.

Dates are the Eastern-time `game_date` (a 10:30 pm ET tip is the next UTC
day; UTC dates would mis-count rest).

rest_days        days between this game and the team's previous counted game,
                 minus one (0 = second night of a back-to-back). Capped at
                 REST_CAP (4); the season opener reads REST_CAP.
b2b              rest_days == 0.
b2b_travel       b2b and the previous game was in a different city.
n_in_4/6/7       games in the window of 4 / 6 / 7 nights ENDING TODAY,
                 inclusive of this game. is_3in4 = n_in_4 >= 3,
                 is_4in6 = n_in_6 >= 4, is_5in7 = n_in_7 >= 5.
g_last7/14       games in the 7 / 14 days BEFORE today (today excluded).
is_home          the team is the designated home team AND the venue is not
                 neutral. A neutral-site game is "away" for both teams.
road_game_no     position of this game in the current run of consecutive
                 non-home games (1 = first game of a trip); 0 at home.
road_trip_len    total length of that run (schedule-known, see caveat above).
home_game_no     position in the current run of consecutive home games; 0 away.
home_after_trip  on the first game of a home stand: length of the road trip
                 that immediately preceded it (0 otherwise). first_home_after3
                 = home_after_trip >= 3.
travel_mi        great-circle miles, previous venue -> this venue
                 (season opener: home base -> this venue).
travel_mi_7d     miles travelled on legs arriving within the last 7 days,
                 this leg included.
tz_shift         UTC offset of this venue minus UTC offset of the previous
                 venue, BOTH taken at this game's tip (so a DST change between
                 two games is not read as travel). > 0 = moved east.
east_shift / west_shift   the positive / negative part of tz_shift.
tz_from_home     UTC offset of the venue minus that of the team's home base,
                 at tip. > 0 = playing east of home.
elev_ft          venue elevation. at_altitude = elev_ft >= 4000 (Denver,
                 Salt Lake City, Mexico City).
local_hour       tip time on the venue's local clock (decimal hours).
early_tip        local_hour < 18.0.
body_hour        tip time on the team's HOME clock.
days_since_open  days since the league's first regular-season date that
                 season. game_no = the team's nth counted game.
post_all_star    the game is after that season's All-Star game date.
nba_cup          the schedule labels the game as an NBA Cup game (2023-24 on).
national_tv      a national broadcaster is listed. ONLY POPULATED for the
                 2020-21, 2025-26 and 2026-27 schedules in our table, so it
                 is returned for reference and must not be used as a model
                 input across seasons.
neutral          the venue is neutral (`is_neutral`).

Venue coordinates come from the schedule row's arena city (with arena-name
overrides for the 2020 Orlando bubble), never from home_team -> arena:
Toronto played 2020-21 in Tampa, Golden State moved Oakland -> San Francisco,
the Clippers moved to Inglewood in 2024-25, and international games are
played in Mexico City, Paris, London, Berlin and Manchester.
"""
from __future__ import annotations

import math
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

REST_CAP = 4
COUNTED_GAME_TYPES = ("regular", "cup_final")

# city -> (lat, lon, IANA zone, elevation in feet). Arena-level coordinates.
VENUES: dict[str, tuple[float, float, str, int]] = {
    "Atlanta": (33.7573, -84.3963, "America/New_York", 1050),
    "Austin": (30.2828, -97.7322, "America/Chicago", 500),
    "Berlin": (52.5079, 13.4433, "Europe/Berlin", 112),
    "Boston": (42.3662, -71.0621, "America/New_York", 20),
    "Brooklyn": (40.6826, -73.9754, "America/New_York", 30),
    "Charlotte": (35.2251, -80.8392, "America/New_York", 750),
    "Chicago": (41.8807, -87.6742, "America/Chicago", 600),
    "Cleveland": (41.4965, -81.6882, "America/New_York", 650),
    "Dallas": (32.7905, -96.8103, "America/Chicago", 430),
    "Denver": (39.7487, -105.0077, "America/Denver", 5280),
    "Detroit": (42.3411, -83.0553, "America/Detroit", 600),
    "Houston": (29.7508, -95.3621, "America/Chicago", 50),
    "Indianapolis": (39.7640, -86.1555, "America/Indiana/Indianapolis", 715),
    "Inglewood": (33.9450, -118.3417, "America/Los_Angeles", 100),
    "Las Vegas": (36.1029, -115.1784, "America/Los_Angeles", 2030),
    "London": (51.5030, 0.0032, "Europe/London", 20),
    "Los Angeles": (34.0430, -118.2673, "America/Los_Angeles", 270),
    "Manchester": (53.4860, -2.1990, "Europe/London", 150),
    "Memphis": (35.1382, -90.0506, "America/Chicago", 260),
    "Mexico City": (19.4040, -99.0950, "America/Mexico_City", 7350),
    "Miami": (25.7814, -80.1870, "America/New_York", 10),
    "Milwaukee": (43.0451, -87.9172, "America/Chicago", 620),
    "Minneapolis": (44.9795, -93.2761, "America/Chicago", 830),
    "New Orleans": (29.9490, -90.0821, "America/Chicago", 5),
    "New York": (40.7505, -73.9934, "America/New_York", 30),
    "Oakland": (37.7503, -122.2030, "America/Los_Angeles", 20),
    "Oklahoma City": (35.4634, -97.5151, "America/Chicago", 1200),
    "Orlando": (28.5392, -81.3839, "America/New_York", 100),
    "Paris": (48.8386, 2.3786, "Europe/Paris", 115),
    "Philadelphia": (39.9012, -75.1720, "America/New_York", 30),
    "Phoenix": (33.4457, -112.0712, "America/Phoenix", 1086),
    "Portland": (45.5316, -122.6668, "America/Los_Angeles", 50),
    "Sacramento": (38.5802, -121.4997, "America/Los_Angeles", 30),
    "Salt Lake City": (40.7683, -111.9011, "America/Denver", 4226),
    "San Antonio": (29.4270, -98.4375, "America/Chicago", 650),
    "San Francisco": (37.7680, -122.3877, "America/Los_Angeles", 10),
    "Tampa": (27.9427, -82.4518, "America/New_York", 15),
    "Toronto": (43.6435, -79.3791, "America/Toronto", 250),
    "Washington": (38.8981, -77.0209, "America/New_York", 50),
    # 2020 restart bubble (ESPN Wide World of Sports, Lake Buena Vista).
    "Orlando bubble": (28.3370, -81.5560, "America/New_York", 100),
}
_BUBBLE_ARENAS = {"AdventHealth Arena", "HP Field House", "VISA Athletic Center"}
ALTITUDE_FT = 4000


def venue_key(arena_city, arena_name=None) -> str | None:
    """Normalise the schedule's arena city to a VENUES key ('Mexico City, Mexico' -> 'Mexico City')."""
    if arena_name in _BUBBLE_ARENAS:
        return "Orlando bubble"
    if arena_city is None or (isinstance(arena_city, float) and math.isnan(arena_city)):
        return None
    c = str(arena_city).split(",")[0].strip()
    return c if c in VENUES else None


def haversine_miles(lat1, lon1, lat2, lon2):
    r = 3958.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _utc_offset_h(zone: str | None, ts_utc: pd.Timestamp) -> float:
    """UTC offset (hours) of `zone` at instant `ts_utc`."""
    if not isinstance(zone, str) or pd.isna(ts_utc):
        return float("nan")
    t = ts_utc.to_pydatetime()
    return t.astimezone(ZoneInfo(zone)).utcoffset().total_seconds() / 3600.0


def _offsets(zones: pd.Series, ts: pd.Series) -> np.ndarray:
    """Vector of UTC offsets at each tip, computed once per distinct (zone, tip instant)."""
    k = pd.DataFrame({"z": zones.astype(object).where(zones.notna(), None).to_numpy(),
                      "d": ts.to_numpy()})
    u = k.drop_duplicates().copy()
    u["off"] = [_utc_offset_h(z, pd.Timestamp(d)) for z, d in zip(u["z"], u["d"])]
    return k.merge(u, on=["z", "d"], how="left")["off"].to_numpy(float)


def _counted_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    s = schedule[schedule["game_type"].isin(COUNTED_GAME_TYPES)].copy()
    # Unresolved NBA Cup knockout slots carry home/away "NaN" until the group stage ends.
    ok = lambda c: c.notna() & c.astype(str).str.fullmatch(r"[A-Z]{3}") & (c.astype(str) != "NaN")
    s = s[ok(s["home_team"]) & ok(s["away_team"])]
    s["gd"] = pd.to_datetime(s["game_date"])
    s["ct"] = pd.to_datetime(s["commence_time"], utc=True)
    s["venue"] = [venue_key(c, n) for c, n in zip(s["arena_city"], s["arena_name"])]
    s["neutral"] = s["is_neutral"].fillna(False).astype(bool)
    return s


def home_bases(schedule: pd.DataFrame) -> pd.DataFrame:
    """(season, team) -> the venue the team played most of its non-neutral home games in."""
    s = _counted_schedule(schedule)
    s = s[~s["neutral"] & s["venue"].notna()]
    hb = (s.groupby(["season", "home_team", "venue"]).size().reset_index(name="n")
          .sort_values("n").groupby(["season", "home_team"]).tail(1))
    return hb.rename(columns={"home_team": "team", "venue": "home_venue"})[["season", "team", "home_venue"]]


def team_schedule_features(schedule: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team): every schedule feature in the module docstring."""
    s = _counted_schedule(schedule)
    hb = home_bases(schedule)
    first_day = s[s["game_type"] == "regular"].groupby("season")["gd"].min().rename("season_open")
    asg = schedule[schedule["game_type"] == "allstar"].copy()
    asg["gd"] = pd.to_datetime(asg["game_date"])
    # The All-Star GAME is the last all-star-type event of the weekend.
    asg_day = asg.groupby("season")["gd"].max().rename("asg_date")

    base = s[["game_id", "season", "gd", "ct", "venue", "neutral", "home_team", "away_team",
              "game_label", "national_tv"]]
    rows = []
    for side, opp in (("home_team", "away_team"), ("away_team", "home_team")):
        t = base.copy()
        t["team"] = t[side]
        t["opp"] = t[opp]
        t["designated_home"] = side == "home_team"
        rows.append(t)
    t = pd.concat(rows, ignore_index=True)
    t = t.merge(hb, on=["season", "team"], how="left")
    t["is_home"] = t["designated_home"] & ~t["neutral"]
    t = t.merge(first_day, on="season", how="left").merge(asg_day, on="season", how="left")
    t = t.sort_values(["season", "team", "ct"]).reset_index(drop=True)

    g = t.groupby(["season", "team"], sort=False)
    t["game_no"] = g.cumcount() + 1
    t["prev_gd"] = g["gd"].shift(1)
    t["prev_venue"] = g["venue"].shift(1)
    t["prev_ct"] = g["ct"].shift(1)
    rest = (t["gd"] - t["prev_gd"]).dt.days - 1
    t["rest_days"] = rest.fillna(REST_CAP).clip(upper=REST_CAP).astype(float)
    t["b2b"] = (rest == 0).astype(int)
    prev_v = t["prev_venue"].where(t["prev_venue"].notna(), t["home_venue"])
    t["b2b_travel"] = ((t["b2b"] == 1) & (prev_v != t["venue"])).astype(int)

    # Window counts on the ET calendar (inclusive of today).
    def _window_counts(df: pd.DataFrame) -> pd.DataFrame:
        d = df["gd"].values.astype("datetime64[D]").astype(np.int64)
        out = {}
        for name, lo, hi in (("n_in_4", 3, 0), ("n_in_6", 5, 0), ("n_in_7", 6, 0),
                             ("g_last7", 7, 1), ("g_last14", 14, 1)):
            left = np.searchsorted(d, d - lo, side="left")
            right = np.searchsorted(d, d - hi, side="right")
            out[name] = right - left
        return pd.DataFrame(out, index=df.index)

    wc = pd.concat([_window_counts(df) for _, df in t.groupby(["season", "team"], sort=False)])
    t = t.join(wc)
    t["is_3in4"] = (t["n_in_4"] >= 3).astype(int)
    t["is_4in6"] = (t["n_in_6"] >= 4).astype(int)
    t["is_5in7"] = (t["n_in_7"] >= 5).astype(int)

    # Home / road runs.
    def _runs(df: pd.DataFrame) -> pd.DataFrame:
        h = df["is_home"].to_numpy()
        run_id = np.cumsum(np.r_[True, h[1:] != h[:-1]])
        pos = pd.Series(1, index=df.index).groupby(run_id).cumsum().to_numpy()
        length = pd.Series(1, index=df.index).groupby(run_id).transform("sum").to_numpy()
        road_no = np.where(h, 0, pos)
        road_len = np.where(h, 0, length)
        home_no = np.where(h, pos, 0)
        # length of the road run immediately before a home stand's first game
        prev_len = np.zeros(len(h), dtype=int)
        run_len = {r: l for r, l in zip(run_id, length)}
        for i in range(len(h)):
            if h[i] and pos[i] == 1 and run_id[i] > 1:
                prev_len[i] = run_len.get(run_id[i] - 1, 0)
        return pd.DataFrame({"road_game_no": road_no, "road_trip_len": road_len,
                             "home_game_no": home_no, "home_after_trip": prev_len}, index=df.index)

    rn = pd.concat([_runs(df) for _, df in t.groupby(["season", "team"], sort=False)])
    t = t.join(rn)
    t["first_home_after3"] = (t["home_after_trip"] >= 3).astype(int)

    # Travel and clocks.
    lat = t["venue"].map(lambda v: VENUES[v][0] if v in VENUES else np.nan)
    lon = t["venue"].map(lambda v: VENUES[v][1] if v in VENUES else np.nan)
    plat = prev_v.map(lambda v: VENUES[v][0] if v in VENUES else np.nan)
    plon = prev_v.map(lambda v: VENUES[v][1] if v in VENUES else np.nan)
    t["travel_mi"] = haversine_miles(plat.to_numpy(float), plon.to_numpy(float),
                                     lat.to_numpy(float), lon.to_numpy(float))
    zone = t["venue"].map(lambda v: VENUES[v][2] if v in VENUES else None)
    pzone = prev_v.map(lambda v: VENUES[v][2] if v in VENUES else None)
    hzone = t["home_venue"].map(lambda v: VENUES[v][2] if v in VENUES else None)
    off = _offsets(zone, t["ct"])
    poff = _offsets(pzone, t["ct"])
    hoff = _offsets(hzone, t["ct"])
    t["tz_shift"] = off - poff
    t["east_shift"] = np.clip(t["tz_shift"], 0, None)
    t["west_shift"] = np.clip(-t["tz_shift"], 0, None)
    t["tz_from_home"] = off - hoff
    t["elev_ft"] = t["venue"].map(lambda v: VENUES[v][3] if v in VENUES else np.nan)
    t["at_altitude"] = (t["elev_ft"] >= ALTITUDE_FT).astype(int)
    utc_h = t["ct"].dt.hour + t["ct"].dt.minute / 60.0
    t["local_hour"] = (utc_h + off) % 24
    t["early_tip"] = (t["local_hour"] < 18.0).astype(int)
    t["body_hour"] = (utc_h + hoff) % 24

    def _miles_7d(df: pd.DataFrame) -> pd.Series:
        d = df["gd"].values.astype("datetime64[D]").astype(np.int64)
        c = np.r_[0.0, np.cumsum(np.nan_to_num(df["travel_mi"].to_numpy(float)))]
        left = np.searchsorted(d, d - 6, side="left")
        return pd.Series(c[np.arange(len(d)) + 1] - c[left], index=df.index)

    t["travel_mi_7d"] = pd.concat([_miles_7d(df) for _, df in t.groupby(["season", "team"], sort=False)])
    t["days_since_open"] = (t["gd"] - t["season_open"]).dt.days
    t["post_all_star"] = (t["gd"] > t["asg_date"]).astype(int)
    t["nba_cup"] = t["game_label"].fillna("").str.contains("Cup").astype(int)
    t["national_tv"] = t["national_tv"].notna().astype(int)
    t["neutral"] = t["neutral"].astype(int)
    t["is_home"] = t["is_home"].astype(int)
    keep = ["game_id", "season", "team", "opp", "designated_home", "is_home", "neutral", "venue",
            "home_venue", "game_no", "rest_days", "b2b", "b2b_travel", "n_in_4", "n_in_6", "n_in_7",
            "is_3in4", "is_4in6", "is_5in7", "g_last7", "g_last14", "road_game_no", "road_trip_len",
            "home_game_no", "home_after_trip", "first_home_after3", "travel_mi", "travel_mi_7d",
            "tz_shift", "east_shift", "west_shift", "tz_from_home", "elev_ft", "at_altitude",
            "local_hour", "early_tip", "body_hour", "days_since_open", "post_all_star", "nba_cup",
            "national_tv", "prev_ct"]
    return t[keep]


TEAM_COLS = ["is_home", "rest_days", "b2b", "b2b_travel", "is_3in4", "is_4in6", "is_5in7", "g_last7",
             "g_last14", "road_game_no", "road_trip_len", "home_game_no", "home_after_trip",
             "first_home_after3", "travel_mi", "travel_mi_7d", "tz_shift", "east_shift", "west_shift",
             "tz_from_home", "early_tip", "body_hour", "game_no"]


def game_schedule_features(schedule: pd.DataFrame) -> pd.DataFrame:
    """One row per game_id: home_* and away_* team features plus game-level ones.

    Game-level: neutral, venue, elev_ft, at_altitude, local_hour, early_tip,
    days_since_open, post_all_star, nba_cup, national_tv (reference only),
    rest_diff = home_rest_days - away_rest_days, and two published-spot flags:
      alt_vs_tired   the venue is at altitude and the visitor is on a b2b or 3-in-4
      both_b2b       both teams on the second night of a back-to-back
    """
    tf = team_schedule_features(schedule)
    h = tf[tf["designated_home"]].set_index("game_id")
    a = tf[~tf["designated_home"]].set_index("game_id")
    out = pd.DataFrame(index=h.index)
    for c in ["season", "neutral", "venue", "elev_ft", "at_altitude", "local_hour", "days_since_open",
              "post_all_star", "nba_cup", "national_tv"]:
        out[c] = h[c]
    out["early_tip"] = h["early_tip"]
    out["home_team"] = h["team"]
    out["away_team"] = a["team"]
    for c in TEAM_COLS + ["prev_ct"]:
        out["home_" + c] = h[c]
        out["away_" + c] = a.reindex(h.index)[c]
    out["rest_diff"] = out["home_rest_days"] - out["away_rest_days"]
    out["alt_vs_tired"] = ((out["at_altitude"] == 1) &
                           ((out["away_b2b"] == 1) | (out["away_is_3in4"] == 1))).astype(int)
    out["both_b2b"] = ((out["home_b2b"] == 1) & (out["away_b2b"] == 1)).astype(int)
    return out.reset_index()


def previous_game_load(games: pd.DataFrame, team_feats: pd.DataFrame,
                       decision_ts: pd.Series, settle_hours: float = 3.0) -> pd.DataFrame:
    """RESULT-derived load of each team's previous game, gated on the decision time.

    `team_feats` is team_schedule_features(); `games` holds game_id, went_to_ot.
    `decision_ts` is indexed like team_feats (one UTC timestamp per row). The
    previous game counts as KNOWN only if prev_ct + settle_hours <= decision_ts;
    otherwise prev_ot is NaN and prev_known is 0. On the second night of a
    back-to-back at an evening-before decision this gate fails by construction.
    """
    tf = team_feats.sort_values(["season", "team", "game_no"]).copy()
    ot = games.set_index("game_id")["went_to_ot"]
    tf["prev_game_id"] = tf.groupby(["season", "team"])["game_id"].shift(1)
    tf["prev_ot_raw"] = tf["prev_game_id"].map(ot)
    dts = decision_ts.reindex(tf.index)
    known = tf["prev_ct"].notna() & ((tf["prev_ct"] + pd.Timedelta(hours=settle_hours)) <= dts)
    tf["prev_known"] = known.astype(int)
    tf["prev_ot"] = tf["prev_ot_raw"].where(known)
    return tf[["game_id", "team", "prev_known", "prev_ot"]]


def from_cache(cache_dir: str) -> pd.DataFrame:
    """Convenience: game-level features straight from the parquet research cache."""
    return game_schedule_features(pd.read_parquet(f"{cache_dir}/nba_schedule.parquet"))
