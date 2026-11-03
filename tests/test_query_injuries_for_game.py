"""query_injuries_for_game uses one pull.

The injuries table stores a full copy of a team's list on every ingest, under
one report_date. Summing that day counts a player once per snapshot. The
reader keeps the newest pull that existed at tip-off, and only the players
on it. A name an earlier pull the same day listed, and this pull left off,
does not count.
"""
from features.feature_engine import _blk_injuries, _compute_injury_adjustment
from data.ingestors.injury_ingestor import (
    latest_injury_rows,
    query_injuries_for_game,
)


def _row(player_id, created_at, weight=0.7, injury_id=1, name="P", **kw):
    base = {
        "player_name": name,
        "player_id": player_id,
        "status": "Out",
        "injury_type": "lower body",
        "scenario": "A",
        "severity_weight": weight,
        "return_ramp_factor": None,
        "games_since_return": None,
        "activation_date": None,
        "created_at": created_at,
        "injury_id": injury_id,
    }
    base.update(kw)
    return base


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Conn:
    """Hands back scripted results in the order the reader asks for them."""

    def __init__(self, script):
        self.script = list(script)
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((" ".join(sql.split()), params))
        if not self.script:
            raise AssertionError(f"unexpected SQL: {sql}")
        return _Result(self.script.pop(0))


OTT_MORNING = "2026-10-13 04:17:18.147923+00"
OTT_AFTERNOON = "2026-10-13 17:17:19.625406+00"
OTT_EVENING = "2026-10-13 22:10:26.970649+00"
OTT_AFTER_TIP = "2026-10-13 23:50:19.279922+00"
TIP = "2026-10-13T23:30:00Z"


def test_three_snapshots_of_one_player_count_once():
    rows = [
        _row("1", OTT_MORNING, weight=0.7, injury_id=1, name="Hughes"),
        _row("1", OTT_AFTERNOON, weight=0.7, injury_id=2, name="Hughes"),
        _row("1", OTT_EVENING, weight=0.7, injury_id=3, name="Hughes"),
    ]
    kept = latest_injury_rows(rows, as_of=TIP)
    assert len(kept) == 1
    assert kept[0]["injury_id"] == 3
    assert _compute_injury_adjustment(rows) == 2.1
    assert _compute_injury_adjustment(kept) == 0.7


def test_a_snapshot_after_tip_is_not_the_latest():
    rows = [
        _row("1", OTT_MORNING, weight=0.5, injury_id=1),
        _row("1", OTT_EVENING, weight=0.7, injury_id=2),
        _row("1", OTT_AFTER_TIP, weight=1.0, injury_id=3),
    ]
    kept = latest_injury_rows(rows, as_of=TIP)
    assert [r["injury_id"] for r in kept] == [2]
    assert _compute_injury_adjustment(kept) == 0.7


def test_a_player_who_only_appears_after_tip_is_left_out():
    rows = [
        _row("1", OTT_EVENING, injury_id=1, name="Hughes"),
        _row("2", OTT_AFTER_TIP, injury_id=2, name="Johnston"),
    ]
    kept = latest_injury_rows(rows, as_of=TIP)
    assert [r["player_id"] for r in kept] == ["1"]


def test_a_player_missing_from_the_newest_pre_tip_pull_does_not_count():
    """Harrison Scott is on the morning and 17:17 pulls and off the 22:10
    pull. Ottawa at 22:23Z is the four names still on 22:10, 2.8, not 3.5."""
    players = {
        "hughes": "Cameron Hughes",
        "scott": "Harrison Scott",
        "kiviranta": "Joel Kiviranta",
        "krys": "Luke Krys",
        "duchene": "Matt Duchene",
    }
    rows = []
    iid = 1
    present = {
        OTT_MORNING: ("hughes", "scott", "krys", "duchene"),
        OTT_AFTERNOON: ("hughes", "scott", "kiviranta", "krys", "duchene"),
        OTT_EVENING: ("hughes", "kiviranta", "krys", "duchene"),
    }
    for stamp, keys in present.items():
        for key in keys:
            rows.append(_row(key, stamp, injury_id=iid, name=players[key]))
            iid += 1
    assert _compute_injury_adjustment(rows) == 9.1
    kept = latest_injury_rows(rows, as_of="2026-10-13T22:23:00Z")
    assert _compute_injury_adjustment(kept) == 2.8
    assert sorted(r["player_id"] for r in kept) == [
        "duchene", "hughes", "kiviranta", "krys",
    ]


def test_same_clock_keeps_the_later_insert():
    rows = [
        _row("1", OTT_EVENING, weight=0.5, injury_id=10, scenario="A"),
        _row("1", OTT_EVENING, weight=0.3, injury_id=11, scenario="B",
             return_ramp_factor=0.7),
    ]
    kept = latest_injury_rows(rows)
    assert kept[0]["injury_id"] == 11
    assert _compute_injury_adjustment(kept) == 0.3


def test_nameless_rows_on_the_newest_pull_stay_separate():
    rows = [
        _row(None, OTT_MORNING, injury_id=1, name=""),
        _row(None, OTT_EVENING, injury_id=2, name=""),
        _row(None, OTT_EVENING, injury_id=3, name=""),
    ]
    kept = latest_injury_rows(rows, as_of=TIP)
    assert sorted(r["injury_id"] for r in kept) == [2, 3]


def test_query_returns_one_row_per_player_as_of_tip():
    home = [
        tuple(_row("1", OTT_MORNING, weight=0.5, injury_id=1, name="Hughes")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("1", OTT_EVENING, weight=0.7, injury_id=2, name="Hughes")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("1", OTT_AFTER_TIP, weight=1.0, injury_id=3, name="Hughes")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("2", OTT_MORNING, injury_id=4, name="Duchene")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("2", OTT_EVENING, injury_id=5, name="Duchene")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("scott", OTT_MORNING, injury_id=6, name="Harrison Scott")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
        tuple(_row("scott", OTT_AFTERNOON, injury_id=7, name="Harrison Scott")[c]
              for c in (
                  "player_name", "player_id", "status", "injury_type",
                  "scenario", "severity_weight", "return_ramp_factor",
                  "games_since_return", "activation_date", "created_at", "injury_id")),
    ]
    conn = _Conn([
        [(TIP,)],                       # games.commence_time
        [("2026-10-13",)],              # MAX(report_date)
        [(OTT_MORNING,)],               # earliest snapshot that day, before tip
        [(OTT_MORNING,), (OTT_EVENING,), (OTT_AFTER_TIP,)],
        home,
        [],
    ])
    out = query_injuries_for_game(
        conn, "NHL", "OTT", "STL", "2026-10-13", game_id="NHL_2026-10-13_STL_OTT")
    assert _compute_injury_adjustment(out["home_injuries"]) == 1.4
    assert sorted(r["injury_id"] for r in out["home_injuries"]) == [2, 5]
    assert "scott" not in {r["player_id"] for r in out["home_injuries"]}
    assert out["away_injuries"] == []
    assert "timestamptz" not in conn.sql[0][0]
    joined = "\n".join(sql for sql, _ in conn.sql)
    assert "timestamptz" not in joined


def test_a_report_taken_entirely_after_tip_falls_back_a_day():
    conn = _Conn([
        [("2026-10-13",)],
        [("2026-10-13 23:50:19+00",)],   # earliest copy that day is after tip
        [("2026-10-12",)],
        [("2026-10-12 04:17:18+00",)],
        [("2026-10-12 22:00:00+00",)],
        [tuple(_row("1", "2026-10-12 22:00:00+00", injury_id=9, name="Hughes")[c]
               for c in (
                   "player_name", "player_id", "status", "injury_type",
                   "scenario", "severity_weight", "return_ramp_factor",
                   "games_since_return", "activation_date", "created_at", "injury_id"))],
        [],
    ])
    out = query_injuries_for_game(
        conn, "NHL", "OTT", "STL", "2026-10-13", as_of=TIP)
    assert [r["injury_id"] for r in out["home_injuries"]] == [9]
    assert conn.script == []


def test_bulk_reader_uses_the_newest_pre_tip_pull_for_every_team():
    bulk = {
        "injuries": {
            "OTT": {"2026-10-13": [
                _row("1", OTT_MORNING, injury_id=1, name="Hughes"),
                _row("1", OTT_EVENING, injury_id=2, name="Hughes"),
                _row("scott", OTT_MORNING, injury_id=5, name="Harrison Scott"),
                _row("1", OTT_AFTER_TIP, injury_id=3, name="Hughes"),
                _row("2", OTT_AFTER_TIP, injury_id=4, name="Johnston"),
            ]},
            "STL": {"2026-10-13": [
                _row("9", OTT_MORNING, injury_id=8, name="Neighbour"),
                _row("9", OTT_EVENING, injury_id=9, name="Neighbour"),
            ]},
        },
        "inj_dates": {"OTT": ["2026-10-13"], "STL": ["2026-10-13"]},
    }
    home = _blk_injuries(bulk, "OTT", "2026-10-13", as_of=TIP)
    assert [r["injury_id"] for r in home] == [2]
    assert [r["injury_id"] for r in _blk_injuries(bulk, "STL", "2026-10-13", as_of=TIP)] == [9]


def test_bulk_reader_drops_a_team_missing_from_the_newest_pre_tip_pull():
    """Scott's shape, across teams: an earlier pull the same day does not
    fill in a team the newest pre-tip pull left off. A post-tip-only name
    is off too, and yesterday's list stays yesterday's."""
    bulk = {
        "injuries": {
            "OTT": {
                "2026-10-12": [_row("2", "2026-10-12 12:00:00+00", injury_id=1, name="Johnston")],
                "2026-10-13": [
                    _row("scott", OTT_MORNING, injury_id=5, name="Harrison Scott"),
                    _row("2", OTT_AFTER_TIP, injury_id=2, name="Johnston"),
                ],
            },
            "BOS": {
                "2026-10-13": [_row("3", OTT_EVENING, injury_id=3, name="Morning")],
            },
        },
    }
    assert _blk_injuries(bulk, "OTT", "2026-10-13", as_of=TIP) == []
    assert [r["injury_id"] for r in _blk_injuries(bulk, "BOS", "2026-10-13", as_of=TIP)] == [3]
