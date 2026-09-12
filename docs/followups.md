# Follow-ups

> **The durable backlog.** Anyone can add to it any time, and items are cleared
> in ordinary working sessions — pick one up when a session has room.
>
> **There is no longer an agent that does this.** Janitor was retired
> 2026-09-03 after four runs finished SUCCEEDED having landed nothing at all;
> it had no way to get work out of its sandbox. `docs/agents_contract.md` has
> the measurements and the routes that were tried, so nobody rebuilds it.
>
> **Why a file:** a task list that lives only in a chat is gone the moment the
> session ends. Four small fixes below were flagged in three separate sessions
> and never done, because each time they lost to a larger ask and nothing
> carried them forward. Same reasoning as CLAUDE.md §1b. That reasoning is
> UNCHANGED by the retirement — the file was always the memory; the agent was
> only ever one possible reader of it.
>
> **Format:** one `## Item` per task. `[needs-decision]` means blocked on a
> human. Tick with `- [x]` and leave it in place for one week so a reader can
> see what recently changed, then delete.

---

## [ ] Re-measure the NFL prop lead curve inside 24 h on the 2026 hourly polls (October)

mike, 2026-09-11: the ceiling STAYS at 24 h (`config.NFL_PROP_MAX_LEAD_HOURS`)
and is re-measured in October. The 2023-25 evidence is one snapshot a day at
13:55 UTC, so its "lead bands" are kickoff-slot proxies
(`docs/nfl_prop_offset_evidence.md`, correction banner): last 4 h +2.96% on
450 (spans zero), 4-8 h +9.30% on 971 (clear), Saturday-morning read of Sunday
games +17.45% on 173 (clear), the separate t24 series +2.12% on 187. Production
has polled hourly since 2026-09-06 (`NFL_PROP_WINDOW_HOURS` 240), so by
mid-October there are ~5 weeks of settled `nfl_prop_market` propositions at
every hour inside 24 h. Grade the rule by the hour the soft quote was taken
(`scripts/nfl_prop_two_sharps.py --by-lead` on the 2026 rows, or a per-hour
variant) and decide 12 / 24 / 36 on that, not on the slot proxies. The open
question is whether to WIDEN to 36 h to reach the Saturday-morning band.

## [ ] The replay and the cut grid pair quotes without production's stale-quote guard

Production has the guard: `models/live_scorer._get_live_dk_odds` declines an
in-play quote whose `snapshot_at` (the market's own `last_update`) predates
the first sight of the game's current score (`_score_changed_at`,
`data/live_quote_guard.quote_predates_score`, tolerance 0). The REPLAY and
the cut sweep (`scripts/live_inning_gate_replay._pair`) pair the newest price
at or before each state with only the age bound, so their "all quotes" grids
count bets production would have declined -- on 2025, 37 of the shipped
cut's 128 bets, 30-7. The sweep cache now carries `runs_moved` (the state at
the price's snapshot_at vs the candidate state), and a sweep read for
production is the FRESH-only grid. `_pair` itself should apply the same rule
so the two never diverge again; a test that a stale pair is dropped.

## [ ] [needs-decision] A calibration map for `mlb_live_total_runs`, fit on the 2025 in-play history

Fitted and measured 2026-09-10 (`scripts/live_calibration_sweep.py`,
`docs/thresholds.md` "The forward check on fresh quotes"): a = 0.8578,
b = −0.0787, helps and transfers on the 2025 date split. The re-sweep on the
calibrated probability finds NO cell that clears breakeven in both halves of
both seasons on fresh quotes; the shipped cut's own fresh record is 92 bets
at +9.5% (2025) and 21 at +3.7% (2026). `promote_external` is in place; the
cut to promote it with is mike's call (the three options are in the
2026-09-10 session entry). Landing order: promote the map first (the lane
goes quiet at 0.675 < 0.72), then the config change; a running loop picks
the map up at its next start (`_CAL_CACHE` is per process, the supervisor
restarts it every 10 minutes); the app's action filter compares the RAW
probability against `min_prob`, which is looser than the decision path when
the cut is on the calibrated scale, so no BET is hidden.

## [ ] Four franchises are filed twice in `games`, and the scores sit on the SBR twin

ARI/AZ, CWS/CHW, OAK/ATH, WSH/WAS: the odds ingestor, the Stats API map and
every `live` row use the first form; the SBR CSV import files the same game
under the second, with the final score, while the live row stays unscored
(2025: 656 unscored live rows, 673 SBR rows). Consequences measured
2026-09-10: the PBP ingestor skipped every one of their games — **no CWS or
WSH game in the 2024 training corpus (81 unscored live rows each), 534 of the
priced 2025 games without plays** — fixed at the read
(`mlb_pbp_ingestor.mlb_game_final` reads the twin) and the 2025 corpus
backfilled (613 games, 46,595 plays). NOT fixed: the duplicate rows
themselves, whatever settles picks on those games, and whether the 2019–2024
PBP corpora are missing those teams' games too (`--backfill` is idempotent;
run it per season and count). Retraining on a corpus that now includes them
is a model update.

## [x] The calibrated decision never reaches player props — FIXED 2026-09-07

`DECIDE_ON_CALIBRATED_PROB` is on by default and is a **no-op in production**.
The branch is in `classify_edge` (`models/scorer.py:1124`); every model that
carries a promoted calibration map is a player prop, and props are decided in
`_make_prop_pick` (`models/scorer.py:2950`) on the RAW probability. 46 of 95
MLB prop BETs since 2026-09-01 (48%) fail their own cut on the calibrated
probability the pick already stores. Measured 2026-09-07,
`docs/mlb_volume_efficiency.md` §2.

**Done 2026-09-07 (mike).** `_make_prop_pick` now carries the branch, scoped
so a map bites only where the weekly pass endorses it (helps AND transfers) —
`data/migrations/promotions_endorsed_only_2026_09_07.sql` re-froze four maps and
demoted six. `pitcher_k` and `pitcher_hits` deliberately stay on identity until
they have 150 graded picks since their retrains (47 and 26 today);
`config.PROP_MAX_SIGNALS_PER_DAY` holds their volume down until then and comes
off with the re-promotion, ~2026-09-12 to 09-15. That is the one thing still
owed here.

## [x] An unfitted weekly refit silently disables a PROMOTED calibration map — FIXED 2026-09-07

`load_calibrations` (`models/probability_calibration.py:386`) reads
`promoted_a, promoted_b` but filters on the **candidate** `method = 'platt'`.
When the weekly pass cannot fit a model it writes `method = NULL`, and the
promoted map disappears on the next read. Measured 2026-09-07:
`mlb_prop_pitcher_k` and `mlb_prop_pitcher_hits` picks carried a distinct
`model_probability_cal` on 166/166 rows from 08-31 to 09-03, 11/43 on 09-04 and
**0/95 from 09-05 on**. `scorer.py:1120` states the intent as "only an endorsed
map bites"; the observed behaviour is that an un-endorsed refit can un-bite an
endorsed one. **Done 2026-09-07 (mike).** `load_calibrations` reads `promoted_method`,
`promote()` freezes the method and both verdicts at promotion, and `demote()`
exists. Detail: `docs/mlb_volume_efficiency.md` §2.

## [x] 40 NCAAF `games` rows since 08-28 carry an FCS visitor's Odds API name with the mascot attached - FIXED AT THE SOURCE 2026-09-07

Measured 2026-09-07 (session 253). `ncaaf_teams` is `/teams/fbs` (139
schools), so every FCS visitor is unresolved by the Odds API name resolver and
its games row keeps the mascot: `NCAAF_2026-09-05_abilene-christian-wildcats_texas-tech`
beside CFBD's `abilene-christian_texas-tech`. 48 live rows in 08-28..09-07
name a different opponent than CFBD's row for the same home team and day; 8
were the prefix bug fixed that session, the other 40 are this. The alias
mirror now grades THROUGH them (one side exact, the other an extended slug),
so picks on them settle - but five shapes it cannot bridge stay unscored:
`albany`/`ualbany`, `liu-sharks`/`long-island-university`,
`citadel-bulldogs`/`the-citadel`, `youngstown-st-penguins`/`youngstown-state`,
`southeastern-louisiana-lions`/`se-louisiana`. None carried a pick.

**Done 2026-09-07 (mike).** `ingest_ncaaf_teams` pulls `/teams` for every
classification after `/teams/fbs`; the worker job
`ncaaf-teams-all-classifications-2026-09-07` loaded it and probed the
resolver. The 40 existing rows keep their ids (picks point at them) and
settle through the alias mirror; new rows resolve at the source.

Query that found it:

```sql
WITH live AS (SELECT game_id, game_date, home_team, away_team FROM games
              WHERE sport='NCAAF' AND data_source='live' AND game_date >= '2026-08-28'),
     cfbd AS (SELECT game_id, game_date, home_team, away_team FROM games
              WHERE sport='NCAAF' AND data_source='cfbd' AND game_date >= '2026-08-27')
SELECT l.game_id, l.away_team, c.away_team, c.game_id
FROM live l JOIN cfbd c ON c.home_team = l.home_team
  AND abs(c.game_date::date - l.game_date::date) <= 1 AND c.away_team <> l.away_team;
```

## [x] Six live NCAAF picks are labelled with the wrong opponent - FIXED 2026-09-07

Same session. `pick_label` read "Indiana @ Purdue Over 45.5 (live)"; the game
was Indiana State @ Purdue, and the bet was on DK's live total for that game
(the live loop prices from the pregame line and the live state, not from team
identity). §1c protects the row as the bet of record; a DISPLAY label is not
the line or the price.

**Done 2026-09-07 (mike: "fix the labels").**
`data/migrations/ncaaf_fcs_visitor_names_2026_09_07.sql`, applied from the
worker's own pass, renames the visitor on the nine `games` rows, writes CFBD's
final onto each, and replaces the wrong name in the 27 labels on those rows that
carry it (the six BETs and the pre-game NONE rows naming the visitor; the
other 16 of 43 name only the home team) once, whole-word. Verified on the
worker's 22:30 UTC pass: 27 corrected, 0 still wrong. The Discord and
app posts that already went out under the wrong name are not rewritten.

## [x] MLB prop scorers price a game with no weather row as a 0°F game — FIXED 2026-09-10 (session 278; mike: the two picks stand, not voided)

Found 2026-09-10 (session 278) on the Gilbert / deGrom Under 6.5 K picks:
`build_pitcher_scoring_rows` leaves `temp_f` None when `game_weather` has no
row, and the scorer's `np.nan_to_num(..., nan=0.0)` turns that into a literal
0°F. Training rows 2019-2025 all carry weather (p01 ≈ 21-39°F), so the trees
read 0 as the coldest game ever seen and cut ~0.8 K off lambda. Reproduced to
four decimals. Two ways a game arrives with no row:

1. **The look-ahead pass** (`step_prop_scoring`, `GAME_SCORE_AHEAD_DAYS=7`)
   scores tomorrow, but `step_weather` fetches `run_date` only. The
   first-signal lock then keeps the evening pick over the 6am re-score.
2. **Same-day games that never get a row:** 814 of 3,971 2026 starts, skewed
   to OAK, LAA, ARI, MIL, SEA, KC, SF, COL, SD, HOU, LAD, MIN home games
   (West Coast / late starts). 72 pitcher-K BETs sit on those games. Cause
   not diagnosed.

The same builder and fill feed `pitcher_hits`, `pitcher_er`, `batter_tb`,
`batter_hr`; not measured.

**Fix shape, three parts:** (a) fetch forecast weather for every look-ahead
date, correcting `_fetch_open_meteo`'s `forecast_days = min(days_old + 2, 16)`
(tested: `forecast_days=1` returns only today for a future date; 3 covers
tomorrow); (b) SKIP a pitcher / batter whose game has no weather row rather
than zero-fill, and log it; (c) diagnose why late-start venues get no row.
Decision needed: whether the 09-10 Gilbert / deGrom picks are VOIDed under
§1c (deGrom is a dead-zone NONE at the real temperature; Gilbert stays a BET
at 0.62 / edge 0.0801). `void_picks.py` refuses a graded pick, so the option
closes at the next settle pass.

## [ ] Three phantom MLB `games` rows from April (RELABELLED 2026-09-07), and one unscored real one

Session 253 (2026-09-07). `MLB_2026-04-16_NYM_LAD`, `MLB_2026-04-17_SEA_SD`
and `MLB_2026-04-17_COL_HOU` are the 04-15 and 04-16 night games filed a
second time under their UTC date with no start time (the story is in the
session entry). Pick 661 on the first is voided; the two AVOIDs on it and the
two on SEA_SD are inert, since no final will ever land on those ids. The rows
themselves are still there, and each is a duplicate of a scored row one day
earlier. **Done 2026-09-07 (mike: "clean up the three phantom rows"):** the
four AVOIDs are voided (declared job `void-phantom-utc-avoids-2026-04-16-17`)
and the rows carry `data_source = 'duplicate_utc'`
(`data/migrations/mlb_phantom_utc_rows_2026_09_07.sql`). Not deleted, the
picks point at them; not scored, the picks post-date their games. What is
left open in this item is the 04-13 row below.

Separately, `MLB_2026-04-13_NYM_LAD` was created by the 2026-09-01 historical
backfill with no score: a real game (first pitch 02:11Z on the 14th) that the
5-day score window never reached and that carries no pick, so the settle heal
does not reach it either. A one-line extension of `_fetch_and_store_scores`
over any unscored MLB row older than the window would close it.

## [ ] The inning-gate replay misses 13 games production actually bet

`scripts/live_inning_gate_replay.py`'s own control prints it: over 2026-08-24 →
09-07 the ungated replay bets 120 games, production bet 94, and **13 of
production's are not in the replay's set**. The replay sees every snapshot we
kept and production saw only the passes it ran, so the replay's set should be a
strict superset; 13 the other way is a fault in the replay. Candidates not yet
checked: games with no usable pre-game feature row, the 120s price-pairing
bound, or `rest_line < 0` firing where production had an earlier price. It does
not change the 2026-09-07 verdict (don't gate — the optimum moves with the
sample and its neighbour is negative in both tables), but the tool cannot be
trusted for a finer question until this is understood.

## [ ] Take `PROP_MAX_SIGNALS_PER_DAY` off when the two maps can be re-promoted

`config.PROP_MAX_SIGNALS_PER_DAY` caps `mlb_prop_pitcher_k` and
`mlb_prop_pitcher_hits` at 3/day. It is an INTERIM operator ceiling, not a
threshold — no sweep supports the number — and it exists only because the
calibrated cut cannot bind until those models have a fitted map again. The
signal that it is time:

```sql
SELECT model_id, count(*) FROM picks
WHERE model_id IN ('mlb_prop_pitcher_k', 'mlb_prop_pitcher_hits')
  AND result IS NOT NULL
  AND game_date >= '2026-09-04'      -- pitcher_hits: '2026-09-05'
GROUP BY 1;                          -- need >= 150 each
```

At 47 and 26 on 2026-09-07, and the cap itself slows the counter — roughly
2026-09-12 to 09-15. Then `python -m models.probability_calibration --promote
--models mlb_prop_pitcher_k mlb_prop_pitcher_hits`, confirm the maps bite, and
delete the two entries. A model update: `Updated-By`.

## [ ] [needs-decision] The live calibration map: 126 of 150, and it does not close

Asked for 2026-09-07 and measured the same day. Two blocking defects are FIXED —
the fit could not see live models at all (`fetch_graded` read a matview that
excludes `is_live`; every lane reported 0 graded picks forever), and
`classify_live_signal` decided on the raw probability. The map itself is still
refused, on two independent counts:

* **n = 126**, and `MIN_GRADED` is 150. At ~9 live bets a day that is ~3 days —
  the pre-game cap and collation did not touch live volume, so the rate holds.
* **`transfers` = FALSE.** Held-out 18.48pp raw -> 8.98pp calibrated, against a
  6.0pp cap. It helps and does not close — the `mlb_prop_pitcher_er` verdict.

And there may be a structural reason it never closes: live lanes write no
dead-zone NONE rows and their AVOIDs are never settled (232 live AVOIDs, 0
graded), so the fit sees one narrow band above the model's own 0.70 floor.

**The decision, when n clears:** the measured map takes a claimed 0.74 to 0.598
while the lane's cut (0.70 prob / 0.14 edge / 0.32 EV) was swept on RAW numbers,
so promoting WITHOUT re-sweeping the cut on calibrated numbers takes the lane to
near zero bets. Promotion and re-sweep are one decision. Do not lower
`MIN_GRADED` or `MAX_TRANSFER_GAP_PP` to make it fit.

Every live lane is 12-15pp hot on the same measurement (`mlb_live_total_runs`
+14.38, `ncaaf_live_total` +15.27, `ncaaf_live_win_prob` +11.97), so this is a
live-betting question, not an MLB one. `docs/mlb_volume_efficiency.md` §10.

## [ ] `LIVE_MAX_BETS_PER_WEEK` is advisory and the ceiling is being exceeded 2.1x

`config.LIVE_MAX_BETS_PER_WEEK["mlb_live_total_runs"] = 30`, set 2026-08-30 on
Matt's *"still too many live bets on MLB"*. `config.py:556` states plainly that
nothing enforces it at score time. Actual: 31 BETs in the week of 08-24, **63
in the week of 08-31**. Either enforce it in the live loop (the
`LIVE_MAX_SIGNALS_PER_DAY` mechanism already exists and is empty) or delete the
number so it stops reading as a guarantee. Assess for NCAAF's two live lanes at
the same time — they carry the same advisory ceilings.

## [ ] No live pick has ever had CLV captured

`picks.clv_pct` is populated on 123 of 165 MLB pre-game BETs since 2026-08-31
and on **0 of 63** live ones. CLV converges far faster than ROI, so
the one MLB model with a usable settled sample is the one we cannot judge by
the fast measure. Sport-agnostic: NFL and NCAAF live lanes have the same hole.

## [ ] One NCAAF game exists twice in `games`, under its ET id and its UTC id

Found 2026-09-06 (session 247) while tracing why a live NCAAF pick never reached
the app. Not the cause of that bug, and not fixed there.

```
NCAAF_2026-09-05_ucla_california   data_source 'live'  commence 2026-09-06T02:37:00+00:00  45-24
NCAAF_2026-09-06_ucla_california   data_source 'cfbd'  commence 2026-09-06T02:30:00.000Z   45-24
```

One football game. The odds feed keyed it by its **ET** date (kickoff 10:37pm ET
on the 5th); the CFBD import keyed it by the **UTC** date (02:30Z on the 6th).
Both rows now carry the same final, so nothing double-counts *today* — but the
picks reference the `09-05` id and the settlement path reads whatever it joins
to, so this is a live settlement and track-record hazard the next time the two
rows disagree, or the next time a model scores against the wrong one.

**What to check before fixing:** how wide this is. Every NCAAF night game after
8pm ET is a candidate, and NBA/NHL west-coast games have the same shape.
`SELECT` on `games` grouped by `(sport, home_team, away_team,
date_trunc('day', commence_time))` having `count(*) > 1` is the query. The fix is
in the ingestor's id derivation (ET, everywhere, per CLAUDE.md §4), plus a
one-off merge of the duplicates that PRESERVES the earlier row's identity —
picks point at it (§1c: `created_at` and the pick's game_id are part of the bet
of record, not metadata).

## [ ] [needs-decision] The player detail screen speaks the fan idiom while the board may be speaking the book's

Found 2026-09-06 (session 246) by the UX review of the ruler change, and NOT
fixed there because the change did not touch that screen.

The Stats board now speaks whichever idiom the mode chooses — `Over 0.5 Hits`
in Over mode, `1+ Hits` in At Least (`lib/hitMode.ts`). `PlayerStatsScreen`
still headlines its own chart threshold in the fan's idiom only — "Hits 1+ ·
last 10", lines 295 and 348 — behind a `±` stepper rather than a ruler.

So a member who sets the board to Over 0.5 and taps a player crosses an idiom
boundary with nothing bridging it: the number is the same bet, named the other
way, on the screen they drilled into to check it.

**The decision is whether the mode should ride along in the navigation params**
(the screen then opens in the idiom the user was reading), or whether the
detail screen is a different question — the player's history rather than a bet
— and is entitled to its own vocabulary. Matt's call; it is a consistency
question, not a correctness one, and either answer is defensible.

## [ ] [needs-decision] Two merged mobile changes are undelivered until the 1.1.0 native build ships

Found 2026-09-05 (session 239), checking whether the calibration removal had
actually reached users rather than trusting a green workflow.

**#504 bumped `mobile/app.json` to version 1.1.0** to ship
`LSApplicationQueriesSchemes` (an Info.plist key only a new binary can carry).
`runtimeVersion` policy is `appVersion`, so **every OTA now targets runtime
1.1.0, and every installed binary is 1.0.0.** Nothing picks them up.

The evidence, from the run history:

- **OTA run #71** (#504) **failed** — correctly. The workflow hard-fails any push
  that moves `mobile/package.json` or `mobile/app.json`, because an OTA cannot
  add native config to an installed binary.
- **OTA run #72** (#503, the calibration removal) **succeeded** — but only because
  that squash commit did not itself touch `app.json`; the bump was already on
  master. The guard only inspects the current push. It published a bundle to a
  runtime version nobody is running.

So the guard did its job for #504 and was structurally unable to catch #503.
Nothing is broken and nothing is lost — both changes wait on master — but
**a green OTA run is not proof of delivery while `version` is ahead of the
shipped binary**, and that is not obvious from the workflow's output.

**Unblocks both:** run `mobile-build.yml` for the 1.1.0 native build, ship it,
and the already-published bundle applies on install. Matt's call — it is a
TestFlight / App Store path.

**Worth fixing while there:** the OTA job could compare `app.json`'s `version`
against the last native build tag and warn (not fail) when it publishes to a
runtime no released binary matches. That is the check that would have said
"published, but to nobody" on run #72.

---

## [ ] [needs-decision] The Explainer's "Why we're different" no longer differentiates

Found 2026-09-05 (session 239), in the UX review of the calibration removal.
**Matt: "I will add new content later."** Left as-is deliberately, waiting on him.

The section used to claim a different OBJECTIVE FUNCTION — most services sell
accuracy, we optimise for calibration — with an external citation behind it.
Calibration came out of the UI, so the rewrite argues from the published record
instead. That is true, but it is the third place the app says it: the Track
Record subtitle ("Nothing hidden, nothing cherry-picked") and its "Read this
first" card already do. A differentiator that restates a promise made twice
elsewhere is not one.

**Two replacements that are true and genuinely unusual**, if he wants a starting
point rather than a blank page:

- **CLV as the skill metric.** "Beat the close" is already computed, already on
  the Record screen, and is the one number that separates edge from variance.
  Almost no consumer picks product publishes it.
- **The pick rule (CLAUDE.md §1c).** "A pick is a pick" — once written, the
  number never changes, even when the line moves against us. That is a real,
  checkable commitment competitors do not make, and the app already enforces it.

Touch `mobile/src/screens/ExplainerScreen.tsx`, the section headed "Why we're
different — the whole record, not one number".

---

## [ ] Dead code: OpeningComparisonScreen has no entry point

Found 2026-09-05 (session 239a). The Record tab's "Experiment: lock our first
signal vs chase the live line" link was that screen's ONLY route in, and it was
removed at Matt's request.

Still shipping in the bundle with no way to reach it: `OpeningComparisonScreen.tsx`
(~200 lines), the `OpeningComparison` route in `App.tsx` (annotated in the
`SignIn` style so it does not read as live), the `OpeningComparison` key in
`RootStackParamList`, and `fetchOpeningVsLive` / `fetchOpeningSlices` plus
`OpeningVsLiveRow` / `OpeningSliceRow` in `queries.ts` / `types/index.ts`.

**The shadow track itself is unaffected** — it keeps running server-side and
keeps its own window (`docs/opening_signals.md`). This is only about whether the
screen stays compiled. Matt's call: delete the lot, or restore one entry point.

---

## [ ] Two icon-only buttons in Settings are silent to VoiceOver

Found 2026-09-05 (session 239), by `ux_scan.mts` — the only two BLOCKER-level
findings in the app.

`mobile/src/screens/SettingsScreen.tsx:423` and `:434` are icon-only
`<Pressable>`s with no `accessibilityLabel`, so a screen-reader user hears
nothing at all. Pre-existing and byte-identical on master, which is why they were
declined on the calibration PR rather than fixed there — but they are real, and
the fix is one prop each.

While in that file, `ExplainerScreen.tsx:414` carries a `fontSize: 13` literal
that should be `font.size.*`.

---

## [ ] Nothing tells us when a market we pruned starts being priced

Found 2026-09-05 (session 237), in the UX review of the college prop prune.

`FOOTBALL_MARKET_NOT_PRICED` (mobile) and the pruned entries in
`config.PROP_MARKETS_NCAAF` / `PROP_ALT_MARKETS['NCAAF']` are a hand-maintained
mirror of one coverage probe. **They are measurements with no drift
detection.** If college books start posting carries or sacks mid-season —
plausible; the pro market prices both — nothing notices. We stop asking, so no
rows appear; no rows appear, so nobody looks. The column stays dark until a
person happens to re-run `scripts/probe_market_coverage.py`.

Same shape as the gap the probe was built to close (CLAUDE.md §1b: the current
state of a system is not its capability), one level up: we have now written our
belief about the market into config, where it will age silently.

**Cheap version:** a scheduled job that re-probes each sport's pruned keys
weekly — one market per call, a handful of credits — and posts to Discord when
one comes back served. The probe already reports exactly this and writes
nothing; it needs a caller and a comparison against the pruned list.

**Related, same session, same file to touch:** neither prop ingestor writes to
`api_call_log` (both use bare `requests.get` with only `record_quota_headers`),
so **prop credit spend is invisible in that table for every sport**. Today's
590-credit college pass had to be read out of the Railway worker log. Worth
doing at the same time — both are about a measurement that exists nowhere
queryable. Detail in `docs/market_coverage.md`.

---

## [ ] [needs-decision] The pre-game line poller deletes a game's non-BET PROP picks

Found 2026-09-03 (session 185) while tracing why the Stats board's ODDS column
was empty for players DraftKings was pricing.

`data/ingestors/pregame_line_poller.py` calls `run_scorer(only_games=…)` every
time DK's number on a game moves. The game scorer's non-BET housekeeping delete
(`models/scorer.py`, "Housekeeping for the pairs the lock deliberately leaves
open") is scoped by `game_id` and not by model, so it removes that game's PROP
`NONE` and `AVOID` rows as well — and `run_scorer` never re-creates them,
because prop scoring is a separate function that only runs on the hourly pass.
`picks_log` for 2026-09-03 shows it plainly: INSERT 36 batter-hits rows at :20,
DELETE 36 at :24, nothing until the next hour.

**Measured.** Prop non-BET deletes per day: 0 on 2026-08-28 and 08-29, then
8,467 / 23,047 / 15,841 / 15,718 on 08-30 → 09-02 — the step is the day the
poller shipped. **No prop BET row was deleted** in that window, so §1c holds for
the bet of record; what churns is the dead-zone and AVOID population.

**Why it is not just "delete the delete".** `_locked_prop_keys` locks on ANY
unsettled row including `NONE`, so nothing else un-locks a dead-zone player. Stop
the delete and a player who was in the dead zone at 10am can never later cross
into a BET — a worse bug than the one being fixed.

**The likely fix, and why it needs a human.** Lock props on `BET` only, matching
the game lock's own rule ("no pick because bad number, then it drifts into pick
territory, is a pick we should take"), and let the prop scorers delete-and-rescore
their own non-BET rows each pass. That changes which picks fire, so under §1b it
is a model update and needs `Updated-By:` — **whose call it is has not been
asked.** Do not ship it from the backlog.

The app-side symptom is already gone: the Stats ODDS column reads
`v_latest_prop_odds_all_books` as of session 185, so a missing prop row no
longer blanks the price.

---

## [ ] 145 pressables are silent or roleless for VoiceOver

Found 2026-09-02 by the first run of `node mobile/scripts/ux_scan.mts --all`
(the deterministic half of the front-end UX review, `mobile/docs/UX_REVIEW.md`
§5): **145 `Pressable`/`Touchable*` tags across 47 files carry neither
`accessibilityRole` nor `accessibilityLabel`. 20 of them are icon-only**, so
VoiceOver has nothing to read at all — the Ionicons glyph is not text — and
the control does not exist for a screen-reader user. The other 125 have a
`<Text>` child, so the label is read but the role is not: "Track" instead of
"Track, button". Both are Apple HIG failures; the icon-only ones are the
Blockers.

Where they are (icon-only first):

| file | icon-only | all |
|---|---|---|
| `screens/StatsScreen.tsx` | 3 | 9 |
| `screens/ModelEditScreen.tsx` | 2 | 13 |
| `screens/SettingsScreen.tsx` | 2 | 7 |
| `screens/ModelsScreen.tsx` | 2 | 5 |
| `screens/PlayerStatsScreen.tsx` | 2 | 5 |
| `components/ParlayLegCard.tsx` | 2 | 2 |
| `screens/ParlayScreen.tsx` | 1 | 11 |
| `components/ParlayDkHandoff.tsx` | 1 | 3 |

Fix, per tag: `accessibilityRole="button"` on every one; `accessibilityLabel`
on the icon-only ones saying what the tap does ("Open settings", "Add to
betslip", "Remove leg"), not what the icon is. `TrackButton.tsx` is the
existing pattern. Where an `Ionicons` sits beside text inside a pressable,
mark it decorative with `accessibilityElementsHidden` so it is not read
before the label. Do not add `accessible={false}` to make the scan quiet.

Mechanical, but not one sitting: it touches ~47 files and the OTA ships it to
every installed build, so do it a few screens per PR, highest-traffic first
(Picks board, Live, Pick detail, Betslip), run `/ux-review` on each PR, and
finish with `node mobile/scripts/ux_scan.mts --all | grep -c a11y-pressable`
reading 0. JS-only, so each merge goes out over the air; no native rebuild.

Same source flagged a second pattern, smaller and separate: a fixed
`height: 48` on the primary button in `PaywallScreen`, `SignInScreen`,
`DiscordLinkModal`, `ConnectSportsbookScreen` and `SignalLockCard` clips the
label under Dynamic Type. `minHeight` plus vertical padding fixes each; five
edits, one PR.

## [x] `mlb_prop_batter_hits` — dormant, and losing when it fires

Surfaced by the first ModelCalibration sweep (2026-09-02): unpaused, 5,661
settled, `cur_n = 0`. Investigated 2026-09-03. It is DORMANT, not a broken feed
— it scored 460 rows on 1–2 Sept and `player_game_log` is continuous — so §7's
"a dormant model and a broken feed look identical" resolves to the dormant side.

**Its predictions compressed, on an unchanged artifact.** `model_registry` shows
one active version since 2026-06-21, never swapped. Two UNCENSORED windows
either side (both with NONE rows present, so like-for-like):

| window | n | sd | p95 | p99.9 | max | ≥0.78 |
|---|---|---|---|---|---|---|
| 06-21→06-25 | 1,457 | 0.1394 | 0.757 | 0.944 | 0.950 | 53 (3.64%) |
| 08-10→09-02 | 8,026 | 0.1020 | 0.657 | 0.774 | 0.795 | 8 (0.10%) |

Same model file, 36x fewer rows clearing the 0.78 prob cut. The break is sharp
at **2026-07-23**: daily max prob ran 0.87–0.99 with BETs every day up to
07-22, and never exceeded 0.795 afterwards. The cut did not move (0.78/0.17
since 2026-06-28), so this is the inputs losing discriminative power, not a
threshold change. Which feature is the open question — the repo's git history
starts 2026-08-27, so there is no code history for July, and identifying it
needs the feature engine run for one date either side of 07-23 (a worker job:
no DATABASE_URL in a dev sandbox).

**Do NOT chase the volume back.** Realised record, 521 settled BETs, flat $100
(`profit_flat` is exactly -100 on every loss, so flat ROI = sum/(n*100) —
dividing by `recommended_bet` mixes flat profit with a Kelly stake and gives a
nonsense -127%):

| bucket | bets | win% | breakeven% | avg odds | flat ROI |
|---|---|---|---|---|---|
| blocked by the -140 floor | 401 | 65.1 | 67.9 | -225 | **-3.89%** |
| passes the -140 floor | 120 | 40.0 | 50.1 | +3 | **-21.16%** |
| all | 521 | 59.3 | 63.8 | -172 | **-7.87%** |

**The -140 floor keeps the WORSE half for this model.** The slice it admits lost
-21.2%; the slice it blocks lost -3.9%. That inverts the floor's purpose here
(on `mlb_prop_batter_rbi` the same floor capped 36 bets at +7.3% vs +2.2%
uncapped), so it is a per-model fact, not a general one.

So the dormancy is currently PROTECTIVE, and that is the risk: the model is
unpaused, and if its distribution ever un-compresses it resumes betting the
-21% slice with nobody deciding to.

The sweep's "best" cell (29 bets, +19%) is not a way out — its verdict was
"FAILS THE TIME SPLIT (19.5% then None%)": the second half has no bets at all,
so it is fitting the pre-07-23 period that no longer exists.

**Decision needed (a model update — needs `Updated-By: <person>` per §1b):**
1. PAUSE or RETIRE it. config's own comment has called it a retrain candidate
   since 2026-06-21; it has now lost $4,098 at flat $100 over 521 bets.
2. Or retrain first, then decide — the features (rolling form, prior-season
   Savant, batting order, opp team ERA) are the same ones that stopped
   discriminating on 07-23, so a retrain without finding that cause may
   reproduce it.
Leaving it live and dormant is the one option with a hidden downside.

**DECIDED 2026-09-03 (mike): PAUSED.** Option 1. `PAUSED_MODELS` in
`config.py`, with the evidence above kept alongside the entry; thresholds
left in the dicts for the unpause. Unpause path is a retrain, but find the
2026-07-23 cause FIRST — the features that stopped discriminating are the
ones a retrain would re-fit, so retraining blind may reproduce it. That
still needs the feature engine run for one date either side of 07-23, which
is a worker job (no `DATABASE_URL` in a dev sandbox).

## [ ] `my_access()` is called by the app and does not exist in production

Found 2026-09-04 in session 208 while enumerating the function grant surface.
`mobile/src/lib/discord.ts:157` calls `supabase.rpc('my_access')` and
`fetchAccess()` does `if (error) throw error` — it does not fail soft. But
`my_access()` is **absent from `pg_proc`**: it and `has_app_access()` are defined
only in `data/migrations/add_discord_link_and_whop_memberships.sql`, which has
**never been applied**. `has_active_subscription()` — the function that migration
supersedes — is the one that actually exists.

CLAUDE.md §6 states the gate is `public.my_access()` / `has_app_access()`. That
is the intended design, not the deployed one, and the difference has never been
written down.

**What needs deciding:** whether to apply that migration (it also creates the
Discord-link and Whop-membership tables), or to change the app. Not touched here
— it is the entitlement path, and applying a never-run migration that creates
billing-adjacent tables is not a side effect of a grant change.

Note it does NOT block the grant work: the migration already carries its own
`REVOKE ALL ... FROM PUBLIC, anon, authenticated` plus
`GRANT EXECUTE ... TO authenticated`, so it stays correct now the default
privilege is revoked.

## [ ] CLAUDE.md is 26% over its own size limit

Noticed 2026-09-04 in session 222, while promoting a rule into §7. The file
states its own budget — *"Keep this file under ~30 KB"* — and it was **37,613
bytes before that promotion and 38,674 after**. So it has been over for a while;
this session added 1,061 bytes of it and is flagging rather than quietly
continuing.

The size matters for the reason the file itself gives: it is re-read at the start
of every session, so every kilobyte is paid on every session forever. That is why
the 909 KB version was split up in the first place.

The file's own test for what to cut is already written down: *"something in it is
a log entry wearing a rule's clothes"* — i.e. anything that records what happened
once rather than governing what happens next. A trim should apply exactly that
test and nothing looser, because the failure mode in the other direction is worse:
a rule that governs future sessions gets deleted, nobody notices, and the trap it
prevented comes back.

Two candidate approaches, both needing a person to approve the cuts:

- Move the EVIDENCE still embedded in rule text out to `docs/rules_evidence.md`,
  which exists for exactly this and is already linked. Several §1b and §7 entries
  still carry their measured story inline.
- Check whether any §7 entry is now fully covered by a path-scoped rule in
  `.claude/rules/`, which loads on demand and costs nothing on sessions that do
  not touch those directories.

Not attempted here: deleting from CLAUDE.md is not a side effect of a dashboard
change, and picking which rules survive is a judgement about what future sessions
need.

## [x] Default privileges still hand anon EXECUTE on every new function

Found 2026-09-03 in session 206, alongside the table fix. `pg_default_acl`
carries three entries for `public` from grantor `postgres`:

    objtype r (tables/views)  anon=arwdDxtm   <- REVOKED 2026-09-03
    objtype S (sequences)     anon=rwU        <- still there
    objtype f (functions)     anon=X          <- still there

So every new function in `public` is still callable by `anon` the moment it
exists. That is how five `SECURITY DEFINER` `feedback_*` RPCs ended up
anon-callable — intended in that case, but nobody granted it.

**DONE 2026-09-04 in session 208** (mike: *"do the function grants too"*), with
exactly that treatment: `RPC_ANON_CALLABLE` in `data/anon_readable.py`, a test
against `mobile/src`, and grants generated from it.

**And "the 17 the app calls" was wrong — it is 24.** Four call sites in
`queries.ts` build the name at runtime (`const fn = sport === 'NFL' ? ... : ...`),
so a literal grep for `.rpc('...')` misses eight functions the app reaches
through a ternary. Sweeping on the literal list would have revoked EXECUTE on
the NBA, WNBA, NCAAF and NFL stats functions — silently. The test resolves both
forms and has its own guard-the-guard case, because a resolver that stops
resolving fails OPEN: the surface looks smaller and the sweep gets bolder.

Also caught: `_jsonb_text_array` must stay granted even though the app never
names it. `custom_model_picks` and `custom_model_backtest` are SECURITY INVOKER
and both call it, so the CALLER needs EXECUTE.

**Completed 2026-09-04 in session 210** (mike: *"sweep the PUBLIC grant off the
19 stats rpcs"*). Session 208 named PUBLIC in the two REVOKEs but not on the 25
it was GRANTing, so the explicit `anon, authenticated` grant sat on top of a
PUBLIC grant that was still there on **20** of them — decoration. The apply now
does `REVOKE ALL ON FUNCTION ... FROM PUBLIC` before each GRANT (order pinned by
a test), and a third in-transaction read-back rolls the whole apply back if
PUBLIC still holds anything on a declared callable. Verified in `pg_proc` after
the run: callable-by-PUBLIC **21 -> 1**, the one being `log_picks_changes()`,
left alone on purpose.

Sequences remain deliberately untouched: `tracked_bets.id` defaults to
`nextval('tracked_bets_id_seq')` and anon holds USAGE/UPDATE on it, so closing
the sequence default would break the next app-writable table's INSERT on its own
primary key.

Sequences are the low-stakes third: `w` on a sequence is `nextval`/`setval`, and
nothing reads a sequence through PostgREST here.

**Also still open, and NOT fixable from this project:** the `supabase_admin`
default-ACL entry for `public` tables grants `anon=arwdDxtm` too. Altering it
needs membership in `supabase_admin`, which `postgres` does not have on a
managed project. Nothing in this repo creates tables as that role, so it is
latent rather than live.

## [x] RLS is off on `worker_jobs` and `odds_history_pulls`

Found 2026-09-01 by `get_advisors(security)`, which reports both at **ERROR**
level: "is public, but RLS has not been enabled."

**IT IS AN OPEN DOOR. This item said it was not, and that was wrong** (corrected
2026-09-03, session 205, while fixing the `odds` grant next door).

`pg_class.relacl` on both tables reads
`{postgres=arwdDxtm/postgres,anon=arwdDxtm/postgres,authenticated=arwdDxtm/postgres,service_role=arwdDxtm/postgres}`
and `has_table_privilege('anon', ..., 'INSERT')` returns **true**. With RLS off
there is nothing behind that, so anon -- the key shipped inside the app -- could
INSERT into `worker_jobs`, the queue the Railway worker claims and executes every
five minutes.

**Why the check below said otherwise:** `information_schema.role_table_grants`
only shows grants the CURRENT role can see. It returns 0 rows for `odds` too --
a table whose relacl demonstrably reads `anon=arwdDxtm`. So 0 rows meant "you
cannot see them", not "they do not exist". `relacl` and `has_table_privilege()`
are the authoritative reads. This is §7's "read the result, not the intent" in
its other form: a null result was read as evidence of absence.

**REVOKEd 2026-09-03** (`data/migrations/tighten_anon_write_grants.sql`), so the
grant is gone and the door is shut. **Still open: enabling RLS on both**, as the
second lock. It was deliberately NOT done in the same migration -- RLS with no
policy locks out every connection that is not the table owner, and the worker's
role has not been verified to be that owner; the revoke closes the hole without
gambling the job queue.

**DONE 2026-09-04 in session 211** (mike: *"enable rls on those three tables"*),
on all three -- `model_artifacts` joined the two named here, because it has the
same shape and the same on-demand creation.

**The open question this item flagged is answered: the worker IS the owner.**
"the worker's role has not been verified to be that owner" was the stated reason
for not doing it in the same migration. Measured: all three are owned by
`postgres`, `postgres` has `rolbypassrls` **and** owns them (exempt twice over),
`service_role` also has `rolbypassrls`, and `pg_stat_activity` shows the worker's
connections as `usename=postgres` via Supavisor. No view or matview selects from
any of the three (`pg_depend` -> `pg_rewrite`), and `mobile/src` never names
them. `FORCE ROW LEVEL SECURITY` -- the variant that WOULD subject the owner to
the policies -- is deliberately not used, and a test pins that.

**NOT run once as a migration, and the reason is this file's own next paragraph
plus a third data point.** All three tables are created on demand by the code
that writes them, so a migration is undone by the next run against a database
where the table does not yet exist -- which is exactly how `model_artifacts` came
back with the full anon grant between two sweeps hours apart. So the pair lives
beside each CREATE, through `data/anon_readable.py::lock_down(conn, table)`,
which carries the `schema_is_current` gate INTERNALLY as the paragraph below
requires. The gate is inside the helper rather than at each call site so a new
caller cannot forget it; `lock_down_sql()` is the ungated builder, for the admin
script and the tests only.

**Verified after the apply, three ways.** `pg_class`: RLS on, `FORCE` off, 0
policies, anon/authenticated hold nothing on all three. `get_advisors(security)`:
the two ERROR-level `rls_disabled_in_public` lints are **gone** and all three now
report `rls_enabled_no_policy` at INFO -- the locked shape this file's last
paragraph says is expected. And `scripts/verify_worker_rls.py` on the worker
itself (it cannot run anywhere else -- the Supabase MCP is
`supabase_read_only_user` and `SET LOCAL ROLE postgres` is denied):

    connected as 'postgres', rolbypassrls=True
    model_artifacts:     rls=True owner=postgres rows_visible=4
    odds_history_pulls:  rls=True owner=postgres rows_visible=1042
    worker_jobs:         rls=True owner=postgres rows_visible=15
    worker_jobs write probe: insert/read-back/update/delete all succeeded

Row counts matter more than the absence of an exception: a non-exempt role gets
**zero rows**, not an error, so a SELECT returning the count already known to be
there is what proves exemption. All rolled back.

Two follow-on fixes the change forced, both worth knowing:

- `job_queue.ensure_schema`'s `schema_is_current(...)` early-return fires BEFORE
  the lock-down, so without `rls=True, revoked_from=API_ROLES` it answers True on
  a still-open table and the lock-down never runs. A guard that dead code can
  satisfy.
- `tests/test_ddl_guard.py` now treats `lock_down(` as a guarded path rather than
  exempting each caller, with its own guard-the-guard case: if `lock_down` stops
  calling `schema_is_current`, every caller silently becomes an unguarded DDL
  site while the offender test keeps passing.

**AND THEN THE REST, 2026-09-04 in session 212** (mike: *"do the remaining seven
too"*). It was **eight** -- my seven was an hour stale and `nfl_odds_cache_backup`
had arrived in between. The invariant now holds schema-wide:

    0 of 84 public base tables have RLS off
    0 have FORCE RLS on

`brand_assets` turned out to be a fourth CREATE SITE (`fetch_brand_avatar.py`)
rather than an archive; the other seven have no create site and are swept by the
admin script only. They are locked rather than dropped because a repair is
reversible only while its backup exists -- retention is a separate decision.

**CLOSED 2026-09-04 in session 220** (mike: *"sure do the grant thing"*), as a
rule rather than a single revoke: a relation the app READS now holds SELECT and
nothing else unless it is named in `ANON_WRITABLE` (`data/anon_readable.py`),
enforced and read back by `scripts/apply_anon_grants.py`. Stating it that way
found **sixteen `v_*` views** carrying the same surplus that the one-table fix
would have left. `TRUNCATE` is revoked from everything, the writable tables
included -- it takes no `WHERE` clause, so no RLS policy can narrow it.

The view grants were measured before being called harmless, because an
auto-updatable non-`security_invoker` view would run its base-table permission
AND RLS checks as the view OWNER (`postgres`, who bypasses both) -- a real write
path, invisible to any check that looks only at base-table ACLs. All sixteen
return 0 from `pg_relation_is_updatable(oid, true)` and carry
`security_invoker=on`. Revoked anyway: a view that is later simplified can
silently become updatable.

**The first apply of that rule was incomplete, and the miss is worth keeping.**
The sweep iterated `ANON_READABLE`; `feedback` is writable-but-not-readable, so
it was never visited and kept **TRUNCATE** through a successful-looking run --
the one verb no RLS policy can narrow. `test_truncate_is_never_granted_to_anything`
passed the whole time, because it checks the DECLARATION and the declaration was
correct. Fixed by driving the sweep from `pg_class` + `has_table_privilege`
instead of a declared list. **Third instance today of a guard that could not fail
for the real case**, after `job_queue` and `threshold_review`; the general rule is
in the session 220 entry.

**DONE 2026-09-04 in session 221, and the way it was open is the lesson.** This
item said narrowing the last three needed a person to decide "what the app is
ALLOWED to do". It did not. Every verb was answerable by reading the call sites,
and mike said so bluntly: *"you have access what are you blathering about"*.

    device_push_tokens   .upsert(onConflict:'token')   -> INSERT + UPDATE
                         nothing deletes a push token  -> DELETE revoked
    tracked_bets         .insert() and .delete()       -> INSERT + DELETE
                         nothing edits a tracked bet   -> UPDATE revoked
    feedback             rpc('feedback_submit') only   -> ALL THREE revoked

`feedback` left `ANON_WRITABLE` entirely: all six `feedback_*` functions are
SECURITY DEFINER owned by `postgres` (verified in `pg_proc`), so they act with the
owner's rights and the app never touches the table. The `anon insert feedback`
policy stays -- inert without a grant, and dropping a policy is a separate change.

The derived verbs match the RLS policies exactly (`a,w` / `a,d` / `a`), which is
the corroboration: whoever wrote the policies encoded the real intent and only the
GRANTS had drifted. Verified in `pg_class` after the apply, and a test now pins
each verb to the call site that justifies it, so widening becomes a deliberate
edit rather than a rediscovered surplus.

**The general lesson, promoted because it is the same shape as this session's
three guard bugs:** "this needs a decision" is itself a claim that has to be
checked. Before handing a question over, ask whether the codebase already answers
it -- CLAUDE.md §1b, *work you can do is not an action item for Matt*.

**The original finding, kept for the record:**

**A NEW OPEN DOOR OF THE SAME SHAPE, FOUND WHILE VERIFYING THIS ONE:**
`game_weather` grants anon INSERT/UPDATE/DELETE while its only anon policies are
SELECT (`allow anon read`, `anon read game_weather`, plus `service_role_all`). So
the writes are **inert today** -- RLS denies them -- but the ACL does not match
intent, and that is precisely the "one lock, and it is an ACL" state this section
exists to complain about. The session-205 sweep missed it.

Safe to close: `mobile/src` only ever SELECTs `game_weather` (three call sites in
`queries.ts`), and every writer is server-side over `postgres`
(`data/ingestors/weather_ingestor.py` and the feature engines). Fix is
`REVOKE INSERT, UPDATE, DELETE ON game_weather FROM anon, authenticated`, or
adding it to a declared write surface if anon really should write weather.

Worth re-running the same query against the other three anon-writable tables
whenever this is touched -- `device_push_tokens`, `feedback` and `tracked_bets`
all hold write grants wider than their policies (DELETE on the first two, UPDATE
on all three), inert for the same reason:

```sql
select c.relname,
       has_table_privilege('anon', c.oid, 'INSERT') as ins,
       has_table_privilege('anon', c.oid, 'UPDATE') as upd,
       has_table_privilege('anon', c.oid, 'DELETE') as del,
       (select string_agg(p.polname||':'||p.polcmd::text, ', ')
          from pg_policy p where p.polrelid = c.oid) as policies
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind = 'r'
  and has_table_privilege('anon', c.oid, 'INSERT,UPDATE,DELETE');
```

The superseded check, kept so nobody re-runs it and re-reaches the wrong answer:

```sql
select table_name, grantee, privilege_type
from information_schema.role_table_grants
where table_schema='public'
  and table_name in ('worker_jobs','odds_history_pulls')
  and grantee in ('anon','authenticated');
-- 0 rows
```

Neither role holds a single table privilege, so PostgREST cannot read or write
either table however the advisor grades it. What is missing is the second lock,
not the first — and §7's rule is that the grant is the thing to check, not the
lint's intent ("run `get_advisors(security)` after every migration and read the
result, not the intent").

Why it still matters enough to do: `worker_jobs` is the queue the Railway worker
CLAIMS AND EXECUTES every five minutes (`tracking/job_queue.py`). A future
migration that grants `anon` INSERT — or a `GRANT ... ON ALL TABLES` that sweeps
it up — turns a missing RLS policy into arbitrary job execution on the container
holding `ODDS_API_KEY`, `DATABASE_URL` and open egress. That is the one table in
this repo where defence in depth is worth the two lines.

Fix: `ALTER TABLE public.worker_jobs ENABLE ROW LEVEL SECURITY;` and the same for
`odds_history_pulls`, with NO policy (so the tables stay service-role only, which
is what they already are in practice), then re-run `get_advisors(security)` and
confirm both ERRORs clear. Add the statements to `supabase/` alongside the other
migrations so a rebuilt project carries them.

**Run it ONCE, as a migration — never in application code.** #389 measured what
that statement costs on this database: `ALTER TABLE ... ENABLE ROW LEVEL
SECURITY` takes ACCESS EXCLUSIVE *whether or not RLS is already on*, and fires
Supabase's `pgrst_ddl_watch`, which 503s the whole app while PostgREST rebuilds
its schema cache. It ran 1,676 times at a 7.8s mean from code that assumed it
was a free no-op. So: a one-time migration is correct and cheap; the same line
inside a function that runs per call is the outage. If you do put it behind
code, guard it with `data.ddl_guard.schema_is_current(...)` as the seven modules
in #389 now do.

Note while you are there: 30 further tables report `rls_enabled_no_policy` at
INFO. That lint is the *opposite* shape — RLS on, no policy, i.e. locked — and is
expected for service-role tables. Do not "fix" those by adding policies.

## [x] `commence_time` is ~16-20 minutes LATER than the actual first pitch

**Done 2026-09-01 in session 166** — `data/first_pitch.py`, `games.first_pitch_at`,
the COALESCE at all three guard sites, and two queued jobs to derive and repair.
The open question (feed artefact vs genuine drift) is unchanged and still needs a
timestamped play source.

**Finished 2026-09-03 in session 204**, because it was closed a call site short
and a clamp short:

- `_is_pregame_snapshot` GAINED the `first_pitch_at` parameter in session 166
  and **not one of its five callers ever passed it** — the guard was wired but
  never armed. All four feature engines now do (measured: zero game-level keys
  change today).
- Three readers had hand-copied `pregame_cutoff_sql()`'s output instead of
  calling it, so they could not inherit a fix to it. All three call it now.
- The prop PRICE read — the one that decides a bet — was not on the list at all.
  It is now, via `_pregame_cutoff_map`, and 49% of player+market keys were
  pricing inside the window.
- **The derivation needed a sanity clamp.** 7 of 415 games derive a first pitch
  hours early (a doubleheader matched to the wrong game); `relabel_in_play` had
  already marked 6,565 genuinely pre-game rows as in_play on the strength of it.
  See `SUSPICIOUS_EARLY_MINUTES`.

**The 6,565 mislabelled rows are repaired** (mike, 2026-09-03: "run the repair
and merge to master"). `scripts/repair_bogus_first_pitch_labels.py` ran on the
worker; verified by query, not by log: the backup table
`odds_pre_first_pitch_relabel_20260903` holds all 6,565 rows with their
original `in_play` value, those rows now read `open`, none remain mislabelled,
and the 33,091 `in_play`-before-scheduled-start rows on other games (the live
loop's own, correct population) were not touched.

mike, 2026-09-01: "should be commence time." He is right, and the direction is
the opposite of what I assumed when I raised it.

Measured over the 413 games with live state coverage (2026-07 onward): the first
`live_game_state` row with `abstract_game_state='Live'` lands on average **19.5
minutes BEFORE** `games.commence_time`, median 15.9 minutes before. Only 4 of
413 games began after their commence_time.

So the boundary every pre-game read uses -- `snapshot_at <= commence_time`, the
§7 rule -- is systematically too late, and odds rows inside that window are
treated as pre-game while the game is already under way. This is a leak in the
PERMISSIVE direction, and it is the explanation for the 48,712 rows labelled
`in_play` by the live loop (correctly, from game state) whose timestamp is at or
before their commence_time.

What to build:
- `games.first_pitch_at`, derived from `MIN(snapshot_at)` over
  `live_game_state` where `abstract_game_state='Live'`, per game.
- Make the pre-game guard prefer it: `COALESCE(first_pitch_at, commence_time)`.
  `features/feature_engine._is_pregame_snapshot` and
  `features/market_movement.load_market_movement` are the two call sites, plus
  `data/ingestors/odds_ingestor._mark_in_play`.
- Do NOT overwrite `commence_time`. It is the scheduled time, the app shows it,
  and the schedule is the right thing to show.
- Coverage is 2026-07 onward only, so `first_pitch_at` will be NULL for
  everything older. The COALESCE handles that, and the guard already fails open.

Whether the ~19-minute gap is a feed artefact (the API marking a game Live
during warmups) or a genuine commence_time drift is worth one query before
building: compare `first_pitch_at` against the first PLAY, if a timestamped
play source can be found. `plays` carries no timestamp today.

## [ ] Market-aware MLB model, now trainable on three seasons instead of one

Blocked until the 2024/2025/2026 historical backfill finishes (declared jobs
`mlb-history-2024`, `-2025`, `-2026-preaug`; watch `odds_history_pulls`).

`features/market_movement.py` computes nine columns and NO model consumes them.
Before 2026-09-01 that was forced: movement existed for 1,906 MLB games, all in
2026, disjoint from where the game models train. The backfill removes that
constraint -- 2024, 2025 and 2026 at two snapshots a day across seven books.

The plan is in `docs/market_movement_features.md` and one thing in it is now
out of date: it says "a new model trained on 2026 alone". It should be
2024-2026, with a chronological split, compared against the incumbent on the
same games.

Check coverage per season before training. A season where the backfill hit its
credit cap is a season with a hole in it, and `stopped_early` in the job result
says so.

## [x] Opposing-starter retrain, as a cloud job rather than a handover

**Done 2026-09-01 in session 166.** All five baselines trained ON THE WORKER via
`jobs/declared_jobs.json`, register=false, seasons 2020-2024, holdout 2025:

| model | holdout_ou_acc | MAE | repo artifact for comparison |
|---|---|---|---|
| hits  | 0.6046 | 0.6861 | 0.6043 / 0.6858 (2019-2024, holdout 2025) |
| tb    | 0.5963 | 1.3269 | 0.5963 / 1.3268 (2019-2024, holdout 2025) |
| runs  | 0.6370 | 0.5662 | 0.6370 / 0.5662 (2019-2024, holdout 2025) |
| rbi   | 0.7082 | 0.6148 | 0.7121 / 0.6199 (2019-2023, holdout 2024) |
| walks | 0.7277 | 0.4501 | 0.7281 / 0.4496 (2019-2023, holdout 2024) |

**Dropping 2019 costs nothing.** hits, tb and runs come back identical to their
2019-2024 artifacts to four decimal places, which settles the one open worry
about pinning 2020-2024 for the activation: the seasons are interchangeable and
only the opposing-starter columns will differ.

Step 2 of the runbook is now unblocked: apply
`docs/patches/activate_opp_starter_features.patch`, queue the same five jobs
with register=true, and compare against the table above.

## [ ] (superseded) Opposing-starter retrain — original handover wording

`docs/activate_opp_starter_features.md` has the patch and the runbook, and it
has been "run these five commands on your machine" for a day. It should be a
`retrain_model` declaration in `jobs/declared_jobs.json` -- the queue exists
now, and `model_artifacts` means the resulting `.pkl` survives the container.

Order matters and the runbook has it: baselines FIRST (register=false, seasons
2020-2024, holdout 2025, current features), then apply the patch, then the real
runs. Comparing a patched model against the artifact in the repo measures two
changes at once.

## [ ] [needs-decision] `DATAGOLF_API_KEY` is not set on either Railway service

Golf has been silently skipping on every pass — `Golf: DATAGOLF_API_KEY not set
— skipping golf step`, three times per refresh (ingest, ingest, scorer). The
variable is absent from both the `worker` and `pollers` variable lists, though
CLAUDE.md §6 lists it as a worker secret, so it was dropped rather than never
added.

This is a SEPARATE outage from the 2026-08-31 database break and predates it.
Found while diagnosing that one; not fixed here because only Matt can supply
the key, and whether the golf models should be running at all right now is his
call, not an agent's. Evidence: worker deploy logs, any refresh pass.

## [x] `nhl-api-py` is not installed on the worker

**The premise was wrong, and the warning was the thing lying.** `nhl-api-py`
3.3.0 WAS installed and had been pinned in `requirements.txt` from the start.
Its module is `nhlpy`; `nhl_stats_ingestor.py` imported `nhl_api` and
`nhl_api_py`, so both spellings raised `ImportError` and the "not installed"
warning fired on every pass forever.

Nothing was broken behind it: neither imported handle was ever read, and the
`NHL_API_AVAILABLE` flag it set was referenced nowhere in the repo. The
ingestor calls `api-web.nhle.com` and `api.nhle.com` directly for everything.
The whole block was dead code whose only output was a daily error naming a
cause that did not exist — and it cost a follow-up item chasing a missing
dependency that was never missing.

Same shape as the NFL wind card failing behind a comment saying it could not:
an error message is a claim, and a claim nothing verifies goes stale pointing
at the wrong thing.

Fixed 2026-09-03: dead block and false warning removed, docstring corrected,
and the unused requirement dropped (nothing imports `nhlpy`; a test now fails
if anything starts to, so the pin goes back before the import does).
Found 2026-08-31.

## [ ] An off-platform pinger, so both containers dying is not silent

`tracking/heartbeat_watchdog.py` (2026-08-31) runs on every service role
precisely so one container can report the other's death, but it is still hosted
inside the system it watches: losing both at once is silent. Closing that needs
something outside Railway — a cron on Matt's machine, or an uptime service
hitting the monitor's `/healthz` — that alerts on the ABSENCE of a heartbeat
rather than on an error. Documented in `docs/monitoring.md` under "What it still
does not cover".

## [x] Stop pulling the NHL 3-way market out of season

`h2h_3way` is fetched per NHL event on every pass and returns **422 on every
one** — 32 wasted round trips per pass, ~1,300 a day. Credits are not charged
on a 422 (verified), so this is latency and noise rather than money, but it is
also 32 lines of error in every pass log, which is how a real error gets
missed.

Flagged 2026-08-30, three times. Fixed 2026-09-03 — but NOT by the season
gate suggested here, and not by a circuit breaker either. A season calendar
has to be right about the NHL's start date every year forever and is wrong
silently. A give-up-after-N-misses breaker was written first and a test
killed it: it cannot tell "out of season" from "in season, but the first
few events listed are far-future games", so it would abandon a market that
IS offered — the exact failure that hid `h2h_3way` for months.

What shipped is a proximity window (`THREE_WAY_LOOKAHEAD_DAYS = 3`): DK
prices the regulation market for games about to happen, so an event further
out is not worth a call either way. Out of season the nearest game is weeks
off and the loop makes ZERO calls; in season it walks today's slate and
nothing else. Fails OPEN on a missing or unparseable `commence_time`, so a
real game is never dropped over a timestamp shape.

## [ ] `run_ledger finish` swallows its own errors

`python -m tracking.run_ledger finish ... 2>/dev/null || true` in
`scripts/refresh_pass.sh`. So a pass that COMPLETED but failed to write its
finish row is later marked `aborted` by the next run, and "aborted" therefore
means either "the pass died" or "the bookkeeping call failed" — two very
different things that cannot be told apart.

This actively cost diagnosis time on 2026-08-30: four passes were investigated
as hangs when at least two were deploy restarts. Keep the `|| true` (a ledger
must never break the pass it observes) but log the failure somewhere visible
instead of `/dev/null`.

## [ ] Settle is step 24 of 28, so it is the first thing lost

Grading and the daily recap sit near the end of the chain. On 2026-08-30 four
passes died mid-chain and the corrected recap went unposted for five hours,
while odds — step 2 — kept updating fine.

Settle genuinely must follow the results ingests, so this is not a reorder.
The fix is to make the record not depend on a pass surviving to the end: a
small settle-and-recap entry point that can run on its own, or a late-day
guarantee pass that does only that.

## [ ] One leaked database connection

`pg_stat_activity` showed a connection idle for 1 day 20 hours. Harmless at
this scale — `data.db.get_connection()` does not pool, so one leak is one
connection — but it is a leak and it will not be the last. Find the caller
that does not close.

## [ ] Batter props never get a best price stamped

Zero August `mlb_prop_batter_*` BETs carry `best_odds`, while
`mlb_prop_pitcher_k` carries 6 of 18. So it is a live code-path bug, not
missing plumbing: the books are configured, all three append sites in
`run_batter_prop_scorer` tag `_best_ctx`, and **1,726 of 1,783 DK batter-prop
quotes (97%) have a same-line match at another book**.

Leading hypothesis, unverified: the prop lock freezes a pick at first signal,
so one written before best-price stamping shipped is never re-stamped. Needs a
reproduction against real rows — the dev sandbox has no `DATABASE_URL`, so run
it locally or on the worker.

Worth real money: on props, **1 in 3 has 1–30 cents available elsewhere and 1
in 16 has 30+**.

## [ ] Surface the best book in Discord and the betslip

Depends on the item above. mike, 2026-08-30: *"the bet should pick the best
line for the bettor, across the main books, not just DK."*

Display and betslip only. The models keep DECIDING on DraftKings — every
threshold was swept on DK-implied edge, and best-of-N prices ~2pp cheaper in
implied probability, so adopting it as the qualifying price would loosen every
cut by that much with nobody deciding to (CLAUDE.md §6).

## [ ] [needs-decision] Re-sweep `mlb_live_total_runs` — the gate is CLEARED

**Measured 2026-09-04 (session 216): 95 settled BETs, every one carrying a DK
price, +12.99u — about +13.7% on flat stakes — most recent pick that same day.**
The item was written at 17 settled with the re-sweep due at ~50, so it is now
overdue rather than pending. (Query: `picks` where `model_id =
'mlb_live_total_runs' and signal_type = 'BET'`, result in ('WIN','LOSS','PUSH');
units gated on `dk_odds IS NOT NULL` per §6, though here nothing is unpriced.)

This is the nearest thing the live lane has to a real result, and CLAUDE.md §1b
cites it as promising-but-unproven — that citation is now stale by 8 bets and
should be refreshed from this number when someone touches it.

A threshold move needs a named human under §1b, so an agent may prepare the
sweep and report it but must not ship the cut.

## [ ] [needs-decision] Live odds feed

Measured 2026-08-30 against a direct DK capture: the Odds API lags DK's in-play
number by a median **54s**, worst **210s**, and missed two lines entirely
inside one 80-minute window. Polling faster cannot fix it — the staleness is on
their side.

Options are a vendor with a real publish clock (OddsPapi free tier, TheRundown
~$49/mo) or accepting the lag. Blocked on mike; needs a spend decision.

## [ ] Backtest a best-line decision basis

The honest version of "does a model rebuild improve things": re-score history
with best-of-N as the qualifying price and compare against the DK-only record,
per model, with the thresholds re-swept in the same pass.

Preliminary evidence says it will NOT help game lines — on 319 settled BETs, DK
was best or tied on **316**, and units at DK equal units at the best price
exactly. Props are the open question.

Substantial: a session's work, not a corner of one.

## [x] Backfill `player_game_log` for the games it never covered — CAUSE FOUND AND FIXED 2026-09-03

The pitcher-stats rebuild (`data/pitcher_stats_rebuild.py`) can only build a
row where `player_game_log` holds the start. It does not hold every game:

| season | completed games | both starters found | pct |
|---|---|---|---|
| 2019-2023 | ~2,500 each | ~2,200 | **86-89%** |
| 2024 | 2,520 | 2,058 | **81.7%** |
| 2025 | 2,518 | 1,889 | **75.0%** |
| 2026 | 2,007 | 1,873 | **93.3%** |

The largest single hole is systematic: **there is not one pgl pitcher row for
any game involving the White Sox or the Nationals before 2026** — not even the
opponent's starter. Those clubs' entire schedules are missing, which is ~638
games in 2024 alone.

The uncovered games now get no pitcher row and drop out of training, which is
the honest outcome but a real cost — the missingness is by CLUB, not at random,
and 2024's White Sox were 41-121, so the drop removes a set of very lopsided
games.

**The cause was not a missing feed. It was the backfill's own skip predicate.**
`backfill_player_game_log` skipped a whole DATE if `player_game_log` held any
row for it — and every MLB date carries ~15 games, so one ingested game marked
the entire date done and every other game on it was never fetched. Measured
before the fix: of 200 White Sox games in 2024, **200 sat on a date that already
had rows from other games, and 0 had rows of their own.**

That is `.claude/rules/data-integrity.md`'s jamming backfill in another shape —
a backfill must filter by the SAME predicate the worker applies, and the unit of
work here is a GAME.

Fixed 2026-09-03: the skip is now per `game_id`, pinned by
`tests/test_game_log_backfill_skip.py` (4 tests, 4 mutations, all caught).
`game_log_backfill` is registered in `tracking/job_queue.py` so the re-fetch
runs on the worker, which has the StatsAPI egress. Deterministic and free — no
paid API involved.

**Still to do: RUN it** (`enqueue(conn, "game_log_backfill",
{"start_season": 2019, "end_season": 2025})`), and only AFTER the fix is on
master and the worker has redeployed — a run against the old code would skip
everything and mark itself done. Then re-run
`python -m data.pitcher_stats_rebuild --force` to lift pitcher coverage from
75-89%, and re-measure.

## [ ] The daily pitcher last-3 lookup keys on `player_name`, not `player_id`

`_build_pitcher_rows` (`data/ingestors/mlb_stats_ingestor.py:562`) computes
`era_last3` with `WHERE player_name = ?`. Names collide: a query for `%Nola%`
in this repo returns two different pitchers, and the rebuild found the same
shape elsewhere. When two pitchers share a name the window silently mixes
them.

`player_id` is present on every row of both tables and is what
`data/pitcher_stats_rebuild.py` groups by. One-line change, but it alters a
served feature value, so it wants a measurement rather than a blind fix.

## [ ] [needs-decision] Make `era_last3` a true rolling last-three ERA

**This is a model update, not a repair, and it is mike's or matt's call.**

`era_last3` is not an ERA over the pitcher's last three starts. Both the daily
ingest and (deliberately) the rebuild compute it as `AVG(era)` over the last
three stored rows — the MEAN OF THREE SEASON-TO-DATE RATES, which is a smoothed
near-duplicate of `era` itself.

The rebuild replicates that on purpose. Serving will keep computing it that way
tomorrow morning, and `d_starter_era_last3` is ~21% of `mlb_f5_moneyline`'s
importance, so training on a truer statistic would measure a system nobody
deployed and silently redefine a fifth of the model.

The true rolling version is computable exactly from `player_game_log` and is
very likely a better feature — it carries information `era` does not, where
today it mostly restates it. Doing it properly means: fix the ingestor, rebuild
all seasons, recompute 2026, re-sweep the thresholds, and stamp it
`Updated-By:`. One decision, one owner, one session.

## [ ] Doubleheaders collide under one game_id, and their props land on top of each other

Found 2026-09-05 while designing the alternate-lines view. 1,546 (game,
market, player, book) keys since 2026-08-29 carry TWO rows at the same
`snapshot_at`, DraftKings included (163): `_build_game_id` is
`MLB_<date>_<away>_<home>`, so both games of DET@CLE on 2026-09-04 write
their props under `MLB_2026-09-04_DET_CLE`, and "the newest row" for Jose
Ramirez is whichever game's batch inserted last. The Odds API gives each game
its own event id; the game_id throws that away. Touches the odds ingestor,
the prop ingestor, `games`, the scorer's `_latest_dk_prop_row` and
settlement, so it is its own session: decide how a second game is keyed
(the app's `startedTeams` map already treats a team with a game still to
come as unstarted), then make both ingestors and the pick lock agree.

**Second symptom, found 2026-09-05 and CONTAINED, not fixed:** the collision
also duplicated PICKS. Game 1's final score settled a prop pick while game 2's
`commence_time` kept the pre-game cutoff open, and both locks released a pick
the moment it was graded — so every 10-minute pass wrote another copy. Eleven
rows for one Logan Allen Over 4.5 Hits, and 20 of the 132 settled BETs in the
published 09-01 window were copies (+7.38u published against +5.68u real). The
locks now key on a pick's EXISTENCE, the prop scorers skip a game that already
has a final score, and `uq_picks_one_row_per_pick` enforces one row per pick —
so the collision can no longer inflate the record. It can still put game 1's
score against game 2's pick, which is what this item is for.

## [ ] `picks.player_id` and `picks.is_live` exist in production and in neither schema file

Found 2026-09-05 writing tests against the real table. Both columns are read
and written all over the scorer, the views and the app, and neither
`data/db_setup.py`'s `SCHEMA_SQL` nor `data/supabase_schema.sql` declares
them — they were added by hand and never written back. So a first-time setup
builds a `picks` table the scorer cannot insert into, and every sqlite-backed
test has to ALTER them in (`tests/test_pick_lock_survives_settlement.py` does).
Small and mechanical: add both to each schema file, and check the same way for
every other column production has grown.

## [x] NCAAF player props have no ingest — DONE 2026-09-05

Raised when NCAAF alternates were approved with nothing to ride. Matt asked
what it meant and then "Yes do it", so
`data/ingestors/ncaaf_prop_odds_ingestor.py` exists: CFBD ids via
`resolve_odds_api_school`, `americanfootball_ncaaf`, the shared parser, and
`config.PROP_MARKETS_NCAAF` + the NCAAF alternates. Scoped to games
DraftKings already prices (measured: 120 games on a Saturday, 70 lined) under
a per-pass ceiling, and OFF (`RUN_NCAAF_PROP_ODDS=0`) until the probe's
measured cost is in front of Matt.

Still open underneath it: **no NCAAF prop MODEL.** These rows are research —
the Stats board's line column and betslip line legs. A college prop model is
its own piece of work, and would need the CFBD player log as its substrate.

## [ ] No slate-wide book-coverage answer the app can afford

Found 2026-09-05 building the Stats picker's coverage note. The board can say
"FanDuel posts no At-Most Hits lines today" for free, because it already holds
that stat's rows. It cannot say "FanDuel has nothing at all today" without
reading every market — and that read is not affordable: `explain analyze` on
`v_latest_prop_odds_all_books` grouped by book for one date measured **17.5s**,
and straight off `player_prop_odds` **8.5s** over 172,462 rows for 2026-09-05.
Both are far past what a screen (or the statement timeout) will take.

The fix is a small coverage table the prop ingestors maintain as they write —
`(game_date, sport, bookmaker, market, has_over, has_under, games)`, one row
per combination, refreshed each pass — which the app reads in milliseconds.

**2026-09-05 update:** most of that table now exists. `latest_prop_odds`
(migration `latest_line_state_tables`) holds one row per current line, so
"which books post which markets today" is `SELECT bookmaker, market, count(*)
FROM latest_prop_odds JOIN games USING (game_id) WHERE game_date = $1 GROUP BY
1, 2` — a few thousand rows, milliseconds. What is left is an RPC (or a tiny
view) for the app to call and the picker copy that reads it.
It would also give the Discord and monitoring surfaces a cheap answer to "which
books did we actually get tonight", which today is a table scan nobody runs.

Not needed for anything shipped yet: Matt's rule is that a book we pull lines
for stays in the picker whatever its depth (2026-09-05), so nothing currently
depends on the slate-wide answer.

---

## [ ] Two publishers can now post the same pick twice

Opened 2026-09-05 by #505, which made every pick-WRITER publish rather than
leaving it to the refresh pass. There are now two processes that can call
`notify_discord_signals` / `notify_signal_changes` for the same date: the
refresh pass (`worker`, at :17 and every 10 minutes in the evening) and the
pre-game line poller (`pollers`, every 30 seconds, whenever a tick writes a
BET). The NFL card jobs are a third.

`push_sent` is `UNIQUE(lock_key, kind)` and is written AFTER a successful post,
so it cannot stop a second POST that was already in flight — only the second
ledger row. Both producers read "unposted BETs", so if their reads straddle the
same ~1-2 second window the same pick goes to the channel twice.

Small: it needs both producers inside the same couple of seconds AND the same
pick. Not zero: the poller ticks 2,880 times a day.

The fix is a Postgres advisory lock around the publish sequence --
`pg_try_advisory_lock` on a fixed key at the top of
`tracking.signal_publisher.publish_new_signals`, skipping the run when it is
not acquired (the other producer is already doing it). For that to bind, the
refresh pass has to go through the same helper rather than calling the two
notifiers directly in `run_pipeline.step_push_notifications` -- which is the
§1b shape anyway (one helper, every caller), but it changes that step's
failure reporting, so it wants its own PR rather than being tacked on.

---

## [x] The locked-pick monitor has never written a row: the eval CSV and `picks` use different game_id shapes

**FIXED 2026-09-06** (same session that found it). `pick_eval.eval_row` now
normalises to the `NFL_`-prefixed id, which fixes wind and opener at once
because both feed that one helper. Pinned by
`tests/test_nfl_pick_monitor.py::TestTheJoinKeyMatchesPicks`, run against the
unfixed code first. Leaving this here for a week per the file's convention.

Found 2026-09-06 (mike, asking why the wind model was firing on nearly half the
Week 1 slate). `nfl_pick_status_history` holds **0 rows for every model**, and
`condition_status` is NULL on all five live `nfl_wind_totals` picks.

It is not a missing dump and it is not a schema problem. The monitor runs
cleanly on every hourly tick and says so:

```
04:00  START nfl-pick-monitor
       NFL pick monitor 2026-09-06: 0 locked pick(s) observed
       DONE  nfl-pick-monitor (exit 0)
```

— repeated at 05:01, 06:02, 07:03, 08:04, 09:04, 10:05, 11:06. It printed the
post-loop message rather than `no evaluation dump — nothing to do`, so the CSV
was read and had rows. The loop found none of them.

**The join key does not match.** `nfl/data_ingest/pick_eval.py` writes
`game_id` as the bare nflverse id and its own field comment calls it "the join
key to picks" — but `scripts/nfl_wind_publisher.py` writes
`game_id = f"NFL_{nflverse_id}"` (its module docstring says so at line 12). So
`current.get((game_id, model_id))` in `scripts/nfl_pick_monitor.py:latest_per_pick`
looks up `NFL_2026_01_CLE_JAX` in a dict keyed `2026_01_CLE_JAX` and misses
every time. `written` stays 0 and the run exits 0, which looks exactly like
"nothing changed".

**Why it is load-bearing.** Wind became insert-once on 2026-08-22 and the
scheduler comment justifies the lock with "every later tick records whether the
conditions still hold (`nfl_pick_status_history`) without touching the bet".
That sentence is currently false. A pick locked at a 12 mph forecast whose wind
collapses to 8 mph before kickoff is flagged nowhere — not in the table, not on
the pick, not in the app.

**It has already cost something concrete.** `CLE @ JAX Under 40.5` locked on
2026-09-05 at a **14.0 mph** forecast. The card's dry run the next day, still
seven days from kickoff, reads **4.3 mph** at the same stadium — the lowest on
the board. The pick stands (§1c, and correctly), but the premise for it is
gone, and there is nowhere that says so: not `nfl_pick_status_history`, not
`picks.condition_status`, not the app. That is the exact scenario
`nfl_pick_monitor`'s docstring describes as "the case this whole mechanism
exists for".

Fix is one line at the write side or the read side; prefer normalising in
`pick_eval.eval_row` so the CSV's own comment becomes true. **The test has to
watch it fail** (§1b): assert a published pick's `game_id` resolves against a
dump produced by `evaluate_board` — the current suite passes with the bug in.

## [x] 43 of the 2026 NFL schedule rows have a BLANK roof and are scored as open-air

**FIXED 2026-09-06.** `weather.open_air_mask` / `RETRACTABLE_STADIUMS`; a blank
roof at one of the five retractable venues is not eligible until the state is
known. The card's board went from 11 "outdoor" to 9 open-air on the Week 1
slate, dropping exactly BUF @ HOU and BAL @ IND. Pinned by four tests in
`tests/test_nfl_wind_fire_window.py`, including two that re-derive the venue set
from `games.csv` so the constant cannot drift. Leaving this here for a week.

Found alongside the item above. `nfl/data/games.csv` for season 2026:

```
outdoors 177   dome 52   (blank) 43
```

The 43 blanks are exactly five stadiums — `ATL97`, `DAL00`, `HOU00`, `IND00`,
`PHO00` — every one of them a **retractable** roof. Prior seasons carry `open`
or `closed` per game (128 and 621 rows), which is the roof state on the day;
2026 has not been played, so the state is empty.

`INDOOR_ROOFS = {"dome", "closed"}` and `select_bets` filters with
`~games.roof.isin(INDOOR_ROOFS)`, so a blank is **outdoor**. Two of the five
live Week 1 wind picks are on that basis:

| pick | stadium | roof in csv | forecast wind |
|---|---|---|---|
| BUF @ HOU Under 44.5 | HOU00 (NRG) | *(blank)* | 12 mph |
| BAL @ IND Under 48.5 | IND00 (Lucas Oil) | *(blank)* | 11 mph |

Both venues close the roof for most games. A wind under bet on a game played
under a closed roof has no premise at all — the forecast is for air the players
never stand in.

This inflates the fire rate on its own: it adds 2 games to an 11-game outdoor
denominator that should be 9, and both of them qualified.

Options, in order of honesty: treat a blank roof at a known retractable venue
as **not eligible** until the state is known (the model loses nothing — a
genuinely open roof re-qualifies once the state lands); or source the roof
state pre-game rather than from the schedule file. Do NOT default blank to
`outdoors`, which is what happens today by omission.

---

## [ ] Historical `sbr_consensus` odds ties are broken arbitrarily (2026-09-08)

**Not urgent, and deliberately not fixed inside the `pregame_total_line` work
that found it** — the fix rewrites training data for every MLB model, which is
a wider change than that PR was measuring.

Historical `sbr_consensus` rows carry a **date-only** `snapshot_at`
(`2025-10-13`, not a timestamp). A game therefore has two rows tying exactly on
`snapshot_at` — one `open`, one `close` — and every "latest pre-game price"
read picks between them arbitrarily:

| game | `_build_bulk_mlb_lookups` (training) | `_get_dk_odds` (serving) |
|---|---|---|
| MLB_2025-10-13_SEA_TOR | 7.0 (`close`) | 8.0 (`open`) |
| MLB_2025-10-09_PHI_LAD | 8.5 | 7.5 |
| MLB_2025-10-08_MIL_CHC | 6.5 | 7.0 |

8 of 40 sampled 2025 games disagree. DK-priced games are unaffected — they
carry full timestamps, and the same comparison on 60 2026 games is 60/60
identical — so this is historical training data only, never a live decision.

The fix is one ORDER BY term in both readers, applied together:
`snapshot_at DESC, CASE snapshot_type WHEN 'close' THEN 0 WHEN 'open' THEN 1
ELSE 2 END`. `close` is the right pre-game number on a tie.

**Before doing it, measure what moves.** It changes `total_line` and
`spread_home` for pre-2024 games in the training set of every MLB model, so it
is a retrain-scope change, not a cleanup.

---

## [ ] Two more shuffled-fold splitters, neither fixed here (2026-09-08)

Found while fixing the live Poisson CV leak
(`docs/mlb_volume_efficiency.md` §16). Both are the same shape — `KFold(shuffle=True)`
on rows that are not independent — and neither is as severe, so neither was
changed in that PR.

**1. The live BINARY branch tunes on randomly permuted rows.**
`train_live_model`'s binary path calls
`_xgb_objective(t, X_train[idx], y_train[idx], 1.0)`, where `idx` is
`rng.choice(...)` — a random subsample. `_xgb_objective` uses
`_time_ordered_cv`, whose own docstring warns: *"Requires the rows to be in
DATE ORDER... Without that sort this split is just an arbitrary partition
wearing a better name."* A random permutation is exactly that. It also carries
the play-row group leak, since it never sees `game_id`.

Not fixed because **both binary live models are retired** —
`mlb_live_win_prob` and `mlb_live_runline`, dropped 2026-08-30 as "badly
overconfident in production", which is the same symptom the Poisson model had
and now has a measured cause. If either is ever revived, fix this first: their
overconfidence was probably never about their features either.

The pre-game path is FINE and was checked, not assumed: `train_model` does
`df_train.sort_values("game_date", kind="mergesort")` at models/trainer.py:262
and passes the full `X_train` with no subsample, so its `_time_ordered_cv`
folds really are time-ordered.

**2. `_oof_predictions` estimates prop dispersion on shuffled folds.**
models/trainer.py:895, `KFold(n_splits=folds, shuffle=True)`, and its own
comment is about honesty: *"Dispersion is estimated from OUT-OF-FOLD
predictions, never from in-sample residuals: a fitted model's own residuals are
too small, which would make every predictive distribution too tight and every
P(over) overconfident."* That is precisely the failure the live model turned
out to have — and a shuffled fold is a weaker version of an in-sample residual.

Much less severe than the live case: a prop row is one player-game, so rows do
NOT share a label the way 64 plays of one game do. What they share is the
game's context columns, so the leak is real but small.

**Measure before changing it.** The size is knowable: compare each prop
model's OOF dispersion under shuffled vs group/time-ordered folds. If the
dispersion is materially larger under honest folds, every prop model's tail is
too tight and the fix is a retrain across all of them — not a one-line change.
