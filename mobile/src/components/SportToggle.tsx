import React from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { LiveDot } from '@/components/LiveDot';
import { colors, font, radii, spacing } from '@/lib/theme';
import { SPORTS, useSportFilter, type Sport } from '@/hooks/useSportFilter';
import { sportChipState } from '@/lib/loadState';
import { reachFrame } from '@/lib/a11y';

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
 * Pass undefined while the board is unknown (loading, slow, failed): every chip
 * is then neutral and none says "no picks today" (lib/loadState
 * sportChipsAvailable / sportChipState, Designer #845).
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
/** In-bounds room above a segment: wrap marginTop (spacing.sm) + padding 2. */
const TOGGLE_ROOM_ABOVE = spacing.sm + 2;

/** Chip height at default text size: 4 + 4 padding + a 13pt line (~15.5). */
export const TOGGLE_CHIP_H = 23;

export function SportToggle({
  available,
  signalCounts,
  liveSports,
  reachAbove = 0,
  reachBelow = 0,
  marginTop = 0,
}: {
  available?: Set<string>;
  signalCounts?: Record<string, number>;
  liveSports?: Set<string>;
  /**
   * H9: points of whitespace / non-interactive content above the row that its
   * chips' touch area may cover (lib/a11y reachFrame). Each screen passes what
   * its own layout has; 0 keeps the in-bounds 10pt.
   */
  reachAbove?: number;
  /**
   * Points of the gap below the row it may take. A later sibling sits there,
   * so the frame is raised; pass HALF of a gap shared with the next row's
   * chips so the two tile.
   */
  reachBelow?: number;
  /** The frame's own margin before the reach (e.g. a wrapper's margin). */
  marginTop?: number;
}) {
  const reach = reachFrame(reachAbove, reachBelow, { raise: reachBelow > 0, marginTop });
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
      style={reach.frame}
      contentContainerStyle={[styles.scroll, reach.content]}
      keyboardShouldPersistTaps="handled"
    >
      <View style={styles.wrap} accessibilityRole="tablist">
        {SPORTS.map((s: Sport, i: number) => {
          const active = s === sport;
          const count = signalCounts?.[s] ?? 0;
          const isLive = liveSports?.has(s) ?? false;
          const { muted, label } = sportChipState({ sport: s, active, available, count, live: isLive });
          return (
            <Pressable
              key={s}
              onPress={() => setSport(s)}
              onLayout={(e) => {
                offsets.current[s] = e.nativeEvent.layout.x;
                if (s === sport) scrollToActive();
              }}
              // ~23pt tall, the smallest target on the Stats board. Slop, not
              // height: this row is on three tabs (UX review, 2026-09-12). A
              // horizontal ScrollView only takes touches inside its own bounds,
              // so the slop is exactly the room inside them: the wrap's 8pt
              // margin + 2pt padding above and 2pt below (35pt), plus whatever
              // the screen lets the frame reach (reachAbove / reachBelow; Picks
              // and Models reach 45pt). Chips abut, so no slop between them —
              // only the row's two ends take the wrap's 2pt padding.
              hitSlop={{
                top: TOGGLE_ROOM_ABOVE + reachAbove,
                bottom: 2 + reachBelow,
                left: i === 0 ? 2 : 0,
                right: i === SPORTS.length - 1 ? 2 : 0,
              }}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              accessibilityLabel={label}
              style={({ pressed }) => [
                styles.segment,
                active && styles.segmentActive,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.segmentInner}>
                {isLive ? <LiveDot /> : null}
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
    gap: spacing.xs,
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
  // Dark on the green fill: white on `bet` was 2.22:1 on a 10pt count;
  // textPrimary is 9.46:1 (audit H6). The fill stays green — the one green
  // count badge PATTERNS §D8 allows, because it counts BETs.
  badgeText: {
    fontSize: font.size.nano,
    lineHeight: 13,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
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
  // No extra opacity: tertiary at 0.7 was 2.16:1 and read as disabled, but
  // the segment is tappable. textTertiary alone is 4.56:1 on noneSoft (M17).
  labelMuted: {
    color: colors.textTertiary,
  },
});
