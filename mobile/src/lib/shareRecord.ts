/**
 * Builds the text shared from the Track Record screen — the public-proof growth
 * loop. Uses the built-in React Native Share API (no native deps), so it ships
 * via an over-the-air update. An image-card version would need react-native-view-shot
 * (a native module → full rebuild) and is a deliberate follow-up.
 */

import { formatPct, formatPctSigned, formatSigned } from '@/lib/format';
import type { TrackRecordSummary } from '@/lib/trackRecord';

export const APP_URL = 'https://signalbase-ai.com';

export function buildShareMessage(
  s: TrackRecordSummary,
  opts: { endUnits?: number | null; since?: string } = {},
): string {
  const record = `${s.wins}-${s.losses}${s.pushes > 0 ? `-${s.pushes}` : ''}`;
  const lines: (string | null)[] = [
    '📊 Signalbase — verified sports-betting model',
    '',
    opts.endUnits != null
      ? // Same sign and 2-decimal rounding as the hero and the equity curve.
        `${formatSigned(opts.endUnits, 2, 'u').replace(/u$/, '')} units, 1 to win`
      : null,
    `${formatPctSigned(s.roi)} ROI · ${record} (${formatPct(s.winRate, 1)} win rate)`,
    s.clvBeatRate != null
      ? `Beat the closing price at the book we bet, ${Math.round(s.clvBeatRate * 100)}% of the time`
      : null,
    opts.since ? `${s.picks} settled picks since ${opts.since}` : null,
    '',
    'Every pick public — wins, losses, no-pick days. Nothing cherry-picked.',
    APP_URL,
  ];
  return lines.filter((l) => l !== null).join('\n');
}
