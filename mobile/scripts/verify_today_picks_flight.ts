/**
 * Today's board is one shared read.
 *
 *   npx tsx scripts/verify_today_picks_flight.ts
 *
 * The flight tests import the cache directly (no React). The request count
 * at the bottom runs the real seven-sport read against a fake fetch, once
 * per caller and once shared, and prints the table counts. That import needs
 * the app's `@/` paths, so it runs under tsx and is skipped when this file
 * is loaded with type stripping alone.
 */

import {
  loadTodayBoard,
  loadTodayBoardOnForeground,
  resetTodayBoardForTests,
  setTodayBoardClockForTests,
  setTodayBoardReader,
  setTodayPicksStaleMsForTests,
  subscribeTodayBoard,
  TODAY_PICKS_STALE_MS,
  todayBoardSnapshot,
  type TodayBoardRead,
} from '../src/lib/todayPicksFlight';

let failures = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures += 1;
    console.log(`[FAIL] ${name}${detail ? ` — ${detail}` : ''}`);
  }
}

interface Row {
  id: number;
}

function ok(id: number): TodayBoardRead<Row> {
  return { data: [{ id }], pausedData: [], loaded: true, error: null, partial: null };
}

function fail(message: string): TodayBoardRead<Row> {
  return { data: [], pausedData: [], loaded: false, error: message, partial: null };
}

/** Resolves only when the test says so, so callers can pile onto one read. */
function gate() {
  let release: () => void = () => {};
  const opened = new Promise<void>((resolve) => {
    release = resolve;
  });
  return { opened, release: () => release() };
}

const DATE = '2026-11-11';

async function singleFlight(): Promise<void> {
  resetTodayBoardForTests();
  let calls = 0;
  const hold = gate();
  setTodayBoardReader(async () => {
    calls += 1;
    await hold.opened;
    return ok(calls);
  });
  const pending = [
    loadTodayBoard(DATE, false),
    loadTodayBoard(DATE, false),
    loadTodayBoard(DATE, false),
    loadTodayBoard(DATE, false),
  ];
  check('four concurrent callers start one read', calls === 1, `calls=${calls}`);
  hold.release();
  await Promise.all(pending);
  check('those callers still made one read', calls === 1, `calls=${calls}`);
  check('the shared read is cached', todayBoardSnapshot<Row>(DATE).data[0]?.id === 1);
  await loadTodayBoard(DATE, false);
  check('a later caller reuses the finished read', calls === 1, `calls=${calls}`);
}

async function refreshInvalidates(): Promise<void> {
  resetTodayBoardForTests();
  let calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    return ok(calls);
  });
  await loadTodayBoard(DATE, false);
  await loadTodayBoard(DATE, true);
  check('refresh after a finished read starts another', calls === 2, `calls=${calls}`);
  check('refresh replaces the cached rows', todayBoardSnapshot<Row>(DATE).data[0]?.id === 2);
}

async function refreshDuringFlightIsOneFollowUp(): Promise<void> {
  resetTodayBoardForTests();
  let calls = 0;
  const holds = [gate(), gate()];
  setTodayBoardReader(async () => {
    const n = calls;
    calls += 1;
    await holds[n]?.opened;
    return ok(calls);
  });
  const first = loadTodayBoard(DATE, false);
  const second = loadTodayBoard(DATE, false);
  const refresh = loadTodayBoard(DATE, true);
  check('a refresh during the read does not start a second one yet', calls === 1, `calls=${calls}`);
  holds[0]?.release();
  // The follow-up is the second read. Let it start before releasing it.
  await Promise.resolve();
  await Promise.resolve();
  check('that refresh schedules exactly one follow-up', calls === 2, `calls=${calls}`);
  holds[1]?.release();
  await Promise.all([first, second, refresh]);
  check('the follow-up is the value callers settle on', todayBoardSnapshot<Row>(DATE).data[0]?.id === 2);
  check('no third read was started', calls === 2, `calls=${calls}`);
}

async function failedRefreshKeepsRows(): Promise<void> {
  resetTodayBoardForTests();
  let calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    if (calls === 1) return ok(1);
    return fail('timed out');
  });
  await loadTodayBoard(DATE, false);
  await loadTodayBoard(DATE, true);
  const snap = todayBoardSnapshot<Row>(DATE);
  check('a failed refresh keeps the rows already loaded', snap.data[0]?.id === 1 && snap.loaded && snap.error === 'timed out');
  resetTodayBoardForTests();
  calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    if (calls === 1) return fail('down');
    return ok(2);
  });
  await loadTodayBoard(DATE, false);
  check('a failed first read leaves the board unloaded', todayBoardSnapshot<Row>(DATE).loaded === false);
  await loadTodayBoard(DATE, false);
  check('the next load retries a failed read', calls === 2 && todayBoardSnapshot<Row>(DATE).data[0]?.id === 2);
}

async function datesDoNotShare(): Promise<void> {
  resetTodayBoardForTests();
  const seen: string[] = [];
  setTodayBoardReader(async (date: string) => {
    seen.push(date);
    return ok(seen.length);
  });
  await Promise.all([loadTodayBoard('2026-11-11', false), loadTodayBoard('2026-11-12', false)]);
  check('two dates are two reads', seen.length === 2, seen.join(','));
  check('each date keeps its own rows', todayBoardSnapshot<Row>('2026-11-11').data[0]?.id === 1
    && todayBoardSnapshot<Row>('2026-11-12').data[0]?.id === 2);
}

async function ageWindow(): Promise<void> {
  resetTodayBoardForTests();
  check('the staleness age is five minutes', TODAY_PICKS_STALE_MS === 5 * 60 * 1000, String(TODAY_PICKS_STALE_MS));
  let t = 1_000_000;
  setTodayBoardClockForTests(() => t);
  let calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    return ok(calls);
  });
  await loadTodayBoard(DATE, false);
  t += TODAY_PICKS_STALE_MS - 1;
  await loadTodayBoard(DATE, false);
  check('a fresh mount does not re-read', calls === 1, `calls=${calls}`);
  await loadTodayBoardOnForeground(DATE);
  check('a fresh foreground does not re-read', calls === 1, `calls=${calls}`);
  t += 1;
  await loadTodayBoard(DATE, false);
  check('a stale mount re-reads once', calls === 2, `calls=${calls}`);

  t += TODAY_PICKS_STALE_MS;
  await loadTodayBoardOnForeground(DATE);
  check('a stale foreground re-reads once', calls === 3, `calls=${calls}`);

  t += TODAY_PICKS_STALE_MS;
  const hold = gate();
  setTodayBoardReader(async () => {
    calls += 1;
    await hold.opened;
    return ok(calls);
  });
  const pending = [0, 1, 2, 3].map(() => loadTodayBoard(DATE, false));
  check('four stale callers start one read', calls === 4, `calls=${calls}`);
  hold.release();
  await Promise.all(pending);
  check('four stale callers still made one read', calls === 4, `calls=${calls}`);
}

async function infinityIsForegroundOnly(): Promise<void> {
  resetTodayBoardForTests();
  setTodayPicksStaleMsForTests(Number.POSITIVE_INFINITY);
  let t = 1_000_000;
  setTodayBoardClockForTests(() => t);
  let calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    return ok(calls);
  });
  await loadTodayBoard(DATE, false);
  t += 24 * 60 * 60 * 1000;
  await loadTodayBoard(DATE, false);
  check('Infinity: a later mount does not re-read', calls === 1, `calls=${calls}`);
  const hold = gate();
  setTodayBoardReader(async () => {
    calls += 1;
    await hold.opened;
    return ok(calls);
  });
  const pending = [0, 1, 2, 3].map(() => loadTodayBoardOnForeground(DATE));
  check('Infinity: four foregrounds start one read', calls === 2, `calls=${calls}`);
  hold.release();
  await Promise.all(pending);
  check('Infinity: four foregrounds still made one read', calls === 2, `calls=${calls}`);
}

async function aQuietDateIsDropped(): Promise<void> {
  resetTodayBoardForTests();
  let calls = 0;
  setTodayBoardReader(async () => {
    calls += 1;
    return ok(calls);
  });
  const stop = subscribeTodayBoard<Row>('2026-11-10', () => {});
  await loadTodayBoard('2026-11-10', false);
  await loadTodayBoard('2026-11-11', false);
  const kept = calls;
  await loadTodayBoard('2026-11-10', false);
  check('a date with a listener is kept', calls === kept, `calls=${calls}`);
  stop();
  await loadTodayBoard('2026-11-12', false);
  const dropped = calls;
  await loadTodayBoard('2026-11-10', false);
  check('a date nobody is watching is dropped', calls === dropped + 1, `calls=${calls} dropped=${dropped}`);
}

async function listenersSeeTheRead(): Promise<void> {
  resetTodayBoardForTests();
  const hold = gate();
  setTodayBoardReader(async () => {
    await hold.opened;
    return ok(7);
  });
  const seen: boolean[] = [];
  const stop = subscribeTodayBoard<Row>(DATE, (snap) => seen.push(snap.loading));
  const pending = loadTodayBoard(DATE, false);
  check('subscribers hear loading at the start', seen[0] === true, JSON.stringify(seen));
  hold.release();
  await pending;
  check('subscribers hear the finished read', seen[seen.length - 1] === false
    && todayBoardSnapshot<Row>(DATE).data[0]?.id === 7);
  stop();
}

/**
 * Tables one board read hits when every page comes back empty. Production
 * pages past 1,000 rows, so these are the reads, not the production page
 * count. Compared per caller vs one shared read.
 */
async function countLaunchRequests(): Promise<void> {
  let hook: typeof import('../src/hooks/useTodayPicks');
  try {
    const { registerHooks } = await import('node:module');
    const stub = new URL('./shims/react-native.mjs', import.meta.url).href;
    registerHooks({
      resolve(specifier, context, nextResolve) {
        if (specifier === 'react-native' || specifier.startsWith('react-native/')) {
          return { url: stub, shortCircuit: true };
        }
        return nextResolve(specifier, context);
      },
    });
    process.env.EXPO_PUBLIC_SUPABASE_URL = 'https://example.supabase.co';
    process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY = 'test-anon-key';
    hook = await import('../src/hooks/useTodayPicks');
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : String(e);
    if (process.env.CI) {
      check('launch request count runs in CI', false, message);
      return;
    }
    console.log(`[SKIP] launch request count (needs tsx and the app graph) — ${message}`);
    return;
  }

  const { resourceFromUrl } = await import('../src/lib/perfLog');
  const tables = ['picks', 'v_latest_odds_all_books', 'games', 'v_latest_dk_odds'] as const;

  async function count(run: () => Promise<void>): Promise<Record<string, number>> {
    const counts: Record<string, number> = {};
    const previous = globalThis.fetch;
    globalThis.fetch = async (input: RequestInfo | URL) => {
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
      const name = resourceFromUrl(url) ?? 'other';
      counts[name] = (counts[name] ?? 0) + 1;
      return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } });
    };
    try {
      await run();
    } finally {
      globalThis.fetch = previous;
    }
    return counts;
  }

  // The hook install replaced the fake reader. Count the real read.
  resetTodayBoardForTests();
  const one = await count(async () => {
    await hook.readTodayBoard('2026-11-11');
  });
  // Four mounts, the call sites named in the launch trace, without a cache.
  const uncached = await count(async () => {
    await Promise.all([
      hook.readTodayBoard('2026-11-11'),
      hook.readTodayBoard('2026-11-11'),
      hook.readTodayBoard('2026-11-11'),
      hook.readTodayBoard('2026-11-11'),
    ]);
  });
  resetTodayBoardForTests();
  const shared = await count(() =>
    Promise.all([
      loadTodayBoard('2026-11-11', false),
      loadTodayBoard('2026-11-11', false),
      loadTodayBoard('2026-11-11', false),
      loadTodayBoard('2026-11-11', false),
    ]).then(() => undefined),
  );

  console.log('LAUNCH REQUEST COUNTS (empty pages; one row per read, not per production page)');
  console.log(`table\t1 read\t4 callers uncached\t4 callers shared`);
  for (const table of tables) {
    const single = one[table] ?? 0;
    const before = uncached[table] ?? 0;
    const after = shared[table] ?? 0;
    console.log(`${table}\t${single}\t${before}\t${after}`);
    check(`${table}: four shared callers make one read's requests`, after === single && before === single * 4,
      `one=${single} uncached=${before} shared=${after}`);
  }
  // Picks and the betslip bar are the two mounts at launch. Same empty-page
  // shape: two uncached reads are twice one read, and the shared flight is one.
  console.log('launch mounts (Picks + betslip), empty pages: uncached = 2× one read, shared = one read');
  for (const table of tables) {
    const single = one[table] ?? 0;
    console.log(`${table}\tuncached ${single * 2}\tshared ${single}`);
  }
}

async function main(): Promise<void> {
  await singleFlight();
  await refreshInvalidates();
  await refreshDuringFlightIsOneFollowUp();
  await failedRefreshKeepsRows();
  await datesDoNotShare();
  await ageWindow();
  await infinityIsForegroundOnly();
  await aQuietDateIsDropped();
  await listenersSeeTheRead();
  await countLaunchRequests();
  if (failures) {
    console.log(`\n${failures} FAILED`);
    process.exit(1);
  }
  console.log('\nALL PASS');
}

void main().catch((e: unknown) => {
  console.error(e);
  process.exit(1);
});
