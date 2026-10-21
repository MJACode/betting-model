"""The NBA projection model (models/nba_prop_projection.py) and its card.

mike, 2026-10-16: "build the projection model", "maximize units won". Six
cells, every qualifying proposition, never a proposition nba_prop_market
holds, decided once in the same window, at the consensus main line, on the
worker's inputs only.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_prop_projection as pj  # noqa: E402
import models.nba_props as nb  # noqa: E402

UTC = timezone.utc
TIP = datetime(2026, 10, 21, 23, 0, tzinfo=UTC)
GID = "NBA_2026-10-21_GSW_LAL"
GAMES = {GID: {"home": "LAL", "away": "GSW", "game_date": "2026-10-21", "season": 2027, "tip": TIP}}
PID = "201939"
BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers", "hardrockbet", "betparx")


def _art(p_over=0.5, alpha=0.0):
    """An artifact whose calibration map returns `p_over` whatever the raw number (a = logit, b = 0)."""
    a = float(np.log(p_over / (1 - p_over)))
    return {"alphas": {m: alpha for m in pj.MARKETS}, "calibration": {m: (a, 0.0) for m in pj.MARKETS},
            "version": "test"}


def _proj(status=None, mu=1.0, pid=PID):
    row = {"game_id": GID, "player_id": pid, "status": status, "projected_at": "x"}
    for m in pj.MARKETS:
        row[f"mu_{m}"] = mu
    return pd.DataFrame([row])


def _q(book, line, over, under, market="player_steals", snap=None, lu=None, pid=PID, player="Stephen Curry"):
    snap = snap or (TIP - timedelta(minutes=55)).isoformat()
    return {"game_id": GID, "player": player, "player_id": pid, "market": market, "book": book,
            "line": line, "over_price": over, "under_price": under, "over_link": f"{book}-o",
            "under_link": f"{book}-u", "snapshot_at": snap, "book_last_update": lu}


def _run(quotes, proj=None, art=None, now=None, rule_keys=(), decided=(), rule_decided=(GID,)):
    return pj.find_bets(quotes, _proj() if proj is None else proj, GAMES,
                        now or TIP - timedelta(minutes=54), art or _art(0.60),
                        set(rule_keys), set(decided), set(rule_decided), BOOKS)


# ── the card ─────────────────────────────────────────────────────────────────

def test_labels_use_the_live_nba_rules_words_for_shared_markets():
    import models.nba_prop_market as mk
    for m in set(pj.MARKETS) & set(mk.MARKET_LABEL):
        assert pj.MARKET_LABEL[m] == mk.MARKET_LABEL[m], m
    assert pj.MARKET_LABEL["player_blocks_steals"] == "Blocks+Steals"
    assert pj.MARKET_LABEL["player_rebounds_assists"] == "Reb+Ast"


def test_the_card_is_the_six_confirmed_cells_without_assists_overs():
    assert pj.CARD == {
        "player_steals": (("over", "under"), 0.02), "player_rebounds": (("under",), 0.01),
        "player_blocks_steals": (("over", "under"), 0.05), "player_blocks": (("under",), 0.02),
        "player_rebounds_assists": (("under",), 0.04), "player_threes": (("over", "under"), 0.04),
    }
    assert "player_assists" not in pj.CARD
    assert set(pj.STATS) == {"rebounds", "assists", "fg3_made", "steals", "blocks"}


def test_the_inputs_are_the_workers_only():
    cols = pj.minutes_cols()
    for c in pj.DROP_OWN + pj.DROP_AVAIL + tuple(nb.LINES):
        assert c not in cols
    assert "tm_o_min" in cols and "own_q" in cols and "b2b" in cols
    assert pj.rate_cols("steals")[-3:] == nb.rate_features("steals")


def test_every_market_the_card_bets_is_fetched_live():
    import config
    for m in pj.MARKETS:
        assert m in config.PROP_MARKETS_NBA, f"{m} is bet but never fetched"


# ── the injury report, small ─────────────────────────────────────────────────

def _report():
    t = lambda h: pd.Timestamp(f"2026-01-15 {h}:00", tz="UTC")  # noqa: E731
    rows = [
        # game A: LAL's 17:00 report lists two, its 18:00 report one (the latest submitted counts)
        ("A", "LAL", t("17"), "1", "Ann", "Out"), ("A", "LAL", t("17"), "2", "Bob", "Questionable"),
        ("A", "LAL", t("18"), "1", "Ann", "Out"),
        # GSW: a later report not yet submitted, an earlier one with an Available player
        ("A", "GSW", t("16"), "3", "Cy", "Questionable"), ("A", "GSW", t("16"), "4", "Di", pj.UNLISTED),
        ("A", "GSW", t("18"), None, "", "NOT YET SUBMITTED"),
        # a report after the decision never counts
        ("A", "GSW", t("21"), "5", "Ed", "Out"),
        # game B: only after its decision -> not covered
        ("B", "BOS", t("21"), "6", "Flo", "Out"),
        # game C: a report before the decision that lists nobody -> covered, nobody out
        ("C", "MIA", t("17"), "7", "Gil", pj.UNLISTED),
    ]
    return pd.DataFrame(rows, columns=["game_id", "team", "report_ts", "player_id", "player_name", "status"])


def test_the_compact_report_reads_exactly_as_the_whole_report():
    rep = _report()
    dec = pd.DataFrame({"game_id": ["A", "B", "C"],
                        "decision_ts": [pd.Timestamp("2026-01-15 19:00", tz="UTC")] * 3})
    small = pj.compact_report(rep, dec)
    pd.testing.assert_frame_equal(
        nb.injury_asof(rep, dec).sort_values(["game_id", "player_name"]).reset_index(drop=True),
        nb.injury_asof(small, dec).sort_values(["game_id", "player_name"]).reset_index(drop=True),
        check_dtype=False)
    assert list(nb.injury_coverage(rep, dec)) == list(nb.injury_coverage(small, dec)) == [True, False, True]
    assert len(small) < len(rep)


def test_the_stored_history_reads_back_with_its_own_decision_times():
    """The live loader has no decision time for a past game: it uses the newest stored row's time,
    and must read back exactly what was stored."""
    rep = _report()
    dec = pd.DataFrame({"game_id": ["A", "B"], "decision_ts": [pd.Timestamp("2026-01-15 19:00", tz="UTC")] * 2})
    small = pj.compact_report(rep, dec)
    games = pd.DataFrame({"game_id": ["A", "B"], "commence_time": ["2026-01-16T00:00:00Z"] * 2})
    import scripts.nba_prop_projection_card as card
    back = card.history_decisions(games, small)
    a = nb.injury_asof(small, dec).sort_values(["game_id", "player_name"]).reset_index(drop=True)
    b = nb.injury_asof(small, back).sort_values(["game_id", "player_name"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)
    assert list(nb.injury_coverage(small, back)) == [True, False]


def test_an_espn_pull_covers_every_game_and_maps_its_two_statuses():
    pull = pd.DataFrame({"team": ["LAL", "LAL", "BOS", "LAL"],
                         "player_name": ["Ann", "Bob", "Flo", "Gus"],
                         "status": ["Out", "Day-To-Day", "Out", "Suspension"]})
    gt = pd.DataFrame({"game_id": [GID, GID, "G2", "G2"], "team": ["LAL", "GSW", "NYK", "MIA"]})
    rows = pj.espn_compact(pull, TIP - timedelta(minutes=60), gt)
    cov = rows[rows.status == pj.COVERED]
    assert sorted(cov.game_id) == sorted([GID, "G2"]), "a game with nobody listed is still covered"
    listed = rows[rows.status != pj.COVERED].set_index("player_name").status.to_dict()
    assert listed == {"Ann": "Out", "Bob": "Questionable"}
    dec = pd.DataFrame({"game_id": [GID, "G2"], "decision_ts": [pd.Timestamp(TIP)] * 2})
    assert list(nb.injury_coverage(rows, dec)) == [True, True]


# ── the main line ────────────────────────────────────────────────────────────

def test_the_main_line_is_draftkings_else_the_most_hung_line_lower_on_a_tie():
    q = lambda b, line: {"book": b, "line": line}  # noqa: E731
    assert pj.main_line([q("fanduel", 1.5), q("draftkings", 0.5), q("betmgm", 1.5)], BOOKS) == 0.5
    assert pj.main_line([q("fanduel", 1.5), q("betmgm", 1.5), q("fanatics", 0.5)], BOOKS) == 1.5
    assert pj.main_line([q("fanduel", 1.5), q("fanatics", 0.5)], BOOKS) == 0.5
    assert pj.main_line([q("pinnacle", 0.5)], BOOKS) is None


# ── find_bets ────────────────────────────────────────────────────────────────

def test_an_over_at_the_best_price_with_ev_over_the_floor_is_bet():
    bets, diag, dec = _run([_q("draftkings", 1.5, +105, -135), _q("fanduel", 1.5, +115, -145)])
    assert len(bets) == 1 and len(dec) == 1
    b = bets[0]
    assert (b.side, b.book, b.price, b.line) == ("over", "fanduel", 115.0, 1.5)
    assert b.prob == 0.6 and b.ev == round(0.6 * 2.15 - 1, 4)
    assert b.dk_price == 105.0, "DraftKings' own price on the same side and line"


def test_a_side_outside_the_cell_is_never_bet():
    """Rebounds is unders only: a 60% over is not a bet, a 60% under is."""
    over = _run([_q("draftkings", 7.5, +110, -140, market="player_rebounds")], art=_art(0.60))[0]
    under = _run([_q("draftkings", 7.5, -140, +110, market="player_rebounds")], art=_art(0.40))[0]
    assert over == [] and len(under) == 1 and under[0].side == "under"


@pytest.mark.parametrize("market,floor", [(m, f) for m, (_, f) in pj.CARD.items()])
def test_each_market_has_its_own_floor(market, floor):
    # at p = 0.5, EV = 0.5 x decimal - 1 reaches the floor at +100 x (1 + 2 x floor)
    edge = 100 * (1 + 2 * floor)
    under_price, over_price = edge - 1, edge + 1
    side = pj.CARD[market][0][0]
    col = (lambda p: (p, -125)) if side == "over" else (lambda p: (-125, p))
    lo = _run([_q("draftkings", 2.5, *col(under_price), market=market)], art=_art(0.5))[0]
    hi = _run([_q("draftkings", 2.5, *col(over_price), market=market)], art=_art(0.5))[0]
    assert lo == [] and len(hi) == 1


def test_a_proposition_nba_prop_market_holds_is_skipped_on_every_line_and_side():
    bets, diag, _ = _run([_q("draftkings", 1.5, +105, -135)], rule_keys={(GID, PID, "player_steals")})
    assert bets == [] and diag["rule_holds"] == 1


def test_the_game_waits_for_nba_prop_market_then_decides_alone_near_the_close():
    q = [_q("draftkings", 1.5, +105, -135, snap=(TIP - timedelta(minutes=55)).isoformat())]
    early, d1, dec1 = _run(q, now=TIP - timedelta(minutes=54), rule_decided=())
    assert early == [] and dec1 == [] and d1["waiting_for_rule"] == 1
    q = [_q("draftkings", 1.5, +105, -135, snap=(TIP - timedelta(minutes=50)).isoformat())]
    late, d2, dec2 = _run(q, now=TIP - timedelta(minutes=49), rule_decided=())
    assert len(late) == 1 and len(dec2) == 1


def test_a_player_listed_out_is_never_bet():
    bets, diag, _ = _run([_q("draftkings", 1.5, +105, -135)], proj=_proj(status="Out"))
    assert bets == [] and diag["out"] == 1


def test_a_stale_quote_is_refused_and_one_with_no_clock_is_counted():
    fresh = (TIP - timedelta(minutes=56)).isoformat()
    old = (TIP - timedelta(minutes=70)).isoformat()
    bets, diag, _ = _run([_q("draftkings", 1.5, +105, -135, lu=fresh), _q("betparx", 1.5, +140, -180, lu=old)])
    assert len(bets) == 1 and bets[0].book == "draftkings" and diag["stale_rejected"] >= 1
    bets, diag, _ = _run([_q("draftkings", 1.5, +105, -135, lu=fresh), _q("betparx", 1.5, +140, -180)])
    assert bets[0].book == "betparx" and diag["last_update_unknown"] >= 1


def test_the_price_floor_is_minus_200():
    bets, diag, _ = _run([_q("draftkings", 0.5, -210, +160)], art=_art(0.80))
    assert bets == [] and diag["below_price_floor"] >= 1


def test_a_tie_on_price_goes_to_the_earlier_book():
    bets, _, _ = _run([_q("betparx", 1.5, +115, -145), _q("fanduel", 1.5, +115, -145)])
    assert bets[0].book == "fanduel"


def test_a_book_hanging_two_lines_for_one_player_is_refused():
    bets, diag, _ = _run([_q("fanduel", 1.5, +115, -145), _q("fanduel", 2.5, +250, -350)])
    assert bets == [] and diag["multi_line"] == 1


def test_an_incoherent_quote_is_not_a_price():
    bets, diag, _ = _run([_q("draftkings", 1.5, +300, +300)])
    assert bets == [] and diag["no_main_line"] == 1


def test_only_the_window_decides_and_only_on_a_fetch_from_inside_it():
    q = [_q("draftkings", 1.5, +105, -135)]
    assert _run(q, now=TIP - timedelta(minutes=58))[2] == []           # before the window
    assert _run(q, now=TIP - timedelta(minutes=44))[2] == []           # after it
    stale = [_q("draftkings", 1.5, +105, -135, snap=(TIP - timedelta(minutes=58)).isoformat())]
    bets, diag, dec = _run(stale, now=TIP - timedelta(minutes=54))
    assert dec == [] and diag["stale_fetch"] == 1


def test_no_projection_is_no_decision_and_a_decided_game_is_never_looked_at_again():
    bets, diag, dec = _run([_q("draftkings", 1.5, +105, -135)], proj=pd.DataFrame())
    assert dec == [] and diag["no_projection"] == 1
    bets, diag, dec = _run([_q("draftkings", 1.5, +105, -135)], decided={GID})
    assert dec == [] and diag["already_decided"] == 1


def test_a_decision_with_no_bet_is_still_a_decision():
    bets, diag, dec = _run([_q("draftkings", 1.5, -110, -110)], art=_art(0.5))
    assert bets == [] and len(dec) == 1 and dec[0]["n_bets"] == 0


def test_the_calibrated_probability_is_the_negative_binomial_through_the_map():
    art = {"alphas": {m: 0.3 for m in pj.MARKETS}, "calibration": {m: (0.1, 0.5) for m in pj.MARKETS}}
    raw = nb.p_over(np.array([2.0]), np.array([1.5]), 0.3)
    want = 1 / (1 + np.exp(-(0.1 + 0.5 * np.log(raw / (1 - raw)))))
    assert np.allclose(pj.p_over_calibrated(art, "player_steals", [2.0], [1.5]), want)


# ── the card's rows ──────────────────────────────────────────────────────────

def test_a_pick_row_names_its_side_book_and_market():
    import scripts.nba_prop_projection_card as card
    bets, _, _ = _run([_q("draftkings", 1.5, +105, -135), _q("fanduel", 1.5, +115, -145)])
    rows = card.pick_rows(bets, 1000.0)
    r = rows[0]
    assert r["pick_label"] == "Stephen Curry Over 1.5 Steals" and r["pick_side"] == "over"
    assert r["model_id"] == "nba_prop_projection" and r["prop_market"] == "player_steals"
    assert (r["decision_book"], r["decision_odds"]) == ("fanduel", 115.0)
    assert r["dk_odds"] == 105.0 and r["line_book"] is None and r["best_book"] == "fanduel"
    assert r["model_probability"] == r["model_probability_cal"] == 0.6
    assert set(card._COLS) <= set(r)


def test_publish_never_writes_into_a_game_nba_prop_market_has_bet():
    """The rule bet the game between this look and the lock: the shared door re-reads under the
    lock and writes nothing more into it (one bet a game across both models), and still records
    this model's decision."""
    import scripts.nba_prop_projection_card as card
    import scripts.nba_props_card as door
    bets, _, decisions = _run([_q("draftkings", 1.5, +105, -135)])
    rows = card.pick_rows(bets, 1000.0)
    written, ledger = [], []

    class _C:
        def execute(self, sql, params=None):
            self.sql = " ".join(sql.split())
            self.params = params
            if "INSERT INTO picks" in self.sql:
                written.append(params)
            if "INSERT INTO nba_prop_projection_decisions" in self.sql:
                ledger.append((params["game_id"], params["n_bets"]))
            return self

        def fetchall(self):
            if self.sql.startswith("SELECT DISTINCT game_id FROM picks WHERE model_id = ANY"):
                return [(GID,)]                            # the rule's bet, committed before the lock
            return []

        def fetchone(self):
            return ("x",) if "INSERT" in self.sql else None

        def commit(self):
            pass

    import scripts.nfl_wind_publisher as wp
    orig = wp._lock_model
    wp._lock_model = lambda conn, mid: None
    try:
        out = door.publish_across_models(_C(), rows, [], decisions)
    finally:
        wp._lock_model = orig
    assert rows and out["decided"]["nba_prop_projection"] == 1 and out["written"] == 0 and written == []
    assert ledger == [(GID, 0)]


def test_settlement_and_closing_value_know_the_model():
    from tracking import paper_tracker as pt
    assert pt._PROP_MARKET_STAT_BY_MODEL["nba_prop_projection"] is pt._NBA_MARKET_STAT
    for m in pj.MARKETS:
        assert m in pt._NBA_MARKET_STAT
    import data.ingestors.nba_prop_close_ingestor as close
    assert "nba_prop_projection" in close.MODEL_IDS


def test_the_config_carries_the_model_everywhere_a_model_must_be():
    import config
    mid = pj.MODEL_ID
    assert mid in config.ACTION_THRESHOLDS and mid in config.MODEL_EDGE_THRESHOLDS
    assert mid in config.MODEL_PROB_THRESHOLDS and mid in config.MODELS_ON_OWN_PROBABILITY
    assert config.MODEL_MIN_ODDS[mid] == -200
    assert config.MODEL_OWN_EV_FLOOR[mid] == min(f for _, f in pj.CARD.values())
    assert config.scoring_method(mid) == config.SCORING_ARTIFACT


def test_the_tables_are_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    for t in ("nba_prop_projection_decisions", "nba_prop_projections", "nba_injury_asof"):
        assert t in WORKER_ONLY_TABLES


# ── the committed artifact ───────────────────────────────────────────────────

def _committed():
    saved = sorted(Path(__file__).parent.parent.joinpath("models", "saved").glob("nba_prop_projection_*.pkl"))
    if not saved:
        pytest.skip("no committed nba_prop_projection artifact")
    return pd.read_pickle(saved[-1])


def test_the_committed_artifact_was_fitted_on_the_workers_inputs():
    art = _committed()
    assert art["model_id"] == pj.MODEL_ID
    assert art["minutes"]["cols"] == pj.minutes_cols()
    for s in pj.STATS:
        assert art["rates"][s]["cols"] == pj.rate_cols(s)
    assert set(art["alphas"]) == set(pj.MARKETS) == set(art["calibration"])
    assert art["train_seasons"][-1] == 2026 and art["calibration_pairs"]["seasons"] == [2024, 2025, 2026]


# ── the injury history the live frame reads ──────────────────────────────────

def test_a_past_game_never_projected_gets_the_newest_espn_pull_55_minutes_before_its_tip():
    import scripts.nba_prop_projection_card as card
    tip = pd.Timestamp("2026-10-21T23:00:00Z")
    pulls = {"2026-10-21 21:50:00.1+00": [("LAL", "Ann", "Out")],          # 70 min out
             "2026-10-21 22:04:59.9+00": [("LAL", "Ann", "Day-To-Day")],   # 55 min out: the one
             "2026-10-21 22:20:00.0+00": [("LAL", "Bob", "Out")]}          # 40 min out: too late
    written = []

    class _C:
        def execute(self, sql, params=None):
            self.s = " ".join(sql.split())
            self.p = params
            if self.s.startswith("DELETE") or self.s.startswith("INSERT"):
                pass
            return self

        def executemany(self, sql, recs):
            written.extend(recs)

        def fetchall(self):
            if "SELECT DISTINCT created_at" in self.s:
                return [(k,) for k in pulls]
            if "WHERE sport = 'NBA' AND created_at = ANY" in self.s:
                return [(t, n, st, k) for k in self.p[0] for t, n, st in pulls[k]]
            return []

        def commit(self):
            pass

    _C.description = None
    hist = {"games": pd.DataFrame({"game_id": [GID], "season": [2027], "game_date": ["2026-10-21"],
                                   "home_team": ["LAL"], "away_team": ["GSW"], "commence_time": [tip.isoformat()]}),
            "asof": pd.DataFrame(columns=list(card.ASOF_COLS)),
            "log": pd.DataFrame({"game_id": [GID], "season": [2027]})}

    def _frame(conn, sql, params=()):
        rows = conn.execute(sql, params).fetchall()
        return pd.DataFrame(rows, columns=["team", "player_name", "status", "created_at"])

    orig = card._frame
    card._frame = _frame
    try:
        n = card.fill_espn_history(_C(), hist)
    finally:
        card._frame = orig
    listed = [r for r in written if r["status"] != pj.COVERED]
    assert n == len(written) and len(listed) == 1
    assert (listed[0]["player_name"], listed[0]["status"]) == ("Ann", "Questionable")
    assert all(r["report_ts"].startswith("2026-10-21T22:04:59") for r in written)


def test_pull_times_parse_with_a_bare_utc_offset():
    import scripts.nba_prop_projection_card as card
    t = card.pull_time("2026-10-16 12:17:30.660504+00")
    assert t == datetime(2026, 10, 16, 12, 17, 30, 660504, tzinfo=UTC)
    assert card.pull_time("not a time") is None


# ── every label publishes; every market settles, either side ─────────────────

@pytest.mark.parametrize("market", sorted(pj.MARKETS))
@pytest.mark.parametrize("side", ["over", "under"])
def test_every_label_passes_the_publishing_check(market, side):
    """A refused label is logged and the bet dropped, silently for the member."""
    from tracking.pick_integrity import pick_problems
    label = f"Victor Wembanyama {side.capitalize()} 2.5 {pj.MARKET_LABEL[market]}"
    assert pick_problems(label, side, 2.5, pj.MODEL_ID, prop_market=market) == []


_BOX = {"player_id": PID, "player_name": "Stephen Curry", "game_id": GID, "team": "GSW",
        "minutes": 34.0, "points": 24, "rebounds": 5, "offensive_reb": 1, "defensive_reb": 4,
        "assists": 7, "steals": 2, "blocks": 1, "turnovers": 3, "fg_made": 9, "fg_att": 19,
        "fg3_made": 4, "fg3_att": 10, "ft_made": 2, "ft_att": 2}


def _settle(side, line, market):
    import re
    import tracking.paper_tracker as pt

    class _C:
        def __init__(self, picks):
            self.picks, self.updates = picks, []

        def execute(self, sql, params=None):
            s = " ".join(sql.split())
            self._rows = []
            if s.upper().startswith("UPDATE"):
                self.updates.append((s, params))
                return self
            m = re.search(r"SELECT (.*?) FROM (\w+)", s, re.I)
            table = m.group(2) if m else ""
            if table == "picks":
                self._rows = self.picks
            elif table == "nba_player_game_log":
                cols = [c.strip().split()[-1].split(".")[-1] for c in m.group(1).split(",")]
                self._rows = [tuple(_BOX.get(c) for c in cols)]
            return self

        def fetchall(self):
            return self._rows

        def fetchone(self):
            return self._rows[0] if self._rows else None

    label = f"Stephen Curry {side.capitalize()} {line:g} {pj.MARKET_LABEL[market]}"
    conn = _C([("pk1", GID, pj.MODEL_ID, side, 110, 10.0, line, PID, label, market, "Stephen Curry")])
    pt._settle_prop_picks(conn, "2026-10-21", "2026-10-22T06:00:00Z")
    sql, params = [(s, p) for s, p in conn.updates if "SET result" in s][-1]
    return "NO_ACTION" if "'NO_ACTION'" in sql else params[0]


@pytest.mark.parametrize("side,line,market,expected", [
    ("over", 2.5, "player_blocks_steals", "WIN"),        # 2 steals + 1 block = 3
    ("under", 2.5, "player_blocks_steals", "LOSS"),
    ("under", 12.5, "player_rebounds_assists", "WIN"),   # 5 + 7 = 12
    ("over", 11.5, "player_rebounds_assists", "WIN"),
    ("over", 1.5, "player_steals", "WIN"),
    ("under", 3.5, "player_threes", "LOSS"),             # 4 threes
    ("under", 1.5, "player_blocks", "WIN"),
    ("under", 5.5, "player_rebounds", "WIN"),
])
def test_each_market_settles_either_side_from_the_box(side, line, market, expected):
    assert _settle(side, line, market) == expected


def test_publish_takes_the_rules_lock_before_its_own():
    """Every NBA prop write goes through the shared door, which takes nba_prop_market's lock and
    then this model's: two overlapping writers cannot both bet one game."""
    import scripts.nba_prop_projection_card as card
    import scripts.nba_props_card as door
    import scripts.nfl_wind_publisher as wp
    bets, _, decisions = _run([_q("draftkings", 1.5, +105, -135)])
    locks = []

    class _C:
        def execute(self, sql, params=None):
            self.sql = sql
            return self

        def fetchall(self):
            return []

        def fetchone(self):
            return ("x",) if "INSERT" in self.sql else None

        def commit(self):
            pass

    orig = wp._lock_model
    wp._lock_model = lambda conn, mid: locks.append(mid)
    try:
        door.publish_across_models(_C(), card.pick_rows(bets, 1000.0), [], decisions)
    finally:
        wp._lock_model = orig
    assert locks == ["nba_prop_market", "nba_prop_projection"]


# ── what the review found (2026-10-16) ───────────────────────────────────────

def test_a_stale_draftkings_quote_is_never_the_reference_price():
    """Discord posts dk_odds as the headline when it is no worse than the bet's price; a DraftKings
    quote the card refused as stale must not get there."""
    fresh = (TIP - timedelta(minutes=56)).isoformat()
    old = (TIP - timedelta(minutes=80)).isoformat()
    bets, _, _ = _run([_q("draftkings", 1.5, +120, -150, lu=old), _q("fanduel", 1.5, +105, -135, lu=fresh)])
    assert len(bets) == 1 and bets[0].book == "fanduel" and bets[0].dk_price is None


def test_the_ev_floor_is_the_markets_own_through_one_accessor():
    import config
    assert config.min_ev_for("nba_prop_projection") == 0.01
    for m, (_, floor) in pj.CARD.items():
        assert config.min_ev_for("nba_prop_projection", m) == floor
        assert floor == config.MODEL_MARKET_EV_FLOOR["nba_prop_projection"][m]
    assert config.min_ev_for("nba_prop_market", "player_steals") == config.min_ev_for("nba_prop_market")


def test_the_good_to_price_solves_the_markets_own_floor():
    """Blocks+Steals at p=0.55 decided at -110 (EV 0.05, its floor): -115 would have been refused,
    so 'good to' cannot reach it. The model-wide 0.01 floor said -119."""
    from tracking.discord_notifier import price_bound
    bound = price_bound(0.55, "nba_prop_projection", 0.0, -200, -110, "player_blocks_steals")
    assert bound == -110
    assert price_bound(0.55, "nba_prop_projection", 0.0, -200, -110) == -119
    import config
    p, dec = 0.55, 1 + 100 / 115
    assert p * dec - 1 < config.min_ev_for("nba_prop_projection", "player_blocks_steals")


def test_a_pick_near_its_tip_is_never_held_back_by_the_per_run_cap(monkeypatch):
    import config
    from tracking import discord_notifier as dn
    monkeypatch.setattr(config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    monkeypatch.setattr(config, "DISCORD_UNCAPPED_WITHIN_MIN", 120)
    now = datetime(2027, 4, 11, 21, 5, tzinfo=UTC)
    soon = [{"k": f"soon{i}", "commence": "2027-04-11T22:00:00+00:00"} for i in range(30)]
    later = [{"k": f"late{i}", "commence": "2027-04-12T02:00:00Z"} for i in range(10)]
    got = dn._cap_for_run(later[:5] + soon + later[5:], now=now)
    assert {s["k"] for s in got} == {s["k"] for s in soon}, "all 30 near-tip picks post; no room for later"
    many_later = [{"k": f"far{i}", "commence": "2027-04-12T02:00:00Z"} for i in range(30)]
    few = soon[:5]
    got = dn._cap_for_run(many_later + few + [{"k": "nostart", "commence": None}], now=now)
    assert len(got) == 20 and {s["k"] for s in few} <= {s["k"] for s in got}
    assert [s["k"] for s in got] == [s["k"] for s in many_later[:15] + few], "oldest first, near-tip all"


def test_the_free_pick_reads_the_price_of_its_own_bet():
    """Two bets on one player in one transaction share created_at; the free pick must join on the
    lock key (player AND market), not on player and side."""
    import inspect
    from tracking import discord_notifier as dn
    src = inspect.getsource(dn._free_pick_candidates)
    assert "{lock_key_sql('p')} = os.lock_key" in src


def test_the_posting_run_sends_every_near_tip_pick_over_the_cap(monkeypatch):
    """The run itself, not just the helper: 30 NBA bets for a game 55 minutes out all go out."""
    import config
    from tracking import discord_notifier as dn
    monkeypatch.setattr(config, "DISCORD_MAX_EMBEDS_PER_RUN", 20)
    tip = (datetime.now(UTC) + timedelta(minutes=55)).isoformat()
    sigs = [{"lock_key": f"k{i}", "sport": "NBA", "label": f"L{i}", "commence": tip} for i in range(30)]
    sent = []
    monkeypatch.setattr(dn, "_new_signals", lambda conn, d: sigs)
    monkeypatch.setattr(dn, "refuse_mismatched", lambda s, where: s)
    monkeypatch.setattr(dn, "_webhook_for_sport", lambda sport: "https://example.invalid/hook")
    monkeypatch.setattr(dn, "_post_picks", lambda url, sport, group, d: sent.extend(group) or [(group, "m1")])

    class _C:
        def execute(self, *a, **k):
            return self

        def commit(self):
            pass

    assert dn._post_new_signals(_C(), "2026-10-21", dry_run=False) == 30
    assert len(sent) == 30
