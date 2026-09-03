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
  applyPendingUpdate,
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
