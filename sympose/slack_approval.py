"""The `slack` approval (docs/decisions/093), in a module of its own so the settings list can name it without bringing in the
engine. Off until the user switches it on, for every persona and every model, since a Slack reply leaves the machine whatever
model wrote it (so this is not one of the categories `sharing.gate` holds back)."""

from sympose import settings_store

SETTING = "slack"


def approved() -> bool:
    """Whether the user has switched Slack on."""
    return settings_store.flag(SETTING, False)
