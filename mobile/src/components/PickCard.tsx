import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  expectedValue,
  formatAmerican,
  formatPct,
  formatPctSigned,
} from '@/lib/format';
import { gameStatus } from '@/lib/format';
import {
  bookLabel,
  displayQuoteForPick,
  formatSideLine,
  gameMarketForModel,
  movementFromLatest,
  pickTimingInfo,
  MODEL_BOOK,
  type Movement,
} from '@/lib/markets';
import { modelShort } from '@/lib/modelMeta';
import { stakeFor, formatUnits, passesActionFilter, type KellySizingOpts, isUnlockedPreview } from '@/lib/thresholds';
import { contrarianTag, publicSplit, sharpScore } from '@/lib/sharpScore';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, LiveGameStateRow, PickSide } from '@/types';
import { AddToPlayButton } from './AddToPlayButton';
import { BookLinesRow } from './BookLinesRow';
import { TrackButton } from './TrackButton';
import { GameStatusPill } from './GameStatusPill';
import { PickContextSheet, pickHasContext } from './PickContextSheet';
import { SharpScorePill } from './SharpScorePill';
import { SignalBadge } from './SignalBadge';

interface Props {
  item: EnrichedPick;
  bankroll: number;
  kelly: KellySizingOpts;
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
   * prob-only picks (null dk_odds) never offer it. */
  onToggleSlip?: () => void;
  /** Freshest live snapshot for this pick's game — drives the score + inning
   * beside the LIVE badge. Omitted (or null) falls back to a bare badge. */
  liveState?: LiveGameStateRow | null;
}

export function PickCard({
  item, bankroll, kelly, onPress, tracked, onToggleTrack, inSlip, onToggleSlip, liveState,
}: Props) {
  const { pick, game } = item;
  const [contextOpen, setContextOpen] = React.useState(false);
  // Live picks are DraftKings only (Matt, 2026-09-03): the in-play model reads
  // DK's line and the bet is placed there, so the user's book never applies.
  const live = pick.is_live === true;
  const hasContext = pickHasContext(pick, game?.sport);
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
    gameStatus(game, liveState).kind === 'pre'
      ? movementFromLatest(pick, item.latestOdds)
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
  // The headline price is always the modeled DraftKings number — the price this
  // pick's edge, EV and stake were computed from. The boards do not follow a
  // book preference (Matt, 2026-09-04: that picker belongs to the Stats page).
  // Where to actually place the bet is the "Betting lines" row below, which
  // prices every book best first.
  const quote = displayQuoteForPick(pick, [], MODEL_BOOK);
  // Their book can hang the same bet off a different number (FD 9.0 vs DK 8.5).
  // Showing the price without the line would misrepresent the bet.
  const quoteLine =
    quote && quote.line != null && pick.scored_line != null && quote.line !== pick.scored_line
      ? quote.line
      : null;

  // Stake is a PAIR: what you lay, and what that wins. Computed off the price
  // the card actually shows (the user's book when it prices the side), because
  // a stake derived from a different number than the one printed beside it is
  // incoherent — a -105 quote risks 1.05u to win 1u, not 1.1u.
  const stake = stakeFor(pick.kelly_fraction, quote?.price ?? pick.dk_odds, kelly);
  // Unlocked look-ahead (future UFC/golf): the line shows, but nothing on the
  // card may read as a signal — the pick re-scores until it locks on game day.
  const preview = isUnlockedPreview(pick);
  // Line shopping lives in the "Betting lines" row below (BookLinesRow): every
  // bettable book, best first, each a hand-off. The old single "Best FD +145"
  // chip is gone — the row says it with buttons.
  // Sharp Score (BET only) + the contrarian/sharp-money tag (a smarter, derived
  // replacement for the raw public-split chip demoted in Phase 2).
  const sharp = preview ? null : sharpScore(pick);
  const contra = contrarianTag(pick);
  // Where the crowd is, for every pick that carries a split. contrarianTag only
  // speaks on a BET sitting in a decisive band, but nearly all captured splits
  // land on NONE/AVOID rows — and the Public sort orders the whole board by this
  // number, so a card it ranks has to print it. Neutral grey, no verdict: the
  // green/amber judged version above owns the cases it covers.
  const crowd = contra ? null : publicSplit(pick);
  // Two-tier card: show at most TWO "hero" chips, in value order
  // (movement steam/skip > contrarian sharp-money > line-shop savings > CLV).
  // Weather is demoted to the detail screen so the differentiating signals
  // aren't drowned out; the public split now shows on the card, because the
  // Public sort ranks by it. Injury always shows (safety).
  const heroOrder: string[] = [];
  if (movementSummary) heroOrder.push('movement');
  if (showClv) heroOrder.push('clv');
  const hero = new Set(heroOrder.slice(0, 2));
  // The public/sharp callout (green "Sharp side · X% public", amber when
  // public-heavy) always shows when present — it's the differentiating signal
  // Matt wants surfaced, so it's exempt from the 2-chip hero cap above.
  // A fallback price used to get its own "No MGM line — showing DK" note here.
  // Removed (Matt, 2026-09-03): the stat's own book label already says whose
  // price it is, and the board header explains the fallback once.
  // WHEN this bet posted. Timing is part of the pick, not metadata (§1c): a
  // live number is minutes old, an NFL opener is days old, and a morning game
  // pick is the number that was on offer at lock. Always shown on an unsettled
  // BET, as the card's last line — under the action buttons (Matt, 2026-09-03)
  // so the signals and the hand-off sit together and the stamp reads as a
  // footer rather than competing with them.
  const timing = pick.result == null ? pickTimingInfo(pick) : null;
  // Why this card carries no signal: it hasn't locked yet. Always shown on
  // previews (exempt from the hero cap, like injury/pick timing).
  const previewLabel = preview
    ? pick.sport === 'GOLF'
      ? 'Preview — locks when the tournament starts'
      : 'Preview — locks fight-day morning'
    : null;
  const hasExtras =
    Boolean(previewLabel) || hero.size > 0 || Boolean(contra) || Boolean(pick.injury_flag);
  // "Betting lines" — actionable BET picks list every bettable book's price for
  // this exact bet, best first, each chip a hand-off to that book. Renders
  // nothing for prob-only picks (no price to hand off), same as the old button.
  const showLines = pick.signal_type === 'BET' && !preview;
  // Track — any pick (props, started games, and live in-play picks) until it
  // settles. Line-change alerts still only fire for game-level pre-game picks
  // with a DK price (the notifier filters server-side); everything tracked
  // scores on the Performance tab. Live picks are tracked by a stable
  // proposition key (useTrackedBets) so the delete+rescore churn can't drop them.
  const canTrack = Boolean(onToggleTrack) && pick.result == null;
  // Betslip — only priced, unsettled, non-preview picks can be a parlay leg.
  const canSlip =
    Boolean(onToggleSlip) && pick.dk_odds != null && pick.result == null && !preview;

  return (
    <Pressable onPress={onPress} style={({ pressed }) => [styles.card, pressed && styles.pressed]}>
      <View style={styles.headerRow}>
        <Text style={styles.matchup} numberOfLines={1}>
          {matchup}
        </Text>
        <GameStatusPill game={game} live={liveState} />
      </View>

      <Text style={styles.label}>{pick.pick_label}</Text>

      <View style={styles.metaRow}>
        <View style={styles.modelChip}>
          <Text style={styles.modelChipText}>{modelShort(pick.model_id)}</Text>
        </View>
        {preview ? (
          <View style={styles.previewBadge}>
            <Text style={styles.previewBadgeText}>PREVIEW</Text>
          </View>
        ) : (
          <SignalBadge signal={pick.signal_type} small />
        )}
        {pick.confidence_tier ? (
          <View style={[styles.tierChip, tierBg(pick.confidence_tier)]}>
            <Text style={[styles.tierText, tierFg(pick.confidence_tier)]}>
              {pick.confidence_tier}
            </Text>
          </View>
        ) : null}
        {sharp ? <SharpScorePill score={sharp.score} band={sharp.band} /> : null}
      </View>

      <View style={styles.statsRow}>
        <Stat label="Model" value={formatPct(pick.model_probability)} />
        <Stat label="Edge" value={formatPctSigned(pick.edge)} color={edgeColor} />
        <Stat label="EV" value={ev == null ? '—' : formatPctSigned(ev)} color={evColor} />
        <Stat
          label={bookLabel(quote?.bookmaker ?? MODEL_BOOK)}
          value={
            quote == null
              ? '—'
              : quoteLine != null
                ? `${quoteLine} ${formatAmerican(quote.price)}`
                : formatAmerican(quote.price)
          }
        />
        <Stat
          label="Stake"
          // Widest cell in the row: stakes are published to two decimals, so
          // "1.15u → 1u" needs more than an even fifth or it wraps.
          wide
          value={
            pick.signal_type !== 'BET' || preview
              ? '—'
              : stake.priced
                ? `${formatUnits(stake.risk)} → ${formatUnits(stake.win)}`
                : formatUnits(stake.conviction)
          }
        />
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

      {showLines ? (
        <BookLinesRow
          pick={pick}
          bookRows={item.bookRows}
          onMore={onPress}
        />
      ) : null}

      {hasContext || canTrack || canSlip ? (
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

function Stat(
  { label, value, color, wide }:
  { label: string; value: string; color?: string; wide?: boolean },
) {
  return (
    <View style={[styles.stat, wide ? styles.statWide : null]}>
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
    // flex + truncation so a long matchup can never push the live score /
    // inning / LIVE badge off the right edge of the card.
    flexShrink: 1,
    marginRight: spacing.sm,
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
  statWide: {
    flex: 1.4,
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
    fontSize: 10,
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
    marginTop: spacing.sm,
  },
  actionsRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
  },
  // The post-time footer: last line of the card, under the action buttons.
  timingRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: spacing.sm,
  },
  // A single Text in a row container does not shrink by default, so the live
  // "Locked … — bet of record" label would overflow the card instead of
  // wrapping (UX review, 2026-09-03).
  timingText: {
    flexShrink: 1,
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
