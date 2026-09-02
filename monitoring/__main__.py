"""Local viewer:  python -m monitoring [--port 8787] [--host 127.0.0.1]

Reads the same Supabase the worker writes to, so it shows live traffic from the
worker as well as anything you run yourself. Loopback-only unless you set
MONITOR_TOKEN (see server.build_server).
"""

import argparse
import os
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from monitoring.server import build_server  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Signalbase pipeline monitor")
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("MONITOR_PORT", "8787")))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-open", action="store_true",
                    help="don't open a browser window")
    args = ap.parse_args()

    if not os.environ.get("DATABASE_URL"):
        print("DATABASE_URL is not set — the monitor reads Supabase directly.\n"
              "Add it to .env (same value the pipeline uses).", file=sys.stderr)
        return 1

    token = os.environ.get("MONITOR_TOKEN") or None
    srv = build_server(args.host, args.port, token)
    url = f"http://{args.host}:{args.port}/" + (f"?token={token}" if token else "")
    print(f"Signalbase monitor → {url}   (ctrl-c to stop)")
    if not args.no_open:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
