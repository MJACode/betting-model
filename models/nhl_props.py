"""NHL count props beyond blocked shots: goalie saves, skater shots on goal, skater assists.

ONE ENGINE, ONE SPEC PER MARKET. models/nhl_prop_blocked_shots.py is the live
blocked-shots model and is deliberately left alone (its artifact was fitted on
exactly that module); this is the same design, generalised so a new market is a
`Spec`, not a new file:

    a gradient-boosted Poisson mean for one player's count in one game, from
    his own exponentially weighted history, his usage, and what the two teams
    do -- every input the weighted mean of EARLIER rows only;
    P(over the line) from the count distribution around that mean.

Tonight's game is scored by appending a row with no result and reading the
same shifted means, so a training row and a live row are one piece of
arithmetic, not two implementations of it.

WHAT DIFFERS BY MARKET
  skater markets   one row per skater-game. Usage is ice time and power-play
                   time; the matchup is what the OPPONENT allows.
  goalie saves     one row per START. A goalie who does not start is void at
                   DraftKings, so a relief appearance is neither history nor a
                   bet here. The matchup is how much the opponent shoots, how
                   much his own team allows, who is at home, and how rested
                   he and both teams are (the last three were added because
                   they predict the COUNT better on seasons the model had not
                   seen -- 0.7% lower deviance -- and for no other reason;
                   the same test added nothing to either skater market).

UNDERS ONLY. In every NHL count market DraftKings' margin sits on the over:
betting every over blind loses 9-12% and every under 0-3.5% (three priced
seasons). The model's overs lose in all three markets here and its unders are
where the return is, so a Spec names the sides it may bet and all three name
the under. That restriction was chosen on the same three seasons the cut was,
which is said out loud in docs/nhl_market_lab.md.

THE BEST PRICE, NOT ONE BOOK. A pick is decided at the best price among the
bettable books (CLAUDE.md 6), and here that is not a detail: the model says
which unders, and several books hang the same player at different numbers and
prices. At DraftKings alone the shots-on-goal unders return about +3% and
nothing in the most recent season; at the best price the same model returns
+5.7% with every season positive. Saves and assists hold either way.
`books()` is who may be shopped. FanDuel is left out: it lists several lines a
player and the shared parser kept one row a player, pairing an over from one
line with an under from another (2,556 of its shots rows fail the coherent-
quote check in the bought history; no other book has more than 11). The
filter drops the pairs it can see, not the ones that happen to sum plausibly.

THE DISTRIBUTION. A Poisson count has variance equal to its mean. Saves do
not: a goalie's night swings with the shot volume he faces, so the spread
around the predicted mean is wider. `fit` measures that excess on the training
rows (`dispersion`, 0 = Poisson) and `p_over` uses a negative binomial when it
is positive. Whether a market uses it is in its Spec. Saves does: its counts
are far wider than Poisson. Assists are Poisson to within 3%. Shots on goal
run about 10% wide and are left Poisson, as the lab had them: the wider
distribution does not change what the model claims against what happens, and
the result holds under either (+5.7% Poisson, +4.9% wider, at the 0.10 cut,
every season positive both ways).
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import nbinom, poisson

BOOK = "draftkings"             # the reference book: the DraftKings-only tables, and the bet link
EXCLUDED_BOOKS = frozenset({"fanduel"})
MIN_GAMES = 10                  # a line is not hung on a debutant (career rows in the log, not this season's)
FIRST_TRAIN_SEASON = 2020
PARAMS = dict(objective="count:poisson", n_estimators=400, max_depth=4, learning_rate=0.03,
              subsample=0.8, colsample_bytree=0.8, min_child_weight=50, reg_lambda=5.0,
              random_state=42, n_jobs=-1, verbosity=0)
# Rows appended for games not yet played carry ids from here up, so they can
# never collide with a real NHL game id (ten digits) or sort before one.
UPCOMING_ID0 = 10 ** 12

SKATER_USAGE = ("toi_l", "toi_s", "pp_toi_l", "pp_toi_s", "is_home", "rest", "is_d", "gp")


@dataclass(frozen=True)
class Spec:
    model_id: str
    market: str            # the Odds API market key in player_prop_odds
    stat: str              # the game-log column the bet settles on
    label: str             # how the stat reads in a pick label
    kind: str              # 'skater' | 'goalie'
    features: tuple[str, ...]
    overdispersed: bool = False
    sides: tuple[str, ...] = ("under",)


SAVES = Spec("nhl_prop_saves", "player_total_saves", "saves", "Saves", "goalie",
             ("saves_l", "saves_s", "sa_l", "opp_sf", "own_sa", "gp",
              "is_home", "rest", "own_rest", "opp_rest"), overdispersed=True)
SHOTS = Spec("nhl_prop_shots_on_goal", "player_shots_on_goal", "shots", "Shots on Goal", "skater",
             ("shots_l", "shots_s", "shot_attempts_l", "shot_attempts_s", "opp_sa") + SKATER_USAGE)
ASSISTS = Spec("nhl_prop_assists", "player_assists", "assists", "Assists", "skater",
               ("assists_l", "assists_s", "points_l", "opp_ga", "opp_pk_opps") + SKATER_USAGE)
SPECS: dict[str, Spec] = {s.model_id: s for s in (SAVES, SHOTS, ASSISTS)}
LIVE: tuple[Spec, ...] = (SAVES, SHOTS, ASSISTS)

SKATER_COLS = ("nhl_game_id", "player_id", "player_name", "position", "season", "game_date",
               "team", "opponent", "is_home", "shots", "shot_attempts", "assists", "points",
               "toi_seconds", "pp_toi_seconds")
GOALIE_COLS = ("nhl_game_id", "player_id", "player_name", "season", "game_date",
               "team", "opponent", "is_home", "started", "saves", "shots_against")
TEAM_COLS = ("nhl_game_id", "game_id", "team", "opponent", "game_date",
             "shots_for", "shots_against", "goals_against", "times_shorthanded")
_SKATER_STATS = ("shots", "shot_attempts", "assists", "points")
_TEAM_STATS = {"sf": "shots_for", "sa": "shots_against", "ga": "goals_against", "pk_opps": "times_shorthanded"}


def books() -> tuple[str, ...]:
    """The books a pick may be decided at: the bettable ones, less EXCLUDED_BOOKS."""
    import config
    return tuple(b for b in config.BEST_LINE_BOOKMAKERS if b not in EXCLUDED_BOOKS)


def name_key(name: str | None) -> str:
    """Letters only, accents and case folded: how a price row finds its player."""
    flat = unicodedata.normalize("NFKD", str(name or ""))
    return "".join(c for c in flat.lower() if c.isalpha())


# ── loading ──────────────────────────────────────────────────────────────────

def load_players(conn, kind: str, player_ids: list | None = None) -> pd.DataFrame:
    """Regular-season rows: all of them to train, a few players' to score."""
    table, cols = (("nhl_goalie_game_log", GOALIE_COLS) if kind == "goalie"
                   else ("nhl_skater_game_log", SKATER_COLS))
    sql = f"SELECT {', '.join(cols)} FROM {table} WHERE game_type = 2 AND player_id IS NOT NULL"
    if player_ids is None:
        rows = conn.execute(sql).fetchall()
    else:
        rows = conn.execute(sql + " AND player_id = ANY(%s)", ([int(p) for p in player_ids],)).fetchall()
    return pd.DataFrame(rows, columns=list(cols))


def load_teams(conn) -> pd.DataFrame:
    rows = conn.execute(f"SELECT {', '.join(TEAM_COLS)} FROM nhl_team_game_log").fetchall()
    return pd.DataFrame(rows, columns=list(TEAM_COLS))


# ── features ─────────────────────────────────────────────────────────────────

def _ew(g, col: str, halflife: float, min_periods: int = 3):
    return g[col].transform(lambda s: s.shift(1).ewm(halflife=halflife, min_periods=min_periods).mean())


def _with_upcoming(players: pd.DataFrame, teams: pd.DataFrame, upcoming: pd.DataFrame | None,
                   cols: tuple[str, ...], results: tuple[str, ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append tonight's players, and both of tonight's teams, as rows with no result."""
    d = players[[c for c in cols if c in players.columns]].copy()
    d["upcoming"] = False
    t = teams[list(TEAM_COLS)].copy()
    if upcoming is None or not len(upcoming):
        return d, t
    u = upcoming.copy()
    # one synthetic game id per game: both teams and every player share it
    ids = {g: UPCOMING_ID0 + i for i, g in enumerate(sorted(u.game_id.unique()))}
    u["nhl_game_id"] = u.game_id.map(ids)
    u["upcoming"] = True
    for c in results:
        u[c] = np.nan
    for c in cols:
        if c not in u.columns:
            u[c] = 1 if c == "started" else np.nan
    d = pd.concat([d, u[list(cols) + ["upcoming"]]], ignore_index=True)
    tu = u[["nhl_game_id", "game_id", "team", "opponent", "game_date"]].drop_duplicates()
    ou = tu.rename(columns={"team": "opponent", "opponent": "team"})
    both = pd.concat([tu, ou[list(tu.columns)]], ignore_index=True)
    for c in _TEAM_STATS.values():
        both[c] = np.nan
    t = pd.concat([t, both[list(TEAM_COLS)]], ignore_index=True).drop_duplicates(
        ["nhl_game_id", "team"], keep="first")
    return d, t


def _team_rates(teams: pd.DataFrame) -> pd.DataFrame:
    """Each team's as-of per-game rates, one row per (game, team)."""
    t = teams.copy()
    for c in _TEAM_STATS.values():
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["game_date"] = pd.to_datetime(t["game_date"])
    t = t.sort_values(["team", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = t.groupby("team", sort=False)
    for k, c in _TEAM_STATS.items():
        t[f"t_{k}"] = _ew(g, c, 25, 5)
    t["t_rest"] = (t.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    return t


def _attach_teams(d: pd.DataFrame, t: pd.DataFrame) -> pd.DataFrame:
    names = list(_TEAM_STATS) + ["rest"]
    keys = [f"t_{k}" for k in names]
    opp = t[["nhl_game_id", "team"] + keys].rename(
        columns={"team": "opponent", **{f"t_{k}": f"opp_{k}" for k in names}})
    own = t[["nhl_game_id", "team"] + keys].rename(columns={f"t_{k}": f"own_{k}" for k in names})
    d = d.merge(opp, on=["nhl_game_id", "opponent"], how="left").merge(own, on=["nhl_game_id", "team"], how="left")
    gid = t[["nhl_game_id", "game_id"]].dropna().drop_duplicates("nhl_game_id")
    d = d.drop(columns=[c for c in ("game_id",) if c in d.columns]).merge(gid, on="nhl_game_id", how="left")
    d["pkey"] = d.player_name.map(name_key)
    return d


def build_skater_frame(skaters: pd.DataFrame, teams: pd.DataFrame,
                       upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per skater-game with every input as of BEFORE that game.

    `upcoming` holds games not yet played -- columns player_id, player_name,
    position, season, game_date, team, opponent, is_home, game_id.
    """
    results = _SKATER_STATS + ("toi_seconds", "pp_toi_seconds")
    d, t = _with_upcoming(skaters, teams, upcoming, SKATER_COLS, results)
    for c in results + ("is_home",):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    for stat in _SKATER_STATS:
        d[f"{stat}_l"], d[f"{stat}_s"] = _ew(g, stat, 30), _ew(g, stat, 6)
    d["toi_l"], d["toi_s"] = _ew(g, "toi_seconds", 20), _ew(g, "toi_seconds", 4)
    d["pp_toi_l"], d["pp_toi_s"] = _ew(g, "pp_toi_seconds", 20), _ew(g, "pp_toi_seconds", 4)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    d["is_d"] = (d.position == "D").astype(int)
    return _attach_teams(d, _team_rates(t))


def build_goalie_frame(goalies: pd.DataFrame, teams: pd.DataFrame,
                       upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per goalie START with every input as of before it.

    `upcoming` -- player_id, player_name, season, game_date, team, opponent,
    is_home, game_id -- is the goalies a book has priced tonight, taken as
    starting: that is the bet, and it is void if he does not.
    """
    results = ("saves", "shots_against")
    d, t = _with_upcoming(goalies, teams, upcoming, GOALIE_COLS, results)
    for c in results + ("is_home", "started"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d = d[d.started == 1].copy()
    d["game_date"] = pd.to_datetime(d["game_date"])
    d = d.sort_values(["player_id", "game_date", "nhl_game_id"]).reset_index(drop=True)
    g = d.groupby("player_id", sort=False)
    d["saves_l"], d["saves_s"] = _ew(g, "saves", 25), _ew(g, "saves", 5)
    d["sa_l"] = _ew(g, "shots_against", 25)
    d["rest"] = (d.game_date - g.game_date.shift(1)).dt.days.clip(upper=6).fillna(6)
    d["gp"] = g.cumcount()
    return _attach_teams(d, _team_rates(t))


def build_frame(spec: Spec, players: pd.DataFrame, teams: pd.DataFrame,
                upcoming: pd.DataFrame | None = None) -> pd.DataFrame:
    build = build_goalie_frame if spec.kind == "goalie" else build_skater_frame
    return build(players, teams, upcoming)


def usable(spec: Spec, frame: pd.DataFrame) -> pd.DataFrame:
    """Rows the model may train on or score: ten prior games and every input present."""
    return frame[frame.gp >= MIN_GAMES].dropna(subset=list(spec.features))


# ── model ────────────────────────────────────────────────────────────────────

def _x(spec: Spec, rows: pd.DataFrame) -> np.ndarray:
    return rows[list(spec.features)].values.astype(float)


def excess_variance(y: np.ndarray, mu: np.ndarray) -> float:
    """alpha in var = mu + alpha * mu^2, by moments. 0 when the counts are no wider than Poisson."""
    y, mu = np.asarray(y, dtype=float), np.asarray(mu, dtype=float)
    return max(0.0, float(((y - mu) ** 2 - mu).sum() / (mu ** 2).sum()))


def fit(spec: Spec, frame: pd.DataFrame, through_season: int) -> dict:
    """Fit on every played, usable row from FIRST_TRAIN_SEASON through `through_season`."""
    from xgboost import XGBRegressor
    tr = usable(spec, frame[~frame.upcoming]).dropna(subset=[spec.stat])
    tr = tr[tr.season.between(FIRST_TRAIN_SEASON, through_season)]
    model = XGBRegressor(**PARAMS)
    y = tr[spec.stat].values.astype(float)
    model.fit(_x(spec, tr), y)
    alpha = excess_variance(y, np.clip(model.predict(_x(spec, tr)), 1e-3, None)) if spec.overdispersed else 0.0
    return {"model": model, "dispersion": alpha, "n_train": len(tr)}


def predict_mean(spec: Spec, fitted: dict, rows: pd.DataFrame) -> np.ndarray:
    return np.clip(fitted["model"].predict(_x(spec, rows)), 1e-3, None)


def p_over(mu, line, dispersion: float = 0.0) -> np.ndarray:
    """P(count > line): the tail above floor(line), Poisson or (dispersion > 0) negative binomial."""
    k = np.floor(np.asarray(line, dtype=float))
    mu = np.asarray(mu, dtype=float)
    if dispersion <= 1e-9:
        return poisson.sf(k, mu)
    n = 1.0 / dispersion
    return nbinom.sf(k, n, n / (n + mu))


def win_per_unit(american: float) -> float:
    return american / 100.0 if american > 0 else 100.0 / abs(american)


def implied(american: float) -> float:
    return 100.0 / (american + 100.0) if american > 0 else abs(american) / (abs(american) + 100.0)


def expected_value(p: float, american: float) -> float:
    return p * (1 + win_per_unit(american)) - 1
