import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import { InfoTooltip } from '@/components/InfoTooltip';
import type { Pick } from '@/types';

interface Props {
  pick: Pick;
}

// Public betting splits (Action Network consensus). Values are 0–100 percentages
// representing the share of tickets / money on THIS pick's side. NULL on F5 and
// prop picks, and on any full-game pick where splits weren't available at score time.
export function PublicBettingCard({ pick }: Props) {
  const bets = numOrNull(pick.public_bet_pct);
  const money = numOrNull(pick.public_money_pct);

  // Nothing to show if neither split is present.
  if (bets == null && money == null) return null;

  return (
    <View style={styles.card}>
      <View style={styles.headingRow}>
        <Text style={styles.heading}>Public betting</Text>
        <InfoTooltip
          title="Money on one side"
          body={
            'These percentages are the share of bets and money on the side WE picked. ' +
            'When the crowd piles its money onto one side, the sportsbook shades that ' +
            "line to balance its risk — so the popular side gets overpriced and the value " +
            'usually sits on the OTHER side. That’s why a low public share on our pick ' +
            '(the crowd is on the other side) is a good sign — we’re already on the side ' +
            'with value. When the public is heavy on OUR side, the opposite is true: the line ' +
            'may be inflated, so treat it as a caution flag.'
          }
          accessibilityLabel="What public betting percentages mean"
        />
      </View>

      <View style={styles.statRow}>
        <Stat label="Bets on this side" value={bets} />
        <Stat label="Money on this side" value={money} />
      </View>

      <Text style={styles.note}>{interpretation(bets, money)}</Text>
      <Text style={styles.source}>Action Network consensus, on the side we picked.</Text>
    </View>
  );
}

function Stat({ label, value }: { label: string; value: number | null }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statValue}>{value != null ? `${Math.round(value)}%` : '—'}</Text>
      <Text style={styles.statLabel}>{label}</Text>
    </View>
  );
}

function interpretation(bets: number | null, money: number | null): string {
  // Lead with where the crowd sits relative to our pick, and what that implies.
  const side =
    bets == null
      ? ''
      : bets >= 60
        ? `The public is heavily on our side (${Math.round(bets)}% of tickets). One-sided money inflates a line, and the sharp angle is often the other side — so treat this as a yellow flag even though it's our pick, and watch for the line moving against you.`
        : bets >= 50
          ? `The public leans our way (${Math.round(bets)}% of tickets).`
          : `We're on the contrarian side — only ${Math.round(bets)}% of tickets back this pick. The crowd's money is piled on the other side, which inflates that line, so the value tends to sit here, where we are.`;

  // Money vs ticket divergence is the sharp signal.
  let sharp = '';
  if (bets != null && money != null) {
    const gap = money - bets;
    if (gap >= 12) {
      sharp = ' Money share outruns ticket share here — a sign sharper bettors are on this side too.';
    } else if (gap <= -12) {
      sharp = ' Money share trails ticket share — bigger bettors are lighter on this side than the ticket count suggests.';
    }
  }

  return `${side}${sharp}`.trim();
}

function numOrNull(v: number | string | null): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  statRow: {
    flexDirection: 'row',
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  stat: {
    flex: 1,
    backgroundColor: colors.bgElevated,
    borderRadius: radii.sm,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.md,
  },
  statValue: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  statLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  note: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.xs,
  },
  source: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.xs,
  },
});
