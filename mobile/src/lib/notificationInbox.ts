/**
 * Network layer for the notifications inbox.
 *
 * Everything goes through the device-keyed SECURITY DEFINER functions in
 * data/migrations/notification_inbox_2026_11_14.sql. The tables are not
 * readable with the anon key; the per-install device id scopes every call,
 * the same trust model as feedback.
 */

import { supabase } from '@/lib/supabase';
import type { InboxItem } from '@/lib/notificationInboxHelpers';

export async function fetchInbox(deviceId: string): Promise<InboxItem[]> {
  const { data, error } = await supabase.rpc('notification_inbox_for_device', {
    p_device_id: deviceId,
  });
  if (error) throw error;
  return ((data ?? []) as unknown as InboxItem[]).map((r) => ({
    ...r,
    id: Number(r.id),
    body: r.body ?? '',
    is_read: Boolean(r.is_read),
  }));
}

export async function fetchInboxUnreadCount(deviceId: string): Promise<number> {
  const { data, error } = await supabase.rpc('notification_unread_count', {
    p_device_id: deviceId,
  });
  if (error) throw error;
  return Number(data ?? 0) || 0;
}

export async function markInboxRead(deviceId: string, id: number): Promise<void> {
  const { error } = await supabase.rpc('notification_mark_read', {
    p_device_id: deviceId,
    p_notification_id: id,
  });
  if (error) throw error;
}

export async function markInboxAllRead(deviceId: string): Promise<void> {
  const { error } = await supabase.rpc('notification_mark_all_read', {
    p_device_id: deviceId,
  });
  if (error) throw error;
}
