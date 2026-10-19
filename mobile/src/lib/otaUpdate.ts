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
 * the background. A fetched update is applied with reloadAsync() rather than
 * being left for a relaunch that may never come.
 *
 * BUT NOT AT COLD START (2026-10-19). Reloading at launch tore the app down
 * while it was still starting — fonts, navigation, the first screen's reads,
 * the push handler — and Matt saw it as "crashes every now and then when I
 * open it the first time, then works": it happened only on the first open
 * after a new bundle shipped (nine shipped 2026-10-17 → 10-19). So launch now
 * DOWNLOADS only. The downloaded bundle is applied on the next real return
 * from the background (a reload at a moment the app was not on screen), or by
 * expo-updates itself on the next cold start, whichever comes first.
 *
 * Split out of the hook so the decision logic is testable off-device:
 * `shouldCheck` is pure, and `applyPendingUpdate` takes the expo-updates
 * surface as an argument. `scripts/verify_ota_update.ts` drives both.
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
 *   download  launch: check and fetch, never reload (see the header)
 *   reload    a real return with a bundle already downloaded: apply it, no
 *             network needed, and the throttle does not apply — the check
 *             that found it already happened
 *   apply     a real return with nothing pending: check, fetch, reload
 *   skip      not a real return, or inside the throttle window
 */
export type UpdateAction = 'download' | 'reload' | 'apply' | 'skip';

export function nextAction(s: CheckState & { pending: boolean }): UpdateAction {
  if (s.trigger === 'launch') return 'download';
  if (s.backgroundedAt == null || s.now - s.backgroundedAt < MIN_BACKGROUND_MS) return 'skip';
  if (s.pending) return 'reload';
  return shouldCheck(s) ? 'apply' : 'skip';
}

/** The slice of expo-updates this module uses. Injectable so the behaviour can
 *  be verified without a device. */
export interface UpdatesApi {
  /** False in Expo Go and in a dev client — there is no update to fetch. */
  isEnabled: boolean;
  checkForUpdateAsync(): Promise<{ isAvailable: boolean }>;
  fetchUpdateAsync(): Promise<{ isNew: boolean }>;
  reloadAsync(): Promise<void>;
}

export type UpdateOutcome = 'disabled' | 'none' | 'downloaded' | 'reloaded' | 'error';

/** `download` stops after the fetch; `apply` reloads into a new bundle. */
export type UpdateMode = 'download' | 'apply';

/**
 * Check, fetch and APPLY. Returns what happened rather than throwing: an
 * update check failing is not an app error, and there is nothing a user could
 * do about it. Offline, a mid-publish manifest, or an unreachable EAS all land
 * on 'error' and are retried at the next launch or foreground return.
 *
 * `reloadAsync()` does not resolve — it tears the JS context down — so
 * 'reloaded' is returned optimistically after the call is issued, and any
 * throw from it is still caught.
 */
export async function applyPendingUpdate(api: UpdatesApi, mode: UpdateMode = 'apply'): Promise<UpdateOutcome> {
  if (!api.isEnabled) return 'disabled';
  try {
    const check = await api.checkForUpdateAsync();
    if (!check.isAvailable) return 'none';
    const fetched = await api.fetchUpdateAsync();
    // isNew false means the fetch resolved to the bundle already running —
    // reloading would be a pointless flash.
    if (!fetched.isNew) return 'none';
    if (mode === 'download') return 'downloaded';
    await api.reloadAsync();
    return 'reloaded';
  } catch {
    return 'error';
  }
}

/** Apply a bundle an earlier `download` already fetched. Never throws. */
export async function reloadDownloaded(api: UpdatesApi): Promise<UpdateOutcome> {
  if (!api.isEnabled) return 'disabled';
  try {
    await api.reloadAsync();
    return 'reloaded';
  } catch {
    return 'error';
  }
}
