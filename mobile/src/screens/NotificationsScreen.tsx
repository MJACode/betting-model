import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import {
  AccessibilityInfo,
  ActivityIndicator,
  Alert,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import Swipeable from 'react-native-gesture-handler/Swipeable';
import { SafeAreaView, useSafeAreaInsets } from 'react-native-safe-area-context';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ErrorBanner } from '@/components/ErrorState';
import { readAuthUserId } from '@/hooks/useAuth';
import { useBetslipBarInset } from '@/hooks/useBetslipBarInset';
import { openPushRoute } from '@/hooks/usePushDeepLink';
import { refreshNotificationInbox, useNotificationInbox } from '@/hooks/useNotificationInbox';
import {
  inboxIconName,
  inboxRouteCaption,
  inboxSection,
  inboxTimeLabel,
  type InboxRow,
} from '@/lib/notificationInbox';
import { routeForPush } from '@/lib/pushRoute';
import { colors, font, opacity, radii, sectionHeaderText, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/** How long a swiped-away alert can be brought back before the hide is written. */
const UNDO_MS = 4500;

function NotificationsHeaderActions() {
  const navigation = useNavigation<Nav>();
  const { unread, markAllRead } = useNotificationInbox();
  const canMark = unread > 0;
  return (
    <View style={styles.headerActions}>
      <Pressable
        onPress={() => navigation.navigate('SettingsSection', { section: 'notifications' })}
        hitSlop={8}
        accessibilityRole="button"
        accessibilityLabel="Notification settings"
        style={({ pressed }) => [styles.iconBtn, pressed && { opacity: opacity.pressed }]}
      >
        <Ionicons name="settings-outline" size={22} color={colors.tint} />
      </Pressable>
      <Pressable
        onPress={() => void markAllRead()}
        disabled={!canMark}
        accessibilityRole="button"
        accessibilityLabel="Mark all read"
        accessibilityState={{ disabled: !canMark }}
        hitSlop={8}
        accessibilityShowsLargeContentViewer
        accessibilityLargeContentTitle="Mark all read"
        style={({ pressed }) => [styles.markBtn, pressed && canMark && { opacity: opacity.pressed }]}
      >
        <Text style={[styles.markText, !canMark && styles.markTextOff]} maxFontSizeMultiplier={1.4}>
          Mark all read
        </Text>
      </Pressable>
    </View>
  );
}

export function NotificationsScreen() {
  const navigation = useNavigation<Nav>();
  const inbox = useNotificationInbox();
  const now = useMemo(() => new Date(), [inbox.rows]);

  useLayoutEffect(() => {
    navigation.setOptions({ headerRight: () => <NotificationsHeaderActions /> });
  }, [navigation]);

  // Select mode: tap rows to pick them, then Delete. "Delete" hides the alert
  // for this member; the stored row is kept (CLAUDE.md section 1b).
  const [selecting, setSelecting] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const betslipInset = useBetslipBarInset();
  const insets = useSafeAreaInsets();
  // The betslip bar's height already includes the home-indicator inset, and
  // the SafeAreaView pads by it too. Count it once.
  const aboveBetslip = Math.max(0, betslipInset - insets.bottom);
  const openSwipe = useRef<Swipeable | null>(null);

  // A swiped-away row is hidden at once and written after UNDO_MS, so Undo
  // never touches the server. Leaving the screen writes it straight away.
  const [pending, setPending] = useState<InboxRow[]>([]);
  const pendingRef = useRef<InboxRow[]>([]);
  const undoTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rows = useMemo(() => {
    if (pending.length === 0) return inbox.rows;
    const gone = new Set(pending.map((r) => r.id));
    return inbox.rows.filter((r) => !gone.has(r.id));
  }, [inbox.rows, pending]);
  const canDelete = inbox.canDelete && rows.length > 0;

  // A row that left the list (deleted, muted, aged out) leaves the selection,
  // and an emptied list leaves select mode.
  useEffect(() => {
    const ids = new Set(rows.map((r) => r.id));
    setSelected((prev) => {
      const next = new Set([...prev].filter((id) => ids.has(id)));
      return next.size === prev.size ? prev : next;
    });
    if (rows.length === 0) setSelecting(false);
  }, [rows]);

  const startSelecting = () => {
    openSwipe.current?.close();
    setSelected(new Set());
    setSelecting(true);
  };
  const stopSelecting = () => {
    setSelecting(false);
    setSelected(new Set());
  };
  const allSelected = rows.length > 0 && selected.size === rows.length;
  const toggleAll = () => setSelected(allSelected ? new Set() : new Set(rows.map((r) => r.id)));
  const toggleRow = (row: InboxRow) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(row.id)) next.delete(row.id);
      else next.add(row.id);
      return next;
    });

  const deleteRows = inbox.deleteRows;
  const runDelete = useCallback(
    async (rows: InboxRow[]) => {
      const ok = await deleteRows(rows);
      if (!ok) {
        Alert.alert('Couldn’t delete', 'Check your connection and try again.');
        return;
      }
    },
    [deleteRows],
  );

  const commitPending = useCallback(() => {
    if (undoTimer.current) clearTimeout(undoTimer.current);
    undoTimer.current = null;
    const toWrite = pendingRef.current;
    pendingRef.current = [];
    setPending([]);
    if (toWrite.length) void runDelete(toWrite);
  }, [runDelete]);

  // Leaving the screen (or the app closing it) writes what is still pending.
  const commitRef = useRef(commitPending);
  commitRef.current = commitPending;
  useEffect(() => () => commitRef.current(), []);

  const swipeDelete = (row: InboxRow) => {
    // One undo at a time: an earlier swipe is written now.
    commitPending();
    pendingRef.current = [row];
    setPending([row]);
    AccessibilityInfo.announceForAccessibility('Notification deleted');
    undoTimer.current = setTimeout(commitPending, UNDO_MS);
  };

  const undoDelete = () => {
    if (undoTimer.current) clearTimeout(undoTimer.current);
    undoTimer.current = null;
    pendingRef.current = [];
    setPending([]);
  };

  const deleteSelected = () => {
    const chosen = rows.filter((r) => selected.has(r.id));
    if (chosen.length === 0) return;
    const title = allSelected
      ? chosen.length === 1
        ? 'Delete this notification?'
        : `Delete all ${chosen.length} notifications?`
      : chosen.length === 1
        ? 'Delete this notification?'
        : `Delete ${chosen.length} notifications?`;
    const body =
      chosen.length === 1
        ? 'It’ll be removed from this list. This can’t be undone.'
        : 'They’ll be removed from this list. This can’t be undone.';
    Alert.alert(title, body, [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: () => {
          stopSelecting();
          commitPending();
          void runDelete(chosen).then(() =>
            AccessibilityInfo.announceForAccessibility(
              chosen.length === 1 ? 'Notification deleted' : `${chosen.length} notifications deleted`,
            ),
          );
        },
      },
    ]);
  };

  const dismissVisible = inbox.dismissVisible;
  useFocusEffect(
    useCallback(() => {
      let cancel = false;
      void refreshNotificationInbox(readAuthUserId()).then(() => {
        if (!cancel) void dismissVisible();
      });
      return () => {
        cancel = true;
      };
    }, [dismissVisible]),
  );

  const sections = useMemo(() => {
    const today = rows.filter((row) => inboxSection(row.sent_at, now) === 'TODAY');
    const earlier = rows.filter((row) => inboxSection(row.sent_at, now) === 'EARLIER');
    const out: { title: string; data: InboxRow[] }[] = [];
    if (today.length) out.push({ title: 'Today', data: today });
    if (earlier.length) out.push({ title: 'Earlier', data: earlier });
    return out;
  }, [rows, now]);

  const openRow = (row: InboxRow) => {
    if (selecting) {
      toggleRow(row);
      return;
    }
    void inbox.markRead(row);
    const route = routeForPush(row.route);
    if (route) openPushRoute(navigation, route);
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <View style={styles.windowRow}>
        <Text style={styles.window} accessibilityLiveRegion="polite">
          {selecting ? `${selected.size} selected` : 'Showing the last 7 days'}
        </Text>
        {canDelete ? (
          <Pressable
            onPress={selecting ? stopSelecting : startSelecting}
            accessibilityRole="button"
            accessibilityLabel={selecting ? 'Cancel selecting' : 'Select notifications'}
            hitSlop={8}
            style={({ pressed }) => [styles.selectBtn, pressed && { opacity: opacity.pressed }]}
          >
            <Text style={styles.selectText}>
              {selecting ? 'Cancel' : 'Select'}
            </Text>
          </Pressable>
        ) : null}
      </View>
      {inbox.error ? (
        <ErrorBanner
          what="notifications"
          error={inbox.error}
          onRetry={() => void inbox.refresh()}
          retrying={inbox.loading}
        />
      ) : null}
      {!inbox.loaded && !inbox.error ? (
        <View style={styles.empty}>
          <ActivityIndicator color={colors.tint} />
        </View>
      ) : sections.length === 0 && !inbox.error ? (
        <View style={styles.empty}>
          <View style={styles.emptyIcon}>
            <Ionicons name="notifications" size={22} color={colors.tint} />
          </View>
          <Text style={styles.emptyTitle}>No notifications</Text>
          <Text style={styles.emptyBody}>
            Nothing in the last 7 days. New BET signals, line moves, live picks, feedback replies,
            and test alerts will show up here.
          </Text>
          <Pressable
            onPress={() => navigation.navigate('SettingsSection', { section: 'notifications' })}
            accessibilityRole="button"
            accessibilityLabel="Notification settings"
            style={({ pressed }) => [styles.emptyLinkHit, pressed && { opacity: opacity.pressed }]}
          >
            <Text style={styles.emptyLink}>Notification settings</Text>
          </Pressable>
          <BetslipBarSpacer />
        </View>
      ) : (
        <SectionList
          sections={sections}
          keyExtractor={(row) => row.id}
          stickySectionHeadersEnabled={false}
          refreshControl={
            <RefreshControl refreshing={inbox.loading} onRefresh={() => void inbox.refresh()} tintColor={colors.tint} />
          }
          // In select mode the bar below already lifts the list clear of the slip.
          ListFooterComponent={selecting ? null : <BetslipBarSpacer />}
          renderSectionHeader={({ section }) => (
            <Text style={styles.section}>{section.title}</Text>
          )}
          renderItem={({ item }) => (
            <InboxListRow
              row={item}
              now={now}
              onPress={() => openRow(item)}
              selecting={selecting}
              selected={selected.has(item.id)}
              swipeToDelete={inbox.canDelete && !selecting}
              onDelete={() => swipeDelete(item)}
              onSwipeOpen={(ref) => {
                if (openSwipe.current && openSwipe.current !== ref) openSwipe.current.close();
                openSwipe.current = ref;
              }}
            />
          )}
          contentContainerStyle={styles.list}
        />
      )}
      {selecting && sections.length > 0 ? (
        <View style={[styles.selectBar, { marginBottom: aboveBetslip }]}>
          <Pressable
            onPress={toggleAll}
            accessibilityRole="button"
            accessibilityLabel={allSelected ? 'Deselect all' : 'Select all'}
            style={({ pressed }) => [styles.selectBarBtn, pressed && { opacity: opacity.pressed }]}
          >
            <Text style={styles.selectText}>
              {allSelected ? 'Deselect all' : 'Select all'}
            </Text>
          </Pressable>
          <Pressable
            onPress={deleteSelected}
            disabled={selected.size === 0}
            accessibilityRole="button"
            accessibilityLabel={
              selected.size === 0 ? 'Delete' : `Delete ${selected.size} selected`
            }
            accessibilityState={{ disabled: selected.size === 0 }}
            style={({ pressed }) => [
              styles.selectBarBtn,
              styles.selectBarDelete,
              pressed && selected.size > 0 && { opacity: opacity.pressed },
            ]}
          >
            <Ionicons
              name="trash-outline"
              size={18}
              color={selected.size === 0 ? colors.textTertiary : colors.avoid}
            />
            <Text style={[styles.deleteText, selected.size === 0 && styles.markTextOff]}>
              {selected.size === 0 ? 'Delete' : `Delete (${selected.size})`}
            </Text>
          </Pressable>
        </View>
      ) : null}
      {pending.length > 0 ? (
        <View style={[styles.undoBar, { bottom: spacing.xl + aboveBetslip }]}>
          <Text style={styles.undoText}>Notification deleted</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Undo delete"
            onPress={undoDelete}
            hitSlop={{ top: 12, bottom: 12, left: 8, right: 8 }}
            style={styles.undoBtn}
          >
            <Text style={styles.undoAction}>Undo</Text>
          </Pressable>
        </View>
      ) : null}
    </SafeAreaView>
  );
}

function InboxListRow({
  row,
  now,
  onPress,
  selecting,
  selected,
  swipeToDelete,
  onDelete,
  onSwipeOpen,
}: {
  row: InboxRow;
  now: Date;
  onPress: () => void;
  selecting: boolean;
  selected: boolean;
  swipeToDelete: boolean;
  onDelete: () => void;
  onSwipeOpen: (ref: Swipeable | null) => void;
}) {
  const unread = row.read_at == null;
  const swipeRef = useRef<Swipeable | null>(null);
  const label = `${unread ? 'Unread. ' : ''}${row.title}. ${row.body}`;
  const content = (
    <Pressable
      onPress={onPress}
      accessibilityRole={selecting ? 'checkbox' : 'button'}
      accessibilityState={selecting ? { checked: selected } : undefined}
      accessibilityLabel={label}
      // VoiceOver has no swipe: the same delete is a rotor action.
      accessibilityActions={swipeToDelete ? [{ name: 'delete', label: 'Delete' }] : undefined}
      onAccessibilityAction={(e) => {
        if (e.nativeEvent.actionName === 'delete') onDelete();
      }}
      style={({ pressed }) => [
        styles.row,
        selected && styles.rowSelected,
        pressed && { opacity: opacity.pressed },
      ]}
    >
      {selecting ? (
        <View style={styles.check} importantForAccessibility="no">
          <Ionicons
            name={selected ? 'checkmark-circle' : 'ellipse-outline'}
            size={24}
            color={selected ? colors.tint : colors.textTertiary}
          />
        </View>
      ) : null}
      <View style={styles.iconTile}>
        <Ionicons name={inboxIconName(row) as 'notifications'} size={18} color={colors.tint} />
      </View>
      <View style={styles.rowBody}>
        <View style={styles.titleLine}>
          <Text style={styles.title} numberOfLines={2}>
            {row.title}
          </Text>
          <Text style={styles.time}>{inboxTimeLabel(row.sent_at, now)}</Text>
        </View>
        <Text style={styles.body} numberOfLines={3}>
          {row.body}
        </Text>
        <Text style={styles.caption}>{inboxRouteCaption(row)}</Text>
      </View>
      {unread ? <View style={styles.dot} importantForAccessibility="no" /> : <View style={styles.dotSpacer} />}
    </Pressable>
  );
  if (!swipeToDelete) return content;
  const renderRightActions = () => (
    <Pressable
      // VoiceOver reaches delete through the row's own Delete action. RNGH
      // renders this button behind a closed row, so keep it out of the tree.
      accessibilityRole="button"
      accessibilityLabel="Delete notification"
      accessibilityElementsHidden
      importantForAccessibility="no-hide-descendants"
      onPress={() => {
        swipeRef.current?.close();
        onDelete();
      }}
      style={({ pressed }) => [styles.swipeDelete, pressed && { opacity: opacity.pressed }]}
    >
      <Ionicons name="trash-outline" size={22} color={colors.onChrome} />
      <Text style={styles.swipeDeleteText}>Delete</Text>
    </Pressable>
  );
  return (
    <Swipeable
      ref={swipeRef}
      renderRightActions={renderRightActions}
      overshootRight={false}
      onSwipeableWillOpen={() => onSwipeOpen(swipeRef.current)}
    >
      {content}
    </Swipeable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bg },
  headerActions: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  iconBtn: { padding: 4 },
  markBtn: { height: 36, justifyContent: 'center', paddingHorizontal: spacing.xs },
  markText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  markTextOff: { color: colors.textTertiary },
  windowRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.sm,
  },
  window: {
    flexShrink: 1,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
  },
  selectBtn: { minHeight: 44, minWidth: 44, justifyContent: 'center', alignItems: 'flex-end' },
  selectText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.tint,
  },
  selectBar: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.xs,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    backgroundColor: colors.bgElevated,
  },
  selectBarBtn: { minHeight: 44, justifyContent: 'center', flexDirection: 'row', alignItems: 'center' },
  selectBarDelete: { gap: spacing.xs },
  deleteText: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.avoid,
  },
  undoBar: {
    position: 'absolute',
    left: spacing.lg,
    right: spacing.lg,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    backgroundColor: colors.textPrimary,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  undoBtn: { minHeight: 44, justifyContent: 'center' },
  undoText: {
    color: colors.bg,
    fontSize: font.size.callout,
    fontWeight: font.weight.medium,
  },
  // Same ink and underline as SavedParlays' undo banner (UX review, 2026-11-16).
  undoAction: {
    color: colors.bg,
    textDecorationLine: 'underline',
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
  },
  check: { justifyContent: 'center', alignSelf: 'center' },
  rowSelected: { backgroundColor: colors.tintSoft },
  swipeDelete: {
    minHeight: 44,
    width: 92,
    backgroundColor: colors.avoid,
    justifyContent: 'center',
    alignItems: 'center',
    gap: 2,
  },
  swipeDeleteText: {
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.onChrome,
  },
  list: { paddingBottom: spacing.xl },
  section: {
    ...sectionHeaderText,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.md,
    paddingBottom: spacing.xs,
  },
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: spacing.md,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md,
    minHeight: 44,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    // Opaque so the swipe's red action is hidden until the row slides.
    backgroundColor: colors.bg,
  },
  iconTile: {
    width: 36,
    height: 36,
    borderRadius: radii.sm,
    backgroundColor: colors.tintSoft,
    alignItems: 'center',
    justifyContent: 'center',
    marginTop: 2,
  },
  rowBody: { flex: 1, minWidth: 0 },
  titleLine: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  title: {
    flex: 1,
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  time: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginTop: 2,
  },
  body: {
    marginTop: 2,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  caption: {
    marginTop: 2,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.tint,
    marginTop: 8,
  },
  dotSpacer: { width: 8 },
  empty: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: spacing.xl,
    paddingBottom: spacing.xxl,
  },
  emptyIcon: {
    width: 56,
    height: 56,
    borderRadius: radii.md,
    backgroundColor: colors.bgCard,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: spacing.lg,
  },
  emptyTitle: {
    fontSize: font.size.title3,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
    marginBottom: spacing.sm,
    textAlign: 'center',
  },
  emptyBody: {
    fontSize: font.size.body,
    color: colors.textSecondary,
    textAlign: 'center',
    marginBottom: spacing.lg,
  },
  emptyLinkHit: { minHeight: 44, justifyContent: 'center' },
  emptyLink: {
    fontSize: font.size.callout,
    fontWeight: font.weight.semibold,
    color: colors.tint,
    textAlign: 'center',
  },
});
