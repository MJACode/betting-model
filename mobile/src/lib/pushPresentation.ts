import * as Notifications from 'expo-notifications';

/**
 * Make a push VISIBLE when the app is already open.
 *
 * iOS hands a notification that arrives in the foreground to the app instead
 * of showing it, and expo-notifications drops it unless a handler says
 * otherwise. Nothing in this app installed one before 2026-09-12, so the very
 * first thing anyone would do to check that notifications work — open the app,
 * trigger a push, watch for it — was guaranteed to show nothing, on a build
 * where everything else was correct. A silent pass for a working system is the
 * same class of bug as a silent failure for a broken one.
 *
 * Banner and list, sound on, badge left alone: the badge is a running count
 * nothing in this app clears, and a number that only ever grows stops meaning
 * anything.
 *
 * Called once from App.tsx module scope. Guarded because a binary built before
 * expo-notifications landed throws on the property access itself, and this file
 * is imported at launch — an unguarded throw here is a white screen, not a
 * missing notification.
 */
export function installNotificationHandler(): void {
  try {
    Notifications.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true,
        shouldShowList: true,
        shouldPlaySound: true,
        shouldSetBadge: false,
      }),
    });
  } catch (err) {
    console.warn('[push] notification handler unavailable', err);
  }
}
