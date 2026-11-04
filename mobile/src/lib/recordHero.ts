/**
 * Designer's Option B for the Record headline.
 *
 * The big number is the posted-stake units Discord prints on the all-time
 * line (`_tally_line`: `{units:+.2f}u`). The same string is the equity
 * curve's end pill. The grid's return is that stake's units / risked, the
 * percentage beside Discord's units. The visible name is "Return on bets".
 * VoiceOver still hears Discord's "All-time". Yesterday uses this same
 * posted stake, and so do the Models tab and the model pages (one unit
 * basis, 2026-11-03). Do not put the Models
 * tab's book on this card.
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

export function roiText(roi: number, risked: number, notLoaded: boolean): string {
  if (notLoaded || !(risked > 0)) return '—';
  return formatPctSigned(roi);
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
  /** False when the select fell back and the units column is not there yet. */
  unitsKnown?: boolean;
  roi: number;
  wins: number;
  losses: number;
  pushes: number;
  winRate: number;
  clvBeatRate: number | null;
  clvPush?: number;
}): string {
  const units = o.notLoaded || o.unitsKnown === false
    ? 'Units unavailable'
    : o.picks <= 0
      ? 'No settled picks'
      : `${unitsSpeech(heroUnitsText(o.units, false))}, 1 to win`;
  const quiet = o.notLoaded || o.picks <= 0;
  const roi = returnOnBetsSpeech(roiText(o.roi, o.risked, quiet || o.unitsKnown === false));
  const record = o.notLoaded
    ? unknownCountSpeech('— settled picks')
    : o.picks <= 0
      ? 'Record unavailable'
      : `Record ${o.wins} wins, ${o.losses} losses${o.pushes > 0 ? `, ${o.pushes} pushes` : ''}`;
  const win = winRateText(o.winRate, o.wins, o.losses, quiet);
  const clv = clvText(o.clvBeatRate, quiet);
  const pushes = o.clvPush ?? 0;
  const clvSpoken = quiet
    ? 'unavailable'
    : clv === '—'
      ? (pushes > 0 ? `0 measured, ${pushes} push` : 'unavailable')
      : pushes > 0 ? `${clv}, ${pushes} push` : clv;
  return [
    units,
    o.label,
    `since ${spokenDate(LIVE_RECORD_START)}`,
    roi,
    record,
    `Win rate ${win === '—' ? 'unavailable' : win}`,
    `Beat the closing line ${clvSpoken}`,
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
    'Yesterday\u2019s percentage, and each model\u2019s on the Models tab, is worked out the same way.'
  );
}

export const CLOSING_LINE_TITLE = 'Beat the closing line';

export function closingLineBody(o: {
  clvSettled: number;
  clvBeatRate: number | null;
  clvPush?: number;
  clvGameSettled: number;
  clvGameBeatRate: number | null;
  clvGamePush?: number;
  clvPropSettled: number;
  clvPropBeatRate: number | null;
  clvPropPush?: number;
  marketClvSettled: number;
  marketClvBeatRate: number | null;
}): string {
  const lead =
    'Closing line value checks whether the book we bet closed at a shorter price than the one we took, on the same number. ' +
    'A moved number is left out. A close that matches the price we took is a push and is left out of the rate. Game lines and props are both in the figure.';
  const pushes = o.clvPush ?? 0;
  if (!(o.clvSettled > 0)) {
    return `${lead}\n\nWe don’t have a closing price for these bets yet.`;
  }
  if (o.clvBeatRate == null) {
    return `${lead}\n\n0 measured, ${pushes} push`;
  }
  const figures = [
    splitPiece('Overall', o.clvSettled, o.clvBeatRate, pushes),
    splitPiece('Game lines', o.clvGameSettled, o.clvGameBeatRate, o.clvGamePush ?? 0),
    splitPiece('Props', o.clvPropSettled, o.clvPropBeatRate, o.clvPropPush ?? 0),
  ];
  if (o.marketClvSettled > 0 && o.marketClvBeatRate != null) {
    figures.push(
      `${splitPiece('Pinnacle’s fair close', o.marketClvSettled, o.marketClvBeatRate, 0)}. A matching Pinnacle price still counts here`,
    );
  }
  return [lead, '', ...figures.filter((line) => line !== '')].join('\n');
}

function splitPiece(label: string, settled: number, rate: number | null, pushes: number): string {
  if (settled <= 0) return '';
  const decisive = Math.max(0, settled - pushes);
  if (decisive <= 0) return `${label}  0 measured, ${pushes} push`;
  const pushNote = pushes > 0 ? `, ${pushes} push` : '';
  if (decisive < MIN_PICKS_FOR_COLOURED_ROI) return `${label}  ${thinSampleCaption()}${pushNote}`;
  return `${label}  ${rate != null ? formatPct(rate, 0) : '—'} of ${decisive}${pushNote}`;
}
