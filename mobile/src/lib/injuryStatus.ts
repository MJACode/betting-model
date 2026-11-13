/**
 * Injury tags on the Stats board.
 *
 * Matt, 2026-10-23, off a screenshot of NFL Anytime TD: Romeo Doubs ranked #3
 * while on Injured Reserve, and nothing on the row said so. The board now tags
 * every player on his team's injury report (IR / O / D / Q, or the MLB IL),
 * greys the row of anyone who is not playing, and sorts him below everyone who
 * is. A sidelined player also cannot be added to a bet (Matt, 2026-10-24):
 * the price pill does not press, and the betslip stores reject the leg.
 *
 * Source: `injury_status_current`, one row per player, kept by the injury
 * ingestor from ESPN's team lists (data/ingestors/injury_ingestor.py).
 */
import { normalizePlayerName } from '@/lib/playerNews';
import type { InjuryStatusRow } from '@/types';

/** A row the ingestor has not re-confirmed in this long is not shown. A feed
 *  outage then ages out, instead of freezing a player as Out for good. */
export const INJURY_FRESH_HOURS = 36;

export type InjuryTone = 'out' | 'warn';

export interface InjuryTag {
  /** What the chip prints: IR, O, D, Q, DTD, IL10, SUSP. */
  label: string;
  /** What VoiceOver says, and the chip's long form. */
  spoken: string;
  tone: InjuryTone;
  /** Not playing: the row greys out and sorts below everyone who is. */
  sidelined: boolean;
}

/**
 * The tag for one status. Null for anything the board has no tag for, so an
 * unknown designation shows nothing rather than a guess.
 */
export function injuryTag(status: string | null | undefined, injuryType?: string | null): InjuryTag | null {
  const type = (injuryType ?? '').trim().toLowerCase();
  switch (status) {
    case 'Out':
      if (type === 'injured reserve') return { label: 'IR', spoken: 'Injured reserve', tone: 'out', sidelined: true };
      if (type === 'suspension') return { label: 'SUSP', spoken: 'Suspended', tone: 'out', sidelined: true };
      return { label: 'O', spoken: 'Out', tone: 'out', sidelined: true };
    case 'IL10':
      return { label: 'IL10', spoken: '10-day injured list', tone: 'out', sidelined: true };
    case 'IL15':
      return { label: 'IL15', spoken: '15-day injured list', tone: 'out', sidelined: true };
    case 'IL60':
      return { label: 'IL60', spoken: '60-day injured list', tone: 'out', sidelined: true };
    case 'Doubtful':
      return { label: 'D', spoken: 'Doubtful', tone: 'out', sidelined: false };
    case 'Questionable':
      return { label: 'Q', spoken: 'Questionable', tone: 'warn', sidelined: false };
    case 'Day-To-Day':
      return { label: 'DTD', spoken: 'Day-to-day', tone: 'warn', sidelined: false };
    default:
      return null;
  }
}

export interface InjuryIndex {
  /** The tag for a board row, or null when he is not on a report. */
  lookup: (name: string | null | undefined, team?: string | null) => InjuryTag | null;
  size: number;
}

export const EMPTY_INJURY_INDEX: InjuryIndex = { lookup: () => null, size: 0 };

/**
 * The same lookup the board uses. True only when this player is not playing
 * (Out, IR, SUSP, IL). Questionable, Doubtful and Day-To-Day are false.
 * No row, an ambiguous name, and a stale row are false: the lookup already
 * decided those say nothing.
 */
export function playerIsSidelined(
  index: InjuryIndex,
  name: string | null | undefined,
  team?: string | null,
): boolean {
  return index.lookup(name, team)?.sidelined === true;
}

/**
 * Whether the Stats price pill accepts a tap.
 *
 * A sidelined player keeps the outlined pill and the ", not playing" label.
 * The control has no onPress and is disabled. Anyone still playing — including
 * Questionable and Doubtful — presses when the row handed the pill a handler.
 */
export function pricePillActivation(
  sidelined: boolean,
  hasHandler: boolean,
): { pressable: boolean; disabled: boolean } {
  if (sidelined) return { pressable: false, disabled: true };
  return { pressable: hasHandler, disabled: !hasHandler };
}

/**
 * Index the current rows for lookup by name and team.
 *
 * Team first: two players can share a name across the league (there are two
 * Josh Allens in the NFL), and the name alone would tag the healthy one. A
 * row with no team on the board falls back to the name only when exactly one
 * team lists that name.
 */
export function buildInjuryIndex(rows: readonly InjuryStatusRow[], nowMs: number): InjuryIndex {
  const cutoff = nowMs - INJURY_FRESH_HOURS * 3600_000;
  const byTeam = new Map<string, InjuryTag>();
  const byName = new Map<string, InjuryTag | null>();
  for (const r of rows) {
    const asOf = Date.parse(r.as_of);
    if (!Number.isFinite(asOf) || asOf < cutoff) continue;
    const tag = injuryTag(r.status, r.injury_type);
    if (!tag) continue;
    const key = r.player_key || normalizePlayerName(r.player_name);
    if (!key) continue;
    byTeam.set(`${r.team}|${key}`, tag);
    // Two teams list the name: ambiguous, so the name-only path says nothing.
    byName.set(key, byName.has(key) ? null : tag);
  }
  if (byTeam.size === 0) return EMPTY_INJURY_INDEX;
  return {
    size: byTeam.size,
    lookup: (name, team) => {
      const key = normalizePlayerName(name);
      if (!key) return null;
      if (team) return byTeam.get(`${team}|${key}`) ?? null;
      return byName.get(key) ?? null;
    },
  };
}

/**
 * Move sidelined players below everyone who is playing, keeping each group's
 * order. A filter-and-concat, so the existing sort stays the tiebreak.
 */
export function sinkSidelined<T>(list: readonly T[], isSidelined: (item: T) => boolean): T[] {
  const playing: T[] = [];
  const out: T[] = [];
  for (const item of list) (isSidelined(item) ? out : playing).push(item);
  return out.length === 0 ? (list as T[]) : playing.concat(out);
}
