"""The missed-day recap posts only when the owner passes --apply.

2026-10-05 has no discord_results row and no x_results row (measured
2026-10-14). This command is the way to post it. A dry run does not import
the notifiers.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import config
from scripts.backfill_results_recap import (
    build_parser, main, post_backfill,
)

SRC = (Path(__file__).parent.parent / "scripts/backfill_results_recap.py"
       ).read_text(encoding="utf-8")


def test_dry_run_is_the_default_and_posts_nothing(monkeypatch):
    calls = []
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-14")

    def boom(*_a, **_k):
        calls.append("called")
        raise AssertionError("a dry run posted")

    # Importing the notifiers here would be the bug. Patching the names the
    # apply branch imports is enough if apply is false: those imports must
    # not run.
    monkeypatch.setattr(
        "tracking.discord_notifier.notify_discord_results", boom, raising=False)
    monkeypatch.setattr(
        "tracking.x_publisher.notify_x_results", boom, raising=False)

    out = post_backfill("2026-10-05", apply=False)
    assert out == {"game_date": "2026-10-05", "apply": False,
                   "discord": None, "x": None}
    assert calls == []
    assert build_parser().parse_args(["--date", "2026-10-05"]).apply is False


def test_apply_calls_both_notifiers_for_that_date(monkeypatch):
    seen = []
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-14")
    monkeypatch.setattr(
        "tracking.discord_notifier.notify_discord_results",
        lambda **kw: seen.append(("discord", kw)) or 1)
    monkeypatch.setattr(
        "tracking.x_publisher.notify_x_results",
        lambda **kw: seen.append(("x", kw)) or 1)

    out = post_backfill("2026-10-05", apply=True)
    assert out["discord"] == 1 and out["x"] == 1
    assert seen == [
        ("discord", {"game_date": "2026-10-05", "dry_run": False}),
        ("x", {"game_date": "2026-10-05", "dry_run": False}),
    ]


def test_a_day_that_is_not_over_is_refused(monkeypatch):
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-14")
    with pytest.raises(SystemExit, match="not over"):
        post_backfill("2026-10-14", apply=True)
    with pytest.raises(SystemExit, match="not over"):
        post_backfill("2026-10-14", apply=False)
    with pytest.raises(SystemExit):
        post_backfill("10/05/2026", apply=False)


def test_the_command_does_not_delete_a_ledger_row_or_post_by_itself():
    body = SRC.split('if __name__', 1)[0]
    assert "DELETE FROM" not in body
    assert "INSERT INTO" not in body
    assert "_post(" not in body
    assert "requests." not in body
    assert "if __name__" in SRC


def test_main_dry_run_prints_and_returns(capsys, monkeypatch):
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-14")
    assert main(["--date", "2026-10-05"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out and "2026-10-05" in out and "Nothing was sent" in out
