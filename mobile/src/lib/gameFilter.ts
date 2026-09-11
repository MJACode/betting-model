/**
 * "Which games am I looking at?" — one selection, read by Picks and by Stats.
 *
 * Matt, 2026-09-09, from a competitor's filter sheet: *"incorporate these
 * filters for games on how to show the match ups and show bets for those games.
 * This should be on picks and stats filter."*
 *
 * The two tabs already had two different ways to say the same thing. Stats had
 * a "Playing today" chip — a whole slate, all or nothing — and Picks had no
 * game cut at all, so "show me the two teams playing tonight and every bet on
 * them" took a search box on one screen and was impossible on the other.
 *
 * This is the cut underneath both: a set of `game_id`s. Empty means every game,
 * which is what an unset filter has to mean — a filter that starts by hiding
 * everything is a broken screen, not a strict one.
 *
 * NOT PERSISTED, AND THAT IS THE POINT. A `game_id` names one fixture on one
 * date. Storing the selection would have last night's games filtering tonight's
 * board, and the failure is silent: the board renders empty and correct, and
 * nothing on screen says the reason is a filter from yesterday. `useSportFilter`
 * persists because a sport is durable; a slate is not. The selection is dropped
 * whenever the sport changes for the same reason.
 */

import { formatGameTimeET, liveSlateDatesET, todayET, weekdayShortET } from './format';
import type { GameRow } from '@/types';

export interface SelectableGame {
  gameId: string;
  /** "NE @ SEA" — the fixture, away side first, as every board writes it. */
  matchup: string;
  /** "8:20 PM ET", or "Sat 3:30 PM ET" when the game is not today. */
  when: string;
  /** Both teams, for the row's own filtering. */
  teams: string[];
  commenceTime: string | null;
  gameDate: string;
}

/**
 * The slate's games, oldest kickoff first, ready to render as rows.
 *
 * `sport` is filtered here rather than by the caller because `games` is the one
 * table every sport writes and a mixed-sport read is the normal case.
 *
 * UFC AND GOLF ARE EXCLUDED, deliberately. Their `games` row stores the two
 * FIGHTERS (or `FIELD`) in home_team/away_team — they are slots, not venues —
 * so "NE @ SEA" would render as "Jon Jones @ Tom Aspinall" for one bout and
 * the reverse for the other side of it. The same reason `SlateGame.isHome` is
 * nullable for those two sports.
 */
const NO_FIXTURE_SPORTS = new Set(['UFC', 'GOLF']);

export function selectableGames(
  games: GameRow[],
  sport: string,
  today: string,
): SelectableGame[] {
  if (NO_FIXTURE_SPORTS.has(sport)) return [];
  // A GAME KEEPS ITS KICKOFF'S DATE, so a 20:25 Sunday kickoff still running at
  // 00:30 ET is filed under yesterday — and a bare `>= today` drops it from the
  // list while the Live view is still showing its in-play picks. The floor is
  // the live window's earliest date, which is exactly what CLAUDE.md §1b and
  // tests/test_live_slate_midnight.py exist to enforce.
  const window = liveSlateDatesET();
  const floor = window.length > 0 ? window[window.length - 1]! : today;
  const from = floor < today ? floor : today;
  return games
    .filter((g) => g.sport === sport && !!g.game_date && g.game_date >= from)
    .map((g) => ({
      gameId: g.game_id,
      matchup: g.away_team && g.home_team ? `${g.away_team} @ ${g.home_team}` : g.game_id,
      when: gameWhen(g),
      teams: [g.away_team, g.home_team].filter((t): t is string => !!t),
      commenceTime: g.commence_time ?? null,
      gameDate: g.game_date,
    }))
    .sort((a, b) =>
      String(a.commenceTime ?? a.gameDate).localeCompare(String(b.commenceTime ?? b.gameDate)),
    );
}

/**
 * "8:20 PM ET" today, "SAT 3:30 PM ET" on any other day.
 *
 * Both halves come from lib/format, and the weekday from the KICKOFF rather
 * than from `game_date`: a game keeps its kickoff's date, so a late start is
 * still filed under yesterday after midnight and the two would disagree.
 * `weekdayShortET` returns null for today, which is the "no prefix" case.
 */
function gameWhen(g: GameRow): string {
  const time = g.commence_time ? formatGameTimeET(g.commence_time) : '';
  // The DAY falls back to `game_date` when the feed has not written a kickoff
  // yet. Deriving it from `commence_time` alone returned null there, and the
  // `?? 'Today'` fallback then labelled a Sunday fixture "Today" — a wrong fact
  // in the one control whose job is telling a multi-day slate apart.
  const day = weekdayShortET(g.commence_time) ?? weekdayShortET(`${g.game_date}T12:00:00Z`);
  if (!time) return day ?? (g.game_date === todayET() ? 'Today' : g.game_date);
  return day ? `${day} ${time}` : time;
}

/**
 * Is this row in the selection?
 *
 * EMPTY IS EVERYTHING. Both callers rely on it: the sheet opens with nothing
 * ticked and the board must be whole, and clearing the last game must restore
 * the board rather than empty it.
 */
export function isGameSelected(gameId: string | null | undefined, selected: Set<string>): boolean {
  if (selected.size === 0) return true;
  return !!gameId && selected.has(gameId);
}

/**
 * The TEAMS a selection covers, for the surfaces that match on team rather
 * than on game_id.
 *
 * The Stats leaderboard is one of them — its rows carry a team, never a game —
 * so the selection has to be translated before it can filter them. Null for an
 * empty selection, matching `slateTeams`' own convention so the two compose.
 */
export function selectedTeams(
  games: SelectableGame[],
  selected: Set<string>,
): string[] | null {
  if (selected.size === 0) return null;
  const teams = new Set<string>();
  for (const g of games) if (selected.has(g.gameId)) for (const t of g.teams) teams.add(t);
  return teams.size > 0 ? Array.from(teams) : null;
}

/** "2 games" / "NE @ SEA" / "All games" — the collapsed row's summary. */
export function gameFilterSummary(
  games: SelectableGame[],
  selected: Set<string>,
): string {
  if (selected.size === 0) return 'All games';
  if (selected.size === 1) {
    const one = games.find((g) => selected.has(g.gameId));
    if (!one) return '1 game';
    // Bounded: this string becomes a pill label, and an NCAAF matchup is two
    // CFBD school names ("Louisiana-Monroe @ Northwestern State").
    return one.matchup.length > 24 ? '1 game' : one.matchup;
  }
  return `${selected.size} games`;
}

/**
 * Drop ids that are not on the current slate.
 *
 * Called whenever the slate is re-read. A selection outlives the games it was
 * made from — the day rolls over, the sport changes, a postponed game leaves
 * the window — and a stale id filters the board to nothing while every control
 * still says a game is selected. Pruning turns that into "All games", which is
 * wrong in the harmless direction.
 */
export function pruneSelection(selected: Set<string>, games: SelectableGame[]): Set<string> {
  if (selected.size === 0) return selected;
  const live = new Set(games.map((g) => g.gameId));
  const kept = new Set<string>();
  for (const id of selected) if (live.has(id)) kept.add(id);
  return kept.size === selected.size ? selected : kept;
}
