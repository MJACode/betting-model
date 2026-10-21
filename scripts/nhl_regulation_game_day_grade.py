"""The regulation model decided on game day, against what it actually bet.

mike, 2026-10-17: "Build the fix". On 2026-10-17 the two NHL moneyline models
posted "BOS (Regulation)" and "LAK ML" on the same game. The regulation model
had locked its pick 31 hours before puck drop, before Boston's back-to-back
game the night before was in; the moneyline model can only decide 16:00Z to
18:00Z on game day. The fix moves the regulation model into the same window.
This is the check promised before it ships: the live regulation artifact,
decided in that window, against the bets it really made this season, on the
same finished games.

WHAT RUNS. The registry's live artifact on the 2026-27 rows the training
builder makes (`build_training_dataset`, every game before the date in the
logs -- the game-day view). The production decision (`nhl_live_artifact_grade
.decide`): the model's own probability (it is in MODELS_ON_OWN_PROBABILITY),
its probability and edge cut, its EV floor, its price floor, the edge cap at
DraftKings. One bet per game per outcome, at DraftKings and at the best price
among the books a member can bet.

PRICES. The live feed's DraftKings / bettable-book `h2h_3way` rows, the LAST
quote of each book inside the window: game day 16:00Z to 18:00Z, or to the
start if that is earlier. A game with no DraftKings quote in the window is not
graded (counted and reported).

THE JOINT RULE. Graded twice: alone, and with every outcome that cannot win
alongside the moneyline model's BET on the same game removed -- what the
scorer does now (models/scorer._apply_nhl_side_conflicts).

THE BAR. The regulation model's real BETs on the same finished games, graded
at the price each was decided at (COALESCE(decision_odds, dk_odds)), one unit
risked per bet in both columns so the two are comparable.

WHAT IT IS NOT. About 120 games. A difference of a few units is noise; this
can show the move makes the model clearly worse, not that either is good.

    python -m scripts.nhl_regulation_game_day_grade
"""
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from data.db import get_connection  # noqa: E402
from features.feature_engine import build_training_dataset  # noqa: E402
from models.trainer import load_model  # noqa: E402
from scripts import nhl_live_artifact_grade as grade  # noqa: E402
from scripts.nhl_market_lab import implied, summarise, win_per_unit  # noqa: E402

pd.set_option("display.width", 250)
MID = "nhl_moneyline_regulation"
SEASON = 2027                       # 2026-27: NHL seasons carry the ENDING year
WINDOW = (16, 18)                   # UTC hours, game day -- the moneyline model's window
OUTCOMES = ("away", "draw", "home")
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)


def _ts(v):
    t = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def window_prices(conn, games: pd.DataFrame) -> pd.DataFrame:
    """Each book's last 3-way quote inside the game-day window."""
    rows = conn.execute(
        "SELECT game_id, bookmaker, snapshot_at, home_price, away_price, draw_price FROM odds "
        "WHERE game_id = ANY(%s) AND market = 'h2h_3way' AND snapshot_type = 'open' "
        "AND bookmaker = ANY(%s)", (list(games.game_id), BETTABLE)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "snap", "home", "away", "draw"])
    for c in ("home", "away", "draw"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.dropna(subset=["home", "away", "draw"])
    px["snap"] = px.snap.map(_ts)
    bounds = {}
    for g in games.itertuples():
        day = datetime.fromisoformat(str(g.game_date)[:10]).replace(tzinfo=timezone.utc)
        lo, hi = day + timedelta(hours=WINDOW[0]), day + timedelta(hours=WINDOW[1])
        bounds[g.game_id] = (lo, min(hi, _ts(g.commence_time)))
    keep = [bounds[g][0] <= s < bounds[g][1] for g, s in zip(px.game_id, px.snap)]
    px = px[keep].sort_values(["game_id", "book", "snap"])
    return px.groupby(["game_id", "book"], sort=False).last().reset_index()


def main() -> None:
    conn = get_connection()
    try:
        art = load_model(MID)
        grade._ARTIFACTS[MID] = art
        calibrated = MID not in config.MODELS_ON_OWN_PROBABILITY
        if calibrated:
            from models.probability_calibration import load_calibrations
            grade.CAL[MID] = load_calibrations(conn).get(MID)
        # Keep rows with a missing input, as the scorer does (it passes NaN to
        # XGBoost). The training builder drops them, and in October that is
        # every game where a team has not played at home or on the road yet:
        # 54 of the first 120 games on 2026-10-17.
        import features.feature_engine as fe
        fe.SPARSE_OK_FEATURES = frozenset(fe.SPARSE_OK_FEATURES) | frozenset(art["feature_cols"])
        f = build_training_dataset(MID, seasons=[SEASON], feature_cols=art["feature_cols"])
        f = f[0] if isinstance(f, tuple) else f
        P = art["model"].predict_proba(f[art["feature_cols"]].values.astype(float))
        pred = pd.DataFrame({"game_id": f.game_id.values,
                             "away_p": P[:, 0], "draw_p": P[:, 1], "home_p": P[:, 2]})

        games = pd.DataFrame(conn.execute(
            "SELECT game_id, game_date, commence_time, home_score, away_score, went_to_ot FROM games "
            "WHERE sport = 'NHL' AND season = %s AND home_score IS NOT NULL "
            "AND commence_time IS NOT NULL", (SEASON,)).fetchall(),
            columns=["game_id", "game_date", "commence_time", "hs", "as_", "ot"])
        for c in ("hs", "as_", "ot"):
            games[c] = pd.to_numeric(games[c], errors="coerce")
        games["result"] = np.where(games.ot == 1, "draw",
                                   np.where(games.hs > games.as_, "home", "away"))
        games = games.merge(pred, on="game_id", how="inner")
        px = window_prices(conn, games)
        dk = px[px.book == "draftkings"].set_index("game_id")
        graded = games[games.game_id.isin(dk.index)]

        ml = {(g, s) for g, s in conn.execute(
            "SELECT game_id, pick_side FROM picks WHERE model_id = 'nhl_moneyline' "
            "AND signal_type = 'BET' AND game_id = ANY(%s)", (list(graded.game_id),)).fetchall()}

        def clash(gid, outcome):
            """True when this outcome cannot win alongside a moneyline BET."""
            return any((gid, s) in ml for s in ("home", "away")
                       if outcome != "draw" and s != outcome)

        bets = []
        for g in graded.itertuples():
            book_rows = px[px.game_id == g.game_id]
            for o in OUTCOMES:
                p = getattr(g, f"{o}_p")
                dk_price = float(dk.loc[g.game_id, o])
                if abs(p - implied(dk_price)) > grade.EDGE_CAP:
                    continue                          # the scorer writes no row at all
                best = book_rows.loc[book_rows[o].idxmax()]
                for at, price in (("dk", dk_price), ("best", float(best[o]))):
                    if grade.decide(MID, p, price, calibrated=calibrated):
                        bets.append({"game_id": g.game_id, "gdate": g.game_date, "outcome": o,
                                     "at": at, "price": price, "p": p, "clash": clash(g.game_id, o),
                                     "profit": win_per_unit(price) if g.result == o else -1.0})
        b = pd.DataFrame(bets)

        real = pd.DataFrame(conn.execute(
            "SELECT game_id, pick_side, COALESCE(decision_odds, dk_odds), result, created_at FROM picks "
            "WHERE model_id = %s AND signal_type = 'BET' AND game_id = ANY(%s) "
            "AND result IN ('WIN', 'LOSS', 'PUSH')", (MID, list(graded.game_id))).fetchall(),
            columns=["game_id", "outcome", "price", "result", "created_at"])
        real["price"] = pd.to_numeric(real.price)
        real["profit"] = [win_per_unit(p) if r == "WIN" else (0.0 if r == "PUSH" else -1.0)
                          for p, r in zip(real.price, real.result)]
        start = graded.set_index("game_id").commence_time.map(_ts).to_dict()
        lead_h = [(start[g] - _ts(c)).total_seconds() / 3600
                  for g, c in zip(real.game_id, real.created_at)]

        print(f"{len(games)} finished 2026-27 games with a feature row; {len(graded)} have a DraftKings "
              f"3-way quote inside the game-day window ({len(games) - len(graded)} do not and are not graded)")
        print(f"moneyline-model BETs on those games: {len(ml)}")
        rows = [{"rule": "what it really bet (decided " + (f"{min(lead_h):.0f}-{max(lead_h):.0f}h before the start)"
                 if lead_h else ")"), **summarise(real.profit.values),
                 "win%": round(float((real.result == "WIN").mean()) * 100, 1) if len(real) else None}]
        for at, name in (("dk", "game-day window @ DraftKings"), ("best", "game-day window @ best bettable")):
            s = b[b["at"] == at] if len(b) else b
            for joint in (False, True):
                t = s[~s.clash] if (joint and len(s)) else s
                rows.append({"rule": name + (" + the joint rule" if joint else ""),
                             **summarise(t.profit.values if len(t) else np.array([])),
                             "win%": round(float((t.profit > 0).mean()) * 100, 1) if len(t) else None})
        print("\n### Same finished games, one unit risked per bet\n")
        print(pd.DataFrame(rows).to_string(index=False))
        if len(b):
            s = b[b["at"] == "best"]
            print(f"\ngame-day bets at the best bettable price by outcome: "
                  f"{s.outcome.value_counts().to_dict()}; removed by the joint rule: {int(s.clash.sum())}")
            both = set(s.game_id) & set(real.game_id)
            print(f"games bet by both the real (early) decision and the game-day one: {len(both)}; "
                  f"same outcome on {sum(1 for g in both if set(s[s.game_id == g].outcome) & set(real[real.game_id == g].outcome))}")
            r_in, r_out = real[real.game_id.isin(both)], real[~real.game_id.isin(both)]
            print(f"  on those games: real early bets {r_in.profit.sum():+.2f} units at avg price "
                  f"{r_in.price.mean():+.0f}; game-day bets {s[s.game_id.isin(both)].profit.sum():+.2f} units "
                  f"at avg price {s[s.game_id.isin(both)].price.mean():+.0f}")
            print(f"  the {len(r_out)} early bets game-day would not have made: {summarise(r_out.profit.values)}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
