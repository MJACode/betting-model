/**
 * Each model's published record, and whether it is HOT or COLD — for the
 * Model section of the Picks filter sheet (Matt, 2026-11-18).
 *
 *   - The number on the row is the model's TOTAL published record: units and
 *     settled bets since the record started (v_public_track_record, the same
 *     rows the Record tab and Discord #results sum).
 *   - HOT / COLD reads the last 7 days, ending yesterday ET
 *     (v_public_track_record_model_daily): up or down at least
 *     HEAT_MIN_UNITS on at least HEAT_MIN_BETS settled bets. Anything else
 *     carries no tag — one bad night is not a cold streak.
 *
 * Pure: the hook (useModelFilterRecords) fetches, this decides.
 */

import { addDays, formatSigned } from '@/lib/format';
import { unitsSpeech } from '@/lib/a11y';

export const HEAT_WINDOW_DAYS = 7;
export const HEAT_MIN_UNITS = 3;
export const HEAT_MIN_BETS = 8;

export type ModelHeat = 'hot' | 'cold' | null;

export interface ModelRecordSummary {
  /** Settled bets in the whole published record. */
  bets: number;
  /** Units on the posted stake, whole published record. */
  units: number;
  /** Settled bets and units in the heat window. */
  windowBets: number;
  windowUnits: number;
  heat: ModelHeat;
}

export interface ModelTotalRow {
  model_id: string;
  picks: number | string | null;
  units?: number | string | null;
}

export interface ModelDailyRow {
  game_date: string;
  model_id: string;
  picks: number | string | null;
  units?: number | string | null;
}

export { addDays };

/** The heat window for a given ET "today": [first, last], both inclusive. */
export function heatWindow(today: string): { first: string; last: string } {
  return { first: addDays(today, -HEAT_WINDOW_DAYS), last: addDays(today, -1) };
}

export function heatFor(windowBets: number, windowUnits: number): ModelHeat {
  if (windowBets < HEAT_MIN_BETS) return null;
  if (windowUnits >= HEAT_MIN_UNITS) return 'hot';
  if (windowUnits <= -HEAT_MIN_UNITS) return 'cold';
  return null;
}

/**
 * One summary per model. A model can have several total rows (one per sport
 * it was scored under); they are summed. Daily rows outside the window are
 * ignored, so the caller may pass a wider read.
 */
export function buildModelRecords(
  totals: ModelTotalRow[],
  daily: ModelDailyRow[],
  today: string,
): Record<string, ModelRecordSummary> {
  const out: Record<string, ModelRecordSummary> = {};
  const get = (id: string) =>
    (out[id] ??= { bets: 0, units: 0, windowBets: 0, windowUnits: 0, heat: null });
  for (const r of totals) {
    const s = get(r.model_id);
    s.bets += Number(r.picks ?? 0);
    s.units += Number(r.units ?? 0);
  }
  const { first, last } = heatWindow(today);
  for (const r of daily) {
    if (r.game_date < first || r.game_date > last) continue;
    const s = get(r.model_id);
    s.windowBets += Number(r.picks ?? 0);
    s.windowUnits += Number(r.units ?? 0);
  }
  for (const s of Object.values(out)) s.heat = heatFor(s.windowBets, s.windowUnits);
  return out;
}

/**
 * "+4.24u · 61 bets" — the same 2-decimal units the Record tab and the model
 * pages print for the same view (formatSigned(units, 2, 'u')).
 */
export function modelRecordLine(r: ModelRecordSummary): string {
  if (r.bets === 0) return 'No settled bets yet';
  return `${formatSigned(r.units, 2, 'u')} · ${r.bets} bet${r.bets === 1 ? '' : 's'}`;
}

/** Spoken form of modelRecordLine and the tag. */
export function modelRecordSpoken(r: ModelRecordSummary): string {
  const tag =
    r.heat === 'hot'
      ? `, hot over the last ${HEAT_WINDOW_DAYS} days`
      : r.heat === 'cold'
        ? `, cold over the last ${HEAT_WINDOW_DAYS} days`
        : '';
  return `${unitsSpeech(modelRecordLine(r).replace(' · ', ', '))}${tag}`;
}

/** The footnote under the list, built from the same constants as the tag. */
export function modelHeatFootnote(): string {
  return (
    `Record: every settled bet, in units. HOT or COLD: up or down ${HEAT_MIN_UNITS}u or more ` +
    `over the last ${HEAT_WINDOW_DAYS} days, on at least ${HEAT_MIN_BETS} bets.`
  );
}
