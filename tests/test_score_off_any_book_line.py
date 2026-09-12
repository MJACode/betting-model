"""Scoring a prop off another book's line when DraftKings does not list it.

mike, 2026-09-12: "Yes, scoring of other books lines."

Measured over the markets an ACTIVE model prices, 2026-08-28 onward:
DraftKings listed 11,780 player propositions and the bettable books listed
1,357 more that it did not -- four fifths of them FanDuel, Hard Rock,
Fanatics and Caesars. Every one of those produced no pick at all.

The two properties these tests exist to hold:

  1. THE LINE IS THE PROPOSITION. The book is taken in BEST_LINE_BOOKMAKERS
     order, never by whose number the model likes best -- otherwise the bet is
     chosen to suit the model. The ordinary best-price check then runs at that
     line, so the pick is still placed at the best bettable price on the same
     number.

  2. THE DraftKings COLUMNS MEAN DraftKings. dk_odds / dk_implied_prob / edge
     stay NULL / 0.0 on these rows, because DraftKings never quoted the
     proposition; the price that decided is in decision_*, and `line_book`
     says who set the number so the population can be graded on its own.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

import config
from models import scorer
from models.scorer import (_fallback_line_quote, _get_prop_dk_odds,
                           _make_prop_pick, _requalify_at_best)

ROOT = Path(__file__).parent.parent


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


class _FakeConn:
    """execute(sql, params).fetchone()/fetchall(), keyed on the bookmaker the
    query asks for. `rows` maps book -> the 5-tuple the query selects."""

    def __init__(self, rows: dict):
        self.rows = rows
        self.asked: list[str] = []
        self._last = None

    def execute(self, sql, params=None):
        self._last = (sql, params or ())
        return self

    def fetchone(self):
        sql, params = self._last
        if "FROM player_prop_odds" not in sql:
            return None
        book = params[3] if len(params) > 3 else "draftkings"
        self.asked.append(book)
        return self.rows.get(book)

    def fetchall(self):
        return []


def _row(line=5.5, over=-120, under=100):
    return (line, over, under, "over-link", "under-link")


@pytest.fixture
def _on(monkeypatch):
    monkeypatch.setattr(scorer, "SCORE_OFF_ANY_BOOK_LINE", True)
    monkeypatch.setattr(scorer, "BEST_LINE_BOOKMAKERS",
                        ["draftkings", "fanduel", "betmgm", "hardrockbet"])


# ── which book sets the line ─────────────────────────────────────────────────

def test_the_first_bettable_book_in_config_order_sets_the_line(_on):
    conn = _FakeConn({"betmgm": _row(line=6.5, over=-105),
                      "fanduel": _row(line=5.5, over=-140)})
    q = _fallback_line_quote(conn, "G", "Player", "pitcher_strikeouts")
    assert q["line_book"] == "fanduel" and q["line"] == 5.5
    assert q["over_price"] == -140, (
        "config order, NOT the better price -- the line is the proposition")


def test_draftkings_is_not_asked_twice(_on):
    conn = _FakeConn({"fanduel": _row()})
    _fallback_line_quote(conn, "G", "Player", "pitcher_strikeouts")
    assert "draftkings" not in conn.asked, "the caller already tried DraftKings"


def test_a_book_with_a_line_but_no_price_is_skipped(_on):
    conn = _FakeConn({"fanduel": (5.5, None, None, None, None),
                      "betmgm": _row(line=5.5, over=-110)})
    assert _fallback_line_quote(conn, "G", "P", "m")["line_book"] == "betmgm"


def test_a_book_with_a_price_but_no_line_is_skipped(_on):
    conn = _FakeConn({"fanduel": (None, -110, -110, None, None),
                      "betmgm": _row(line=5.5)})
    assert _fallback_line_quote(conn, "G", "P", "m")["line_book"] == "betmgm"


def test_no_bettable_book_lists_it_is_none_not_a_crash(_on):
    assert _fallback_line_quote(_FakeConn({}), "G", "P", "m") is None


def test_the_flag_off_restores_no_draftkings_no_pick(monkeypatch, _on):
    monkeypatch.setattr(scorer, "SCORE_OFF_ANY_BOOK_LINE", False)
    conn = _FakeConn({"fanduel": _row()})
    assert _fallback_line_quote(conn, "G", "P", "m") is None
    assert conn.asked == [], "the flag must short-circuit before any read"


def test_the_read_is_bounded_and_excludes_in_play(_on):
    """Same two guards the DraftKings read carries: a pre-game pick may never
    be priced off an in-play row, and the evening refresh keeps writing 'open'
    rows after first pitch (CLAUDE.md section 7)."""
    conn = _FakeConn({"fanduel": _row()})
    _fallback_line_quote(conn, "G", "P", "m", "2026-09-12T23:05:00Z")
    sql = conn._last[0]
    assert "snapshot_type IS NULL OR snapshot_type != 'in_play'" in sql
    assert "snapshot_at::timestamptz <= %s::timestamptz" in sql


def test_the_draftkings_hit_says_draftkings_set_the_line(_on):
    conn = _FakeConn({"draftkings": _row()})
    q = _get_prop_dk_odds(conn, "G", "Player", "pitcher_strikeouts")
    assert q["line_book"] is None, "NULL means DraftKings, on the row too"


# ── what the pick then looks like ────────────────────────────────────────────

@pytest.fixture
def _cut(monkeypatch):
    monkeypatch.setattr(config, "MODEL_PROB_THRESHOLDS", {"m": 0.55}, raising=False)
    monkeypatch.setattr(scorer, "MODEL_PROB_THRESHOLDS", {"m": 0.55})
    monkeypatch.setattr(scorer, "MODEL_EDGE_THRESHOLDS", {"m": 0.05})
    monkeypatch.setattr(scorer, "MODEL_MIN_ODDS", {})
    monkeypatch.setattr(scorer, "PROB_ONLY_MODELS", set())
    monkeypatch.setattr(scorer, "PAUSED_MODELS", set())
    # The AUTOMATIC pauses too: _is_paused also reads model_auto_pauses
    # (_auto_paused_models), so stubbing the config constant alone leaves the
    # test reading production state -- see test_prop_calibrated_decision.
    monkeypatch.setattr(scorer, "_auto_paused_models", lambda: set())
    monkeypatch.setattr(scorer, "DECIDE_ON_CALIBRATED_PROB", False)
    monkeypatch.setattr(scorer, "MAX_EDGE_CAP", 0.30)


def _pick(line_book, odds=-110.0, prob=0.62):
    implied = scorer.american_to_implied_prob(odds)
    return _make_prop_pick(
        game_id="G", model_id="m", game_date="2026-09-12",
        player_name="Player", pick_side="over", model_prob=prob,
        dk_implied_prob=implied, edge=prob - implied, dk_odds=odds,
        line=5.5, bankroll=1000.0, stat_label="Ks",
        dk_bet_link="dk-link", line_book=line_book)


def test_a_pick_off_another_books_line_carries_no_draftkings_numbers(_cut):
    p = _pick("fanduel")
    assert p["line_book"] == "fanduel"
    assert p["dk_odds"] is None, "DraftKings never quoted this proposition"
    assert p["dk_implied_prob"] == 0.0 and p["edge"] == 0.0
    assert p["dk_bet_link"] is None, "a DraftKings slip would open empty"
    assert p["decision_book"] == "fanduel" and p["decision_odds"] == -110.0
    assert p["decision_edge"] > 0 and p["decision_implied_prob"] > 0


def test_the_same_pick_at_draftkings_keeps_its_draftkings_numbers(_cut):
    p = _pick(None)
    assert p["line_book"] is None
    assert p["dk_odds"] == -110.0 and p["edge"] > 0
    assert p["decision_book"] == "draftkings" and p["dk_bet_link"] == "dk-link"


def test_the_cut_is_applied_at_that_books_price(_cut):
    """The model's own cut, unchanged, judged at the price that exists."""
    assert _pick("fanduel", odds=-110.0, prob=0.62)["signal_type"] == "BET"
    # -190: implied 0.655 against a 0.62 model, so the edge is -0.035 -- inside
    # the dead zone in both directions, which is a NONE row, not a signal.
    assert _pick("fanduel", odds=-190.0, prob=0.62)["signal_type"] == "NONE"


def test_such_a_pick_is_still_re_checked_at_the_best_price(_cut, monkeypatch):
    """The re-check used to key on dk_odds, which is NULL on every one of
    these by design -- keying there would have excluded exactly the picks
    this change creates."""
    monkeypatch.setattr(scorer, "DECIDE_ON_BEST_PRICE", True)
    p = _pick("fanduel", odds=-190.0, prob=0.62)
    assert p["signal_type"] == "NONE"
    _requalify_at_best(p, {"book": "betmgm", "odds": -105.0, "link": "mgm"},
                       is_prop=True)
    assert p["signal_type"] == "BET"
    assert p["decision_book"] == "betmgm" and p["decision_odds"] == -105.0
    assert p["dk_odds"] is None, "still no DraftKings price, still NULL"


def test_a_pick_with_no_price_anywhere_is_left_alone(_cut, monkeypatch):
    monkeypatch.setattr(scorer, "DECIDE_ON_BEST_PRICE", True)
    p = _pick(None, odds=-110.0)
    p["dk_odds"] = p["decision_odds"] = p["decision_book"] = None
    before = dict(p)
    _requalify_at_best(p, {"book": "betmgm", "odds": -105.0, "link": None},
                       is_prop=True)
    assert p == before


# ── the column reaches the row, the log and the app ─────────────────────────

def test_every_prop_build_site_passes_the_line_book():
    src = _src("models/scorer.py")
    assert src.count("pick = _make_prop_pick(") == \
        src.count("line_book=(prop_odds or {}).get('line_book'),"), (
        "a build site that forgets line_book writes the other book's price "
        "into picks.dk_odds")


def test_the_insert_carries_the_column():
    src = _src("models/scorer.py")
    body = src[src.index("def _insert_picks("):]
    body = body[:body.index("\ndef ")]
    assert "line_book," in body and "%(line_book)s," in body
    assert '"line_book":          p.get("line_book")' in body


def test_the_audit_copy_carries_the_column():
    assert '"line_book",' in _src("tracking/first_signal_repair.py")


def test_the_schema_creates_and_migrates_the_column():
    src = _src("data/db_setup.py")
    assert '("picks", "line_book", "TEXT"),' in src
    assert '("picks_log", "line_book", "TEXT"),' in src
    assert "line_book             TEXT," in src


# ── the migration ────────────────────────────────────────────────────────────

MIG = "score_off_any_book_line_2026_09_12.sql"


def test_the_migration_is_registered_before_the_view_files():
    order = _src("data/view_migrations.py")
    assert MIG in order
    assert order.index(MIG) < order.index("track_record_reads_graded_matview.sql")


def test_the_migration_is_one_guarded_idempotent_block():
    sql = _src(f"data/migrations/{MIG}")
    assert sql.count("DO $mig$") == 1 and sql.count("END $mig$;") == 1
    # guarded on the property each step establishes, never on its own shape
    assert "column_name = 'line_book'" in sql
    assert "position('line_book' in d) = 0" in sql
    assert "IF position(new_profit in d) > 0 THEN" in sql


def test_published_units_gate_on_the_deciding_price():
    """The gate exists because settlement fabricates -110 for an unpriced
    pick. A pick scored off FanDuel's line and settled at FanDuel's price is
    priced -- leaving the gate on dk_odds would bet it and never count it."""
    sql = _src(f"data/migrations/{MIG}")
    assert "COALESCE(p.decision_odds, p.dk_odds) IS NOT NULL" in sql
    assert "v_public_track_record" in sql and "v_public_track_record_daily" in sql
    # and the file that owns that property must not fight this one
    marker = _src("data/migrations/require_price_for_published_units.sql")
    assert "decision_profit CONSTANT text" in marker
    assert "position(decision_profit in d) > 0" in marker


def test_the_trigger_copies_line_book():
    sql = _src(f"data/migrations/{MIG}")
    fn = sql[sql.index("CREATE OR REPLACE FUNCTION public.log_picks_changes"):]
    fn = fn[:fn.index("$fn$;")]
    assert fn.count("line_book") == 2, "named in the column list AND the values"
    assert "r.line_book" in fn


# ── the app ──────────────────────────────────────────────────────────────────

def test_a_pick_draftkings_never_priced_cannot_be_a_parlay_leg():
    """A parlay is ONE DraftKings slip. `legFromPick` keys on dk_odds, which is
    NULL on these picks -- so the gate that keeps a prob-only pick out keeps
    these out too, and that is the correct answer, not an oversight. Pinned
    because a tidy-up of the comment could widen it to the deciding price and
    put an unplaceable leg on a slip (UX review, 2026-09-12)."""
    src = _src("mobile/src/lib/parlay.ts")
    body = src[src.index("export function legFromPick("):]
    body = body[:body.index("\nexport ")]
    assert "p.dk_odds == null ? null : Number(p.dk_odds)" in body
    assert "a parlay is ONE DraftKings slip" in body.replace("  ", " ").replace("\n", " ") \
        or "ONE DraftKings slip" in src


def test_the_app_reads_the_column_but_does_not_claim_a_settled_one():
    types = _src("mobile/src/types/index.ts")
    assert "  line_book: string | null;" in types, "every Pick carries it"
    key = types[types.index("export type SettledPickKey ="):types.index("export type SettledPick =")]
    assert "'line_book'" not in key, (
        "the settled screens name a book through decision_book; adding this "
        "column there costs every member a full re-download for nothing")
    q = _src("mobile/src/lib/queries.ts")
    assert "decision_edge, line_book';" in q, "the board read carries it"
    row = q[q.index("FullOutcomePickRow"):]
    row = row[:row.index("}")]
    assert "line_book: string | null;" not in row, (
        "v_model_full_outcome_picks does not return it -- declaring it would "
        "make every row read undefined and claim DraftKings' line")


def test_no_app_copy_calls_the_line_draftkings_unconditionally():
    """The two blockers the UX review caught: a recap row that says 'record
    only' about units the day's total already counted, and a reasoning row
    that names DraftKings as the source of a line DraftKings never posted."""
    recap = _src("mobile/src/components/DailyResultsModal.tsx")
    assert "decisionOdds(pick) == null" in recap
    assert "RECORD_ONLY_MODELS.has(pick.model_id) || pick.dk_odds == null" not in recap
    reasoning = _src("mobile/src/components/ReasoningCard.tsx")
    assert "The DK line when we generated this pick." not in reasoning
    assert "lineBook(pick)" in reasoning
