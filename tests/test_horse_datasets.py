"""The horse racing fetch list. No network. The download itself is a local run
of scripts/horse/fetch_datasets.py, not this file."""
from __future__ import annotations

from pathlib import Path

from scripts.horse.fetch_datasets import (
    betfair_names,
    iter_items,
    kaggle_url,
    load_manifest,
    manual_rows,
)


def test_the_manifest_names_the_public_sets_and_their_licences():
    manifest = load_manifest()
    by_id = {row["id"]: row for row in manifest["kaggle"]}
    assert by_id["gdaley-hkracing"]["licence"] == "CC0: Public Domain"
    assert by_id["gdaley-hkracing"]["zip_bytes"] == 3584412
    assert by_id["lantanacamara-hong-kong-horse-racing"]["licence"] == "Unknown"
    uk = by_id["deltaromeo-uk-ireland-1988-2026"]
    assert uk["large"] is True
    assert uk["zip_bytes"] == 1120674866
    assert "CDLA" in uk["licence"] or "Community Data License Agreement" in uk["licence"]
    jumps = by_id["sheikhbarabas-uk-ireland-2005-2019"]
    assert jumps["licence"] == "Unknown"
    assert jumps["zip_bytes"] == 78948203


def test_kaggle_uses_the_public_download_url():
    assert kaggle_url("gdaley", "hkracing") == (
        "https://www.kaggle.com/api/v1/datasets/download/gdaley/hkracing"
    )


def test_betfair_thoroughbred_names_match_the_listing():
    manifest = load_manifest()
    names = betfair_names(manifest["betfair_anz_thoroughbreds"])
    assert names[:6] == [f"ANZ_Thoroughbreds_{year}.zip" for year in range(2020, 2026)]
    assert names[-1] == "ANZ_Thoroughbreds_2026_10.csv"
    assert len(names) == 16
    assert manifest["betfair_anz_thoroughbreds"]["base"].endswith("/data/assets/")


def test_all_skips_the_large_zip_and_an_explicit_id_does_not():
    manifest = load_manifest()
    everything = iter_items(manifest, only=None, include_large=False)
    ids = {item["id"] for item in everything}
    assert "deltaromeo-uk-ireland-1988-2026" not in ids
    assert "gdaley-hkracing" in ids
    assert "betfair-ANZ_Thoroughbreds_2026_10.csv" in ids
    named = iter_items(manifest, only={"deltaromeo-uk-ireland-1988-2026"}, include_large=False)
    assert [item["id"] for item in named] == ["deltaromeo-uk-ireland-1988-2026"]


def test_the_cc0_sample_is_a_few_rows():
    root = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "horse"
    sample = (root / "gdaley_races_sample.csv").read_text(encoding="utf-8")
    licence = (root / "LICENCE.txt").read_text(encoding="utf-8")
    assert sample.startswith("race_id,date,venue,")
    assert len(sample.splitlines()) == 4
    assert len(sample.encode("utf-8")) < 8_000
    assert "CC0" in licence


def test_equibase_is_manual_and_is_not_a_download():
    manifest = load_manifest()
    rows = manual_rows(manifest, only=None)
    assert [row["id"] for row in rows] == ["equibase-2023"]
    text = rows[0]["licence"].lower()
    assert "non-commercial" in text
    assert "wagering" in text
    assert "redistribution" in text
    assert rows[0]["email"] == "signalbaseskinny@gmail.com"
    downloaded = {item["id"] for item in iter_items(manifest, only=None, include_large=True)}
    assert "equibase-2023" not in downloaded
