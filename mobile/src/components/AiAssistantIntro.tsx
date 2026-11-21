import React, { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Modal } from '@/components/TrackedModal';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';

import { useAiAssistant } from '@/hooks/useAiAssistant';
import {
  INTRO_DISMISSED_KEY,
  UNLOCKED_SHOWN_KEY,
  perDayLabel,
  shouldShowIntroCard,
  shouldShowUnlockedSheet,
} from '@/lib/aiAssistant';
import { colors, font, radii, spacing, opacity } from '@/lib/theme';
import { PrimaryButton } from '@/components/PrimaryButton';

/**
 * The two one-time AI Assistant moments on Picks (mockups 5 and 7).
 *
 *  - The intro card: paying or comped members who have not connected. "Not
 *    now" or the X hides it for good on this device.
 *  - The "unlocked" sheet: once, the first time this device sees a member who
 *    was on a trial and now pays. When it shows, the card waits for next time.
 *
 * Both are remembered in AsyncStorage; storage that fails reads as "not yet
 * dismissed" for the card and "already shown" for the sheet, so neither can
 * loop. Never on a trial, never for the App Review account.
 */
export function AiAssistantIntro({ onSetUp }: { onSetUp: () => void }) {
  const { status, previousEntitlement } = useAiAssistant();
  const [flags, setFlags] = useState<{ dismissed: boolean; shown: boolean } | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);

  useEffect(() => {
    let live = true;
    (async () => {
      let dismissed = false;
      let shown = true;
      try {
        const [d, s] = await Promise.all([
          AsyncStorage.getItem(INTRO_DISMISSED_KEY),
          AsyncStorage.getItem(UNLOCKED_SHOWN_KEY),
        ]);
        dismissed = d === '1';
        shown = s === '1';
      } catch {
        /* keep the safe defaults */
      }
      if (live) setFlags({ dismissed, shown });
    })();
    return () => {
      live = false;
    };
  }, []);

  const showSheet = flags != null && shouldShowUnlockedSheet(status, previousEntitlement, flags.shown);
  useEffect(() => {
    if (!showSheet) return;
    setSheetOpen(true);
    setFlags((f) => (f ? { ...f, shown: true } : f));
    void AsyncStorage.setItem(UNLOCKED_SHOWN_KEY, '1').catch(() => {});
  }, [showSheet]);

  const dismissCard = () => {
    setFlags((f) => (f ? { ...f, dismissed: true } : f));
    void AsyncStorage.setItem(INTRO_DISMISSED_KEY, '1').catch(() => {});
  };

  const insets = useSafeAreaInsets();
  const showCard = flags != null && !sheetOpen && shouldShowIntroCard(status, flags.dismissed);
  const unlimited = !!status?.unlimited;
  const perDay = perDayLabel(status);

  return (
    <>
      {showCard ? (
        <View style={styles.card}>
          <View style={styles.cardTop}>
            <View style={styles.pill}>
              <Text style={styles.pillText}>New for members</Text>
            </View>
            <Pressable
              onPress={dismissCard}
              accessibilityRole="button"
              accessibilityLabel="Dismiss AI Assistant intro"
              hitSlop={12}
              style={({ pressed }) => [styles.close, pressed && styles.pressed]}
            >
              <Ionicons name="close" size={18} color={colors.brandMuted} />
            </Pressable>
          </View>
          <Text style={styles.title}>Ask your AI assistant about Stats</Text>
          <Text style={styles.body}>
            Connect Claude, ChatGPT or Grok to Signal Base and ask about hit rates, matchups and the
            best price in plain English.{unlimited ? '' : ` ${perDay}.`}
          </Text>
          <View style={styles.actions}>
            <View style={{ flex: 1 }}>
              <PrimaryButton
                label="Set it up"
                variant="brand"
                onPress={() => {
                  dismissCard();
                  onSetUp();
                }}
              />
            </View>
            <PrimaryButton label="Not now" variant="chromeSecondary" onPress={dismissCard} style={styles.notNow} />
          </View>
        </View>
      ) : null}

      <Modal
        trackName="AiAssistantUnlockedSheet"
        visible={sheetOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setSheetOpen(false)}
      >
        <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={() => setSheetOpen(false)}
          accessibilityRole="button"
          accessibilityLabel="Close AI Assistant is unlocked"
        />
        <Pressable
          style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}
          onPress={() => {}}
          accessible={false}
          accessibilityViewIsModal
        >
          <View style={styles.sheetIcon}>
            <Ionicons name="lock-open" size={24} color={colors.brandInk} />
          </View>
          <Text style={styles.eyebrow}>You’re a full member</Text>
          <Text style={styles.sheetTitle} accessibilityRole="header">AI Assistant is unlocked</Text>
          <Text style={styles.body}>
            Thanks for staying with Signal Base. You can now connect Claude, ChatGPT or Grok and ask
            about Stats in plain English: {perDay}.
          </Text>
          <View style={styles.sheetActions}>
            <PrimaryButton
              label="Set up AI Assistant"
              variant="brand"
              onPress={() => {
                setSheetOpen(false);
                dismissCard();
                onSetUp();
              }}
            />
            <PrimaryButton label="Later" variant="chromeSecondary" onPress={() => setSheetOpen(false)} />
          </View>
        </Pressable>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.chromeSurface,
    borderRadius: radii.lg,
    padding: spacing.xl,
    gap: spacing.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
  },
  cardTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  pill: {
    backgroundColor: colors.brand,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  pillText: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.bold,
    color: colors.brandInk,
  },
  close: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', marginRight: -spacing.md },
  pressed: { opacity: opacity.pressed },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    lineHeight: 27,
    color: colors.onChrome,
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.body,
    lineHeight: 21,
    color: colors.onChromeSecondary,
  },
  actions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  notNow: { alignSelf: 'auto' },
  backdrop: { flex: 1, backgroundColor: colors.scrim, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.chromeSurface,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.xl,
    gap: spacing.md,
  },
  sheetIcon: {
    width: 52,
    height: 52,
    borderRadius: radii.md,
    backgroundColor: colors.brand,
    alignItems: 'center',
    justifyContent: 'center',
  },
  eyebrow: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.brand,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  sheetTitle: {
    fontFamily: font.family,
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.onChrome,
  },
  sheetActions: { gap: spacing.sm, paddingTop: spacing.xs },
});
