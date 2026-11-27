import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, AppState, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { Modal } from '@/components/TrackedModal';
import { SegmentTabs } from '@/components/GroupTabs';
import {
  BET_ALL_LIVE_NOTE,
  BET_ALL_SINGLES_NOTE,
  BET_ALL_SKIP_TEXT,
  bestLinePlan,
  bookCoverage,
  quoteForBestLine,
  oneBookPlan,
  planTotals,
  type BetAllCandidates,
  type BetAllLeg,
  type BetAllMode,
  type BetAllPick,
  type BetAllStep,
} from '@/lib/betAll';
import { bookLabel, bookName, storedQuoteBook } from '@/lib/markets';
import { foundAtText } from '@/lib/myBooks';
import { decisionOdds } from '@/lib/decisionPrice';
import { linesPriceText } from '@/lib/linesBoard';
import { trueMinus } from '@/lib/signalsCard';
import { formatAmerican, formatUnits } from '@/lib/format';
import { stakeFor } from '@/lib/thresholds';
import { openBookBetslip } from '@/lib/sportsbookLinks';
import { colors, font, radii, spacing, sectionHeaderText, opacity, cardDense } from '@/lib/theme';
import type { Pick } from '@/types';
import { PrimaryButton } from '@/components/PrimaryButton';
import { sportDisplayName } from '@/lib/liveSports';

interface Props {
  visible: boolean;
  sport: string;
  /** Name each pick's sport on its row: the all-sports sheet holds several
   *  (Matt, 2026-11-27), and a label alone does not say which. */
  showSport?: boolean;
  candidates: BetAllCandidates;
  myBooks: readonly string[];
  /** Whether a pick is already in the member's tracked bets
   *  (useTrackedBets.isTracked). The tick on each pick reads this, so a
   *  tick is the tracked state itself, not a copy of it. */
  isTracked: (pick: Pick) => boolean;
  /** Adds placed bets to the member's tracked bets, all in one write
   *  (useTrackedBets.trackMany). */
  onTrack: (picks: Pick[]) => void;
  /** Takes a pick back out of tracked bets (useTrackedBets.untrackPick). */
  onUntrack: (pick: Pick) => void;
  onClose: () => void;
}

/** Picks split by sport, in the order each sport first appears. */
function bySport(ps: readonly BetAllPick[]): [string, BetAllPick[]][] {
  const m = new Map<string, BetAllPick[]>();
  for (const p of ps) {
    const s = p.pick.sport ?? '';
    m.set(s, [...(m.get(s) ?? []), p]);
  }
  return [...m.entries()];
}

function stakeText(risk: number, win: number): string {
  return `Bet ${formatUnits(risk)} · Win ${formatUnits(win)}`;
}

/**
 * Bet all (Matt, 2026-11-14): every pre-game signal for one sport (or, from the top of Picks, every
 * sport: Matt, 2026-11-27), sent to
 * the member's sportsbooks as single bets. Best line is the default; One
 * sportsbook puts every pick it has at one book. Live bets are not part of
 * it, and the sheet says so. lib/betAll.ts holds the rules.
 *
 * Two phases. Choose: the picks, ticked by default, and the mode. Send: the
 * books as a list, opened one at a time, each pick with a Placed tick.
 *
 * Tracking is per pick (Matt, 2026-11-20, replacing the per-book placed
 * question and the warning on close): ticking a
 * pick tracks it at once, unticking takes it back out, and a book with more
 * than one pick has a "Placed all" shortcut. Nothing waits for an answer, so
 * closing the sheet never loses a placed bet and never needs a warning.
 */
export function BetAllSheet({ visible, sport, showSport = false, candidates, myBooks, isTracked, onTrack, onUntrack, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { picks: allPicks, skipped } = candidates;
  const [mode, setMode] = useState<BetAllMode>('best');
  // EVERY PICK ON THE BOARD, TRACKED ONES INCLUDED (Matt, 2026-11-21,
  // replacing the same day's "Untracked only" switch once the board gained
  // its own Tracked filter): Bet all sends what the board shows. A tracked
  // pick is listed and ticked like any other, marked "Tracking"; to leave
  // them out, pick "Not tracked" in the board's filter sheet.
  const picks = allPicks;
  // The picks already tracked when Start was tapped. The send step's progress
  // counts only bets placed in THIS run, so a pick tracked before it does not
  // read as done here (UX review, 2026-11-21).
  const [trackedAtStart, setTrackedAtStart] = useState<Set<string>>(() => new Set());
  const [selected, setSelected] = useState<Set<string>>(() => new Set(allPicks.map((p) => p.key)));
  const [book, setBook] = useState<string | null>(null);
  const [phase, setPhase] = useState<'choose' | 'send'>('choose');
  const [steps, setSteps] = useState<BetAllStep[]>([]);
  const [opened, setOpened] = useState<Set<string>>(() => new Set());
  const awaiting = useRef<string | null>(null);
  // Tracked picks that are ticked: named above the button so a bet already
  // placed is never sent to a book again unnoticed (UX review, 2026-11-21).
  // Read AFTER `selected` is declared: above it, the shipped bundle reads
  // `selected` as undefined and every open of the sheet crashed (2026-11-21).
  const trackedTicked = picks.filter((p) => selected.has(p.key) && isTracked(p.pick)).length;

  // A fresh sheet every time it opens: every pick ticked, Best line.
  const pickKeys = allPicks.map((p) => p.key).join(',');
  useEffect(() => {
    if (!visible) return;
    setMode('best');
    setSelected(new Set(allPicks.map((p) => p.key)));
    setBook(null);
    setPhase('choose');
    setSteps([]);
    setOpened(new Set());
    awaiting.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);
  // A pick that leaves the board (its game started) leaves the selection.
  useEffect(() => {
    setSelected((prev) => new Set([...prev].filter((k) => allPicks.some((p) => p.key === k))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickKeys]);

  // Back from a book: no question, only a spoken nudge for VoiceOver (iOS
  // has no live regions), since a sighted member sees the ticks.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active' && awaiting.current) {
        AccessibilityInfo.announceForAccessibility(`Back from ${bookName(awaiting.current)}. Tick each bet you placed to track it.`);
        awaiting.current = null;
      }
    });
    return () => sub.remove();
  }, []);

  const coverage = useMemo(() => bookCoverage(picks, selected, myBooks), [picks, selected, myBooks]);
  const chosenBook = book && coverage.some((c) => c.bookmaker === book) ? book : coverage[0]?.bookmaker ?? null;
  const bestSteps = useMemo(() => bestLinePlan(picks, selected), [picks, selected]);
  const onePlan = useMemo(
    () => (chosenBook ? oneBookPlan(picks, selected, chosenBook) : { step: null, missing: [] as BetAllPick[] }),
    [picks, selected, chosenBook],
  );
  const planSteps = mode === 'best' ? bestSteps : onePlan.step ? [onePlan.step] : [];
  const totals = planTotals(planSteps);

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const openStep = async (step: BetAllStep, link: string | null) => {
    const opened = await openBookBetslip(step.bookmaker, link, { sameBookOnly: true });
    if (!opened) return;
    awaiting.current = step.bookmaker;
    setOpened((prev) => new Set(prev).add(step.bookmaker));
  };

  const start = () => {
    if (planSteps.length === 0) return;
    setSteps(planSteps);
    setTrackedAtStart(
      new Set(planSteps.flatMap((s) => s.legs).filter((l) => isTracked(l.pick)).map((l) => l.key)),
    );
    setOpened(new Set());
    setPhase('send');
    // One book: no list to read first, open it straight away.
    if (planSteps.length === 1) void openStep(planSteps[0]!, planSteps[0]!.links[0] ?? null);
  };

  // One tick per pick: ticking tracks it now, unticking takes it back out.
  const togglePlaced = (leg: BetAllLeg) => {
    if (isTracked(leg.pick)) onUntrack(leg.pick);
    else onTrack([leg.pick]);
  };
  const placeAll = (step: BetAllStep) => {
    const rest = step.legs.filter((l) => !isTracked(l.pick)).map((l) => l.pick);
    if (rest.length > 0) onTrack(rest);
  };

  // Legs this run is waiting on: a leg tracked before Start is not one.
  const runLegs = (step: BetAllStep) => step.legs.filter((l) => !trackedAtStart.has(l.key));
  const trackedIn = (step: BetAllStep) => runLegs(step).filter((l) => isTracked(l.pick)).length;
  const totalLegs = steps.reduce((n, s) => n + runLegs(s).length, 0);
  const placedLegs = steps.reduce((n, s) => n + trackedIn(s), 0);
  const nextStep = steps.find((s) => trackedIn(s) < runLegs(s).length);

  // "NFL · " before a row's detail, on the all-sports sheet only.
  const sportPrefix = (pick: Pick) => (showSport && pick.sport ? `${sportDisplayName(pick.sport)} · ` : '');

  const pickRow = (p: BetAllPick, i: number) => {
    const inBookMode = mode === 'book' && chosenBook != null;
    const q = inBookMode ? p.quotes.find((x) => x.bookmaker === chosenBook) ?? null : quoteForBestLine(p);
    const available = q != null;
    const on = selected.has(p.key) && available;
    const best = p.quotes[0]!;
    const notBest = inBookMode && q != null && q.price !== best.price && q.bookmaker !== best.bookmaker;
    const stake = q ? stakeFor(p.pick.kelly_fraction, q.price, p.pick.stake_units) : null;
    // Where the model found it, whenever the price shown is another book's
    // (UX_REVIEW §0, the card's "Found at HRB +110"). The record stays there.
    const record = storedQuoteBook(p.pick);
    const modelPrice = decisionOdds(p.pick);
    const tracked = isTracked(p.pick);
    const foundAt =
      q && q.bookmaker !== record && modelPrice != null ? ` · ${foundAtText(bookLabel(record), formatAmerican(modelPrice))}` : '';
    const detail = !available
      ? `Not at ${bookName(chosenBook!)}`
      : notBest
        ? `${stakeText(stake!.risk, stake!.win)} · ${bookLabel(best.bookmaker)} ${linesPriceText(best.price)} is better${foundAt}`
        : `${stakeText(stake!.risk, stake!.win)}${foundAt}`;
    const sub = `${sportPrefix(p.pick)}${tracked ? `Tracking · ${detail}` : detail}`;
    return (
      <Pressable
        key={p.key}
        onPress={() => available && toggle(p.key)}
        disabled={!available}
        accessibilityRole="checkbox"
        accessibilityState={{ checked: on, disabled: !available }}
        accessibilityLabel={`${trueMinus(p.label)}, ${q ? linesPriceText(q.price) : 'not available'}. ${sub}`}
        style={({ pressed }) => [styles.row, i > 0 && styles.rowDivider, pressed && styles.pressed]}
      >
        <Ionicons
          name={!available ? 'remove-circle-outline' : on ? 'checkmark-circle' : 'ellipse-outline'}
          size={22}
          color={!available ? colors.textTertiary : on ? colors.tint : colors.textTertiary}
        />
        <View style={styles.rowBody}>
          <Text style={[styles.rowTitle, !available && styles.muted]} numberOfLines={2}>
            {trueMinus(p.label)}
          </Text>
          <Text style={styles.rowSub} numberOfLines={2}>
            {/* Same word as the card's Track button, so the two read as one state. `sub` adds the
                sport for VoiceOver only: on screen the sport is the group's header (UX review). */}
            {tracked ? <Text style={styles.trackedTag}>Tracking</Text> : null}
            {tracked ? ` · ${detail}` : detail}
          </Text>
        </View>
        <Text style={[styles.price, !available && styles.muted]}>{q ? linesPriceText(q.price) : '—'}</Text>
      </Pressable>
    );
  };

  // Best line: picks grouped under the book the plan will open.
  // On the all-sports sheet each book splits by sport, under a sport header,
  // so the row's footnote keeps its room for "Found at" (UX review, 2026-11-27).
  const bestGroups = useMemo(() => {
    const m = new Map<string, BetAllPick[]>();
    for (const p of picks) {
      const b = quoteForBestLine(p).bookmaker;
      m.set(b, [...(m.get(b) ?? []), p]);
    }
    return [...m.entries()]
      .sort((a, b) => b[1].length - a[1].length)
      .flatMap(([b, ps]) =>
        showSport
          ? bySport(ps).map(([s, sp]) => ({ key: `${b}:${s}`, title: `${sportDisplayName(s)} · ${bookName(b)} · best line`, picks: sp }))
          : [{ key: b, title: `${bookName(b)} · best line`, picks: ps }],
      );
  }, [picks, showSport]);
  const bookGroups = useMemo(
    () =>
      showSport
        ? bySport(picks).map(([s, sp]) => ({ key: s, title: sportDisplayName(s), picks: sp }))
        : [{ key: 'all', title: null as string | null, picks }],
    [picks, showSport],
  );

  const allSelected = picks.length > 0 && picks.every((p) => selected.has(p.key));
  // Picks on the list that are ticked.
  const selectedShown = picks.filter((p) => selected.has(p.key)).length;

  const ctaLabel =
    totals.legs === 0
      ? 'Select a pick'
      : planSteps.length === 1
        ? `Open ${planSteps[0]!.name} with ${totals.legs} ${totals.legs === 1 ? 'pick' : 'picks'}`
        : `Start · ${planSteps.length} sportsbooks, one at a time`;

  return (
    <Modal trackName="BetAllSheet" visible={visible} animationType="slide" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          // Mid-send a stray tap would lose the member's place in the book
          // list (reopening starts at Choose); the X and Done still close,
          // and with every tick already tracked there is nothing to warn about.
          onPress={phase === 'send' ? undefined : onClose}
          accessibilityRole="button"
          accessibilityLabel="Close Bet all"
          accessible={phase !== 'send'}
        />
        <Pressable
          style={[styles.sheet, { paddingBottom: Math.max(insets.bottom, spacing.lg) }]}
          onPress={() => {}}
          accessible={false}
          accessibilityViewIsModal
        >
          <View style={styles.grabber} />
          <View style={styles.header}>
            <View style={styles.headerBody}>
              <Text style={styles.title} accessibilityRole="header">
                {phase === 'choose' ? `Bet all · ${sport}` : `Bet all · ${placedLegs} of ${totalLegs} tracked`}
              </Text>
              <Text style={styles.subtitle}>
                {phase === 'choose'
                  ? showSport
                    ? `Every sport’s signals. Board filters don’t apply. ${BET_ALL_LIVE_NOTE}`
                    : BET_ALL_LIVE_NOTE
                  : 'Tick each bet once you’ve placed it to track it.'}
              </Text>
            </View>
            <Pressable onPress={onClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close Bet all">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          {phase === 'choose' ? (
            <>
              <View style={styles.segment}>
                <SegmentTabs
                  items={['best', 'book'] as const}
                  active={mode}
                  onChange={setMode}
                  labelFor={(m) => (m === 'best' ? 'Best line' : 'One sportsbook')}
                />
              </View>
              {picks.length > 1 ? (
                <Pressable
                  // Acts on every pick shown, tracked ones included.
                  onPress={() =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      for (const p of picks) {
                        if (allSelected) next.delete(p.key);
                        else next.add(p.key);
                      }
                      return next;
                    })
                  }
                  accessibilityRole="button"
                  accessibilityLabel={allSelected ? 'Select none' : 'Select all'}
                  hitSlop={12}
                  style={styles.selectAll}
                >
                  <Text style={styles.link}>{allSelected ? 'Select none' : 'Select all'}</Text>
                </Pressable>
              ) : null}

              {mode === 'book' && coverage.length > 0 ? (
                <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips} contentContainerStyle={styles.chipsRow}>
                  {coverage.map((c) => {
                    const on = c.bookmaker === chosenBook;
                    return (
                      <Pressable
                        key={c.bookmaker}
                        onPress={() => setBook(c.bookmaker)}
                        accessibilityRole="button"
                        accessibilityState={{ selected: on }}
                        accessibilityLabel={`${c.name}, has ${c.covered} of ${selectedShown}, ${c.atBest} at the best price`}
                        style={[styles.chip, on && styles.chipOn]}
                      >
                        <Text style={[styles.chipBook, on && styles.chipBookOn]}>{c.short}</Text>
                        <Text style={styles.chipMeta}>{`${c.covered} of ${selectedShown}`}</Text>
                      </Pressable>
                    );
                  })}
                </ScrollView>
              ) : null}

              <ScrollView style={styles.list} bounces={false}>
                {mode === 'best' ? (
                  bestGroups.map((g) => (
                    <View key={g.key} style={styles.group}>
                      <Text style={styles.groupTitle} accessibilityRole="header">{g.title}</Text>
                      <View style={styles.card}>{g.picks.map(pickRow)}</View>
                    </View>
                  ))
                ) : (
                  <View style={styles.group}>
                    {bookGroups.map((g) => (
                      <View key={g.key} style={g.title ? styles.group : undefined}>
                        {g.title ? <Text style={styles.groupTitle} accessibilityRole="header">{g.title}</Text> : null}
                        <View style={styles.card}>{g.picks.map(pickRow)}</View>
                      </View>
                    ))}
                    {onePlan.missing.length > 0 && chosenBook ? (
                      <Text style={styles.warn}>
                        {`${onePlan.missing.length} selected ${onePlan.missing.length === 1 ? 'pick isn’t' : 'picks aren’t'} at ${bookName(chosenBook)}. Best line includes ${onePlan.missing.length === 1 ? 'it' : 'them'}.`}
                      </Text>
                    ) : null}
                  </View>
                )}
                {skipped.length > 0 ? (
                  <View style={styles.group}>
                    <Text style={styles.groupTitle}>Not included</Text>
                    <View style={styles.card}>
                      {skipped.map((s, i) => (
                        <View key={s.key} style={[styles.row, i > 0 && styles.rowDivider]} accessible accessibilityLabel={`${sportPrefix(s.pick)}${trueMinus(s.label)}, not included, ${BET_ALL_SKIP_TEXT[s.reason]}`}>
                          <View style={styles.rowBody}>
                            <Text style={[styles.rowTitle, styles.muted]} numberOfLines={2}>{trueMinus(s.label)}</Text>
                            <Text style={styles.rowSub}>{`${sportPrefix(s.pick)}${BET_ALL_SKIP_TEXT[s.reason]}`}</Text>
                          </View>
                        </View>
                      ))}
                    </View>
                  </View>
                ) : null}
              </ScrollView>

              <View style={styles.footer}>
                {trackedTicked > 0 ? (
                  <Text style={styles.warn}>
                    {`${trackedTicked} you’re already tracking ${trackedTicked === 1 ? 'is' : 'are'} included. Untick ${trackedTicked === 1 ? 'it' : 'them'}, or pick Not tracked in Filters to leave ${trackedTicked === 1 ? 'it' : 'them'} out.`}
                  </Text>
                ) : null}
                <Text style={styles.summary}>
                  {totals.legs === 0
                    ? 'No picks selected'
                    : `${totals.legs} single ${totals.legs === 1 ? 'bet' : 'bets'} · ${planSteps.length} ${planSteps.length === 1 ? 'sportsbook' : 'sportsbooks'} · ${stakeText(totals.risk, totals.win)}`}
                </Text>
                <PrimaryButton label={ctaLabel} onPress={start} disabled={totals.legs === 0} />
              </View>
            </>
          ) : (
            <>
              <ScrollView style={styles.list} bounces={false}>
                {steps.map((step) => {
                  const n = trackedIn(step);
                  const runN = runLegs(step).length;
                  const all = n === runN;
                  const isNext = step === nextStep;
                  const statusText = runN === 0
                    ? 'Already tracking'
                    : all
                    ? 'All tracked'
                    : n > 0
                      ? `${n} of ${runN} tracked`
                      : opened.has(step.bookmaker)
                        ? 'Tick what you placed'
                        : isNext
                          ? 'Next'
                          : 'Waiting';
                  return (
                    <View key={step.bookmaker} style={[styles.step, isNext && styles.stepNext]}>
                      <View style={styles.stepTop}>
                        <Text style={styles.stepTitle}>{`${step.name} · ${step.legs.length} ${step.legs.length === 1 ? 'pick' : 'picks'}`}</Text>
                        <Text style={[styles.stepStatus, n > 0 && styles.stepPlaced]}>{statusText}</Text>
                      </View>
                      {step.legs.map((l) => {
                        const on = isTracked(l.pick);
                        return (
                          <Pressable
                            key={l.key}
                            onPress={() => togglePlaced(l)}
                            accessibilityRole="checkbox"
                            accessibilityState={{ checked: on }}
                            accessibilityLabel={`Placed: ${sportPrefix(l.pick)}${trueMinus(l.label)} ${linesPriceText(l.price)}, ${stakeText(l.stake.risk, l.stake.win)}${trackedAtStart.has(l.key) ? ', already tracking' : ''}`}
                            accessibilityHint={on ? 'Takes it out of tracked bets' : 'Adds it to tracked bets'}
                            style={({ pressed }) => [styles.leg, pressed && styles.pressed]}
                          >
                            <Ionicons
                              name={on ? 'checkmark-circle' : 'ellipse-outline'}
                              size={22}
                              color={on ? colors.betInk : colors.textTertiary}
                            />
                            <View style={styles.rowBody}>
                              <Text style={styles.legLabel} numberOfLines={2}>{`${trueMinus(l.label)} ${linesPriceText(l.price)}`}</Text>
                              <Text style={styles.legStake}>
                                {trackedAtStart.has(l.key)
                                  ? `${sportPrefix(l.pick)}${stakeText(l.stake.risk, l.stake.win)} · Already tracking`
                                  : `${sportPrefix(l.pick)}${stakeText(l.stake.risk, l.stake.win)}`}
                              </Text>
                            </View>
                          </Pressable>
                        );
                      })}
                      {all ? null : (
                        <>
                          {step.legs.length > 1 ? (
                            <Pressable
                              onPress={() => placeAll(step)}
                              accessibilityRole="button"
                              accessibilityLabel={`Placed all ${step.legs.length} at ${step.name}, track them`}
                              hitSlop={8}
                              style={styles.markPlaced}
                            >
                              <Text style={styles.link}>{`Placed all ${step.legs.length}`}</Text>
                            </Pressable>
                          ) : null}
                          {step.links.length <= 1 ? (
                            <Pressable
                              onPress={() => void openStep(step, step.links[0] ?? null)}
                              accessibilityRole="button"
                              accessibilityLabel={`Open ${step.name}`}
                              accessibilityHint={`Opens ${step.name} with these picks on the slip`}
                              style={({ pressed }) => [styles.open, pressed && styles.pressed]}
                            >
                              <Text style={styles.openText}>{`Open ${step.name}`}</Text>
                            </Pressable>
                          ) : (
                            step.links.map((link, i) => (
                              <Pressable
                                key={link}
                                onPress={() => void openStep(step, link)}
                                accessibilityRole="button"
                                accessibilityLabel={`Add pick ${i + 1} of ${step.links.length} in ${step.name}`}
                                style={({ pressed }) => [styles.open, pressed && styles.pressed]}
                              >
                                <Text style={styles.openText}>{`Add pick ${i + 1} of ${step.links.length} in ${step.short}`}</Text>
                              </Pressable>
                            ))
                          )}
                          {step.links.length > 1 ? (
                            <Text style={styles.note}>{`${step.name} takes one pick per link. Come back here for the next one.`}</Text>
                          ) : null}
                          {step.unlinked.length > 0 ? (
                            <Text style={styles.note}>
                              {`${step.unlinked.length === 1 ? 'One pick' : `${step.unlinked.length} picks`} can’t be added by link. Find ${step.unlinked.length === 1 ? 'it' : 'them'} in ${step.name}.`}
                            </Text>
                          ) : null}
                        </>
                      )}
                    </View>
                  );
                })}
                <Text style={styles.note}>{BET_ALL_SINGLES_NOTE}</Text>
              </ScrollView>
              <View style={styles.footer}>
                {placedLegs > 0 ? <Text style={styles.summary}>Untick a bet to take it out of tracked bets.</Text> : null}
                <PrimaryButton label="Done" onPress={onClose} />
              </View>
            </>
          )}
        </Pressable>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: colors.scrim, justifyContent: 'flex-end' },
  sheet: {
    backgroundColor: colors.bg,
    borderTopLeftRadius: radii.lg,
    borderTopRightRadius: radii.lg,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    maxHeight: '90%',
    flexShrink: 1,
  },
  grabber: {
    alignSelf: 'center',
    width: 40,
    height: 4,
    borderRadius: 2,
    backgroundColor: colors.separatorOpaque,
    marginBottom: spacing.sm,
  },
  header: { flexDirection: 'row', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: spacing.md },
  headerBody: { flex: 1, paddingRight: spacing.md },
  title: { fontSize: font.size.title3, fontWeight: font.weight.bold, color: colors.textPrimary },
  subtitle: { fontSize: font.size.footnote, color: colors.textSecondary, marginTop: 2 },
  segment: { marginBottom: spacing.sm },
  selectAll: { alignSelf: 'flex-end', minHeight: 44, justifyContent: 'center' },
  markPlaced: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
  chips: { flexGrow: 0, marginBottom: spacing.md },
  chipsRow: { gap: spacing.sm },
  chip: {
    minWidth: 64,
    minHeight: 44,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    borderWidth: 1.5,
    borderColor: colors.separatorOpaque,
    alignItems: 'center',
    justifyContent: 'center',
  },
  chipOn: { borderColor: colors.tint },
  chipBook: { fontSize: font.size.footnote, fontWeight: font.weight.bold, color: colors.textSecondary },
  chipBookOn: { color: colors.textPrimary },
  chipMeta: { fontSize: font.size.caption, color: colors.textSecondary, fontVariant: ['tabular-nums'] },
  list: { flexGrow: 0, flexShrink: 1 },
  group: { marginBottom: spacing.md },
  groupTitle: {
    ...sectionHeaderText,
    marginBottom: spacing.xs,
    marginLeft: spacing.xs,
  },
  card: { backgroundColor: colors.bgCard, borderRadius: radii.md, overflow: 'hidden' },
  row: {
    minHeight: 52,
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
  },
  rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.separator },
  rowBody: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary },
  // Not tint: tint is the tick beside it, and the tag must not blend into it.
  trackedTag: { color: colors.medInk, fontWeight: font.weight.semibold },
  rowSub: { marginTop: 2, fontSize: font.size.footnote, color: colors.textSecondary, fontVariant: ['tabular-nums'] },
  price: { fontSize: font.size.body, fontWeight: font.weight.semibold, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  muted: { color: colors.textTertiary },
  warn: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.medInk,
    backgroundColor: colors.medSoft,
    borderRadius: radii.sm,
    padding: spacing.sm,
    overflow: 'hidden',
  },
  footer: { paddingTop: spacing.sm, gap: spacing.sm },
  summary: { fontSize: font.size.footnote, color: colors.textSecondary, fontVariant: ['tabular-nums'] },
  step: { ...cardDense, marginBottom: spacing.sm, gap: spacing.sm },
  stepNext: { borderWidth: 1.5, borderColor: colors.tint },
  stepTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.sm },
  stepTitle: { flex: 1, fontSize: font.size.body, fontWeight: font.weight.bold, color: colors.textPrimary },
  stepStatus: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textSecondary },
  stepPlaced: { color: colors.betInk },
  leg: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  legLabel: { flex: 1, fontSize: font.size.footnote, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  legStake: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textPrimary, fontVariant: ['tabular-nums'] },
  open: {
    minHeight: 44,
    borderRadius: radii.pill,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
  },
  openText: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textInverse },
  link: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.tint },
  note: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18, marginBottom: spacing.sm },
  pressed: { opacity: opacity.pressed },
});
