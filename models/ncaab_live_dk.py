"""The NCAAB in-play loop's DraftKings quotes and state, from DraftKings' own
board (written every few seconds by data/ingestors/dk_live_board.py on mike's
machine into dk_live_reads / dk_live_feed).

THE SAME RULE AS THE GRADE, ON A FASTER SOURCE (models/ncaab_live_ig.py, "THE
DECISION"):
  STAMP   a quote's stamp is the read where DraftKings FIRST showed that
          number and price (the provider's last_update meant the same).
  STATE   at the stamp: DraftKings' own score, period and clock in that read
          (DraftKings showed a basket a median 3.7 s after it, ESPN's
          scoreboard 20 s, its play-by-play 42 s; 2026-11-12). Team fouls,
          which DraftKings does not carry, from ESPN's newest summary at or
          before the stamp (ESPN runs ~40 s behind, so a foul in the last
          minute before the stamp can be missing from the bonus terms).
  FRESH   no point scored between the stamp and the read the loop decides on:
          a basket DraftKings' line has not yet repriced is not eligible
          (41 of 180 baskets, DraftKings moved the line a read or more after
          its score).
  HELD    the quote must have been seen on a later read too (the feed's last
          read is after the stamp): in 3 of 180 baskets DraftKings' line moved
          before its own score did, and a second read is what catches most
          of those. It costs one read (2.5 s).
Pure functions here; the loop reads the tables and supplies `now`.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SPORT = "NCAAB"
BOOK = "draftkings"
# The feed's last read must be this recent for its rows to be trusted.
FEED_MAX_AGE_SEC = 8.0
LOOKBACK_MIN = 60
SPREAD_KEY = ("spread_home", "spread_home_price", "spread_away_price")
TOTAL_KEY = ("total_line", "over_price", "under_price")
ML_KEY = ("home_ml", "away_ml")
QS_COLS = ["game_id", "market", "book", "stamp", "fetch_at", "home_price", "away_price", "spread_home",
           "total_line", "over_price", "under_price", "period", "clock_s", "game_s", "type_text", "h_pts",
           "a_pts", "h_tf", "a_tf", "h_fetch", "a_fetch", "pts_since", "held"]


def feed_last_read(conn, sport: str = SPORT):
    """(last_read_at, ok) of the feed, or None when it has never written."""
    from data.db import release_read
    try:
        row = conn.execute("SELECT last_read_at, ok FROM dk_live_feed WHERE sport = %s", (sport,)).fetchone()
    finally:
        release_read(conn)
    if not row:
        return None
    ts = pd.Timestamp(row[0])
    return (ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")), bool(row[1])


def feed_is_live(last, now) -> bool:
    if last is None or not last[1]:
        return False
    return 0.0 <= (pd.Timestamp(now) - last[0]).total_seconds() <= FEED_MAX_AGE_SEC


READ_COLS = ("game_id", "read_at", "period_label", "period", "clock_s", "home_score", "away_score",
             "spread_home", "spread_home_price", "spread_away_price", "total_line", "over_price", "under_price",
             "home_ml", "away_ml")
# (home_ml / away_ml: data/migrations/dk_live_reads_all_sports_2026_11_13.sql)


def recent_reads(conn, game_ids, sport: str = SPORT, lookback_min: int = LOOKBACK_MIN) -> pd.DataFrame:
    from data.db import release_read
    if not game_ids:
        return pd.DataFrame(columns=list(READ_COLS))
    try:
        rows = conn.execute(f"""
            SELECT {', '.join(READ_COLS)} FROM dk_live_reads
             WHERE sport = %s AND game_id = ANY(%s) AND read_at > NOW() - (%s || ' minutes')::interval
             ORDER BY game_id, read_at
        """, (sport, sorted(game_ids), str(int(lookback_min)))).fetchall()
    finally:
        release_read(conn)
    df = pd.DataFrame(rows, columns=list(READ_COLS))
    if len(df):
        df["read_at"] = pd.to_datetime(df["read_at"], utc=True)
        for c in READ_COLS[3:]:
            if c != "period_label":
                df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def _same(a, b) -> bool:
    return all((pd.isna(x) and pd.isna(y)) or x == y for x, y in zip(a, b))


def _fouls_at(plays: pd.DataFrame | None, stamp) -> tuple:
    if plays is None or not len(plays):
        return np.nan, np.nan
    p = plays[plays["wallclock"] <= stamp]
    if not len(p):
        return 0.0, 0.0
    last = p.sort_values(["wallclock", "play_no"]).iloc[-1]
    return float(last["h_tf"]), float(last["a_tf"])


def quote_states_dk(reads: pd.DataFrame, fetch_at, plays_by_game: dict) -> pd.DataFrame:
    """One row per (game, market) of DraftKings' current quote, shaped as
    models.ncaab_live_ig.quote_states' output, so eligible_quotes /
    decision_offers / choose run on it unchanged. `fetch_at` is the feed's
    last read; `plays_by_game[game_id]` is that game's ESPN plays with team
    fouls (models.ncaab_live_ig.with_team_fouls), or absent: the game is
    then left out (fouls unknown, fail closed)."""
    fetch_at = pd.Timestamp(fetch_at)
    out = []
    for gid, g in reads.groupby("game_id", sort=True):
        if gid not in plays_by_game:
            continue
        g = g[g["read_at"] <= fetch_at].sort_values("read_at").reset_index(drop=True)
        if not len(g):
            continue
        last = g.iloc[-1]
        for market, key in (("spreads", SPREAD_KEY), ("totals", TOTAL_KEY)):
            cur = tuple(last[k] for k in key)
            if any(pd.isna(x) for x in cur):
                continue
            i = len(g) - 1
            while i > 0 and _same(tuple(g.iloc[i - 1][k] for k in key), cur):
                i -= 1
            st = g.iloc[i]
            per = st["period"]
            if pd.isna(per) or pd.isna(st["clock_s"]) or pd.isna(st["home_score"]) or pd.isna(st["away_score"]):
                continue
            h_tf, a_tf = _fouls_at(plays_by_game.get(gid), st["read_at"])
            pts = abs((last["home_score"] + last["away_score"]) - (st["home_score"] + st["away_score"]))
            clock = float(st["clock_s"])
            out.append({
                "game_id": gid, "market": market, "book": BOOK, "stamp": st["read_at"], "fetch_at": fetch_at,
                "home_price": last["spread_home_price"] if market == "spreads" else np.nan,
                "away_price": last["spread_away_price"] if market == "spreads" else np.nan,
                "spread_home": last["spread_home"] if market == "spreads" else np.nan,
                "total_line": last["total_line"] if market == "totals" else np.nan,
                "over_price": last["over_price"] if market == "totals" else np.nan,
                "under_price": last["under_price"] if market == "totals" else np.nan,
                "period": float(per), "clock_s": clock, "game_s": (float(per) - 1) * 1200.0 + (1200.0 - clock),
                "type_text": "End Period" if st["period_label"] == "Halftime" else "",
                "h_pts": int(st["home_score"]), "a_pts": int(st["away_score"]), "h_tf": h_tf, "a_tf": a_tf,
                "h_fetch": int(last["home_score"]), "a_fetch": int(last["away_score"]),
                "pts_since": float(pts), "held": bool(fetch_at > st["read_at"]),
            })
    qs = pd.DataFrame(out, columns=QS_COLS)
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        qs[c] = pd.to_numeric(qs[c], errors="coerce").astype(float)
    return qs


# Another book's number must have stood this long on its page, with no score on
# DraftKings' board since the book set it, before it may decide. BetRivers
# moves AHEAD of DraftKings' score: measured 2026-11-26 (NCAAB, 827 of
# DraftKings' score changes on games BetRivers carried), its spread changed in
# the 5 s before DraftKings showed the score 370 times, against 171-231 in any
# other 5 s window from 5 to 65 s before. Inside 10 s a number can carry a
# basket our state does not; after it, DraftKings would have shown the score.
CONFIRM_SEC = 10.0


def _read_at_or_before(g: pd.DataFrame, at):
    """The game's newest DraftKings read at or before `at`, or None."""
    h = g[g["read_at"] <= at]
    return None if not len(h) else h.iloc[-1]


def quote_states_books(book_q: pd.DataFrame, reads: pd.DataFrame, fetch_at, plays_by_game: dict,
                       dk_qs: pd.DataFrame | None = None, outlier_pts: float = 6.0,
                       confirm_sec: float = CONFIRM_SEC) -> pd.DataFrame:
    """Another book's quotes (models.book_live_quotes.current_quotes at
    `fetch_at`) in quote_states_dk's shape, ALREADY FILTERED, so the window
    can add them after DraftKings' own hold checks (mike, 2026-11-26: "We want
    best line"; issue #1644). The rule's terms, on that book's number:
      STATE   DraftKings' board at the page time the book's number was first
              SHOWN (`shown`), as DraftKings' own rows are priced at their
              first sighting; fouls from ESPN at that time.
      FRESH   no point between the book's `stamp` (its previous read's page
              time: the number was set after it) and the decision read, on
              DraftKings' score. A number up before the last score is DROPPED,
              not held for: it is the book's to reprice, not ours to wait on.
      HELD    the book's newest read is after the read that first showed it.
      STOOD   shown at least `confirm_sec` before the decision read
              (CONFIRM_SEC: a book can move for a basket before DraftKings'
              board shows it).
      NEAR    within `outlier_pts` of DraftKings' own number on the market,
              when DraftKings has one: M.drop_outliers then cannot drop
              DraftKings' row for another book's stale one.
    A game with no DraftKings read at the stamp, or no ESPN plays, is left
    out (fail closed). `fetch_at` is DraftKings' feed read the window decides
    on, so the book's rows share its fetch (decision_offers prices the first)."""
    fetch_at = pd.Timestamp(fetch_at)
    out = []
    if book_q is None or not len(book_q) or reads is None or not len(reads):
        return pd.DataFrame(out, columns=QS_COLS)
    dk_num = {}
    if dk_qs is not None and len(dk_qs):
        for _i, r in dk_qs.iterrows():
            dk_num[(r["game_id"], r["market"])] = r["spread_home"] if r["market"] == "spreads" else r["total_line"]
    for _i, q in book_q.iterrows():
        gid, market = q["game_id"], q["market"]
        if market not in ("spreads", "totals") or gid not in plays_by_game or not bool(q["held"]):
            continue
        if (fetch_at - pd.Timestamp(q["shown"])).total_seconds() < confirm_sec:
            continue
        g = reads[reads["game_id"] == gid].sort_values("read_at")
        now_r = _read_at_or_before(g, fetch_at)
        at_stamp = _read_at_or_before(g, q["stamp"])
        st = _read_at_or_before(g, q["shown"])
        if now_r is None or at_stamp is None or st is None:
            continue
        if any(pd.isna(x) for x in (now_r["home_score"], now_r["away_score"], at_stamp["home_score"],
                                     at_stamp["away_score"], st["home_score"], st["away_score"],
                                     st["period"], st["clock_s"])):
            continue
        pts = abs((now_r["home_score"] + now_r["away_score"]) - (at_stamp["home_score"] + at_stamp["away_score"]))
        if pts > 0:
            continue
        num = q["spread_home"] if market == "spreads" else q["total_line"]
        ref = dk_num.get((gid, market))
        if ref is not None and pd.notna(ref) and abs(float(num) - float(ref)) > outlier_pts:
            continue
        h_tf, a_tf = _fouls_at(plays_by_game.get(gid), q["shown"])
        per, clock = float(st["period"]), float(st["clock_s"])
        out.append({
            "game_id": gid, "market": market, "book": q["book"], "stamp": q["shown"], "fetch_at": fetch_at,
            "home_price": q["home_price"] if market == "spreads" else np.nan,
            "away_price": q["away_price"] if market == "spreads" else np.nan,
            "spread_home": q["spread_home"] if market == "spreads" else np.nan,
            "total_line": q["total_line"] if market == "totals" else np.nan,
            "over_price": q["over_price"] if market == "totals" else np.nan,
            "under_price": q["under_price"] if market == "totals" else np.nan,
            "period": per, "clock_s": clock, "game_s": (per - 1) * 1200.0 + (1200.0 - clock),
            "type_text": "End Period" if st["period_label"] == "Halftime" else "",
            "h_pts": int(st["home_score"]), "a_pts": int(st["away_score"]), "h_tf": h_tf, "a_tf": a_tf,
            "h_fetch": int(now_r["home_score"]), "a_fetch": int(now_r["away_score"]),
            "pts_since": 0.0, "held": True,
        })
    qs = pd.DataFrame(out, columns=QS_COLS)
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        qs[c] = pd.to_numeric(qs[c], errors="coerce").astype(float)
    return qs


class DbSource:
    """A loop's DraftKings source on the worker: the two tables, read on the
    loop's own connection, for one sport."""

    def __init__(self, conn_fn, sport: str = SPORT):
        self.c, self.sport = conn_fn, sport

    def last_read(self):
        return feed_last_read(self.c(), self.sport)

    def reads(self, game_ids) -> pd.DataFrame:
        return recent_reads(self.c(), game_ids, sport=self.sport)


def current_quotes(reads: pd.DataFrame, fetch_at, markets=("spreads", "totals")) -> pd.DataFrame:
    """DraftKings' current number and prices per (game, market) at `fetch_at`,
    each stamped with the read where DraftKings FIRST showed it (the
    provider's last_update meant the same), in the `odds` row vocabulary the
    loops' quote frames use: game_id, market, book, stamp, spread_home,
    home_price, away_price, total_line, over_price, under_price. A game whose
    newest row carries no line for a market has no quote for it."""
    fetch_at = pd.Timestamp(fetch_at)
    keys = {"spreads": SPREAD_KEY, "totals": TOTAL_KEY, "h2h": ML_KEY}
    out = []
    for gid, g in reads.groupby("game_id", sort=True):
        g = g[g["read_at"] <= fetch_at].sort_values("read_at").reset_index(drop=True)
        if not len(g):
            continue
        last = g.iloc[-1]
        for market in markets:
            key = keys[market]
            if any(k not in g.columns for k in key):
                continue
            cur = tuple(last[k] for k in key)
            if any(pd.isna(x) for x in cur):
                continue
            i = len(g) - 1
            while i > 0 and _same(tuple(g.iloc[i - 1][k] for k in key), cur):
                i -= 1
            row = {"game_id": gid, "market": market, "book": BOOK, "stamp": g.iloc[i]["read_at"],
                   "spread_home": np.nan, "home_price": np.nan, "away_price": np.nan,
                   "total_line": np.nan, "over_price": np.nan, "under_price": np.nan}
            if market == "spreads":
                row.update(spread_home=cur[0], home_price=cur[1], away_price=cur[2])
            elif market == "h2h":
                row.update(home_price=cur[0], away_price=cur[1])
            else:
                row.update(total_line=cur[0], over_price=cur[1], under_price=cur[2])
            out.append(row)
    return pd.DataFrame(out, columns=["game_id", "market", "book", "stamp", "spread_home", "home_price",
                                      "away_price", "total_line", "over_price", "under_price"])
