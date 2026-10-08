"""The two LIVE NHL artifacts, graded in units at real prices on their holdout season.

Rounds one to three of docs/nhl_market_lab.md graded a DIFFERENT model (a
regularised logistic on the per-game logs). Nothing had put the artifacts
`model_registry` says are live -- `nhl_moneyline` and
`nhl_moneyline_regulation`, both trained 2018-19 -> 2024-25 -- against a price.
2025-26 is the only season neither has seen, so it is the only season graded.

WHAT RUNS. The production .pkl through the production decision
(`models.scorer._decide`, re-stated in `decide` below): the probability
correction every model decides on (`model_calibration.promoted_b`, applied by
`apply_calibration`), the per-model probability / edge cut, the EV floor, the
price floor, the edge cap at DraftKings. Each rule is reported twice: as it
runs today, and on the model's own probability with the correction off.

PRICES. Moneyline: `odds.source = 'odds_api_historical'`, the bet decided at
each book's FIRST pre-game quote; closing-line value is Pinnacle's LAST
pre-game no-vig probability minus Pinnacle's FIRST, on the side taken (round
three's measurement; the blind rows carry it too, as the bar).
Regulation 3-way: the prop-history purchase, one pre-game snapshot per game,
so no closing-line value. "best" is the best price among the books a member
can bet (`config.BEST_LINE_BOOKMAKERS`).

WHAT IT IS NOT. Production scores a game when its line opens, days ahead, and
locks the pick; this decides at the game-day quote. And 1,352 games carry an
interval of several points either side -- this can show a loss, not prove an
edge.

    python -m scripts.nhl_live_artifact_grade
    python -m scripts.nhl_live_artifact_grade --artifact nhl_moneyline=models/saved/x.pkl

`--artifact` grades a file instead of the registry's live version (a retrain
candidate before it is switched on). Each artifact is scored on the frame its
OWN feature list builds, so an old one and a new one can be read side by side.
"""
import pickle
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import config  # noqa: E402
from data.db import get_connection  # noqa: E402
from data.ingestors.nhl_prop_odds_history import SOURCE as PROP_SOURCE  # noqa: E402
from features.feature_engine import build_training_dataset  # noqa: E402
from models.probability_calibration import apply_calibration, load_calibrations  # noqa: E402
from models.trainer import load_model  # noqa: E402
from scripts.nhl_market_lab import implied, novig, summarise, win_per_unit  # noqa: E402

pd.set_option("display.width", 250)
FEED = "odds_api_historical"
SEASON = 2026
MODELS = ("nhl_moneyline", "nhl_moneyline_regulation")
BETTABLE = list(config.BEST_LINE_BOOKMAKERS)
# Read from model_calibration in main(): the promoted map the scorer applies.
# Both models carried a = 1, b = -0.259947 on 2026-10-01 (zero graded picks, so
# the offset pooled across the other models' records).
CAL: dict = {}
EV_FLOOR = {m: config.min_ev_for(m) for m in MODELS}
MIN_ODDS = {m: config.min_odds_for(m) for m in MODELS}
CUTS = {m: (config.MODEL_PROB_THRESHOLDS[m], config.MODEL_EDGE_THRESHOLDS[m]) for m in MODELS}
EDGE_CAP = config.MAX_EDGE_CAP
_FRAMES: dict = {}
_ARTIFACT_FILES: dict = {}       # model_id -> path, from --artifact
_ARTIFACTS: dict = {}


def artifact(model_id: str) -> dict:
    """The registry's live version, or the file named on the command line."""
    if model_id not in _ARTIFACTS:
        path = _ARTIFACT_FILES.get(model_id)
        if path:
            with open(path, "rb") as fh:
                _ARTIFACTS[model_id] = pickle.load(fh)
        else:
            _ARTIFACTS[model_id] = load_model(model_id)
    return _ARTIFACTS[model_id]


def frame(model_id: str) -> pd.DataFrame:
    """The holdout season's feature rows, built for THIS artifact's feature list."""
    if model_id not in _FRAMES:
        f = build_training_dataset(model_id, seasons=[SEASON],
                                   feature_cols=artifact(model_id)["feature_cols"])
        _FRAMES[model_id] = f[0] if isinstance(f, tuple) else f
    return _FRAMES[model_id]


def _ts(v):
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def ev(p, price):
    return p * (1 + win_per_unit(price)) - 1


def decide(model_id, p_raw, price, *, calibrated):
    """The scorer's _decide at one quote. True = BET."""
    ip = implied(price)
    p = apply_calibration(p_raw, CAL[model_id]) if calibrated else p_raw
    mp, me = CUTS[model_id]
    return (p - ip >= me and p >= mp and ev(p, price) >= EV_FLOOR[model_id]
            and price >= MIN_ODDS[model_id])


def _labels(model_id):
    """Which of the two rows is the rule production runs. A model in
    config.MODELS_ON_OWN_PROBABILITY decides on its own number (the regulation
    model since PR #876, 2026-10-03); until 2026-10-08 this script still called
    the corrected-probability row 'AS IT RUNS TODAY' for it."""
    own = model_id in config.MODELS_ON_OWN_PROBABILITY
    return (("corrected probability" + ("" if own else " (AS IT RUNS TODAY)")),
            ("model's OWN probability" + (" (AS IT RUNS TODAY)" if own else "")))


def halves(profit, dates):
    order = np.argsort(np.asarray(dates), kind="stable")
    h = len(order) // 2
    if h == 0:
        return {}
    return {"early": round(float(profit[order[:h]].mean()) * 100, 1),
            "late": round(float(profit[order[h:]].mean()) * 100, 1)}


def ml_prices(conn):
    games = conn.execute(
        "SELECT game_id, commence_time, game_date, home_score, away_score FROM games "
        "WHERE sport='NHL' AND season=%s AND home_score IS NOT NULL AND commence_time IS NOT NULL",
        (SEASON,)).fetchall()
    start = {g[0]: _ts(g[1]) for g in games}
    ids = list(start)
    rows = []
    for i in range(0, len(ids), 300):
        rows += conn.execute(
            "SELECT game_id, bookmaker, snapshot_at, home_price, away_price FROM odds "
            "WHERE game_id = ANY(%s) AND source = %s AND snapshot_type='open' AND market='h2h'",
            (ids[i:i + 300], FEED)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "snap", "hp", "ap"])
    px["snap"] = px.snap.map(_ts)
    px["hp"], px["ap"] = pd.to_numeric(px.hp), pd.to_numeric(px.ap)
    px = px.dropna(subset=["hp", "ap"])
    px = px[[s <= start[g] for g, s in zip(px.game_id, px.snap)]]
    px = px.sort_values(["game_id", "book", "snap"])
    first = px.groupby(["game_id", "book"], sort=False).first().reset_index()
    last = px.groupby(["game_id", "book"], sort=False).last().reset_index()
    out = {}
    for gid, g in first.groupby("game_id"):
        d = {"game_id": gid}
        dk = g[g.book == "draftkings"]
        if len(dk):
            d["dk_home"], d["dk_away"] = float(dk.hp.iloc[0]), float(dk.ap.iloc[0])
        pin = g[g.book == "pinnacle"]
        if len(pin):
            d["pin_open_home"] = novig(float(pin.hp.iloc[0]), float(pin.ap.iloc[0]))
        soft = g[g.book.isin(BETTABLE)]
        if len(soft):
            ih, ia = soft.hp.idxmax(), soft.ap.idxmax()
            d["best_home"], d["best_home_book"] = float(soft.hp.loc[ih]), soft.book.loc[ih]
            d["best_away"], d["best_away_book"] = float(soft.ap.loc[ia]), soft.book.loc[ia]
        out[gid] = d
    for gid, g in last[last.book == "pinnacle"].groupby("game_id"):
        out.setdefault(gid, {"game_id": gid})["pin_close_home"] = novig(float(g.hp.iloc[0]), float(g.ap.iloc[0]))
    gm = pd.DataFrame(games, columns=["game_id", "commence", "gdate", "hs", "as_"])
    gm["hs"], gm["as_"] = pd.to_numeric(gm.hs), pd.to_numeric(gm.as_)
    return gm.merge(pd.DataFrame(out.values()), on="game_id", how="left")


def moneyline(conn):
    mid = "nhl_moneyline"
    art = artifact(mid)
    f = frame(mid).copy()
    f["p"] = art["model"].predict_proba(f[art["feature_cols"]].values.astype(float))[:, 1]
    df = f[["game_id", "p", "is_early_season"]].merge(ml_prices(conn), on="game_id", how="inner")
    df = df.dropna(subset=["dk_home", "dk_away"])
    y = (df.hs > df.as_).astype(int).values
    nv = np.array([novig(h, a) for h, a in zip(df.dk_home, df.dk_away)])
    eps = 1e-9
    ll = lambda p: float(-np.mean(y * np.log(np.clip(p, eps, 1)) + (1 - y) * np.log(np.clip(1 - p, eps, 1))))
    from sklearn.metrics import roc_auc_score
    print(f"\n===== nhl_moneyline {art['version']} on 2025-26: {len(df):,} games with a DraftKings pre-game price "
          f"({int(df.pin_close_home.notna().sum()):,} with a Pinnacle close) =====")
    print(f"log loss: model {ll(df.p.values):.4f} | DraftKings no-vig {ll(nv):.4f} | home rate {ll(np.full(len(y), y.mean())):.4f}"
          f"   AUC: model {roc_auc_score(y, df.p):.4f} | DraftKings {roc_auc_score(y, nv):.4f}")
    q = df.p.quantile([0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99]).round(3).to_dict()
    print(f"model home-win probability quantiles: {q}; share >= 0.70: {float((df.p >= 0.70).mean()):.3f}; "
          f"share within 0.485..0.515: {float(df.p.between(0.485, 0.515).mean()):.3f}; "
          f"share within 0.435..0.565 (the band the correction flips): {float(df.p.between(0.435, 0.565).mean()):.3f}")

    def bets(rule):
        """rule(p_side, price) -> bool. One row per BET side."""
        rows = []
        for r in df.itertuples():
            for side, p, dk, best in (("home", r.p, r.dk_home, getattr(r, "best_home", np.nan)),
                                      ("away", 1 - r.p, r.dk_away, getattr(r, "best_away", np.nan))):
                edge_dk = p - implied(dk)
                if abs(edge_dk) > EDGE_CAP:
                    continue                                    # the scorer writes no row at all
                yield_ = {"game_id": r.game_id, "gdate": r.gdate, "side": side, "p": p,
                          "won": (r.hs > r.as_) if side == "home" else (r.as_ > r.hs),
                          "pin_open": r.pin_open_home if side == "home" else 1 - r.pin_open_home,
                          "pin_close": r.pin_close_home if side == "home" else 1 - r.pin_close_home,
                          "dk_nv": novig(r.dk_home, r.dk_away) if side == "home" else novig(r.dk_away, r.dk_home)}
                if rule(p, dk):
                    rows.append({**yield_, "price": dk, "at": "dk"})
                if not np.isnan(best) and rule(p, best):
                    rows.append({**yield_, "price": best, "at": "best"})
        b = pd.DataFrame(rows)
        if b.empty:
            return b
        b["profit"] = np.where(b.won, b.price.map(win_per_unit), -1.0)
        b["clv"] = b.pin_close - b.pin_open          # round three's measurement, same book both ends
        return b

    def line(name, b, at):
        s = b[b["at"] == at] if len(b) else b
        if len(s) < 20:
            return {"rule": name, "priced at": at, "bets": len(s)}
        return {"rule": name, "priced at": at, **summarise(s.profit.values, s.clv.values),
                **halves(s.profit.values, s.gdate.values),
                "dog share": round(float((s.price > 0).mean()), 2),
                "avg p": round(float(s.p.mean()), 3), "win%": round(float(s.won.mean()) * 100, 1)}

    rows = []
    live = bets(lambda p, pr: decide(mid, p, pr, calibrated=True))
    raw = bets(lambda p, pr: decide(mid, p, pr, calibrated=False))
    tag_cal, tag_raw = _labels(mid)
    for at in ("dk", "best"):
        rows.append(line(tag_cal, live, at))
    for at in ("dk", "best"):
        rows.append(line(tag_raw, raw, at))
    print("\n### The production rule on the holdout season\n")
    print(pd.DataFrame(rows).to_string(index=False))
    if len(live):
        s = live[live["at"] == "dk"]
        flip = s[s.p < 0.5]
        print(f"\nof the {len(s)} as-it-runs bets at DraftKings: {len(flip)} are on a side the model itself has under 50% "
              f"({summarise(flip.profit.values) if len(flip) else {}}); "
              f"{len(s) - len(flip)} on a side it has at 50%+ ({summarise(s[s.p >= 0.5].profit.values) if len(s) - len(flip) else {}})")

    # the neighbourhood: raw edge vs DraftKings' implied (vig in, as the scorer measures it), no prob floor
    rows = []
    for e in (0.02, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15):
        b = bets(lambda p, pr, e=e: p - implied(pr) >= e)
        rows.append({"edge>=": e, **{k: v for k, v in line("", b, "dk").items() if k not in ("rule", "priced at")}})
    print("\n### Neighbourhood: bet any side whose raw model probability beats DraftKings' implied by the cut (no other gate)\n")
    print(pd.DataFrame(rows).to_string(index=False))
    rows = []
    for mp in (0.50, 0.55, 0.60, 0.65, 0.70):
        for e in (0.03, 0.05, 0.08):
            b = bets(lambda p, pr, e=e, mp=mp: p - implied(pr) >= e and p >= mp)
            rows.append({"prob>=": mp, "edge>=": e,
                         **{k: v for k, v in line("", b, "dk").items() if k not in ("rule", "priced at")}})
    print("\n### Probability floor x edge, raw probability, at DraftKings\n")
    print(pd.DataFrame(rows).to_string(index=False))
    # blind baselines on the same games
    rows = []
    for nm, fn in (("always home", lambda r: ("home", r.dk_home)), ("always away", lambda r: ("away", r.dk_away)),
                   ("always favourite", lambda r: ("home", r.dk_home) if r.dk_home < r.dk_away else ("away", r.dk_away)),
                   ("always underdog", lambda r: ("home", r.dk_home) if r.dk_home > r.dk_away else ("away", r.dk_away))):
        pr, clv = [], []
        for r in df.itertuples():
            side, price = fn(r)
            won = (r.hs > r.as_) if side == "home" else (r.as_ > r.hs)
            pr.append(win_per_unit(price) if won else -1.0)
            move = r.pin_close_home - r.pin_open_home
            clv.append(move if side == "home" else -move)
        rows.append({"blind": nm, **summarise(np.array(pr), np.array(clv))})
    print("\n### Blind baselines, same games, DraftKings price\n")
    print(pd.DataFrame(rows).to_string(index=False))


def regulation(conn):
    mid = "nhl_moneyline_regulation"
    art = artifact(mid)
    f = frame(mid).copy()
    P = art["model"].predict_proba(f[art["feature_cols"]].values.astype(float))
    pred = pd.DataFrame({"game_id": f.game_id.values, "away": P[:, 0], "draw": P[:, 1], "home": P[:, 2]})
    rows = conn.execute(
        "SELECT o.game_id, o.bookmaker, o.home_price, o.away_price, o.draw_price, g.game_date, "
        "g.home_score, g.away_score, g.went_to_ot FROM odds o JOIN games g ON g.game_id = o.game_id "
        "WHERE o.source = %s AND o.market = 'h2h_3way' AND g.season = %s", (PROP_SOURCE, SEASON)).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "home", "away", "draw", "gdate", "hs", "as_", "ot"])
    for c in ("home", "away", "draw", "hs", "as_", "ot"):
        px[c] = pd.to_numeric(px[c], errors="coerce")
    px = px.dropna(subset=["home", "away", "draw"]).drop_duplicates(["game_id", "book"], keep="last")
    px["result"] = np.where(px.ot == 1, "draw", np.where(px.hs > px.as_, "home", "away"))
    px = px.merge(pred, on="game_id", how="inner", suffixes=("", "_p"))
    # The query has no ORDER BY, and a sum of floats depends on its order: two
    # runs differed by 0.1 unit in the same cells until the rows were sorted.
    px = px.sort_values(["game_id", "book"]).reset_index(drop=True)
    dk = px[px.book == "draftkings"]
    y = dk.result.map({"away": 0, "draw": 1, "home": 2}).values
    Pm = dk[["away_p", "draw_p", "home_p"]].values
    imp = dk[["away", "draw", "home"]].map(implied).values
    nvp = imp / imp.sum(axis=1, keepdims=True)
    ll = lambda Q: float(-np.mean(np.log(np.clip(Q[np.arange(len(y)), y], 1e-9, 1))))
    base = np.bincount(y, minlength=3) / len(y)
    calP = np.vectorize(lambda p: apply_calibration(float(p), CAL[mid]))(Pm)
    print(f"\n===== nhl_moneyline_regulation {art['version']} on 2025-26: {len(dk):,} games with a DraftKings 3-way price =====")
    print(f"log loss: model {ll(Pm):.4f} | DraftKings no-vig {ll(nvp):.4f} | this season's own class rates {ll(np.tile(base, (len(y), 1))):.4f}")
    print(f"model mean probabilities away/draw/home: {Pm.mean(axis=0).round(3)}; actual: {base.round(3)}")
    print(f"after the correction the three probabilities sum to {calP.sum(axis=1).mean():.3f} on average "
          f"(min {calP.sum(axis=1).min():.3f}, max {calP.sum(axis=1).max():.3f}); raw they sum to {Pm.sum(axis=1).mean():.3f}")

    def bets(src, calibrated):
        out = []
        for r in src.itertuples():
            for o in ("away", "draw", "home"):
                p, price = getattr(r, f"{o}_p"), getattr(r, o)
                if decide(mid, p, price, calibrated=calibrated):
                    out.append({"game_id": r.game_id, "book": r.book, "gdate": r.gdate, "outcome": o, "p": p,
                                "price": price, "profit": win_per_unit(price) if r.result == o else -1.0})
        return pd.DataFrame(out)

    def line(name, b, best):
        if len(b) == 0:
            return {"rule": name, "bets": 0}
        if best:                                   # one bet per game-outcome at the best bettable price
            b = b[b.book.isin(BETTABLE)].sort_values("price", ascending=False).drop_duplicates(["game_id", "outcome"])
        else:
            b = b[b.book == "draftkings"]
        if len(b) < 20:
            return {"rule": name, "bets": len(b)}
        mix = b.outcome.value_counts(normalize=True).round(2).to_dict()
        return {"rule": name, **summarise(b.profit.values), **halves(b.profit.values, b.gdate.values),
                "games": b.game_id.nunique(), "avg raw p": round(float(b.p.mean()), 3),
                "home/draw/away": f"{mix.get('home', 0)}/{mix.get('draw', 0)}/{mix.get('away', 0)}"}

    live, raw = bets(px, True), bets(px, False)
    tag_cal, tag_raw = _labels(mid)
    rows = [line(f"{tag_cal} @ DraftKings", live, False),
            line(f"{tag_cal} @ best bettable book", live, True),
            line(f"{tag_raw} @ DraftKings", raw, False),
            line(f"{tag_raw} @ best bettable", raw, True)]
    print("\n### The production rule on the holdout season\n")
    print(pd.DataFrame(rows).to_string(index=False))
    rows = []
    for c in (0.0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30):
        out = []
        for r in dk.itertuples():
            for o in ("away", "draw", "home"):
                p, price = getattr(r, f"{o}_p"), getattr(r, o)
                if ev(p, price) >= c:
                    out.append({"gdate": r.gdate, "profit": win_per_unit(price) if r.result == o else -1.0})
        b = pd.DataFrame(out)
        rows.append({"raw EV>=": c, **(summarise(b.profit.values) if len(b) else {"bets": 0}),
                     **(halves(b.profit.values, b.gdate.values) if len(b) >= 20 else {})})
    print("\n### Neighbourhood: bet any outcome whose raw model EV at DraftKings clears the cut\n")
    print(pd.DataFrame(rows).to_string(index=False))
    rows = []
    for o in ("away", "draw", "home"):
        pr = np.where(dk.result == o, dk[o].map(win_per_unit), -1.0)
        rows.append({"blind": f"always {o}", **summarise(pr)})
    print("\n### Blind baselines at DraftKings\n")
    print(pd.DataFrame(rows).to_string(index=False))


def bands() -> None:
    """Claimed, corrected and realised, on every side of every holdout game."""
    art = artifact("nhl_moneyline")
    f = frame("nhl_moneyline")
    p = art["model"].predict_proba(f[art["feature_cols"]].values.astype(float))[:, 1]
    y = f.target.values.astype(int)
    side = pd.DataFrame({"p": np.r_[p, 1 - p], "won": np.r_[y, 1 - y]})
    side["cal"] = side.p.map(lambda v: apply_calibration(float(v), CAL["nhl_moneyline"]))
    side["band"] = pd.cut(side.p, [0.0, 0.40, 0.435, 0.485, 0.50, 0.515, 0.565, 0.60, 0.65, 1.0], right=False)
    t = side.groupby("band", observed=True).agg(sides=("won", "size"), model_says=("p", "mean"),
                                                corrected_says=("cal", "mean"),
                                                actually_won=("won", "mean")).round(3)
    print("\n### nhl_moneyline: what the model says, what the correction says, what happened "
          "(every side of every game)\n")
    print(t.to_string())

    mid = "nhl_moneyline_regulation"
    art = artifact(mid)
    g = frame(mid)
    P = art["model"].predict_proba(g[art["feature_cols"]].values.astype(float))
    y3 = g.target.values.astype(int)
    r = pd.DataFrame({"p": P.ravel(), "won": np.eye(3)[y3].ravel()})
    r["cal"] = r.p.map(lambda v: apply_calibration(float(v), CAL[mid]))
    floor = CUTS[mid][0]
    lifted = r[(r.p < floor) & (r.cal >= floor)]
    print(f"\n### nhl_moneyline_regulation: outcomes under the {floor:.2f} probability floor on the model's own "
          f"number that the correction lifts over it\n\n{len(lifted):,} outcomes | model says {lifted.p.mean():.3f} | "
          f"corrected says {lifted.cal.mean():.3f} | actually happened {lifted.won.mean():.3f}")


def main() -> None:
    # A function, not module-level code, so the worker's nhl_research job can
    # import and run it (tracking/job_queue._run_script_main).
    for i, a in enumerate(sys.argv):
        if a == "--artifact" and i + 1 < len(sys.argv):
            k, _, v = sys.argv[i + 1].partition("=")
            _ARTIFACT_FILES[k] = v
    c = get_connection()
    try:
        maps = load_calibrations(c)
        CAL.update({m: maps.get(m) for m in MODELS})
        print(f"promoted corrections {CAL}; cuts (prob, edge) {CUTS}; EV floors {EV_FLOOR}; "
              f"price floors {MIN_ODDS}; edge cap {EDGE_CAP}; bettable books {BETTABLE}")
        moneyline(c)
        regulation(c)
        bands()
    finally:
        c.close()


if __name__ == "__main__":
    main()
