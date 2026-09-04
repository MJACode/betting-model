"""
The ModelCalibration judgement pass, as a worker cron.

The rules are all DELTAS, and that is the property most worth pinning. Measured
against production 2026-09-03 before this shipped: 13 of the 22 models in the
2026-09-02 sweep carry a standing "RE-CUT to ..." verdict. A rule that reported
every RE-CUT would post thirteen identical findings every Monday forever, which
is the same trap the pipeline watch's silent-kind rule fell into.
"""
from datetime import date

import pytest

import config
from tracking import calibration_watch as cw


def _row(model_id, verdict="NO CUT", cur_n=10, settled=500, **kw):
    row = {"model_id": model_id, "paused": False, "settled": settled,
           "cur_n": cur_n, "cur_roi": 1.0, "best_prob": 0.58, "best_edge": 0.10,
           "best_n": 30, "best_roi": 9.0, "best_per_week": 5.0,
           "half_a": 8.0, "half_b": 7.0, "verdict": verdict}
    row.update(kw)
    return row


class TestVerdictChanges:
    def test_a_standing_verdict_is_not_news(self):
        """The whole reason every rule is a delta."""
        same = {"m": _row("m", verdict="RE-CUT to 0.58/0.10 (12.5% / 1.4% by half)")}
        assert cw.verdict_changes(same, {"m": dict(same["m"])}) == []

    def test_thirteen_standing_re_cuts_produce_nothing(self):
        """The exact production shape this was calibrated against."""
        sweep = {f"m{i}": _row(f"m{i}", verdict=f"RE-CUT to 0.5{i}/0.10") for i in range(13)}
        assert cw.verdict_changes(sweep, {k: dict(v) for k, v in sweep.items()}) == []

    def test_a_changed_verdict_is_reported_with_both_sides(self):
        prev = {"m": _row("m", verdict="NO CUT — nothing profitable")}
        cur = {"m": _row("m", verdict="RE-CUT to 0.58/0.10")}
        out = cw.verdict_changes(cur, prev)
        assert len(out) == 1
        assert "NO CUT" in out[0] and "RE-CUT" in out[0]

    def test_a_re_cut_carries_the_exact_edit_and_says_a_person_decides(self):
        prev = {"m": _row("m", verdict="NO CUT")}
        cur = {"m": _row("m", verdict="RE-CUT to 0.58/0.10", best_prob=0.58,
                         best_edge=0.10)}
        line = cw.verdict_changes(cur, prev)[0]
        assert "ACTION_THRESHOLDS['m']" in line
        assert "0.58" in line and "0.1" in line
        assert "a person decides" in line and "Updated-By" in line

    def test_it_never_emits_an_edit_for_a_non_re_cut(self):
        prev = {"m": _row("m", verdict="RE-CUT to 0.58/0.10")}
        cur = {"m": _row("m", verdict="PEAK, NOT A PLATEAU — watch, do not ship.")}
        line = cw.verdict_changes(cur, prev)[0]
        assert "ACTION_THRESHOLDS" not in line

    def test_an_arrival_is_not_a_verdict_change(self):
        """roster_changes owns arrivals; reporting both would double-count."""
        assert cw.verdict_changes({"m": _row("m")}, {}) == []


class TestDormantLiveModels:
    def test_a_live_model_with_no_bets_is_flagged(self):
        out = cw.dormant_live_models({"m": _row("m", cur_n=0, settled=5661)},
                                     paused_now=set())
        assert len(out) == 1
        assert "5661 settled" in out[0]
        assert "broken-feed" in out[0], "must not assert dormancy over a broken feed"

    def test_pausing_a_model_silences_it_immediately(self):
        """
        Reads CURRENT config, not the sweep's stored `paused` snapshot. That
        column reflects what the sweep saw on its run_date, so a snapshot-based
        rule would keep firing for a model paused today until next Monday --
        which is exactly what happened with mlb_prop_batter_hits, paused
        2026-09-03 against a 2026-09-02 sweep row saying paused=false.
        """
        stale_snapshot = {"m": _row("m", cur_n=0, paused=False)}
        assert cw.dormant_live_models(stale_snapshot, paused_now={"m"}) == []

    def test_a_model_that_is_betting_is_not_dormant(self):
        assert cw.dormant_live_models({"m": _row("m", cur_n=7)}, paused_now=set()) == []

    def test_the_live_config_is_the_default(self):
        """Guards against the default silently becoming the stored snapshot."""
        paused = next(iter(config.PAUSED_MODELS))
        assert cw.dormant_live_models({paused: _row(paused, cur_n=0)}) == []


class TestRosterChanges:
    def test_a_model_dropping_out_is_reported(self):
        out = cw.roster_changes({}, {"m": _row("m")})
        assert len(out) == 1 and "DROPPED OUT" in out[0]

    def test_a_model_entering_is_reported_with_its_verdict(self):
        out = cw.roster_changes({"m": _row("m", verdict="NO CUT — nothing")}, {})
        assert len(out) == 1 and "NO CUT" in out[0]

    def test_a_stable_roster_is_silent(self):
        s = {"m": _row("m")}
        assert cw.roster_changes(s, {k: dict(v) for k, v in s.items()}) == []


class TestVolumeShifts:
    def test_a_large_proportional_move_on_a_real_count_is_reported(self):
        out = cw.volume_shifts({"m": _row("m", cur_n=169)},
                               {"m": _row("m", cur_n=20)})
        assert len(out) == 1 and "20 → 169" in out[0]

    def test_a_tiny_count_doubling_is_noise(self):
        """2 -> 4 doubles and means nothing."""
        assert cw.volume_shifts({"m": _row("m", cur_n=4)},
                                {"m": _row("m", cur_n=2)}) == []

    def test_a_small_absolute_move_on_a_big_count_is_noise(self):
        assert cw.volume_shifts({"m": _row("m", cur_n=171)},
                                {"m": _row("m", cur_n=169)}) == []

    def test_falling_to_zero_from_a_real_count_is_reported(self):
        out = cw.volume_shifts({"m": _row("m", cur_n=0)},
                               {"m": _row("m", cur_n=43)})
        assert len(out) == 1 and "43 → 0" in out[0]


class _Conn:
    def __init__(self, dates=(), sweeps=None, auto_pauses=None):
        self.dates, self.sweeps = dates, sweeps or {}
        self.auto_pauses, self.committed = auto_pauses, False
        self.inserts = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if "to_regclass" in s:
            return _Res([(self.auto_pauses,)])
        if "DISTINCT run_date" in s:
            return _Res([(d,) for d in self.dates])
        if "FROM model_calibration_sweeps WHERE run_date" in s:
            rows = self.sweeps.get(params[0], [])
            return _Res([tuple(r[c] for c in
                               ("model_id", "paused", "settled", "cur_n", "cur_roi",
                                "best_prob", "best_edge", "best_n", "best_roi",
                                "best_per_week", "half_a", "half_b", "verdict"))
                         for r in rows])
        if "INSERT INTO push_sent" in s:
            self.inserts.append(params)
            return _Res([])
        return _Res([])

    def commit(self):
        self.committed = True

    def rollback(self):
        pass


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class TestTheRun:
    def test_a_first_sweep_reports_no_baseline_rather_than_everything_changed(
            self, monkeypatch):
        """
        Production had exactly ONE run_date when this shipped. Without this the
        first run would report all 22 models as brand new.
        """
        posted = {}
        monkeypatch.setattr(cw, "_announce", lambda s: posted.update(s) or True)
        conn = _Conn(dates=("2026-09-02",),
                     sweeps={"2026-09-02": [_row("m", cur_n=5)]},
                     auto_pauses="model_auto_pauses")
        out = cw.run_calibration_watch(conn, today=date(2026, 9, 7))
        assert out["baseline"] is None
        assert out["findings"] == []

    def test_an_empty_sweep_table_says_the_sweep_never_completed(self, monkeypatch):
        monkeypatch.setattr(cw, "_announce", lambda s: True)
        out = cw.run_calibration_watch(_Conn(dates=()), today=date(2026, 9, 7))
        assert out["status"] == "no_sweep"
        assert "never completed" in out["findings"][0]

    def test_the_missing_auto_pauses_table_is_named_not_skipped(self, monkeypatch):
        monkeypatch.setattr(cw, "_announce", lambda s: True)
        conn = _Conn(dates=("2026-09-02",),
                     sweeps={"2026-09-02": [_row("m", cur_n=5)]},
                     auto_pauses=None)
        out = cw.run_calibration_watch(conn, today=date(2026, 9, 7))
        assert any("model_auto_pauses" in f for f in out["findings"])

    def test_it_is_ledgered_only_after_the_post_confirms(self, monkeypatch):
        monkeypatch.setattr(cw, "_announce", lambda s: True)
        conn = _Conn(dates=("2026-09-02",),
                     sweeps={"2026-09-02": [_row("m", cur_n=5)]},
                     auto_pauses="x")
        cw.run_calibration_watch(conn, today=date(2026, 9, 7))
        assert conn.inserts, "a confirmed post must be ledgered"
        assert conn.inserts[0][1] == "calibration_watch"
        assert conn.committed

    def test_a_failed_post_is_never_ledgered(self, monkeypatch):
        """§7: a kind with zero push_sent rows must mean it has NEVER succeeded."""
        monkeypatch.setattr(cw, "_announce", lambda s: False)
        conn = _Conn(dates=("2026-09-02",),
                     sweeps={"2026-09-02": [_row("m", cur_n=5)]},
                     auto_pauses="x")
        out = cw.run_calibration_watch(conn, today=date(2026, 9, 7))
        assert out["posted"] is False
        assert conn.inserts == [], "an unconfirmed post must not be ledgered"

    def test_the_kill_switch_stops_it(self, monkeypatch):
        monkeypatch.setenv("RUN_CALIBRATION_WATCH", "0")
        assert cw.run_calibration_watch(_Conn())["status"] == "disabled"


class TestItNeverDecides:
    def test_the_module_contains_no_write_to_config_or_thresholds(self):
        import io
        from pathlib import Path
        src = io.open(Path(cw.__file__), encoding="utf-8").read()
        for forbidden in ("ACTION_THRESHOLDS[", "PAUSED_MODELS.add",
                          "PAUSED_MODELS.remove", "UPDATE model_registry"):
            assert forbidden not in src.replace(
                "ACTION_THRESHOLDS['{row['model_id']}']", ""), forbidden

    def test_every_post_carries_the_in_sample_caveat(self, monkeypatch):
        """A description reads as a forecast without it."""
        sent = {}
        monkeypatch.setattr("tracking.discord_notifier._post",
                            lambda url, payload: sent.update(payload) or "id1")
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_OPS", "https://example/x")
        cw._announce({"status": "ok", "run_date": "2026-09-02", "baseline": None,
                      "models": 22, "findings": []})
        assert "IN-SAMPLE" in sent["embeds"][0]["description"]
        assert "13-48pp" in sent["embeds"][0]["description"]
