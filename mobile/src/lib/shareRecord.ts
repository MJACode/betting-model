/**
 * Builds the text shared from the Track Record screen — the public-proof growth
 * loop. Uses the built-in React Native Share API (no native deps), so it ships
 * via an over-the-air update. An image-card version would need react-native-view-shot
 * (a native module → full rebuild) and is a deliberate follow-up.
 */

import { formatClvBeatLine } from '@/lib/clvBeat';
import { formatPct, formatPctSigned, formatSigned } from '@/lib/format';
import type { TrackRecordSummary } from '@/lib/trackRecord';

export const APP_URL = 'https://signalbase-ai.com';

function clvShareLine(s: TrackRecordSummary): string | null {
  const pushes = s.clvPush ?? 0;
  const beats = s.clvBeat ?? 0;
  const decisive = Math.max(0, (s.clvSettled ?? 0) - pushes);
  const losses = Math.max(0, decisive - beats);
  if (s.clvBeatRate == null && pushes <= 0) return null;
  const clause = formatClvBeatLine(beats, losses, pushes);
  if (!clause) return null;
  return `Beat the closing price at the book we bet, ${clause}`;
}

export function buildShareMessage(
  s: TrackRecordSummary,
  opts: { endUnits?: number | null; since?: string } = {},
): string {
  const record = `${s.wins}-${s.losses}${s.pushes > 0 ? `-${s.pushes}` : ''}`;
  const recordLine = `${record} (${formatPct(s.winRate, 1)} win rate)`;
  // Same gate as the cards: ROI is known only when something was risked.
  // An unset column (the select ran before the migration) and an all-void
  // selection (risked 0) both leave roi at 0. The record and the win rate stay.
  const roiKnown = (s.risked ?? 0) > 0;
  const lines: (string | null)[] = [
    '📊 Signalbase — verified sports-betting model',
    '',
    opts.endUnits != null && roiKnown
      ? // Same sign and 2-decimal rounding as the hero and the equity curve.
        `${formatSigned(opts.endUnits, 2, 'u').replace(/u$/, '')} units, 1 to win`
      : null,
    roiKnown ? `${formatPctSigned(s.roi)} ROI · ${recordLine}` : recordLine,
    clvShareLine(s),
    opts.since ? `${s.picks} settled picks since ${opts.since}` : null,
    '',
    'Every pick public — wins, losses, no-pick days. Nothing cherry-picked.',
    APP_URL,
  ];
  return lines.filter((l) => l !== null).join('\n');
}
