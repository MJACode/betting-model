/**
 * Turns the Performance tab's two bet lists into the Insights card's one
 * (lib/performanceInsights.ts): tracked picks, scored at the member's stakes,
 * and the bets they logged by hand.
 *
 * A tracked pick keeps its own label (pickTitleText), its decided price and
 * book, its sport, its model and its same-book CLV. A logged bet is free text,
 * so it brings only its price and the book typed in; it is never put in a
 * sport or market it did not name.
 */
import { decisionOdds } from './decisionPrice';
import { etDate } from './format';
import { sportDisplayName } from './liveSports';
import { bookName, marketClassForModel, pickTitleText, storedQuoteBook } from './markets';
import { isPropModel } from './modelMeta';
import type { InsightBet, InsightStatus } from './performanceInsights';
import type { TrackedBetRow } from './trackedPerformance';
import type { ManualBet } from '@/hooks/useManualBets';
import type { Pick } from '@/types';

/** The card's market groups. */
export function insightBetType(pick: Pick): string {
  if (pick.prop_market || isPropModel(pick.model_id)) return 'Player props';
  switch (marketClassForModel(pick.model_id)) {
    case 'game_ml':
      return 'Moneyline';
    case 'game_spread':
      return 'Spread';
    case 'game_total':
      return 'Total';
    case 'off_prop':
    case 'pitching_prop':
      return 'Player props';
    default:
      break;
  }
  // marketClassForModel puts these in 'other' for parlay pricing only.
  if (pick.model_id.startsWith('atp_') || pick.model_id.startsWith('wta_')) return 'Moneyline';
  if (pick.model_id === 'ufc_total_rounds') return 'Total';
  if (pick.model_id.startsWith('ufc_') && /moneyline|win/.test(pick.model_id)) return 'Moneyline';
  return 'Other';
}

function trackedStatus(row: TrackedBetRow): InsightStatus | null {
  switch (row.status) {
    case 'won':
    case 'lost':
    case 'push':
    case 'open':
      return row.status;
    default:
      // No action and a voided pick are not bets the recap counts.
      return null;
  }
}

export function insightFromTracked(row: TrackedBetRow): InsightBet | null {
  const status = trackedStatus(row);
  if (!status) return null;
  const p = row.pick;
  const book = storedQuoteBook(p);
  const clv = p.clv_method === 'standard_v2' && p.clv_pct != null ? Number(p.clv_pct) : null;
  return {
    key: `t:${p.pick_id}:${p.game_id}:${p.pick_side}`,
    date: p.game_date,
    stamp: p.created_at ?? '',
    title: pickTitleText(p),
    status,
    profit: status === 'won' || status === 'lost' ? row.profit : 0,
    risked: status === 'won' || status === 'lost' ? row.stake : 0,
    odds: decisionOdds(p),
    sport: p.sport ? sportDisplayName(p.sport) : null,
    betType: insightBetType(p),
    book: book ? bookName(book) : null,
    modelId: p.model_id,
    clvPct: clv != null && Number.isFinite(clv) ? clv : null,
    source: 'tracked',
  };
}

export function insightFromManual(b: ManualBet): InsightBet | null {
  const placed = new Date(b.placed_at);
  if (Number.isNaN(placed.getTime())) return null;
  const decided = b.result === 'won' || b.result === 'lost';
  const book = b.book?.trim();
  return {
    key: `m:${b.id}`,
    date: etDate(placed),
    stamp: b.placed_at,
    title: b.description,
    status: b.result,
    profit: decided ? Number(b.profit) || 0 : 0,
    risked: decided ? Number(b.stake) || 0 : 0,
    odds: b.odds_american,
    sport: null,
    betType: null,
    book: book ? book : null,
    modelId: null,
    clvPct: null,
    source: 'logged',
  };
}

export function buildInsightBets(tracked: TrackedBetRow[], manual: ManualBet[]): InsightBet[] {
  const out: InsightBet[] = [];
  for (const r of tracked) {
    const b = insightFromTracked(r);
    if (b) out.push(b);
  }
  for (const m of manual) {
    const b = insightFromManual(m);
    if (b) out.push(b);
  }
  return out;
}
