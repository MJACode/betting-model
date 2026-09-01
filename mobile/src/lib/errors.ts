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
