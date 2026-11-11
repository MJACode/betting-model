"""The GitHub mirror records what the token may not read, and pages fully.

scripts/local_mirror_github.py exports each repo's issues, PRs, reviews,
settings and the rest as JSON. mike asked for the full setup; an item the
token is refused (webhooks and deploy keys need admin) must appear in the
report with its HTTP status, not vanish. No network here: a fake answers.
"""
from __future__ import annotations

import json

from scripts import local_mirror_github as lmg


class FakeGitHub(lmg.GitHub):
    def __init__(self, routes):
        super().__init__("not-a-real-token", opener=lambda *a, **k: None)
        self.routes = routes
        self.seen: list[str] = []

    def _request(self, url, accept="application/vnd.github+json"):
        path = url.replace(lmg.API, "")
        self.seen.append(path)
        self.calls += 1
        for prefix, answer in self.routes.items():
            if path.split("?")[0] == prefix:
                status, data, headers = answer(path) if callable(answer) else answer
                return status, json.dumps(data).encode(), headers
        return 404, json.dumps({"message": "Not Found"}).encode(), {}


def test_next_link_is_followed_until_the_last_page():
    assert lmg.parse_next_link(
        '<https://api.github.com/x?page=2>; rel="next", <https://api.github.com/x?page=9>; rel="last"'
    ) == "https://api.github.com/x?page=2"
    assert lmg.parse_next_link('<https://api.github.com/x?page=1>; rel="prev"') is None

    def labels(path):
        if "page=2" in path:
            return 200, [{"name": "c"}], {}
        return 200, [{"name": "a"}, {"name": "b"}], {"Link": '<https://api.github.com/repos/o/r/labels?per_page=100&page=2>; rel="next"'}
    gh = FakeGitHub({"/repos/o/r/labels": labels})
    status, items, capped = gh.paginate("/repos/o/r/labels")
    assert (status, [i["name"] for i in items], capped) == (200, ["a", "b", "c"], False)


def test_refused_items_are_recorded_with_their_status(tmp_path):
    pulls = [{"number": 1, "updated_at": "2026-11-01T00:00:00Z"},
             {"number": 2, "updated_at": "2026-11-02T00:00:00Z"}]
    routes = {
        "/repos/o/r": (200, {"full_name": "o/r"}, {}),
        "/repos/o/r/pulls": (200, pulls, {}),
        "/repos/o/r/pulls/1/reviews": (200, [{"id": 11, "state": "APPROVED"}], {}),
        "/repos/o/r/pulls/2/reviews": (200, [], {}),
        "/repos/o/r/hooks": (404, {"message": "Not Found"}, {}),
        "/repos/o/r/keys": (403, {"message": "Must have admin rights to Repository."}, {}),
    }
    gh = FakeGitHub(routes)
    report = {r["item"]: r for r in lmg.export_meta(gh, "o/r", tmp_path)}
    assert report["hooks"]["status"] == 404
    assert report["deploy_keys"] == {"item": "deploy_keys", "status": 403,
                                     "message": "Must have admin rights to Repository."}
    assert report["pulls"]["count"] == 2
    assert report["pull_reviews"]["count"] == 1
    saved = json.loads((tmp_path / "_export_report.json").read_text(encoding="utf-8"))
    assert {i["item"] for i in saved["items"]} >= {"hooks", "deploy_keys", "actions_secrets"}

    # A second export re-fetches reviews only for PRs that changed.
    gh2 = FakeGitHub(routes)
    lmg.export_meta(gh2, "o/r", tmp_path)
    assert not any("/reviews" in p for p in gh2.seen)
