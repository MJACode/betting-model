# MLB totals public-fade (paper)

Fade a public OVER pile, bet UNDER. **Not** an unpause of `mlb_over_under`.
**Not** `mlb_total_market` (that card is Pin fair − soft implied).

Code: `models/mlb_total_public_fade.py`, `scripts/mlb_total_public_fade_card.py`.
Runs on the same pipeline step as the other MLB game-line cards
(`mlb-game-market` / refresh_pass) and as `--step mlb-total-public-fade`.

**Selective recut (2026-09-19 grid):** blunt t70 flooded 12/12 on
2026-09-19 (those 12 are VOID). The ticket × juice × holdout grid is
`docs/mlb_total_public_fade_selective.md`. Recommended paper rule:
**over tickets ≥ 90, juice any, max 3 / slate.** Defaults in config stay
70 / any / unlimited. Do not flip `PUBLISH`.

## The card

| Piece | Rule |
|---|---|
| Source | `public_betting` consensus totals, **last** snapshot with `snapshot_at < commence_time` |
| Trigger | OVER tickets ≥ `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` (default **70**; **80** and **90** supported) |
| Juice | `MLB_TOTAL_PUBLIC_FADE_JUICE` default **any** (grid rejected every floor) |
| Slate cap | `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` default unlimited; recommended paper **3** |
| Side | Always UNDER |
| Price | Best open under among DK / FD / MGM / WH (`williamhill_us`) at **DK’s open total**; fallback DK |
| Line | Main total **5.5–14.5** |
| Price window | Under American in **[-200, 200]** |
| INSERT | `MLB_TOTAL_PUBLIC_FADE_PUBLISH` default **0** |
| Slate guard | After candidate BETs: if one `pick_side` is **≥70%** of that model's BET count **and** n_bet **≥ 4**, **suppress all** (skip INSERT / notify). Shared helper: `models/slate_concentration.py`. |

As-of is offset-aware (`_parse_iso_ts`). A lexicographic compare on
`public_betting.snapshot_at` (`-04:00`) vs `games.commence_time` (`+00:00`)
is a leak — the same trap as `docs/mlb_market_handicap_features.md`.
A snapshot stamped **at** commence is refused (`<`, not `<=`).

Lock is insert-once per `(game_id, model_id)` (§1c). A later tick must not
replace the under that was taken.

**Slate concentration / sanity guard** (2026-09-19). This card only ever
bets UNDER. On 2026-09-19 it wrote `signal_type=BET` under on **12/12**
games (public over tickets 75–95% everywhere) and notified the board.
`models/slate_concentration.py` runs after candidate BETs are built and
before INSERT/notify. Trigger: one `pick_side` ≥ **70%** of that model's
BET count on the slate **and** n_bet ≥ **4**. Policy for this fade:
**suppress all** (safer than top-K). A mixed slate that is not
concentrated is untouched — 3 unders of 8 still publish the 3 that
cleared the ticket cut. The helper is reusable by other game-market
cards; they may choose `top_k` (K=2) instead. A WARN logs
`n_bet`, `n_under`, `n_over`, `threshold`. The guard does not delete or
rewrite a pick that already exists.

`mlb_over_under` and `mlb_runline` stay in `PAUSED_MODELS`. This id is **not**
in `GAME_MARKET_GATE_MODELS` — a public-steam overlay would veto the fade.

Stored `edge` on the pick is **(over tickets − 50) / 100**, not a calibrated
probability edge. Stake is a flat 1 unit (`recommended_bet` = 100).
`ACTION_THRESHOLDS` is 0/0 so the action filter does not invent a second cut;
the ticket threshold lives in the finder / env.

## Backtest (specified 2026-09-16)

Window 2026-05-31 → 2026-09-16, pre-commence public ∩ DK open:

| Cut | n | Units | ROI |
|---|---|---|---|
| t70 | 64 | **+5.43u** | **+8.5%** |
| t70 and under ≥ −115 | 56 | **+6.02u** | **+10.8%** |
| Blind under, same universe | | | ~**+2.3%** |

Monthly at t70: Jun **+7.3%**, Jul **+16.5%**.

This pass independently measured (Supabase, 2026-09-16):
`public_betting` totals-over **1,369** games, 2026-05-31→09-16;
**99** of those have `snapshot_at::timestamptz < commence_time`. That is the
coverage caveat, not a re-grade of the table above.

## Caveats (load-bearing)

1. **136 honest pre-commence public games as of 2026-09-19**, not a
   season (Jun 59, Jul 25, Aug **0**, Sep 52). Action Network splits
   start 2026-05-31. **Zero rows in 2019–2025.** The 2026-09-16 note of
   ~85–99 is the same table before Sep 16–19 honest coverage landed.
2. `public_betting` is `UNIQUE(game_id, market, side, book)` — last upsert
   wins. Hourly refresh historically overwrote the pre-game split with a
   post-start fetch (August honest coverage: 0). The ingestor now
   refuses post-start upserts; **already-overwritten history stays unusable**.
3. The 2026-09-16 t70 +8.5% / 64 is the overwrite leftover. Re-grade
   2026-09-19: t70 +5.0% / 101 overall, **−11.5% / 43** on complete-
   coverage days, **−15.8% / 34** in September. See
   `docs/mlb_total_public_fade_selective.md`.
4. Do **not** set `MLB_TOTAL_PUBLIC_FADE_PUBLISH=1` without mike. Default 0
   means the worker logs flags and writes nothing. Railway is 0 after the
   2026-09-19 all-under card; **leave default 0** until mike says
   otherwise. The slate guard is not a substitute for that gate.
5. Do **not** unpause `mlb_over_under` / `mlb_runline` from this file.
6. An all-under (or ≥70% one-side) slate of 4+ BETs is suppressed in full.
   That is a sanity bound, not a new ticket cut.

## Env (Railway; redeploy after setting)

| Variable | Default | Meaning |
|---|---|---|
| `MLB_TOTAL_PUBLIC_FADE_PUBLISH` | `0` | `1` writes BET rows |
| `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` | `70` | Over-ticket cut; recommended paper **90** |
| `MLB_TOTAL_PUBLIC_FADE_JUICE` | `any` | `any` / `ge_m115` / `ge_m110` / `ge_m105` / `plus` |
| `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` | empty | Max unders per date; recommended paper **3** |
