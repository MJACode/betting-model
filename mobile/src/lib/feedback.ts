/**
 * Network layer for in-app feedback.
 *
 * Everything goes through the device-scoped SECURITY DEFINER RPCs (see
 * data/migrations/add_feedback_threads.sql). The tables themselves are not
 * readable or writable with the anon key: the device_id passed here is what
 * scopes every call to this install's own conversations.
 *
 * `sender: 'support'` can only be written by the service role, so nothing the
 * app does can forge a reply from us.
 */

import { Platform } from 'react-native';

import { supabase } from '@/lib/supabase';
import { APP_VERSION } from '@/lib/socialLinks';
import type { FeedbackCategory, FeedbackMessage, FeedbackThread } from '@/lib/feedbackHelpers';

/** Open a new conversation, or add a turn to one this device already owns. */
export async function submitFeedback(params: {
  deviceId: string;
  message: string;
  category?: FeedbackCategory;
  threadId?: number | null;
  userId?: string | null;
}): Promise<number> {
  const { data, error } = await supabase.rpc('feedback_submit', {
    p_device_id: params.deviceId,
    p_message: params.message,
    p_category: params.category ?? 'other',
    p_app_version: APP_VERSION,
    p_platform: `${Platform.OS} ${String(Platform.Version)}`,
    p_thread_id: params.threadId ?? null,
    p_user_id: params.userId ?? null,
  });
  if (error) throw error;
  return data as unknown as number;
}

export async function fetchFeedbackThreads(deviceId: string): Promise<FeedbackThread[]> {
  const { data, error } = await supabase.rpc('feedback_threads_for_device', {
    p_device_id: deviceId,
  });
  if (error) throw error;
  return (data ?? []) as unknown as FeedbackThread[];
}

export async function fetchFeedbackMessages(
  deviceId: string,
  threadId: number,
): Promise<FeedbackMessage[]> {
  const { data, error } = await supabase.rpc('feedback_messages_for_thread', {
    p_device_id: deviceId,
    p_thread_id: threadId,
  });
  if (error) throw error;
  return (data ?? []) as unknown as FeedbackMessage[];
}

/** Clears the unread badge for one conversation on THIS device only. */
export async function markFeedbackRead(deviceId: string, threadId: number): Promise<void> {
  const { error } = await supabase.rpc('feedback_mark_read', {
    p_device_id: deviceId,
    p_thread_id: threadId,
  });
  if (error) throw error;
}

export async function fetchFeedbackUnreadCount(deviceId: string): Promise<number> {
  const { data, error } = await supabase.rpc('feedback_unread_count', {
    p_device_id: deviceId,
  });
  if (error) throw error;
  return (data as unknown as number) ?? 0;
}
