# MLB totals: the search for a second betting rule (2026-09-19)

> **Provenance.** From PR #759 (2026-09-19, never merged), carried to
> master 2026-10-10 as a write-up only; its 1,029-line measurement script
> and tests were not kept. On 2026-09-19 the search had only three days of
> September with a public split taken before first pitch, so where the
> whole season has since been measured, this page gives the whole-season
> figure and says so. Figures marked **2026-09-19** are the PR's and were
> not re-run.

**The question.** Is there a bettable MLB totals rule other than the
public-over fade (`docs/mlb_total_public_fade.md`)? `mlb_over_under` was
paused; this looked at rules built on market data instead of a trained
model.

**The answer: no.** Nothing met the bar, and the full September made the
closest misses worse, not better. No model, cut or publish switch was
changed.

**The bar** (the same one the run-line search used,
`docs/mlb_runline_edge_hunt.md`): at least 40 bets; at least two months
with bets, and every one of them positive; positive overall; at most 4 bets
a day; and not a lone good setting whose neighbours fail (for example, a
top-3-a-day rule whose top-2 and top-4 versions lose). August counts as
missing, not red: its pre-game public splits were overwritten.

**Coverage.** Games with a consensus totals split taken before first
pitch, re-counted 2026-10-10: Jun 59, Jul 25, Aug 0, Sep 154, Oct 17; 252
with a final score. On 2026-09-19 it was 123 settled games, 39 of them in
September.

---

## What was tried

| Approach | Result | Measured |
|---|---|---|
| Fade the public over (bet the under), 70% of tickets, every game | 214 bets, **−3.1%**. Jun +15.8% on 47, Jul +15.0% on 20, **Sep −12.9% on 138**, Oct +6.9% on 9 | 2026-10-10, whole season |
| Same, the two heaviest over piles a day, 70% | 78 bets, −1.4%. **Sep −27.6% on 27** | 2026-10-10, whole season |
| Same, top 2 a day, 80% | 69 bets, +3.0%. Jun +29.4% on 25, Jul +4.1% on 11, **Sep −27.6% on 27**, Oct +28.8% on 6 | 2026-10-10, whole season |
| The narrow price band on the under, −110 to −100 (I24), as the live card builds it | 49 bets, **−12.6%** | 2026-10-10; detail in `docs/mlb_total_public_fade.md` |
| Ticket share combined with price bands: under priced −120 to −100, top 2 a day | 70% tickets: 74 bets, +0.5%. Jun +26.7% on 27, Jul +2.4% on 13, **Sep −26.0% on 26**, Oct −5.3% on 8. 80% tickets: 65 bets, +5.4%. Jun +42.5% on 24, **Jul −5.9% on 10**, **Sep −26.0% on 26**, Oct +13.7% on 5 | 2026-10-10, whole season |
| Fade the money share instead of the ticket share (80%, top 2 a day) | 72 bets, −1.4% (−1.00u): Jun +16.5% on 26, Jul +18.5% on 13, **Sep −32.4% on 26**, Oct +10.4% on 7 | 2026-10-10, whole season |
| Fade the public under (bet the over) | Too thin to test. The highest under-ticket share on the board all season is 59% (one June game); 19 games all season have 40% or more on the under | 2026-10-10 |
| Reverse line movement, or follow the money | 20 bets or fewer in every setting, months mixed | 2026-09-19 |
| Pinnacle's no-vig price against a soft book's raw price (with its margin), both quotes within 300 seconds, same total | **No bets**: the gap never reaches 1.5 points (June, July and Sep 16-18) | 2026-09-19 |
| Pinnacle's no-vig price against a soft book's no-vig price, 1.8 points or more, within 300 seconds | Apr −4.9% on 36, May −24.5% on 26, Jun +16.2% on 17, Jul +8.8% on 30, Aug −20.5% on 32, **Sep −22.4% on 31**; season 172 bets, −16.25u | every month re-measured 2026-10-10; June and July match the PR |
| DraftKings line moves (steam), followed or faded | No setting with 40 or more bets was positive in both June and July. September was not measured (the query timed out) | 2026-09-19 |
| Public split combined with a line move | 35 games had an equal-line move; no setting reaches 40 bets | 2026-09-19 |

**The earlier Pinnacle totals figure.** The 2026-09-15 search
(`docs/mlb_runline_ou_edge_search.md`) called Pinnacle against DraftKings
on totals, about +11% on about 103 bets, the "leading" totals replacement.
PR #759 found that the gap came from pairing each book's latest quote
with no limit on how far apart the two were taken, so the prices could be
hours apart. With the two quotes required to be within 300 seconds of each
other, the gap it bet on does not occur (the "no bets" row above), and the
no-vig version was red in four of the six months, April and May included.
A correction is in that file.

---

## How the 2026-10-10 rows were measured

All read-only, against production, on 2026-10-10.

**The public-fade rows** use the query at the end of
`docs/mlb_total_public_fade.md`, changed as follows. Each rebuild
reproduces the PR's June and July figures exactly.

- **Every game, and top 2 a day, at 70% or 80% tickets:** set the ticket
  cut in `sp` and delete the band line.
- **Money share:** in `sp`, select `pb.public_money_pct` in place of
  `pb.public_bet_pct` (so the top 2 a day are ranked by money share) and
  cut on `pb.public_money_pct >= 80`; delete the band line.
- **Ticket share with the −120 to −100 band:** ticket cut 70 or 80, and the
  band line changed to `s.imp <= 120.0 / 220.0 and s.imp >= 0.5`. The band
  is applied before the top 2 a day, as the live card does it.

**The Pinnacle no-vig row** (one call, inside the production statement
timeout). Change `0.018` for a different cut.

```sql
-- Pinnacle's no-vig price against a soft book's no-vig price on MLB totals
-- (read-only), PR #759's construction: each book's latest pre-game quote;
-- the soft book on the same total as Pinnacle, in [5.5, 14.5]; the two
-- quotes taken within 300 seconds of each other; soft price in [-200, 200];
-- the largest gap per game, 1.8 points or more; flat 1 unit.
with g as materialized (
  select game_id, game_date gd, commence_time ct,
         to_char(commence_time::timestamptz at time zone 'UTC',
                 'YYYY-MM-DD"T"HH24:MI:SS"Z"') ct_utc,
         home_score::float + away_score::float tr
  from games
  where sport = 'MLB' and game_date >= '2026-03-20'
    and home_score is not null and away_score is not null
), q as materialized (
  select g.game_id, b.bk, b.ord, l.tl, l.op, l.up, l.ts
  from g
  cross join (values ('pinnacle', 0), ('draftkings', 1), ('fanduel', 2),
                     ('betmgm', 3), ('williamhill_us', 4)) b(bk, ord)
  join lateral (
    select o.total_line::float tl, o.over_price::float op,
           o.under_price::float up, o.snapshot_at::timestamptz ts
    from odds o
    where o.game_id = g.game_id and o.market = 'totals' and o.bookmaker = b.bk
      and o.snapshot_at <= g.ct_utc                   -- lets the index stop early
      and o.snapshot_type = 'open'
      and o.snapshot_at::timestamptz <= g.ct::timestamptz
    order by o.snapshot_at desc limit 1) l on true
), imp as (
  select q.*,
         case when op > 0 then 100 / (op + 100) else -op / (-op + 100) end io,
         case when up > 0 then 100 / (up + 100) else -up / (-up + 100) end iu
  from q where op is not null and up is not null
), pairs as (
  select s.game_id, s.ord, s.tl, s.op, s.up,
         p.io / (p.io + p.iu) pin_over, s.io / (s.io + s.iu) soft_over
  from imp p
  join imp s on s.game_id = p.game_id and s.bk <> 'pinnacle' and s.tl = p.tl
  where p.bk = 'pinnacle' and p.tl between 5.5 and 14.5
    and abs(extract(epoch from p.ts - s.ts)) <= 300   -- quotes within 300 s
), cands as (
  select pr.game_id, pr.ord, pr.tl, v.side, v.sord, v.price, v.edge
  from pairs pr
  cross join lateral (values ('over', 0, pr.op, pr.pin_over - pr.soft_over),
                             ('under', 1, pr.up, pr.soft_over - pr.pin_over))
       v(side, sord, price, edge)
  where v.price between -200 and 200 and v.edge >= 0.018   -- the cut
), best as (
  select distinct on (game_id) * from cands
  order by game_id, edge desc, ord, sord
), bets as (
  select g.gd,
         case when g.tr = b.tl then 0.0
              when (g.tr > b.tl) = (b.side = 'over')
                then case when b.price > 0 then b.price / 100.0
                          else 100.0 / abs(b.price) end
              else -1.0 end units
  from best b join g on g.game_id = b.game_id
)
select coalesce(substr(gd, 1, 7), 'all') mon, count(*) bets,
       round(sum(units)::numeric, 2) units,
       round(100 * sum(units)::numeric / count(*), 1) roi_pct
from bets
group by grouping sets ((substr(gd, 1, 7)), ())
order by 1;
```

---

## What was not changed

- `mlb_over_under` and `mlb_runline` stay paused.
- No change to the public-fade settings or to any publish switch.
- No new model was added: nothing met the bar.
