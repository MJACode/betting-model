/**
 * The NBA Stats tab's 1st Basket board (Matt, 2026-11-08). Pure on purpose:
 * scripts/verify_nba_first_basket.ts pins it without React.
 *
 * One card per game on the slate. Per team: the usual jumper and his tip
 * record, how often the team wins the tip, scores first (split by won / lost
 * tip) and gives up the first score. Per player: the likely first scorers,
 * ranked by how often each took his team's first shot.
 *
 * DEFINITIONS (Matt, 2026-11-08; the writer is data/ingestors/nba_first_basket.py):
 *   first basket  the game's first score of ANY kind, free throws included.
 *   first shot    the team's first field-goal attempt; Made is whether it went in.
 *   tip           the opening jump ball; the winner is the team that gained possession.
 * This season only, regular season. Every number is shown as "x of N" so the
 * sample is never hidden (UX research, 2026-11-08: about 9 games a team in
 * early November).
 */

/** v_nba_first_basket_team_season, one row per team. */
export interface NbaFbTeamRow {
  season: number;
  team: string;
  games: number;
  tip_games: number;
  tips_won: number;
  scored_first: number;
  scored_first_won_tip: number;
  lost_tip_games: number;
  scored_first_lost_tip: number;
  allowed_first: number;
  jumper_espn_id: number | null;
  jumper_name: string | null;
  jumper_jumps: number;
  jumper_jumps_won: number;
}

/** v_nba_first_basket_player_season, one row per player (latest team). */
export interface NbaFbPlayerRow {
  season: number;
  espn_id: number;
  name: string;
  team: string;
  games: number;
  starts: number;
  first_fga: number;
  first_fga_made: number;
  game_first_scores: number;
  team_first_scores: number;
  jumps: number;
  jumps_won: number;
  last_game_date: string;
}

export const NBA_FB_TEAM_COLUMNS =
  'season,team,games,tip_games,tips_won,scored_first,scored_first_won_tip,lost_tip_games,' +
  'scored_first_lost_tip,allowed_first,jumper_espn_id,jumper_name,jumper_jumps,jumper_jumps_won';

export const NBA_FB_PLAYER_COLUMNS =
  'season,espn_id,name,team,games,starts,first_fga,first_fga_made,game_first_scores,' +
  'team_first_scores,jumps,jumps_won,last_game_date';

/** How many candidates each team shows. Three fit a 320pt card (UX research). */
export const NBA_FB_CANDIDATES = 3;

const num = (v: unknown): number => {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
};

/** PostgREST returns bigint / count columns as strings on some paths. */
export function normalizeTeamRow(r: NbaFbTeamRow): NbaFbTeamRow {
  return {
    ...r,
    season: num(r.season),
    games: num(r.games),
    tip_games: num(r.tip_games),
    tips_won: num(r.tips_won),
    scored_first: num(r.scored_first),
    scored_first_won_tip: num(r.scored_first_won_tip),
    lost_tip_games: num(r.lost_tip_games),
    scored_first_lost_tip: num(r.scored_first_lost_tip),
    allowed_first: num(r.allowed_first),
    jumper_espn_id: r.jumper_espn_id == null ? null : num(r.jumper_espn_id),
    jumper_jumps: num(r.jumper_jumps),
    jumper_jumps_won: num(r.jumper_jumps_won),
  };
}

export function normalizePlayerRow(r: NbaFbPlayerRow): NbaFbPlayerRow {
  return {
    ...r,
    season: num(r.season),
    espn_id: num(r.espn_id),
    games: num(r.games),
    starts: num(r.starts),
    first_fga: num(r.first_fga),
    first_fga_made: num(r.first_fga_made),
    game_first_scores: num(r.game_first_scores),
    team_first_scores: num(r.team_first_scores),
    jumps: num(r.jumps),
    jumps_won: num(r.jumps_won),
  };
}

/** "6 of 9", or an em dash when there is nothing to count. */
export function ofN(x: number, n: number): string {
  return n > 0 ? `${x} of ${n}` : '—';
}

/** "6/9", the compact form for the 3-column candidate rows. */
export function slashN(x: number, n: number): string {
  return n > 0 ? `${x}/${n}` : '—';
}

/** "67%", rounded; null when n is 0. Shown only next to its "x of N". */
export function pctOf(x: number, n: number): string | null {
  return n > 0 ? `${Math.round((100 * x) / n)}%` : null;
}

/** "6 of 9 (67%)". */
export function ofNPct(x: number, n: number): string {
  const p = pctOf(x, n);
  return p ? `${ofN(x, n)} (${p})` : ofN(x, n);
}

/** One stat line of the team comparison: label, away value, home value. */
export interface FbCompareLine {
  key: string;
  label: string;
  away: string;
  home: string;
  /** Spoken form for VoiceOver, both teams. */
  a11y: string;
}

function teamValues(r: NbaFbTeamRow | null) {
  if (!r) {
    const dash = '—';
    return { jumper: dash, jumperTips: dash, tips: dash, first: dash, wonTip: dash, lostTip: dash, allows: dash };
  }
  return {
    jumper: r.jumper_name ?? '—',
    jumperTips: ofN(r.jumper_jumps_won, r.jumper_jumps),
    tips: ofNPct(r.tips_won, r.tip_games),
    first: ofNPct(r.scored_first, r.games),
    wonTip: ofN(r.scored_first_won_tip, r.tips_won),
    lostTip: ofN(r.scored_first_lost_tip, r.lost_tip_games),
    allows: ofNPct(r.allowed_first, r.games),
  };
}

/**
 * The team comparison, away first (the card reads AWAY @ HOME). A team with
 * no row yet (no game stored this season) shows dashes, never zeros.
 */
export function fbCompareLines(
  awayTeam: string,
  homeTeam: string,
  away: NbaFbTeamRow | null,
  home: NbaFbTeamRow | null,
): FbCompareLine[] {
  const a = teamValues(away);
  const h = teamValues(home);
  const spoken = (label: string, av: string, hv: string) =>
    `${label}: ${awayTeam} ${av}, ${homeTeam} ${hv}`;
  const line = (key: keyof typeof a, label: string): FbCompareLine => ({
    key,
    label,
    away: a[key],
    home: h[key],
    a11y: spoken(label, a[key], h[key]),
  });
  return [
    line('jumper', 'Usual jumper'),
    line('jumperTips', 'His tips won'),
    line('tips', 'Team won tip'),
    line('first', 'Scored first'),
    line('wonTip', 'After winning tip'),
    line('lostTip', 'After losing tip'),
    line('allows', 'Opponent scored first'),
  ];
}

/** One likely-first-scorer row. */
export interface FbCandidate {
  espnId: number;
  name: string;
  games: number;
  firstShot: string;
  made: string;
  firstBasket: string;
  a11y: string;
}

/**
 * A team's likely first scorers: players listed under this team, ranked by
 * how many of the team's first shots they took, then by first baskets, then
 * fewer games (the same count in fewer games is the higher rate), then name.
 * A player who has never taken a first shot or scored a first basket is left
 * out, so a thin team shows fewer than three rather than padding with zeros.
 */
export function fbCandidates(
  team: string,
  players: NbaFbPlayerRow[],
  n: number = NBA_FB_CANDIDATES,
): FbCandidate[] {
  return players
    .filter((p) => p.team === team && p.games > 0 && (p.first_fga > 0 || p.game_first_scores > 0))
    .sort(
      (x, y) =>
        y.first_fga - x.first_fga ||
        y.game_first_scores - x.game_first_scores ||
        x.games - y.games ||
        x.name.localeCompare(y.name),
    )
    .slice(0, n)
    .map((p) => ({
      espnId: p.espn_id,
      name: p.name,
      games: p.games,
      firstShot: slashN(p.first_fga, p.games),
      made: slashN(p.first_fga_made, p.first_fga),
      firstBasket: slashN(p.game_first_scores, p.games),
      a11y:
        `${p.name}, ${p.games} ${p.games === 1 ? 'game' : 'games'}. ` +
        `Took the team's first shot ${ofN(p.first_fga, p.games)}` +
        (p.first_fga > 0 ? `, made ${ofN(p.first_fga_made, p.first_fga)}` : '') +
        `. Scored the game's first basket ${ofN(p.game_first_scores, p.games)}.`,
    }));
}

/** The teams on the slate, for the server narrowing of both reads. */
export function fbSlateTeams(games: { home_team: string; away_team: string }[]): string[] {
  const s = new Set<string>();
  for (const g of games) {
    if (g.home_team) s.add(g.home_team);
    if (g.away_team) s.add(g.away_team);
  }
  return Array.from(s).sort();
}

/** The legend under the board. One string so the verify script can pin it. */
export const NBA_FB_LEGEND =
  'First basket is the game’s first score of any kind, free throws included. ' +
  'First shot is the team’s first field-goal attempt; Made is how often it went in. ' +
  'The tip goes to the team that gains possession. Players are ranked by how often they took ' +
  'their team’s first shot. This season, regular season, from play-by-play.';
