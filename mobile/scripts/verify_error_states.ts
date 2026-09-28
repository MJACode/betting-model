/**
 * Error, empty and loading states — usability audit PR 2 (2026-09-25: H3, M1,
 * M2, M12, L11 and reduce-motion skeletons).
 *
 *   npx tsx scripts/verify_error_states.ts
 *
 * Pins:
 *   - friendlyError / friendlyCause sort a failure into offline / slow / auth /
 *     server and NEVER echo the raw Supabase text or "[object Object]";
 *   - no screen renders a raw error inside <Text> (`{error}`, `errorText(…)`,
 *     `.message`, "Connection error:"), except SignIn's auth copy;
 *   - ErrorState / ErrorBanner: avoidInk icon (never the bright `avoid`),
 *     role alert, a 44pt Retry, announced once;
 *   - skeletons hold still under Reduce Motion;
 *   - each screen that loads remotely uses ErrorState / ErrorBanner;
 *   - PicksHome says "No picks match" when only the search emptied the list,
 *     and a vanished pick offers "Open Picks" (L11).
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { errorKind, friendlyCause, friendlyError } from '../src/lib/errors';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

// ── friendlyError mapping ───────────────────────────────────────────────────
const cases: [unknown, string][] = [
  [new TypeError('Network request failed'), 'offline'],
  ['TypeError: Failed to fetch', 'offline'],
  [{ message: 'canceling statement due to statement timeout', code: '57014' }, 'slow'],
  [{ message: 'JWT expired', code: 'PGRST301' }, 'auth'],
  [{ message: 'Could not query the database for the schema cache', code: 'PGRST002' }, 'server'],
  [{}, 'server'],
  [null, 'server'],
];
for (const [e, kind] of cases) {
  const got = errorKind(e);
  check(`errorKind(${JSON.stringify(e instanceof Error ? e.message : e)}) = ${kind}`, got === kind, got);
}
const raw = { message: 'relation "picks" does not exist', code: '42P01' };
const f = friendlyError(raw, 'today’s MLB picks');
check('title names the thing', f.title === 'Couldn’t load today’s MLB picks', f.title);
check('raw text never reaches the copy', !/relation|42P01|picks" does/.test(f.title + f.cause), f.cause);
check('no [object Object] in the copy', !/object Object/.test(friendlyCause({}) + friendlyError({}, 'x').title));
check('every cause is one sentence ending in a full stop',
  ['offline', 'slow', 'auth', 'server'].every((k) => {
    const c = friendlyCause(k === 'offline' ? 'offline' : k === 'slow' ? 'timeout' : k === 'auth' ? 'JWT expired' : 'boom');
    return /^[A-Z].*\.$/.test(c);
  }));

// ── no raw error rendered in <Text> ─────────────────────────────────────────
function walk(dir: string, out: string[] = []): string[] {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (p.endsWith('.tsx')) out.push(p);
  }
  return out;
}
const RAW_IN_TEXT = /\{\s*(?:\w+\.)*(?:error|err|e|\w+Error)(?:\.message)?\s*\}|errorText\(|\.message\b|Connection error/;
export function rawErrorSites(src: string): number[] {
  const lines: number[] = [];
  for (const m of src.matchAll(/<Text\b[^>]*>([\s\S]*?)<\/Text>/g)) {
    if (RAW_IN_TEXT.test(m[1])) lines.push(src.slice(0, m.index).split('\n').length);
  }
  return lines;
}
check('probe: the scanner catches a raw {error}', rawErrorSites('<Text style={s.e}>Couldn’t load: {error}</Text>').length === 1);
check('probe: the scanner catches errorText(e)', rawErrorSites('<Text>\n  {errorText(e)}\n</Text>').length === 1);
check('probe: the scanner passes friendly copy', rawErrorSites('<Text>{friendlyCause(error)}</Text>').length === 0);
const ALLOW = new Set(['src/screens/SignInScreen.tsx']); // auth form: the message IS the instruction
const hits: string[] = [];
for (const p of walk(join(ROOT, 'src'))) {
  const rel = relative(ROOT, p);
  if (ALLOW.has(rel)) continue;
  for (const l of rawErrorSites(readFileSync(p, 'utf-8'))) hits.push(`${rel}:${l}`);
}
check('no raw error text rendered anywhere', hits.length === 0, hits.join(', '));

// ── ErrorState / ErrorBanner / Skeleton wiring ──────────────────────────────
const es = read('src/components/ErrorState.tsx');
check('ErrorState icons are avoidInk', (es.match(/color=\{colors\.avoidInk\}/g) ?? []).length === 2);
check('ErrorState never uses the bright avoid', !/colors\.avoid\b(?!Ink|Soft)/.test(es));
check('ErrorState/ErrorBanner role alert', (es.match(/accessibilityRole="alert"/g) ?? []).length === 2);
check('both Retry buttons are 44pt', (es.match(/minHeight: 44/g) ?? []).length >= 2);
check('announced for VoiceOver', /announceForAccessibility/.test(es));
check('copy comes from friendlyError', /friendlyError\(error, what\)/.test(es));
const sk = read('src/components/Skeleton.tsx');
check('Skeleton reads Reduce Motion', /useReduceMotion\(\)/.test(sk));
check('useReduceMotion starts still', /useState\(true\)/.test(read('src/hooks/useReduceMotion.ts')));

const USERS: Record<string, RegExp> = {
  'src/screens/PicksHomeScreen.tsx': /<ErrorState\b[\s\S]*<ErrorBanner\b|<ErrorBanner\b[\s\S]*<ErrorState\b/,
  'src/screens/TrackRecordScreen.tsx': /<ErrorState\b/,
  'src/screens/ModelsScreen.tsx': /<ErrorState\b[\s\S]*|<ErrorBanner\b/,
  'src/screens/PickDetailScreen.tsx': /<ErrorState\b/,
  'src/screens/ParlayScreen.tsx': /<ErrorBanner\b/,
  'src/screens/TeamStatsScreen.tsx': /<ErrorBanner\b/,
  'src/screens/PlayerStatsScreen.tsx': /<ErrorBanner\b/,
  'src/screens/ModelDetailScreen.tsx': /<ErrorBanner\b/,
  'src/screens/BuiltInModelDetailScreen.tsx': /<ErrorBanner\b/,
  'src/screens/OpeningComparisonScreen.tsx': /<ErrorBanner\b/,
  'src/components/TeamsBoard.tsx': /<ErrorBanner\b/,
};
for (const [p, re] of Object.entries(USERS)) check(`${p.split('/').pop()} uses the shared error state`, re.test(read(p)));
const models = read('src/screens/ModelsScreen.tsx');
check('Models: no zero cards while loading or failed (H3)', /<Skeleton\b/.test(models) && /<ErrorState\b/.test(models));
const home = read('src/screens/PicksHomeScreen.tsx');
check('PicksHome: search-emptied copy (M12)', /No picks match/.test(home) && /emptiedBySearch/.test(home) && /Clear search/.test(home));
check('PicksHome: prices-unavailable banner (M2)', /pricesUnavailable/.test(home));
check('PickDetail: vanished pick → Open Picks (L11)', /Open Picks/.test(read('src/screens/PickDetailScreen.tsx')));

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);
