import { useCallback, useEffect, useRef, useState } from 'react';
import { AppState } from 'react-native';
import {
  fetchPicksForDate,
  fetchUpcomingUfcPicks,
  fetchUpcomingNflPicks,
  fetchUpcomingNcaafPicks,
  fetchUpcomingNcaabPicks,
  fetchUpcomingNcaabwPicks,
  fetchUpcomingNhlPicks,
  fetchUpcomingTennisPicks,
} from '@/lib/queries';
import { addDays, gameStatus, isGameOver, todayET } from '@/lib/format';
import { attachDiscordPublish, voidHiddenFromBoard } from '@/lib/discordPublish';
import { isModelRetired, isPausedForDisplay } from '@/lib/thresholds';
import { errorText, isAbortError } from '@/lib/errors';
import {
  loadTodayBoard,
  moveTodayBoardDay,
  setTodayBoardReader,
  subscribeTodayBoardDay,
  todayBoardDay,
  todayBoardIsStale,
  todayPicksDateKey,
  subscribeTodayBoard,
  todayBoardSnapshot,
  type TodayBoardRead,
  type TodayBoardSnapshot,
} from '@/lib/todayPicksFlight';
import type { EnrichedPick } from '@/types';

/**
 * How far ahead the UFC board looks. Mirrors the UFC opening-price card's
 * reach (scripts/ufc_open_moneyline_card.HORIZON_DAYS, 120 days), plus one
 * day of ET/UTC margin, the same rule NFL_AHEAD_DAYS follows below: that model
 * bets a fight a week or more out (often two to four weeks), and Discord and
 * push have no date horizon, so a shorter window is a bet a member gets in the
 * channel and cannot find in the app (UX review, 2026-11-13). Raise this
 * whenever the card's reach is raised.
 */
const UFC_AHEAD_DAYS = 121;
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
/**
 * How far ahead the NCAAB board looks. The NCAAB totals model decides minutes
 * after DraftKings first posts a game's total, usually the day before the game,
 * so a same-day read would hide its picks until game day. 7 is config.GAME_SCORE_AHEAD_DAYS, the outer bound the
 * scorer uses for the other basketball sports. NCAAB is not in
 * GAME_SCORE_AHEAD_SPORTS, so this is a bound, not a mirror: raise it if an
 * NCAAB model ever writes further out. Only the picks' own games are read
 * (fetchUpcomingNcaabPicks), so a longer window costs little.
 */
const NCAAB_AHEAD_DAYS = 7;
/**
 * How far ahead the NCAABW (women's college basketball) board looks. Its
 * totals model decides at DraftKings' first posted total, which came 1 to 6
 * Eastern dates before the game's date in 155 of 1,772 priced games and never
 * more than 6, so a same-day read would hide those picks until game day. 7 is
 * the card's own slate window (scripts/ncaabw_total_card.py SLATE_DAYS):
 * raise this whenever that is raised, never lower it below it. Only the
 * picks' own games are read (fetchUpcomingNcaabwPicks), so the window costs
 * little.
 */
const NCAABW_AHEAD_DAYS = 7;
/**
 * How far ahead the tennis boards (ATP, WTA) look. The tennis card decides a
 * match at most 35 minutes before its listed start (scripts/
 * tennis_moneyline_card.py DECISION_LEAD) and files the pick under that
 * start's Eastern date, so a match listed between 00:00 and 00:35 ET is
 * posted the evening before under tomorrow's date. One day reaches it; the
 * card writes nothing further ahead. Raise this if DECISION_LEAD ever passes
 * a day.
 */
const TENNIS_AHEAD_DAYS = 1;

/** How often the Picks tab reloads today's boards while it is open. The app's
 *  own help text says lines refresh every 10 minutes at the busiest; a reload
 *  more often than the data changes buys nothing (Matt, 2026-11-12). */
export const TODAY_POLL_MS = 10 * 60_000;
/** Returning to the app or the tab reloads only when the last load is older. */
export const TODAY_RESUME_MIN_AGE_MS = 60_000;

/*
 * Who reloads today's board, in one place. PicksHomeScreen owns every reload:
 * every TODAY_POLL_MS while its tab is focused and the app is in front, and
 * once on coming back to the app or the tab when its last load is older than
 * TODAY_RESUME_MIN_AGE_MS, plus pull-to-refresh. Each of those calls
 * `refresh` below. This hook does not reload on its own when the app comes
 * back; it only moves an undated board onto the new Eastern date after
 * midnight, and the first read of that new day is a first read, not a reload.
 *
 * Underneath, every mount of one date shares a single in-flight read
 * (lib/todayPicksFlight.ts): the betslip bar, Picks, Player Stats and the
 * model screens wait on the same request instead of each starting the seven
 * sports again. A mount reuses a finished read younger than
 * TODAY_PICKS_STALE_MS; Picks' timer and pull always read.
 *
 * Overlapping reloads (a pull during a poll) are ordered by the flight: one
 * read per date at a time, and a refresh that arrives mid-read runs one
 * follow-up, so the newest read is the one every mount settles on. The error
 * banner is cleared only by a read that succeeds, so a failing background
 * reload does not unmount it and mount it again (UX review, 2026-11-12).
 */

/**
 * The seven-sport read, once. The flight cache (lib/todayPicksFlight.ts) is
 * what makes a second mount wait instead of starting it again. The split
 * below is unchanged: `data` is what every consumer except the All board
 * sees, and `pausedData` is the All board's paused rows.
 */
export async function readTodayBoard(target: string): Promise<TodayBoardRead<EnrichedPick>> {
  let data: EnrichedPick[] = [];
  // PAUSED models' rows, kept apart from `data` (Matt, 2026-09-26: "NFL is only
  // showing tackle bets. It should be all bets"). Eleven of twelve NFL prop
  // models are paused, so hiding them left the NFL board a tackles board. Only
  // the Picks screen's All segment reads this, and labels every card PAUSED.
  // A paused pick Discord already POSTED stays in `data` (isPausedForDisplay):
  // it is the bet of record, so it draws as one and the betslip can hold it;
  // every other consumer of this hook (Signals, the sport badges, Models, the
  // Stats pills, the betslip) still sees `data` alone, so the 2026-09-19 rule
  // holds everywhere else. passesActionFilter already refuses a paused model,
  // so none of these rows can be counted or drawn as a bet.
  let pausedData: EnrichedPick[] = [];
  let error: string | null = null;
  // At least one load has SUCCEEDED. Until then a count is unknown ("—"), not
  // zero: `loading` alone can't say it, because every refresh sets it too
  // (lib/loadState countsKnown, Designer #845).
  let loaded = false;
  // Reads that failed WITHOUT taking the board down: the odds views behind the
  // line pills, or one sport's look-ahead card. What failed, deduped, plus the
  // FIRST reason (the 2026-09-04 failure took three reads down with the same
  // statement timeout; three copies of one Postgres sentence is not a
  // message), so the screen can say "Couldn't load today's lines" rather than
  // show an empty pill (Matt, 2026-09-05: "fix it").
  let partial: { whats: string[]; reason: string } | null = null;
  const setData = (rows: EnrichedPick[]) => {
    data = rows;
  };
  const setPausedData = (rows: EnrichedPick[]) => {
    pausedData = rows;
  };
  // The shared flight publishes loading. This read only fills the rows.
  const setLoading = (_next: boolean) => {};
  const setError = (next: string | null) => {
    error = next;
  };
  const setLoaded = (next: boolean) => {
    loaded = next;
  };
  const setPartial = (next: { whats: string[]; reason: string } | null) => {
    partial = next;
  };

  // No setError(null) here: `error` starts null, and the shown banner is the
  // flight's, which clears it only when a read succeeds.
  setLoading(true);
  const whats: string[] = [];
  let reason: string | null = null;
  const note = (what: string) => (e: unknown) => {
    // A cancel is not a missing section: no partial banner for it.
    if (isAbortError(e)) return;
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
    // NCAAB joined with its totals model, which usually decides the day before.
    // NCAABW joined with its own (2026-11-10), which decides up to six days before.
    // Tennis joined 2026-11-14: a match listed just after midnight is posted
    // the evening before.
    // The look-ahead fetches are enrichment — don't fail the whole feed on
    // them, but record each failure in `partial`.
    const [rows, ufcRows, nflRows, ncaafRows, ncaabRows, ncaabwRows, nhlRows, tennisRows] = await Promise.all([
      fetchPicksForDate(target, (what, e) => note(what)(e)),
      fetchUpcomingUfcPicks(target, addDays(target, UFC_AHEAD_DAYS)).catch(swallow('the upcoming UFC card')),
      fetchUpcomingNflPicks(target, addDays(target, NFL_AHEAD_DAYS)).catch(swallow('this week’s NFL card')),
      fetchUpcomingNcaafPicks(target, addDays(target, NCAAF_AHEAD_DAYS)).catch(swallow('the upcoming NCAAF card')),
      fetchUpcomingNcaabPicks(target, addDays(target, NCAAB_AHEAD_DAYS), (what, e) =>
        note(what)(e),
      ).catch(swallow('the upcoming NCAAB card')),
      fetchUpcomingNcaabwPicks(target, addDays(target, NCAABW_AHEAD_DAYS), (what, e) =>
        note(what)(e),
      ).catch(swallow('the upcoming NCAABW card')),
      fetchUpcomingNhlPicks(target, addDays(target, NHL_AHEAD_DAYS)).catch(swallow('the upcoming NHL card')),
      fetchUpcomingTennisPicks(target, addDays(target, TENNIS_AHEAD_DAYS)).catch(swallow('the upcoming tennis matches')),
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
    const merged = [...rows, ...ufcRows, ...nflRows, ...ncaafRows, ...ncaabRows, ...ncaabwRows, ...nhlRows, ...tennisRows];
    const stamped = await attachDiscordPublish(merged.map((d) => d.pick));
    const byId = new Map(stamped.map((p) => [p.pick_id, p]));
    const all = merged.map((d) => ({
      ...d,
      pick: byId.get(d.pick.pick_id) ?? d.pick,
    })).filter(
      (d) => !isGameOver(d.game, d.pick.sport)
        // A tennis no-bet row never gets a final score (only a settled BET
        // writes one), so it leaves once its match is past the badge window
        // instead of lingering, statusless, until midnight. BETs stay until
        // they settle (UX review, 2026-11-14).
        && !((d.pick.sport === 'ATP' || d.pick.sport === 'WTA') && d.pick.signal_type !== 'BET'
             && gameStatus(d.game).kind === 'ended')
        && !isModelRetired(d.pick.model_id)
        && !voidHiddenFromBoard(d.pick),
    );
    setData(all.filter((d) => !isPausedForDisplay(d.pick)));
    setPausedData(all.filter((d) => isPausedForDisplay(d.pick)));
    setPartial(whats.length > 0 && reason != null ? { whats, reason } : null);
    setLoaded(true);
  } catch (e: unknown) {
    if (!isAbortError(e)) setError(errorText(e));
  } finally {
    setLoading(false);
  }
  return { data, pausedData, loaded, error, partial };
}

setTodayBoardReader(readTodayBoard);

export function useTodayPicks(date?: string) {
  // The default day is state so a return to the app after midnight ET
  // switches the board. todayET() read once at mount would keep yesterday until the
  // component happened to re-render. An explicit `date` argument is left
  // alone: the caller asked for that day.
  //
  // Every undated mount also follows one shared day (lib/todayPicksFlight).
  // When one of them moves onto a new Eastern day, by mounting, refreshing or
  // coming back to the app on it, the rest move too. Without that the betslip
  // bar, which never pulls or remounts, kept yesterday's board after Picks had
  // moved on (design review, 2026-11-13). The day only moves forward.
  const [liveDay, setLiveDay] = useState(() => {
    const today = todayET();
    const shared = todayBoardDay();
    return shared != null && shared > today ? shared : today;
  });
  const target = date ?? liveDay;
  const moveDay = useCallback((day: string) => {
    const next = moveTodayBoardDay(day);
    setLiveDay((prev) => (prev >= next ? prev : next));
  }, []);
  const [board, setBoard] = useState<TodayBoardSnapshot<EnrichedPick>>(() => todayBoardSnapshot<EnrichedPick>(target));
  // The rows are shared. The spinner is not. A pull on Picks must not turn the
  // betslip's resolving state back on, or replace a model screen's known empty
  // list with a spinner, just because this hook is mounted there too.
  const [loading, setLoading] = useState(() => !todayBoardSnapshot<EnrichedPick>(target).loaded);
  // A newer load must not be cleared by an older one's finally.
  const loadGen = useRef(0);

  useEffect(() => {
    const day = todayPicksDateKey({
      explicit: date,
      held: target,
      today: todayET(),
      heldIsStale: todayBoardIsStale(target),
      refresh: false,
    });
    // The cached read for the day this screen is holding has aged out, and
    // the Eastern date has moved. Switch before subscribing, so the effect
    // runs again on today instead of refreshing yesterday.
    if (day !== target) {
      moveDay(day);
      return;
    }
    // An undated mount on a newer day than the others brings them along.
    if (date == null) moveTodayBoardDay(target);
    let alive = true;
    const token = ++loadGen.current;
    const current = todayBoardSnapshot<EnrichedPick>(target);
    setBoard(current);
    setLoading(!current.loaded);
    const stop = subscribeTodayBoard<EnrichedPick>(target, setBoard);
    void loadTodayBoard(target, false).finally(() => {
      if (alive && loadGen.current === token) setLoading(false);
    });
    return () => {
      alive = false;
      stop();
    };
  }, [target, date, moveDay]);

  // Follow the shared day. A mount that missed a move between its render and
  // this effect catches up here.
  useEffect(() => {
    if (date != null) return undefined;
    const follow = (day: string) => setLiveDay((prev) => (prev >= day ? prev : day));
    const shared = todayBoardDay();
    if (shared != null) follow(shared);
    return subscribeTodayBoardDay(follow);
  }, [date]);

  // Coming back to the app after midnight ET: move an undated board onto the
  // new Eastern date. This does NOT reload. Reloading on return is
  // PicksHomeScreen's rule (TODAY_RESUME_MIN_AGE_MS), and a second resume
  // reload here would start another read on top of it. A new date re-runs the
  // effect above, whose read joins Picks' if one is in flight. Same AppState
  // hook as useLinesBoard. A focus hook is off limits here: the betslip bar is
  // mounted outside the navigator.
  useEffect(() => {
    if (date != null) return undefined;
    const sub = AppState.addEventListener('change', (state) => {
      if (state !== 'active') return;
      moveDay(todayET());
    });
    return () => sub.remove();
  }, [date, moveDay]);

  // Pull-to-refresh, Picks' 10-minute timer and its resume reload all call
  // this. It skips the finished read. A refresh during an in-flight read
  // waits for one follow-up.
  // Only this caller spins: the shared read updates every other mount's rows
  // without flipping their loading flag.
  const refresh = useCallback(() => {
    const token = ++loadGen.current;
    setLoading(true);
    const day = todayPicksDateKey({
      explicit: date,
      held: target,
      today: todayET(),
      heldIsStale: todayBoardIsStale(target),
      refresh: true,
    });
    // Start the read BEFORE moving the shared day, so every board that follows
    // onto the new day joins this read instead of starting its own.
    const flight = loadTodayBoard(day, true).finally(() => {
      if (loadGen.current === token) setLoading(false);
    });
    if (date == null) moveDay(day);
    return flight;
  }, [date, target, moveDay]);

  return {
    data: board.data,
    pausedData: board.pausedData,
    loading,
    loaded: board.loaded,
    error: board.error,
    partial: board.partial,
    refresh,
    date: target,
  };
}
