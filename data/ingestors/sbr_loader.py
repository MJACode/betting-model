"""
sbr_loader.py — Parses SportsBookReviewsOnline (SBR) historical Excel files
into the betting_model.db SQLite database.

HOW TO GET SBR DATA:
  1. Go to https://www.sportsbookreviewsonline.com/scoresoddsarchives/mlb/mlboddsarchives.htm
     (MLB) or /nhl/nhloddsarchives.htm (NHL)
  2. Download the Excel file for each season you need (2019–2024)
  3. Save to:
       data/raw/datawarehouse/mlb/mlb_2019.xlsx
       data/raw/datawarehouse/mlb/mlb_2020.xlsx  ... etc
       data/raw/datawarehouse/nhl/nhl_2019.xlsx  ... etc
  4. Run: python -m data.ingestors.sbr_loader

SBR FILE FORMAT (both MLB and NHL):
  Each game = 2 consecutive rows (away team row, then home team row).
  Columns vary slightly by sport — the parser handles both.

  MLB columns typically:
    Date | Rot | VH | Team | 1st | 2nd | 3rd | 4th | 5th | 6th | 7th | 8th | 9th | Final | Open | Close | ML | 2H

  NHL columns typically:
    Date | Rot | VH | Team | 1st | 2nd | 3rd | OT | Final | Open | Close | ML | 2H
"""

import sys
import re
from pathlib import Path
from datetime import datetime
import pandas as pd
from loguru import logger
import psycopg2.extras

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config import SPORTS
from data.db import get_connection, DBConnection


# ── Team name normalization ───────────────────────────────────────────────────
# SBR uses full city/team names. Map to 2-3 letter abbrevs used everywhere else.

MLB_NAME_MAP = {
    "Arizona Diamondbacks": "ARI", "Arizona": "ARI", "D-backs": "ARI",
    "Atlanta Braves": "ATL", "Atlanta": "ATL", "Braves": "ATL",
    "Baltimore Orioles": "BAL", "Baltimore": "BAL", "Orioles": "BAL",
    "Boston Red Sox": "BOS", "Boston": "BOS", "Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chi Cubs": "CHC", "Cubs": "CHC",
    "Chicago White Sox": "CWS", "Chi White Sox": "CWS", "White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cincinnati": "CIN", "Reds": "CIN",
    "Cleveland Guardians": "CLE", "Cleveland Indians": "CLE", "Cleveland": "CLE",
    "Colorado Rockies": "COL", "Colorado": "COL", "Rockies": "COL",
    "Detroit Tigers": "DET", "Detroit": "DET", "Tigers": "DET",
    "Houston Astros": "HOU", "Houston": "HOU", "Astros": "HOU",
    "Kansas City Royals": "KC", "Kansas City": "KC", "Royals": "KC",
    "Los Angeles Angels": "LAA", "LA Angels": "LAA", "Angels": "LAA",
    "Los Angeles Dodgers": "LAD", "LA Dodgers": "LAD", "Dodgers": "LAD",
    "Miami Marlins": "MIA", "Miami": "MIA", "Marlins": "MIA",
    "Milwaukee Brewers": "MIL", "Milwaukee": "MIL", "Brewers": "MIL",
    "Minnesota Twins": "MIN", "Minnesota": "MIN", "Twins": "MIN",
    "New York Mets": "NYM", "NY Mets": "NYM", "Mets": "NYM",
    "New York Yankees": "NYY", "NY Yankees": "NYY", "Yankees": "NYY",
    "Oakland Athletics": "OAK", "Oakland": "OAK", "Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Philadelphia": "PHI", "Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "Pittsburgh": "PIT", "Pirates": "PIT",
    "San Diego Padres": "SD", "San Diego": "SD", "Padres": "SD",
    "Seattle Mariners": "SEA", "Seattle": "SEA", "Mariners": "SEA",
    "San Francisco Giants": "SF", "San Francisco": "SF", "Giants": "SF",
    "St. Louis Cardinals": "STL", "St Louis Cardinals": "STL", "Cardinals": "STL",
    "Tampa Bay Rays": "TB", "Tampa Bay": "TB", "Rays": "TB",
    "Texas Rangers": "TEX", "Texas": "TEX", "Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Toronto": "TOR", "Blue Jays": "TOR",
    "Washington Nationals": "WSH", "Washington": "WSH", "Nationals": "WSH",
}

NHL_NAME_MAP = {
    "Anaheim Ducks": "ANA", "Anaheim": "ANA", "Ducks": "ANA",
    # Relocated franchise — canonical id is UTA across all seasons
    # (Arizona Coyotes → Utah Hockey Club → Utah Mammoth)
    "Arizona Coyotes": "UTA", "Arizona": "UTA", "Coyotes": "UTA",
    "Utah Hockey Club": "UTA", "Utah Mammoth": "UTA", "Utah": "UTA",
    "Boston Bruins": "BOS", "Boston": "BOS", "Bruins": "BOS",
    "Buffalo Sabres": "BUF", "Buffalo": "BUF", "Sabres": "BUF",
    "Carolina Hurricanes": "CAR", "Carolina": "CAR", "Hurricanes": "CAR",
    "Columbus Blue Jackets": "CBJ", "Columbus": "CBJ", "Blue Jackets": "CBJ",
    "Calgary Flames": "CGY", "Calgary": "CGY", "Flames": "CGY",
    "Chicago Blackhawks": "CHI", "Chicago": "CHI", "Blackhawks": "CHI",
    "Colorado Avalanche": "COL", "Colorado": "COL", "Avalanche": "COL",
    "Dallas Stars": "DAL", "Dallas": "DAL", "Stars": "DAL",
    "Detroit Red Wings": "DET", "Detroit": "DET", "Red Wings": "DET",
    "Edmonton Oilers": "EDM", "Edmonton": "EDM", "Oilers": "EDM",
    "Florida Panthers": "FLA", "Florida": "FLA", "Panthers": "FLA",
    "Los Angeles Kings": "LAK", "LA Kings": "LAK", "Kings": "LAK",
    "Minnesota Wild": "MIN", "Minnesota": "MIN", "Wild": "MIN",
    "Montreal Canadiens": "MTL", "Montreal": "MTL", "Canadiens": "MTL",
    "New Jersey Devils": "NJD", "New Jersey": "NJD", "Devils": "NJD",
    "Nashville Predators": "NSH", "Nashville": "NSH", "Predators": "NSH",
    "New York Islanders": "NYI", "NY Islanders": "NYI", "Islanders": "NYI",
    "New York Rangers": "NYR", "NY Rangers": "NYR", "Rangers": "NYR",
    "Ottawa Senators": "OTT", "Ottawa": "OTT", "Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Philadelphia": "PHI", "Flyers": "PHI",
    "Pittsburgh Penguins": "PIT", "Pittsburgh": "PIT", "Penguins": "PIT",
    "Seattle Kraken": "SEA", "Seattle": "SEA", "Kraken": "SEA",
    "San Jose Sharks": "SJS", "San Jose": "SJS", "Sharks": "SJS",
    "St. Louis Blues": "STL", "St Louis Blues": "STL", "Blues": "STL",
    "Tampa Bay Lightning": "TBL", "Tampa Bay": "TBL", "Lightning": "TBL",
    "Toronto Maple Leafs": "TOR", "Toronto": "TOR", "Maple Leafs": "TOR",
    "Vancouver Canucks": "VAN", "Vancouver": "VAN", "Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Vegas": "VGK", "Golden Knights": "VGK",
    "Washington Capitals": "WSH", "Washington": "WSH", "Capitals": "WSH",
    "Winnipeg Jets": "WPG", "Winnipeg": "WPG", "Jets": "WPG",
}


def normalize_team(name: str, sport: str) -> str:
    """Map SBR team name to standard 2-3 letter abbreviation."""
    name_map = MLB_NAME_MAP if sport == "MLB" else NHL_NAME_MAP
    name = str(name).strip()
    # Exact match first
    if name in name_map:
        return name_map[name]
    # Case-insensitive match
    name_lower = name.lower()
    for k, v in name_map.items():
        if k.lower() == name_lower:
            return v
    # Partial match (last resort)
    for k, v in name_map.items():
        if k.lower() in name_lower or name_lower in k.lower():
            return v
    logger.warning(f"Could not normalize team name: '{name}' ({sport})")
    return name.upper()[:3]


def parse_american_odds(val) -> float | None:
    """Convert SBR odds cell to float American odds. Returns None if unparseable."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip().replace(" ", "")
    if s in ("", "NL", "pk", "PK", "N/A"):
        return None
    # Remove trailing letters (e.g. "EV", "+100½")
    s = re.sub(r"[a-zA-Z½]", "", s)
    try:
        v = float(s)
        # SBR sometimes stores moneylines as e.g. 110 meaning +110 or -110
        # Convention: positive = home favourite unlikely; treat as-is since
        # the sign is usually present in the raw file.
        return v
    except (ValueError, TypeError):
        return None


def american_to_decimal(american: float | None) -> float | None:
    if american is None:
        return None
    if american > 0:
        return round(american / 100 + 1, 6)
    else:
        return round(100 / abs(american) + 1, 6)


def parse_sbr_file(filepath: Path, sport: str, season: int) -> list[dict]:
    """
    Parse one SBR Excel file. Returns a list of game dicts ready for DB insert.
    """
    logger.info(f"Parsing {filepath.name} ({sport} {season})")

    try:
        df = pd.read_excel(filepath, header=0, dtype=str)
    except Exception as e:
        logger.error(f"Could not read {filepath}: {e}")
        return []

    # Normalise column names
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # SBR alternates V (visitor/away) and H (home) rows
    # Find the VH column
    vh_col = next((c for c in df.columns if "vh" in c), None)
    team_col = next((c for c in df.columns if c in ("team", "teams")), None)
    final_col = next((c for c in df.columns if "final" in c), None)
    date_col = next((c for c in df.columns if "date" in c), None)

    if not all([vh_col, team_col, final_col, date_col]):
        logger.error(f"Could not identify required columns in {filepath.name}. Found: {list(df.columns)}")
        return []

    # Identify odds columns
    open_col  = next((c for c in df.columns if c == "open"), None)
    close_col = next((c for c in df.columns if c == "close"), None)
    ml_col    = next((c for c in df.columns if c in ("ml", "ml_close")), None)

    games = []
    rows = df.to_dict("records")
    i = 0
    while i < len(rows) - 1:
        away_row = rows[i]
        home_row = rows[i + 1]

        # Validate we have a V/H pair
        vh_away = str(away_row.get(vh_col, "")).strip().upper()
        vh_home = str(home_row.get(vh_col, "")).strip().upper()
        if vh_away != "V" or vh_home != "H":
            i += 1
            continue

        # Parse date (SBR stores as e.g. "401" meaning April 1, or "20190401")
        raw_date = str(away_row.get(date_col, "")).strip()
        game_date = _parse_sbr_date(raw_date, season)
        if game_date is None:
            i += 2
            continue

        # Teams
        away_team = normalize_team(str(away_row.get(team_col, "")), sport)
        home_team = normalize_team(str(home_row.get(team_col, "")), sport)

        # Scores
        away_score = _safe_float(away_row.get(final_col))
        home_score = _safe_float(home_row.get(final_col))

        # Odds — SBR puts the line on BOTH rows typically; we use away row
        open_line  = parse_american_odds(away_row.get(open_col))
        close_line = parse_american_odds(away_row.get(close_col))
        ml_away    = parse_american_odds(away_row.get(ml_col))
        ml_home    = parse_american_odds(home_row.get(ml_col))

        # For spread/total: SBR Open column = run/puck line value for the away team
        # Close column = closing total (O/U) for some formats — context-dependent
        # We store both and let feature_engine interpret them

        game_id = f"{sport}_{game_date}_{away_team}_{home_team}"

        # Determine outcome
        home_win = None
        if home_score is not None and away_score is not None:
            home_win = 1 if home_score > away_score else 0

        games.append({
            "game_id":       game_id,
            "sport":         sport,
            "season":        season,
            "game_date":     game_date,
            "home_team":     home_team,
            "away_team":     away_team,
            "home_score":    home_score,
            "away_score":    away_score,
            "home_win":      home_win,
            "data_source":   "sbr",
            "ml_away_open":  ml_away,
            "ml_home_open":  ml_home,
            "ml_away_close": None,
            "ml_home_close": None,
            "total_open":    open_line,
            "total_close":   close_line,
            "over_open_odds":  None,
            "under_open_odds": None,
            "over_close_odds": None,
            "under_close_odds":None,
        })
        i += 2

    logger.success(f"Parsed {len(games)} games from {filepath.name}")
    return games


def _parse_sbr_date(raw: str, season: int) -> str | None:
    """Convert SBR date formats to ISO YYYY-MM-DD."""
    raw = str(raw).strip().replace("/", "").replace("-", "")
    if not raw or raw in ("nan", ""):
        return None
    try:
        # Full 8-digit date: 20190401
        if len(raw) == 8:
            return datetime.strptime(raw, "%Y%m%d").strftime("%Y-%m-%d")
        # 3-4 digit: 401 = April 1, 1025 = October 25
        if len(raw) in (3, 4):
            mmdd = raw.zfill(4)
            return datetime.strptime(f"{season}{mmdd}", "%Y%m%d").strftime("%Y-%m-%d")
    except ValueError:
        pass
    logger.warning(f"Could not parse date: '{raw}' for season {season}")
    return None


def _safe_float(val) -> float | None:
    try:
        v = float(str(val).strip())
        return v if not pd.isna(v) else None
    except (ValueError, TypeError):
        return None


def load_to_db(games: list[dict], conn: DBConnection) -> tuple[int, int]:
    """Upsert games and odds into the database. Returns (games_inserted, odds_inserted)."""
    now = datetime.utcnow().isoformat()
    cursor = conn._conn.cursor()

    # ── games ─────────────────────────────────────────────────────────────────
    game_rows = [
        (
            g["game_id"], g["sport"], g["season"], g["game_date"],
            g["home_team"], g["away_team"],
            g["home_score"], g["away_score"], g["home_win"],
            g["data_source"], now,
        )
        for g in games
    ]
    psycopg2.extras.execute_batch(cursor, """
        INSERT INTO games
            (game_id, sport, season, game_date, home_team, away_team,
             home_score, away_score, home_win, data_source, updated_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT(game_id) DO UPDATE SET
            home_score  = EXCLUDED.home_score,
            away_score  = EXCLUDED.away_score,
            home_win    = EXCLUDED.home_win,
            updated_at  = EXCLUDED.updated_at
    """, game_rows, page_size=500)
    games_n = len(game_rows)

    # ── odds ──────────────────────────────────────────────────────────────────
    h2h_rows, totals_rows, spreads_rows = [], [], []

    for g in games:
        if g.get("ml_home_open") is not None or g.get("ml_away_open") is not None:
            h2h_rows.append((
                g["game_id"], g["sport"], "h2h", "sbr_consensus", "open", g["game_date"],
                g.get("ml_home_open"), g.get("ml_away_open"),
            ))
        if g.get("ml_home_close") is not None or g.get("ml_away_close") is not None:
            h2h_rows.append((
                g["game_id"], g["sport"], "h2h", "sbr_consensus", "close", g["game_date"],
                g.get("ml_home_close"), g.get("ml_away_close"),
            ))
        if g.get("total_open") is not None:
            totals_rows.append((
                g["game_id"], g["sport"], "totals", "sbr_consensus", "open", g["game_date"],
                g.get("total_open"), g.get("over_open_odds"), g.get("under_open_odds"),
            ))
        if g.get("total_close") is not None:
            totals_rows.append((
                g["game_id"], g["sport"], "totals", "sbr_consensus", "close", g["game_date"],
                g.get("total_close"), g.get("over_close_odds"), g.get("under_close_odds"),
            ))
        if g.get("spread_home") is not None:
            spreads_rows.append((
                g["game_id"], g["sport"], "spreads", "sbr_consensus", "open", g["game_date"],
                g["spread_home"],
            ))

    if h2h_rows:
        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO odds
                (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                 home_price, away_price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, h2h_rows, page_size=500)

    if totals_rows:
        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO odds
                (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                 total_line, over_price, under_price)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, totals_rows, page_size=500)

    if spreads_rows:
        psycopg2.extras.execute_batch(cursor, """
            INSERT INTO odds
                (game_id, sport, market, bookmaker, snapshot_type, snapshot_at,
                 spread_home)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT DO NOTHING
        """, spreads_rows, page_size=500)

    odds_n = len(h2h_rows) + len(totals_rows) + len(spreads_rows)
    conn.commit()
    return games_n, odds_n


def parse_csv_file(filepath: Path, sport: str) -> list[dict]:
    """
    Parse a flat CSV file where each row is one game.
    Expected columns:
      game id, date, away team, away score, away ml open, away ml close,
      over open, over open odds, over close, over close odds,
      home team, home score, home ml open, home ml close,
      under open, under open odds, under close, under close odds
    """
    logger.info(f"Parsing CSV {filepath.name} ({sport})")
    try:
        df = pd.read_csv(filepath, dtype=str)
    except Exception as e:
        logger.error(f"Could not read {filepath}: {e}")
        return []

    df.columns = [c.strip().lower() for c in df.columns]

    required = {"date", "away team", "home team", "away score", "home score"}
    missing = required - set(df.columns)
    if missing:
        logger.error(f"CSV missing required columns: {missing}")
        return []

    games = []
    for _, row in df.iterrows():
        raw_date = str(row.get("date", "")).strip()
        # Date is YYYYMMDD — derive season from year
        if len(raw_date) == 8:
            try:
                game_date = datetime.strptime(raw_date, "%Y%m%d").strftime("%Y-%m-%d")
                season = int(raw_date[:4])
            except ValueError:
                logger.warning(f"Could not parse date: '{raw_date}'")
                continue
        else:
            logger.warning(f"Unexpected date format: '{raw_date}'")
            continue

        away_team  = str(row.get("away team", "")).strip().upper()
        home_team  = str(row.get("home team", "")).strip().upper()
        away_score = _safe_float(row.get("away score"))
        home_score = _safe_float(row.get("home score"))

        home_win = None
        if home_score is not None and away_score is not None:
            home_win = 1 if home_score > away_score else 0

        game_id = f"{sport}_{game_date}_{away_team}_{home_team}"

        # MLB runline is always -1.5 for the home team (fixed line)
        spread_home = -1.5 if sport == "MLB" else None

        games.append({
            "game_id":         game_id,
            "sport":           sport,
            "season":          season,
            "game_date":       game_date,
            "home_team":       home_team,
            "away_team":       away_team,
            "home_score":      home_score,
            "away_score":      away_score,
            "home_win":        home_win,
            "data_source":     "sbr_csv",
            "ml_away_open":    parse_american_odds(row.get("away ml open")),
            "ml_away_close":   parse_american_odds(row.get("away ml close")),
            "ml_home_open":    parse_american_odds(row.get("home ml open")),
            "ml_home_close":   parse_american_odds(row.get("home ml close")),
            "total_open":      _safe_float(row.get("over open")),
            "over_open_odds":  parse_american_odds(row.get("over open odds")),
            "under_open_odds": parse_american_odds(row.get("under open odds")),
            "total_close":     _safe_float(row.get("over close")),
            "over_close_odds": parse_american_odds(row.get("over close odds")),
            "under_close_odds":parse_american_odds(row.get("under close odds")),
            "spread_home":     spread_home,
        })

    logger.success(f"Parsed {len(games)} games from {filepath.name}")
    return games


def load_sport(sport: str, conn: DBConnection) -> None:
    """Load all SBR files for a given sport from data/raw/sbr/{sport.lower()}/."""
    sbr_dir = SPORTS[sport]["sbr_dir"]
    if not sbr_dir.exists():
        logger.warning(f"SBR directory not found: {sbr_dir}")
        return

    total_games = total_odds = 0

    # CSV files — one row per game, multi-season, no season in filename needed
    for filepath in sorted(sbr_dir.glob("*.csv")):
        games = parse_csv_file(filepath, sport)
        if games:
            g, o = load_to_db(games, conn)
            total_games += g
            total_odds  += o

    # Excel files — one file per season, two rows per game (legacy SBR format)
    for filepath in sorted(sbr_dir.glob("*.xls*")):
        match = re.search(r"(\d{4})", filepath.stem)
        if not match:
            logger.warning(f"Could not extract season from filename: {filepath.name}")
            continue
        season = int(match.group(1))
        games = parse_sbr_file(filepath, sport, season)
        if games:
            g, o = load_to_db(games, conn)
            total_games += g
            total_odds  += o

    if total_games == 0:
        logger.warning(f"No games loaded for {sport} — add CSV or Excel files to {sbr_dir}")
    else:
        logger.success(f"{sport}: loaded {total_games} games, {total_odds} odds records")


def main():
    """Load all SBR data for all sports."""
    logger.info("SBR Loader starting")
    conn = get_connection()
    try:
        for sport in SPORTS:
            load_sport(sport, conn)
    finally:
        conn.close()
    logger.success("SBR Loader complete")


if __name__ == "__main__":
    main()
