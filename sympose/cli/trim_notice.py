"""The reply header's context notices (docs/decisions/015): how many older
turns were left out of what the model was sent because they did not fit its
window, whether the reply stopped at its length limit, and, once, that the start of the conversation
is now stood for by notes (docs/decisions/055). Each shown only on turns where it happened; all
behind one setting."""

from sympose import settings_store

SETTING = "show_trim_notice"


def enabled() -> bool:
    return settings_store.flag(SETTING)


def segment(dropped: int, truncated: bool = False, condensed: int = 0) -> str:
    """` \u00b7 14 earlier turns condensed`, ` \u00b7 3 older turns out of context` (and ` \u00b7 reply cut at the
    length limit`) to append to the header, or `""` when there is nothing to say or the notices are
    turned off. `condensed` is the number of turns newly stood for by notes: the caller passes it only
    on the reply that first used them."""
    if not enabled():
        return ""
    notice = ""
    if condensed > 0:
        notice += f" \u00b7 {condensed} earlier {'turn' if condensed == 1 else 'turns'} condensed"
    if dropped > 0:
        notice += f" \u00b7 {dropped} older {'turn' if dropped == 1 else 'turns'} out of context"
    if truncated:
        notice += " \u00b7 reply cut at the length limit"
    return notice
