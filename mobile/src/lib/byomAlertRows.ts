/**
 * Pure parsing for the member's open bets (byomAlerts.ts). No Supabase
 * import, so scripts/verify_byom_alerts.ts runs it under node.
 */

export interface ByomOpenBet {
  alert_id: string;
  model_id: string;
  model_name: string;
  sport: string;
  market: string;
  label: string;
  home_team: string | null;
  away_team: string | null;
  commence_time: string | null;
  price: number;
  /** When the line and price first fit the rules. */
  locked_at: string | null;
  /** When the worker found it (the alert's time). */
  detected_at: string;
  /** Kickoff has passed; the result is not in yet. */
  started: boolean;
}

export type ByomOpenBetsResult =
  | { status: 'ok'; bets: ByomOpenBet[] }
  | { status: 'unavailable' };

/** PostgREST / Postgres "no such function": the migration is not applied. */
export function isMissingFunction(e: unknown): boolean {
  if (e == null || typeof e !== 'object') return false;
  const code = (e as Record<string, unknown>).code;
  return code === 'PGRST202' || code === '42883';
}

function str(v: unknown): string | null {
  return typeof v === 'string' && v !== '' ? v : null;
}

function num(v: unknown): number | null {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN;
  return Number.isFinite(n) ? n : null;
}

/** One row, or null when a field the card needs is missing. */
export function parseOpenBet(row: unknown): ByomOpenBet | null {
  if (row == null || typeof row !== 'object') return null;
  const r = row as Record<string, unknown>;
  const alertId = str(r.alert_id);
  const modelId = str(r.model_id);
  const label = str(r.label);
  const price = num(r.price);
  const detected = str(r.detected_at);
  if (!alertId || !modelId || !label || price == null || !detected) return null;
  return {
    alert_id: alertId,
    model_id: modelId,
    model_name: str(r.model_name) ?? 'My model',
    sport: str(r.sport) ?? 'NFL',
    market: str(r.market) ?? '',
    label,
    home_team: str(r.home_team),
    away_team: str(r.away_team),
    commence_time: str(r.commence_time),
    price,
    locked_at: str(r.locked_at),
    detected_at: detected,
    started: r.started === true,
  };
}

/** "DET @ BUF" from the stored teams, or null. */
export function matchupLabel(bet: Pick<ByomOpenBet, 'home_team' | 'away_team'>): string | null {
  if (!bet.home_team || !bet.away_team) return null;
  return `${bet.away_team} @ ${bet.home_team}`;
}
