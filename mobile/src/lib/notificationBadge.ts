/**
 * The app-icon badge and the delivered notifications, from the same unread
 * count the bell uses.
 *
 * expo-notifications assigns the OS identifier. The producer puts the inbox
 * row's notification_id on the payload as data.inboxId, and this matches
 * that. Only those notifications are dismissed. A number the OS drew in red
 * on the icon is set and cleared from the unread count.
 */

export interface PresentedNotification {
  request: {
    identifier: string;
    content: { data?: Record<string, unknown> | null };
  };
}

export interface BadgeNotifications {
  setBadgeCountAsync(count: number): Promise<boolean>;
  getPresentedNotificationsAsync(): Promise<PresentedNotification[]>;
  dismissNotificationAsync(identifier: string): Promise<void>;
}

export async function applyUnreadBadge(
  count: number,
  notifications: BadgeNotifications,
): Promise<void> {
  try {
    await notifications.setBadgeCountAsync(Math.max(0, count));
  } catch (err) {
    console.warn('[push] could not set the app badge', err);
  }
}

export function inboxIdOf(notification: PresentedNotification): string | null {
  const data = notification.request.content.data;
  const id = data && data.inboxId;
  return typeof id === 'string' && id.length > 0 ? id : null;
}

/** Dismiss delivered Signalbase notifications whose inbox id is in `ids`. */
export async function dismissInboxNotifications(
  ids: string[],
  notifications: BadgeNotifications,
): Promise<void> {
  if (ids.length === 0) return;
  const wanted = new Set(ids);
  try {
    const presented = await notifications.getPresentedNotificationsAsync();
    for (const notification of presented) {
      const id = inboxIdOf(notification);
      if (id != null && wanted.has(id)) {
        await notifications.dismissNotificationAsync(notification.request.identifier);
      }
    }
  } catch (err) {
    console.warn('[push] could not dismiss delivered notifications', err);
  }
}
