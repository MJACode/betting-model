import React, { useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import type { RouteProp } from '@react-navigation/native';
import { useNavigation, useRoute } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { AddLineSheet } from '@/components/AddLineSheet';
import { GroupTabs } from '@/components/GroupTabs';
import { HitModeSheet } from '@/components/HitModeSheet';
import { HitRateChart } from '@/components/HitRateChart';
import { PlayerBetBar } from '@/components/PlayerBetBar';
import { PlayerNewsButton } from '@/components/PlayerNewsButton';
import { TrendStrip } from '@/components/TrendStrip';
import { useNow } from '@/hooks/useNow';
import { usePlayerNews } from '@/hooks/usePlayerNews';
import { usePlayerPropQuote } from '@/hooks/usePlayerPropQuote';
import { logValues, trendBuckets, usePlayerTrends } from '@/hooks/usePlayerTrends';
import { usePreferredBooks } from '@/hooks/usePreferredBooks';
import { useParlaySlip } from '@/hooks/useParlaySlip';
import { useTodayPicks } from '@/hooks/useTodayPicks';
import {
  chipKey,
  chipsForLoadedPlayer,
  chipsForPlayer,
  defaultChipForPlayer,
  filledChipCounts,
  gameContextLine,
  groupsOfChips,
  lineStepFor,
  logStatValue,
  openingChip,
  playerSubtitle,
  roundLineToStep,
  windowOptionsFor,
  type GameWindow,
  type PlayerLogEntry,
  type PlayerLogSport,
} from '@/lib/playerLog';
import { propMarketForStat, propModelForStat } from '@/lib/statCatalog';
import type { StatDef } from '@/lib/statCatalog';
import { anyBookPostsSide, buildPickIndex, slipPickFor } from '@/lib/statsOdds';
import {
  hitModeHeadline,
  hitModeLabel,
  modeLineLabel,
  rulerValueLabel,
  selectionFor,
  type HitMode,
} from '@/lib/hitMode';
import { propLineSheetInput, type LineSheetInput } from '@/lib/lineLegs';
import { computeHitRate, isHit, type HitDirection } from '@/lib/hitRate';
import { slipKeyForPick } from '@/lib/parlay';
import { formatAmerican } from '@/lib/format';
import { todayET } from '@/lib/format';
import { colors, font, gradeColor, radii, spacing } from '@/lib/theme';
import { gradeSpoken, type MatchupGrade } from '@/lib/matchup';
import type { RootStackParamList } from '@/types';
import { bookName, sideNotPostedNote, storedQuoteBook } from '@/lib/markets';
import { decisionOdds } from '@/lib/decisionPrice';

type Route = RouteProp<RootStackParamList, 'PlayerStats'>;

export function PlayerStatsScreen() {
  const route = useRoute<Route>();
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { playerId, playerName, playerType } = route.params;
  const fromParlay = route.params.fromParlay === true;
  // Handed over by the Stats board; absent when the player was opened from
  // anywhere else. Typed loosely on the route (a string) and narrowed here.
  const matchupText = route.params.matchupText ?? null;
  const matchupGrade = (route.params.matchupGrade as MatchupGrade | undefined) ?? null;
  // Older navigation state (a screen restored from a build before player detail
  // went multi-sport) carries no sport — MLB was the only one that could open it.
  const sport: PlayerLogSport = route.params.sport ?? 'MLB';

  const allChips = useMemo(() => chipsForPlayer(sport, playerType), [sport, playerType]);
  // What the user last tapped. The stat actually charted is derived from it
  // below, because the load can retire the group it belongs to.
  const [picked, setPicked] = useState<StatDef | null>(() => defaultChipForPlayer(sport, playerType));
  const windows = useMemo(() => windowOptionsFor(sport), [sport]);
  const [gameWindow, setGameWindow] = useState<GameWindow>(10);
  // The "at least" threshold. null = auto-default to the rounded median once data loads.
  const [line, setLine] = useState<number | null>(null);
  // At Least / Over / Under — the SAME control the Stats board has had since
  // 2026-09-05 (lib/hitMode.ts), which this screen never adopted. It is what
  // makes the card able to ask for the other side of a bet at all: until now
  // every number on it was an over, silently.
  const [mode, setMode] = useState<HitMode>('atLeast');
  const [modeOpen, setModeOpen] = useState(false);

  useEffect(() => {
    navigation.setOptions({ title: playerName });
  }, [navigation, playerName]);

  // Sport/player changed (the screen is reused across pushes) — reset to that
  // sport's default stat and window rather than charting a stat it has no data for.
  useEffect(() => {
    setPicked(defaultChipForPlayer(sport, playerType));
    setGameWindow(windows.some((w) => w.value === 10) ? 10 : windows[0]!.value);
  }, [sport, playerType, playerId, windows]);

  const beforeDate = todayET();
  const { games, loading, loaded, error } = usePlayerTrends({
    playerId: playerId || null,
    playerName: playerId ? null : playerName,
    beforeDate,
    sport,
    // Only tells the hook a stat is selected at all: the fetch reads the
    // sport's whole column list, and the chart below is drawn from the stat
    // resolved after the rows land.
    stat: picked,
    playerType,
  });
  // `loaded` is the hook's: until the first fetch RESOLVES this screen knows
  // nothing about the player, so it offers no stat controls. A tab row drawn
  // from the catalog would show the Defense tab on a quarterback for the
  // length of the fetch and then withdraw it (UX review, 2026-09-20).

  // The tabs this player actually fills, read off the LOADED log: a quarterback
  // offered a Defense tab is a control that leads nowhere — ten charted zeroes
  // and a 0% badge in alarm red (Matt, 2026-09-19).
  const chips = useMemo(() => chipsForLoadedPlayer(allChips, games), [allChips, games]);
  const groups = useMemo(() => groupsOfChips(chips), [chips]);
  // Which of those chips the player has a number in — what a tab opens on.
  const filled = useMemo(() => filledChipCounts(chips, games), [chips, games]);

  // DERIVED, not corrected after the fact: the load can retire the group the
  // screen opened on (every football screen opens on Pass Yards, which no
  // linebacker will ever fill), and an effect that fixed it afterwards painted
  // one frame with an empty chip row and nothing selected (UX review,
  // 2026-09-20). Resolving it here means that frame cannot exist.
  const stat = useMemo(() => {
    if (picked && chips.some((c) => c.key === picked.key && c.group === picked.group)) return picked;
    return openingChip(chips, filled);
  }, [picked, chips, filled]);

  // Charted off the rows already in hand, for the stat resolved above — never
  // a second fetch, so the numbers and the label they sit under always belong
  // to the same stat.
  const values = useMemo(() => logValues(games, stat), [games, stat]);
  const trends = useMemo(() => trendBuckets(values), [values]);

  // Recent news for this player. Independent of the trend load: news failing
  // must never cost the chart, and vice versa.
  const news = usePlayerNews({ sport, playerId: playerId || null, playerName });

  // ── The betslip leg ────────────────────────────────────────────────────────
  // The Stats board's line pills open the sportsbook (Matt, 2026-09-04), so
  // this is where a leg joins OUR slip. It is deliberately the model's pick and
  // not the chart's threshold: a parlay leg is a bet of record (§1c), and the
  // pick states its own line, so the card can never offer a bet at a number
  // nobody priced. No edge, no EV — the Stats surface stays out of the models.
  const { data: todayPicks } = useTodayPicks();
  const slip = useParlaySlip();
  //
  // GATED ON THE LINE THE CHART IS SHOWING. The card sits directly under a
  // chart the user re-lines with the ± stepper, so its placement claims the
  // number on screen — offering the model's Over 0.5 pick under a 3+ chart
  // would hand someone a leg they did not read. slipPickFor is the guard, and
  // it is the same one the sheet this card replaced was built around.
  //
  // This screen's stepper is an "N+" threshold; the market line is the
  // half-point below it, which is how lineFor() converts on the Stats board.
  //
  // OVER ONLY. A prop model's pick is an over at its scored line; offering it
  // under an "Under 1.5" card would hand someone the opposite of the bet they
  // are reading. The card's own bet bar covers the under — the model does not.
  const slipPick = useMemo(() => {
    if (line == null || mode === 'under') return null;
    const idx = buildPickIndex(todayPicks, propModelForStat(stat));
    const found = slipPickFor({ player_id: playerId }, idx, line - 0.5);
    return found && found.pick.result == null ? found : null;
  }, [todayPicks, stat, playerId, line, mode]);
  const slipKey = slipPick ? slipKeyForPick(slipPick.pick) : null;
  const inSlip = slipKey != null && slip.has(slipKey);
  const toggleSlip = () => {
    if (slipKey == null) return;
    const adding = !inSlip;
    slip.toggle(slipKey);
    if (adding && fromParlay) navigation.navigate('Betslip');
  };

  const step = useMemo(() => lineStepFor(stat), [stat]);
  const statLabel = stat?.label ?? '';

  // Reset the line to auto whenever the stat changes — a points line makes no
  // sense for rebounds.
  useEffect(() => {
    setLine(null);
  }, [stat?.key, sport, playerId]);

  // Values come most-recent-first. Window slices the most recent N.
  const windowed = useMemo(
    () => (gameWindow === 'all' ? values : values.slice(0, gameWindow)),
    [values, gameWindow],
  );

  const { avg, median } = useMemo(() => computeAvgMedian(windowed), [windowed]);
  const maxValue = useMemo(() => (values.length ? Math.max(...values) : 0), [values]);

  // Auto-pick a sensible starting line (the median, snapped onto the stepper's
  // grid) once, then keep it sticky across window changes until stat/player changes.
  useEffect(() => {
    if (line == null && median != null) {
      setLine(roundLineToStep(median, step));
    }
  }, [line, median, step]);

  const effLine = line ?? 0;

  // ── The sportsbook line behind the number on screen ────────────────────────
  // The card's threshold and the book's line are the same bet in two idioms:
  // "2+ Hits" is Over 1.5. `selectionFor` is the one translation, shared with
  // the board, so the price can never be fetched for a different bet than the
  // chart is drawing. It holds at every step size — a 250-yard threshold is
  // Over 249.5 exactly as a 2-hit one is Over 1.5.
  const selection = useMemo(() => selectionFor(effLine, mode), [effLine, mode]);
  const market = useMemo(() => propMarketForStat(stat), [stat]);
  const { books } = usePreferredBooks();
  // Threaded into the quote so "which games have not started" re-derives on
  // the tick instead of freezing at mount.
  const now = useNow();
  const propQuote = usePlayerPropQuote({
    sport,
    team: games[0]?.team ?? null,
    playerName,
    market: line == null ? null : market,
    line: selection.line,
    side: selection.side,
    books,
    now,
  });

  // "2+ Total Bases" / "Over 1.5 Total Bases" — the bet in the active idiom.
  // One string, read by the card's headline, the bet bar and the sheet, so
  // they cannot drift into naming the same bet two ways on one screen.
  const headline = useMemo(
    () => hitModeHeadline(effLine, mode, statLabel),
    [effLine, mode, statLabel],
  );

  // The compare sheet — the same AddLineSheet a Stats pill opens, so a line
  // added from here is the same Stats LINE leg, keyed the same way, and
  // re-prices on the betslip exactly like one added from the board.
  const [lineSheet, setLineSheet] = useState<LineSheetInput | null>(null);
  const openCompare = () => {
    if (!propQuote.quote) return;
    setLineSheet(
      propLineSheetInput(propQuote.quote, sport, statLabel, headline, (l, s) =>
        modeLineLabel(l, s, mode),
      ),
    );
  };

  // The board's own hit math, against the book's half-point line and the
  // card's side — so an under card counts unders instead of silently counting
  // overs, and the count agrees with the chart bar for bar.
  const { hits, total: hitTotal, pct: hitPct } = useMemo(
    () => (line == null ? { hits: 0, total: 0, pct: 0 } : computeHitRate(windowed, selection.line, selection.side)),
    [windowed, line, selection],
  );
  // This player has no number at all for the charted stat in the loaded
  // window — a never-filled chip inside a surviving tab, or the position
  // fallback (19 of 138 defensive ends have no sack and no interception in
  // twenty-five games). A red 0% badge there reads "this bet loses" when the
  // truth is "there is nothing here" (UX review, 2026-09-20). An UNDER on the
  // same stat is untouched: 25 of 25 is a real answer to a real question.
  const noEvidence =
    stat != null && (filled.get(chipKey(stat)) ?? 0) === 0 && hitTotal > 0 && hits === 0;
  const noEvidenceText = `No ${statLabel.toLowerCase()} in ${hitTotal} games`;
  const hitColor = noEvidence
    ? colors.none
    : hitPct >= 0.6
      ? colors.bet
      : hitPct >= 0.45
        ? colors.med
        : colors.avoid;

  const stepLine = (deltaSteps: number) => {
    setLine((prev) => {
      const base = prev ?? roundLineToStep(median ?? step, step);
      return Math.min(Math.max(0, base + deltaSteps * step), Math.ceil(maxValue) + step * 5);
    });
  };

  const windowLabel = gameWindow === 'all' ? `${windowed.length} games` : `last ${gameWindow}`;
  const activeGroup = stat?.group ?? groups[0];
  const groupChips = groups.length > 1 ? chips.filter((c) => c.group === activeGroup) : chips;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView contentContainerStyle={styles.list}>
        <View style={styles.header}>
          <View style={styles.headerText}>
            <Text style={styles.playerName}>{playerName}</Text>
            <Text style={styles.meta}>{playerSubtitle(sport, games[0]?.team ?? null, games[0], playerType)}</Text>
            {/* Tonight's matchup, in full. The Stats board's MATCHUP column is
                a bare grade as of 2026-09-05, so this is where the FACT behind
                it lives for a sighted user — Matt's own alternative home for it
                ("have it be in the player data when you click on a record",
                2026-09-04). Only present when the board handed it over, so a
                player opened from anywhere else shows nothing here rather than
                an empty row. */}
            {matchupText ? (
              // Labelled, because VoiceOver drops a bare "+" and would
              // announce a B+ as a B — gradeSpoken exists for exactly this and
              // the screen that now OWNS this fact was the one mis-speaking it
              // (UX review, 2026-09-05).
              <View
                style={styles.matchupRow}
                accessible
                accessibilityLabel={`Tonight's matchup, ${
                  matchupGrade ? `${gradeSpoken(matchupGrade)}, ` : ''
                }${matchupText.replace(/ · /g, ', ')}`}
              >
                {matchupGrade ? (
                  <Text style={[styles.matchupGrade, { color: gradeColor(matchupGrade) }]}>
                    {matchupGrade}
                  </Text>
                ) : null}
                <Text style={styles.matchupLine} numberOfLines={2}>
                  {matchupText}
                </Text>
              </View>
            ) : null}
          </View>
          {/* Recent news, top right — the sentence behind the number. Hidden
              when the feed has nothing on this player, so the header never
              offers a sheet with nothing in it. */}
          <PlayerNewsButton
            playerName={playerName}
            subtitle={playerSubtitle(sport, games[0]?.team ?? null, games[0], playerType)}
            news={news}
          />
        </View>

        {/* Group tabs — the same two-level bar as the Stats tab (Matt,
            2026-09-04). Only sports whose stats span several groups (NFL) show
            a row; one group means the chip row already says everything, and
            when the sport HAS groups but this player fills one, the name is
            kept as a plain header so a linebacker's two chips still say
            "Defense" (UX review, 2026-09-20). */}
        {!loaded ? (
          <View
            style={styles.controlsSkeleton}
            accessible
            accessibilityLabel="Loading this player's stats"
          >
            <View style={[styles.skeletonBlock, { width: '45%' }]} />
            <View style={[styles.skeletonBlock, { width: '70%' }]} />
          </View>
        ) : (
          <>
            {groups.length === 1 && groupsOfChips(allChips).length > 1 ? (
              <Text style={styles.sectionHeader}>{groups[0]}</Text>
            ) : null}
            <GroupTabs
              second={false}
              groups={groups}
              active={activeGroup}
              onChange={(g) => {
                const first = openingChip(chips, filled, g);
                if (first) setPicked(first);
              }}
            />

            {/* Stat selector */}
            <ScrollView
              horizontal
              showsHorizontalScrollIndicator={false}
              contentContainerStyle={styles.windowRow}
            >
              {groupChips.map((c) => {
                const active = c.key === stat?.key && c.group === stat?.group;
                return (
                  <Pressable
                    key={chipKey(c)}
                    onPress={() => setPicked(c)}
                    // Pre-existing (ux_scan a11y-pressable, byte-identical to
                    // master): a chip whose only child is a Text announces as
                    // "button" and nothing else, and neither row said which
                    // chip was ACTIVE. Cleared here because this change made
                    // the stat row the bet-type selector and brought the file
                    // into the reviewed set — the same courtesy the stepper
                    // was paid.
                    accessibilityRole="button"
                    accessibilityState={{ selected: active }}
                    accessibilityLabel={`${c.label} bets`}
                    style={[styles.windowChip, active && styles.windowChipActive]}
                  >
                    <Text style={[styles.windowChipText, active && styles.windowChipTextActive]}>
                      {c.label}
                    </Text>
                  </Pressable>
                );
              })}
            </ScrollView>
          </>
        )}

        {/* Game-range selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.windowRow}
        >
          {windows.map((w) => {
            const active = w.value === gameWindow;
            return (
              <Pressable
                key={String(w.value)}
                onPress={() => setGameWindow(w.value)}
                accessibilityRole="button"
                accessibilityState={{ selected: active }}
                accessibilityLabel={
                  w.value === 'all' ? 'All games' : `Last ${w.value} games`
                }
                style={[styles.windowChip, active && styles.windowChipActive]}
              >
                <Text style={[styles.windowChipText, active && styles.windowChipTextActive]}>
                  {w.label}
                </Text>
              </Pressable>
            );
          })}
        </ScrollView>

        {error ? (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>Connection error: {error}</Text>
          </View>
        ) : null}

        {loading && games.length === 0 ? (
          <ActivityIndicator style={styles.loading} accessibilityLabel="Loading recent games" />
        ) : windowed.length === 0 ? (
          <View style={styles.emptyCard}>
            {/* Two different nothings: no games at all, or games with no value
                for THIS stat (NCAAF leaves a category's columns NULL for a
                player who took no part in it). Saying "no recent games" above
                a populated Recent games list made the screen contradict
                itself (UX review, 2026-09-20). */}
            <Text style={styles.emptyText}>
              {games.length === 0
                ? 'No recent games on file.'
                : `No ${statLabel.toLowerCase()} in the last ${games.length} games.`}
            </Text>
          </View>
        ) : (
          <>
            {/* Hit-rate summary + line stepper */}
            <View style={styles.hitCard}>
              <View style={styles.hitTop}>
                <View>
                  <Text style={styles.hitLabel}>
                    {headline} · {windowLabel}
                  </Text>
                  <Text style={styles.hitCount}>
                    {noEvidence ? noEvidenceText : `Hit ${hits} of ${hitTotal} games`}
                  </Text>
                </View>
                <View
                  style={[styles.hitBadge, { backgroundColor: hitColor }]}
                  accessible
                  accessibilityLabel={
                    noEvidence ? noEvidenceText : `Hit rate ${Math.round(hitPct * 100)} percent`
                  }
                >
                  <Text style={styles.hitBadgeText}>
                    {noEvidence ? '—' : `${Math.round(hitPct * 100)}%`}
                  </Text>
                </View>
              </View>

              <View style={styles.statsRow}>
                <View style={styles.statCell}>
                  <Text style={styles.statCellValue}>{avg != null ? avg.toFixed(1) : '—'}</Text>
                  <Text style={styles.statCellLabel}>Avg</Text>
                </View>
                <View style={styles.statCell}>
                  <Text style={styles.statCellValue}>{median != null ? median.toFixed(1) : '—'}</Text>
                  <Text style={styles.statCellLabel}>Median</Text>
                </View>
                <View style={styles.stepper}>
                  {/* The board's own mode control, not a second one. It opens
                      HitModeSheet, which is the one place the three idioms are
                      shown side by side — "2+ Hits", "Over 1.5 Hits", "Under
                      1.5 Hits" — so nobody hunts for a difference between the
                      first two that isn't there. */}
                  <Pressable
                    onPress={() => setModeOpen(true)}
                    hitSlop={8}
                    accessibilityRole="button"
                    accessibilityLabel={`Direction: ${hitModeLabel(mode)}. Change`}
                    style={({ pressed }) => [styles.modeBtn, pressed && { opacity: 0.7 }]}
                  >
                    <Text style={styles.stepperLabel}>{hitModeLabel(mode)}</Text>
                    <Ionicons name="chevron-down" size={12} color={colors.textSecondary} />
                  </Pressable>
                  {/* Icon-only, so the label is the only thing VoiceOver has
                      — an unlabelled glyph button is announced as "button" and
                      nothing else. Pre-existing; cleared here because this
                      change brought the file into the reviewed set. */}
                  <Pressable
                    onPress={() => stepLine(-1)}
                    hitSlop={8}
                    style={styles.stepBtn}
                    accessibilityRole="button"
                    accessibilityLabel="Lower the line"
                  >
                    <Ionicons name="remove" size={18} color={colors.tint} />
                  </Pressable>
                  <Text style={styles.stepValue}>{rulerValueLabel(effLine, mode)}</Text>
                  <Pressable
                    onPress={() => stepLine(1)}
                    hitSlop={8}
                    style={styles.stepBtn}
                    accessibilityRole="button"
                    accessibilityLabel="Raise the line"
                  >
                    <Ionicons name="add" size={18} color={colors.tint} />
                  </Pressable>
                </View>
              </View>

              {/* The bet, between the control that sets it and the evidence
                  for it. Above the chart because the stepper directly above
                  changes which bet this is and the price is that change's
                  result — and because below a 200pt chart it fell entirely
                  under the fold on a 4.7" phone, which is a poor home for the
                  one thing this screen gained (UX review). NOT pinned:
                  BetslipBar is mounted at the app root and owns the bottom of
                  this screen the moment the slip has a leg. */}
              <PlayerBetBar
                quote={propQuote.quote}
                game={propQuote.game}
                headline={headline}
                mode={mode}
                side={selection.side}
                books={books}
                statLabel={statLabel}
                marketPriced={market != null}
                hasGame={propQuote.hasGame}
                sidePosted={propQuote.sidePosted}
                loading={propQuote.loading}
                error={propQuote.error}
                onRetry={propQuote.reload}
                onCompare={openCompare}
              />

              <HitRateChart
                values={windowed}
                line={selection.line}
                side={selection.side}
                lineLabel={modeLineLabel(selection.line, selection.side, mode, true)}
                avg={avg}
                median={median}
              />

              <View style={styles.legendRow}>
                <View style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: colors.bet }]} />
                  {/* Both halves named in the ACTIVE idiom. "Hit (2+)" beside
                      "Under" read as two different vocabularies on one
                      legend, and on an under card the second one was simply
                      wrong — it labelled the losing bar with the bet. */}
                  <Text style={styles.legendText}>
                    Hit ({modeLineLabel(selection.line, selection.side, mode)})
                  </Text>
                </View>
                <View style={styles.legendItem}>
                  <View style={[styles.legendDot, { backgroundColor: colors.avoid }]} />
                  <Text style={styles.legendText}>Miss</Text>
                </View>
              </View>
            </View>


            {/* The betslip leg. The Stats board's line pills go straight to the
                sportsbook now, so this is the one place a leg joins OUR slip —
                and only where the model actually made a pick, because a leg is
                a bet of record and carries its own line. */}
            {slipPick ? (
              <View style={styles.slipCard}>
                <View style={styles.slipBody}>
                  <Text style={styles.slipLabel} numberOfLines={2}>
                    {slipPick.pick.pick_label}
                  </Text>
                  {decisionOdds(slipPick.pick) != null ? (
                    <Text style={styles.slipPrice}>
                      {formatAmerican(decisionOdds(slipPick.pick))} · {bookName(storedQuoteBook(slipPick.pick))}
                    </Text>
                  ) : null}
                </View>
                <Pressable
                  onPress={toggleSlip}
                  hitSlop={8}
                  accessibilityRole="button"
                  accessibilityLabel={inSlip ? 'Remove from betslip' : 'Add to betslip'}
                  style={({ pressed }) => [
                    styles.slipBtn,
                    inSlip && styles.slipBtnIn,
                    pressed && { opacity: 0.7 },
                  ]}
                >
                  <Ionicons
                    name={inSlip ? 'checkmark' : 'add'}
                    size={16}
                    color={inSlip ? colors.bet : colors.textInverse}
                  />
                  <Text style={[styles.slipBtnText, inSlip && styles.slipBtnTextIn]}>
                    {inSlip ? 'In slip' : 'Add'}
                  </Text>
                </Pressable>
              </View>
            ) : null}

            <TrendStrip
              title={`${statLabel} — rolling averages`}
              trends={trends}
              mode="player"
              unit={statLabel}
            />

            <Text style={styles.sectionHeader}>Recent games</Text>
            {games.map((g) => (
              <GameRow
                key={g.game_id}
                row={g}
                sport={sport}
                stat={stat}
                line={selection.line}
                side={selection.side}
              />
            ))}
          </>
        )}
      </ScrollView>

      <HitModeSheet
        visible={modeOpen}
        mode={mode}
        lineN={effLine}
        statLabel={statLabel}
        onPick={(m) => {
          setMode(m);
          setModeOpen(false);
        }}
        // What the member's books actually sell, from the rows already
        // loaded — so a side none of them prices is closed here rather than
        // answered with an empty bet bar one screen down. A market with no
        // coverage read yet leaves both open: an unknown is not a no.
        overAvailable={propQuote.coverage.size === 0 || anyBookPostsSide(propQuote.coverage, 'over')}
        underAvailable={
          propQuote.coverage.size === 0 || anyBookPostsSide(propQuote.coverage, 'under')
        }
        // WHY the row is greyed. A disabled option with no reason is the "why
        // is FanDuel blank" question in a smaller box — the same sentence the
        // bet bar composes, from the one helper, so the sheet and the card can
        // never explain the same absence two ways.
        unavailableNote={
          propQuote.coverage.size > 0 && !anyBookPostsSide(propQuote.coverage, 'under')
            ? sideNotPostedNote(books, 'under', statLabel)
            : propQuote.coverage.size > 0 && !anyBookPostsSide(propQuote.coverage, 'over')
              ? sideNotPostedNote(books, 'over', statLabel)
              : undefined
        }
        onClose={() => setModeOpen(false)}
      />
      <AddLineSheet
        input={lineSheet}
        game={propQuote.game}
        onClose={() => setLineSheet(null)}
        onAdded={fromParlay ? () => navigation.navigate('Betslip') : undefined}
      />
    </SafeAreaView>
  );
}

function computeAvgMedian(values: number[]): { avg: number | null; median: number | null } {
  if (values.length === 0) return { avg: null, median: null };
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median =
    sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
  return { avg, median };
}

function GameRow({
  row,
  sport,
  stat,
  line,
  side,
}: {
  row: PlayerLogEntry;
  sport: PlayerLogSport;
  stat: StatDef | null;
  /** The book's half-point line, so the dot, the chart and the count all
   *  compare the same number the same way. */
  line: number;
  side: HitDirection;
}) {
  const num = logStatValue(row, stat);
  // Yardage arrives as a NUMERIC string and can be fractional in nflverse — one
  // decimal at most, so a 78-yard game never renders as 78.0000001.
  const value = num == null ? '—' : String(Math.round(num * 10) / 10);
  const hit = isHit(num, line, side);
  return (
    <View style={styles.gameRow}>
      <View style={styles.gameDot}>
        {num != null ? (
          <View
            style={[styles.dot, { backgroundColor: hit ? colors.bet : colors.avoid }]}
          />
        ) : null}
      </View>
      <View style={{ flex: 1 }}>
        <Text style={styles.gameDate}>{row.game_date}</Text>
        <Text style={styles.gameMeta}>{gameContextLine(sport, row)}</Text>
      </View>
      <View style={styles.gameStat}>
        <Text style={styles.gameStatValue}>{value}</Text>
        <Text style={styles.gameStatLabel}>{stat?.label ?? ''}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  slipCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    marginTop: spacing.md,
  },
  slipBody: { flex: 1 },
  slipLabel: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  slipPrice: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  slipBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.tint,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  slipBtnIn: {
    backgroundColor: colors.betSoft,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.bet,
  },
  slipBtnText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  slipBtnTextIn: { color: colors.bet },
  container: { flex: 1, backgroundColor: colors.bg },
  // Clears BetslipBar, which is mounted at the app ROOT and sits over the
  // bottom of this screen whenever the slip has a leg — at 24pt the tail of
  // the game log was underneath it. Pre-existing; this change gave the screen
  // a second way to put a leg in the slip without leaving it, so it now
  // happens to anyone who uses the card as intended.
  list: { paddingBottom: spacing.xxl * 2 },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.sm,
  },
  headerText: { flex: 1, paddingRight: spacing.md },
  playerName: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  meta: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  // Its own row rather than a third meta line: at the same size and colour as
  // `meta` directly above it, the fact the GRADE column now depends on was
  // visually indistinguishable from the player's identity subtitle, and a
  // reader scanned straight past it (UX review, 2026-09-05).
  matchupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginTop: spacing.xs,
    paddingTop: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  matchupLine: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  matchupGrade: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
  },
  windowRow: {
    paddingHorizontal: spacing.lg,
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  windowChip: {
    paddingHorizontal: 14,
    paddingVertical: 7,
    borderRadius: radii.pill,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.separator,
  },
  windowChipActive: {
    backgroundColor: colors.tint,
    borderColor: colors.tint,
  },
  windowChipText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  windowChipTextActive: {
    color: colors.textInverse,
  },
  hitCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.sm,
    marginBottom: spacing.md,
    padding: spacing.md,
  },
  hitTop: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  hitLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
  },
  hitCount: {
    fontSize: font.size.headline,
    color: colors.textPrimary,
    fontWeight: font.weight.bold,
    marginTop: 2,
  },
  hitBadge: {
    minWidth: 56,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: radii.md,
    alignItems: 'center',
  },
  hitBadgeText: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textInverse,
  },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
    gap: spacing.lg,
  },
  statCell: {
    alignItems: 'center',
  },
  statCellValue: {
    fontSize: font.size.callout,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  statCellLabel: {
    fontSize: font.size.nano,
    color: colors.textTertiary,
    marginTop: 1,
  },
  stepper: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'flex-end',
    gap: spacing.sm,
  },
  stepperLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  // 44pt tall so the control that changes which BET the screen is about meets
  // the minimum target, which a bare text label did not.
  modeBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
    minHeight: 44,
    paddingRight: spacing.xs,
    justifyContent: 'center',
  },
  stepBtn: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: colors.noneSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepValue: {
    minWidth: 26,
    textAlign: 'center',
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  legendRow: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: spacing.lg,
    marginTop: spacing.sm,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  sectionHeader: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.sm,
  },
  gameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
  },
  gameDot: {
    width: 16,
    alignItems: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  gameDate: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  gameMeta: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
  },
  gameStat: {
    alignItems: 'flex-end',
  },
  gameStatValue: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  gameStatLabel: {
    fontSize: font.size.nano,
    color: colors.textTertiary,
    marginTop: 1,
  },
  // Holds the stat controls' slot while the log loads, so the row does not
  // appear, offer a tab this player cannot fill, and withdraw it.
  controlsSkeleton: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    paddingBottom: spacing.xs,
    gap: spacing.sm,
  },
  skeletonBlock: {
    height: 10,
    borderRadius: radii.sm,
    backgroundColor: colors.noneSoft,
  },
  emptyCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    alignItems: 'center',
  },
  emptyText: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  loading: { marginVertical: spacing.xxl },
  errorBanner: {
    backgroundColor: colors.avoidSoft,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
    borderRadius: 8,
  },
  errorText: { color: colors.avoid, fontSize: font.size.footnote },
});
