# MLB run line: the search for a rule built on market data (2026-09-19)

> **Provenance.** From PR #757 (2026-09-19, never merged), carried to
> master 2026-10-10 as a write-up only. Its 924-line measurement script and
> tests were not kept; the query at the end of this page rebuilds the board
> and the closest misses. Figures marked **2026-09-19** are the PR's.
> Figures marked **2026-10-10** were measured with read-only SQL against
> production during the review of PR #757 or for this page. The section
> "After the PR was written" is the out-of-sample check, and it is where to
> start.

**The question.** `mlb_runline` is paused. Is there a bettable run-line
rule that is not the trained model? This looked at four kinds of rule:
fading the public (by tickets or by money), Pinnacle against the soft
books, reverse line movement, and following or fading DraftKings line moves
(steam).

**The answer: no, and the games played since make it clearer.** Nothing
was published from this search. Before the PR was written, two cells came
close and were declined because their neighbours failed. In the 105 games
played after it, both lost, and so did most settings around them (−8% to
−18%). The exception is a trap, described in "After the PR was written".

**The bar.** At least 40 bets; every month with bets positive, and at
least two of them; positive overall; at most 4 bets a day; and a
neighbourhood, not a lone good setting. "A lone good setting" includes the
case where keeping the top 3 a day works but the top 2 and the top 4 lose.
August counts as missing, not red (below).

**How the board was built.** Public split: the consensus run-line split
taken before first pitch (an offset-aware time comparison). Prices: each
book's latest pre-game quote (`snapshot_type='open'`,
`snapshot_at <= commence_time`). Each side shopped among DraftKings,
FanDuel, BetMGM and William Hill at DraftKings' ±1.5, American price
between −200 and +200. Flat 1 unit. The line is the home number (CLAUDE.md
§4).

---

## Coverage

Games with a run-line consensus split taken before first pitch:

| Month | Any row | Before first pitch | Settled |
|---|---:|---:|---:|
| 2026-05 | 15 | 0 | 0 |
| 2026-06 | 400 | 59 | 59 |
| 2026-07 | 342 | 25 | 25 |
| 2026-08 | 397 | **0** | 0 |
| 2026-09 (to 19) | 254 | 54 | 39 |

That is the 2026-09-19 count. August is empty because `public_betting`
keeps one row per game, market, side and book, and a later update
overwrote each pre-game split (the same trap as
`docs/mlb_total_public_fade.md`). Two 2026-07-01 rows with home tickets 100
and away tickets 99 were dropped as broken. After shopping, the PR's board
was **119** games.

Re-counted 2026-10-10 (before first pitch): Jun 59, Jul 25, Aug 0, Sep 154,
Oct 17. Rebuilt today with the PR's filters, the board through 2026-09-19
is **132** games, not 119; the extra rows are in the data now, and the
cause was not separated. There are **105** more board games from 09-20
through the postseason.

---

## Verdict by approach (2026-09-19)

| Approach | Verdict |
|---|---|
| Fade the ticket-heavy side | **Nothing to publish.** The only setting with 40+ bets that passed was fading the heaviest side at 70% or 75% of tickets, top 2 a day: +0.51u on 42 (+1.2%); Jun +1.8%/23, Jul +1.2%/13, **Sep −1.0%/6**. The looser neighbour (65%, top 2) was −1.8% on 50. A −110 to −100 price band was 11 bets and red. |
| Fade the money-heavy side | **Nothing to publish.** Every game at 75% (+4.42u on 59, +7.5%) and 80% (+2.45u on 48, +5.1%) was positive in all three months but bet up to 6 and 5 a day (the bar is 4). Top 3 a day at 70/75/80% met the bar on paper (57/51/44 bets, every month positive, 3 a day) but top 2 and top 4 at the same cuts lost in September: a lone good setting. Not published. |
| Bet the home underdog | **No.** The same bets as fading the away side once the home number is +1.5. July −50% to −74%. |
| Reverse line movement (back the underdog when the favourite's money lags its tickets) | **No.** Every setting is under 40 bets, red, or both. Following the money on the favourite also loses. |
| Public split combined with a line move | **No.** Fading the public when the line moved against it is 16 bets or fewer. The settings positive in all three months are under 40 bets; those over 40 have a red September. |
| Pinnacle against the soft books | **No new rule.** Pinnacle's no-vig price against DraftKings' raw price, 2 points or more, latest quotes: no bets in June. The no-vig against no-vig version at 1.8 points, DraftKings only: Jun −3.36u on 28, Jul −4.08u on 34. Against the wider soft-book list it is the existing model `mlb_spread_market`; its season, month by month, is in `docs/mlb_spread_market_2026.md`. |
| Steam (DraftKings line moves) | **No.** Following a move of 2 points or more was positive in one month (June) and red in the other five, September −14.2% on 87. |

---

## Fading the ticket-heavy side (2026-09-19, 119-game board)

Fade the named pile and bet the other run-line side. "Top 2" keeps the two
games a day with the heaviest pile.

| Construction | n | Units | ROI | Jun | Jul | Sep |
|---|---:|---:|---:|---:|---:|---:|
| fade heaviest, 70%, every game | 71 | −3.56 | −5.0% | +4.5%/30 | −11.8%/17 | −12.2%/24 |
| **fade heaviest, 70%, top 2** | **42** | **+0.51** | **+1.2%** | **+1.8%/23** | **+1.2%/13** | **−1.0%/6** |
| fade heaviest, 65%, top 2 | 50 | −0.88 | −1.8% | −1.8%/29 | −2.1%/15 | −1.0%/6 |
| fade heaviest, 80%, top 2 | 36 | +1.50 | +4.2% | +4.8%/19 | +5.9%/11 | −1.0%/6 |
| fade heaviest, 90%, top 2 | 17 | +3.14 | +18.5% | −0.8%/6 | +17.9%/7 | +48.5%/4 |
| fade the favourite, 70%, top 2 | 42 | +0.51 | +1.2% | the same 42 bets as above | | |
| fade home, 60%, every game | 49 | +1.58 | +3.2% | +13.0%/26 | +22.5%/12 | **−41.0%/11** |
| fade public where Pinnacle agrees, 70% | 54 | −1.16 | −2.2% | +12.4%/26 | **−43.8%/12** | +5.3%/16 |
| 70%, price −110 to −100 | 11 | −1.32 | −12.0% | −3.8%/6 | +100%/1 | −52.3%/4 |

The +1.2% cell was not published: September was red, the looser
neighbour lost, it was 42 bets over three part-months with August missing,
and fading the favourite at 70% is the same 42 bets, not a second signal.

## Fading the money-heavy side, and the home underdog (2026-09-19, 119-game board)

Fade the side holding more of the money, ranked by that share.

| Construction | n | Units | ROI | Jun | Jul | Sep | max a day |
|---|---:|---:|---:|---:|---:|---:|---:|
| 75%, every game | 59 | +4.42 | +7.5% | +13.4%/26 | +0.5%/18 | +5.6%/15 | **6** |
| 80%, every game | 48 | +2.45 | +5.1% | +9.5%/21 | +0.4%/15 | +3.3%/12 | **5** |
| **70%, top 3** | **57** | **+4.60** | **+8.1%** | **+11.1%/31** | **+6.5%/17** | **+0.8%/9** | **3** |
| **75%, top 3** | **51** | **+5.65** | **+11.1%** | **+13.4%/26** | **+13.1%/16** | **+0.8%/9** | **3** |
| **80%, top 3** | **44** | **+3.13** | **+7.1%** | **+9.5%/21** | **+7.5%/14** | **+0.8%/9** | **3** |
| 75%, top 2 | 42 | +2.68 | +6.4% | +6.6%/23 | +12.2%/13 | **−7.1%/6** | 2 |
| 75%, top 4 | 56 | +2.29 | +4.1% | +13.4%/26 | +0.5%/18 | **−10.7%/12** | 4 |
| 85%, top 3 | 38 | +2.50 | +6.6% | +9.2%/18 | +3.7%/13 | +5.1%/7 | 3 |
| home underdog, fade away at 65% | 41 | −0.95 | −2.3% | +4.3%/18 | **−57.9%/8** | +19.4%/15 | 7 |

Why top 3 was not published: top 2 and top 4 at the same cuts lost in
September, so only the number 3 kept September positive at 40+ bets. July
every game was +0.5% on 18 at 75% and −4.7% on 19 at 70%; top 3 produced
its July figure by dropping the fourth and later bets on busy days. Every
game at 75% and 80% was positive in all three months but broke the 4-a-day
limit. The "after the PR" section below shows the decision was right.

## Public split combined with a line move (2026-09-19, 119-game board)

DraftKings' move from its first to its latest home price, attached to the
public board. Prices stay the shopped latest quote.

| Construction | n | Units | ROI | Months |
|---|---:|---:|---:|---|
| fade public, line moved against it, 65%, move ≥1 point | 16 | +3.74 | +23.4% | Jun +36.5%/11, Jul +2.5%/3, **Sep −17.5%/2** |
| fade public, any move, 80%, ≥1 point, top 2 | 26 | +6.03 | +23.2% | Jun +16.4%/11, Jul +34.9%/10, Sep +14.8%/5 (under 40) |
| fade public, any move, 65%, ≥1 point, top 2 | 40 | +7.91 | +19.8% | Jun +16.6%/22, Jul +37.7%/12, **Sep −4.4%/6** |
| follow the move, any, 65%, ≥3 points | 20 | +4.33 | +21.7% | three months positive (under 40) |
| follow the move, with the public, 65%, ≥3 points | 13 | +3.39 | +26.1% | three months positive (under 40) |

Every setting positive in all three months is under 40 bets; every setting
at 40 or more has a red September.

## Reverse line movement (2026-09-19, 119-game board)

Favourite tickets at or above the cut, and the favourite's money share
below its ticket share by at least the gap; bet the underdog.

| Construction | n | Units | ROI | Months |
|---|---:|---:|---:|---|
| 55%, gap ≥5 | 30 | −0.20 | −0.7% | Jun +1.1%/12, Jul −37.1%/5, Sep +11.7%/13 |
| 65%, gap ≥5 | 25 | +0.02 | +0.1% | Jul −100%/2 |
| 70%, gap ≥5 | 20 | +0.26 | +1.3% | under 40 |
| 80%, gap ≥5 | 13 | +0.36 | +2.8% | under 40 |
| 55%, gap ≥10 | 17 | −0.22 | −1.3% | |
| 70%, gap ≥10 | 10 | −2.76 | −27.6% | |
| follow the money on the favourite, 55%, money ahead by ≥5 | 31 | −4.76 | −15.3% | all three months red |

No setting reaches 40 bets, and widening the gap makes it worse.

## Steam: DraftKings' first to latest pre-game price, same ±1.5 (2026-09-19, whole 2026 odds history)

The move is 100 × (latest home implied probability − first home implied
probability). Follow bets the side the price moved toward; fade bets the
other.

| Month | follow ≥2 points, n | Units | ROI | fade ≥2 points, units | follow ≥3 points, n | Units |
|---|---:|---:|---:|---:|---:|---:|
| 2026-04 | 73 | −9.86 | −13.5% | +3.77 | 34 | −8.51 |
| 2026-05 | 123 | −13.43 | −10.9% | −2.72 | 50 | +2.61 |
| 2026-06 | 92 | **+4.86** | **+5.3%** | −13.04 | 47 | +1.31 |
| 2026-07 | 101 | −14.33 | −14.2% | +3.92 | 63 | −5.72 |
| 2026-08 | 124 | −7.12 | −5.7% | −0.59 | 74 | +0.52 |
| 2026-09 (to 19) | 87 | **−12.39** | **−14.2%** | +5.73 | | |

September following at 2 points by week: 1-9 −4.00u on 39, 10-14 +0.19u on
24, 15-19 −8.58u on 24. June is a lone positive month.

---

## After the PR was written (2026-10-10)

Measured with the query below on the board rebuilt today: 132 games to
2026-09-19 and 105 games after it (09-20 through the postseason, every
settled game).

**The two near-misses, rebuilt on today's board, to 09-19:** money-heavy
fade at 75%, top 3 a day: 54 bets, +6.08u, +11.3% (the PR had 51, +5.65u).
Ticket fade at 70%, top 2: 44 bets, +0.10u, +0.2% (the PR had 42, +0.51u).

**After 09-19, both near misses lost, and so did most settings around them:**

| Construction | Bets | Units | ROI |
|---|---:|---:|---:|
| Money-heavy fade, 70%, top 3 | 32 | −3.36 | −10.5% |
| Money-heavy fade, 75%, top 3 | 27 | −3.34 | −12.4% |
| Money-heavy fade, 80%, top 3 | 24 | −1.91 | −8.0% |
| Money-heavy fade, 75%, every game | 48 | −8.81 | −18.4% |
| Money-heavy fade, 75%, top 4 | 33 | −5.50 | −16.7% |
| Ticket fade, 65%, top 2 | 27 | −3.70 | −13.7% |
| Ticket fade, 70%, top 2 | 25 | −3.34 | −13.4% |
| Ticket fade, 80%, top 2 | 18 | −3.16 | −17.6% |
| Ticket fade, 70%, every game | 55 | −5.48 | −10.0% |

**A trap to avoid.** After 09-19 the money-heavy **top 2** cells turned
positive: +12.2% on 24 at 70%, +15.5% on 19 at 75%, +13.2% on 18 at 80%.
Before 09-19 it was top 2 that lost in September while top 3 held. The same
neighbouring settings swapping places from one stretch to the next is the
mark of noise. Neither top 2 nor top 3 is a signal; do not start the next
search from the top-2 figure.

**Re-running it** (read-only; one call, inside the production statement
timeout). Each output row is one construction: `kind` is the fade, `cut` the
share, `top_k` the daily limit (0 = every game).

```sql
-- MLB run-line public-split board, rebuilt the way PR #757 built it
-- (read-only). One row per settled game: the consensus run-line split
-- taken before first pitch; DraftKings' latest pre-game line at +/-1.5;
-- each side's best price at that line among DraftKings, FanDuel, BetMGM
-- and William Hill, between -200 and +200. Then the money-share and
-- ticket-share fades, every qualifying game and top 2 / 3 / 4 a day,
-- split at 2026-09-19 (the day the PR was written).
with sp as materialized (
  select h.game_id, g.game_date gd, g.commence_time ct,
         to_char(g.commence_time::timestamptz at time zone 'UTC',
                 'YYYY-MM-DD"T"HH24:MI:SS"Z"') ct_utc,
         g.home_score::float hs, g.away_score::float aws,
         h.public_bet_pct::float ht, h.public_money_pct::float hm,
         a.public_bet_pct::float at_, a.public_money_pct::float am
  from public_betting h
  join games g on g.game_id = h.game_id
  join public_betting a on a.game_id = h.game_id and a.market = 'spreads'
                       and a.side = 'away' and a.book = 'consensus'
  where h.market = 'spreads' and h.side = 'home' and h.book = 'consensus'
    and g.sport = 'MLB'
    and h.snapshot_at::timestamptz < g.commence_time::timestamptz
    and g.home_score is not null
    -- drop broken splits (both sides near 100)
    and abs(h.public_bet_pct + a.public_bet_pct - 100) <= 15
    and not (h.public_bet_pct >= 98 and a.public_bet_pct >= 50)
    and not (a.public_bet_pct >= 98 and h.public_bet_pct >= 50)
), q as materialized (
  select sp.game_id, b.bk, b.ord, l.sh, l.hp, l.ap
  from sp
  cross join (values ('draftkings', 1), ('fanduel', 2), ('betmgm', 3),
                     ('williamhill_us', 4)) b(bk, ord)
  join lateral (
    select o.spread_home::float sh, o.home_price::float hp, o.away_price::float ap
    from odds o
    where o.game_id = sp.game_id and o.market = 'spreads' and o.bookmaker = b.bk
      and o.snapshot_at <= sp.ct_utc                  -- lets the index stop early
      and o.snapshot_type = 'open'
      and o.snapshot_at::timestamptz <= sp.ct::timestamptz
    order by o.snapshot_at desc limit 1) l on true
), dk as (
  select game_id, sh from q
  where bk = 'draftkings' and abs(abs(sh) - 1.5) < 1e-9
), shop as (
  select dk.game_id, dk.sh, s.side, s.price,
         row_number() over (partition by dk.game_id, s.side
                            order by i.imp, s.ord) rn
  from dk
  join q on q.game_id = dk.game_id and q.sh = dk.sh
  cross join lateral (values ('home', q.hp, q.ord), ('away', q.ap, q.ord)) s(side, price, ord)
  cross join lateral (select case when s.price > 0 then 100 / (s.price + 100)
                                  else -s.price / (-s.price + 100) end) i(imp)
  where s.price between -200 and 200
), board as (
  select sp.*, h.sh line, h.price home_price, w.price away_price,
         case when sp.gd <= '2026-09-19' then 'to 09-19' else 'after 09-19' end period
  from sp
  join shop h on h.game_id = sp.game_id and h.side = 'home' and h.rn = 1
  join shop w on w.game_id = sp.game_id and w.side = 'away' and w.rn = 1
), cand as (
  -- money fade: bet against the side holding more of the money
  select b.period, b.gd, b.game_id, 'money' kind, c.cut,
         greatest(b.hm, b.am) pile,
         case when b.hm >= b.am then 'away' else 'home' end bet_side,
         b.hs, b.aws, b.line, b.home_price, b.away_price
  from board b cross join (values (70.0), (75.0), (80.0)) c(cut)
  where greatest(b.hm, b.am) >= c.cut
  union all
  -- ticket fade: bet against the side holding more of the tickets
  select b.period, b.gd, b.game_id, 'tickets', c.cut,
         greatest(b.ht, b.at_),
         case when b.ht >= b.at_ then 'away' else 'home' end,
         b.hs, b.aws, b.line, b.home_price, b.away_price
  from board b cross join (values (65.0), (70.0), (80.0)) c(cut)
  where greatest(b.ht, b.at_) >= c.cut
), graded as (
  select c.period, c.kind, c.cut, c.gd, c.game_id, c.pile,
         row_number() over (partition by c.kind, c.cut, c.gd
                            order by c.pile desc, c.game_id desc) day_rank,
         case
           when (c.hs - c.aws + c.line) = 0 then 0.0
           when ((c.hs - c.aws + c.line) > 0) = (c.bet_side = 'home') then
             case when p.price > 0 then p.price / 100.0 else 100.0 / abs(p.price) end
           else -1.0 end units
  from cand c
  cross join lateral (select case when c.bet_side = 'home' then c.home_price
                                  else c.away_price end) p(price)
)
select period, kind, cut, k.k as top_k, count(*) as bets,
       round(sum(units)::numeric, 2) as units,
       round(100 * sum(units)::numeric / count(*), 1) as roi_pct
from graded cross join (values (0), (2), (3), (4)) k(k)
where k.k = 0 or day_rank <= k.k
group by 1, 2, 3, 4
union all
select period, 'board games', null, null, count(*), null, null from board group by 1
order by 1 desc, 2, 3, 4;
```

---

## What this is not

- Not an unpause of `mlb_runline`, `mlb_over_under` or the first-five
  models, and not a new model.
- Not a change to any publish switch.
- Not the totals public fade (`docs/mlb_total_public_fade.md`), which
  fades the over on totals and is measured there.
