"""
Build the artifact for the NFL in-play leader moneyline model
(nfl_live_leader_ml), and prove the production scorer reproduces the backtest.

    PYTHONIOENCODING=utf-8 python -m scripts.build_nfl_live_leader_artifact
    PYTHONIOENCODING=utf-8 python -m scripts.build_nfl_live_leader_artifact --seasons 2016-2025
    PYTHONIOENCODING=utf-8 python -m scripts.build_nfl_live_leader_artifact --parity
    PYTHONIOENCODING=utf-8 python -m scripts.build_nfl_live_leader_artifact --population

WHAT IT FITS. The win-probability model of scripts/nfl_edge_inplay_2025.py
(hypothesis H1, "leader ref=pbp"): one logistic regression per exact lead
4..16 on every regulation play-state with <= 600 s left,

    logit P(leader wins) ~ 1 + t + ball + ball*t + fav + dog,   t = ln(1 + secs)

The functions below are PORTED UNCHANGED from that script (play_states with
timed=False, post_ball_team, attach_games, leader_view, logit_irls, fit_wp
without its prints, check_possession); wp_design and wp_lookup are imported
from nfl_live_leader.model, which carries them verbatim, so the fit and the
live scorer build their design matrix with ONE function.

THE PRODUCTION FIT IS IN-SAMPLE FOR BOTH GRADED SEASONS. The default fit is
2016-2025. The evidence the model went live on is 2024 graded with a
2016-2023 fit and 2025 graded with a 2016-2024 fit; the shipped artifact has
seen both seasons, so it has NO out-of-sample record of its own. The closest
out-of-sample analogue is the 2016-2024 fit on 2025: 80 bets, +1.84u (+2.3%).

INPUTS (free, public). nflverse play-by-play per season and the nflverse
schedule (games.csv), read from the local research cache when present
(NFL_EDGE_CACHE, default %TEMP%/nfl_edge: pbp_<season>.parquet,
nflverse_games.parquet), else downloaded from the nflverse release. No
database, no Odds API call.

OUTPUT. models/saved/nfl_live_leader_ml_wp.json: identity, training counts,
feature definitions, the fit settings, the coefficients at FULL float64
precision (json writes repr(), which round-trips exactly), the rule, and a
golden grid (13 leads x clock 30..570 s x ball 0/1 x 3 bands) that the tests
compare to wp_lookup.

--parity rebuilds the two grading fits (2016-2023, 2016-2024), checks them
bit-for-bit against the backtest's own fit_wp, scores the cached bought
in-play snapshots (inplay_2024.parquet, inplay_2025.parquet) with the
PRODUCTION nfl_live_leader.model.decide, one bet per game at the first
qualifying snapshot, and must reproduce 2024: 87 bets / +13.79u / 0 pushes
and 2025: 80 bets / +1.84u / 1 push, bet for bet. The snapshot construction
(the state at a served snapshot, the game-over flag, the DraftKings quote) is
the 2024 study's own, imported from scripts/nfl_edge_inplay_2024.py, because
that is the construction the numbers were graded on.

PARITY IS ABOUT THE DECISION FUNCTION, NOT THE LOOP. It proves decide()
reproduces the study on the study's own states. The live loop sees different
states, so --population replays the same snapshots the way the loop would:

  - a state whose last play was a touchdown, an extra point or two-point try,
    a made field goal or a safety is refused (the loop waits for the next
    snap), and the game is tried again at its next snapshot;
  - the favourite band comes from DraftKings' last pre-kickoff spread (the
    loop's source, cached as odds_hist_2020_2025.parquet), not nflverse's
    consensus close;
  - the state lags the quote by 0, 15, 30, 45 and 60 s (ESPN posts a play
    some seconds after it ends; the quote is fresh);
  - and the SHIPPED 2016-2025 fit is compared with the grading fits.

Its lag-0 row is the population of record for this model.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nfl_live_leader import model as M  # noqa: E402
from nfl_live_leader.model import wp_design, wp_lookup  # noqa: E402

CACHE = Path(os.environ.get("NFL_EDGE_CACHE",
                            Path(os.environ.get("TEMP", "/tmp")) / "nfl_edge"))
NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
OUT = ROOT / "models" / "saved" / "nfl_live_leader_ml_wp.json"
DEFAULT_SEASONS = list(range(2016, 2026))
SEC_CENTRES = [30.0, 90.0, 150.0, 210.0, 270.0, 330.0, 390.0, 450.0, 510.0, 570.0]

# The backtest's column list (scripts/nfl_edge_inplay_2025.PBP_COLS), unchanged.
PBP_COLS = ["game_id", "season_type", "qtr", "game_seconds_remaining", "posteam", "defteam",
            "home_team", "away_team", "total_home_score", "total_away_score", "touchdown",
            "td_team", "interception", "fumble_lost", "punt_attempt", "field_goal_result",
            "fourth_down_failed", "safety", "extra_point_attempt", "two_point_attempt",
            "kickoff_attempt", "play_type", "vegas_home_wp", "vegas_home_wpa",
            "return_touchdown", "order_sequence", "home_opening_kickoff"]

# The published numbers the production scorer must reproduce (run 2 of
# scripts/nfl_edge_inplay_2024.py, H1 "leader ref=pbp secs<=600 edge>=0.02", DK).
PARITY_TARGETS = {2024: {"train": list(range(2016, 2024)), "bets": 87, "units": 13.79,
                         "pushes": 0, "states": 38325, "games": 1694},
                  2025: {"train": list(range(2016, 2025)), "bets": 80, "units": 1.84,
                         "pushes": 1, "states": 43024, "games": 1912}}
POSSESSION_AGREEMENT_PCT = 99.78
POPULATION_LAGS = (0, 15, 30, 45, 60)
# The play kinds the live loop refuses to price straight after (state.py).
_PLAY_COLS = ["touchdown", "extra_point_attempt", "two_point_attempt",
              "field_goal_result", "safety"]
_STATE_COLS = ["qtr", "secs", "home_sc", "away_sc", "home_ball"]


# ─── inputs ────────────────────────────────────────────────────────────────

def _download(url: str, dest: Path) -> None:
    import requests
    print(f"downloading {url}", flush=True)
    r = requests.get(url, timeout=600)
    r.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)


def pbp_path(season: int) -> Path:
    p = CACHE / f"pbp_{season}.parquet"
    if not p.exists():
        _download(f"{NFLVERSE}/pbp/play_by_play_{season}.parquet", p)
    return p


def load_games() -> pd.DataFrame:
    """The nflverse schedule: the cached parquet, else games.csv from the
    release. Only game_id, week, game_type, scores, result, total,
    spread_line and total_line are used (attach_games)."""
    p = CACHE / "nflverse_games.parquet"
    if p.exists():
        return pd.read_parquet(p)
    csv = CACHE / "games.csv"
    if not csv.exists():
        _download(f"{NFLVERSE}/schedules/games.csv", csv)
    return pd.read_csv(csv, low_memory=False)


# ─── ported from scripts/nfl_edge_inplay_2025.py, behaviour unchanged ────────

def post_ball_team(p: pd.DataFrame) -> np.ndarray:
    """Team with the ball after the play, from the play's own row only."""
    f = lambda c: p[c].fillna(0).values == 1                      # noqa: E731
    td = f("touchdown") & p.td_team.notna().values
    other_td = np.where(p.td_team.values == p.home_team.values, p.away_team.values,
                        p.home_team.values)
    conv = f("extra_point_attempt") | f("two_point_attempt")
    fgm = (p.field_goal_result == "made").values
    fgx = p.field_goal_result.isin(["missed", "blocked"]).values
    ko = f("kickoff_attempt")
    to = f("interception") | f("fumble_lost")
    conds = [td, conv, fgm | f("safety"), ko & f("fumble_lost"), ko,
             to | f("punt_attempt") | fgx | f("fourth_down_failed")]
    vals = [other_td, p.defteam.values, p.defteam.values, p.defteam.values,
            p.posteam.values, p.defteam.values]
    return np.select(conds, vals, default=p.posteam.values)


def play_states(seasons) -> pd.DataFrame:
    """The training rows: play_states(seasons, timed=False) of the backtest."""
    parts = []
    for s in seasons:
        p = pd.read_parquet(pbp_path(s), columns=PBP_COLS)
        p["season"] = s
        parts.append(p)
    p = pd.concat(parts, ignore_index=True)
    p = p.sort_values(["game_id", "order_sequence"], kind="stable")
    p = p[p.posteam.notna() & p.qtr.notna() & p.game_seconds_remaining.notna()].copy()
    team = post_ball_team(p)
    # last play of each quarter (in game order) -> flags; Q2's last -> 2nd-half receiver
    p["is_last_q"] = p.groupby(["game_id", "qtr"]).cumcount(ascending=False) == 0
    recv2 = np.where(p.home_opening_kickoff.fillna(0).values == 1, p.away_team.values,
                     p.home_team.values)
    team = np.where(p.is_last_q.values & (p.qtr.values == 2), recv2, team)
    p["ball_team"] = team
    p["home_ball"] = (team == p.home_team.values).astype(int)
    p["home_sc"] = p.total_home_score.astype(float)
    p["away_sc"] = p.total_away_score.astype(float)
    p["secs"] = np.where(p.is_last_q & (p.qtr <= 4), (4 - p.qtr) * 900.0,
                         p.game_seconds_remaining.astype(float))
    p["vwp_post"] = (p.vegas_home_wp + p.vegas_home_wpa.fillna(0)).clip(0, 1)
    p["nonoff_td"] = ((p.return_touchdown.fillna(0) == 1)
                      | ((p.touchdown.fillna(0) == 1) & p.td_team.notna() & (p.td_team != p.posteam))
                      | ((p.touchdown.fillna(0) == 1) & p.play_type.isin(["kickoff", "punt"])))
    return p


def check_possession(p: pd.DataFrame) -> tuple[int, float]:
    """(plays checked, % agreement): the derived post-play ball against the
    next play's posteam, excluding PAT-next rows. Unchanged, returned
    rather than printed."""
    nxt = p.groupby("game_id").posteam.shift(-1)
    nq = p.groupby("game_id").qtr.shift(-1)
    nconv = (p.groupby("game_id").extra_point_attempt.shift(-1).fillna(0) == 1) | \
            (p.groupby("game_id").two_point_attempt.shift(-1).fillna(0) == 1)
    same_half = ((p.qtr <= 2) & (nq <= 2)) | ((p.qtr >= 3) & (nq >= 3))
    m = nxt.notna() & ~nconv & (same_half | (p.is_last_q & (p.qtr == 2)))
    agree = (p.ball_team[m] == nxt[m]).mean()
    return int(m.sum()), float(100 * agree)


def attach_games(p: pd.DataFrame, g: pd.DataFrame) -> pd.DataFrame:
    gg = g[["game_id", "week", "game_type", "home_score", "away_score", "result", "total",
            "spread_line", "total_line"]]
    return p.merge(gg, on="game_id", how="inner")


def leader_view(df):
    d = df.home_sc - df.away_sc
    lead_home = d > 0
    out = pd.DataFrame(index=df.index)
    out["lead"] = d.abs()
    out["lead_home"] = lead_home
    out["ball"] = np.where(lead_home, df.home_ball, 1 - df.home_ball)
    exp_m = np.where(lead_home, df.spread_line, -df.spread_line)
    out["band"] = np.where(exp_m >= 3.5, 0, np.where(exp_m <= -3.5, 2, 1))
    return out


def logit_irls(X, y, lam=1.0, iters=100):
    """Logistic regression with fractional targets; ridge lam on the slopes."""
    b = np.zeros(X.shape[1])
    R = lam * np.eye(X.shape[1])
    R[0, 0] = 0.0
    for _ in range(iters):
        eta = np.clip(X @ b, -30, 30)
        pr = 1 / (1 + np.exp(-eta))
        W = np.clip(pr * (1 - pr), 1e-9, None)
        step = np.linalg.solve(X.T @ (W[:, None] * X) + R, X.T @ (y - pr) - R @ b)
        b = b + step
        if np.abs(step).max() < 1e-9:
            break
    return b


def fit_wp(tr: pd.DataFrame):
    """The backtest's fit_wp without its prints: (coefs, per-lead rows, the
    training frame)."""
    x = tr[(tr.qtr <= 4) & tr.spread_line.notna()].copy()
    x = x.join(leader_view(x))
    x = x[(x.lead >= 4) & (x.lead <= 16) & (x.secs <= 600)].copy()
    fin = np.where(x.lead_home, x.result, -x.result)
    x["win"] = np.where(fin > 0, 1.0, np.where(fin < 0, 0.0, 0.5))
    coefs = np.zeros((13, 6))
    rows = []
    for L in range(4, 17):
        z = x[x.lead == L]
        X = wp_design(z.secs, z.ball, z.band)
        coefs[L - 4] = logit_irls(X, z.win.values)
        rows.append({"lead": L, "states": int(len(z)), "games": int(z.game_id.nunique()),
                     "games_leader_lost": int(z[z.win == 0].game_id.nunique())})
    return coefs, rows, x


# ─── the artifact ──────────────────────────────────────────────────────────

_PORTED = (post_ball_team, play_states, check_possession, attach_games, leader_view,
           logit_irls, fit_wp, M.wp_design, M.wp_lookup)


def _fit_source_md5() -> str:
    src = "\n".join(inspect.getsource(f) for f in _PORTED)
    return hashlib.md5(src.encode("utf-8")).hexdigest()


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def golden_grid(coefs) -> dict:
    rows = []
    for L in range(M.LEAD_MIN, M.LEAD_MAX + 1):
        for ball in (0, 1):
            for band in (0, 1, 2):
                v = wp_lookup(coefs, np.full(len(SEC_CENTRES), L), np.full(len(SEC_CENTRES), ball),
                              np.full(len(SEC_CENTRES), band), np.array(SEC_CENTRES))
                rows.append({"lead": L, "ball": ball, "band": band,
                             "wp": [float(w) for w in v]})
    return {"secs": SEC_CENTRES,
            "note": "wp[i] = wp_lookup(coefs, lead, ball, band, secs[i]) at float64",
            "rows": rows}


def fit_block(seasons, g, tr=None):
    """Fit on `seasons`: (coefs, training dict)."""
    if tr is None:
        tr = attach_games(play_states(seasons), g)
    n_chk, agree = check_possession(tr)
    coefs, rows, x = fit_wp(tr)
    training = {
        "seasons": [int(s) for s in seasons],
        "season_types": sorted(str(v) for v in x.season_type.dropna().unique()),
        "game_types": sorted(str(v) for v in x.game_type.dropna().unique()),
        "source": "nflverse play_by_play_<season>.parquet + nflverse schedules games.csv "
                  "(closing spread_line, final result incl. overtime)",
        "filters": ["posteam, qtr and game_seconds_remaining non-null (real plays)",
                    "inner join to the nflverse schedule",
                    "qtr <= 4", "spread_line non-null", "lead 4-16", "secs <= 600"],
        "states": int(len(x)), "games": int(x.game_id.nunique()),
        "per_lead": rows,
        "possession_check": {"plays": n_chk, "agreement_pct": round(agree, 4),
                             "definition": "derived post-play ball vs the next play's "
                                           "posteam, excluding PAT-next rows"},
    }
    return coefs, training


def build_artifact(seasons) -> dict:
    g = load_games()
    coefs, training = fit_block(seasons, g)
    graded = {2024, 2025} & set(seasons)
    training["in_sample_note"] = (
        f"This fit includes {sorted(graded)}: the seasons the model's evidence was graded on "
        "are IN-SAMPLE for this artifact, so it has no out-of-sample record of its own. The "
        "evidence: 2024 graded with a 2016-2023 fit (87 bets, +13.79u, +15.8%), 2025 graded "
        "with a 2016-2024 fit (80 bets, +1.84u, +2.3%); pooled 167 bets +9.4% (90% CI +1.8 to "
        "+16.8, p 0.022). Marginal: it did not survive the pre-registered multiple-testing "
        "family." if graded else "Out-of-sample for 2024 and 2025.")
    now = datetime.now(timezone.utc)
    return {
        "identity": {
            "model_id": M.MODEL_ID,
            "artifact_version": now.strftime("v%Y%m%d_%H%M%S"),
            "built_at": now.isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "builder": "scripts/build_nfl_live_leader_artifact.py",
            "fit_source_md5": _fit_source_md5(),
            "backtest": "scripts/nfl_edge_inplay_2024.py + scripts/nfl_edge_inplay_2025.py, "
                        "H1 'leader ref=pbp secs<=600 edge>=0.02', venue DraftKings",
        },
        "training": training,
        "features": {
            "columns": list(M.COLUMNS),
            "definitions": {
                "const": "1",
                "t": "ln(1 + secs) (numpy log1p)",
                "secs": "game_seconds_remaining at the SNAP of the last completed play; the "
                        "last play of a quarter is set to the quarter boundary (4 - qtr) * 900",
                "ball": "1 when the leader has the ball AFTER the play (post_ball_team: TD -> "
                        "the non-scoring team; PAT/2-pt, made FG, safety -> defteam; kickoff -> "
                        "the receiver unless fumble lost; interception, fumble lost, punt, "
                        "missed/blocked FG, failed 4th down -> defteam; else posteam)",
                "ball_t": "ball * t",
                "fav": "band == 0: the leader's pregame expected margin >= +3.5",
                "dog": "band == 2: the leader's pregame expected margin <= -3.5",
                "lead": "|home score - away score| after the play; one fit per lead 4..16",
            },
            "band": {
                "training_source": "nflverse spread_line: the HOME team's expected margin, "
                                   "positive = home favoured",
                "training_formula": "leader margin = spread_line if leader home else -spread_line",
                "production_source": "DraftKings' last pre-kickoff `spreads` row in `odds` "
                                     "(spread_home = the HOME handicap, negative = home "
                                     "favoured), so spread_line = -spread_home",
                "production_formula": "leader margin = -spread_home if leader home else "
                                      "+spread_home",
                "fav_at": M.FAV_AT, "dog_at": M.DOG_AT,
                "missing_spread": "refuse (never 0)",
            },
        },
        "fit": {"method": "IRLS (logit_irls)", "start": "zeros",
                "target": "leader final result incl. overtime: win 1 / tie 0.5 / loss 0",
                "ridge": 1.0, "ridge_on": "the five slopes; intercept unpenalised",
                "max_iter": 100, "tol": 1e-9, "eta_clip": 30, "weight_floor": 1e-9,
                "per_lead": "13 independent fits, lead 4..16; not smoothed across leads"},
        "coefficients": {str(L): [float(v) for v in coefs[L - 4]] for L in range(4, 17)},
        "rule": {"period_max": M.PERIOD_MAX, "secs_max": M.SECS_MAX,
                 "lead_min": M.LEAD_MIN, "lead_max": M.LEAD_MAX, "edge_cut": M.EDGE_CUT,
                 "implied": "1 / decimal(DraftKings price of the leader), vig included",
                 "venue": "draftkings", "market": "h2h", "side": "the leader",
                 "one_bet_per_game": True, "entry": "the first qualifying evaluation",
                 "evaluation_cadence_sec": 300, "min_price": None, "max_price": None,
                 "overtime": "never priced; graded on the final incl. overtime, a tie pushes"},
        "golden_grid": golden_grid(coefs),
    }


# ─── parity ────────────────────────────────────────────────────────────────

def _grade(v, dec) -> np.ndarray:
    v = np.asarray(v, float)
    d = np.asarray(dec, float)
    return np.where(v == 1, d - 1, np.where(v == 0, -1.0, 0.0))


def parity() -> bool:
    os.environ["NFL_EDGE_CACHE"] = str(CACHE)
    from scripts import nfl_edge_inplay_2024 as B24
    from scripts import nfl_edge_inplay_2025 as B25
    from scripts.nfl_edge_lib import games as bt_games

    g = bt_games()
    tr_all = attach_games(play_states(range(2016, 2025)), g)
    ok = True
    for season, tgt in PARITY_TARGETS.items():
        tr = tr_all[tr_all.season < season]
        coefs, training = fit_block(tgt["train"], g, tr=tr)
        with redirect_stdout(io.StringIO()):
            bt_coefs = B25.fit_wp(tr)
        same_fit = bool(np.array_equal(coefs, bt_coefs))
        art = M.artifact_from_dict(json.loads(json.dumps(
            {"coefficients": {str(L): [float(v) for v in coefs[L - 4]] for L in range(4, 17)},
             "features": {"columns": list(M.COLUMNS)}, "rule": {}, "identity": {}})))

        with redirect_stdout(io.StringIO()):
            d = B24.load_inplay(season, g)
            st, _ = B24.states(season, g)
            sf = B24.snapshot_frame(d, g, st, 0)
            q = B25.venue_quotes(d, sf)
        dk = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][
            B24.KEYS + ["price_home", "price_away"]]

        # PRODUCTION PATH: decide() on every live (not game-over) snapshot that has a
        # DraftKings moneyline, in game and time order; first BET per game.
        x = sf[~sf.over.astype(bool)].merge(dk, on=B24.KEYS).sort_values(B24.KEYS)
        bets, seen = [], set()
        for r in x.itertuples(index=False):
            if r.game_id in seen:
                continue
            poss = None if pd.isna(r.home_ball) else ("home" if int(r.home_ball) == 1 else "away")
            dcs = M.decide(art, period=r.qtr, secs=r.secs, home_score=r.home_sc,
                           away_score=r.away_sc, possession=poss,
                           spread_home=(None if pd.isna(r.spread_line) else -r.spread_line),
                           home_price=r.price_home, away_price=r.price_away)
            if dcs.bet:
                seen.add(r.game_id)
                fin = r.result if dcs.side == "home" else -r.result
                v = 1.0 if fin > 0 else (0.0 if fin < 0 else 0.5)
                bets.append({"game_id": r.game_id, "snapshot_at": r.snapshot_at,
                             "side": dcs.side, "dec": dcs.decimal, "v": v, "wp": dcs.wp,
                             "edge": dcs.edge})
        b = pd.DataFrame(bets)
        pr = _grade(b.v, b.dec)
        units = round(float(pr.sum()), 2)
        pushes = int((b.v == 0.5).sum())

        # THE BACKTEST'S OWN SELECTION on the same frame, for a bet-by-bet comparison.
        _, s = B24.h1_frame(sf, bt_coefs)
        h = q[q.market == "h2h"].merge(s[B24.KEYS + ["lead_home"]], on=B24.KEYS)
        h["dec"] = np.where(h.lead_home, h.dec_h, h.dec_a)
        e = s.merge(h[h.bookmaker == "draftkings"][B24.KEYS + ["dec"]], on=B24.KEYS) \
            .sort_values(B24.KEYS)
        e["edge"] = e.wp - 1 / e.dec
        e = e[(e.secs <= 600) & (e.edge >= 0.02)].groupby("game_id", as_index=False).head(1)
        same_bets = (len(e) == len(b)
                     and list(zip(e.game_id, e.snapshot_at)) == list(zip(b.game_id, b.snapshot_at)))

        checks = {
            "fit bit-identical to the backtest's fit_wp": same_fit,
            f"training states {training['states']:,} == {tgt['states']:,}":
                training["states"] == tgt["states"],
            f"training games {training['games']:,} == {tgt['games']:,}":
                training["games"] == tgt["games"],
            f"possession agreement {training['possession_check']['agreement_pct']:.2f}% == "
            f"{POSSESSION_AGREEMENT_PCT}%":
                round(training["possession_check"]["agreement_pct"], 2) == POSSESSION_AGREEMENT_PCT,
            f"bets {len(b)} == {tgt['bets']}": len(b) == tgt["bets"],
            f"units {units:+.2f} == {tgt['units']:+.2f}": units == tgt["units"],
            f"pushes {pushes} == {tgt['pushes']}": pushes == tgt["pushes"],
            f"bet-by-bet identical to the backtest's selection ({len(e)} bets)": same_bets,
        }
        print(f"\n{season}: graded with the {tgt['train'][0]}-{tgt['train'][-1]} fit "
              f"({training['states']:,} states, {training['games']:,} games); "
              f"{len(x):,} live DraftKings snapshots scored by nfl_live_leader.model.decide")
        print(f"  {len(b)} bets, {units:+.2f}u, {pushes} push(es), ROI "
              f"{100 * pr.mean():+.1f}%, win {100 * (b.v == 1).mean():.1f}%, "
              f"mean edge {b.edge.mean():.3f}")
        for k, v in checks.items():
            print(f"  [{'PASS' if v else 'FAIL'}] {k}")
            ok &= bool(v)
    print(f"\nPARITY {'PASSED' if ok else 'FAILED'}")
    return ok


def _first_bets(x: pd.DataFrame, art, spread_home=None, eligible=None) -> pd.DataFrame:
    """One bet per game at the first snapshot decide() takes, in game and
    time order. `spread_home` overrides the band source per row; `eligible`
    False means the loop would refuse that state (the game is tried again at
    its next snapshot)."""
    bets, seen = [], set()
    for i, r in enumerate(x.itertuples(index=False)):
        if r.game_id in seen or (eligible is not None and not eligible[i]):
            continue
        poss = None if pd.isna(r.home_ball) else ("home" if int(r.home_ball) == 1 else "away")
        if spread_home is None:
            sp = None if pd.isna(r.spread_line) else -r.spread_line
        else:
            sp = None if pd.isna(spread_home[i]) else float(spread_home[i])
        dcs = M.decide(art, period=r.qtr, secs=r.secs, home_score=r.home_sc,
                       away_score=r.away_sc, possession=poss, spread_home=sp,
                       home_price=r.price_home, away_price=r.price_away)
        if dcs.bet:
            seen.add(r.game_id)
            fin = r.result if dcs.side == "home" else -r.result
            bets.append({"game_id": r.game_id, "snapshot_at": r.snapshot_at,
                         "dec": dcs.decimal, "v": 1.0 if fin > 0 else (0.0 if fin < 0 else 0.5)})
    b = pd.DataFrame(bets, columns=["game_id", "snapshot_at", "dec", "v"])
    b["pnl"] = _grade(b.v, b.dec)
    # The PUBLISHED stake (Discord, X, results_snapshots): 1u to win, risk
    # capped at 3u -- tracking.discord_notifier.stake_for, called, not copied.
    from tracking.discord_notifier import stake_for
    risk, win = [], []
    for dec in b.dec:
        american = (dec - 1) * 100 if dec >= 2 else -100 / (dec - 1)
        st = stake_for(None, american)
        risk.append(st.risk)
        win.append(st.win)
    b["risk_pub"] = risk
    b["pnl_pub"] = np.where(b.v == 1, win, np.where(b.v == 0, -b.risk_pub, 0.0))
    return b


def _summ(b: pd.DataFrame) -> str:
    roi = 100 * b.pnl.mean() if len(b) else 0.0
    return f"{len(b):3d} bets {b.pnl.sum():+7.2f}u {roi:+5.1f}%"


def _summ_pub(b: pd.DataFrame) -> str:
    """Units at the published stake, and the return on the units it risked."""
    roi = 100 * b.pnl_pub.sum() / b.risk_pub.sum() if len(b) else 0.0
    return f"{b.pnl_pub.sum():+7.2f}u on {b.risk_pub.sum():6.1f}u risked {roi:+5.1f}%"


def _dk_pregame_spread() -> pd.Series:
    """DraftKings' last pre-kickoff spread per game: the home handicap, the
    loop's band source (gameday.load_context reads the same rows from odds)."""
    oh = pd.read_parquet(CACHE / "odds_hist_2020_2025.parquet",
                         columns=["game_id", "bookmaker", "market", "point", "snapshot_at",
                                  "commence_time"])
    oh = oh[(oh.bookmaker == "draftkings") & (oh.market == "spreads")].copy()
    oh["point"] = pd.to_numeric(oh.point, errors="coerce")
    oh["snapshot_at"] = pd.to_datetime(oh.snapshot_at, utc=True)
    oh["commence_time"] = pd.to_datetime(oh.commence_time, utc=True)
    oh = oh[oh.snapshot_at <= oh.commence_time].sort_values("snapshot_at")
    return oh.groupby("game_id").tail(1).set_index("game_id").point


def population() -> bool:
    """The live loop's population on the bought 2024/2025 snapshots (module
    docstring). Prints one table; returns False if the state attachment does
    not reproduce the study's states or lag 0 without the loop's refusals
    does not reproduce parity."""
    os.environ["NFL_EDGE_CACHE"] = str(CACHE)
    from scripts import nfl_edge_inplay_2024 as B24
    from scripts import nfl_edge_inplay_2025 as B25
    from scripts.nfl_edge_lib import games as bt_games

    g = bt_games()
    dk_spread = _dk_pregame_spread()
    shipped = M.load_artifact()
    tr_all = attach_games(play_states(range(2016, 2025)), g)
    ok = True
    rows = {}
    for season, tgt in PARITY_TARGETS.items():
        coefs, _ = fit_block(tgt["train"], g, tr=tr_all[tr_all.season < season])
        art = M.artifact_from_dict(json.loads(json.dumps(
            {"coefficients": {str(L): [float(v) for v in coefs[L - 4]] for L in range(4, 17)},
             "features": {"columns": list(M.COLUMNS)}, "rule": {}, "identity": {}})))
        with redirect_stdout(io.StringIO()):
            d = B24.load_inplay(season, g)
            st, _ = B24.states(season, g)
        snaps = d[["game_id", "snapshot_at"]].drop_duplicates(B24.KEYS)
        ident = st[["game_id", "t_known"] + _STATE_COLS + _PLAY_COLS].sort_values("t_known")
        for lag in POPULATION_LAGS:
            with redirect_stdout(io.StringIO()):
                sf = B24.snapshot_frame(d, g, st, lag)
                q = B25.venue_quotes(d, sf)
            # The last play behind each snapshot's state, attached the way the
            # study attaches the state itself (known at snapshot - lag).
            xi = snaps.copy()
            xi["t_state"] = (xi.snapshot_at - pd.Timedelta(seconds=lag)) \
                .astype("datetime64[ns, UTC]")
            xi = pd.merge_asof(xi.sort_values("t_state"), ident, left_on="t_state",
                               right_on="t_known", by="game_id", direction="backward",
                               allow_exact_matches=True)
            chk = sf[B24.KEYS + _STATE_COLS].merge(xi[B24.KEYS + _STATE_COLS], on=B24.KEYS,
                                                    suffixes=("", "_x"))
            same = all((chk[c].fillna(-9) == chk[c + "_x"].fillna(-9)).all()
                       for c in _STATE_COLS)
            if not same:
                print(f"  [FAIL] {season} lag {lag}: the last-play attachment does not "
                      f"reproduce the study's states")
                ok = False
            dk = q[(q.market == "h2h") & (q.bookmaker == "draftkings")][
                B24.KEYS + ["price_home", "price_away"]]
            x = sf[~sf.over.astype(bool)].merge(xi[B24.KEYS + _PLAY_COLS], on=B24.KEYS,
                                                how="left") \
                .merge(dk, on=B24.KEYS).sort_values(B24.KEYS).reset_index(drop=True)
            flag = lambda c: x[c].fillna(0).values == 1                      # noqa: E731
            scoring = (flag("touchdown") | flag("extra_point_attempt")
                       | flag("two_point_attempt") | (x.field_goal_result == "made").values
                       | flag("safety"))
            sp = x.game_id.map(dk_spread).values
            rows[(season, lag, "study")] = _first_bets(x, art)
            rows[(season, lag, "loop")] = _first_bets(x, art, spread_home=sp, eligible=~scoring)
            if lag == 0:
                rows[(season, 0, "shipped_study")] = _first_bets(x, shipped)
                rows[(season, 0, "shipped_loop")] = _first_bets(x, shipped, spread_home=sp,
                                                                eligible=~scoring)
                gs = x.groupby("game_id").spread_line.first()
                diff = (gs + gs.index.to_series().map(dk_spread)).dropna()
                lh = (x.home_sc - x.away_sc) > 0
                m_nv = np.where(lh, x.spread_line, -x.spread_line)
                m_dk = np.where(lh, -sp, sp)
                band = lambda m: np.where(m >= 3.5, 0, np.where(m <= -3.5, 2, 1))  # noqa: E731
                inwin = ((x.qtr == 4) & (x.secs <= 600)
                         & (x.home_sc - x.away_sc).abs().between(4, 16) & ~np.isnan(sp))
                rows[(season, "band")] = (len(gs), int(gs.index.to_series().map(dk_spread)
                                                      .notna().sum()),
                                          int((diff == 0).sum()), int((diff.abs() >= 1).sum()),
                                          int((inwin & (band(m_nv) != band(m_dk))).sum()),
                                          int(inwin.sum()))
        b0 = rows[(season, 0, "study")]
        if not (len(b0) == tgt["bets"] and round(float(b0.pnl.sum()), 2) == tgt["units"]):
            print(f"  [FAIL] {season} lag 0, study states: {_summ(b0)} is not parity's "
                  f"{tgt['bets']} bets {tgt['units']:+.2f}u")
            ok = False

    seasons = list(PARITY_TARGETS)
    pooled = lambda lag, kind: pd.concat([rows[(s_, lag, kind)] for s_ in seasons])  # noqa: E731
    print("\nThe live loop's population on the bought DraftKings snapshots "
          "(grading fits; first bet per game)")
    print(f"{'state lag':>10}  {'study states, nflverse band':>30}  "
          f"{'loop refusals + DraftKings band':>32}")
    for lag in POPULATION_LAGS:
        for s_ in seasons + ["pooled"]:
            st_ = pooled(lag, "study") if s_ == "pooled" else rows[(s_, lag, "study")]
            lp_ = pooled(lag, "loop") if s_ == "pooled" else rows[(s_, lag, "loop")]
            print(f"{lag:>8} s  {str(s_):>6}  {_summ(st_):>22}  {_summ(lp_):>30}")
    print("\nAt the PUBLISHED stake (1u to win, risk capped at 3u), same bets as above")
    for lag in POPULATION_LAGS:
        for s_ in seasons + ["pooled"]:
            st_ = pooled(lag, "study") if s_ == "pooled" else rows[(s_, lag, "study")]
            lp_ = pooled(lag, "loop") if s_ == "pooled" else rows[(s_, lag, "loop")]
            print(f"{lag:>8} s  {str(s_):>6}  {_summ_pub(st_):>36}  {_summ_pub(lp_):>36}")
    print("\nThe shipped 2016-2025 fit on the same lag-0 frames (in-sample for both seasons)")
    for kind, label in (("study", "study states"), ("loop", "loop refusals + DK band")):
        for s_ in seasons:
            a_ = rows[(s_, 0, kind)]
            b_ = rows[(s_, 0, f"shipped_{kind}")]
            ka, kb = set(zip(a_.game_id, a_.snapshot_at)), set(zip(b_.game_id, b_.snapshot_at))
            print(f"  {s_} {label:>24}: grading fit {_summ(a_)} | shipped {_summ(b_)} | "
                  f"shipped keeps {len(ka & kb)}, drops {len(ka - kb)}, adds {len(kb - ka)}")
    print("\nFavourite band: DraftKings' last pre-kickoff spread vs nflverse's close")
    for s_ in seasons:
        n, have, eq, ge1, flips, inwin = rows[(s_, "band")]
        print(f"  {s_}: DraftKings spread for {have} of {n} games; equal {eq}, differ by 1+ "
              f"points {ge1}; in-window snapshot states in a different band: {flips} of {inwin}")
    print(f"\nPOPULATION {'OK' if ok else 'FAILED'}")
    return ok


def parse_seasons(s: str) -> list[int]:
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(v) for v in s.split(",")]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seasons", default="2016-2025",
                    help="training seasons, e.g. 2016-2025 or 2016,2017")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--parity", action="store_true",
                    help="rebuild the 2016-2023 / 2016-2024 fits and reproduce the backtest")
    ap.add_argument("--population", action="store_true",
                    help="replay the bought snapshots the way the live loop sees them")
    a = ap.parse_args()
    if a.parity:
        return 0 if parity() else 1
    if a.population:
        return 0 if population() else 1
    seasons = parse_seasons(a.seasons)
    art = build_artifact(seasons)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # LF on every machine: models/saved is -text, so git stores the bytes as written.
    out.write_text(json.dumps(art, indent=1) + "\n", encoding="utf-8", newline="\n")
    t = art["training"]
    print(f"wrote {out}: seasons {seasons[0]}-{seasons[-1]}, {t['states']:,} states, "
          f"{t['games']:,} games, possession agreement {t['possession_check']['agreement_pct']:.2f}%")
    for r in t["per_lead"]:
        c = art["coefficients"][str(r["lead"])]
        print(f"  lead {r['lead']:2d}: {r['states']:5d} states, {r['games']:4d} games, "
              f"{r['games_leader_lost']:3d} lost  coefs " + " ".join(f"{v:+.3f}" for v in c))
    return 0


if __name__ == "__main__":
    sys.exit(main())
