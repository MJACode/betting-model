"""The NFL game rules write a NONE row for every game they evaluate.

Matt, 2026-09-26, looking at a 14-game Sunday that showed 7 cards: "There are
only 7 bets showing under NFL. All bet lines should be showing on the today
tab." The app was not dropping anything -- `nfl_wind_totals` and
`nfl_opener_spread` only ever wrote BET rows, so the rest of the slate never
reached `picks`. `scripts/nfl_wind_publisher.publish_scored` writes the model's
view of every other game as a NONE row.

The properties pinned here are the ones that would cost a real bet if broken:

  * a NONE row never LOCKS a game -- the BET that fires later still lands;
  * a BET that lands clears the game's NONE row, never the other way round;
  * a NONE row never carries a fabricated price, and never sits beside a BET;
  * the pick monitor never flags a NONE row as a locked pick.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import nfl_wind_publisher as pub  # noqa: E402
from tracking.pick_integrity import pick_problems  # noqa: E402

NFL_ROOT = ROOT / "nfl"

_spec = importlib.util.spec_from_file_location(
    "nfl_opener_spread_model_scored", NFL_ROOT / "models" / "opener_spread.py")
opener_model = importlib.util.module_from_spec(_spec)
sys.path.insert(0, str(NFL_ROOT))
try:
    _spec.loader.exec_module(opener_model)
finally:
    sys.path.remove(str(NFL_ROOT))


@pytest.fixture(scope="module")
def wind():
    sys.path.insert(0, str(NFL_ROOT))
    try:
        from _nfl_models import load_nfl_model
        yield load_nfl_model("wind_totals")
    finally:
        sys.path.remove(str(NFL_ROOT))


GAME = "NFL_2026_03_CIN_PIT"
GAMES = {GAME: {"home_team": "PIT", "away_team": "CIN", "game_date": "2026-09-27",
                "commence_time": "2026-09-27T17:00:00+00:00"}}


def _eval(model_id="nfl_wind_totals", **kw):
    row = {"game_id": GAME, "model_id": model_id,
           "observed_at": "2026-09-26T13:00:00+00:00", "qualifies": "0",
           "reason": "forecast wind 6.2 mph below the 11 mph threshold",
           "current_line": "42.5", "current_price": "-110",
           "current_book": "draftkings", "model_prob": "", "edge": ""}
    row.update(kw)
    return row


# ── the model boards carry a quote on every priced row ─────────────────────

class TestEvalRowsCarryTheLine:
    def test_wind_below_threshold_still_carries_the_under_quote(self, wind):
        g = pd.DataFrame([{
            "game_id": "2026_03_CIN_PIT", "kick_utc": "2026-09-27T17:00:00+00:00",
            "stadium_id": "PIT00", "roof": "outdoors", "lead_days": 1.2,
            "forecast_wind": 6.2, "best_book": "fanduel", "best_total": 42.5,
            "best_under_px": -105, "best_over_px": -115,
        }])
        (row,) = wind.evaluate_board(g)
        assert row["qualifies"] == "0"
        assert "below the 11 mph threshold" in row["reason"]
        assert (row["current_line"], row["current_price"], row["current_book"]) == (
            42.5, -105, "fanduel")

    def test_wind_unquoted_game_carries_no_line(self, wind):
        g = pd.DataFrame([{
            "game_id": "2026_03_CIN_PIT", "kick_utc": "2026-09-27T17:00:00+00:00",
            "stadium_id": "PIT00", "roof": "outdoors", "lead_days": 1.2,
            "forecast_wind": 6.2, "best_book": None, "best_total": float("nan"),
            "best_under_px": float("nan"), "best_over_px": float("nan"),
        }])
        (row,) = wind.evaluate_board(g)
        assert row["current_line"] == "" and row["current_price"] == ""

    def test_opener_waiting_on_pinnacle_carries_the_dk_home_spread(self):
        sched = pd.DataFrame([{
            "game_id": "2026_03_CIN_PIT", "home_team": "PIT", "away_team": "CIN",
            "matchup": "CIN @ PIT", "kick_utc": "2026-09-27 17:00:00+00:00",
            "lead_days": 1.2}])
        frame = pd.DataFrame([
            {"event_id": "e", "home": "PIT", "away": "CIN", "book": b,
             "market": "spreads", "side": s, "price": px, "point": pt}
            for b, s, px, pt in [("fanduel", "home", -108, -3.0),
                                 ("fanduel", "away", -112, 3.0),
                                 ("draftkings", "home", -110, -2.5),
                                 ("draftkings", "away", -110, 2.5)]])
        (row,) = opener_model.evaluate_board(frame, sched)
        assert row["reason"].startswith("waiting on Pinnacle")
        assert (row["current_line"], row["current_price"], row["current_book"]) == (
            -2.5, -110, "draftkings")


# ── the pure transform ──────────────────────────────────────────────────────

class TestBuildScoredRows:
    def test_wind_without_an_opinion_is_the_market_at_zero_edge(self):
        (p,) = pub.build_scored_rows({(GAME, "nfl_wind_totals"): _eval()}, GAMES, 1000.0)
        assert p["signal_type"] == "NONE"
        assert p["pick_side"] == "under" and p["scored_line"] == 42.5
        assert p["dk_odds"] == -110.0
        assert p["model_probability"] == p["dk_implied_prob"] == 0.5238
        assert p["edge"] == 0.0 and p["kelly_fraction"] == 0.0
        assert p["recommended_bet"] == 0.0
        assert p["pick_label"] == "CIN @ PIT Under 42.5 (no bet, DK)"
        assert p["downgrade_reason"].startswith("forecast wind 6.2 mph")

    def test_wind_with_an_opinion_keeps_the_models_numbers(self):
        r = _eval(model_prob="0.5671", edge="0.0149",
                  reason="wind 12.0 mph but edge +1.49pp below 3pp")
        (p,) = pub.build_scored_rows({(GAME, "nfl_wind_totals"): r}, GAMES, 1000.0)
        assert p["model_probability"] == 0.5671 and p["edge"] == 0.0149
        # The card's edge is against its de-vigged market; the row says so.
        assert p["dk_implied_prob"] == pytest.approx(0.5522)

    def test_opener_is_the_home_side_at_the_home_number(self):
        r = _eval("nfl_opener_spread", current_line="-3.0", current_price="-108",
                  current_book="fanduel",
                  reason="deviation +0.50 below the 2.0 pt threshold")
        (p,) = pub.build_scored_rows({(GAME, "nfl_opener_spread"): r}, GAMES, 1000.0)
        assert p["pick_side"] == "home" and p["scored_line"] == -3.0
        assert p["pick_label"] == "CIN @ PIT — PIT -3 (no bet, FD)"
        assert p["edge"] == 0.0

    @pytest.mark.parametrize("model_id", ["nfl_wind_totals", "nfl_opener_spread"])
    def test_label_names_the_quote_book_the_way_the_app_reads_it(self, model_id):
        # mobile/src/lib/markets.ts storedQuoteBook: /\(([^()]*?),\s*([A-Za-z]{2,5})\)/
        # A bare "(FD)" misses it and the app calls a FanDuel price DraftKings.
        import re
        r = _eval(model_id, current_book="fanduel", current_line="-3.0")
        (p,) = pub.build_scored_rows({(GAME, model_id): r}, GAMES, 1000.0)
        m = re.search(r"\(([^()]*?),\s*([A-Za-z]{2,5})\)", p["pick_label"])
        assert m and m.group(2) == "FD"

    @pytest.mark.parametrize("model_id,line,side", [
        ("nfl_wind_totals", "42.5", "under"),
        ("nfl_opener_spread", "-3.0", "home"),
        ("nfl_opener_spread", "6.5", "home"),
    ])
    def test_label_agrees_with_the_fields(self, model_id, line, side):
        # QUOTE A PICK FROM ITS LABEL (CLAUDE.md §00): the words and the
        # numbers must pass the same check a published BET does.
        r = _eval(model_id, current_line=line)
        (p,) = pub.build_scored_rows({(GAME, model_id): r}, GAMES, 1000.0)
        assert p["pick_side"] == side
        assert pick_problems(p["pick_label"], p["pick_side"], p["scored_line"],
                             model_id, home="PIT", away="CIN") == []

    @pytest.mark.parametrize("over", [
        {"current_price": ""}, {"current_line": ""}, {"current_price": "0"},
    ])
    def test_no_quote_no_row(self, over):
        # profit_flat fabricates -110 for a NULL price (CLAUDE.md §6).
        assert pub.build_scored_rows(
            {(GAME, "nfl_wind_totals"): _eval(**over)}, GAMES, 1000.0) == []

    def test_unknown_game_is_skipped(self):
        assert pub.build_scored_rows(
            {(GAME, "nfl_wind_totals"): _eval()}, {}, 1000.0) == []

    def test_latest_observation_wins(self):
        old = _eval(observed_at="2026-09-26T12:00:00+00:00", current_line="44.0")
        new = _eval(observed_at="2026-09-26T13:00:00+00:00", current_line="42.5")
        other = _eval(model_id="nfl_prop_market")
        latest = pub.latest_eval_rows([new, old, other])
        assert list(latest) == [(GAME, "nfl_wind_totals")]
        assert latest[(GAME, "nfl_wind_totals")]["current_line"] == "42.5"


# ── the database half, against a recording connection ──────────────────────

class _Conn:
    """Records every statement; answers the reads publish_scored makes."""

    def __init__(self, games=(), picks=()):
        self.games, self.picks, self.sql = list(games), list(picks), []

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sql.append((flat, params))
        rows = []
        if flat.startswith("SELECT game_id, home_team"):
            rows = self.games
        elif flat.startswith("SELECT pick_id, game_id, model_id, signal_type"):
            rows = self.picks

        class R:
            def fetchall(self_r):
                return rows

            def fetchone(self_r):
                return rows[0] if rows else None
        return R()

    def commit(self):
        self.sql.append(("COMMIT", None))

    def close(self):
        pass

    def writes(self, verb):
        return [s for s, _ in self.sql if s.startswith(verb)]


def _kick(hours):
    return (datetime.now(timezone.utc) + timedelta(hours=hours)).isoformat()


def _dump(tmp_path, rows, date="2026-09-26"):
    with open(tmp_path / f"pick_eval_{date}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


@pytest.fixture
def run(monkeypatch, tmp_path):
    import data.db as db

    def _run(conn, rows):
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        _dump(tmp_path, rows)
        return pub.publish_scored("2026-09-26")
    return _run


class TestPublishScored:
    def test_writes_a_none_row_for_an_unstarted_game(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))])
        assert run(conn, [_eval()]) == 1
        (ins,) = [(s, p) for s, p in conn.sql if s.startswith("INSERT INTO picks")]
        assert ins[1]["signal_type"] == "NONE"

    def test_never_beside_a_bet(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[(1, GAME, "nfl_wind_totals", "BET", "x", "under",
                             0.57, 0.51, 0.06, -105, 42.5, None)])
        assert run(conn, [_eval()]) == 0
        assert not conn.writes("INSERT") and not conn.writes("UPDATE")

    def test_started_game_is_frozen(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(-1))])
        assert run(conn, [_eval()]) == 0
        assert not conn.writes("INSERT") and not conn.writes("UPDATE")

    def test_unchanged_row_is_not_rewritten(self, run):
        (p,) = pub.build_scored_rows({(GAME, "nfl_wind_totals"): _eval()}, GAMES, 1000.0)
        existing = (7, GAME, "nfl_wind_totals", "NONE") + tuple(
            p[k] for k in pub._SCORED_FIELDS)
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[existing])
        assert run(conn, [_eval()]) == 0
        assert not conn.writes("UPDATE") and not conn.writes("INSERT")

    def test_moved_line_refreshes_the_none_row_only(self, run):
        (p,) = pub.build_scored_rows({(GAME, "nfl_wind_totals"): _eval()}, GAMES, 1000.0)
        existing = (7, GAME, "nfl_wind_totals", "NONE") + tuple(
            p[k] for k in pub._SCORED_FIELDS)
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[existing])
        assert run(conn, [_eval(current_line="41.5")]) == 1
        (upd,) = [(s, prm) for s, prm in conn.sql if s.startswith("UPDATE picks")]
        assert "signal_type = 'NONE' AND result IS NULL" in upd[0]
        assert upd[1]["pick_id"] == 7 and upd[1]["scored_line"] == 41.5


# ── a NONE row never locks a game, and a BET clears it ──────────────────────

class _LockConn(_Conn):
    """A picks table holding one NONE row for the game, and nothing else."""

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sql.append((flat, params))
        none_only = "signal_type = 'BET'" not in flat
        if flat.startswith("SELECT DISTINCT game_id FROM picks"):
            rows = [(GAME,)] if none_only else []
        elif flat.startswith("SELECT 1 FROM picks"):
            rows = [(1,)] if none_only else []
        else:
            rows = []

        class R:
            def fetchall(self_r):
                return rows

            def fetchone(self_r):
                return rows[0] if rows else None
        return R()


def _write_card(path, row):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(row))
        w.writeheader()
        w.writerow(row)


class TestNoneRowNeverLocks:
    def test_wind_bet_lands_over_a_none_row_and_clears_it(self, monkeypatch, tmp_path):
        import data.db as db
        conn = _LockConn()
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        monkeypatch.setattr(pub, "_flush_snapshots_safe", lambda d: None)
        monkeypatch.setattr(pub, "_flush_board_safe", lambda d: None)
        _write_card(tmp_path / "wind_card_2026-09-26.csv", {
            "game_id": "2026_03_CIN_PIT", "matchup": "CIN @ PIT",
            "kick_utc": "2026-09-27 17:00:00+00:00", "stadium_id": "PIT00",
            "lead_days": "1.2", "forecast_wind": "14.0", "exp_true_wind": "12.0",
            "total_line": "42.5", "book": "fanduel", "price": "-105",
            "model_prob": "0.5700", "market_prob": "0.5000", "edge": "0.0700",
            "stake_pct": "1.05", "ev_pct": "11.3"})
        assert pub.publish("2026-09-26") == 1
        order = [s.split(" ")[0] + " " + s.split(" ")[2] for s, _ in conn.sql
                 if s.startswith(("DELETE", "INSERT INTO picks"))]
        assert order == ["DELETE picks", "INSERT picks"]
        (delete,) = conn.writes("DELETE")
        assert "signal_type = 'NONE' AND result IS NULL" in delete

    def test_opener_bet_lands_over_a_none_row_and_clears_it(self, monkeypatch, tmp_path):
        import data.db as db
        conn = _LockConn()
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        monkeypatch.setattr(pub, "_flush_snapshots_safe", lambda d: None)
        _write_card(tmp_path / "opener_card_2026-09-26.csv", {
            "game_id": "2026_03_CIN_PIT", "matchup": "CIN @ PIT",
            "kick_utc": "2026-09-27 17:00:00+00:00", "lead_days": "4.2",
            "side": "away", "bet_team": "CIN", "book": "betmgm", "price": "-105",
            "side_line": "5.0", "soft_home_line": "-5.0", "pin_home_line": "-2.5",
            "dev": "-2.5", "model_prob": "0.5900", "market_prob": "0.5122",
            "edge": "0.0778", "stake_pct": "2.0"})
        assert pub.publish_opener("2026-09-26") == 1
        assert conn.writes("DELETE") and conn.writes("INSERT INTO picks")


def test_pick_monitor_reads_locked_bets_only():
    src = (ROOT / "scripts" / "nfl_pick_monitor.py").read_text(encoding="utf-8")
    select = src.split("SELECT p.pick_id, p.game_id, p.model_id", 1)[1].split('"""', 1)[0]
    assert "p.signal_type = 'BET'" in select


def test_scheduler_runs_the_scored_step_on_the_nfl_poll():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    body = src.split("def run_nfl_poll", 1)[1].split("\ndef ", 1)[0]
    assert '"scripts.nfl_wind_publisher", "--scored"' in body
