/**
 * Whether a newer app bundle has been downloaded and is waiting for the next
 * time the app starts (a cold start, not a return from the background) (src/lib/otaUpdate.ts: the app never
 * applies one while running, Matt 2026-10-19).
 *
 * Matt, same day: tell the member, quietly, with no button. useOtaUpdates
 * calls markUpdateReady() when a download lands; it returns true only the
 * first time, so the toast shows once per session. Settings reads it to add
 * "update ready" to the version line.
 *
 * No imports, so scripts/verify_ota_update.ts runs it under bare node.
 */

let ready = false;
const listeners = new Set<() => void>();

/** Record that a bundle is waiting. True only on the first call. */
export function markUpdateReady(): boolean {
  if (ready) return false;
  ready = true;
  listeners.forEach((fn) => fn());
  return true;
}

export function isUpdateReady(): boolean {
  return ready;
}

export function subscribeUpdateReady(fn: () => void): () => void {
  listeners.add(fn);
  return () => {
    listeners.delete(fn);
  };
}

/** The once-per-session note (a toast, no action). */
// "Starts", not "open": on iOS a return from the background resumes the old
// bundle, so "open" would read as broken (UX review, 2026-10-19).
export const UPDATE_READY_MESSAGE =
  'A new version of Signalbase is ready. It loads the next time the app starts.';

/** Appended to the Settings version line while a bundle is waiting. */
export const UPDATE_READY_SETTINGS = 'Update ready, loads on next start.';

/** Test hook. */
export function resetUpdateReadyForTests(): void {
  ready = false;
  listeners.clear();
}
