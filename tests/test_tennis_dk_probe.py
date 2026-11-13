"""DraftKings' tennis board reader: the league ids on the tennis page, and
every selection of a league board as a row. The page snippets are copied from
the page mike's run saved on 2026-11-13; the board is the repo's real
DraftKings fixture (tests/fixtures/dk_ncaab_board_2026-11-13.json), which uses
the same sportscontent shape every sport's board does."""
import json
from pathlib import Path

from scripts import tennis_dk_probe as dk

PAGE = (
    '{"displayGroupId":6,"eventGroupId":218378,"eventGroupName":"ITF - Zamora (M)",'
    '"nameIdentifier":"m15-zamora","deepLink":"","tags":["FeaturedSubcategory","OSB"]},'
    '{"displayGroupId":6,"eventGroupId":215568,"eventGroupName":"Challenger Doubles - Brisbane",'
    '"nameIdentifier":"challenger-doubles-brisbane"},'
    '{"name":"Challenger - Orleans","displayGroupId":"6","eventGroupId":"73124",'
    '"path":"/leagues/tennis/challenger-orleans"},'
    '{"name":"NHL","displayGroupId":"8","eventGroupId":"42133","path":"/leagues/hockey/nhl"}'
)


def test_league_ids_from_both_shapes_singles_only_tennis_only():
    ids = dk.league_ids(PAGE)
    assert ids == {"218378": "ITF - Zamora (M)", "73124": "Challenger - Orleans"}


def test_every_selection_becomes_a_row_with_its_market_and_event():
    body = json.loads((Path(__file__).parent / "fixtures" / "dk_ncaab_board_2026-11-13.json")
                      .read_text(encoding="utf-8"))
    rows = dk.selection_rows(body, "92483", "test", "2026-11-13T00:00:00+00:00")
    known = {str(m["id"]) for m in body["markets"]}
    assert len(rows) == sum(1 for s in body["selections"] if str(s["marketId"]) in known) > 0
    rec = dict(zip(dk.COLS, next(r for r in rows if r[0] == "0HC87219107P350_3")))
    assert rec["american"] == -115 and rec["points"] == 3.5          # the Unicode minus read
    assert rec["outcome_type"] == "Away" and rec["label"] == "West Florida"
    assert rec["dk_event_id"] == "35006878" and rec["source"] == dk.SOURCE
    assert rec["p1_name"] and rec["p2_name"]                         # both players placed


def test_a_pass_stores_only_what_changed(monkeypatch):
    body = json.loads((Path(__file__).parent / "fixtures" / "dk_ncaab_board_2026-11-13.json")
                      .read_text(encoding="utf-8"))

    class _R:
        def __init__(self, code, text="", js=None):
            self.status_code, self.text, self._js = code, text, js

        def json(self):
            return self._js

    class _S:
        def get(self, url, timeout=None):
            return _R(200, text=PAGE) if "sports/tennis" in url else _R(200, js=body)

    class _C:
        def __init__(self):
            self.n = 0

        def executemany(self, sql, rows):
            self.n += len(rows)

        def commit(self):
            pass

    monkeypatch.setattr(dk, "PAUSE_S", 0)
    conn, last = _C(), {}
    a = dk.one_pass(_S(), conn, last, None)
    b = dk.one_pass(_S(), conn, last, None)
    assert a["leagues"] == 2 and a["stored"] > 0
    assert b["stored"] == 0 and conn.n == a["stored"]                # nothing changed, nothing stored


def _board_with_pages():
    return {
        "events": [{"id": "E1", "name": "A vs B", "startEventDate": "2026-11-14T02:00:00Z",
                    "status": "NOT_STARTED",
                    "participants": [{"name": "A", "sortOrder": 1}, {"name": "B", "sortOrder": 2}]}],
        "markets": [{"id": "M1", "eventId": "E1", "name": "Moneyline", "subcategoryId": 6364, "main": True}],
        "selections": [{"id": "S1", "marketId": "M1", "label": "A", "outcomeType": "Home",
                        "displayOdds": {"american": "\u2212150"}},
                       {"id": "S2", "marketId": "M1", "label": "B", "outcomeType": "Away",
                        "displayOdds": {"american": "+125"}}],
        "categories": [{"id": 488, "name": "Match Lines"}, {"id": 500, "name": "Game by Game"}],
        "subcategories": [{"id": 6364, "categoryId": 488, "name": "Moneyline"},
                          {"id": 16090, "categoryId": 488, "name": "Total Games"},
                          {"id": 12256, "categoryId": 500, "name": "Game Winner"}],
    }


def test_subpages_skip_the_default_page_and_in_play_kinds():
    assert dk.subpages(_board_with_pages()) == [("488", "16090", "Total Games")]


def _session(responses):
    class _R:
        def __init__(self, code, text="", js=None):
            self.status_code, self.text, self._js = code, text, js

        def json(self):
            return self._js

    class _S:
        def get(self, url, timeout=None):
            for key, resp in responses:
                if key in url:
                    return _R(*resp)
            raise AssertionError(f"unexpected url {url}")
    return _S()


def test_a_pass_reads_each_sub_page_and_skips_a_finished_league(monkeypatch):
    monkeypatch.setattr(dk, "PAUSE_S", 0)
    page = ('{"name":"Gone","displayGroupId":"6","eventGroupId":"999","path":"/leagues/tennis/gone"},'
            '{"name":"Live","displayGroupId":"6","eventGroupId":"111","path":"/leagues/tennis/live"}')
    totals = {"markets": [{"id": "M2", "eventId": "E1", "name": "Total Games", "subcategoryId": 16090}],
              "events": _board_with_pages()["events"],
              "selections": [{"id": "S3", "marketId": "M2", "label": "Over", "outcomeType": "Over",
                              "points": 21.5, "displayOdds": {"american": "\u2212110"}}]}
    s = _session([("sports/tennis", (200, page)), ("leagues/999", (404,)),
                  ("subcategories/16090", (200, "", totals)), ("leagues/111", (200, "", _board_with_pages()))])
    res = dk.one_pass(s, None, {}, None)
    assert res["leagues_gone"] == 1 and res["subpages_tried"] == 1 and res["subpages_gone"] == 0
    assert res["seen"] == 3 and "refused" not in res and "warning" not in res


def test_every_sub_page_missing_is_flagged_as_a_wrong_address(monkeypatch):
    monkeypatch.setattr(dk, "PAUSE_S", 0)
    page = '{"name":"Live","displayGroupId":"6","eventGroupId":"111","path":"/leagues/tennis/live"}'
    s = _session([("sports/tennis", (200, page)), ("subcategories/16090", (404,)),
                  ("leagues/111", (200, "", _board_with_pages()))])
    res = dk.one_pass(s, None, {}, None)
    assert res["subpages_gone"] == res["subpages_tried"] == 1 and "warning" in res


def test_a_refusal_ends_the_pass(monkeypatch):
    monkeypatch.setattr(dk, "PAUSE_S", 0)
    page = '{"name":"Live","displayGroupId":"6","eventGroupId":"111","path":"/leagues/tennis/live"}'
    s = _session([("sports/tennis", (200, page)), ("leagues/111", (403,))])
    assert "refused" in dk.one_pass(s, None, {}, None)


def test_a_second_copy_does_not_start(monkeypatch, capsys):
    monkeypatch.setattr(dk, "other_readers", lambda me: [4242])
    called = []
    monkeypatch.setattr(dk, "detach", lambda argv, log_dir: called.append(argv) or 0)
    assert dk.main(["--detach", "--no-store"]) == 0
    assert called == [] and "already_running" in capsys.readouterr().out


def test_detach_relaunches_without_the_flag(monkeypatch):
    monkeypatch.setattr(dk, "other_readers", lambda me: [])
    seen = []
    monkeypatch.setattr(dk, "detach", lambda argv, log_dir: seen.append(argv) or 0)
    assert dk.main(["--detach", "--out", "x", "--log-until", "2026-12-31T00:00:00"]) == 0
    assert seen == [["--out", "x", "--log-until", "2026-12-31T00:00:00"]]
