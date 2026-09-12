"""The best bettable price DECIDES a pre-game pick (2026-09-09).

mike: "we should remove DK only - we want best lines for us regardless."
Stage 2 of docs/best_line.md, authorised "stage 2 go" on 2026-09-03; the
re-sweep gate it carried was lifted by the "regardless" (no cut moved --
scripts/best_line_threshold_sweep.py found nothing shippable on 12 days of
best-price history, so every cut is simply applied at the better price, which
is 0.68pp looser on average and 3.61pp at the extreme).

What this pins, each watched failing against the pre-flip code:

  * a pick NONE at DraftKings becomes a BET at a better book's price, sized
    there, and the four decision_* columns say so; the DK columns keep their
    DraftKings meaning beside it;
  * the price floor (MODEL_MIN_ODDS) is judged at the deciding price;
  * a tie keeps DraftKings as the deciding book;
  * a quote past the pre-game cutoff, an in-play quote, or a quote that has
    gone stale cannot decide;
  * a live pick, a downgraded pick and a pick with no DraftKings price are
    left as decided at DraftKings;
  * every settle path grades at COALESCE(decision_odds, dk_odds), the
    emitted action-filter SQL cuts there, and the migration that adds the
    columns is registered, one statement, and guarded on its own properties.

Pure-function / static-source tests -- no network, no DB.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import config
from models import scorer
from models.scorer import (
    _best_game_price,
    _best_prop_price,
    _fresh_quotes,
    _requalify_at_best,
    american_to_implied_prob,
)

REPO = Path(__file__).resolve().parent.parent
MODEL = "mlb_moneyline"
PROP = "mlb_prop_pitcher_k"


def _source(rel: str) -> str:
    return (REPO / rel).read_text(encoding="utf-8")


@pytest.fixture
def _rules(monkeypatch):
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, MODEL, 0.07)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, MODEL, 0.60)
    monkeypatch.setitem(config.MODEL_EDGE_THRESHOLDS, PROP, 0.06)
    monkeypatch.setitem(config.MODEL_PROB_THRESHOLDS, PROP, 0.55)
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", config.MODEL_EDGE_THRESHOLDS)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", config.MODEL_PROB_THRESHOLDS)
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(scorer, "DECIDE_ON_BEST_PRICE", True)
    monkeypatch.setattr(scorer, "_is_paused", lambda mid: False)
    monkeypatch.setattr(scorer, "_blocked_by_min_odds", lambda mid, odds: False)


def _dk_pick(model_id=MODEL, prob=0.66, dk_odds=-150.0, **over):
    ip = american_to_implied_prob(dk_odds)
    p = {"model_id": model_id, "pick_label": "TEX ML", "model_probability": prob,
         "dk_implied_prob": round(ip, 4), "edge": round(prob - ip, 4),
         "dk_odds": dk_odds, "bankroll_at_pick": 1000.0,
         "signal_type": scorer._decide(model_id, prob, ip, prob - ip, dk_odds,
                                       is_prop=model_id.startswith("mlb_prop")),
         "kelly_fraction": 0.0, "recommended_bet": 0.0,
         **scorer._decision_fields("draftkings", dk_odds, ip, prob - ip)}
    p.update(over)
    return p


# ── the flip itself ──────────────────────────────────────────────────────────

def test_a_none_at_draftkings_becomes_a_bet_at_the_better_price(_rules):
    """0.66 against -150 (implied 0.600) is a 6.0pp edge: NONE at a 7pp cut.
    The same pick at -120 (implied 0.545) is 11.5pp: a BET, sized there."""
    p = _dk_pick()
    assert p["signal_type"] == "NONE"
    _requalify_at_best(p, {"book": "fanduel", "odds": -120.0, "link": "fd"}, is_prop=False)
    assert p["signal_type"] == "BET"
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == -120.0
    assert p["decision_edge"] == pytest.approx(0.66 - american_to_implied_prob(-120.0), abs=1e-4)
    assert p["kelly_fraction"] > 0 and p["recommended_bet"] > 0
    # The DraftKings columns are untouched -- they are the reference, not the decision.
    assert p["dk_odds"] == -150.0 and p["edge"] == pytest.approx(0.06, abs=1e-4)


def test_the_stake_is_sized_at_the_deciding_price(_rules):
    """Kelly at -120 is larger than Kelly at -150 for the same probability, and
    the pick carries the -120 number."""
    p = _dk_pick(prob=0.70)                       # BET at DK already
    at_dk = p["kelly_fraction"] = scorer._size(MODEL, 0.70, american_to_implied_prob(-150.0),
                                                1000.0, "BET", is_prop=False)[0]
    _requalify_at_best(p, {"book": "betmgm", "odds": -120.0, "link": None}, is_prop=False)
    assert p["kelly_fraction"] > at_dk


def test_the_price_floor_is_judged_at_the_deciding_price(monkeypatch, _rules):
    """A prop that fails the -140 floor at DraftKings' -165 passes it at another
    book's -135: the floor working at the price taken."""
    monkeypatch.setattr(scorer, "_blocked_by_min_odds",
                        lambda mid, odds: odds is not None and odds < -140)
    p = _dk_pick(model_id=PROP, prob=0.72, dk_odds=-165.0)
    assert p["signal_type"] == "NONE"
    _requalify_at_best(p, {"book": "fanduel", "odds": -135.0, "link": None}, is_prop=True)
    assert p["signal_type"] == "BET" and p["decision_odds"] == -135.0


def test_a_tie_keeps_draftkings_as_the_deciding_book(_rules):
    """_best_of keeps the first book on a tie and DraftKings is first in config
    order, so the shop returns DraftKings and the decision stays there."""
    p = _dk_pick(prob=0.70)
    _requalify_at_best(p, {"book": "draftkings", "odds": -150.0, "link": None}, is_prop=False)
    assert p["decision_book"] == "draftkings" and p["decision_odds"] == -150.0
    assert p["signal_type"] == "BET"


@pytest.mark.parametrize("why", ["live", "downgraded", "no_price", "flag_off", "no_best"])
def test_the_pick_stays_decided_at_draftkings_when(why, monkeypatch, _rules):
    p = _dk_pick()
    best = {"book": "fanduel", "odds": -120.0, "link": None}
    if why == "live":
        p["is_live"] = True
    elif why == "downgraded":
        p["downgrade_reason"] = "daily cap"
    elif why == "no_price":
        # No price ANYWHERE -- a prob-only model whose market no book lists.
        # Until 2026-09-12 this case keyed on dk_odds alone, which would now
        # exclude every pick scored off another book's line (dk_odds is NULL
        # on those by design) from the best-price re-check.
        p["dk_odds"] = None
        p["decision_odds"] = None
        p["decision_book"] = None
    elif why == "flag_off":
        monkeypatch.setattr(scorer, "DECIDE_ON_BEST_PRICE", False)
    elif why == "no_best":
        best = None
    before = dict(p)
    _requalify_at_best(p, best, is_prop=False)
    assert p == before


def test_the_edge_cap_is_not_reapplied_at_the_best_price(monkeypatch, _rules):
    """The cap guards the model's disagreement with the REFERENCE book, measured
    in the builders. A cheaper book pushing the decision edge past it is the
    price difference, not model noise."""
    monkeypatch.setattr(scorer, "MAX_EDGE_CAP", 0.10)
    p = _dk_pick(prob=0.69, dk_odds=-150.0)       # 9pp at DK, under the cap
    _requalify_at_best(p, {"book": "fanduel", "odds": +100.0, "link": None}, is_prop=False)
    assert p["decision_edge"] == pytest.approx(0.19, abs=1e-4)
    assert p["signal_type"] == "BET"


# ── the quotes that may decide ───────────────────────────────────────────────

class FakeConn:
    def __init__(self, rows):
        self._rows, self.params, self._sql = rows, None, ""

    def execute(self, sql, params=None):
        self.params, self._sql = params, sql
        return self

    def fetchall(self):
        return self._rows


def test_the_game_shop_is_bounded_at_the_pregame_cutoff():
    conn = FakeConn([])
    _best_game_price(conn, "g", "h2h", "home", None, cutoff="2026-09-09T23:05:00")
    assert "substr(snapshot_at, 1, 19) <= ?" in conn._sql
    assert conn.params[-1] == "2026-09-09T23:05:00"
    conn = FakeConn([])
    _best_game_price(conn, "g", "h2h", "home", None)
    assert "substr(snapshot_at" not in conn._sql, "no cutoff: fail open, no bound"


def test_the_prop_shop_is_bounded_and_pre_game_only():
    conn = FakeConn([])
    _best_prop_price(conn, "g", "Blake Snell", "pitcher_strikeouts", "over", 5.5,
                     cutoff="2026-09-09T23:05:00")
    assert "snapshot_at::timestamptz <= ?::timestamptz" in conn._sql
    assert "snapshot_type != 'in_play'" in conn._sql
    assert "ORDER BY snapshot_at::timestamptz DESC" in conn._sql
    assert conn.params[-1] == "2026-09-09T23:05:00"


def test_a_stale_quote_cannot_decide(monkeypatch):
    """A book whose newest quote is an hour behind the shop stopped pricing;
    its number is not on offer, however good it looks."""
    monkeypatch.setattr(scorer, "BEST_LINE_MAX_LAG_MIN", 30.0)
    rows = [
        ("draftkings", -150, None, None, None, "2026-09-09T18:00:00Z"),
        ("fanduel", -110, None, None, None, "2026-09-09T16:30:00Z"),   # 90 min stale
        ("betmgm", -140, None, None, None, "2026-09-09T17:58:00Z"),
    ]
    best = _best_game_price(FakeConn(rows), "MLB_2026-09-09_NYY_BOS", "h2h", "home", None)
    assert best["book"] == "betmgm"


def test_a_quote_with_no_stamp_is_kept():
    """Fail open: a missing timestamp must not delete a book from the shop."""
    kept = _fresh_quotes([{"book": "a", "odds": -110, "snapshot_at": None},
                          {"book": "b", "odds": -120, "snapshot_at": "2026-09-09T18:00:00Z"}])
    assert [q["book"] for q in kept] == ["a", "b"]


def test_the_prop_shop_still_matches_on_the_line():
    rows = [
        ("draftkings", -140, "dk", 5.5, "2026-09-09T18:00:00Z"),
        ("fanduel", -105, "fd", 6.5, "2026-09-09T18:00:00Z"),   # different bet
        ("betmgm", -125, "mgm", 5.5, "2026-09-09T18:00:00Z"),
    ]
    best = _best_prop_price(FakeConn(rows), "g", "Blake Snell", "pitcher_strikeouts", "over", 5.5)
    assert best["book"] == "betmgm"


# ── one code path, every surface ─────────────────────────────────────────────

def test_the_prop_lanes_requalify_before_dedupe_sees_the_signal():
    """Every _tag_prop call passes conn, so the best price is resolved and the
    pick re-decided where it is built -- before dedupe_player_props, the daily
    caps and the first-signal lock read signal_type."""
    src = _source("models/scorer.py")
    calls = re.findall(r"_tag_prop\(pick, _best_ctx(, conn)?\)", src)
    assert calls and all(c == ", conn" for c in calls), calls
    ctxs = re.findall(r"_best_ctx = \(game_id,\s*\n\s*\(prop_odds or \{\}\)\.get\(\"player_name\"\) or player_name,\s*\n\s*market, (\w+)\.get\(game_id\)\)", src)
    assert len(ctxs) == 5 and set(ctxs) <= {"cut_map", "cutoffs"}, ctxs


def test_every_scorer_insert_carries_the_decision_columns():
    src = _source("models/scorer.py")
    ins = src[src.index("def _insert_picks("):]
    for col in ("decision_book", "decision_odds", "decision_implied_prob", "decision_edge"):
        assert f"%({col})s" in ins, col


def test_the_emitted_action_filter_cuts_at_the_deciding_price():
    from scripts.emit_threshold_sql import emit
    sql = emit("p.")
    assert "COALESCE(p.decision_edge, p.edge) >= " in sql
    assert "COALESCE(p.decision_odds, p.dk_odds) >= " in sql
    assert " p.edge >= " not in sql and " p.dk_odds >= " not in sql


def test_the_migration_is_registered_one_statement_and_guarded():
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "decide_on_best_price_2026_09_09.sql"
    assert name in ACTIVE_MIGRATIONS
    # Before the two view files that now cut on its columns.
    assert ACTIVE_MIGRATIONS.index(name) < ACTIVE_MIGRATIONS.index("track_record_reads_graded_matview.sql")
    code = "\n".join(l for l in _source(f"data/migrations/{name}").splitlines()
                     if not l.lstrip().startswith("--"))
    assert code.count("$mig$") == 2 and code.split("$mig$")[-1].strip() == ";"
    for guard in ("column_name = 'decision_edge'", "attname = 'decision_edge'",
                  "position('decision_edge' in d) = 0", "position('decision_odds' in d) = 0"):
        assert guard in code, guard


def test_the_restore_carries_the_deciding_price():
    from tracking.first_signal_repair import _COPY_COLS
    for col in ("decision_book", "decision_odds", "decision_implied_prob", "decision_edge"):
        assert col in _COPY_COLS


def test_the_schema_and_the_column_runner_carry_the_columns():
    from data.db_setup import _MIGRATIONS
    have = {(t, c) for t, c, _ in _MIGRATIONS}
    for t in ("picks", "picks_log"):
        for c in ("decision_book", "decision_odds", "decision_implied_prob", "decision_edge"):
            assert (t, c) in have, (t, c)
