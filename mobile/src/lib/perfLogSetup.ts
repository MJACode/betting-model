import { AppState, Platform } from 'react-native';
import * as Updates from 'expo-updates';

import { getDeviceId } from '@/hooks/useDeviceId';
import { configurePerfLog, flushPerfLog, resetPerfBackoff, type TimingRow } from '@/lib/perfLog';
import { APP_VERSION } from '@/lib/socialLinks';
import { supabase } from '@/lib/supabase';

/**
 * Wires src/lib/perfLog.ts to the real app: the log_app_timings RPC for
 * delivery, a timer and the move to background for when to send. Called once
 * at module scope in App.tsx, right after crash logging.
 */

/** Send buffered timings this often while the app is open. After a failed
 *  send, perfLog skips these ticks for 1, 2, 4 ... 15 minutes. */
const FLUSH_EVERY_MS = 60_000;

function updateId(): string | null {
  try {
    return Updates.updateId ?? null;
  } catch {
    return null;
  }
}

let started = false;

export function startPerfLogging(): void {
  if (started) return;
  started = true;
  configurePerfLog({
    now: () => Date.now(),
    async send(rows: TimingRow[]) {
      const deviceId = await getDeviceId();
      const { error } = await supabase.rpc('log_app_timings', {
        p_device_id: deviceId,
        p_app_version: APP_VERSION ?? null,
        p_update_id: updateId(),
        p_platform: `${Platform.OS} ${String(Platform.Version)}`,
        p_rows: rows.map((r) => ({
          kind: r.kind,
          name: r.name,
          ms: r.ms,
          status: r.status,
          screen: r.screen,
          request_count: r.requestCount,
          since_launch_ms: r.sinceLaunchMs,
          occurred_at: r.occurredAt,
        })),
      });
      if (error) throw error;
    },
  });
  setInterval(() => {
    void flushPerfLog();
  }, FLUSH_EVERY_MS);
  AppState.addEventListener('change', (state) => {
    if (state === 'background') void flushPerfLog();
    // A failed send backs off (perfLog); coming back is a fresh chance.
    if (state === 'active') resetPerfBackoff();
  });
}
