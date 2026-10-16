/**
 * Signals pick card copy (Picks > Signals, Designer Option A).
 *
 * Pure — no React Native — so the card, VoiceOver and the verify script
 * share one sentence. The bet is quoted from `pick_label` (CLAUDE.md §00):
 * a total drops only the matchup prefix, because the compact line already
 * names the teams. A signed number uses U+2212; a hyphen inside a name
 * ("Louisiana-Monroe") stays a hyphen.
 */

import { MINUS } from './format';

/** ASCII hyphen used as a minus sign → U+2212. Names with hyphens are left. */
export function trueMinus(text: string): string {
  return text.replace(/(^|[\s(])-(?=\d)/g, `$1${MINUS}`);
}

/**
 * The bet the Signals card headlines.
 * "Sam Houston -7.5" → "Sam Houston −7.5".
 * "NYY vs BOS Over 8.5" → "Over 8.5" (the teams are the line above).
 * A prop keeps the stored label, player included.
 */
export function signalsBetHeadline(pickLabel: string | null | undefined): string {
  const label = (pickLabel ?? '').trim();
  const total = label.match(/^(?:.+?)\s+(?:vs|@)\s+(?:.+?)\s+((?:Over|Under)\b.*)$/);
  // NFL card labels append the stake ("· 1.00u"). The stake cell owns that
  // number; the hero is the bet.
  const bet = (total ? total[1] : label).replace(/\s·\s[\d.]+u$/, '');
  return trueMinus(bet);
}

/** "−110 MGM" — the decision price and the book that price came from. */
export function signalsPriceText(priceText: string, book: string): string {
  return `${trueMinus(priceText)} ${book}`.trim();
}

/**
 * "Bet MGM −110". The word is Bet (the best bettable book is named, not
 * implied to be DraftKings). No price → "Open <book>", never a made-up number.
 */
export function signalsCtaLabel(book: string, priceText: string | null): string {
  if (!priceText) return `Open ${book}`;
  return `Bet ${book} ${trueMinus(priceText)}`;
}

/**
 * Clock for the compact line. `gameDayLabelET` is null on the ET day of the
 * game, so a today card stays "8:00 PM ET". A later day is "Sat 10/17 · 8:00
 * PM ET" — the Signals board mixes dates and has no day headers.
 */
export function signalsContextTime(
  day: string | null | undefined,
  clock: string | null | undefined,
): string {
  return [day, clock].filter((part): part is string => Boolean(part && part.length > 0)).join(' · ');
}

/**
 * VoiceOver for the Signals hero. The 22pt number is the decision price, so
 * that is what is spoken, with the full book name. A moved current price is
 * the next sentence. Stale and untracked cards stay on `heroPriceSpeech`.
 */
export function signalsHeroSpeech(input: {
  decisionPrice: string;
  book: string;
  currentPrice?: string | null;
}): string {
  const locked = `${trueMinus(input.decisionPrice)} ${input.book}`.trim();
  if (!input.currentPrice) return locked;
  return `${locked}. Now ${trueMinus(input.currentPrice)} ${input.book}`.trim();
}

/**
 * Team token for the compact line. Pro sports already store abbreviations.
 * NCAAF stores the school name; the registry abbreviation is used when we
 * have it. An unknown school stays the school name — a code is not invented.
 */
export function compactTeam(
  name: string,
  sport: string,
  abbrevs?: ReadonlyMap<string, string> | null,
): string {
  if (sport !== 'NCAAF') return name;
  const hit = abbrevs?.get(name)?.trim();
  return hit ? hit : name;
}

/** "WKU @ SHSU · NCAAF · 8:00 PM ET". Golf is the event. UFC uses "vs". */
export function signalsContextLine(input: {
  sport: string;
  away: string;
  home: string;
  timeLabel: string;
  abbrevs?: ReadonlyMap<string, string> | null;
}): string {
  const { sport } = input;
  const away = compactTeam(input.away, sport, input.abbrevs);
  const home = compactTeam(input.home, sport, input.abbrevs);
  let matchup = '';
  if (sport === 'GOLF' || !away || away === 'FIELD') matchup = home;
  else if (!home) matchup = away;
  else matchup = `${away} ${sport === 'UFC' ? 'vs' : '@'} ${home}`;
  return [matchup, sport, input.timeLabel].filter((part) => part.length > 0).join(' · ');
}

/** Full names, "at" / "versus", for the card's VoiceOver label. */
export function signalsTeamsSpeech(sport: string, away: string, home: string): string | null {
  if (sport === 'GOLF' || !away || away === 'FIELD') return home || null;
  if (!home) return away || null;
  return `${away} ${sport === 'UFC' ? 'versus' : 'at'} ${home}`;
}

/**
 * The stake cell. One figure, the units to win (`stake.win` when a price
 * exists, otherwise the conviction). Never "1.1u → 1u", never dollars.
 */
export function signalsStakeUnits(stake: {
  priced: boolean;
  win: number;
  conviction: number;
}): number {
  return stake.priced ? stake.win : stake.conviction;
}
