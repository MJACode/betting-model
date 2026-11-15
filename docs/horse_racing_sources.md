# Horse racing sources

Vendor prices below are from pages checked 14 Nov 2026, copied as printed.
A page with no number is marked unknown. The design that uses these sources
is `docs/horse_racing_scope.md`. Public files are fetched by
`scripts/horse/fetch_datasets.py` into gitignored `data/horse/`.

## US thoroughbred

| Source | What it is | Price | Limit |
|---|---|---|---|
| [HDW via JCapper Flex](http://www.jcapper.com/horseracingdata/) | All North American thoroughbred past performances (`.JCP`) and chart files (`F.TXT`). | $5.95/day Silver or $7.95/day Platinum, capped at $89 or $119/month after 15 download days. | No API. The server keeps the last 45 days. Best cheap structured option. |
| [Equibase 2023 complimentary set](https://www.equibase.com/handicappersdata.cfm) | Full-year 2023 past performances and matching result charts. | Free, by email. | See below. Scraping the public Equibase site is banned. |
| [TrackMaster Plus Pro](https://www.trackmaster.com/products/tmu) | XML data files. | $5/card, 20 downloads $49.95/month, unlimited $149.95/month. | One US file vendor, not this and HDW together. |
| [Equibase downloadable charts](https://www.equibase.com/products/whataredownloadablecharts.cfm) | CSV/XML results with speed figures and final odds. | $1.50/card, or $219.95/month. | Results and final odds. Not a live tote. |
| Horse Racing Nation data files | Data files. | $299/month. | Price from this note; not re-fetched on 15 Nov. |
| Equibase Industry Services | Commercial PP, simulcast, and tote. | Quote only. | The production licence if a personal file plan does not allow a published model. |
| Brisnet | Comma-delimited past performances and charts, with an archive. | Not confirmed. | |
| PDF-only products | Equibase PPs, DRF Formulator $239.95/month, TimeformUS, Thoro-Graph, Ragozin. | As named. | Figure overlays. Not a feed. |

No cheap live US tote API was found. The Odds API sports list does not
include racing. Final odds come from the result charts.

### Equibase 2023, by hand

Registration is the link above. The file arrives by email at
`signalbaseskinny@gmail.com` in 5–7 business days. Terms: internal,
non-commercial testing only. Not for wagering use. Not for redistribution.
`scripts/horse/fetch_datasets.py` prints those steps and does not download
the file. It is never committed. Drop it in `data/horse/equibase-2023/` if
it is used at all.

## UK, Ireland, Hong Kong

| Source | What it is | Price | Limit |
|---|---|---|---|
| [The Racing API](https://www.theracingapi.com/) | REST/JSON. Core coverage is UK, Ireland, and Hong Kong, plus group races and selected handicaps worldwide. | Free, £27.99, £59.99 (Standard: bookmaker odds plus 12 months of results), £99.99 (Pro: odds history plus racecards). Full-history add-on £499. | Updates every 3 minutes, 5 requests/second. No resale. Not for betting operators. The US add-on and the Australia add-on are closed to new subscribers. `/pricing` returned 404 on 15 Nov 2026; confirm the pounds in the dashboard. |
| [Betfair historical data](https://support.developer.betfair.com/hc/en-us/articles/360019984158-Are-bulk-purchase-discounts-available) | Time-stamped exchange prices, including US markets where the file has them. The API also has live exchange prices. | Horse racing Advanced £69/month or £699/year. Pro £230/month or £2,299/year. Basic is free: 1-minute odds, no volume. | A Betfair account. Australian and New Zealand customers should email `automation@betfair.com.au` before buying from the UK historic site. US residents generally cannot register from a restricted location. |
| Timeform API | GB/IE ratings. | From £500/month. | Not required for the first model. |
| HKJC | Results on the official site. | No public bulk API. | The Racing API is the practical HK card. |

## Australia and New Zealand

Checked 14 Nov 2026 (ET). New Zealand is noted on each row.

| Source | Coverage | Price | Limit |
|---|---|---|---|
| [Punting Form](https://puntingform.com.au/pricing) | Australia, Hong Kong, and Singapore. Form, results, ratings, speed maps, official SP / TAB / Betfair starting prices and fluctuations, plus proprietary 200m sectionals. REST at `https://api.puntingform.com.au`, and CSV. New Zealand is not listed. North American sectionals are described as not yet launched. | Printed with no currency code. The operator is ABettorEdge Pty Limited, Australia. Free (no API). Starter $59.00/Month (form and results API/CSV). Professional $297.00/Month (sectional viewing for all TAB meetings). Modeller unknown (`sales@puntingform.com.au`): sectionals API, historical Betfair prices, and the option to buy historical sectionals from 2014 and point-in-time data. Those add-on prices are unknown. | [Terms](https://www.puntingform.com.au/terms-and-conditions): personal use. Commercial use needs prior written consent. |
| [Racing Australia materials](https://www.racingaustralia.horse/AboutUs/Materials.aspx) | Nominations, acceptances, trials, fields, form, results, positions in-running for TAB meetings, plus comments, summaries, and speed maps. | No public price. From 1 July 2025 RA appointed five wholesalers: BettorData, BetMakers, Mediality Racing, News Perform (Punters Paradise), and Racing and Sports. End-user prices are the wholesaler's. | Personal, non-commercial use of the website. No scraping. NZ is out of scope for RA. |
| [Racing and Sports](https://racingandsports.company/) | B2B form and odds for 33+ jurisdictions, thoroughbred, harness, and greyhound. The about page (19 Jul 2022) names Australia, New Zealand, Hong Kong, Japan, Singapore, Korea, Macau, Malaysia, South Africa, UK, Ireland, France, and Germany. | Quote only. | Commercial contract. An approved Racing Australia distributor. |
| [Betfair Australia CSVs](https://betfair-datascientists.github.io/data/dataListing/) | Australia and New Zealand thoroughbred market snapshots. Not a form feed. Fields include max/min matched prices and volume, weighted average price, BSP, and the winner. Monthly files also carry best available prices and overrounds at the scheduled start, plus win and place results. | Free. No login. | Annual zips 2020–2025 and monthly CSVs through 2026-10, under `https://betfair-datascientists.github.io/data/assets/`. The fetch script takes the thoroughbred files only. |
| [Krok Odds](https://krokodds.com.au/api-access) | Every AU thoroughbred, harness, and greyhound meeting: form, results, sectionals, fixed odds, Betfair BSP, tote. | Free tier: 50 credits/month, 5 requests/minute, 14 days of odds history. API plan A$49/month: 50,000 credits, 500 requests/minute. | Personal analysis, with attribution when the data is shown. Resale of the raw feed is not included. NZ is not listed. |
| NZTR / LoveRacing | Race information and results in the browser. | No public bulk API or price list found. | `https://xml.tab.co.nz/` returned 404 on this check. |

The cheap Australia/New Zealand start is Punting Form Starter at
$59.00/Month plus the free Betfair CSVs.

## Kaggle and the other public files

Downloaded 14 Nov 2026 with an unauthenticated GET to
`https://www.kaggle.com/api/v1/datasets/download/{owner}/{slug}`. No Kaggle
account was created. Sizes are the byte counts from that download. Row
counts are CSV records, not raw text lines. `scripts/horse/manifest.json`
is the same list, and the fetch script warns if a new download's size
differs.

| Dataset | Licence | Zip | What was in it |
|---|---|---|---|
| [gdaley/hkracing](https://www.kaggle.com/datasets/gdaley/hkracing) | CC0 | 3,584,412 bytes | `races.csv` 6,349 rows; `runs.csv` 79,447 rows. Dates in the file 1997-06-02 to 2005-08-28. The card says those dates are obscured. Names are not included. |
| [lantanacamara/hong-kong-horse-racing](https://www.kaggle.com/datasets/lantanacamara/hong-kong-horse-racing) | Unknown | 2,245,030 bytes | 2,367 race rows and 30,189 runner rows, 2014-09-14 to 2017-07-16. The card says the rows were extracted from HKJC. |
| [deltaromeo/horse-racing-results-ukireland-2015-2025](https://www.kaggle.com/datasets/deltaromeo/horse-racing-results-ukireland-2015-2025) | CDLA-Sharing 1.0 | 1,120,674,866 bytes (listing 3,947,445,590 uncompressed) | UK/Ireland results 1988-01-01 to 2026-10-23. 5,113,697 valid runner rows across the three CSVs. Starting prices, not a live feed. The fetch script does not take this one unless it is named. |
| [sheikhbarabas/horse-racing-results-uk-ireland-2005-to-2019](https://www.kaggle.com/datasets/sheikhbarabas/horse-racing-results-uk-ireland-2005-to-2019) | Unknown | 78,948,203 bytes | National Hunt only. 744,347 runner rows, 2005-04-24 to 2019-12-29 (30,573 rows have `date=NA`). |

NYRA Big Data Derby 2022 was not downloaded. The competition data list
returned HTTP 401, and a download returned HTTP 404. Community re-uploads
were left alone.

A few rows of the CC0 Hong Kong file are in `tests/fixtures/horse/` so a
test can see the shape. The other licences do not get a committed sample.

## Methods

The scope doc is where these are turned into a backtest. Short form, from
the same 14 Nov note:

- Bolton and Chapman 1986: a conditional logit per race.
- Benter 1994: a second stage that blends the model's log probability with
  the public tote's log probability, fit out of sample.
- Harville 1973, with a Benter or Lo/Bacon-Shone discount, for exotics.
  Exotics are parked.
- Fractional Kelly, capped for pool impact. Takeout is 15% or more. The
  published stake in this repo stays 1 unit to win until someone asks for
  a different stake.
- The close is the final tote or Betfair SP, not a two-sided book close.
