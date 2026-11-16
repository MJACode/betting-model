"""An in-play bet at a book whose number DraftKings does not hang is still a pick.

The bug this pins (found 2026-11-16): the men's and women's college basketball
in-play loops and the EuroLeague halftime loop built the `picks` row with
dk_implied_prob = NULL whenever DraftKings had no quote on the same side at the
same number in the read. `picks.dk_implied_prob` is NOT NULL in production, so
the insert failed, the loop logged "write failed ... (non-fatal)" and the bet
was never stored or posted. From 2026-11-09 to 11-15 that dropped 20 of the 24
men's in-play bets and 13 of the 22 women's halftime bets the loops decided
(the pollers' logs; docs/sports/ncaabw.md, "Why the women's record trails the
men's").

The house convention for a pick decided away from DraftKings is the first-half
cards' and the NBA in-play loop's: dk_odds NULL, dk_implied_prob 0.0, edge 0.0,
line_book naming the book taken, the decision_* columns carrying the price the
pick was decided, sized and settled at (CLAUDE.md 6).
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.euroleague_live_loop as EL  # noqa: E402
import models.ncaab_live_ig as IG  # noqa: E402
import models.ncaab_live_loop as MEN  # noqa: E402
import models.ncaabw_live_loop as WOMEN  # noqa: E402

# The NOT NULL columns of production `picks` with no default, read from
# information_schema on 2026-11-16. (data/supabase_schema.sql also marks
# dk_odds NOT NULL; production does not, and 16 models store it NULL.)
REQUIRED = ("model_id", "sport", "game_date", "pick_side", "pick_label", "model_probability",
            "dk_implied_prob", "edge", "kelly_fraction", "recommended_bet", "bankroll_at_pick")
TIP = pd.Timestamp("2026-11-14T17:00:00Z")


def _women(dk_line):
    ctx = WOMEN.GameCtx("NCAABW_2026-11-14_providence_boston-college", "2026-11-14", 2027, "Boston College",
                        "Providence", TIP, 401, None, None)
    best = {"side": "under", "book": "betmgm", "price": -110.0, "line": 145.5, "prob": 0.5769}
    rows = [{"book": "betmgm", "line": 145.5, "over_price": -110.0, "under_price": -110.0, "prob": 0.4231,
             "side": "over"}]
    if dk_line is not None:
        rows.append({"book": "draftkings", "line": dk_line, "over_price": -115.0, "under_price": -105.0,
                     "prob": 0.4231, "side": "over"})
    return WOMEN.build_pick(ctx, best, pd.DataFrame(rows), {"h_pts": 39, "a_pts": 36}, {}, 1000.0), best


def _men(dk_line):
    rule = next(r for r in IG.RULES if r.model_id == IG.TOTAL_H2)
    ctx = MEN.GameCtx("NCAAB_2026-11-12_niagara_bowling-green", "2026-11-12", 2027, "Bowling Green", "Niagara",
                      TIP, 402, None, None)
    best = {"side": "over", "book": "williamhill_us", "price": -110.0, "line": 156.5, "p_win": 0.60, "p_push": 0.0}
    rows = [{"book": "williamhill_us", "side": "over", "line": 156.5, "ev": 0.10, "price": -110.0, "p_win": 0.60,
             "p_push": 0.0}]
    if dk_line is not None:
        rows.append({"book": "draftkings", "side": "over", "line": dk_line, "ev": 0.05, "price": -105.0,
                     "p_win": 0.60, "p_push": 0.0})
    return MEN.build_pick(ctx, rule, best, pd.DataFrame(rows), {"period": 2, "diff": 10}, {}, 1000.0), best


def _euroleague(dk_line):
    ctx = EL.GameCtx("EUROLEAGUE_2026-11-14_away_home", "2026-11-14", 2027, "Home Club", "Away Club", TIP,
                     "E2026", 101)
    best = {"side": "home", "book": "betmgm", "price": -110.0, "line": -3.5, "prob": 0.58}
    rows = [{"book": "betmgm", "line": -3.5, "home_price": -110.0, "away_price": -110.0, "prob": 0.58,
             "side": "home"}]
    if dk_line is not None:
        rows.append({"book": "draftkings", "line": dk_line, "home_price": -105.0, "away_price": -115.0,
                     "prob": 0.58, "side": "home"})
    return EL.build_pick(ctx, best, pd.DataFrame(rows), SimpleNamespace(ht_home=40, ht_away=35), {}, 1000.0), best


BUILDERS = {"ncaabw": (_women, 147.5), "ncaab": (_men, 157.5), "euroleague": (_euroleague, -4.5)}


@pytest.mark.parametrize("name", sorted(BUILDERS))
@pytest.mark.parametrize("dk", ["absent", "another number"])
def test_a_bet_draftkings_does_not_quote_at_its_number_is_a_writable_pick(name, dk):
    build, other_line = BUILDERS[name]
    row, best = build(None if dk == "absent" else other_line)
    missing = [c for c in REQUIRED if row.get(c) is None]
    assert not missing, f"{name}: NOT NULL columns left empty: {missing}"
    assert row["dk_implied_prob"] == 0.0 and row["edge"] == 0.0 and row["dk_odds"] is None
    assert row["line_book"] == best["book"]
    assert row["decision_book"] == best["book"] and row["decision_odds"] == best["price"]
    assert row["decision_implied_prob"] > 0


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_draftkings_at_the_same_number_still_fills_its_own_columns(name):
    build, _ = BUILDERS[name]
    line = {"ncaabw": 145.5, "ncaab": 156.5, "euroleague": -3.5}[name]
    row, _ = build(line)
    assert row["dk_odds"] is not None and row["dk_implied_prob"] > 0
    assert row["line_book"] is None


def test_no_live_loop_writes_an_empty_draftkings_probability():
    """The next in-play loop is forked from one of these; a NULL here drops its bets."""
    bad = []
    for path in sorted((ROOT / "models").glob("*live*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r'"dk_implied_prob"\s*:\s*None\b', text):
            bad.append(path.name)
    assert not bad, f"these write dk_implied_prob = NULL when DraftKings has no quote: {bad}"
