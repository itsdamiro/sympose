"""`/context`: what the number under the chat box means, with the figures in full (docs/decisions/018,
"Update"). Read back from what the meter shows, never recomputed."""

from sympose.cli import meter


def render(figures: tuple[int, int] | None, estimated: bool, shown: bool) -> list[str]:
    """`figures` is `(tokens in use, prompt budget)` or `None`; `estimated` while it is the figure
    worked out at a model switch; `shown` is whether the meter line is turned on."""
    if figures is None:
        return ["No memory figure yet: the meter fills after the first reply of a conversation. It also stays "
                "empty when the model's size limit is unknown."]
    used, limit = figures
    lines = [f"Memory used: {used:,} of {limit:,} ({meter.percent(used, limit)}%)."]
    if estimated:
        lines.append(
            "This is an estimate for the model you switched to, worked out from the conversation so far. It "
            "leaves out the next message's notes, so it may read low; the next reply replaces it with the real figure."
        )
    else:
        lines.append(
            "This counts the persona's instructions, notes sent with your last message, the conversation and the "
            "last reply, with a safety margin, so it may read a little high."
        )
    lines.append("At 100% the next message starts leaving out the oldest messages.")
    if not shown:
        lines.append("The meter under the chat box is hidden (turn it on in /settings under Display).")
    return lines
