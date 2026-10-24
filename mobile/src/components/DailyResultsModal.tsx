import React, { useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from 'react-native';
import { SafeAreaProvider, SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';
import { friendlyCause } from '@/lib/errors';
import { unitsSpeech } from '@/lib/a11y';
import { addDays, formatAmerican } from '@/lib/format';
import { modelRecordBelow, STACKED_BLOCK } from '@/lib/modelBadgeLayout';
import { modelHistoryMark, modelLong, modelShort } from '@/lib/modelMeta';
import { postedPickUnits } from '@/lib/thresholds';
import { CalendarGrid } from '@/components/CalendarGrid';
import { ModelBadgeRow } from '@/components/ModelBadgeRow';
import {
  ALL_SPORTS,
  dayRoiText,
  dayUnitsText,
  dayWinRateText,
  EMPTY_DAILY,
  scopeDailyResults,
  type DailyResults,
  type DayGameSummary,
  type DayStakeStats,
  type ModelDayStats,
  type SportDayBreakdown,
} from '@/lib/dailyResults';
import type { Pick } from '@/types';
import { bookLabelShort, storedQuoteBook } from '@/lib/markets';
import { decisionOdds } from '@/lib/decisionPrice';

/**
 * Daily results: how every model did on a given day — a consolidated "All"
 * record + ROI, a per-sport / per-model breakdown (tappable sport chips filter
 * the whole view), the individual picks (graded AND still-open), and every
 * game the models scored that day. The user can step days with the chevrons or
 * jump anywhere via the calendar (bounded [minDate, maxDate]). Presentational;
 * the host owns the data (useDailyResults), the selected date, and visibility
 * (useDailyRecapControl).
 */
export function DailyResultsModal({
  visible,
  onClose,
  date,
  minDate,
  maxDate,
  onSelectDate,
  results,
  loading,
  error,
}: {
  visible: boolean;
  onClose: () => void;
  date: string;
  minDate: string;
  maxDate: string;
  onSelectDate: (date: string) => void;
  results: DailyResults;
  loading: boolean;
  error: string | null;
}) {
  const [calendarOpen, setCalendarOpen] = useState(false);
  const [sportFilter, setSportFilter] = useState<string>('ALL');
  // Sport cards open collapsed — the header carries the sport's record; a tap
  // shows its models.
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(new Set());

  // Snap the sport filter back to All every time the modal opens — a sticky
  // per-sport filter from a previous open would read as missing data.
  const wasVisible = useRef(false);
  useEffect(() => {
    if (visible && !wasVisible.current) {
      setSportFilter('ALL');
      setExpanded(new Set());
    }
    wasVisible.current = visible;
  }, [visible]);
  // A new day starts collapsed too.
  useEffect(() => setExpanded(new Set()), [date]);
  const toggleSport = (sport: string) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(sport)) next.delete(sport);
      else next.add(sport);
      return next;
    });

  const scoped = useMemo(() => scopeDailyResults(results, sportFilter), [results, sportFilter]);

  // Every sport gets a section, in canonical order — sports with no settled
  // picks this day render an explicit empty state instead of disappearing.
  // Any sport the lib returns that isn't in ALL_SPORTS (future addition) is
  // appended so it can never be silently dropped.
  const sportSections: SportDayBreakdown[] = [
    ...ALL_SPORTS.map(
      (sport) =>
        results.sports.find((s) => s.sport === sport) ?? {
          sport,
          total: EMPTY_DAILY,
          models: [],
          live: 0,
          pending: 0,
          unpublished: 0,
        },
    ),
    ...results.sports.filter((s) => !ALL_SPORTS.includes(s.sport)),
  ];
  const visibleSections =
    sportFilter === 'ALL' ? sportSections : sportSections.filter((s) => s.sport === sportFilter);
  // Sports that had picks come first (canonical order kept); the quiet ones are
  // still listed — never dropped — but as one line underneath, so they don't
  // split up the sports that did play.
  const activeSections = visibleSections.filter(sportHasActivity);
  const quietSections = visibleSections.filter((s) => !sportHasActivity(s));
  // One sport filtered, or only one sport played: its card opens — collapsing
  // the only card would add a tap and hide nothing.
  const single = sportFilter !== 'ALL' || activeSections.length === 1;
  const noPickSports = quietSections.filter((s) => s.unpublished === 0).map((s) => s.sport);
  const notPostedSports = quietSections.filter((s) => s.unpublished > 0).map((s) => s.sport);

  // The displayed results can lag the selected date by one render while a new
  // day loads — treat that as loading so we never show day A under day B's header.
  const stale = results.date !== date;
  const showLoading = loading || stale;
  // Pending picks and scored games are content too — a day where nothing has
  // settled yet (e.g. WNBA finals not ingested) must show its picks as open,
  // not render as an off day.
  const hasContent =
    !stale &&
    (results.overall.picks > 0 ||
      results.pending > 0 ||
      results.gradedPicks.length > 0 ||
      results.games.length > 0 ||
      results.unpublished > 0);
  const isYesterday = date === maxDate;
  const canPrev = date > minDate;
  const canNext = date < maxDate;

  return (
    // A native Modal renders in its own view hierarchy, so the app's root
    // SafeAreaProvider doesn't reach it — without this local provider the
    // SafeAreaView gets a 0 top inset and the close button ends up under the
    // status bar (untappable). onRequestClose handles the Android back button.
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      onRequestClose={onClose}
    >
      <SafeAreaProvider>
      <SafeAreaView style={styles.container} edges={['top', 'bottom']}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.title}>{isYesterday ? 'Yesterday’s results' : 'Daily results'}</Text>
            <Text style={styles.subtitle}>{prettyDate(date)}</Text>
          </View>
          <Pressable
            onPress={onClose}
            hitSlop={12}
            style={styles.closeBtn}
            accessibilityRole="button"
            accessibilityLabel="Close daily results"
          >
            <Ionicons name="close" size={22} color={colors.textSecondary} />
          </Pressable>
        </View>

        {/* Day navigation — always visible so an empty/error day isn't a dead end. */}
        <View style={styles.dateNav}>
          <Pressable
            accessibilityRole="button"
            onPress={() => canPrev && onSelectDate(addDays(date, -1))}
            disabled={!canPrev}
            hitSlop={10}
            accessibilityLabel="Previous day"
            style={({ pressed }) => [styles.navBtn, pressed && { opacity: 0.6 }]}
          >
            <Ionicons
              name="chevron-back"
              size={20}
              color={canPrev ? colors.tint : colors.textTertiary}
            />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ expanded: calendarOpen }}
            onPress={() => setCalendarOpen((open) => !open)}
            hitSlop={8}
            accessibilityLabel="Pick a date"
            style={({ pressed }) => [styles.dateChip, pressed && { opacity: 0.6 }]}
          >
            <Ionicons name="calendar-outline" size={15} color={colors.tint} />
            <Text style={styles.dateChipText}>{shortDate(date)}</Text>
            <Ionicons
              name={calendarOpen ? 'chevron-up' : 'chevron-down'}
              size={13}
              color={colors.tint}
            />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => canNext && onSelectDate(addDays(date, 1))}
            disabled={!canNext}
            hitSlop={10}
            accessibilityLabel="Next day"
            style={({ pressed }) => [styles.navBtn, pressed && { opacity: 0.6 }]}
          >
            <Ionicons
              name="chevron-forward"
              size={20}
              color={canNext ? colors.tint : colors.textTertiary}
            />
          </Pressable>
        </View>

        {calendarOpen ? (
          <View style={styles.calendarWrap}>
            <CalendarGrid
              // Remount when the day changes so the grid opens on the right month.
              key={date}
              selected={date}
              minDate={minDate}
              maxDate={maxDate}
              onSelect={(d) => {
                setCalendarOpen(false);
                onSelectDate(d);
              }}
            />
          </View>
        ) : null}

        {showLoading ? (
          <View style={styles.center}>
            <ActivityIndicator />
          </View>
        ) : error ? (
          <View style={styles.center}>
            <Text style={styles.error}>Couldn’t load this day’s results.</Text>
            <Text style={styles.errorDetail}>{friendlyCause(error)}</Text>
          </View>
        ) : !hasContent ? (
          <View style={styles.center}>
            <Ionicons name="moon-outline" size={40} color={colors.textTertiary} />
            <Text style={styles.emptyTitle}>No picks this day</Text>
            <Text style={styles.emptyBody}>
              An off day — nothing was scored or nothing cleared the bar. That’s a valid signal,
              not a miss.
            </Text>
          </View>
        ) : (
          <ScrollView contentContainerStyle={styles.list}>
            {/* Sport filter — All + one chip per sport */}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              style={styles.sportChipsFrame}
              contentContainerStyle={styles.sportChips}
            >
              {['ALL', ...ALL_SPORTS].map((s) => {
                const active = sportFilter === s;
                return (
                  <Pressable
                    // ~30pt chip; the row's frame (sportChipsFrame) keeps this slop
                    // inside the horizontal ScrollView.
                    hitSlop={{ top: 7, bottom: 7, left: 2, right: 2 }}
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    key={s}
                    onPress={() => setSportFilter(s)}
                    style={[styles.sportChip, active && styles.sportChipActive]}
                    accessibilityLabel={s === 'ALL' ? 'All sports' : s}
                  >
                    <Text style={[styles.sportChipText, active && styles.sportChipTextActive]}>
                      {s === 'ALL' ? 'All' : s}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>

            {/* Hero — the scoped record (All or the selected sport) */}
            {scoped.record.picks > 0 ? (
              <View style={styles.hero}>
                <Text style={styles.heroLabel}>
                  {sportFilter === 'ALL' ? 'All models' : sportFilter} — return on bets
                </Text>
                <Text
                  style={[styles.heroRoi, { color: scoped.record.risked > 0 ? roiColor(scoped.record.roi) : colors.textSecondary }]}
                  accessibilityLabel={scoped.record.risked > 0 ? undefined : 'Return on bets unavailable'}
                >
                  {dayRoiText(scoped.record.risked, scoped.record.roi)}
                </Text>
                <Text style={styles.heroRecord}>{recordLine(scoped.record)}</Text>
                {/* How the day splits. Both halves count identically — a live
                    pick locks at first signal and settles the same way — but a
                    day carried by in-play bets reads very differently from one
                    carried by the morning board, and the number is meaningless
                    without saying which. */}
                {scoped.live > 0 ? (
                  <Text style={styles.splitNote}>
                    {scoped.record.picks - scoped.live} pre-game · {scoped.live} in-play
                  </Text>
                ) : null}
                <View style={styles.heroStats}>
                  <HeroStat label="Picks" value={String(scoped.record.picks)} />
                  <HeroStat
                    label="Units"
                    value={dayUnitsText(scoped.record.units)}
                    color={unitsColor(scoped.record.units)}
                  />
                  <HeroStat
                    label="Win rate"
                    value={dayWinRateText(scoped.record.wins, scoped.record.losses, scoped.record.winRate)}
                    color={scoped.record.wins + scoped.record.losses > 0 ? undefined : colors.textSecondary}
                  />
                </View>
                {scoped.pending > 0 ? (
                  <Text style={styles.pendingNote}>
                    +{scoped.pending} more {scoped.pending === 1 ? 'pick' : 'picks'} still awaiting a
                    result
                  </Text>
                ) : null}
              </View>
            ) : (
              <View style={[styles.hero, styles.heroEmpty]}>
                <Ionicons
                  name={scoped.pending > 0 ? 'hourglass-outline' : 'moon-outline'}
                  size={28}
                  color={colors.textTertiary}
                />
                <Text style={styles.heroEmptyTitle}>
                  {scoped.pending > 0
                    ? 'Nothing graded yet'
                    : scoped.unpublished > 0
                      ? 'Nothing posted'
                      : 'No qualifying picks'}
                </Text>
                <Text style={styles.heroEmptyBody}>
                  {scoped.pending > 0
                    ? `${scoped.pending} ${scoped.pending === 1 ? 'pick is' : 'picks are'} still awaiting a result — check back once the games settle.`
                    : scoped.unpublished > 0
                      ? sportFilter === 'ALL'
                        ? 'No picks were posted this day.'
                        : `No ${sportFilter} picks were posted this day.`
                      : sportFilter === 'ALL'
                        ? 'No picks cleared the bar this day.'
                        : `No ${sportFilter} picks cleared the bar this day.`}
                </Text>
              </View>
            )}

            {/* Per-sport breakdown — sports with picks first, each collapsible.
                A single-sport filter shows its one card already open. */}
            {activeSections.map((s) => (
              <SportCard
                key={s.sport}
                section={s}
                open={single || expanded.has(s.sport)}
                collapsible={!single}
                onToggle={() => toggleSport(s.sport)}
              />
            ))}

            {/* Every sport is still accounted for: the quiet ones share one line. */}
            {quietSections.length > 0 ? (
              <View style={[styles.sportCard, styles.sportCardEmpty]}>
                {noPickSports.length > 0 ? (
                  <Text style={styles.quietLine}>
                    <Text style={styles.quietLabel}>No picks  </Text>
                    {noPickSports.join(' · ')}
                  </Text>
                ) : null}
                {notPostedSports.length > 0 ? (
                  <Text style={styles.quietLine}>
                    <Text style={styles.quietLabel}>Not posted  </Text>
                    {notPostedSports.join(' · ')}
                  </Text>
                ) : null}
              </View>
            ) : null}

            {/* Every pick behind the record — graded first, then still-open */}
            {scoped.gradedPicks.length > 0 || scoped.pendingPicks.length > 0 ? (
              <View style={styles.sportCard}>
                <Text style={styles.picksTitle}>The picks</Text>
                {scoped.gradedPicks.map((p) => (
                  <PickRow key={p.pick_id} pick={p} />
                ))}
                {scoped.pendingPicks.map((p) => (
                  <PendingPickRow key={p.pick_id} pick={p} />
                ))}
              </View>
            ) : null}

            {/* Every game the models scored that day */}
            {scoped.games.length > 0 ? (
              <View style={styles.sportCard}>
                <Text style={styles.picksTitle}>Games scored</Text>
                <Text style={styles.gamesSub}>
                  Every game the models looked at this day, whether or not a pick fired.
                </Text>
                {scoped.games.map((g) => (
                  <GameScoreRow key={g.gameId} game={g} showSport={sportFilter === 'ALL'} />
                ))}
              </View>
            ) : null}

            <Text style={styles.footer}>
              Settled picks that Discord posted. Each pick risks the amount
              needed to win 1 unit. At −110 that’s 1.1 units to win 1. Risk is
              capped at 3 units, and a pick with no price counts as 1 unit. The
              percentage is units won or lost divided by units risked. The Models
              tab uses a flat $100 bet, so its percentages won’t match. Open
              picks settle after their games go final.
            </Text>
          </ScrollView>
        )}
      </SafeAreaView>
      </SafeAreaProvider>
    </Modal>
  );
}

function sportHasActivity(s: SportDayBreakdown): boolean {
  return s.total.picks > 0 || s.pending > 0 || s.models.length > 0;
}

/** One sport's day: the header is its record; opening it lists the models. */
function SportCard({
  section: s,
  open,
  collapsible,
  onToggle,
}: {
  section: SportDayBreakdown;
  open: boolean;
  collapsible: boolean;
  onToggle: () => void;
}) {
  const roiText = s.total.picks > 0 ? dayRoiText(s.total.risked, s.total.roi) : null;
  const sub =
    s.total.picks > 0
      ? `${recordLine(s.total)} · ${stakeLine(s.total)}${s.pending > 0 ? ` · ${s.pending} pending` : ''}`
      : s.pending > 0
        ? 'Signals fired — results not graded yet'
        : `${recordLine(s.total)} · ${dayUnitsText(s.total.units)}`;
  const header = (
    <>
      <View style={styles.sportHeader}>
        <Text style={styles.sportName}>{s.sport}</Text>
        <View style={styles.sportHeaderRight}>
          {roiText != null ? (
            <Text
              style={[styles.sportRoi, { color: s.total.risked > 0 ? roiColor(s.total.roi) : colors.textSecondary }]}
              accessibilityLabel={s.total.risked > 0 ? undefined : 'Return on bets unavailable'}
            >
              {roiText}
            </Text>
          ) : s.pending > 0 ? (
            <Text style={styles.sportEmptyNote}>
              {s.pending} {s.pending === 1 ? 'pick' : 'picks'} pending
            </Text>
          ) : (
            <Text style={styles.sportEmptyNote}>{dayUnitsText(s.total.units)}</Text>
          )}
          {collapsible && s.models.length > 0 ? (
            <Ionicons
              name={open ? 'chevron-up' : 'chevron-down'}
              size={16}
              color={colors.textTertiary}
            />
          ) : null}
        </View>
      </View>
      <Text style={[styles.sportSub, !open && styles.sportSubCollapsed]}>{sub}</Text>
    </>
  );
  return (
    <View style={styles.sportCard}>
      {collapsible && s.models.length > 0 ? (
        <Pressable
          onPress={onToggle}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`${s.sport}, ${sub}${
            s.total.picks === 0
              ? s.pending > 0
                ? `, ${s.pending} pending`
                : ''
              : s.total.risked > 0
                ? `, ${roiText} return`
                : ', return unavailable'
          }`}
          accessibilityHint={open ? 'Hides the models' : 'Shows the models'}
          style={({ pressed }) => [styles.sportToggle, pressed && { opacity: 0.6 }]}
        >
          {header}
        </Pressable>
      ) : (
        header
      )}
      {open ? s.models.map((m) => <ModelRow key={m.modelId} model={m} />) : null}
    </View>
  );
}

function HeroStat({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <View style={styles.heroStat}>
      <Text style={[styles.heroStatValue, color ? { color } : null]}>{value}</Text>
      <Text style={styles.heroStatLabel}>{label}</Text>
    </View>
  );
}

function ModelRow({ model }: { model: ModelDayStats }) {
  const priced = model.risked > 0;
  const mark = modelHistoryMark(model.modelId);
  const { width: windowWidth, fontScale } = useWindowDimensions();
  const recordBelow = modelRecordBelow(fontScale, windowWidth);
  return (
    <View style={[styles.modelRow, recordBelow && styles.modelRowStacked]}>
      <View style={recordBelow ? styles.modelLeftStacked : styles.modelLeft}>
        <ModelBadgeRow badge={modelShort(model.modelId)} variant="tile">
          {/* Wraps on spaces. At 1.3× text, or on a narrow phone, the badge
              sits above the name so a word is not split. */}
          <Text style={styles.modelName}>
            {modelLong(model.modelId)}
          </Text>
          <Text style={styles.modelSub}>
            {recordLine(model)}
            {` · ${stakeLine(model)}`}
            {mark ? ` · ${mark}` : ''}
          </Text>
        </ModelBadgeRow>
      </View>
      <Text
        style={[
          styles.modelRoi,
          recordBelow && styles.modelRoiStacked,
          { color: priced ? roiColor(model.roi) : colors.textSecondary },
        ]}
        accessibilityLabel={priced ? undefined : 'Return on bets unavailable'}
      >
        {dayRoiText(model.risked, model.roi)}
      </Text>
    </View>
  );
}

const RESULT_STYLE: Record<string, { label: string; color: string; bg: string }> = {
  // The letter carries the result; the ink makes it readable on its wash
  // (4.61 / 5.01 / 9.55:1 — the bright hues were 2.0–3.1:1; audit H2).
  WIN: { label: 'W', color: colors.betInk, bg: colors.betSoft },
  LOSS: { label: 'L', color: colors.avoidInk, bg: colors.avoidSoft },
  PUSH: { label: 'P', color: colors.textSecondary, bg: colors.noneSoft },
};

function PickRow({ pick }: { pick: Pick }) {
  const res = RESULT_STYLE[pick.result ?? ''] ?? RESULT_STYLE.PUSH!;
  // The row shows the same money the day's total added: postedPickUnits.
  const profit = postedPickUnits(pick).units;
  const price = decisionOdds(pick);
  const missingPrice = price == null;
  const unitsLabel = unitsSpeech(dayUnitsText(profit));
  return (
    <View style={styles.modelRow}>
      <View style={[styles.resultBadge, { backgroundColor: res.bg }]}>
        <Text style={[styles.resultBadgeText, { color: res.color }]}>{res.label}</Text>
      </View>
      <View style={styles.modelNameWrap}>
        <Text style={styles.modelName} numberOfLines={2}>
          {pick.pick_label}
        </Text>
        <Text style={styles.modelSub}>
          {modelShort(pick.model_id)}
          {missingPrice
            ? ' · no price'
            : ` · ${bookLabelShort(storedQuoteBook(pick))} ${formatAmerican(price)}`}
        </Text>
      </View>
      <Text
        style={[styles.modelRoi, { color: unitsColor(profit) }]}
        accessibilityLabel={missingPrice ? `no price, ${unitsLabel}` : unitsLabel}
      >
        {dayUnitsText(profit)}
      </Text>
    </View>
  );
}

/** A BET pick that cleared the cut but hasn't graded yet (result NULL). */
function PendingPickRow({ pick }: { pick: Pick }) {
  return (
    <View style={styles.modelRow}>
      <View style={[styles.resultBadge, { backgroundColor: colors.noneSoft }]}>
        <Ionicons name="hourglass-outline" size={13} color={colors.textSecondary} />
      </View>
      <View style={styles.modelNameWrap}>
        <Text style={styles.modelName} numberOfLines={2}>
          {pick.pick_label}
        </Text>
        <Text style={styles.modelSub}>
          {modelShort(pick.model_id)}
          {decisionOdds(pick) != null ? ` · ${bookLabelShort(storedQuoteBook(pick))} ${formatAmerican(decisionOdds(pick))}` : ''}
        </Text>
      </View>
      <Text style={styles.openLabel}>Open</Text>
    </View>
  );
}

function GameScoreRow({ game, showSport }: { game: DayGameSummary; showSport: boolean }) {
  const meta = [
    showSport ? game.sport : null,
    `${game.pickCount} ${game.pickCount === 1 ? 'pick' : 'picks'} scored`,
    game.final ? 'Final' : 'No final score yet',
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <View style={styles.modelRow}>
      <View style={styles.modelNameWrap}>
        <Text style={styles.modelName} numberOfLines={1}>
          {game.matchup}
        </Text>
        <Text style={styles.modelSub}>{meta}</Text>
      </View>
      <Text style={[styles.gameScore, !game.final && { color: colors.textTertiary }]}>
        {game.final ? `${game.awayScore}–${game.homeScore}` : '—'}
      </Text>
    </View>
  );
}

function recordLine(s: DayStakeStats): string {
  const base = `${s.wins}–${s.losses}`;
  return s.pushes > 0 ? `${base}–${s.pushes}` : base;
}

/** Units beside a record line. A push-only total is 0.00u, not a dash. */
function stakeLine(s: DayStakeStats): string {
  return dayUnitsText(s.units);
}

// Text ink with the sign (pnlColor), not the positive/negative heat-map fills,
// which are 2.22 / 3.55:1 as text (audit H2).
// The tone of the ROUNDED percent formatPctSigned prints (1 dp of roi × 100),
// so "+0.1%" is green and "0.0%" is grey — never an epsilon of its own.
function roiColor(roi: number): string {
  return pnlColor(roi, 1, 100);
}

/** Colour a units figure by what dayUnitsText prints (2 dp), so a day that
 *  rounds to "0.00u" never reads as a win or a loss. */
function unitsColor(units: number): string {
  return pnlColor(units, 2);
}

function prettyDate(date: string): string {
  try {
    const d = new Date(`${date}T12:00:00Z`);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'long',
      month: 'long',
      day: 'numeric',
    }).format(d);
  } catch {
    return date;
  }
}

function shortDate(date: string): string {
  try {
    const d = new Date(`${date}T12:00:00Z`);
    return new Intl.DateTimeFormat('en-US', {
      timeZone: 'UTC',
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    }).format(d);
  } catch {
    return date;
  }
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1 },
  title: {
    fontSize: font.size.title1,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  closeBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.noneSoft,
  },
  dateNav: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.sm,
  },
  navBtn: { padding: 4 },
  dateChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radii.pill,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.tint,
  },
  dateChipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  calendarWrap: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    gap: spacing.sm,
  },
  error: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  errorDetail: { fontSize: font.size.footnote, color: colors.textSecondary, textAlign: 'center' },
  emptyTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: spacing.sm,
  },
  emptyBody: {
    fontSize: font.size.callout,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 22,
  },
  list: { padding: spacing.lg, paddingTop: spacing.xs, gap: spacing.md },

  // The chips' 7pt vertical slop has to land inside the ScrollView (which
  // clips touches to its bounds): pad by 7 and pull back by 7 — no visual move.
  sportChipsFrame: {
    marginVertical: -7,
  },
  sportChips: {
    flexDirection: 'row',
    gap: spacing.sm,
    paddingVertical: 2 + 7,
  },
  sportChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs + 2,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separator,
  },
  sportChipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  sportChipText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  sportChipTextActive: { color: colors.bg },

  hero: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: 'center',
  },
  heroLabel: { fontSize: font.size.footnote, color: colors.textSecondary },
  heroRoi: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    marginTop: 2,
  },
  heroRecord: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginTop: 2,
  },
  heroStats: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    alignSelf: 'stretch',
    marginTop: spacing.md,
  },
  heroEmpty: { gap: spacing.xs },
  heroEmptyTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  heroEmptyBody: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    lineHeight: 19,
  },
  splitNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
    textAlign: 'center',
  },
  pendingNote: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
    textAlign: 'center',
  },
  heroStat: { alignItems: 'center' },
  heroStatValue: { fontSize: font.size.callout, fontWeight: font.weight.semibold, color: colors.textPrimary },
  heroStatLabel: { fontSize: font.size.caption, color: colors.textSecondary, marginTop: 2 },

  sportCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  sportHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  sportName: { fontSize: font.size.headline, fontWeight: font.weight.bold, color: colors.textPrimary },
  sportRoi: { fontSize: font.size.headline, fontWeight: font.weight.bold },
  // No opacity: 0.75 over textTertiary was 3.15:1. The muted look comes from
  // the tertiary ink itself (5.23:1 on bgCard).
  sportCardEmpty: { paddingVertical: spacing.sm },
  sportEmptyNote: { fontSize: font.size.footnote, color: colors.textTertiary },
  sportSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.sm },
  sportSubCollapsed: { marginBottom: 0 },
  // The whole header is the tap target: name + record line, never under 44pt.
  sportToggle: { minHeight: 44, justifyContent: 'center' },
  sportHeaderRight: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  quietLine: { fontSize: font.size.footnote, color: colors.textTertiary, lineHeight: 20 },
  quietLabel: { fontWeight: font.weight.semibold },
  picksTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  gamesSub: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: -spacing.sm + 2,
    marginBottom: spacing.sm,
  },

  modelRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  modelRowStacked: {
    flexDirection: 'column',
    alignItems: 'stretch',
  },
  modelLeft: { flex: 1 },
  modelLeftStacked: { ...STACKED_BLOCK, alignSelf: 'stretch' },
  resultBadge: {
    width: 26,
    height: 26,
    borderRadius: 13,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: spacing.sm,
  },
  resultBadgeText: { fontSize: font.size.footnote, fontWeight: font.weight.bold },
  modelNameWrap: { flex: 1 },
  modelName: { fontSize: font.size.body, fontWeight: font.weight.medium, color: colors.textPrimary },
  modelSub: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 1 },
  modelRoi: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.sm },
  modelRoiStacked: { alignSelf: 'flex-end', marginTop: spacing.xs },
  openLabel: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
    marginLeft: spacing.sm,
  },
  gameScore: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginLeft: spacing.sm,
  },

  footer: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
    lineHeight: 18,
  },
});
