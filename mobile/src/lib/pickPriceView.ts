/**
 * The price a Signals card shows for one pick, and whether that price can be
 * bet: the price check, the price age, the model's own price, and the
 * member's books. Pure, so verify scripts can run it.
 *
 * PickCard and Bet all (lib/betAll.ts) both read this. Bet all offers a pick
 * only when its card would offer the bet, so the two must not work it out
 * twice. Moved out of PickCard.tsx unchanged on 2026-11-14.
 */
import {
  currentLineQuotes,
  heroAmericanForPick,
  numOrNull,
  priceAgeFor,
  storedQuoteBook,
  type HeroAmerican,
} from './markets';
import { myBooksView } from './myBooks';
import { priceCheckForItem } from './pickPriceCheck';
import { hasPricedLine } from './decisionPrice';
import { openForAction } from './discordPublish';
import type { EnrichedPick, LiveGameStateRow } from '@/types';

export function pickPriceView(
  item: EnrichedPick,
  liveState: LiveGameStateRow | null | undefined,
  myBooks: readonly string[],
  myBooksReady: boolean,
) {
  const { pick, game } = item;
  // H4 price check (display only, lib/priceCheck.ts): an implausible edge or a
  // lock far from the book's current price shows "Price check" and "—" for
  // edge and EV instead of headlining the board. After the start "Now" is the
  // in-play price, so only the edge rule applies then (Reviewer #847).
  const check = priceCheckForItem(item, liveState ?? null);
  const flagged = check.flagged;
  // The scorer's price-age rule (markets.PREGAME_PRICE_MAX_AGE_MIN): before
  // the start, a deciding price the book stopped updating is no price, so
  // the card shows "Now —" and offers no hand-off at it. Same start test
  // as the price check above.
  const priceAge = priceAgeFor(pick, game, liveState ?? null);
  const modelHero = heroAmericanForPick(pick, item.latestOdds, item.bookRows, priceAge);
  // At THEIR books. 'mine': the record book is not theirs but one of theirs
  // has the same bet, so the card shows that price with the edge and return
  // at it. 'none': none of theirs has it. Only on an open BET with a price;
  // a settled or non-BET row keeps the pick's own numbers.
  const myView =
    myBooksReady && pick.signal_type === 'BET' && hasPricedLine(pick) && openForAction(pick)
      ? myBooksView({
          quotes: currentLineQuotes(pick, item.bookRows, modelHero, priceAge),
          // Live or not, the record is kept at the book that decided it (§6).
          recordBook: storedQuoteBook(pick),
          myBooks,
          modelProbability: pick.model_probability,
        })
      : null;
  const myQuote = myView?.status === 'mine' ? myView.best : null;
  const notAtMyBooks = myView?.status === 'none';
  // The price the card shows. On 'mine' it is their best book at the scored
  // line, drawn as a plain decision price (no Now/Locked pill: there is no
  // lock at that book to compare against).
  const heroPrice: HeroAmerican | null = myQuote
    ? {
        kind: 'decision',
        price: myQuote.price,
        book: myQuote.bookmaker,
        line: numOrNull(pick.scored_line),
        link: myQuote.link,
        lockedPrice: myQuote.price,
        showLockedCaption: false,
      }
    : modelHero;
  return { check, flagged, priceAge, modelHero, myView, myQuote, notAtMyBooks, heroPrice };
}
