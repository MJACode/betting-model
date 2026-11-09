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
| Juice band | Optional. `MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN` / `_MAX` default **unset = no band**. I24 is **[-110, -100]** inclusive on the shopped under. Finder applies it **before** top-K. |
| INSERT | `MLB_TOTAL_PUBLIC_FADE_PUBLISH` default **0** |
| Top-K | Optional. `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` default **0** = all-pass. Set **2** + `RANK=ticket` to keep the two heaviest OVER piles per day. Runs **before** the slate guard. |
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

**Top-2 flags** (the 2026-09-19 recommendation; no longer one since
2026-10-10: 78 bets −1.4%, September −27.6% on 27, see the note below;
PUBLISH stays 0):

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

*Later (2026-10-10):* with the whole of September and October, ticket
top-2 at 70% is **78 bets, −1.11u, −1.4%** (Jun +15.5%/28, Jul +9.8%/14,
Sep −27.6%/27, Oct +6.9%/9). At 80% without a band it is 69 bets, +2.08u,
+3.0%, with the same red September (−27.6% on 27). Every game at 70% is
214 bets, −6.70u, −3.1% (Sep −12.9% on 138). The June and July plus did
not survive the first full month of pre-game public data. Measured with
the query in the I24 re-measure below, with the cut changed and the band
removed.

## I24 juice band (2026-09-19)

#751 measured **one-sided juice floors** (under ≥ −115 / −110 / −105 /
plus-money). Every floor was worse than `any`. That is a **floor**,
not a band: it keeps plus-money and only drops heavy juice.

**I24 is a narrow band**, different: over tickets ≥ **80** (existing
`TICKET_PCT`) and the shopped under American in **[−110, −100]**
inclusive. Top-K (`MAX_PER_SLATE` / `RANK=ticket`) and the
concentration guard stay as on master. Unset env is no band so merge
does not recut the card.

The figure first written here for I24 was **38 bets, +9.51u, +25%, with
June, July and September all positive**. It came from a different price
source from the one the live card uses, and on the live card's prices the
band loses money. Removed 2026-10-10; see "I24 re-measured on the live
card's prices" below.

A posted **+100** is even money (`implied(+100) == implied(−100)`) and
sits on the cap; **+105** is plus-money past the cap and is out.

**Not steam_cap2.** That construction is tickets ≥75 AND
money ≥ tickets, juice **floor** ≥ −115, cap 2. Regrade of the first
honest Sep pregame public (2026-09-16→18): **5 settled, 2-3, −1.18u,
−23.6%** (Jun +12.0%/12, Jul +12.5%/7). September failed. Do not ship
steam_cap2 from this file. (This paragraph also said I24 was "the band
that stayed positive across Jun/Jul/Sep"; that was removed 2026-10-10.)

**I24 band settings** (not a recommendation: red on the live card's
prices, below; the write switch has been off since 2026-09-19):

```
MLB_TOTAL_PUBLIC_FADE_TICKET_PCT=80
MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN=-110
MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX=-100
MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE=2
MLB_TOTAL_PUBLIC_FADE_RANK=ticket
MLB_TOTAL_PUBLIC_FADE_PUBLISH=0
```

## I24 re-measured on the live card's prices (2026-10-10)

From PR #760 and PR #759 (2026-09-19, never merged), measured again to the
end of the season on 2026-10-10 with the read-only query at the end of this
section. Every figure in the table was reproduced that day: the first two
rows by that query, the last two by the same query with each game's first
DraftKings quote in place of the shopped latest quote.

**What the live card does.** The finder (`find_fade_bets`) takes each
book's latest pre-game quote (`load_latest_quotes`: `snapshot_type='open'`,
`snapshot_at <= commence_time`, newest first), shops the under at
DraftKings' total among DraftKings, FanDuel, BetMGM and William Hill,
applies the band to that shopped price, and only then keeps the two
heaviest over piles a day (`select_top_k`). The +9.51u figure used each
game's first DraftKings quote only, and had no daily limit.

| Construction | Games | Bets | Units | ROI | By month |
|---|---|---|---|---|---|
| **The live card:** latest quote, 4 books, band, then top 2 a day | every settled game to Oct 10 | **49** | **−6.19u** | **−12.6%** | Jun +3.9%/15, Jul −35.5%/6, Sep −22.0%/25, Oct +28.4%/3 |
| Latest quote, 4 books, band, every qualifying game (no slate guard) | every settled game to Oct 10 | 86 | −9.82u | −11.4% | Jun −2.6%/16, Jul −44.7%/7, Sep −11.9%/60, Oct +28.4%/3 |
| First DraftKings quote only, band, every game: the documented figure | to Sep 18 | 41 | +9.51u | +23.2% | Jun +32.0%/20, Jul +28.6%/9, Sep +4.5%/12 |
| The same, after the figure was written | Sep 19 to Oct 10 | 54 | −0.46u | −0.8% | Sep −2.7%/48, Oct +13.9%/6 |

The documented figure's units reproduce exactly on 41 bets, not 38. So the
+25% came from a price source the card does not use, and it did not hold
even on that source once it was written.

Two results from PR #760 that were not re-run here:

- PR #759 reported I24 at 22 bets, −12.2%. It kept the top 2 a day first
  and applied the band afterwards, which is not the live order. (The review
  of #759 re-ran that order to the end of the season: 37 bets, −10.8%.)
- A sweep of 60 stricter settings (85, 90 and 95% tickets; narrower bands
  inside [−110, −100]; top 1; at least 2 bets before the concentration
  guard applies) found none with at least 40 bets and every month positive.
  That was on 2026-09-19, with three days of September.

**Live record.** `picks` holds 49 rows for this model, all written Sep 16
to 19: 15-21-1 and −7.19u over 37 settled, plus 12 NO_ACTION rows from
2026-09-19. PR #760 reads them as the all-pass card at 70% tickets, not
I24. The last row was written 2026-09-19 at 04:24 UTC; the Railway write
switch read False from 14:25 UTC that day (`config.py`, the "CORRECTED
THE SAME DAY" comment).

**To run it again** (read-only; one call, inside the production statement
timeout). Change the ticket cut in `sp`, delete the band line for no band,
or change the `values (0), (2)` list for a different daily limit.

```sql
-- I24 as the live card builds it, through every settled game (read-only).
-- Over tickets >= 80 (consensus split taken before first pitch); each
-- book's latest pre-game quote; DraftKings' total in [5.5, 14.5]; the
-- under shopped at that total among DK, FanDuel, BetMGM and William Hill,
-- price in [-200, 200]; band [-110, -100] by implied probability (a posted
-- +100 is inside); then the two heaviest over piles a day.
with sp as materialized (
  select pb.game_id, g.game_date gd, g.commence_time ct,
         to_char(g.commence_time::timestamptz at time zone 'UTC',
                 'YYYY-MM-DD"T"HH24:MI:SS"Z"') ct_utc,
         g.home_score::float + g.away_score::float total_runs,
         pb.public_bet_pct::float over_tix
  from public_betting pb
  join games g on g.game_id = pb.game_id
  where pb.market = 'totals' and pb.side = 'over' and pb.book = 'consensus'
    and g.sport = 'MLB'
    and pb.snapshot_at::timestamptz < g.commence_time::timestamptz
    and g.home_score is not null and g.away_score is not null
    and pb.public_bet_pct >= 80                       -- ticket cut
), q as materialized (
  select sp.game_id, b.bk, b.ord, l.tl, l.up
  from sp
  cross join (values ('draftkings', 1), ('fanduel', 2), ('betmgm', 3),
                     ('williamhill_us', 4)) b(bk, ord)
  join lateral (
    select o.total_line::float tl, o.under_price::float up
    from odds o
    where o.game_id = sp.game_id and o.market = 'totals' and o.bookmaker = b.bk
      and o.snapshot_at <= sp.ct_utc                  -- lets the index stop early
      and o.snapshot_type = 'open'
      and o.snapshot_at::timestamptz <= sp.ct::timestamptz
    order by o.snapshot_at desc limit 1) l on true
), dk as (
  select game_id, tl from q where bk = 'draftkings' and tl between 5.5 and 14.5
), shop as (
  select dk.game_id, dk.tl, q.up, i.imp,
         row_number() over (partition by dk.game_id order by i.imp, q.ord) rn
  from dk join q on q.game_id = dk.game_id and q.tl = dk.tl
  cross join lateral (select case when q.up > 0 then 100 / (q.up + 100)
                                  else -q.up / (-q.up + 100) end) i(imp)
  where q.up between -200 and 200
), bets as (
  select sp.gd, sp.game_id, sp.over_tix,
         case when sp.total_runs < s.tl
                then case when s.up > 0 then s.up / 100.0 else 100.0 / abs(s.up) end
              when sp.total_runs = s.tl then 0.0 else -1.0 end units
  from sp join shop s on s.game_id = sp.game_id and s.rn = 1
  where s.imp <= 110.0 / 210.0 and s.imp >= 0.5       -- band; delete for no band
), ranked as (
  select b.*, row_number() over (partition by gd
                                 order by over_tix desc, game_id desc) day_rank
  from bets b
)
select case when k.k = 0 then 'every game' else 'top 2 a day' end construction,
       coalesce(substr(gd, 1, 7), 'all') as mon, count(*) as bets,
       round(sum(units)::numeric, 2) units,
       round(100 * sum(units)::numeric / count(*), 1) roi_pct
from ranked cross join (values (0), (2)) k(k)
where k.k = 0 or day_rank <= k.k
group by grouping sets ((k.k, substr(gd, 1, 7)), (k.k))
order by 1, 2;
```

## Caveats (load-bearing)

1. **Pre-game public coverage is thin and has a hole.** Games with a
   consensus totals split taken before first pitch, re-counted 2026-10-10:
   Jun 59, Jul 25, **Aug 0**, Sep 154, Oct 17; 255 in all, 252 with a final
   score. It was ~85–99 when this card was built. Action Network splits
   start 2026-05-31. **Zero rows in 2019–2025.**
2. `public_betting` is `UNIQUE(game_id, market, side, book)` — last upsert
   wins. Hourly refresh historically overwrote the pre-game split with a
   post-start fetch (August honest coverage: 2 games). The ingestor now
   refuses post-start upserts; **already-overwritten history stays unusable**.
3. n is small. The 2026-09-16 t70 cell was 64; the 2026-09-19 remasure
   is 101 all-pass / 48 ticket-top-2. I24 (t80 + [−110, −100]) was 38 on
   2026-09-19; on the live card's prices it is 49 through 2026-10-10 (the
   re-measure table above).
   t80 is an env, not a second model.
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
| `MLB_TOTAL_PUBLIC_FADE_TICKET_PCT` | `70` | Over-ticket cut; `80` is the tighter neighbour |
| `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` | `0` | `0` = all-pass. Set `2` to keep top-K per day (recommended with `RANK=ticket` on 2026-09-19; red in September, 78 bets −1.4% through 2026-10-10) |
| `MLB_TOTAL_PUBLIC_FADE_RANK` | `ticket` | `ticket` \| `gap` \| `juice` \| `composite` \| `ev`. Only `ticket` cleared the holdout. `ev` without a bucket table ranks as ticket |
| `MLB_TOTAL_PUBLIC_FADE_EDGE_FLOOR` | `0` | LOMO estimated-edge floor. Sweep-only (card has no bucket table). Every floor tried (≥2/3/5pp) lost |
| `MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN` | unset | Inclusive American band lower bound (most juice). I24 = `-110`. Unset = no band |
| `MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX` | unset | Inclusive American band upper bound (least juice). I24 = `-100`. Unset = no band |
