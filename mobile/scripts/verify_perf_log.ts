/**
 * Standalone verification for load-time logging (src/lib/perfLog.ts). Run with:
 *
 *   npx tsx scripts/verify_perf_log.ts
 *
 * Pins what the logger exists for (2026-10-31):
 *   * the wrapped fetch returns and throws exactly what the real one does, and
 *     still does when the bookkeeping itself throws;
 *   * one request row per call, named by view or rpc, with no query string,
 *     and the logger's own sends are not timed;
 *   * a screen row only once EVERY request it started has finished, timed to
 *     the last one; a request that starts after JOIN_MS does not hold it open;
 *   * the first screen also writes a launch row, timed from the launch clock;
 *   * a failed send keeps the rows and a later flush delivers them once.
 */

import {
  configurePerfLog,
  flushPerfLog,
  JOIN_MS,
  peekPerfBufferForTests,
  QUIET_MS,
  resetPerfLogForTests,
  resourceFromUrl,
  setPerfScreen,
  timedFetch,
  type TimingRow,
} from '../src/lib/perfLog';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${!cond && detail ? ` — ${detail}` : ''}`);
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const BASE = 'https://abc.supabase.co';

let clock = 1_000_000;
function setup(sent: TimingRow[][] = [], failSend = () => false) {
  resetPerfLogForTests();
  clock = 1_000_000;
  configurePerfLog({
    now: () => clock,
    launchAt: clock - 200,
    async send(rows) {
      if (failSend()) throw new Error('offline');
      sent.push(rows);
    },
  });
}

/** A fake fetch whose calls resolve when told to. */
function controllable() {
  const calls: { input: any; init: any; resolve: (v: any) => void; reject: (e: any) => void }[] = [];
  const f = (input: any, init?: any) =>
    new Promise((resolve, reject) => {
      calls.push({ input, init, resolve, reject });
    });
  return { f, calls };
}

async function main() {
  // --- naming
  check('names a view', resourceFromUrl(`${BASE}/rest/v1/v_public_track_record?select=*&model_id=eq.x`) === 'v_public_track_record');
  check('names an rpc', resourceFromUrl(`${BASE}/rest/v1/rpc/player_window_totals?x=1`) === 'rpc:player_window_totals');
  check('names auth', resourceFromUrl(`${BASE}/auth/v1/token?grant_type=refresh_token`) === 'auth:token');
  check('ignores a foreign url', resourceFromUrl('https://example.com/api/thing') === null);

  // --- passthrough
  {
    setup();
    const { f, calls } = controllable();
    const wrapped = timedFetch(f);
    const res = { status: 200, marker: 'same object' };
    const init = { method: 'GET', headers: { a: 'b' } };
    const p = wrapped(`${BASE}/rest/v1/picks?select=*`, init);
    check('the real fetch got the same arguments', calls[0].input === `${BASE}/rest/v1/picks?select=*` && calls[0].init === init);
    calls[0].resolve(res);
    check('the response is the same object', (await p) === res);

    const err = new Error('network down');
    const p2 = wrapped(`${BASE}/rest/v1/picks`);
    calls[1].reject(err);
    let caught: unknown = null;
    try {
      await p2;
    } catch (e) {
      caught = e;
    }
    check('the error is the same object', caught === err);
    const rows = peekPerfBufferForTests().filter((r) => r.kind === 'request');
    check('a failed request is logged with status 0', rows.some((r) => r.status === 0));
  }

  // --- bookkeeping that throws does not break the request
  {
    resetPerfLogForTests();
    configurePerfLog({
      now: () => {
        throw new Error('clock broke');
      },
      launchAt: 0,
      async send() {},
    });
    const { f, calls } = controllable();
    let ok = false;
    try {
      const p = timedFetch(f)(`${BASE}/rest/v1/picks`);
      calls[0].resolve({ status: 200 });
      ok = (await p).status === 200;
    } catch {
      ok = false;
    }
    check('a throwing clock still returns the response', ok);
  }

  // --- request rows
  {
    setup();
    const { f, calls } = controllable();
    const wrapped = timedFetch(f);
    const p = wrapped(`${BASE}/rest/v1/v_latest_dk_odds?select=game_id&game_date=eq.2026-10-31`);
    clock += 250;
    calls[0].resolve({ status: 200 });
    await p;
    const own = wrapped(`${BASE}/rest/v1/rpc/log_app_timings`);
    calls[1].resolve({ status: 204 });
    await own;
    const reqs = peekPerfBufferForTests().filter((r) => r.kind === 'request');
    check('one request row, timed', reqs.length === 1 && reqs[0].ms === 250, JSON.stringify(reqs));
    check('no query string is kept', !JSON.stringify(reqs).includes('game_date'));
    check("the logger's own send is not timed", !reqs.some((r) => r.name.includes('log_app')));
  }

  // --- screen + launch windows
  {
    setup();
    const { f, calls } = controllable();
    const wrapped = timedFetch(f);
    // First screen: requests start before navigation is ready, as on a real cold start.
    const a = wrapped(`${BASE}/rest/v1/picks`);
    const b = wrapped(`${BASE}/rest/v1/v_latest_dk_odds`);
    setPerfScreen('Tabs');
    clock += 100;
    calls[0].resolve({ status: 200 });
    await a;
    await sleep(QUIET_MS + 50);
    check('the screen is not loaded while a request is still out', !peekPerfBufferForTests().some((r) => r.kind === 'screen'));
    clock += 400;
    calls[1].resolve({ status: 200 });
    await b;
    await sleep(QUIET_MS + 50);
    const screens = peekPerfBufferForTests().filter((r) => r.kind === 'screen');
    const launches = peekPerfBufferForTests().filter((r) => r.kind === 'launch');
    check('first screen: one row, timed to the LAST request', screens.length === 1 && screens[0].ms === 500 && screens[0].requestCount === 2, JSON.stringify(screens));
    check('first screen takes the first route name', screens[0]?.name === 'Tabs');
    check('launch row timed from the launch clock', launches.length === 1 && launches[0].ms === 700, JSON.stringify(launches));

    // Second screen: a request after JOIN_MS (a poll) does not hold it open.
    setPerfScreen('PickDetail');
    const c = wrapped(`${BASE}/rest/v1/picks`);
    clock += JOIN_MS + 500;
    const late = wrapped(`${BASE}/rest/v1/v_live_game_state_latest`);
    clock += 50;
    calls[2].resolve({ status: 200 });
    await c;
    await sleep(QUIET_MS + 50);
    const detail = peekPerfBufferForTests().filter((r) => r.kind === 'screen' && r.name === 'PickDetail');
    check('a request after JOIN_MS does not hold the screen open', detail.length === 1 && detail[0].requestCount === 1, JSON.stringify(detail));
    calls[3].resolve({ status: 200 });
    await late;
    check('only the first screen writes a launch row', peekPerfBufferForTests().filter((r) => r.kind === 'launch').length === 1);

    // A request that starts in the quiet gap after the last one finished
    // keeps the screen open: the screen is loaded when IT finishes.
    setPerfScreen('ModelDetail');
    const d1 = wrapped(`${BASE}/rest/v1/picks`);
    clock += 100;
    calls[4].resolve({ status: 200 });
    await d1;
    await sleep(QUIET_MS / 3);
    clock += 50;
    const d2 = wrapped(`${BASE}/rest/v1/v_model_full_outcome_record`);
    await sleep(QUIET_MS);
    check('a request in the quiet gap holds the screen open', !peekPerfBufferForTests().some((r) => r.kind === 'screen' && r.name === 'ModelDetail'));
    clock += 600;
    calls[5].resolve({ status: 200 });
    await d2;
    await sleep(QUIET_MS + 50);
    const md = peekPerfBufferForTests().filter((r) => r.kind === 'screen' && r.name === 'ModelDetail');
    check('...and the screen is timed to that request', md.length === 1 && md[0].ms === 750 && md[0].requestCount === 2, JSON.stringify(md));

    // A screen that starts no request writes no screen row.
    setPerfScreen('Settings');
    await sleep(QUIET_MS + 50);
    check('a screen with no request writes no row', !peekPerfBufferForTests().some((r) => r.kind === 'screen' && r.name === 'Settings'));
  }

  // --- delivery
  {
    const sent: TimingRow[][] = [];
    let offline = true;
    setup(sent, () => offline);
    const { f, calls } = controllable();
    const p = timedFetch(f)(`${BASE}/rest/v1/picks`);
    calls[0].resolve({ status: 200 });
    await p;
    await flushPerfLog();
    check('offline: the rows stay buffered', sent.length === 0 && peekPerfBufferForTests().length > 0);
    offline = false;
    await flushPerfLog();
    await flushPerfLog();
    const delivered = sent.flat().filter((r) => r.kind === 'request');
    check('back online: delivered once', delivered.length === 1 && peekPerfBufferForTests().length === 0, JSON.stringify(sent));
  }

  if (failures > 0) {
    console.log(`\n${failures} check(s) failed`);
    process.exit(1);
  }
  console.log('\nall checks passed');
}

void main();
