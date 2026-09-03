# Best line on pre-game picks — why picks read as DraftKings, and the route off it

> mike, 2026-09-02: *"investigate why mlb/wnba/ncaaf/ufc picks continue to only
> come from DraftKings lines. I mentioned earlier that picks should have the
> best possible line. they are all available in the odds api. design the best
> solution. this is only for pregame picks for now."*
>
> Live/in-play lanes are explicitly **out of scope** and unchanged.
> Every number below was measured on 2026-09-02, with the query stated.

---

## 1. The answer is three separate things, and only two of them are bugs

**(a) Two markets were fetched DraftKings-only at the source. This was a bug and
it is fixed.**

`data/ingestors/odds_ingestor._get_event_odds` hard-coded
`"bookmakers": ODDS_API_BOOKMAKER`. It is the **only** route by which MLB
first-five markets and UFC round totals are fetched — both are "additional
markets" that the bulk `/odds` endpoint does not carry — so those two markets
had one book in the database while every bulk market had seven:

| market | draftkings | every other book |
|---|---|---|
| `h2h_1st_5_innings` (MLB F5) | 704 rows | **0** |
| UFC `totals` (round totals) | 891 rows | **0** |
| MLB `h2h` / `spreads` / `totals` | ~3,000 each | 520–871 each, ×6 books |
| UFC `h2h` | 1,613 | 435–1,570, ×5 books |

*(`SELECT sport, market, bookmaker, count(*) FROM odds WHERE snapshot_at >=
'2026-09-01' AND snapshot_type <> 'in_play' GROUP BY 1,2,3`, sport from the
game_id prefix.)*

Consequence: **51 of 176 recent MLB pre-game BETs — every `mlb_f5_moneyline`
pick — had nothing to line-shop against**, and neither did any
`ufc_total_rounds` pick. Not "the shop found DK best": there was one quote.

This is the same bug, in the same file, that mike named on 2026-09-01 about
`_get_historical_odds` (*"Pinnacle data is in odds api. I have brought this up
several times. why do you ignore it."*). The `bookmakers` param counts as **one
region** on the per-event endpoint as well, so seven books cost exactly what one
book costs — 1 credit per market per region per call, unchanged.

**(b) Most picks that show no best price simply predate the feature.**

Best-line stamping shipped ~2026-08-28. Coverage by week of `created_at`, all
pre-game BETs:

| week | bets | with a best price |
|---|---|---|
| 07-13 → 08-17 (6 weeks) | 191 | **0** |
| 08-24 | 30 | 19 |
| 08-31 | 70 | **69** |

The one miss in the clean window is the UFC round-totals pick from (a). So the
"MLB 48%, WNBA 12%, UFC 0%" coverage figures that opened this investigation were
an artifact of pooling six pre-feature weeks with four post-feature days — a
BET-count answering the wrong question, exactly the §1b trap. **WNBA was never
broken**; its season ended 2026-08-30, two days after the feature landed.

**(c) The price that DECIDES is DraftKings, by calibrated design — and that is
the part mike is actually asking to change.**

CLAUDE.md §6 pins `edge`, the BET/AVOID call, the Kelly stake, settled P&L and
CLV to DK, because every threshold was swept on DK-implied edge. `picks.best_*`
records the better number for display and the betslip hand-off only, and
`tests/test_best_line.py` asserts the decision path never sees it. That is not a
defect; it is the calibration boundary, and moving it is §2 below.

---

## 2. The finding that mattered most: a quarter of "best prices" cannot be bet

`BEST_LINE_BOOKMAKERS` defaulted to `LINE_SHOP_BOOKMAKERS`, which includes
**pinnacle** and **bovada**. Pinnacle does not accept US customers; Bovada is
offshore. Both belong in the feed — Pinnacle is the sharp de-vig reference
`SHARP_BOOKMAKERS` is built on, Bovada carried the NCAAF opener signal — but
neither is an answer to *"where should I place this?"*

Of the **69** pre-game BETs since 08-31 carrying a best price:

- **35** named a book other than DraftKings, and
- **18 of those 35 named Pinnacle or Bovada.**

So **over half of every "we found you a better number" claim, and 26% of all
bets, pointed at a price the bettor could not take** — while the column's own
docstring says it is "what the bettor should actually take". Lifetime, Pinnacle
is the stamped `best_book` on 398 picks and Bovada on 261.

Fixed by splitting the roles: `BEST_LINE_EXCLUDE_BOOKMAKERS`
(default `pinnacle,bovada`) removes a book from *shopping* while leaving it in
`LINE_SHOP_BOOKMAKERS` and `ODDS_API_BOOKMAKERS_PARAM` for analysis.
**Which books belong on that list is mike's call** — it depends on where he
actually holds accounts, and the env var takes any list.

---

## 3. Stage 1 — shipped in this change (no model behaviour changes)

| # | Fix | Effect |
|---|---|---|
| 1 | `_get_event_odds` takes `bookmakers`, defaulting to `ODDS_API_BOOKMAKERS_PARAM`, with a 400 fallback to DK-only | MLB F5 and UFC round totals become shoppable for the first time. Zero extra credits |
| 2 | `_best_game_price` resolves the UFC sibling orientation, flipping the side for `h2h` and keeping it for `totals` | `_get_dk_odds` has done this since the 2026-08-29 card; best-price lookup did not, so a fight five books had priced could silently stamp NULL |
| 3 | Unbettable books excluded from shopping, kept in the feed | §2 |

Nothing here touches `edge`, the BET/AVOID call, Kelly, settlement or CLV, so
there is no `Updated-By:` trailer — this is ingest and display plumbing.

**Verify after deploy** (do not trust the comment — CLAUDE.md §1b):

```sql
-- (1) other books arrive on the two per-event markets
SELECT market, bookmaker, count(*) FROM odds
WHERE market IN ('h2h_1st_5_innings','totals')
  AND snapshot_at >= '<deploy date>' GROUP BY 1,2 ORDER BY 1,2;
-- (2) credits per fetch did not move
SELECT * FROM odds_api_quota ORDER BY checked_at DESC LIMIT 20;
```

---

## 4. Stage 2 — moving qualification to the best price (mike's decision)

This is the real request, and it cannot be shipped as a side effect of Stage 1.

**What it costs.** Every cut in `MODEL_EDGE_THRESHOLDS` /
`MODEL_PROB_THRESHOLDS` was swept on DK-implied edge. Qualifying on the best of
N books lowers the implied probability, so every cut loosens by that amount with
nobody deciding to. Measured on the 69 clean-window bets: **0.68pp on average,
3.61pp at most**. `config.py` carries an older ~2pp figure from 92 MLB games on
08-28; the populations differ (market-wide games vs same-line picks) and the
re-sweep is what settles it — do not relitigate it beforehand.

**The evidence needed already mostly exists, which is better than assumed.**
§7's evaluation rule requires grading BET, AVOID and dead-zone NONE alike. The
stamping runs on every scored row, not just bets — since 08-31: **NONE
2,621/2,647, AVOID 311/312, BET 69/70**. So the re-sweep sample is the full
scored universe, not a BET-only one.

The residual gap is real but narrow: propositions that get **no row at all**
(`abs(edge) > MAX_EDGE_CAP` — 35.3% of `mlb_runline` games per §7) and NONE rows
removed by `cleanup-picks`. Reconstructing those needs raw non-DK history, and
`PRUNE_NON_DK_KEEP_DAYS = 2` deletes it after two days.

**Retention, measured rather than estimated.** Non-DK rows written per day:
252,705 in `odds` (573 B/row) + 98,680 in `player_prop_odds` (663 B/row) ≈
**210 MB/day, ~6.3 GB/month**. The comment in `config.py` says ~2.7 GB/month;
that counted one table. So "raise it to 90 days" is a ~19 GB commitment, which
is why it is a decision and not a default. Two cheaper options, in order of
preference:

1. **Do nothing.** Accept the narrow gap and re-sweep off the picks table, which
   already carries the full scored universe. Free.
2. **Keep one snapshot per book per proposition per day** instead of ~21. Same
   reconstruction power for the re-sweep at roughly 1/20th the volume
   (~10 MB/day), and it is a change to `data/prune_odds.py`, not a retention
   number.

Raising `PRUNE_NON_DK_KEEP_DAYS` wholesale is the expensive third option. What
must not happen is deciding this in three months: pruned rows are gone.

**The order, when mike says go.**

1. Re-sweep each pre-game model's cut on best-implied edge — **per model, never
   copied across** (§1b), with the plateau/CI/time-split standards of §7.
2. Flip qualification, Kelly and settlement to the best price in ONE change,
   `Updated-By: mike`. `tests/test_multi_book_odds.py` and
   `tests/test_best_line.py` will fail — they are the tripwires being
   deliberately retired, and that failure is how you know it is the intended
   change rather than a leak.
3. **CLV stays DK-to-DK** in either case: there is no best-price closing history
   to measure against, and mixing the two would make the number meaningless.

---

## 5. Scope fences

- **Same line only.** A better price on Over 9.0 is not a better price on
  Over 8.5 — it is a different bet, and the model probability was computed at
  the scored line. Line-aware shopping means re-scoring at the alternate line;
  that is a separate piece of work, not part of this.
- **No backfill of `best_*` onto locked picks.** Stamping today's shop onto an
  old pick fabricates score-time data — §1c, timing is data.
- **Live lanes untouched, with ONE deliberate exception.** `_best_live_price`
  and the in-play loops are unchanged in mechanics, per mike's instruction. But
  the unbettable-book exclusion in §2 is a shared config constant, so it applies
  to live stamping too — and that is on purpose: a price the bettor cannot take
  is the wrong number on a live pick for exactly the same reason it is wrong on
  a pre-game one, and §1b says a fix like this is assessed against every lane
  rather than left in one. It changes which book a live pick names, never
  whether it fires. Say the word and it can be pre-game-only instead.
- **No UI change.** Whether the headline price members see becomes best-instead-
  of-DK is a product decision, not a consequence of this.

---

## 6. Where the pieces live

| Thing | File |
|---|---|
| Book roles: shop / sharp / feed / excluded | `config.py` — `LINE_SHOP_BOOKMAKERS`, `BEST_LINE_BOOKMAKERS`, `BEST_LINE_EXCLUDE_BOOKMAKERS`, `SHARP_BOOKMAKERS` |
| Best-price lookup (pre-game, prop, live) | `models/scorer.py` — `_best_game_price`, `_best_prop_price`, `_best_live_price` |
| Per-event fetch (F5, UFC round totals) | `data/ingestors/odds_ingestor.py` — `_get_event_odds` |
| Retention | `data/prune_odds.py`, `config.PRUNE_NON_DK_KEEP_DAYS` |
| The DK-decides invariant | CLAUDE.md §6; `tests/test_multi_book_odds.py`, `tests/test_best_line.py` |
