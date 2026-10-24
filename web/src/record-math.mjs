/**
 * Same rollup as mobile/src/lib/trackRecord.ts summarize() and groupBySport().
 *
 * Picks are wins + losses + pushes, not the view's picks column.
 * A retired model id is skipped, matching isModelRetired.
 * Sports covered are sports with a non-retired model whose picks column is > 0.
 * Units are the posted-stake `units` column the Record hero prints
 * (formatSigned to 2 decimals, U+2212 for a loss, unsigned when the
 * rounded value is zero). A missing units column hides the row.
 */

const MINUS = "\u2212";

export function formatSigned(value, digits = 2, suffix = "") {
  const n = Number(value);
  if (value == null || !Number.isFinite(n)) return "\u2014";
  const abs = Math.abs(n).toFixed(digits);
  if (Number(abs) === 0) return `${abs}${suffix}`;
  return `${n > 0 ? "+" : MINUS}${abs}${suffix}`;
}

/**
 * @param {Array<Record<string, unknown>>} rows
 * @param {Iterable<string>} retired
 * @returns {{picks: number, units: number, unitsText: string, sports: number} | null}
 */
export function summarizeRecord(rows, retired) {
  const retiredSet = retired instanceof Set ? retired : new Set(retired);
  const kept = [];
  for (const row of rows) {
    if (retiredSet.has(String(row.model_id))) continue;
    kept.push(row);
  }
  if (kept.length === 0) return null;
  const postedKnown = kept.some((row) => row.units != null || row.risked != null);
  if (!postedKnown) return null;

  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let units = 0;
  for (const row of kept) {
    wins += Number(row.wins ?? 0);
    losses += Number(row.losses ?? 0);
    pushes += Number(row.pushes ?? 0);
    units += Number(row.units ?? 0);
  }
  const picks = wins + losses + pushes;
  if (!(picks > 0)) return null;

  const sports = new Set();
  for (const row of kept) {
    if (Number(row.picks ?? 0) <= 0) continue;
    if (row.sport) sports.add(String(row.sport));
  }
  return {
    picks,
    units,
    unitsText: formatSigned(units, 2, "u"),
    sports: sports.size,
  };
}
