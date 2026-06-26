import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { modelClvFor, sharpScore } from '@/lib/sharpScore';
import { formatPct } from '@/lib/format';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';
import { SharpScorePill } from './SharpScorePill';

/**
 * Detail-screen breakdown of the Sharp Score: the headline number plus the three
 * components that drive it, each with a plain-English line. BET picks only
 * (returns nothing otherwise).
 */
export function SharpScoreCard({ pick }: { pick: Pick }) {
  const sharp = sharpScore(pick);
  if (!sharp) return null;
  const clv = modelClvFor(pick.model_id);
  const { parts } = sharp;

  const bandLine =
    sharp.band === 'high'
      ? 'High conviction — clears its bar by a wide margin and/or the model has strong closing-line value.'
      : sharp.band === 'med'
        ? 'Solid — a real edge, but not a standout on every axis.'
        : 'Lean — qualifies as a BET but scores modestly on edge, CLV, or public.';

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.heading}>Sharp Score</Text>
        <SharpScorePill score={sharp.score} band={sharp.band} />
      </View>
      <Text style={styles.bandLine}>{bandLine}</Text>

      <Part
        label="Edge strength"
        points={parts.edge}
        max={40}
        sub="How far past this model's own bet threshold the pick sits."
      />
      <Part
        label="Model CLV pedigree"
        points={parts.pedigree}
        max={40}
        sub={
          parts.pedigreeKnown && clv?.beatRate != null
            ? `This model has beaten the closing line on ${formatPct(clv.beatRate, 0)} of its settled bets — the strongest evidence of a real edge.`
            : 'Not enough settled picks with closing-line data yet — scored neutral until the model proves it.'
        }
      />
      <Part
        label="Contrarian / public"
        points={parts.contrarian}
        max={20}
        sub={
          parts.contrarianKnown
            ? 'Higher when the public is light on our side (we hold the better-priced side); lower when the crowd is piled on.'
            : 'No public betting split for this market — scored neutral.'
        }
        last
      />
    </View>
  );
}

function Part({
  label,
  points,
  max,
  sub,
  last,
}: {
  label: string;
  points: number;
  max: number;
  sub: string;
  last?: boolean;
}) {
  return (
    <View style={[styles.part, last && styles.partLast]}>
      <View style={styles.partHeader}>
        <Text style={styles.partLabel}>{label}</Text>
        <Text style={styles.partPoints}>
          {Math.round(points)}<Text style={styles.partMax}> / {max}</Text>
        </Text>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: `${Math.max(0, Math.min(100, (points / max) * 100))}%` }]} />
      </View>
      <Text style={styles.partSub}>{sub}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  bandLine: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  part: {
    paddingBottom: spacing.md,
    marginBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  partLast: {
    paddingBottom: 0,
    marginBottom: 0,
    borderBottomWidth: 0,
  },
  partHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 4,
  },
  partLabel: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  partPoints: {
    fontSize: font.size.callout,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  partMax: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.regular,
  },
  track: {
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.noneSoft,
    overflow: 'hidden',
    marginBottom: 4,
  },
  fill: {
    height: 5,
    borderRadius: 3,
    backgroundColor: colors.tint,
  },
  partSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
