/**
 * Per-day, per-model results for the "Yesterday's results" recap.
 *
 * Pure (no React / Supabase) so it's unit-testable. The win-loss set is the
 * posted settled BETs (passesRecordFilter, Discord still has the lock). The
 * money is Discord's posted stake: `postedPickUnits`, the app twin of
 * `published_pick_unit_profit` / `published_pick_unit_risked`. ROI is units
 * won or lost divided by units risked. The Models tab stays on the flat
 * $100 book.
 */
import { formatPctSigned, formatSigned } from '@/lib/format';
import {
  isContaminatedPregamePick,
  isModelRetired,
  passesActionFilter,
  passesRecordFilter,
  postedPickUnits,
} from '@/lib/thresholds';
import type { GameRow, Pick } from '@/types';
import { LIVE_RECORD_START } from '@/lib/recordStart';
import { decisionEdge } from '@/lib/decisionPrice';

/**
 * One day's posted-stake book. `units` and `risked` are what Discord adds.
 * `roi` is units divided by units risked (0 when nothing was risked).
 *
 * This is not `CustomModelStats`. That type's `profitFlat` and `stakedFlat`
 * are the Models tab's flat book, stored per 100 of one flat unit. Putting
 * the posted units in those fields made a day total look like that book.
 */
export interface DayStakeStats {
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  /** wins / (wins + losses). 0 when nothing was decided. */
  winRate: number;
  units: number;
  risked: number;
  roi: number;
}

export interface ModelDayStats extends DayStakeStats {
  modelId: string;
  /** In-play model. Its picks count exactly like a pre-game pick — they lock at
   *  first signal and settle the same way — but a reader deciding whether a day
   *  went well should be able to see which half of the book produced it. */
  live: boolean;
}

export interface SportDayBreakdown {
  sport: string;
  total: DayStakeStats;
  models: ModelDayStats[];
  /** This sport's BET picks that cleared the cut but have no W/L/P yet — shown
   *  so an unsettled day (e.g. WNBA finals not ingested yet) reads as "picks
   *  pending", never as "there were no picks". */
  pending: number;
  /** Graded BETs that passed the record filter and Discord does not have. */
  unpublished: number;
  /** How many of this sport's graded picks came from an in-play model. */
  live: number;
}

/** One game the models scored that day — every game with at least one scored
 *  pick row (any signal), with its final score when available. */
export interface DayGameSummary {
  gameId: string;
  sport: string;
  /** "AWY @ HOM" (UFC: "A vs B"; golf: the event name). */
  matchup: string;
  homeScore: number | null;
  awayScore: number | null;
  final: boolean;
  /** Scored pick rows (BET + AVOID + NONE) referencing this game. */
  pickCount: number;
  commenceTime: string | null;
}

export interface DailyResults {
  date: string;
  overall: DayStakeStats;
  sports: SportDayBreakdown[];
  /** BET picks that cleared the current cut but have no W/L/P yet (result NULL —
   *  a prop whose player DNP, or a game not settled at fetch time). Surfaced so
   *  the recap reconciles with the number of picks the user actually placed. */
  pending: number;
  /** Graded BETs left out because Discord does not have them. */
  unpublished: number;
  /** The individual graded (WIN/LOSS/PUSH) picks behind the record, sorted by
   *  sport order then profit desc, so the recap can list what was actually bet. */
  gradedPicks: Pick[];
  /** The still-open BET picks behind `pending`, same sport ordering. */
  pendingPicks: Pick[];
  /** How many graded picks across the whole day came from an in-play model.
   *  The day's record is the sum of both halves; this says how it splits. */
  live: number;
  /** Every game the models scored that day, with finals where available. */
  games: DayGameSummary[];
}

/** Earliest day the recap can show — the record start. */
export const RESULTS_MIN_DATE = LIVE_RECORD_START;

export function emptyDailyResults(date: string): DailyResults {
  return {
    date,
    overall: EMPTY_DAILY,
    sports: [],
    pending: 0,
    unpublished: 0,
    gradedPicks: [],
    pendingPicks: [],
    live: 0,
    games: [],
  };
}

// Preferred sport ordering — mirrors TrackRecordScreen's selector order.
const SPORT_ORDER: Record<string, number> = {
  MLB: 0,
  WNBA: 1,
  NBA: 2,
  NFL: 3,
  NCAAF: 4,
  UFC: 5,
  NHL: 6,
  // GOLF retired 2026-09-08 (mike) -- omitted so the recap grows no chip that
  // can only ever report zero. DailyResultsModal appends any sport the lib
  // returns that is missing here, so a golf row could still never be dropped.
};

/** Every sport the recap should always surface, in display order — a sport with
 *  no settled picks on a given day still gets an explicit empty section so an
 *  off day (e.g. no WNBA games) never reads as the sport being dropped. */
export const ALL_SPORTS: string[] = Object.keys(SPORT_ORDER).sort(
  (a, b) => SPORT_ORDER[a]! - SPORT_ORDER[b]!,
);

interface Acc {
  wins: number;
  losses: number;
  pushes: number;
  units: number;
  risked: number;
}

function emptyAcc(): Acc {
  return { wins: 0, losses: 0, pushes: 0, units: 0, risked: 0 };
}

/** Caller guarantees p.result is WIN / LOSS / PUSH. Money is the posted
 *  stake (`postedPickUnits`): 1 unit to win at the taken price, risk capped
 *  at 3. A missing price is 1 unit. A push adds no units and no risk. */
function tally(acc: Acc, p: Pick): void {
  if (p.result === 'WIN') acc.wins++;
  else if (p.result === 'LOSS') acc.losses++;
  else acc.pushes++; // PUSH
  const money = postedPickUnits(p);
  acc.units += money.units;
  acc.risked += money.risked;
}

function finalize(acc: Acc): DayStakeStats {
  const decided = acc.wins + acc.losses;
  const roi = acc.risked > 0 ? acc.units / acc.risked : 0;
  return {
    picks: acc.wins + acc.losses + acc.pushes,
    wins: acc.wins,
    losses: acc.losses,
    pushes: acc.pushes,
    winRate: decided > 0 ? acc.wins / decided : 0,
    units: acc.units,
    risked: acc.risked,
    roi,
  };
}

export const EMPTY_DAILY: DayStakeStats = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  units: 0,
  risked: 0,
  roi: 0,
};

/** Discord's `{units:+.2f}u`, with the app's unsigned zero and U+2212. */
export function dayUnitsText(units: number): string {
  return formatSigned(units, 2, 'u');
}

/** No decided bets (pushes only) has no win rate. An all-loss day is 0.0%. */
export function dayWinRateText(wins: number, losses: number, winRate: number): string {
  if (wins + losses <= 0) return '—';
  return formatPctSigned(winRate).replace('+', '');
}

/** Units won or lost divided by units risked. A day that risked nothing
 *  (a push, and nothing else) has no percentage — Discord leaves it off. */
export function dayRoiText(risked: number, roi: number): string {
  if (!(risked > 0)) return '—';
  return formatPctSigned(roi);
}

/** One sport's (or All's) slice of a day — what the modal renders once the
 *  user taps a sport chip. Pure so the filtering is unit-testable. */
export interface ScopedDailyResults {
  /** 'ALL' or a sport code. */
  scope: string;
  record: DayStakeStats;
  /** Per-model rows for a single-sport scope; null for 'ALL' (the modal shows
   *  the per-sport breakdown instead). */
  models: ModelDayStats[] | null;
  pending: number;
  /** Graded BETs in this scope that Discord does not have. */
  unpublished: number;
  /** Graded picks in this scope that came from an in-play model. */
  live: number;
  gradedPicks: Pick[];
  pendingPicks: Pick[];
  games: DayGameSummary[];
}

export function scopeDailyResults(r: DailyResults, sport: string): ScopedDailyResults {
  if (sport === 'ALL') {
    return {
      scope: 'ALL',
      record: r.overall,
      models: null,
      pending: r.pending,
      unpublished: r.unpublished,
      live: r.live,
      gradedPicks: r.gradedPicks,
      pendingPicks: r.pendingPicks,
      games: r.games,
    };
  }
  const section = r.sports.find((s) => s.sport === sport);
  return {
    scope: sport,
    record: section?.total ?? EMPTY_DAILY,
    models: section?.models ?? [],
    pending: section?.pending ?? 0,
    unpublished: section?.unpublished ?? 0,
    live: section?.live ?? 0,
    gradedPicks: r.gradedPicks.filter((p) => p.sport === sport),
    pendingPicks: r.pendingPicks.filter((p) => p.sport === sport),
    games: r.games.filter((g) => g.sport === sport),
  };
}

function bySportOrder(a: string, b: string): number {
  return (SPORT_ORDER[a] ?? 99) - (SPORT_ORDER[b] ?? 99) || a.localeCompare(b);
}

function gameMatchup(g: GameRow): string {
  if (g.sport === 'GOLF') return g.home_team; // event name; away is 'FIELD'
  if (g.sport === 'UFC') return `${g.away_team} vs ${g.home_team}`;
  return `${g.away_team} @ ${g.home_team}`;
}

/**
 * Group a day's picks into overall + per-sport + per-model records.
 * Only settled (WIN/LOSS/PUSH) BET picks that pass the record filter
 * count toward the record and the units. NO_ACTION rows, off-date rows, and
 * sub-threshold ungraded picks are excluded. BET picks awaiting a result (result NULL)
 * are tallied per-sport as `pending` and listed in `pendingPicks` — a sport
 * whose games haven't settled yet shows as "pending", never as absent.
 * `dayGames` (optional) yields `games`: every game with ≥1 scored pick row.
 * Accepts settled-only OR all-of-day picks (pending is 0 in the former).
 */
export function computeDailyResults(
  date: string,
  dayPicks: Pick[],
  dayGames: GameRow[] = [],
): DailyResults {
  const overall = emptyAcc();
  const bySport = new Map<string, Acc>();
  const byModel = new Map<string, { sport: string; acc: Acc; live: boolean }>();
  const pendingBySport = new Map<string, number>();
  const unpublishedBySport = new Map<string, number>();
  let unpublished = 0;
  const picksPerGame = new Map<string, number>();
  const gradedPicks: Pick[] = [];
  const pendingPicks: Pick[] = [];
  const liveBySport = new Map<string, number>();
  let liveGraded = 0;

  for (const p of dayPicks) {
    if (p.game_date !== date) continue;
    // Live in-play picks COUNT. They were excluded while the live board
    // delete-and-rescored every pass, when a live row was a moving quote rather
    // than a bet anyone was given. Since the first-signal lock they are the bet
    // of record: locked at their line and price, never re-priced, and settled
    // through the same path as a pre-game pick. Dropping them understated
    // 2026-08-29 by 23 of its 31 BET picks — the day mike asked about.
    //
    // CLV is the one thing that stays pre-game only, and it already is:
    // _capture_clv and all four record views filter is_live. An in-play price
    // has no meaningful closing line to be compared against.
    // A retired model — live or pre-game — is out of every total; its picks
    // stay in the DB as the record of what was published (§1c), nothing more.
    // (Until 2026-09-02 this was gated on is_live. passesActionFilter below
    // refuses a retired model too, so this is the explicit statement of the
    // rule, not the only thing enforcing it.)
    if (isModelRetired(p.model_id)) continue;

    // ...but `is_live` alone does not mean "in-play bet". The column carries a
    // SECOND population: the session-114 repair rows — ~14k PRE-GAME prop picks
    // retroactively flagged because they were scored against an in-play price
    // after first pitch. They are contamination, not bets, and 65 of them are
    // settled and clear current thresholds (20-45, -$1,493), so counting them
    // would put fabricated losses in the record session 114 removed. Only
    // model_id can tell the two apart.
    if (isContaminatedPregamePick(p)) continue;

    // Every scored row (BET/AVOID/NONE) counts toward its game's pick count.
    picksPerGame.set(p.game_id, (picksPerGame.get(p.game_id) ?? 0) + 1);

    // TWO QUESTIONS, TWO FILTERS (2026-09-12). A GRADED pick is history: it was
    // bet, so it counts however the model's cut or paused flag has moved since
    // — passesRecordFilter. An UNGRADED one is still a claim about what to bet
    // now, so a paused model's row must not be counted as placed —
    // passesActionFilter. Applying the action filter to both is what made the
    // Discord recap and this modal disagree: tracking/discord_notifier.py's
    // _SETTLED_SQL stopped re-cutting settled rows, and a surface with an extra
    // gate loses rows silently (CLAUDE.md 1b).
    const graded =
      p.result === 'WIN' || p.result === 'LOSS' || p.result === 'PUSH';
    if (!(graded ? passesRecordFilter(p) : passesActionFilter(p))) continue;
    // A graded BET Discord does not have is not in the published record.
    // Omitted means the ledger was not read (the pure tests). `unknown` is a
    // failed read and stays, so a ledger outage does not paint 0-0.
    if (graded && p.discordPublish === 'unpublished') {
      unpublished += 1;
      unpublishedBySport.set(p.sport, (unpublishedBySport.get(p.sport) ?? 0) + 1);
      continue;
    }
    if (p.result !== 'WIN' && p.result !== 'LOSS' && p.result !== 'PUSH') {
      if (p.result == null) {
        // Placed, not yet graded — track per sport so the breakdown can say
        // "N pending" instead of reading as a day with no picks.
        pendingPicks.push(p);
        pendingBySport.set(p.sport, (pendingBySport.get(p.sport) ?? 0) + 1);
      }
      continue;
    }

    gradedPicks.push(p);
    if (p.is_live) {
      liveGraded += 1;
      liveBySport.set(p.sport, (liveBySport.get(p.sport) ?? 0) + 1);
    }

    tally(overall, p);

    let sAcc = bySport.get(p.sport);
    if (!sAcc) {
      sAcc = emptyAcc();
      bySport.set(p.sport, sAcc);
    }
    tally(sAcc, p);

    let mEntry = byModel.get(p.model_id);
    if (!mEntry) {
      mEntry = { sport: p.sport, acc: emptyAcc(), live: false };
      byModel.set(p.model_id, mEntry);
    }
    // Read off the PICK, not parsed out of the model id. The row's own flag is
    // what every other consumer keys on (the views, _capture_clv, the Live
    // tab), so inferring it a second way would create two sources of truth
    // that can disagree — and the one that disagreed would be this one.
    if (p.is_live) mEntry.live = true;
    tally(mEntry.acc, p);
  }

  // Per-model rows grouped under their sport. Money is the same graded picks
  // as the W-L on the row.
  const modelsBySport = new Map<string, ModelDayStats[]>();
  for (const [modelId, { sport, acc, live }] of byModel) {
    const stats = finalize(acc);
    if (stats.picks === 0) continue;
    const arr = modelsBySport.get(sport) ?? [];
    arr.push({ modelId, live, ...stats });
    modelsBySport.set(sport, arr);
  }

  // A sport gets a section if it has counted picks or pending picks.
  const sectionSports = new Set([
    ...bySport.keys(),
    ...pendingBySport.keys(),
    ...unpublishedBySport.keys(),
    ...modelsBySport.keys(),
  ]);
  const sports: SportDayBreakdown[] = [];
  for (const sport of sectionSports) {
    const total = finalize(bySport.get(sport) ?? emptyAcc());
    const pendingCount = pendingBySport.get(sport) ?? 0;
    const unpublishedCount = unpublishedBySport.get(sport) ?? 0;
    const models = (modelsBySport.get(sport) ?? []).sort(
      (a, b) => b.units - a.units,
    );
    if (total.picks === 0 && pendingCount === 0 && unpublishedCount === 0 && models.length === 0) continue;
    sports.push({ sport, total, models, pending: pendingCount,
                  unpublished: unpublishedCount, live: liveBySport.get(sport) ?? 0 });
  }
  sports.sort((a, b) => bySportOrder(a.sport, b.sport));

  gradedPicks.sort(
    (a, b) =>
      bySportOrder(a.sport, b.sport) ||
      postedPickUnits(b).units - postedPickUnits(a).units,
  );
  pendingPicks.sort(
    (a, b) => bySportOrder(a.sport, b.sport) || decisionEdge(b) - decisionEdge(a),
  );

  // Every game the models scored that day (≥1 pick row of any signal).
  const games: DayGameSummary[] = dayGames
    .filter((g) => g.game_date === date && (picksPerGame.get(g.game_id) ?? 0) > 0)
    .map((g) => ({
      gameId: g.game_id,
      sport: g.sport,
      matchup: gameMatchup(g),
      homeScore: g.home_score,
      awayScore: g.away_score,
      final: g.home_score != null && g.away_score != null,
      pickCount: picksPerGame.get(g.game_id) ?? 0,
      commenceTime: g.commence_time ?? null,
    }))
    .sort(
      (a, b) =>
        bySportOrder(a.sport, b.sport) ||
        (a.commenceTime ?? '').localeCompare(b.commenceTime ?? '') ||
        a.gameId.localeCompare(b.gameId),
    );

  return {
    date,
    overall: finalize(overall),
    sports,
    pending: pendingPicks.length,
    unpublished,
    gradedPicks,
    pendingPicks,
    live: liveGraded,
    games,
  };
}
