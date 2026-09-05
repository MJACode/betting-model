/**
 * Source-derived guards for the Stats tab's line pill and tab bar.
 *
 * Run with:  npx tsx scripts/verify_stats_pill.ts
 *
 * These three decisions are Matt's, made on 2026-09-04 against a competitor's
 * leaderboard, and each is the kind that quietly regresses in a refactor:
 *
 *  1. THE PILL IS THE BET LINK — REVERSED FOR PLAYERS the same evening. The
 *     morning's "mirror exactly how they show the draft kings line and its
 *     betable link directly to that sportsbook" became, with the competitor's
 *     betslip flow beside ours: "it shouldn't take you directly to the book,
 *     it should ask you if you want to add to bet slip then bet slip should
 *     allow you to add to any book." So on the Players board the pill opens
 *     AddLineSheet (verify_line_legs.ts pins that flow); since 2026-09-05 the
 *     Teams board's pill asks the same way (team line legs), and the pill's
 *     LOOK — filled in the book's colour, carrying its mark — holds on both.
 *  2. NOTHING UNDER THE PLAYER NAME. "I also like how their lines are clean."
 *     The Players rows are one line: name and team, nothing beneath.
 *  3. THE STAT GROUPS ARE TABS. "batting and pitching is floating to nowhere,
 *     can you have those have the same pattern as players and team." Every
 *     group row on the tab renders through the shared GroupTabs.
 *
 * Checked against the source because there is no renderer here: the assertions
 * read the files and fail when the shape changes, which is what a refactor
 * touches. Behaviour that CAN be executed lives in verify_stats_odds.ts.
 */

import { readFileSync } from 'node:fs';

import { gradeFor, gradeSpoken, lastName, normalCdf } from '../src/lib/matchup';
import { join } from 'node:path';

const ROOT = join(import.meta.dirname, '..');
const read = (p: string) => readFileSync(join(ROOT, p), 'utf-8');

let failures = 0;
function check(name: string, cond: boolean, detail = '') {
  if (!cond) failures++;
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}${detail ? ` — ${detail}` : ''}`);
}

const stats = read('src/screens/StatsScreen.tsx');
const teams = read('src/components/TeamsBoard.tsx');
const player = read('src/screens/PlayerStatsScreen.tsx');
const bookMark = read('src/components/BookMark.tsx');
const theme = read('src/lib/theme.ts');
const groupTabs = read('src/components/GroupTabs.tsx');

// ── 1. The pill asks, on Players and on Teams ───────────────────────────────

// The CALL, not the import: a file that still imports a helper but no longer
// hands it the quote has quietly changed what a tap does.
check(
  'StatsScreen: tapping a line pill opens the add-to-betslip sheet, not a book',
  /setLineSheet\(\s*quote\s*\)/.test(stats) && !/openBookBetslip\(/.test(stats),
);
check(
  'TeamsBoard: tapping a line pill opens the add-to-betslip sheet, not a book (team line legs, 2026-09-05)',
  /setLineSheet\(\s*quote\s*\)/.test(teams) && !/openBookBetslip\(/.test(teams),
);
for (const [file, src] of [
  ['StatsScreen', stats],
  ['TeamsBoard', teams],
] as const) {
  check(
    `${file}: no in-app sheet stands between the pill and the book`,
    !src.includes('StatsLineSheet'),
  );
  check(
    `${file}: the pill is filled in the book's own colour`,
    // The call on the quote, not the import — a file can keep the import and
    // still have stopped colouring anything.
    /bookButtonColors\(\s*quote\.book\s*\)/.test(src),
  );
  check(`${file}: the pill carries the book's mark`, src.includes('<BookMark'));
}

// The sheet is gone from the tree entirely — a stray copy would be a second,
// drifting definition of what a pill does.
let sheetExists = true;
try {
  read('src/components/StatsLineSheet.tsx');
} catch {
  sheetExists = false;
}
check('StatsLineSheet.tsx is deleted, not orphaned', !sheetExists);

// ── 2. Nothing under the player name ────────────────────────────────────────

check(
  'the Players rows carry no meta line under the name',
  !stats.includes('styles.rowMeta'),
);
check(
  'and the style itself is gone, so nothing can quietly re-add it',
  !stats.includes('rowMeta: {'),
);
// The line the price is for still reaches a screen-reader, since it is no
// longer printed on the row.
check(
  "the pill's accessibility label still names the line and the stat",
  /accessibilityLabel=\{label\}/.test(stats) &&
    /\$\{sideWord\} \$\{quote\.line\} \$\{statLabel\}/.test(stats),
);

// ── 3. The stat groups are tabs, everywhere ─────────────────────────────────

for (const [file, src] of [
  ['StatsScreen', stats],
  ['TeamsBoard', teams],
  ['PlayerStatsScreen', player],
] as const) {
  check(`${file}: stat groups render through the shared GroupTabs`, src.includes('<GroupTabs'));
  check(
    `${file}: no hand-rolled floating group row survives`,
    !src.includes('styles.groupTab') && !src.includes('groupTabText'),
  );
}
check(
  'Players | Teams and Hit Rates | Averages use the same component as the groups',
  // Word-bounded: <SegmentTabsAnythingElse must not count as a match.
  (stats.match(/<SegmentTabs[\s/>]/g) ?? []).length >= 2,
);
check(
  'the group row drops the top rule so the two levels read as one bar',
  /rowSecond:\s*\{\s*borderTopWidth: 0/.test(groupTabs),
);
check(
  'the bar is not a ScrollView — the widest set (NFL, four) fits at 25% each',
  !groupTabs.includes('ScrollView'),
);

// ── The mark itself ─────────────────────────────────────────────────────────

check(
  'BookMark takes the pill foreground, so the mark can never fail contrast',
  // Its own prop, not the glyph registry's — those are two different types and
  // the first version of this check was satisfied by the wrong one.
  /\/\*\* Foreground of the pill[\s\S]{0,120}?\n  color: string;/.test(bookMark),
);
check(
  'with no licensed glyph it renders NOTHING — no text stand-in for a logo',
  /if \(!Glyph\) return null;/.test(bookMark) && !/bookLabel/.test(bookMark),
);
check(
  'BookMark is silent for VoiceOver (the pill label already names the book)',
  // Every branch that renders. There is one now that the text fallback is gone,
  // so this asserts the count matches the branches rather than a fixed number.
  (bookMark.match(/importantForAccessibility="no-hide-descendants"/g) ?? []).length ===
    (bookMark.match(/return \(/g) ?? []).length,
);
check(
  'a logo registry exists, so dropping the licensed files in touches one file',
  // The declaration, not the sentence in the doc comment above it.
  /const BOOK_GLYPHS[:\s]/.test(bookMark),
);

// ── 3b. The matchup column: a graded difficulty, and where the fact went ───
// Matt, 2026-09-04: "Add it as a widened spot column or have it be in the
// player data when you click on a record." Then 2026-09-05: "update spot
// column to just be difficulty of that match up and have a bigger scale
// besides low med and high."
//
// So the column is now ONE letter, and 09-04's other option became load-bearing
// rather than rejected: the fact behind the grade moved to the player's detail
// screen. What is pinned here is that both halves happened — if the column got
// its grade and the fact went nowhere, the ERA left the product.

const matchup = read('src/lib/matchup.ts');
const playerDetail = read('src/screens/PlayerStatsScreen.tsx');

check(
  'the scale is bigger than three tiers',
  // The literal ask. Thirteen letters, and the old union is gone.
  /'A\+' \| 'A' \| 'A-'/.test(matchup) &&
    !/'favorable' \| 'neutral' \| 'tough'/.test(matchup),
);
check(
  'an ungraded matchup is a dash, never a C',
  // Grading an unknown starter as average invents the one fact the column
  // exists to report. Executed, not grepped.
  gradeFor(null) === null && gradeFor(NaN) === null,
);
check(
  'the grade is a percentile against MEASURED anchors, not remembered cliffs',
  // The old bands called 77% of WNBA matchups favourable because they assumed a
  // ~101 league-average defensive rating; the measured 2026 figure is 106.5.
  // Anything that reintroduces a bare comparison against a magic number here
  // should fail this.
  /const ANCHORS = \{/.test(matchup) &&
    /wnbaDefRtg: \{ median: 106\.46/.test(matchup) &&
    !/era >= 4\.6/.test(matchup),
);
// The grade boundaries and the CDF are pure, so RUN them.
check('a median matchup grades C-ish, not A', ['C', 'C+'].includes(gradeFor(normalCdf(0)) ?? ''));
check('a bottom-decile spot fails', gradeFor(normalCdf(-1.6)) === 'F' || gradeFor(normalCdf(-1.6)) === 'D-');
check('a top-decile spot is an A', (gradeFor(normalCdf(1.4)) ?? '').startsWith('A'));
check(
  'the scale is monotone — a better spot never grades worse',
  (() => {
    const order = ['F','D-','D','D+','C-','C','C+','B-','B','B+','A-','A','A+'];
    let prev = -1;
    for (let zi = -3; zi <= 3; zi += 0.05) {
      const idx = order.indexOf(gradeFor(normalCdf(zi)) ?? '');
      if (idx < prev) return false;
      prev = idx;
    }
    return true;
  })(),
);
check(
  'every grade is reachable — a band nothing can land in is a lie about the scale',
  (() => {
    const seen = new Set<string>();
    for (let zi = -4; zi <= 4; zi += 0.01) seen.add(gradeFor(normalCdf(zi)) ?? '');
    return seen.size === 13;
  })(),
);
check(
  'a batter matchup still names the opposing starter AND his ERA',
  // `text` is the sole carrier now that the cell prints only a letter — it
  // reaches the cell's screen-reader label AND the player detail screen.
  /text: `vs \$\{m\.opponent\} · \$\{shortName\(m\.opp_starter_name\)\} \$\{era\.toFixed\(2\)\} ERA\$\{hand\}`/.test(
    matchup,
  ),
);
check(
  'a named starter with no ERA yet is named, not called TBD',
  /\$\{m\.opp_starter_name \?\? 'starter TBD'\}/.test(matchup),
);
check(
  'the fact has somewhere to go: the player detail screen prints it',
  // Without this the column change deletes the ERA from the product for every
  // sighted user.
  /matchupText \? \(/.test(playerDetail) && /styles\.matchupLine/.test(playerDetail),
);
// lastName is pure and importable, so this RUNS it rather than grepping the
// source for a constant name — the first version asserted /SUFFIXES/, which
// `SUFFIXES_X` still satisfies. Where behaviour can be executed, execute it.
for (const [input, want] of [
  ['Nestor Cortes Jr.', 'Cortes'],
  ['Ke Bryan Hayes Sr.', 'Hayes'],
  ['Jose De Leon', 'De Leon'],
  ['Bryan De La Cruz', 'De La Cruz'],
  ['Cristian Javier', 'Javier'],
  ['Ohtani', 'Ohtani'],
] as const) {
  check(`lastName(${JSON.stringify(input)}) is the surname, not the suffix`, lastName(input) === want, lastName(input));
}
check(
  'the GRADE column and its header share one constant, and its growth is bounded',
  /colHeaderMatchup: \{\s*\n\s*minWidth: MATCHUP_W,/.test(stats) &&
    /matchupWrap: \{\s*\n\s*minWidth: MATCHUP_W,\s*\n\s*maxWidth:/.test(stats),
);
check(
  'and both right-hand columns can give, so the player NAME is not the only one that does',
  (stats.match(/^\s+flexShrink: 1,$/gm) ?? []).length >= 2,
);
check(
  'the grade is coloured off its own ramp, not the BET/AVOID pair',
  // colors.bet/avoid are this app's BET/AVOID semantics, and they fail AA
  // outright at 2.22:1 and 2.20:1 — which is what the old tier colours were.
  /export function gradeColor/.test(theme) &&
    /gradeGood: '#/.test(theme) &&
    !/gradeGood: colors\.bet/.test(theme),
);
check(
  "BOTH of the board's traffic lights are on that ramp, not just the new one",
  // Shipping an accessible ramp two columns from an inaccessible one left the
  // board running two contrast standards with the accessible one on the
  // SECONDARY column (UX review, 2026-09-05).
  /if \(pct >= 0\.6\) return colors\.gradeGood;/.test(stats) &&
    !/AMBER/.test(stats) &&
    !/AMBER/.test(teams),
);
check(
  'the ramp encodes RANK, not just category: lightness falls good -> bad',
  // The first attempt tuned five steps to ~5:1 each, which made them
  // iso-luminant (B was fractionally LIGHTER than A) — a reader could see two
  // rows differed but not which was better, and deuteranopia collapsed the
  // green and the olive together. Computed here, not asserted from a comment.
  (() => {
    const hex = (k: string) => (new RegExp(`${k}: '(#[0-9A-Fa-f]{6})'`).exec(theme) ?? [])[1];
    const lin = (c: number) => { const x = c / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; };
    const lum = (h: string) => { const n = parseInt(h.slice(1), 16);
      return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255); };
    const ramp = ['gradeGood', 'gradeMid', 'gradeBad'].map(hex);
    if (ramp.some((h) => !h)) return false;
    const ls = (ramp as string[]).map(lum);
    const monotone = ls[0] > ls[1] && ls[1] > ls[2];
    // and every step still readable as TEXT on the card
    const aa = ls.every((l) => 1.05 / (l + 0.05) >= 4.5);
    return monotone && aa;
  })(),
);
check(
  'the header word fits its column, and the column carries the legend',
  // "MATCHUP" needs ~56-58pt at 11pt semibold and truncated inside 52.
  // And a bare "B+" says neither which end is good nor why some rows dash.
  /\n\s+GRADE\n/.test(stats) && /title="Matchup grade"/.test(stats),
);
check(
  "the cell's label does not re-announce the opponent the subline just took",
  // Built on `text` it said "at SEA" (subline) then "vs LAA" (cell) — the same
  // duplication the visual layer fixed, one layer down.
  /accessibilityLabel=\{`Matchup grade \$\{gradeSpoken\(matchup\.grade\)\}\$\{matchup\.fact/.test(stats) &&
    /fact: string \| null;/.test(matchup),
);
check(
  'the detail screen spells the grade out too — a bare "+" is dropped by VoiceOver',
  /accessibilityLabel=\{`Tonight's matchup, \$\{/.test(playerDetail) &&
    /gradeSpoken\(matchupGrade\)/.test(playerDetail),
);
check(
  'both boards answer the pull gesture',
  // They were the only two lists in the app whose pull did nothing, and every
  // row prints a clock now.
  (stats.match(/refreshControl=\{<RefreshControl/g) ?? []).length === 2 &&
    /refreshControl=\{<RefreshControl/.test(teams),
);
check(
  'the teams row reserves height only when it HAS a game',
  // A TeamRow is not tappable, so the height buys no touch target — reserved
  // unconditionally it was dead space on every row of every off-day board.
  /rowWithGame: \{ minHeight: 54 \}/.test(teams) &&
    /subline \? styles\.rowWithGame : null/.test(teams),
);
check(
  'the clock survives a background/resume, not just a tick',
  // iOS suspends JS timers, so a resume showed the pre-suspend clock for up to
  // a full interval — the exact case the hook exists for.
  /AppState\.addEventListener/.test(read('src/hooks/useNow.ts')),
);
check(
  'and colour is never the only carrier — the LETTER is the fact, spelled out for VoiceOver',
  /accessibilityLabel=\{`Matchup grade \$\{gradeSpoken\(matchup\.grade\)\}/.test(stats) &&
    gradeSpoken('B+') === 'B plus' &&
    gradeSpoken('C-') === 'C minus' &&
    gradeSpoken('A') === 'A',
);

// ── 3c. …and the opponent came back under the name (2026-09-05) ────────────
// Matt, from a competitor screenshot: "add the time of the game and who they
// are playing under the name … for all sports".
check(
  'the subline is sourced from the slate, not the MLB/WNBA matchup views',
  // The matchup views cover two sports. `games` covers eight — "for all
  // sports" is the whole ask.
  /buildSlateGameIndex\(slateGames, slate/.test(stats) &&
    /const sublineFor = useCallback\(/.test(stats),
);
check(
  'both boards print it — Hit Rates and Averages, not just the one on screen',
  (stats.match(/subline=\{sublineFor\(/g) ?? []).length === 2 &&
    (stats.match(/styles\.rowSubline/g) ?? []).length === 2,
);
check(
  'VoiceOver hears the game on every row, tappable or not',
  // The non-tappable sports (NHL, UFC, Golf) set accessible={false} on the
  // name block, so the label has to sit on the subline Text itself.
  (stats.match(/accessibilityLabel=\{sublineSpoken\(subline\)\}/g) ?? []).length === 2 &&
    /accessibilityLabel=\{sublineSpoken\(subline\)\}/.test(teams),
);
check(
  'the teams board carries the same subline, from the same helper',
  /slateSubline\(/.test(teams) && /buildSlateGameIndex\(/.test(teams),
);
check(
  'the status word is printed once per row, not beside a price that says it too',
  // OddsCell / TeamLineCell already print "Live"/"Final" to explain a missing
  // number. The subline only takes the status when that column is hidden.
  /showOdds \? null : startedTeams\.get\(match\.key\)/.test(stats) &&
    /showLines \? null : startedTeams\.get\(item\.team\)/.test(teams),
);
check(
  'and the status is looked up by the key the row MATCHED on, so UFC rows get one',
  // A UFC row has no team; keying on row.team left every fight advertising a
  // start time hours after it ended.
  /startedTeams\.get\(match\.key\)/.test(stats),
);
check(
  'the row reserves a 44pt tap target, so a late subline cannot re-flow the list',
  // Players only: that row IS the tap target and a full-width row cannot use
  // hitSlop. The Teams row is not tappable and reserves conditionally instead.
  /minHeight: 44,/.test(stats),
);
check(
  'the subline clears the AA contrast floor (textTertiary at 11pt does not)',
  (stats.match(/rowSubline: \{[\s\S]{0,120}?color: colors\.textSecondary/g) ?? []).length === 1 &&
    /rowSubline: \{ fontSize: font\.size\.micro, color: colors\.textSecondary/.test(teams),
);
check(
  'one clock feeds every time-derived cell, so the board ages together',
  /const now = useNow\(\)/.test(stats) && /const now = useNow\(\)/.test(teams) &&
    (stats.match(/new Date\(now\)\.toISOString\(\)/g) ?? []).length === 2,
);

// ── 4. What the review caught: three regressions that must not come back ────

check(
  'the betslip card is gated on the line the chart is showing (§1c)',
  /slipPickFor\(\s*\{ player_id: playerId \}\s*,\s*idx\s*,\s*line - 0\.5\s*\)/.test(player),
);
check(
  'and slipPickFor is live code again, so its test guards something',
  player.includes("from '@/lib/statsOdds'") && player.includes('slipPickFor'),
);
check(
  'the leaderboard rows do not swallow the price pill for VoiceOver',
  // A Pressable is accessible by default, which collapses the row into ONE
  // element and makes the nested bet link unreachable.
  // Anchored to the JSX prop on its own line: the comment that EXPLAINS the
  // fix contains the same characters, and counting those was what let a
  // removed prop still pass.
  (stats.match(/^\s+accessible=\{false\}$/gm) ?? []).length >= 2,
);
check(
  "and the row's own tap is still reachable, on the name block",
  (stats.match(/accessibilityHint=\{tappable \? 'Opens this player' : undefined\}/g) ?? []).length >= 2,
);
check(
  'the price column grows with the text rather than clipping the price',
  /oddsWrap: \{\s*\n\s*minWidth: ODDS_W,\s*\n\s*maxWidth:/.test(stats),
);
check(
  'the pill clears the 44pt target with vertical hitSlop',
  /hitSlop=\{\{ top: 12, bottom: 12/.test(stats) && /hitSlop=\{\{ top: 12, bottom: 12/.test(teams),
);
check(
  'only the book whose brand colour we hold is filled; the rest are outlined',
  /const filled = quote\.book === MODEL_BOOK;/.test(stats) &&
    /const filled = quote\.book === MODEL_BOOK;/.test(teams),
);
check(
  'the two tab levels differ by more than type size',
  /tabActiveSecond:\s*\{\s*\n\s*borderBottomColor: colors\.textPrimary/.test(groupTabs) &&
    /borderBottomWidth: 1,/.test(groupTabs),
);
check(
  'a screen with no first level gets a first-level group row',
  /second=\{false\}/.test(player),
);
check(
  'group labels are uppercased by style, so VoiceOver reads words not letters',
  groupTabs.includes("textTransform: 'uppercase'") && !groupTabs.includes('g.toUpperCase()'),
);

console.log(failures === 0 ? '\nALL PASS' : `\n${failures} FAILURE(S)`);
process.exit(failures === 0 ? 0 : 1);
