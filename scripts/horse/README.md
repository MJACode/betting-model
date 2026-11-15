# Horse racing files

`fetch_datasets.py` reads `manifest.json` and writes under `data/horse/`.
That directory is gitignored. The files are a regenerable download. They are
not the system of record, they are not committed, and the script does not
write a pick.

```bash
python -m scripts.horse.fetch_datasets --list
python -m scripts.horse.fetch_datasets --only gdaley-hkracing
python -m scripts.horse.fetch_datasets --all
python -m scripts.horse.fetch_datasets --only deltaromeo-uk-ireland-1988-2026
```

`--all` fetches both Hong Kong zips, the National Hunt zip, and the 16
Betfair Australia/NZ thoroughbred files. It skips the UK/Ireland 1988–2026
zip (1.12 GB, about 3.95 GB unzipped). Name that id, or pass
`--all --include-large`, to get it.
`--unzip` extracts a zip next to itself. A file already on disk is left
alone unless `--force` is set.

Measured sizes, row counts, and date ranges are in `manifest.json` and in
`docs/horse_racing_sources.md`. They were taken on 14 Nov 2026 from the
copies downloaded that day. A later Kaggle version can differ; the script
prints a warning when the byte count does not match, and it still keeps the
file.

## Licences

| Id | Licence | Commit a sample? |
|---|---|---|
| `gdaley-hkracing` | CC0 | Yes. `tests/fixtures/horse/` holds a few rows. |
| `lantanacamara-hong-kong-horse-racing` | Unknown. Card says the rows were taken from the HKJC site. | No. |
| `deltaromeo-uk-ireland-1988-2026` | CDLA-Sharing 1.0 | Not in git. The zip is too big, and a cut of it is not what was measured. |
| `sheikhbarabas-uk-ireland-2005-2019` | Unknown | No. |
| `betfair-anz-thoroughbreds` | Free CSV published by Betfair Australia. No login. | No. Fetch the file. |
| `equibase-2023` | Internal, non-commercial testing only. Not for wagering use. Not for redistribution. | Never. |

## Equibase 2023

Register at https://www.equibase.com/handicappersdata.cfm. The drop is
emailed to signalbaseskinny@gmail.com and takes 5–7 business days. Put it
in `data/horse/equibase-2023/` by hand. The fetch command prints this and
does not write a file. Do not commit it.

## Not fetched

NYRA Big Data Derby 2022 needs a Kaggle login. On 14 Nov 2026 the competition
data list returned HTTP 401 and a download returned HTTP 404. No account was
created. Community re-uploads were left alone.

Kaggle's public dataset URL is
`https://www.kaggle.com/api/v1/datasets/download/{owner}/{slug}` with no
token. Betfair thoroughbred files are the `ANZ_Thoroughbreds_*` links on
https://betfair-datascientists.github.io/data/dataListing/ (annual zips
2020–2025, monthly CSVs through 2026-10). Harness and greyhound files on
that page are not downloaded.
