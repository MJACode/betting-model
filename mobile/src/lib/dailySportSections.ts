/**
 * How the daily-results modal splits one day's sports.
 *
 * Pure. The modal builds the visible sections in canonical sport order and
 * passes that list here. A sport with picks, a pending pick, or a model row
 * stays in that order. A quiet sport stays in that same order on the lines
 * underneath: nothing unpublished is "No picks", and an unpublished count is
 * "Not posted". An unpublished count does not move a sport that had picks.
 */

export interface DailySportSection {
  sport: string;
  total: { picks: number };
  pending: number;
  unpublished: number;
  models: { readonly length: number };
}

/** The predicate the cards used before they were grouped. */
export function sportSectionHasActivity(section: DailySportSection): boolean {
  return section.total.picks > 0 || section.pending > 0 || section.models.length > 0;
}

export function partitionDailySportSections<T extends DailySportSection>(
  sections: readonly T[],
): { active: T[]; noPicks: string[]; notPosted: string[] } {
  const active: T[] = [];
  const noPicks: string[] = [];
  const notPosted: string[] = [];
  for (const section of sections) {
    if (sportSectionHasActivity(section)) {
      active.push(section);
      continue;
    }
    if (section.unpublished > 0) notPosted.push(section.sport);
    else noPicks.push(section.sport);
  }
  return { active, noPicks, notPosted };
}
