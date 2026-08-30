"""Print the shape of a monitor API response, for the probe workflow's log.

Deliberately prints COUNTS and small scalars only, never pick rows or
anything that could carry a credential: this output lands in a public
Actions log.
"""
import json
import sys

path, fn = sys.argv[1], sys.argv[2]
d = json.load(open(fn))
print(f"  {path} top-level keys: {sorted(d)}")

ops = d.get("ops") or {}
if ops:
    print(f"  ops panels: {sorted(k for k in ops if k != 'ages')}")
    print(f"  roster rows: {len(ops.get('roster') or [])}")
    print(f"  performance rows: {len(ops.get('performance') or [])}")
    print(f"  series rows: {len(ops.get('series') or [])}")
    comm = ops.get("community") or {}
    print(f"  community: {ops.get('community')}")
    disc = ops.get("discord") or {}
    # A reason string is safe (it names a missing VARIABLE, never a value).
    print(f"  discord configured={disc.get('configured')} "
          f"members={disc.get('members')} reason={disc.get('reason')}")
    print(f"  cache ages (s): {ops.get('ages')}")
    roster = ops.get("roster") or []
    if roster:
        live = sum(1 for r in roster if not r.get("paused"))
        art = sum(1 for r in roster if r.get("version"))
        print(f"  roster: {live} live, {len(roster) - live} paused, "
              f"{len(roster) - art} without an artifact")
