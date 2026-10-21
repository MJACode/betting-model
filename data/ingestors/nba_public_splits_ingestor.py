"""
nba_public_splits_ingestor.py -- NBA public betting splits (% of tickets, % of
money per side, moneyline / spread / total) from Action Network's free
scoreboard JSON, into `nba_public_splits`.

Two capture kinds, never mixed, because they answer different questions:

* ``archive_undated`` -- what Action Network serves for a game AFTER it has
  been played: ONE number per side, with no time on it. Pulled for 2020-21 on
  (season labels 2021..). Measured 2026-10-16 (docs/nba_public_splits.md):
  the archive is the split as it stood at or near the start, not at any
  earlier decision time, so it is a CLOSING-split control, not a feature a
  pre-tip model may read hours before tip.
* ``pregame_poll`` -- a snapshot fetched before the listed start, stamped with
  the fetch time (``observed_at``). Forward capture from 2026-27, one row per
  refresh pass, so a pre-tip decision at time T can read the latest row with
  ``observed_at <= T``.

Two endpoints, stored side by side (``endpoint``), because they disagree on a
minority of values and an analysis should see that rather than inherit a
silent choice:

* v1 ``/web/v1/scoreboard/nba?period=game&bookIds=15&date=YYYYMMDD`` --
  consensus splits back to opening night 2020-21, plus an ``inserted`` stamp
  (the last write of the consensus row, which is AFTER the listed start for
  most games, so it is not an observation time; it is kept as evidence).
* v2 ``/web/v2/scoreboard/nba?bookIds=15&date=YYYYMMDD&periods=event`` --
  the endpoint the MLB ingestor uses; splits from 2023-24 on. Serves ``0`` on
  both sides where it has no split, which is MISSING, not 0%.

Why NOT the `public_betting` table: models/scorer.py copies that table's
percentages onto every pick by game id with no sport filter, and
tracking/model_quality.py reads them back. NBA rows there would change what
live NBA picks carry. This table touches no live surface.

No API key; free; no paid calls. Requests carry browser-like headers -- a bare
client is refused (HTTP 403 seen 2026-10-16), the same headers answer 200.

Usage:
    python -m data.ingestors.nba_public_splits_ingestor --backfill \
        --seasons 2021-2026                 # archive, both endpoints
    python -m data.ingestors.nba_public_splits_ingestor --poll   # today, pre-tip
    python -m data.ingestors.nba_public_splits_ingestor --archive-date 2026-10-21
    ... --dry-run                            # fetch + parse + match, no writes
    python -m data.ingestors.nba_public_splits_ingestor --backfill-quality \
        --expect reversed_at_source=72 --expect late_rewrite=1706

Unreliable rows are flagged, not deleted: ``quality`` is 'reversed_at_source'
(the 2022-03-09 slate) or 'late_rewrite' (v1 rewritten long after tip), NULL
otherwise. Read with ``quality IS NULL`` unless the flag is the subject.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date as _date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# ── Constants ─────────────────────────────────────────────────────────────────

TABLE = "nba_public_splits"
SOURCE = "action_network"
CONSENSUS_BOOK = 15            # Action Network's consensus pseudo-book
V1_BASE = "https://api.actionnetwork.com/web/v1/scoreboard/nba"
V2_BASE = "https://api.actionnetwork.com/web/v2/scoreboard/nba"
REQUEST_TIMEOUT = 25
REQUEST_PAUSE_S = 1.0          # politeness between requests on a backfill
WRITE_BATCH = 3000             # rows per commit

_ET = ZoneInfo("America/New_York")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Referer": "https://www.actionnetwork.com/nba/public-betting",
}

ARCHIVE = "archive_undated"
POLL = "pregame_poll"

# ``quality`` -- rows the stored history shows to be unreliable AT THE SOURCE.
# NULL means nothing is known against the row. Measured 2026-10-17
# (docs/nba_public_splits.md, "Rows to leave out"):
#
# * 2022-03-09: Action Network holds home and away the other way round for the
#   whole slate (12 games, 72 v1 rows): UTA at home against POR is stored at
#   +19.5 / +1500, MIN at home against OKC at +15.5 / +700. Every row of the
#   date is flagged, whatever its endpoint.
# * v1 listings whose consensus row was last written more than
#   LATE_REWRITE_MIN minutes after the listed start (297 listings, the twelve
#   above among them): the split was rewritten long after the game, so it is
#   not known to be the split at tip.
#
# One flag per row; a reversed row is flagged reversed even when it is also
# late (all twelve 2022-03-09 listings are).
Q_REVERSED = "reversed_at_source"
Q_LATE = "late_rewrite"
REVERSED_AT_SOURCE_DATES = frozenset({"2022-03-09"})
LATE_REWRITE_MIN = 400.0

# Action Network market name -> our market key (same vocabulary as
# public_betting and the odds tables).
_V2_MARKETS = {"moneyline": "h2h", "spread": "spreads", "total": "totals"}

# v1 flat fields -> (market, side). Each side carries its own line and price.
#   value: the side's line (None for moneyline), odds: the side's price.
_V1_FIELDS = {
    ("h2h", "home"):     {"value": None, "odds": "ml_home",
                          "tickets": "ml_home_public", "money": "ml_home_money"},
    ("h2h", "away"):     {"value": None, "odds": "ml_away",
                          "tickets": "ml_away_public", "money": "ml_away_money"},
    ("spreads", "home"): {"value": "spread_home", "odds": "spread_home_line",
                          "tickets": "spread_home_public", "money": "spread_home_money"},
    ("spreads", "away"): {"value": "spread_away", "odds": "spread_away_line",
                          "tickets": "spread_away_public", "money": "spread_away_money"},
    ("totals", "over"):  {"value": "total", "odds": "over",
                          "tickets": "total_over_public", "money": "total_over_money"},
    ("totals", "under"): {"value": "total", "odds": "under",
                          "tickets": "total_under_public", "money": "total_under_money"},
}

_PAIRS = {"h2h": ("home", "away"), "spreads": ("home", "away"),
          "totals": ("over", "under")}

# Action Network abbreviation spellings that differ from ours. Every abbr seen
# across 2020-21..2025-26 already matches; these are the common alternates.
_ABBR_ALIASES = {"BRK": "BKN", "PHO": "PHX", "NO": "NOP", "NY": "NYK",
                 "GS": "GSW", "SA": "SAS", "UTAH": "UTA", "WSH": "WAS",
                 "CHO": "CHA"}


# ── Pure parsing (unit-tested) ────────────────────────────────────────────────

def an_pct(raw) -> float | None:
    """A 0-100 percentage exactly as served, or None.

    NO fractional rescaling. The MLB ingestor's `_pct` multiplies any value in
    [0, 1] by 100, which turns a real 1% side into 100%. The archive serves
    integers 0-100 (a 1% side exists on a -3500 favourite), so the value is
    taken as-is and anything outside 0..100 is refused.
    """
    if raw is None or isinstance(raw, bool):
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    if not 0.0 <= val <= 100.0:
        return None
    return round(val, 1)


def clean_pair(a: float | None, b: float | None) -> tuple:
    """Validate the two sides of one metric (tickets OR money) of one market.

    Returns (a, b, status), status one of:
      'ok'      -- both present and sum to 100 within 1 point of rounding;
      'missing' -- both absent, or both 0 (v2 serves 0/0 where it has no split);
      'one_side'-- exactly one side present (kept: it is what was served);
      'bad_sum' -- both present but not summing to ~100: both set to None.
    """
    if a is None and b is None:
        return None, None, "missing"
    if a is not None and b is not None:
        if a == 0 and b == 0:
            return None, None, "missing"
        if abs(a + b - 100.0) > 1.0:
            return None, None, "bad_sum"
        return a, b, "ok"
    return a, b, "one_side"


def et_game_date(start_time: str) -> str | None:
    """Action Network's UTC start_time -> the ET calendar date our games use.

    A 7:30pm PT tip is 03:30Z the next day; games.game_date is the ET date.
    """
    if not start_time:
        return None
    try:
        dt = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ET).strftime("%Y-%m-%d")


def team_abbr(team: dict | None, known: set[str]) -> str | None:
    """Our 3-letter id for an Action Network team dict, or None if unknown.

    The AN abbreviation is tried first (it matches ours for every team seen),
    then its full name against config.NBA_ODDS_API_MAP. No fuzzy guessing: an
    unknown team is reported unmatched, never given an invented id.
    """
    if not isinstance(team, dict):
        return None
    abbr = (team.get("abbr") or "").upper()
    abbr = _ABBR_ALIASES.get(abbr, abbr)
    if abbr in known:
        return abbr
    from config import NBA_ODDS_API_MAP
    from data.ingestors.odds_ingestor import _name_key
    for name in (team.get("full_name"), team.get("display_name")):
        if not name:
            continue
        key = _name_key(name)
        hit = next((v for k, v in NBA_ODDS_API_MAP.items() if _name_key(k) == key), None)
        if hit in known:
            return hit
    return None


def _game_meta(game: dict, known: set[str]) -> dict:
    teams = {t.get("id"): t for t in game.get("teams") or [] if isinstance(t, dict)}
    return {
        "an_game_id": game.get("id"),
        "an_start_time": game.get("start_time"),
        "an_game_type": game.get("type"),
        "an_status": game.get("status"),
        "an_season": game.get("season"),   # AN labels by STARTING year; not used
        "game_date": et_game_date(game.get("start_time")),
        "an_home": team_abbr(teams.get(game.get("home_team_id")), known),
        "an_away": team_abbr(teams.get(game.get("away_team_id")), known),
    }


def parse_v2_sides(game: dict, book_id: int = CONSENSUS_BOOK) -> dict:
    """{(market, side): {value, odds, tickets, money}} from a v2 game.

    Only pre-game entries (is_live false). An in-progress game carries both
    pre-game and live entries for the same side; the live ones show 0/0.
    """
    block = (game.get("markets") or {}).get(str(book_id)) or {}
    period = block.get("event") if isinstance(block.get("event"), dict) else block
    out: dict = {}
    for an_key, market in _V2_MARKETS.items():
        for e in (period or {}).get(an_key) or []:
            if not isinstance(e, dict) or e.get("is_live"):
                continue
            side = e.get("side")
            if side not in _PAIRS[market] or (market, side) in out:
                continue
            bi = e.get("bet_info") or {}
            out[(market, side)] = {
                "value": None if market == "h2h" else e.get("value"),
                "odds": e.get("odds"),
                "tickets": an_pct((bi.get("tickets") or {}).get("percent")),
                "money": an_pct((bi.get("money") or {}).get("percent")),
            }
    return out


def v1_consensus_row(game: dict, book_id: int = CONSENSUS_BOOK) -> dict | None:
    for o in game.get("odds") or []:
        if isinstance(o, dict) and o.get("book_id") == book_id and o.get("type") == "game":
            return o
    return None


def parse_v1_sides(game: dict, book_id: int = CONSENSUS_BOOK) -> dict:
    """{(market, side): {value, odds, tickets, money}} from a v1 game's
    consensus odds row (flat field names, see _V1_FIELDS)."""
    o = v1_consensus_row(game, book_id)
    if not o:
        return {}
    out = {}
    for key, f in _V1_FIELDS.items():
        out[key] = {
            "value": o.get(f["value"]) if f["value"] else None,
            "odds": o.get(f["odds"]),
            "tickets": an_pct(o.get(f["tickets"])),
            "money": an_pct(o.get(f["money"])),
        }
    return out


def validate_sides(sides: dict, counts: dict | None = None) -> dict:
    """Apply clean_pair to tickets and money of every market. Mutates a copy."""
    out = {k: dict(v) for k, v in sides.items()}
    for market, (s1, s2) in _PAIRS.items():
        if (market, s1) not in out and (market, s2) not in out:
            continue
        for metric in ("tickets", "money"):
            a = out.get((market, s1), {}).get(metric)
            b = out.get((market, s2), {}).get(metric)
            a2, b2, status = clean_pair(a, b)
            if counts is not None:
                counts[f"{metric}_{status}"] = counts.get(f"{metric}_{status}", 0) + 1
            if (market, s1) in out:
                out[(market, s1)][metric] = a2
            if (market, s2) in out:
                out[(market, s2)][metric] = b2
    return out


def flip_side(market: str, side: str) -> str:
    """Home<->away for team markets; over/under is orientation-free."""
    if market == "totals":
        return side
    return {"home": "away", "away": "home"}[side]


def match_game(index: dict, game_date: str | None, away: str | None,
               home: str | None) -> tuple:
    """(game_id, season, kind). kind: 'exact' | 'swapped' | 'not_found'
    | 'team_unknown'.

    'swapped' = our games row lists the same two teams on the same ET date with
    home and away the other way round (neutral-site games); the caller then
    flips the team-market sides so `side` is always in OUR orientation.
    """
    if not away or not home:
        return None, None, "team_unknown"
    hit = index.get((game_date, away, home))
    if hit:
        return hit[0], hit[1], "exact"
    hit = index.get((game_date, home, away))
    if hit:
        return hit[0], hit[1], "swapped"
    return None, None, "not_found"


def not_started(games: list[dict], now: datetime) -> tuple[list[dict], int]:
    """(games whose LISTED start is still in the future, count already started).

    The forward poll stamps a row with its fetch time and promises it was seen
    before tip; a game at or past its listed start is refused (the table's
    CHECK constraint refuses it too). A start that cannot be parsed counts as
    started -- refusing is the safe side.
    """
    keep, started = [], 0
    for g in games or []:
        try:
            st = datetime.fromisoformat(str(g.get("start_time")).replace("Z", "+00:00"))
        except ValueError:
            started += 1
            continue
        if st.tzinfo is None or now >= st:
            started += 1
            continue
        keep.append(g)
    return keep, started


def keep_for_poll(info: dict) -> bool:
    """Skip Action Network preseason games -- no games row, no model bets them
    -- but only when they match nothing of ours: AN labelled the rescheduled
    regular-season GSW @ UTA of 2024-02-15 (postponed from 2024-01-17) 'pre'."""
    return info.get("an_game_type") != "pre" or info.get("game_id") is not None


def inserted_minus_start_min(inserted: str | None, start_time: str | None):
    """Minutes from the listed start to v1's `inserted` stamp. Positive = the
    consensus row was last written AFTER the listed start."""
    try:
        a = datetime.fromisoformat(str(inserted).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(start_time).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return round((a - b).total_seconds() / 60.0, 1)


def quality_flag(game_date: str | None, inserted_lag_min) -> str | None:
    """The row's ``quality`` value: 'reversed_at_source', 'late_rewrite' or None.

    `inserted_lag_min` is inserted_minus_start_min (v1 only; None on v2 and on
    every poll row). The stored-row backfill (quality_backfill_statements)
    applies this same rule in SQL; a test holds the two together.
    """
    if game_date in REVERSED_AT_SOURCE_DATES:
        return Q_REVERSED
    if inserted_lag_min is not None and float(inserted_lag_min) > LATE_REWRITE_MIN:
        return Q_LATE
    return None


def build_rows(game: dict, endpoint: str, index: dict, known: set[str], *,
               capture_kind: str, fetched_at: str, observed_at: str | None = None,
               counts: dict | None = None) -> tuple[list[dict], dict]:
    """Rows for one Action Network game from one endpoint, plus its match info.

    A row is written only when at least one of tickets/money survived
    validation: a line and price with no split is not what this table is for.
    """
    meta = _game_meta(game, known)
    if endpoint == "v1":
        sides = parse_v1_sides(game)
        o = v1_consensus_row(game) or {}
        src_inserted = o.get("inserted")
        num_bets = o.get("num_bets")
    else:
        sides = parse_v2_sides(game)
        src_inserted = None
        num_bets = game.get("num_bets")
    sides = validate_sides(sides, counts)
    game_id, season, kind = match_game(index, meta["game_date"],
                                       meta["an_away"], meta["an_home"])
    if kind == "swapped":
        home, away = meta["an_away"], meta["an_home"]
    else:
        home, away = meta["an_home"], meta["an_away"]
    snapshot_key = "archive" if capture_kind == ARCHIVE else str(observed_at)
    lag = inserted_minus_start_min(src_inserted, meta["an_start_time"])
    quality = quality_flag(meta["game_date"], lag)
    rows = []
    for (market, side), v in sides.items():
        if v.get("tickets") is None and v.get("money") is None:
            continue
        our_side = flip_side(market, side) if kind == "swapped" else side
        rows.append({
            "an_game_id": meta["an_game_id"],
            "game_id": game_id,
            "season": season,
            "game_date": meta["game_date"],
            "an_start_time": meta["an_start_time"],
            "an_game_type": meta["an_game_type"],
            "an_status": meta["an_status"],
            "home_team": home,
            "away_team": away,
            "match_kind": kind,
            "market": market,
            "side": our_side,
            "line_value": v.get("value"),
            "odds": v.get("odds"),
            "tickets_pct": v.get("tickets"),
            "money_pct": v.get("money"),
            "num_bets": num_bets,
            "endpoint": endpoint,
            "book_id": CONSENSUS_BOOK,
            "capture_kind": capture_kind,
            "observed_at": observed_at,
            "source_inserted_at": src_inserted,
            "inserted_minus_start_min": lag,
            "snapshot_key": snapshot_key,
            "fetched_at": fetched_at,
            "source": SOURCE,
            "quality": quality,
        })
    return rows, {**meta, "game_id": game_id, "season": season, "match_kind": kind,
                  "n_rows": len(rows)}


# ── HTTP ──────────────────────────────────────────────────────────────────────

def fetch_scoreboard(endpoint: str, day: str, cache_dir: Path | None = None) -> dict:
    """The raw scoreboard JSON for one ET date (YYYY-MM-DD).

    `cache_dir` keeps each response as a temp download so a re-run does not
    refetch; it is a cache, the database is the record.
    """
    import requests

    ymd = day.replace("-", "")
    cache = cache_dir / f"{endpoint}_{ymd}.json" if cache_dir else None
    if cache and cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    if endpoint == "v1":
        url, params = V1_BASE, {"period": "game", "bookIds": CONSENSUS_BOOK, "date": ymd}
    else:
        url, params = V2_BASE, {"bookIds": CONSENSUS_BOOK, "date": ymd, "periods": "event"}
    resp = requests.get(url, params=params, headers=_HEADERS, timeout=REQUEST_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    if cache:
        cache.write_text(json.dumps(data), encoding="utf-8")
    return data


# ── DB ────────────────────────────────────────────────────────────────────────

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS nba_public_splits (
    split_id                 BIGSERIAL PRIMARY KEY,
    an_game_id               BIGINT  NOT NULL,
    game_id                  TEXT,
    season                   INTEGER,
    game_date                TEXT    NOT NULL,
    an_start_time            TIMESTAMPTZ,
    an_game_type             TEXT,
    an_status                TEXT,
    home_team                TEXT,
    away_team                TEXT,
    match_kind               TEXT    NOT NULL,
    market                   TEXT    NOT NULL,
    side                     TEXT    NOT NULL,
    line_value               NUMERIC,
    odds                     INTEGER,
    tickets_pct              NUMERIC,
    money_pct                NUMERIC,
    num_bets                 INTEGER,
    endpoint                 TEXT    NOT NULL,
    book_id                  INTEGER NOT NULL,
    capture_kind             TEXT    NOT NULL,
    observed_at              TIMESTAMPTZ,
    source_inserted_at       TIMESTAMPTZ,
    inserted_minus_start_min NUMERIC,
    snapshot_key             TEXT    NOT NULL,
    fetched_at               TIMESTAMPTZ NOT NULL,
    source                   TEXT    NOT NULL,
    quality                  TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT {TABLE}_uniq UNIQUE
        (an_game_id, market, side, endpoint, capture_kind, snapshot_key),
    CONSTRAINT {TABLE}_capture_chk CHECK (
        (capture_kind = '{ARCHIVE}' AND observed_at IS NULL AND snapshot_key = 'archive')
        OR (capture_kind = '{POLL}' AND observed_at IS NOT NULL
            AND observed_at < an_start_time))
)
"""

# The table was created (2026-10-16) before `quality` existed; CREATE TABLE IF
# NOT EXISTS does not add a column to an existing table, this does.
_ADD_QUALITY_SQL = f"ALTER TABLE {TABLE} ADD COLUMN IF NOT EXISTS quality TEXT"

_INDEXES = {
    f"{TABLE}_game_idx":
        f"CREATE INDEX IF NOT EXISTS {TABLE}_game_idx ON {TABLE} (game_id)",
    f"{TABLE}_season_idx":
        f"CREATE INDEX IF NOT EXISTS {TABLE}_season_idx ON {TABLE} (season, endpoint)",
    f"{TABLE}_date_idx":
        f"CREATE INDEX IF NOT EXISTS {TABLE}_date_idx "
        f"ON {TABLE} (game_date, capture_kind, endpoint)",
}

ROW_COLS = (
    "an_game_id", "game_id", "season", "game_date", "an_start_time",
    "an_game_type", "an_status", "home_team", "away_team", "match_kind",
    "market", "side", "line_value", "odds", "tickets_pct", "money_pct",
    "num_bets", "endpoint", "book_id", "capture_kind", "observed_at",
    "source_inserted_at", "inserted_minus_start_min", "snapshot_key",
    "fetched_at", "source", "quality",
)

_INSERT_SQL = f"""
INSERT INTO {TABLE} (
    an_game_id, game_id, season, game_date, an_start_time, an_game_type,
    an_status, home_team, away_team, match_kind, market, side, line_value,
    odds, tickets_pct, money_pct, num_bets, endpoint, book_id, capture_kind,
    observed_at, source_inserted_at, inserted_minus_start_min, snapshot_key,
    fetched_at, source, quality
) VALUES (
    %(an_game_id)s, %(game_id)s, %(season)s, %(game_date)s, %(an_start_time)s,
    %(an_game_type)s, %(an_status)s, %(home_team)s, %(away_team)s,
    %(match_kind)s, %(market)s, %(side)s, %(line_value)s, %(odds)s,
    %(tickets_pct)s, %(money_pct)s, %(num_bets)s, %(endpoint)s, %(book_id)s,
    %(capture_kind)s, %(observed_at)s, %(source_inserted_at)s,
    %(inserted_minus_start_min)s, %(snapshot_key)s, %(fetched_at)s, %(source)s,
    %(quality)s
)
ON CONFLICT (an_game_id, market, side, endpoint, capture_kind, snapshot_key)
DO NOTHING
"""


def ensure_table(conn) -> None:
    """Create the table on demand, closed to the app roles in the same breath.

    DDL only when the catalog says it is needed (data/ddl_guard.py): the
    forward step runs on every refresh pass, and a no-op CREATE still fires
    PostgREST's schema reload. The table is named literally so
    tests/test_anon_readable.py can see the guard and the lock-down.
    """
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, "nba_public_splits", columns=ROW_COLS,
                             indexes=tuple(_INDEXES), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(_CREATE_SQL)
        conn.execute(_ADD_QUALITY_SQL)
        lock_down(conn, "nba_public_splits")
        for stmt in _INDEXES.values():
            conn.execute(stmt)
    conn.commit()


def load_games_index(conn, seasons: tuple[int, int]) -> tuple[dict, dict]:
    """(index, dates): index[(game_date, away, home)] = (game_id, season);
    dates[season] = sorted distinct game dates."""
    rows = conn.execute(
        "SELECT game_id, season, game_date, away_team, home_team FROM games "
        "WHERE sport = 'NBA' AND season BETWEEN %s AND %s",
        (seasons[0], seasons[1]),
    ).fetchall()
    index, dates = {}, {}
    for gid, season, gdate, away, home in rows:
        index[(gdate, away, home)] = (gid, season)
        dates.setdefault(season, set()).add(gdate)
    return index, {s: sorted(d) for s, d in dates.items()}


def stored_archive_dates(conn, endpoint: str, day: str | None = None) -> set[str]:
    sql = (f"SELECT DISTINCT game_date FROM {TABLE} "
           f"WHERE endpoint = %s AND capture_kind = %s")
    params: tuple = (endpoint, ARCHIVE)
    if day:
        sql += " AND game_date = %s"
        params += (day,)
    return {r[0] for r in conn.execute(sql, params).fetchall()}


def stored_archive_games(conn, endpoint: str, day: str) -> set[int]:
    """Action Network game ids already archived for one endpoint on one ET date.

    The forward archive decides per GAME, not per date: a 10pm ET tip is
    still in play at the 00:17 ET pass that first archives its date, and a
    per-date check would never come back for it.
    """
    return {r[0] for r in conn.execute(
        f"SELECT DISTINCT an_game_id FROM {TABLE} "
        f"WHERE endpoint = %s AND capture_kind = %s AND game_date = %s",
        (endpoint, ARCHIVE, day)).fetchall()}


def archive_ready(games: list[dict] | None, stored_ids: set) -> list[dict]:
    """The games of one scoreboard to archive now: finished (Action Network
    status 'complete') and not already stored for this endpoint. A finished
    game that built no rows (no split served) stays unstored and is looked at
    again on the next pass."""
    return [g for g in games or []
            if (g.get("status") or "") == "complete" and g.get("id") not in stored_ids]


def quality_backfill_statements(ph: str = "%s") -> list[tuple[str, str, tuple]]:
    """(flag, UPDATE, params) that set `quality` on STORED rows by the same
    rule quality_flag() applies to new ones, reversed first so a row that is
    both carries the reversed flag. Both only touch rows not already carrying
    their flag, so a second run updates nothing. `ph` is the placeholder
    ('?' lets the test run them on SQLite)."""
    dates = tuple(sorted(REVERSED_AT_SOURCE_DATES))
    marks = ", ".join([ph] * len(dates))
    return [
        (Q_REVERSED,
         f"UPDATE {TABLE} SET quality = {ph} WHERE game_date IN ({marks}) "
         f"AND (quality IS NULL OR quality <> {ph})",
         (Q_REVERSED, *dates, Q_REVERSED)),
        (Q_LATE,
         f"UPDATE {TABLE} SET quality = {ph} WHERE quality IS NULL "
         f"AND inserted_minus_start_min > {ph}",
         (Q_LATE, LATE_REWRITE_MIN)),
    ]


def backfill_quality(conn, expect: dict | None = None) -> dict:
    """Flag the stored rows in ONE transaction: add the column if the catalog
    lacks it, run both UPDATEs, commit once. With `expect` ({flag: rows}), any
    count that differs rolls the whole write back and raises -- a count that
    does not match what was measured beforehand is a question, not a result.
    Returns {flag: rows updated}."""
    from data.ddl_guard import schema_is_current
    try:
        if not schema_is_current(conn, TABLE, columns=("quality",)):
            conn.execute(_ADD_QUALITY_SQL)
        counts = {flag: conn.execute(sql, params).rowcount
                  for flag, sql, params in quality_backfill_statements()}
        if expect is not None and counts != expect:
            raise RuntimeError(f"quality backfill: updated {counts}, expected "
                               f"{expect}; rolled back, nothing written")
    except Exception:
        conn.rollback()
        raise
    conn.commit()
    return counts


def write_rows(conn, rows: list[dict]) -> int:
    """Insert one group of rows in ONE transaction. The backfill passes whole
    dates (so its skip-a-stored-date rule can never meet half a date); the
    forward archive passes whole games, so a date it is still filling in holds
    some games and not others -- a later --backfill over that date would skip
    it. ON CONFLICT DO NOTHING makes a re-run write nothing already stored.
    Returns rows attempted."""
    if not rows:
        return 0
    for i in range(0, len(rows), WRITE_BATCH):
        conn.executemany(_INSERT_SQL, rows[i:i + WRITE_BATCH])
    conn.commit()
    return len(rows)


def active_queries(conn) -> int:
    return conn.execute(
        "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
    ).fetchone()[0]


# ── Runs ──────────────────────────────────────────────────────────────────────

def _known_abbrs() -> set[str]:
    from config import NBA_ODDS_API_MAP
    return set(NBA_ODDS_API_MAP.values())


def run_backfill(seasons: tuple[int, int], endpoints=("v1", "v2"),
                 cache_dir: Path | None = None, dry_run: bool = False,
                 max_active: int = 25) -> dict:
    """Archive every ET date that holds an NBA game in `games` for the seasons.

    Resumable: a date already stored for an endpoint is skipped (each date is
    committed in one transaction, so it is all there or not at all).
    """
    from data.db import get_connection

    conn = get_connection()
    summary = {"dates": 0, "skipped_dates": 0, "rows": 0, "games": 0,
               "match": {}, "unmatched": [], "pair_status": {},
               "fetch_errors": []}
    try:
        if not dry_run:
            ensure_table(conn)
        index, dates = load_games_index(conn, seasons)
        known = _known_abbrs()
        for endpoint in endpoints:
            done = set() if dry_run else stored_archive_dates(conn, endpoint)
            pending: list[dict] = []
            for season in sorted(dates):
                for day in dates[season]:
                    if day in done:
                        summary["skipped_dates"] += 1
                        continue
                    cached = bool(cache_dir and (
                        cache_dir / f"{endpoint}_{day.replace('-', '')}.json").exists())
                    try:
                        data = fetch_scoreboard(endpoint, day, cache_dir)
                    except Exception as exc:                      # noqa: BLE001
                        summary["fetch_errors"].append((endpoint, day, str(exc)[:200]))
                        logger.warning(f"{endpoint} {day}: fetch failed: {exc}")
                        time.sleep(REQUEST_PAUSE_S * 5)
                        continue
                    if not cached:
                        time.sleep(REQUEST_PAUSE_S)
                    fetched_at = datetime.now(timezone.utc).isoformat()
                    summary["dates"] += 1
                    for game in data.get("games") or []:
                        rows, info = build_rows(
                            game, endpoint, index, known, capture_kind=ARCHIVE,
                            fetched_at=fetched_at, counts=summary["pair_status"])
                        summary["games"] += 1
                        key = f"{endpoint}:{info['match_kind']}:{info['an_game_type']}"
                        summary["match"][key] = summary["match"].get(key, 0) + 1
                        if info["match_kind"] != "exact" and len(summary["unmatched"]) < 400:
                            summary["unmatched"].append(
                                (endpoint, day, info["an_game_id"], info["an_game_type"],
                                 info["an_away"], info["an_home"], info["match_kind"]))
                        pending.extend(rows)
                    if len(pending) >= WRITE_BATCH and not dry_run:
                        if active_queries(conn) > max_active:
                            logger.warning("database busy; pausing 30s before writing")
                            time.sleep(30)
                        summary["rows"] += write_rows(conn, pending)
                        pending = []
                logger.info(f"{endpoint} season {season}: done "
                            f"({summary['dates']} dates fetched so far)")
            if pending and not dry_run:
                summary["rows"] += write_rows(conn, pending)
            elif pending:
                summary["rows"] += len(pending)
    finally:
        conn.close()
    return summary


def run_poll(target_date: str | None = None, dry_run: bool = False) -> dict:
    """Forward capture: today's (ET) games that have NOT reached their listed
    start, stamped with the fetch time. One row per side per pass."""
    from data.db import get_connection

    now = datetime.now(timezone.utc)
    day = target_date or now.astimezone(_ET).strftime("%Y-%m-%d")
    try:
        data = fetch_scoreboard("v2", day)
    except Exception as exc:                                     # noqa: BLE001
        logger.warning(f"NBA public splits poll: fetch failed (non-fatal): {exc}")
        return {"date": day, "rows": 0, "error": str(exc)}
    conn = get_connection()
    try:
        if not dry_run:
            ensure_table(conn)
        y = int(day[:4])
        index, _ = load_games_index(conn, (y, y + 1))
        known = _known_abbrs()
        observed_at = now.isoformat()
        all_games = data.get("games") or []
        upcoming, started = not_started(all_games, now)
        games = len(all_games)
        rows, preseason = [], 0
        for game in upcoming:
            r, info = build_rows(game, "v2", index, known, capture_kind=POLL,
                                 fetched_at=observed_at, observed_at=observed_at)
            if not keep_for_poll(info):
                preseason += 1
                continue
            rows.extend(r)
        n = len(rows) if dry_run else write_rows(conn, rows)
    finally:
        conn.close()
    logger.info(f"NBA public splits poll {day}: {games} games, {started} already "
                f"started, {preseason} preseason skipped, {n} rows")
    return {"date": day, "games": games, "already_started": started,
            "preseason_skipped": preseason, "rows": n}


def run_archive_date(day: str, dry_run: bool = False) -> dict:
    """Archive one date's finished games from both endpoints (the forward job
    runs this for yesterday, so the 2026-27 archive sits beside its pre-tip
    polls).

    Decided per GAME: each pass archives every finished game not already
    stored for that endpoint. The first pass after midnight ET (00:17) finds a
    10pm ET tip still in play; the next pass (01:17) archives it. A per-date
    check -- skip once any row of the date is stored -- never came back for
    it. The 2026-27 schedule has 182 regular-season tips at 10pm ET or later,
    every one on a date with an earlier game (nba_schedule, read 2026-10-17).
    The cost is one free
    scoreboard GET per endpoint per pass for yesterday (v1 was already
    refetched every pass: it carried NBA splits through 2026-04-12 and none on
    2026-04-20, 05-15 or 06-10, so it is stored only if it ever returns).
    """
    from data.db import get_connection

    conn = get_connection()
    out = {"date": day, "rows": 0, "already_stored": {}, "not_finished": {}}
    try:
        if not dry_run:
            ensure_table(conn)
        y = int(day[:4])
        index, _ = load_games_index(conn, (y, y + 1))
        known = _known_abbrs()
        fetched_at = datetime.now(timezone.utc).isoformat()
        rows = []
        for endpoint in ("v1", "v2"):
            stored = set() if dry_run else stored_archive_games(conn, endpoint, day)
            try:
                data = fetch_scoreboard(endpoint, day)
            except Exception as exc:                             # noqa: BLE001
                logger.warning(f"{endpoint} {day}: fetch failed (non-fatal): {exc}")
                continue
            games = data.get("games") or []
            ready = archive_ready(games, stored)
            out["already_stored"][endpoint] = sum(g.get("id") in stored for g in games)
            out["not_finished"][endpoint] = sum(
                (g.get("status") or "") != "complete" and g.get("id") not in stored
                for g in games)
            for game in ready:
                r, info = build_rows(game, endpoint, index, known,
                                     capture_kind=ARCHIVE, fetched_at=fetched_at)
                if keep_for_poll(info):
                    rows.extend(r)
        out["rows"] = len(rows) if dry_run else write_rows(conn, rows)
    finally:
        conn.close()
    return out


def run_forward(run_date: str | None = None) -> dict:
    """The refresh-pass entry point: archive yesterday, poll today. Both
    best-effort -- a failure is logged and the pass continues."""
    today = run_date or datetime.now(_ET).strftime("%Y-%m-%d")
    yesterday = (_date.fromisoformat(today) - timedelta(days=1)).isoformat()
    out = {}
    try:
        out["archive"] = run_archive_date(yesterday)
    except Exception as exc:                                     # noqa: BLE001
        logger.warning(f"NBA public splits archive {yesterday} failed: {exc}")
        out["archive"] = {"error": str(exc)}
    try:
        out["poll"] = run_poll(today)
    except Exception as exc:                                     # noqa: BLE001
        logger.warning(f"NBA public splits poll {today} failed: {exc}")
        out["poll"] = {"error": str(exc)}
    return out


# ── CLI ───────────────────────────────────────────────────────────────────────

def _parse_seasons(text: str) -> tuple[int, int]:
    a, _, b = text.partition("-")
    return int(a), int(b or a)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--backfill", action="store_true")
    ap.add_argument("--seasons", default="2021-2026",
                    help="ending-year labels, e.g. 2021-2026")
    ap.add_argument("--endpoints", default="v1,v2")
    ap.add_argument("--cache-dir", help="temp directory for raw responses")
    ap.add_argument("--poll", action="store_true")
    ap.add_argument("--archive-date", metavar="YYYY-MM-DD")
    ap.add_argument("--forward", action="store_true")
    ap.add_argument("--date", metavar="YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--summary-out", help="write the run summary JSON here")
    ap.add_argument("--backfill-quality", action="store_true",
                    help="set `quality` on stored rows (one transaction)")
    ap.add_argument("--expect", action="append", default=[], metavar="FLAG=ROWS",
                    help="with --backfill-quality: roll back unless each count matches")
    args = ap.parse_args()

    if args.backfill_quality:
        from data.db import get_connection
        expect = {k: int(v) for k, _, v in (e.partition("=") for e in args.expect)}
        conn = get_connection()
        try:
            res = backfill_quality(conn, expect or None)
        finally:
            conn.close()
    elif args.backfill:
        cache = Path(args.cache_dir) if args.cache_dir else None
        if cache:
            cache.mkdir(parents=True, exist_ok=True)
        res = run_backfill(_parse_seasons(args.seasons),
                           tuple(e.strip() for e in args.endpoints.split(",") if e.strip()),
                           cache_dir=cache, dry_run=args.dry_run)
    elif args.poll:
        res = run_poll(args.date, dry_run=args.dry_run)
    elif args.archive_date:
        res = run_archive_date(args.archive_date, dry_run=args.dry_run)
    elif args.forward:
        res = run_forward(args.date)
    else:
        ap.error("choose --backfill, --poll, --archive-date, --forward or --backfill-quality")
    text = json.dumps(res, indent=1, default=str)
    if args.summary_out:
        Path(args.summary_out).write_text(text, encoding="utf-8")
    print(text[:6000])
