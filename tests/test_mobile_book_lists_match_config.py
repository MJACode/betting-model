"""The app's sportsbook lists ARE config.py's lists.

The app carries its own copy of which books the server fetches
(`LINE_SHOP_BOOKS`) and which a pick can be decided at (`BETTABLE_BOOKS`), in
mobile/src/lib/markets.ts, because a phone cannot import config.py. On
2026-09-20 the server cut fourteen fetched books to ten (mike: "yes drop the 4
books") and the app kept all fourteen for seven weeks. The member's book picker
offered Bally Bet, ReBet and Fliff, none priced since 2026-09-20, and ESPN BET,
none since 2026-10-01 (v_latest_odds_all_books, measured 2026-11-06). Those
were checkboxes that could never show a price.

Nothing caught it because the two mobile checks that pinned the list pinned its
LENGTH (`=== 13`), a second copy of the app's own number. This compares the
app's literals with config's evaluated lists, so a cut on either side fails
here. It reads the .ts as text and needs no node, so it runs on every machine
that runs the suite. mobile/scripts/verify_book_lines.ts makes the same
comparison through the app's real exports.

Config is evaluated in a child process with the four env overrides removed:
production runs config's defaults (neither Railway service sets any of them,
2026-11-06), so a local override must not decide this test.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKETS = ROOT / "mobile" / "src" / "lib" / "markets.ts"
OVERRIDES = (
    "LINE_SHOP_BOOKMAKERS",
    "BEST_LINE_BOOKMAKERS",
    "BEST_LINE_EXCLUDE_BOOKMAKERS",
    "BETTABLE_BOOKS",
)
# Cut from the fetch list on 2026-09-20 (espnbet earlier). Old picks and NFL
# card labels still name them, so the app must keep their display names.
DROPPED = {"espnbet": ("ESPN BET", "ESPN"), "ballybet": ("Bally Bet", "BALLY"),
           "rebet": ("ReBet", "REBET"), "fliff": ("Fliff", "FLIFF")}


@pytest.fixture(scope="module")
def cfg() -> dict:
    env = {k: v for k, v in os.environ.items() if k not in OVERRIDES}
    env["PYTHONIOENCODING"] = "utf-8"
    code = (
        "import json, os, config\n"
        "print(json.dumps({'fetched': config.LINE_SHOP_BOOKMAKERS,"
        " 'decided': config.BEST_LINE_BOOKMAKERS,"
        " 'excluded': config.BEST_LINE_EXCLUDE_BOOKMAKERS,"
        f" 'overridden': [k for k in {list(OVERRIDES)!r} if k in os.environ]}}))\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["overridden"] == [], (
        f"{out['overridden']} set in .env: this compares against config's own "
        "defaults, which are what production runs")
    return out


@pytest.fixture(scope="module")
def src() -> str:
    return MARKETS.read_text(encoding="utf-8")


def _array(src: str, name: str) -> list[str]:
    m = re.search(rf"export const {name}\b[^=]*=\s*\[(.*?)\];", src, re.S)
    assert m, f"{name} literal not found in markets.ts"
    return re.findall(r"'([a-z0-9_]+)'", m.group(1))


def _record_keys(src: str, name: str) -> set[str]:
    m = re.search(rf"const {name}: Record<string, string> = \{{(.*?)\n\}};", src, re.S)
    assert m, f"{name} not found in markets.ts"
    return set(re.findall(r"^\s*([a-z0-9_]+):", m.group(1), re.M))


def test_the_app_lists_every_book_the_server_fetches_in_its_order(src, cfg):
    assert _array(src, "LINE_SHOP_BOOKS") == cfg["fetched"]


def test_the_reference_only_books_are_configs(src, cfg):
    assert set(_array(src, "REFERENCE_ONLY_BOOKS")) == set(cfg["excluded"])


def test_the_picker_offers_exactly_the_books_a_pick_can_be_decided_at(src, cfg):
    # BETTABLE_BOOKS is DERIVED in the app; pin the derivation, then apply it.
    assert re.search(
        r"export const BETTABLE_BOOKS: BookKey\[\] = LINE_SHOP_BOOKS\.filter\(\s*"
        r"\(b\) => !REFERENCE_ONLY_BOOKS\.includes\(b\),\s*\);",
        src,
    ), "BETTABLE_BOOKS is no longer LINE_SHOP_BOOKS minus REFERENCE_ONLY_BOOKS"
    fetched = _array(src, "LINE_SHOP_BOOKS")
    reference = set(_array(src, "REFERENCE_ONLY_BOOKS"))
    assert [b for b in fetched if b not in reference] == cfg["decided"]


def test_the_book_key_type_is_the_fetched_list(src, cfg):
    m = re.search(r"export type BookKey =(.*?);", src, re.S)
    assert m
    assert set(re.findall(r"'([a-z0-9_]+)'", m.group(1))) == set(cfg["fetched"])


def test_every_fetched_and_every_dropped_book_keeps_its_name_and_label(src, cfg):
    assert set(cfg["fetched"]) <= _record_keys(src, "BOOK_NAMES")
    assert set(cfg["fetched"]) <= _record_keys(src, "BOOK_LABELS")
    for key, (name, label) in DROPPED.items():
        assert key not in cfg["fetched"], f"{key} is fetched again; update DROPPED"
        assert re.search(rf"^\s*{key}: '{re.escape(name)}',", src, re.M), key
        assert re.search(rf"^\s*{key}: '{label}',", src, re.M), key
