import { useCallback, useEffect, useState } from 'react';
import { AppState, type AppStateStatus } from 'react-native';
import type { Session, User } from '@supabase/supabase-js';

import { supabase } from '@/lib/supabase';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { signOut as signOutRequest } from '@/lib/auth';

/**
 * Auth session state.
 *
 * Module-store + listener set, the same shape as useSportFilter / usePreferredBook,
 * so every mounted consumer sees one source of truth and there's only ever one
 * Supabase auth subscription.
 *
 * While `AUTH_ENABLED` is false this is inert: status pins to 'disabled', no
 * subscription is created, and no AppState listener is attached.
 */

export type AuthStatus = 'disabled' | 'loading' | 'signedIn' | 'signedOut';

interface AuthState {
  status: AuthStatus;
  session: Session | null;
}

const listeners = new Set<(s: AuthState) => void>();

let state: AuthState = {
  status: AUTH_ENABLED ? 'loading' : 'disabled',
  session: null,
};
let bootstrapped = false;

function setState(next: AuthState) {
  state = next;
  listeners.forEach((fn) => fn(next));
}

function applySession(session: Session | null) {
  setState({
    status: session ? 'signedIn' : 'signedOut',
    session,
  });
}

/**
 * supabase-js's `autoRefreshToken` timer doesn't know about app suspension, so
 * on React Native it has to be driven by AppState — otherwise a token can
 * expire while backgrounded and the first request after resume fails. This is
 * the pattern Supabase documents for RN.
 */
function handleAppStateChange(next: AppStateStatus) {
  if (next === 'active') {
    void supabase.auth.startAutoRefresh();
  } else {
    void supabase.auth.stopAutoRefresh();
  }
}

/** Idempotent: subscribes once per app process, no matter how many mounts. */
function bootstrap() {
  if (bootstrapped || !AUTH_ENABLED) return;
  bootstrapped = true;

  supabase.auth
    .getSession()
    .then(({ data }) => applySession(data.session))
    .catch((err) => {
      console.warn('[auth] initial session load failed', err);
      applySession(null);
    });

  // Fires for sign-in, sign-out, token refresh and user updates.
  supabase.auth.onAuthStateChange((_event, session) => {
    applySession(session);
  });

  AppState.addEventListener('change', handleAppStateChange);
  if (AppState.currentState === 'active') {
    void supabase.auth.startAutoRefresh();
  }
}

export interface UseAuth {
  /** 'disabled' whenever the feature flag is off. */
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  email: string | null;
  /** True only for a real signed-in user. False when auth is disabled. */
  signedIn: boolean;
  /** Session resolved (or auth is off) — safe to render an auth-dependent UI. */
  ready: boolean;
  signOut: () => Promise<void>;
}

export function useAuth(): UseAuth {
  const [local, setLocal] = useState<AuthState>(state);

  useEffect(() => {
    bootstrap();
    setLocal(state);
    const listener = (s: AuthState) => setLocal(s);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  const signOut = useCallback(async () => {
    if (!AUTH_ENABLED) return;
    await signOutRequest();
    // onAuthStateChange also fires, but clear immediately so the UI doesn't
    // sit on a stale session while the request round-trips.
    applySession(null);
  }, []);

  const user = local.session?.user ?? null;

  return {
    status: local.status,
    session: local.session,
    user,
    email: user?.email ?? null,
    signedIn: local.status === 'signedIn',
    ready: local.status !== 'loading',
    signOut,
  };
}
