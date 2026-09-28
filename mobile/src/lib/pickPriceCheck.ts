/**
 * H4's price check for a board row, from the numbers the card already has:
 * the decision edge, the locked (decision) price and the current price at the
 * same book (heroAmericanForPick's "Now"). The band itself — and the
 * comment that it is a display heuristic only — lives in lib/priceCheck.ts.
 */
import { decisionEdge, decisionOdds } from '@/lib/decisionPrice';
import { heroAmericanForPick } from '@/lib/markets';
import { priceCheck, type PriceCheck } from '@/lib/priceCheck';
import type { EnrichedPick } from '@/types';

export function priceCheckForItem(item: Pick<EnrichedPick, 'pick' | 'latestOdds' | 'bookRows'>): PriceCheck {
  const hero = heroAmericanForPick(item.pick, item.latestOdds, item.bookRows);
  return priceCheck({
    edge: decisionEdge(item.pick),
    locked: decisionOdds(item.pick),
    current: hero?.kind === 'now' ? hero.price : null,
  });
}
