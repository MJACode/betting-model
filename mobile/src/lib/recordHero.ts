/**
 * Designer's Option B for the Record headline.
 *
 * The big number is the posted-stake units Discord prints on the all-time
 * line (`_tally_line`: `{units:+.2f}u`). The same string is the equity
 * curve's end pill. Flat-bet ROI on the grid is that stake's return
 * (units / risked), which is the +2.5% beside Discord's units — not the
 * flat $100 book Yesterday and Models still use.
 */

import { spokenDate, unitsSpeech, unknownCountSpeech } from '@/lib/a11y';
import { formatPct, formatPctSigned, formatSigned } from '@/lib/format';
import { LIVE_RECORD_START, LIVE_RECORD_START_SHORT, MIN_PICKS_FOR_COLOURED_ROI, thinSampleCaption } from '@/lib/recordStart';
import { pnlTone } from '@/lib/tone';

/** Discord's all-time field name. A sport filter replaces it with that sport. */
export const DISCORD_ALL_TIME_LABEL = 'All-time';

/** Above this Dynamic Type scale the hero stacks. Narrow phones stack sooner. */
export const HERO_STACK_AT = 1.2;

export function heroStacks(fontScale: number, width = 390): boolean {
  if (!Number.isFinite(fontScale) || fontScale <= 0) return false;
  if (fontScale >= HERO_STACK_AT) return true;
  return width < 380 && fontScale >= 1.1;
}

/** Discord's `{units:+.2f}u`, with the app's U+2212 for a loss. */
export function heroUnitsText(units: number, notLoaded: boolean): string {
  if (notLoaded) return '—';
  return formatSigned(units, 2, 'u');
}

export function roiText(roiFlat: number, risked: number, notLoaded: boolean): string {
  if (notLoaded || !(risked > 0)) return '—';
  return formatPctSigned(roiFlat);
}

export function recordLine(wins: number, losses: number, pushes: number, notLoaded: boolean): string {
  if (notLoaded) return '—';
  return `${wins}–${losses}${pushes > 0 ? `–${pushes}` : ''}`;
}

export function winRateText(winRate: number, wins: number, losses: number, notLoaded: boolean): string {
  if (notLoaded || wins + losses <= 0) return '—';
  return formatPct(winRate, 0);
}

export function clvText(rate: number | null, notLoaded: boolean): string {
  if (notLoaded || rate == null) return '—';
  return formatPct(rate, 0);
}

export function sinceLine(): string {
  return `since ${LIVE_RECORD_START_SHORT}`;
}

/**
 * One VoiceOver stop. Units are the first words, then the Discord label,
 * the date, and the four grid cells.
 */
export function heroAccessibilityLabel(o: {
  notLoaded: boolean;
  picks: number;
  label: string;
  units: number;
  risked: number;
  roiFlat: number;
  wins: number;
  losses: number;
  pushes: number;
  winRate: number;
  clvBeatRate: number | null;
}): string {
  const units = o.notLoaded
    ? 'Units unavailable'
    : o.picks <= 0
      ? 'No settled picks'
      : unitsSpeech(heroUnitsText(o.units, false));
  const quiet = o.notLoaded || o.picks <= 0;
  const roi = roiText(o.roiFlat, o.risked, quiet);
  const record = o.notLoaded
    ? unknownCountSpeech('— settled picks')
    : o.picks <= 0
      ? 'Record unavailable'
      : `Record ${o.wins} wins, ${o.losses} losses${o.pushes > 0 ? `, ${o.pushes} pushes` : ''}`;
  const win = winRateText(o.winRate, o.wins, o.losses, quiet);
  const clv = clvText(o.clvBeatRate, quiet);
  return [
    units,
    o.label,
    `since ${spokenDate(LIVE_RECORD_START)}`,
    `Flat-bet ROI ${roi === '—' ? 'unavailable' : roi}`,
    record,
    `Win rate ${win === '—' ? 'unavailable' : win}`,
    `Beat the closing line ${clv === '—' ? 'unavailable' : clv}`,
  ].join('. ');
}

/** Positive ends in betInk. A loss is avoidInk. Flat is neutral. Never the bright green. */
export function equityStrokeToken(units: number): 'betInk' | 'avoidInk' | 'textSecondary' {
  return pnlTone(units, 2);
}

export const FLAT_BET_ROI_TITLE = 'Flat-bet ROI';

export function flatBetRoiBody(): string {
  return (
    'This is units won or lost divided by units risked. Each bet is 1 unit to win, ' +
    'at the price it was taken at. At −110 that is 1.1 units risked to win 1. ' +
    'Nothing risks more than 3, and a heavier favorite still risks 3 and wins less than 1. ' +
    'It is the same percentage Discord posts beside the all-time units. ' +
    'Yesterday and the Models tab use a flat $100 bet, so their percentages will not match this one.'
  );
}

export const CLOSING_LINE_TITLE = 'Beat the closing line';

export function closingLineBody(o: {
  clvSettled: number;
  clvBeatRate: number | null;
  clvGameSettled: number;
  clvGameBeatRate: number | null;
  clvPropSettled: number;
  clvPropBeatRate: number | null;
  marketClvSettled: number;
  marketClvBeatRate: number | null;
}): string {
  const lead =
    'Closing line value checks whether the book we bet closed at a shorter price than the one we took, on the same number. ' +
    'A moved number is left out. Game lines and props are both in the figure.';
  if (!(o.clvSettled > 0) || o.clvBeatRate == null) {
    return `${lead}\n\nWe don’t have a closing price for these bets yet.`;
  }
  const figures = [
    `Overall  ${formatPct(o.clvBeatRate, 0)} of ${o.clvSettled}`,
    splitPiece('Game lines', o.clvGameSettled, o.clvGameBeatRate),
    splitPiece('Props', o.clvPropSettled, o.clvPropBeatRate),
  ];
  if (o.marketClvSettled > 0 && o.marketClvBeatRate != null) {
    figures.push(splitPiece('Pinnacle’s fair close', o.marketClvSettled, o.marketClvBeatRate));
  }
  return [lead, '', ...figures.filter((line) => line !== '')].join('\n');
}

function splitPiece(label: string, settled: number, rate: number | null): string {
  if (settled <= 0) return '';
  if (settled < MIN_PICKS_FOR_COLOURED_ROI) return `${label}  ${thinSampleCaption()}`;
  return `${label}  ${rate != null ? formatPct(rate, 0) : '—'} of ${settled}`;
}
