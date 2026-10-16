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
 * A game-market tag that belongs to the bet, not to the team name. It stays
 * on the hero when the matchup prefix is dropped: "Over 4.5 F5". A two-word
 * school ("Los Angeles") is not in this list. "Team Total" is handled apart
 * from this list: that bet is per team, and stripping the matchup drops the
 * club the total belongs to.
 */
const TOTAL_QUALIFIER = /(?:F5|alternate total|1st-period total)$/i;

/**
 * The bet the Signals card headlines.
 * "Sam Houston -7.5" → "Sam Houston −7.5".
 * "LAK vs EDM Under 6.0" → "Under 6.0" (the stored NHL game total; the
 * teams are the line above). "NYY vs BOS Over 4.5 F5" keeps F5.
 * A team total is quoted whole: picks has no such label (measured
 * 2026-10-16, 0 rows), and the odds row stores the club as
 * team_totals_home / team_totals_away with the feed description
 * ("Boston Bruins"), not as a tag between two clubs. "Boston Bruins Over
 * 3.5" and "BOS vs NYY Team Total Over 3.5" both keep every team word.
 * A prop keeps the stored label, player included.
 */
export function signalsBetHeadline(pickLabel: string | null | undefined): string {
  // NFL card labels append the stake ("· 1.00u"). The stake cell owns that
  // number; the hero is the bet.
  const label = (pickLabel ?? '').trim().replace(/\s·\s[\d.]+u$/, '');
  // Per-team market. Quoting the label whole is the only way the club is
  // not dropped: the words do not say which of the two sides the total is.
  if (/\bteam total\b/i.test(label)) return trueMinus(label);
  const split = label.match(/^(.*?)\s+(?:vs|@)\s+(.*)$/);
  if (!split) return trueMinus(label);
  const rest = split[2];
  const at = rest.search(/(?:^|\s)(?:Over|Under)\b/);
  if (at < 0) return trueMinus(label);
  const betAt = at === 0 ? 0 : at + 1;
  // "vs Over …" with no home team is not a game total. Leave the label.
  if (betAt === 0) return trueMinus(label);
  const before = rest.slice(0, betAt).trimEnd();
  const qualifier = before.match(TOTAL_QUALIFIER);
  const bet = qualifier ? rest.slice(betAt - qualifier[0].length - 1) : rest.slice(betAt);
  return trueMinus(bet);
}

/** "−110 MGM" — the decision price and the book that price came from. */
export function signalsPriceText(priceText: string, book: string): string {
  return `${trueMinus(priceText)} ${book}`.trim();
}

/**
 * "Bet MGM −110" when the button is the decision book at the decision price.
 * "Best now · FD −105" when the button's book or price is not that hero
 * (`bestNow`): the same Best/Bet split as the Today card, with "now" because
 * the 22pt number is still the lock. `lineText` is the book's current line
 * when this button is a bet at that line and it is not the line in the
 * headline. No price → "Open <book>", never a made-up number.
 */
export function signalsCtaLabel(
  book: string,
  priceText: string | null,
  lineText?: string | null,
  opts?: { bestNow?: boolean },
): string {
  if (!priceText) return `Open ${book}`;
  const line = lineText ? `${trueMinus(lineText)} ` : '';
  const quote = `${book} ${line}${trueMinus(priceText)}`;
  return opts?.bestNow ? `Best now · ${quote}` : `Bet ${quote}`;
}

/**
 * The same button, as VoiceOver should say it. Full book name, no middle
 * dot: "Best now, FanDuel, −105". `book` here is the spoken name.
 */
export function signalsCtaSpeech(
  book: string,
  priceText: string | null,
  lineText?: string | null,
  opts?: { bestNow?: boolean },
): string {
  if (!priceText) return `Open ${book}`;
  const parts = [opts?.bestNow ? 'Best now' : 'Bet', book];
  if (lineText) parts.push(trueMinus(lineText));
  parts.push(trueMinus(priceText));
  return parts.join(', ');
}

/** "Picked at −110 MGM" — the lock, on screen only when the button is not it. */
export function signalsPickedAtLine(priceText: string, book: string): string {
  return `Picked at ${trueMinus(priceText)} ${book}`;
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
 * The small line under the hero when the book's current line or price is
 * not the number the pick was written at. Null when nothing to show has
 * been passed, so the screen and VoiceOver stay quiet together.
 *
 * `line` is already the pick's side ("-8.5", "+3.5", "9") and is null when
 * the line has not moved. `price` is the current American. `priceDiffers`
 * is that price against the decision price. A line move prints the line and
 * the price; a price move with the same line prints the price. `book` is
 * whatever this surface uses (the short label on screen, the full name
 * when spoken) — the numbers are the same call either way.
 */
export function signalsNowLine(input: {
  line: string | null;
  price: string | null;
  priceDiffers: boolean;
  book: string;
}): string | null {
  if (input.price == null) return null;
  if (!input.line && !input.priceDiffers) return null;
  const parts = ['Now'];
  if (input.line) parts.push(trueMinus(input.line));
  parts.push(trueMinus(input.price));
  if (input.book) parts.push(input.book);
  return parts.join(' ');
}

/**
 * VoiceOver for the Signals hero. The 22pt number is the decision price, so
 * that is what is spoken, with the full book name — the same `signalsPriceText`
 * the screen uses, so the two cannot format the price differently. `now` is
 * the Now line the screen is showing (built by `signalsNowLine`); null when
 * the screen has none. The lock is this one price. The grey "Picked at"
 * line is visual only, so it is not spoken again. Stale and untracked
 * cards stay on `heroPriceSpeech`.
 */
export function signalsHeroSpeech(input: {
  decisionPrice: string;
  book: string;
  now?: string | null;
}): string {
  const locked = signalsPriceText(input.decisionPrice, input.book);
  if (!input.now) return locked;
  return `${locked}. ${input.now}`;
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
 * The Stake cell. Both figures are `stakeFor`'s: units to bet (`risk`) and
 * units to win (`win`), already formatted ("1.5u", "0.4u"). A capped heavy
 * favorite reads "Bet 1.5u · Win 0.4u", so the risk is not hidden behind the
 * smaller win. Never the "1.1u → 1u" arrow, never dollars.
 */
export function signalsStakeLine(riskUnits: string, winUnits: string): string {
  return `Bet ${riskUnits} · Win ${winUnits}`;
}

/** "1u" → "1 unit". "0.4u" and "10u" stay plural. */
function unitsSpoken(shown: string): string {
  const spoken = shown.replace(/(\d)u\b/g, '$1 units');
  return spoken === '1 units' ? '1 unit' : spoken;
}

/** VoiceOver for the Stake cell. Both amounts, in the same order as the line. */
export function signalsStakeSpeech(riskUnits: string, winUnits: string): string {
  return `Bet ${unitsSpoken(riskUnits)}, win ${unitsSpoken(winUnits)}`;
}
