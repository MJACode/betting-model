/**
 * Signals pick card copy (Designer Option 1, on the Option A structure).
 *
 * Pure — no React Native — so the card, VoiceOver and the verify script
 * share one sentence. The headline is the bet only, built from the pick's
 * side, line, market and teams. A stake suffix ("· 0.77u"), an opener age
 * ("· NEW 0m", "· up 5h", "· age unknown") and a parenthetical
 * ("Wind 14 mph, FD", "Opener -2 vs Pinnacle, fanatics", "(DK)") never
 * become the bet. "(Regulation)" and "(matchup)" stay.
 * A signed number uses U+2212; a hyphen inside a name
 * ("Louisiana-Monroe") stays a hyphen.
 *
 * The player name is the one token a prop has no column for. The card
 * passes it in. `label` is the stored pick_label, used only when those
 * fields cannot name the bet. The wind reason reads that label when the
 * weather row has no number.
 */

import { MINUS } from './format';

/** ASCII hyphen used as a minus sign → U+2212. Names with hyphens are left. */
export function trueMinus(text: string): string {
  return text.replace(/(^|[\s(])-(?=\d)/g, `$1${MINUS}`);
}

/**
 * The stat word a prop headline uses, keyed by the odds market. Plain words
 * ("Tackles + Assists", "Three-pointers", "Points + Rebounds + Assists"),
 * not the scorer's short forms, so the headline does not parse `pick_label`.
 */
const PROP_BET_STAT: Readonly<Record<string, string>> = {
  pitcher_strikeouts: 'Strikeouts',
  pitcher_hits_allowed: 'Hits',
  pitcher_earned_runs: 'Earned runs',
  pitcher_outs: 'Outs',
  pitcher_walks: 'Walks',
  batter_hits: 'Hits',
  batter_total_bases: 'Total bases',
  batter_home_runs: 'Home runs',
  batter_rbis: 'Runs batted in',
  batter_runs_scored: 'Runs',
  batter_stolen_bases: 'Stolen bases',
  batter_walks: 'Walks',
  player_points: 'Points',
  player_rebounds: 'Rebounds',
  player_assists: 'Assists',
  player_threes: 'Three-pointers',
  player_points_rebounds_assists: 'Points + Rebounds + Assists',
  player_steals: 'Steals',
  player_blocks: 'Blocks',
  player_blocks_steals: 'Blocks + Steals',
  player_rebounds_assists: 'Rebounds + Assists',
  player_turnovers: 'Turnovers',
  player_double_double: 'Double-double',
  player_pass_yds: 'Pass yards',
  player_pass_attempts: 'Pass attempts',
  player_pass_completions: 'Completions',
  player_pass_tds: 'Pass touchdowns',
  player_rush_yds: 'Rush yards',
  player_rush_attempts: 'Carries',
  player_reception_yds: 'Receiving yards',
  player_receptions: 'Receptions',
  player_rush_reception_yds: 'Rushing + receiving yards',
  player_anytime_td: 'Anytime TD',
  player_tackles_assists: 'Tackles + Assists',
  player_sacks: 'Sacks',
  player_blocked_shots: 'Blocked shots',
  player_total_saves: 'Saves',
  player_shots_on_goal: 'Shots on goal',
};

export interface SignalsBetFields {
  /** `home` / `away` / `over` / `under` / `draw`, or a side those five cannot
   * name (golf `yes`, a UFC method class). Anything else uses `label`. */
  side: string;
  line: number | string | null;
  /** Odds market (`totals`, `spreads`, `h2h`, `team_totals_home`, a prop key). */
  market: string | null;
  homeTeam?: string | null;
  awayTeam?: string | null;
  /** Prop player. Game markets leave this empty. */
  player?: string | null;
  /** Overrides `PROP_BET_STAT` when the market is not in that map.
   * A non-prop total appends it ("Under 2.5 Rounds"). */
  stat?: string | null;
  /** Stored `pick_label`. Fallback only — see `signalsLabelHeadline`. */
  label?: string | null;
}

const STRUCTURED_SIDES = new Set(['home', 'away', 'over', 'under', 'draw']);

/** Parentheticals that are the bet. Every other one is noise: a book code,
 * a full book name, the wind forecast, "no bet", or "live". */
const KEPT_PAREN = /^(regulation|matchup)$/i;

/**
 * Stake ("· 0.98u") and opener age ("· NEW 0m", "· up 5h", "· up 2d",
 * "· age unknown") sit at the end, in either order. Peel whichever is
 * last until neither remains.
 */
function stripTrailingLabelNoise(text: string): string {
  let prev = '';
  while (prev !== text) {
    prev = text;
    text = text
      .replace(/\s*·\s*\d+(?:\.\d+)?u\s*$/iu, '')
      .replace(/\s*·\s*NEW\s+\d+m\s*$/iu, '')
      .replace(/\s*·\s*up\s+\d+(?:\.\d+)?[hd]\s*$/iu, '')
      .replace(/\s*·\s*age unknown\s*$/iu, '');
  }
  return text;
}

/**
 * The stored label, with the stake, the opener age, and any parenthetical
 * that is not the bet taken off. Null when there is nothing left to show.
 */
export function signalsLabelHeadline(label: string | null | undefined): string | null {
  if (!label) return null;
  let text = stripTrailingLabelNoise(label.trim());
  let prev = '';
  while (prev !== text) {
    prev = text;
    text = text.replace(/\s*\(([^()]*)\)/g, (full, inner: string) =>
      KEPT_PAREN.test(inner.trim()) ? full : '');
  }
  text = stripTrailingLabelNoise(text).replace(/\s{2,}/g, ' ').trim();
  return text ? trueMinus(text) : null;
}

/** "Wind 14 mph" inside a stored label. The publisher rounds to an integer. */
function windMphFromLabel(label: string | null | undefined): number | null {
  if (!label) return null;
  const match = /Wind\s+(\d+(?:\.\d+)?)\s*mph/i.exec(label);
  return match ? finiteLine(match[1]) : null;
}

function finiteLine(line: number | string | null | undefined): number | null {
  if (line == null || line === '') return null;
  const n = typeof line === 'number' ? line : Number(line);
  return Number.isFinite(n) ? n : null;
}

/** Totals and props: 56 → "56", 43.5 → "43.5". Whole numbers drop the decimal. */
function totalNumber(line: number): string {
  const n = Math.round(line * 1000) / 1000;
  if (Object.is(n, -0) || n === 0) return '0';
  return String(n);
}

/**
 * Spreads: the pick's side, printed like `formatSideLine` — a whole number
 * stays whole (`+3`, `−7`), a tenth stays a tenth (`−7.5`). U+2212 for a minus.
 * Forcing `.0` made the lock disagree with the Now line on the same card.
 */
function spreadNumber(line: number, side: string, market: string): string {
  const shown = market.startsWith('spreads') && side === 'away' ? -line : line;
  const n = Object.is(shown, -0) ? 0 : shown;
  const body = String(Math.abs(n));
  if (n > 0) return `+${body}`;
  if (n < 0) return `${MINUS}${body}`;
  return body;
}

function isPropMarket(market: string | null, player: string | null): boolean {
  if (player) return true;
  return market != null && /^(player_|pitcher_|batter_)/.test(market);
}

/**
 * The bet the card headlines. "Under 56", "Sam Houston −7.5", "Sam Houston ML",
 * "Roquan Smith Under 9.5 Tackles + Assists". A first-five market keeps " F5". A team
 * total names the club the market belongs to and the market ("Boston Bruins Team
 * Total Over 3.5"), as DraftKings names it.
 * Regulation moneyline is "(Regulation)", not "ML" — it pays only on a
 * regulation win. Golf and UFC method of victory have no structured market,
 * so the stored label is the headline.
 */
export function signalsBetHeadline(fields: SignalsBetFields): string {
  const market = fields.market;
  const side = fields.side;
  const line = finiteLine(fields.line);
  const home = (fields.homeTeam ?? '').trim();
  const away = (fields.awayTeam ?? '').trim();
  const player = (fields.player ?? '').trim();
  const stored = signalsLabelHeadline(fields.label);
  const f5 = market != null && market.includes('1st_5');
  const team = side === 'away' ? away : home;
  const regulation = market != null && market.startsWith('h2h_3way');

  if (!STRUCTURED_SIDES.has(side)) {
    return stored ?? trueMinus(team || side);
  }

  let bet: string;
  let fromLabel = false;
  if (side === 'draw') {
    bet = regulation ? 'Draw (Regulation)' : 'Draw';
  } else if (market != null && market.startsWith('team_totals')) {
    const club = market === 'team_totals_away' ? away : home;
    const word = side === 'over' ? 'Over' : side === 'under' ? 'Under' : '';
    const num = line == null ? '' : totalNumber(line);
    bet = [club, 'Team Total', word, num].filter((part) => part.length > 0).join(' ');
  } else if (market != null && market.startsWith('spreads')) {
    const num = line == null ? '' : spreadNumber(line, side, market);
    bet = [team, num].filter((part) => part.length > 0).join(' ');
  } else if (regulation) {
    bet = team ? `${team} (Regulation)` : 'Regulation';
  } else if (
    market != null && market.startsWith('h2h')
    || (market == null && (side === 'home' || side === 'away') && !player)
  ) {
    bet = team ? `${team} ML` : 'ML';
  } else if (side === 'over' || side === 'under') {
    const word = side === 'over' ? 'Over' : 'Under';
    const prop = isPropMarket(market, player);
    const stat = (fields.stat ?? '').trim() || (prop && market ? PROP_BET_STAT[market] ?? '' : '');
    if (prop && market === 'player_anytime_td' && player) {
      bet = `${player} Anytime TD`;
    } else if (prop && (!player || !stat) && stored) {
      bet = stored;
      fromLabel = true;
    } else if (prop && market === 'player_anytime_td') {
      bet = stored ?? 'Anytime TD';
      fromLabel = stored != null;
    } else {
      const num = line == null ? '' : totalNumber(line);
      const subject = prop ? player : '';
      const extra = prop ? stat : (fields.stat ?? '').trim();
      bet = [subject, word, num, extra].filter((part) => part.length > 0).join(' ');
    }
  } else {
    bet = stored ?? (team || side);
    fromLabel = stored != null && bet === stored;
  }
  if (f5 && bet && !fromLabel) bet = `${bet} F5`;
  return fromLabel ? bet : trueMinus(bet);
}

/**
 * The short line under the headline. Wind totals name the forecast the bet
 * was taken at: "Wind 14 mph at kickoff". That number is the one in the
 * stored label. `windMph` is used only when the label has none. A missing
 * wind, and every other model, stay quiet — a reason is not invented, and
 * "N models agree" is not this line. There is no dome flag on an NFL
 * look-ahead row, so a dome does not get its own branch.
 */
export function signalsReasonLine(input: {
  modelId: string;
  windMph: number | string | null | undefined;
  label?: string | null;
}): string | null {
  if (input.modelId !== 'nfl_wind_totals') return null;
  const n = windMphFromLabel(input.label) ?? finiteLine(input.windMph ?? null);
  if (n == null) return null;
  return `Wind ${Math.round(n)} mph at kickoff`;
}

/**
 * Footer caption. `longName` is `modelLong` ("NFL Totals").
 * `when` is the existing timing label ("Posted 11:07 AM ET", "Locked …",
 * "Priced …"), or null when the card is not showing one.
 */
export function signalsModelCaption(longName: string, when: string | null | undefined): string {
  const name = `${longName.trim()} model`;
  const posted = (when ?? '').trim();
  return posted ? `${name} · ${posted}` : name;
}

/**
 * VoiceOver for the Option 1 card: the verdict (BET / AVOID / NEUTRAL),
 * the bet, the price and book, the game (teams, then time), the reason,
 * the three figures, the stake, the model, when it posted, then paused /
 * status / sharp / started. NONE is spoken as NEUTRAL.
 */
export function signalsCardSpeech(input: {
  verdict?: string | null;
  bet: string;
  price: string | null;
  reason: string | null;
  teams: string | null;
  time: string | null;
  edge: string | null;
  modelChance: string | null;
  expectedReturn: string | null;
  stake: string | null;
  modelName: string | null;
  posted: string | null;
  paused: string | null;
  gameStatus: string | null;
  sharp: string | null;
  started: string | null;
}): string {
  const parts = [
    input.verdict,
    input.bet,
    input.price,
    input.teams,
    input.time,
    input.reason,
    input.edge,
    input.modelChance,
    input.expectedReturn,
    input.stake,
    input.modelName,
    input.posted,
    input.paused,
    input.gameStatus,
    input.sharp,
    input.started,
  ];
  return parts.filter((p): p is string => Boolean(p && p.length > 0)).reduce((acc, part) => {
    if (acc.length === 0) return part;
    return acc.endsWith('.') ? `${acc} ${part}` : `${acc}. ${part}`;
  }, '');
}

/** "−110 MGM" — the decision price and the book that price came from. */
export function signalsPriceText(priceText: string, book: string): string {
  return `${trueMinus(priceText)} ${book}`.trim();
}

/**
 * Resting sportsbook control (Matt approved 2026-10-27).
 * "Best DK −115" when several books are bettable (`best`).
 * "Bet FD −105" when one book is bettable.
 * "Open DK" when there is no price — never a made-up number.
 * No "now". The line stays in the hero: `lineText` is ignored so this
 * control cannot repeat it.
 */
export function signalsCtaLabel(
  book: string,
  priceText: string | null,
  _lineText?: string | null,
  opts?: { best?: boolean },
): string {
  if (!priceText) return `Open ${book}`;
  const quote = `${book} ${trueMinus(priceText)}`;
  return opts?.best ? `Best ${quote}` : `Bet ${quote}`;
}

/**
 * The same control, as VoiceOver should say it. Full book name, no middle
 * dot: "Best, DraftKings, −115". `book` here is the spoken name. The line
 * is not spoken here; the hero's Now line carries it.
 */
export function signalsCtaSpeech(
  book: string,
  priceText: string | null,
  _lineText?: string | null,
  opts?: { best?: boolean },
): string {
  if (!priceText) return `Open ${book}`;
  return [opts?.best ? 'Best' : 'Bet', book, trueMinus(priceText)].join(', ');
}

/**
 * Clock for the compact line. `gameDayLabelET` is null on the ET day of the
 * game, so a today card stays "8:00 PM ET". A later day is "Sat 10/17 · 8:00
 * PM ET" — the Signals board mixes dates and has no day headers.
 */
export function signalsContextTime(
  day: string | null | undefined,
  clock: string | null | undefined,
): string {
  return [day, clock].filter((part): part is string => Boolean(part && part.length > 0)).join(' · ');
}

/**
 * The small line under the hero when the book's current line or price is
 * not the number the pick was written at. Null when nothing to show has
 * been passed, so the screen and VoiceOver stay quiet together.
 *
 * `line` is already the pick's side ("-8.5", "+3.5", "9") and is null when
 * the line has not moved. `price` is the current American. `priceDiffers`
 * is that price against the decision price. A line move names the book
 * first so the two numbers are not bare: "MGM line now −4.5 (−110)". A
 * price move with the same line is "MGM now (−105)". `book` is whatever
 * this surface uses (the short label on screen, the full name when
 * spoken) — the numbers are the same call either way.
 */
export function signalsNowLine(input: {
  line: string | null;
  price: string | null;
  priceDiffers: boolean;
  book: string;
}): string | null {
  if (input.price == null) return null;
  if (!input.line && !input.priceDiffers) return null;
  const price = `(${trueMinus(input.price)})`;
  const who = input.book ? `${input.book} ` : '';
  if (input.line) return `${who}line now ${trueMinus(input.line)} ${price}`;
  return `${who}now ${price}`;
}

/**
 * VoiceOver for the Signals hero. The 22pt number is the decision price, so
 * that is what is spoken, with the full book name — the same `signalsPriceText`
 * the screen uses, so the two cannot format the price differently. `now` is
 * the Now line the screen is showing (built by `signalsNowLine`); null when
 * the screen has none. The lock is this one price. Stale and untracked
 * cards stay on `heroPriceSpeech`.
 */
export function signalsHeroSpeech(input: {
  decisionPrice: string;
  book: string;
  now?: string | null;
}): string {
  const locked = signalsPriceText(input.decisionPrice, input.book);
  if (!input.now) return locked;
  return `${locked}. ${input.now}`;
}

/**
 * Team token for the compact line. Pro sports already store abbreviations.
 * NCAAF stores the school name; the registry abbreviation is used when we
 * have it. An unknown school stays the school name — a code is not invented.
 */
export function compactTeam(
  name: string,
  sport: string,
  abbrevs?: ReadonlyMap<string, string> | null,
): string {
  if (sport !== 'NCAAF') return name;
  const hit = abbrevs?.get(name)?.trim();
  return hit ? hit : name;
}

/** "WKU @ SHSU · NCAAF · 8:00 PM ET". Golf is the event. UFC uses "vs". */
export function signalsContextLine(input: {
  sport: string;
  away: string;
  home: string;
  timeLabel: string;
  abbrevs?: ReadonlyMap<string, string> | null;
}): string {
  const { sport } = input;
  const away = compactTeam(input.away, sport, input.abbrevs);
  const home = compactTeam(input.home, sport, input.abbrevs);
  let matchup = '';
  if (sport === 'GOLF' || !away || away === 'FIELD') matchup = home;
  else if (!home) matchup = away;
  else matchup = `${away} ${sport === 'UFC' ? 'vs' : '@'} ${home}`;
  return [matchup, sport, input.timeLabel].filter((part) => part.length > 0).join(' · ');
}

/** Full names, "at" / "versus", for the card's VoiceOver label. */
export function signalsTeamsSpeech(sport: string, away: string, home: string): string | null {
  if (sport === 'GOLF' || !away || away === 'FIELD') return home || null;
  if (!home) return away || null;
  return `${away} ${sport === 'UFC' ? 'versus' : 'at'} ${home}`;
}

export type SignalsStakeForm = 'bet-win' | 'risk-win';
export const SIGNALS_STAKE_FORM: SignalsStakeForm = 'bet-win';

/**
 * The Stake cell. Both figures are `stakeFor`'s: units to bet (`risk`) and
 * units to win (`win`), already formatted ("1.5u", "0.4u"). The word comes
 * from `SIGNALS_STAKE_FORM`. Never the "1.1u → 1u" arrow, never dollars.
 */
function stakeWord(): 'Bet' | 'Risk' {
  return SIGNALS_STAKE_FORM === 'risk-win' ? 'Risk' : 'Bet';
}

export function signalsStakeLine(riskUnits: string, winUnits: string): string {
  return `${stakeWord()} ${riskUnits} · Win ${winUnits}`;
}

/** "1u" → "1 unit". "0.4u" and "10u" stay plural. */
function unitsSpoken(shown: string): string {
  const spoken = shown.replace(/(\d)u\b/g, '$1 units');
  return spoken === '1 units' ? '1 unit' : spoken;
}

/** VoiceOver for the Stake cell. Same `SIGNALS_STAKE_FORM` as the line. */
export function signalsStakeSpeech(riskUnits: string, winUnits: string): string {
  return `${stakeWord()} ${unitsSpoken(riskUnits)}, win ${unitsSpoken(winUnits)}`;
}
