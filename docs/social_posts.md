# Posts to @SignalBasePicks

Manual posts are rows in `social_post_queue`. The worker job
`social_post_queue` drains due rows every 5 minutes, then one queued
profile update, then at most one automated pick. It uses the same
OAuth 1.0a client and the same four Railway variables on the `worker`
service: `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`,
`X_ACCESS_TOKEN_SECRET`. There is no new secret. `RUN_X_PUBLISHER=0`
stops this drain, the pick slate, and the recaps.

Results recaps (`notify_x_results`, `notify_x_period`) are not paced by
the pick clock below. They still ledger in `push_sent` on their own kinds.

## Pick timing

`notify_x_picks` posts the same released pre-game picks as before
(`_new_signals` with Discord's ledger ignored, same order, same text).
One call confirms at most one tweet. The pipeline refresh still calls
it, and this 5-minute job calls it too. The call opens a session-mode
connection and takes `X_PICKS_LOCK` for the read, the send, and the
ledger, so those two callers cannot each send one.

A call posts only when all of these hold:

- `RUN_X_PUBLISHER` is not `0`, the four keys are set, and
  `X_POST_ALL_PICKS` is not `0` / `false` / `no` / `off`.
- The America/New_York clock is outside 1:00am inclusive through 8:00am
  exclusive. 12:35am is before this window, so a pick can still post
  then. A call inside the window posts nothing and writes nothing. The
  next call at or after 8:00am posts the next unsent pick whose game
  has not started.
- The newest `push_sent.sent_at` with `kind = 'x_pick'` is at least 10
  minutes old, or there is no such row. The newest of the last eight
  stamps is taken by parsed time. A read failure or an unreadable stamp
  posts nothing.
- The pick has no `x_pick` row yet. A pick whose `commence` is at or
  before the send time is not tweeted and is not ledgered. The call
  moves on to the next pick. A missing commence is still postable.

`push_sent` is inserted only after X confirms the tweet,
`UNIQUE(lock_key, kind)`, kind `x_pick`, `sent_at` the ET timestamp,
`message_id` the tweet id. That insert is unchanged. Discord and the
published record do not read this kind. A pick that is held or dropped
stays out of the ledger, so a later pass can still post it until the
game starts. A 429 does not ledger; the next call retries that same
pick, and the 10-minute gap does not start until a tweet is confirmed.

The set of picks is the set that clears the existing slate query. The
one pick that does not go out is one whose game has started before its
send slot.

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

## How to enqueue a post with an image

`media_urls` is a list of up to 4 https URLs. Each file must be jpeg, png,
or webp, and at most 5MB. The drain downloads the bytes and uploads them
with `POST https://api.x.com/2/media/upload` (`media_category` =
`tweet_image`), using the same OAuth 1.0a header as a tweet. No new
secret. GIF is refused.

A public Supabase Storage object URL is a valid value. This repo does not
create the bucket. Upload the card to a public bucket (for example
`social-post-media`) and paste the object URL.

One card, posted on the next drain:

```sql
INSERT INTO social_post_queue
  (thread_key, position, body, media_urls)
VALUES (
  'pick-card-2026-10-21',
  1,
  'Tonight''s card',
  ARRAY['https://PROJECT.supabase.co/storage/v1/object/public/social-post-media/pick-card.png']
);
```

`reply_to_tweet_id` is optional. Null leaves the row as it was: position 1
is a new post, and a later position replies to the previous post in the
same `thread_key`. Set it to reply to some other tweet. The id is the
numeric status id, up to 19 digits.

```sql
INSERT INTO social_post_queue
  (thread_key, position, body, media_urls, reply_to_tweet_id)
VALUES (
  'pick-card-reply-2026-10-21',
  1,
  'The card from last night',
  ARRAY['https://PROJECT.supabase.co/storage/v1/object/public/social-post-media/pick-card.png'],
  '1234567890123456789'
);
```

From the worker, one image on one post (more than one `--body-file` cannot
carry `--media-url`; put those images on in SQL):

```bash
python -m tracking.social_posts --enqueue \
  --thread-key pick-card-2026-10-21 \
  --body-file card.txt \
  --media-url 'https://PROJECT.supabase.co/storage/v1/object/public/social-post-media/pick-card.png' \
  --reply-to 1234567890123456789
```

That inserts and does not post.

After each successful upload the drain writes that id into `media_ids` and
commits before the tweet. A later pass uploads only indexes that do not
already have an id. If an upload fails, the row is `failed`, `error` says
why, and the tweet is not created — the text does not go out without the
image. A 429 from the upload or the image host puts the row back to
`queued` and stops the pass. Do not clear `media_ids` when you requeue.

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
- More than 4 images, a non-https URL, or a file that is not jpeg, png, or
  webp is `failed`. Nothing is tweeted.
- An image that fails to download or upload is `failed`. The tweet is not
  sent without the image.
- A row that already has a `tweet_id` is not uploaded again.

To send a `failed` or `uncertain` row again, check the account first, then:

```sql
UPDATE social_post_queue
   SET status = 'queued', error = NULL, claimed_at = NULL
 WHERE id = 123
   AND status IN ('failed', 'uncertain')
   AND tweet_id IS NULL;
```

Leave `media_ids` alone. Those ids are already uploaded. Clearing them
uploads the same images again; it does not change the "one tweet" rule,
but it is wasted work and the row does not need it.

## Profile

The same 5-minute job applies queued rows in `social_profile_update` after
it drains posts. It does not tweet. The call is
`POST https://api.x.com/1.1/account/update_profile.json` with form fields
`name`, `description`, and `url`, signed with the same OAuth 1.0a header
and the same four `X_*` variables. Form fields are part of the signature.
`RUN_X_PUBLISHER=0` leaves the row `queued`.

A row is claimed with `UPDATE ... WHERE status = 'queued'` before the
request. A second drain does not send it. An HTTP 4xx, including 429, is
`failed` and is not retried. A timeout or a 5xx is `failed` and is not
retried either. `response` stores X's body. `error` stores the failure.
`applied_at` is set only when X accepted the update.

The migration seeds one row, and only when the table has no row yet. A
later pass returns before that insert, so a deleted row is not put back.
The seeded name is 30 characters and the description is 156, so neither
was trimmed. X's limits are 50 and 160. The URL is the sheet, 100
characters, and it is a single-quoted literal. The worker rewrites a `?`
outside single quotes to `%s`. The first seed was in a dollar quote, so
production stored 101 characters and X answered HTTP 403, code 120:
`Account update failed: Url is too long (maximum is 100 characters).`
That row stays `failed`. The next migration queues the 100-character URL
once.

```text
name: SignalBase | Model Picks + CLV
description: Model-driven picks: NHL, NFL, CFB, NBA & more. Every posted pick graded, every closing line tracked. Full record below. Discord: discord.gg/Sge4Djj2xT · 21+
url: https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing
```

Another update, after this one has left `queued`, is a new row. The SQL
editor (the table owner) can insert it. `anon` cannot.

```sql
INSERT INTO social_profile_update (name, description, url)
VALUES (
  'SignalBase | Model Picks + CLV',
  'Model-driven picks: NHL, NFL, CFB, NBA & more. Every posted pick graded, every closing line tracked. Full record below. Discord: discord.gg/Sge4Djj2xT · 21+',
  'https://docs.google.com/spreadsheets/d/1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo/edit?usp=sharing'
);
```

A name over 50 characters or a description over 160 is refused before the
request and the row is `failed`.

## Pinning

Not available with this client. The signed call is `POST https://api.x.com/2/tweets`
(OAuth 1.0a user context, read and write). The public v2 API can pin a
List (`POST /2/users/:id/pinned_lists`). It has no pin-tweet method. After
the root post is up, `pin_status` is `unsupported` and `pin_note` has the
status URL. Pin that post by hand in the X app.
