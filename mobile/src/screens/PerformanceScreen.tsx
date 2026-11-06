import React, { useEffect, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Modal } from '@/components/TrackedModal';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { SettingsButton } from '@/components/SettingsButton';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useNavigation } from '@react-navigation/native';
import { useSportsbookSync } from '@/hooks/useSportsbookSync';
import { useManualBets, type ManualBet, type ManualBetResult } from '@/hooks/useManualBets';
import { useTrackedBetResults, type StakeMode } from '@/hooks/useTrackedBetResults';
import { ManualBetModal } from '@/components/ManualBetModal';
import { FLAT_UNIT, FLAT_UNIT_TONE_SCALE, formatAmerican, formatFlatStake, formatFlatUnits, labelWithoutStake } from '@/lib/format';
import { unitsSpeech } from '@/lib/a11y';
import type { SyncedBet } from '@/lib/sharpsports';
import type { TrackedBetRow, TrackedBetSummary } from '@/lib/trackedPerformance';
import { postedTrackedStake } from '@/lib/trackedStake';
import { colors, font, pnlColor, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';
import { decisionOdds } from '@/lib/decisionPrice';
import { bookLabelShort, storedQuoteBook } from '@/lib/markets';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { PickRowTitle } from '@/components/PickRowTitle';

type Nav = NativeStackNavigationProp<RootStackParamList>;

export function PerformanceScreen() {
  const navigation = useNavigation<Nav>();
  const { accounts, bets, summary, linked, needsReconnect, loading, refresh } =
    useSportsbookSync();
  const manual = useManualBets();
  const tracked = useTrackedBetResults();
  const [showAdd, setShowAdd] = useState(false);
  const [stakeEdit, setStakeEdit] = useState<TrackedBetRow | null>(null);

  const settleManual = (bet: ManualBet) => {
    if (bet.result !== 'open') {
      Alert.alert('Remove this bet?', bet.description, [
        { text: 'Cancel', style: 'cancel' },
        { text: 'Remove', style: 'destructive', onPress: () => manual.remove(bet.id) },
      ]);
      return;
    }
    Alert.alert('Settle bet', bet.description, [
      { text: 'Won', onPress: () => manual.settle(bet.id, 'won') },
      { text: 'Lost', onPress: () => manual.settle(bet.id, 'lost') },
      { text: 'Push', onPress: () => manual.settle(bet.id, 'push') },
      { text: 'Cancel', style: 'cancel' },
    ]);
  };

  const manualCard = (
    <ManualBetsCard bets={manual.bets} onAdd={() => setShowAdd(true)} onRowPress={settleManual} />
  );
  const trackedCard = (
    <TrackedBetsCard
      rows={tracked.rows}
      summary={tracked.summary}
      trackedCount={tracked.trackedCount}
      stakeMode={tracked.stakeMode}
      onStakeModeChange={tracked.setStakeMode}
      onEditStake={setStakeEdit}
      onRowPress={(row) => {
        // Synthetic live rows (model moved off the side; game over) carry a
        // negative pick_id and have no pick row to open.
        if (row.pick.pick_id > 0) {
          navigation.navigate('PickDetail', { pickId: row.pick.pick_id });
        }
      }}
      onRowLongPress={(row) => {
        Alert.alert('Stop tracking?', labelWithoutStake(row.pick.pick_label), [
          { text: 'Cancel', style: 'cancel' },
          {
            text: 'Untrack',
            style: 'destructive',
            onPress: () => tracked.untrackPick(row.pick),
          },
        ]);
      }}
    />
  );
  const addModal = (
    <>
      <ManualBetModal visible={showAdd} onClose={() => setShowAdd(false)} onAdd={manual.add} />
      <StakeEditModal
        row={stakeEdit}
        onClose={() => setStakeEdit(null)}
        onSave={(amount) => {
          if (stakeEdit) tracked.setCustomStake(stakeEdit.pick.pick_id, amount);
          setStakeEdit(null);
        }}
      />
    </>
  );

  // The real-world state: sportsbook sync isn't live yet, so self-tracking IS
  // the Performance tab. Sync is a small "coming soon" note at the top, not a
  // CTA — the connect flow has no live keys behind it and would dead-end.
  if (!linked && !loading) {
    return (
      <SafeAreaView style={styles.container} edges={['top']}>
        <ScrollView contentContainerStyle={styles.list}>
          <View style={styles.header}>
            <View style={styles.titleRow}>
              <Text style={styles.title}>Performance</Text>
              <SettingsButton />
            </View>
            <Text style={styles.subtitle}>Your bets, tracked by you</Text>
          </View>

          <View style={styles.soon}>
            <Ionicons name="link-outline" size={15} color={colors.textTertiary} />
            <View style={styles.soonText}>
              <Text style={styles.soonTitle}>Sportsbook sync — coming soon</Text>
              <Text style={styles.soonSub}>
                Automatic bet import from DraftKings, FanDuel and more. Until then, log your bets
                below.
              </Text>
            </View>
          </View>

          <Pressable
            onPress={() => navigation.navigate('TrackRecord')}
            accessibilityRole="button"
            accessibilityLabel="See the model’s verified track record"
            style={({ pressed }) => [styles.trackLink, pressed && styles.btnPressed]}
          >
            <Ionicons name="shield-checkmark-outline" size={16} color={colors.tint} />
            <Text style={styles.trackLinkText}>See the model’s verified track record</Text>
            <Ionicons name="chevron-forward" size={15} color={colors.tint} />
          </Pressable>

          {manualCard}
          {trackedCard}
          <BetslipBarSpacer />
        </ScrollView>
        {addModal}
      </SafeAreaView>
    );
  }

  const bookLabel = formatBookList(
    Array.from(new Set(accounts.map((a) => a.book).filter(Boolean) as string[])),
  );
  // Ink, not the bright bet/avoid hues (2.22 / 3.55:1 as text; audit H2).
  // Sync is not live (no keys; the screen above is the real state). Until
  // it is, synced amounts read at the tab's one scale, 100 = 1u, like the
  // logged and tracked bets. Which unit a synced bet should use once sync
  // ships (the member's own, from Settings?) is an open decision.
  const profitColor = pnlColor(summary.net_profit, 2, FLAT_UNIT_TONE_SCALE);

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={() => {
              void refresh(true);
              void tracked.refresh();
            }}
          />
        }
      >
        <View style={styles.header}>
          <View style={styles.titleRow}>
            <Text style={styles.title}>Performance</Text>
            <SettingsButton />
          </View>
          <Text style={styles.subtitle}>{bookLabel || 'Sportsbook'} · pull to refresh</Text>
        </View>

        <Pressable
          onPress={() => navigation.navigate('TrackRecord')}
          accessibilityRole="button"
          accessibilityLabel="See the model’s verified track record"
          style={({ pressed }) => [styles.trackLink, pressed && styles.btnPressed]}
        >
          <Ionicons name="shield-checkmark-outline" size={16} color={colors.tint} />
          <Text style={styles.trackLinkText}>See the model’s verified track record</Text>
          <Ionicons name="chevron-forward" size={15} color={colors.tint} />
        </Pressable>

        {needsReconnect ? (
          <Pressable
            onPress={() => navigation.navigate('ConnectSportsbook')}
            accessibilityRole="button"
            accessibilityLabel="A linked account needs reconnecting. Tap to fix."
            style={({ pressed }) => [styles.reconnect, pressed && styles.btnPressed]}
          >
            <Ionicons name="alert-circle-outline" size={16} color={colors.medInk} />
            <Text style={styles.reconnectText}>
              A linked account needs reconnecting — tap to fix.
            </Text>
          </Pressable>
        ) : null}

        <View style={styles.summaryCard}>
          <View
            style={styles.summaryMain}
            accessible
            accessibilityLabel={`Net units, ${unitsSpeech(formatFlatUnits(summary.net_profit))}`}
          >
            <Text style={styles.summaryLabel}>Net units</Text>
            <Text style={[styles.summaryProfit, { color: profitColor }]}>
              {formatFlatUnits(summary.net_profit)}
            </Text>
          </View>
          <View style={styles.summaryStatsRow}>
            <SummaryStat
              label="Win rate"
              value={summary.win_rate != null ? `${Math.round(summary.win_rate * 100)}%` : '—'}
            />
            <SummaryStat label="Settled" value={String(summary.settled_bets)} />
            <SummaryStat label="Open" value={String(summary.open_bets)} />
          </View>
        </View>

        {bets.length === 0 ? (
          <Text style={styles.empty}>
            No synced bets yet. Place a bet on a linked book — it’ll appear here after the next
            sync.
          </Text>
        ) : (
          bets.slice(0, 100).map((b) => <BetRow key={b.bet_id} bet={b} />)
        )}

        {loading && bets.length === 0 ? <ActivityIndicator style={styles.loading} /> : null}

        {trackedCard}
        {manualCard}

        <Pressable
          onPress={() => navigation.navigate('ConnectSportsbook')}
          accessibilityRole="button"
          accessibilityLabel="Manage connections"
          style={({ pressed }) => [styles.secondaryBtn, pressed && styles.btnPressed]}
        >
          <Text style={styles.secondaryBtnText}>Manage connections</Text>
        </Pressable>
        <BetslipBarSpacer />
      </ScrollView>
      {addModal}
    </SafeAreaView>
  );
}

function ManualBetsCard({
  bets,
  onAdd,
  onRowPress,
}: {
  bets: ManualBet[];
  onAdd: () => void;
  onRowPress: (b: ManualBet) => void;
}) {
  const settled = bets.filter((b) => b.result !== 'open');
  const net = settled.reduce((s, b) => s + Number(b.profit ?? 0), 0);
  const wins = settled.filter((b) => b.result === 'won').length;
  const losses = settled.filter((b) => b.result === 'lost').length;

  return (
    <View style={styles.manualCard}>
      <View style={styles.manualHeader}>
        <Text style={styles.manualTitle}>Your bets</Text>
        {bets.length > 0 ? (
          <Pressable
            onPress={onAdd}
            // ~18pt text link in the card header: 13 + 18 + 13 = 44pt.
            hitSlop={{ top: 13, bottom: 13, left: 8, right: 8 }}
            accessibilityRole="button"
            accessibilityLabel="Add a bet"
            style={styles.addManualBtn}
          >
            <Ionicons name="add" size={16} color={colors.tint} />
            <Text style={styles.addManualText}>Add a bet</Text>
          </Pressable>
        ) : null}
      </View>

      {bets.length === 0 ? (
        <>
          <Text style={styles.manualEmpty}>
            Record the bets you place — any book, any sport — and your record builds here. Stored on
            this device.
          </Text>
          <Pressable
            onPress={onAdd}
            accessibilityRole="button"
            accessibilityLabel="Add a bet"
            style={({ pressed }) => [styles.primaryBtn, pressed && styles.btnPressed]}
          >
            <Text style={styles.primaryBtnText}>Add a bet</Text>
          </Pressable>
        </>
      ) : (
        <>
          <Text
            style={styles.manualSummary}
            accessibilityLabel={unitsSpeech(
              `${formatFlatUnits(net)}, ${wins} won, ${losses} lost` +
                (settled.length < bets.length ? `, ${bets.length - settled.length} open` : ''),
            )}
          >
            {formatFlatUnits(net)} · {wins}–{losses}
            {settled.length < bets.length ? ` · ${bets.length - settled.length} open` : ''}
          </Text>
          {bets.map((b) => (
            <Pressable
              key={b.id}
              onPress={() => onRowPress(b)}
              accessibilityRole="button"
              accessibilityLabel={[
                b.description,
                b.book,
                unitsSpeech(`${formatFlatStake(b.stake)} risk`),
                b.odds_american != null ? formatAmerican(b.odds_american) : null,
                b.result === 'open' ? 'Open' : unitsSpeech(formatFlatUnits(b.profit)),
              ]
                .filter(Boolean)
                .join(', ')}
              accessibilityHint="Settle or remove this bet"
              style={styles.manualRow}
            >
              <View style={{ flex: 1 }}>
                <Text style={styles.manualDesc} numberOfLines={1}>
                  {b.description}
                </Text>
                <Text style={styles.manualSub} numberOfLines={1}>
                  {[
                    b.book,
                    `${formatFlatStake(b.stake)} risk`,
                    b.odds_american != null ? formatAmerican(b.odds_american) : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </Text>
              </View>
              <Text style={[styles.manualRight, { color: manualResultColor(b.result, b.profit) }]}>
                {b.result === 'open' ? 'Open' : formatFlatUnits(b.profit)}
              </Text>
            </Pressable>
          ))}
          <Text style={styles.manualHint}>Tap a bet to settle it or remove it.</Text>
        </>
      )}
    </View>
  );
}

function manualResultColor(result: ManualBetResult, profit: number): string {
  if (result === 'open') return colors.textSecondary;
  return pnlColor(profit, 2, FLAT_UNIT_TONE_SCALE);
}

const TRACKED_ROW_CAP = 40;

// As posted is the Record tab's stake (lib/trackedStake), so a tracked pick
// shows the Record's units. My stakes is the member's own override.
const STAKE_MODES: { value: StakeMode; label: string }[] = [
  { value: 'posted', label: 'As posted' },
  { value: 'custom', label: 'My stakes' },
];

function stakeCaption(mode: StakeMode): string {
  if (mode === 'custom') return 'Tap a stake to set your own, in units. Bets you leave alone stay as posted';
  return 'Each pick to win 1u at its posted price, risk capped at 3u, as on the Record tab';
}

/** "2u your stake" when the member set it, "1.5u as posted" when they have not. */
function stakeChipText(row: TrackedBetRow): string {
  return `${formatFlatStake(row.stake)} ${row.customStake ? 'your stake' : 'as posted'}`;
}

function TrackedBetsCard({
  rows,
  summary,
  trackedCount,
  stakeMode,
  onStakeModeChange,
  onEditStake,
  onRowPress,
  onRowLongPress,
}: {
  rows: TrackedBetRow[];
  summary: TrackedBetSummary;
  trackedCount: number;
  stakeMode: StakeMode;
  onStakeModeChange: (mode: StakeMode) => void;
  onEditStake: (row: TrackedBetRow) => void;
  onRowPress: (row: TrackedBetRow) => void;
  onRowLongPress: (row: TrackedBetRow) => void;
}) {
  return (
    <View style={styles.manualCard}>
      <View style={styles.manualHeader}>
        <Text style={styles.manualTitle}>Tracked picks</Text>
        {trackedCount > 0 ? (
          <Text style={styles.trackedCount}>{trackedCount}</Text>
        ) : null}
      </View>

      {rows.length === 0 ? (
        <Text style={styles.manualEmpty}>
          Tap the bell on any pick to track it. Once games settle, your tracked bets score here
          automatically.
        </Text>
      ) : (
        <>
          <Text
            style={styles.manualSummary}
            accessibilityLabel={unitsSpeech(
              (summary.settled > 0
                ? `${formatFlatUnits(summary.net)}, ${summary.wins} won, ${summary.losses} lost` +
                  (summary.pushes > 0 ? `, ${summary.pushes} pushed` : '')
                : 'Nothing settled yet') + (summary.open > 0 ? `, ${summary.open} open` : ''),
            )}
          >
            {summary.settled > 0
              ? `${formatFlatUnits(summary.net)} · ${summary.wins}–${summary.losses}` +
                (summary.pushes > 0 ? `–${summary.pushes}` : '')
              : 'Nothing settled yet'}
            {summary.open > 0 ? ` · ${summary.open} open` : ''}
          </Text>
          <View style={styles.stakePills} accessibilityRole="radiogroup">
            {STAKE_MODES.map((m) => {
              const active = stakeMode === m.value;
              return (
                <Pressable
                  key={m.value}
                  onPress={() => onStakeModeChange(m.value)}
                  // ~28pt pill: 8 + 28 + 8 = 44pt; a stake basis is one-of-two,
                  // so radio + checked, not a bare button (audit M10).
                  hitSlop={{ top: 8, bottom: 8, left: 2, right: 2 }}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active, selected: active }}
                  accessibilityLabel={`Stake basis: ${m.label}`}
                  style={[styles.stakePill, active && styles.stakePillActive]}
                >
                  <Text style={[styles.stakePillText, active && styles.stakePillTextActive]}>
                    {m.label}
                  </Text>
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.trackedBasis}>{stakeCaption(stakeMode)}</Text>
          {rows.slice(0, TRACKED_ROW_CAP).map((row) => (
            <Pressable
              key={row.pick.pick_id}
              onPress={() => onRowPress(row)}
              onLongPress={() => onRowLongPress(row)}
              accessibilityRole="button"
              accessibilityLabel={[
                labelWithoutStake(row.pick.pick_label),
                formatGameDate(row.pick.game_date),
                decisionOdds(row.pick) != null
                  ? `${bookLabelShort(storedQuoteBook(row.pick))} ${formatAmerican(decisionOdds(row.pick))}`
                  : null,
                unitsSpeech(stakeMode === 'custom' ? stakeChipText(row) : `${formatFlatStake(row.stake)} risk`),
                unitsSpeech(trackedResultLabel(row)),
              ]
                .filter(Boolean)
                .join(', ')}
              accessibilityHint={row.pick.pick_id > 0 ? 'Opens the pick' : undefined}
              // The row groups its children for VoiceOver, so the nested stake
              // chip and the long-press Untrack are offered as actions too —
              // long-press was the only route to Untrack (audit M10; the
              // visible Untrack + Undo toast is PR 5).
              accessibilityActions={[
                { name: 'untrack', label: 'Untrack' },
                ...(stakeMode === 'custom' ? [{ name: 'editStake', label: 'Edit stake' }] : []),
              ]}
              onAccessibilityAction={(e) => {
                if (e.nativeEvent.actionName === 'untrack') onRowLongPress(row);
                else if (e.nativeEvent.actionName === 'editStake') onEditStake(row);
              }}
              style={styles.manualRow}
            >
              <View style={{ flex: 1 }}>
                <PickRowTitle pick={row.pick} titleStyle={styles.manualDesc} matchupStyle={styles.manualSub} />
                <Text style={styles.manualSub} numberOfLines={1}>
                  {[
                    formatGameDate(row.pick.game_date),
                    decisionOdds(row.pick) != null
                      ? `${bookLabelShort(storedQuoteBook(row.pick))} ${formatAmerican(decisionOdds(row.pick))}`
                      : null,
                    // As posted, risk runs 0.25u to 3u by price, so the row says
                    // what it laid, as the logged bets above do (UX review).
                    stakeMode === 'posted' ? `${formatFlatStake(row.stake)} risk` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </Text>
                {stakeMode === 'custom' ? (
                  <Pressable
                    onPress={() => onEditStake(row)}
                    // ~20pt chip: 12 + 20 + 12 = 44pt. Slop, not size, so the
                    // row doesn't grow (audit M10: was an 11pt pencil, slop 6).
                    hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
                    accessibilityRole="button"
                    accessibilityLabel={`Edit stake, ${unitsSpeech(stakeChipText(row))}`}
                    style={styles.stakeChip}
                  >
                    <Ionicons name="pencil-outline" size={11} color={colors.tint} />
                    <Text style={styles.stakeChipText}>{stakeChipText(row)}</Text>
                  </Pressable>
                ) : null}
              </View>
              <Text style={[styles.manualRight, { color: trackedResultColor(row) }]}>
                {trackedResultLabel(row)}
              </Text>
            </Pressable>
          ))}
          {rows.length > TRACKED_ROW_CAP ? (
            <Text style={styles.manualHint}>Showing the {TRACKED_ROW_CAP} most recent.</Text>
          ) : null}
          <Text style={styles.manualHint}>Tap a bet for details · hold to untrack.</Text>
        </>
      )}
    </View>
  );
}

function trackedResultLabel(row: TrackedBetRow): string {
  switch (row.status) {
    case 'open':
      return 'Open';
    case 'no_action':
      return 'No action';
    case 'not_graded':
      return 'Not graded';
    case 'push':
      return 'Push';
    default:
      return formatFlatUnits(row.profit);
  }
}

function trackedResultColor(row: TrackedBetRow): string {
  if (row.status === 'won') return colors.betInk;
  if (row.status === 'lost') return colors.avoidInk;
  return colors.textSecondary;
}

/** 'YYYY-MM-DD' → 'M/D' without Date parsing (a bare ISO date parses as UTC
 *  midnight and renders the previous day in US timezones). */
function formatGameDate(gameDate: string): string | null {
  const parts = gameDate.split('-');
  if (parts.length !== 3) return null;
  const month = Number(parts[1]);
  const day = Number(parts[2]);
  if (!Number.isFinite(month) || !Number.isFinite(day)) return null;
  return `${month}/${day}`;
}

function StakeEditModal({
  row,
  onClose,
  onSave,
}: {
  row: TrackedBetRow | null;
  onClose: () => void;
  onSave: (amount: number | null) => void;
}) {
  const [amount, setAmount] = useState('');
  useEffect(() => {
    // Stored at the 100-is-1u scale (lib/format FLAT_UNIT); edited in units.
    // A posted row opens empty, so the placeholder shows the posted stake and
    // Save without typing keeps it posted (it used to save the rounded figure
    // as the member's own). A stake the member set opens filled in.
    if (row) {
      setAmount(row.customStake ? String(Math.round((row.stake / FLAT_UNIT) * 100) / 100) : '');
    }
  }, [row]);

  const save = () => {
    const n = parseFloat(amount);
    // Empty / invalid input puts the bet back on the posted stake.
    onSave(Number.isFinite(n) && n >= 0 ? n * FLAT_UNIT : null);
  };

  return (
    <Modal trackName="PerformanceScreen" visible={row != null} transparent animationType="fade" onRequestClose={onClose}>
      <View style={styles.stakeModalBackdrop}>
        {/* Tap outside the card to dismiss (audit M10). A sibling behind the
            card, not its parent, so VoiceOver still reaches the card's input
            and buttons one by one. */}
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel="Close stake editor"
        />
        <View style={styles.stakeModalCard} accessibilityViewIsModal>
          <Text style={styles.stakeModalTitle}>Your stake for this bet, in units</Text>
          <Text style={styles.stakeModalLabel} numberOfLines={2}>
            {labelWithoutStake(row?.pick.pick_label)}
          </Text>
          <Text style={styles.stakeModalHint}>
            What you risk on this bet, settled at its posted price. Leave it empty to keep the
            posted stake.
          </Text>
          <TextInput
            accessibilityLabel="Stake in units"
            style={styles.stakeModalInput}
            value={amount}
            onChangeText={(t) => setAmount(t.replace(/[^0-9.]/g, ''))}
            keyboardType="decimal-pad"
            clearButtonMode="while-editing"
            autoFocus
            placeholder={row ? `${formatFlatStake(postedTrackedStake(row.pick).risk)} as posted` : 'As posted'}
            placeholderTextColor={colors.textTertiary}
          />
          <View style={styles.stakeModalActions}>
            <Pressable
              onPress={() => onSave(null)}
              hitSlop={12}
              accessibilityRole="button"
              accessibilityLabel="Use the posted stake"
            >
              <Text style={styles.stakeModalReset}>Use posted stake</Text>
            </Pressable>
            <View style={styles.stakeModalRight}>
              <Pressable onPress={onClose} hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }} accessibilityRole="button" accessibilityLabel="Cancel">
                <Text style={styles.stakeModalCancel}>Cancel</Text>
              </Pressable>
              <Pressable onPress={save} hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }} accessibilityRole="button" accessibilityLabel="Save stake">
                <Text style={styles.stakeModalSave}>Save</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

function SummaryStat({ label, value }: { label: string; value: string }) {
  return (
    <View style={styles.summaryStat}>
      <Text style={styles.summaryStatValue}>{value}</Text>
      <Text style={styles.summaryStatLabel}>{label}</Text>
    </View>
  );
}

function BetRow({ bet }: { bet: SyncedBet }) {
  const settled = bet.settled;
  const profit = Number(bet.profit ?? 0);
  const resultColor = !settled ? colors.textSecondary : pnlColor(profit, 2, FLAT_UNIT_TONE_SCALE);
  const right = settled
    ? formatFlatUnits(profit)
    : bet.stake != null
      ? `${formatFlatStake(bet.stake)} risked`
      : 'Open';

  return (
    <View style={styles.betRow}>
      <View style={{ flex: 1 }}>
        <Text style={styles.betTitle} numberOfLines={1}>
          {bet.book ?? 'Bet'}
          {bet.type ? ` · ${bet.type}` : ''}
        </Text>
        <Text style={styles.betSub} numberOfLines={1}>
          {[
            bet.odds_american != null ? formatAmerican(bet.odds_american) : null,
            (bet.status ?? '').toString() || null,
            formatDate(bet.placed_at),
          ]
            .filter(Boolean)
            .join(' · ')}
        </Text>
      </View>
      <Text style={[styles.betRight, { color: resultColor }]} accessibilityLabel={unitsSpeech(right)}>
        {right}
      </Text>
    </View>
  );
}

function formatDate(iso: string | null): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return null;
  }
}

function formatBookList(names: string[]): string {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} & ${names[1]}`;
  return `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}`;
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.bg,
  },
  list: {
    paddingBottom: spacing.xl,
  },
  header: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.md,
  },
  titleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  title: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 4,
  },
  summaryCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  summaryMain: {
    alignItems: 'center',
    marginBottom: spacing.md,
  },
  summaryLabel: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginBottom: 2,
  },
  summaryProfit: {
    fontSize: font.size.largeTitle,
    fontWeight: font.weight.bold,
  },
  summaryStatsRow: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    paddingTop: spacing.md,
  },
  summaryStat: {
    alignItems: 'center',
  },
  summaryStatValue: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  summaryStatLabel: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 2,
  },
  soon: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.separatorOpaque,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  soonText: { flex: 1 },
  soonTitle: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  soonSub: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    lineHeight: 16,
    marginTop: 1,
  },
  trackLink: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  trackLinkText: {
    flex: 1,
    fontSize: font.size.callout,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  reconnect: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: colors.medSoft,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.md,
  },
  // medInk 4.99:1 on medSoft; `med` was 1.97:1. The icon keeps amber (M24).
  reconnectText: {
    flex: 1,
    fontSize: font.size.footnote,
    color: colors.medInk,
    fontWeight: font.weight.medium,
  },
  betRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginHorizontal: spacing.lg,
    marginBottom: spacing.sm,
  },
  betTitle: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    textTransform: 'capitalize',
  },
  betSub: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginTop: 2,
    textTransform: 'capitalize',
  },
  betRight: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    marginLeft: spacing.md,
  },
  empty: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
    paddingHorizontal: spacing.xl,
    marginVertical: spacing.lg,
    lineHeight: 19,
  },
  manualCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
  },
  manualHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.sm,
  },
  manualTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  addManualBtn: { flexDirection: 'row', alignItems: 'center', gap: 2 },
  addManualText: { fontSize: font.size.footnote, color: colors.tint, fontWeight: font.weight.semibold },
  manualEmpty: { fontSize: font.size.footnote, color: colors.textSecondary, lineHeight: 18 },
  manualSummary: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
  },
  manualRow: {
    // Declared tap floor (verify_a11y); the two-line row is already ~56pt, so this
    // changes nothing on screen.
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
  },
  manualDesc: { fontSize: font.size.body, color: colors.textPrimary, fontWeight: font.weight.medium },
  manualSub: { fontSize: font.size.caption, color: colors.textTertiary, marginTop: 2 },
  manualRight: { fontSize: font.size.callout, fontWeight: font.weight.semibold, marginLeft: spacing.md },
  manualHint: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
    fontStyle: 'italic',
  },
  trackedCount: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    fontWeight: font.weight.semibold,
  },
  trackedBasis: {
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginBottom: spacing.sm,
  },
  stakePills: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    backgroundColor: colors.bg,
    borderRadius: radii.pill,
    padding: 3,
    marginBottom: spacing.sm,
  },
  stakePill: {
    paddingHorizontal: spacing.md,
    paddingVertical: 5,
    borderRadius: radii.pill,
  },
  stakePillActive: {
    backgroundColor: colors.tint,
  },
  stakePillText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.medium,
  },
  stakePillTextActive: {
    color: colors.textInverse,
    fontWeight: font.weight.semibold,
  },
  stakeChip: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 4,
    marginTop: 4,
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: radii.pill,
    borderWidth: 1,
    borderColor: colors.separator,
    backgroundColor: colors.bg,
  },
  stakeChipText: {
    fontSize: font.size.caption,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  stakeModalBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.xl,
  },
  stakeModalCard: {
    alignSelf: 'stretch',
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.lg,
  },
  stakeModalTitle: {
    fontSize: font.size.headline,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  stakeModalLabel: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
    marginBottom: spacing.sm,
  },
  stakeModalHint: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
    marginBottom: spacing.md,
  },
  stakeModalInput: {
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    backgroundColor: colors.bg,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    textAlign: 'center',
  },
  stakeModalActions: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  stakeModalRight: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.lg,
  },
  stakeModalReset: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  stakeModalCancel: {
    fontSize: font.size.body,
    color: colors.textSecondary,
  },
  stakeModalSave: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.tint,
  },
  primaryBtn: {
    backgroundColor: colors.tint,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    alignSelf: 'stretch',
    alignItems: 'center',
  },
  primaryBtnText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  secondaryBtn: {
    backgroundColor: colors.bgCard,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: radii.md,
    marginHorizontal: spacing.lg,
    marginTop: spacing.md,
    alignItems: 'center',
  },
  secondaryBtnText: {
    color: colors.tint,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
  btnPressed: {
    opacity: 0.7,
  },
  loading: {
    marginTop: spacing.lg,
  },
});
