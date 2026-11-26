"""Pure parsers for the This PC window.

No file, process or clock access here: every function takes its input, and the
time it should judge against, as arguments. tests/test_pc_monitor.py feeds them
real lines copied from the PC's logs on 2026-11-21.

Times leave this module as epoch seconds (UTC), so the page formats every one of
them the same way, in the PC's own time zone.
"""

from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from typing import Any, Iterable

# The in-play models use a dk_live_feed row only while it is at most this many
# seconds old (models/ncaab_live_dk.py, FEED_MAX_AGE_SEC). A test keeps them equal.
FEED_MAX_AGE_SEC = 8.0
# A league with no live game is read this often (dk_live_board.IDLE_POLL_SEC).
IDLE_POLL_SEC = 30.0
# How far past its next read an idle league may run before it is flagged.
IDLE_SLACK_SEC = 30.0
# The feed exits after 45 minutes with no live game and the once-a-minute task
# starts it again, so a gap shorter than this between runs is normal.
FEED_RESTART_GRACE_SEC = 180.0
# The backup rewrites progress.json every few seconds while it copies tables.
PROGRESS_FRESH_SEC = 120.0
# The phone page: the PC rewrites its row this often while a phone has asked
# within PHONE_WATCHING_SEC, and once a minute otherwise (a 13 KB row rewritten
# every 2 s all day would be hundreds of MB of dead rows for nobody).
PUBLISH_FAST_SEC = 2.0
PUBLISH_SLOW_SEC = 60.0
PHONE_WATCHING_SEC = 60.0


# Every league DraftKings' board reads (dk_live_board.LEAGUES), so a league
# with no dk_live_feed row is still listed; and the detail the board writes for
# a league DraftKings is not listing (dk_live_board.NOT_LISTED). A test keeps
# both equal to the board's.
FEED_LEAGUES = ("EUROLEAGUE", "NBA", "NCAAB", "NCAABW", "NCAAF", "NFL", "NHL")
NOT_LISTED = "not listed by DraftKings"

# The other books (data/ingestors/book_live_boards.py, BOOKS): what the feed
# does with each one's answer, in the order the page lists them. "parsed": its
# live lines go to `odds`; "captured": its answer is stored until a parser is
# written from it; "home page": its home page is stored for the hosts it calls.
# A test keeps this equal to BOOKS.
BOOK_KINDS = {"fanduel": "parsed", "betrivers": "parsed", "betmgm": "captured",
              "williamhill_us": "captured", "fanatics": "home page", "hardrockbet": "home page"}
BOOK_NAMES = {"draftkings": "DraftKings", "fanduel": "FanDuel", "betrivers": "BetRivers",
              "betmgm": "BetMGM", "williamhill_us": "Caesars", "fanatics": "Fanatics",
              "hardrockbet": "Hard Rock"}
# A book is read every BOOK_POLL_SEC while its league has a game live
# (book_live_boards.POLL_SEC), and not at all otherwise; its home page every
# BOOK_HOME_PAGE_SEC (DISCOVER_SEC) while anything is live.
BOOK_POLL_SEC = 30.0
BOOK_HOME_PAGE_SEC = 6 * 3600.0


def book_status(row: dict[str, Any], kind: str | None) -> dict[str, str]:
    """One book and league's last read in book_live_feed, in words."""
    age, live = row.get("age_s"), row.get("live_events") or 0
    detail = str(row.get("detail") or "")
    if age is None:
        return {"tone": "idle", "text": "never read"}
    if detail == "refused":
        return {"tone": "bad", "text": "refused (403 / bot wall)"}
    if row.get("ok") is False:
        status = row.get("status")
        return {"tone": "bad", "text": f"HTTP {status}" if status else (detail or "last read failed")}
    if kind == "home page":
        return {"tone": "idle", "text": "home page stored"}
    if kind == "captured":
        return {"tone": "idle", "text": "answer stored, no parser yet"}
    if age > BOOK_POLL_SEC * 3:
        return {"tone": "idle", "text": "not read lately"}
    if live == 0:
        return {"tone": "idle", "text": "no live game"}
    matched = row.get("matched") or 0
    if matched < live:
        return {"tone": "warn", "text": f"{live - matched} of {live} not matched"}
    return {"tone": "ok", "text": "fresh"}


def publish_interval(demand_age_s: float | None) -> float:
    """How often the PC writes its view for the phone, given how long ago a
    phone last asked (None: never)."""
    if demand_age_s is not None and demand_age_s < PHONE_WATCHING_SEC:
        return PUBLISH_FAST_SEC
    return PUBLISH_SLOW_SEC


# ── time ────────────────────────────────────────────────────────────────────

_FRACTION = re.compile(r"(\.\d{6})\d+")


def parse_iso(value: Any) -> float | None:
    """An ISO 8601 time as epoch seconds. Accepts 'Z', '+00:00' and the seven
    fractional digits PowerShell writes. A time with no zone is read as UTC.
    None for anything that does not parse."""
    if not isinstance(value, str) or not value.strip():
        return None
    s = _FRACTION.sub(r"\1", value.strip())
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


_DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def parse_duration(value: Any) -> int | None:
    """An ISO 8601 duration such as 'PT18H' or 'PT1M' as seconds."""
    if not isinstance(value, str):
        return None
    m = _DURATION.match(value.strip())
    if not m or not any(m.groups()):
        return None
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def in_daily_window(now_minute_of_day: int, start_minute: int, duration_s: int) -> bool:
    """Whether a clock time falls inside a daily window that may run past
    midnight (09:00 for 18 hours ends at 03:00 the next day)."""
    if duration_s >= 86400:
        return True
    return (now_minute_of_day - start_minute) % 1440 < duration_s / 60


# ── Task Scheduler ──────────────────────────────────────────────────────────

# LastTaskResult codes seen on this PC, in plain words. Anything else is shown
# as its code. The tone drives the colour: ok, idle, warn, bad.
_RESULTS: dict[int, tuple[str, str]] = {
    0x0: ("ok", "last run finished without an error"),
    0x41301: ("ok", "running now"),
    0x41303: ("idle", "has not run yet"),
    0x41302: ("warn", "the task is disabled"),
    0x41306: ("bad", "the last run was stopped by hand"),
    0x41325: ("idle", "queued to start"),
    # IgnoreNew: a once-a-minute start turned away because the job is still
    # running. Normal for the in-play feed, which runs for hours.
    0x800710E0: ("ok", "already running (a repeat start was skipped)"),
    0x8004131F: ("ok", "already running (a repeat start was skipped)"),
    0x8007042B: ("bad", "the process ended unexpectedly"),
    0xC000013A: ("bad", "the process was closed (Ctrl+C or its window was shut)"),
}


def describe_task_result(code: Any) -> dict[str, Any]:
    if code is None:
        return {"tone": "idle", "text": "no result recorded", "code": None}
    try:
        c = int(code) & 0xFFFFFFFF
    except (TypeError, ValueError):
        return {"tone": "warn", "text": f"result {code!r}", "code": None}
    hexcode = f"0x{c:X}"
    if c in _RESULTS:
        tone, text = _RESULTS[c]
    elif c < 0x100:
        tone, text = "bad", f"last run ended with exit code {c}"
    else:
        tone, text = "warn", f"last result {hexcode}"
    return {"tone": tone, "text": text, "code": hexcode}


_FILE_ARG = re.compile(r"-File\s+\"?([^\"]+?\.ps1)\"?(?:\s|$)", re.IGNORECASE)
_HHMM = re.compile(r"T(\d{2}):(\d{2})")
_TRIGGER_NAMES = {"MSFT_TaskDailyTrigger": "daily", "MSFT_TaskLogonTrigger": "at sign-in",
                  "MSFT_TaskTimeTrigger": "once", "MSFT_TaskWeeklyTrigger": "weekly",
                  "MSFT_TaskBootTrigger": "at start-up"}


def _as_list(v: Any) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _schedule(triggers: list) -> tuple[str, dict | None]:
    """A one-line schedule, and the daily repeating window if there is one."""
    parts, window = [], None
    for t in triggers:
        if not isinstance(t, dict) or t.get("enabled") is False:
            continue
        kind = _TRIGGER_NAMES.get(t.get("type"), t.get("type") or "trigger")
        every = parse_duration(t.get("interval"))
        lasting = parse_duration(t.get("duration"))
        m = _HHMM.search(t.get("start") or "")
        text = kind
        if kind in ("daily", "once") and m:
            text = f"{kind} at {m.group(1)}:{m.group(2)}"
            if every:
                text = (f"every {every // 60} min" if every < 3600 else f"every {every // 3600} h")
                if kind == "daily":  # a one-off start time that repeats has no daily start
                    text += f" from {m.group(1)}:{m.group(2)}"
                # A repetition with no end (or one past a day) runs all day.
                if lasting and lasting < 86400:
                    text += f" for {lasting // 3600} h" if lasting % 3600 == 0 else f" for {lasting // 60} min"
                    if kind == "daily":
                        window = {"start_minute": int(m.group(1)) * 60 + int(m.group(2)),
                                  "duration_s": lasting}
        delay = parse_duration(t.get("delay"))
        if kind == "at sign-in" and delay:
            text += f" (+{delay // 60} min)"
        parts.append(text)
    return ", ".join(parts) or "no schedule", window


def parse_tasks(raw: Any) -> list[dict[str, Any]]:
    """The tasks in one Task Scheduler folder, from the JSON the PowerShell read
    prints (one object, or a list of them)."""
    if isinstance(raw, str):
        raw = json.loads(raw) if raw.strip() else []
    out = []
    for t in _as_list(raw):
        if not isinstance(t, dict):
            continue
        schedule, window = _schedule(_as_list(t.get("triggers")))
        m = _FILE_ARG.search(t.get("action") or "")
        out.append({
            "name": t.get("name"),
            "state": t.get("state"),
            "last_run_at": parse_iso(t.get("last_run_at")),
            "next_run_at": parse_iso(t.get("next_run_at")),
            "result": describe_task_result(t.get("last_result")),
            "schedule": schedule,
            "window": window,
            "script": m.group(1).replace("\\", "/").rsplit("/", 1)[-1].lower() if m else None,
        })
    return sorted(out, key=lambda x: str(x["name"]))


# ── processes ───────────────────────────────────────────────────────────────

def _cmd(cmdline: Iterable[str] | None) -> str:
    return " ".join(cmdline or []).replace("\\", "/").lower()


def runs_script(cmdline: Iterable[str] | None, script: str) -> bool:
    """A PowerShell process started with -File <...>/<script>."""
    c = _cmd(cmdline)
    return bool(script) and re.search(r"-file\s+\"?[^\"]*/" + re.escape(script.lower()), c) is not None


def is_dk_feed(name: str | None, cmdline: Iterable[str] | None) -> bool:
    """The in-play feed itself: python -m data.ingestors.dk_live_board."""
    return (name or "").lower().startswith("python") and \
        re.search(r"-m\s+data\.ingestors\.dk_live_board(\s|$)", _cmd(cmdline)) is not None


def arg_value(cmdline: Iterable[str] | None, flag: str) -> str | None:
    """The value after `flag` in an argv list ('--log' -> the log path)."""
    args = list(cmdline or [])
    for i, a in enumerate(args):
        if a == flag and i + 1 < len(args):
            return args[i + 1]
        if a.startswith(flag + "="):
            return a.split("=", 1)[1]
    return None


# ── log lines ───────────────────────────────────────────────────────────────

_LOG_LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),(\d{3}) ([A-Z]+) (.*)$")


def parse_log_lines(lines: Iterable[str]) -> list[dict[str, Any]]:
    """Python logging lines ('2026-11-21 12:08:41,895 INFO read 1301 ...').

    The time is the PC's local clock, which is how the feed writes it. A line
    that does not start with a time (a traceback) is joined to the one above."""
    out: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.rstrip("\r\n")
        m = _LOG_LINE.match(line)
        if m:
            at = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S").timestamp() + int(m.group(2)) / 1000
            out.append({"at": at, "level": m.group(3), "msg": m.group(4)})
        elif out and line.strip():
            out[-1]["msg"] += "\n" + line
    return out


def collapse_problems(entries: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    """Warnings and errors, one row per distinct message with how many times
    and when first and last. Newest first."""
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for e in entries:
        if e["level"] not in ("WARNING", "ERROR", "CRITICAL"):
            continue
        first_line = e["msg"].split("\n", 1)[0]
        g = groups.setdefault((e["level"], first_line), {
            "level": e["level"], "message": first_line, "count": 0,
            "first_at": e["at"], "last_at": e["at"]})
        g["count"] += 1
        g["last_at"] = e["at"]
    return sorted(groups.values(), key=lambda g: g["last_at"], reverse=True)[:limit]


_READ = re.compile(r"^read (\d+) \(([^)]+)\): (\{.*\})\s*$")


def _literal(text: str) -> dict:
    try:
        v = ast.literal_eval(text)
    except (ValueError, SyntaxError):
        return {}
    return v if isinstance(v, dict) else {}


def read_rate(reads: list[dict[str, Any]], max_points: int = 10) -> dict[str, Any] | None:
    """Reads per second from the feed's 'read N' lines.

    The feed writes one such line every 100 reads, counting all sports together,
    so this is a rate over the last few hundred reads, not a per-second count.
    A restart sets the counter back to 1; only the run since then is used."""
    run: list[dict[str, Any]] = []
    for r in reversed(reads):
        if run and r["n"] >= run[-1]["n"]:
            break
        run.append(r)
        if len(run) >= max_points:
            break
    if len(run) < 2:
        return None
    newest, oldest = run[0], run[-1]
    span = newest["at"] - oldest["at"]
    if span <= 0:
        return None
    count = newest["n"] - oldest["n"]
    return {"per_s": count / span, "reads": count, "from_at": oldest["at"], "to_at": newest["at"]}


def feed_log_summary(entries: list[dict[str, Any]]) -> dict[str, Any]:
    reads = []
    started_at = None
    stop = None
    for e in entries:
        m = _READ.match(e["msg"])
        if m:
            reads.append({"at": e["at"], "n": int(m.group(1)), "sport": m.group(2),
                          "detail": _literal(m.group(3))})
        elif e["msg"].startswith("reading "):
            started_at, stop = e["at"], None
        elif "exiting" in e["msg"]:
            stop = {"at": e["at"], "message": e["msg"].split("\n", 1)[0]}
    return {
        "last_line_at": entries[-1]["at"] if entries else None,
        "started_at": started_at,
        "last_read": reads[-1] if reads else None,
        "rate": read_rate(reads),
        "stopped": stop,
        "problems": collapse_problems(entries),
    }


_START = re.compile(r"^--- start (\S+)\s*$")
_EXIT = re.compile(r"^--- exit (-?\d+) (\S+)\s*$")


def parse_launcher_log(lines: Iterable[str]) -> list[dict[str, Any]]:
    """The in-play feed launcher's runs: '--- start <UTC>' and
    '--- exit <code> <UTC>'. A start with no exit is still running, or was
    killed with the launcher."""
    runs: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        m = _START.match(line)
        if m:
            runs.append({"start_at": parse_iso(m.group(1)), "exit_code": None, "exit_at": None})
            continue
        m = _EXIT.match(line)
        if m and runs and runs[-1]["exit_at"] is None:
            runs[-1]["exit_code"] = int(m.group(1))
            runs[-1]["exit_at"] = parse_iso(m.group(2))
    return runs


# The code, when present, is its own word: 'dk exit  2026-11-21T18:26:22Z' has
# none, and its time must not be read as code 2026.
_PASS_EXIT = re.compile(r"^(\w+) exit\s+(?:(-?\d+)\s+)?(\S+)\s*$")


def parse_tennis_passes(lines: Iterable[str]) -> list[dict[str, Any]]:
    """The tennis task's passes: '--- start <UTC>', then '<collector> exit
    <code> <UTC>' per collector. The launcher leaves the code blank today, which
    is kept as None (not recorded), never as 0."""
    passes: list[dict[str, Any]] = []
    for raw in lines:
        line = raw.strip()
        m = _START.match(line)
        if m:
            passes.append({"start_at": parse_iso(m.group(1)), "collectors": {}})
            continue
        m = _PASS_EXIT.match(line)
        if m and passes:
            passes[-1]["collectors"][m.group(1)] = {
                "exit_code": int(m.group(2)) if m.group(2) is not None else None,
                "at": parse_iso(m.group(3))}
    return passes


def last_json_line(text: str | None) -> dict[str, Any] | None:
    """The last line of a collector's summary file, as JSON."""
    for line in reversed((text or "").splitlines()):
        if line.strip():
            try:
                v = json.loads(line)
            except ValueError:
                return None
            return v if isinstance(v, dict) else None
    return None


# ── API calls and data movement ─────────────────────────────────────────────

# Every outgoing call the system makes is a row in api_call_log, from the worker
# and from this PC alike (monitoring/probe.py writes it). Which machine made a
# call is worked out from the program that made it: a module this PC is
# running (or has run this session) is this PC; everything else is the worker.
PC_CALL_SOURCES = frozenset({"data.ingestors.dk_live_board"})

# Fixed colour slots, by provider, so a provider keeps its colour whatever its
# volume. Everything else is "Other" (grey on the page).
PROVIDER_SLOTS = ("DraftKings", "The Odds API", "ESPN (site)", "ESPN (core)", "CFBD", "www.bovada.lv")


def module_of(cmdline: Iterable[str] | None) -> str | None:
    """'python -m data.ingestors.dk_live_board ...' -> 'data.ingestors.dk_live_board'."""
    args = list(cmdline or [])
    for i, a in enumerate(args):
        if a == "-m" and i + 1 < len(args):
            return args[i + 1]
    return None


def _short_path(path: Any) -> str:
    """The call's path without its query string (which can carry parameters
    nobody needs on a phone)."""
    p = str(path or "").split("?", 1)[0]
    return p if len(p) <= 70 else p[:67] + "..."


def call_event(row: tuple, pc_sources: Iterable[str]) -> dict[str, Any]:
    """One api_call_log row (call_id, epoch, api, category, method, path, sport,
    status, ok, duration_ms, resp_bytes, credits, quota_remaining, error,
    source) as a stream event."""
    (cid, at, api, category, method, path, sport, status, ok, ms, size, credits,
     remaining, error, source) = row
    return {
        "id": f"c{cid}", "at": at, "kind": "call",
        "where": "pc" if source in set(pc_sources) else "worker",
        "provider": api, "category": category, "what": f"{method} {_short_path(path)}",
        "by": source, "sport": sport, "status": status, "ok": bool(ok), "ms": ms,
        "bytes": size, "credits": float(credits) if credits else None,
        "credits_left": float(remaining) if remaining is not None else None,
        "error": (str(error)[:120] if error else None),
    }


def save_event(row: tuple) -> dict[str, Any]:
    """One new dk_live_reads row (id, sport, game_id, epoch, period_label,
    home_score, away_score, spread_home, total_line): a line or score change
    this PC saved to the database."""
    rid, sport, game, at, period, hs, as_, spread, total = row
    bits = [f"{sport} game {game}"]
    if hs is not None and as_ is not None:
        bits.append(f"home {hs}, away {as_}" + (f" ({period})" if period else ""))
    if spread is not None:
        bits.append(f"home spread {spread:+g}")
    if total is not None:
        bits.append(f"total {total:g}")
    return {"id": f"s{rid}", "at": at, "kind": "saved", "where": "pc", "provider": "Supabase",
            "what": "saved to dk_live_reads: " + ", ".join(bits), "ok": True}


def call_timeline(rows: list[tuple], now: float, pc_sources: Iterable[str],
                  bucket_s: int = 10, window_s: int = 600) -> dict[str, Any]:
    """Calls per bucket over the window, by provider slot, from rows of
    (bucket epoch, api, source, calls, failed, credits); plus a per-provider
    table and the calls a minute each machine made over the last minute."""
    pcs = set(pc_sources)
    n = window_s // bucket_s
    start = (now // bucket_s) * bucket_s - (n - 1) * bucket_s
    series = {name: [0] * n for name in (*PROVIDER_SLOTS, "Other")}
    failed = [0] * n
    providers: dict[tuple[str, str], dict[str, Any]] = {}
    last_min = {"pc": 0, "worker": 0}
    for b, api, source, calls, bad, credits in rows:
        i = int((b - start) // bucket_s)
        if not 0 <= i < n:
            continue
        slot = api if api in series and api != "Other" else "Other"
        series[slot][i] += int(calls)
        failed[i] += int(bad or 0)
        where = "pc" if source in pcs else "worker"
        p = providers.setdefault((api, where), {"name": api, "where": where, "slot": slot,
                                                "calls": 0, "failed": 0, "credits": 0.0})
        p["calls"] += int(calls)
        p["failed"] += int(bad or 0)
        p["credits"] += float(credits or 0)
        if b >= now - 60:
            last_min[where] += int(calls)
    return {"start": start, "bucket_s": bucket_s, "n": n,
            "series": [{"name": k, "counts": v} for k, v in series.items()],
            "failed": failed,
            "providers": sorted(providers.values(), key=lambda p: -p["calls"]),
            "calls_last_min": last_min}


# ── judgements ──────────────────────────────────────────────────────────────

def feed_presence(running: bool, now: float, in_window: bool | None,
                  runs: list[dict[str, Any]], window_text: str | None = None) -> dict[str, str]:
    """Whether the in-play feed being up or down is a problem.

    It is meant to be down outside the task's daily window, and for under a
    minute after it exits on 45 idle minutes (exit 0). Anything else is not."""
    if running:
        return {"tone": "ok", "text": "running"}
    if in_window is False:
        return {"tone": "idle", "text": "off by schedule" + (f" (the task runs {window_text})" if window_text else "")}
    last = runs[-1] if runs else None
    if last and last.get("exit_at") is None and last.get("start_at") is not None \
            and now - last["start_at"] < FEED_RESTART_GRACE_SEC:
        return {"tone": "idle", "text": "starting: the launcher is updating its copy of the code"}
    if last and last.get("exit_at") is not None:
        code, ago = last.get("exit_code"), now - last["exit_at"]
        when = "under a minute" if ago < 60 else f"{int(ago // 60)} min"
        if code == 0 and ago < FEED_RESTART_GRACE_SEC:
            return {"tone": "idle", "text": "between runs: it stops after 45 minutes with no live "
                                            "game, and the task starts it again within a minute"}
        if code not in (0, None):
            return {"tone": "bad", "text": f"stopped with exit code {code}, {when} ago"}
        return {"tone": "bad", "text": f"not running for {when}, inside the hours the task should keep it up"}
    return {"tone": "bad", "text": "not running"}


def sport_status(row: dict[str, Any], feed_running: bool) -> dict[str, str]:
    """One league's freshness in dk_live_feed, judged the way its readers judge it."""
    age, live = row.get("age_s"), row.get("live_events") or 0
    if age is None:
        return {"tone": "idle", "text": "never read"}
    if not feed_running:
        return {"tone": "idle", "text": "feed not running"}
    if str(row.get("detail") or "").startswith(NOT_LISTED):
        return {"tone": "idle", "text": "DraftKings is not listing this league right now (it lists a league "
                                        "only while it has offers); asked again every 10 min"}
    if row.get("ok") is False:
        return {"tone": "bad", "text": "the last read failed"}
    if live > 0:
        if age <= FEED_MAX_AGE_SEC:
            return {"tone": "ok", "text": "fresh"}
        return {"tone": "bad", "text": f"older than the {FEED_MAX_AGE_SEC:.0f} s the in-play models accept"}
    if age <= IDLE_POLL_SEC + IDLE_SLACK_SEC:
        return {"tone": "idle", "text": f"no live game; read every {IDLE_POLL_SEC:.0f} s"}
    return {"tone": "warn", "text": f"no live game, and the read every {IDLE_POLL_SEC:.0f} s is late"}


_PASS_FILE = re.compile(r"^(fetch|bin_refresh|catchup|github|supabase|duckdb|report)_(\d{8}T\d{6}Z)\.(log|err)$")


def newest_pass(names: Iterable[str]) -> str | None:
    """The newest backup pass id (e.g. '20261121T162749Z') among the log names."""
    ids = {m.group(2) for n in names if (m := _PASS_FILE.match(n))}
    return max(ids) if ids else None


def pass_started_at(pass_id: str) -> float | None:
    try:
        return datetime.strptime(pass_id, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


_REPORT = re.compile(
    r"(?P<tables>[\d,]+) tables / (?P<rows>[\d,]+) rows on disk, (?P<differing>\d+) differing, "
    r"(?P<failed>\d+) failed;.*?disk free (?P<free>[\d.]+) of (?P<total>[\d.]+) GB")
_SNAPSHOT_ROW = re.compile(r"wrote pc_copy_snapshots row (\d+)")


def parse_report(text: str | None) -> dict[str, Any] | None:
    """The backup's report line: tables and rows on disk, failures, disk space."""
    m = _REPORT.search(text or "")
    if not m:
        return None
    row = _SNAPSHOT_ROW.search(text or "")
    return {"tables": int(m["tables"].replace(",", "")), "rows": int(m["rows"].replace(",", "")),
            "differing": int(m["differing"]), "failed": int(m["failed"]),
            "disk_free_gb": float(m["free"]), "disk_total_gb": float(m["total"]),
            "snapshot_row": int(row.group(1)) if row else None}


def backup_status(pass_id: str | None, files: dict[str, dict[str, Any]],
                  progress: dict[str, Any] | None, progress_mtime: float | None,
                  state: dict[str, Any] | None, now: float, task_running: bool) -> dict[str, Any]:
    """Where the backup is, from the files it leaves.

    `files` maps 'supabase.log' style keys (stage.ext) of the newest pass to
    {size, mtime}. progress.json outlives its run, so it only counts as live
    progress while it is fresh and its run has not been recorded as finished."""
    out: dict[str, Any] = {"pass_id": pass_id, "pass_started_at": pass_started_at(pass_id) if pass_id else None,
                           "stage": None, "copy": None, "warnings": []}
    has = lambda k: k in files  # noqa: E731
    if not pass_id:
        out["stage"] = "no backup pass found"
    elif has("report.log") and files["report.log"].get("size", 0) > 0:
        out["stage"] = "finished"
        out["finished_at"] = files["report.log"].get("mtime")
    elif has("report.err"):
        out["stage"] = "writing the report"
    elif has("duckdb.err"):
        out["stage"] = "building the local DuckDB copy"
    elif has("supabase.err") or has("github.err"):
        out["stage"] = "copying the database and GitHub"
    else:
        out["stage"] = "starting"

    p_started = parse_iso((progress or {}).get("started_at"))
    p_now = parse_iso((progress or {}).get("now"))
    s_finished = parse_iso((state or {}).get("run_finished_at"))
    belongs = (p_started is not None and out["pass_started_at"] is not None
               and p_started >= out["pass_started_at"] - 60)
    done = s_finished is not None and p_started is not None and s_finished >= p_started
    if belongs and not done and out["stage"] == "copying the database and GitHub":
        age = now - (p_now or progress_mtime or now)
        out["copy"] = {
            "table": progress.get("table"),
            "rows_pulled": progress.get("rows_pulled"),
            "rows_per_s": progress.get("rows_per_s_reading"),
            "rows_per_s_wall": progress.get("rows_per_s_wall"),
            "elapsed_s": progress.get("elapsed_s"),
            "paused_s": progress.get("paused_s"),
            "updated_at": p_now or progress_mtime,
            "age_s": age,
        }
        if age > PROGRESS_FRESH_SEC:
            out["warnings"].append(f"the table copy has not reported progress for {int(age // 60)} min")
    if out["stage"] != "finished" and not task_running and pass_id:
        out["warnings"].append("the pass is not finished but the backup task is not running")
    if state:
        out["last_copy"] = {
            "run_id": state.get("run_id"),
            "kind": state.get("kind"),
            "started_at": parse_iso(state.get("run_started_at")),
            "finished_at": s_finished,
            "tables": state.get("tables"),
            "rows_pulled": state.get("rows_pulled"),
            "failed_tables": len(state.get("failed_tables") or []),
            "mismatched_tables": len(state.get("mismatched_tables") or []),
        }
    return out
