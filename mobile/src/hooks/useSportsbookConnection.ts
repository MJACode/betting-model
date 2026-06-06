import AsyncStorage from '@react-native-async-storage/async-storage';
import { useCallback, useEffect, useState } from 'react';

/**
 * Beta scaffold: tracks which sportsbooks the user has "connected".
 * No actual sync happens yet — flipping one on only records intent so the
 * Performance tab can show synced-mode UI. Bet history sync ships later.
 *
 * Multiple books can be connected at once (DraftKings + FanDuel + ...), since
 * real bettors spread action across books and we want per-book P&L once sync
 * lands.
 */
export type SportsbookProvider = 'draftkings' | 'fanduel';

export interface SportsbookConnection {
  provider: SportsbookProvider;
  connectedAt: string;
}

export interface ProviderMeta {
  id: SportsbookProvider;
  name: string;
  /** Two-letter badge text, e.g. "DK" / "FD". */
  abbrev: string;
  /** Logo tile background + foreground for brand-accurate badges. */
  logoBg: string;
  logoFg: string;
}

/** Order here is the order books render in the Connect screen. */
export const SPORTSBOOK_PROVIDERS: ProviderMeta[] = [
  { id: 'draftkings', name: 'DraftKings', abbrev: 'DK', logoBg: '#000000', logoFg: '#53D337' },
  { id: 'fanduel', name: 'FanDuel', abbrev: 'FD', logoBg: '#1493FF', logoFg: '#FFFFFF' },
];

export function providerMeta(id: SportsbookProvider): ProviderMeta {
  return SPORTSBOOK_PROVIDERS.find((p) => p.id === id) ?? SPORTSBOOK_PROVIDERS[0];
}

type ConnectionMap = Partial<Record<SportsbookProvider, SportsbookConnection>>;

const KEY = 'sportsbook.connections.v2';
const LEGACY_KEY = 'sportsbook.connection.v1';

const KNOWN: ReadonlySet<SportsbookProvider> = new Set(
  SPORTSBOOK_PROVIDERS.map((p) => p.id),
);

const listeners = new Set<(c: ConnectionMap) => void>();
let cached: ConnectionMap | undefined = undefined;

function sanitize(raw: unknown): ConnectionMap {
  const out: ConnectionMap = {};
  if (!raw || typeof raw !== 'object') return out;
  for (const [k, v] of Object.entries(raw as Record<string, unknown>)) {
    if (!KNOWN.has(k as SportsbookProvider)) continue;
    const conn = v as Partial<SportsbookConnection> | null;
    if (conn && conn.provider === k && typeof conn.connectedAt === 'string') {
      out[k as SportsbookProvider] = {
        provider: k as SportsbookProvider,
        connectedAt: conn.connectedAt,
      };
    }
  }
  return out;
}

async function load(): Promise<ConnectionMap> {
  if (cached !== undefined) return cached;
  try {
    const raw = await AsyncStorage.getItem(KEY);
    if (raw) {
      cached = sanitize(JSON.parse(raw));
      return cached;
    }
    // One-time migration from the single-connection v1 shape.
    const legacy = await AsyncStorage.getItem(LEGACY_KEY);
    if (legacy) {
      const old = JSON.parse(legacy) as Partial<SportsbookConnection> | null;
      if (old && old.provider && KNOWN.has(old.provider)) {
        cached = {
          [old.provider]: {
            provider: old.provider,
            connectedAt:
              typeof old.connectedAt === 'string'
                ? old.connectedAt
                : new Date().toISOString(),
          },
        };
        await AsyncStorage.setItem(KEY, JSON.stringify(cached));
      } else {
        cached = {};
      }
      await AsyncStorage.removeItem(LEGACY_KEY);
      return cached;
    }
    cached = {};
  } catch {
    cached = {};
  }
  return cached;
}

async function persist(next: ConnectionMap) {
  cached = next;
  if (Object.keys(next).length === 0) {
    await AsyncStorage.removeItem(KEY);
  } else {
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
  }
  listeners.forEach((fn) => fn(next));
}

function toList(map: ConnectionMap): SportsbookConnection[] {
  return Object.values(map)
    .filter((c): c is SportsbookConnection => c != null)
    .sort((a, b) => a.connectedAt.localeCompare(b.connectedAt));
}

export function useSportsbookConnection() {
  const [map, setMap] = useState<ConnectionMap>(cached ?? {});
  const [ready, setReady] = useState<boolean>(cached !== undefined);

  useEffect(() => {
    let mounted = true;
    load().then((c) => {
      if (!mounted) return;
      setMap(c);
      setReady(true);
    });
    const listener = (c: ConnectionMap) => setMap({ ...c });
    listeners.add(listener);
    return () => {
      mounted = false;
      listeners.delete(listener);
    };
  }, []);

  const connect = useCallback((provider: SportsbookProvider) => {
    const next: ConnectionMap = {
      ...(cached ?? {}),
      [provider]: { provider, connectedAt: new Date().toISOString() },
    };
    persist(next).catch((err) => console.warn('[sportsbook] connect failed', err));
  }, []);

  const disconnect = useCallback((provider: SportsbookProvider) => {
    const next: ConnectionMap = { ...(cached ?? {}) };
    delete next[provider];
    persist(next).catch((err) =>
      console.warn('[sportsbook] disconnect failed', err),
    );
  }, []);

  const isConnected = useCallback(
    (provider: SportsbookProvider) => map[provider] != null,
    [map],
  );

  const connections = toList(map);

  return {
    /** All connected books, oldest connection first. */
    connections,
    /** Raw provider → connection lookup. */
    connectionMap: map,
    /** True when at least one book is connected. */
    anyConnected: connections.length > 0,
    isConnected,
    ready,
    connect,
    disconnect,
  };
}
