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
  oneBookPlan,
  planTotals,
  type BetAllCandidates,
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

type StepStatus = 'todo' | 'opened' | 'placed' | 'skipped';

interface Props {
  visible: boolean;
  sport: string;
  candidates: BetAllCandidates;
  myBooks: readonly string[];
  /** Adds a placed bet to the member's tracked bets (useTrackedBets.track). */
  onTrack: (pick: Pick) => void;
  onClose: () => void;
}

function stakeText(risk: number, win: number): string {
  return `Bet ${formatUnits(risk)} · Win ${formatUnits(win)}`;
}

/**
 * Bet all (Matt, 2026-11-14): every pre-game signal for one sport, sent to
 * the member's sportsbooks as single bets. Best line is the default; One
 * sportsbook puts every pick it has at one book. Live bets are not part of
 * it, and the sheet says so. lib/betAll.ts holds the rules.
 *
 * Two phases. Choose: the picks, ticked by default, and the mode. Send: the
 * books as a list, opened one at a time. Coming back from a book asks once
 * whether the bets were placed; Placed adds them to tracked bets.
 */
export function BetAllSheet({ visible, sport, candidates, myBooks, onTrack, onClose }: Props) {
  const insets = useSafeAreaInsets();
  const { picks, skipped } = candidates;
  const [mode, setMode] = useState<BetAllMode>('best');
  const [selected, setSelected] = useState<Set<string>>(() => new Set(picks.map((p) => p.key)));
  const [book, setBook] = useState<string | null>(null);
  const [phase, setPhase] = useState<'choose' | 'send'>('choose');
  const [steps, setSteps] = useState<BetAllStep[]>([]);
  const [status, setStatus] = useState<Record<string, StepStatus>>({});
  const [askFor, setAskFor] = useState<string | null>(null);
  const awaiting = useRef<string | null>(null);
  const [confirmStop, setConfirmStop] = useState(false);

  // A fresh sheet every time it opens: every pick ticked, Best line.
  const pickKeys = picks.map((p) => p.key).join(',');
  useEffect(() => {
    if (!visible) return;
    setMode('best');
    setSelected(new Set(picks.map((p) => p.key)));
    setBook(null);
    setPhase('choose');
    setSteps([]);
    setStatus({});
    setAskFor(null);
    setConfirmStop(false);
    awaiting.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible]);
  // A pick that leaves the board (its game started) leaves the selection.
  useEffect(() => {
    setSelected((prev) => new Set([...prev].filter((k) => picks.some((p) => p.key === k))));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pickKeys]);

  // Back from a book: ask once about that book's bets.
  useEffect(() => {
    const sub = AppState.addEventListener('change', (next) => {
      if (next === 'active' && awaiting.current) {
        setAskFor(awaiting.current);
        awaiting.current = null;
      }
    });
    return () => sub.remove();
  }, []);

  // iOS has no live regions: say the question out loud when it appears
  // (UX review), so a VoiceOver user is asked about the bets they placed.
  useEffect(() => {
    if (askFor) {
      AccessibilityInfo.announceForAccessibility(`Back from ${bookName(askFor)}. Did you place these bets as singles?`);
    }
  }, [askFor]);

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
    setStatus((s) => ({ ...s, [step.bookmaker]: s[step.bookmaker] === 'placed' ? 'placed' : 'opened' }));
  };

  const start = () => {
    if (planSteps.length === 0) return;
    setSteps(planSteps);
    setStatus(Object.fromEntries(planSteps.map((s) => [s.bookmaker, 'todo' as StepStatus])));
    setPhase('send');
    // One book: no list to read first, open it straight away.
    if (planSteps.length === 1) void openStep(planSteps[0]!, planSteps[0]!.links[0] ?? null);
  };

  const answer = (book: string, placed: 'placed' | 'todo' | 'skipped') => {
    if (placed === 'placed') {
      const step = steps.find((s) => s.bookmaker === book);
      step?.legs.forEach((l) => onTrack(l.pick));
    }
    setStatus((s) => ({ ...s, [book]: placed }));
    setAskFor(null);
  };

  const doneCount = steps.filter((s) => status[s.bookmaker] === 'placed' || status[s.bookmaker] === 'skipped').length;
  const allDone = phase === 'send' && steps.length > 0 && doneCount === steps.length;
  const placedLegs = steps
    .filter((s) => status[s.bookmaker] === 'placed')
    .reduce((n, s) => n + s.legs.length, 0);
  const nextStep = steps.find((s) => status[s.bookmaker] === 'todo' || status[s.bookmaker] === 'opened');

  const pickRow = (p: BetAllPick, i: number) => {
    const inBookMode = mode === 'book' && chosenBook != null;
    const q = inBookMode ? p.quotes.find((x) => x.bookmaker === chosenBook) ?? null : p.quotes[0]!;
    const available = q != null;
    const on = selected.has(p.key) && available;
    const best = p.quotes[0]!;
    const notBest = inBookMode && q != null && q.price !== best.price && q.bookmaker !== best.bookmaker;
    const stake = q ? stakeFor(p.pick.kelly_fraction, q.price, p.pick.stake_units) : null;
    // Where the model found it, whenever the price shown is another book's
    // (UX_REVIEW §0, the card's "Found at HRB +110"). The record stays there.
    const record = storedQuoteBook(p.pick);
    const modelPrice = decisionOdds(p.pick);
    const foundAt =
      q && q.bookmaker !== record && modelPrice != null ? ` · ${foundAtText(bookLabel(record), formatAmerican(modelPrice))}` : '';
    const sub = !available
      ? `Not at ${bookName(chosenBook!)}`
      : notBest
        ? `${stakeText(stake!.risk, stake!.win)} · ${bookLabel(best.bookmaker)} ${linesPriceText(best.price)} is better${foundAt}`
        : `${stakeText(stake!.risk, stake!.win)}${foundAt}`;
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
            {sub}
          </Text>
        </View>
        <Text style={[styles.price, !available && styles.muted]}>{q ? linesPriceText(q.price) : '—'}</Text>
      </Pressable>
    );
  };

  // Best line: picks grouped under the book with their best price.
  const bestGroups = useMemo(() => {
    const m = new Map<string, BetAllPick[]>();
    for (const p of picks) {
      const b = p.quotes[0]!.bookmaker;
      m.set(b, [...(m.get(b) ?? []), p]);
    }
    return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
  }, [picks]);

  // Mid-send, a stray tap must not throw away a book that is waiting for
  // its Placed answer (UX review): the backdrop does nothing, and the X asks.
  const pendingAnswer = phase === 'send' && !allDone && steps.some((s) => status[s.bookmaker] === 'opened');
  const requestClose = () => {
    if (pendingAnswer) setConfirmStop(true);
    else onClose();
  };
  const allSelected = picks.length > 0 && picks.every((p) => selected.has(p.key));

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
                {phase === 'choose' ? `Bet all · ${sport}` : allDone ? 'All done' : `Bet all · ${doneCount} of ${steps.length} done`}
              </Text>
              <Text style={styles.subtitle}>{BET_ALL_LIVE_NOTE}</Text>
            </View>
            <Pressable onPress={requestClose} hitSlop={12} accessibilityRole="button" accessibilityLabel="Close Bet all">
              <Ionicons name="close" size={24} color={colors.textSecondary} />
            </Pressable>
          </View>

          {confirmStop ? (
            <View style={styles.ask}>
              <Text style={styles.askTitle} accessibilityRole="header">Stop Bet all?</Text>
              <Text style={styles.askBody}>Bets you placed and haven’t marked won’t be tracked.</Text>
              <View style={styles.askButtons}>
                <Pressable onPress={() => setConfirmStop(false)} accessibilityRole="button" accessibilityLabel="Keep going" style={[styles.askBtn, styles.askPrimary]}>
                  <Text style={styles.askPrimaryText}>Keep going</Text>
                </Pressable>
                <Pressable onPress={onClose} accessibilityRole="button" accessibilityLabel="Stop Bet all" style={styles.askBtn}>
                  <Text style={styles.askBtnText}>Stop</Text>
                </Pressable>
              </View>
            </View>
          ) : null}

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
                  onPress={() => setSelected(allSelected ? new Set() : new Set(picks.map((p) => p.key)))}
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
                        accessibilityLabel={`${c.name}, has ${c.covered} of ${selected.size}, ${c.atBest} at the best price`}
                        style={[styles.chip, on && styles.chipOn]}
                      >
                        <Text style={[styles.chipBook, on && styles.chipBookOn]}>{c.short}</Text>
                        <Text style={styles.chipMeta}>{`${c.covered} of ${selected.size}`}</Text>
                      </Pressable>
                    );
                  })}
                </ScrollView>
              ) : null}

              <ScrollView style={styles.list} bounces={false}>
                {mode === 'best' ? (
                  bestGroups.map(([b, ps]) => (
                    <View key={b} style={styles.group}>
                      <Text style={styles.groupTitle}>{`${bookName(b)} · best line`}</Text>
                      <View style={styles.card}>{ps.map(pickRow)}</View>
                    </View>
                  ))
                ) : (
                  <View style={styles.group}>
                    <View style={styles.card}>{picks.map(pickRow)}</View>
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
                        <View key={s.key} style={[styles.row, i > 0 && styles.rowDivider]} accessible accessibilityLabel={`${trueMinus(s.label)}, not included, ${BET_ALL_SKIP_TEXT[s.reason]}`}>
                          <View style={styles.rowBody}>
                            <Text style={[styles.rowTitle, styles.muted]} numberOfLines={2}>{trueMinus(s.label)}</Text>
                            <Text style={styles.rowSub}>{BET_ALL_SKIP_TEXT[s.reason]}</Text>
                          </View>
                        </View>
                      ))}
                    </View>
                  </View>
                ) : null}
              </ScrollView>

              <View style={styles.footer}>
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
              {askFor ? (
                <View style={styles.ask} accessibilityLiveRegion="polite">
                  <Text style={styles.askTitle}>{`Back from ${bookName(askFor)}`}</Text>
                  <Text style={styles.askBody}>
                    {(() => {
                      const n = steps.find((s) => s.bookmaker === askFor)?.legs.length ?? 0;
                      return `Did you place ${n === 1 ? 'this bet' : `these ${n} bets`} as ${n === 1 ? 'a single' : 'singles'}?`;
                    })()}
                  </Text>
                  <View style={styles.askButtons}>
                    <Pressable onPress={() => answer(askFor, 'placed')} accessibilityRole="button" accessibilityLabel="Placed, track these bets" style={[styles.askBtn, styles.askPrimary]}>
                      <Text style={styles.askPrimaryText}>Placed · track</Text>
                    </Pressable>
                    <Pressable onPress={() => answer(askFor, 'todo')} accessibilityRole="button" accessibilityLabel="Not yet" style={styles.askBtn}>
                      <Text style={styles.askBtnText}>Not yet</Text>
                    </Pressable>
                    <Pressable onPress={() => answer(askFor, 'skipped')} accessibilityRole="button" accessibilityLabel="Skip this sportsbook" style={styles.askBtn}>
                      <Text style={styles.askBtnText}>Skip</Text>
                    </Pressable>
                  </View>
                </View>
              ) : null}
              <ScrollView style={styles.list} bounces={false}>
                {steps.map((step) => {
                  const st = status[step.bookmaker] ?? 'todo';
                  const isNext = step === nextStep;
                  return (
                    <View key={step.bookmaker} style={[styles.step, isNext && styles.stepNext]}>
                      <View style={styles.stepTop}>
                        <Text style={styles.stepTitle}>{`${step.name} · ${step.legs.length} ${step.legs.length === 1 ? 'pick' : 'picks'}`}</Text>
                        <Text style={[styles.stepStatus, st === 'placed' && styles.stepPlaced]}>
                          {st === 'placed' ? 'Placed' : st === 'skipped' ? 'Skipped' : st === 'opened' ? 'Opened' : isNext ? 'Next' : 'Waiting'}
                        </Text>
                      </View>
                      {st === 'placed' || st === 'skipped' ? null : (
                        <>
                          {step.legs.map((l) => (
                            <View key={l.key} style={styles.leg}>
                              <Text style={styles.legLabel} numberOfLines={2}>{`${trueMinus(l.label)} ${linesPriceText(l.price)}`}</Text>
                              <Text style={styles.legStake}>{stakeText(l.stake.risk, l.stake.win)}</Text>
                            </View>
                          ))}
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
                          {st === 'opened' ? (
                            <Pressable onPress={() => setAskFor(step.bookmaker)} accessibilityRole="button" accessibilityLabel={`Mark ${step.name} bets as placed`} style={styles.markPlaced}>
                              <Text style={styles.link}>Mark as placed</Text>
                            </Pressable>
                          ) : null}
                        </>
                      )}
                    </View>
                  );
                })}
                <Text style={styles.note}>{BET_ALL_SINGLES_NOTE}</Text>
              </ScrollView>
              {allDone ? (
                <View style={styles.footer}>
                  <Text style={styles.summary}>
                    {placedLegs === 0 ? 'Nothing was tracked.' : `${placedLegs} ${placedLegs === 1 ? 'bet' : 'bets'} added to tracked bets.`}
                  </Text>
                  <PrimaryButton label="Done" onPress={onClose} />
                </View>
              ) : null}
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
  ask: {
    ...cardDense,
    marginBottom: spacing.md,
    gap: spacing.xs,
    borderWidth: 1.5,
    borderColor: colors.tint,
  },
  askTitle: { fontSize: font.size.body, fontWeight: font.weight.bold, color: colors.textPrimary },
  askBody: { fontSize: font.size.footnote, color: colors.textSecondary },
  askButtons: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.xs },
  askBtn: {
    flex: 1,
    minHeight: 44,
    borderRadius: radii.sm,
    backgroundColor: colors.tintSoft,
    alignItems: 'center',
    justifyContent: 'center',
  },
  askPrimary: { backgroundColor: colors.tint },
  askBtnText: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textPrimary },
  askPrimaryText: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textInverse },
  step: { ...cardDense, marginBottom: spacing.sm, gap: spacing.sm },
  stepNext: { borderWidth: 1.5, borderColor: colors.tint },
  stepTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: spacing.sm },
  stepTitle: { flex: 1, fontSize: font.size.body, fontWeight: font.weight.bold, color: colors.textPrimary },
  stepStatus: { fontSize: font.size.footnote, fontWeight: font.weight.semibold, color: colors.textSecondary },
  stepPlaced: { color: colors.betInk },
  leg: { flexDirection: 'row', justifyContent: 'space-between', gap: spacing.sm },
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
