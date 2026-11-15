/**
 * Standalone verification for crash logging (src/lib/crashLog.ts). Run with:
 *
 *   npx tsx scripts/verify_crash_log.ts
 *
 * Pins the four properties the logger exists for (2026-10-19, "the app
 * crashes now and then on first open" with no record anywhere):
 *   * a report is STORED before it is sent, so a fatal error that kills the
 *     app mid-send is delivered on the next launch;
 *   * a failed send keeps the report, and a later flush delivers it once;
 *   * a fatal error is held back from the native handler until its report
 *     is sent or FATAL_FLUSH_MS passes, and the native handler still runs;
 *   * a launch that died before RUNNING_AFTER_MS is reported on the next one,
 *     with the stage it died in and the gap to the next launch.
 */

import {
  beginLaunch,
  configureCrashLog,
  earlyExitFrom,
  flushCrashQueue,
  installGlobalErrorHandler,
  MARKER_KEY,
  MAX_QUEUED,
  QUEUE_KEY,
  recordError,
  resetCrashLogForTests,
  setCrashScreen,
  type CrashContext,
  type CrashReport,
  type KeyValueStore,
  type UpdatesLogEntry,
  UPDATES_LOG_MAX_ENTRIES,
  UPDATES_LOG_READ_TIMEOUT_MS,
  RUNNING_AFTER_MS,
} from '../src/lib/crashLog';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${!cond && detail ? ` — ${detail}` : ''}`);
}

function memStore(): KeyValueStore & { data: Map<string, string> } {
  const data = new Map<string, string>();
  return {
    data,
    async getItem(k) { return data.has(k) ? data.get(k)! : null; },
    async setItem(k, v) { data.set(k, v); },
  };
}

const CTX: CrashContext = {
  appVersion: '1.1.0', updateId: 'upd-B', updateCreatedAt: null,
  platform: 'ios 18', isEmergencyLaunch: false, emergencyLaunchReason: null,
};

function setup(opts: {
  sendFails?: () => boolean; ctx?: Partial<CrashContext>; now?: () => number;
  updatesLog?: () => Promise<UpdatesLogEntry[]>;
} = {}) {
  resetCrashLogForTests();
  const store = memStore();
  const sent: CrashReport[] = [];
  const queuedAtSend: number[] = [];
  configureCrashLog({
    storage: store,
    deviceId: async () => 'device-1234',
    context: () => ({ ...CTX, ...opts.ctx }),
    now: opts.now ?? (() => 1_000_000),
    updatesLog: opts.updatesLog,
    async send(r) {
      queuedAtSend.push(JSON.parse(store.data.get(QUEUE_KEY) ?? '[]').length);
      if (opts.sendFails?.()) throw new Error('offline');
      sent.push(r);
    },
  });
  const queue = () => JSON.parse(store.data.get(QUEUE_KEY) ?? '[]') as CrashReport[];
  return { store, sent, queue, queuedAtSend };
}

async function main() {
  // ── stored before sent, then cleared ──
  {
    const { sent, queue, queuedAtSend } = setup();
    setCrashScreen('PicksHome');
    await recordError('js_error', new TypeError('x is undefined'));
    check('the report was in storage when the send began', queuedAtSend[0] === 1, `queued=${queuedAtSend[0]}`);
    check('one report sent', sent.length === 1);
    check('it carries kind, message, stack and screen',
      sent[0]?.kind === 'js_error' && sent[0]?.message === 'TypeError: x is undefined'
      && typeof sent[0]?.stack === 'string' && sent[0]?.screen === 'PicksHome');
    check('the queue is empty after a successful send', queue().length === 0);
  }

  // ── a failed send keeps it; the next flush delivers it once ──
  {
    let offline = true;
    const { sent, queue } = setup({ sendFails: () => offline });
    await recordError('render', new Error('boom'), '\n in StatsScreen');
    check('offline: nothing sent', sent.length === 0);
    check('offline: the report stays queued', queue().length === 1);
    offline = false;
    await Promise.all([flushCrashQueue(), flushCrashQueue()]);
    check('back online: sent exactly once, even with two flushes at once', sent.length === 1, `sent=${sent.length}`);
    check('back online: the component stack survives', sent[0]?.componentStack === '\n in StatsScreen');
    check('back online: the queue is empty', queue().length === 0);
  }

  // ── the queue is bounded ──
  {
    const { queue } = setup({ sendFails: () => true });
    for (let i = 0; i < MAX_QUEUED + 5; i++) await recordError('js_error', new Error(`e${i}`));
    const q = queue();
    check(`the queue holds at most ${MAX_QUEUED}`, q.length === MAX_QUEUED, `len=${q.length}`);
    check('the oldest are dropped first', q[q.length - 1]?.message === `Error: e${MAX_QUEUED + 4}`);
  }

  // ── a non-Error throw does not break the logger ──
  {
    const { sent } = setup();
    const circular: Record<string, unknown> = {};
    circular.self = circular;
    await recordError('js_error', circular);
    check('an unserialisable throw is still reported', sent.length === 1 && sent[0]?.message === 'unserialisable error');
  }

  // ── fatal: report first, native handler second, and always ──
  {
    const { sent } = setup();
    const calls: Array<{ fatal?: boolean; sentBefore: number }> = [];
    let handler: (e: unknown, f?: boolean) => void = () => {};
    installGlobalErrorHandler({
      getGlobalHandler: () => (_e: unknown, f?: boolean) => { calls.push({ fatal: f, sentBefore: sent.length }); },
      setGlobalHandler: (h) => { handler = h; },
    });
    handler(new Error('fatal one'), true);
    check('fatal: the native handler has NOT run synchronously', calls.length === 0);
    await new Promise((r) => setTimeout(r, 50));
    check('fatal: the native handler ran after the report was sent', calls.length === 1 && calls[0].sentBefore === 1, JSON.stringify(calls));
    check('fatal: it is reported as js_fatal', sent[0]?.kind === 'js_fatal');
    handler(new Error('soft'), false);
    check('non-fatal: the native handler runs straight away', calls.length === 2 && calls[1].fatal === false);
  }
  {
    // A send that hangs must not stop the app closing.
    resetCrashLogForTests();
    const store = memStore();
    configureCrashLog({
      storage: store, deviceId: async () => 'device-1234', context: () => CTX, now: () => 0,
      send: () => new Promise<void>(() => {}),
    });
    let ran = false;
    let handler: (e: unknown, f?: boolean) => void = () => {};
    installGlobalErrorHandler({ getGlobalHandler: () => () => { ran = true; }, setGlobalHandler: (h) => { handler = h; } });
    handler(new Error('fatal, network hung'), true);
    await new Promise((r) => setTimeout(r, 1_700));
    check('fatal with a hung send: the native handler still runs within FATAL_FLUSH_MS', ran);
    check('fatal with a hung send: the report is kept for the next launch', (JSON.parse(store.data.get(QUEUE_KEY) ?? '[]') as unknown[]).length === 1);
  }

  // ── early exit ──
  check('no previous marker: nothing reported', earlyExitFrom(null, 10, 'a') === null);
  check('previous launch reached running: nothing reported',
    earlyExitFrom({ stage: 'running', at: 0, updateId: 'a' }, 10, 'a') === null);
  {
    const r = earlyExitFrom({ stage: 'launching', at: 1_000, updateId: 'upd-A' }, 1_800, 'upd-B');
    check('died while launching: reported as early_exit with that stage', r?.kind === 'early_exit' && r?.stage === 'launching');
    check('the gap and both bundle ids are carried',
      r?.extra?.gap_ms === 800 && r?.extra?.prev_update_id === 'upd-A'
      && r?.extra?.update_id_now === 'upd-B' && r?.extra?.bundle_changed === true, JSON.stringify(r?.extra));
  }
  {
    const t = 5_000;
    const { store, sent } = setup({ now: () => t });
    store.data.set(MARKER_KEY, JSON.stringify({ stage: 'launching', at: 1_000, updateId: 'upd-A' }));
    await beginLaunch();
    await flushCrashQueue();
    check('beginLaunch reports the previous launch that died young', sent.length === 1 && sent[0]?.stage === 'launching');
    const m = JSON.parse(store.data.get(MARKER_KEY)!);
    check('beginLaunch writes this launch as launching', m.stage === 'launching' && m.at === 5_000 && m.updateId === 'upd-B');
  }
  {
    const { queue } = setup({ sendFails: () => true });
    await Promise.all([
      recordError('js_error', new Error('first')),
      recordError('js_error', new Error('second')),
    ]);
    const messages = queue().map((r) => r.message);
    check('two concurrent enqueues both survive',
      queue().length === 2 && messages.includes('Error: first') && messages.includes('Error: second'),
      JSON.stringify(messages));
  }
  {
    const { sent } = setup({ ctx: { isEmergencyLaunch: true, emergencyLaunchReason: 'update crashed' } });
    await beginLaunch();
    await flushCrashQueue();
    check('an expo-updates rollback is reported', sent.some((r) => r.kind === 'emergency_launch' && r.message === 'update crashed'));
  }

  // ── expo-updates' own log (2026-11-14: a native abort before JS ran) ──
  {
    // What ErrorRecovery writes before it aborts: the JS-runtime error, then
    // the "crashing" line. Info lines and an old error must not be sent.
    const LOG: UpdatesLogEntry[] = [
      { timestamp: 500, level: 'error', code: 'UpdateFailedToLoad', message: 'old, already reported' },
      { timestamp: 900_000, level: 'info', code: 'None', message: 'ErrorRecovery: launching a cached update' },
      { timestamp: 900_100, level: 'error', code: 'JSRuntimeError', message: 'Fatal exception: asset missing', updateId: 'upd-C' },
      { timestamp: 900_200, level: 'fatal', code: 'UpdateFailedToLoad', message: 'ErrorRecovery: could not recover from error, crashing' },
    ];
    const { sent, store } = setup({ updatesLog: async () => LOG });
    store.data.set('crashlog.updates_log_seen', '500');
    await beginLaunch();
    await flushCrashQueue();
    const r = sent.find((x) => x.kind === 'emergency_launch');
    const entries = (r?.extra?.updates_log ?? []) as Array<Record<string, unknown>>;
    check('updates log: its errors are reported on the next launch',
      !!r && r.extra?.source === 'updates_log' && entries.length === 2, JSON.stringify(r));
    check('updates log: the message is the newest error, with its code',
      r?.message === 'UpdateFailedToLoad: ErrorRecovery: could not recover from error, crashing', String(r?.message));
    check('updates log: the entry naming the failed bundle is kept',
      entries[0]?.update_id === 'upd-C' && entries[0]?.message === 'Fatal exception: asset missing');
    check('updates log: dated when expo-updates wrote it, not now',
      r?.occurredAt === new Date(900_200).toISOString(), String(r?.occurredAt));

    // A second launch with the same log sends nothing new.
    const before = sent.length;
    await beginLaunch();
    await flushCrashQueue();
    check('updates log: an entry is sent once', !sent.slice(before).some((x) => x.kind === 'emergency_launch'));
  }
  {
    const { sent } = setup({ updatesLog: async () => [
      { timestamp: 10, level: 'info', code: 'None', message: 'fine' },
      { timestamp: 20, level: 'warn', code: 'None', message: 'meh' },
    ] });
    await beginLaunch();
    await flushCrashQueue();
    check('updates log: info and warn lines are not reported', !sent.some((x) => x.kind === 'emergency_launch'));
  }
  {
    const many: UpdatesLogEntry[] = Array.from({ length: 40 }, (_, i) =>
      ({ timestamp: 1000 + i, level: 'error', code: 'UpdateFailedToLoad', message: `e${i}` }));
    const { sent } = setup({ updatesLog: async () => many });
    await beginLaunch();
    await flushCrashQueue();
    const entries = (sent.find((x) => x.kind === 'emergency_launch')?.extra?.updates_log ?? []) as Array<Record<string, unknown>>;
    check('updates log: capped to the newest entries',
      entries.length === UPDATES_LOG_MAX_ENTRIES && entries[entries.length - 1]?.message === 'e39', String(entries.length));
  }
  {
    const { sent } = setup({
      ctx: { isEmergencyLaunch: true, emergencyLaunchReason: 'update crashed' },
      updatesLog: async () => [{ timestamp: 5, level: 'error', code: 'JSRuntimeError', message: 'boom' }],
    });
    await beginLaunch();
    await flushCrashQueue();
    const rows = sent.filter((x) => x.kind === 'emergency_launch');
    check('updates log: an emergency launch carries the entries on its own row',
      rows.length === 1 && rows[0].message === 'update crashed'
        && (rows[0].extra?.updates_log as unknown[] | undefined)?.length === 1, JSON.stringify(rows));
  }
  {
    // An offline open: expo-updates logs failed downloads at error level.
    // No launch failed, so no row.
    const { sent } = setup({ updatesLog: async () => [
      { timestamp: 10, level: 'error', code: 'Unknown', message: 'The Internet connection appears to be offline.' },
      { timestamp: 20, level: 'error', code: 'AssetsFailedToLoad', message: 'download failed' },
      { timestamp: 30, level: 'error', code: 'UpdateServerUnreachable', message: 'unreachable' },
    ] });
    await beginLaunch();
    await flushCrashQueue();
    check('updates log: an offline open (download errors only) is not reported',
      !sent.some((x) => x.kind === 'emergency_launch'));
  }
  {
    // A launch failure followed by a later download error: named by the failure.
    const { sent } = setup({ updatesLog: async () => [
      { timestamp: 10, level: 'error', code: 'JSRuntimeError', message: 'Fatal exception: x' },
      { timestamp: 20, level: 'error', code: 'Unknown', message: 'offline' },
    ] });
    await beginLaunch();
    await flushCrashQueue();
    const r = sent.find((x) => x.kind === 'emergency_launch');
    check('updates log: the row is named by the launch failure, not a later download error',
      r?.message === 'JSRuntimeError: Fatal exception: x'
        && (r?.extra?.updates_log as unknown[] | undefined)?.length === 2, String(r?.message));
  }
  {
    // A native read that never returns must not hold the launch marker.
    const realSetTimeout = globalThis.setTimeout;
    const timers: Array<{ fn: () => void; ms: number }> = [];
    (globalThis as { setTimeout: unknown }).setTimeout = ((fn: () => void, ms: number) => {
      timers.push({ fn, ms }); return 0 as unknown as ReturnType<typeof setTimeout>;
    }) as unknown;
    const { store } = setup({ updatesLog: () => new Promise<UpdatesLogEntry[]>(() => {}) });
    const launched = beginLaunch();
    await new Promise<void>((res) => realSetTimeout(res, 20));
    const marker = timers.find((t) => t.ms === RUNNING_AFTER_MS);
    marker?.fn();
    await new Promise<void>((res) => realSetTimeout(res, 20));
    const m = JSON.parse(store.data.get(MARKER_KEY) ?? '{}');
    check('updates log: a hung read still lets the launch be marked running', m.stage === 'running', JSON.stringify(m));
    const cut = timers.find((t) => t.ms === UPDATES_LOG_READ_TIMEOUT_MS);
    cut?.fn();
    let done = false;
    void launched.then(() => { done = true; });
    await new Promise<void>((res) => realSetTimeout(res, 20));
    (globalThis as { setTimeout: unknown }).setTimeout = realSetTimeout;
    check('updates log: a hung read is cut off and the launch finishes', !!cut && done);
  }
  {
    // The seen mark is written only once the report is stored.
    const { store } = setup({ updatesLog: async () => [
      { timestamp: 77, level: 'fatal', code: 'UpdateFailedToLoad', message: 'crashing' },
    ] });
    const realSet = store.setItem.bind(store);
    store.setItem = async (k, v) => { if (k === QUEUE_KEY) throw new Error('disk full'); return realSet(k, v); };
    await beginLaunch();
    check('updates log: a report that could not be stored is not marked sent',
      !store.data.has('crashlog.updates_log_seen'), String(store.data.get('crashlog.updates_log_seen')));
  }
  {
    const { sent } = setup({ updatesLog: async () => { throw new Error('ERR_UPDATES_READ_LOGS'); } });
    let threw = false;
    try { await beginLaunch(); await flushCrashQueue(); } catch { threw = true; }
    check('updates log: a failed read throws nothing and sends nothing',
      !threw && !sent.some((x) => x.kind === 'emergency_launch'));
  }

  // ── nothing configured: nothing throws ──
  resetCrashLogForTests();
  let threw = false;
  try { await recordError('js_error', new Error('x')); await beginLaunch(); await flushCrashQueue(); } catch { threw = true; }
  check('unconfigured: every entry point is a no-op', !threw);

  console.log(failures ? `\n${failures} check(s) FAILED.` : '\nAll checks passed.');
  process.exit(failures ? 1 : 0);
}

void main();
