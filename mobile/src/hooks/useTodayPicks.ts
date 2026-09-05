import { useCallback, useEffect, useState } from 'react';
import {
  fetchPicksForDate,
  fetchUpcomingUfcPicks,
  fetchUpcomingGolfPicks,
  fetchUpcomingNflPicks,
  fetchUpcomingNcaafPicks,
} from '@/lib/queries';
import { addDays, isGameOver, todayET } from '@/lib/format';
import { isModelRetired } from '@/lib/thresholds';
import { errorText } from '@/lib/errors';
import type { EnrichedPick } from '@/types';

/** Mirrors config.UFC_SCORE_AHEAD_DAYS — how far ahead UFC fights are scored. */
const UFC_AHEAD_DAYS = 7;
/** Mirrors config.GOLF_SCORE_AHEAD_DAYS — how far ahead tournaments are scored. */
const GOLF_AHEAD_DAYS = 7;
/**
 * How far ahead the NFL board looks. Must cover the OPENER's lock window, not
 * just the wind card's: the opener card takes bets from T-7 (daily_opener_card
 * LEAD_HI_DAYS) and never re-prices them, so a 5-day window left a pick locked
 * at T-7/T-6 invisible for up to two days — precisely when its stale number is
 * still gettable. 8 = the full T-7 window plus a day of ET/UTC-boundary margin.
 * (The wind card only reaches 4 days out, so it was always covered.)
 */
const NFL_AHEAD_DAYS = 8;
/**
 * Mirrors config.NCAAF_SCORE_AHEAD_DAYS. College football plays one slate a
 * week, so without this the NCAAF board is empty six days out of seven — and
 * the cross-book opener rule, which fires days ahead on purpose, would never
 * be visible at all.
 */
const NCAAF_AHEAD_DAYS = 7;

export function useTodayPicks(date?: string) {
  const target = date ?? todayET();
  const [data, setData] = useState<EnrichedPick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Reads that failed WITHOUT taking the board down: the odds views behind the
  // line pills, or one sport's look-ahead card. Each is "what — why", deduped
  // by what, so the screen can say "Couldn't load today's lines" rather than
  // show an empty pill (Matt, 2026-09-05: "fix it").
  const [partial, setPartial] = useState<string[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const failed = new Map<string, string>();
    const note = (what: string) => (e: unknown) => {
      if (!failed.has(what)) failed.set(what, `${what} — ${errorText(e)}`);
      console.warn(`[useTodayPicks] ${what} failed`, e);
    };
    const swallow = (what: string) => (e: unknown) => {
      note(what)(e);
      return [] as EnrichedPick[];
    };
    try {
      // Today's picks (all sports) + the upcoming UFC card. UFC events are
      // weekly, so the UFC tab shows the next card's picks ahead of fight day.
      // The look-ahead fetches are enrichment — don't fail the whole feed on
      // them, but record each failure in `partial`.
      const [rows, ufcRows, golfRows, nflRows, ncaafRows] = await Promise.all([
        fetchPicksForDate(target, (what, e) => note(what)(e)),
        fetchUpcomingUfcPicks(target, addDays(target, UFC_AHEAD_DAYS)).catch(swallow('UFC picks')),
        fetchUpcomingGolfPicks(target, addDays(target, GOLF_AHEAD_DAYS)).catch(swallow('golf picks')),
        fetchUpcomingNflPicks(target, addDays(target, NFL_AHEAD_DAYS)).catch(swallow('NFL picks')),
        fetchUpcomingNcaafPicks(target, addDays(target, NCAAF_AHEAD_DAYS)).catch(swallow('NCAAF picks')),
      ]);
      // Drop games that have already finished — once a game ends it shouldn't
      // linger on the board for the rest of the day. A retired model's picks
      // are dropped here too (Matt, 2026-09-02: "absent from display and not
      // counted toward anything"). This hook feeds the Today/Signals/Movement
      // board, the sport-toggle counts, the Models cards' live lists and the
      // Stats odds pills, so one filter at the source keeps all of them in
      // agreement — before this, the board drew a retired BET as a green,
      // stakeable card while the header count excluded it. The rows stay in
      // the DB as the record of what was published (§1c).
      const all = [...rows, ...ufcRows, ...golfRows, ...nflRows, ...ncaafRows].filter(
        (d) => !isGameOver(d.game, d.pick.sport) && !isModelRetired(d.pick.model_id),
      );
      setData(all);
      setPartial(Array.from(failed.values()));
    } catch (e: unknown) {
      setError(errorText(e));
    } finally {
      setLoading(false);
    }
  }, [target]);

  useEffect(() => {
    void load();
  }, [load]);

  return { data, loading, error, partial, refresh: load, date: target };
}
