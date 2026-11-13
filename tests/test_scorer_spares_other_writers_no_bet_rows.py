"""The game scorer's clears take only the no-bet rows its own pass re-writes.

A pick is a pick (CLAUDE.md 1c), and a model's NONE row is part of what the
app's All board shows and what the evaluation rule (section 7) grades. The
game scorer (models.scorer.run_scorer) clears unsettled no-bet rows so it can
re-write one current row per side each pass. Until 2026-11-06 the clear at the
end of a full pass (the refresh pass and the daily pipeline) had no model
filter: it took EVERY model's unsettled non-BET row on every game not yet
started, across the whole look-ahead window, whoever wrote it.

What that cost, measured in picks_log (read-only Supabase, 2026-11-06):

* The five NCAAB cards (PR #1147, 2026-11-04) write a NONE row once, when they
  decide a game, and never again. 257 of the 278 they wrote were deleted, in
  27 transactions; each one landed 0.3 to 2.5 seconds before a full scoring
  pass logged its finish in pipeline_log (records_in about 400). The cards
  never re-write a decided game, so the rows were gone for good.
* The NFL opener and wind rows are kept current by their own writer
  (scripts/nfl_wind_publisher.publish_scored: insert, or update in place).
  The same sweep deleted 3,704 nfl_opener_spread and 2,478 nfl_wind_totals
  NONE rows between 2026-11-01 and 11-06 (213 passes); each came back at the
  next NFL poll as a new row, so the board lost them between the two and the
  row's created_at -- when the number was seen -- restarted every pass.

The rows a full pass may clear are the game models it re-scores
(config.MODELS) and the MLB and WNBA prop models whose scorers run right after
it in the same pass: that clear is what releases a player the prop lock holds
at NONE (tests/test_prop_no_bet_rows_survive_to_tipoff.py pins it). Every
model observed in a non-BET delete since 2026-07-01 that is outside that set
is a live model (its own loop clears is_live rows) or one of the victims
above.

Behavioural, not source scans: run_scorer runs against the sqlite board from
the prop test, so the DELETE statements that execute are the ones in
models/scorer.py.
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models.scorer as scorer  # noqa: E402
from tests.test_prop_no_bet_rows_survive_to_tipoff import (  # noqa: E402
    T0, TARGET, _Board, _iso, _wire,
)

NCAAB_CARDS = ("ncaab_total_blend", "ncaab_spread_market",
               "ncaab_moneyline_own_spread", "ncaab_first_half_spread",
               "ncaab_first_half_total",
               # the women's totals card (2026-11-10): the same write-once NONE row
               "ncaabw_total_blend")
NFL_RULES = ("nfl_opener_spread", "nfl_wind_totals")
# The NCAAF moneyline card (2026-11-10): a write-once NONE row on a sport the
# scorer's own loop scores, beside models the pass does clear (ncaaf_spread).
NCAAF_CARD = "ncaaf_moneyline_market"
# A game-market card that writes on MLB games (scripts run by the
# mlb-game-market step), so a foreign row on a game the loop DOES reach.
MLB_CARD = "mlb_total_public_fade"
MLB_BUILDER = ("models.scorer", "build_mlb_game_features")


def _game(game_id, sport, game_date, commence):
    return (game_id, sport, int(game_date[:4]), game_date, "HOM", "AWY",
            _iso(commence))


def _seed_none(board, game_id, model_id, game_date, side="home"):
    board.db.execute(
        "INSERT INTO picks (game_id, model_id, game_date, pick_side, "
        "signal_type, dk_odds, created_at) "
        "VALUES (?,?,?,?, 'NONE', -110, 'earlier pass')",
        (game_id, model_id, game_date, side))


def _held(board, game_id, model_id):
    return set(board.db.execute(
        "SELECT pick_side, signal_type, created_at FROM picks "
        "WHERE game_id = ? AND model_id = ?", (game_id, model_id)).fetchall())


KEPT = {("home", "NONE", "earlier pass")}


@pytest.fixture
def board_and_ids(monkeypatch):
    later = T0 + timedelta(hours=3)
    nfl_day = (date.fromisoformat(TARGET) + timedelta(days=4)).isoformat()
    ncaab = f"NCAAB_{TARGET}_AAA_BBB"
    nfl = f"NFL_{nfl_day}_PIT_CIN"
    mlb_scored = f"MLB_{TARGET}_CCC_DDD"
    mlb_unscored = f"MLB_{TARGET}_EEE_FFF"
    ncaaf = f"NCAAF_{TARGET}_GGG_HHH"
    games = [_game(ncaab, "NCAAB", TARGET, later),
             _game(ncaaf, "NCAAF", TARGET, later),
             _game(nfl, "NFL", nfl_day, T0 + timedelta(days=4)),
             _game(mlb_scored, "MLB", TARGET, later),
             _game(mlb_unscored, "MLB", TARGET, later)]
    board = _Board(games)
    for mid in NCAAB_CARDS:
        _seed_none(board, ncaab, mid, TARGET)
    for mid in NFL_RULES:
        _seed_none(board, nfl, mid, nfl_day)
    _seed_none(board, ncaaf, NCAAF_CARD, TARGET)
    _seed_none(board, ncaaf, "ncaaf_spread", TARGET)
    board.ncaaf = ncaaf
    for g in (mlb_scored, mlb_unscored):
        board.seed(g, "mlb_moneyline", "mlb_prop_batter_hits")
        _seed_none(board, g, MLB_CARD, TARGET)
    _wire(monkeypatch, board, *MLB_BUILDER, no_features={mlb_unscored})
    return board, ncaab, nfl, mlb_scored, mlb_unscored


def test_a_full_pass_leaves_every_other_writers_no_bet_rows(board_and_ids):
    board, ncaab, nfl, mlb_scored, mlb_unscored = board_and_ids

    scorer.run_scorer(target_date=TARGET)          # the refresh pass's call

    for mid in NCAAB_CARDS:
        assert _held(board, ncaab, mid) == KEPT, (
            f"{mid}: the scorer's sweep deleted an NCAAB card's NONE row; "
            "the card decides a game once and never writes it again")
    for mid in NFL_RULES:
        assert _held(board, nfl, mid) == KEPT, (
            f"{mid}: the scorer's sweep deleted an NFL rule's NONE row; "
            "publish_scored keeps it current in place")
    # A card's row on a game the loop re-scores (the per-game clear) and on
    # one it does not (only the sweep reaches it).
    assert _held(board, mlb_scored, MLB_CARD) == KEPT, "per-game clear"
    assert _held(board, mlb_unscored, MLB_CARD) == KEPT, "end-of-pass sweep"
    # The NCAAF moneyline card's row stays; the scorer's own NCAAF model's
    # stale row on the same game is the one the pass clears.
    assert _held(board, board.ncaaf, NCAAF_CARD) == KEPT, (
        "the scorer's sweep deleted the NCAAF moneyline card's NONE row; "
        "the card decides a game once and never writes it again")
    assert _held(board, board.ncaaf, "ncaaf_spread") != KEPT


def test_a_full_pass_still_clears_what_it_rewrites(board_and_ids):
    """Unchanged: the game model is cleared and re-scored, a game it cannot
    re-score loses its stale game-model rows, and every prop NONE/AVOID is
    cleared (that releases the prop lock); BETs are never touched."""
    board, _ncaab, _nfl, mlb_scored, mlb_unscored = board_and_ids

    scorer.run_scorer(target_date=TARGET)

    assert board.held(mlb_scored, "mlb_moneyline") == {(None, "NONE", "this pass")}
    assert board.held(mlb_unscored, "mlb_moneyline") == set()
    for g in (mlb_scored, mlb_unscored):
        assert board.held(g, "mlb_prop_batter_hits") == {
            ("p_bet", "BET", "earlier pass")}


def test_the_poller_leaves_them_too(board_and_ids):
    board, ncaab, nfl, mlb_scored, mlb_unscored = board_and_ids

    scorer.run_scorer(target_date=TARGET,
                      only_games={ncaab, nfl, mlb_scored, mlb_unscored, board.ncaaf},
                      game_models_only=True)

    for mid in NCAAB_CARDS:
        assert _held(board, ncaab, mid) == KEPT, mid
    for mid in NFL_RULES:
        assert _held(board, nfl, mid) == KEPT, mid
    assert _held(board, mlb_scored, MLB_CARD) == KEPT
    assert _held(board, mlb_unscored, MLB_CARD) == KEPT
    assert _held(board, board.ncaaf, NCAAF_CARD) == KEPT


def test_every_prop_scorer_in_the_pass_is_in_the_cleared_set():
    """A prop scorer added to models/scorer.py whose models are left out of
    the cleared set would keep a NONE player locked all day (the release is
    this clear). NFL props are excluded on purpose: the evening refresh does
    not re-run them (the NOT LIKE 'nfl_prop_%' clause). Golf has its own
    scorer and its own delete."""
    cleared = scorer._pass_rewritten_models(game_models_only=False)
    for name in dir(scorer):
        if not (name.endswith("_PROP_CONFIG") and name.startswith("_")):
            continue
        cfg = getattr(scorer, name)
        if not isinstance(cfg, dict) or name == "_NFL_PROP_CONFIG":
            continue
        missing = set(cfg) - cleared
        assert not missing, f"{name}: {sorted(missing)} not cleared"
    assert set(scorer.MODELS) <= cleared
    assert not any(m.startswith(("ncaab_", "nfl_")) for m in cleared)
    assert NCAAF_CARD not in cleared and "ncaaf_spread" in cleared
    assert scorer._pass_rewritten_models(game_models_only=True) == set(scorer.MODELS)
