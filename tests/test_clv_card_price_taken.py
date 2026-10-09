"""The app's CLV card prints the price the bet was taken at, at the book it was
taken (mike, 2026-10-08: "grade CLV at the price taken").

`clv_pct` is graded at `paper_tracker._bet_price_and_book`. The card must print
the same price at the same book, or it shows a number the grade never used
(DraftKings -125 on "FLA ML", taken at BetMGM +154). `mobile/src/lib/clvBet.ts`
mirrors that function. These tests pin the mirror three ways:

- its model ids, label maps and label patterns equal the server's (runs here);
- the same rows through both functions give the same book and price (needs
  Node, which CI has; skipped where it is missing); where the capture recorded
  a book, the app prints that one, against answers written out by hand, since
  the server function takes no recorded book;
- the card reads the helper, and the query and the type carry `clv_bet_book`.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tracking import paper_tracker as pt

ROOT = Path(__file__).parent.parent
CLV_BET = (ROOT / "mobile/src/lib/clvBet.ts").read_text(encoding="utf-8")
DETAIL = (ROOT / "mobile/src/screens/PickDetailScreen.tsx").read_text(encoding="utf-8")


def _ts_list(name: str) -> set[str]:
    m = re.search(rf"export const {name}: readonly string\[\] = \[([^\]]*)\]", CLV_BET)
    assert m, name
    return set(re.findall(r"'([a-z_]+)'", m.group(1)))


def _ts_map(name: str) -> dict[str, str]:
    m = re.search(rf"export const {name}: Readonly<Record<string, string>> = \{{(.*?)\}};",
                  CLV_BET, re.S)
    assert m, name
    return dict(re.findall(r"([A-Z_]+): '([a-z_]+)'", m.group(1)))


def test_the_label_priced_models_are_the_servers():
    assert _ts_list("CLV_SUFFIX_LABEL_MODELS") == set(pt._SUFFIX_LABEL_PRICED_MODELS)
    assert _ts_list("CLV_NFL_LABEL_MODELS") == set(pt._NFL_LABEL_PRICED_MODELS)


def test_the_label_maps_are_the_servers():
    assert _ts_map("CLV_SUFFIX_LABEL_BOOK") == pt._LABEL_BOOK
    assert _ts_map("CLV_NFL_LABEL_BOOK") == pt._NFL_LABEL_BOOK


def test_the_label_patterns_are_the_servers():
    suffix = re.search(r"const SUFFIX_RE = /(.*)/;", CLV_BET).group(1)
    nfl = re.search(r"const NFL_RE = /(.*)/;", CLV_BET).group(1)
    assert suffix == pt._LABEL_BOOK_RE.pattern
    assert nfl == pt._NFL_LABEL_BOOK_RE.pattern


def test_the_helper_has_no_imports_so_node_can_run_it():
    assert not re.search(r"^import ", CLV_BET, re.M)


# One row per group measured on every captured pick (2026-10-09), plus the
# label cases the server distinguishes.
CASES = [
    # re-graded today: clv_bet_book recorded
    dict(model_id="mlb_over_under", pick_label="NYY vs TB Under 7.0",
         dk_odds=101, decision_odds=105, decision_book="betmgm", clv_bet_book="betmgm"),
    # taken at another book, before clv_bet_book existed
    dict(model_id="nhl_moneyline", pick_label="FLA ML",
         dk_odds=-125, decision_odds=154, decision_book="BetMGM", clv_bet_book=None),
    # taken at DraftKings
    dict(model_id="mlb_moneyline", pick_label="NYY ML",
         dk_odds=-130, decision_odds=-130, decision_book="draftkings", clv_bet_book=None),
    # decided before 2026-09-09: no decision columns
    dict(model_id="mlb_moneyline", pick_label="NYY ML",
         dk_odds=-130, decision_odds=None, decision_book=None, clv_bet_book=None),
    # a line DraftKings never hung (the 30 Hard Rock NHL props)
    dict(model_id="nhl_prop_shots_on_goal", pick_label="Sidney Crosby Over 2.5 SOG",
         dk_odds=None, decision_odds=-115, decision_book="hardrockbet", clv_bet_book=None),
    # market-relative props: the label suffix owns dk_odds
    dict(model_id="nfl_prop_market", pick_label="Jadarian Price Over 1.5 Rec (FD)",
         dk_odds=-120, decision_odds=None, decision_book=None, clv_bet_book=None),
    dict(model_id="wnba_prop_market", pick_label="A'ja Wilson Over 24.5 Pts (fliff)",
         dk_odds=110, decision_odds=None, decision_book=None, clv_bet_book=None),
    dict(model_id="nfl_prop_market", pick_label="Jadarian Price Over 1.5 Rec",
         dk_odds=-120, decision_odds=None, decision_book=None, clv_bet_book=None),
    # NFL wind/opener: the comma book owns dk_odds
    dict(model_id="nfl_wind_totals",
         pick_label="PIT @ CLE Under 38.5 (Wind 11 mph, CZR) · 1.19u",
         dk_odds=-105, decision_odds=None, decision_book=None, clv_bet_book=None),
    dict(model_id="nfl_opener_spread",
         pick_label="HOU @ TEN — TEN +9.5 (Opener +2 vs Pinnacle, BOV) · 1.67u",
         dk_odds=-110, decision_odds=None, decision_book=None, clv_bet_book=None),
    dict(model_id="nfl_opener_spread", pick_label="HOU @ TEN — TEN +9.5",
         dk_odds=-110, decision_odds=None, decision_book=None, clv_bet_book=None),
    # a parenthesis on any other model is not a book
    dict(model_id="mlb_f5_moneyline", pick_label="NYY ML (F5)",
         dk_odds=-130, decision_odds=None, decision_book=None, clv_bet_book=None),
    dict(model_id="nfl_prop_receptions", pick_label="X Over 4.5 Rec, FD)",
         dk_odds=-110, decision_odds=None, decision_book=None, clv_bet_book=None),
    # nothing priced
    dict(model_id="mlb_moneyline", pick_label="NYY ML",
         dk_odds=None, decision_odds=None, decision_book=None, clv_bet_book=None),
]


# The capture writes clv_bet_book from this same derivation
# (tracking/paper_tracker.py:1834, written at :1857 and :1963), so on every
# row in production it equals the derived book. The app still prefers it,
# which guards a row whose decision columns or label changed after it was
# graded; no row looks like that today. The server function takes no
# recorded book, so these answers are written out, not computed.
RECORDED = [
    # the recorded book wins, trimmed and lowercased, at the derived price
    (dict(model_id="mlb_over_under", pick_label="NYY vs TB Under 7.0",
          dk_odds=101, decision_odds=105, decision_book="betmgm",
          clv_bet_book="FanDuel "),
     ["fanduel", 105.0]),
    # a recorded book on a row with no price prints nothing
    (dict(model_id="mlb_moneyline", pick_label="NYY ML",
          dk_odds=None, decision_odds=None, decision_book=None, clv_bet_book="betmgm"),
     [None, None]),
]


def _server(c: dict) -> list:
    price, book = pt._bet_price_and_book(c["model_id"], c["dk_odds"], c["decision_odds"],
                                         c["decision_book"], c["pick_label"])
    return [book, None if price is None else float(price)]


def _app(rows: list[dict]) -> list:
    """[book, price, clvLabelBook] per row, from clvBet.ts under Node."""
    script = f"""
import {{ clvBetQuote, clvLabelBook }} from "./mobile/src/lib/clvBet.ts";
const cases = {json.dumps(rows)};
const got = cases.map((c) => {{
  const q = clvBetQuote(c);
  return [q.book, q.price == null ? null : Number(q.price), clvLabelBook(c)];
}});
process.stdout.write(JSON.stringify(got));
"""
    proc = subprocess.run(
        ["node", "--experimental-strip-types", "--input-type=module", "-e", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_the_cases_cover_every_server_branch():
    books = {tuple(_server(c)) for c in CASES}
    assert ("betmgm", 105.0) in books and ("betmgm", 154.0) in books
    assert ("hardrockbet", -115.0) in books and ("fanduel", -120.0) in books
    assert ("fliff", 110.0) in books and ("williamhill_us", -105.0) in books
    assert ("bovada", -110.0) in books and (None, None) in books
    assert ("draftkings", -120.0) in books and ("draftkings", -130.0) in books


def test_a_recorded_book_differs_from_the_derived_one():
    # Otherwise "the recorded book wins" and "the recorded book is ignored"
    # give the same answer and the Node test below cannot tell them apart.
    row, want = RECORDED[0]
    derived = _server(row)
    assert derived[0] != want[0] and derived[1] == want[1], (derived, want)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node (CI has 22)")
def test_the_app_prefers_the_recorded_book_at_the_derived_price():
    got = _app([row for row, _ in RECORDED])
    for (row, want), g in zip(RECORDED, got):
        assert g[:2] == want, (row, g, want)


@pytest.mark.skipif(shutil.which("node") is None, reason="needs node (CI has 22)")
def test_the_app_prices_every_row_as_the_server_grades_it():
    want = [_server(c) for c in CASES]
    got = _app(CASES)
    for case, g, w in zip(CASES, got, want):
        assert g[:2] == w, (case, g, w)
        # The book the header names (storedQuoteBook) is the graded book
        # wherever the row carries a price.
        if w[1] is not None:
            assert g[2] == w[0], (case, g, w)


def _clv_card() -> str:
    start = DETAIL.index("function ClvCard(")
    return DETAIL[start:DETAIL.index("\nconst styles", start)]


def test_the_card_prints_the_price_taken_not_draftkings():
    card = _clv_card()
    assert "clvBetQuote(pick)" in card
    assert "formatAmerican(bet.price)" in card
    assert "formatAmerican(pick.dk_odds)" not in card
    assert "Signal line" not in card


def test_the_header_takes_its_book_from_the_cards_rule():
    # storedQuoteBook names the book on every other price on the pick screens
    # (the header, the board's price chip, the movement card). It read its own
    # NFL-only pattern and named DraftKings over a CLV card that said Caesars
    # or FanDuel for the same price. It must return the card's rule.
    markets = (ROOT / "mobile/src/lib/markets.ts").read_text(encoding="utf-8")
    start = markets.index("export function storedQuoteBook(")
    body = markets[start:markets.index("\n}", start)]
    assert "return decisionBook(pick) ?? clvLabelBook(pick);" in body
    assert not any(f".{m}(" in body for m in ("exec", "match", "test", "startsWith"))
    assert "BOOK_KEY_BY_ABBREV" not in markets
    assert re.search(r"^import \{[^}]*\bclvLabelBook\b[^}]*\} from '\./clvBet';",
                     markets, re.M)


def test_the_query_and_the_type_carry_the_bet_book():
    queries = (ROOT / "mobile/src/lib/queries.ts").read_text(encoding="utf-8")
    cols = queries.split("const PICK_COLUMNS =", 1)[1].split(";", 1)[0]
    assert "clv_bet_book" in cols
    types = (ROOT / "mobile/src/types/index.ts").read_text(encoding="utf-8")
    assert re.search(r"^\s*clv_bet_book: string \| null;", types, re.M)
