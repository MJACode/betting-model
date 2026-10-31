/**
 * Load-time logging (2026-10-31, Matt: "improve the performance of the app" —
 * measure first). The server can say how long a query ran; only the phone can
 * say how long a member waited. Three kinds of row, all sent to app_timings:
 *
 *   request  one Supabase call, timed on the phone: network + server. `name` is
 *            the view or table (`v_public_track_record`) or `rpc:<fn>`; query
 *            strings are never sent.
 *   screen   a navigation to a screen until every request it started has
 *            finished and the network has been quiet for QUIET_MS. A screen
 *            that starts no request in its first JOIN_MS writes no row.
 *   launch   the same, for the first screen, measured from when this module
 *            was first evaluated (JS start). Time the OS spends before JS runs
 *            is not visible from here.
 *
 * No imports, so it runs under bare node (scripts/verify_perf_log.ts). It must
 * never break a request: every line of bookkeeping is wrapped, and the wrapped
 * fetch returns or throws exactly what the real one did.
 */

export type TimingKind = 'request' | 'screen' | 'launch';

export interface TimingRow {
  kind: TimingKind;
  name: string;
  ms: number;
  status: number | null;
  screen: string | null;
  requestCount: number | null;
  sinceLaunchMs: number;
  occurredAt: string;
}

export interface PerfLogDeps {
  now: () => number;
  /** Launch clock override (tests). Default: when this module was first evaluated. */
  launchAt?: number;
  send: (rows: TimingRow[]) => Promise<void>;
}

/** A request must START within this long of a navigation to count toward it. */
export const JOIN_MS = 1_500;
/** The network must stay idle this long before a screen counts as loaded. */
export const QUIET_MS = 300;
/** The first screen gets longer to start its reads (auth, access, hydration). */
export const LAUNCH_JOIN_MS = 5_000;
/** Most rows held while a send is failing; the oldest go first. */
export const MAX_BUFFERED = 300;
/** Most rows in one send. The server caps a call at the same number. */
export const MAX_BATCH = 100;

type Fetch = (input: any, init?: any) => Promise<any>;

interface ScreenWindow {
  name: string | null;
  start: number;
  /** When the screen was named. For the launch window this is when navigation
   *  became ready, later than `start` (JS start). */
  namedAt: number;
  joinMs: number;
  launch: boolean;
  pending: Set<number>;
  count: number;
  lastEnd: number;
  quietTimer: ReturnType<typeof setTimeout> | null;
}

let deps: PerfLogDeps | null = null;
let launchAt = Date.now();
let currentScreen: string | null = null;
let windowState: ScreenWindow | null = null;
let buffer: TimingRow[] = [];
let nextId = 1;
let flushing: Promise<void> | null = null;

function now(): number {
  return deps ? deps.now() : Date.now();
}

function push(row: Omit<TimingRow, 'sinceLaunchMs' | 'occurredAt'>, at: number): void {
  buffer.push({ ...row, sinceLaunchMs: Math.max(0, Math.round(at - launchAt)), occurredAt: new Date(at).toISOString() });
  if (buffer.length > MAX_BUFFERED) buffer = buffer.slice(-MAX_BUFFERED);
}

/** Call once, as early as possible: the launch clock and the first window start here. */
export function configurePerfLog(d: PerfLogDeps): void {
  deps = d;
  if (d.launchAt != null) launchAt = d.launchAt;
  windowState = openWindow(null, launchAt, LAUNCH_JOIN_MS, true);
}

function openWindow(name: string | null, start: number, joinMs: number, launch: boolean): ScreenWindow {
  return { name, start, namedAt: start, joinMs, launch, pending: new Set(), count: 0, lastEnd: start, quietTimer: null };
}

function closeWindow(): void {
  if (windowState?.quietTimer) clearTimeout(windowState.quietTimer);
  windowState = null;
}

/** Called on every navigation change. The launch window takes the first name it is given. */
export function setPerfScreen(name: string | null | undefined): void {
  try {
    const n = name ?? null;
    if (n === currentScreen) return;
    currentScreen = n;
    if (windowState && windowState.launch && windowState.name == null) {
      windowState.name = n;
      windowState.namedAt = now();
      return;
    }
    closeWindow();
    if (n != null) windowState = openWindow(n, now(), JOIN_MS, false);
  } catch {
    // never let timing break navigation
  }
}

function settle(w: ScreenWindow): void {
  if (windowState !== w || w.pending.size > 0 || w.count === 0) return;
  const name = w.name ?? 'unknown';
  push({ kind: 'screen', name, ms: Math.max(0, Math.round(w.lastEnd - w.namedAt)), status: null, screen: name, requestCount: w.count }, w.lastEnd);
  if (w.launch) {
    push({ kind: 'launch', name, ms: Math.round(w.lastEnd - launchAt), status: null, screen: name, requestCount: w.count }, w.lastEnd);
  }
  windowState = null;
}

/**
 * `https://x.supabase.co/rest/v1/v_name?select=...` → `v_name`;
 * `/rest/v1/rpc/fn` → `rpc:fn`; `/auth/v1/token` → `auth:token`.
 * Anything else is not ours and is not timed.
 */
export function resourceFromUrl(url: string): string | null {
  const m = /\/(rest|auth|functions)\/v1\/([^?#]*)/.exec(url);
  if (!m) return null;
  const path = m[2].replace(/\/+$/, '');
  if (m[1] === 'rest') return path.startsWith('rpc/') ? `rpc:${path.slice(4)}` : path || null;
  return `${m[1]}:${path.split('/')[0] || 'root'}`;
}

/** Our own reporting calls are not timed, or every send would log a row about itself. */
function isOwnCall(name: string): boolean {
  return name === 'rpc:log_app_timings' || name === 'rpc:log_app_error';
}

function urlOf(input: any): string {
  if (typeof input === 'string') return input;
  if (input && typeof input.url === 'string') return input.url;
  try {
    return String(input);
  } catch {
    return '';
  }
}

function begin(name: string): { id: number; start: number; w: ScreenWindow | null } {
  const start = now();
  const id = nextId++;
  const w = windowState;
  if (w && start - w.start <= w.joinMs) {
    w.pending.add(id);
    w.count++;
    if (w.quietTimer) {
      clearTimeout(w.quietTimer);
      w.quietTimer = null;
    }
    return { id, start, w };
  }
  return { id, start, w: null };
}

function end(name: string, t: { id: number; start: number; w: ScreenWindow | null }, status: number | null): void {
  const at = now();
  push({ kind: 'request', name, ms: Math.round(at - t.start), status, screen: currentScreen, requestCount: null }, at);
  const w = t.w;
  if (!w || windowState !== w) return;
  w.pending.delete(t.id);
  w.lastEnd = Math.max(w.lastEnd, at);
  if (w.pending.size === 0) {
    w.quietTimer = setTimeout(() => settle(w), QUIET_MS);
  }
}

/** Wrap the fetch Supabase uses. The result and any error pass through untouched. */
export function timedFetch(real: Fetch): Fetch {
  return (input: any, init?: any) => {
    let name: string | null = null;
    let t: ReturnType<typeof begin> | null = null;
    try {
      name = resourceFromUrl(urlOf(input));
      if (name && !isOwnCall(name)) t = begin(name);
    } catch {
      t = null;
    }
    const p = real(input, init);
    if (!t || !name) return p;
    const n = name;
    const timer = t;
    return p.then(
      (res: any) => {
        try {
          end(n, timer, typeof res?.status === 'number' ? res.status : null);
        } catch {
          // ignore
        }
        return res;
      },
      (err: unknown) => {
        try {
          end(n, timer, 0); // 0 = no response (offline, timeout, aborted)
        } catch {
          // ignore
        }
        throw err;
      },
    );
  };
}

/**
 * Send what is buffered, MAX_BATCH at a time. A failed send keeps the rows for
 * the next flush. One flush at a time.
 */
export function flushPerfLog(): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    try {
      while (deps && buffer.length > 0) {
        const batch = buffer.slice(0, MAX_BATCH);
        try {
          await deps.send(batch);
        } catch {
          return;
        }
        buffer = buffer.slice(batch.length);
      }
    } finally {
      flushing = null;
    }
  })();
  return flushing;
}

/** For the verify script only. */
export function peekPerfBufferForTests(): TimingRow[] {
  return buffer.slice();
}

export function resetPerfLogForTests(): void {
  closeWindow();
  deps = null;
  currentScreen = null;
  buffer = [];
  nextId = 1;
  flushing = null;
  launchAt = Date.now();
}
