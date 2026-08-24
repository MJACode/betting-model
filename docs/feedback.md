# In-app feedback — reading it and replying

The mobile Settings → **Send feedback** row used to open a `mailto:`. It now
opens an in-app conversation: the user writes, we answer, and the answer appears
in their app (plus a push notification). This doc is the support side.

## Where it lives

| Piece | What |
|---|---|
| `feedback_threads` | one row per conversation, owned by a `device_id` (a per-install UUID; `user_id` too once auth is on). Carries `status`, `subject`, `app_version`, `platform`. |
| `feedback_messages` | the turns. `sender` is `'user'` or `'support'`. |
| Mobile | `screens/FeedbackScreen.tsx` (composer + your conversations), `screens/FeedbackThreadScreen.tsx` (one conversation), `hooks/useFeedback.ts`, `lib/feedback.ts` (RPCs), `lib/feedbackHelpers.ts` (pure). |
| Push | `tracking/push_notifier.notify_feedback_replies()` — runs in the hourly push step, ledgered per message. |
| Schema | `data/migrations/add_feedback_threads.sql` |

`status` is: **open** = the ball is with us (new, or the user replied to our
answer), **answered** = we replied last, **closed** = done.

## Reading it

Everything below runs as the service role — the Supabase SQL editor, or Claude
mobile with the Supabase MCP. Paste these into the Claude-mobile project
instructions if you want "any new feedback?" to work.

```sql
-- What needs an answer, oldest first
SELECT t.id, t.status, t.category, t.subject, t.app_version, t.platform,
       t.last_message_at,
       (SELECT count(*) FROM feedback_messages m WHERE m.thread_id = t.id) AS turns
FROM feedback_threads t
WHERE t.status = 'open'
ORDER BY t.last_message_at;
```

```sql
-- Read one conversation in full
SELECT sender, body, created_at
FROM feedback_messages
WHERE thread_id = 42
ORDER BY id;
```

## Replying

One call. It writes the message, flips the thread to `answered`, and bumps
`last_message_at` — so a thread can't end up answered-but-still-listed-as-open:

```sql
SELECT feedback_reply(42, 'Thanks — the totals model is paused right now, which is why those look off. Details in Settings → How this works.');
```

Close it out instead of just answering (nothing more expected):

```sql
SELECT feedback_reply(42, 'Shipped in this week''s update — thanks again!', true);
```

The user sees the reply next time they open the app, and gets a push within the
hour if they've enabled notifications. If they reply again the thread flips back
to `open`.

**`feedback_reply` is service-role only.** It is deliberately not granted to
`anon`/`authenticated` — that grant is the only thing stopping a client posting
a message that renders as coming from us. Note that revoking from `PUBLIC` is
*not* enough: Supabase's default privileges name `anon` and `authenticated`
explicitly, so they must be revoked by name (this was caught live during the
build — anon could post as support until it was).

## How access works (read before touching RLS)

The app uses the anon key with **no session**, so a row-level policy has no
identity to filter on — a `USING (true)` SELECT policy would expose every user's
feedback to anyone holding the public key. So:

* both tables have RLS on and **no policies at all**,
* anon's default table grants are **revoked**,
* the only way in is the device-scoped `SECURITY DEFINER` RPCs, each of which
  requires the caller to present the `device_id` that owns the row.

That is the same trust model `tracked_bets` and the SharpSports link already
use: the per-install UUID acts as a bearer token. It is unguessable, but it is
not an account — **feedback is tied to a device, not a person**, so it does not
follow a user to a new phone, and the Feedback screen says so. Wiring `user_id`
(already a column) to real accounts is the upgrade once `AUTH_ENABLED` is on.

| RPC | Callable by | Purpose |
|---|---|---|
| `feedback_submit(device, message, category, app_version, platform, thread_id, user_id)` | anon | open a conversation, or add a turn to one this device owns |
| `feedback_threads_for_device(device)` | anon | this device's conversations + unread counts |
| `feedback_messages_for_thread(device, thread_id)` | anon | the turns (ownership-checked) |
| `feedback_mark_read(device, thread_id)` | anon | clear this device's unread badge |
| `feedback_unread_count(device)` | anon | scalar for the Settings badge |
| `feedback_reply(thread_id, body, close)` | **service role only** | our answer |

Abuse guards live in `feedback_submit`, since none of this is authenticated:
4,000 characters per message, 20 messages per device per hour, 25 open
conversations per device. Unknown categories are coerced to `other`.

## What the security advisor says (expected)

Running `get_advisors(security)` after this shipped produces, for feedback:

* 2 × INFO `rls_enabled_no_policy` on `feedback_threads` / `feedback_messages` —
  **intended**, that is the design above (RLS on, no policies, RPC-only). Two
  dozen other internal tables sit in the same state.
* 10 × WARN `anon_security_definer_function_executable` /
  `authenticated_...` for the five device-scoped RPCs — **intended**, that is how
  the app reaches its own data with no session.
* **`feedback_reply` is NOT in that list.** If it ever appears there, the support
  function has become callable from the app: revoke it from `anon` and
  `authenticated` immediately.

The two ERROR-level `rls_disabled_in_public` notices (`nfl_odds_history`,
`nfl_pick_status_history`) are pre-existing and unrelated — see session 125.

## Notes

* The old, empty `feedback` table (message/app_version/created_at, from the
  website era) is unrelated and unused. Left in place, nothing reads it.
* Push delivery still depends on the one-time native push setup in
  `docs/push_notifications.md`. Until a device has registered a token, replies
  are still delivered — they just appear when the user next opens the app, with
  no buzz.
* Email hasn't gone away: the Feedback screen keeps an "Email us instead" link.
