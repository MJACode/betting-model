/**
 * Sharp Score + contrarian/sharp-money tag.
 *
 * The Sharp Score answers "how sharp is this bet?" in one 0–100 number, blending
 * three things we already compute but never combined: how far the pick clears its
 * model's own edge bar, how well that model has historically beaten the closing
 * line (CLV pedigree), and whether the public is on the light side (contrarian).
 *
 * All functions are pure. The model-CLV pedigree comes from a module store
 * populated once at app start (useModelClvPedigree) — the same pattern as the
 * server-threshold store in thresholds.ts — so cards compute the score with no
 * per-row fetch.
 */

import { thresholdFor } from '@/lib/thresholds';
import type { Pick } from '@/types';

// ── Model CLV pedigree store ────────────────────────────────────────────────
export interface ModelClv {
  beatRate: number | null; // share of settled picks that beat the close (clv_beat / clv_settled)
  avgClvPct: number | null;
  settled: number; // settled picks with a captured CLV (sample size)
}

// Below this CLV sample a model is treated as "unproven" — the pedigree
// component falls back to neutral rather than trusting a tiny beat-rate.
export const MIN_CLV_SAMPLE = 20;

let store: Record<string, ModelClv> | null = null;

export function setModelClv(map: Record<string, ModelClv> | null): void {
  store = map;
}

export function modelClvFor(modelId: string): ModelClv | null {
  return store?.[modelId] ?? null;
}

// ── Contrarian / sharp-money tag ────────────────────────────────────────────
export type ContrarianTone = 'sharp' | 'crowded';

export interface ContrarianTag {
  tone: ContrarianTone;
  label: string;
  /** % of public bets on OUR side (lower = more contrarian). */
  betPct: number;
}

/**
 * public_bet_pct is the share of public tickets on the side WE picked. When the
 * crowd is light on our side (we hold the contrarian, better-priced side) that's
 * a sharp-money signal; when the crowd is piled onto our side the line is at
 * risk of moving against us. Only meaningful for full-game ML/O/U/RL picks that
 * carry splits — props/F5/golf store NULL and get no tag.
 */
export function contrarianTag(pick: Pick): ContrarianTag | null {
  if (pick.signal_type !== 'BET') return null;
  const bets = numOrNull(pick.public_bet_pct);
  if (bets == null) return null;
  if (bets <= 40) return { tone: 'sharp', label: 'Sharp side', betPct: bets };
  if (bets >= 65) return { tone: 'crowded', label: 'Public-heavy', betPct: bets };
  return null;
}

// ── Sharp Score ─────────────────────────────────────────────────────────────
export type SharpBand = 'high' | 'med' | 'low';

export interface SharpScoreParts {
  edge: number; // 0..40
  pedigree: number; // 0..40
  contrarian: number; // 0..20
  pedigreeKnown: boolean;
  contrarianKnown: boolean;
}

export interface SharpScore {
  score: number; // 0..100
  band: SharpBand;
  parts: SharpScoreParts;
}

const EDGE_MAX = 40;
const PEDIGREE_MAX = 40;
const CONTRARIAN_MAX = 20;

function clamp01(x: number): number {
  return x < 0 ? 0 : x > 1 ? 1 : x;
}

/**
 * 0–100 composite, only for BET picks. Components:
 *  - Edge strength (0–40): how far past the model's own min_edge the pick sits
 *    (3× the bar = full marks). Prob-only models use model_probability over
 *    their min_prob instead, since edge is ignored for them.
 *  - CLV pedigree (0–40): the model's historical beat-the-close rate (0.40→0,
 *    0.80→full). Unproven models (sample < MIN_CLV_SAMPLE) score a neutral 20.
 *  - Contrarian bonus (0–20): low public share on our side scores higher; no
 *    split available → neutral 10.
 */
export function sharpScore(pick: Pick): SharpScore | null {
  if (pick.signal_type !== 'BET') return null;
  const t = thresholdFor(pick.model_id);

  // Edge component.
  let edge: number;
  if (t?.prob_only) {
    const floor = t.min_prob;
    edge = EDGE_MAX * clamp01((pick.model_probability - floor) / Math.max(1 - floor, 0.01));
  } else {
    const bar = t?.min_edge ?? 0.05;
    // edge == bar → 0; edge == 3×bar → full.
    edge = EDGE_MAX * clamp01((pick.edge - bar) / Math.max(2 * bar, 0.04));
  }

  // CLV pedigree component.
  const clv = modelClvFor(pick.model_id);
  const pedigreeKnown = clv != null && clv.beatRate != null && clv.settled >= MIN_CLV_SAMPLE;
  const pedigree = pedigreeKnown
    ? PEDIGREE_MAX * clamp01((clv!.beatRate! - 0.4) / 0.4)
    : PEDIGREE_MAX * 0.5; // neutral when unproven

  // Contrarian component.
  const tag = contrarianTag(pick);
  const bets = numOrNull(pick.public_bet_pct);
  const contrarianKnown = bets != null;
  let contrarian: number;
  if (!contrarianKnown) {
    contrarian = CONTRARIAN_MAX * 0.5; // neutral
  } else if (tag?.tone === 'sharp') {
    contrarian = CONTRARIAN_MAX; // light public on our side
  } else if (tag?.tone === 'crowded') {
    contrarian = 0; // crowd piled onto our side
  } else {
    contrarian = CONTRARIAN_MAX * 0.5;
  }

  const score = Math.round(edge + pedigree + contrarian);
  return {
    score,
    band: score >= 70 ? 'high' : score >= 45 ? 'med' : 'low',
    parts: { edge, pedigree, contrarian, pedigreeKnown, contrarianKnown },
  };
}

function numOrNull(v: number | string | null | undefined): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}
