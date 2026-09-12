---
paths:
  - "tracking/**"
  - "models/**"
  - "nfl/**"
  - "ncaaf_live/**"
  - "mobile/src/**"
  - "data/migrations/**"
  - "data/anon_readable.py"
  - "scripts/void_picks.py"
  - "scripts/backfill_publish_keys.py"
  - "config.py"
---

# Picks and publishing — a pick is a pick, and every surface shows the same ones

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

## THE PICK RULE — the mechanics (the rule itself is CLAUDE.md §1c)

Matt, 2026-08-29: *"a pick is a pick and if line movement makes it no longer a
pick we don't remove, it just means that the line has moved, but it existed at
one point, which is why timing is key."*

Once a model produces a BET at a line and a price, **that pick existed** and is
the bet of record. If the line then moves so the model would no longer take it,
that is LINE MOVEMENT. It does not retract the bet, does not change the number
that was given, and must never delete or overwrite the row. A user told to take
Over 44.5 at −115 was not told to take Over 54.5 at −120 — the second is a
DIFFERENT BET, and publishing it as though it were the first is misreporting
what the model said.

**The NFL rules (`docs/sports/nfl.md`) are the reference implementation.** `nfl_wind_totals` and
`nfl_opener_spread` are insert-once by construction: the pick locks the moment
it lands and is never re-priced. Every other model was brought to match:

| Scope | Flag | Locks at |
|---|---|---|
| NFL wind / opener | (insert-once by construction) | first qualifying card |
| Game-level picks | `LOCK_GAME_PICKS_AT_FIRST_RUN` | first scoring run of the day |
| Player props | `LOCK_PROP_PICKS_AT_FIRST_SIGNAL` | first signal on a confirmed lineup |
| Live / in-play | `LOCK_LIVE_PICKS_AT_FIRST_SIGNAL` | first live BET per (game, model) lane |

**Anything new must follow the same rule.** A new model, sport or lane does not
get to delete-and-replace its own picks. If you are writing a scorer loop, the
question to answer before it ships is: *when this re-runs and the line has
moved, what happens to the pick that already exists?* The only acceptable
answer is "nothing".

### Corollaries

- **Timing is data, not metadata.** `created_at` is when the number was
  available and is part of the pick's meaning. A restore or a backfill must
  preserve it; stamping today's clock on an old pick misreports the bet.
- **A "no longer qualifies" row is a display state, not a deletion.** NCAAF
  writes a NONE row carrying DK's live number and a reason (`docs/sports/ncaaf.md`); it never
  removes the game. Live lanes keep the locked BET standing after the lane
  closes.
- **Deletes that remain are scoped to rows that were never a pick**: dead-zone
  NONE rows for games that have not started, and the UFC/NCAAF look-ahead
  window, where picks are explicitly not yet locked and re-score until game
  morning (`docs/sports/{ufc,ncaaf}.md`). A BET is never in that set.
- **The audit log is the backstop.** `picks_log` records every INSERT and
  DELETE, so a pick destroyed by pre-lock churn is recoverable.
  `tracking/first_signal_repair.py` (`--step restore-first-signals`, and run on
  every NCAAF live-loop start) reads the first BET back out and restores it as
  the standing row, preserving the original `created_at` and clearing the
  notification ledger so the corrected pick is re-announced. Idempotent.

> **Not here on purpose:** the settled-record rule and the
> paused-model-visibility rule stay in CLAUDE.md §1c. A pause needs no file
> open at all, so a scoped copy would not load for the session that breaks
> them. `tests/test_settled_record_is_immutable.py` asserts they are there.

## THE PUBLISHING RULE — the app, Discord and push are identical

**THE APP, DISCORD AND PUSH SHOW THE SAME PICKS. THEY ARE IDENTICAL.**
(Matt, 2026-09-05: *"The app and discord should always show the same picks.
They should be identical."*) Every publishing surface reads **`picks`** and
applies the **same `model_action_thresholds` cut** the app's
`passesActionFilter` applies. A surface that reads anything else is a surface
that will disagree, and the disagreement is always silent.

A surface with an extra GATE can only lose rows, and does it silently —
`opening_signals` did, at 6 of 125 eligible BETs (`docs/rules_evidence.md`).

- **No publishing surface gets a date horizon.** A pick is publishable when its
  game has **not started**, however far ahead it was written. A horizon is a
  thing you can only fail at quietly.
- **`opening_signals` is the CLV / opening-signal shadow track, not a gate.**
  It keeps its own window (`docs/opening_signals.md`). Never publish from it.
- **The one guard that SHOULD bound the set is the started-game check** —
  announcing a pick once the game is under way sends the reader to a bet they
  cannot take.
- **A LIVE surface resolves its window with `config.live_slate_dates()`, never
  today** — a game keeps its KICKOFF's game_date, so a late start outlives the
  calendar day. Mirrored in the app by `liveSlateDatesET()`; the two are pinned
  by `tests/test_live_slate_midnight.py`.
- **ONE PUBLISHER AT A TIME — a ledger cannot PREVENT a duplicate, only record
  one.** Read → send → ledger is in that order deliberately, so two processes in
  one window both send and the second INSERT is swallowed: one row, two
  messages. Take `tracking/publish_lock.py`'s advisory lock — `pollers` and
  `worker` both publish, so this is live.
- **ONE PICK, ONE KEY — and two picks are never one key.** Every surface
  identifies a pick by the synthesised `push_sent.lock_key`, which is UNIQUE per
  `kind`, so two picks that share a key are ONE pick: the second is not delayed,
  it is gone. Mint it ONLY from `tracking/publish_keys.py`, and when a model
  writes a NEW identity column, add it there — `nfl_prop_market` writes
  `player_key` + `prop_market` and no `player_id`, so a whole game's props
  collapsed onto one key (`docs/discord.md`). Changing the key is a data
  migration, not a code change: re-ledger the already-published picks
  (`scripts/backfill_publish_keys.py`) BEFORE the code ships, or every one of
  them republishes.
- **A VOIDED pick is not publishable and not displayable** (§1c). Excluded in
  the publishers' SQL and in the app's `passesActionFilter`. Only `'VOID'` —
  NCAAF's `'OK'` / `'GONE'` are live states on real picks.
- **A new surface is a line in the parity tests**, not a copied query:
  `tests/test_{nfl_lookahead_signals,publish_key_identity,publisher_lock}.py`.
- **LIVE PICKS POST TO THEIR SPORT'S LIVE CHANNEL.** (mike, 2026-09-09:
  *"Push picks to discord in live games to their live channels."*) Every
  in-play model announces its BETs there, and a new in-play model that writes
  `is_live` picks without calling `notify_discord_live` is the NFL bug of
  2026-09-05 again. Webhooks, fallbacks and the routing: `docs/discord.md`.
