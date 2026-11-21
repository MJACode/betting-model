"""The published record, checked against the "SignalBase Record History" sheet.

Matt, 2026-11-21: mike said to use the sheet as "the single source of truth",
and "we should always do a check against this. still do what we're doing
today, but use that as a reference point to make sure that we're always in
sync with it." So the record is still computed here, from `picks`, exactly as
Discord and the app compute it; this module only READS the sheet and says
where the two disagree. It never changes a pick, a view or a post.

Three comparisons, each one a list of findings:

  picks     every graded posted pick, by pick_id: in the record and not on the
            sheet, on the sheet and not in the record, a different result, or
            units that differ by more than half a cent. Units are the record's
            own (published_pick_unit_profit), rounded to 2 places as the sheet
            prints them.
  all_time  Discord's last all-time line (results_snapshots) against the
            sheet's graded picks up to that line's game date.
  daily     each Discord daily recap from DAILY_POST_CHECK_FROM on, against
            the sheet's picks for that date. Recaps before then are the old
            posts that were never restated (2026-09-05, 09-26, 10-27, 11-17
            and 08-29..08-31); they would report the same gap every hour.

A pick graded in the last SETTLE_GRACE is left out of "not on the sheet": the
sheet refreshes about once an hour, so a pick graded at 10:58 is not yet a
disagreement at 11:00.

Every run is stored (record_sheet_checks). A run with findings posts ONE ops
alert per distinct set of findings per ET day, ledgered in push_sent, so an
hourly check does not post the same gap 24 times.
"""
from __future__ import annotations

import csv
import hashlib
from decimal import ROUND_HALF_UP, Decimal
import io
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import requests

import config

ET = ZoneInfo("America/New_York")

SHEET_ID = "1FaUkZnjirMrh0G3Je3RpNoO6d9wq6CcKGZr9bbSovXo"
PICKS_GID = "963938855"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/htmlview"
EXPORT_URL = (f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export"
              f"?format=csv&gid={PICKS_GID}")

DAILY_POST_CHECK_FROM = "2026-11-21"
SETTLE_GRACE = timedelta(hours=3)
# One cent. The sheet rounds a few losses up where the record's own figure
# rounds down: measured 2026-11-21, three of 1,705 picks, all plus-money
# losses (#1660578 and #4473237 at +113: record -0.88495, sheet -0.89;
# #3849773 at +177: -0.56497, sheet -0.57). A real disagreement is a stake,
# a result or a missing pick, never one cent.
UNITS_TOLERANCE = 0.011
# A summed line (all-time, one day) is the sum of per-pick figures the sheet
# has already rounded to the cent, against Discord's unrounded sum. Measured
# 2026-11-21 over 1,705 picks: +59.84 on the sheet's rows, +59.86 unrounded.
AGG_TOLERANCE = 0.05
ALERT_KIND = "record_sheet_drift"
MAX_LISTED = 15

_GRADED = {"WIN", "LOSS", "PUSH"}


class SheetUnreadable(RuntimeError):
    """The sheet could not be fetched or did not look like the Picks tab."""


def _cents(x) -> float:
    """Half away from zero, as the sheet prints a unit figure (Python's round
    is half-to-even, which reads 0.125 as 0.12)."""
    return float(Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _units(text) -> float:
    s = str(text or "").strip().replace("u", "").replace("+", "").replace("−", "-")
    return float(s) if s else 0.0


def parse_sheet_csv(text: str) -> dict[int, dict]:
    """Graded rows of the Picks tab, keyed by pick_id. OPEN rows are skipped:
    the sheet counts them in no total."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "pick_id" not in rows[0] or "result" not in rows[0]:
        raise SheetUnreadable("the Picks tab has no pick_id / result columns")
    out: dict[int, dict] = {}
    for r in rows:
        result = (r.get("result") or "").strip().upper()
        if result not in _GRADED:
            continue
        pid = (r.get("pick_id") or "").strip()
        if not pid.isdigit():
            continue
        out[int(pid)] = {
            "date": (r.get("date") or "").strip(),
            "sport": (r.get("sport") or "").strip(),
            "pick": (r.get("pick") or "").strip(),
            "result": result,
            "units": _cents(_units(r.get("units"))),
        }
    return out


def fetch_sheet(get=requests.get) -> dict[int, dict]:
    resp = get(EXPORT_URL, timeout=30)
    if resp.status_code != 200:
        raise SheetUnreadable(f"sheet export returned HTTP {resp.status_code}")
    ctype = resp.headers.get("content-type", "")
    if "text/csv" not in ctype:
        # A private sheet answers 200 with Google's sign-in page.
        raise SheetUnreadable(f"sheet export returned {ctype or 'no content type'}, not CSV")
    return parse_sheet_csv(resp.content.decode("utf-8-sig"))


def _record_sql() -> str:
    """The Discord recap's own predicate (tracking.discord_notifier._SETTLED_SQL)
    with this check's select list, so the two can never count different picks."""
    from tracking.discord_notifier import _SETTLED_SQL
    head, sep, tail = _SETTLED_SQL.partition("FROM picks p")
    if not sep:
        raise RuntimeError("the recap query has no FROM picks p")
    select = """
        SELECT p.pick_id, p.game_date, p.sport, p.pick_label, p.result, p.settled_at,
               published_pick_unit_profit(COALESCE(p.decision_odds, p.dk_odds), p.result, p.stake_units)
        """
    return select + sep + tail.format(window=">= %s")


def record_picks(conn) -> dict[int, dict]:
    out: dict[int, dict] = {}
    for pid, gd, sport, label, result, settled_at, units in conn.execute(
            _record_sql(), (config.PAPER_TRADING_START,)).fetchall():
        out[int(pid)] = {
            "date": str(gd), "sport": sport, "pick": label, "result": result,
            "units": _cents(units or 0), "settled_at": settled_at,
        }
    return out


def _parse_ts(value):
    if value is None or isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def compare_picks(record: dict[int, dict], sheet: dict[int, dict],
                  now: datetime) -> list[dict]:
    findings = []
    for pid in sorted(set(record) | set(sheet)):
        r, s = record.get(pid), sheet.get(pid)
        if r and not s:
            ts = _parse_ts(r.get("settled_at"))
            if ts is not None and ts.tzinfo is None:
                ts = ts.replace(tzinfo=ET)
            if ts is not None and now - ts < SETTLE_GRACE:
                continue
            findings.append({"kind": "not_on_sheet", "pick_id": pid, "date": r["date"],
                             "pick": r["pick"], "record": f"{r['result']} {r['units']:+.2f}u"})
        elif s and not r:
            findings.append({"kind": "not_in_record", "pick_id": pid, "date": s["date"],
                             "pick": s["pick"], "sheet": f"{s['result']} {s['units']:+.2f}u"})
        elif r["result"] != s["result"] or abs(r["units"] - s["units"]) > UNITS_TOLERANCE:
            findings.append({"kind": "differs", "pick_id": pid, "date": r["date"],
                             "pick": r["pick"],
                             "record": f"{r['result']} {r['units']:+.2f}u",
                             "sheet": f"{s['result']} {s['units']:+.2f}u"})
    return findings


def _tally(rows) -> tuple[int, int, int, float]:
    w = sum(1 for x in rows if x["result"] == "WIN")
    l = sum(1 for x in rows if x["result"] == "LOSS")
    p = sum(1 for x in rows if x["result"] == "PUSH")
    return w, l, p, round(sum(x["units"] for x in rows), 2)


def _line(t) -> str:
    w, l, p, u = t
    return f"{w}-{l}" + (f"-{p}" if p else "") + f", {u:+.2f}u"


def compare_posts(conn, sheet: dict[int, dict]) -> list[dict]:
    """Discord's stored lines (results_snapshots) against the sheet."""
    findings = []
    row = conn.execute("""
        SELECT game_date, wins, losses, pushes, units FROM results_snapshots
        WHERE scope = 'all_time' AND sport IS NULL
        ORDER BY game_date DESC LIMIT 1""").fetchone()
    if row:
        gd = str(row[0])
        posted = (int(row[1]), int(row[2]), int(row[3]), round(float(row[4]), 2))
        mine = _tally([s for s in sheet.values() if s["date"] <= gd])
        if posted[:3] != mine[:3] or abs(posted[3] - mine[3]) > AGG_TOLERANCE:
            findings.append({"kind": "all_time", "date": gd,
                             "discord": _line(posted), "sheet": _line(mine)})
    for gd, w, l, p, u in conn.execute("""
            SELECT game_date, wins, losses, pushes, units FROM results_snapshots
            WHERE scope = 'daily' AND sport IS NULL AND game_date >= %s
            ORDER BY game_date""", (DAILY_POST_CHECK_FROM,)).fetchall():
        gd = str(gd)
        posted = (int(w), int(l), int(p), round(float(u), 2))
        mine = _tally([s for s in sheet.values() if s["date"] == gd])
        if posted[:3] != mine[:3] or abs(posted[3] - mine[3]) > AGG_TOLERANCE:
            findings.append({"kind": "daily", "date": gd,
                             "discord": _line(posted), "sheet": _line(mine)})
    return findings


def format_alert(findings: list[dict], record_n: int, sheet_n: int) -> str:
    lines = [f"Record {record_n} graded picks, sheet {sheet_n}. {len(findings)} difference(s):"]
    for f in findings[:MAX_LISTED]:
        if f["kind"] in ("all_time", "daily"):
            label = "Discord all-time" if f["kind"] == "all_time" else "Discord daily"
            lines.append(f"- {label} {f['date']}: posted {f['discord']}, sheet {f['sheet']}")
        elif f["kind"] == "differs":
            lines.append(f"- {f['date']} {f['pick']} (#{f['pick_id']}): record {f['record']}, sheet {f['sheet']}")
        elif f["kind"] == "not_on_sheet":
            lines.append(f"- {f['date']} {f['pick']} (#{f['pick_id']}): in the record ({f['record']}), not on the sheet")
        else:
            lines.append(f"- {f['date']} {f['pick']} (#{f['pick_id']}): on the sheet ({f['sheet']}), not in the record")
    if len(findings) > MAX_LISTED:
        lines.append(f"...and {len(findings) - MAX_LISTED} more (record_sheet_checks).")
    lines.append(f"Sheet: {SHEET_URL}")
    return "\n".join(lines)


def _store(conn, now, ok, record_n, sheet_n, findings, error=None) -> None:
    conn.execute("""
        INSERT INTO record_sheet_checks
            (checked_at, ok, record_graded, sheet_graded, findings, error)
        VALUES (%s, %s, %s, %s, %s::jsonb, %s)""",
        (now.isoformat(), ok, record_n, sheet_n, json.dumps(findings), error))
    conn.commit()


def run_record_sheet_check(conn=None, *, get=requests.get, now: datetime | None = None,
                           alert=None) -> dict:
    """One check. Returns {"ok", "record", "sheet", "findings", "alerted"}."""
    from data.db import get_connection
    if alert is None:
        from tracking.watch_util import post_ops_alert as alert
    now = now or datetime.now(ET)
    own = conn is None
    conn = conn or get_connection()
    try:
        try:
            sheet = fetch_sheet(get)
        except Exception as exc:  # noqa: BLE001 - a check that cannot read says so
            msg = f"{type(exc).__name__}: {exc}"[:300]
            _store(conn, now, False, None, None, [], msg)
            sent = _alert_once(conn, now, [{"kind": "unreadable", "error": msg}],
                               f"The record check could not read the sheet: {msg}\nSheet: {SHEET_URL}",
                               alert)
            return {"ok": False, "error": msg, "alerted": sent}
        record = record_picks(conn)
        findings = compare_picks(record, sheet, now) + compare_posts(conn, sheet)
        _store(conn, now, not findings, len(record), len(sheet), findings)
        sent = False
        if findings:
            sent = _alert_once(conn, now, findings,
                               format_alert(findings, len(record), len(sheet)), alert)
        return {"ok": not findings, "record": len(record), "sheet": len(sheet),
                "findings": findings, "alerted": sent}
    finally:
        if own:
            conn.close()


def _alert_once(conn, now, findings, text, alert) -> bool:
    sig = hashlib.md5(json.dumps(findings, sort_keys=True, default=str).encode()).hexdigest()[:12]
    lock = f"{ALERT_KIND}:{now.date().isoformat()}:{sig}"
    if conn.execute("SELECT 1 FROM push_sent WHERE lock_key = %s AND kind = %s",
                    (lock, ALERT_KIND)).fetchone():
        return False
    if not alert("Record out of sync with the sheet", text):
        return False
    conn.execute("INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, %s, %s) "
                 "ON CONFLICT (lock_key, kind) DO NOTHING",
                 (lock, ALERT_KIND, now.isoformat()))
    conn.commit()
    return True


if __name__ == "__main__":
    res = run_record_sheet_check()
    print(json.dumps({k: v for k, v in res.items() if k != "findings"}, default=str))
    for f in res.get("findings", [])[:50]:
        print(json.dumps(f, default=str))
