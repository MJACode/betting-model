import type { TonightMatchupRow } from '@/types';

/**
 * Tonight-matchup helpers for the Stats tab.
 *
 * A leaderboard row is joined to tonight's slate by TEAM (the player's team
 * from the season/window totals). The matchup line answers "who do they face
 * tonight and is that a good spot?":
 *   - Batters   → the opposing probable starter's ERA (season, last-3 shown).
 *                 A bad pitcher (high ERA) is FAVORABLE for the hitter.
 *   - Pitchers  → the opposing lineup's wOBA + K% (weak, whiffy offense =
 *                 favorable).
 *   - WNBA      → the opposing team's defensive rating (higher = worse
 *                 defense = favorable for scorers).
 *
 * Thresholds are league-typical bands, not percentiles — simple and stable.
 */

export type MatchupTier = 'favorable' | 'neutral' | 'tough';

export interface MatchupInfo {
  tier: MatchupTier;
  /** e.g. "vs LAA · S. Gray 5.90 ERA (R)" */
  text: string;
  /**
   * The ONE fact the board's SPOT column carries under the opponent, short
   * enough for a ~68pt column: the opposing starter and his arm, the opposing
   * lineup's wOBA, the defence's rating.
   *
   * It IS the ERA, reversing a first pass that printed the arm instead. Three
   * things settled it: the tier colour is a 3-bucket step function with cliffs
   * at 4.60 and 3.40 and league-average starter ERA is ~4.10, so the colour
   * separates the tails while the number separates the middle, where most rows
   * live; handedness is un-actionable on a board that never shows the hitter's
   * bat side; and `text` — the only other carrier of the ERA — now reaches a
   * screen reader and nothing else, so dropping the number here removed it from
   * the product for every sighted user. Null when the feed has nothing.
   */
  detail: string | null;
  row: TonightMatchupRow;
}

const num = (v: number | string | null | undefined): number | null => {
  if (v == null) return null;
  const n = typeof v === 'number' ? v : parseFloat(v);
  return Number.isFinite(n) ? n : null;
};

/**
 * "Braxton Ashcraft" → "Ashcraft". The SPOT column has room for one word.
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
    // "TBD" only when the STARTER is unknown. A named starter with no ERA yet —
    // a call-up, a first start — is not an unknown opponent, and three letters
    // under "vs HOU" read as though the game itself were unsettled.
    return {
      tier: 'neutral',
      text: `vs ${m.opponent} · ${m.opp_starter_name ?? 'starter TBD'}`,
      detail: m.opp_starter_name ? `${lastName(m.opp_starter_name)}${hand}` : 'TBD',
      row: m,
    };
  }
  const tier: MatchupTier = era >= 4.6 ? 'favorable' : era <= 3.4 ? 'tough' : 'neutral';
  return {
    tier,
    text: `vs ${m.opponent} · ${shortName(m.opp_starter_name)} ${era.toFixed(2)} ERA${hand}`,
    detail: `${lastName(m.opp_starter_name)} ${era.toFixed(2)}`,
    row: m,
  };
}

/** Pitcher vs the opposing lineup: low wOBA / high K% = favorable. */
function gradePitcher(m: TonightMatchupRow): MatchupInfo {
  const woba = num(m.opp_team_woba);
  const kPct = num(m.opp_team_k_pct);
  if (woba == null && kPct == null) {
    return { tier: 'neutral', text: `vs ${m.opponent}`, detail: null, row: m };
  }
  let tier: MatchupTier = 'neutral';
  if ((woba != null && woba >= 0.33) || (kPct != null && kPct <= 0.19)) tier = 'tough';
  else if ((woba != null && woba <= 0.305) || (kPct != null && kPct >= 0.235)) tier = 'favorable';
  const bits: string[] = [];
  if (woba != null) bits.push(`${woba.toFixed(3).replace(/^0/, '')} wOBA`);
  if (kPct != null) bits.push(`${(kPct * 100).toFixed(1)}% K`);
  return {
    tier,
    text: `vs ${m.opponent} · ${bits.join(', ')}`,
    detail: woba != null ? `${woba.toFixed(3).replace(/^0/, '')} wOBA` : `${((kPct ?? 0) * 100).toFixed(0)}% K`,
    row: m,
  };
}

/** WNBA scorer vs the opposing defense: high def rating = favorable. */
function gradeWnba(m: TonightMatchupRow): MatchupInfo {
  const def = num(m.opp_def_rating);
  if (def == null) return { tier: 'neutral', text: `vs ${m.opponent}`, detail: null, row: m };
  const tier: MatchupTier = def >= 104 ? 'favorable' : def <= 98.5 ? 'tough' : 'neutral';
  return {
    tier,
    text: `vs ${m.opponent} · DefRtg ${def.toFixed(1)}`,
    detail: `${def.toFixed(1)} Def`,
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
