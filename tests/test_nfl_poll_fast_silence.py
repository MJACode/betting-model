"""
The fast NFL poll went silent on 2026-10-11 (mike: "nfl_poll_fast has gone
silent"). Its heartbeat stopped at 12:12Z with the Sunday slate still to play.

The cause, from the worker log and pg_stat_activity: the opener appends the
whole odds board to the day's board CSV every minute (~560 rows a minute), and
every wind tick re-copied the WHOLE file into nfl_odds_history, two round trips
per row in one transaction. Each run took longer than the last (18, 27, 48, 71,
105, 151, 232 minutes that day), and the job allows one run at a time, so the
run that started at 12:20Z held the fast poll for ~5.7 hours.

Two guards, one per half of the failure:
  * the board flush sends only rows added since the last flush, looks each
    matchup up once, and stops starting batches at its time budget;
  * every step of an NFL poll tick has a timeout, so no single step can hold
    the poll past its cadence again.
"""

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

FIELDS = ["snapshot_at", "commence_time", "home", "away", "bookmaker",
          "market", "point", "price_home", "price_away"]
GAME = ("NFL_2026_06_BUF_LV", 2026, 6)


def _append_board(path: Path, rows: list[dict]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        if new:
            w.writeheader()
        for r in rows:
            w.writerow(r)


def _row(i: int, home: str = "LV", away: str = "BUF") -> dict:
    return {"snapshot_at": f"2026-10-11T12:{i:02d}:00+00:00",
            "commence_time": "2026-10-11T20:05:00+00:00",
            "home": home, "away": away, "bookmaker": "pinnacle",
            "market": "totals", "point": "47.5",
            "price_home": "-105", "price_away": "-115"}


class FakeConn:
    """Records lookups and batch inserts; knows one game, LV vs BUF."""

    def __init__(self, log):
        self.log = log

    def execute(self, sql, params=None):
        self.log.setdefault("selects", []).append(params)

        class R:
            def fetchone(_self):
                return GAME if tuple(params or ()) == ("LV", "BUF") else None
        return R()

    def executemany(self, sql, params_list):
        assert "ON CONFLICT (snapshot_at, game_id, bookmaker, market) DO NOTHING" in sql
        self.log.setdefault("batches", []).append(list(params_list))

    def commit(self):
        self.log["commits"] = self.log.get("commits", 0) + 1

    def close(self):
        pass


def _setup(monkeypatch, tmp_path):
    import data.db as db
    from scripts import nfl_wind_publisher as pub
    log: dict = {}
    monkeypatch.setattr(db, "get_connection", lambda: FakeConn(log))
    monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
    return pub, log, tmp_path / "board_2026-10-11.csv"


def _sent(log) -> int:
    return sum(len(b) for b in log.get("batches", []))


def test_board_flush_sends_only_rows_added_since_the_last_flush(monkeypatch, tmp_path):
    pub, log, path = _setup(monkeypatch, tmp_path)
    _append_board(path, [_row(i) for i in range(3)])
    assert pub.publish_board("2026-10-11") == 3
    assert _sent(log) == 3

    _append_board(path, [_row(i) for i in range(3, 5)])
    log.clear()
    assert pub.publish_board("2026-10-11") == 2
    assert _sent(log) == 2, "the whole day was re-sent: the 2026-10-11 silence"
    assert path.with_suffix(".flushed").read_text(encoding="utf-8") == "5"


def test_board_flush_looks_each_matchup_up_once(monkeypatch, tmp_path):
    pub, log, path = _setup(monkeypatch, tmp_path)
    _append_board(path, [_row(i) for i in range(6)]
                  + [_row(i, home="KC", away="DEN") for i in range(6)])
    pub.publish_board("2026-10-11")
    assert len(log["selects"]) == 2, "one lookup per quote, not per matchup"


def test_board_flush_stops_at_its_budget_and_resumes_from_the_marker(monkeypatch, tmp_path):
    pub, log, path = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(pub, "BOARD_CHUNK", 2)
    monkeypatch.setattr(pub, "BOARD_FLUSH_BUDGET_S", -1)  # already over budget
    _append_board(path, [_row(i) for i in range(5)])

    assert pub.publish_board("2026-10-11") == 2          # one batch, then stop
    assert path.with_suffix(".flushed").read_text(encoding="utf-8") == "2"
    assert pub.publish_board("2026-10-11") == 2
    assert pub.publish_board("2026-10-11") == 1
    assert pub.publish_board("2026-10-11") == 0          # nothing left
    assert _sent(log) == 5 and log["commits"] == 3


def test_rows_for_an_unpublished_game_are_skipped_once_not_every_tick(monkeypatch, tmp_path):
    pub, log, path = _setup(monkeypatch, tmp_path)
    _append_board(path, [_row(0), _row(1, home="NYJ", away="MIA")])
    assert pub.publish_board("2026-10-11") == 1
    assert path.with_suffix(".flushed").read_text(encoding="utf-8") == "2"


def test_a_half_written_last_row_waits_for_the_next_tick(monkeypatch, tmp_path):
    pub, log, path = _setup(monkeypatch, tmp_path)
    _append_board(path, [_row(0), _row(1)])
    full = ",".join(_row(2)[k] for k in FIELDS)
    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(full[:20])                       # the opener, mid-append

    assert pub.publish_board("2026-10-11") == 2
    assert path.with_suffix(".flushed").read_text(encoding="utf-8") == "2"

    with path.open("a", encoding="utf-8", newline="") as fh:
        fh.write(full[20:] + "\r\n")
    log.clear()
    assert pub.publish_board("2026-10-11") == 1
    assert log["batches"][0][0]["snapshot_at"] == _row(2)["snapshot_at"]


def test_a_poll_step_that_hangs_is_killed_at_its_timeout():
    import scheduler
    t0 = time.monotonic()
    scheduler._run([sys.executable, "-c", "import time; time.sleep(60)"],
                   "hang-test", timeout=2)
    assert time.monotonic() - t0 < 30


def test_a_killed_step_fails_the_run_loudly_after_publishing(monkeypatch):
    """The timeouts must not trade the silence alarm for nothing: a run that
    had to kill a step raises, so its heartbeat records "error"."""
    import pytest
    import scheduler
    published = []
    monkeypatch.setattr(scheduler, "_nfl_lead_hours", lambda: 1.0)
    monkeypatch.setattr(scheduler, "run_nfl_wind_card",
                        lambda *a, **k: ["nfl-wind-publish"])
    monkeypatch.setattr(scheduler, "_run", lambda *a, **k: "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", published.append)
    with pytest.raises(RuntimeError, match="nfl-wind-publish"):
        scheduler.run_nfl_poll(fast=True)
    assert published == ["nfl-poll"], "a pick that did get written must still go out"


def test_the_alerter_reports_a_watched_job_whose_last_run_failed():
    from tracking import failure_alerter as fa

    class Conn:
        def execute(self, sql, params=()):
            self.sql = sql
            return self

        def fetchall(self):
            if "job_heartbeats" not in self.sql:
                return []
            now = "2999-01-01T00:00:00+00:00"   # fresh: this is not about silence
            if "last_status" in self.sql:
                return [("nfl_poll_fast", "error",
                         "RuntimeError('NFL poll step(s) killed at 180s: nfl-wind-publish')")]
            return [("nfl_poll_fast", now)]

    got = fa._conditions(Conn())
    assert "jobfail:nfl_poll_fast" in got
    assert "nfl-wind-publish" in got["jobfail:nfl_poll_fast"][2]


def _body(src: str, name: str) -> str:
    rest = src[src.index(f"def {name}("):]
    end = rest.find("\ndef ", 1)
    return rest if end < 0 else rest[:end]


def test_every_step_of_an_nfl_poll_tick_is_bounded():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    poll = _body(src, "run_nfl_poll")
    card = _body(src, "run_nfl_wind_card")
    for body, name in ((poll, "run_nfl_poll"), (card, "run_nfl_wind_card")):
        calls = [c for c in body.split("_run(")[1:]]
        assert calls, name
        for c in calls:
            assert "timeout=" in c.split(")\n", 1)[0], (
                f"a step in {name} has no timeout: one stuck step skips every "
                "tick after it (max_instances=1)")
    assert "run_nfl_wind_card(" in poll
    assert "timeout=" in poll.split("run_nfl_wind_card(", 1)[1].split("\n", 1)[0]
