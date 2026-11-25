import React from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { ByomOpenBetCard } from '@/components/byom/ByomOpenBetCard';
import { SectionTitle } from '@/components/SectionTitle';
import type { ByomOpenBet } from '@/lib/byomAlerts';
import { colors, font, spacing } from '@/lib/theme';

/**
 * Open bets from the member's own models. Renders nothing when there are
 * none, so a member with no models (or before the migration) sees no gap.
 */
export function ByomOpenBetsSection({
  title,
  bets,
  showModel = true,
  inset = true,
  error,
  onOpen,
}: {
  title: string;
  bets: ByomOpenBet[];
  showModel?: boolean;
  /** True in an edge-to-edge list (Picks), false inside a padded screen. */
  inset?: boolean;
  /** A failed refresh. Shown under the cards already loaded. */
  error?: string | null;
  onOpen?: (bet: ByomOpenBet) => void;
}) {
  if (bets.length === 0) return null;
  return (
    <View style={styles.section}>
      <SectionTitle
        title={title}
        style={inset ? undefined : styles.flushTitle}
        tooltip={{
          title: 'Bets from your models',
          body:
            'The first DraftKings line and price that fit your model’s rules, '
            + 'on games not graded yet. A later line move does not change the bet. '
            + 'These are yours only and are not in the Record.',
        }}
      />
      <View style={inset ? styles.inset : undefined}>
      {bets.map((bet) => (
        <ByomOpenBetCard
          key={bet.alert_id}
          bet={bet}
          showModel={showModel}
          onPress={onOpen ? () => onOpen(bet) : undefined}
        />
      ))}
      {error ? <Text style={styles.error}>{`Couldn’t refresh: ${error}`}</Text> : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  section: { marginBottom: spacing.md },
  inset: { paddingHorizontal: spacing.lg },
  flushTitle: { paddingHorizontal: 0, marginTop: 0 },
  error: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
});
