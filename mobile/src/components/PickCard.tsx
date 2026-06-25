import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  expectedValue,
  formatAmerican,
  formatCurrency,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { gameStatus } from '@/lib/format';
import { bookLabel, movementFromLatest, type Movement } from '@/lib/markets';
import { modelShort } from '@/lib/modelMeta';
import { recommendedBet, passesActionFilter, type KellySizingOpts } from '@/lib/thresholds';
import { DK_GREEN, openBetslip } from '@/lib/draftkings';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick } from '@/types';
import { AddToPlayButton } from './AddToPlayButton';
import { GameStatusPill } from './GameStatusPill';
import { PickContextSheet, pickHasContext } from './PickContextSheet';
import { SignalBadge } from './SignalBadge';

interface Props {
  item: EnrichedPick;
  bankroll: number;
  kelly: KellySizingOpts;
  onPress: () => void;
  /** Whether this pick is in the manual parlay slip. */
  inPlay?: boolean;
  /** Toggle this pick in/out of the parlay slip. When set (and the pick has a
   * DK price), an "Add to parlay" button renders. */
  onTogglePlay?: () => void;
}

export function PickCard({ item, bankroll, kelly, onPress, inPlay, onTogglePlay }: Props) {
  const { pick, game } = item;
  const [contextOpen, setContextOpen] = React.useState(false);
  const hasContext = pickHasContext(pick, game?.sport);
  // Golf picks are per-player on one tournament row (home_team = event name,
  // away_team = 'FIELD') — show just the event. UFC fights are "A vs B".
  const matchup = game
    ? game.sport === 'GOLF'
      ? game.home_team
      : `${game.away_team} ${game.sport === 'UFC' ? 'vs' : '@'} ${game.home_team}`
    : '';
  const bet = recommendedBet(pick.kelly_fraction, bankroll, kelly);
  // Edge reads green only when the pick actually clears its model-specific action
  // threshold (passesActionFilter), not at a flat ±5% — a 6% edge that doesn't
  // qualify for that model should not look like a green light. AVOID stays red.
  const qualifies = passesActionFilter(pick);
  const edgeColor = qualifies
    ? colors.bet
    : pick.signal_type === 'AVOID'
      ? colors.avoid
      : colors.textSecondary;
  const ev = expectedValue(pick.model_probability, pick.dk_odds);
  const evColor =
    ev == null ? colors.textSecondary : ev > 0 ? colors.bet : ev < 0 ? colors.avoid : colors.textSecondary;
  // Pre-game only: once the game starts, the closing line (CLV) takes over.
  const movement =
    gameStatus(game).kind === 'pre' ? movementFromLatest(pick, item.latestOdds) : null;
  const movementSummary = summarizeMovement(movement);
  const showClv = pick.clv_pct != null;
  const clvColor =
    pick.clv_pct == null
      ? colors.textTertiary
      : pick.clv_pct > 0
        ? colors.bet
        : pick.clv_pct < 0
          ? colors.avoid
          : colors.textTertiary;
  // Line shopping: a non-DK book beats DK for this side. Only surface on BET
  // picks so the board isn't cluttered with line-shop chips on dead picks.
  const bestOdds = pick.signal_type === 'BET' ? item.bestOdds ?? null : null;
  // Two-tier card: show at most TWO "hero" chips, in value order
  // (movement = most actionable steam/skip > line-shop savings > CLV proof).
  // Weather + public splits are demoted to the detail screen so the
  // differentiating signals aren't drowned out. Injury always shows (safety).
  const heroOrder: string[] = [];
  if (movementSummary) heroOrder.push('movement');
  if (bestOdds) heroOrder.push('bestOdds');
  if (showClv) heroOrder.push('clv');
  const hero = new Set(heroOrder.slice(0, 2));
  const hasExtras = hero.size > 0 || Boolean(pick.injury_flag);
  // "Send this bet to DraftKings" — only actionable BET picks with a captured
  // betslip deep link get the hand-off button.
  const showDkButton = pick.signal_type === 'BET' && Boolean(pick.dk_bet_link);
  const canAddToPlay = Boolean(onTogglePlay) && pick.dk_odds != null;

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
        <Stat label="EV" value={ev == null ? '—' : formatPctSigned(ev)} color={evColor} />
        <Stat label="DK" value={formatAmerican(pick.dk_odds)} />
        <Stat label="Bet" value={pick.signal_type === 'BET' ? formatCurrency(bet) : '—'} />
      </View>

      {hasExtras ? (
        <View style={styles.extrasRow}>
          {movementSummary && hero.has('movement') ? (
            <View style={styles.extraItem}>
              <Ionicons
                name={movementSummary.icon}
                size={13}
                color={movementSummary.color}
                style={styles.extraIcon}
              />
              <Text
                style={[
                  styles.extraText,
                  { color: movementSummary.color, fontWeight: font.weight.medium },
                ]}
              >
                {movementSummary.label}
              </Text>
            </View>
          ) : null}
          {showClv && hero.has('clv') ? (
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
          {bestOdds && hero.has('bestOdds') ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="pricetag-outline"
                size={13}
                color={colors.bet}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, { color: colors.bet, fontWeight: font.weight.medium }]}>
                Best {bookLabel(bestOdds.bookmaker)} {formatAmerican(bestOdds.price)}
              </Text>
            </View>
          ) : null}
          {pick.injury_flag ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="medkit-outline"
                size={13}
                color={colors.med}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, styles.injuryText]} numberOfLines={1}>
                {pick.injury_flag}
              </Text>
            </View>
          ) : null}
        </View>
      ) : null}

      {showDkButton ? (
        <Pressable
          onPress={() => {
            void openBetslip(pick.dk_bet_link);
          }}
          style={({ pressed }) => [styles.dkButton, pressed && styles.dkButtonPressed]}
          hitSlop={6}
        >
          <Ionicons name="open-outline" size={15} color="#000" />
          <Text style={styles.dkButtonText}>Bet on DraftKings</Text>
        </Pressable>
      ) : null}

      {hasContext || canAddToPlay ? (
        <View style={styles.actionsRow}>
          {hasContext ? (
            <Pressable
              onPress={() => setContextOpen(true)}
              hitSlop={6}
              style={({ pressed }) => [styles.contextBtn, pressed && styles.pressed]}
            >
              <Ionicons name="information-circle-outline" size={15} color={colors.tint} />
              <Text style={styles.contextBtnText}>Context</Text>
            </Pressable>
          ) : (
            <View />
          )}
          {canAddToPlay ? (
            <AddToPlayButton inPlay={Boolean(inPlay)} onPress={onTogglePlay!} compact />
          ) : null}
        </View>
      ) : null}

      {contextOpen ? (
        <PickContextSheet enriched={item} visible onClose={() => setContextOpen(false)} />
      ) : null}
    </Pressable>
  );
}

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

// Line movement since the pick was scored (latest DK snapshot vs scored odds).
// Steam against the pick is the "re-check before betting" warning; a move in
// the bettor's favor is highlighted as extra value.
function summarizeMovement(
  movement: Movement | null,
): { icon: IoniconName; label: string; color: string } | null {
  if (!movement) return null;
  if (movement.severity === 'skip') {
    return {
      icon: 'warning-outline',
      color: colors.avoid,
      label: `Line ${movement.scoredLine} → ${movement.currentLine}`,
    };
  }
  const prices = `${formatAmerican(movement.scoredPrice)} → ${formatAmerican(movement.currentPrice)}`;
  if (movement.severity === 'caution') {
    return { icon: 'flame-outline', color: colors.avoid, label: `Steam ${prices}` };
  }
  return { icon: 'trending-up-outline', color: colors.bet, label: prices };
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
    color: colors.med,
    fontWeight: font.weight.medium,
  },
  dkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    backgroundColor: DK_GREEN,
    borderRadius: radii.md,
    paddingVertical: 10,
    marginTop: spacing.md,
  },
  dkButtonPressed: {
    opacity: 0.85,
  },
  dkButtonText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: '#000',
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.sm,
  },
  contextBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
    backgroundColor: colors.bgCard,
  },
  contextBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
});
