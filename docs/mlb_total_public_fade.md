# MLB totals public-fade (paper)

Fade a public OVER pile, bet UNDER. **Not** an unpause of `mlb_over_under`.
**Not** `mlb_total_market` (that card is Pin fair − soft implied).

Code: `models/mlb_total_public_fade.py`, `scripts/mlb_total_public_fade_card.py`.
Runs on the same pipeline step as the other MLB game-line cards
(`mlb-game-market` / refresh_pass) and as `--step mlb-total-public-fade`.

## The card

| Piece | Rule |
|---|---|
| Source | `public_betting` consensus totals, **last** snapshot with `snapshot_at < commence_time` |
| Trigger | OVER tickets ≥ `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` (default **70**; **80** supported) |
| Side | Always UNDER |
| Price | Best open under among DK / FD / MGM / WH (`williamhill_us`) at **DK’s open total**; fallback DK |
| Line | Main total **5.5–14.5** |
| Price window | Under American in **[-200, 200]** |
| INSERT | `MLB_TOTAL_PUBLIC_FADE_PUBLISH` default **0** |
| Top-K | **Always on.** `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` is clamped to **1 or 2** (default **2**, `RANK=ticket`). 0 is not all-pass. Runs **before** the slate guard. |
| Slate guard | After ranking: if one `pick_side` is **≥70%** of that model's BET count **and** n_bet **≥ 4**, **suppress all**. Shared helper: `models/slate_concentration.py`. |

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

## Top-K remeasure (2026-09-19)

The 2026-09-16 card is whole-slate. On 2026-09-19 that was 12/12 UNDER.
This pass ranked the same finder universe and kept top-1 / top-2 per
`game_date`. Prices are leak-bounded **open** (`snapshot_type='open'`
and `snapshot_at::timestamptz <= commence_time`). September
`latest_odds` is late juice (−500 to −10000) and is not this board.

**Coverage (Supabase, 2026-09-19).** `public_betting` totals-over
consensus **1,406** games; **136** pre-commence. Monthly pre / post:
May 0/15, Jun 59/341, Jul 25/317, **Aug 0/397**, Sep 52/200. Graded
intersection with a shopped DK-line under in [5.5, 14.5] × [−200, 200]:
**106** at t65, **101** at t70. August is empty. September is three
settled days (16–18), not a month.

**t70 all-pass vs top-K** (flat 1 unit, pushes in *n*, ROI = units/*n*):

| Construction | n | Units | ROI | max/day |
|---|---|---|---|---|
| all-pass t70 | 101 | **+5.92u** | **+5.9%** | 15 |
| ticket top-1 | 26 | +2.72u | +10.5% | 1 |
| **ticket top-2** | **48** | **+5.37u** | **+11.2%** | **2** |
| t80 ticket top-2 | 42 | +7.46u | +17.8% | 2 |
| t90 ticket top-2 | 27 | +5.38u | +19.9% | 2 |
| gap top-2 | 48 | +1.60u | +3.3% | 2 |
| juice top-2 | 48 | −4.52u | −9.4% | 2 |
| composite top-2 | 48 | +1.79u | +3.7% | 2 |
| LOMO-EV top-2 | 48 | −0.10u | −0.2% | 2 |
| LOMO-EV top-1 | 26 | −2.86u | −11.0% | 1 |
| edge floor ≥2pp (LOMO, all-pass) | 53 | −9.16u | −17.3% | 9 |
| under ≥ −115 | 86 | −3.02u | −3.5% | 14 |
| suppress-all (drop days n≥4) | 29 | −0.40u | −1.4% | 3 |

Ticket top-2 is the only ranking whose neighbourhood stays positive
(t70 / t80 / t90 top-2 all +). Gap, juice, the juice-adjusted
composite, and month-holdout EV (bucket wr − implied) do not. The
2026-09-16 juice floor (under ≥ −115, then +10.8%) is **−3.5%** on
this board — September killed it. The 2026-09-19 suppress-all guard
is **−1.4%**: it keeps only thin slates and throws away the days
that printed.

**Month holdout (ticket top-2, t70 pool):**

| Month | all-pass ROI | ticket top-2 ROI |
|---|---|---|
| Jun | +15.8% / 47 | +15.5% / 28 |
| Jul | +15.0% / 20 | +9.8% / 14 |
| Sep (16–18 only) | −13.3% / 34 | −5.8% / 6 |

Jun+Jul all-pass +15.6% / 67 vs ticket top-2 +13.6% / 42 — ranking
gives back some units for a 2-bet cap. September all-pass is the
bleed; top-2 cuts it. Wilson on the pooled top-2 cell is 44–71%
win rate (28–20). n=48 is still small.

**Recommended flag (PUBLISH stays 0):**

```
MLB_TOTAL_PUBLIC_FADE_TICKET_PCT=70
MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE=2
MLB_TOTAL_PUBLIC_FADE_RANK=ticket
MLB_TOTAL_PUBLIC_FADE_EDGE_FLOOR=0
```

t80 + top-2 is the tighter neighbour (+17.8% / 42), not a second
model. Do not set RANK to gap / juice / composite / ev — those
cells are in the fail table above. Sweep:
`python -m scripts.mlb_total_public_fade_topk`.

## t75 ∩ juice ≥ −115 top-1 (2026-09-19 month chunks)

Prior signal: top-1/day among over tickets ≥75 and under ≥ −115
looked ~+18% on n~23, September thin. Re-graded on leak-bounded
opens, chunk SQL Jun / Jul / Sep (Sep 16–18 settled; Sep 19
unsettled and excluded; three 09-18 west-coast scores still NULL
and excluded).

**t75 ∩ ≥ −115 pool** (flat 1 unit):

| Construction | n | Units | ROI | max/day |
|---|---:|---:|---:|---:|
| all-pass | 87 | +2.43u | +2.8% | 14 |
| **ticket top-1** | **24** | **+1.36u** | **+5.7%** | **1** |
| ticket top-2 | 45 | +1.38u | +3.1% | 2 |
| gap top-1 | 24 | −2.50u | −10.4% | 1 |
| juice top-1 | 24 | −2.17u | −9.0% | 1 |
| composite top-1 | 24 | −2.46u | −10.3% | 1 |

**Month chunks (ticket top-1):**

| Month | all-pass | ticket top-1 |
|---|---|---|
| Jun | +8.0% / 42 | **+19.4% / 13** |
| Jul | −2.4% / 16 | −0.8% / 8 |
| Sep 16–18 | −1.9% / 29 | −36.4% / 3 |

Jun+Jul ticket top-1 is **+11.7% / 21**, not +18% / ~23. The ~+18%
cell is **June alone**. July is flat. September is three days and
the three heaviest piles went 1-2: `CHC vs ATL Under 7.5` LOSS,
`CWS vs DET Under 8.5` WIN, `BAL vs MIL Under 8.0` LOSS. Gap /
juice / composite stay negative on this pool too.

Do **not** move the ticket cut to 75 or add a −115 juice floor.
That pool + top-1 is weaker than t70 ticket top-2 on the wider
board (+11.2% / 48). Rank stays `ticket`. Cap stays 2.

## Caveats (load-bearing)

1. **~85–99 pre-commence public games in the DB**, not a season. Action
   Network splits start 2026-05-31. **Zero rows in 2019–2025.**
2. `public_betting` is `UNIQUE(game_id, market, side, book)` — last upsert
   wins. Hourly refresh historically overwrote the pre-game split with a
   post-start fetch (August honest coverage: 2 games). The ingestor now
   refuses post-start upserts; **already-overwritten history stays unusable**.
3. n is small. The 2026-09-16 t70 cell was 64; the 2026-09-19 remasure
   is 101 all-pass / 48 ticket-top-2. t80 is an env, not a second model.
4. Do **not** set `MLB_TOTAL_PUBLIC_FADE_PUBLISH=1` without mike. Default 0
   means the worker logs flags and writes nothing. Railway is 0 after the
   2026-09-19 all-under card; **leave default 0** until mike says
   otherwise. The slate guard is not a substitute for that gate.
5. Do **not** unpause `mlb_over_under` / `mlb_runline` from this file.
6. An all-under (or ≥70% one-side) slate of 4+ BETs is suppressed in full.
   That is a sanity bound, not a new ticket cut. With the 1–2 cap the
   guard is a backstop; ranking is what stops a twelve-under card.

## Env (Railway; redeploy after setting)

| Variable | Default | Meaning |
|---|---|---|
| `MLB_TOTAL_PUBLIC_FADE_PUBLISH` | `0` | `1` writes BET rows |
| `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` | `70` | Over-ticket cut; `80` is the tighter neighbour |
| `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` | `2` | Clamped to 1 or 2. 0 / >2 become 2. The card never all-passes |
| `MLB_TOTAL_PUBLIC_FADE_RANK` | `ticket` | `ticket` \| `gap` \| `juice` \| `composite` \| `ev`. Only `ticket` cleared the holdout. `ev` without a bucket table ranks as ticket |
| `MLB_TOTAL_PUBLIC_FADE_EDGE_FLOOR` | `0` | LOMO estimated-edge floor. Sweep-only (card has no bucket table). Every floor tried (≥2/3/5pp) lost |
