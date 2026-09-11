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

/**
 * Does the grade column span more than one COLOUR on screen?
 *
 * `gradeColor` collapses A/B into good, C into mid and D/F into bad, so a
 * two-team NFL slate whose defences were both top-decile paints every one of
 * ~110 rows the same red, 60pt from a live price — which reads as a verdict on
 * the bet rather than a ranking of players. The LETTER is right and stays
 * (D- on both sides of tonight's opener is true); it is the ramp that has to
 * go quiet. Same rule, and the same reason, as hitRateColorDiscriminates.
 */
export function gradeColorDiscriminates(grades: (MatchupGrade | null)[]): boolean {
  const bands = grades
    .filter((g): g is MatchupGrade => g != null)
    .map((g) => (g.startsWith('A') || g.startsWith('B') ? 'good' : g.startsWith('C') ? 'mid' : 'bad'));
  if (bands.length < 2) return false;
  return bands.some((b) => b !== bands[0]);
}

/**
 * The four grades a floor can be set to, best first.
 *
 * The full scale is thirteen letters and a row of thirteen chips is a wall;
 * these are the four people reach for. Comparison is on GRADE_ORDER below, so
 * a row graded between two of them still cuts correctly.
 */
export const GRADE_FLOORS: MatchupGrade[] = ['A', 'B', 'C', 'D'];

/**
 * Is this grade at or above the floor?
 *
 * `includeUngraded` DEFAULTS TO TRUE, and that default is a correction. A dash
 * means we hold no rating for that defence, not that the spot is bad — and on
 * an NCAAF Saturday the ungraded rows are the FCS visitors, i.e. the softest
 * spots on the board. Hiding them by default made a filter whose stated
 * question is "show me the easy matchups" delete the easiest ones first, and
 * it did it silently: the pill just said "B or better" and the list was
 * shorter (UX review, 2026-09-09). The switch is there for anyone who wants
 * only rows we can actually vouch for.
 */
export function meetsGradeFloor(
  grade: MatchupGrade | null | undefined,
  floor: MatchupGrade | null,
  includeUngraded = true,
): boolean {
  if (!floor) return true;
  if (!grade) return includeUngraded;
  return GRADE_ORDER.indexOf(grade) <= GRADE_ORDER.indexOf(floor);
}

/** Best to worst. The index IS the ordering, so nothing sorts on a letter. */
const GRADE_ORDER: MatchupGrade[] = [
  'A+', 'A', 'A-', 'B+', 'B', 'B-', 'C+', 'C', 'C-', 'D+', 'D', 'D-', 'F',
];

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

// ── Toughness for the sports with no matchup view ────────────────────────────
//
// Matt, 2026-09-09, asked to filter the board on how tough a spot is. That
// column existed for MLB and WNBA ONLY — `v_mlb_tonight_matchups` and
// `v_wnba_tonight_matchups` are the only two such views — so on the NFL board
// he was looking at, and on NCAAF and NBA, it was a column of dashes and a
// filter over it would have filtered nothing.
//
// The question those two views answer with a probable starter or a lineup, the
// rest answer with the OPPONENT'S DEFENCE, which we already store for the Teams
// board. Same A+..F scale and the same method as the anchors above: a z-score
// against a MEASURED median and an IQR-derived sigma, run through the normal
// CDF to a percentile. Never hand-set cliffs — that is what had the old
// three-tier column printing one colour four times in five.
//
// Measured 2026-09-09 against production, `team_stats_board(sport, season)`:
//
//   NFL   points allowed/G   n=32   p25 20.07  median 23.09  p75 25.06
//   NCAAF EPA/play allowed   n=136  p25 0.098  median 0.155  p75 0.203
//   NBA   defensive rating   n=30   p25 110.42 median 112.40 p75 115.55
//
// All three point the same way — a HIGHER number is a worse defence and so a
// FAVOURABLE spot for the player — so the percentile is used unflipped.
//
// NHL IS DELIBERATELY ABSENT: `team_stats_board('NHL', 2026)` returned zero
// rows on the day this was written, and an anchor invented for an empty table
// is a number nobody measured. It grades as null (a dash) until those rows
// exist, which is the honest answer and the one this file already gives for an
// unknown starter.
// `label` is what the cell prints; `spoken` is what VoiceOver says, for the
// same reason this file already turns "(R)" into "right-handed" — an
// abbreviation and a slash are read out as punctuation. `label` matches the
// Teams board's own wording for the identical number (teamStatCatalog), so one
// stat is not two idioms on one tab.
const DEFENCE_ANCHORS: Record<
  string,
  {
    key: string; median: number; sigma: number; dp: number;
    /** Column wording, matching teamStatCatalog for the same number. */
    label: string;
    /** The metric as a sentence, for the tooltip and for VoiceOver. */
    spoken: string;
    /** Sentence form for the cell's fact: "NE allows 17.9 pts/g". */
    verb: string;
    unit: string;
  }
> = {
  NFL: {
    key: 'points_against_pg', median: 23.085, sigma: 3.695, dp: 1,
    label: 'Allowed/G', spoken: 'points allowed per game', verb: 'allows', unit: 'pts/g',
  },
  NCAAF: {
    key: 'epa_def', median: 0.155, sigma: 0.0778, dp: 3,
    label: 'EPA/play Def', spoken: 'EPA per play allowed', verb: 'allows', unit: 'EPA/play',
  },
  NBA: {
    key: 'def_rating', median: 112.395, sigma: 3.807, dp: 1,
    label: 'Def Rtg', spoken: 'defensive rating', verb: '', unit: 'def rtg',
  },
};

/** Does this sport grade a spot off the opponent's defence? */
export function gradesOnDefence(sport: string): boolean {
  return sport in DEFENCE_ANCHORS;
}

/** How the grade is worded on screen, for the sports that use one. */
export function defenceMetricLabel(sport: string): string | null {
  return DEFENCE_ANCHORS[sport]?.label ?? null;
}

/** The same metric as a sentence, for the column's tooltip. */
export function defenceMetricSpoken(sport: string): string | null {
  return DEFENCE_ANCHORS[sport]?.spoken ?? null;
}

/**
 * A player's spot graded on the defence he faces.
 *
 * `opponent` is the other team's row from the Teams board read. Null in, null
 * grade out — an unknown defence is a dash, never a C, for the same reason a
 * missing starter is: grading an absent fact as average invents the one thing
 * the column exists to report.
 */
export function gradeOpponentDefence(
  sport: string,
  opponent: Record<string, unknown> | null | undefined,
  opponentTeam: string | null,
  /** The season the opponent's row is from — printed, never assumed. */
  season?: number | null,
): MatchupInfo | null {
  const anchor = DEFENCE_ANCHORS[sport];
  if (!anchor) return null;
  const value = opponent ? num(opponent[anchor.key] as number | string | null) : null;
  if (value == null) {
    return {
      grade: null,
      score: null,
      text: opponentTeam ? `vs ${opponentTeam}` : '',
      fact: null,
      row: {} as TonightMatchupRow,
    };
  }
  const score = normalCdf(z(value, anchor));
  const shown = value.toFixed(anchor.dp);
  // SUBJECT, then number, then the season it came from. MLB's version names a
  // person ("S. Gray 5.90 ERA") so its subject is obvious; a bare team-season
  // rate under a header reading "Tonight's matchup" can be taken for the
  // player's own number or for a projection of this game (UX review).
  const seasonNote = season != null ? ` (${season})` : '';
  const claim = [opponentTeam, anchor.verb, shown, anchor.unit].filter(Boolean).join(' ');
  return {
    grade: gradeFor(score),
    score,
    text: opponentTeam ? `vs ${opponentTeam} · ${claim}${seasonNote}` : `${claim}${seasonNote}`,
    // Spoken: words, not a slash. Same reason this file says "right-handed"
    // rather than "(R)".
    fact: `${opponentTeam ? `${opponentTeam} ` : ''}${shown} ${anchor.spoken}${seasonNote}`,
    row: {} as TonightMatchupRow,
  };
}
