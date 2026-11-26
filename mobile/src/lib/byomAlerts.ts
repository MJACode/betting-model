/**
 * Open bets and alerts on the member's own models (Matt, 2026-11-25).
 *
 * A bet here is the first DraftKings line and price in the 7 days before
 * kickoff that fit the model's rules (Matt, 2026-11-26: game week only), on
 * a game that has not been graded yet: the same lock the model's
 * record uses. The worker stores it once (byom_alerts) and never changes
 * it when the line moves. These are not picks: they are never in the
 * Record tab, Discord or the published record.
 *
 * The RPCs are in data/migrations/byom_alerts_2026_11_25.sql, which is
 * applied by hand. Until it is, every read here returns `unavailable` and
 * the screens show nothing extra.
 *
 * The label is the stored `byom_leg_label`, shown word for word, never a
 * line rebuilt here (CLAUDE.md §00).
 */

import { parseOpenBet, isMissingFunction, type ByomOpenBet, type ByomOpenBetsResult } from './byomAlertRows';
import { supabase } from './supabase';

export { isMissingFunction, matchupLabel, movedLine, parseOpenBet } from './byomAlertRows';
export type { ByomOpenBet, ByomOpenBetsResult } from './byomAlertRows';

export async function fetchByomOpenBets(): Promise<ByomOpenBetsResult> {
  const { data, error } = await supabase.rpc('byom_my_open_bets');
  if (error) {
    if (isMissingFunction(error)) return { status: 'unavailable' };
    throw error;
  }
  const rows = Array.isArray(data) ? data : [];
  const bets: ByomOpenBet[] = [];
  for (const row of rows) {
    const bet = parseOpenBet(row);
    if (bet) bets.push(bet);
  }
  return { status: 'ok', bets };
}

/** model_id -> alerts on. Null when the migration is not applied. */
export async function fetchByomAlertSettings(): Promise<Map<string, boolean> | null> {
  const { data, error } = await supabase.rpc('byom_alert_settings');
  if (error) {
    if (isMissingFunction(error)) return null;
    throw error;
  }
  const out = new Map<string, boolean>();
  for (const row of Array.isArray(data) ? data : []) {
    const r = row as Record<string, unknown>;
    const id = typeof r.model_id === 'string' && r.model_id !== '' ? r.model_id : null;
    if (id) out.set(id, r.alerts_enabled !== false);
  }
  return out;
}

export async function setByomAlerts(modelId: string, enabled: boolean): Promise<boolean> {
  const { data, error } = await supabase.rpc('byom_set_alerts', {
    p_model_id: modelId,
    p_enabled: enabled,
  });
  if (error) throw error;
  return data !== false;
}

