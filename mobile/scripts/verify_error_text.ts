/**
 * Standalone verification for errorText (src/lib/errors.ts). Run with:
 *
 *   npx tsx scripts/verify_error_text.ts
 *
 * WHY: supabase-js does not throw — it returns `{ data, error }` and every
 * query helper in this app re-throws that plain object. `String(e)` on a plain
 * object is "[object Object]", which is what the Stats tab actually showed
 * users on 2026-09-01 while PostgREST answered 503 to every leaderboard RPC:
 *
 *     Connection error: [object Object]
 *
 * Pins: a PostgrestError renders its message (and code); an Error still wins;
 * a string passes through; and NOTHING ever renders as "[object Object]".
 */

import { errorText } from '../src/lib/errors';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── the actual bug: a PostgrestError is a plain object, not an Error ──
const pgrst = {
  message: 'Could not query the database for the schema cache',
  details: null,
  hint: null,
  code: 'PGRST002',
};
const rendered = errorText(pgrst);
check('PostgrestError renders its message', rendered.includes('schema cache'), rendered);
check('PostgrestError renders its code', rendered.includes('PGRST002'), rendered);
check('PostgrestError is never [object Object]', rendered !== '[object Object]', rendered);

// The 500 half of the same outage: a cancelled statement.
const timeout = { message: 'canceling statement due to statement timeout', code: '57014' };
check('statement timeout renders', errorText(timeout).includes('timeout'), errorText(timeout));

// ── every other shape a catch block can receive ──
check('Error keeps its message', errorText(new Error('boom')) === 'boom');
check('string passes through', errorText('plain failure') === 'plain failure');
check('null falls back', errorText(null) === 'Something went wrong');
check('undefined falls back', errorText(undefined) === 'Something went wrong');
check('custom fallback is used', errorText(null, 'Try again') === 'Try again');
check('empty Error message falls back', errorText(new Error('')) === 'Something went wrong');
check('message-only object', errorText({ message: 'no code here' }) === 'no code here');
check('code-only object', errorText({ code: '42501' }) === '42501');
check('details when message is absent', errorText({ details: 'row not found' }) === 'row not found');

// A featureless object is the one that used to produce "[object Object]".
const bare = errorText({ status: 503 });
check('featureless object falls back, not [object Object]',
  bare === 'Something went wrong', bare);

// ── the invariant, over every shape at once ──
const shapes: unknown[] = [
  pgrst, timeout, new Error('x'), 'str', null, undefined, 0, false, [],
  {}, { status: 503 }, { message: '' }, { message: '   ' }, new Date(),
];
const bad = shapes.filter((s) => errorText(s) === '[object Object]');
check('no shape renders as [object Object]', bad.length === 0, JSON.stringify(bad));
const blank = shapes.filter((s) => errorText(s).trim() === '');
check('no shape renders blank', blank.length === 0, JSON.stringify(blank));

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
