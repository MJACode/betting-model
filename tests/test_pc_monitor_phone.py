"""The Betting PC monitor on mike's phone (mike, 2026-11-21: "can u create an
app for my phone too").

The PC writes its page's view to one private row (pc_monitor_state); the cloud
monitor serves the same page at /pc/, opened by the phone link's token, which
must open nothing else. The PC window shows the link as a QR code drawn by
pc_monitor/qr.py, checked here against an independent implementation.
"""

from __future__ import annotations

import json
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
TOKEN_MAIN = "main-dashboard-token"
TOKEN_PHONE = "phone-link-token-abc"


# ── the QR code ─────────────────────────────────────────────────────────────

def _qrcode_terminal() -> Path | None:
    for d in [ROOT, *ROOT.parents]:
        p = d / "mobile" / "node_modules" / "qrcode-terminal"
        if (p / "vendor" / "QRCode" / "index.js").is_file():
            return p
    return None


def test_qr_matches_an_independent_encoder_module_for_module():
    """Every module of every mask, versions 1-6, levels L and M, against
    qrcode-terminal (Expo installs it under mobile/node_modules)."""
    from tests._node import NODE
    from pc_monitor import qr
    pkg = _qrcode_terminal()
    if NODE is None or pkg is None:
        pytest.skip("node or mobile/node_modules/qrcode-terminal not available")
    base = "https://worker-production-229d.up.railway.app/pc/?token=" + "Ab3_-" * 30
    cases = []
    for ecl in ("L", "M"):
        for n in (5, 14, 17, 25, 32, 40, 53, 60, 75, 78, 88, 100, 106, 120, 134):
            try:
                qr.smallest_version(base[:n].encode(), ecl)
            except ValueError:
                continue
            cases.append([base[:n], ecl])
    out = subprocess.run([NODE, str(ROOT / "tests" / "qr_reference.js"), str(pkg), json.dumps(cases)],
                         capture_output=True, text=True, check=True, encoding="utf-8")
    ref = json.loads(out.stdout)
    versions = set()
    for (text, ecl), r in zip(cases, ref):
        ver = qr.smallest_version(text.encode(), ecl)
        assert ver == r["version"], (text, ecl)
        versions.add(ver)
        for m in range(8):
            mine = ["".join("1" if d else "0" for d in row) for row in qr.encode(text, ecl, mask=m, version=ver)]
            assert mine == r["masks"][m], f"{ecl} len {len(text)} v{ver} mask {m}"
    assert versions == {1, 2, 3, 4, 5, 6}


def test_qr_svg_and_length_limit():
    from pc_monitor import qr
    link = "https://worker-production-229d.up.railway.app/pc/?token=" + "x" * 32
    s = qr.svg(link)
    assert s.startswith("<svg") and 'fill="#000"' in s
    assert len(qr.encode(link)) == 37                    # version 5
    with pytest.raises(ValueError):
        qr.encode("x" * 200)


# ── how often the PC writes ─────────────────────────────────────────────────

def test_the_pc_writes_fast_only_while_a_phone_is_watching():
    from pc_monitor import readers as R
    assert R.publish_interval(None) == 60.0
    assert R.publish_interval(5.0) == 2.0
    assert R.publish_interval(59.0) == 2.0
    assert R.publish_interval(61.0) == 60.0


class _FakeDb:
    def __init__(self):
        self.writes: list[tuple[str, tuple]] = []

    def write(self, sql, params=None):
        self.writes.append((sql, params))
        return [("tok-from-db",)] if "RETURNING phone_token" in sql else []

    def rows(self, sql, params=None):
        return [(12.0,)]                                  # a phone asked 12 s ago


def test_the_written_view_never_carries_the_token():
    from pc_monitor.app import Collector
    c = Collector()
    db = _FakeDb()
    c._publish(db)
    assert c.phone_token == "tok-from-db"
    published = [p for s, p in db.writes if s.strip().startswith("UPDATE pc_monitor_state SET view")]
    assert len(published) == 1
    payload_json, host = published[0]
    assert "tok-from-db" not in payload_json and '"phone"' not in payload_json
    assert json.loads(payload_json)["host"] == host
    # Within 2 s it does not write again; a phone is watching, so 2 s is the gap.
    c._publish(db)
    assert len([1 for s, _ in db.writes if "SET view" in s]) == 1
    assert c.panels.get("publish")["data"]["phone_watching"] is True


def test_the_pc_window_gets_the_link_and_its_qr_code():
    from pc_monitor.app import Collector, build_server
    c = Collector()
    c.phone_token = "tok-local"
    srv = build_server(0, c)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        port = srv.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state") as r:
            state = json.loads(r.read())
        assert state["phone"]["url"].endswith("/pc/?token=tok-local")
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/phone-qr.svg") as r:
            assert r.headers["Content-Type"] == "image/svg+xml" and r.read().startswith(b"<svg")
    finally:
        srv.shutdown()


# ── the cloud monitor's /pc/ ────────────────────────────────────────────────

@pytest.fixture()
def cloud(monkeypatch):
    from monitoring import server
    calls = {"demand": 0}
    state = {"view": {"now": 1.0, "app": "pc_monitor", "host": "MAHome", "feed": {}},
             "age_s": 5.0, "token": TOKEN_PHONE, "host": "MAHome", "read_at": 0.0}
    monkeypatch.setattr(server, "pc_state", lambda: state)
    monkeypatch.setattr(server, "pc_mark_demand", lambda host: calls.__setitem__("demand", calls["demand"] + 1))
    srv = server.build_server("127.0.0.1", 0, TOKEN_MAIN)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", calls, state
    srv.shutdown()


def _get(url: str) -> tuple[int, bytes, dict]:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(url) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def test_the_phone_token_opens_the_pc_page(cloud):
    base, calls, _ = cloud
    code, body, headers = _get(f"{base}/pc/api/state?token={TOKEN_PHONE}")
    assert code == 200
    data = json.loads(body)
    assert data["host"] == "MAHome" and data["pc_reported_age_s"] >= 5.0
    assert TOKEN_PHONE not in body.decode() and "token" not in data
    assert headers.get("Referrer-Policy") == "no-referrer"
    assert calls["demand"] == 1
    code, body, _ = _get(f"{base}/pc/?token={TOKEN_PHONE}")
    assert code == 200 and b"Betting PC monitor" in body
    code, _, headers = _get(f"{base}/pc?token={TOKEN_PHONE}")
    assert code == 302 and headers["Location"] == f"/pc/?token={TOKEN_PHONE}"


def test_the_phone_token_opens_nothing_else(cloud):
    base, _, _ = cloud
    for path in ("/", "/api/snapshot", "/api/stream", "/index.html"):
        code, _, _ = _get(f"{base}{path}?token={TOKEN_PHONE}")
        assert code == 401, path


def test_a_wrong_or_missing_token_is_refused_and_the_main_token_still_works(cloud):
    base, _, _ = cloud
    assert _get(f"{base}/pc/api/state?token=wrong")[0] == 401
    assert _get(f"{base}/pc/api/state")[0] == 401
    assert _get(f"{base}/pc/?token=wrong")[0] == 401
    assert _get(f"{base}/pc/api/state?token={TOKEN_MAIN}")[0] == 200


def test_before_any_pc_has_reported_the_page_says_so(cloud, monkeypatch):
    from monitoring import server
    base, _, _ = cloud
    monkeypatch.setattr(server, "pc_state", lambda: None)
    code, body, _ = _get(f"{base}/pc/api/state?token={TOKEN_MAIN}")
    assert code == 503 and b"has not reported" in body


def test_a_database_failure_is_a_503_not_a_crash(cloud, monkeypatch):
    from monitoring import server
    base, _, _ = cloud

    def boom():
        raise RuntimeError("pooler dropped")
    monkeypatch.setattr(server, "pc_state", boom)
    assert _get(f"{base}/pc/api/state?token={TOKEN_MAIN}")[0] == 503
    # With the database down only the dashboard's own token can open the page.
    assert _get(f"{base}/pc/api/state?token={TOKEN_PHONE}")[0] == 401


def test_the_reported_age_keeps_growing_after_the_read():
    from monitoring.server import pc_payload
    v = pc_payload({"view": {"now": 1, "phone": {"url": "x"}}, "age_s": 10.0, "read_at": 100.0}, now=130.0)
    assert v["pc_reported_age_s"] == pytest.approx(40.0)
    assert "phone" not in v


def test_the_pick_page_parser_does_not_catch_the_pc_paths():
    from tracking.pick_landing import parse_pick_path
    for path in ("/pc", "/pc/", "/pc/api/state"):
        assert parse_pick_path(path) is None


def test_the_page_asks_the_path_it_was_served_from():
    """One HTML file serves the PC (/) and the phone (/pc/?token=...)."""
    html = (ROOT / "pc_monitor" / "static" / "index.html").read_text(encoding="utf-8")
    assert 'fetch("/api/state"' not in html
    assert '+ "api/state" + location.search' in html
