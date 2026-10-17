"""The NBA totals overs model (`nba_total_luck`): every rule it ships on.

models/nba_total_luck.py holds the rule; scripts/nba_total_luck_card.py writes
it. Each test below names the rule it pins. The replay of the lab on the
research cache is tests/test_nba_total_luck_replay.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc


# ── helpers ──────────────────────────────────────────────────────────────────

def _et(y, m, d, hh, mm, ss=0):
    return datetime(y, m, d, hh, mm, ss, tzinfo=ET).astimezone(UTC)


def _season(n_games: int, opp_fg3m: int = 10, hot_fg3m: int = 18, start="2026-10-21",
            others: bool = False):
    """A synthetic season: HOM and AWY each play OT1/OT2 once a day.

    Against HOM and AWY the others make `opp_fg3m` of 40 threes; HOM and AWY
    make `hot_fg3m`. With 10 against 18 the league rate sits near 35% and
    HOM's and AWY's opponents shot 25%: their luck-adjusted defence is worse
    than the raw one, so the adjusted total is HIGHER (an over gap).
    `others` adds a daily OT3 vs OT4 game (neither team is HOM or AWY): it
    reaches the gap only through the league's averages."""
    games, box = [], []
    d0 = pd.Timestamp(start)
    pairs = (("HOM", "OT1"), ("OT2", "AWY")) + ((("OT3", "OT4"),) if others else ())
    for i in range(n_games):
        day = (d0 + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        for home, away in pairs:
            gid = f"NBA_{day}_{away}_{home}"
            games.append({"game_id": gid, "season": 2027, "game_date": day,
                          "home_team": home, "away_team": away,
                          # each team's final = its box points below
                          "home_score": 110 if home in ("HOM", "AWY") else 100,
                          "away_score": 110 if away in ("HOM", "AWY") else 100})
            for team in (home, away):
                ours = team in ("HOM", "AWY")
                box.append({"game_id": gid, "team": team, "points": 110 if ours else 100,
                            "fg_att": 88, "fg3_made": hot_fg3m if ours else opp_fg3m,
                            "fg3_att": 40, "ft_made": 16, "ft_att": 20,
                            "offensive_reb": 10, "turnovers": 13})
    return pd.DataFrame(games), pd.DataFrame(box)


def _target(day="2026-11-05"):
    return pd.DataFrame([{"game_id": f"NBA_{day}_AWY_HOM", "season": 2027, "game_date": day,
                          "home_team": "HOM", "away_team": "AWY"}])


def _rows(gid, fetch, quotes):
    """odds-table rows: (book, line, over, under) at one fetch."""
    out = []
    for book, line, over, under in quotes:
        out.append({"game_id": gid, "bookmaker": book, "market": "totals",
                    "snapshot_type": "open",
                    "snapshot_at": (fetch - timedelta(seconds=30)).isoformat(),
                    "created_at": fetch.isoformat(), "total_line": line,
                    "over_price": over, "under_price": under,
                    "over_link": f"https://{book}/over", "under_link": f"https://{book}/under"})
    return pd.DataFrame(out)


@pytest.fixture(scope="module")
def art():
    return tl.load_artifact()


def _decide(art, quotes, gap, tip=None, monkeypatch=None, **kw):
    """decide() on one target whose luck gap is forced to `gap` (the offer
    mechanics, independent of the ratings)."""
    t = _target()
    tip = tip or _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    games = t.assign(tip=pd.Timestamp(tip))
    q = tl.quote_frame(_rows(t.game_id[0], fetch, quotes), games)
    proj = t.assign(gap_total=gap, gap_margin=0.0)
    monkeypatch.setattr(tl, "f4_projections", lambda targets, tb: proj)
    monkeypatch.setattr(tl, "missing_inputs", lambda targets, *a: {
        g: {"score_missing": [], "box_missing": [], "box_mismatch": [], "presumed_unplayed": []}
        for g in targets["game_id"]})
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    empty = pd.DataFrame(columns=["game_id", "team", *tl.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team",
                                  "home_score", "away_score"])
    return tl.decide(t, q, empty, final, times, art, scheduled=final, **kw)


# ── the gap: one copy, shared with the lab ───────────────────────────────────

def test_the_lab_grades_the_very_functions_the_live_model_bets():
    """RULE: the live gap equals the lab's for the same inputs. Never two copies:
    the lab imports the live model's F4 functions."""
    from scripts import nba_game2_luck as L
    for name in ("team_box", "as_of_ratings", "f4_projections", "f4_signal", "side_strength",
                 "_before"):
        assert getattr(L, name) is getattr(tl, name), f"the lab has its own {name}"
    assert (L.MIN_GAMES, L.FTA_POSS, L.BOX_COLS) == (tl.MIN_GAMES, tl.FTA_POSS, tl.BOX_COLS)


def test_cold_opponent_threes_give_an_over_gap_and_hot_ones_an_under_gap():
    """RULE: the gap is luck-adjusted minus raw projected total; opponents who
    shot cold make the adjusted total higher."""
    games, box = _season(12)
    cold = tl.f4_projections(_target(), tl.team_box(box, games))["gap_total"].iloc[0]
    games, box = _season(12, opp_fg3m=18, hot_fg3m=10)
    hot = tl.f4_projections(_target(), tl.team_box(box, games))["gap_total"].iloc[0]
    assert cold >= tl.GAP_CUT and hot <= -tl.GAP_CUT, (cold, hot)


def test_the_gap_uses_only_games_before_the_game_date():
    """RULE: ratings from games final before the game's Eastern date only (an
    afternoon game that day is left out, as in the lab)."""
    games, box = _season(12)
    t = _target("2026-11-01")                    # the 12th day of the season
    base = tl.f4_projections(t, tl.team_box(box, games))["gap_total"].iloc[0]
    g2, b2 = _season(13)                         # adds games ON 2026-11-02
    same_day = g2[g2["game_date"] == "2026-11-02"].copy()
    same_day["game_date"] = "2026-11-01"
    b_same = b2[b2["game_id"].isin(same_day["game_id"])].copy()
    # a wild night that day: HOM's and AWY's opponents go 0 for 40 from three
    b_same.loc[b_same["team"].isin(["OT1", "OT2"]), "fg3_made"] = 0
    games2 = pd.concat([games, same_day], ignore_index=True)
    box2 = pd.concat([box, b_same], ignore_index=True)
    after = tl.f4_projections(t, tl.team_box(box2, games2))["gap_total"].iloc[0]
    assert after == pytest.approx(base)
    # and the same night one day EARLIER does move it (the check can see a change)
    earlier = same_day.assign(game_date="2026-10-31")
    moved = tl.f4_projections(t, tl.team_box(box2, pd.concat([games, earlier], ignore_index=True)))
    assert moved["gap_total"].iloc[0] != pytest.approx(base)


# ── the ten-game rule ────────────────────────────────────────────────────────

@pytest.mark.parametrize("n,priced", [(9, False), (10, True)])
def test_both_teams_need_ten_games(monkeypatch, art, n, priced):
    """RULE: CLAUDE.md section 3 -- no bet until both teams have played 10 games."""
    games, box = _season(n)
    day = (pd.Timestamp("2026-10-21") + pd.Timedelta(days=n)).strftime("%Y-%m-%d")
    t = _target(day)
    tip = _et(*map(int, day.split("-")), 19, 30)
    fetch = tip - timedelta(minutes=65)
    q = tl.quote_frame(_rows(t.game_id[0], fetch, [("pinnacle", 224.5, -105, -115),
                                                   ("draftkings", 224.5, -110, -110)]),
                       t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    bets, decisions, diag = tl.decide(t, q, box, games, times, art, scheduled=games)
    assert diag["early_season"] == (0 if priced else 1)
    assert (len(bets) == 1) is priced, (decisions, diag)


def test_a_missing_box_score_declines_the_game(art):
    """RULE: a final game with no box score would drop out of BOTH teams'
    ratings and move the gap silently; such a game is not priced."""
    games, box = _season(12)
    gone = games["game_id"].iloc[3]
    box = box[box["game_id"] != gone]
    t = _target()
    tip = _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    q = tl.quote_frame(_rows(t.game_id[0], fetch, [("draftkings", 224.5, -110, -110)]),
                       t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    bets, decisions, diag = tl.decide(t, q, box, games, times, art, scheduled=games)
    assert not bets and diag["box_missing"] == 1
    assert decisions[0].detail.startswith("box_missing")


# ── completeness: every game of the season before the date, not just the two
#    teams' (models/nba_total_luck.missing_inputs) ────────────────────────────

def _complete_case(games, box, scheduled, art, day="2026-11-05"):
    t = _target(day)
    tip = _et(*map(int, day.split("-")), 19, 30)
    fetch = tip - timedelta(minutes=65)
    q = tl.quote_frame(_rows(t.game_id[0], fetch, [("pinnacle", 224.5, -105, -115),
                                                   ("draftkings", 224.5, -110, -110)]),
                       t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    return tl.decide(t, q, box, games, times, art, scheduled=scheduled)


def test_a_missing_box_between_two_other_teams_declines_the_game(art):
    """RULE: the league's 3P%, FT% and points per 100 come from EVERY game
    before the date. A scored game between two other teams with no box drops
    out of them and moves the gap (the review measured 2.992 -> 3.008, a bet
    the lab never made), so it declines the game too."""
    games, box = _season(12, others=True)
    gone = games[games["home_team"] == "OT3"]["game_id"].iloc[4]
    short = box[box["game_id"] != gone]
    full = tl.f4_projections(_target(), tl.team_box(box, games))["gap_total"].iloc[0]
    moved = tl.f4_projections(_target(), tl.team_box(short, games))["gap_total"].iloc[0]
    assert moved != pytest.approx(full), "the case must move the gap, or it proves nothing"
    bets, decisions, diag = _complete_case(games, box, games, art)
    assert diag["box_missing"] == 0, "the intact season must not decline"
    bets, decisions, diag = _complete_case(games, short, games, art)
    assert not bets and diag["box_missing"] == 1, decisions
    assert decisions[0].detail.startswith(f"box_missing:1 ({gone})")


def test_a_previous_night_game_with_no_score_declines_the_game(art):
    """RULE: a game played before the date whose final has not landed in
    `games` is owed. The old check never saw it (it loaded only scored games):
    it dropped out of everything, the two teams' own ratings included."""
    games, box = _season(14, others=True)
    night = games[games["game_date"] == "2026-11-03"]
    final = games[~games["game_id"].isin(night["game_id"])]
    short = box[~box["game_id"].isin(night["game_id"])]
    bets, decisions, diag = _complete_case(games, box, games, art)
    assert diag["score_missing"] == 0 and diag["box_missing"] == 0
    bets, decisions, diag = _complete_case(final, short, games, art)
    assert not bets and diag["score_missing"] == 1, decisions
    assert decisions[0].detail.startswith(f"score_missing:{len(night)} (")


def test_a_postponed_game_is_not_owed(art):
    """A game ESPN (or stats.nba.com, "PPD") lists as postponed or cancelled was
    not played: the lab never had it, so it is not waited for."""
    games, box = _season(14, others=True)
    gone = games[games["game_date"] == "2026-11-03"]["game_id"].iloc[2]
    final = games[games["game_id"] != gone]
    short = box[box["game_id"] != gone]
    sched = games.assign(status_text=np.where(games["game_id"] == gone, "Postponed", "Final"))
    _, _, diag = _complete_case(final, short, sched, art)
    assert diag["score_missing"] == 0 and diag["box_missing"] == 0, diag
    _, _, diag = _complete_case(final, short, sched.assign(status_text="Final"), art)
    assert diag["score_missing"] == 1, "the same game, not marked postponed, is owed"


def test_a_game_unscored_for_two_weeks_is_presumed_unplayed_and_named(art):
    """A game still unscored UNPLAYED_AFTER_DAYS after its date is presumed not
    played (a postponement nothing recorded): it no longer blocks, but it is
    listed in diag['presumed_unplayed'] so the card logs it every pass."""
    games, box = _season(30, others=True)
    old = games[games["game_date"] == "2026-10-22"]["game_id"].iloc[2]
    recent = games[games["game_date"] == "2026-11-15"]["game_id"].iloc[2]
    for gone, blocks in ((old, False), (recent, True)):
        final = games[games["game_id"] != gone]
        short = box[box["game_id"] != gone]
        _, decisions, diag = _complete_case(final, short, games, art, day="2026-11-20")
        assert (diag["score_missing"] == 1) is blocks, (gone, diag)
        assert diag["presumed_unplayed"] == ([] if blocks else [gone]), diag


def test_a_placeholder_with_no_teams_is_not_a_game(art):
    """nba_schedule seeds the NBA Cup knockout slots before their teams are known
    (home and away 'NaN', 3 such ids in 2026-27, read 2026-10-17). They never
    get a score and must not block the model from December on."""
    games, box = _season(14, others=True)
    slot = pd.DataFrame([{"game_id": "NBA_2026-11-01_nan_nan", "season": 2027,
                          "game_date": "2026-11-01", "home_team": "NaN", "away_team": "NaN"}])
    _, _, diag = _complete_case(games, box, pd.concat([games, slot, slot]), art)
    assert diag["score_missing"] == 0, diag
    assert tl.scheduled_games(pd.concat([games, slot]))["game_id"].tolist() == \
        sorted(games["game_id"])


def test_the_schedule_is_a_required_input(art):
    """No default: a caller that forgot it would skip the check without a sound."""
    games, box = _season(12)
    with pytest.raises(TypeError):
        tl.decide(_target(), pd.DataFrame(), box, games, pd.DataFrame(), art)


def _SeasonConn(games, schedule, box):
    """load_season's reads answered from frames shaped like the production
    tables: the replay's own FrameConn, so the unit tests and the replay of the
    lab read through one copy."""
    from scripts.nba_total_luck_replay import FrameConn
    return FrameConn(games, schedule, box)


def _cup_world(n_days=50):
    """A season with every game listed in nba_schedule, plus what the live
    `games` table holds in December: a quarterfinal the schedule lists only as
    a placeholder, and the Cup final, which the schedule lists only as a
    'cup_final' placeholder. Both scored and boxed, the final from a wild
    night that moves the league's three-point rate."""
    games, box = _season(n_days, others=True)
    sched = games.assign(game_type="regular", status_text="Final")
    qf = {"game_id": "NBA_2026-12-04_OT3_OT1", "season": 2027, "game_date": "2026-12-04",
          "home_team": "OT1", "away_team": "OT3", "home_score": 100, "away_score": 100}
    final = {"game_id": "NBA_2026-12-11_OT4_OT2", "season": 2027, "game_date": "2026-12-11",
             "home_team": "OT2", "away_team": "OT4", "home_score": 100, "away_score": 100}
    holders = pd.DataFrame([
        {"game_id": "NBA_2026-12-04_nan_nan", "season": 2027, "game_date": "2026-12-04",
         "home_team": "NaN", "away_team": "NaN", "game_type": "regular", "status_text": "TBD"},
        {"game_id": "NBA_2026-12-11_nan_nan", "season": 2027, "game_date": "2026-12-11",
         "home_team": "NaN", "away_team": "NaN", "game_type": "cup_final", "status_text": "8:00 pm ET"},
        # the last regular-season day, so December is inside the season
        {"game_id": "NBA_2027-04-11_OT1_OT2", "season": 2027, "game_date": "2027-04-11",
         "home_team": "OT2", "away_team": "OT1", "game_type": "regular", "status_text": "8:00 pm ET"},
    ])
    extra_box = []
    for g, fg3 in ((qf, 12), (final, 30)):
        for team in (g["home_team"], g["away_team"]):
            extra_box.append({"game_id": g["game_id"], "team": team, "points": 100, "fg_att": 88,
                              "fg3_made": fg3, "fg3_att": 40, "ft_made": 16, "ft_att": 20,
                              "offensive_reb": 10, "turnovers": 13})
    all_games = pd.concat([games, pd.DataFrame([qf, final])], ignore_index=True)
    all_box = pd.concat([box, pd.DataFrame(extra_box)], ignore_index=True)
    return all_games, pd.concat([sched, holders], ignore_index=True), all_box


def test_the_cup_final_never_enters_the_ratings_and_a_quarterfinal_does():
    """RULE (the lab's population): regular-season games only. The Cup final
    is a `games` row the schedule cannot match (its row is a 'cup_final'
    placeholder with no teams), on a day with a non-regular schedule row: it is
    in neither the scored set nor the owed set. A quarterfinal, unlisted the
    same way but on a regular-season day, counts, as it did in the lab."""
    from scripts import nba_total_luck_card as card
    games, sched, box = _cup_world()
    final, bx, owed = card.load_season(_SeasonConn(games, sched, box), 2027, "2026-12-20")
    assert "NBA_2026-12-11_OT4_OT2" not in set(final["game_id"])
    assert "NBA_2026-12-11_OT4_OT2" not in set(owed["game_id"])
    assert "NBA_2026-12-11_OT4_OT2" not in set(bx["game_id"])
    assert "NBA_2026-12-04_OT3_OT1" in set(final["game_id"])
    assert "NBA_2026-12-04_OT3_OT1" in set(owed["game_id"])
    # and the final would have moved the gap: the case is not vacuous
    t = _target("2026-12-15")
    with_final = tl.f4_projections(t, tl.team_box(box, games))["gap_total"].iloc[0]
    without = tl.f4_projections(t, tl.team_box(bx, final))["gap_total"].iloc[0]
    assert with_final != pytest.approx(without)


@pytest.mark.parametrize("day,kind,counts", [
    ("2026-10-15", "preseason", False),    # before the first regular-season day
    ("2027-04-20", "playoff", False),      # after the last one
    ("2026-12-11", "cup_final", False),    # a day the schedule gives another kind of game
    ("2026-12-05", None, True),            # a regular-season day: a game added after the load
])
def test_an_unlisted_games_row_counts_only_on_a_regular_season_day(day, kind, counts):
    days = pd.DataFrame([
        {"season": 2027, "game_date": "2026-10-20", "game_type": "regular"},
        {"season": 2027, "game_date": "2027-04-11", "game_type": "regular"},
        {"season": 2027, "game_date": "2026-10-15", "game_type": "preseason"},
        {"season": 2027, "game_date": "2026-12-11", "game_type": "cup_final"},
    ])
    rows = pd.DataFrame([{"game_id": f"NBA_{day}_AAA_BBB", "season": 2027, "game_date": day,
                          "game_type": None}])
    assert (len(tl.regular_season(rows, days)) == 1) is counts, (day, kind)
    listed = rows.assign(game_type="regular")
    assert len(tl.regular_season(listed, days)) == 1, "a listed regular game always counts"
    other = rows.assign(game_type="cup_final")
    assert tl.regular_season(other, days).empty, "a listed non-regular game never counts"
    assert tl.regular_season(rows, days.iloc[0:0]).empty, "no schedule, nothing counts"


def test_the_slate_prices_an_unlisted_quarterfinal_and_skips_the_cup_final():
    """The slate applies the same rule: the lab bet Cup quarterfinals and
    semifinals; the final is not a regular-season game."""
    from scripts import nba_total_luck_card as card
    now = _et(2026, 12, 11, 18, 55)
    tip = _et(2026, 12, 11, 20, 0)
    qf_now, qf_tip = _et(2026, 12, 4, 18, 55), _et(2026, 12, 4, 20, 0)

    class C:
        def __init__(self, rows):
            self.rows = rows

        def execute(self, sql, params=None):
            q = " ".join(sql.split())
            if q.startswith("SELECT g.game_id, g.home_team"):
                out = self.rows
            elif q.startswith("SELECT DISTINCT season, game_date, game_type"):
                out = [(2027, "2026-10-20", "regular"), (2027, "2027-04-11", "regular"),
                       (2027, "2026-12-04", "regular"), (2027, "2026-12-11", "cup_final")]
            else:
                raise AssertionError(q[:60])
            return type("R", (), {"fetchall": lambda self_: list(out)})()

    skipped = []
    got = card.slate(C([("NBA_2026-12-11_OT4_OT2", "OT2", "OT4", "2026-12-11", 2027,
                         tip.isoformat(), None, None)]), now, skipped)
    assert got == {} and skipped and "NBA_2026-12-11_OT4_OT2" in skipped[0]
    got = card.slate(C([("NBA_2026-12-04_OT3_OT1", "OT1", "OT3", "2026-12-04", 2027,
                         qf_tip.isoformat(), None, None)]), qf_now)
    assert list(got) == ["NBA_2026-12-04_OT3_OT1"]


def test_the_card_owes_every_scheduled_game_and_every_unlisted_regular_season_game():
    """load_season's owed set: nba_schedule's regular-season rows (scored or
    not) plus the `games` rows the schedule does not list on a regular-season
    day (games added after the schedule was loaded)."""
    from scripts import nba_total_luck_card as card
    games, sched, box = _cup_world()
    unscored = sched[sched["game_date"] == "2026-11-01"]["game_id"].iloc[0]
    games = games[games["game_id"] != unscored]
    final, _, owed = card.load_season(_SeasonConn(games, sched, box), 2027, "2026-12-20")
    assert unscored in set(owed["game_id"]) and unscored not in set(final["game_id"])
    assert {"home_score", "away_score"} <= set(final.columns)
    assert tl.scheduled_games(owed)["game_id"].is_unique


def test_a_box_that_does_not_add_up_to_the_final_declines_the_game(art):
    """RULE (box integrity): each team's box points must equal its final score.
    A player-game stored twice (an 'espn:<id>' fallback row and a later
    NBA.com row) adds his line twice to the team's possessions and ratings and
    to the league's rates; both teams' rows are present, so only the sum shows
    it. The lab's box added up on 19,038 of 19,038 team-games."""
    games, box = _season(14, others=True)
    gid = games[games["home_team"] == "OT3"]["game_id"].iloc[2]
    dup = box[(box["game_id"] == gid) & (box["team"] == "OT3")].assign(points=0, fg_att=20)
    doubled = pd.concat([box, dup.assign(points=12)], ignore_index=True)
    _, _, diag = _complete_case(games, box, games, art)
    assert diag["box_mismatch"] == 0, "an intact season must not decline"
    bets, decisions, diag = _complete_case(games, doubled, games, art)
    assert not bets and diag["box_mismatch"] == 1, decisions
    assert decisions[0].detail.startswith(f"box_mismatch:1 ({gid})")
    short = box.copy()
    short.loc[(short["game_id"] == gid) & (short["team"] == "OT4"), "points"] -= 9
    _, decisions, diag = _complete_case(games, short, games, art)
    assert diag["box_mismatch"] == 1, "a short box declines too"


def test_the_box_check_needs_the_scores():
    games, box = _season(12)
    with pytest.raises(ValueError, match="home_score"):
        tl.missing_inputs(_target(), tl.scheduled_games(games),
                          games.drop(columns=["home_score", "away_score"]),
                          tl.team_box(box, games))


# ── the offer: exactly the harness's choice ──────────────────────────────────

def test_the_offer_is_the_best_ev_under_the_market_fair_line(monkeypatch, art):
    """RULE: the over at the deciding book with the highest EV under the
    market's fair line (Pinnacle's no-vig through the empirical distribution).
    Same number, the best price wins; a better number can beat a better price."""
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -110, -110),
         ("fanduel", 224.5, -105, -115), ("betmgm", 225.5, +100, -120),
         ("williamhill_us", 223.5, -118, -102)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert len(bets) == 1
    b = bets[0]
    # the harness's own ranking of the same offers
    sig = {(2027, "totals"): tl.pricing_dist(art, 2027)}
    t = _target()
    tip = _et(2026, 11, 5, 19, 30)
    fetch = tip - timedelta(minutes=65)
    frame = tl.quote_frame(_rows(t.game_id[0], fetch, q), t.assign(tip=pd.Timestamp(tip)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    vis = H.visible(frame, times)
    neutral = H.fair_offers(H.offers(vis), H.market_fair(vis, sig))
    overs = neutral[(neutral["side"] == "over") & neutral["book"].isin(config.BEST_LINE_BOOKMAKERS)]
    best = overs.sort_values("ev", ascending=False).iloc[0]
    assert (b.book, b.line, b.price) == (best["book"], best["line"], best["price"])
    assert b.fair_ref == "pinnacle"
    assert b.ev_fair == pytest.approx(float(best["ev"]))
    assert b.ev_fair >= overs["ev"].max() - 1e-12


def test_a_tie_goes_to_the_earlier_book(monkeypatch, art):
    """RULE: equal EV -> the earlier book in config.BEST_LINE_BOOKMAKERS."""
    q = [("pinnacle", 224.5, -105, -115), ("betrivers", 224.5, -105, -115),
         ("fanduel", 224.5, -105, -115)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    order = config.BEST_LINE_BOOKMAKERS
    assert order.index("fanduel") < order.index("betrivers")
    assert bets[0].book == "fanduel"


def test_without_pinnacle_the_fair_line_is_the_deciding_books_median(monkeypatch, art):
    q = [("draftkings", 224.5, -110, -110), ("fanduel", 225.5, -105, -115),
         ("betmgm", 224.5, -105, -115)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets and bets[0].fair_ref == "consensus"


def test_pinnacle_and_bovada_are_never_the_book_taken(monkeypatch, art):
    q = [("pinnacle", 224.5, +120, -140), ("bovada", 220.5, +150, -180),
         ("draftkings", 224.5, -110, -110)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets[0].book == "draftkings"


# ── the price floor ──────────────────────────────────────────────────────────

def test_an_over_under_minus_200_is_never_taken_even_when_the_platform_floor_moves(
        monkeypatch, art):
    """RULE: -200 or better (config.min_odds_for, pinned in MODEL_MIN_ODDS),
    even when a Railway DEFAULT_MIN_ODDS override moves the harness's own
    import-time floor."""
    assert config.min_odds_for(tl.MODEL_ID) == -200
    monkeypatch.setattr(H, "PRICE_FLOOR", -1000.0)
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 219.5, -210, +170),
         ("fanduel", 224.5, -110, -110)]
    bets, _, _ = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)
    assert bets and bets[0].book == "fanduel" and bets[0].price >= -200
    only = [("pinnacle", 224.5, -105, -115), ("draftkings", 219.5, -210, +170)]
    bets, decisions, _ = _decide(art, only, gap=4.0, monkeypatch=monkeypatch)
    assert not bets and decisions[0].detail == "no_offer"


# ── overs only, and the cut ──────────────────────────────────────────────────

@pytest.mark.parametrize("gap", [-6.0, -3.0, 2.99])
def test_no_bet_below_the_cut_and_never_an_under(monkeypatch, art, gap):
    """RULE: bet the over when gap >= 3; an under gap is never bet (the
    unders were mixed), and no side is taken under the cut."""
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, +110, -130),
         ("fanduel", 224.5, -130, +110)]
    bets, decisions, _ = _decide(art, q, gap=gap, monkeypatch=monkeypatch)
    assert bets == [] and decisions[0].detail.startswith("gap_below_cut")


def test_an_under_gap_never_bets_the_under_even_at_a_great_price(monkeypatch, art):
    """RULE: overs only. A gap of -6 favours the under by 6; the rule still
    bets nothing, however good the under's price."""
    q = [("pinnacle", 224.5, -105, -115), ("fanduel", 224.5, -150, +130)]
    for gap in (-6.0, 6.0):
        bets, _, _ = _decide(art, q, gap=gap, monkeypatch=monkeypatch)
        assert all(b.line == 224.5 and b.price == -150 for b in bets), bets
        assert (len(bets) == 1) is (gap > 0)


def test_at_the_cut_the_bet_is_the_over(monkeypatch, art):
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -130, +110)]
    bets, _, _ = _decide(art, q, gap=3.0, monkeypatch=monkeypatch)
    assert len(bets) == 1 and bets[0].book == "draftkings" and bets[0].price == -130


# ── the probability ──────────────────────────────────────────────────────────

def test_the_probability_is_market_fair_plus_the_walk_forward_uplift(monkeypatch, art):
    """RULE: model_probability = the market-fair P(over) at the line + the
    gap >= 3 bucket's uplift fitted on the seasons before the live one
    (2021-22..2025-26 for 2026-27: 290 wins in 508 bets against a mean fair
    0.5050)."""
    up = tl.uplift(art, 2027)
    assert up == pytest.approx((290 - sum(v["sum_p_win"] for v in art["bucket"].values())) / 508)
    assert up == pytest.approx(0.0659, abs=5e-4)
    assert tl.uplift(art, 2026) == pytest.approx(0.0679, abs=5e-4)    # fitted on 2022-2025
    q = [("pinnacle", 224.5, -105, -115), ("draftkings", 224.5, -110, -110)]
    b = _decide(art, q, gap=4.0, monkeypatch=monkeypatch)[0][0]
    assert b.p_model == pytest.approx(b.p_fair + up)
    assert b.uplift == pytest.approx(up)


def test_the_artifact_prices_each_season_from_the_seasons_before_it(art):
    """RULE: the empirical totals distribution for season S uses the
    residuals of seasons before S only (the lab's close_dist)."""
    assert tl.newest_season(art) == 2026
    r = tl.residual_frame(art)
    assert tl.pricing_dist(art, 2027).n == int((r["season"] < 2027).sum())
    assert tl.pricing_dist(art, 2026).n == int((r["season"] < 2026).sum())


def test_the_ev_floor_is_not_a_second_cut():
    """RULE (CLAUDE.md 1b): the model carries its own EV floor, and it is not a
    second cut. The EV the floor reads refunds a push (the gate's p_push). On
    the 508 graded bets at the 2026-27 uplift that EV is +0.011 at the
    smallest, +0.038 next, +0.100 at the median, so 0.00 removes none."""
    floor = config.min_ev_for(tl.MODEL_ID)
    assert floor == 0.0 and floor < 0.011
    assert tl.MODEL_ID in config.MODEL_OWN_EV_FLOOR
    assert config.ACTION_THRESHOLDS[tl.MODEL_ID]["min_edge"] <= floor
    assert config.ACTION_THRESHOLDS[tl.MODEL_ID]["min_prob"] == 0.0
    assert tl.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.scoring_method(tl.MODEL_ID) == "rule"


# ── timing: a fetch 60-66 minutes before tip, from the window job ───────────

def _window_job(monkeypatch):
    # The scheduler-reading helpers of the NBA prop window job's tests, shared.
    from tests.test_nba_prop_window import _jobs
    return _jobs(monkeypatch)["nba_total_luck_window"]


def _fires(job, start, end):
    from tests.test_nba_prop_window import _fires as fires
    return fires(job, start, end)


def test_the_window_holds_at_least_two_of_the_job_s_ticks(monkeypatch):
    """RULE: one skipped tick cannot lose a game. The window the job fetches
    in is at least two of its ticks wide, it sits inside the card's decision
    window, and its bottom leaves a minute for the fetch to land."""
    from scripts import nba_total_luck_window as win
    job = _window_job(monkeypatch)
    day = _et(2026, 11, 5, 0, 0)
    fires = _fires(job, day, day + timedelta(hours=24) - timedelta(seconds=1))
    gaps = {(b - a).total_seconds() / 60 for a, b in zip(fires, fires[1:])}
    cadence = max(gaps)
    assert len(fires) == 1440 and cadence == 1.0, "every minute, around the clock"
    lo, hi = win.LOOK_AHEAD_MIN
    assert hi - lo >= 2 * cadence
    assert lo >= tl.DECISION_LEAD_MIN[0] + 1 and hi <= tl.DECISION_LEAD_MIN[1]


def _simulate(tip, ticks, skip=(), lag_s=10):
    """The window job's ticks: plan (the game is in LOOK_AHEAD_MIN), fetch
    (rows land `lag_s` later), card (timing on that fetch). -> the lead of the
    fetch that decided, or None."""
    from scripts import nba_total_luck_window as win
    lo, hi = win.LOOK_AHEAD_MIN
    for i, t in enumerate(ticks):
        if i in skip or not lo <= tl.lead_minutes(tip, t) <= hi:
            continue
        fetch = t + timedelta(seconds=lag_s)
        if tl.timing(tip, fetch, fetch + timedelta(seconds=20)) == "decide":
            return tl.lead_minutes(tip, fetch)
    return None


@pytest.mark.parametrize("hh,mm", [(12, 0), (13, 0), (15, 30), (17, 0), (18, 0), (19, 0),
                                   (19, 30), (20, 0), (21, 30), (22, 0), (22, 10), (22, 30)])
def test_every_tip_is_decided_on_a_fetch_60_to_66_minutes_out(monkeypatch, hh, mm):
    """RULE (decision point C, 60-180 minutes): every tip time, afternoon or
    evening, is decided by the first window tick, on a fetch 60-66 minutes out;
    with that tick skipped, the next one decides; with every tick in the
    window skipped, nothing is decided (and the card logs it)."""
    tip = _et(2026, 11, 5, hh, mm)
    ticks = _fires(_window_job(monkeypatch), tip - timedelta(minutes=200), tip)
    first = _simulate(tip, ticks)
    assert first is not None and 60 <= first < 66, first
    in_window = [i for i, t in enumerate(ticks) if 61 <= tl.lead_minutes(tip, t) <= 66]
    assert len(in_window) >= 2
    second = _simulate(tip, ticks, skip={in_window[0]})
    assert second is not None and 60 <= second < first, (first, second)
    assert _simulate(tip, ticks, skip=set(in_window)) is None


def test_the_card_decides_only_on_a_fresh_fetch_60_to_66_minutes_out():
    tip = _et(2026, 11, 5, 19, 30)
    assert tl.timing(tip, _et(2026, 11, 5, 18, 24, 10), _et(2026, 11, 5, 18, 24, 30)) == "decide"
    assert tl.timing(tip, _et(2026, 11, 5, 18, 29, 50), _et(2026, 11, 5, 18, 30)) == "decide"
    # a refresh pass's fetch 70 minutes out: the window job fetches later
    assert tl.timing(tip, _et(2026, 11, 5, 18, 20, 10), _et(2026, 11, 5, 18, 21)) == "too_early"
    # rows that landed 59.8 minutes out are past C
    assert tl.timing(tip, _et(2026, 11, 5, 18, 30, 10), _et(2026, 11, 5, 18, 31)) == "too_late"
    # the newest fetch is 6 minutes old: this tick's fetch failed, the next tries again
    assert tl.timing(tip, _et(2026, 11, 5, 18, 24, 10), _et(2026, 11, 5, 18, 30, 11)) == "stale_fetch"


# ── the card: decided once, under the lock ───────────────────────────────────

class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return list(self._rows)

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """Answers the card's reads; records its writes."""

    def __init__(self, decided=(), bet=(), ledger_table=True):
        self.decided, self.bet, self.ledger_table = set(decided), set(bet), ledger_table
        self.sql, self.ledger, self.picks, self.commits = [], [], [], 0

    def execute(self, sql, params=None):
        self.sql.append(sql)
        if "information_schema.tables" in sql:
            return _Cur([(1,)] if self.ledger_table else [])
        if "FROM nba_total_luck_decisions" in sql:
            return _Cur([(g,) for g in self.decided])
        if "FROM picks" in sql:
            return _Cur([(g,) for g in self.bet])
        if sql.startswith("INSERT INTO nba_total_luck_decisions"):
            if params["game_id"] in self.decided:
                return _Cur([])
            self.decided.add(params["game_id"])
            self.ledger.append(params)
            return _Cur([(params["game_id"],)])
        if sql.startswith("INSERT INTO picks"):
            self.picks.append(params)
            return _Cur([(len(self.picks),)])
        return _Cur([])

    def commit(self):
        self.commits += 1


def _bet(gid="NBA_2026-11-05_AWY_HOM", price=-110.0, p_fair=0.50, book="fanduel", dk=-110.0):
    return tl.TotalLuckBet(game_id=gid, season=2027, line=224.5, price=price, book=book, gap=4.2,
                           p_fair=p_fair, p_push=0.0, ev_fair=-0.04, uplift=0.0659,
                           p_model=p_fair + 0.0659, fair_ref="pinnacle", fair_mu=224.0,
                           fetch_at=_et(2026, 11, 5, 18, 20, 10), dk_price=dk,
                           link="https://fanduel/over", dk_link="https://draftkings/over")


GAMES = {"NBA_2026-11-05_AWY_HOM": {"home": "HOM", "away": "AWY", "game_date": "2026-11-05",
                                    "season": 2027, "tip": _et(2026, 11, 5, 19, 30)}}


def test_a_decided_game_is_never_decided_again():
    """RULE (CLAUDE.md 1c): lock on first write. The second look writes nothing,
    whatever the price, and a game with a BET is never decided again."""
    from scripts import nba_total_luck_card as card
    b = _bet()
    rows, refused = card.pick_rows([b], GAMES, 1000.0)
    d = [tl.Decision(b.game_id, b.fetch_at, 4.2, 1, "bet")]
    conn = _Conn()
    assert card.publish(conn, rows, d, {b.game_id: 69.8}, refused) == (1, 1)
    better = card.pick_rows([_bet(price=+105.0)], GAMES, 1000.0)[0]
    assert card.publish(conn, better, d, {b.game_id: 59.8}, {}) == (0, 0)
    assert len(conn.picks) == 1 and conn.picks[0]["decision_odds"] == -110.0
    assert any("pg_advisory_xact_lock" in s for s in conn.sql), "published without the model lock"
    conn2 = _Conn(bet={b.game_id})
    assert card.publish(conn2, rows, d, {}, {}) == (0, 0)


def test_a_no_bet_decision_is_recorded_so_a_later_offer_cannot_bet_it():
    from scripts import nba_total_luck_card as card
    b = _bet()
    conn = _Conn()
    nobet = [tl.Decision(b.game_id, b.fetch_at, 4.2, 0, "no_offer")]
    assert card.publish(conn, [], nobet, {b.game_id: 69.8}, {}) == (0, 1)
    rows, _ = card.pick_rows([b], GAMES, 1000.0)
    assert card.publish(conn, rows, [tl.Decision(b.game_id, b.fetch_at, 4.2, 1, "bet")],
                        {}, {}) == (0, 0)
    assert conn.picks == [] and conn.ledger[0]["detail"] == "no_offer"


def test_run_card_decides_only_games_due_and_not_already_decided(monkeypatch):
    from scripts import nba_total_luck_card as card
    now = _et(2026, 11, 5, 18, 25)
    games = {
        "G_DUE": {"home": "HOM", "away": "AWY", "game_date": "2026-11-05", "season": 2027,
                  "tip": _et(2026, 11, 5, 19, 30)},
        "G_DONE": {"home": "OT1", "away": "OT2", "game_date": "2026-11-05", "season": 2027,
                   "tip": _et(2026, 11, 5, 19, 30)},
        "G_LATER": {"home": "AAA", "away": "BBB", "game_date": "2026-11-05", "season": 2027,
                    "tip": _et(2026, 11, 5, 20, 30)},
    }
    fetch = _et(2026, 11, 5, 18, 24, 10)
    conn = _Conn(decided={"G_DONE"})
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: games)
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {k: fetch for k in g})
    seen = {}

    def fake_decide(targets, quotes, box, final, times, art, *, scheduled, **kw):
        seen["games"] = sorted(targets["game_id"])
        return [], [], {**dict.fromkeys(tl.DIAG_KEYS, 0), "presumed_unplayed": []}
    monkeypatch.setattr(tl, "decide", fake_decide)
    monkeypatch.setattr(card, "load_season",
                        lambda c, s, b: (pd.DataFrame(), pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(card, "load_quote_rows", lambda c, g, s: pd.DataFrame(
        columns=list(tl.QUOTE_ROW_COLS)))
    out = card.run_card(do_publish=False, now=now)
    assert seen["games"] == ["G_DUE"]
    assert out["timing"]["already_decided"] == 1 and out["timing"]["too_early"] == 1


def test_a_dry_run_creates_no_ledger_and_writes_nothing(monkeypatch):
    """A dry run (run_pipeline --dry-run) writes nothing to production, not even
    the ledger's CREATE TABLE."""
    from scripts import nba_total_luck_card as card
    conn = _Conn(ledger_table=False)
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: dict(GAMES))
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {})
    card.run_card(do_publish=False, now=_et(2026, 11, 5, 18, 32))
    assert not any("CREATE" in s or s.startswith("INSERT") for s in conn.sql), conn.sql
    assert conn.commits == 0


def test_the_card_refuses_a_season_the_artifact_does_not_end_just_before(monkeypatch, art):
    from scripts import nba_total_luck_card as card
    games = {"G": {"home": "HOM", "away": "AWY", "game_date": "2027-11-05", "season": 2028,
                   "tip": _et(2027, 11, 5, 19, 30)}}
    conn = _Conn()
    monkeypatch.setattr(card, "get_connection", lambda: type("C", (), {
        "execute": conn.execute, "commit": conn.commit, "close": lambda self: None})())
    monkeypatch.setattr(card, "slate", lambda c, n, s=None: games)
    monkeypatch.setattr(card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(card, "newest_fetch", lambda c, g, n: {"G": _et(2027, 11, 5, 18, 25, 10)})
    called = []
    monkeypatch.setattr(tl, "decide", lambda *a, **k: called.append(1))
    out = card.run_card(do_publish=True, now=_et(2027, 11, 5, 18, 26))
    assert sum(out["timing"].values()) == 0, "the game must be due, or this proves nothing"
    assert called == [] and out["decided"] == 0 and conn.ledger == [] and conn.picks == []


# ── the row and its label ────────────────────────────────────────────────────

def test_the_label_reads_back_against_its_side_and_line():
    """RULE: 'HOM vs AWY Over 224.5' -- the side and the stored total agree with
    the label (tracking/pick_integrity), and the row carries the price taken."""
    from scripts import nba_total_luck_card as card
    from tracking.pick_integrity import pick_problems
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    r = rows[0]
    assert r["pick_label"] == "HOM vs AWY Over 224.5" and refused == {}
    assert r["pick_side"] == "over" and r["scored_line"] == 224.5
    assert pick_problems(r["pick_label"], r["pick_side"], r["scored_line"], tl.MODEL_ID,
                         "HOM", "AWY") == []
    assert (r["decision_book"], r["decision_odds"], r["best_book"]) == ("fanduel", -110.0, "fanduel")
    assert r["model_probability"] == r["model_probability_cal"] == round(0.50 + 0.0659, 4)
    assert r["signal_type"] == "BET" and r["sport"] == "NBA"


def test_a_label_that_disagrees_with_its_line_is_refused(monkeypatch):
    from scripts import nba_total_luck_card as card
    monkeypatch.setattr(card, "pick_label", lambda b, h, a: f"{h} vs {a} Over 230.5")
    rows, refused = card.pick_rows([_bet()], GAMES, 1000.0)
    assert rows == [] and refused == {"NBA_2026-11-05_AWY_HOM": "label_mismatch"}


def test_a_bet_under_the_ev_floor_is_refused():
    from scripts import nba_total_luck_card as card
    rows, refused = card.pick_rows([_bet(p_fair=0.40)], GAMES, 1000.0)    # EV well under 0.00
    assert rows == [] and refused["NBA_2026-11-05_AWY_HOM"].startswith("ev_below_floor")


def test_the_ev_floor_refunds_a_push():
    """RULE: model_probability is P(the over WINS), pushes in its denominator,
    so the EV the floor reads is p x decimal - 1 + P(push). The graded bet
    this decides: 2023-01-24 DEN at NOP, over 232.0 at -110, P(push) 0.024:
    -0.012 with the push counted as a loss, +0.011 refunded. Here: p x decimal
    - 1 = -0.010 with a 0.030 chance of a push."""
    from scripts import nba_total_luck_card as card
    p_model = 0.99 / (1 + 100 / 110)                     # p x decimal - 1 = -0.010
    whole = _bet(p_fair=p_model - 0.0659)
    whole = tl.TotalLuckBet(**{**whole.__dict__, "line": 224.0, "p_push": 0.030})
    rows, refused = card.pick_rows([whole], GAMES, 1000.0)
    assert refused == {} and len(rows) == 1, refused
    half = tl.TotalLuckBet(**{**whole.__dict__, "line": 224.5, "p_push": 0.0})
    rows, refused = card.pick_rows([half], GAMES, 1000.0)
    assert rows == [] and refused["NBA_2026-11-05_AWY_HOM"].startswith("ev_below_floor")


def test_the_shared_gate_is_unchanged_for_every_other_caller():
    from models.honest_ev import gate
    g = gate("nhl_over_under", 0.55, -110)
    assert g.ev == pytest.approx(config.expected_value(g.cal_prob, -110))
    assert gate("nhl_over_under", 0.55, -110, p_push=0.02).ev == pytest.approx(g.ev + 0.02)
    assert gate("nhl_over_under", 0.55, None, p_push=0.02).ev is None


@pytest.mark.parametrize("paused", [False, True])
def test_a_paused_model_s_rows_carry_the_paused_marker(monkeypatch, paused):
    """RULE (config.PAUSED_NOTE): a row written while the model is paused says
    so itself, so it stays unannounced after an unpause; a live row carries no
    marker. The marker is written: it is in the insert's column list."""
    from models import scorer
    from scripts import nba_total_luck_card as card
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "PAUSED_MODELS",
                        {tl.MODEL_ID} if paused else set())
    rows, _ = card.pick_rows([_bet()], GAMES, 1000.0)
    assert rows[0]["downgrade_reason"] == (config.PAUSED_NOTE if paused else None)
    assert "downgrade_reason" in card._COLS
    conn = _Conn()
    card.publish(conn, rows, [tl.Decision(rows[0]["game_id"], _bet().fetch_at, 4.2, 1, "bet")],
                 {}, {})
    assert conn.picks[0]["downgrade_reason"] == (config.PAUSED_NOTE if paused else None)


# ── wiring ───────────────────────────────────────────────────────────────────

def test_it_settles_as_a_total():
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick(tl.MODEL_ID) == "totals"


def test_the_refresh_pass_does_not_run_it():
    """RULE: one producer, the window job. On the refresh pass a skipped tick
    lost every game it would have decided, and the card made the pass longer."""
    import re
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert not re.search(r"^\s*step nba-total-luck\s*$", sh, re.M)
