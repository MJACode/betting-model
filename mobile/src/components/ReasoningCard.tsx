import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import {
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import {
  KELLY_MULTIPLIER,
  PROB_ONLY_MODELS,
  recommendedBet,
  type KellySizingOpts,
} from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';

interface Props {
  pick: Pick;
  bankroll: number;
  kelly: KellySizingOpts;
}

export function ReasoningCard({ pick, bankroll, kelly }: Props) {
  const bet = recommendedBet(pick.kelly_fraction, bankroll, kelly);
  const isProbOnly = PROB_ONLY_MODELS.has(pick.model_id);
  const capLabel = kelly.cap != null ? `capped at ${formatPct(kelly.cap)} of bankroll` : 'no cap';
  const multLabel =
    kelly.multiplier === 1 ? '' : ` × ${kelly.multiplier.toFixed(2)}× aggressiveness`;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Why this bet?</Text>

      <Row
        label="Model probability"
        value={formatPct(pick.model_probability)}
        sub="What our XGBoost + Platt calibration says is the chance this side hits."
      />

      {pick.dk_odds != null ? (
        <Row
          label={`DK ${formatAmerican(pick.dk_odds)} implied`}
          value={formatPct(pick.dk_implied_prob)}
          sub="What DraftKings' odds imply about that chance (1 / decimal odds)."
        />
      ) : (
        <Row
          label="DK implied"
          value="N/A"
          sub="DraftKings is not pricing this market right now — this is a prob-only pick."
        />
      )}

      {!isProbOnly ? (
        <Row
          label="Edge"
          value={formatPctSigned(pick.edge)}
          tint={pick.edge >= 0.05 ? colors.bet : pick.edge <= -0.05 ? colors.avoid : undefined}
          sub={`= model ${formatPct(pick.model_probability)} − DK ${formatPct(pick.dk_implied_prob)}. Positive means we think the side is mispriced in our favor.`}
        />
      ) : (
        <Row
          label="Edge"
          value="Prob-only"
          sub="DK juices HR Over 0.5 hard. Edge is ignored — this fires when our model probability clears the threshold on its own."
        />
      )}

      {pick.signal_type === 'BET' ? (
        <Row
          label="Bet size"
          value={formatCurrency(bet)}
          sub={`Server tenth-Kelly (${KELLY_MULTIPLIER} × edge / (1 − implied))${multLabel}, ${capLabel}. Tap Settings to change bankroll or aggressiveness.`}
        />
      ) : null}

      {pick.scored_line != null ? (
        <Row label="Line at score time" value={String(pick.scored_line)} sub="The DK line when we generated this pick. If it has since moved against you, the edge may be smaller now." />
      ) : null}
    </View>
  );
}

function Row({
  label,
  value,
  sub,
  tint,
}: {
  label: string;
  value: string;
  sub?: string;
  tint?: string;
}) {
  return (
    <View style={styles.row}>
      <View style={styles.rowHeader}>
        <Text style={styles.rowLabel}>{label}</Text>
        <Text style={[styles.rowValue, tint ? { color: tint } : null]}>{value}</Text>
      </View>
      {sub ? <Text style={styles.rowSub}>{sub}</Text> : null}
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
  heading: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.md,
  },
  row: {
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 2,
  },
  rowLabel: {
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
    flexShrink: 1,
  },
  rowValue: {
    fontSize: font.size.callout,
    color: colors.textPrimary,
    fontWeight: font.weight.semibold,
  },
  rowSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
});
