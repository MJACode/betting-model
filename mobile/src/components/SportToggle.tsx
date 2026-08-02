import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import { SPORTS, useSportFilter, type Sport } from '@/hooks/useSportFilter';

/**
 * Global sport selector. Drives the shared sport filter so every board shows one
 * sport at a time.
 *
 * Scrolls horizontally: there are six sports and a fixed row of six segments
 * overflowed the screen edge on a phone (the last one or two were unreachable).
 * The selected segment is scrolled into view on mount so a stored non-MLB sport
 * isn't hidden off-screen.
 *
 * `available` mutes sports with nothing on the board — they stay tappable (this
 * is the app-wide selector, and a user switching sports expects the empty state
 * to explain itself) but read as secondary so the eye lands on live sports.
 */
export function SportToggle({ available }: { available?: Set<string> }) {
  const { sport, setSport } = useSportFilter();
  const scrollRef = React.useRef<ScrollView>(null);
  const offsets = React.useRef<Record<string, number>>({});

  // Scroll the active sport into view once we know where it sits.
  const scrollToActive = React.useCallback(() => {
    const x = offsets.current[sport];
    if (x != null && x > 0) {
      scrollRef.current?.scrollTo({ x: Math.max(0, x - 40), animated: false });
    }
  }, [sport]);

  return (
    <ScrollView
      ref={scrollRef}
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.scroll}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.wrap}>
        {SPORTS.map((s: Sport) => {
          const active = s === sport;
          const muted = available != null && !available.has(s) && !active;
          return (
            <Pressable
              key={s}
              onPress={() => setSport(s)}
              onLayout={(e) => {
                offsets.current[s] = e.nativeEvent.layout.x;
                if (s === sport) scrollToActive();
              }}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              accessibilityLabel={muted ? `${s}, no picks today` : s}
              style={({ pressed }) => [
                styles.segment,
                active && styles.segmentActive,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[styles.label, active && styles.labelActive, muted && styles.labelMuted]}
              >
                {s}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: {
    paddingRight: spacing.lg,
  },
  wrap: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
    marginTop: spacing.sm,
  },
  segment: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.sm - 2,
  },
  segmentActive: {
    backgroundColor: colors.bgCard,
  },
  pressed: {
    opacity: 0.6,
  },
  label: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  labelActive: {
    color: colors.tint,
  },
  labelMuted: {
    color: colors.textTertiary,
    opacity: 0.7,
  },
});
