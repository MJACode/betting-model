/**
 * Crash and error logging to Supabase (`app_errors`, written only through the
 * insert-only `log_app_error` RPC — data/migrations/add_app_errors.sql).
 *
 * WHY THIS EXISTS. On 2026-10-19 Matt reported the app crashing "every now and
 * then when I open it up for the first time", fine on the next open. The app
 * had no crash reporting and no error boundary, so nothing could say why. The
 * leading suspect is the launch-time OTA reload (src/lib/otaUpdate.ts), and
 * this module is built to confirm or rule that out.
 *
 * What it captures:
 *   - js_fatal / js_error  every uncaught JS error, via ErrorUtils
 *   - render               a screen that threw while rendering (ErrorBoundary)
 *   - early_exit           the PREVIOUS launch never reached RUNNING_AFTER_MS.
 *                          JS cannot see a native crash, but it can see that
 *                          the last launch died young. (Rows before
 *                          2026-10-19 may carry stage "ota_reload", from
 *                          when the app still reloaded itself.)
 *   - emergency_launch     expo-updates rolled back a bundle that crashed
 *
 * A report is written to AsyncStorage FIRST and sent second, so a fatal error
 * that kills the app before the network call returns is sent on the next
 * launch. Nothing here may throw: logging a crash must never cause one.
 *
 * Every dependency is injectable (`configureCrashLog`) so
 * scripts/verify_crash_log.ts drives the logic without a device.
 */

export type ReportKind =
  | 'js_fatal'
  | 'js_error'
  | 'render'
  | 'early_exit'
  | 'emergency_launch'
  // Freeze tracking (src/lib/freezeLog.ts, 2026-11-06).
  | 'restart'
  | 'js_stall'
  | 'modal_stuck';

/** Startup stages, in order. `running` = this launch survived its first 15s. */
export type LaunchStage = 'launching' | 'running';

export interface CrashReport {
  kind: ReportKind;
  occurredAt: string;
  message?: string | null;
  stack?: string | null;
  componentStack?: string | null;
  screen?: string | null;
  stage?: LaunchStage | null;
  extra?: Record<string, unknown> | null;
}

export interface LaunchMarker {
  stage: LaunchStage;
  /** ms epoch the stage was written. */
  at: number;
  updateId: string | null;
}

export interface CrashContext {
  appVersion: string | null;
  updateId: string | null;
  updateCreatedAt: string | null;
  platform: string | null;
  isEmergencyLaunch: boolean;
  emergencyLaunchReason: string | null;
}

export interface KeyValueStore {
  getItem(key: string): Promise<string | null>;
  setItem(key: string, value: string): Promise<void>;
}

/**
 * One entry of expo-updates' own log (`Updates.readLogEntriesAsync`). The
 * shape is expo-updates 29's `UpdatesLogEntry`; restated here so this module
 * keeps importing nothing.
 */
export interface UpdatesLogEntry {
  /** ms epoch the entry was written. */
  timestamp: number;
  message: string;
  code: string;
  level: string;
  updateId?: string | null;
  assetId?: string | null;
  stacktrace?: string[] | null;
}

export interface CrashLogDeps {
  storage: KeyValueStore;
  /**
   * expo-updates' log on the phone, newest window only. Optional: without it
   * no updates-log report is made. It is a file expo-updates writes natively,
   * so it survives a crash that happens before any JS runs (TestFlight
   * 2026-11-14: ErrorRecovery.crash() 0.24 s after launch, nothing in
   * app_errors).
   */
  updatesLog?: () => Promise<UpdatesLogEntry[]>;
  /** Send one report. Throws on failure, so the report stays queued. */
  send(report: CrashReport, deviceId: string, ctx: CrashContext): Promise<void>;
  deviceId(): Promise<string>;
  context(): CrashContext;
  now(): number;
}

export const QUEUE_KEY = 'crashlog.queue';
export const MARKER_KEY = 'crashlog.launch';
/** Keep at most this many unsent reports; the oldest go first. */
export const MAX_QUEUED = 20;
/** A launch that lives this long counts as started. */
export const RUNNING_AFTER_MS = 15_000;
/** How long a fatal error waits for its report before the app is let go. */
export const FATAL_FLUSH_MS = 1_500;
/** Newest updates-log timestamp already reported, so an entry is sent once. */
export const UPDATES_LOG_SEEN_KEY = 'crashlog.updates_log_seen';
/** How far back to read expo-updates' log. It prunes entries past a day. */
export const UPDATES_LOG_WINDOW_MS = 24 * 60 * 60 * 1000;
/** At most this many entries ride on one report, newest kept. */
export const UPDATES_LOG_MAX_ENTRIES = 15;
/** The native log read gets this long; past it the launch moves on without. */
export const UPDATES_LOG_READ_TIMEOUT_MS = 3_000;
const UPDATES_LOG_BAD_LEVELS = new Set(['error', 'fatal']);
/**
 * A report is made only when an entry says a LAUNCH failed. expo-updates also
 * logs at error level for every failed download (FileDownloader: code Unknown,
 * AssetsFailedToLoad), so an offline open would otherwise be a row. Those
 * entries still ride along as context when a launch failure is reported.
 * ErrorRecovery writes JSRuntimeError (the exception) and UpdateFailedToLoad
 * ("crashing") before it aborts.
 */
const UPDATES_LOG_LAUNCH_CODES = new Set(['UpdateFailedToLoad', 'JSRuntimeError', 'InitializationError']);

let deps: CrashLogDeps | null = null;
/**
 * What the app was doing just before a report (freezeLog's trail). Added to
 * every report's extra as `trail` and `session` unless the report brings its
 * own trail.
 */
let trailProvider: (() => { trail: unknown; session: unknown } | null) | null = null;
let currentScreen: string | null = null;
let currentStage: LaunchStage = 'launching';
let flushing: Promise<void> | null = null;
/**
 * Every read-modify-write of the queue runs on this chain. Two reports
 * enqueued together during launch (the previous launch's early_exit, and a
 * render or js_error on the first frame) otherwise both read the same list
 * and the later setItem drops the earlier report.
 */
let queueWrite: Promise<void> = Promise.resolve();

function withQueueWrite<T>(fn: () => Promise<T>): Promise<T> {
  const run = queueWrite.then(fn, fn);
  queueWrite = run.then(() => undefined, () => undefined);
  return run;
}

export function configureCrashLog(d: CrashLogDeps): void {
  deps = d;
}

export function setTrailProvider(fn: (() => { trail: unknown; session: unknown } | null) | null): void {
  trailProvider = fn;
}

function withTrail(extra: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  if (extra && 'trail' in extra) return extra;
  let t: { trail: unknown; session: unknown } | null = null;
  try {
    t = trailProvider ? trailProvider() : null;
  } catch {
    t = null;
  }
  if (!t || t.trail == null) return extra ?? null;
  return { ...(extra ?? {}), trail: t.trail, session: t.session };
}

/** Called on every navigation change so a report names the screen. */
export function setCrashScreen(name: string | null | undefined): void {
  currentScreen = name ?? null;
}

const clip = (s: unknown, n: number): string | null =>
  s == null ? null : String(s).slice(0, n);

function errorParts(error: unknown): { message: string | null; stack: string | null } {
  if (error instanceof Error) {
    return { message: clip(`${error.name}: ${error.message}`, 2000), stack: clip(error.stack, 8000) };
  }
  try {
    return { message: clip(typeof error === 'string' ? error : JSON.stringify(error), 2000), stack: null };
  } catch {
    return { message: 'unserialisable error', stack: null };
  }
}

async function readQueue(store: KeyValueStore): Promise<CrashReport[]> {
  try {
    const raw = await store.getItem(QUEUE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function enqueue(report: CrashReport): Promise<void> {
  return withQueueWrite(async () => {
    if (!deps) return;
    const queue = await readQueue(deps.storage);
    queue.push(report);
    await deps.storage.setItem(QUEUE_KEY, JSON.stringify(queue.slice(-MAX_QUEUED)));
  });
}

/**
 * Send everything queued, oldest first. Stops at the first failure and keeps
 * the rest (offline is the usual reason, and the next launch retries). One
 * flush at a time, so two triggers cannot send a report twice.
 */
export function flushCrashQueue(): Promise<void> {
  if (flushing) return flushing;
  flushing = (async () => {
    if (!deps) return;
    const d = deps;
    try {
      const queue = await readQueue(d.storage);
      if (queue.length === 0) return;
      const deviceId = await d.deviceId();
      const ctx = d.context();
      let sent = 0;
      for (const r of queue) {
        try {
          await d.send(r, deviceId, ctx);
          sent += 1;
        } catch {
          break;
        }
      }
      if (sent > 0) {
        // Re-read under the same lock as enqueue: a report may have been
        // queued while this flush was sending, and its write must not race
        // this one.
        await withQueueWrite(async () => {
          const now = await readQueue(d.storage);
          await d.storage.setItem(QUEUE_KEY, JSON.stringify(now.slice(sent)));
        });
      }
    } catch {
      // never throw from the logger
    }
  })().finally(() => {
    flushing = null;
  });
  return flushing;
}

/** Queue a report, then try to send it. Never rejects. */
export async function recordReport(report: Omit<CrashReport, 'occurredAt' | 'screen' | 'stage'> & {
  screen?: string | null;
  stage?: LaunchStage | null;
}): Promise<void> {
  if (!deps) return;
  try {
    await enqueue({
      ...report,
      extra: withTrail(report.extra),
      occurredAt: new Date(deps.now()).toISOString(),
      screen: report.screen === undefined ? currentScreen : report.screen,
      stage: report.stage === undefined ? currentStage : report.stage,
    });
  } catch {
    return;
  }
  await flushCrashQueue();
}

export function recordError(kind: 'js_fatal' | 'js_error' | 'render', error: unknown, componentStack?: string | null): Promise<void> {
  const { message, stack } = errorParts(error);
  return recordReport({ kind, message, stack, componentStack: clip(componentStack, 4000) });
}

async function writeMarker(stage: LaunchStage): Promise<void> {
  if (!deps) return;
  currentStage = stage;
  const marker: LaunchMarker = { stage, at: deps.now(), updateId: deps.context().updateId };
  try {
    await deps.storage.setItem(MARKER_KEY, JSON.stringify(marker));
  } catch {
    // ignore
  }
}

/**
 * What the previous launch's marker says about how it ended. Pure.
 *
 * A marker not at `running` means that launch never lived RUNNING_AFTER_MS:
 * a crash, or a user closing the app inside 15s. `gap_ms` (marker to next
 * launch) is carried so the two can be weighed.
 */
export function earlyExitFrom(prev: LaunchMarker | null, now: number, updateIdNow: string | null): CrashReport | null {
  if (!prev || prev.stage === 'running') return null;
  return {
    kind: 'early_exit',
    occurredAt: new Date(prev.at).toISOString(),
    stage: prev.stage,
    screen: null,
    message: `previous launch ended at stage "${prev.stage}" before ${RUNNING_AFTER_MS / 1000}s`,
    extra: {
      gap_ms: now - prev.at,
      prev_update_id: prev.updateId,
      update_id_now: updateIdNow,
      bundle_changed: prev.updateId !== updateIdNow,
    },
  };
}

/**
 * The updates-log entries worth reporting: level error or fatal, newer than
 * `seenThrough`, oldest first, capped to the newest UPDATES_LOG_MAX_ENTRIES.
 * Pure.
 */
export function newUpdatesLogErrors(entries: UpdatesLogEntry[], seenThrough: number): UpdatesLogEntry[] {
  const bad = entries
    .filter((e) => e && typeof e.timestamp === 'number' && e.timestamp > seenThrough
      && UPDATES_LOG_BAD_LEVELS.has(String(e.level).toLowerCase()))
    .sort((a, b) => a.timestamp - b.timestamp);
  return bad.slice(-UPDATES_LOG_MAX_ENTRIES);
}

function summariseEntry(e: UpdatesLogEntry): Record<string, unknown> {
  return {
    at: new Date(e.timestamp).toISOString(),
    level: e.level,
    code: e.code,
    message: clip(e.message, 1000),
    update_id: e.updateId ?? null,
    asset_id: e.assetId ?? null,
    stacktrace: e.stacktrace ? clip(e.stacktrace.slice(0, 15).join('\n'), 1500) : null,
  };
}

/** Whether these entries include a failed launch, the only thing reported. */
export function hasLaunchFailure(entries: UpdatesLogEntry[]): boolean {
  return entries.some((e) => String(e.level).toLowerCase() === 'fatal'
    || UPDATES_LOG_LAUNCH_CODES.has(String(e.code)));
}

function withTimeout<T>(p: Promise<T>, ms: number, fallback: T): Promise<T> {
  return new Promise<T>((resolve) => {
    const t = setTimeout(() => resolve(fallback), ms);
    p.then((v) => { clearTimeout(t); resolve(v); }, () => { clearTimeout(t); resolve(fallback); });
  });
}

/**
 * Read expo-updates' own log: the error and fatal entries not yet reported,
 * when they include a failed launch. Does NOT mark them seen; the caller does
 * that once the report is queued, so a failed enqueue resends rather than
 * drops. The read is bounded by UPDATES_LOG_READ_TIMEOUT_MS. Never throws.
 */
async function updatesLogReport(d: CrashLogDeps): Promise<{
  entries: Record<string, unknown>[];
  /** Newest entry read: what gets marked seen. */
  newest: UpdatesLogEntry;
  /** Newest launch-failure entry: what the row is named and dated by. */
  headline: UpdatesLogEntry;
} | null> {
  if (!d.updatesLog) return null;
  try {
    let seen = 0;
    try {
      const raw = await d.storage.getItem(UPDATES_LOG_SEEN_KEY);
      seen = raw ? Number(raw) || 0 : 0;
    } catch {
      seen = 0;
    }
    const all = await withTimeout(d.updatesLog(), UPDATES_LOG_READ_TIMEOUT_MS, [] as UpdatesLogEntry[]);
    const bad = newUpdatesLogErrors(all, seen);
    if (bad.length === 0 || !hasLaunchFailure(bad)) return null;
    const headline = [...bad].reverse().find((e) => hasLaunchFailure([e]))!;
    return { entries: bad.map(summariseEntry), newest: bad[bad.length - 1], headline };
  } catch {
    return null;
  }
}

async function markUpdatesLogSeen(d: CrashLogDeps, newest: UpdatesLogEntry): Promise<void> {
  try {
    await d.storage.setItem(UPDATES_LOG_SEEN_KEY, String(newest.timestamp));
  } catch {
    // worst case the same entries are sent again next launch
  }
}

/**
 * Call once per JS start, as early as possible. Reads how the last launch
 * ended, records it, writes this launch's marker, and reports an expo-updates
 * rollback if there was one, then marks the launch `running` after 15s.
 */
export async function beginLaunch(): Promise<void> {
  if (!deps) return;
  const d = deps;
  let prev: LaunchMarker | null = null;
  try {
    const raw = await d.storage.getItem(MARKER_KEY);
    prev = raw ? (JSON.parse(raw) as LaunchMarker) : null;
  } catch {
    prev = null;
  }
  await writeMarker('launching');
  const ctx = d.context();
  const early = earlyExitFrom(prev, d.now(), ctx.updateId);
  if (early) {
    try {
      await enqueue(early);
    } catch {
      // ignore
    }
  }
  // Scheduled before the updates-log read, so a slow native read can never
  // leave this launch marked `launching` (a false early_exit next time).
  setTimeout(() => {
    void writeMarker('running');
  }, RUNNING_AFTER_MS);
  // Reported as `emergency_launch`, the expo-updates kind (no new server
  // kind: one the RPC refuses would stop the queue behind it). On an
  // emergency launch the entries ride on that row, so one event is one row.
  const log = await updatesLogReport(d);
  if (ctx.isEmergencyLaunch) {
    try {
      await enqueue({
        kind: 'emergency_launch',
        occurredAt: new Date(d.now()).toISOString(),
        stage: 'launching',
        screen: null,
        message: ctx.emergencyLaunchReason,
        extra: log ? { updates_log: log.entries } : null,
      });
      if (log) await markUpdatesLogSeen(d, log.newest);
    } catch {
      // ignore
    }
  } else if (log) {
    try {
      await enqueue({
        kind: 'emergency_launch',
        occurredAt: new Date(log.headline.timestamp).toISOString(),
        stage: 'launching',
        screen: null,
        message: clip(`${log.headline.code}: ${log.headline.message}`, 2000),
        extra: { source: 'updates_log', updates_log: log.entries },
      });
      await markUpdatesLogSeen(d, log.newest);
    } catch {
      // ignore
    }
  }
}

interface ErrorUtilsShape {
  getGlobalHandler(): (error: unknown, isFatal?: boolean) => void;
  setGlobalHandler(handler: (error: unknown, isFatal?: boolean) => void): void;
}

let installed = false;

/**
 * Wrap React Native's global error handler. The previous handler still runs
 * (it is what shows the red box in development and closes the app on a fatal
 * error in release), but a fatal error first gets up to FATAL_FLUSH_MS to
 * store and send its report.
 */
export function installGlobalErrorHandler(errorUtils?: ErrorUtilsShape | null): void {
  const eu = errorUtils ?? (globalThis as { ErrorUtils?: ErrorUtilsShape }).ErrorUtils;
  if (installed || !eu) return;
  installed = true;
  const previous = eu.getGlobalHandler();
  let handling = false;
  eu.setGlobalHandler((error, isFatal) => {
    if (handling) {
      previous(error, isFatal);
      return;
    }
    handling = true;
    let report: Promise<void>;
    try {
      report = recordError(isFatal ? 'js_fatal' : 'js_error', error).catch(() => undefined);
    } catch {
      report = Promise.resolve();
    }
    if (!isFatal) {
      handling = false;
      previous(error, isFatal);
      return;
    }
    const timeout = new Promise<void>((resolve) => setTimeout(resolve, FATAL_FLUSH_MS));
    void Promise.race([report, timeout]).finally(() => {
      handling = false;
      previous(error, isFatal);
    });
  });
}

/** Test hook: forget module state between scenarios. */
export function resetCrashLogForTests(): void {
  deps = null;
  trailProvider = null;
  currentScreen = null;
  currentStage = 'launching';
  flushing = null;
  installed = false;
  queueWrite = Promise.resolve();
}
