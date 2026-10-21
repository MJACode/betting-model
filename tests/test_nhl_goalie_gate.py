"""The NHL goalie gate and the poll that feeds it (mike, 2026-10-20: "We should
absolutely always know the goalie matchup before making a bet as well.").

What these pin:
  - ESPN's status survives the parse ('expected' / 'confirmed', and 'none' when
    a team is listed with no starter), and an unchanged slate costs no athlete
    fetch;
  - DailyFaceoff's page parses to our team ids (St Louis without the period),
    Confirmed / Likely / unconfirmed;
  - a designation is stored only when (name, status) changed;
  - a goalie row ESPN's confirmation contradicts is rewritten A -> B, a second
    run is a no-op, and A -> B -> A puts A back without a key clash;
  - the gate's reasons: expected, missing, no goalie row, a mismatched row,
    DailyFaceoff disagreeing, and the first-name alias step;
  - the one exemption, shots on goal (mike, 2026-10-20: "Ok on shots on
    goal"), is exactly that model, and every other NHL model is refused.

No network, no database: fixtures are cut from the samples in the 2026-10-20
investigation (goalie_work/df_today.html.json, the ESPN core event documents).
The guards at the INSERT sites are tests/test_nhl_goalie_guards.py.
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

import models.nhl_goalie_gate as gate
from data.ingestors import nhl_goalie_designations as des
from data.ingestors.espn_probables import fetch_espn_nhl_designations

NOW = datetime(2026, 10, 20, 19, 30, tzinfo=timezone.utc)      # 3:30pm ET
DAY = "2026-10-20"
SEA_DET = "NHL_2026-10-20_DET_SEA"
MTL_SJS = "NHL_2026-10-20_SJS_MTL"
STL_WPG = "NHL_2026-10-20_WPG_STL"


# ── ESPN ─────────────────────────────────────────────────────────────────────

LISTING = "https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events?dates=20261020&limit=50"


def _competitor(cid: str, side: str, athlete_id: int | None, status: str | None):
    c = {"$ref": f"http://espn/comp/{cid}", "id": cid, "homeAway": side,
         "team": {"$ref": f"http://espn/team/{cid}"}}
    if athlete_id is None:
        c["probables"] = []
    else:
        c["probables"] = [{
            "name": "probableStartingGoalie", "playerId": athlete_id,
            "athlete": {"$ref": f"http://espn/athlete/{athlete_id}"},
            "status": {"id": "102" if status == "confirmed" else "101",
                       "name": status.title(), "type": status},
        }]
    return c


def _espn_docs(sea_status="confirmed", mtl_athlete=4233889, sjs_athlete=None):
    """Two events as ESPN core serves them (shape measured 2026-10-20): the
    event carries each competitor's homeAway and probables inline."""
    return {
        LISTING: {"items": [{"$ref": "http://espn/event/1"}, {"$ref": "http://espn/event/2"}]},
        "https://espn/event/1": {"shortName": "DET @ SEA", "competitions": [{"competitors": [
            _competitor("25", "home", 3149633, sea_status),
            _competitor("5", "away", 4697382, "confirmed")]}]},
        "https://espn/event/2": {"shortName": "SJ @ MTL", "competitions": [{"competitors": [
            _competitor("10", "home", mtl_athlete, "confirmed"),
            _competitor("18", "away", sjs_athlete, "expected")]}]},
        "https://espn/athlete/3149633": {"displayName": "Philipp Grubauer", "id": "3149633"},
        "https://espn/athlete/4697382": {"displayName": "Daniil Tarasov", "id": "4697382"},
        "https://espn/athlete/4233889": {"displayName": "Jakub Dobeš", "id": "4233889"},
        "https://espn/athlete/77": {"displayName": "Sam Montembeault", "id": "77"},
    }


class _Fetch:
    def __init__(self, docs):
        self.docs, self.calls = docs, []

    def __call__(self, url):
        url = url.replace("http://", "https://")
        self.calls.append(url)
        if url not in self.docs:
            raise RuntimeError(f"unexpected fetch: {url}")
        return self.docs[url]


PAIRS = {("SEA", "DET"), ("MTL", "SJS")}


def test_espn_keeps_the_status_and_records_a_team_with_no_starter():
    f = _Fetch(_espn_docs())
    rows = {r["team"]: r for r in fetch_espn_nhl_designations(
        DAY, fetch=f, teams_ok=lambda h, a: (h, a) in PAIRS)}
    assert rows["SEA"]["designation"] == "confirmed"
    assert rows["SEA"]["player_name"] == "Philipp Grubauer"
    assert rows["MTL"]["player_name"] == "Jakub Dobeš"
    assert rows["SJS"]["designation"] == "none" and rows["SJS"]["player_name"] is None
    # the short name placed every competitor: no team document was fetched
    assert not any("/team/" in u for u in f.calls)


def test_an_unchanged_slate_costs_the_listing_and_one_call_a_game():
    f = _Fetch(_espn_docs())
    known = {"SEA": {"espn_athlete_id": "3149633", "designation": "confirmed",
                     "player_name": "Philipp Grubauer"},
             "DET": {"espn_athlete_id": "4697382", "designation": "confirmed",
                     "player_name": "Daniil Tarasov"},
             "MTL": {"espn_athlete_id": "4233889", "designation": "confirmed",
                     "player_name": "Jakub Dobeš"}}
    rows = fetch_espn_nhl_designations(DAY, fetch=f, known=known,
                                       teams_ok=lambda h, a: (h, a) in PAIRS)
    assert len(rows) == 4
    assert len(f.calls) == 3                     # listing + two event documents


def test_a_changed_status_fetches_the_athlete_again():
    f = _Fetch(_espn_docs())
    known = {"SEA": {"espn_athlete_id": "3149633", "designation": "expected",
                     "player_name": "Philipp Grubauer"}}
    fetch_espn_nhl_designations(DAY, fetch=f, known=known, teams_ok=lambda h, a: (h, a) in PAIRS)
    assert "https://espn/athlete/3149633" in f.calls


def test_a_started_game_is_skipped_after_its_event_document():
    f = _Fetch(_espn_docs())
    rows = fetch_espn_nhl_designations(DAY, fetch=f, teams_ok=lambda h, a: (h, a) in PAIRS,
                                       skip_game=lambda h, a: (h, a) == ("SEA", "DET"))
    assert {r["team"] for r in rows} == {"MTL", "SJS"}
    assert "https://espn/athlete/3149633" not in f.calls


def test_espn_fails_open():
    def boom(url):
        raise RuntimeError("blocked")
    assert fetch_espn_nhl_designations(DAY, fetch=boom) == []


# ── DailyFaceoff ─────────────────────────────────────────────────────────────

def _df_game(home, away, hg, ag, hs, ags, hsid=None, asid=None):
    """One game of DailyFaceoff's pageProps.data, the fields the parser reads."""
    return {"homeTeamName": home, "awayTeamName": away,
            "homeGoalieName": hg, "awayGoalieName": ag,
            "homeGoalieId": 1 if hg else None, "awayGoalieId": 2 if ag else None,
            "homeNewsStrengthName": hs, "awayNewsStrengthName": ags,
            "homeNewsStrengthId": hsid, "awayNewsStrengthId": asid}


DF_PROPS = {"date": DAY, "data": [
    # 2026-10-20 as served: confirmed both ends; Likely; St Louis without the period
    _df_game("Seattle Kraken", "Detroit Red Wings", "Philipp Grubauer", "Daniil Tarasov",
             "Confirmed", "Confirmed", 2, 2),
    _df_game("Montreal Canadiens", "San Jose Sharks", "Jakub Dobes", "Alex Nedeljkovic",
             "Confirmed", "Likely", 2, 3),
    _df_game("St Louis Blues", "Winnipeg Jets", "Joel Hofer", "Stuart Skinner",
             None, None),                                  # tomorrow's shape: no status yet
]}


def _df_html(props) -> str:
    blob = json.dumps({"props": {"pageProps": props}})
    return (f'<html><head></head><body><script id="__NEXT_DATA__" type="application/json">'
            f'{blob}</script></body></html>')


def test_dailyfaceoff_page_parses_to_our_teams_and_statuses():
    rows = {r["team"]: r for r in des.parse_dailyfaceoff(des.parse_dailyfaceoff_page(_df_html(DF_PROPS)))}
    assert rows["SEA"]["status"] == "confirmed" and rows["SEA"]["player_name"] == "Philipp Grubauer"
    assert rows["SJS"]["status"] == "likely"
    assert rows["STL"]["status"] == "unconfirmed"          # "St Louis Blues", no period
    assert rows["WPG"]["player_name"] == "Stuart Skinner"


def test_a_page_with_no_data_blob_is_an_error_not_an_empty_slate():
    with pytest.raises(ValueError):
        des.parse_dailyfaceoff_page("<html>Just a moment...</html>")   # a Cloudflare challenge


def test_dailyfaceoff_fails_open_with_one_warning():
    def blocked(url):
        raise RuntimeError("403 Forbidden")
    assert des.fetch_dailyfaceoff(DAY, fetch_html=blocked) is None
    assert des.fetch_dailyfaceoff(DAY, fetch_html=lambda url: "<html></html>") is None


# ── change detection ─────────────────────────────────────────────────────────

def _obs(gid, team, source, name, status):
    return {"game_id": gid, "team": team, "source": source, "player_name": name,
            "status": status, "source_player_id": None}


def test_only_a_changed_name_or_status_is_stored():
    latest = {(SEA_DET, "SEA", "espn"): {"player_name": "Philipp Grubauer", "status": "expected"},
              (SEA_DET, "DET", "espn"): {"player_name": "Daniil Tarasov", "status": "confirmed"},
              (MTL_SJS, "MTL", "espn"): {"player_name": "Sam Montembeault", "status": "expected"}}
    observed = [_obs(SEA_DET, "SEA", "espn", "Philipp Grubauer", "confirmed"),   # status changed
                _obs(SEA_DET, "DET", "espn", "Daniil Tarasov", "confirmed"),     # unchanged
                _obs(MTL_SJS, "MTL", "espn", "Jakub Dobes", "confirmed"),        # goalie changed
                _obs(MTL_SJS, "MTL", "dailyfaceoff", "Jakub Dobes", "confirmed")]  # first sighting
    new = des.changes(latest, observed)
    assert [(r["team"], r["source"], r["status"]) for r in new] == [
        ("SEA", "espn", "confirmed"), ("MTL", "espn", "confirmed"), ("MTL", "dailyfaceoff", "confirmed")]
    assert des.changes({**latest, **{(r["game_id"], r["team"], r["source"]): r for r in new}},
                       observed) == []


# ── the A -> B rewrite, through run() on a fake database ─────────────────────

class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class FakeDB:
    """The four tables the poll touches, answering the poll's own SQL."""

    def __init__(self, games, stats):
        self.games = games                      # list of dicts
        self.stats = stats                      # nhl_goalie_stats rows
        self.designations: list[dict] = []
        self.commits = 0
        self._clock = 0

    def _stamp(self):
        self._clock += 1
        return f"2026-10-20 1{self._clock % 10}:00:00+00"

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        if q.startswith("SELECT game_id, home_team, away_team, commence_time FROM games"):
            return _Rows([(g["game_id"], g["home"], g["away"], g["commence"])
                          for g in self.games if g["date"] == params[0]])
        if q.startswith("SELECT home_team, away_team FROM games"):
            return _Rows([(g["home"], g["away"]) for g in self.games if g["date"] == params[0]])
        if "FROM nhl_goalie_designations" in q:
            ids = set(params[0])
            latest = {}
            for r in sorted(self.designations, key=lambda r: r["observed_at"]):
                if r["game_id"] in ids:
                    latest[(r["game_id"], r["team"], r["source"])] = r
            return _Rows([(r["game_id"], r["team"], r["source"], r["player_id"], r["player_name"],
                           r["status"], r["source_player_id"], r["observed_at"], r["designation_id"])
                          for r in latest.values()])
        if q.startswith("UPDATE nhl_goalie_designations SET last_seen_at"):
            for r in self.designations:
                if r["designation_id"] in params[1]:
                    r["last_seen_at"] = params[0]
            return _Rows([])
        if q.startswith("SELECT game_id, team, player_id, player_name FROM nhl_goalie_stats"):
            ids = set(params[0])
            rows = sorted((r for r in self.stats if r["game_id"] in ids),
                          key=lambda r: r["created_at"], reverse=True)
            return _Rows([(r["game_id"], r["team"], r["player_id"], r["player_name"]) for r in rows])
        if q.startswith("DELETE FROM nhl_goalie_stats WHERE game_id"):
            self.stats = [r for r in self.stats if not (r["game_id"], r["team"]) == tuple(params)]
            return _Rows([])
        raise AssertionError(f"unexpected SQL: {q[:120]}")

    def executemany(self, sql, rows):
        q = " ".join(sql.split())
        if q.startswith("INSERT INTO nhl_goalie_designations"):
            for r in rows:
                self.designations.append({**r, "designation_id": len(self.designations) + 1})
        elif q.startswith("DELETE FROM nhl_goalie_stats WHERE team"):
            for r in rows:
                self.stats = [s for s in self.stats if not (s["team"] == r["team"] and
                              s["game_date"] == r["game_date"] and s["player_id"] is None)]
        elif q.startswith("INSERT INTO nhl_goalie_stats"):
            for r in rows:
                clash = [s for s in self.stats
                         if s["player_id"] == r["player_id"] and s["game_date"] == r["game_date"]]
                if clash:
                    raise AssertionError("ON CONFLICT(player_id, game_date): the old row was not removed")
                self.stats.append({**r, "created_at": self._stamp()})
        else:
            raise AssertionError(f"unexpected executemany: {q[:120]}")

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


@pytest.fixture
def resolver(monkeypatch):
    """Names -> NHL ids without the NHL API or the log (the real ones are
    nhl_stats_ingestor.resolve_goalie_id / goalie_row, tested there)."""
    ids = {"Philipp Grubauer": "8475831", "Joey Daccord": "8478916", "Daniil Tarasov": "8480193",
           "Jakub Dobeš": "8482593", "Jakub Dobes": "8482593", "Sam Montembeault": "8478470"}
    monkeypatch.setattr(des._Resolver, "_load", lambda self: None)
    monkeypatch.setattr(des._Resolver, "player_id", lambda self, name: ids.get(name))
    monkeypatch.setattr(des._Resolver, "row", lambda self, team, name, pid, gid: {
        "player_name": name, "player_id": pid, "team": team, "season": 2027,
        "game_date": DAY, "game_id": gid, "save_pct": 0.905})


def _db():
    games = [{"game_id": SEA_DET, "home": "SEA", "away": "DET", "date": DAY,
              "commence": "2026-10-21T01:40:00Z"},
             {"game_id": MTL_SJS, "home": "MTL", "away": "SJS", "date": DAY,
              "commence": "2026-10-20T23:00:00Z"}]
    stats = [{"game_id": SEA_DET, "team": "SEA", "player_id": "8478916", "player_name": "Joey Daccord",
              "game_date": DAY, "created_at": "2026-10-20 10:06:00+00"},
             {"game_id": SEA_DET, "team": "DET", "player_id": "8480193", "player_name": "Daniil Tarasov",
              "game_date": DAY, "created_at": "2026-10-20 10:06:00+00"},
             {"game_id": MTL_SJS, "team": "MTL", "player_id": "8478470", "player_name": "Sam Montembeault",
              "game_date": DAY, "created_at": "2026-10-20 10:06:00+00"}]
    return FakeDB(games, stats)


def _run(db, docs, now=NOW):
    return des.run([DAY], now=now, conn=db, espn_fetch=_Fetch(docs),
                   df_fetch=lambda url: _df_html(DF_PROPS))


def test_a_confirmed_goalie_replaces_the_6am_row_and_a_second_run_is_a_no_op(resolver):
    db = _db()
    out = _run(db, _espn_docs())
    assert sorted(out["swapped"]) == [f"{SEA_DET} SEA -> Philipp Grubauer", f"{MTL_SJS} MTL -> Jakub Dobeš"]
    sea = [r for r in db.stats if r["game_id"] == SEA_DET and r["team"] == "SEA"]
    assert [(r["player_name"], r["player_id"]) for r in sea] == [("Philipp Grubauer", "8475831")]
    n = len(db.designations)
    again = _run(db, _espn_docs())
    assert again["swapped"] == [] and again["stored"] == 0 and len(db.designations) == n


def test_a_back_and_forth_puts_the_first_goalie_back_without_a_key_clash(resolver):
    db = _db()
    _run(db, _espn_docs())                                       # Daccord -> Grubauer
    docs = _espn_docs()
    docs["https://espn/event/1"]["competitions"][0]["competitors"][0]["probables"][0].update(
        playerId=99, athlete={"$ref": "http://espn/athlete/99"})
    docs["https://espn/athlete/99"] = {"displayName": "Joey Daccord", "id": "99"}
    out = _run(db, docs)                                         # Grubauer -> Daccord
    assert f"{SEA_DET} SEA -> Joey Daccord" in out["swapped"]
    sea = [r for r in db.stats if r["game_id"] == SEA_DET and r["team"] == "SEA"]
    assert [r["player_name"] for r in sea] == ["Joey Daccord"]


def test_an_expected_goalie_never_rewrites_the_row(resolver):
    db = _db()
    out = _run(db, _espn_docs(sea_status="expected"))
    assert f"{SEA_DET} SEA -> Philipp Grubauer" not in out["swapped"]
    assert any(r["player_name"] == "Joey Daccord" for r in db.stats)


def test_a_started_or_past_game_is_never_touched(resolver):
    db = _db()
    after_both = datetime(2026, 10, 21, 2, 0, tzinfo=timezone.utc)
    out = _run(db, _espn_docs(), now=after_both)
    assert out["games"] == 0 and out["stored"] == 0 and out["swapped"] == []
    assert db.designations == []


def test_a_tomorrow_game_is_recorded_but_its_row_is_never_created(resolver):
    db = _db()
    db.games = [{**g, "date": "2026-10-21", "commence": "2026-10-21T23:00:00Z"} for g in db.games]
    db.stats = []
    out = des.run(["2026-10-21"], now=NOW, conn=db,
                  espn_fetch=_Fetch({**_espn_docs(), LISTING.replace("20261020", "20261021"):
                                     _espn_docs()[LISTING]}),
                  df_fetch=lambda url: _df_html(DF_PROPS))
    assert out["stored"] > 0 and out["swapped"] == [] and db.stats == []


# ── the gate's reasons ───────────────────────────────────────────────────────

T0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)


def _latest(**over):
    base = {
        (SEA_DET, "SEA", "espn"): {"player_id": "8475831", "player_name": "Philipp Grubauer",
                                   "status": "confirmed", "observed_at": T0},
        (SEA_DET, "DET", "espn"): {"player_id": "8480193", "player_name": "Daniil Tarasov",
                                   "status": "confirmed", "observed_at": T0 + timedelta(hours=2)},
    }
    for key, row in over.items():
        team, source = key.split("_")
        if row is None:
            base.pop((SEA_DET, team, source), None)
        else:
            base[(SEA_DET, team, source)] = {**base.get((SEA_DET, team, source), {}), **row}
    return base


STATS = {(SEA_DET, "SEA"): {"player_id": "8475831", "player_name": "Philipp Grubauer",
                            "created_at": "2026-10-20 16:00:00+00"},
         (SEA_DET, "DET"): {"player_id": "8480193", "player_name": "Daniil Tarasov",
                            "created_at": "2026-10-20 10:06:00+00"}}


def test_known_when_both_are_confirmed_and_the_rows_agree():
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(), STATS)
    assert m.reason is None
    assert m.known_at == T0 + timedelta(hours=2)            # the later of the stamps
    assert m.starters["SEA"] == ("8475831", "Philipp Grubauer")


@pytest.mark.parametrize("over, why", [
    ({"SEA_espn": {"status": "expected"}}, "SEA expected"),
    ({"DET_espn": None}, "DET no starter listed"),
    ({"DET_espn": {"status": "none", "player_name": None}}, "DET no starter listed"),
    ({"SEA_dailyfaceoff": {"player_name": "Joey Daccord", "status": "likely"}},
     "SEA DailyFaceoff names Joey Daccord, ESPN confirmed Philipp Grubauer"),
])
def test_why_a_game_is_not_known(over, why):
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(**over), STATS)
    assert m.reason == f"waiting for both confirmed starting goalies ({why})"
    assert m.known_at is None


def test_a_goalie_row_that_names_someone_else_is_not_known():
    stats = {**STATS, (SEA_DET, "SEA"): {"player_id": "8478916", "player_name": "Joey Daccord",
                                         "created_at": "2026-10-20 10:06:00+00"}}
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(), stats)
    assert "SEA goalie row names Joey Daccord, ESPN confirmed Philipp Grubauer" in m.reason
    no_row = {k: v for k, v in STATS.items() if k[1] != "DET"}
    assert "DET no goalie row yet" in gate.assess(SEA_DET, "SEA", "DET", _latest(), no_row).reason


def test_dailyfaceoff_agreeing_under_another_spelling_is_agreement():
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(
        SEA_dailyfaceoff={"player_name": "Phil Grubauer", "status": "confirmed"},
        DET_dailyfaceoff={"player_name": "Daniil Tarasov", "status": "likely"}), STATS)
    assert m.reason is None


@pytest.mark.parametrize("a, b, same", [
    ("Jakub Dobeš", "Jakub Dobes", True),                   # accents
    ("Matt Murray", "Matthew Murray", True),                # the alias step
    ("Dan Vladar", "Daniel Vladar", True),
    ("Sam Montembeault", "Samuel Montembeault", True),
    ("Ukko-Pekka Luukkonen", "Ukko Pekka Luukkonen", True),
    ("Matt Murray", "Mike Murray", False),                  # same last name, another man
    ("Joey Daccord", "Philipp Grubauer", False),
    ("", "", False),
])
def test_names(a, b, same):
    assert gate.same_goalie_name(a, b) is same


def test_ids_decide_when_both_sides_have_one():
    assert gate.same_goalie("8475831", "P. Grubauer", "8475831", "Philipp Grubauer")
    assert not gate.same_goalie("8475831", "Philipp Grubauer", "8478916", "Philipp Grubauer")


class _GateConn:
    """Answers the gate's three reads; `fail` makes every read raise."""

    def __init__(self, games, latest, stats, fail=False):
        self.games, self.latest, self.stats, self.fail = games, latest, stats, fail
        self.reads = 0

    def execute(self, sql, params=None):
        q = " ".join(sql.split())
        if q.startswith(("SAVEPOINT", "RELEASE", "ROLLBACK TO")):
            return _Rows([])
        self.reads += 1
        if self.fail:
            raise RuntimeError("relation nhl_goalie_designations does not exist")
        if "FROM games" in q:
            return _Rows(self.games)
        if "FROM nhl_goalie_designations" in q:
            # seen_at: when a poll last read the row (default: just now, so a
            # test about something else is not aged out by the wall clock).
            return _Rows([(g, t, s, r["player_id"], r["player_name"], r["status"], r["observed_at"],
                           r.get("seen_at") or datetime.now(timezone.utc))
                          for (g, t, s), r in self.latest.items()])
        if "FROM nhl_goalie_stats" in q:
            return _Rows([(g, t, r["player_id"], r["player_name"], r["created_at"])
                          for (g, t), r in self.stats.items()])
        raise AssertionError(q)


def test_the_gate_reads_and_fails_closed():
    conn = _GateConn([(SEA_DET, "SEA", "DET")], _latest(), STATS)
    assert gate.matchup_reasons(conn, [SEA_DET]) == {SEA_DET: None}
    broken = _GateConn([], {}, {}, fail=True)
    assert gate.matchup_reasons(broken, [SEA_DET]) == {SEA_DET: gate.CHECK_FAILED}
    assert gate.matchup_reasons(conn, ["NHL_2026-10-20_X_Y"])["NHL_2026-10-20_X_Y"].endswith(
        "(game not found)")


def test_refuse_unknown_drops_or_downgrades_and_leaves_other_sports_unread():
    conn = _GateConn([(SEA_DET, "SEA", "DET")], _latest(SEA_espn={"status": "expected"}), STATS)
    nhl = {"game_id": SEA_DET, "sport": "NHL", "signal_type": "BET", "model_id": "nhl_over_under",
           "pick_label": "SEA vs DET Under 6.0", "kelly_fraction": 0.02, "recommended_bet": 20.0}
    mlb = {"game_id": "MLB_x", "sport": "MLB", "signal_type": "BET", "model_id": "mlb_over_under"}
    assert gate.refuse_unknown(conn, [nhl, mlb], mode="drop", label="t") == [mlb]
    none = gate.refuse_unknown(conn, [copy.deepcopy(nhl)], mode="none", label="t")[0]
    assert none["signal_type"] == "NONE" and none["recommended_bet"] == 0.0
    assert none["downgrade_reason"] == "waiting for both confirmed starting goalies (SEA expected)"
    quiet = _GateConn([], {}, {})
    assert gate.refuse_unknown(quiet, [mlb], mode="drop", label="t") == [mlb] and quiet.reads == 0


# ── the one exemption: shots on goal (mike, 2026-10-20) ──────────────────────

ROOT = Path(__file__).resolve().parent.parent
SOG = "nhl_prop_shots_on_goal"


def test_the_exemption_is_exactly_shots_on_goal_and_says_who_asked():
    """Adding a model here takes a new instruction, and the comment above the
    constant has to say whose. mike, 2026-10-20: "Ok on shots on goal"."""
    import config
    assert config.NHL_GOALIE_GATE_EXEMPT == frozenset({SOG})
    lines = (ROOT / "config.py").read_text(encoding="utf-8").splitlines()
    at = [i for i, line in enumerate(lines) if line.startswith("NHL_GOALIE_GATE_EXEMPT")]
    assert len(at) == 1, "one definition of NHL_GOALIE_GATE_EXEMPT"
    comment = []
    for line in reversed(lines[:at[0]]):
        if not line.startswith("#"):
            break
        comment.append(line)
    text = " ".join(comment)
    assert "mike" in text and "2026-10-20" in text and "Ok on shots on goal" in text, text


def _row(model_id, game_id=SEA_DET):
    return {"game_id": game_id, "sport": "NHL", "signal_type": "BET", "model_id": model_id,
            "pick_label": f"{model_id} pick", "kelly_fraction": 0.02, "recommended_bet": 20.0}


@pytest.mark.parametrize("model_id", [
    "nhl_moneyline", "nhl_moneyline_regulation", "nhl_over_under", "nhl_puckline",
    "nhl_prop_blocked_shots", "nhl_prop_saves", "nhl_prop_assists",
    "nhl_prop_points",          # no such model yet: a new NHL model is gated by default
])
def test_every_nhl_model_but_shots_on_goal_is_refused_on_an_unknown_game(model_id):
    conn = _GateConn([(SEA_DET, "SEA", "DET")], _latest(SEA_espn={"status": "expected"}), STATS)
    assert gate.refuse_unknown(conn, [_row(model_id)], mode="drop", label="t") == []
    none = gate.refuse_unknown(conn, [_row(model_id)], mode="none", label="t")[0]
    assert none["signal_type"] == "NONE" and none["recommended_bet"] == 0.0


def test_a_shots_on_goal_bet_passes_an_unknown_game_without_a_read():
    conn = _GateConn([(SEA_DET, "SEA", "DET")], _latest(SEA_espn={"status": "expected"}), STATS)
    sog = _row(SOG)
    assert gate.refuse_unknown(conn, [sog], mode="drop", label="t") == [sog] and conn.reads == 0
    saves = _row("nhl_prop_saves")
    assert gate.refuse_unknown(conn, [saves, sog], mode="drop", label="t") == [sog]
    assert gate.is_exempt(SOG) and not gate.is_exempt("nhl_prop_saves") and not gate.is_exempt(None)


# ── review fixes, 2026-10-21 ─────────────────────────────────────────────────
#
# Three ways a stored confirmation could stand when it should not: a goalie
# row with no NHL id (the moneyline then reads the team's previous starter), a
# confirmation no poll has re-read (ESPN blocking the worker stores nothing),
# and a new ESPN starter whose name could not be read (the team was skipped,
# so the old confirmation stayed the latest row).

def test_a_goalie_row_with_no_nhl_id_is_not_known():
    """NYI 2026-10-06 (Varlamov): the row's id was NULL. Names agree, so the
    old check called the game known and the moneyline filled the id from the
    team's last starter (models/nhl_moneyline_anchored._goalie_frame)."""
    latest = _latest(SEA_espn={"player_id": None})
    stats = {**STATS, (SEA_DET, "SEA"): {"player_id": None, "player_name": "Philipp Grubauer",
                                         "created_at": "2026-10-20 16:00:00+00"}}
    m = gate.assess(SEA_DET, "SEA", "DET", latest, stats)
    assert m.reason == ("waiting for both confirmed starting goalies "
                        "(SEA goalie row for Philipp Grubauer has no NHL id)")
    empty = {**STATS, (SEA_DET, "SEA"): {**stats[(SEA_DET, "SEA")], "player_id": ""}}
    assert "has no NHL id" in gate.assess(SEA_DET, "SEA", "DET", latest, empty).reason


def test_a_confirmation_no_poll_has_read_lately_is_not_known():
    import config
    limit = timedelta(minutes=config.NHL_GOALIE_READ_MAX_AGE_MIN)
    read_at = T0 + timedelta(hours=2)                       # DET's confirmation is the later one
    fresh = _latest(SEA_espn={"seen_at": read_at}, DET_espn={"seen_at": read_at})
    assert gate.assess(SEA_DET, "SEA", "DET", fresh, STATS, now=read_at + limit).reason is None
    late = read_at + limit + timedelta(minutes=1)
    m = gate.assess(SEA_DET, "SEA", "DET", fresh, STATS, now=late)
    assert m.reason == ("waiting for both confirmed starting goalies "
                        "(DET ESPN not read since 17:00Z; SEA ESPN not read since 17:00Z)")
    # A row never re-read counts from when it was stored.
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(), STATS, now=T0 + limit + timedelta(minutes=1))
    assert "SEA ESPN not read since 15:00Z" in m.reason


def test_a_dailyfaceoff_name_too_old_to_be_read_no_longer_vetoes():
    import config
    limit = timedelta(minutes=config.NHL_GOALIE_READ_MAX_AGE_MIN)
    now = T0 + timedelta(hours=3)
    disagree = {"player_name": "Joey Daccord", "status": "likely"}
    rows = _latest(SEA_espn={"seen_at": now}, DET_espn={"seen_at": now},
                   SEA_dailyfaceoff={**disagree, "observed_at": T0, "seen_at": now})
    assert "DailyFaceoff names Joey Daccord" in gate.assess(
        SEA_DET, "SEA", "DET", rows, STATS, now=now).reason
    old = _latest(SEA_espn={"seen_at": now}, DET_espn={"seen_at": now},
                  SEA_dailyfaceoff={**disagree, "observed_at": T0, "seen_at": now - limit * 2})
    assert gate.assess(SEA_DET, "SEA", "DET", old, STATS, now=now).reason is None


def test_the_gate_reads_when_each_row_was_last_seen():
    import config
    seen = T0 + timedelta(hours=4)
    latest = _latest(SEA_espn={"seen_at": seen}, DET_espn={"seen_at": seen})
    conn = _GateConn([(SEA_DET, "SEA", "DET")], latest, STATS)
    at = seen + timedelta(minutes=config.NHL_GOALIE_READ_MAX_AGE_MIN)
    assert gate.matchup_states(conn, [SEA_DET], now=at)[SEA_DET].reason is None
    later = at + timedelta(minutes=1)
    assert "ESPN not read since" in gate.matchup_states(conn, [SEA_DET], now=later)[SEA_DET].reason


def test_a_new_espn_starter_whose_name_cannot_be_read_closes_the_gate():
    """ESPN switches SEA to a new athlete and his document times out. The team
    used to be skipped, so the stored confirmation of the old goalie stayed the
    latest row and the gate kept calling the game known."""
    docs = _espn_docs()
    docs["https://espn/event/1"]["competitions"][0]["competitors"][0]["probables"][0].update(
        playerId=55, athlete={"$ref": "http://espn/athlete/55"})          # no document for 55
    known = {"SEA": {"espn_athlete_id": "3149633", "designation": "confirmed",
                     "player_name": "Philipp Grubauer"}}
    rows = {r["team"]: r for r in fetch_espn_nhl_designations(
        DAY, fetch=_Fetch(docs), known=known, teams_ok=lambda h, a: (h, a) in PAIRS)}
    assert rows["SEA"]["designation"] == gate.UNREAD and rows["SEA"]["player_name"] is None
    assert rows["SEA"]["espn_athlete_id"] == "55"
    m = gate.assess(SEA_DET, "SEA", "DET", _latest(
        SEA_espn={"player_id": None, "player_name": None, "status": gate.UNREAD}), STATS)
    assert "SEA ESPN named a starter whose name could not be read" in m.reason


def test_the_same_starter_keeps_his_name_when_only_his_status_changed():
    """A status change re-reads the athlete document; if that read fails, the
    same athlete id still names him."""
    docs = _espn_docs()
    del docs["https://espn/athlete/3149633"]
    known = {"SEA": {"espn_athlete_id": "3149633", "designation": "expected",
                     "player_name": "Philipp Grubauer"}}
    rows = {r["team"]: r for r in fetch_espn_nhl_designations(
        DAY, fetch=_Fetch(docs), known=known, teams_ok=lambda h, a: (h, a) in PAIRS)}
    assert (rows["SEA"]["player_name"], rows["SEA"]["designation"]) == ("Philipp Grubauer", "confirmed")


def test_a_poll_that_cannot_read_espn_fails_and_stores_what_dailyfaceoff_said(resolver):
    db = _db()

    def blocked(url):
        raise RuntimeError("403 Forbidden")
    with pytest.raises(RuntimeError, match="ESPN"):
        des.run([DAY], now=NOW, conn=db, espn_fetch=blocked, df_fetch=lambda url: _df_html(DF_PROPS))
    assert db.designations and {r["source"] for r in db.designations} == {"dailyfaceoff"}
    assert db.commits == 1


def test_an_espn_listing_with_none_of_our_games_fails_the_poll(resolver):
    db = _db()
    docs = _espn_docs()
    docs[LISTING] = {"items": []}
    with pytest.raises(RuntimeError, match="ESPN"):
        _run(db, docs)


def test_the_step_reports_a_failed_poll(monkeypatch):
    import run_pipeline

    def boom(**kw):
        raise RuntimeError("ESPN not read for 2026-10-20")
    monkeypatch.setattr(des, "run", boom)
    assert run_pipeline.step_nhl_goalie_designations(today_only=True) is False


def test_each_poll_marks_the_rows_it_read_as_still_standing(resolver):
    db = _db()
    _run(db, _espn_docs())
    first = {(r["game_id"], r["team"], r["source"]): r for r in db.designations}
    assert all(r["last_seen_at"] == NOW for r in first.values())
    later = NOW + timedelta(minutes=5)
    out = _run(db, _espn_docs(), now=later)
    assert out["stored"] == 0
    assert all(r["last_seen_at"] == later for r in db.designations)
    assert all(r["observed_at"] == NOW for r in db.designations)     # history is not moved
    # A game ESPN did not answer for keeps its old read time and ages out.
    docs = _espn_docs()
    del docs["https://espn/event/2"]
    _run(db, docs, now=later + timedelta(minutes=5))
    mtl = [r for r in db.designations if r["game_id"] == MTL_SJS and r["source"] == "espn"]
    assert mtl and all(r["last_seen_at"] == later for r in mtl)


def test_a_tomorrow_game_row_that_exists_is_never_rewritten(resolver):
    """Rewrites are for today's games only, even when a tomorrow row exists
    and ESPN has already confirmed someone else for it."""
    db = _db()
    db.games = [{**g, "date": "2026-10-21", "commence": "2026-10-21T23:00:00Z"} for g in db.games]
    db.stats = [{**r, "game_date": "2026-10-21"} for r in db.stats]
    before = [dict(r) for r in db.stats]
    out = des.run(["2026-10-21"], now=NOW, conn=db,
                  espn_fetch=_Fetch({**_espn_docs(), LISTING.replace("20261020", "20261021"):
                                     _espn_docs()[LISTING]}),
                  df_fetch=lambda url: _df_html(DF_PROPS))
    assert out["stored"] > 0 and out["swapped"] == []
    assert db.stats == before
