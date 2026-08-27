"""
cfbd_ingestor.py — CollegeFootballData.com → NCAAF games, box scores, betting
lines and ASOF team-stat snapshots.

CFBD (https://collegefootballdata.com) is the SOLE history source for college
football. A free API key (email only, no card) unlocks everything we need:

  /teams/fbs                 → ncaaf_teams (school registry + name resolution)
  /games                     → games rows (scores, week, neutral site, conf game)
  /games/teams               → ncaaf_team_game_log (per-team per-game box score)
  /lines                     → odds rows (REAL historical spreads/totals/ML)
  /ratings/sp, /ratings/srs  → season-final ratings, used as NEXT season's prior
  /ratings/elo               → weekly Elo (genuinely ASOF)
  /talent                    → 247 team talent composite
  /player/returning          → returning production
  /stats/season[/advanced]   → efficiency, windowed by startWeek/endWeek

`/lines` is the reason this sport is buildable: it ships real historical
spreads, totals and moneylines, so ncaaf_spread and ncaaf_over_under can be
trained AND backtested against actual prices. Every other non-MLB totals/spread
model in this repo is blocked on exactly that missing history.

────────────────────────────────────────────────────────────────────────────
LEAK DISCIPLINE (the whole point of the snapshot design)
────────────────────────────────────────────────────────────────────────────
CFBD's season endpoints return FULL-SEASON totals for a year, which would leak
the result of the game we're predicting. So:

  • Efficiency / scoring / tempo are pulled WINDOWED (`endWeek = W - 1`) and
    stamped with an as_of_date strictly before week W's first kickoff. The
    feature engine's `as_of_date <= game_date` lookup therefore only ever sees
    completed prior weeks.
  • SP+ / SRS / talent / returning production are taken from the PRIOR season
    and stamped at a preseason as_of_date. Prior-season strength is known
    before a snap is played, so it is leak-free — and in a 12-game sport it is
    the single most valuable feature we have. In-season improvement is carried
    by the windowed efficiency stats.
  • Elo is genuinely week-indexed at the source, so it updates in-season.

The preseason row (games_played = 0) is what makes week 1 predictable at all.

────────────────────────────────────────────────────────────────────────────
FIELD-NAME ASSUMPTIONS
────────────────────────────────────────────────────────────────────────────
CFBD is unreachable from the dev sandbox (egress proxy), so exact JSON key
spellings could not be confirmed live. Every parser therefore reads through
`_pick()`, which accepts several candidate spellings (camelCase and snake_case)
and returns the first present. Run `python -m scripts.verify_cfbd` once with a
real key: it prints the actual keys each endpoint returns and flags anything a
parser would have missed. Fixes land in the `_pick` candidate lists only.

Usage:
    python -m data.ingestors.cfbd_ingestor --backfill 2015 2025
    python -m data.ingestors.cfbd_ingestor --backfill-lines 2015 2025
    python -m data.ingestors.cfbd_ingestor --season 2026            # weekly refresh
    python -m data.ingestors.cfbd_ingestor --results 2026-09-06     # finals only
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import config
from data.db import get_connection

SPORT = "NCAAF"

# Season types CFBD uses. Postseason carries bowls + the playoff; both are
# ingested (we need the results to settle) but bowls are excluded from TRAINING
# by the feature engine — opt-outs and month-long layoffs make them noise.
_SEASON_TYPES = ("regular", "postseason")


# ══════════════════════════════════════════════════════════════════════════════
# Pure helpers — no network, no DB. These are what the tests exercise.
# ══════════════════════════════════════════════════════════════════════════════

def _pick(row: dict, *names, default=None):
    """First present (non-None) value among several candidate key spellings."""
    if not isinstance(row, dict):
        return default
    for n in names:
        if n in row and row[n] is not None:
            return row[n]
    return default


def _num(row: dict, *names, default=None):
    """_pick coerced to float. Returns default on anything non-numeric."""
    v = _pick(row, *names)
    if v is None or isinstance(v, bool):
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _int(row: dict, *names, default=None):
    v = _num(row, *names)
    return int(v) if v is not None else default


def ncaaf_slug(school: str) -> str:
    """
    Slugify a school name for use inside a game_id.

    "Miami (OH)" → "miami-oh"; "Texas A&M" → "texas-a-m"; accents stripped.
    Mirrors slugify_fighter (UFC) — the display name lives in
    games.home_team/away_team, the slug only ever appears in the id.
    """
    if not school:
        return ""
    s = unicodedata.normalize("NFKD", str(school))
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Every non-alphanumeric run collapses to a single hyphen — including "&",
    # so "Texas A&M" → "texas-a-m". The slug only has to be stable and unique,
    # not pretty; the display name lives in games.home_team.
    s = re.sub(r"[^a-z0-9]+", "-", s.lower())
    return s.strip("-")


def build_ncaaf_game_id(game_date: str, away: str, home: str) -> str:
    return f"NCAAF_{game_date}_{ncaaf_slug(away)}_{ncaaf_slug(home)}"


def ncaaf_season_for_date(game_date: str) -> int:
    """
    Season label = calendar year of the FALL.

    January and February games are bowls / the playoff and belong to the PRIOR
    year's season. This is the mirror image of the NBA Oct-Dec rule and the
    same footgun: never derive a season from a date anywhere else — CFBD
    returns `season` explicitly on every game and that value always wins.
    """
    year, month = int(game_date[:4]), int(game_date[5:7])
    return year - 1 if month <= 2 else year


def shrink_to_prior(in_season, prior, games_played: int | None,
                    k: float | None = None):
    """
    Blend a season-to-date value toward the team's prior-season value.

        blended = w * in_season + (1 - w) * prior,  w = gp / (gp + k)

    A CFB team plays 12-13 games, so a raw season-to-date rate is noise for the
    first month. At k=4 the prior still carries half the weight after 4 games
    and ~24% after 13. Returns whichever side is available when one is missing,
    and None when neither is.
    """
    if k is None:
        k = config.NCAAF_PRIOR_SHRINKAGE_K
    if in_season is None:
        return prior
    if prior is None:
        return in_season
    gp = max(int(games_played or 0), 0)
    w = gp / (gp + k) if (gp + k) > 0 else 0.0
    return round(w * float(in_season) + (1.0 - w) * float(prior), 6)


def parse_teams(payload: list) -> list[dict]:
    """/teams/fbs → ncaaf_teams rows."""
    rows = []
    for t in payload or []:
        school = _pick(t, "school", "team")
        if not school:
            continue
        alt = [a for a in (_pick(t, "alt_name1", "altName1"),
                           _pick(t, "alt_name2", "altName2"),
                           _pick(t, "alt_name3", "altName3")) if a]
        rows.append({
            "school":         school,
            "abbreviation":   _pick(t, "abbreviation"),
            "mascot":         _pick(t, "mascot"),
            "conference":     _pick(t, "conference"),
            "division":       _pick(t, "division", "classification_division"),
            "classification": _pick(t, "classification", default="fbs"),
            "alt_names":      "|".join(dict.fromkeys(alt)) or None,
        })
    return rows


def parse_venues(payload: list) -> list[dict]:
    """
    /venues → ncaaf_venues rows.

    Elevation arrives in METRES from CFBD and is stored in FEET, because every
    altitude threshold anyone quotes for football (Laramie at 7,220, the Air
    Force / Wyoming effect, "a mile high") is in feet. Converting once here
    beats a magic 3.28 buried in the feature engine.
    """
    rows = []
    for v in payload or []:
        vid = _int(v, "id", "venue_id")
        if vid is None:
            continue
        elev_m = _num(v, "elevation")
        rows.append({
            "venue_id":     vid,
            "name":         _pick(v, "name"),
            "city":         _pick(v, "city"),
            "state":        _pick(v, "state"),
            "latitude":     _num(v, "latitude", "lat"),
            "longitude":    _num(v, "longitude", "lon", "lng"),
            "elevation_ft": round(elev_m * 3.28084, 1) if elev_m is not None else None,
            "capacity":     _int(v, "capacity"),
            "grass":        None if _pick(v, "grass") is None else int(bool(_pick(v, "grass"))),
            "dome":         None if _pick(v, "dome") is None else int(bool(_pick(v, "dome"))),
        })
    return rows


def parse_games(payload: list) -> list[dict]:
    """
    /games → games rows.

    Only games with a start date are kept. Scores stay NULL until the game is
    complete, so an unplayed game upserts cleanly and gets filled in later.
    """
    rows = []
    for g in payload or []:
        start = _pick(g, "start_date", "startDate")
        home  = _pick(g, "home_team", "homeTeam")
        away  = _pick(g, "away_team", "awayTeam")
        if not (start and home and away):
            continue
        game_date = str(start)[:10]
        season = _int(g, "season", "year") or ncaaf_season_for_date(game_date)
        hs = _num(g, "home_points", "homePoints")
        as_ = _num(g, "away_points", "awayPoints")
        completed = _pick(g, "completed")
        home_win = None
        if hs is not None and as_ is not None and hs != as_:
            home_win = int(hs > as_)
        rows.append({
            "game_id":     build_ncaaf_game_id(game_date, away, home),
            "sport":       SPORT,
            "season":      int(season),
            "game_date":   game_date,
            "commence_time": str(start),
            "home_team":   home,
            "away_team":   away,
            "home_score":  hs,
            "away_score":  as_,
            "home_win":    home_win,
            "venue_id":    _int(g, "venue_id", "venueId"),
            "week":        _int(g, "week"),
            "neutral_site": int(bool(_pick(g, "neutral_site", "neutralSite", default=False))),
            "conference_game": int(bool(_pick(g, "conference_game", "conferenceGame", default=False))),
            "data_source": "cfbd",
            "_cfbd_id":    _pick(g, "id", "game_id", "gameId"),
            "_season_type": _pick(g, "season_type", "seasonType"),
            "_completed":  bool(completed) if completed is not None else (hs is not None),
            "_home_classification": _pick(g, "home_classification", "homeClassification"),
            "_away_classification": _pick(g, "away_classification", "awayClassification"),
        })
    return rows


def parse_lines(payload: list, providers) -> list[dict]:
    """
    /lines → odds rows (one per market per game per provider).

    `providers` is a preference-ordered list (a bare string is accepted too).
    EVERY provider present is emitted, each under its own bookmaker label — no
    single CFBD provider covers 2015-2025, so picking one would silently throw
    away whole seasons. The feature engine resolves the preference at read
    time via config.NCAAF_LINE_BOOKMAKER_PRIORITY.

    `spread` in CFBD is HOME-relative and matches our `spread_home` convention
    exactly (negative = home favoured), so no sign flip is applied — the
    settlement path grades `margin + spread_home` unchanged.

    Prices are often absent in the historical archive; a NULL price still gives
    a usable TARGET (the line is what the target is computed against), which is
    all training needs. Live scoring always uses real DK prices.
    """
    if isinstance(providers, str):
        providers = [providers]
    wanted = {str(p).lower(): p for p in providers}
    rows = []
    for g in payload or []:
        start = _pick(g, "start_date", "startDate")
        home  = _pick(g, "home_team", "homeTeam")
        away  = _pick(g, "away_team", "awayTeam")
        if not (start and home and away):
            continue
        game_date = str(start)[:10]
        game_id = build_ncaaf_game_id(game_date, away, home)
        for ln in _pick(g, "lines", default=[]) or []:
            key = str(_pick(ln, "provider", default="")).lower()
            if key not in wanted:
                continue
            spread  = _num(ln, "spread")
            total   = _num(ln, "over_under", "overUnder")
            home_ml = _num(ln, "home_moneyline", "homeMoneyline")
            away_ml = _num(ln, "away_moneyline", "awayMoneyline")
            # snapshot_at = the game date: unambiguously pre-game for a
            # historical archive row, so the pregame guard keeps it.
            base = {
                "game_id":       game_id,
                "sport":         SPORT,
                "bookmaker":     config.ncaaf_line_bookmaker(wanted[key]),
                "snapshot_type": "open",
                "snapshot_at":   game_date,
            }
            if spread is not None:
                rows.append({**base, "market": "spreads", "spread_home": spread,
                             "home_price": _num(ln, "home_spread_price", "homeSpreadPrice"),
                             "away_price": _num(ln, "away_spread_price", "awaySpreadPrice")})
            if total is not None:
                rows.append({**base, "market": "totals", "total_line": total,
                             "over_price":  _num(ln, "over_price", "overPrice"),
                             "under_price": _num(ln, "under_price", "underPrice")})
            if home_ml is not None or away_ml is not None:
                rows.append({**base, "market": "h2h",
                             "home_price": home_ml, "away_price": away_ml})
    return rows


def parse_team_game_stats(payload: list,
                          id_map: dict | None = None,
                          games_by_id: dict | None = None) -> list[dict]:
    """
    /games/teams → ncaaf_team_game_log rows (two per game, one per team).

    `id_map` maps CFBD's numeric game id → our game_id; `games_by_id` carries
    the schedule metadata (season/week/date/neutral/conference) keyed by our
    game_id. Both come from the /games pull, so the log always agrees with the
    games row. A game missing from id_map is skipped rather than guessed at.

    CFBD returns each game with a `teams` list, each carrying a flat `stats`
    list of {category, stat} pairs. `possessionTime` is "MM:SS"; third downs
    arrive as "5-13".
    """
    id_map = id_map or {}
    games_by_id = games_by_id or {}
    out = []
    for g in payload or []:
        teams = _pick(g, "teams", default=[]) or []
        if len(teams) != 2:
            continue
        game_id = id_map.get(_pick(g, "id", "game_id", "gameId"))
        if not game_id:
            continue
        pts = {}
        for t in teams:
            pts[_pick(t, "school", "team")] = _num(t, "points")
        for t in teams:
            school = _pick(t, "school", "team")
            if not school:
                continue
            opp = next((_pick(o, "school", "team") for o in teams
                        if _pick(o, "school", "team") != school), None)
            stats = {}
            for s in _pick(t, "stats", default=[]) or []:
                cat = _pick(s, "category")
                if cat:
                    stats[str(cat)] = _pick(s, "stat")
            third_c, third_a = _split_ratio(stats.get("thirdDownEff"))
            pen_n, pen_y = _split_ratio(stats.get("totalPenaltiesYards"))
            # CFBD exposes no totalPlays category, so derive it from rush + pass
            # attempts (completionAttempts is "21-39", attempts is the second
            # number). In NCAA scoring a sack is charged as a rushing attempt,
            # so rushingAttempts already absorbs them and this does not
            # undercount dropbacks. Plays wiped out by penalty are excluded —
            # a small, consistent undercount that differences out.
            _comp, pass_att = _split_ratio(stats.get("completionAttempts"))
            rush_att = _to_int(stats.get("rushingAttempts"))
            total_plays = ((rush_att or 0) + (pass_att or 0)) or None
            meta = games_by_id.get(game_id, {})
            out.append({
                "game_id":   game_id,
                "team":      school,
                "opponent":  opp,
                "season":    meta.get("season"),
                "week":      meta.get("week"),
                "season_type": meta.get("season_type"),
                "game_date": meta.get("game_date"),
                "is_home":   int(_pick(t, "home_away", "homeAway", default="") == "home"),
                "is_neutral_site":    meta.get("neutral_site"),
                "is_conference_game": meta.get("conference_game"),
                "points":            _to_int(pts.get(school)),
                "points_allowed":    _to_int(pts.get(opp)),
                "total_yards":       _to_int(stats.get("totalYards")),
                "rushing_yards":     _to_int(stats.get("rushingYards")),
                "passing_yards":     _to_int(stats.get("netPassingYards")),
                "plays":             total_plays,
                "possession_seconds": _possession_seconds(stats.get("possessionTime")),
                "first_downs":       _to_int(stats.get("firstDowns")),
                "third_down_conv":   third_c,
                "third_down_att":    third_a,
                "turnovers":         _to_int(stats.get("turnovers")),
                "penalties":         pen_n,
                "penalty_yards":     pen_y,
                "sacks":             _to_float(stats.get("sacks")),
                "tackles_for_loss":  _to_float(stats.get("tacklesForLoss")),
            })
    return out



def _comp_att(val) -> tuple[int | None, int | None]:
    """
    '18/30' -> (18, 30). Completions/attempts, SLASH-separated.

    Deliberately not _split_ratio: that one splits on '-' for third-down and
    penalty strings. Passing it a 'C/ATT' value returns (None, None) silently,
    which drops every passer and yields an empty QB table that looks like an
    API outage rather than a parsing bug.
    """
    if not isinstance(val, str) or "/" not in val:
        return (None, None)
    a, _, b = val.partition("/")
    try:
        return (int(a.strip()), int(b.strip()))
    except (TypeError, ValueError):
        return (None, None)


def _athlete_stats(team_payload: dict, category: str) -> dict:
    """
    {player_id: {stat_name: raw_value}} for one category of one team-game.

    CFBD nests these three deep: categories -> types -> athletes. Reading by
    NAME at every level (never index) so a reordered payload cannot silently
    map yards onto attempts.
    """
    out: dict = {}
    for cat in _pick(team_payload, "categories", default=[]) or []:
        if str(_pick(cat, "name", default="")).lower() != category:
            continue
        for typ in _pick(cat, "types", default=[]) or []:
            tname = str(_pick(typ, "name", default="")).upper()
            for ath in _pick(typ, "athletes", default=[]) or []:
                pid = _pick(ath, "id", "playerId")
                if pid is None:
                    continue
                rec = out.setdefault(str(pid), {"name": _pick(ath, "name")})
                rec[tname] = _pick(ath, "stat")
    return out


def parse_qb_game_stats(payload: list,
                        id_map: dict | None = None,
                        games_by_id: dict | None = None) -> list[dict]:
    """
    /games/players -> ncaaf_qb_game rows: every passer, per team-game.

    `is_primary` is the passer with the most ATTEMPTS (ties broken on yards,
    then on a stable player-id sort so re-ingesting the same game can never
    flip the flag). Attempts, not completions or yards, because attempts is the
    participation signal -- a starter who is pulled after a bad half still owns
    the snaps he took, and a wildcat/trick-play passer never accumulates them.

    QBR is deliberately ignored: it is ESPN-derived and present for only ~48%
    of team-games, so any feature built on it would be missing at random across
    half the sample. Attempts/completions/yards/TD/INT are present in 100% of
    FBS team-games back to 2015.
    """
    id_map = id_map or {}
    games_by_id = games_by_id or {}
    out: list[dict] = []
    for g in payload or []:
        game_id = id_map.get(_pick(g, "id", "game_id", "gameId"))
        if not game_id:
            continue
        meta = games_by_id.get(game_id, {})
        teams = _pick(g, "teams", default=[]) or []
        for t in teams:
            school = _pick(t, "school", "team")
            if not school:
                continue
            opp = next((_pick(o, "school", "team") for o in teams
                        if _pick(o, "school", "team") != school), None)
            passing = _athlete_stats(t, "passing")
            if not passing:
                continue
            rushing = _athlete_stats(t, "rushing")

            rows = []
            for pid, st in passing.items():
                comp, att = _comp_att(st.get("C/ATT"))
                if att is None:            # no parseable attempts -> not a passer
                    continue
                r = rushing.get(pid, {})
                rows.append({
                    "game_id":   game_id,
                    "team":      school,
                    "opponent":  opp,
                    "season":    meta.get("season"),
                    "week":      meta.get("week"),
                    "season_type": meta.get("season_type"),
                    "game_date": meta.get("game_date"),
                    "player_id": pid,
                    "player_name": st.get("name"),
                    "is_primary": 0,
                    "attempts":    att,
                    "completions": comp,
                    "pass_yards":  _to_int(st.get("YDS")),
                    "pass_td":     _to_int(st.get("TD")),
                    "interceptions": _to_int(st.get("INT")),
                    "rush_att":    _to_int(r.get("CAR")),
                    "rush_yards":  _to_int(r.get("YDS")),
                    "rush_td":     _to_int(r.get("TD")),
                })
            if not rows:
                continue
            rows.sort(key=lambda x: (-(x["attempts"] or 0),
                                     -(x["pass_yards"] or 0),
                                     str(x["player_id"])))
            rows[0]["is_primary"] = 1
            out.extend(rows)
    return out

def _split_ratio(val) -> tuple[int | None, int | None]:
    """'5-13' → (5, 13). Anything else → (None, None)."""
    if not val or not isinstance(val, str) or "-" not in val:
        return (None, None)
    a, _, b = val.partition("-")
    try:
        return (int(a.strip()), int(b.strip()))
    except ValueError:
        return (None, None)


def _possession_seconds(val) -> int | None:
    """'31:24' → 1884 seconds."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str) and ":" in val:
        m, _, s = val.partition(":")
        try:
            return int(m.strip()) * 60 + int(s.strip())
        except ValueError:
            return None
    return _to_int(val)


def _to_int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_season_stats(payload: list) -> dict:
    """
    /stats/season → {school: {stat_key: value}}.

    Returned as flat {team, statName, statValue} triples; we keep the handful
    the feature set actually uses.
    """
    out: dict = {}
    for r in payload or []:
        team = _pick(r, "team", "school")
        name = _pick(r, "stat_name", "statName")
        if not team or not name:
            continue
        out.setdefault(team, {})[str(name)] = _num(r, "stat_value", "statValue")
    return out


def parse_advanced_stats(payload: list) -> dict:
    """
    /stats/season/advanced → {school: {flat_metric: value}}.

    The payload nests offense/defense objects; we flatten to the handful of
    metrics the model uses so the snapshot builder stays trivial.
    """
    out: dict = {}
    for r in payload or []:
        team = _pick(r, "team", "school")
        if not team:
            continue
        off = _pick(r, "offense", default={}) or {}
        dfn = _pick(r, "defense", default={}) or {}
        ppa_o, ppa_d = _pick(off, "ppa"), _pick(dfn, "ppa")
        out[team] = {
            "epa_per_play_off":     _to_float(ppa_o),
            "epa_per_play_def":     _to_float(ppa_d),
            "success_rate_off":     _num(off, "success_rate", "successRate"),
            "success_rate_def":     _num(dfn, "success_rate", "successRate"),
            "explosiveness_off":    _num(off, "explosiveness"),
            "explosiveness_def":    _num(dfn, "explosiveness"),
            "havoc_rate":           _num(_pick(dfn, "havoc", default={}) or {}, "total"),
            "havoc_rate_allowed":   _num(_pick(off, "havoc", default={}) or {}, "total"),
            "finishing_drives_off": _num(_pick(off, "field_position", "fieldPosition", default={}) or {},
                                         "average_start", "averageStart"),
            "finishing_drives_def": _num(_pick(dfn, "field_position", "fieldPosition", default={}) or {},
                                         "average_start", "averageStart"),
            "avg_field_position_off": _num(_pick(off, "field_position", "fieldPosition", default={}) or {},
                                           "average_start", "averageStart"),
            "plays_per_game":       None,   # filled from the game log
            "seconds_per_play":     None,   # filled from the game log
        }
    return out


def parse_ratings(payload: list, kind: str) -> dict:
    """
    /ratings/sp | /ratings/srs | /ratings/elo → {school: {col: value}}.
    """
    out: dict = {}
    for r in payload or []:
        team = _pick(r, "team", "school")
        if not team:
            continue
        if kind == "sp":
            out[team] = {
                "sp_overall":       _num(r, "rating"),
                "sp_offense":       _num(_pick(r, "offense", default={}) or {}, "rating"),
                "sp_defense":       _num(_pick(r, "defense", default={}) or {}, "rating"),
                "sp_special_teams": _num(_pick(r, "special_teams", "specialTeams", default={}) or {}, "rating"),
            }
        elif kind == "srs":
            out[team] = {"srs": _num(r, "rating", "srs")}
        elif kind == "elo":
            out[team] = {"elo": _num(r, "elo", "rating")}
    return out


def parse_talent(payload: list) -> dict:
    """/talent → {school: talent_composite}."""
    return {t: v for t, v in (
        (_pick(r, "school", "team"), _num(r, "talent"))
        for r in payload or []) if t and v is not None}


def parse_returning(payload: list) -> dict:
    """/player/returning → {school: total returning PPA}."""
    out = {}
    for r in payload or []:
        team = _pick(r, "team", "school")
        if not team:
            continue
        val = _num(r, "total_ppa", "totalPPA", "percent_ppa", "percentPPA")
        if val is not None:
            out[team] = val
    return out


# ══════════════════════════════════════════════════════════════════════════════
# HTTP
# ══════════════════════════════════════════════════════════════════════════════

_SESSION: requests.Session | None = None


def _session() -> requests.Session:
    global _SESSION
    if _SESSION is None:
        _SESSION = requests.Session()
        _SESSION.headers.update({
            "Authorization": f"Bearer {config.CFBD_API_KEY}",
            "Accept": "application/json",
        })
    return _SESSION


def _get(path: str, **params):
    """
    One CFBD GET. Returns the decoded body, or None on any failure.

    Fails soft on purpose: a single missing week must never sink a multi-season
    backfill, and the callers all treat None as "no rows for this slice".
    """
    if not config.CFBD_API_KEY:
        raise RuntimeError(
            "CFBD_API_KEY is not set. Get a free key at "
            "https://collegefootballdata.com/key and add it to .env "
            "(and to the Railway variables for the worker)."
        )
    url = f"{config.CFBD_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    clean = {k: v for k, v in params.items() if v is not None}
    for attempt in range(3):
        try:
            r = _session().get(url, params=clean, timeout=30)
            if r.status_code == 429:          # rate limited — back off and retry
                wait = 5 * (attempt + 1)
                logger.warning(f"CFBD 429 on {path} — sleeping {wait}s")
                time.sleep(wait)
                continue
            r.raise_for_status()
            time.sleep(config.CFBD_REQUEST_PAUSE)
            return r.json()
        except Exception as exc:                        # noqa: BLE001
            if attempt == 2:
                logger.warning(f"CFBD {path} {clean} failed: {exc}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


# ══════════════════════════════════════════════════════════════════════════════
# Writers
# ══════════════════════════════════════════════════════════════════════════════

_VENUE_COLS = ["venue_id", "name", "city", "state", "latitude", "longitude",
               "elevation_ft", "capacity", "grass", "dome"]

_VENUE_UPSERT = f"""
    INSERT INTO ncaaf_venues ({', '.join(_VENUE_COLS)})
    VALUES ({', '.join('%(' + c + ')s' for c in _VENUE_COLS)})
    ON CONFLICT(venue_id) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in _VENUE_COLS if c != 'venue_id')}
"""

_TEAM_UPSERT = """
    INSERT INTO ncaaf_teams (school, abbreviation, mascot, conference,
                             division, classification, alt_names)
    VALUES (%(school)s, %(abbreviation)s, %(mascot)s, %(conference)s,
            %(division)s, %(classification)s, %(alt_names)s)
    ON CONFLICT(school) DO UPDATE SET
        abbreviation   = EXCLUDED.abbreviation,
        mascot         = EXCLUDED.mascot,
        conference     = EXCLUDED.conference,
        division       = EXCLUDED.division,
        classification = EXCLUDED.classification,
        alt_names      = EXCLUDED.alt_names
"""

# COALESCE on scores so an unplayed-game upsert can never blank a final score
# that already landed (the WNBA/NBA _upsert_games lesson).
_GAME_UPSERT = """
    INSERT INTO games (game_id, sport, season, game_date, commence_time,
                       home_team, away_team, home_score, away_score, home_win,
                       week, neutral_site, conference_game, venue_id, data_source)
    VALUES (%(game_id)s, %(sport)s, %(season)s, %(game_date)s, %(commence_time)s,
            %(home_team)s, %(away_team)s, %(home_score)s, %(away_score)s, %(home_win)s,
            %(week)s, %(neutral_site)s, %(conference_game)s, %(venue_id)s, %(data_source)s)
    ON CONFLICT(game_id) DO UPDATE SET
        home_score      = COALESCE(EXCLUDED.home_score, games.home_score),
        away_score      = COALESCE(EXCLUDED.away_score, games.away_score),
        home_win        = COALESCE(EXCLUDED.home_win,   games.home_win),
        commence_time   = COALESCE(games.commence_time, EXCLUDED.commence_time),
        week            = COALESCE(EXCLUDED.week,            games.week),
        neutral_site    = COALESCE(EXCLUDED.neutral_site,    games.neutral_site),
        conference_game = COALESCE(EXCLUDED.conference_game, games.conference_game),
        venue_id        = COALESCE(EXCLUDED.venue_id,        games.venue_id),
        season          = EXCLUDED.season,
        updated_at      = NOW()::TEXT
"""

_LOG_COLS = ["game_id", "team", "opponent", "season", "week", "season_type",
             "game_date", "is_home", "is_neutral_site", "is_conference_game",
             "points", "points_allowed", "total_yards", "rushing_yards",
             "passing_yards", "plays", "possession_seconds", "first_downs",
             "third_down_conv", "third_down_att", "turnovers", "penalties",
             "penalty_yards", "sacks", "tackles_for_loss"]

_LOG_UPSERT = f"""
    INSERT INTO ncaaf_team_game_log ({', '.join(_LOG_COLS)})
    VALUES ({', '.join('%(' + c + ')s' for c in _LOG_COLS)})
    ON CONFLICT(team, game_id) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in _LOG_COLS if c not in ('team', 'game_id'))}
"""

_QB_COLS = ["game_id", "team", "opponent", "season", "week", "season_type",
            "game_date", "player_id", "player_name", "is_primary",
            "attempts", "completions", "pass_yards", "pass_td",
            "interceptions", "rush_att", "rush_yards", "rush_td"]

_QB_UPSERT = f"""
    INSERT INTO ncaaf_qb_game ({', '.join(_QB_COLS)})
    VALUES ({', '.join('%(' + c + ')s' for c in _QB_COLS)})
    ON CONFLICT(game_id, team, player_id) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in _QB_COLS
                   if c not in ('game_id', 'team', 'player_id'))}
"""

_STAT_COLS = ["team", "season", "as_of_date", "games_played",
              "sp_overall", "sp_offense", "sp_defense", "sp_special_teams",
              "srs", "elo", "talent", "returning_ppa",
              "epa_per_play_off", "epa_per_play_def",
              "success_rate_off", "success_rate_def",
              "explosiveness_off", "explosiveness_def",
              "havoc_rate", "havoc_rate_allowed",
              "finishing_drives_off", "finishing_drives_def",
              "avg_field_position_off",
              "third_down_rate_off", "third_down_rate_def", "turnover_margin_pg",
              "plays_per_game", "seconds_per_play",
              "points_per_game", "points_allowed_pg", "points_last_3",
              "point_differential", "wins", "losses",
              "conference", "classification"]

_STAT_UPSERT = f"""
    INSERT INTO ncaaf_team_stats ({', '.join(_STAT_COLS)})
    VALUES ({', '.join('%(' + c + ')s' for c in _STAT_COLS)})
    ON CONFLICT(team, season, as_of_date) DO UPDATE SET
        {', '.join(f'{c} = EXCLUDED.{c}' for c in _STAT_COLS
                   if c not in ('team', 'season', 'as_of_date'))}
"""

# Append-only odds table with no natural unique key — guard on the exact tuple
# so a re-run of the lines backfill is a no-op instead of a duplicate.
_ODDS_INSERT = """
    INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                      home_price, away_price, spread_home, total_line,
                      over_price, under_price)
    SELECT %(game_id)s, %(sport)s, %(market)s, %(bookmaker)s, %(snapshot_type)s,
           %(snapshot_at)s, %(home_price)s, %(away_price)s, %(spread_home)s,
           %(total_line)s, %(over_price)s, %(under_price)s
    WHERE EXISTS (SELECT 1 FROM games g WHERE g.game_id = %(game_id)s)
      AND NOT EXISTS (
        SELECT 1 FROM odds o
        WHERE o.game_id = %(game_id)s AND o.market = %(market)s
          AND o.bookmaker = %(bookmaker)s AND o.snapshot_at = %(snapshot_at)s)
"""

_ODDS_FIELDS = ["game_id", "sport", "market", "bookmaker", "snapshot_type",
                "snapshot_at", "home_price", "away_price", "spread_home",
                "total_line", "over_price", "under_price"]


def _norm(rows: list[dict], fields: list[str]) -> list[dict]:
    """Fill every declared field so executemany's named params always bind."""
    return [{f: r.get(f) for f in fields} for r in rows]


# ══════════════════════════════════════════════════════════════════════════════
# Ingest — schedule, box scores, lines
# ══════════════════════════════════════════════════════════════════════════════

_GAME_FIELDS = ["game_id", "sport", "season", "game_date", "commence_time",
                "home_team", "away_team", "home_score", "away_score", "home_win",
                "week", "neutral_site", "conference_game", "venue_id", "data_source"]


def ingest_ncaaf_teams(season: int, conn=None) -> int:
    """/teams/fbs → ncaaf_teams. Re-run per season to track realignment."""
    own = conn is None
    conn = conn or get_connection()
    try:
        rows = parse_teams(_get("/teams/fbs", year=season))
        if rows:
            conn.executemany(_TEAM_UPSERT, rows)
            conn.commit()
        logger.info(f"NCAAF teams {season}: {len(rows)} school(s)")
        return len(rows)
    finally:
        if own:
            conn.close()


def ingest_ncaaf_venues(conn=None) -> int:
    """/venues → ncaaf_venues. Season-independent; one call refreshes all."""
    own = conn is None
    conn = conn or get_connection()
    try:
        rows = parse_venues(_get("/venues"))
        if rows:
            conn.executemany(_VENUE_UPSERT, _norm(rows, _VENUE_COLS))
            conn.commit()
        logger.info(f"NCAAF venues: {len(rows)} venue(s)")
        return len(rows)
    finally:
        if own:
            conn.close()


def ingest_ncaaf_games(season: int, conn=None) -> tuple[int, dict, dict]:
    """
    /games → games rows for both season types.

    Returns (rows_written, id_map, games_by_id) so the caller can chain the
    box-score pull without re-fetching the schedule.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        parsed: list[dict] = []
        for stype in _SEASON_TYPES:
            payload = _get("/games", year=season, seasonType=stype)
            for row in parse_games(payload):
                row.setdefault("_season_type", stype)
                parsed.append(row)

        # Keep games with at least one FBS team. FBS-vs-FCS rows are needed for
        # the FBS team's own form and rest days; the feature engine refuses to
        # SCORE them (an FCS opponent has no stats row), which is the gate.
        keep = [g for g in parsed
                if "fbs" in {str(g.get("_home_classification") or "fbs").lower(),
                             str(g.get("_away_classification") or "fbs").lower()}]

        conn.executemany(_GAME_UPSERT, _norm(keep, _GAME_FIELDS))
        conn.commit()

        id_map = {g["_cfbd_id"]: g["game_id"] for g in keep if g.get("_cfbd_id") is not None}
        games_by_id = {
            g["game_id"]: {
                "season": g["season"], "week": g["week"],
                "season_type": g.get("_season_type"), "game_date": g["game_date"],
                "neutral_site": g["neutral_site"],
                "conference_game": g["conference_game"],
            } for g in keep
        }
        logger.info(f"NCAAF games {season}: {len(keep)} game(s) upserted "
                    f"({len(parsed) - len(keep)} FCS-only skipped)")
        return len(keep), id_map, games_by_id
    finally:
        if own:
            conn.close()


def ingest_ncaaf_game_log(season: int, id_map: dict, games_by_id: dict,
                          conn=None) -> int:
    """/games/teams (per week) → ncaaf_team_game_log."""
    own = conn is None
    conn = conn or get_connection()
    try:
        weeks = sorted({m["week"] for m in games_by_id.values() if m.get("week")})
        total = 0
        for stype in _SEASON_TYPES:
            for wk in weeks or [None]:
                payload = _get("/games/teams", year=season, week=wk, seasonType=stype)
                rows = parse_team_game_stats(payload, id_map, games_by_id)
                if rows:
                    conn.executemany(_LOG_UPSERT, _norm(rows, _LOG_COLS))
                    conn.commit()
                    total += len(rows)
        logger.info(f"NCAAF game log {season}: {total} team-game row(s)")
        return total
    finally:
        if own:
            conn.close()



def ingest_ncaaf_qb_log(season: int, id_map: dict, games_by_id: dict,
                        conn=None) -> int:
    """/games/players (per week) -> ncaaf_qb_game."""
    own = conn is None
    conn = conn or get_connection()
    try:
        weeks = sorted({m["week"] for m in games_by_id.values() if m.get("week")})
        total = 0
        for stype in _SEASON_TYPES:
            for wk in weeks or [None]:
                payload = _get("/games/players", year=season, week=wk,
                               seasonType=stype)
                rows = parse_qb_game_stats(payload, id_map, games_by_id)
                if rows:
                    conn.executemany(_QB_UPSERT, _norm(rows, _QB_COLS))
                    conn.commit()
                    total += len(rows)
        logger.info(f"NCAAF QB log {season}: {total} passer-game row(s)")
        return total
    finally:
        if own:
            conn.close()

def ingest_ncaaf_lines(season: int, conn=None) -> int:
    """
    /lines → odds rows under the cfbd_consensus bookmaker.

    This is the training-line source. Live scoring still reads DraftKings from
    The Odds API — the DraftKings-only invariant is untouched, since this
    bookmaker key only ever appears on backfilled historical rows.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        rows: list[dict] = []
        for stype in _SEASON_TYPES:
            payload = _get("/lines", year=season, seasonType=stype)
            rows.extend(parse_lines(payload, config.CFBD_LINES_PROVIDERS))
        if rows:
            conn.executemany(_ODDS_INSERT, _norm(rows, _ODDS_FIELDS))
            conn.commit()
        by_book: dict = {}
        for r in rows:
            by_book[r["bookmaker"]] = by_book.get(r["bookmaker"], 0) + 1
        logger.info(f"NCAAF lines {season}: {len(rows)} row(s) {by_book or ''}")
        return len(rows)
    finally:
        if own:
            conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ASOF team-stat snapshots — the leak-critical piece
# ══════════════════════════════════════════════════════════════════════════════

def _local_aggregates(log_rows: list[dict]) -> dict:
    """
    Season-to-date aggregates per team from already-played games only.

    log_rows must ALREADY be filtered to games before the snapshot date — this
    function does no date filtering of its own, so the caller owns the leak
    boundary and there is exactly one place to get it wrong.
    """
    by_team: dict = {}
    for r in log_rows:
        by_team.setdefault(r["team"], []).append(r)

    out: dict = {}
    for team, rows in by_team.items():
        rows = sorted(rows, key=lambda x: (x.get("game_date") or ""))
        gp = len(rows)
        pts = [r["points"] for r in rows if r.get("points") is not None]
        pa  = [r["points_allowed"] for r in rows if r.get("points_allowed") is not None]
        plays = [r["plays"] for r in rows if r.get("plays")]
        poss  = [r["possession_seconds"] for r in rows if r.get("possession_seconds")]
        tdc   = sum(r["third_down_conv"] or 0 for r in rows)
        tda   = sum(r["third_down_att"] or 0 for r in rows)
        tos   = [r["turnovers"] for r in rows if r.get("turnovers") is not None]

        wins = sum(1 for r in rows
                   if r.get("points") is not None and r.get("points_allowed") is not None
                   and r["points"] > r["points_allowed"])
        losses = sum(1 for r in rows
                     if r.get("points") is not None and r.get("points_allowed") is not None
                     and r["points"] < r["points_allowed"])

        # Opponent turnovers aren't in our own row, so turnover MARGIN is
        # approximated as (league-average giveaways − ours). Left as negated
        # giveaways per game: the sign is right and it differences cleanly.
        out[team] = {
            "games_played":      gp,
            "points_per_game":   round(sum(pts) / len(pts), 4) if pts else None,
            "points_allowed_pg": round(sum(pa) / len(pa), 4) if pa else None,
            "points_last_3":     round(sum(pts[-3:]) / len(pts[-3:]), 4) if pts else None,
            "point_differential": round((sum(pts) - sum(pa)) / gp, 4) if (pts and pa and gp) else None,
            "plays_per_game":    round(sum(plays) / len(plays), 4) if plays else None,
            "seconds_per_play":  (round(sum(poss) / sum(plays), 4)
                                  if plays and poss and sum(plays) else None),
            "third_down_rate_off": round(tdc / tda, 4) if tda else None,
            "turnover_margin_pg":  round(-sum(tos) / len(tos), 4) if tos else None,
            "wins": wins, "losses": losses,
        }
    return out


def _prior_season_context(season: int) -> dict:
    """
    Everything the preseason prior is built from: the PRIOR season's final SP+,
    SRS, talent, returning production and efficiency.

    Prior-season strength is known before a snap of the new season is played,
    so it is leak-free — and in a 12-game sport it is the most valuable signal
    we have. Current-season SP+ is deliberately never used: it is computed from
    the very games we would be predicting.
    """
    prev = season - 1
    # A failed fetch (_get → None, e.g. rate-limited) is NOT the same as an
    # empty payload. Building snapshots from a failed core fetch writes
    # all-NULL rating columns, and the blanket upsert then OVERWRITES good
    # rows from earlier runs with NULLs — that is exactly how the 2016-2025
    # weekly snapshots lost SP+/SRS/EPA on 2026-08-23. Refuse loudly instead;
    # the fault-isolated backfill reports the season and moves on.
    sp_p  = _get("/ratings/sp", year=prev)
    srs_p = _get("/ratings/srs", year=prev)
    adv_p = _get("/stats/season/advanced", year=prev)
    if sp_p is None or srs_p is None or adv_p is None:
        raise RuntimeError(
            f"CFBD prior-season context for {season} unavailable "
            f"(sp={'ok' if sp_p is not None else 'FAILED'}, "
            f"srs={'ok' if srs_p is not None else 'FAILED'}, "
            f"adv={'ok' if adv_p is not None else 'FAILED'}) — rate-limited? "
            f"Refusing to build snapshots that would overwrite good rows with NULLs.")
    sp   = parse_ratings(sp_p, "sp")
    srs  = parse_ratings(srs_p, "srs")
    # Talent/returning can be legitimately absent in early seasons (talent
    # starts ~2015) — an empty payload is fine; only a FAILED fetch of the
    # core trio above is fatal.
    tal  = parse_talent(_get("/talent", year=season))          # recruiting: current year is preseason-known
    ret  = parse_returning(_get("/player/returning", year=season))
    adv  = parse_advanced_stats(adv_p)
    merged: dict = {}
    for team in set(sp) | set(srs) | set(tal) | set(ret) | set(adv):
        merged[team] = {
            **(sp.get(team) or {}),
            **(srs.get(team) or {}),
            "talent":        tal.get(team),
            "returning_ppa": ret.get(team),
            "_prior_adv":    adv.get(team) or {},
        }
    return merged


_ADV_KEYS = ["epa_per_play_off", "epa_per_play_def", "success_rate_off",
             "success_rate_def", "explosiveness_off", "explosiveness_def",
             "havoc_rate", "havoc_rate_allowed", "finishing_drives_off",
             "finishing_drives_def", "avg_field_position_off"]


def _stat_row(team: str, season: int, as_of: str, gp: int,
              prior: dict, adv: dict, local: dict,
              elo: dict, team_meta: dict,
              prior_local: dict | None = None) -> dict:
    """
    Assemble one ncaaf_team_stats row, shrinking every rate toward the prior.

    `prior_local` is the team's FULL prior-season scoring/tempo aggregate. It
    matters more than it looks: without it a preseason row has no points-per-
    game at all, and since the training builder drops any row with a null
    feature, every week-1 game (~16% of a season) would silently vanish from
    the matrix. Prior-season scoring is known before kickoff, so it is a
    legitimate prior rather than a fabricated value.
    """
    prior_adv = prior.get("_prior_adv") or {}
    prior_local = prior_local or {}
    row = {
        "team": team, "season": season, "as_of_date": as_of,
        "games_played": gp,
        # Ratings are PRIOR-season values held constant through the year (see
        # _prior_season_context); Elo is genuinely week-indexed at the source.
        "sp_overall":       prior.get("sp_overall"),
        "sp_offense":       prior.get("sp_offense"),
        "sp_defense":       prior.get("sp_defense"),
        "sp_special_teams": prior.get("sp_special_teams"),
        "srs":              prior.get("srs"),
        "elo":              elo.get(team, {}).get("elo") if elo else None,
        "talent":           prior.get("talent"),
        "returning_ppa":    prior.get("returning_ppa"),
        "conference":       team_meta.get("conference"),
        "classification":   team_meta.get("classification"),
    }
    for key in _ADV_KEYS:
        row[key] = shrink_to_prior(adv.get(key), prior_adv.get(key), gp)
    for key in ("plays_per_game", "seconds_per_play", "points_per_game",
                "points_allowed_pg", "third_down_rate_off", "turnover_margin_pg",
                "point_differential"):
        row[key] = shrink_to_prior(local.get(key), prior_local.get(key), gp)
    row["third_down_rate_def"] = None      # needs opponent rows; v2
    # Recent form falls back to the prior season's rate before enough games
    # have been played for a last-3 to mean anything.
    row["points_last_3"] = (local.get("points_last_3")
                            if local.get("games_played") else prior_local.get("points_per_game"))
    row["wins"]   = local.get("wins", 0)
    row["losses"] = local.get("losses", 0)
    return row


def ingest_ncaaf_team_stats(season: int, conn=None) -> int:
    """
    Build every ASOF snapshot for a season.

    One preseason row per team (games_played = 0, prior-season ratings only —
    this is what makes week 1 predictable), then one row per team per week
    stamped the day BEFORE that week's first kickoff, carrying only stats from
    completed prior weeks.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        teams_meta = {
            r[0]: {"conference": r[1], "classification": r[2]}
            for r in conn.execute(
                "SELECT school, conference, classification FROM ncaaf_teams").fetchall()
        }
        week_starts = {
            int(r[0]): r[1] for r in conn.execute("""
                SELECT week, MIN(game_date) FROM games
                WHERE sport = %(s)s AND season = %(y)s AND week IS NOT NULL
                GROUP BY week ORDER BY week
            """, {"s": SPORT, "y": season}).fetchall() if r[0] is not None
        }
        log_cols = ["team", "week", "game_date", "points", "points_allowed",
                    "plays", "possession_seconds", "third_down_conv",
                    "third_down_att", "turnovers"]
        log_rows = [dict(zip(log_cols, r)) for r in conn.execute(f"""
            SELECT {', '.join(log_cols)} FROM ncaaf_team_game_log
            WHERE season = %(y)s
        """, {"y": season}).fetchall()]

        prior = _prior_season_context(season)
        prior_log = [dict(zip(log_cols, r)) for r in conn.execute(f"""
            SELECT {', '.join(log_cols)} FROM ncaaf_team_game_log
            WHERE season = %(y)s
        """, {"y": season - 1}).fetchall()]
        prior_local = _local_aggregates(prior_log)
        rows: list[dict] = []

        # ── Preseason: prior-season strength only ──────────────────────────────
        preseason_as_of = f"{season}-08-01"
        for team, p in prior.items():
            rows.append(_stat_row(team, season, preseason_as_of, 0, p,
                                  p.get("_prior_adv") or {}, {}, {},
                                  teams_meta.get(team, {}),
                                  prior_local.get(team, {})))

        # ── One snapshot per week, built from completed prior weeks only ───────
        for wk in sorted(week_starts):
            if wk <= 1:
                continue                      # week 1 is served by the preseason row
            as_of = _day_before(week_starts[wk])
            # Same fail-LOUD rule as _prior_season_context: a None payload is a
            # failed fetch, and writing this week's rows anyway would blanket-
            # overwrite previously-good snapshots with NULL efficiency columns.
            adv_p = _get("/stats/season/advanced", year=season,
                         startWeek=1, endWeek=wk - 1)
            elo_p = _get("/ratings/elo", year=season, week=wk)
            if adv_p is None or elo_p is None:
                raise RuntimeError(
                    f"CFBD weekly stats fetch failed for {season} week {wk} "
                    f"(adv={'ok' if adv_p is not None else 'FAILED'}, "
                    f"elo={'ok' if elo_p is not None else 'FAILED'}) — "
                    f"aborting this season's snapshot build rather than "
                    f"poisoning it with NULL overwrites.")
            adv = parse_advanced_stats(adv_p)
            elo = parse_ratings(elo_p, "elo")
            # Filter on DATE, not week number. CFBD restarts week numbering
            # for the postseason -- every bowl/playoff game is
            # season_type='postseason', week=1 -- so `week < wk` admitted the
            # ENTIRE postseason into every in-season snapshot from week 2
            # onward. Audited 2026-08-25: Ohio State's 2024-09-04 snapshot
            # reported games_played=5 (their Aug 31 opener plus four playoff
            # games played that December and January), and 32.7% of all
            # snapshots across 2014-2025 carried this look-ahead. A date cut
            # enforces the leakage contract directly and cannot be broken by
            # week-numbering semantics.
            local = _local_aggregates(_completed_before(log_rows, as_of))
            for team in set(local) | set(adv) | set(prior):
                lp = local.get(team, {})
                rows.append(_stat_row(
                    team, season, as_of, int(lp.get("games_played") or 0),
                    prior.get(team, {}), adv.get(team, {}), lp, elo,
                    teams_meta.get(team, {}), prior_local.get(team, {})))

        if rows:
            conn.executemany(_STAT_UPSERT, _norm(rows, _STAT_COLS))
            conn.commit()
        logger.info(f"NCAAF team stats {season}: {len(rows)} snapshot row(s) "
                    f"across {len(week_starts)} week(s)")
        return len(rows)
    finally:
        if own:
            conn.close()


def _completed_before(log_rows: list[dict], as_of: str) -> list[dict]:
    """
    Game-log rows for games completed strictly BEFORE `as_of`.

    Filters on DATE, never on week number. CFBD restarts week numbering for the
    postseason -- every bowl and playoff game is season_type='postseason',
    week=1 -- so the previous `week < wk` filter admitted the ENTIRE postseason
    into every in-season snapshot from week 2 onward.

    Audited 2026-08-25: Ohio State's 2024-09-04 snapshot reported
    games_played=5 (their Aug 31 opener plus four playoff games from that
    December and January), and 32.7% of all snapshots across 2014-2025 carried
    look-ahead of this kind. A date cut enforces the leakage contract directly
    and cannot be broken by week-numbering semantics.

    Verify with: python -m scripts.ncaaf_search.audit_snapshots
    """
    out = []
    for r in log_rows:
        d = r.get("game_date")
        if d and str(d)[:10] < as_of:
            out.append(r)
    return out


def _day_before(date_str: str) -> str:
    try:
        return (datetime.strptime(date_str[:10], "%Y-%m-%d")
                - timedelta(days=1)).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return date_str[:10]


# ══════════════════════════════════════════════════════════════════════════════
# Results (pre-settlement) + Odds API name resolution + orchestration
# ══════════════════════════════════════════════════════════════════════════════

def ingest_ncaaf_results_for_date(run_date: str | None = None,
                                  heal_days: int = 10, conn=None) -> int:
    """
    Fill final scores so settlement has something to grade. Runs BEFORE settle.

    Self-healing (the UFC csv-loader lesson): re-pulls any NCAAF game inside the
    heal window that still has no score, so a missed Saturday backfills itself
    instead of stranding picks forever.
    """
    own = conn is None
    conn = conn or get_connection()
    try:
        run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lo = (datetime.strptime(run_date, "%Y-%m-%d")
              - timedelta(days=heal_days)).strftime("%Y-%m-%d")
        seasons = [int(r[0]) for r in conn.execute("""
            SELECT DISTINCT season FROM games
            WHERE sport = %(s)s AND game_date BETWEEN %(lo)s AND %(hi)s
              AND home_score IS NULL
        """, {"s": SPORT, "lo": lo, "hi": run_date}).fetchall()]
        if not seasons:
            logger.info(f"NCAAF results: nothing pending in {lo}..{run_date}")
            return 0

        total = 0
        for season in seasons:
            for stype in _SEASON_TYPES:
                rows = [g for g in parse_games(_get("/games", year=season, seasonType=stype))
                        if g["home_score"] is not None and lo <= g["game_date"] <= run_date]
                if rows:
                    conn.executemany(_GAME_UPSERT, _norm(rows, _GAME_FIELDS))
                    conn.commit()
                    total += len(rows)
        logger.info(f"NCAAF results {lo}..{run_date}: {total} final(s)")
        return total
    finally:
        if own:
            conn.close()


_SCHOOL_CACHE: list[dict] | None = None


def _load_schools(conn=None) -> list[dict]:
    global _SCHOOL_CACHE
    if _SCHOOL_CACHE is not None:
        return _SCHOOL_CACHE
    own = conn is None
    conn = conn or get_connection()
    try:
        _SCHOOL_CACHE = [
            {"school": r[0], "mascot": r[1],
             "alt": [a for a in (r[2] or "").split("|") if a]}
            for r in conn.execute(
                "SELECT school, mascot, alt_names FROM ncaaf_teams").fetchall()
        ]
    except Exception as exc:                            # noqa: BLE001
        logger.warning(f"ncaaf_teams unavailable ({exc}) — name resolution is identity-only")
        _SCHOOL_CACHE = []
    finally:
        if own:
            conn.close()
    return _SCHOOL_CACHE


def reset_school_cache() -> None:
    """Drop the cached school list (call after re-ingesting ncaaf_teams)."""
    global _SCHOOL_CACHE
    _SCHOOL_CACHE = None


def _fold(v: str) -> str:
    """Case-, accent- and punctuation-insensitive comparison key."""
    import unicodedata
    v = unicodedata.normalize("NFD", (v or "").strip().lower())
    return "".join(ch for ch in v if ch.isalnum() or ch == " ").replace("  ", " ")


def resolve_odds_api_school(name: str, conn=None) -> str:
    """
    The Odds API team name → CFBD canonical school name.

    The Odds API lists NCAAF teams with the mascot appended ("Ohio State
    Buckeyes"), so this strips it by matching against ncaaf_teams. Resolution
    order: explicit config override → exact school → "school mascot" → longest
    school that prefixes the input → alt name → the input unchanged (warned).

    Identity fallback is deliberate: an unresolved name yields a game_id that
    simply won't match a stats row, so the scorer skips that game — far safer
    than silently attaching odds to the wrong team.
    """
    if not name:
        return name
    override = (config.NCAAF_ODDS_API_MAP or {}).get(name)
    if override:
        return override

    schools = _load_schools(conn)
    if not schools:
        return name

    # All comparisons are accent- and punctuation-FOLDED. The Odds API writes
    # "San Jose State" and "Hawaii"; CFBD's canonical spellings are
    # "San José State" and "Hawai'i", so plain .lower() comparison missed both
    # -- and those are FBS teams whose Week-1 game_ids were being built from
    # the raw Odds API string, which CFBD finals could then never match
    # (the UFC duplicate-row disease). Folding squashes case, diacritics and
    # punctuation; the longest-prefix-wins rule below keeps folding safe for
    # the Miami / Miami (OH) style collisions.
    lowered = _fold(name)
    for s in schools:
        if _fold(s["school"]) == lowered:
            return s["school"]
    for s in schools:
        if s["mascot"] and _fold(f"{s['school']} {s['mascot']}") == lowered:
            return s["school"]
    best = None
    best_len = -1
    for s in schools:
        sl = _fold(s["school"])
        if lowered.startswith(sl) and len(sl) > best_len:
            best, best_len = s["school"], len(sl)
    if best:
        return best
    for s in schools:
        if any(_fold(a) == lowered for a in s["alt"]):
            return s["school"]

    logger.warning(f"Unresolved NCAAF school from Odds API: '{name}' — "
                   f"add it to config.NCAAF_ODDS_API_MAP")
    return name


def ingest_ncaaf_season(season: int, conn=None, with_lines: bool = True) -> dict:
    """Full pull for one season: teams → games → box scores → lines → snapshots."""
    own = conn is None
    conn = conn or get_connection()
    try:
        summary = {"teams": ingest_ncaaf_teams(season, conn),
                   "venues": ingest_ncaaf_venues(conn)}
        reset_school_cache()
        n_games, id_map, games_by_id = ingest_ncaaf_games(season, conn)
        summary["games"] = n_games
        summary["game_log"] = ingest_ncaaf_game_log(season, id_map, games_by_id, conn)
        summary["qb_log"] = ingest_ncaaf_qb_log(season, id_map, games_by_id, conn)
        if with_lines:
            summary["lines"] = ingest_ncaaf_lines(season, conn)
        summary["team_stats"] = ingest_ncaaf_team_stats(season, conn)
        return summary
    finally:
        if own:
            conn.close()


def backfill_ncaaf(start_year: int, end_year: int, with_lines: bool = True) -> dict:
    """
    Paced, resumable, idempotent multi-season backfill.

    Each season runs on its OWN connection and its own try/except: a 12-season
    paced pull holds a connection long enough for Supabase to drop it (the v8
    retrain lesson), and one season's failure must not silently abandon the
    rest — that is exactly how 2016-2025 ended up with venue_id NULL while
    2014-2015 had it. Failures are collected and re-raised as a summary at the
    END so the run still goes red, but every healthy season lands first.
    """
    totals: dict = {}
    failed: list[str] = []
    for season in range(start_year, end_year + 1):
        logger.info(f"── NCAAF backfill {season} ──")
        conn = get_connection()
        try:
            for k, v in ingest_ncaaf_season(season, conn, with_lines).items():
                totals[k] = totals.get(k, 0) + v
        except Exception as exc:                        # noqa: BLE001
            logger.error(f"NCAAF backfill {season} failed: {exc}")
            failed.append(f"{season}: {exc}")
        finally:
            conn.close()
    logger.success(f"NCAAF backfill {start_year}-{end_year}: {totals}")
    if failed:
        raise RuntimeError(
            f"NCAAF backfill: {len(failed)} season(s) failed — "
            + "; ".join(failed))
    return totals



def _schedule_maps(season: int) -> tuple[dict, dict]:
    """
    (id_map, games_by_id) for a season, WITHOUT writing anything.

    CFBD's numeric game id is transient — parse_games exposes it as `_cfbd_id`
    and it is never persisted — so any box-score pull has to rebuild the map
    from a fresh /games call. Two API calls, and it guarantees the ids line up
    with what the games table already holds.
    """
    parsed: list[dict] = []
    for stype in _SEASON_TYPES:
        payload = _get("/games", year=season, seasonType=stype)
        for row in parse_games(payload):
            row.setdefault("_season_type", stype)
            parsed.append(row)
    keep = [g for g in parsed
            if "fbs" in {str(g.get("_home_classification") or "fbs").lower(),
                         str(g.get("_away_classification") or "fbs").lower()}]
    id_map = {g["_cfbd_id"]: g["game_id"]
              for g in keep if g.get("_cfbd_id") is not None}
    games_by_id = {
        g["game_id"]: {"season": g["season"], "week": g["week"],
                       "season_type": g.get("_season_type"),
                       "game_date": g["game_date"]}
        for g in keep
    }
    return id_map, games_by_id


def backfill_ncaaf_qb(start_year: int, end_year: int) -> int:
    """
    QB box scores only, for seasons already ingested.

    Separate from the full backfill so the QB layer can be added to an existing
    database without re-pulling lines and snapshots (~17 API calls per season
    instead of ~50).
    """
    total = 0
    conn = get_connection()
    try:
        for season in range(start_year, end_year + 1):
            id_map, games_by_id = _schedule_maps(season)
            if not id_map:
                logger.warning(f"NCAAF QB backfill {season}: no games — skipping")
                continue
            total += ingest_ncaaf_qb_log(season, id_map, games_by_id, conn)
    finally:
        conn.close()
    logger.success(f"NCAAF QB backfill {start_year}-{end_year}: {total} row(s)")
    return total


def refresh_ncaaf_games(start_year: int, end_year: int) -> int:
    """
    Re-pull ONLY the schedule (/games) for a season range — 2 API calls per
    season. This is the cheap repair for games metadata (venue_id, week,
    neutral_site, conference_game) without re-fetching box scores, lines, or
    stat snapshots: the upsert COALESCEs the metadata in without touching
    anything already settled. Venues refresh first so every venue_id points at
    a real row.
    """
    ingest_ncaaf_venues()
    total = 0
    failed: list[str] = []
    for season in range(start_year, end_year + 1):
        conn = get_connection()
        try:
            n, _, _ = ingest_ncaaf_games(season, conn)
            total += n
        except Exception as exc:                        # noqa: BLE001
            logger.error(f"NCAAF games refresh {season} failed: {exc}")
            failed.append(f"{season}: {exc}")
        finally:
            conn.close()
    logger.success(f"NCAAF games refresh {start_year}-{end_year}: {total} game(s)")
    if failed:
        raise RuntimeError(
            f"NCAAF games refresh: {len(failed)} season(s) failed — "
            + "; ".join(failed))
    return total


def refresh_ncaaf_stats(start_year: int, end_year: int) -> int:
    """
    Rebuild ONLY the ncaaf_team_stats snapshots for a season range (~35 API
    calls per season: prior context + per-week advanced/elo). The repair for
    snapshot poisoning — no games/box-scores/lines re-fetch.
    """
    total = 0
    failed: list[str] = []
    for season in range(start_year, end_year + 1):
        conn = get_connection()
        try:
            total += ingest_ncaaf_team_stats(season, conn)
        except Exception as exc:                        # noqa: BLE001
            logger.error(f"NCAAF stats refresh {season} failed: {exc}")
            failed.append(f"{season}: {exc}")
        finally:
            conn.close()
    logger.success(f"NCAAF stats refresh {start_year}-{end_year}: {total} row(s)")
    if failed:
        raise RuntimeError(
            f"NCAAF stats refresh: {len(failed)} season(s) failed — "
            + "; ".join(failed))
    return total


def backfill_ncaaf_lines(start_year: int, end_year: int) -> int:
    conn = get_connection()
    total = 0
    try:
        for season in range(start_year, end_year + 1):
            total += ingest_ncaaf_lines(season, conn)
    finally:
        conn.close()
    logger.success(f"NCAAF lines backfill {start_year}-{end_year}: {total} row(s)")
    return total


def run_ncaaf_stats_ingestor(season: int | None = None) -> dict:
    """
    In-season weekly refresh. Off-season the schedule pull returns nothing and
    every step is a clean no-op — that IS the off-season gate.
    """
    season = season or ncaaf_season_for_date(
        datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    return ingest_ncaaf_season(season, with_lines=False)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="CollegeFootballData.com → NCAAF tables")
    ap.add_argument("--backfill", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--backfill-lines", nargs=2, type=int, metavar=("START", "END"))
    ap.add_argument("--season", type=int, help="Full pull for one season")
    ap.add_argument("--venues", action="store_true",
                    help="Refresh ncaaf_venues only (season-independent)")
    ap.add_argument("--refresh-stats", nargs=2, type=int, metavar=("START", "END"),
                    help="Rebuild only the ncaaf_team_stats snapshots "
                         "(~35 API calls per season)")
    ap.add_argument("--refresh-games", nargs=2, type=int, metavar=("START", "END"),
                    help="Re-pull only the schedule (venue_id/week/neutral/"
                         "conference metadata) — 2 API calls per season")
    ap.add_argument("--results", nargs="?", const="", metavar="YYYY-MM-DD",
                    help="Fill final scores (pre-settlement)")
    ap.add_argument("--backfill-qb", nargs=2, type=int, metavar=("START", "END"),
                    help="QB box scores only for already-ingested seasons "
                         "(~15 API calls per season)")
    ap.add_argument("--no-lines", action="store_true")
    args = ap.parse_args()

    if args.venues:
        ingest_ncaaf_venues()
    elif args.backfill:
        backfill_ncaaf(args.backfill[0], args.backfill[1], not args.no_lines)
    elif args.backfill_qb:
        backfill_ncaaf_qb(args.backfill_qb[0], args.backfill_qb[1])
    elif args.backfill_lines:
        backfill_ncaaf_lines(args.backfill_lines[0], args.backfill_lines[1])
    elif args.refresh_games:
        refresh_ncaaf_games(args.refresh_games[0], args.refresh_games[1])
    elif args.refresh_stats:
        refresh_ncaaf_stats(args.refresh_stats[0], args.refresh_stats[1])
    elif args.season:
        logger.success(ingest_ncaaf_season(args.season, with_lines=not args.no_lines))
    elif args.results is not None:
        ingest_ncaaf_results_for_date(args.results or None)
    else:
        logger.success(run_ncaaf_stats_ingestor())
