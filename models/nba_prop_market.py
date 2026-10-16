"""
NBA player props: same-line UNDERS against Pinnacle. Model id `nba_prop_market`.

The one NBA model that cleared every pre-registered bar of the 2026-27 rebuild
(docs/nba_models_2026.md, section 4.3; mike 2026-10-15: "build new nba models,
remove any previous nba models"; "use what you've learned in this repo"). A
frozen rule with no trained artifact. The card that writes its picks is
scripts/nba_prop_market_card.py.

THE RULE, per game, on every refresh pass:
  1. Decide ONLY when the game's tip is 45 to 70 minutes away (DECISION_WINDOW_MIN).
     The edge was measured on one archived snapshot about an hour before
     each tip (median lead 54 minutes), and assists bet earlier than tip-60
     lost. Never earlier. The tip is the NBA's scheduled start
     (nba_schedule.commence_time, or games.commence_time when that is
     earlier): the odds feed rewrites games.commence_time, and it already
     reads 10 minutes later than the schedule on 35 of 1,206 season-2027 games.
  2. Read the game's NEWEST pre-tip prop fetch. One refresh pass stamps one
     `snapshot_at` on every row it stores, and each game is one event call,
     so the rows of a game sharing one `snapshot_at` were quoted together.
     Pinnacle must be in that newest fetch; if a newer fetch lacks it, the
     game is skipped this pass ("pinnacle_withdrawn"). A fetch from before
     the decision window is not used ("stale_fetch").
  3. Pinnacle's two-way quote must be coherent: implied over + implied under
     between 1.00 and 1.15 inclusive (the lab's `between`). Its proportional
     no-vig under is the probability.
  4. Price every bettable book IN THAT SAME FETCH at Pinnacle's EXACT line.
     The book's own two-way quote must be coherent too, its under at -200 or
     better, and its own clock (`book_last_update`, the feed's last_update for
     that market) no more than 10 minutes behind Pinnacle's in the fetch: the
     2023-26 archive stored no such clock, so a stale soft quote could not be
     ruled out there, and it is refused here. A quote with no clock is
     counted, not refused (the convention of data/live_quote_guard.py).
  5. EV = fair under x decimal - 1, through models.honest_ev.gate (the
     model's own probability; floor config.MODEL_OWN_EV_FLOOR = 0.00).
  6. One proposition per (player, market): the best EV among the books. One
     BET per game: the best EV among the game's propositions. A tie goes to
     the earlier book in SOFT_BOOKS (DraftKings first).
  The card then writes at most MAX_BETS_PER_NIGHT a night, first come.

UNDERS ONLY. Blind overs lose 7.3% and blind unders 2.2% across 505,932
propositions at the best bettable price -- the over-lean NFL, NHL and WNBA
showed too -- and every over rule failed.

THE FIVE MARKETS. Points, rebounds, assists, threes, points+rebounds+assists.
Double-double and triple-double are left out. That is a POST-HOC narrowing:
the pre-registered pooled rule passes with them in too (25,204 bets, +2.85%,
90% CI +1.75..+3.96) as it does without them (24,513 bets, +2.90%, positive
every season). They are dropped because each failed on its own and a Yes/No
market prices no under the way the counting markets do, not because the pooled
number needed it.

THE EVIDENCE (2023-24 to 2025-26, 1,230 games a season, one snapshot 60 min
before each tip, the best bettable price, units to win one):
    all three seasons            25,204 bets  +2.85%  90% CI +1.75..+3.96
    by season                    +4.1% / +2.2% / +2.1%  (2025-26 +0.34..+3.85)
    -200 floor, no DD / TD       24,572 bets  +2.96%  +1.85..+4.05, every season +
    one a game, four a night      1,862 bets  +5.05%  +1.35..+8.76, every season +
    neighbouring floors          +2.1% (EV -0.01), +3.1% (EV 0.01)
    placebo (Pinnacle shuffled)  mean -1.5%, 95th percentile -1.0%
    blind under, same props      -1.5%
It survives Bonferroni and Benjamini-Hochberg over the 1,518 cells searched.
Expect about +2% live: the top cell of a search carries winner's curse, and
2025-26, never used to choose anything, returned +2.1%. Hard Rock carries ~37%
of the units and is decaying (+16 / +8 / +3% by season); the rule clears
without it (+2.29%). Closing-line value could not be measured (one archived
snapshot a game), so the card stores a closing snapshot for every bet.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import config
from models.market_relative import implied

MODEL_ID = "nba_prop_market"
SPORT = "NBA"
SHARP_BOOK = "pinnacle"
# The book whose OWN price fills the dk_* columns (the scorer's convention).
REFERENCE_BOOK = "draftkings"
# Never a deciding price: Pinnacle is the reference, Bovada is not bettable for
# members. Excluded here explicitly as well as by config, so an env override of
# BEST_LINE_BOOKMAKERS cannot put either back.
NEVER_BET = ("pinnacle", "bovada")
SOFT_BOOKS: tuple[str, ...] = tuple(b for b in config.BEST_LINE_BOOKMAKERS
                                    if b not in NEVER_BET)

MARKETS: tuple[str, ...] = (
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",
)
# What the pick label calls each market (pick_label "<Name> Under <line> <label>").
MARKET_LABEL = {
    "player_points": "Pts",
    "player_rebounds": "Reb",
    "player_assists": "Ast",
    "player_threes": "3PM",
    "player_points_rebounds_assists": "PRA",
}
# What settles each market. Mirrors tracking.paper_tracker._NBA_MARKET_STAT,
# pinned by test: the selector and the settler hold one opinion of a market.
MARKET_STAT = {
    "player_points": "points",
    "player_rebounds": "rebounds",
    "player_assists": "assists",
    "player_threes": "fg3_made",
    "player_points_rebounds_assists": "COMPUTE_PRA",
}
SIDE = "under"

# Implied over + implied under, inclusive (scripts/nba_prop_market_lab.py
# COHERENT, used with pandas `between`).
COHERENT = (1.00, 1.15)

# Minutes before tip in which a game may be decided, both ends inclusive.
# docs/nba_models_2026.md 4.3: the archive's snapshot sat a median 54 minutes
# before tip, and assists bet before tip-60 lost. Not widened when a pass
# misses it: the card logs the miss instead (window_missed).
DECISION_WINDOW_MIN = (45, 70)

# A soft quote whose own clock is more than this far behind Pinnacle's in the
# same fetch is refused (mike's spec, 2026-10-15).
STALE_SOFT_MAX_MIN = 10

# ONE BET A GAME AND FOUR A NIGHT (the night is the game's ET date), first come
# in the order games reach their window. Measured on the shipped rule's own bet
# list (2023-24..2025-26, -200 floor, no double/triple-double; one a game = the
# best EV in the game's snapshot; four a night = first four games by tip):
#     every proposition       24,572 bets  +2.96%  90% CI +1.85..+4.05
#     one a game, 4 a night    1,862 bets  +5.05%  90% CI +1.35..+8.76
# both positive in every season. Live, the night is filled in tip order, then
# EV -- the backtest's order (scripts/nba_prop_market_card.per_night) -- and a
# later pass never replaces a bet.
MAX_BETS_PER_GAME = 1
MAX_BETS_PER_NIGHT = 4

DIAG_KEYS = (
    "games", "already_bet", "too_early", "in_window", "too_late", "window_missed",
    "no_sharp", "pinnacle_withdrawn", "stale_fetch", "pinnacle_present",
    "unresolved", "ambiguous", "duplicate_name",
    "sharp_incoherent", "no_pair", "line_mismatch", "soft_incoherent",
    "stale_rejected", "last_update_unknown", "below_price_floor",
    "below_ev_floor", "compared", "qualifying", "bets",
)


@dataclass(frozen=True)
class NbaPropBet:
    game_id: str
    game_date: str
    tip: str                   # the tip the window was measured against (ISO, UTC)
    player: str                # the BET book's own spelling (CLV reads its close by it)
    player_id: str
    market: str
    line: float
    book: str                  # the book the bet is taken at
    price: float               # that book's American price on the under
    fair: float                # Pinnacle's proportional no-vig under, same fetch
    ev: float                  # fair x decimal(price) - 1
    link: str | None
    sharp_over: float
    sharp_under: float
    fetch: str                 # the fetch's snapshot_at text
    soft_last_update: str | None
    sharp_last_update: str | None
    dk_price: float | None     # DraftKings' own under at this line in this fetch
    dk_link: str | None
    dk_player: str | None


# ── time ──────────────────────────────────────────────────────────────────────

def parse_ts(value) -> datetime | None:
    """Any stored timestamp (TEXT in 'Z', '+00:00' or '-04:00' shapes) -> aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def tip_of(schedule_ct, games_ct) -> datetime | None:
    """The earlier of the schedule's start and games.commence_time.

    The backtest's tip is the schedule's (they are identical for every
    2023-24..2025-26 game); the odds feed has since moved games.commence_time
    later on some 2026-27 games. The earlier one never lets a decision or a
    price read run past the real start.
    """
    a, b = parse_ts(schedule_ct), parse_ts(games_ct)
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def minutes_to_tip(tip: datetime, now: datetime) -> float:
    return (tip - now).total_seconds() / 60.0


def in_window(tip: datetime, now: datetime) -> bool:
    lo, hi = DECISION_WINDOW_MIN
    return lo <= minutes_to_tip(tip, now) <= hi


# ── names ─────────────────────────────────────────────────────────────────────

def name_key(name: str | None) -> str:
    """The results writer's normaliser, with initials joined.

    The ids come from nba_player_game_log, which the results writer fills, so
    the id taken here is the one a pick settles on. The key adds one step:
    runs of single letters are joined, because the books write "R.J. Barrett"
    where the log has "RJ Barrett", and the shared normaliser turns the first
    into "r j barrett" (measured 2026-10-16 on the opening-week prop rows).
    """
    from data.ingestors.wnba_results_ingestor import norm_player_name
    out: list[str] = []
    initials = ""
    for tok in norm_player_name(name or "").split():
        if len(tok) == 1:
            initials += tok
            continue
        if initials:
            out.append(initials)
            initials = ""
        out.append(tok)
    if initials:
        out.append(initials)
    return " ".join(out)


class Roster:
    """Normalised name -> NBA.com player id, per team, from nba_player_game_log.

    `rows` is (player_id, player_name, team) over this season and last. A name
    resolves only when exactly ONE player on the game's two teams carries it
    (bar 13: two players sharing a name never share a price -- the NHL
    namesake defect was +89.8u of phantom profit). The results writer may
    store a rookie as 'espn:<id>'; that id resolves like any other.
    """

    def __init__(self, rows):
        self._by_team: dict[tuple[str, str], set[str]] = defaultdict(set)
        for pid, name, team in rows or ():
            k = name_key(name)
            if pid is None or not k or not team:
                continue
            self._by_team[(str(team), k)].add(str(pid))

    def resolve(self, name: str, home: str, away: str) -> tuple[str | None, str]:
        """(player_id, "ok") or (None, "unresolved" | "ambiguous")."""
        k = name_key(name)
        ids = self._by_team.get((home, k), set()) | self._by_team.get((away, k), set())
        if len(ids) == 1:
            return next(iter(ids)), "ok"
        return None, ("unresolved" if not ids else "ambiguous")


# ── quotes ────────────────────────────────────────────────────────────────────

QUOTE_COLS = ("game_id", "player", "market", "book", "line", "over_price",
              "under_price", "over_link", "under_link", "snapshot_at",
              "book_last_update", "snapshot_type")


def load_quotes(conn, games: dict[str, dict], now: datetime,
                lookback_min: int = 5) -> list[dict]:
    """The pre-game prop rows find_bets needs for `games`, one statement.

    `snapshot_type = 'open'` only: the closing snapshot the card buys for CLV
    is filed 'close' and must never decide a bet. The text bound on
    snapshot_at is an IO prefilter, not the rule: live stamps have been UTC
    '+00:00' since 2026-10-09, so the lexical bound is chronological for every
    row it could matter for. It starts `lookback_min` before the earliest
    game's window opens: a fetch older than the window can neither decide a
    game (stale_fetch) nor show that a pass reached it (window_missed), and a
    game is fetched on every pass, so the read is a few fetches per game, not
    the days of fetches stored since its props were first posted. The exact
    bounds (snapshot_at <= now, < tip) are applied on PARSED times in find_bets.
    """
    if not games:
        return []
    earliest = min(g["tip"] for g in games.values())
    lower = (earliest - timedelta(minutes=DECISION_WINDOW_MIN[1] + lookback_min))
    books = sorted(set(SOFT_BOOKS) | {SHARP_BOOK, REFERENCE_BOOK})
    rows = conn.execute("""
        SELECT game_id, player_name, market, bookmaker, line, over_price,
               under_price, over_link, under_link, snapshot_at, book_last_update,
               snapshot_type
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND market = ANY(%s) AND bookmaker = ANY(%s)
          AND snapshot_type = 'open'
          AND snapshot_at >= %s
    """, (list(games), list(MARKETS), books,
          lower.astimezone(timezone.utc).isoformat())).fetchall()
    out = []
    for r in rows:
        q = dict(zip(QUOTE_COLS, r))
        for k in ("line", "over_price", "under_price"):
            if q[k] is not None:
                q[k] = float(q[k])              # NUMERIC arrives as Decimal
        out.append(q)
    return out


def coherent(q: dict) -> bool:
    o, u = implied(q.get("over_price")), implied(q.get("under_price"))
    if o is None or u is None:
        return False
    return COHERENT[0] <= o + u <= COHERENT[1]


def fair_under(q: dict) -> float:
    o, u = implied(q["over_price"]), implied(q["under_price"])
    return u / (o + u)


def _pre_tip(rows: list[dict], tip: datetime, now: datetime) -> list[dict]:
    out = []
    for r in rows:
        if r.get("snapshot_type", "open") != "open":
            continue                               # 'close' never decides
        t = parse_ts(r.get("snapshot_at"))
        if t is None or t > now or t >= tip:
            continue
        out.append(r)
    return out


def fetch_times(rows: list[dict]) -> list[datetime]:
    return sorted({t for t in (parse_ts(r.get("snapshot_at")) for r in rows) if t})


def window_was_fetched(rows: list[dict], tip: datetime) -> bool:
    """Did any pre-game fetch of this game land inside its decision window?

    The prop fetch runs on every refresh pass, so a game with no fetch inside
    the window had no pass that could decide it.
    """
    lo, hi = DECISION_WINDOW_MIN
    return any(lo <= minutes_to_tip(tip, t) <= hi for t in fetch_times(rows))


# ── the rule ──────────────────────────────────────────────────────────────────

def find_bets(quotes: list[dict], games: dict[str, dict], roster: Roster,
              now: datetime, taken: set[str] | None = None,
              soft_books: tuple[str, ...] | None = None
              ) -> tuple[list[NbaPropBet], dict]:
    """At most one bet a game. Pure, given its inputs.

    `games` is {game_id: {"home", "away", "tip": datetime, "game_date"}} for
    every unstarted game the card is looking at; the window is applied here.
    `taken` holds games that already carry an nba_prop_market BET: they are
    never re-decided.
    """
    from models.honest_ev import gate

    soft = tuple(soft_books) if soft_books is not None else SOFT_BOOKS
    soft = tuple(b for b in soft if b not in NEVER_BET)
    taken = taken or set()
    floor = config.min_odds_for(MODEL_ID)
    stale_after = timedelta(minutes=STALE_SOFT_MAX_MIN)
    diag = dict.fromkeys(DIAG_KEYS, 0)

    by_game: dict[str, list[dict]] = defaultdict(list)
    for q in quotes:
        by_game[q["game_id"]].append(q)

    bets: list[NbaPropBet] = []
    for gid in sorted(games):
        g = games[gid]
        tip = g["tip"]
        if tip is None or tip <= now:
            continue
        diag["games"] += 1
        lead = minutes_to_tip(tip, now)
        rows = _pre_tip(by_game.get(gid, []), tip, now)
        if lead > DECISION_WINDOW_MIN[1]:
            diag["too_early"] += 1
            continue
        if gid in taken:
            diag["already_bet"] += 1
            continue
        if lead < DECISION_WINDOW_MIN[0]:
            diag["too_late"] += 1
            if not window_was_fetched(rows, tip):
                diag["window_missed"] += 1
            continue
        diag["in_window"] += 1

        rows = [r for r in rows if r.get("market") in MARKETS]
        pins = [r for r in rows if r.get("book") == SHARP_BOOK]
        if not pins:
            diag["no_sharp"] += 1
            continue
        pin_fetch = max(parse_ts(r["snapshot_at"]) for r in pins)
        newest = max(parse_ts(r["snapshot_at"]) for r in rows)
        if newest > pin_fetch:
            diag["pinnacle_withdrawn"] += 1
            continue
        if minutes_to_tip(tip, pin_fetch) > DECISION_WINDOW_MIN[1]:
            diag["stale_fetch"] += 1             # the newest price predates the window
            continue
        diag["pinnacle_present"] += 1
        fetch = [r for r in rows if parse_ts(r["snapshot_at"]) == pin_fetch]

        # Every row's player, by id. A name the roster cannot place on one
        # player is skipped, at every book.
        keyed: dict[tuple[str, str], dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
        seen_names: dict[str, str] = {}
        for r in fetch:
            name = r.get("player") or ""
            if name not in seen_names:
                pid, why = roster.resolve(name, g["home"], g["away"])
                seen_names[name] = pid or why
                if pid is None:
                    diag[why] += 1
            pid = seen_names[name]
            if pid in ("unresolved", "ambiguous"):
                continue
            keyed[(pid, r["market"])][r["book"]].append(r)

        best_in_game: NbaPropBet | None = None
        for (pid, market), by_book in sorted(keyed.items()):
            sharp_rows = by_book.get(SHARP_BOOK, [])
            if not sharp_rows:
                continue                          # no Pinnacle price for this prop
            if any(len(v) > 1 for v in by_book.values()):
                # Two spellings at one book mapped to one player: which row is
                # the price is unknowable, so the proposition is skipped.
                diag["duplicate_name"] += 1
                continue
            sharp = sharp_rows[0]
            if sharp.get("line") is None or not coherent(sharp):
                diag["sharp_incoherent"] += 1
                continue
            line = float(sharp["line"])
            fair = fair_under(sharp)
            pin_lu = parse_ts(sharp.get("book_last_update"))

            dk = None
            dk_rows = by_book.get(REFERENCE_BOOK, [])
            if dk_rows and dk_rows[0].get("line") is not None \
                    and float(dk_rows[0]["line"]) == line and coherent(dk_rows[0]) \
                    and dk_rows[0].get("under_price") is not None:
                dk = dk_rows[0]

            if not any(b in by_book for b in soft):
                diag["no_pair"] += 1
                continue
            best: NbaPropBet | None = None
            for book in soft:
                rs = by_book.get(book)
                if not rs:
                    continue
                q = rs[0]
                if q.get("line") is None or float(q["line"]) != line:
                    diag["line_mismatch"] += 1
                    continue
                if not coherent(q):
                    diag["soft_incoherent"] += 1
                    continue
                soft_lu = parse_ts(q.get("book_last_update"))
                if soft_lu is None or pin_lu is None:
                    diag["last_update_unknown"] += 1
                elif soft_lu < pin_lu - stale_after:
                    diag["stale_rejected"] += 1
                    continue
                diag["compared"] += 1
                price = float(q["under_price"])
                if price < floor:
                    diag["below_price_floor"] += 1
                    continue
                ev = gate(MODEL_ID, fair, price)
                if ev.ev is None or not ev.clears:
                    diag["below_ev_floor"] += 1
                    continue
                diag["qualifying"] += 1
                cand = NbaPropBet(
                    game_id=gid, game_date=g["game_date"], tip=tip.isoformat(),
                    player=q["player"], player_id=pid, market=market, line=line,
                    book=book, price=price, fair=float(fair), ev=float(ev.ev),
                    link=q.get("under_link"),
                    sharp_over=float(sharp["over_price"]),
                    sharp_under=float(sharp["under_price"]),
                    fetch=str(sharp["snapshot_at"]),
                    soft_last_update=q.get("book_last_update"),
                    sharp_last_update=sharp.get("book_last_update"),
                    dk_price=float(dk["under_price"]) if dk is not None else None,
                    dk_link=dk.get("under_link") if dk is not None else None,
                    dk_player=dk.get("player") if dk is not None else None,
                )
                # Strictly greater: a tie keeps the earlier book (DraftKings first).
                if best is None or cand.ev > best.ev:
                    best = cand
            if best is not None and (best_in_game is None or best.ev > best_in_game.ev):
                best_in_game = best
        if best_in_game is not None:
            bets.append(best_in_game)
            diag["bets"] += 1
    return bets, diag
