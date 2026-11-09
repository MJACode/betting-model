"""End to end: the LIVE loop on real 2025-26 games, against the lab's decisions.

Each sampled game is replayed through nba_live.gameday.Loop.tick exactly as a
night would run it, from the raw inputs the loop reads live:
  * ESPN's real game summary (free), cut to the plays whose wallclock is at
    or before the moment the loop reads it (the tick's served instant plus
    the settle wait), with the game reported in progress;
  * an odds payload in the feed's own JSON shape, built from the archive's
    quotes at that purchase (every book, h2h and spreads), parsed by the
    pre-game ingestor's parser as the live loop parses it;
  * Pinnacle's pre-game spread rows and the starters' prior minutes as the
    lab had them; the lab's own walk-forward model for 2025-26.
The loop's decisions are compared with the replay of the shipped rule on the
lab's table (scripts/nba_live_ingame_replay.py) at the same purchase: the same
models decided, bet or no bet, side, book, number and price.

    PYTHONPATH=. NBA_RESEARCH_CACHE=<v2> python -m scripts.nba_live_ingame_e2e --games 60
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import models.nba_live_ingame as M  # noqa: E402
from data.ingestors.odds_ingestor import NBA_ODDS_API_MAP  # noqa: E402
from nba_live import espn as E  # noqa: E402
from nba_live import gameday as G  # noqa: E402
from nba_live import odds as O  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_ingame_data as D  # noqa: E402
from scripts import nba_ingame_ig2 as IG  # noqa: E402
from scripts import nba_live_ingame_replay as R  # noqa: E402

NAME = {}
for full, code in NBA_ODDS_API_MAP.items():
    NAME.setdefault(code, full)


class Clock:
    def __init__(self, t):
        self.t = t

    def now(self):
        return self.t

    def sleep(self, s):
        self.t = self.t + timedelta(seconds=s)


class ArchiveEspn:
    def __init__(self, clock, summary_json, event):
        self.clock, self.j, self.event = clock, summary_json, event
        self.calls = 0

    def scoreboard(self, d):
        self.calls += 1
        return [self.event]

    def summary(self, eid):
        self.calls += 1
        t = self.clock.now().strftime("%Y-%m-%dT%H:%M:%SZ")
        j = dict(self.j)
        j["plays"] = [p for p in self.j.get("plays") or [] if (p.get("wallclock") or "") <= t]
        head = json.loads(json.dumps(self.j["header"]))
        head["competitions"][0]["status"] = {"type": {"state": "in", "completed": False}}
        j["header"] = head
        return j


class Resp:
    def __init__(self, payload):
        self._p, self.status_code = payload, 200
        self.headers = {"x-requests-last": "2", "x-requests-remaining": "2000000"}

    def json(self):
        return self._p

    def raise_for_status(self):
        pass


class ArchiveOdds:
    def __init__(self, payload):
        self.payload, self.calls = payload, 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        return Resp(self.payload)


def payload_from(rows: pd.DataFrame, home: str, away: str, tip) -> list:
    hn, an = NAME[home], NAME[away]
    books = []
    for b, g in rows.groupby("book"):
        mk = []
        for r in g.itertuples(index=False):
            stamp = pd.Timestamp(r.stamp).strftime("%Y-%m-%dT%H:%M:%SZ")
            if r.market == "h2h":
                mk.append({"key": "h2h", "last_update": stamp, "outcomes": [
                    {"name": hn, "price": float(r.price_a)}, {"name": an, "price": float(r.price_b)}]})
            else:
                mk.append({"key": "spreads", "last_update": stamp, "outcomes": [
                    {"name": hn, "price": float(r.price_a), "point": float(r.line)},
                    {"name": an, "price": float(r.price_b), "point": -float(r.line)}]})
        books.append({"key": b, "markets": mk})
    return [{"id": "x", "home_team": hn, "away_team": an,
             "commence_time": pd.Timestamp(tip).strftime("%Y-%m-%dT%H:%M:%SZ"), "bookmakers": books}]


class ArchiveStore(G.Store):
    def __init__(self, game, pin_rows, minutes):
        super().__init__(conn_factory=lambda: None)
        self.game, self.pin_rows, self.minutes = game, pin_rows, minutes
        self.ledger, self.picks = {}, []

    def resolve_game(self, home, away, et_date):
        g = self.game
        return {"game_id": g["game_id"], "home": g["home_team"], "away": g["away_team"],
                "game_date": str(g["game_date"])[:10], "season": 2026, "g_ct": g["tip"].isoformat(),
                "s_ct": g["tip"].isoformat(), "game_type": "regular",
                "days": [(2026, "2025-10-21", "regular"), (2026, "2026-04-12", "regular")]}

    def pinnacle_spread_rows(self, game_id, tip):
        return self.pin_rows

    def decided_models(self, game_id):
        return set()

    def prior_minutes(self, box, season, before):
        return {int(r["athlete_id"]): self.minutes.get(int(r["athlete_id"]), 0.0) for r in box}

    def bankroll(self):
        return 1000.0

    def used_today(self):
        return 0

    def write_decision(self, row, pick):
        self.ledger[(row["game_id"], row["model_id"])] = row
        if pick:
            self.picks.append(pick)
        return True, pick is not None

    def record_prices(self, rows, known):
        return 0

    def record_fetch(self, credits, fired_at):
        pass

    def notify(self, d):
        pass

    def recycle(self):
        pass

    def close(self):
        pass


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games", type=int, default=60)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--quotes", default=str(D.OUT))
    ap.add_argument("--json", default=None)
    ap.add_argument("--game", default=None, help="only this game id (debugging)")
    a = ap.parse_args()
    q = R.load_table(Path(a.quotes))
    q = q[q["season"] == 2026]
    train, _ = IG.training_states(H.CACHE)
    model = IG.models_by_season(train, M.FEATURES)[2026]
    prior = IG.pregame_prior(H.CACHE)
    ref = R.replay(q, prior, {2026: model}, (2026,))
    ref = ref[ref["fetch_at"].dt.minute == 0]                  # the hourly ticks the loop has
    games = H.load_games(H.CACHE).set_index("game_id")
    if a.game:
        ref = ref[ref["game_id"] == a.game]
    sample = ref.drop_duplicates(["game_id", "fetch_at"]).sample(
        n=min(a.games, ref[["game_id", "fetch_at"]].drop_duplicates().shape[0]), random_state=a.seed)
    # the archive's pre-game Pinnacle spreads, created_at = the purchase instant
    data = H.load(H.CACHE, seasons=[2026])
    pin = data.quotes[(data.quotes["book"] == "pinnacle") & (data.quotes["market"] == "spreads")]
    pm = D.prior_minutes((2026,))
    art = M.load_artifact()
    client = E.EspnClient()
    out, mism = [], []
    for s in sample.itertuples(index=False):
        g = games.loc[s.game_id]
        rows = q[(q["game_id"] == s.game_id) & (q["fetch_at"] == s.fetch_at)]
        eid = int(rows["espn_game_id"].iloc[0])
        j = client.summary(eid)
        time.sleep(0.25)
        if j is None:
            out.append({"game_id": s.game_id, "error": "no summary"})
            continue
        comp = j["header"]["competitions"][0]
        h = next(c for c in comp["competitors"] if c["homeAway"] == "home")["team"]
        aw = next(c for c in comp["competitors"] if c["homeAway"] == "away")["team"]
        ev = E.EspnEvent(eid, comp.get("date"), 2, "in", False, None, h["abbreviation"], aw["abbreviation"],
                         h.get("location"), aw.get("location"))
        served = pd.Timestamp(rows["served_at"].iloc[0]).to_pydatetime()
        clock = Clock(served)                                  # the fetch is served at the lab's instant
        pr = pin[pin["game_id"] == s.game_id]
        pin_rows = [(s.game_id, "pinnacle", "spreads", "open", r.snapshot_at.isoformat(),
                     r.fetch_at.isoformat(), float(r.line), float(r.price_a), float(r.price_b))
                    for r in pr.itertuples(index=False)]
        mins = {int(r.athlete_id): float(r.prior_min) for r in pm[(pm["espn_game_id"] == eid) & pm["athlete_id"].notna()].itertuples(index=False)}
        store = ArchiveStore({"game_id": s.game_id, "home_team": g["home_team"], "away_team": g["away_team"],
                              "game_date": g["game_date"], "tip": g["tip"]}, pin_rows, mins)
        feed = O.LiveOddsFeed(session=ArchiveOdds(payload_from(rows, g["home_team"], g["away_team"], g["tip"])),
                              now=clock.now)
        import os
        os.environ.setdefault("ODDS_API_KEY", "replay")
        loop = G.Loop(store, ArchiveEspn(clock, j, ev), feed, art, now=clock.now, sleep=clock.sleep,
                      clock=G.TickClock(second=(served.minute * 60 + served.second)), settle=30)
        loop.models[2026] = model
        loop.pass_once()
        lab = ref[(ref["game_id"] == s.game_id) & (ref["fetch_at"] == s.fetch_at)]
        game_g = next(iter(loop.games.values()))
        lab_mu = float(prior.set_index("game_id")["mu_pre"].get(s.game_id, np.nan))
        for r in lab.itertuples(index=False):
            live = store.ledger.get((s.game_id, r.model_id))
            same = (live is not None and bool(live["bet"]) == bool(r.bet)
                    and (not r.bet or (live["side"] == r.side and live["book"] == r.book
                                       and np.isclose(live["price"], r.price)
                                       and (r.market == "h2h" or np.isclose(live["line"], r.line)))))
            row = {"game_id": s.game_id, "model_id": r.model_id, "lab": r.reason,
                   "live": None if live is None else live["reason"], "same": bool(same),
                   "mu_lab": round(lab_mu, 4), "mu_live": None if game_g is None or game_g.mu_pre is None
                   else round(game_g.mu_pre, 4)}
            out.append(row)
            if not same:
                mism.append(row)
        extra = {k for k in store.ledger if k[1] not in set(lab["model_id"])}
        for k in extra:
            mism.append({"game_id": k[0], "model_id": k[1], "lab": None, "live": store.ledger[k]["reason"]})
    n = len([x for x in out if "same" in x])
    ok = sum(1 for x in out if x.get("same"))
    mu = [abs(x["mu_lab"] - x["mu_live"]) for x in out if x.get("mu_live") is not None and x["mu_lab"] == x["mu_lab"]]
    print(f"{ok} of {n} decisions identical (bet or not; side, book, number, price) across "
          f"{sample.shape[0]} game-ticks; {len(mism)} mismatches; "
          f"max |prior live - lab| {max(mu) if mu else float('nan'):.6f}")
    for m_ in mism[:40]:
        print(json.dumps(m_))
    if a.json:
        Path(a.json).write_text(json.dumps({"decisions": out, "mismatches": mism}, indent=1, default=str),
                                encoding="utf-8")


if __name__ == "__main__":
    main()
