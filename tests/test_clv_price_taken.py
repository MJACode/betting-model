"""CLV grades the price the pick was TAKEN at, at the book it was taken at.

mike, 2026-10-08: "grade CLV at the price taken". Until this change
_capture_clv graded `dk_odds` against a DraftKings lock snapshot whenever
DraftKings hung the line, even when the pick was decided and settled at
another book (docs/followups.md, "CLV is graded at DraftKings' price").

The price is COALESCE(decision_odds, dk_odds). The book is decision_book, else
the book named in the label (the market-relative prop cards' "(FD)" suffix and
the NFL cards' "(Wind 11 mph, FD)" form), else DraftKings. The lock two-way is
read at THAT book at created_at; the close is Pinnacle, else that book.

Five row shapes, measured on production 2026-10-08 (BET, not live):
  A  dk_odds = DraftKings' own price, decision_* = a better book     153 rows
  B  dk_odds = decision_odds, decision_book = the line book (MLB cards) 51
  C  dk_odds NULL, decision_* set (lines DraftKings never hung)        30
  D  dk_odds = soft price, book only in the "(FD)" label suffix        113
  E  dk_odds = best-book price, book only in "(…, FD)" (NFL cards)     31
A, B and E change. C and D were already graded at the price taken.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime
from pathlib import Path

import pytest

from tracking import clv_math
from tracking import paper_tracker as pt
from tracking.clv_math import price_clv_pct

ROOT = Path(__file__).parent.parent
LEGACY = "graded_at_dk_legacy"
MIGRATION = "clv_price_taken_2026_10_08.sql"


def _ts(v) -> datetime:
    s = str(v).replace("Z", "+00:00")
    return datetime.fromisoformat(s + ":00" if re.search(r"[+-]\d\d$", s) else s)


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


_GAME_COLS = ("home_price", "away_price", "draw_price", "spread_home",
              "total_line", "over_price", "under_price")


class _Conn:
    """Answers the statements _capture_clv issues for a GAME-LINE pick.

    quotes: (book, market, snapshot_at, {col: value}). UPDATEs are parsed by
    column name, so a capture that does not write a column fails on the key.
    """

    def __init__(self, picks, quotes):
        self.picks, self.quotes = picks, quotes
        self.updates: list[dict] = []

    def execute(self, sql, params=()):
        s = " ".join(sql.split())
        if s.startswith("SELECT p.pick_id"):
            cols = [c.strip().split(".")[-1] for c in s[7:s.index(" FROM picks")].split(",")]
            return _Res([tuple(p[c] for c in cols) for p in self.picks
                         if p["game_date"] == params[0]])
        if "FROM odds" in s:
            game_id, market, book, bound = params
            rows = sorted((q for q in self.quotes
                           if q[0] == book and q[1] == market and _ts(q[2]) <= _ts(bound)),
                          key=lambda q: _ts(q[2]), reverse=True)
            if "ABS(spread_home) = 1.5" in s:
                rows = [q for q in rows if abs(q[3].get("spread_home") or 0) == 1.5]
            return _Res([tuple(q[3].get(c) for c in _GAME_COLS) for q in rows[:1]])
        if s.startswith("UPDATE picks"):
            set_part = s[s.index(" SET ") + 5:s.index(" WHERE ")]
            keys = [a.split("=")[0].strip() for a in set_part.split(",")] + ["pick_id"]
            assert len(keys) == len(params), s
            self.updates.append(dict(zip(keys, params)))
            return _Res([])
        raise AssertionError(f"unexpected statement: {s[:80]}")


def _pick(**kw):
    base = dict(pick_id=1, game_id="MLB_2026-09-20_NYY_BOS", model_id="mlb_over_under",
                pick_side="over", dk_odds=-115.0, commence_time="2026-09-20T23:05:00Z",
                pick_label="BOS vs NYY Over 8.5", scored_line=8.5,
                created_at="2026-09-20 15:00:00+00", prop_market=None, clv_method=None,
                decision_odds=-105.0, decision_book="betmgm", game_date="2026-09-20")
    base.update(kw)
    base.setdefault("game_time", base["commence_time"])   # the start the pick was written against
    return base


LOCK, CLOSE = "2026-09-20T14:55:00Z", "2026-09-20T23:00:00Z"
TOTALS = [  # group A: DraftKings -115, BetMGM -105 at the same 8.5
    ("draftkings", "totals", LOCK, dict(total_line=8.5, over_price=-115, under_price=-105)),
    ("betmgm", "totals", LOCK, dict(total_line=8.5, over_price=-105, under_price=-115)),
    ("draftkings", "totals", CLOSE, dict(total_line=8.5, over_price=-125, under_price=105)),
    ("betmgm", "totals", CLOSE, dict(total_line=8.5, over_price=-118, under_price=-102)),
    ("pinnacle", "totals", CLOSE, dict(total_line=8.5, over_price=-120, under_price=104)),
]


# ── the resolver ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("model_id, dk, dec, dec_book, label, want", [
    # A: decided at another book -> that price at that book
    ("mlb_over_under", -115.0, -105.0, "BetMGM", "BOS vs NYY Over 8.5", (-105.0, "betmgm")),
    # B: same price, other book
    ("mlb_spread_market", 130.0, 130.0, "fanduel", "BOS +1.5 (FD)", (130.0, "fanduel")),
    # decided at DraftKings since the flip -> unchanged
    ("mlb_moneyline", -120.0, -120.0, "draftkings", "NYY ML", (-120.0, "draftkings")),
    # before the flip: no decision_* -> DraftKings
    ("mlb_moneyline", -120.0, None, None, "NYY ML", (-120.0, "draftkings")),
    # C: no DraftKings price
    ("nhl_prop_saves", None, -115.0, "hardrockbet", "X Under 25.5 Saves", (-115.0, "hardrockbet")),
    # D: market-relative label suffix (unchanged)
    ("nfl_prop_market", -120.0, None, None, "A Player Under 1.5 Rec (FD)", (-120.0, "fanduel")),
    ("wnba_prop_market", 105.0, None, None, "A Player Over 8.5 Ast (fliff)", (105.0, "fliff")),
    # E: the NFL cards' comma form, abbreviations and raw keys
    ("nfl_wind_totals", -110.0, None, None,
     "SEA @ WAS Under 40.5 (Wind 13 mph, MGM) · 0.83u", (-110.0, "betmgm")),
    ("nfl_wind_totals", -109.0, None, None,
     "PIT @ CLE Under 38.5 (Wind 11 mph, CZR) · 1.19u", (-109.0, "williamhill_us")),
    ("nfl_opener_spread", -112.0, None, None,
     "HOU @ TEN — TEN +9.5 (Opener +2 vs Pinnacle, BR) · 1.67u · NEW 0m", (-112.0, "betrivers")),
    ("nfl_wind_totals", -110.0, None, None,
     "CAR @ CLE Under 42.5 (Wind 11 mph, fanatics) · 0.78u", (-110.0, "fanatics")),
    ("nfl_wind_totals", -105.0, None, None,
     "DEN @ KC Under 43.5 (Wind 12 mph, DK) · 1.15u", (-105.0, "draftkings")),
    # a parenthesis on a model that never names a book in its label is NOT a book
    ("mlb_f5_moneyline", -130.0, None, None, "NYY ML (F5)", (-130.0, "draftkings")),
    # nothing priced
    ("mlb_moneyline", None, None, None, "NYY ML", (None, None)),
])
def test_the_bet_is_the_price_taken_at_the_book_it_was_taken(model_id, dk, dec, dec_book,
                                                             label, want):
    assert pt._bet_price_and_book(model_id, dk, dec, dec_book, label) == want


def test_the_nfl_label_map_is_the_inverse_of_the_nfl_publisher():
    """The NFL cards write BOOK_ABBREV.get(book, book). A book the resolver
    cannot map back would be graded at DraftKings, silently."""
    tree = ast.parse((ROOT / "scripts" / "nfl_wind_publisher.py").read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", "") == "BOOK_ABBREV")
    abbrev = ast.literal_eval(node.value)
    for book, tag in abbrev.items():
        if not re.fullmatch(r"[A-Za-z_]+", tag) or book == "caesars":
            continue        # "MB (exch.)" cannot be a label token; caesars == williamhill_us
        assert pt._NFL_LABEL_BOOK[tag] == book, tag


# ── capture, by row shape ─────────────────────────────────────────────────────

def test_group_a_grades_the_deciding_price_against_the_deciding_books_lock():
    conn = _Conn([_pick()], TOTALS)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(-105.0, -120, [104], book="pinnacle",
                            bet_other_prices=[-115], bet_book="betmgm")
    master, _ = price_clv_pct(-115.0, -120, [104], book="pinnacle",
                              bet_other_prices=[-105], bet_book="draftkings")
    assert want != master
    assert (u["clv_pct"], u["clv_close_book"], u["clv_bet_book"]) == (want, "pinnacle", "betmgm")


def test_without_pinnacle_the_close_stays_draftkings_only_the_bet_side_moved():
    """Only the BET moved to the price taken. A soft book's "close" is
    junk-prone (pick 2899429: Fanatics -110/-130 against DraftKings +380/-600),
    so a pick at DraftKings' line still closes Pinnacle, else DraftKings."""
    conn = _Conn([_pick()], [q for q in TOTALS if q[0] != "pinnacle"])
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(-105.0, -125, [105], book="draftkings",
                            bet_other_prices=[-115], bet_book="betmgm")
    assert (u["clv_close_book"], u["closing_dk_odds"], u["clv_pct"], u["clv_bet_book"]) ==         ("draftkings", -125, want, "betmgm")


def test_the_close_is_bounded_by_the_start_the_pick_was_written_against():
    """games.commence_time moves after puck drop (the feed's :10 became
    00:10:37 on 2026-10-08). A close read against the later time took a quote
    45 s after the start. The earlier of the two starts bounds the close."""
    pick = _pick(commence_time="2026-09-20T23:15:00Z", game_time="2026-09-20T23:05:00Z")
    quotes = TOTALS + [("pinnacle", "totals", "2026-09-20T23:10:00Z",
                        dict(total_line=8.5, over_price=-150, under_price=130))]
    conn = _Conn([pick], quotes)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    assert u["closing_dk_odds"] == -120      # Pinnacle at 23:00, not the 23:10 in-play quote


def test_group_b_same_price_reads_the_lock_at_the_line_book():
    """mlb_spread_market writes the line book's price into dk_odds AND
    decision_odds. The DraftKings lock never shows that price (0 of 28
    measured), so the bet kept its margin while the close lost it."""
    pick = _pick(game_id="MLB_2026-09-17_SEA_HOU", model_id="mlb_spread_market",
                 pick_side="away", dk_odds=130.0, decision_odds=130.0,
                 decision_book="fanduel", scored_line=1.5,
                 pick_label="SEA -1.5 (FD)", game_date="2026-09-17",
                 commence_time="2026-09-17T23:05:00Z",
                 created_at="2026-09-17 15:00:00+00")
    quotes = [
        ("draftkings", "spreads", "2026-09-17T14:50:00Z", dict(spread_home=1.5, home_price=-160, away_price=135)),
        ("fanduel", "spreads", "2026-09-17T14:50:00Z", dict(spread_home=1.5, home_price=-155, away_price=130)),
        ("pinnacle", "spreads", "2026-09-17T23:00:00Z", dict(spread_home=1.5, home_price=-150, away_price=136)),
    ]
    conn = _Conn([pick], quotes)
    assert pt._capture_clv(conn, "2026-09-17", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(130.0, 136, [-150], book="pinnacle",
                            bet_other_prices=[-155], bet_book="fanduel")
    raw, _ = price_clv_pct(130.0, 136, [-150], book="pinnacle")
    assert want != raw
    assert (u["clv_pct"], u["clv_bet_book"]) == (want, "fanduel")


def test_group_e_reads_the_nfl_cards_book_out_of_the_label():
    """Pick 2780826 as stored: SEA @ WAS Under 40.5 at BetMGM -110. BetMGM's
    lock two-way was -108/-110; DraftKings' was -102/-118; Pinnacle closed
    +101/-116. Stored -0.47 (raw bet implied); at the price taken +1.69."""
    pick = _pick(game_id="NFL_2026_03_SEA_WAS", model_id="nfl_wind_totals",
                 pick_side="under", dk_odds=-110.0, decision_odds=None, decision_book=None,
                 scored_line=40.5, pick_label="SEA @ WAS Under 40.5 (Wind 13 mph, MGM) · 0.83u",
                 created_at="2026-09-24 00:20:09.294539+00",
                 commence_time="2026-09-27T17:00:00+00:00", game_date="2026-09-27")
    quotes = [
        ("betmgm", "totals", "2026-09-24T00:19:51Z", dict(total_line=40.5, over_price=-108, under_price=-110)),
        ("draftkings", "totals", "2026-09-24T00:19:43Z", dict(total_line=40.5, over_price=-102, under_price=-118)),
        ("pinnacle", "totals", "2026-09-26T23:00:34Z", dict(total_line=40.5, over_price=101, under_price=-116)),
    ]
    conn = _Conn([pick], quotes)
    assert pt._capture_clv(conn, "2026-09-27", "TS") == 1
    (u,) = conn.updates
    assert (u["clv_pct"], u["clv_bet_book"], u["clv_close_book"]) == (1.69, "betmgm", "pinnacle")


def test_a_draftkings_decided_row_is_unchanged():
    pick = _pick(dk_odds=-115.0, decision_odds=-115.0, decision_book="draftkings")
    conn = _Conn([pick], TOTALS)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    want, _ = price_clv_pct(-115.0, -120, [104], book="pinnacle",
                            bet_other_prices=[-105], bet_book="draftkings")
    assert (u["clv_pct"], u["clv_bet_book"]) == (want, "draftkings")


# ── the recompute of rows graded under the DraftKings rule ───────────────────

def test_a_legacy_stamped_row_is_re_measured_and_leaves_the_queue():
    pick = _pick(clv_method=LEGACY)
    conn = _Conn([pick], TOTALS)
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 1
    (u,) = conn.updates
    assert (u["clv_method"], u["clv_bet_book"]) == ("no_vig", "betmgm")


def test_a_legacy_row_that_cannot_be_re_measured_is_marked_visited_not_requeued():
    """No close at any book (a pruned history, a renamed player). The old
    number stays on the row, stamped legacy so the pedigree keeps excluding
    it, and clv_bet_book marks it visited so the backfill does not re-walk
    its date forever (the self-healing-backfill rule)."""
    pick = _pick(clv_method=LEGACY)
    # Only BetMGM quoted: neither Pinnacle nor DraftKings has a close.
    conn = _Conn([pick], [q for q in TOTALS if q[0] == "betmgm"])
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 0
    (u,) = conn.updates
    assert u == {"clv_bet_book": "betmgm", "pick_id": 1}


def test_an_ordinary_row_with_no_close_is_left_for_a_later_pass():
    """Regression guard (passes on master too): an un-stamped row with no
    quote anywhere is not stamped captured."""
    conn = _Conn([_pick()], [])
    assert pt._capture_clv(conn, "2026-09-20", "TS") == 0
    assert conn.updates == []


def _fn(name: str) -> str:
    text = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(text))
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


def test_both_queues_revisit_the_legacy_stamp_once():
    clause = "OR (p.clv_method = %s AND p.clv_bet_book IS NULL)"
    for name in ("_backfill_clv", "_capture_clv"):
        src = _fn(name)
        assert clause in " ".join(src.split()), name
        assert "CLV_METHOD_DK_GRADED_LEGACY" in src, name


def test_the_legacy_stamp_never_enters_the_pedigree():
    from tracking import model_quality
    assert clv_math.CLV_METHOD_DK_GRADED_LEGACY == LEGACY
    assert LEGACY not in clv_math.PEDIGREE_CLV_METHODS
    assert LEGACY not in model_quality.CLV_METHODS
    view = (ROOT / "data" / "migrations" / "record_excludes_paused_rows_2026_09_28.sql"
            ).read_text(encoding="utf-8")
    assert "clv_method IN ('no_vig','zero_vig')" in view


# ── the migration ─────────────────────────────────────────────────────────────

def _migration() -> str:
    return (ROOT / "data" / "migrations" / MIGRATION).read_text(encoding="utf-8")


def test_the_migration_is_on_the_worker_list_after_the_method_column():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIGRATION in ACTIVE_MIGRATIONS
    assert (ACTIVE_MIGRATIONS.index("add_clv_method_2026_09_14.sql")
            < ACTIVE_MIGRATIONS.index(MIGRATION))


def test_the_column_ddl_is_guarded_so_the_no_op_pass_fires_nothing():
    """view_migrations runs this file on every pass. A bare ADD COLUMN IF NOT
    EXISTS still takes the table lock and fires pgrst_ddl_watch every time
    (.claude/rules/operations.md)."""
    sql = _migration()
    assert "information_schema.columns" in sql
    assert "column_name = 'clv_bet_book'" in sql
    assert "ADD COLUMN IF NOT EXISTS" not in sql


def test_the_stamp_is_guarded_on_the_property_the_recompute_establishes():
    """Guard on clv_bet_book IS NULL (written by every capture from this change
    on), never on clv_captured_at: nulling that from a migration that re-runs
    every pass would re-null forever, and the app hides the card while it is
    NULL."""
    sql = " ".join(_migration().split())
    assert f"SET clv_method = '{LEGACY}'" in sql
    assert "p.clv_bet_book IS NULL" in sql
    assert "p.clv_captured_at IS NOT NULL" in sql
    assert "clv_captured_at = NULL" not in sql and "SET clv_captured_at" not in sql


def test_the_stamp_names_the_same_label_priced_nfl_models_as_the_resolver():
    sql = _migration()
    for model in pt._NFL_LABEL_PRICED_MODELS:
        assert f"'{model}'" in sql, model


def test_the_recompute_is_declared_as_a_one_shot_job_by_mike():
    entries = json.loads((ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    (job,) = [e for e in entries if e["key"] == "clv-price-taken-recompute-2026-10-08"]
    assert job["job_type"] == "clv_backfill"
    assert job["requested_by"] == "mike"


def test_the_backfill_job_brings_the_schema_current_before_it_reads():
    """A declared job can be claimed before the first pass after a deploy has
    run its migrations; the capture SELECT names clv_bet_book."""
    import inspect
    import tracking.job_queue as jq
    src = inspect.getsource(jq.JOBS["clv_backfill"][0])
    assert src.index("apply_view_migrations(") < src.index("_backfill_clv(conn")
