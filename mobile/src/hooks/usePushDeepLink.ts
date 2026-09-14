import { useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import type { NavigationContainerRef } from '@react-navigation/native';

import { routeForPush, type PushRoute } from '@/lib/pushRoute';
import { setSportForVisit } from '@/hooks/useSportFilter';
import type { RootStackParamList } from '@/types';

type NavRef = NavigationContainerRef<RootStackParamList>;

/**
 * Identifiers already acted on in THIS JS runtime. Survives a remount of the
 * hook (Fast Refresh, a parent re-create). Does NOT survive
 * `Updates.reloadAsync()` — that starts a new runtime, which is why the
 * native last-response must also be cleared. `useOtaUpdates` reloads on
 * launch and on foreground whenever a bundle is waiting.
 */
const handledResponseIds = new Set<string>();

function responseIdentifier(
  response: Notifications.NotificationResponse,
): string | null {
  const id = response.notification.request.identifier;
  return typeof id === 'string' && id.length > 0 ? id : null;
}

/** Drop the sticky native last-response so a later remount cannot re-open it. */
function clearNativeLastResponse(): void {
  try {
    const clear = Notifications.clearLastNotificationResponseAsync;
    if (typeof clear !== 'function') return;
    void clear().catch((err) =>
      console.warn('[push] could not clear last notification response', err),
    );
  } catch (err) {
    console.warn('[push] could not clear last notification response', err);
  }
}

/** Perform a resolved route. One place, so the two callers cannot drift. */
function navigateTo(navRef: NavRef, route: PushRoute): void {
  switch (route.kind) {
    case 'pick':
      navRef.navigate('PickDetail', { pickId: route.pickId });
      return;
    case 'feedbackThread':
      navRef.navigate('FeedbackThread', { threadId: route.threadId });
      return;
    case 'board':
      // Sport FIRST: the board is sport-scoped, so navigating before the switch
      // lands shows the wrong sport's picks for a frame and then swaps under
      // the reader. A null sport means the push spanned several, and then the
      // user's own selection is left alone — picking one would hide the rest.
      if (route.sport) setSportForVisit(route.sport);
      navRef.navigate('Tabs', { screen: 'Picks', params: { view: route.view } });
      return;
  }
}

/**
 * Send a tapped notification to the thing it is about.
 *
 * TWO ENTRY POINTS, AND THE SECOND IS THE ONE THAT GETS FORGOTTEN.
 *
 *  1. The app is running (foreground or backgrounded) and the user taps:
 *     `addNotificationResponseReceivedListener` fires.
 *  2. The app was NOT running and the tap LAUNCHED it: no listener exists yet
 *     when the OS hands the response over, so nothing fires. That response is
 *     only retrievable from `getLastNotificationResponseAsync()`. Handling only
 *     (1) means deep links work in testing — where the app is always already
 *     open — and silently do nothing for the user who taps a notification on a
 *     locked phone, which is most of them.
 *
 * The cold-start response is sticky on the native side: Expo keeps returning
 * it until `clearLastNotificationResponseAsync` runs. Consume it exactly
 * once — identifier de-dupe in this runtime, native clear for the next —
 * or a remount (this app's OTA reload, Fast Refresh) re-opens the pick
 * and the user can never leave it.
 *
 * Navigation goes through the container ref, not a screen's `navigation` prop,
 * because this is mounted at the app root — where BetslipBar sits, outside
 * NavigationContainer. Hence no `useFocusEffect` here either
 * (`.claude/rules/frontend.md`: it calls useNavigation(), which throws there).
 * On a cold start the ref is not ready when the response arrives, so a route
 * that lands early is held and replayed once `ready` flips.
 */
export function usePushDeepLink(navRef: NavRef, ready: boolean): void {
  const pendingRef = useRef<PushRoute | null>(null);
  // `ready` in a ref, read at dispatch time. It must NOT be an effect
  // dependency: `ready` always goes false -> true on launch (onReady fires
  // after the first render), so a dependency on it guarantees one teardown —
  // and the teardown used to cancel the in-flight cold-start lookup while the
  // once-guard stopped it ever being retried. The launch tap, the case this
  // hook exists for, was dropped on essentially every cold start, and the
  // warm path worked perfectly, so nothing on a developer's phone showed it
  // (UX review, 2026-09-06).
  const readyRef = useRef(ready);
  useEffect(() => {
    readyRef.current = ready;
  }, [ready]);

  useEffect(() => {
    const dispatch = (route: PushRoute) => {
      if (readyRef.current && navRef.isReady()) navigateTo(navRef, route);
      else pendingRef.current = route;
    };

    const handle = (response: Notifications.NotificationResponse | null) => {
      if (!response) return;
      // The listener AND getLast can both deliver the same tap (Android
      // cold start; a remount while the native last-response is still set).
      // Act once. An empty identifier is rare; we still clear the native
      // copy so the next runtime cannot replay it.
      const id = responseIdentifier(response);
      if (id != null) {
        if (handledResponseIds.has(id)) return;
        handledResponseIds.add(id);
      }
      clearNativeLastResponse();
      const route = routeForPush(response.notification.request.content.data);
      // null is the deliberate outcome for a payload this build cannot read:
      // the app simply opens, which is what tapping a notification did before
      // any of this existed.
      if (route) dispatch(route);
    };

    let sub: Notifications.Subscription | undefined;
    try {
      sub = Notifications.addNotificationResponseReceivedListener(handle);
      // The launch tap. INSIDE the same try: without a native module the
      // property access throws synchronously, out of the effect body, where
      // the .catch below never sees it — a red screen on launch instead of the
      // inert no-op the guard promises.
      Notifications.getLastNotificationResponseAsync()
        .then(handle)
        .catch((err) => console.warn('[push] cold-start response unavailable', err));
    } catch (err) {
      // No native module (a build without expo-notifications) — the same guard
      // usePushNotifications uses. Deep linking is inert, the app is fine.
      console.warn('[push] notifications unavailable', err);
    }

    return () => sub?.remove();
    // Mounted once, for the app's lifetime. navRef is a stable container ref.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Replay whatever arrived before the navigator could take it.
  useEffect(() => {
    if (!ready || !navRef.isReady()) return;
    const route = pendingRef.current;
    if (!route) return;
    pendingRef.current = null;
    navigateTo(navRef, route);
  }, [navRef, ready]);
}
