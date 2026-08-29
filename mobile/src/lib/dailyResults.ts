/**
 * Per-day, per-model results aggregation for the "Yesterday's results" recap.
 *
 * Pure (no React / Supabase) so it's unit-testable. Grades a single day's
 * SETTLED BET picks at the CURRENT action thresholds — the same flat-ROI /
 * W-L-P logic the Models tab uses (computeBuiltInModelStats). For recent days
 * this matches the full-outcome view (yesterday's BET picks were generated under
 * today's server-driven thresholds), without needing a per-day DB view.
 */
import { passesActionFilter, RECORD_ONLY_MODELS } from '@/lib/thresholds';
import type { GameRow, Pick } from '@/types';
import type { CustomModelStats } from '@/hooks/useCustomModelStats';

export interface ModelDayStats extends CustomModelStats {
  modelId: string;
  /** Record-only model (e.g. batter HR): its W-L is shown on the row, but it is
   *  excluded from the overall/sport totals and its money fields are zeroed —
   *  the same treatment as the Models tab and the public track record. */
  recordOnly: boolean;
}

export interface SportDayBreakdown {
  sport: string;
  total: CustomModelStats;
  models: ModelDayStats[];
  /** This sport's BET picks that cleared the cut but have no W/L/P yet — shown
   *  so an unsettled day (e.g. WNBA finals not ingested yet) reads as "picks
   *  pending", never as "there were no picks". */
  pending: number;
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
  overall: CustomModelStats;
  sports: SportDayBreakdown[];
  /** BET picks that cleared the current cut but have no W/L/P yet (result NULL —
   *  a prop whose player DNP, or a game not settled at fetch time). Surfaced so
   *  the recap reconciles with the number of picks the user actually placed. */
  pending: number;
  /** The individual graded (WIN/LOSS/PUSH) picks behind the record, sorted by
   *  sport order then profit desc, so the recap can list what was actually bet. */
  gradedPicks: Pick[];
  /** The still-open BET picks behind `pending`, same sport ordering. */
  pendingPicks: Pick[];
  /** Every game the models scored that day, with finals where available. */
  games: DayGameSummary[];
}

/** Earliest day the recap can show — the record start. */
export const RESULTS_MIN_DATE = '2026-04-14';

export function emptyDailyResults(date: string): DailyResults {
  return {
    date,
    overall: EMPTY_DAILY,
    sports: [],
    pending: 0,
    gradedPicks: [],
    pendingPicks: [],
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
  GOLF: 7,
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
  profitFlat: number;
  stakedFlat: number;
}

function emptyAcc(): Acc {
  return { wins: 0, losses: 0, pushes: 0, profitFlat: 0, stakedFlat: 0 };
}

/** Caller guarantees p.result is WIN / LOSS / PUSH. Each settled pick stakes
 *  $100 flat — pushes count toward staked (matches computeBuiltInModelStats). */
function tally(acc: Acc, p: Pick): void {
  if (p.result === 'WIN') acc.wins++;
  else if (p.result === 'LOSS') acc.losses++;
  else acc.pushes++; // PUSH
  acc.profitFlat += Number(p.profit_flat ?? 0);
  acc.stakedFlat += 100;
}

function finalize(acc: Acc): CustomModelStats {
  const decided = acc.wins + acc.losses;
  return {
    picks: acc.wins + acc.losses + acc.pushes,
    wins: acc.wins,
    losses: acc.losses,
    pushes: acc.pushes,
    winRate: decided > 0 ? acc.wins / decided : 0,
    profitFlat: acc.profitFlat,
    stakedFlat: acc.stakedFlat,
    roiFlat: acc.stakedFlat > 0 ? acc.profitFlat / acc.stakedFlat : 0,
  };
}

export const EMPTY_DAILY: CustomModelStats = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  winRate: 0,
  profitFlat: 0,
  stakedFlat: 0,
  roiFlat: 0,
};

/** One sport's (or All's) slice of a day — what the modal renders once the
 *  user taps a sport chip. Pure so the filtering is unit-testable. */
export interface ScopedDailyResults {
  /** 'ALL' or a sport code. */
  scope: string;
  record: CustomModelStats;
  /** Per-model rows for a single-sport scope; null for 'ALL' (the modal shows
   *  the per-sport breakdown instead). */
  models: ModelDayStats[] | null;
  pending: number;
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
 * Only settled (WIN/LOSS/PUSH) BET picks that pass the current action filter
 * count toward the record; NO_ACTION rows, off-date rows, live picks, and
 * sub-threshold picks are excluded. Record-only models (RECORD_ONLY_MODELS —
 * batter HR) are listed but never counted. BET picks awaiting a result (result NULL)
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
  const byModel = new Map<string, { sport: string; acc: Acc }>();
  const pendingBySport = new Map<string, number>();
  const picksPerGame = new Map<string, number>();
  const gradedPicks: Pick[] = [];
  const pendingPicks: Pick[] = [];

  for (const p of dayPicks) {
    if (p.game_date !== date) continue;
    if (p.is_live) continue; // pre-game board only

    // Every scored row (BET/AVOID/NONE) counts toward its game's pick count.
    picksPerGame.set(p.game_id, (picksPerGame.get(p.game_id) ?? 0) + 1);

    if (!passesActionFilter(p)) continue; // BET-only, meets current cut
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

    // Record-only models (batter HR) are listed and get a per-model W-L row,
    // but never count toward the overall or per-sport record/P&L.
    if (!RECORD_ONLY_MODELS.has(p.model_id)) {
      tally(overall, p);

      let sAcc = bySport.get(p.sport);
      if (!sAcc) {
        sAcc = emptyAcc();
        bySport.set(p.sport, sAcc);
      }
      tally(sAcc, p);
    }

    let mEntry = byModel.get(p.model_id);
    if (!mEntry) {
      mEntry = { sport: p.sport, acc: emptyAcc() };
      byModel.set(p.model_id, mEntry);
    }
    tally(mEntry.acc, p);
  }

  // Per-model rows grouped under their sport. Record-only models keep their
  // W-L but get zeroed money so the row can never read as counted P&L.
  const modelsBySport = new Map<string, ModelDayStats[]>();
  for (const [modelId, { sport, acc }] of byModel) {
    const recordOnly = RECORD_ONLY_MODELS.has(modelId);
    let stats = finalize(acc);
    if (stats.picks === 0) continue;
    if (recordOnly) stats = { ...stats, profitFlat: 0, stakedFlat: 0, roiFlat: 0 };
    const arr = modelsBySport.get(sport) ?? [];
    arr.push({ modelId, recordOnly, ...stats });
    modelsBySport.set(sport, arr);
  }

  // A sport gets a section if it has counted picks, pending picks, OR
  // record-only model rows — a day where only HR graded must still surface MLB.
  const sectionSports = new Set([
    ...bySport.keys(),
    ...pendingBySport.keys(),
    ...modelsBySport.keys(),
  ]);
  const sports: SportDayBreakdown[] = [];
  for (const sport of sectionSports) {
    const total = finalize(bySport.get(sport) ?? emptyAcc());
    const pendingCount = pendingBySport.get(sport) ?? 0;
    const models = (modelsBySport.get(sport) ?? []).sort(
      (a, b) => b.profitFlat - a.profitFlat,
    );
    if (total.picks === 0 && pendingCount === 0 && models.length === 0) continue;
    sports.push({ sport, total, models, pending: pendingCount });
  }
  sports.sort((a, b) => bySportOrder(a.sport, b.sport));

  gradedPicks.sort(
    (a, b) =>
      bySportOrder(a.sport, b.sport) ||
      Number(b.profit_flat ?? 0) - Number(a.profit_flat ?? 0),
  );
  pendingPicks.sort(
    (a, b) => bySportOrder(a.sport, b.sport) || Number(b.edge ?? 0) - Number(a.edge ?? 0),
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
    gradedPicks,
    pendingPicks,
    games,
  };
}
