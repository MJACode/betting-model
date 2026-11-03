/**
 * #1091 Lows: the inline bet headline, the missing-price VoiceOver label,
 * and the About-sheet → sportsbook-picker hand-off.
 *
 *   node --experimental-strip-types scripts/verify_stats_board_a11y.ts
 *
 * No device, no React Native. The screen wiring is pinned by reading the
 * source; the decisions are pinned by calling the pure helpers.
 */

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import type { PickerHandoffPhase } from '../src/lib/statsBoardA11y';

const root = join(import.meta.dirname, '..');
// Dynamic .ts import: node --experimental-strip-types (what CI runs) does not
// resolve an extensionless specifier, and a static `.ts` import fails tsc.
const {
  HEADLINE_WRAP_FONT_SCALE,
  PICKER_AFTER_DISMISS_MS,
  SHEET_DISMISS_FALLBACK_MS,
  boardNotesAccessibilityLabel,
  lineHeadlineNumberOfLines,
  reducePickerHandoff,
} = await import(pathToFileURL(join(root, 'src/lib/statsBoardA11y.ts')).href);
const stats = readFileSync(join(root, 'src/screens/StatsScreen.tsx'), 'utf8');
const sheet = readFileSync(join(root, 'src/components/InfoTooltip.tsx'), 'utf8');

let failed = 0;
function check(name: string, ok: boolean, detail = ''): void {
  if (ok) {
    console.log(`  ok  ${name}`);
    return;
  }
  failed += 1;
  console.log(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
}

const reason = 'FanDuel hasn’t posted Hits lines today.';

check(
  'default Dynamic Type keeps the bet headline on one line',
  lineHeadlineNumberOfLines(1) === 1 && lineHeadlineNumberOfLines(1.39) === 1,
);
check(
  'accessibility sizes drop the line cap so the headline can wrap',
  lineHeadlineNumberOfLines(HEADLINE_WRAP_FONT_SCALE) === undefined
    && lineHeadlineNumberOfLines(2) === undefined,
);
check('a bad font scale does not drop the cap', lineHeadlineNumberOfLines(Number.NaN) === 1);

check(
  'the ⓘ label is unchanged when prices are present',
  boardNotesAccessibilityLabel(2, null) === 'About this board, 2 notes'
    && boardNotesAccessibilityLabel(1, '  ') === 'About this board, 1 note',
);
check(
  'the ⓘ label says why the price column is dashes',
  boardNotesAccessibilityLabel(2, reason)
    === `About this board, 2 notes, including why prices are missing. ${reason}`,
);

function step(phase: PickerHandoffPhase, event: 'tap-ios' | 'tap-other' | 'release' | 'fallback') {
  return reducePickerHandoff(phase, event);
}

const iosTap = step('idle', 'tap-ios');
check(
  'iOS tap closes the sheet and does not open the picker yet',
  iosTap.phase === 'armed' && iosTap.closeSheet && !iosTap.openPicker && iosTap.armFallback,
);
const iosFallback = step(iosTap.phase, 'fallback');
check(
  'a dropped onDismiss still opens the picker and leaves the hand-off armed',
  iosFallback.phase === 'armed' && iosFallback.openPicker && !iosFallback.armFallback,
);
const iosDismiss = step(iosFallback.phase, 'release');
check(
  'a late onDismiss opens the picker again and then disarms',
  iosDismiss.phase === 'opened' && iosDismiss.openPicker && !iosDismiss.closeSheet,
);
const iosAgain = step(iosDismiss.phase, 'release');
check('a second dismiss does not open the picker again', !iosAgain.openPicker && iosAgain.phase === 'opened');
check(
  'Got it (dismiss while idle) does not open the picker',
  !step('idle', 'release').openPicker && step('idle', 'release').phase === 'idle',
);
const other = step('idle', 'tap-other');
check(
  'other platforms open the picker immediately and do not arm a fallback',
  other.phase === 'opened' && other.openPicker && other.closeSheet && !other.armFallback,
);
check('a second iOS tap while armed does not arm a second fallback', !step('armed', 'tap-ios').armFallback);
check(
  'the fallback wait is after the post-dismiss defer',
  PICKER_AFTER_DISMISS_MS > 0 && SHEET_DISMISS_FALLBACK_MS > PICKER_AFTER_DISMISS_MS + 300,
);

check(
  'the headline reads the font scale through the helper',
  stats.includes('lineHeadlineNumberOfLines('),
);
check(
  'the ⓘ says why prices are missing only when the price column is absent',
  stats.includes('const missingPriceReason = showOdds ? null : (noLinesNote?.text ?? null);')
    && stats.includes('boardNotesAccessibilityLabel(boardNotes.length, missingPriceReason)'),
);
check(
  'a one-off dash stays hidden — the absent column is explained on the ⓘ',
  stats.includes('accessibilityElementsHidden') && stats.includes('importantForAccessibility="no-hide-descendants"'),
);
check(
  'opening the notes sheet clears a leftover hand-off',
  stats.includes("pickerHandoff.current = 'idle'"),
);
check(
  'the fallback present does not consume the hand-off',
  stats.includes("reducePickerHandoff(pickerHandoff.current, 'fallback')"),
);
check(
  'a refused present is asked for again by dropping the flag first',
  stats.includes('if (pickerOpenRef.current) setPickerOpenTracked(false)'),
);
check(
  'Change your sportsbooks goes through the hand-off, iOS waiting on dismiss',
  stats.includes("Platform.OS === 'ios' ? 'tap-ios' : 'tap-other'")
    && stats.includes("reducePickerHandoff(")
    && stats.includes('PICKER_AFTER_DISMISS_MS')
    && stats.includes('SHEET_DISMISS_FALLBACK_MS'),
);
check(
  'the sheet forwards onDismiss and the screen releases the hand-off there',
  sheet.includes('onDismiss={onDismiss}') && stats.includes('onDismiss={onNotesSheetDismiss}'),
);

if (failed) {
  console.log(`\n${failed} failed`);
  process.exit(1);
}
console.log('\nALL PASS');
