"""
NCAAB full-game totals: the NCAAB totals model (`ncaab_total_blend`).

LIVE, real money (mike, 2026-10-30: "Yes to the totals model"; CLAUDE.md
section 2). The card that writes its picks is scripts/ncaab_total_card.py; the
frozen numbers it reads are models/saved/ncaab_total_blend_2027.json, written
by scripts/ncaab_total_blend_build.py. docs/sports/ncaab.md has the evidence.

THE MODEL, per game, as of the moment DraftKings' total is read (the QUOTE):
  1. RATINGS. A ridge refit of every team's offence, defence and tempo on this
     season's finals that had ENDED (tip + 2.5 hours) at or before the quote,
     rounded down to the hour. Each game weighs 0.5 ^ (days ago / 45). The
     preseason prior is last season's end-of-season rating, carried at 0.72
     (efficiency) and 0.9 (tempo); a team new to Division I starts at last
     season's 10th-percentile offence and 90th-percentile defence. A team with
     fewer than 10 games on this season's schedule is pooled into one "other"
     team. Possessions are the box-score estimate fga - orb + tov + 0.475 fta,
     the two teams averaged (the only count the in-season ESPN feed gives; it
     runs 0.30-0.46 a game below NCAA's play-by-play count).
       predicted total = (eff_home + eff_away) x possessions / 100
  2. RESIDUAL. A fixed linear correction on as-of shooting luck (three-point
     and free-throw percentage made and allowed) and style rates (free-throw
     rate, three-point attempt rate, offensive-rebound rate, turnover rate),
     each the season so far shrunk toward last season's league rate. Fitted on
     seasons 2012-2026 (walk-forward in the evidence).
  3. BLEND with DraftKings' total L:
       mean = L + c + beta x (model - L),   normal with sd sigma,
     c / beta / sigma fitted per phase (November; December on) on the paid
     seasons 2021-2026, on the model's as-of predictions at DraftKings' first
     stored total.
  4. PRICE at DraftKings' own two prices on that total: P(win | no push) on
     whole points, minus the price's implied probability. Bet the better side
     when that edge is above 0.04 (config.MODEL_EDGE_THRESHOLDS).
  5. BOTH TEAMS 10+ GAMES that ended before the quote (CLAUDE.md section 3).
     Under this rule the model has never bet in November.

THE EVIDENCE (graded exactly as it runs live, scratch chain of 2026-10-30,
docs/sports/ncaab.md): cut 0.04, both teams 10+ games, DraftKings' first
stored total, stake_for. 2021-2025: 1,094 bets, 606-475-13, +87.48 units,
+7.32%, date-resampled 95% interval [2.0, 12.7], 5 of 5 seasons positive,
close EV +0.27% against Pinnacle's no-vig close. 2025-26 (never used to
choose): 349 bets, +26.76 units, +7.03%. 92% of the 2021-2025 bets are overs;
prices -120 to +102.

THE PROBABILITY (what model_probability holds): P(win | no push) on the bet
side, the number the 0.04 cut was measured on. decision_edge = that minus
DraftKings' implied probability, so the publishers' 0.04 edge filter agrees
with the card exactly. The model decides on its own number
(config.MODELS_ON_OWN_PROBABILITY): it has no record to fit a map on.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

MODEL_ID = "ncaab_total_blend"
SPORT = "NCAAB"
MARKET = "totals"
BOOK = "draftkings"

ROOT = Path(__file__).resolve().parent.parent
ARTIFACT_PATH = "models/saved/ncaab_total_blend_2027.json"
ARTIFACT_KIND = "ncaab_total_blend"

OTHER = -1                       # the pooled team (fewer than 10 scheduled games)
END_H = 2.5                      # a game has ended this long after its tip
K_FTA = 0.475                    # possessions = fga - orb + tov + K_FTA x fta
POSS_RANGE = (40.0, 110.0)       # a contest estimate outside it is not used
MIN_GAMES = 10                   # CLAUDE.md section 3
SCHED_MIN = 10                   # scheduled games below which a team is pooled
PLAY_BY_PLAY_SOURCE = "sportsdataverse_ncaa"
PHASES = ("Nov", "Dec+")
STAGE2_COLS = ("luck3_def", "luck3_off", "luckft_def", "luckft_off",
               "ftr_sum", "par3_sum", "orb_sum", "tov_sum")
BOX_STATS = ("pts", "d_pts", "fga", "fgm", "tpa", "tpm", "fta", "ftm", "orb", "drb", "tov")
_HOUR_NS = 3600 * 10 ** 9
_EPOCH = pd.Timestamp("2000-01-01")

# The decision hours, UTC (the bought snapshots the evidence used): 22:00 the
# day before the game's Eastern date, then 15:00 on the game's date and every
# hour after it until tip.
EVE_HOUR_UTC = 22
DAY_HOUR_UTC = 15


# ── small helpers ──────────────────────────────────────────────────────────────

def phase_of(game_date) -> str:
    """'Nov' for a November game date, else 'Dec+'."""
    return "Nov" if pd.Timestamp(game_date).month == 11 else "Dec+"


def day_number(game_date) -> int:
    return int((pd.Timestamp(str(game_date)[:10]) - _EPOCH).days)


def to_ns(ts) -> int | None:
    """An aware timestamp (or ISO text) as UTC nanoseconds; None when absent."""
    if ts is None or (isinstance(ts, float) and math.isnan(ts)):
        return None
    t = pd.Timestamp(ts)
    if pd.isna(t):
        return None
    t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
    return int(t.as_unit("ns").value)


def floor_hour_ns(ns: int) -> int:
    return (int(ns) // _HOUR_NS) * _HOUR_NS


def decision_hour(game_date, tip: datetime, hour: datetime) -> bool:
    """Is `hour` (a whole UTC hour) one of this game's decision hours?

    22:00Z on the day before its Eastern date; else 15:00Z on its date and
    every hour after it, before tip. A game not decided at one (no DraftKings
    total, a box score still to land) waits for the next."""
    d = pd.Timestamp(str(game_date)[:10]).date()
    h = hour.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    eve = datetime.combine(d - timedelta(days=1), time(EVE_HOUR_UTC), tzinfo=timezone.utc)
    if h == eve:
        return True
    day = datetime.combine(d, time(DAY_HOUR_UTC), tzinfo=timezone.utc)
    return day <= h < tip.astimezone(timezone.utc)


# ── box scores ─────────────────────────────────────────────────────────────────

def dedupe_box(box: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team). The same game can be stored twice: NCAA's
    play-by-play row (source sportsdataverse_ncaa) and the in-season ESPN feed.
    The key is ESPN's game id when the row has one, else its contest id; the
    play-by-play row wins."""
    b = box.copy()
    eg = pd.to_numeric(b.get("espn_game_id"), errors="coerce") if "espn_game_id" in b else pd.Series(np.nan, index=b.index)
    b["_key"] = np.where(eg.notna(), "espn:" + eg.fillna(0).astype("int64").astype(str),
                         "contest:" + b["contest_id"].astype(str))
    b["_pref"] = (b["source"] != PLAY_BY_PLAY_SOURCE).astype(int)
    b = b.sort_values(["_key", "team_espn_id", "_pref"], kind="stable")
    b = b.drop_duplicates(["_key", "team_espn_id"], keep="first")
    return b.drop(columns=["_pref"])


def team_possessions(row_like) -> pd.Series:
    """fga - orb + tov + 0.475 fta for each row."""
    return (row_like["fga"] - row_like["orb"] + row_like["tov"] + K_FTA * row_like["fta"])


def game_possessions(box: pd.DataFrame) -> pd.Series:
    """Possessions per game_id: the two teams' estimates averaged, None
    outside POSS_RANGE. `box` is deduped and carries game_id."""
    b = box[box["game_id"].notna()]
    est = team_possessions(b).groupby(b["game_id"]).mean()
    return est.where((est > POSS_RANGE[0]) & (est < POSS_RANGE[1]))


# ── ratings ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Params:
    K: float = 9.0
    KT: float = 3.0
    half_life: float = 45.0
    a: float = 0.72
    b: float = 0.0
    r_tempo: float = 0.9
    K_h: float = 300.0
    htp_K: float = 300.0

    @classmethod
    def from_dict(cls, d: dict) -> "Params":
        return cls(**{k: float(d[k]) for k in cls.__dataclass_fields__ if k in d})


@dataclass
class EndState:
    """A season's final ratings: the next season's prior."""
    teams: dict                  # team id (int, OTHER = -1) -> (O, D, T)
    mu: float
    h: float
    tmu: float
    htp: float

    def to_json(self) -> dict:
        return {"mu": self.mu, "h": self.h, "tmu": self.tmu, "htp": self.htp,
                "teams": {str(int(t)): [round(float(v), 6) for v in ods]
                          for t, ods in sorted(self.teams.items())}}

    @classmethod
    def from_json(cls, d: dict) -> "EndState":
        return cls(teams={int(t): tuple(float(x) for x in v) for t, v in d["teams"].items()},
                   mu=float(d["mu"]), h=float(d["h"]), tmu=float(d["tmu"]), htp=float(d["htp"]))


def pooled_ids(ids: pd.Series, n_sched: pd.Series) -> np.ndarray:
    """A team's own id when it has >= SCHED_MIN games on its season's
    schedule (n_sched, the same row's count), else OTHER; a missing id is
    OTHER too."""
    out = []
    for t, n in zip(ids, n_sched):
        if t is None or (isinstance(t, float) and math.isnan(t)) or pd.isna(t):
            out.append(OTHER)
            continue
        out.append(int(t) if (pd.notna(n) and int(n) >= SCHED_MIN) else OTHER)
    return np.array(out, dtype=int)


class SeasonRatings:
    """One season's ridge system: efficiency (offence, defence, mu, home) and
    tempo (team tempo, tmu, home on possessions), with the prior as the ridge
    centre. Games are added in any order; solve() weighs each by
    0.5 ^ ((target day - game day) / half_life), exactly as ratings2.run's
    growing weights times its solve-time scale."""

    def __init__(self, teams, prior: EndState | None, params: Params, t0: int):
        self.p = params
        self.teams = sorted(int(t) for t in teams)
        self.ix = {t: i for i, t in enumerate(self.teams)}
        nt = self.nt = len(self.teams)
        self.np_ = 2 * nt + 2            # O, D, mu, h
        self.nq = nt + 2                 # T, tmu, htp
        self.t0 = float(t0)
        self.lnw = math.log(0.5) / params.half_life if params.half_life else 0.0
        self.A = np.zeros((self.np_, self.np_)); self.rhs = np.zeros(self.np_)
        self.At = np.zeros((self.nq, self.nq)); self.rht = np.zeros(self.nq)
        self.ng: dict[int, int] = {}
        self._prior(prior)

    def _prior(self, pe: EndState | None) -> None:
        nt, p = self.nt, self.p
        bp = np.zeros(self.np_); tp = np.zeros(self.nq)
        lam = np.zeros(self.np_); lamt = np.zeros(self.nq)
        ihtp = nt + 1
        if pe is None:
            bp[2 * nt] = 100.0; tp[nt] = 68.0; bp[2 * nt + 1] = 1.5
            lam[:2 * nt] = p.K; lam[2 * nt] = 1e-3; lam[2 * nt + 1] = 1e-3
            lamt[:nt] = p.KT; lamt[nt] = 1e-3
            tp[ihtp] = 0.0; lamt[ihtp] = 1e-3
        else:
            vals = [v for t, v in pe.teams.items() if t != OTHER]
            newO = float(np.percentile([v[0] for v in vals], 10))
            newD = float(np.percentile([v[1] for v in vals], 90))
            for t in self.teams:
                i = self.ix[t]
                if t in pe.teams:
                    O0, D0, T0 = pe.teams[t]
                    if t == OTHER:
                        r = 1.0; rT = 1.0
                    else:
                        # b x returning share is 0 live (b = 0): no roster input.
                        r = float(np.clip(p.a + p.b * 0.5, 0.0, 1.0)); rT = p.r_tempo
                    bp[i] = r * O0; bp[nt + i] = r * D0; tp[i] = rT * T0
                else:
                    bp[i] = newO; bp[nt + i] = newD; tp[i] = 0.0
            bp[2 * nt] = pe.mu; bp[2 * nt + 1] = pe.h; tp[nt] = pe.tmu
            lam[:2 * nt] = p.K; lam[2 * nt] = 5.0; lam[2 * nt + 1] = p.K_h
            lamt[:nt] = p.KT; lamt[nt] = 5.0
            tp[ihtp] = pe.htp; lamt[ihtp] = p.htp_K
        self.bp, self.tp, self.lam, self.lamt = bp, tp, lam, lamt

    def add(self, hid, aid, rh, ra, loc, dn, poss, hs, asc) -> None:
        """Add games: pooled ids (hid/aid), real ids (rh/ra, for the 10-game
        count), location (1 home court, 0 neutral), day number, possessions
        (NaN = no box), scores."""
        hid = np.asarray(hid, int); aid = np.asarray(aid, int)
        for x in list(rh) + list(ra):
            if x is None or (isinstance(x, float) and math.isnan(x)):
                continue
            self.ng[int(x)] = self.ng.get(int(x), 0) + 1
        poss = np.asarray(poss, float)
        k = np.where(np.isfinite(poss) & (poss > 0))[0]
        if not len(k):
            return
        nt = self.nt
        dn = np.asarray(dn, float)[k]
        w = np.exp(-self.lnw * (dn - self.t0)) if self.p.half_life else np.ones(len(k))
        i = np.array([self.ix[t] for t in hid[k]]); j = np.array([self.ix[t] for t in aid[k]])
        l = np.asarray(loc, float)[k]
        n = len(k)
        cols = np.concatenate([np.stack([i, nt + j, np.full(n, 2 * nt), np.full(n, 2 * nt + 1)], 1),
                               np.stack([j, nt + i, np.full(n, 2 * nt), np.full(n, 2 * nt + 1)], 1)])
        cv = np.concatenate([np.stack([np.ones(n), np.ones(n), np.ones(n), l], 1),
                             np.stack([np.ones(n), np.ones(n), np.ones(n), -l], 1)])
        ww = np.concatenate([w, w])
        pk = poss[k]
        y = np.concatenate([100 * np.asarray(hs, float)[k] / pk, 100 * np.asarray(asc, float)[k] / pk])
        m = cols.shape[1]
        for u in range(m):
            np.add.at(self.rhs, cols[:, u], ww * cv[:, u] * y)
            for v in range(m):
                np.add.at(self.A, (cols[:, u], cols[:, v]), ww * cv[:, u] * cv[:, v])
        idt = np.stack([i, j, np.full(n, nt), np.full(n, nt + 1)], 1)
        ct = np.column_stack([np.ones((n, 3)), l])
        for u in range(4):
            np.add.at(self.rht, idt[:, u], w * ct[:, u] * pk)
            for v in range(4):
                np.add.at(self.At, (idt[:, u], idt[:, v]), w * ct[:, u] * ct[:, v])

    def solve(self, D: float):
        from scipy.linalg import cho_factor, cho_solve
        sc = math.exp(self.lnw * (D - self.t0)) if self.p.half_life else 1.0
        beta = cho_solve(cho_factor(self.A * sc + np.diag(self.lam)), self.rhs * sc + self.lam * self.bp)
        tau = cho_solve(cho_factor(self.At * sc + np.diag(self.lamt)), self.rht * sc + self.lamt * self.tp)
        return beta, tau

    def predict(self, beta, tau, hid, aid, loc):
        """(total, possessions) for games given pooled ids and location."""
        nt = self.nt
        i = np.array([self.ix[int(t)] for t in hid]); j = np.array([self.ix[int(t)] for t in aid])
        l = np.asarray(loc, float)
        O = beta[:nt]; D = beta[nt:2 * nt]; mu = beta[2 * nt]; h = beta[2 * nt + 1]
        T = tau[:nt]; tmu = tau[nt]; htp = tau[nt + 1]
        eh = mu + O[i] + D[j] + h * l
        ea = mu + O[j] + D[i] - h * l
        pp = tmu + T[i] + T[j] + htp * l
        return (eh + ea) * pp / 100.0, pp

    def end_state(self, beta, tau) -> EndState:
        nt = self.nt
        return EndState(teams={t: (float(beta[self.ix[t]]), float(beta[nt + self.ix[t]]),
                                   float(tau[self.ix[t]])) for t in self.teams},
                        mu=float(beta[2 * nt]), h=float(beta[2 * nt + 1]),
                        tmu=float(tau[nt]), htp=float(tau[nt + 1]))


def season_games(games: pd.DataFrame) -> pd.DataFrame:
    """Normalise a season's games for the ratings: pooled ids, location, day
    number, end time. `games` carries game_id, game_date, commence_time,
    home_espn_id, away_espn_id, neutral_site, home_score, away_score, poss,
    and n_sched_home / n_sched_away (scheduled games per team this season)."""
    g = games.copy()
    # Per row, so a frame of several seasons pools each team by its own
    # season's schedule.
    g["hid"] = pooled_ids(g["home_espn_id"], g["n_sched_home"])
    g["aid"] = pooled_ids(g["away_espn_id"], g["n_sched_away"])
    g["loc"] = np.where(pd.to_numeric(g["neutral_site"], errors="coerce").fillna(0) == 1, 0.0, 1.0)
    g["dn"] = [day_number(d) for d in g["game_date"]]
    g["end_ns"] = [end_ns_of(c, d) for c, d in zip(g["commence_time"], g["game_date"])]
    return g


def end_ns_of(commence_time, game_date) -> int:
    """tip + 2.5 h; a game with no tip is taken to have ended by 06:00Z the
    day after its date."""
    t = to_ns(commence_time)
    if t is not None:
        return t + int(END_H * _HOUR_NS)
    d = pd.Timestamp(str(game_date)[:10]) + pd.Timedelta(days=1, hours=6)
    return int(d.tz_localize("UTC").as_unit("ns").value)


def ratings_at(sg: pd.DataFrame, prior: EndState | None, params: Params,
               targets: pd.DataFrame, cut_ns: int) -> pd.DataFrame:
    """Predictions for `targets` (rows of sg) using only sg's finals that had
    ended at or before cut_ns (hour-floored by the caller). -> game_id, pt,
    pp, ng_h, ng_a, plus the solve per target date."""
    teams = sorted(set(sg["hid"]) | set(sg["aid"]))
    sr = SeasonRatings(teams, prior, params, int(sg["dn"].min()))
    done = sg[(sg["end_ns"] <= cut_ns) & sg["home_score"].notna() & sg["away_score"].notna()]
    sr.add(done["hid"], done["aid"], done["home_espn_id"], done["away_espn_id"], done["loc"],
           done["dn"], done["poss"], done["home_score"], done["away_score"])
    rows = []
    for D, grp in targets.groupby("dn"):
        beta, tau = sr.solve(float(D))
        pt, pp = sr.predict(beta, tau, grp["hid"], grp["aid"], grp["loc"])
        for gid, h, a, x, y in zip(grp["game_id"], grp["home_espn_id"], grp["away_espn_id"], pt, pp):
            rows.append({"game_id": gid, "pt_s1": float(x), "pp": float(y),
                         "ng_h": sr.ng.get(int(h), 0) if pd.notna(h) else 0,
                         "ng_a": sr.ng.get(int(a), 0) if pd.notna(a) else 0})
    return pd.DataFrame(rows)


def season_pass(sg: pd.DataFrame, prior: EndState | None, params: Params,
                cut: dict | None = None):
    """A whole season as the evidence ran it (ratings2.run, one season).

    Games in `cut` (game_id -> UTC ns of DraftKings' first stored total) are
    predicted from finals that ended at or before that time, rounded down to
    the hour (the strict rule); every other game from every final dated
    before its date. -> (predictions frame, end-of-season state)."""
    cut = cut or {}
    sg = sg.sort_values(["dn", "game_id"], kind="stable").reset_index(drop=True)
    teams = sorted(set(sg["hid"]) | set(sg["aid"]))
    t0 = int(sg["dn"].min())
    pred = np.full((len(sg), 2), np.nan); ngh = np.zeros(len(sg)); nga = np.zeros(len(sg))
    rh = sg["home_espn_id"].values; ra = sg["away_espn_id"].values

    def _ng(sr, sel):
        ngh[sel] = [sr.ng.get(int(x), 0) if pd.notna(x) else 0 for x in rh[sel]]
        nga[sel] = [sr.ng.get(int(x), 0) if pd.notna(x) else 0 for x in ra[sel]]

    def _add(sr, idx):
        x = sg.iloc[idx]
        sr.add(x["hid"], x["aid"], x["home_espn_id"], x["away_espn_id"], x["loc"], x["dn"],
               x["poss"], x["home_score"], x["away_score"])

    # (i) the date rule, every game
    sr = SeasonRatings(teams, prior, params, t0)
    dn = sg["dn"].values
    for D in np.unique(dn):
        sel = np.where(dn == D)[0]
        beta, tau = sr.solve(float(D))
        pt, pp = sr.predict(beta, tau, sg["hid"].values[sel], sg["aid"].values[sel], sg["loc"].values[sel])
        pred[sel, 0] = pt; pred[sel, 1] = pp
        _ng(sr, sel)
        _add(sr, sel)
    beta, tau = sr.solve(float(dn.max() + 1))
    end = sr.end_state(beta, tau)
    # (ii) the strict end-time rule for games that carry a quote time
    cvec = np.array([cut.get(g, -1) for g in sg["game_id"].values], dtype=np.int64)
    has = np.where(cvec > 0)[0]
    strict = np.zeros(len(sg), dtype=bool)
    if len(has):
        endns = sg["end_ns"].values.astype(np.int64)
        order = np.argsort(endns, kind="stable")
        sr = SeasonRatings(teams, prior, params, t0)
        ptr = 0
        keys = pd.DataFrame({"k": has, "c": (cvec[has] // _HOUR_NS) * _HOUR_NS, "D": dn[has]}).sort_values(["c", "D"])
        for (cc, D), grp in keys.groupby(["c", "D"], sort=True):
            nxt = ptr
            while nxt < len(order) and endns[order[nxt]] <= cc:
                nxt += 1
            if nxt > ptr:
                _add(sr, order[ptr:nxt]); ptr = nxt
            beta, tau = sr.solve(float(D))
            sel = grp["k"].values
            pt, pp = sr.predict(beta, tau, sg["hid"].values[sel], sg["aid"].values[sel], sg["loc"].values[sel])
            pred[sel, 0] = pt; pred[sel, 1] = pp
            _ng(sr, sel)
        strict[has] = True
    out = sg[["game_id", "season", "game_date", "home_espn_id", "away_espn_id"]].copy()
    out["pt_s1"] = pred[:, 0]; out["pp"] = pred[:, 1]
    out["ng_h"] = ngh; out["ng_a"] = nga; out["strict"] = strict
    return out, end


# ── shooting luck and style rates (as of the quote) ────────────────────────────

_PAIR_SUMS = ("fga", "tpa", "tpm", "fta", "ftm", "orb", "tov", "poss",
              "x_fga", "x_tpa", "x_tpm", "x_fta", "x_ftm", "x_drb", "x_orb", "drb", "x_tov", "x_poss")


def box_pairs(box: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with the team's own box, its opponent's (x_*),
    the game's possessions (both sides' estimate averaged) and end_ns.
    `box` is deduped and carries game_id (may be None), _key, season,
    team_espn_id and end_ns."""
    b = box.copy()
    b["poss"] = team_possessions(b).groupby(b["_key"]).transform("mean")
    keep = ["_key", "team_espn_id", "fga", "tpa", "tpm", "fta", "ftm", "orb", "drb", "tov", "poss"]
    # The opponent side keeps rows with no ESPN team id (a non-Division I
    # opponent): the team's game still counts, as it did in the evidence.
    opp = b[keep].rename(columns={c: "x_" + c for c in keep if c != "_key"})
    t = b[b["team_espn_id"].notna()].merge(opp, on="_key")
    t = t[(t["team_espn_id"] != t["x_team_espn_id"]) | t["x_team_espn_id"].isna()]
    t = t.drop_duplicates(["_key", "team_espn_id"])
    return t


def league_rates(pairs: pd.DataFrame) -> dict:
    """A season's league rates from its pairs: the next season's reference."""
    s = pairs[["tpm", "tpa", "ftm", "fta", "fga", "orb", "x_drb", "tov", "poss"]].sum()
    return {"p3": float(s.tpm / s.tpa), "ft": float(s.ftm / s.fta), "ftr": float(s.fta / s.fga),
            "par3": float(s.tpa / s.fga), "orbr": float(s.orb / (s.orb + s.x_drb)),
            "tovr": float(s.tov / s.poss)}


def _team_rates(z: pd.DataFrame, rf: dict) -> pd.DataFrame:
    f = pd.DataFrame(index=z.index)
    f["o3p"] = (z.tpm + 100 * rf["p3"]) / (z.tpa + 100) - rf["p3"]
    f["d3p"] = (z.x_tpm + 100 * rf["p3"]) / (z.x_tpa + 100) - rf["p3"]
    f["oft"] = (z.ftm + 50 * rf["ft"]) / (z.fta + 50) - rf["ft"]
    f["dft"] = (z.x_ftm + 50 * rf["ft"]) / (z.x_fta + 50) - rf["ft"]
    f["oftr"] = (z.fta + 200 * rf["ftr"]) / (z.fga + 200) - rf["ftr"]
    f["dftr"] = (z.x_fta + 200 * rf["ftr"]) / (z.x_fga + 200) - rf["ftr"]
    f["o3r"] = (z.tpa + 200 * rf["par3"]) / (z.fga + 200) - rf["par3"]
    f["d3r"] = (z.x_tpa + 200 * rf["par3"]) / (z.x_fga + 200) - rf["par3"]
    f["oorb"] = (z.orb + 50 * rf["orbr"]) / (z.orb + z.x_drb + 50) - rf["orbr"]
    f["dorb"] = (z.x_orb + 50 * rf["orbr"]) / (z.x_orb + z.drb + 50) - rf["orbr"]
    f["otov"] = (z.tov + 100 * rf["tovr"]) / (z.poss + 100) - rf["tovr"]
    f["dtov"] = (z.x_tov + 100 * rf["tovr"]) / (z.x_poss + 100) - rf["tovr"]
    return f


def style_features(pairs: pd.DataFrame, queries: pd.DataFrame, ref_by_season: dict) -> pd.DataFrame:
    """The eight stage-2 inputs for each query (game_id, season,
    home_espn_id, away_espn_id, cut_ns): each team's season-to-date sums over
    games that ENDED at or before cut_ns, shrunk to the reference (last
    season's league rate), offence plus the opponent's defence."""
    sums = list(_PAIR_SUMS)
    t = pairs.sort_values(["season", "team_espn_id", "end_ns"], kind="stable")
    cs = t.groupby(["season", "team_espn_id"])[sums].cumsum()
    cs[["season", "team_espn_id", "end_ns"]] = t[["season", "team_espn_id", "end_ns"]]
    cs = cs.astype({"season": "int64", "team_espn_id": float, "end_ns": "int64"})
    cs = cs.sort_values("end_ns", kind="stable")
    q0 = queries.reset_index(drop=True)
    ref = pd.DataFrame([ref_by_season[int(s)] for s in q0["season"]], index=q0["game_id"])
    side = {}
    for s, col in (("h", "home_espn_id"), ("a", "away_espn_id")):
        q = q0[["game_id", "season", col, "cut_ns"]].rename(columns={col: "team_espn_id"})
        q = q.dropna(subset=["team_espn_id"])
        q = q.astype({"season": "int64", "team_espn_id": float, "cut_ns": "int64"}).sort_values("cut_ns", kind="stable")
        m = pd.merge_asof(q, cs, left_on="cut_ns", right_on="end_ns", by=["season", "team_espn_id"],
                          allow_exact_matches=True, direction="backward")
        m = m.set_index("game_id").reindex(q0["game_id"])
        side[s] = _team_rates(m[sums].fillna(0), ref)
    H, A = side["h"], side["a"]
    out = pd.DataFrame({"game_id": q0["game_id"].values})
    out["luck3_def"] = (H.d3p + A.d3p).values
    out["luck3_off"] = (H.o3p + A.o3p).values
    out["luckft_def"] = (H.dft + A.dft).values
    out["luckft_off"] = (H.oft + A.oft).values
    out["ftr_sum"] = (H.oftr + A.dftr + A.oftr + H.dftr).values
    out["par3_sum"] = (H.o3r + A.d3r + A.o3r + H.d3r).values
    out["orb_sum"] = (H.oorb + A.dorb + A.oorb + H.dorb).values
    out["tov_sum"] = (H.otov + A.dtov + A.otov + H.dtov).values
    # a team with no id gets no inputs (the residual reads them as 0, as the
    # evidence did)
    gone = (q0["home_espn_id"].isna() | q0["away_espn_id"].isna()).values
    out.loc[gone, list(STAGE2_COLS)] = np.nan
    return out


def residual(feats: pd.DataFrame, coef) -> np.ndarray:
    """Stage 2: const + sum(coef x input), a missing input read as 0."""
    X = np.column_stack([np.ones(len(feats))] + [feats[c].fillna(0).values for c in STAGE2_COLS])
    return X @ np.asarray(coef, float)


def fit_stage2(d: pd.DataFrame) -> list[float]:
    """OLS of (total - stage-1 prediction) on the eight inputs."""
    X = np.column_stack([np.ones(len(d))] + [d[c].fillna(0).values for c in STAGE2_COLS])
    return [float(x) for x in np.linalg.lstsq(X, (d["total"] - d["pt_s1"]).values, rcond=None)[0]]


def fit_blend(d: pd.DataFrame) -> dict | None:
    """OLS of (total - L) on (model - L); sigma = residual sd (ddof 0).
    None below 300 games, as the evidence's fit refused."""
    x = d[["pt", "line", "total"]].dropna()
    if len(x) < 300:
        return None
    X = np.column_stack([np.ones(len(x)), x["pt"] - x["line"]])
    y = (x["total"] - x["line"]).values
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    return {"c": float(b[0]), "beta": float(b[1]), "sigma": float(np.std(y - X @ b)), "n": int(len(x))}


# ── pricing ────────────────────────────────────────────────────────────────────

def dec(american) -> float:
    a = float(american)
    return 1.0 + a / 100.0 if a > 0 else 1.0 + 100.0 / abs(a)


def outcome_probs(mu: float, sigma: float, line: float) -> tuple[float, float, float]:
    """(P over, P push, P under) for a normal total on whole points."""
    from scipy.stats import norm
    if abs(line - round(line)) < 1e-9:
        pw = float(norm.sf(line + 0.5, mu, sigma))
        pp = float(norm.cdf(line + 0.5, mu, sigma) - norm.cdf(line - 0.5, mu, sigma))
    else:
        pw = float(norm.sf(line, mu, sigma)); pp = 0.0
    return pw, pp, 1.0 - pw - pp


@dataclass(frozen=True)
class Priced:
    side: str            # "over" | "under"
    prob: float          # P(win | no push) on that side
    price: float         # DraftKings' price on that side
    edge: float          # prob - implied(price)
    mean: float          # the blended mean total
    sigma: float


def price(model_total: float, line: float, over_price: float, under_price: float,
          blend: dict) -> Priced:
    """Blend the model with the line, price both sides, keep the better one
    (a tie goes to the over, as the evidence's >= did)."""
    mean = line + blend["c"] + blend["beta"] * (model_total - line)
    pw, pp, pl = outcome_probs(mean, blend["sigma"], line)
    po = pw / (pw + pl); pu = pl / (pw + pl)
    eo = po - 1.0 / dec(over_price); eu = pu - 1.0 / dec(under_price)
    if eo >= eu:
        return Priced("over", po, float(over_price), eo, mean, blend["sigma"])
    return Priced("under", pu, float(under_price), eu, mean, blend["sigma"])


# ── the artifact ───────────────────────────────────────────────────────────────

def load_artifact(path: str | Path | None = None) -> dict:
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    art = json.loads(p.read_text(encoding="utf-8"))
    if art.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"{p}: not an {ARTIFACT_KIND} artifact")
    return art


# ── the live decision ──────────────────────────────────────────────────────────

DIAG_KEYS = ("games", "not_decision_hour", "already_decided", "no_dk_total", "box_pending",
             "box_missing", "below_10_games", "no_blend", "below_cut", "bets")
# Hold a game while a team's earlier game that ended before the quote has no
# final score or no box yet, for this long after it ended. A box that never
# lands is then treated as absent (the evidence also had a few games with no
# possessions), unless a team is missing more than MAX_OLD_MISSING of them.
BOX_WAIT_H = 36
MAX_OLD_MISSING = 1
# A game ESPN lists with one of these never counts and never holds.
NOT_PLAYED = {"STATUS_CANCELED", "STATUS_POSTPONED", "STATUS_FORFEIT"}


@dataclass
class Quote:
    game_id: str
    line: float
    over_price: float
    under_price: float
    quote_at: datetime          # DraftKings' own time on the row (snapshot_at)
    fetched_at: datetime        # when it was stored (created_at)
    link_over: str | None = None
    link_under: str | None = None


@dataclass
class Decision:
    game_id: str
    status: str                 # "bet" | a DIAG key
    detail: str
    quote: Quote | None = None
    cutoff: datetime | None = None
    model_total: float | None = None
    priced: Priced | None = None
    ng: tuple = (0, 0)
    extra: dict = field(default_factory=dict)


def missing_inputs(sg: pd.DataFrame, box_rows: dict, team: int, cut_ns: int) -> tuple[int, int]:
    """(recent, old): this team's season games that had ended at or before
    cut_ns and lack a final score or either side's box row; `recent` ended
    within BOX_WAIT_H of the cutoff. box_rows: game_id -> stored rows. Both
    sides are counted by row, not by team id: NCAA's row for a non-Division I
    opponent often has no ESPN id."""
    x = sg[((sg["home_espn_id"] == team) | (sg["away_espn_id"] == team)) & (sg["end_ns"] <= cut_ns)]
    x = x[~x["status"].isin(NOT_PLAYED)] if "status" in x else x
    recent = old = 0
    wait = int(BOX_WAIT_H * _HOUR_NS)
    for gid, hs, e in zip(x["game_id"], x["home_score"], x["end_ns"]):
        if pd.notna(hs) and box_rows.get(gid, 0) >= 2:
            continue
        if e > cut_ns - wait:
            recent += 1
        else:
            old += 1
    return recent, old


def decide(targets: pd.DataFrame, quotes: dict, sg: pd.DataFrame, box: pd.DataFrame,
           art: dict, cut: float) -> list[Decision]:
    """Decide each target game at its DraftKings quote.

    targets: rows of sg (the season's games, season_games() applied, with
    poss and status) to decide now. quotes: game_id -> Quote. box: the
    season's deduped box rows with game_id, _key and end_ns. Pure given its
    inputs."""
    params = Params.from_dict(art["params"])
    prior = EndState.from_json(art["end_state"])
    ref = {int(art["season"]): art["league_rates"]}
    blend = art["blend"]
    coef = art["stage2"]["coef"]
    season = int(art["season"])
    box_rows = box["game_id"].dropna().value_counts().to_dict() if len(box) else {}
    pairs = box_pairs(box) if len(box) else box.iloc[0:0]
    if len(pairs):
        pairs = pairs.assign(season=season)
    out: list[Decision] = []
    pending = []
    for r in targets.itertuples(index=False):
        q = quotes.get(r.game_id)
        if q is None:
            out.append(Decision(r.game_id, "no_dk_total", "no DraftKings total standing"))
            continue
        cut_ns = floor_hour_ns(to_ns(q.quote_at))
        held = []
        old_total = 0
        for team in (r.home_espn_id, r.away_espn_id):
            if pd.isna(team):
                continue
            rec, old = missing_inputs(sg, box_rows, int(team), cut_ns)
            if rec:
                held.append(f"{int(team)}: {rec} recent game(s) without a score or box")
            if old > MAX_OLD_MISSING:
                held.append(f"{int(team)}: {old} older game(s) without a score or box")
            old_total += old
        if held:
            status = "box_pending" if all("recent" in h for h in held) else "box_missing"
            out.append(Decision(r.game_id, status, "; ".join(held), quote=q))
            continue
        pending.append((r, q, cut_ns))
    if not pending:
        return out
    # ratings and inputs, grouped by cutoff
    rows = []
    for cut_ns in sorted({c for _, _, c in pending}):
        grp = [(r, q) for r, q, c in pending if c == cut_ns]
        tg = targets[targets["game_id"].isin([r.game_id for r, _ in grp])]
        pr = ratings_at(sg, prior, params, tg, cut_ns)
        qf = tg[["game_id", "home_espn_id", "away_espn_id"]].assign(season=season, cut_ns=cut_ns)
        if len(pairs):
            ft = style_features(pairs[pairs["end_ns"] <= cut_ns], qf, ref)
        else:
            ft = pd.DataFrame({"game_id": qf["game_id"], **{c: np.nan for c in STAGE2_COLS}})
        m = pr.merge(ft, on="game_id", how="left")
        m["rhat"] = residual(m, coef)
        m["pt"] = m["pt_s1"] + m["rhat"]
        for x in m.itertuples(index=False):
            rows.append((x, cut_ns))
    by_gid = {x.game_id: (x, c) for x, c in rows}
    for r, q, cut_ns in pending:
        x, _ = by_gid[r.game_id]
        ng = (int(x.ng_h), int(x.ng_a))
        cutoff = datetime.fromtimestamp(cut_ns / 1e9, tz=timezone.utc)
        if min(ng) < MIN_GAMES:
            out.append(Decision(r.game_id, "below_10_games", f"games played {ng[0]}/{ng[1]}",
                                quote=q, cutoff=cutoff, model_total=float(x.pt), ng=ng))
            continue
        b = blend.get(phase_of(r.game_date))
        if not b:
            out.append(Decision(r.game_id, "no_blend", f"no blend fit for {phase_of(r.game_date)}",
                                quote=q, cutoff=cutoff, model_total=float(x.pt), ng=ng))
            continue
        pz = price(float(x.pt), q.line, q.over_price, q.under_price, b)
        status = "bets" if pz.edge > cut else "below_cut"
        out.append(Decision(r.game_id, status,
                            f"{pz.side} {q.line:g} edge {pz.edge:+.4f} model {x.pt:.2f} mean {pz.mean:.2f}",
                            quote=q, cutoff=cutoff, model_total=float(x.pt), priced=pz, ng=ng,
                            extra={"pt_s1": float(x.pt_s1), "rhat": float(x.rhat), "pp": float(x.pp)}))
    return out
