"""The Slack App manifest of one persona (docs/decisions/093): what `sympose slack manifest <handle>` prints, so making the
App in Slack is a paste and not a form. It asks for exactly what the adapter uses and nothing more: direct messages to the bot,
mentions of it, `/new`, the files shared with them (`files:read`), Socket Mode (so no public address), no history, no buttons.

The field names and limits are Slack's app manifest reference; the manifest was not tried against a real workspace."""

import json
import re
from typing import Any

from sympose import profile as profile_mod

NAME_LIMIT = 35  # `display_information.name`
BOT_NAME_LIMIT = 80  # `features.bot_user.display_name`, which takes lower case letters, digits, `-`, `_` and `.` only
BOT_SCOPES = ["app_mentions:read", "chat:write", "commands", "files:read", "im:history"]
BOT_EVENTS = ["app_mention", "message.im"]
NEW_COMMAND = {"command": "/new", "description": "Start a new conversation", "should_escape": False}


def _bot_name(handle: str) -> str:
    return re.sub(r"[^a-z0-9._-]", "-", handle.lower())[:BOT_NAME_LIMIT]


def manifest(handle: str, name: str) -> dict[str, Any]:
    """The manifest for the persona `handle` shown as `name` in Slack (a name over Slack's limit is cut)."""
    shown = name.strip()[:NAME_LIMIT] or handle
    return {
        "display_information": {"name": shown, "description": "A persona of Sympose, answering from your notes."},
        "features": {
            "app_home": {"home_tab_enabled": False, "messages_tab_enabled": True, "messages_tab_read_only_enabled": False},
            "bot_user": {"display_name": _bot_name(handle), "always_online": True},
            "slash_commands": [dict(NEW_COMMAND)],
        },
        "oauth_config": {"scopes": {"bot": list(BOT_SCOPES)}},
        "settings": {
            "event_subscriptions": {"bot_events": list(BOT_EVENTS)},
            "interactivity": {"is_enabled": False},
            "org_deploy_enabled": False,
            "socket_mode_enabled": True,
            "token_rotation_enabled": False,
        },
    }


def render(handle: str) -> str | None:
    """The manifest as JSON text, or `None` when there is no such persona."""
    persona = profile_mod.resolve_profile(handle)
    if persona is None:
        return None
    return json.dumps(manifest(persona["handle"], str(persona.get("name") or "")), indent=2)
