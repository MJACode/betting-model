/**
 * Everything the matchup page reads beyond the game's own lines, loaded as
 * INDEPENDENT sections — the same shape as hooks/useTeamDetail, for the same
 * reason: an empty injury report or a slow odds read must not cost the ranks.
 *
 * Plain `useEffect` (useSection), never `useFocusEffect`: the app-root rule in
 * .claude/rules/frontend.md is cheaper to follow than to reason about.
 *
 * Every read was sized on production 2026-11-23 before it shipped:
 *   team_stats_board('NBA', 2027) ......... 30 rows
 *   games, one team's last 10 finals ...... 10 rows
 *   team_period_results FG, one team ..... 10 rows (98 stored for BOS)
 *   games, two teams' meetings ............ 5 rows (16 stored for MIN/BKN)
 *   injury_status_current NBA ............. 104 rows (92 Out, 12 Day-To-Day)
 *   v_latest_odds_all_books, one game ..... ~40 rows
 */
import { useMemo, useState } from 'react';

import { useSection } from '@/hooks/useTeamDetail';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import {
  fetchGameLineRowsAllMarkets,
  fetchHeadToHead,
  fetchInjuryStatus,
  fetchTeamFullGameCovers,
  fetchTeamRecentGamesForSport,
  fetchTeamStats,
} from '@/lib/queries';
import { bestUnder, coverSummary, restDays, teamInjuries, type CoverRow } from '@/lib/gameMatchup';
import { buildTeamLineIndex } from '@/lib/statsOdds';
import { formFromGames, headToHead, summarizeForm, teamRanks } from '@/lib/teamDetail';
import type { Sport } from '@/hooks/useSportFilter';
import type { GameRow, InjuryStatusRow, OddsByBookRow, TeamStatsRow } from '@/types';

/** How many finished games the form and cover lines look back over. */
export const MATCHUP_FORM_GAMES = 10;
/** How many past meetings the head-to-head card lists. */
export const MATCHUP_MEETINGS = 5;

export function useMatchup(game: GameRow | null, enabled: boolean) {
  const { books, ready: booksReady } = usePreferredBooks();
  const [nonce, setNonce] = useState(0);
  const refresh = () => setNonce((n) => n + 1);

  const on = enabled && game != null && !!game.home_team && !!game.away_team;
  const sport = (game?.sport ?? 'NBA') as Sport;
  const away = game?.away_team ?? '';
  const home = game?.home_team ?? '';
  const date = game?.game_date ?? '';
  const season = game?.season ?? null;

  // The board's 30 rows: the league each rank is out of.
  const board = useSection<{ season: number | null; rows: TeamStatsRow[] }>(
    { season: null, rows: [] },
    on && season != null ? () => fetchTeamStats(sport, season) : null,
    [on, sport, season, nonce],
  );

  const awayRecent = useSection<GameRow[]>(
    [],
    on ? () => fetchTeamRecentGamesForSport(sport, away, date, MATCHUP_FORM_GAMES) : null,
    [on, sport, away, date, nonce],
  );
  const homeRecent = useSection<GameRow[]>(
    [],
    on ? () => fetchTeamRecentGamesForSport(sport, home, date, MATCHUP_FORM_GAMES) : null,
    [on, sport, home, date, nonce],
  );
  const awayCovers = useSection<CoverRow[]>(
    [],
    on ? () => fetchTeamFullGameCovers(sport, away, date, MATCHUP_FORM_GAMES) : null,
    [on, sport, away, date, nonce],
  );
  const homeCovers = useSection<CoverRow[]>(
    [],
    on ? () => fetchTeamFullGameCovers(sport, home, date, MATCHUP_FORM_GAMES) : null,
    [on, sport, home, date, nonce],
  );
  const meetings = useSection<GameRow[]>(
    [],
    on ? () => fetchHeadToHead(sport, away, home, MATCHUP_MEETINGS) : null,
    [on, sport, away, home, nonce],
  );
  const injuries = useSection<InjuryStatusRow[]>(
    [],
    on ? () => fetchInjuryStatus(sport) : null,
    [on, sport, nonce],
  );
  const lines = useSection<OddsByBookRow[]>(
    [],
    on && game ? () => fetchGameLineRowsAllMarkets(game.game_id) : null,
    [on, game?.game_id, nonce],
  );

  const ranks = useMemo(() => {
    const rows = board.data.rows;
    return {
      efficiency: { away: teamRanks(rows, away, sport, 'Efficiency'), home: teamRanks(rows, home, sport, 'Efficiency') },
      betting: { away: teamRanks(rows, away, sport, 'Betting'), home: teamRanks(rows, home, sport, 'Betting') },
    };
  }, [board.data.rows, away, home, sport]);

  const rowFor = (team: string) => board.data.rows.find((r) => r.team === team) ?? null;

  const form = useMemo(() => {
    const awayForm = formFromGames(awayRecent.data, away);
    const homeForm = formFromGames(homeRecent.data, home);
    return {
      away: summarizeForm(awayForm, MATCHUP_FORM_GAMES),
      home: summarizeForm(homeForm, MATCHUP_FORM_GAMES),
      // Newest finished game before this one: the rest count.
      awayRest: restDays(awayForm[0]?.date ?? null, date),
      homeRest: restDays(homeForm[0]?.date ?? null, date),
      awayCover: coverSummary(awayCovers.data, MATCHUP_FORM_GAMES),
      homeCover: coverSummary(homeCovers.data, MATCHUP_FORM_GAMES),
    };
  }, [awayRecent.data, homeRecent.data, awayCovers.data, homeCovers.data, away, home, date]);

  const h2h = useMemo(() => headToHead(meetings.data, away, home), [meetings.data, away, home]);

  const injured = useMemo(
    () => ({ away: teamInjuries(injuries.data, away), home: teamInjuries(injuries.data, home) }),
    [injuries.data, away, home],
  );

  // Best of the member's books, from each team's side, at one number per
  // market (lib/statsOdds). Waits on the stored book list so the default set
  // never shows for a frame (usePreferredBooks).
  const best = useMemo(() => {
    if (!game || !booksReady) return null;
    const games = [game];
    const ml = buildTeamLineIndex(lines.data, games, { market: 'h2h', books });
    const spread = buildTeamLineIndex(lines.data, games, { market: 'spreads', books });
    const over = buildTeamLineIndex(lines.data, games, { market: 'totals', books });
    return {
      awayMl: ml.get(away) ?? null,
      homeMl: ml.get(home) ?? null,
      awaySpread: spread.get(away) ?? null,
      homeSpread: spread.get(home) ?? null,
      // The over is the same quote from either side; the home key is used.
      over: over.get(home) ?? null,
      under: bestUnder(lines.data, game.game_id, books),
    };
  }, [game, booksReady, books, lines.data, away, home]);

  return {
    refresh,
    books,
    board,
    awayRow: rowFor(away),
    homeRow: rowFor(home),
    ranks,
    formLoading: awayRecent.loading || homeRecent.loading || awayCovers.loading || homeCovers.loading,
    formError: awayRecent.error ?? homeRecent.error ?? awayCovers.error ?? homeCovers.error,
    form,
    h2h,
    meetingsLoading: meetings.loading,
    meetingsError: meetings.error,
    injured,
    injuriesLoading: injuries.loading,
    injuriesError: injuries.error,
    best,
    linesLoading: lines.loading || !booksReady,
    linesError: lines.error,
  };
}
