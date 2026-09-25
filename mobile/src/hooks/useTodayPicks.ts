import { useCallback, useEffect, useState } from 'react';
import {
  fetchPicksForDate,
  fetchUpcomingUfcPicks,
  fetchUpcomingNflPicks,
  fetchUpcomingNcaafPicks,
  fetchUpcomingNhlPicks,
} from '@/lib/queries';
import { addDays, isGameOver, todayET } from '@/lib/format';
import { attachDiscordPublish, voidHiddenFromBoard } from '@/lib/discordPublish';
import { isModelPaused, isModelRetired } from '@/lib/thresholds';
import { errorText } from '@/lib/errors';
import type { EnrichedPick } from '@/types';

/** Mirrors config.UFC_SCORE_AHEAD_DAYS — how far ahead UFC fights are scored. */
const UFC_AHEAD_DAYS = 7;
/**
 * How far ahead the NFL board looks. Must cover the WIDEST window any NFL
 * producer can write a pick in, because Discord and push have NO date horizon
 * at all (CLAUDE.md §1b) — whatever this number is short by is a pick a member
 * gets in the channel and cannot find in the app.
 *
 * 11, not 8 (2026-09-09). 8 covered the opener's T-7 lock window plus a day of
 * ET/UTC margin, which was the widest producer when it was written. It is not
 * any more: `scheduler.NFL_POLL_HORIZON_DAYS` is 10 and
 * `config.NFL_PROP_WINDOW_HOURS` is 240h — also 10 — so the prop card prices,
 * and the scorer can lock, a game ten days out. Measured against production
 * the day this changed, nothing was actually beyond 8 days, so this is closing
 * the gap before it costs a pick rather than after: the last time these two
 * windows were allowed to differ, two Week 1 wind picks 9 days out reached the
 * app and nothing else, and it took a month to notice.
 *
 * 11 = the 10-day poll/prop horizon plus one day of ET/UTC-boundary margin.
 * Raise this whenever a server-side NFL horizon is raised; never lower it below
 * the largest of them.
 */
const NFL_AHEAD_DAYS = 11;
/**
 * Mirrors config.NCAAF_SCORE_AHEAD_DAYS. NCAAF is scored as far ahead as
 * DraftKings has a line (Matt, 2026-09-07: "whenever lines are released"),
 * and a pick locks the moment it fires, so the card has to reach every game
 * the scorer can write a BET for — marquee games are listed months out. The
 * server admits only DK-priced games; measured 2026-09-07 the season window is
 * 107 games (924 `games` rows, 2,309 all-books rows), so every read is paged.
 */
const NCAAF_AHEAD_DAYS = 150;
/**
 * Mirrors config.GAME_SCORE_AHEAD_DAYS for NHL. The scorer prices NHL (with
 * MLB, NBA and WNBA) this far ahead of `game_date`; a DraftKings price is
 * the real gate and this number is the outer bound. 7, not the NFL card's
 * 11: NHL has no poll or prop horizon past this constant, and the board has
 * to reach every date the scorer can write. A game exactly 7 days out is
 * inside the window (`lte`), which is the 2026-09-29 opener read on
 * 2026-09-22.
 */
const NHL_AHEAD_DAYS = 7;

export function useTodayPicks(date?: string) {
  const target = date ?? todayET();
  const [data, setData] = useState<EnrichedPick[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  // Reads that failed WITHOUT taking the board down: the odds views behind the
  // line pills, or one sport's look-ahead card. What failed, deduped, plus the
  // FIRST reason (the 2026-09-04 failure took three reads down with the same
  // statement timeout; three copies of one Postgres sentence is not a
  // message), so the screen can say "Couldn't load today's lines" rather than
  // show an empty pill (Matt, 2026-09-05: "fix it").
  const [partial, setPartial] = useState<{ whats: string[]; reason: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const whats: string[] = [];
    let reason: string | null = null;
    const note = (what: string) => (e: unknown) => {
      if (!whats.includes(what)) whats.push(what);
      if (reason == null) reason = errorText(e);
      console.warn(`[useTodayPicks] ${what} failed`, e);
    };
    const swallow = (what: string) => (e: unknown) => {
      note(what)(e);
      return [] as EnrichedPick[];
    };
    try {
      // Today's picks (all sports) plus each look-ahead card. UFC, NFL and
      // NCAAF have had one; NHL joined the scorer's 7-day game window
      // (config.GAME_SCORE_AHEAD_DAYS) and was still same-day here, so a
      // slate dated inside that window never reached the chip or the board.
      // The look-ahead fetches are enrichment — don't fail the whole feed on
      // them, but record each failure in `partial`.
      const [rows, ufcRows, nflRows, ncaafRows, nhlRows] = await Promise.all([
        fetchPicksForDate(target, (what, e) => note(what)(e)),
        fetchUpcomingUfcPicks(target, addDays(target, UFC_AHEAD_DAYS)).catch(swallow('the upcoming UFC card')),
        fetchUpcomingNflPicks(target, addDays(target, NFL_AHEAD_DAYS)).catch(swallow('this week’s NFL card')),
        fetchUpcomingNcaafPicks(target, addDays(target, NCAAF_AHEAD_DAYS)).catch(swallow('the upcoming NCAAF card')),
        fetchUpcomingNhlPicks(target, addDays(target, NHL_AHEAD_DAYS)).catch(swallow('the upcoming NHL card')),
      ]);
      // Drop games that have already finished — once a game ends it shouldn't
      // linger on the board for the rest of the day. A retired or paused
      // model's picks are dropped here too (Matt, 2026-09-02 / 2026-09-19:
      // catalog and today's board show only active models). This hook feeds
      // the Today/Signals board, the sport-toggle counts, the Models cards'
      // live lists, the filter Market chips and the Stats odds pills, so one
      // filter at the source keeps all of them in agreement — before this, the
      // board drew a retired BET as a green, stakeable card while the header
      // count excluded it. The rows stay in the DB as the record of what was
      // published (§1c).
      //
      // A VOID the channel does not still show is dropped here, not only in
      // passesActionFilter (2026-09-09). Five surfaces read this hook without
      // that filter — the Today segment, both model screens, the Stats odds
      // pill and the betslip hand-off. A VOID Discord already posted stays:
      // the message is the bet (Matt, 2026-09-23). voidHiddenFromBoard is
      // that split. passesActionFilter is the Signals / green-bet half.
      const merged = [...rows, ...ufcRows, ...nflRows, ...ncaafRows, ...nhlRows];
      const stamped = await attachDiscordPublish(merged.map((d) => d.pick));
      const byId = new Map(stamped.map((p) => [p.pick_id, p]));
      const all = merged.map((d) => ({
        ...d,
        pick: byId.get(d.pick.pick_id) ?? d.pick,
      })).filter(
        (d) => !isGameOver(d.game, d.pick.sport)
          && !isModelRetired(d.pick.model_id)
          && !isModelPaused(d.pick.model_id)
          && !voidHiddenFromBoard(d.pick),
      );
      setData(all);
      setPartial(whats.length > 0 && reason != null ? { whats, reason } : null);
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
