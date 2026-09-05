"""Which books serve which prop markets — the audit that stored data cannot do.

Matt, 2026-09-05: "Check all the sportsbooks we get betting lines for and see
if they publish stats under different keys and sync everything up with the
stats tab."

The prompt was FanDuel and Caesars showing nothing on the MLB hits board. They
price hits for every hitter on the slate and publish them ONLY under
`batter_hits_alternate`, never returning a single `batter_hits` row — so their
column was blank until alternates shipped.

What is pinned here is the part that is easy to get subtly wrong: a market we
never REQUEST has no rows, and no query over stored data can tell "no book
prices this" from "we never asked". The probe exists to ask, so it must ask
about the right keys, cost what it claims, and write nothing.
"""

import inspect
import io
from pathlib import Path

import pytest

import config
from scripts import probe_market_coverage as p

ROOT = Path(__file__).parent.parent


def test_the_probe_asks_about_every_market_we_pull_and_its_alternate():
    for sport in ("MLB", "WNBA", "NBA", "NFL", "NCAAF"):
        cand = p.candidate_markets(sport)
        for m in p._standard_markets(sport):
            assert m in cand, f"{sport}: {m} not asked"
            assert f"{m}_alternate" in cand, f"{sport}: {m}_alternate not asked"


def test_it_asks_about_the_board_columns_that_are_permanently_blank():
    """A blank column is either "no book prices it" or "we never asked", and
    those look identical until someone asks."""
    mlb = p.candidate_markets("MLB")
    assert "batter_doubles" in mlb and "batter_at_bats" in mlb
    wnba = p.candidate_markets("WNBA")
    # NBA pulls steals/blocks/turnovers; the WNBA board shows those columns and
    # the WNBA pull has never included them.
    for m in ("player_steals", "player_blocks"):
        assert m in wnba, f"WNBA never asks about {m}"
        assert m not in config.PROP_MARKETS_WNBA, "sanity: that is the gap"
        assert m in config.PROP_MARKETS_NBA, "sanity: NBA already pulls it"


def test_no_market_is_asked_about_twice():
    for sport in ("MLB", "WNBA", "NBA", "NFL", "NCAAF"):
        cand = p.candidate_markets(sport)
        assert len(cand) == len(set(cand)), f"{sport} asks a market twice"


def test_one_market_per_call_so_a_rejected_key_is_identified_exactly():
    src = inspect.getsource(p.probe)
    assert '"markets": market,' in src, "a chunk would hide which key was rejected"
    assert "unsupported.append(market)" in src


def test_the_probe_writes_nothing():
    src = inspect.getsource(p)
    for forbidden in ("_insert_prop_odds", "INSERT INTO", "executemany"):
        assert forbidden not in src, f"a probe that writes is a pull with a nice name ({forbidden})"


def test_it_reports_supported_but_empty_apart_from_unsupported():
    """"The API does not know this key" and "no book priced it today" are
    different answers and lead to different decisions."""
    src = inspect.getsource(p.probe)
    assert '"unsupported_keys": unsupported' in src
    assert '"empty_but_supported"' in src


def test_only_books_we_asked_for_are_ever_counted():
    src = inspect.getsource(p.probe)
    assert "if key not in LINE_SHOP_BOOKMAKERS:" in src


def test_the_job_validates_its_sport_and_market_list():
    from tracking.job_queue import JOBS, _validate_market_coverage as v
    assert "market_coverage" in JOBS
    assert v({"sport": "mlb"}) == {"sport": "MLB", "markets": None}
    assert v({"sport": "MLB", "markets": ["batter_hits"]})["markets"] == ["batter_hits"]
    # An explicit empty list is a caller error, never a full sweep: `or None`
    # would have quietly turned one into the other.
    with pytest.raises(ValueError):
        v({"sport": "MLB", "markets": []})
    with pytest.raises(ValueError):
        v({"sport": "MLB", "markets": "batter_hits"})
    with pytest.raises(ValueError):
        v({"sport": "CRICKET"})


# ── what the probe found, and what was done about it ────────────────────────
#
# The 2026-09-05 probe asked 30 MLB keys on a live event and answered all
# three questions stored data cannot:
#
#   SERVED but not pulled     batter_doubles, batter_triples,
#                             batter_stolen_bases_alternate   -> added
#   SUPPORTED but nobody      pitcher_hits_allowed_alternate,
#   priced it                 pitcher_walks_alternate         -> dropped
#                             (they had also produced zero rows all day)
#   UNSUPPORTED key           batter_at_bats,
#                             pitcher_home_runs_allowed,
#                             pitcher_pitches                 -> stay blank

def _board_markets(sport: str) -> set[str]:
    """The player_prop_odds markets mobile/src/lib/statCatalog.ts can display.

    Two routes and both are followed, because they are the thing that drifts:
    a stat reaches its market THROUGH a model id (STAT_KEY_TO_MODEL ->
    markets.PROP_MARKET_BY_MODEL) unless it has no model, in which case a
    direct map carries it (STAT_KEY_TO_MARKET, and FOOTBALL_STAT_TO_MARKET for
    the two leagues that have no prop model at all).
    """
    import re
    cat = io.open(ROOT / "mobile" / "src" / "lib" / "statCatalog.ts", encoding="utf-8").read()
    mkt = io.open(ROOT / "mobile" / "src" / "lib" / "markets.ts", encoding="utf-8").read()

    catalog = cat.split("export const STAT_CATALOG")[1].split("];")[0]
    keys = {m.group(1) for m in re.finditer(
        r"\{ key: '([a-z_0-9]+)'[^}]*sport: '" + sport + r"'", catalog)}

    def table(src: str, name: str) -> dict[str, str]:
        body = src.split(name)[1].split("};")[0]
        return {m.group(1): m.group(2) for m in
                re.finditer(r"^\s*([a-z_0-9]+): '([a-z_0-9]+)'", body, re.M)}

    model_for = table(cat, "STAT_KEY_TO_MODEL")
    market_for_model = table(mkt, "PROP_MARKET_BY_MODEL")
    direct = table(cat, "STAT_KEY_TO_MARKET")
    football = table(cat, "FOOTBALL_STAT_TO_MARKET")

    out = set()
    for k in keys:
        if sport in ("NFL", "NCAAF"):
            if k in football:
                out.add(football[k])
            continue
        model = model_for.get(k)
        if model and model in market_for_model:
            out.add(market_for_model[model])
        elif k in direct:
            out.add(direct[k])
    return out


def test_the_mlb_board_and_the_mlb_pull_are_one_set():
    """The invariant football already carries, now that MLB has a stat with a
    market and no model: a market we pull that nothing can show is a credit
    spent every pass, and a board column with no market is a permanent dash.

    Model-backed stats resolve through their model id, so this compares the
    MARKETS, not the route to them.
    """
    board = _board_markets("MLB")
    pulled = set(config.PROP_MARKETS_ALL)
    # Board stats whose market comes via a model resolve to the same keys.
    from data.ingestors.prop_odds_ingestor import ALT_MARKET_REMAP
    assert board, "the MLB board maps some markets"
    assert board <= pulled, f"the board asks for markets we never pull: {board - pulled}"
    assert pulled - board == set(), f"we pull markets nothing can display: {pulled - board}"
    assert "batter_home_runs" in ALT_MARKET_REMAP.values(), "sanity: the HR remap still stands"


def test_the_columns_the_probe_proved_available_are_pulled():
    for m in ("batter_doubles", "batter_triples"):
        assert m in config.PROP_MARKETS_ALL, f"{m} came back SERVED and is still not pulled"
    assert "batter_stolen_bases_alternate" in config.PROP_ALT_MARKETS["MLB"]


def test_the_alternates_nobody_prices_are_gone():
    """Measured twice: zero rows across a full day of passes, and "supported,
    but no book priced it" from the probe."""
    for m in ("pitcher_hits_allowed_alternate", "pitcher_walks_alternate",
              "pitcher_earned_runs_alternate", "pitcher_outs_alternate"):
        assert m not in config.PROP_ALT_MARKETS["MLB"], f"{m} returns nothing and costs credits"


def test_every_mlb_alternate_still_has_a_standard_market():
    base = set(config.PROP_MARKETS_ALL)
    for k in config.PROP_ALT_MARKETS["MLB"]:
        assert k[:-len("_alternate")] in base, f"{k} has no standard market"
