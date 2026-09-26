/**
 * "Which day am I looking at?" — the DATE cut on the Picks board.
 *
 * Matt, 2026-09-26, from the NCAAF board: *"Add a Filter by date because games
 * could be on different days."* That board held a live game, a 6:30 PM kickoff
 * and a look-ahead pick for Sat 11/28 in the first three cards — three different
 * days, sorted by edge, with nothing but a small kickoff stamp to tell them
 * apart.
 *
 * The cut is a set of `game_date`s (the ET date of kickoff — the one the whole
 * pipeline files a game under). EMPTY MEANS EVERY DATE, the same contract as
 * the Games cut: a filter that starts by hiding the board is a broken screen.
 *
 * THIS IS A VIEWER'S FILTER, NOT A DATE HORIZON. CLAUDE.md's publishing rule
 * forbids a horizon on a publishing surface because it drops picks quietly.
 * This one drops nothing unless the user taps a day, it defaults to every date,
 * and while it narrows the board it shows as a badge, a removable pill and a
 * "n/m" count on the bar — the same visibility every other cut has.
 *
 * NOT PERSISTED, for the Games cut's reason: a date is one day, and a stored
 * "Sat" would be filtering next Saturday's board to nothing.
 */

import { dayLabelET, dayLabelSpokenET, todayET } from './format';

export interface DateOption {
  /** YYYY-MM-DD, the pick's `game_date`. */
  date: string;
  /** "Today" / "Tomorrow" / "Sat 11/28". */
  label: string;
  /** The same day for VoiceOver: "Saturday, November 28". */
  spoken: string;
  /** Picks on the board for that date. */
  count: number;
}

/** 'Today' / 'Tomorrow' / 'Yesterday' / 'Sat 11/28' — the app's one day label. */
export function dateLabel(date: string, today: string = todayET()): string {
  return dayLabelET(date, today);
}

/**
 * The dates the picks on screen fall on, earliest first, each with its count.
 * Only dates that hold a pick — the chips can never offer an empty day.
 */
export function dateOptionsFor(
  dates: Iterable<string | null | undefined>,
  today: string = todayET(),
): DateOption[] {
  const counts = new Map<string, number>();
  for (const d of dates) if (d) counts.set(d, (counts.get(d) ?? 0) + 1);
  return Array.from(counts.keys())
    .sort()
    .map((date) => ({
      date,
      label: dateLabel(date, today),
      spoken: dayLabelSpokenET(date, today),
      count: counts.get(date)!,
    }));
}

/** Is a pick on this date in the selection? Empty selection = every date. */
export function isDateSelected(date: string | null | undefined, selected: Set<string>): boolean {
  if (selected.size === 0) return true;
  return !!date && selected.has(date);
}

/**
 * The selection this board can honour — DISPLAY ONLY, never written back.
 *
 * The same selection follows the reader across Today / Signals / Live, which
 * hold different picks, so a day picked on Today can be absent from Signals.
 * If NONE of the chosen days is on this board the cut would empty it while the
 * chips (which only list present days) showed nothing selected — the exact
 * "board looks broken, no control says why" failure. So an impossible
 * selection READS as every date here; a partly present one is kept as the
 * real filter it still is. The caller keeps the user's own choice untouched,
 * so Today → Live → Today comes back to the day they picked (UX review,
 * 2026-09-26: the first version saved the fallback and erased it).
 */
export function effectiveDateSelection(selected: Set<string>, options: DateOption[]): Set<string> {
  if (selected.size === 0) return selected;
  const present = new Set(options.map((o) => o.date));
  for (const d of selected) if (present.has(d)) return selected;
  return new Set<string>();
}

/** Is the Date cut narrowing THIS board? */
export function datesAreNarrowed(selected: Set<string>, options: DateOption[]): boolean {
  if (selected.size === 0) return false;
  const shown = options.filter((o) => selected.has(o.date)).length;
  return shown > 0 && shown < options.length;
}

/** "All dates" / "Today" / "Sat 11/28" / "2 dates" — summary and pill label. */
export function dateFilterSummary(selected: Set<string>, options: DateOption[]): string {
  const shown = options.filter((o) => selected.has(o.date));
  if (selected.size === 0 || shown.length === 0 || shown.length === options.length) {
    return 'All dates';
  }
  if (shown.length === 1) return shown[0]!.label;
  return `${shown.length} dates`;
}
