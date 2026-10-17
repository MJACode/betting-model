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

Reviewer's post-merge findings on #838 add: a row the model FIRED on is never
written as a NONE row; a NONE row left beside a BET is cleared; a flexed
kickoff refreshes the row; and the scored writer and the BET writers share a
per-model advisory lock so a BET cannot commit between the scored writer's
read and its insert.
"""

from __future__ import annotations

import csv
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import psycopg2
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
        # The app's storedQuoteBook reads it with mobile/src/lib/clvBet.ts NFL_RE,
        # /,\s*([A-Za-z_]+)\)/ (pinned to paper_tracker._NFL_LABEL_BOOK_RE).
        # A bare "(FD)" misses it and the app calls a FanDuel price DraftKings.
        import re
        r = _eval(model_id, current_book="fanduel", current_line="-3.0")
        (p,) = pub.build_scored_rows({(GAME, model_id): r}, GAMES, 1000.0)
        m = re.search(r",\s*([A-Za-z_]+)\)", p["pick_label"])
        assert m and m.group(1) == "FD"

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

    def __init__(self, games=(), picks=(), delete_rowcount=1):
        self.games, self.picks, self.sql = list(games), list(picks), []
        self.delete_rowcount = delete_rowcount

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.sql.append((flat, params))
        rows = []
        if flat.startswith("SELECT game_id, home_team"):
            rows = self.games
        elif flat.startswith("SELECT pick_id, game_id, model_id, signal_type"):
            rows = self.picks
        n = self.delete_rowcount if flat.startswith("DELETE") else len(rows)

        class R:
            rowcount = n

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


def _none_row(pick_id=7, model_id="nfl_wind_totals", games=GAMES, **eval_kw):
    """An existing NONE row exactly as publish_scored would read it back."""
    (p,) = pub.build_scored_rows({(GAME, model_id): _eval(model_id, **eval_kw)},
                                 games, 1000.0)
    return (pick_id, GAME, model_id, "NONE") + tuple(p[k] for k in pub._SCORED_FIELDS)


def _bet_row(pick_id=1, model_id="nfl_wind_totals", side="under"):
    return (pick_id, GAME, model_id, "BET", "x", side, 0.57, 0.51, 0.06, -105,
            42.5, None, "2026-09-27", "2026-09-27T17:00:00+00:00")


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
        kick = _kick(24)
        games = {GAME: {**GAMES[GAME], "commence_time": kick}}
        (p,) = pub.build_scored_rows({(GAME, "nfl_wind_totals"): _eval()}, games, 1000.0)
        existing = (7, GAME, "nfl_wind_totals", "NONE") + tuple(
            p[k] for k in pub._SCORED_FIELDS)
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", kick)],
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


# ── Reviewer, #838 post-merge ───────────────────────────────────────────────

class TestQualifyingRowIsNotANoneRow:
    """build_scored_rows never read `qualifies`: a game the model FIRED on,
    before its BET row landed, got a "(no bet)" row carrying the firing edge."""

    @pytest.mark.parametrize("model_id", ["nfl_wind_totals", "nfl_opener_spread"])
    def test_fired_row_is_skipped(self, model_id):
        r = _eval(model_id, qualifies="1", model_prob="0.5900", edge="0.0700",
                  reason="wind 14 mph, edge +7.0pp")
        assert pub.build_scored_rows({(GAME, model_id): r}, GAMES, 1000.0) == []

    def test_non_qualifying_row_still_written(self):
        (p,) = pub.build_scored_rows(
            {(GAME, "nfl_wind_totals"): _eval(qualifies="0")}, GAMES, 1000.0)
        assert p["signal_type"] == "NONE"

    def test_fired_row_writes_nothing_to_the_db(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))])
        assert run(conn, [_eval(qualifies="1", model_prob="0.59", edge="0.07")]) == 0
        assert not conn.writes("INSERT") and not conn.writes("UPDATE")


class TestNoneRowBesideABetIsCleared:
    def test_leftover_none_beside_a_bet_is_deleted_with_the_guard(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[_bet_row(), _none_row()])
        assert run(conn, [_eval()]) == 0
        (delete,) = [(q, prm) for q, prm in conn.sql if q.startswith("DELETE")]
        assert "signal_type = 'NONE' AND result IS NULL" in delete[0]
        assert delete[1] == (GAME, "nfl_wind_totals")
        assert not conn.writes("INSERT") and not conn.writes("UPDATE")

    def test_started_game_is_left_alone(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(-1))],
                     picks=[_bet_row(), _none_row()])
        run(conn, [_eval()])
        assert not conn.writes("DELETE")

    def test_no_delete_when_there_is_no_none_row(self, run):
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[_bet_row()])
        run(conn, [_eval()])
        assert not conn.writes("DELETE")

    @pytest.mark.parametrize("rowcount", [1, 0])
    def test_cleared_counts_rows_deleted_not_deletes_tried(self, run, capsys, rowcount):
        # rowcount 0: the row went between the read and the delete.
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[_bet_row(), _none_row()], delete_rowcount=rowcount)
        run(conn, [_eval()])
        assert len(conn.writes("DELETE")) == 1
        assert f"{rowcount} cleared beside a BET" in capsys.readouterr().out


    @pytest.mark.parametrize("rowcount", [1, 0])
    def test_cleared_reads_rowcount_through_the_real_cursor_wrapper(self, run, capsys,
                                                                    rowcount):
        # The fake above sets rowcount itself; this goes through the REAL
        # data.db._CursorResult, which had no rowcount, so prod always read 0.
        from data.db import _CursorResult

        class _Raw:
            def __init__(self, rows, n):
                self.rows, self.rowcount = rows, n

            def fetchall(self):
                return list(self.rows)

            def fetchone(self):
                return self.rows[0] if self.rows else None

        class _Wrapped(_Conn):
            def execute(self, sql, params=None):
                r = super().execute(sql, params)
                return _CursorResult(_Raw(r.fetchall(), r.rowcount))

        conn = _Wrapped(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                        picks=[_bet_row(), _none_row()], delete_rowcount=rowcount)
        assert pub._clear_scored_row(conn, GAME, "nfl_wind_totals") == rowcount
        conn.sql.clear()
        run(conn, [_eval()])
        assert len(conn.writes("DELETE")) == 1
        assert f"{rowcount} cleared beside a BET" in capsys.readouterr().out


class TestFlexedKickoffRefreshes:
    def test_moved_kickoff_alone_refreshes_the_row(self, run):
        # Same line, price and reason; only the kickoff moved (a flex).
        old = _none_row()                              # GAMES: 2026-09-27 17:00Z
        new_kick = _kick(48)
        conn = _Conn(games=[(GAME, "PIT", "CIN", "2026-09-28", new_kick)],
                     picks=[old])
        assert run(conn, [_eval()]) == 1
        (upd,) = [(q, prm) for q, prm in conn.sql if q.startswith("UPDATE picks")]
        assert upd[1]["game_time"] == new_kick and upd[1]["game_date"] == "2026-09-28"
        assert "game_date = %(game_date)s, game_time = %(game_time)s" in upd[0]

    def test_scored_fields_cover_the_kickoff(self):
        assert {"game_date", "game_time"} <= set(pub._SCORED_FIELDS)


class TestPickEmLabel:
    def test_none_row_pick_em_reads_pk(self):
        r = _eval("nfl_opener_spread", current_line="0", current_price="-110")
        (p,) = pub.build_scored_rows({(GAME, "nfl_opener_spread"): r}, GAMES, 1000.0)
        assert p["pick_label"] == "CIN @ PIT — PIT PK (no bet, DK)"
        assert "+0" not in p["pick_label"]
        assert pick_problems(p["pick_label"], "home", 0.0, "nfl_opener_spread",
                             home="PIT", away="CIN") == []

    def test_bet_row_label_is_unchanged(self):
        # The BET label keeps "+0": tracking/pick_integrity reads the FIRST
        # signed number after the dash, and with "PK" that becomes the
        # "(Opener -2.5 vs Pinnacle" deviation -- a false label mismatch on a
        # real bet. Only the NONE row (no signed number after it) says PK.
        _, (p,) = pub.build_opener_rows([{
            "game_id": "2026_03_CIN_PIT", "matchup": "CIN @ PIT",
            "kick_utc": "2026-09-27 17:00:00+00:00", "lead_days": "4.2",
            "side": "away", "bet_team": "CIN", "book": "betmgm", "price": "-105",
            "side_line": "0", "soft_home_line": "0", "pin_home_line": "2.5",
            "dev": "-2.5", "model_prob": "0.5900", "market_prob": "0.5122",
            "edge": "0.0778", "stake_pct": "2.0"}], 1000.0)
        assert "— CIN +0 (Opener" in p["pick_label"]
        assert pick_problems(p["pick_label"], "away", 0.0, "nfl_opener_spread",
                             home="PIT", away="CIN") == []

    @pytest.mark.parametrize("line,text", [(-3.0, "-3"), (6.5, "+6.5"), (0.0, "PK")])
    def test_fmt_spread(self, line, text):
        assert pub._fmt_spread(line) == text


# ── the publish race (Reviewer, #838 post-merge) ────────────────────────────
#
# publish_scored read the BET set and inserted later. An opener BET that
# committed in between made a home NONE insert hit uq_picks_one_row_per_pick
# (rolling back the whole scored pass), and an away BET left a permanent NONE
# row beside it. Both writers now take the same per-model
# pg_advisory_xact_lock BEFORE they read. Simulated here: the lock call is the
# moment the scored writer waits for the opener's transaction, so the fake
# "commits" the opener BET exactly then.

class _RaceConn(_Conn):
    def __init__(self, games, picks, on_lock=None):
        super().__init__(games, picks)
        self.on_lock, self.lock_keys = on_lock, []

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        if "pg_advisory_xact_lock" in flat:
            self.lock_keys.append(params[0])
            if self.on_lock:
                self.on_lock(self)
                self.on_lock = None
        return super().execute(sql, params)


def _lock_index(conn):
    return next(i for i, (q, _) in enumerate(conn.sql) if "pg_advisory_xact_lock" in q)


class TestPublishRace:
    def test_scored_takes_the_lock_before_reading_bets(self, run):
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [])
        run(conn, [_eval()])
        read = next(i for i, (q, _) in enumerate(conn.sql)
                    if q.startswith("SELECT pick_id, game_id, model_id, signal_type"))
        assert _lock_index(conn) < read

    def test_every_scored_model_is_locked_not_just_those_in_the_dump(self, run):
        # The dump has only wind; the picks read (and the cleanup delete)
        # covers every SCORED_MODEL_IDS model, so every one is locked.
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [])
        run(conn, [_eval("nfl_wind_totals")])
        assert conn.lock_keys == [pub._model_lock_key(m)
                                  for m in sorted(pub.SCORED_MODEL_IDS)]

    def test_home_bet_committing_during_the_wait_blocks_the_none_insert(self, run):
        # Without the lock this was the uq_picks_one_row_per_pick violation.
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [],
                         on_lock=lambda c: c.picks.append(
                             _bet_row(model_id="nfl_opener_spread", side="home")))
        r = _eval("nfl_opener_spread", current_line="-3.0", current_price="-108")
        assert run(conn, [r]) == 0
        assert not conn.writes("INSERT") and not conn.writes("UPDATE")

    def test_away_bet_committing_during_the_wait_clears_the_none_row(self, run):
        # Without the lock + cleanup this left a NONE row beside the BET.
        none = _none_row(model_id="nfl_opener_spread", current_line="-3.0")
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [none],
                         on_lock=lambda c: c.picks.append(
                             _bet_row(model_id="nfl_opener_spread", side="away")))
        r = _eval("nfl_opener_spread", current_line="-3.0", current_price="-108")
        run(conn, [r])
        (delete,) = [(q, prm) for q, prm in conn.sql if q.startswith("DELETE")]
        assert delete[1] == (GAME, "nfl_opener_spread")
        assert not conn.writes("INSERT")

    def test_both_models_locked_in_a_fixed_order(self, run):
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [])
        run(conn, [_eval("nfl_wind_totals"), _eval("nfl_opener_spread", current_line="-3")])
        assert conn.lock_keys == [pub._model_lock_key(m) for m in
                                  sorted(("nfl_wind_totals", "nfl_opener_spread"))]

    def test_opener_writer_takes_the_same_key_before_its_lock_read(self, monkeypatch, tmp_path):
        import data.db as db
        conn = _LockConn()
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        monkeypatch.setattr(pub, "_flush_snapshots_safe", lambda d: None)
        _write_card(tmp_path / "opener_card_2026-09-26.csv", {
            "game_id": "2026_03_CIN_PIT", "matchup": "CIN @ PIT",
            "kick_utc": "2026-09-27 17:00:00+00:00", "lead_days": "4.2",
            "side": "home", "bet_team": "PIT", "book": "betmgm", "price": "-105",
            "side_line": "-5.0", "soft_home_line": "-5.0", "pin_home_line": "-2.5",
            "dev": "2.5", "model_prob": "0.5900", "market_prob": "0.5122",
            "edge": "0.0778", "stake_pct": "2.0"})
        pub.publish_opener("2026-09-26")
        lock = _lock_index(conn)
        read = next(i for i, (q, _) in enumerate(conn.sql) if q.startswith("SELECT 1 FROM picks"))
        assert lock < read
        assert conn.sql[lock][1] == (pub._model_lock_key("nfl_opener_spread"),)

    def test_wind_writer_takes_the_same_key_before_its_lock_read(self, monkeypatch, tmp_path):
        import data.db as db
        conn = _LockConn()
        monkeypatch.setattr(db, "get_connection", lambda: conn)
        monkeypatch.setattr(pub, "CARDS_DIR", tmp_path)
        monkeypatch.setattr(pub, "_flush_snapshots_safe", lambda d: None)
        monkeypatch.setattr(pub, "_flush_board_safe", lambda d: None)
        pub.publish("2026-09-26")                  # no card: still locks and reads
        lock = _lock_index(conn)
        read = next(i for i, (q, _) in enumerate(conn.sql)
                    if q.startswith("SELECT DISTINCT game_id FROM picks"))
        assert lock < read
        assert conn.sql[lock][1] == (pub._model_lock_key("nfl_wind_totals"),)

    def test_lock_key_is_stable_and_per_model(self):
        a, b = (pub._model_lock_key(m) for m in ("nfl_wind_totals", "nfl_opener_spread"))
        assert a != b and all(-(2 ** 31) <= k < 2 ** 31 for k in (a, b))
        assert a == pub._model_lock_key("nfl_wind_totals")


# ── the lock survives neither a dropped connection nor a long wait ─────────
#
# #844 review M1: data/db classified `SELECT pg_advisory_xact_lock` as a read,
# so a drop after it reconnected, replayed the next read on a NEW backend
# (which holds no lock) and the pass carried on unlocked. (e): the wait is
# bounded by lock_timeout, and a timeout fails the pass with nothing written.

class _PgCursor:
    def __init__(self, pg):
        self.pg, self.rows, self.rowcount = pg, [], 0

    def execute(self, sql, params=None):
        flat = " ".join(sql.split())
        self.pg.executed.append(flat)
        if self.pg.drop_on and flat.startswith(self.pg.drop_on):
            self.pg.drop_on, self.pg.closed = None, 2
            raise psycopg2.OperationalError("server closed the connection unexpectedly")
        self.rows = self.pg.games if flat.startswith("SELECT game_id, home_team") else []

    def fetchall(self):
        return list(self.rows)

    def fetchone(self):
        return self.rows[0] if self.rows else None


class _Pg:
    """A psycopg2 connection stand-in for data.db.DBConnection."""

    def __init__(self, games=(), drop_on=None):
        self.games, self.drop_on = list(games), drop_on
        self.closed, self.executed, self.commits = 0, [], 0

    def cursor(self):
        if self.closed:
            raise psycopg2.InterfaceError("connection already closed")
        return _PgCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass

    def close(self):
        self.closed = 1


@pytest.fixture
def wrapped(monkeypatch):
    import data.db as db
    reopened: list[_Pg] = []

    def fake_open(url, options=None):
        reopened.append(_Pg())
        return reopened[-1]

    monkeypatch.setattr(db, "_open", fake_open)
    monkeypatch.setattr(db.time, "sleep", lambda s: None)
    return db, reopened


class TestLockSurvivesNothing:
    def test_drop_after_the_lock_raises_connection_lost(self, wrapped):
        db, reopened = wrapped
        first = _Pg(drop_on="SELECT pick_id")
        w = db.DBConnection(first, url="postgresql://x")
        w.execute("SELECT pg_advisory_xact_lock(%s)", (7,))     # the lock alone
        with pytest.raises(db.ConnectionLost):
            w.execute("SELECT pick_id FROM picks")
        assert reopened[0].executed == [], "nothing replayed on the unlocked backend"

    def test_publish_scored_drop_after_the_lock_aborts_the_pass(self, wrapped, run):
        db, reopened = wrapped
        first = _Pg(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                    drop_on="SELECT pick_id, game_id, model_id, signal_type")
        with pytest.raises(db.ConnectionLost):
            run(db.DBConnection(first, url="postgresql://x"), [_eval()])
        assert any("pg_advisory_xact_lock" in q for q in first.executed)
        assert reopened[0].executed == [] and reopened[0].commits == 0

    def test_lock_timeout_is_set_before_every_lock(self, run):
        conn = _RaceConn([(GAME, "PIT", "CIN", "2026-09-27", _kick(24))], [])
        run(conn, [_eval()])
        qs = [q for q, _ in conn.sql]
        for i, q in enumerate(qs):
            if "pg_advisory_xact_lock" in q:
                assert qs[i - 1] == f"SET LOCAL lock_timeout = '{pub._PICKS_LOCK_TIMEOUT}'"

    def test_lock_timeout_fails_the_pass_with_nothing_written(self, run):
        class _LockTimeout(psycopg2.errors.LockNotAvailable):
            pgcode = "55P03"          # what the server sets; unset when built by hand

        class _Busy(_Conn):
            def execute(self, sql, params=None):
                if "pg_advisory_xact_lock" in sql:
                    self.sql.append(("LOCK TIMEOUT", None))
                    raise _LockTimeout("canceling statement due to lock timeout")
                return super().execute(sql, params)
        conn = _Busy(games=[(GAME, "PIT", "CIN", "2026-09-27", _kick(24))],
                     picks=[_bet_row(), _none_row()])
        with pytest.raises(RuntimeError, match="not acquired within"):
            run(conn, [_eval()])
        assert not any(q.startswith(("INSERT", "UPDATE", "DELETE", "COMMIT"))
                       for q, _ in conn.sql)


# ── the preflight's tightened lock checks (Reviewer, #838 post-merge) ───────

class TestPreflightLockChecks:
    @pytest.fixture
    def pf(self):
        from scripts import nfl_preflight
        return nfl_preflight

    def test_guarded_none_delete_is_allowed(self, pf):
        src = '''conn.execute("""
            DELETE FROM picks WHERE game_id = %s
              AND signal_type = 'NONE' AND result IS NULL
        """)'''
        assert pf._unguarded_pick_deletes(src) == []

    @pytest.mark.parametrize("where", [
        "game_id = %s",                                      # anything
        "game_id = %s AND signal_type = 'NONE'",             # settled NONE too
        "game_id = %s AND result IS NULL",                   # an unsettled BET
        "game_id = %s AND signal_type = 'BET' AND result IS NULL",
    ])
    def test_any_other_delete_fails(self, pf, where):
        src = f'''conn.execute("""DELETE FROM picks WHERE {where}""")'''
        assert pf._unguarded_pick_deletes(src)

    @pytest.mark.parametrize("src", [
        # schema-qualified table name: the old regex never matched it
        '''conn.execute("""DELETE FROM public.picks WHERE game_id = %s""")''',
        # OR-form guard: both phrases present, the OR deletes anything
        '''conn.execute("""DELETE FROM picks WHERE signal_type = 'NONE'
               AND result IS NULL OR game_id = %s""")''',
        # guard only in a trailing SQL comment
        '''conn.execute("""DELETE FROM picks WHERE game_id = %s
               -- signal_type = 'NONE' AND result IS NULL
        """)''',
        # guard only in a trailing Python comment
        '''conn.execute("DELETE FROM picks WHERE game_id = %s")  # signal_type = 'NONE' AND result IS NULL''',
    ])
    def test_evasions_fail(self, pf, src):
        assert pf._unguarded_pick_deletes(src)

    def test_guarded_delete_on_public_picks_is_allowed(self, pf):
        src = '''conn.execute("""DELETE FROM public.picks WHERE game_id = %s
               AND signal_type = 'NONE' AND result IS NULL""")'''
        assert pf._unguarded_pick_deletes(src) == []

    def test_lock_section_passes_on_this_tree(self, pf):
        pf.results.clear()
        pf.check_lock_semantics()
        fails = [r for r in pf.results if r[1] == pf.FAIL]
        pf.results.clear()
        assert fails == []

    def test_helper_is_above_both_writers(self):
        src = (ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8")
        assert src.index("\ndef _clear_scored_row(") < src.index("\ndef publish(")


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


# ── preflight: CI mode and the pinned constants (#844 review) ──────────────

class _After(datetime):
    """A clock past the committed schedule (games.csv ends in January 2027)."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2027, 3, 1, tzinfo=timezone.utc)


class TestPreflightCiMode:
    @pytest.fixture
    def pf(self, monkeypatch):
        from scripts import nfl_preflight
        monkeypatch.setattr(nfl_preflight, "datetime", _After)
        monkeypatch.delenv("NFL_PREFLIGHT_OFFLINE", raising=False)
        for name in ("check_models", "check_import_shadowing", "check_lock_semantics",
                     "check_schedule", "check_cards_run", "check_schema",
                     "check_config_gates"):
            monkeypatch.setattr(nfl_preflight, name, lambda: None)
        nfl_preflight.results.clear()
        yield nfl_preflight
        nfl_preflight.results.clear()
        nfl_preflight.CI_MODE = False

    def _schedule(self, pf):
        return next(r for r in pf.results if "schedule covers" in r[2])

    def test_ci_mode_passes_with_a_warning(self, pf):
        assert pf.main(["--ci"]) == 0
        assert self._schedule(pf)[1] == pf.WARN

    def test_offline_env_is_ci_mode(self, pf, monkeypatch):
        monkeypatch.setenv("NFL_PREFLIGHT_OFFLINE", "1")
        assert pf.main([]) == 0
        assert self._schedule(pf)[1] == pf.WARN

    def test_default_mode_still_fails(self, pf):
        assert pf.main([]) == 1
        assert self._schedule(pf)[1] == pf.FAIL

    def test_ci_workflow_runs_ci_mode(self):
        wf = (ROOT / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
        assert "python -m scripts.nfl_preflight --ci" in wf


def test_preflight_pins_the_fire_lead_and_deploy_threshold():
    from scripts import nfl_preflight as pf
    pf.results.clear()
    pf.check_models()
    pf.check_config_gates()
    got = {r[2].split("  — ")[0]: r[1] for r in pf.results}
    pf.results.clear()
    assert got["wind fires no further out than 4 days"] == pf.PASS
    assert got["opener fires at a 2-pt deviation"] == pf.PASS
    assert got["a deviation at DEPLOY_THRESHOLD clears the gate"] == pf.PASS


def test_pick_monitor_reads_locked_bets_only():
    src = (ROOT / "scripts" / "nfl_pick_monitor.py").read_text(encoding="utf-8")
    select = src.split("SELECT p.pick_id, p.game_id, p.model_id", 1)[1].split('"""', 1)[0]
    assert "p.signal_type = 'BET'" in select


def test_scheduler_runs_the_scored_step_on_the_nfl_poll():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    body = src.split("def run_nfl_poll", 1)[1].split("\ndef ", 1)[0]
    assert '"scripts.nfl_wind_publisher", "--scored"' in body
