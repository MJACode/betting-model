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


def test_the_prop_lookup_joins_on_name_not_id():
    """player_prop_odds has NO player_id column -- it stores the book's own name
    string, which is the same join scorer._get_prop_dk_odds uses to price the
    pick. Querying by id would raise 'column does not exist' at runtime, and the
    first sign would be a silent gap in CLV."""
    src = _fn("_closing_prop_odds")
    assert "player_name = %s" in src
    # Body only -- the docstring names the column it deliberately does not use.
    body = src.split('"""')[2]
    assert "player_id" not in body


def test_a_prop_pick_whose_label_has_no_name_is_skipped_not_guessed():
    src = _fn("_capture_clv")
    assert "_PICK_LABEL_RE.match(pick_label" in src
    assert "if not player_name:" in src


def test_clv_pct_never_compares_prices_across_a_moved_line():
    """clv_pct differences two prices for the SAME proposition. Over 5.5 at -110
    and Over 6.5 at -110 are different bets.

    Measured before this shipped: of 2,655 resolvable prop picks, 1,115 (42%)
    closed on a different line. Including them gave -4.83pp average / 14.4%
    beating the close; same-line only it is +1.33pp / 18.8%. The first number is
    fiction, and it is the one that would have been published.

    Adding line CLV (2026-08-30) did not loosen this. It changed what the guard
    SKIPS -- clv_pct alone, rather than the whole pick -- never what clv_pct
    means."""
    src = _fn("_capture_clv")
    assert "_closing_line_for(" in src
    assert "abs(float(closing_line) - float(scored_line))" in src
    assert "if not line_moved:" in src, (
        "clv_pct must be computed only on an unmoved line")


def test_line_moved_is_derived_from_the_numbers_not_from_the_points_helper():
    """_line_clv_pts returns None for a pick_side it cannot orient. Deriving
    "did the line move" from it would read that None as "it held" and let a
    cross-line price comparison through -- the exact leak the guard exists to
    stop."""
    src = _fn("_capture_clv")
    assert "line_moved = (closing_line is not None and scored_line is not None" in src


def test_moneyline_has_no_line_and_is_never_skipped_by_the_guard():
    """The guard must not silently drop every h2h pick."""
    src = _fn("_closing_line_for")
    assert "return None" in src, "moneyline must fall through to no line"
    guard = _fn("_capture_clv")
    assert "closing_line is not None and scored_line is not None" in guard


def test_the_close_is_recorded_even_when_the_line_moved():
    """The whole point of line CLV. Before it, closing_line was only ever
    written when it EQUALLED scored_line -- so the app's "Line 44.5 -> 46.5"
    row, gated on scored_line !== closing_line, could never render. The one
    thing a user most wants to see was structurally invisible."""
    src = _fn("_capture_clv")
    write = src.split("conn.execute(", 1)[1]
    assert "closing_line    = %s" in write
    assert "line_clv_pts    = %s" in write
    assert "clv_beat_close  = %s" in write


def test_a_pick_is_only_stamped_captured_once_a_measure_resolved():
    """clv_captured_at is the idempotency gate now, so stamping a pick that no
    measure applies to would retire it from the backfill forever."""
    src = _fn("_capture_clv")
    assert src.count("continue") >= 4, (
        "unresolvable picks must be left for a later pass, not stamped")


def test_the_backfill_is_self_healing_and_bounded():
    """No one-off script can reach production from a dev session -- the Supabase
    MCP is read-only and the worker runs only scheduled jobs. So the backfill
    rides the settle, walks the oldest un-measured dates, and converges."""
    src = _fn("_backfill_clv")
    assert "ORDER BY p.game_date" in src, "oldest first, or it never converges"
    assert "LIMIT %s" in src, "unbounded scan would stall the settle"
    # clv_captured_at, NOT clv_pct: recording the close across a moved line
    # means a captured pick can legitimately carry a NULL clv_pct, and the old
    # gate would re-process every one of those on every settle, forever.
    assert "clv_captured_at IS NULL" in src
    assert "clv_pct IS NULL" not in src
    assert "is_live IS NOT TRUE" in src
    settle = SRC.read_text()
    assert "_backfill_clv(conn, clv_at)" in settle, "backfill not wired into settle"


def test_a_backfill_failure_never_breaks_settlement():
    assert "non-fatal" in _fn("_backfill_clv")


def test_a_pick_stamped_after_first_pitch_is_never_measured():
    """A pre-game pick whose created_at is AFTER its own commence_time is not a
    pre-game pick: its scored_line was never a number DK had up before the game,
    so differencing it against the close compares two market states and calls
    the gap movement.

    Measured on production 2026-08-30: of 1,249 settled MLB+WNBA prop bets still
    unmeasured, 1,046 were stamped after first pitch, and only 10% of the MLB
    ones had their scored_line anywhere in DK's pre-game history for that
    market. Without this guard, recording the close across a moved line would
    have manufactured ~1,046 beat-the-close verdicts, nearly all positive."""
    src = _fn("_capture_clv")
    assert "created = _as_utc(created_at)" in src
    assert "if created is None or created > ct:" in src
    assert "p.created_at" in src, "created_at must be selected to be checked"


def test_the_backfill_queue_cannot_jam_on_uncapturable_dates():
    """The scan listed any date holding an un-captured pick, so a date whose
    picks are ALL permanently unmeasurable sat at the head of the queue forever
    and the 40 oldest dates were re-walked every settle instead of advancing.
    Eleven of the twelve oldest queued dates were in that state on 2026-08-30 --
    377 picks re-listed and re-skipped on every run, which is why the backfill
    had not converged."""
    src = _fn("_backfill_clv")
    assert "p.created_at::timestamptz <= g.commence_time::timestamptz" in src


def test_both_guards_agree():
    """The backfill picks the dates and _capture_clv does the work, so a pick
    the capture will always skip must not be what puts its date in the queue."""
    scan = _fn("_backfill_clv")
    cap = _fn("_capture_clv")
    assert "created_at" in scan and "created_at" in cap
