"""Create a sport's Discord channel as a copy of another sport's: one-off.

Made for NCAAB (2026-10-30): the NCAAB totals model went live with no #ncaab
channel. This clones the #ncaaf channel's place and access, so exactly the
members who can see #ncaaf can see #ncaab:

  * the same category (parent_id),
  * the position right after it,
  * the same permission overwrites, role by role and member by member,
  * the same slow mode and age flag. Not the topic: #ncaaf's would describe
    football.

It prints the new channel's id, which goes into DISCORD_CHANNEL_NCAAB on the
worker. The worker runs the NCAAB totals card and holds DISCORD_BOT_TOKEN; the
pollers have no bot token, so a channel id there resolves nothing. The notifier
makes the channel's webhook itself through the bot token
(tracking/discord_notifier._channel_webhook). A channel id is not a secret;
the token and any webhook URL are, and this script prints neither.

    python -m scripts.discord_create_sport_channel --name ncaab --like ncaaf --dry-run
    python -m scripts.discord_create_sport_channel --name ncaab --like ncaaf

Needs DISCORD_BOT_TOKEN, and the bot needs Manage Channels in the guild (and,
to copy an overwrite, the permissions that overwrite grants). It refuses when a
channel with the new name already exists, and prints that one's id instead.
When the bot is in more than one guild, pass --guild.
"""
from __future__ import annotations

import argparse
import os
import sys

import requests

API = "https://discord.com/api/v10"
TEXT = 0
# Not "topic": the source sport's topic would describe the new channel wrongly.
COPIED = ("nsfw", "rate_limit_per_user")


def find_channel(channels: list[dict], name: str) -> dict | None:
    """The text channel called exactly `name`, else None."""
    for c in channels:
        if c.get("name") == name and c.get("type", TEXT) == TEXT:
            return c
    return None


def create_body(src: dict, name: str) -> dict:
    """The POST body for a channel placed and permissioned like `src`."""
    body = {"name": name, "type": TEXT,
            "parent_id": src.get("parent_id"),
            "position": int(src.get("position") or 0) + 1,
            "permission_overwrites": [
                {"id": o["id"], "type": o["type"], "allow": o.get("allow", "0"),
                 "deny": o.get("deny", "0")}
                for o in src.get("permission_overwrites") or []]}
    for k in COPIED:
        if src.get(k) is not None:
            body[k] = src[k]
    return body


def _get(path: str, headers: dict):
    r = requests.get(f"{API}{path}", headers=headers, timeout=20)
    print(f"GET {path.split('?')[0]} -> {r.status_code}")
    if r.status_code != 200:
        sys.exit(f"Discord refused {path}: {r.status_code}")
    return r.json()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--name", default="ncaab")
    ap.add_argument("--like", default="ncaaf")
    ap.add_argument("--guild", default=None, help="guild id; needed when the bot is in several")
    ap.add_argument("--dry-run", action="store_true", help="print the body, create nothing")
    a = ap.parse_args(argv)
    token = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        sys.exit("DISCORD_BOT_TOKEN is not set")
    headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
    guild = a.guild
    if guild is None:
        guilds = _get("/users/@me/guilds", headers)
        if len(guilds) != 1:
            sys.exit(f"the bot is in {len(guilds)} guilds; pass --guild "
                     f"({', '.join(g['id'] + ' ' + g.get('name', '') for g in guilds)})")
        guild = guilds[0]["id"]
    channels = _get(f"/guilds/{guild}/channels", headers)
    there = find_channel(channels, a.name)
    if there is not None:
        print(f"#{a.name} already exists: {there['id']}")
        return
    src = find_channel(channels, a.like)
    if src is None:
        sys.exit(f"no #{a.like} channel in guild {guild}")
    body = create_body(src, a.name)
    print(f"cloning #{a.like} ({src['id']}): category {body['parent_id']}, position "
          f"{body['position']}, {len(body['permission_overwrites'])} permission overwrite(s)")
    if a.dry_run:
        print(body)
        return
    r = requests.post(f"{API}/guilds/{guild}/channels", headers=headers, json=body, timeout=20)
    print(f"POST /guilds/{guild}/channels -> {r.status_code}")
    if r.status_code not in (200, 201):
        sys.exit(f"Discord refused the new channel: {r.status_code} {r.text[:300]}")
    made = r.json()
    print(f"created #{made.get('name')}: {made['id']}")
    print(f"set DISCORD_CHANNEL_{a.name.upper()}={made['id']} on the worker, where the bot "
          f"token is, then redeploy it")


if __name__ == "__main__":
    main()
