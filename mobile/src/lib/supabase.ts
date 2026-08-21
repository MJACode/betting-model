import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';

import { AUTH_ENABLED } from './authConfig';

const SUPABASE_URL = process.env.EXPO_PUBLIC_SUPABASE_URL ?? '';
const SUPABASE_ANON_KEY = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY ?? '';

if (!SUPABASE_URL || !SUPABASE_ANON_KEY) {
  console.warn(
    '[supabase] EXPO_PUBLIC_SUPABASE_URL / EXPO_PUBLIC_SUPABASE_ANON_KEY missing. ' +
      'Copy mobile/.env.example to mobile/.env and fill in values.',
  );
}

/**
 * Session handling is gated on the auth feature flag.
 *
 * While auth is off these stay exactly as they have always been (no session is
 * persisted, no refresh timer runs), so turning the flag on is the only thing
 * that changes client behavior. When it's on, supabase-js persists the session
 * to AsyncStorage and refreshes it in the background.
 *
 * `detectSessionInUrl` stays false on native — there is no URL bar to read; we
 * hand the OAuth callback to supabase-js ourselves in lib/auth.ts.
 *
 * `flowType: 'pkce'` is set unconditionally. It's inert with auth off, and PKCE
 * is required for the browser-based OAuth round trip to be safe on a public
 * client: the code that comes back is worthless without the verifier held in
 * this app's storage.
 */
export const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  auth: {
    storage: AsyncStorage,
    autoRefreshToken: AUTH_ENABLED,
    persistSession: AUTH_ENABLED,
    detectSessionInUrl: false,
    flowType: 'pkce',
  },
});

export const SUPABASE_PROJECT_REF = (() => {
  const match = SUPABASE_URL.match(/https:\/\/([^.]+)\.supabase\.co/);
  return match ? match[1] : 'unknown';
})();
