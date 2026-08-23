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


# ── Backtest harness ──────────────────────────────────────────────────────────
# The harness is what decides whether a market is beatable, so its price
# arithmetic and its refusal conditions are worth pinning.

import models.nfl_prop_backtest as nbt              # noqa: E402
from models.nfl_prop_backtest import (      # noqa: E402
    american_to_profit, no_vig_pair, _verdict,
)


class TestPriceMath:
    def test_profit_at_american_odds(self):
        assert american_to_profit(-110) == pytest.approx(100 / 110)
        assert american_to_profit(150) == pytest.approx(1.5)
        assert american_to_profit(100) == pytest.approx(1.0)

    def test_de_vig_a_two_sided_quote(self):
        """The benchmark is the no-vig probability implied by the price paid,
        not 50%. A -110/-110 pair is a fair coin; a -130/+110 pair is not."""
        o, u = no_vig_pair(-110, -110)
        assert (o, u) == pytest.approx((0.5, 0.5))
        o, u = no_vig_pair(-130, 110)
        assert o + u == pytest.approx(1.0)
        assert o > u

    def test_one_way_market_is_not_de_vigged(self):
        # betting into a one-sided quote is a different proposition; the caller
        # skips it rather than averaging it in on a made-up fair value
        assert no_vig_pair(-110, None)[1] is None


class TestVerdict:
    def test_too_few_bets_is_no_verdict(self):
        assert _verdict(40, 0.10, 5.0, {}).startswith("NO VERDICT")

    def test_interval_touching_zero_is_not_beatable(self):
        v = _verdict(200, 0.05, -1.0, {2024: {"bets": 100, "roi_pct": 5},
                                       2025: {"bets": 100, "roi_pct": 5}})
        assert v.startswith("NOT BEATABLE")

    def test_edge_concentrated_in_one_season_is_called_out(self):
        v = _verdict(200, 0.05, 1.0, {2024: {"bets": 100, "roi_pct": 12},
                                      2025: {"bets": 100, "roi_pct": 0.2}})
        assert v.startswith("ONE SEASON")

    def test_spread_across_seasons_clears(self):
        v = _verdict(200, 0.05, 1.0, {2024: {"bets": 100, "roi_pct": 5},
                                      2025: {"bets": 100, "roi_pct": 5}})
        assert v.startswith("CLEARS THE BAR")


class TestPropOddsLoader:
    """
    The loader is the only join between the odds feed and the model rows, and it
    reaches production through both the scorer and the backtest. It shipped once
    calling norm_player_name without importing it — invisible until a market
    actually returned rows, because an empty result never enters the loop.
    """

    class _Cur:
        def __init__(self, rows): self._rows = rows
        def fetchall(self): return self._rows

    class _Conn:
        def __init__(self, rows): self._rows = rows
        def execute(self, sql, params=None):
            return TestPropOddsLoader._Cur(self._rows)

    ROW = ("NFL_2025_01_KC_BUF", "Marvin Harrison Jr.", "player_receptions",
           4.5, -115, -105, None, None, "2025-09-07T14:00:00Z", "draftkings")

    def test_keys_on_the_normalised_name(self):
        from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_odds
        got = load_nfl_prop_odds(self._Conn([self.ROW]), ["NFL_2025_01_KC_BUF"])
        assert ("NFL_2025_01_KC_BUF", "marvinharrison", "player_receptions") in got

    def test_carries_the_price_and_the_snapshot_time(self):
        from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_odds
        q = list(load_nfl_prop_odds(self._Conn([self.ROW]), ["x"]).values())[0]
        assert q["line"] == 4.5 and q["over_price"] == -115
        # the backtest's timestamp gate reads this; losing it would silently
        # allow a post-kickoff line
        assert q["snapshot_at"] == "2025-09-07T14:00:00Z"

    def test_empty_slate_short_circuits(self):
        from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_odds
        assert load_nfl_prop_odds(self._Conn([]), []) == {}


class TestYesNoMarkets:
    def test_anytime_td_gets_a_default_line(self):
        """Anytime TD is Yes/No with no numeric `point`. Without it in this set
        the parser drops every row and the market reads as non-existent."""
        from data.ingestors.prop_odds_ingestor import YESNO_DEFAULT_LINE_MARKETS
        assert "player_anytime_td" in YESNO_DEFAULT_LINE_MARKETS


class TestIngestEventsDoesNotShadowItsMarkets:
    """
    _ingest_events takes a `markets` parameter and loops books. Naming the loop
    variable `markets` too left the SECOND event asking the API for a list of
    dicts — invisible on any single-event probe, fatal on a real slate.
    """

    def test_every_event_requests_the_same_market_list(self, monkeypatch):
        import data.ingestors.nfl_prop_odds_ingestor as m
        seen = []

        def fake_event_props(event_id, markets, snapshot_iso=None,
                             regions=None, books=None):
            seen.append(list(markets))
            assert all(isinstance(x, str) for x in markets)
            return ([("draftkings", [{"key": "player_receptions", "outcomes": []}])],
                    "2024-01-01T00:00:00Z", 1)

        monkeypatch.setattr(m, "_event_props", fake_event_props)
        monkeypatch.setattr(m, "_insert_prop_odds", lambda conn, rows: len(rows))

        class Conn:
            def commit(self): pass

        games = {("KC", "BUF", "2024-10-06"): ("NFL_2024_05_KC_BUF", "2024-10-06"),
                 ("TB", "CIN", "2024-10-06"): ("NFL_2024_05_TB_CIN", "2024-10-06")}
        evs = [{"id": "1", "home_team": "Buffalo Bills",
                "away_team": "Kansas City Chiefs", "commence_time": "2024-10-06T17:00:00Z"},
               {"id": "2", "home_team": "Cincinnati Bengals",
                "away_team": "Tampa Bay Buccaneers", "commence_time": "2024-10-06T17:00:00Z"}]
        m._ingest_events(Conn(), evs, games, "2024-10-06T14:00:00Z", "open",
                         ["player_anytime_td"])
        assert seen == [["player_anytime_td"], ["player_anytime_td"]]


class TestPlaceboCannotSilentlyNotHappen:
    """
    Three NFL targets are derived and have no rolling column of their own. The
    first real run guarded the placebo with `if col in columns`, so for those
    three it passed the MODEL's own predictions through — and the output read
    "the placebo reproduces the model exactly", which looks like evidence the
    edge is fake when it actually means no placebo ran. On the one market that
    showed a profit, that was the whole verdict.
    """

    def test_derived_targets_build_from_components(self):
        import pandas as pd
        from models.nfl_prop_backtest import _naive_projection
        te = pd.DataFrame({"def_tackles_solo_r8": [3.0, 4.0],
                           "def_tackle_assists_r8": [2.0, 1.0]})
        got = _naive_projection("nfl_prop_tackles_assists", te, 5.0)
        assert list(got) == [5.0, 5.0]

    def test_unbuildable_placebo_raises_rather_than_passing_through(self):
        import pandas as pd
        from models.nfl_prop_backtest import _naive_projection
        with pytest.raises(ValueError, match="cannot build a placebo"):
            _naive_projection("nfl_prop_tackles_assists", pd.DataFrame({"x": [1]}), 5.0)

    def test_every_configured_model_has_a_buildable_placebo(self):
        """A new model must not be able to join the family with a placebo that
        silently no-ops."""
        import config
        from features.nfl_prop_feature_engine import NFL_PROP_FEATURE_MAP, _TARGET
        from models.nfl_prop_backtest import _NAIVE_COMPONENTS
        from features.nfl_prop_feature_engine import _PLAYER_ROLL_COLS
        for mid in [m for m in config.PROP_MODELS if m.startswith("nfl_prop")]:
            if mid in _NAIVE_COMPONENTS:
                continue
            assert _TARGET[mid] in _PLAYER_ROLL_COLS, (
                f"{mid}: target has no rolling column and no _NAIVE_COMPONENTS entry")


# ── The definitional-mismatch gate ───────────────────────────────────────────
# Tackles returned +13.47% and its naive placebo +10.09%, which a rolling
# average cannot do against real prices. The cause was that our computed actual
# lands over the line 41.1% of the time while the book's own de-vigged price
# says 50% — a different stat, not an edge. These pin the gate that catches it,
# and pin the two honest markets it must not condemn: a book pins sacks and
# anytime-TD at a 0.5 line and prices the skew, so their over-rates are 37% and
# 29% by design and match the book exactly.

def _uni(over, under, fair_over, push=0):
    n = over + under + push
    return nbt._universe_summary({
        "over": over, "under": under, "push": push, "sum_diff": 0.0,
        "sum_fair_over": fair_over * n, "priced": n})


def test_universe_reports_the_gap_against_the_books_own_price():
    u = _uni(411, 589, 0.50)
    assert u["over_pct"] == 41.1 and u["book_over_pct"] == 50.0
    assert u["gap_pp"] == -8.9


def test_verdict_flags_a_definitional_mismatch_over_a_profitable_roi():
    # the real tackles numbers: a wide, significant, two-season positive ROI
    seasons = {2024: {"bets": 935, "roi_pct": 16.76},
               2025: {"bets": 704, "roi_pct": 9.1}}
    v = nbt._verdict(1639, 0.1347, 8.99, seasons, _uni(411, 589, 0.50))
    assert v.startswith("DEFINITIONAL MISMATCH")


def test_a_half_line_market_priced_to_its_own_skew_is_not_flagged():
    # sacks: 37.4% of player-games clear 0.5, and the book's price says 37%
    v = nbt._verdict(833, 0.05, 1.0, {2024: {"bets": 445, "roi_pct": 5.0},
                                      2025: {"bets": 388, "roi_pct": 5.0}},
                     _uni(374, 626, 0.37))
    assert "MISMATCH" not in v
    # anytime TD: 28.7% score, book says 28%
    v = nbt._verdict(600, 0.05, 1.0, {2024: {"bets": 300, "roi_pct": 5.0},
                                      2025: {"bets": 300, "roi_pct": 5.0}},
                     _uni(287, 713, 0.28))
    assert "MISMATCH" not in v


def test_verdict_without_a_universe_still_works():
    # one-way markets never populate `priced`; the gate must abstain, not crash
    seasons = {2024: {"bets": 300, "roi_pct": 5.0}, 2025: {"bets": 300, "roi_pct": 5.0}}
    assert "MISMATCH" not in nbt._verdict(600, 0.05, 1.0, seasons, {})
    assert "MISMATCH" not in nbt._verdict(600, 0.05, 1.0, seasons, None)


# ── Local cache ──────────────────────────────────────────────────────────────
# The cache exists so a sweep runs in seconds instead of a CI round trip. It is
# only safe if two things hold: the cached odds path returns exactly what the
# SQL path returns (otherwise the backtest and the live scorer grade different
# lines), and a cache that does not cover the requested seasons falls back to
# the DB rather than silently answering short.

import pandas as pd                                                 # noqa: E402
import data.local_store as lstore                                   # noqa: E402
from data.ingestors.nfl_prop_odds_ingestor import _odds_from_frame  # noqa: E402


def _odds_frame():
    return pd.DataFrame([
        # two snapshots for one prop: the LATER one must win, as ORDER BY does
        dict(game_id="NFL_2024_01_A_B", game_date="2024-09-08", player_name="A.J. Brown",
             market="player_receptions", line=5.5, over_price=-115, under_price=-105,
             bookmaker="draftkings", snapshot_at="2024-09-08T12:00:00Z", season=2024),
        dict(game_id="NFL_2024_01_A_B", game_date="2024-09-08", player_name="A.J. Brown",
             market="player_receptions", line=6.5, over_price=-110, under_price=-110,
             bookmaker="draftkings", snapshot_at="2024-09-08T15:00:00Z", season=2024),
        # a different book, same prop — must not leak into a draftkings read
        dict(game_id="NFL_2024_01_A_B", game_date="2024-09-08", player_name="A.J. Brown",
             market="player_receptions", line=4.5, over_price=+100, under_price=-130,
             bookmaker="fanduel", snapshot_at="2024-09-08T16:00:00Z", season=2024),
        dict(game_id="NFL_2024_01_C_D", game_date="2024-09-08", player_name="Jonathan Taylor",
             market="player_rush_yds", line=78.5, over_price=-112, under_price=-108,
             bookmaker="draftkings", snapshot_at="2024-09-08T14:00:00Z", season=2024),
    ])


class TestLocalOddsCache:
    def test_latest_snapshot_wins_like_the_sql_ordering(self):
        out = _odds_from_frame(_odds_frame(), ["NFL_2024_01_A_B"], None, "draftkings", None)
        q = out[("NFL_2024_01_A_B", "ajbrown", "player_receptions")]
        assert q["line"] == 6.5 and q["over_price"] == -110

    def test_bookmaker_and_market_filters(self):
        f = _odds_frame()
        assert _odds_from_frame(f, ["NFL_2024_01_A_B"], ["player_rush_yds"],
                                "draftkings", None) == {}
        fd = _odds_from_frame(f, ["NFL_2024_01_A_B"], None, "fanduel", None)
        assert fd[("NFL_2024_01_A_B", "ajbrown", "player_receptions")]["line"] == 4.5

    def test_before_cutoff_drops_later_snapshots(self):
        # the timestamp gate the backtest uses for kickoff
        out = _odds_from_frame(_odds_frame(), ["NFL_2024_01_A_B"], None, "draftkings",
                               "2024-09-08T13:00:00Z")
        assert out[("NFL_2024_01_A_B", "ajbrown", "player_receptions")]["line"] == 5.5

    def test_unknown_game_returns_nothing(self):
        assert _odds_from_frame(_odds_frame(), ["NFL_2024_01_X_Y"], None,
                                "draftkings", None) == {}

    def test_key_is_the_normalised_name(self):
        out = _odds_from_frame(_odds_frame(), ["NFL_2024_01_C_D"], None, "draftkings", None)
        assert ("NFL_2024_01_C_D", "jonathantaylor", "player_rush_yds") in out


class TestLocalCacheGuards:
    def test_inactive_cache_reads_nothing(self):
        lstore._active = False
        assert lstore.read_table("nfl_prop_odds") is None

    def test_partial_season_coverage_falls_back_to_the_db(self, tmp_path, monkeypatch):
        # A cache holding 2024 must NOT answer a request for 2023+2024 — a short
        # frame would look like a result rather than a missing pull.
        monkeypatch.setattr(lstore, "CACHE_DIR", tmp_path)
        lstore.write_table("t", pd.DataFrame({"season": [2024], "x": [1]}), [2024])
        lstore._active = True
        try:
            assert lstore.read_table("t", [2024]) is not None
            assert lstore.read_table("t", [2023, 2024]) is None
        finally:
            lstore._active = False


def test_a_nonfinite_fair_price_cannot_switch_the_gate_off():
    """
    The gate reads a mean of the book's de-vigged over-rate. One nan makes that
    mean nan, `abs(nan) > 5` is False, and the definitional check silently stops
    firing — the failure mode it exists to catch would sail through.
    """
    import numpy as np
    u = {"over": 411, "under": 589, "push": 0, "sum_diff": 0.0,
         "sum_fair_over": float("nan"), "priced": 1000}
    gap = nbt._universe_summary(u).get("gap_pp")
    assert gap is None or np.isfinite(gap), "a nan gap must not reach _verdict"


# ── Gate 3: the post-kickoff line check ──────────────────────────────────────
# Kickoffs and snapshots arrive in different shapes, and 'T' sorts after a
# space. A string compare therefore calls every snapshot post-kickoff and throws
# away almost every bet — the whole sweep quietly shrank by 4x when the kickoff
# source changed from the database to a parquet Timestamp. Same failure class as
# the session-106 WNBA odds leak, in the opposite direction.

from models.nfl_prop_backtest import _as_dt                          # noqa: E402


class TestKickoffGate:
    def test_the_two_real_wire_formats_compare_correctly(self):
        snap = _as_dt("2024-09-29T13:55:38Z")            # odds feed
        kick = _as_dt("2024-09-29 18:00:00+00:00")       # parquet Timestamp
        assert snap < kick, "a pre-kickoff line must survive the gate"
        # and the naive version this replaced gets it backwards
        assert not ("2024-09-29T13:55:38Z" < "2024-09-29 18:00:00+00:00")

    def test_post_kickoff_is_still_rejected(self):
        assert _as_dt("2024-09-29T19:30:00Z") > _as_dt("2024-09-29 18:00:00+00:00")

    def test_naive_timestamps_are_treated_as_utc_not_crashed_on(self):
        assert _as_dt("2024-09-29 18:00:00") == _as_dt("2024-09-29T18:00:00Z")

    def test_unparseable_returns_none_so_the_gate_abstains(self):
        # abstaining keeps the bet; silently dropping every bet is the worse of
        # the two failure modes and is what the string compare did
        assert _as_dt("not a date") is None and _as_dt(None) is None


def test_a_one_way_market_stays_one_way_through_the_cache():
    """
    SQL gives None for a missing price, parquet gives NaN, and `NaN is not
    None`. Unnormalised, anytime-TD (no under price) looked two-sided and the
    cached backtest booked thousands of under bets at a nan price.
    """
    df = pd.DataFrame([dict(
        game_id="NFL_2024_01_A_B", game_date="2024-09-08", player_name="Saquon Barkley",
        market="player_anytime_td", line=0.5, over_price=110.0,
        under_price=float("nan"), bookmaker="draftkings",
        snapshot_at="2024-09-08T12:00:00Z", season=2024)])
    q = _odds_from_frame(df, ["NFL_2024_01_A_B"], None, "draftkings", None)
    assert q[("NFL_2024_01_A_B", "saquonbarkley", "player_anytime_td")]["under_price"] is None


def test_a_targeted_backfill_never_substitutes_draftkings():
    """
    The 422 retry falls back to DK so a renamed display book cannot cost the
    prices we score against. But `player_prop_odds` appends without dedup, so on
    a backfill that asks for ONE missing book, substituting DK would silently
    re-insert every row the table already holds. The retry must only fire when
    DK was actually requested.
    """
    import inspect
    from data.ingestors import nfl_prop_odds_ingestor as ing
    src = inspect.getsource(ing._event_props)
    assert "dk_requested" in src, "the 422 retry must be gated on DK being asked for"
    assert 'ODDS_API_BOOKMAKER in params["bookmakers"].split(",")' in src


# ── Market-relative selection ────────────────────────────────────────────────
# De-vig the sharp book, bet the soft outlier. The load-bearing rule is that
# only EQUAL lines are compared: Pinnacle at 5.5 and DraftKings at 6.5 are
# different propositions, and treating the price gap between them as edge
# manufactures one — the same class of error as the tackles mismatch, which
# produced a significant two-season +13% that was entirely measurement.

import models.nfl_prop_market as mkt                                  # noqa: E402


def _q(book, line, over, under):
    return {"line": line, "over_price": over, "under_price": under}


class TestMarketRelative:
    def test_edge_is_measured_against_the_sharp_devigged_price(self):
        q = {("g", "p", "player_receptions", "pinnacle"): _q("p", 5.5, -110, -110),
             ("g", "p", "player_receptions", "draftkings"): _q("d", 5.5, 120, -140)}
        bets, diag = mkt.find_bets(q, min_edge=0.02)
        assert len(bets) == 1 and bets[0].side == "over"
        # pinnacle -110/-110 de-vigs to 50/50; DK +120/-140 de-vigs the over to
        # ~43.8%, so the edge is ~6.2pp, not the raw implied difference
        assert 0.05 < bets[0].edge < 0.07
        assert diag["compared"] == 1

    def test_a_different_line_is_a_different_bet_and_is_dropped(self):
        q = {("g", "p", "player_receptions", "pinnacle"): _q("p", 5.5, -110, -110),
             ("g", "p", "player_receptions", "draftkings"): _q("d", 6.5, 120, -140)}
        bets, diag = mkt.find_bets(q, min_edge=0.02)
        assert bets == [] and diag["line_mismatch"] == 1 and diag["compared"] == 0

    def test_no_sharp_quote_means_no_bet(self):
        q = {("g", "p", "player_receptions", "draftkings"): _q("d", 5.5, 120, -140)}
        bets, diag = mkt.find_bets(q, min_edge=0.02)
        assert bets == [] and diag["no_sharp"] == 1

    def test_the_sharp_book_is_never_bet_against_itself(self):
        q = {("g", "p", "player_receptions", "pinnacle"): _q("p", 5.5, 200, -300)}
        bets, _ = mkt.find_bets(q, min_edge=0.02)
        assert bets == []

    def test_a_one_way_quote_is_not_devigged_into_a_fake_edge(self):
        q = {("g", "p", "player_anytime_td", "pinnacle"): _q("p", 0.5, 110, None),
             ("g", "p", "player_anytime_td", "draftkings"): _q("d", 0.5, 160, None)}
        bets, diag = mkt.find_bets(q, min_edge=0.02)
        assert bets == [] and diag["one_way"] == 1


class TestMarketGrading:
    def _bet(self, side, line, price, edge=0.06):
        return mkt.MarketBet("NFL_2024_05_A_B", "player", "player_receptions",
                             side, "draftkings", line, price, 0.55, edge, -110)

    def test_settles_and_pushes_on_a_whole_number(self):
        actuals = {("NFL_2024_05_A_B", "player", "player_receptions"): 6.0}
        g = mkt.grade([self._bet("over", 5.5, -110)], actuals, {}, {})
        assert g[0]["result"] == "WIN"
        g = mkt.grade([self._bet("over", 6.0, -110)], actuals, {}, {})
        assert g[0]["result"] == "PUSH" and g[0]["profit"] == 0.0

    def test_a_post_kickoff_quote_is_dropped(self):
        actuals = {("NFL_2024_05_A_B", "player", "player_receptions"): 6.0}
        snaps = {("NFL_2024_05_A_B", "player", "player_receptions", "draftkings"):
                 "2024-10-06T19:00:00Z"}
        kicks = {"NFL_2024_05_A_B": "2024-10-06 17:00:00+00:00"}
        assert mkt.grade([self._bet("over", 5.5, -110)], actuals, snaps, kicks) == []

    def test_dedupe_keeps_one_bet_per_proposition_at_the_best_edge(self):
        actuals = {("NFL_2024_05_A_B", "player", "player_receptions"): 6.0}
        a = self._bet("over", 5.5, -110, edge=0.06)
        b = mkt.MarketBet("NFL_2024_05_A_B", "player", "player_receptions",
                          "over", "fanduel", 5.5, 100, 0.55, 0.09, -110)
        g = mkt.grade([a, b], actuals, {}, {})
        assert len(g) == 1 and g[0]["book"] == "fanduel"   # higher edge wins
        assert len(mkt.grade([a, b], actuals, {}, {}, dedupe=False)) == 2

    def test_season_comes_from_the_game_id_label_not_a_date(self):
        assert mkt.season_of("NFL_2024_18_A_B") == 2024


def test_the_snapshot_offset_is_real_datetime_arithmetic():
    """
    The snapshot time was computed as `17 - hours_before`, which formats a
    NEGATIVE hour past 17 — a 24h offset asked the API for
    '...T-7:00:00Z'. Every offset of a day or more, which is exactly what a
    timing experiment needs, would have been malformed.
    """
    import inspect
    from data.ingestors import nfl_prop_odds_ingestor as ing
    # strip comments: the fix is described in one, and matching prose would
    # make this pass or fail on wording rather than on code
    src = "\n".join(l.split("#")[0] for l in
                    inspect.getsource(ing.backfill_nfl_prop_odds).splitlines())
    assert "17 - hours_before" not in src
    assert "timedelta(hours=hours_before)" in src
    # and the arithmetic itself
    from datetime import datetime, timedelta
    anchor = datetime.fromisoformat("2024-10-06T17:00:00+00:00")
    assert (anchor - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ") == "2024-10-05T17:00:00Z"
    assert (anchor - timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ") == "2024-10-04T17:00:00Z"


def test_a_timing_run_can_be_labelled_so_it_cannot_displace_the_main_series():
    """
    Analysis takes the latest snapshot per proposition. Pulling extra offsets
    under the same label would make T-1h the 'latest' and silently restate the
    result the T-3h series produced.
    """
    import inspect
    from data.ingestors import nfl_prop_odds_ingestor as ing
    sig = inspect.signature(ing.backfill_nfl_prop_odds)
    assert sig.parameters["snapshot_type"].default == "open"
    assert "snapshot_type" in inspect.getsource(ing.backfill_nfl_prop_odds)


# ── Multi-book quote loader (cache path) ─────────────────────────────────────
# The market rule lives or dies on keeping every book's own row. A loader that
# collapsed books would silently make the sharp book stand in for a soft one and
# produce an edge of zero everywhere, which reads as "no edge" rather than "bug".
def test_load_nfl_prop_quotes_keeps_each_book_separate():
    import pandas as pd
    from data import local_store
    from data.ingestors import nfl_prop_odds_ingestor as ing

    df = pd.DataFrame([
        # same proposition, two books, two prices
        dict(game_id="G", player_name="A.J. Brown", market="player_receptions",
             line=4.5, over_price=-110, under_price=-110,
             snapshot_at="2024-09-01T12:00:00Z", bookmaker="pinnacle"),
        dict(game_id="G", player_name="A.J. Brown", market="player_receptions",
             line=4.5, over_price=+120, under_price=-145,
             snapshot_at="2024-09-01T12:00:00Z", bookmaker="draftkings"),
        # a later snapshot for one book only must not displace the other book
        dict(game_id="G", player_name="A.J. Brown", market="player_receptions",
             line=4.5, over_price=+100, under_price=-120,
             snapshot_at="2024-09-01T14:00:00Z", bookmaker="draftkings"),
        dict(game_id="OTHER", player_name="A.J. Brown", market="player_receptions",
             line=4.5, over_price=-110, under_price=-110,
             snapshot_at="2024-09-01T12:00:00Z", bookmaker="pinnacle"),
    ])
    orig = local_store.read_table
    local_store.read_table = lambda t, **k: df if t == "nfl_prop_odds" else None
    try:
        q = ing.load_nfl_prop_quotes(None, ["G"])
    finally:
        local_store.read_table = orig

    assert set(k[3] for k in q) == {"pinnacle", "draftkings"}
    assert all(k[0] == "G" for k in q)                       # other game filtered
    k_dk = [k for k in q if k[3] == "draftkings"][0]
    assert q[k_dk]["over_price"] == 100                      # latest snapshot wins
    k_pin = [k for k in q if k[3] == "pinnacle"][0]
    assert q[k_pin]["over_price"] == -110                    # untouched by DK's update


def test_load_nfl_prop_quotes_normalises_nan_prices():
    """Anytime TD has no under side; parquet stores that as NaN, not None."""
    import pandas as pd
    from data import local_store
    from data.ingestors import nfl_prop_odds_ingestor as ing

    df = pd.DataFrame([dict(
        game_id="G", player_name="Saquon Barkley", market="player_anytime_td",
        line=0.5, over_price=-150, under_price=float("nan"),
        snapshot_at="2024-09-01T12:00:00Z", bookmaker="pinnacle")])
    orig = local_store.read_table
    local_store.read_table = lambda t, **k: df if t == "nfl_prop_odds" else None
    try:
        q = ing.load_nfl_prop_quotes(None, ["G"])
    finally:
        local_store.read_table = orig
    assert list(q.values())[0]["under_price"] is None


def test_live_prop_pull_asks_for_the_sharp_book(monkeypatch):
    """
    Pinnacle is served in `eu`; the platform's global region is `us`. If the live
    pull does not widen both region and book list, the market rule has no sharp
    reference and silently degrades to "no bets" rather than erroring.
    """
    import data.ingestors.nfl_prop_odds_ingestor as m
    seen = {}

    def fake_event_props(event_id, markets, snapshot_iso=None,
                         regions=None, books=None):
        seen["regions"], seen["books"] = regions, books
        return ([], None, 0)

    monkeypatch.setattr(m, "_event_props", fake_event_props)
    monkeypatch.setattr(m, "_insert_prop_odds", lambda conn, rows: len(rows))

    class Conn:
        def commit(self): pass

    games = {("KC", "BUF", "2024-10-06"): ("NFL_2024_05_KC_BUF", "2024-10-06")}
    evs = [{"id": "1", "home_team": "Buffalo Bills",
            "away_team": "Kansas City Chiefs", "commence_time": "2024-10-06T17:00:00Z"}]
    m._ingest_events(Conn(), evs, games, None, "open",
                     regions=m.MARKET_REGIONS, books=m.MARKET_BOOKS)

    assert "eu" in seen["regions"]
    assert "pinnacle" in seen["books"]
    # and the books we bet at are still asked for
    assert "draftkings" in seen["books"]


# ── Live market card ─────────────────────────────────────────────────────────
class TestMarketCard:
    """
    The card is plumbing, but two of its behaviours are load-bearing: it must
    select exactly what the backtest graded, and it must never price a game that
    has already kicked off.
    """

    def _conn(self, rows):
        class Conn:
            def execute(self, sql, params=None):
                class R:
                    def fetchall(self_inner): return rows
                return R()
            def close(self): pass
        return Conn()

    def test_started_games_are_never_priced(self, monkeypatch):
        from datetime import datetime, timedelta, timezone
        import scripts.nfl_prop_market_card as card_mod

        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        rows = [("NFL_2025_01_KC_BUF", past, "BUF", "KC", True, "2025-09-07"),
                ("NFL_2025_01_KC_BUF", past, "KC", "BUF", False, "2025-09-07")]

        asked = {}

        def fake_quotes(conn, gids, markets=None, **k):
            asked["gids"] = list(gids)
            return {}

        monkeypatch.setattr(card_mod, "load_nfl_prop_quotes", fake_quotes)
        bets, diag, _ = card_mod.card(self._conn(rows), "2025-09-07", "2025-09-15")
        assert bets == []
        assert diag["reason"].startswith("every game")
        assert "gids" not in asked          # never even asked for the board

    def test_one_bet_per_proposition(self, monkeypatch):
        from datetime import datetime, timedelta, timezone
        import scripts.nfl_prop_market_card as card_mod
        import models.nfl_prop_market as mkt

        future = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
        rows = [("NFL_2025_01_KC_BUF", future, "BUF", "KC", True, "2025-09-07"),
                ("NFL_2025_01_KC_BUF", future, "KC", "BUF", False, "2025-09-07")]

        g, p, m = "NFL_2025_01_KC_BUF", "josh allen", "player_pass_yds"
        quotes = {
            (g, p, m, "pinnacle"):   {"line": 250.5, "over_price": -110,
                                      "under_price": -110, "player_name": "Josh Allen"},
            # two soft books both way off — one opinion, not two
            (g, p, m, "draftkings"): {"line": 250.5, "over_price": +140,
                                      "under_price": -170, "player_name": "Josh Allen"},
            (g, p, m, "fanduel"):    {"line": 250.5, "over_price": +130,
                                      "under_price": -160, "player_name": "Josh Allen"},
        }
        monkeypatch.setattr(card_mod, "load_nfl_prop_quotes",
                            lambda conn, gids, markets=None, **k: quotes)
        bets, diag, names = card_mod.card(self._conn(rows), "2025-09-07", "2025-09-15")

        assert len(bets) == 1
        assert bets[0].book == "draftkings"      # best edge wins
        assert bets[0].side == "over"
        assert names[p] == "Josh Allen"          # display spelling carried back
        # and the card renders without blowing up on the matchup lookup
        out = card_mod.render(bets, diag, card_mod.slate(self._conn(rows), "a", "b"), names)
        assert "Josh Allen" in out and "KC@BUF" in out

    def test_threshold_stays_at_the_precommitted_five_points(self):
        """
        6pp beat 5pp in training and returned -0.46% blind. If this constant
        drifts, the strategy is no longer the one that was validated.
        """
        import scripts.nfl_prop_market_card as card_mod
        assert card_mod.MIN_EDGE == 0.05
