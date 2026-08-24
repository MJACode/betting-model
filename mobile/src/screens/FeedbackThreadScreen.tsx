import React, { useCallback, useEffect, useRef, useState } from 'react';
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
import { useFocusEffect, useRoute } from '@react-navigation/native';
import type { RouteProp } from '@react-navigation/native';

import { useFeedback } from '@/hooks/useFeedback';
import { showToast } from '@/components/Toast';
import {
  feedbackErrorMessage,
  relativeTime,
  validateFeedback,
  type FeedbackCategory,
  type FeedbackMessage,
} from '@/lib/feedbackHelpers';
import { colors, font, radii, spacing } from '@/lib/theme';
import type { RootStackParamList } from '@/types';

type Route = RouteProp<RootStackParamList, 'FeedbackThread'>;

/**
 * One conversation. Your messages on the right, ours on the left.
 *
 * Opening the thread marks it read on THIS device (feedback_mark_read is
 * device-scoped), which is what clears the Settings badge.
 */
export function FeedbackThreadScreen() {
  const { params } = useRoute<Route>();
  const threadId = params.threadId;
  const { threads, submit, markRead, loadMessages } = useFeedback();

  const [messages, setMessages] = useState<FeedbackMessage[]>([]);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [reply, setReply] = useState('');
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<ScrollView>(null);

  const thread = threads.find((t) => t.thread_id === threadId);

  const load = useCallback(async () => {
    try {
      setMessages(await loadMessages(threadId));
      setFailed(false);
    } catch (err) {
      console.warn('[feedback] thread load failed', err);
      setFailed(true);
    } finally {
      setLoading(false);
    }
  }, [loadMessages, threadId]);

  // Re-read on focus so a reply that landed while we were elsewhere shows up.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  // Mark read once per visit, after the messages are actually on screen.
  useEffect(() => {
    if (!loading && !failed) void markRead(threadId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, failed, threadId]);

  const send = useCallback(async () => {
    const check = validateFeedback(reply);
    if (!check.ok) {
      showToast(check.reason);
      return;
    }
    setSending(true);
    try {
      await submit(check.body, (thread?.category as FeedbackCategory) ?? 'other', threadId);
      setReply('');
      await load();
      requestAnimationFrame(() => scrollRef.current?.scrollToEnd({ animated: true }));
    } catch (err) {
      showToast(feedbackErrorMessage(err));
    } finally {
      setSending(false);
    }
  }, [load, reply, submit, thread?.category, threadId]);

  const canSend = validateFeedback(reply).ok && !sending;

  return (
    <SafeAreaView style={styles.container} edges={['bottom']}>
      <KeyboardAvoidingView
        style={{ flex: 1 }}
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        keyboardVerticalOffset={Platform.OS === 'ios' ? 96 : 0}
      >
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: false })}
        >
          {thread ? <Text style={styles.subject}>{thread.subject}</Text> : null}

          {loading ? (
            <ActivityIndicator style={{ marginTop: spacing.xl }} color={colors.tint} />
          ) : failed ? (
            <Pressable style={styles.errorCard} onPress={load}>
              <Text style={styles.errorText}>Couldn't load this conversation. Tap to retry.</Text>
            </Pressable>
          ) : (
            messages.map((m) => <Bubble key={m.message_id} message={m} />)
          )}

          {!loading && !failed && messages.length > 0 && thread?.status !== 'answered' ? (
            <Text style={styles.awaiting}>
              We haven't replied yet — you'll get a notification here when we do.
            </Text>
          ) : null}
        </ScrollView>

        <View style={styles.composer}>
          <TextInput
            style={styles.replyInput}
            value={reply}
            onChangeText={setReply}
            placeholder="Reply…"
            placeholderTextColor={colors.textTertiary}
            multiline
            editable={!sending}
          />
          <Pressable
            onPress={send}
            disabled={!canSend}
            style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
          >
            {sending ? (
              <ActivityIndicator color={colors.textInverse} size="small" />
            ) : (
              <Text style={styles.sendText}>Send</Text>
            )}
          </Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function Bubble({ message }: { message: FeedbackMessage }) {
  const mine = message.sender === 'user';
  return (
    <View style={[styles.bubbleRow, mine ? styles.rowMine : styles.rowTheirs]}>
      <View style={[styles.bubble, mine ? styles.bubbleMine : styles.bubbleTheirs]}>
        {!mine ? <Text style={styles.sender}>Signalbase</Text> : null}
        <Text style={[styles.body, mine && styles.bodyMine]}>{message.body}</Text>
        <Text style={[styles.when, mine && styles.whenMine]}>{relativeTime(message.created_at)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.bgGrouped },
  content: { padding: spacing.lg, paddingBottom: spacing.md, gap: spacing.sm },
  subject: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.textTertiary,
    marginBottom: spacing.xs,
  },
  bubbleRow: { flexDirection: 'row' },
  rowMine: { justifyContent: 'flex-end' },
  rowTheirs: { justifyContent: 'flex-start' },
  bubble: { maxWidth: '85%', borderRadius: radii.lg, padding: spacing.md, gap: 4 },
  bubbleMine: { backgroundColor: colors.tint, borderBottomRightRadius: radii.sm },
  bubbleTheirs: { backgroundColor: colors.bgCard, borderBottomLeftRadius: radii.sm },
  sender: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    fontWeight: font.weight.semibold,
    color: colors.textTertiary,
  },
  body: {
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  bodyMine: { color: colors.textInverse },
  when: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
  },
  whenMine: { color: '#FFFFFFB0' },
  awaiting: {
    fontFamily: font.family,
    fontSize: font.size.caption,
    color: colors.textTertiary,
    textAlign: 'center',
    marginTop: spacing.sm,
  },
  errorCard: {
    backgroundColor: colors.avoidSoft,
    borderRadius: radii.md,
    padding: spacing.md,
  },
  errorText: {
    fontFamily: font.family,
    fontSize: font.size.footnote,
    color: colors.avoid,
    textAlign: 'center',
  },
  composer: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    gap: spacing.sm,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.separator,
    backgroundColor: colors.bgCard,
  },
  replyInput: {
    flex: 1,
    maxHeight: 120,
    minHeight: 40,
    borderRadius: radii.md,
    backgroundColor: colors.bgGrouped,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontFamily: font.family,
    fontSize: font.size.body,
    color: colors.textPrimary,
  },
  sendBtn: {
    backgroundColor: colors.tint,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.sm,
    minWidth: 72,
    alignItems: 'center',
  },
  sendBtnDisabled: { opacity: 0.4 },
  sendText: {
    fontFamily: font.family,
    fontSize: font.size.body,
    fontWeight: font.weight.semibold,
    color: colors.textInverse,
  },
});
