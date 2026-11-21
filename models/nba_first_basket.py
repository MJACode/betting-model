"""NBA first basket (nba_first_basket): who scores the game's first points, priced from the opening
tip and each starter's share of his team's first score, blended with the other books' price.

mike, 2026-11-20, after an 0-6 NBA night: "invent a new way to make this profitable". No NBA search
here had priced the market (docs/nba_first_basket.md). It went live on his "yes" the same day, after
the grade below, knowing it passed five of the six house bars and failed the sixth.

THE RULE IS TEST 2b, AS GRADED (data/local/research/nba_research/first_basket/prereg.md):
  - the model's probability that a starter scores the game's first points: P(his team scores first)
    x his share of his team's first scores. P(team first) = c x P(win tip) + (1 - c) x P(lose tip),
    c the running league rate the tip winner scores first; P(win tip) by log5 of the two jumpers'
    opening-tip win rates, each shrunk toward 0.5 (A_TIP). His share: his team-first scores over his
    starts, shrunk toward his points share among the five starters (K_SHARE), the five normalised,
    less the bench's running share. Every count decays by DECAY a season. Learned from games on
    earlier dates only.
  - the books' price: each deciding book's no-vig over every name it lists for the game; for each
    (starter, book), the MEDIAN of that starter's no-vig at the OTHER deciding books, three or more.
  - p = W_MODEL x model + (1 - W_MODEL) x that median. EV = p x decimal - 1 at that book's price.
  - one bet a game: the highest-EV (starter, book), if its EV clears config.min_ev_for (0.05).
Graded on 2024-25..2026-27 at the bought snapshot 10 minutes before tip: 1,930 bets, +14.56 units,
+7.45% (95% interval -5.00% to +20.85%); 2024-25 +8.51%, 2025-26 +7.86%; floors 0.00 / 0.10 +6.02% /
+12.43%; days 0-44 +1.31%, day 45+ +10.52%; log loss 0.32317 vs the books' median 0.32326. It fails
only the interval bar. W_MODEL was fitted on 2023-24 alone.

THE STARTERS are what the books list at the decision fetch (assign_starters): the names at least
MIN_LISTING_BOOKS deciding books list, placed on the team whose history has them; a side listing six
keeps the five the most books list; a name neither team's history has fills the one side short of
five; a side still at four takes its name the fewest books list, else a stand-in with no history; a
side at three or fewer is declined. The grade used the box's starters, which the books list once
lineups post (about 30 minutes before tip). Replayed on the bought snapshots this rule made 1,862 bets
against the grade's 1,930, 1,690 of them identical (first_basket/fidelity_join.parquet).

WHAT SETTLES IT: each book's own rule (first_basket_outcome): the first made field goal at DraftKings,
BetMGM, Fanatics and BetRivers; the first points of any kind, free throws included, at FanDuel, Caesars
and Hard Rock. A player who does not start settles NO_ACTION (tracking/paper_tracker). The model was
fitted on the first points of any kind; re-graded on each book's own rule the same bets made +9.67%.

THE MARKET MAY GO. AP and Front Office Sports reported on 2026-10-16 that the NBA asked its partner
books to stop offering single-player "first-of" bets. On 2026-11-20 nine books still quoted it and the
2026-27 history holds it on 226 games; a book that withdraws it simply stops quoting, and a starter
quoted by fewer than four deciding books cannot be bet (the bet book and three others).
"""
from __future__ import annotations

import re
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

import numpy as np
import pandas as pd

import config

MODEL_ID = "nba_prop_first_basket"
SPORT = "NBA"
MARKET = "player_first_basket"
SIDE = "over"                     # Yes, stored as Over 0.5 like the other Yes-only props
LINE = 0.5
LABEL = "First Basket"
REFERENCE_BOOK = "draftkings"
# The seven books the rule was graded at. A pick may only name one that config also lets a pick
# name (deciding_books); betPARX and Bovada are fetched but were never in the grade.
GRADED_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "hardrockbet",
                "betrivers")
W_MODEL = 0.25
MIN_OTHER_BOOKS = 3
MIN_LISTING_BOOKS = 3
A_TIP, K_SHARE, DECAY = 2.0, 40.0, 0.5
C_TIP_PRIOR, C_TIP_PRIOR_N = 0.64, 50.0
BENCH_PRIOR = (2.0, 100.0)        # pseudo (bench first scores, team first scores)
PPG_PRIOR = (10.0, 1.0)           # pseudo (points, games)
TEAM_JUMPS_KEPT = 15
DECISION_WINDOW_MIN = (5, 20)     # minutes before tip


def deciding_books() -> tuple[str, ...]:
    allowed = set(config.BEST_LINE_BOOKMAKERS)
    return tuple(b for b in GRADED_BOOKS if b in allowed)


def name_norm(name: str | None) -> str:
    """The grade's name key (fb_price.norm): ASCII, lower case, letters and spaces, no suffix."""
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    n = re.sub(r"[^a-z ]", "", n)
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", n)
    return " ".join(n.split())


def american_to_decimal(a: float) -> float:
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def log5(a: float, b: float) -> float:
    return a * (1 - b) / (a * (1 - b) + b * (1 - a))


# ── the model's state ─────────────────────────────────────────────────────────

def _recent_jumps() -> deque:
    return deque(maxlen=TEAM_JUMPS_KEPT)


class State:
    """Everything the price knows, learned one game date at a time from earlier games only.

    `games`: one row per game -- game_id, season, game_date, tip_side ('H'/'A'/None), j1, j2 (the two
    jumpers' ids), fs_side, fs_id (who scored the game's first points). `box`: one row per player-game
    he played -- game_id, espn_id, side, team, name, starter, pts. The same shapes as the research
    model (fb_model.build), so the two can be checked against each other.
    """

    def __init__(self, box: pd.DataFrame):
        self.side_of: dict = {}
        self.starters: dict = defaultdict(list)
        for r in box.itertuples(index=False):
            self.side_of[(r.game_id, r.espn_id)] = r.side
            if r.starter:
                self.starters[(r.game_id, r.side)].append(r.espn_id)
        self.team_of = {(r.game_id, r.side): r.team
                        for r in box.drop_duplicates(["game_id", "side"]).itertuples()}
        self.box_by_game = {g: t for g, t in box.groupby("game_id")}
        self.jw, self.jn = defaultdict(float), defaultdict(float)
        self.team_jumps = defaultdict(_recent_jumps)
        self.fs_w, self.st_n = defaultdict(float), defaultdict(float)
        self.ppg_s, self.ppg_n = defaultdict(float), defaultdict(float)
        self.lg, self.bench = [0.0, 0.0], [0.0, 0.0]
        self.season = None

    def new_season(self, s: int) -> None:
        if s == self.season:
            return
        for dct in (self.jw, self.jn, self.fs_w, self.st_n, self.ppg_s, self.ppg_n):
            for k in dct:
                dct[k] *= DECAY
        self.lg = [x * DECAY for x in self.lg]
        self.bench = [x * DECAY for x in self.bench]
        self.season = s

    def jumper(self, team: str, sts: list) -> object:
        recent = list(self.team_jumps[team])
        cand = sorted(((recent.count(pid), pid) for pid in sts), reverse=True)
        return cand[0][1] if cand[0][0] > 0 else max(sts, key=lambda x: self.jn[x])

    def price(self, sts_h: list, sts_a: list, team_h: str, team_a: str) -> dict:
        """{espn_id: P(he scores the game's first points)} for the ten starters, plus the parts."""
        c_tip = (self.lg[0] + C_TIP_PRIOR_N * C_TIP_PRIOR) / (self.lg[1] + C_TIP_PRIOR_N)
        b_sh = (self.bench[0] + BENCH_PRIOR[0]) / (self.bench[1] + BENCH_PRIOR[1])
        jh, ja = self.jumper(team_h, sts_h), self.jumper(team_a, sts_a)
        rh = (self.jw[jh] + A_TIP) / (self.jn[jh] + 2 * A_TIP)
        ra = (self.jw[ja] + A_TIP) / (self.jn[ja] + 2 * A_TIP)
        p_tip_h = log5(rh, ra)
        pf = {"H": c_tip * p_tip_h + (1 - c_tip) * (1 - p_tip_h)}
        pf["A"] = 1 - pf["H"]
        out: dict = {"p_tip_h": p_tip_h, "p_first": pf, "p": {}, "share": {}}
        for sd, sts in (("H", sts_h), ("A", sts_a)):
            ppg = np.array([(self.ppg_s[x] + PPG_PRIOR[0]) / (self.ppg_n[x] + PPG_PRIOR[1]) for x in sts])
            prior = ppg / ppg.sum()
            raw = np.array([(self.fs_w[x] + K_SHARE * pr) / (self.st_n[x] + K_SHARE)
                            for x, pr in zip(sts, prior)])
            share = raw / raw.sum() * (1 - b_sh)
            for pid, sh in zip(sts, share):
                out["share"][pid] = float(sh)
                out["p"][pid] = float(pf[sd] * sh)
        return out

    def learn(self, day: pd.DataFrame) -> None:
        for g in day.itertuples(index=False):
            if isinstance(g.tip_side, str):
                self.lg[1] += 1
                self.lg[0] += int(g.fs_side == g.tip_side)
                for j in (g.j1, g.j2):
                    if j is None or (isinstance(j, float) and np.isnan(j)):
                        continue
                    sd = self.side_of.get((g.game_id, j))
                    if sd is None:
                        continue
                    self.jn[j] += 1
                    self.jw[j] += int(sd == g.tip_side)
                    self.team_jumps[self.team_of.get((g.game_id, sd))].append(j)
            for sd in ("H", "A"):
                sts = self.starters.get((g.game_id, sd), [])
                for pid in sts:
                    self.st_n[pid] += 1
                if g.fs_side == sd:
                    self.bench[1] += 1
                    if g.fs_id in sts:
                        self.fs_w[g.fs_id] += 1
                    else:
                        self.bench[0] += 1
            b = self.box_by_game.get(g.game_id)
            if b is not None:
                for r in b.itertuples(index=False):
                    self.ppg_s[r.espn_id] += r.pts
                    self.ppg_n[r.espn_id] += 1


def state_before(games: pd.DataFrame, box: pd.DataFrame, game_date: str) -> State:
    """The state learned from every game dated strictly before `game_date`."""
    st = State(box)
    for d, day in games[games.game_date < game_date].groupby("game_date", sort=True):
        st.new_season(int(day.season.iloc[0]))
        st.learn(day)
    return st


@dataclass
class Prepared:
    """What a decision on `game_date` needs, built once a day: the state learned from every game
    before that date (its box lookups dropped, so it pickles small) and who each name is."""
    game_date: str
    state: State
    latest: dict          # espn_id -> (team, normalised name) of his latest box row
    anywhere: dict        # normalised name -> espn_id, for a name one player alone carries
    history_through: str  # the newest game date it learned from


def prepare(games: pd.DataFrame, box: pd.DataFrame, game_date: str) -> Prepared:
    st = state_before(games, box, game_date)
    st.side_of, st.starters, st.team_of, st.box_by_game = {}, {}, {}, {}
    before = games[games.game_date < game_date]
    b = box[box.game_id.isin(set(before.game_id))][["game_id", "espn_id", "team", "name"]].copy()
    b["nm"] = b.name.map(name_norm)
    last = b.sort_values("game_id").drop_duplicates("espn_id", keep="last")
    latest = {int(r.espn_id): (r.team, r.nm) for r in last.itertuples(index=False)}
    ids = b.drop_duplicates(["nm", "espn_id"]).groupby("nm").espn_id.apply(list)
    anywhere = {nm: int(v[0]) for nm, v in ids.items() if len(v) == 1}
    return Prepared(game_date, st, latest, anywhere,
                    str(before.game_date.max()) if len(before) else "")


def names_for(prep: Prepared, teams: tuple[str, str]) -> "Names":
    out, seen = {}, defaultdict(set)
    for pid, (team, nm) in prep.latest.items():
        if team in teams:
            seen[nm].add(pid)
            out[(team, nm)] = pid
    return Names({k: v for k, v in out.items() if len(seen[k[1]]) == 1}, prep.anywhere)


# ── history from the database ────────────────────────────────────────────────

def load_history(conn) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(games, box) in State's shapes from nba_first_basket_games / _players (data/ingestors/
    nba_first_basket.py, every regular season stored) and the points in nba_player_game_log,
    joined by name within the game (the log's ids are NBA.com's, the first-basket tables ESPN's)."""
    g = pd.DataFrame(conn.execute(
        "SELECT game_id, season, game_date, team, is_home, won_tip, jumper_espn_id, scored_first, "
        "first_score_espn_id FROM nba_first_basket_games").fetchall(),
        columns=["game_id", "season", "game_date", "team", "is_home", "won_tip", "jumper",
                 "scored_first", "first_score"])
    p = pd.DataFrame(conn.execute(
        "SELECT game_id, espn_id, team, name, starter FROM nba_first_basket_players").fetchall(),
        columns=["game_id", "espn_id", "team", "name", "starter"])
    pts = pd.DataFrame(conn.execute(
        "SELECT l.game_id, l.player_name, l.points FROM nba_player_game_log l "
        "WHERE l.game_id IN (SELECT DISTINCT game_id FROM nba_first_basket_games)").fetchall(),
        columns=["game_id", "player_name", "points"])
    return history_frames(g, p, pts)


def history_frames(g: pd.DataFrame, p: pd.DataFrame, pts: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """The pure half of load_history: stored rows -> (games, box)."""
    g = g.copy()
    g["side"] = np.where(g.is_home.astype(bool), "H", "A")
    rows = []
    for gid, t in g.groupby("game_id"):
        h, a = t[t.side == "H"], t[t.side == "A"]
        if h.empty or a.empty:
            continue
        h, a = h.iloc[0], a.iloc[0]
        tip = None
        if h.won_tip is not None and not pd.isna(h.won_tip):
            tip = "H" if bool(h.won_tip) else "A"
        first = h if bool(h.scored_first) else a if bool(a.scored_first) else None
        rows.append({"game_id": gid, "season": int(h.season), "game_date": str(h.game_date)[:10],
                     "tip_side": tip,
                     "j1": _id(h.jumper), "j2": _id(a.jumper),
                     "fs_side": None if first is None else first.side,
                     "fs_id": None if first is None else _id(first.first_score)})
    games = pd.DataFrame(rows).sort_values(["game_date", "game_id"]).reset_index(drop=True)
    side_by_team = {(r.game_id, r.team): r.side for r in g.itertuples()}
    box = p.copy()
    box["espn_id"] = box.espn_id.map(_id)
    box["side"] = [side_by_team.get((gid, tm)) for gid, tm in zip(box.game_id, box.team)]
    box = box[box.side.notna()]
    box["starter"] = box.starter.fillna(False).astype(bool)
    box["nm"] = box.name.map(name_norm)
    pts = pts.assign(nm=pts.player_name.map(name_norm)).drop_duplicates(["game_id", "nm"])
    box = box.merge(pts[["game_id", "nm", "points"]], on=["game_id", "nm"], how="left")
    box["pts"] = pd.to_numeric(box.points, errors="coerce").fillna(0.0).astype(float)
    return games, box[["game_id", "espn_id", "side", "team", "name", "starter", "pts"]]


def _id(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class Names:
    """Who a listed name is. `by_team`: {(team, name): espn_id} for each player whose LATEST box row
    was for that team, one id per name across the two teams; `anywhere`: {name: espn_id} for a name
    only one player in the whole history carries."""

    def __init__(self, by_team: dict, anywhere: dict):
        self.by_team, self.anywhere = by_team, anywhere

    def on(self, team: str, nm: str):
        return self.by_team.get((team, nm))


def name_map(box: pd.DataFrame, teams: tuple[str, str]) -> Names:
    """Names for the two teams from every box row stored (load_history's box)."""
    b = box[["game_id", "espn_id", "team", "name"]].copy()
    b["nm"] = b.name.map(name_norm)
    ids_by_name = b.drop_duplicates(["nm", "espn_id"]).groupby("nm").espn_id.apply(list)
    anywhere = {nm: ids[0] for nm, ids in ids_by_name.items() if len(ids) == 1}
    last = b.sort_values("game_id").drop_duplicates("espn_id", keep="last")
    last = last[last.team.isin(teams)]
    out, seen = {}, defaultdict(set)
    for r in last.itertuples(index=False):
        seen[r.nm].add(r.espn_id)
        out[(r.team, r.nm)] = r.espn_id
    return Names({k: v for k, v in out.items() if len(seen[k[1]]) == 1}, anywhere)


def new_player_id(nm: str) -> int:
    """A stable stand-in id for a listed starter the history has never seen (a rookie's first start):
    negative, so it can never be an ESPN id, and the state knows nothing about it -- which is how the
    grade priced such a player."""
    import zlib
    return -int(zlib.crc32(nm.encode()) or 1)


def assign_starters(listed: dict[str, list[str]], game: dict, names: Names,
                    thin: dict[str, list[str]] | None = None
                    ) -> tuple[dict[str, list[tuple[str, int]]], str | None]:
    """The five starters a side from the names MIN_LISTING_BOOKS books list. A name on a team's
    history goes to that team. A side listing six or more keeps the five the most books list. A name
    on neither team's history goes to the one side short of five when exactly one is, as the player
    the history has for that name anywhere, else as a new player. -> (sides, None) or ({}, why)."""
    sides: dict[str, list[tuple[str, int, int]]] = {"H": [], "A": []}
    loose = []
    for nm, books in listed.items():
        placed = False
        for team, sd in ((game["home"], "H"), (game["away"], "A")):
            pid = names.on(team, nm)
            if pid is not None:
                sides[sd].append((nm, pid, len(books)))
                placed = True
                break
        if not placed:
            loose.append((nm, len(books)))
    for sd in ("H", "A"):
        if len(sides[sd]) > 5:
            sides[sd] = sorted(sides[sd], key=lambda x: (-x[2], x[0]))[:5]
    short = [sd for sd in ("H", "A") if len(sides[sd]) < 5]
    if len(short) == 1 and len(loose) == 5 - len(sides[short[0]]):
        sd = short[0]
        for nm, n in loose:
            sides[sd].append((nm, names.anywhere.get(nm, new_player_id(nm)), n))
    # A side one short: the fifth is a starter fewer than MIN_LISTING_BOOKS books list. Take the
    # team's name that the most of the other books list; else a stand-in with no history. He is in
    # the five only to share out the team's probability: with no price at three books he is never bet.
    for team, sd in ((game["home"], "H"), (game["away"], "A")):
        if len(sides[sd]) != 4:
            continue
        have = {nm for nm, _, _ in sides[sd]}
        cands = sorted(((len(b), nm) for nm, b in (thin or {}).items()
                        if nm not in have and names.on(team, nm) is not None), reverse=True)
        if cands:
            nm = cands[0][1]
            sides[sd].append((nm, names.on(team, nm), cands[0][0]))
        else:
            sides[sd].append((f"(unlisted {team})", new_player_id(f"unlisted {team}"), 0))
    if len(sides["H"]) != 5 or len(sides["A"]) != 5:
        return {}, f"starters_listed home={len(sides['H'])} away={len(sides['A'])} unplaced={len(loose)}"
    return {sd: [(nm, pid) for nm, pid, _ in v] for sd, v in sides.items()}, None


# ── the decision ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class FirstBasketBet:
    game_id: str
    game_date: str
    tip: datetime
    player: str           # the bet book's own spelling
    espn_id: int
    team: str
    book: str
    price: float
    p_model: float
    p_market: float       # the other books' median no-vig
    prob: float           # the blend: the number the bet is decided on
    ev: float
    dk_price: float | None
    n_books: int
    fetch: str
    link: str | None = None        # the bet book's deep link, when the feed sent one
    dk_link: str | None = None


def listings(quotes: list[dict], books: tuple[str, ...]) -> dict[str, list[str]]:
    """{normalised name: [books listing him]} over every listed name."""
    by = defaultdict(set)
    for q in quotes:
        if q["book"] in books and q.get("price") is not None:
            by[name_norm(q["player"])].add(q["book"])
    return {n: sorted(b) for n, b in by.items()}


def starters_from_listings(quotes: list[dict], books: tuple[str, ...]) -> dict[str, list[str]]:
    """{normalised name: [books listing him]} for the names listed by MIN_LISTING_BOOKS or more."""
    return {n: b for n, b in listings(quotes, books).items() if len(b) >= MIN_LISTING_BOOKS}


def decide(game: dict, quotes: list[dict], st: State, names: "Names", books: tuple[str, ...] | None = None
           ) -> tuple[FirstBasketBet | None, str]:
    """One game's decision. `quotes`: this game's rows at ONE fetch, each {book, player, price,
    fetch}; `names`: name_map for the two teams. -> (the bet or None, why)."""
    books = books or deciding_books()
    qs = [q for q in quotes if q["book"] in books and q.get("price") is not None]
    if not qs:
        return None, "no_quotes"
    every = listings(qs, books)
    listed = {n: b for n, b in every.items() if len(b) >= MIN_LISTING_BOOKS}
    thin = {n: b for n, b in every.items() if len(b) < MIN_LISTING_BOOKS}
    sides, why = assign_starters(listed, game, names, thin)
    if why:
        return None, why
    pr = st.price([p for _, p in sides["H"]], [p for _, p in sides["A"]], game["home"], game["away"])
    pid_of = {nm: pid for sd in sides.values() for nm, pid in sd}
    team_of = {nm: (game["home"] if any(nm == x for x, _ in sides["H"]) else game["away"])
               for nm in pid_of}
    # each book's no-vig over every name it lists for the game
    imp = defaultdict(dict)
    price = defaultdict(dict)
    spelled = {}
    links = {}
    for q in qs:
        nm = name_norm(q["player"])
        price[q["book"]][nm] = float(q["price"])
        imp[q["book"]][nm] = 1 / american_to_decimal(q["price"])
        spelled[(q["book"], nm)] = q["player"]
        links[(q["book"], nm)] = q.get("link")
    novig = {b: {nm: v / sum(d.values()) for nm, v in d.items()} for b, d in imp.items()}
    best = None
    for nm, pid in pid_of.items():
        quoted = [b for b in novig if nm in novig[b]]
        for b in quoted:
            others = [novig[o][nm] for o in quoted if o != b]
            if len(others) < MIN_OTHER_BOOKS:
                continue
            p_mkt = float(median(others))
            p = W_MODEL * pr["p"][pid] + (1 - W_MODEL) * p_mkt
            ev = p * american_to_decimal(price[b][nm]) - 1
            if best is None or ev > best[0]:
                best = (ev, nm, pid, b, p, p_mkt, len(quoted))
    if best is None:
        return None, "no_reference"
    ev, nm, pid, b, p, p_mkt, n_books = best
    from models.honest_ev import gate
    g = gate(MODEL_ID, p, price[b][nm])
    if not g.clears:
        return None, f"best_ev {ev:.4f} below floor {g.floor:.2f}"
    dk = price.get(REFERENCE_BOOK, {}).get(nm)
    bet = FirstBasketBet(
        game_id=game["game_id"], game_date=game["game_date"], tip=game["tip"],
        player=spelled[(b, nm)], espn_id=int(pid), team=team_of[nm], book=b, price=price[b][nm],
        p_model=pr["p"][pid], p_market=p_mkt, prob=p, ev=ev, dk_price=dk, n_books=n_books,
        fetch=qs[0].get("fetch") or "", link=links.get((b, nm)),
        dk_link=links.get((REFERENCE_BOOK, nm)))
    return bet, f"bet ev={ev:.4f}"


def in_window(tip: datetime, now: datetime) -> bool:
    lead = (tip - now).total_seconds() / 60.0
    return DECISION_WINDOW_MIN[0] <= lead <= DECISION_WINDOW_MIN[1]


# ── settlement ────────────────────────────────────────────────────────────────
# Each book's own rule (house rules read 2026-11-20; data/local/research/nba_research/first_basket/
# book_rules.md). BetRivers' is from a secondary source only. Hard Rock's says "first point is scored";
# it does not name free throws outright. The PRICE does not split by these: the graded rule priced every
# book's quote as the game's first points of any kind, and re-graded on each book's own rule test 2b
# made 1,930 bets, +18.91 units, +9.67% (-3.17..+23.02).
FIELD_GOAL_BOOKS = frozenset({"draftkings", "betmgm", "fanatics", "betrivers"})
ANY_SCORE_BOOKS = frozenset({"fanduel", "williamhill_us", "hardrockbet"})


def first_basket_outcome(book: str | None, starter: bool | None, espn_id, first_any, first_fg) -> int | None:
    """The settled value of a first-basket Yes at `book` for one player-game: 1 he scored what that
    book pays on (the first made field goal at FIELD_GOAL_BOOKS, the first points of any kind, free
    throws included, everywhere else), 0 he did not, None = no action. Every bet is on a listed starter
    and every deciding book but BetMGM voids a player who does not start (BetMGM voids only one who does
    not play or comes on after the first field goal), so a non-starter is no action at every book.
    The one place the definition lives."""
    if starter is None or not bool(starter):
        return None
    first = first_fg if book in FIELD_GOAL_BOOKS else first_any
    if first is None:
        return None
    return int(int(first) == int(espn_id))


def settle_facts(conn, game_ids: list[str]) -> dict[str, dict]:
    """{game_id: {"first_any", "first_fg", "starters": {name: espn_id}, "played": {name: espn_id}}}
    from the play-by-play (period 1, through nba_pbp's primary key) and its box, for the games whose
    play-by-play holds both a first score and a first made field goal. A game missing either is left
    out, so its picks wait for the next pass rather than settle on half a record."""
    if not game_ids:
        return {}
    gmap = dict(conn.execute(
        "SELECT espn_game_id, game_id FROM nba_pbp_games WHERE game_id = ANY(%s) AND season_type = 2",
        (list(game_ids),)).fetchall())
    if not gmap:
        return {}
    plays = conn.execute(
        "SELECT espn_game_id, play_no, athlete_id_1, type_text, shooting_play, team_side FROM nba_pbp "
        "WHERE espn_game_id = ANY(%s) AND period = 1 AND points > 0 ORDER BY espn_game_id, play_no",
        (list(gmap),)).fetchall()
    box = conn.execute(
        "SELECT espn_game_id, espn_id, name, starter FROM nba_pbp_box WHERE espn_game_id = ANY(%s) "
        "AND COALESCE(did_not_play, FALSE) = FALSE AND side IN ('H', 'A')", (list(gmap),)).fetchall()
    return facts_from_rows(gmap, plays, box)


def facts_from_rows(gmap: dict, plays, box) -> dict[str, dict]:
    """The pure half of settle_facts."""
    first_any, first_fg = {}, {}
    for eg, _no, ath, typ, shooting, side in plays:
        if side not in ("H", "A") or ath is None:
            continue
        first_any.setdefault(eg, ath)
        if shooting and not str(typ or "").lower().startswith("free throw"):
            first_fg.setdefault(eg, ath)
    out = {}
    for eg, gid in gmap.items():
        if eg not in first_any or eg not in first_fg:
            continue
        out[gid] = {"first_any": int(first_any[eg]), "first_fg": int(first_fg[eg]),
                    "starters": {}, "played": {}}
    for eg, pid, name, starter in box:
        gid = gmap.get(eg)
        if gid not in out:
            continue
        nm = name_norm(name)
        out[gid]["played"][nm] = int(pid)
        if starter:
            out[gid]["starters"][nm] = int(pid)
    return out
