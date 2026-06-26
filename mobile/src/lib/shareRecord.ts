/**
 * Builds the text shared from the Track Record screen — the public-proof growth
 * loop. Uses the built-in React Native Share API (no native deps), so it ships
 * via an over-the-air update. An image-card version would need react-native-view-shot
 * (a native module → full rebuild) and is a deliberate follow-up.
 */

import type { TrackRecordSummary } from '@/lib/trackRecord';

export const APP_URL = 'https://signalbase-ai.com';

export function buildShareMessage(
  s: TrackRecordSummary,
  opts: { endUnits?: number | null; since?: string } = {},
): string {
  const pct = (v: number) => `${v >= 0 ? '+' : ''}${(v * 100).toFixed(1)}%`;
  const record = `${s.wins}-${s.losses}${s.pushes > 0 ? `-${s.pushes}` : ''}`;
  const lines: (string | null)[] = [
    '📊 Signalbase — verified sports-betting model',
    '',
    `${pct(s.roiFlat)} flat-bet ROI · ${record} (${Math.round(s.winRate * 100)}% win rate)`,
    opts.endUnits != null
      ? `${opts.endUnits >= 0 ? '+' : ''}${opts.endUnits.toFixed(1)} units on flat $100 bets`
      : null,
    s.clvBeatRate != null ? `Beat the closing line ${Math.round(s.clvBeatRate * 100)}% of the time` : null,
    opts.since ? `${s.picks} settled picks since ${opts.since}` : null,
    '',
    'Every pick public — wins, losses, no-pick days. Nothing cherry-picked.',
    APP_URL,
  ];
  return lines.filter((l) => l !== null).join('\n');
}
