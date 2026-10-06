import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { TrendBuckets } from '@/types';

interface Props {
  title: string;
  trends: TrendBuckets;
  mode: 'team' | 'player';
  /** Team strip: "R", "pts" or "goals". Player strip: the stat name ("Ks", "Hits"). */
  unit?: string;
}

const KEYS: Array<{ key: keyof TrendBuckets; label: string }> = [
  { key: 'l3', label: 'L3' },
  { key: 'l5', label: 'L5' },
  { key: 'l10', label: 'L10' },
  { key: 'l20', label: 'L20' },
  { key: 'season', label: 'Season' },
];

export function TrendStrip({ title, trends, mode, unit }: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.row}>
        {KEYS.map((k) => {
          const t = trends[k.key];
          // Team "season" is the last 25 finished games in that sport, and it
          // crosses into the previous season once that window is full. The
          // player strip keeps "Season": its window is 25 or 50 by sport.
          const label = mode === 'team' && k.key === 'season' ? 'L25' : k.label;
          const primary =
            mode === 'team'
              ? t.winPct != null
                ? `${Math.round(t.winPct * 100)}%`
                : '—'
              : t.avg != null
                ? t.avg.toFixed(2)
                : '—';
          const secondary =
            mode === 'team'
              ? t.avg != null
                ? unit
                  ? `${t.avg.toFixed(1)} ${unit}`
                  : t.avg.toFixed(1)
                : '—'
              : unit ?? '';
          return (
            <View key={k.key} style={styles.cell}>
              <Text style={styles.cellLabel}>{label}</Text>
              <Text style={styles.cellValue}>{primary}</Text>
              <Text style={styles.cellSecondary}>{secondary}</Text>
              <Text style={styles.cellGames}>{t.games} G</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  title: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  cell: {
    flex: 1,
    alignItems: 'center',
  },
  cellLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  cellValue: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cellSecondary: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  cellGames: {
    fontSize: font.size.micro,
    color: colors.textTertiary,
    marginTop: 1,
  },
});
