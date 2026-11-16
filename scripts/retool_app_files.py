"""Keep the repo copy of the Retool ops dashboard and the live Retool app in step.

The dashboard ("Betting Model — Models & Ops",
https://signalbaseskinny--betting-model-models-ops.retool.app) is a Retool
React app. Its source lives in `retool/models-ops/`; `retool/README.md` says
which copy takes effect and how an edit made here reaches Retool.

Retool's own GitHub sync ("Source Control", "Protect app") needs the
Enterprise plan; this account is on Team, so there is no automatic sync in
either direction. The two directions are:

  Retool -> repo   A Claude session reads every file with the Retool MCP tool
                   `retool_read_react_app_files` (large results are saved to a
                   JSON file), then:
                       python -m scripts.retool_app_files write DUMP.json ...
  repo -> Retool   A Claude session sends the change to the app through a
                   Retool thread and publishes it, then reads the files back
                   and proves they match:
                       python -m scripts.retool_app_files check DUMP.json ...

A DUMP is the JSON the MCP tool returns:
    {"files": [{"path": "/frontend/App.tsx", "content": "...",
                "sizeBytes": 6463, "truncated": false}, ...]}

Files are written and compared as raw UTF-8 bytes with the line endings left
exactly as Retool has them (LF); `.gitattributes` keeps `retool/**` LF on
checkout so the comparison stays byte-for-byte on Windows.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT / "retool" / "models-ops"

# Not exported: the read tool truncates any file over 64 KB, and pnpm
# regenerates the lockfile from the package.json files.
NOT_EXPORTED = {"/pnpm-lock.yaml"}


@dataclass
class DumpFile:
    path: str          # Retool path, leading slash: "/frontend/App.tsx"
    content: str
    size_bytes: int
    truncated: bool

    @property
    def data(self) -> bytes:
        return self.content.encode("utf-8")


@dataclass
class Report:
    written: list[str] = field(default_factory=list)
    match: list[str] = field(default_factory=list)
    differs: list[str] = field(default_factory=list)
    missing_in_repo: list[str] = field(default_factory=list)
    only_in_repo: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def load_dumps(paths: list[Path]) -> list[DumpFile]:
    """Every file across one or more MCP read results, refusing duplicates."""
    out: dict[str, DumpFile] = {}
    for p in paths:
        doc = json.loads(p.read_text(encoding="utf-8"))
        for f in doc["files"]:
            if f["path"] in out:
                raise ValueError(f"{f['path']} appears in more than one dump")
            out[f["path"]] = DumpFile(
                path=f["path"],
                content=f["content"],
                size_bytes=int(f["sizeBytes"]),
                truncated=bool(f.get("truncated")),
            )
    return [out[k] for k in sorted(out)]


def _local(dest: Path, retool_path: str) -> Path:
    rel = retool_path.lstrip("/")
    target = (dest / rel).resolve()
    if dest.resolve() not in target.parents:
        raise ValueError(f"{retool_path} would land outside {dest}")
    return target


def _usable(f: DumpFile, report: Report) -> bool:
    if f.path in NOT_EXPORTED:
        report.skipped.append(f"{f.path} (not exported: lockfile)")
        return False
    if f.truncated:
        report.skipped.append(f"{f.path} (truncated by the read tool)")
        return False
    if len(f.data) != f.size_bytes:
        report.errors.append(
            f"{f.path}: content is {len(f.data)} bytes, Retool says {f.size_bytes}")
        return False
    return True


def write(files: list[DumpFile], dest: Path) -> Report:
    """Write each file byte-for-byte, then read it back and check it."""
    report = Report()
    for f in files:
        if not _usable(f, report):
            continue
        target = _local(dest, f.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(f.data)
        if target.read_bytes() != f.data:
            report.errors.append(f"{f.path}: read-back differs from what was written")
        else:
            report.written.append(f.path)
    return report


def check(files: list[DumpFile], dest: Path) -> Report:
    """Compare the repo copy with Retool, byte for byte, in both directions."""
    report = Report()
    seen: set[str] = set()
    for f in files:
        seen.add(f.path)
        if not _usable(f, report):
            continue
        target = _local(dest, f.path)
        if not target.exists():
            report.missing_in_repo.append(f.path)
        elif target.read_bytes() == f.data:
            report.match.append(f.path)
        else:
            report.differs.append(f.path)
    if dest.exists():
        for p in sorted(dest.rglob("*")):
            if p.is_file():
                rp = "/" + p.relative_to(dest).as_posix()
                if rp not in seen:
                    report.only_in_repo.append(rp)
    return report


def _print(report: Report) -> None:
    for name in ("written", "match", "differs", "missing_in_repo",
                 "only_in_repo", "skipped", "errors"):
        items = getattr(report, name)
        print(f"{name}: {len(items)}")
        if name not in ("written", "match"):
            for item in items:
                print(f"  {item}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["write", "check"])
    ap.add_argument("dumps", nargs="+", type=Path)
    ap.add_argument("--dest", type=Path, default=DEFAULT_DEST)
    args = ap.parse_args(argv)

    files = load_dumps(args.dumps)
    report = write(files, args.dest) if args.command == "write" else check(files, args.dest)
    _print(report)
    bad = report.errors or report.differs or report.missing_in_repo or report.only_in_repo
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
