# Pre-publish sanity gate

Before any pick is posted to Discord or push (pre-game **and** live), the
signal list is filtered by `tracking.publish_sanity.filter_for_publish`.
Live lanes call `notify_discord_live` / `notify_live_signals` directly and
**bypass** `publish_new_signals`, so the gate is wired on those four send
paths, not only on the pre-game publisher.

This is a send-time refuse, the same shape as
`tracking.pick_integrity.refuse_mismatched`. It does not mutate `picks`,
does not ledger a refusal (the pick retries until the row is fixed), and
does not pause a model or change a unit size. Discord and push apply the
identical function.

Related, not this gate:

- Insert-time slate guard: `models/slate_concentration.py` (#747)
- Daily report-only monitor: `tracking/model_quality.py` / `docs/model_quality.md`

`last_refusals()` is an in-process hook toward model_quality later. Nothing
is written to `model_quality_checks` on the hot path. No new table.

## Kill switch

`RUN_PUBLISH_SANITY=0` (Railway variable; redeploy) disables the **new**
checks only. Integrity still runs. Canonical flag: `config.RUN_PUBLISH_SANITY`
(default on).

## Checks

| # | Check | When | Missing data |
|---|---|---|---|
| 1 | **pick_integrity** — label vs side/line | every pick, always | refuse (producer must supply side and line) |
| 2 | **Stakeability** — paused / retired / VOID / non-BET | every pick | fail closed on `config.PAUSED_MODELS` / `RETIRED_MODELS`; VOID only if `condition_status` is on the dict |
| 3 | **Stale clock** — pre-game after first pitch/kickoff; live outside `live_slate_dates()` | every pick | fail open (no commence / no game_date) |
| 4 | **Absurd price/line** — null/zero/invalid American odds; impossible totals/spreads | every pick | fail open if the producer did not supply any odds key (push live today) |
| 5 | **Same-game contradiction** — same model/lane posts both sides or Over+Under in one pass | every pick (list-level) | n/a |
| 6 | **One-sided public books** — tickets ≥70% on **this** side, n≥4 | every pick | fail open (no `public_bet_pct`). Aligns with the MLB handicap idea / `slate_concentration` / `model_quality` |
| 7 | **Already decided / dead bet** — e.g. Under when the score already cleared the total; game Final | live only | fail open (no scores) so a bad feed does not empty the board |
| 8 | **Money vs tickets skew** — tickets piled here, money is not (trap-side steam) | pregame | fail open |
| 9 | **Prop lineup** — confirmed Out/Doubtful/inactive, or `lineup_confirmed=False` | pregame props | fail open (unknown status) |
| 10 | **Outdoor total context** — Over from a non-wind model while extreme wind (≥20 mph, outdoor) is already on the card | pregame totals | fail open (no `wind_mph`) |
| 11 | **Too-good edge** — `abs(edge)` above `MAX_EDGE_CAP` / `LIVE_MAX_EDGE_CAP`, or a 4σ outlier vs supplied `recent_edges` | every pick | fail open (no `edge` key) |
| 12 | **First-signal lock** — a later row in the same pass that re-prices the locked BET is refused; the locked row is checked as-is | every pick (list-level) | keep the earliest `posted_at` / `created_at` |

Fail **closed** means a clear case is refused. Fail **open** means that
check is skipped so a missing feed cannot silently empty the board.

## What this is not

- An auto-pause or a unit bump.
- A second board. The pick stays in `picks`. The app still reads `picks`.
  A refused row is a bug that stays loud in ERROR logs until someone
  fixes it — the same contract as pick_integrity.
- A replacement for `live_publishable_sql`, the started-game / first-pitch
  guards, `publish_lock`, or `publish_keys`.
- A slow path. Deterministic, in-process, no LLM, no extra network. Live
  must stay well under 5 seconds.

Tests: `tests/test_publish_sanity.py`.
