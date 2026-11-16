import { useEffect, useRef } from 'react';
import { AppState } from 'react-native';
import * as Notifications from 'expo-notifications';
import type { NavigationContainerRef } from '@react-navigation/native';

import { routeForPush, type PushRoute } from '@/lib/pushRoute';
import { setSportForVisit } from '@/hooks/useSportFilter';
import { readAuthStatus, useAuth } from '@/hooks/useAuth';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { notePush } from '@/lib/freezeLog';
import type { RootStackParamList } from '@/types';

type NavRef = NavigationContainerRef<RootStackParamList>;

/**
 * Identifiers already acted on in THIS JS runtime. Survives a remount of the
 * hook (Fast Refresh, a parent re-create). Does NOT survive a new JS runtime
 * (a cold start, a dev reload), which is why the native last-response must
 * also be cleared. The app no longer reloads itself for updates
 * (src/lib/otaUpdate.ts).
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
  // No try: a missing native module throws on the subscribe effect's
  // property access first, and that effect never reaches handle(). A
  // second try here would also be the first `try {` in the file, which
  // is what test_the_app_handles_the_cold_start_tap pins.
  const clear = Notifications.clearLastNotificationResponseAsync;
  if (typeof clear !== 'function') return;
  void clear().catch((err) =>
    console.warn('[push] could not clear last notification response', err),
  );
}

/**
 * False while auth is on and the session is signed out. The caller keeps the
 * route and tries again after sign-in. Pick detail stays behind the premium
 * gate, so a free member still does not see the pick.
 */
function shellOpen(): boolean {
  if (!AUTH_ENABLED) return true;
  const status = readAuthStatus();
  return status === 'signedIn' || status === 'disabled';
}

/** Perform a resolved route. One place, so the two callers cannot drift. */
function navigateTo(navRef: NavRef, route: PushRoute): boolean {
  if (AUTH_ENABLED && readAuthStatus() === 'signedOut') return false;
  switch (route.kind) {
    case 'pick':
      navRef.navigate('PickDetail', { pickId: route.pickId });
      return true;
    case 'feedbackThread':
      navRef.navigate('FeedbackThread', { threadId: route.threadId });
      return true;
    case 'board':
      // Sport FIRST: the board is sport-scoped, so navigating before the switch
      // lands shows the wrong sport's picks for a frame and then swaps under
      // the reader. A null sport means the push spanned several, and then the
      // user's own selection is left alone — picking one would hide the rest.
      if (route.sport) setSportForVisit(route.sport);
      navRef.navigate('Tabs', { screen: 'Picks', params: { view: route.view } });
      return true;
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
  const { status } = useAuth();
  // NAVIGATE ONLY ONCE THE APP IS ACTIVE (2026-11-15). Both Pick Detail
  // freezes Matt hit from a push (app_errors 85 and 87, iOS 27.3) have the
  // same trail: `screen PickDetail` logged ~0.2 s BEFORE `app_state active`,
  // then taps that went nowhere with no pop-up open. The same screen opened
  // from the list while active popped normally. A tap on a notification
  // fires the listener while the app is still coming up, and the push was
  // being started in that window. Hold the route until iOS says active.
  // A ref, not state: a state here re-renders the whole App root on every
  // foreground, and the held route would wait a commit after iOS says active.
  const appActiveRef = useRef(AppState.currentState === 'active');
  const pendingRef = useRef<PushRoute | null>(null);
  // `ready` mirrored for the AppState listener, which outlives renders.
  const readyNowRef = useRef(ready);
  readyNowRef.current = ready;

  /** Perform the held route if everything it needs is now true. */
  const replayRef = useRef(() => {});
  replayRef.current = () => {
    if (!appActiveRef.current || !readyNowRef.current || !navRef.isReady()) return;
    if (!shellOpen()) return;
    const route = pendingRef.current;
    if (!route) return;
    pendingRef.current = null;
    notePush('replay');
    navigateTo(navRef, route);
  };

  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      appActiveRef.current = next === 'active';
      if (appActiveRef.current) replayRef.current();
    });
    // Re-read AFTER subscribing. The change to active can land between the
    // first render's read and this effect (a cold start from a notification),
    // and then no event ever reaches the listener: the tap would be held for
    // the whole session.
    appActiveRef.current = AppState.currentState === 'active';
    replayRef.current();
    return () => sub.remove();
  }, []);
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
      if (
        appActiveRef.current &&
        readyRef.current &&
        navRef.isReady() &&
        navigateTo(navRef, route)
      ) {
        return;
      }
      if (!appActiveRef.current) notePush('held');
      pendingRef.current = route;
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

  // Replay whatever arrived before the navigator could take it, and a tap
  // that landed while signed out, once the session is in. A tap held for
  // the app to become active is replayed by the AppState listener above.
  useEffect(() => {
    replayRef.current();
  }, [navRef, ready, status]);
}
