import { useCallback, useEffect, useState } from 'react';
import { useDeviceId } from './useDeviceId';
import {
  fetchSportsbookSync,
  startSportsbookLink,
  type SyncResponse,
} from '@/lib/sharpsports';

const EMPTY: SyncResponse = {
  accounts: [],
  bets: [],
  summary: { total_bets: 0, settled_bets: 0, open_bets: 0, net_profit: 0, win_rate: null },
};

/**
 * Real sportsbook link + bet-sync state for this device, sourced from the
 * SharpSports Edge Function. `link()` opens the Booklink flow; `refresh(true)`
 * pulls fresh bet history from SharpSports before reading.
 */
export function useSportsbookSync() {
  const { deviceId, ready: deviceReady } = useDeviceId();
  const [data, setData] = useState<SyncResponse>(EMPTY);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(
    async (pull = false): Promise<SyncResponse | null> => {
      if (!deviceId) return null;
      setLoading(true);
      setError(null);
      try {
        const next = await fetchSportsbookSync(deviceId, pull);
        setData(next);
        return next;
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : String(e));
        return null;
      } finally {
        setLoading(false);
      }
    },
    [deviceId],
  );

  useEffect(() => {
    if (deviceReady && deviceId) void refresh(false);
  }, [deviceReady, deviceId, refresh]);

  // Opens the hosted Booklink flow, then pulls fresh data once it closes.
  // Returns the post-link sync so the caller can confirm which books linked.
  const link = useCallback(async (): Promise<SyncResponse | null> => {
    if (!deviceId) throw new Error('Device not ready');
    await startSportsbookLink(deviceId);
    return refresh(true);
  }, [deviceId, refresh]);

  const verifiedAccounts = data.accounts.filter((a) => (a.status ?? '') !== 'unverified');
  const needsReconnect = data.accounts.some((a) => a.status === 'unverified');

  return {
    deviceId,
    accounts: data.accounts,
    verifiedAccounts,
    needsReconnect,
    bets: data.bets,
    summary: data.summary,
    linked: data.accounts.length > 0,
    loading,
    error,
    refresh,
    link,
  };
}
