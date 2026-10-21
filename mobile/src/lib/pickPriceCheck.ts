/**
 * H4's price check for a board row, from the numbers the card already has:
 * the decision edge, the locked (decision) price and the current price at the
 * same book (heroAmericanForPick's "Now"). The band itself — and the
 * comment that it is a display heuristic only — lives in lib/priceCheck.ts.
 *
 * Once the game has started (or the pick is an in-play signal) "Now" is the
 * in-play price, so the moved-price rule is skipped (Reviewer #847): pass the
 * card's live snapshot so the start test matches the card's.
 *
 * Before the start, a deciding price older than PREGAME_PRICE_MAX_AGE_MIN is
 * flagged ('stale'): the scorer treats it as no price (2026-10-09), so the
 * card shows "Price check" and "—" for edge and EV rather than a September
 * price as if it were current.
 */
import { decisionEdge, decisionOdds } from '@/lib/decisionPrice';
import { gameHasStarted } from '@/lib/format';
import { heroAmericanForPick, priceAgeFor } from '@/lib/markets';
import { priceCheck, type PriceCheck } from '@/lib/priceCheck';
import type { EnrichedPick, LiveGameStateRow } from '@/types';

export function priceCheckForItem(
  item: Pick<EnrichedPick, 'pick' | 'latestOdds' | 'bookRows'> & { game?: EnrichedPick['game'] },
  liveState?: Pick<LiveGameStateRow, 'abstract_game_state' | 'home_score' | 'away_score'> | null,
  now?: number,
): PriceCheck {
  const gameStarted = gameHasStarted(item.game ?? null, liveState ?? null, item.pick.game_time);
  const priceAge = priceAgeFor(item.pick, item.game ?? null, liveState ?? null, now);
  const hero = heroAmericanForPick(item.pick, item.latestOdds, item.bookRows, priceAge);
  return priceCheck({
    edge: decisionEdge(item.pick),
    locked: decisionOdds(item.pick),
    current: hero?.kind === 'now' ? hero.price : null,
    started: item.pick.is_live === true || gameStarted,
    stale: hero?.stale === true,
  });
}
