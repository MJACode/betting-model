/**
 * Builds the text shared from the Track Record screen — the public-proof growth
 * loop. Uses the built-in React Native Share API (no native deps), so it ships
 * via an over-the-air update. An image-card version would need react-native-view-shot
 * (a native module → full rebuild) and is a deliberate follow-up.
 */

import { formatPctSigned, formatSigned } from '@/lib/format';
import type { TrackRecordSummary } from '@/lib/trackRecord';

export const APP_URL = 'https://signalbase-ai.com';

export function buildShareMessage(
  s: TrackRecordSummary,
  opts: { endUnits?: number | null; since?: string } = {},
): string {
  const record = `${s.wins}-${s.losses}${s.pushes > 0 ? `-${s.pushes}` : ''}`;
  const recordLine = `${record} (${Math.round(s.winRate * 100)}% win rate)`;
  // Same gate as the cards: ROI is known only when something was risked.
  // An unset column (the select ran before the migration) and an all-void
  // selection (risked 0) both leave roi at 0. The record and the win rate stay.
  const roiKnown = (s.risked ?? 0) > 0;
  const lines: (string | null)[] = [
    '📊 Signalbase — verified sports-betting model',
    '',
    roiKnown ? `${formatPctSigned(s.roi)} ROI · ${recordLine}` : recordLine,
    opts.endUnits != null && roiKnown
      ? // Same sign and 2-decimal rounding as the equity curve (U+2212 for a loss).
        `${formatSigned(opts.endUnits, 2, 'u').replace(/u$/, '')} units, 1 to win`
      : null,
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
