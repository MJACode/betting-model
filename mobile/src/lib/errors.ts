/**
 * errorText — turn anything a catch block can receive into a readable string.
 *
 * WHY: supabase-js does NOT throw. `{ data, error }` hands back a plain object
 * (PostgrestError: `{ message, details, hint, code }`), and every call site in
 * this app re-throws that object. `String(e)` on a plain object is
 * **"[object Object]"** — which is exactly what the Stats tab showed users on
 * 2026-09-01 while PostgREST was answering 503 to every leaderboard RPC. The
 * banner was working; it just had nothing to say.
 *
 * So the order matters: check for a `message` field BEFORE falling back to
 * String(), because the objects that actually reach these handlers are the ones
 * String() cannot render.
 */
export function errorText(e: unknown, fallback = 'Something went wrong'): string {
  if (e == null) return fallback;
  if (typeof e === 'string') return e || fallback;
  if (e instanceof Error) return e.message || fallback;

  if (typeof e === 'object') {
    const o = e as Record<string, unknown>;
    // PostgrestError / AuthError / StorageError all carry `message`; `code` is
    // worth keeping because "PGRST002" (schema cache unavailable) and "57014"
    // (statement timeout) are the difference between "retry" and "report it".
    const msg = typeof o.message === 'string' ? o.message.trim() : '';
    const code = typeof o.code === 'string' ? o.code.trim() : '';
    if (msg && code) return `${msg} (${code})`;
    if (msg) return msg;
    if (code) return code;
    const details = typeof o.details === 'string' ? o.details.trim() : '';
    if (details) return details;
  }

  const s = String(e);
  // The whole point: never hand the user a stringified object.
  return s === '[object Object]' || !s ? fallback : s;
}

/** What kind of failure a load hit, so the copy can say what to do about it. */
export type ErrorKind = 'offline' | 'slow' | 'auth' | 'server';

export interface FriendlyError {
  /** "Couldn’t load today’s MLB picks". Names the thing, never the cause. */
  title: string;
  /** One plain sentence: what happened and what to do. Never the raw text. */
  cause: string;
  kind: ErrorKind;
}

const CAUSE: Record<ErrorKind, string> = {
  offline: 'You’re offline. Check your connection and try again.',
  slow: 'Signalbase is slow to respond right now. Try again in a moment.',
  auth: 'Your session has expired. Try again, or sign out and back in.',
  server: 'Something went wrong on our side. Try again in a moment.',
};

/**
 * Sort a failure into offline / slow / auth / server. Reads the raw text the
 * hooks keep (errorText output) or the thrown value itself. Order matters:
 * "TypeError: Failed to fetch" is offline even though it is also an error, and
 * a PostgREST 57014 is a timeout even though it arrives as a 500.
 */
export function errorKind(e: unknown): ErrorKind {
  const raw = typeof e === 'string' ? e : errorText(e, '');
  if (/failed to fetch|network request failed|network ?error|internet|offline|load failed|aborted|ENOTFOUND|ECONNREFUSED|ERR_NETWORK/i.test(raw)) {
    return 'offline';
  }
  if (/57014|statement timeout|timed? ?out|timeout/i.test(raw)) return 'slow';
  if (/\bJWT\b|PGRST30[0-3]|\b401\b|not authori[sz]ed|invalid claim|session (has )?expired|refresh token/i.test(raw)) {
    return 'auth';
  }
  return 'server';
}

/**
 * PATTERNS §E3 copy for a failed load: a human title that names `what`, a cause
 * class, and NEVER the raw Supabase text (UX_REVIEW §3; usability audit H3/M1).
 * The raw detail stays in the hook's state for dev logging only.
 *
 *   friendlyError(e, 'today’s MLB picks')
 *   → { title: 'Couldn’t load today’s MLB picks', cause: 'You’re offline. …', kind: 'offline' }
 */
export function friendlyError(e: unknown, what: string): FriendlyError {
  const kind = errorKind(e);
  return { title: `Couldn’t load ${what}`, cause: CAUSE[kind], kind };
}

/** Just the cause sentence, for inline one-liners ("Couldn’t load lines. {cause}"). */
export function friendlyCause(e: unknown): string {
  return CAUSE[errorKind(e)];
}
