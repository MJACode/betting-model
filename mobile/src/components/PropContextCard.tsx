import React from 'react';
import { StyleSheet, Text, View } from 'react-native';
import { MODEL_META } from '@/lib/modelMeta';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { Pick } from '@/types';
import type { PropContext } from '@/hooks/usePropContext';

interface Props {
  pick: Pick;
  context: PropContext;
}

interface RowDef {
  label: string;
  value: string;
  tint?: string;
}

/**
 * "Matchup" card for MLB prop picks — the Statcast / platoon / umpire / lineup
 * context the prop models already use as features, surfaced to the user.
 */
export function PropContextCard({ pick, context }: Props) {
  const metaType = MODEL_META[pick.model_id]?.type;
  if (metaType !== 'pitcher_prop' && metaType !== 'batter_prop') return null;
  const { savant, batHand, umpire, lineup, loading } = context;
  if (loading) return null;

  const rows: RowDef[] = [];
  const pct = (v: number | null, digits = 1) => (v == null ? null : `${Number(v).toFixed(digits)}%`);

  if (metaType === 'pitcher_prop' && savant) {
    push(rows, 'xERA', savant.xera != null ? Number(savant.xera).toFixed(2) : null);
    push(rows, 'K rate', pct(savant.k_pct));
    push(rows, 'Whiff rate', pct(savant.whiff_pct));
    push(rows, 'CSW rate', pct(savant.csw_pct));
    push(
      rows,
      'Avg fastball',
      savant.avg_velocity != null ? `${Number(savant.avg_velocity).toFixed(1)} mph` : null,
    );
    if (pick.model_id === 'mlb_prop_pitcher_hits' || pick.model_id === 'mlb_prop_pitcher_er') {
      push(rows, 'Groundball rate', pct(savant.gb_pct));
    }
  }

  if (metaType === 'batter_prop') {
    if (savant) {
      push(rows, 'Barrel rate', pct(savant.barrel_pct));
      push(rows, 'Hard-hit rate', pct(savant.hard_hit_pct));
      push(rows, 'xBA', savant.xba != null ? Number(savant.xba).toFixed(3) : null);
      push(rows, 'xSLG', savant.xslg != null ? Number(savant.xslg).toFixed(3) : null);
      if (pick.model_id === 'mlb_prop_batter_hr') {
        push(
          rows,
          'Launch angle',
          savant.launch_angle != null ? `${Number(savant.launch_angle).toFixed(1)}°` : null,
        );
      }
      if (pick.model_id === 'mlb_prop_batter_sb' || pick.model_id === 'mlb_prop_batter_runs') {
        push(
          rows,
          'Sprint speed',
          savant.sprint_speed != null ? `${Number(savant.sprint_speed).toFixed(1)} ft/s` : null,
        );
      }
    }

    // Platoon: batter hand vs the opposing starter's throw hand (both stored).
    const throwHand = pick.pitcher_throw_hand;
    if (batHand && throwHand) {
      const advantage = batHand === 'S' || batHand !== throwHand;
      rows.push({
        label: 'Platoon',
        value: `Bats ${batHand} vs ${throwHand}HP${advantage ? ' — edge' : ''}`,
        tint: advantage ? colors.bet : undefined,
      });
    }

    if (lineup?.batting_order != null) {
      rows.push({
        label: 'Lineup',
        value: `Hitting ${ordinal(lineup.batting_order)}${lineup.is_confirmed ? ' (confirmed)' : ''}`,
      });
    }
  }

  if (umpire && (umpire.k_plus_minus != null || umpire.k_per_game != null)) {
    const pm = umpire.k_plus_minus;
    const pmStr =
      pm != null ? `${pm > 0 ? '+' : ''}${Number(pm).toFixed(1)} K/gm vs avg` : `${umpire.k_per_game} K/gm`;
    rows.push({
      label: 'HP umpire',
      value: `${umpire.umpire_name} · ${pmStr}`,
      tint:
        pm != null && pm >= 0.5 && pick.pick_side === 'over'
          ? colors.bet
          : pm != null && pm <= -0.5 && pick.pick_side === 'over'
            ? colors.avoid
            : undefined,
    });
  }

  if (rows.length === 0) return null;

  return (
    <View style={styles.card}>
      <Text style={styles.heading}>Matchup</Text>
      {rows.map((r) => (
        <View key={r.label} style={styles.row}>
          <Text style={styles.rowLabel}>{r.label}</Text>
          <Text style={[styles.rowValue, r.tint ? { color: r.tint } : null]}>{r.value}</Text>
        </View>
      ))}
      <Text style={styles.caption}>Season Statcast data — the same inputs the model trains on.</Text>
    </View>
  );
}

function push(rows: RowDef[], label: string, value: string | null) {
  if (value != null) rows.push({ label, value });
}

function ordinal(n: number): string {
  const suffix =
    n % 10 === 1 && n !== 11 ? 'st' : n % 10 === 2 && n !== 12 ? 'nd' : n % 10 === 3 && n !== 13 ? 'rd' : 'th';
  return `${n}${suffix}`;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  heading: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginBottom: 4,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    paddingVertical: 5,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separator,
  },
  rowLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  rowValue: {
    fontSize: font.size.footnote,
    color: colors.textPrimary,
    fontWeight: font.weight.medium,
  },
  caption: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
});
