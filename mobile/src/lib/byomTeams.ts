/**
 * Current franchise names for the BYOM opponent picker.
 * Abbrevs match the facts tables (LA, WAS, LV, not the historical Odds API names).
 */

export interface ByomTeam {
  abbrev: string;
  name: string;
}

export const NFL_TEAMS: readonly ByomTeam[] = [
  { abbrev: 'ARI', name: 'Arizona Cardinals' },
  { abbrev: 'ATL', name: 'Atlanta Falcons' },
  { abbrev: 'BAL', name: 'Baltimore Ravens' },
  { abbrev: 'BUF', name: 'Buffalo Bills' },
  { abbrev: 'CAR', name: 'Carolina Panthers' },
  { abbrev: 'CHI', name: 'Chicago Bears' },
  { abbrev: 'CIN', name: 'Cincinnati Bengals' },
  { abbrev: 'CLE', name: 'Cleveland Browns' },
  { abbrev: 'DAL', name: 'Dallas Cowboys' },
  { abbrev: 'DEN', name: 'Denver Broncos' },
  { abbrev: 'DET', name: 'Detroit Lions' },
  { abbrev: 'GB', name: 'Green Bay Packers' },
  { abbrev: 'HOU', name: 'Houston Texans' },
  { abbrev: 'IND', name: 'Indianapolis Colts' },
  { abbrev: 'JAX', name: 'Jacksonville Jaguars' },
  { abbrev: 'KC', name: 'Kansas City Chiefs' },
  { abbrev: 'LV', name: 'Las Vegas Raiders' },
  { abbrev: 'LAC', name: 'Los Angeles Chargers' },
  { abbrev: 'LA', name: 'Los Angeles Rams' },
  { abbrev: 'MIA', name: 'Miami Dolphins' },
  { abbrev: 'MIN', name: 'Minnesota Vikings' },
  { abbrev: 'NE', name: 'New England Patriots' },
  { abbrev: 'NO', name: 'New Orleans Saints' },
  { abbrev: 'NYG', name: 'New York Giants' },
  { abbrev: 'NYJ', name: 'New York Jets' },
  { abbrev: 'PHI', name: 'Philadelphia Eagles' },
  { abbrev: 'PIT', name: 'Pittsburgh Steelers' },
  { abbrev: 'SF', name: 'San Francisco 49ers' },
  { abbrev: 'SEA', name: 'Seattle Seahawks' },
  { abbrev: 'TB', name: 'Tampa Bay Buccaneers' },
  { abbrev: 'TEN', name: 'Tennessee Titans' },
  { abbrev: 'WAS', name: 'Washington Commanders' },
];

export const NBA_TEAMS: readonly ByomTeam[] = [
  { abbrev: 'ATL', name: 'Atlanta Hawks' },
  { abbrev: 'BOS', name: 'Boston Celtics' },
  { abbrev: 'BKN', name: 'Brooklyn Nets' },
  { abbrev: 'CHA', name: 'Charlotte Hornets' },
  { abbrev: 'CHI', name: 'Chicago Bulls' },
  { abbrev: 'CLE', name: 'Cleveland Cavaliers' },
  { abbrev: 'DAL', name: 'Dallas Mavericks' },
  { abbrev: 'DEN', name: 'Denver Nuggets' },
  { abbrev: 'DET', name: 'Detroit Pistons' },
  { abbrev: 'GSW', name: 'Golden State Warriors' },
  { abbrev: 'HOU', name: 'Houston Rockets' },
  { abbrev: 'IND', name: 'Indiana Pacers' },
  { abbrev: 'LAC', name: 'LA Clippers' },
  { abbrev: 'LAL', name: 'Los Angeles Lakers' },
  { abbrev: 'MEM', name: 'Memphis Grizzlies' },
  { abbrev: 'MIA', name: 'Miami Heat' },
  { abbrev: 'MIL', name: 'Milwaukee Bucks' },
  { abbrev: 'MIN', name: 'Minnesota Timberwolves' },
  { abbrev: 'NOP', name: 'New Orleans Pelicans' },
  { abbrev: 'NYK', name: 'New York Knicks' },
  { abbrev: 'OKC', name: 'Oklahoma City Thunder' },
  { abbrev: 'ORL', name: 'Orlando Magic' },
  { abbrev: 'PHI', name: 'Philadelphia 76ers' },
  { abbrev: 'PHX', name: 'Phoenix Suns' },
  { abbrev: 'POR', name: 'Portland Trail Blazers' },
  { abbrev: 'SAC', name: 'Sacramento Kings' },
  { abbrev: 'SAS', name: 'San Antonio Spurs' },
  { abbrev: 'TOR', name: 'Toronto Raptors' },
  { abbrev: 'UTA', name: 'Utah Jazz' },
  { abbrev: 'WAS', name: 'Washington Wizards' },
];

export function teamsForSport(sport: 'NFL' | 'NBA'): readonly ByomTeam[] {
  return sport === 'NBA' ? NBA_TEAMS : NFL_TEAMS;
}

export function filterTeams(teams: readonly ByomTeam[], query: string): ByomTeam[] {
  const q = query.trim().toLowerCase();
  if (q === '') return [...teams];
  return teams.filter((team) =>
    team.abbrev.toLowerCase().includes(q) || team.name.toLowerCase().includes(q));
}
