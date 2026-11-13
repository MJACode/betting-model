"""A paged read retries a statement timeout once, and only a timeout.

2026-10-31 (Matt): the Stats board showed "Couldn't load the board" on every
first open. Edge logs showed the first page of player_recent_games_nba fail
with 500 / 57014 and the same request succeed right after. fetchAllPages now
asks for a timed-out page once more before failing.

Runs mobile/src/lib/paging.ts directly under Node's type stripping, so it
needs no node_modules.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGING = ROOT / "mobile" / "src" / "lib" / "paging.ts"

SCRIPT = r"""
import { fetchAllPages, isStatementTimeout } from '%(paging)s';
const fail = (m) => { console.error(m); process.exit(1); };
const timeout = { code: '57014', message: 'canceling statement due to statement timeout' };

// 1. A timeout on the first page, then success: the read returns every row.
{
  let calls = 0;
  const rows = await fetchAllPages((from) => {
    calls++;
    if (calls === 1) return Promise.resolve({ data: null, error: timeout });
    return Promise.resolve({ data: from === 0 ? [1, 2, 3] : [], error: null });
  });
  if (rows.length !== 3) fail('retry did not return the rows: ' + JSON.stringify(rows));
  if (calls !== 3) fail('expected 3 calls (timeout, page, empty), got ' + calls);
}

// 2. Two timeouts in a row: the read fails, after exactly one retry.
{
  let calls = 0;
  let threw = null;
  try {
    await fetchAllPages(() => { calls++; return Promise.resolve({ data: null, error: timeout }); });
  } catch (e) { threw = e; }
  if (threw !== timeout) fail('a second timeout must reach the caller');
  if (calls !== 2) fail('expected 2 calls, got ' + calls);
}

// 2b. One retry per read: a timeout on page 1 and again on page 2 fails.
{
  let calls = 0;
  let threw = null;
  try {
    await fetchAllPages((from) => {
      calls++;
      if (calls === 1 || calls === 3) return Promise.resolve({ data: null, error: timeout });
      return Promise.resolve({ data: from === 0 ? Array(1000).fill(0) : [1], error: null });
    });
  } catch (e) { threw = e; }
  if (threw !== timeout || calls !== 3) fail('retried more than once per read: ' + calls);
}

// 3. Any other error is not retried.
{
  let calls = 0;
  const other = { code: 'PGRST002', message: 'schema cache' };
  let threw = null;
  try {
    await fetchAllPages(() => { calls++; return Promise.resolve({ data: null, error: other }); });
  } catch (e) { threw = e; }
  if (threw !== other || calls !== 1) fail('a non-timeout error was retried: ' + calls);
}

if (!isStatementTimeout({ message: 'canceling statement due to statement timeout' })) fail('message form');
if (isStatementTimeout(null) || isStatementTimeout('57014')) fail('non-objects');
console.log('ok');
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_fetch_all_pages_retries_a_statement_timeout_once(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(SCRIPT % {"paging": PAGING.as_uri()}, encoding="utf-8")
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--no-warnings", str(script)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stdout.strip() == "ok"


def test_season_index_migration_is_active_and_guarded():
    from data.view_migrations import ACTIVE_MIGRATIONS

    name = "nba_wnba_game_log_season_index_2026_10_31.sql"
    assert name in ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / name).read_text(encoding="utf-8")
    # DDL only when the index is missing: a CREATE INDEX on every pass takes a
    # SHARE lock and forces a PostgREST schema reload (.claude/rules/operations.md).
    assert sql.count("to_regclass('public.idx_nba_plog_season_player') IS NULL") == 1
    assert sql.count("to_regclass('public.idx_wnba_plog_season_player') IS NULL") == 1
