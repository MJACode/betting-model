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

export type ReportKind = 'js_fatal' | 'js_error' | 'render' | 'early_exit' | 'emergency_launch';

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

export interface CrashLogDeps {
  storage: KeyValueStore;
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

let deps: CrashLogDeps | null = null;
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
  if (ctx.isEmergencyLaunch) {
    try {
      await enqueue({
        kind: 'emergency_launch',
        occurredAt: new Date(d.now()).toISOString(),
        stage: 'launching',
        screen: null,
        message: ctx.emergencyLaunchReason,
      });
    } catch {
      // ignore
    }
  }
  setTimeout(() => {
    void writeMarker('running');
  }, RUNNING_AFTER_MS);
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
  currentScreen = null;
  currentStage = 'launching';
  flushing = null;
  installed = false;
  queueWrite = Promise.resolve();
}
