# RACING — thoroughbred horse racing: sources, the market grid, open items

> **Started 2026-11-15.** The scope (`docs/horse_racing_scope.md`, PR #1357)
> designed the tables, the pick, units, closing value and settlement, and
> catalogued the sources (`docs/horse_racing_sources.md`). The same day, mike:
> *"pickup the pr that was created and merged on horse racing. do additional
> research, invoke model skill."* This file is the league doc the
> league-models skill keeps: what the sources hold, the market grid, the leads
> found outside the repo, and what is open. The tables behind every number
> are in `docs/horse_racing_market_audit.md`.
>
> **Nothing is live and nothing is registered.** No `racing_*` table exists,
> no model id is in `config.py`, and no pick has been written. The two sport
> codes the scope proposed (`RACING`, `RACING_INTL`) are unused.

## What the sources hold (measured 2026-11-15)

| Source | What it holds | Stored |
|---|---|---|
| Betfair Australia's ANZ thoroughbred CSVs (free, no login) | **1,303,266 runners in 132,750 races, 2020-01 to 2026-10**, 11–14% of them New Zealand. One row a runner: the best back and lay and both book percentages **at the scheduled start**, win and place BSP, traded prices and volumes to the off and in play, win and place result. No form, no tote price, no fixed-odds price. | Supabase, `horse_racing|betfair_anz_thoroughbreds` (82 files) |
| Hong Kong 1997–2005 (Kaggle `gdaley/hkracing`, CC0) | 6,348 races, 79,447 runners, Sha Tin and Happy Valley. Final win and place pool odds, dividends, rating, draw, weights, sectional positions, finish times, jockey and trainer ids. Dates obscured by the author; order kept. | `horse_racing|gdaley_hkracing` |
| Hong Kong 2014–2017 (Kaggle `lantanacamara`, licence unknown) | 2,367 races, 30,189 runners, final win odds (shown as 99 above 99), positions, weights. | `horse_racing|lantanacamara_hong_kong_horse_racing` |
| Hong Kong 2016–2018 pools before the off (GitHub `nch015/horserace_data`, no licence stated) | 1,510 races, the win and place pools sampled a median 171 times a race (every 12 minutes, then every 6 in the last 3½ hours), dividends, and results with final odds back to 1979. Added 2026-11-15 evening. | `horse_racing|nch015_horserace_data` (6 rows) |
| UK/Ireland 1988–2026 (Kaggle `deltaromeo`, CDLA-Sharing) | 5.1 million runners with starting prices (the manifest's count). Added 2026-11-15 evening. | `horse_racing|deltaromeo_uk_ireland_1988_2026`: the 1.12 GB zip in 34 parts of 32 MiB |
| National Hunt 2005–2019 (Kaggle `sheikhbarabas`) | 744,347 runners, jumps only. | not downloaded |
| Equibase 2023 complimentary year | US past performances and charts, by email. "Not for wagering use." | not requested |

**Data checks, Betfair ANZ** (`scripts/horse/anz_study.py`, per year):

| Year | Races | BSP missing | Place BSP missing | Dead-heat races | BSP book (median) | Scheduled-off back book (median) |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | 18,786 | 0.05% | 11.8% | 80 | 1.0038 | 1.0190 |
| 2021 | 19,362 | 0.03% | 13.9% | 86 | 1.0026 | 1.0183 |
| 2022 | 19,496 | 0.01% | 13.6% | 80 | 1.0037 | 1.0189 |
| 2023 | 19,932 | 0.02% | 13.3% | 62 | 1.0041 | 1.0198 |
| 2024 | 19,550 | 0.07% | 12.1% | 32 | 1.0029 | 1.0184 |
| 2025 | 19,521 | 0.01% | 0.3% | 56 | 1.0034 | 1.0186 |
| 2026 | 16,103 | 0.01% | 0.4% | 55 | 1.0019 | 1.0210 |

Three traps found, each written into the study script:

- **One file writes its dates day-first.** `ANZ_Thoroughbreds_2025_04.csv`
  alone gives `1/04/2025`; every other file is ISO. The loader reads both and
  refuses a row outside its file's month (`tests/test_horse_study_math.py`).
- **13.1% of races have a scheduled-start snapshot that cannot be used**
  (17,436 races, overlapping causes): a back book outside 0.98–1.06 (5.1%;
  as low as 0.56, as high as 13.9), a lay book outside 0.90–1.02 (3.2%), a
  runner with no lay (1.0%), a runner whose lay is under its back (8.4%), and
  favourites shown at 1.01 that started at 3.46. They put
  runners into the wrong price band (the shortest band's mean BSP was 52%
  above its scheduled-start back with them, 0.9% without) and broke some
  unit totals. A live rule sees the same broken book, so it skips the race;
  the study does too (115,296 of 132,681 fully priced races remain).
- **The place-BSP fill rate changes in 2025**: 12–14% of runners have none
  in 2020–2024, under 0.5% after. A place result pooled across that break
  mixes two populations.

Hong Kong's checks are in the study doc, §3.

## Where a bettor in the United States can bet a race (scouted 2026-11-15)

Read from operator, regulator and trade pages on 2026-11-15. The facts that
decide the grid are here; every source URL, and which facts rest only on a
search engine's excerpt, are in `docs/horse_racing_scout_us_outlets.md`.

| Outlet | Price | What it offers outside the US |
|---|---|---|
| DraftKings Racing (DK Horse) | pool (pari-mutuel); joining the host track's pool rests on a search excerpt only | UK, Ireland, Japan, Dubai, Australia, Sweden, Korea; **Hong Kong disputed** (one page lists it, one does not) |
| FanDuel Racing (formerly TVG) | pool | Australia (~120 tracks), France (~90), UK (~75), Hong Kong (Sha Tin), Japan (local-government tracks; JRA not confirmed), New Zealand and more. Began betting into **commingled Hong Kong Jockey Club pools** on 2014-03-31 (DRF); whether it still commingles in 2026 was not confirmed |
| Xpressbet (1/ST BET) | pool | Hong Kong (both tracks; commingled HKJC pools from 2014-07-01, per a 2014 announcement; 2026 not confirmed), Japan (local-government only), Australia, New Zealand, UK, Ireland, France and more |
| TwinSpires, NYRA Bets, AmWager, BetMGM Racing, Caesars Racebook | pool | wide lists; TwinSpires' own pages did not open (search excerpts only) |
| bet365 (Colorado, New Jersey) | **fixed odds** | about 140 tracks in Colorado, mostly Australian, UK and Irish |
| MonmouthBets (New Jersey) | fixed odds | five US tracks (2023 list) |

- **No exchange.** Betfair's New Jersey exchange closed 2020-10-01. Kalshi
  listed nothing for the 2026 Derby; Polymarket listed a contract and took it
  down at Churchill's request.
- **Fixed odds are legal in New Jersey, Colorado and West Virginia**;
  Louisiana is writing its rules.
- **The take on the pools a US bettor joins**: the Hong Kong Jockey Club win
  and place pools pay back 82.5% (17.5% taken); NYRA 16% (win, place, show),
  Churchill Downs 17.5%, Santa Anita 15.43%, Gulfstream 17%; Australia's TAB
  14.25–25% by bet type. What a US customer pays on top for a commingled
  foreign pool was not found.
- **Retail rewards are small**: NYRA Bets 0.2–0.4%, AmWager 0.25–1.25%
  (from the published point rates).
- **Late money in US pools.** Computer-assisted teams were 25–30% of US
  handle (DRF, 2025) and bet in the final seconds: the share of win money in
  the last odds cycle at Aqueduct rose from 11.0% to 16.8% over the winters
  of 2022 to 2025. NYRA stopped them at 1–2 minutes to post in 2026 (their
  share fell from about 21% to 12–13%); Del Mar and Santa Anita at 2 minutes
  in 2025; Churchill and Keeneland have no cut-off.

**What this means for the grid.** For our users the price is a pool almost
everywhere: unknown when the pick is made, paid at the final odds, after
15–18% has been taken. The Betfair exchange is a reference here, not a book a
pick could name. Hong Kong is the one jurisdiction where the free files hold
the pool a US outlet offered in 2026 and was commingled into as of 2014
(2026 commingling not confirmed).

## The market grid

| Market | Settles on | Inputs held | Prices | Baseline | Methods tried | Result | Status |
|---|---|---|---|---|---|---|---|
| Win, Hong Kong pools (offered by US outlets in 2026; commingled as of 2014, 2026 not confirmed) | official first; a dead heat splits | runner facts 1979–2018 | final pool odds 1997–2005 and 2014–2017; **the pool before the off, 2016–2018** (to about 5.6 minutes out) | every band −13% to −28%, longshots −48% to −54%; favourite −16.7% and −14.2% | pool calibration; Bolton–Chapman fundamentals; Benter blend against the final pool and against the pool 5–12 minutes out; late money (six lead pairs); removal of each feature group; split by meeting | decided before the off and paid at the dividend: every runner −19.2% to −19.6% at every lead; the form model carries a little against the pool before the off (`b` +0.14 to +0.21) and none against the close, and its bets lose; 183 bet sets, none with an interval above zero | **nothing clears** (audit §3, §3b, §7) |
| Place, Hong Kong pools | first three (7+ runners) | the same | final place odds | −18.4% betting every runner | Harville against the win pool (the "Dr Z" test), raw and calibrated, on final pools and on both pools before the off; by field size | before the off, graded 2017/18: −7.6% to −36.9% at every lead and cut; every field size loses | **nothing clears** (audit §3a, §7a) |
| Win, Australia and New Zealand (Betfair exchange; not bettable from the US) | Betfair's result; a dead heat splits | prices only, no form | scheduled-start back and lay, BSP, 2020-01 to 2026-10 | every band negative net of commission (−0.70% to −12.6% at BSP); the favourite negative every year | price bands at two prices; favourites by year and by track size; BSP against the back; a logit on the scheduled-start prices | audit §4, §4b | **nothing clears** |
| Place, Australia and New Zealand (Betfair) | Betfair's place market (2 or 3 places) | the same | place BSP | negative in every Harville band net | Harville raw and discounted; a calibrated rule with a predicted place BSP; split by field size | every year negative net; the best gross cut −0.09% | **nothing clears** (audit §4a) |
| Win and place, US pools | official order after any DQ | none | none free: Equibase charts $219.95/month, HDW $119/month; the free 2023 Equibase year is "not for wagering use" | not measured | none | | **parked: no price.** Routes tried: the free files (none US), Kaggle (NYRA's 2022 set needs a login), Equibase (paid, or free with a no-wagering licence), the odds feed (no racing) |
| Show (US) | first three | none | none | | | | parked, as US win |
| Win and place, UK and Ireland | official result | 5.1 million runners with starting prices (not downloaded) | starting price only | not measured | none | | **to do**: the free 1.12 GB set; a starting price is bettable at UK books, not from the US |
| Win, Australian pools (FanDuel Racing and others offer Australian tracks; whether into the TAB's pool was not established) | TAB result | none | none free (Punting Form Starter, $59.00/Month as printed, carries TAB starting prices) | | | | parked: no price held |
| Each-way | two bets, win and place terms | | | | | | parked: the unit function grades one result a row (scope §5) |
| Exacta, trifecta, quinella, multi-race | dividends | | Hong Kong win and place dividends only | | | | parked: no exotic dividends held |
| Fixed odds (bet365 Colorado and New Jersey) | the book's rules | | none found | | | | parked: no price history found |
| In running (Betfair) | | | in-play traded prices only, no path | | | | parked: not bettable from the US |

Every "nothing clears" row names its own mechanisms and the stuck ladder in
the audit, §5.

## What would have to change before a model could pass

1. **A price closer to the off than 5 minutes.** The free Hong Kong path
   (2016–2018, added 2026-11-15) answered the "pre-off price" question it
   could: decided on the pool 5.6 to 33 minutes out and paid at the
   dividend, nothing clears, and 84% of what the pool learns after 30 minutes
   out arrives after its last bettable snapshot (audit §7). A form model
   holds a little information the pool 5–12 minutes out lacks, and the close
   holds all of it. So the remaining test needs a decision in the last minute
   or two, which needs a finer path than one snapshot every 6 minutes:
   the US$499 HKJC odds-movement archive (win and place from December 2021,
   polled about every 1 or 5 minutes), or Betfair's own history (behind an
   account).
2. **A sharp price against the pool**, the mechanism that has worked most
   often in this repo (a sharp reference against a softer price on the same
   event, `methods.md` §2): Betfair's price on a Hong Kong or US race against
   the pool a US outlet sells, both at a moment before the off. Nothing free
   holds both series.
3. **A book a pick may name**, with a licence that covers the app, Discord
   and push (scope §8, unchanged).

## Leads found outside the repo (scouted 2026-11-15)

28 leads were read (all of them, with sources: `docs/horse_racing_scout_leads.md`); these decided an experiment:

| Lead | Source | Claim | Here |
|---|---|---|---|
| Exchanges carry less favourite-longshot bias than bookmakers | Smith, Paton and Vaughan Williams, *Economica* 2006 | lower biases on exchanges | BSP within 0.2 points in every band of 8,000+ runners |
| Place pools mispriced against the win pool | Hausch, Ziemba and Rubinstein, *Management Science* 1981; Ziemba 2012 | "substantial positive profits" in US place and show pools | null in Hong Kong's final pools and on the exchange |
| Harville over-rates favourites for a place | Lo, Bacon-Shone and Busche, *Management Science* 1995 | Henery and Stern fit better | confirmed in both markets (said 0.84, placed 0.75); both place markets already price it |
| Fundamentals plus the public, blended | Benter 1994; Bolton and Chapman 1986; Chapman 2008 (2,000 Hong Kong races) | positive returns in Hong Kong | null against the final pool, 1999–2004 |
| A model on market prices alone | Sung and Johnson, *Economica* 2010 | "substantial abnormal returns" | null on the exchange's scheduled-start prices: log loss 1.7906 against the back's 1.7907, bets −3.7% to −4.0% net (audit §4b) |
| Late money is informed, and priced by the off | Betfair Automation Hub, "Do #theyknow?"; Hanyu et al., arXiv 2509.14645 (JRA 2004–2023) | plunges pay only from the early price; ex-ante predictability "very limited" | consistent: BSP beats the scheduled-start back on log loss (1.7981 against 1.8017) |
| Public ratings models against BSP | Betfair's Hub ratings tutorial | back at BSP −8.97% on 8,356 bets at 5% commission | the bar a form model would have to clear |
| A Hong Kong gradient-boosting model, 2015–2017 | RaceQuant student project, NYC Data Science Academy | −1.13% flat on 805 bets | the bar on the recent Hong Kong set |

Not found anywhere: a data dictionary for the Betfair ANZ files, a 2015–2026
study of the favourite at BSP after commission, a New Zealand commission
rate, and any racing model with a published return on the Kaggle Hong Kong
set.

## Open items

- The UK/Ireland starting-price set: download (1.12 GB), store, grade the
  blind bets by price band (issue #1370).
- Store each new Betfair ANZ monthly file as it is published, from the
  2026-11 file onward (issue #1371).
- A pre-off price path and a US pool series, both behind a purchase or an
  account: decisions for mike.
