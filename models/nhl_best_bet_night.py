"""
NHL best bet a night: Pinnacle's no-vig price against a bettable book, once a night.

mike, 2026-11-22: "Yes" to building it on all four markets, deciding after both
goalies are confirmed, one bet a night, flat stake, skipping a game that
already holds an NHL bet. Four model ids, one per market, because a pick
settles on its model's market (tracking/paper_tracker._RULE_MODEL_MARKETS):

    nhl_night_puckline    the puck line (spreads, the home number)
    nhl_night_total       the full-game total
    nhl_night_moneyline   the moneyline (overtime and shootout in)
    nhl_night_regulation  the regulation 3-way (home, draw, away after 60 min)

They are ONE rule and share one night: at most one bet a night across the four.

THE RULE, per unstarted game whose two goalies are confirmed
(models/nhl_goalie_gate.py), on every refresh pass and goalie-window tick:
  1. Per market, take the newest stored fetch that holds Pinnacle's price,
     taken after the matchup became known (after_confirmation, per market:
     the four are not fetched together); skip the market this pass if a
     newer fetch exists without Pinnacle ("pinnacle_withdrawn"), as
     models/nhl_totals_market.py does.
  2. De-vig Pinnacle by the POWER method (each implied chance raised to the one
     power that makes them sum to 1); its overround must be strictly between
     1.00 and 1.15 (1.20 for the 3-way).
  3. Price every bettable book IN THAT SAME FETCH at the same number: EV =
     fair x decimal - 1, every outcome, -200 or better.
  4. A game's candidate is its largest EV across the four markets, if at
     least the model's floor (0.01, config.MODEL_OWN_EV_FLOOR).
  5. The night's bet is the largest candidate EV on the FIRST pass that has
     any, among the night's games with no NHL BET standing. Once the night
     has a bet, nothing more is written for it.

THE EVIDENCE (docs/nhl_sharp_vs_soft.md, "The best bet a night with both
goalies confirmed"; scripts/nhl_best_bet_confirmed_goalies.py). 2021-22 to
2025-26, each game at its first stored fetch after DailyFaceoff's archive
(nhl_goalie_archive) shows both goalies confirmed, the first bet of the night:
puck line, moneyline, 3-way and totals, power de-vig, EV >= 0.01: 323 bets,
+63.9u, +18.6% (+5.6..+31.6), every season positive, +53.9u without the ten
best nights. The same with DraftKings as the reference: +20.8u; FanDuel +4.3u.
A higher floor did not do better (3% and up: 80 bets, -11.1%), so the stake is
flat. Without totals the proportional split is +5.7% on 276: totals carry a
good part of it, and nhl_over_under bets totals the same way, game by game.
THIS CODE, REPLAYED over the same seasons (scripts/nhl_best_bet_night_replay.py,
2026-11-22: every stored fetch a pass, goalies as the archive has them, cut at
the scheduled puck drop, goalie timing per market): 323 bets, +66.5u, +20.0%
(+6.9..+33.1), CLV +2.13%, every season positive, +56.5u without the ten best
nights. On 319 of the research's 323 nights it makes the same bet (game,
market and side); the other 4 differ by 0.1u in all.
NOT IN THE BACKTEST: the skip of a game that already holds an NHL bet, and the
live decision moment (the history holds about noon and the start hour; live,
the goalie window decides within minutes of a confirmation).

ONE GAME, NO TWO BETS THAT CANNOT BOTH WIN. This card skips a game holding any
NHL BET; the side models (models/scorer._apply_side_conflicts) and the totals
card (scripts/nhl_totals_card.publish) read this model's standing BETs and do
not bet against them.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import config
from models.market_relative import implied

FAMILY = "nhl_best_bet_night"
MARKET_MODEL = {
    "spreads": "nhl_night_puckline",
    "totals": "nhl_night_total",
    "h2h": "nhl_night_moneyline",
    "h2h_3way": "nhl_night_regulation",
}
MODEL_IDS = tuple(MARKET_MODEL.values())
SHARP_BOOK = "pinnacle"
REFERENCE_BOOK = "draftkings"
SOFT_BOOKS = tuple(b for b in config.BEST_LINE_BOOKMAKERS if b != SHARP_BOOK)

# market -> (outcomes, price columns, link columns, line column, overround range)
SPEC = {
    "spreads": (("home", "away"), ("home_price", "away_price"), ("home_link", "away_link"),
                "spread_home", (1.0, 1.15)),
    "totals": (("over", "under"), ("over_price", "under_price"), ("over_link", "under_link"),
               "total_line", (1.0, 1.15)),
    "h2h": (("home", "away"), ("home_price", "away_price"), ("home_link", "away_link"),
            None, (1.0, 1.15)),
    "h2h_3way": (("home", "draw", "away"), ("home_price", "draw_price", "away_price"),
                 ("home_link", "draw_link", "away_link"), None, (1.0, 1.20)),
}
DIAG_KEYS = ("games", "no_sharp", "pinnacle_withdrawn", "stale_fetch", "sharp_incoherent",
             "no_pair", "compared", "below_price_floor", "below_ev_floor", "candidates")


@dataclass(frozen=True)
class Candidate:
    game_id: str
    market: str
    model_id: str
    side: str                       # home / away / draw / over / under
    book: str
    line: float | None              # spread_home or total_line; None for h2h / 3-way
    price: float
    fair: float                     # Pinnacle's power-de-vigged probability of `side`
    ev: float
    created_at: str                 # the fetch (odds.created_at text)
    link: str | None
    dk_price: float | None
    dk_link: str | None


def power_devig(prices) -> list[float] | None:
    """Each implied chance to the one power k (>= 1) that makes them sum to 1.
    None when a price is missing or the set already sums to 1 or less."""
    ps = [implied(p) for p in prices]
    if any(p is None or p <= 0 or p >= 1 for p in ps):
        return None
    if sum(ps) <= 1.0:
        return None
    lo, hi = 1.0, 4.0
    for _ in range(60):
        k = (lo + hi) / 2
        if sum(p ** k for p in ps) > 1.0:
            lo = k
        else:
            hi = k
    k = (lo + hi) / 2
    out = [p ** k for p in ps]
    s = sum(out)
    return [x / s for x in out]


def _fetch_ts(row):
    from features.feature_engine import _parse_iso_ts
    return _parse_iso_ts(row.get("created_ts") or row.get("created_at"))


def _snap_ts(row):
    from features.feature_engine import _parse_iso_ts
    return _parse_iso_ts(row.get("snapshot_at"))


def _line(row, market):
    col = SPEC[market][3]
    if col is None:
        return None
    v = row.get(col)
    return None if v is None else float(v)


def _overround(row, market):
    ps = [implied(row.get(c)) for c in SPEC[market][1]]
    if any(p is None for p in ps):
        return None
    return sum(ps)


def load_quotes(conn, game_ids) -> list[dict]:
    """Per game and market: Pinnacle's newest complete pre-game row; the newest
    pre-game row from any book but DraftKings (to see a later fetch without
    Pinnacle); and every bettable book's newest row in Pinnacle's own fetch.
    Bounded on games.commence_time by snapshot_at AND created_at: in-play NHL
    rows are stored as 'open' too."""
    game_ids = list(game_ids)
    if not game_ids:
        return []
    books = list(SOFT_BOOKS) + ([REFERENCE_BOOK] if REFERENCE_BOOK not in SOFT_BOOKS else [])
    cols = ("game_id", "market", "bookmaker", "created_at", "created_ts", "snapshot_at",
            "home_price", "away_price", "draw_price", "spread_home", "total_line",
            "over_price", "under_price", "home_link", "away_link", "draw_link",
            "over_link", "under_link")
    # created_ts is named: unnamed, it would be a second "created_at" in the
    # CTEs, and the soft join on p.created_at would be ambiguous.
    sel = ("o.game_id, o.market, o.bookmaker, o.created_at, o.created_at::timestamptz AS created_ts, "
           "o.snapshot_at, o.home_price, o.away_price, o.draw_price, o.spread_home, "
           "o.total_line, o.over_price, o.under_price, o.home_link, o.away_link, "
           "o.draw_link, o.over_link, o.under_link")
    rows = conn.execute(f"""
        WITH g AS (
            SELECT game_id, commence_time::timestamptz AS ct
            FROM games WHERE game_id = ANY(%s) AND commence_time IS NOT NULL
        ),
        pre AS (
            SELECT o.* FROM odds o JOIN g ON g.game_id = o.game_id
            WHERE o.market = ANY(%s) AND o.snapshot_type = 'open'
              AND o.snapshot_at::timestamptz <= g.ct
              AND o.created_at::timestamptz <= g.ct
        ),
        p AS (
            SELECT DISTINCT ON (o.game_id, o.market) {sel}
            FROM pre o WHERE o.bookmaker = %s
            ORDER BY o.game_id, o.market, o.created_at::timestamptz DESC,
                     o.snapshot_at::timestamptz DESC
        ),
        newest AS (
            SELECT DISTINCT ON (o.game_id, o.market) {sel}
            FROM pre o WHERE o.bookmaker <> %s
            ORDER BY o.game_id, o.market, o.created_at::timestamptz DESC
        ),
        soft AS (
            SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker) {sel}
            FROM pre o JOIN p ON p.game_id = o.game_id AND p.market = o.market
                             AND p.created_at = o.created_at
            WHERE o.bookmaker = ANY(%s)
            ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at::timestamptz DESC
        )
        SELECT * FROM p UNION ALL SELECT * FROM newest UNION ALL SELECT * FROM soft
    """, (game_ids, list(SPEC), SHARP_BOOK, REFERENCE_BOOK, books)).fetchall()
    out = []
    for r in rows:
        q = dict(zip(cols, r))
        q["book"] = q.pop("bookmaker")
        for k in ("home_price", "away_price", "draw_price", "spread_home", "total_line",
                  "over_price", "under_price"):
            if q[k] is not None:
                q[k] = float(q[k])
        out.append(q)
    return out


def after_confirmation(quotes, known_at: dict) -> tuple[list[dict], list[tuple[str, str]]]:
    """The quotes of each (game, market) whose newest Pinnacle fetch was taken
    at or after the game's goalie matchup became known, and the pairs held.

    Per MARKET, not per game: Pinnacle's four markets are not fetched together
    (2026-11-08 to 11-21, 19 of 96 games had their newest 3-way price more than
    30 minutes older than their newest total), so a game-level check would
    price a market set before the goalie news. A game with no recorded moment
    keeps its quotes, as scripts/nhl_totals_card.after_confirmation does."""
    newest: dict = {}
    for q in quotes:
        if q.get("book") == SHARP_BOOK:
            ts = _fetch_ts(q)
            key = (q["game_id"], q["market"])
            if ts is not None and (key not in newest or ts > newest[key]):
                newest[key] = ts
    held = sorted(k for k, ts in newest.items()
                  if known_at.get(k[0]) is not None and ts < known_at[k[0]])
    drop = set(held)
    return [q for q in quotes if (q["game_id"], q["market"]) not in drop], held


def game_candidates(quotes, soft_books=None, min_odds=None, now=None,
                    floors: dict | None = None) -> tuple[dict, dict]:
    """{game_id: best Candidate across markets} and the pass diagnostic.

    `floors` maps model id -> EV floor (default config.min_ev_for). `now`
    refuses a market whose newest Pinnacle fetch is older than
    config.PREGAME_PRICE_MAX_AGE_MIN (None, the replay's, applies no age check).
    """
    soft = tuple(soft_books) if soft_books is not None else SOFT_BOOKS
    oldest = None if now is None else now - timedelta(minutes=config.PREGAME_PRICE_MAX_AGE_MIN)
    diag = dict.fromkeys(DIAG_KEYS, 0)
    by_gm: dict = defaultdict(list)
    for q in quotes:
        by_gm[(q["game_id"], q["market"])].append(q)
    best: dict[str, Candidate] = {}
    games = {g for g, _ in by_gm}
    diag["games"] = len(games)
    for (gid, market), rows in sorted(by_gm.items()):
        if market not in SPEC:
            continue
        model_id = MARKET_MODEL[market]
        floor = (floors or {}).get(model_id, config.min_ev_for(model_id))
        price_floor = config.min_odds_for(model_id) if min_odds is None else min_odds
        outs, pcols, lcols, _, coh = SPEC[market]
        pins = [r for r in rows if r["book"] == SHARP_BOOK and _fetch_ts(r) is not None]
        if not pins:
            diag["no_sharp"] += 1
            continue
        sharp = max(pins, key=lambda r: (_fetch_ts(r), _snap_ts(r) or _fetch_ts(r)))
        fetched = _fetch_ts(sharp)
        newest = max((_fetch_ts(r) for r in rows
                      if r["book"] != REFERENCE_BOOK and _fetch_ts(r) is not None), default=fetched)
        if newest > fetched:
            diag["pinnacle_withdrawn"] += 1
            continue
        if oldest is not None and fetched < oldest:
            diag["stale_fetch"] += 1
            continue
        over = _overround(sharp, market)
        if over is None or not (coh[0] < over < coh[1]):
            diag["sharp_incoherent"] += 1
            continue
        fair = power_devig([sharp[c] for c in pcols])
        if fair is None:
            diag["sharp_incoherent"] += 1
            continue
        line = _line(sharp, market)
        same: dict = {}
        for r in rows:
            if r["book"] == SHARP_BOOK or r["created_at"] != sharp["created_at"]:
                continue
            prev = same.get(r["book"])
            if prev is None or (_snap_ts(r) or fetched) > (_snap_ts(prev) or fetched):
                same[r["book"]] = r
        if not any(b in same for b in soft):
            diag["no_pair"] += 1
            continue
        dk = same.get(REFERENCE_BOOK)
        if dk is not None and (_line(dk, market) != line
                               or not (coh[0] < (_overround(dk, market) or 0) < coh[1])):
            dk = None
        for bk in soft:
            q = same.get(bk)
            if q is None or _line(q, market) != line:
                continue
            o = _overround(q, market)
            if o is None or not (coh[0] < o < coh[1]):
                continue
            diag["compared"] += 1
            for i, side in enumerate(outs):
                price = float(q[pcols[i]])
                if price_floor is not None and price < price_floor:
                    diag["below_price_floor"] += 1
                    continue
                ev = config.expected_value(fair[i], price)
                if ev is None or ev < floor:
                    diag["below_ev_floor"] += 1
                    continue
                cand = Candidate(
                    game_id=gid, market=market, model_id=model_id, side=side, book=bk,
                    line=line, price=price, fair=float(fair[i]), ev=float(ev),
                    created_at=sharp["created_at"], link=q.get(lcols[i]),
                    dk_price=float(dk[pcols[i]]) if dk is not None else None,
                    dk_link=dk.get(lcols[i]) if dk is not None else None)
                # Strictly greater: on a tie the earlier market, book and side keep it.
                if gid not in best or cand.ev > best[gid].ev:
                    best[gid] = cand
    diag["candidates"] = len(best)
    return best, diag


def pick_of_the_night(candidates: dict, games: dict, night_has_bet: set,
                      games_with_bet: set) -> dict[str, Candidate]:
    """{night (ET game date): the one Candidate to bet}. A night that already
    has a family bet gets nothing; a game holding any NHL BET is skipped."""
    by_night: dict = defaultdict(list)
    for gid, c in candidates.items():
        night = (games.get(gid) or {}).get("game_date")
        if night is None or night in night_has_bet or gid in games_with_bet:
            continue
        by_night[night].append(c)
    return {n: max(cs, key=lambda c: (c.ev, -MODEL_IDS.index(c.model_id)))
            for n, cs in by_night.items()}
