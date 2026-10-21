"""No NHL bet of any kind until both starting goalies are confirmed.

THE RULE (mike, 2026-10-20): "We should absolutely always know the goalie
matchup before making a bet as well." Every NHL model, present and future: nhl_moneyline,
nhl_moneyline_regulation, nhl_over_under, nhl_puckline, and the blocked-shots,
saves and assists props.

ONE EXEMPTION: THE SHOTS-ON-GOAL PROPS (mike, 2026-10-20: "Ok on shots on
goal"). config.NHL_GOALIE_GATE_EXEMPT names it. That model never reads the
goalie, and its record is its early price, so it keeps deciding at its
opening fetch. Every check here is per row, by model_id (`is_exempt`,
`is_gated_bet`): an exempt row passes untouched and costs no read, and a
model that is not named is gated, so a new NHL model waits by default.

WHY IT WAS NEEDED. `nhl_goalie_stats` holds one row per team per game, written
once at ~10:06Z from ESPN's probable starter (data/ingestors/
nhl_stats_ingestor.py). ESPN says whether that name is `expected` or
`confirmed`; the status was thrown away and the row never changed again. The
6am goalie did not start in 65 of 251 team-games 2026-10-01..10-19, and in 22
of 70 (31%) for 10-14..10-19. On 2026-10-20 MTL (a Fowler row, Dobes
confirmed) and SEA (Daccord row, Grubauer confirmed) both changed after the
write. The moneyline gate only checked that a row EXISTED; the totals card and
the prop cards had no goalie gate at all.

KNOWN, for one game, means for BOTH teams:
  1. the latest ESPN designation (`nhl_goalie_designations`, source 'espn')
     is 'confirmed';
  2. the `nhl_goalie_stats` row for that game and team names the same goalie
     (the designation poll rewrites the row when ESPN confirms someone else,
     data/ingestors/nhl_goalie_designations.py), so the model's inputs are the
     confirmed goalie's;
  3. if DailyFaceoff has a latest designation for that team, it names the same
     goalie. Its status is not required to be "Confirmed": DailyFaceoff is a
     veto on a disagreement, not a second confirmation, because it is behind
     Cloudflare and may never answer the worker (fail-open in the poll).

ESPN's 'confirmed' tracks the morning-skate signal and is looser than
DailyFaceoff's "Confirmed" (2026-10-20: ESPN confirmed Kuemper for LAK while
DailyFaceoff still said Likely). That is why condition 3 exists.

THE GAME-DAY BOUND IS DATA, NOT A CLOCK. Condition 2 needs the game-day
`nhl_goalie_stats` row, which exists only from the ~10:06Z write on game day
(after that morning's game-log top-up), and the poll rewrites rows; it never
creates one. So a game cannot be KNOWN before its own game day, and a game
whose 6am row was never written stays unknown all day (fail closed, and the
reason says so).

NAMES. Ids decide when both sides carry one (the stats row and the ESPN
designation are both resolved to NHL ids the same way). Otherwise names are
compared with accents and punctuation stripped (Dobeš / Dobes) and one small
first-name alias step (Matt / Matthew, Dan / Daniel, Sam / Samuel ...):
`same_goalie_name`. The last name must match exactly after that folding.

FAILS CLOSED. A read that raises means "not known": every game in the call
gets CHECK_FAILED, and the next pass asks again. A lost connection is
re-raised, because it means the caller's unit of work is gone.

ONE MODULE, three users: the scorer's two NHL side models
(models/scorer._nhl_game_day_reason) and its sport-level guard on every NHL
model scored through score_game; the totals and prop cards, which drop
unknown games before pooling; and `refuse_unknown`, the last line at every
INSERT site that writes NHL picks.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone

from loguru import logger

import config

SPORT = "NHL"
SOURCE_ESPN = "espn"
SOURCE_DAILYFACEOFF = "dailyfaceoff"
SOURCES = (SOURCE_ESPN, SOURCE_DAILYFACEOFF)
CONFIRMED = "confirmed"
# Written when ESPN lists the game but no probable starter for a team, so a
# withdrawn confirmation does not leave a stale 'confirmed' as the latest row.
NO_STARTER = "none"
CHECK_FAILED = "goalie check failed; not deciding this pass"
WAITING = "waiting for both confirmed starting goalies"

# Equivalent first names. Small on purpose: a goalie is identified by his last
# name plus this, and anything looser could match two people.
FIRST_NAME_ALIASES: tuple[frozenset, ...] = tuple(frozenset(g) for g in (
    {"matt", "matthew", "mat"},
    {"alex", "alexander", "alexandar", "aleksander", "aleksandr", "alexandre"},
    {"sam", "samuel"},
    {"dan", "daniel", "danny"},
    {"mike", "michael"},
    {"nick", "nicholas", "nicolas", "nico"},
    {"joe", "joey", "joseph"},
    {"jake", "jacob"},
    {"cal", "calvin"},
    {"zach", "zack", "zachary"},
    {"will", "william"},
    {"chris", "christopher"},
    {"tony", "anthony"},
    {"ben", "benjamin"},
    {"tom", "thomas"},
    {"dave", "david"},
    {"jeff", "jeffrey"},
    {"phil", "philip", "phillip", "philipp", "philippe"},
    {"ilya", "ilia"},
    {"dmitri", "dmitry", "dimitri"},
    {"pyotr", "petr"},
    {"jon", "jonathan"},
    {"ken", "kenneth"},
))


def _fold(text: str | None) -> str:
    """Lower case, accents gone, only letters and digits."""
    flat = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in flat.lower() if c.isalnum() and not unicodedata.combining(c))


def name_parts(name: str | None) -> tuple[str, str]:
    """(first, last), folded: the last word is the last name, everything before
    it the first ("Ukko-Pekka Luukkonen" and "Ukko Pekka Luukkonen" agree). A
    one-word name is all last name."""
    words = [w for w in (name or "").replace(".", " ").split() if _fold(w)]
    if not words:
        return "", ""
    return _fold(" ".join(words[:-1])), _fold(words[-1])


def _first_names_agree(a: str, b: str) -> bool:
    if not a or not b or a == b:
        return True
    return any(a in g and b in g for g in FIRST_NAME_ALIASES)


def same_goalie_name(a: str | None, b: str | None) -> bool:
    """True when two spellings name the same goalie. Never true for an empty name."""
    fa, la = name_parts(a)
    fb, lb = name_parts(b)
    if not la or not lb or la != lb:
        return False
    return _first_names_agree(fa, fb)


def same_goalie(a_id, a_name, b_id, b_name) -> bool:
    """Ids decide when both are present; otherwise the names do."""
    if a_id not in (None, "") and b_id not in (None, ""):
        return str(a_id) == str(b_id)
    return same_goalie_name(a_name, b_name)


# ── the decision, pure ───────────────────────────────────────────────────────

@dataclass
class Matchup:
    """One game's goalie state. `reason` None means KNOWN."""
    game_id: str
    reason: str | None
    known_at: datetime | None = None
    # team -> (player_id, player_name) of the confirmed starter, KNOWN games only
    starters: dict = field(default_factory=dict)


def _utc(v) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    text = str(v).strip().replace("Z", "+00:00")
    # nhl_goalie_stats.created_at is TEXT from now()::text: "... 10:06:12.12+00",
    # an hours-only offset older parsers refuse.
    if (" " in text or "T" in text) and text[-3] in "+-" and text[-2:].isdigit():
        text += ":00"
    try:
        d = datetime.fromisoformat(text)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def team_problem(team: str, espn: dict | None, stats: dict | None,
                 dailyfaceoff: dict | None) -> str | None:
    """None when this team's starter is known; otherwise what is missing, in
    words a reader of the pick row can act on."""
    if not espn or not espn.get("player_name") or espn.get("status") == NO_STARTER:
        return f"{team} no starter listed"
    if espn.get("status") != CONFIRMED:
        return f"{team} {espn.get('status') or 'unconfirmed'}"
    if not stats:
        return f"{team} no goalie row yet"
    if not same_goalie(stats.get("player_id"), stats.get("player_name"),
                       espn.get("player_id"), espn.get("player_name")):
        return (f"{team} goalie row names {stats.get('player_name')}, "
                f"ESPN confirmed {espn.get('player_name')}")
    if dailyfaceoff and dailyfaceoff.get("player_name") and not same_goalie_name(
            dailyfaceoff.get("player_name"), espn.get("player_name")):
        return (f"{team} DailyFaceoff names {dailyfaceoff.get('player_name')}, "
                f"ESPN confirmed {espn.get('player_name')}")
    return None


def assess(game_id: str, home: str, away: str, latest: dict, stats: dict) -> Matchup:
    """One game from the latest designations and the goalie rows. Pure.

    `latest`: {(game_id, team, source): row}; `stats`: {(game_id, team): row}.

    known_at is the moment the matchup became known: the later of each team's
    ESPN confirmation and its goalie row. DailyFaceoff is left out of it on
    purpose: a "Likely" turning "Confirmed" for the same goalie does not change
    the matchup, and must not make a game look newly known.
    """
    problems, starters, stamps = [], {}, []
    for team in (away, home):
        espn = latest.get((game_id, team, SOURCE_ESPN))
        row = stats.get((game_id, team))
        why = team_problem(team, espn, row, latest.get((game_id, team, SOURCE_DAILYFACEOFF)))
        if why:
            problems.append(why)
            continue
        starters[team] = (row.get("player_id") or espn.get("player_id"), espn.get("player_name"))
        stamps += [t for t in (_utc(espn.get("observed_at")), _utc(row.get("created_at"))) if t]
    if problems:
        return Matchup(game_id, f"{WAITING} ({'; '.join(problems)})")
    return Matchup(game_id, None, max(stamps) if stamps else None, starters)


# ── the reads ────────────────────────────────────────────────────────────────

_GAMES_SQL = "SELECT game_id, home_team, away_team FROM games WHERE game_id = ANY(%s)"
# Latest row per (game, team, source): the table is append-only history.
_LATEST_SQL = """
    SELECT DISTINCT ON (game_id, team, source)
           game_id, team, source, player_id, player_name, status, observed_at
    FROM nhl_goalie_designations
    WHERE game_id = ANY(%s)
    ORDER BY game_id, team, source, observed_at DESC
"""
# Newest first, as models.nhl_moneyline_anchored.listed_goalies reads it.
_STATS_SQL = """
    SELECT game_id, team, player_id, player_name, created_at
    FROM nhl_goalie_stats
    WHERE game_id = ANY(%s)
    ORDER BY created_at DESC
"""


def _select(conn, sql: str, params) -> list:
    """fetchall() inside a savepoint, so a failed read never poisons the
    caller's transaction (a card holding its model lock, a scorer's game)."""
    conn.execute("SAVEPOINT nhl_goalie_gate")
    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        try:
            conn.execute("ROLLBACK TO SAVEPOINT nhl_goalie_gate")
        except Exception:                                   # noqa: BLE001
            pass
        raise
    conn.execute("RELEASE SAVEPOINT nhl_goalie_gate")
    return rows


def matchup_states(conn, game_ids) -> dict[str, Matchup]:
    """{game_id: Matchup} for every id asked about. Fails closed."""
    ids = sorted({str(g) for g in game_ids if g})
    if not ids:
        return {}
    from data.db import ConnectionLost
    try:
        teams = {r[0]: (r[1], r[2]) for r in _select(conn, _GAMES_SQL, (ids,))}
        latest = {(r[0], r[1], r[2]): {"player_id": r[3], "player_name": r[4],
                                        "status": r[5], "observed_at": r[6]}
                  for r in _select(conn, _LATEST_SQL, (ids,))}
        stats: dict = {}
        for gid, team, pid, name, created in _select(conn, _STATS_SQL, (ids,)):
            stats.setdefault((gid, team), {"player_id": pid, "player_name": name,
                                           "created_at": created})
    except ConnectionLost:
        raise
    except Exception as exc:                                # noqa: BLE001 - fail closed
        logger.error(f"NHL goalie gate: read failed ({exc!r}); "
                     f"{len(ids)} game(s) treated as not known")
        return {g: Matchup(g, CHECK_FAILED) for g in ids}
    out = {}
    for g in ids:
        if g not in teams:
            out[g] = Matchup(g, f"{WAITING} (game not found)")
            continue
        home, away = teams[g]
        out[g] = assess(g, home, away, latest, stats)
    return out


def matchup_reasons(conn, game_ids) -> dict[str, str | None]:
    """{game_id: None when both starting goalies are known, else the reason}."""
    return {g: m.reason for g, m in matchup_states(conn, game_ids).items()}


def known_games(conn, game_ids) -> dict[str, datetime | None]:
    """{game_id: known_at} for the games whose matchup is known."""
    return {g: m.known_at for g, m in matchup_states(conn, game_ids).items() if m.reason is None}


def split_known(games: dict, reasons: dict) -> tuple[dict, dict]:
    """(the games that may produce a bet, {game_id: reason} for the rest)."""
    held = {g: reasons.get(g) or CHECK_FAILED for g in games if reasons.get(g, CHECK_FAILED)}
    return {g: v for g, v in games.items() if g not in held}, held


def log_held(label: str, held: dict) -> None:
    """One line per pass: how many games were held back, and why."""
    if not held:
        return
    detail = "; ".join(f"{g}: {r}" for g, r in sorted(held.items()))
    logger.info(f"{label}: {len(held)} NHL game(s) held back until both starting "
                f"goalies are confirmed -- {detail}")


# ── the last line, at every INSERT that writes NHL picks ─────────────────────

def is_nhl_bet(row: dict) -> bool:
    return (str(row.get("sport") or "").upper() == SPORT
            and row.get("signal_type") == "BET" and bool(row.get("game_id")))


def is_exempt(model_id) -> bool:
    """True for a model that does not wait for the goalies
    (config.NHL_GOALIE_GATE_EXEMPT: shots on goal, mike 2026-10-20)."""
    return bool(model_id) and model_id in config.NHL_GOALIE_GATE_EXEMPT


def is_gated_bet(row: dict) -> bool:
    """An NHL BET this rule holds back while its game's matchup is not known."""
    return is_nhl_bet(row) and not is_exempt(row.get("model_id"))


def refuse_unknown(conn, rows: list[dict], *, mode: str, label: str,
                   reasons: dict | None = None) -> list[dict]:
    """Every NHL BET whose game's goalie matchup is not known is refused.

    mode "drop": the row is removed (the cards write BET rows only, so a
    refused row has nothing to become). mode "none": the row is turned NONE
    with the reason in `downgrade_reason`, unsized, the way the scorer turns
    any other declined BET (models/scorer._downgrade). Rows that are not NHL
    BETs, and the exempt model's BETs (`is_exempt`), pass through untouched
    and cost no read. Logged at WARNING: reaching
    this line means a gate upstream of it did not hold. `reasons`, when given,
    is the caller's reading of the gate for these games (the scorer's
    once-a-game memo) and saves the read.
    """
    if mode not in ("drop", "none"):
        raise ValueError(f"refuse_unknown: unknown mode {mode!r}")
    bets = [r for r in rows if is_gated_bet(r)]
    if not bets:
        return rows
    if reasons is None:
        reasons = matchup_reasons(conn, {r["game_id"] for r in bets})
    out = []
    for r in rows:
        why = reasons.get(r.get("game_id"), CHECK_FAILED) if is_gated_bet(r) else None
        if not why:
            out.append(r)
            continue
        logger.warning(f"{label}: refused NHL BET {r.get('pick_label')} "
                       f"({r.get('model_id')}, {r.get('game_id')}) -- {why}")
        if mode == "none":
            out.append({**r, "signal_type": "NONE", "kelly_fraction": 0.0,
                        "recommended_bet": 0.0, "downgrade_reason": why})
    return out
