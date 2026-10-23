"""The Slack part of `sympose doctor` (docs/decisions/093, 029): what is missing before `sympose slack` can put a persona in
Slack, and which personas are connected right now. Nothing here reads a token's value, and nothing is fixed for the person:
a token or an owner ID is theirs to put in `.env`. Silent for an installation that has not touched Slack."""

import os
import re

from sympose import profile, slack_approval, slack_credentials, slack_heartbeat

_TOKEN = re.compile(r"^SLACK_(.+)_(BOT|APP)_TOKEN$")


def _set(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def _named_in_env() -> dict[str, set[str]]:
    """The token variables set in the environment: the persona part of each name, with which of the two are there."""
    found: dict[str, set[str]] = {}
    for name in os.environ:
        match = _TOKEN.match(name)
        if match and _set(name):
            found.setdefault(match.group(1), set()).add(match.group(2))
    return found


def in_slack() -> list[str]:
    """The handles that have both tokens, so would be put in Slack by `sympose slack`."""
    return [p["handle"] for p in profile.list_profiles() if slack_credentials.tokens(p["handle"])]


def problems() -> list[str]:
    """What stops a persona being in Slack, one sentence each; nothing for an installation with no Slack token at all."""
    roster = {p["handle"] for p in profile.list_profiles()}
    named = _named_in_env()
    found = []
    for handle in sorted(roster):
        bot, app = (bool(token) for token in slack_credentials.pair(handle))
        if bot != app:
            have, lack = ("bot", "app") if bot else ("app", "bot")
            found.append(f"the persona {handle!r} has its Slack {have} token but not its {lack} token ({slack_credentials.variable(handle, lack)} in .env), so it is not in Slack")
    for key in sorted(set(named) - {slack_credentials.env_key(h) for h in roster}):
        found.append(f"SLACK_{key}_BOT_TOKEN or SLACK_{key}_APP_TOKEN is set in .env, but no persona has that handle, so it is ignored")
    if in_slack():
        if slack_credentials.owner() is None:
            found.append(f"{slack_credentials.OWNER_VARIABLE} is not set in .env, so `sympose slack` will not start (it answers only you)")
        if not slack_approval.approved():
            found.append("a persona has its Slack tokens, but Slack is switched off in Settings, so `sympose slack` will not start")
    return found


def report() -> list[str]:
    """One line for each persona that has both tokens: connected or not. Empty when none has, so nothing is said."""
    lines = []
    for handle in in_slack():
        state = "connected" if slack_heartbeat.connected(handle) else "not connected (is `sympose slack` running?)"
        lines.append(f"- persona {handle}: {state}")
    return ["Slack:", *lines] if lines else []
