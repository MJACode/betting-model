/**
 * The four all-books line reads DRAIN the server's row cap instead of
 * silently stopping at it.
 *
 * Run with:  npx tsx scripts/verify_row_cap.ts
 *
 * Supabase caps every PostgREST response at max-rows (1,000 here), whatever
 * .limit() asks for, and says nothing. On 2026-09-04 the Stats board asked for
 * 20,000 prop rows, got the first 1,000 of 1,912, and printed a DraftKings
 * line for the games that sorted first and a dash for the rest — Harper
 * priced, Betts / Perez / Santana blank, while DraftKings had posted all four
 * since the early morning. The Picks screen's line-shop read was truncated
 * the same way (14,580 rows on a full day).
 *
 * The executable half runs fetchAllPages against a fake server that enforces
 * the cap; the source half pins that every all-books read goes through it
 * with a deterministic order and no .limit().
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { fetchAllPages, PAGE_ROWS } from '../src/lib/paging';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

/** A PostgREST that holds `total` rows and never returns more than `cap`. */
function fakeServer(total: number, cap: number) {
  const calls: Array<[number, number]> = [];
  const page = (from: number, to: number) => {
    calls.push([from, to]);
    const end = Math.min(to + 1, from + cap, total);
    const data = [] as Array<{ i: number }>;
    for (let i = from; i < end; i++) data.push({ i });
    return Promise.resolve({ data, error: null });
  };
  return { page, calls };
}

async function main() {
  // ── executable ─────────────────────────────────────────────────────────────
  {
    const srv = fakeServer(1912, 1000);
    const rows = await fetchAllPages<{ i: number }>(srv.page);
    check('a 1,912-row read behind a 1,000 cap returns all 1,912 rows', rows.length === 1912, `${rows.length}`);
    check('rows come back in order with no repeats', rows.every((r, i) => r.i === i));
    check('it asked for a third (empty) page to prove the end', srv.calls.length === 3, `${srv.calls.length} calls`);
    check('each window is PAGE_ROWS wide', srv.calls.every(([f, t]) => t - f + 1 === PAGE_ROWS));
    check('the second window starts where the capped first one ended', srv.calls[1]?.[0] === 1000, `${srv.calls[1]?.[0]}`);
  }
  {
    // A cap SMALLER than the window: the short page must not read as the end.
    const srv = fakeServer(2500, 700);
    const rows = await fetchAllPages<{ i: number }>(srv.page);
    check('a cap below the window size still drains everything', rows.length === 2500, `${rows.length}`);
  }
  {
    const srv = fakeServer(0, 1000);
    const rows = await fetchAllPages<{ i: number }>(srv.page);
    check('an empty read is one call and no rows', rows.length === 0 && srv.calls.length === 1);
  }
  {
    let threw = false;
    try {
      await fetchAllPages(() => Promise.resolve({ data: null, error: new Error('57014') }));
    } catch {
      threw = true;
    }
    check('a page error rejects rather than returning a partial slate', threw);
  }

  // ── source ─────────────────────────────────────────────────────────────────
  const q = read('src/lib/queries.ts');
  const pg = read('src/lib/paging.ts');
  // Every read of the two views. A statement ends at the next line that opens
  // with `)`, `:` or `]` — the arrow's closing paren for a paged read, the
  // ternary / array continuation for the per-game ones in fetchPickDetail...
  const reads = [...q.matchAll(/\.from\('(v_latest_(?:prop_)?odds_all_books)'\)/g)].map((m) => {
    const at = m.index ?? 0;
    const after = q.slice(at);
    // ...or at the first `;`, which ends a plain one-statement read.
    const end = after.search(/;|\n\s*[):\]]/);
    return { view: m[1]!, at, before: q.slice(Math.max(0, at - 400), at), stmt: after.slice(0, end < 0 ? 600 : end) };
  });
  // SLATE reads return a whole day, a week, or every game with a signal, and
  // must page; per-GAME reads are a few dozen rows by construction and stay a
  // plain select.
  const isSlate = (stmt: string) => /\.(eq|gt|gte)\('game_date'|\.in\('game_id'/.test(stmt);
  const dated = reads.filter((r) => isSlate(r.stmt));
  const perGame = reads.filter((r) => !isSlate(r.stmt));
  check('seven slate all-books reads (Stats props, Teams lines, Picks x2, UFC / NFL / NCAAF windows)', dated.length === 7, `${dated.length}`);
  check('four per-game reads (the pick detail x2, the prop and game line-leg re-prices)', perGame.length === 4, `${perGame.length}`);
  // The Picks screen's two reads are bounded to the picks that render lines,
  // never the whole day (the 2026-09-04 UX review: 16 statements per mount).
  const picksReads = dated.filter((r) => r.stmt.includes(".in('game_id'"));
  check('the Picks screen bounds both reads to signal games', picksReads.length === 2, `${picksReads.length}`);
  check('its prop read is bounded to the signal players too', picksReads.some((r) => r.stmt.includes(".in('player_name'")));
  check('fetchAllPages drops page-seam repeats when given a key', /seen\.has\(k\)/.test(pg));
  for (const r of dated) {
    check(`${r.view} @${r.at}: inside fetchAllPages`, r.before.includes('fetchAllPages<'));
    check(`${r.view} @${r.at}: pages with .range(from, to)`, r.stmt.includes('.range(from, to)'));
    check(`${r.view} @${r.at}: deterministic order for paging`, r.stmt.includes(".order('game_id')") && r.stmt.includes(".order('bookmaker')"));
    check(`${r.view} @${r.at}: no .limit() to be capped`, !r.stmt.includes('.limit('));
  }
  for (const r of perGame) {
    check(`${r.view} @${r.at}: per-game read is bounded to one game_id`, r.stmt.includes(".eq('game_id'"));
    check(`${r.view} @${r.at}: per-game read asks for no cap-sized limit`, !/\.limit\((\d{4,})\)/.test(r.stmt));
  }
  check('fetchAllPages stops only on an EMPTY page, never a short one',
    /if \(rows\.length === 0\) break;/.test(pg) && !/rows\.length < PAGE_ROWS/.test(pg));
  check('fetchAllPages advances by what came back, not by the window',
    /from \+= rows\.length;/.test(pg));

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILED`);
  process.exit(failures === 0 ? 0 : 1);
}

void main();
