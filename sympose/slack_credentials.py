"""Where the Slack credentials come from (docs/decisions/093): the environment, read here and nowhere else. A module of its own
so `sympose doctor` can look without bringing in the chat engine (and litellm, a few seconds) the way `slack_channel` does."""

import os

OWNER_VARIABLE = "SLACK_OWNER_USER_ID"


def owner() -> str | None:
    """The one Slack user whose messages are answered."""
    return (os.getenv(OWNER_VARIABLE) or "").strip() or None


def env_key(handle: str) -> str:
    """The persona's part of its token variable names: `ada-lovelace` is `SLACK_ADA_LOVELACE_BOT_TOKEN`'s `ADA_LOVELACE`."""
    return handle.upper().replace("-", "_")


def tokens(handle: str) -> tuple[str, str] | None:
    """The bot token and the app token of this persona's Slack App, or `None` when it has none (it is then not in Slack)."""
    prefix = f"SLACK_{env_key(handle)}_"
    bot, app = (os.getenv(prefix + name, "").strip() for name in ("BOT_TOKEN", "APP_TOKEN"))
    return (bot, app) if bot and app else None
