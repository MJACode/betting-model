import React, { useCallback, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import { useFeedback } from '@/hooks/useFeedback';
import { showToast } from '@/components/Toast';
import { SUPPORT_EMAIL, openFeedback } from '@/lib/socialLinks';
import {
  FEEDBACK_CATEGORIES,
  MAX_FEEDBACK_CHARS,
  feedbackErrorMessage,
  relativeTime,
  statusLabel,
  validateFeedback,
  type FeedbackCategory,
  type FeedbackThread,
} from '@/lib/feedbackHelpers';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Nav = NativeStackNavigationProp<RootStackParamList>;

/**
 * Feedback home: write something, and see the conversations you've already had.
 *
 * This replaces the old mailto: hand-off. The point of keeping it in the app is
 * the return trip — we answer in the same thread and it shows up here, so a
 * reply isn't lost in an inbox.
 */
export function FeedbackScreen() {
  const navigation = useNavigation<Nav>();
  const { threads, loading, error, loaded, refresh, submit } = useFeedback();

  const [category, setCategory] = useState<FeedbackCategory>('bug');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);

  // Refresh on every focus — coming back from a thread should show the cleared
  // unread state, and a reply may have landed while the screen was backgrounded.
  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const validation = useMemo(() => validateFeedback(body), [body]);
  const remaining = MAX_FEEDBACK_CHARS - body.trim().length;

  const send = useCallback(async () => {
    const check = validateFeedback(body);
    if (!check.ok) {
      showToast(check.reason);
      return;
    }
    setSending(true);
    try {
      const threadId = await submit(check.body, category);
      setBody('');
      showToast("Sent — we'll reply here");
      navigation.navigate('FeedbackThread', { threadId });
    } catch (err) {
      showToast(feedbackErrorMessage(err));
    } finally {
      setSending(false);
    }
  }, [body, category, navigation, submit]);

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 96 : 0}
      >
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <Text style={styles.title}>Tell us what you think</Text>
          <Text style={styles.subtitle}>
            Bug, feature idea, or a pick that looks wrong — we read every message and reply right
            here in the app.
          </Text>

          <View style={styles.card}>
            <Text style={styles.cardLabel}>What's this about?</Text>
            <View style={styles.chipRow}>
              {FEEDBACK_CATEGORIES.map((c) => {
                const active = c.key === category;
                return (
                  <Pressable
                    key={c.key}
                    onPress={() => setCategory(c.key)}
                    style={[styles.chip, active && styles.chipActive]}
                  >
                    <Text style={[styles.chipText, active && styles.chipTextActive]}>{c.label}</Text>
                  </Pressable>
                );
              })}
            </View>

            <TextInput
              style={styles.input}
              value={body}
              onChangeText={setBody}
              placeholder="What happened, or what would you like to see?"
              placeholderTextColor={colors.textTertiary}
              multiline
              textAlignVertical="top"
              editable={!sending}
            />
            <View style={styles.inputFooter}>
              <Text style={styles.hint}>
                {remaining < 200 ? `${remaining} characters left` : 'Include the pick or screen if it helps.'}
              </Text>
              <Pressable
                onPress={send}
                disabled={!validation.ok || sending}
                style={[styles.sendBtn, (!validation.ok || sending) && styles.sendBtnDisabled]}
              >
                {sending ? (
                  <ActivityIndicator color={colors.textInverse} size="small" />
                ) : (
                  <Text style={styles.sendText}>Send</Text>
                )}
              </Pressable>
            </View>
          </View>

          <Text style={styles.sectionHeader}>Your conversations</Text>

          {loading && !loaded ? (
            <ActivityIndicator style={{ marginTop: spacing.lg }} color={colors.tint} />
          ) : error ? (
            <Pressable style={styles.emptyCard} onPress={refresh}>
              <Text style={styles.emptyTitle}>Couldn't load your conversations</Text>
              <Text style={styles.emptyBody}>Tap to try again.</Text>
            </Pressable>
          ) : threads.length === 0 ? (
            <View style={styles.emptyCard}>
              <Text style={styles.emptyTitle}>Nothing yet</Text>
              <Text style={styles.emptyBody}>
                Anything you send shows up here with our reply.
              </Text>
            </View>
          ) : (
            threads.map((t) => (
              <ThreadRow
                key={t.thread_id}
                thread={t}
                onPress={() => navigation.navigate('FeedbackThread', { threadId: t.thread_id })}
              />
            ))
          )}

          <Text style={styles.footnote}>
            Conversations are tied to this device, so they won't follow you to a new phone. Prefer
            email? Write to {SUPPORT_EMAIL}.
          </Text>
          <Pressable onPress={openFeedback} style={({ pressed }) => pressed && styles.pressed}>
            <Text style={styles.emailLink}>Email us instead</Text>
          </Pressable>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ThreadRow({ thread, onPress }: { thread: FeedbackThread; onPress: () => void }) {
  const unread = thread.unread_count > 0;
  return (
    <Pressable style={({ pressed }) => [styles.threadCard, pressed && styles.pressed]} onPress={onPress}>
      <View style={{ flex: 1 }}>
        <View style={styles.threadTop}>
          {unread ? <View style={styles.dot} /> : null}
          <Text style={[styles.threadSubject, unread && styles.threadSubjectUnread]} numberOfLines={1}>
            {thread.subject}
          </Text>
        </View>
        <Text style={styles.threadPreview} numberOfLines={2}>
          {thread.last_sender === 'support' ? 'Us: ' : 'You: '}
          {thread.last_body ?? ''}
        </Text>
        <Text style={styles.threadMeta}>
          {statusLabel(thread)} · {relativeTime(thread.last_message_at)}
        </Text>
      </View>
      <Ionicons name="chevron-forward" size={18} color={colors.textTertiary} />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl, gap: spacing.md },
  title: {
    fontFamily: font.family,
    fontSize: font.size.title2,
    fontWeight: font.weight.bold,
    color: colors.textPrimary,
  },
  subtitle: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: -spacing.xs,
  },
  card: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
    gap: spacing.sm,
  },
  cardLabel: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textSecondary,
  },
  chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.noneSoft,
  },
  chipActive: { backgroundColor: colors.tint },
  chipText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
  },
  chipTextActive: { color: colors.textInverse, fontWeight: font.weight.semibold },
  input: {
    minHeight: 120,
    borderRadius: radii.md,
    backgroundColor: colors.bgGrouped,
    padding: spacing.md,
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  inputFooter: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: spacing.sm,
  },
  hint: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  sendBtn: {
    backgroundColor: colors.tint,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
    minWidth: 84,
    alignItems: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendText: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
  sectionHeader: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.6,
    marginTop: spacing.sm,
    marginLeft: 2,
  },
  threadCard: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.md,
  },
  threadTop: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.tint },
  threadSubject: {
    flex: 1,
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  threadSubjectUnread: { fontWeight: font.weight.semibold },
  threadPreview: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    marginTop: 2,
  },
  threadMeta: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: 4,
  },
  emptyCard: {
    backgroundColor: colors.bgCard,
    borderRadius: radii.lg,
    padding: spacing.lg,
    alignItems: 'center',
    gap: spacing.xs,
  },
  emptyTitle: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textPrimary,
  },
  emptyBody: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textSecondary,
    textAlign: 'center',
  },
  footnote: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    marginTop: spacing.sm,
  },
  emailLink: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.tint,
    textDecorationLine: 'underline',
  },
  pressed: { opacity: 0.6 },
});
