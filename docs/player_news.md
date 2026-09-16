# Player news — the "Recent News" sheet on the prop screens

**What it is.** A newspaper icon in the top right of a prop player's screens.
Tapping it opens a sheet of that player's recent notes, newest first: the date,
the headline, what happened, and — for providers that carry one — the ANALYSIS
paragraph that says what it means for his workload.

**Why.** A player prop is a bet on ONE person, and what moves it most often is a
sentence, not a number: *"on a 75-pitch limit"*, *"scratched with hamstring
tightness"*, *"moved up to leadoff"*. The pick screen showed the line, the edge,
the form chart and the matchup context, and nothing that reads like that.
Asked for by Matt on 2026-08-30 off a screenshot of another app's RotoWire-powered
sheet: *"If you're on a prop player it should have a new icon on the top right to
click on recent news for that player."*

---

## STATUS 2026-09-16: the sheet has been EMPTY since it shipped

**`player_news` holds zero rows and always has.** The ingest step ran ~90 times
a day from the day it shipped and `pipeline_log` recorded `success` on every
single one. The sheet's icon hides itself when a player has no news, so this
reads in the app as "nobody has any news, ever" rather than as a fault.

**Cause: the feed is on the one ESPN host that 403s this worker.** Measured in
`api_call_log`, 30 days to 2026-09-16:

| host | calls | status |
|---|---|---|
| `site.api.espn.com` (source `pipeline`) | **6,084** | **403, every one — never a 200** |
| `sports.core.api.espn.com` | 974,931 | 200 |

The 403s are our news calls specifically — `/apis/site/v2/sports/*/news?limit=50`,
89 per league feed in the last two days, most recent 10:15 UTC on 2026-09-16.
The only 200s on `site.api` in that window are 25 `ncaaf-live` calls on
2026-09-12, from the loop documented as running on Matt's **residential**
machine, which is consistent with the block being on the worker's IP.

This is not new information to the project — `ncaaf_live/feeds/cfbd_scoreboard.py`
and `nfl/live_model/feeds/espn_core.py` both exist *because* `site.api` has 403'd
the worker since 2026-08-05, and injuries, WNBA results and NFL live state were
all ported to `sports.core`. **This ingestor was built on the dead host a month
after the block, and nothing caught it because it reported success.**

### Why it stayed invisible, and what changed

Every fetch is a deliberate quiet zero — a news outage must not fail the pass it
runs in — so by the time the step saw an empty list, the 403 was gone. An empty
list from a blocked host and an empty list from a quiet Tuesday were the same
value. **Fixed 2026-09-16:** the ingest now tallies transport outcomes and, when
*every* call failed, returns `feed_dead` with the reason and the step FAILS.
`refresh_pass_steps` CRITs on a step failing in all three recent passes and the
ops alerter posts it once, throttled, with a recovery message. A partial failure
is a coverage gap, not an outage, and deliberately does not trip it.

### OPEN — needs Matt: where the news actually comes from

The fix makes the outage loud; it does **not** restore the feature, and the next
pass will now report `player-news-refresh` as failed until the source changes.
Picking the replacement is a call to make, not a guess to ship:

1. **Port to `sports.core.api.espn.com`** — the host that already serves this
   worker a million calls a week. Whether core exposes an equivalent *news*
   resource, and in what shape, **could not be verified from the dev sandbox**:
   ESPN is blocked there too (proxy 403, WebFetch `EGRESS_BLOCKED`), there is no
   Railway MCP in that session and no `DATABASE_URL` to queue a worker probe.
   Probing ESPN from fresh IPs is what got this project blocked before, so this
   wants one deliberate probe from the worker, not a speculative parser.
2. **A licensed feed** (RotoWire / RotoBaller / SportsDataIO) — the providers
   table below. `PLAYER_NEWS_PROVIDER` and the `analysis` column exist so one
   drops in behind the same table and the same sheet.
3. **Drop the feature** and remove the icon, rather than ship a sheet that is
   empty by construction.

## The provider question

The screenshot's sheet is **RotoWire**, which is licensed content — that is what
"Powered by ROTOWIRE" means, and it is why the notes are one-per-player with a
separate analysis paragraph. We do not have that licence, so the provider is a
**setting**, not a hard-code:

| Provider | Cost | What it gives | Status |
|---|---|---|---|
| `espn` | Free, no key | ARTICLES — headline, summary, link — tagged with the players they are about | **Shipped, the default** |
| RotoWire | Licensed (contact syndication) | ~250 player notes/day per major sport, with ANALYSIS | Available if Matt wants it |
| RotoBaller | Licensed, advertised as low-cost | 50–150 notes/day, NFL/MLB/NBA/NHL/PGA/MMA/CFB | Available |
| SportsDataIO | Licensed, commercial agreement | `News`, `NewsByDate`, `NewsByPlayerID` per sport | Available |

ESPN was chosen for v1 because it is free, needs no key, and reuses the hidden
API the injury ingestor already reads — so the feature ships and can be judged
on real usage before anyone signs a contract. **Its limitation is coverage, not
correctness**: the league feed is ~10 stories, a team feed ~10 more, so a
storyline player is well covered and a middle reliever may have nothing. The
sheet's icon hides itself when there is nothing, so that reads as "no news"
rather than as a broken button.

Swapping in a paid feed is: write a function returning `NewsItem`s, name it in
`PROVIDERS` in `data/ingestors/player_news_ingestor.py`, set
`PLAYER_NEWS_PROVIDER` in Railway. The table, the sheet, the icon and the
`analysis` block are already shaped for it — nothing else changes.

---

## The pieces

| Piece | Where |
|---|---|
| Table | `player_news` (`data/migrations/add_player_news.sql`, registered in `data/view_migrations.py` so it self-applies) |
| Ingestor | `data/ingestors/player_news_ingestor.py` |
| Config | `config.PLAYER_NEWS_*`, `config.ESPN_NEWS_PATHS`, `config.REFRESH_PLAYER_NEWS_MAX_AGE_MIN` |
| Pipeline | `run_pipeline.py --step player-news` (daily) / `player-news-refresh` (intraday, in `scripts/refresh_pass.sh`) |
| App query | `fetchPlayerNews` in `mobile/src/lib/queries.ts` |
| App hook | `mobile/src/hooks/usePlayerNews.ts` |
| App UI | `PlayerNewsButton` (the icon + dot) → `PlayerNewsSheet` |
| Screens | `PlayerStatsScreen` (header, top right) and `PickDetailScreen` (prop picks only) |
| Tests | `tests/test_player_news_ingestor.py` |

## Storage shape

One row per **(source item, player)**. An article naming six players writes six
rows; a one-note-per-player feed writes one. Both read identically back out.

Every row carries two keys on purpose:

* `player_id` — OUR id, the one on picks and the game logs. NULL when the feed
  names someone we have never logged.
* `player_key` — `normalize_player_name(player_name)`, always present.

That second key is the accented-name lesson applied before it could bite:
`data/name_match.py` exists because an exact-string join on `player_name` cost
~9% of every MLB slate its prop prices (session 148). The app prefers the id and
falls back to the key, and a name two players share resolves to **no id** rather
than the wrong one — both stay readable by key.

## The ESPN call budget

ESPN has IP-blocked this worker twice (sessions 112, 115), so this is
deliberately frugal:

* one league feed per sport per run;
* at most `PLAYER_NEWS_MAX_TEAM_FETCHES` (default 12) team feeds, spent only on
  teams that actually have a player-prop pick today;
* the intraday step is gated on a **max age**
  (`REFRESH_PLAYER_NEWS_MAX_AGE_MIN`, default 60), not a cadence — the same
  shape as the injury and weather refreshes, so ~42 passes a day cannot become
  42 sweeps.

Retention is `PLAYER_NEWS_RETENTION_DAYS` (default 21). This table is a cache of
a feed we can always re-read; nothing in it is irreplaceable paid data, so the
§1b "extracted data belongs in Supabase" rule is satisfied by the table existing
and the pruning is safe.

## Running it by hand

```bash
python -m data.ingestors.player_news_ingestor              # every configured sport
python -m data.ingestors.player_news_ingestor --sport MLB
python run_pipeline.py --step player-news
```
