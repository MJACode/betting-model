/**
 * Aggregation helpers for the public track record (v_public_track_record).
 * The view already applies the current action criteria per model; here we just
 * roll the per-model rows up to overall and per-sport summaries for display.
 */

import type { TrackRecordRow } from '@/types';

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
