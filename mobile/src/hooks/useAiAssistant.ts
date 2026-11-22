import { useCallback, useEffect, useState } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';

import type { McpStatus } from '@/lib/aiAssistant';
import { LAST_ENTITLEMENT_KEY } from '@/lib/aiAssistant';
import { disconnectMcpAssistant, fetchMcpStatus } from '@/lib/aiAssistantApi';
import { AUTH_ENABLED } from '@/lib/authConfig';
import { errorText, isAbortError } from '@/lib/errors';
import { useAuth } from './useAuth';

/**
 * The member's AI Assistant status, from `public.mcp_my_status()`.
 *
 * One module store, the same shape as useAccess: Settings, its tile and the
 * Picks intro card mount together, so there is one in-flight read and every
 * consumer sees the same row. Signed out, or with sign-in off, it is null,
 * and every surface hides.
 *
 * A failed refresh keeps the last good row: a blip must not flip a connected
 * member to "set it up". The server is the boundary either way.
 *
 * Plain useEffect, not the focus-aware hook: the Picks card is not app-root today,
 * but the rule (frontend.md) costs nothing to follow here.
 */

interface State {
  status: McpStatus | null;
  loading: boolean;
  error: string | null;
  /** The entitlement last seen on this device, read BEFORE this fetch wrote it. */
  previousEntitlement: string | null;
  loaded: boolean;
}

let state: State = { status: null, loading: false, error: null, previousEntitlement: null, loaded: false };
const listeners = new Set<(s: State) => void>();
let inFlight: Promise<void> | null = null;
let previousRead = false;

function setState(next: Partial<State>) {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn(state));
}

async function refresh(signedIn: boolean): Promise<void> {
  if (!AUTH_ENABLED || !signedIn) {
    setState({ status: null, loading: false, error: null, loaded: true });
    return;
  }
  if (inFlight) return inFlight;
  setState({ loading: true });
  inFlight = (async () => {
    try {
      if (!previousRead) {
        previousRead = true;
        let prev: string | null = null;
        try {
          prev = await AsyncStorage.getItem(LAST_ENTITLEMENT_KEY);
        } catch {
          prev = null;
        }
        setState({ previousEntitlement: prev });
      }
      const status = await fetchMcpStatus();
      setState({ status, error: null, loaded: true });
      try {
        await AsyncStorage.setItem(LAST_ENTITLEMENT_KEY, status.entitlement);
      } catch {
        /* storage off: the unlocked sheet simply does not show */
      }
    } catch (e) {
      setState({ error: isAbortError(e) ? null : errorText(e), loaded: true });
    } finally {
      setState({ loading: false });
      inFlight = null;
    }
  })();
  return inFlight;
}

export interface UseAiAssistant {
  status: McpStatus | null;
  previousEntitlement: string | null;
  loading: boolean;
  loaded: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /**
   * Disconnect one assistant (null: every one, on a server that has no list),
   * then re-read. Throws on failure so the caller can say so.
   */
  disconnect: (assistant: string | null) => Promise<void>;
}

export function useAiAssistant(): UseAiAssistant {
  const { signedIn, status: authStatus } = useAuth();
  const [local, setLocal] = useState<State>(state);

  useEffect(() => {
    setLocal(state);
    const fn = (s: State) => setLocal(s);
    listeners.add(fn);
    return () => {
      listeners.delete(fn);
    };
  }, []);

  useEffect(() => {
    if (authStatus === 'loading') return;
    void refresh(signedIn);
  }, [authStatus, signedIn]);

  const doRefresh = useCallback(() => refresh(signedIn), [signedIn]);
  const disconnect = useCallback(async (assistant: string | null) => {
    await disconnectMcpAssistant(assistant);
    // A read already in flight may have started before the disconnect; wait
    // for it, then read again so the list reflects the server after it.
    if (inFlight) {
      try {
        await inFlight;
      } catch {
        /* its error is already in state */
      }
    }
    await refresh(signedIn);
  }, [signedIn]);

  return {
    status: local.status,
    previousEntitlement: local.previousEntitlement,
    loading: local.loading,
    loaded: local.loaded,
    error: local.error,
    refresh: doRefresh,
    disconnect,
  };
}
