#!/usr/bin/env python3
"""Post one finished day's results recap that never went out.

    python -m scripts.backfill_results_recap --date 2026-10-05
    python -m scripts.backfill_results_recap --date 2026-10-05 --apply

2026-10-05 was never recapped. Measured 2026-10-14: push_sent has no
discord_results:2026-10-05 and no x_results:2026-10-05. The 6am recap that
morning found nothing counting settled yet, and nothing asked again for that
date. post_missed_recap only retries yesterday.

Dry-run is the default and posts nothing. --apply calls
tracking.discord_notifier.notify_discord_results and
tracking.x_publisher.notify_x_results for that date. Those functions still
refuse a day that is not over, still ledger a post, and still no-op when the
day is already ledgered. This command does not delete a ledger row and does
not call Discord or X on its own.

Do not run --apply from a migration or from a worker pass. The owner runs it.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

import config


def _date_is_over(game_date: str, today: str | None = None) -> bool:
    """True when game_date is a real YYYY-MM-DD strictly before today ET."""
    if len(game_date) != 10 or game_date.count("-") != 2:
        return False
    try:
        datetime.strptime(game_date, "%Y-%m-%d")
    except ValueError:
        return False
    today = today if today is not None else config.today_et()
    return game_date < today


def post_backfill(game_date: str, apply: bool = False) -> dict:
    """Dry-run unless apply is true. Returns what each surface reported.

    apply false does not import the notifiers, so a dry run cannot post.
    """
    if not _date_is_over(game_date):
        raise SystemExit(
            f"refusing {game_date}: the day is not over "
            f"(today ET is {config.today_et()})")
    if not apply:
        return {"game_date": game_date, "apply": False,
                "discord": None, "x": None}
    from tracking.discord_notifier import notify_discord_results
    from tracking.x_publisher import notify_x_results
    return {
        "game_date": game_date,
        "apply": True,
        "discord": notify_discord_results(game_date=game_date, dry_run=False),
        "x": notify_x_results(game_date=game_date, dry_run=False),
    }


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", required=True, help="game_date YYYY-MM-DD")
    ap.add_argument("--apply", action="store_true",
                    help="post the recap. Without it this is a dry run.")
    return ap


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    result = post_backfill(a.date, apply=a.apply)
    if not a.apply:
        print(f"DRY RUN: would post the {a.date} results recap on Discord and X.")
        print("Re-run with --apply to post. Nothing was sent.")
        return 0
    print(f"posted {a.date}: discord={result['discord']} x={result['x']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
