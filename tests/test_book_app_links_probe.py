"""The sportsbook app-link probe: reads AASA rules the way iOS does, writes nothing."""
import json

import pytest

import scripts.book_app_links_probe as probe
import tracking.job_queue as jq

MGM_LINK = "https://sports.nj.betmgm.com/en/sports?options=1-2-3&type=Single"


def _aasa(**detail):
    return {"applinks": {"details": [{"appIDs": ["TEAM.com.example.app"], **detail}]}}


def test_a_components_rule_on_the_path_claims_the_link():
    v = probe.link_verdict(_aasa(components=[{"/": "/en/sports*"}]), MGM_LINK)
    assert v == [{"app_ids": ["TEAM.com.example.app"], "claimed": True,
                  "rule": {"/": "/en/sports*"}}]


def test_an_exclude_rule_first_means_not_claimed():
    aasa = _aasa(components=[{"/": "/en/sports", "exclude": True}, {"/": "*"}])
    assert probe.link_verdict(aasa, MGM_LINK)[0]["claimed"] is False


def test_a_query_rule_must_match_the_named_parameter():
    hit = _aasa(components=[{"/": "/en/sports", "?": {"options": "*"}}])
    miss = _aasa(components=[{"/": "/en/sports", "?": {"betslip": "*"}}])
    assert probe.link_verdict(hit, MGM_LINK)[0]["claimed"] is True
    assert probe.link_verdict(miss, MGM_LINK)[0]["claimed"] is False


def test_old_paths_format_and_its_not_prefix():
    assert probe.link_verdict(_aasa(paths=["/en/*"]), MGM_LINK)[0]["claimed"] is True
    assert probe.link_verdict(_aasa(paths=["NOT /en/*", "*"]), MGM_LINK)[0]["claimed"] is False
    assert probe.link_verdict(_aasa(paths=["/casino/*"]), MGM_LINK)[0]["claimed"] is False


def test_the_cdn_copy_is_read_first_and_a_missing_file_is_reported(capsys):
    calls = []

    def get(url):
        calls.append(url)
        if "cdn-apple.com" in url and "betmgm" in url:
            return 200, json.dumps(_aasa(components=[{"/": "/en/sports*"}])), None
        return 404, "", None

    assert probe.probe(get) == 0
    out = capsys.readouterr().out.split(probe.SUMMARY_MARK, 1)[1]
    assert "betmgm sports.nj.betmgm.com: CLAIMED" in out
    assert "draftkings sportsbook.draftkings.com: NO AASA" in out
    assert calls[0] == "https://app-site-association.cdn-apple.com/a/v1/sports.nj.betmgm.com"


def test_nothing_fetched_fails_the_job():
    assert probe.probe(lambda url: (None, "", "ConnectionError: refused")) == 1


def test_the_job_is_registered_and_takes_no_args():
    assert jq.JOBS["book_app_links_probe"][0] is jq._job_book_app_links_probe
    assert jq._validate_book_app_links_probe({}) == {}
    with pytest.raises(ValueError):
        jq._validate_book_app_links_probe({"url": "https://example.com"})
