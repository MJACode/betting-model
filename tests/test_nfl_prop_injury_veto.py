"""NFL prop Out/Doubtful veto: timestamped, fail-open, not a feature.

The clock is the whole product. A status that predates the quote suppresses
the bet; a status that arrived after the line must not. Healthy / unknown /
Questionable players pass through. Tests FAILED against a version that
vetoed on status alone (no clock) and against one that used `>` instead of
`<=` for equal timestamps.
"""
from __future__ import annotations

from pathlib import Path

from models.nfl_prop_injury_veto import (
    apply_injury_veto,
    load_nfl_injury_index,
    player_is_vetoed,
    should_veto,
)
from models.nfl_prop_market import MarketBet, apply_injury_veto as mk_veto

GID = "NFL_2026_02_KC_BUF"
PLAYER = "jamarrchase"
MARKET = "player_receptions"
BOOK = "draftkings"
STATUS_TS = "2026-09-13T18:00:00Z"
QUOTE_AFTER = "2026-09-13T19:00:00Z"
QUOTE_BEFORE = "2026-09-13T17:00:00Z"


def _bet(player=PLAYER, book=BOOK):
    return MarketBet(GID, player, MARKET, "over", book,
                     6.5, -110.0, 0.58, 0.07, -120.0)


def _quotes(snapshot_at, player=PLAYER, book=BOOK):
    return {(GID, player, MARKET, book): {"snapshot_at": snapshot_at}}


def _idx(status, status_ts=STATUS_TS, player="Ja'Marr Chase"):
    from data.ingestors.nfl_props_data_ingestor import norm_player_name
    return {norm_player_name(player): [
        {"status": status, "status_ts": status_ts, "player_name": player}
    ]}


def test_out_before_quote_vetoes():
    assert should_veto("Out", STATUS_TS, QUOTE_AFTER) is True
    kept, diag = apply_injury_veto([_bet()], _quotes(QUOTE_AFTER), _idx("Out"))
    assert kept == []
    assert diag["injury_veto"] == 1


def test_doubtful_before_quote_vetoes():
    assert should_veto("Doubtful", STATUS_TS, QUOTE_AFTER) is True
    kept, _ = apply_injury_veto([_bet()], _quotes(QUOTE_AFTER), _idx("doubtful"))
    assert kept == []


def test_out_after_quote_does_not_veto():
    """Look-ahead: the news did not exist when this line was taken."""
    assert should_veto("Out", STATUS_TS, QUOTE_BEFORE) is False
    kept, diag = apply_injury_veto([_bet()], _quotes(QUOTE_BEFORE), _idx("Out"))
    assert len(kept) == 1
    assert diag["injury_veto"] == 0


def test_equal_timestamps_veto():
    """ESPN dates are second-precision; a quote at that instant had the news."""
    assert should_veto("Out", STATUS_TS, STATUS_TS) is True


def test_questionable_does_not_veto():
    assert should_veto("Questionable", STATUS_TS, QUOTE_AFTER) is False
    kept, diag = apply_injury_veto(
        [_bet()], _quotes(QUOTE_AFTER), _idx("Questionable"))
    assert len(kept) == 1
    assert diag["injury_veto"] == 0


def test_active_and_unknown_players_pass_through():
    assert should_veto("Active", STATUS_TS, QUOTE_AFTER) is False
    assert should_veto(None, STATUS_TS, QUOTE_AFTER) is False
    kept, diag = apply_injury_veto([_bet()], _quotes(QUOTE_AFTER), {})
    assert len(kept) == 1
    assert diag["injury_veto"] == 0


def test_missing_clocks_fail_open():
    """Cannot prove the news predates the line → do not veto."""
    assert should_veto("Out", None, QUOTE_AFTER) is False
    assert should_veto("Out", STATUS_TS, None) is False
    kept, _ = apply_injury_veto([_bet()], {}, _idx("Out"))
    assert len(kept) == 1


def test_name_normalisation_matches_the_quote_key():
    """Odds feed 'Ja'Marr Chase' vs nflverse spelling still vetoes."""
    from data.ingestors.nfl_props_data_ingestor import norm_player_name
    assert player_is_vetoed(
        "Ja'Marr Chase", QUOTE_AFTER, _idx("Out", player="Ja'Marr Chase"))
    assert player_is_vetoed(
        "jamarrchase", QUOTE_AFTER, _idx("Out", player="Ja'Marr Chase"))
    assert norm_player_name("Ja'Marr Chase Jr.") == norm_player_name(
        "Ja'Marr Chase Jr")


def test_nfl_prop_market_reexports_the_gate():
    """The card imports the veto from models.nfl_prop_market on purpose."""
    assert mk_veto is apply_injury_veto


def test_the_card_applies_the_veto_before_locking_a_pick():
    src = Path(__file__).parent.parent.joinpath(
        "scripts/nfl_prop_market_card.py").read_text(encoding="utf-8")
    assert "apply_injury_veto" in src
    assert "load_nfl_injury_index" in src
    scorer = Path(__file__).parent.parent.joinpath(
        "models/scorer.py").read_text(encoding="utf-8")
    assert "player_is_vetoed" in scorer


def test_injured_reserve_is_out_and_vetoes():
    """The ingestor maps IR → Out; a stored Out still has to beat the clock."""
    kept, diag = apply_injury_veto(
        [_bet()], _quotes(QUOTE_AFTER), _idx("Out"))
    assert kept == [] and diag["injury_veto"] == 1


class _InjConn:
    def __init__(self, latest, rows):
        self.latest = latest
        self.rows = rows
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        self._last = sql
        return self

    def fetchone(self):
        return (self.latest,)

    def fetchall(self):
        return self.rows


def test_loader_keys_by_norm_name_and_skips_empty():
    conn = _InjConn("2026-09-14", [
        ("Ja'Marr Chase", "Out", STATUS_TS),
        ("Tyler Huntley", "Questionable", STATUS_TS),
    ])
    idx = load_nfl_injury_index(conn, "2026-09-14")
    assert "jamarrchase" in idx
    assert idx["jamarrchase"][0]["status"] == "Out"
    assert load_nfl_injury_index(None) == {}
    boom = _InjConn("2026-09-14", [])
    def _raise(*a, **k):
        raise RuntimeError("no such column: status_ts")
    boom.execute = _raise
    assert load_nfl_injury_index(boom, "2026-09-14") == {}
