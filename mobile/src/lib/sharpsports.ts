import * as WebBrowser from 'expo-web-browser';
import { supabase } from './supabase';

/**
 * SharpSports client (mobile side).
 *
 * Account linking and bet-history sync run through our `sharpsports` Edge
 * Function, which holds the SharpSports private key. The app only ever sends
 * its device `internalId` and opens the hosted Booklink URL — it never handles
 * the user's sportsbook password or the private API key.
 *
 * Flow:
 *   1. startSportsbookLink(deviceId) → Edge `context` → open Booklink webview.
 *   2. user logs into their sportsbook inside SharpSports' hosted UI.
 *   3. fetchSportsbookSync(deviceId, true) → Edge `bets` (refresh) → linked
 *      accounts + synced bets + P&L summary.
 */

export interface LinkedAccount {
  bettor_account_id: string;
  book: string | null;
  book_abbr: string | null;
  book_region: string | null;
  status: string | null; // 'verified' | 'unverified'
  linked_at: string | null;
}

export interface SyncedBet {
  bet_id: string;
  book: string | null;
  type: string | null; // 'single' | 'parlay'
  status: string | null;
  placed_at: string | null;
  settled_at: string | null;
  odds_american: number | null;
  stake: number | null;
  payout: number | null;
  profit: number | null;
  settled: boolean | null;
}

export interface SyncSummary {
  total_bets: number;
  settled_bets: number;
  open_bets: number;
  net_profit: number;
  win_rate: number | null;
}

export interface SyncResponse {
  accounts: LinkedAccount[];
  bets: SyncedBet[];
  summary: SyncSummary;
}

/**
 * Open the SharpSports Booklink flow so the user can link a sportsbook account.
 * Resolves once the in-app browser is dismissed (the caller should then sync).
 */
export async function startSportsbookLink(internalId: string): Promise<void> {
  const { data, error } = await supabase.functions.invoke('sharpsports', {
    body: { action: 'context', internalId },
  });
  if (error) throw error;
  const url = (data as { url?: string } | null)?.url;
  if (!url) throw new Error('Could not start the sportsbook link flow.');
  await WebBrowser.openBrowserAsync(url);
}

/** Read this device's linked accounts + synced bets (optionally pulling fresh first). */
export async function fetchSportsbookSync(
  internalId: string,
  refresh = false,
): Promise<SyncResponse> {
  const { data, error } = await supabase.functions.invoke('sharpsports', {
    body: { action: 'bets', internalId, refresh },
  });
  if (error) throw error;
  const r = (data ?? {}) as Partial<SyncResponse>;
  return {
    accounts: r.accounts ?? [],
    bets: r.bets ?? [],
    summary:
      r.summary ?? {
        total_bets: 0,
        settled_bets: 0,
        open_bets: 0,
        net_profit: 0,
        win_rate: null,
      },
  };
}
