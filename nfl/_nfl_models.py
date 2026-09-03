"""Import a module from nfl/models/ unambiguously, whatever sys.path says.

WHY THIS EXISTS, AND WHY `sys.path.insert` IS NOT ENOUGH

A bare `from models.wind_totals import ...` is not safe from anywhere in this
package. The platform repo has its own top-level `models` package WITH an
`__init__.py`; `nfl/models/` has none, so it is a PEP 420 namespace portion.
When both roots are on sys.path, Python's finder records the namespace portion
and KEEPS LOOKING -- and a regular package found later wins over a namespace
portion **regardless of path order**. So even after

    sys.path.insert(0, <nfl root>)

puts nfl/ first, `import models` still resolves to the platform's package, and
`models.wind_totals` raises ModuleNotFoundError rather than falling back.

That is not hypothetical. `scripts/weekly_wind_card.py` did exactly this and
failed on EVERY scheduled run -- reproduced from the production invocation
(cwd=nfl/, PYTHONPATH=<repo root>, which scheduler.py sets so these children can
`import monitoring`), and seen hourly in the Railway deploy log:

    from models.wind_totals import select_bets, UNIT_PCT, MAX_CALIBRATED_LEAD
    ModuleNotFoundError: No module named 'models.wind_totals'

`scripts/nfl_preflight.py` carried a comment asserting the production cards were
safe "because the scheduler runs them with cwd=nfl/". **cwd is not sys.path**:
for `python scripts/foo.py`, sys.path[0] is the SCRIPT's directory, and cwd
never enters into it. The card had been broken since that reasoning was written.

Loading by absolute path is unambiguous no matter what is on sys.path, and is
what tests/test_nfl_opener.py already does. `scripts/daily_opener_card.py`
worked out this same fix independently; this module is that implementation,
lifted so there is one copy rather than one per script.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_MODELS = Path(__file__).resolve().parent / "models"


def load_nfl_model(name: str):
    """Return nfl/models/<name>.py as a module, bypassing sys.path entirely."""
    path = _MODELS / f"{name}.py"
    mod_name = f"nfl_model_{name}"
    cached = sys.modules.get(mod_name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:          # pragma: no cover — unreachable
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # Register BEFORE exec: a module using @dataclass under
    # `from __future__ import annotations` resolves its annotations through
    # sys.modules[cls.__module__] and raises without this.
    sys.modules[mod_name] = mod
    spec.loader.exec_module(mod)
    return mod
