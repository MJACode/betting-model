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
