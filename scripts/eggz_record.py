#!/usr/bin/env python3
"""Grade, manually settle, or restate one capper's day. Dry-run unless --apply.

Does not read Discord. Does not post unless `restate --apply`. Does not
delete a push_sent row. A dry run writes nothing. `--capper` defaults to
eggz, so the commands below are unchanged. It may sit before or after the
command.

    python -m scripts.eggz_record grade
    python -m scripts.eggz_record grade --apply
    python -m scripts.eggz_record settle --id 12 --result LOSS --note "log: 11 points"
    python -m scripts.eggz_record settle --id 12 --result LOSS --note "log: 11 points" --apply
    python -m scripts.eggz_record restate 2026-10-22
    python -m scripts.eggz_record restate 2026-10-22 --apply
    python -m scripts.eggz_record --capper parlaymatt grade --apply
    python -m scripts.eggz_record --capper parlaymatt restate 2026-10-22 --apply

`grade` re-reads stored messages and grades finals. Run it before settle,
then list the rows still open and settle those. Do not reuse an id from
before that grade: a needs_review row is deleted and inserted again, so
its id changes.

`restate` needs mike's approval (config.RECORD_RESTATEMENT_APPROVALS) and then
posts one Corrected recap for a day that already has a sent
recap, then stops. It returns 0 when a leg is still unresolved, a game of
that sport is in progress, or that correction was already sent.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking.eggz_picks import (  # noqa: E402
    CAPPERS,
    EGGZ,
    EggzSettleError,
    grade_pending,
    open_legs,
    restate_eggz_day,
    settle_manual,
)


def _capper(name: str):
    key = (name or "eggz").strip().lower()
    if key not in CAPPERS:
        raise SystemExit(f"unknown capper {name!r}; use eggz or parlaymatt")
    return CAPPERS[key]


def _print_open(rows) -> None:
    if not rows:
        print("no pending or needs_review legs")
        return
    print(f"{len(rows)} open leg(s):")
    for row in rows:
        (pid, status, reason, game_date, sport, market, player, side,
         price, stake, posted) = row
        who = player or ""
        print(
            f"  id={pid} {status} {game_date or '-'} {sport or '-'} "
            f"{market or '-'} {who} {side or ''} price={price} "
            f"stake={stake} reason={reason} posted={posted}"
        )


def cmd_grade(apply: bool, capper=EGGZ) -> int:
    from data.db import get_connection
    conn = get_connection()
    try:
        if not apply:
            rows = open_legs(conn) if capper is EGGZ else open_legs(conn, capper)
            _print_open(rows)
            print("dry-run: nothing graded. Pass --apply to grade.")
            return 0
        n = grade_pending(conn) if capper is EGGZ else grade_pending(conn, capper)
        print(f"graded {n}")
        rows = open_legs(conn) if capper is EGGZ else open_legs(conn, capper)
        _print_open(rows)
        return 0
    finally:
        conn.close()


def cmd_settle(pick_id: int, result: str, note: str, apply: bool, capper=EGGZ) -> int:
    from data.db import get_connection
    conn = get_connection()
    try:
        if capper is EGGZ:
            out = settle_manual(conn, pick_id, result, note, apply=apply)
        else:
            out = settle_manual(conn, pick_id, result, note, apply=apply, capper=capper)
    except EggzSettleError as exc:
        print(f"refused: {exc}")
        return 1
    finally:
        conn.close()
    verb = "settled" if out["applied"] else "would settle"
    print(
        f"{verb} id={out['id']} {out['result']} "
        f"units={out['units']:.4f} risked={out['risked']:.4f}"
    )
    if not out["applied"]:
        print("dry-run: nothing written. Pass --apply to grade this leg.")
    return 0


def cmd_restate(game_date: str, apply: bool, capper=EGGZ) -> int:
    if capper is EGGZ:
        n = restate_eggz_day(game_date, dry_run=not apply)
    else:
        n = restate_eggz_day(game_date, dry_run=not apply, capper=capper)
    if apply:
        print(f"restate {game_date}: posted {n}")
    elif n:
        print(f"dry-run restate {game_date}: would post a Corrected recap")
    else:
        print(
            f"dry-run restate {game_date}: held, already corrected, "
            "or that day was never sent"
        )
    return 0


def _take_capper(argv: list[str]) -> tuple[str, list[str]]:
    """Pull `--capper name` from anywhere. The rest of the CLI is unchanged."""
    name = "eggz"
    out: list[str] = []
    i = 0
    while i < len(argv):
        if argv[i] == "--capper":
            if i + 1 >= len(argv):
                raise SystemExit("--capper needs a name: eggz or parlaymatt")
            name = argv[i + 1]
            i += 2
            continue
        out.append(argv[i])
        i += 1
    return name, out


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    capper_name, raw = _take_capper(raw)
    capper = _capper(capper_name)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--apply", action="store_true",
        help="write grades or post the correction; omit for a dry run")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("grade", parents=[common], help="reparse stored messages and grade finals")

    settle = sub.add_parser("settle", parents=[common], help="grade one set-aside leg")
    settle.add_argument("--id", type=int, required=True)
    settle.add_argument("--result", required=True)
    settle.add_argument("--note", required=True)

    restate = sub.add_parser("restate", parents=[common], help="post a Corrected day recap")
    restate.add_argument("game_date")

    args = parser.parse_args(raw)
    if args.command == "grade":
        return cmd_grade(args.apply, capper)
    if args.command == "settle":
        return cmd_settle(args.id, args.result, args.note, args.apply, capper)
    if args.command == "restate":
        return cmd_restate(args.game_date, args.apply, capper)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
