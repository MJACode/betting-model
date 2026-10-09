/**
 * The words the pick card shows and speaks about its hero price and its price
 * check (second review of the stale-price rule, 2026-10-09).
 *
 * Pure (no React Native import), so the pytest pin runs it under plain node.
 *
 * Why it exists: a card whose deciding price DraftKings stopped updating
 * (markets.heroAmericanForPick, `stale`) said "Price check" and spoke "this
 * price looks off", when the price was not off, only old; its "Now —" never
 * said why there was no price (the Live card uses the same "—" for "not
 * loaded yet"); and VoiceOver heard "Now unavailable DK" with no price at
 * all, while the eye saw "Locked −112". The wording now follows the check's
 * reasons, names the book in full when spoken, and reads the lock out.
 */
import { formatAmerican, formatStampET } from './format';
import { bookLabel, bookName, PREGAME_PRICE_MAX_AGE_MIN, type HeroAmerican } from './markets';
import type { PriceCheck } from './priceCheck';

/** Only the old-price rule tripped: the number is old, not implausible. */
export function onlyStalePrice(check: Pick<PriceCheck, 'reasons'>): boolean {
  return check.reasons.length > 0 && check.reasons.every((r) => r === 'stale');
}

/** The chip in the card's title row when the check trips. */
export function priceCheckChipText(check: Pick<PriceCheck, 'reasons'>): string {
  return onlyStalePrice(check) ? 'Old price' : 'Price check';
}

/**
 * Spoken in the card label in place of "Edge …" when the check trips. An
 * implausible edge or a moved price keeps "looks off"; an old price says
 * which book has not updated it, and since when.
 */
export function priceCheckSpeech(
  check: Pick<PriceCheck, 'reasons'>,
  hero: HeroAmerican | null | undefined,
): string {
  if (onlyStalePrice(check) && hero?.stale) {
    return `${notUpdated(hero)}, so edge and EV are hidden`;
  }
  return 'Price check: this price looks off, so edge and EV are hidden';
}

/** "DraftKings has not updated this price since Sat, 9/5 · 7:59 PM ET". */
function notUpdated(hero: HeroAmerican): string {
  const when = hero.staleSince
    ? `since ${formatStampET(hero.staleSince)}`
    : `in over ${Math.round(PREGAME_PRICE_MAX_AGE_MIN / 60)} hours`;
  return `${bookName(hero.book)} has not updated this price ${when}`;
}

/**
 * The caption under the hero price. A stale price adds when the book last
 * priced it: "Locked −112 · DK last priced Sat, 9/5 · 7:59 PM ET" (the time
 * alone on the same day). It wraps; the block has no line limit.
 */
export function lockedCaptionText(hero: HeroAmerican): string {
  const locked = `Locked ${formatAmerican(hero.lockedPrice)}`;
  if (!hero.stale || !hero.staleSince) return locked;
  return `${locked} · ${bookLabel(hero.book)} last priced ${formatStampET(hero.staleSince)}`;
}

/**
 * Pick Detail's header line under the decided price, when the deciding book
 * has stopped updating it: why the screen offers no sportsbook and no
 * betslip. Null otherwise.
 */
export function stalePriceNote(hero: HeroAmerican | null | undefined): string | null {
  if (!hero?.stale) return null;
  return `${notUpdated(hero)}, so no sportsbook or betslip is offered at it.`;
}

/**
 * The hero price as the card label speaks it, with the full book name:
 * "Now −115 DraftKings. Locked −110", "−110 DraftKings", and on a stale card
 * "No current DraftKings price. Locked −112". A Live price that has not
 * loaded keeps "unavailable": that is not "no current price".
 */
export function heroPriceSpeech(hero: HeroAmerican, priceTag: string): string {
  const parts: string[] = [];
  if (hero.stale) {
    parts.push(`No current ${bookName(hero.book)} price`);
  } else {
    const tag = hero.kind === 'now' ? priceTag : hero.kind === 'locked' ? 'Locked' : '';
    const price = hero.price == null ? 'unavailable' : formatAmerican(hero.price);
    parts.push(`${tag} ${price} ${bookName(hero.book)}`.trim());
  }
  if (hero.showLockedCaption) parts.push(`Locked ${formatAmerican(hero.lockedPrice)}`);
  return parts.join('. ');
}
