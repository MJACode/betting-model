import AsyncStorage from '@react-native-async-storage/async-storage';
import { useEffect, useState } from 'react';

/**
 * Stable, device-scoped identifier.
 *
 * The app has no user accounts (anon Supabase client), so we mint one UUID per
 * install and persist it. It's used as the SharpSports `internalId` that maps a
 * SharpSports bettor back to this device, and as the key our Edge Functions
 * scope linked-account + synced-bet reads/writes by.
 *
 * Not a secret in the cryptographic sense, but unguessable — which is what
 * gates one device's bet history from another's (those tables have no anon
 * read policy; reads go through the sharpsports Edge Function by internalId).
 */
const KEY = 'device.id';

let cached: string | null = null;

/** RFC-4122-ish v4 UUID without a native crypto dependency. */
function uuidv4(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function getDeviceId(): Promise<string> {
  if (cached) return cached;
  try {
    const existing = await AsyncStorage.getItem(KEY);
    if (existing) {
      cached = existing;
      return existing;
    }
    const id = uuidv4();
    await AsyncStorage.setItem(KEY, id);
    cached = id;
    return id;
  } catch {
    // Fall back to an in-memory id for this session if storage is unavailable.
    cached = cached ?? uuidv4();
    return cached;
  }
}

export function useDeviceId() {
  const [deviceId, setDeviceId] = useState<string | null>(cached);

  useEffect(() => {
    let mounted = true;
    getDeviceId().then((id) => {
      if (mounted) setDeviceId(id);
    });
    return () => {
      mounted = false;
    };
  }, []);

  return { deviceId, ready: deviceId != null };
}
