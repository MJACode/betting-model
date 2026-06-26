/**
 * Calibration ("reliability") of settled BET picks: do the model's stated
 * probabilities match how often those picks actually win? When we say 70%, does
 * it hit ~70%? This is the honesty metric no hype app shows.
 *
 * Pure. Fed by settled Pick[] (model_probability = predicted, result = actual).
 */

import type { Pick } from '@/types';

export interface CalibrationBin {
  n: number; // sample size in the bin
  predMean: number; // mean predicted probability (0..1)
  actualRate: number; // empirical win rate (0..1)
  lo: number; // predicted-prob range covered by the bin
  hi: number;
}

export interface Calibration {
  bins: CalibrationBin[];
  /** Sample-weighted mean |predicted − actual| across bins, in 0..1. */
  gap: number;
  n: number; // total decided picks
}

export interface CalibrationOpts {
  minTotal?: number; // need at least this many decided picks to chart
  minPerBin?: number; // target picks per quantile bin
  maxBins?: number;
}

const mean = (xs: number[]): number => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0);

/**
 * Quantile-binned reliability. Decided (WIN/LOSS) picks are sorted by predicted
 * probability and split into up to maxBins equal-count groups, so each point is
 * backed by a comparable sample — more robust than fixed-width bins on small,
 * skewed prop/golf distributions. Returns null below minTotal.
 */
export function buildCalibration(picks: Pick[], opts: CalibrationOpts = {}): Calibration | null {
  const minTotal = opts.minTotal ?? 15;
  const minPerBin = opts.minPerBin ?? 6;
  const maxBins = opts.maxBins ?? 6;

  const decided = picks
    .filter((p) => p.result === 'WIN' || p.result === 'LOSS')
    .map((p) => ({ p: Number(p.model_probability), won: p.result === 'WIN' ? 1 : 0 }))
    .filter((d) => Number.isFinite(d.p));

  const n = decided.length;
  if (n < minTotal) return null;
  decided.sort((a, b) => a.p - b.p);

  const k = Math.max(1, Math.min(maxBins, Math.floor(n / minPerBin)));
  const bins: CalibrationBin[] = [];
  for (let i = 0; i < k; i++) {
    const start = Math.floor((i * n) / k);
    const end = Math.floor(((i + 1) * n) / k);
    const slice = decided.slice(start, end);
    if (!slice.length) continue;
    bins.push({
      n: slice.length,
      predMean: mean(slice.map((s) => s.p)),
      actualRate: mean(slice.map((s) => s.won)),
      lo: slice[0]!.p,
      hi: slice[slice.length - 1]!.p,
    });
  }

  const gap = bins.reduce((acc, b) => acc + b.n * Math.abs(b.predMean - b.actualRate), 0) / n;
  return { bins, gap, n };
}

/** A plain-English read on the gap for captions. */
export function calibrationVerdict(gap: number): string {
  if (gap <= 0.05) return 'Well calibrated — stated odds match reality closely.';
  if (gap <= 0.1) return 'Reasonably calibrated — small drift between stated and actual.';
  return 'Loosely calibrated so far — stated odds and outcomes still diverge (small sample or drift).';
}
