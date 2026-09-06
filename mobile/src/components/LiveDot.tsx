import React from 'react';
import { StyleSheet, View } from 'react-native';
import { colors } from '@/lib/theme';

/**
 * The app's live mark: one 6pt red dot, drawn identically everywhere.
 *
 * It began inside GameStatusPill's LIVE pill. When Live stopped being a bottom
 * tab on 2026-09-06 and became a conditional segment on Picks, the same dot had
 * to appear on the segment and on the sport chips — the segment's presence and
 * the chip's dot are now what tell a user something is in play, so the three
 * marks have to be visibly the same thing. Three copies of
 * `{width:6,height:6,borderRadius:3,backgroundColor:avoid}` argued in comments
 * that they were deliberately identical, which is the argument for one
 * component (UX_REVIEW §8).
 *
 * Decorative on its own: every caller already names the state in its own
 * accessibilityLabel ("NCAAF, 3 signals, in play now"), so this must stay out
 * of the accessibility tree rather than adding a second, wordless announcement.
 */
export function LiveDot() {
  return <View style={styles.dot} accessibilityElementsHidden importantForAccessibility="no" />;
}

const styles = StyleSheet.create({
  dot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.avoid,
  },
});
