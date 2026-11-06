import AsyncStorage from '@react-native-async-storage/async-storage';
import { AppState } from 'react-native';

import { recordReport, setTrailProvider } from '@/lib/crashLog';
import {
  beginFreezeLog,
  configureFreezeLog,
  noteAppState,
  sessionSummary,
  trailForReport,
  type AppStateName,
} from '@/lib/freezeLog';

/**
 * Wires src/lib/freezeLog.ts to the real app: AsyncStorage for the session
 * record, AppState for foreground/background, and the crash log for delivery
 * (so freeze reports share its queue, retry and app_errors table). Called once
 * at module scope in App.tsx, right after startCrashLogging().
 */

let started = false;

export function startFreezeLogging(): void {
  if (started) return;
  started = true;
  configureFreezeLog({
    storage: AsyncStorage,
    now: () => Date.now(),
    report(kind, message, extra, screen) {
      void recordReport(
        screen === undefined ? { kind, message, extra } : { kind, message, extra, screen },
      );
    },
    setTimeout: (fn, ms) => setTimeout(fn, ms),
    clearTimeout: (h) => clearTimeout(h as ReturnType<typeof setTimeout>),
    setInterval: (fn, ms) => setInterval(fn, ms),
  });
  setTrailProvider(() => {
    const trail = trailForReport();
    return trail ? { trail, session: sessionSummary() } : null;
  });
  void beginFreezeLog((AppState.currentState ?? 'unknown') as AppStateName);
  AppState.addEventListener('change', (state) => noteAppState(state as AppStateName));
}
