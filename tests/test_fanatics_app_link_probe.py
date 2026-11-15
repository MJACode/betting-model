"""The Fanatics app-link probe: a run that writes nothing and reports what it reached."""
import json

import scripts.fanatics_app_link_probe as probe
import tracking.job_queue as jq


def _no_hop(url):
    return None, None, "", "ConnectionError: refused"


def test_an_aasa_and_a_scheme_in_a_script_reach_the_summary(capsys):
    aasa = {"applinks": {"details": [{"appIDs": ["TEAM.com.fanatics.sportsbook"],
                                      "components": [{"/": "/betslip/*"}]}]}}
    page = '<script src="/static/app.js"></script>'
    js = 'open("fanaticssportsbook://betslip?selectionIds=123")'

    def get(url):
        if "cdn-apple.com/a/v1/sportsbook.fanatics.com" in url:
            return 200, json.dumps(aasa), None, url
        if url == "https://sportsbook.fanatics.com/":
            return 200, page, None, url
        if url.endswith("/static/app.js"):
            return 200, js, None, url
        return None, "", "ConnectionError: refused", url

    assert probe.probe(get=get, hop=_no_hop) == 0
    out = capsys.readouterr().out
    assert "aasa sportsbook.fanatics.com: apps=['TEAM.com.fanatics.sportsbook']" in out
    assert "/betslip/*" in out
    assert "fanaticssportsbook://betslip?selectionIds=123" in out.split(probe.SUMMARY_MARK)[1]


def test_nothing_reached_is_a_failure():
    assert probe.probe(get=lambda url: (None, "", "ConnectionError: refused", url), hop=_no_hop) == 1


def test_the_job_type_is_registered_and_takes_no_args():
    fn, validate = jq.JOBS["fanatics_app_link_probe"]
    assert fn is jq._job_fanatics_app_link_probe
    assert validate({}) == {}


def test_a_share_link_is_followed_hop_by_hop_and_its_target_reaches_the_summary(capsys):
    hops = {
        "https://fanatics.onelink.me/5kut/mgsfxrr2":
            (302, "https://betfanatics.com/s?deep_link_value=%2Fbetslip%2Fshare%2Fabc-123", "", None),
        "https://betfanatics.com/s?deep_link_value=%2Fbetslip%2Fshare%2Fabc-123":
            (200, None, '<a href="fanaticssportsbook://betslip/share/abc-123">open</a>', None),
    }
    hop = lambda url: hops.get(url, (None, None, "", "ConnectionError: refused"))  # noqa: E731
    trail = probe.share_link_trail("https://fanatics.onelink.me/5kut/mgsfxrr2", hop=hop)
    assert [t["status"] for t in trail] == [302, 200]
    assert any("fanaticssportsbook://betslip/share/abc-123" in h for h in trail[1]["hits"])

    assert probe.probe(get=lambda url: (None, "", "ConnectionError: refused", url), hop=hop) == 0
    out = capsys.readouterr().out.split(probe.SUMMARY_MARK)[1]
    assert "share mgsfxrr2 -> https://betfanatics.com/s?deep_link_value=/betslip/share/abc-123" in out
