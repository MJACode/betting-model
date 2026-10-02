"""Tonight's NHL blocked-shots card: price DraftKings' lines with the model, bet the unders that clear.

Deployment of models/nhl_prop_blocked_shots. This script is plumbing: read the
newest pre-game DraftKings quote for each player in tonight's unstarted games,
build each player's inputs through the SAME function the model was fitted and
backtested on, and write a pick when the expected value at DraftKings' price
clears the model's own floor (config.MODEL_OWN_EV_FLOOR).

Deliberate, and load-bearing:

  IT DECIDES ON THE MODEL'S OWN PROBABILITY (config.MODELS_ON_OWN_PROBABILITY).
  The cut was measured on that number. The correction a model with no record
  is given turned the same three seasons from +6.2% into a loss
  (scripts/nhl_prop_blocked_shots_backtest.py).

  INSERT-ONCE PER PLAYER PER GAME. A pick is a pick (CLAUDE.md 1c): when the
  line or the price moves after it is written, nothing happens to it.

  A PLAYER IT CANNOT IDENTIFY IS SKIPPED AND LOGGED, never guessed. The price
  row carries a name; the model needs his game log and which side he plays
  for, and settlement needs his id.

  DraftKings posts this market within a few hours of puck drop (none at any
  book five hours out on 2026-10-01), so the card runs right after the prop
  price step on every refresh pass and is a clean no-op until quotes exist.

    python -m scripts.nhl_prop_card                 # tonight's card, writes nothing
    python -m scripts.nhl_prop_card --publish       # write the picks
    python -m scripts.nhl_prop_card --date 2026-10-01
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
import config  # noqa: E402
import models.nhl_prop_blocked_shots as bs  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.season_labels import nhl_season_label  # noqa: E402
from models.scorer import _pause_note  # noqa: E402

MODEL_ID = bs.MODEL_ID
ET = ZoneInfo("America/New_York")
COHERENT_SUM = (1.00, 1.15)      # a two-way quote outside this is not one anyone was offered
STAT_LABEL = "Blocked Shots"


def _utc(v) -> datetime:
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def slate(conn, game_date: str, now: datetime) -> dict[str, dict]:
    """Tonight's games that have not started."""
    rows = conn.execute("""
        SELECT game_id, home_team, away_team, commence_time
        FROM games WHERE sport = 'NHL' AND game_date = %s AND commence_time IS NOT NULL
    """, (game_date,)).fetchall()
    return {r[0]: {"home": r[1], "away": r[2], "commence_time": r[3]}
            for r in rows if _utc(r[3]) > now}


def latest_quotes(conn, games: dict[str, dict]) -> pd.DataFrame:
    """The newest pre-game DraftKings quote per (game, player)."""
    if not games:
        return pd.DataFrame(columns=["game_id", "player", "line", "over", "under", "snap", "over_link", "under_link"])
    rows = conn.execute("""
        SELECT game_id, player_name, line, over_price, under_price, snapshot_at, over_link, under_link
        FROM player_prop_odds
        WHERE game_id = ANY(%s) AND market = %s AND bookmaker = %s AND snapshot_type = 'open'
    """, (list(games), bs.MARKET, bs.BOOK)).fetchall()
    q = pd.DataFrame(rows, columns=["game_id", "player", "line", "over", "under", "snap", "over_link", "under_link"])
    if q.empty:
        return q
    q["snap"] = q.snap.map(_utc)
    for c in ("line", "over", "under"):
        q[c] = pd.to_numeric(q[c], errors="coerce")
    q = q[[s <= _utc(games[g]["commence_time"]) for g, s in zip(q.game_id, q.snap)]]
    q = q.sort_values("snap").drop_duplicates(["game_id", "player"], keep="last")
    two = q.over.notna() & q.under.notna()
    total = q.over.map(bs_implied, na_action="ignore") + q.under.map(bs_implied, na_action="ignore")
    bad = two & ~total.between(*COHERENT_SUM)
    if bad.any():
        logger.warning(f"nhl-prop-card: {int(bad.sum())} DraftKings quote(s) dropped as incoherent")
    return q[~bad & q.line.notna()].reset_index(drop=True)


def bs_implied(american: float) -> float:
    return 100.0 / (american + 100.0) if american > 0 else abs(american) / (abs(american) + 100.0)


def candidates(conn, teams: list[str], seasons: list[int]) -> pd.DataFrame:
    """Every skater who has played for one of tonight's teams this season or last.

    Read through the (team, season, game_date) index: a league-wide "latest row
    per player" sorts the whole log and was cancelled by the statement timeout
    the first time this card was replayed.
    """
    rows = conn.execute("""
        SELECT DISTINCT player_id, player_name FROM nhl_skater_game_log
        WHERE team = ANY(%s) AND season = ANY(%s) AND game_type = 2
    """, (list(teams), list(seasons))).fetchall()
    d = pd.DataFrame(rows, columns=["player_id", "player_name"])
    d["pkey"] = d.player_name.map(bs.name_key)
    return d


def identities(skaters: pd.DataFrame) -> pd.DataFrame:
    """Each loaded skater's MOST RECENT row: the team he plays for now, and his position."""
    if skaters.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "team", "position", "pkey"])
    last = (skaters.sort_values(["game_date", "nhl_game_id"]).groupby("player_id", sort=False).tail(1)
            [["player_id", "player_name", "team", "position"]].copy())
    last["pkey"] = last.player_name.map(bs.name_key)
    return last


def upcoming_rows(quotes: pd.DataFrame, games: dict[str, dict], who: pd.DataFrame,
                  game_date: str, season: int) -> tuple[pd.DataFrame, list[str]]:
    """One row per priced player the log can place on one of the two teams.

    A name that matches nobody, or more than one player in the game, or a
    player whose last team is neither side (he changed teams and has not played
    for the new one yet) is skipped and named.
    """
    rows, skipped = [], []
    for q in quotes.itertuples():
        g = games[q.game_id]
        m = who[(who.pkey == bs.name_key(q.player)) & who.team.isin([g["home"], g["away"]])]
        if len(m) != 1:
            skipped.append(f"{q.player} ({q.game_id}): {'no' if m.empty else len(m)} match on either team")
            continue
        p = m.iloc[0]
        rows.append({"player_id": int(p.player_id), "player_name": p.player_name, "position": p.position,
                     "season": season, "game_date": game_date, "team": p.team,
                     "opponent": g["away"] if p.team == g["home"] else g["home"],
                     "is_home": int(p.team == g["home"]), "game_id": q.game_id, "quote_player": q.player})
    return pd.DataFrame(rows), skipped


def decide(mu: float, line: float, over, under) -> dict | None:
    """The better side at DraftKings' prices, or None when neither is priced."""
    po = float(bs.p_over(mu, line))
    best = None
    for side, price, p in (("over", over, po), ("under", under, 1 - po)):
        if price is None or pd.isna(price):
            continue
        ev = bs.expected_value(p, float(price))
        if best is None or ev > best["ev"]:
            best = {"side": side, "price": float(price), "p": p, "ev": ev}
    return best


def pick_rows(scored: pd.DataFrame, games: dict[str, dict], game_date: str, bankroll: float) -> list[dict]:
    """Scored players -> picks rows for the ones that clear. Pure, so it is testable."""
    from models.honest_ev import gate
    floor = config.min_odds_for(MODEL_ID)
    rows = []
    for r in scored.itertuples():
        d = decide(r.mu, r.line, r.over, r.under)
        if d is None:
            continue
        ev = gate(MODEL_ID, d["p"], d["price"])
        if not ev.clears or d["price"] < floor:
            continue
        g = games[r.game_id]
        side = "Over" if d["side"] == "over" else "Under"
        implied = bs_implied(d["price"])
        rows.append({
            "game_id": r.game_id, "model_id": MODEL_ID, "sport": "NHL",
            "game_date": game_date, "game_time": g.get("commence_time"),
            "pick_side": d["side"],
            "pick_label": f"{r.quote_player} {side} {r.line:g} {STAT_LABEL} (DK)",
            "model_probability": round(d["p"], 4),
            "model_probability_cal": round(ev.cal_prob, 4),
            "dk_implied_prob": round(implied, 4),
            "edge": round(d["p"] - implied, 4),
            "dk_odds": d["price"], "scored_line": float(r.line),
            "kelly_fraction": 0.01, "recommended_bet": round(0.01 * bankroll, 2),
            "bankroll_at_pick": bankroll, "signal_type": "BET",
            "confidence_tier": "MED",
            "prop_market": bs.MARKET, "player_key": r.quote_player,
            "player_id": str(r.player_id),
            "dk_bet_link": r.over_link if d["side"] == "over" else r.under_link,
            "decision_book": bs.BOOK, "decision_odds": d["price"],
            "decision_implied_prob": round(implied, 4), "decision_edge": round(d["p"] - implied, 4),
            # A paused model keeps its verdict and says it is paused (#850).
            "downgrade_reason": _pause_note(MODEL_ID),
            "_ev": round(d["ev"], 4), "_mu": round(float(r.mu), 3),
        })
    return rows


_COLS = ("game_id", "model_id", "sport", "game_date", "game_time", "pick_side", "pick_label",
         "model_probability", "dk_implied_prob", "edge", "dk_odds", "scored_line", "kelly_fraction",
         "recommended_bet", "bankroll_at_pick", "signal_type", "confidence_tier", "prop_market",
         "player_key", "player_id", "dk_bet_link", "model_probability_cal",
         "decision_book", "decision_odds", "decision_implied_prob", "decision_edge",
         "downgrade_reason")
_INSERT = (f"INSERT INTO picks ({', '.join(_COLS)}) "
           f"VALUES ({', '.join('%(' + c + ')s' for c in _COLS)})")


def publish(conn, rows: list[dict]) -> int:
    """Insert-once per (game, player, market): a second pass never touches a pick that exists."""
    written = 0
    for r in rows:
        if conn.execute("""
            SELECT 1 FROM picks WHERE game_id = %s AND model_id = %s AND player_key = %s AND prop_market = %s
        """, (r["game_id"], r["model_id"], r["player_key"], r["prop_market"])).fetchone():
            continue
        conn.execute(_INSERT, {c: r[c] for c in _COLS})
        written += 1
    if written:
        conn.commit()
    return written


def render(scored: pd.DataFrame, rows: list[dict], skipped: list[str]) -> str:
    out = [f"NHL blocked-shots card — {len(scored)} priced player(s) scored, {len(rows)} bet(s), "
           f"{len(skipped)} skipped"]
    for r in sorted(rows, key=lambda x: -x["_ev"]):
        out.append(f"  {r['pick_label']:46s} {r['dk_odds']:+5.0f}  model {r['model_probability']:.3f}  "
                   f"mean {r['_mu']:.2f}  EV {r['_ev'] * 100:+.1f}%")
    for s in skipped:
        out.append(f"  skipped: {s}")
    return "\n".join(out)


def run_card(game_date: str | None = None, do_publish: bool = False, now: datetime | None = None,
             artifact: dict | None = None, keep: dict | None = None) -> dict:
    """The pipeline entry point (run_pipeline step + refresh pass).

    `now` and `artifact` exist so a past slate can be replayed against a named
    artifact; `keep`, when given, receives the scored frame and the pick rows.
    """
    now = now or datetime.now(timezone.utc)
    game_date = game_date or now.astimezone(ET).strftime("%Y-%m-%d")
    out = {"date": game_date, "priced": 0, "scored": 0, "bets": 0, "published": 0, "skipped": 0}
    conn = get_connection()
    try:
        games = slate(conn, game_date, now)
        quotes = latest_quotes(conn, games)
        out["priced"] = len(quotes)
        if quotes.empty:
            logger.info(f"nhl-prop-card: no DraftKings {bs.MARKET} quotes for {game_date} "
                        f"({len(games)} unstarted game(s))")
            return out
        art = artifact
        if art is None:
            from models.trainer import load_model
            art = load_model(MODEL_ID)
        if art is None:
            logger.error(f"nhl-prop-card: no active {MODEL_ID} artifact — nothing scored")
            return out
        season = nhl_season_label(game_date)
        teams = sorted({t for g in games.values() for t in (g["home"], g["away"])})
        cand = candidates(conn, teams, [season, season - 1])
        named = cand[cand.pkey.isin({bs.name_key(p) for p in quotes.player})]
        # Strictly before tonight. Nothing is logged for a game that has not
        # been played, but a replay of a past slate would otherwise read it.
        sk = bs.load_skaters(conn, sorted(named.player_id.unique())) if len(named) else pd.DataFrame(
            columns=list(bs.SKATER_COLS))
        sk = sk[sk.game_date.astype(str) < game_date]
        up, skipped = upcoming_rows(quotes, games, identities(sk), game_date, season)
        out["skipped"] = len(skipped)
        scored = pd.DataFrame()
        if len(up):
            tm = bs.load_teams(conn)
            tm = tm[tm.game_date.astype(str) < game_date]
            frame = bs.build_frame(sk[sk.player_id.isin(up.player_id)], tm, up.drop(columns=["quote_player"]))
            f = bs.usable(frame[frame.upcoming]).copy()
            short = set(up.player_id) - set(f.player_id)
            for pid in sorted(short):
                skipped.append(f"{up[up.player_id == pid].quote_player.iloc[0]}: under "
                               f"{bs.MIN_GAMES} games in the log, or an input missing")
            if len(f):
                f["mu"] = bs.predict_mean(art["model"], f)
                scored = (f[["player_id", "game_id", "mu"]]
                          .merge(up[["player_id", "game_id", "quote_player"]], on=["player_id", "game_id"])
                          .merge(quotes.rename(columns={"player": "quote_player"}),
                                 on=["game_id", "quote_player"]))
        out["scored"], out["skipped"] = len(scored), len(skipped)
        rows = []
        if len(scored):
            from models.scorer import _get_current_bankroll
            rows = pick_rows(scored, games, game_date, _get_current_bankroll(conn))
        out["bets"] = len(rows)
        if keep is not None:
            keep.update(scored=scored, rows=rows, skipped=skipped)
        logger.info("\n" + render(scored, rows, skipped))
        if do_publish and rows:
            out["published"] = publish(conn, rows)
            logger.info(f"nhl-prop-card: published {out['published']} new pick(s) of {len(rows)} that clear")
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=None)
    ap.add_argument("--publish", action="store_true")
    a = ap.parse_args()
    print(run_card(a.date, do_publish=a.publish))


if __name__ == "__main__":
    main()
