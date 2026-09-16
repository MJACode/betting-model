"""
Market-handicap features for MLB game lines (runline / totals).

WHY THIS EXISTS
---------------
mike, 2026-09-16: the game models should learn the same board work a handicapper
uses — ticket vs money gaps, RLM, steam, open→current vs sharp — not another
pure "who covers" fundamentals stack.

`features/market_movement.py` already computed line-move / Pinnacle-gap columns;
`public_betting` already stored Action Network ticket/handle splits. Neither
reached the train matrix. `models/game_market_gate.py` only downgrades a BET to
NONE after `_decide`. This module is the TRAIN-TIME block.

WHAT IT PRODUCES
----------------
Public (Action Network, `public_betting` table):

  * `pub_home_ticket_pct` / `pub_home_money_pct` — 0-100 on the HOME runline
  * `pub_home_rlm` — money − tickets on home. Positive = money ahead of tickets
    on the home side (sharp-lean home / RLM against a public-away ticket pile).
  * `pub_fav_ticket_pct` / `pub_fav_money_pct` / `pub_fav_rlm` — the same three
    on the FAVORITE (home if `spread_home < 0`). Classic board: favorite −1.5
    at 90% tickets / 20% money → `pub_fav_rlm = -70` → lean the dog +1.5.
  * `pub_over_ticket_pct` / `pub_over_money_pct` / `pub_over_rlm` — totals.
  * `pub_dog_ticket_pct` / `pub_dog_rlm` — complement of the favorite.
  * Gated: `pub_*_present`, RLM × move, public-steam / RLM flags, fade-public-fav,
    `pub_home_vs_sharp`, `mkt_steam_home` / `mkt_total_steamed`. None unless
    the raw inputs exist (presence flags are 0/1 after attach).

Movement / sharp (reused from `MARKET_MOVEMENT_FEATURES`, no new odds joins):

  * open implied, signed/abs home-prob move, book disagreement, snapshot count,
    Pinnacle no-vig home, DK vs sharp, plus `mkt_spread_move` / `mkt_total_move`.

MISSING IS None, NEVER 0.0 — for the *raw* percentages, RLM, and line-move.
A game with no splits is not "0% public on home". Presence / steam *flags*
are the exception: they are 1/0 when the inputs exist so the model can
learn "we have splits" vs NaN, and stay None when the inputs to evaluate
them are missing (do not invent a 0-steam from a missing move).

XGBoost routes NaN; `SPARSE_OK_FEATURES` keeps those rows in train so a
pre-2026 SBR game is not deleted because Action Network did not exist.

AS-OF / LEAKAGE
---------------
Public rows and odds snapshots must be pre-game twice over: `snapshot_type`
is not enough (evening refresh keeps writing `open` after first pitch). The
Python bound is `_is_pregame_snapshot` (same helper as the rest of the engine:
actual first pitch when believable, scheduled start otherwise, fail-open on
a missing timestamp).

`public_betting` is UNIQUE(game_id, market, side, book) — one row, last upsert
wins. Measured 2026-09-16: 4,704 of 8,214 stored snapshots sit after
`commence_time` on a *text* compare; offset-aware parse + first-pitch leaves
**101 / 2,059** completed 2026 games with a pre-game home-runline split, and
**0 / 16,000** in 2019–2025 train. Those post-start rows are DROPPED here, not
used. The ingestor now refuses post-start upserts so future last-rows stay the
last pre-game split. Historical overwrites stay NaN.
"""

from __future__ import annotations

from collections import defaultdict


# ── Feature names (single source; FEATURE_MAP and SPARSE_OK import these) ─────

# Existing market_movement.py names, reused. A test pins this is a subset.
MLB_HANDICAP_MOVE_SHARED = [
    "mkt_open_implied_home",
    "mkt_move_home_pp",
    "mkt_move_abs_pp",
    "mkt_book_disagree_pp",
    "mkt_snapshots",
    "mkt_sharp_devig_home",
    "mkt_dk_vs_sharp_pp",
]
MLB_HANDICAP_MOVE_SPREAD = ["mkt_spread_move"]
MLB_HANDICAP_MOVE_TOTAL = ["mkt_total_move"]

MLB_HANDICAP_PUBLIC_HOME = [
    "pub_home_ticket_pct",
    "pub_home_money_pct",
    "pub_home_rlm",
]
MLB_HANDICAP_PUBLIC_FAV = [
    "pub_fav_ticket_pct",
    "pub_fav_money_pct",
    "pub_fav_rlm",
]
MLB_HANDICAP_PUBLIC_OVER = [
    "pub_over_ticket_pct",
    "pub_over_money_pct",
    "pub_over_rlm",
]

# Gated / interaction columns. None unless the raw inputs exist, except the
# `*_present` flags which are 1.0 / 0.0 after attach so XGBoost can split
# "have splits" vs "do not". Same 55% heavy as models.game_market_gate.
PUBLIC_HEAVY_TICKET_PCT = 55.0
PUBLIC_FADE_TICKET_PCT = 65.0
STEAM_HOME_PP = 3.0          # market_movement.md >3pp steam bucket
TOTAL_STEAM_PTS = 0.5        # game_market_gate line_steam_pts

MLB_HANDICAP_PUBLIC_DOG = [
    "pub_dog_ticket_pct",
    "pub_dog_rlm",
]
MLB_HANDICAP_GATES_SPREAD = [
    "pub_home_present",
    "mkt_move_present",
    "pub_home_rlm_x_move",
    "pub_fav_rlm_x_move",
    "pub_home_public_steam",
    "pub_home_rlm_flag",
    "pub_fav_public_steam",
    "pub_fav_rlm_flag",
    "pub_fade_public_fav",
    "pub_home_vs_sharp",
    "mkt_steam_home",
]
MLB_HANDICAP_GATES_TOTAL = [
    "pub_over_present",
    "mkt_total_move_present",
    "pub_over_rlm_x_move",
    "pub_over_public_steam",
    "pub_over_rlm_flag",
    "mkt_total_steamed",
]

MLB_HANDICAP_SPREAD_FEATURES = (
    MLB_HANDICAP_MOVE_SHARED
    + MLB_HANDICAP_MOVE_SPREAD
    + MLB_HANDICAP_PUBLIC_HOME
    + MLB_HANDICAP_PUBLIC_FAV
    + MLB_HANDICAP_PUBLIC_DOG
    + MLB_HANDICAP_GATES_SPREAD
)
MLB_HANDICAP_TOTAL_FEATURES = (
    MLB_HANDICAP_MOVE_SHARED
    + MLB_HANDICAP_MOVE_TOTAL
    + MLB_HANDICAP_PUBLIC_OVER
    + MLB_HANDICAP_GATES_TOTAL
)

HANDICAP_SPARSE_FEATURES = frozenset(
    MLB_HANDICAP_SPREAD_FEATURES + MLB_HANDICAP_TOTAL_FEATURES
)

_PUBLIC_EMPTY = {
    k: None
    for k in (
        MLB_HANDICAP_PUBLIC_HOME
        + MLB_HANDICAP_PUBLIC_FAV
        + MLB_HANDICAP_PUBLIC_OVER
    )
}


def empty_handicap() -> dict:
    """Every handicap column as None. Merge this, then overlay what we have."""
    out = {k: None for k in HANDICAP_SPARSE_FEATURES}
    return out


def favorite_side(spread_home) -> str | None:
    """'home' if home is laying the run; 'away' if home is getting it.

    None when the line is missing or a pick'em (spread_home == 0). The runline
    this model prices is ±1.5, so 0 should not appear; we still refuse to
    invent a favorite.
    """
    from features.feature_engine import numeric_feature_value

    s = numeric_feature_value(spread_home)
    if s is None or s == 0:
        return None
    return "home" if s < 0 else "away"


def _pct_pair(side_row: dict | None) -> tuple:
    """(ticket_pct, money_pct) as float-or-None. Empty/Decimal coerced."""
    from features.feature_engine import numeric_feature_value

    if not side_row:
        return None, None
    return (
        numeric_feature_value(side_row.get("ticket")),
        numeric_feature_value(side_row.get("money")),
    )


def _rlm(ticket, money):
    """money − tickets. None if either side is missing; 0.0 is a real flat split."""
    if ticket is None or money is None:
        return None
    return round(float(money) - float(ticket), 1)


def _mul(a, b):
    if a is None or b is None:
        return None
    return round(float(a) * float(b), 4)


def _gated_flag(*, have_inputs: bool, condition: bool) -> float | None:
    """None when we cannot evaluate; 1.0/0.0 when we can."""
    if not have_inputs:
        return None
    return 1.0 if condition else 0.0


def _fav_signed_home_move(move, spread_home):
    """Home-prob move from the favorite's point of view. None if either missing."""
    if move is None:
        return None
    fav = favorite_side(spread_home)
    if fav is None:
        return None
    m = float(move)
    return m if fav == "home" else -m


def build_rich_handicap(feat: dict, spread_home=None) -> dict:
    """Gated indicators + public×move interactions. Missing inputs stay None.

    Presence flags are 1.0/0.0 (never None) once attach has run: "we looked
    and there are no splits" is a real 0, not a missing percentage.
    """
    from features.feature_engine import numeric_feature_value

    out = dict(feat)
    if spread_home is None:
        spread_home = out.get("spread_home")

    home_t = numeric_feature_value(out.get("pub_home_ticket_pct"))
    home_rlm = numeric_feature_value(out.get("pub_home_rlm"))
    fav_t = numeric_feature_value(out.get("pub_fav_ticket_pct"))
    fav_rlm = numeric_feature_value(out.get("pub_fav_rlm"))
    over_t = numeric_feature_value(out.get("pub_over_ticket_pct"))
    over_rlm = numeric_feature_value(out.get("pub_over_rlm"))
    move = numeric_feature_value(out.get("mkt_move_home_pp"))
    total_move = numeric_feature_value(out.get("mkt_total_move"))
    sharp = numeric_feature_value(out.get("mkt_sharp_devig_home"))
    fav_move = _fav_signed_home_move(move, spread_home)

    if fav_t is not None:
        out["pub_dog_ticket_pct"] = round(100.0 - float(fav_t), 1)
    else:
        out["pub_dog_ticket_pct"] = None
    if fav_rlm is not None:
        out["pub_dog_rlm"] = round(-float(fav_rlm), 1)
    else:
        out["pub_dog_rlm"] = None

    out["pub_home_present"] = 1.0 if home_t is not None else 0.0
    out["mkt_move_present"] = 1.0 if move is not None else 0.0
    out["pub_over_present"] = 1.0 if over_t is not None else 0.0
    out["mkt_total_move_present"] = 1.0 if total_move is not None else 0.0

    out["pub_home_rlm_x_move"] = _mul(home_rlm, move)
    out["pub_fav_rlm_x_move"] = _mul(fav_rlm, fav_move)
    out["pub_over_rlm_x_move"] = _mul(over_rlm, total_move)

    out["pub_home_public_steam"] = _gated_flag(
        have_inputs=home_t is not None and move is not None,
        condition=home_t is not None and home_t >= PUBLIC_HEAVY_TICKET_PCT
        and move is not None and move > 0,
    )
    out["pub_home_rlm_flag"] = _gated_flag(
        have_inputs=home_t is not None and move is not None,
        condition=home_t is not None and home_t >= PUBLIC_HEAVY_TICKET_PCT
        and move is not None and move < 0,
    )
    out["pub_fav_public_steam"] = _gated_flag(
        have_inputs=fav_t is not None and fav_move is not None,
        condition=fav_t is not None and fav_t >= PUBLIC_HEAVY_TICKET_PCT
        and fav_move is not None and fav_move > 0,
    )
    out["pub_fav_rlm_flag"] = _gated_flag(
        have_inputs=fav_t is not None and fav_move is not None,
        condition=fav_t is not None and fav_t >= PUBLIC_HEAVY_TICKET_PCT
        and fav_move is not None and fav_move < 0,
    )
    out["pub_fade_public_fav"] = _gated_flag(
        have_inputs=fav_t is not None and fav_rlm is not None,
        condition=fav_t is not None and fav_t >= PUBLIC_FADE_TICKET_PCT
        and fav_rlm is not None and fav_rlm < 0,
    )
    out["pub_over_public_steam"] = _gated_flag(
        have_inputs=over_t is not None and total_move is not None,
        condition=over_t is not None and over_t >= PUBLIC_HEAVY_TICKET_PCT
        and total_move is not None and total_move > 0,
    )
    out["pub_over_rlm_flag"] = _gated_flag(
        have_inputs=over_t is not None and total_move is not None,
        condition=over_t is not None and over_t >= PUBLIC_HEAVY_TICKET_PCT
        and total_move is not None and total_move < 0,
    )

    if home_t is not None and sharp is not None:
        out["pub_home_vs_sharp"] = round(float(home_t) / 100.0 - float(sharp), 4)
    else:
        out["pub_home_vs_sharp"] = None

    out["mkt_steam_home"] = _gated_flag(
        have_inputs=move is not None,
        condition=move is not None and move >= STEAM_HOME_PP,
    )
    out["mkt_total_steamed"] = _gated_flag(
        have_inputs=total_move is not None,
        condition=total_move is not None and abs(total_move) >= TOTAL_STEAM_PTS,
    )
    return out


def build_public_features(splits: dict | None, spread_home=None) -> dict:
    """Turn one game's pre-game splits into the pub_* dict.

    `splits` shape: {market: {side: {"ticket": float, "money": float}}}
    Markets we read: 'spreads' for home/fav, 'totals' for over. We do not mix
    h2h splits onto a runline — the board example is the runline ticket pile.
    """
    out = dict(_PUBLIC_EMPTY)
    if not splits:
        return out

    spread_block = splits.get("spreads") or {}
    home_t, home_m = _pct_pair(spread_block.get("home"))
    out["pub_home_ticket_pct"] = home_t
    out["pub_home_money_pct"] = home_m
    out["pub_home_rlm"] = _rlm(home_t, home_m)

    fav = favorite_side(spread_home)
    if fav is not None:
        fav_t, fav_m = _pct_pair(spread_block.get(fav))
        out["pub_fav_ticket_pct"] = fav_t
        out["pub_fav_money_pct"] = fav_m
        out["pub_fav_rlm"] = _rlm(fav_t, fav_m)

    total_block = splits.get("totals") or {}
    over_t, over_m = _pct_pair(total_block.get("over"))
    out["pub_over_ticket_pct"] = over_t
    out["pub_over_money_pct"] = over_m
    out["pub_over_rlm"] = _rlm(over_t, over_m)
    return out


def attach_market_handicap(feat: dict, *, movement: dict | None = None,
                           splits: dict | None = None,
                           spread_home=None) -> dict:
    """Merge handicap columns onto a feature row. Missing stays None.

    `spread_home` defaults to the row's own `spread_home` so favorite framing
    matches the line the model is pricing. Callers that built the row from an
    h2h odds snapshot (live `build_mlb_game_features`) must pass the spreads
    line explicitly.
    """
    if feat is None:
        return feat
    if spread_home is None:
        spread_home = feat.get("spread_home")
    from features.market_movement import MARKET_MOVEMENT_FEATURES

    out = dict(feat)
    out.update(empty_handicap())
    if movement:
        for key in MARKET_MOVEMENT_FEATURES:
            if key in HANDICAP_SPARSE_FEATURES and key in movement:
                out[key] = movement[key]
    out.update(build_public_features(splits, spread_home=spread_home))
    out = build_rich_handicap(out, spread_home=spread_home)
    return out


def row_is_pregame(snapshot_at, commence_time, first_pitch_at=None,
                   as_of=None) -> bool:
    """True when this snapshot may enter a feature. Fail-open on missing clocks.

    `as_of` is an extra ceiling (live scoring "now", or a reconstructed tick).
    Training omits it; the commence/first-pitch bound is enough.
    """
    from features.feature_engine import _is_pregame_snapshot

    if not _is_pregame_snapshot(snapshot_at, commence_time, first_pitch_at):
        return False
    if as_of is not None and not _is_pregame_snapshot(snapshot_at, as_of):
        return False
    return True


def select_latest_pregame_splits(rows: list[dict], as_of=None) -> dict:
    """Filter leaked snapshots, then keep the newest row per (game, market, side).

    `rows` items need: game_id, market, side, ticket/public_bet_pct,
    money/public_money_pct, snapshot_at, commence_time, first_pitch_at (optional),
    book (optional).
    """
    from features.feature_engine import _parse_iso_ts, numeric_feature_value

    surviving: dict[tuple, dict] = {}
    for raw in rows or []:
        snap = raw.get("snapshot_at")
        if not row_is_pregame(snap, raw.get("commence_time"),
                              raw.get("first_pitch_at"), as_of=as_of):
            continue
        gid = raw.get("game_id")
        market = raw.get("market")
        side = raw.get("side")
        if not gid or not market or not side:
            continue
        key = (gid, market, side)
        prev = surviving.get(key)
        if prev is None:
            surviving[key] = raw
            continue
        # Newest snapshot wins; equal timestamps keep the one already stored.
        new_ts = _parse_iso_ts(snap)
        old_ts = _parse_iso_ts(prev.get("snapshot_at"))
        if new_ts is not None and (old_ts is None or new_ts >= old_ts):
            surviving[key] = raw

    by_game: dict[str, dict] = defaultdict(lambda: defaultdict(dict))
    for (gid, market, side), raw in surviving.items():
        ticket = numeric_feature_value(
            raw.get("ticket", raw.get("public_bet_pct")))
        money = numeric_feature_value(
            raw.get("money", raw.get("public_money_pct")))
        by_game[gid][market][side] = {"ticket": ticket, "money": money}
    # Convert defaultdicts to plain dicts so missing markets stay missing.
    return {gid: {m: dict(sides) for m, sides in markets.items()}
            for gid, markets in by_game.items()}


def load_public_splits(conn, sport: str = "MLB", game_id: str | None = None,
                       as_of=None) -> dict:
    """Bulk-load as-of-safe public splits. {game_id: {market: {side: pcts}}}."""
    extra = ""
    params: list = [sport]
    if game_id:
        extra = " AND pb.game_id = %s"
        params.append(game_id)
    rows = conn.execute(f"""
        SELECT pb.game_id, pb.market, pb.side, pb.book,
               pb.public_bet_pct, pb.public_money_pct, pb.snapshot_at,
               g.commence_time, g.first_pitch_at
        FROM public_betting pb
        JOIN games g ON g.game_id = pb.game_id
        WHERE g.sport = %s
          {extra}
        ORDER BY pb.game_id, pb.market, pb.side, pb.snapshot_at
    """, tuple(params)).fetchall()
    parsed = []
    for r in rows:
        parsed.append({
            "game_id": r[0], "market": r[1], "side": r[2], "book": r[3],
            "public_bet_pct": r[4], "public_money_pct": r[5],
            "snapshot_at": r[6], "commence_time": r[7], "first_pitch_at": r[8],
        })
    return select_latest_pregame_splits(parsed, as_of=as_of)


def load_market_movement_for_game(conn, game_id: str, sport: str = "MLB",
                                  decision_book: str = "draftkings") -> dict | None:
    """One game's movement dict, or None when we never saw a pre-game snapshot."""
    from features.market_movement import load_market_movement

    by_game = load_market_movement(conn, sport, decision_book=decision_book,
                                   game_id=game_id)
    return by_game.get(game_id)


def lookup_pregame_spread_home(conn, game_id: str) -> float | None:
    """Latest pre-game DK (else any) home spread. None if we never saw one.

    Live `build_mlb_game_features` is handed the h2h odds row, which has no
    spread. Favorite framing still needs the runline number.
    """
    from features.feature_engine import (
        _is_pregame_snapshot, numeric_feature_value,
    )

    rows = conn.execute("""
        SELECT o.spread_home, o.snapshot_at, o.bookmaker,
               g.commence_time, g.first_pitch_at
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.game_id = %s
          AND o.market = 'spreads'
          AND COALESCE(o.snapshot_type, '') <> 'in_play'
          AND o.spread_home IS NOT NULL
        ORDER BY CASE o.bookmaker WHEN 'draftkings' THEN 0 ELSE 1 END,
                 o.snapshot_at DESC
    """, (game_id,)).fetchall()
    for spread, snap, _book, commence, first_pitch in rows:
        if _is_pregame_snapshot(snap, commence, first_pitch):
            return numeric_feature_value(spread)
    return None


def load_handicap_for_game(conn, game_id: str, spread_home=None,
                           sport: str = "MLB") -> dict:
    """Serve-time convenience: movement + public for one game, already merged."""
    if spread_home is None:
        spread_home = lookup_pregame_spread_home(conn, game_id)
    movement = load_market_movement_for_game(conn, game_id, sport=sport)
    splits = load_public_splits(conn, sport=sport, game_id=game_id).get(game_id)
    return attach_market_handicap(
        {}, movement=movement, splits=splits, spread_home=spread_home)
