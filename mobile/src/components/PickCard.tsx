import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { modelShort } from '@/lib/modelMeta';
import { recommendedBet, type KellySizingOpts } from '@/lib/thresholds';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, GameWeather } from '@/types';
import { GameStatusPill } from './GameStatusPill';
import { SignalBadge } from './SignalBadge';

interface Props {
  item: EnrichedPick;
  bankroll: number;
  kelly: KellySizingOpts;
  onPress: () => void;
}

export function PickCard({ item, bankroll, kelly, onPress }: Props) {
  const { pick, game, weather } = item;
  const matchup = game ? `${game.away_team} @ ${game.home_team}` : '';
  const bet = recommendedBet(pick.kelly_fraction, bankroll, kelly);
  const edgeColor =
    pick.edge >= 0.05 ? colors.bet : pick.edge <= -0.05 ? colors.avoid : colors.textSecondary;
  const weatherSummary = summarizeWeather(weather);
  const publicSummary = summarizePublic(pick);
  const showClv = pick.clv_pct != null;
  const clvColor =
    pick.clv_pct == null
      ? colors.textTertiary
      : pick.clv_pct > 0
        ? colors.bet
        : pick.clv_pct < 0
          ? colors.avoid
          : colors.textTertiary;
  const hasExtras =
    showClv || Boolean(publicSummary) || Boolean(weatherSummary) || Boolean(pick.injury_flag);

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.headerRow}>
        <Text style={styles.matchup}>{matchup}</Text>
        <GameStatusPill game={game} />
      </View>

      <Text style={styles.label}>{pick.pick_label}</Text>

      <View style={styles.metaRow}>
        <View style={styles.modelChip}>
          <Text style={styles.modelChipText}>{modelShort(pick.model_id)}</Text>
        </View>
        <SignalBadge signal={pick.signal_type} small />
        {pick.confidence_tier ? (
          <View style={[styles.tierChip, tierBg(pick.confidence_tier)]}>
            <Text style={[styles.tierText, tierFg(pick.confidence_tier)]}>
              {pick.confidence_tier}
            </Text>
          </View>
        ) : null}
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(pick.model_probability)} />
        <Stat label="Edge" value={formatPctSigned(pick.edge)} color={edgeColor} />
        <Stat label="DK" value={formatAmerican(pick.dk_odds)} />
        <Stat label="Bet" value={pick.signal_type === 'BET' ? formatCurrency(bet) : '—'} />
      </View>

      {hasExtras ? (
        <View style={styles.extrasRow}>
          {showClv ? (
            <View style={styles.extraItem}>
              <Ionicons
                name={pick.clv_pct! >= 0 ? 'trending-up-outline' : 'trending-down-outline'}
                size={13}
                color={clvColor}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, { color: clvColor, fontWeight: font.weight.medium }]}>
                CLV {formatClv(pick.clv_pct!)}
              </Text>
            </View>
          ) : null}
          {publicSummary ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="people-outline"
                size={13}
                color={publicSummary.color}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, { color: publicSummary.color }]}>
                {publicSummary.label}
              </Text>
            </View>
          ) : null}
          {weatherSummary ? (
            <View style={styles.extraItem}>
              <Ionicons
                name={weatherSummary.icon}
                size={13}
                color={colors.textTertiary}
                style={styles.extraIcon}
              />
              <Text style={styles.extraText}>{weatherSummary.label}</Text>
            </View>
          ) : null}
          {pick.injury_flag ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="medkit-outline"
                size={13}
                color={colors.avoid}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, styles.injuryText]} numberOfLines={1}>
                {pick.injury_flag}
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}
    </Pressable>
  );
}

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

function summarizeWeather(
  w: GameWeather | null,
): { icon: IoniconName; label: string } | null {
  if (!w) return null;
  if (w.is_dome_game) return { icon: 'home-outline', label: 'Dome' };
  const parts: string[] = [];
  if (w.temp_f != null) parts.push(`${Math.round(w.temp_f)}°`);
  if (w.wind_mph != null) parts.push(`${Math.round(w.wind_mph)} mph`);
  if (!parts.length) return null;
  const icon: IoniconName =
    w.precip_mm != null && w.precip_mm > 0.3 ? 'rainy-outline' : 'sunny-outline';
  return { icon, label: parts.join(' · ') };
}

// Public betting splits (Action Network consensus), share of tickets / money on
// THIS pick's side. Only full-game ML/O/U/RL picks carry these — props, F5, and
// WNBA picks store NULL, so this returns null and nothing renders for them.
function summarizePublic(pick: EnrichedPick['pick']): { label: string; color: string } | null {
  const bets = numOrNull(pick.public_bet_pct);
  const money = numOrNull(pick.public_money_pct);
  if (bets == null && money == null) return null;

  const parts: string[] = [];
  if (bets != null) parts.push(`${Math.round(bets)}% bets`);
  if (money != null) parts.push(`${Math.round(money)}% money`);

  // Contrarian (we're on the light side) = possible sharp angle → highlight.
  // Heavy public agreement = line-move risk → muted.
  const color =
    bets != null && bets < 45
      ? colors.bet
      : bets != null && bets >= 65
        ? colors.textSecondary
        : colors.textTertiary;

  return { label: `Public ${parts.join(' / ')}`, color };
}

function numOrNull(v: number | string | null): number | null {
  if (v == null) return null;
  const n = typeof v === 'string' ? Number(v) : v;
  return Number.isFinite(n) ? n : null;
}

// CLV is stored in percentage points (e.g. 2.3 = beat the close by 2.3pp).
function formatClv(clvPct: number): string {
  const sign = clvPct > 0 ? '+' : '';
  return `${sign}${clvPct.toFixed(1)}pp`;
}

function Stat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.stat}>
      <Text style={styles.statLabel}>{label}</Text>
      <Text style={[styles.statValue, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

function tierBg(tier: 'HIGH' | 'MED' | 'LOW') {
  if (tier === 'HIGH') return { backgroundColor: colors.betSoft };
  if (tier === 'MED') return { backgroundColor: '#FFF4E5' };
  return { backgroundColor: colors.noneSoft };
}

function tierFg(tier: 'HIGH' | 'MED' | 'LOW') {
  if (tier === 'HIGH') return { color: colors.high };
  if (tier === 'MED') return { color: colors.med };
  return { color: colors.low };
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
    shadowColor: '#000',
    shadowOpacity: 0.05,
    shadowRadius: 4,
    shadowOffset: { width: 0, height: 1 },
    elevation: 1,
  },
  pressed: {
    opacity: 0.7,
  },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: spacing.xs,
  },
  matchup: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  modelChip: {
    backgroundColor: colors.noneSoft,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  modelChipText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  tierChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  tierText: {
    fontSize: 10,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
  },
  statsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
  stat: {
    flex: 1,
  },
  statLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  statValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  extrasRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.md,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  extraItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    maxWidth: '100%',
  },
  extraIcon: {
    marginRight: 0,
  },
  extraText: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  injuryText: {
    color: colors.avoid,
    fontWeight: font.weight.medium,
  },
});
