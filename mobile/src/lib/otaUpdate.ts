/**
 * OTA self-update policy — the half of over-the-air delivery that lives in the
 * app rather than in CI.
 *
 * WHY THIS EXISTS. `.github/workflows/mobile-ota.yml` publishes every JS-only
 * merge to the `production` channel within minutes, and it has done so
 * reliably. Publishing is not delivering. expo-updates' default behaviour is
 * check-on-launch and apply on the NEXT cold launch, so an installed build
 * shows the previous bundle until the user force-quits and relaunches TWICE —
 * which nobody does. iOS keeps an app resident for days.
 *
 * That gap is not theoretical. The daily recap started counting in-play picks
 * on 2026-08-30 (published to the production channel at 10:41 ET). On
 * 2026-08-31 at 11:13 the app still showed Sunday's MLB day as 7 picks, 2-5,
 * -$325.93 — the pre-change number — while the Discord recap, computed
 * server-side from the same rows, had already posted 10-6 / +11.4% with 9
 * in-play bets. Same data, same thresholds; the phone was simply running an
 * older bundle.
 *
 * So the app checks for itself: at cold start, and on every real return from
 * the background, and DOWNLOADS what it finds. It never applies a bundle to a
 * running app. expo-updates launches the newest downloaded bundle at the next
 * cold start, so the 2026-08-31 gap is now "one fresh start", not "two". A
 * return keeps checking after a download, so a second bundle published in
 * the same session replaces the first rather than waiting a launch.
 *
 * WHY IT NEVER RELOADS (Matt, 2026-10-19, option A). Applying a bundle meant
 * Updates.reloadAsync(), which starts a new JS runtime inside the running
 * process. Matt's TestFlight crash report of 10:41 ET that day shows the
 * process launched at 09:04 and aborted at 10:41 in expo-updates'
 * ErrorRecovery.crash(): a fatal JS error within its 10 s window after first
 * render (docs.expo.dev/eas-update/error-recovery), i.e. right after an
 * in-process reload on return from the background, the first return after
 * #1003 published at 10:18. The same bundle opened cleanly from cold. A
 * reload at launch had already been removed (it was the first theory); this
 * removes the other one. There is no reloadAsync in UpdatesApi, so no caller
 * can bring it back without tests/test_mobile_ota_self_update.py failing.
 *
 * Split out of the hook so the decision logic is testable off-device:
 * `shouldCheck` and `nextAction` are pure, and `downloadUpdate` takes the
 * expo-updates surface as an argument. `scripts/verify_ota_update.ts` drives
 * all three.
 */

/** A foreground return only counts if the app was actually away this long —
 *  dismissing a permission sheet or the share sheet is not a return. */
export const MIN_BACKGROUND_MS = 60_000;

/** Never hit the update server more often than this, whatever the trigger. */
export const MIN_CHECK_INTERVAL_MS = 5 * 60_000;

export type CheckTrigger = 'launch' | 'foreground';

export interface CheckState {
  now: number;
  /** When a check last STARTED, or null if none has. */
  lastCheckAt: number | null;
  /** When the app went to the background, or null if it hasn't. */
  backgroundedAt: number | null;
  trigger: CheckTrigger;
}

/**
 * Whether to run an update check now.
 *
 * Launch always checks — it is the one moment with no session to interrupt,
 * and the throttle must not let a fast relaunch cycle skip it. A foreground
 * return checks only after a real absence, and never inside the throttle
 * window.
 */
export function shouldCheck(s: CheckState): boolean {
  if (s.trigger === 'launch') return true;
  if (s.backgroundedAt == null) return false;
  if (s.now - s.backgroundedAt < MIN_BACKGROUND_MS) return false;
  if (s.lastCheckAt != null && s.now - s.lastCheckAt < MIN_CHECK_INTERVAL_MS) return false;
  return true;
}

/**
 * What to do for one trigger. Pure.
 *
 *   download  launch, or a real return with the throttle clear: check and
 *             fetch (a newer bundle replaces one already downloaded)
 *   skip      not a real return, or inside the throttle window
 */
export type UpdateAction = 'download' | 'skip';

export function nextAction(s: CheckState): UpdateAction {
  if (s.trigger === 'launch') return 'download';
  return shouldCheck(s) ? 'download' : 'skip';
}

/** The slice of expo-updates this module uses. Injectable so the behaviour can
 *  be verified without a device. Deliberately no reloadAsync (see header). */
export interface UpdatesApi {
  /** False in Expo Go and in a dev client — there is no update to fetch. */
  isEnabled: boolean;
  checkForUpdateAsync(): Promise<{ isAvailable: boolean }>;
  fetchUpdateAsync(): Promise<{ isNew: boolean }>;
}

export type UpdateOutcome = 'disabled' | 'none' | 'downloaded' | 'error';

/**
 * Check and fetch. Never applies: expo-updates launches a downloaded bundle at
 * the next cold start. Returns what happened rather than throwing: offline, a
 * mid-publish manifest or an unreachable EAS all land on 'error' and are
 * retried at the next launch or real return.
 */
export async function downloadUpdate(api: UpdatesApi): Promise<UpdateOutcome> {
  if (!api.isEnabled) return 'disabled';
  try {
    const check = await api.checkForUpdateAsync();
    if (!check.isAvailable) return 'none';
    const fetched = await api.fetchUpdateAsync();
    // isNew false means the fetch resolved to the bundle already running.
    return fetched.isNew ? 'downloaded' : 'none';
  } catch {
    return 'error';
  }
}
