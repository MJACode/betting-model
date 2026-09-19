# MLB totals public-fade (paper)

Fade a public OVER pile, bet UNDER. **Not** an unpause of `mlb_over_under`.
**Not** `mlb_total_market` (that card is Pin fair − soft implied).

Code: `models/mlb_total_public_fade.py`, `scripts/mlb_total_public_fade_card.py`.
Re-grade: `python -m scripts.mlb_total_public_fade_select`.
Runs on the same pipeline step as the other MLB game-line cards
(`mlb-game-market` / refresh_pass) and as `--step mlb-total-public-fade`.

## The card (2026-09-19 steam rule)

| Piece | New rule (`RULE=steam`, default) | Old blunt rule (`RULE=blunt`) |
|---|---|---|
| Source | `public_betting` consensus totals, **last** snapshot with `snapshot_at < commence_time` | same |
| Trigger | OVER tickets ≥ **75** **and** OVER money ≥ OVER tickets (public steam on the over) | OVER tickets ≥ `TICKET_PCT` (default **70**; **80** supported) |
| Juice floor | **off** (`MIN_UNDER_PRICE` unset). `−115` is opt-in and **failed** month holdout | none (window only) |
| Slate cap | hard max **2** BETs, ranked by over_tix then juice (lower implied) | none — every game that clears the cut |
| Side | Always UNDER | Always UNDER |
| Price | Best open under among DK / FD / MGM / WH at **DK’s open total**; fallback DK | same |
| Line | Main total **5.5–14.5** | same |
| Price window | Under American in **[-200, 200]** | same |
| INSERT | `MLB_TOTAL_PUBLIC_FADE_PUBLISH` default **0** | same |
| Slate guard | After candidate BETs: if one `pick_side` is **≥70%** of that model's BET count **and** n_bet **≥ 4**, **suppress all**. Shared helper: `models/slate_concentration.py`. | same |

The blunt rule is the 2026-09-16 card. It is still the `blunt` env. It is
not the default because it is ~80–86% of the honest public universe and
wrote UNDER on **12/12** games on 2026-09-19.

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
**suppress all**. The steam cap of 2 usually keeps n_bet below 4, so the
guard is the backstop for `blunt` or `MAX_PER_SLATE=0`. A WARN logs
`n_bet`, `n_under`, `n_over`, `threshold`. The guard does not delete or
rewrite a pick that already exists.

`mlb_over_under` and `mlb_runline` stay in `PAUSED_MODELS`. This id is **not**
in `GAME_MARKET_GATE_MODELS` — a public-steam overlay would veto the fade.

Stored `edge` on the pick is **(over tickets − 50) / 100**, not a calibrated
probability edge. Stake is a flat 1 unit (`recommended_bet` = 100).
`ACTION_THRESHOLDS` is 0/0 so the action filter does not invent a second cut;
the ticket / steam cut lives in the finder / env.

## Measured cells (Supabase, 2026-09-19)

Honest pre-commence public ∩ DK open ∩ line 5.5–14.5 ∩ shopped under among
DK/FD/MGM/WH, settled through 2026-09-18. Window of public coverage:
2026-06-08→07-11 and 2026-09-16→09-18 (Action Network last-upsert; July–mid
September overwritten). Query: `scripts/mlb_total_public_fade_select.py`.

Priced settled universe **n=118**. Blind under on that universe: 62-53-3,
**+3.2%**.

| Rule | n | W-L | Units | ROI | Share of universe |
|---|---|---|---|---|---|
| **steam75, money ≥ tix** | **42** | 25-17 | **+5.61u** | **+13.4%** | 36.5% |
| steam75 + juice ≥ −115 | 37 | 20-17 | +1.39u | +3.8% | 32.2% |
| steam75 + cap 2 / slate | 28 | 16-12 | +2.38u | +8.5% | — |
| steam75 + juice ≥ −115 + cap 2 | 24 | 12-12 | −0.88u | −3.7% | — |
| blunt t70 | 99 | 55-44 | +6.25u | +6.3% | **86.1%** |
| t80 + juice ≥ −115 | 71 | 38-33 | +2.10u | +3.0% | **61.7%** |
| top-1-by-tix among t70 | 26 | 14-12 | +0.82u | +3.2% | 22.6% |
| tix ≥75 and (tix − money) ≥ 10 | 7 | 4-3 | +0.84u | +12.1% | 6.1% |

Known early SQL, replicated here:

- steam75 money ≥ tix → under: brief said ~n=42 +9.5%. **This pass: n=42
  +13.4%** (shopped 4-book price, not a flat −110). First incomplete shop
  (missing 2026-06-12/15 DK) was n=40 +9.5% — that is the cell the brief
  named.
- blunt ≥70: brief said ~+2.8% and ~80% of universe. **This pass: +6.3%
  and 86.1%.** Concentration matches; ROI moved with the missing June
  shops and September. Still the all-slate rule.
- ≥80 with juice ≥ −115: brief said ~+6.7% but >50% of universe.
  **This pass: +3.0% and 61.7%.** Concentration matches; September
  dragged the ROI.

Earlier specified backtest (2026-09-16 card, t70, window through 09-16
only): n=64 +5.43u +8.5%; t70 and under ≥ −115 n=56 +6.02u +10.8%.
That table is the blunt card at the date it shipped. It is not this
rule.

### Month holdout + bootstrap (5,000, seed 19)

**steam75 (no juice, no cap)** — the only cell with every hold month ≥ 0
and every train-without-month > 0:

| Hold out | Train | Test |
|---|---|---|
| 2026-06 | n=26 +3.1% | n=16 **+29.9%** |
| 2026-07 | n=35 +13.9% | n=7 **+10.8%** |
| 2026-09 | n=23 +24.1% | n=19 **+0.3%** |

Bootstrap: mean **+13.4%**, 95% CI **[−14.5, +41.1]**, P(ROI>0)=**0.82**.
The CI still spans zero. n=42 is thin.

**steam75 + juice ≥ −115** (the brief's primary candidate) **fails** as
a tighter cut: pooled +3.8%; hold 2026-07 **−1.3%**; bootstrap P+=0.57,
CI [−27, +35]. The floor drops the juiced steam bets that were +EV.

**steam75 + cap 2** (the anti-spam constraint on the steam cell): pooled
+8.5%; hold 2026-06 +25.6%, 2026-07 +10.8%, **2026-09 −36.8%** (n=6).
September's top-2 by tickets were the wrong games. Cap 2 is a product
bound against whole-slate spam, not a ROI peak. Combined with the
concentration suppress it is what the card fires.

**blunt t70** hold 2026-09 **−12.7%** on 33 bets (the 09-16…18 all-under
days). That is why it is no longer the default.

**top-1-by-tix** and **ticket−money gap ≥ 10** were searched after the
juice floor failed. Top-1 is −/flat. Gap≥10 is n=7 — too thin to ship
as the rule.

## Why steam, not blunt

Blunt ≥70 is a board, not a selection. 86% of the honest public games
clear it, so a 12-game slate becomes 12 unders. Steam (money piled on
the same side as the tickets, at a 75 floor) is 36% of that universe,
replicated the brief's n=42 cell, and is the only neighbourhood that
survives a month split without going negative.

A −115 juice floor looked cleaner and did not survive the same split.
It stays an env (`MLB_TOTAL_PUBLIC_FADE_MIN_UNDER_PRICE=-115`) so it
can be re-measured; it is **not** on.

## Caveats (load-bearing)

1. **~118 priced pre-commence public games**, not a season. Action
   Network splits start 2026-05-31. **Zero rows in 2019–2025.** Honest
   coverage is June–early July plus mid-September; hourly refresh
   historically overwrote the rest.
2. `public_betting` is `UNIQUE(game_id, market, side, book)` — last upsert
   wins. Already-overwritten history stays unusable.
3. n=42 is small. The bootstrap CI for steam75 includes zero. This is a
   **paper** rule.
4. Do **not** set `MLB_TOTAL_PUBLIC_FADE_PUBLISH=1` without mike. Default 0
   means the worker logs flags and writes nothing. Railway is 0 after the
   2026-09-19 all-under card; **leave default 0** until mike says
   otherwise. The steam cap and the slate guard are not a substitute
   for that gate.
5. Do **not** unpause `mlb_over_under` / `mlb_runline` from this file.
6. An all-under (or ≥70% one-side) slate of 4+ BETs is suppressed in full.
   That is a sanity bound, not a new ticket cut.

## Env (Railway; redeploy after setting)

| Variable | Default | Meaning |
|---|---|---|
| `MLB_TOTAL_PUBLIC_FADE_PUBLISH` | `0` | `1` writes BET rows |
| `MLB_TOTAL_PUBLIC_FADE_RULE` | `steam` | `steam` or `blunt` |
| `MLB_TOTAL_PUBLIC_FADE_STEAM_TICKETS` | `75` | Steam over-ticket floor |
| `MLB_TOTAL_PUBLIC_FADE_REQUIRE_MONEY_STEAM` | `1` | Steam requires money ≥ tickets |
| `MLB_TOTAL_PUBLIC_FADE_MIN_UNDER_PRICE` | unset | Optional American juice floor. `−115` failed holdout |
| `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` | `2` | Steam hard cap. `0` = unlimited |
| `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` | `70` | Blunt over-ticket cut; `80` is the tighter neighbour |
