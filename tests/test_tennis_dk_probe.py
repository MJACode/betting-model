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
