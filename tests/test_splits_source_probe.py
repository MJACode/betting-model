"""The Scoreboard splits source probe: parses what it is given, writes nothing."""
import json

import pytest

import scripts.splits_source_probe as probe
import tracking.job_queue as jq

DK_HTML = """<html><body><a href="/draftkings-sportsbook-betting-splits/?tb_eg=88808">NFL</a>
<table><tr><th>Handle</th><th>Bets</th></tr>
<tr><td>Chicago Bears</td><td>39%</td><td>48%</td></tr>
<tr><td>Seattle Seahawks</td><td>61%</td><td>52%</td></tr></table>
<iframe src="https://widgets.example/splits"></iframe></body></html>"""

AN = {"games": [{"markets": {
    "15": {"event": {"spread": [{"side": "home", "bet_info": {"tickets": {"percent": 42}}}]}},
    "68": {"event": {"spread": [{"side": "home", "bet_info": {"tickets": {"percent": None}}}]}},
}}]}


def test_dk_html_is_described_from_the_page_itself():
    d = probe.describe_dk_html(DK_HTML)
    assert (d["tables"], d["rows"], d["percent_cells"]) == (1, 3, 4)
    assert d["iframes"] == ["https://widgets.example/splits"]
    assert d["split_links"] == ["/draftkings-sportsbook-betting-splits/?tb_eg=88808"]
    assert "Chicago Bears 39% 48%" in d["handle_window"]


def test_only_a_book_with_a_percent_counts_as_carrying_a_split():
    d = probe.describe_an_games(AN)
    assert d == {"games": 1, "books": {"15": 1, "68": 1}, "books_with_split": {"15": 1}}


def test_a_blocked_dk_page_fails_the_job_and_an_is_still_measured(capsys):
    calls = []

    def get(url, **kw):
        calls.append(url)
        if "dknetwork" in url:
            return 403, "", None
        if url.endswith("/books"):
            return 200, json.dumps({"books": [{"id": 68, "display_name": "DraftKings"}]}), None
        return 200, json.dumps(AN), None

    assert probe.probe(get, today="2026-11-05") == 1
    out = capsys.readouterr().out.split(probe.SUMMARY_MARK, 1)[1]
    assert "dk: HTTP 403" in out
    assert "DraftKings ids: ['68=DraftKings']" in out
    assert any("scoreboard/nfl" in u for u in calls)


def test_the_job_is_registered_and_takes_no_args():
    assert jq.JOBS["splits_source_probe"][0] is jq._job_splits_source_probe
    assert jq._validate_splits_source_probe({}) == {}
    with pytest.raises(ValueError):
        jq._validate_splits_source_probe({"url": "https://example.com"})
