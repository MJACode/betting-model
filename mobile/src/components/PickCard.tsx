import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  expectedValue,
  formatAmerican,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { gameDayLabelET, gameStatus } from '@/lib/format';
import {
  bestHandoffForPick,
  bookLabel,
  formatSideLine,
  gameMarketForModel,
  heroAmericanForPick,
  marketForPick,
  movementFromLatest,
  numOrNull,
  pickTimingInfo,
  splitPickTitle,
  type Movement,
} from '@/lib/markets';
import { stakeFor, formatUnits, passesActionFilter, isUnlockedPreview } from '@/lib/thresholds';
import { contrarianTag, publicSplit, sharpScore } from '@/lib/sharpScore';
import { colors, font, radii, spacing } from '@/lib/theme';
import { decisionEdge, decisionOdds, hasPricedLine } from '@/lib/decisionPrice';
import { DK_GREEN, openBookBetslip } from '@/lib/sportsbookLinks';
import type { EnrichedPick, LiveGameStateRow, PickSide } from '@/types';
import { AddToPlayButton } from './AddToPlayButton';
import { TrackButton } from './TrackButton';
import { GameStatusPill } from './GameStatusPill';
import { SharpScorePill } from './SharpScorePill';
import { SignalBadge } from './SignalBadge';

interface Props {
  item: EnrichedPick;
  onPress: () => void;
  /** Whether this bet is tracked (Performance-tab scoring + line alerts). */
  tracked?: boolean;
  /** Toggle tracking. When set, a "Track" button renders on any unsettled,
   * non-live pick. */
  onToggleTrack?: () => void;
  /** Whether this pick is in the user's betslip. */
  inSlip?: boolean;
  /** Toggle betslip membership. When set, an "Add to betslip" button renders on
   * priced, unsettled, non-preview picks — a betslip leg needs a payout, so
   * prob-only picks (no decision price) never offer it. */
  onToggleSlip?: () => void;
  /** Freshest live snapshot for this pick's game — drives the score + inning
   * beside the LIVE badge. Omitted (or null) falls back to a bare badge. */
  liveState?: LiveGameStateRow | null;
  /** Today board only: BET/AVOID/NONE sits immediately before the label.
   * Signals and Live are already BET-only, so the small badge is omitted. */
  showSignalBadge?: boolean;
}

export function PickCard({
  item, onPress, tracked, onToggleTrack, inSlip, onToggleSlip, liveState,
  showSignalBadge = false,
}: Props) {
  const { pick, game } = item;
  // Golf picks are per-player on one tournament row (home_team = event name,
  // away_team = 'FIELD') — show just the event. UFC fights are "A vs B".
  const matchup = game
    ? game.sport === 'GOLF'
      ? game.home_team
      : `${game.away_team} ${game.sport === 'UFC' ? 'vs' : '@'} ${game.home_team}`
    : '';

  // Edge reads green only when the pick actually clears its model-specific action
  // threshold (passesActionFilter), not at a flat ±5% — a 6% edge that doesn't
  // qualify for that model should not look like a green light. AVOID stays red.
  const qualifies = passesActionFilter(pick);
  // gradeGood / gradeBad, not bet/avoid: Edge is now the hero number and
  // colors.bet is 2.22:1 on bgCard (theme.ts). The ramp already exists for
  // a readable good/bad (UX review).
  const edgeColor = qualifies
    ? colors.gradeGood
    : pick.signal_type === 'AVOID'
      ? colors.gradeBad
      : colors.textSecondary;
  // EV, edge and stake at the price the pick was DECIDED at (2026-09-09).
  const ev = expectedValue(pick.model_probability, decisionOdds(pick));
  const evColor =
    ev == null ? colors.textSecondary : ev > 0 ? colors.bet : ev < 0 ? colors.avoid : colors.textSecondary;
  // Pre-game only: once the game starts, the closing line (CLV) takes over.
  const status = gameStatus(game, liveState);
  const movement =
    status.kind === 'pre'
      ? movementFromLatest(pick, item.latestOdds, item.bookRows)
      : null;
  // The visible pill prefixes a future day ("Tue 9/29 · 5:00 PM ET"). The
  // card's accessibilityLabel replaces its children, so VoiceOver has to
  // hear that same string or a next-Tuesday NHL bet sounds like tonight.
  const preWhen =
    status.kind === 'pre' && status.timeLabel
      ? [gameDayLabelET(game?.commence_time), status.timeLabel].filter(Boolean).join(' · ')
      : null;
  const movementSummary = summarizeMovement(movement, pick.pick_side, gameMarketForModel(pick.model_id));
  const showClv = pick.clv_pct != null;
  const clvColor =
    pick.clv_pct == null
      ? colors.textTertiary
      : pick.clv_pct > 0
        ? colors.bet
        : pick.clv_pct < 0
          ? colors.avoid
          : colors.textTertiary;

  const heroPrice = heroAmericanForPick(pick, item.latestOdds, item.bookRows);
  // Compare home-relative as numbers: PostgREST can send NUMERIC as a string,
  // and "-1" !== -1 would print a line on every card. Print from the pick's
  // side so an away spread that has moved (NYJ +5, scored −5, Now −4.5)
  // never reads as “−4.5”.
  const quoteLineRaw =
    heroPrice &&
    numOrNull(heroPrice.line) != null &&
    numOrNull(pick.scored_line) != null &&
    numOrNull(heroPrice.line) !== numOrNull(pick.scored_line)
      ? numOrNull(heroPrice.line)
      : null;
  const quoteLine =
    quoteLineRaw == null
      ? null
      : formatSideLine(
          quoteLineRaw,
          pick.pick_side,
          gameMarketForModel(pick.model_id) ?? marketForPick(pick),
        );

  // Stake stays on the deciding price, never the Now snapshot — §6.
  const stake = stakeFor(pick.kelly_fraction, decisionOdds(pick));
  // Unlocked look-ahead (future UFC/golf): the line shows, but nothing on the
  // card may read as a signal — the pick re-scores until it locks on game day.
  const preview = isUnlockedPreview(pick);
  const sharp = preview ? null : sharpScore(pick);
  const contra = contrarianTag(pick);
  // Where the crowd is, for every pick that carries a split. contrarianTag only
  // speaks on a BET sitting in a decisive band, but nearly all captured splits
  // land on NONE/AVOID rows — and the Public sort orders the whole board by this
  // number, so a card it ranks has to print it. Neutral grey, no verdict: the
  // green/amber judged version above owns the cases it covers.
  const crowd = contra ? null : publicSplit(pick);
  // Two-tier extras: show at most TWO chips besides injury / preview / contra.
  const heroOrder: string[] = [];
  if (movementSummary) heroOrder.push('movement');
  if (showClv) heroOrder.push('clv');
  const hero = new Set(heroOrder.slice(0, 2));
  // WHEN this bet posted. Timing is part of the pick, not metadata (§1c).
  const timing = pick.result == null ? pickTimingInfo(pick) : null;
  const previewLabel = preview
    ? pick.sport === 'GOLF'
      ? 'Preview — locks when the tournament starts'
      : 'Preview — locks fight-day morning'
    : null;
  const hasExtras =
    Boolean(previewLabel) || hero.size > 0 || Boolean(contra) || Boolean(crowd) || Boolean(pick.injury_flag);
  // One book CTA on the list card. Full BookLinesRow stays on Pick Detail.
  const handoff = !preview && pick.signal_type === 'BET'
    ? bestHandoffForPick(pick, item.bookRows, heroPrice)
    : null;
  const canTrack = Boolean(onToggleTrack) && pick.result == null;
  // Betslip — priced (decision price, not dk_odds), unsettled, non-preview.
  const canSlip =
    Boolean(onToggleSlip) && hasPricedLine(pick) && pick.result == null && !preview;
  // Sharp or confidence — not both, and never stacked on top of a badge-less
  // BET-only board as a third equal chip. Sharp wins when both exist.
  const showSharp = Boolean(sharp);
  const showTier = Boolean(pick.confidence_tier) && !showSharp;
  const stakeCaption =
    pick.signal_type !== 'BET' || preview
      ? null
      : stake.priced
        ? `${formatUnits(stake.risk)} → ${formatUnits(stake.win)}`
        : formatUnits(stake.conviction);
  const caption = [
    `Model ${formatPct(pick.model_probability)}`,
    ev == null ? null : `EV ${formatPctSigned(ev)}`,
    stakeCaption,
  ]
    .filter((p): p is string => p != null)
    .join(' · ');
  const { primary: titlePrimary, secondary: titleSecondary } = splitPickTitle(pick);

  return (
    // The card tap is the only route to the pick's breakdown now that the
    // Context button is gone, so it has to announce itself: a settled pick
    // renders no action buttons at all, and without this VoiceOver reads the
    // card as inert text (UX review, 2026-09-05).
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={[
        matchup,
        preWhen,
        pick.pick_label,
        pick.signal_type,
        `Edge ${formatPctSigned(decisionEdge(pick))}`,
        heroPrice
          ? `${heroPrice.kind === 'now' ? 'Now' : heroPrice.kind === 'locked' ? 'Locked' : ''} ${heroPrice.price == null ? 'unavailable' : formatAmerican(heroPrice.price)} ${bookLabel(heroPrice.book)}`.trim()
          : null,
      ]
        .filter((p): p is string => Boolean(p))
        .join('. ')}
      accessibilityHint="Opens the full breakdown, including recent form and matchup context."
      style={({ pressed }) => [styles.card, pressed && styles.pressed]}
    >
      <View style={styles.headerRow}>
        <Text style={styles.matchup} numberOfLines={1}>
          {matchup}
        </Text>
        {/* Live clock stays on this pill (Fixtured-style score + period).
            Do not invent a second clock chrome on the card. */}
        <GameStatusPill game={game} live={liveState} />
      </View>

      <View style={styles.titleBlock}>
        <View style={styles.labelRow}>
          {preview ? (
            <View style={[styles.labelChip, styles.previewBadge]}>
              <Text style={styles.previewBadgeText}>PREVIEW</Text>
            </View>
          ) : showSignalBadge ? (
            <View style={styles.labelChip}>
              <SignalBadge signal={pick.signal_type} small />
            </View>
          ) : null}
          <View style={styles.labelStack}>
            <Text
              style={styles.label}
              numberOfLines={1}
              {...(titleSecondary
                ? { adjustsFontSizeToFit: true, minimumFontScale: 0.75 }
                : {})}
            >
              {titlePrimary}
            </Text>
            {titleSecondary ? (
              <Text style={styles.playerName} numberOfLines={1}>
                {titleSecondary}
              </Text>
            ) : null}
          </View>
          {showSharp && sharp ? (
            <View style={styles.labelChip}>
              <SharpScorePill score={sharp.score} band={sharp.band} />
            </View>
          ) : null}
          {showTier && pick.confidence_tier ? (
            <View style={[styles.labelChip, styles.tierChip, tierBg(pick.confidence_tier)]}>
              <Text style={[styles.tierText, tierFg(pick.confidence_tier)]}>
                {pick.confidence_tier}
              </Text>
            </View>
          ) : null}
        </View>
      </View>

      <View style={styles.heroRow}>
        <View style={styles.heroEdgeBlock}>
          <Text style={[styles.heroEdge, { color: edgeColor }]}>
            {formatPctSigned(decisionEdge(pick))}
          </Text>
          <Text style={styles.heroEdgeLabel}>Edge</Text>
        </View>
        {heroPrice ? (
          <View style={styles.heroPriceBlock}>
            <View style={heroPrice.kind === 'now' ? styles.pricePill : styles.heroPriceRow}>
              {heroPrice.kind !== 'decision' ? (
                <Text style={styles.nowTag}>{heroPrice.kind === 'now' ? 'Now' : 'Locked'}</Text>
              ) : null}
              <Text style={styles.heroPrice}>
                {heroPrice.price == null
                  ? '—'
                  : quoteLine != null
                    ? // Already flipped via formatSideLine; do not template-interpolate
                      // the identifier the raw-home scan lists.
                      <>{quoteLine} {formatAmerican(heroPrice.price)}</>
                    : formatAmerican(heroPrice.price)}
              </Text>
              <Text style={styles.heroBook}>{bookLabel(heroPrice.book)}</Text>
            </View>
            {heroPrice.showLockedCaption ? (
              <Text style={styles.lockedCaption}>
                Locked {formatAmerican(heroPrice.lockedPrice)}
              </Text>
            ) : null}
          </View>
        ) : null}
      </View>

      {caption ? (
        <Text style={styles.captionLine} numberOfLines={2}>
          {caption}
        </Text>
      ) : null}

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
          {contra ? (
            <View style={styles.extraItem}>
              <Ionicons
                name={contra.tone === 'sharp' ? 'shield-checkmark-outline' : 'people-outline'}
                size={13}
                color={contra.tone === 'sharp' ? colors.bet : colors.med}
                style={styles.extraIcon}
              />
              <Text
                style={[
                  styles.extraText,
                  {
                    color: contra.tone === 'sharp' ? colors.bet : colors.med,
                    fontWeight: font.weight.medium,
                  },
                ]}
              >
                {contra.label} · {Math.round(contra.betPct)}% public
              </Text>
            </View>
          ) : null}
          {crowd ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="people-outline"
                size={13}
                color={colors.textTertiary}
                style={styles.extraIcon}
              />
              <Text style={styles.extraText}>
                {Math.round(crowd.betPct)}% public on this side
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
          {previewLabel ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="lock-open-outline"
                size={13}
                color={colors.textTertiary}
                style={styles.extraIcon}
              />
              <Text style={styles.extraText}>{previewLabel}</Text>
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

      {handoff || canTrack || canSlip ? (
        <View style={styles.actionsRow}>
          {handoff ? (
            <Pressable
              onPress={() => {
                void openBookBetslip(handoff.bookmaker, handoff.link);
              }}
              hitSlop={{ top: 8, bottom: 8, left: 4, right: 4 }}
              accessibilityRole="button"
              accessibilityLabel={`${handoff.verb} at ${bookLabel(handoff.bookmaker)}, ${formatAmerican(handoff.price)}`}
              style={({ pressed }) => [
                styles.handoff,
                handoff.bookmaker === 'draftkings' && styles.handoffDk,
                pressed && styles.pressed,
              ]}
            >
              <Text
                style={[styles.handoffText, handoff.bookmaker === 'draftkings' && styles.handoffTextDk]}
                numberOfLines={1}
              >
                {handoff.verb} {bookLabel(handoff.bookmaker)} {formatAmerican(handoff.price)}
              </Text>
            </Pressable>
          ) : (
            <View />
          )}
          <View style={styles.actionsRight}>
            {canSlip ? (
              <AddToPlayButton inPlay={Boolean(inSlip)} onPress={onToggleSlip!} compact />
            ) : null}
            {canTrack ? (
              <TrackButton tracked={Boolean(tracked)} onPress={onToggleTrack!} compact />
            ) : null}
          </View>
        </View>
      ) : null}

      {timing ? (
        <View style={styles.timingRow}>
          <Ionicons
            name={timing.kind === 'live' ? 'lock-closed-outline' : 'time-outline'}
            size={13}
            color={timing.kind === 'live' ? colors.bet : colors.textTertiary}
            style={styles.extraIcon}
          />
          <Text
            style={[
              styles.extraText,
              styles.timingText,
              timing.kind === 'live'
                ? { color: colors.bet, fontWeight: font.weight.medium }
                : null,
            ]}
          >
            {timing.label}
          </Text>
        </View>
      ) : null}
    </Pressable>
  );
}

type IoniconName = React.ComponentProps<typeof Ionicons>['name'];

// Line movement since the pick was scored (latest snapshot vs scored odds).
// Steam against the pick is the "re-check before betting" warning; a move in
// the bettor's favor is highlighted as extra value.
function summarizeMovement(
  movement: Movement | null,
  side: PickSide,
  market: string | null,
): { icon: IoniconName; label: string; color: string } | null {
  if (!movement) return null;
  // Lines render from the PICK'S side (spreads are stored home-relative), so a
  // pick labeled "NYJ +5" never shows "-5" beside it.
  const lines =
    `Line ${formatSideLine(movement.scoredLine, side, market)}` +
    ` → ${formatSideLine(movement.currentLine, side, market)}`;
  if (movement.severity === 'skip') {
    return { icon: 'warning-outline', color: colors.avoid, label: lines };
  }
  // Line-only (NFL) picks compare lines, never cross-book prices.
  if (movement.lineOnly) {
    return { icon: 'trending-up-outline', color: colors.bet, label: lines };
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

function tierBg(tier: 'HIGH' | 'MED' | 'LOW') {
  if (tier === 'HIGH') return { backgroundColor: colors.betSoft };
  if (tier === 'MED') return { backgroundColor: colors.medSoft };
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
    borderRadius: radii.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xs,
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
    // flex + truncation so a long matchup can never push the live score /
    // inning / LIVE badge off the right edge of the card.
    flexShrink: 1,
    marginRight: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  // Signal-first on Today: badge immediately before the label. Wraps so a
  // long NFL prop + sharp pill cannot clip at accessibility sizes (HIG).
  titleBlock: {
    marginBottom: spacing.xs,
  },
  labelRow: {
    flexDirection: 'row',
    // Top of the stack (the 17pt bet), not the mid-point of a two-line
    // prop title — otherwise badge / sharp / tier float between bet and
    // player. flexWrap + rowGap still let a long bet + pills wrap at
    // accessibility sizes (HIG); chips stay on the primary line of
    // whichever wrap row they land on.
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: spacing.sm,
    rowGap: spacing.xs,
  },
  // 2pt nudge: nano/caption pills (~16–18pt) vs 17pt headline line-box
  // (~22pt). Keeps the chip optically on the bet when Dynamic Type
  // grows the player caption underneath.
  labelChip: {
    marginTop: 2,
    alignSelf: 'flex-start',
  },
  // Bet + player name stack so the badge / sharp / tier stay on the primary
  // row (props only). Game markets render a single headline in this stack.
  labelStack: {
    flexGrow: 1,
    flexShrink: 1,
    flexBasis: 0,
    minWidth: 0,
  },
  label: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  playerName: {
    marginTop: 1,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  tierChip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
  },
  tierText: {
    fontSize: font.size.nano,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
  },
  heroRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    gap: spacing.md,
    marginBottom: spacing.xs,
  },
  heroEdgeBlock: {
    flexShrink: 0,
  },
  heroEdge: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    fontVariant: ['tabular-nums'],
    color: colors.textPrimary,
  },
  heroEdgeLabel: {
    marginTop: 1,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.medium,
  },
  heroPriceBlock: {
    flexShrink: 1,
    alignItems: 'flex-end',
  },
  heroPriceRow: {
    flexDirection: 'row',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: 4,
  },
  // Public Options Hub analog: the bettable American lives in a pill so Now
  // reads as the emphasized price, not another caption next to Edge.
  pricePill: {
    flexDirection: 'row',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    justifyContent: 'flex-end',
    gap: 4,
    backgroundColor: colors.bgGrouped,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  nowTag: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  heroPrice: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    fontVariant: ['tabular-nums'],
    color: colors.textPrimary,
  },
  heroBook: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  lockedCaption: {
    marginTop: 1,
    fontSize: font.size.caption,
    color: colors.textSecondary,
    fontVariant: ['tabular-nums'],
  },
  captionLine: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: spacing.xs,
  },
  extrasRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.xs,
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
  // Neutral pill for unlocked look-ahead picks — deliberately NOT the green
  // BET treatment: the pick re-scores until it locks on game day.
  previewBadge: {
    borderRadius: radii.pill,
    paddingVertical: 3,
    paddingHorizontal: 6,
    backgroundColor: colors.noneSoft,
    alignSelf: 'flex-start',
  },
  previewBadgeText: {
    fontSize: font.size.nano,
    fontWeight: font.weight.semibold,
    letterSpacing: 0.4,
    color: colors.none,
  },
  injuryText: {
    color: colors.med,
    fontWeight: font.weight.medium,
  },
  actionsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
    marginTop: spacing.xs,
  },
  actionsRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    flexShrink: 0,
  },
  handoff: {
    flexShrink: 1,
    minHeight: 36,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: radii.pill,
    backgroundColor: colors.bgGrouped,
    justifyContent: 'center',
  },
  handoffDk: {
    backgroundColor: DK_GREEN,
  },
  handoffText: {
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    fontVariant: ['tabular-nums'],
  },
  handoffTextDk: {
    color: colors.textPrimary,
  },
  // The post-time footer: last line of the card, under the action buttons.
  timingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.xs,
  },
  // A single Text in a row container does not shrink by default, so the live
  // "Locked … — bet of record" label would overflow the card instead of
  // wrapping (UX review, 2026-09-03).
  timingText: {
    flexShrink: 1,
  },
});
