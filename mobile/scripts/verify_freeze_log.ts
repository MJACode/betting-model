// Drives src/lib/freezeLog.ts (and its hook into crashLog.ts) with a fake
// clock, fake timers and in-memory storage. Run by tests/test_mobile_freeze_log.py
// under node --experimental-strip-types.

import {
  beginFreezeLog,
  configureFreezeLog,
  noteAppState,
  noteModalDismissed,
  noteModalShown,
  noteModalVisible,
  noteScreen,
  noteTouch,
  resetFreezeLogForTests,
  restartFrom,
  sessionSummary,
  tick,
  trailForReport,
  SESSION_KEY,
  MODAL_CONFIRM_MS,
  type SessionRecord,
} from '../src/lib/freezeLog';
import {
  configureCrashLog,
  recordReport,
  resetCrashLogForTests,
  setTrailProvider,
  type CrashReport,
} from '../src/lib/crashLog';

let failures = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) console.log(`[PASS] ${name}`);
  else {
    failures += 1;
    console.log(`[FAIL] ${name} ${detail}`);
  }
}

interface Sent { kind: string; message: string; extra: Record<string, unknown>; screen?: string | null }

function harness(stored: Record<string, string> = {}) {
  let clock = 1_000_000;
  const store = { ...stored };
  const sent: Sent[] = [];
  const timers = new Map<number, { at: number; fn: () => void }>();
  let nextId = 1;
  resetFreezeLogForTests();
  configureFreezeLog({
    storage: {
      async getItem(k) { return store[k] ?? null; },
      async setItem(k, v) { store[k] = v; },
    },
    now: () => clock,
    report(kind, message, extra, screen) { sent.push({ kind, message, extra, screen }); },
    setTimeout(fn, ms) { const id = nextId++; timers.set(id, { at: clock + ms, fn }); return id; },
    clearTimeout(h) { timers.delete(h as number); },
    setInterval() { return 0; },
  });
  return {
    store,
    sent,
    advance(ms: number) {
      clock += ms;
      for (const [id, t] of [...timers]) {
        if (t.at <= clock) { timers.delete(id); t.fn(); }
      }
    },
    get now() { return clock; },
  };
}

function session(over: Partial<SessionRecord>): SessionRecord {
  return {
    launchAt: 0,
    savedAt: 60_000,
    appState: 'active',
    backgroundAt: null,
    screen: 'Settings',
    lastTouchAt: 58_000,
    touchesSinceNav: 7,
    openModals: ['DailyResultsModal'],
    trail: [
      { t: 50_000, k: 'screen', d: 'Settings' },
      { t: 58_000, k: 'touch', d: '7' },
    ],
    ...over,
  };
}

// --- how the previous session ended -------------------------------------
{
  const r = restartFrom(session({}), 70_000);
  check('ended on screen: reported as restart, naming the screen', r !== null && r.screen === 'Settings');
  check('restart carries taps since navigation and open pop-ups',
    r !== null && r.extra.touches_since_nav === 7
      && JSON.stringify(r.extra.open_modals) === '["DailyResultsModal"]');
  check('restart carries the previous trail', r !== null && Array.isArray(r.extra.trail)
    && (r.extra.trail as unknown[]).length === 2);
  check('ended in the app switcher (inactive): reported', restartFrom(session({ appState: 'inactive' }), 70_000) !== null);
  check('relaunched 30s after background: reported',
    restartFrom(session({ appState: 'background', backgroundAt: 60_000 }), 90_000) !== null);
  check('relaunched 10 min after background: not reported',
    restartFrom(session({ appState: 'background', backgroundAt: 60_000 }), 660_000) === null);
  check('a session under 15s: left to early_exit', restartFrom(session({ savedAt: 10_000 }), 70_000) === null);
  check('no previous session: nothing', restartFrom(null, 70_000) === null);
}

// --- beginFreezeLog reads the stored session and reports it ---------------
{
  const h = harness({ [SESSION_KEY]: JSON.stringify(session({ launchAt: 900_000, savedAt: 990_000, trail: [] })) });
  await beginFreezeLog('active');
  check('launch after a forced restart sends one restart report',
    h.sent.length === 1 && h.sent[0].kind === 'restart' && h.sent[0].screen === 'Settings');
  const saved = JSON.parse(h.store[SESSION_KEY]) as SessionRecord;
  check('this launch saved its own session at once', saved.launchAt === h.now);
}

// --- the stall watchdog ----------------------------------------------------
{
  const h = harness();
  await beginFreezeLog('active');
  h.advance(2_000); tick();
  check('a normal tick is not a stall', h.sent.length === 0);
  h.advance(6_000); tick();
  check('a 6s gap while on screen is a js_stall', h.sent.length === 1 && h.sent[0].kind === 'js_stall'
    && h.sent[0].extra.stall_ms === 6_000);
  // iOS runs no timers in background: no tick until the app is back.
  noteAppState('background');
  h.advance(60_000);
  noteAppState('active');
  h.advance(1_000); tick();
  check('time spent in background is not a stall', h.sent.length === 1);
  for (let i = 0; i < 5; i += 1) { h.advance(6_000); tick(); }
  check('stall reports are capped per launch', h.sent.filter((s) => s.kind === 'js_stall').length === 3);
}

// --- pop-ups that iOS never confirms ---------------------------------------
{
  const h = harness();
  await beginFreezeLog('active');
  noteModalVisible('A', true, true);
  h.advance(300); noteModalShown('A');
  h.advance(MODAL_CONFIRM_MS + 1);
  check('a pop-up iOS showed is not stuck', h.sent.length === 0);
  check('it is listed as open', JSON.stringify(sessionSummary()?.open_modals) === '["A"]');
  noteModalVisible('A', false, true);
  h.advance(300); noteModalDismissed('A');
  h.advance(MODAL_CONFIRM_MS + 1);
  check('a pop-up iOS dismissed is not stuck', h.sent.length === 0);
  noteModalVisible('B', true, true);
  h.advance(MODAL_CONFIRM_MS + 1);
  check('a pop-up iOS never showed is reported as modal_stuck present',
    h.sent.length === 1 && h.sent[0].kind === 'modal_stuck' && h.sent[0].extra.phase === 'present');
  noteModalShown('B');
  noteModalVisible('B', false, true);
  h.advance(MODAL_CONFIRM_MS + 1);
  check('a close iOS never confirmed is reported as modal_stuck dismiss',
    h.sent.length === 2 && h.sent[1].extra.phase === 'dismiss');
  noteModalVisible('C', true, false);
  noteModalShown('C');
  noteModalVisible('C', false, false);
  h.advance(MODAL_CONFIRM_MS + 1);
  check('without a dismiss callback (Android) a close is not watched', h.sent.length === 2);
}

// --- taps and screens in the trail ---------------------------------------
{
  const h = harness();
  await beginFreezeLog('active');
  noteScreen('Picks');
  noteTouch(); noteTouch(); noteTouch();
  const t = trailForReport() ?? [];
  const last = t[t.length - 1];
  check('a run of taps is one crumb with the count', last?.[1] === 'touch' && last?.[2] === '3');
  check('taps since navigation counted', sessionSummary()?.touches_since_nav === 3);
  noteScreen('Settings');
  check('a screen change resets the tap count', sessionSummary()?.touches_since_nav === 0);
  for (let i = 0; i < 200; i += 1) { noteScreen(`S${i}`); }
  check('the trail stays bounded', (trailForReport() ?? []).length <= 40
    && JSON.stringify(trailForReport()).length <= 3_000);
  void h;
}

// --- every crash-log report carries the trail ------------------------------
{
  harness();
  await beginFreezeLog('active');
  noteScreen('Settings');
  resetCrashLogForTests();
  const queue: Record<string, string> = {};
  const delivered: CrashReport[] = [];
  configureCrashLog({
    storage: { async getItem(k) { return queue[k] ?? null; }, async setItem(k, v) { queue[k] = v; } },
    async send(r) { delivered.push(r); },
    async deviceId() { return 'device-test-1234'; },
    context: () => ({ appVersion: '1', updateId: null, updateCreatedAt: null, platform: 'ios', isEmergencyLaunch: false, emergencyLaunchReason: null }),
    now: () => 0,
  });
  setTrailProvider(() => ({ trail: trailForReport(), session: sessionSummary() }));
  await recordReport({ kind: 'js_error', message: 'boom' });
  const extra = delivered[0]?.extra as Record<string, unknown> | undefined;
  check('a js_error report carries the trail', Array.isArray(extra?.trail)
    && JSON.stringify(extra?.trail).includes('Settings'));
  await recordReport({ kind: 'js_stall', message: 's', extra: { trail: ['own'] } });
  const own = delivered[1]?.extra as Record<string, unknown> | undefined;
  check('a report with its own trail keeps it', JSON.stringify(own?.trail) === '["own"]');
}

if (failures > 0) {
  console.log(`${failures} failure(s)`);
  process.exit(1);
}
console.log('all freeze-log checks passed');
