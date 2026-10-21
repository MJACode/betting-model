"""NHL blocked shots: a Poisson model of one skater's count, priced against DraftKings.

WHY THIS ONE. docs/nhl_market_lab.md graded six NHL prop markets on three
priced seasons. Blocked shots at DraftKings is the only one whose return was
positive in every season at every cut (12 of 12 cells), with intervals clear of
zero, and it was picked out on 2025-26 and then held on two seasons bought
afterwards. The bets are unders: DraftKings' margin on this market sits on the
over (blind overs -10.7%, blind unders -1.0% in 2025-26), Pinnacle does not
quote it, and the model's job is to say which unders.

THE MODEL. scripts/nhl_prop_lab.py's, moved here so the backtest, the trainer
and tonight's card run ONE function. A gradient-boosted Poisson mean from:

    the player's own blocks, exponentially weighted (half-lives 30 and 6 games)
    his ice time and power-play time, weighted the same way (20 and 4)
    how much the OPPONENT shoots (their shots for, half-life 25)
    defenceman or forward, home or road, days of rest, career games in the log

Every input is strictly before the game: each is the weighted mean of the
player's (or opponent's) EARLIER rows. Tonight's game is scored by appending a
row for it with no result and reading the same shifted mean -- so a training
row and a live row are the same arithmetic, not two implementations of it.

P(under the line) is the Poisson probability of `floor(line)` or fewer.

WHAT IT DOES NOT KNOW. Lineups. A scratched player is void at DraftKings (and
settles NO_ACTION here); a player who dresses and is hurt in the first period
is a live bet that the under wins. Neither is modelled.
"""
from __future__ import annotations

import unicodedata

import numpy as np
import pandas as pd
from scipy.stats import poisson

MODEL_ID = "nhl_prop_blocked_shots"
MARKET = "player_blocked_shots"
STAT = "blocked_shots"
BOOK = "draftkings"
FEATURES = ["blocked_shots_l", "blocked_shots_s", "opp_sf",
            "toi_l", "toi_s", "pp_toi_l", "pp_toi_s", "is_home", "rest", "is_d", "gp"]
# A line is not hung on a debutant, and ten games is what the lab required
# before it would predict one.
MIN_GAMES = 10
FIRST_TRAIN_SEASON = 2020
PARAMS = dict(objective="count:poisson", n_estimators=400, max_depth=4, learning_rate=0.03,
              subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5.0,
              random_state=42, n_jobs=-1, verbosity=0)

SKATER_COLS = ("nhl_game_id", "player_id", "player_name", "position", "season", "game_date",
               "team", "opponent", "is_home", "blocked_shots", "toi_seconds", "pp_toi_seconds")
TEAM_COLS = ("nhl_game_id", "game_id", "team", "opponent", "game_date", "shots_for")
# Rows appended for games not yet played carry ids from here up, so they can
# never collide with a real NHL game id (ten digits) or sort before one.
UPCOMING_ID0 = 10 ** 12


def name_key(name: str | None) -> str:
    """Letters only, accents and case folded: how a price row finds its player."""
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(c for c in flat.lower() if c.isalpha())


# ── loading ──────────────────────────────────────────────────────────────────

def load_skaters(conn, player_ids: list | None = None) -> pd.DataFrame:
    """Regular-season skater rows: all of them to train, a few players' to score."""
    sql = (f"SELECT {', '.join(SKATER_COLS)} FROM nhl_skater_game_log WHERE game_type = 2")
    if player_ids is None:
        rows = conn.execute(sql).fetchall()
    else:
        rows = conn.execute(sql + " AND player_id = ANY(%s)", ([int(p) for p in player_ids],)).fetchall()
    return pd.DataFrame(rows, columns=list(SKATER_COLS))


def load_teams(conn) -> pd.DataFrame:
    rows = conn.execute(f"SELECT {', '.join(TEAM_COLS)} FROM nhl_team_game_log").fetchall()
    return pd.DataFrame(rows, columns=list(TEAM_COLS))


# ── features ─────────────────────────────────────────────────────────────────

def _ew(g, col: str, halflife: float, min_periods: int = 3):
    return g[col].transform(lambda s: s.shift(1).ewm(halflife=halflife, min_periods=min_periods).mean())


def build_frame(skaters: pd.DataFrame, teams: pd.DataFrame,
                upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per skater-game with every input as of BEFORE that game.

    `upcoming` holds games not yet played -- columns player_id, player_name,
    position, season, game_date, team, opponent, is_home, game_id -- and comes
    back as rows flagged `upcoming` with the same inputs and no result.
    """
    d = skaters.copy()
    d["upcoming"] = False
    t = teams.copy()
    if upcoming is not None and len(upcoming):
        u = upcoming.copy()
        # one synthetic game id per (game_id): both teams and every player share it
        ids = {g: UPCOMING_ID0 + i for i, g in enumerate(sorted(u.game_id.unique()))}
        u["nhl_game_id"] = u.game_id.map(ids)
        u["upcoming"] = True
        for c in ("blocked_shots", "toi_seconds", "pp_toi_seconds"):
            u[c] = np.nan
        d = pd.concat([d, u[list(SKATER_COLS) + ["upcoming"]]], ignore_index=True)
        tu = (u[["nhl_game_id", "game_id", "team", "opponent", "game_date"]].drop_duplicates()
              .assign(shots_for=np.nan))
        # the opponent's row too: its shots-for is what the player's blocks answer to
        ou = tu.rename(columns={"team": "opponent", "opponent": "team"})
        t = pd.concat([t, tu, ou[list(TEAM_COLS)]], ignore_index=True).drop_duplicates(
            ["nhl_game_id", "team"], keep="first")

    for c in ("blocked_shots", "toi_seconds", "pp_toi_seconds", "is_home"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["blocked_shots_l"], d["blocked_shots_s"] = _ew(g, STAT, 30), _ew(g, STAT, 6)
    d["toi_l"], d["toi_s"] = _ew(g, "toi_seconds", 20), _ew(g, "toi_seconds", 4)
    d["pp_toi_l"], d["pp_toi_s"] = _ew(g, "pp_toi_seconds", 20), _ew(g, "pp_toi_seconds", 4)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    d["is_d"] = (d.position == "D").astype(int)

    t["shots_for"] = pd.to_numeric(t["shots_for"], errors="coerce")
    t["game_date"] = pd.to_datetime(t["game_date"])
    t = t.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    t["opp_sf"] = _ew(t.groupby("team", sort=False), "shots_for", 25, 5)
    opp = t[["nhl_game_id", "team", "opp_sf"]].rename(columns={"team": "opponent"})
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left")
    gid = t[["nhl_game_id", "game_id"]].dropna().drop_duplicates("nhl_game_id")
    d = d.drop(columns=[c for c in ("game_id",) if c in d.columns]).merge(gid, on="nhl_game_id", how="left")
    d["pkey"] = d.player_name.map(name_key)
    return d


def usable(frame: pd.DataFrame) -> pd.DataFrame:
    """Rows the model may train on or score: ten prior games and every input present."""
    return frame[frame.gp >= MIN_GAMES].dropna(subset=FEATURES)


# ── model ────────────────────────────────────────────────────────────────────

def fit(frame: pd.DataFrame, through_season: int):
    """Fit on every played, usable row from FIRST_TRAIN_SEASON through `through_season`."""
    from xgboost import XGBRegressor
    tr = usable(frame[~frame.upcoming]).dropna(subset=[STAT])
    tr = tr[tr.season.between(FIRST_TRAIN_SEASON, through_season)]
    m = XGBRegressor(**PARAMS)
    m.fit(tr[FEATURES].values.astype(float), tr[STAT].values.astype(float))
    return m, len(tr)


def predict_mean(model, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(model.predict(rows[FEATURES].values.astype(float)), 1e-3, None)


def p_over(mu, line) -> np.ndarray:
    """P(count > line): the Poisson tail above floor(line)."""
    return poisson.sf(np.floor(np.asarray(line, dtype=float)), np.asarray(mu, dtype=float))


def win_per_unit(american: float) -> float:
    return american / 100.0 if american > 0 else 100.0 / abs(american)


def expected_value(p: float, american: float) -> float:
    return p * (1 + win_per_unit(american)) - 1
