"""NHL prop overs are a paper track. They are not picks.

The 2026-10-02 side sweep (docs/nhl_market_lab.md) found no over cell that
clears. Live cards keep writing unders. An over that clears the same floor
is stored in nhl_prop_paper_overs and must not become a BET.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import config
import models.nhl_prop_blocked_shots as bs
import models.nhl_props as P
from scripts import nhl_prop_card as blocked_card
from scripts import nhl_prop_over_paper as paper
from tests.test_nhl_prop_blocked_shots import GAMES as BLOCKED_GAMES
from tests.test_nhl_prop_blocked_shots import _scored
from tests.test_nhl_props import GAME, GAMES, _mus, _quotes

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "add_nhl_prop_paper_overs.sql"


class TestAnOverIsNotAPick:
    def test_a_blocked_shots_over_that_clears_is_paper_and_not_published(self):
        """Mean 3.0 at 1.5, over -110: the over is the price the old card kept.
        The published card is unders, so this row is not a pick."""
        scored = _scored(mu=3.0, under=-400, over=-110, line=1.5)
        assert blocked_card.pick_rows(scored, BLOCKED_GAMES, "2026-10-01", 1000.0) == []
        d = blocked_card.decide(3.0, 1.5, -110, -400)
        assert d["side"] == "under"
        overs = paper.blocked_paper_overs(scored, BLOCKED_GAMES, "2026-10-01")
        assert len(overs) == 1
        r = overs[0]
        assert r["pick_side"] == "over" and r["model_id"] == bs.MODEL_ID
        assert r["pick_label"] == "Charlie McAvoy Over 1.5 Blocked Shots (DK)"
        assert r["book"] == "draftkings" and r["price"] == -110
        assert r["ev"] >= config.min_ev_for(bs.MODEL_ID)
        assert "signal_type" not in r

    def test_a_shots_over_the_live_spec_refuses_is_paper(self):
        q = _quotes([(1, "draftkings", 1.5, 150, -190)])
        mus = _mus([(1, 4.0)])
        assert P.SHOTS.sides == ("under",) and P.SHOTS.max_per_game == 3
        from scripts import nhl_props_card as card
        assert card.pick_rows(P.SHOTS, mus, q, GAMES, "2026-10-01", 1000.0, 0.0) == []
        rows = paper.props_paper_overs(P.SHOTS, mus, q, GAMES, "2026-10-01", 0.0)
        assert len(rows) == 1
        assert rows[0]["pick_side"] == "over" and rows[0]["model_id"] == P.SHOTS.model_id
        assert rows[0]["pick_label"] == "Skater 1 Over 1.5 Shots on Goal"
        assert "signal_type" not in rows[0]
        assert rows[0]["ev"] >= 0.10

    def test_the_per_game_cap_does_not_apply_to_paper_overs(self):
        """The cap of 3 is an under-board limit. The sweep that rejected overs
        did not apply it, so the paper track does not either."""
        q = _quotes([(i, "draftkings", 1.5, 150, -190) for i in range(1, 5)])
        mus = _mus([(i, 4.0) for i in range(1, 5)])
        rows = paper.props_paper_overs(P.SHOTS, mus, q, GAMES, "2026-10-01", 0.0)
        assert len(rows) == 4
        assert {r["player_id"] for r in rows} == {"1", "2", "3", "4"}

    def test_an_under_cannot_be_copied_onto_the_paper_track(self):
        with pytest.raises(ValueError, match="overs only"):
            paper.from_card_row({"pick_side": "under", "game_id": GAME})


class TestGrading:
    def test_units_not_dollars(self):
        assert paper.grade_units(2, 1.5, -110) == ("WIN", round(P.win_per_unit(-110), 4))
        assert paper.grade_units(1, 1.5, 150) == ("LOSS", -1.0)
        assert paper.grade_units(1.5, 1.5, -110) == ("PUSH", 0.0)

    def test_a_logged_game_with_no_stat_is_left_alone(self, monkeypatch):
        pending = [(7, GAME, "nhl_prop_shots_on_goal", "1", 2.5, -110.0, "2026-10-01")]
        updates = []

        class Conn:
            def execute(self, sql, params=None):
                class R:
                    def fetchall(self_inner):
                        return pending if "SELECT" in sql else []
                if "UPDATE" in sql:
                    updates.append(params)
                return R()

            def commit(self):
                pass

        monkeypatch.setattr(
            "tracking.paper_tracker._load_nhl_prop_actuals",
            lambda conn, date: {("1", GAME): {"shots": None}},
        )
        assert paper.settle_paper(Conn(), "2026-10-01") == 0
        assert updates == []

    def test_a_dnp_in_a_logged_game_is_no_action(self, monkeypatch):
        pending = [(9, GAME, "nhl_prop_shots_on_goal", "1", 2.5, -110.0, "2026-10-01")]
        updates = []

        class Conn:
            def execute(self, sql, params=None):
                class R:
                    def fetchall(self_inner):
                        return pending if "SELECT" in sql else []
                if "UPDATE" in sql:
                    updates.append(params)
                return R()

            def commit(self):
                self.committed = True

        # Another skater logged the game; this player did not dress.
        monkeypatch.setattr(
            "tracking.paper_tracker._load_nhl_prop_actuals",
            lambda conn, date: {("2", GAME): {"shots": 3}},
        )
        assert paper.settle_paper(Conn(), "2026-10-01") == 1
        assert updates[0][0] == "NO_ACTION" and updates[0][1] == 0.0


class TestItDoesNotWriteAPick:
    def test_record_paper_inserts_into_its_own_table_once(self):
        seen = []

        class Conn:
            def execute(self, sql, params=None):
                seen.append(sql)
                class R:
                    def fetchone(self_inner):
                        return (1,) if len(seen) == 1 else None
                return R()

            def commit(self):
                self.commits = getattr(self, "commits", 0) + 1

        row = {
            "game_id": GAME, "model_id": "nhl_prop_shots_on_goal", "player_id": "1",
            "game_date": "2026-10-01", "pick_label": "Skater 1 Over 1.5 Shots on Goal",
            "scored_line": 1.5, "price": 150.0, "book": "draftkings",
            "model_probability": 0.8, "ev": 0.2,
        }
        conn = Conn()
        assert paper.record_paper(conn, [row]) == 1
        assert paper.record_paper(conn, [row]) == 0
        blob = "\n".join(seen)
        assert "INSERT INTO nhl_prop_paper_overs" in blob
        assert "ON CONFLICT (game_id, model_id, player_id) DO NOTHING" in blob
        assert "INSERT INTO picks" not in blob
        src = Path(paper.__file__).read_text(encoding="utf-8")
        assert "INSERT INTO picks" not in src
        insert = src.split("_INSERT =", 1)[1].split('"""', 2)[1]
        assert "signal_type" not in insert and "picks" not in insert.lower()

    def test_the_migration_is_recording_only_and_one_statement(self):
        from data.view_migrations import ACTIVE_MIGRATIONS
        assert MIG.name in ACTIVE_MIGRATIONS
        sql = MIG.read_text(encoding="utf-8")
        assert "DO $$" in sql and "to_regclass('public.nhl_prop_paper_overs')" in sql
        assert "ENABLE ROW LEVEL SECURITY" in sql
        assert "REVOKE ALL ON public.nhl_prop_paper_overs FROM anon, authenticated" in sql
        assert "INSERT INTO picks" not in sql
        # One statement: the runner uses conn.execute, which cannot split a DO block.
        body = sql.split("DO $$", 1)[1]
        assert body.strip().endswith("$$;")
        assert "DO $$" not in body
