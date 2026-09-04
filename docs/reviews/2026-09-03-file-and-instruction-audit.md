# Audit — archivable files, and whether the instruction set is too complex

> Requested by Matt, 2026-09-03: *"are there any unused project files that can be
> archived, is the instruction set too complex or ok?"*
>
> **Analysis only — nothing was moved, deleted or archived.** Two questions, two
> verdicts. Method for question 1 is in §4 so the numbers can be re-derived.
>
> Supabase and Railway MCP connectors are unauthenticated in this session, so
> `model_registry` could not be queried; that gates exactly one recommendation
> (§1.2) and is flagged in place.

---

## Verdict, up front

**Question 1 — unused files: yes, but not where it looks.** The interesting
answer is not a list of dead scripts. It is that **98% of the tracked repo is two
directories**, and one of them is described in the docs at 1/56th of its real
size. Dead code exists (about a dozen files) but it is rounding error by bytes
and only a mild cognitive tax.

**Question 2 — instruction set: it is fine, and the architecture is genuinely
good.** ~33.5 KB always-loaded, path-scoped rules on top, a test that pins the
size, and a clean split with no duplication. The concern worth holding is not
complexity, it is **regrowth rate**: it has been trimmed twice in five days.

---

## 1. What is actually taking up the repo

Tracked working tree: **934 MB across 7,683 files.**

| path | MB | files | share |
|---|---:|---:|---:|
| `nfl/data/` | 721.0 | 6,796 | **77.2%** |
| `models/saved/` | 193.9 | 74 | **20.8%** |
| everything else — all source, docs, tests, mobile | ~19 | ~810 | 2.0% |

### 1.1 `nfl/data/odds_cache/` — 668 MB, and the doc says 12 MB

`docs/sports/nfl.md:24` states:

> *"`nfl/data/odds_cache/` (2,632 snapshots, ~12MB) is IRREPLACEABLE — ~45,000
> Odds API credits"*

Measured today: **6,769 files, 668 MB.** That is 2.6× the file count and **56×
the size**.

The mechanism is a bulk import, not drift. `git ls-tree` at the 2026-08-15
commit shows exactly 2,632 files, so the doc was accurate when written; only
four commits have ever added to the directory (one on 08-15, three on 08-22),
and the jump landed in those. Per-file size went from ~4.5 KB to ~99 KB, which
fits the "47 books" widening noted in `docs/nfl_props_build_prompt.md:63` —
more books and markets per snapshot, not more snapshots over time. **No addition
after 2026-08-22 was found**, so this is a step change that the doc never
caught up with, not ongoing unbounded growth.

This matters beyond tidiness, because the sentence is doing decision-making work.
It is the justification for keeping the cache in git ("irreplaceable, and small
enough that committing it is the protection scheme"). At 12 MB that trade is
obviously right. At 668 MB — **71% of everything tracked, in a repo every clone
and every Railway build pulls** — it is a different trade that nobody has
actually made.

Two further points, both from the repo's own rules:

- **CLAUDE.md §1b says extracted data belongs in Supabase.** `odds_cache` is
  named in `docs/rules_evidence.md:139` as still outside, "protected, but by a
  different scheme". That scheme is git, which has no integrity verification —
  unlike `nfl_live_prop_snapshots`, which has checksummed rows and a `--verify`
  flag. The better home already exists and is already built.
- **It is live, not dead.** `nfl/scripts/replay_wind_card.py:79` (touched
  2026-09-03) and `replay_opener_card.py:72` read it directly, at zero credit
  cost. So this is a **relocation** candidate, not a deletion one — move it to
  Supabase with the existing snapshot scheme, keep a thin local cache, and let
  the replay scripts read through.

**Recommendation:** correct `docs/sports/nfl.md:24` first — that is a one-line
fix and it is currently misinforming every decision about the largest asset in
the repo. Then decide the storage question with the real number in hand.

### 1.2 `models/saved/` — 51 MB of superseded artifacts

74 tracked artifacts, 194 MB. Of those, **17 files / 51.2 MB are superseded
versions** — an older `.pkl` sitting beside a newer one for the same model:

| model | keeping | older tracked | MB |
|---|---|---:|---:|
| `mlb_prop_batter_sb` | 20260611 | 1 | **30.4** |
| `mlb_runline` | 20260823 | 3 | 5.3 |
| `mlb_moneyline` | 20260903 | 2 | 4.8 |
| `ncaaf_spread` | 20260828 | 3 | 3.6 |
| `ncaaf_over_under` | 20260825 | 3 | 2.3 |
| `mlb_f5_moneyline` | 20260903 | 1 | 1.9 |
| `mlb_prop_pitcher_k` | 20260903 | 2 | 1.2 |
| `mlb_over_under` | 20260704 | 1 | 0.9 |
| `wnba_prop_player_assists` | 20260831 | 1 | 0.9 |

`.gitignore` already carries the convention ("delete the old .pkl"); it is just
not being followed. The 30.4 MB `mlb_prop_batter_sb_20260513` was flagged in the
2026-08-30 review and is still there.

**One check before moving any of these, and it needs Supabase auth:** confirm no
`model_registry` row still points at an older path. A deactivated row that still
carries the path is fine; an *active* one is not. The rule that makes this
non-obvious is CLAUDE.md §7 — a registry row pointing at a missing artifact
silently stops a model scoring, and that has already cost a month of picks.
Until that query runs, treat these as **archive candidates, not confirmed dead**.

---

## 2. Genuinely unused code and docs

Method in §4. These are the files that survive a reachability walk from real
entrypoints **and** have no reference in any non-historical file. Small by bytes;
the value of moving them is that a future reader stops treating them as live.

### 2.1 Dead one-off scripts — high confidence

`nfl/scripts/` holds eight files last touched **2026-08-15**, unreachable from
any entrypoint, and referenced **nowhere at all — not even in the session log**:

`backfill_bettime.py`, `backfill_closing.py`, `backtest_clv.py`, `bias_scan.py`,
`build_odds_all_books.py`, `build_odds_table.py`, `crosscheck_sbr.py`,
`replay_opener_card.py`

These are the one-off backfills and probes from the original NFL import. Note
`replay_opener_card.py` reads `odds_cache` (§1.1), so if the cache moves it needs
either updating or archiving — it cannot silently stay as-is.

Same shape, elsewhere: `scripts/ncaaf_search/profile_data.py`,
`scripts/nfl_prop_timing.py`, `scripts/live_model_holdout_compare.py`,
`nfl/live_model/backtest/flow_robustness.py`.

### 2.2 `email/` — a preview generator with no delivery path

`email/render_picks_email.py` (329 lines) plus `email/preview.html`. Its own
docstring says `--live` is *"not implemented yet"*, and nothing outside the
module references it — no scheduler job, no pipeline step, no workflow. The last
commit touching it (2026-08-29) was incidental, part of the "drop paper trading"
sweep. The 2026-08-30 review flagged `preview.html:386` as still carrying stale
"Paper trading · Not real money" copy; that is still true, and it is stale copy
in a file nothing generates.

Either the email is a live plan — in which case `--live` is an open task, not an
archive candidate — or it is not, and both files move to `docs/history/`. **That
one is your call, not a technical finding.**

### 2.3 Plan and prompt docs whose work has shipped

`docs/history/` already exists as the archive location; these are the four that
belong there:

| file | KB | last touched | why |
|---|---:|---|---|
| `docs/ncaaf_model_plan.md` | 12.6 | 2026-08-30 | NCAAF shipped, then the models it plans were replaced twice (classifier → margin regression → cross-book opener). Only reference is a comment in `data/migrations/add_ncaaf_tables.sql:2`. |
| `docs/retrain_2026_plan.md` | 12.7 | 2026-08-30 | the 2026 retrains happened. One reference, a `config.py:1398` "see" pointer. |
| `docs/nfl_props_build_prompt.md` | 6.3 | 2026-08-22 | a build prompt; `docs/nfl_props_model.md:7` opens with *"This answers `docs/nfl_props_build_prompt.md`"*. The answer shipped and is 50 KB. |
| `docs/prediction_markets_eval.md` | 3.7 | 2026-06-19 | an evaluation that concluded. Nothing since. |

**Explicitly NOT archivable, despite looking similar** — each is load-bearing
right now and I checked each individually:
`team_stats_leak.md` (14 refs incl. `.claude/rules/data-integrity.md`),
`team_stats_rebuild_scope.md`, `activate_opp_starter_features.md` and
`docs/patches/` (still an open item in `followups.md:302` and four pending jobs
in `jobs/declared_jobs.json`), `market_movement_features.md`,
`model_state_assessment.md`, `ncaaf_search_findings.md`.

### 2.4 Two small loose ends

- **`render.yaml`** — a Render.com blueprint. Deployment is Railway
  (`railway.json`, `Procfile`). Its only reference is `docs/cloud_worker.md:314`
  offering it as "Option A". If Render is not a live fallback, it is vestigial;
  if it is, the doc should say so rather than presenting two equal options.
- **`dk_mlb_sample.json`** — 164 KB of DraftKings sample payload at the repo
  root. Untracked when I last looked on 2026-08-30; it has since been
  **committed**. Nothing references it. It is either a fixture (belongs in
  `tests/fixtures/`) or a scratch artifact (belongs nowhere).

### 2.5 What the scan says is NOT dead

Three things that look archivable and are not — worth recording so they do not
get re-proposed:

- **`dashboard/app.py`** — last touched 2026-09-02, guarded by
  `tests/test_retired_models.py:126` and `tests/test_worker_deps.py`. The Retool
  port (sessions 193–194) did *not* supersede it, and the new
  `requirements-dashboard.txt` is a deliberate split that keeps 176 MB of
  Streamlit/plotly off the worker. That is a good change, not a leftover.
- **`scripts/ncaaf_search/`** — unreachable from any entrypoint because it is a
  research harness run by hand, not a pipeline step. It is the best
  methodological asset in the repo (see the 2026-08-30 review §1) and should be
  used *more*, not archived.
- **`docs/sports/{golf,ufc,mlb}.md`** — read as zero-reference only because
  CLAUDE.md points at them with a brace glob rather than by name.

---

## 3. Is the instruction set too complex?

**No. It is in good shape, and the split done on 2026-09-03 was the right
move.** The measurements:

| | bytes | loaded |
|---|---:|---|
| `CLAUDE.md` | 33,504 | every session |
| `.claude/rules/data-integrity.md` | 6,796 | opening `data/`, `models/`, `tracking/`, `monitoring/` |
| `.claude/rules/operations.md` | 4,351 | opening the pipeline, scheduler, scripts |
| `.claude/rules/analysis-and-thresholds.md` | 2,406 | opening `models/`, `scripts/` |
| `.claude/rules/frontend.md` | 1,136 | opening `mobile/src/`, `mobile/docs/` |

**Floor ~33.5 KB (~8k tokens); realistic ceiling ~47 KB on a session that touches
data, models and the pipeline at once.** Against the 225k tokens this file was
costing on 2026-08-30, that is a 95%+ reduction and it is not close to a problem.

**Four things that are specifically well done:**

1. **The path-scoped mechanism is the right answer to the growth question**, and
   the reasoning in `tests/test_claude_rules_split.py` is correct on a subtle
   point: a rule delivered when the matching file is opened is *more* reliably
   applied than a line 700 lines into a startup read. Scoping is not a demotion.
2. **The split left no duplicate.** I checked §7 — the data-integrity and
   operations rules genuinely left CLAUDE.md, replaced by a pointer that explains
   where they went and why. Two homes for one rule is the failure mode here and
   it was avoided.
3. **The size cap is a real test, not a comment.** `tests/test_claude_md_size.py`
   pins `MAX_BYTES = 36_000` and passes at 34,375 — about **1.6 KB of headroom**.
   The test's own note ("if this fails, the fix is almost never to raise the
   limit") is the correct instinct.
4. **Every rule file is asserted to be path-scoped.** A rule file without
   `paths:` loads unconditionally and silently re-creates the cost — the test
   catches exactly that.

**Two observations, neither of which is "too complex":**

- **The regrowth rate is the thing to watch, not the size.** CLAUDE.md was
  45,605 B on 2026-09-03, trimmed to 39,377, then to 34,375 — two trims in one
  day, four days after the 909 KB → 39 KB split. The cap has been lowered
  45,000 → 41,000 → 36,000 in the same window. **The file is being actively held
  down rather than naturally staying down**, and the 1.6 KB of headroom is about
  two rules. That is fine as long as the ratchet keeps being applied; it is worth
  knowing that the mechanism currently working is discipline plus a test, not
  equilibrium.
- **§1b is 9,732 bytes — 29% of the file, and nearly 3× the next section.** It
  is the one place where rule and evidence still sit together (the credit-ceiling
  story, the sandbox-limits story, the Supabase story each carry their narrative
  inline) even though `docs/rules_evidence.md` now exists for exactly that. If
  more headroom is ever needed, that is where it is — and the rules themselves
  do not have to move.

**One asymmetry worth naming.** The *instruction set* is disciplined and capped.
The *docs corpus* it points at is 72 markdown files and 1.8 MB, with no
equivalent pressure: `docs/sessions/2026-08.md` alone is 476 KB and
`2026-09.md` reached 164 KB in three days. That is by design — sessions are
grep-only, never loaded — and the design is sound. But nothing currently prunes
or rolls up the session log, so it will keep growing at roughly 200 KB/month.
Not urgent; worth a rollup convention before it is 5 MB.

---

## 4. Method (so the numbers can be re-derived)

- **Reachability:** AST-walked imports from real entrypoints — `scheduler.py`,
  `run_pipeline.py`, `config.py`, every `python -m <mod>` and `python <path>.py`
  string in tracked `.sh`/`.yml`/`.json`/`Procfile`/`railway.json`, plus
  CLAUDE.md §5, `docs/local_ops.md` and `docs/cloud_worker.md`. Test files are
  their own roots, since pytest discovers by path and they would otherwise all
  read as orphans (this is why a naive scan returns ~94 false positives).
- **Reference counting deliberately EXCLUDES `docs/sessions/`, `docs/history/`
  and `docs/reviews/`.** A dead script mentioned once in a June session entry
  otherwise reads as "referenced". Inverted, that exclusion is the best signal
  available: *referenced only in the session log* is close to a definition of
  archivable.
- **Staleness:** `git log -1 --format=%cs -- <file>` per file.
- **Caveats:** the `nfl/` package executes with `cwd=nfl/`, so its internal
  imports resolve differently and the walk under-reports reachability there — I
  hand-checked every `nfl/` file I named. And basename reference counting is
  noisy for generic names (`build.py`, `config.py`, `models.py`), so nothing was
  proposed on that signal alone.

---

## 5. Suggested order, if you want to act

1. **Fix `docs/sports/nfl.md:24`** — 2,632 snapshots / ~12 MB → 6,769 / 668 MB.
   One line, and it currently misinforms the biggest storage decision in the repo.
2. **Archive the eight dead `nfl/scripts/` one-offs** plus the four in §2.1.
   Zero references anywhere, including the session log.
3. **Move the four shipped plan/prompt docs to `docs/history/`** (§2.3).
4. **Resolve `dk_mlb_sample.json`** — `tests/fixtures/` or gone.
5. **Decide on `email/`** — live plan or archive. Your call.
6. **Query `model_registry` for active rows pointing at superseded `.pkl`
   paths**, then archive the 17 files / 51 MB (§1.2). Needs Supabase auth.
7. **Decide the `odds_cache` storage question** with the corrected number
   (§1.1). This is the only item that changes the repo's shape.
8. **Leave the instruction set alone.** If you want headroom later, §1b's
   inline evidence is the place, and `docs/rules_evidence.md` is already the
   destination.

---

*Written 2026-09-03. Analysis only — no file was moved, deleted or archived, and
no code was changed. The pre-existing uncommitted work in the tree (session 210's
live-quote guard) was not touched.*
