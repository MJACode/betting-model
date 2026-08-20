"""
verify_cfbd.py — one-time CFBD endpoint + parser verification spike.

WHY THIS EXISTS
    collegefootballdata.com is blocked by the dev sandbox's egress proxy, so
    the parsers in data/ingestors/cfbd_ingestor.py were written against CFBD's
    documented shapes rather than a live payload. Every field is read through
    _pick(), which accepts several candidate spellings — this script proves
    which ones are actually right.

WHAT IT DOES (read-only — never writes to the DB)
    For each endpoint the ingestor uses:
      • confirms it responds and the free-tier key has access
      • prints the real top-level keys of a sample record
      • runs our parser over it and reports how many rows came back
      • flags every parsed field that is None for >90% of rows — those are the
        _pick() candidate lists that need a real key name added

    Then prints the FBS school list (the canonical team ids) so
    config.NCAAF_ODDS_API_MAP can be filled in for any Odds API name the
    resolver would get wrong.

USAGE
    export CFBD_API_KEY=...        # https://collegefootballdata.com/key
    python -m scripts.verify_cfbd            # defaults to season 2024
    python -m scripts.verify_cfbd --season 2023 --week 5

Paste the output back and the fixes land in the _pick() candidate lists only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from data.ingestors import cfbd_ingestor as cf  # noqa: E402

NULL_THRESHOLD = 0.90


def _sample_keys(payload, limit: int = 40) -> str:
    if isinstance(payload, list) and payload and isinstance(payload[0], dict):
        return ", ".join(sorted(payload[0].keys())[:limit])
    if isinstance(payload, dict):
        return ", ".join(sorted(payload.keys())[:limit])
    return f"(unexpected shape: {type(payload).__name__})"


def _null_report(rows: list[dict], ignore: set[str] | None = None) -> list[str]:
    """Fields that are None for >90% of parsed rows — i.e. likely _pick misses."""
    ignore = ignore or set()
    if not rows:
        return []
    bad = []
    for field in rows[0]:
        if field in ignore or field.startswith("_"):
            continue
        nulls = sum(1 for r in rows if r.get(field) is None)
        if nulls / len(rows) > NULL_THRESHOLD:
            bad.append(f"{field} ({nulls}/{len(rows)} null)")
    return bad


def _check(label: str, payload, parser, *args, ignore=None) -> None:
    print(f"\n── {label} " + "─" * max(0, 60 - len(label)))
    if payload is None:
        print("  ✗ NO RESPONSE — endpoint unreachable, or not on the free tier.")
        return
    n_raw = len(payload) if isinstance(payload, list) else 1
    print(f"  raw records : {n_raw}")
    print(f"  raw keys    : {_sample_keys(payload)}")
    try:
        parsed = parser(payload, *args)
    except Exception as exc:                              # noqa: BLE001
        print(f"  ✗ PARSER RAISED: {type(exc).__name__}: {exc}")
        return
    rows = list(parsed.values()) if isinstance(parsed, dict) else parsed
    if isinstance(parsed, dict):
        rows = [r if isinstance(r, dict) else {"value": r} for r in rows]
    print(f"  parsed rows : {len(rows)}")
    if not rows:
        print("  ✗ PARSER RETURNED NOTHING — key names almost certainly differ.")
        return
    misses = _null_report(rows, ignore)
    if misses:
        print("  ⚠ always-null fields (add the real key to that _pick list):")
        for m in misses:
            print(f"      - {m}")
    else:
        print("  ✓ every parsed field populated")
    print(f"  example     : { {k: v for k, v in list(rows[0].items())[:8]} }")


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify CFBD endpoints + parsers")
    ap.add_argument("--season", type=int, default=2024)
    ap.add_argument("--week", type=int, default=5)
    args = ap.parse_args()

    if not config.CFBD_API_KEY:
        print("CFBD_API_KEY is not set.\n"
              "Get a free key (email only, no card) at "
              "https://collegefootballdata.com/key, then:\n"
              "    export CFBD_API_KEY=...")
        return 1

    season, week = args.season, args.week
    print(f"CFBD verification — season {season}, week {week}")
    print(f"base url: {config.CFBD_BASE_URL}")

    teams_payload = cf._get("/teams/fbs", year=season)
    _check("/teams/fbs", teams_payload, cf.parse_teams,
           ignore={"division", "alt_names", "mascot", "abbreviation"})

    games_payload = cf._get("/games", year=season, seasonType="regular")
    _check("/games", games_payload, cf.parse_games,
           ignore={"home_score", "away_score", "home_win", "commence_time"})

    lines_payload = cf._get("/lines", year=season, seasonType="regular")
    _check(f"/lines (provider={config.CFBD_LINES_PROVIDER})", lines_payload,
           cf.parse_lines, config.CFBD_LINES_PROVIDER,
           ignore={"spread_home", "total_line", "home_price", "away_price",
                   "over_price", "under_price"})
    if lines_payload:
        providers = sorted({str(l.get("provider")) for g in lines_payload
                            for l in (g.get("lines") or [])})
        print(f"  providers available: {providers}")
        print(f"  → config.CFBD_LINES_PROVIDER is '{config.CFBD_LINES_PROVIDER}'; "
              f"pick the one with the widest history if it is not listed.")

    # /games/teams needs the id map, so rebuild it from the schedule we just pulled
    parsed_games = cf.parse_games(games_payload) if games_payload else []
    id_map = {g["_cfbd_id"]: g["game_id"] for g in parsed_games if g.get("_cfbd_id")}
    meta = {g["game_id"]: {"season": g["season"], "week": g["week"],
                           "season_type": "regular", "game_date": g["game_date"],
                           "neutral_site": g["neutral_site"],
                           "conference_game": g["conference_game"]}
            for g in parsed_games}
    _check("/games/teams", cf._get("/games/teams", year=season, week=week,
                                   seasonType="regular"),
           cf.parse_team_game_stats, id_map, meta,
           ignore={"sacks", "tackles_for_loss", "season_type"})
    if id_map:
        print(f"  id map built from /games: {len(id_map)} game ids")
    else:
        print("  ⚠ id map EMPTY — /games did not expose a numeric game id, so "
              "box scores cannot be joined. Check the 'id' key name.")

    _check("/ratings/sp", cf._get("/ratings/sp", year=season),
           cf.parse_ratings, "sp")
    _check("/ratings/srs", cf._get("/ratings/srs", year=season),
           cf.parse_ratings, "srs")
    _check("/ratings/elo (week-indexed)",
           cf._get("/ratings/elo", year=season, week=week), cf.parse_ratings, "elo")
    _check("/talent", cf._get("/talent", year=season), cf.parse_talent)
    _check("/player/returning", cf._get("/player/returning", year=season),
           cf.parse_returning)

    # The windowed call is what makes the snapshots leak-free — if startWeek /
    # endWeek are not honoured, every in-season row would carry full-season
    # totals and the models would train on the future.
    print("\n── WINDOWED advanced stats (leak-critical) " + "─" * 18)
    full = cf._get("/stats/season/advanced", year=season)
    part = cf._get("/stats/season/advanced", year=season, startWeek=1, endWeek=3)
    _check("/stats/season/advanced (endWeek=3)", part, cf.parse_advanced_stats,
           ignore={"plays_per_game", "seconds_per_play"})
    if full and part:
        pf, pp = cf.parse_advanced_stats(full), cf.parse_advanced_stats(part)
        team = next((t for t in pp if t in pf), None)
        if team:
            a, b = pf[team].get("epa_per_play_off"), pp[team].get("epa_per_play_off")
            print(f"  {team}: full-season EPA/play {a} vs weeks 1-3 {b}")
            if a is not None and b is not None and a == b:
                print("  ✗ IDENTICAL — startWeek/endWeek appear to be IGNORED.\n"
                      "    The snapshot builder would leak full-season data. Fix "
                      "before training: switch to per-week /stats/season/advanced "
                      "aggregation or compute EPA from /plays.")
            else:
                print("  ✓ windowing is honoured — snapshots are leak-free")

    print("\n── FBS schools (canonical team ids) " + "─" * 25)
    schools = cf.parse_teams(teams_payload)
    print(f"  {len(schools)} schools")
    for s in schools[:10]:
        print(f"    {s['school']!r:28} mascot={s['mascot']!r} conf={s['conference']!r}")
    print("    ...")
    print("\n  The Odds API lists NCAAF teams as '<school> <mascot>'. The resolver\n"
          "  strips the mascot automatically; add only the ones it gets wrong to\n"
          "  config.NCAAF_ODDS_API_MAP.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
