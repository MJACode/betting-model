"""A rule card's market must be named everywhere a market is read off a model id.

The rule cards (tracking/paper_tracker._RULE_MODEL_MARKETS: nba_total_luck,
mlb_total_market, nfl_wind_totals, ...) are not in config.MODELS, and several
of their ids carry none of the substrings the SQL name patterns look for
('over_under', 'runline', 'spread'). Each SQL mapping below falls through to
'h2h' for an id it does not name, and then reads the game's MONEYLINE rows for
a totals pick: no over price, no line, nothing to compare.

  * public.clv_game_market (the closing-line recompute,
    data/migrations/clv_standard_v2_2026_10_14.sql). A miss there stamps the
    pick's CLV standard_v2 with every column NULL once capture has missed for
    six hours, and nothing revisits a standard_v2 row.
  * check_line_movement's CASE (models/scorer.py, the check-lines step).
  * the Claude-mobile picks prompt's latest_odds join
    (docs/mobile_picks_prompt.md).

The app's own mapping (mobile/src/lib/markets.ts) is pinned by
mobile/scripts/verify_preferred_book.ts and verify_pick_timing.ts.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from tracking.paper_tracker import _RULE_MODEL_MARKETS  # noqa: E402

CLV_MIG = ROOT / "data" / "migrations" / "clv_standard_v2_2026_10_14.sql"
SCORER = ROOT / "models" / "scorer.py"
PROMPT = ROOT / "docs" / "mobile_picks_prompt.md"

RULE_IDS = sorted(_RULE_MODEL_MARKETS)


def _clv_game_market() -> dict[str, str]:
    sql = CLV_MIG.read_text(encoding="utf-8")
    i = sql.index("FUNCTION public.clv_game_market(model_id text)")
    body = sql[i:sql.index("$body$;", i)]
    return dict(re.findall(r"WHEN '([a-z0-9_]+)' THEN '([a-z0-9_]+)'", body))


def _like(pattern: str) -> re.Pattern:
    """SQL LIKE -> regex: % any run, _ any one character."""
    out = "".join(".*" if c == "%" else "." if c == "_" else re.escape(c) for c in pattern)
    return re.compile(out)


def _case(block: str):
    """Evaluate a `CASE WHEN p.model_id LIKE/= ... THEN 'm' ... ELSE 'x' END`
    block, in order, as Postgres would for one model id."""
    whens = re.findall(r"WHEN\s+(.+?)\s+THEN\s+'([a-z0-9_]+)'", block, flags=re.S)
    default = re.search(r"ELSE\s+'([a-z0-9_]+)'", block).group(1)
    rules = []
    for cond, market in whens:
        tests = []
        for part in re.split(r"\s+OR\s+", cond.strip()):
            m = re.fullmatch(r"p\.model_id\s+LIKE\s+'([^']+)'", part.strip())
            if m:
                tests.append(("like", _like(m.group(1).replace("%%", "%"))))
                continue
            m = re.fullmatch(r"p\.model_id\s*=\s*'([^']+)'", part.strip())
            assert m, f"a WHEN this test cannot read: {part!r}"
            tests.append(("eq", m.group(1)))
        rules.append((tests, market))

    def resolve(model_id: str) -> str:
        for tests, market in rules:
            for kind, v in tests:
                if (kind == "eq" and model_id == v) or (kind == "like" and v.fullmatch(model_id)):
                    return market
        return default
    return resolve


def _scorer_case():
    src = SCORER.read_text(encoding="utf-8")
    i = src.index("def check_line_movement")
    j = src.index("o.market = CASE", i)
    return _case(src[j:src.index("END", j)])


def _prompt_case():
    src = PROMPT.read_text(encoding="utf-8")
    j = src.index("AND lo.market = CASE")
    return _case(src[j:src.index("END", j)])


def test_the_case_reader_reads_the_name_patterns_as_postgres_does():
    """The evaluator above must agree with the patterns it reads, or the tests
    below prove nothing."""
    scorer = _scorer_case()
    assert scorer("mlb_f5_over_under") == "totals_1st_5_innings"
    assert scorer("nhl_over_under") == "totals"
    assert scorer("mlb_runline") == "spreads"
    assert scorer("nba_moneyline") == "h2h"
    prompt = _prompt_case()
    assert prompt("nhl_moneyline_regulation") == "h2h_3way"
    assert prompt("nba_spread") == "spreads"
    assert prompt("some_model_nobody_named") == "h2h"


@pytest.mark.parametrize("model_id", RULE_IDS)
def test_the_closing_line_recompute_reads_the_rule_card_s_market(model_id):
    """RULE: public.clv_game_market names every rule card with the market it
    settles on (tracking/paper_tracker._market_for_pick)."""
    assert _clv_game_market().get(model_id) == _RULE_MODEL_MARKETS[model_id], model_id


def test_the_closing_line_functions_are_recreated_when_they_change():
    """The functions are re-created only when clv_power_fair's comment differs
    from fn_comment, so the guard's literal and the COMMENT ON FUNCTION literal
    must be the same string. (When clv_game_market changes, both are bumped
    together, or production never sees the change.)"""
    sql = CLV_MIG.read_text(encoding="utf-8")
    declared = re.search(r"fn_comment text := '([^']+)'", sql).group(1)
    stamped = re.search(r"COMMENT ON FUNCTION public\.clv_power_fair\(double precision\[\]\) IS\s*"
                        r"'([^']+)'", sql).group(1)
    assert declared == stamped
    assert declared != "clv-standard-v2-power-80-0.05-12", (
        "clv_game_market changed (nba_total_luck) after production stamped this comment; "
        "without a new comment the guard never re-creates it")


@pytest.mark.parametrize("model_id", RULE_IDS)
def test_the_line_movement_check_reads_the_rule_card_s_market(model_id):
    assert _scorer_case()(model_id) == _RULE_MODEL_MARKETS[model_id], model_id


@pytest.mark.parametrize("model_id", RULE_IDS)
def test_the_claude_mobile_prompt_reads_the_rule_card_s_market(model_id):
    assert _prompt_case()(model_id) == _RULE_MODEL_MARKETS[model_id], model_id
