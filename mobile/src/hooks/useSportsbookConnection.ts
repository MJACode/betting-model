import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Beta scaffold: tracks whether the user has "connected" their sportsbook.
 * No actual sync happens yet — flipping this on only records intent so the
 * Performance tab can show synced-mode UI. Bet history sync ships later.
 */
export type SportsbookProvider = 'draftkings';

export interface SportsbookConnection {
  provider: SportsbookProvider;
  connectedAt: string;
}

const KEY = 'sportsbook.connection.v1';

const listeners = new Set<(c: SportsbookConnection | null) => void>();
let cached: SportsbookConnection | null | undefined = undefined;

async function load(): Promise<SportsbookConnection | null> {
  if (cached !== undefined) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (!raw) {
      cached = null;
    } else {
      const parsed = JSON.parse(raw) as SportsbookConnection;
      cached = parsed && parsed.provider ? parsed : null;
    }
  } catch {
    cached = null;
  }
  return cached;
}

async function save(next: SportsbookConnection | null) {
  cached = next;
  if (next == null) {
    await AsyncStorage.removeItem(KEY);
  } else {
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
  }
  listeners.forEach((fn) => fn(next));
}

export function useSportsbookConnection() {
  const [connection, setConnection] = useState<SportsbookConnection | null>(
    cached ?? null,
  );
  const [ready, setReady] = useState<boolean>(cached !== undefined);

  useEffect(() => {
    let mounted = true;
    load().then((c) => {
      if (!mounted) return;
      setConnection(c);
      setReady(true);
    });
    const listener = (c: SportsbookConnection | null) => setConnection(c);
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const connect = useCallback((provider: SportsbookProvider) => {
    const next: SportsbookConnection = {
      provider,
      connectedAt: new Date().toISOString(),
    };
    save(next).catch((err) => console.warn('[sportsbook] connect failed', err));
  }, []);

  const disconnect = useCallback(() => {
    save(null).catch((err) => console.warn('[sportsbook] disconnect failed', err));
  }, []);

  return {
    connection,
    connected: connection != null,
    ready,
    connect,
    disconnect,
  };
}
