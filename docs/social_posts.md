# Manual posts to @SignalBasePicks

Picks and results recaps are unchanged. They still go out through
`tracking/x_publisher.py` (`notify_x_picks`, `notify_x_results`,
`notify_x_period`) on the schedules they already have, and they still
ledger in `push_sent`.

A marketing post is a row in `social_post_queue`. The worker job
`social_post_queue` drains due rows every 5 minutes. It uses the same
OAuth 1.0a client and the same four Railway variables on the `worker`
service: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
`X_ACCESS_TOKEN_SECRET`. There is no new secret. `RUN_X_PUBLISHER=0`
stops this drain as well as the slate and the recaps.

## What is already queued

The migration seeds one thread, `all-time-ledger-2026-10-20`, three posts,
status `queued`. It is Draft 1, the all-time ledger. Position 1 has `pin`
set. Position 3 has `allow_link` set because the text contains
`discord.gg`. Nothing in that migration calls X. The worker posts the
thread on the first drain after the migration has landed and the new
scheduler job is running.

## How a row gets published

1. Merge to `master`. Railway redeploys the worker.
2. The worker's view-migration pass creates `social_post_queue` and inserts
   the seed if the table was not already locked down. A later pass returns
   without inserting again.
3. Within 5 minutes, `run_social_post_queue` claims each due `queued` row,
   posts it, and stores `tweet_id` and `tweet_url`. Position 2 is a reply
   to position 1. Position 3 is a reply to position 2.
4. A second pass sees `posted` and does not send again.

To post a queued thread immediately, on the worker (the service that has
the four keys), not from a laptop that has no keys:

```bash
python -m tracking.social_posts --drain
```

Without `--drain` the same command is a dry run. It writes nothing and
does not call X.

## How to enqueue another post or thread

In the Supabase SQL editor (the table owner). `anon` and `authenticated`
cannot write this table.

One post:

```sql
INSERT INTO social_post_queue (thread_key, position, body, scheduled_at)
VALUES ('clv-receipt-2026-10-21', 1, 'text here', NOW());
```

A thread. Positions start at 1 and have no gaps. `pin` on position 1 is a
request, not a pin. `allow_link` is required on any post that contains a
URL. X bills a URL at $0.20 instead of $0.015. Leave it false otherwise.

```sql
INSERT INTO social_post_queue
  (thread_key, position, body, allow_link, pin, scheduled_at)
VALUES
  ('weekly-2026-10-27', 1, 'first post', false, true, NOW()),
  ('weekly-2026-10-27', 2, 'second post', false, false, NOW());
```

`scheduled_at` in the future waits. Status stays `queued` until the drain.

Or from the worker, one UTF-8 file per post, exact contents:

```bash
python -m tracking.social_posts --enqueue \
  --thread-key weekly-2026-10-27 \
  --pin \
  --body-file post1.txt \
  --body-file post2.txt
```

That inserts and does not post. Add `--allow-link` if a file contains a
URL. Add `--drain` only when this process should post immediately.

A `thread_key` that already has a row is refused. Use a new key.

## What the drain will not do

- It will not send a row that already has a `tweet_id`.
- It will not send a row twice. The claim is committed before the HTTP
  call. A second drain sees `posting` or `posted` and stops.
- A 429 goes back to `queued` (X did not create the tweet) and the rest of
  the pass waits.
- An HTTP 4xx is `failed`. It is not retried.
- A timeout or a 5xx is `uncertain`. It is not retried, because the tweet
  may already exist.
- A `posting` row with no tweet id whose claim is older than 10 minutes
  becomes `uncertain` and is not retried.
- A URL with `allow_link` false is `failed` and is not sent.
- A body over 280 characters is `failed`. The text is not shortened.

To send a `failed` or `uncertain` row again, check the account first, then:

```sql
UPDATE social_post_queue
   SET status = 'queued', error = NULL, claimed_at = NULL
 WHERE id = 123
   AND status IN ('failed', 'uncertain')
   AND tweet_id IS NULL;
```

## Pinning

Not available with this client. The signed call is `POST https://api.x.com/2/tweets`
(OAuth 1.0a user context, read and write). The public v2 API can pin a
List (`POST /2/users/:id/pinned_lists`). It has no pin-tweet method. After
the root post is up, `pin_status` is `unsupported` and `pin_note` has the
status URL. Pin that post by hand in the X app.
