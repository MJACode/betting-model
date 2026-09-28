import React from 'react';
import { StyleSheet, Text, useWindowDimensions, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { colors, font, radii } from '@/lib/theme';
import { badgeGlyphSize } from '@/lib/tone';
import { PAUSED_SPOKEN, PAUSED_TAG_TEXT } from '@/lib/pausedPick';

interface Props {
  /** Pick Detail header: 12pt. Cards and slip legs: 11pt. */
  large?: boolean;
  /**
   * Whether the tag speaks for itself. OFF by default: on PickCard the card is
   * the one accessible element and PAUSED_SPOKEN is part of its label, and on
   * Pick Detail the note line right under the header says it in full — a
   * separately readable tag would say it twice (the #848 rule for the price
   * check chip and the started line). ON for a betslip leg, which has no
   * card-level label to carry it.
   */
  speak?: boolean;
}

/**
 * A paused model's pick (isPausedForDisplay): a small NEUTRAL tag beside the
 * model — not a warning, and never in place of the BET / NONE / AVOID badge.
 * Hairline outline in the opaque separator token, no fill (a flat grey pill
 * read as a disabled NONE badge next to one), pause glyph and word in
 * textSecondary (10.94:1 on bgCard, 9.80:1 on bg).
 */
export function PausedTag({ large = false, speak = false }: Props) {
  const size = large ? font.size.caption : font.size.micro;
  const { fontScale } = useWindowDimensions();
  const a11y = speak
    ? { accessible: true, accessibilityRole: 'text' as const, accessibilityLabel: PAUSED_SPOKEN }
    : { accessibilityElementsHidden: true, importantForAccessibility: 'no-hide-descendants' as const };
  return (
    <View style={[styles.tag, large && styles.tagLarge]} {...a11y}>
      <Ionicons
        name="pause"
        size={badgeGlyphSize(size, fontScale)}
        color={colors.textSecondary}
        accessibilityElementsHidden
        importantForAccessibility="no"
      />
      <Text style={[styles.text, { fontSize: size }]}>{PAUSED_TAG_TEXT}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'center',
    gap: 2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
    borderRadius: radii.pill,
    paddingHorizontal: 6,
    paddingVertical: 1,
  },
  tagLarge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
  },
  text: {
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
});
