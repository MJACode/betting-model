"""
Unit tests for multi-book line shopping.

Two things are covered here:

1. The player-prop parser is book-aware — the same player/market priced at two
   books produces two independent rows whose prices never merge.
2. The DraftKings isolation guarantee: every model-facing read of odds still
   hard-filters to draftkings. Extra books are DISPLAY-ONLY. If someone ever
   refactors one of those queries and drops the filter, a FanDuel/BetMGM price
   could silently reach scoring, training, or CLV — these tests fail loudly
   instead.

Pure-function / static-source tests — no network, no DB.
"""

import re
from pathlib import Path

from data.ingestors.prop_odds_ingestor import _parse_prop_markets

import config

REPO = Path(__file__).resolve().parent.parent


def _prop_markets(over_price, under_price, over_link=None):
    return [
        {
            "key": "batter_hits",
            "outcomes": [
                {"name": "Over", "description": "Aaron Judge",
                 "price": over_price, "point": 1.5, "link": over_link},
                {"name": "Under", "description": "Aaron Judge",
                 "price": under_price, "point": 1.5},
            ],
        }
    ]


# ── Multi-book prop parsing ──────────────────────────────────────────────────

def test_prop_rows_are_stamped_with_their_bookmaker():
    rows = _parse_prop_markets(
        _prop_markets(-130, 110), "G1", "2026-08-01", "open", "ts",
        allowed_markets={"batter_hits"}, bookmaker="betmgm",
    )
    assert len(rows) == 1
    assert rows[0]["bookmaker"] == "betmgm"


def test_prop_bookmaker_defaults_to_draftkings():
    """Back-compat: existing callers that omit `bookmaker` still write DK rows."""
    rows = _parse_prop_markets(
        _prop_markets(-130, 110), "G1", "2026-08-01", "open", "ts",
        allowed_markets={"batter_hits"},
    )
    assert rows[0]["bookmaker"] == config.ODDS_API_BOOKMAKER == "draftkings"


def test_same_player_at_two_books_does_not_merge_prices():
    """
    The parser builds its row dict keyed by (market, player). It is called once
    per book, so each call gets a fresh dict — two books must never collapse
    into one row or overwrite each other's prices.
    """
    dk = _parse_prop_markets(
        _prop_markets(-130, 110, "DK_LINK"), "G1", "2026-08-01", "open", "ts",
        allowed_markets={"batter_hits"}, bookmaker="draftkings",
    )
    fd = _parse_prop_markets(
        _prop_markets(-115, -105, "FD_LINK"), "G1", "2026-08-01", "open", "ts",
        allowed_markets={"batter_hits"}, bookmaker="fanduel",
    )

    assert len(dk) == 1 and len(fd) == 1
    assert dk[0]["player_name"] == fd[0]["player_name"] == "Aaron Judge"
    assert dk[0]["market"] == fd[0]["market"] == "batter_hits"

    # Same proposition, different prices and links — the whole point of shopping.
    assert dk[0]["over_price"] == -130 and fd[0]["over_price"] == -115
    assert dk[0]["under_price"] == 110 and fd[0]["under_price"] == -105
    assert dk[0]["over_link"] == "DK_LINK" and fd[0]["over_link"] == "FD_LINK"


# ── Config invariants ────────────────────────────────────────────────────────

def test_model_still_scores_against_draftkings():
    assert config.ODDS_API_BOOKMAKER == "draftkings"


def test_draftkings_is_always_first_line_shop_book():
    """DK must be present and first — the models depend on its rows existing."""
    assert config.LINE_SHOP_BOOKMAKERS[0] == "draftkings"
    assert config.ODDS_API_BOOKMAKERS_PARAM.split(",")[0] == "draftkings"


def test_books_param_has_no_duplicates():
    books = config.ODDS_API_BOOKMAKERS_PARAM.split(",")
    assert len(books) == len(set(books))


# ── DraftKings isolation (the safety net) ────────────────────────────────────

def _source(rel: str) -> str:
    # encoding pinned: these sources are UTF-8, and on Windows the default
    # locale codec (cp1252) raises UnicodeDecodeError on them -- which made
    # this whole file error out rather than assert, silently disarming the
    # DraftKings-only tripwire it exists to be.
    return (REPO / rel).read_text(encoding="utf-8")


def test_scorer_prop_odds_filters_draftkings():
    """models/scorer.py `_get_prop_dk_odds` must pin props to DK."""
    src = _source("models/scorer.py")
    assert "FROM player_prop_odds" in src
    # The only player_prop_odds read in the scorer must carry a DK filter.
    for block in src.split("FROM player_prop_odds")[1:]:
        window = block[:400]
        assert re.search(r"bookmaker\s*=\s*'draftkings'", window), (
            "a player_prop_odds read in scorer.py lost its draftkings filter — "
            "non-DK prices could reach scoring"
        )


def test_closing_line_reads_filter_draftkings():
    """CLV must be measured against DK's close, not whichever book is best."""
    src = _source("tracking/paper_tracker.py")
    for block in src.split("FROM odds")[1:]:
        window = block[:400]
        assert re.search(r"bookmaker\s*=\s*'draftkings'", window), (
            "a paper_tracker odds read lost its draftkings filter"
        )


def test_feature_engines_whitelist_draftkings():
    """
    Training features must never see a line-shop book. Each engine whitelists
    draftkings (+ sbr_consensus for synthetic historical lines). Without this,
    adding books would multiply training rows per game.
    """
    engines = [
        "features/feature_engine.py",
        "features/wnba_feature_engine.py",
        "features/nba_feature_engine.py",
    ]
    for rel in engines:
        src = _source(rel)
        for block in src.split("FROM odds")[1:]:
            window = block[:600]
            assert "bookmaker IN ('draftkings', 'sbr_consensus')" in window, (
                f"{rel}: an odds read is missing the draftkings whitelist — "
                "line-shop books would leak into training features"
            )


def test_line_shop_books_are_not_referenced_by_scoring_code():
    """
    LINE_SHOP_BOOKMAKERS is a display concern. The scorer and settlement must
    not import it — that would be the first step toward scoring a non-DK price.
    """
    for rel in ("models/scorer.py", "tracking/paper_tracker.py"):
        assert "LINE_SHOP_BOOKMAKERS" not in _source(rel), (
            f"{rel} references LINE_SHOP_BOOKMAKERS — scoring must stay DK-only"
        )


# ── Line-shop retention (data/prune_odds.py) ─────────────────────────────────

def test_prune_never_touches_the_scoring_book():
    """
    draftkings powers CLV / line movement / opening signals, and sbr_consensus
    is synthetic TRAINING data for the feature engines. Pruning either would
    silently degrade the model, so both must stay protected.
    """
    from data.prune_odds import PROTECTED_BOOKMAKERS
    assert "draftkings" in PROTECTED_BOOKMAKERS
    assert "sbr_consensus" in PROTECTED_BOOKMAKERS


def test_prune_predicates_date_by_game_not_snapshot():
    """
    The `odds` table has NO date column — dating a row by its snapshot would
    prune a future UFC/golf event's only line-shop row (those are priced up to
    7 days ahead). Both tables must key retention on the GAME's date.
    """
    from data.prune_odds import _TABLES, _older_than
    by_table = {t: (ident, sql) for t, ident, sql in _TABLES}

    odds_sql = _older_than(by_table["odds"][1], "<", "cutoff")
    assert "games" in odds_sql and "game_date" in odds_sql, (
        "odds retention must resolve game_date via the games table"
    )

    prop_sql = _older_than(by_table["player_prop_odds"][1], "<", "cutoff")
    assert prop_sql.startswith("game_date <"), (
        "player_prop_odds carries game_date directly"
    )


def test_prune_identity_matches_the_all_books_views():
    """
    Tier 2 keeps the newest row per proposition per book — that partition MUST
    match the views' DISTINCT ON, or pruning would delete a row the app reads.
    """
    from data.prune_odds import _TABLES
    by_table = {t: ident for t, ident, _ in _TABLES}
    assert by_table["odds"] == ("game_id", "market")
    assert by_table["player_prop_odds"] == ("game_id", "market", "player_name")


def test_prune_rejects_keep_days_below_one():
    """keep_days=0 would prune today's rows and blank the live board."""
    import pytest
    from data.prune_odds import run_prune_odds
    with pytest.raises(ValueError):
        run_prune_odds(run_date="2026-08-01", keep_days=0)


def test_prune_never_touches_cfbd_archive_lines():
    """
    CFBD historical lines (cfbd_draftkings, cfbd_bovada, …) are NCAAF training
    data: one snapshot per game on long-finished games — exactly the shape
    Tier 1 deletes. The first 47,204-row lines backfill was wiped by the next
    6am worker run (2026-08-22) because these labels weren't protected.
    """
    from data.prune_odds import PROTECTED_BOOKMAKER_PREFIXES, _unprotected

    assert any("cfbd".startswith(p) or p == "cfbd"
               for p in PROTECTED_BOOKMAKER_PREFIXES)

    params: dict = {"protected": ("draftkings", "sbr_consensus")}
    pred = _unprotected(params)
    # The predicate must exclude prefix-protected books, and the pattern must
    # actually cover every label ncaaf_line_bookmaker() can emit.
    assert "NOT LIKE" in pred
    patterns = [v for k, v in params.items() if k.startswith("protected_pfx_")]
    import config
    for provider in ("DraftKings", "Bovada", "consensus", "teamrankings"):
        label = config.ncaaf_line_bookmaker(provider)
        assert any(label.startswith(pat[:-1]) for pat in patterns if pat.endswith("%")), (
            f"{label} would be prunable — archive lines must survive the pruner")
