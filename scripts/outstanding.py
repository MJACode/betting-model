"""Everything still open in this repo: unmerged work and tracked outstanding tasks.

    python -m scripts.outstanding                 # the full list
    python -m scripts.outstanding --no-fetch      # skip `git fetch` (branch list may be stale)
    python -m scripts.outstanding --session-start # a short summary for the SessionStart hook

The tracker is GitHub itself, because it sits outside every branch: a list kept
in a file on one branch is invisible from the others. (mike, 2026-11-13: "How
can we track all outstanding tasks, things that haven't been merged?")

  * an OPEN PULL REQUEST is unmerged work;
  * a PUSHED BRANCH WITH NO PULL REQUEST is unmerged work nobody can see on
    GitHub's list, so it is listed here too;
  * everything else that outlives a session is an ISSUE labelled `outstanding`,
    opened the same turn it is found (`~/.claude/CLAUDE.md` §6), with the time
    it can be checked, and closed when it is done.

Read-only: it runs `gh` and `git` queries and changes nothing. Standard library
only, so the hook can run it from any checkout. The session-start mode never
fetches and fails open: any error prints nothing.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

LABEL = "outstanding"
RECENT_DAYS = 30
RULE = "Rule: CLAUDE.md, TEST IT NOW; each Outstanding tasks line carries its issue or PR number."


def _run(args, timeout=30):
    out = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                         encoding="utf-8", errors="replace")
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(args[:3])}: {out.stderr.strip()[:200]}")
    return out.stdout


def repo_slug(remote_url: str) -> str:
    """owner/name from an https or ssh GitHub remote URL."""
    tail = remote_url.strip().rstrip("/")
    if tail.endswith(".git"):
        tail = tail[:-4]
    tail = tail.replace(":", "/")
    parts = [p for p in tail.split("/") if p]
    return "/".join(parts[-2:])


def _days(iso: str, now: dt.datetime) -> int:
    when = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return max(0, (now - when).days)


# A time-of-day gate, not a test of the code: `.github/workflows/daily-merge-gate.yml`
# posts it red during the 6am ET daily and it stays red until its next scheduled
# tick, which GitHub runs far less often than its cron asks. Reported apart.
TIME_GATES = {"daily pipeline not running"}


def checks_state(rollup) -> str:
    states = set()
    for c in rollup or []:
        if (c.get("name") or c.get("context") or "") in TIME_GATES:
            continue
        s = (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
        if s:
            states.add(s)
    if not states:
        return "no checks"
    if states & {"FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"}:
        return "checks failing"
    if states & {"PENDING", "IN_PROGRESS", "QUEUED", "EXPECTED", "WAITING"}:
        return "checks running"
    return "checks pass"


def branches_without_pr(refs_text: str, pr_heads: set[str], now: dt.datetime):
    """Parse `git for-each-ref` lines: (branch, days since last commit, subject).

    `pr_heads` holds every branch that has an open or a MERGED pull request:
    those are tracked or done. A squash merge leaves the branch looking
    unmerged to git, so the pull request's state is what counts.
    """
    out = []
    for line in refs_text.splitlines():
        parts = line.split("\t", 2)
        if len(parts) < 2:
            continue
        ref, when = parts[0], parts[1]
        subject = parts[2] if len(parts) > 2 else ""
        name = ref.split("/", 1)[1] if ref.startswith("origin/") else ref
        if name in ("HEAD", "master", "main") or ref == "origin" or name in pr_heads:
            continue
        out.append((name, _days(when, now), subject))
    return sorted(out, key=lambda r: r[1])


def split_by_pr_state(all_prs):
    """Branch names with a merged pull request, and those whose only pull requests were closed."""
    merged, closed = set(), set()
    for p in all_prs:
        (merged if p.get("state") == "MERGED" else closed if p.get("state") == "CLOSED" else set()).add(
            p.get("headRefName", ""))
    return merged, closed - merged


def gather(fetch: bool, repo: str | None = None, history: int = 2000):
    now = dt.datetime.now(dt.timezone.utc)
    repo = repo or repo_slug(_run(["git", "remote", "get-url", "origin"]))
    prs = json.loads(_run(["gh", "pr", "list", "--repo", repo, "--state", "open", "--limit", "300",
                           "--json", "number,title,headRefName,createdAt,isDraft,author,statusCheckRollup"]))
    past = json.loads(_run(["gh", "pr", "list", "--repo", repo, "--state", "all", "--limit", str(history),
                            "--json", "headRefName,state"], timeout=60))
    merged, closed = split_by_pr_state(past)
    issues = json.loads(_run(["gh", "issue", "list", "--repo", repo, "--state", "open", "--label", LABEL,
                              "--limit", "300", "--json", "number,title,createdAt"]))
    if fetch:
        _run(["git", "fetch", "-q", "--prune", "origin"], timeout=120)
    refs = _run(["git", "for-each-ref", "refs/remotes/origin", "--no-merged", "origin/master",
                 "--format=%(refname:short)%09%(committerdate:iso-strict)%09%(subject)"])
    rows = branches_without_pr(refs, {p["headRefName"] for p in prs} | merged, now)
    branches = [r for r in rows if r[0] not in closed]
    closed_rows = [r for r in rows if r[0] in closed]
    return now, repo, prs, issues, branches, closed_rows


def report(now, repo, prs, issues, branches, closed_rows) -> str:
    lines = [f"OPEN WORK in {repo}, {now:%Y-%m-%d %H:%M} UTC", ""]
    lines.append(f"Pull requests not merged: {len(prs)}")
    for p in sorted(prs, key=lambda p: p["createdAt"]):
        who = (p.get("author") or {}).get("login", "?")
        draft = " draft," if p.get("isDraft") else ""
        lines.append(f"  #{p['number']}  {_days(p['createdAt'], now):>3}d old,{draft} {checks_state(p.get('statusCheckRollup'))}, "
                     f"{who}: {p['title'][:90]}")
    recent = [b for b in branches if b[1] <= RECENT_DAYS]
    lines += ["", f"Pushed branches with no pull request, last {RECENT_DAYS} days: {len(recent)}"
                  f" (older: {len(branches) - len(recent)})"]
    for name, days, subject in recent:
        lines.append(f"  {name}  {days}d since its last commit: {subject[:80]}")
    recent_closed = [b for b in closed_rows if b[1] <= RECENT_DAYS]
    lines += ["", f"Branches whose pull request was closed without merging, last {RECENT_DAYS} days: "
                  f"{len(recent_closed)}"]
    for name, days, subject in recent_closed:
        lines.append(f"  {name}  {days}d: {subject[:80]}")
    lines += ["", f"Issues labelled '{LABEL}': {len(issues)}"]
    for i in sorted(issues, key=lambda i: i["createdAt"]):
        lines.append(f"  #{i['number']}  {_days(i['createdAt'], now):>3}d old: {i['title'][:100]}")
    return "\n".join(lines)


def session_summary(now, repo, prs, issues, branches, closed_rows=()) -> str:
    oldest_pr = min(prs, key=lambda p: p["createdAt"]) if prs else None
    oldest_issue = min(issues, key=lambda i: i["createdAt"]) if issues else None
    recent = [b for b in branches if b[1] <= RECENT_DAYS]
    parts = [f"OPEN WORK (python -m scripts.outstanding lists it): {len(prs)} pull requests not merged"]
    if oldest_pr:
        parts[-1] += f", oldest #{oldest_pr['number']} ({_days(oldest_pr['createdAt'], now)}d)"
    parts.append(f"{len(recent)} pushed branches with no pull request in the last {RECENT_DAYS} days")
    issue_part = f"{len(issues)} issues labelled {LABEL}"
    if oldest_issue:
        issue_part += f", oldest #{oldest_issue['number']} ({_days(oldest_issue['createdAt'], now)}d)"
    parts.append(issue_part)
    return "; ".join(parts) + ". " + RULE


def cache_path() -> str:
    return os.path.join(tempfile.gettempdir(), "betting-model-outstanding.json")


def write_cache(gathered, path=None) -> None:
    now, repo, prs, issues, branches, closed_rows = gathered
    with open(path or cache_path(), "w", encoding="utf-8") as fh:
        json.dump({"at": now.isoformat(), "summary": session_summary(*gathered)}, fh)


def read_cache(path=None, max_age_hours=24, now=None):
    """The cached summary and its age in minutes, or None if absent, unreadable or too old."""
    now = now or dt.datetime.now(dt.timezone.utc)
    try:
        with open(path or cache_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        age = now - dt.datetime.fromisoformat(data["at"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if age > dt.timedelta(hours=max_age_hours):
        return None
    return data["summary"], int(age.total_seconds() // 60)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--no-fetch", action="store_true", help="do not run git fetch first")
    ap.add_argument("--session-start", action="store_true",
                    help="hook output: the cached summary as JSON (computed once if there is no cache)")
    ap.add_argument("--refresh-cache", action="store_true",
                    help="recompute the summary into the cache (the background SessionStart hook)")
    args = ap.parse_args(argv)
    if args.session_start:
        try:  # fail open: a session must always start
            cached = read_cache()
            if cached:
                text = f"{cached[0]} (as of {cached[1]} min ago)"
            else:
                gathered = gather(fetch=False, history=400)
                write_cache(gathered)
                text = session_summary(*gathered)
        except Exception:
            return 0
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": text}}))
        return 0
    if args.refresh_cache:
        try:
            write_cache(gather(fetch=False))
        except Exception:
            return 0
        return 0
    gathered = gather(fetch=not args.no_fetch)
    write_cache(gathered)
    print(report(*gathered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
