"""
NBA player props: the projection model. Model id `nba_prop_projection`.

Asked for by mike on 2026-10-16 ("build the projection model"; "maximize units
won"). It projects each player's count from his minutes and his per-minute
rates (models/nba_props.py, the NHL count recipe carried to basketball),
widens the mean into a negative-binomial distribution, CALIBRATES that
probability per market, and bets every proposition whose calibrated EV at the
best bettable price clears its market's floor. The card that writes its picks
is scripts/nba_prop_projection_card.py; the artifact is fitted by
scripts/nba_prop_projection_train.py.

THE CARD (six cells; the evidence is docs/nba_models_2026.md section 5):

    market                  sides          calibrated-EV floor
    steals                  over + under   0.02
    rebounds                under          0.01
    blocks + steals         over + under   0.05
    blocks                  under          0.02
    rebounds + assists      under          0.04
    threes                  over + under   0.04

Graded walk-forward on 2023-24..2025-26 at the best of the eight bettable
books, the -200 price floor, every qualifying proposition: 83,360 bets,
+4.12% (the seven-cell research card less assists overs). The research chose
a seventh cell, ASSISTS OVERS, and it is NOT here: on 2025-26, the season it
was confirmed on, it made +0.74% with a 90% interval of -2.88..+4.27, its
neighbouring floor lost, its late half lost, and at the five books the live
feed returns it was -1.29% (DraftKings alone -3.51%).

THE RULE, per game, ONCE:
  1. Decide in the same window as nba_prop_market, 45-57 minutes before tip
     (models.nba_prop_market.DECISION_WINDOW_MIN), on the game's newest prop
     fetch, which must itself be from inside the window.
  2. Never a proposition another NBA prop model holds. A (game, player,
     market) nba_prop_market has bet is skipped on every line and both
     sides: one bet per proposition across the NBA prop models, as graded.
     So a game is decided only once nba_prop_market has decided it, or when
     the window is about to close without it (DECIDE_ALONE_BY_MIN).
  3. THE MAIN LINE ONLY: DraftKings' two-sided line, else the line most
     bettable books hang two-sided (ties: the lower). The calibration map
     holds there and only there (models/nba_props.py, calibration notes):
     one point off it the calibrated number barely moves while the outcome
     moves 4-8 points, in the direction that favours the better price.
  4. Over and under at that line, each at the best bettable price among
     config.BEST_LINE_BOOKMAKERS (never Pinnacle or Bovada; a tie to the
     earlier book in that list), the book's own two-way quote coherent
     (implied sum 1.00-1.15) and the price -200 or better.
  5. A quote whose own clock (book_last_update) is more than STALE_MAX_MIN
     behind the freshest book's clock for the same market in the same fetch
     is refused. The archive stored no clock, so this is a LIVE deviation
     from the graded population: most of the graded edge comes from the
     best price (the second-best price graded +1.45%), which is exactly
     where a stale quote hides. A quote with no clock is counted, not
     refused (the nba_prop_market convention).
  6. EV = calibrated P(side) x decimal - 1; bet when the side is in the
     market's cell and EV >= the cell's floor. If both sides clear, the
     higher EV. A player listed Out is never bet.

NO CAPS. Every qualifying proposition, no game or night cap (mike,
2026-10-16: "maximize units won").

WHAT THE WORKER CAN SEE, AND WHY THE MODEL USES ONLY THAT. The live worker
has the ESPN box line (whole minutes, starter flag, counting stats), the
schedule, the props and an injury table with two statuses, Out and
Day-To-Day. So the model was fitted on exactly those inputs: no usage, no
fouls, no Probable, no game lines (scripts/nba_prop_model_verify.py, the
"worker re-fit"). Day-To-Day stands in for Doubtful, Questionable and
Probable; Out for Out.

THE ROSTER A GAME IS PROJECTED WITH, both in training and live: everyone who
appeared for the team this season within ROSTER_DAYS days, everyone the
injury report at the decision lists Out or Day-To-Day, and (live) everyone a
book prices in the game. Training also had the game's own box; the timing
verifier rescored the card on the pre-game roster only and it held (+3.99%).

THE PROBABILITY SHOWN IS AN UPPER BOUND. Choosing on EV selects on the
model's own error: in the graded band the calibrated number claimed 0.533,
the bets won 0.501, the price implied 0.483.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

import models.nba_props as nb
from models.honest_ev import gate
from models.nba_prop_market import DECISION_WINDOW_MIN, minutes_to_tip, parse_ts

MODEL_ID = "nba_prop_projection"
SPORT = "NBA"

# market -> (sides it bets, calibrated-EV floor). docs/nba_models_2026.md 5.
CARD: dict[str, tuple[tuple[str, ...], float]] = {
    "player_steals":           (("over", "under"), 0.02),
    "player_rebounds":         (("under",), 0.01),
    "player_blocks_steals":    (("over", "under"), 0.05),
    "player_blocks":           (("under",), 0.02),
    "player_rebounds_assists": (("under",), 0.04),
    "player_threes":           (("over", "under"), 0.04),
}
MARKETS = tuple(CARD)
MARKET_LABEL = {m: nb.BY_MARKET[m].label for m in MARKETS}
# The base stats the card's markets sum: one per-minute rate model each.
STATS = tuple(s for s in nb.BASE_STATS if any(s in nb.BY_MARKET[m].parts for m in MARKETS))

# The inputs the worker cannot compute (scripts/nba_prop_model_verify.setup).
DROP_OWN = ("usg_l", "usg_s", "r_fouls_l", "own_p")
DROP_AVAIL = ("tm_o_usg", "ctx_o_usg", "d_o_usg", "opp_o_usg")

ROSTER_DAYS = 30
MU_FLOOR = 0.05                    # scripts/nba_prop_model_lab.MU_FLOOR
COHERENT = (1.00, 1.15)
STALE_MAX_MIN = 10
PRICE_FLOOR_DEFAULT = -200.0
# Wait for nba_prop_market's decision of the game until the tip is this close;
# then decide alone (nothing of the rule's can be taken that it has not bet).
DECIDE_ALONE_BY_MIN = 50.0

# The official report's five statuses, read as the ESPN table carries them.
_DTD = ("Doubtful", "Questionable", "Probable")
UNLISTED = "ESPN_UNLISTED"         # a team's report with nobody on it; not a REAL_STATUS
COVERED = "COVERED"                # one per game: a report existed at the decision


def minutes_cols() -> list[str]:
    """The minutes model's inputs: every frame input but the game lines and the worker-unknowns."""
    drop = set(DROP_OWN) | set(DROP_AVAIL)
    return [c for c in nb.OWN + nb.AVAIL + nb.SCHED + nb.TEAM if c not in drop]


def rate_cols(stat: str) -> list[str]:
    return minutes_cols() + nb.rate_features(stat)


# ── the worker's inputs, shaped as models/nba_props.build_frame reads them ────

def box_from_log(log: pd.DataFrame, games: pd.DataFrame, schedule: pd.DataFrame) -> pd.DataFrame:
    """nba_player_game_adv from the ESPN box log: whole minutes, played, starter; no usage or fouls.

    Regular-season games only. A log row whose team is neither side of its game is dropped.
    (scripts/nba_prop_model_verify.adv_from_log, unchanged.)
    """
    g = games.set_index("game_id")
    reg = set(schedule[schedule.game_type == "regular"].game_id)
    lg = log[log.game_id.isin(reg) & log.game_id.isin(g.index)].copy()
    home, away = lg.game_id.map(g.home_team), lg.game_id.map(g.away_team)
    ok = (lg.team == home) | (lg.team == away)
    lg, home, away = lg[ok], home[ok], away[ok]
    is_home = lg.team == home
    return pd.DataFrame({
        "game_id": lg.game_id.values, "player_id": lg.player_id.astype(str).values, "nba_game_id": None,
        "season": lg.season.values, "game_type": "regular", "game_date": lg.game_date.values,
        "team": lg.team.values, "opponent": np.where(is_home, away, home), "is_home": is_home.values,
        "player_name": lg.player_name.values, "position": None, "is_starter": lg.is_starter.values,
        "played": True, "minutes_exact": pd.to_numeric(lg.minutes, errors="coerce").astype(float).values,
        "usage_pct": np.nan, "fouls": np.nan})


def collapse_official(report: pd.DataFrame) -> pd.DataFrame:
    """The official report read as the ESPN table carries it: Doubtful / Questionable / Probable
    -> Questionable (Day-To-Day); Available -> not listed. (verify.collapse_report, lag 0.)"""
    r = report.copy()
    s = r.status.astype(object)
    s = s.where(~s.isin(_DTD), "Questionable")
    s = s.where(s != "Available", UNLISTED)
    r["status"] = s
    return r


def compact_report(report: pd.DataFrame, decisions: pd.DataFrame) -> pd.DataFrame:
    """What build_frame needs of a report, and nothing else: one COVERED row per game with any report
    row filed at or before its decision, and the Out / Questionable rows of each team's latest
    SUBMITTED report at or before it. build_frame reads this exactly as it reads the whole report
    (tests/test_nba_prop_projection.py), so the history can be stored small.

    `report`: game_id, team, report_ts (UTC), player_id, player_name, status (collapsed).
    `decisions`: game_id, decision_ts (UTC).
    """
    cols = ["game_id", "team", "report_ts", "player_id", "player_name", "status"]
    dec = decisions[["game_id", "decision_ts"]]
    cov = nb.injury_coverage(report, dec)
    covered = dec[cov.values]
    first_ts = report[report.game_id.isin(covered.game_id)].merge(dec, on="game_id")
    first_ts = first_ts[first_ts.report_ts <= first_ts.decision_ts].groupby("game_id").report_ts.min()
    marks = first_ts.rename("report_ts").reset_index().assign(
        team="", player_id=None, player_name="", status=COVERED)
    listed = nb.injury_asof(report, dec)
    listed = listed[listed.status.isin(["Out", "Questionable"])][cols]
    return pd.concat([marks[cols], listed], ignore_index=True)


def espn_compact(pull: pd.DataFrame, pull_ts, game_teams: pd.DataFrame) -> pd.DataFrame:
    """One ESPN injuries pull as the compact report for the games in `game_teams`.

    `pull`: the rows of ONE pull (team, player_name, status), statuses 'Out' / 'Day-To-Day';
    `pull_ts`: when it was taken; `game_teams`: game_id, team (both sides of each game).
    The pull is the whole league's list at that moment, so every game it covers gets its
    COVERED row whether or not anyone on either team is listed. ESPN's player ids are not
    NBA.com ids, so the name is kept and the id left for build_frame's roster match.
    """
    cols = ["game_id", "team", "report_ts", "player_id", "player_name", "status"]
    ts = pd.Timestamp(pull_ts)
    ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
    gids = game_teams.game_id.drop_duplicates()
    marks = pd.DataFrame({"game_id": gids.values, "team": "", "report_ts": ts, "player_id": None,
                          "player_name": "", "status": COVERED})
    p = pull[pull.status.isin(["Out", "Day-To-Day"])].copy()
    p["status"] = np.where(p.status == "Out", "Out", "Questionable")
    rows = game_teams.merge(p[["team", "player_name", "status"]], on="team")
    rows = rows.assign(report_ts=ts, player_id=None)[cols]
    return pd.concat([marks[cols], rows], ignore_index=True)


def asof_roster(box: pd.DataFrame, games: pd.DataFrame, report: pd.DataFrame,
                decisions: pd.DataFrame, game_ids, days: int = ROSTER_DAYS) -> pd.DataFrame:
    """Who a worker can know is on each team at the decision of each game in `game_ids`: everyone
    whose latest log appearance strictly before the game was for this team, this season, within
    `days` days; and everyone the report at the decision lists Out or Questionable.
    -> game_id, team, player_id, why, in_log. (verify.asof_roster, the game set made explicit so a
    game with no box yet -- tonight's -- has a roster too.)"""
    g = games[games.game_id.isin(set(game_ids))][["game_id", "season", "game_date", "home_team", "away_team"]]
    tg = pd.concat([g.rename(columns={"home_team": "team"})[["game_id", "season", "game_date", "team"]],
                    g.rename(columns={"away_team": "team"})[["game_id", "season", "game_date", "team"]]])
    tg["d"] = pd.to_datetime(tg.game_date)
    ap = box[["player_id", "player_name", "team", "season", "game_date"]].copy()
    ap["d"] = pd.to_datetime(ap.game_date)
    tsp = ap[["team", "season", "player_id"]].drop_duplicates()
    pairs = tg.merge(tsp, on=["team", "season"])
    last = ap.rename(columns={"team": "last_team", "season": "last_season", "d": "last_d"})[
        ["player_id", "last_team", "last_season", "last_d"]].sort_values("last_d")
    pairs = pairs.sort_values("d")
    m = pd.merge_asof(pairs, last, left_on="d", right_on="last_d", by="player_id",
                      allow_exact_matches=False)
    hist = m[(m.last_team == m.team) & (m.last_season == m.season)
             & ((m.d - m.last_d).dt.days <= days)][["game_id", "team", "player_id"]].assign(why="history")
    rep = nb.injury_asof(report, decisions[decisions.game_id.isin(set(game_ids))])
    rep = rep[rep.status.isin(["Out", "Questionable"])]
    who = box[["team", "season", "player_id", "player_name"]]
    rep = nb._attach_report_ids(rep, who)
    rep = rep[["game_id", "team", "player_id"]].assign(player_id=lambda x: x.player_id.astype(str), why="report")
    ros = pd.concat([hist, rep], ignore_index=True)
    if ros.empty:
        return pd.DataFrame(columns=["game_id", "team", "player_id", "why", "in_log"])
    ros = ros.groupby(["game_id", "team", "player_id"], as_index=False).why.agg(
        lambda s: "+".join(sorted(set(s))))
    inlog = set(zip(box.game_id, box.player_id))
    ros["in_log"] = [k in inlog for k in zip(ros.game_id, ros.player_id)]
    return ros


def worker_data(games: pd.DataFrame, schedule: pd.DataFrame, log: pd.DataFrame,
                report: pd.DataFrame, decisions: pd.DataFrame) -> dict:
    """The `data` dict build_frame reads, from the worker's inputs. Played games' absences are the
    pre-game roster's players with no box line (an inferred inactive list)."""
    box = box_from_log(log, games, schedule)
    ros = asof_roster(box, games, report, decisions, box.game_id.unique())
    names = box.drop_duplicates("player_id").set_index("player_id").player_name
    gm = games.set_index("game_id")
    ina = ros[~ros.in_log][["game_id", "team", "player_id"]].copy()
    ina["player_name"] = ina.player_id.map(names)
    ina["season"] = ina.game_id.map(gm.season)
    ina["game_date"] = ina.game_id.map(gm.game_date)
    ina["game_type"] = "regular"
    ina["reason"] = "inferred"
    return {"nba_games": games, "nba_schedule": schedule, "nba_player_game_log": log,
            "nba_player_game_adv": box, "nba_game_inactives": ina, "nba_injury_report": report,
            "player_positions": pd.DataFrame(columns=["player_id"])}


# ── the model ─────────────────────────────────────────────────────────────────

def predict_means(art: dict, rows: pd.DataFrame) -> pd.DataFrame:
    """Each row's projected minutes and the mean of every card market (two-stage: minutes x rate)."""
    out = pd.DataFrame(index=rows.index)
    mins = nb.predict_minutes(art["minutes"], rows)
    out["min_hat"] = mins
    mu = {s: nb.predict_rate_mean(art["rates"][s], rows, mins) for s in STATS}
    for m in MARKETS:
        out[f"mu_{m}"] = np.clip(sum(mu[s] for s in nb.BY_MARKET[m].parts), MU_FLOOR, None)
    return out


def p_over_calibrated(art: dict, market: str, mu, line) -> np.ndarray:
    """The negative-binomial P(over), then the market's Platt map: the probability the card prices."""
    raw = nb.p_over(np.asarray(mu, dtype=float), np.asarray(line, dtype=float), float(art["alphas"][market]))
    return nb.apply_calibration(raw, tuple(art["calibration"][market]))


# ── pricing ───────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProjectionBet:
    game_id: str
    game_date: str
    tip: str
    player: str                # the BET book's own spelling
    player_id: str
    market: str
    side: str                  # 'over' | 'under'
    line: float
    book: str
    price: float
    prob: float                # calibrated P(side): the model's own probability (an upper bound)
    ev: float
    mu: float                  # the projected count
    link: str | None
    fetch: str
    book_last_update: str | None
    dk_price: float | None     # DraftKings' own price on this side at this line, this fetch
    dk_link: str | None


def implied_one(american) -> float | None:
    if american is None or (isinstance(american, float) and np.isnan(american)):
        return None
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def coherent(q: dict) -> bool:
    o, u = implied_one(q.get("over_price")), implied_one(q.get("under_price"))
    return o is not None and u is not None and COHERENT[0] <= o + u <= COHERENT[1]


def main_line(quotes: list[dict], books: tuple[str, ...]) -> float | None:
    """DraftKings' two-sided line, else the line most bettable books hang two-sided (ties: the lower).
    (scripts/nba_prop_model_lab.main_lines.) `quotes`: one player-market's coherent two-sided rows."""
    q = [r for r in quotes if r["book"] in books]
    dk = [r for r in q if r["book"] == "draftkings"]
    if dk:
        return float(dk[0]["line"])
    if not q:
        return None
    counts: dict[float, int] = {}
    for r in q:
        counts[float(r["line"])] = counts.get(float(r["line"]), 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]


DIAG_KEYS = (
    "games", "too_early", "too_late", "window_missed", "already_decided", "waiting_for_rule",
    "in_window", "no_fetch", "stale_fetch", "no_projection", "decided",
    "propositions", "rule_holds", "out", "unpriced", "multi_line", "no_main_line",
    "stale_rejected", "last_update_unknown", "below_price_floor", "below_ev_floor",
    "qualifying", "bets",
)


def find_bets(quotes: list[dict], projections: pd.DataFrame, games: dict[str, dict],
              now: datetime, art: dict, rule_keys: set[tuple[str, str, str]],
              decided: set[str], rule_decided: set[str],
              books: tuple[str, ...], price_floor: float = PRICE_FLOOR_DEFAULT,
              ) -> tuple[list[ProjectionBet], dict, list[dict]]:
    """Every qualifying proposition, and the games this look decides. Pure.

    `quotes`: pre-game rows (game_id, player, player_id, market, book, line, over_price, under_price,
    over_link, under_link, snapshot_at, book_last_update), the player already resolved to an id
    (None where refused). `projections`: game_id, player_id, status, mu_<market>. `rule_keys`:
    (game_id, player_id, market) nba_prop_market holds. -> (bets, diag, decisions).
    """
    diag = dict.fromkeys(DIAG_KEYS, 0)
    bets: list[ProjectionBet] = []
    decisions: list[dict] = []
    lo, hi = DECISION_WINDOW_MIN
    by_game: dict[str, list[dict]] = {}
    for q in quotes:
        by_game.setdefault(q["game_id"], []).append(q)
    proj = projections.set_index(["game_id", "player_id"]) if len(projections) else None
    for gid in sorted(games):
        g = games[gid]
        tip = g["tip"]
        if tip is None or tip <= now:
            continue
        diag["games"] += 1
        lead = minutes_to_tip(tip, now)
        if lead > hi:
            diag["too_early"] += 1
            continue
        if gid in decided:
            diag["already_decided"] += 1
            continue
        if lead < lo:
            diag["too_late"] += 1
            continue
        if gid not in rule_decided and lead > DECIDE_ALONE_BY_MIN:
            diag["waiting_for_rule"] += 1
            continue
        diag["in_window"] += 1
        rows = [r for r in by_game.get(gid, [])
                if (t := parse_ts(r.get("snapshot_at"))) is not None and t <= now and t < tip]
        if not rows:
            diag["no_fetch"] += 1
            continue
        fetch_ts = max(parse_ts(r["snapshot_at"]) for r in rows)
        if minutes_to_tip(tip, fetch_ts) > hi:
            diag["stale_fetch"] += 1
            continue
        if proj is None or gid not in proj.index.get_level_values(0):
            diag["no_projection"] += 1
            continue
        fetch = [r for r in rows if parse_ts(r["snapshot_at"]) == fetch_ts]
        fetch_at = str(fetch[0]["snapshot_at"])
        before = dict(diag)
        n_bets = 0
        # the freshest clock per market in this fetch (the stale-quote reference)
        fresh: dict[str, datetime] = {}
        for r in fetch:
            lu = parse_ts(r.get("book_last_update"))
            if lu is not None and (r["market"] not in fresh or lu > fresh[r["market"]]):
                fresh[r["market"]] = lu
        keyed: dict[tuple[str, str], list[dict]] = {}
        for r in fetch:
            if r.get("player_id") and r["market"] in CARD:
                keyed.setdefault((str(r["player_id"]), r["market"]), []).append(r)
        for (pid, market), qs in sorted(keyed.items()):
            diag["propositions"] += 1
            if (gid, pid, market) in rule_keys:
                diag["rule_holds"] += 1
                continue
            if (gid, pid) not in proj.index:
                diag["no_projection"] += 1
                continue
            p = proj.loc[(gid, pid)]
            if isinstance(p, pd.DataFrame):
                p = p.iloc[0]
            if p.get("status") in ("Out", "Doubtful"):
                diag["out"] += 1
                continue
            two = [q for q in qs if q["book"] in books and q.get("line") is not None and coherent(q)]
            if any(sum(1 for q in two if q["book"] == b) > 1 for b in books):
                diag["multi_line"] += 1            # a book hanging two lines: which is its main is unknowable
                continue
            line = main_line(two, books)
            if line is None:
                diag["no_main_line"] += 1
                continue
            at = [q for q in two if float(q["line"]) == line]
            mu = float(p[f"mu_{market}"])
            p_over = float(p_over_calibrated(art, market, [mu], [line])[0])
            sides, floor = CARD[market]
            best: ProjectionBet | None = None
            for side in sides:
                col = f"{side}_price"
                cands = []
                for q in at:
                    price = q.get(col)
                    if price is None:
                        continue
                    lu = parse_ts(q.get("book_last_update"))
                    ref = fresh.get(market)
                    if lu is None or ref is None:
                        diag["last_update_unknown"] += 1
                    elif lu < ref - timedelta(minutes=STALE_MAX_MIN):
                        diag["stale_rejected"] += 1
                        continue
                    if float(price) < price_floor:
                        diag["below_price_floor"] += 1
                        continue
                    cands.append(q)
                if not cands:
                    diag["unpriced"] += 1
                    continue
                order = {b: i for i, b in enumerate(books)}
                q = sorted(cands, key=lambda r: (-float(r[col]), order[r["book"]]))[0]
                prob = p_over if side == "over" else 1.0 - p_over
                price = float(q[col])
                # the shared gate: own probability (config.MODELS_ON_OWN_PROBABILITY), and
                # config.MODEL_OWN_EV_FLOOR under the cell's own floor
                ok = gate(MODEL_ID, prob, price)
                ev = float(ok.ev)
                if ev < max(floor, ok.floor):
                    diag["below_ev_floor"] += 1
                    continue
                diag["qualifying"] += 1
                dk = next((r for r in at if r["book"] == "draftkings" and r.get(col) is not None), None)
                bet = ProjectionBet(
                    game_id=gid, game_date=g["game_date"], tip=tip.isoformat(),
                    player=q.get("player") or "", player_id=pid, market=market, side=side,
                    line=line, book=q["book"], price=price, prob=round(prob, 4), ev=round(ev, 4),
                    mu=round(mu, 3), link=q.get(f"{side}_link"), fetch=fetch_at,
                    book_last_update=q.get("book_last_update"),
                    dk_price=float(dk[col]) if dk is not None else None,
                    dk_link=dk.get(f"{side}_link") if dk is not None else None)
                if best is None or bet.ev > best.ev:
                    best = bet
            if best is not None:
                bets.append(best)
                n_bets += 1
                diag["bets"] += 1
        diag["decided"] += 1
        detail = " ".join(f"{k}={diag[k] - before.get(k, 0)}" for k in DIAG_KEYS
                          if diag[k] - before.get(k, 0))
        decisions.append({"game_id": gid, "fetch_at": fetch_at, "n_quotes": len(fetch),
                          "n_bets": n_bets, "detail": detail})
    return bets, diag, decisions
