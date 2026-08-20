import React from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import {
  expectedValue,
  formatAmerican,
  formatCurrency,
  formatGameTimeET,
  formatPct,
  formatPctSigned,
  gameDayLabelET,
} from '@/lib/format';
import { gameStatus } from '@/lib/format';
import {
  bookLabel,
  displayQuoteForPick,
  formatSideLine,
  gameMarketForModel,
  movementFromLatest,
  nflTimingInfo,
  MODEL_BOOK,
  type Movement,
} from '@/lib/markets';
import { usePreferredBook } from '@/hooks/usePreferredBook';
import { modelShort } from '@/lib/modelMeta';
import { recommendedBet, passesActionFilter, type KellySizingOpts } from '@/lib/thresholds';
import { contrarianTag, sharpScore } from '@/lib/sharpScore';
import { betOnBookLabel, bookButtonColors, openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { EnrichedPick, LiveGameStateRow, PickSide } from '@/types';
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
  /** Freshest live snapshot for this pick's game — drives the score + inning
   * beside the LIVE badge. Omitted (or null) falls back to a bare badge. */
  liveState?: LiveGameStateRow | null;
}

export function PickCard({
  item, bankroll, kelly, onPress, tracked, onToggleTrack, liveState,
}: Props) {
  const { pick, game } = item;
  const { book: preferredBook, isNonModelBook } = usePreferredBook();
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
  // The price the user actually sees: their own sportsbook's number when it has
  // one, otherwise the modeled DraftKings price (flagged as such). Model/Edge/EV
  // on this card always come from the DK line the model scored — only the price
  // and line shown here follow the user's book.
  const quote = displayQuoteForPick(pick, item.bookRows ?? [], preferredBook);
  // Their book can hang the same bet off a different number (FD 9.0 vs DK 8.5).
  // Showing the price without the line would misrepresent the bet.
  const quoteLine =
    quote && quote.line != null && pick.scored_line != null && quote.line !== pick.scored_line
      ? quote.line
      : null;
  // Line shopping: a non-DK book beats DK for this side. Only surface on BET
  // picks so the board isn't cluttered with line-shop chips on dead picks.
  // Redundant when it's already the book we're quoting — that price says it better.
  const bestRaw = pick.signal_type === 'BET' ? item.bestOdds ?? null : null;
  const bestOdds = bestRaw && bestRaw.bookmaker === quote?.bookmaker ? null : bestRaw;
  // Sharp Score (BET only) + the contrarian/sharp-money tag (a smarter, derived
  // replacement for the raw public-split chip demoted in Phase 2).
  const sharp = sharpScore(pick);
  const contra = contrarianTag(pick);
  // Two-tier card: show at most TWO "hero" chips, in value order
  // (movement steam/skip > contrarian sharp-money > line-shop savings > CLV).
  // Weather + raw public splits are demoted to the detail screen so the
  // differentiating signals aren't drowned out. Injury always shows (safety).
  const heroOrder: string[] = [];
  if (movementSummary) heroOrder.push('movement');
  if (bestOdds) heroOrder.push('bestOdds');
  if (showClv) heroOrder.push('clv');
  const hero = new Set(heroOrder.slice(0, 2));
  // The public/sharp callout (green "Sharp side · X% public", amber when
  // public-heavy) always shows when present — it's the differentiating signal
  // Matt wants surfaced, so it's exempt from the 2-chip hero cap above.
  // A fallback price is called out so a non-DK bettor never reads the modeled
  // DraftKings number as their own book's. BET picks only — the stat's own book
  // label already carries the truth, and prop coverage gaps are common enough
  // that noting them on dead picks would bury the board in grey text.
  const showFallbackNote =
    Boolean(quote?.isFallback) && isNonModelBook && pick.signal_type === 'BET';
  // NFL picks are published days ahead of kickoff — always show WHEN this pick
  // was locked/priced (exempt from the hero cap, like injury: a day-of user
  // must know they're looking at Tuesday's number). "Locked Tue 8/18", or the
  // time alone when it was priced today.
  const nflTiming = pick.result == null ? nflTimingInfo(pick) : null;
  const nflTimingLabel = nflTiming
    ? `${nflTiming.verb} ${gameDayLabelET(pick.created_at) ?? formatGameTimeET(pick.created_at)}`
    : null;
  const hasExtras =
    hero.size > 0 ||
    Boolean(contra) ||
    Boolean(pick.injury_flag) ||
    showFallbackNote ||
    Boolean(nflTimingLabel);
  // "Send this bet to my book" — actionable BET picks hand off to whichever book
  // the user selected, using that book's own betslip link.
  const betBook = quote?.isPreferred ? preferredBook : MODEL_BOOK;
  const betLink = quote?.link ?? pick.dk_bet_link;
  const betColors = bookButtonColors(betBook);
  const showBetButton = pick.signal_type === 'BET' && Boolean(betLink);
  // Track — any pick (props, started games, and live in-play picks) until it
  // settles. Line-change alerts still only fire for game-level pre-game picks
  // with a DK price (the notifier filters server-side); everything tracked
  // scores on the Performance tab. Live picks are tracked by a stable
  // proposition key (useTrackedBets) so the delete+rescore churn can't drop them.
  const canTrack = Boolean(onToggleTrack) && pick.result == null;

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
        <SignalBadge signal={pick.signal_type} small />
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
          {showFallbackNote ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="wallet-outline"
                size={13}
                color={colors.textTertiary}
                style={styles.extraIcon}
              />
              <Text style={[styles.extraText, { color: colors.textTertiary }]}>
                No {bookLabel(preferredBook)} line — showing DK
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
          {nflTimingLabel ? (
            <View style={styles.extraItem}>
              <Ionicons
                name="time-outline"
                size={13}
                color={colors.textTertiary}
                style={styles.extraIcon}
              />
              <Text style={styles.extraText}>{nflTimingLabel}</Text>
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

      {showBetButton ? (
        <Pressable
          onPress={() => {
            void openBookBetslip(betBook, betLink);
          }}
          style={({ pressed }) => [
            styles.dkButton,
            { backgroundColor: betColors.bg },
            pressed && styles.dkButtonPressed,
          ]}
          hitSlop={6}
        >
          <Ionicons name="open-outline" size={15} color={betColors.fg} />
          <Text style={[styles.dkButtonText, { color: betColors.fg }]}>
            {betOnBookLabel(betBook)}
          </Text>
        </Pressable>
      ) : null}

      {hasContext || canTrack ? (
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
            {canTrack ? (
              <TrackButton tracked={Boolean(tracked)} onPress={onToggleTrack!} compact />
            ) : null}
          </View>
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
  // Background/text color come from the book being handed off to
  // (bookButtonColors), so they're applied inline rather than fixed here.
  dkButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
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
