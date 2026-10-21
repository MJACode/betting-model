"""
The late-game leader win-probability model and its betting rule. Pure: no
network, no database, no clock.

THE MODEL (fitted by scripts/build_nfl_live_leader_artifact.py, stored in
models/saved/nfl_live_leader_ml_wp.json). Thirteen logistic regressions, one
per exact lead L = 4..16:

    logit P(leader wins) = b0 + b1*t + b2*ball + b3*ball*t + b4*fav + b5*dog
    t    = ln(1 + secs)
    secs = game seconds remaining at the SNAP of the last completed play
    ball = 1 when the leader has the ball after that play
    fav  = 1 when the leader's pregame expected margin is >= +3.5
    dog  = 1 when it is <= -3.5   (otherwise both 0: the base band)

THE RULE. Regulation only (period <= 4), secs <= 600, lead 4-16, a pregame
spread and a known possession. edge = WP - 1/decimal(DraftKings price of the
leader), the vig INCLUDED. BET the leader when edge >= 0.02. One bet per game,
the first qualifying evaluation; the caller enforces that.

TWO THINGS THAT MUST STAY BIT-IDENTICAL TO THE BACKTEST, and why they are
written the way they are:
  * wp_design / wp_lookup are the backtest's own functions, numpy for numpy.
    The scalar wp() calls them on one-element arrays rather than re-deriving
    the arithmetic with `math`, because a different log1p/exp path can differ
    by an ulp and the golden grid in the artifact is an exactness test.
  * the implied probability is 1 / am_to_dec(price), the backtest's formula,
    NOT data/live_quote_guard.american_to_implied: (-a)/((-a)+100) rounds
    differently and is not what the 167 graded bets were decided on.

THE BAND SIGN. The platform stores a spread as the HOME handicap (`odds.
spread_home`, negative = home favoured; CLAUDE.md section 4). The model was
trained on nflverse spread_line, which is the home team's EXPECTED MARGIN
(positive = home favoured), so spread_line = -spread_home and

    leader expected margin = -spread_home  if the leader is home
                           = +spread_home  if the leader is away

A missing spread is a refusal, never 0: 0 would put the game in the base band.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MODEL_ID = "nfl_live_leader_ml"
ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_PATH = ROOT / "models" / "saved" / "nfl_live_leader_ml_wp.json"

LEAD_MIN = 4
LEAD_MAX = 16
SECS_MAX = 600
PERIOD_MAX = 4
EDGE_CUT = 0.02
FAV_AT = 3.5          # leader expected margin >= +3.5 -> favourite band (0)
DOG_AT = -3.5         # <= -3.5 -> underdog band (2); between -> base band (1)
BAND_FAV, BAND_BASE, BAND_DOG = 0, 1, 2
COLUMNS = ("const", "t", "ball", "ball_t", "fav", "dog")


# ─── the backtest's own functions (scripts/nfl_edge_inplay_2025.py) ─────────

def am_to_dec(a):
    """American -> decimal. scripts/nfl_edge_lib.am_to_dec, unchanged."""
    a = np.asarray(a, dtype=float)
    return np.where(a > 0, 1 + a / 100.0, 1 + 100.0 / np.abs(a))


def wp_design(secs, ball, band):
    """The design matrix [const, t, ball, ball*t, fav, dog]. Unchanged."""
    t = np.log1p(np.asarray(secs, float))
    bl = np.asarray(ball, float)
    bd = np.asarray(band)
    return np.column_stack([np.ones(len(t)), t, bl, bl * t, bd == 0, bd == 2]).astype(float)


def wp_lookup(coefs, lead, ball, band, secs):
    """Fitted P(leader wins). Unchanged -- including the lead CLIP, which is why
    every caller must gate the lead to 4-16 first: a lead of 3 would silently
    borrow the lead-4 fit and a lead of 20 the lead-16 fit."""
    li = np.clip(np.asarray(lead, int) - 4, 0, 12)
    X = wp_design(secs, ball, band)
    eta = (X * coefs[li]).sum(1)
    return 1 / (1 + np.exp(-np.clip(eta, -30, 30)))


# ─── the artifact ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Artifact:
    coefs: np.ndarray                    # (13, 6), row L-4 = lead L
    rule: dict
    identity: dict
    training: dict = field(default_factory=dict)
    golden_grid: dict = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.identity.get("artifact_version", ""))


def artifact_from_dict(d: dict) -> Artifact:
    coefs = np.array([d["coefficients"][str(L)] for L in range(LEAD_MIN, LEAD_MAX + 1)],
                     dtype=float)
    if coefs.shape != (13, 6) or not np.isfinite(coefs).all():
        raise ValueError(f"bad coefficient block: shape {coefs.shape}")
    if list(d["features"]["columns"]) != list(COLUMNS):
        raise ValueError(f"column order {d['features']['columns']} != {COLUMNS}")
    return Artifact(coefs=coefs, rule=dict(d.get("rule") or {}),
                    identity=dict(d.get("identity") or {}),
                    training=dict(d.get("training") or {}),
                    golden_grid=dict(d.get("golden_grid") or {}))


def load_artifact(path: Path | str | None = None) -> Artifact:
    p = Path(path) if path else ARTIFACT_PATH
    return artifact_from_dict(json.loads(p.read_text(encoding="utf-8")))


# ─── features ─────────────────────────────────────────────────────────────────

def leader_expected_margin(spread_home: float, leader_is_home: bool) -> float:
    """The leader's pregame expected margin from the HOME handicap (see the
    module docstring for the sign)."""
    return -float(spread_home) if leader_is_home else float(spread_home)


def band_for(expected_margin: float) -> int:
    """leader_view's band: 0 favourite (>= 3.5), 2 underdog (<= -3.5), 1 base."""
    if expected_margin >= FAV_AT:
        return BAND_FAV
    if expected_margin <= DOG_AT:
        return BAND_DOG
    return BAND_BASE


def wp(art: Artifact, lead: int, secs: float, ball: int, band: int) -> float:
    """P(the leader wins), for one state. Refuses a lead outside 4-16 rather
    than letting wp_lookup's clip borrow a neighbouring fit."""
    if not (LEAD_MIN <= int(lead) <= LEAD_MAX):
        raise ValueError(f"lead {lead} outside {LEAD_MIN}-{LEAD_MAX}")
    if int(ball) not in (0, 1) or int(band) not in (0, 1, 2):
        raise ValueError(f"ball {ball} / band {band} out of range")
    return float(wp_lookup(art.coefs, np.array([int(lead)]), np.array([int(ball)]),
                           np.array([int(band)]), np.array([float(secs)]))[0])


# ─── the decision ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Decision:
    bet: bool
    reason: str                       # "BET", "edge below cut", or why it refused
    side: str | None = None           # "home" | "away" (the leader)
    lead: int | None = None
    secs: float | None = None
    ball: int | None = None
    band: int | None = None
    expected_margin: float | None = None
    wp: float | None = None
    price: float | None = None        # the leader's DraftKings American price
    decimal: float | None = None
    implied: float | None = None      # 1 / decimal, vig included
    edge: float | None = None


def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def decide(art: Artifact, *, period, secs, home_score, away_score, possession,
           spread_home, home_price, away_price, final: bool = False,
           edge_cut: float | None = None) -> Decision:
    """The rule for one evaluation. `possession` is "home" / "away" (the team
    with the ball after the last completed play) or None when unknown;
    `spread_home` is the pregame HOME handicap; prices are DraftKings American.

    Refuses -- never guesses -- when the game is over, in overtime, outside the
    window, missing its spread, or the possession is unknown."""
    cut = EDGE_CUT if edge_cut is None else float(edge_cut)
    if final:
        return Decision(False, "game over")
    p = _num(period)
    if p is None:
        return Decision(False, "period unknown")
    if p > PERIOD_MAX:
        return Decision(False, "overtime")
    s = _num(secs)
    if s is None or s < 0:
        return Decision(False, "clock unknown")
    if s > SECS_MAX:
        return Decision(False, f"secs {s:.0f} > {SECS_MAX}")
    hs, as_ = _num(home_score), _num(away_score)
    if hs is None or as_ is None:
        return Decision(False, "score unknown")
    diff = hs - as_
    lead = int(abs(diff))
    if not (LEAD_MIN <= lead <= LEAD_MAX):
        return Decision(False, f"lead {lead} outside {LEAD_MIN}-{LEAD_MAX}", lead=lead, secs=s)
    sp = _num(spread_home)
    if sp is None:
        return Decision(False, "no pregame spread", lead=lead, secs=s)
    if possession not in ("home", "away"):
        return Decision(False, "possession unknown", lead=lead, secs=s)
    leader_home = diff > 0
    side = "home" if leader_home else "away"
    ball = int(possession == side)
    m = leader_expected_margin(sp, leader_home)
    band = band_for(m)
    price = _num(home_price if leader_home else away_price)
    if price is None or price == 0:
        return Decision(False, "no DraftKings price for the leader", side=side, lead=lead,
                        secs=s, ball=ball, band=band, expected_margin=m)
    w = wp(art, lead, s, ball, band)
    dec = float(am_to_dec(price))
    implied = 1 / dec
    edge = w - implied
    bet = edge >= cut
    return Decision(bet, "BET" if bet else "edge below cut", side=side, lead=lead, secs=s,
                    ball=ball, band=band, expected_margin=m, wp=w, price=price,
                    decimal=dec, implied=implied, edge=edge)
