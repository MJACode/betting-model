import { useCallback, useEffect, useState } from 'react';

import {
  NO_ACCESS,
  fetchAccess,
  linkDiscord,
  unlinkDiscord,
  type AccessRow,
} from '@/lib/discord';
import { discordLinkReady } from '@/lib/discordConfig';
import { billingReady } from '@/lib/billingConfig';
import { useAuth } from './useAuth';

/**
 * The signed-in user's whole access picture, from `public.my_access()`.
 *
 * ONE read answers both halves of the membership rule: an app subscription and
 * a Whop-sold Discord membership are ORed in the database, so the client never
 * has to know which one paid. That matters beyond tidiness — computing it here
 * would mean the app and any future server-side gate could disagree, and the
 * user would see a different answer depending on who asked.
 *
 * Module-store + listener set, the same shape as useAuth / useSportFilter, so
 * every mounted consumer sees one source of truth and there is only ever one
 * in-flight fetch.
 *
 * Two behaviours worth knowing, both inherited from useSubscription because
 * they were right there:
 *
 *  - When billing AND Discord linking are both off, this is inert and
 *    `entitled` is TRUE. Everything is free today, so a flag that is off must
 *    never lock users out of what they already have.
 *
 *  - A failed refresh keeps the LAST GOOD row rather than dropping to
 *    NO_ACCESS. A network blip must not paywall a paying user mid-slate; the
 *    server-side check is the real boundary anyway.
 */

interface AccessState {
  access: AccessRow;
  loading: boolean;
  error: string | null;
  /** True once a real fetch has resolved (or the feature is off). */
  loaded: boolean;
}

const listeners = new Set<(s: AccessState) => void>();

/** Any gate at all? With both flags dark there is nothing to ask about. */
function accessEnabled(): boolean {
  return billingReady() || discordLinkReady();
}

let state: AccessState = {
  access: NO_ACCESS,
  loading: accessEnabled(),
  error: null,
  loaded: !accessEnabled(),
};
let inFlight: Promise<void> | null = null;

function setState(next: Partial<AccessState>) {
  state = { ...state, ...next };
  listeners.forEach((fn) => fn(state));
}

/** Collapses concurrent refreshes — several screens mount at once on launch. */
async function refreshAccess(signedIn: boolean): Promise<void> {
  if (!accessEnabled() || !signedIn) {
    setState({ access: NO_ACCESS, loading: false, loaded: true, error: null });
    return;
  }
  if (inFlight) return inFlight;

  setState({ loading: true });
  inFlight = (async () => {
    try {
      const row = await fetchAccess();
      setState({ access: row, error: null, loaded: true });
    } catch (e) {
      // Keep the previous row — see the note above about not paywalling on a blip.
      setState({ error: e instanceof Error ? e.message : String(e), loaded: true });
    } finally {
      setState({ loading: false });
      inFlight = null;
    }
  })();
  return inFlight;
}

export interface UseAccess {
  access: AccessRow;
  /** Access to paid features. True whenever both gates are disabled. */
  entitled: boolean;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
  /** Run the Discord OAuth flow. Resolves false when the user cancels. */
  link: () => Promise<boolean>;
  unlink: () => Promise<void>;
  /** A link or unlink is in flight — disable the button. */
  busy: boolean;
}

export function useAccess(): UseAccess {
  const { signedIn, status: authStatus } = useAuth();
  const [local, setLocal] = useState<AccessState>(state);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setLocal(state);
    const listener = (s: AccessState) => setLocal(s);
    listeners.add(listener);
    return () => {
      listeners.delete(listener);
    };
  }, []);

  useEffect(() => {
    if (authStatus === 'loading') return;
    void refreshAccess(signedIn);
  }, [authStatus, signedIn]);

  const refresh = useCallback(() => refreshAccess(signedIn), [signedIn]);

  const link = useCallback(async () => {
    setBusy(true);
    try {
      const result = await linkDiscord();
      if (result.outcome === 'cancelled') return false;
      // The function already returned the fresh row; adopt it rather than
      // spending another round trip re-asking the question we just answered.
      setState({ access: result.access, error: null, loaded: true });
      return true;
    } finally {
      setBusy(false);
    }
  }, []);

  const unlink = useCallback(async () => {
    setBusy(true);
    try {
      setState({ access: await unlinkDiscord(), error: null, loaded: true });
    } finally {
      setBusy(false);
    }
  }, []);

  return {
    access: local.access,
    entitled: !accessEnabled() ? true : local.access.entitled,
    loading: local.loading,
    error: local.error,
    refresh,
    link,
    unlink,
    busy,
  };
}
