"""IG-2, the in-game state model (scripts/nba_ingame_ig2.py,
docs/nba_models_2026.md 7.2-7.3), on synthetic frames.

What each test pins:
  - the freshness rule: a deciding quote is used only when no point came after
    its stamp, none came after its Pinnacle quote's stamp, Pinnacle is paired,
    and the book is one of the 8 deciding books;
  - the decision is the FIRST eligible fetch in a phase, even when a later
    fetch in the phase would carry a higher EV;
  - the Q4 phase needs 6:00 or more on the clock (5:59 is out), and halftime is
    not a phase;
  - walk-forward: a model for season S refuses any row of season S or later;
  - the Stern limit: with no time left the leader wins;
  - a home margin of +5 makes home -3.5 the likelier spread side (the sign that
    has flipped twice in this repo);
  - the foul inputs point the right way (an away team in the penalty, or an
    away star in foul trouble, favours home);
  - the information test: a model that knows something the benchmark does not
    gives an interval below zero; one that knows nothing gives an interval
    that covers zero; and the gate needs BOTH intervals below zero;
  - the side the model favours is the side whose best offer has the higher EV;
  - the training grid takes the latest play at or before each game time.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from scripts import nba_ingame_ig2 as G

T0 = pd.Timestamp("2025-01-10T01:00:00Z")


def quote(book="draftkings", market="h2h", pts_since=0, pin_since=0, pin_fa=0.6, period=3,
          phase="live", clock=500.0, fetch=0, stamp=0, game="G1", coherent=True):
    f = T0 + pd.Timedelta(hours=fetch)
    s = f - pd.Timedelta(minutes=5) + pd.Timedelta(seconds=stamp)
    return {"game_id": game, "market": market, "book": book, "coherent": coherent, "pin_fa": pin_fa,
            "pts_since_stamp": pts_since, "pin_pts_since": pin_since, "period": period, "phase": phase,
            "clock_s": clock, "fetch_at": f, "stamp": s, "pin_stamp": s}


def test_the_freshness_rule_keeps_only_fresh_paired_deciding_quotes():
    q = pd.DataFrame([
        quote(),                                   # kept
        quote(book="fanduel", pts_since=2),        # a point after its own stamp
        quote(book="betmgm", pin_since=1),         # a point after Pinnacle's stamp
        quote(book="betrivers", pin_fa=np.nan),    # no Pinnacle within 60 s
        quote(book="pinnacle"),                    # never a deciding book
        quote(book="bovada"),                      # never a deciding book
        quote(book="draftkings", market="totals"),  # not an IG-2 market
        quote(book="williamhill_us", coherent=False),
    ])
    el = G.eligible(q)
    assert list(el["book"]) == ["draftkings"]


def test_the_decision_is_the_first_eligible_fetch_in_the_phase():
    q = pd.DataFrame([quote(fetch=0, book="draftkings"), quote(fetch=0, book="fanduel"),
                      quote(fetch=1, book="draftkings"), quote(fetch=1, book="betmgm")])
    q["ev"] = [0.01, 0.02, 0.30, 0.40]          # the later fetch looks better; it is never used
    d = G.decision_quotes(G.eligible(q))
    assert sorted(d["book"]) == ["draftkings", "fanduel"]
    assert (d["fetch_at"] == T0).all()


def test_q4_needs_six_minutes_and_halftime_is_not_a_phase():
    q = pd.DataFrame([quote(period=4, clock=360.0), quote(period=4, clock=359.0),
                      quote(period=2, phase="halftime", clock=0.0), quote(period=1, phase="break", clock=0.0),
                      quote(period=3, phase="break", clock=0.0)])
    assert list(G.phase_label(q)) == ["Q4", "", "", "Q1-Q2", "Q3"]


def _train(seasons, n=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        f = rng.uniform(0.125, 1.0, n)
        mu = rng.normal(0, 6, n)
        m = rng.normal(0, 8, n)
        fm = m + f * mu + rng.normal(0, 12 * np.sqrt(f))
        rows.append(pd.DataFrame({"season": s, "f": f, "m": m, "mu_pre": mu, "final_margin": fm}))
    t = pd.concat(rows, ignore_index=True)
    t["x_mu_pre"], t["x_f"], t["x_m"], t["x_mf"] = t["f"] * t["mu_pre"], t["f"], t["m"], t["m"] * t["f"]
    for c in G.FOULS:
        t[c] = 0.0
    return t


def test_a_model_for_season_s_refuses_season_s_and_later():
    t = _train([2022, 2023])
    with pytest.raises(ValueError):
        G.StateModel().fit(t, 2023)
    with pytest.raises(ValueError):
        G.StateModel().fit(t, 2022, allow_own_season=True)
    m = G.StateModel(G.CORE).fit(t[t["season"] == 2022], 2023)
    assert m.n_train == 400 and abs(m.beta[0] - 1.0) < 0.35          # the prior's drift is learnt
    assert 80 < m.s1 < 220                                             # Stern's variance, 12^2 = 144


def test_models_by_season_fits_each_season_on_earlier_seasons_only():
    t = _train([2021, 2022, 2023])
    ms = G.models_by_season(t, G.CORE, seasons=(2021, 2022, 2023))
    assert ms[2021].n_train == 400 and ms[2022].n_train == 400 and ms[2023].n_train == 800


def test_with_no_time_left_the_leader_wins():
    m = G.StateModel(G.CORE)
    m.beta, m.s1, m.s0 = np.zeros(4), 144.0, G.S0_FLOOR
    df = pd.DataFrame({"m": [3.0, -3.0], "f": [0.0, 0.0], "x_mu_pre": 0.0, "x_f": 0.0, "x_m": [3.0, -3.0],
                       "x_mf": 0.0})
    p = m.p_home(df)
    assert p[0] > 0.999 and p[1] < 0.001


def test_a_five_point_home_margin_favours_home_minus_three_and_a_half():
    off = pd.DataFrame({"game_id": "G", "market": "spreads", "side": ["home", "away"], "line": -3.5,
                        "price": -110.0, "book": "draftkings"})
    c = G.priced(off, mean=np.array([5.0, 5.0]), sd=np.array([6.0, 6.0]), p_home=np.array([np.nan, np.nan]))
    assert c.loc[0, "p_win"] > 0.5 > c.loc[1, "p_win"]
    assert c.loc[0, "ev"] > 0 > c.loc[1, "ev"]
    # ... but not home -7.5: a 5-point margin does not cover 7.5
    c = G.priced(off.assign(line=-7.5), mean=np.array([5.0, 5.0]), sd=np.array([6.0, 6.0]),
                 p_home=np.array([np.nan, np.nan]))
    assert c.loc[0, "p_win"] < 0.5 < c.loc[1, "p_win"]


def _state(**kw):
    base = {"secs_left": 1000.0, "clock_s": 360.0, "period": 3.0, "h_pts": 50.0, "a_pts": 50.0, "mu_pre": 0.0,
            "h_tf_period": 2.0, "a_tf_period": 2.0}
    for side in "ha":
        for k in (1, 2, 3):
            base[f"{side}_top{k}_pf"] = 1.0
    base.update(kw)
    return pd.DataFrame([base])


def test_foul_inputs_point_toward_the_team_that_benefits():
    x = G.features(_state(a_tf_period=5.0))
    assert x["x_pen"].iloc[0] > 0 and x["x_tf"].iloc[0] > 0
    x = G.features(_state(h_tf_period=6.0))
    assert x["x_pen"].iloc[0] < 0
    x = G.features(_state(a_top1_pf=4.0))           # 4 fouls in Q3: trouble (>= period + 1)
    assert x["x_trouble"].iloc[0] > 0 and x["x_top"].iloc[0] > 0
    x = G.features(_state(a_top1_pf=3.0))           # 3 in Q3 is not yet trouble
    assert x["x_trouble"].iloc[0] == 0
    x = G.features(_state(h_top2_pf=6.0))
    assert x["x_out"].iloc[0] < 0


def _info_rows(informative: bool, seed=5, days=150, per_day=8):
    rng = np.random.default_rng(seed)
    rows = []
    for s in (2021, 2022, 2023, 2024, 2025, 2026):
        n = days * per_day
        z = rng.normal(0, 1.2, n)              # what the market knows
        h = rng.normal(0, 0.8, n)              # what only an informed model knows
        y = (rng.random(n) < 1 / (1 + np.exp(-(z + h)))).astype(float)
        model = z + h if informative else z + rng.normal(0, 0.8, n)
        rows.append(pd.DataFrame({"season": s, "game_date": np.repeat([f"{s}-{d}" for d in range(days)], per_day),
                                  "game_id": np.arange(n), "y": y, "bench_logit": z, "model_logit": model}))
    return pd.concat(rows, ignore_index=True)


def _gate(rows):
    per = pd.concat([G.stacked_losses(rows, "ll", "bench_logit", "model_logit", S) for S in G.GRADED])
    ch = G.delta_ci(per[per["season"].isin((2022, 2023, 2024, 2025))])
    cf = G.delta_ci(per[per["season"] == 2026])
    return ch, cf


def test_an_informed_model_lowers_log_loss_and_passes_the_gate():
    ch, cf = _gate(_info_rows(True))
    assert ch["hi"] < 0 and cf["hi"] < 0
    assert G.has_information(ch, cf)


def test_a_model_with_no_new_information_does_not_pass_the_gate():
    ch, cf = _gate(_info_rows(False))
    assert ch["lo"] < 0 < ch["hi"] or ch["lo"] > 0
    assert not G.has_information(ch, cf)


def test_the_gate_needs_both_intervals_below_zero():
    assert not G.has_information({"hi": -0.01}, {"hi": 0.001})
    assert not G.has_information({"hi": 0.001}, {"hi": -0.01})
    assert G.has_information({"hi": -0.001}, {"hi": -0.002})


def test_the_side_the_model_favours_is_the_higher_ev_side():
    c = pd.DataFrame({"game_id": "G", "market": "h2h", "book": ["draftkings", "fanduel", "draftkings", "pinnacle"],
                      "side": ["home", "home", "away", "away"], "ev": [-0.05, -0.02, 0.03, 0.20]})
    s = G.with_side_pick(c)
    assert (s["side_pick"] == "away").all()   # Pinnacle's 0.20 is not a deciding offer; 0.03 still wins
    c.loc[2, "ev"] = -0.04
    assert (G.with_side_pick(c)["side_pick"] == "home").all()


def test_the_training_grid_takes_the_latest_play_at_or_before_each_game_time():
    tl = pd.DataFrame({"game_id": "G", "wc": pd.to_datetime(["2025-01-01T00:00:00Z"] * 5),
                       "play_no": [1, 2, 3, 4, 5], "period": [1.0, 1.0, 1.0, 1.0, 4.0],
                       "clock_s": [700.0, 650.0, 645.0, 520.0, 300.0],
                       "game_s": [20.0, 70.0, 75.0, 200.0, 2580.0],
                       "h_pts": [0, 2, 4, 9, 90], "a_pts": [0, 0, 3, 5, 88]})
    st = G.grid_states(tl, step=30, secs=(360, 2850))
    by = st.set_index("play_no")
    # play 1 leaves 2,860 s (above 2,850); play 2 is never the latest play at a
    # grid time (play 3 follows it before 90 s); play 5 sits at 5:00 of Q4
    assert set(by.index) == {3, 4}
    assert by.loc[3, "secs_left"] == 645 + 720 * 3
    assert by.loc[4, "h_pts"] == 9
