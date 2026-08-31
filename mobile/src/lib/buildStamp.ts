import * as Updates from 'expo-updates';

/**
 * Which JS bundle this install is actually running.
 *
 * `APP_VERSION` (app.json's `version`) identifies the NATIVE binary and does
 * not move when an OTA ships, so it cannot answer "is my app current?" — and
 * that question was unanswerable on 2026-08-31, when the daily recap on a
 * phone disagreed with the same day's Discord recap purely because the phone
 * was on an older bundle (see src/lib/otaUpdate.ts).
 *
 * `Updates.createdAt` is when the running bundle was PUBLISHED, which is the
 * number worth showing: compare it against the last mobile merge and the
 * answer is immediate. It is null when the embedded (shipped-with-the-binary)
 * bundle is running, which is exactly what a build straight from TestFlight,
 * a dev client, or Expo Go looks like.
 */
export const BUILD_STAMP: string = (() => {
  try {
    const at = Updates.createdAt;
    if (!at) return 'base build';
    return at.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    // expo-updates throws rather than returning null in some dev contexts.
    return 'base build';
  }
})();
