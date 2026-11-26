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
  /**
   * DraftKings' line in force now for the same bet, labelled by the server
   * (byom_leg_label) like `label`. Null when no current quote is stored.
   */
  now_label: string | null;
  now_price: number | null;
  now_at: string | null;
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
    now_label: str(r.now_label),
    now_price: num(r.now_price),
    now_at: str(r.now_at),
  };
}

/**
 * The line now, when it differs from the bet's: "BUF -2.5", "-105". Null
 * when there is no current quote or nothing moved. Both strings come from
 * the server; nothing here rebuilds a line (CLAUDE.md §00).
 */
export function movedLine(
  bet: Pick<ByomOpenBet, 'label' | 'price' | 'now_label' | 'now_price' | 'started'>,
): { label: string; price: number } | null {
  // After the start a quote is in-play or frozen, and either reads as live.
  if (bet.started) return null;
  if (bet.now_label == null || bet.now_price == null) return null;
  if (bet.now_label === bet.label && bet.now_price === bet.price) return null;
  return { label: bet.now_label, price: bet.now_price };
}

/** "DET @ BUF" from the stored teams, or null. */
export function matchupLabel(bet: Pick<ByomOpenBet, 'home_team' | 'away_team'>): string | null {
  if (!bet.home_team || !bet.away_team) return null;
  return `${bet.away_team} @ ${bet.home_team}`;
}
