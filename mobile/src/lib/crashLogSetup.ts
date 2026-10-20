import AsyncStorage from '@react-native-async-storage/async-storage';
import { Platform } from 'react-native';
import * as Updates from 'expo-updates';

import { getDeviceId } from '@/hooks/useDeviceId';
import {
  beginLaunch,
  configureCrashLog,
  flushCrashQueue,
  installGlobalErrorHandler,
  type CrashContext,
} from '@/lib/crashLog';
import { APP_VERSION } from '@/lib/socialLinks';
import { supabase } from '@/lib/supabase';

/**
 * Wires src/lib/crashLog.ts to the real app: AsyncStorage for the queue and
 * launch marker, the log_app_error RPC for delivery, expo-updates for which
 * bundle is running. Called once at module scope in App.tsx, before any
 * screen mounts.
 */

function context(): CrashContext {
  let updateId: string | null = null;
  let updateCreatedAt: string | null = null;
  let isEmergencyLaunch = false;
  let emergencyLaunchReason: string | null = null;
  try {
    updateId = Updates.updateId ?? null;
    updateCreatedAt = Updates.createdAt ? Updates.createdAt.toISOString() : null;
    isEmergencyLaunch = Boolean(Updates.isEmergencyLaunch);
    emergencyLaunchReason = Updates.emergencyLaunchReason ?? null;
  } catch {
    // expo-updates throws in some dev contexts; the built-in bundle reads as null.
  }
  return {
    appVersion: APP_VERSION ?? null,
    updateId,
    updateCreatedAt,
    platform: `${Platform.OS} ${String(Platform.Version)}`,
    isEmergencyLaunch,
    emergencyLaunchReason,
  };
}

/** Wait this long after launch before sending queued reports, so the send does
 *  not compete with the first screen's own reads. */
const FIRST_FLUSH_DELAY_MS = 5_000;

let started = false;

export function startCrashLogging(): void {
  if (started) return;
  started = true;
  configureCrashLog({
    storage: AsyncStorage,
    deviceId: getDeviceId,
    context,
    now: () => Date.now(),
    async send(report, deviceId, ctx) {
      const { error } = await supabase.rpc('log_app_error', {
        p_device_id: deviceId,
        p_kind: report.kind,
        p_message: report.message ?? null,
        p_stack: report.stack ?? null,
        p_component_stack: report.componentStack ?? null,
        p_screen: report.screen ?? null,
        p_stage: report.stage ?? null,
        p_app_version: ctx.appVersion,
        p_update_id: ctx.updateId,
        p_update_created_at: ctx.updateCreatedAt,
        p_platform: ctx.platform,
        p_occurred_at: report.occurredAt,
        p_extra: report.extra ?? null,
      });
      if (error) throw error;
    },
  });
  installGlobalErrorHandler();
  void beginLaunch().then(() => {
    setTimeout(() => {
      void flushCrashQueue();
    }, FIRST_FLUSH_DELAY_MS);
  });
}
