"""Polite JSON reads. Personal, non-commercial.

The caller pauses between calls. This retries a dropped connection, a 429
and a 5xx. A 404 is not retried: the resource is not there.
"""
from __future__ import annotations

import random
import time

import requests

USER_AGENT = "BettingModel/1.0 (personal non-commercial research)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
HTTP_TIMEOUT = 45
MAX_ATTEMPTS = 4


class FetchFailed(Exception):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def get_json(url: str, session: requests.Session | None = None,
             headers: dict | None = None) -> dict:
    """One URL. Raises FetchFailed when it does not return a JSON object."""
    own = session is None
    sess = session or requests.Session()
    last = "no attempt"
    status = None
    try:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                resp = sess.get(url, headers=headers or HEADERS, timeout=HTTP_TIMEOUT)
                status = resp.status_code
                if status == 200:
                    body = resp.json()
                    if not isinstance(body, dict):
                        raise FetchFailed(f"not an object: {url}", status=status)
                    return body
                last = f"HTTP {status}"
                if status == 404 or (400 <= status < 500 and status != 429):
                    raise FetchFailed(last, status=status)
            except FetchFailed:
                raise
            except (requests.RequestException, ValueError) as exc:
                last = f"{type(exc).__name__}: {str(exc)[:160]}"
                status = None
            if attempt < MAX_ATTEMPTS:
                time.sleep(min(2 ** attempt, 20) + random.uniform(0, 0.4))
        raise FetchFailed(f"{MAX_ATTEMPTS} attempts, last: {last}", status=status)
    finally:
        if own:
            sess.close()
