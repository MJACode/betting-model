"""
Market movement as a FEATURE — the data the models price against but never read.

WHY THIS EXISTS
---------------
mike, 2026-08-31: "are you using odds api data?" For pricing, yes; for
predicting, almost not at all. Across every feature engine in the repo the only
market-derived inputs are `total_line`, `spread_home`, `implied_team_total` and
`implied_opp_total` — four static numbers taken from one snapshot of one book.
Meanwhile Supabase holds 660,961 MLB odds rows over 42,330 games from 8 books at
~15.6 snapshots per game, going back to 2009, and 361,299 more for NCAAF. The
models are handed a photograph of a market they are never allowed to watch move.

THE MEASUREMENT THAT JUSTIFIES IT
---------------------------------
MLB, DraftKings h2h, games with >= 4 pre-game snapshots, bucketed by how the
home implied probability moved between the first pre-game snapshot and the last:

    away steamed  > 3pp   166 games   opened 0.552   home won 49.4%
    away drift  1-3pp     334 games   opened 0.550   home won 52.7%
    flat  within 1pp      551 games   opened 0.550   home won 50.8%
    home drift  1-3pp     316 games   opened 0.549   home won 55.4%
    home steamed  > 3pp   167 games   opened 0.550   home won 55.1%

Every bucket opens at essentially the same price, so the movement is not team
strength in disguise; yet the realised win rate spans six points, monotonically.
Beat-the-close is 0 to -4pp in every bucket, which is the ordinary finding that
the closing line is efficient -- so the move is not to beat the close but to
READ it.

WHAT THIS MODULE IS CAREFUL ABOUT
---------------------------------
* PRE-GAME ONLY, twice over: `snapshot_type <> 'in_play'` AND
  `snapshot_at <= commence_time`. Both are needed, because the evening refresh
  keeps writing `open` rows after first pitch (§7's leak trap). The bound uses
  the same fail-open helper as the rest of the engine, so SBR and synthetic rows
  with no usable timestamp survive.
* TRAIN AND SERVE COMPUTE THE SAME THING. "Latest" here always means the latest
  PRE-GAME snapshot, which at serve time is simply the newest row; there is no
  separate live path to drift out of step with the training one.
* SILENT ON THIN DATA. A game with one snapshot has no movement, and this
  returns None rather than 0.0 for it -- zero is a real value meaning "the line
  did not move", and conflating it with "we never saw the line" is how a feature
  teaches a model that missing data is a signal.
"""

from __future__ import annotations

from collections import defaultdict

import config
from features.feature_engine import _is_pregame_snapshot, _parse_iso_ts
from models.market_relative import devig

# Every feature this module can produce. Named once so the builders, the tests
# and the activation patch cannot drift apart.
MARKET_MOVEMENT_FEATURES = [
    "mkt_open_implied_home",   # the opening pre-game price, as a probability
    "mkt_move_home_pp",        # latest - open, in probability POINTS (signed)
    "mkt_move_abs_pp",         # magnitude of the move, direction discarded
    "mkt_book_disagree_pp",    # spread across books at the latest snapshot
    "mkt_snapshots",           # how many pre-game snapshots we saw
    "mkt_total_move",          # latest total_line - opening total_line
    "mkt_spread_move",         # latest spread_home - opening spread_home
    "mkt_sharp_devig_home",    # Pinnacle's no-vig home probability, latest pre-game
    "mkt_dk_vs_sharp_pp",      # DK implied - sharp no-vig, in probability points
]

_EMPTY = {k: None for k in MARKET_MOVEMENT_FEATURES}


def american_to_prob(price) -> float | None:
    """American odds -> implied probability, vig included.

    Vig is deliberately left in. These features are about MOVEMENT and
    DISAGREEMENT, both of which are differences: the overround cancels in the
    first and is the point of the second.
    """
    if price is None:
        return None
    try:
        p = float(price)
    except (TypeError, ValueError):
        return None
    if p == 0:
        return None
    return (-p / (-p + 100.0)) if p < 0 else (100.0 / (p + 100.0))


def load_market_movement(conn, sport: str, decision_book: str = "draftkings") -> dict:
    """Bulk-load every pre-game h2h/totals/spreads snapshot for one sport.

    One query rather than per-game lookups: the same reason the rest of the
    engines bulk-load. Returns {game_id: {feature: value}}, ready to merge into
    a feature row.
    """
    rows = conn.execute("""
        SELECT o.game_id, o.bookmaker, o.snapshot_at, o.home_price,
               o.away_price, o.total_line, o.spread_home,
               -- ACTUAL first pitch where we know it, scheduled start where we
               -- do not. commence_time runs ~16-20 minutes late against
               -- reality (data/first_pitch.py), so bounding on it alone admits
               -- rows from the first innings as "pre-game".
               COALESCE(g.first_pitch_at, g.commence_time) AS commence_time
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = %s
          AND COALESCE(o.snapshot_type, '') <> 'in_play'
        ORDER BY o.game_id, o.snapshot_at
    """, (sport,)).fetchall()

    per_game: dict[str, list[dict]] = defaultdict(list)
    for (game_id, book, snap, home_price, away_price,
         total_line, spread_home, commence) in rows:
        if not _is_pregame_snapshot(snap, commence):
            continue
        per_game[game_id].append({
            "book": book, "snap": snap,
            "home_price": home_price, "away_price": away_price,
            "total_line": total_line, "spread_home": spread_home,
        })
    return {gid: build_market_features(snaps, decision_book)
            for gid, snaps in per_game.items()}


def build_market_features(snaps: list[dict], decision_book: str = "draftkings") -> dict:
    """Turn one game's pre-game snapshots into the feature dict.

    Split out from the loader so it can be exercised without a database, and so
    a live scorer can call it with whatever rows it already holds.
    """
    if not snaps:
        return dict(_EMPTY)

    ordered = sorted(snaps, key=lambda r: (_parse_iso_ts(r["snap"]) is None,
                                           _parse_iso_ts(r["snap"]) or 0,
                                           str(r["snap"])))
    # The decision book leads, because every threshold in this repo was swept on
    # DK-implied edge (CLAUDE.md §6). Falling back to all books keeps a game
    # with no DK coverage from silently losing the feature entirely.
    book_rows = [r for r in ordered if r["book"] == decision_book] or ordered

    out = dict(_EMPTY)
    out["mkt_snapshots"] = len(book_rows)

    priced = [r for r in book_rows if american_to_prob(r["home_price"]) is not None]
    if priced:
        p_open = american_to_prob(priced[0]["home_price"])
        p_last = american_to_prob(priced[-1]["home_price"])
        out["mkt_open_implied_home"] = round(p_open, 4)
        # None, not 0.0, when there is only one price: "the line did not move"
        # and "we only ever saw it once" are different facts.
        if len(priced) >= 2:
            move = (p_last - p_open) * 100.0
            out["mkt_move_home_pp"] = round(move, 2)
            out["mkt_move_abs_pp"] = round(abs(move), 2)

    totals = [r for r in book_rows if r["total_line"] is not None]
    if len(totals) >= 2:
        out["mkt_total_move"] = round(float(totals[-1]["total_line"])
                                      - float(totals[0]["total_line"]), 2)
    spreads = [r for r in book_rows if r["spread_home"] is not None]
    if len(spreads) >= 2:
        out["mkt_spread_move"] = round(float(spreads[-1]["spread_home"])
                                       - float(spreads[0]["spread_home"]), 2)

    # Cross-book disagreement, using each book's OWN latest pre-game price.
    #
    # Not "every book at the last timestamp": books do not publish on the same
    # tick, so pinning them to one moment leaves most games with a single quote
    # and the feature null. Taking each book's newest price keeps the quantity
    # comparable while actually populating -- and the staleness this admits is
    # bounded by the same pre-game window everything else here uses.
    at_last = {}
    for r in ordered:                      # ordered oldest-first, so later wins
        prob = american_to_prob(r["home_price"])
        if prob is not None:
            at_last[r["book"]] = prob
    if len(at_last) >= 2:
        out["mkt_book_disagree_pp"] = round(
            (max(at_last.values()) - min(at_last.values())) * 100.0, 2)

    # ── The sharp book's no-vig price, and DK's distance from it ─────────────
    #
    # A sharp book's de-vigged number is the best single public estimate of a
    # true probability, and "where does DK sit relative to it" is a different
    # and better question than "what do I think will happen". Two-sided by
    # necessity: devig needs both prices, so a one-way quote yields nothing
    # rather than a half-corrected number.
    #
    # Latest pre-game snapshot per book, not the last row overall -- the sharp
    # book and DK do not publish on the same tick, so pinning both to one
    # timestamp would drop most games.
    sharp_book = (config.SHARP_BOOKMAKERS or ["pinnacle"])[0]
    sharp = _latest_two_sided(ordered, sharp_book)
    if sharp is not None:
        home_p, _ = devig(sharp["home_price"], sharp["away_price"])
        if home_p is not None:
            out["mkt_sharp_devig_home"] = round(home_p, 4)
            dk_last = _latest_two_sided(ordered, decision_book)
            dk_prob = american_to_prob(dk_last["home_price"]) if dk_last else None
            if dk_prob is not None:
                out["mkt_dk_vs_sharp_pp"] = round((dk_prob - home_p) * 100.0, 2)

    return out


def _latest_two_sided(ordered: list[dict], book: str) -> dict | None:
    """The newest pre-game snapshot for `book` carrying BOTH prices."""
    for row in reversed(ordered):
        if row["book"] == book and row.get("home_price") is not None \
                and row.get("away_price") is not None:
            return row
    return None
