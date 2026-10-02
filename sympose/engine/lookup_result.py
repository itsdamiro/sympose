"""What one lookup tool call gives back (docs/decisions/040), shared by the tools."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Result:
    """What one tool call gives back: `text` for the model, `hits` (the passages it was sent, as the
    turn record keeps them), `withheld` (what a cloud model was not sent, by category) and `lookup`,
    the entry the turn record keeps for the call (a count, never text)."""

    text: str
    hits: list[dict[str, Any]] = field(default_factory=list)
    withheld: dict[str, int] = field(default_factory=dict)
    lookup: dict[str, Any] = field(default_factory=dict)
    chats: list[dict[str, Any]] = field(default_factory=list)
