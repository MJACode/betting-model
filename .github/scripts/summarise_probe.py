"""Print the shape of a monitor API response, for the probe workflow's log.

DELIBERATELY GENERIC over the ops panels. The first version hardcoded the
panel names it expected ("roster", "performance") and printed `0 rows` for
every one of them -- the payload's real keys are "models" and "perf", and a
later session had added "cal" and "livecal" that the list could not see at
all. A hardcoded list does not fail when the payload moves, it silently
under-reports, which is the one thing a monitoring probe must never do.

So: iterate whatever panels are actually there, and name any that are new.

Prints COUNTS and small scalars only, never pick rows or anything that could
carry a credential: this output lands in an Actions log.
"""
import json
import sys

path, fn = sys.argv[1], sys.argv[2]
d = json.load(open(fn))
print(f"  {path} top-level keys: {sorted(d)}")

ops = d.get("ops") or {}
if not ops:
    sys.exit(0)

panels = sorted(k for k in ops if k != "ages")
print(f"  ops panels ({len(panels)}): {panels}")

for name in panels:
    v = ops[name]
    if isinstance(v, list):
        print(f"    {name}: {len(v)} rows")
    elif isinstance(v, dict):
        # Small scalar dicts (community, discord) are worth printing whole;
        # anything larger just gets its shape.
        if len(v) <= 12 and all(not isinstance(x, (list, dict)) for x in v.values()):
            print(f"    {name}: {v}")
        else:
            print(f"    {name}: dict with keys {sorted(v)}")
    else:
        print(f"    {name}: {v!r}")

ages = ops.get("ages") or {}
if ages:
    print("  cache ages (s): "
          + ", ".join(f"{k}={0 if a is None else round(a, 1)}"
                      for k, a in sorted(ages.items())))
    stale = [k for k, a in ages.items() if a is None]
    if stale:
        print(f"  ::warning::panels never computed: {sorted(stale)}")

# The roster is the one panel whose CONTENT is a health signal rather than
# just a row count: a model registered with no trained artifact silently
# stops scoring (CLAUDE.md section 7).
roster = ops.get("models") or []
if roster:
    live = sum(1 for r in roster if not r.get("paused"))
    no_art = sum(1 for r in roster if not r.get("version"))
    print(f"  roster: {live} live, {len(roster) - live} paused, "
          f"{no_art} without a trained artifact")
