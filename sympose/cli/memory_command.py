"""`/memory` (docs/decisions/041): refresh a persona's context.md/profile.md now, or review a
staged proposal. A real model call (`memory_refresh.refresh`), so it runs off the interface
thread, on a pool of its own: not the one chat turns use (`turns.py`), so it never queues behind, or
ahead of, an actual reply, and not the loop's default pool, which `/quit` waits on (`turns.py`'s
comment on `_ENGINE_EXECUTOR`) and a 60-second wait would hold up. Several workers, so one wait never
queues behind another (#108)."""

import concurrent.futures

from rich.text import Text

from sympose.cli import off_thread, picker, transcript as transcript_mod
from sympose.cli.selection import SelectionOption
from sympose.engine import memory, memory_refresh, memory_write

_EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4, thread_name_prefix="sympose-memory")

PICKER_KIND = "memory"
CONFIRM_KIND = "memory_confirm"
_STAGED_LINE = 'A memory update is ready to review: /memory, then "Review pending change".'

_SAID = {
    memory_refresh.UNCHANGED: "Nothing to update.",
    memory_refresh.SKIPPED: "Nothing to update from yet: no recaps to learn from, or the model in use is not approved for memory and recaps (/share).",
    memory_refresh.FAILED: "The memory update did not work: the model could not be reached or the files could not be written (see the log).",
}


def announce_pending(app) -> None:
    """Told, not asked, the same posture `share.announce` already uses at launch: a proposal an
    earlier background refresh staged is said once when chat opens, not left for the user to
    discover only by typing `/memory` (docs/decisions/041: "surfaced ... the next time the user
    opens chat")."""
    if memory_write.has_pending(app.persona.handle):
        transcript_mod.mount_line(app, _STAGED_LINE, "system")


async def open_picker(app) -> None:
    options = [SelectionOption("Refresh now", "refresh")]
    if memory_write.has_pending(app.persona.handle):
        options.append(SelectionOption("Review pending change", "review"))
    await picker.open_picker(app, PICKER_KIND, "Memory", options)


async def choose(app, value: str | None) -> None:
    """A row of the `/memory` picker was chosen."""
    if value == "refresh":
        app.run_worker(_run_refresh(app))
    elif value == "review":
        await _open_review(app)


async def _run_refresh(app) -> None:
    handle = app.persona.handle
    # The model the session is actually using, not only the persona's own -- the same forwarding
    # `runtime.py`'s automatic recap/memory refreshes already do on a persona switch.
    model = app.model_override.id if app.model_override else None
    transcript_mod.mount_line(app, "Checking for a memory update...", "system")
    context_before = memory.context(handle)
    # `refresh_in_background`, not `memory_refresh.refresh` directly: this joins a refresh
    # already running for `handle` (the automatic one from launch/persona-switch, say) instead of
    # racing a second, redundant model call against it.
    memory_refresh.refresh_in_background(handle, model)
    finished = await off_thread.run(_EXECUTOR, memory_refresh.wait_for_refresh, handle, 60.0)
    if off_thread.quitting(app):
        return
    if not finished:
        line = "Still checking for a memory update -- try /memory again in a moment."
    elif memory_write.has_pending(handle):
        line = _STAGED_LINE
    elif memory.context(handle) != context_before:
        line = "context.md updated."
    else:
        # No recorded outcome means the refresh raised before it could record one: a failure.
        line = _SAID.get(memory_refresh.last_outcome(handle) or memory_refresh.FAILED, _SAID[memory_refresh.UNCHANGED])
    transcript_mod.mount_line(app, line, "system")
    app.transcript.scroll_end(animate=False)


def _diff_sections(handle: str) -> list[str]:
    sections = []
    for label, current, pending in (
        ("profile.md", memory.profile(handle), memory_write.pending_profile(handle)),
        ("context.md", memory.context(handle), memory_write.pending_context(handle)),
    ):
        if pending is not None:
            sections.append(memory_write.diff_text(current, pending, label))
    return sections


async def _open_review(app) -> None:
    sections = _diff_sections(app.persona.handle)
    if not sections:
        transcript_mod.mount_line(app, "Nothing pending to review.", "system")
        app.transcript.scroll_end(animate=False)
        return
    transcript_mod.mount_line(app, Text("\n\n".join(sections)), "system")
    await picker.open_picker(
        app, CONFIRM_KIND, "Save these changes?", [SelectionOption("Save", "accept"), SelectionOption("Discard", "discard")]
    )


def apply_review(app, value: str | None) -> None:
    """A row of the accept/discard confirm picker was chosen."""
    handle = app.persona.handle
    if value == "accept":
        line = "Saved." if memory_write.accept_pending(handle) else "Couldn't save the changes."
    elif value == "discard":
        memory_write.discard_pending(handle)
        line = "Discarded."
    else:
        return
    transcript_mod.mount_line(app, line, "system")
    app.transcript.scroll_end(animate=False)
