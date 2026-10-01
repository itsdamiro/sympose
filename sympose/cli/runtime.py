"""Slash-command handling and applying a picker's selection. `/clear` and
`/quit` are real, concurrency-aware (they check `pending_turns`/
`turn_locks`/`active_reply_timers`, state `turns.py`/`app.py` own);
Persona-switch continuity (`session_id`/
`session_generation` reset in `apply_picker_choice`) is also real state
that `turns.py`'s generation-guard logic depends on, not mock behavior.
The chat-turn dispatch/streaming path itself lives in `turns.py`, split
out to hold the 200-LOC-per-file cap."""

from rich.style import Style

from sympose import engine
from sympose.cli import (
    compact_command, context_explain, grounded_list, grounding_line, help_notes, memory_command, meter, meter_estimate, picker,
    settings_list, share, stop, transcript as transcript_mod,
)
from sympose.cli.commands import COMMANDS
from sympose import persona_model
from sympose.cli.options import active_model, list_personas
from sympose.engine.model_options import offered
from sympose.cli.selection import SelectionOption
from sympose.engine import memory, memory_refresh
from sympose.profile import set_default_persona


async def run_command(app, command, args: str = "") -> None:
    transcript = app.transcript
    if command.name == "/help":
        transcript_mod.mount_line(app, "Commands:", "system")
        for c in COMMANDS:
            color = app.theme_color("error", "red") if c.danger else app.theme_color("primary", "cyan")
            line = transcript_mod.styled_line(f"  {c.name:<10}", Style(color=color, bold=True), c.summary)
            transcript_mod.mount_line(app, line, "system")
        await help_notes.open_picker(app)  # the Sympose guide: the notes the persona answers from (ADR 019)
    elif command.name == "/model":
        await picker.open_picker(
            app, "model", "Select a model", [SelectionOption(m.label, m.id) for m in offered(active_model(app.persona, app.model_override).id)]
        )
    elif command.name == "/persona":
        await picker.open_picker(
            app,
            "persona",
            "Select a persona",
            [
                SelectionOption(f"{p.name} — {p.title}" if p.title else p.name, p.handle)
                for p in list_personas()
            ],
        )
    elif command.name == "/default":
        if set_default_persona(app.persona.handle):
            line = f"@{app.persona.handle} is now the default persona."
        else:
            line = f"Couldn't save @{app.persona.handle} as the default persona."
        transcript_mod.mount_line(app, line, "system")
    elif command.name == "/grounding":
        turned_on = not grounding_line.enabled()
        if grounding_line.set_enabled(turned_on):
            line = f"Grounded notes are now {'shown' if turned_on else 'hidden'} in reply headers."
        else:
            line = "Couldn't save the grounded-notes setting."
        transcript_mod.mount_line(app, line, "system")
    elif command.name == "/grounded":
        for line in grounded_list.render(app.last_sent, app.persona.name):
            transcript_mod.mount_line(app, line, "system")
    elif command.name == "/context":
        widget = app.query_one(meter.ContextMeter)
        for line in context_explain.render(widget.figures, widget.estimated, meter.enabled()):
            transcript_mod.mount_line(app, line, "system")
    elif command.name == "/compact":
        await compact_command.run(app)
    elif command.name == "/remember":
        # No `memory_remember` gate here: that setting is about a *model* being trusted to write
        # on its own; this is the user's own words, typed directly, no model call (docs/decisions/041).
        if not args:
            transcript_mod.mount_line(app, "Usage: /remember <text> — saved to decisions.md, no model involved.", "system")
        elif memory.append_decision(app.persona.handle, args):
            transcript_mod.mount_line(app, "Saved to decisions.md.", "system")
        else:
            transcript_mod.mount_line(app, "Couldn't save that to decisions.md.", "system")
    elif command.name == "/memory":
        await memory_command.open_picker(app)
    elif command.name == "/share":
        await share.open_picker(app)
    elif command.name == "/clear":
        # A turn that's queued or still running its engine call has no
        # reply widget yet — clearing now would wipe its "You" line, so
        # when that turn later resolves the reply would mount with no
        # visible question above it. `pending_turns`, not a lock's
        # `.locked()`, is what `action_quit` already uses for this same
        # in-flight check (docs/decisions/008); a turn's own streaming
        # reveal (below) only starts after `pending_turns` has already
        # dropped back to 0, so this can't also block a plain clear during
        # an active stream.
        if app.pending_turns > 0:
            transcript_mod.mount_line(
                app, "Can't clear while a reply is in progress or messages are waiting.", "system"
            )
        else:
            # A reply may still be mid-stream — stop its timer rather than
            # let it keep ticking against a transcript that was just cleared
            # out from under it. Two or more replies can be streaming at once
            # (docs/decisions/008 — one lock per persona), so every active
            # timer is stopped, not just one slot's worth.
            for timer in app.active_reply_timers:
                timer.stop()
            app.active_reply_timers.clear()
            app.reply_skips.clear()
            stop.refresh_for(app)
            await transcript.remove_children()
            app.last_speaker = None
    elif command.name == "/settings":
        await settings_list.open_picker(app)
    elif command.name == "/quit":
        # `app.action_quit` (also Textual's own ctrl+q/command-palette
        # quit route) has the in-flight-aware fast-exit check — one place
        # for it, not duplicated here too.
        await app.action_quit()
        return
    transcript.scroll_end(animate=False)


def apply_picker_choice(app, kind: str, value: str | None) -> bool:
    """Apply a picker choice. `True` when the vault is now open to a cloud model that has not been
    asked about it yet, so the caller opens the `/share` list (docs/decisions/031)."""
    transcript = app.transcript
    was_cloud = share.in_cloud(app)
    ask = False
    if kind == "model":
        model = next((m for m in offered(active_model(app.persona, app.model_override).id) if m.id == value), None)
        if model is not None:
            app.model_override = model
            saved = persona_model.set_model(app.persona.handle, model.id)  # the persona's own, kept (ADR 044)
            meter.clear(app)  # the old figure was measured against the previous window
            meter_estimate.start(app, model.id)  # ...and an estimate for the new one, if there is anything to count
            picker.update_banner(app)
            kept = (
                f"Saved for @{app.persona.handle}."
                if saved
                else f"Couldn't save it to @{app.persona.handle}'s persona.yaml: it applies for this session only."
            )
            transcript_mod.mount_line(app, f"Switched model to {model.label}. {kept}", "system")
            ask = share.on_change(app, was_cloud)
    elif kind == "persona":
        persona = next((p for p in list_personas() if p.handle == value), None)
        if persona is not None and persona.handle != app.persona.handle:
            app.persona = persona
            # Each persona has its own saved model (ADR 044): the session's pick was for the last one.
            app.model_override = None
            # Sessions are stored per-handle (sympose/engine/session.py) — an
            # old session_id from the previous persona would resolve to a
            # different persona's directory under the new handle (nothing
            # there, silently empty history) while still writing new turns
            # under the old id, forking/losing history across the switch.
            # A new persona starts a fresh session, same as a fresh process: a new generation has no
            # session id yet, and the old one's stays for a message still queued behind it.
            app.session_generation += 1
            app.last_sent = None  # `/grounded` describes the last reply of the persona now talking, not the previous one (#106)
            meter.clear(app)  # a fresh session starts empty
            picker.update_banner(app)
            # Recaps use the model the user picked, not only the persona's own: the messages go to it (ADR 023).
            engine.refresh_recaps(persona.handle, app.model_override.id if app.model_override else None)
            engine.refresh_embeddings(persona.handle)  # ADR 027
            if memory_refresh.auto_refresh_enabled():  # off by default: /memory refresh always stays manual (ADR 041)
                engine.refresh_memory(persona.handle, app.model_override.id if app.model_override else None)
            engine.refresh_status_phrases(persona.handle, app.model_override.id if app.model_override else None)
            transcript_mod.mount_line(app, f"Now talking to @{persona.handle}.", "system")
            share.on_change(app, was_cloud)  # told, not asked: `/share` is there when they want it
            memory_command.announce_pending(app)  # a proposal an earlier refresh staged is said too (ADR 041)
    elif kind == share.PICKER_KIND:
        if value is not None:
            share.toggle(app, value)
    elif kind == help_notes.PICKER_KIND:
        if value is not None:
            help_notes.show(app, value)
    transcript.scroll_end(animate=False)
    return ask
