import { useEffect, useRef } from 'react';
import { AppState, Linking } from 'react-native';
import type { NavigationContainerRef } from '@react-navigation/native';

import { readAuthStatus, useAuth } from '@/hooks/useAuth';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { parsePickBooksUrl } from '@/lib/pickBooksLink';
import type { RootStackParamList } from '@/types';

type NavRef = NavigationContainerRef<RootStackParamList>;

type Pending = { pickId: number; token: number };

/**
 * Open the book-picker sheet when the app is launched from
 * `signalbase://pick/<id>` (the Discord landing page).
 *
 * Mounted at the app root, beside usePushDeepLink, so it uses the container
 * ref and a plain effect. useFocusEffect calls useNavigation and throws
 * outside NavigationContainer.
 *
 * A URL that arrives before the navigator is ready, or before iOS says the
 * app is active, is held and replayed. Navigating to Pick Detail in that
 * window is the freeze the push hook already waits out.
 *
 * The launch delivers the URL twice (getInitialURL and the first event).
 * Those two, within a second, are one open. A later tap of the same link
 * is another open: `openBooks` is a new token each time.
 */
export function usePickBooksLink(navRef: NavRef, ready: boolean): void {
  const { status } = useAuth();
  const readyRef = useRef(ready);
  readyRef.current = ready;
  const navRefHolder = useRef(navRef);
  navRefHolder.current = navRef;
  const pending = useRef<Pending | null>(null);
  const token = useRef(0);
  const lastUrl = useRef<string | null>(null);
  const lastAt = useRef(0);

  const flush = useRef(() => {
    if (!readyRef.current) return;
    if (AppState.currentState !== 'active') return;
    if (AUTH_ENABLED && readAuthStatus() === 'signedOut') return;
    const next = pending.current;
    if (next == null) return;
    pending.current = null;
    navRefHolder.current.navigate('PickDetail', {
      pickId: next.pickId,
      openBooks: next.token,
    });
  });

  useEffect(() => {
    const take = (url: string | null) => {
      if (!url) return;
      const id = parsePickBooksUrl(url);
      if (id == null) return;
      const now = Date.now();
      if (lastUrl.current === url && now - lastAt.current < 1000) return;
      lastUrl.current = url;
      lastAt.current = now;
      token.current += 1;
      pending.current = { pickId: id, token: token.current };
      flush.current();
    };
    const sub = Linking.addEventListener('url', (event) => take(event.url));
    Linking.getInitialURL().then(take).catch(() => {});
    const appSub = AppState.addEventListener('change', (state) => {
      if (state === 'active') flush.current();
    });
    return () => {
      sub.remove();
      appSub.remove();
    };
  }, []);

  useEffect(() => {
    flush.current();
  }, [ready, status]);
}
