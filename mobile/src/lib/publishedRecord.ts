/**
 * Which settled picks the model detail screen counts.
 *
 * The Record reads v_public_track_record. That view is settled BETs Discord
 * still has, and its CLV columns count a pick only when clv_pct is present
 * and clv_method is no_vig or zero_vig. Model detail used to count every
 * settled BET (passesRecordFilter) and, for the list, every scored pick at
 * today's cut. Those are larger sets than the Record.
 *
 * `unknown` is not posted. A ledger read that failed does not invent a
 * published bet. The header still comes from the view when that fetch works.
 */
import type { DiscordPublish } from './discordPublish';
import { passesRecordFilter, type RecordFilterable } from './thresholds';

export const VIEW_CLV_METHODS = ['no_vig', 'zero_vig'] as const;

export function isPostedSettledBet(
  p: RecordFilterable & {
    result: string | null;
    discordPublish?: DiscordPublish;
  },
): boolean {
  if (!passesRecordFilter(p)) return false;
  if (p.result !== 'WIN' && p.result !== 'LOSS' && p.result !== 'PUSH') return false;
  return p.discordPublish === 'published';
}

export function countsTowardViewClv(p: {
  clv_pct: number | null | undefined;
  clv_method?: string | null;
}): boolean {
  if (p.clv_pct == null || !Number.isFinite(Number(p.clv_pct))) return false;
  return p.clv_method === 'no_vig' || p.clv_method === 'zero_vig';
}
