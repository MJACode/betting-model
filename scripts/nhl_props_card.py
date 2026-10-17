"""Tonight's NHL saves, shots-on-goal and assists card: the unders each model likes, at the best price on offer.

Deployment of models/nhl_props (every Spec in `LIVE`). The blocked-shots card
(scripts/nhl_prop_card.py) is the same idea for one model at one book and is
left exactly as it went live; this one runs beside it in the same refresh-pass
step and borrows its slate reader, so the two cannot drift on what "tonight"
means.

For each live market: read the newest pre-game quote at each bettable book for
each player in tonight's unstarted games, build his inputs through the SAME
function the model was fitted and backtested on, and write ONE pick -- the
book, line and price with the best expected value -- when that clears the
model's own floor (config.MODEL_OWN_EV_FLOOR).

Deliberate, and load-bearing:

  UNDERS ONLY, THE MODEL'S OWN PROBABILITY, THE BEST PRICE. All three are how
  the cut was measured (scripts/nhl_prop_backtest.py).

  ONLY THE NEWEST FETCH OF A GAME IS SHOPPED. Every book in one fetch is
  quoted at the same instant, so "the best price" is one a bettor could take.
  A book that dropped out of the newest fetch is not carried forward from an
  older one: comparing prices taken at different moments is how the moneyline
  "edge" of 2026-10-01 was manufactured.

  INSERT-ONCE PER PLAYER PER GAME PER MARKET, KEYED ON THE PLAYER'S ID. A pick
  is a pick (CLAUDE.md 1c): when a line or a price moves, or a better book
  appears on a later pass, nothing happens to the pick that exists. The id,
  not the name, because two books spell one player two ways.

  ONE NHL PROP BET A GAME, ACROSS ALL FOUR PROP MODELS (mike, 2026-10-02:
  "1 max ... it needs to be the best of the best"). Blocked shots, saves,
  shots on goal and assists are pooled; the single best-EV bet in a game is
  written, and only if no NHL prop bet exists for that game already. A game
  whose best bet does not clear its model's floor gets none. Graded on three
  priced seasons (scripts/nhl_prop_combined_cap.py): with every floor at 0.18,
  +16.2% on 1,659 bets, every season positive, against +6.7% on 9,082 under
  the old per-model rules.

  THE DraftKings COLUMNS MEAN DraftKings. The row is written the way the
  scorer writes a pick decided away from DraftKings (CLAUDE.md 6):
  `decision_*` carry the book, price and edge the bet was DECIDED at;
  `dk_odds` / `dk_implied_prob` / `edge` carry DraftKings' own number for the
  same line when it quoted one, and are empty when it did not, in which case
  `line_book` names whose line it is. The betslip, the all-books card, Discord
  and the closing-line capture already read rows of that shape; a row with
  another book's price in `dk_odds` is one the betslip would call DraftKings'.

  A LIMIT PER GAME (Spec.max_per_game; shots on goal: 3, mike 2026-10-01).
  The best-EV bets in a game are kept up to the limit, and a pick an earlier
  pass already wrote counts against it: a later pass adds only what is left
  and never replaces a pick that exists.

  A GOALIE A BOOK PRICES IS TAKEN AS STARTING. That is the bet: the books void
  saves when he does not start, and settlement does the same.

  A PLAYER IT CANNOT IDENTIFY IS SKIPPED AND LOGGED, never guessed.

    python -m scripts.nhl_props_card                 # tonight's card, writes nothing
    python -m scripts.nhl_props_card --publish       # write the picks
    python -m scripts.nhl_props_card --date 2026-10-01 --model nhl_prop_saves
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402
import models.nhl_props as np_  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.season_labels import nhl_season_label  # noqa: E402
from scripts.nhl_prop_card import COHERENT_SUM, ET, _utc, slate  # noqa: E402

QUOTE_COLS = ["game_id", "player", "book", "line", "over", "under", "snap", "over_link", "under_link"]


def latest_quotes(conn, games: dict[str, dict], market: str) -> pd.DataFrame:
    """Each game's NEWEST pre-game fetch: one row per (game, player, book, line) in one market."""
    if not games:
        return pd.DataFrame(columns=QUOTE_COLS)
    rows = conn.execute("""
        SELECT game_id, player_name, bookmaker, line, over_price, under_price, snapshot_at, over_link, under_link
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND market = %s AND bookmaker = ANY(%s) AND snapshot_type = 'open'
    """, (list(games), market, list(np_.books()))).fetchall()
    q = pd.DataFrame(rows, columns=QUOTE_COLS)
    if q.empty:
        return q
    q["snap"] = q.snap.map(_utc)
    for c in ("line", "over", "under"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q = q[[s <= _utc(games[g]["commence_time"]) for g, s in zip(q.game_id, q.snap)]]
    if q.empty:
        return q.reset_index(drop=True)
    q = q[q.snap == q.groupby("game_id").snap.transform("max")]
    q = q.drop_duplicates(["game_id", "player", "book", "line"], keep="last")
    two = q.over.notna() & q.under.notna()
    total = q.over.map(np_.implied, na_action="ignore") + q.under.map(np_.implied, na_action="ignore")
    bad = two & ~total.between(*COHERENT_SUM)
    if bad.any():
        logger.warning(f"nhl-props-card: {int(bad.sum())} {market} quote(s) dropped as incoherent "
                       f"({q[bad].book.value_counts().to_dict()})")
    return q[~bad & q.line.notna()].reset_index(drop=True)


def candidates(conn, kind: str, teams: list[str], seasons: list[int]) -> pd.DataFrame:
    """Everyone who has played for one of tonight's teams this season or last (read by team, not league-wide)."""
    table = "nhl_goalie_game_log" if kind == "goalie" else "nhl_skater_game_log"
    rows = conn.execute(f"""
        SELECT DISTINCT player_id, player_name FROM {table}
        WHERE team = ANY(%s) AND season = ANY(%s) AND game_type = 2 AND player_id IS NOT NULL
    """, (list(teams), list(seasons))).fetchall()
    d = pd.DataFrame(rows, columns=["player_id", "player_name"])
    d["pkey"] = d.player_name.map(np_.name_key)
    return d


def identities(players: pd.DataFrame) -> pd.DataFrame:
    """Each loaded player's MOST RECENT row: the team he plays for now (and a skater's position)."""
    cols = ["player_id", "player_name", "team"] + (["position"] if "position" in players.columns else [])
    if players.empty:
        return pd.DataFrame(columns=cols + ["pkey"])
    last = (players.sort_values(["game_date", "nhl_game_id"]).groupby("player_id", sort=False).tail(1)
            [cols].copy())
    last["pkey"] = last.player_name.map(np_.name_key)
    return last


def upcoming_rows(quotes: pd.DataFrame, games: dict[str, dict], who: pd.DataFrame,
                  game_date: str, season: int) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    """Place each priced name on one of the two teams.

    Returns (one row per PLAYER-game for the model, the quotes with the
    player's id attached, who was skipped). A name that matches nobody, or
    more than one player in the game, or a player whose last team is neither
    side (he changed teams and has not played for the new one yet) is skipped
    and named.
    """
    rows, ids, skipped = {}, [], []
    for (gid, player), _ in quotes.groupby(["game_id", "player"], sort=False):
        g = games[gid]
        m = who[(who.pkey == np_.name_key(player)) & who.team.isin([g["home"], g["away"]])]
        if len(m) != 1:
            skipped.append(f"{player} ({gid}): {'no' if m.empty else len(m)} match on either team")
            continue
        p = m.iloc[0]
        ids.append({"game_id": gid, "player": player, "player_id": int(p.player_id)})
        row = {"player_id": int(p.player_id), "player_name": p.player_name,
               "season": season, "game_date": game_date, "team": p.team,
               "opponent": g["away"] if p.team == g["home"] else g["home"],
               "is_home": int(p.team == g["home"]), "game_id": gid}
        if "position" in who.columns:
            row["position"] = p.position
        rows[(gid, int(p.player_id))] = row
    priced = (quotes.merge(pd.DataFrame(ids), on=["game_id", "player"]) if ids
              else quotes.iloc[0:0].assign(player_id=pd.Series(dtype="int64")))
    return pd.DataFrame(list(rows.values())), priced, skipped


def best_bet(spec: np_.Spec, mu: float, quotes: pd.DataFrame, dispersion: float) -> dict | None:
    """The one bet to make on a player: the best expected value among every book, line and side the
    Spec may take that clears the model's floor and the price floor. None when nothing does.

    Two books at the same line and price are the same bet; the one named is the
    earlier in `books()` (DraftKings first), so the pick does not depend on the
    order rows came back in.
    """
    from models.honest_ev import gate
    floor = config.min_odds_for(spec.model_id)
    rank = {b: i for i, b in enumerate(np_.books())}
    best = None
    for q in sorted(quotes.itertuples(), key=lambda q: rank.get(q.book, len(rank))):
        po = float(np_.p_over(mu, q.line, dispersion))
        for side, price, link, p in (("over", q.over, q.over_link, po), ("under", q.under, q.under_link, 1 - po)):
            if side not in spec.sides or price is None or pd.isna(price) or float(price) < floor:
                continue
            ev = gate(spec.model_id, p, float(price))
            if not ev.clears:
                continue
            raw = np_.expected_value(p, float(price))
            if best is None or raw > best["ev"]:
                best = {"side": side, "price": float(price), "p": p, "ev": raw, "cal": ev.cal_prob,
                        "book": q.book, "line": float(q.line), "link": link, "quote_player": q.player}
    return best


def draftkings_at(quotes: pd.DataFrame, line: float, side: str) -> dict | None:
    """DraftKings' own quote for this player at THIS line and side, or None when it has none.

    A DraftKings quote at a different number is not a price for this bet.
    """
    dk = quotes[(quotes.book == np_.BOOK) & (quotes.line == line)]
    if dk.empty or pd.isna(dk[side].iloc[0]):
        return None
    return {"price": float(dk[side].iloc[0]), "link": dk[f"{side}_link"].iloc[0], "player": dk.player.iloc[0]}


def pick_rows(spec: np_.Spec, mus: pd.DataFrame, priced: pd.DataFrame, games: dict[str, dict],
              game_date: str, bankroll: float, dispersion: float) -> list[dict]:
    """Model means + priced quotes -> one picks row per player that clears. Pure, so it is testable."""
    rows = []
    for m in mus.itertuples():
        q = priced[(priced.game_id == m.game_id) & (priced.player_id == m.player_id)]
        d = best_bet(spec, m.mu, q, dispersion)
        if d is None:
            continue
        g = games[m.game_id]
        side = "Over" if d["side"] == "over" else "Under"
        implied = np_.implied(d["price"])
        dk = draftkings_at(q, d["line"], d["side"])
        dk_implied = np_.implied(dk["price"]) if dk else None
        elsewhere = d["book"] != np_.BOOK
        # The name DraftKings uses when it quoted this line (that is the name
        # the closing-line lookup searches for), else the deciding book's.
        name = dk["player"] if dk else d["quote_player"]
        rows.append({
            "game_id": m.game_id, "model_id": spec.model_id, "sport": "NHL",
            "game_date": game_date, "game_time": g.get("commence_time"),
            "pick_side": d["side"],
            "pick_label": f"{name} {side} {d['line']:g} {spec.label}",
            "model_probability": round(d["p"], 4),
            "model_probability_cal": round(d["cal"], 4),
            # DraftKings' number at this line, or the NOT NULL placeholders when
            # it has none (the scorer's convention: _make_prop_pick, line_book).
            "dk_odds": dk["price"] if dk else None,
            "dk_implied_prob": round(dk_implied, 4) if dk else 0.0,
            "edge": round(d["p"] - dk_implied, 4) if dk else 0.0,
            "dk_bet_link": dk["link"] if dk else None,
            "line_book": None if dk else d["book"],
            "scored_line": d["line"],
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "prop_market": spec.market, "player_key": name,
            "player_id": str(int(m.player_id)),
            "decision_book": d["book"], "decision_odds": d["price"],
            "decision_implied_prob": round(implied, 4), "decision_edge": round(d["p"] - implied, 4),
            # The better-than-DraftKings price and its betslip link, for the
            # surfaces that publish "the best book and price".
            "best_book": d["book"] if elsewhere else None,
            "best_odds": d["price"] if elsewhere else None,
            "best_implied_prob": round(implied, 4) if elsewhere else None,
            "best_edge": round(d["p"] - implied, 4) if elsewhere else None,
            "best_bet_link": d["link"] if elsewhere else None,
            "_ev": round(d["ev"], 4), "_mu": round(float(m.mu), 3),
        })
    return rows


def existing_picks(conn, model_id: str, game_ids: list[str]) -> dict[str, set[str]]:
    """The players this model has already picked in each game: {game_id: {player_id}}."""
    if not game_ids:
        return {}
    out: dict[str, set[str]] = {}
    for gid, pid in conn.execute(
            "SELECT game_id, player_id FROM picks WHERE model_id = %s AND game_id = ANY(%s)",
            (model_id, list(game_ids))).fetchall():
        out.setdefault(gid, set()).add(str(pid))
    return out


def limit_per_game(spec: np_.Spec, rows: list[dict], existing: dict[str, set[str]] | None = None) -> list[dict]:
    """At most `spec.max_per_game` picks a game, best EV first, counting the picks already written.

    A row for a player already picked is dropped (publish would skip it, and
    it holds its slot already). Pure, so it is testable.
    """
    if spec.max_per_game is None:
        return rows
    existing = existing or {}
    left = {}
    kept = []
    for r in sorted(rows, key=lambda r: (-r["_ev"], r["player_id"])):
        have = existing.get(r["game_id"], set())
        if r["player_id"] in have:
            continue
        n = left.setdefault(r["game_id"], spec.max_per_game - len(have))
        if n <= 0:
            continue
        left[r["game_id"]] = n - 1
        kept.append(r)
    return kept


# Every NHL prop model. One bet a game is shared among all of them.
PROP_MODEL_IDS = ("nhl_prop_blocked_shots", "nhl_prop_saves", "nhl_prop_shots_on_goal", "nhl_prop_assists")
MAX_PROP_BETS_PER_GAME = 1
# At most FOUR NHL prop bets a night (one game_date), best EV first, the picks
# already written that night included (mike, 2026-10-08: "4 a night"; it was
# two from 2026-10-03, mike: "Too many fucking unders nhl props.").
#
# WHY FOUR. The two-a-night figures (832 bets, +20.9%, +173.8 units) were
# inflated by a backtest defect: a shared player name (two Elias Petterssons)
# priced the forward's shots-on-goal under at the defenceman's count, +60.9 of
# those units. With shared names refused as the card refuses them
# (scripts/nhl_prop_backtest.namesakes, #895), the four models together at EV
# >= 0.18, one a game, three priced seasons (worker job 444467,
# scripts/nhl_prop_ev_lab.py), in units a season:
#   2 a night +38.8 (+14.4%) | 3 +46.1 | 4 +54.6 (+12.9%) | 6 +56.8 | none +65.6
# Every season is positive at every level. On the books that post these
# markets live, four a night (+56.8) matches no limit (+56.5) against +35.5
# for two: the gain with a hard ceiling. About 2.8 bets a night on average.
# The backtest keeps each night's best; live, a pass writes what has cleared
# by then, and a later better bet does not replace an earlier one.
# docs/nhl_clv_ev_assessment.md.
MAX_PROP_BETS_PER_NIGHT = 4


def games_with_a_prop_bet(conn, game_ids: list[str]) -> set[str]:
    """The games any NHL prop model has already written a pick for."""
    if not game_ids:
        return set()
    return {r[0] for r in conn.execute(
        "SELECT DISTINCT game_id FROM picks WHERE model_id = ANY(%s) AND game_id = ANY(%s)",
        (list(PROP_MODEL_IDS), list(game_ids))).fetchall()}


def prop_bets_by_night(conn, game_dates: list[str]) -> dict[str, int]:
    """How many NHL prop picks are already written for each game_date."""
    if not game_dates:
        return {}
    return {str(d): int(n) for d, n in conn.execute(
        "SELECT game_date, count(*) FROM picks WHERE model_id = ANY(%s) AND game_date = ANY(%s) "
        "GROUP BY game_date", (list(PROP_MODEL_IDS), list(game_dates))).fetchall()}


def per_night(rows: list[dict], written: dict[str, int] | None = None) -> list[dict]:
    """At most MAX_PROP_BETS_PER_NIGHT a game_date, best EV first, written picks counted. Pure."""
    written = written or {}
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=lambda r: (-r["_ev"], r["model_id"], str(r["player_id"]))):
        d = str(r["game_date"])
        n = left.setdefault(d, MAX_PROP_BETS_PER_NIGHT - written.get(d, 0))
        if n <= 0:
            continue
        left[d] = n - 1
        kept.append(r)
    return kept


def one_per_game(rows: list[dict], taken: set[str] | None = None) -> list[dict]:
    """The best-EV row in each game across every prop model, none for a game already bet. Pure."""
    taken = taken or set()
    left: dict[str, int] = {}
    kept = []
    for r in sorted(rows, key=lambda r: (-r["_ev"], r["model_id"], str(r["player_id"]))):
        if r["game_id"] in taken:
            continue
        n = left.setdefault(r["game_id"], MAX_PROP_BETS_PER_GAME)
        if n <= 0:
            continue
        left[r["game_id"]] = n - 1
        kept.append(r)
    return kept


def publish_across_models(rows: list[dict]) -> int:
    """Write the one bet a game the four prop models' rows allow. The only door a prop pick goes through."""
    from scripts.nhl_prop_card import publish as publish_blocked
    if not rows:
        return 0
    conn = get_connection()
    try:
        taken = games_with_a_prop_bet(conn, sorted({r["game_id"] for r in rows}))
        written = prop_bets_by_night(conn, sorted({str(r["game_date"]) for r in rows}))
        chosen = per_night(one_per_game(rows, taken), written)
        logger.info(f"nhl-props: {len(chosen)} bet(s) kept of {len(rows)} that clear "
                    f"(one a game, {MAX_PROP_BETS_PER_NIGHT} a night, across all four prop models; "
                    f"{len(taken)} game(s) already bet; already written by night {written})")
        written = 0
        for r in chosen:
            written += (publish_blocked if r["model_id"] == "nhl_prop_blocked_shots" else publish)(conn, [r])
        return written
    finally:
        conn.close()


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "model_probability_cal", "dk_implied_prob", "edge", "dk_odds", "scored_line",
         "kelly_fraction", "recommended_bet", "bankroll_at_pick", "signal_type", "confidence_tier",
         "prop_market", "player_key", "player_id", "dk_bet_link", "line_book",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "best_book", "best_odds", "best_implied_prob", "best_edge", "best_bet_link")
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)})")


def publish(conn, rows: list[dict]) -> int:
    """Insert-once per (game, model, market, player id): a later pass never touches a pick that exists."""
    written = 0
    for r in rows:
        if conn.execute("""
            SELECT 1 FROM picks WHERE game_id = %s AND model_id = %s AND prop_market = %s AND player_id = %s
        """, (r["game_id"], r["model_id"], r["prop_market"], r["player_id"])).fetchone():
            continue
        conn.execute(_INSERT, {c: r[c] for c in _COLS})
        written += 1
    if written:
        conn.commit()
    return written


def render(spec: np_.Spec, n_scored: int, rows: list[dict], skipped: list[str]) -> str:
    out = [f"NHL {spec.label.lower()} card — {n_scored} priced player(s) scored, {len(rows)} bet(s), "
           f"{len(skipped)} skipped"]
    for r in sorted(rows, key=lambda x: -x["_ev"]):
        out.append(f"  {r['pick_label']:44s} {r['decision_odds']:+5.0f} @ {r['decision_book']:14s} "
                   f"model {r['model_probability']:.3f}  mean {r['_mu']:.2f}  EV {r['_ev'] * 100:+.1f}%")
    for s in skipped:
        out.append(f"  skipped: {s}")
    return "\n".join(out)


def score_market(conn, spec: np_.Spec, games: dict[str, dict], game_date: str,
                 artifact: dict | None = None) -> dict:
    """One market's card: the model's mean for each priced player, the picks that clear, who was skipped."""
    out = {"priced": 0, "mus": pd.DataFrame(), "quotes": pd.DataFrame(), "rows": [], "skipped": []}
    quotes = latest_quotes(conn, games, spec.market)
    out["priced"] = int(quotes.groupby(["game_id", "player"]).ngroups) if len(quotes) else 0
    if quotes.empty:
        logger.info(f"nhl-props-card: no {spec.market} quotes at a bettable book for {game_date} "
                    f"({len(games)} unstarted game(s))")
        return out
    art = artifact
    if art is None:
        from models.trainer import load_model
        art = load_model(spec.model_id)
    if art is None:
        logger.error(f"nhl-props-card: no active {spec.model_id} artifact — nothing scored")
        return out
    season = nhl_season_label(game_date)
    teams = sorted({t for g in games.values() for t in (g["home"], g["away"])})
    cand = candidates(conn, spec.kind, teams, [season, season - 1])
    named = cand[cand.pkey.isin({np_.name_key(p) for p in quotes.player})]
    cols = list(np_.GOALIE_COLS if spec.kind == "goalie" else np_.SKATER_COLS)
    pl = (np_.load_players(conn, spec.kind, sorted(named.player_id.unique())) if len(named)
          else pd.DataFrame(columns=cols))
    # Strictly before tonight. Nothing is logged for a game that has not been
    # played, but a replay of a past slate would otherwise read it.
    pl = pl[pl.game_date.astype(str) < game_date]
    up, priced, skipped = upcoming_rows(quotes, games, identities(pl), game_date, season)
    mus = pd.DataFrame()
    if len(up):
        tm = np_.load_teams(conn)
        tm = tm[tm.game_date.astype(str) < game_date]
        frame = np_.build_frame(spec, pl[pl.player_id.isin(up.player_id)], tm, up)
        f = np_.usable(spec, frame[frame.upcoming]).copy()
        for pid in sorted(set(up.player_id) - set(f.player_id)):
            skipped.append(f"{up[up.player_id == pid].player_name.iloc[0]}: under "
                           f"{np_.MIN_GAMES} games in the log, or an input missing")
        if len(f):
            f["mu"] = np_.predict_mean(spec, art, f)
            mus = f[["player_id", "game_id", "mu"]].reset_index(drop=True)
    rows = []
    if len(mus):
        from models.scorer import _get_current_bankroll
        rows = pick_rows(spec, mus, priced, games, game_date, _get_current_bankroll(conn),
                         float(art.get("dispersion", 0.0)))
        n_clear = len(rows)
        rows = limit_per_game(spec, rows, existing_picks(conn, spec.model_id, sorted(games)))
        if len(rows) < n_clear:
            logger.info(f"nhl-props-card: {spec.model_id} kept {len(rows)} of {n_clear} that clear "
                        f"(at most {spec.max_per_game} a game, picks already written included)")
    out.update(mus=mus, quotes=priced, rows=rows, skipped=skipped)
    logger.info("\n" + render(spec, len(mus), rows, skipped))
    return out


def run_card(game_date: str | None = None, do_publish: bool = False, now: datetime | None = None,
             artifacts: dict | None = None, keep: dict | None = None, only: str | None = None) -> dict:
    """The pipeline entry point (run_pipeline step + refresh pass).

    `now` and `artifacts` ({model_id: artifact}) exist so a past slate can be
    replayed against named artifacts; `keep`, when given, receives each
    market's scored frame and pick rows. One market failing does not stop the
    next: each is its own model.
    """
    now = now or datetime.now(timezone.utc)
    game_date = game_date or now.astimezone(ET).strftime("%Y-%m-%d")
    out: dict = {"date": game_date}
    conn = get_connection()
    try:
        games = slate(conn, game_date, now)
        pooled: list[dict] = []
        for spec in np_.LIVE:
            if only and spec.model_id != only:
                continue
            try:
                r = score_market(conn, spec, games, game_date, (artifacts or {}).get(spec.model_id))
                pooled += r["rows"]
                out[spec.model_id] = {"priced": r["priced"], "scored": len(r["mus"]), "bets": len(r["rows"]),
                                      "skipped": len(r["skipped"])}
                if keep is not None:
                    keep[spec.model_id] = r
            except Exception as exc:
                conn.rollback()
                logger.error(f"nhl-props-card: {spec.model_id} failed: {exc}")
                out[spec.model_id] = {"error": str(exc)}
        # Pooled, then one a game: the best bet across the markets, not the first market's.
        out["published"] = publish_across_models(pooled) if (do_publish and pooled) else 0
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=None)
    ap.add_argument("--model", default=None, choices=[s.model_id for s in np_.LIVE])
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(a.date, do_publish=a.publish, only=a.model))


if __name__ == "__main__":
    main()
