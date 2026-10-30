"""The NCAAB totals model (models/ncaab_total_blend.py), its card
(scripts/ncaab_total_card.py), its artifact, its config, its settlement and its
job. mike, 2026-10-30: "Yes to the totals model".

What these pin, beyond "it runs":
  * AS OF THE QUOTE. Nothing that ended after DraftKings' quote (rounded down
    to the hour) moves a prediction, a 10-game count or a shooting input.
  * The live single-cutoff refit equals the evidence's season pass.
  * The probability the card writes is the one the cut was measured on, so the
    publishers' edge filter agrees with the card.
  * Each game is decided once, and a hold is not a decision.
"""
from __future__ import annotations

import json
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
            gid = f"NCAAB_{gd}_t{a}_t{h}"
            rows.append({"game_id": gid, "season": season, "game_date": gd, "commence_time": tip,
                         "home_score": float(hs), "away_score": float(as_), "neutral_site": 0,
                         "espn_event_id": eid, "home_espn_id": h, "away_espn_id": a,
                         "status": "STATUS_FINAL"})
            for team, opp, pts, dpts in ((h, a, hs, as_), (a, h, as_, hs)):
                fga = round(poss * 0.88 + rng.normal(0, 2)); tpa = round(fga * 0.38)
                fta = round(poss * 0.3); orb = round(fga * 0.12); tov = round(poss * 0.17)
                box.append({"contest_id": f"espn:{eid}", "team": f"t{team}", "game_date": gd,
                            "espn_game_id": eid, "team_espn_id": team, "season": season,
                            "pts": float(pts), "d_pts": float(dpts), "fga": float(fga),
                            "fgm": float(round(fga * 0.45)), "tpa": float(tpa),
                            "tpm": float(round(tpa * (0.34 + rng.normal(0, 0.05)))),
                            "fta": float(fta), "ftm": float(round(fta * 0.71)), "orb": float(orb),
                            "drb": float(round(fga * 0.25)), "tov": float(tov),
                            "source": "espn_summary"})
    return pd.DataFrame(rows), pd.DataFrame(box)


def _prior(teams):
    import models.ncaab_total_blend as nb
    return nb.EndState(teams={t: (1.0 * (t % 5), -0.5 * (t % 3), 0.3 * (t % 4)) for t in teams} | {nb.OTHER: (-5.0, 4.0, 0.0)},
                       mu=106.0, h=2.7, tmu=68.0, htp=0.35)


def _prepared(games, box):
    import scripts.ncaab_total_card as card
    return card.prepare_season(games, box)


def _art(teams, season=2027):
    import models.ncaab_total_blend as nb
    return {"kind": nb.ARTIFACT_KIND, "season": season, "prior_season": season - 1,
            "params": {"K": 9.0, "KT": 3.0, "half_life": 45.0, "a": 0.72, "b": 0.0,
                       "r_tempo": 0.9, "K_h": 300.0, "htp_K": 300.0},
            "end_state": _prior(teams).to_json(),
            "league_rates": {"p3": 0.34, "ft": 0.71, "ftr": 0.34, "par3": 0.38, "orbr": 0.29,
                             "tovr": 0.17},
            "stage2": {"cols": list(nb.STAGE2_COLS), "coef": [-0.5, -20, -8, -9, 5, -6, 3, 3, -7]},
            "blend": {"Nov": {"c": -0.4, "beta": 0.33, "sigma": 17.4, "n": 4000},
                      "Dec+": {"c": 0.2, "beta": 0.45, "sigma": 16.5, "n": 20000}}}


# ── config, settlement, registration ─────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut_and_floor():
    mid = "ncaab_total_blend"
    assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.04}
    assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.04
    assert config.MODEL_PROB_THRESHOLDS[mid] == 0.0
    assert config.MODEL_OWN_EV_FLOOR[mid] == 0.07
    assert config.min_ev_for(mid) == 0.07
    assert mid in config.MODELS_ON_OWN_PROBABILITY
    assert config.scoring_method(mid) == "rule"
    assert config.min_odds_for(mid) == -200
    # not a trainable model: the trainer and loaders iterate these
    assert mid not in config.MODELS and "NCAAB" not in config.SPORTS
    assert "NCAAB" in config.DISCORD_SPORTS


def test_its_picks_settle_as_totals():
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick("ncaab_total_blend") == "totals"


def test_its_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert "ncaab_total_decisions" in WORKER_ONLY_TABLES


# ── the artifact ─────────────────────────────────────────────────────────────

def test_the_committed_artifact_is_complete_and_built_on_the_live_inputs():
    import models.ncaab_total_blend as nb
    art = nb.load_artifact()
    assert art["season"] == 2027 and art["prior_season"] == 2026
    # no returning-minutes input: a this-season roster is not known in November
    assert art["params"]["a"] == 0.72 and art["params"]["b"] == 0.0
    assert "0.475" in art["possessions"]
    assert len(art["stage2"]["coef"]) == 1 + len(nb.STAGE2_COLS)
    assert art["stage2"]["train_seasons"] == [2012, 2026]
    assert art["blend_train_seasons"] == [2021, 2026]
    for ph in nb.PHASES:
        b = art["blend"][ph]
        assert b["n"] >= 300 and 0 < b["beta"] < 1 and 10 < b["sigma"] < 25
    st = nb.EndState.from_json(art["end_state"])
    assert len(st.teams) > 300 and nb.OTHER in st.teams
    assert set(art["league_rates"]) == {"p3", "ft", "ftr", "par3", "orbr", "tovr"}


# ── decision hours ───────────────────────────────────────────────────────────

def test_decision_hours_are_22z_the_evening_before_then_15z_on_until_tip():
    import models.ncaab_total_blend as nb
    tip = datetime(2026, 12, 6, 0, 30, tzinfo=timezone.utc)     # ET date 2026-12-05
    at = lambda d, h: datetime(2026, 12, d, h, tzinfo=timezone.utc)  # noqa: E731
    assert nb.decision_hour("2026-12-05", tip, at(4, 22))
    assert not nb.decision_hour("2026-12-05", tip, at(4, 21))
    assert not nb.decision_hour("2026-12-05", tip, at(4, 23))      # no overnight hours
    assert not nb.decision_hour("2026-12-05", tip, at(5, 3))
    assert not nb.decision_hour("2026-12-05", tip, at(5, 14))
    assert nb.decision_hour("2026-12-05", tip, at(5, 15))
    assert nb.decision_hour("2026-12-05", tip, at(5, 23))
    assert nb.decision_hour("2026-12-05", tip, at(6, 0))          # 00:00Z, tip 00:30Z
    assert not nb.decision_hour("2026-12-05", tip, at(6, 1))


# ── box scores ───────────────────────────────────────────────────────────────

def test_the_play_by_play_row_wins_and_the_key_is_espns_game_id():
    import models.ncaab_total_blend as nb
    rows = pd.DataFrame([
        {"contest_id": "espn:9", "espn_game_id": 9, "team_espn_id": 1, "source": "espn_summary", "fga": 60.0},
        {"contest_id": "5551", "espn_game_id": 9, "team_espn_id": 1, "source": nb.PLAY_BY_PLAY_SOURCE, "fga": 61.0},
        {"contest_id": "espn:9", "espn_game_id": 9, "team_espn_id": 2, "source": "espn_summary", "fga": 55.0},
        {"contest_id": "777", "espn_game_id": None, "team_espn_id": 3, "source": nb.PLAY_BY_PLAY_SOURCE, "fga": 50.0},
    ])
    d = nb.dedupe_box(rows)
    assert len(d) == 3
    assert d[d["team_espn_id"] == 1]["fga"].tolist() == [61.0]
    assert set(d["_key"]) == {"espn:9", "contest:777"}


def test_possessions_are_the_box_estimate_averaged_and_bounded():
    import models.ncaab_total_blend as nb
    b = pd.DataFrame({"game_id": ["g", "g", "h", "h"], "fga": [60.0, 56.0, 10.0, 10.0],
                      "orb": [10.0, 8.0, 0.0, 0.0], "tov": [12.0, 14.0, 0.0, 0.0],
                      "fta": [20.0, 16.0, 0.0, 0.0]})
    p = nb.game_possessions(b)
    assert p["g"] == pytest.approx(((60 - 10 + 12 + 0.475 * 20) + (56 - 8 + 14 + 0.475 * 16)) / 2)
    assert np.isnan(p["h"])                      # 10 possessions is not a game


# ── the ratings ──────────────────────────────────────────────────────────────

def test_the_live_refit_equals_the_evidence_season_pass_at_the_same_quote():
    import models.ncaab_total_blend as nb
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
    import models.ncaab_total_blend as nb
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
    import models.ncaab_total_blend as nb
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
    import models.ncaab_total_blend as nb
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


# ── the decision ─────────────────────────────────────────────────────────────

def _quote(gid, line=140.5, at=None, op=-110, up=-110):
    import models.ncaab_total_blend as nb
    at = at or datetime(2027, 1, 10, 21, 40, tzinfo=timezone.utc)
    return nb.Quote(game_id=gid, line=line, over_price=op, under_price=up, quote_at=at,
                    fetched_at=at)


def _late_target(sg):
    t = sg.sort_values("dn").iloc[[-1]]
    at = (pd.Timestamp(t["game_date"].iloc[0]) - pd.Timedelta(hours=2, minutes=20)).tz_localize("UTC")
    return t, at.to_pydatetime()


def test_a_game_is_decided_at_its_quote_with_both_teams_past_ten_games():
    import models.ncaab_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    t, at = _late_target(sg)
    gid = t["game_id"].iloc[0]
    # a line far under the model: an over with a large edge
    out = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, sg, b, art, 0.04)
    (d,) = out
    assert min(d.ng) >= 10, d.ng
    assert d.status == "bets" and d.priced.side == "over" and d.priced.edge > 0.04
    assert d.cutoff == at.replace(minute=0)
    # the same game at its own line: no edge, still a decision
    near = nb.decide(t, {gid: _quote(gid, line=round(d.model_total) + 0.5, at=at)}, sg, b, art, 0.04)
    assert near[0].status in ("below_cut", "bets")


def test_no_draftkings_total_and_early_season_are_not_bets():
    import models.ncaab_total_blend as nb
    games, box = _season()
    sg, b = _prepared(games, box)
    art = _art(sorted(set(sg["home_espn_id"])))
    early = sg.sort_values("dn").iloc[[10]]
    gid = early["game_id"].iloc[0]
    at = (pd.Timestamp(early["game_date"].iloc[0]) - pd.Timedelta(hours=2)).tz_localize("UTC").to_pydatetime()
    (d,) = nb.decide(early, {gid: _quote(gid, line=100.5, at=at)}, sg, b, art, 0.04)
    assert d.status == "below_10_games"
    (d2,) = nb.decide(early, {}, sg, b, art, 0.04)
    assert d2.status == "no_dk_total"


def test_a_missing_box_for_a_game_that_just_ended_holds_the_game():
    import models.ncaab_total_blend as nb
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
    (ok,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, recent, b, art, 0.04)
    assert ok.status == "bets"
    (d,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, recent,
                     b[b["game_id"] != last], art, 0.04)
    assert d.status == "box_pending", d.detail
    # a final score not stored yet holds it the same way
    unscored = recent.copy()
    unscored.loc[unscored["game_id"] == last, ["home_score", "away_score"]] = np.nan
    (d2,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, unscored, b, art, 0.04)
    assert d2.status == "box_pending"
    # one old box that never landed does not hold it; two do
    old1 = mine.iloc[-2]["game_id"]; old2 = mine.iloc[-3]["game_id"]
    (d3,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, sg, b[b["game_id"] != old1], art, 0.04)
    assert d3.status == "bets"
    (d4,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, sg,
                      b[~b["game_id"].isin([old1, old2])], art, 0.04)
    assert d4.status == "box_missing"


# ── the card ─────────────────────────────────────────────────────────────────

def _bet_decision():
    import models.ncaab_total_blend as nb
    q = _quote("NCAAB_2027-01-10_kansas_duke", line=145.5)
    pz = nb.Priced(side="over", prob=0.58, price=-110.0, edge=0.58 - 110 / 210, mean=149.0, sigma=16.5)
    return nb.Decision("NCAAB_2027-01-10_kansas_duke", "bets", "over", quote=q,
                       cutoff=datetime(2027, 1, 10, 21, tzinfo=timezone.utc), model_total=152.0,
                       priced=pz, ng=(14, 15))


GAMES = {"NCAAB_2027-01-10_kansas_duke": {"home": "Duke", "away": "Kansas",
                                          "game_date": "2027-01-10",
                                          "commence_time": "2027-01-11T00:00:00Z",
                                          "tip": datetime(2027, 1, 11, tzinfo=timezone.utc),
                                          "season": 2027}}


def test_a_bet_row_carries_the_probability_the_cut_was_measured_on():
    import scripts.ncaab_total_card as card
    rows, refused = card.pick_rows([_bet_decision()], GAMES, 1000.0)
    assert not refused
    (r,) = rows
    assert r["pick_label"] == "Duke vs Kansas Over 145.5"
    assert r["model_probability"] == 0.58 and r["model_probability_cal"] == 0.58
    assert r["dk_odds"] == r["decision_odds"] == -110.0
    assert r["decision_book"] == "draftkings" and r["best_book"] is None and r["line_book"] is None
    assert r["decision_edge"] == pytest.approx(0.58 - 110 / 210, abs=1e-4)
    # the publishers' filter: decision_edge >= the model's min_edge
    assert r["decision_edge"] >= config.ACTION_THRESHOLDS["ncaab_total_blend"]["min_edge"]
    assert r["signal_type"] == "BET" and r["scored_line"] == 145.5


def test_a_bet_under_its_ev_floor_is_refused():
    import models.ncaab_total_blend as nb
    import scripts.ncaab_total_card as card
    d = _bet_decision()
    d.priced = nb.Priced(side="over", prob=0.56, price=-150.0, edge=0.56 - 0.6, mean=149.0, sigma=16.5)
    rows, refused = card.pick_rows([d], GAMES, 1000.0)
    assert not rows and d.game_id in refused


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
        elif "FROM ncaab_total_decisions" in s:
            res = [(g,) for g in self.decided]
        elif "FROM picks" in s:
            res = []
        elif s.startswith("INSERT INTO ncaab_total_decisions"):
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
    import models.ncaab_total_blend as nb
    import scripts.ncaab_total_card as card
    import scripts.nfl_wind_publisher as pub
    monkeypatch.setattr(pub, "_lock_model", lambda conn, mid: conn.execute("SELECT pg_advisory_xact_lock"))
    d = _bet_decision()
    hold = nb.Decision("NCAAB_2027-01-10_x_y", "box_pending", "a box to land")
    rows, refused = card.pick_rows([d], GAMES, 1000.0)
    conn = _Conn()
    hour = datetime(2027, 1, 10, 22, tzinfo=timezone.utc)
    assert card.publish(conn, rows, [d, hold], hour, refused) == (1, 1)
    assert [x["game_id"] for x in conn.ledger] == [d.game_id]
    assert len(conn.picks) == 1 and conn.committed
    # the next hour: decided already, nothing written
    assert card.publish(conn, rows, [d], hour + timedelta(hours=1), refused) == (0, 0)
    assert len(conn.picks) == 1


def test_the_quote_read_is_pregame_draftkings_and_fresh():
    import scripts.ncaab_total_card as card

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
    import scripts.ncaab_total_card as card
    monkeypatch.setenv("RUN_NCAAB_TOTAL_CARD", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.run_card(do_publish=True)["off"] is True


# ── the job ──────────────────────────────────────────────────────────────────

def _jobs(monkeypatch):
    from tests.test_nba_prop_window import _jobs as jobs
    return jobs(monkeypatch)


def test_the_job_runs_hourly_at_five_past_utc_all_year(monkeypatch):
    import scheduler
    from tests.test_nba_prop_window import _fires
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaab_total_card"]
    assert job.max_instances == 1 and job.coalesce is True
    for start in (datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc),     # standard time
                  datetime(2027, 3, 20, 0, 0, tzinfo=timezone.utc)):     # after DST returns
        fires = _fires(job, start, start + timedelta(hours=23, minutes=59))
        assert len(fires) == 24
        utc = [f.astimezone(timezone.utc) for f in fires]
        assert all(f.minute == 5 for f in utc)
        assert {f.hour for f in utc} >= {22, 15}
    assert "ncaab_total_card" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_total_card"] >= 120


def test_the_job_runs_the_card_and_publishes(monkeypatch):
    import scheduler
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    scheduler.run_ncaab_total_card()
    assert ran[0][-3:] == ["-m", "scripts.ncaab_total_card", "--publish"]
    assert pub == ["ncaab-total-card"]
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaab_total_card()


# ── Discord ──────────────────────────────────────────────────────────────────

class _Resp:
    def __init__(self, status, body):
        self.status_code, self._body = status, body

    def json(self):
        return self._body


def test_a_channel_id_resolves_to_the_bots_own_webhook(monkeypatch):
    import tracking.discord_notifier as dn
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    monkeypatch.setattr(dn.config, "DISCORD_CHANNELS", {"NCAAB": "123"})
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    dn._CHANNEL_HOOKS.clear()
    calls = []

    def get(url, headers=None, timeout=None):
        assert headers["Authorization"] == "Bot tok"
        calls.append(("GET", url))
        if url.endswith("/users/@me"):
            return _Resp(200, {"id": "999"})
        return _Resp(200, [{"id": "1", "token": "other", "user": {"id": "555"}},
                           {"id": "2", "token": "mine", "user": {"id": "999"}}])

    def post(*a, **k):
        raise AssertionError("must reuse the bot's own webhook")
    monkeypatch.setattr(dn.requests, "get", get)
    monkeypatch.setattr(dn.requests, "post", post)
    url = dn._webhook_for_sport("NCAAB")
    assert url == "https://discord.com/api/webhooks/2/mine"
    n = len(calls)
    assert dn._webhook_for_sport("NCAAB") == url and len(calls) == n     # cached


def test_a_channel_without_a_bot_webhook_gets_one_created(monkeypatch):
    import tracking.discord_notifier as dn
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    monkeypatch.setattr(dn.config, "DISCORD_CHANNELS", {"NCAAB": "123"})
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    dn._CHANNEL_HOOKS.clear()
    monkeypatch.setattr(dn.requests, "get", lambda url, headers=None, timeout=None:
                        _Resp(200, {"id": "999"}) if url.endswith("/users/@me") else _Resp(200, []))
    made = []

    def post(url, headers=None, json=None, timeout=None):
        made.append((url, json))
        return _Resp(200, {"id": "7", "token": "new"})
    monkeypatch.setattr(dn.requests, "post", post)
    assert dn._webhook_for_sport("NCAAB") == "https://discord.com/api/webhooks/7/new"
    assert made and made[0][0].endswith("/channels/123/webhooks")


def test_a_webhook_variable_wins_and_failures_never_log_the_url(monkeypatch):
    import tracking.discord_notifier as dn
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {"NCAAB": "http://hook"})
    monkeypatch.setattr(dn.config, "DISCORD_CHANNELS", {"NCAAB": "123"})
    monkeypatch.setenv("DISCORD_BOT_TOKEN", "tok")
    assert dn._webhook_for_sport("NCAAB") == "http://hook"
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOKS", {})
    monkeypatch.setattr(dn.config, "DISCORD_WEBHOOK_DEFAULT", "")
    dn._CHANNEL_HOOKS.clear()
    monkeypatch.setattr(dn.requests, "get", lambda *a, **k: _Resp(403, {"message": "Missing Access"}))
    assert dn._webhook_for_sport("NCAAB") is None
    # no token: no call at all
    monkeypatch.delenv("DISCORD_BOT_TOKEN")
    dn._CHANNEL_HOOKS.clear()
    monkeypatch.setattr(dn.requests, "get", lambda *a, **k: (_ for _ in ()).throw(AssertionError("call")))
    assert dn._webhook_for_sport("NCAAB") is None


def test_the_channel_script_clones_the_ncaaf_channels_place_and_permissions():
    import scripts.discord_create_sport_channel as sc
    src = {"id": "11", "name": "ncaaf", "type": 0, "parent_id": "77", "position": 9,
           "topic": "college football", "nsfw": False, "rate_limit_per_user": 0,
           "permission_overwrites": [{"id": "1", "type": 0, "allow": "0", "deny": "1024"},
                                     {"id": "2", "type": 0, "allow": "1024", "deny": "0"}]}
    body = sc.create_body(src, "ncaab")
    assert body["name"] == "ncaab" and body["type"] == 0
    assert body["parent_id"] == "77" and body["position"] == 10
    assert body["permission_overwrites"] == src["permission_overwrites"]
    channels = [src, {"id": "12", "name": "ncaab-live", "type": 0}]
    assert sc.find_channel(channels, "ncaaf")["id"] == "11"
    assert sc.find_channel(channels, "ncaab") is None


def test_the_channel_job_is_a_dry_run_unless_told_to_apply(monkeypatch):
    import tracking.job_queue as jq
    fn, validate = jq.JOBS["discord_create_channel"]
    args = validate({"name": "ncaab", "like": "ncaaf"})
    assert args["apply"] is False
    ran = []
    monkeypatch.setattr(jq, "_run_script_main", lambda mod, argv: ran.append((mod, argv)) or "ok")
    fn(**args)
    fn(**validate({"name": "ncaab", "like": "ncaaf", "apply": True}))
    assert ran == [("scripts.discord_create_sport_channel", ["--name", "ncaab", "--like", "ncaaf", "--dry-run"]),
                   ("scripts.discord_create_sport_channel", ["--name", "ncaab", "--like", "ncaaf"])]
    for bad in ({"name": "NCAAB!", "like": "ncaaf"}, {"name": "ncaab", "like": "ncaaf", "apply": "yes"},
                {"name": "ncaab", "like": "ncaaf", "shell": "rm"}):
        with pytest.raises(ValueError):
            validate(bad)


def test_a_game_against_an_opponent_with_no_espn_id_still_counts_in_the_inputs():
    """NCAA's box rows for a non-Division I opponent often carry no ESPN team
    id. The evidence kept the team's side of that game; dropping it emptied
    the early-season inputs of every team that opened against one."""
    import models.ncaab_total_blend as nb
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
    import models.ncaab_total_blend as nb
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
    """Replaying the live path on 2025-26 held 2,857 of 5,586 games: NCAA's
    row for a non-Division I opponent carries no ESPN team id, so the hold read
    the game as unboxed. A game is boxed when both of its rows are stored."""
    import models.ncaab_total_blend as nb
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
    (d,) = nb.decide(t, {gid: _quote(gid, line=100.5, at=at)}, recent, no_id, art, 0.04)
    assert d.status == "bets", d.detail
