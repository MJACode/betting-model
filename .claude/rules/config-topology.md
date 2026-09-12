---
paths:
  - "config.py"
  - "data/threshold_sync.py"
  - "models/scorer.py"
  - "models/live_scorer.py"
  - "ncaaf_live/**"
  - "nfl/live_model/**"
  - "scheduler.py"
  - ".env"
---

# Config topology — where each kind of setting actually lives

> **Path-scoped rule file.** It loads into context the moment Claude opens a
> file matching the paths above, and costs nothing on a session that never
> touches them. Moved out of CLAUDE.md on 2026-09-12, verbatim — the rule is
> unchanged. CLAUDE.md keeps a one-line pointer so a session that never opens
> these paths still knows the rule exists.
>
> **A rule only belongs here if it can ONLY be broken by editing one of these
> files.** Anything reachable without opening a file — pausing a model, running
> SQL, answering a question — must stay in CLAUDE.md, or it will not load for
> the session that breaks it. That is not hypothetical: a pause erased 55
> settled bets on 2026-09-12, and that session opened none of these paths.
> Measured story: `docs/rules_evidence.md`.

Three homes, three roles. Getting this wrong is how a threshold change
silently fails to reach production.

**Secrets → Railway Variables** (the live copy the worker reads): `DATABASE_URL`
(Supabase **session pooler** string), `ODDS_API_KEY`, `DATAGOLF_API_KEY`,
`CFBD_API_KEY`, `FETCH_F5_LIVE=1`, `TZ=America/New_York`, plus the loop kill
switches (`RUN_LIVE_LOOP`, `RUN_NFL_WIND_CARD`, `LIVE_DAILY_CREDIT_CAP`). The
same keys also sit in the local `.env` for manual CLI runs.
**Railway env edits only take effect on redeploy.** `docs/cloud_worker.md` is the
source of truth for the variable list.

**Thresholds → canonical in `config.py`, mirrored to Supabase.** The scorer reads
`config.py` directly, so the BET decision is config-canonical wherever the code
runs. `data.threshold_sync` (Step 0c of the daily pipeline) mirrors it into the
`model_action_thresholds` table, which the app action filter and the track-record
views read. **A hand edit to that table is temporary** — the next daily run
overwrites it from `config.py` on master. To change a cut permanently, edit
`config.py` and merge; to make it live immediately, edit the table AND merge
before the next 6am run.

**Sportsbooks → `config.py`, env-overridable.** `LINE_SHOP_BOOKMAKERS` drives the
Odds API `bookmakers` param (the `us2` books cost a second region — measured,
`docs/best_line.md` §2); `BEST_LINE_BOOKMAKERS` is the set a pick may be DECIDED
at, and it excludes the books a member cannot bet.

### Two invariants that must not be broken

- **A PICK IS DECIDED, SIZED AND SETTLED AT THE BEST BETTABLE PRICE, AND THE
  ROW SAYS WHICH PRICE AND WHOSE LINE.** (mike, 2026-09-09: *"we should remove
  DK only - we want best lines for us regardless"*; the in-play models joined
  2026-09-10, *"yes do everything"*.) The decision runs at the best price
  across `config.BEST_LINE_BOOKMAKERS` at the line, stored as
  `picks.decision_book / decision_odds / decision_implied_prob /
  decision_edge`; settlement, the record views, the RPCs, Discord, push and
  the app's action filter all read them as `COALESCE(decision_x, dk_x)`
  (pre-2026-09-09 rows were decided at DraftKings, so the fallback is exact).
  **DraftKings stays the REFERENCE:** training features and CLV are DK-to-DK,
  and `edge` / `dk_odds` keep their DraftKings meaning. No cut moved with
  either change. One code path per model decides at both prices —
  `scorer._decide` / `_size`, `live_scorer.classify_live_signal`,
  `ncaaf_live.serve.LiveEngine._decide` — with the stale-line cap always on
  the DraftKings edge. `nfl_live_prop` stays DraftKings-only (its feed carries
  no other book). Detail and the measurements: `docs/best_line.md`. Tests:
  `tests/test_{decide_on_best_price,best_line_live}.py`.
- **A PLAYER PROP DRAFTKINGS DOES NOT LIST IS SCORED OFF THE FIRST BETTABLE
  BOOK THAT DOES.** (mike, 2026-09-12: *"Yes, scoring of other books lines."*)
  Book taken in `BEST_LINE_BOOKMAKERS` order, NEVER by price — the LINE is the
  proposition, so choosing the book by the number would choose the bet to suit
  the model. `picks.line_book` names it, NULL = DraftKings, and on those rows
  **`dk_odds` / `dk_implied_prob` / `edge` are NULL / 0.0 by design**, so every
  read of a pick's price or edge goes through `decision_*` and the
  published-units gate reads `COALESCE(decision_odds, dk_odds)`. GAME markets
  are unchanged: a game-level DraftKings line is a model FEATURE, so changing
  its source is a retrain question. **These picks are a new population — no cut
  was swept on it — so report them separately, by `line_book`.**
  `SCORE_OFF_ANY_BOOK_LINE=0` restores "no DraftKings quote, no pick".
  Test: `tests/test_score_off_any_book_line.py`.
- **`picks.profit_flat` FABRICATES -110 FOR ANY PICK WITH NO PRICE.** (2026-09-03.)
  A win with `dk_odds IS NULL` (and, since 2026-09-09, `decision_odds IS NULL`)
  is stored as +$90.91 on a $100 stake — exactly the payout of -110 — so
  `profit_flat` is NOT a safe units source on its own. **Any read of
  `profit_flat` must be gated on `dk_odds IS NOT NULL`.**
  `mv_scored_pick_outcomes.profit_units` is correctly NULL for these. Evidence,
  and the 261 affected BETs: `docs/rules_evidence.md`.

- **ACCESS IS DECIDED IN ONE PLACE, AND IT IS NOT THE SUBSCRIPTIONS TABLE.**
  (2026-08-30, Matt.) A membership bought on Discord (Whop) entitles the app,
  and an app subscription entitles the Discord — so `subscriptions` only ever
  holds half the answer. The gate is `public.my_access()` / `has_app_access()`
  server-side and `useEntitlement()` in the app; gating on
  `useSubscription().entitled` charges a Discord member twice for what they
  already bought. Revocation follows the same rule in reverse, with one
  refinement that must not be lost: **each side revokes only the Discord role
  it granted**, so a lapsed App Store subscription cannot strip a member who is
  still paying Whop. Detail: `mobile/docs/DISCORD_LINKING.md`.
- **Pre-game and in-play prices never mix.** In-play rows are written with
  `snapshot_type='in_play'` and are excluded from pre-game scoring, training
  features and closing-line math. Separately, the evening refresh keeps writing
  `open` rows AFTER first pitch, so any read of a "pre-game" line must also bound
  on `snapshot_at <= commence_time` — see the leak trap in §7.

Full detail (retention and pruning, best-line mechanics, machine paths):
`docs/config_topology.md`.
