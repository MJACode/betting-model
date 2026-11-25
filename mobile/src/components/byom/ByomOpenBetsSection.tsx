import React, { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { ByomOpenBetCard } from '@/components/byom/ByomOpenBetCard';
import { ErrorBanner } from '@/components/ErrorState';
import { SectionTitle } from '@/components/SectionTitle';
import type { ByomOpenBet } from '@/lib/byomAlerts';
import { colors, font, opacity, spacing } from '@/lib/theme';

const TOOLTIP = {
  title: 'Bets from your models',
  body:
    'The first DraftKings line and price that fit your model’s rules, '
    + 'on games not graded yet. A later line move does not change the bet. '
    + 'These are yours only and are not in the Record.',
};

/**
 * Open bets from the member's own models.
 *
 * With no bets and no error it renders nothing, unless `emptyText` is given
 * (the model's own page, where "none yet" must read differently from "not
 * working"). A failed first load shows a banner with Retry. `cap` shows that
 * many cards and a "Show all" row (the Picks board, so official signals stay
 * near the top).
 */
export function ByomOpenBetsSection({
  title,
  bets,
  showModel = true,
  showFit = true,
  inset = true,
  cap,
  emptyText,
  error,
  retrying = false,
  onRetry,
  onOpen,
}: {
  title: string;
  bets: ByomOpenBet[];
  showModel?: boolean;
  showFit?: boolean;
  /** True in an edge-to-edge list (Picks), false inside a padded screen. */
  inset?: boolean;
  cap?: number;
  /** Shown when there are no bets and no error. Omit to render nothing. */
  emptyText?: string;
  error?: string | null;
  retrying?: boolean;
  onRetry?: () => void;
  onOpen?: (bet: ByomOpenBet) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const empty = bets.length === 0;
  if (empty && !error && !emptyText) return null;
  const capped = cap != null && !expanded && bets.length > cap;
  const shown = capped ? bets.slice(0, cap) : bets;

  return (
    <View style={styles.section}>
      <SectionTitle
        title={title}
        style={inset ? undefined : styles.flushTitle}
        tooltip={TOOLTIP}
      />
      <View style={inset ? styles.inset : undefined}>
        {empty && error && onRetry ? (
          <ErrorBanner
            what="your open bets"
            error={error}
            onRetry={onRetry}
            retrying={retrying}
            style={styles.banner}
          />
        ) : null}
        {empty && !error && emptyText ? <Text style={styles.empty}>{emptyText}</Text> : null}
        {shown.map((bet) => (
          <ByomOpenBetCard
            key={bet.alert_id}
            bet={bet}
            showModel={showModel}
            showFit={showFit}
            onPress={onOpen ? () => onOpen(bet) : undefined}
          />
        ))}
        {capped ? (
          <Pressable
            onPress={() => setExpanded(true)}
            accessibilityRole="button"
            accessibilityLabel={`Show all ${bets.length} bets from your models`}
            style={({ pressed }) => [styles.more, pressed && styles.pressed]}
          >
            <Text style={styles.moreText}>{`Show all ${bets.length}`}</Text>
          </Pressable>
        ) : null}
        {(!empty || !onRetry) && error ? <Text style={styles.error}>{`Couldn’t refresh: ${error}`}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: spacing.md },
  inset: { paddingHorizontal: spacing.lg },
  flushTitle: { paddingHorizontal: 0, marginTop: 0 },
  banner: { marginHorizontal: 0 },
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  more: {
    minHeight: 44,
    justifyContent: 'center',
  },
  pressed: { opacity: opacity.pressed },
  moreText: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  error: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});
