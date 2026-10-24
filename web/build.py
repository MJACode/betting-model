#!/usr/bin/env python3
"""Build the Signal Base marketing site into dist/.

Legal pages are rendered from web/content/*.md. The source files stay intact.
This script strips the DRAFT banner, fills [DATE], and removes bracketed
attorney notes. The build fails if a '[' survives in any generated HTML page.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
from datetime import datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from zoneinfo import ZoneInfo

WEB = Path(__file__).resolve().parent
REPO = WEB.parent
CONTENT = WEB / "content"
TEMPLATES = WEB / "templates"
STATIC = WEB / "static"

EMAIL = "Signalbaseskinny@gmail.com"
PHONE_LABEL = "1-800-GAMBLER"
PHONE_HREF = "tel:+18004262537"


class PlaceholderError(SystemExit):
    """A '[' survived rendering. SystemExit so the build process fails."""


def escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def publish_date(iso: str | None) -> str:
    if iso:
        day = datetime.strptime(iso, "%Y-%m-%d").date()
    else:
        day = datetime.now(ZoneInfo("America/New_York")).date()
    return f"{day.strftime('%B')} {day.day}, {day.year}"


def strip_draft_banner(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if line.lstrip().startswith(">") and "DRAFT" in line:
            continue
        kept.append(line)
    return "\n".join(kept).lstrip("\n")


def strip_known_placeholders(text: str, when: str) -> str:
    text = text.replace("[DATE]", when)
    text = re.sub(r"\[ATTORNEY NOTE:[^\]]*\]", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def inline(text: str) -> str:
    pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)|\*\*([^*]+)\*\*")
    parts: list[str] = []
    pos = 0
    for match in pattern.finditer(text):
        parts.append(escape(text[pos:match.start()]))
        if match.group(1) is not None:
            url = match.group(2).strip()
            if not (url.startswith("https://") or url.startswith("mailto:")):
                raise PlaceholderError(f"refusing link {url}")
            parts.append(f'<a href="{escape(url)}">{escape(match.group(1))}</a>')
        else:
            parts.append(f"<strong>{escape(match.group(3))}</strong>")
        pos = match.end()
    parts.append(escape(text[pos:]))
    html = "".join(parts)
    html = html.replace(
        EMAIL,
        f'<a href="mailto:{EMAIL}">{EMAIL}</a>',
    )
    html = html.replace(
        PHONE_LABEL,
        f'<a href="{PHONE_HREF}">{PHONE_LABEL}</a>',
    )
    return html


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def render_legal_markdown(source: str, when: str) -> tuple[str, list[tuple[str, str]]]:
    """Return article HTML and (slug, heading) pairs. Raises if '[' survives."""
    text = strip_known_placeholders(strip_draft_banner(source), when)
    blocks = _blocks(text)
    html_parts: list[str] = []
    headings: list[tuple[str, str]] = []
    for kind, value in blocks:
        if kind == "h1":
            continue
        if kind == "h2":
            slug = slugify(value)
            headings.append((slug, value))
            html_parts.append(f'<h2 id="{slug}">{inline(value)}</h2>')
        elif kind == "ul":
            items = "".join(f"<li>{inline(item)}</li>" for item in value)
            html_parts.append(f"<ul>{items}</ul>")
        else:
            html_parts.append(f"<p>{inline(value)}</p>")
    html = "\n".join(html_parts)
    if "[" in html:
        raise PlaceholderError("a '[' placeholder survived legal rendering")
    if "DRAFT" in html or "ATTORNEY NOTE" in html:
        raise PlaceholderError("draft or attorney note text survived legal rendering")
    return html, headings


def _blocks(text: str) -> list[tuple[str, object]]:
    lines = text.splitlines()
    blocks: list[tuple[str, object]] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(("p", " ".join(part.strip() for part in paragraph)))
            paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            flush()
            i += 1
            continue
        if line.startswith("# "):
            flush()
            blocks.append(("h1", line[2:].strip()))
            i += 1
            continue
        if line.startswith("## "):
            flush()
            blocks.append(("h2", line[3:].strip()))
            i += 1
            continue
        if line.startswith("- "):
            flush()
            items: list[str] = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(lines[i][2:].strip())
                i += 1
            blocks.append(("ul", items))
            continue
        paragraph.append(line)
        i += 1
    flush()
    return blocks


def _b64url_json(segment: str) -> dict:
    padded = segment + "=" * (-len(segment) % 4)
    return json.loads(base64.urlsafe_b64decode(padded))


def assert_public_anon(url: str, key: str) -> None:
    if key.count(".") != 2:
        raise SystemExit("supabase anon key is not a JWT")
    payload = _b64url_json(key.split(".")[1])
    if payload.get("role") != "anon":
        raise SystemExit("refusing a Supabase key whose role is not anon")
    ref = str(payload.get("ref") or "")
    if not ref or ref not in url:
        raise SystemExit("anon key project ref does not match the Supabase URL")


def retired_model_ids() -> list[str]:
    vendored_path = WEB / "src" / "retired-models.json"
    vendored = json.loads(vendored_path.read_text(encoding="utf-8"))
    if not isinstance(vendored, list) or not all(isinstance(x, str) for x in vendored):
        raise SystemExit("web/src/retired-models.json must be a list of strings")
    mobile = REPO / "mobile" / "src" / "lib" / "thresholds.generated.ts"
    if mobile.is_file():
        match = re.search(
            r"export const RETIRED_MODELS = new Set<string>\(\[([\s\S]*?)\]\);",
            mobile.read_text(encoding="utf-8"),
        )
        if not match:
            raise SystemExit("could not read RETIRED_MODELS from the app")
        parsed = re.findall(r"'([^']+)'", match.group(1))
        if set(parsed) != set(vendored):
            raise SystemExit(
                "web/src/retired-models.json does not match "
                "mobile/src/lib/thresholds.generated.ts RETIRED_MODELS"
            )
    return vendored


def record_js() -> str:
    config = json.loads((WEB / "src" / "public-config.json").read_text(encoding="utf-8"))
    url = config["supabaseUrl"]
    key = config["supabaseAnonKey"]
    assert_public_anon(url, key)
    math = (WEB / "src" / "record-math.mjs").read_text(encoding="utf-8")
    math = re.sub(r"^export ", "", math, flags=re.MULTILINE)
    boot = (WEB / "src" / "record-boot.js").read_text(encoding="utf-8")
    payload = {
        "supabaseUrl": url,
        "supabaseAnonKey": key,
        "retired": retired_model_ids(),
    }
    return "const CONFIG = " + json.dumps(payload, indent=2) + ";\n" + math + "\n" + boot


def header() -> str:
    return """<a class="skip" href="#main">Skip to content</a>
<header class="site-header">
  <div class="wrap header-inner">
    <a class="logo" href="/">
      <img src="/mark.png" width="32" height="32" alt="">
      <span>Signal Base</span>
    </a>
    <nav class="nav" aria-label="Primary">
      <a href="/#what">What it does</a>
      <a href="/#how">How it works</a>
      <a class="nav-cta" href="/#get">Get the app</a>
    </nav>
  </div>
</header>"""


def footer(year: int) -> str:
    return f"""<footer class="site-footer">
  <div class="wrap">
    <div class="footer-top">
      <div>
        <a class="logo" href="/">
          <img src="/mark.png" width="32" height="32" alt="">
          <span>Signal Base</span>
        </a>
        <p class="footer-domain"><a href="/">signalbase-ai.com</a></p>
      </div>
      <nav class="footer-nav" aria-label="Footer">
        <a href="/terms">Terms and Conditions</a>
        <a href="/privacy">Privacy Policy</a>
        <a href="mailto:{EMAIL}">{EMAIL}</a>
      </nav>
    </div>
    <div class="disclaimer">
      <p><strong class="age">21+</strong> For people 21 and older. Signal Base is for information and entertainment. It is not a sportsbook, takes no bets and does not pay out winnings. Past results don't guarantee future results.</p>
      <p>Gambling problem? Call <a href="{PHONE_HREF}">{PHONE_LABEL}</a>. Bet only where it's legal for you.</p>
    </div>
    <p class="copyright">© {year} Signal Base. Apple and App Store are trademarks of Apple Inc.</p>
  </div>
</footer>"""


def shell(title: str, description: str, body: str, year: int, script: bool) -> str:
    extra = '<script src="/record.js" defer></script>' if script else ""
    csp = (
        "default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; "
        "connect-src 'self' https://vvprgnrmzeekokzkrkfu.supabase.co; "
        "font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'"
    )
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#0b1220">
<meta name="description" content="{escape(description)}">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<title>{escape(title)}</title>
<link rel="icon" href="/favicon.png" type="image/png">
<link rel="stylesheet" href="/site.css">
</head>
<body>
{header()}
{body}
{footer(year)}
{extra}
</body>
</html>
"""
    if "[" in page:
        raise PlaceholderError(f"'[' survived in {title}")
    return page


def legal_page(name: str, h1: str, description: str, when: str, year: int) -> str:
    source = (CONTENT / f"{name}.md").read_text(encoding="utf-8")
    body, headings = render_legal_markdown(source, when)
    toc = "\n".join(
        f'<li><a href="#{slug}">{escape(heading)}</a></li>' for slug, heading in headings
    )
    template = (TEMPLATES / "legal.html").read_text(encoding="utf-8")
    current = ' aria-current="page"'
    html = (
        template.replace("{{H1}}", escape(h1))
        .replace("{{TOC}}", toc)
        .replace("{{BODY}}", body)
        .replace("{{PRIVACY_CURRENT}}", current if name == "privacy" else "")
        .replace("{{TERMS_CURRENT}}", current if name == "terms" else "")
    )
    title = f"{h1} — Signal Base"
    return shell(title, description, html, year, script=False)


def build(out: Path, when_iso: str | None) -> str:
    when = publish_date(when_iso)
    year = int(when.rsplit(" ", 1)[1])
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    landing = (TEMPLATES / "landing.html").read_text(encoding="utf-8")
    (out / "index.html").write_text(
        shell(
            "Signal Base",
            "Sports picks with a record you can check. Signal Base runs models on every game and tracks every pick in units.",
            landing,
            year,
            script=True,
        ),
        encoding="utf-8",
    )
    terms = legal_page(
        "terms",
        "Terms and Conditions",
        "Terms and Conditions for Signal Base.",
        when,
        year,
    )
    privacy = legal_page(
        "privacy",
        "Privacy Policy",
        "Privacy Policy for Signal Base.",
        when,
        year,
    )
    (out / "terms").mkdir()
    (out / "privacy").mkdir()
    (out / "terms" / "index.html").write_text(terms, encoding="utf-8")
    (out / "privacy" / "index.html").write_text(privacy, encoding="utf-8")
    for name in ("site.css", "mark.png", "favicon.png"):
        shutil.copyfile(STATIC / name, out / name)
    (out / "record.js").write_text(record_js(), encoding="utf-8")
    for html in out.rglob("*.html"):
        text = html.read_text(encoding="utf-8")
        if "[" in text:
            raise PlaceholderError(f"'[' survived in {html}")
        if "ATTORNEY NOTE" in text or "[DATE]" in text:
            raise PlaceholderError(f"placeholder survived in {html}")
        if "DRAFT —" in text or "FOR ATTORNEY REVIEW" in text:
            raise PlaceholderError(f"draft banner survived in {html}")
    return when


def serve(out: Path, port: int) -> None:
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(out), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path != "/" and path.endswith("/"):
                path = path[:-1]
            rel = path.lstrip("/")
            if rel and not Path(rel).suffix and (out / rel / "index.html").is_file():
                self.path = f"/{rel}/index.html"
            elif path == "/":
                self.path = "/index.html"
            super().do_GET()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Serving {out} at http://127.0.0.1:{port}/")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the Signal Base site")
    parser.add_argument("--out", default=str(WEB / "dist"))
    parser.add_argument("--date", help="Publish date as YYYY-MM-DD. Defaults to today in America/New_York.")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    out = Path(args.out)
    when = build(out, args.date)
    print(f"Built {out} (effective date {when})")
    if args.serve:
        serve(out, args.port)


if __name__ == "__main__":
    main()
