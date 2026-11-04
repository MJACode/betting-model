"""
NCAAB game lines at the 15:00 UTC check: every bettable book's standing quote,
the sign-crossing artefacts removed, and the books' consensus.

Shared by the NCAAB spread model (models/ncaab_spread_market.py), the
moneyline model (models/ncaab_moneyline_own_spread.py, which also reads the
moneyline market and Pinnacle's and Bovada's quotes through the `books` and
`need_line` arguments) and the first-half models planned on the same pieces. One pure function
per step, so the card (scripts/ncaab_spread_card.py) and the build's replay
(scripts/ncaab_spread_market_build.py) run the SAME code: the card feeds it
rows read from `odds`, the replay the stored history.

THE CHECK INSTANT. 15:00 UTC on the game's date (games.game_date, the Eastern
date): 10:00 ET in winter, 11:00 EDT from mid-March. The research bought its
history at that instant; nothing else it tested held up (22:00 UTC the evening
before failed, the hour before tip made +0.43%). A game that tips at or before
the instant is never quoted.

A BOOK'S QUOTE at the instant is its newest pre-game row whose own stamp
(`snapshot_at`, the feed's last_update for that market) is at or before the
instant and no more than WINDOW_MIN minutes older, and at or before the tip.
Rows with no line or no price on either side are dropped first, so they can
never hide an older complete row. Two rows of one book with the same stamp:
the one stored last wins (`order`).

A DATA-ERROR QUOTE IS DROPPED AFTER THAT (models/ncaab_quote_bounds.py): a
book's quote whose line is outside its market's plausible range (a full-game
spread beyond +/-60) or whose price is beyond +/-100000.
It is dropped before the artefact rule and the consensus read it, so it can
never move a median, and the book's older row does NOT take its place: that
book has no quote at the instant. dropped_quotes() returns them, for the cards
to log and count.

THE ARTEFACT RULE. A quote on the other side of zero from the median of the
OTHER bettable books' quotes at the same instant (flagged or not) is a pick'em
sign error in the feed, not a price: with two or more other books it is
'artefact', with exactly one 'ambiguous'. Both are dropped. A 0 line never
flags (strict product < 0).

CONSENSUS. The median of the remaining quotes, the book being priced
INCLUDED, and their count (`n_ok`).

Measured 2026-11-02 on the 2026-27 slate (119 games with odds): the hourly
refresh pass at :17 past 9 a.m. ET stores every listed book's spread, so at
15:00 UTC the median stamp is 42 minutes old, and 83-96% of book-game pairs
hold a stamp inside the 60-minute window across the hours of that day.
Caesars (williamhill_us) was missing from the 14:00-16:00 UTC passes that day.
The five-minute capture (scripts/ncaab_odds_capture.py) adds a row only when a
number moves, so an unchanged quote keeps the pass's stamp.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from models import ncaab_quote_bounds as qb

# The bettable books the research priced and took the consensus over. Pinned
# here, not read from config.BEST_LINE_BOOKMAKERS: an environment override of
# that list must not silently change who is in the consensus.
BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics",
         "betrivers", "hardrockbet", "betparx")
CHECK_HOUR_UTC = 15
WINDOW_MIN = 60

QUOTE_COLS = ["game_id", "bookmaker", "ts", "line", "p1", "p2", "order"]


def check_instant(game_date) -> datetime:
    """15:00 UTC on the game's date."""
    d = pd.Timestamp(str(game_date)[:10])
    return datetime(d.year, d.month, d.day, CHECK_HOUR_UTC, tzinfo=timezone.utc)


def _utc(x) -> pd.Series:
    return pd.to_datetime(x, utc=True, format="mixed")


def _market(market: str | None, need_line: bool) -> str:
    return market or ("spreads" if need_line else "h2h")


def _newest(rows: pd.DataFrame, window_min: int | None, books, need_line: bool) -> pd.DataFrame:
    """Each (game, book)'s newest complete row in the window, data errors
    included: standing_quotes before the bounds. window_min=None: no
    window, each book's newest row however old."""
    if not len(rows):
        cols = list(dict.fromkeys(QUOTE_COLS + ["instant", "tip"] + list(rows.columns)))
        return pd.DataFrame(columns=cols)
    r = rows[rows["bookmaker"].isin(books)]
    r = r[(r["line"].notna() | (not need_line)) & r["p1"].notna() & r["p2"].notna()]
    keep = (r["ts"] <= r["tip"]) & (r["ts"] <= r["instant"]) & (r["instant"] < r["tip"])
    if window_min is not None:
        keep &= r["ts"] >= r["instant"] - pd.Timedelta(minutes=window_min)
    r = r[keep]
    r = r.sort_values(["game_id", "bookmaker", "ts", "order"], kind="mergesort")
    return r.drop_duplicates(["game_id", "bookmaker"], keep="last").reset_index(drop=True)


def standing_quotes(rows: pd.DataFrame, window_min: int | None = WINDOW_MIN, books=BOOKS,
                    need_line: bool = True, market: str | None = None) -> pd.DataFrame:
    """Each (game, book)'s quote at its game's instant.

    rows: one per stored odds row, with game_id, bookmaker, ts (the row's own
    stamp, UTC), line (home number for a spread), p1 / p2 (home / away
    American prices), order (higher = stored later), instant and tip (UTC) for
    its game, and any extra columns, which are carried through. Books outside
    `books` (default BOOKS) are ignored. need_line=False reads a market with
    no line (the moneyline, models/ncaab_moneyline_own_spread.py): a row then
    needs only its two prices. market names the bounds that apply
    (models/ncaab_quote_bounds.LINE_RANGE): 'spreads' by default, 'h2h' when
    need_line is False. A book whose newest row is a data error has no quote
    (dropped_quotes). window_min=None reads each book's newest row however old
    (the first-post moneyline model, models/ncaab_moneyline_first_post.py:
    change-only rows keep an unchanged quote's old stamp). -> one row per
    (game_id, bookmaker)."""
    q = _newest(rows, window_min, books, need_line)
    return qb.split(q, _market(market, need_line))[0].reset_index(drop=True)


def dropped_quotes(rows: pd.DataFrame, window_min: int | None = WINDOW_MIN, books=BOOKS,
                   need_line: bool = True, market: str | None = None) -> pd.DataFrame:
    """The quotes standing_quotes drops as data errors, with `market` and
    `why`: what the cards log and count."""
    q = _newest(rows, window_min, books, need_line)
    return qb.split(q, _market(market, need_line))[1].reset_index(drop=True)


def flag_and_consensus(q: pd.DataFrame) -> pd.DataFrame:
    """Add raw_loo / raw_nb (median and count of the OTHER books' lines,
    flagged or not), flag ('ok' | 'artefact' | 'ambiguous'), cons (median of
    the game's 'ok' lines, this book included) and n_ok (their count)."""
    q = q.copy()
    q["raw_loo"] = np.nan
    q["raw_nb"] = 0
    if not len(q):
        q["flag"] = pd.Series(dtype=object)
        q["cons"] = np.nan
        q["n_ok"] = 0
        return q
    loo = np.full(len(q), np.nan)
    nb = np.zeros(len(q), int)
    lines = q["line"].to_numpy(float)
    for _, idx in q.groupby("game_id", sort=False).indices.items():
        v = lines[idx]
        for j, k in enumerate(idx):
            others = np.delete(v, j)
            nb[k] = len(others)
            if len(others):
                loo[k] = np.median(others)
    q["raw_loo"] = loo
    q["raw_nb"] = nb
    cross = np.isfinite(loo) & (lines * np.where(np.isfinite(loo), loo, 0.0) < 0)
    q["flag"] = np.select([cross & (nb >= 2), cross & (nb == 1)], ["artefact", "ambiguous"], "ok")
    ok = q["flag"] == "ok"
    med = q[ok].groupby("game_id")["line"].median()
    cnt = q[ok].groupby("game_id")["line"].size()
    q["cons"] = q["game_id"].map(med)
    q["n_ok"] = q["game_id"].map(cnt).fillna(0).astype(int)
    return q


def snapshot(rows: pd.DataFrame, window_min: int | None = WINDOW_MIN) -> pd.DataFrame:
    """standing_quotes, then flag_and_consensus: the whole 15:00 UTC read."""
    return flag_and_consensus(standing_quotes(rows, window_min))


# ── the database read ────────────────────────────────────────────────────────

# The columns each market keeps its line and two prices in, home side first.
# A moneyline has no line (None: read as NULL).
MARKET_COLS = {
    "spreads": ("spread_home", "home_price", "away_price", "home_link", "away_link"),
    "h2h": (None, "home_price", "away_price", "home_link", "away_link"),
}


def load_rows(conn, games: dict[str, dict], instant: datetime, market: str = "spreads",
              window_min: int = WINDOW_MIN, books=BOOKS) -> pd.DataFrame:
    """The stored odds rows standing_quotes needs for these games at one
    instant: every pre-game row of `books` (default BOOKS) whose own stamp is
    inside the window. games: game_id -> {"tip": aware datetime, ...}. One
    read, keyed on the game ids, bounded to the hour before the instant."""
    if not games:
        return pd.DataFrame(columns=QUOTE_COLS + ["instant", "tip", "link1", "link2", "stored_at"])
    line_c, p1_c, p2_c, l1_c, l2_c = MARKET_COLS[market]
    line_sql = f"o.{line_c}" if line_c else "NULL"
    oldest = instant - timedelta(minutes=window_min)
    got = conn.execute(f"""
        SELECT o.game_id, o.bookmaker, o.snapshot_at, o.created_at::timestamptz,
               {line_sql}, o.{p1_c}, o.{p2_c}, o.{l1_c}, o.{l2_c}
        FROM odds o
        WHERE o.game_id = ANY(%s) AND o.market = %s AND o.bookmaker = ANY(%s)
          AND o.snapshot_type IS DISTINCT FROM 'in_play'
          AND o.snapshot_at::timestamptz <= %s
          AND o.snapshot_at::timestamptz >= %s
    """, (sorted(games), market, list(books), instant.isoformat(), oldest.isoformat())).fetchall()
    d = pd.DataFrame(got, columns=["game_id", "bookmaker", "snapshot_at", "stored_at", "line",
                                   "p1", "p2", "link1", "link2"])
    for c in ("line", "p1", "p2"):
        d[c] = pd.to_numeric(d[c], errors="coerce").astype(float)
    d["ts"] = _utc(d["snapshot_at"]) if len(d) else pd.Series(dtype="datetime64[ns, UTC]")
    stored = _utc(d["stored_at"]) if len(d) else pd.Series(dtype="datetime64[ns, UTC]")
    d["order"] = stored.dt.as_unit("ns").astype("int64") if len(d) else pd.Series(dtype="int64")
    d["instant"] = pd.Timestamp(instant)
    d["tip"] = d["game_id"].map({g: pd.Timestamp(v["tip"]) for g, v in games.items()})
    return d
