import React from 'react';
import { Pressable, StyleSheet, Text, useWindowDimensions } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { noteBack } from '@/lib/freezeLog';
import {
  HEADER_ITEM_HEIGHT,
  PLAYER_DETAIL_PARENT,
  backChevronSize,
  playerTitleMaxWidth,
  settingsTitleMaxWidth,
  stackBackDecision,
} from '@/lib/stackBack';
import { colors, font, opacity } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

/** Same type as the player title, for a short section name such as "Legal & support". */
export function SettingsSectionHeaderTitle({
  children,
}: {
  children?: React.ReactNode;
  /** Passed by the stack. On iOS it is the header tint. The title is not a link. */
  tintColor?: string;
}) {
  const { width, fontScale } = useWindowDimensions();
  return (
    <Text
      numberOfLines={1}
      adjustsFontSizeToFit
      minimumFontScale={0.8}
      maxFontSizeMultiplier={2}
      style={[styles.title, { maxWidth: settingsTitleMaxWidth(width, fontScale) }]}
    >
      {children}
    </Text>
  );
}

/** Centered player name. One line, and no wider than the gap between the Back buttons. */
export function PlayerStatsHeaderTitle({
  children,
}: {
  children?: React.ReactNode;
  /** Passed by the stack. On iOS it is the header tint (the link colour). The name is not a link. */
  tintColor?: string;
}) {
  const { width, fontScale } = useWindowDimensions();
  return (
    <Text
      numberOfLines={1}
      maxFontSizeMultiplier={2}
      style={[styles.title, { maxWidth: playerTitleMaxWidth(width, fontScale) }]}
    >
      {children}
    </Text>
  );
}

/**
 * The Back button on every pushed screen: a chevron, no word.
 *
 * It replaces UIKit's back button, which went dead after a modal on iOS 27
 * (Player Stats, Settings, Pick Detail from a push). This one is a React
 * pressable in the header's left slot. The stack insets that header by the
 * safe area; the provider is seeded so the inset exists on the first frame.
 *
 * CHEVRON ONLY (Matt, 2026-11-16). On iOS 26+ UIKit draws its own glass
 * bubble behind any view in the bar's left slot. With a chevron and "Back"
 * inside it, the bubble hugged the text with no side padding and read as a
 * cramped grey pill. A 44pt square makes that bubble a circle around the
 * chevron, which is what Apple's own minimal Back looks like and what the
 * Mobbin reference set uses (IMDb, TIDE, Tiimo, Calm, X; none of 15 shows a
 * "Back" word). Below iOS 26 there is no bubble and it is a bare chevron.
 * VoiceOver still reads "Back". Supersedes the chevron + "Back" of #1239.
 *
 * A 36pt square, not 44 (2026-11-17): on iOS 26+ UIKit fits a header view
 * into 36pt and react-native-screens 4.16 does not re-center our content, so
 * a 44pt square drew the chevron 4pt low in its bubble (HEADER_ITEM_HEIGHT).
 * hitSlop takes the target to 52 x 52 (12 above, 4 below, 8 a side); it stays
 * inside the bar and does not reach down into the title. zIndex / elevation order the button inside its
 * own header slot. The title width is what keeps a long name off it — the
 * title is a UIKit label, and a React zIndex does not paint over that.
 */
type BackPath = 'pop' | 'replace' | 'reset';

/**
 * The tap is logged BEFORE navigating: if the pop throws or hangs, the crumb
 * is already saved, so the trail cannot misread a failed pop as a tap that
 * never arrived (review M3 on #1377).
 */
function BackPill({ decide, go }: { decide: () => BackPath; go: (path: BackPath) => void }) {
  const { fontScale } = useWindowDimensions();
  const icon = backChevronSize(fontScale);
  return (
    <Pressable
      onPress={() => {
        const path = decide();
        noteBack(path);
        go(path);
      }}
      accessibilityRole="button"
      accessibilityLabel="Back"
      hitSlop={{ top: 12, bottom: 4, left: 8, right: 8 }}
      style={({ pressed }) => [styles.pill, pressed && styles.pressed]}
    >
      <Ionicons name="chevron-back" size={icon} color={colors.tint} />
    </Pressable>
  );
}

export function PlayerStatsBackButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <BackPill
      decide={() => (stackBackDecision(navigation.canGoBack()) === 'pop' ? 'pop' : 'replace')}
      go={(path) => {
        if (path === 'pop') navigation.goBack();
        else navigation.replace(PLAYER_DETAIL_PARENT.name, { screen: PLAYER_DETAIL_PARENT.screen });
      }}
    />
  );
}

/**
 * The same button on every other pushed screen (the navigator's default).
 *
 * The arrow-only system Back (2026-11-08) went dead again on 2026-11-15, on
 * Pick Detail opened from a push notification, iOS 27.3. UIKit's Back has now
 * failed on three screens, and the React pill has not failed on either screen
 * that carries it, so no pushed screen uses UIKit's Back. An empty stack (a
 * reset, or a deep link that landed alone) goes to the tabs.
 */
export function StackBackButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <BackPill
      decide={() => (stackBackDecision(navigation.canGoBack()) === 'pop' ? 'pop' : 'reset')}
      go={(path) => {
        if (path === 'pop') navigation.goBack();
        else navigation.reset({ index: 0, routes: [{ name: 'Tabs' }] });
      }}
    />
  );
}

/**
 * The same button on a Settings section. An empty stack returns to Settings.
 * The player screen's empty-stack parent stays the Stats tab.
 */
export function SettingsSectionBackButton() {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  return (
    <BackPill
      decide={() => (stackBackDecision(navigation.canGoBack()) === 'pop' ? 'pop' : 'reset')}
      go={(path) => {
        if (path === 'pop') navigation.goBack();
        // Settings alone has no back and no tabs, so Android back would leave
        // the app. Put the tabs under it.
        else navigation.reset({ index: 1, routes: [{ name: 'Tabs' }, { name: 'Settings' }] });
      }}
    />
  );
}

const styles = StyleSheet.create({
  title: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    textAlign: 'center',
    color: colors.textPrimary,
  },
  pill: {
    alignItems: 'center',
    justifyContent: 'center',
    width: HEADER_ITEM_HEIGHT,
    height: HEADER_ITEM_HEIGHT,
    zIndex: 20,
    elevation: 20,
  },
  pressed: { opacity: opacity.pressed },
});
