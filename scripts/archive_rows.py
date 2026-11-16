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
          measured on the PC copy 2026-11-16.
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

THE FINGERPRINT. Per row, md5 of the row's columns as text (numbers as
round(x * 1e6), times as text), first 15 hex digits as an integer, summed over
the rows. Postgres and DuckDB compute it alike: measured 2026-11-16 on 199,991
`picks_log` rows, both gave 115382440917824267217252.

    python scripts/archive_rows.py prepare --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py upload  --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py remove  --table player_prop_odds --rule repeat --date 2026-10-20
    python scripts/archive_rows.py run     --table player_prop_odds --rule repeat --start 2026-03-01 --end 2026-11-12
    python scripts/archive_rows.py reclaim --table player_prop_odds      # quiet window only
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
    ("odds", "repeat"): "features/market_movement.py counts DraftKings snapshots per past game "
                        "(mkt_snapshots) and scripts/build_nba_live_ig2_artifact.py groups rows "
                        "by fetch; both train on past games from Postgres",
    ("odds", "old"): "the Teams board, CLV's same-line close, BYOM, the line charts and "
                     "team_period_results read mid-path rows of old games",
    ("player_prop_odds", "old"): "the line charts, the NHL player prop view and BYOM prop facts read "
                                 "lines that are neither opener nor close",
}
SERVER_GAMES_PER_STATEMENT = 3
STATEMENT_TIMEOUT = "300s"
ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc

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


SPECS = {
    "odds": Spec(
        "odds", "odds_id", ("game_id", "market", "bookmaker"),
        ("home_price", "away_price", "draw_price", "spread_home", "total_line",
         "over_price", "under_price"),
        ("game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "source"),
        "CASE t.market WHEN 'alternate_spreads' THEN t.spread_home "
        "WHEN 'alternate_totals' THEN t.total_line END",
        "CASE t.market WHEN 'alternate_spreads' THEN t.spread_home "
        "WHEN 'alternate_totals' THEN t.total_line END"),
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


def rule_sql(spec: Spec, rule: str, d: Dialect) -> str:
    """SELECT pk, h, game_id for the rows of the given games the rule moves.
    Parameters, in order: the game ids, the min-age cutoff, and for 'old' the
    old cutoff (all UTC epoch seconds for DuckDB, timestamps for Postgres)."""
    if rule not in RULES:
        raise ValueError(f"unknown rule {rule!r}")
    p = d.param()
    cut = (lambda x: f"to_timestamp({x})") if not d.pg else (lambda x: f"{x}::timestamptz")
    key = ", ".join(spec.key)
    rung = spec.rung_pg if d.pg else spec.rung_dk
    lags = ",\n           ".join(f"lag({c}) OVER w AS lag_{c}" for c in spec.values)
    same = " AND ".join(f"{c} IS NOT DISTINCT FROM lag_{c}" for c in spec.values)
    old = f"start < {cut(p)}" if rule == "old" else "FALSE"
    return f"""
WITH g AS (
  SELECT game_id, {d.ts('commence_time')} AS start FROM games WHERE game_id {d.games()}),
r0 AS (
  SELECT t.*, g.start, {d.ts('t.snapshot_at')} AS ts, {rung} AS rung
    FROM {spec.table} t JOIN g ON g.game_id = t.game_id),
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
"""


def cutoffs(now: dt.datetime) -> tuple[dt.datetime, dt.datetime]:
    return now - dt.timedelta(days=MIN_AGE_DAYS), now - dt.timedelta(days=OLD_DAYS)


def _params(d: Dialect, rule: str, games, now: dt.datetime) -> list:
    min_cut, old_cut = cutoffs(now)
    if d.pg:
        out = [list(games), min_cut]
        return out + [old_cut] if rule == "old" else out
    out = [list(games), min_cut.timestamp()]
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


def server_selection(conn, spec: Spec, rule: str, games, now: dt.datetime) -> dict:
    """{game_id: (rows, checksum)} by the rule, in Postgres, read-only."""
    if not games:
        return {}
    d = Dialect("pg")
    sql = (f"SELECT game_id, count(*), sum(h)::text FROM ({rule_sql(spec, rule, d)}) s "
           f"GROUP BY game_id")
    out = {}
    games = list(games)
    # A few games a statement: all 23 games of 2026-11-08 in one statement ran
    # into the database's statement timeout; 3 took 4 s.
    for i in range(0, len(games), SERVER_GAMES_PER_STATEMENT):
        part = games[i:i + SERVER_GAMES_PER_STATEMENT]
        conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
        rows = conn.execute(sql, tuple(_params(d, rule, part, now))).fetchall()
        conn.rollback()
        out.update({g: (int(n), int(c)) for g, n, c in rows})
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


def upload_and_check(path: Path, obj: str) -> str:
    """Upload, download again, compare bytes. Returns the file's sha256."""
    s, base = _storage()
    ensure_bucket(s, base)
    want = sha256(path)
    with open(path, "rb") as fh:
        r = s.post(f"{base}/storage/v1/object/{BUCKET}/{obj}", data=fh, timeout=600,
                   headers={"content-type": "application/octet-stream", "x-upsert": "true"})
    if r.status_code not in (200, 201):
        raise RuntimeError(f"upload of {obj} failed: HTTP {r.status_code} {r.text[:200]}")
    got = s.get(f"{base}/storage/v1/object/{BUCKET}/{obj}", timeout=600)
    if got.status_code != 200 or hashlib.sha256(got.content).hexdigest() != want:
        raise RuntimeError(f"{obj}: the copy read back from Storage differs from the file")
    return want


def remove_game(conn, spec: Spec, rule: str, game: str, want: tuple[int, int],
                now: dt.datetime) -> int:
    """Remove one game's rows, only if Postgres picks exactly the archived set."""
    d = Dialect("pg")
    sel = rule_sql(spec, rule, d)
    params = tuple(_params(d, rule, [game], now))
    try:
        conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
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


# ── Steps ────────────────────────────────────────────────────────────────────

def prepare(copy, conn, table: str, rule: str, date: str, now: dt.datetime, log=print) -> dict:
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
    theirs = server_selection(conn, spec, rule, list(mine), now)
    ensure_ledger(conn)
    for g, (n, c) in sorted(mine.items()):
        ok = theirs.get(g) == (n, c)
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
    log(f"prepare {table} {rule} {date}: {out['rows']:,} rows in {out['with_rows']} games; "
        f"{out['ready']} match Postgres, {len(out['refused'])} refused")
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


def remove(conn, table: str, rule: str, date: str, now: dt.datetime, log=print) -> dict:
    spec = SPECS[table]
    path = file_path(table, rule, date)
    back = file_selection(spec, path)
    rows = conn.execute("""
        SELECT batch_key, rows, checksum, file_sha256, stored_at, removed_at, note
          FROM archive_batches WHERE table_name = %s AND rule = %s AND game_date = %s""",
        (table, rule, date)).fetchall()
    conn.rollback()
    digest = sha256(path)
    out = {"removed": 0, "games": 0, "skipped": []}
    for g, n, c, fsha, stored, removed_at, note in rows:
        if removed_at is not None:
            continue
        if stored is None or fsha != digest:
            out["skipped"].append((g, "no verified Storage copy of this file"))
            continue
        if note or back.get(g) != (int(n), int(c)):
            out["skipped"].append((g, note or "file does not hold the ledger's rows"))
            continue
        try:
            out["removed"] += remove_game(conn, spec, rule, g, (int(n), int(c)), now)
            out["games"] += 1
        except RuntimeError as exc:
            out["skipped"].append((g, str(exc)))
    log(f"remove {table} {rule} {date}: {out['removed']:,} rows from {out['games']} games; "
        f"{len(out['skipped'])} skipped")
    return out


def check_allowed(table: str, rule: str) -> None:
    if (table, rule) not in ALLOWED:
        raise SystemExit(f"{table} {rule} may not move yet: "
                         f"{REFUSED.get((table, rule), 'not reviewed')}")


def run(copy, conn, table: str, rule: str, start: str, end: str, now: dt.datetime,
        log=print) -> dict:
    """Every ET game date in [start, end]: prepare, then upload and remove when
    the Storage copy can be made. Without the key it prepares only."""
    check_allowed(table, rule)
    try:
        _storage()
        can_store = True
    except RuntimeError as exc:
        can_store = False
        log(f"Storage: {exc}")
    d = dt.date.fromisoformat(start)
    out = {"dates": 0, "prepared_rows": 0, "removed_rows": 0, "refused_games": 0}
    while d <= dt.date.fromisoformat(end):
        p = prepare(copy, conn, table, rule, d.isoformat(), now, log)
        out["dates"] += 1
        out["prepared_rows"] += p["rows"]
        out["refused_games"] += len(p["refused"])
        if can_store and p["ready"]:
            upload(conn, table, rule, d.isoformat(), log)
            out["removed_rows"] += remove(conn, table, rule, d.isoformat(), now, log)["removed"]
        d += dt.timedelta(days=1)
    return out


def table_size(conn, table: str) -> tuple[int, int]:
    n = conn.execute("SELECT pg_total_relation_size(%s::regclass), pg_database_size(current_database())",
                     (table,)).fetchone()
    conn.rollback()
    return int(n[0]), int(n[1])


def reclaim(conn, table: str, log=print) -> dict:
    """Rewrite the table so the removed rows' space comes back (VACUUM FULL).
    It locks the table while it runs, so it belongs in the quiet window, and it
    needs free disk the size of what is kept."""
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
    ap.add_argument("step", choices=("prepare", "upload", "remove", "run", "reclaim", "status"))
    ap.add_argument("--table", choices=sorted(SPECS))
    ap.add_argument("--rule", choices=RULES, default="repeat")
    ap.add_argument("--date", help="ET game date, YYYY-MM-DD")
    ap.add_argument("--start", help="run: first ET game date")
    ap.add_argument("--end", help="run: last ET game date")
    ap.add_argument("--copy-db", default=DEFAULT_COPY_DB)
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
            print(json.dumps(run(copy, conn, a.table, a.rule, a.start, a.end, now)))
            return 0
        if not (a.table and a.date):
            ap.error("--table and --date are required")
        if a.step in ("prepare", "remove"):
            check_allowed(a.table, a.rule)
        if a.step == "prepare":
            import duckdb
            copy = duckdb.connect(a.copy_db, read_only=True)
            prepare(copy, conn, a.table, a.rule, a.date, now)
        elif a.step == "upload":
            upload(conn, a.table, a.rule, a.date)
        else:
            remove(conn, a.table, a.rule, a.date, now)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
