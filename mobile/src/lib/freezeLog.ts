/**
 * Freeze and restart tracking (2026-11-06, Matt: "Back button was not working
 * on this screen … Cannot move from that screen need to restart. This keeps
 * happening in other spots"). The crash log saw nothing: a frozen screen
 * throws no error. This module records what the app was doing, so the next
 * freeze leaves evidence.
 *
 * Three parts:
 *   - a TRAIL: the last MAX_TRAIL things that happened (screens, pop-ups
 *     opening and closing, taps, app going to background, stalls). Every
 *     app_errors report carries it in extra.trail (crashLog's trail provider).
 *   - a SESSION record saved to storage every few seconds, so the NEXT launch
 *     can see how the last one ended and report a `restart` when it looks
 *     like the member had to kill the app.
 *   - two live alarms: `js_stall` (the JS thread stopped for STALL_MS or
 *     more, so nothing on screen could respond) and `modal_stuck` (a pop-up
 *     was told to open or close and iOS never confirmed it — the classic
 *     invisible layer that swallows every tap).
 *
 * No imports, like crashLog.ts, so scripts/verify_freeze_log.ts drives it
 * under bare node. Nothing here may throw.
 */

export type CrumbKind =
  | 'launch'
  | 'screen'
  | 'touch'
  | 'app_state'
  | 'modal_open'
  | 'modal_shown'
  | 'modal_close'
  | 'modal_dismissed'
  | 'stall';

export interface Crumb {
  /** ms epoch. */
  t: number;
  k: CrumbKind;
  /** Screen / modal name, app state, or a tap count for coalesced taps. */
  d?: string;
}

export type AppStateName = 'active' | 'inactive' | 'background' | 'unknown' | 'extension';

export interface SessionRecord {
  launchAt: number;
  /** Last time this session saved itself. */
  savedAt: number;
  appState: AppStateName;
  /** When the app last went to background, if it is there now. */
  backgroundAt: number | null;
  screen: string | null;
  lastTouchAt: number | null;
  /** Taps since the screen last changed: many taps and no navigation = stuck. */
  touchesSinceNav: number;
  /** Pop-ups the app believes are open right now. */
  openModals: string[];
  trail: Crumb[];
}

export type FreezeReportKind = 'restart' | 'js_stall' | 'modal_stuck';

export interface FreezeLogDeps {
  storage: {
    getItem(key: string): Promise<string | null>;
    setItem(key: string, value: string): Promise<void>;
  };
  now(): number;
  /** Send one report through the crash log (queued, retried). */
  report(kind: FreezeReportKind, message: string, extra: Record<string, unknown>, screen?: string | null): void;
  setTimeout(fn: () => void, ms: number): unknown;
  clearTimeout(handle: unknown): void;
  setInterval(fn: () => void, ms: number): unknown;
}

export const SESSION_KEY = 'freezelog.session';
export const MAX_TRAIL = 40;
/** The trail attached to a report is trimmed to this many characters. */
export const MAX_TRAIL_CHARS = 3_000;
/** Save the session at most this often while active. */
export const SAVE_EVERY_MS = 5_000;
/** The stall watchdog ticks this often. */
export const TICK_MS = 2_000;
/** A gap this long between ticks, while active, is a stall. */
export const STALL_MS = 5_000;
/** iOS gets this long to confirm a pop-up opened or closed. */
export const MODAL_CONFIRM_MS = 4_000;
/** A relaunch this soon after going to background counts as a restart. */
export const QUICK_RELAUNCH_MS = 120_000;
/** Sessions shorter than this are already covered by crashLog's early_exit. */
export const MIN_SESSION_MS = 15_000;
/** At most this many stall reports per launch. */
export const MAX_STALL_REPORTS = 3;

let deps: FreezeLogDeps | null = null;
let session: SessionRecord | null = null;
let lastSave = 0;
let lastTick = 0;
let stallReports = 0;
const reportedModal = new Set<string>();
const modalTimers = new Map<string, unknown>();

function safe(fn: () => void): void {
  try {
    fn();
  } catch {
    // never throw from the logger
  }
}

function crumb(k: CrumbKind, d?: string): void {
  if (!session || !deps) return;
  const t = deps.now();
  const last = session.trail[session.trail.length - 1];
  // Coalesce a run of taps into one crumb carrying the count.
  if (k === 'touch' && last && last.k === 'touch') {
    last.d = String(Number(last.d ?? '1') + 1);
    last.t = t;
    return;
  }
  session.trail.push(d === undefined ? { t, k } : { t, k, d: d.slice(0, 60) });
  if (session.trail.length > MAX_TRAIL) session.trail.splice(0, session.trail.length - MAX_TRAIL);
}

function save(force = false): void {
  if (!session || !deps) return;
  const now = deps.now();
  if (!force && now - lastSave < SAVE_EVERY_MS) return;
  lastSave = now;
  session.savedAt = now;
  const d = deps;
  const body = JSON.stringify(session);
  void d.storage.setItem(SESSION_KEY, body).catch(() => undefined);
}

/**
 * The trail as it goes on a report: newest last, each entry `[seconds before
 * the report, kind, detail]`, oldest entries dropped until it fits.
 */
export function trailForReport(): Array<[number, CrumbKind, string?]> | null {
  if (!session || !deps) return null;
  const now = deps.now();
  const rows = session.trail.map((c): [number, CrumbKind, string?] =>
    c.d === undefined
      ? [Math.round((now - c.t) / 100) / 10, c.k]
      : [Math.round((now - c.t) / 100) / 10, c.k, c.d],
  );
  while (rows.length > 0 && JSON.stringify(rows).length > MAX_TRAIL_CHARS) rows.shift();
  return rows;
}

/** A short summary of the live session, attached beside the trail. */
export function sessionSummary(): Record<string, unknown> | null {
  if (!session || !deps) return null;
  const now = deps.now();
  return {
    app_state: session.appState,
    open_modals: session.openModals,
    touches_since_nav: session.touchesSinceNav,
    since_last_touch_ms: session.lastTouchAt == null ? null : now - session.lastTouchAt,
    session_ms: now - session.launchAt,
  };
}

/**
 * What the previous session's record says about how it ended. Pure.
 *
 * - Last saved state `active` or `inactive`: the app ended while on screen
 *   or in the app switcher, with no move to background. A crash, iOS killing
 *   a hung app, or the member swiping it away from the switcher.
 * - Last saved state `background` and this launch within QUICK_RELAUNCH_MS:
 *   it was closed and opened again almost at once, which is what a member
 *   does when the screen will not respond. (iOS reclaiming a backgrounded app
 *   can land here too; the trail tells them apart.)
 * - Anything else is a normal end and reports nothing.
 *
 * Sessions shorter than MIN_SESSION_MS are skipped: crashLog's early_exit
 * already reports those.
 */
export function restartFrom(prev: SessionRecord | null, now: number): {
  message: string;
  screen: string | null;
  extra: Record<string, unknown>;
} | null {
  if (!prev || typeof prev.launchAt !== 'number' || typeof prev.savedAt !== 'number') return null;
  if (prev.savedAt - prev.launchAt < MIN_SESSION_MS) return null;
  const endedInBackground = prev.appState === 'background';
  const sinceBackground = prev.backgroundAt == null ? null : now - prev.backgroundAt;
  if (endedInBackground && (sinceBackground == null || sinceBackground > QUICK_RELAUNCH_MS)) return null;
  const last = prev.trail ?? [];
  const lastAt = last.length > 0 ? last[last.length - 1].t : prev.savedAt;
  const trail = last.map((c): [number, CrumbKind, string?] => {
    const ago = Math.round((lastAt - c.t) / 100) / 10;
    return c.d === undefined ? [ago, c.k] : [ago, c.k, c.d];
  });
  while (trail.length > 0 && JSON.stringify(trail).length > MAX_TRAIL_CHARS) trail.shift();
  return {
    message: endedInBackground
      ? `relaunched ${Math.round((sinceBackground ?? 0) / 1000)}s after going to background`
      : `previous session ended while ${prev.appState}, never went to background`,
    screen: prev.screen,
    extra: {
      ended_state: prev.appState,
      since_background_ms: sinceBackground,
      since_last_save_ms: now - prev.savedAt,
      session_ms: prev.savedAt - prev.launchAt,
      touches_since_nav: prev.touchesSinceNav,
      since_last_touch_ms: prev.lastTouchAt == null ? null : prev.savedAt - prev.lastTouchAt,
      open_modals: prev.openModals,
      // Seconds before the last saved crumb, not before this report.
      trail,
    },
  };
}

export function configureFreezeLog(d: FreezeLogDeps): void {
  deps = d;
}

/**
 * Call once per JS start. Reports how the previous session ended (if it looks
 * like a forced restart), starts this session's record and the stall watchdog.
 */
export async function beginFreezeLog(initialState: AppStateName): Promise<void> {
  if (!deps) return;
  const d = deps;
  let prev: SessionRecord | null = null;
  try {
    const raw = await d.storage.getItem(SESSION_KEY);
    prev = raw ? (JSON.parse(raw) as SessionRecord) : null;
  } catch {
    prev = null;
  }
  const now = d.now();
  // Keep anything that happened before the stored record was read.
  const early = session?.trail ?? [];
  session = {
    launchAt: now,
    savedAt: now,
    appState: initialState,
    backgroundAt: initialState === 'background' ? now : null,
    screen: session?.screen ?? null,
    lastTouchAt: session?.lastTouchAt ?? null,
    touchesSinceNav: session?.touchesSinceNav ?? 0,
    openModals: session?.openModals ?? [],
    trail: [{ t: now, k: 'launch' as CrumbKind, d: initialState }, ...early].slice(-MAX_TRAIL),
  };
  safe(() => {
    const r = restartFrom(prev, now);
    if (r) d.report('restart', r.message, r.extra, r.screen);
  });
  save(true);
  lastTick = now;
  d.setInterval(tick, TICK_MS);
}

function ensureSession(): SessionRecord | null {
  if (!deps) return null;
  if (!session) {
    // An event before beginFreezeLog's storage read finished.
    const now = deps.now();
    session = {
      launchAt: now,
      savedAt: now,
      appState: 'active',
      backgroundAt: null,
      screen: null,
      lastTouchAt: null,
      touchesSinceNav: 0,
      openModals: [],
      trail: [],
    };
  }
  return session;
}

/** The watchdog. A long gap between ticks, active on both ends, is a stall. */
export function tick(): void {
  safe(() => {
    if (!deps || !session) return;
    const now = deps.now();
    const gap = now - lastTick;
    const state = session.appState;
    if (gap >= STALL_MS && state === 'active') {
      crumb('stall', `${gap}ms`);
      if (stallReports < MAX_STALL_REPORTS) {
        stallReports += 1;
        deps.report(
          'js_stall',
          `JS thread stopped for ${gap}ms while on screen`,
          { stall_ms: gap, ...(sessionSummary() ?? {}), trail: trailForReport() },
        );
      }
    }
    lastTick = now;
    if (state === 'active') save();
  });
}

export function noteScreen(name: string | null | undefined): void {
  safe(() => {
    const s = ensureSession();
    if (!s || !name || name === s.screen) return;
    s.screen = name;
    s.touchesSinceNav = 0;
    crumb('screen', name);
    save();
  });
}

export function noteTouch(): void {
  safe(() => {
    const s = ensureSession();
    if (!s || !deps) return;
    s.lastTouchAt = deps.now();
    s.touchesSinceNav += 1;
    crumb('touch');
  });
}

export function noteAppState(state: AppStateName): void {
  safe(() => {
    const s = ensureSession();
    if (!s || !deps || state === s.appState) return;
    s.appState = state;
    s.backgroundAt = state === 'background' ? deps.now() : null;
    crumb('app_state', state);
    // Leaving the screen is the moment that matters: save now, not in 5s.
    save(true);
    if (state === 'active') {
      // Timers do not run in background, so the first tick back would see the
      // whole time away as a stall. Restart the watchdog's clock.
      lastTick = deps.now();
    }
  });
}

function watchModal(name: string, phase: 'present' | 'dismiss'): void {
  if (!deps) return;
  const d = deps;
  const key = `${name}:${phase}`;
  const prior = modalTimers.get(name);
  if (prior !== undefined) d.clearTimeout(prior);
  const handle = d.setTimeout(() => {
    safe(() => {
      modalTimers.delete(name);
      if (reportedModal.has(key)) return;
      reportedModal.add(key);
      d.report(
        'modal_stuck',
        phase === 'present'
          ? `pop-up "${name}" was opened but iOS never showed it`
          : `pop-up "${name}" was closed but iOS never confirmed it went away`,
        { modal: name, phase, waited_ms: MODAL_CONFIRM_MS, ...(sessionSummary() ?? {}), trail: trailForReport() },
      );
    });
  }, MODAL_CONFIRM_MS);
  modalTimers.set(name, handle);
}

function clearModalWatch(name: string): void {
  const prior = modalTimers.get(name);
  if (prior !== undefined && deps) deps.clearTimeout(prior);
  modalTimers.delete(name);
}

/**
 * A pop-up's `visible` changed (or it mounted visible). `confirmsDismiss` is
 * false where the platform has no dismiss callback (Android), so a close is
 * recorded but not watched.
 */
export function noteModalVisible(name: string, visible: boolean, confirmsDismiss: boolean): void {
  safe(() => {
    const s = ensureSession();
    if (!s) return;
    if (visible) {
      if (!s.openModals.includes(name)) s.openModals.push(name);
      crumb('modal_open', name);
      watchModal(name, 'present');
    } else {
      s.openModals = s.openModals.filter((m) => m !== name);
      crumb('modal_close', name);
      if (confirmsDismiss) watchModal(name, 'dismiss');
      else clearModalWatch(name);
    }
    save(true);
  });
}

export function noteModalShown(name: string): void {
  safe(() => {
    clearModalWatch(name);
    crumb('modal_shown', name);
  });
}

export function noteModalDismissed(name: string): void {
  safe(() => {
    clearModalWatch(name);
    crumb('modal_dismissed', name);
  });
}

/** Test hook: forget module state between scenarios. */
export function resetFreezeLogForTests(): void {
  deps = null;
  session = null;
  lastSave = 0;
  lastTick = 0;
  stallReports = 0;
  reportedModal.clear();
  modalTimers.clear();
}
