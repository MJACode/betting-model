/**
 * Standalone verification for OTA self-update (src/lib/otaUpdate.ts). Run with:
 *
 *   npx tsx scripts/verify_ota_update.ts
 *
 * Two jobs, both checked here:
 *   * the app finds and DOWNLOADS a published bundle by itself (launch and
 *     every real return), so the next cold start runs it — the 2026-08-31
 *     delivery gap;
 *   * it NEVER applies one to a running app (2026-10-19: the TestFlight
 *     crash was expo-updates aborting on a fatal JS error right after an
 *     in-process reload). UpdatesApi has no reloadAsync at all.
 */

import {
  downloadUpdate,
  nextAction,
  shouldCheck,
  MIN_BACKGROUND_MS,
  MIN_CHECK_INTERVAL_MS,
  type UpdatesApi,
} from '../src/lib/otaUpdate';
import {
  isUpdateReady,
  markUpdateReady,
  resetUpdateReadyForTests,
  subscribeUpdateReady,
  UPDATE_READY_MESSAGE,
} from '../src/lib/updateReady';

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const NOW = 1_700_000_000_000;

// ── shouldCheck ──────────────────────────────────────────────────────────────

check(
  'launch always checks, even with no history',
  shouldCheck({ now: NOW, lastCheckAt: null, backgroundedAt: null, trigger: 'launch' }),
);

// The throttle must never gate launch. A user who force-quits and relaunches
// twice in a minute is the one person actively trying to get the update.
check(
  'launch checks even inside the throttle window',
  shouldCheck({ now: NOW, lastCheckAt: NOW - 1_000, backgroundedAt: null, trigger: 'launch' }),
);

check(
  'a foreground event with no recorded background is ignored',
  !shouldCheck({ now: NOW, lastCheckAt: null, backgroundedAt: null, trigger: 'foreground' }),
);

check(
  'a brief absence (permission sheet) does not trigger a check',
  !shouldCheck({
    now: NOW,
    lastCheckAt: null,
    backgroundedAt: NOW - (MIN_BACKGROUND_MS - 1),
    trigger: 'foreground',
  }),
);

check(
  'a real return from the background triggers a check',
  shouldCheck({
    now: NOW,
    lastCheckAt: null,
    backgroundedAt: NOW - MIN_BACKGROUND_MS,
    trigger: 'foreground',
  }),
);

check(
  'a real return inside the throttle window does NOT re-check',
  !shouldCheck({
    now: NOW,
    lastCheckAt: NOW - (MIN_CHECK_INTERVAL_MS - 1),
    backgroundedAt: NOW - MIN_BACKGROUND_MS,
    trigger: 'foreground',
  }),
);

check(
  'a real return outside the throttle window checks again',
  shouldCheck({
    now: NOW,
    lastCheckAt: NOW - MIN_CHECK_INTERVAL_MS,
    backgroundedAt: NOW - MIN_BACKGROUND_MS,
    trigger: 'foreground',
  }),
);

// The window has to be long enough to survive an overnight background and
// short enough that a normal morning open picks the bundle up.
check(
  'the background threshold is a real absence, not a tap-away',
  MIN_BACKGROUND_MS >= 30_000 && MIN_BACKGROUND_MS <= 10 * 60_000,
  `${MIN_BACKGROUND_MS}ms`,
);

// ── nextAction: download only ─────────────────────────

const away = NOW - MIN_BACKGROUND_MS;
check('launch downloads',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: null, trigger: 'launch' }) === 'download');
check('a real return checks again, even after a download (a newer bundle replaces it)',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: away, trigger: 'foreground' }) === 'download');
check('a brief absence does nothing',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: NOW - (MIN_BACKGROUND_MS - 1), trigger: 'foreground' }) === 'skip');
check('a real return inside the throttle does nothing',
  nextAction({ now: NOW, lastCheckAt: NOW - 1_000, backgroundedAt: away, trigger: 'foreground' }) === 'skip');
check('no trigger can ask for anything but download or skip',
  ['launch', 'foreground'].every((trigger) =>
    ['download', 'skip'].includes(nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: away, trigger: trigger as 'launch' }))));

// ── updateReady: the quiet note shows once per session ──────────────────────

resetUpdateReadyForTests();
{
  let heard = 0;
  const off = subscribeUpdateReady(() => { heard++; });
  check('nothing downloaded: not ready', !isUpdateReady());
  check('the first download is the one that shows the note', markUpdateReady() === true && isUpdateReady());
  check('a second download in the same session does not show it again', markUpdateReady() === false);
  check('Settings is told once', heard === 1, String(heard));
  off();
  check('the note says when it loads and offers no action',
    /next time the app starts/i.test(UPDATE_READY_MESSAGE) && !/\bopen\b/i.test(UPDATE_READY_MESSAGE) && !/tap|restart|refresh/i.test(UPDATE_READY_MESSAGE));
}
resetUpdateReadyForTests();

// ── downloadUpdate ──────────────────────────────────────────────────────────

interface Calls { checked: number; fetched: number }

function fakeApi(over: { available?: boolean; isNew?: boolean; isEnabled?: boolean }): { api: UpdatesApi; calls: Calls } {
  const calls: Calls = { checked: 0, fetched: 0 };
  const api: UpdatesApi = {
    isEnabled: over.isEnabled ?? true,
    checkForUpdateAsync: async () => {
      calls.checked++;
      return { isAvailable: over.available ?? false };
    },
    fetchUpdateAsync: async () => {
      calls.fetched++;
      return { isNew: over.isNew ?? true };
    },
  };
  return { api, calls };
}

async function main(): Promise<void> {
  {
    // Expo Go / dev client: nothing to fetch. A clean no-op, not an error.
    const { api, calls } = fakeApi({ isEnabled: false, available: true });
    const out = await downloadUpdate(api);
    check('disabled updates are a no-op', out === 'disabled' && calls.checked === 0, out);
  }
  {
    const { api, calls } = fakeApi({ available: false });
    const out = await downloadUpdate(api);
    check('nothing available: no fetch', out === 'none' && calls.checked === 1 && calls.fetched === 0, out);
  }
  {
    const { api, calls } = fakeApi({ available: true, isNew: false });
    const out = await downloadUpdate(api);
    check('the bundle already running is not counted as downloaded', out === 'none' && calls.fetched === 1, out);
  }
  {
    // The load-bearing case: a new bundle is fetched, so the next cold
    // start runs it, and nothing is applied to this running app.
    const { api, calls } = fakeApi({ available: true, isNew: true });
    const out = await downloadUpdate(api);
    check('a new bundle is fetched and reported downloaded',
      out === 'downloaded' && calls.checked === 1 && calls.fetched === 1, `${out} fetched=${calls.fetched}`);
  }
  {
    // Offline is the common case, not an exception. It must never surface.
    const { api } = fakeApi({ available: true });
    api.checkForUpdateAsync = async () => {
      throw new Error('network');
    };
    check('a failed check is swallowed', (await downloadUpdate(api)) === 'error');
  }
  {
    const { api } = fakeApi({ available: true });
    api.fetchUpdateAsync = async () => {
      throw new Error('download cut');
    };
    check('a failed download is swallowed', (await downloadUpdate(api)) === 'error');
  }

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
  if (failures > 0) process.exit(1);
}

void main();
