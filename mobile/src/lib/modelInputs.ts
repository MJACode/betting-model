/**
 * What the built-in models look at, per sport — the plain-language copy behind
 * the "What these models look at" card on the Models tab.
 *
 * This is a DESCRIPTION of the feature lists in the backend, not a mirror of
 * them: `features/feature_engine.py` (game models), `features/prop_feature_engine.py`
 * (MLB props), `features/{nba,wnba}_prop_feature_engine.py`,
 * `features/ufc_feature_engine.py`, `features/golf_feature_engine.py`,
 * `features/live_game_features.py` (MLB live), `ncaaf_live/serve.py` (NCAAF live),
 * the NFL card rules in `docs/sports/nfl.md`, and the market-relative prop rule
 * in `models/market_relative.py`. When a feature list changes, this copy is the
 * user-facing half of that change and moves with it.
 *
 * Two things this copy must never do:
 *   - name a raw feature (`d_starter_era`) or a model id — users see markets and
 *     plain words, never column names (UX_REVIEW §7);
 *   - describe the platform as paper trading (CLAUDE.md §2).
 *
 * Every entry ends on the same point: these inputs set the model's PROBABILITY;
 * the pick is still decided against DraftKings' line (CLAUDE.md §6). Line
 * movement and public-betting splits are shown beside a pick but are NOT model
 * inputs, so they are deliberately absent here.
 */

import type { Sport } from '@/hooks/useSportFilter';

export interface InputGroup {
  /** Short plain-language heading, e.g. "Starting pitchers". */
  label: string;
  /** The data elements in that group, as short chips. */
  items: string[];
}

export interface SportModelInputs {
  /** One sentence shown while the card is collapsed. */
  headline: string;
  groups: InputGroup[];
  /** Where the data comes from — shown as a footnote when expanded. */
  sources: string[];
}

/** The closing line every sport shares, so it cannot drift into eight phrasings. */
export const MODEL_INPUTS_DECIDES =
  'These inputs set the model’s probability. Every pick is still decided against the DraftKings line — that is where the edge comes from.';

export const MODEL_INPUTS_BY_SPORT: Record<Sport, SportModelInputs> = {
  MLB: {
    headline:
      'Starting pitchers, lineups, bullpen fatigue, weather and park, injuries, the umpire, and each player’s recent form.',
    groups: [
      {
        label: 'Starting pitchers',
        items: [
          'ERA, K/9, BB/9, WHIP',
          'Last 3 starts',
          'Statcast whiff %, K %, xERA',
          'Fastball velocity',
          'Listed starter scratched',
        ],
      },
      {
        label: 'Lineups and hitting',
        items: [
          'Team wOBA, wRC+, OPS, ISO',
          'Team K % and walk %',
          'Runs scored last 5 and 10',
          'Batting-order slot',
          'Confirmed lineup (props)',
          'Lefty / righty matchup',
        ],
      },
      {
        label: 'Bullpen',
        items: ['Bullpen ERA', 'Relief innings last 1 and 3 days'],
      },
      {
        label: 'Weather and park',
        items: ['Wind blowing out or in', 'Temperature', 'Dome or roof closed', 'Park factor'],
      },
      {
        label: 'Injuries',
        items: ['Active injuries', 'Players returning from the IL', 'Opponent injuries'],
      },
      {
        label: 'Umpire',
        items: ['Home-plate umpire strikeout tendency', 'Walk-zone tendency'],
      },
      {
        label: 'Record and form',
        items: ['Win %', 'Run differential', 'Early season (fewer than 10 games)'],
      },
      {
        label: 'Player form (props)',
        items: [
          'Last 3, 5, 10 and 20 games',
          'Season average',
          'Hot / cold trend',
          'Statcast xBA, xSLG, barrel %, hard-hit %',
          'Sprint speed',
          'Opponent pitching quality',
        ],
      },
      {
        label: 'In-game (live totals)',
        items: ['Inning, outs, runners on', 'Score so far', 'Half-innings left', 'Pregame pitching context'],
      },
      {
        label: 'Market',
        items: ['DraftKings total (totals model)', 'DraftKings runline (runline model)'],
      },
    ],
    sources: [
      'MLB Stats API',
      'Baseball Savant (Statcast)',
      'Open-Meteo weather',
      'ESPN injury reports',
      'Umpire assignments',
      'The Odds API (DraftKings lines)',
    ],
  },

  WNBA: {
    headline:
      'Team efficiency and pace, scoring form, rest and back-to-backs, injuries, and each player’s minutes and recent production.',
    groups: [
      {
        label: 'Team efficiency',
        items: [
          'Offensive, defensive and net rating',
          'Pace',
          'eFG %, 3P %, FT %',
          'Rebounds and assists per game',
          'Turnover %',
        ],
      },
      {
        label: 'Scoring form',
        items: ['Points for and against per game', 'Last 3 and 5 games'],
      },
      {
        label: 'Schedule',
        items: ['Rest days', 'Back-to-back'],
      },
      {
        label: 'Injuries',
        items: ['Active injuries', 'Players returning'],
      },
      {
        label: 'Record and form',
        items: ['Win %', 'Point differential', 'Early season (fewer than 10 games)'],
      },
      {
        label: 'Player form (props)',
        items: [
          'Minutes last 3 and 5, season',
          'Starter or bench',
          'The stat last 3, 5, 10 games and season',
          'Hot / cold trend',
          'Opponent defensive rating and pace',
          'Home or away, rest days',
        ],
      },
      {
        label: 'Market-relative props',
        items: [
          'Pinnacle’s price on the same line, vig removed',
          'Retail book’s price on that line',
          'Points, rebounds and assists only',
        ],
      },
    ],
    sources: [
      'stats.nba.com',
      'ESPN box scores and injury reports',
      'The Odds API (DraftKings and Pinnacle lines)',
    ],
  },

  NBA: {
    headline:
      'Team efficiency and pace, scoring form, rest and back-to-backs, injuries, and each player’s minutes and recent production.',
    groups: [
      {
        label: 'Team efficiency',
        items: [
          'Offensive, defensive and net rating',
          'Pace',
          'eFG %, 3P %, FT %',
          'Rebounds and assists per game',
          'Turnover %',
        ],
      },
      {
        label: 'Scoring form',
        items: ['Points for and against per game', 'Last 3 and 5 games'],
      },
      {
        label: 'Schedule',
        items: ['Rest days', 'Back-to-back'],
      },
      {
        label: 'Injuries',
        items: ['Active injuries', 'Players returning'],
      },
      {
        label: 'Record and form',
        items: ['Win %', 'Point differential', 'Early season (fewer than 10 games)'],
      },
      {
        label: 'Player form (props)',
        items: [
          'Minutes last 3 and 5, season',
          'Starter or bench',
          'The stat last 3, 5, 10 games and season',
          'Hot / cold trend',
          'Opponent defensive rating and pace',
          'Home or away, rest days',
          'Double-double rate (double-double market)',
        ],
      },
      {
        label: 'Market',
        items: ['DraftKings total (totals model)', 'DraftKings spread (spread model)'],
      },
    ],
    sources: ['stats.nba.com', 'ESPN injury reports', 'The Odds API (DraftKings lines)'],
  },

  NHL: {
    headline:
      'Goal scoring and shot share, special teams, the starting goalies, injuries, and home / away splits.',
    groups: [
      {
        label: 'Scoring and shot share',
        items: ['Goals for and against per game', 'Last 5 and 10 games', 'Corsi (shot-attempt share)'],
      },
      {
        label: 'Special teams',
        items: ['Power-play %', 'Penalty-kill %'],
      },
      {
        label: 'Goalies',
        items: ['Season save %', 'Goals-against average', 'Goals saved above average', 'Starting goalie out'],
      },
      {
        label: 'Home / away',
        items: ['Home team’s scoring at home', 'Road team’s scoring on the road'],
      },
      {
        label: 'Injuries',
        items: ['Active injuries', 'Players returning'],
      },
      {
        label: 'Record and form',
        items: ['Win %', 'Goal differential', 'Early season (fewer than 10 games)'],
      },
      {
        label: 'Market',
        items: ['DraftKings total (totals model)', 'DraftKings puck line (puck-line model)'],
      },
    ],
    sources: ['NHL API', 'ESPN injury reports', 'The Odds API (DraftKings lines)'],
  },

  UFC: {
    headline:
      'Each fighter’s record and finishing rates, striking and grappling numbers, age, reach and layoff, and whether the bout is five rounds.',
    groups: [
      {
        label: 'Record and finishes',
        items: ['Career win %', 'Win streak', 'UFC experience', 'KO, submission and decision rates', 'Average fight length'],
      },
      {
        label: 'Striking',
        items: ['Strikes landed and absorbed per minute', 'Striking accuracy', 'Striking defence'],
      },
      {
        label: 'Grappling',
        items: ['Takedowns per fight', 'Takedown accuracy and defence', 'Submission attempts'],
      },
      {
        label: 'Physical and schedule',
        items: ['Age', 'Height and reach', 'Stance matchup', 'Days since last fight'],
      },
      {
        label: 'Bout',
        items: ['Three or five rounds', 'DraftKings round total (rounds model only)', 'At least 3 prior UFC fights each'],
      },
    ],
    sources: ['UFCStats fight records', 'The Odds API (DraftKings lines)'],
  },

  GOLF: {
    headline:
      'Strokes gained by part of the game, recent finishes, course history, the strength of the field, and time since the last start.',
    groups: [
      {
        label: 'Strokes gained',
        items: ['Total, last 8 and 24 rounds', 'Off the tee', 'Approach', 'Around the green', 'Putting', 'Recent form vs baseline'],
      },
      {
        label: 'Results',
        items: ['Average finish last 5 and 10', 'Made-cut rate last 10', 'Rounds played last 90 days'],
      },
      {
        label: 'Course and field',
        items: ['Strokes gained at this event in prior years', 'Rounds played here', 'Field strength'],
      },
      {
        label: 'Schedule',
        items: ['Days since last event', 'At least 20 measured rounds'],
      },
      {
        label: 'Matchups',
        items: ['The difference between the two players on every input above'],
      },
    ],
    sources: ['DataGolf rounds, fields and DraftKings odds'],
  },

  NFL: {
    headline:
      'Forecast wind at kickoff for totals, Pinnacle versus a soft book’s spread for openers, and Pinnacle’s vig-free price for player props.',
    groups: [
      {
        label: 'Wind totals',
        items: [
          'Forecast wind at kickoff (issued 1–4 days out)',
          'Outdoor stadiums only',
          'The total at every book, vig removed',
          'Fires at 11 mph and up, under only',
        ],
      },
      {
        label: 'Opener spread',
        items: [
          'Pinnacle’s spread',
          'A soft book’s spread that lags it by a point or more',
          '2 to 7 days before kickoff',
          'Locks at the first qualifying number',
        ],
      },
      {
        label: 'Player props',
        items: [
          'Pinnacle’s price on the same line, vig removed',
          'Retail book’s price on that line',
          'Only equal lines are compared',
        ],
      },
    ],
    sources: [
      'Open-Meteo forecasts',
      'The Odds API (Pinnacle, DraftKings and the soft books)',
      'nflverse schedule and results',
    ],
  },

  NCAAF: {
    headline:
      'Program ratings, efficiency and tempo, the venue and weather for totals, two books’ opening spreads, and live score and clock in-game.',
    groups: [
      {
        label: 'Totals rule',
        items: [
          'Points for and against',
          'Plays per game (tempo)',
          'EPA per play, offense and defense',
          'SP+ offense and defense',
          'Week, neutral site, conference game',
          'Elevation, dome, grass',
          'Forecast temperature, wind, rain',
          'Fires only 8+ points off the DraftKings total',
        ],
      },
      {
        label: 'Opener spread',
        items: [
          'Bovada’s opening spread',
          'DraftKings’ opening spread, still on its opener',
          'Both captured within 90 minutes',
          'Disagree by 1+ point (2.5+ for high conviction)',
        ],
      },
      {
        label: 'In-game (live)',
        items: [
          'Score, quarter and clock',
          'Possession, down, distance, field position',
          'Timeouts left',
          'Pass rate so far',
          'Pregame spread and total',
          'Wind and dome',
        ],
      },
    ],
    sources: [
      'CollegeFootballData',
      'Open-Meteo weather',
      'ESPN live scoreboard',
      'The Odds API (DraftKings and Bovada lines)',
    ],
  },
};

export function modelInputsForSport(sport: Sport): SportModelInputs {
  return MODEL_INPUTS_BY_SPORT[sport];
}
