import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import React, { useCallback, useLayoutEffect, useMemo } from 'react';
import { ActivityIndicator, Pressable, RefreshControl, SectionList, StyleSheet, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { BetslipBarSpacer } from '@/components/BetslipBarSpacer';
import { ErrorBanner } from '@/components/ErrorState';
import { readAuthUserId } from '@/hooks/useAuth';
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
    const today = inbox.rows.filter((row) => inboxSection(row.sent_at, now) === 'TODAY');
    const earlier = inbox.rows.filter((row) => inboxSection(row.sent_at, now) === 'EARLIER');
    const out: { title: string; data: InboxRow[] }[] = [];
    if (today.length) out.push({ title: 'Today', data: today });
    if (earlier.length) out.push({ title: 'Earlier', data: earlier });
    return out;
  }, [inbox.rows, now]);

  const openRow = (row: InboxRow) => {
    void inbox.markRead(row);
    const route = routeForPush(row.route);
    if (route) openPushRoute(navigation, route);
  };

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <Text style={styles.window}>Showing the last 7 days</Text>
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
          ListFooterComponent={<BetslipBarSpacer />}
          renderSectionHeader={({ section }) => (
            <Text style={styles.section}>{section.title}</Text>
          )}
          renderItem={({ item }) => <InboxListRow row={item} now={now} onPress={() => openRow(item)} />}
          contentContainerStyle={styles.list}
        />
      )}
    </SafeAreaView>
  );
}

function InboxListRow({
  row,
  now,
  onPress,
}: {
  row: InboxRow;
  now: Date;
  onPress: () => void;
}) {
  const unread = row.read_at == null;
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${unread ? 'Unread. ' : ''}${row.title}. ${row.body}`}
      style={({ pressed }) => [styles.row, pressed && { opacity: opacity.pressed }]}
    >
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
  window: {
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.xs,
    paddingBottom: spacing.sm,
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
