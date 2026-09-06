import { useCallback, useEffect, useRef } from 'react';
import * as Notifications from 'expo-notifications';
import type { NavigationContainerRef } from '@react-navigation/native';

import { routeForPush, type PushRoute } from '@/lib/pushRoute';
import { setSportGlobal } from '@/hooks/useSportFilter';
import type { RootStackParamList } from '@/types';

type NavRef = NavigationContainerRef<RootStackParamList>;

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
      if (route.sport) setSportGlobal(route.sport);
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
 * The cold-start response is sticky: it keeps being returned for the life of
 * the process, so it is consumed exactly once or a remount would re-navigate
 * and the user could never leave the screen.
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
  const coldStartHandledRef = useRef(false);

  const dispatch = useCallback(
    (route: PushRoute) => {
      if (ready && navRef.isReady()) navigateTo(navRef, route);
      else pendingRef.current = route;
    },
    [navRef, ready],
  );

  useEffect(() => {
    let cancelled = false;

    const handle = (response: Notifications.NotificationResponse | null) => {
      if (cancelled || !response) return;
      const route = routeForPush(response.notification.request.content.data);
      // null is the deliberate outcome for a payload this build cannot read:
      // the app simply opens, which is what tapping a notification did before
      // any of this existed.
      if (route) dispatch(route);
    };

    let sub: Notifications.Subscription | undefined;
    try {
      sub = Notifications.addNotificationResponseReceivedListener(handle);
    } catch (err) {
      // No native module (a build without expo-notifications) — the same guard
      // usePushNotifications uses. Deep linking is inert, the app is fine.
      console.warn('[push] response listener unavailable', err);
    }

    // The launch tap, consumed once.
    if (!coldStartHandledRef.current) {
      coldStartHandledRef.current = true;
      Notifications.getLastNotificationResponseAsync()
        .then(handle)
        .catch((err) => console.warn('[push] cold-start response unavailable', err));
    }

    return () => {
      cancelled = true;
      sub?.remove();
    };
  }, [dispatch]);

  // Replay whatever arrived before the navigator could take it.
  useEffect(() => {
    if (!ready || !navRef.isReady()) return;
    const route = pendingRef.current;
    if (!route) return;
    pendingRef.current = null;
    navigateTo(navRef, route);
  }, [navRef, ready]);
}
