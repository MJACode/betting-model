# MLB totals edge hunt (2026-09-19) — Deliverable B

Standing hunt for a **stakeable `mlb_over_under` construction** after the
runline hunt (PR #757) returned empty. Same ship bar. **No publisher.**

`mlb_over_under` stays paused. `mlb_total_market` INSERT stays 0.
`mlb_total_public_fade` / I24 guards are **not recut**
(`config.py` and `models/mlb_total_public_fade.py` untouched).
No `PUBLISH` flag is flipped.

Measure script: `python -m scripts.mlb_over_under_edge_hunt`
(`--json` is a sandbox cache of the Supabase pull). Tests pin grading
and the ship bar: `tests/test_mlb_over_under_edge_hunt.py`.

---

## Ship bar (identical to the runline hunt)

A cell ships only if **all** of these hold:

| Gate | Cut |
|---|---|
| Sample | n ≥ 40 decided-or-push rows |
| Months | every populated month green, **and** ≥ 2 such months |
| ROI | flat 1u ROI > 0 |
| Concentration | max bets / `game_date` ≤ 4 |
| Neighbourhood | not a one-cell peak |
| K-peak | if top-3 works, top-2 **and** top-4 must also |

A Jun+Jul print with a red September is not a ship. A public-board
CLEAR that the same cut fails on the **full DK month** is not a ship
(coverage-selected sample — see closest miss).

---

## Coverage (Supabase 2026-09-19)

`public_betting` consensus totals-over, settled MLB, offset-aware
`snapshot_at < commence_time`:

| Month | Pregame public | All public rows |
|---|---|---|
| 2026-05 | 0 | 15 |
| 2026-06 | 59 | 378 |
| 2026-07 | 25 | 337 |
| 2026-08 | 0 | 397 |
| 2026-09 | 39 | 239 |

Honest public board used below: **123 games** (Jun 59 / Jul 25 / Sep 39).
August last-upsert overwrite — 0 pre-commence rows. Thin before ~2026-05-31.

Odds: `snapshot_type='open'` AND `snapshot_at <= commence_time`. Shop
DK/FD/MGM/WH at the **latest** leak-bounded DK total 5.5–14.5, American
[−200, 200], both sides required. Flat 1 unit.

### Production settled BET (not VOID, not live)

| model | n | W-L | units |
|---|---|---|---|
| `mlb_over_under` | 172 | 70-92 | **−28.58** |
| `mlb_total_public_fade` | 37 | 15-21 | **−7.19** (Sep 16–18 card) |
| `mlb_total_market` | 0 | — | INSERT off |

`mlb_over_under` by month: Apr −10.99u/70, May +0.57u/16, Jun −2.12u/28,
Jul −4.26u/31, Aug −4.09u/7, Sep −7.69u/20.

---

## Verdict

**Deliverable B.** No cell on the public/Pin/RLM/steam/overlay grid
cleared the bar **and** survived the full-book / neighbourhood / K-peak
checks. Do not unpause `mlb_over_under`. Do not flip any `PUBLISH`.
Do not recut I24. Next careful work is I24 upgrades on the **existing**
fade finder, not a new totals publisher.

---

## What was tested

Families, all on the 123-game board unless noted:

1. **Fade heaviest / OVER / UNDER tickets** at t60–t90, all-pass and top-1/2/3.
2. **I24-shaped juice** `[−110, −100]` on this latest-open both-sides shop
   (labelled, **not a recut** of the fade-finder I24 card).
3. **Fade money-heavy** m60–m90, all-pass and top-2/3/4.
4. **Fade public ∩ Pin-agree** t65–t80, all-pass and top-2.
5. **RLM fade-over** t55–t80 × rlm ≤ −5/−10/−15/−20; **follow-money OVER** rlm ≥ 5.
6. **Pin-vs-soft** implied and de-vig, lean and any-side, 1.5–3.0pp, on
   public-board latest quotes **and** first-open Pin-vs-DK by month.
7. **Steam follow / fade** on June DK opens (cache) and July full DK month
   (SQL). September full-month steam SQL timed out; Sep 16–18 public-board
   moves were attached for overlay.
8. **Public × steam overlay** (oppose / agree / any × fade-public /
   follow-steam × t60–t80 × ≥1/2/3pp × top-1..4) after Jul+Sep moves
   were attached (123/123 rows with `move_over_pp`).

Fade-UNDER pile: **n=0** at every cut — public is almost never under-heavy.

---

## Closest misses (why they failed)

### 1. Public-board steam follow — mechanical CLEAR, refused

On the **123-game public board**, follow-steam (any public direction) is
a neighbourhood, not a K-peak:

| Cell | n | ROI | months | max/day | bar |
|---|---|---|---|---|---|
| follow-steam any t65 ≥1pp all-pass | 67 | +13.3% | Jun +21.1%/28, Jul +15.9%/13, Sep +3.7%/26 | 12 | max/day |
| **t65 ≥1pp top-2** | **40** | **+24.8%** | Jun +18.9%/23, Jul +19.9%/11, Sep +56.0%/6 | 2 | **CLEAR** |
| t65 ≥1pp top-3 | 47 | +23.8% | all green | 3 | CLEAR |
| t65 ≥1pp top-4 | 53 | +27.3% | all green | 4 | CLEAR |
| t60 ≥1pp top-2/3/4 | 41/49/55 | +21.7/+22.5/+26.1% | all green | 2–4 | CLEAR |
| t65 ≥0.5pp top-2/3/4 | 42/55/63 | +16.6/+17.6/+19.3% | all green | 2–4 | CLEAR |
| no-ticket steam follow ≥1pp top-2/3/4 | 44/53/60 | +18.8/+22.1/+20.5% | all green | 2–4 | CLEAR |

**Veto:** the same follow cut on the **full July DK book** (not the 25
public-row games) is a wipeout:

| Window | cut | n | units | ROI |
|---|---|---|---|---|
| 2026-06 public-cache DK steam | follow ≥1pp | 224 | +5.70u | +2.5% |
| 2026-06 | follow ≥2pp | 117 | +13.11u | +11.2% |
| **2026-07 full DK** | **follow ≥1pp** | **197** | **−118.50u** | **−60.2%** |
| 2026-07 full DK | follow ≥2pp | 110 | −66.02u | −60.0% |
| 2026-07 full DK | follow ≥3pp | 53 | −31.55u | −59.5% |
| 2026-07 full DK | fade ≥1pp | 197 | −105.28u | −53.4% |

July public coverage is **25 pregame rows vs 334 steam-move games**. A
t65 / “has a public row” filter is missing-data, not a market filter.
When Action Network is populated daily this construction **is** full-book
steam follow, which July already failed. Same class of refuse as runline
steam-follow Sep wipeout. **No card.**

September full-month steam SQL timed out on MCP (even 10-day windows).
Sep 16–18 public-board follow ≥1pp all-pass was +6.7%/28 — thin green
on three days, not a second full-book month.

### 2. Fade public ∩ Pin-agree

| Cell | n | ROI | months | why not |
|---|---|---|---|---|
| t70 all-pass | 42 | +15.1% | Jun +44.9%/19, Jul −5.3%/12, Sep −14.2%/11 | Jul+Sep red, max/day=5 |
| t70 top-2 | 33 | +20.7% | Jun +51.5%/15, Jul −5.3%/12, Sep −4.1%/6 | n<40, Jul+Sep red |
| t65 all-pass | 45 | +13.7% | same shape | Jul+Sep red, max/day=5 |

June-only. Not month-stable.

### 3. Ticket fade OVER (heaviest = OVER; under pile empty)

| Cell | n | ROI | months | why not |
|---|---|---|---|---|
| t70 all-pass | 91 | −10.0% | Jun +5.0%/41, Jul −5.4%/16, Sep −30.2%/34 | Jul+Sep red, max/day=14 |
| t80 top-2 | 38 | +5.1% | Jun +21.7%/22, Jul −6.8%/10, Sep −36.4%/6 | n<40, Jul+Sep red |
| t90 top-2 | 26 | +10.2% | Jun +31.7%/16, Jul −6.2%/4, Sep −36.4%/6 | n<40, Sep red |
| t80 all-pass | 73 | −8.9% | Jun +14.2%/31, Jul −22.3%/12, Sep −27.5%/30 | Jul+Sep red |

Same Sep-red shape the runline ticket fade showed. Not a recut of I24.

### 4. I24-shaped juice on **this** latest-open board — not a recut

t80 + shopped under in `[−110, −100]`: **n=37 −12.65u −34.2%**, all three
months red (Jun −9.1%/15, Jul −68.0%/6, Sep −45.0%/16).

This is **not** the fade-finder I24 card in `docs/mlb_total_public_fade.md`
(claimed n=38 +9.51u +25%, Jun/Jul/Sep all +). Different shop /
intersection (this hunt requires both sides at the latest equal DK line).
Production `mlb_total_public_fade` settled **37 −7.19u** on the Sep 16–18
all-pass card — also not that finder cell. **Do not recut I24 from these
numbers.** Tickets≥80, under odds [−110, −100], max 2/slate, concentration
guard stay where they are.

### 5. Money-heavy fade

| Cell | n | ROI | months | why not |
|---|---|---|---|---|
| m80 all-pass | 75 | −9.0% | Jun +11.2%/30, Jul +1.5%/13, Sep −32.1%/32 | Sep red, max/day=13 |
| m80 top-3 | 50 | −1.5% | Jun +8.8%/28, Jul +1.5%/13, Sep −37.7%/9 | Sep red |
| m80 top-4 | 55 | +1.5% | Jun +11.2%/30, Jul +1.5%/13, Sep −22.5%/12 | Sep red |

No K-peak CLEAR (nothing with top-2 **and** top-4 green). All-pass
max/day 10–14.

### 6. RLM / follow-money OVER

Every RLM fade-over cut n<40 and/or red. Follow-money OVER t55 rlm≥5:
**+17.8%/22** (Jul +36.1%/7, Sep +60.9%/9, **Jun −68.2%/6**). n<40,
June wipeout.

### 7. Pin-vs-soft

**Latest equal-line, public board:** implied ≥1.5pp n=1; ≥2.0pp empty.
de-vig ≥1.8pp n=13 +6.3% (Jun +96.1%/4, Jul −33.3%/3, Sep −33.8%/6).
de-vig ≥2.0pp −33.6%/9.

**First-open Pin vs first-open DK, implied lean, equal total:**

| Month | paired | ≥1.5pp n / u | ≥2.0pp n / u |
|---|---|---|---|
| 2026-04 | 216 | 0 / 0 | 0 / 0 |
| 2026-05 | 271 | 5 / +1.03 | 2 / +2.02 |
| 2026-07 | 216 | 1 / +1.00 | 0 / 0 |

GROK Pin-vs-DK implied ~+11%/103 Apr–Jul is **not reproduced** on
first-open or latest-open equal-line pairing. Existing
`mlb_total_market` Pin-de-vig vs soft-de-vig May–Jun 2pp **−11.13%/79**
remains the documented loser. INSERT stays 0.

June latest-open Pin-implied lean vs DK ≥1.5pp: n=0 (216-class pairing
on the public slice is even thinner).

---

## What this is not

- Not an unpause of XGBoost `mlb_over_under` or `mlb_runline`.
- Not a `PUBLISH=1` on `mlb_total_market` or `mlb_total_public_fade`.
- Not a recut of I24 / tickets≥80 / under [−110, −100] / max 2/slate /
  concentration guard.
- Not a re-ship of the runline empty report (ticket fade, money-heavy
  top-3, RLM dog, Pin-vs-DK ≥2pp spreads). Those stay in PR #757.
- Not permission to treat the public-board steam neighbourhood as a
  paper card. Full-July −118.50u / 197 is the measurement that refuses it.

---

## Next (owner, not this PR)

Careful **I24 upgrades on the existing fade finder** — the finder card
still claims n=38 +9.51u +25% with Jun/Jul/Sep all green. This hunt did
not reproduce that cell on the latest-open both-sides shop and did not
touch the guards. A remesure of *that* finder (same as-of as
`scripts/mlb_total_public_fade_topk.py`) is the next totals question,
not a new publisher and not an XGBoost unpause.
