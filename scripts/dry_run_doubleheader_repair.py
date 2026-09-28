#!/usr/bin/env python3
"""
DRY RUN. Re-grade the settled BETs stored on collapsed 2026 MLB doubleheader
rows against the game each one was actually for. READ-ONLY: this file has no
write path at all.

    python -m scripts.dry_run_doubleheader_repair                  # DATABASE_URL, read-only session
    python -m scripts.dry_run_doubleheader_repair --print-sql      # the SELECTs, parameters inlined
    python -m scripts.dry_run_doubleheader_repair --rows rows.json # rows those SELECTs returned
    ... --markdown report.md --json report.json

WHY. Until data/mlb_game_id.py gave game 2 its own `_G2` id, both games of a
doubleheader were stored on ONE `games` row (MLB_<date>_<away>_<home>). A pick
on that row was graded on whichever game's final and box score landed on it.
The Stats API lists 25 game-2s in 2026; 19 of the collapsed rows carry picks,
and 32 of those picks are settled BETs.

WHAT IT DOES, per settled BET on a collapsed row:
  1. Works out which game (G1 or G2) the bet was for. Evidence, strongest
     first; the first one that decides wins, and every one is reported:
       sid      - the DraftKings selection family in the pick's dk_bet_link:
                  when it was on the board (first/last DK snapshot carrying it)
                  against each game's first pitch and end. A family still up
                  after game 1 ended is game 2's; one that left the board
                  while later snapshots kept coming, before game 2's first
                  pitch, is game 1's;
       pitcher  - a pitcher prop belongs to the game that pitcher pitched in
                  (a starter pitches in one game of a doubleheader);
       live     - an in-play bet was written while one game was live;
       created  - a pre-game bet written after game 1 ENDED and before game 2
                  began (one written during game 1 proves nothing);
       time     - the pick's own game_time is nearest that game's start.
  2. Grades it on that game's real final from the Stats API (linescore for
     game lines and F5, boxscore player stats for props), with the SAME math
     the settler uses (paper_tracker._compute_result and its prop compare,
     including the DNP -> NO_ACTION and missing-price -> -110 rules).
  3. Flags whether the bet was public: a Discord post (push_sent kinds
     discord_signal / discord_live -- tracking/discord_publish.py), a phone
     push (new_bet / live_signal), counted in the app's Track Record
     (v_public_track_record's predicate), a leg of the public parlay track
     record, or inside a published daily recap (results_snapshots).

It never writes: every statement below is a SELECT, the live path opens the
session READ ONLY and rolls back, and nothing here calls commit. The Stats API
calls are GETs. It is a report for Matt to decide on; any repair is a
separate, reviewed change.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SEASON = 2026
STATS = "https://statsapi.mlb.com"

# ── SQL: SELECT only ─────────────────────────────────────────────────────────

BETS_SQL = """
SELECT p.pick_id, p.game_id, p.game_date, p.model_id, p.pick_side,
       p.pick_label, p.player_id, p.player_key, p.prop_market, p.scored_line,
       p.dk_odds, p.decision_odds, p.recommended_bet, p.result,
       p.profit_flat, p.profit_kelly, p.game_time, p.created_at,
       p.settled_at, p.is_live, p.dk_bet_link, p.condition_status
  FROM picks p
 WHERE p.game_id = ANY(%s)
   AND p.signal_type = 'BET'
   AND p.result IS NOT NULL
 ORDER BY p.game_id, p.pick_id"""

ROWS_SQL = """
SELECT g.game_id, g.commence_time, g.first_pitch_at, g.away_score,
       g.home_score, g.away_score_f5, g.home_score_f5,
       (SELECT MIN(s.snapshot_at) FROM live_game_state s
         WHERE s.game_id = g.game_id AND s.abstract_game_state = 'Final'
           AND s.home_score IS NOT NULL) AS final_at
  FROM games g
 WHERE g.game_id = ANY(%s)"""

# When each BET's DraftKings MARKET was on the stored board. The sid is
# 0QA<market>#<outcome>... (props, F5) or 0OU<market><O|U><line>_n (totals); a
# line move mints a new outcome id inside the same market, so the market id is
# the family. On a collapsed row both games' markets sit side by side: game 1's
# family stops at game 1's first pitch (or, an in-play one, by its end) while
# game 2's carries on to game 2's. board_next is the next snapshot of the same
# table on the row at least 5 minutes after the family was last seen -- proof
# the board was still being read when the family was gone.
SID_SQL = """
WITH b AS (
  SELECT pick_id, game_id,
         CASE WHEN model_id LIKE 'mlb_prop_%%' THEN 'props' ELSE 'odds' END AS src,
         substring(replace(split_part(dk_bet_link, 'outcomes=', 2), '%%23', '#')
                   FROM '^0[A-Z]{2}([0-9]+)') AS fam
    FROM picks
   WHERE pick_id = ANY(%s) AND dk_bet_link IS NOT NULL
),
o AS (
  SELECT game_id, 'odds' AS src, snapshot_at::timestamptz AS t,
         ARRAY[home_sid, away_sid, over_sid, under_sid] AS sids
    FROM odds
   WHERE bookmaker = 'draftkings' AND game_id IN (SELECT game_id FROM b)
  UNION ALL
  SELECT game_id, 'props', snapshot_at::timestamptz, ARRAY[over_sid, under_sid]
    FROM player_prop_odds
   WHERE bookmaker = 'draftkings' AND game_id IN (SELECT game_id FROM b)
),
fs AS (
  SELECT b.pick_id, MIN(o.t) AS fam_first, MAX(o.t) AS fam_last
    FROM b JOIN o ON o.game_id = b.game_id AND o.src = b.src
   WHERE EXISTS (SELECT 1 FROM unnest(o.sids) s
                  WHERE substring(s FROM '^0[A-Z]{2}([0-9]+)') = b.fam)
   GROUP BY b.pick_id
)
SELECT b.pick_id, b.fam, fs.fam_first, fs.fam_last,
       (SELECT MIN(o.t) FROM o WHERE o.game_id = b.game_id AND o.src = b.src
           AND o.t > fs.fam_last + interval '5 minutes') AS board_next
  FROM b JOIN fs ON fs.pick_id = b.pick_id
 ORDER BY b.pick_id"""


def _publish_sql() -> str:
    from tracking.publish_keys import live_lock_key_sql, lock_key_sql
    return f"""
SELECT k.pick_id, s.kind, s.sent_at, s.message_id
  FROM (SELECT p.pick_id, {lock_key_sql('p')} AS pre_key,
               {live_lock_key_sql('p')} AS live_key
          FROM picks p WHERE p.pick_id = ANY(%s)) k
  JOIN push_sent s ON s.lock_key IN (k.pre_key, k.live_key)
 ORDER BY k.pick_id, s.sent_at"""


# v_public_track_record's WHERE clause (pg_get_viewdef, read 2026-09-28): the
# picks the app's Track Record screen counts. It counts WIN/LOSS/PUSH only, so
# a NO_ACTION that re-grades to a result would ENTER the record.
TRACK_RECORD_SQL = r"""
SELECT p.pick_id,
       p.result IN ('WIN', 'LOSS', 'PUSH') AS counted_now
  FROM picks p
 WHERE p.pick_id = ANY(%s)
   AND p.signal_type = 'BET'
   AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%%\_live\_%%')
   AND p.game_date >= '2026-09-01'
   AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')"""

PARLAY_SQL = """
SELECT parlay_key, game_date, leg_keys, result, profit_flat
  FROM parlay_track_record
 WHERE game_date = ANY(%s)"""

RECAP_SQL = """
SELECT game_date, published_at, settled
  FROM results_snapshots
 WHERE scope = 'daily' AND sport IS NULL AND game_date = ANY(%s)"""

QUERIES = ("bets", "rows", "sids", "publish", "track_record", "parlays", "recaps")


def _render(sql: str, params: tuple) -> str:
    """The statement with its parameters inlined, for a SQL editor."""
    def lit(v):
        if isinstance(v, (list, tuple)):
            if all(isinstance(x, int) for x in v):
                return "ARRAY[" + ",".join(str(x) for x in v) + "]::bigint[]"
            return "ARRAY[" + ",".join("'" + str(x).replace("'", "''") + "'"
                                       for x in v) + "]::text[]"
        return "'" + str(v).replace("'", "''") + "'"
    return (sql % tuple(lit(p) for p in params)).replace("%%", "%")


# ── Stats API (GET only) ─────────────────────────────────────────────────────

def _get(path: str) -> dict:
    import requests
    r = requests.get(STATS + path, timeout=30)
    r.raise_for_status()
    return r.json()


def _ts(v) -> datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    s = str(v).strip().replace("Z", "+00:00")
    if " " in s and "T" not in s:
        s = s.replace(" ", "T", 1)
    if len(s) >= 3 and s[-3] in "+-" and s[-6] != ":" and ":" not in s[-3:]:
        s += ":00"                                    # '...+00' (Postgres text)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def fetch_doubleheaders(season: int = SEASON, through: str | None = None) -> list[dict]:
    """Every doubleheader date/matchup with a played game 2, both games with
    start, end, final, F5 and per-player box stats."""
    from data.ingestors.mlb_stats_ingestor import STATSAPI_TEAM_IDS
    through = through or datetime.now(timezone.utc).date().isoformat()
    sched = _get(f"/api/v1/schedule?sportId=1&season={season}&gameType=R"
                 f"&startDate={season}-03-01&endDate={through}&hydrate=linescore")
    by_key: dict[tuple, dict] = {}
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            if g.get("doubleHeader") not in ("Y", "S"):
                continue
            away = STATSAPI_TEAM_IDS.get(g["teams"]["away"]["team"]["id"])
            home = STATSAPI_TEAM_IDS.get(g["teams"]["home"]["team"]["id"])
            key = (g.get("officialDate"), away, home)
            by_key.setdefault(key, {})[int(g.get("gameNumber") or 1)] = g
    out = []
    for (date, away, home), games in sorted(by_key.items()):
        if 2 not in games or 1 not in games:
            continue
        if any(g["status"].get("detailedState") != "Final" for g in games.values()):
            continue
        dh = {"date": date, "away": away, "home": home,
              "collapsed_id": f"MLB_{date}_{away}_{home}", "games": {}}
        for n, g in games.items():
            dh["games"][n] = _game_detail(g)
        out.append(dh)
    return out


def _game_detail(g: dict) -> dict:
    pk = g["gamePk"]
    feed = _get(f"/api/v1.1/game/{pk}/feed/live?fields=gameData,gameInfo,"
                f"firstPitch,gameDurationMinutes,delayDurationMinutes")
    info = feed.get("gameData", {}).get("gameInfo", {})
    first = _ts(info.get("firstPitch")) or _ts(g.get("gameDate"))
    minutes = (info.get("gameDurationMinutes") or 180) + (info.get("delayDurationMinutes") or 0)
    ls = g.get("linescore", {})
    inn = ls.get("innings", [])
    f5 = inn[:5]
    box = _get(f"/api/v1/game/{pk}/boxscore")
    players = {}
    for side in ("away", "home"):
        t = box["teams"][side]
        for pid in t.get("pitchers", []):
            st = t["players"].get(f"ID{pid}", {}).get("stats", {}).get("pitching", {})
            try:
                ip = float(st.get("inningsPitched") or 0)
            except (TypeError, ValueError):
                ip = 0.0
            if ip > 0:        # the game-log ingest's rule: 0 IP is no row
                players.setdefault(str(pid), {}).update({
                    "innings_pitched": ip, "p_strikeouts": st.get("strikeOuts"),
                    "p_walks": st.get("baseOnBalls"), "p_hits_allowed": st.get("hits"),
                    "p_earned_runs": st.get("earnedRuns"),
                    "starter": t["pitchers"][0] == pid})
        for pid in t.get("batters", []):
            st = t["players"].get(f"ID{pid}", {}).get("stats", {}).get("batting", {})
            if st.get("atBats") is None:
                continue
            h, d2, d3, hr = (int(st.get(k) or 0) for k in
                             ("hits", "doubles", "triples", "homeRuns"))
            players.setdefault(str(pid), {}).update({
                "hits": h, "total_bases": h + d2 + 2 * d3 + 3 * hr, "home_runs": hr,
                "rbi": st.get("rbi"), "runs": st.get("runs"),
                "stolen_bases": st.get("stolenBases"), "walks": st.get("baseOnBalls")})
    return {
        "game_pk": pk, "game_number": int(g.get("gameNumber") or 1),
        "scheduled": g.get("gameDate"),
        "tbd": bool(g.get("status", {}).get("startTimeTBD")),
        "first_pitch": first.isoformat() if first else None,
        "end": (first + timedelta(minutes=minutes)).isoformat() if first else None,
        "away_runs": ls.get("teams", {}).get("away", {}).get("runs"),
        "home_runs": ls.get("teams", {}).get("home", {}).get("runs"),
        "away_f5": sum(int(i.get("away", {}).get("runs") or 0) for i in f5) if len(f5) == 5 else None,
        "home_f5": sum(int(i.get("home", {}).get("runs") or 0) for i in f5) if len(f5) == 5 else None,
        "players": players,
    }


# ── which game ───────────────────────────────────────────────────────────────

LIVE_MARGIN = timedelta(minutes=45)   # feeds go live up to ~36 min early
SLACK = timedelta(minutes=15)         # DK snapshot cadence after a final


@dataclass
class Assignment:
    game: int | None
    decided_by: str | None
    confidence: str
    evidence: dict = field(default_factory=dict)
    conflict: bool = False
    note: str = ""


def sid_game(sid: dict | None, s1, e1, s2) -> int | None:
    """Game 1 or 2 from when the bet's DK market family was on the board."""
    if not sid or not sid.get("fam_last"):
        return None
    first, last = _ts(sid["fam_first"]), _ts(sid["fam_last"])
    nxt = _ts(sid.get("board_next"))
    if first > e1 or last > e1 + SLACK:
        return 2                  # still offered after game 1 was over
    if nxt and nxt < s2:
        return 1                  # gone while the board was still read, pre-game 2
    return None


def assign_game(bet: dict, dh: dict, sid: dict | None) -> Assignment:
    g1, g2 = dh["games"][1], dh["games"][2]
    s1, s2 = _ts(g1["first_pitch"]), _ts(g2["first_pitch"])
    e1, e2 = _ts(g1["end"]), _ts(g2["end"])
    ev: dict[str, int | None] = {}
    notes = []

    ev["sid"] = sid_game(sid, s1, e1, s2) if sid else None

    if bet["model_id"].startswith("mlb_prop_pitcher_") and bet.get("player_id"):
        pid = str(bet["player_id"])
        inn = [n for n, g in ((1, g1), (2, g2))
               if "innings_pitched" in g["players"].get(pid, {})]
        ev["pitcher"] = inn[0] if len(inn) == 1 else None

    created = _ts(bet.get("created_at"))
    if bet.get("is_live") and created:
        ev["live"] = (1 if s1 - LIVE_MARGIN <= created <= e1
                      else 2 if s2 - LIVE_MARGIN <= created <= e2 else None)
    elif created:
        # A pre-game bet written after game 1 was OVER and before game 2
        # began can only be game 2's. One written DURING game 1 proves
        # nothing: game 1's in-play prices were on the row labelled pre-game.
        ev["created"] = 2 if e1 < created < s2 else None
        if created > s2:
            notes.append("written after both games had started")
        elif s1 < created <= e1:
            notes.append("written while game 1 was in play")
    gt = _ts(bet.get("game_time"))
    if gt:
        ev["time"] = 1 if abs(gt - s1) <= abs(gt - s2) else 2

    decided = next((k for k in ("sid", "pitcher", "live", "created", "time")
                    if ev.get(k)), None)
    game = ev.get(decided) if decided else None
    votes = {v for k, v in ev.items() if v and k != "time"}
    conflict = len(votes) > 1
    conf = "high" if decided in ("sid", "pitcher", "live", "created") else "low"
    if conflict:
        notes.append("evidence conflicts: " + ", ".join(
            f"{k}=G{v}" for k, v in ev.items() if v and k != "time"))
    return Assignment(game, decided, conf, ev, conflict, "; ".join(notes))


# ── grading (the settler's math) ─────────────────────────────────────────────

def grade(bet: dict, g: dict) -> tuple[str, float, float]:
    from tracking.paper_tracker import (_PROP_STAT_MAP, _compute_result,
                                        _ip_to_outs, _market_for_pick)
    odds = bet.get("decision_odds")
    odds = float(odds) if odds is not None else (
        float(bet["dk_odds"]) if bet.get("dk_odds") is not None else None)
    rec = float(bet.get("recommended_bet") or 0.0)
    line = float(bet["scored_line"]) if bet.get("scored_line") is not None else None
    mid = bet["model_id"]

    if mid.startswith("mlb_prop_"):
        ptype, col = _PROP_STAT_MAP[mid]
        row = g["players"].get(str(bet.get("player_id")), {})
        # A player with no row in that game's box did not play in it.
        played = "innings_pitched" in row if ptype == "pitcher" else "hits" in row
        if not played:
            actual = None
        elif col == "COMPUTE_OUTS":
            actual = _ip_to_outs(row["innings_pitched"])
        else:
            actual = row.get(col)
        if actual is None or line is None:
            return "NO_ACTION", 0.0, 0.0            # DNP in that game: DK voids
        return _prop_result(bet["pick_side"], float(actual), line, odds, rec)

    market = _market_for_pick(mid)
    if "1st_5_innings" in market:
        h, a = g["home_f5"], g["away_f5"]
        if h is None or a is None:
            return "NO_ACTION", 0.0, 0.0
        hw = int(h > a) if h != a else None
    else:
        h, a = g["home_runs"], g["away_runs"]
        hw = int(h > a) if h is not None and a is not None else None
    return _compute_result(bet["pick_side"], market, h, a, hw, None, None, odds,
                           line if "spreads" in market else None,
                           line if "totals" in market else None, rec)


def _prop_result(side, actual, line, odds, rec):
    from models.scorer import american_to_decimal
    if actual == line:
        return "PUSH", 0.0, 0.0
    won = (actual > line) == (side == "over")
    dec = american_to_decimal(odds if odds is not None else -110)
    if dec is None:
        return "NO_ACTION", 0.0, 0.0
    if won:
        return "WIN", round(100.0 * (dec - 1), 2), round(rec * (dec - 1), 2)
    return "LOSS", -100.0, round(-rec, 2)


# ── the report ───────────────────────────────────────────────────────────────

def build_report(dhs: list[dict], rows: dict) -> dict:
    by_id = {d["collapsed_id"]: d for d in dhs}
    sids = {int(r["pick_id"]): r for r in rows.get("sids", [])}
    pubs: dict[int, list] = {}
    for r in rows.get("publish", []):
        pubs.setdefault(int(r["pick_id"]), []).append(r["kind"])
    track = {int(r["pick_id"]): bool(r["counted_now"]) for r in rows.get("track_record", [])}
    legs: dict[str, list] = {}
    for p in rows.get("parlays", []):
        for k in json.loads(p["leg_keys"]) if isinstance(p["leg_keys"], str) else p["leg_keys"]:
            legs.setdefault(k, []).append(p["parlay_key"])
    recaps = {str(r["game_date"]): r for r in rows.get("recaps", [])}
    row_by_id = {r["game_id"]: r for r in rows.get("rows", [])}

    out = []
    for b in rows["bets"]:
        dh = by_id.get(b["game_id"])
        if dh is None:
            continue
        a = assign_game(b, dh, sids.get(int(b["pick_id"])))
        g = dh["games"].get(a.game) if a.game else None
        new = grade(b, g) if g else (None, None, None)
        other = dh["games"].get(3 - a.game) if a.game else None
        alt = grade(b, other) if other else (None, None, None)
        cur_flat = float(b["profit_flat"] or 0)
        kinds = sorted(set(pubs.get(int(b["pick_id"]), [])))
        key = f"{b['game_id']}:{b['model_id']}"
        recap = recaps.get(str(b["game_date"]))
        settled = _ts(b.get("settled_at"))
        in_recap = bool(recap and settled and _ts(recap["published_at"])
                        and settled <= _ts(recap["published_at"])
                        and b["result"] in ("WIN", "LOSS", "PUSH"))
        rowg = row_by_id.get(b["game_id"], {})
        scored_on = None
        for n, gg in dh["games"].items():
            if (rowg.get("home_score") is not None
                    and float(rowg["home_score"]) == gg["home_runs"]
                    and float(rowg["away_score"]) == gg["away_runs"]):
                scored_on = n if scored_on is None else scored_on
        out.append({
            "pick_id": int(b["pick_id"]), "game_id": b["game_id"],
            "model_id": b["model_id"], "label": b["pick_label"],
            "is_live": bool(b.get("is_live")),
            "assigned": f"G{a.game}" if a.game else "?",
            "decided_by": a.decided_by, "confidence": a.confidence,
            "evidence": a.evidence, "conflict": a.conflict, "note": a.note,
            "other_game": alt[0], "other_game_flat": alt[1], "row_score_is": f"G{scored_on}" if scored_on else "?",
            "current": b["result"], "current_flat": cur_flat,
            "corrected": new[0], "corrected_flat": new[1],
            "changes": new[0] is not None and (new[0] != b["result"]
                                               or abs((new[1] or 0) - cur_flat) > 0.005),
            "discord": [k for k in kinds if k.startswith("discord_")],
            "push": [k for k in kinds if not k.startswith("discord_")],
            "track_record": track.get(int(b["pick_id"])),
            "track_record_eligible": int(b["pick_id"]) in track,
            "parlay_legs": legs.get(key, []),
            "in_recap": in_recap,
        })
    changed = [r for r in out if r["changes"]]
    net = sum((r["corrected_flat"] or 0) - r["current_flat"] for r in changed) / 100.0
    hi = [r for r in changed if r["confidence"] == "high"]
    net_hi = sum((r["corrected_flat"] or 0) - r["current_flat"] for r in hi) / 100.0
    return {"bets": out, "n": len(out), "n_changed": len(changed),
            "net_units_change": round(net, 4),
            "n_changed_high_confidence": len(hi),
            "net_units_change_high_confidence": round(net_hi, 4)}


def markdown(rep: dict) -> str:
    h = ("| pick | game_id | market | label | assigned | by | current | cur u | corrected | new u | public |\n"
         "|---|---|---|---|---|---|---|---|---|---|---|")
    lines = [h]
    for r in rep["bets"]:
        pub = []
        if r["discord"]:
            pub.append("Discord")
        if r["track_record"]:
            pub.append("Track Record")
        elif r["track_record_eligible"]:
            pub.append("Track Record (if graded)")
        if r["parlay_legs"]:
            pub.append("parlay record")
        if r["in_recap"]:
            pub.append("recap")
        if r["push"]:
            pub.append("push")
        cf = r["corrected_flat"]
        lines.append(
            f"| {r['pick_id']} | {r['game_id']} | {r['model_id']} | {r['label']} | "
            f"{r['assigned']}{' ⚠' if r['conflict'] else ''} | {r['decided_by']} | "
            f"{r['current']} | {r['current_flat']/100:+.2f} | "
            f"{r['corrected'] or '?'}{' *' if r['changes'] else ''} | "
            f"{'' if cf is None else f'{cf/100:+.2f}'} | {', '.join(pub) or '-'} |")
    lines.append("")
    lines.append(f"{rep['n']} BETs; {rep['n_changed']} change; "
                 f"net {rep['net_units_change']:+.2f}u (1u flat, settler math). "
                 f"High-confidence assignments only: {rep['n_changed_high_confidence']} change, "
                 f"net {rep['net_units_change_high_confidence']:+.2f}u; the rest are decided "
                 f"by game_time alone.")
    return "\n".join(lines)


def _read_only_rows(ids: list[str]) -> dict:
    from data.db import get_connection
    conn = get_connection()
    try:
        # Session READ ONLY: the server itself refuses any write on it.
        conn._conn.rollback()
        conn._conn.cursor().execute(
            "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        rows = {}

        def q(name, sql, params):
            cur = conn._conn.cursor()
            cur.execute(sql, params)
            cols = [c[0] for c in cur.description]
            rows[name] = [dict(zip(cols, r)) for r in cur.fetchall()]
        q("bets", BETS_SQL, (ids,))
        pids = [int(b["pick_id"]) for b in rows["bets"]]
        dates = sorted({str(b["game_date"]) for b in rows["bets"]})
        q("rows", ROWS_SQL, (ids,))
        q("sids", SID_SQL, (pids,))
        q("publish", _publish_sql(), (pids,))
        q("track_record", TRACK_RECORD_SQL, (pids,))
        q("parlays", PARLAY_SQL, (dates,))
        q("recaps", RECAP_SQL, (dates,))
        return rows
    finally:
        conn._conn.rollback()
        conn.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--rows", help="JSON {query name: rows} from --print-sql's SELECTs")
    ap.add_argument("--schedule", help="cached fetch_doubleheaders() JSON")
    ap.add_argument("--save-schedule", help="write the Stats API fetch here (local file)")
    ap.add_argument("--print-sql", action="store_true")
    ap.add_argument("--pick-ids", help="comma list, for --print-sql of the per-pick queries")
    ap.add_argument("--markdown")
    ap.add_argument("--json")
    a = ap.parse_args()

    if a.schedule:
        dhs = json.loads(Path(a.schedule).read_text())
        for d in dhs:                              # JSON keys are strings
            d["games"] = {int(k): v for k, v in d["games"].items()}
    else:
        dhs = fetch_doubleheaders()
        if a.save_schedule:
            Path(a.save_schedule).write_text(json.dumps(dhs))
    ids = [d["collapsed_id"] for d in dhs]

    if a.print_sql:
        pids = [int(x) for x in (a.pick_ids or "0").split(",")]
        print("-- bets\n" + _render(BETS_SQL, (ids,)) + ";")
        print("-- rows\n" + _render(ROWS_SQL, (ids,)) + ";")
        print("-- sids\n" + _render(SID_SQL, (pids,)) + ";")
        print("-- publish\n" + _render(_publish_sql(), (pids,)) + ";")
        print("-- track_record\n" + _render(TRACK_RECORD_SQL, (pids,)) + ";")
        return 0

    rows = json.loads(Path(a.rows).read_text()) if a.rows else _read_only_rows(ids)
    rep = build_report(dhs, rows)
    md = markdown(rep)
    print(md)
    if a.markdown:
        Path(a.markdown).write_text(md + "\n")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
