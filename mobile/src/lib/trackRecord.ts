/**
 * Aggregation helpers for the public track record (v_public_track_record).
 * The view already applies the current action criteria per model; here we just
 * roll the per-model rows up to overall and per-sport summaries for display.
 */

import { isModelRetired } from '@/lib/thresholds';
import type { ParlayTrackRow, TrackRecordRow } from '@/types';

export interface TrackRecordSummary {
  picks: number;
  wins: number;
  losses: number;
  pushes: number;
  profitFlat: number;
  stakedFlat: number;
  roiFlat: number; // profit / staked
  winRate: number; // wins / (wins + losses)
  clvSettled: number;
  clvBeat: number;
  clvBeatRate: number | null; // clvBeat / clvSettled
}

export const EMPTY_SUMMARY: TrackRecordSummary = {
  picks: 0,
  wins: 0,
  losses: 0,
  pushes: 0,
  profitFlat: 0,
  stakedFlat: 0,
  roiFlat: 0,
  winRate: 0,
  clvSettled: 0,
  clvBeat: 0,
  clvBeatRate: null,
};

export function summarize(rows: TrackRecordRow[]): TrackRecordSummary {
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  let stakedFlat = 0;
  let clvSettled = 0;
  let clvBeat = 0;

  for (const r of rows) {
    // The view drops a retired model once threshold_sync prunes its row; until
    // then the row survives and would count. Same guard as passesActionFilter.
    if (isModelRetired(r.model_id)) continue;
    wins += Number(r.wins ?? 0);
    losses += Number(r.losses ?? 0);
    pushes += Number(r.pushes ?? 0);
    profitFlat += Number(r.profit_flat ?? 0);
    stakedFlat += Number(r.staked_flat ?? 0);
    clvSettled += Number(r.clv_settled ?? 0);
    clvBeat += Number(r.clv_beat ?? 0);
  }

  const decided = wins + losses;
  return {
    picks: wins + losses + pushes,
    wins,
    losses,
    pushes,
    profitFlat,
    stakedFlat,
    roiFlat: stakedFlat > 0 ? profitFlat / stakedFlat : 0,
    winRate: decided > 0 ? wins / decided : 0,
    clvSettled,
    clvBeat,
    clvBeatRate: clvSettled > 0 ? clvBeat / clvSettled : null,
  };
}

export interface SportGroup {
  sport: string;
  summary: TrackRecordSummary;
  models: TrackRecordRow[]; // sorted by profit desc
}

/** Group per-model rows by sport, dropping models with no settled picks. */
export function groupBySport(rows: TrackRecordRow[]): SportGroup[] {
  const bySport = new Map<string, TrackRecordRow[]>();
  for (const r of rows) {
    if (isModelRetired(r.model_id)) continue;
    if (Number(r.picks ?? 0) <= 0) continue; // no settled picks yet
    const list = bySport.get(r.sport) ?? [];
    list.push(r);
    bySport.set(r.sport, list);
  }

  const groups: SportGroup[] = [];
  for (const [sport, list] of bySport) {
    const models = [...list].sort(
      (a, b) => Number(b.profit_flat ?? 0) - Number(a.profit_flat ?? 0),
    );
    groups.push({ sport, summary: summarize(list), models });
  }
  // Most active sport first.
  return groups.sort((a, b) => b.summary.picks - a.summary.picks);
}

// ── Parlay record (public parlay track record) ───────────────────────────────

export interface ParlaySummary {
  parlays: number; // settled W/L/P
  wins: number;
  losses: number;
  pushes: number;
  profitFlat: number; // units (1u flat stake per parlay)
  roiFlat: number; // profit / decided
  winRate: number; // wins / (wins + losses)
}

/** Summarize settled tracked parlays. Flat 1-unit stake each. */
export function summarizeParlays(rows: ParlayTrackRow[]): ParlaySummary {
  let wins = 0;
  let losses = 0;
  let pushes = 0;
  let profitFlat = 0;
  for (const r of rows) {
    if (r.result === 'WIN') wins += 1;
    else if (r.result === 'LOSS') losses += 1;
    else if (r.result === 'PUSH') pushes += 1;
    if (r.result === 'WIN' || r.result === 'LOSS') profitFlat += Number(r.profit_flat ?? 0);
  }
  const decided = wins + losses;
  return {
    parlays: wins + losses + pushes,
    wins,
    losses,
    pushes,
    profitFlat,
    roiFlat: decided > 0 ? profitFlat / decided : 0,
    winRate: decided > 0 ? wins / decided : 0,
  };
}
