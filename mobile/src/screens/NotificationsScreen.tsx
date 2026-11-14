import React, { useCallback, useLayoutEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  SectionList,
  StyleSheet,
  Text,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { useNotificationInbox } from '@/hooks/useNotificationInbox';
import { navigateTo } from '@/hooks/usePushDeepLink';
import { routeForPush, type PushRoute } from '@/lib/pushRoute';
import {
  inboxRowSpeech,
  inboxSections,
  inboxTimeLabel,
  type InboxItem,
} from '@/lib/notificationInboxHelpers';
import { showToast } from '@/components/Toast';
import { EmptyState } from '@/components/EmptyState';
import { ErrorBanner, ErrorState } from '@/components/ErrorState';
import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { colors, font, opacity, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

function hintFor(route: PushRoute | null): string | undefined {
  if (!route) return undefined;
  switch (route.kind) {
    case 'pick':
      return 'Opens the pick';
    case 'feedbackThread':
      return 'Opens the conversation';
    case 'board':
      return 'Opens the Picks board';
  }
}

/**
 * The notifications inbox (Matt, 2026-11-14): every push from the last 30
 * days, word for word, newest first. Unread rows are bold with a dot. A tap
 * clears that one and opens what it is about, the same place the push opens.
 * "Read all" clears the rest. Alerts are kept here even while push is off, so
 * this is also where a muted phone sees what it missed.
 */
export function NotificationsScreen() {
  const navigation = useNavigation<Nav>();
  const { items, unread, loaded, loading, error, refresh, markRead, markAllRead } =
    useNotificationInbox();

  // Every focus: a push may have landed while the screen was behind another.
  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const sections = useMemo(() => inboxSections(items), [items]);

  // The spinner shows for a pull only, not for the refresh on every return.
  const [pulling, setPulling] = useState(false);
  const pull = useCallback(async () => {
    setPulling(true);
    await refresh();
    setPulling(false);
  }, [refresh]);

  const open = useCallback(
    (item: InboxItem) => {
      if (!item.is_read) void markRead(item.id);
      const route = routeForPush(item.data);
      // A payload this build cannot read only clears the item. The words are
      // already on screen, which is the whole message.
      if (route) navigateTo(navigation, route);
    },
    [markRead, navigation],
  );

  const readAll = useCallback(async () => {
    const ok = await markAllRead();
    if (!ok) showToast('Couldn’t mark them read. Try again.', { announce: true });
  }, [markAllRead]);

  // Read all lives in the navigation bar, so it is still there after the list
  // has scrolled (UX review, 2026-11-14). Shown only while something is unread.
  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight:
        unread > 0
          ? () => (
              <Pressable
                onPress={() => void readAll()}
                accessibilityRole="button"
                accessibilityLabel={`Mark all ${unread} as read`}
                style={({ pressed }) => [styles.readAll, pressed && { opacity: opacity.pressed }]}
              >
                <Ionicons name="checkmark-done" size={16} color={colors.tint} />
                <Text style={styles.readAllText}>Read all</Text>
              </Pressable>
            )
          : undefined,
    });
  }, [navigation, unread, readAll]);

  const header =
    items.length > 0 ? (
      <View>
        {error ? (
          <ErrorBanner what="your notifications" error={error} onRetry={() => void refresh()} retrying={loading} />
        ) : null}
        <Text style={styles.toolbarText} accessibilityRole="header">
          {unread > 0 ? `${unread} unread` : 'All caught up'}
        </Text>
      </View>
    ) : null;

  if (!loaded && loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator />
      </View>
    );
  }

  return (
    <SectionList
      style={styles.list}
      contentContainerStyle={styles.content}
      sections={sections}
      keyExtractor={(item) => String(item.id)}
      stickySectionHeadersEnabled={false}
      refreshControl={<RefreshControl refreshing={pulling} onRefresh={() => void pull()} />}
      ListHeaderComponent={header}
      renderSectionHeader={({ section }) => (
        <Text style={styles.sectionTitle} accessibilityRole="header">
          {section.title}
        </Text>
      )}
      renderItem={({ item, index, section }) => (
        <Pressable
          onPress={() => open(item)}
          accessibilityRole="button"
          accessibilityLabel={inboxRowSpeech(item)}
          accessibilityHint={hintFor(routeForPush(item.data))}
          style={({ pressed }) => [
            styles.row,
            index === 0 && styles.rowFirst,
            index === section.data.length - 1 && styles.rowLast,
            pressed && { backgroundColor: colors.tintSoft },
          ]}
        >
          <View style={styles.dotSlot}>
            {item.is_read ? null : <View style={styles.dot} />}
          </View>
          <View style={styles.rowBody}>
            <View style={styles.rowTop}>
              <Text
                style={[styles.title, !item.is_read && styles.titleUnread]}
                numberOfLines={3}
              >
                {item.title}
              </Text>
              <Text style={styles.time}>{inboxTimeLabel(item.created_at)}</Text>
            </View>
            {item.body ? (
              <Text style={styles.body}>
                {item.body}
              </Text>
            ) : null}
          </View>
        </Pressable>
      )}
      ItemSeparatorComponent={() => (
        <View style={styles.separatorFrame}>
          <View style={styles.separator} />
        </View>
      )}
      ListEmptyComponent={
        error ? (
          <ErrorState what="your notifications" error={error} onRetry={() => void refresh()} retrying={loading} />
        ) : (
          <EmptyState
            title="No notifications yet"
            subtitle="New bets, live picks, line moves on bets you track, and replies to your feedback land here, even when push is off. They stay for 30 days."
          />
        )
      }
      ListFooterComponent={<BetslipBarSpacer />}
    />
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: colors.bg },
  content: { padding: spacing.lg, paddingBottom: spacing.xl },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg },
  toolbarText: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    marginBottom: spacing.xs,
  },
  readAll: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    minHeight: 44,
    paddingHorizontal: spacing.xs,
  },
  readAllText: {
    fontSize: font.size.body,
    color: colors.tint,
    fontWeight: font.weight.semibold,
  },
  sectionTitle: {
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    fontWeight: font.weight.semibold,
    textTransform: 'uppercase',
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: 'row',
    backgroundColor: colors.bgCard,
    paddingVertical: spacing.md,
    paddingRight: spacing.lg,
    minHeight: 44,
  },
  rowFirst: { borderTopLeftRadius: radii.md, borderTopRightRadius: radii.md },
  rowLast: { borderBottomLeftRadius: radii.md, borderBottomRightRadius: radii.md },
  dotSlot: { width: 24, alignItems: 'center', paddingTop: 6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.tint },
  rowBody: { flex: 1 },
  rowTop: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
  title: {
    flex: 1,
    fontSize: font.size.body,
    color: colors.textPrimary,
    fontWeight: font.weight.regular,
  },
  titleUnread: { fontWeight: font.weight.bold },
  time: { fontSize: font.size.caption, color: colors.textTertiary, paddingTop: 2 },
  body: {
    marginTop: 2,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    lineHeight: 18,
  },
  separatorFrame: { backgroundColor: colors.bgCard },
  separator: {
    height: StyleSheet.hairlineWidth,
    backgroundColor: colors.separator,
    marginLeft: 24,
  },
  empty: { alignItems: 'center', paddingTop: spacing.xxl * 2, paddingHorizontal: spacing.xl, gap: spacing.sm },
  emptyTitle: { fontSize: font.size.headline, fontWeight: font.weight.semibold, color: colors.textPrimary },
  emptyBody: { fontSize: font.size.footnote, color: colors.textSecondary, textAlign: 'center', lineHeight: 18 },
});
