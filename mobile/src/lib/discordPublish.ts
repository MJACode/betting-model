/**
 * Discord publish state is the board. VOID does not retract a post.
 *
 * Matt, 2026-09-23: Discord is the source of truth. Today / Signals show a
 * bet the channel still has, including one later marked VOID. A bet the
 * channel never got is not an active Discord-led bet.
 *
 * The ledger is `v_discord_published` (push_sent kinds discord_signal and
 * discord_live). The app cannot read push_sent itself. A failed read is
 * `unknown`: non-VOID bets keep the previous display, VOID stays hidden.
 *
 * The lock key is tracking/publish_keys.py. Null and empty identity parts
 * are omitted, matching COALESCE(':' || col, '').
 */

export type DiscordPublish = 'published' | 'unpublished' | 'unknown';

const KEY_PARTS = ['player_id', 'player_key', 'prop_market'] as const;

type LockPick = {
  game_id: string;
  model_id: string;
  pick_side?: string | null;
  player_id?: string | null;
  player_key?: string | null;
  prop_market?: string | null;
  is_live?: boolean | null;
  signal_type?: string | null;
  pick_id?: number;
};

export function lockKeyForPick(p: LockPick): string {
  const tail = KEY_PARTS.map((c) => p[c]).filter((c) => c).join(':');
  if (p.is_live) {
    const base = `live:${p.game_id}:${p.model_id}:${p.pick_side ?? ''}`;
    return tail ? `${base}:${tail}` : base;
  }
  return tail ? `${p.game_id}:${p.model_id}:${tail}` : `${p.game_id}:${p.model_id}`;
}

/**
 * A BET is on the Discord board.
 *
 * published  — the channel has it. VOID does not hide it.
 * unpublished — the channel does not. Not an active Discord-led bet.
 * unknown / omitted — ledger unread. Non-VOID stays; VOID stays hidden.
 */
export function discordLedVisible(
  conditionStatus: string | null | undefined,
  publish: DiscordPublish | undefined,
): boolean {
  if (publish === 'published') return true;
  if (conditionStatus === 'VOID') return false;
  if (publish === 'unpublished') return false;
  return true;
}

/** Today's scored list drops a VOID the channel does not still show. */
export function voidHiddenFromBoard(p: {
  condition_status: string | null;
  discordPublish?: DiscordPublish;
}): boolean {
  return p.condition_status === 'VOID' && p.discordPublish !== 'published';
}

/**
 * Still open for the user to act on — Track and betslip render.
 *
 * `result == null` is an unsettled pick. A VOID writes `result = 'NO_ACTION'`
 * as its marker, not as a settlement, so a VOID the channel still shows is
 * the same open bet (Matt, 2026-09-23) and keeps its actions. Without this a
 * published VOID drew on the board with no Track and no betslip — the
 * 2026-09-26 UFC card. The settled record still excludes it
 * (passesRecordFilter).
 */
export function openForAction(p: {
  result: string | null;
  condition_status: string | null;
  discordPublish?: DiscordPublish;
}): boolean {
  if (p.result == null) return true;
  return p.result === 'NO_ACTION'
    && p.condition_status === 'VOID'
    && p.discordPublish === 'published';
}

const CHUNK = 80;

/**
 * Ledger read for these picks. `null` means the read failed (view missing,
 * permission, network) — callers must treat that as `unknown`, not as
 * "Discord has nothing".
 */
export async function fetchPublishedLockKeys(picks: LockPick[]): Promise<Set<string> | null> {
  const keys = [...new Set(picks.filter((p) => p.signal_type === 'BET').map(lockKeyForPick))];
  if (keys.length === 0) return new Set();
  const { supabase } = await import('./supabase');
  const found = new Set<string>();
  const chunks: string[][] = [];
  for (let i = 0; i < keys.length; i += CHUNK) chunks.push(keys.slice(i, i + CHUNK));
  const results = await Promise.all(chunks.map((chunk) =>
    supabase.from('v_discord_published').select('lock_key').in('lock_key', chunk)));
  for (const { data, error } of results) {
    if (error) return null;
    for (const row of (data ?? []) as { lock_key: string }[]) found.add(row.lock_key);
  }
  return found;
}

export function discordPublishState(key: string, published: Set<string> | null): DiscordPublish {
  if (published == null) return 'unknown';
  return published.has(key) ? 'published' : 'unpublished';
}

export async function attachDiscordPublish<T extends LockPick & {
  signal_type?: string | null;
  discordPublish?: DiscordPublish;
}>(picks: T[]): Promise<T[]> {
  const published = await fetchPublishedLockKeys(picks);
  return picks.map((p) => ({
    ...p,
    discordPublish: p.signal_type === 'BET'
      ? discordPublishState(lockKeyForPick(p), published)
      : p.discordPublish,
  }));
}
