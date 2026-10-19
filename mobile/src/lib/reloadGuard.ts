/**
 * When an OTA reload must wait (2026-10-19, UX review of the first-open fix).
 *
 * A reload starts a new JS runtime, so whatever lives only in memory is lost:
 * the navigation stack, scroll, and every unsaved text field. Two moments make
 * that loss real, and on both the reload is skipped; the bundle stays
 * downloaded and is applied at the next return or by expo-updates at the next
 * cold start.
 *
 *   push_tap  a notification tap was just handled. usePushDeepLink clears the
 *             native last-response when it handles a tap, so a reload right
 *             after it would land on Picks instead of the tapped pick.
 *   editing   the focused screen holds a draft only in memory: a feedback
 *             message or reply, a custom model, the betslip's custom leg.
 *
 * No imports, so scripts/verify_ota_update.ts runs it under bare node.
 */

/** Wait this long after the app comes back before deciding, so a push tap
 *  that is landing at the same moment has been handled and recorded. */
export const RELOAD_SETTLE_MS = 1_000;

/** A reload this soon after a handled push tap is skipped. */
export const PUSH_TAP_QUIET_MS = 5_000;

/** Routes whose screen keeps a draft only in component state. */
export const NO_RELOAD_ROUTES: ReadonlySet<string> = new Set([
  'Feedback',
  'FeedbackThread',
  'ModelEdit',
  'Betslip',
]);

let lastPushTapAt: number | null = null;
let focusedRoute: string | null = null;

export function notePushTap(now: number = Date.now()): void {
  lastPushTapAt = now;
}

export function setFocusedRoute(name: string | null | undefined): void {
  focusedRoute = name ?? null;
}

export type ReloadBlock = 'push_tap' | 'editing' | null;

/** Why a reload must wait right now, or null when it may go ahead. */
export function reloadBlockedReason(now: number = Date.now()): ReloadBlock {
  if (lastPushTapAt != null && now - lastPushTapAt < PUSH_TAP_QUIET_MS) return 'push_tap';
  if (focusedRoute != null && NO_RELOAD_ROUTES.has(focusedRoute)) return 'editing';
  return null;
}

/** Test hook. */
export function resetReloadGuardForTests(): void {
  lastPushTapAt = null;
  focusedRoute = null;
}
