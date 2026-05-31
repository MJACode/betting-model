import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
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
      <Text style={styles.heading}>Public betting</Text>

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
  // Lead with where the crowd sits relative to our pick.
  const side =
    bets == null
      ? ''
      : bets >= 60
        ? `The public is heavily on our side (${Math.round(bets)}% of tickets) — popular play, so watch for the line moving against you.`
        : bets >= 50
          ? `The public leans our way (${Math.round(bets)}% of tickets).`
          : `We're on the contrarian side — only ${Math.round(bets)}% of tickets back this pick.`;

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
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.md,
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
