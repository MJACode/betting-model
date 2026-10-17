"""IG-1, live totals after in-game shooting luck (scripts/nba_ingame_ig1.py,
docs/nba_models_2026.md 7.2 and the lab's reading of it), on synthetic rows.

Pinned: luck counts a three three times and a free throw once, against the
team's own rates from EARLIER dates; missed heaves count as attempts only
before 2025-26; a quote is eligible only from a deciding book, fresh, with a
fresh Pinnacle quote; the window comes from each quote's own stamp; only the
first purchase in a window decides; the luck state is read at the earliest
stamp involved; every fit for season S uses earlier seasons only; the
information statistic is below zero when the model carries information and
zero when it adds nothing; the control is the opposite signal; the gate
closes on an interval that reaches zero."""
from __future__ import annotations

import numpy as np
import pandas as pd

from scripts import nba_ingame_ig1 as G

UTC = "UTC"


def _state(**kw):
    base = {"season": 2025, "h_fg3m": 0, "h_fg3a": 0, "h_heave3": 0, "h_ftm": 0, "h_fta": 0,
            "a_fg3m": 0, "a_fg3a": 0, "a_heave3": 0, "a_ftm": 0, "a_fta": 0,
            "h_e3": 0.35, "h_eft": 0.8, "a_e3": 0.35, "a_eft": 0.8}
    base.update(kw)
    return pd.DataFrame([base])


def test_luck_counts_a_three_three_times_and_a_free_throw_once():
    # home 5 of 10 threes at 35% expected: 3 x (5 - 3.5) = 4.5; away 6 of 10 free
    # throws at 80% expected: 6 - 8 = -2
    s = _state(h_fg3m=5, h_fg3a=10, a_ftm=6, a_fta=10)
    assert np.isclose(G.luck_points(s).iloc[0], 4.5 - 2.0)


def test_missed_heaves_count_as_attempts_before_2025_26_only():
    old = _state(season=2025, h_fg3m=5, h_fg3a=10, h_heave3=2)
    new = _state(season=2026, h_fg3m=5, h_fg3a=10, h_heave3=2)
    assert np.isclose(G.luck_points(old).iloc[0], 3 * (5 - 12 * 0.35))
    assert np.isclose(G.luck_points(new).iloc[0], 3 * (5 - 10 * 0.35))


def test_expected_rates_use_the_teams_earlier_dates_only():
    games = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "season": 2024,
                          "game_date": ["2024-01-01", "2024-01-03", "2024-01-05"],
                          "home_team": ["AAA"] * 3, "away_team": ["BBB"] * 3})
    box = pd.DataFrame({"game_id": ["g1", "g2", "g3"], "team": ["AAA"] * 3,
                        "fg3_made": [1, 9, 0], "fg3_att": [10, 10, 10],
                        "ft_made": [5, 10, 0], "ft_att": [10, 10, 10]})
    r = G.team_rates(box, games).set_index("game_date")
    assert r.loc["2024-01-01", "n"] == 0 and np.isnan(r.loc["2024-01-01", "e3"])
    assert np.isclose(r.loc["2024-01-03", "e3"], 0.1)          # g1 only
    assert np.isclose(r.loc["2024-01-05", "e3"], 0.5)          # g1 + g2, never g3
    assert np.isclose(r.loc["2024-01-05", "eft"], 0.75)


def _q(rows):
    t0 = pd.Timestamp("2024-01-01T01:00:00", tz=UTC)
    base = {"game_id": "G", "season": 2024, "game_date": "2024-01-01", "market": "totals",
            "book": "draftkings", "coherent": True, "pin_fa": 0.5, "fa": 0.5, "line": 220.5,
            "pin_line": 220.5, "pts_since_stamp": 0.0, "period": 2.0, "phase": "live",
            "clock_s": 300.0, "secs_left": 1740.0, "price_a": -110.0, "price_b": -110.0,
            "final_home": 110.0, "final_away": 108.0,
            **{c: 0.0 for c in G.STATE if c not in ("period", "clock_s", "secs_left")}}
    out = []
    for r in rows:
        x = {**base, **r}
        x["fetch_at"] = t0 + pd.Timedelta(minutes=x.pop("fetch_min", 0))
        x["stamp"] = t0 + pd.Timedelta(seconds=x.pop("stamp_s", -300))
        x["pin_stamp"] = t0 + pd.Timedelta(seconds=x.pop("pin_s", -300))
        x["served_at"] = x["fetch_at"] - pd.Timedelta(seconds=264)
        out.append(x)
    return pd.DataFrame(out)


def _pin(**kw):
    return {"book": "pinnacle", **kw}


def test_only_fresh_deciding_quotes_with_a_fresh_pinnacle_quote_are_eligible():
    q = _q([
        _pin(stamp_s=-300, pin_s=-300),                                   # Pinnacle, fresh
        {"book": "draftkings"},                                           # kept
        {"book": "fanduel", "pts_since_stamp": 2.0},                      # a point since its stamp
        {"book": "bovada"},                                               # never a deciding book
        {"book": "betmgm", "coherent": False},                            # incoherent
        {"book": "betrivers", "pin_fa": np.nan},                          # no coherent Pinnacle
        {"book": "williamhill_us", "market": "spreads"},                  # not a total
        _pin(game_id="H", stamp_s=-300, pin_s=-300, pts_since_stamp=1.0),  # Pinnacle not fresh
        {"book": "draftkings", "game_id": "H"},                           # its Pinnacle is stale
    ])
    el = G.eligible(q)
    assert list(el["book"]) == ["draftkings"] and list(el["game_id"]) == ["G"]


def test_the_window_comes_from_each_quotes_own_stamp():
    q = _q([
        _pin(stamp_s=-300, pin_s=-300),
        {"book": "draftkings", "period": 2.0, "phase": "live"},
        {"book": "fanduel", "period": 2.0, "phase": "halftime", "clock_s": 0.0},
        {"book": "betmgm", "period": 3.0, "phase": "live"},
        {"book": "betrivers", "period": 1.0, "phase": "live"},           # Q1: no IG-1 window
    ])
    el = G.eligible(q).set_index("book")["window"].to_dict()
    assert el == {"draftkings": "Q2", "fanduel": "halftime", "betmgm": "Q3"}


def test_only_the_first_purchase_in_a_window_decides():
    q = _q([
        _pin(stamp_s=-300, pin_s=-300),
        {"book": "draftkings", "fetch_min": 0},
        _pin(fetch_min=60, stamp_s=3300, pin_s=3300),
        {"book": "draftkings", "fetch_min": 60, "stamp_s": 3300, "pin_s": 3300},
        {"book": "fanduel", "fetch_min": 60, "stamp_s": 3300, "pin_s": 3300},
    ])
    d = G.decisions(G.eligible(q))
    assert len(d) == 1 and d["fetch_at"].iloc[0] == q["fetch_at"].min()


def test_the_luck_state_is_read_at_the_earliest_stamp_involved():
    # the Pinnacle quote is stamped 40 s before the offer; one more three-point
    # miss happened in between, so the state must be Pinnacle's
    q = _q([
        _pin(stamp_s=-340, pin_s=-340, h_fg3a=4.0),
        {"book": "draftkings", "stamp_s": -300, "pin_s": -340, "h_fg3a": 5.0},
    ])
    d = G.decisions(G.eligible(q))
    st = G.state_at_t0(d, q)
    assert len(st) == 1 and st["h_fg3a"].iloc[0] == 4.0


def _rows(seed: int, info: float, n_per: int = 400, seasons=(2021, 2022, 2023)):
    """Info-test rows: the final total = Pinnacle's mu + info x (luck-implied
    shift) + noise. info = 0: Pinnacle already has everything."""
    rng = np.random.default_rng(seed)
    out = []
    for s in seasons:
        for w, sl in (("Q2", 2000.0), ("halftime", 1440.0), ("Q3", 1000.0)):
            L = rng.normal(0, 8, n_per)
            P = rng.normal(110, 8, n_per)
            C = np.full(n_per, 225.0)
            f = sl / G.GAME_S
            mu = P + C * f
            y = mu - info * L * f / (1 - f) + rng.normal(0, 10, n_per)
            out.append(pd.DataFrame({"game_id": [f"{s}{w}{i}" for i in range(n_per)], "season": s,
                                     "game_date": [f"{s}-{i % 120:03d}" for i in range(n_per)],
                                     "window": w, "secs_left": sl, "h_pts": P / 2, "a_pts": P / 2,
                                     "C": C, "L": L, "mu": mu, "final_home": np.floor(y / 2),
                                     "final_away": y - np.floor(y / 2)}))
    return pd.concat(out, ignore_index=True)


def test_the_statistic_is_below_zero_when_the_model_carries_information():
    f = G.info_frame(_rows(1, info=0.8), seasons=[2022, 2023])
    r = G.mean_ci(f, "d_main", n_boot=500)
    assert r["hi"] < 0


def test_the_statistic_is_zero_when_the_model_adds_nothing():
    rows = _rows(2, info=0.8)
    rows["L"] = 0.0                       # no luck: M is Pinnacle's own mu plus a fitted shift of nothing
    rows["h_pts"] = rows["a_pts"] = (rows["mu"] - rows["C"] * rows["secs_left"] / G.GAME_S) / 2
    rows["C"] = (rows["h_pts"] + rows["a_pts"]) / (1 - rows["secs_left"] / G.GAME_S)
    rows["mu"] = rows["h_pts"] + rows["a_pts"] + rows["C"] * rows["secs_left"] / G.GAME_S
    f = G.info_frame(rows, seasons=[2022, 2023])
    assert np.allclose(f["d_main"], 0.0, atol=1e-6)


def test_every_fit_for_season_s_uses_earlier_seasons_only():
    rows = _rows(3, info=0.5)
    f1 = G.info_frame(rows, seasons=[2022, 2023])
    changed = rows.copy()
    m = changed["season"] == 2023
    changed.loc[m, "final_home"] = changed.loc[m, "final_home"] + 40      # 2023's results only
    f2 = G.info_frame(changed, seasons=[2022, 2023])
    k = ["w_full", "w_raw", "b_main", "b_raw", "b_luck"]
    a, b = f1[f1["season"] == 2023], f2[f2["season"] == 2023]
    assert np.allclose(a[k].to_numpy(), b[k].to_numpy())                 # 2023's fit never saw 2023
    a, b = f1[f1["season"] == 2022], f2[f2["season"] == 2022]
    assert np.allclose(a[k + ["d_main"]].to_numpy(), b[k + ["d_main"]].to_numpy())


def test_ig1_bets_against_luck_and_the_control_with_it():
    st = pd.DataFrame({"game_id": ["G"], "window": ["Q2"], "L": [5.0]})
    off = pd.DataFrame({"game_id": ["G", "G"], "market": ["totals", "totals"], "side": ["over", "under"]})
    ig = G.side_strength(off, G.strength_frame(st, "Q2", control=False)).set_index("side")["strength"]
    ct = G.side_strength(off, G.strength_frame(st, "Q2", control=True)).set_index("side")["strength"]
    assert ig["under"] == 5.0 and ig["over"] == -5.0          # hot shooting: IG-1 takes the under
    assert ct["over"] == 5.0 and ct["under"] == -5.0


def test_the_gate_closes_on_an_interval_that_reaches_zero():
    assert G.gate_passes({"hi": -0.01})
    assert not G.gate_passes({"hi": 0.0})
    assert not G.gate_passes({"hi": 0.3})
    assert not G.gate_passes({"hi": np.nan})


def test_the_cell_count_is_24_plus_24():
    assert G.EXPECTED_ROWS == {"IG-1": 24, "control_ig1_persist": 24}
    assert G.CUTS == (2.0, 4.0, 6.0, 8.0) and G.WINDOWS == ("Q2", "halftime", "Q3")
