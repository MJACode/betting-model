"""
Tests for the WNBA teams-list sports.core fallback in injury_ingestor
(session 116).

Since the 2026-08-05 site.api.espn.com IP block, the live team-id resolver
returned {} and injuries fell back to the static 12-franchise map — GSV/PDX/
TOR (2025-26 expansion teams) silently dropped out of injury coverage. The
core-API fallback resolves ids from the ESPN host that still serves the
worker. Fetch is injected — no network in these tests.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestors.injury_ingestor import (
    CORE_WNBA_TEAMS_URL,
    _fetch_wnba_espn_team_ids_core,
)


def _fake_fetch(docs):
    """Build an injectable fetch backed by a {url: doc} dict."""
    def fetch(url):
        if url not in docs:
            raise RuntimeError(f"unexpected fetch: {url}")
        doc = docs[url]
        if isinstance(doc, Exception):
            raise doc
        return doc
    return fetch


def _listing(refs):
    return {"items": [{"$ref": r} for r in refs]}


class TestCoreTeamsFallback:
    def test_resolves_expansion_teams_by_name(self):
        docs = {
            CORE_WNBA_TEAMS_URL: _listing([
                "https://core/teams/129",
                "http://core/teams/130",   # core emits http:// $refs
                "https://core/teams/17",
            ]),
            "https://core/teams/129": {
                "id": "129", "displayName": "Portland Fire",
                "location": "Portland", "name": "Fire"},
            # http:// ref is forced to https before fetch
            "https://core/teams/130": {
                "id": "130", "displayName": "Toronto Tempo",
                "location": "Toronto", "name": "Tempo"},
            "https://core/teams/17": {
                "id": "17", "displayName": "Las Vegas Aces",
                "location": "Las Vegas", "name": "Aces"},
        }
        resolved = _fetch_wnba_espn_team_ids_core(fetch=_fake_fetch(docs))
        assert resolved == {"PDX": 129, "TOR": 130, "LV": 17}

    def test_listing_failure_returns_empty(self):
        docs = {CORE_WNBA_TEAMS_URL: RuntimeError("403")}
        assert _fetch_wnba_espn_team_ids_core(fetch=_fake_fetch(docs)) == {}

    def test_one_bad_team_doc_does_not_sink_the_rest(self):
        docs = {
            CORE_WNBA_TEAMS_URL: _listing([
                "https://core/teams/bad",
                "https://core/teams/9",
            ]),
            "https://core/teams/bad": RuntimeError("500"),
            "https://core/teams/9": {
                "id": "9", "displayName": "New York Liberty",
                "location": "New York", "name": "Liberty"},
        }
        resolved = _fetch_wnba_espn_team_ids_core(fetch=_fake_fetch(docs))
        assert resolved == {"NY": 9}

    def test_unmatchable_name_skipped(self):
        docs = {
            CORE_WNBA_TEAMS_URL: _listing(["https://core/teams/99"]),
            "https://core/teams/99": {
                "id": "99", "displayName": "Team TBD",
                "location": "Nowhere", "name": "TBD"},
        }
        assert _fetch_wnba_espn_team_ids_core(fetch=_fake_fetch(docs)) == {}

    def test_unexpected_listing_shape_returns_empty(self):
        docs = {CORE_WNBA_TEAMS_URL: {"nope": True}}
        assert _fetch_wnba_espn_team_ids_core(fetch=_fake_fetch(docs)) == {}
