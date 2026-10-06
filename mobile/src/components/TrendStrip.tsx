import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import {
  TEAM_WINDOW_SIZE,
  teamCellAccessibilityLabel,
  teamGamesRow,
  teamSeasonNote,
} from '@/lib/teamForm';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { TrendBuckets } from '@/types';

interface Props {
  title: string;
  trends: TrendBuckets;
  mode: 'team' | 'player';
  /** Team strip: "R", "pts" or "goals". Player strip: the stat name ("Ks", "Hits"). */
  unit?: string;
  /** Team strip: "runs", "points" or "goals". What VoiceOver speaks. */
  spokenUnit?: string;
  /** Games in the fetched window from the pick's season. Null when the season is unknown. */
  seasonGames?: number | null;
}

const KEYS: Array<{ key: keyof TrendBuckets; label: string }> = [
  { key: 'l3', label: 'L3' },
  { key: 'l5', label: 'L5' },
  { key: 'l10', label: 'L10' },
  { key: 'l20', label: 'L20' },
  { key: 'season', label: 'Season' },
];

export function TrendStrip({ title, trends, mode, unit, spokenUnit, seasonGames }: Props) {
  const note =
    mode === 'team'
      ? teamSeasonNote(seasonGames, {
          l3: trends.l3.games,
          l5: trends.l5.games,
          l10: trends.l10.games,
          l20: trends.l20.games,
          l25: trends.season.games,
        })
      : null;
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
          const windowSize = TEAM_WINDOW_SIZE[k.key] ?? t.games;
          // Team: "4 games" only when the window is short. "G" in hockey is
          // goals, and a failed fetch must not print "0 G". Player keeps "G"
          // — that window is not 3/5/10/20/25 — and still hides a zero.
          const gamesLabel =
            mode === 'team'
              ? teamGamesRow(t.games, windowSize)
              : t.games > 0
                ? `${t.games} G`
                : null;
          return (
            <View
              key={k.key}
              style={styles.cell}
              accessible={mode === 'team'}
              accessibilityLabel={
                mode === 'team'
                  ? teamCellAccessibilityLabel({
                      window: windowSize,
                      games: t.games,
                      winPct: t.winPct,
                      avg: t.avg,
                      spokenUnit: spokenUnit ?? '',
                      seasonGames,
                    })
                  : undefined
              }
            >
              <Text style={styles.cellLabel}>{label}</Text>
              <Text style={styles.cellValue}>{primary}</Text>
              <Text style={styles.cellSecondary}>{secondary}</Text>
              {gamesLabel ? <Text style={styles.cellGames}>{gamesLabel}</Text> : null}
            </View>
          );
        })}
      </View>
      {note ? <Text style={styles.note}>{note}</Text> : null}
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
  note: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  cellLabel: {
    textAlign: 'center',
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  cellValue: {
    textAlign: 'center',
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cellSecondary: {
    textAlign: 'center',
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  cellGames: {
    textAlign: 'center',
    fontSize: font.size.micro,
    color: colors.textTertiary,
    marginTop: 1,
  },
});
