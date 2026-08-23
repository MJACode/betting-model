"""
NFL player-prop tests: the nflverse parsers, and the response distributions.

The distribution tests are the load-bearing ones. NFL is the first sport in this
repo whose prop markets are NOT all Poisson, and reading P(over) off the wrong
family is a silent failure: the picks still generate, they are just
systematically overconfident. See docs/nfl_props_model.md §2.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.ingestors.nfl_props_data_ingestor import (
    norm_player_name, parse_player_rows, parse_team_rows,
    parse_upcoming_team_rows, parse_snap_rows, _kickoff_utc, games_rows,
)


SCHEDULE = {
    "2025_01_KC_BUF": {
        "game_id": "2025_01_KC_BUF", "season": "2025", "week": "1",
        "gameday": "2025-09-07", "gametime": "16:25", "game_type": "REG",
        "home_team": "BUF", "away_team": "KC", "home_score": "27", "away_score": "24",
        "spread_line": "-2.5", "total_line": "48.5", "roof": "outdoors",
        "surface": "grass", "temp": "68", "wind": "9", "div_game": "0",
    },
    "2025_02_NE_MIA": {   # scheduled, not played
        "game_id": "2025_02_NE_MIA", "season": "2025", "week": "2",
        "gameday": "2025-09-14", "gametime": "13:00", "game_type": "REG",
        "home_team": "MIA", "away_team": "NE", "home_score": "", "away_score": "",
        "spread_line": "3.0", "total_line": "43.0", "roof": "outdoors",
        "surface": "grass", "temp": "", "wind": "", "div_game": "1",
    },
}

PLAYER_CSV = (
    "player_id,player_display_name,position,season,week,season_type,game_id,team,"
    "opponent_team,completions,attempts,passing_yards,passing_tds,"
    "passing_interceptions,carries,rushing_yards,rushing_tds,receptions,targets,"
    "receiving_yards,receiving_tds,target_share,def_tackles_solo,def_tackle_assists,"
    "def_sacks,fg_att,fg_made\n"
    # QB
    "00-001,Patrick Mahomes,QB,2025,1,REG,2025_01_KC_BUF,KC,BUF,"
    "24,38,289,2,1,3,17,0,0,0,0,0,0,0,0,0,0,0\n"
    # WR with an accented, suffixed name — exercises norm_player_name
    "00-002,Marvin Harrison Jr.,WR,2025,1,REG,2025_01_KC_BUF,KC,BUF,"
    "0,0,0,0,0,0,0,0,6,9,84,1,0.24,0,0,0,0,0\n"
    # long snapper: all-zero across every tracked stat → dropped
    "00-003,Nobody Special,LS,2025,1,REG,2025_01_KC_BUF,KC,BUF,"
    "0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0\n"
    # row whose game is not in the schedule → dropped (no game_date)
    "00-004,Ghost Player,WR,2025,1,REG,2025_99_XX_YY,KC,BUF,"
    "0,0,0,0,0,0,0,0,3,4,30,0,0.1,0,0,0,0,0\n"
)


class TestNormaliseName:
    def test_strips_accents_suffixes_and_punctuation(self):
        assert norm_player_name("Marvin Harrison Jr.") == "marvinharrison"
        assert norm_player_name("Amon-Ra St. Brown") == "amonrastbrown"
        assert norm_player_name("José Ramírez") == "joseramirez"

    def test_is_the_join_key_both_sides_agree(self):
        # the weekly-stats spelling and the PFR spelling must collapse together —
        # this is the entire snap-count join
        assert norm_player_name("Marvin Harrison Jr.") == norm_player_name("Marvin Harrison")


class TestParsePlayerRows:
    def test_parses_and_filters(self):
        rows = parse_player_rows(PLAYER_CSV, SCHEDULE)
        names = {r["player_name"] for r in rows}
        assert names == {"Patrick Mahomes", "Marvin Harrison Jr."}

    def test_carries_modelling_columns_and_game_date(self):
        rows = {r["player_name"]: r for r in parse_player_rows(PLAYER_CSV, SCHEDULE)}
        wr = rows["Marvin Harrison Jr."]
        assert wr["target_share"] == pytest.approx(0.24)
        assert wr["game_date"] == "2025-09-07"
        assert wr["game_id"] == "NFL_2025_01_KC_BUF"
        assert wr["norm_name"] == "marvinharrison"

    def test_dateless_rows_are_dropped_not_defaulted(self):
        # game_date orders every rolling window; a dateless row would corrupt it
        assert all(r["game_date"] for r in parse_player_rows(PLAYER_CSV, SCHEDULE))


class TestParseTeamRows:
    def test_volume_is_summed_from_the_player_rows(self):
        rows = parse_team_rows(parse_player_rows(PLAYER_CSV, SCHEDULE), SCHEDULE)
        kc = next(r for r in rows if r["team"] == "KC")
        assert kc["pass_attempts"] == 38
        assert kc["carries"] == 3
        assert kc["plays"] == 41            # the share denominator
        assert kc["targets"] == 9

    def test_market_context_and_orientation(self):
        kc = next(r for r in parse_team_rows(
            parse_player_rows(PLAYER_CSV, SCHEDULE), SCHEDULE) if r["team"] == "KC")
        assert kc["is_home"] == 0
        assert kc["spread_line"] == -2.5    # stays HOME-relative; the engine flips it
        assert kc["total_line"] == 48.5
        assert kc["points_for"] == 24 and kc["points_against"] == 27


class TestUpcomingRows:
    def test_only_unplayed_games_and_only_missing_sides(self):
        played = {("NFL_2025_01_KC_BUF", "KC"), ("NFL_2025_01_KC_BUF", "BUF")}
        rows = parse_upcoming_team_rows(SCHEDULE, 2025, played)
        assert {(r["game_id"], r["team"]) for r in rows} == {
            ("NFL_2025_02_NE_MIA", "NE"), ("NFL_2025_02_NE_MIA", "MIA")}

    def test_context_present_volume_null(self):
        # this is what the scorer reads before kickoff; volume must be absent,
        # not zero, or the rolling means would be poisoned by a fake game
        row = parse_upcoming_team_rows(SCHEDULE, 2025, set())[0]
        assert row["total_line"] == 43.0 and row["div_game"] == 1
        assert row["plays"] is None and row["points_for"] is None


class TestSnapRows:
    CSV = ("game_id,season,week,player,pfr_player_id,position,team,opponent,"
           "offense_snaps,offense_pct,defense_snaps,defense_pct,st_snaps,st_pct\n"
           "2025_01_KC_BUF,2025,1,Marvin Harrison,HarrMa00,WR,KC,BUF,58,0.83,0,0,4,0.12\n"
           "2025_01_KC_BUF,2025,1,Marvin Harrison,HarrMa00,WR,KC,BUF,58,0.83,0,0,4,0.12\n")

    def test_dedupes_on_the_unique_key(self):
        rows = parse_snap_rows(self.CSV)
        assert len(rows) == 1
        assert rows[0]["norm_name"] == "marvinharrison"
        assert rows[0]["offense_pct"] == pytest.approx(0.83)


class TestKickoff:
    def test_eastern_to_utc(self):
        # 20:20 ET on a Thursday is 00:20 UTC the NEXT day — getting this wrong
        # makes the started-game guard fire a day early or never
        assert _kickoff_utc("2026-09-10", "20:20").startswith("2026-09-11T00:20")

    def test_missing_time_is_none_not_midnight(self):
        # a guessed midnight would make every Sunday game look already-started
        assert _kickoff_utc("2026-09-13", None) is None
        assert _kickoff_utc("2026-09-13", "") is None


# ── Response distributions ────────────────────────────────────────────────────
# These are the tests that matter. Everything above is plumbing; this is where a
# wrong answer costs money silently.

from models.scorer import _nfl_prop_probs, _push_adjusted   # noqa: E402


def _art(model_type, **kw):
    return {"model_type": model_type, **kw}


class TestCountDistributions:
    def test_negative_binomial_is_wider_than_poisson_at_the_same_mean(self):
        """
        The whole reason the NB head exists. Same fitted mean, same line: the
        overdispersed distribution must put MORE mass in the tail. If this ever
        inverts, every P(over) on an overdispersed market is overconfident.
        """
        mu, line = 30.0, 35.5
        p_pois, _, _ = _nfl_prop_probs(_art("poisson"), mu, line)
        p_nb, _, _ = _nfl_prop_probs(_art("nbinom", nb_r=8.0), mu, line)
        assert p_nb > p_pois
        # and symmetrically it must put more mass BELOW a low line
        _, u_pois, _ = _nfl_prop_probs(_art("poisson"), mu, 24.5)
        _, u_nb, _ = _nfl_prop_probs(_art("nbinom", nb_r=8.0), mu, 24.5)
        assert u_nb > u_pois

    def test_large_r_collapses_to_poisson(self):
        """r → ∞ IS the Poisson. A market that turns out equidispersed must
        degrade gracefully rather than to something else."""
        mu, line = 5.0, 5.5
        p_pois, _, _ = _nfl_prop_probs(_art("poisson"), mu, line)
        p_nb, _, _ = _nfl_prop_probs(_art("nbinom", nb_r=1e6), mu, line)
        assert p_nb == pytest.approx(p_pois, abs=1e-4)

    def test_half_point_line_has_no_push(self):
        p_o, p_u, p_push = _nfl_prop_probs(_art("nbinom", nb_r=6.0), 4.0, 4.5)
        assert p_push == 0.0
        assert p_o + p_u == pytest.approx(1.0)

    def test_whole_number_line_pushes(self):
        """NFL count lines are frequently whole numbers (4 receptions, 30
        attempts). A push returns the stake — folding it into `under` would
        overstate every under."""
        p_o, p_u, p_push = _nfl_prop_probs(_art("nbinom", nb_r=6.0), 4.0, 4.0)
        assert p_push > 0.05
        assert p_o + p_u + p_push == pytest.approx(1.0)
        # over is strictly X > 4, so exactly-4 belongs to neither side
        assert p_o < 1.0 - p_u


class TestYardageDistribution:
    ART = _art("gamma", zero_inflation=0.06, gamma_shape=1.1)

    def test_is_far_wider_than_a_poisson_would_be(self):
        """Receiving yards have variance-to-mean ~30. A Poisson at mean 45
        essentially never reaches 100; the real distribution does about 1 game
        in 8."""
        p_gamma, _, _ = _nfl_prop_probs(self.ART, 45.0, 99.5)
        p_pois, _, _ = _nfl_prop_probs(_art("poisson"), 45.0, 99.5)
        assert p_gamma > 0.05
        assert p_pois < 1e-6

    def test_zero_mass_shows_up_below_the_lowest_line(self):
        _, p_under, _ = _nfl_prop_probs(self.ART, 45.0, 0.5)
        assert p_under > 0.05          # the shutout games are real

    def test_continuous_markets_never_push(self):
        assert _nfl_prop_probs(self.ART, 45.0, 50.0)[2] == 0.0

    def test_monotone_in_the_line(self):
        ps = [_nfl_prop_probs(self.ART, 45.0, L)[0] for L in (20.5, 45.5, 70.5, 120.5)]
        assert ps == sorted(ps, reverse=True)

    def test_mixture_mean_matches_the_fitted_mean(self):
        """The Gamma is re-scaled by 1/(1-p0) precisely so the zero-inflated
        mixture has the mean the model actually fitted."""
        from scipy import stats
        p0, k, mu = 0.06, 1.1, 45.0
        m = mu / (1 - p0)
        assert (1 - p0) * stats.gamma(a=k, scale=m / k).mean() == pytest.approx(mu)


class TestPushAdjustment:
    def test_no_push_is_identity(self):
        assert _push_adjusted(0.55, 0.0) == pytest.approx(0.55)

    def test_conditional_on_resolving(self):
        """A price is quoted against P(win | the bet resolves) — a push returns
        the stake. Comparing a raw P(over) to that price understates the model
        on every whole-number line."""
        assert _push_adjusted(0.45, 0.10) == pytest.approx(0.5)

    def test_degenerate_all_push(self):
        assert _push_adjusted(0.0, 1.0) == 0.0


class TestBinaryMarket:
    def test_logistic_passes_through(self):
        p_o, p_u, p_push = _nfl_prop_probs(_art("logistic"), 0.31, 0.5)
        assert (p_o, p_u, p_push) == pytest.approx((0.31, 0.69, 0.0))


# ── Prop-odds game-id resolution ──────────────────────────────────────────────
# The Odds API knows team names and a kickoff instant; the modelling tables know
# the nflverse game id. A wrong bridge here produces orphan odds rows the scorer
# silently never joins to, so the resolver looks the pair UP and returns None
# rather than constructing an id it cannot verify.

from data.ingestors.nfl_prop_odds_ingestor import resolve_nfl_game_id   # noqa: E402

GAMES = {
    # (away, home, game_date) -> (game_id, game_date)
    ("NE", "SEA", "2026-09-09"): ("NFL_2026_01_NE_SEA", "2026-09-09"),
    ("TB", "CIN", "2026-09-13"): ("NFL_2026_01_TB_CIN", "2026-09-13"),
}


class TestResolveGameId:
    def test_afternoon_kickoff(self):
        got = resolve_nfl_game_id(GAMES, "Cincinnati Bengals", "Tampa Bay Buccaneers",
                                  "2026-09-13T17:00:00Z")
        assert got == ("NFL_2026_01_TB_CIN", "2026-09-13")

    def test_prime_time_kickoff_rolls_into_the_next_utc_day(self):
        """A Thursday 8:20pm ET kickoff is 00:20 UTC on Friday. Matching only on
        the UTC date would drop every prime-time game — which is most of the
        nationally televised slate."""
        got = resolve_nfl_game_id(GAMES, "Seattle Seahawks", "New England Patriots",
                                  "2026-09-10T00:20:00Z")
        assert got == ("NFL_2026_01_NE_SEA", "2026-09-09")

    def test_unknown_team_name_skips_rather_than_guesses(self):
        assert resolve_nfl_game_id(GAMES, "Nonexistent Team", "Tampa Bay Buccaneers",
                                   "2026-09-13T17:00:00Z") is None

    def test_reversed_home_away_does_not_match(self):
        # home/away orientation is part of the key — a flipped event is not this game
        assert resolve_nfl_game_id(GAMES, "Tampa Bay Buccaneers", "Cincinnati Bengals",
                                   "2026-09-13T17:00:00Z") is None

    def test_unparseable_kickoff_is_none(self):
        assert resolve_nfl_game_id(GAMES, "Cincinnati Bengals", "Tampa Bay Buccaneers",
                                   "not-a-time") is None


class TestGamesRows:
    """
    player_prop_odds.game_id and picks.game_id both FK to games. Without a row
    here an NFL prop line cannot be stored and an NFL prop pick cannot be
    written — which is exactly how the first production insert failed.
    """

    def _rows(self):
        return parse_team_rows(parse_player_rows(PLAYER_CSV, SCHEDULE), SCHEDULE)

    def test_one_row_per_game_from_the_home_side(self):
        g = games_rows(self._rows())
        assert len(g) == 1
        assert g[0]["home_team"] == "BUF" and g[0]["away_team"] == "KC"
        assert g[0]["game_id"] == "NFL_2025_01_KC_BUF"

    def test_scores_and_home_win(self):
        g = games_rows(self._rows())[0]
        assert (g["home_score"], g["away_score"]) == (27, 24)
        assert g["home_win"] == 1

    def test_unplayed_game_has_no_score_and_no_winner(self):
        # an upcoming game must not be stamped home_win=0, which would grade as
        # an away win everywhere downstream
        g = games_rows(parse_upcoming_team_rows(SCHEDULE, 2025, set()))
        assert len(g) == 1
        assert g[0]["home_score"] is None and g[0]["home_win"] is None

    def test_tie_is_no_winner(self):
        rows = self._rows()
        rows[0]["points_for"] = rows[0]["points_against"] = 20
        assert games_rows(rows)[0]["home_win"] is None

    def test_away_row_alone_still_produces_the_game(self):
        """The fixture only has players for the away team. Keying off the home
        side would emit nothing, and no games row means every prop line and pick
        for that game fails its foreign key."""
        rows = self._rows()
        assert all(r["is_home"] == 0 for r in rows)
        g = games_rows(rows)
        assert len(g) == 1
        assert g[0]["home_team"] == "BUF" and g[0]["away_team"] == "KC"
