import { useEffect } from 'react';
import { Platform } from 'react-native';
import * as Notifications from 'expo-notifications';
import { supabase } from '@/lib/supabase';
import { getDeviceId } from '@/hooks/useDeviceId';
import { usePushOptIn } from '@/hooks/usePushOptIn';

/** Registers for push + upserts the Expo token when the user has opted in.
 *  All native calls are guarded so a binary without the module just no-ops. */
export function usePushNotifications(): void {
  const { enabled } = usePushOptIn();
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    (async () => {
      try {
        const perm = await Notifications.requestPermissionsAsync();
        if (perm.status !== 'granted') return;
        const projectId = '0e16eb4b-190b-4356-be61-5b7a6b1da5ee';
        const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
        if (cancelled || !token) return;
        const deviceId = await getDeviceId();
        await supabase
          .from('device_push_tokens')
          .upsert(
            { token, device_id: deviceId, platform: Platform.OS, enabled: true,
              last_seen: new Date().toISOString() },
            { onConflict: 'token' },
          );
      } catch (err) {
        // No native module (pre-rebuild) or permission denied — silently skip.
        console.warn('[push] registration skipped', err);
      }
    })();
    return () => { cancelled = true; };
  }, [enabled]);
}
