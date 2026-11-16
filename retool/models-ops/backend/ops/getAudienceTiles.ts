type AudienceRow = {
  subscribers_active: string
  subscribers_total: string
  push_devices: string
  linked_books: string
  feedback_open: string
  discord_posts_7d: string
  discord_posts_total: string
}

export default async function (_req: { params: Record<string, never>; user: User }) {
  const result = await supabase.query<AudienceRow>(`
    SELECT
      (SELECT COUNT(*) FROM subscriptions WHERE status IN ('active','trialing')) AS subscribers_active,
      (SELECT COUNT(*) FROM subscriptions)                             AS subscribers_total,
      (SELECT COUNT(*) FROM device_push_tokens WHERE enabled)          AS push_devices,
      (SELECT COUNT(*) FROM linked_sportsbook_accounts)                AS linked_books,
      (SELECT COUNT(*) FROM feedback_threads WHERE status <> 'closed') AS feedback_open,
      (SELECT COUNT(*) FROM push_sent WHERE kind LIKE 'discord%'
         AND sent_at::timestamptz > NOW() - interval '7 days')         AS discord_posts_7d,
      (SELECT COUNT(*) FROM push_sent WHERE kind LIKE 'discord%')      AS discord_posts_total
  `)
  return result.data[0] ?? null
}
