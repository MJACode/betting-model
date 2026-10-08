"""scripts/nhl_prop_ev_lab.py: the regime grid applies the card's order, and the
whole script runs end to end on a synthetic league without a database.

It runs on the worker (the `nhl_research` job), where a crash costs a deploy
and a five-minute tick, so the end-to-end run here is the check that it will
print rather than raise.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import models.nhl_props as P
import scripts.nhl_prop_backtest as bt
import scripts.nhl_prop_ev_lab as lab

TEAMS = ("BOS", "NYR", "TOR", "MTL")


def _cand(rows):
    return pd.DataFrame(rows, columns=["model_id", "game_id", "pkey", "game_date", "ev", "profit"])


class TestRegimeOrder:
    def test_best_ev_takes_the_games_one_slot(self):
        c = _cand([("m", "g1", "a", "2026-01-01", 0.30, 1.0),
                   ("m", "g1", "b", "2026-01-01", 0.20, -1.0)])
        assert list(lab.regime(c, 0.10, 1, None).pkey) == ["a"]

    def test_the_nightly_limit_keeps_the_nights_best_after_the_game_limit(self):
        c = _cand([("m", "g1", "a", "2026-01-01", 0.30, 1.0),
                   ("m", "g1", "b", "2026-01-01", 0.29, 1.0),     # loses g1's slot to a
                   ("m", "g2", "c", "2026-01-01", 0.25, 1.0),
                   ("m", "g3", "d", "2026-01-01", 0.20, 1.0)])     # third game of a two-bet night
        assert sorted(lab.regime(c, 0.10, 1, 2).pkey) == ["a", "c"]

    def test_the_floor_applies_before_the_caps(self):
        c = _cand([("m", "g1", "a", "2026-01-01", 0.12, 1.0),
                   ("m", "g2", "b", "2026-01-01", 0.30, 1.0)])
        assert list(lab.regime(c, 0.18, 1, 2).pkey) == ["b"]


def _name(kind: str, pid: int) -> str:
    """Letters only: the price matcher (models.nhl_props.name_key) drops digits, so "Skater 103"
    and "Skater 104" would be one player."""
    return f"{kind} " + "".join(chr(ord("a") + int(d)) for d in str(pid))


def _league():
    """Seasons 2020-2027, four teams, three skaters and a starter a side, prices from 2024."""
    rng = np.random.default_rng(11)
    sk, go, tm, games, px = [], [], [], [], []
    gid = 0
    for season in range(2020, 2028):
        start = pd.Timestamp(f"{season - 1}-10-05") if season < 2027 else pd.Timestamp("2026-09-29")
        for d in range(14):
            date = start + pd.Timedelta(days=d)
            ds = date.strftime("%Y-%m-%d")
            for home, away in ((TEAMS[d % 4], TEAMS[(d + 1) % 4]), (TEAMS[(d + 2) % 4], TEAMS[(d + 3) % 4])):
                gid += 1
                game_id = f"NHL_{ds}_{away}_{home}"
                commence = (date + pd.Timedelta(hours=23)).strftime("%Y-%m-%dT%H:%M:%SZ")
                games.append((game_id, season, commence))
                for team, opp, is_home in ((home, away, 1), (away, home, 0)):
                    tm.append({"nhl_game_id": gid, "game_id": game_id, "team": team, "opponent": opp,
                               "game_date": ds, "shots_for": int(rng.integers(20, 40)),
                               "shots_against": int(rng.integers(20, 40)),
                               "goals_against": int(rng.integers(0, 6)),
                               "times_shorthanded": int(rng.integers(0, 6))})
                    t = TEAMS.index(team)
                    for k in range(3):
                        pid = 100 + 10 * t + k
                        a = int(rng.integers(0, 3))
                        sk.append({"nhl_game_id": gid, "player_id": pid, "player_name": _name("Skater", pid),
                                   "position": "D" if k == 0 else "C", "season": season, "game_date": ds,
                                   "team": team, "opponent": opp, "is_home": is_home,
                                   "shots": int(rng.integers(0, 6)), "shot_attempts": int(rng.integers(0, 10)),
                                   "assists": a, "points": a + int(rng.integers(0, 2)),
                                   "toi_seconds": int(rng.integers(600, 1500)),
                                   "pp_toi_seconds": int(rng.integers(0, 200)), "game_type": 2})
                    gk = 900 + t
                    go.append({"nhl_game_id": gid, "player_id": gk, "player_name": _name("Goalie", gk),
                               "season": season, "game_date": ds, "team": team, "opponent": opp,
                               "is_home": is_home, "started": 1, "saves": int(rng.integers(15, 40)),
                               "shots_against": int(rng.integers(18, 44)), "game_type": 2})
                    if season < 2024:
                        continue
                    snaps = ([date + pd.Timedelta(hours=12), date + pd.Timedelta(hours=22, minutes=20)]
                             if season == 2027 else [date + pd.Timedelta(hours=22)])
                    names = [(_name("Skater", 100 + 10 * t + k), m, ln) for k in range(3)
                             for m, ln in (("player_shots_on_goal", 2.5), ("player_assists", 0.5))]
                    names.append((_name("Goalie", gk), "player_total_saves", 24.5))
                    for snap in snaps:
                        for name, market, line in names:
                            for book in ("draftkings", "betmgm", "fanduel"):
                                u = float(rng.choice([-140, -125, -115, -105, 100, 110, 125]))
                                o = -115.0 if u > 0 else 100.0
                                px.append((game_id, name, market, book, line, o, u,
                                           snap.strftime("%Y-%m-%dT%H:%M:%SZ")))
    sk, go, tm = pd.DataFrame(sk), pd.DataFrame(go), pd.DataFrame(tm)
    return sk, go, tm, games, px


@pytest.fixture
def league(monkeypatch):
    sk, go, tm, games, px = _league()
    gdf = pd.DataFrame(games, columns=["game_id", "season", "commence_time"])
    pdf = pd.DataFrame(px, columns=["game_id", "player", "market", "book", "line", "over", "under", "snap"])
    hist = gdf[gdf.season.isin(bt.SEASONS)]

    def fake_load(_cache):
        return {"skater": sk[list(P.SKATER_COLS)], "goalie": go[list(P.GOALIE_COLS)],
                "teams": tm[list(P.TEAM_COLS)], "games": hist,
                "prices": pdf[pdf.game_id.isin(hist.game_id)]}

    def fake_blocked():
        rows = pdf[(pdf.market == "player_shots_on_goal") & (pdf.book == "draftkings")
                   & pdf.game_id.isin(hist.game_id)].drop_duplicates(["game_id", "player"]).copy()
        rows = rows.merge(hist[["game_id", "season"]], on="game_id")
        rows["pkey"] = rows.player.map(P.name_key) + "b"
        rows["game_date"] = pd.to_datetime(rows.game_id.str[4:14])
        rows["side"], rows["price"], rows["line"] = "under", -110.0, 1.5
        rows["p"] = 0.62
        rows["ev"] = rows.p * (1 + rows.price.map(P.win_per_unit)) - 1
        rows["profit"] = np.where(np.arange(len(rows)) % 2 == 0, 100 / 110, -1.0)
        return rows.assign(model_id="nhl_prop_blocked_shots", book="draftkings",
                           won=(rows.profit > 0).astype(int))

    class Conn:
        def execute(self, sql, params=None):
            if "FROM games" in sql:
                self.out = [tuple(r) for r in gdf[gdf.season == params[0]].itertuples(index=False)]
            elif "FROM player_prop_odds" in sql:
                ids, markets = set(params[0]), set(params[1])
                self.out = [r for r in px if r[0] in ids and r[2] in markets]
            else:
                raise AssertionError(sql)
            return self

        def fetchall(self):
            return self.out

        def close(self):
            pass

    import data.db
    monkeypatch.setattr(bt, "load", fake_load)
    monkeypatch.setattr(lab, "blocked_sides", fake_blocked)
    monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: Conn())
    monkeypatch.setattr(P, "load_players", lambda conn, kind, ids=None: (go if kind == "goalie" else sk)[
        list(P.GOALIE_COLS if kind == "goalie" else P.SKATER_COLS)])
    monkeypatch.setattr(P, "load_teams", lambda conn: tm[list(P.TEAM_COLS)])
    monkeypatch.setattr(lab, "FLOORS", (0.0, 0.05))       # random prices: keep enough rows to summarise
    monkeypatch.setattr(lab, "summary", _loose_summary(lab.summary))


def _loose_summary(real):
    def s(label, b):
        if len(b) == 0:
            return {**label, "bets": 0}
        return real(label, pd.concat([b] * max(1, -(-30 // len(b))), ignore_index=True))
    return s


def test_the_whole_script_runs_on_a_synthetic_league(league, capsys):
    lab.main()
    out = capsys.readouterr().out
    for heading in ("TODAY'S RULE, reproduced", "Floor x bets a game", "Floor x bets a night",
                    "FanDuel shopped or not", "Assists on both sides", "2026-27 SO FAR",
                    "decided at the OPEN vs at the CLOSE"):
        assert heading in out, heading
    assert "Traceback" not in out
