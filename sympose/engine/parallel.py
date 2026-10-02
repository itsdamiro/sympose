"""Whether replies in different conversations of one persona run at the same time (docs/decisions/057). A cloud
model's replies run on the provider's servers, so two cost nothing in speed and run side by side. A local model's
replies share one machine's graphics chip and memory, so two at once are each slower, and Ollama must itself be set
to serve requests side by side: they run one after the other. `parallel_replies` says which: `auto` (by the model),
`on` (always side by side, the user's machine and call) or `off` (always one at a time). Two messages in the same
conversation always run in order."""

from sympose import settings_store
from sympose.engine import sharing

SETTING = "parallel_replies"
AUTO, ON, OFF = "auto", "on", "off"


def mode() -> str:
    """The setting as the user chose it; anything else, unset or malformed, is `auto`."""
    chosen = settings_store.get(SETTING)
    return chosen if chosen in (ON, OFF) else AUTO


def side_by_side(model: str) -> bool:
    """Whether a reply by `model` may run while another conversation's reply of the persona is being written."""
    chosen = mode()
    return chosen == ON or (chosen == AUTO and not sharing.is_local(model))
