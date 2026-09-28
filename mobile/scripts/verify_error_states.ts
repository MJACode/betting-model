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
 *
 * Behavioural (Reviewer, #845 — these RUN the logic, not scan for it):
 *   - isAbortError: an intentional cancel is silent, never "You're offline";
 *     errorKind's offline / slow patterns are narrow;
 *   - lib/loadState: ErrorState vs ErrorBanner, "—" on a failed count, the
 *     Models Custom-tab failure, and the live-prices banner (pricesUnavailable);
 *   - errorAnnouncement reads the Designer's reassurance line after the cause.
 *
 * Designer review fixes (#845, at 1cfc1652, re-verified on f815347b):
 *   - L11: fetchPickById reads with .maybeSingle(); a missing pick (null, or a
 *     PGRST116 that still arrives) is PickDetail's not-found / "Open Picks"
 *     state, never an ErrorState whose Retry can't succeed;
 *   - no fake zeros: counts are "—" until the FIRST SUCCESSFUL load (loading,
 *     slow and failed first loads alike), then real — a successful empty load
 *     is a real 0;
 *   - sport chips are neutral while the board is unknown: nothing muted, no
 *     "no picks today";
 *   - a repeat identical failure after a pressed Retry is announced again;
 *     ErrorState, ErrorBanner and the M2 banner are polite live regions.
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';

import { errorAnnouncement, errorKind, friendlyCause, friendlyError, isAbortError, isNotFoundError } from '../src/lib/errors';
import {
  countLabel,
  countsKnown,
  detailPresentation,
  enrichmentTracker,
  errorSurface,
  knownCount,
  loadPresentation,
  repeatFailureAnnounce,
  showLivePricesBanner,
  sportChipState,
  sportChipsAvailable,
  todayHeaderCounts,
} from '../src/lib/loadState';

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
    const c = friendlyCause(k === 'offline' ? 'Failed to fetch' : k === 'slow' ? 'statement timeout' : k === 'auth' ? 'JWT expired' : 'boom');
    return /^[A-Z].*\.$/.test(c);
  }));

// ── aborts are silent; offline / slow are narrow (Reviewer MEDIUM 2) ───────
const abort = Object.assign(new Error('The operation was aborted.'), { name: 'AbortError' });
const aborts: unknown[] = [
  abort,
  { name: 'AbortError', message: 'signal is aborted without reason' },
  'AbortError: The user aborted a request.',
  'The operation was aborted.',
  'signal is aborted without reason',
  'Aborted',
  { code: 20, message: 'x' },
];
for (const e of aborts) check(`isAbortError(${JSON.stringify(e instanceof Error ? e.name : e)})`, isAbortError(e));
const notAborts: unknown[] = [
  new TypeError('Network request failed'),
  'TypeError: Failed to fetch',
  { message: 'canceling statement due to statement timeout', code: '57014' },
  null,
  '',
  'Season aborted early for the franchise',
];
for (const e of notAborts) check(`not an abort: ${JSON.stringify(e instanceof Error ? e.message : e)}`, !isAbortError(e));
check('an abort never reads as offline or slow', aborts.every((e) => !['offline', 'slow'].includes(errorKind(e))));
const narrow: [unknown, string][] = [
  ['Load failed', 'offline'], // Safari's fetch TypeError, exactly
  ['TypeError: Load failed', 'offline'],
  ['ENOTFOUND api.signalbase', 'offline'],
  ['Gateway Timeout', 'slow'],
  ['connect ETIMEDOUT 1.2.3.4:443', 'slow'],
  ['Image load failed for logo', 'server'], // a bare "load failed" is not offline
  ['timeout_ms must be positive', 'server'], // a bare "timeout" is not slow
  ['offline_mode column missing', 'server'], // nor a bare "offline"
  ['internet_explorer flag', 'server'],
];
for (const [e, kind] of narrow) check(`narrow: errorKind(${JSON.stringify(e)}) = ${kind}`, errorKind(e) === kind, errorKind(e));

// ── lib/loadState: ErrorState vs ErrorBanner, "—", Custom tab, M2 ──────────
const P = (loading: boolean, error: unknown, hasData: boolean) => loadPresentation({ loading, error, hasData });
check('first load, nothing yet → skeleton', P(true, null, false).body === 'skeleton' && !P(true, null, false).banner);
check('failed first load → ErrorState, no banner', P(false, 'Failed to fetch', false).body === 'error' && !P(false, 'x', false).banner);
check('failed refresh over rows → rows kept + ErrorBanner', P(false, 'x', true).body === 'content' && P(false, 'x', true).banner);
check('ErrorState and ErrorBanner never stack',
  [true, false].every((l) => [null, 'x'].every((e) => [true, false].every((d) => {
    const p = P(l, e, d);
    return !(p.body === 'error' && p.banner);
  }))));
check('loaded and empty → content (the empty state), not an error', P(false, null, false).body === 'content');
check('an aborted load → no ErrorState, no banner', P(false, abort, false).body === 'content' && !P(false, abort, true).banner);
const failedCold = { loading: false, error: 'Failed to fetch', hasData: false };
check('Models Built-in: a failed first load is the list’s ErrorState', errorSurface(failedCold, true) === 'state');
check('Models Custom: a failed first load is a BANNER, never silence (MEDIUM 1)', errorSurface(failedCold, false) === 'banner');
check('Models Custom: a failed refresh is a banner too', errorSurface({ ...failedCold, hasData: true }, false) === 'banner');
check('Models: no error → no surface on either tab', errorSurface({ ...failedCold, error: null }, false) === 'none' && errorSurface({ ...failedCold, error: null }, true) === 'none');
check('Models Custom: an abort is silent', errorSurface({ ...failedCold, error: abort }, false) === 'none');
check('"—" when the count never loaded', countLabel(knownCount(0, { loaded: false, error: 'x', hasData: false })) === '—');
check('a real zero stays 0 (a successful empty load)', countLabel(knownCount(0, { loaded: true, error: null, hasData: false })) === '0');
check('rows on screen keep their count through a failed refresh', countLabel(knownCount(7, { loaded: true, error: 'x', hasData: true })) === '7');
const live = { view: 'live', liveError: null, pricesUnavailable: true, liveCount: 3 };
check('M2: prices-unavailable banner over live rows', showLivePricesBanner(live));
check('M2: not on another view', !showLivePricesBanner({ ...live, view: 'today' }));
check('M2: not over an empty board', !showLivePricesBanner({ ...live, liveCount: 0 }));
check('M2: not on top of a whole-load failure', !showLivePricesBanner({ ...live, liveError: 'x' }));
check('M2: not when prices loaded', !showLivePricesBanner({ ...live, pricesUnavailable: false }));
const t1 = enrichmentTracker();
check('M2: a clean fetch → pricesUnavailable false', t1.missed === false);
t1.onError('live odds', new Error('boom'));
check('M2: one failed live-price read → pricesUnavailable true', t1.missed === true);
const t2 = enrichmentTracker();
t2.onError('live odds', abort);
check('M2: an aborted read is not a miss', t2.missed === false);

// ── Designer review fixes (#845) — RUN, not scanned ─────────────────────────
// L11: not-found is an answer, not a failure.
check('L11: PGRST116 (object) is not-found', isNotFoundError({ code: 'PGRST116', message: 'JSON object requested, multiple (or no) rows returned' }));
check('L11: PGRST116 kept as errorText string is not-found', isNotFoundError('JSON object requested, multiple (or no) rows returned (PGRST116)'));
check('L11: a timeout / offline / null is NOT not-found',
  [{ code: '57014', message: 'statement timeout' }, 'Failed to fetch', null, '', { code: 'PGRST301' }].every((e) => !isNotFoundError(e)));
const D = (loading: boolean, error: unknown, found: boolean) => detailPresentation({ loading, error, found });
check('L11: a missing pick (no row, no error) → notFound ("Open Picks")', D(false, null, false) === 'notFound');
check('L11: a PGRST116 that still arrives → notFound, not the ErrorState', D(false, { code: 'PGRST116' }, false) === 'notFound' && D(false, 'x (PGRST116)', false) === 'notFound');
check('L11: a real failure → ErrorState (Retry)', D(false, 'Failed to fetch', false) === 'error');
check('L11: loading → spinner; a row → content', D(true, null, false) === 'loading' && D(false, null, true) === 'content');
check('L11: an abort is not an ErrorState', D(false, abort, false) === 'notFound' || D(false, abort, false) === 'content');
const queries = read('src/lib/queries.ts');
const fetchPickById = queries.match(/export async function fetchPickById[\s\S]*?\n}\n/)?.[0] ?? '';
export function singleRowRead(fn: string): boolean {
  return /\.maybeSingle\(\)/.test(fn) && !/\.single\(\)/.test(fn);
}
check('probe: the .single() pin catches a revert', !singleRowRead(fetchPickById.replace('.maybeSingle()', '.single()')));
check('L11: fetchPickById reads with .maybeSingle(), never .single()', fetchPickById.length > 0 && singleRowRead(fetchPickById), fetchPickById.slice(0, 80));
check('L11: fetchPickById lets not-found through as null', /if \(error && !isNotFoundError\(error\)\) throw error;\s*if \(!data\) return null;/.test(fetchPickById));
check('L11: no detail read in queries.ts uses .single() (0 rows would be a 406)', !/\.single\(\)/.test(queries));
const pdSrc = read('src/screens/PickDetailScreen.tsx');
check('L11: PickDetail branches on detailPresentation', /detailPresentation\(\{ loading, error, found: data != null \}\)/.test(pdSrc)
  && /body === 'error'/.test(pdSrc) && /body === 'notFound'/.test(pdSrc));
check('L11: PickDetail maps a caught PGRST116 to not-found', /if \(isNotFoundError\(e\)\) setData\(null\);/.test(pdSrc));

// No fake zeros: unknown until the first SUCCESSFUL load.
const K = (loaded: boolean, error: unknown, hasData: boolean) => countsKnown({ loaded, error, hasData });
check('zeros: first load in flight (or slow) → unknown, not 0', !K(false, null, false) && countLabel(knownCount(0, { loaded: false, error: null, hasData: false })) === '—');
check('zeros: failed first load → unknown', !K(false, 'Failed to fetch', false));
check('zeros: aborted first load (no error kept, never loaded) → unknown', !K(false, null, false));
check('zeros: a successful empty load → a real 0', K(true, null, false));
check('zeros: a refresh after a successful load stays known (no flicker to —)', K(true, null, false));
check('zeros: a failed refresh with nothing on screen → unknown', !K(true, 'x', false));
check('zeros: rows on screen → known', K(false, null, true) && K(true, 'x', true));
check('header: "—" bets / scored until known',
  todayHeaderCounts({ date: 'Sep 28', known: false, bet: 0, total: 0, paused: 0 }) === 'Sep 28 · — bets · — scored');
check('header: real counts once known',
  todayHeaderCounts({ date: 'Sep 28', known: true, bet: 0, total: 0, paused: 0 }) === 'Sep 28 · 0 bets · 0 scored'
  && todayHeaderCounts({ date: 'Sep 28', known: true, bet: 3, total: 12, paused: 2 }) === 'Sep 28 · 3 bets · 12 scored · 2 paused');

// Sport chips: neutral while unknown.
const empty = new Set<string>();
const unknownChips = sportChipsAvailable(empty, false);
check('chips: unknown board → no availability set (neutral)', unknownChips === undefined);
const nfl = sportChipState({ sport: 'NFL', active: false, available: unknownChips, count: 0, live: false });
check('chips: unknown → NFL not muted, no "no picks today"', !nfl.muted && nfl.label === 'NFL', nfl.label);
const known = sportChipState({ sport: 'NFL', active: false, available: sportChipsAvailable(empty, true), count: 0, live: false });
check('chips: known and empty → muted, "NFL, no picks today"', known.muted && known.label === 'NFL, no picks today', known.label);
check('chips: a sport with picks is never muted',
  !sportChipState({ sport: 'MLB', active: false, available: new Set(['MLB']), count: 2, live: true }).muted
  && sportChipState({ sport: 'MLB', active: false, available: new Set(['MLB']), count: 2, live: true }).label === 'MLB, 2 signals, in play now');
check('chips: the active sport is never muted', !sportChipState({ sport: 'NFL', active: true, available: empty, count: 0, live: false }).muted);

// (a) A repeat identical failure after a pressed Retry is announced again.
const R = (o: Partial<Parameters<typeof repeatFailureAnnounce>[0]>) =>
  repeatFailureAnnounce({ pressed: true, wasRetrying: true, retrying: false, key: 'k', lastKey: 'k', ...o });
check('a11y: pressed Retry settles on the SAME failure → announce again', R({}));
check('a11y: a background poll (no press) stays quiet', !R({ pressed: false }));
check('a11y: still retrying → not yet', !R({ retrying: true }));
check('a11y: a DIFFERENT failure is the title/kind effect’s (announced once, not twice)', !R({ key: 'other' }));
check('a11y: nothing announced before → not a repeat', !R({ lastKey: null }));

// ── Designer: the reassurance line (PicksHome only) ─────────────────────────
const copy = friendlyError('Failed to fetch', 'today’s MLB picks');
check('announcement: title, cause, reassurance in order',
  errorAnnouncement(copy, 'Nothing is wrong with your picks.') ===
    'Couldn’t load today’s MLB picks. You’re offline. Check your connection and try again. Nothing is wrong with your picks.',
  errorAnnouncement(copy, 'Nothing is wrong with your picks.'));
check('announcement without reassurance is title + cause', errorAnnouncement(copy) === `${copy.title}. ${copy.cause}`);

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

// ── wiring for the behaviour above (Reviewer, #845) ─────────────────────────
check('ErrorState/ErrorBanner: optional reassurance prop, rendered after the cause',
  /reassurance\?: string/.test(es) && (es.match(/\{copy\.cause\}<\/Text>\s*\{reassurance \?/g) ?? []).length === 2);
check('ErrorState/ErrorBanner: announce via errorAnnouncement(copy, reassurance)', /errorAnnouncement\(copy, reassurance\)/.test(es));
check('ErrorState/ErrorBanner: an abort renders nothing', (es.match(/if \(silent\) return null;/g) ?? []).length === 2);
check('PicksHome passes the reassurance to both its error surfaces',
  /PICKS_REASSURANCE = 'Nothing is wrong with your picks\.'/.test(home) && (home.match(/reassurance=\{PICKS_REASSURANCE\}/g) ?? []).length === 2);
const reassuranceElsewhere = walk(join(ROOT, 'src'))
  .filter((p) => !/PicksHomeScreen|ErrorState\.tsx/.test(p))
  .filter((p) => /\breassurance=/.test(readFileSync(p, 'utf-8')));
check('no other screen passes a reassurance', reassuranceElsewhere.length === 0, reassuranceElsewhere.map((p) => relative(ROOT, p)).join(', '));
check('PicksHome: failed / "—" / M2 banner come from lib/loadState',
  /loadPresentation\(/.test(home) && /knownCount\(/.test(home) && /showLivePricesBanner\(/.test(home));
check('Models: the error surface comes from errorSurface(load, tab === \'builtin\')',
  /errorSurface\(load, tab === 'builtin'\)/.test(models) && /surface === 'banner' \?/.test(models) && /surface === 'state' \?/.test(models));
check('Models: no `error && !failedLoad` banner gate (it hid the Custom failure)', !/error && !failedLoad/.test(models));
check('Models: ListHeaderComponent ternary is parenthesised', /firstLoad \|\| failedLoad \? null : \(\s*!loading &&/.test(models));
check('useLivePicks: pricesUnavailable from enrichmentTracker', /enrichmentTracker\(/.test(read('src/hooks/useLivePicks.ts')) && /setPricesUnavailable\(enrichment\.missed\)/.test(read('src/hooks/useLivePicks.ts')));
// Every catch that stores an error skips an intentional cancel.
const tsFiles = (dir: string, out: string[] = []): string[] => {
  for (const n of readdirSync(dir)) {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) tsFiles(p, out);
    else if (/\.tsx?$/.test(p)) out.push(p);
  }
  return out;
};
const unguarded: string[] = [];
for (const p of tsFiles(join(ROOT, 'src'))) {
  const rel = relative(ROOT, p);
  if (/lib\/|SignInScreen/.test(rel)) continue;
  readFileSync(p, 'utf-8').split('\n').forEach((line, i) => {
    if (/(setError\(|error: )errorText\(/.test(line) && !/isAbortError\(/.test(line)) unguarded.push(`${rel}:${i + 1}`);
  });
}
check('every catch that stores an error skips aborts (isAbortError)', unguarded.length === 0, unguarded.join(', '));
check('failure toasts / alerts skip aborts too',
  /if \(cancelled \|\| isAbortError\(e\)\) return;\s*setSlate/.test(read('src/components/TeamsBoard.tsx'))
  && /if \(cancelled \|\| isAbortError\(e\)\) return;\s*setPropLines/.test(read('src/screens/StatsScreen.tsx'))
  && /if \(!isAbortError\(e\)\) Alert\.alert\('Couldn’t start linking'/.test(read('src/screens/ConnectSportsbookScreen.tsx')));
const pd = read('src/screens/PickDetailScreen.tsx');
// Designer review fixes: wiring for the behaviour pinned above.
check('zeros: useTodayPicks / useLivePicks expose `loaded`, set only on success',
  /setLoaded\(true\);\s*\} catch/.test(read('src/hooks/useTodayPicks.ts')) && /setLoaded\(true\);\s*\} catch/.test(read('src/hooks/useLivePicks.ts')));
check('zeros: PicksHome feeds `loaded` into both unknown flags',
  /knownCount\(0, \{ loaded, error,/.test(home) && /knownCount\(0, \{ loaded: liveLoaded, error: liveError,/.test(home));
check('zeros: the All header comes from todayHeaderCounts(known: !todayUnknown)', /todayHeaderCounts\(\{ date, known: !todayUnknown, \.\.\.todayStats \}\)/.test(home));
check('zeros: tabs read (—) while unknown', /count=\{todayUnknown \? null : todayStats\.total\}/.test(home)
  && /count=\{todayUnknown \? null : live\.length\}/.test(home) && /count=\{liveUnknown \? null : liveData\.length\}/.test(home));
check('zeros: Signals and Live headers do not print 0 while unknown',
  /\$\{todayUnknown \? '—' : live\.length\} pre-game signals/.test(home) && /liveUnknown\s*\? '— in play'/.test(home));
check('chips: PicksHome passes sportChipsAvailable(availableSports, known)',
  /available=\{sportChipsAvailable\(availableSports, !todayUnknown && !liveUnknown\)\}/.test(home) && !/available=\{availableSports\}/.test(home));
const toggle = read('src/components/SportToggle.tsx');
check('chips: SportToggle takes muted + label from sportChipState', /sportChipState\(\{/.test(toggle) && /accessibilityLabel=\{label\}/.test(toggle) && !/'no picks today'/.test(toggle));
check('a11y: ErrorState/ErrorBanner re-announce via repeatFailureAnnounce, keyed on the pressed Retry',
  /repeatFailureAnnounce\(\{ pressed: pressed\.current/.test(es) && (es.match(/markRetry\(\);\s*onRetry\(\);/g) ?? []).length === 2);
check('a11y: ErrorState, ErrorBanner are polite live regions', (es.match(/accessibilityLiveRegion="polite"/g) ?? []).length === 2);
check('a11y: the M2 live-prices banner is a polite live region',
  /accessibilityHint="Reloads live prices"\s*accessibilityLiveRegion="polite"/.test(home));
check('PickDetail: no dead retrying={loading} under the early-return spinner', !/retrying=\{loading\}/.test(pd));
check('TeamsBoard: its ErrorBanner passes retrying', /retrying=\{loading\}/.test(read('src/components/TeamsBoard.tsx').match(/<ErrorBanner\b[\s\S]*?\/>/)?.[0] ?? ''));

console.log(failures ? `\n${failures} FAILED` : '\nALL PASS');
process.exit(failures ? 1 : 0);
