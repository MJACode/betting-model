import type React from 'react';
import * as Sentry from '@sentry/react-native';
import * as Updates from 'expo-updates';

import { getDeviceId } from '@/hooks/useDeviceId';

/**
 * Sentry (2026-11-06, Matt: "Can we add Sentry tracking in the app … Yes
 * continue with all"). It sees what app_errors cannot: native crashes, and
 * iOS app hangs, where the main thread stops and the screen freezes while the
 * JS thread may be fine (src/lib/freezeLog.ts watches only JS).
 *
 * app_errors stays the system of record. Every Sentry event is copied into
 * Supabase `sentry_events` by the worker (data/ingestors/sentry_events.py), so
 * Sentry is a second copy, never the only one (CLAUDE.md §1b).
 *
 * Privacy: no PII (no email, no IP), no screenshots, no view hierarchy,
 * session replay OFF (Matt: off at first). Events carry the anonymous
 * device id, the same one app_errors carries, so the two join.
 *
 * SENTRY_DSN is public by design (it can only send events), so it lives in
 * source. Empty = Sentry is not started and nothing is sent.
 */
export const SENTRY_DSN = '';

let started = false;

export function startSentry(): void {
  if (started || !SENTRY_DSN) return;
  started = true;
  let channel: string | null = null;
  try {
    channel = Updates.channel ?? null;
  } catch {
    channel = null;
  }
  Sentry.init({
    dsn: SENTRY_DSN,
    environment: channel ?? (__DEV__ ? 'development' : 'production'),
    enabled: !__DEV__,
    sendDefaultPii: false,
    enableNativeCrashHandling: true,
    enableAppHangTracking: true,
    appHangTimeoutInterval: 2,
    attachScreenshot: false,
    attachViewHierarchy: false,
    // A fatal JS error waits on this flush before the app closes, after the
    // crash log's own 1.5 s (crashLog.ts). The native layer has already
    // written the event to disk, so a long wait buys little (UX review).
    shutdownTimeout: 1000,
    // Tracing and session replay are OFF by leaving tracesSampleRate and the
    // replay rates UNSET. A 0 turns them on at a 0% sample: in 7.2.0 any
    // number installs the replay and tracing integrations
    // (integrations/default.js, typeof === 'number').
  });
  try {
    const updateId = Updates.updateId ?? null;
    if (updateId) Sentry.setTag('update_id', updateId);
  } catch {
    // expo-updates throws in some dev contexts
  }
  void getDeviceId()
    .then((id) => Sentry.setTag('device_id', id))
    .catch(() => undefined);
}

/** Called on every navigation change so an event names the screen. */
export function setSentryScreen(name: string | null | undefined): void {
  if (!started || !name) return;
  try {
    Sentry.setTag('screen', name);
    Sentry.addBreadcrumb({ category: 'navigation', message: name, level: 'info' });
  } catch {
    // never throw from the logger
  }
}

/** Wraps the root component: Sentry's touch breadcrumbs and error capture. */
export const wrapWithSentry = <P extends Record<string, unknown>>(
  component: React.ComponentType<P>,
): React.ComponentType<P> => (SENTRY_DSN ? Sentry.wrap(component) : component);
