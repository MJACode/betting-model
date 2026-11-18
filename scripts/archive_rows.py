#!/usr/bin/env python
"""Move rows out of Supabase into the archive: mike's PC, backed up in Storage (#1345).

mike, 2026-11-16: "move all the historical data past a certain point to my
laptop and just keep what was needed in Supabase", and of the exact repeats:
"keep it in the archive on my computer".

WHAT LEAVES SUPABASE (`odds`, `player_prop_odds`), per game that started more
than MIN_AGE_DAYS ago:
  repeat  a row with the same prices and line as the same book's row before it
          for the same proposition and label (an exact duplicate saved again a
          few minutes later). 66.0% of prop rows and 53.8% of game-odds rows,
          measured on the PC copy 2026-11-16 (game odds 47.6% on 11-18).
  old     for games that started more than OLD_DAYS ago, every row but the two
          kept below.
Never moved: each proposition's first row (the opener) and its last pre-game
row at or before the start (the close), per book. Those are what the Teams
board, CLV and the scorer read for a finished game. A proposition is (game,
market, book), plus the player for props, plus the rung for an alternate line.

HOW A ROW LEAVES. Nothing is removed until all of these hold, per game:
  1. The PC copy (betting.duckdb) picks the rows by the rule and writes them to
     a Parquet file under ARCHIVE_ROOT (no egress: the rows are already here).
  2. The file is read back: same count, same fingerprint.
  3. The file is uploaded to Supabase Storage (private bucket BUCKET) and
     downloaded again: same bytes.
  4. In ONE transaction, Postgres picks the rows by the same rule, and its count
     and fingerprint must equal the file's. Only then are exactly those rows
     removed, and the ledger row `archive_batches` is written with them.
A row the copy has not seen (written after the copy) changes Postgres's
fingerprint, so its game is refused and retried after the next nightly copy.

WHEN IT TOUCHES SUPABASE. Step 4 is the only heavy read, and it runs only in
the quiet window (REMOVE_WINDOW_ET, outside the hourly refresh, and only while
the database is not busy). Preparing reads the PC copy alone: no Postgres
check by default (--check adds one). Measured 2026-11-16: 256 MB of shared
buffers and a 60-connection limit (Supabase's two smallest sizes) for a 101 GB
database, so a game's rows come off disk at 650-2,300 rows a second, and the daytime prepare
pass that also checked every game in Postgres, 09:00-13:50 ET, coincided with
178 statement timeouts across the project, 79 of them app reads, against at most 5 an
hour in the 18 hours before and none after it stopped.

THE FINGERPRINT. Per row, md5 of the row's columns as text (numbers as
round(x * 1e6), times as text), first 15 hex digits as an integer, summed over
the rows. Postgres and DuckDB compute it alike: measured 2026-11-16 on 199,991
`picks_log` rows, both gave 115382440917824267217252.

    python scripts/archive_rows.py prepare --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py upload  --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py remove  --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py remove  --table player_prop_odds --rule repeat --pending   # every stored date
    python scripts/archive_rows.py run     --table player_prop_odds --rule repeat --start 2026-03-01 --end 2026-11-12
    python scripts/archive_rows.py reclaim --table player_prop_odds      # see reclaim(): unmeasured
    python scripts/archive_rows.py status

Only (player_prop_odds, repeat) may move today; ALLOWED and REFUSED say why.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ARCHIVE_ROOT = Path(os.environ.get(
    "ARCHIVE_ROOT", r"C:\Users\micha\Documents\betting_local_copies\archive"))
DEFAULT_COPY_DB = r"C:\Users\micha\Documents\betting_local_copies\betting.duckdb"
DEFAULT_ENV = r"C:\Users\micha\documents\betting-model\.env"
BUCKET = "archive"
MIN_AGE_DAYS = 3
OLD_DAYS = 90
RULES = ("repeat", "old")
# What may move today. Every other (table, rule) has a production reader that
# would change what it returns, found by the reader audit of 2026-11-16 (the
# reasons below; detail in docs/data_archive.md, "What reads old rows"). Each
# opens once its reader reads the archive or a kept summary instead.
ALLOWED = {("player_prop_odds", "repeat")}
REFUSED = {
    # The reader audit of 2026-11-18 found more than _ODDS_KEEP holds, among them
    # two in production; the list is in docs/data_archive.md, "What reads old rows".
    ("odds", "repeat"): "the app's line history for past picks (the at-pick price and its "
                        "6-hour limit), the first-half CLV close (a row on the pick's line "
                        "after the pick), the NCAAB spread and moneyline builds (the hour "
                        "before 15:00 UTC), and research scripts that rebuild fetches or "
                        "measure price age read the rows a repeat would move",
    ("odds", "old"): "the Teams board, CLV's same-line close, BYOM, the line charts and "
                     "team_period_results read mid-path rows of old games",
    ("player_prop_odds", "old"): "the line charts, the NHL player prop view and BYOM prop facts read "
                                 "lines that are neither opener nor close",
}
# One game a statement. Measured 2026-11-16 at midday: one game of 45k rows
# took 70 s and one of 340k took 148 s; three such games in one statement ran
# past 300 s.
STATEMENT_TIMEOUT = "300s"
REMOVE_TIMEOUT = "900s"
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
# Removals run from 01:30 to 05:30 ET: after the late games, before the 06:00
# pipeline and its merge gate. Inside it they also stay out of the hourly
# refresh (minutes 15-28, the PC copy's own closed windows) and pause while more
# than MAX_ACTIVE_OTHERS other statements are running.
REMOVE_WINDOW_ET = (dt.time(1, 30), dt.time(5, 30))
MAX_ACTIVE_OTHERS = 6
BUSY_SLEEP_S = 20.0
# `--now` (mike, 2026-11-16: "why cant you just fuckin run it now"): removals at
# any hour, guarded harder. The app's reads give up at 8 s (role
# `authenticated`; `anon` at 3 s, measured in pg_roles), so a removal waits
# while any app read has run APP_READ_LIMIT_S, rests after each game as long as
# the game took (it holds the disk at most half the time), and still stays out
# of the :17 refresh and the 05:40-07:16 morning window.
APP_ROLES = ("authenticator", "authenticated", "anon")
APP_READ_LIMIT_S = 2.0
# A game with more archived rows than this is removed one market a transaction.
# Measured 2026-11-16: 82,694 rows in 10.4 s and 289,143 in 25.3 s, but one
# 408,831-row game took 395 s in the evening and six app reads timed out
# behind it; the guard runs only between transactions.
SPLIT_ROWS = 50_000
REMOVE_LOCK = 1345_0001   # pg advisory lock key: one removal run at a time
# --batch-rows N (game odds, 2026-11-18): 85,666 games hold `odds` rows, most
# of a few hundred, against 1,007 prop games. One game a transaction costs
# about 1.6 s even for 96 rows (the prop removal log of 2026-11-17), which is
# 38 hours for odds. So small games go together, up to N archived rows and
# BATCH_GAMES games a transaction, each game still checked on its own.
BATCH_GAMES = 200

LEDGER_DDL = """
CREATE TABLE IF NOT EXISTS archive_batches (
    table_name    TEXT        NOT NULL,
    rule          TEXT        NOT NULL,
    batch_key     TEXT        NOT NULL,
    game_date     TEXT,
    file_path     TEXT        NOT NULL,
    storage_path  TEXT,
    file_sha256   TEXT,
    rows          BIGINT      NOT NULL,
    checksum      TEXT        NOT NULL,
    prepared_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    stored_at     TIMESTAMPTZ,
    removed_at    TIMESTAMPTZ,
    removed_rows  BIGINT,
    note          TEXT,
    PRIMARY KEY (table_name, rule, batch_key)
)
"""
LEDGER_COLUMNS = ("table_name", "rule", "batch_key", "game_date", "file_path",
                  "storage_path", "file_sha256", "rows", "checksum", "prepared_at",
                  "stored_at", "removed_at", "removed_rows", "note")


@dataclass(frozen=True)
class Spec:
    table: str
    pk: str
    key: tuple[str, ...]          # the proposition, without the rung
    values: tuple[str, ...]       # what a repeat repeats
    text_cols: tuple[str, ...]    # fingerprinted as text
    rung_pg: str                  # the rung of an alternate line, Postgres
    rung_dk: str                  # the same, DuckDB
    # Rows a reader needs whole, so no rule moves them, as a predicate on the
    # alias k (the rule's last step). Written for both engines: Postgres needs
    # its % doubled, because the statement goes through psycopg2 with params.
    keep_pg: str = "FALSE"
    keep_dk: str = "FALSE"


# The game-odds rows a reader needs whole (the reader audit of 2026-11-18, in
# docs/data_archive.md, "What reads old rows"). Each line names its reader.
# Narrowing this list moves rows that games already archived kept, and the
# ledger marks those games done, so a narrower list needs a new rule name.
_ODDS_KEEP = """(
  -- features/market_movement.py: mkt_snapshots counts each book's MLB pre-game snapshots
  (k.sport = 'MLB' AND coalesce(k.snapshot_type, '') <> 'in_play'
     AND k.market IN ('h2h', 'spreads', 'totals'))
  -- the paid in-play history buyers resume from the served times they stored
  OR (coalesce(k.snapshot_type, '') = 'in_play'
      AND (k.source LIKE 'historical_inplay{p}' OR k.source = 'odds_api_ncaab_inplay_history'))
  -- scripts/build_nba_live_ig2_artifact.py and scripts/nba_s_ingame27.py group by fetch
  OR (k.sport = 'NBA' AND coalesce(k.snapshot_type, '') = 'in_play' AND k.source IS NULL)
  -- scripts/nhl_totals_lab.py reads this paid history whole
  OR (k.sport = 'NHL' AND k.market = 'totals' AND k.source = 'odds_api_historical')
  -- data/ingestors/nfl_odds_cache_import.py resumes on the served times it stored,
  -- so a re-run would import a moved row again
  OR k.source LIKE 'nfl_odds_cache{p}'
)"""


SPECS = {
    "odds": Spec(
        "odds", "odds_id", ("game_id", "market", "bookmaker"),
        ("home_price", "away_price", "draw_price", "spread_home", "total_line",
         "over_price", "under_price"),
        ("game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "source"),
        "CASE t.market WHEN 'alternate_spreads' THEN t.spread_home "
        "WHEN 'alternate_totals' THEN t.total_line END",
        "CASE t.market WHEN 'alternate_spreads' THEN t.spread_home "
        "WHEN 'alternate_totals' THEN t.total_line END",
        _ODDS_KEEP.replace("{p}", "%%"), _ODDS_KEEP.replace("{p}", "%")),
    "player_prop_odds": Spec(
        "player_prop_odds", "prop_id", ("game_id", "market", "player_name", "bookmaker"),
        ("line", "over_price", "under_price"),
        ("game_id", "player_name", "market", "bookmaker", "snapshot_type", "snapshot_at"),
        "CASE WHEN t.market LIKE '%%alternate' THEN t.line END",
        "CASE WHEN t.market LIKE '%alternate' THEN t.line END"),
}


# ── The rule, written once for both engines ─────────────────────────────────

class Dialect:
    def __init__(self, name: str):
        self.name = name
        self.pg = name == "pg"

    def ts(self, expr: str) -> str:
        if self.pg:
            return f"(CASE WHEN {expr} ~ '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}' THEN ({expr})::timestamptz END)"
        return f"try_cast({expr} AS TIMESTAMPTZ)"

    def num(self, expr: str) -> str:
        if self.pg:
            return f"round(({expr})::numeric * 1000000)::bigint"
        return f"round(({expr}) * 1000000)::BIGINT"

    def text(self, expr: str) -> str:
        return f"coalesce(({expr})::{'text' if self.pg else 'VARCHAR'}, '~')"

    def h(self, row_text: str) -> str:
        if self.pg:
            return f"('x' || substr(md5({row_text}), 1, 15))::bit(60)::bigint"
        return f"('0x' || substr(md5({row_text}), 1, 15))::BIGINT"

    def games(self) -> str:
        return "= ANY(%s)" if self.pg else "IN (SELECT unnest(?))"

    def param(self) -> str:
        return "%s" if self.pg else "?"


def fingerprint_expr(spec: Spec, d: Dialect, alias: str = "k") -> str:
    parts = [d.text(f"{alias}.{spec.pk}")]
    parts += [d.text(f"{alias}.{c}") for c in spec.text_cols]
    parts += [d.text(d.num(f"{alias}.{c}")) for c in spec.values]
    return d.h(" || '|' || ".join(parts))


def rule_sql(spec: Spec, rule: str, d: Dialect, by_market: bool = False) -> str:
    """SELECT pk, h, game_id for the rows of the given games the rule moves.
    Parameters, in order: the game ids, the market when `by_market`, the
    min-age cutoff, and for 'old' the old cutoff (all UTC epoch seconds for
    DuckDB, timestamps for Postgres). Every window is partitioned by market, so
    one market's selection is exactly that market's share of the game's."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}")
    p = d.param()
    cut = (lambda x: f"to_timestamp({x})") if not d.pg else (lambda x: f"{x}::timestamptz")
    key = ", ".join(spec.key)
    rung = spec.rung_pg if d.pg else spec.rung_dk
    lags = ",\n           ".join(f"lag({c}) OVER w AS lag_{c}" for c in spec.values)
    same = " AND ".join(f"{c} IS NOT DISTINCT FROM lag_{c}" for c in spec.values)
    old = f"start < {cut(p)}" if rule == "old" else "FALSE"
    mkt = f" WHERE t.market = {p}" if by_market else ""
    keep = spec.keep_pg if d.pg else spec.keep_dk
    return f"""
WITH g AS (
  SELECT game_id, {d.ts('commence_time')} AS start FROM games WHERE game_id {d.games()}),
r0 AS (
  SELECT t.*, g.start, {d.ts('t.snapshot_at')} AS ts, {rung} AS rung
    FROM {spec.table} t JOIN g ON g.game_id = t.game_id{mkt}),
r AS (
  SELECT r0.*, (coalesce(snapshot_type, '') <> 'in_play' AND ts <= start) AS pre FROM r0),
k AS (
  SELECT r.*,
         row_number() OVER (PARTITION BY {key}, rung ORDER BY ts, {spec.pk}) AS first_n,
         row_number() OVER (PARTITION BY {key}, rung
                            ORDER BY CASE WHEN pre THEN 0 ELSE 1 END, ts DESC, {spec.pk} DESC)
           AS close_n,
         lag({spec.pk}) OVER w AS lag_pk,
         {lags}
    FROM r
  WINDOW w AS (PARTITION BY {key}, rung, coalesce(snapshot_type, '') ORDER BY ts, {spec.pk}))
SELECT k.{spec.pk} AS pk, {fingerprint_expr(spec, d)} AS h, k.game_id AS game_id
  FROM k
 WHERE k.ts IS NOT NULL AND k.start IS NOT NULL AND k.start < {cut(p)}
   AND k.first_n > 1
   AND NOT (k.close_n = 1 AND coalesce(k.pre, FALSE))
   AND ({old} OR (k.lag_pk IS NOT NULL AND {same}))
   AND NOT coalesce({keep}, FALSE)
"""


def cutoffs(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    return now - dt.timedelta(days=MIN_AGE_DAYS), now - dt.timedelta(days=OLD_DAYS)


def _params(d: Dialect, rule: str, games, now: dt.datetime, market: str | None = None) -> list:
    min_cut, old_cut = cutoffs(now)
    m = [market] if market is not None else []
    if d.pg:
        out = [list(games)] + m + [min_cut]
        return out + [old_cut] if rule == "old" else out
    out = [list(games)] + m + [min_cut.timestamp()]
    return out + [old_cut.timestamp()] if rule == "old" else out


# ── The PC copy ──────────────────────────────────────────────────────────────

def games_on(copy, date: str, now: dt.datetime) -> list[str]:
    """Games whose ET start date is `date` and which started over MIN_AGE_DAYS ago."""
    min_cut, _ = cutoffs(now)
    rows = copy.execute("""
        SELECT game_id, epoch(try_cast(commence_time AS TIMESTAMPTZ)) FROM games
         WHERE try_cast(commence_time AS TIMESTAMPTZ) BETWEEN to_timestamp(?) AND to_timestamp(?)""",
        [(dt.datetime.fromisoformat(date).replace(tzinfo=ET)).timestamp(),
         (dt.datetime.fromisoformat(date).replace(tzinfo=ET) + dt.timedelta(days=1)).timestamp() - 1]
    ).fetchall()
    return sorted(g for g, s in rows if s is not None and s < min_cut.timestamp())


def copy_selection(copy, spec: Spec, rule: str, games, now: dt.datetime) -> dict:
    """{game_id: (rows, checksum)} by the rule, on the PC copy."""
    if not games:
        return {}
    sql = f"SELECT game_id, count(*), sum(h) FROM ({rule_sql(spec, rule, Dialect('dk'))}) s GROUP BY game_id"
    return {g: (int(n), int(c)) for g, n, c in copy.execute(sql, _params(Dialect("dk"), rule, games, now)).fetchall()}


def file_path(table: str, rule: str, date: str) -> Path:
    return ARCHIVE_ROOT / table / rule / date[:7] / f"{date}.parquet"


def storage_path(table: str, rule: str, date: str) -> str:
    return f"{table}/{rule}/{date[:7]}/{date}.parquet"


def write_file(copy, spec: Spec, rule: str, games, now: dt.datetime, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    sel = rule_sql(spec, rule, Dialect("dk"))
    params = _params(Dialect("dk"), rule, games, now)
    copy.execute("DROP TABLE IF EXISTS temp.archive_pick")
    copy.execute(f"CREATE TEMP TABLE archive_pick AS SELECT pk FROM ({sel}) s", params)
    copy.execute(f"""COPY (SELECT t.* FROM {spec.table} t
                           WHERE t.{spec.pk} IN (SELECT pk FROM temp.archive_pick)
                           ORDER BY t.{spec.pk})
                     TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(tmp, path)


def file_selection(spec: Spec, path: Path) -> dict:
    """{game_id: (rows, checksum)} read back from the archive file."""
    import duckdb
    con = duckdb.connect()
    d = Dialect("dk")
    sql = (f"SELECT k.game_id, count(*), sum({fingerprint_expr(spec, d)}) "
           f"FROM read_parquet('{path.as_posix()}') k GROUP BY k.game_id")
    return {g: (int(n), int(c)) for g, n, c in con.execute(sql).fetchall()}


def file_markets(spec: Spec, path: Path, game: str) -> dict:
    """{market: (rows, checksum, [pk, ...])} for one game, read from the file."""
    import duckdb
    con = duckdb.connect()
    d = Dialect("dk")
    sql = (f"SELECT k.market, count(*), sum({fingerprint_expr(spec, d)}), list(k.{spec.pk}) "
           f"FROM read_parquet('{path.as_posix()}') k WHERE k.game_id = ? GROUP BY k.market")
    return {m: (int(n), int(c), [int(x) for x in pks])
            for m, n, c, pks in con.execute(sql, [game]).fetchall()}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


# ── Supabase: the ledger, Storage, the gated removal ────────────────────────

def ensure_ledger(conn) -> None:
    from data.anon_readable import lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, "archive_batches", columns=LEDGER_COLUMNS,
                             rls=True, revoked_from=("anon", "authenticated")):
        conn.execute(LEDGER_DDL)
        lock_down(conn, "archive_batches")
        conn.commit()


def is_timeout(exc: BaseException) -> bool:
    """A statement the database cancelled for running too long. psycopg2 makes
    it an OperationalError, the same family as a dropped connection, but it is
    not one: running it again at the same size only repeats the heavy read."""
    import psycopg2.errors
    return isinstance(exc, psycopg2.errors.QueryCanceled)


TIMED_OUT = "timed out"


def server_selection(conn, spec: Spec, rule: str, games, now: dt.datetime) -> dict:
    """{game_id: (rows, checksum)} by the rule, in Postgres, read-only, one
    game a statement. A game whose statement times out maps to TIMED_OUT."""
    d = Dialect("pg")
    sql = (f"SELECT game_id, count(*), sum(h)::text FROM ({rule_sql(spec, rule, d)}) s "
           f"GROUP BY game_id")
    out = {}
    for g in games:
        try:
            conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
            rows = conn.execute(sql, tuple(_params(d, rule, [g], now))).fetchall()
        except Exception as exc:  # noqa: BLE001
            conn.rollback()
            if not is_timeout(exc):
                raise
            out[g] = TIMED_OUT
            continue
        conn.rollback()
        out.update({gid: (int(n), int(c)) for gid, n, c in rows})
    return out


def _storage():
    import requests
    from scripts.local_mirror import project_url, read_env_value
    env = Path(os.environ.get("ARCHIVE_ENV_FILE", DEFAULT_ENV))
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or read_env_value("SUPABASE_SERVICE_ROLE_KEY", env)
    base = project_url(os.environ.get("DATABASE_URL", ""), env)
    if not key or not base:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY (or the project URL) is not set; "
                           "the Storage copy cannot be made, so nothing is removed")
    s = requests.Session()
    s.headers.update({"apikey": key, "Authorization": f"Bearer {key}"})
    return s, base.rstrip("/")


def ensure_bucket(s, base: str) -> None:
    r = s.get(f"{base}/storage/v1/bucket/{BUCKET}", timeout=30)
    if r.status_code == 200:
        if r.json().get("public"):
            raise RuntimeError(f"bucket {BUCKET!r} is public; the archive must be private")
        return
    r = s.post(f"{base}/storage/v1/bucket", json={"id": BUCKET, "name": BUCKET, "public": False},
               timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"could not create bucket {BUCKET!r}: HTTP {r.status_code} {r.text[:200]}")


# Storage refuses one object over the project's file-size limit: on 2026-11-16
# it took a 23.8 MB file and refused 52.9 MB and 70.5 MB ones with HTTP 413
# (Supabase's default limit is 50 MB). A larger file goes up in parts of this
# size, named <object>.part-001, -002, ...; the local file stays whole.
PART_BYTES = 40 * 2**20


def part_names(obj: str, size: int) -> list[str]:
    if size <= PART_BYTES:
        return [obj]
    n = -(-size // PART_BYTES)
    return [f"{obj}.part-{i:03d}" for i in range(1, n + 1)]


def upload_and_check(path: Path, obj: str, storage=None) -> str:
    """Upload, download again, compare bytes. Returns the file's sha256.
    A file over PART_BYTES is stored in parts; the parts read back and joined
    must hash to the file's sha256."""
    s, base = storage or _storage()
    ensure_bucket(s, base)
    want = sha256(path)
    names = part_names(obj, path.stat().st_size)
    got = hashlib.sha256()
    with open(path, "rb") as fh:
        for name in names:
            chunk = fh.read(PART_BYTES) if len(names) > 1 else fh.read()
            r = s.post(f"{base}/storage/v1/object/{BUCKET}/{name}", data=chunk, timeout=600,
                       headers={"content-type": "application/octet-stream", "x-upsert": "true"})
            if r.status_code not in (200, 201):
                raise RuntimeError(f"upload of {name} failed: HTTP {r.status_code} {r.text[:200]}")
    for name in names:
        back = s.get(f"{base}/storage/v1/object/{BUCKET}/{name}", timeout=600)
        if back.status_code != 200:
            raise RuntimeError(f"{name}: could not read the copy back (HTTP {back.status_code})")
        got.update(back.content)
    if got.hexdigest() != want:
        raise RuntimeError(f"{obj}: the copy read back from Storage differs from the file")
    return want


def remove_game(conn, spec: Spec, rule: str, game: str, want: tuple[int, int],
                now: dt.datetime) -> int:
    """Remove one game's rows, only if Postgres picks exactly the archived set."""
    d = Dialect("pg")
    sel = rule_sql(spec, rule, d)
    params = tuple(_params(d, rule, [game], now))
    try:
        conn.execute(f"SET LOCAL statement_timeout = '{REMOVE_TIMEOUT}'")
        conn.execute(f"CREATE TEMP TABLE archive_pick ON COMMIT DROP AS {sel}", params)
        n, c = conn.execute("SELECT count(*), coalesce(sum(h), 0)::text FROM archive_pick").fetchone()
        if (int(n), int(c)) != want:
            conn.rollback()
            raise RuntimeError(f"{game}: Postgres picks {n} rows / {c}, the archive holds "
                               f"{want[0]} / {want[1]}; nothing removed")
        cur = conn.execute(f"DELETE FROM {spec.table} t USING archive_pick a WHERE t.{spec.pk} = a.pk")
        removed = cur.rowcount
        if removed != want[0]:
            conn.rollback()
            raise RuntimeError(f"{game}: the delete matched {removed} rows, not {want[0]}; rolled back")
        conn.execute("""UPDATE archive_batches SET removed_at = now(), removed_rows = %s
                         WHERE table_name = %s AND rule = %s AND batch_key = %s""",
                     (removed, spec.table, rule, game))
        conn.commit()
        return removed
    except Exception:
        conn.rollback()
        raise


# ── The quiet window ─────────────────────────────────────────────────────────

def in_removal_window(t: dt.datetime) -> bool:
    start, end = REMOVE_WINDOW_ET
    return start <= t.astimezone(ET).time() < end


def _load(conn) -> tuple[int, float]:
    """(other statements running, seconds the longest app read has run)."""
    n, app_s = conn.execute(
        "SELECT count(*), coalesce(max(extract(epoch FROM now() - query_start)) "
        "FILTER (WHERE usename = ANY(%s)), 0) FROM pg_stat_activity WHERE state = 'active' "
        "AND backend_type = 'client backend' AND pid <> pg_backend_pid()",
        (list(APP_ROLES),)).fetchone()
    conn.rollback()
    return int(n), float(app_s)


def wait_for_quiet(conn, clock=None, sleeper=None, log=print, anytime: bool = False) -> bool:
    """True when a removal may start now; False once the night's window is over.
    Waits out the hourly refresh and a busy database while the window lasts.
    With `anytime` there is no window: it also waits while an app read has run
    APP_READ_LIMIT_S, and the morning window counts as closed."""
    import time
    from scripts.local_mirror import closed_until
    clock = clock or (lambda: dt.datetime.now(UTC))
    sleeper = sleeper or time.sleep
    said = None
    while True:
        t = clock()
        if not anytime and not in_removal_window(t):
            return False
        until = closed_until(t)
        if until is not None:
            if said != "refresh":
                log(f"removals pause for the refresh pass until {until.astimezone(ET):%H:%M} ET")
                said = "refresh"
            sleeper(max(1.0, (until - t).total_seconds()))
            continue
        busy, app_s = _load(conn)
        if busy > MAX_ACTIVE_OTHERS or (anytime and app_s >= APP_READ_LIMIT_S):
            why = (f"an app read has run {app_s:.1f} s" if anytime and app_s >= APP_READ_LIMIT_S
                   else f"{busy} other statements running (> {MAX_ACTIVE_OTHERS})")
            if said != why[:12]:
                log(f"removals pause: {why}")
                said = why[:12]
            sleeper(BUSY_SLEEP_S if busy > MAX_ACTIVE_OTHERS else 5.0)
            continue
        return True


def remove_market(conn, spec: Spec, rule: str, game: str, market: str,
                  want: tuple, now: dt.datetime) -> int:
    """Remove one market of one game, only if Postgres picks exactly the
    archived set for it. Returns rows removed; 0 when an earlier run that
    stopped part-way through the game already removed this market."""
    d = Dialect("pg")
    sel = rule_sql(spec, rule, d, by_market=True)
    params = tuple(_params(d, rule, [game], now, market))
    n_want, c_want, pks = want
    try:
        conn.execute(f"SET LOCAL statement_timeout = '{REMOVE_TIMEOUT}'")
        conn.execute(f"CREATE TEMP TABLE archive_pick ON COMMIT DROP AS {sel}", params)
        n, c = conn.execute("SELECT count(*), coalesce(sum(h), 0)::text FROM archive_pick").fetchone()
        if int(n) == 0:
            left = conn.execute(f"SELECT count(*) FROM {spec.table} WHERE {spec.pk} = ANY(%s)",
                                (pks,)).fetchone()[0]
            conn.rollback()
            if int(left) == 0:
                return 0
            raise RuntimeError(f"{game} {market}: Postgres picks no rows but {left} archived rows "
                               f"remain; nothing removed")
        if (int(n), int(c)) != (n_want, c_want):
            conn.rollback()
            raise RuntimeError(f"{game} {market}: Postgres picks {n} rows / {c}, the archive holds "
                               f"{n_want} / {c_want}; nothing removed")
        cur = conn.execute(f"DELETE FROM {spec.table} t USING archive_pick a WHERE t.{spec.pk} = a.pk")
        if cur.rowcount != n_want:
            conn.rollback()
            raise RuntimeError(f"{game} {market}: the delete matched {cur.rowcount} rows, not "
                               f"{n_want}; rolled back")
        conn.commit()
        return n_want
    except Exception:
        conn.rollback()
        raise


# ── Steps ────────────────────────────────────────────────────────────────────

def prepare(copy, conn, table: str, rule: str, date: str, now: dt.datetime, log=print,
            check: bool = False) -> dict:
    """Write the date's file from the PC copy and its ledger rows. With `check`
    it also picks each game in Postgres now; without it (the default) the only
    Postgres read is the one inside the removal, which refuses any game where
    Postgres and the file differ."""
    spec = SPECS[table]
    games = games_on(copy, date, now)
    mine = copy_selection(copy, spec, rule, games, now)
    path = file_path(table, rule, date)
    out = {"date": date, "games": len(games), "with_rows": len(mine),
           "rows": sum(n for n, _ in mine.values()), "ready": 0, "refused": []}
    if not mine:
        return out
    write_file(copy, spec, rule, list(mine), now, path)
    back = file_selection(spec, path)
    if back != mine:
        raise RuntimeError(f"{path}: the file read back differs from the copy's selection")
    theirs = server_selection(conn, spec, rule, list(mine), now) if check else None
    ensure_ledger(conn)
    for g, (n, c) in sorted(mine.items()):
        ok = theirs is None or theirs.get(g) == (n, c)
        conn.execute("""
            INSERT INTO archive_batches (table_name, rule, batch_key, game_date, file_path,
                                         storage_path, rows, checksum, note)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (table_name, rule, batch_key) DO UPDATE SET
              file_path = EXCLUDED.file_path, storage_path = EXCLUDED.storage_path,
              rows = EXCLUDED.rows, checksum = EXCLUDED.checksum, note = EXCLUDED.note,
              prepared_at = now()
            WHERE archive_batches.removed_at IS NULL""",
            (table, rule, g, date, str(path), storage_path(table, rule, date), n, str(c),
             None if ok else f"Postgres picks {theirs.get(g)}"))
        if ok:
            out["ready"] += 1
        else:
            out["refused"].append(g)
    conn.commit()
    if check:
        log(f"prepare {table} {rule} {date}: {out['rows']:,} rows in {out['with_rows']} games; "
            f"{out['ready']} match Postgres, {len(out['refused'])} refused")
    else:
        log(f"prepare {table} {rule} {date}: {out['rows']:,} rows in {out['with_rows']} games "
            f"written and read back; Postgres is checked at removal")
    return out


def upload(conn, table: str, rule: str, date: str, log=print) -> str:
    path = file_path(table, rule, date)
    digest = upload_and_check(path, storage_path(table, rule, date))
    conn.execute("""UPDATE archive_batches SET stored_at = now(), file_sha256 = %s
                     WHERE table_name = %s AND rule = %s AND game_date = %s""",
                 (digest, table, rule, date))
    conn.commit()
    log(f"upload {table} {rule} {date}: stored and read back, sha256 {digest[:12]}")
    return digest


REMOVAL_TIMED_OUT = "removal timed out"


def _note(conn, spec: Spec, rule: str, game: str, note: str) -> None:
    conn.execute("""UPDATE archive_batches SET note = %s
                     WHERE table_name = %s AND rule = %s AND batch_key = %s AND removed_at IS NULL""",
                 (note, spec.table, rule, game))
    conn.commit()


def remove(conn, table: str, rule: str, date: str, now: dt.datetime, log=print,
           clock=None, sleeper=None, anytime: bool = False, batch_rows: int = 0) -> dict:
    """Remove the date's stored games, one transaction each, in the quiet window
    only (with `anytime`, at any hour under the harder guard and resting after
    each game as long as it took). A game Postgres disagrees on is refused and noted (it is prepared
    again after the next copy); a game that runs past REMOVE_TIMEOUT is noted
    and left for the next night; neither stops the others."""
    spec = SPECS[table]
    path = file_path(table, rule, date)
    back = file_selection(spec, path)
    rows = conn.execute("""
        SELECT batch_key, rows, checksum, file_sha256, stored_at, removed_at, note
          FROM archive_batches WHERE table_name = %s AND rule = %s AND game_date = %s""",
        (table, rule, date)).fetchall()
    conn.rollback()
    digest = sha256(path)
    out = {"removed": 0, "games": 0, "skipped": [], "stopped": None}
    if batch_rows > 0:
        return _remove_batched(conn, spec, rule, date, path, back, digest, rows, now, log,
                               clock, sleeper, anytime, batch_rows, out)
    for g, n, c, fsha, stored, removed_at, note in rows:
        if removed_at is not None:
            continue
        if stored is None or fsha != digest:
            out["skipped"].append((g, "no verified Storage copy of this file"))
            continue
        if note and not note.startswith(REMOVAL_TIMED_OUT):
            out["skipped"].append((g, note))
            continue
        if back.get(g) != (int(n), int(c)):
            out["skipped"].append((g, "file does not hold the ledger's rows"))
            continue
        if not wait_for_quiet(conn, clock, sleeper, log, anytime=anytime):
            out["stopped"] = "outside the quiet window"
            break
        tick = clock or (lambda: dt.datetime.now(UTC))
        rest = sleeper or __import__("time").sleep
        t0 = tick()
        try:
            if int(n) > SPLIT_ROWS:
                got, done = _remove_by_market(conn, spec, rule, g, path, (int(n), int(c)), now,
                                              log, clock, sleeper, anytime)
                if not done:
                    out["removed"] += got
                    out["stopped"] = "outside the quiet window"
                    break
            else:
                got = remove_game(conn, spec, rule, g, (int(n), int(c)), now)
                took = (tick() - t0).total_seconds()
                if anytime and took > 0:
                    rest(took)
            out["removed"] += got
            out["games"] += 1
            log(f"  {g}: {got:,} rows removed in {(tick() - t0).total_seconds():.1f} s")
        except RuntimeError as exc:
            _note(conn, spec, rule, g, f"refused at removal: {exc}")
            out["skipped"].append((g, str(exc)))
        except Exception as exc:  # noqa: BLE001
            if not is_timeout(exc):
                raise
            msg = f"{REMOVAL_TIMED_OUT} after {REMOVE_TIMEOUT} at {_utc_iso(now)}; left in Supabase"
            _note(conn, spec, rule, g, msg)
            out["skipped"].append((g, msg))
    log(f"remove {table} {rule} {date}: {out['removed']:,} rows from {out['games']} games; "
        f"{len(out['skipped'])} skipped" + (f"; stopped: {out['stopped']}" if out["stopped"] else ""))
    return out


def _remove_batched(conn, spec: Spec, rule: str, date: str, path: Path, back: dict, digest: str,
                    rows, now: dt.datetime, log, clock, sleeper, anytime: bool, batch_rows: int,
                    out: dict) -> dict:
    """remove() with small games together: the same checks per game, then up to
    batch_rows archived rows and BATCH_GAMES games a transaction. A game over
    SPLIT_ROWS still goes one market a transaction."""
    tick = clock or (lambda: dt.datetime.now(UTC))
    rest = sleeper or __import__("time").sleep
    ready = []
    for g, n, c, fsha, stored, removed_at, note in rows:
        if removed_at is not None:
            continue
        if stored is None or fsha != digest:
            out["skipped"].append((g, "no verified Storage copy of this file"))
        elif note and not note.startswith(REMOVAL_TIMED_OUT):
            out["skipped"].append((g, note))
        elif back.get(g) != (int(n), int(c)):
            out["skipped"].append((g, "file does not hold the ledger's rows"))
        else:
            ready.append((g, (int(n), int(c))))
    big = [(g, w) for g, w in ready if w[0] > SPLIT_ROWS]
    small = sorted((g, w) for g, w in ready if w[0] <= SPLIT_ROWS)
    batches, cur, cur_n = [], {}, 0
    for g, w in small:
        if cur and (cur_n + w[0] > batch_rows or len(cur) >= BATCH_GAMES):
            batches.append(cur)
            cur, cur_n = {}, 0
        cur[g] = w
        cur_n += w[0]
    if cur:
        batches.append(cur)
    for g, w in big:
        if not wait_for_quiet(conn, clock, sleeper, log, anytime=anytime):
            out["stopped"] = "outside the quiet window"
            break
        t0 = tick()
        try:
            got, done = _remove_by_market(conn, spec, rule, g, path, w, now, log, clock, sleeper,
                                          anytime)
        except RuntimeError as exc:
            _note(conn, spec, rule, g, f"refused at removal: {exc}")
            out["skipped"].append((g, str(exc)))
            continue
        out["removed"] += got
        if not done:
            out["stopped"] = "outside the quiet window"
            break
        out["games"] += 1
        log(f"  {g}: {got:,} rows removed in {(tick() - t0).total_seconds():.1f} s")
    for b in ([] if out["stopped"] else batches):
        if not wait_for_quiet(conn, clock, sleeper, log, anytime=anytime):
            out["stopped"] = "outside the quiet window"
            break
        t0 = tick()
        try:
            got, refused = remove_batch(conn, spec, rule, b, now)
        except RuntimeError as exc:
            for g in b:
                _note(conn, spec, rule, g, f"refused at removal: {exc}")
                out["skipped"].append((g, str(exc)))
            continue
        except Exception as exc:  # noqa: BLE001
            if not is_timeout(exc):
                raise
            msg = f"{REMOVAL_TIMED_OUT} after {REMOVE_TIMEOUT} at {_utc_iso(now)}; left in Supabase"
            for g in b:
                _note(conn, spec, rule, g, msg)
                out["skipped"].append((g, msg))
            continue
        took = (tick() - t0).total_seconds()
        for g, why in refused.items():
            _note(conn, spec, rule, g, f"refused at removal: {why}")
            out["skipped"].append((g, why))
        out["removed"] += got
        out["games"] += len(b) - len(refused)
        log(f"  {len(b) - len(refused)} games: {got:,} rows removed in {took:.1f} s"
            + (f"; {len(refused)} refused" if refused else ""))
        if anytime and took > 0:
            rest(took)
    log(f"remove {spec.table} {rule} {date}: {out['removed']:,} rows from {out['games']} games; "
        f"{len(out['skipped'])} skipped" + (f"; stopped: {out['stopped']}" if out["stopped"] else ""))
    return out


def _remove_by_market(conn, spec: Spec, rule: str, game: str, path: Path, want: tuple,
                      now: dt.datetime, log, clock, sleeper, anytime: bool) -> tuple:
    """A game over SPLIT_ROWS, one market a transaction, the guard before each.
    Returns (rows removed, finished). Unfinished leaves the game resumable."""
    tick = clock or (lambda: dt.datetime.now(UTC))
    rest = sleeper or __import__("time").sleep
    markets = file_markets(spec, path, game)
    if (sum(v[0] for v in markets.values()), sum(v[1] for v in markets.values())) != tuple(want):
        raise RuntimeError(f"{game}: the file's markets do not add up to the ledger; nothing removed")
    got = 0
    for i, m in enumerate(sorted(markets)):
        if i and not wait_for_quiet(conn, clock, sleeper, log, anytime=anytime):
            return got, False
        t0 = tick()
        got += remove_market(conn, spec, rule, game, m, markets[m], now)
        took = (tick() - t0).total_seconds()
        if anytime and took > 0:
            rest(took)
    conn.execute("""UPDATE archive_batches SET removed_at = now(), removed_rows = %s
                     WHERE table_name = %s AND rule = %s AND batch_key = %s""",
                 (want[0], spec.table, rule, game))
    conn.commit()
    return got, True


def _utc_iso(t: dt.datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def remove_pending(conn, table: str, rule: str, now: dt.datetime, log=print,
                   clock=None, sleeper=None, anytime: bool = False, batch_rows: int = 0) -> dict:
    """Every date with a stored copy and a game not yet removed, oldest first,
    until the quiet window ends (with `anytime`, until all are done)."""
    check_allowed(table, rule)
    # One removal at a time: a second run would find the first one's games
    # already gone and note them refused.
    got = conn.execute("SELECT pg_try_advisory_lock(%s)", (REMOVE_LOCK,)).fetchone()[0]
    if not got:
        conn.rollback()
        log("another removal is running; nothing done")
        return {"dates": 0, "removed_rows": 0, "skipped_games": 0,
                "stopped": "another removal is running"}
    dates = [r[0] for r in conn.execute("""
        SELECT DISTINCT game_date FROM archive_batches
         WHERE table_name = %s AND rule = %s AND stored_at IS NOT NULL AND removed_at IS NULL
         ORDER BY 1""", (table, rule)).fetchall()]
    conn.rollback()
    out = {"dates": 0, "removed_rows": 0, "skipped_games": 0, "stopped": None}
    for date in dates:
        r = remove(conn, table, rule, date, now, log, clock, sleeper, anytime=anytime,
                   batch_rows=batch_rows)
        out["dates"] += 1
        out["removed_rows"] += r["removed"]
        out["skipped_games"] += len(r["skipped"])
        if r["stopped"]:
            out["stopped"] = r["stopped"]
            break
    conn.execute("SELECT pg_advisory_unlock(%s)", (REMOVE_LOCK,))
    conn.rollback()
    return out


# ── Bulk: many dates from one pass of the copy; small games together ─────────

def _games_by_date(copy, start: str, end: str, now: dt.datetime) -> dict:
    """{ET date: [game_id, ...]} for games in [start, end] that started over
    MIN_AGE_DAYS ago: games_on() for a range, in one read."""
    min_cut, _ = cutoffs(now)
    lo = dt.datetime.fromisoformat(start).replace(tzinfo=ET)
    hi = dt.datetime.fromisoformat(end).replace(tzinfo=ET) + dt.timedelta(days=1)
    rows = copy.execute("""
        SELECT game_id, epoch(try_cast(commence_time AS TIMESTAMPTZ)) FROM games
         WHERE try_cast(commence_time AS TIMESTAMPTZ) >= to_timestamp(?)
           AND try_cast(commence_time AS TIMESTAMPTZ) < to_timestamp(?)""",
        [lo.timestamp(), hi.timestamp()]).fetchall()
    out: dict = {}
    for g, start_s in rows:
        if start_s is not None and start_s < min_cut.timestamp():
            day = dt.datetime.fromtimestamp(start_s, ET).date().isoformat()
            out.setdefault(day, []).append(g)
    return {d: sorted(v) for d, v in sorted(out.items())}


def prepare_range(copy, conn, table: str, rule: str, start: str, end: str, now: dt.datetime,
                  log=print) -> dict:
    """prepare() for every ET date in [start, end], from ONE pass of the copy.

    The same file per date, the same read-back and the same ledger rows as
    prepare(), one ledger statement per date. Measured 2026-11-18: one pick
    over all of `odds` on the copy took 515 s, and a per-date pick 13 s, which
    is about 11 hours for its 2,984 dates before writing a file.

    A date whose file is already in Storage is skipped, never rewritten: its
    rows may have left Supabase, and a new pick could then hold fewer rows than
    the archive it would replace."""
    check_allowed(table, rule)
    spec = SPECS[table]
    ensure_ledger(conn)
    done = {r[0] for r in conn.execute(
        """SELECT DISTINCT game_date FROM archive_batches
            WHERE table_name = %s AND rule = %s AND stored_at IS NOT NULL""", (table, rule)).fetchall()}
    conn.rollback()
    by_date = {d: g for d, g in _games_by_date(copy, start, end, now).items() if d not in done}
    out = {"dates": 0, "games": 0, "rows": 0, "skipped_dates": len(done)}
    games = [g for v in by_date.values() for g in v]
    if not games:
        return out
    d = Dialect("dk")
    copy.execute("DROP TABLE IF EXISTS temp.archive_days")
    copy.execute("CREATE TEMP TABLE archive_days AS SELECT unnest(?) AS game_id, unnest(?) AS _day",
                 [games, [day for day, v in by_date.items() for _ in v]])
    copy.execute("DROP TABLE IF EXISTS temp.archive_bulk")
    copy.execute(f"""
        CREATE TEMP TABLE archive_bulk AS
        SELECT t.*, a._day FROM {spec.table} t
          JOIN ({rule_sql(spec, rule, d)}) s ON t.{spec.pk} = s.pk
          JOIN temp.archive_days a ON a.game_id = t.game_id
         ORDER BY a._day, t.{spec.pk}""", _params(d, rule, games, now))
    sel: dict = {}
    for day, g, n, c in copy.execute(
            f"SELECT k._day, k.game_id, count(*), sum({fingerprint_expr(spec, d)}) "
            f"FROM temp.archive_bulk k GROUP BY 1, 2").fetchall():
        sel.setdefault(day, {})[g] = (int(n), int(c))
    for day in sorted(sel):
        mine = sel[day]
        path = file_path(table, rule, day)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        copy.execute(f"""COPY (SELECT * EXCLUDE (_day) FROM temp.archive_bulk WHERE _day = ?
                               ORDER BY {spec.pk})
                         TO '{tmp.as_posix()}' (FORMAT PARQUET, COMPRESSION ZSTD)""", [day])
        os.replace(tmp, path)
        if file_selection(spec, path) != mine:
            raise RuntimeError(f"{path}: the file read back differs from the copy's selection")
        gs = sorted(mine)
        conn.execute("""
            INSERT INTO archive_batches (table_name, rule, batch_key, game_date, file_path,
                                         storage_path, rows, checksum, note)
            SELECT %s, %s, u.g, %s, %s, %s, u.n, u.c, NULL
              FROM unnest(%s::text[], %s::bigint[], %s::text[]) AS u(g, n, c)
            ON CONFLICT (table_name, rule, batch_key) DO UPDATE SET
              file_path = EXCLUDED.file_path, storage_path = EXCLUDED.storage_path,
              rows = EXCLUDED.rows, checksum = EXCLUDED.checksum, note = EXCLUDED.note,
              prepared_at = now()
            WHERE archive_batches.removed_at IS NULL""",
            (table, rule, day, str(path), storage_path(table, rule, day),
             gs, [mine[g][0] for g in gs], [str(mine[g][1]) for g in gs]))
        conn.commit()
        out["dates"] += 1
        out["games"] += len(gs)
        out["rows"] += sum(n for n, _ in mine.values())
    copy.execute("DROP TABLE IF EXISTS temp.archive_bulk")
    log(f"prepare {table} {rule} {start}..{end}: {out['rows']:,} rows in {out['games']:,} games "
        f"over {out['dates']} dates written and read back; {len(done)} dates already stored")
    return out


def remove_batch(conn, spec: Spec, rule: str, wants: dict, now: dt.datetime) -> tuple:
    """Remove several small games in ONE transaction. Each is still checked on
    its own: only a game whose Postgres pick equals the archive's count and
    fingerprint is deleted. Returns (rows removed, {game: why refused})."""
    d = Dialect("pg")
    games = sorted(wants)
    sel = rule_sql(spec, rule, d)
    try:
        conn.execute(f"SET LOCAL statement_timeout = '{REMOVE_TIMEOUT}'")
        conn.execute(f"CREATE TEMP TABLE archive_pick ON COMMIT DROP AS {sel}",
                     tuple(_params(d, rule, games, now)))
        got = {g: (int(n), int(c)) for g, n, c in conn.execute(
            "SELECT game_id, count(*), coalesce(sum(h), 0)::text FROM archive_pick GROUP BY game_id"
        ).fetchall()}
        ok = [g for g in games if got.get(g) == tuple(wants[g])]
        refused = {g: (f"{g}: Postgres picks {got.get(g, (0, 0))[0]} rows / {got.get(g, (0, 0))[1]}, "
                       f"the archive holds {wants[g][0]} / {wants[g][1]}; nothing removed")
                   for g in games if g not in ok}
        removed = 0
        if ok:
            want_n = sum(wants[g][0] for g in ok)
            cur = conn.execute(f"DELETE FROM {spec.table} t USING archive_pick a "
                               f"WHERE t.{spec.pk} = a.pk AND a.game_id = ANY(%s)", (ok,))
            if cur.rowcount != want_n:
                conn.rollback()
                raise RuntimeError(f"a batch of {len(ok)} games: the delete matched {cur.rowcount} "
                                   f"rows, not {want_n}; rolled back")
            conn.execute("""UPDATE archive_batches b SET removed_at = now(), removed_rows = u.n
                              FROM unnest(%s::text[], %s::bigint[]) AS u(g, n)
                             WHERE b.table_name = %s AND b.rule = %s AND b.batch_key = u.g""",
                         (ok, [wants[g][0] for g in ok], spec.table, rule))
            removed = want_n
        conn.commit()
        return removed, refused
    except Exception:
        conn.rollback()
        raise


def check_allowed(table: str, rule: str) -> None:
    if (table, rule) not in ALLOWED:
        raise SystemExit(f"{table} {rule} may not move yet: "
                         f"{REFUSED.get((table, rule), 'not reviewed')}")


DATE_ATTEMPTS = 3


def run(copy, conn, table: str, rule: str, start: str, end: str, now: dt.datetime,
        log=print, connect=None, check: bool = False, clock=None, sleeper=None) -> dict:
    """Every ET game date in [start, end]: prepare, then upload when the
    Storage copy can be made (without the key it prepares only), then remove
    if it is the quiet window.

    A dropped connection retries the date on a new one (`connect`). On
    2026-11-16 the pooler closed the connection on the 40th date (Postgres
    itself had not restarted). Every step is safe to repeat: prepare
    rewrites its file and ledger rows, upload overwrites the object and reads
    it back, and remove skips games already removed. A statement timeout is
    not a dropped connection and is never retried here: the same read would
    only run again (2026-09-10 was read three times that way)."""
    import psycopg2
    from data.db import ConnectionLost
    check_allowed(table, rule)
    try:
        _storage()
        can_store = True
    except RuntimeError as exc:
        can_store = False
        log(f"Storage: {exc}")
    clock = clock or (lambda: dt.datetime.now(UTC))
    d = dt.date.fromisoformat(start)
    out = {"dates": 0, "prepared_rows": 0, "removed_rows": 0, "refused_games": 0}
    while d <= dt.date.fromisoformat(end):
        for attempt in range(1, DATE_ATTEMPTS + 1):
            try:
                p = prepare(copy, conn, table, rule, d.isoformat(), now, log, check=check)
                removed = 0
                if can_store and p["ready"]:
                    upload(conn, table, rule, d.isoformat(), log)
                    if in_removal_window(clock()):
                        removed = remove(conn, table, rule, d.isoformat(), now, log,
                                         clock, sleeper)["removed"]
                break
            except (ConnectionLost, psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                if is_timeout(exc) or connect is None or attempt == DATE_ATTEMPTS:
                    raise
                log(f"{d}: connection lost ({type(exc).__name__}); retrying on a new one "
                    f"({attempt}/{DATE_ATTEMPTS - 1})")
                try:
                    conn.close()
                except Exception:  # noqa: BLE001
                    pass
                conn = connect()
        out["dates"] += 1
        out["prepared_rows"] += p["rows"]
        out["refused_games"] += len(p["refused"])
        out["removed_rows"] += removed
        d += dt.timedelta(days=1)
    return out


def table_size(conn, table: str) -> tuple[int, int]:
    n = conn.execute("SELECT pg_total_relation_size(%s::regclass), pg_database_size(current_database())",
                     (table,)).fetchone()
    conn.rollback()
    return int(n[0]), int(n[1])


def reclaim(conn, table: str, log=print) -> dict:
    """Rewrite the table so the removed rows' space comes back (VACUUM FULL).

    NOT YET MEASURED, so not yet scheduled. It holds an exclusive lock on the
    table for the whole rewrite (no prop row can be written or read), and on
    this small machine nobody has timed a rewrite of a 40 GB table: a game's
    rows came off disk at 650-2,300 rows a second on 2026-11-16. It also needs
    free disk for the new table, its indexes and the write-ahead log. Before it
    runs: time a sequential read of the table in the quiet window, and read the
    free disk. If it cannot finish inside the window, the choices are a plain
    VACUUM (the space is reused by new rows but not returned), pg_repack (no
    long lock), or a larger machine for one night."""
    before = table_size(conn, table)
    conn.commit()
    raw = conn._conn
    old = raw.autocommit
    raw.autocommit = True
    try:
        with raw.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute(f"VACUUM (FULL, ANALYZE) {table}")
    finally:
        raw.autocommit = old
    after = table_size(conn, table)
    out = {"table_before_gb": round(before[0] / 2**30, 2), "table_after_gb": round(after[0] / 2**30, 2),
           "db_before_gb": round(before[1] / 2**30, 2), "db_after_gb": round(after[1] / 2**30, 2)}
    log(f"reclaim {table}: {json.dumps(out)}")
    return out


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("step", choices=("prepare", "upload", "remove", "run", "bulk", "reclaim",
                                     "status"))
    ap.add_argument("--table", choices=sorted(SPECS))
    ap.add_argument("--rule", choices=RULES, default="repeat")
    ap.add_argument("--date", help="ET game date, YYYY-MM-DD")
    ap.add_argument("--start", help="run: first ET game date")
    ap.add_argument("--end", help="run: last ET game date")
    ap.add_argument("--copy-db", default=DEFAULT_COPY_DB)
    ap.add_argument("--check", action="store_true",
                    help="prepare/run: also pick each game in Postgres now (heavy; quiet window)")
    ap.add_argument("--pending", action="store_true",
                    help="remove: every date with a stored copy, until the quiet window ends")
    ap.add_argument("--now", action="store_true",
                    help="remove: at any hour, waiting while an app read has run 2 s and "
                         "resting after each game as long as it took")
    ap.add_argument("--batch-rows", type=int, default=0,
                    help="remove: small games together, up to N archived rows a transaction")
    a = ap.parse_args(argv)
    from dotenv import load_dotenv
    load_dotenv(os.environ.get("ARCHIVE_ENV_FILE", DEFAULT_ENV), override=False)
    from data.db import get_connection
    conn = get_connection()
    now = dt.datetime.now(UTC)
    try:
        if a.step == "status":
            ensure_ledger(conn)
            for r in conn.execute("""
                SELECT table_name, rule, count(*), sum(rows), count(*) FILTER (WHERE stored_at IS NOT NULL),
                       count(*) FILTER (WHERE removed_at IS NOT NULL), coalesce(sum(removed_rows), 0)
                  FROM archive_batches GROUP BY 1, 2 ORDER BY 1, 2""").fetchall():
                print(json.dumps(dict(zip(("table", "rule", "games", "rows", "stored", "removed",
                                           "removed_rows"), r)), default=str))
            return 0
        if a.step == "reclaim":
            if not a.table:
                ap.error("--table is required")
            reclaim(conn, a.table)
            return 0
        if a.step == "run":
            if not (a.table and a.start and a.end):
                ap.error("--table, --start and --end are required")
            import duckdb
            copy = duckdb.connect(a.copy_db, read_only=True)
            print(json.dumps(run(copy, conn, a.table, a.rule, a.start, a.end, now,
                                 connect=get_connection, check=a.check)))
            return 0
        if a.step == "bulk":
            # prepare every date in [start, end] from one pass of the copy, then
            # upload each; removal stays its own step (remove --pending).
            if not (a.table and a.start and a.end):
                ap.error("--table, --start and --end are required")
            import duckdb
            copy = duckdb.connect(a.copy_db, read_only=True)
            p = prepare_range(copy, conn, a.table, a.rule, a.start, a.end, now)
            dates = [r[0] for r in conn.execute("""
                SELECT DISTINCT game_date FROM archive_batches
                 WHERE table_name = %s AND rule = %s AND stored_at IS NULL AND removed_at IS NULL
                   AND game_date BETWEEN %s AND %s ORDER BY 1""",
                (a.table, a.rule, a.start, a.end)).fetchall()]
            conn.rollback()
            for day in dates:
                upload(conn, a.table, a.rule, day)
            print(json.dumps({**p, "uploaded_dates": len(dates)}))
            return 0
        if a.step == "remove" and a.pending:
            if not a.table:
                ap.error("--table is required")
            # A dropped connection starts the pending list again on a new one
            # (games already removed are skipped); a timeout is never retried here.
            import psycopg2
            for attempt in range(1, DATE_ATTEMPTS + 1):
                try:
                    print(json.dumps(remove_pending(conn, a.table, a.rule, now, anytime=a.now,
                                                    batch_rows=a.batch_rows)))
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                    if is_timeout(exc) or attempt == DATE_ATTEMPTS:
                        raise
                    print(f"connection lost ({type(exc).__name__}); again on a new one", flush=True)
                    try:
                        conn.close()
                    except Exception:  # noqa: BLE001
                        pass
                    conn = get_connection()
            return 0
        if not (a.table and a.date):
            ap.error("--table and --date are required")
        if a.step in ("prepare", "remove"):
            check_allowed(a.table, a.rule)
        if a.step == "prepare":
            import duckdb
            copy = duckdb.connect(a.copy_db, read_only=True)
            prepare(copy, conn, a.table, a.rule, a.date, now, check=a.check)
        elif a.step == "upload":
            upload(conn, a.table, a.rule, a.date)
        else:
            remove(conn, a.table, a.rule, a.date, now, anytime=a.now, batch_rows=a.batch_rows)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
