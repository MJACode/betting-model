"""
NBA in-play game-state model (IG-2), live and real money: one rule.

mike, 2026-11-04: "everything goes live now, that's why we do back testing ...
and you continually improve models as you get more data." The third NBA search
(docs/nba_models_2026.md section 7) graded IG-2 on five seasons of in-play
quotes and 6 of its 18 cells passed the house standard: three rules, one model
id each. Re-graded on the fetches the loop can actually make (the archive's
hourly purchases, the shipped rule, section 9's house standard with 200
placebo runs; scripts/nba_live_ig2_regrade.py), 2021-22 .. 2025-26, only one
passes, and only it is live (mike, 2026-11-04: the backtest is the gate):

  nba_live_spread_q12   LIVE. live spread, quarters 1-2 phase, EV >= 0.05
                        1,348 bets, +96.6 units, +6.4% (95% +1.4 .. +11.3),
                        5 of 5 seasons, every bar passed; prices -160 / -114 /
                        +114 (min / median / max)

HELD OUT (HELD_OUT_RULES: their code path is this one, the loop never decides
them, no config registry names them; each is added the day it passes):

  nba_live_ml_q3        live moneyline, quarter 3 phase, EV >= 0.05
                        503 bets, +26.2 units, +8.3% (-2.7 .. +19.3), 4 of 5;
                        fails the interval and the bands
  nba_live_spread_q3    live spread, quarter 3 phase, EV >= 0.05
                        813 bets, +41.2 units, +4.5% (-2.0 .. +11.0), 4 of 5;
                        fails the interval, the bands and the placebo

NOT BUILT: the quarter-4 spread. It failed the backtest's placebo bar (record
7.3). The quarters 1-2 and quarter 4 moneylines failed every bar.

THE RULE, EXACTLY AS GRADED. Every function below that decides anything calls
the graded code: scripts/nba_ingame_ig2 (G: features, the state model, eligible,
offers, side choice, pricing), scripts/nba_game_harness (H: the empirical
pre-game distribution, side_probs, choose with the -200 floor), scripts/
nba_ingame_data (D: plays, timeline, phase bounds, Pinnacle pairing) and
scripts/nba_s_ingame27 (L: the 2026-27 search's live-row reading, its stable
state join, its impossible-number rules 1, 3, 4 and its clock rules 5, 6).

  MODEL     IG-2's Stern model: final home margin ~ Normal(m + X b, sqrt(s1 f
            + s0)), inputs margin, time left, Pinnacle's pre-game spread as the
            prior, team fouls, the top-minute starters' fouls. Fit on every
            30 s game state of 2020-21 .. 2025-26 (the stored training states
            the graded run built), the season-2027 model of IG-2's walk-forward
            (fit on every season before it). models/saved/nba_live_ig2_2027.json.
  PRIOR     Pinnacle's last coherent pre-tip spread (source-less worker rows,
            fetched and stamped before the listed tip), solved to a home margin
            through the empirical distribution of (final margin - Pinnacle's
            close) on 2020-21 .. 2025-26 (L.live_prior's construction).
  STATE     at a quote's stamp: the last ESPN play logged at or before it, ties
            broken by play order (L.state_at_stable, docs/nba_search_ingame27.md
            3.2), never scripts/nba_ingame_data.state_at.
  FRESH     record 7.1: no point scored between the deciding quote's stamp and
            the moment its fetch was served, the same for the Pinnacle quote it
            is paired with, and Pinnacle quoted the same game and market in the
            same fetch within 60 s, coherent.
  CLOCKS    a game whose first ESPN play is more than 15 minutes before the
            listed tip is refused (rule 5, one-sided as graded), as is a game
            with two consecutive plays 45+ minutes apart (rule 6), or a play
            4+ hours from the game's median wallclock (D.drop_wild_wallclocks).
  BAD ROWS  a price strictly between -100 and +100 (rule 1); a deciding spread
            more than 6 points, or a deciding moneyline more than 0.25 no-vig,
            from its Pinnacle pair (rules 3, 4).
  PHASES    quarters 1-2: periods 1-2, live or the break after quarter 1;
            quarter 3: period 3, live or the break after it. Halftime is in
            neither. A quote's phase is read at its OWN stamp.
  DECISION  per game and rule: the FIRST fetch holding an eligible deciding
            quote of the rule's market in its phase (G.decision_quotes). Every
            such quote is an offer, the side is the one whose best offer has
            the higher model EV (G.with_side_pick), the bet is the best-EV offer
            on that side at one of config.BEST_LINE_BOOKMAKERS at -200 or
            better, when its EV clears the cut (H.choose). An eligible fetch
            whose best offer does not clear the cut SPENDS the rule for the
            game: a later fetch is never used, whatever its EV. A fetch with no
            eligible quote is not a decision; the next fetch is tried.
  STAKE     one unit to win, risk capped at 3 (H.risk_win, stake_for).

The cadence that makes "the first fetch" mean what it meant in the grade lives
in the loop (models/nba_live_loop.py): fetches only at each hour minus 264 s,
the archive's hourly purchase (the :30 gap-fill purchases were built from
listed tips, which the loop cannot rebuild).

EV here is the harness's: p_win x (decimal - 1) - p_lose, a push returning the
stake. The row's model_probability is P(win | no push), so the platform's EV
gate (config.expected_value, which has no push) reads EV / (1 - p_push), never
less than the rule's EV: the shared gate cannot refuse a bet the rule took.

Pure: no network, no database, no clock. The loop and the parity replay
(scripts/build_nba_live_ig2_artifact.py) call the same functions.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_KIND = "nba_live_ig2"
ARTIFACT_PATH = "models/saved/nba_live_ig2_2027.json"
SEASON = 2027                 # 2026-27, the ending-year label (CLAUDE.md section 4)

SPREAD_Q12 = "nba_live_spread_q12"
ML_Q3 = "nba_live_ml_q3"
SPREAD_Q3 = "nba_live_spread_q3"


@dataclass(frozen=True)
class Rule:
    model_id: str
    phase: str                # G.PHASES label: "Q1-Q2" | "Q3"
    market: str               # "spreads" | "h2h"


# The rules the loop runs, and only these (mike, 2026-11-04: the backtest is
# the gate). Each is in config's registries and in model_registry.
RULES: tuple[Rule, ...] = (
    Rule(SPREAD_Q12, "Q1-Q2", "spreads"),
)
# Built and graded, NOT live: on the loop's own fetch times (the archive's
# hourly purchases) neither clears the house standard (module docstring). The
# loop never decides them and no config registry names them; their code path is
# this one, and scripts/nba_live_ig2_regrade.py re-grades them. A rule moves to
# RULES, with its config entries, the day it passes.
HELD_OUT_RULES: tuple[Rule, ...] = (
    Rule(ML_Q3, "Q3", "h2h"),
    Rule(SPREAD_Q3, "Q3", "spreads"),
)
GRADED_RULES: tuple[Rule, ...] = RULES + HELD_OUT_RULES
MODEL_IDS: tuple[str, ...] = tuple(r.model_id for r in RULES)
RULE_BY_ID = {r.model_id: r for r in GRADED_RULES}

FAR_FUTURE = pd.Timestamp("2200-01-01", tz="UTC")


def _lab():
    """(G, H, D, L): the graded modules, imported when first needed so that
    importing this file stays cheap for config checks and tests that never
    price anything."""
    from scripts import nba_game_harness as H
    from scripts import nba_ingame_data as D
    from scripts import nba_ingame_ig2 as G
    from scripts import nba_s_ingame27 as L
    return G, H, D, L


def rule_cut(model_id: str) -> float:
    """The rule's EV cut: the model's own EV floor (config.min_ev_for), one
    number for the rule and the platform gate."""
    import config
    return float(config.min_ev_for(model_id))


def rule_floor(model_id: str) -> float:
    import config
    return float(config.min_odds_for(model_id))


# ─── the artifact ──────────────────────────────────────────────────────────────

@dataclass
class Artifact:
    model: object                 # scripts.nba_ingame_ig2.StateModel, season 2027
    prior_dist: object            # scripts.nba_game_harness.ResidDist (2027, spreads)
    raw: dict = field(default_factory=dict)

    @property
    def version(self) -> str:
        return str(self.raw.get("version", ""))

    @property
    def models(self) -> dict:
        """The {season: model} map G.apply_model reads."""
        return {int(self.model.S): self.model}


def state_model_from(sm: dict):
    G, _H, _D, _L = _lab()
    if list(sm["cols"]) != list(G.FEATURES):
        raise ValueError(f"artifact columns {sm['cols']} are not IG-2's {G.FEATURES}")
    beta = np.asarray(sm["beta"], dtype=float)
    if beta.shape != (len(G.FEATURES),) or not np.isfinite(beta).all():
        raise ValueError(f"bad coefficient block: {beta.shape}")
    m = G.StateModel(G.FEATURES)
    m.beta, m.s1, m.s0 = beta, float(sm["s1"]), float(sm["s0"])
    m.S, m.n_train = int(sm["season"]), int(sm.get("n_train", 0))
    if not (m.s1 > 0 and m.s0 > 0):
        raise ValueError("variance terms must be positive")
    return m


def artifact_from_dict(d: dict) -> Artifact:
    _G, H, _D, _L = _lab()
    if d.get("kind") != ARTIFACT_KIND:
        raise ValueError(f"not an {ARTIFACT_KIND} artifact (kind={d.get('kind')!r})")
    return Artifact(model=state_model_from(d["state_model"]),
                    prior_dist=H.ResidDist.from_state(d["prior_dist"]), raw=d)


def load_artifact(path: str | Path | None = None) -> Artifact:
    """The committed artifact, else its copy in Supabase's model_artifacts
    (models.trainer._restore_artifact), else raise. Never a default model."""
    p = Path(path) if path is not None else ROOT / ARTIFACT_PATH
    if not p.exists() and path is None:
        from data.db import get_connection
        from models.trainer import _restore_artifact
        conn = get_connection()
        try:
            got = _restore_artifact(conn, ARTIFACT_PATH)
        finally:
            conn.close()
        if got is None:
            raise FileNotFoundError(f"{ARTIFACT_PATH}: not on disk and not in model_artifacts")
        p = Path(got)
    return artifact_from_dict(json.loads(p.read_text(encoding="utf-8")))


# ─── the pre-game prior ────────────────────────────────────────────────────────

def pinnacle_close_spread(rows: pd.DataFrame, game: dict) -> tuple[float, float, pd.Timestamp] | None:
    """(close_line, close_fa, close_at): Pinnacle's last coherent pre-tip
    spread for one game, from stored `odds` rows, exactly as the 2026-27
    search read it (L.live_prior): source-less rows, fetch (created_at) and
    stamp both before the listed tip (H.frame_quotes), the newest fetch's
    newest stamp that is coherent (H.pinnacle_close). None when there is none.

    `game`: game_id, season, game_date, tip (UTC Timestamp)."""
    _G, H, _D, _L = _lab()
    if rows is None or len(rows) == 0:
        return None
    o = rows.copy()
    if "source" in o:
        o = o[o["source"].isna()]
    o = o[(o["bookmaker"] == H.SHARP) & (o["market"] == "spreads")].copy()
    if o.empty:
        return None
    o["snapshot_at"] = pd.to_datetime(o["snapshot_at"], utc=True, format="mixed")
    o["created_at"] = pd.to_datetime(o["created_at"], utc=True, format="mixed")
    for c in ("home_price", "away_price", "spread_home", "total_line", "over_price", "under_price"):
        o[c] = pd.to_numeric(o.get(c), errors="coerce") if c in o else np.nan
    o["game_id"] = game["game_id"]
    o["season"], o["game_date"], o["tip"] = int(game["season"]), game["game_date"], game["tip"]
    o["fetch_at"] = o["created_at"]
    qq = H.frame_quotes(o)
    close = H.pinnacle_close(H.Data(games=pd.DataFrame(), quotes=qq, fetches=pd.DataFrame()))
    close = close[close["market"] == "spreads"]
    if close.empty:
        return None
    r = close.iloc[0]
    return float(r["close_line"]), float(r["close_fa"]), r["close_at"]


def prior_margin(art: Artifact, close_line: float, close_fa: float) -> float:
    """The home margin Pinnacle's close implies, through the artifact's
    empirical distribution (H.solve_any at the home number)."""
    G, H, _D, _L = _lab()
    mu = H.solve_any(G.threshold("spreads", np.array([close_line], float)),
                     np.array([close_fa], float), np.array([art.prior_dist], dtype=object))
    return float(mu[0])


# ─── the live game's period bounds ─────────────────────────────────────────────

def _action_mask(p: pd.DataFrame) -> np.ndarray:
    """D.phase_bounds' ACTION play: the jump ball, or a play with the clock
    running that is not a substitution, timeout, technical or period marker."""
    _G, _H, D, _L = _lab()
    t = p["type_text"].fillna("")
    na = np.zeros(len(p), bool)
    for w in D.NOT_ACTION:
        na |= t.str.contains(w).to_numpy()
    return (((t == "Jumpball") | (p["clock_s"] < D.period_length(p["period"]))) & ~na).to_numpy()


def live_bounds(plays: pd.DataFrame, final_games=()) -> pd.DataFrame:
    """D.phase_bounds for games still in progress.

    D.phase_bounds was written for finished games: the last period's end is
    its End Period row, else its newest play, and a period's start is its
    first ACTION play backed off by the clock, else its first row. On a game
    in progress three of those read wrong, and each is fixed here; a game in
    `final_games` keeps D.phase_bounds unchanged.
      * a period with no action play yet has not started (ESPN logs the next
        period's 12:00 substitutions the moment the previous one ends, and its
        "first row" would start it at once): its row is dropped;
      * the newest started period with no End Period row has not ended: its
        end is in the far future, so a stamp after its newest play is live,
        not postgame;
      * the newest started period WITH an End Period row is followed by a
        period that has not started: a row starting in the far future, so a
        stamp after the End Period is the break (halftime after period 2).
    """
    _G, _H, D, _L = _lab()
    b = D.phase_bounds(plays)
    if b.empty:
        return b
    p = plays.dropna(subset=["wc"])
    started = set(map(tuple, p.loc[_action_mask(p), ["game_id", "period"]].drop_duplicates().to_numpy()))
    ended = set(map(tuple, p.loc[p["type_text"].fillna("") == "End Period",
                                 ["game_id", "period"]].drop_duplicates().to_numpy()))
    out = []
    for gid, grp in b.groupby("game_id", sort=False):
        grp = grp.sort_values("period")
        if gid in set(final_games):
            out.append(grp)
            continue
        keep = grp[[(gid, int(per)) in started for per in grp["period"]]].copy()
        if keep.empty:
            continue
        last = int(keep["period"].max())
        if (gid, last) in ended:
            out.append(keep)
            out.append(pd.DataFrame({"game_id": [gid], "period": [last + 1],
                                     "start": [FAR_FUTURE], "end": [FAR_FUTURE]}))
        else:
            keep.loc[keep["period"] == last, "end"] = FAR_FUTURE
            out.append(keep)
    if not out:
        return b.iloc[0:0]
    res = pd.concat(out, ignore_index=True)
    res["start"] = pd.to_datetime(res["start"], utc=True)
    res["end"] = pd.to_datetime(res["end"], utc=True)
    return res[["game_id", "period", "start", "end"]]


def in_play_state(q: pd.DataFrame, plays: pd.DataFrame, top: pd.DataFrame,
                  games: pd.DataFrame, final_games=()) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """L.in_play_state with live_bounds in place of D.phase_bounds; every
    other line is the 2026-27 search's: the in-play test by the play-by-play
    clock, the listed-tip bound, the stable state join (L.restate), the
    Pinnacle pairing (D.attach_pinnacle) and the finals (none in play)."""
    _G, _H, D, L = _lab()
    tl = D.timeline(plays, top)
    bounds = live_bounds(plays, final_games)
    first = bounds.groupby("game_id")["start"].min().rename("first_play_at")
    last = bounds.sort_values("period").groupby("game_id").tail(1).set_index("game_id")["end"].rename("final_end_at")
    q = q.merge(first.reset_index(), on="game_id", how="left").merge(last.reset_index(), on="game_id", how="left")
    q, counts = D.keep_in_play(q, bounds)
    notes = dict(counts)
    early = q["stamp"] <= q["tip"]
    notes["in_play_by_clock_not_after_listed_tip"] = int(early.sum())
    q = q[~early].reset_index(drop=True)
    if q.empty:
        return q, tl, notes
    q = L.restate(q, tl)
    q["halftime"] = q["phase"] == "halftime"
    q = D.attach_pinnacle(q)
    if "home_score" in games:
        g = games.set_index("game_id")
        q["final_home"] = q["game_id"].map(g["home_score"])
        q["final_away"] = q["game_id"].map(g["away_score"])
    notes["rows_out"] = int(len(q))
    return q, tl, notes


# ─── one fetch's quotes ────────────────────────────────────────────────────────

def fetch_quotes(rows: pd.DataFrame, games: pd.DataFrame,
                 seen: set | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """One fetch's `odds`-shaped rows -> quotes in the 2026-27 search's shape
    (L.live_quotes: fetch = created_at, served = created_at never before the
    fetch's newest stamp, rule 1, coherent, fa), then the graded dedupe across
    fetches: a (game, market, book, stamp) already seen in an EARLIER fetch is
    dropped, the first kept. `seen` is updated in place with this fetch's.
    Returns (quotes, rule-1 rows, notes)."""
    _G, _H, _D, L = _lab()
    o = rows.copy()
    # L.live_quotes keeps the source-less rows (the worker's live pulls). The
    # loop's own rows carry a source marker (nba_live_feed.LIVE_SOURCE) and are
    # the same kind of row, so they are read as source-less here.
    o["source"] = None
    q, _raw, dropped, notes = L.live_quotes(o, games)
    if seen is not None and len(q):
        key = list(zip(q["game_id"], q["market"], q["book"], q["stamp"]))
        again = np.array([k in seen for k in key], bool)
        notes["rows_stamp_seen_in_earlier_fetch"] = int(again.sum())
        q = q[~again].reset_index(drop=True)
        seen.update(k for k, a in zip(key, again) if not a)
    return q, dropped, notes


def prepare(q: pd.DataFrame, plays: pd.DataFrame, pbp: pd.DataFrame, top: pd.DataFrame,
            games: pd.DataFrame, final_games=()) -> tuple[pd.DataFrame, dict]:
    """Quotes -> the table G.eligible reads, with the 2026-27 search's
    exclusions in its order: in-play state, rule 5 (early clock), rule 6
    (clock jump, on the plays known so far), rules 3-4, then Pinnacle's own
    freshness and the IG-2 phase. `pbp` is the nba_pbp-shaped rows (play_no,
    wallclock) rule 6 reads; `plays` is D.plays_frame of them (wild-wallclock
    games already out)."""
    G, _H, _D, L = _lab()
    notes: dict = {}
    if q.empty:
        return q.assign(phase_ig2=pd.Series(dtype=object)), notes
    q, _tl, n1 = in_play_state(q, plays, top, games, final_games)
    notes.update(n1)
    if q.empty:
        return q.assign(phase_ig2=pd.Series(dtype=object)), notes
    q, early = L.drop_early_clocks(q)
    notes["games_first_play_before_listed_tip"] = early
    jumps = L.jump_games(pbp) if len(pbp) else {}
    notes["games_wallclock_jump"] = jumps
    q = q[~q["game_id"].isin(set(jumps))].reset_index(drop=True)
    q, d34 = L.apply_bad_rows(q)
    notes["rule34_dropped"] = int(len(d34))
    return L.step1_table(q), notes


def eligible_for(qt: pd.DataFrame, rule: Rule) -> pd.DataFrame:
    """Eligible deciding quotes (G.eligible) of the rule's market in its phase."""
    G, _H, _D, _L = _lab()
    if qt.empty:
        return qt
    el = G.eligible(qt)
    return el[(el["market"] == rule.market) & (el["phase_ig2"] == rule.phase)].copy()


# ─── the decision ──────────────────────────────────────────────────────────────

@dataclass
class Decision:
    game_id: str
    model_id: str
    bet: bool
    reason: str
    offers: pd.DataFrame | None = None       # every priced offer of the decision fetch
    pick: dict | None = None                 # the chosen offer (H.choose row) when bet


def priced_offers(dec: pd.DataFrame, models: dict) -> pd.DataFrame:
    """G.grid_frames' candidate frame: the model at each quote's own state,
    two offers per quote (home, away), priced (H.side_probs, H.with_ev), and
    the per-game side the model favours (G.with_side_pick)."""
    G, _H, _D, _L = _lab()
    d = G.apply_model(G.features(dec), models)
    off = G.offer_rows(d)
    return G.with_side_pick(G.priced(off, off["mean"], off["sd"], off["p_home"]))


EV_DECIMALS = 12


def choose_bets(cand: pd.DataFrame, cut: float, floor: float) -> pd.DataFrame:
    """H.choose on the model's side: one bet per (game, market), best EV at a
    deciding book, price >= floor, EV >= cut.

    EV is rounded to EV_DECIMALS first. Two books at the same number and price
    have the same EV, and H.choose sends a tie to the earlier book in
    BEST_LINE_BOOKMAKERS; but EV computed in a one-game frame can differ from
    the same EV computed in the grade's many-game frame by floating-point noise
    (4e-16), and the noise, not the rule, then chose the book (3 of the 1,753
    graded quarters 1-2 spread bets, independent review 2026-11-04). Rounding
    makes a tie a tie in every frame."""
    _G, H, _D, _L = _lab()
    if "ev" in cand:
        cand = cand.assign(ev=cand["ev"].round(EV_DECIMALS))
    return H.choose(cand, cut, sides=["model"], floor=floor)


def decide_first_fetch(el: pd.DataFrame, models: dict, cut: float, floor: float) -> pd.DataFrame:
    """The grade's whole decision over many games at once (the parity replay):
    the first eligible fetch per (game, market, phase) (G.decision_quotes),
    priced and chosen ONE PHASE AT A TIME, as G.run_grid does: the side the
    model favours is per (game, market) within a phase, and pricing two phases
    in one frame would let a quarter-3 offer pick a quarter-1 side. `el` must
    carry mu_pre. Returns the bets, with phase_ig2."""
    G, _H, _D, _L = _lab()
    if el.empty:
        return el.assign(phase_ig2=pd.Series(dtype=object))
    dec = G.decision_quotes(el)
    out = []
    for ph in G.PHASES:
        d = dec[dec["phase_ig2"] == ph]
        if d.empty:
            continue
        out.append(choose_bets(priced_offers(d, models), cut, floor).assign(phase_ig2=ph))
    return pd.concat(out, ignore_index=True) if out else dec.iloc[0:0]


def decide(el_rule: pd.DataFrame, rule: Rule, models: dict, mu_pre: float,
           cut: float | None = None, floor: float | None = None) -> Decision | None:
    """One game, one rule, one fetch. `el_rule` is this fetch's eligible
    quotes of the rule's market in its phase, for ONE game (eligible_for).

    None: the fetch holds no eligible quote, so it is not a decision and the
    next fetch is tried. Otherwise a Decision, bet or not, which SPENDS the
    rule for the game."""
    cut = rule_cut(rule.model_id) if cut is None else float(cut)
    floor = rule_floor(rule.model_id) if floor is None else float(floor)
    if el_rule is None or el_rule.empty:
        return None
    games = set(el_rule["game_id"])
    if len(games) != 1:
        raise ValueError(f"decide() takes one game, got {sorted(games)}")
    if len(set(el_rule["fetch_at"])) != 1:
        raise ValueError("decide() takes one fetch")
    gid = next(iter(games))
    if mu_pre is None or not math.isfinite(float(mu_pre)):
        return Decision(gid, rule.model_id, False, "no pre-game prior (no Pinnacle spread close)")
    dec = el_rule.assign(mu_pre=float(mu_pre))
    cand = priced_offers(dec, models)
    bets = choose_bets(cand, cut, floor)
    if bets.empty:
        best = cand[cand["side"] == cand["side_pick"]]
        why = "no offer on the model's side clears the cut"
        if len(best):
            top = best.sort_values("ev", ascending=False).iloc[0]
            why = (f"best offer on the model's side {top['side']} {top['book']} "
                   f"{top['price']:+.0f}, EV {top['ev']:.3f} (cut {cut:.2f}, floor {floor:+.0f})")
        return Decision(gid, rule.model_id, False, why, offers=cand)
    return Decision(gid, rule.model_id, True, "BET", offers=cand, pick=bets.iloc[0].to_dict())


# ─── the top players (IG-2's foul inputs) ──────────────────────────────────────

def prior_minutes(history: pd.DataFrame, game_date: str, season: int) -> pd.DataFrame:
    """(athlete_id, prior_min) for a game on `game_date`: minutes per game in
    the player's played games of this season before that date, else his
    previous season's average over played games, else 0 --
    nba_ingame_data.prior_minutes / L.box_prior_minutes, read for one date.

    `history`: nba_pbp_box rows of regular-season games (espn_id, minutes,
    game_date, season) for `season` and `season - 1`."""
    if history is None or len(history) == 0:
        return pd.DataFrame({"athlete_id": pd.Series(dtype="int64"), "prior_min": pd.Series(dtype=float)})
    b = history.rename(columns={"espn_id": "athlete_id"}).copy()
    b["athlete_id"] = pd.to_numeric(b["athlete_id"], errors="coerce").astype("int64")
    b["season"] = b["season"].astype(int)
    b["m"] = pd.to_numeric(b["minutes"], errors="coerce")
    b["game_date"] = b["game_date"].astype(str).str[:10]
    played = b[b["m"].fillna(0) > 0]
    cur = played[(played["season"] == int(season)) & (played["game_date"] < str(game_date)[:10])]
    last = played[played["season"] == int(season) - 1]
    m_cur = cur.groupby("athlete_id")["m"].mean()
    m_last = last.groupby("athlete_id")["m"].mean()
    ids = sorted(set(b["athlete_id"]))
    pm = pd.Series(ids, dtype="int64").map(m_cur).fillna(pd.Series(ids, dtype="int64").map(m_last)).fillna(0.0)
    return pd.DataFrame({"athlete_id": ids, "prior_min": pm.to_numpy(float)})


def top_players(game_id: str, espn_game_id: int, starters: pd.DataFrame,
                history: pd.DataFrame, game_date: str, season: int) -> pd.DataFrame:
    """D.top_players for one game: each side's three starters (`starters`:
    espn_id, side H/A, starter) ranked by prior minutes, ties by athlete id."""
    _G, _H, D, _L = _lab()
    s = starters.rename(columns={"espn_id": "athlete_id"}).copy()
    s["athlete_id"] = pd.to_numeric(s["athlete_id"], errors="coerce").astype("int64")
    s = s.assign(game_id=game_id, espn_game_id=int(espn_game_id))
    pm = prior_minutes(history, game_date, season).assign(espn_game_id=int(espn_game_id))
    return D.top_players(s[["game_id", "espn_game_id", "athlete_id", "side", "starter"]], pm)


# ─── the pick's numbers ────────────────────────────────────────────────────────

def american_to_decimal(price: float) -> float:
    p = float(price)
    return 1.0 + (p / 100.0 if p > 0 else 100.0 / abs(p))


def prob_no_push(p_win: float, p_push: float) -> float:
    """P(win | no push): the row's model_probability (module docstring)."""
    p_push = float(p_push or 0.0)
    return float(p_win) / max(1.0 - p_push, 1e-12)


def side_line(rule: Rule, side: str, home_line) -> float | None:
    """The bet side's own number from the stored HOME number (CLAUDE.md
    section 4): the home number for home, negated for away."""
    if rule.market != "spreads" or home_line is None:
        return None
    return float(home_line) if side == "home" else -float(home_line)


def pick_label(rule: Rule, side: str, home_line, home: str, away: str) -> str:
    """The words a person reads: 'BOS -4.5 (live)', 'MIA ML (live)'. Built
    from the side and the HOME number, so tracking.pick_integrity agrees."""
    team = home if side == "home" else away
    if rule.market == "h2h":
        return f"{team} ML (live)"
    n = side_line(rule, side, home_line)
    if n == 0:
        return f"{team} PK (live)"       # pick'em: tracking.pick_integrity reads PK as 0
    return f"{team} {n:+g} (live)"


# ─── one game never carries two bets that cannot both win ──────────────────────

def winning_margins(market: str, side: str, home_line) -> tuple[float, float]:
    """The integer final home margins (overtime counted, so never 0) a bet
    wins on, as an inclusive [lo, hi] (+-inf open)."""
    inf = math.inf
    if market == "h2h":
        return (1.0, inf) if side == "home" else (-inf, -1.0)
    x = -float(home_line)                       # home covers when margin > -line
    if side == "home":
        return (math.floor(x) + 1.0, inf)
    return (-inf, math.ceil(x) - 1.0)


def cannot_both_win(a: dict, b: dict) -> bool:
    """mike, 2026-10-17: "It can't be both." True when no final margin wins
    both bets. Each dict: market, side, line (the HOME number, None for a
    moneyline)."""
    la, ha = winning_margins(a["market"], a["side"], a.get("line"))
    lb, hb = winning_margins(b["market"], b["side"], b.get("line"))
    lo, hi = max(la, lb), min(ha, hb)
    if lo > hi:
        return True
    return lo == hi == 0.0
