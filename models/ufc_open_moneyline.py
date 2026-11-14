"""UFC fight winner, decided at least a week out: a rating model anchored on
Pinnacle's no-vig price, bet at the best price a pick may name.

THE RULE (docs/ufc_market_audit.md section 3d). At a pull where Pinnacle and
at least one book in config.BEST_LINE_BOOKMAKERS both quote the fight, fetched
within MAX_GAP_MIN of each other, and at least MIN_LEAD_H before the start:

    p(A wins) = logistic( logit(Pinnacle's no-vig A) + b . z )

z the A-minus-B fighter inputs built strictly before the fight
(models/ufc_ratings.py), standardised with the artifact's mean and spread
(a missing input counts as the mean), b the ridge fit stored in the
artifact. At each book the side with the larger EV is that book's candidate;
a candidate below the price floor is dropped; the best remaining EV across
books is the pull's pick. It is a BET when that EV clears the model's own
EV floor (config.MODEL_OWN_EV_FLOOR). The first pull that clears locks the
fight. A = the fighter whose ufcstats name has the smaller slug.

WHY. The first posted price is a guess the market corrects, and the ratings
say which way: on the bought feed history 2020-06 to 2026-06, 846 bets at
+12.85% [+8.0, +17.5], every year positive, EV against Pinnacle's close
+1.4%, a donor-opinion placebo at -1.9%.

The artifact (models/saved/ufc_open_moneyline.json) is built by
scripts/ufc_open_moneyline_build.py from Supabase alone: the fight log, the
profiles and the BestFightOdds opens in ufc_price_archive.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MODEL_ID = "ufc_open_moneyline"
SPORT = "UFC"
MARKET = "h2h"
MIN_LEAD_H = 168.0
MAX_GAP_MIN = 10.0
RIDGE = 30.0
ARTIFACT = Path(__file__).resolve().parent / "saved" / "ufc_open_moneyline.json"


def american_to_decimal(a: float) -> float:
    a = float(a)
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def novig_a(pa: float, pb: float) -> float:
    ia, ib = 1 / american_to_decimal(pa), 1 / american_to_decimal(pb)
    return ia / (ia + ib)


def logit(p: float) -> float:
    p = min(max(float(p), 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def fit(X: np.ndarray, offset: np.ndarray, y: np.ndarray, lam: float = RIDGE) -> np.ndarray:
    """Ridge logistic with the market log-odds as an unpenalised offset."""
    from scipy.optimize import minimize

    def nll(b):
        s = offset + X @ b
        return np.sum(np.logaddexp(0, s) - y * s) + lam * np.sum(b ** 2)

    def grad(b):
        s = offset + X @ b
        p = 1 / (1 + np.exp(-s))
        return X.T @ (p - y) + 2 * lam * b

    return minimize(nll, np.zeros(X.shape[1]), jac=grad, method="L-BFGS-B").x


def load_artifact(path: Path = ARTIFACT) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def opinion(art: dict, z: dict) -> float:
    """b . standardised z; a missing input counts as the training mean."""
    s = 0.0
    for f, mu, sd, b in zip(art["features"], art["mu"], art["sd"], art["b"]):
        v = z.get(f)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        s += b * (float(v) - mu) / (sd or 1.0)
    return s


@dataclass
class Pick:
    side: str            # "a" or "b"
    book: str
    price: float
    prob: float          # the model's chance for the side
    ev: float


@dataclass
class Decision:
    fight: str
    status: str          # bets | below_cut | no_pull
    detail: str = ""
    pick: Pick | None = None
    quotes: dict = field(default_factory=dict)


def decide_pull(pin: tuple[float, float], books: dict[str, tuple[float, float]], xb: float,
                cut: float, floor: float | None) -> tuple[Pick | None, Pick | None]:
    """(the pull's pick if it clears the cut, the best candidate either way).
    `pin` and each book's quote are (price of A, price of B)."""
    pm = 1 / (1 + math.exp(-(logit(novig_a(*pin)) + xb)))
    best = None
    # A tie in EV goes to the earlier book in config.BEST_LINE_BOOKMAKERS
    # (DraftKings first), the order every best-line choice here uses.
    import config
    order = {b: i for i, b in enumerate(config.BEST_LINE_BOOKMAKERS)}
    for book in sorted(books, key=lambda b: (order.get(b, len(order)), b)):
        pa, pb = books[book]
        ea = pm * american_to_decimal(pa) - 1
        eb = (1 - pm) * american_to_decimal(pb) - 1
        side, ev, price, prob = ("a", ea, pa, pm) if ea >= eb else ("b", eb, pb, 1 - pm)
        if floor is not None and price < floor:
            continue
        if best is None or ev > best.ev:
            best = Pick(side, book, float(price), prob, ev)
    if best is not None and best.ev >= cut:
        return best, best
    return None, best
