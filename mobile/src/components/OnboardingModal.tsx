import React, { useEffect, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { BookChecklist, toggleBook } from '@/components/BookChecklist';
import { BrandMark } from '@/components/BrandMark';
import { BOOKS, usePreferredBooks, type BookKey } from '@/hooks/usePreferredBooks';
import { colors, font, radii, spacing } from '@/lib/theme';
import { pageLabel } from '@/lib/a11y';

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
      "Every market has its own model, and every pick it makes goes on the record — wins and losses, nothing hidden. A model's record is here from its first settled pick, even when that is one bet.",
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
      'Every pick is a flat 1-unit play, so no single call can run away with your roll. Pick a unit you can afford to lose, shop for the best price, skip the parlays the books push, and never chase. Tools here are built to help you last — not to promise you can’t lose.',
  },
];

/**
 * The last step: which sportsbooks the member uses (Matt, 2026-10-19). Every
 * book starts checked, because the value is in shopping all of them; the
 * member unchecks the ones they cannot use in their state. Settings keeps the
 * same list (SportsbookPickerSheet). A member who installed before this step
 * existed sees it on its own (`booksOnly`), once.
 */
const BOOKS_TITLE = 'Where do you bet?';
const BOOKS_BODY =
  'You get the most value by using every sportsbook you can: prices differ, and the best one changes from pick to pick. Uncheck any you can’t use in your state. You can change this anytime in Settings.';

export function OnboardingModal({
  visible,
  onDone,
  booksOnly = false,
}: {
  visible: boolean;
  onDone: () => void;
  /** Show only the sportsbook step (a member who has seen the slides). */
  booksOnly?: boolean;
}) {
  const { books, chosen, setBooks } = usePreferredBooks();
  const [step, setStep] = useState(0);
  // A first choice starts with every book checked, so it is an uncheck and
  // never a hunt. A replay from Settings starts from the member's own set.
  const [selected, setSelected] = useState<BookKey[]>([...BOOKS]);
  const firstStep = booksOnly ? SLIDES.length : 0;
  useEffect(() => {
    if (visible) {
      setStep(firstStep);
      setSelected(chosen ? [...books] : [...BOOKS]);
    }
    // Seeded once per open: a server answer landing mid-step must not undo
    // the member's checkmarks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, firstStep]);

  const total = SLIDES.length + 1;
  const onBooks = step >= SLIDES.length;
  const slide = onBooks ? null : SLIDES[step];

  const finish = () => {
    setBooks(selected);
    onDone();
  };
  const next = () => {
    if (onBooks) finish();
    else setStep((s) => s + 1);
  };
  // Skip passes the slides, never the choice: an unanswered set would bring
  // this screen back on every launch.
  const skip = () => setStep(SLIDES.length);

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="fullScreen">
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.skipRow}>
          {onBooks ? (
            // Same height as Skip at any text size, so the title does not jump.
            <Text
              style={[styles.skip, styles.hidden]}
              accessibilityElementsHidden
              importantForAccessibility="no-hide-descendants"
            >
              Skip
            </Text>
          ) : (
            <Pressable
              onPress={skip}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Skip intro"
            >
              <Text style={styles.skip}>Skip</Text>
            </Pressable>
          )}
        </View>

        {slide ? (
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
        ) : (
          <View style={styles.booksBody}>
            <Text style={styles.title} accessibilityRole="header">{BOOKS_TITLE}</Text>
            <Text style={styles.text}>{BOOKS_BODY}</Text>
            <ScrollView style={styles.booksList} contentContainerStyle={styles.booksListContent}>
              <BookChecklist
                selected={selected}
                onToggle={(b) => setSelected((prev) => toggleBook(prev, b))}
              />
            </ScrollView>
          </View>
        )}

        <View style={styles.footer}>
          {/* One spoken element for the dots, "Page 2 of 5" — bare circles
              said nothing to VoiceOver (audit M19). Hidden when the books
              step is shown on its own. */}
          {booksOnly ? null : (
            <View
              style={styles.dots}
              accessible
              accessibilityRole="text"
              accessibilityLabel={pageLabel(step, total)}
            >
              {Array.from({ length: total }, (_, i) => (
                <View key={i} style={[styles.dot, i === step && styles.dotActive]} />
              ))}
            </View>
          )}
          <Pressable
            onPress={next}
            accessibilityRole="button"
            accessibilityLabel={
              onBooks
                ? `Save ${selected.length} sportsbook${selected.length === 1 ? '' : 's'}${booksOnly ? '' : ' and get started'}`
                : `Next, ${pageLabel(step + 1, total).toLowerCase()}`
            }
            style={({ pressed }) => [styles.btn, pressed && styles.btnPressed]}
          >
            <Text style={styles.btnText}>{onBooks ? (booksOnly ? 'Save' : 'Save and get started') : 'Next'}</Text>
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
  hidden: { opacity: 0 },
  booksBody: {
    flex: 1,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.md,
  },
  booksList: { flex: 1, marginTop: spacing.lg },
  booksListContent: { paddingBottom: spacing.md },
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
