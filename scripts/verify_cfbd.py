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


def _lines_coverage(from_season: int, to_season: int) -> int:
    """
    Per-season, per-provider line coverage.

    This is the go/no-go for how far back the spread and totals models can
    train. DraftKings only launched in 2018 and reached most states in
    2019-2021, so its CFBD history is expected to thin out in the back seasons
    — and a season with no lines contributes ZERO rows to ncaaf_spread and
    ncaaf_over_under, however many games it has. Better to learn that here than
    after an eleven-season backfill.
    """
    print(f"Betting-line coverage {from_season}-{to_season}")
    print(f"configured providers (preference order): "
          f"{config.CFBD_LINES_PROVIDERS}\n")

    totals: dict = {}
    per_season: dict = {}
    for season in range(from_season, to_season + 1):
        payload = cf._get("/lines", year=season, seasonType="regular")
        if payload is None:
            print(f"  {season}: NO RESPONSE")
            continue
        counts: dict = {}
        for g in payload:
            for ln in (g.get("lines") or []):
                prov = str(ln.get("provider") or "?")
                has_spread = ln.get("spread") is not None
                has_total = (ln.get("overUnder") is not None
                             or ln.get("over_under") is not None)
                if has_spread or has_total:
                    c = counts.setdefault(prov, {"spread": 0, "total": 0})
                    c["spread"] += int(has_spread)
                    c["total"] += int(has_total)
        per_season[season] = (len(payload), counts)
        for prov, c in counts.items():
            t = totals.setdefault(prov, {"spread": 0, "total": 0, "seasons": 0})
            t["spread"] += c["spread"]
            t["total"] += c["total"]
            t["seasons"] += 1

    providers = sorted(totals, key=lambda p: -totals[p]["spread"])
    print(f"{'season':>7} {'games':>6}  " + "  ".join(f"{p[:12]:>12}" for p in providers))
    for season, (n_games, counts) in sorted(per_season.items()):
        cells = []
        for p in providers:
            c = counts.get(p)
            cells.append(f"{c['spread']:>12}" if c else f"{'—':>12}")
        print(f"{season:>7} {n_games:>6}  " + "  ".join(cells))

    print("\n(cells are games with a SPREAD from that provider)\n")
    print(f"{'provider':>14}  {'seasons':>7}  {'spreads':>8}  {'totals':>8}")
    for p in providers:
        t = totals[p]
        print(f"{p[:14]:>14}  {t['seasons']:>7}  {t['spread']:>8}  {t['total']:>8}")

    # We ingest EVERY configured provider and resolve preference at read time,
    # so the question is not "which one" but "is any season uncovered by all of
    # them" — a season no configured provider priced contributes zero rows to
    # ncaaf_spread / ncaaf_over_under, however many games it has.
    configured = {p.lower() for p in config.CFBD_LINES_PROVIDERS}
    present = {p.lower() for p in providers}
    print()
    missing_cfg = sorted(configured - present)
    if missing_cfg:
        print(f"  note: configured but absent from this window: {missing_cfg}")
    unconfigured = sorted(present - configured)
    if unconfigured:
        print(f"  note: available but NOT configured: {unconfigured} — add to "
              f"config.CFBD_LINES_PROVIDERS if a season is uncovered below.")

    uncovered = [
        season for season, (_, counts) in per_season.items()
        if not any(p.lower() in configured and c["spread"]
                   for p, c in counts.items())
    ]
    if uncovered:
        print(f"  ✗ NO configured provider priced: {sorted(uncovered)}")
        print(f"     Those seasons yield zero spread/totals training rows. Add a "
              f"deeper provider or narrow the backfill window.")
        return 1
    print(f"  ✓ every season {from_season}-{to_season} is covered by at least "
          f"one configured provider")
    for season, (_, counts) in sorted(per_season.items()):
        winner = next((p for p in config.CFBD_LINES_PROVIDERS
                       if counts.get(p) and counts[p]["spread"]), None)
        print(f"      {season}: {winner}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Verify CFBD endpoints + parsers")
    ap.add_argument("--season", type=int, default=2024)
    ap.add_argument("--week", type=int, default=5)
    ap.add_argument("--lines-coverage", action="store_true",
                    help="Per-season, per-provider betting-line coverage. Run "
                         "this BEFORE a multi-season backfill.")
    ap.add_argument("--from-season", type=int, default=2015)
    ap.add_argument("--to-season", type=int, default=2025)
    args = ap.parse_args()

    if not config.CFBD_API_KEY:
        print("CFBD_API_KEY is not set.\n"
              "Get a free key (email only, no card) at "
              "https://collegefootballdata.com/key, then:\n"
              "    export CFBD_API_KEY=...")
        return 1

    if args.lines_coverage:
        return _lines_coverage(args.from_season, args.to_season)

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
    _check(f"/lines (providers={config.CFBD_LINES_PROVIDERS})", lines_payload,
           cf.parse_lines, config.CFBD_LINES_PROVIDERS,
           ignore={"spread_home", "total_line", "home_price", "away_price",
                   "over_price", "under_price"})
    if lines_payload:
        providers = sorted({str(l.get("provider")) for g in lines_payload
                            for l in (g.get("lines") or [])})
        print(f"  providers available: {providers}")
        print(f"  → config.CFBD_LINES_PROVIDERS is {config.CFBD_LINES_PROVIDERS}; "
              f"run --lines-coverage to confirm every season is covered.")

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
