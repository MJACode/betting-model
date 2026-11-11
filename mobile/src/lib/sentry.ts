import type React from 'react';
import * as Sentry from '@sentry/react-native';
import * as Updates from 'expo-updates';

import appConfig from '../../app.json';

import { getDeviceId, peekDeviceId } from '@/hooks/useDeviceId';
import { scopeTags } from '@/lib/sentryScope';
import { scrubBreadcrumb, scrubSentryEvent } from '@/lib/sentryScrub';

// Same value as socialLinks.APP_VERSION. Read here so starting Sentry does not
// pull the share-message helpers in.
const APP_VERSION = appConfig.expo.version;

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
 * source. This is the signal-base / signal-base-mobile client key. Empty
 * still means Sentry is not started and nothing is sent.
 */
export const SENTRY_DSN =
  'https://f8fbe2f714eba74c4159b93cf987a942@o4512386387017728.ingest.us.sentry.io/4512386389311488';

let started = false;
let starting: Promise<void> | null = null;
// True when this call already inited, or skipped init, before returning.
// App.tsx uses it to start the other loggers in the same turn.
let readyNow = false;

/**
 * device_id is read before init and put on initialScope. A tag set in a
 * promise after init misses a crash in that gap, and that tag is how a
 * Sentry row joins app_errors. When the id is already on disk the read is
 * synchronous (useDeviceId.peekDeviceId). The first launch of a build waits
 * for AsyncStorage, then inits.
 *
 * release here is a TAG, the app version. The SDK's own release string is
 * left unset so it stays the native one (bundle id, version, build) that the
 * dSYM from the TestFlight build was uploaded under.
 */
export function startSentry(): Promise<void> {
  if (started || !SENTRY_DSN) {
    readyNow = true;
    return Promise.resolve();
  }
  if (starting) return starting;
  const known = peekDeviceId();
  if (known) {
    initSentry(known);
    readyNow = true;
    return Promise.resolve();
  }
  starting = getDeviceId()
    .then((id) => {
      initSentry(id);
    })
    .catch(() => {
      initSentry(null);
    });
  return starting;
}

/** Init already happened in this turn (or there is nothing to start). */
export function sentryReadyNow(): boolean {
  return readyNow;
}

function initSentry(deviceId: string | null): void {
  if (started || !SENTRY_DSN) return;
  started = true;
  let channel: string | null = null;
  let updateId: string | null = null;
  try {
    channel = Updates.channel ?? null;
    updateId = Updates.updateId ?? null;
  } catch {
    channel = null;
    updateId = null;
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
    beforeSend: scrubSentryEvent,
    beforeBreadcrumb: scrubBreadcrumb,
    initialScope: {
      tags: scopeTags({ deviceId, release: APP_VERSION, updateId }),
    },
  });
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
