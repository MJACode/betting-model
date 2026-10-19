/**
 * Standalone verification for OTA self-update (src/lib/otaUpdate.ts). Run with:
 *
 *   npx tsx scripts/verify_ota_update.ts
 *
 * Pins the behaviour that closes a real, measured delivery gap: a published
 * bundle must be APPLIED without the user force-quitting the app. The daily
 * recap counted in-play picks from 2026-08-30 and the OTA published at 10:41
 * ET that morning, yet on 2026-08-31 the app still rendered the pre-change
 * number while the server-side Discord recap had the corrected one.
 *
 * Two halves, both checked here:
 *   * shouldCheck  — WHEN a check runs (launch always; a foreground return
 *                    only after a real absence, and outside the throttle).
 *   * applyPendingUpdate — that a fetched new bundle is RELOADED, that nothing
 *                    is fetched when nothing is available, and that a throw
 *                    anywhere is swallowed rather than surfaced.
 */

import {
  NO_RELOAD_ROUTES,
  PUSH_TAP_QUIET_MS,
  notePushTap,
  reloadBlockedReason,
  resetReloadGuardForTests,
  setFocusedRoute,
} from '../src/lib/reloadGuard';
import {
  applyPendingUpdate,
  nextAction,
  reloadDownloaded,
  shouldCheck,
  MIN_BACKGROUND_MS,
  MIN_CHECK_INTERVAL_MS,
  type UpdatesApi,
} from '../src/lib/otaUpdate';

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

// ── nextAction: launch never reloads (2026-10-19) ───────────────────────────
// Reloading during cold start was the "crashes the first time I open it" bug:
// it happened only on the first open after a new bundle shipped.

const away = NOW - MIN_BACKGROUND_MS;
check('launch only downloads, never reloads',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: null, trigger: 'launch', pending: false }) === 'download');
check('launch with a bundle already pending still only downloads',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: null, trigger: 'launch', pending: true }) === 'download');
check('a real return with a downloaded bundle reloads it',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: away, trigger: 'foreground', pending: true }) === 'reload');
check('the pending reload is not held back by the check throttle',
  nextAction({ now: NOW, lastCheckAt: NOW - 1_000, backgroundedAt: away, trigger: 'foreground', pending: true }) === 'reload');
check('a brief absence never reloads, even with a bundle pending',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: NOW - (MIN_BACKGROUND_MS - 1), trigger: 'foreground', pending: true }) === 'skip');
check('a real return with nothing pending only downloads (no reload while the member is on screen)',
  nextAction({ now: NOW, lastCheckAt: null, backgroundedAt: away, trigger: 'foreground', pending: false }) === 'download');
check('a real return inside the throttle with nothing pending is skipped',
  nextAction({ now: NOW, lastCheckAt: NOW - 1_000, backgroundedAt: away, trigger: 'foreground', pending: false }) === 'skip');

// ── reloadGuard: a reload must not lose a tapped pick or a draft ────────────

resetReloadGuardForTests();
check('nothing recorded: a reload may go ahead', reloadBlockedReason(NOW) === null);
notePushTap(NOW);
check('a push tap just handled blocks the reload', reloadBlockedReason(NOW + 1_000) === 'push_tap');
check('the tap stops blocking after PUSH_TAP_QUIET_MS', reloadBlockedReason(NOW + PUSH_TAP_QUIET_MS) === null);
resetReloadGuardForTests();
for (const r of ['Feedback', 'FeedbackThread', 'ModelEdit', 'Betslip']) {
  setFocusedRoute(r);
  check(`a draft-holding screen blocks the reload: ${r}`, reloadBlockedReason(NOW) === 'editing');
}
setFocusedRoute('PicksHome');
check('an ordinary screen does not block the reload', reloadBlockedReason(NOW) === null);
check('the draft list is exactly the four in-memory editors', NO_RELOAD_ROUTES.size === 4);
resetReloadGuardForTests();

// ── applyPendingUpdate ───────────────────────────────────────────────────────

interface Calls { checked: number; fetched: number; reloaded: number }

function fakeApi(
  over: Partial<UpdatesApi> & { available?: boolean; isNew?: boolean },
): { api: UpdatesApi; calls: Calls } {
  const calls: Calls = { checked: 0, fetched: 0, reloaded: 0 };
  const api: UpdatesApi = {
    isEnabled: true,
    checkForUpdateAsync: async () => {
      calls.checked++;
      return { isAvailable: over.available ?? false };
    },
    fetchUpdateAsync: async () => {
      calls.fetched++;
      return { isNew: over.isNew ?? true };
    },
    reloadAsync: async () => {
      calls.reloaded++;
    },
    ...(over.isEnabled !== undefined ? { isEnabled: over.isEnabled } : {}),
  };
  return { api, calls };
}

async function main(): Promise<void> {
  {
    // Expo Go / dev client: there is nothing to fetch and reloadAsync would
    // throw. Must be a clean no-op, not an error.
    const { api, calls } = fakeApi({ isEnabled: false, available: true });
    const out = await applyPendingUpdate(api);
    check('disabled updates are a no-op', out === 'disabled' && calls.checked === 0, out);
  }

  {
    const { api, calls } = fakeApi({ available: false });
    const out = await applyPendingUpdate(api);
    check(
      'nothing available: no fetch, no reload',
      out === 'none' && calls.checked === 1 && calls.fetched === 0 && calls.reloaded === 0,
      out,
    );
  }

  {
    // The bundle already running. Reloading would be a flash for nothing.
    const { api, calls } = fakeApi({ available: true, isNew: false });
    const out = await applyPendingUpdate(api);
    check(
      'an already-running bundle is not reloaded',
      out === 'none' && calls.fetched === 1 && calls.reloaded === 0,
      out,
    );
  }

  {
    // THE LOAD-BEARING CASE. A new bundle is fetched and APPLIED in the same
    // session — not left for a relaunch that may never happen.
    const { api, calls } = fakeApi({ available: true, isNew: true });
    const out = await applyPendingUpdate(api);
    check(
      'a new bundle is fetched AND reloaded',
      out === 'reloaded' && calls.checked === 1 && calls.fetched === 1 && calls.reloaded === 1,
      `${out} checked=${calls.checked} fetched=${calls.fetched} reloaded=${calls.reloaded}`,
    );
  }

  {
    // Launch mode: the bundle is fetched and NOT reloaded.
    const { api, calls } = fakeApi({ available: true, isNew: true });
    const out = await applyPendingUpdate(api, 'download');
    check(
      'download mode fetches a new bundle and does NOT reload',
      out === 'downloaded' && calls.fetched === 1 && calls.reloaded === 0,
      `${out} reloaded=${calls.reloaded}`,
    );
  }

  {
    const { api, calls } = fakeApi({});
    const out = await reloadDownloaded(api);
    check('a pending bundle is applied with no network call',
      out === 'reloaded' && calls.reloaded === 1 && calls.checked === 0 && calls.fetched === 0, out);
    api.reloadAsync = async () => { throw new Error('refused'); };
    check('a failed pending reload is swallowed', (await reloadDownloaded(api)) === 'error');
    const off = fakeApi({ isEnabled: false });
    check('a pending reload is a no-op when updates are disabled',
      (await reloadDownloaded(off.api)) === 'disabled' && off.calls.reloaded === 0);
  }

  {
    // Offline is the common case, not an exception. It must never surface.
    const { api } = fakeApi({ available: true });
    api.checkForUpdateAsync = async () => {
      throw new Error('network');
    };
    const out = await applyPendingUpdate(api);
    check('a failed check is swallowed', out === 'error', out);
  }

  {
    const { api, calls } = fakeApi({ available: true, isNew: true });
    api.reloadAsync = async () => {
      throw new Error('reload refused');
    };
    const out = await applyPendingUpdate(api);
    check('a failed reload is swallowed', out === 'error' && calls.fetched === 1, out);
  }

  console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
  if (failures > 0) process.exit(1);
}

void main();
