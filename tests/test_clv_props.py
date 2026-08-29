"""CLV must cover player props — they are the bulk of the settled record.

Before this, CLV was captured for game-level picks only, so the published
beat-the-close rate rested on 240 of 3,422 settled bets (7%). A rate measured
on 7% of the book says very little about the book.
"""
import ast
from pathlib import Path

SRC = Path(__file__).parent.parent / "tracking/paper_tracker.py"


def _fn(name: str) -> str:
    text = SRC.read_text()
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == name)
    return "\n".join(text.splitlines()[fn.lineno - 1:fn.end_lineno])


def test_props_are_no_longer_excluded_from_clv():
    src = _fn("_capture_clv")
    for excluded in ("mlb_prop_%%", "wnba_prop_%%", "nba_prop_%%"):
        assert excluded not in src, f"props still excluded from CLV: {excluded}"


def test_live_picks_stay_excluded_forever():
    """An in-play price has no meaningful close to compare against."""
    src = _fn("_capture_clv")
    assert "p.is_live IS NOT TRUE" in src


def test_golf_stays_excluded():
    """Its prices live in golf_odds, and a tournament has no closing moment."""
    assert "golf_%%" in _fn("_capture_clv")


def test_every_prop_model_maps_to_a_dk_market():
    """A model missing from the map silently loses its CLV — the exact gap this
    change is closing — so the map is checked against the registry."""
    import importlib.util
    import sys
    import types
    sys.modules.setdefault("dotenv",
                           types.SimpleNamespace(load_dotenv=lambda *a, **k: None))
    spec = importlib.util.spec_from_file_location(
        "cfg", Path(__file__).parent.parent / "config.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)

    text = SRC.read_text()
    tree = ast.parse(text)
    node = next(n for n in tree.body
                if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", "") == "_PROP_MARKET_FOR_MODEL")
    mapped = set(ast.literal_eval(node.value))

    prop_models = {m for m in cfg.PROP_MODELS
                   if not m.startswith(("nfl_prop", "golf_"))}
    missing = prop_models - mapped
    assert not missing, f"prop models with no DK market for CLV: {sorted(missing)}"


def test_the_closing_prop_lookup_is_bounded_at_first_pitch():
    """The evening refresh writes post-first-pitch snapshots as
    snapshot_type='open' (the §106 leak), so an unbounded 'latest' would take an
    IN-PLAY number as the close and record a fictional CLV."""
    src = _fn("_closing_prop_odds")
    assert "snapshot_at::timestamptz <= %s::timestamptz" in src
    assert "ORDER BY snapshot_at::timestamptz DESC" in src, (
        "text ordering on a mixed-format timestamp column is not chronological")
    assert "bookmaker = 'draftkings'" in src


def test_a_prop_pick_without_a_player_id_is_skipped_not_guessed():
    src = _fn("_capture_clv")
    assert "if not player_id:" in src
