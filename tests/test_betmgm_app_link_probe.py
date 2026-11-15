"""The BetMGM app-link probe: pure parsers, and a run that writes nothing."""
import json

import scripts.betmgm_app_link_probe as probe
import tracking.job_queue as jq


def test_app_store_bundle_ids_are_read():
    payload = {"results": [{"trackId": 1430875409, "trackName": "BetMGM Sportsbook",
                            "bundleId": "com.playmgm.nj.sports2", "sellerName": "BetMGM"},
                           {"trackId": 1, "trackName": "no bundle"}]}
    assert probe.app_store_apps(payload) == [{"track_id": 1430875409, "name": "BetMGM Sportsbook",
                                              "bundle_id": "com.playmgm.nj.sports2", "seller": "BetMGM"}]


def test_only_app_handoff_meta_tags_are_kept():
    page = ('<meta name="apple-itunes-app" content="app-id=1430875409, app-argument=betmgmsports://x?a=1&amp;b=2">'
            '<meta property="al:ios:url" content="betmgmsports://y">'
            '<meta name="description" content="sports">')
    assert probe.meta_tags(page) == {"apple-itunes-app": "app-id=1430875409, app-argument=betmgmsports://x?a=1&b=2",
                                     "al:ios:url": "betmgmsports://y"}


def test_custom_schemes_skip_web_schemes():
    text = 'a "https://x.com/y" b "betmgmsports://sports/en?options=1-2-3" c ws://z d itms-apps://app'
    assert probe.custom_schemes(text) == ["betmgmsports://sports/en?options=1-2-3", "itms-apps://app"]


def test_snippets_find_needles_with_context():
    text = "x" * 300 + "window.location='betmgmsports://open'" + "y" * 300
    hits = probe.snippets(text, needles=("betmgmsports",), width=20)
    assert len(hits) == 1 and "betmgmsports://open" in hits[0]


def test_a_run_prints_a_summary_and_fails_only_when_nothing_was_reached(capsys):
    def get(url):
        if "itunes.apple.com/lookup" in url:
            return 200, json.dumps({"results": [{"trackId": 1430875409, "trackName": "BetMGM",
                                                 "bundleId": "com.playmgm.nj.sports2"}]}), None, url
        return None, "", "ConnectionError: refused", url
    assert probe.probe(get=get) == 0
    out = capsys.readouterr().out
    assert probe.SUMMARY_MARK in out and "SAME app" in out

    assert probe.probe(get=lambda url: (None, "", "ConnectionError: refused", url)) == 1


def test_the_job_type_is_registered_and_takes_no_args():
    fn, validate = jq.JOBS["betmgm_app_link_probe"]
    assert fn is jq._job_betmgm_app_link_probe
    assert validate({}) == {}
