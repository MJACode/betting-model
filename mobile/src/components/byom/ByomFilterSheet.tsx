import React, { useEffect, useRef, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ByomBetCount } from '@/components/byom/ByomBetCount';
import { ByomCheckChip } from '@/components/byom/ByomCheckChip';
import type { ByomSheetTab } from '@/components/byom/ByomPropSideFields';
import { searchByomPlayerNames } from '@/lib/byom';
import {
  betTypeLabel,
  isYesOnlyProp,
  type ByomMarket,
  type ByomPropSide,
  type ByomRecord,
  type ByomSport,
} from '@/lib/byomRecord';
import {
  KICK_SLOTS,
  PRICE_CHOICES,
  SPREAD_SCALE,
  canMoveBand,
  canMovePrice,
  daysFor,
  formatAmericanBand,
  formatLineNumber,
  formatSpread,
  lineScale,
  lineStepNote,
  monthsFor,
  moveBand,
  movePrice,
  openBand,
  openPriceBand,
  resetSheetFilters,
  shownKickSlots,
  toggleMember,
  totalScale,
  withKickSlots,
  type ByomBand,
  type ByomPriceBand,
  type ByomPropFilterState,
  type LineScale,
} from '@/lib/byomPropFilters';
import { filterTeams, teamsForSport } from '@/lib/byomTeams';
import { colors, font, radii, spacing } from '@/lib/theme';

export function ByomFilterSheet({
  tab,
  sport,
  market,
  propSide,
  side,
  primetime,
  propFilters,
  record,
  loading,
  error,
  showsUnits,
  blocked = null,
  onRetry,
  onClose,
  onTab,
  onSide,
  onPrimetime,
  onPropFilters,
}: {
  tab: ByomSheetTab | null;
  sport: ByomSport;
  market: ByomMarket;
  propSide: ByomPropSide | null;
  side: 'home' | 'away' | 'over' | 'under' | null;
  primetime: boolean | null;
  propFilters: ByomPropFilterState;
  record: ByomRecord | null;
  loading: boolean;
  error: string | null;
  showsUnits: boolean;
  /** Side is still required, so the preview has not run. */
  blocked?: string | null;
  onRetry: () => void;
  onClose: () => void;
  onTab: (tab: ByomSheetTab) => void;
  onSide: (side: 'home' | 'away' | 'over' | 'under' | null) => void;
  onPrimetime: (primetime: boolean | null) => void;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const bets = record?.bets ?? 0;
  const showLabel = blocked || error
    ? 'Done'
    : loading
      ? 'Updating…'
      : `Show ${bets} bet${bets === 1 ? '' : 's'}`;
  const sideLabel = isYesOnlyProp(market)
    ? 'Yes'
    : propSide === 'under'
      ? 'Under'
      : propSide === 'over'
        ? 'Over'
        : 'Any';
  const reset = () => {
    const next = resetSheetFilters(propFilters);
    onPropFilters(next);
    onSide(null);
    if (next.kickSlots.includes('prime')) onPrimetime(null);
  };
  return (
    <Modal
      visible={tab != null}
      animationType="slide"
      presentationStyle="pageSheet"
      allowSwipeDismissal
      onRequestClose={onClose}
    >
      <SafeAreaView style={styles.screen} edges={['top', 'bottom']}>
      <KeyboardAvoidingView
        style={styles.flex}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      >
        <View style={styles.nav}>
          <Pressable
            onPress={reset}
            accessibilityRole="button"
            accessibilityLabel="Reset filters"
            style={styles.navBtn}
          >
            <Text style={styles.navText}>Reset</Text>
          </Pressable>
          <Text style={styles.navTitle}>More filters</Text>
          <Pressable
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel="Done"
            style={styles.navBtn}
          >
            <Text style={[styles.navText, styles.navDone]}>Done</Text>
          </Pressable>
        </View>
        <View style={styles.segment} accessibilityRole="tablist">
          {(['odds', 'time', 'matchup'] as const).map((item) => {
            const selected = item === tab;
            const label = item === 'odds' ? 'Odds' : item === 'time' ? 'Time' : 'Matchup';
            return (
              <Pressable
                key={item}
                onPress={() => onTab(item)}
                accessibilityRole="tab"
                accessibilityLabel={label}
                accessibilityState={{ selected }}
                style={[styles.segmentItem, selected && styles.segmentOn]}
              >
                <Text style={[styles.segmentText, selected && styles.segmentTextOn]}>{label}</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.context}>
          {sport} · {betTypeLabel(market)} · {sideLabel}
        </Text>
        <ScrollView
          style={styles.flex}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
        >
          {tab === 'odds' ? (
            <OddsTab
              sport={sport}
              market={market}
              propFilters={propFilters}
              onPropFilters={onPropFilters}
            />
          ) : null}
          {tab === 'time' ? (
            <TimeTab
              sport={sport}
              primetime={primetime}
              propFilters={propFilters}
              onPrimetime={onPrimetime}
              onPropFilters={onPropFilters}
            />
          ) : null}
          {tab === 'matchup' ? (
            <MatchupTab
              sport={sport}
              side={side}
              propFilters={propFilters}
              onSide={onSide}
              onPropFilters={onPropFilters}
            />
          ) : null}
        </ScrollView>
        <ByomBetCount
          record={record}
          loading={loading && blocked == null}
          error={error}
          onRetry={onRetry}
          showsUnits={showsUnits}
          blocked={blocked}
        />
        <Pressable
          onPress={onClose}
          accessibilityRole="button"
          accessibilityLabel={showLabel}
          style={styles.show}
        >
          <Text style={styles.showText}>{showLabel}</Text>
        </Pressable>
      </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}

function Card({
  title,
  detail,
  children,
}: {
  title: string;
  detail?: string;
  children: React.ReactNode;
}) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>{title}</Text>
      {detail ? <Text style={styles.cardDetail}>{detail}</Text> : null}
      {children}
    </View>
  );
}

function OddsTab({
  sport,
  market,
  propFilters,
  onPropFilters,
}: {
  sport: ByomSport;
  market: ByomMarket;
  propFilters: ByomPropFilterState;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const scale = lineScale(market);
  const hidden = isYesOnlyProp(market);
  const locked = !hidden && scale == null;
  const spread = SPREAD_SCALE;
  const total = totalScale(sport);
  const setPrice = (band: ByomPriceBand | 'any') => {
    if (band === 'any') {
      onPropFilters({ ...propFilters, priceBand: null, priceCustom: null });
      return;
    }
    onPropFilters({
      ...propFilters,
      priceBand: band,
      priceCustom: band === 'custom' ? (propFilters.priceCustom ?? openPriceBand()) : propFilters.priceCustom,
    });
  };
  return (
    <View>
      {hidden ? null : (
        <Card
          title="Player line"
          detail={locked
            ? 'Custom needs exactly one stat'
            : `The player’s ${betTypeLabel(market)} line at game start`}
        >
          <View style={styles.chips}>
            <ByomCheckChip
              label="Any"
              exclusive
              selected={propFilters.lineBand == null}
              onPress={() => onPropFilters({ ...propFilters, lineBand: null })}
            />
            <ByomCheckChip
              label="Custom"
              exclusive
              selected={propFilters.lineBand != null}
              disabled={locked || scale == null}
              onPress={() => {
                if (scale == null) return;
                onPropFilters({ ...propFilters, lineBand: propFilters.lineBand ?? openBand(scale) });
              }}
            />
          </View>
          {locked ? (
            <Text style={styles.note}>
              Lines differ by stat, so Custom is off when more than one stat is selected.
            </Text>
          ) : null}
          {scale != null && propFilters.lineBand ? (
            <>
              <BandStepper
                band={propFilters.lineBand}
                scale={scale}
                formatValue={formatLineNumber}
                onChange={(lineBand) => onPropFilters({ ...propFilters, lineBand })}
              />
              <Text style={styles.note}>{lineStepNote(scale)}</Text>
            </>
          ) : null}
        </Card>
      )}
      <Card title="Price" detail="DraftKings price on your side at game start">
        <View style={styles.chips}>
          {PRICE_CHOICES.map((choice) => (
            <ByomCheckChip
              key={choice.value}
              label={choice.label}
              exclusive
              selected={(propFilters.priceBand ?? 'any') === choice.value}
              onPress={() => setPrice(choice.value)}
            />
          ))}
        </View>
        {propFilters.priceBand === 'custom' && propFilters.priceCustom ? (
          <BandStepper
            band={propFilters.priceCustom}
            scale={null}
            price
            formatValue={formatAmericanBand}
            onChange={(priceCustom) => onPropFilters({ ...propFilters, priceCustom })}
          />
        ) : null}
      </Card>
      <Card title="Game spread" detail="Player’s team spread at game start">
        <View style={styles.chips}>
          <ByomCheckChip
            label="Any"
            exclusive
            selected={propFilters.spreadBand == null}
            onPress={() => onPropFilters({ ...propFilters, spreadBand: null })}
          />
          <ByomCheckChip
            label="Custom"
            exclusive
            selected={propFilters.spreadBand != null}
            onPress={() => onPropFilters({
              ...propFilters,
              spreadBand: propFilters.spreadBand ?? openBand(spread),
            })}
          />
        </View>
        {propFilters.spreadBand ? (
          <BandStepper
            band={propFilters.spreadBand}
            scale={spread}
            formatValue={formatSpread}
            onChange={(spreadBand) => onPropFilters({ ...propFilters, spreadBand })}
          />
        ) : null}
        <Text style={styles.note}>Team spread from −14 to +14 in 0.5 steps.</Text>
      </Card>
      <Card title="Game total" detail="Game over/under at game start">
        <View style={styles.chips}>
          <ByomCheckChip
            label="Any"
            exclusive
            selected={propFilters.totalBand == null}
            onPress={() => onPropFilters({ ...propFilters, totalBand: null })}
          />
          <ByomCheckChip
            label="Custom"
            exclusive
            selected={propFilters.totalBand != null}
            onPress={() => onPropFilters({
              ...propFilters,
              totalBand: propFilters.totalBand ?? openBand(total),
            })}
          />
        </View>
        {propFilters.totalBand ? (
          <BandStepper
            band={propFilters.totalBand}
            scale={total}
            formatValue={formatLineNumber}
            onChange={(totalBand) => onPropFilters({ ...propFilters, totalBand })}
          />
        ) : null}
      </Card>
    </View>
  );
}

function TimeTab({
  sport,
  primetime,
  propFilters,
  onPrimetime,
  onPropFilters,
}: {
  sport: ByomSport;
  primetime: boolean | null;
  propFilters: ByomPropFilterState;
  onPrimetime: (primetime: boolean | null) => void;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const months = monthsFor(sport);
  const days = daysFor(sport);
  const slots = shownKickSlots(propFilters.kickSlots, primetime);
  const setSlots = (kickSlots: ByomPropFilterState['kickSlots']) => {
    const next = withKickSlots(kickSlots);
    onPrimetime(next.primetime);
    onPropFilters({ ...propFilters, kickSlots: next.kickSlots });
  };
  return (
    <View>
      <Card title="Month">
        <View style={styles.chips}>
          <ByomCheckChip
            label="Any"
            selected={propFilters.months.length === 0}
            onPress={() => onPropFilters({ ...propFilters, months: [] })}
          />
          {months.map((month) => (
            <ByomCheckChip
              key={month.value}
              label={month.label}
              selected={propFilters.months.includes(month.value)}
              onPress={() => onPropFilters({
                ...propFilters,
                months: toggleMember(propFilters.months, month.value, months.map((item) => item.value)),
              })}
            />
          ))}
        </View>
      </Card>
      <Card title="Day of week" detail={sport === 'NBA' ? 'Tipoff day, ET' : 'Kickoff day, ET'}>
        <View style={styles.chips}>
          <ByomCheckChip
            label="Any"
            selected={propFilters.weekdays.length === 0}
            onPress={() => onPropFilters({ ...propFilters, weekdays: [] })}
          />
          {days.map((day) => (
            <ByomCheckChip
              key={day.value}
              label={day.label}
              selected={propFilters.weekdays.includes(day.value)}
              onPress={() => onPropFilters({
                ...propFilters,
                weekdays: toggleMember(propFilters.weekdays, day.value, days.map((item) => item.value)),
              })}
            />
          ))}
        </View>
      </Card>
      {sport === 'NFL' ? (
        <Card title="Time slot" detail="From kickoff time, ET">
          <View style={styles.chips}>
            <ByomCheckChip
              label="Any"
              selected={slots.length === 0}
              onPress={() => setSlots([])}
            />
            {KICK_SLOTS.map((slot) => (
              <ByomCheckChip
                key={slot.value}
                label={slot.label}
                selected={slots.includes(slot.value)}
                onPress={() => setSlots(toggleMember(
                  slots,
                  slot.value,
                  KICK_SLOTS.map((item) => item.value),
                ))}
              />
            ))}
          </View>
          <Text style={styles.note}>
            Early = before 2 PM · Late = 2–6 PM · Primetime = 7 PM or later. London/Christmas games use their ET kickoff.
          </Text>
        </Card>
      ) : null}
      {sport === 'NFL' ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>Weeks</Text>
          <Text style={styles.cardDetail}>Live today · unchanged</Text>
          <Text style={styles.weekLine}>Week 1 – Week 18</Text>
        </View>
      ) : null}
    </View>
  );
}

function MatchupTab({
  sport,
  side,
  propFilters,
  onSide,
  onPropFilters,
}: {
  sport: ByomSport;
  side: 'home' | 'away' | 'over' | 'under' | null;
  propFilters: ByomPropFilterState;
  onSide: (side: 'home' | 'away' | 'over' | 'under' | null) => void;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const teamSide = side === 'home' || side === 'away' ? side : 'any';
  const [teamQuery, setTeamQuery] = useState('');
  const teams = filterTeams(teamsForSport(sport), teamQuery);
  return (
    <View>
      <Card title="Player’s team" detail="Home or away for the player’s team">
        <View style={styles.chips}>
          {([
            ['any', 'Any'],
            ['home', 'Home'],
            ['away', 'Away'],
          ] as const).map(([value, label]) => (
            <ByomCheckChip
              key={value}
              label={label}
              exclusive
              selected={teamSide === value}
              onPress={() => onSide(value === 'any' ? null : value)}
            />
          ))}
        </View>
      </Card>
      <View style={styles.card}>
        <Text style={styles.cardTitle}>Opponent</Text>
        <Text style={styles.cardDetail}>Any by default · pick one or more</Text>
        {propFilters.opponents.length > 0 ? (
          <View style={styles.chips}>
            {[...propFilters.opponents].sort().map((abbrev) => (
              <ByomCheckChip
                key={abbrev}
                label={`${abbrev} \u2715`}
                selected
                showCheck={false}
                accessibilityLabel={`Remove ${abbrev}`}
                onPress={() => onPropFilters({
                  ...propFilters,
                  opponents: propFilters.opponents.filter((item) => item !== abbrev),
                })}
              />
            ))}
          </View>
        ) : null}
        <TextInput
          value={teamQuery}
          onChangeText={setTeamQuery}
          placeholder="Search teams"
          placeholderTextColor={colors.textTertiary}
          accessibilityLabel="Search teams"
          autoCorrect={false}
          style={styles.search}
        />
        {teams.map((team) => {
          const selected = propFilters.opponents.includes(team.abbrev);
          return (
            <Pressable
              key={team.abbrev}
              onPress={() => onPropFilters({
                ...propFilters,
                opponents: selected
                  ? propFilters.opponents.filter((item) => item !== team.abbrev)
                  : [...propFilters.opponents, team.abbrev],
              })}
              accessibilityRole="button"
              accessibilityLabel={team.name}
              accessibilityState={{ selected }}
              style={styles.team}
            >
              <Text style={[styles.teamText, selected && styles.teamTextOn]}>{team.name}</Text>
              {selected ? <Text style={styles.check}>{'\u2713'}</Text> : null}
            </Pressable>
          );
        })}
      </View>
      <PlayerPicker sport={sport} propFilters={propFilters} onPropFilters={onPropFilters} />
    </View>
  );
}

function PlayerPicker({
  sport,
  propFilters,
  onPropFilters,
}: {
  sport: ByomSport;
  propFilters: ByomPropFilterState;
  onPropFilters: (next: ByomPropFilterState) => void;
}) {
  const [query, setQuery] = useState('');
  const [names, setNames] = useState<string[]>([]);
  const [missing, setMissing] = useState(false);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);
  const seq = useRef(0);
  useEffect(() => {
    const trimmed = query.trim();
    if (trimmed.length < 2) {
      setNames([]);
      setMissing(false);
      setSearching(false);
      setSearchError(null);
      return;
    }
    const id = ++seq.current;
    setSearching(true);
    const timer = setTimeout(() => {
      void searchByomPlayerNames(sport, trimmed).then((result) => {
        if (seq.current !== id) return;
        setNames(result.names);
        setMissing(result.missing);
        setSearchError(null);
        setSearching(false);
      }).catch(() => {
        if (seq.current !== id) return;
        setNames([]);
        setMissing(false);
        setSearchError('Couldn’t search players.');
        setSearching(false);
      });
    }, 300);
    return () => clearTimeout(timer);
  }, [query, sport, retry]);
  const typed = query.trim();
  return (
    <View style={styles.card}>
      <Text style={styles.cardTitle}>Player · optional</Text>
      <Text style={styles.cardDetail}>Only this player’s lines</Text>
      {propFilters.player ? (
        <View style={styles.chips}>
          <ByomCheckChip
            label={`${propFilters.player} \u2715`}
            selected
            showCheck={false}
            accessibilityLabel={`Remove ${propFilters.player}`}
            onPress={() => onPropFilters({ ...propFilters, player: null })}
          />
        </View>
      ) : null}
      <TextInput
        value={query}
        onChangeText={setQuery}
        placeholder="Search players (e.g. CeeDee Lamb)"
        placeholderTextColor={colors.textTertiary}
        accessibilityLabel="Search players"
        autoCorrect={false}
        style={styles.search}
      />
      {searching ? <ActivityIndicator style={styles.note} color={colors.tint} /> : null}
      {names.map((name) => (
        <Pressable
          key={name}
          onPress={() => onPropFilters({ ...propFilters, player: name })}
          accessibilityRole="button"
          accessibilityLabel={name}
          accessibilityState={{ selected: propFilters.player === name }}
          style={styles.team}
        >
          <Text style={styles.teamText}>{name}</Text>
        </Pressable>
      ))}
      {missing && typed.length >= 2 ? (
        <Pressable
          onPress={() => onPropFilters({ ...propFilters, player: typed })}
          accessibilityRole="button"
          accessibilityLabel={`Use ${typed}`}
          style={styles.team}
        >
          <Text style={styles.teamText}>Use “{typed}”</Text>
        </Pressable>
      ) : null}
      {!searching && !searchError && !missing && typed.length >= 2 && names.length === 0 ? (
        <Text style={styles.note}>No players match</Text>
      ) : null}
      {searchError ? (
        <Pressable
          onPress={() => setRetry((current) => current + 1)}
          accessibilityRole="button"
          accessibilityLabel="Retry player search"
          style={styles.team}
        >
          <Text style={styles.teamText}>{searchError} Retry</Text>
        </Pressable>
      ) : null}
      {propFilters.player == null && typed.length < 2 && searchError == null ? (
        <Text style={styles.note}>Any player (default). Picking one narrows the sample a lot.</Text>
      ) : null}
    </View>
  );
}

function BandStepper({
  band,
  scale,
  price = false,
  formatValue,
  onChange,
}: {
  band: ByomBand;
  scale: LineScale | null;
  price?: boolean;
  formatValue: (value: number) => string;
  onChange: (band: ByomBand) => void;
}) {
  const rows: { edge: 'min' | 'max'; caption: string; foot: string }[] = [
    { edge: 'min', caption: 'From', foot: 'min' },
    { edge: 'max', caption: 'To', foot: 'max' },
  ];
  return (
    <View style={styles.stepper}>
      {rows.map((row) => {
        const dec = price || scale == null
          ? canMovePrice(band, row.edge, -1)
          : canMoveBand(band, row.edge, -1, scale);
        const inc = price || scale == null
          ? canMovePrice(band, row.edge, 1)
          : canMoveBand(band, row.edge, 1, scale);
        const shown = formatValue(band[row.edge]);
        return (
          <View key={row.edge} style={styles.stepRow}>
            <Pressable
              onPress={() => onChange(price || scale == null
                ? movePrice(band, row.edge, -1)
                : moveBand(band, row.edge, -1, scale))}
              disabled={!dec}
              accessibilityRole="button"
              accessibilityLabel={`Decrease ${row.caption}, ${shown}`}
              accessibilityState={{ disabled: !dec }}
              style={[styles.stepBtn, !dec && styles.stepBtnOff]}
            >
              <Text style={styles.stepBtnText}>{'\u2212'}</Text>
            </Pressable>
            <View style={styles.stepValue}>
              <Text style={styles.stepCaption}>{row.caption}</Text>
              <Text style={styles.stepNumber}>{shown}</Text>
              <Text style={styles.stepCaption}>{row.foot}</Text>
            </View>
            <Pressable
              onPress={() => onChange(price || scale == null
                ? movePrice(band, row.edge, 1)
                : moveBand(band, row.edge, 1, scale))}
              disabled={!inc}
              accessibilityRole="button"
              accessibilityLabel={`Increase ${row.caption}, ${shown}`}
              accessibilityState={{ disabled: !inc }}
              style={[styles.stepBtn, !inc && styles.stepBtnOff]}
            >
              <Text style={styles.stepBtnText}>+</Text>
            </Pressable>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: colors.bg,
    paddingHorizontal: spacing.lg,
  },
  flex: { flex: 1 },
  content: { paddingBottom: spacing.lg },
  nav: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
  },
  navBtn: {
    minHeight: 44,
    minWidth: 64,
    justifyContent: 'center',
  },
  navText: {
    fontSize: font.size.callout,
    color: colors.tint,
  },
  navDone: {
    textAlign: 'right',
    fontWeight: font.weight.semibold,
  },
  navTitle: {
    flex: 1,
    textAlign: 'center',
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  segment: {
    flexDirection: 'row',
    backgroundColor: colors.noneSoft,
    borderRadius: radii.sm,
    padding: 2,
    marginBottom: spacing.sm,
  },
  segmentItem: {
    flex: 1,
    minHeight: 44,
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: radii.sm,
  },
  segmentOn: {
    backgroundColor: colors.bgCard,
  },
  segmentText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  segmentTextOn: {
    color: colors.textPrimary,
  },
  context: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.md,
    padding: spacing.md,
    marginBottom: spacing.md,
  },
  cardTitle: {
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  cardDetail: {
    marginTop: 2,
    marginBottom: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: spacing.sm,
    marginTop: spacing.sm,
  },
  note: {
    marginTop: spacing.sm,
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  weekLine: {
    marginTop: spacing.sm,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  stepper: {
    marginTop: spacing.md,
    gap: spacing.sm,
  },
  stepRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.bg,
    borderRadius: radii.md,
    padding: spacing.sm,
  },
  stepBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: colors.bgCard,
    borderWidth: 1,
    borderColor: colors.low,
    alignItems: 'center',
    justifyContent: 'center',
  },
  stepBtnOff: {
    opacity: 0.4,
  },
  stepBtnText: {
    fontSize: font.size.title3,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  stepValue: {
    flex: 1,
    alignItems: 'center',
  },
  stepCaption: {
    fontSize: font.size.caption,
    color: colors.textSecondary,
  },
  stepNumber: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  search: {
    minHeight: 44,
    marginTop: spacing.sm,
    borderRadius: radii.md,
    backgroundColor: colors.noneSoft,
    paddingHorizontal: spacing.md,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  team: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.separatorOpaque,
  },
  teamText: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  teamTextOn: {
    fontWeight: font.weight.bold,
  },
  check: {
    fontSize: font.size.body,
    fontWeight: font.weight.bold,
    color: colors.tint,
  },
  show: {
    minHeight: 50,
    borderRadius: radii.md,
    backgroundColor: colors.tint,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.sm,
  },
  showText: {
    color: colors.textInverse,
    fontSize: font.size.headline,
    fontWeight: font.weight.semibold,
  },
});
