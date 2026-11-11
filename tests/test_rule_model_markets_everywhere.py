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

The Claude-mobile picks prompt carried a third copy in its live-odds join until
2026-11-04. The prompt is gone (the open picks are the public.open_picks view,
which reads no odds rows), so that copy is gone too.

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


def test_the_case_reader_reads_the_name_patterns_as_postgres_does():
    """The evaluator above must agree with the patterns it reads, or the tests
    below prove nothing."""
    scorer = _scorer_case()
    assert scorer("mlb_f5_over_under") == "totals_1st_5_innings"
    assert scorer("nhl_over_under") == "totals"
    assert scorer("mlb_runline") == "spreads"
    assert scorer("nba_moneyline") == "h2h"
    assert scorer("some_model_nobody_named") == "h2h"


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
    # Every comment a version of clv_game_market has carried. Production held
    # the first on 2026-10-18 and still on 2026-10-19 (read-only query of the
    # function's comment); the second shipped with
    # nba_total_luck, which may reach production before nba_team_total_luck; the
    # third with nba_team_total_luck, which production holds before
    # nba_first_half_total_luck ships; the fourth with nba_first_half_total_luck,
    # which production held on 2026-11-02 (read-only query of the comment, and
    # clv_game_market('ncaab_spread_market') returned 'h2h') before
    # ncaab_spread_market ships; the fifth with ncaab_spread_market, which
    # production holds once that model merges, before ncaab_moneyline_own_spread
    # ships.
    stamped_before = {
        "clv-standard-v2-power-80-0.05-12",
        "clv-standard-v2-power-80-0.05-12-nba-total-luck",
        "clv-standard-v2-power-80-0.05-12-nba-team-total-luck",
        "clv-standard-v2-power-80-0.05-12-nba-first-half-total-luck",
        # ncaab_spread_market's (#1127), which production may hold before this
        # change: ncaab_first_half_spread changes the function again (its
        # market and the close-only first-half spread), so a stamp of its own.
        "clv-standard-v2-power-80-0.05-12-ncaab-spread-market",
        # ncaab_first_half_spread's (#1128), which production holds once that
        # model merges, before ncaab_moneyline_own_spread changes the function
        # again (it names the moneyline model as h2h), so a stamp of its own.
        "clv-standard-v2-power-80-0.05-12-ncaab-spread-and-first-half",
        # ncaab_moneyline_own_spread's (#1125), which production holds once
        # that model merges, before ncaab_first_half_total changes the function
        # again (it names the first-half total as totals_h1), so a stamp of
        # its own.
        "clv-standard-v2-power-80-0.05-12-ncaab-moneyline-own-spread",
        # ncaab_first_half_total's (#1137), which production holds once that
        # model merges, before ncaab_moneyline_first_post names itself as h2h.
        "clv-standard-v2-power-80-0.05-12-ncaab-first-half-total",
        # ncaab_moneyline_first_post's, which production held on 2026-11-07 after #1214 merged
        # nba_q1_trend into clv_game_market WITHOUT a new comment: clv_game_market('nba_q1_trend')
        # returned 'h2h' (read-only query, 2026-11-07 14:10Z).
        "clv-standard-v2-power-80-0.05-12-ncaab-moneyline-first-post",
        # nba_q1_trend's (#1216), which production holds from 2026-11-07, before
        # ncaabw_total_blend (the women's college basketball totals model, 2026-11-10)
        # names itself as totals.
        "clv-standard-v2-power-80-0.05-12-nba-q1-trend",
        # ncaabw_total_blend's, which production holds before nba_q1_trend_ml names
        # itself as h2h_q1 and joins the NBA close-only markets. The function body
        # still names ncaabw_total_blend as totals.
        "clv-standard-v2-power-80-0.05-12-ncaabw-total-blend",
    }
    assert declared not in stamped_before, (
        "clv_game_market changed (nba_q1_trend_ml, keeping ncaabw_total_blend) after production may have "
        "stamped this comment; without a new comment the guard never re-creates it")


# The mapping's own text, pinned to the comment that ships it. #1214 edited the mapping and kept the comment, so
# production never re-created the function: the guard above could not see it, because it reads only the comment.
# Editing clv_game_market now fails here until the comment is bumped AND this hash is set to the new body's.
# The hash is the merged body: ncaabw_total_blend from master and nba_q1_trend_ml from this branch.
GAME_MARKET_BODY = {"clv-standard-v2-power-80-0.05-12-nba-q1-trend-ml": "5ef76d1e2c14d033"}


def test_an_edit_to_the_market_map_bumps_the_comment():
    import hashlib
    sql = CLV_MIG.read_text(encoding="utf-8")
    declared = re.search(r"fn_comment text := '([^']+)'", sql).group(1)
    i = sql.index("FUNCTION public.clv_game_market(model_id text)")
    body = sql[i:sql.index("$body$;", i)].replace("\r\n", "\n")
    got = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    assert GAME_MARKET_BODY.get(declared) == got, (
        f"clv_game_market's text is {got} under the comment {declared!r}: bump fn_comment and the "
        f"COMMENT ON FUNCTION literal, add the old comment to stamped_before, and pin the new hash here")


@pytest.mark.parametrize("model_id", RULE_IDS)
def test_the_line_movement_check_reads_the_rule_card_s_market(model_id):
    assert _scorer_case()(model_id) == _RULE_MODEL_MARKETS[model_id], model_id

