import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { BrandMark } from '@/components/BrandMark';
import { colors, font, radii, spacing } from '@/lib/theme';

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

interface Slide {
  icon: IoniconName;
  title: string;
  body: string;
  bullets?: string[];
}

const SLIDES: Slide[] = [
  {
    icon: 'shield-checkmark-outline',
    title: 'Graded in public, not hype',
    body:
      'Every market has its own model, and every pick it makes goes on the record — wins and losses, nothing hidden. A record that is still only a handful of bets is marked too early to judge, rather than hidden until it looks good.',
  },
  {
    icon: 'trending-up-outline',
    title: 'What winning actually looks like',
    body:
      'Beating the books is a grind, not a jackpot. A genuinely strong model wins roughly 53–57% of bets and a good stretch lands in the high-single to mid-teens ROI. Losing days and cold streaks are completely normal — judge us over hundreds of bets, not one night.',
  },
  {
    icon: 'pause-circle-outline',
    title: 'No pick is a pick',
    body:
      'Some days nothing clears our bar, so we show nothing. That restraint is the edge — forcing action on low-conviction games is how bankrolls bleed out. An empty board is a valid signal, not a bug.',
  },
  {
    icon: 'wallet-outline',
    title: 'Bet to stay in the game',
    body:
      'Sizes default to a fraction of Kelly so one cold run can’t wipe you out. Set a bankroll you can afford to lose, shop for the best price, skip the parlays the books push, and never chase. Tools here are built to help you last — not to promise you can’t lose.',
  },
];

export function OnboardingModal({ visible, onDone }: { visible: boolean; onDone: () => void }) {
  const [step, setStep] = useState(0);
  const last = step >= SLIDES.length - 1;
  const slide = SLIDES[step];

  const next = () => {
    if (last) onDone();
    else setStep((s) => s + 1);
  };

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen">
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.skipRow}>
          <Pressable onPress={onDone} hitSlop={12}>
            <Text style={styles.skip}>Skip</Text>
          </Pressable>
        </View>

        <View style={styles.body}>
          {step === 0 ? (
            // The first screen a new user sees leads with the brand mark
            // (assets/brand/mark.png); the later slides keep their icons.
            <BrandMark size={88} style={styles.mark} />
          ) : (
            <View style={styles.iconWrap}>
              <Ionicons name={slide.icon} size={40} color={colors.tint} />
            </View>
          )}
          <Text style={styles.title}>{slide.title}</Text>
          <Text style={styles.text}>{slide.body}</Text>
        </View>

        <View style={styles.footer}>
          <View style={styles.dots}>
            {SLIDES.map((_, i) => (
              <View key={i} style={[styles.dot, i === step && styles.dotActive]} />
            ))}
          </View>
          <Pressable
            onPress={next}
            style={({ pressed }) => [styles.btn, pressed && styles.btnPressed]}
          >
            <Text style={styles.btnText}>{last ? 'Get started' : 'Next'}</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  skipRow: {
    alignItems: 'flex-end',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
  },
  skip: { fontSize: font.size.body, color: colors.textTertiary, fontWeight: font.weight.medium },
  body: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    paddingHorizontal: spacing.xl,
  },
  mark: {
    marginBottom: spacing.xl,
  },
  // Same silhouette as the mark on slide 1 (a rounded square, not a circle),
  // so the swipe from slide 1 to 2 changes the content, not the hero's shape.
  iconWrap: {
    width: 88,
    height: 88,
    borderRadius: Math.round(88 * 0.224),
    backgroundColor: colors.bgCard,
    alignItems: 'center',
    justifyContent: 'center',
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
  footer: { paddingHorizontal: spacing.xl, paddingBottom: spacing.lg },
  dots: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 8,
    marginBottom: spacing.lg,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.separatorOpaque,
  },
  dotActive: { backgroundColor: colors.tint, width: 22 },
  btn: {
    backgroundColor: colors.tint,
    paddingVertical: spacing.md,
    borderRadius: radii.md,
    alignItems: 'center',
  },
  btnPressed: { opacity: 0.8 },
  btnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
});
