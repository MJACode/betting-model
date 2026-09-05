import type { TonightMatchupRow } from '@/types';

/**
 * Tonight-matchup grading for the Stats tab's MATCHUP column.
 *
 * A leaderboard row is joined to tonight's slate by TEAM (the player's team
 * from the season/window totals). The column answers ONE question — how hard
 * is this spot? — as a letter grade (Matt, 2026-09-05: "update spot column to
 * just be difficulty of that match up and have a bigger scale besides low med
 * and high").
 *
 * What drives the grade, per row type:
 *   - Batters   → the opposing probable starter's season ERA. A bad pitcher
 *                 (high ERA) is FAVORABLE for the hitter.
 *   - Pitchers  → the opposing lineup's wOBA + K% (weak, whiffy offense =
 *                 favorable).
 *   - WNBA      → the opposing team's defensive rating (higher = worse
 *                 defense = favorable for scorers).
 *
 * ── Why this replaced three tiers ──────────────────────────────────────────
 *
 * The previous scale was `favorable | neutral | tough` off hand-set cliffs
 * described as "league-typical bands". Measured against the actual 2026 data
 * (Supabase, 2026-09-05) two of the three were badly mis-centred, and the
 * column was mostly printing one colour:
 *
 *   metric                     shipped cliffs      what they classified
 *   opposing starter ERA       ≥4.60 / ≤3.40       32% / 38% / 31%   (fine)
 *   opposing lineup wOBA       ≤.305 / ≥.330       10% / 81% / 10%
 *   opposing lineup K%         ≥.235 / ≤.190       23% / 74% /  3%
 *   WNBA opp def rating        ≥104  / ≤98.5       77% /  18% /  6%
 *
 * So a WNBA row was called a favorable spot three times in four, and a pitcher
 * row was grey four times in five. The cliffs assumed a ~101 league-average
 * defensive rating; the measured 2026 average is 106.5.
 *
 * A grade fixes both at once because it is defined RELATIVE TO THE MEASURED
 * DISTRIBUTION rather than to a remembered number: the anchors below are
 * medians and IQR-derived spreads pulled from the database, and the letter is
 * the percentile they place a row at. Re-measure them when a season turns —
 * `docs/sports/mlb.md` carries the queries.
 */

export type MatchupGrade =
  | 'A+' | 'A' | 'A-'
  | 'B+' | 'B' | 'B-'
  | 'C+' | 'C' | 'C-'
  | 'D+' | 'D' | 'D-'
  | 'F';

export interface MatchupInfo {
  /**
   * How good this spot is for the row, as a letter. NULL when the feed has
   * nothing to grade on — an unknown matchup is a dash, never a C. Grading a
   * missing starter as average is inventing the one fact the column exists to
   * report.
   */
  grade: MatchupGrade | null;
  /** The 0..1 favourability percentile the grade came from. */
  score: number | null;
  /** e.g. "vs LAA · S. Gray 5.90 ERA (R)" — the whole fact, for the detail screen. */
  text: string;
  /**
   * The fact WITHOUT the opponent, spoken: "S. Gray 5.90 ERA, right-handed".
   *
   * The MATCHUP cell's screen-reader label uses this, not `text`: the row's
   * subline already announces "at SEA", so a label built on `text` said the
   * opponent twice from two sources and in two idioms — "at SEA" then "vs LAA"
   * (UX review, 2026-09-05). Same duplication the visual layer fixed, one
   * layer down. The handedness is a word here rather than "(R)", which
   * VoiceOver reads as punctuation.
   */
  fact: string | null;
  row: TonightMatchupRow;
}

/**
 * League anchors. MEASURED, not remembered — every pair below is a median and
 * an IQR-derived sigma ((p75 − p25) / 1.349, which is robust to the handful of
 * 20.00-ERA call-ups that would wreck a plain standard deviation).
 *
 * Measured 2026-09-05 against the production database:
 *
 *   starterEra   n=2,617 probable-starter days since 2026-05-01 (every pitcher
 *                carrying a `pitcher_strikeouts` prop, at the ERA he held that
 *                day — the exact population this column grades).
 *                median 4.00, p25 3.21, p75 4.86.
 *   teamWoba     n=31, latest `mlb_team_stats` per team. median .3160.
 *   teamKPct     n=31, same rows. median .2180.
 *   wnbaDefRtg   n=17, latest `wnba_team_stats` per team. median 106.46.
 *
 * Sign is applied at the call site, so every anchor here is just "where the
 * middle is and how wide the middle is".
 */
const ANCHORS = {
  starterEra: { median: 4.0, sigma: 1.223 },
  teamWoba: { median: 0.316, sigma: 0.0078 },
  teamKPct: { median: 0.218, sigma: 0.0126 },
  wnbaDefRtg: { median: 106.46, sigma: 3.403 },
} as const;

/**
 * wOBA and K% are averaged into one pitcher score, and averaging two
 * correlated z-scores shrinks the spread — so the blend is divided by its own
 * measured sigma to put it back on the unit scale the grade cuts assume.
 * Measured at 0.803 across the 31 teams (corr(wOBA, K%) = 0.29, and
 * sqrt((1 + 0.29) / 2) = 0.803 — the measurement and the algebra agree).
 * Without it every pitcher row drifts a grade and a half toward C.
 */
const PITCHER_BLEND_SIGMA = 0.803;

/**
 * Grade cuts on the 0..1 percentile. Symmetric, with C the widest band: an
 * average matchup is the single most common thing a row can be, and a scale
 * whose middle is narrow flickers between C- and C+ on noise.
 */
const GRADE_CUTS: [number, MatchupGrade][] = [
  [0.955, 'A+'],
  [0.9, 'A'],
  [0.82, 'A-'],
  [0.73, 'B+'],
  [0.64, 'B'],
  [0.55, 'B-'],
  [0.46, 'C+'],
  [0.36, 'C'],
  [0.27, 'C-'],
  [0.18, 'D+'],
  [0.1, 'D'],
  [0.045, 'D-'],
];

/** Standard normal CDF — Abramowitz & Stegun 26.2.17, |error| < 7.5e-8. */
export function normalCdf(z: number): number {
  const t = 1 / (1 + 0.2316419 * Math.abs(z));
  const d = 0.3989422804014327 * Math.exp((-z * z) / 2);
  const p =
    d *
    t *
    (0.31938153 +
      t * (-0.356563782 + t * (1.781477937 + t * (-1.821255978 + t * 1.330274429))));
  return z >= 0 ? 1 - p : p;
}

/** A favourability percentile → its letter. */
export function gradeFor(score: number | null): MatchupGrade | null {
  if (score == null || !Number.isFinite(score)) return null;
  for (const [cut, grade] of GRADE_CUTS) if (score >= cut) return grade;
  return 'F';
}

/** 'B+' → "B plus" — VoiceOver reads a bare "+" as nothing at all. */
export function gradeSpoken(grade: MatchupGrade): string {
  if (grade.endsWith('+')) return `${grade[0]} plus`;
  if (grade.endsWith('-')) return `${grade[0]} minus`;
  return grade;
}

/** "R" → "right-handed". Spoken labels get words, not initials. */
function handWord(hand: string | null | undefined): string {
  if (hand === 'R') return ', right-handed';
  if (hand === 'L') return ', left-handed';
  return '';
}

const num = (v: number | string | null | undefined): number | null => {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
};

const z = (value: number, anchor: { median: number; sigma: number }): number =>
  (value - anchor.median) / anchor.sigma;

/**
 * "Braxton Ashcraft" → "Ashcraft".
 *
 * A bare `parts[parts.length - 1]` shipped **"Jr."** for every suffixed pitcher
 * — "Nestor Cortes Jr." is a real name on a real probables feed, and both MLB
 * StatsAPI and the DK feed carry the suffix. Particles are kept too, because
 * "De Leon" and "De La Cruz" are the surname, not "Leon" and "Cruz".
 */
const SUFFIXES = new Set(['jr', 'jr.', 'sr', 'sr.', 'ii', 'iii', 'iv', 'v']);
const PARTICLES = new Set(['de', 'del', 'de la', 'la', 'van', 'von', 'da', 'di', "o'"]);

export function lastName(name: string): string {
  const parts = name.trim().split(/\s+/);
  while (parts.length > 1 && SUFFIXES.has(parts[parts.length - 1].toLowerCase())) parts.pop();
  if (parts.length < 2) return parts[0] ?? name;
  // Walk back over particles so a two- or three-word surname survives whole.
  let i = parts.length - 1;
  while (i > 1 && PARTICLES.has(parts[i - 1].toLowerCase())) i--;
  return parts.slice(i).join(' ');
}

/** "Braxton Ashcraft" → "B. Ashcraft" */
export function shortName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2) return name;
  return `${parts[0][0]}. ${parts.slice(1).join(' ')}`;
}

/** team → matchup row for tonight (first game on doubleheader days). */
export function buildMatchupMap(rows: TonightMatchupRow[]): Map<string, TonightMatchupRow> {
  const map = new Map<string, TonightMatchupRow>();
  for (const r of rows) if (!map.has(r.team)) map.set(r.team, r);
  return map;
}

/** Batter vs the opposing starter: high ERA = favorable. */
function gradeBatter(m: TonightMatchupRow): MatchupInfo {
  const era = num(m.opp_starter_era);
  const hand = m.opp_starter_hand ? ` (${m.opp_starter_hand})` : '';
  if (!m.opp_starter_name || era == null) {
    // Ungraded, not average. "TBD" only when the STARTER is unknown; a named
    // starter with no ERA yet — a call-up, a first start — is still an unknown
    // SPOT, so both land here.
    return {
      grade: null,
      score: null,
      text: `vs ${m.opponent} · ${m.opp_starter_name ?? 'starter TBD'}`,
      fact: m.opp_starter_name ? shortName(m.opp_starter_name) : null,
      row: m,
    };
  }
  const score = normalCdf(z(era, ANCHORS.starterEra));
  return {
    grade: gradeFor(score),
    score,
    text: `vs ${m.opponent} · ${shortName(m.opp_starter_name)} ${era.toFixed(2)} ERA${hand}`,
    fact: `${shortName(m.opp_starter_name)} ${era.toFixed(2)} ERA${handWord(m.opp_starter_hand)}`,
    row: m,
  };
}

/** Pitcher vs the opposing lineup: low wOBA / high K% = favorable. */
function gradePitcher(m: TonightMatchupRow): MatchupInfo {
  const woba = num(m.opp_team_woba);
  const kPct = num(m.opp_team_k_pct);
  if (woba == null && kPct == null) {
    return { grade: null, score: null, text: `vs ${m.opponent}`, fact: null, row: m };
  }
  // Both signs point the same way — toward "good for the pitcher".
  const zs: number[] = [];
  if (woba != null) zs.push(-z(woba, ANCHORS.teamWoba));
  if (kPct != null) zs.push(z(kPct, ANCHORS.teamKPct));
  // One metric is already on the unit scale; only a BLEND needs rescaling.
  const raw = zs.reduce((a, b) => a + b, 0) / zs.length;
  const score = normalCdf(zs.length > 1 ? raw / PITCHER_BLEND_SIGMA : raw);
  const bits: string[] = [];
  if (woba != null) bits.push(`${woba.toFixed(3).replace(/^0/, '')} wOBA`);
  if (kPct != null) bits.push(`${(kPct * 100).toFixed(1)}% K`);
  return {
    grade: gradeFor(score),
    score,
    text: `vs ${m.opponent} · ${bits.join(', ')}`,
    fact: bits.join(', '),
    row: m,
  };
}

/** WNBA scorer vs the opposing defense: high def rating = favorable. */
function gradeWnba(m: TonightMatchupRow): MatchupInfo {
  const def = num(m.opp_def_rating);
  if (def == null) return { grade: null, score: null, text: `vs ${m.opponent}`, fact: null, row: m };
  const score = normalCdf(z(def, ANCHORS.wnbaDefRtg));
  return {
    grade: gradeFor(score),
    score,
    text: `vs ${m.opponent} · DefRtg ${def.toFixed(1)}`,
    fact: `${def.toFixed(1)} defensive rating`,
    row: m,
  };
}

export function gradeMatchup(
  sport: string,
  playerType: 'batter' | 'pitcher' | undefined,
  m: TonightMatchupRow,
): MatchupInfo {
  if (sport === 'WNBA') return gradeWnba(m);
  if (playerType === 'pitcher') return gradePitcher(m);
  return gradeBatter(m);
}
