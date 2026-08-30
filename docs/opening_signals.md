# Opening-signal shadow track

> Moved out of CLAUDE.md on 2026-08-30 (that file had reached 909 KB and was
> being re-read in full every session). Content is verbatim unless noted.
> Session-by-session history: `docs/sessions/`.

## 25. Opening-Signal Shadow Track (line/public movement comparison)
The live `picks` table is delete+rescored every hourly refresh, so a game/market
flips in and out of BET as the line moves. This shadow track answers Matt's
question: lock the **first** BET cross, then measure how the line moved (public
betting / sharp money) after we locked, and compare that record to chasing the
live line. **Shadow only — it never touches the live `picks` flow, settlement
totals, or the go-live gate.**

| Piece | Where | What |
|---|---|---|
| `opening_signals` table | schema (SQLite + Supabase) | one locked row per `lock_key` (`game:model` for game markets, `game:model:player` for props); UNIQUE → first BET cross wins, later refreshes + side flips can't overwrite |
| Capture | `tracking/opening_signals.capture_opening_signals` | `INSERT … SELECT … ON CONFLICT (lock_key) DO NOTHING` from current live BET picks; **excludes live (in-play) picks**. Pipeline `--step opening-signals`, runs **last** (after all game + prop scoring) in the daily flow and every hourly refresh |
| Settle | `tracking/opening_signals.settle_opening_signals` | called inside `paper_tracker.settle_picks` (game-level markets only). Reuses `_compute_result` + `_closing_dk_odds`. Fills result/P&L (vs the **opening** dk_odds + scored_line), `clv_pct` (close vs open), `line_move_dir` (toward/against/flat, ±0.5pp), `public_side` (with_public ≥55 / contrarian ≤45 / even, from the locked split). **NOT folded into the live settle totals.** |
| Report | `python -m tracking.opening_report [--since 2026-04-14]` | opening-track vs live-track win%/ROI/units/CLV, plus the opening track sliced by line-move direction and public side |

**Conventions / caveats:**
- `line_move_dir` is from our pick's perspective: `clv_pct > +0.5pp` = the price
  moved **toward** us (we beat the close); `< -0.5pp` = against.
- Props are **captured** (data accrues) but **not settled** here yet — phase 1 is
  game-level, where line-move + public splits actually apply. Settle props in a
  follow-up if the comparison proves useful.
- Public-side slicing only covers full-game ML/spread/totals (Action Network,
  best-effort) — props/F5/golf/UFC have no public split → `public_side` NULL.
- Migration `add_opening_signals_shadow_track` (applied 2026-06-20); SQL also at
  `data/migrations/add_opening_signals_shadow_track.sql`. RLS on + anon read.

---
