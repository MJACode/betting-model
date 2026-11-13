#!/usr/bin/env python
"""A local mirror of the whole GitHub setup, on mike's machine.

mike, 2026-11-03: *"can you also mirror github on my machine? the full setup"*.
The partner of scripts/local_mirror.py (the Supabase copy). For every repo the
logged-in gh account can reach under the owners below:

  * `git clone --mirror` into <dest>/<owner>/<repo>.git: every branch, tag and
    GitHub's refs/pull/* PR heads. A rerun refreshes with
    `git remote update --prune`. The wiki, when one exists, beside it as
    <repo>.wiki.git.
  * <dest>/<owner>/<repo>.meta/: JSON per item: issues and PRs, every issue
    comment, review and review comment, labels, milestones, releases (assets
    downloaded), workflows and recent runs, deployments, repo settings,
    branches and their protection, rulesets, webhooks, deploy keys, Actions
    secret and variable NAMES (GitHub never returns values), environments,
    collaborators, and the rest listed in ITEMS.
  * <repo>.meta/_export_report.json: for every item, the HTTP status it got.
    An item the token may not read (403/404, usually "needs admin") is
    recorded with its status and message, never skipped silently.

AUTH. Git uses gh's credential helper (already configured for github.com on
this machine; passed explicitly too, so a scheduled run does not depend on it).
The API calls use `gh auth token`, held in memory for the Authorization
header only. The token is never written to a file, a remote URL or a log.

Usage:
  python local_mirror_github.py                       # every reachable repo
  python local_mirror_github.py --repo MJACode/betting-model
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

DEFAULT_DEST = Path(r"C:\Users\micha\Documents\betting_local_copies\github")
OWNERS = ("malkatrazz", "MJACode")
API = "https://api.github.com"
MAX_RUN_PAGES = 10          # 1,000 most recent workflow runs
MAX_PAGES = 200             # a backstop, recorded when it binds

# (file name, path template, list?)
ITEMS: list[tuple[str, str, bool]] = [
    ("repo", "/repos/{r}", False),
    ("topics", "/repos/{r}/topics", False),
    ("languages", "/repos/{r}/languages", False),
    ("issues", "/repos/{r}/issues?state=all&sort=created&direction=asc", True),
    ("issue_comments", "/repos/{r}/issues/comments?sort=created&direction=asc", True),
    ("issue_events", "/repos/{r}/issues/events", True),
    ("pulls", "/repos/{r}/pulls?state=all&sort=created&direction=asc", True),
    ("pull_review_comments", "/repos/{r}/pulls/comments?sort=created&direction=asc", True),
    ("commit_comments", "/repos/{r}/comments", True),
    ("labels", "/repos/{r}/labels", True),
    ("milestones", "/repos/{r}/milestones?state=all", True),
    ("releases", "/repos/{r}/releases", True),
    ("branches", "/repos/{r}/branches", True),
    ("rulesets", "/repos/{r}/rulesets?includes_parents=true", True),
    ("workflows", "/repos/{r}/actions/workflows", True),
    ("workflow_runs", "/repos/{r}/actions/runs", True),
    ("actions_permissions", "/repos/{r}/actions/permissions", False),
    ("actions_secrets", "/repos/{r}/actions/secrets", True),
    ("actions_variables", "/repos/{r}/actions/variables", True),
    ("dependabot_secrets", "/repos/{r}/dependabot/secrets", True),
    ("environments", "/repos/{r}/environments", True),
    ("deployments", "/repos/{r}/deployments", True),
    ("hooks", "/repos/{r}/hooks", True),
    ("deploy_keys", "/repos/{r}/keys", True),
    ("collaborators", "/repos/{r}/collaborators", True),
    ("invitations", "/repos/{r}/invitations", True),
    ("autolinks", "/repos/{r}/autolinks", True),
    ("pages", "/repos/{r}/pages", False),
    ("contributors", "/repos/{r}/contributors", True),
]
# Endpoints that wrap their list in an object.
WRAPPED = {"workflows": "workflows", "workflow_runs": "workflow_runs",
           "actions_secrets": "secrets", "actions_variables": "variables",
           "dependabot_secrets": "secrets", "environments": "environments"}


def _iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"{_iso()} {msg}", flush=True)


def gh_path() -> str | None:
    return shutil.which("gh") or (r"C:\Program Files\GitHub CLI\gh.exe"
                                  if os.path.exists(r"C:\Program Files\GitHub CLI\gh.exe") else None)


def gh_token() -> str:
    gh = gh_path()
    if not gh:
        raise SystemExit("gh CLI not found")
    out = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=30)
    tok = out.stdout.strip()
    if out.returncode != 0 or not tok:
        raise SystemExit("gh auth token returned nothing; run `gh auth login`")
    return tok


def parse_next_link(link_header: str | None) -> str | None:
    """The rel="next" URL of a GitHub Link header, if any."""
    if not link_header:
        return None
    for part in link_header.split(","):
        m = re.match(r'\s*<([^>]+)>\s*;\s*rel="([^"]+)"', part)
        if m and m.group(2) == "next":
            return m.group(1)
    return None


class _NoAuthOnRedirect(urllib.request.HTTPRedirectHandler):
    """Release assets redirect to object storage, which rejects a second
    Authorization scheme; drop the header when the host changes."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None and urllib.parse.urlparse(newurl).netloc != urllib.parse.urlparse(req.full_url).netloc:
            for h in list(new.headers):
                if h.lower() == "authorization":
                    del new.headers[h]
        return new


class GitHub:
    def __init__(self, token: str, opener: Callable | None = None):
        self._token = token
        self._open = opener or urllib.request.build_opener(_NoAuthOnRedirect()).open
        self.calls = 0

    def _request(self, url: str, accept: str = "application/vnd.github+json"):
        if not url.startswith("http"):
            url = API + url
        req = urllib.request.Request(url, headers={
            "Accept": accept, "Authorization": f"Bearer {self._token}",
            "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "betting-model-local-mirror"})
        for attempt in range(5):
            self.calls += 1
            try:
                with self._open(req, timeout=60) as resp:
                    return resp.status, resp.read(), dict(resp.headers)
            except urllib.error.HTTPError as exc:
                body = exc.read()
                hdrs = dict(exc.headers or {})
                remaining = hdrs.get("X-RateLimit-Remaining") or hdrs.get("x-ratelimit-remaining")
                if exc.code in (403, 429) and remaining == "0":
                    reset = int(hdrs.get("X-RateLimit-Reset") or hdrs.get("x-ratelimit-reset") or 0)
                    wait = max(5, min(3600, reset - int(time.time()) + 5))
                    log(f"rate limited; sleeping {wait}s")
                    time.sleep(wait)
                    continue
                if exc.code >= 500 and attempt < 4:
                    time.sleep(5 * (attempt + 1))
                    continue
                return exc.code, body, hdrs
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < 4:
                    time.sleep(5 * (attempt + 1))
                    continue
                return 0, str(exc).encode(), {}
        return 0, b"retries exhausted", {}

    def get(self, path: str) -> tuple[int, Any]:
        status, body, _ = self._request(path)
        return status, _json(body)

    def paginate(self, path: str, wrapped: str | None = None,
                 max_pages: int = MAX_PAGES) -> tuple[int, list, bool]:
        """(status of the first failing page or 200, items, capped?)."""
        sep = "&" if "?" in path else "?"
        url: str | None = f"{path}{sep}per_page=100"
        items: list = []
        pages = 0
        while url:
            status, body, headers = self._request(url)
            if status != 200:
                return status, (items if items else _json(body)), False
            data = _json(body)
            if wrapped and isinstance(data, dict):
                data = data.get(wrapped, [])
            items.extend(data if isinstance(data, list) else [data])
            pages += 1
            url = parse_next_link(headers.get("Link") or headers.get("link"))
            if url and pages >= max_pages:
                return 200, items, True
        return 200, items, False

    def download(self, url: str, dest: Path) -> int:
        status, body, _ = self._request(url, accept="application/octet-stream")
        if status == 200:
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_name(dest.name + ".tmp")
            tmp.write_bytes(body)
            os.replace(tmp, dest)
        return status


def _json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8")) if body else None
    except Exception:  # noqa: BLE001
        return {"raw": body[:500].decode("utf-8", "replace")}


def _message(data: Any) -> str:
    if isinstance(data, dict):
        return str(data.get("message") or data.get("raw") or "")[:200]
    return ""


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
    os.replace(tmp, path)


# ------------------------------------------------------------------ git

def _git_env() -> dict:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    return env


def _git_auth_args() -> list[str]:
    """Use gh's credential helper for this command only (no config written)."""
    gh = gh_path()
    if not gh:
        return []
    helper = "!'" + gh.replace("\\", "/") + "' auth git-credential"
    return ["-c", "credential.https://github.com.helper=",
            "-c", f"credential.https://github.com.helper={helper}"]


def _git(args: list[str], cwd: Path | None = None, timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *_git_auth_args(), *args], cwd=cwd, capture_output=True,
                          text=True, timeout=timeout, env=_git_env())


def mirror_git(url: str, path: Path) -> dict:
    """Clone --mirror the first time; `remote update --prune` after."""
    if path.exists() and (path / "HEAD").exists():
        p = _git(["-C", str(path), "remote", "update", "--prune"])
        action = "refreshed"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        p = _git(["clone", "--mirror", url, str(path)])
        action = "cloned"
    out = {"action": action, "ok": p.returncode == 0,
           "stderr_tail": (p.stderr or "").strip().splitlines()[-3:] if p.returncode else []}
    if p.returncode == 0:
        refs = _git(["-C", str(path), "for-each-ref", "--format=%(refname)"]).stdout.splitlines()
        out["refs"] = len(refs)
        out["branches"] = sum(r.startswith("refs/heads/") for r in refs)
        out["tags"] = sum(r.startswith("refs/tags/") for r in refs)
        out["pull_refs"] = sum(r.startswith("refs/pull/") for r in refs)
        fsck = _git(["-C", str(path), "count-objects", "-vH"]).stdout
        out["size"] = " ".join(l for l in fsck.splitlines() if l.startswith("size-pack"))
        lfs = _git(["-C", str(path), "show", "HEAD:.gitattributes"])
        out["uses_lfs"] = lfs.returncode == 0 and "filter=lfs" in lfs.stdout
        if out["uses_lfs"]:
            f = _git(["-C", str(path), "lfs", "fetch", "--all"])
            out["lfs_fetch_ok"] = f.returncode == 0
    return out


# ------------------------------------------------------------------ metadata

def export_meta(gh: GitHub, repo: str, meta: Path, max_run_pages: int = MAX_RUN_PAGES) -> list[dict]:
    report: list[dict] = []

    def record(item: str, status: int, data: Any, count: int | None = None, capped: bool = False,
               note: str | None = None):
        row = {"item": item, "status": status}
        if status == 200:
            row["count"] = count
            if capped:
                row["capped"] = True
        else:
            row["message"] = _message(data)
        if note:
            row["note"] = note
        report.append(row)
        return row

    saved: dict[str, Any] = {}
    for name, tmpl, is_list in ITEMS:
        path = tmpl.format(r=repo)
        if is_list:
            pages = max_run_pages if name == "workflow_runs" else MAX_PAGES
            status, data, capped = gh.paginate(path, WRAPPED.get(name), max_pages=pages)
            count = len(data) if status == 200 else None
            note = f"most recent {len(data)} runs" if name == "workflow_runs" else None
        else:
            status, data = gh.get(path)
            capped = False
            count = 1 if status == 200 else None
            note = None
        record(name, status, data, count, capped, note)
        if status == 200:
            _write(meta / f"{name}.json", data)
            saved[name] = data

    # Reviews are per pull request. Re-fetch only PRs updated since last export.
    pulls = saved.get("pulls") or []
    reviews_path = meta / "pull_reviews.json"
    old: dict[str, Any] = {}
    if reviews_path.exists():
        with open(reviews_path, encoding="utf-8") as fh:
            old = json.load(fh)
    reviews: dict[str, Any] = {}
    fetched = refused = 0
    first_refusal = None
    for pr in pulls:
        key = str(pr["number"])
        prev = old.get(key)
        if prev and prev.get("updated_at") == pr.get("updated_at"):
            reviews[key] = prev
            continue
        status, data, _ = gh.paginate(f"/repos/{repo}/pulls/{pr['number']}/reviews")
        if status == 200:
            reviews[key] = {"updated_at": pr.get("updated_at"), "reviews": data}
            fetched += 1
        else:
            refused += 1
            first_refusal = first_refusal or (status, _message(data))
    _write(reviews_path, reviews)
    row = record("pull_reviews", 200 if not refused else (first_refusal or (0,))[0], {},
                 sum(len(v["reviews"]) for v in reviews.values()),
                 note=f"{len(reviews)} PRs, {fetched} fetched this run, {refused} refused")
    if refused:
        row["message"] = first_refusal[1]

    # Branch protection for each protected branch.
    prot: dict[str, Any] = {}
    for b in saved.get("branches") or []:
        if not b.get("protected"):
            continue
        status, data = gh.get(f"/repos/{repo}/branches/{urllib.parse.quote(b['name'], safe='')}/protection")
        prot[b["name"]] = {"status": status, "protection": data if status == 200 else None,
                           "message": None if status == 200 else _message(data)}
    if prot:
        _write(meta / "branch_protection.json", prot)
        ok = sum(v["status"] == 200 for v in prot.values())
        bad = [v for v in prot.values() if v["status"] != 200]
        r = record("branch_protection", 200 if not bad else bad[0]["status"], {}, ok,
                   note=f"{len(prot)} protected branch(es)")
        if bad:
            r["message"] = bad[0]["message"]
    else:
        record("branch_protection", 200, {}, 0, note="no protected branches")

    # Each ruleset in full.
    rules = []
    for rs in saved.get("rulesets") or []:
        status, data = gh.get(f"/repos/{repo}/rulesets/{rs['id']}")
        rules.append({"id": rs["id"], "status": status, "ruleset": data})
    if saved.get("rulesets") is not None:
        _write(meta / "rulesets_detail.json", rules)

    # Environments: secret and variable names per environment.
    env_detail = {}
    for env in saved.get("environments") or []:
        name = urllib.parse.quote(env["name"], safe="")
        s1, sec, _ = gh.paginate(f"/repos/{repo}/environments/{name}/secrets", "secrets")
        s2, var, _ = gh.paginate(f"/repos/{repo}/environments/{name}/variables", "variables")
        env_detail[env["name"]] = {"secrets_status": s1, "secret_names": [s["name"] for s in sec]
                                   if s1 == 200 else None, "secrets_message": None if s1 == 200 else _message(sec),
                                   "variables_status": s2, "variables": var if s2 == 200 else None,
                                   "variables_message": None if s2 == 200 else _message(var)}
    if env_detail:
        _write(meta / "environment_secrets_and_variables.json", env_detail)
        r = record("environment_secrets_and_variables", 200, {}, len(env_detail))
        refusals = [(k, v) for k, v in env_detail.items()
                    if v["secrets_status"] != 200 or v["variables_status"] != 200]
        if refusals:
            k, v = refusals[0]
            r["status"] = v["secrets_status"] if v["secrets_status"] != 200 else v["variables_status"]
            r["message"] = f"{k}: {v['secrets_message'] or v['variables_message']}"

    # Release assets.
    got = failed = unchanged = 0
    for rel in saved.get("releases") or []:
        tag = re.sub(r'[<>:"/\\|?*]', "_", rel.get("tag_name") or str(rel["id"]))
        for asset in rel.get("assets") or []:
            dest = meta / "release_assets" / tag / re.sub(r'[<>:"/\\|?*]', "_", asset["name"])
            if dest.exists() and dest.stat().st_size == asset.get("size"):
                unchanged += 1
                continue
            status = gh.download(asset["url"], dest)
            if status == 200:
                got += 1
            else:
                failed += 1
    record("release_assets", 200 if not failed else 0, {}, got + unchanged,
           note=f"{got} downloaded, {unchanged} unchanged, {failed} failed")

    _write(meta / "_export_report.json", {"repo": repo, "at": _iso(), "items": report})
    return report


def discover(gh: GitHub, owners: tuple[str, ...]) -> list[dict]:
    found: dict[str, dict] = {}
    status, mine, _ = gh.paginate("/user/repos?affiliation=owner,collaborator,organization_member")
    if status == 200:
        for r in mine:
            if r["owner"]["login"].lower() in {o.lower() for o in owners}:
                found[r["full_name"]] = r
    for owner in owners:
        status, theirs, _ = gh.paginate(f"/users/{owner}/repos?type=owner")
        if status == 200:
            for r in theirs:
                found.setdefault(r["full_name"], r)
    return sorted(found.values(), key=lambda r: r["full_name"].lower())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dest", default=str(DEFAULT_DEST))
    ap.add_argument("--repo", action="append", help="owner/name; default: every reachable repo")
    ap.add_argument("--owners", default=",".join(OWNERS))
    ap.add_argument("--skip-meta", action="store_true")
    ap.add_argument("--max-run-pages", type=int, default=MAX_RUN_PAGES)
    args = ap.parse_args(argv)
    dest = Path(args.dest)
    gh = GitHub(gh_token())
    repos = discover(gh, tuple(o.strip() for o in args.owners.split(",") if o.strip()))
    if args.repo:
        wanted = {r.lower() for r in args.repo}
        repos = [r for r in repos if r["full_name"].lower() in wanted]
    log(f"{len(repos)} repos: {', '.join(r['full_name'] for r in repos)}")
    summary = []
    for r in repos:
        full = r["full_name"]
        owner, name = full.split("/", 1)
        base = dest / owner
        row: dict[str, Any] = {"repo": full, "private": r.get("private")}
        try:
            row["git"] = mirror_git(f"https://github.com/{full}.git", base / f"{name}.git")
            log(f"{full}: git {row['git']}")
            if r.get("has_wiki"):
                ls = _git(["ls-remote", f"https://github.com/{full}.wiki.git"], timeout=120)
                if ls.returncode == 0:
                    row["wiki"] = mirror_git(f"https://github.com/{full}.wiki.git", base / f"{name}.wiki.git")
                else:
                    row["wiki"] = {"ok": False, "note": "wiki enabled but no wiki repository exists "
                                                        "(no page was ever created)",
                                   "stderr_tail": (ls.stderr or "").strip().splitlines()[-2:]}
            else:
                row["wiki"] = {"ok": False, "note": "wiki disabled on this repo"}
            log(f"{full}: wiki {row['wiki']}")
            if not args.skip_meta:
                rep = export_meta(gh, full, base / f"{name}.meta", args.max_run_pages)
                row["meta"] = rep
                for it in rep:
                    if it["status"] != 200:
                        log(f"{full}: REFUSED {it['item']} -> HTTP {it['status']} {it.get('message', '')}")
                ok = [f"{it['item']}={it.get('count')}" for it in rep if it["status"] == 200]
                log(f"{full}: exported {', '.join(ok)}")
        except Exception as exc:  # noqa: BLE001
            row["error"] = repr(exc)[:300]
            log(f"{full}: FAILED {exc!r}\n{traceback.format_exc()}")
        summary.append(row)
    _write(dest / "_mirror_summary.json", {"at": _iso(), "api_calls": gh.calls, "repos": summary})
    log(f"done: {len(summary)} repos, {gh.calls} API calls")
    return 1 if any(s.get("error") or not s.get("git", {}).get("ok") for s in summary) else 0


if __name__ == "__main__":
    sys.exit(main())
