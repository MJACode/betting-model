/**
 * What the Stats tab's Teams board shows, per sport, and what each number
 * means to someone about to bet.
 *
 * Three groups, in this order, and the order is the point:
 *
 *  1. EFFICIENCY — how well a team plays, adjusted for pace, ballpark or
 *     opponent where the source allows. These are the numbers that say the
 *     most about the NEXT game, so they lead.
 *
 *  2. RECORD — wins, losses, scoring and (NFL) raw yardage. Context: the
 *     market already prices it in. Scored/Allowed/Margin per game moved here
 *     from Efficiency (Matt, 2026-11-03) because they are not adjusted for
 *     anything, and NFL pass/rush yards per game because they are VOLUME,
 *     which follows the score (a trailing team throws, a leading team runs).
 *
 *  3. BETTING — ATS, over/under, favourite/dog, home/away and rest splits.
 *     They describe how a team did against past lines, not how it will do
 *     against the next one, and every explanation says so.
 *
 * EVERY STAT CARRIES A ONE-LINE `hint` (always on screen) AND AN `explain`
 * (behind "Details"): what it is, what's good, how to use it for a bet, what
 * to watch for (Matt, 2026-11-03: "explain each data field ... and how to use
 * it"; casual bettors, but serious ones). No copy here states a number the
 * repo has not established — "100 is average" is the definition of wRC+, not
 * a measurement, and break-even at -110 is arithmetic (110 / 210).
 *
 * MLB and NHL "spreads" are the run line and puck line (±1.5), so their
 * betting labels say so (`bySport`).
 *
 * Deliberately NOT here:
 *  - NHL expected-goals share (xGF%). The free NHL API does not expose it and
 *    our column is 0% populated, so it would be a column of dashes.
 *  - NFL DVOA / PFF grades. Proprietary and licensed; EPA per play needs NFL
 *    play-by-play we do not ingest, so NFL efficiency is yards-per-play.
 *  - MLB rest splits. Baseball plays daily, so a rest-day cut is noise.
 *  - Sample counts for the favourite/dog splits. team_stats_board does not
 *    return them, so those two cannot apply the small-sample rule yet.
 */
import type { Sport } from '@/hooks/useSportFilter';
import type { TeamStatsRow } from '@/types';

export type TeamStatGroup = 'Efficiency' | 'Record' | 'Betting';

export const TEAM_GROUP_ORDER: TeamStatGroup[] = ['Efficiency', 'Record', 'Betting'];

/** One line under the group tabs: what this kind of number is for. */
export const TEAM_GROUP_INTRO: Record<TeamStatGroup, string> = {
  Efficiency: 'How well a team actually plays. The best guide to the next game.',
  Record: 'Wins, losses and scoring. Useful context, but the line already knows it.',
  Betting: 'How a team did against past lines. It describes, it doesn’t predict.',
};

/** How a value is rendered. `pct3` is a 0..1 rate shown as a percentage. */
export type TeamStatFormat = 'int' | 'dec1' | 'dec2' | 'dec3' | 'pct3';

/** The "Details" sheet for one stat. */
export interface TeamStatExplain {
  /** What the number measures, in plain words. */
  what: string;
  /** Which way is good, and where average sits when that is definitional. */
  good: string;
  /** How a bettor uses it. */
  use: string;
  /** The trap, if there is one worth naming. */
  watch?: string;
}

/** The headed sections the Details sheet renders, in order. */
export function explainSections(e: TeamStatExplain): { heading: string; text: string }[] {
  const out = [
    { heading: 'What it is', text: e.what },
    { heading: 'What’s good', text: e.good },
    { heading: 'How to use it', text: e.use },
  ];
  if (e.watch) out.push({ heading: 'Watch out for', text: e.watch });
  return out;
}

type SportCopy = Partial<Pick<TeamStatDef, 'label' | 'hint' | 'explain'>>;

export interface TeamStatDef {
  key: keyof TeamStatsRow;
  label: string;
  group: TeamStatGroup;
  /** Sports that show this stat. */
  sports: Sport[];
  format: TeamStatFormat;
  /**
   * Which end of the league is good, for the rank tint. `null` means neither
   * (pace is a style, not a virtue) — those render uncoloured.
   */
  better: 'high' | 'low' | null;
  /**
   * Companion win/loss columns, rendered under the value as "67-42".
   * Present on the betting splits so a 60% ATS mark can't hide a 3-2 sample.
   */
  record?: { w: keyof TeamStatsRow; l: keyof TeamStatsRow; p?: keyof TeamStatsRow };
  /**
   * Columns summed for the games behind a split, so one built on 4 games
   * reads as 4 games (lib/teamBoard MIN_SPLIT_SAMPLE). Home/away use the
   * team's decided home/away games — every graded split game is one of them.
   */
  sample?: (keyof TeamStatsRow)[];
  /** One line, always on screen above the list. */
  hint: string;
  /** Behind "Details". */
  explain: TeamStatExplain;
  /** Per-sport wording (MLB's run line, NHL's puck line). */
  bySport?: Partial<Record<Sport, SportCopy>>;
}

const BALL: Sport[] = ['MLB', 'NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF'];
const HOOPS: Sport[] = ['NBA', 'WNBA'];
/** Sports where a rest-day split is meaningful (MLB plays daily). */
const RESTFUL: Sport[] = ['NBA', 'WNBA', 'NHL', 'NFL', 'NCAAF'];

const ATS_SAMPLE: (keyof TeamStatsRow)[] = ['ats_w', 'ats_l', 'ats_p'];
/** NBA's Betting numbers are counted from team_period_results (lib/teamPeriodSplits):
 *  which line each game is graded against, said once on the sheets that need it. */
const NBA_GRADED_LINE = 'Each game is graded against DraftKings’ last line before tip, or the other books’ median when DraftKings had none. The Period, Games and Side filters re-count it.';
const NBA_SPLIT_WATCH = 'A split of a split is a small sample. Under 10 games in a season view the board marks it “small sample” and does not colour it.';

/** The spread's name in each sport, for the betting copy. */
const RUN_LINE = 'the run line (±1.5 runs)';
const PUCK_LINE = 'the puck line (±1.5 goals)';
const PRICED_LINE_GOOD =
  'Higher means the team covers more often. Run and puck lines are usually priced well away from even money, so 50% is not break-even here — the price you get matters as much as the cover rate.';

export const TEAM_STAT_CATALOG: TeamStatDef[] = [
  // ── Efficiency ──────────────────────────────────────────────────────────
  // MLB
  {
    key: 'wrc_plus', label: 'wRC+', group: 'Efficiency', sports: ['MLB'], format: 'int', better: 'high',
    hint: 'Runs the lineup creates, adjusted for ballpark. 100 is league average.',
    explain: {
      what: 'Weighted Runs Created Plus: how much offense a lineup produces per plate appearance, adjusted for its ballpark and the league’s scoring level.',
      good: '100 is exactly league average. 110 is 10% better than average, 90 is 10% worse.',
      use: 'Compare the two lineups in a game. A big gap favours the better offense; two strong lineups point toward the over. Always check it against tonight’s starting pitchers.',
      watch: 'It is a season number. Injuries, trades and a hot or cold month take time to show up.',
    },
  },
  {
    key: 'ops', label: 'OPS', group: 'Efficiency', sports: ['MLB'], format: 'dec3', better: 'high',
    hint: 'On-base plus slugging: getting on base plus hitting for power.',
    explain: {
      what: 'On-base percentage plus slugging percentage, in one number.',
      good: 'Higher is better.',
      use: 'A quick read on lineup quality. To compare two teams, prefer wRC+.',
      watch: 'It is not adjusted for ballpark, so hitter-friendly parks inflate it.',
    },
  },
  {
    key: 'team_era', label: 'Team ERA', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low',
    hint: 'Earned runs allowed per nine innings, starters and bullpen together.',
    explain: {
      what: 'Earned runs the whole pitching staff allows per 9 innings.',
      good: 'Lower is better.',
      use: 'A season-long view of run prevention. For a single game the starting pitcher matters more than the staff number, so check who is pitching.',
      watch: 'Defense and ballpark affect it, and a few bad outings can move it a lot.',
    },
  },
  {
    key: 'bullpen_era', label: 'Bullpen ERA', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low',
    hint: 'ERA of the relief pitchers only.',
    explain: {
      what: 'Earned runs per 9 innings, relievers only.',
      good: 'Lower is better.',
      use: 'Relievers often pitch the last third of the game. A weak bullpen is a reason for caution backing that team on the full game, and can help the over, most of all when its starter tends to leave early.',
      watch: 'Bullpens change quickly with injuries and call-ups, and relief innings are few, so the number is jumpy.',
    },
  },
  {
    key: 'team_whip', label: 'WHIP', group: 'Efficiency', sports: ['MLB'], format: 'dec2', better: 'low',
    hint: 'Walks plus hits allowed per inning.',
    explain: {
      what: 'How many runners the pitching staff puts on base per inning.',
      good: 'Lower is better. More runners on base usually means more runs.',
      use: 'Read it beside ERA. A good ERA with a high WHIP means a staff has been escaping trouble, which is hard to keep doing.',
    },
  },
  // Basketball
  {
    key: 'net_rating', label: 'Net Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high',
    hint: 'Points scored minus allowed per 100 possessions.',
    explain: {
      what: 'A team’s scoring margin per 100 possessions, so fast and slow teams compare fairly.',
      good: 'Above 0 means the team outscores its opponents. Bigger is better.',
      use: 'The best single number for how good a team is. The gap between two teams’ Net Rtg is a rough sense of who should be favoured and by how much — set it beside the spread.',
      watch: 'Early in the season a couple of blowouts move it a lot, and an injury to a key player changes it fast.',
    },
  },
  {
    key: 'off_rating', label: 'Off Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high',
    hint: 'Points scored per 100 possessions.',
    explain: {
      what: 'How many points the offense scores per 100 possessions.',
      good: 'Higher is better.',
      use: 'A strong offense against a weak defense (high Def Rtg) points toward a higher team total or game total.',
    },
  },
  {
    key: 'def_rating', label: 'Def Rtg', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'low',
    hint: 'Points allowed per 100 possessions. Lower is better.',
    explain: {
      what: 'How many points the defense allows per 100 possessions.',
      good: 'Lower is better.',
      use: 'Pair it with the opponent’s Off Rtg. Two good defenses point toward the under.',
    },
  },
  {
    key: 'pace', label: 'Pace', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: null,
    hint: 'Possessions per game. Fast teams create more scoring chances.',
    explain: {
      what: 'How many possessions a team uses in a game.',
      good: 'Neither end is better. It is a style, so it is not coloured.',
      use: 'Mostly for totals. Two fast teams mean more possessions and usually more points; two slow teams, fewer. Combine it with Off and Def Rtg before judging a total.',
    },
  },
  {
    key: 'efg_pct', label: 'eFG%', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'high',
    hint: 'Shooting accuracy, with a made 3 counted as worth more than a 2.',
    explain: {
      what: 'Field goal percentage where a made 3-pointer counts as 1.5 makes, because it is worth 1.5 times as much.',
      good: 'Higher is better.',
      use: 'Shooting drives scoring more than anything else. A team shooting well above its usual level may cool off.',
      watch: 'Hot and cold shooting stretches are common; a few games can mislead.',
    },
  },
  {
    key: 'tov_pct', label: 'TOV%', group: 'Efficiency', sports: HOOPS, format: 'dec1', better: 'low',
    hint: 'Share of possessions that end in a turnover. Lower is better.',
    explain: {
      what: 'Turnovers per 100 possessions.',
      good: 'Lower is better.',
      use: 'Careless teams give away scoring chances. Against an opponent that forces turnovers, that costs them points.',
    },
  },
  // NHL
  {
    key: 'corsi_for_pct', label: 'Corsi%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high',
    hint: 'This team’s share of all shot attempts in its games.',
    explain: {
      what: 'Of every shot attempt by both teams — on goal, missed or blocked — the share this team took.',
      good: '50% is even. Above 50% means the team has the puck more and controls play.',
      use: 'It shows who is really driving games. A team winning a lot with a low Corsi% may be leaning on hot goaltending or shooting, which tends to fade; a team losing with a high Corsi% may be due to improve.',
      watch: 'Teams that are ahead often sit back, which lowers their number. It does not measure shot quality.',
    },
  },
  {
    key: 'pp_pct', label: 'PP%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high',
    hint: 'How often the power play scores.',
    explain: {
      what: 'Power-play goals divided by power-play chances.',
      good: 'Higher is better.',
      use: 'Matters most against teams that take a lot of penalties. A strong power play against a weak penalty kill helps that team and the over.',
      watch: 'Power-play chances are few, so it swings over short stretches.',
    },
  },
  {
    key: 'pk_pct', label: 'PK%', group: 'Efficiency', sports: ['NHL'], format: 'dec1', better: 'high',
    hint: 'How often the penalty kill stops the other team scoring.',
    explain: {
      what: 'The share of opponents’ power plays that end without a goal.',
      good: 'Higher is better.',
      use: 'The other half of special teams. A weak penalty kill against a strong power play is an edge for the team with the power play.',
      watch: 'Like PP%, it rests on few chances.',
    },
  },
  // College football
  {
    key: 'sp_overall', label: 'SP+', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: 'An opponent-adjusted rating of how good a team is.',
    explain: {
      what: 'Analyst Bill Connelly’s rating, built from efficiency and explosiveness and adjusted for the strength of each opponent.',
      good: '0 is an average FBS team; the number reads as points better or worse than average.',
      use: 'The difference between two teams’ SP+ is a rough expected margin on a neutral field. Compare it with the spread.',
      watch: 'Early in the season it leans on preseason expectations.',
    },
  },
  {
    key: 'epa_off', label: 'EPA/play Off', group: 'Efficiency', sports: ['NCAAF'], format: 'dec3', better: 'high',
    hint: 'Points the offense adds on a typical play.',
    explain: {
      what: 'Expected Points Added: how much each play changed the offense’s expected points, given down, distance and field position. This is the average per play.',
      good: 'Higher is better. Above 0 means the offense adds value on a typical play.',
      use: 'One of the strongest measures of offensive quality. Compare it with the opponent’s defensive EPA/play.',
      watch: 'It is not adjusted for opponent; check who they have played.',
    },
  },
  {
    key: 'epa_def', label: 'EPA/play Def', group: 'Efficiency', sports: ['NCAAF'], format: 'dec3', better: 'low',
    hint: 'Points the defense gives up on a typical play. Lower is better.',
    explain: {
      what: 'The EPA opponents gain per play against this defense.',
      good: 'Lower is better. Below 0 means opponents lose value on a typical play.',
      use: 'Set it against the opponent’s offensive EPA/play to see which side should win the matchup.',
      watch: 'It is not adjusted for opponent; check who they have played.',
    },
  },
  {
    key: 'success_off', label: 'Success% Off', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: 'Share of plays that keep the offense on schedule.',
    explain: {
      what: 'A play counts as a success when it gains enough for its down: half the yards needed on 1st down, 70% on 2nd, all of them on 3rd or 4th.',
      good: 'Higher is better.',
      use: 'It measures consistency. High success with low explosiveness is a team that grinds out drives; the reverse lives on big plays.',
    },
  },
  {
    key: 'success_def', label: 'Success% Def', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'low',
    hint: 'Share of opponents’ plays that stay on schedule. Lower is better.',
    explain: {
      what: 'The success rate opponents manage against this defense.',
      good: 'Lower is better.',
      use: 'A defense that keeps opponents off schedule forces long third downs and punts.',
    },
  },
  {
    key: 'explosiveness_off', label: 'Explosiveness', group: 'Efficiency', sports: ['NCAAF'], format: 'dec2', better: 'high',
    hint: 'How big the offense’s gains are when a play works.',
    explain: {
      what: 'The average EPA on the offense’s successful plays.',
      good: 'Higher is better.',
      use: 'Big-play offenses can cover large spreads quickly.',
      watch: 'Big plays come in bunches, so explosive teams are streakier than consistent ones.',
    },
  },
  {
    key: 'havoc_rate', label: 'Havoc%', group: 'Efficiency', sports: ['NCAAF'], format: 'dec1', better: 'high',
    hint: 'Share of plays where the defense makes a disruptive play.',
    explain: {
      what: 'The share of plays with a tackle for loss, forced fumble, interception or pass breakup.',
      good: 'Higher is better.',
      use: 'High-havoc defenses create turnovers and drive-killing losses. Against an offense that turns the ball over, that is an edge.',
    },
  },
  // NFL — yards-based, because we do not ingest NFL play-by-play for EPA.
  {
    key: 'yards_per_play', label: 'Yards/Play', group: 'Efficiency', sports: ['NFL'], format: 'dec2', better: 'high',
    hint: 'Average yards the offense gains per play.',
    explain: {
      what: 'Total offensive yards divided by offensive plays.',
      good: 'Higher is better.',
      use: 'A simple efficiency check that is not inflated by how many plays a team runs. Compare it between the two teams.',
      watch: 'It is not adjusted for opponent, and it ignores turnovers, penalties and red-zone finishing.',
    },
  },

  // ── Record ──────────────────────────────────────────────────────────────
  {
    key: 'win_pct', label: 'Win%', group: 'Record', sports: BALL, format: 'pct3', better: 'high',
    record: { w: 'wins', l: 'losses' },
    hint: 'Share of games won.',
    explain: {
      what: 'Wins divided by games decided.',
      good: 'Higher is better.',
      use: 'Good teams win, but the betting line already reflects it. Win% on its own will not find you value.',
      watch: 'Close games are partly luck. Margin/G is a better guide to how good a team is.',
    },
  },
  {
    key: 'point_diff_pg', label: 'Margin/G', group: 'Record', sports: BALL, format: 'dec2', better: 'high',
    hint: 'Average scoring margin per game.',
    explain: {
      what: 'Points scored minus points allowed, per game.',
      good: 'Above 0 means the team outscores opponents on average.',
      use: 'A better guide to team strength than win-loss, because close wins and losses are partly luck. A team with a winning record but a small margin may be overrated.',
      watch: 'It is not adjusted for opponent, and one blowout can skew it early.',
    },
    bySport: {
      MLB: { explain: { what: 'Runs scored minus runs allowed, per game.', good: 'Above 0 means the team outscores opponents on average.', use: 'A better guide to team strength than win-loss, because one-run games are partly luck. A team with a winning record but a small run margin may be overrated.', watch: 'It is not adjusted for opponent, and one blowout can skew it early.' } },
      NHL: { explain: { what: 'Goals scored minus goals allowed, per game.', good: 'Above 0 means the team outscores opponents on average.', use: 'A better guide to team strength than the standings, because one-goal and overtime games are partly luck.', watch: 'Goals are rare, so it is noisier than Corsi% over short stretches.' } },
    },
  },
  {
    key: 'points_for_pg', label: 'Scored/G', group: 'Record', sports: BALL, format: 'dec2', better: 'high',
    hint: 'Average points scored per game.',
    explain: {
      what: 'Points scored per game.',
      good: 'Higher is better.',
      use: 'A starting point for team totals and game totals. Compare it with the opponent’s Allowed/G.',
      watch: 'Not adjusted for opponent or pace.',
    },
    bySport: {
      MLB: { hint: 'Average runs scored per game.', explain: { what: 'Runs scored per game.', good: 'Higher is better.', use: 'A starting point for team totals and game totals. Compare it with the opponent’s Allowed/G and tonight’s starter.', watch: 'Not adjusted for ballpark or opponent.' } },
      NHL: { hint: 'Average goals scored per game.', explain: { what: 'Goals scored per game.', good: 'Higher is better.', use: 'A starting point for team totals and game totals. Compare it with the opponent’s Allowed/G and goalie.', watch: 'Not adjusted for opponent.' } },
    },
  },
  {
    key: 'points_against_pg', label: 'Allowed/G', group: 'Record', sports: BALL, format: 'dec2', better: 'low',
    hint: 'Average points allowed per game.',
    explain: {
      what: 'Points allowed per game.',
      good: 'Lower is better.',
      use: 'Pair it with the opponent’s Scored/G when looking at a total.',
      watch: 'Not adjusted for opponent or pace.',
    },
    bySport: {
      MLB: { hint: 'Average runs allowed per game.', explain: { what: 'Runs allowed per game.', good: 'Lower is better.', use: 'Pair it with the opponent’s Scored/G when looking at a total, and check the starter.', watch: 'Not adjusted for ballpark or opponent.' } },
      NHL: { hint: 'Average goals allowed per game.', explain: { what: 'Goals allowed per game.', good: 'Lower is better.', use: 'Pair it with the opponent’s Scored/G when looking at a total, and check who is in goal.', watch: 'Goaltending swings it a lot.' } },
    },
  },
  {
    key: 'pass_yards_pg', label: 'Pass Yds/G', group: 'Record', sports: ['NFL'], format: 'dec1', better: 'high',
    hint: 'Passing yards per game. Volume, not efficiency.',
    explain: {
      what: 'Total passing yards per game.',
      good: 'Higher means more passing, not necessarily better passing.',
      use: 'Useful context for passing props. Teams that trail throw more, so high passing yards can mean a team often plays from behind.',
      watch: 'To judge quality, use Yards/Play.',
    },
  },
  {
    key: 'rush_yards_pg', label: 'Rush Yds/G', group: 'Record', sports: ['NFL'], format: 'dec1', better: 'high',
    hint: 'Rushing yards per game. Volume, not efficiency.',
    explain: {
      what: 'Total rushing yards per game.',
      good: 'Higher means more running, not necessarily better running.',
      use: 'Useful context for rushing props. Teams that lead run more to use up the clock, so high rushing yards often follow winning rather than cause it.',
      watch: 'To judge quality, use Yards/Play.',
    },
  },
  {
    key: 'games_played', label: 'Games', group: 'Record', sports: BALL, format: 'int', better: null,
    hint: 'Games played this season.',
    explain: {
      what: 'How many games this season’s numbers are built on.',
      good: 'Neither. More games means every other number on the board is more reliable.',
      use: 'Check it first. With only a handful of games, treat every rate on the board as a rough early read.',
    },
  },

  // ── Betting ─────────────────────────────────────────────────────────────
  {
    key: 'ats_pct', label: 'ATS%', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    record: { w: 'ats_w', l: 'ats_l', p: 'ats_p' }, sample: ATS_SAMPLE,
    hint: 'How often the team covered the spread.',
    explain: {
      what: 'Against the spread: the share of games where the team beat the betting spread. Pushes are left out.',
      good: 'Above 50% means the team has done better than the market expected. At standard -110 odds a bettor needs about 52.4% to profit.',
      use: 'It tells you whether the market has been under- or overrating a team so far. Use it as a prompt to look closer, not a reason to bet.',
      watch: 'The line adjusts as a team surprises people, so past covers say little about the next one. Under 10 games the board marks it “small sample” and does not colour it.',
    },
    bySport: {
      MLB: {
        label: 'Run Line%', hint: 'How often the team covered the run line (±1.5 runs).',
        explain: {
          what: `How often the team covered ${RUN_LINE}: as the favourite it must win by 2 or more; as the underdog it covers by winning or losing by 1. Pushes cannot happen.`,
          good: PRICED_LINE_GOOD,
          use: 'Shows whether a team tends to win big or lose close. Read it with the prices on offer, not on its own.',
          watch: 'The line and price adjust as a team surprises people. Under 10 games the board marks it “small sample” and does not colour it.',
        },
      },
      NHL: {
        label: 'Puck Line%', hint: 'How often the team covered the puck line (±1.5 goals).',
        explain: {
          what: `How often the team covered ${PUCK_LINE}: as the favourite it must win by 2 or more; as the underdog it covers by winning or losing by 1.`,
          good: PRICED_LINE_GOOD,
          use: 'Shows whether a team tends to win by multiple goals or keep games close. Read it with the prices on offer.',
          watch: 'The line and price adjust as a team surprises people. Under 10 games the board marks it “small sample” and does not colour it.',
        },
      },
      NBA: {
        explain: {
          what: `Against the spread: the share of games where the team beat the betting spread. Pushes are left out. ${NBA_GRADED_LINE}`,
          good: 'Above 50% means the team has done better than the market expected. At standard -110 odds a bettor needs about 52.4% to profit.',
          use: 'It tells you whether the market has been under- or overrating a team so far. Use it as a prompt to look closer, not a reason to bet.',
          watch: 'The line adjusts as a team surprises people, so past covers say little about the next one. Under 10 games in a season view the board marks it “small sample” and does not colour it.',
        },
      },
    },
  },
  {
    key: 'over_pct', label: 'Over%', group: 'Betting', sports: BALL, format: 'pct3', better: null,
    record: { w: 'ou_o', l: 'ou_u', p: 'ou_p' }, sample: ['ou_o', 'ou_u', 'ou_p'],
    hint: 'How often this team’s games went over the total.',
    explain: {
      what: 'The share of the team’s games where the combined score beat the sportsbook’s total. Pushes are left out.',
      good: 'Neither end is better. It is a tendency, not a grade, so it is not coloured.',
      use: 'Shows whether totals have been set too low or too high for this team. Check it with pace and both teams’ scoring before betting a total.',
      watch: 'Books move totals as trends appear, so an over streak does not mean the next total is too low. Under 10 games the board marks it “small sample” and does not colour it.',
    },
    bySport: {
      NBA: {
        explain: {
          what: `The share of the team’s games where the combined score beat the sportsbook’s total. Pushes are left out. ${NBA_GRADED_LINE}`,
          good: 'Neither end is better. It is a tendency, not a grade, so it is not coloured.',
          use: 'Shows whether totals have been set too low or too high for this team. Check it with pace and both teams’ scoring before betting a total.',
          watch: 'Books move totals as trends appear, so an over streak does not mean the next total is too low. Under 10 games in a season view the board marks it “small sample”.',
        },
      },
    },
  },
  {
    key: 'ats_home_pct', label: 'ATS% Home', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    sample: ['home_w', 'home_l'],
    hint: 'How often the team covered the spread at home.',
    explain: {
      what: 'ATS%, home games only.',
      good: 'Above 50% means the market has underrated the team at home.',
      use: 'Compare it with the team’s overall ATS%. A big home/away gap can show a team the market misjudges in one setting.',
      watch: 'It is half a season’s games. A big gap on a small sample is usually noise. Under 10 home games the board marks it “small sample”.',
    },
    bySport: {
      MLB: { label: 'RL% Home', hint: 'How often the team covered the run line at home.', explain: { what: 'Run line cover rate, home games only.', good: PRICED_LINE_GOOD, use: 'Compare it with the team’s overall Run Line%.', watch: 'Under 10 home games the board marks it “small sample”.' } },
      NHL: { label: 'PL% Home', hint: 'How often the team covered the puck line at home.', explain: { what: 'Puck line cover rate, home games only.', good: PRICED_LINE_GOOD, use: 'Compare it with the team’s overall Puck Line%.', watch: 'Under 10 home games the board marks it “small sample”.' } },
    },
  },
  {
    key: 'ats_away_pct', label: 'ATS% Away', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    sample: ['away_w', 'away_l'],
    hint: 'How often the team covered the spread on the road.',
    explain: {
      what: 'ATS%, road games only.',
      good: 'Above 50% means the market has underrated the team on the road.',
      use: 'Compare it with the team’s overall and home ATS%.',
      watch: 'It is half a season’s games. Under 10 road games the board marks it “small sample”.',
    },
    bySport: {
      MLB: { label: 'RL% Away', hint: 'How often the team covered the run line on the road.', explain: { what: 'Run line cover rate, road games only.', good: PRICED_LINE_GOOD, use: 'Compare it with the team’s overall Run Line%.', watch: 'Under 10 road games the board marks it “small sample”.' } },
      NHL: { label: 'PL% Away', hint: 'How often the team covered the puck line on the road.', explain: { what: 'Puck line cover rate, road games only.', good: PRICED_LINE_GOOD, use: 'Compare it with the team’s overall Puck Line%.', watch: 'Under 10 road games the board marks it “small sample”.' } },
    },
  },
  {
    key: 'fav_ats_pct', label: 'ATS% as Fav', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    hint: 'How often the team covered when it was favoured.',
    explain: {
      what: 'ATS%, only in games where the team was the favourite.',
      good: 'Above 50% means the team has beaten the market’s expectations as a favourite.',
      use: 'Shows whether the market overrates or underrates the team when it is expected to win.',
      watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games. Check the team’s overall ATS record.',
    },
    bySport: {
      MLB: { label: 'RL% as Fav', hint: 'How often the team covered -1.5 runs as the favourite.', explain: { what: 'How often the team won by 2+ runs when it was favoured.', good: PRICED_LINE_GOOD, use: 'Shows whether the team tends to win comfortably when expected to win.', watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games.' } },
      NHL: { label: 'PL% as Fav', hint: 'How often the team covered -1.5 goals as the favourite.', explain: { what: 'How often the team won by 2+ goals when it was favoured.', good: PRICED_LINE_GOOD, use: 'Shows whether the team tends to win comfortably when expected to win.', watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games.' } },
      NBA: { explain: { what: `ATS%, only in games where the team was the favourite. ${NBA_GRADED_LINE}`, good: 'Above 50% means the team has beaten the market’s expectations as a favourite.', use: 'Shows whether the market overrates or underrates the team when it is expected to win.', watch: NBA_SPLIT_WATCH } },
    },
  },
  {
    key: 'dog_ats_pct', label: 'ATS% as Dog', group: 'Betting', sports: BALL, format: 'pct3', better: 'high',
    hint: 'How often the team covered as the underdog.',
    explain: {
      what: 'ATS%, only in games where the team was the underdog.',
      good: 'Above 50% means the team has beaten the market’s expectations as an underdog.',
      use: 'Shows whether the market has been selling the team short when it is not expected to win.',
      watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games. Check the team’s overall ATS record.',
    },
    bySport: {
      MLB: { label: 'RL% as Dog', hint: 'How often the team covered +1.5 runs as the underdog.', explain: { what: 'How often the team won or lost by 1 run when it was the underdog.', good: PRICED_LINE_GOOD, use: 'Shows whether the team keeps games close when it is not expected to win.', watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games.' } },
      NHL: { label: 'PL% as Dog', hint: 'How often the team covered +1.5 goals as the underdog.', explain: { what: 'How often the team won or lost by 1 goal when it was the underdog.', good: PRICED_LINE_GOOD, use: 'Shows whether the team keeps games close when it is not expected to win.', watch: 'The board can’t show how many games this is built on yet, so a high number may rest on two or three games.' } },
      NBA: { explain: { what: `ATS%, only in games where the team was the underdog. ${NBA_GRADED_LINE}`, good: 'Above 50% means the team has beaten the market’s expectations as an underdog.', use: 'Shows whether the market has been selling the team short when it is not expected to win.', watch: NBA_SPLIT_WATCH } },
    },
  },
  {
    key: 'rest_adv_ats_pct', label: 'ATS% Rest Edge', group: 'Betting', sports: RESTFUL, format: 'pct3', better: 'high',
    sample: ['rest_adv_games'],
    hint: 'Covering in games where this team had more rest than its opponent.',
    explain: {
      what: 'ATS%, only in games where this team had more days off than the opponent.',
      good: 'Above 50% means the team has made the most of the extra rest.',
      use: 'Rest can affect how a team plays. When this team has the rest edge tonight, this shows how it has done in the same spot.',
      watch: 'These spots are rare, so the sample is small. Under 10 games the board marks it “small sample”.',
    },
    bySport: {
      NHL: { label: 'PL% Rest Edge', explain: { what: 'Puck line cover rate, only in games where this team had more days off than the opponent.', good: PRICED_LINE_GOOD, use: 'When this team has the rest edge tonight, this shows how it has done in the same spot.', watch: 'These spots are rare. Under 10 games the board marks it “small sample”.' } },
    },
  },
  {
    key: 'short_rest_ats_pct', label: 'ATS% Short Rest', group: 'Betting', sports: RESTFUL, format: 'pct3', better: 'high',
    sample: ['short_rest_games'],
    hint: 'Covering on back-to-backs (basketball, hockey) or short weeks (football).',
    explain: {
      what: 'ATS% on little rest: the second night of a back-to-back in basketball and hockey, or a short week (6 days or fewer) in football.',
      good: 'Above 50% means the team has handled tired spots better than the market expected.',
      use: 'Check it when the team is on short rest tonight, together with the opponent’s rest.',
      watch: 'Small sample. Under 10 games the board marks it “small sample”.',
    },
    bySport: {
      NHL: { label: 'PL% Short Rest', explain: { what: 'Puck line cover rate on the second night of a back-to-back.', good: PRICED_LINE_GOOD, use: 'Check it when the team is on a back-to-back tonight.', watch: 'Small sample. Under 10 games the board marks it “small sample”.' } },
    },
  },
];

/** A catalog entry with its sport's wording applied. */
export function resolveTeamStat(def: TeamStatDef, sport: Sport): TeamStatDef {
  const over = def.bySport?.[sport];
  return over ? { ...def, ...over } : def;
}

/** Team stats this sport shows, in catalog order, worded for the sport. */
export function teamStatsForSport(sport: Sport): TeamStatDef[] {
  return TEAM_STAT_CATALOG.filter((s) => s.sports.includes(sport)).map((s) => resolveTeamStat(s, sport));
}

/** One stat for a sport, by key, worded for the sport; null when not shown. */
export function teamStatFor(sport: Sport, key: keyof TeamStatsRow): TeamStatDef | null {
  return teamStatsForSport(sport).find((s) => s.key === key) ?? null;
}

/** "ATS", "RL" or "PL": the spread's short name in this sport. */
export function spreadWord(sport: Sport): string {
  if (sport === 'MLB') return 'RL';
  if (sport === 'NHL') return 'PL';
  return 'ATS';
}

/** Groups that actually have a stat for this sport (so no empty tabs render). */
export function teamGroupsForSport(sport: Sport): TeamStatGroup[] {
  const present = new Set(teamStatsForSport(sport).map((s) => s.group));
  return TEAM_GROUP_ORDER.filter((g) => present.has(g));
}

/**
 * The sport's default team stat — the most useful single number to open on.
 * Efficiency-first by design: the board should not greet you with an ATS record.
 */
export function defaultTeamStatFor(sport: Sport): TeamStatDef | null {
  const wantKey: Partial<Record<Sport, keyof TeamStatsRow>> = {
    MLB: 'wrc_plus',
    NBA: 'net_rating',
    WNBA: 'net_rating',
    NHL: 'corsi_for_pct',
    NFL: 'yards_per_play',
    NCAAF: 'sp_overall',
  };
  const list = teamStatsForSport(sport);
  const key = wantKey[sport];
  return list.find((s) => s.key === key) ?? list[0] ?? null;
}

/** Sports with a team board at all (golf and UFC have no teams). */
const TEAM_SPORTS = new Set<Sport>(BALL);
export function supportsTeamBoard(sport: Sport): boolean {
  return TEAM_SPORTS.has(sport);
}

/**
 * The season the Teams board asks for first, by the sport's own label
 * (CLAUDE.md §4), on the America/New_York clock.
 *
 * NBA and NHL name a season by the year it ENDS, so October through December
 * belong to next year's label: on 2026-11-02 the 2026-27 season is 2027. The
 * board used to ask for the calendar year for every sport and so showed the
 * finished 2025-26 season, labelled "2026", a month into 2026-27.
 * MLB, WNBA, NFL and NCAAF use the calendar year here (football's fallback to
 * the previous label lives in fetchTeamStats).
 */
export function teamBoardSeason(sport: Sport, now: Date = new Date()): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York',
    year: 'numeric',
    month: 'numeric',
  }).formatToParts(now);
  const year = Number(parts.find((p) => p.type === 'year')?.value);
  const month = Number(parts.find((p) => p.type === 'month')?.value);
  // NCAABW labels by the ending year like NCAAB (docs/sports/ncaabw.md).
  // Neither college sport is on the Teams board; this keeps the label right.
  if (sport === 'NBA' || sport === 'NHL' || sport === 'NCAAB' || sport === 'NCAABW') {
    return month >= 10 ? year + 1 : year;
  }
  return year;
}

/** How the board names a season: "2026-27" for the leagues that straddle
 *  two years, else the year. */
export function teamSeasonLabel(sport: Sport, season: number): string {
  if (sport === 'NBA' || sport === 'NHL' || sport === 'NCAAB' || sport === 'NCAABW') {
    return `${season - 1}-${String(season).slice(2)}`;
  }
  return String(season);
}

/** Numeric value for a team row under a stat, or null when absent. */
export function teamStatValue(row: TeamStatsRow, def: TeamStatDef): number | null {
  const v = row[def.key];
  if (typeof v === 'number') return v;
  // Postgres NUMERIC can arrive as a string over PostgREST.
  if (typeof v === 'string') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

export function formatTeamStat(value: number | null, format: TeamStatFormat): string {
  if (value == null) return '—';
  switch (format) {
    case 'int': return String(Math.round(value));
    case 'dec1': return value.toFixed(1);
    case 'dec2': return value.toFixed(2);
    case 'dec3': return value.toFixed(3);
    case 'pct3': return `${(value * 100).toFixed(1)}%`;
  }
}

/** "67-42" or "67-42-3" when the split can push. */
export function formatRecord(row: TeamStatsRow, def: TeamStatDef): string | null {
  if (!def.record) return null;
  const w = teamStatValue(row, { ...def, key: def.record.w });
  const l = teamStatValue(row, { ...def, key: def.record.l });
  if (w == null || l == null) return null;
  const p = def.record.p ? teamStatValue(row, { ...def, key: def.record.p }) : null;
  return p != null && p > 0 ? `${w}-${l}-${p}` : `${w}-${l}`;
}
