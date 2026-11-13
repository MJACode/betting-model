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

/** The ids this module mints. A file that holds anything else is ignored. */
const ID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

let cached: string | null = null;

type DeviceIdFile = {
  exists: boolean;
  textSync: () => string;
  create: () => void;
  // SDK 54: write() is synchronous (it returns void). There is no writeSync.
  write: (contents: string) => void;
};

/**
 * A copy of the id that can be read synchronously. AsyncStorage cannot, and
 * Sentry.init has to know the id before the first event (lib/sentry.ts).
 * The file is written only after AsyncStorage has the same id. A missing
 * native module leaves the async path in place.
 */
function deviceIdFile(): DeviceIdFile | null {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const fs = require('expo-file-system') as {
      File: new (dir: object, name: string) => DeviceIdFile;
      Paths: { document: object };
    };
    return new fs.File(fs.Paths.document, KEY);
  } catch {
    return null;
  }
}

function readMirroredDeviceId(): string | null {
  try {
    const file = deviceIdFile();
    if (!file || !file.exists) return null;
    const text = file.textSync().trim();
    return ID_RE.test(text) ? text : null;
  } catch {
    return null;
  }
}

function writeMirroredDeviceId(id: string): void {
  try {
    const file = deviceIdFile();
    if (!file) return;
    if (!file.exists) file.create();
    file.write(id);
  } catch {
    // AsyncStorage still has the id. The next launch reads it the slow way.
  }
}

/** The id if this process, or a previous one, already knows it. Null on the first read of a fresh install. */
export function peekDeviceId(): string | null {
  if (cached) return cached;
  const fromDisk = readMirroredDeviceId();
  if (fromDisk) cached = fromDisk;
  return cached;
}

/** RFC-4122-ish v4 UUID without a native crypto dependency. */
function uuidv4(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export async function getDeviceId(): Promise<string> {
  const known = peekDeviceId();
  if (known) return known;
  try {
    const existing = await AsyncStorage.getItem(KEY);
    if (existing) {
      cached = existing;
      writeMirroredDeviceId(existing);
      return existing;
    }
    const id = uuidv4();
    await AsyncStorage.setItem(KEY, id);
    cached = id;
    writeMirroredDeviceId(id);
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
