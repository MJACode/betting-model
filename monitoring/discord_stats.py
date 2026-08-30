"""Discord community size — guild member and presence counts.

THE CONSTRAINT, STATED PLAINLY: an incoming webhook cannot read this. A webhook
is a write-only URL; it has no permission to see who is in the server. The only
way to a member count is a BOT TOKEN calling
`GET /guilds/{id}?with_counts=true`, which returns approximate_member_count and
approximate_presence_count (online now).

So this module is inert until two variables are set, and says so rather than
inventing a number:

  DISCORD_BOT_TOKEN   a bot token from https://discord.com/developers
  DISCORD_GUILD_ID    the server id (Developer Mode -> right-click server -> Copy ID)

The bot needs no privileged intents and no channel permissions for this call —
it only has to be a member of the guild. See docs/monitoring.md.

Cached hard (10 min) and never blocking: Discord rate-limits per bot, and a
community count that is ten minutes old is not a worse number.
"""

from __future__ import annotations

import os

import requests

API = "https://discord.com/api/v10"
TIMEOUT = 8


def configured() -> bool:
    return bool(os.environ.get("DISCORD_BOT_TOKEN")
                and os.environ.get("DISCORD_GUILD_ID"))


def guild_stats() -> dict:
    """{members, online, name} — or a `reason` explaining what is missing.

    Never raises: this is one panel on a dashboard, not a pipeline step.
    """
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    guild = os.environ.get("DISCORD_GUILD_ID", "").strip()
    if not token or not guild:
        missing = [n for n, v in (("DISCORD_BOT_TOKEN", token),
                                  ("DISCORD_GUILD_ID", guild)) if not v]
        return {"configured": False,
                "reason": f"not configured — set {' and '.join(missing)}. "
                          f"Webhooks are write-only and cannot read a member count."}
    try:
        r = requests.get(f"{API}/guilds/{guild}",
                         params={"with_counts": "true"},
                         headers={"Authorization": f"Bot {token}"},
                         timeout=TIMEOUT)
        if r.status_code == 401:
            return {"configured": True, "reason": "Discord rejected the bot token (401)"}
        if r.status_code == 403:
            return {"configured": True,
                    "reason": "the bot is not a member of that guild (403)"}
        if r.status_code == 404:
            return {"configured": True, "reason": "no guild with that id (404)"}
        if r.status_code == 429:
            return {"configured": True, "reason": "rate-limited by Discord (429)"}
        r.raise_for_status()
        d = r.json()
        return {
            "configured": True,
            "name":    d.get("name"),
            "members": d.get("approximate_member_count"),
            "online":  d.get("approximate_presence_count"),
        }
    except Exception as exc:
        return {"configured": True, "reason": f"{type(exc).__name__}: {exc}"[:160]}
