/**
 * Source-derived guards for the Stats tab's line pill and tab bar.
 *
 * Run with:  npx tsx scripts/verify_stats_pill.ts
 *
 * These three decisions are Matt's, made on 2026-09-04 against a competitor's
 * leaderboard, and each is the kind that quietly regresses in a refactor:
 *
 *  1. THE PILL IS THE BET LINK. "mirror exactly how they show the draft kings
 *     line and its betable link directly to that sportsbook." One tap goes to
 *     the book — no sheet in between, on either board.
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

import { lastName } from '../src/lib/matchup';
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
const groupTabs = read('src/components/GroupTabs.tsx');

// ── 1. The pill is the bet link ─────────────────────────────────────────────

for (const [file, src] of [
  ['StatsScreen', stats],
  ['TeamsBoard', teams],
] as const) {
  // The CALL, not the import: a file that still imports the helper but no
  // longer hands it the quote has quietly stopped being a bet link.
  check(
    `${file}: tapping a line pill hands the quote to openBookBetslip`,
    /openBookBetslip\(\s*quote\.book\s*,\s*quote\.link\s*\)/.test(src),
  );
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

// ── 3b. The matchup moved into the table, it did not vanish ────────────────
// Matt, 2026-09-04: "Add it as a widened spot column or have it be in the
// player data when you click on a record … Whatever the design thinks is best
// usability and UI." The designer's answer was the column, explicitly against
// the detail screen: a board whose matchup lives one tap deeper "can no longer
// be scanned for a bet, only for a name."

const matchup = read('src/lib/matchup.ts');
check(
  'every matchup carries the one fact the SPOT column prints',
  /detail: string \| null;/.test(matchup),
);
check(
  'a batter matchup names the opposing starter AND his ERA',
  // The ERA, not the arm: the tier colour separates only the tails (cliffs at
  // 4.60 / 3.40 around a ~4.10 league average), and `text` — the only other
  // carrier — now reaches a screen reader and nothing else.
  /detail: `\$\{lastName\(m\.opp_starter_name\)\} \$\{era\.toFixed\(2\)\}`/.test(matchup),
);
check(
  'a named starter with no ERA yet is named, not called TBD',
  /detail: m\.opp_starter_name \? `\$\{lastName\(m\.opp_starter_name\)\}\$\{hand\}` : 'TBD'/.test(
    matchup,
  ),
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
  'the SPOT column and its header share one constant, and its growth is bounded',
  /colHeaderMatchup: \{ minWidth: SPOT_W/.test(stats) &&
    /matchupWrap: \{\s*\n\s*minWidth: SPOT_W,\s*\n\s*maxWidth:/.test(stats),
);
check(
  'and both right-hand columns can give, so the player NAME is not the only one that does',
  (stats.match(/^\s+flexShrink: 1,$/gm) ?? []).length >= 2,
);
check(
  'the tier colours the FACT, not the team abbreviation',
  // colors.bet/avoid are BET/AVOID semantics: a green team name on a board of
  // prices reads as a side, and the hit-rate column is already a traffic light.
  /<Text style=\{\[styles\.matchupDetail, \{ color: c \}\]\}/.test(stats) &&
    /<Text style=\{styles\.matchupOppName\}/.test(stats),
);
check(
  'and colour is never the only carrier — the label says the tier IN WORDS',
  // Not the FAV/TGH/NEU glyph: spoken, "TGH" is noise and "NEU" is "new".
  /accessibilityLabel=\{`\$\{matchupTierWord\(matchup\.tier\)\} spot/.test(stats) &&
    /return 'Favourable';/.test(stats),
);
check(
  'the two-line rail stays straight when a sport has no detail',
  /\{matchup\.detail \?\? '—'\}/.test(stats),
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
