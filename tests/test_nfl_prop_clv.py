"""NFL prop CLV was never captured.

The 2026-08-29 change that extended CLV to player props wrote the model -> DK
market map for MLB, WNBA and NBA, and wrote its own guard test to EXCLUDE
"nfl_prop". No NFL prop had settled until 2026-09-09 (NE @ SEA), so the gap
had no symptom until the first recap with an NFL line published "2-1" with no
beat-the-close figure -- while player_prop_odds held 256,076 quotes for that
game, 58 players, 23 markets, and a DraftKings close for all three picks at
23:25Z, 55 minutes before kickoff. mike: "Where is the CLV stats on nfl?"

Without an entry a pick falls through to the game-odds lookup, which has no
NFL rows, and is skipped in silence with clv_captured_at NULL -- so the
self-healing backfill re-walks it on every settle, forever, and never fills it.

Two things are pinned here: the twelve distributional models map to exactly
the market the scorer prices them on, and the market-relative rule (whose
dk_odds is the SOFT book's price, book named only in the label) closes at its
own book rather than at DraftKings.
"""
import ast
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "tracking" / "paper_tracker.py"


def _assign(path: Path, name: str):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    # Plain and annotated assignments both: scorer writes
    # `_NFL_PROP_CONFIG: dict[str, dict] = {...}`.
    node = next(n for n in tree.body
                if (isinstance(n, ast.Assign)
                    and getattr(n.targets[0], "id", "") == name)
                or (isinstance(n, ast.AnnAssign)
                    and getattr(n.target, "id", "") == name))
    return ast.literal_eval(node.value)


def _fn(name: str) -> str:
    text = SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


def test_the_twelve_nfl_prop_models_close_on_the_market_they_are_priced_on():
    """The scorer prices nfl_prop_X on _NFL_PROP_CONFIG[X]['market']; the
    close must be read on the same key or CLV compares two different props."""
    mapped = _assign(SRC, "_PROP_MARKET_FOR_MODEL")
    scorer = _assign(ROOT / "models" / "scorer.py", "_NFL_PROP_CONFIG")
    assert len(scorer) == 12
    for model_id, cfg in scorer.items():
        assert mapped.get(model_id) == cfg["market"], model_id


def test_the_market_relative_rules_take_their_market_from_the_row():
    mapped = _assign(SRC, "_PROP_MARKET_FOR_MODEL")
    assert mapped["nfl_prop_market"] == "FROM_PROP_MARKET"
    assert mapped["wnba_prop_market"] == "FROM_PROP_MARKET"
    src = _fn("_capture_clv")
    assert "p.prop_market" in src, "the SELECT must fetch the row's market"
    assert 'if prop_market == "FROM_PROP_MARKET":' in src
    assert "bookmaker = _book_from_label(pick_label)" in src
    assert "bookmaker=bookmaker" in src, "the close must be read at the pick's book"


@pytest.mark.parametrize("label, book", [
    ("Jadarian Price Over 1.5 Rec (FD)", "fanduel"),
    ("Sam Darnold Under 19.5 Comp (MGM)", "betmgm"),
    ("A Player Over 0.5 Anytime TD (DK)", "draftkings"),
    # _BOOK.get(b.book, b.book) writes an unmapped book RAW.
    ("Some Guy Over 44.5 Rush Yds (fliff)", "fliff"),
    ("Some Guy Over 44.5 Rush Yds (hardrockbet)", "hardrockbet"),
    # A distributional pick has no suffix and is priced at DraftKings.
    ("Rhamondre Stevenson Under 88.5 Ru+Re Yds", "draftkings"),
    (None, "draftkings"),
])
def test_the_book_is_read_from_the_label_suffix(label, book):
    from tracking.paper_tracker import _book_from_label
    assert _book_from_label(label) == book


def test_the_label_book_map_is_the_inverse_of_both_cards():
    """The two market-relative cards each carry a _BOOK map; the resolver
    must invert exactly those, or a card can add a book the close cannot find."""
    inverse = _assign(SRC, "_LABEL_BOOK")
    for card in ("nfl_prop_market_card.py", "wnba_prop_market_card.py"):
        book = _assign(ROOT / "scripts" / card, "_BOOK")
        assert {v: k for k, v in book.items()} == inverse, card


def test_the_closing_prop_lookup_defaults_to_draftkings_and_binds_the_book():
    src = _fn("_closing_prop_odds")
    assert 'bookmaker: str = "draftkings"' in src
    assert "AND bookmaker = %s" in src
    assert "bookmaker = 'draftkings'" not in src.split('"""')[-1], (
        "the book must be a parameter, not a literal")


def test_the_map_test_no_longer_excludes_nfl():
    """The guard that should have caught this was written to skip it."""
    guard = (ROOT / "tests" / "test_clv_props.py").read_text(encoding="utf-8")
    assert not re.search(r'startswith\(\(\s*"nfl_prop"', guard)
