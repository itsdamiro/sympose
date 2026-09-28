"""`/context`: what the number under the chat box means, with the figures in full (docs/decisions/018,
"Update"). Read back from what the meter shows, never recomputed."""

from sympose.cli import meter


def render(figures: tuple[int, int] | None, estimated: bool, shown: bool) -> list[str]:
    """`figures` is `(tokens in use, prompt budget)` or `None`; `estimated` while it is the figure
    worked out at a model switch; `shown` is whether the meter line is turned on."""
    if figures is None:
        return ["No context figure yet: the meter fills after the first reply of a chat. It also stays empty "
                "when the model's window is unknown."]
    used, limit = figures
    lines = [f"Context: {used:,} of {limit:,} tokens of the prompt budget ({meter.percent(used, limit)}%)."]
    if estimated:
        lines.append(
            "This is an estimate for the model you switched to, worked out from the conversation so far. It "
            "leaves out the next message's notes, so it may read low; the next reply replaces it with the real figure."
        )
    else:
        lines.append(
            "Counted: the persona's instructions, the notes sent with your last message, the conversation kept "
            "and the last reply, plus a 15% safety margin, so it leans high."
        )
    lines.append(
        "The budget is the model's window minus the room kept for the reply. At 100% the next message starts "
        "leaving older turns out."
    )
    if not shown:
        lines.append(f"The meter under the chat box is hidden ({meter.SETTING} is false in settings.json).")
    return lines
