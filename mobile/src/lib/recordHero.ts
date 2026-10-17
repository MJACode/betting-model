/**
 * Designer's Option B for the Record headline.
 *
 * The big number is the posted-stake units Discord prints on the all-time
 * line (`_tally_line`: `{units:+.2f}u`). The same string is the equity
 * curve's end pill. The grid's return is that stake's units / risked, the
 * percentage beside Discord's units. The visible name is "Return on bets".
 * VoiceOver still hears Discord's "All-time". Yesterday and Models still
 * use a flat $100 bet. Do not put Yesterday's name for its book on this card.
 */

import { spokenDate, unitsSpeech, unknownCountSpeech } from '@/lib/a11y';
import { formatPct, formatPctSigned, formatSigned } from '@/lib/format';
import { LIVE_RECORD_START, LIVE_RECORD_START_SHORT, MIN_PICKS_FOR_COLOURED_ROI, thinSampleCaption } from '@/lib/recordStart';
import { pnlTone } from '@/lib/tone';

/** Discord's all-time field name. A sport filter replaces it with that sport. */
export const DISCORD_ALL_TIME_LABEL = 'All-time';

/** Visible hero title. VoiceOver keeps DISCORD_ALL_TIME_LABEL. */
export const HERO_VISIBLE_ALL_TIME = 'Total profit · all time';

export function heroVisibleLabel(discordLabel: string): string {
  if (discordLabel === DISCORD_ALL_TIME_LABEL) return HERO_VISIBLE_ALL_TIME;
  return `Total profit · ${discordLabel}`;
}

/** Small line under the units number. */
export const UNITS_CAPTION = 'Units · 1 to win';

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
  return formatPct(winRate, 1);
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
      : `${unitsSpeech(heroUnitsText(o.units, false))}, 1 to win`;
  const quiet = o.notLoaded || o.picks <= 0;
  const roi = returnOnBetsSpeech(roiText(o.roiFlat, o.risked, quiet));
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
    roi,
    record,
    `Win rate ${win === '—' ? 'unavailable' : win}`,
    `Beat the closing line ${clv === '—' ? 'unavailable' : clv}`,
  ].join('. ');
}

/** Positive ends in betInk. A loss is avoidInk. Flat is neutral. Never the bright green. */
export function equityStrokeToken(units: number): 'betInk' | 'avoidInk' | 'textSecondary' {
  return pnlTone(units, 2);
}

/** Sheet title. The cell says "Return on bets". */
export const ROI_SHEET_TITLE = 'Return on bets (ROI)';

/** "+2.5%" → "Return on bets, 2.5 percent". An em dash is unavailable. */
export function returnOnBetsSpeech(roi: string): string {
  if (roi === '—') return 'Return on bets, unavailable';
  const minus = roi.startsWith('\u2212') || roi.startsWith('-');
  const digits = roi.replace(/^[+\u2212-]/, '').replace('%', '');
  return `Return on bets, ${minus ? 'minus ' : ''}${digits} percent`;
}

export function roiSheetBody(): string {
  return (
    'Each pick risks the amount needed to win 1 unit. ' +
    'At −110 that\u2019s 1.1 units to win 1. ' +
    'Risk is capped at 3 units, and a pick with no price counts as 1 unit. ' +
    'This number is units won or lost divided by units risked. ' +
    'It matches the percentage in Discord\u2019s all-time line. ' +
    'Yesterday and Models use a flat $100 bet, so their percentages won\u2019t match.'
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
