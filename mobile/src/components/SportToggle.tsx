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
 *
 * `signalCounts` badges each sport with how many picks have cleared the bet
 * line there. Because the boards show ONE sport at a time, a user parked on
 * their usual sport had no way to know another one had bets waiting — during
 * the Sept/Oct MLB-NFL overlap that meant missing NFL entirely. The badge is
 * the cross-sport signal: green count = actionable bets on that board.
 *
 * `liveSports` marks the sports with an in-play pick standing right now, with
 * the same 6pt red dot the LIVE pill on a card uses (GameStatusPill) — one live
 * mark in the app, not two. This is what replaced the Live bottom tab on
 * 2026-09-06: the tab was always on screen but never said WHICH sport was live,
 * so a user on MLB still had to tap through all eight to find the NCAAF game.
 * The dot says it from wherever they are.
 */
export function SportToggle({
  available,
  signalCounts,
  liveSports,
}: {
  available?: Set<string>;
  signalCounts?: Record<string, number>;
  liveSports?: Set<string>;
}) {
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
          const count = signalCounts?.[s] ?? 0;
          const isLive = liveSports?.has(s) ?? false;
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
              accessibilityLabel={[
                s,
                count > 0 ? `${count} signal${count === 1 ? '' : 's'}` : null,
                isLive ? 'in play now' : null,
                count === 0 && !isLive && muted ? 'no picks today' : null,
              ]
                .filter(Boolean)
                .join(', ')}
              style={({ pressed }) => [
                styles.segment,
                active && styles.segmentActive,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.segmentInner}>
                {isLive ? <View style={styles.liveDot} /> : null}
                <Text
                  style={[styles.label, active && styles.labelActive, muted && styles.labelMuted]}
                >
                  {s}
                </Text>
                {count > 0 ? (
                  <View style={styles.badge}>
                    <Text style={styles.badgeText}>{count}</Text>
                  </View>
                ) : null}
              </View>
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
  segmentInner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 5,
  },
  badge: {
    minWidth: 16,
    paddingHorizontal: 4,
    paddingVertical: 1,
    borderRadius: radii.pill,
    backgroundColor: colors.bet,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badgeText: {
    fontSize: font.size.nano,
    lineHeight: 13,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  // The same 6pt red dot GameStatusPill draws inside the LIVE pill. Copied by
  // value rather than shared, like the pill's own, but deliberately identical:
  // two different live marks in one app is how "is this live?" stops being
  // answerable at a glance.
  liveDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: colors.avoid,
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
