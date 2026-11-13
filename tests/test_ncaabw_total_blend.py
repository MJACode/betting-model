"""The NCAABW (women's college basketball) totals model
(models/ncaabw_total_blend.py), its card (scripts/ncaabw_total_card.py), its
artifact, its config, its settlement and its job. mike, 2026-11-09: build the
women's models from the men's learnings.

A fork of tests/test_ncaab_total_blend.py (2026-11-10). The men's tests for
what the two models share are kept (the same synthetic season, the women's
ids). What the women's model changed has its own tests here: the box rows of
two sources placed on their games (place_box), the all-phase blend a thin
phase falls back to, the short-schedule guard, the flat stake.

What these pin, beyond "it runs":
  * AS OF THE QUOTE. Nothing that ended after DraftKings' quote (rounded down
    to the hour) moves a prediction, a games count or a shooting input.
  * The live single-cutoff refit equals the evidence's season pass.
  * The probability the card writes is the one the cut was measured on, so the
    publishers' edge filter agrees with the card.
  * Each game is decided once, and a hold is not a decision.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import pytest

import config


# ── synthetic season ──────────────────────────────────────────────────────────

def _season(n_teams=12, days=70, seed=3, season=2027, start="2026-11-03"):
    """A round-robin-ish season: every team about every third day, tips at
    00:00Z, scores from team strengths. Returns (games, box)."""
    rng = np.random.default_rng(seed)
    teams = list(range(100, 100 + n_teams))
    off = {t: rng.normal(0, 6) for t in teams}
    tem = {t: rng.normal(0, 3) for t in teams}
    rows, box = [], []
    d0 = pd.Timestamp(start)
    eid = 401000000
    for day in range(days):
        if day % 3:
            continue
        perm = rng.permutation(teams)
        for k in range(0, len(perm) - 1, 2):
            h, a = int(perm[k]), int(perm[k + 1])
            gd = (d0 + pd.Timedelta(days=day)).strftime("%Y-%m-%d")
            tip = (d0 + pd.Timedelta(days=day + 1)).strftime("%Y-%m-%dT00:00:00Z")
            poss = 68 + tem[h] + tem[a] + rng.normal(0, 3)
            hs = round(poss * (1.05 + (off[h] - off[a]) / 100) + rng.normal(0, 8))
            as_ = round(poss * (1.02 + (off[a] - off[h]) / 100) + rng.normal(0, 8))
            eid += 1
            gid = f"NCAABW_{gd}_t{a}_t{h}"
            rows.append({"game_id": gid, "season": season, "game_date": gd, "commence_time": tip,
                         "home_score": float(hs), "away_score": float(as_), "neutral_site": 0,
                         "espn_event_id": eid, "home_espn_id": h, "away_espn_id": a,
                         "status": "STATUS_FINAL"})
            for team, opp, pts, dpts in ((h, a, hs, as_), (a, h, as_, hs)):
                fga = round(poss * 0.88 + rng.normal(0, 2)); tpa = round(fga * 0.38)
                fta = round(poss * 0.3); orb = round(fga * 0.12); tov = round(poss * 0.17)
                box.append({"contest_id": f"espn:{eid}", "team": f"t{team}", "game_date": gd,
                            "espn_game_id": eid, "team_espn_id": team, "season": season,
                            "is_home": team == h, "home_espn_id": h, "away_espn_id": a,
                            "pts": float(pts), "d_pts": float(dpts), "fga": float(fga),
                            "fgm": float(round(fga * 0.45)), "tpa": float(tpa),
                            "tpm": float(round(tpa * (0.34 + rng.normal(0, 0.05)))),
                            "fta": float(fta), "ftm": float(round(fta * 0.71)), "orb": float(orb),
                            "drb": float(round(fga * 0.25)), "tov": float(tov),
                            "source": "espn_summary"})
    return pd.DataFrame(rows), pd.DataFrame(box)


def _prior(teams):
    import models.ncaabw_total_blend as nb
    return nb.EndState(teams={t: (1.0 * (t % 5), -0.5 * (t % 3), 0.3 * (t % 4)) for t in teams} | {nb.OTHER: (-5.0, 4.0, 0.0)},
                       mu=106.0, h=2.7, tmu=68.0, htp=0.35)


def _prepared(games, box):
    import scripts.ncaabw_total_card as card
    return card.prepare_season(games, box)


def _art(teams, season=2027):
    import models.ncaabw_total_blend as nb
    return {"kind": nb.ARTIFACT_KIND, "season": season, "prior_season": season - 1,
            "params": {"K": 9.0, "KT": 3.0, "half_life": 45.0, "a": 0.72, "b": 0.0,
                       "r_tempo": 0.9, "K_h": 300.0, "htp_K": 300.0},
            "end_state": _prior(teams).to_json(),
            "league_rates": {"p3": 0.34, "ft": 0.71, "ftr": 0.34, "par3": 0.38, "orbr": 0.29,
                             "tovr": 0.17},
            "stage2": {"cols": list(nb.STAGE2_COLS), "coef": [-0.5, -20, -8, -9, 5, -6, 3, 3, -7]},
            "blend": {"all": {"c": 0.1, "beta": 0.40, "sigma": 16.8, "n": 24000},
                      "Nov": {"c": -0.4, "beta": 0.33, "sigma": 17.4, "n": 4000},
                      "Dec+": {"c": 0.2, "beta": 0.45, "sigma": 16.5, "n": 20000}}}


# ── config, settlement, registration ─────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut_and_floor():
    mid = "ncaabw_total_blend"
    # The women's own cut (docs/sports/ncaabw.md "Research"), not the men's copied.
    assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.05}
    assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.05
    assert config.MODEL_PROB_THRESHOLDS[mid] == 0.0
    assert config.MODEL_OWN_EV_FLOOR[mid] == 0.07
    assert config.min_ev_for(mid) == 0.07
    assert mid in config.MODELS_ON_OWN_PROBABILITY
    assert config.scoring_method(mid) == "rule"
    assert config.min_odds_for(mid) == -200
    # not a trainable model: the trainer and loaders iterate these
    assert mid not in config.MODELS and "NCAABW" not in config.SPORTS
    assert "NCAABW" in config.DISCORD_SPORTS


def test_its_picks_settle_as_totals():
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick("ncaabw_total_blend") == "totals"


def test_its_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert "ncaabw_total_decisions" in WORKER_ONLY_TABLES


# ── the artifact ─────────────────────────────────────────────────────────────

def test_the_committed_artifact_is_complete_and_built_on_the_live_inputs():
    import models.ncaabw_total_blend as nb
    art = nb.load_artifact()
    assert art["season"] == 2027 and art["prior_season"] == 2026
    # no returning-minutes input: a this-season roster is not known in November
    assert art["params"]["a"] == 0.72 and art["params"]["b"] == 0.0
    assert "0.475" in art["possessions"]
    assert len(art["stage2"]["coef"]) == 1 + len(nb.STAGE2_COLS)
    # ESPN's women's schedule is stored from 2015-16; the feed prices 2024-25 on
    assert art["stage2"]["train_seasons"] == [2016, 2026]
    assert art["blend_train_seasons"] == [2025, 2026]
    # every priced game, and each phase with 300 of them: November has 218,
    # so it has no fit of its own and is priced with "all"
    assert set(art["blend"]) == {"all", "Nov", "Dec+"}
    assert art["blend"]["Nov"] is None
    for ph in ("all", "Dec+"):
        b = art["blend"][ph]
        assert b["n"] >= 300 and 0 < b["beta"] < 1 and 10 < b["sigma"] < 25
    assert nb.blend_for(art["blend"], "2026-11-20") == art["blend"]["all"]
    assert nb.blend_for(art["blend"], "2027-01-20") == art["blend"]["Dec+"]
    # the replay the build printed: the card's own decision matched it game by game
    m = art["replay"]["card_path"]["match"]
    assert m["replay_bets"] == m["card_bets"] == m["same_game"] == m["same_side"] > 300
    assert not m["replay_only"] and not m["card_only"] and not m["held"]
    # the edge cap sits above every edge the replay produced
    import models.ncaabw_quote_bounds as qb
    assert art["replay"]["live_blend_in_sample"]["max_edge_every_priced_game"] < qb.EDGE_CAP[nb.MODEL_ID]
    st = nb.EndState.from_json(art["end_state"])
    assert len(st.teams) > 300 and nb.OTHER in st.teams
    assert set(art["league_rates"]) == {"p3", "ft", "ftr", "par3", "orbr", "tovr"}


# ── the decision moment: DraftKings' first posted total ──────────────────────

def test_a_total_outside_90_200_is_a_feed_error():
    """The men's history holds one DraftKings typo, 1465.0 for 146.5. The
    women's range is the women's own: every DraftKings women's total stored
    ran 107.5 to 173.5 (models/ncaabw_quote_bounds.py)."""
    import models.ncaabw_total_blend as nb
    assert nb.TOTAL_RANGE == (90.0, 200.0)
    assert nb.valid_total(146.5) and nb.valid_total("90") and nb.valid_total(200.0)
    for bad in (1465.0, 14.5, 89.5, 200.5, 220.0, None, "x", float("nan")):
        assert not nb.valid_total(bad), bad


def test_the_first_post_read_is_draftkings_earliest_usable_pregame_row():
    import scripts.ncaabw_total_card as card

    class C:
        def execute(self, sql, params):
            self.sql, self.params = " ".join(sql.split()), params

            class R:
                def fetchall(self_inner):
                    return []
            return R()
    c = C()
    now = datetime(2027, 1, 10, 22, 3, tzinfo=timezone.utc)
    assert card.load_first_posts(c, {}, now) == {}
    card.load_first_posts(c, {"g": {}}, now)
    s = c.sql
    assert "o.bookmaker = %s" in s and c.params[1] == "draftkings"
    assert "snapshot_type = 'open'" in s and "o.snapshot_at::timestamptz <= g.ct" in s
    assert "o.created_at::timestamptz <= %s" in s and c.params[2] == now.isoformat()
    # the bound and both prices are in the WHERE, so a typo row is never the
    # first post: the next row is
    where = s.split("WHERE o.market")[1].split("ORDER BY")[0]
    assert "o.total_line::numeric BETWEEN 90 AND 200" in where
    assert "o.over_price IS NOT NULL" in where and "o.under_price IS NOT NULL" in where
    # earliest by DraftKings' own time; one stamp twice keeps the row stored last
    assert s.endswith("ORDER BY o.game_id, o.snapshot_at::timestamptz ASC, "
                      "o.created_at::timestamptz DESC")
    assert "created_at::timestamptz >= %s" not in s      # no freshness bound on the first post


def test_a_quote_row_with_a_typo_total_or_no_price_is_not_a_quote():
    import scripts.ncaabw_total_card as card
    at = datetime(2027, 1, 10, 21, 40, tzinfo=timezone.utc)
    rows = [("a", 1465.0, -110, -110, at.isoformat(), at, None, None),
            ("b", 146.5, None, -110, at.isoformat(), at, None, None),
            ("c", 146.5, "-112", "-108", "2027-01-10T21:40:00Z", at, "lo", "lu")]
    got = card._quote_rows(rows, at + timedelta(minutes=3))
    assert set(got) == {"c"}
    q = got["c"]
    assert (q.line, q.over_price, q.under_price) == (146.5, -112.0, -108.0)
    assert q.quote_at == at


def test_the_first_post_stands_only_at_the_same_total_and_both_prices():
    import scripts.ncaabw_total_card as card
    q = _quote("g", line=146.5, op=-110, up=-110)
    assert card.same_quote(q, _quote("g", line=146.5, op=-110, up=-110,
                                     at=datetime(2027, 1, 10, 22, 50, tzinfo=timezone.utc)))
    assert not card.same_quote(q, _quote("g", line=147.5))
    assert not card.same_quote(q, _quote("g", line=146.5, op=-112))
    assert not card.same_quote(q, _quote("g", line=146.5, up=-108))
    assert not card.same_quote(q, None)


# ── box scores ───────────────────────────────────────────────────────────────

def _box_row(contest, team, tid, source, fga, orb, tov, fta, eid=None, *, date="2026-11-09",
             is_home=None, home=None, away=None, pts=70.0, d_pts=60.0):
    return {"contest_id": contest, "team": team, "game_date": date, "espn_game_id": eid,
            "team_espn_id": tid, "is_home": is_home, "home_espn_id": home, "away_espn_id": away,
            "source": source, "fga": fga, "orb": orb, "tov": tov, "fta": fta,
            "pts": pts, "d_pts": d_pts}


def _game(gid, event, home, away, date="2026-11-09", hs=70.0, as_=60.0):
    return {"game_id": gid, "espn_event_id": event, "game_date": date, "home_espn_id": home,
            "away_espn_id": away, "home_score": hs, "away_score": as_}


def test_ncaas_rows_with_no_espn_game_id_land_on_the_game_and_replace_espns():
    """The women's trap, measured 2026-11-10: NCAA's 2026-27 rows carry no
    ESPN game id (0 of 958), so keyed on that id alone the ESPN feed's two
    rows and NCAA's two rows of one game are four rows of two "games". They
    are matched on the date and both teams, and one source is kept."""
    import models.ncaabw_total_blend as nb
    pbp = nb.PLAY_BY_PLAY_SOURCE
    games = pd.DataFrame([_game("g1", 401900001, 8, 2433), _game("g2", 401900002, 5, 6)])
    espn = [_box_row("espn:401900001", "Arkansas", 8.0, "espn_summary", 62.0, 9.0, 12.0, 20.0,
                     401900001.0, is_home=True, home=8.0, away=2433.0),
            _box_row("espn:401900001", "Northwestern State", 2433.0, "espn_summary", 60.0, 8.0, 15.0, 12.0,
                     401900001.0, is_home=False, home=8.0, away=2433.0, pts=60.0, d_pts=70.0)]
    ncaa = [_box_row("6607281", "Arkansas", 8.0, pbp, 63.0, 9.0, 12.0, 20.0, None,
                     is_home=True, home=8.0, away=2433.0),
            _box_row("6607281", "Northwestern St.", 2433.0, pbp, 61.0, 8.0, 15.0, 12.0, None,
                     is_home=False, home=8.0, away=2433.0, pts=60.0, d_pts=70.0)]
    only_espn = [_box_row("espn:401900002", "A", 5.0, "espn_summary", 58.0, 7.0, 13.0, 18.0,
                          401900002.0, is_home=True, home=5.0, away=6.0),
                 _box_row("espn:401900002", "B", 6.0, "espn_summary", 57.0, 6.0, 14.0, 16.0,
                          401900002.0, is_home=False, home=5.0, away=6.0, pts=60.0, d_pts=70.0)]
    for order in (espn + ncaa + only_espn, only_espn + ncaa + espn):
        d = nb.place_box(pd.DataFrame(order), games)
        assert d.groupby("game_id").size().to_dict() == {"g1": 2, "g2": 2}
        assert set(d[d["game_id"] == "g1"]["source"]) == {pbp}          # NCAA's where it holds the game
        assert set(d[d["game_id"] == "g2"]["source"]) == {"espn_summary"}
        assert d["_key"].nunique() == 2
        assert nb.game_possessions(d)["g1"] == pytest.approx(
            ((63 - 9 + 12 + 0.475 * 20) + (61 - 8 + 15 + 0.475 * 12)) / 2)


def test_a_row_naming_espns_event_is_placed_by_it_whatever_its_teams_say():
    import models.ncaabw_total_blend as nb
    pbp = nb.PLAY_BY_PLAY_SOURCE
    games = pd.DataFrame([_game("g1", 401487517, 161, 2000)])
    # NCAA's rows of a season that carries ESPN's id (2023-24 to 2025-26), neither side with a team id
    rows = pd.DataFrame([_box_row("2335540", "Mercy", np.nan, pbp, 61.0, 6.0, 23.0, 13.0, 401487517.0),
                         _box_row("2335540", "FDU", np.nan, pbp, 76.0, 15.0, 15.0, 17.0, 401487517.0)])
    d = nb.place_box(rows, games)
    assert sorted(d["team"]) == ["FDU", "Mercy"] and set(d["game_id"]) == {"g1"}
    assert nb.game_possessions(d)["g1"] == pytest.approx((84.175 + 84.075) / 2)


def test_a_contest_two_games_could_be_is_placed_on_neither():
    """Two games of the same two teams on one date (a doubleheader, or a
    duplicate schedule row): the date-and-teams key is not unique, so it
    matches nothing; the score key then places each on its own final."""
    import models.ncaabw_total_blend as nb
    pbp = nb.PLAY_BY_PLAY_SOURCE
    games = pd.DataFrame([_game("g1", 1, 8, 9, hs=70.0, as_=60.0), _game("g2", 2, 8, 9, hs=55.0, as_=58.0)])
    a = [_box_row("c1", "H", 8.0, pbp, 60.0, 8.0, 12.0, 15.0, None, is_home=True, home=8.0, away=9.0,
                  pts=70.0, d_pts=60.0),
         _box_row("c1", "A", 9.0, pbp, 60.0, 8.0, 12.0, 15.0, None, is_home=False, home=8.0, away=9.0,
                  pts=60.0, d_pts=70.0)]
    b = [_box_row("c2", "H", 8.0, pbp, 60.0, 8.0, 12.0, 15.0, None, is_home=True, home=8.0, away=9.0,
                  pts=55.0, d_pts=58.0),
         _box_row("c2", "A", 9.0, pbp, 60.0, 8.0, 12.0, 15.0, None, is_home=False, home=8.0, away=9.0,
                  pts=58.0, d_pts=55.0)]
    d = nb.place_box(pd.DataFrame(a + b), games)
    assert d.groupby("contest_id")["game_id"].first().to_dict() == {"c1": "g1", "c2": "g2"}
    # with no score on the schedule yet, neither is placed: a wrong game is worse than none
    unscored = games.assign(home_score=np.nan, away_score=np.nan)
    d2 = nb.place_box(pd.DataFrame(a + b), unscored)
    assert d2["game_id"].isna().all() and d2["_key"].nunique() == 2


def test_a_row_on_no_stored_game_keeps_its_own_key():
    import models.ncaabw_total_blend as nb
    games = pd.DataFrame([_game("g1", 1, 8, 9)])
    rows = pd.DataFrame([_box_row("777", "X", 3.0, nb.PLAY_BY_PLAY_SOURCE, 50.0, 5.0, 10.0, 10.0, None,
                                  date="2026-12-01", is_home=True, home=3.0, away=4.0),
                         _box_row("espn:55", "Y", 4.0, "espn_summary", 50.0, 5.0, 10.0, 10.0, 55.0,
                                  date="2026-12-01", is_home=False, home=3.0, away=4.0)])
    d = nb.place_box(rows, games)
    assert d["game_id"].isna().all()
    assert set(d["_key"]) == {"contest:777", "espn:55"}
    assert len(nb.place_box(rows.iloc[0:0], games)) == 0


def test_a_team_whose_old_games_have_no_team_ids_is_not_held():
    """The live card's hold needs two box rows on a game. With NCAA's rows for
    FDU's games (no team id on either side), each such game kept one row, so
    two of them held every FDU game as box_missing for the rest of the season
    (2024-25: FDU and Saint Francis had five each)."""
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg0, _ = _prepared(games, box)
    t0, at = _late_target(sg0)
    gid = t0["game_id"].iloc[0]
    home = int(t0["home_espn_id"].iloc[0])
    cut_ns = nb.floor_hour_ns(nb.to_ns(at))
    mine = sg0[((sg0["home_espn_id"] == home) | (sg0["away_espn_id"] == home)) & (sg0["end_ns"] <= cut_ns)]
    old = mine.sort_values("end_ns")["game_id"].iloc[-4:-2].tolist()     # ended days before the quote
    ev = dict(zip(games["game_id"], games["espn_event_id"]))
    ncaa = box.copy()
    on_old = ncaa["espn_game_id"].isin([ev[g] for g in old])
    ncaa.loc[on_old, "team_espn_id"] = np.nan
    ncaa.loc[on_old, "source"] = nb.PLAY_BY_PLAY_SOURCE
    ncaa.loc[on_old, "contest_id"] = ncaa.loc[on_old, "espn_game_id"].astype("int64").astype(str) + "0"
    sg, b = _prepared(games, ncaa)
    assert b[b["game_id"].isin(old)].groupby("game_id").size().tolist() == [2, 2]
    art = _art(sorted(set(sg["home_espn_id"])))
    t = sg[sg["game_id"] == gid]
    (d,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, sg, b, art, 0.04)
    assert d.status == "bets", d.detail


def test_possessions_are_the_box_estimate_averaged_and_bounded():
    import models.ncaabw_total_blend as nb
    b = pd.DataFrame({"game_id": ["g", "g", "h", "h"], "fga": [60.0, 56.0, 10.0, 10.0],
                      "orb": [10.0, 8.0, 0.0, 0.0], "tov": [12.0, 14.0, 0.0, 0.0],
                      "fta": [20.0, 16.0, 0.0, 0.0]})
    p = nb.game_possessions(b)
    assert p["g"] == pytest.approx(((60 - 10 + 12 + 0.475 * 20) + (56 - 8 + 14 + 0.475 * 16)) / 2)
    assert np.isnan(p["h"])                      # 10 possessions is not a game


# ── the ratings ──────────────────────────────────────────────────────────────

def test_the_live_refit_equals_the_evidence_season_pass_at_the_same_quote():
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, _ = _prepared(games, box)
    params = nb.Params()
    prior = _prior(sorted(set(sg["home_espn_id"]) | set(sg["away_espn_id"])))
    late = sg.sort_values("dn").iloc[-6:]
    # a quote at 21:40Z the evening before each game
    cut = {g: nb.to_ns(pd.Timestamp(d) - pd.Timedelta(hours=2, minutes=20)) for g, d in
           zip(late["game_id"], late["game_date"])}
    passed, _ = nb.season_pass(sg, prior, params, cut)
    for gid in late["game_id"]:
        c = nb.floor_hour_ns(cut[gid])
        live = nb.ratings_at(sg, prior, params, sg[sg["game_id"] == gid], c).iloc[0]
        ref = passed[passed["game_id"] == gid].iloc[0]
        assert live["pt_s1"] == pytest.approx(ref["pt_s1"], abs=1e-6)
        assert (live["ng_h"], live["ng_a"]) == (ref["ng_h"], ref["ng_a"])


def test_nothing_that_ended_after_the_quote_moves_the_prediction_or_the_count():
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, _ = _prepared(games, box)
    params = nb.Params()
    prior = _prior(sorted(set(sg["home_espn_id"]) | set(sg["away_espn_id"])))
    target = sg.sort_values("dn").iloc[[-1]]
    cut_ns = nb.floor_hour_ns(nb.to_ns(pd.Timestamp(target["game_date"].iloc[0]) - pd.Timedelta(hours=2)))
    base = nb.ratings_at(sg, prior, params, target, cut_ns).iloc[0]
    later = sg[(sg["end_ns"] > cut_ns) & (sg["game_id"] != target["game_id"].iloc[0])]
    assert len(later)
    moved = sg.copy()
    moved.loc[moved["game_id"].isin(later["game_id"]), "home_score"] += 40
    again = nb.ratings_at(moved, prior, params, target, cut_ns).iloc[0]
    assert again["pt_s1"] == base["pt_s1"] and again["ng_h"] == base["ng_h"]
    # and a game that HAD ended does move it
    earlier = sg[sg["end_ns"] <= cut_ns].iloc[[0]]
    moved2 = sg.copy()
    moved2.loc[moved2["game_id"] == earlier["game_id"].iloc[0], "home_score"] += 40
    assert nb.ratings_at(moved2, prior, params, target, cut_ns).iloc[0]["pt_s1"] != base["pt_s1"]


def test_the_shooting_inputs_use_only_games_ended_before_the_quote():
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    pairs = nb.box_pairs(b).assign(season=2027)
    ref = {2027: _art([])["league_rates"]}
    target = sg.sort_values("dn").iloc[[-1]]
    cut_ns = nb.floor_hour_ns(nb.to_ns(pd.Timestamp(target["game_date"].iloc[0]) - pd.Timedelta(hours=2)))
    q = target[["game_id", "home_espn_id", "away_espn_id"]].assign(season=2027, cut_ns=cut_ns)
    base = nb.style_features(pairs, q, ref).iloc[0]
    late = pairs["end_ns"] > cut_ns
    moved = pairs.copy(); moved.loc[late, "tpm"] = moved.loc[late, "tpa"]
    assert nb.style_features(moved, q, ref).iloc[0].equals(base)
    early = pairs["end_ns"] <= cut_ns
    moved2 = pairs.copy(); moved2.loc[early, "tpm"] = moved2.loc[early, "tpa"]
    assert nb.style_features(moved2, q, ref).iloc[0]["luck3_off"] != base["luck3_off"]


# ── pricing ──────────────────────────────────────────────────────────────────

def test_the_probability_is_win_given_no_push_and_the_edge_is_against_the_price():
    import models.ncaabw_total_blend as nb
    from scipy.stats import norm
    b = {"c": 0.0, "beta": 0.5, "sigma": 16.0}
    pz = nb.price(150.0, 144.5, -110, -110, b)          # mean 147.25 over 144.5
    p_over = norm.sf(144.5, 147.25, 16.0)
    assert pz.side == "over" and pz.prob == pytest.approx(p_over)
    assert pz.edge == pytest.approx(p_over - 110 / 210)
    # a whole number: the push is taken out of both sides
    pz2 = nb.price(150.0, 145.0, -110, -110, b)
    pw, pp, pl = nb.outcome_probs(147.5, 16.0, 145.0)
    assert pp > 0 and pz2.prob == pytest.approx(pw / (pw + pl))


def test_a_phase_with_no_fit_of_its_own_is_priced_with_the_all_phase_blend():
    """November has 218 priced games in the two seasons, under the 300 a fit
    needs: its games are priced with the fit on every priced game, as the
    evidence graded them. With neither there is no price."""
    import models.ncaabw_total_blend as nb
    rng = np.random.default_rng(1)
    n = 700
    d = pd.DataFrame({"game_date": ["2025-11-20"] * 200 + ["2026-01-20"] * 500,
                      "line": 130.0 + rng.normal(0, 8, n)})
    d["pt"] = d["line"] + rng.normal(0, 5, n)
    d["total"] = d["line"] + 0.7 * (d["pt"] - d["line"]) + rng.normal(0, 16, n)
    blends = nb.fit_blends(d)
    assert blends["Nov"] is None and blends["Dec+"]["n"] == 500 and blends["all"]["n"] == 700
    assert nb.blend_for(blends, "2026-11-15") is blends["all"]
    assert nb.blend_for(blends, "2026-12-15") is blends["Dec+"]
    assert nb.blend_for({"Nov": None, "Dec+": None}, "2026-11-15") is None
    # and the decision uses it: a November game with only "all" is priced, not no_blend
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    art["blend"]["Nov"] = None
    nov = sg[sg["game_date"].str[5:7] == "11"].sort_values("dn").iloc[[-1]]
    gid = nov["game_id"].iloc[0]
    at = (pd.Timestamp(nov["game_date"].iloc[0]) - pd.Timedelta(hours=2)).tz_localize("UTC").to_pydatetime()
    (d1,) = nb.decide(nov, {gid: _quote(gid, line=125.5, at=at)}, sg, b, art, 0.05)
    assert d1.status == "bets" and d1.priced.sigma == art["blend"]["all"]["sigma"]
    art["blend"]["all"] = None
    (d2,) = nb.decide(nov, {gid: _quote(gid, line=125.5, at=at)}, sg, b, art, 0.05)
    assert d2.status == "no_blend"


# ── the decision ─────────────────────────────────────────────────────────────

def _quote(gid, line=140.5, at=None, op=-110, up=-110):
    import models.ncaabw_total_blend as nb
    at = at or datetime(2027, 1, 10, 21, 40, tzinfo=timezone.utc)
    return nb.Quote(game_id=gid, line=line, over_price=op, under_price=up, quote_at=at,
                    fetched_at=at)


def _late_target(sg):
    t = sg.sort_values("dn").iloc[[-1]]
    at = (pd.Timestamp(t["game_date"].iloc[0]) - pd.Timedelta(hours=2, minutes=20)).tz_localize("UTC")
    return t, at.to_pydatetime()


def test_a_game_is_decided_at_its_quote_with_both_teams_past_ten_games():
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    # a line far under the model: an over with a large edge
    out = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, sg, b, art, 0.04)
    (d,) = out
    assert min(d.ng) >= 10, d.ng
    assert d.status == "bets" and d.priced.side == "over" and d.priced.edge > 0.04
    assert d.cutoff == at.replace(minute=0)
    # the same game at its own line: no edge, still a decision
    near = nb.decide(t, {gid: _quote(gid, line=round(d.model_total) + 0.5, at=at)}, sg, b, art, 0.04)
    assert near[0].status in ("below_cut", "bets")


def test_an_early_game_is_priced_with_no_games_played_wait():
    """No games-played wait, as the evidence was graded. A team's first games
    are decided on the price; with no DraftKings total there is still nothing
    to decide."""
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    early = sg.sort_values("dn").iloc[[10]]
    gid = early["game_id"].iloc[0]
    at = (pd.Timestamp(early["game_date"].iloc[0]) - pd.Timedelta(hours=2)).tz_localize("UTC").to_pydatetime()
    (d,) = nb.decide(early, {gid: _quote(gid, line=125.5, at=at)}, sg, b, art, 0.04)
    assert min(d.ng) < 10, d.ng
    assert d.status == "bets" and d.priced.side == "over"
    assert f"games {d.ng[0]}/{d.ng[1]}" in d.detail
    (d2,) = nb.decide(early, {}, sg, b, art, 0.04)
    assert d2.status == "no_dk_total"


def test_a_missing_box_for_a_game_that_just_ended_holds_the_game():
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    home = int(t["home_espn_id"].iloc[0])
    cut_ns = nb.floor_hour_ns(nb.to_ns(at))
    mine = sg[((sg["home_espn_id"] == home) | (sg["away_espn_id"] == home)) & (sg["end_ns"] <= cut_ns)]
    mine = mine.sort_values("end_ns")
    last = mine.iloc[-1]["game_id"]
    # the team's last game ended five hours before the quote
    recent = sg.copy()
    recent.loc[recent["game_id"] == last, "end_ns"] = cut_ns - 5 * 3600 * 10 ** 9
    (ok,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, recent, b, art, 0.04)
    assert ok.status == "bets"
    (d,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, recent,
                     b[b["game_id"] != last], art, 0.04)
    assert d.status == "box_pending", d.detail
    # a final score not stored yet holds it the same way
    unscored = recent.copy()
    unscored.loc[unscored["game_id"] == last, ["home_score", "away_score"]] = np.nan
    (d2,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, unscored, b, art, 0.04)
    assert d2.status == "box_pending"
    # one old box that never landed does not hold it; two do
    old1 = mine.iloc[-2]["game_id"]; old2 = mine.iloc[-3]["game_id"]
    (d3,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, sg, b[b["game_id"] != old1], art, 0.04)
    assert d3.status == "bets"
    (d4,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, sg,
                      b[~b["game_id"].isin([old1, old2])], art, 0.04)
    assert d4.status == "box_missing"


def test_a_held_first_post_is_decided_as_of_its_own_hour_and_the_wait_ages_to_now():
    """The quote stays the first post while a box is awaited, so the cutoff
    never moves; the 36-hour wait for a box that never lands is counted to the
    run's instant, not to that fixed cutoff."""
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    home = int(t["home_espn_id"].iloc[0])
    cut_ns = nb.floor_hour_ns(nb.to_ns(at))
    mine = sg[((sg["home_espn_id"] == home) | (sg["away_espn_id"] == home)) & (sg["end_ns"] <= cut_ns)]
    last = mine.sort_values("end_ns").iloc[-1]["game_id"]
    recent = sg.copy()
    recent.loc[recent["game_id"] == last, "end_ns"] = cut_ns - 5 * 3600 * 10 ** 9
    nobox = b[b["game_id"] != last]
    q = {gid: _quote(gid, line=125.5, at=at)}
    # an hour later the box is still missing: held, at the same first post
    (d,) = nb.decide(t, q, recent, nobox, art, 0.04, now=at + timedelta(hours=1))
    assert d.status == "box_pending" and d.quote.quote_at == at
    # the box lands: decided at the first post, as of the first post's hour
    (ok,) = nb.decide(t, q, recent, b, art, 0.04, now=at + timedelta(hours=3))
    (same,) = nb.decide(t, q, recent, b, art, 0.04)
    assert ok.status == "bets" and ok.cutoff == at.replace(minute=0)
    assert ok.priced == same.priced and ok.model_total == same.model_total
    # 36 hours after that game ended the missing box stops holding (one old
    # missing box never holds)
    (late,) = nb.decide(t, q, recent, nobox, art, 0.04, now=at + timedelta(hours=32))
    assert late.status == "bets" and late.cutoff == at.replace(minute=0)


# ── the card ─────────────────────────────────────────────────────────────────

def _bet_decision():
    import models.ncaabw_total_blend as nb
    q = _quote("NCAABW_2027-01-10_kansas_duke", line=145.5)
    pz = nb.Priced(side="over", prob=0.58, price=-110.0, edge=0.58 - 110 / 210, mean=149.0, sigma=16.5)
    return nb.Decision("NCAABW_2027-01-10_kansas_duke", "bets", "over", quote=q,
                       cutoff=datetime(2027, 1, 10, 21, tzinfo=timezone.utc), model_total=152.0,
                       priced=pz, ng=(14, 15))


GAMES = {"NCAABW_2027-01-10_kansas_duke": {"home": "Duke", "away": "Kansas",
                                          "game_date": "2027-01-10",
                                          "commence_time": "2027-01-11T00:00:00Z",
                                          "tip": datetime(2027, 1, 11, tzinfo=timezone.utc),
                                          "season": 2027}}


def test_a_bet_row_carries_the_probability_the_cut_was_measured_on():
    import scripts.ncaabw_total_card as card
    rows, refused = card.pick_rows([_bet_decision()], GAMES, 1000.0)
    assert not refused
    (r,) = rows
    assert r["pick_label"] == "Duke vs Kansas Over 145.5"
    assert r["model_probability"] == 0.58 and r["model_probability_cal"] == 0.58
    assert r["dk_odds"] == r["decision_odds"] == -110.0
    assert r["decision_book"] == "draftkings" and r["best_book"] is None and r["line_book"] is None
    assert r["decision_edge"] == pytest.approx(0.58 - 110 / 210, abs=1e-4)
    # the publishers' filter: decision_edge >= the model's min_edge
    assert r["decision_edge"] >= config.ACTION_THRESHOLDS["ncaabw_total_blend"]["min_edge"]
    assert r["signal_type"] == "BET" and r["scored_line"] == 145.5


def test_a_bet_under_its_ev_floor_is_refused():
    import models.ncaabw_total_blend as nb
    import scripts.ncaabw_total_card as card
    d = _bet_decision()
    d.priced = nb.Priced(side="over", prob=0.56, price=-150.0, edge=0.56 - 0.6, mean=149.0, sigma=16.5)
    rows, refused = card.pick_rows([d], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and d.game_id in refused


class _Conn:
    def __init__(self, decided=()):
        self.decided = set(decided)
        self.sql = []
        self.ledger, self.picks = [], []
        self.committed = False

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        s = " ".join(sql.split())
        res = []
        if s.startswith("SELECT 1 FROM information_schema.tables"):
            res = [(1,)]
        elif "FROM ncaabw_total_decisions" in s:
            res = [(g,) for g in self.decided]
        elif "FROM picks" in s:
            res = []
        elif s.startswith("INSERT INTO ncaabw_total_decisions"):
            if params["game_id"] in self.decided:
                res = []
            else:
                self.decided.add(params["game_id"]); self.ledger.append(params)
                res = [(params["game_id"],)]
        elif s.startswith("INSERT INTO picks"):
            self.picks.append(params); res = [(1,)]

        class R:
            def fetchone(self_inner):
                return res[0] if res else None

            def fetchall(self_inner):
                return res
        return R()

    def commit(self):
        self.committed = True


def test_publish_writes_the_decision_and_the_bet_once_and_never_a_hold(monkeypatch):
    import models.ncaabw_total_blend as nb
    import scripts.ncaabw_total_card as card
    import scripts.nfl_wind_publisher as pub
    monkeypatch.setattr(pub, "_lock_model", lambda conn, mid: conn.execute("SELECT pg_advisory_xact_lock"))
    d = _bet_decision()
    hold = nb.Decision("NCAABW_2027-01-10_x_y", "box_pending", "a box to land")
    rows, refused = card.pick_rows([d], GAMES, 1000.0)
    conn = _Conn()
    hour = datetime(2027, 1, 10, 22, tzinfo=timezone.utc)
    assert card.publish(conn, rows, [d, hold], hour, refused) == (1, 1)
    assert [x["game_id"] for x in conn.ledger] == [d.game_id]
    assert len(conn.picks) == 1 and conn.committed
    # the next hour: decided already, nothing written
    assert card.publish(conn, rows, [d], hour + timedelta(hours=1), refused) == (0, 0)
    assert len(conn.picks) == 1


def test_a_decided_game_is_never_decided_again_and_the_slate_reads_the_ledger_alone():
    import scripts.ncaabw_total_card as card
    insert = " ".join(card._INSERT_DECISION.split())
    assert insert.endswith("ON CONFLICT (game_id) DO NOTHING RETURNING game_id")
    conn = _Conn(decided=["g"])
    assert card.decided_games(conn, ["g", "h"]) == {"g"}
    assert [s for s, _ in conn.sql if "FROM picks" in s]
    # the whole slate is read from the ledger alone; picks only when asked
    ledger_only = _Conn()
    card.decided_games(ledger_only, ["g"], bets=False)
    assert not [s for s, _ in ledger_only.sql if "FROM picks" in s]


def test_every_bet_is_the_flat_stake():
    """One women's model, so no second bet to agree with: the card writes no
    stake_units, which every surface reads as the flat 1 unit to win."""
    import scripts.ncaabw_total_card as card
    assert "stake_units" not in card._COLS and "stake_reason" not in card._COLS
    rows, _ = card.pick_rows([_bet_decision()], GAMES, 1000.0)
    assert set(rows[0]) == set(card._COLS)


def test_the_quote_read_is_pregame_draftkings_and_fresh():
    import scripts.ncaabw_total_card as card

    class C:
        def execute(self, sql, params):
            self.sql, self.params = " ".join(sql.split()), params

            class R:
                def fetchall(self_inner):
                    return []
            return R()
    c = C()
    now = datetime(2027, 1, 10, 22, 5, tzinfo=timezone.utc)
    card.load_quotes(c, {"g": {}}, now)
    assert "o.bookmaker = %s" in c.sql and c.params[1] == "draftkings"
    assert "snapshot_type = 'open'" in c.sql
    assert "o.snapshot_at::timestamptz <= g.ct" in c.sql
    assert c.params[2] == now.isoformat()
    assert c.params[3] == (now - timedelta(minutes=card.DK_MAX_AGE_MIN)).isoformat()


def test_the_kill_switch_reads_nothing(monkeypatch):
    import scripts.ncaabw_total_card as card
    monkeypatch.setenv("RUN_NCAABW_TOTAL_CARD", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.run_card(do_publish=True)["off"] is True


# ── a run that cannot decide its games fails, after publishing the rest ──────

class _ClosingConn:
    def close(self):
        pass


def _card_run(monkeypatch, art, extra_season=None, drop_boxes=(), standing="same", d1=(),
              keep_games=None):
    """run_card over the synthetic season's last game, read through stubs:
    no database. `extra_season` adds a game of that season to the slate;
    `drop_boxes` removes those games' box rows; `standing` is DraftKings'
    standing number against the first post ("same", "moved" or None); `d1`
    is the registry's Division I ids; `keep_games` keeps only that many of the
    stored games before the target (a schedule not stored whole).
    -> (card, published calls, now, (sg, target, first-post time))."""
    import scripts.ncaabw_total_card as card
    monkeypatch.delenv("RUN_NCAABW_TOTAL_CARD", raising=False)
    games, box = _season()
    sg, _ = _prepared(games, box)
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    tip = datetime.fromisoformat(t["commence_time"].iloc[0].replace("Z", "+00:00"))
    slate = {gid: {"season": 2027, "game_date": t["game_date"].iloc[0], "tip": tip,
                   "commence_time": t["commence_time"].iloc[0], "home": "Duke", "away": "Kansas"}}
    if extra_season:
        slate["NCAABW_next_season"] = dict(slate[gid], season=extra_season)
    box = box[~box["espn_game_id"].isin(games[games["game_id"].isin(drop_boxes)]["espn_event_id"])]
    if keep_games is not None:
        games = pd.concat([games[games["game_id"] != gid].sort_values("commence_time").tail(keep_games),
                           games[games["game_id"] == gid]])
    monkeypatch.setattr(card, "get_connection", lambda: _ClosingConn())
    monkeypatch.setattr(card, "slate", lambda conn, now: slate)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids, bets=True: set())
    monkeypatch.setattr(card, "ensure_decisions_table", lambda conn: None)
    monkeypatch.setattr(card, "artifact", lambda: art)
    monkeypatch.setattr(card, "load_season", lambda conn, season: (games, box))
    monkeypatch.setattr(card, "d1_team_ids", lambda conn: set(d1))
    firsts = {x: _quote(x, line=125.5, at=at) for x in slate}
    monkeypatch.setattr(card, "load_first_posts", lambda conn, g, now: {
        x: q for x, q in firsts.items() if x in g})
    later = at + timedelta(minutes=20)
    now_q = {"same": lambda x: _quote(x, line=125.5, at=later),
             "moved": lambda x: _quote(x, line=126.5, at=later),
             "typo": lambda x: _quote(x, line=1005.0, at=later),
             None: lambda x: None}[standing]
    monkeypatch.setattr(card, "load_quotes", lambda conn, g, now: {
        x: now_q(x) for x in g if now_q(x) is not None})
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    calls = []
    monkeypatch.setattr(card, "publish", lambda conn, rows, decisions, hour, refused:
                        calls.append([d.status for d in decisions]) or (len(rows), len(decisions)))
    now = at + timedelta(minutes=23)       # the run after the capture stored the first post
    return card, calls, now, (sg, t, at)


def test_an_artifact_for_another_season_fails_the_run_after_publishing(monkeypatch):
    """November 2027 with nobody having rebuilt the artifact: every game of
    season 2028 is skipped. The run used to log an error and exit 0, so the
    heartbeat stayed green and the model placed nothing all season."""
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, _ = _card_run(monkeypatch, art, extra_season=2028)
    with pytest.raises(card.CardIncomplete, match="season 2028"):
        card.run_card(do_publish=True, now=now)
    assert calls == [["bets"]]          # season 2027's bet still went to the ledger first


def test_a_missing_blend_fails_the_run(monkeypatch):
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    # a phase with no fit falls back to the all-phase fit; with neither, no price
    art["blend"]["Dec+"] = None
    art["blend"]["all"] = None
    card, calls, now, _ = _card_run(monkeypatch, art)
    with pytest.raises(card.CardIncomplete, match="no_blend"):
        card.run_card(do_publish=False, now=now)


def test_a_season_long_box_hold_fails_the_run(monkeypatch):
    """box_missing holds every game of a team until its old boxes land, which
    can be all season: the run fails so the failure alerter says so."""
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, _ = _prepared(games, box)
    t, at = _late_target(sg)
    home = int(t["home_espn_id"].iloc[0])
    cut_ns = nb.floor_hour_ns(nb.to_ns(at))
    mine = sg[((sg["home_espn_id"] == home) | (sg["away_espn_id"] == home)) & (sg["end_ns"] <= cut_ns)]
    old = mine.sort_values("end_ns")["game_id"].iloc[-3:-1].tolist()
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, _ = _card_run(monkeypatch, art, drop_boxes=old)
    with pytest.raises(card.CardIncomplete, match="box_missing"):
        card.run_card(do_publish=False, now=now)


def test_a_schedule_not_stored_whole_fails_the_run_and_decides_nothing(monkeypatch):
    """Measured 2026-11-10 on the first run against the stored tables: the
    women's schedule held 1,245 games to 2026-11-23, so no team had 10 and
    every team would have been pooled into the "other" team, each game priced
    off one pooled rating. A Division I team under 10 stored games stops its
    game and fails the run."""
    games, box = _season()
    sg, _ = _prepared(games, box)
    t, _at = _late_target(sg)
    teams = sorted(set(sg["home_espn_id"]) | set(sg["away_espn_id"]))
    art = _art(teams)
    card, calls, now, _ = _card_run(monkeypatch, art, d1=teams, keep_games=12)
    with pytest.raises(card.CardIncomplete, match="schedule_short"):
        card.run_card(do_publish=True, now=now)
    assert calls == [["schedule_short"]] and "schedule_short" not in card.FINAL
    # the same short schedule for two sides that are not Division I: pooled, as the model means
    card, calls, now, _ = _card_run(monkeypatch, art, d1=(), keep_games=12)
    out = card.run_card(do_publish=True, now=now)
    assert out["diag"]["schedule_short"] == 0 and calls and calls[0][0] in ("bets", "below_cut")
    # and the whole schedule with Division I sides decides
    card, calls, now, _ = _card_run(monkeypatch, art, d1=teams)
    assert card.run_card(do_publish=True, now=now)["bets"] == 1


def test_the_guard_names_each_short_team():
    import scripts.ncaabw_total_card as card
    sg = pd.DataFrame([{"game_id": "a", "home_espn_id": 1.0, "away_espn_id": 2.0,
                        "n_sched_home": 7, "n_sched_away": 31},
                       {"game_id": "b", "home_espn_id": 3.0, "away_espn_id": np.nan,
                        "n_sched_home": 9, "n_sched_away": 0},
                       {"game_id": "c", "home_espn_id": 1.0, "away_espn_id": 2.0,
                        "n_sched_home": 7, "n_sched_away": 31}])
    got = card.schedule_short(sg, ["a", "b"], {1, 2})
    assert got == {"a": "team 1 has 7 game(s) on the stored schedule"}       # 3 is not Division I; c not asked
    assert card.schedule_short(sg, ["a"], set()) == {}


def test_a_complete_run_does_not_raise(monkeypatch):
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, _ = _card_run(monkeypatch, art)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 1 and calls == [["bets"]]


def test_the_bet_is_at_the_first_post_as_of_its_hour(monkeypatch):
    """The card decides at DraftKings' first posted total, as of that row's
    own hour, at any minute of any hour: there is no decision hour."""
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, _, (_, t, at) = _card_run(monkeypatch, art)
    got = []
    monkeypatch.setattr(card, "publish", lambda conn, rows, decisions, hour, refused:
                        got.append((rows, decisions, hour)) or (len(rows), len(decisions)))
    now = at + timedelta(hours=1, minutes=48)
    assert now.minute not in (0, 5) and now.hour not in (15, 22)
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 1
    ((rows, (d,), hour),) = got
    assert d.status == "bets" and d.cutoff == at.replace(minute=0)
    assert d.quote.quote_at == at and d.quote.line == 125.5
    assert rows[0]["scored_line"] == 125.5 and hour == now


def test_a_first_post_no_longer_standing_is_decided_with_no_bet(monkeypatch):
    """The first post moved before the card saw it (or DraftKings took the
    total down): decided first_post_gone, final, and never bet at the later
    number."""
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    for standing in ("moved", None):
        card, calls, now, _ = _card_run(monkeypatch, art, standing=standing)
        out = card.run_card(do_publish=True, now=now)
        assert out["bets"] == 0 and out["diag"]["first_post_gone"] == 1
        assert calls == [["first_post_gone"]]


def test_a_standing_total_that_is_a_feed_error_makes_the_game_wait(monkeypatch):
    """Whether the first post still stands is unknown while DraftKings'
    standing row is a typo: not a bet, not gone, looked at again next run."""
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, _ = _card_run(monkeypatch, art, standing="typo")
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 0 and out["diag"]["out_of_range"] == 1
    assert calls == [["out_of_range"]] and "out_of_range" not in card.FINAL


def test_a_game_with_no_first_post_reads_nothing_more(monkeypatch):
    games, box = _season()
    sg, _ = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    card, calls, now, _ = _card_run(monkeypatch, art)
    monkeypatch.setattr(card, "load_first_posts", lambda conn, g, now: {})
    monkeypatch.setattr(card, "load_season", lambda conn, season: (_ for _ in ()).throw(
        AssertionError("the season read is for a first post only")))
    out = card.run_card(do_publish=True, now=now)
    assert out["bets"] == 0 and out["diag"]["no_dk_total"] == 1 and calls == []


def test_an_incomplete_run_exits_non_zero(monkeypatch):
    import scripts.ncaabw_total_card as card
    monkeypatch.setattr(card, "run_card", lambda do_publish=False: (_ for _ in ()).throw(
        card.CardIncomplete("season 2028: no artifact")))
    with pytest.raises(SystemExit) as e:
        card.main(["--publish"])
    assert e.value.code == 1


# ── the job ──────────────────────────────────────────────────────────────────

def _jobs(monkeypatch):
    from tests.test_nba_prop_window import _jobs as jobs
    return jobs(monkeypatch)


def test_the_job_runs_every_five_minutes_three_after_each_capture_tick(monkeypatch):
    """DraftKings' first total is stored by the women's capture (minute
    1-59/5, 120 s timeout) and decided three minutes later, a minute after the
    men's card."""
    import scheduler
    from tests.test_nba_prop_window import _fires
    from tracking.job_heartbeat import MAX_SILENCE
    jobs = _jobs(monkeypatch)
    job = jobs["ncaabw_total_card"]
    assert job.max_instances == 1 and job.coalesce is True
    assert job.misfire_grace_time < 300                   # a late fire never stacks behind the next
    for start in (datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc),     # standard time
                  datetime(2027, 3, 20, 0, 0, tzinfo=timezone.utc)):     # after DST returns
        fires = _fires(job, start, start + timedelta(hours=23, minutes=59))
        assert len(fires) == 288
        utc = [f.astimezone(timezone.utc) for f in fires]
        assert all(f.minute % 5 == 4 for f in utc)
        cap = _fires(jobs["ncaabw_odds_capture"], start, start + timedelta(hours=23, minutes=59))
        assert {f.astimezone(timezone.utc).minute % 5 for f in cap} == {1}
        men = _fires(jobs["ncaab_total_card"], start, start + timedelta(hours=23, minutes=59))
        assert {f.astimezone(timezone.utc).minute % 5 for f in men} == {3}
    assert "ncaabw_total_card" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaabw_total_card"] == 20


def test_the_job_runs_the_card_and_publishes(monkeypatch):
    import scheduler
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    scheduler.run_ncaabw_total_card()
    assert ran[0][-3:] == ["-m", "scripts.ncaabw_total_card", "--publish"]
    assert pub == ["ncaabw-total-card"]
    # a run that fails still publishes what it wrote, THEN raises
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaabw_total_card()
    assert pub == ["ncaabw-total-card", "ncaabw-total-card"]


def test_a_failed_card_run_beats_error_and_the_alerter_reports_it(monkeypatch):
    """The whole chain for a card that exits non-zero: the scheduled job raises,
    its heartbeat records 'error', and the failure alerter's read of the
    heartbeats lists the job."""
    import scheduler
    from tracking import job_heartbeat as jh
    beats = []
    job = _jobs(monkeypatch)["ncaabw_total_card"]
    monkeypatch.setattr(jh, "beat", lambda jid, status, detail="": beats.append((jid, status, detail)))
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: None)
    with pytest.raises(RuntimeError):
        job.func()
    assert beats and beats[-1][:2] == ("ncaabw_total_card", "error")

    class C:
        def execute(self, sql, params=None):
            class R:
                def fetchall(self_inner):
                    return [("ncaabw_total_card", "error", beats[-1][2])]
            return R()
    assert [j for j, _ in jh.failing_jobs(C())] == ["ncaabw_total_card"]


def test_a_game_against_an_opponent_with_no_espn_id_still_counts_in_the_inputs():
    """NCAA's box rows for a non-Division I opponent often carry no ESPN team
    id. The evidence kept the team's side of that game; dropping it emptied
    the early-season inputs of every team that opened against one."""
    import models.ncaabw_total_blend as nb
    box = pd.DataFrame([
        {"_key": "contest:1", "team_espn_id": 5.0, "fga": 60.0, "tpa": 20.0, "tpm": 9.0, "fta": 20.0,
         "ftm": 15.0, "orb": 10.0, "drb": 25.0, "tov": 12.0},
        {"_key": "contest:1", "team_espn_id": np.nan, "fga": 55.0, "tpa": 22.0, "tpm": 5.0, "fta": 10.0,
         "ftm": 6.0, "orb": 8.0, "drb": 20.0, "tov": 18.0},
    ])
    p = nb.box_pairs(box)
    assert len(p) == 1 and p.iloc[0]["team_espn_id"] == 5.0
    assert p.iloc[0]["x_tov"] == 18.0


def test_a_team_is_pooled_by_its_own_seasons_schedule():
    """The build prepares sixteen seasons in one frame: a team that left
    Division I later must still be itself in the seasons it played a full
    schedule (Hartford 2011 was pooled by its 2023 count before this)."""
    import models.ncaabw_total_blend as nb
    g = pd.DataFrame([
        {"game_id": "a", "season": 2011, "game_date": "2010-11-13", "commence_time": "2010-11-14T00:00:00Z",
         "home_espn_id": 42, "away_espn_id": 7, "n_sched_home": 31, "n_sched_away": 30, "neutral_site": 0},
        {"game_id": "b", "season": 2024, "game_date": "2023-11-13", "commence_time": "2023-11-14T00:00:00Z",
         "home_espn_id": 42, "away_espn_id": 7, "n_sched_home": 3, "n_sched_away": 30, "neutral_site": 0},
    ])
    sg = nb.season_games(g)
    assert sg["hid"].tolist() == [42, nb.OTHER]
    assert sg["aid"].tolist() == [7, 7]


def test_a_box_whose_opponent_row_has_no_espn_id_does_not_hold_the_game():
    """NCAA's row for a non-Division I opponent carries no ESPN team id (the
    men's replay once held half a season on it). A game is boxed when both of
    its rows are stored."""
    import models.ncaabw_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    home = int(t["home_espn_id"].iloc[0])
    cut_ns = nb.floor_hour_ns(nb.to_ns(at))
    mine = sg[((sg["home_espn_id"] == home) | (sg["away_espn_id"] == home)) & (sg["end_ns"] <= cut_ns)]
    last = mine.sort_values("end_ns").iloc[-1]
    recent = sg.copy()
    recent.loc[recent["game_id"] == last["game_id"], "end_ns"] = cut_ns - 5 * 3600 * 10 ** 9
    opp = int(last["away_espn_id"]) if int(last["home_espn_id"]) == home else int(last["home_espn_id"])
    no_id = b.copy()
    no_id.loc[(no_id["game_id"] == last["game_id"]) & (no_id["team_espn_id"] == opp), "team_espn_id"] = np.nan
    (d,) = nb.decide(t, {gid: _quote(gid, line=125.5, at=at)}, recent, no_id, art, 0.04)
    assert d.status == "bets", d.detail


def test_a_game_priced_below_the_cut_is_a_none_row_and_one_waiting_is_no_row():
    """The All board shows every scored game."""
    import models.ncaabw_total_blend as nb
    import scripts.ncaabw_total_card as card
    d = _bet_decision()
    d.status = "below_cut"
    (r,), refused = card.pick_rows([d], GAMES, 1000.0)
    assert not refused
    assert (r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) == ("NONE", 0.0, 0.0)
    assert (r["pick_side"], r["scored_line"]) == ("over", 145.5)
    waiting = nb.Decision(d.game_id, "box_pending", "x", quote=d.quote)
    assert card.pick_rows([waiting], GAMES, 1000.0) == ([], {})


def test_publish_counts_only_bets_and_marks_a_none_row_as_no_bet_in_the_ledger():
    import scripts.ncaabw_total_card as card
    d = _bet_decision()
    d.status = "below_cut"
    rows, refused = card.pick_rows([d], GAMES, 1000.0)
    conn = _Conn()
    import scripts.nfl_wind_publisher as wp
    orig, wp._lock_model = wp._lock_model, (lambda c, m: None)
    try:
        assert card.publish(conn, rows, [d], datetime(2027, 1, 10, 21, tzinfo=timezone.utc),
                            refused) == (0, 1)
    finally:
        wp._lock_model = orig
    assert [p["signal_type"] for p in conn.picks] == ["NONE"]
    assert conn.ledger[0]["n_bets"] == 0


def test_the_womens_sport_has_the_same_emoji_as_the_mens():
    from tracking.discord_notifier import _SPORT_EMOJI
    assert _SPORT_EMOJI["NCAABW"] == _SPORT_EMOJI["NCAAB"]
