import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { Modal } from '@/components/TrackedModal';
import { discordInviteIfPaid } from '@/lib/discord';
import { discordJoinCopy, type DiscordJoinChoice, type DiscordJoinVariant } from '@/lib/discordJoin';
import { openLink } from '@/lib/socialLinks';
import { colors, font, radii, spacing } from '@/lib/theme';

/**
 * Paid members, once, after onboarding. The invite is opened, never printed.
 * Either button marks the screen seen. Android back is Maybe later, so the
 * full screen cannot trap the member.
 */
export function DiscordJoinModal({
  visible,
  variant,
  discordPaid,
  onChoose,
}: {
  visible: boolean;
  variant: DiscordJoinVariant | null;
  discordPaid: boolean;
  onChoose: (choice: DiscordJoinChoice) => void;
}) {
  const copy = variant ? discordJoinCopy(variant) : null;
  const onJoin = () => {
    onChoose('join');
    const invite = discordInviteIfPaid(discordPaid);
    if (invite) void openLink(invite, 'Discord', { revealUrl: false });
  };

  return (
    <Modal
      trackName="DiscordJoinModal"
      visible={visible && copy != null}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={() => onChoose('later')}
    >
      {copy ? (
        <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
          <ScrollView style={styles.scroller} contentContainerStyle={styles.body}>
            <View style={styles.iconWrap}>
              <Ionicons name="chatbubble-outline" size={40} color={colors.tint} />
            </View>
            <Text style={styles.title} accessibilityRole="header">
              {copy.headline}
            </Text>
            <Text style={styles.text}>{copy.body}</Text>
            <View
              style={styles.bullets}
              accessible
              accessibilityRole="text"
              accessibilityLabel={copy.bullets.join('. ')}
            >
              {copy.bullets.map((line) => (
                <View
                  key={line}
                  style={styles.bulletRow}
                  accessibilityElementsHidden
                  importantForAccessibility="no-hide-descendants"
                >
                  <Ionicons name="checkmark" size={18} color={colors.tint} />
                  <Text style={styles.bullet}>{line}</Text>
                </View>
              ))}
            </View>
          </ScrollView>
          <View style={styles.footer}>
            <Pressable
              onPress={onJoin}
              accessibilityRole="button"
              accessibilityLabel="Join Discord"
              style={({ pressed }) => [styles.btn, pressed && styles.btnPressed]}
            >
              <Text style={styles.btnText}>{copy.primary}</Text>
            </Pressable>
            <Pressable
              onPress={() => onChoose('later')}
              accessibilityRole="button"
              accessibilityLabel="Maybe later"
              style={({ pressed }) => [styles.later, pressed && styles.btnPressed]}
            >
              <Text style={styles.laterText}>{copy.secondary}</Text>
            </Pressable>
            <Text style={styles.note}>{copy.note}</Text>
          </View>
        </SafeAreaView>
      ) : null}
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  scroller: { flex: 1 },
  body: {
    flexGrow: 1,
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.lg,
  },
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: Math.round(88 * 0.224),
    backgroundColor: colors.bgCard,
    alignItems: 'center',
    justifyContent: 'center',
    alignSelf: 'center',
    marginBottom: spacing.xl,
  },
  title: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    textAlign: 'center',
    marginBottom: spacing.md,
  },
  text: {
    fontSize: font.size.callout,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 24,
  },
  bullets: {
    marginTop: spacing.lg,
    gap: spacing.sm,
  },
  bulletRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
  },
  bullet: {
    flex: 1,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    lineHeight: 22,
  },
  footer: {
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.lg,
  },
  btn: {
    backgroundColor: colors.tint,
    minHeight: 44,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnPressed: { opacity: 0.8 },
  btnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  later: {
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
  },
  laterText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    textAlign: 'center',
    lineHeight: 18,
  },
});
